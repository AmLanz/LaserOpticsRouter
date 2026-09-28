"""LaserOpticsRouter Fusion add-in entry point. See README.md for installation."""
import json
import pathlib
import traceback
import uuid
import tempfile
import datetime
import adsk.core
import adsk.fusion
from . import core, fusion_backend as backend, exports, clipboard_support, workflow

PALETTE_ID = "LaserOpticsRouterPalette"
OPEN_ID = "LaserOpticsRouterOpen"
BUILD_ID = "LaserOpticsRouterBuild"
MANAGE_ID = "LaserOpticsRouterManage"
_handlers = []
_app = None
_ui = None
_preview = None
_pending_build = None
_pending_manage = None
_doc_key = ""
_operation_active = False
_last_build_error = ""
_plans = workflow.PlanCache()
_drafts = workflow.DraftStore()
_draft_key = ""


def diagnostic(message):
    path = pathlib.Path(tempfile.gettempdir()) / "LaserOpticsRouter-build.log"
    try:
        if path.exists() and path.stat().st_size > 1000000: path.write_text("", encoding="utf-8")
        with path.open("a", encoding="utf-8") as stream:
            stream.write(datetime.datetime.now().isoformat()+" ["+core.VERSION+"] "+message+"\n")
            stream.flush()
    except OSError: pass
    return str(path)


def file_exchange(data):
    action = data.get("format", "csv")
    if action not in ("csv", "svg", "import", "document"):
        raise core.LayoutError("Unknown export type.")
    dialog = _ui.createFileDialog()
    dialog.isMultiSelectEnabled = False
    extension = "zip" if action == "document" else "svg" if action == "svg" else "csv"
    dialog.title = ("Import LaserOpticsRouter CSV" if action == "import" else
                    "Export all saved document paths" if action == "document" else "Export LaserOpticsRouter "+action.upper())
    dialog.filter = extension.upper()+" files (*."+extension+")"
    dialog.initialFilename = "LaserOpticsRouter"+("_document" if action == "document" else "")+"."+extension
    result = dialog.showOpen() if action == "import" else dialog.showSave()
    if result != adsk.core.DialogResults.DialogOK: return dict(cancelled=True)
    path = pathlib.Path(dialog.filename)
    if action == "import":
        if path.stat().st_size > 12000000: raise core.LayoutError("CSV file exceeds 12 MB.")
        config = exports.import_csv(path.read_text(encoding="utf-8-sig"), backend.load_component_defaults(design()), data.get("document_id"))
        return dict(config=config, path=str(path))
    if action == "document":
        routes = backend.document_export(design())
        path.write_bytes(exports.export_document_zip(routes, _app.activeDocument.name))
        return dict(path=str(path), route_count=len(routes))
    plan = core.plan_layout(data["config"])
    if action == "csv": text = exports.export_csv(plan)
    elif action == "svg":
        transform = backend.matrix_parts(backend.find_run(design(),data["edit_token"]).transform2) if data.get("edit_token") else None
        text = exports.export_svg(plan, data.get("projection", "XY"), transform)
    else: raise core.LayoutError("Unknown export type.")
    path.write_text(text, encoding="utf-8")
    return dict(path=str(path))


def listen(event, handler, scope=None):
    handler._lor_scope = scope
    event.add(handler)
    _handlers.append((event, handler))


def release_handlers(scope):
    """Do not retain completed Fusion commands for the rest of the session."""
    for event, handler in list(_handlers):
        if getattr(handler, "_lor_scope", None) is scope:
            try: event.remove(handler)
            except Exception: pass
            _handlers.remove((event, handler))


def design():
    product = adsk.fusion.Design.cast(_app.activeProduct)
    if not product:
        raise core.LayoutError("Open a Fusion design in the Design workspace.")
    return product


def palette(): return _ui.palettes.itemById(PALETTE_ID)


def send(action, data):
    p = palette()
    if p and p.isValid:
        try: p.sendInfoToHTML(action, json.dumps(data, allow_nan=False))
        except Exception: _app.log("LaserOpticsRouter UI: "+traceback.format_exc())


def clear_preview():
    global _preview
    if _preview:
        try:
            if _preview.isValid: _preview.deleteMe()
        except Exception: pass
        _preview = None


