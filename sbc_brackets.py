"""L-shaped SBC brackets for aluminium extrusion (20x20 / 40x40, 6 mm slot). They clip onto the frame without screws.

Coordinates (bracket-local, in mm)
  x : vertical. 0 is the height of the frame centre
  y : front-back. 0 is the front face of the frame; the frame is on the y<0 side, the board on the y>0 side
  z : along the rail. This axis points up when printing; the z = Z0 face (outside of the front plate) sits on the build plate

Structure
  - The grip (two hooks + a key that sits in the front slot + the back plate) is shared by every board
  - The front plate is the same size as the board. Holes, cut-outs and the SD card notch are per board
  - spacer=True adds standoffs (bosses) integrated into the front plate (upright orientations only, see SPACER_ORIENTS)
"""
import os, sys
import math
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
DIN_SLIT_IN = 0.5        # gap on the inner side of the leaf spring (towards the key). Only separates it from the back plate
DIN_SLIT_OUT = 2.0       # gap on the outer side. The band of back plate in front of the leaf spring moves outwards with it, and its top end
                         # moves further than the barb tip (din_spring_travel()). The back plate beyond this gap stops the spring a little
                         # after the barb clears the lip, so it cannot be bent much further than pushing on needs
DIN_NOSE_H = 7.0         # length of the hook (barb) along the rail. Only on the tip side of the leaf spring
DIN_KEY_HALF = 12.2      # half width of the key that sits in the centre channel (between the side walls, about 25 mm wide)
DIN_KEY_D = 2.0


def din_leaf_x():
    return DIN_W / 2 + DIN_FIT


def grip_din(h=W):
    """Grip for DIN rail. Identical top and bottom.
    - The centre key sits in the hat's channel (between the side walls) and takes the vertical load
    - Leaf springs on both sides pass outside the lip edges, and the hooks at their tips catch behind the lips. Each leaf spring is a cantilever
      running along the rail (the print height direction) and flexes vertically (x). It is separated from the back plate by DIN_SLIT_IN and DIN_SLIT_OUT and joined only by T on the build plate side"""
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
        for a, b in ((xl - DIN_SLIT_IN, xl), (xl + DIN_LEAF_T, xl + DIN_LEAF_T + DIN_SLIT_OUT)):
            s -= box(*sorted((sg * a, sg * b)), -0.01, T + FIL + 0.1, Z0 + T, W / 2 + 1)
        # also remove the gusset in front of the leaf spring (so the spring is rooted only in T on the build plate side)
        s -= box(*sorted((sg * (xl - DIN_SLIT_IN), sg * (xl + DIN_LEAF_T + DIN_SLIT_OUT))), T, T + FIL + 0.1, Z0 + T, W / 2 + 1)
    return s


def din_spring_travel():
    """How far the top end of a DIN leaf spring moves outwards while the barb tip passes the lip edge (DIN_HOOK - DIN_FIT).
    The spring is a cantilever from the top of the front plate (z = Z0 + T). The lip edge pushes it at the lowest point of the
    barb tip (where the 45-degree underside ends); above that point the spring stays straight, so its top end moves further.
    Beam estimate, ignoring the twist of the spring: 1.77 mm (a linear FEA of the spring and the band gives 1.63 mm at the band)"""
    za = W / 2 - DIN_NOSE_H + DIN_HOOK + 0.01
    a = za - (Z0 + T)
    return (DIN_HOOK - DIN_FIT) * (1 + 1.5 * (W / 2 - za) / a)


def din_spring_hit(s):
    """Overlap (mm3) between the rest of DIN bracket s and its leaf springs moved outwards by din_spring_travel(), both sides.
    Moves each spring with its barb and the band of back plate in front of it as one piece, so the overlap is on the safe side
    (the real spring moves less near its root). Must be 0, or the spring stops before the barb clears the lip"""
    xl = din_leaf_x(); d = din_spring_travel(); hit = 0.0
    for sg in (1, -1):
        cut = box(*sorted((sg * xl, sg * (xl + DIN_LEAF_T))), -DIN_LEAF_BACK - 0.2, T + FIL + 0.2, Z0 + T, W / 2 + 1) \
            + box(*sorted((sg * (xl - DIN_HOOK - 0.2), sg * xl)), -DIN_LEAF_BACK - 0.2, -0.3, Z0 + T, W / 2 + 1)
        hit += (Pos(sg * d, 0, 0) * (s & cut) & (s - cut)).volume
    return hit


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


