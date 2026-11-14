"""アルミフレーム(20x20 / 40x40、溝幅6)用 SBC L字ブラケット。ネジ無しでフレームに付く。

座標(ブラケット局所座標、単位 mm)
  x : 上下方向。0 がフレームの中心の高さ
  y : 前後方向。0 がフレーム正面、フレームは y<0 側、基板は y>0 側
  z : レール方向。造形時はこの向きが上になり、z = Z0 の面(前板の外側)が造形面に付く

構成
  - 掴み部(爪2本 + 正面の溝に入るキー + 背板)は全機種共通
  - 前板は基板と同じ大きさ。穴・肉抜き・SDカード用の切り欠きは機種ごと
  - spacer=True で、前板にスペーサー(ボス)を一体で立てる
"""
import sys
from build123d import (Polygon, Circle, Rectangle, Box, Cylinder, Pos, Rot, Plane, RectangleRounded,
                       extrude, fillet, chamfer, Axis, import_step)

# ======================= 共通の道具 =======================
SLOT_X = {20: [0.0], 40: [-10.0, 10.0]}          # フレーム1面あたりの溝の中心


def prism(pts, L):
    """XY 断面の多角形を Z 方向に長さ L で押し出す(Z 中心合わせ)"""
    return extrude(Polygon(*pts, align=None), L / 2, both=True)


def mirror_x(pts):
    return [(-x, y) for x, y in reversed(pts)]


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def xz_prism(pts_xz, y0, y1):
    """(x, z) 断面を Y 方向に押し出す"""
    return Pos(0, (y0 + y1) / 2, 0) * (Rot(90, 0, 0) * prism(pts_xz, y1 - y0))


def frame(series, L=120.0):
    """アルミフレームの簡略形状(干渉確認・表示用)。溝は隅の斜めリブを見込んだ安全側の形"""
    S = float(series)
    sk = fillet(Rectangle(S, S).vertices(), 1.0)
    slot = [(-3, 0.01), (3, 0.01), (3, -2), (6, -2), (6, -3), (3, -6), (-3, -6), (-6, -3), (-6, -2), (-3, -2)]
    for ang in (0, 90, 180, 270):
        for sx in SLOT_X[series]:
            sk -= Rot(0, 0, ang) * Pos(sx, S / 2) * Polygon(*slot, align=None)
    for cx in SLOT_X[series]:
        for cy in SLOT_X[series]:
            sk -= Pos(cx, cy) * Circle(2.1)
    return Pos(0, -S / 2, -L / 2) * extrude(sk, L)


# ---- DIN レール TS35 x 7.5(EN 60715) ----
DIN_W, DIN_D, DIN_T, DIN_BASE = 35.0, 7.5, 1.0, 27.0   # 幅、奥行き、板厚、ハットの底の外幅


def din_rail(L=120.0):
    """DIN レールの簡略形状(干渉確認・表示用)。正面(リップの前面)が y=0、背面のパネル側が y=-7.5"""
    hb = DIN_BASE / 2; hw = DIN_W / 2
    r = box(-hw, -(hb - DIN_T), -DIN_T, 0, -L / 2, L / 2) + box(hb - DIN_T, hw, -DIN_T, 0, -L / 2, L / 2)   # リップ
    r += box(-hb, -(hb - DIN_T), -DIN_D, 0, -L / 2, L / 2) + box(hb - DIN_T, hb, -DIN_D, 0, -L / 2, L / 2)  # 側壁
    r += box(-hb, hb, -DIN_D, -DIN_D + DIN_T, -L / 2, L / 2)                                              # 底
    return r


def mount_frame(series, L=120.0):
    """取付先の形状(series = 20 / 40 / "DIN")"""
    return din_rail(L) if series == "DIN" else frame(series, L)


def mount_tag(series):
    return "DIN35" if series == "DIN" else f"{series}{series}"


