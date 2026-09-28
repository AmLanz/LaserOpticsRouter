"""Fusion BRep generation, component instances and document endpoint records."""
import datetime
import copy
import json
import math
import uuid
import time
from dataclasses import asdict, replace
import adsk.core
import adsk.fusion
try:
    from . import core
except ImportError:
    import core

GROUP = "LaserOpticsRouter"
MM = 0.1
COLORS = {"beam": (245, 48, 60), "lens": (111, 208, 224),
          "mirror": (177, 184, 193), "oap": (215, 176, 90),
          "pol": (105, 111, 120), "bs": (63, 122, 235), "bsc": (90, 157, 239),
          "wp": (144, 208, 197), "rp": (166, 198, 231), "bd": (202, 207, 221),
          "housing": (38, 43, 50), "interface": (96, 106, 118), "orientation": (232, 183, 66)}
COLORS["generic"] = (180, 164, 213)
COLORS.update(laha=(174, 208, 211), laqu=(185, 196, 221), nd=(89, 100, 112), tp=(163, 198, 216))
COLORS.update({"beam-"+name: tuple(int(value[i:i+2], 16) for i in (1,3,5))
               for name, value in core.BEAM_COLORS.items() if name != "red"})


def beam_kind(color):
    return "beam" if color == "red" else "beam-"+color


class OperationProgress:
    """Modal progress with bounded event pumping on Fusion's main thread.

    Call only between native operations, never while editing a base feature.
    A single kernel operation cannot be interrupted by this mechanism.
    """
    def __init__(self, ui, title, guard=None):
        self.ui, self.title, self.guard = ui, title, guard
        self.dialog, self.last_pump = None, 0.0

    def __enter__(self):
        if self.ui and hasattr(self.ui, "createProgressDialog"):
            self.dialog = self.ui.createProgressDialog()
            self.dialog.isCancelButtonShown = True
            self.dialog.cancelButtonText = "Cancel"
            self.dialog.show(self.title, "Preparing…", 0, 100, 1)
        return self.report

    def report(self, label, done=0, total=1):
        if self.dialog:
            self.dialog.message = label
            self.dialog.progressValue = max(0, min(100, int(100*done/max(1,total))))
        now = time.monotonic()
        if now-self.last_pump >= 0.08 or done >= total:
            self.last_pump = now
            pump = getattr(adsk, "doEvents", None)
            if pump: pump()
        if self.guard and not self.guard():
            raise core.LayoutError("The active document changed. Operation cancelled.")
        if self.dialog and self.dialog.wasCancelled:
            raise core.LayoutError("Operation cancelled.")

    def __exit__(self, *exc):
        if self.dialog: self.dialog.hide()


def insert_custom_component(design, parent, optic, component, placement):
    """Reuse the component definition; never copy, edit, or break its source link."""
    linked = optic["settings"].get("component_linked", False)
    token = optic["settings"].get("component_token")
    for source in design.findEntityByToken(token) if token else []:
        if isinstance(source, adsk.fusion.Occurrence):
            linked = linked or bool(getattr(source, "isReferencedComponent", False))
    inserted = parent.occurrences.addExistingComponent(component, placement)
    if not inserted: raise RuntimeError("Could not instance custom component for "+optic["label"])
    if linked and not getattr(inserted, "isReferencedComponent", False):
        raise core.LayoutError(optic["label"]+": Fusion did not preserve the external component link. "
                               "Build cancelled. Reinsert the source as a linked component and select it again.")
    return inserted


def protect_inserted_component(occurrence, warnings):
    """Selection guard on this newly created instance, not an edit lock."""
    try:
        occurrence.isSelectable = False
        if occurrence.isSelectable: raise RuntimeError("Selection guard was not retained.")
    except Exception:
        message = "Fusion could not make an inserted CAD instance unselectable. Review its Selectable setting in the browser."
        if message not in warnings: warnings.append(message)


def route_build_context(design):
    """Read design intent without changing the document or its modeling history.

    Fusion before January 2026 has no designIntent API and supports the
    original internal-component workflow. designType is a different property:
    changing it can destroy the parametric timeline, so never use it here.
    """
    types = getattr(adsk.fusion, "DesignIntentTypes", None)
    try:
        intent = design.designIntent
    except AttributeError:
        return dict(intent="legacy", can_build=True, requires_hybrid=False, message="")
    except Exception as exc:
        return dict(intent="unavailable", can_build=False, requires_hybrid=False,
                    message="Cannot read this document's design type. Reopen the palette and try again. "+str(exc))
    for name in ("hybrid", "part", "assembly"):
        value = getattr(types, name.title()+"DesignIntentType", None)
        if value is not None and intent == value:
            restricted = name != "hybrid"
            reason = ("Part documents allow only one component." if name == "part" else
                      "Assembly documents allow external components only.")
            message = (reason+" This route needs internal components. Switch to Hybrid & build changes "
                       "this document to Hybrid, then creates the route. Preview keeps the current document type."
                       if restricted else "")
            return dict(intent=name, can_build=True, requires_hybrid=restricted, message=message)
    return dict(intent="unavailable", can_build=False, requires_hybrid=False,
                message="This Fusion document type is not supported. Open a Hybrid design to build routes.")


def validate_route_build(design, convert_from=None):
    context = route_build_context(design)
    if not context["can_build"]:
        raise core.LayoutError(context["message"])
    if context["requires_hybrid"] and convert_from != context["intent"]:
        raise core.LayoutError("This is a "+context["intent"].title()+" document. LaserOpticsRouter needs "
                               "Hybrid to create internal route components. Use Switch to Hybrid & build "
                               "in Layout, or change the document to Hybrid in Fusion and try again.")
    return context


def point(p): return adsk.core.Point3D.create(*(x*MM for x in p))
def vector(v): return adsk.core.Vector3D.create(*v)


def matrix(origin, columns):
    m = adsk.core.Matrix3D.create()
    if not m.setWithCoordinateSystem(point(origin), *(vector(v) for v in columns)):
        raise RuntimeError("Could not construct the optic coordinate transform.")
    return m


def custom_placement(optic):
    """The same component-origin-to-optic transform for preview and native build."""
    return matrix(*core.custom_transform(optic))


def compose_placements(parent, local):
    """Map local coordinates through the parent, with translations in mm."""
    origin, axes = matrix_parts(parent)
    local_origin, local_axes = matrix_parts(local)
    return matrix(core.add(origin, core.world(axes, local_origin)),
                  tuple(core.world(axes, axis) for axis in local_axes))


def root_proxy(native, parent, label):
    """Add a rooted parent's full assembly path to a newly inserted child."""
    if native.assemblyContext is not None:
        raise core.LayoutError(label+": expected a native occurrence from insertion.")
    proxy = native.createForAssemblyContext(parent)
    if not proxy or proxy.assemblyContext is None:
        raise core.LayoutError(label+": Fusion could not resolve the root assembly context.")
    return proxy


def check_occurrence_pose(occurrence, expected, label):
    actual = occurrence.transform2
    def xyz(value): return (value.x, value.y, value.z)
    a, b = point((0, 0, 0)), point((0, 0, 0))
    a.transformBy(actual); b.transformBy(expected)
    position_error = core.norm(core.sub(xyz(a), xyz(b)))/MM
    axis_error = 0.0
    for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        a, b = vector(axis), vector(axis)
        a.transformBy(actual); b.transformBy(expected)
        axis_error = max(axis_error, core.norm(core.sub(xyz(a), xyz(b))))
    if position_error > 1e-5 or axis_error > 1e-8:
        raise core.LayoutError(f"{label}: Fusion did not retain the preview placement "
                               f"(position error {position_error:.6g} mm; axis error {axis_error:.3g}). "
                               "Build cancelled rather than keeping a shifted optic.")


def set_occurrence_pose(occurrence, expected, label):
    """Place a new root occurrence or rooted proxy in design-root coordinates.

    Nested natives must first pass through root_proxy: Fusion only accepts
    transform overrides on their root-context proxies. For those proxies use
    transform2 and capture the position once; initialTransform is reserved for
    top-level occurrences so its coordinate convention cannot be ambiguous.
    Source occurrences are never passed here or modified.
    """
    try:
        check_occurrence_pose(occurrence, expected, label)
        return False  # Insertion already placed it; do not edit its timeline.
    except core.LayoutError:
        pass
    # isGrounded is pinning, and its getter throws on subcomponents. New
    # occurrences are not pinned. Only release automatic grounding to parent.
    if getattr(occurrence, "isGroundToParent", False):
        occurrence.isGroundToParent = False
    if occurrence.assemblyContext is None:
        # Autodesk has published both spellings. Only root natives reach here.
        can_edit = (getattr(occurrence, "isVaildForEditInitialPosition", False) or
                    getattr(occurrence, "isValidForEditInitialPosition", False))
        if can_edit:
            try:
                occurrence.initialTransform = expected.copy()
                check_occurrence_pose(occurrence, expected, label)
                return False
            except (RuntimeError, AttributeError):
                pass
    occurrence.transform2 = expected.copy()
    check_occurrence_pose(occurrence, expected, label)
    return True


