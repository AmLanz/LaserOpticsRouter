"""LaserOpticsRouter: dependency-free layout mathematics (mm, degrees).

The Gaussian option is an isotropic, paraxial M-squared envelope. It is not
an aberration, polarization, diffraction-pattern or material ray tracer.
"""
import base64
import copy
import json
import math
import re
import uuid
import hashlib
from dataclasses import asdict, dataclass, replace, field

VERSION = "1.6.1"
EPS = 1e-10
CONNECTION_POSITION_MM = 0.001
CONNECTION_ANGLE_DEG = 0.001
MAX_CONNECTION_CANDIDATES = 250000
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
FAMILIES = ("lens", "mirror", "oap", "pol", "bs", "bsc", "wp", "rp", "bd", "laha", "laqu", "nd", "tp", "generic")
SPLITTERS = ("bs", "bsc", "wp", "rp", "bd")
PRISMS = ("wp", "rp", "bd")
BEAM_COLORS = {"red": "#d63b4e", "blue": "#2878ce", "green": "#258252",
               "yellow": "#e2b426", "orange": "#ef6b26", "purple": "#8959bd",
               "white": "#ffffff"}


def beam_color(value, inherit=False):
    if value not in BEAM_COLORS and not (inherit and value == "inherit"):
        raise LayoutError("Choose a supported beam color.")
    return value


class LayoutError(ValueError):
    def __init__(self, message, row=None, token=None, start=None, end=None):
        super().__init__(message)
        self.row, self.token, self.start, self.end = row, token, start, end

    def data(self):
        return dict(message=str(self), row=self.row, token=self.token,
                    start=self.start, end=self.end)


def finite(value, label="Value"):
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise LayoutError(label + " must be a number.")
    if not math.isfinite(value):
        raise LayoutError(label + " must be finite.")
    return value


def vec(v):
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise LayoutError("A coordinate must contain three numbers.")
    return tuple(finite(x, "Coordinate") for x in v)


def add(a, b): return tuple(x + y for x, y in zip(a, b))
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def mul(a, s): return tuple(x * s for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a): return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    if n < EPS:
        raise LayoutError("Undefined direction: zero-length vector.")
    return mul(a, 1/n)


def direction(azimuth, elevation):
    a, e = math.radians(azimuth), math.radians(elevation)
    return (math.cos(e)*math.cos(a), math.cos(e)*math.sin(a), math.sin(e))


def angles(d, pole_azimuth=0):
    d = unit(d)
    a = math.degrees(math.atan2(d[1], d[0])) if math.hypot(d[0], d[1]) > EPS else pole_azimuth
    return a % 360, math.degrees(math.asin(max(-1, min(1, d[2]))))


def frame(z, preferred_x=None):
    """Right-handed orthonormal columns; valid at vertical directions too."""
    z = unit(z)
    if preferred_x is None or norm(sub(preferred_x, mul(z, dot(preferred_x, z)))) < EPS:
        seed = min(((1, 0, 0), (0, 1, 0), (0, 0, 1)), key=lambda a: abs(dot(a, z)))
    else:
        seed = preferred_x
    x = unit(sub(seed, mul(z, dot(seed, z))))
    return (x, cross(z, x), z)


def world(columns, local):
    return tuple(sum(columns[j][i]*local[j] for j in range(3)) for i in range(3))


def rotated_columns(columns, rx, ry, rz):
    """Fixed local axes: X, then Y, then Z; matrix Rz @ Ry @ Rx."""
    ax, ay, az = [math.radians(finite(a)) for a in (rx, ry, rz)]
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    rows = ((cz*cy, cz*sy*sx-sz*cx, cz*sy*cx+sz*sx),
            (sz*cy, sz*sy*sx+cz*cx, sz*sy*cx-cz*sx),
            (-sy, cy*sx, cy*cx))
    return tuple(world(columns, tuple(rows[i][j] for i in range(3))) for j in range(3))


@dataclass
class BeamState:
    position: tuple = (0.0, 0.0, 0.0)
    azimuth: float = 0.0
    elevation: float = 0.0
    model: str = "geometric"
    y: float = 2.5
    slope: float = 0.0
    q_real: float = 0.0
    q_imag: float = 1.0
    wavelength_nm: float = 800.0
    m2: float = 1.0
    path_mm: float = 0.0
    boundary_normal: tuple = (0.0, 0.0, 0.0)
    boundary_bend: float = 0.0
    boundary_kind: str = ""
    extra_opl_mm: float = 0.0
    throughput: float = 1.0
    gdd_fs2: float = 0.0
    trace: list = field(default_factory=list)
    link: dict = field(default_factory=dict)
    color: str = "red"

    @property
    def d(self): return direction(self.azimuth, self.elevation)

    @property
    def beta(self): return self.m2*self.wavelength_nm*1e-6/math.pi

    @property
    def radius(self):
        if self.model == "gaussian":
            return math.sqrt(self.beta*(self.q_real**2+self.q_imag**2)/self.q_imag)
        return abs(self.y)

    @property
    def radial_slope(self):
        if self.model == "gaussian":
            return self.radius*self.q_real/(self.q_real**2+self.q_imag**2)
        return math.copysign(1, self.y)*self.slope if self.y else abs(self.slope)

    def propagated(self, length):
        length = finite(length, "Propagation distance")
        result = replace(self, position=add(self.position, mul(self.d, length)),
                         path_mm=self.path_mm+length)
        if length:
            result.boundary_normal, result.boundary_bend, result.boundary_kind = (0, 0, 0), 0, ""
        if self.model == "gaussian":
            result.q_real += length
        else:
            result.y += self.slope*length
            scale = max(abs(self.y), abs(self.slope*length), 1e-300)
            if abs(result.y) < 8*math.ulp(scale):
                result.y = 0.0
        return result

    def focused(self, focal):
        result = replace(self)
        if self.model == "gaussian":
            q = complex(self.q_real, self.q_imag)
            q = 1/(1/q-1/focal)
            result.q_real, result.q_imag = q.real, q.imag
        else:
            result.slope -= self.y/focal
        return result

    def turned(self, horizontal, vertical):
        e = self.elevation + vertical
        if not -90 <= e <= 90:
            raise LayoutError("Resulting elevation must be between -90° and +90°. Split or revise the turn.")
        return replace(self, azimuth=(self.azimuth+horizontal) % 360, elevation=e)

    def stats(self):
        s = self.radial_slope
        status = "near collimated" if abs(s) <= 1e-6 else ("diverging" if s > 0 else "converging")
        if self.model == "geometric" and self.y == 0:
            status = "geometric focus"
        result = dict(position=list(self.position), direction=list(self.d),
                      azimuth=self.azimuth, elevation=self.elevation,
                      azimuth_defined=abs(self.elevation) < 89.999999,
                      diameter_mm=2*self.radius, half_angle_mrad=1000*math.atan(s),
                      status=status, path_mm=self.path_mm, model=self.model,
                      optical_path_mm=self.path_mm+self.extra_opl_mm,
                      loss_pct=100*(1-self.throughput), gdd_fs2=self.gdd_fs2)
        if self.model == "gaussian":
            result.update(waist_diameter_mm=2*math.sqrt(self.beta*self.q_imag),
                          waist_distance_mm=-self.q_real,
                          far_half_angle_mrad=1000*math.atan(math.sqrt(self.beta/self.q_imag)),
                          wavelength_nm=self.wavelength_nm, m2=self.m2)
            if abs(self.q_real) < 1e-9:
                result["status"] = "at Gaussian waist"
        return result