def _l_body(series, H, depth, Hb=None):
    """Grip + back plate + front plate + gusset. H = half height of the front plate, depth = from the back plate to the end of the front plate,
    Hb = half height of the back plate (H when not given)"""
    s = grip_din() if series == "DIN" else grip(series)
    Hb = H if Hb is None else Hb
    s += box(-Hb, Hb, 0.0, T, -W / 2, W / 2)
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
    xr = xr_of(series)
    zl = Z0 + T + FIL + 1.0; drop = W / 2 - zl
    if H - xr > 1.0:
        for sg in (1, -1):
            if xr + drop <= H + 0.1:
                pts = [(sg * xr, W / 2 + 0.1), (sg * (H + 0.1), W / 2 + 0.1), (sg * (H + 0.1), zl), (sg * (xr + drop), zl)]
            else:                                      # a narrow plate: the slope reaches the plate edge before it gets down to zl
                pts = [(sg * xr, W / 2 + 0.1), (sg * (H + 0.1), W / 2 + 0.1),
                       (sg * (H + 0.1), W / 2 + 0.1 - (H + 0.1 - xr) * (W / 2 + 0.1 - zl) / drop)]
            s -= xz_prism(pts if sg > 0 else list(reversed(pts)), -0.02, T + 0.005)
    return bed_chamfer(s)


def xr_of(series):
    """Half height of back plate that the hooks (or the DIN leaf springs and their slits) need"""
    return (din_leaf_x() + DIN_LEAF_T + DIN_SLIT_OUT + 2.0) if series == "DIN" else (series / 2 + FIT + ARM_T + 2.0)


def bed_chamfer(s):
    """Chamfer the outline on the build plate (against elephant's foot). Only where the wall above rises vertically: on a wall that
    already leans out at 45 degrees (the roof of an opening that starts at the build plate), a chamfer would make it overhang"""
    leaning = [x for f in s.faces() if 0.01 < abs(f.normal_at(f.center()).Z) < 0.99 for x in f.edges()]
    outer = [e for e in s.edges().group_by(Axis.Z)[0] if e.center().Y > 1.0          # skip the thin tips of the hooks
             and not any(e.is_same(x) for x in leaning)]
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


def official(step_path):
    """Place a board's official 3D model on its bracket, for interference checks only. Each board class lists the official
    models it fits in STEPS: file name -> (rotation about z in degrees, centre x and y of the PCB outline, z of the PCB
    underside), all in the file's own coordinates. Returns (board class, parts). Some models are partly surfaces rather than
    solids (e.g. the ROCK 5B+ PCB), so the shells that belong to no solid are returned as parts too"""
    name = os.path.basename(step_path)
    for B in BOARDS:
        if name in getattr(B, "STEPS", {}):
            rot, cx, cy, zb = B.STEPS[name]
            loc = Pos(0, T + BOARD_Y0 + B.S / 2, Z0 + T + B.BOARD_SPACER - zb) * Rot(0, 0, rot) * Pos(-cx, -cy, 0)
            model = loc * import_step(step_path)
            solids = model.solids()
            in_solid = {sh for so in solids for sh in so.shells()}
            return B, [c for c in solids if c.volume > 0.5] + [sh for sh in model.shells() if sh not in in_solid]
    known = ", ".join(n for B in BOARDS for n in getattr(B, "STEPS", {}))
    raise SystemExit(f"{name}: not a known official 3D model (known: {known})")


class Board:
    """What every board class shares. A board class gives its outline (L x S), where its holes, openings and standoffs are on the
    upright-portrait front plate (holes_xy / cuts / spacer_xy, in bracket-local x and y), and a simplified board (ghost)"""
    SD_END = False                                     # True when the microSD slot is at the l = 0 short edge

    @classmethod
    def holes_xy(cls):
        return [cls.xy(l, s_) for l, s_ in cls.HOLES]

    @classmethod
    def spacer_xy(cls):
        return cls.holes_xy()

    @classmethod
    def bracket(cls, series, spacer=False, orient=None):
        if spacer and orient not in (None,) + SPACER_ORIENTS:
            raise ValueError(f"no integrated standoffs in {orient}: on a standing board plate they cannot print without support")
        if orient not in (None, UPRIGHT):
            return oriented(cls, series, spacer, orient)
        H = cls.L / 2
        s = _l_body(series, H, BOARD_Y0 + cls.S)
        for x, y in cls.holes_xy():
            s -= Pos(x, y, Z0 + T / 2) * Cylinder(cls.HOLE_D / 2, T + 2)
        for c in cls.cuts():
            s -= rrect(*c)
        s = _finish(s, series, H, T + BOARD_Y0 + cls.S)
        if spacer:
            sp = cls.SPACER
            s = add_spacers(s, cls.spacer_xy(), sp["h"], sp["d"], sp["pilot"])
        return s