def capture_placements(design, pending, checks):
    if pending and design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
        if design.snapshots.hasPendingSnapshot:
            snapshot = design.snapshots.add()
            if not snapshot: raise RuntimeError("Fusion could not capture the optic placements.")
    for occurrence, expected, label in checks:
        check_occurrence_pose(occurrence, expected, label)


def cylinder(manager, p0, r0, p1, r1):
    if r0 == 0: p0, p1, r0, r1 = p1, p0, r1, r0
    body = manager.createCylinderOrCone(point(p0), r0*MM, point(p1), r1*MM)
    if not body: raise RuntimeError("Fusion could not create a beam/optic solid. Check very small dimensions.")
    return body


def boolean(manager, target, tool, operation):
    if not manager.booleanOperation(target, tool, operation):
        raise RuntimeError("Fusion's solid operation failed. Check coincident surfaces or extreme dimensions.")
    return target


def box(manager, center, columns, lengths):
    bound = adsk.core.OrientedBoundingBox3D.create(point(center), vector(columns[0]), vector(columns[1]),
                                                 *(length*MM for length in lengths))
    body = manager.createBox(bound)
    if not body: raise RuntimeError("Fusion could not create the reference box.")
    return body


def halfspace(manager, plane, normal, extent):
    center = core.sub(plane, core.mul(normal, extent/2))
    basis = core.frame(normal)
    return box(manager, center, (basis[2], basis[0], basis[1]), (extent, extent, extent))


def extension(state, normal, forward):
    cosine = abs(core.dot(state.d, normal))
    if cosine < 1e-7 or state.radius == 0: return None
    k = math.sqrt(max(0, 1-cosine*cosine))/cosine
    max_slope = (math.sqrt(state.beta/state.q_imag) if state.model == "gaussian" else abs(state.slope))
    if max_slope*k >= 0.95: return None
    ext = (state.radius*k+1e-4)/(1-max_slope*k)
    if state.model == "geometric" and state.y*(state.y+(1 if forward else -1)*state.slope*ext) < 0:
        return None
    return ext


def segment_bodies(manager, seg, options, warnings):
    state, length = seg["state"], seg["length"]
    tolerance = core.finite(options.get("gaussian_tolerance_mm", 0.01), "Gaussian display tolerance")
    if tolerance <= 0: raise core.LayoutError("Gaussian display tolerance must be positive.")
    knots = core.sample_segment(seg, tolerance)
    trims = [None, None]
    if options.get("clean_joints", True):
        for index, optic in enumerate((seg["trim_start"], seg["trim_end"])):
            if not optic: continue
            if optic["bend_deg"] < 10:
                warnings.append(optic.get("label", "Mirror")+": bend below 10°; envelope joint not trimmed.")
                continue
            edge = state if index == 0 else state.propagated(length)
            ext = extension(edge, optic["normal"], index == 1)
            if ext is None:
                warnings.append(optic.get("label", "Mirror")+": focus/grazing geometry prevents a clean joint.")
                continue
            t = -ext if index == 0 else length+ext
            knots[0 if index == 0 else -1] = (t, state.propagated(t).radius)
            trims[index] = optic
    result = []
    for i, ((t0, r0), (t1, r1)) in enumerate(zip(knots, knots[1:])):
        if t1-t0 < 1e-9: continue
        if state.model == "gaussian" and min(r0, r1) < 0.00005:
            warnings.append("Gaussian radius below 0.05 µm: display radius limited to Fusion's practical modeling scale; reported beam state is unchanged.")
            r0, r1 = max(r0, 0.00005), max(r1, 0.00005)
        a, b = core.add(state.position, core.mul(state.d, t0)), core.add(state.position, core.mul(state.d, t1))
        body = cylinder(manager, a, r0, b, r1)
        extent = 4*(abs(t1-t0)+r0+r1+1)
        for index, optic in enumerate(trims):
            if optic and ((index == 0 and i == 0) or (index == 1 and i == len(knots)-2)):
                cutter = halfspace(manager, optic["position"], optic["normal"], extent)
                boolean(manager, body, cutter, adsk.fusion.BooleanTypes.DifferenceBooleanType)
        result.append((seg["name"]+(f" · {i+1}" if len(knots) > 2 else ""), body, beam_kind(state.color)))
    return result


def optic_bodies(manager, optic, options):
    p, n = tuple(optic["position"]), tuple(optic["normal"])
    diameter, kind = optic["diameter_mm"], optic["kind"]
    radius = diameter/2
    basis = core.representation_frame(optic)
    if optic.get("visual_flip"):
        n = core.world(basis, tuple(core.dot(n, v) for v in optic["frame"]))
    if kind == "bd":
        # Datum stays on the ordinary ray; centre the built-in aperture between
        # the two axes. Combining reverses local walk-off, not this aperture.
        p = core.add(p,core.world(basis,((-1 if optic.get("combining") else 1)*optic["amount"]/2,0,0)))
    def at(local): return core.add(p, core.world(basis, local))
    name = optic["label"]
    if kind == "generic":
        if optic["shape"] == "cube": body = box(manager, p, basis, (diameter, diameter, diameter))
        elif optic["shape"] == "ball":
            body = manager.createSphere(point(p), radius*MM)
            if not body: raise RuntimeError("Fusion could not create the generic ball.")
        else:
            half = optic["depth_mm"]/2
            body = cylinder(manager, at((0,0,-half)), radius, at((0,0,half)), radius)
        return [(name, body, kind)]
    if kind in core.PRISMS:
        length, width = optic["tube_length_mm"], optic["crystal_width_mm"]
        scale = diameter/25.4
        body = cylinder(manager, at((0,0,-length/2)), radius, at((0,0,length/2)), radius)
        opening = box(manager,p,basis,(width,width,length+max(1,scale)))
        boolean(manager,body,opening,adsk.fusion.BooleanTypes.DifferenceBooleanType)
        crystal_length = length if kind == "bd" else min(width,length)
        crystal = box(manager,p,basis,(width,width,crystal_length))
        result = [(name+" · housing",body,"housing"),(name+" · crystal",crystal,kind)]
        if kind in ("wp","rp"):
            interface_frame = core.frame(core.world(basis,(1,0,1)),basis[1])
            plane = box(manager,p,interface_frame,(width*2,max(width,crystal_length)*2,0.08*scale))
            boolean(manager,plane,manager.copy(crystal),adsk.fusion.BooleanTypes.IntersectionBooleanType)
            result.append((name+" · orientation interface",plane,"interface"))
        else:
            # Small mark on the entrance rim indicates the local walk-off side.
            a, b, c = (width/2+radius)/2, radius*.88, radius*.96
            z = -length/2-0.25*scale
            mark = cylinder(manager,at((a,0,z)),0.15*scale,at((b,0,z)),0.15*scale)
            head = cylinder(manager,at((b,0,z)),0.5*scale,at((c,0,z)),0)
            result.extend([(name+" · offset side",mark,"orientation"),(name+" · offset arrow",head,"orientation")])
        return result
    if kind == "lens":
        thickness = core.finite(options.get("lens_thickness_mm", 2))
        sag = min(radius*0.12, 4)
        curvature = (radius*radius+sag*sag)/(2*sag)
        positive = optic["focal_mm"] > 0
        half_center = thickness/2+sag if positive else thickness/2
        half_edge = thickness/2 if positive else thickness/2+sag
        h = max(half_center, half_edge)
        body = cylinder(manager, at((0, 0, -h)), radius, at((0, 0, h)), radius)
        for sign in (-1, 1):
            c = sign*(half_center-curvature if positive else half_center+curvature)
            sphere = manager.createSphere(point(at((0, 0, c))), curvature*MM)
            boolean(manager, body, sphere, adsk.fusion.BooleanTypes.IntersectionBooleanType if positive
                    else adsk.fusion.BooleanTypes.DifferenceBooleanType)
        return [(name, body, kind)]
    if kind == "bsc":
        body = box(manager, p, basis, (diameter, diameter, diameter))
        plane_basis = core.frame(n, basis[1])
        plane = box(manager, p, (plane_basis[2], plane_basis[0], plane_basis[1]),
                    (min(0.15, diameter/100), diameter, diameter*math.sqrt(2)))
        boolean(manager, plane, manager.copy(body), adsk.fusion.BooleanTypes.IntersectionBooleanType)
        return [(name, body, kind), (name+" · internal splitter", plane, "bs")]
    if kind == "oap":
        data = optic["oap"]
        rho, f = data["decenter_mm"], data["parent_focal_mm"]
        rmin, rmax = max(0, rho-radius), rho+radius
        z0, z1 = (rmin*rmin-rho*rho)/(4*f), (rmax*rmax-rho*rho)/(4*f)
        thickness = core.finite(options.get("oap_thickness_mm", 4))
        body = cylinder(manager, at((0, 0, z0-thickness)), radius, at((0, 0, z1)), radius)
        # Conical bands sample the analytic parent paraboloid. Sag error <= 0.01 mm
        # unless the 160-band complexity cap is reached. This is a layout surface.
        count = min(160, max(12, math.ceil((rmax-rmin)/math.sqrt(16*f*0.01))))
        radii = sorted(set([rmin+(rmax-rmin)*i/count for i in range(count+1)]+[rho]))
        for a, b in zip(radii, radii[1:]):
            za, zb = (a*a-rho*rho)/(4*f), (b*b-rho*rho)/(4*f)
            cutter = cylinder(manager, at((-rho, 0, za)), a, at((-rho, 0, zb)), b)
            boolean(manager, body, cutter, adsk.fusion.BooleanTypes.DifferenceBooleanType)
        return [(name, body, kind)]
    thickness = (1.0 if kind in ("pol", "laha", "laqu") else 2.5 if kind == "nd" else 1.5 if kind in ("bs", "tp")
                 else core.finite(options.get("mirror_thickness_mm", 3)))
    if kind in ("pol", "laha", "laqu", "nd", "tp"): a, b = core.sub(p, core.mul(n, thickness/2)), core.add(p, core.mul(n, thickness/2))
    else: a, b = core.sub(p, core.mul(n, thickness)), p
    return [(name, cylinder(manager, a, radius, b, radius), kind)]


