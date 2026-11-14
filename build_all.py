"""Generate 3MF, STL and STEP files for every model (each board x 20x20 / 40x40 / DIN rail x without / with integrated standoffs) and the HTML viewer.

Usage:
  python build_all.py                          # write every model as 3MF, STL and STEP, and viewer.html, to models/
  python build_all.py --vim1s-step vim1s-pcba-3d-v11.stp   # use the official VIM1S 3D model for interference checks (not put in viewer.html)
  python build_all.py --check                  # also report interference with the frame and board, unsupported areas and print time estimates
  python build_all.py --coupons                # also write fit test coupons (clearance 0.00 / 0.05 / 0.10 mm)
  python build_all.py --only PiB --series 20 DIN   # only some of them (20 / 40 / DIN)

Requirements: Python 3.11 or later, build123d (plus trimesh, shapely, networkx and rtree for --check)
"""
import argparse, json, os, sys
from build123d import Pos, Compound, Mesher, export_step, export_stl
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


def ghost(B, vim_step):
    if B is sb.VIM1S:
        return sb.VIM1S.ghost(vim_step)
    return [B.ghost()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "models"))
    ap.add_argument("--vim1s-step", default=None, help="path to Khadas' official vim1s-pcba-3d-v11.stp, used for interference checks (optional; not put in viewer.html)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--coupons", action="store_true")
    ap.add_argument("--no-viewer", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="PiB / PiA / PiZero / VIM1S")
    ap.add_argument("--series", nargs="*", default=[str(x) for x in sb.SERIES], help="20 / 40 / DIN")
    a = ap.parse_args()
    a.series = [x if x == "DIN" else int(x) for x in a.series]
    os.makedirs(a.out, exist_ok=True)
    boards = [B for B in sb.BOARDS if not a.only or B.name in a.only]
    if a.check:
        import checks_print as cp, checks_time as ct
    ghosts = {B.name: ghost(B, a.vim1s_step) for B in boards}
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
                    hit_board = sum((s & g).volume for g in ghosts[B.name])
                    unsup = cp.unsupported(s)[0]
                    m["min"] = ct.estimate(s)["min"]
                    line += f"  frame overlap {hit_frame:.2f}  board overlap {hit_board:.2f} mm3  unsupported {unsup} mm2  ~{m['min']} min"
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
        # Boards in the viewer are built only from the simplified shapes, which can be distributed. The official 3D model from
        # --vim1s-step is used only for interference checks; not even a converted shape goes into viewer.html
        # (so the manufacturer's CAD data is not redistributed)
        data = dict(frames={s: mesh(sb.mount_frame(s, 260), 0.2) for s in a.series},
                    ghosts={B.name: mesh(Compound(ghost(B, None)), 0.3) for B in boards},
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
