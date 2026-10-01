"""Offline CSV round-trip and orthographic SVG documentation; no Fusion imports."""
import copy
import csv
import io
import json
import math
import re
import uuid
import zipfile
from xml.etree import ElementTree as ET
try:
    from . import core, schematic_svg
except ImportError:
    import core, schematic_svg

CSV_FIELDS = ["record", "id", "name", "commands", "start_mode", "endpoint", "token",
              "geometric_mm", "optical_path_mm", "loss_pct", "gdd_fs2", "x_mm", "y_mm", "z_mm",
              "azimuth_deg", "elevation_deg", "diameter_mm", "half_angle_mrad", "diameter_h_mm", "diameter_v_mm", "wavelength_nm", "spectral_weight"]+list(core.BUDGET_FIELDS)+["data_json"]


def csv_text(value):
    """Keep commands such as +l50 as spreadsheet text, not formulas."""
    value = str(value)
    return "'"+value if value[:1] in ("=", "+", "-", "@", "\t", "\r", "\n", "'") else value


def csv_untext(value):
    return value[1:] if value.startswith("'") else value


def export_csv(plan):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(CSV_FIELDS)), lineterminator="\n")
    writer.writeheader()
    config = core.snapshot_config(plan)
    header = {k: v for k, v in config.items() if k not in ("rows", "optic_overrides")}
    writer.writerow(dict(record="LaserOpticsRouter:1.2", name=csv_text(config.get("run_name", "")),
                         data_json=json.dumps(header, ensure_ascii=False)))
    for row in config["rows"]:
        writer.writerow(dict(record="path", **{k:csv_text(row.get(k, "")) for k in ("id", "name", "commands", "start_mode", "endpoint")},
                             data_json=json.dumps(row, ensure_ascii=False)))
    for optic in plan["optics"]:
        writer.writerow(dict(record="optic", id=csv_text(optic["id"]), token=csv_text(optic["token"]), name=csv_text(optic["label"]),
                             **optic["budget"], data_json=json.dumps(config["optic_overrides"][optic["id"]], ensure_ascii=False)))
    for endpoint in plan["endpoints"]:
        s = endpoint["stats"]
        writer.writerow(dict(record="summary", id=csv_text(endpoint["id"]), name=csv_text(endpoint["name"]),
                             geometric_mm=s["path_mm"], optical_path_mm=s["optical_path_mm"],
                             loss_pct=s["loss_pct"], gdd_fs2=s["gdd_fs2"],
                             x_mm=s["position"][0],y_mm=s["position"][1],z_mm=s["position"][2],
                             azimuth_deg=s["azimuth"],elevation_deg=s["elevation"],
                             diameter_mm=s["diameter_mm"],half_angle_mrad=s["half_angle_mrad"],
                             diameter_h_mm=s.get("diameter_h_mm",s["diameter_mm"]),diameter_v_mm=s.get("diameter_v_mm",s["diameter_mm"]),
                             wavelength_nm=s["wavelength_nm"],spectral_weight=s.get("spectral_weight",1)))
    return "\ufeff"+stream.getvalue()


def import_csv(text, component_defaults=None, document_id=None):
    if len(text) > 12000000: raise core.LayoutError("CSV file is too large (12 MB limit).")
    csv.field_size_limit(8000000)
    text = text.lstrip("\ufeff")
    if not text.strip(): raise core.LayoutError("CSV file is empty.")
    delimiter = ";" if text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    if "route_key" in (reader.fieldnames or []):
        raise core.LayoutError("This is the combined document overview. Import an individual CSV from the ZIP's routes folder.")
    if not {"record", "data_json"}.issubset(reader.fieldnames or []):
        raise core.LayoutError("Use a LaserOpticsRouter 1.2 CSV export, with its record and data_json columns.")
    config, rows, overrides = None, [], {}
    for lineno, row in enumerate(reader, 2):
        try:
            for key in ("id", "name", "commands", "start_mode", "endpoint", "token"):
                if isinstance(row.get(key), str): row[key] = csv_untext(row[key])
            kind = row.get("record")
            if kind == "LaserOpticsRouter:1.2":
                if config is not None: raise ValueError("Duplicate settings header")
                config = json.loads(row["data_json"])
                config["run_name"] = row.get("name") or config.get("run_name", "Imported route")
            elif kind == "path":
                item = json.loads(row.get("data_json") or "{}")
                for key in ("id", "name", "commands", "start_mode", "endpoint"):
                    if row.get(key) is not None: item[key] = row[key]
                rows.append(item)
            elif kind == "optic":
                item = json.loads(row.get("data_json") or "{}")
                item["token"] = row["token"]
                item.setdefault("budget", {})
                for key in core.BUDGET_FIELDS:
                    if row.get(key, "") != "": item["budget"][key] = core.finite(row[key], key)
                if row["id"] in overrides: raise ValueError("Duplicate optic ID")
                overrides[row["id"]] = item
            elif kind not in ("summary", "", None): raise ValueError("Unknown record type")
        except (ValueError, TypeError, KeyError) as exc:
            raise core.LayoutError(f"CSV line {lineno}: {exc}") from exc
    if config is None: raise core.LayoutError("Missing LaserOpticsRouter settings header.")
    same_document = document_id and config.get("document_id") == document_id
    old_id, new_id = config.get("route_id", ""), uuid.uuid4().hex
    config.update(rows=rows, optic_overrides=overrides, route_id=new_id)
    if document_id: config["document_id"] = document_id
    # A clone gets a new route identity. Rebind histories of its own copied
    # branch starts, while preserving links to separate upstream routes.
    def rebind(state):
        for event in state.trace:
            if old_id and str(event.get("id", "")).startswith(old_id+":"):
                event["id"] = new_id+event["id"][len(old_id):]
        if state.link.get("run_id") == old_id:
            state.link.update(run_id=new_id,document_id=config.get("document_id", ""),revision=1)
        for ray in state.spectral_rays:
            child = core.state_from_dict(ray)
            rebind(child)
            ray.update(trace=child.trace,link=child.link)
    for row in rows:
        if row.get("start_mode") != "snapshot": continue
        state, name = core.decode_endpoint(row.get("endpoint", ""))
        rebind(state)
        row["endpoint"] = core.encode_endpoint(state, name)
    config["component_defaults"] = copy.deepcopy(component_defaults or {})
    if not same_document:
        for s in overrides.values():
            if s.get("custom"):
                s["component_token"] = s["component_ref_token"] = ""
    core.plan_layout(config)
    return config