def resolve_component(design, optic):
    for field in ("component_ref_token", "component_token"):
        token = optic["settings"].get(field, "")
        if not token: continue
        for entity in design.findEntityByToken(token):
            if isinstance(entity, adsk.fusion.Occurrence): return entity.component
            if isinstance(entity, adsk.fusion.Component): return entity
    raise core.LayoutError(optic["label"]+": the selected component no longer exists. Select it again.")


def temporary_geometry(plan, design, beam_only=False, progress=None):
    manager = adsk.fusion.TemporaryBRepManager.get()
    options = plan["config"].get("options", {})
    warnings = list(plan["warnings"])
    for key in ("lens_thickness_mm", "mirror_thickness_mm", "oap_thickness_mm"):
        if core.finite(options.get(key, 2)) <= 0: raise core.LayoutError("Optic thickness must be positive.")
    for key in ("beam_opacity", "optics_opacity"):
        if not 0 <= core.finite(options.get(key, 0.5)) <= 1: raise core.LayoutError("Opacity must be between 0 and 1.")
    beam, optics, customs = [], [], []
    count, total = 0, len(plan["segments"])+(0 if beam_only else len(plan["optics"]))
    for segment in plan["segments"]:
        if progress: progress("Preparing beam section "+str(count+1), count, total)
        beam.extend(segment_bodies(manager, segment, options, warnings))
        count += 1
        if len(beam) > 5000: raise core.LayoutError("This layout creates more than 5000 beam sections. Build it in smaller steps.")
    for optic in ([] if beam_only else plan["optics"]):
        if progress: progress("Preparing "+optic["label"], count, total)
        if optic["settings"].get("custom") and options.get("use_assigned_components", True):
            customs.append((optic, resolve_component(design, optic)))
        elif options.get("show_optics", True):
            optics.extend(optic_bodies(manager, optic, options))
        count += 1
    if progress: progress("Geometry prepared", total, total)
    return dict(beam=beam, optics=optics, custom=customs, warnings=list(dict.fromkeys(warnings)))


def appearance(app, design, kind):
    name = GROUP+" "+kind
    existing = design.appearances.itemByName(name)
    if existing: return existing
    library = app.materialLibraries.itemById("BA5EE55E-9982-449B-9D66-9F036540E140")
    source = library.appearances.itemById("Prism-093") if library else None
    if not source: return None
    result = design.appearances.addByCopy(source, name)
    prop = adsk.core.ColorProperty.cast(result.appearanceProperties.itemById("opaque_albedo"))
    if prop: prop.value = adsk.core.Color.create(*COLORS[kind], 255)
    return result


def add_bodies(component, design, entries):
    if not entries: return []
    base = None
    if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
        base = component.features.baseFeatures.add()
        base.name = "LaserOpticsRouter geometry"
        if not base.startEdit(): raise RuntimeError("Could not enter the geometry base feature.")
    bodies = []
    start_count = 0 if base else component.bRepBodies.count
    try:
        for name, temporary, kind in entries:
            body = component.bRepBodies.add(temporary, base) if base else component.bRepBodies.add(temporary)
            if not body: raise RuntimeError("Could not add body "+name)
            body.name = name
    finally:
        if base and not base.finishEdit(): raise RuntimeError("Could not finish the geometry base feature.")
    collection = base.bodies if base else component.bRepBodies
    if collection.count != start_count+len(entries): raise RuntimeError("Unexpected number of created bodies.")
    for i, (name, _, kind) in enumerate(entries):
        body = collection.item(start_count+i)
        body.name = name
        if kind == "beam" or kind.startswith("beam-"):
            body.attributes.add(GROUP, "beam_style", kind)
        bodies.append((body, kind))
    return bodies


def load_settings(design):
    defaults = core.default_config()
    attr = design.attributes.itemByName(GROUP, "last_settings")
    if attr:
        try:
            data = json.loads(attr.value)
            if data.get("version") == 1:
                data.setdefault("options", {}).setdefault("use_assigned_components", True)
                defaults.update(data)
        except (ValueError, TypeError): pass
    defaults["options"] = dict(core.default_config()["options"], **defaults.get("options", {}))
    defaults["route_id"] = uuid.uuid4().hex  # reopening starts a new independent build
    doc = design.attributes.itemByName(GROUP, "document_id")
    if doc: defaults["document_id"] = doc.value
    defaults["component_defaults"] = load_component_defaults(design)
    return defaults


def load_component_defaults(design):
    attr = design.attributes.itemByName(GROUP, "component_defaults")
    if attr:
        try:
            data = json.loads(attr.value)
            if isinstance(data, dict): return core.normalize_component_defaults(data)
        except (ValueError, TypeError): pass
    return {}


def save_component_default(design, key, settings):
    token = core.default_token(key)
    key = core.default_key(token)
    defaults = load_component_defaults(design)
    if settings is None: defaults.pop(key, None)
    else:
        template = core.component_template(settings)
        if template["custom"]: resolve_component(design, dict(label=key, settings=template))
        core._optic(core.BeamState(), token, key, template, core.default_config()["sizes"])
        core.budget_values(token["kind"], template)
        if abs(core.finite(template.get("displacement_mm", 0))) > 10000:
            raise core.LayoutError("Transmission displacement must be at most 10000 mm in magnitude.")
        defaults[key] = template
    old = design.attributes.itemByName(GROUP, "component_defaults")
    if old and not design.attributes.itemByName(GROUP, "component_defaults_before_1_2_0"):
        # Keep the original table when the first save merges old orientation keys.
        old_defaults = json.loads(old.value)
        if old_defaults != core.normalize_component_defaults(old_defaults):
            design.attributes.add(GROUP, "component_defaults_before_1_2_0", old.value)
    design.attributes.add(GROUP, "component_defaults", json.dumps(defaults, allow_nan=False))
    return defaults


