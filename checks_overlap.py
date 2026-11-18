"""Overlaps for the interference, retention and leaf spring checks, measured twice: by OCC's boolean intersection and from triangle
meshes (manifold3d). Between solids, the volume they share (common_volume); for the parts of a board's official 3D model that are
only surfaces, the area of surface inside a solid (surface_area).
OCC's intersection can silently miss where nearly parallel flat faces overlap and return 0, part of the overlap or the whole of one
shape. A check that trusts it alone then passes interference that is there, or reports a bracket that is held as loose. The two
results may differ by what the meshes' chords move on curved faces; beyond that, the overlap is counted as a disagreement and the
model fails, whichever result would have passed."""
import numpy as np
import manifold3d as mf
import rtree
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GeomLProp import GeomLProp_SLProps
from OCP.IMeshTools import IMeshTools_MeshAlgoType_Delabella, IMeshTools_MeshAlgoType_Watson, IMeshTools_Parameters
from OCP.ShapeAnalysis import ShapeAnalysis_ShapeTolerance
from OCP.TopAbs import TopAbs_EDGE, TopAbs_IN, TopAbs_REVERSED
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Vertex
from OCP.gp import gp_Pnt
from build123d import GeomType, Shape

TOL, ANGLE = 0.02, 0.2        # mesh: chord error (mm) and angle (rad). A chord moves a curved face by at most TOL
EPS_FLAT, EPS_CURVED = 1e-3, TOL + 1e-3   # surface_area(): how far a face's thin solid reaches to each side of it (mm). A flat
                                          # face's mesh lies on the face; a curved face's mesh, and the solid's, up to TOL off it


def _matrix(loc):
    t = loc.Transformation()
    return np.array([[t.Value(r, c) for c in range(1, 5)] for r in range(1, 4)])


def _solid(solid):
    """A closed manifold3d solid from one OCC solid, or None if no mesh of it closes and holds the solid's volume (within what the
    chords move and the solid's own tolerance). Triangle i has face id 2i + 1 if it lies on a curved face, 2i if on a plane, so
    that the triangles of an intersection tell which came from curved faces.
    Triangulates with Delabella, and with BRepMesh's default (Watson) where Delabella's mesh does not close: in vendors' STEP
    files, Watson ran out of memory (over 8 GB) on a PCB face with 3,397 holes, which Delabella meshes in 14 s, and Delabella
    left most of one face of a connector open, which Watson meshes"""
    for algo in (IMeshTools_MeshAlgoType_Delabella, IMeshTools_MeshAlgoType_Watson):
        m = _mesh(solid, algo)
        if m is not None:
            return m
    return None


def _mesh(solid, algo):
    """_solid() with one triangulation algorithm. A face BRepMesh cannot mesh (a vendor's file has cylinders of no height) is left
    as a hole for _holes() to close"""
    t = _triangulate(solid, algo)
    if t is None:
        return None
    xyz, faces = t[0], [(f, m) for f, m in t[2] if m is not None]
    if not faces:
        return None
    tri = np.concatenate([m for _, m in faces])
    curved = np.concatenate([np.full(len(m), f.geom_type != GeomType.PLANE, dtype=np.uint64) for f, m in faces])
    keep = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])   # at the pole of a sphere or a cone
    tri, curved = tri[keep], curved[keep]
    m = mf.Manifold(mf.Mesh64(vert_properties=xyz, tri_verts=tri.astype(np.uint64), face_id=np.arange(len(tri), dtype=np.uint64) * 2 + curved))
    if m.status() != mf.Error.NoError:
        fill = _holes(tri)
        if fill is None:
            return None
        tri, curved = np.concatenate([tri, fill]), np.concatenate([curved, np.ones(len(fill), dtype=np.uint64)])   # counted as curved
        m = mf.Manifold(mf.Mesh64(vert_properties=xyz, tri_verts=tri.astype(np.uint64), face_id=np.arange(len(tri), dtype=np.uint64) * 2 + curved))
        if m.status() != mf.Error.NoError:
            return None
    allow = (TOL * sum(f.area for f in solid.faces() if f.geom_type != GeomType.PLANE) + 1e-3 + 1e-4 * solid.volume
             + ShapeAnalysis_ShapeTolerance().Tolerance(solid.wrapped, 1) * solid.area)
    return m if abs(m.volume() - solid.volume) <= allow else None