def state_from_dict(data):
    if not isinstance(data, dict):
        raise LayoutError("Invalid endpoint state.")
    try:
        args = {k: data[k] for k in BeamState.__dataclass_fields__ if k in data}
        s = BeamState(**args)
        s.position = vec(s.position)
        s.boundary_normal = vec(s.boundary_normal)
        for name in BeamState.__dataclass_fields__:
            if name not in ("position", "model", "boundary_normal", "boundary_kind", "trace", "link", "color"):
                setattr(s, name, finite(getattr(s, name), name))
        if s.model not in ("geometric", "gaussian"):
            raise LayoutError("Unknown beam model.")
        s.color = beam_color(s.color)
        if not -90 <= s.elevation <= 90 or s.path_mm < 0:
            raise LayoutError("Invalid endpoint elevation or path length.")
        if s.wavelength_nm <= 0 or s.m2 < 1 or s.q_imag <= 0:
            raise LayoutError("Wavelength and q imaginary part must be positive; M² must be at least 1.")
        if not 0 <= s.throughput <= 1 or not isinstance(s.trace, list) or not isinstance(s.link, dict):
            raise LayoutError("Invalid reference budget or endpoint origin.")
        if len(s.trace) > 20000:
            raise LayoutError("Endpoint history is too long. Start a new source for this layout.")
        if s.radius > 1e7 or norm(s.position) > 1e9 or abs(s.radial_slope) > 100:
            raise LayoutError("Beam dimensions or slopes exceed the layout range.")
        return s
    except (TypeError, OverflowError, ZeroDivisionError) as exc:
        raise LayoutError("Invalid or overflowing endpoint state.") from exc


def initial_state(source):
    diameter = finite(source.get("diameter_mm", 5), "Initial diameter")
    half_angle = finite(source.get("half_angle_mrad", 0), "Initial half-angle")/1000
    if diameter <= 0 or abs(half_angle) >= math.pi/2:
        raise LayoutError("Initial diameter must be positive and half-angle smaller than 90°.")
    s = BeamState(position=vec(source.get("position", (0, 0, 0))),
                  azimuth=finite(source.get("azimuth", 0)) % 360,
                  elevation=finite(source.get("elevation", 0)),
                  model=source.get("model", "geometric"), y=diameter/2,
                  slope=math.tan(half_angle), wavelength_nm=finite(source.get("wavelength_nm", 800)),
                  m2=finite(source.get("m2", 1)), color=beam_color(source.get("color", "red")))
    if s.wavelength_nm <= 0 or s.m2 < 1:
        raise LayoutError("Wavelength must be positive; enter M² ≥ 1 (not M).")
    if s.model == "gaussian":
        q = 1/complex(s.slope/s.y, -s.beta/(s.y*s.y))
        s.q_real, s.q_imag = q.real, q.imag
    return state_from_dict(asdict(s))


def encode_endpoint(state, name="Endpoint"):
    payload = {"format": "LaserOpticsRouter.Endpoint", "version": 2,
               "name": str(name)[:160], "state": asdict(state)}
    raw = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "LOR2:"+base64.urlsafe_b64encode(raw).decode("ascii")


def decode_endpoint(text):
    text = str(text).strip()
    if len(text) > 4000000 or not text.startswith(("LOR1:", "LOR2:")):
        raise LayoutError("Paste a complete LOR1: or LOR2: endpoint copied from LaserOpticsRouter.")
    try:
        data = json.loads(base64.b64decode(text[5:], altchars=b"-_", validate=True).decode("utf-8"))
        if data.get("format") != "LaserOpticsRouter.Endpoint" or data.get("version") not in (1, 2):
            raise ValueError("Unsupported version")
        required = set(BeamState.__dataclass_fields__)-{"extra_opl_mm", "throughput", "gdd_fs2", "trace", "link", "color"}
        if not required.issubset(data["state"]):
            raise ValueError("Incomplete state")
        return state_from_dict(data["state"]), str(data.get("name", "Endpoint"))
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        if isinstance(exc, LayoutError):
            raise
        raise LayoutError("Endpoint is incomplete, damaged or has an unsupported version.") from exc


def default_config():
    return dict(version=1, release=VERSION, route_id=uuid.uuid4().hex, document_id=uuid.uuid4().hex, run_name="LaserOpticsRouter", source=dict(
        position=[0, 0, 0], azimuth=0, elevation=0, diameter_mm=5,
        half_angle_mrad=0, model="geometric", wavelength_nm=800, m2=1, color="red"),
        rows=[dict(id="line1", name="Path 1", commands="p100 l50 p25 r90 p75", start_mode="source")],
        sizes={kind: dict(small=12.7, normal=25.4, large=50.8) for kind in FAMILIES},
        optic_overrides={}, component_defaults={}, budget_defaults=copy.deepcopy(BUDGET_DEFAULTS), options=dict(clean_joints=True, show_optics=True,
        keep_following_paths=True, use_assigned_components=False, protect_components=True,
        beam_opacity=0.30, optics_opacity=0.65, lens_thickness_mm=2,
        mirror_thickness_mm=3, oap_thickness_mm=4, gaussian_tolerance_mm=0.01))


# Illustrative coated-optic values near 800 nm, not product specifications.
# Glass n/thickness are deliberately zero until the user supplies both.
BUDGET_DEFAULTS = {
    "generic": dict(loss_pct=0, gdd_fs2=0),
    "lens": dict(loss_pct=1, gdd_fs2=100),
    "mirror": dict(loss_pct=1, gdd_fs2=0),
    "oap": dict(loss_pct=2, gdd_fs2=0),
    "pol": dict(loss_pct=5, gdd_fs2=100),
    "laha": dict(loss_pct=1, gdd_fs2=50),
    "laqu": dict(loss_pct=1, gdd_fs2=50),
    "nd": dict(loss_pct=90, gdd_fs2=100),
    "tp": dict(loss_pct=1, gdd_fs2=100),
    "bs": dict(transmission_pct=49, reflection_pct=49, gdd_t_fs2=100, gdd_r_fs2=0),
    "bsc": dict(transmission_pct=49, reflection_pct=49, gdd_t_fs2=300, gdd_r_fs2=300),
    "wp": dict(transmission_pct=49, reflection_pct=49, gdd_t_fs2=0, gdd_r_fs2=0),
    "rp": dict(transmission_pct=49, reflection_pct=49, gdd_t_fs2=0, gdd_r_fs2=0),
    "bd": dict(transmission_pct=49, reflection_pct=49, gdd_t_fs2=0, gdd_r_fs2=0, loss_pct=1, gdd_fs2=0),
}
BUDGET_FIELDS = ("loss_pct", "gdd_fs2", "n", "thickness_mm", "transmission_pct", "reflection_pct",
                 "gdd_t_fs2", "gdd_r_fs2", "n_t", "n_r", "thickness_t_mm", "thickness_r_mm")


def budget_values(kind, settings, defaults=None):
    values = {key: 0.0 for key in BUDGET_FIELDS}
    if kind in SPLITTERS:
        values.update(transmission_pct=50.0, reflection_pct=50.0)
    if not settings.get("custom"):
        values.update((defaults or BUDGET_DEFAULTS).get(kind, BUDGET_DEFAULTS[kind]))
    values.update(settings.get("budget", {}))
    values = {k: finite(values[k], "Budget "+k) for k in BUDGET_FIELDS}
    for key in ("loss_pct", "transmission_pct", "reflection_pct"):
        if not 0 <= values[key] <= 100: raise LayoutError("Loss, reflection and transmission must be 0–100%.")
    if kind in SPLITTERS and values["transmission_pct"]+values["reflection_pct"] > 100+1e-9:
        raise LayoutError("Splitter transmission + reflection cannot exceed 100%.")
    for suffix in ("", "_t", "_r"):
        n, t = values["n"+suffix], values["thickness"+suffix+"_mm"]
        if n < 0 or t < 0: raise LayoutError("Refractive index and effective glass thickness cannot be negative.")
        if t > 0 and n <= 0: raise LayoutError("Enter n > 0 when effective glass thickness is nonzero.")
    return values


def budget_event(state, event_id, *, geometric_mm=0, loss_pct=0, gdd_fs2=0, n=0, thickness_mm=0):
    extra = (n-1)*thickness_mm if n > 0 and thickness_mm > 0 else 0.0
    event = dict(id=event_id, geometric_mm=geometric_mm, extra_opl_mm=extra,
                 loss_pct=loss_pct, gdd_fs2=gdd_fs2,
                 state_stamp=state_fingerprint({k:getattr(state,k) for k in BeamState.__dataclass_fields__ if k not in ("trace","link")}))
    return replace(state, extra_opl_mm=state.extra_opl_mm+extra,
                   throughput=state.throughput*(1-loss_pct/100), gdd_fs2=state.gdd_fs2+gdd_fs2,
                   trace=state.trace+[event])


