"""全モデル(3機種 x 20角・40角・DINレール x スペーサー無し/一体)の 3MF・STEP と、HTML ビューアを生成する。

使い方:
  python build_all.py                          # models/ に 18モデル x (3MF + STEP) と viewer.html を出力
  python build_all.py --vim1s-step vim1s-pcba-3d-v11.stp   # ビューアと干渉検査に VIM1S の公式3Dモデルを使う
  python build_all.py --check                  # フレーム・基板との干渉、サポートの要否、印刷時間の見積もりも出す
  python build_all.py --coupons                # はめあい確認用の試験片(すきま 0.00 / 0.05 / 0.10mm)も出力
  python build_all.py --only Pi4 --series 20 DIN   # 一部だけ(20 / 40 / DIN)

必要なもの: Python 3.10 以上、build123d(--check を付ける場合は trimesh、shapely も)
"""
import argparse, json, os, sys
from build123d import Pos, Compound, Mesher, export_step, export_stl
import sbc_brackets as sb

HERE = os.path.dirname(os.path.abspath(__file__))
BED = 256.0                                   # 3MF を置く造形面の大きさ(中央に置く)


def model_id(B, series, spacer):
    return f"{B.name}_{sb.mount_tag(series)}" + ("_spacer" if spacer else "")


def write_3mf(shape, path, name):
    bb = shape.bounding_box()
    p = Pos(BED / 2 - (bb.min.X + bb.max.X) / 2, BED / 2 - (bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape   # 造形向きのまま中央へ
    m = Mesher(); m.add_shape(p, linear_deflection=0.02, angular_deflection=0.2, part_number=name); m.write(path)


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
    ap.add_argument("--vim1s-step", default=None, help="Khadas 公式の vim1s-pcba-3d-v11.stp のパス(任意)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--coupons", action="store_true")
    ap.add_argument("--no-viewer", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="Pi4 / PiZero / VIM1S")
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
                export_step(s, os.path.join(a.out, n + ".step"))
                bb = s.bounding_box()
                m = dict(id=n, name=B.name, title=B.title, series=series, mount=sb.mount_label(series), spacer=spacer,
                         size=[round(x, 1) for x in (bb.size.X, bb.size.Y, bb.size.Z)], vol=round(s.volume / 1000, 1), min=None,
                         boss=(dict(B.SPACER) if spacer else None))
                line = f"{n:22s} 外形 {m['size']} mm  体積 {m['vol']} cm3"
                if a.check:
                    fr = frames[series]
                    hit_frame = (s & fr).volume
                    hit_board = sum((s & g).volume for g in ghosts[B.name])
                    unsup = cp.unsupported(s)[0]
                    m["min"] = ct.estimate(s)["min"]
                    line += f"  フレーム干渉 {hit_frame:.2f}  基板干渉 {hit_board:.2f} mm3  支え無し {unsup} mm2  約{m['min']}分"
                print(line)
                if not a.no_viewer:
                    m["mesh"] = mesh(s)
                models.append(m)
    if a.coupons:
        for series in [x for x in a.series if x != "DIN"]:
            for i, fit in enumerate((0.0, 0.05, 0.10)):
                export_stl(sb.coupon(series, fit, i + 1), os.path.join(a.out, f"fit_test_{series}{series}_{i + 1}.stl"))
        print("試験片: fit_test_*_1 = すきま 0.00mm、_2 = 0.05mm(本体と同じ)、_3 = 0.10mm。切り欠きの数で区別")
    if not a.no_viewer:
        data = dict(frames={s: mesh(sb.mount_frame(s, 260), 0.2) for s in a.series},
                    ghosts={B.name: mesh(Compound([g for g in ghosts[B.name] if g.volume > 3.0]), 0.6 if B is sb.VIM1S else 0.3,
                                         1 if B is sb.VIM1S else 2) for B in boards},
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
        print("viewer.html を出力しました")


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