# ======================= Raspberry Pi Model B size (5, 4 B, 3 B+, 3 B, 2 B, 1 B+, Radxa ROCK 3C, Pine64 ROCK64) =======================
class PiB(Board):
    """85 x 56 mm, holes 58 x 49 mm, 3.5 mm from the edges. Same on the official mechanical drawings of the Raspberry Pi 5, 4 B, 3 B+, 3 B and 1 B+;
    the 2 B has "the same form factor" as the 1 B+ (official documentation). The official drawings of the Radxa ROCK 3C (2D DXF) and
    the Pine64 ROCK64 (dimension drawing) have the same outline and holes, with the microSD slot on the underside at a short edge"""
    name, title = "PiB", "Raspberry Pi 5 / 4 B / 3 B+ / 3 B / 2 B / 1 B+, Radxa ROCK 3C, Pine64 ROCK64"
    L, S = 85.0, 56.0                                  # board outline
    HOLE_L, HOLE_S = (3.5, 61.5), (3.5, 52.5)          # mounting holes (long side, short side)
    HOLE_D = 3.0                                       # hole diameter of the version without standoffs
    SD_DEPTH = 19.0
    SD_END = True
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
    def holes_xy(cls):
        return [cls.xy(l, s_) for flip in (False, True) for l, s_ in cls.holes(flip)]   # two sets of holes (ports down / ports up)

    @classmethod
    def spacer_xy(cls):
        return [cls.xy(l, s_) for l, s_ in cls.holes(False)]                         # standoffs only for the ports-down set

    @classmethod
    def cuts(cls):
        H = cls.L / 2; yb = T + BOARD_Y0; yc = yb + 28.0; xn = H - cls.SD_DEPTH
        y0w = yb + 3.5 + 6.0 / 2 + 4.0; y1w = 2 * yc - y0w
        c = [tuple(sorted((sg * xn, sg * (2 * H - xn + 4)))) + (y0w, y1w) for sg in (1, -1)]   # openings at both ends = SD card notch
        return c + [(x0, x1, y0w, y1w) for x0, x1 in ((-(xn - RIB), -RIB / 2), (RIB / 2, xn - RIB))]

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
class PiA(Board):
    """65 x 56 mm, holes 58 x 49 mm, 3.5 mm from the edges (official 3 A+ mechanical drawing, which the documentation says also applies to the 1 A+)"""
    name, title = "PiA", "Raspberry Pi 3 A+ / 1 A+"
    L, S, BT = 65.0, 56.0, 1.6
    HOLES = [(3.5, 3.5), (3.5, 52.5), (61.5, 3.5), (61.5, 52.5)]   # symmetric along the long side, so one set fits either orientation
    HOLE_D = 3.0
    SD_DEPTH = 15.0
    SD_END = True
    SPACER = dict(h=5.0, d=6.0, pilot=2.2, screw="M2.5")
    BOARD_SPACER = 5.0

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + (cls.S - s))      # GPIO side (large s) towards the back plate, ports facing out

    @classmethod
    def cuts(cls):
        H = cls.L / 2; yb = T + BOARD_Y0
        y0w = yb + 3.5 + 6.0 / 2 + 4.0; y1w = yb + cls.S - (3.5 + 6.0 / 2 + 4.0)   # clear of the standoffs, as on PiB
        xn = H - cls.SD_DEPTH
        c = [tuple(sorted((sg * xn, sg * (H + 4)))) + (y0w, y1w) for sg in (1, -1)]   # SD card notch at both ends (fits either way round)
        return c + [(x0, x1, y0w, y1w) for x0, x1 in ((-(xn - RIB), -RIB / 2), (RIB / 2, xn - RIB))]

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


# ======================= Raspberry Pi Zero size (Zero, Zero W, Zero 2 W, Radxa ZERO 3W / 3E) =======================
class PiZero(Board):
    """65 x 30 mm, holes 58 x 23 mm, 3.5 mm from the edges (official Zero W and Zero 2 W mechanical drawings; the Zero has the same holes).
    The official drawings and 3D models of the Radxa ZERO 3W and 3E have the same outline and holes"""
    name, title = "PiZero", "Raspberry Pi Zero / Zero W / Zero 2 W, Radxa ZERO 3W / 3E"
    L, S, BT = 65.0, 30.0, 1.6
    STEPS = {"radxa_zero_3w_3d.stp": (180, 32.495, 15.003, -1.6),        # Radxa ZERO 3W
             "rs109_pcba.stp": (180, 32.495, 15.003, -1.62)}             # Radxa ZERO 3E (the pads under the holes are 0.02 mm proud)
    HOLES = [(3.5, 3.5), (3.5, 26.5), (61.5, 3.5), (61.5, 26.5)]   # 58 x 23. Symmetric both ways, so one set fits either orientation
    HOLE_D = 3.0
    SD_DEPTH = 15.0
    SD_END = True
    WIN_M = 2.5
    SPACER = dict(h=3.0, d=6.0, pilot=2.2, screw="M2.5")
    BOARD_SPACER = 3.0

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + (cls.S - s))      # GPIO side (large s) towards the back plate, ports facing out

    @classmethod
    def cuts(cls):
        H = cls.L / 2; yb = T + BOARD_Y0
        y0w = yb + 3.5 + cls.HOLE_D / 2 + cls.WIN_M; y1w = yb + cls.S - 3.5 - cls.HOLE_D / 2 - cls.WIN_M
        xn = H - cls.SD_DEPTH
        c = [tuple(sorted((sg * xn, sg * (H + 4)))) + (y0w, y1w) for sg in (1, -1)]
        return c + [(x0, x1, y0w, y1w) for x0, x1 in ((-(xn - RIB), -RIB / 2), (RIB / 2, xn - RIB))]

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