def find_run(design, token, editable=False):
    for entity in design.findEntityByToken(token):
        occurrence = adsk.fusion.Occurrence.cast(entity)
        if occurrence and occurrence.component.attributes.itemByName(GROUP, "run_id"):
            if editable and occurrence.assemblyContext is not None:
                raise core.LayoutError("Edit/delete routes at the design root. Nested route instances support endpoint copying only.")
            return occurrence
    raise core.LayoutError("This saved route no longer exists. Refresh the saved paths list.")


def load_run(design, token):
    occurrence = find_run(design, token, editable=True)
    attr = occurrence.component.attributes.itemByName(GROUP, "settings")
    if not attr: raise core.LayoutError("This route has no editable settings.")
    config = core.snapshot_config(core.plan_layout(json.loads(attr.value)))
    config["route_id"] = occurrence.component.attributes.itemByName(GROUP, "run_id").value
    config["component_defaults"] = load_component_defaults(design)
    return dict(config=config, token=occurrence.entityToken, name=occurrence.component.name)


def rename_run(design, token, name):
    occurrence = find_run(design, token, editable=True)
    name = str(name).strip()[:100]
    if not name: raise core.LayoutError("Enter a path/run name.")
    main = occurrence.component
    attr = main.attributes.itemByName(GROUP, "settings")
    config = json.loads(attr.value)
    config["run_name"] = name
    main.name = name
    main.attributes.add(GROUP, "settings", json.dumps(config, allow_nan=False))
    return name


def delete_run(design, token):
    occurrence = find_run(design, token, editable=True)
    name = occurrence.component.name
    if not occurrence.deleteMe(): raise RuntimeError("Fusion could not delete this route.")
    return name


def build(app, design, plan, replace_token=None, prepared=None, convert_from=None, progress=None):
    # Recheck inside the native command: the document type may have changed
    # since the palette displayed the explicitly labelled conversion action.
    context = validate_route_build(design, convert_from)
    old = find_run(design, replace_token, editable=True) if replace_token else None
    geometry = prepared if prepared is not None else temporary_geometry(plan, design)
    options = plan["config"].get("options", {})
    previous_active = getattr(design, "activeOccurrence", None)
    occurrence = None
    pending_capture, pose_checks = False, []
    succeeded = False
    stage = "Activate design root"
    done, total = 0, len(geometry["beam"])+len(geometry["optics"])+len(geometry["custom"])+3
    try:
        if progress: progress(stage, done, total)
        if previous_active and not design.activateRootComponent():
            raise RuntimeError("Could not activate the design root for component placement.")
        if context["requires_hybrid"]:
            stage = "Switch document to Hybrid"
            try:
                design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
                if route_build_context(design)["intent"] != "hybrid":
                    raise RuntimeError("Fusion did not retain the Hybrid document type.")
            except Exception as exc:
                raise core.LayoutError("Fusion could not switch this document to Hybrid. "
                                       "Change its design type to Hybrid in Fusion, then build again. "+str(exc)) from exc
        route_placement = old.transform2.copy() if old else adsk.core.Matrix3D.create()
        stage = "Create route component"
        occurrence = design.rootComponent.occurrences.addNewComponent(route_placement)
        if not occurrence: raise RuntimeError("Could not create the route component.")
        stage = "Place route origin"
        pending_capture |= set_occurrence_pose(occurrence, route_placement, "Route origin")
        pose_checks.append((occurrence, route_placement, "Route origin"))
        main = occurrence.component
        name = str(plan["config"].get("run_name") or GROUP)[:100]
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        main.name = name+" · "+stamp
        main.description = "LaserOpticsRouter layout. Saved beam states and settings are attached to this component."
        styled = []
        for label, entries, opacity in (("Beam", geometry["beam"], options.get("beam_opacity", 0.3)),
                                        ("Optics", geometry["optics"], options.get("optics_opacity", 0.65))):
            if not entries and not (label == "Optics" and geometry["custom"]): continue
            stage = "Create "+label+" component"
            child_occ = main.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            if not child_occ: raise RuntimeError("Could not create the "+label+" component.")
            stage = "Resolve and place "+label+" in root context"
            child_proxy = root_proxy(child_occ, occurrence, label)
            pending_capture |= set_occurrence_pose(child_proxy, route_placement, label+" origin")
            pose_checks.append((child_proxy, route_placement, label+" origin"))
            child = child_occ.component
            child.name, child.opacity = label, opacity
            child.attributes.add(GROUP, "role", label.lower())
            stage = "Add "+label+" solids"
            # Close each base feature before pumping events or honouring Cancel.
            # Limit transient insertion work while keeping one native Undo step.
            for offset in range(0, len(entries), 40):
                batch = entries[offset:offset+40]
                styled.extend(add_bodies(child, design, batch))
                done += len(batch)
                if progress: progress(stage, done, total)
            if label == "Optics":
                for optic, component in geometry["custom"]:
                    placement = custom_placement(optic)
                    stage = "Insert custom optic "+optic["label"]
                    # Insertion uses parent coordinates. Correction/verification
                    # use a root proxy and the composed root-coordinate target.
                    if progress: progress(stage, done, total)
                    new_occ = insert_custom_component(design, child, optic, component, placement)
                    stage = "Resolve and place custom optic "+optic["label"]+" in root context"
                    new_proxy = root_proxy(new_occ, child_proxy, optic["label"])
                    root_placement = compose_placements(route_placement, placement)
                    pending_capture |= set_occurrence_pose(new_proxy, root_placement, optic["label"])
                    pose_checks.append((new_proxy, root_placement, optic["label"]))
                    if options.get("protect_components", True):
                        protect_inserted_component(new_occ, geometry["warnings"])
                    done += 1
                    if progress: progress("Placed "+optic["label"], done, total)
        stage = "Apply beam and optic colors"
        color_warning = "Geometry was created; appearance assignment was unavailable in this Fusion installation."
        try:
            appearances = {kind: appearance(app, design, kind) for kind in {k for _, k in styled}}
        except Exception:
            appearances = {}
            geometry["warnings"].append(color_warning)
        for index, (body, kind) in enumerate(styled):
            # Keep cancellation outside the cosmetic-failure fallback.
            if progress and index % 40 == 0:
                progress(stage+" · "+str(index+1)+" / "+str(len(styled)), done, total)
            try:
                if appearances.get(kind): body.appearance = appearances[kind]
            except Exception:
                if color_warning not in geometry["warnings"]: geometry["warnings"].append(color_warning)
                break
        stage = "Save route records"
        if progress: progress(stage, done+1, total)
        run_id = old.component.attributes.itemByName(GROUP, "run_id").value if old else plan["config"].get("route_id", uuid.uuid4().hex)
        rev_attr = old.component.attributes.itemByName(GROUP, "revision") if old else None
        revision = int(rev_attr.value if rev_attr else 1)+1 if old else 1
        main.attributes.add(GROUP, "revision", str(revision))
        main.attributes.add(GROUP, "run_id", run_id)
        main.attributes.add(GROUP, "settings", json.dumps(core.snapshot_config(plan), allow_nan=False))
        main.attributes.add(GROUP, "endpoints", json.dumps(plan["endpoints"], allow_nan=False))
        main.attributes.add(GROUP, "created", stamp)
        design.attributes.add(GROUP, "last_settings", json.dumps(core.snapshot_config(plan), allow_nan=False))
        design.attributes.add(GROUP, "document_id", str(plan["config"].get("document_id", "")))
        stage = "Capture and verify component placements"
        capture_placements(design, pending_capture, pose_checks)
        if progress: progress("Verified placements", done+2, total)
        if old:
            stage = "Replace previous route"
            if not old.deleteMe(): raise RuntimeError("Fusion could not replace the old route.")
        stage = "Refresh following routes"
        refresh_dependencies(app, design, follow=not options.get("keep_following_paths", True),
                             warnings=geometry["warnings"], root_run_id=run_id)
        if progress: progress("Route built", total, total)
        succeeded = True
    except Exception as exc:
        raise RuntimeError(stage+": "+str(exc)) from exc
    # The calling Fusion command owns rollback through executeFailed. Do not
    # delete the partial result and then ask Fusion to undo those deletions.
    finally:
        if previous_active and previous_active.isValid and (not succeeded or not options.get("protect_components", True)):
            try: previous_active.activate()
            except Exception: pass
    return dict(name=main.name, token=occurrence.entityToken, config=core.snapshot_config(plan),
                run_id=run_id, endpoint_count=len(plan["endpoints"]),
                replaced=bool(replace_token), warnings=geometry["warnings"],
                build_context=route_build_context(design))


