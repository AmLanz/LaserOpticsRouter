"""Standalone router schematic export. Keep symbols in parity with schematic.js.

No browser, JavaScript runtime, CAD objects or network are needed by Fusion.
Beam coordinates are preserved in SVG data attributes; glyphs are not to scale.
"""
import copy
import math
from html import escape
try:
    from . import core
except ImportError:
    import core


def n(value):
    return format(round(value, 4) or 0, '.12g')


def xy(p, axes): return p[axes[0]], -p[axes[1]]
def angle(v): return math.degrees(math.atan2(v[1], v[0]))
def rotate(a, body): return f'<g transform="rotate({n(a)})">{body}</g>'
BASE = 'stroke="#344e61" stroke-width="1.7" stroke-linejoin="round"'


def label_position(point, text, width, height, occupied):
    """Keep coincident return-pass and neighboring optic labels readable."""
    x,y=point;size=6*len(text)
    sides=(-1,1) if x+16+size>width-5 else (1,-1)
    for side in sides:
        for offset in (-19,24,-36,41,-53,58):
            anchor=x+side*16;baseline=y+offset
            box=(anchor-size if side<0 else anchor,baseline-11,
                 anchor if side<0 else anchor+size,baseline+2)
            if box[0]<5 or box[2]>width-5 or box[1]<5 or box[3]>height-30:continue
            if any(box[0]<b[2]+3 and box[2]>b[0]-3 and box[1]<b[3]+3 and box[3]>b[1]-3 for b in occupied):continue
            occupied.append(box)
            return side*16,offset,side<0
    return (-16 if x>width-95 else 16),-19,x>width-95