def mount_label(series):
    return "DINレール(TS35)" if series == "DIN" else f"{series}角フレーム"


def world():
    """局所座標 → 表示用の座標(横レール: フレーム軸 = X、正面 = +Y、上 = +Z)"""
    return Plane(origin=(0, 0, 0), x_dir=(0, 0, 1), z_dir=(-1, 0, 0)).location


# ======================= 掴み部(全機種共通) =======================
T = 3.0                  # 前板と背板の厚み
W = 16.0                 # レール方向の幅(造形時の高さ)
Z0 = -W / 2              # 造形面
ARM_T = 1.6              # 爪の腕の付け根の厚み
ARM_TIP = 0.9            # 腕の先(返しの手前)の厚み。先細りにして押し込み時のひずみを下げる
TAB = 3.0                # 指掛け
HOOK = 1.0               # 返しの高さ(掛かり)
FIT = 0.05               # フレームとのすきま(片側)
ROOT_C = 0.4             # 腕の付け根の面取り
KEY_D = 1.8              # 正面の溝に入るキーの深さ
BOARD_Y0 = 4.0           # 背板の前面から基板の後端まで
FIL = 4.0                # 背板と前板の内隅の補強
WIN_R = 3.0; RIB = 6.0; CORNER_R = 3.5; BED_CHAMFER = 0.5


def arm(hw, fit=FIT):
    """爪。背板の裏から直接出て、フレームの上(下)面を後ろへ伸び、溝の縁に掛かる。バネ用の隙間は無い"""
    xi = hw + fit; xe = xi + 1.8
    return [(xi - ROOT_C, 0.01), (xi, -ROOT_C), (xi, -7.0), (xi - HOOK, -7.0), (xi - HOOK, -8.8), (xi + 0.4, -10.6),
            (xe + TAB, -10.6), (xe + TAB, -8.6), (xe, -8.6), (xe, -7.0), (xi + ARM_TIP, -6.0), (xi + ARM_T, 0.01)]


def grip(series, fit=FIT, h=W):
    """フレームを掴む部分(上下同形の爪2本 + 正面の溝に入るキー)。背板の裏面 y=0 に付く"""
    hw = series / 2; k = 3.0 - fit - 0.05
    g = prism(arm(hw, fit), h) + prism(mirror_x(arm(hw, fit)), h)
    for sx in SLOT_X[series]:
        g += prism([(sx - k, 0.01), (sx + k, 0.01), (sx + k, -KEY_D + 0.5), (sx + k - 0.5, -KEY_D),
                    (sx - k + 0.5, -KEY_D), (sx - k, -KEY_D + 0.5)], h)
    return g


# ---- DIN 用の掴み部 ----
DIN_FIT = 0.05           # リップの縁とのすきま(片側)
DIN_HOOK = 0.8           # リップの裏に掛かる量
DIN_LEAF_T = 1.2         # 板バネの厚み
DIN_LEAF_BACK = 2.6      # 板バネがリップの裏へ回り込む深さ
DIN_SLIT = 0.5           # 板バネと背板を分けるすきま
DIN_NOSE_H = 7.0         # 爪(返し)の高さ方向の長さ。板バネの先端側だけに付ける
DIN_KEY_HALF = 12.2      # 中央の溝(側壁の内側、幅約25mm)に入るキーの半幅
DIN_KEY_D = 2.0


def din_leaf_x():
    return DIN_W / 2 + DIN_FIT