def transformed_state(data, transform):
    state = core.state_from_dict(data)
    p = point(state.position); p.transformBy(transform)
    d = vector(state.d); d.transformBy(transform)
    n = vector(state.boundary_normal); n.transformBy(transform)
    a, e = core.angles((d.x, d.y, d.z), state.azimuth)
    return replace(state, position=(p.x/MM, p.y/MM, p.z/MM), azimuth=a, elevation=e,
                   boundary_normal=(n.x, n.y, n.z))


def _attribute(component, name, default=""):
    attr = component.attributes.itemByName(GROUP, name)
    return attr.value if attr else default


def document_id(design):
    return _attribute(design, "document_id")


def _route_records(design):
    routes, warnings = [], []
    for occurrence in design.rootComponent.allOccurrences:
        main = occurrence.component
        attr = main.attributes.itemByName(GROUP, "endpoints")
        if not attr: continue
        try:
            config = json.loads(_attribute(main, "settings", "{}"))
            routes.append(dict(occurrence=occurrence, records=json.loads(attr.value), config=config,
                               run_id=_attribute(main, "run_id"), revision=int(_attribute(main, "revision", "1"))))
        except (ValueError, TypeError): warnings.append("Could not read route records: "+occurrence.name)
    return routes, warnings


def _route_inputs(route, items, doc):
    """Match saved starts in world coordinates; retain identity when possible."""
    rows = route["config"].get("rows", [])
    row_order = {row["id"]:i for i,row in enumerate(rows)}
    inputs = []
    for index, row in enumerate(rows):
        if row.get("start_mode") != "snapshot": continue
        try:
            local, _ = core.decode_endpoint(row.get("endpoint", ""))
        except core.LayoutError:
            inputs.append(dict(row=row, tracked=True, candidates=[], selected=None, damaged=True))
            continue
        before = transformed_state(asdict(local), route["occurrence"].transform2)
        candidates = []
        for item in items:
            same_instance = item["run_token"] == route["occurrence"].entityToken
            if same_instance:
                # Only earlier lines can provide an internal branch start.
                if row_order.get(item["row_id"], index) >= index: continue
            else:
                # Never reconnect a route to a descendant of itself.
                if any(str(e.get("id", "")).startswith(route["run_id"]+":") for e in item["state"].get("trace", [])):
                    continue
                if not item["editable"]: continue
            if core.connection_matches(before, core.state_from_dict(item["state"])):
                candidates.append(item)
        link = before.link
        preferred = [item for item in candidates if link.get("document_id") == doc and
                     item["run_id"] == link.get("run_id") and item["endpoint_id"] == link.get("endpoint_id")]
        selected = preferred[0] if len(preferred) == 1 else candidates[0] if len(candidates) == 1 else None
        inputs.append(dict(row=row, before=before, tracked=bool(link and link.get("document_id") == doc),
                           candidates=candidates, selected=selected, damaged=False))
    return inputs


def _saved_data(design):
    routes, warnings = _route_records(design)
    items, runs, providers = [], [], {}
    doc = document_id(design)
    for route in routes:
        occurrence, main = route["occurrence"], route["occurrence"].component
        run = dict(token=occurrence.entityToken, name=main.name, run=occurrence.fullPathName,
                   run_id=route["run_id"], revision=route["revision"],
                   editable=occurrence.assemblyContext is None, endpoint_count=len(route["records"]),
                   stale=False, needs_refresh=False, upstream_pending=False, has_connections=False, reasons=[],
                   display_repair_needed=_attribute(main, "stale_display", "false") == "true")
        runs.append(run)
        rows = {row["id"]:row for row in route["config"].get("rows", [])}
        try: command_index = core.command_index(dict(route["config"], route_id=route["run_id"]))
        except core.LayoutError: command_index = {}
        for record in route["records"]:
            state = transformed_state(record["state"], occurrence.transform2)
            state.link = core.endpoint_link(state, doc, route["run_id"], route["revision"], record["id"])
            item = dict(name=record["name"], run=occurrence.fullPathName,
                        id=occurrence.entityToken+"|"+record["id"], kind=record["kind"], run_token=occurrence.entityToken,
                        run_id=route["run_id"], endpoint_id=record["id"], state=asdict(state),
                        trace_start=record.get("trace_start", 0),
                        start_state=asdict(transformed_state(record["start_state"], occurrence.transform2)) if record.get("start_state") else None,
                        endpoint=core.encode_endpoint(state, occurrence.fullPathName+" / "+record["name"]), stats=state.stats())
            row_id = record["id"].split(":", 1)[0]
            row = rows.get(row_id, {})
            item.update(row_id=row_id, row_name=row.get("name", row_id), commands=row.get("commands", ""),
                        editable=run["editable"], route_name=main.name)
            item.update(core.describe_endpoint(record, command_index))
            items.append(item)
            if occurrence.assemblyContext is None:
                providers.setdefault((route["run_id"], record["id"]), []).append(item)
    by_token = {run["token"]:run for run in runs}
    dependencies = {}
    for route, run in zip(routes, runs):
        parents = set()
        route["inputs"] = _route_inputs(route, items, doc)
        run["has_connections"] = bool(route["inputs"])
        for connection in route["inputs"]:
            label = connection["row"].get("name", "Path")+": "
            candidates, target = connection["candidates"], connection["selected"]
            if not candidates:
                if connection["tracked"]:
                    run["stale"] = True
                    run["reasons"].append(label+("saved start is damaged." if connection["damaged"] else
                                                 "no existing endpoint matches its start position and direction."))
                continue
            if target is None:
                run["needs_refresh"] = True
                run["reasons"].append(label+"several endpoints match; choose a source with Refresh beam.")
                continue
            if target["run_token"] != run["token"]: parents.add(target["run_token"])
            before = connection["before"]
            after = core.state_from_dict(target["state"])
            identity = (before.link.get("document_id"),before.link.get("run_id"),before.link.get("endpoint_id"))
            current = (doc,target["run_id"],target["endpoint_id"])
            if identity != current or not core.equivalent_state(before, after):
                run["needs_refresh"] = True
                run["reasons"].append(label+"connection matches; refresh its beam state and reference totals.")
        dependencies[run["token"]] = parents
    for _ in routes:
        changed = False
        for run in runs:
            if not run["upstream_pending"] and any(by_token[parent]["stale"] or by_token[parent]["needs_refresh"]
                                                  for parent in dependencies[run["token"]]):
                run["upstream_pending"] = run["needs_refresh"] = True
                run["reasons"].append("An upstream route needs attention; refresh it first.")
                changed = True
        if not changed: break
    for run in runs:
        run["status"] = "disconnected" if run["stale"] else "upstream_pending" if run["upstream_pending"] else "update_available" if run["needs_refresh"] else "current"
    for item in items:
        run = by_token[item["run_token"]]
        item.update(stale=run["stale"], needs_refresh=run["needs_refresh"], status=run["status"])
    return dict(items=items, runs=runs, warnings=warnings), routes, providers


def saved_endpoints(design):
    return _saved_data(design)[0]


def document_schematic(design):
    """Read saved command geometry in world coordinates, without rebuilding CAD.

    Computed on demand when opening the calculator, not on every draft edit.
    Native occurrences and manually moved internal CAD parts are never cached.
    """
    routes, warnings = _route_records(design)
    lines, optics = [], []
    for route in routes:
        occurrence = route["occurrence"]
        try:
            config = dict(route["config"], route_id=route["run_id"])
            public = core.public_plan(core.plan_layout(config))
            transform = occurrence.transform2
            for line in public["lines"]:
                for key in ("start", "end"):
                    p = point(line[key]); p.transformBy(transform)
                    line[key] = [p.x/MM, p.y/MM, p.z/MM]
                line["run_token"] = occurrence.entityToken
                lines.append(line)
            for optic in public["optics"]:
                optic = copy.deepcopy(optic)
                p = point(optic["position"]); p.transformBy(transform)
                optic["position"] = [p.x/MM, p.y/MM, p.z/MM]
                for key in ("normal", "input_direction", "output_direction"):
                    v = vector(optic[key]); v.transformBy(transform)
                    optic[key] = [v.x, v.y, v.z]
                optic["frame"] = [[v.x,v.y,v.z] for v in
                                  [transformed_vector(axis, transform) for axis in optic["frame"]]]
                optic["run_token"] = occurrence.entityToken
                optic["label"] = occurrence.component.name+" / "+optic["label"]
                optics.append(optic)
        except (core.LayoutError, RuntimeError, ValueError) as exc:
            warnings.append("Schematic unavailable for "+occurrence.component.name+": "+str(exc))
    return dict(lines=lines, optics=optics, warnings=warnings)


