"""L-shaped SBC brackets for aluminium extrusion (20x20 / 40x40, 6 mm slot). They clip onto the frame without screws.

Coordinates (bracket-local, in mm)
  x : vertical. 0 is the height of the frame centre
  y : front-back. 0 is the front face of the frame; the frame is on the y<0 side, the board on the y>0 side
  z : along the rail. This axis points up when printing; the z = Z0 face (outside of the front plate) sits on the build plate

Structure
  - The grip (two hooks + a key that sits in the front slot + the back plate) is shared by every board
  - The front plate is the same size as the board. Holes, cut-outs and the SD card notch are per board
  - spacer=True adds standoffs (bosses) integrated into the front plate
"""
import sys
from build123d import (Polygon, Circle, Rectangle, Box, Cylinder, Pos, Rot, Plane, RectangleRounded,
                       extrude, fillet, chamfer, Axis, import_step)

# ======================= Common helpers =======================
SLOT_X = {20: [0.0], 40: [-10.0, 10.0]}          # slot centres on each face of the frame


def prism(pts, L):
    """Extrude a polygon in the XY plane by L along Z (centred on Z)"""
    return extrude(Polygon(*pts, align=None), L / 2, both=True)


def mirror_x(pts):
    return [(-x, y) for x, y in reversed(pts)]


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def xz_prism(pts_xz, y0, y1):
    """Extrude an (x, z) profile along Y"""
    return Pos(0, (y0 + y1) / 2, 0) * (Rot(90, 0, 0) * prism(pts_xz, y1 - y0))


def frame(series, L=120.0):
    """Simplified aluminium extrusion (for interference checks and display). The slot shape allows for the diagonal ribs in the corners, erring on the safe side"""
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


# ---- DIN rail TS35 x 7.5 (EN 60715) ----
DIN_W, DIN_D, DIN_T, DIN_BASE = 35.0, 7.5, 1.0, 27.0   # width, depth, sheet thickness, outer width of the hat's base


def din_rail(L=120.0):
    """Simplified DIN rail (for interference checks and display). The front (front face of the lips) is y=0, the back (panel side) is y=-7.5"""
    hb = DIN_BASE / 2; hw = DIN_W / 2
    r = box(-hw, -(hb - DIN_T), -DIN_T, 0, -L / 2, L / 2) + box(hb - DIN_T, hw, -DIN_T, 0, -L / 2, L / 2)   # lips
    r += box(-hb, -(hb - DIN_T), -DIN_D, 0, -L / 2, L / 2) + box(hb - DIN_T, hb, -DIN_D, 0, -L / 2, L / 2)  # side walls
    r += box(-hb, hb, -DIN_D, -DIN_D + DIN_T, -L / 2, L / 2)                                              # base
    return r


def mount_frame(series, L=120.0):
    """Shape of what the bracket mounts on (series = 20 / 40 / "DIN")"""
    return din_rail(L) if series == "DIN" else frame(series, L)


def mount_tag(series):
    return "DIN35" if series == "DIN" else f"{series}{series}"


def mount_label(series):
    return "DIN rail (TS35)" if series == "DIN" else f"{series}x{series} extrusion"


def world():
    """Local coordinates -> display coordinates (horizontal rail: frame axis = X, front = +Y, up = +Z)"""
    return Plane(origin=(0, 0, 0), x_dir=(0, 0, 1), z_dir=(-1, 0, 0)).location


# ======================= Grip (shared by every board) =======================
T = 3.0                  # thickness of the front plate and the back plate
W = 16.0                 # width along the rail (height when printing)
Z0 = -W / 2              # build plate
ARM_T = 1.6              # thickness of the hook arm at its root
ARM_TIP = 0.9            # thickness at the end of the arm (just before the barb). Tapered to lower the strain when pushing on
TAB = 3.0                # finger tab
HOOK = 1.0               # barb height (engagement)
FIT = 0.05               # clearance to the frame (per side)
ROOT_C = 0.4             # chamfer at the arm root
KEY_D = 1.8              # depth of the key that sits in the front slot
BOARD_Y0 = 4.0           # from the front face of the back plate to the rear edge of the board
FIL = 4.0                # gusset in the inside corner between the back plate and the front plate
WIN_R = 3.0; RIB = 6.0; CORNER_R = 3.5; BED_CHAMFER = 0.5