def _triangulate(shape, algo, apart=False):
    """Nodes (n x 3), their (u, v) on the surface of their face (n x 2, only with apart, otherwise None) and, for each face of
    shape, (face, its triangles as node indices), the triangles None where BRepMesh could not mesh the face. None if an edge has
    no nodes on the mesh of a face it bounds.
    Meshes a copy, with TOL in mm: Shape.mesh() takes the tolerance relative to the size of each edge, and leaves its mesh on the
    shape, where the print checks and the 3MF writer would then reuse it.
    Each face's mesh has its own copy of the nodes on its edges, and two faces may place an edge's node apart by up to the edge's
    tolerance (0.15 mm in a vendor's STEP file), so the copies are joined by which edge and vertex they lie on, not by position.
    With apart, they are joined only within a face (across its seam), so that each node belongs to one face"""
    shape = Shape.cast(BRepBuilderAPI_Copy(shape.wrapped, False, False).Shape())
    params = IMeshTools_Parameters()
    params.Deflection, params.Angle, params.Relative, params.InParallel = TOL, ANGLE, False, False
    params.MeshAlgo = algo
    BRepMesh_IncrementalMesh(shape.wrapped, params)
    ids, xyz, uv, faces = {}, [], [], []

    def node(key, p, q):
        if key not in ids:
            ids[key] = len(xyz)
            xyz.append(p)
            uv.append(q)
        return ids[key]

    for fi, f in enumerate(shape.faces()):
        loc = TopLoc_Location()
        poly = BRep_Tool.Triangulation_s(f.wrapped, loc)
        if poly is None:
            faces.append((f, None))
            continue
        m = _matrix(loc)
        p = np.array([(q.X(), q.Y(), q.Z()) for q in (poly.Node(i) for i in range(1, poly.NbNodes() + 1))]) @ m[:, :3].T + m[:, 3]
        q = (np.array([(x.X(), x.Y()) for x in (poly.UVNode(i) for i in range(1, poly.NbNodes() + 1))]) if apart
             else np.zeros((len(p), 0)))
        at = np.full(len(p), -1)
        ex = TopExp_Explorer(f.wrapped, TopAbs_EDGE)
        while ex.More():
            e = TopoDS.Edge(ex.Current())
            ex.Next()
            on = BRep_Tool.PolygonOnTriangulation_s(e, poly, loc)
            if on is None:
                return None
            v1, v2 = TopoDS_Vertex(), TopoDS_Vertex()
            TopExp.Vertices_s(e, v1, v2)
            last, flat = on.NbNodes(), BRep_Tool.Degenerated_s(e)
            for j in range(1, last + 1):
                key = v1.TShape() if j == 1 or flat else v2.TShape() if j == last else (e.TShape(), j)
                k = on.Node(j) - 1
                at[k] = node((fi, key) if apart else key, p[k], q[k])
        inner = at < 0
        at[inner] = np.arange(len(xyz), len(xyz) + inner.sum())
        xyz.extend(p[inner])
        uv.extend(q[inner])
        t = at[np.array([(x.Value(1), x.Value(2), x.Value(3)) for x in poly.Triangles()]) - 1]
        faces.append((f, t[:, [0, 2, 1]] if f.wrapped.Orientation() == TopAbs_REVERSED else t))
    return np.array(xyz).reshape(-1, 3), np.array(uv).reshape(-1, 2) if apart else None, faces