def optic_budget(state, optic, event_id, port=""):
    b = optic["budget"]
    suffix = "_"+port.lower() if port else ""
    loss = 100-b["transmission_pct" if port == "T" else "reflection_pct"] if port else b["loss_pct"]
    return budget_event(state, event_id+suffix, loss_pct=loss, gdd_fs2=b["gdd"+suffix+"_fs2"],
                        n=b["n"+suffix], thickness_mm=b["thickness"+suffix+"_mm"])


def reflected_chain_entries(entries, available):
    """Trim selected parent lines at the reflected port used downstream.

    Only a known port in the same route instance and line may replace a line
    end. Its complete trace must match the downstream snapshot. This avoids
    inferring connectivity from coincident coordinates or similar lengths.
    """
    resolved, notes = [], []
    for entry in entries:
        trace = entry["state"].get("trace", [])
        choices = {}
        if entry.get("kind") == "end":
            local_id = entry.get("endpoint_id", entry["id"])
            for port in available:
                if port.get("kind") not in ("reflected", "secondary", "end") or port["id"] == entry["id"]: continue
                port_id = port.get("endpoint_id", port["id"])
                if port_id.split(":", 1)[0] != local_id.split(":", 1)[0]: continue
                if port.get("run_token") != entry.get("run_token"): continue
                branch = port["state"].get("trace", [])
                n = len(branch)
                if port.get("trace_start", 0) != entry.get("trace_start", 0) or n <= entry.get("trace_start", 0): continue
                split = next((i for i,(a,b) in enumerate(zip(branch,trace)) if a != b), None)
                if split is None: continue
                event_id = str(branch[split].get("id", ""))
                if not event_id.endswith("_r") or trace[split].get("id") != event_id[:-2]+"_t": continue
                # A selected continuation must begin at/after this port. Merely
                # selecting both outgoing ports does not choose a unique arm.
                if any(other is not entry and other.get("trace_start", 0) >= n and
                       other["state"].get("trace", [])[:n] == branch for other in entries):
                    choices[port["id"]] = port
        if choices:
            port = max(choices.values(),key=lambda p:len(p["state"].get("trace",[])))
            longest = port["state"]["trace"]
            if any(p["state"]["trace"] != longest[:len(p["state"]["trace"])] for p in choices.values()):
                raise LayoutError("Selected continuations use different reflected branches. Select one connected arm.")
            resolved.append(port)
            notes.append(entry.get("name", "Parent path")+" counted up to "+port.get("name", "its reflected port")+".")
        else:
            resolved.append(entry)
    return resolved, list(dict.fromkeys(notes))


class _StaleBudgetSource(LayoutError):
    pass


def _calculate_trace_chain(entries, available=None):
    """Sum selected contiguous contributions once, rejecting gaps and mixed arms."""
    if not entries: raise LayoutError("Select at least one path end or reflected port.")
    requested = entries
    entries, notes = reflected_chain_entries(entries, available or entries)
    selected_links = {}
    for entry in entries:
        link = entry["state"].get("link", {})
        if link: selected_links[(link.get("document_id"),link.get("run_id"),link.get("endpoint_id"))] = entry
    for entry in entries:
        link = (entry.get("start_state") or {}).get("link", {})
        current = selected_links.get((link.get("document_id"),link.get("run_id"),link.get("endpoint_id")))
        if current and not equivalent_state(state_from_dict(entry["start_state"]),
                                             state_from_dict(current["state"]), history=False):
            raise _StaleBudgetSource("A selected source endpoint moved or its beam state changed. Refresh the continuation before combining these paths.")
    traces = [entry["state"].get("trace", []) for entry in entries]
    if any(not t for t in traces):
        raise LayoutError("This endpoint predates reference budgets. Rebuild that route first.")
    longest = max(traces, key=len)
    chosen = set()
    for entry, trace in zip(entries, traces):
        if trace != longest[:len(trace)]:
            raise LayoutError("Select one connected arm. These endpoints branch, are unrelated, or have different source histories.")
        start = entry.get("trace_start", 0)
        chosen.update(range(start, len(trace)))
    if not chosen: raise LayoutError("The selected paths have no length or optical contributions.")
    if chosen != set(range(min(chosen), max(chosen)+1)):
        raise LayoutError("A connecting path is missing from the selection.")
    geo = extra = gdd = 0.0
    throughput = 1.0
    for i in sorted(chosen):
        e = longest[i]
        geo += finite(e["geometric_mm"]); extra += finite(e["extra_opl_mm"])
        gdd += finite(e["gdd_fs2"]); throughput *= 1-finite(e["loss_pct"])/100
    selections = [dict(requested_id=before["id"], resolved_id=entry["id"], name=entry.get("name", "Path"),
                       run_token=entry.get("run_token", "draft"),
                       event_ids=[e["id"] for e in entry["state"]["trace"][entry.get("trace_start", 0):]],
                       included=entry.get("included", []), included_commands=entry.get("included_commands", ""))
                  for before, entry in zip(requested, entries)]
    return dict(geometric_mm=geo, optical_path_mm=geo+extra, loss_pct=100*(1-throughput),
                gdd_fs2=gdd, contributions=len(chosen), notes=notes, selections=selections)


def _budget_identity(entry):
    local = entry['state'].get('trace', [])[entry.get('trace_start', 0):]
    instance = entry.get('run_token') or entry.get('run_id') or (
        str(local[0].get('id', '')).split(':', 1)[0] if local else entry['state'].get('link', {}).get('run_id', 'draft'))
    endpoint = entry.get('endpoint_id', entry['id'])
    return str(instance), str(endpoint)


def _budget_row(entry):
    instance, endpoint = _budget_identity(entry)
    return instance, endpoint.split(':', 1)[0]


def _reflected_alternative(entry, candidate):
    if entry.get('kind') != 'end' or _budget_row(entry) != _budget_row(candidate): return False
    if candidate.get('kind') not in ('reflected', 'secondary', 'end'): return False
    a, b = entry['state'].get('trace', []), candidate['state'].get('trace', [])
    if entry.get('trace_start', 0) != candidate.get('trace_start', 0): return False
    split = next((i for i, (x, y) in enumerate(zip(a,b)) if x != y), None)
    if split is None: return False
    event = str(b[split].get('id', ''))
    return event.endswith('_r') and a[split].get('id') == event[:-2]+'_t'


