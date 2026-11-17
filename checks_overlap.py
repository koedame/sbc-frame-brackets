"""Overlap volume for the interference, retention and leaf spring checks, measured twice: by OCC's boolean intersection and by an
intersection of triangle meshes (manifold3d).
OCC's intersection can silently miss where nearly parallel flat faces overlap and return 0, part of the overlap or the whole of one
shape. A check that trusts it alone then passes interference that is there, or reports a bracket that is held as loose. The two
results may differ by what the meshes' chords move on curved faces; beyond that, the overlap is counted as a disagreement and the
model fails, whichever result would have passed."""
import numpy as np
import manifold3d as mf
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IMeshTools import IMeshTools_MeshAlgoType_Delabella, IMeshTools_MeshAlgoType_Watson, IMeshTools_Parameters
from OCP.ShapeAnalysis import ShapeAnalysis_ShapeTolerance
from OCP.TopAbs import TopAbs_EDGE, TopAbs_REVERSED
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Vertex
from build123d import GeomType, Shape

TOL, ANGLE = 0.02, 0.2        # mesh: chord error (mm) and angle (rad). A chord moves a curved face by at most TOL
_MESHES = {}


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
    """_solid() with one triangulation algorithm.
    Meshes a copy, with TOL in mm: Shape.mesh() takes the tolerance relative to the size of each edge, and leaves its mesh on the
    shape, where the print checks and the 3MF writer would then reuse it.
    Each face's mesh has its own copy of the nodes on its edges, and two faces may place an edge's node apart by up to the edge's
    tolerance (0.15 mm in a vendor's STEP file), so the copies are joined by which edge and vertex they lie on, not by position.
    A face BRepMesh cannot mesh (a vendor's file has cylinders of no height) is left as a hole for _holes() to close"""
    solid = Shape.cast(BRepBuilderAPI_Copy(solid.wrapped, False, False).Shape())
    params = IMeshTools_Parameters()
    params.Deflection, params.Angle, params.Relative, params.InParallel = TOL, ANGLE, False, False
    params.MeshAlgo = algo
    BRepMesh_IncrementalMesh(solid.wrapped, params)
    ids, xyz, tri, curved = {}, [], [], []

    def node(key, p):
        if key not in ids:
            ids[key] = len(xyz)
            xyz.append(p)
        return ids[key]

    for f in solid.faces():
        loc = TopLoc_Location()
        poly = BRep_Tool.Triangulation_s(f.wrapped, loc)
        if poly is None:
            continue
        m = _matrix(loc)
        p = np.array([(q.X(), q.Y(), q.Z()) for q in (poly.Node(i) for i in range(1, poly.NbNodes() + 1))]) @ m[:, :3].T + m[:, 3]
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
                at[k] = node(key, p[k])
        inner = at < 0
        at[inner] = np.arange(len(xyz), len(xyz) + inner.sum())
        xyz.extend(p[inner])
        t = at[np.array([(x.Value(1), x.Value(2), x.Value(3)) for x in poly.Triangles()]) - 1]
        tri.append(t[:, [0, 2, 1]] if f.wrapped.Orientation() == TopAbs_REVERSED else t)
        curved += [f.geom_type != GeomType.PLANE] * len(t)
    if not tri:
        return None
    xyz, tri, curved = np.array(xyz), np.concatenate(tri), np.array(curved, dtype=np.uint64)
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


def _manifold(shape):
    """shape as a manifold3d solid (None if any of its solids does not mesh closed). Meshed once per shape, wherever it is placed,
    and kept while the shape exists: before a new mesh is added, the meshes of shapes that only this cache still refers to are
    dropped (every model makes new brackets, whose meshes would otherwise pile up, about 4 MB a model)"""
    key = shape.wrapped.TShape()
    if key not in _MESHES:
        for k in [k for k in _MESHES if k.GetRefCount() == 1]:
            del _MESHES[k]
        here = Shape.cast(shape.wrapped.Located(TopLoc_Location()))
        pieces = [_solid(s) for s in here.solids()]
        _MESHES[key] = None if not pieces or None in pieces else mf.Manifold.batch_boolean(pieces, mf.OpType.Add)
    m = _MESHES[key]
    return None if m is None else m.transform(_matrix(shape.wrapped.Location()))


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