def _holes(tri):
    """Triangles that close the holes in a mesh, one fan per hole, or None if its open edges do not run round loops.
    BRepMesh can leave a few boundary nodes of a small face out of its triangles (a face of a vendor's STEP file whose edges lie
    0.1 mm off its surface), which leaves a hole of a fraction of a millimetre there. A loop that passes a node twice is cut there
    into two holes"""
    d = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    n = int(d.max()) + 1
    after = {}
    for a, b in d[~np.isin(d[:, 1] * n + d[:, 0], d[:, 0] * n + d[:, 1])].tolist():   # edges whose reverse no triangle has
        after.setdefault(a, []).append(b)
    fill = []
    for start in list(after):
        path, where = [start], {start: 0}
        while after[start] or len(path) > 1:
            if not after.get(path[-1]):
                return None
            b = after[path[-1]].pop()
            if b in where:
                i = where[b]
                fill += [(path[i], path[j + 1], path[j]) for j in range(i + 1, len(path) - 1)]
                for x in path[i + 1:]:
                    del where[x]
                del path[i + 1:]
            else:
                where[b] = len(path)
                path.append(b)
    return np.array(fill, dtype=tri.dtype).reshape(-1, 3)


class _Kept:
    """What is made from each shape (meshes), once per shape wherever it is placed, and kept while the shape exists: every model
    makes new brackets, whose meshes would otherwise pile up (about 4 MB a model). The entries of shapes that only this cache still
    refers to are dropped whenever it has doubled since they were last looked for: GetRefCount() takes about 0.7 ms, and looking
    at every entry before each new one took minutes with the thousands of parts of an official 3D model"""

    def __init__(self):
        self.made, self.swept = {}, 16

    def __call__(self, shape, make):
        key = shape.wrapped.TShape()
        if key not in self.made:
            if len(self.made) >= 2 * self.swept:
                for k in [k for k in self.made if k.GetRefCount() == 1]:
                    del self.made[k]
                self.swept = max(len(self.made), 16)
            self.made[key] = make(Shape.cast(shape.wrapped.Located(TopLoc_Location())))
        return self.made[key]


_MESHES, _SHEETS = _Kept(), _Kept()


def _manifold(shape):
    """shape as a manifold3d solid (None if any of its solids does not mesh closed)"""
    m = _MESHES(shape, _union)
    return None if m is None else m.transform(_matrix(shape.wrapped.Location()))


def _union(here):
    """_manifold() of a shape at the origin"""
    pieces = [_solid(s) for s in here.solids()]
    return None if not pieces or None in pieces else mf.Manifold.batch_boolean(pieces, mf.OpType.Add)


def common_volume(a, b, doubts, what):
    """Volume (mm3) of solid a inside solid b, by OCC. Measured again from triangle meshes; if the two differ by more than the
    chords can explain (TOL x the curved area around the overlap), or the meshes cannot be made, appends a line naming what to
    doubts. A model with any doubts fails its check"""
    r = a & b
    parts = [] if r is None else r if isinstance(r, list) else [r]
    occ = sum(s.volume for p in parts for s in p.solids())
    ma, mb = _manifold(a), _manifold(b)
    if ma is None or mb is None:
        doubts.append(f"{what}: OCC {occ:.2f} mm3, not checked by mesh (does not mesh as a closed solid)")
        return occ
    common = ma ^ mb
    mesh = common.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    t = np.asarray(mesh.tri_verts)[np.asarray(mesh.face_id) % 2 == 1]
    curved = 0.5 * np.linalg.norm(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]]), axis=1).sum()
    curved = max(curved, sum(f.area for p in parts for s in p.solids() for f in s.faces() if f.geom_type != GeomType.PLANE))
    tri = common.volume()
    if abs(occ - tri) > TOL * curved + 1e-3 + 1e-4 * max(occ, tri):
        doubts.append(f"{what}: OCC {occ:.2f} mm3, mesh {tri:.2f} mm3")
    return occ