def _geometric_budget_chain(requested, available, original_error):
    """Find one directed, continuous arm and count each instance's local events.

    Coordinates and full direction vectors connect independently created paths.
    Only a unique chain may supply unselected intermediate contributions.
    Recorded source history is kept intact; this never rewrites optical states.
    """
    resolved, notes = reflected_chain_entries(requested, available)
    pool = {_budget_identity(e): e for e in list(available)+list(resolved)
            if e.get('start_state') and e['state'].get('trace', [])[e.get('trace_start', 0):]}
    groups = {}
    for before, entry in zip(requested, resolved):
        groups.setdefault(_budget_row(entry), []).append((before, entry))
    choices = {}
    for row, members in groups.items():
        longest = max((e for _,e in members), key=lambda e:len(e['state'].get('trace', [])))
        trace = longest['state'].get('trace', [])
        if any(e['state'].get('trace', []) != trace[:len(e['state'].get('trace', []))] for _,e in members):
            raise original_error
        keys = {_budget_identity(longest)}
        # Explicit selection of a port constrains the arm; a whole-line end may
        # be shortened to the reflected/secondary output that connects onward.
        if len({_budget_identity(e) for _,e in members}) == 1:
            keys.update(k for k,e in pool.items() if _reflected_alternative(longest,e))
        choices[row] = keys
    pool = {k:e for k,e in pool.items() if _budget_row(e) not in choices or k in choices[_budget_row(e)]}
    if any(not (keys & pool.keys()) for keys in choices.values()): raise original_error
    if len(pool) > 3000: raise LayoutError('Too many path endpoints for automatic joining. Use a smaller current route or select a direct chain.')
    starts = {k: state_from_dict(e['start_state']) for k,e in pool.items()}
    ends = {k: state_from_dict(e['state']) for k,e in pool.items()}
    rows = {k: _budget_row(e) for k,e in pool.items()}
    # Nearby-position buckets bound adjacency work for large documents.
    cell = lambda p: tuple(math.floor(v/CONNECTION_POSITION_MM) for v in p)
    buckets = {}
    for k,s in starts.items(): buckets.setdefault(cell(s.position), []).append(k)
    edges, examined_connections = {}, 0
    for k,end in ends.items():
        cx,cy,cz = cell(end.position)
        near = (other for dx in (-1,0,1) for dy in (-1,0,1) for dz in (-1,0,1)
                for other in buckets.get((cx+dx,cy+dy,cz+dz), []))
        edges[k] = []
        for other in near:
            examined_connections += 1
            if examined_connections > MAX_CONNECTION_CANDIDATES:
                raise LayoutError('Too many coincident endpoints for automatic joining. Use Current route or a smaller set of available paths.')
            if rows[k] != rows[other] and connection_matches(end,starts[other]): edges[k].append(other)
    required = set(groups)
    # Prune nodes that cannot lead to any selected contribution.
    reverse = {}
    for key, targets in edges.items():
        for target in targets: reverse.setdefault(target, []).append(key)
    can_reach = {k for k in pool if rows[k] in required}; todo = list(can_reach)
    while todo:
        for key in reverse.get(todo.pop(), []):
            if key not in can_reach:can_reach.add(key);todo.append(key)
    solutions, examined = {}, 0
    stack = [(key,(key,),frozenset((rows[key],))) for row in required for key in choices[row] if key in pool]
    while stack:
        key,path,seen = stack.pop();examined += 1
        if examined > 20000:
            raise LayoutError('Too many possible connecting paths. Select intermediate endpoints to identify one connected arm.')
        if required <= seen:
            signature = tuple((rows[k],tuple(e['id'] for e in pool[k]['state']['trace'][pool[k].get('trace_start',0):])) for k in path)
            solutions[signature] = path
            if len(solutions) > 1:raise LayoutError('More than one continuous connecting path exists. Select the intermediate path or port explicitly.')
            continue
        for other in edges[key]:
            if other in can_reach and rows[other] not in seen:
                stack.append((other,path+(other,),seen|{rows[other]}))
    if not solutions: raise original_error
    path = next(iter(solutions.values())); chosen = {rows[k]:pool[k] for k in path}
    selections, events = [], {}
    geo = extra = gdd = 0.0;throughput = 1.0
    for key in path:
        entry = pool[key]; row = rows[key]; local = entry['state']['trace'][entry.get('trace_start',0):]
        for event in local:
            event_key = (key[0], event['id'])
            if event_key in events:
                if events[event_key] != event:raise LayoutError('Conflicting versions of the same optical contribution. Refresh the affected routes.')
                continue
            events[event_key] = event
            geo += finite(event['geometric_mm']);extra += finite(event['extra_opl_mm'])
            gdd += finite(event['gdd_fs2']);throughput *= 1-finite(event['loss_pct'])/100
        if row not in required:
            notes.append('Included connecting path: '+entry.get('route_name',entry.get('run',''))+' / '+entry.get('name','Path')+'.')
    def selection(before, entry, automatic=False):
        return dict(requested_id=before['id'] if before else None, resolved_id=entry['id'],
                    run_token=entry.get('run_token','draft'), name=entry.get('name','Path'),
                    route_name=entry.get('route_name',entry.get('run','')), automatic=automatic,
                    event_ids=[e['id'] for e in entry['state']['trace'][entry.get('trace_start',0):]],
                    included=entry.get('included',[]), included_commands=entry.get('included_commands',''))
    for before, entry in zip(requested,resolved):
        use = chosen[_budget_row(entry)]
        # Keep a deliberately selected shorter prefix's own highlight.
        if entry['state']['trace'] == use['state']['trace'][:len(entry['state']['trace'])]:use = entry
        selections.append(selection(before,use))
        if _budget_identity(use) != _budget_identity(before):
            notes.append(before.get('name','Parent path')+' counted up to '+use.get('name','its reflected port')+'.')
    selections.extend(selection(None,pool[k],True) for k in path if rows[k] not in required)
    # Independent paths may have different envelope settings. Sum their manual
    # budgets honestly without claiming to propagate one continuous beam state.
    if any(not same_envelope(ends[a],starts[b]) for a,b in zip(path,path[1:])):
        notes.append('Connected geometry has differing beam envelopes. This total combines local reference budgets; it does not recalculate beam propagation.')
    notes.append('Joined by endpoint position and forward direction; each local contribution is counted once.')
    return dict(geometric_mm=geo,optical_path_mm=geo+extra,loss_pct=100*(1-throughput),gdd_fs2=gdd,
                contributions=len(events),notes=list(dict.fromkeys(notes)),selections=selections,connection_mode='geometry')


def calculate_chain(entries, available=None):
    """Combine a recorded arm or one uniquely connected geometric path."""
    if not entries:raise LayoutError('Select at least one path end or reflected port.')
    available = available or entries
    try:
        result = _calculate_trace_chain(entries,available)
    except _StaleBudgetSource:
        raise  # Do not conceal a known stale link behind a coincident point.
    except LayoutError as exc:
        if 'predates reference budgets' in str(exc):raise
        return _geometric_budget_chain(entries,available,exc)
    # Distinct copies of a route reuse event ids. They are physical contributions,
    # not duplicate checkboxes, and must be joined/countable by instance.
    seen = {}
    for entry in entries:
        identity = _budget_identity(entry)
        for event in entry['state']['trace'][entry.get('trace_start',0):]:
            prior = seen.setdefault(event['id'], identity[0])
            if prior != identity[0]:
                return _geometric_budget_chain(entries,available,LayoutError('Select one connected arm; these route instances are not connected.'))
    return result


def state_fingerprint(data):
    state = asdict(state_from_dict(data))
    state.pop("link", None)
    # Reference contributions are captured by their totals. Names are not geometry.
    state.pop("trace", None)
    state.pop("color", None)  # Display color must not change optical trace identity.
    def rounded(v):
        if isinstance(v, (float, int)): return round(v, 7)
        if isinstance(v, (list, tuple)): return [rounded(x) for x in v]
        return v
    state = {k: rounded(v) for k, v in state.items()}
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:24]


def endpoint_link(state, document_id, run_id, revision, endpoint_id):
    return dict(document_id=document_id, run_id=run_id, revision=revision,
                endpoint_id=endpoint_id, fingerprint=state_fingerprint(asdict(state)))


def connection_matches(a, b):
    """Same oriented connection, independent of diameter, budgets and revisions."""
    return (norm(sub(a.position, b.position)) <= CONNECTION_POSITION_MM and
            norm(sub(a.d, b.d)) <= 2*math.sin(math.radians(CONNECTION_ANGLE_DEG)/2))


def equivalent_state(a, b, history=True):
    if not connection_matches(a, b) or a.model != b.model: return False
    fields = ("y", "slope") if a.model == "geometric" else ("q_real", "q_imag", "m2", "wavelength_nm")
    fields += ("path_mm", "extra_opl_mm", "throughput", "gdd_fs2", "boundary_bend")
    return (a.color == b.color and all(math.isclose(getattr(a,k),getattr(b,k),rel_tol=1e-9,abs_tol=1e-8) for k in fields) and
            a.boundary_kind == b.boundary_kind and norm(sub(a.boundary_normal,b.boundary_normal)) < 1e-7 and
            (not history or a.trace == b.trace))


def beam_frame(state):
    a = math.radians(state.azimuth)
    return frame(state.d, (-math.sin(a), math.cos(a), 0))


def continuation_transform(before, after):
    """Rigid movement mapping the old beam origin/frame to the new one."""
    a, b = beam_frame(before), beam_frame(after)
    inverse_a = tuple(tuple(a[j][i] for j in range(3)) for i in range(3))
    rotation = tuple(world(b, column) for column in inverse_a)
    return sub(after.position, world(rotation, before.position)), rotation


def moved_state(state, origin, rotation):
    d = world(rotation, state.d)
    az, el = angles(d, state.azimuth)
    return replace(state, position=add(origin, world(rotation, state.position)), azimuth=az, elevation=el,
                   boundary_normal=world(rotation, state.boundary_normal))