def arm(hw, fit=FIT):
    """Hook. Comes straight off the back of the back plate, runs back over the top (bottom) face of the frame and catches the slot edge. No gap for a spring"""
    xi = hw + fit; xe = xi + 1.8
    return [(xi - ROOT_C, 0.01), (xi, -ROOT_C), (xi, -7.0), (xi - HOOK, -7.0), (xi - HOOK, -8.8), (xi + 0.4, -10.6),
            (xe + TAB, -10.6), (xe + TAB, -8.6), (xe, -8.6), (xe, -7.0), (xi + ARM_TIP, -6.0), (xi + ARM_T, 0.01)]


def grip(series, fit=FIT, h=W):
    """The part that grips the frame (two identical hooks top and bottom + a key in the front slot). Attached to the back face of the back plate, y=0"""
    hw = series / 2; k = 3.0 - fit - 0.05
    g = prism(arm(hw, fit), h) + prism(mirror_x(arm(hw, fit)), h)
    for sx in SLOT_X[series]:
        g += prism([(sx - k, 0.01), (sx + k, 0.01), (sx + k, -KEY_D + 0.5), (sx + k - 0.5, -KEY_D),
                    (sx - k + 0.5, -KEY_D), (sx - k, -KEY_D + 0.5)], h)
    return g


# ---- Grip for DIN rail ----
DIN_FIT = 0.05           # clearance to the lip edge (per side)
DIN_HOOK = 0.8           # how far the hook reaches behind the lip
DIN_LEAF_T = 1.2         # leaf spring thickness
DIN_LEAF_BACK = 2.6      # how deep the leaf spring reaches behind the lip
DIN_SLIT = 0.5           # gap that separates the leaf spring from the back plate
DIN_NOSE_H = 7.0         # length of the hook (barb) along the rail. Only on the tip side of the leaf spring
DIN_KEY_HALF = 12.2      # half width of the key that sits in the centre channel (between the side walls, about 25 mm wide)
DIN_KEY_D = 2.0


def din_leaf_x():
    return DIN_W / 2 + DIN_FIT


def grip_din(h=W):
    """Grip for DIN rail. Identical top and bottom.
    - The centre key sits in the hat's channel (between the side walls) and takes the vertical load
    - Leaf springs on both sides pass outside the lip edges, and the hooks at their tips catch behind the lips. Each leaf spring is a cantilever
      running along the rail (the print height direction) and flexes vertically (x). It is separated from the back plate by DIN_SLIT and joined only by T on the build plate side"""
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
        cut = [(xl + 0.01, z0), (xl + 0.01, z1 + 1), (xl - 1.0, z1 + 1), (xl - 1.0, z0 + 1.01)]   # make the underside of the hook 45 degrees
        if sg < 0:
            cut = [(-x, z) for x, z in reversed(cut)]
        g += (Pos(0, 0, (z0 + z1) / 2) * prism(nose, z1 - z0)) & xz_prism(cut, -DIN_LEAF_BACK - 0.1, 0.1)
    return g


def din_slits(s, H):
    """Cut the back plate and the gusset free on both sides of each leaf spring (keeping T on the build plate side)"""
    xl = din_leaf_x()
    for sg in (1, -1):
        for a, b in ((xl - DIN_SLIT, xl), (xl + DIN_LEAF_T, xl + DIN_LEAF_T + DIN_SLIT)):
            s -= box(*sorted((sg * a, sg * b)), -0.01, T + FIL + 0.1, Z0 + T, W / 2 + 1)
        # also remove the gusset in front of the leaf spring (so the spring is rooted only in T on the build plate side)
        s -= box(*sorted((sg * (xl - DIN_SLIT), sg * (xl + DIN_LEAF_T + DIN_SLIT))), T, T + FIL + 0.1, Z0 + T, W / 2 + 1)
    return s


def coupon(series, fit, mark):
    """Fit test coupon (6 mm tall). Told apart by the number of notches (mark)"""
    hw = series / 2; xe = hw + fit + ARM_T + TAB + 1.0; h = 6.0
    c = prism([(-xe, 0), (xe, 0), (xe, T), (-xe, T)], h) + grip(series, fit, h)
    for i in range(mark):
        c -= box(-xe + 2.5 + 3.0 * i, -xe + 4.0 + 3.0 * i, T - 1.0, T + 1, -h, h)
    return c


def rrect(x0, x1, y0, y1, rad=WIN_R):
    """Rounded-rectangle cutter through the front plate"""
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, Z0 - 1) * extrude(RectangleRounded(x1 - x0, y1 - y0, rad), T + 2)