def symbol(o, axes):
    a = angle(xy(o.get('input_direction', [1,0,0]), axes))
    normal = xy(o.get('normal', [1,0,0]), axes)
    t = angle((-normal[1], normal[0]))
    kind = o['kind']
    def line(d, w): return rotate(d, f'<path d="M-15 0 H15" fill="none" stroke="#344e61" stroke-width="{w}"/>')
    if kind == 'lens':
        path = 'M-6 -15 Q2 0 -6 15 L6 15 Q-2 0 6 -15 Z' if o['focal_mm'] < 0 else 'M0 -15 Q13 0 0 15 Q-13 0 0 -15 Z'
        return rotate(a, f'<path d="{path}" fill="#d8edf2" {BASE}/>')
    if kind == 'cyl': return rotate(a, f'<rect x="-6" y="-15" width="12" height="30" rx="5" fill="#d8edf2" {BASE}/><path d="M-3 -10 V10 M3 -10 V10" stroke="#5b92a2"/><text x="8" y="-7" font-size="9">{escape(o.get("axis","h"))}</text>')
    if kind == 'grating': return rotate(t, f'<rect x="-16" y="-3" width="32" height="6" fill="#d8bc82" {BASE}/><path d="M-12 -3 V3 M-8 -3 V3 M-4 -3 V3 M0 -3 V3 M4 -3 V3 M8 -3 V3 M12 -3 V3" stroke="#725829"/>')
    if kind == 'reset': return rotate(a, f'<rect x="-3" y="-15" width="6" height="30" fill="#c0e2d4" {BASE}/><path d="M-8 -9 L-3 -4 L-8 1 M3 -1 L8 4 L3 9" fill="none" stroke="#2a6954"/>')
    if kind == 'mirror': return rotate(t, f'<rect x="-15" y="-2.5" width="30" height="5" rx=".5" fill="#8c9ba7" {BASE}/><path d="M-15 -3 H15" stroke="#162f43" stroke-width="1.7"/>')
    # Local -Y faces the optical normal; the concave face meets the ray at (0,0).
    if kind == 'oap': return rotate(t, f'<path d="M-15 -5 Q0 5 15 -5 L15 -2 Q0 8 -15 -2 Z" fill="#d7b373" {BASE}/>')
    if kind == 'bs': return line(t, 1.8)
    if kind == 'tp': return rotate(t, f'<rect x="-15" y="-2" width="30" height="4" fill="#d8e8ef" {BASE}/>')
    if kind in ('laha','laqu','nd'):
        x, w, fill = (-3,6,'#8997a5') if kind == 'nd' else (-1.5,3,'#c6dfe4')
        return rotate(a, f'<rect x="{x}" y="-14" width="{w}" height="28" rx=".6" fill="{fill}" {BASE}/>')
    if kind == 'bsc':
        r = math.radians(t-a); c, s = math.cos(r), math.sin(r); m = 13/max(abs(c),abs(s))
        return rotate(a, f'<rect x="-13" y="-13" width="26" height="26" fill="#e0edfa" {BASE}/><path d="M{n(-c*m)} {n(-s*m)} L{n(c*m)} {n(s*m)}" stroke="#326d9f" stroke-width="1.8"/>')
    if kind in ('wp','rp','bd'):
        transverse, forward = xy(o['frame'][0],axes), xy(o['input_direction'],axes)
        side = 1 if forward[0]*transverse[1]-forward[1]*transverse[0] > 0 else -1
        shape = '<path d="M-18 -12 H10 L18 12 H-10 Z"/>' if kind == 'bd' else '<rect x="-17" y="-12" width="34" height="24"/>'
        seam = '<path d="M-12 -4 H1 L9 4 H14" stroke="#567d86"/>' if kind == 'bd' else '<path d="M-17 12 L17 -12" stroke="#567d86"/>'
        marks = {'wp':'<circle cx="-7" cy="-5" r="3"/><circle cx="-7" cy="-5" r=".7" fill="#344e61"/><path d="M7 0 V9 M4 3 L7 0 L10 3 M4 6 L7 9 L10 6"/>',
                 'rp':'<circle cx="-8" cy="-4" r="3"/><circle cx="-8" cy="-4" r=".7" fill="#344e61"/><path d="M8 0 V9 M5 3 L8 0 L11 3 M5 6 L8 9 L11 6"/>',
                 'bd':'<circle cx="-7" cy="4" r="2.7"/><circle cx="-7" cy="4" r=".7" fill="#344e61"/><path d="M7 -9 V-1 M4 -6 L7 -9 L10 -6 M4 -4 L7 -1 L10 -4"/>'}[kind]
        return rotate(a, f'<g transform="scale(1 {side})" {BASE}><g fill="#e1eee8">{shape}</g><g fill="none">{seam}{marks}</g></g>')
    if kind == 'generic':
        shape = o.get('shape',o.get('settings',{}).get('shape','disc'))
        if shape == 'ball': return f'<circle r="12" fill="#eee7f4" {BASE}/>'
        if shape == 'cube': return rotate(a, f'<rect x="-12" y="-12" width="24" height="24" fill="#eee7f4" {BASE}/>')
        return line(a+90,2.4)
    if kind == 'pol': return rotate(a, f'<rect x="-4" y="-14" width="8" height="28" fill="#e3e8ec" {BASE}/><path d="M-4 -8 L4 -12 M-4 0 L4 -4 M-4 8 L4 4" stroke="#708493"/>')
    return f'<path d="M0 -10 L10 0 L0 10 L-10 0 Z" fill="white" {BASE}/>'


def moved_optic(optic, origin, axes):
    o = copy.deepcopy(optic)
    o['position'] = core.add(origin,core.world(axes,o['position']))
    for key in ('normal','input_direction','output_direction','transmission_offset'):
        if key in o: o[key] = core.world(axes,o[key])
    if 'transmission_position' in o: o['transmission_position'] = core.add(origin,core.world(axes,o['transmission_position']))
    o['frame'] = [core.world(axes,v) for v in o['frame']]
    if o.get('cad_frame'): o['cad_frame'] = [core.world(axes,v) for v in o['cad_frame']]
    return o