def parse_commands(text, row=None):
    tokens = []
    for match in re.finditer(r"\S+", str(text).split("#", 1)[0]):
        raw = match.group()
        tok = raw.lower()
        item = dict(raw=raw, start=match.start(), end=match.end(), size="normal", flip=False, visual_flip=False)
        try:
            m = re.fullmatch(r"p("+NUMBER+r")", tok)
            if m:
                item.update(kind="propagate", length=finite(m[1]))
                if item["length"] < 0:
                    raise LayoutError("Propagation distance must be nonnegative.")
            else:
                p = re.match(r"[+_f-]*", tok)
                prefixes = p[0]
                if sum(prefixes.count(c) for c in "+-") > 1 or prefixes.count("f") > 1 or prefixes.count("_") > 1:
                    raise LayoutError("Use each optic modifier only once: one size sign, one f and one underscore.")
                sign = "+" if "+" in prefixes else "-" if "-" in prefixes else ""
                item["size"] = {"+": "large", "-": "small", "": "normal"}[sign]
                item["flip"] = "_" in prefixes
                item["visual_flip"] = "f" in prefixes
                body = tok[p.end():]
                if body in ("pol", "g", "laha", "laqu", "nd"):
                    item["kind"] = "generic" if body == "g" else body
                elif re.fullmatch(r"tp("+NUMBER+r")(?:d("+NUMBER+r"))?", body):
                    m = re.fullmatch(r"tp("+NUMBER+r")(?:d("+NUMBER+r"))?", body)
                    item.update(kind="tp", angle=finite(m[1]), displacement=finite(m[2] or 0))
                    if abs(item["angle"]) >= 90:
                        raise LayoutError("Tweaker plate incidence must be between −90° and +90° (exclusive).")
                    if abs(item["displacement"]) > 10000:
                        raise LayoutError("Beam displacement must be at most 10000 mm in magnitude.")
                elif body in ("bsc", "bsc-"):
                    item["kind"] = "bsc"
                    item["reverse"] = body.endswith("-")
                elif re.fullmatch(r"(?:wp|rp|bd)("+NUMBER+r")[hv]?-?", body):
                    m = re.fullmatch(r"(wp|rp|bd)("+NUMBER+r")([hv])?(-)?", body)
                    kind, value = m[1], finite(m[2])
                    if value <= 0: raise LayoutError("Prism angle / displacer distance must be positive; use a trailing - for the other side.")
                    if kind != "bd" and value >= 180: raise LayoutError("Prism separation angle must be below 180°.")
                    if kind == "bd" and value > 10000: raise LayoutError("Beam displacement must be at most 10000 mm.")
                    item.update(kind=kind, amount=value, axis=m[3] or "h", reverse=bool(m[4]))
                elif re.fullmatch(r"l("+NUMBER+r")", body):
                    item.update(kind="lens", focal=finite(body[1:]))
                else:
                    m = re.fullmatch(r"(r|bs)("+NUMBER+r")(?:v("+NUMBER+r"))?(?:f("+NUMBER+r"))?", body)
                    if not m:
                        if re.match(r"[cef]"+NUMBER+r"$", tok):
                            raise LayoutError("Legacy c/f/e commands were removed. Use l<focal> and p<distance>; define collimation in Source.")
                        raise LayoutError("Unknown command. Use spaces: p50 l50 r90 pol g bs30 bsc r90f50 _r90f50 wp20h rp10.6 bd4v laha laqu nd tp30d0.5. The f prefix rotates optics only, never propagation.")
                    if m[1] == "bs" and m[4] is not None:
                        raise LayoutError("A beam splitter has no focal-length suffix.")
                    item.update(kind="oap" if m[4] else ("mirror" if m[1] == "r" else "bs"),
                                horizontal=finite(m[2]), vertical=finite(m[3] or 0))
                    if m[4]: item["focal"] = finite(m[4])
                if item["flip"] and item["kind"] not in ("oap", "bd"):
                    raise LayoutError("The underscore applies to an OAP or a combining beam displacer.")
                if item.get("focal") == 0:
                    raise LayoutError("Focal length cannot be zero.")
                if item["kind"] == "oap" and item["focal"] < 0:
                    raise LayoutError("OAP reflected focal length must be positive. Use _ to swap its parent-axis leg.")
            tokens.append(item)
        except LayoutError as exc:
            raise LayoutError(str(exc), row, len(tokens), match.start(), match.end()) from exc
    if not tokens:
        raise LayoutError("Enter at least one command, for example p100.", row, 0, 0, len(str(text)))
    if len(tokens) > 2000:
        raise LayoutError("Use at most 2000 commands per line.", row)
    return tokens


CUSTOM_FIELDS = ("component_token", "component_ref_token", "component_name", "component_linked", "reference",
                 "reference_name", "shift", "rotation", "diameter_mm", "design_bend_deg", "roll_deg", "budget",
                 "tube_length_mm", "crystal_width_mm", "shape", "depth_mm", "beam_color", "displacement_mm")


def default_key(token, state=None):
    """Part defaults; normalize case/numbers and ignore both orientation modifiers."""
    prefix = {"normal": "", "small": "-", "large": "+"}[token["size"]]
    kind = token["kind"]
    if kind == "lens": body = "l"+format(token["focal"], ".15g")
    elif kind == "generic": body = "g"
    elif kind in ("pol", "bsc", "bs", "laha", "laqu", "nd", "tp"): body = kind
    elif kind in PRISMS: body = kind+format(token["amount"], ".15g")
    elif kind == "oap":
        # Calibration belongs to the physical design bend, not the turn sign or
        # which leg follows the parent axis. At an inclined input use the true bend.
        start = state or BeamState()
        end = start.turned(token["horizontal"], token["vertical"])
        bend = math.degrees(math.acos(max(-1, min(1, dot(start.d, end.d)))))
        body = "r"+format(round(bend, 8), ".10g")+"f"+format(token["focal"], ".15g")
    else:
        body = ("bs" if kind == "bs" else "r")+format(token["horizontal"], ".15g")
        if token["vertical"]: body += "v"+format(token["vertical"], ".15g")
        if kind == "oap": body += "f"+format(token["focal"], ".15g")
    return prefix+body


def normalize_component_defaults(defaults):
    """Merge legacy underscore presets; an unprefixed preset wins a collision.

    Work on copies. Loading old documents must not rewrite their saved data or
    alter the explicit placements pinned in already-built route configurations.
    """
    result = {}
    candidates = []
    for key, settings in defaults.items():
        try:
            tokens = parse_commands(key)
            if len(tokens) != 1 or tokens[0]["kind"] == "propagate": raise LayoutError("Not an optic")
            token = tokens[0]
            canonical = default_key(token)
            priority = (bool(token["flip"]), bool(token["visual_flip"]), key != canonical, key)
            candidates.append((priority, canonical, settings))
        except LayoutError:
            result[key] = copy.deepcopy(settings)
    for _, canonical, settings in sorted(candidates, key=lambda item: item[0]):
        if canonical not in result: result[canonical] = copy.deepcopy(settings)
    return result


def default_token(key):
    """Resolve a physical-part key, including angle-independent plate defaults."""
    command = re.sub(r"^([+-]?)bs$", r"\g<1>bs90", str(key))
    command = re.sub(r"^([+-]?)tp$", r"\g<1>tp0d0", command)
    tokens = parse_commands(command)
    if len(tokens) != 1 or tokens[0]["kind"] == "propagate":
        raise LayoutError("Invalid component-default key.")
    return tokens[0]


def component_template(settings):
    result = {k: copy.deepcopy(settings[k]) for k in CUSTOM_FIELDS if k in settings}
    result["custom"] = settings.get("custom", bool(result.get("component_ref_token") or result.get("component_token")))
    if result["custom"] and not (result.get("component_ref_token") or result.get("component_token")):
        raise LayoutError("Select a component before saving its default.")
    for field in ("reference", "shift", "rotation"):
        result[field] = list(vec(result.get(field, [0, 0, 0])))
    return result


def optic_settings(token, override, defaults, state=None):
    if override.get("token") not in (None, token["raw"]): override = {}
    key = default_key(token, state)
    mode = override.get("representation")
    if mode is None:
        if "custom" in override: mode = "custom" if override["custom"] else "builtin"
        elif any(k in override for k in CUSTOM_FIELDS):
            # Old drafts could store just a changed property, without a mode.
            # Preserve their resolved choice as an individual calibration.
            override = dict(copy.deepcopy(defaults.get(key, {})), **override)
            mode = "custom" if override.get("custom", bool(override.get("component_ref_token") or override.get("component_token"))) else "builtin"
        else: mode = "default"
    if mode not in ("builtin", "default", "custom"):
        raise LayoutError("Unknown optic representation.")
    settings = copy.deepcopy(defaults.get(key, {})) if mode == "default" else copy.deepcopy(override)
    # A default is a live reference, never a partly copied individual placement.
    custom = (settings.get("custom", bool(settings.get("component_ref_token") or settings.get("component_token")))
              if mode == "default" else mode == "custom")
    settings.update(representation=mode, custom=custom)
    for field_name in ("reference", "shift", "rotation"):
        if field_name in settings: settings[field_name] = list(vec(settings[field_name]))
    return settings


