"""Generate 3MF, STL and STEP files and the HTML viewer for the brackets (board x mount x orientation x without / with integrated standoffs).

Ready-made files for every model are attached to each GitHub release; build only when you change something.

Usage:
  python build_all.py --board PiB --mount 20 --orient flat-portrait --format 3mf
                                               # only what you need: here the PiB bracket (Raspberry Pi B size) for 20x20, flat portrait, as 3MF
  python build_all.py --board PiB --check      # also check interference with the frame and board, unsupported areas, print time,
                                               # that the bracket is held (moved 0.3 mm forward, up or down, it hits the frame) and that flat head
                                               # screws stay below the back of the flat plates, and that every extrude() in the
                                               # scripts names its direction; for DIN rail
                                               # against steel and aluminium rails, and whether the leaf springs can bend far enough to push on
                                               # (exit 1 if a check fails)
  python build_all.py --check --board-step vim1s-pcba-3d-v11.stp --board-step ROCK5B_v1.42_3D.step
                                               # check against the boards' official 3D models (not put in viewer.html)
  python build_all.py --coupons                # also write fit test coupons (clearance 0.00 / 0.05 / 0.10 mm)
  python build_all.py                          # everything (every model in 3MF, STL and STEP, and viewer.html) to models/

pack_release.py arranges what a full build with --coupons wrote into the files of a release (one zip per bracket).

Requirements: Python 3.12 to 3.14, build123d (plus trimesh, shapely, networkx, rtree and manifold3d for --check)
"""
import argparse, ast, glob, json, os, sys
from build123d import Pos, Compound, Mesher, export_step, export_stl
import sbc_brackets as sb

HERE = os.path.dirname(os.path.abspath(__file__))
FORMATS = ["3mf", "stl", "step", "viewer"]
BED = 256.0                                   # size of the build plate the 3MF and STL are placed on (centred)
RETAIN_D = 0.3                                # retention: moved this far forward, up or down, the bracket must hit what it is on
RETAIN = {"forward": (0, RETAIN_D, 0), "up": (RETAIN_D, 0, 0), "down": (-RETAIN_D, 0, 0)}


def model_id(B, series, spacer, orient=sb.UPRIGHT):
    """PiB_2020_upright-portrait, PiB_2020_upright-portrait_standoffs, PiB_2020_flat-portrait, ...: every part of the name is
    always there, so the files of one mount sort and read as a list of orientations"""
    return f"{B.name}_{sb.mount_tag(series)}_{orient}" + ("_standoffs" if spacer else "")


