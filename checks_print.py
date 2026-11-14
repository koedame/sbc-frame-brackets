"""造形可否の検査。形状を層ごとに輪切りにし、各層が1層下の輪郭から45度以内に収まるかを調べる。
面の向きだけを見る検査と違い、宙から始まる部分(垂れ下がるリップなど)も検出する。"""
import numpy as np, trimesh
from shapely.ops import unary_union

LAYER = 0.2


def unsupported(shape, rot=None, layer=LAYER):
    """戻り値: (支えの無い面積の合計[mm2], 1層での最大値[mm2])。rot は造形向きへの回転(Z が上)"""
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
            ar = sum(g.area for g in getattr(bad, 'geoms', [bad]) if g.area > 0.05)   # 数値誤差の細片は無視
            total += ar; worst = max(worst, ar)
        elif prev is None and cur is not None and sec is not secs[0]:
            total += cur.area; worst = max(worst, cur.area)
        prev = cur
    return round(total, 1), round(worst, 1)
