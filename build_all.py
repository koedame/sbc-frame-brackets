"""Generate 3MF, STL and STEP files and the HTML viewer for the brackets (board x mount x orientation x without / with integrated standoffs).

Ready-made files for every model are attached to each GitHub release; build only when you change something.

Usage:
  python build_all.py --board PiB --mount 20 --orient flat-portrait --format 3mf
                                               # only what you need: here the PiB bracket (Raspberry Pi B size) for 20x20, flat portrait, as 3MF
  python build_all.py --board PiB --check      # also check interference with the frame and board, unsupported areas and print time,
                                               # and for DIN rail whether the leaf springs can bend far enough to push on (exit 1 if a check fails)
  python build_all.py --check --board-step vim1s-pcba-3d-v11.stp --board-step ROCK5B_v1.42_3D.step
                                               # check against the boards' official 3D models (not put in viewer.html)
  python build_all.py --coupons                # also write fit test coupons (clearance 0.00 / 0.05 / 0.10 mm)
  python build_all.py                          # everything (every model in 3MF, STL and STEP, and viewer.html) to models/

Requirements: Python 3.11 or later, build123d (plus trimesh, shapely, networkx and rtree for --check)
"""
import argparse, json, os, sys
from build123d import Pos, Compound, Mesher, export_step, export_stl
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN
from OCP.gp import gp_Pnt
import sbc_brackets as sb

HERE = os.path.dirname(os.path.abspath(__file__))
FORMATS = ["3mf", "stl", "step", "viewer"]
BED = 256.0                                   # size of the build plate the 3MF and STL are placed on (centred)


def model_id(B, series, spacer, orient=sb.UPRIGHT):
    """PiB_2020, PiB_2020_spacer, PiB_2020_upright-landscape_spacer, PiB_2020_flat-portrait, ... (upright portrait has no suffix)"""
    return (f"{B.name}_{sb.mount_tag(series)}" + ("" if orient == sb.UPRIGHT else f"_{orient}")
            + ("_spacer" if spacer else ""))


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
                    help="a board's official 3D model (STEP, or STL for one published only as STL), used for the board interference check in place of the simplified board. "
                         "Repeat for several models; the file name tells which board it is (STEPS in sbc_brackets.py). Not put in viewer.html")
    ap.add_argument("--check", action="store_true", help="check every model built; exit 1 if any check fails")
    ap.add_argument("--coupons", action="store_true")
    ap.add_argument("--board", nargs="+", choices=[B.name for B in sb.BOARDS], default=[B.name for B in sb.BOARDS])
    ap.add_argument("--mount", nargs="+", choices=["20", "40", "DIN"], default=["20", "40", "DIN"])
    ap.add_argument("--orient", nargs="+", choices=list(sb.ORIENTS), default=list(sb.ORIENTS))
    ap.add_argument("--format", nargs="+", choices=FORMATS, default=FORMATS,
                    help="viewer.html shows only the models built in the same run")
    a = ap.parse_args()
    a.mount = [x if x == "DIN" else int(x) for x in a.mount]
    viewer = "viewer" in a.format
    os.makedirs(a.out, exist_ok=True)
    boards = [B for B in sb.BOARDS if B.name in a.board]
    if a.check:
        import checks_print as cp, checks_time as ct
    boards_chk = {B.name: [("board", [B.ghost()])] for B in boards}   # what the board overlap is measured against (board frame)
    official = {}
    for p in a.board_step:
        B, solids = sb.official(p)
        official.setdefault(B.name, []).append((os.path.basename(p), solids))
    boards_chk.update((n, v) for n, v in official.items() if n in boards_chk)
    frames = {s: sb.mount_frame(s, 300) for s in a.mount}
    models = []; ghosts = {}; failed = []
    for B, orient, series, spacer in [(B, o, se, sp) for B in boards for o in a.orient for se in a.mount for sp in (False, True)
                                       if o in sb.SPACER_ORIENTS or not sp]:   # flat and shelf: no integrated standoffs
        n = model_id(B, series, spacer, orient)
        M = sb.place(B, orient, series)
        gk = B.name if orient == sb.UPRIGHT else f"{B.name}_{sb.mount_tag(series)}_{orient}"   # board shown with this model
        if viewer and gk not in ghosts:
            ghosts[gk] = mesh(Compound([M * B.ghost()]), 0.3)
        s = B.bracket(series, spacer, orient)
        if "3mf" in a.format:
            write_3mf(s, os.path.join(a.out, n + ".3mf"), n)
        if "stl" in a.format:
            export_stl(on_plate(s), os.path.join(a.out, n + ".stl"), tolerance=0.02, angular_tolerance=0.2)
        if "step" in a.format:
            export_step(s, os.path.join(a.out, n + ".step"))
        bb = s.bounding_box()
        m = dict(id=n, name=B.name, title=B.title, series=series, mount=sb.mount_label(series), spacer=spacer,
                 orient=orient, orient_label=sb.ORIENTS[orient], ghost=gk,
                 size=[round(x, 1) for x in (bb.size.X, bb.size.Y, bb.size.Z)], vol=round(s.volume / 1000, 1), min=None,
                 boss=(dict(B.SPACER) if spacer else None))
        line = f"{n:40s} size {m['size']} mm  volume {m['vol']} cm3"
        if a.check:
            fr = frames[series]
            hit_frame = (s & fr).volume
            hits = []; bad = round(hit_frame, 2) > 0 or len(s.solids()) != 1
            for lab, gs in boards_chk[B.name]:
                v, ar = overlap(s, [M * g for g in gs])
                hits.append(f"{lab} overlap {v:.2f} mm3" + ("" if all(g.solids() for g in gs) else f" + {ar:.2f} mm2 of surface"))
                bad |= round(v, 2) > 0 or round(ar, 2) > 0
            hit_board = "  ".join(hits)
            unsup = cp.unsupported(s)[0]
            bad |= unsup > 0
            m["min"] = ct.estimate(s)["min"]
            line += (f"  frame overlap {hit_frame:.2f}  {hit_board}  unsupported {unsup} mm2  ~{m['min']} min"
                     + ("" if len(s.solids()) == 1 else f"  {len(s.solids())} separate solids (must be 1)"))
            if series == "DIN":
                spring = sb.din_spring_hit(s)
                bad |= round(spring, 2) > 0
                line += f"  leaf spring travel {sb.din_spring_travel():.2f} mm overlap {spring:.2f} mm3"
            if bad:
                failed.append(n)
        print(line)
        if viewer:
            m["mesh"] = mesh(s)
        models.append(m)
    if a.coupons:
        for series in [x for x in a.mount if x != "DIN"]:
            for i, fit in enumerate((0.0, 0.05, 0.10)):
                export_stl(sb.coupon(series, fit, i + 1), os.path.join(a.out, f"fit_test_{series}{series}_{i + 1}.stl"))
        print("Coupons: fit_test_*_1 = clearance 0.00 mm, _2 = 0.05 mm (same as the brackets), _3 = 0.10 mm. Told apart by the number of notches")
    if viewer:
        # Boards in the viewer are built only from the simplified shapes, which can be distributed. The official 3D models from
        # --board-step are used only for interference checks; not even a converted shape goes into viewer.html
        # (so the manufacturers' CAD data is not redistributed)
        data = dict(frames={s: mesh(sb.mount_frame(s, 260), 0.2) for s in a.mount},
                    ghosts=ghosts,
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
    if a.check:
        if failed:
            sys.exit(f"Checks failed for {len(failed)} of {len(models)} models: " + ", ".join(failed))
        print(f"Checks passed for all {len(models)} models")


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