def _l_body(series, H, depth):
    """Grip + back plate + front plate + gusset. H = half height of the front plate, depth = from the back plate to the end of the front plate"""
    s = grip_din() if series == "DIN" else grip(series)
    s += box(-H, H, 0.0, T, -W / 2, W / 2)
    s += box(-H, H, T - 0.01, T + depth, Z0, Z0 + T)
    y1 = T - 0.01; z1 = Z0 + T - 0.01
    s += Rot(0, -90, 0) * prism([(z1, y1), (z1, y1 + FIL), (z1 + FIL, y1)], 2 * H)
    if series == "DIN":
        s = din_slits(s, H)
    return s


def _finish(s, series, H, yo):
    """Round the outer corners, lower the back plate outside the hook roots, chamfer the outline on the build plate"""
    for sg in (1, -1):
        cx = sg * (H - CORNER_R); cy = yo - CORNER_R
        s -= box(*sorted((cx, sg * (H + 1))), cy, yo + 1, Z0 - 1, Z0 + T + 1) - Pos(cx, cy, Z0 + T / 2) * Cylinder(CORNER_R, T + 4)
    xr = (din_leaf_x() + DIN_LEAF_T + DIN_SLIT + 2.0) if series == "DIN" else (series / 2 + FIT + ARM_T + 2.0)
    zl = Z0 + T + FIL + 1.0; drop = W / 2 - zl
    if H - xr > 1.0:
        for sg in (1, -1):
            pts = [(sg * xr, W / 2 + 0.1), (sg * (H + 0.1), W / 2 + 0.1), (sg * (H + 0.1), zl), (sg * (xr + drop), zl)]
            s -= xz_prism(pts if sg > 0 else list(reversed(pts)), -0.02, T + 0.005)
    outer = [e for e in s.edges().group_by(Axis.Z)[0] if e.center().Y > 1.0]   # skip the thin tips of the hooks
    for c in (BED_CHAMFER, 0.3):
        try:
            return chamfer(outer, c)
        except Exception as e:
            print("chamfer", c, "failed", str(e)[:50], file=sys.stderr)
    return s


def add_spacers(s, pts, h, d_boss, d_pilot):
    """Add standoffs (bosses) to the front plate. Fill the plate holes, add the bosses, then drill the pilot holes again"""
    for x, y in pts:
        s += Pos(x, y, Z0 + (T + h) / 2) * Cylinder(d_boss / 2, T + h - 0.01)
    for x, y in pts:
        s -= Pos(x, y, Z0 + (T + h) / 2) * Cylinder(d_pilot / 2, T + h + 2)
    return s


# ======================= Raspberry Pi Model B size (5, 4 B, 3 B+, 3 B, 2 B, 1 B+) =======================
class PiB:
    """85 x 56 mm, holes 58 x 49 mm, 3.5 mm from the edges. Same on the official mechanical drawings of the Raspberry Pi 5, 4 B, 3 B+, 3 B and 1 B+;
    the 2 B has "the same form factor" as the 1 B+ (official documentation)"""
    name, title = "PiB", "Raspberry Pi 5 / 4 B / 3 B+ / 3 B / 2 B / 1 B+"
    L, S = 85.0, 56.0                                  # board outline
    HOLE_L, HOLE_S = (3.5, 61.5), (3.5, 52.5)          # mounting holes (long side, short side)
    HOLE_D = 3.0                                       # hole diameter of the version without standoffs
    SD_DEPTH = 19.0
    SPACER = dict(h=5.0, d=6.0, pilot=2.2, screw="M2.5")
    BOARD_SPACER = 5.0                                 # height the board sits at, for display and interference checks

    @classmethod
    def holes(cls, flip=False):
        """flip=True is the set for ports facing up. Offset by 20 mm along the long side"""
        return [((cls.L - l) if flip else l, s) for l in cls.HOLE_L for s in cls.HOLE_S]

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + s)

    @classmethod
    def bracket(cls, series, spacer=False):
        H = cls.L / 2
        s = _l_body(series, H, BOARD_Y0 + cls.S)
        for flip in (False, True):                     # two sets of holes (ports down / ports up)
            for l, s_ in cls.holes(flip):
                x, y = cls.xy(l, s_)
                s -= Pos(x, y, Z0 + T / 2) * Cylinder(cls.HOLE_D / 2, T + 2)
        yb = T + BOARD_Y0; yc = yb + 28.0; xn = H - cls.SD_DEPTH
        y0w = yb + 3.5 + 6.0 / 2 + 4.0; y1w = 2 * yc - y0w
        for sg in (1, -1):                             # openings at both ends = SD card notch
            s -= rrect(*sorted((sg * xn, sg * (2 * H - xn + 4))), y0w, y1w)
        for x0, x1 in ((-(xn - RIB), -RIB / 2), (RIB / 2, xn - RIB)):
            s -= rrect(x0, x1, y0w, y1w)
        s = _finish(s, series, H, yb + cls.S)
        if spacer:                                     # standoffs only for the ports-down set (4 of them)
            sp = cls.SPACER
            s = add_spacers(s, [cls.xy(l, s_) for l, s_ in cls.holes(False)], sp["h"], sp["d"], sp["pilot"])
        return s

    @classmethod
    def ghost(cls):
        """Board for display and interference checks (simplified). GPIO side towards the back plate, USB/LAN at the top end"""
        to = lambda l, s, h: (cls.L / 2 - l, T + BOARD_Y0 + (cls.S - s), Z0 + T + cls.BOARD_SPACER + h)
        def blk(l0, l1, s0, s1, h0, h1):
            a, b = to(l0, s0, h0), to(l1, s1, h1)
            return box(min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), min(a[2], b[2]), max(a[2], b[2]))
        g = blk(0, cls.L, 0, cls.S, 0, 1.6)
        g += blk(64, 87, 2, 54, 1.6, 17.6)             # USB / LAN
        g += blk(7, 58, 49, 54.5, 1.6, 10.1)           # GPIO
        return g


