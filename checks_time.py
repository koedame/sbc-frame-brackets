"""印刷時間の見積もり(比較用)。造形姿勢の形状を 0.2mm ごとに輪切りにし、外周・内周・面の塗りつぶし・移動を積算する。
スライサーの実測ではない。同じ条件で形どうしを比べるための値。"""
import numpy as np, trimesh
from shapely.ops import unary_union

LAYER, LW = 0.2, 0.45
V = dict(first=25.0, outer=45.0, inner=80.0, solid=90.0, sparse=120.0)   # mm/s (PETG の一般的な設定を仮定)
WALLS, SHELL, DENS = 2, 4, 0.15          # 壁2周、上下の密な層4枚、内部充填15%
T_ISLAND, T_LAYER = 0.9, 0.4             # 島1つあたりの移動と引き戻し[s]、層替え[s]
ACC = 2500.0                             # 加速度[mm/s2]。短い線分ほど最高速に届かない


def _move(length, v, seg):
    """長さ length を平均線分長 seg で走る時間。加減速ぶんを足す"""
    if length <= 0: return 0.0
    n = max(length / max(seg, 0.5), 1.0)
    return length / v + n * v / ACC


def estimate(shape, rot=None):
    s = rot * shape if rot is not None else shape
    v, t = s.tessellate(0.03)
    m = trimesh.Trimesh(np.array([(p.X, p.Y, p.Z) for p in v]), np.array(t), process=True)
    z0, z1 = m.bounds[0][2], m.bounds[1][2]
    hs = np.arange(LAYER / 2, z1 - z0, LAYER)
    secs = m.section_multiplane([0, 0, z0], [0, 0, 1], hs)
    polys = [unary_union([p.buffer(0) for p in sec.polygons_full]) if sec is not None else None for sec in secs]
    tot = dict(wall=0.0, fill=0.0, travel=0.0); fil = 0.0
    for k, P in enumerate(polys):
        if P is None or P.is_empty: continue
        geoms = list(getattr(P, "geoms", [P]))
        inner = P
        for w in range(WALLS):
            ring = P.buffer(-LW * (w + 0.5))
            if ring.is_empty: break
            L = ring.length; nseg = sum(len(g.exterior.coords) + sum(len(i.coords) for i in g.interiors) for g in getattr(ring, "geoms", [ring]))
            vv = V["first"] if k == 0 else (V["outer"] if w == 0 else V["inner"])
            tot["wall"] += _move(L, vv, L / max(nseg, 1) * 3); fil += L
        inner = P.buffer(-LW * WALLS)
        if not inner.is_empty:
            lo = polys[k - SHELL] if k - SHELL >= 0 else None; hi = polys[k + SHELL] if k + SHELL < len(polys) else None
            core = inner.intersection(lo).intersection(hi) if (lo is not None and hi is not None) else inner.difference(inner)
            solid_a = inner.area - core.area; sparse_a = core.area
            vv = V["first"] if k == 0 else V["solid"]
            tot["fill"] += _move(solid_a / LW, vv, 12.0) + _move(sparse_a * DENS / LW, V["sparse"], 8.0)
            fil += solid_a / LW + sparse_a * DENS / LW
        tot["travel"] += len(geoms) * T_ISLAND + T_LAYER
    sec_total = sum(tot.values())
    return dict(min=round(sec_total / 60, 1), wall=round(tot["wall"] / 60, 1), fill=round(tot["fill"] / 60, 1), travel=round(tot["travel"] / 60, 1),
                layers=len(polys), g=round(fil * LW * LAYER * 1.27 / 1000, 1))