def transformed_vector(axis, transform):
    v = vector(axis); v.transformBy(transform)
    return v


def _refresh_context(design, token):
    occurrence = find_run(design, token, editable=True)
    if len(list(design.rootComponent.allOccurrencesByComponent(occurrence.component))) != 1:
        raise core.LayoutError("This route component has multiple instances. Make the route independent before refreshing its beam.")
    data, routes, _ = _saved_data(design)
    route = next(r for r in routes if r["occurrence"].entityToken == occurrence.entityToken)
    return occurrence, route, data


def _usable_source(item, route):
    return item["run_token"] == route["occurrence"].entityToken or item.get("status", "current") == "current"


def _default_source(connection, route):
    target = connection["selected"]
    usable = [e for e in connection["candidates"] if _usable_source(e, route)]
    if target and target in usable: return target
    return usable[0] if len(usable) == 1 else None


def refresh_candidates(design, token):
    occurrence, route, _ = _refresh_context(design, token)
    rows = []
    for connection in route["inputs"]:
        # Independent snapshots from outside this document can remain snapshots.
        if not connection["tracked"] and not connection["candidates"]: continue
        target = _default_source(connection, route)
        rows.append(dict(id=connection["row"]["id"], name=connection["row"].get("name", "Path"),
                         selected=target["id"] if target else "", candidates=[
            dict(id=e["id"], name=e["route_name"]+" / "+e["name"], stats=e["stats"],
                 commands=e["commands"], usable=_usable_source(e,route), status=e["status"])
            for e in connection["candidates"]]))
    return dict(token=occurrence.entityToken, name=occurrence.component.name, rows=rows,
                position_tolerance_mm=core.CONNECTION_POSITION_MM, angle_tolerance_deg=core.CONNECTION_ANGLE_DEG)


def prepare_route_refresh(design, token, choices=None):
    """Replan from suitable live endpoints before entering the native transaction."""
    validate_route_build(design)
    occurrence, route, _ = _refresh_context(design, token)
    choices = choices or {}
    config = copy.deepcopy(route["config"])
    inverse = occurrence.transform2.copy()
    if not inverse.invert(): raise core.LayoutError("Cannot invert this route's placement.")
    inputs = {c["row"]["id"]:c for c in route["inputs"]}
    checks, refreshed = [], 0
    for index, row in enumerate(config.get("rows", [])):
        connection = inputs.get(row["id"])
        if not connection: continue
        if not connection["tracked"] and not connection["candidates"]: continue
        if row["id"] in choices:
            target = next((e for e in connection["candidates"] if e["id"] == choices[row["id"]]), None)
        else:
            target = _default_source(connection, route)
        if target is None:
            raise core.LayoutError(row.get("name", "Path")+": choose a matching source endpoint. Rescan if its position changed.")
        if not _usable_source(target, route):
            raise core.LayoutError("Refresh the source route first: "+target["route_name"])
        if target["run_token"] == occurrence.entityToken:
            # Re-evaluate earlier lines so internal reflected branches receive
            # the new beam, rather than reusing the old internal snapshot.
            prefix = dict(config, rows=config["rows"][:index])
            prior = core.plan_layout(prefix)
            endpoint = next((e for e in prior["endpoints"] if e["id"] == target["endpoint_id"]), None)
            if not endpoint: raise core.LayoutError("An internal branch must refer to an earlier path line.")
            fresh = transformed_state(endpoint["state"], occurrence.transform2)
            fresh.link = core.endpoint_link(fresh, document_id(design), route["run_id"], route["revision"]+1, endpoint["id"])
        else:
            fresh = core.state_from_dict(target["state"])
            checks.append((target["id"], copy.deepcopy(target["state"])))
        before = connection["before"]
        if not core.connection_matches(before, fresh):
            raise core.LayoutError("The refreshed source no longer meets "+row.get("name", "this path")+".")
        local = transformed_state(asdict(fresh), inverse)
        old_local, _ = core.decode_endpoint(row["endpoint"])
        # Match within the documented tolerance, then keep the existing CAD ray
        # exactly: small endpoint roundoff must not move any nominal optic.
        local = replace(local, position=old_local.position, azimuth=old_local.azimuth, elevation=old_local.elevation)
        row["endpoint"] = core.encode_endpoint(local, target["route_name"]+" / "+target["name"])
        row["endpoint_name"] = target["route_name"]+" / "+target["name"]
        refreshed += 1
    if not refreshed: raise core.LayoutError("This route has no saved source connection to refresh.")
    old_plan, new_plan = core.plan_layout(route["config"]), core.plan_layout(config)
    if len(old_plan["optics"]) != len(new_plan["optics"]):
        raise core.LayoutError("Refreshing would change the optic count. Edit this route manually.")
    for old, new in zip(old_plan["optics"], new_plan["optics"]):
        if (old["id"] != new["id"] or core.norm(core.sub(old["position"],new["position"])) > 1e-6 or
                any(core.norm(core.sub(a,b)) > 1e-8 for a,b in zip(old["frame"],new["frame"]))):
            raise core.LayoutError("Refreshing would change optic positions. Edit this route manually.")
    beams = [child for child in occurrence.component.occurrences
             if _attribute(child.component,"role") == "beam" or child.component.name == "Beam"]
    if len(beams) > 1 or (old_plan["segments"] and not beams):
        raise core.LayoutError("Cannot identify a single existing Beam group. Restore its Beam name or edit the route manually.")
    return dict(token=occurrence.entityToken, revision=route["revision"], placement=occurrence.transform2.copy(),
                old_settings=_attribute(occurrence.component,"settings"), plan=new_plan, source_checks=checks,
                old_beams=beams, geometry=temporary_geometry(new_plan, design, beam_only=True))


def refresh_route(app, design, prepared):
    """Replace only the beam group and records, leaving every optic untouched."""
    validate_route_build(design)
    occurrence = find_run(design, prepared["token"], editable=True)
    main = occurrence.component
    if (int(_attribute(main,"revision","1")) != prepared["revision"] or
            _attribute(main,"settings") != prepared["old_settings"]):
        raise core.LayoutError("The route changed while preparing its refresh. Rescan and try again.")
    check_occurrence_pose(occurrence, prepared["placement"], "Route to refresh")
    current = {e["id"]:e for e in saved_endpoints(design)["items"]}
    for key, state in prepared["source_checks"]:
        if key not in current or current[key]["state"] != state or current[key]["status"] != "current":
            raise core.LayoutError("A source endpoint changed while preparing the refresh. Rescan and try again.")
    geometry, plan = prepared["geometry"], prepared["plan"]
    previous_active = getattr(design,"activeOccurrence",None)
    stage = "Create refreshed beam"
    try:
        if previous_active and not design.activateRootComponent():
            raise RuntimeError("Could not activate the design root.")
        styled = []
        if geometry["beam"]:
            child = main.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            if not child: raise RuntimeError("Could not create the refreshed Beam group.")
            proxy = root_proxy(child, occurrence, "Refreshed beam")
            target = occurrence.transform2.copy()
            pending = set_occurrence_pose(proxy,target,"Refreshed beam")
            child.component.name = "Beam"
            child.component.attributes.add(GROUP,"role","beam")
            child.component.opacity = plan["config"].get("options",{}).get("beam_opacity",0.3)
            styled = add_bodies(child.component,design,geometry["beam"])
            capture_placements(design,pending,[(proxy,target,"Refreshed beam")])
        stage = "Replace previous beam"
        for old in prepared["old_beams"]:
            if not old.deleteMe(): raise RuntimeError("Fusion could not remove the previous Beam group.")
        stage = "Save refreshed beam states"
        main.attributes.add(GROUP,"settings",json.dumps(core.snapshot_config(plan),allow_nan=False))
        main.attributes.add(GROUP,"endpoints",json.dumps(plan["endpoints"],allow_nan=False))
        main.attributes.add(GROUP,"revision",str(prepared["revision"]+1))
        stage = "Update connection status"
        refresh_dependencies(app,design,warnings=geometry["warnings"])
    except Exception as exc:
        raise RuntimeError(stage+": "+str(exc)) from exc
    finally:
        if previous_active and previous_active.isValid:
            try: previous_active.activate()
            except Exception: pass
    if app:
        try:
            colors = {kind: appearance(app,design,kind) for kind in {k for _, k in styled}}
            for body,kind in styled:
                if colors[kind]: body.appearance = colors[kind]
        except Exception:
            geometry["warnings"].append("Beam refreshed; appearance assignment was unavailable.")
    return dict(operation="refresh_route", token=occurrence.entityToken, name=main.name,
                config=core.snapshot_config(plan), warnings=geometry["warnings"])