def grip_din(h=W):
    """DIN レール用の掴み部。上下同形。
    - 中央のキーがハットの溝(側壁の間)に入り、上下方向の重さを受ける
    - 両側の板バネがリップの縁の外を通り、先端の爪がリップの裏に掛かる。板バネはレール方向(造形の高さ方向)に伸びた片持ちで、
      上下方向(x)にしなる。背板とはすきま DIN_SLIT で分かれ、造形面側の T だけでつながる"""
    xl = din_leaf_x(); g = None
    k = DIN_KEY_HALF
    g = prism([(-k, 0.01), (k, 0.01), (k, -DIN_KEY_D + 0.5), (k - 0.5, -DIN_KEY_D), (-k + 0.5, -DIN_KEY_D), (-k, -DIN_KEY_D + 0.5)], h)
    for sg in (1, -1):
        leaf = [(xl, -DIN_LEAF_BACK), (xl + DIN_LEAF_T, -DIN_LEAF_BACK), (xl + DIN_LEAF_T, 0.01), (xl, 0.01)]
        nose = [(xl + 0.01, -DIN_T - DIN_FIT), (xl - DIN_HOOK, -DIN_T - DIN_FIT), (xl - DIN_HOOK, -DIN_T - DIN_FIT - 0.6), (xl + 0.01, -DIN_LEAF_BACK)]
        if sg < 0:
            leaf = mirror_x(leaf); nose = mirror_x(nose)
        g += prism(leaf, h)
        z1 = h / 2; z0 = z1 - DIN_NOSE_H
        cut = [(xl + 0.01, z0), (xl + 0.01, z1 + 1), (xl - 1.0, z1 + 1), (xl - 1.0, z0 + 1.01)]   # 爪の下面を45度にする
        if sg < 0:
            cut = [(-x, z) for x, z in reversed(cut)]
        g += (Pos(0, 0, (z0 + z1) / 2) * prism(nose, z1 - z0)) & xz_prism(cut, -DIN_LEAF_BACK - 0.1, 0.1)
    return g


def din_slits(s, H):
    """板バネの両脇で、背板と内隅の補強を切り離す(造形面側の T は残す)"""
    xl = din_leaf_x()
    for sg in (1, -1):
        for a, b in ((xl - DIN_SLIT, xl), (xl + DIN_LEAF_T, xl + DIN_LEAF_T + DIN_SLIT)):
            s -= box(*sorted((sg * a, sg * b)), -0.01, T + FIL + 0.1, Z0 + T, W / 2 + 1)
        # 板バネの前にある内隅の補強も取り除く(板バネの根元を造形面側の T だけにする)
        s -= box(*sorted((sg * (xl - DIN_SLIT), sg * (xl + DIN_LEAF_T + DIN_SLIT))), T, T + FIL + 0.1, Z0 + T, W / 2 + 1)
    return s


def coupon(series, fit, mark):
    """はめあい確認用の試験片(高さ6mm)。mark 個の切り欠きで区別する"""
    hw = series / 2; xe = hw + fit + ARM_T + TAB + 1.0; h = 6.0
    c = prism([(-xe, 0), (xe, 0), (xe, T), (-xe, T)], h) + grip(series, fit, h)
    for i in range(mark):
        c -= box(-xe + 2.5 + 3.0 * i, -xe + 4.0 + 3.0 * i, T - 1.0, T + 1, -h, h)
    return c


def rrect(x0, x1, y0, y1, rad=WIN_R):
    """前板を貫通する角丸の抜き型"""
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, Z0 - 1) * extrude(RectangleRounded(x1 - x0, y1 - y0, rad), T + 2)


def _l_body(series, H, depth):
    """掴み部 + 背板 + 前板 + 内隅の補強。H = 前板の半高さ、depth = 背板から前板の先まで"""
    s = grip_din() if series == "DIN" else grip(series)
    s += box(-H, H, 0.0, T, -W / 2, W / 2)
    s += box(-H, H, T - 0.01, T + depth, Z0, Z0 + T)
    y1 = T - 0.01; z1 = Z0 + T - 0.01
    s += Rot(0, -90, 0) * prism([(z1, y1), (z1, y1 + FIL), (z1 + FIL, y1)], 2 * H)
    if series == "DIN":
        s = din_slits(s, H)
    return s