# ======================= Raspberry Pi Model A+ size (3 A+, 1 A+) =======================
class PiA:
    """65 x 56 mm, holes 58 x 49 mm, 3.5 mm from the edges (official 3 A+ mechanical drawing, which the documentation says also applies to the 1 A+)"""
    name, title = "PiA", "Raspberry Pi 3 A+ / 1 A+"
    L, S, BT = 65.0, 56.0, 1.6
    HOLES = [(3.5, 3.5), (3.5, 52.5), (61.5, 3.5), (61.5, 52.5)]   # symmetric along the long side, so one set fits either orientation
    HOLE_D = 3.0
    SD_DEPTH = 15.0
    SPACER = dict(h=5.0, d=6.0, pilot=2.2, screw="M2.5")
    BOARD_SPACER = 5.0

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + (cls.S - s))      # GPIO side (large s) towards the back plate, ports facing out

    @classmethod
    def bracket(cls, series, spacer=False):
        H = cls.L / 2
        s = _l_body(series, H, BOARD_Y0 + cls.S)
        for l, s_ in cls.HOLES:
            x, y = cls.xy(l, s_)
            s -= Pos(x, y, Z0 + T / 2) * Cylinder(cls.HOLE_D / 2, T + 2)
        yb = T + BOARD_Y0
        y0w = yb + 3.5 + 6.0 / 2 + 4.0; y1w = yb + cls.S - (3.5 + 6.0 / 2 + 4.0)   # clear of the standoffs, as on PiB
        xn = H - cls.SD_DEPTH
        for sg in (1, -1):                             # openings at both ends = SD card notch (the board fits either way round)
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
        """Board for display and interference checks (simplified): USB-A, HDMI and the GPIO header, placed from the official 3 A+ drawing"""
        def blk(l0, l1, s0, s1, h0, h1):
            xa, ya = cls.xy(l0, s0); xb, yb_ = cls.xy(l1, s1)
            za, zb = Z0 + T + cls.BOARD_SPACER + h0, Z0 + T + cls.BOARD_SPACER + h1
            return box(min(xa, xb), max(xa, xb), min(ya, yb_), max(ya, yb_), za, zb)
        t = cls.BT
        g = blk(0, cls.L, 0, cls.S, 0, t)
        g += blk(51.0, 66.0, 24.5, 38.5, t, t + 7.0)          # USB-A (centre 31.5 mm from the HDMI edge, Z-Height 7.0)
        g += blk(24.5, 39.5, -1.0, 11.5, t, t + 6.5)          # HDMI (centre 32 mm, Z-Height 6.5)
        g += blk(7.0, 58.0, 49.0, 54.5, t, t + 8.5)           # GPIO header (Z-Height 8.5)
        return g


