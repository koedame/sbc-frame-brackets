"""Printability check. Slices the shape layer by layer and checks that each layer stays within 45 degrees of the outline of the layer below.
Unlike a check that only looks at face angles, this also catches parts that start in mid-air (such as a hanging lip)."""
import numpy as np, trimesh
from shapely.ops import unary_union

LAYER = 0.2


def unsupported(shape, rot=None, layer=LAYER):
    """Returns (total unsupported area [mm2], largest unsupported area in a single layer [mm2]). rot rotates the shape into print orientation (Z up)"""
    s = rot * shape if rot is not None else shape
    v, t = s.tessellate(0.02)
    m = trimesh.Trimesh(np.array([(p.X, p.Y, p.Z) for p in v]), np.array(t), process=True)
    z0, z1 = m.bounds[0][2], m.bounds[1][2]
    hs = np.arange(layer / 2, z1 - z0, layer)
    secs = m.section_multiplane([0, 0, z0], [0, 0, 1], hs)
    prev, total, worst = None, 0.0, 0.0
    for sec in secs:
        cur = unary_union([p.buffer(0) for p in sec.polygons_full]) if sec is not None else None
        if prev is not None and cur is not None:
            bad = cur.difference(prev.buffer(layer + 0.03))
            ar = sum(g.area for g in getattr(bad, 'geoms', [bad]) if g.area > 0.05)   # ignore slivers from numerical error
            total += ar; worst = max(worst, ar)
        elif prev is None and cur is not None and sec is not secs[0]:
            total += cur.area; worst = max(worst, cur.area)
        prev = cur
    return round(total, 1), round(worst, 1)