# ======================= Khadas VIM1S / VIM3 / VIM4 =======================
class VIM1S(Board):
    """Dimensions taken from Khadas' official 3D model vim1s-pcba-3d-v11.stp. The official 3D models and 2D drawings of the
    VIM3 and VIM4 have the same outline and holes"""
    name, title = "VIM1S", "Khadas VIM1S / VIM3 / VIM4"
    L, S, BT = 82.0, 56.638, 1.21
    HOLES = [(2.5, 3.134), (79.5, 3.134), (16.5, 48.634), (65.5, 48.634)]   # trapezoid pattern (77 / 49 / 45.5). s=0 is the GPIO side
    HOLE_D = 3.0
    SD_L0, SD_L1, SD_S0 = 32.0, 55.0, 46.0             # microSD notch (middle of the port-side edge, underside of the board)
    WIN_S0, WIN_S1 = 7.5, 41.0
    SPACER = dict(h=5.0, d=5.0, pilot=1.7, screw="M2")  # 5 mm because the LAN jack on the underside sticks out 3.5 mm below the board
    BOARD_SPACER = 5.0
    STEPS = {"vim1s-pcba-3d-v11.stp": (0, 35.16, -34.633, -1.205),
             "vim3-pcba-3d-v14.stp": (180, -155.846, 46.546, 50.143),
             "vim4-pcba-3d-v13.stp": (180, 41.0, 28.315, -1.2)}

    @classmethod
    def xy(cls, l, s):
        return (l - cls.L / 2, T + BOARD_Y0 + s)

    @classmethod
    def cuts(cls):
        l0, l1 = 6.0, cls.L - 6.0; wl = (l1 - l0 - 2 * RIB) / 3
        c = []
        for i in range(3):                             # three lightening windows
            a = l0 + i * (wl + RIB)
            (xa, ya), (xb, yb2) = cls.xy(a, cls.WIN_S0), cls.xy(a + wl, cls.WIN_S1)
            c.append((xa, xb, ya, yb2))
        yo = T + BOARD_Y0 + cls.S
        (xa, ya), (xb, _) = cls.xy(cls.SD_L0, cls.SD_S0), cls.xy(cls.SD_L1, 0)
        return c + [(xa, xb, ya, yo + 4)]              # microSD notch (open to the outer edge)

    @classmethod
    def ghost(cls):
        """Just the bare board (does not affect the bracket shape). Use the official 3D models (STEPS) for interference checks"""
        z = Z0 + T + cls.BOARD_SPACER
        return box(-cls.L / 2, cls.L / 2, T + BOARD_Y0, T + BOARD_Y0 + cls.S, z, z + cls.BT)


# ======================= Radxa ROCK 5B / 5B+ =======================
class ROCK5B(Board):
    """100.2 x 74.25 mm, four 3.5 mm holes 93.15 x 49 mm apart, 3.55 mm from the GPIO-side edge (official 2D drawings and 3D models
    of the ROCK 5B v1.42 and ROCK 5B+ v1.2). The microSD card sticks out past the GPIO-side edge, under the board, beside the frame"""
    name, title = "ROCK5B", "Radxa ROCK 5B / 5B+"
    L, S, BT = 100.2, 74.25, 1.6
    HOLES = [(3.55, 3.55), (96.70, 3.55), (3.55, 52.55), (96.70, 52.55)]   # s=0 is the GPIO side
    HOLE_D = 3.0                                       # the board holes are 3.5 mm
    WIN_S = ((10.55, 45.55), (59.55, 70.25))           # two rows of lightening windows, clear of the standoffs
    SPACER = dict(h=8.0, d=5.4, pilot=2.2, screw="M2.5")  # 8 mm: parts under the 5B+ reach 5.4 mm below the board, and the 5B's microSD card sits under it. 5.4 mm: a part under the 5B+ is 3.1 mm from a hole centre
    BOARD_SPACER = 8.0
    STEPS = {"ROCK5B_v1.42_3D.step": (180, -6.896, 94.691, -1.5),
             "rock5bp_pcba_3d_V1_2_20250314.stp": (0, 47.097, 37.121, -1.6)}

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + s)

    @classmethod
    def cuts(cls):
        l0, l1 = 6.0, cls.L - 6.0; wl = (l1 - l0 - 2 * RIB) / 3
        c = []
        for s0, s1 in cls.WIN_S:
            for i in range(3):
                a = l0 + i * (wl + RIB)
                (xa, ya), (xb, yb2) = cls.xy(a, s0), cls.xy(a + wl, s1)
                c.append((min(xa, xb), max(xa, xb), ya, yb2))
        return c

    @classmethod
    def ghost(cls):
        """Just the bare board (does not affect the bracket shape). Use the official 3D models (STEPS) for interference checks"""
        z = Z0 + T + cls.BOARD_SPACER
        return box(-cls.L / 2, cls.L / 2, T + BOARD_Y0, T + BOARD_Y0 + cls.S, z, z + cls.BT)