def bootstrap():
    global _draft_key
    current = design()
    if not _draft_key:
        try: identity = _app.activeDocument.dataFile.id
        except Exception: identity = ""
        _draft_key = identity or backend.document_id(current) or _doc_key
    recovery, recovery_error = None, ""
    try: recovery = _drafts.load(_draft_key)
    except Exception as exc: recovery_error = "Could not read the recovery draft: "+str(exc)
    return dict(config=backend.load_settings(current), saved=backend.saved_endpoints(current),
                document=_app.activeDocument.name, doc_key=_doc_key, version=core.VERSION,
                recovery=recovery, recovery_error=recovery_error,
                build_context=backend.route_build_context(current))


def pick_component():
    p = palette()
    p.isVisible = False
    try:
        selection = _ui.selectEntity("Select the component occurrence to instance as this optic", "Occurrences")
        occurrence = adsk.fusion.Occurrence.cast(selection.entity)
        if not occurrence: raise core.LayoutError("Select a component occurrence in this design.")
        return dict(component_token=occurrence.entityToken, component_ref_token=occurrence.component.entityToken,
                    component_name=occurrence.fullPathName,
                    component_linked=bool(getattr(occurrence, "isReferencedComponent", False)),
                    reference=[0, 0, 0], reference_name="Component origin")
    except RuntimeError:
        return dict(cancelled=True)
    finally:
        if p.isValid: p.isVisible = True


def pick_reference(token):
    current = design()
    found = current.findEntityByToken(token)
    occurrence = next((adsk.fusion.Occurrence.cast(x) for x in found
                       if adsk.fusion.Occurrence.cast(x)), None)
    if not occurrence: raise core.LayoutError("Select the custom component first.")
    p = palette(); p.isVisible = False
    try:
        selection = _ui.selectEntity("Select a point or a circular edge/arc: its centre becomes the beam datum",
                                     "Vertices,SketchPoints,ConstructionPoints,CircularEdges,SketchCurves")
        entity = selection.entity
        sketch_types = (adsk.fusion.SketchPoint, adsk.fusion.SketchCircle, adsk.fusion.SketchArc)
        if isinstance(entity, adsk.fusion.SketchCurve) and not isinstance(entity, sketch_types):
            raise core.LayoutError("Select a circular sketch curve, circular edge or a point.")
        is_curve = isinstance(entity, (adsk.fusion.BRepEdge, adsk.fusion.SketchCircle, adsk.fusion.SketchArc))
        if isinstance(entity, sketch_types):
            hit = entity.worldGeometry.copy()
        else:
            hit = entity.geometry.copy()
        if is_curve:
            curve = adsk.core.Circle3D.cast(hit) or adsk.core.Arc3D.cast(hit)
            if not curve: raise core.LayoutError("Select a circular edge or arc to use its centre.")
            hit = curve.center.copy()
        # Selection geometry on assembly proxies is in the active root context.
        # Native points in non-root components need their occurrence transform.
        context = getattr(entity, "assemblyContext", None)
        owner = getattr(entity, "parentComponent", None)
        if owner is None and isinstance(entity, (adsk.fusion.BRepVertex, adsk.fusion.BRepEdge)): owner = entity.body.parentComponent
        if not isinstance(entity, sketch_types) and context is None and owner == occurrence.component:
            hit.transformBy(occurrence.transform2)
        inverse = occurrence.transform2.copy()
        if not inverse.invert(): raise core.LayoutError("Cannot invert the selected component transform.")
        hit.transformBy(inverse)
        return dict(reference=[hit.x/backend.MM, hit.y/backend.MM, hit.z/backend.MM],
                    reference_name="Circular edge / arc centre" if is_curve else (getattr(entity, "name", "Selected point") or "Selected point"))
    except RuntimeError:
        return dict(cancelled=True)
    finally:
        if p.isValid: p.isVisible = True