# ======================= Raspberry Pi Zero size (Zero, Zero W, Zero 2 W) =======================
class PiZero:
    """65 x 30 mm, holes 58 x 23 mm, 3.5 mm from the edges (official Zero W and Zero 2 W mechanical drawings; the Zero has the same holes)"""
    name, title = "PiZero", "Raspberry Pi Zero / Zero W / Zero 2 W"
    L, S, BT = 65.0, 30.0, 1.6
    HOLES = [(3.5, 3.5), (3.5, 26.5), (61.5, 3.5), (61.5, 26.5)]   # 58 x 23. Symmetric both ways, so one set fits either orientation
    HOLE_D = 3.0
    SD_DEPTH = 15.0
    WIN_M = 2.5
    SPACER = dict(h=3.0, d=6.0, pilot=2.2, screw="M2.5")
    BOARD_SPACER = 3.0

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + (cls.S - s))      # GPIO side (large s) towards the back plate, ports facing out

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
        """Board for display and interference checks (simplified), with the microSD card"""
        def blk(l0, l1, s0, s1, h0, h1):
            xa, ya = cls.xy(l0, s0); xb, yb_ = cls.xy(l1, s1)
            za, zb = Z0 + T + cls.BOARD_SPACER + h0, Z0 + T + cls.BOARD_SPACER + h1
            return box(min(xa, xb), max(xa, xb), min(ya, yb_), max(ya, yb_), za, zb)
        t = cls.BT
        g = blk(0, cls.L, 0, cls.S, 0, t)
        g += blk(6.8, 18.0, -0.5, 7.5, t, t + 3.5)             # mini HDMI
        g += blk(37.4, 45.4, -1.0, 5.0, t, t + 3.0)            # micro USB (data)
        g += blk(50.0, 58.0, -1.0, 5.0, t, t + 3.0)            # micro USB (power)
        g += blk(7.1, 58.0, 25.2, 27.8 + 2.54, t, t + 8.5)     # GPIO header (if fitted)
        g += blk(61.0, 66.0, 7.0, 23.0, t, t + 1.3)            # camera connector
        g += blk(-2.5, 12.0, 11.4, 22.4, t, t + 1.4)           # microSD (centre 16.9 mm from the port edge, official Zero W drawing)
        return g


# ======================= Khadas VIM1S =======================
class VIM1S:
    """Dimensions taken from Khadas' official 3D model vim1s-pcba-3d-v11.stp"""
    name, title = "VIM1S", "Khadas VIM1S"
    L, S, BT = 82.0, 56.638, 1.21
    HOLES = [(2.5, 3.134), (79.5, 3.134), (16.5, 48.634), (65.5, 48.634)]   # trapezoid pattern (77 / 49 / 45.5). s=0 is the GPIO side
    HOLE_D = 3.0
    SD_L0, SD_L1, SD_S0 = 32.0, 55.0, 46.0             # microSD notch (middle of the port-side edge, underside of the board)
    WIN_S0, WIN_S1 = 7.5, 41.0
    SPACER = dict(h=5.0, d=5.0, pilot=1.7, screw="M2")  # 5 mm because the LAN jack on the underside sticks out 3.5 mm below the board
    BOARD_SPACER = 5.0
    STEP_X0, STEP_Y0, STEP_ZTOP = -5.84, -62.952, 0.005  # lower-left corner and top face of the board in the official 3D model

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
        for i in range(3):                             # three lightening windows
            a = l0 + i * (wl + RIB)
            (xa, ya), (xb, yb2) = cls.xy(a, cls.WIN_S0), cls.xy(a + wl, cls.WIN_S1)
            s -= rrect(xa, xb, ya, yb2)
        yo = T + BOARD_Y0 + cls.S
        (xa, ya), (xb, _) = cls.xy(cls.SD_L0, cls.SD_S0), cls.xy(cls.SD_L1, 0)
        s -= rrect(xa, xb, ya, yo + 4)                 # microSD notch (open to the outer edge)
        s = _finish(s, series, H, yo)
        if spacer:
            sp = cls.SPACER
            s = add_spacers(s, [cls.xy(l, s_) for l, s_ in cls.HOLES], sp["h"], sp["d"], sp["pilot"])
        return s

    @classmethod
    def ghost(cls, step_path=None):
        """Returns the official 3D model if given, otherwise just the bare board (does not affect the bracket shape)"""
        loc = Pos(-cls.STEP_X0 - cls.L / 2, T + BOARD_Y0 - cls.STEP_Y0, Z0 + T + cls.BOARD_SPACER + cls.BT - cls.STEP_ZTOP)
        if step_path:
            return [c for c in (loc * import_step(step_path)).solids() if c.volume > 0.5]
        z = Z0 + T + cls.BOARD_SPACER
        return [box(-cls.L / 2, cls.L / 2, T + BOARD_Y0, T + BOARD_Y0 + cls.S, z, z + cls.BT)]


BOARDS = [PiB, PiA, PiZero, VIM1S]
SERIES = (20, 40, "DIN")