def _sheet(p, normal, tri, eps):
    """A closed thin solid round the mesh of one face (nodes p, triangles tri): the mesh moved eps to each side along the face's
    unit normals at its nodes (normal; NaN where the surface has none, and the mesh's normal is taken there), face id 0 on the
    side the face's normal points to and 1 on the other, joined round its open edges (face id 2). Returns the solid, its run id
    and the area of each of its two sides, or None if it does not close or a triangle turns over (where the face curves tighter
    than eps). Along the face's normals, not the mesh's: a node on an edge lies up to the edge's tolerance off the face (0.007 mm
    on a pad of 0.05 mm2 of the ROCK 5B+), which tips the mesh's normals there far enough to turn the thin triangles over"""
    n = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]])
    none = np.isnan(normal).any(axis=1)
    if none.any():
        at = np.zeros_like(p)
        for k in range(3):
            np.add.at(at, tri[:, k], n)
        size = np.linalg.norm(at[none], axis=1, keepdims=True)
        if (size == 0).any():
            return None
        normal = normal.copy()
        normal[none] = at[none] / size
    sides, area = [p + eps * normal, p - eps * normal], []
    for q in sides:
        c = np.cross(q[tri[:, 1]] - q[tri[:, 0]], q[tri[:, 2]] - q[tri[:, 0]])
        if ((c * n).sum(axis=1) < 0).any():
            return None
        area.append(0.5 * np.linalg.norm(c, axis=1).sum())
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    k = len(p)
    rim = e[~np.isin(e[:, 0] * k + e[:, 1], e[:, 1] * k + e[:, 0])]   # edges no other triangle of the face has
    wall = np.concatenate([np.c_[rim[:, 1], rim[:, 0], rim[:, 0] + k], np.c_[rim[:, 1], rim[:, 0] + k, rim[:, 1] + k]])
    t = np.concatenate([tri, tri[:, ::-1] + k, wall])
    run = mf.Manifold.reserve_ids(1)
    m = mf.Manifold(mf.Mesh64(vert_properties=np.concatenate(sides), tri_verts=t.astype(np.uint64),
                              run_index=np.array([0, t.size], dtype=np.uint64), run_original_id=np.array([run], dtype=np.uint32),
                              face_id=np.repeat(np.array([0, 1, 2], dtype=np.uint64), [len(tri), len(tri), len(wall)])))
    return None if m.status() != mf.Error.NoError else (m, run, area)


def _normals(face, uv):
    """Unit normals of face at points (u, v) of its surface, pointing the way the face does (NaN where the surface has none)"""
    props = GeomLProp_SLProps(BRep_Tool.Surface_s(face.wrapped), 1, 1e-9)
    out = np.full((len(uv), 3), np.nan)
    for i, (u, v) in enumerate(uv):
        props.SetParameters(u, v)
        if props.IsNormalDefined():
            d = props.Normal()
            out[i] = d.X(), d.Y(), d.Z()
    return -out if face.wrapped.Orientation() == TopAbs_REVERSED else out


def _sheets(shell):
    """The faces of a shell as thin solids (_sheet), in the shell's own frame, each as [area, solid, its run id, area of its two
    sides, the 8 corners of its box]; the solid is None where the face cannot be meshed or thickened. A face is thickened
    EPS_CURVED to each side if it is curved, and EPS_FLAT where it curves tighter than that or is flat.
    A face is meshed again with Watson (as in _solid()) if Delabella's mesh does not cover it (its area must match the face's
    within what the chords can move its edges, TOL x their length, plus 1% on a curved face, whose triangles are flat) or folds
    over where it is thickened"""
    return _SHEETS(shell, _thicken)