# ======================= BeagleBoard.org BeagleBone Black =======================
class BBB(Board):
    """86.36 x 54.61 mm (3.400 x 2.150 in), four 3.175 mm (1/8 in) holes in a trapezoid, from the board outline and drill file of
    the official Rev C manufacturing data and the board dimension drawing in the System Reference Manual. The microSD slot,
    micro HDMI and USB-A are at one short end (microSD and micro HDMI under the board), Ethernet, the power jack and mini USB
    (under the board) at the other. No official 3D model is published"""
    name, title = "BBB", "BeagleBoard.org BeagleBone Black"
    L, S, BT = 86.36, 54.61, 1.575
    # l = 0 is the microSD end (x = 3.400 in in the manufacturing data), s is y there (0 at the P9 header edge).
    # From the drill file: (3.175, 0.250), (3.175, 1.900), (0.575, 0.125), (0.575, 2.025) in
    HOLES = [(5.715, 6.35), (5.715, 48.26), (71.755, 3.175), (71.755, 51.435)]
    HOLE_D = 3.0                                       # the board holes are 3.175 mm
    SD_END = True
    SD_NOTCH = (23.0, 20.0, 44.5)                      # microSD end notch: depth, s range (microSD holder and micro HDMI under the board)
    USB_NOTCH = (75.0, 38.0, 50.0)                     # power end notch: from l, s range (mini USB under the board)
    WIN_L, WIN_S = (29.0, 69.0), (10.0, 44.61)         # two lightening windows, clear of the standoffs and the notches
    SPACER = dict(h=6.0, d=6.0, pilot=2.6, screw="M3")  # 6 mm tall: the System Reference Manual gives a "max height" of 4.76 mm without
                                                       # saying of what. 6 mm across: the nearest parts under the board are 5.2 mm from a hole centre
    BOARD_SPACER = 6.0

    @classmethod
    def xy(cls, l, s):
        return (cls.L / 2 - l, T + BOARD_Y0 + s)

    @classmethod
    def cuts(cls):
        def r(l0, l1, s0, s1):
            (xa, ya), (xb, yb_) = cls.xy(l0, s0), cls.xy(l1, s1)
            return min(xa, xb), max(xa, xb), ya, yb_
        d, s0, s1 = cls.SD_NOTCH; u, t0, t1 = cls.USB_NOTCH; (a, b), (w0, w1) = cls.WIN_L, cls.WIN_S
        wl = (b - a - RIB) / 2
        return [r(-4.0, d, s0, s1), r(u, cls.L + 4.0, t0, t1)] + [r(c, c + wl, w0, w1) for c in (a, a + wl + RIB)]

    @classmethod
    def ghost(cls):
        """Board for display and interference checks (simplified). x, y are the manufacturing data's coordinates (mm, top view):
        outlines from the silkscreen, header pins from the drill file, heights from the official bill of materials. The heights of
        the micro HDMI and mini USB under the board are not published, so they are shown reaching the plate (it is notched there)"""
        def blk(x0, x1, y0, y1, h0, h1):
            (xa, ya), (xb, yb_) = cls.xy(cls.L - x0, y0), cls.xy(cls.L - x1, y1)
            za, zb = Z0 + T + cls.BOARD_SPACER + h0, Z0 + T + cls.BOARD_SPACER + h1
            return box(min(xa, xb), max(xa, xb), ya, yb_, za, zb)
        t = cls.BT; down = 0.02 - cls.BOARD_SPACER
        g = blk(0, cls.L, 0, cls.S, 0, t)
        g += blk(-2.62, 19.23, 21.89, 37.80, t, t + 13.3)     # Ethernet (RJ45, 13.3 mm tall)
        g += blk(-2.54, 12.07, 4.95, 14.10, t, t + 11.0)      # power jack (11 mm)
        g += blk(72.34, 86.33, 10.26, 23.37, t, t + 7.0)      # USB-A (7 mm)
        for y0 in (0.635, 48.895):                             # P9 / P8 expansion headers (8.5 mm), and their pins through the board
            g += blk(18.415, 76.835, y0, y0 + 5.08, t, t + 8.5)
            g += blk(19.2, 76.1, y0 + 0.77, y0 + 4.31, t - 3.0, 0)
        g += blk(66.17, 86.36, 24.26, 44.41, -1.8, 0)         # microSD holder, under the board (1.8 mm)
        g += blk(80.45, 87.05, 21.90, 30.11, down, 0)         # micro HDMI, under the board
        g += blk(-0.50, 6.50, 40.28, 47.98, down, 0)          # mini USB, under the board
        return g


