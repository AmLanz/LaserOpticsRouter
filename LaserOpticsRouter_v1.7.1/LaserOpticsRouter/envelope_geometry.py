"""Bounded polygonal ellipse skins for anisotropic planning solids (mm).

The old circular cone path is deliberately separate. These are display meshes
converted to closed BRep shells, not surfaces of constant optical phase.
"""
import math
try:
    from . import core, beam_matrix
except ImportError:
    import core, beam_matrix


def skin(segment, tolerance=.01, sides=48, floor=.001):
    state, length = segment['state'], segment['length']
    distances = beam_matrix.knots(state.moments,length,tolerance)
    if len(distances) > 128:
        raise core.LayoutError('Astigmatic solid needs more than 128 cross sections. Shorten the propagation or use draft preview.')
    axes = core.beam_frame(state)
    vertices, faces = [], []
    limited = False
    for t in distances:
        s = state.propagated(t)
        limited |= beam_matrix.ellipse(s.moments)[1] < floor
        for x,y in beam_matrix.ring(s.moments,sides,floor):
            vertices.append(core.add(s.position,core.add(core.mul(axes[0],x),core.mul(axes[1],y))))
    faces.append(tuple(reversed(range(sides))))
    for ring in range(len(distances)-1):
        for j in range(sides):
            a,b = ring*sides+j, ring*sides+(j+1)%sides
            c,d = b+sides,a+sides
            faces.extend(((a,b,c),(a,c,d)))
    faces.append(tuple(range((len(distances)-1)*sides,len(distances)*sides)))
    return vertices, faces, limited
