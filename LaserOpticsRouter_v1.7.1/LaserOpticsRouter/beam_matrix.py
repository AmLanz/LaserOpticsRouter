"""Paraxial second moments in local (horizontal, vertical, h slope, v slope).

Spatial block eigenvalues are squared envelope radii (Gaussian: 1/e²).
Only activated for anisotropic optics; the legacy scalar solver stays intact.
All transformations use S' = T S Tᵀ, including transported beam frames.
"""
import math


def identity(n=4):
    return [[float(i == j) for j in range(n)] for i in range(n)]


def transform(s, t):
    # Transform amplitudes of a PSD factor, then form their Gram matrix. Direct
    # T S Tᵀ subtracts large variances at a focus and can produce negative widths.
    scale=[math.sqrt(max(0,s[i][i])) for i in range(4)]
    a=[[s[i][j]/(scale[i]*scale[j]) if scale[i]*scale[j] else 0 for j in range(4)] for i in range(4)]
    l=[[0.0]*4 for _ in range(4)];remaining=list(range(4))
    for k in range(4):
        residual={i:a[i][i]-sum(l[i][j]**2 for j in range(k)) for i in remaining}
        p=max(remaining,key=lambda i:residual[i]);pivot=residual[p]
        if pivot<1e-14:break
        l[p][k]=math.sqrt(pivot);remaining.remove(p)
        for i in remaining:
            l[i][k]=(a[i][p]-sum(l[i][j]*l[p][j] for j in range(k)))/l[p][k]
    factor=[[sum(t[i][j]*scale[j]*l[j][k] for j in range(4)) for k in range(4)] for i in range(4)]
    for i in range(4):
        for k in range(4):
            bound=sum(abs(t[i][j]*scale[j]*l[j][k]) for j in range(4))
            if abs(factor[i][k])<4e-14*bound:factor[i][k]=0.0
    return [[sum(factor[i][k]*factor[j][k] for k in range(4)) for j in range(4)] for i in range(4)]


def seed(state):
    if state.moments:
        return [list(row) for row in state.moments]
    r, slope = state.radius, state.radial_slope
    angular = slope*slope + ((state.beta/r)**2 if state.model == 'gaussian' else 0)
    # At a geometric focus the signed ray height is zero but divergence remains.
    s = [[0.0]*4 for _ in range(4)]
    for i in range(2):
        s[i][i], s[i][i+2], s[i+2][i], s[i+2][i+2] = r*r, r*slope, r*slope, angular
    return s


def propagate(s, distance):
    t = identity()
    t[0][2] = t[1][3] = distance
    return transform(s, t)


def focus(s, focal, axis=None):
    t = identity()
    for i in ((0, 1) if axis is None else (axis,)):
        t[i+2][i] = -1/focal
    return transform(s, t)


def axes_transform(s, position, slope=None):
    """2×2 position/slope maps, in transverse coordinate frames."""
    slope = position if slope is None else slope
    t = [[0.0]*4 for _ in range(4)]
    for i in range(2):
        for j in range(2):
            t[i][j], t[i+2][j+2] = position[i][j], slope[i][j]
    return transform(s, t)


def ellipse(s):
    a, b, c = max(0, s[0][0]), (s[0][1]+s[1][0])/2, max(0, s[1][1])
    gap = math.hypot(a-c, 2*b)
    high = max(0, (a+c+gap)/2)
    # Determinant form avoids cancellation for very narrow line foci.
    low = max(0, (a*c-b*b)/high) if high else 0
    angle = math.atan2(2*b, a-c)/2 if gap > 1e-20 else 0
    return math.sqrt(high), math.sqrt(low), angle


def ring(s, count=48, floor=0):
    """Continuous symmetric square-root parameterization, stable at axis swaps."""
    major, minor, a = ellipse(s)
    major, minor = max(floor, major), max(floor, minor)
    c, z = math.cos(a), math.sin(a)
    root = ((major*c*c+minor*z*z, (major-minor)*c*z),
            ((major-minor)*c*z, major*z*z+minor*c*c))
    return [(root[0][0]*math.cos(t)+root[0][1]*math.sin(t),
             root[1][0]*math.cos(t)+root[1][1]*math.sin(t))
            for t in (2*math.pi*i/count for i in range(count))]


def waists(s):
    return [-s[i][i+2]/s[i+2][i+2] for i in range(2) if s[i+2][i+2] > 1e-30]


def knots(s, length, tolerance=.01):
    """Subdivide on actual ellipse boundary error; retain both projected waists."""
    points = sorted({0.0, length, *(t for t in waists(s) if 0 < t < length)})
    result = [0.0]
    def refine(a, b, depth=0):
        m = (a+b)/2
        ra, rb, rm = (ring(propagate(s,t), 16) for t in (a,b,m))
        error = max(math.hypot((p[0]+q[0])/2-r[0], (p[1]+q[1])/2-r[1]) for p,q,r in zip(ra,rb,rm))
        if error > tolerance and depth < 14:
            refine(a,m,depth+1); refine(m,b,depth+1)
        else:
            result.append(b)
    for a,b in zip(points,points[1:]): refine(a,b)
    return result


def validate(s):
    if not isinstance(s, (list, tuple)) or len(s) != 4 or any(not isinstance(r,(list,tuple)) or len(r)!=4 for r in s):
        raise ValueError('Beam moments must be a 4×4 matrix.')
    s = [[float(v) for v in row] for row in s]
    if not all(math.isfinite(v) for r in s for v in r):
        raise ValueError('Beam moments must be finite.')
    # Normalize units, then use symmetric Jacobi eigenvalues. Unpivoted
    # semidefinite Cholesky is unstable for transported geometric line foci.
    scale = [math.sqrt(max(abs(s[i][i]), 1e-30)) for i in range(4)]
    a = [[s[i][j]/(scale[i]*scale[j]) for j in range(4)] for i in range(4)]
    for i in range(4):
        for j in range(i+1):
            if abs(a[i][j]-a[j][i]) > 1e-6: raise ValueError('Beam moments must be symmetric.')
            a[i][j]=a[j][i]=(a[i][j]+a[j][i])/2
    for _ in range(60):
        p,q=max(((i,j) for i in range(4) for j in range(i+1,4)),key=lambda ij:abs(a[ij[0]][ij[1]]))
        if abs(a[p][q])<1e-12:break
        theta=.5*math.atan2(2*a[p][q],a[q][q]-a[p][p]);c,z=math.cos(theta),math.sin(theta)
        app,aqq,apq=a[p][p],a[q][q],a[p][q]
        for i in range(4):
            if i in (p,q):continue
            aip,aiq=a[i][p],a[i][q]
            a[i][p]=a[p][i]=c*aip-z*aiq;a[i][q]=a[q][i]=z*aip+c*aiq
        a[p][p]=c*c*app-2*c*z*apq+z*z*aqq
        a[q][q]=z*z*app+2*c*z*apq+c*c*aqq;a[p][q]=a[q][p]=0
    if min(a[i][i] for i in range(4)) < -1e-6:raise ValueError('Invalid negative beam variance.')
    return s