BOARDS = [PiB, PiA, PiZero, VIM1S, ROCK5B, BBB]
SERIES = (20, 40, "DIN")


# ======================= Mounting orientations =======================
# The grip only prints one way up, so every orientation keeps it on the build plate (z = Z0) and changes how the board plate sits
# relative to it. A board's holes, openings and standoffs are defined once, on the upright-portrait front plate (the "board frame":
# holes_xy / cuts / spacer_xy / ghost / STEPS), and place() moves them, the simplified board and the official 3D models to the
# orientation. In the flat and shelf orientations the board plate stands upright while printing, so openings get 45-degree roofs,
# holes become teardrops, and each opening keeps the rest of its rectangle as a shallow pocket in the face under the board.
# Those orientations have no integrated standoffs: a standoff growing sideways out of a standing plate only prints without support
# if its underside rises at 45 degrees from the plate. Either that slope eats the seat (most of it on PiB and VIM1S, and the ROCK5B
# standoffs never reach the board), or it is filled in below and hits the parts under the ZERO 3E and VIM1S boards.
ORIENTS = {"upright-portrait": "Upright, portrait", "upright-landscape": "Upright, landscape",
           "flat-portrait": "Flat, portrait", "flat-landscape": "Flat, landscape",
           "shelf-portrait": "Shelf, portrait", "shelf-landscape": "Shelf, landscape"}
UPRIGHT = "upright-portrait"
SPACER_ORIENTS = ("upright-portrait", "upright-landscape")   # orientations with an integrated-standoff version
SD_GAP = 17.0            # gap to the back plate when the microSD end of the board faces the frame, so a finger reaches the card
POCKET = 1.0             # depth of the pocket that keeps an opening's whole rectangle clear on a standing plate (parts under the
                         # ZERO 3E reach 0.64 mm into the plate where the 45-degree roof of its microSD-end notch leaves material)


def shelf_top(series):
    """Height of the shelf's top face. On DIN rail the shelf, its gusset and the root rib keep clear of the leaf springs' slits"""
    if series == "DIN":
        return din_leaf_x() + DIN_LEAF_T + DIN_SLIT_OUT + 0.5 + T + FIL
    return xr_of(series)


def gap(B, orient):
    """From the front face of the back plate to the near edge of the board"""
    return SD_GAP if B.SD_END and orient in ("upright-landscape", "shelf-portrait") else BOARD_Y0


def flat_edge(B, orient, series):
    """Where a flat-mounted board starts along the rail: beside the grip (z = W/2), or further on when one of its holes would
    otherwise reach the gap that a DIN leaf spring needs above its free end"""
    if series != "DIN":
        return W / 2
    M = place(B, orient, series, edge=W / 2)
    xl = din_leaf_x(); k0, k1 = xl - DIN_SLIT_IN - 0.5, xl + DIN_LEAF_T + DIN_SLIT_OUT + 0.5
    zc = W / 2 + 1 + (DIN_SLIT_IN + DIN_LEAF_T + DIN_SLIT_OUT) / 2 + 1.0       # top of the gap over the leaf spring + 1 mm
    hit = lambda x, w: abs(x) + w > k0 and abs(x) - w < k1
    need = 0.0
    for x, y in B.holes_xy():
        p = (M * Pos(x, y, Z0)).position
        if hit(p.X, B.HOLE_D / 2):
            need = max(need, zc - (p.Z - B.HOLE_D / 2))
    return W / 2 + need