class HTMLHandler(adsk.core.HTMLEventHandler):
    def notify(self, args):
        global _preview, _pending_build, _pending_manage, _last_build_error, _operation_active
        try:
            data = json.loads(args.data or "{}")
            action = args.action
            if _operation_active and action != "diagnostic":
                raise core.LayoutError("Wait for the current Fusion operation to finish.")
            if action != "bootstrap" and data.get("doc_key") != _doc_key:
                raise core.LayoutError("The active document changed. Reload this window before continuing.")
            if action == "bootstrap": result = bootstrap()
            elif action == "save_draft":
                result = dict(saved_at=_drafts.save(_draft_key, data["config"], data.get("edit_target")))
            elif action == "discard_draft":
                _drafts.discard(_draft_key); result = {}
            elif action == "analyze":
                clear_preview()
                result = backend.public_plan(design(), _plans.get(data["config"]), data.get("edit_token"))
            elif action == "decode":
                result = backend.endpoint_in_run_frame(design(), data.get("endpoint", ""), data.get("edit_token"))
            elif action == "saved": result = backend.saved_endpoints(design())
            elif action == "schematic": result = backend.document_schematic(design())
            elif action == "refresh_candidates": result = backend.refresh_candidates(design(), data.get("token", ""))
            elif action == "refresh_route":
                if _operation_active or _pending_build or _pending_manage: raise core.LayoutError("Another operation is in progress.")
                clear_preview()
                _app.activeViewport.refresh()
                prepared = backend.prepare_route_refresh(design(), data.get("token", ""), data.get("choices"))
                _pending_build = dict(operation="refresh_route", prepared=prepared, close=False, doc_key=_doc_key)
                _ui.commandDefinitions.itemById(BUILD_ID).execute()
                result = dict(queued=True)
            elif action == "calculate": result = core.calculate_chain(data.get("entries", []), data.get("available"))
            elif action == "file": result = file_exchange(data)
            elif action == "copy_text":
                try:
                    clipboard_support.copy_text(data.get("text", ""))
                    result = dict(copied=True)
                except Exception as exc:
                    result = dict(copied=False, message=str(exc))
            elif action == "diagnostic": result = dict(text=_last_build_error or "No build traceback in this session.")
            elif action == "load_run":
                clear_preview()
                result = backend.load_run(design(), data.get("token", ""))
            elif action == "manage":
                if _operation_active or _pending_manage or _pending_build: raise core.LayoutError("Another operation is in progress.")
                clear_preview()
                _pending_manage = dict(data, doc_key=_doc_key)
                _ui.commandDefinitions.itemById(MANAGE_ID).execute()
                result = dict(queued=True)
            elif action == "pick_component": result = pick_component()
            elif action == "pick_reference": result = pick_reference(data.get("component_token", ""))
            elif action == "preview":
                clear_preview()
                plan = _plans.get(data["config"])
                quality = data.get("quality", "solid")
                if quality not in ("draft", "solid", "selected"): raise core.LayoutError("Unknown preview quality.")
                _operation_active = True
                try:
                    with backend.OperationProgress(_ui if quality != "draft" else None, "Preview optics",
                                                   lambda: data.get("doc_key") == _doc_key) as progress:
                        _preview, warnings = backend.preview(design(), plan, data.get("edit_token"), quality,
                                                             optic_id=data.get("optic_id"), progress=progress)
                finally:
                    _operation_active = False
                _app.activeViewport.refresh()
                result = dict(warnings=warnings)
            elif action == "clear_preview":
                clear_preview(); result = {}
            elif action == "build":
                if _operation_active or _pending_build or _pending_manage: raise core.LayoutError("Another operation is in progress.")
                current = design()
                context = backend.validate_route_build(current, data.get("convert_from"))
                # Dispose preview outside the undoable model transaction.
                clear_preview()
                _app.activeViewport.refresh()
                plan = _plans.get(data["config"])
                diagnostic("Preparing geometry for build (document type: "+context["intent"]+")")
                _operation_active = True
                try:
                    with backend.OperationProgress(_ui, "Prepare route", lambda: data.get("doc_key") == _doc_key) as progress:
                        geometry = backend.temporary_geometry(plan, current, progress=progress)
                finally:
                    _operation_active = False
                _pending_build = dict(config=data["config"], edit_token=data.get("edit_token"),
                                      plan=plan, geometry=geometry,
                                      convert_from=data.get("convert_from"),
                                      close=bool(data.get("close", True)), doc_key=_doc_key)
                _ui.commandDefinitions.itemById(BUILD_ID).execute()
                result = dict(queued=True)
            elif action == "close":
                clear_preview(); palette().isVisible = False; result = {}
            else: raise core.LayoutError("Unknown interface action: "+str(action))
            args.returnData = json.dumps(dict(ok=True, result=result), allow_nan=False)
        except core.LayoutError as exc:
            if args.action in ("build", "refresh_route"): _pending_build = None
            if args.action == "manage": _pending_manage = None
            error = exc.data()
            if args.action in ("build", "refresh_route"):
                try: error["build_context"] = backend.route_build_context(design())
                except Exception: pass
            args.returnData = json.dumps(dict(ok=False, error=error))
        except Exception:
            if args.action in ("build", "refresh_route"):
                _pending_build = None
                _last_build_error = traceback.format_exc()
                diagnostic(_last_build_error)
            if args.action == "manage": _pending_manage = None
            _app.log("LaserOpticsRouter:\n"+traceback.format_exc())
            args.returnData = json.dumps(dict(ok=False, error=dict(message="Fusion operation failed. Details are in Text Commands. "+str(__import__('sys').exc_info()[1]))))