def document_export(design):
    """Read every saved instance, including its current world placement."""
    saved, routes, _ = _saved_data(design)
    if saved["warnings"]:
        raise core.LayoutError("Document export could not read every route: "+"; ".join(saved["warnings"]))
    if not routes: raise core.LayoutError("Build a route before exporting all saved document paths.")
    records = []
    for route, run in zip(routes, saved["runs"]):
        records.append(dict(name=run["name"], instance=run["run"], run_id=run["run_id"], revision=run["revision"],
                            stale=run["stale"], needs_refresh=run["needs_refresh"], status=run["status"],
                            reasons=run["reasons"], config=route["config"],
                            placement=matrix_parts(route["occurrence"].transform2),
                            endpoints=[e for e in saved["items"] if e["run_token"] == run["token"]]))
    return records


def matrix_parts(transform):
    p = point((0,0,0)); p.transformBy(transform)
    columns = []
    for a in ((1,0,0),(0,1,0),(0,0,1)):
        v = vector(a); v.transformBy(transform); columns.append((v.x,v.y,v.z))
    return (p.x/MM,p.y/MM,p.z/MM), tuple(columns)


def _same_beam_shape(a, b):
    fields = ("y", "slope") if a.model == "geometric" else ("q_real", "q_imag", "m2", "wavelength_nm")
    return a.model == b.model and all(math.isclose(getattr(a,k),getattr(b,k),rel_tol=1e-8,abs_tol=1e-8) for k in fields)


def _follow_route(route, providers, doc, unavailable):
    occurrence = route["occurrence"]
    if occurrence.assemblyContext is not None: return False, "Nested route: review its placement manually."
    config = copy.deepcopy(route["config"])
    targets, motions = [], []
    for index, row in enumerate(config.get("rows", [])):
        if row.get("start_mode") == "previous": continue
        if row.get("start_mode") != "snapshot": return False, "An independent source prevents moving this whole route."
        before_local, _ = core.decode_endpoint(row.get("endpoint", ""))
        link = before_local.link
        matches = providers.get((link.get("run_id"), link.get("endpoint_id")), [])
        if link.get("document_id") != doc or len(matches) != 1 or link.get("run_id") in unavailable:
            return False, "Source endpoint is unavailable or still outdated."
        before = transformed_state(asdict(before_local), occurrence.transform2)
        after = core.state_from_dict(matches[0]["state"])
        if not _same_beam_shape(before, after):
            return False, "Input beam diameter/divergence changed; moving existing geometry cannot update its envelope."
        motions.append(core.continuation_transform(before, after)); targets.append((index, after))
    if not motions: return False, "No tracked start endpoint."
    origin, rotation = motions[0]
    for other_origin, other_rotation in motions[1:]:
        if core.norm(core.sub(origin,other_origin)) > 1e-5 or any(core.norm(core.sub(a,b)) > 1e-8 for a,b in zip(rotation,other_rotation)):
            return False, "Multiple starts require incompatible movements; keep this route as a reference."
    old_origin, old_rotation = matrix_parts(occurrence.transform2)
    new_placement = matrix(core.add(origin,core.world(rotation,old_origin)),
                           tuple(core.world(rotation,c) for c in old_rotation))
    inverse = new_placement.copy()
    if not inverse.invert(): raise core.LayoutError("Cannot invert continuation placement.")
    for index, target in targets:
        local = transformed_state(asdict(target), inverse)
        config["rows"][index]["endpoint"] = core.encode_endpoint(local, config["rows"][index].get("endpoint_name", "Start"))
    plan = core.plan_layout(config)
    # Everything above is read-only. A failure from here aborts the caller's
    # command transaction, including the new upstream route.
    if getattr(occurrence, "isGroundToParent", False): occurrence.isGroundToParent = False
    occurrence.transform2 = new_placement
    check_occurrence_pose(occurrence, new_placement, occurrence.name)
    main = occurrence.component
    main.attributes.add(GROUP,"settings",json.dumps(core.snapshot_config(plan),allow_nan=False))
    main.attributes.add(GROUP,"endpoints",json.dumps(plan["endpoints"],allow_nan=False))
    main.attributes.add(GROUP,"revision",str(route["revision"]+1))
    return True, ""


def _restore_route_colors(app, design, routes, statuses, warnings):
    """Migrate legacy clear beams once; connection status never recolors geometry.

    Called only inside a native model command. Ordinary refreshes do no material
    lookups or body writes, and source CAD components are never touched.
    """
    if not app: return
    colors = {}
    for route, status in zip(routes, statuses):
        main = route["occurrence"].component
        if _attribute(main, "stale_display", "false") != "true":
            status["display_repair_needed"] = False
            continue
        try:
            for child in main.occurrences:
                component = child.component
                if component.name != "Beam" and _attribute(component, "role") != "beam": continue
                for body in component.bRepBodies:
                    kind = _attribute(body, "beam_style", "beam")
                    if kind not in COLORS: kind = "beam"
                    if kind not in colors: colors[kind] = appearance(app, design, kind)
                    if not colors[kind]: raise RuntimeError("Beam material unavailable")
                    body.appearance = colors[kind]
                component.opacity = route["config"].get("options", {}).get("beam_opacity", 0.3)
            main.attributes.add(GROUP, "stale_display", "false")
            status["display_repair_needed"] = False
        except Exception:
            warnings.append(main.name+": beam colors could not be restored; retry Refresh on Saved paths.")


def refresh_dependencies(app, design, follow=False, warnings=None, root_run_id=None):
    warnings = warnings if warnings is not None else []
    data, routes, providers = _saved_data(design)
    eligible = {route["run_id"] for route in routes} if root_run_id is None else {root_run_id}
    if follow and root_run_id is not None:
        for _ in routes:
            before = len(eligible)
            for route in routes:
                for row in route["config"].get("rows", []):
                    if row.get("start_mode") != "snapshot": continue
                    try: state, _ = core.decode_endpoint(row.get("endpoint", ""))
                    except core.LayoutError: continue
                    if state.link.get("document_id") == document_id(design) and state.link.get("run_id") in eligible:
                        eligible.add(route["run_id"])
            if len(eligible) == before: break
        eligible.discard(root_run_id)
    moved = False
    if follow:
        for _ in range(len(routes)+1):
            changed = False
            unavailable = {r["run_id"] for r in data["runs"] if r["stale"] or r["needs_refresh"]}
            for route, status in zip(routes, data["runs"]):
                if not (status["stale"] or status["needs_refresh"]) or route["run_id"] not in eligible: continue
                ok, reason = _follow_route(route, providers, document_id(design), unavailable)
                if ok: changed = moved = True; break
            if not changed: break
            data, routes, providers = _saved_data(design)
        for status in data["runs"]:
            if (status["stale"] or status["needs_refresh"]) and status["run_id"] in eligible:
                warnings.append(status["name"]+": left in place for manual review; its inputs could not be followed rigidly.")
    if moved and design.designType == adsk.fusion.DesignTypes.ParametricDesignType and design.snapshots.hasPendingSnapshot:
        design.snapshots.add()
    _restore_route_colors(app, design, routes, data["runs"], warnings)
    data["warnings"] = list(dict.fromkeys(data["warnings"]+warnings))
    return data