def _thicken(here):
    """_sheets() of a shell at the origin"""
    whole = _triangulate(here, IMeshTools_MeshAlgoType_Delabella, apart=True)
    out = []
    for i, f in enumerate(here.faces() if whole is None else [f for f, _ in whole[2]]):
        area = f.area
        if area < 1e-6:            # nothing to measure (cylinders of no height)
            continue
        curved, edge, sheet = f.geom_type != GeomType.PLANE, sum(e.length for e in f.edges()), None
        for xyz, uv, tri in _face_meshes(whole, i, f):
            if tri is None:
                continue
            used, tri = np.unique(tri[(tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])],
                                  return_inverse=True)
            tri, p = tri.reshape(-1, 3), xyz[used]
            a = 0.5 * np.linalg.norm(np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]]), axis=1).sum()
            if not tri.size or abs(a - area) > TOL * edge + 1e-3 + (1e-2 if curved else 1e-4) * area:
                continue
            normal = _normals(f, uv[used])
            for eps in ((EPS_CURVED, EPS_FLAT) if curved else (EPS_FLAT,)):
                sheet = _sheet(p, normal, tri, eps)
                if sheet is not None:
                    break
            if sheet is not None:
                break
        if sheet is not None:
            lo, hi = np.array(sheet[0].bounding_box()).reshape(2, 3)
        else:
            b = f.bounding_box()
            lo, hi = np.array([b.min.X, b.min.Y, b.min.Z]), np.array([b.max.X, b.max.Y, b.max.Z])
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        out.append([area] + ([None, None, None] if sheet is None else list(sheet)) + [corners])
    return out


def _face_meshes(whole, i, f):
    """Meshes of face f (the i-th of its shell) to try in turn, as (nodes, their (u, v), triangles or None): from Delabella's mesh
    of the whole shell (whole; on its own if the shell would not mesh), then on its own with Watson"""
    if whole is not None:
        yield whole[0], whole[1], whole[2][i][1]
    for algo in (() if whole is not None else (IMeshTools_MeshAlgoType_Delabella,)) + (IMeshTools_MeshAlgoType_Watson,):
        t = _triangulate(f, algo, apart=True)
        if t is not None:
            yield t[0], t[1], t[2][0][1]


def _batches(lo, hi, runs):
    """Batch number of each box (rows of lo and hi), such that no two boxes in a batch touch or have the same run id (a part used
    more than once in a model has the same run ids each time). The boxes that touch are found with an R-tree: comparing every box
    with every other took most of a minute for the 35,000 faces of the ROCK 5B+ model"""
    index = rtree.index.Index(((i, (*lo[i], *hi[i]), None) for i in range(len(lo))), properties=rtree.index.Property(dimension=3))
    ids, counts = index.intersection_v(lo, hi)
    pairs = [np.c_[np.repeat(np.arange(len(lo)), counts.astype(np.int64)), ids]]
    same = {}
    for i, r in enumerate(runs.tolist()):
        same.setdefault(r, []).append(i)
    pairs += [np.array([(i, j) for i in g for j in g]) for g in same.values() if len(g) > 1]
    pairs = np.concatenate(pairs)
    pairs = pairs[np.argsort(pairs[:, 0], kind="stable")]
    start = np.searchsorted(pairs[:, 0], np.arange(len(lo) + 1))
    batch = np.full(len(lo), -1)
    for i in range(len(lo)):
        taken = batch[pairs[start[i]:start[i + 1], 1]]
        free = np.ones(len(taken) + 1, dtype=bool)
        free[taken[(taken >= 0) & (taken < len(free))]] = False
        batch[i] = int(np.argmax(free))
    return batch