class BuildExecute(adsk.core.CommandEventHandler):
    def __init__(self, context):
        super().__init__()
        self.context = context
    def notify(self, args):
        global _pending_build, _last_build_error
        request = _pending_build
        _pending_build = None
        if request and request.get("operation") == "refresh_route":
            self.context.update(success_action="managed", failure_action="manage_failed")
        try:
            if not request or request["doc_key"] != _doc_key:
                raise core.LayoutError("Document changed before the build started.")
            self.context["request"] = request  # retain transient bodies through command destruction/rollback
            diagnostic("Native build started")
            if request.get("operation") == "refresh_route":
                result = backend.refresh_route(_app, design(), request["prepared"])
            else:
                with backend.OperationProgress(getattr(_app, "userInterface", None), "Build route",
                                               lambda: request["doc_key"] == _doc_key) as progress:
                    result = backend.build(_app, design(), request["plan"], request.get("edit_token"), request["geometry"],
                                           convert_from=request.get("convert_from"), progress=progress)
            diagnostic("Native build completed")
            result["saved"] = backend.saved_endpoints(design())
            self.context["success"] = result
        except Exception as exc:
            args.executeFailed = True
            _last_build_error = traceback.format_exc()
            log = diagnostic(_last_build_error)
            _app.log("LaserOpticsRouter build:\n"+traceback.format_exc())
            self.context["failure"] = dict(message=str(exc)+"\nDiagnostic log: "+log)


class BuildDestroyed(adsk.core.CommandEventHandler):
    def __init__(self, context):
        super().__init__(); self.context = context
    def notify(self, args):
        global _operation_active
        failure = self.context.get("failure")
        success = self.context.get("success")
        close = self.context.get("request", {}).get("close")
        _operation_active = False
        success_action = self.context.get("success_action", "built")
        failure_action = self.context.get("failure_action", "build_failed")
        if failure and self.context.get("request", {}).get("doc_key") == _doc_key:
            # Query after Fusion has finished rollback, not during execute.
            try: failure["build_context"] = backend.route_build_context(design())
            except Exception: pass
        release_handlers(self.context)
        self.context.clear()
        if failure: send(failure_action, failure)
        elif success:
            send(success_action, success)
            if close and palette(): palette().isVisible = False


