"""Generate 3MF, STL and STEP files for every model (each board x 20x20 / 40x40 / DIN rail x without / with integrated standoffs) and the HTML viewer.

Usage:
  python build_all.py                          # write every model as 3MF, STL and STEP, and viewer.html, to models/
  python build_all.py --check                  # also report interference with the frame and board, unsupported areas and print time estimates,
                                               # and for DIN rail whether the leaf springs can bend far enough to push on
  python build_all.py --check --board-step vim1s-pcba-3d-v11.stp --board-step ROCK5B_v1.42_3D.step
                                               # check against the boards' official 3D models (not put in viewer.html)
  python build_all.py --coupons                # also write fit test coupons (clearance 0.00 / 0.05 / 0.10 mm)
  python build_all.py --only PiB --series 20 DIN   # only some of them (20 / 40 / DIN)

Requirements: Python 3.11 or later, build123d (plus trimesh, shapely, networkx and rtree for --check)
"""
import argparse, json, os, sys
from build123d import Pos, Compound, Mesher, export_step, export_stl
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN
from OCP.gp import gp_Pnt
import sbc_brackets as sb

HERE = os.path.dirname(os.path.abspath(__file__))
BED = 256.0                                   # size of the build plate the 3MF and STL are placed on (centred)


def model_id(B, series, spacer):
    return f"{B.name}_{sb.mount_tag(series)}" + ("_spacer" if spacer else "")


