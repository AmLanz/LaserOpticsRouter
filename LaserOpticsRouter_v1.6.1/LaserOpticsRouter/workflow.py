"""Small, Fusion-independent workflow utilities. No cached native entities."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

try:
    from . import core
except ImportError:
    import core


class PlanCache:
    """One bounded pure-Python entry, copied at the boundary for safe callers."""
    def __init__(self):
        self.key = self.plan = None

    def get(self, config):
        key = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if self.key != key:
            plan = core.plan_layout(config)
            self.key, self.plan = key, plan
        return copy.deepcopy(self.plan)

    def clear(self):
        self.key = self.plan = None


class DraftStore:
    """Atomic, per-document local recovery; never modifies the CAD document."""
    LIMIT = 12_000_000

    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else Path.home()/".LaserOpticsRouter"/"drafts"

    def path(self, key):
        return self.directory/(hashlib.sha256(str(key).encode()).hexdigest()+".json")

    def load(self, key):
        path = self.path(key)
        if not path.exists(): return None
        if path.stat().st_size > self.LIMIT: raise core.LayoutError("Recovery draft exceeds 12 MB.")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("config"), dict):
            raise core.LayoutError("Recovery draft format is invalid.")
        return data

    def save(self, key, config, edit_target=None):
        # Syntax errors are valid drafts: do not run the optical solver here.
        data = dict(schema=1, saved_at=time.time(), config=config, edit_target=edit_target)
        text = json.dumps(data, allow_nan=False, ensure_ascii=False)
        if len(text.encode("utf-8")) > self.LIMIT: raise core.LayoutError("Recovery draft exceeds 12 MB; export the route instead.")
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="draft-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path(key))
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
        return data["saved_at"]

    def discard(self, key):
        self.path(key).unlink(missing_ok=True)


def wire_geometry(plan):
    """Bounded line pairs for draft preview: no BRep, booleans or CAD copies.

    Optical rings are nominal interaction planes, not custom CAD envelopes.
    Four sampled envelope rails show the paraxial beam and geometric waists.
    """
    groups = {"beam": [], "envelope": [], "optic": []}
    for segment in plan["segments"]:
        state, length = segment["state"], segment["length"]
        end = state.propagated(length)
        suffix = "" if state.color == "red" else "-"+state.color
        groups.setdefault("beam"+suffix, []).extend((state.position, end.position))
        distances = {0, length} if state.model == "geometric" else {length*i/16 for i in range(17)}
        if state.model == "geometric" and state.slope:
            waist = -state.y/state.slope
            if 0 < waist < length: distances.add(waist)
        elif state.model == "gaussian":
            waist = state.stats()["waist_distance_mm"]
            if 0 < waist < length: distances.add(waist)
        basis = core.frame(state.d)
        samples = [state.propagated(d) for d in sorted(distances)]
        for axis in basis[:2]:
            for sign in (-1, 1):
                points = [core.add(s.position, core.mul(axis, sign*s.radius)) for s in samples]
                for a, b in zip(points, points[1:]): groups.setdefault("envelope"+suffix, []).extend((a, b))
        if sum(len(v) for k,v in groups.items() if k.startswith("envelope")) > 260000:
            raise core.LayoutError("Draft preview is too large. Divide this layout into smaller routes.")
    for optic in plan["optics"]:
        origin, axes = optic["position"], core.frame(optic["normal"])
        radius = optic["diameter_mm"]/2
        if optic.get("shape") == "cube":
            for axis in range(3):
                other = [i for i in range(3) if i != axis]
                for a in (-radius,radius):
                    for b in (-radius,radius):
                        start, end = [0,0,0], [0,0,0]
                        for p in (start,end): p[other[0]],p[other[1]] = a,b
                        start[axis],end[axis] = -radius,radius
                        groups["optic"].extend(core.add(origin,core.world(axes,p)) for p in (start,end))
        else:
            for a,b in (((0,1),(1,2),(2,0)) if optic.get("shape") == "ball" else ((0,1),)):
                ring = []
                for i in range(25):
                    p = [0,0,0];p[a],p[b] = radius*math.cos(i*math.pi/12),radius*math.sin(i*math.pi/12)
                    ring.append(core.add(origin,core.world(axes,p)))
                for p,q in zip(ring,ring[1:]): groups["optic"].extend((p,q))
        groups["optic"].extend((origin, core.add(origin, core.mul(optic["output_direction"], min(10, radius)))))
    return groups