def place(B, orient, series, edge=None):
    """Location that moves the board frame (upright portrait) to the orientation"""
    L, S = B.L, B.S; yb = T + BOARD_Y0; g = gap(B, orient); hs = shelf_top(series)
    if edge is None and orient.startswith("flat"):
        edge = flat_edge(B, orient, series)
    tf = {"upright-portrait": ((0, 0, 0), (1, 0, 0), (0, 0, 1)),
          "upright-landscape": ((-(yb + S / 2), T + g + L / 2, 0), (0, -1, 0), (0, 0, 1)),     # microSD end towards the frame, ports forward
          "flat-portrait": ((0, -Z0, (edge or 0) + yb + S), (1, 0, 0), (0, 1, 0)),             # the board starts beside the grip
          "flat-landscape": ((yb + S / 2, -Z0, (edge or 0) + L / 2), (0, 0, -1), (0, 1, 0)),
          "shelf-portrait": ((hs - T - Z0, T + g + L / 2, Z0 + yb + S), (0, -1, 0), (1, 0, 0)),
          "shelf-landscape": ((hs - T - Z0, T + g - yb, Z0 + L / 2), (0, 0, -1), (1, 0, 0))}[orient]
    return Plane(origin=tf[0], x_dir=tf[1], z_dir=tf[2]).location


def _vcut(kind, sk, n0, n1):
    """Extrude a sketch drawn in (across, up) through a standing plate, from n0 to n1 along its normal.
    kind "flat": plate in the x-z plane (across = x, normal = y); "shelf": plate in the y-z plane (across = y, normal = x)"""
    o, xd, zd = ((0, (n0 + n1) / 2, 0), (1, 0, 0), (0, -1, 0)) if kind == "flat" else (((n0 + n1) / 2, 0, 0), (0, 1, 0), (1, 0, 0))
    return Plane(origin=o, x_dir=xd, z_dir=zd).location * extrude(sk, abs(n1 - n0) / 2, both=True)


def _tear(a, b, r):
    """Teardrop (point up) so a sideways hole prints without support"""
    q = r / math.sqrt(2)
    return Pos(a, b) * (Circle(r) + Polygon((-q, q), (0, r * math.sqrt(2)), (q, q), (0, 0), align=None))


def _vopen(a0, a1, b0, b1, lo, hi, top):
    """Outlines (across, up) of an opening in a standing plate whose top is never a flat roof: a notch open at the top stays a
    rectangle, a notch open at the side gets a roof rising towards the open edge, a closed opening gets a 45-degree roof inside
    the rectangle (split by ribs when it is too wide for one). lo / hi / top = edges of the plate"""
    h = b1 - b0
    if b1 >= top:
        return [[(a0, b0), (a1, b0), (a1, b1), (a0, b1)]]
    if a1 > hi:
        e = hi
        return [[(a0, b0), (a1, b0), (a1, b1), (e, b1), (a0, b1 - (e - a0))] if e - a0 < h else
                [(e - h, b0), (a1, b0), (a1, b1), (e, b1)]]
    if a0 < lo:
        e = lo
        return [[(a1, b0), (a1, b1 - (a1 - e)), (e, b1), (a0, b1), (a0, b0)] if a1 - e < h else
                [(e + h, b0), (e, b1), (a0, b1), (a0, b0)]]
    w = a1 - a0; n = max(1, math.ceil((w + RIB) / (2 * h + RIB)))
    wi = (w - (n - 1) * RIB) / n
    out = []
    for i in range(n):
        c0 = a0 + i * (wi + RIB); c1 = c0 + wi
        out.append([(c0, b0), (c1, b0), (c1, b1 - wi / 2), ((c0 + c1) / 2, b1), (c0, b1 - wi / 2)])
    return out


def _round_top(s, kind, lo, hi, top, n0, n1):
    """Round the two top corners of a standing plate (the bottom ones stay square: a rounded bottom corner would overhang)"""
    R = CORNER_R
    for e, sg in ((hi, 1), (lo, -1)):
        sk = Pos(e - sg * (R - 1) / 2, top - (R - 1) / 2) * Rectangle(R + 1, R + 1) - Pos(e - sg * R, top - R) * Circle(R)
        s -= _vcut(kind, sk, n0 - 0.01, n1 + 0.01)
    return s


def din_caps(s):
    """For a back plate that carries on above the grip: a gap with a 45-degree roof over each leaf spring, so the plate above does
    not tie the spring's free end"""
    xl = din_leaf_x(); x0, x1 = xl - DIN_SLIT_IN, xl + DIN_LEAF_T + DIN_SLIT_OUT; z1 = W / 2 + 1
    for sg in (1, -1):
        pts = [(x0, W / 2), (x1, W / 2), (x1, z1), ((x0 + x1) / 2, z1 + (x1 - x0) / 2), (x0, z1)]
        s -= xz_prism(pts if sg > 0 else [(-x, z) for x, z in reversed(pts)], -0.02, T + 0.02)
    return s