def representation_frame(optic):
    basis = tuple(tuple(v) for v in optic["frame"])
    return rotated_columns(basis, 0, 0, 180) if optic.get("visual_flip") else basis


def prism_axis(state, token):
    axis = beam_frame(state)[0 if token["axis"] == "h" else 1]
    return mul(axis, -1 if token.get("reverse") else 1)


def prism_output(state, token, secondary=False):
    """Fixed central-ray separation, independent of wavelength/polarization."""
    axis = prism_axis(state, token)
    if token["kind"] == "bd":
        return replace(state, position=add(state.position, mul(axis, token["amount"] if secondary else 0)),
                       boundary_normal=(0,0,0), boundary_bend=0, boundary_kind="")
    theta = token["amount"]*((0.5 if secondary else -0.5) if token["kind"] == "wp" else (1 if secondary else 0))
    rad = math.radians(theta)
    az, el = angles(add(mul(state.d, math.cos(rad)), mul(axis, math.sin(rad))), state.azimuth)
    return replace(state, azimuth=az, elevation=el, boundary_normal=(0,0,0), boundary_bend=0, boundary_kind="")


def same_envelope(a, b):
    if a.model != b.model: return False
    keys = ("y", "slope") if a.model == "geometric" else ("q_real", "q_imag", "wavelength_nm", "m2")
    return all(math.isclose(getattr(a,k),getattr(b,k),rel_tol=1e-9,abs_tol=1e-10) for k in keys)


def displaced(state, offset):
    if norm(offset) < EPS: return replace(state)
    return replace(state, position=add(state.position, offset), boundary_normal=(0,0,0),
                   boundary_bend=0, boundary_kind="")


def _optic(state, token, key, settings, sizes):
    kind = token["kind"]
    size = finite(settings.get("diameter_mm") or sizes.get(kind, {}).get(token["size"],
                  dict(small=12.7, normal=25.4, large=50.8)[token["size"]]), "Optic size")
    if size <= 0 or size > 10000:
        raise LayoutError("Optic size must be positive and at most 10000 mm.")
    out = replace(state)
    if kind == "bsc":
        roll = math.radians(finite(settings.get("roll_deg", 0), "Cube roll")+(180 if token.get("reverse") else 0))
        a = math.radians(state.azimuth)
        left = (-math.sin(a), math.cos(a), 0)
        up = cross(state.d, left)
        d_out = add(mul(left, math.cos(roll)), mul(up, math.sin(roll)))
        out.azimuth, out.elevation = angles(d_out, state.azimuth)
    elif kind in ("mirror", "oap", "bs"):
        out = state.turned(token["horizontal"], token["vertical"])
    elif kind in PRISMS and not token["flip"]:
        out = prism_output(state, token)
    d_in, d_out = state.d, out.d
    bend = math.degrees(math.acos(max(-1, min(1, dot(d_in, d_out)))))
    reflecting = kind in ("mirror", "oap", "bs", "bsc")
    if reflecting and bend < 0.01:
        raise LayoutError("A reflecting optic needs a nonzero bend (at least 0.01°). Omit a zero turn.")
    normal = unit(sub(d_out, d_in)) if reflecting else d_in
    offset = (0, 0, 0)
    if kind == "tp":
        theta = math.radians(token["angle"])
        normal = add(mul(d_in, math.cos(theta)), mul(beam_frame(state)[0], math.sin(theta)))
        offset = mul(beam_frame(state)[0], token["displacement"]*(-1 if token["angle"] < 0 else 1))
        out = displaced(out, offset)
    elif kind in ("bs", "bsc"):
        distance = finite(settings.get("displacement_mm", 0), "Transmission displacement")
        if abs(distance) > 10000:
            raise LayoutError("Transmission displacement must be at most 10000 mm in magnitude.")
        transverse = sub(d_out, mul(d_in, dot(d_in, d_out)))
        axis = unit(transverse) if norm(transverse) > 1e-8 else beam_frame(state)[0]
        offset = mul(axis, -distance)
    azimuth = math.radians(state.azimuth)
    basis = frame(normal, (-math.sin(azimuth), math.cos(azimuth), 0))
    oap = None
    if kind == "oap":
        f = token["focal"]
        z = d_out if token["flip"] else mul(d_in, -1)
        focal_vector = mul(d_in, -f) if token["flip"] else mul(d_out, f)
        radial = sub(mul(focal_vector, -1), mul(z, -dot(focal_vector, z)))
        basis = frame(z, radial)
        parent_f = f*(1-math.cos(math.radians(bend)))/2
        if parent_f < 1e-4:
            raise LayoutError("This OAP bend/focal length produces an impractically small parent focal length.")
        oap = dict(parent_focal_mm=parent_f, reflected_focal_mm=f,
                   decenter_mm=norm(radial), vertex_depth_mm=f-parent_f,
                   off_axis_deg=180-bend, parent_axis=list(z),
                   focus=list(add(state.position, focal_vector)))
    elif kind == "bsc":
        basis = frame(d_in, d_out)
    elif kind in PRISMS:
        basis = frame(d_in, mul(prism_axis(state,token), -1 if token["flip"] else 1))
    if kind in ("lens", "oap"):
        out = out.focused(token["focal"])
    if kind == "generic":
        color = beam_color(settings.get("beam_color", "inherit"), inherit=True)
        if color != "inherit": out = replace(out, color=color)
    incidence = math.degrees(math.acos(min(1, abs(dot(d_in, normal))))) if reflecting or kind == "tp" else 0
    footprint = 2*state.radius/max(abs(dot(d_in, normal)), 1e-10)
    if kind == "oap": footprint = 2*state.radius  # blank aperture is measured along its parent axis
    if kind == "bsc": footprint = 2*state.radius
    optic = dict(id=key, kind=kind, token=token["raw"], size=token["size"],
                 diameter_mm=size, position=list(state.position), normal=list(normal),
                 frame=[list(x) for x in basis], input_direction=list(d_in),
                 output_direction=list(d_out), bend_deg=bend, incidence_deg=incidence,
                 footprint_mm=footprint, focal_mm=token.get("focal"), flip=token["flip"],
                 settings=copy.deepcopy(settings), oap=oap, default_key=default_key(token, state),
                 reverse=token.get("reverse", False),
                 visual_flip=token["visual_flip"])
    if kind in ("tp", "bs", "bsc"):
        optic.update(displacement_mm=token["displacement"] if kind == "tp" else distance,
                     transmission_offset=list(offset), transmission_position=list(add(state.position, offset)))
    if kind == "tp": optic["plate_angle_deg"] = token["angle"]
    if kind == "generic":
        shape = settings.get("shape", "disc")
        if shape not in ("disc", "cube", "ball"):
            raise LayoutError("Choose disc, cube or ball for a generic optic.")
        depth = finite(settings.get("depth_mm", 3), "Generic optic depth")
        if not 0 < depth <= 10000:
            raise LayoutError("Generic optic depth must be positive and at most 10000 mm.")
        optic.update(shape=shape, depth_mm=depth)
    if reflecting:
        out.boundary_normal, out.boundary_bend, out.boundary_kind = tuple(normal), bend, kind
    if kind in PRISMS:
        scale = size/25.4
        length = (41 if token["amount"] > 2.7 else 28) if kind == "bd" else 14
        width = finite(settings.get("crystal_width_mm") or 10*scale, "Crystal width")
        length = finite(settings.get("tube_length_mm") or length*scale, "Tube length")
        if width <= 0 or width*math.sqrt(2) >= size or length <= 0 or length > 10000:
            raise LayoutError("Crystal width must fit inside the tube; tube length must be positive and at most 10000 mm.")
        optic.update(amount=token["amount"], axis=token["axis"], combining=token["flip"],
                     tube_length_mm=length, crystal_width_mm=width)
    return optic, out