def _finish(s, series, H, yo):
    """外側の角R、爪の根元より外の背板を低くする、造形面の外周の面取り"""
    for sg in (1, -1):
        cx = sg * (H - CORNER_R); cy = yo - CORNER_R
        s -= box(*sorted((cx, sg * (H + 1))), cy, yo + 1, Z0 - 1, Z0 + T + 1) - Pos(cx, cy, Z0 + T / 2) * Cylinder(CORNER_R, T + 4)
    xr = (din_leaf_x() + DIN_LEAF_T + DIN_SLIT + 2.0) if series == "DIN" else (series / 2 + FIT + ARM_T + 2.0)
    zl = Z0 + T + FIL + 1.0; drop = W / 2 - zl
    if H - xr > 1.0:
        for sg in (1, -1):
            pts = [(sg * xr, W / 2 + 0.1), (sg * (H + 0.1), W / 2 + 0.1), (sg * (H + 0.1), zl), (sg * (xr + drop), zl)]
            s -= xz_prism(pts if sg > 0 else list(reversed(pts)), -0.02, T + 0.005)
    outer = [e for e in s.edges().group_by(Axis.Z)[0] if e.center().Y > 1.0]   # 爪の細い先端は除く
    for c in (BED_CHAMFER, 0.3):
        try:
            return chamfer(outer, c)
        except Exception as e:
            print("chamfer", c, "failed", str(e)[:50], file=sys.stderr)
    return s


def add_spacers(s, pts, h, d_boss, d_pilot):
    """前板にスペーサー(ボス)を一体で立てる。前板の穴を埋めてからボスを立て、ネジの下穴をあけ直す"""
    for x, y in pts:
        s += Pos(x, y, Z0 + (T + h) / 2) * Cylinder(d_boss / 2, T + h - 0.01)
    for x, y in pts:
        s -= Pos(x, y, Z0 + (T + h) / 2) * Cylinder(d_pilot / 2, T + h + 2)
    return s


# ======================= Raspberry Pi 4 =======================
class Pi4:
    name, title = "Pi4", "Raspberry Pi 4"
    L, S = 85.0, 56.0                                  # 基板外形
    HOLE_L, HOLE_S = (3.5, 61.5), (3.5, 52.5)          # 取付穴(長辺方向, 短辺方向)
    HOLE_D = 3.0                                       # スペーサー無し版の穴径
    SD_DEPTH = 19.0
    SPACER = dict(h=5.0, d=6.0, pilot=2.2, screw="M2.5")
    BOARD_SPACER = 5.0                                 # 表示・干渉確認で基板を載せる高さ

    @classmethod
    def holes(cls, flip=False):
        """flip=True はポート上向き用の組。長辺方向に 20mm ずれる"""
        return [((cls.L - l) if flip else l, s) for l in cls.HOLE_L for s in cls.HOLE_S]

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + s)

    @classmethod
    def bracket(cls, series, spacer=False):
        H = cls.L / 2
        s = _l_body(series, H, BOARD_Y0 + cls.S)
        for flip in (False, True):                     # 穴2組(ポート下 / ポート上)
            for l, s_ in cls.holes(flip):
                x, y = cls.xy(l, s_)
                s -= Pos(x, y, Z0 + T / 2) * Cylinder(cls.HOLE_D / 2, T + 2)
        yb = T + BOARD_Y0; yc = yb + 28.0; xn = H - cls.SD_DEPTH
        y0w = yb + 3.5 + 6.0 / 2 + 4.0; y1w = 2 * yc - y0w
        for sg in (1, -1):                             # 両端の開口 = SDカード用の切り欠き
            s -= rrect(*sorted((sg * xn, sg * (2 * H - xn + 4))), y0w, y1w)
        for x0, x1 in ((-(xn - RIB), -RIB / 2), (RIB / 2, xn - RIB)):
            s -= rrect(x0, x1, y0w, y1w)
        s = _finish(s, series, H, yb + cls.S)
        if spacer:                                     # スペーサーはポート下向きの1組(4個)だけ
            sp = cls.SPACER
            s = add_spacers(s, [cls.xy(l, s_) for l, s_ in cls.holes(False)], sp["h"], sp["d"], sp["pilot"])
        return s

    @classmethod
    def ghost(cls):
        """表示・干渉確認用の基板(簡略)。GPIO 側を背板寄り、USB/LAN を上端に置く"""
        to = lambda l, s, h: (cls.L / 2 - l, T + BOARD_Y0 + (cls.S - s), Z0 + T + cls.BOARD_SPACER + h)
        def blk(l0, l1, s0, s1, h0, h1):
            a, b = to(l0, s0, h0), to(l1, s1, h1)
            return box(min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), min(a[2], b[2]), max(a[2], b[2]))
        g = blk(0, cls.L, 0, cls.S, 0, 1.6)
        g += blk(64, 87, 2, 54, 1.6, 17.6)             # USB / LAN
        g += blk(7, 58, 49, 54.5, 1.6, 10.1)           # GPIO
        return g