def oriented(B, series, spacer, orient):
    """Bracket for an orientation other than upright portrait"""
    M = place(B, orient, series)
    kind = orient.split("-")[0]; portrait = orient.endswith("portrait")
    L, S = B.L, B.S; g = gap(B, orient); xr = xr_of(series); sp = B.SPACER
    to = lambda xy: [tuple((M * Pos(x, y, Z0)).position) for x, y in xy]

    def rect(c):                                       # an opening of the board frame -> (x0, x1, y0, y1, z0, z1)
        (ax, ay, az), (bx, by, bz) = to([(c[0], c[2]), (c[1], c[3])])
        return min(ax, bx), max(ax, bx), min(ay, by), max(ay, by), min(az, bz), max(az, bz)

    if kind == "upright":                              # landscape: long side forward, the plate still lies on the build plate
        Hp = S / 2
        s = _l_body(series, Hp, g + L, Hb=max(Hp, xr))
        for x, y, _ in to(B.holes_xy()):
            s -= Pos(x, y, Z0 + T / 2) * Cylinder(B.HOLE_D / 2, T + 2)
        for x0, x1, y0, y1, _, _ in map(rect, B.cuts()):
            y0 = max(y0, T + FIL + 1.0)                # an opening that reaches past the board stops short of the gusset
            if y1 - y0 > 2 * WIN_R + 0.1 and x1 - x0 > 2 * WIN_R + 0.1:
                s -= rrect(x0, x1, y0, y1)
        s = _finish(s, series, Hp, T + g + L)
        if spacer:
            s = add_spacers(s, [(x, y) for x, y, _ in to(B.spacer_xy())], sp["h"], sp["d"], sp["pilot"])
        return s

    s = grip_din() if series == "DIN" else grip(series)
    if kind == "flat":                                 # the back plate is the board plate; the board sits beside the grip
        Pa = (L if portrait else S) / 2; ze = flat_edge(B, orient, series); top = ze + (S if portrait else L)
        s += box(-max(Pa, xr), max(Pa, xr), 0, T, Z0, W / 2)
        s += box(-Pa, Pa, 0, T, W / 2 - 0.01, top)
        if series == "DIN":
            s = din_caps(din_slits(s, Pa))
        n0, n1, lo, hi, b_min = 0.0, T, -Pa, Pa, max(ze + 1.0, W / 2 + 4.0)   # openings keep a rib above the grip
        ac = lambda p: p[0]
    else:                                              # shelf on top of the back plate, the board lying on it
        hs = shelf_top(series); yo = T + g + (L if portrait else S); top = Z0 + (S if portrait else L)
        s += box(-xr, hs, 0, T, Z0, W / 2)
        s += box(hs - T, hs, 0, yo, Z0, top)
        s += box(hs - RIB, hs, 0, T, Z0, top)          # rib along the shelf's root
        x1 = hs - T + 0.01; y1 = T - 0.01
        s += Pos(0, 0, (Z0 + top) / 2) * prism([(x1, y1), (x1, y1 + FIL), (x1 - FIL, y1)], top - Z0)   # gusset under the shelf
        if series == "DIN":
            s = din_slits(s, xr)
        n0, n1, lo, hi, b_min = hs - T, hs, -1e9, yo, -1e9
        ac = lambda p: p[1]
        Pa = None
    for p in to(B.holes_xy()):
        s -= _vcut(kind, _tear(ac(p), p[2], B.HOLE_D / 2), n0 - 1, n1 + 1)
    for c in map(rect, B.cuts()):
        a0, a1 = (c[0], c[1]) if kind == "flat" else (c[2], c[3])
        if kind == "shelf":
            a0 = max(a0, T + FIL + 1.0)                # stop short of the gusset and the rib at the root
        b0, b1 = max(c[4], b_min), c[5]
        if b1 - b0 < 1.0 or a1 - a0 < 1.0:
            continue
        for poly in _vopen(a0, a1, b0, b1, lo, hi, top):
            s -= _vcut(kind, Polygon(*poly, align=None), n0 - 1, n1 + 1)
        # the rest of the rectangle as a pocket in the face under the board, its ceiling cut at 45 degrees
        s -= _vcut(kind, Polygon((a0, b0), (a1, b0), (a1, b1 - POCKET), (a0, b1 - POCKET), align=None), n1 - POCKET, n1 + 0.01)
        s -= _vcut("shelf" if kind == "flat" else "flat",
                   Polygon((n1 - POCKET, b1 - POCKET - 0.01), (n1 + 0.01, b1 - POCKET - 0.01), (n1 + 0.01, b1 + 0.01), align=None), a0, a1)
    s = _round_top(s, kind, lo, hi, top, n0, n1) if kind == "flat" else _round_top_far(s, hi, top, n0, n1)
    return bed_chamfer(s)


def _round_top_far(s, hi, top, n0, n1):
    """Shelf: round only the top corner at the far end (the root end is held by the rib)"""
    R = CORNER_R
    sk = Pos(hi - (R - 1) / 2, top - (R - 1) / 2) * Rectangle(R + 1, R + 1) - Pos(hi - R, top - R) * Circle(R)
    return s - _vcut("shelf", sk, n0 - 0.01, n1 + 0.01)