def export_svg(plan, projection="XY", transform=None):
    return schematic_svg.render(plan, projection, transform)


def export_document_zip(routes, document_name="LaserOpticsRouter"):
    """One download: combined documentation, world projections and route CSVs."""
    if not routes: raise core.LayoutError("No saved routes to export.")
    combined = dict(config=dict(run_name=document_name), segments=[], optics=[])
    table = io.StringIO(newline="")
    fields = ["route_key", "route_name", "instance", "outdated", "connection_status", "needs_beam_refresh", "coordinate_frame", "placement_json"]+list(dict.fromkeys(CSV_FIELDS))
    writer = csv.DictWriter(table, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    manifest = dict(format="LaserOpticsRouter.Document", version=1, release=core.VERSION,
                    document=document_name, units="mm / degrees / fs2 / percent", routes=[])
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, route in enumerate(routes, 1):
            key = f"route_{index:03d}"
            slug = re.sub(r"[^A-Za-z0-9_-]+", "_", route["name"]).strip("_")[:60] or "route"
            filename = "routes/"+key+"_"+slug+".csv"
            plan = core.plan_layout(route["config"])
            route_csv = export_csv(plan)
            archive.writestr(filename, route_csv)
            origin, axes = route["placement"]
            summaries = {e["endpoint_id"]:e for e in route["endpoints"]}
            for row in csv.DictReader(io.StringIO(route_csv.lstrip("\ufeff"))):
                row.update(route_key=key, route_name=csv_text(route["name"]), instance=csv_text(route["instance"]),
                           outdated="yes" if route["stale"] else "no", coordinate_frame="route-local",
                           connection_status=route.get("status","disconnected" if route["stale"] else "current"),
                           needs_beam_refresh="yes" if route.get("needs_refresh") else "no")
                if row["record"] == "LaserOpticsRouter:1.2":
                    row["placement_json"] = json.dumps(route["placement"])
                elif row["record"] == "summary":
                    endpoint = summaries[csv_untext(row["id"])]
                    s = endpoint["stats"]
                    row.update(coordinate_frame="design-root", endpoint=endpoint["endpoint"],
                               x_mm=s["position"][0], y_mm=s["position"][1], z_mm=s["position"][2],
                               azimuth_deg=s["azimuth"], elevation_deg=s["elevation"],
                               diameter_h_mm=s.get("diameter_h_mm", s["diameter_mm"]),
                               diameter_v_mm=s.get("diameter_v_mm", s["diameter_mm"]),
                               data_json=json.dumps(endpoint["state"], ensure_ascii=False))
                writer.writerow(row)
            for segment in plan["segments"]:
                combined["segments"].append(dict(segment, name=route["name"]+" / "+segment["name"],
                    state=core.moved_state(segment["state"], origin, axes)))
            for optic in plan["optics"]:
                combined["optics"].append(schematic_svg.moved_optic(dict(optic, label=route["name"]+" / "+optic["label"]), origin, axes))
            manifest["routes"].append(dict(route, key=key, csv=filename))
        archive.writestr("all_paths.csv", "\ufeff"+table.getvalue())
        archive.writestr("document.json", json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False))
        for projection in ("XY", "XZ", "YZ"):
            archive.writestr("all_paths_"+projection+".svg", export_svg(combined, projection))
        archive.writestr("README.txt", "LaserOpticsRouter document export\n\n"
            "all_paths.csv: all saved routes, commands, optics and endpoint budgets.\n"
            "Path commands use route-local axes; summary coordinates use current design-root axes.\n"
            "placement_json maps route-local coordinates to design-root coordinates (mm and axis columns).\n"
            "document.json: saved settings, placements, endpoint states and dependency links.\n"
            "all_paths_XY/XZ/YZ.svg: combined router schematics at current placements (symbols not to scale).\n"
            "routes/*.csv: individually importable route drafts; use Import CSV in LaserOpticsRouter.\n"
            "Import is one route at a time, in its original local frame. Whole-document restore is not provided.\n"
            "Disconnected routes and routes needing beam refresh are included and flagged; export does not rebuild geometry.\n"
            "Custom CAD models are referenced, not embedded. Keep the Fusion design for CAD geometry.\n"
            "Reference losses, GDD and glass-adjusted lengths are simple approximations.\n")
    return output.getvalue()