# ======================= Raspberry Pi Zero =======================
class PiZero:
    name, title = "PiZero", "Raspberry Pi Zero"
    L, S, BT = 65.0, 30.0, 1.6
    HOLES = [(3.5, 3.5), (3.5, 26.5), (61.5, 3.5), (61.5, 26.5)]   # 58 x 23。上下左右対称なので1組で両向きに付く
    HOLE_D = 3.0
    SD_DEPTH = 15.0
    WIN_M = 2.5
    SPACER = dict(h=3.0, d=6.0, pilot=2.2, screw="M2.5")
    BOARD_SPACER = 3.0

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + (cls.S - s))      # GPIO 側(s 大)を背板寄り、ポート側を外向き

    @classmethod
    def bracket(cls, series, spacer=False):
        H = cls.L / 2
        s = _l_body(series, H, BOARD_Y0 + cls.S)
        for l, s_ in cls.HOLES:
            x, y = cls.xy(l, s_)
            s -= Pos(x, y, Z0 + T / 2) * Cylinder(cls.HOLE_D / 2, T + 2)
        yb = T + BOARD_Y0
        y0w = yb + 3.5 + cls.HOLE_D / 2 + cls.WIN_M; y1w = yb + cls.S - 3.5 - cls.HOLE_D / 2 - cls.WIN_M
        xn = H - cls.SD_DEPTH
        for sg in (1, -1):
            s -= rrect(*sorted((sg * xn, sg * (H + 4))), y0w, y1w)
        for x0, x1 in ((-(xn - RIB), -RIB / 2), (RIB / 2, xn - RIB)):
            s -= rrect(x0, x1, y0w, y1w)
        s = _finish(s, series, H, yb + cls.S)
        if spacer:
            sp = cls.SPACER
            s = add_spacers(s, [cls.xy(l, s_) for l, s_ in cls.HOLES], sp["h"], sp["d"], sp["pilot"])
        return s

    @classmethod
    def ghost(cls):
        """表示・干渉確認用の基板(簡略)と microSD"""
        def blk(l0, l1, s0, s1, h0, h1):
            xa, ya = cls.xy(l0, s0); xb, yb_ = cls.xy(l1, s1)
            za, zb = Z0 + T + cls.BOARD_SPACER + h0, Z0 + T + cls.BOARD_SPACER + h1
            return box(min(xa, xb), max(xa, xb), min(ya, yb_), max(ya, yb_), za, zb)
        t = cls.BT
        g = blk(0, cls.L, 0, cls.S, 0, t)
        g += blk(6.8, 18.0, -0.5, 7.5, t, t + 3.5)             # mini HDMI
        g += blk(37.4, 45.4, -1.0, 5.0, t, t + 3.0)            # micro USB(データ)
        g += blk(50.0, 58.0, -1.0, 5.0, t, t + 3.0)            # micro USB(電源)
        g += blk(7.1, 58.0, 25.2, 27.8 + 2.54, t, t + 8.5)     # GPIO ヘッダ(実装した場合)
        g += blk(61.0, 66.0, 7.0, 23.0, t, t + 1.3)            # カメラコネクタ
        g += blk(-2.5, 12.0, 11.5, 22.5, t, t + 1.4)           # microSD(位置は仮定)
        return g