def on_plate(shape):
    bb = shape.bounding_box()
    return Pos(BED / 2 - (bb.min.X + bb.max.X) / 2, BED / 2 - (bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape   # centre it, keeping the print orientation


def write_3mf(shape, path, name):
    m = Mesher(); m.add_shape(on_plate(shape), linear_deflection=0.02, angular_deflection=0.2, part_number=name); m.write(path)


def write(shape, formats, out, name):
    """Write a model in the formats asked for: 3MF and STL laid on the build plate as printed, STEP where it is"""
    if "3mf" in formats:
        write_3mf(shape, os.path.join(out, name + ".3mf"), name)
    if "stl" in formats:
        export_stl(on_plate(shape), os.path.join(out, name + ".stl"), tolerance=0.02, angular_tolerance=0.2)
    if "step" in formats:
        export_step(shape, os.path.join(out, name + ".step"))


def mesh(shape, tol=0.08, nd=2):
    v, t = (sb.world() * shape).tessellate(tol, 0.3)
    return dict(v=[round(c, nd) for p in v for c in (p.X, p.Y, p.Z)], t=[i for tri in t for i in tri])


def overlap(s, parts, doubts, what):
    """Interference between the bracket and a board: the volume (mm3) shared with its solid parts (common_volume), and for parts
    that are only surfaces, the area (mm2) of surface inside the bracket (surface_area). Both add to doubts if OCC and the meshes
    disagree"""
    from checks_overlap import common_volume, surface_area
    vol, shells = 0.0, []
    sbb = s.bounding_box()
    for g in parts:
        gb = g.bounding_box()
        if (gb.min.X > sbb.max.X or gb.max.X < sbb.min.X or gb.min.Y > sbb.max.Y or gb.max.Y < sbb.min.Y
                or gb.min.Z > sbb.max.Z or gb.max.Z < sbb.min.Z):
            continue
        if g.solids():
            vol += common_volume(s, g, doubts, what)
        else:
            shells.append(g)
    return vol, (surface_area(s, shells, doubts, what) if shells else 0.0)


def undirected_extrudes():
    """The extrude() calls in the scripts that neither name the direction (dir=) nor go both ways (both=True). Without dir,
    build123d extrudes along the face's normal, and a Polygon's normal depends on which way its points go round: a profile
    mirrored by a sign turns the other way and extrudes backwards"""
    found = []
    for f in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        for n in ast.walk(ast.parse(open(f, encoding="utf-8").read())):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "extrude"
                    and not any(k.arg == "dir" or (k.arg == "both" and getattr(k.value, "value", None) is True)
                                for k in n.keywords)):
                found.append(f"{os.path.basename(f)}:{n.lineno}")
    return found


def disagree(doubts):
    """The overlaps that OCC and the meshes measured differently (checks_overlap), for the end of a model's line"""
    return "" if not doubts else "  OCC and mesh disagree (check fails): " + "; ".join(doubts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "models"))
    ap.add_argument("--board-step", action="append", default=[], metavar="PATH",
                    help="a board's official 3D model (STEP, or STL for one published only as STL), used for the board interference check in place of the simplified board. "
                         "Repeat for several models; the file name tells which board it is (official_models in boards/<board>.json). Not put in viewer.html")
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
        if bad := undirected_extrudes():
            sys.exit("extrude() without dir= or both=True, so its direction follows the face's normal: " + ", ".join(bad))
        import checks_print as cp, checks_time as ct, checks_overlap as co
    boards_chk = {B.name: [("board", [B.ghost()])] for B in boards}   # what the board overlap is measured against (board frame)
    official = {}
    for p in a.board_step:
        B, solids = sb.official(p)
        official.setdefault(B.name, []).append((os.path.basename(p), solids))
    boards_chk.update((n, v) for n, v in official.items() if n in boards_chk)
    frames = {s: sb.mount_frames(s, 300) for s in a.mount}
    models = []; ghosts = {}; cradles = {}; failed = []; n_checked = 0
    for B in [B for B in boards if B.cradle()]:   # a board with no mounting holes snaps into a cradle that is screwed on
        n, c = f"{B.name}_cradle", B.cradle()
        write(c, a.format, a.out, n)
        bb = c.bounding_box()
        line = f"{n:40s} size {[round(x, 1) for x in (bb.size.X, bb.size.Y, bb.size.Z)]} mm  volume {round(c.volume / 1000, 1)} cm3"
        if a.check:
            hits = []; doubts = []; bad = len(c.solids()) != 1
            for lab, gs in boards_chk[B.name]:
                v, ar = overlap(B.cradle_placed(), gs, doubts, lab)
                hits.append(f"{lab} overlap {v:.2f} mm3" + ("" if all(g.solids() for g in gs) else f" + {ar:.2f} mm2 of surface"))
                bad |= round(v, 2) > 0 or round(ar, 2) > 0
            unsup = cp.unsupported(c)[0]
            bad |= unsup > 0 or bool(doubts)
            line += (f"  {'  '.join(hits)}  unsupported {unsup} mm2  ~{ct.estimate(c)['min']} min"
                     + ("" if len(c.solids()) == 1 else f"  {len(c.solids())} separate solids (must be 1)")
                     + disagree(doubts))
            n_checked += 1
            if bad:
                failed.append(n)
        print(line)
        boards_chk[B.name] = [(lab, gs + [B.cradle_placed()]) for lab, gs in boards_chk[B.name]]   # the brackets must clear it too
    for B, orient, series, spacer in [(B, o, se, sp) for B in boards for o in a.orient for se in a.mount for sp in (False, True)
                                       if o in sb.SPACER_ORIENTS or not sp]:   # flat and shelf: no integrated standoffs
        n = model_id(B, series, spacer, orient)
        M = sb.place(B, orient, series)
        gk = B.name if orient == sb.UPRIGHT else f"{B.name}_{sb.mount_tag(series)}_{orient}"   # board shown with this model
        if viewer and gk not in ghosts:
            ghosts[gk] = mesh(Compound([M * B.ghost()]), 0.3)
            if B.cradle():
                cradles[gk] = mesh(M * B.cradle_placed())
        s = B.bracket(series, spacer, orient)
        write(s, a.format, a.out, n)
        bb = s.bounding_box()
        m = dict(id=n, name=B.name, title=B.title, series=series, mount=sb.mount_label(series), spacer=spacer,
                 orient=orient, orient_label=sb.ORIENTS[orient], ghost=gk, cradle=f"{B.name}_cradle" if B.cradle() else None,
                 size=[round(x, 1) for x in (bb.size.X, bb.size.Y, bb.size.Z)], vol=round(s.volume / 1000, 1), min=None,
                 hole_d=B.hole_d, boss=(dict(B.standoffs, n=len(B.spacer_xy())) if spacer else None))
        line = f"{n:40s} size {m['size']} mm  volume {m['vol']} cm3"
        if a.check:
            hit_frame = []; loose = []; doubts = []
            for lab, fr in frames[series]:
                hit_frame.append(co.common_volume(s, fr, doubts, lab))
                loose += [f"{d} on the {lab}" for d, v in RETAIN.items()
                          if round(co.common_volume(Pos(*v) * s, fr, doubts, f"moved {d} on the {lab}"), 2) <= 0]
            hits = []; bad = any(round(v, 2) > 0 for v in hit_frame) or len(s.solids()) != 1 or bool(loose)
            for lab, gs in boards_chk[B.name]:
                v, ar = overlap(s, [M * g for g in gs], doubts, lab)
                hits.append(f"{lab} overlap {v:.2f} mm3" + ("" if all(g.solids() for g in gs) else f" + {ar:.2f} mm2 of surface"))
                bad |= round(v, 2) > 0 or round(ar, 2) > 0
            if orient.startswith("flat"):              # the plate lies on the frame: the screw heads have to sink into it
                v, _ = overlap(s, [M * h for h in B.flat_heads()], doubts, "flat head screws")
                hits.append(f"flat head screws overlap {v:.2f} mm3")
                bad |= round(v, 2) > 0
            hit_board = "  ".join(hits)
            unsup = cp.unsupported(s)[0]
            bad |= unsup > 0
            m["min"] = ct.estimate(s)["min"]
            line += (f"  frame overlap {hit_frame[0]:.2f}" + "".join(f" ({lab} {v:.2f})" for (lab, _), v in zip(frames[series][1:], hit_frame[1:]))
                     + ("  held" if not loose else f"  not held: comes off when moved {RETAIN_D} mm " + ", ".join(loose))
                     + f"  {hit_board}  unsupported {unsup} mm2  ~{m['min']} min"
                     + ("" if len(s.solids()) == 1 else f"  {len(s.solids())} separate solids (must be 1)"))
            if series == "DIN":
                spring = sb.din_spring_hit(s, doubts)
                bad |= round(spring, 2) > 0
                line += f"  leaf spring travel {sb.din_spring_travel():.2f} mm overlap {spring:.2f} mm3"
            bad |= bool(doubts)
            line += disagree(doubts)
            n_checked += 1
            if bad:
                failed.append(n)
        print(line)
        if viewer:
            m["mesh"] = mesh(s)
        models.append(m)
    if a.coupons:
        for series in [x for x in a.mount if x != "DIN"]:
            for i, fit in enumerate(sb.COUPON_FITS):
                export_stl(sb.coupon(series, fit, i + 1), os.path.join(a.out, f"fit_test_{series}{series}_{i + 1}.stl"))
        print("Coupons: fit_test_*_1 = clearance 0.00 mm, _2 = 0.05 mm (same as the brackets), _3 = 0.10 mm. Told apart by the number of notches")
    if viewer:
        # Boards in the viewer are built only from the simplified shapes, which can be distributed. The official 3D models from
        # --board-step are used only for interference checks; not even a converted shape goes into viewer.html
        # (so the manufacturers' CAD data is not redistributed)
        data = dict(frames={s: mesh(sb.mount_frame(s, 260), 0.2) for s in a.mount},
                    ghosts=ghosts,
                    cradles=cradles,
                    models=models)
        tpl = open(os.path.join(HERE, "viewer.tpl.html"), encoding="utf-8").read()
        three = open(os.path.join(HERE, "vendor", "three.min.js"), encoding="utf-8").read()
        orbit = open(os.path.join(HERE, "vendor", "OrbitControls.js"), encoding="utf-8").read()
        lic = open(os.path.join(HERE, "vendor", "LICENSE-three.txt"), encoding="utf-8").read().strip()
        html = (tpl.replace("__THREE_LICENSE__", lic)
                   .replace("__THREE__", three.replace("</script", "<\\/script"))
                   .replace("__ORBIT__", orbit.replace("</script", "<\\/script"))
                   # The data comes from the board definitions; "<" escaped so that no string in it can close the <script>
                   .replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")))
        open(os.path.join(a.out, "viewer.html"), "w", encoding="utf-8").write(html)
        print("Wrote viewer.html")
    if a.check:
        if failed:
            sys.exit(f"Checks failed for {len(failed)} of {n_checked} models: " + ", ".join(failed))
        print(f"Checks passed for all {n_checked} models")


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