def public_plan(design, plan, edit_token=None):
    result = copy.deepcopy(core.public_plan(plan))
    result["build_context"] = route_build_context(design)
    occurrence = find_run(design, edit_token, editable=True) if edit_token else None
    transform = occurrence.transform2 if occurrence else adsk.core.Matrix3D.create()
    run_id = _attribute(occurrence.component, "run_id") if occurrence else plan["config"].get("route_id", "draft")
    revision = int(_attribute(occurrence.component, "revision", "1"))+1 if occurrence else 1
    def transform_stats(stats):
        p = point(stats["position"]); p.transformBy(transform)
        d = vector(stats["direction"]); d.transformBy(transform)
        stats["position"], stats["direction"] = [p.x/MM, p.y/MM, p.z/MM], [d.x, d.y, d.z]
        stats["azimuth"], stats["elevation"] = core.angles(stats["direction"], stats["azimuth"])
        stats["azimuth_defined"] = abs(stats["elevation"]) < 89.999999
    def transform_endpoint(endpoint):
        state = transformed_state(endpoint["state"], transform)
        state.link = core.endpoint_link(state, plan["config"].get("document_id", document_id(design)), run_id, revision, endpoint["id"])
        endpoint.update(state=asdict(state), stats=state.stats(), endpoint=core.encode_endpoint(state, endpoint["name"]))
        if endpoint.get("start_state"):
            endpoint["start_state"] = asdict(transformed_state(endpoint["start_state"],transform))
    # deepcopy preserves shared endpoint objects; transform each just once.
    for endpoint in result["endpoints"]: transform_endpoint(endpoint)
    for line in result["lines"]:
        for key in ("start", "end"):
            p = point(line[key]); p.transformBy(transform)
            line[key] = [p.x/MM, p.y/MM, p.z/MM]
    result["route_id"] = run_id
    for row in result["rows"]:
        for step in row["steps"]:
            transform_stats(step)
            for secondary in step.get("secondary",[]): transform_stats(secondary)
    for optic in result["optics"]:
        p = point(optic["position"]); p.transformBy(transform)
        optic["position"] = [p.x/MM, p.y/MM, p.z/MM]
        for key in ("normal", "input_direction", "output_direction"):
            v = vector(optic[key]); v.transformBy(transform)
            optic[key] = [v.x, v.y, v.z]
        if optic["oap"]:
            v = vector(optic["oap"]["parent_axis"]); v.transformBy(transform)
            p = point(optic["oap"]["focus"]); p.transformBy(transform)
            optic["oap"]["parent_axis"] = [v.x, v.y, v.z]
            optic["oap"]["focus"] = [p.x/MM, p.y/MM, p.z/MM]
        for key in ("frame",):
            out = []
            for value in optic[key]:
                v = vector(value); v.transformBy(transform); out.append([v.x, v.y, v.z])
            optic[key] = out
    return result


def endpoint_in_run_frame(design, endpoint, edit_token=None):
    state, name = core.decode_endpoint(endpoint)
    if edit_token:
        inverse = find_run(design, edit_token, editable=True).transform2.copy()
        if not inverse.invert(): raise core.LayoutError("Cannot invert the route placement.")
        state = transformed_state(asdict(state), inverse)
    return dict(name=name, endpoint=core.encode_endpoint(state, name), stats=state.stats())


def component_body_frames(component):
    """Native body coordinates mapped into the selected component definition.

    Traverse immediate native occurrences and compose each parent once.
    allOccurrences contains context-dependent proxies; treating their matrices
    as local child poses mixes frames for nested/rotated CAD assemblies.
    This definition frame is the one addExistingComponent instances in Build.
    """
    stack = [(component, adsk.core.Matrix3D.create(), 0)]
    visited = 0
    while stack:
        part, local, depth = stack.pop()
        visited += 1
        if depth > 100 or visited > 10000:
            raise core.LayoutError("Component hierarchy is too large or cyclic. Use a simplified optical assembly.")
        for body in part.bRepBodies:
            if body.isVisible:
                yield getattr(body, "nativeObject", None) or body, local
        # Component.occurrences is relative to this definition, unlike a rooted
        # occurrence's childOccurrences. Strip any proxy before reading its pose.
        for occurrence in reversed(list(getattr(part, "occurrences", []))):
            native = getattr(occurrence, "nativeObject", None) or occurrence
            if not getattr(native, "isLightBulbOn", True): continue
            stack.append((native.component, compose_placements(local, native.transform2), depth+1))


def transform_preview_body(manager, body, transform):
    if manager.transform(body, transform) is False:
        raise core.LayoutError("Fusion could not apply the CAD preview transform. Preview cancelled; no source geometry was changed.")


def iter_custom_preview_bodies(manager, component, placement):
    """Copy native geometry and apply one composed component-to-target matrix."""
    count, faces = 0, 0
    for body, local in component_body_frames(component):
        count += 1
        faces += getattr(getattr(body, "faces", None), "count", 0)
        if count > 1000 or faces > 100000:
            raise core.LayoutError("This component is too detailed for a quick CAD preview. "
                                   "Use a simplified source with at most 1000 bodies and 100000 faces.")
        copied = manager.copy(body)
        if not copied: raise RuntimeError("Fusion could not copy a component body for preview.")
        transform_preview_body(manager, copied, compose_placements(placement, local))
        yield copied


def custom_preview_bodies(manager, component, placement):
    return list(iter_custom_preview_bodies(manager, component, placement))


def preview(design, plan, edit_token=None, quality="solid", optic_id=None, progress=None):
    if quality in ("draft", "selected"):
        try:
            from .workflow import wire_geometry
        except ImportError:
            from workflow import wire_geometry
        group = design.rootComponent.customGraphicsGroups.add()
        try:
            if edit_token: group.transform = find_run(design, edit_token, editable=True).transform2
            styles = {"beam": ((210, 40, 62), 2.5), "envelope": ((178, 72, 85), 1), "optic": ((27, 99, 142), 2)}
            for kind, points in wire_geometry(plan).items():
                if not points: continue
                coordinates = adsk.fusion.CustomGraphicsCoordinates.create([x*MM for p in points for x in p])
                graphic = group.addLines(coordinates, [], False)
                if not graphic: raise RuntimeError("Could not create draft preview lines.")
                base, _, name = kind.partition("-")
                color, weight = styles[base]
                if name: color = COLORS["beam-"+name]
                graphic.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(*color, 255))
                graphic.weight = weight
            if quality == "selected":
                optic = next((o for o in plan["optics"] if o["id"] == optic_id), None)
                if not optic or not optic["settings"].get("custom"):
                    raise core.LayoutError("Select an optic with an assigned component to inspect its CAD.")
                component = resolve_component(design, optic)
                if progress: progress("Inspecting "+optic["label"], 0, 1)
                manager = adsk.fusion.TemporaryBRepManager.get()
                count = 0
                for body in iter_custom_preview_bodies(manager, component, custom_placement(optic)):
                    graphic = group.addBRepBody(body)
                    graphic.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(175,187,200,255))
                    graphic.setOpacity(0.8, True)
                    count += 1
                    if progress: progress("Inspecting "+optic["label"]+" · "+str(count)+" bodies", 0, 1)
                if not count: raise core.LayoutError("This component has no visible solid/surface bodies to preview. Mesh-only models are not supported.")
                # RGB axes show the calibrated source frame at the optical datum.
                _, axes = core.custom_transform(optic)
                datum = core.add(optic["position"], core.world(optic["frame"], optic["settings"].get("shift", (0,0,0))))
                for axis, color in zip(axes, ((220,65,65),(50,165,85),(55,115,225))):
                    end = core.add(datum, core.mul(axis, max(10, min(40,optic["diameter_mm"]))))
                    coords = adsk.fusion.CustomGraphicsCoordinates.create([x*MM for p in (datum,end) for x in p])
                    graphic = group.addLines(coords, [], False)
                    graphic.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(*color,255))
                    graphic.weight = 3
                if progress: progress("Component preview ready", 1, 1)
            return group, list(plan["warnings"])
        except Exception:
            group.deleteMe()
            raise
    geometry = temporary_geometry(plan, design, progress=progress)
    placement = find_run(design, edit_token, editable=True).transform2 if edit_token else None
    group = design.rootComponent.customGraphicsGroups.add()
    try:
        manager = adsk.fusion.TemporaryBRepManager.get()
        for _, body, kind in geometry["beam"]+geometry["optics"]:
            if placement: transform_preview_body(manager, body, placement)
            graphic = group.addBRepBody(body)
            graphic.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(*COLORS[kind], 255))
            graphic.setOpacity(plan["config"].get("options", {}).get("beam_opacity", 0.3) if kind == "beam" or kind.startswith("beam-") else 0.7, True)
        manager = adsk.fusion.TemporaryBRepManager.get()
        for optic, component in geometry["custom"]:
            for body in iter_custom_preview_bodies(manager, component, custom_placement(optic)):
                if progress: progress("Previewing "+optic["label"], 0, 1)
                if placement: transform_preview_body(manager, body, placement)
                graphic = group.addBRepBody(body)
                graphic.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(175, 187, 200, 255))
                graphic.setOpacity(0.75, True)
        return group, geometry["warnings"]
    except Exception:
        group.deleteMe()
        raise