# ======================= Khadas VIM1S =======================
class VIM1S:
    """寸法は Khadas 公式3Dモデル vim1s-pcba-3d-v11.stp から取得"""
    name, title = "VIM1S", "Khadas VIM1S"
    L, S, BT = 82.0, 56.638, 1.21
    HOLES = [(2.5, 3.134), (79.5, 3.134), (16.5, 48.634), (65.5, 48.634)]   # 台形配置(77 / 49 / 45.5)。s=0 が GPIO 側
    HOLE_D = 3.0
    SD_L0, SD_L1, SD_S0 = 32.0, 55.0, 46.0             # microSD 用の切り欠き(ポート側の辺の中央、基板の裏)
    WIN_S0, WIN_S1 = 7.5, 41.0
    SPACER = dict(h=5.0, d=5.0, pilot=1.7, screw="M2")  # 裏面の LAN が基板下面から 3.5mm 出るので 5mm
    BOARD_SPACER = 5.0
    STEP_X0, STEP_Y0, STEP_ZTOP = -5.84, -62.952, 0.005  # 公式3Dモデル上の基板の左下と上面

    @classmethod
    def xy(cls, l, s):
        return (l - cls.L / 2, T + BOARD_Y0 + s)

    @classmethod
    def bracket(cls, series, spacer=False):
        H = cls.L / 2
        s = _l_body(series, H, BOARD_Y0 + cls.S)
        for l, s_ in cls.HOLES:
            x, y = cls.xy(l, s_)
            s -= Pos(x, y, Z0 + T / 2) * Cylinder(cls.HOLE_D / 2, T + 2)
        l0, l1 = 6.0, cls.L - 6.0; wl = (l1 - l0 - 2 * RIB) / 3
        for i in range(3):                             # 肉抜き窓3つ
            a = l0 + i * (wl + RIB)
            (xa, ya), (xb, yb2) = cls.xy(a, cls.WIN_S0), cls.xy(a + wl, cls.WIN_S1)
            s -= rrect(xa, xb, ya, yb2)
        yo = T + BOARD_Y0 + cls.S
        (xa, ya), (xb, _) = cls.xy(cls.SD_L0, cls.SD_S0), cls.xy(cls.SD_L1, 0)
        s -= rrect(xa, xb, ya, yo + 4)                 # microSD 用の切り欠き(外側の辺に開く)
        s = _finish(s, series, H, yo)
        if spacer:
            sp = cls.SPACER
            s = add_spacers(s, [cls.xy(l, s_) for l, s_ in cls.HOLES], sp["h"], sp["d"], sp["pilot"])
        return s

    @classmethod
    def ghost(cls, step_path=None):
        """公式3Dモデルがあればそれを、無ければ基板の板だけを返す(ブラケットの形状には影響しない)"""
        loc = Pos(-cls.STEP_X0 - cls.L / 2, T + BOARD_Y0 - cls.STEP_Y0, Z0 + T + cls.BOARD_SPACER + cls.BT - cls.STEP_ZTOP)
        if step_path:
            return [c for c in (loc * import_step(step_path)).solids() if c.volume > 0.5]
        z = Z0 + T + cls.BOARD_SPACER
        return [box(-cls.L / 2, cls.L / 2, T + BOARD_Y0, T + BOARD_Y0 + cls.S, z, z + cls.BT)]


BOARDS = [Pi4, PiZero, VIM1S]
SERIES = (20, 40, "DIN")