def on_plate(shape):
    bb = shape.bounding_box()
    return Pos(BED / 2 - (bb.min.X + bb.max.X) / 2, BED / 2 - (bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape   # centre it, keeping the print orientation


def write_3mf(shape, path, name):
    m = Mesher(); m.add_shape(on_plate(shape), linear_deflection=0.02, angular_deflection=0.2, part_number=name); m.write(path)


def mesh(shape, tol=0.08, nd=2):
    v, t = (sb.world() * shape).tessellate(tol, 0.3)
    return dict(v=[round(c, nd) for p in v for c in (p.X, p.Y, p.Z)], t=[i for tri in t for i in tri])


def overlap(s, parts):
    """Interference between the bracket and a board: the volume (mm3) shared with its solid parts, and for parts that are only
    surfaces, the area (mm2) of surface inside the bracket. Surfaces lying on the bracket's faces (the board resting on the
    standoffs) are not counted"""
    vol = area = 0.0
    sbb = s.bounding_box()
    for g in parts:
        gb = g.bounding_box()
        if (gb.min.X > sbb.max.X or gb.max.X < sbb.min.X or gb.min.Y > sbb.max.Y or gb.max.Y < sbb.min.Y
                or gb.min.Z > sbb.max.Z or gb.max.Z < sbb.min.Z):
            continue
        r = s & g
        if g.solids():
            vol += r.volume
            continue
        for f in r.faces():
            v, t = f.tessellate(0.05)
            p = (v[t[0][0]] + v[t[0][1]] + v[t[0][2]]) / 3          # a point on the face
            if BRepClass3d_SolidClassifier(s.wrapped, gp_Pnt(p.X, p.Y, p.Z), 1e-4).State() == TopAbs_IN:
                area += f.area
    return vol, area


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "models"))
    ap.add_argument("--board-step", action="append", default=[], metavar="PATH",
                    help="a board's official 3D model, used for the board interference check in place of the simplified board. "
                         "Repeat for several models; the file name tells which board it is (STEPS in sbc_brackets.py). Not put in viewer.html")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--coupons", action="store_true")
    ap.add_argument("--no-viewer", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help=" / ".join(B.name for B in sb.BOARDS))
    ap.add_argument("--series", nargs="*", default=[str(x) for x in sb.SERIES], help="20 / 40 / DIN")
    a = ap.parse_args()
    a.series = [x if x == "DIN" else int(x) for x in a.series]
    os.makedirs(a.out, exist_ok=True)
    boards = [B for B in sb.BOARDS if not a.only or B.name in a.only]
    if a.check:
        import checks_print as cp, checks_time as ct
    boards_chk = {B.name: [("board", [B.ghost()])] for B in boards}   # what the board overlap is measured against
    official = {}
    for p in a.board_step:
        B, solids = sb.official(p)
        official.setdefault(B.name, []).append((os.path.basename(p), solids))
    boards_chk.update((n, v) for n, v in official.items() if n in boards_chk)
    frames = {s: sb.mount_frame(s, 300) for s in a.series}
    models = []
    for B in boards:
        for series in a.series:
            for spacer in (False, True):
                n = model_id(B, series, spacer)
                s = B.bracket(series, spacer)
                write_3mf(s, os.path.join(a.out, n + ".3mf"), n)
                export_stl(on_plate(s), os.path.join(a.out, n + ".stl"), tolerance=0.02, angular_tolerance=0.2)
                export_step(s, os.path.join(a.out, n + ".step"))
                bb = s.bounding_box()
                m = dict(id=n, name=B.name, title=B.title, series=series, mount=sb.mount_label(series), spacer=spacer,
                         size=[round(x, 1) for x in (bb.size.X, bb.size.Y, bb.size.Z)], vol=round(s.volume / 1000, 1), min=None,
                         boss=(dict(B.SPACER) if spacer else None))
                line = f"{n:22s} size {m['size']} mm  volume {m['vol']} cm3"
                if a.check:
                    fr = frames[series]
                    hit_frame = (s & fr).volume
                    hits = []
                    for lab, gs in boards_chk[B.name]:
                        v, ar = overlap(s, gs)
                        hits.append(f"{lab} overlap {v:.2f} mm3" + ("" if all(g.solids() for g in gs) else f" + {ar:.2f} mm2 of surface"))
                    hit_board = "  ".join(hits)
                    unsup = cp.unsupported(s)[0]
                    m["min"] = ct.estimate(s)["min"]
                    line += f"  frame overlap {hit_frame:.2f}  {hit_board}  unsupported {unsup} mm2  ~{m['min']} min"
                    if series == "DIN":
                        line += f"  leaf spring travel {sb.din_spring_travel():.2f} mm overlap {sb.din_spring_hit(s):.2f} mm3"
                print(line)
                if not a.no_viewer:
                    m["mesh"] = mesh(s)
                models.append(m)
    if a.coupons:
        for series in [x for x in a.series if x != "DIN"]:
            for i, fit in enumerate((0.0, 0.05, 0.10)):
                export_stl(sb.coupon(series, fit, i + 1), os.path.join(a.out, f"fit_test_{series}{series}_{i + 1}.stl"))
        print("Coupons: fit_test_*_1 = clearance 0.00 mm, _2 = 0.05 mm (same as the brackets), _3 = 0.10 mm. Told apart by the number of notches")
    if not a.no_viewer:
        # Boards in the viewer are built only from the simplified shapes, which can be distributed. The official 3D models from
        # --board-step are used only for interference checks; not even a converted shape goes into viewer.html
        # (so the manufacturers' CAD data is not redistributed)
        data = dict(frames={s: mesh(sb.mount_frame(s, 260), 0.2) for s in a.series},
                    ghosts={B.name: mesh(Compound([B.ghost()]), 0.3) for B in boards},
                    models=models)
        tpl = open(os.path.join(HERE, "viewer.tpl.html"), encoding="utf-8").read()
        three = open(os.path.join(HERE, "vendor", "three.min.js"), encoding="utf-8").read()
        orbit = open(os.path.join(HERE, "vendor", "OrbitControls.js"), encoding="utf-8").read()
        lic = open(os.path.join(HERE, "vendor", "LICENSE-three.txt"), encoding="utf-8").read().strip()
        html = (tpl.replace("__THREE_LICENSE__", lic)
                   .replace("__THREE__", three.replace("</script", "<\\/script"))
                   .replace("__ORBIT__", orbit.replace("</script", "<\\/script"))
                   .replace("__DATA__", json.dumps(data, separators=(",", ":"))))
        open(os.path.join(a.out, "viewer.html"), "w", encoding="utf-8").write(html)
        print("Wrote viewer.html")


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