def render(plan, projection='XY', transform=None):
    if projection not in ('XY','XZ','YZ'): raise core.LayoutError('Choose XY, XZ or YZ projection.')
    axes = {'XY':(0,1),'XZ':(0,2),'YZ':(1,2)}[projection]
    optics = [moved_optic(o,*transform) if transform else o for o in plan['optics']]
    lines = []
    for s in plan['segments']:
        state = core.moved_state(s['state'],*transform) if transform else s['state']
        lines.append(dict(start=state.position,end=state.propagated(s['length']).position,
                          color=state.color,secondary=s.get('secondary'),name=s['name'],spectral=bool(s.get('spectral')),spectral_weight=state.spectral_weight,wavelength_nm=state.wavelength_nm))
    pts = [xy(p,axes) for l in lines for p in (l['start'],l['end'])]+[xy(o['position'],axes) for o in optics] or [(0,0)]
    lo, hi = [min(p[i] for p in pts) for i in (0,1)], [max(p[i] for p in pts) for i in (0,1)]
    w, h = 900,320
    scale = min((w-100)/max(hi[0]-lo[0],30),(h-100)/max(hi[1]-lo[1],30))
    cx,cy = (lo[0]+hi[0])/2,(lo[1]+hi[1])/2
    def project(p):
        x,y=xy(p,axes)
        return w/2+(x-cx)*scale,h/2+(y-cy)*scale
    raw = 50/scale; power = 10**math.floor(math.log10(raw))
    grid = next(v*power for v in (1,2,5,10) if v*power >= raw)
    step = grid*scale; gx,gy = project((0,0,0))
    title = escape(plan['config'].get('run_name','LaserOpticsRouter')+' · '+projection)
    out = [f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="900" height="320" viewBox="0 0 900 320" role="img" class="optical-map"><title>{title}</title><desc>Router schematic. Grid in millimetres; optic symbols are not to scale. Polarization marks are reference annotations only. Beam data-world-start/end attributes preserve XYZ in millimetres.</desc><rect width="900" height="320" fill="#fbfcfd"/>']
    x=gx%step
    while x<w:
        out.append(f'<path d="M{n(x)} 0 V{h}" stroke="#e8edf1" stroke-width="1"/>');x+=step
    y=gy%step
    while y<h:
        out.append(f'<path d="M0 {n(y)} H{w}" stroke="#e8edf1" stroke-width="1"/>');y+=step
    for l in lines:
        a,b=project(l['start']),project(l['end']);paint=core.BEAM_COLORS[l['color']]
        weight=l.get('spectral_weight',1)
        if l.get('spectral'): out.append(f'<g opacity="{n(max(.14,math.sqrt(weight)))}">')
        d=f'M{n(a[0])},{n(a[1])} L{n(b[0])},{n(b[1])}'
        outline='#53677a' if paint=='#ffffff' else '#fff'
        dash='stroke-dasharray="6 3"' if l['secondary'] else ''
        out.append(f'<path d="{d}" fill="none" stroke="{outline}" stroke-width="4.5"/>')
        label=l['name']+(f' · {l["wavelength_nm"]:g} nm · relative weight {weight:g}' if l.get('spectral') else '')
        out.append(f'<line class="beam" x1="{n(a[0])}" y1="{n(a[1])}" x2="{n(b[0])}" y2="{n(b[1])}" data-world-start="{",".join(format(v,".15g") for v in l["start"])}" data-world-end="{",".join(format(v,".15g") for v in l["end"])}" data-wavelength-nm="{l["wavelength_nm"]:g}" data-spectral-weight="{weight:g}" stroke="{paint}" stroke-width="2.2" {dash}><title>{escape(label)}</title></line>')
        dx,dy=b[0]-a[0],b[1]-a[1]
        if math.hypot(dx,dy)>32:
            stroke='#53677a' if paint=='#ffffff' else paint
            out.append(f'<path d="M-5 -3 L2 0 L-5 3" transform="translate({n(a[0]+dx*.68)} {n(a[1]+dy*.68)}) rotate({n(angle((dx,dy)))})" fill="none" stroke="{stroke}" stroke-width="1.8"/>')
        if l.get('spectral'): out.append('</g>')
    occupied=[]
    for i,o in enumerate(optics,1):
        p=project(o['position']);text=f'{i} · {o["token"]}'
        label_x,label_y,left=label_position(p,text,w,h,occupied)
        mark=' — polarization marks are schematic references only' if o['kind'] in core.PRISMS else ''
        out.append(f'<g class="map-optic" data-kind="{escape(o["kind"])}" transform="translate({n(p[0])},{n(p[1])})">{symbol(o,axes)}<text x="{label_x}" y="{label_y}" text-anchor="{"end" if left else "start"}" font-size="10" font-family="sans-serif" fill="#23435a" paint-order="stroke" stroke="#fbfcfd" stroke-width="3">{escape(text)}</text><title>{escape(o["label"]+mark)}</title></g>')
    out.append(f'<rect x="0" y="{h-25}" width="{w}" height="25" fill="#fbfcfd" fill-opacity=".94"/><text x="12" y="{h-9}" font-size="11" font-family="sans-serif" fill="#516676">{projection} · grid {n(grid)} mm · 100% · symbols not to scale</text></svg>')
    return ''.join(out)