def surface_area(solid, shells, doubts, what):
    """Area (mm2) of the surfaces in shells inside solid, by OCC: the faces of their intersection whose middle is strictly inside,
    so that a surface lying on the solid's faces (the board resting on the standoffs) is not counted.
    Measured again from meshes: each face is thickened into a thin solid (_sheets), which is intersected with the solid's mesh.
    Each of its two sides has a share inside, the same where the face is inside but none on one side where the face lies on the
    solid; the smaller share of the face's area is counted. If the two areas differ by more than the chords and the thickening can
    move the line where the solid's surface crosses the faces (TOL + EPS_CURVED times its length, plus 0.001 mm2 and 0.01%), or a
    face that cannot be meshed or thickened has its box reaching into the solid, appends a line naming what to doubts. A model
    with any doubts fails its check.
    The thin solids are intersected with the solid in batches whose boxes do not touch, so that none of them merges with another"""
    occ = 0.0
    for g in shells:
        for f in (solid & g).faces():
            v, t = f.tessellate(0.05)
            p = (v[t[0][0]] + v[t[0][1]] + v[t[0][2]]) / 3          # a point on the face
            if BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(p.X, p.Y, p.Z), 1e-4).State() == TopAbs_IN:
                occ += f.area
    ms = _manifold(solid)
    if ms is None:
        doubts.append(f"{what}: OCC {occ:.2f} mm2 of surface, not checked by mesh (the solid does not mesh closed)")
        return occ
    slo, shi = np.array(ms.bounding_box()).reshape(2, 3)
    near, missing = [], 0
    for g in shells:
        m = _matrix(g.wrapped.Location())
        for area, sheet, run, sides, corners in _sheets(g):
            c = corners @ m[:, :3].T + m[:, 3]
            lo, hi = c.min(axis=0), c.max(axis=0)
            if (lo > shi).any() or (hi < slo).any():
                continue
            if sheet is None:            # a flat face's box has no thickness
                size = np.maximum(hi - lo, EPS_FLAT)
                missing += (mf.Manifold.cube(size.tolist(), True).translate(((lo + hi) / 2).tolist()) ^ ms).volume() > 0
            else:
                near.append((area, sheet.transform(m), run, sides, lo - 1e-3, hi + 1e-3))
    if missing:
        doubts.append(f"{what}: {missing} faces of surface not checked by mesh (do not mesh, and reach into the solid)")
    runs = np.array([x[2] for x in near])
    batch = _batches(np.array([x[4] for x in near]), np.array([x[5] for x in near]), runs) if near else np.zeros(0, dtype=int)
    inside, cut = np.zeros((len(near), 2)), np.zeros((len(near), 2))
    for b in range(batch.max() + 1 if near else 0):
        index = {int(runs[i]): int(i) for i in np.flatnonzero(batch == b)}
        r = (mf.Manifold.batch_boolean([near[i][1] for i in index.values()], mf.OpType.Add) ^ ms).to_mesh64()
        v, t, fid = np.asarray(r.vert_properties)[:, :3], np.asarray(r.tri_verts), np.asarray(r.face_id)
        at = np.asarray(r.run_index) // 3
        face = np.repeat(np.array([index.get(int(x), -1) for x in np.asarray(r.run_original_id)], dtype=np.int64), np.diff(at))
        w = t[(face >= 0) & (fid == 2)].astype(np.int64)                          # triangles on a wall of a thin solid
        w = np.sort(np.concatenate([w[:, [0, 1]], w[:, [1, 2]], w[:, [2, 0]]]), axis=1)
        on = (face >= 0) & (fid < 2)                                               # on a side
        t, k = t[on].astype(np.int64), face[on] * 2 + fid[on].astype(np.int64)
        inside += np.bincount(k, 0.5 * np.linalg.norm(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]]), axis=1),
                              minlength=2 * len(near)).reshape(-1, 2)
        e = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
        e = np.c_[np.tile(k, 3), np.sort(e, axis=1)]
        e, n = np.unique(e, axis=0, return_counts=True)
        e = e[n == 1]                                    # the edge of the area inside, on each side
        e = e[~np.isin(e[:, 1] * len(v) + e[:, 2], w[:, 0] * len(v) + w[:, 1])]   # but not where it is the face's own edge
        cut += np.bincount(e[:, 0], np.linalg.norm(v[e[:, 1]] - v[e[:, 2]], axis=1), minlength=2 * len(near)).reshape(-1, 2)
    tri = length = 0.0
    for i, (area, _, _, sides, _, _) in enumerate(near):
        share = inside[i] / np.array(sides)
        j = int(np.argmin(share))
        tri += area * min(share[j], 1.0)
        length += cut[i, j]
    if not abs(occ - tri) <= (TOL + EPS_CURVED) * length + 1e-3 + 1e-4 * max(occ, tri):     # NaN fails too
        doubts.append(f"{what}: OCC {occ:.2f} mm2, mesh {tri:.2f} mm2 of surface")
    return occ