class BuildCreated(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        global _operation_active
        _operation_active = True
        context = {}
        args.command.isAutoExecute = True
        listen(args.command.execute, BuildExecute(context), context)
        listen(args.command.destroy, BuildDestroyed(context), context)


class ManageExecute(adsk.core.CommandEventHandler):
    def __init__(self, context):
        super().__init__(); self.context = context
    def notify(self, args):
        global _pending_manage
        request = _pending_manage
        _pending_manage = None
        try:
            if not request or request["doc_key"] != _doc_key:
                raise core.LayoutError("The document changed before the operation started.")
            current = design()
            operation = request.get("operation")
            result = dict(operation=operation)
            if operation == "save_default":
                result["component_defaults"] = backend.save_component_default(current, request["key"], request.get("settings"))
            elif operation == "rename_run":
                result["name"] = backend.rename_run(current, request["token"], request.get("name", ""))
            elif operation == "delete_run": result["name"] = backend.delete_run(current, request["token"])
            elif operation == "refresh_status": pass
            else: raise core.LayoutError("Unknown saved-path operation.")
            if operation in ("delete_run", "refresh_status"):
                result["saved"] = backend.refresh_dependencies(_app, current)
            else:
                result["saved"] = backend.saved_endpoints(current)
            self.context["success"] = result
        except Exception as exc:
            args.executeFailed = True
            _app.log("LaserOpticsRouter manage:\n"+traceback.format_exc())
            self.context["failure"] = dict(message=str(exc))


class ManageCreated(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        global _operation_active
        _operation_active = True
        context = dict(success_action="managed", failure_action="manage_failed")
        args.command.isAutoExecute = True
        listen(args.command.execute, ManageExecute(context), context)
        listen(args.command.destroy, BuildDestroyed(context), context)


class PaletteClosed(adsk.core.UserInterfaceGeneralEventHandler):
    def notify(self, args): clear_preview()


def show_palette():
    design()
    p = palette()
    if not p:
        # Fusion's embedded browser needs a file URI, not a native Windows path.
        path = (pathlib.Path(__file__).resolve().parent / "palette.html").as_uri()
        p = _ui.palettes.add(PALETTE_ID, "LaserOpticsRouter", path, True, True, True, 1060, 850, True)
        listen(p.incomingFromHTML, HTMLHandler())
        listen(p.closed, PaletteClosed())
    else:
        p.isVisible = True
        send("reload", {})


class OpenExecute(adsk.core.CommandEventHandler):
    def notify(self, args):
        try: show_palette()
        except Exception as exc: _ui.messageBox(str(exc), "LaserOpticsRouter")


class OpenCreated(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        scope = {}
        listen(args.command.execute, OpenExecute(), scope)
        listen(args.command.destroy, OpenDestroyed(scope), scope)


class OpenDestroyed(adsk.core.CommandEventHandler):
    def __init__(self, scope):
        super().__init__(); self.scope = scope
    def notify(self, args): release_handlers(self.scope)


class DocumentActivated(adsk.core.DocumentEventHandler):
    def notify(self, args):
        global _doc_key, _draft_key
        clear_preview()
        _plans.clear()
        _draft_key = ""
        _doc_key = str(uuid.uuid4())
        send("reload", {})


def run(context):
    global _app, _ui, _doc_key, _draft_key
    _draft_key = ""
    _plans.clear()
    _app = adsk.core.Application.get()
    _ui = _app.userInterface
    _doc_key = str(uuid.uuid4())
    try:
        for identifier, title, description, handler in (
            (OPEN_ID, "LaserOpticsRouter", "Route laser beams, place optics and continue saved endpoints.", OpenCreated()),
            (BUILD_ID, "Build laser layout", "Create or replace the selected route.", BuildCreated()),
            (MANAGE_ID, "Manage laser paths", "Save component defaults, rename or delete a saved route.", ManageCreated())):
            definition = _ui.commandDefinitions.itemById(identifier)
            if definition: definition.deleteMe()
            definition = _ui.commandDefinitions.addButtonDefinition(identifier, title, description)
            listen(definition.commandCreated, handler)
        panel = _ui.allToolbarPanels.itemById("SolidScriptsAddinsPanel")
        if panel and not panel.controls.itemById(OPEN_ID):
            control = panel.controls.addCommand(_ui.commandDefinitions.itemById(OPEN_ID))
            control.isPromoted = True
        listen(_app.documentActivated, DocumentActivated())
        # Startup loading registers the button quietly; explicit Run opens it.
        if not isinstance(context, dict) or not context.get("IsApplicationStartup", False):
            show_palette()
    except Exception:
        _ui.messageBox("LaserOpticsRouter could not start:\n"+traceback.format_exc())


def stop(context):
    global _pending_build, _pending_manage
    clear_preview()
    _plans.clear()
    _pending_build = None
    _pending_manage = None
    if _ui:
        p = palette()
        if p: p.deleteMe()
        panel = _ui.allToolbarPanels.itemById("SolidScriptsAddinsPanel")
        if panel:
            control = panel.controls.itemById(OPEN_ID)
            if control: control.deleteMe()
        for identifier in (OPEN_ID, BUILD_ID, MANAGE_ID):
            definition = _ui.commandDefinitions.itemById(identifier)
            if definition: definition.deleteMe()
    for event, handler in reversed(_handlers):
        try: event.remove(handler)
        except Exception: pass
    _handlers.clear()