def sample_segment(segment, tolerance=0.01):
    """Adaptive envelope knots; include every focus/waist explicitly."""
    s, length = segment["state"], segment["length"]
    points = [0.0, length]
    waist = -s.q_real if s.model == "gaussian" else (-s.y/s.slope if s.slope else -1)
    if 0 < waist < length: points.append(waist)
    points.sort()
    if s.model == "geometric": return [(t, s.propagated(t).radius) for t in points]
    result = []
    def refine(a, b, depth=0):
        ra, rb = s.propagated(a).radius, s.propagated(b).radius
        m = (a+b)/2
        rm = s.propagated(m).radius
        allowed = min(tolerance, max(rm*0.005, 1e-6))
        if depth < 14 and abs((ra+rb)/2-rm) > allowed:
            refine(a, m, depth+1); refine(m, b, depth+1)
        else:
            result.append((a, ra))
    for a, b in zip(points, points[1:]): refine(a, b)
    result.append((length, s.propagated(length).radius))
    if len(result) > 2048: raise LayoutError("Gaussian envelope requires too many sections; shorten this propagation.")
    return result


def plan_layout(config):
    config = copy.deepcopy(config)
    config["release"] = VERSION
    config["component_defaults"] = normalize_component_defaults(config.get("component_defaults", {}))
    rows = config.get("rows", [])
    if not 1 <= len(rows) <= 100:
        raise LayoutError("Use between 1 and 100 path lines.")
    source = initial_state(config.get("source", {}))
    sizes = config.get("sizes", {})
    overrides = config.get("optic_overrides", {})
    all_segments, all_optics, endpoints, row_results, warnings = [], [], [], [], []
    previous = None
    previous_companions = []
    ids = set()
    for ri, row in enumerate(rows):
        rid = str(row.get("id", "line"+str(ri+1)))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", rid):
            raise LayoutError("Path IDs must use letters, numbers, underscores or hyphens (at most 100 characters).", ri)
        if rid in ids: raise LayoutError("Path line IDs must be unique.", ri)
        ids.add(rid)
        name = str(row.get("name", "Path "+str(ri+1)))[:100]
        mode = row.get("start_mode", "source")
        if mode == "previous":
            if previous is None: raise LayoutError("The first line cannot continue a previous line.", ri)
            state = replace(previous)
        elif mode == "snapshot":
            state, _ = decode_endpoint(row.get("endpoint", ""))
        elif mode == "source": state = replace(source)
        else: raise LayoutError("Unknown start mode.", ri)
        companions = copy.deepcopy(previous_companions) if mode == "previous" else []
        for lane in companions:
            lane.update(trace_start=len(lane["state"].trace), start_state=asdict(lane["state"]), last_segment=None)
        start_path = state.path_mm
        start_state = asdict(state)
        trace_start = len(state.trace)
        tokens = parse_commands(row.get("commands", ""), ri)
        if not isinstance(row.get("step_labels", {}), dict):
            raise LayoutError("Step labels must be an object keyed by step identity.", ri)
        # Older routes retain their numeric IDs. The visual editor assigns stable
        # IDs to new steps so moving/inserting a step cannot attach the wrong CAD.
        step_ids = row.get("step_ids", [str(i) for i in range(len(tokens))])
        if (not isinstance(step_ids, list) or len(step_ids) != len(tokens)
                or any(not isinstance(s, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", s) for s in step_ids)
                or len(set(step_ids)) != len(step_ids)):
            raise LayoutError("Step identities are invalid. Re-enter this line in the command editor.", ri)
        row_segments, row_optics, steps, ports = [], [], [], []
        pending = (dict(kind="mirror", normal=list(state.boundary_normal), position=list(state.position),
                        bend_deg=state.boundary_bend, label=name+" · start interface")
                   if norm(state.boundary_normal) > EPS else None)
        for ti, token in enumerate(tokens):
            try:
                key = rid+":"+step_ids[ti]
                step_label = str(row.get("step_labels", {}).get(step_ids[ti], ""))[:100].strip()
                if token["kind"] == "propagate":
                    length = token["length"]
                    if length > 0:
                        if state.model == "geometric" and state.y == 0 and state.slope == 0:
                            raise LayoutError("A zero-radius, zero-divergence beam cannot be drawn.")
                        seg = dict(name=f"{name} — {ti+1:03d} {step_label or token['raw']}", state=replace(state),
                                   length=length, trim_start=None, trim_end=None, row=ri, secondary=False,
                                   event_ids=[str(config.get("route_id", "draft"))+":"+key+":p"])
                        if pending and pending["kind"] in ("mirror", "oap"):
                            seg["trim_start"] = pending
                        row_segments.append(seg)
                        # The two outputs of a prism/displacer advance together.
                        # Coincident combined rays keep separate budget histories;
                        # identical envelopes are drawn only once.
                        for lane in companions:
                            other = lane["state"]
                            if not (lane["combined"] and connection_matches(other,state) and same_envelope(other,state)):
                                extra = dict(name=f"{name} — {ti+1:03d} {token['raw']} · secondary",
                                             state=replace(other), length=length, trim_start=pending if lane["combined"] else None,
                                             trim_end=None, row=ri, secondary=True,
                                             event_ids=[str(config.get("route_id", "draft"))+":"+key+":p:"+lane["id"]])
                                row_segments.append(extra); lane["last_segment"] = extra
                            else:
                                seg["event_ids"].append(str(config.get("route_id", "draft"))+":"+key+":p:"+lane["id"])
                                lane["last_segment"] = None
                            lane["state"] = budget_event(other.propagated(length),
                                str(config.get("route_id", "draft"))+":"+key+":p:"+lane["id"], geometric_mm=length)
                        state = state.propagated(length)
                        state = budget_event(state, str(config.get("route_id", "draft"))+":"+key+":p",
                                             geometric_mm=length)
                        pending = None
                else:
                    settings = optic_settings(token, overrides.get(key, {}), config.get("component_defaults", {}), state)
                    optic, out = _optic(state, token, key, settings, sizes)
                    optic["budget"] = budget_values(token["kind"], settings, config.get("budget_defaults"))
                    event_id = str(config.get("route_id", "draft"))+":"+key
                    optic["event_ids"] = [event_id+suffix for suffix in ("", "_t", "_r", ":B", ":B_t", ":B_r")]
                    out = optic_budget(out, optic, event_id, "R" if token["kind"] in ("bs", "bsc") else
                                       "T" if token["kind"] in PRISMS and not token["flip"] else "")
                    optic.update(row=ri, step=ti, label=f"{name} · {ti+1} · {step_label or token['raw']}")
                    row_optics.append(optic)
                    if optic["footprint_mm"] > optic.get("crystal_width_mm",optic["diameter_mm"]):
                        warnings.append(optic["label"]+": beam footprint exceeds the nominal optic size; beam is not aperture-clipped.")
                    if token["kind"] == "oap":
                        if token["visual_flip"]:
                            warnings.append(optic["label"]+": f rotates the CAD representation only. Recheck OAP surface alignment; use _ to swap the parent-axis leg in the optical layout.")
                        if settings.get("custom"):
                            angle = finite(settings.get("design_bend_deg", 90), "Custom OAP design bend")
                            if abs(angle-optic["bend_deg"]) > 0.2:
                                warnings.append(optic["label"]+f": requested bend {optic['bend_deg']:.3f}° differs from custom OAP design bend {angle:g}°. Envelope remains idealized.")
                        if abs(state.radial_slope) > 0.1:
                            warnings.append(optic["label"]+": large beam angle; the paraxial envelope is only a layout approximation.")
                    if token["kind"] in PRISMS:
                        if token["kind"] == "bd" and token["flip"]:
                            expected = prism_output(state, token, True)
                            matches = [lane for lane in companions if not lane["combined"] and connection_matches(lane["state"],expected)]
                            if len(matches) != 1:
                                warnings.append(optic["label"]+": beam displacer orientation wrong — no matching parallel displaced beam. Beams remain separate.")
                                # Invalid combiners neither merge rays nor apply
                                # a fictitious reference loss to an optical path.
                                out = replace(state)
                            else:
                                lane = matches[0]
                                other = replace(lane["state"],position=state.position,azimuth=state.azimuth,elevation=state.elevation)
                                lane.update(state=optic_budget(other,optic,event_id+":B"),combined=True)
                                warnings.append(optic["label"]+": combined geometry; main and secondary arm budgets remain separate. No interference or polarization is calculated.")
                                if not same_envelope(state,other):
                                    warnings.append(optic["label"]+": the combined beams have different envelopes; both envelopes are shown on the common axis.")
                        else:
                            if companions:
                                raise LayoutError("This line already carries a paired beam. Continue an output endpoint in a separate line before another splitting prism/displacer.")
                            secondary = optic_budget(prism_output(state,token,True),optic,event_id,"R")
                            lane = dict(id=key+":B",state=secondary,combined=False,trace_start=trace_start,
                                        start_state=copy.deepcopy(start_state),last_segment=None)
                            companions.append(lane)
                            for suffix, ray, kind, label in (("A",out,"primary","main output"),("B",secondary,"secondary","secondary output")):
                                portname = optic["label"]+" · "+label
                                ports.append(dict(id=key+":"+suffix,name=portname,state=asdict(ray),endpoint=encode_endpoint(ray,portname),
                                                  stats=ray.stats(),kind=kind,trace_start=trace_start,start_state=start_state))
                            if token["kind"] == "bd" and token["amount"]+2*state.radius > optic["crystal_width_mm"]:
                                warnings.append(optic["label"]+": displaced beam pair may exceed the crystal clear aperture; beams are not clipped.")
                        state = out
                        pending = None
                    elif token["kind"] in ("bs", "bsc"):
                        ports.append(dict(id=key+":R", name=optic["label"]+" · reflected", state=asdict(out),
                                          endpoint=encode_endpoint(out, optic["label"]+" · reflected"),
                                          stats=out.stats(), kind="reflected", trace_start=trace_start,
                                          start_state=start_state))
                        state = optic_budget(displaced(state, optic["transmission_offset"]), optic, event_id, "T")
                        if norm(optic["transmission_offset"]) > EPS: pending = None
                    else:
                        if token["kind"] in ("mirror", "oap") and row_segments:
                            last = next((s for s in reversed(row_segments) if not s.get("secondary")), row_segments[-1])
                            end = last["state"].propagated(last["length"])
                            if norm(sub(end.position, state.position)) < 1e-7:
                                if last["trim_end"]:
                                    warnings.append(optic["label"]+": coincident reflectors may overlap; the incoming and outgoing ends use their respective first/last planes.")
                                else:
                                    last["trim_end"] = optic
                        state = out
                    if token["kind"] not in PRISMS:
                        for lane in companions:
                            if lane["combined"]:
                                _, ray = _optic(lane["state"],token,key,settings,sizes)
                                if token["kind"] in ("bs","bsc"):
                                    ray = displaced(lane["state"], optic["transmission_offset"]) # paired histories follow transmission
                                lane["state"] = optic_budget(ray,optic,event_id+":B","T" if token["kind"] in ("bs","bsc") else "")
                                if lane["last_segment"] and token["kind"] in ("mirror","oap"):
                                    lane["last_segment"]["trim_end"] = optic
                            else:
                                warnings.append(optic["label"]+": this optic acts on the main beam only. The secondary beam continues independently; use its endpoint for its own optics.")
                    pending = optic if token["kind"] in ("mirror", "oap") else None if token["kind"] == "tp" and norm(optic["transmission_offset"]) > EPS else pending
                state = state_from_dict(asdict(state))
                for lane in companions: lane["state"] = state_from_dict(asdict(lane["state"]))
                steps.append(dict(id=key, label=step_label, token=token, command=token["raw"], secondary=[lane["state"].stats() for lane in companions], **state.stats()))
            except LayoutError as exc:
                raise LayoutError(str(exc), ri, ti, token["start"], token["end"]) from exc
        previous = state
        previous_companions = copy.deepcopy(companions)
        endname = name+(" · combined end (main arm)" if companions and companions[0]["combined"] else " · end")
        endpoint = dict(id=rid+":end", name=endname, state=asdict(state),
                        endpoint=encode_endpoint(state, endname), stats=state.stats(), kind="end",
                        trace_start=trace_start, start_state=start_state)
        for index,lane in enumerate(companions):
            ray = lane["state"]
            endname = name+(" · combined end (secondary arm)" if lane["combined"] else " · secondary end")
            ports.append(dict(id=rid+":end:B"+str(index+1),name=endname,state=asdict(ray),endpoint=encode_endpoint(ray,endname),
                              stats=ray.stats(),kind="end",trace_start=lane["trace_start"],start_state=lane["start_state"]))
        endpoints.extend(ports+[endpoint])
        row_results.append(dict(id=rid, name=name, length_mm=state.path_mm-start_path,
                                endpoint=endpoint, ports=ports, steps=steps, start_state=start_state))
        all_segments.extend(row_segments); all_optics.extend(row_optics)
    if not all_segments:
        warnings.append("No propagation length: only optics and endpoint records will be created.")
    index = command_index(config)
    for endpoint in endpoints: endpoint.update(describe_endpoint(endpoint, index))
    return dict(config=config, rows=row_results, segments=all_segments, optics=all_optics,
                endpoints=endpoints, warnings=list(dict.fromkeys(warnings)))


def command_index(config):
    """Map trace identities to entered commands without modifying saved traces."""
    result = {}
    for ri, row in enumerate(config.get("rows", [])):
        tokens = parse_commands(row.get("commands", ""), ri)
        ids = row.get("step_ids", [str(i) for i in range(len(tokens))])
        for i, (token, sid) in enumerate(zip(tokens, ids)):
            key = str(config.get("route_id", "draft"))+":"+row["id"]+":"+sid
            result[key] = dict(command=token["raw"], kind=token["kind"],
                               label=row.get("step_labels", {}).get(sid) or token["raw"], row=ri, step=i)
    return result


def describe_endpoint(endpoint, index):
    included = []
    for event in endpoint.get("state", {}).get("trace", [])[endpoint.get("trace_start", 0):]:
        event_id = event["id"]
        # Step identity has three colon-separated fields; propagation and paired
        # ray suffixes follow. T/R are the only suffixes on the step field.
        base = ":".join(event_id.split(":")[:3])
        port = ""
        if base not in index and base.endswith(("_t", "_r")):
            port, base = base[-1].upper(), base[:-2]
        meta = index.get(base)
        if meta:
            if not port and event_id.endswith((":B_t", ":B_r")): port = event_id[-1].upper()
            included.append(dict(event, **meta, port=port))
    commands = " ".join(e["command"]+(" ["+e["port"]+"]" if e["port"] else "") for e in included)
    return dict(included=included, included_commands=commands)


def public_plan(plan):
    result = {k: plan[k] for k in ("rows", "optics", "endpoints", "warnings")}
    result["lines"] = [dict(start=s["state"].position,
                            end=s["state"].propagated(s["length"]).position,
                            row=s["row"], secondary=bool(s.get("secondary")),
                            event_ids=s.get("event_ids", []), color=s["state"].color,
                            diameter_start_mm=2*s["state"].radius,
                            diameter_end_mm=2*s["state"].propagated(s["length"]).radius)
                       for s in plan["segments"]]
    return result


def snapshot_config(plan):
    """Pin the representations actually built, so future defaults cannot alter them."""
    config = copy.deepcopy(plan["config"])
    for row in config.get("rows", []):
        row.pop("starter_step_id", None)
    config["optic_overrides"] = {}
    for optic in plan["optics"]:
        settings = copy.deepcopy(optic["settings"])
        settings["budget"] = copy.deepcopy(optic["budget"])
        settings.update(token=optic["token"], representation="custom" if settings["custom"] else "builtin")
        config["optic_overrides"][optic["id"]] = settings
    return config


def custom_transform(optic):
    settings = optic["settings"]
    shift = vec(settings.get("shift", [0, 0, 0]))
    rotation = vec(settings.get("rotation", [0, 0, 0]))
    reference = vec(settings.get("reference", [0, 0, 0]))
    basis = tuple(tuple(a) for a in optic["frame"])
    rotated = rotated_columns(basis, rotation[0], rotation[1], rotation[2]+(180 if optic.get("visual_flip") else 0))
    origin = sub(add(optic["position"], world(basis, shift)), world(rotated, reference))
    return origin, rotated
