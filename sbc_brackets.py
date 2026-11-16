"""L-shaped SBC brackets for aluminium extrusion (20x20 / 40x40, 6 mm slot). They clip onto the frame without screws.

Coordinates (bracket-local, in mm)
  x : vertical. 0 is the height of the frame centre
  y : front-back. 0 is the front face of the frame; the frame is on the y<0 side, the board on the y>0 side
  z : along the rail. This axis points up when printing; the z = Z0 face (outside of the front plate) sits on the build plate

Structure
  - The grip (two hooks + a key that sits in the front slot + the back plate) is shared by every board
  - The front plate is the same size as the board. Holes, cut-outs and the SD card notch are per board, from its definition
    in boards/ (boards/README.md)
  - spacer=True adds standoffs (bosses) integrated into the front plate (upright orientations only, see SPACER_ORIENTS)
"""
import glob, json, math, os, sys
from build123d import (Polygon, Circle, Rectangle, Box, Cylinder, Pos, Rot, Plane, RectangleRounded,
                       extrude, fillet, chamfer, Axis, import_step, Solid, Compound)
from OCP.StlAPI import StlAPI_Reader
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid

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
DIN_ALU_WALL, DIN_ALU_D = 1.5, 7.3                     # aluminium rails (Takachi FDR): 1.5 mm side walls (24 mm channel), 7.3 deep;
                                                       # the lips are 1 mm at the edge, as on steel rails


def din_rail(L=120.0, wall=DIN_T, depth=DIN_D):
    """Simplified DIN rail (for interference checks and display). The front (front face of the lips) is y=0, the back (panel side) is
    y=-depth. wall = thickness of the side walls and the base (the steel rail's sheet, or DIN_ALU_WALL)"""
    hb = DIN_BASE / 2; hw = DIN_W / 2
    r = box(-hw, -(hb - wall), -DIN_T, 0, -L / 2, L / 2) + box(hb - wall, hw, -DIN_T, 0, -L / 2, L / 2)   # lips
    r += box(-hb, -(hb - wall), -depth, 0, -L / 2, L / 2) + box(hb - wall, hb, -depth, 0, -L / 2, L / 2)  # side walls
    r += box(-hb, hb, -depth, -depth + wall, -L / 2, L / 2)                                              # base
    return r


def mount_frame(series, L=120.0):
    """Shape of what the bracket mounts on (series = 20 / 40 / "DIN")"""
    return din_rail(L) if series == "DIN" else frame(series, L)


def mount_frames(series, L=120.0):
    """Everything the bracket must fit, for --check: the frame, or for DIN rail both steel and aluminium rails"""
    if series != "DIN":
        return [("frame", frame(series, L))]
    return [("steel rail", din_rail(L)), ("aluminium rail", din_rail(L, DIN_ALU_WALL, DIN_ALU_D))]


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
DIN_LEAF_T = 0.8         # leaf spring thickness. With DIN_NOSE_H this sets the bending strain at the spring's root when the barb
                         # clears the lip: 0.77% (beam), under the 0.96% allowed for a one-off push in PETG across the layers
DIN_LEAF_BACK = 2.6      # how deep the leaf spring reaches behind the lip
DIN_SLIT_IN = 0.5        # gap on the inner side of the leaf spring (towards the key). Only separates it from the back plate
DIN_SLIT_OUT = 1.5       # gap on the outer side. The band of back plate in front of the leaf spring moves outwards with it, and its top end
                         # moves further than the barb tip (din_spring_travel()). The back plate beyond this gap stops the spring a little
                         # after the barb clears the lip, so it cannot be bent much further than pushing on needs (at the stop the root
                         # strain is about 1.2%, still under the yield strain of about 1.4%)
DIN_NOSE_H = 3.0         # length of the hook (barb) along the rail. Only on the tip side of the leaf spring, so the lip edge pushes the
                         # spring as far from its root as it can
DIN_KEY_HALF = 11.8      # half width of the key that sits in the centre channel (between the side walls): 25 mm wide on steel rails
                         # with 1 mm sheet, 24 mm on aluminium rails with 1.5 mm side walls; the key fits both
DIN_KEY_D = 2.0


def din_leaf_x():
    return DIN_W / 2 + DIN_FIT


def grip_din(h=W):
    """Grip for DIN rail. Identical top and bottom.
    - The roots of the leaf springs (solid back plate, DIN_FIT from the lip edges) touch the lip edges first and take the vertical load.
      The centre key sits in the hat's channel (between the side walls) as a back-up
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
    Beam estimate, ignoring the twist of the spring: 0.98 mm (a linear FEA of the spring and the band gives 0.95 mm at the band)"""
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


def add_spacers(s, pts, h, d_boss, d_pilot, foot=None):
    """Add standoffs (bosses) to the front plate. Fill the plate holes, add the bosses, then drill the pilot holes again.
    foot = (height, diameter) of a wider base under a boss that has to be slim further up"""
    for x, y in pts:
        s += Pos(x, y, Z0 + (T + h) / 2) * Cylinder(d_boss / 2, T + h - 0.01)
        if foot:
            s += Pos(x, y, Z0 + (T + foot[0]) / 2) * Cylinder(foot[1] / 2, T + foot[0] - 0.01)
    for x, y in pts:
        s -= Pos(x, y, Z0 + (T + h) / 2) * Cylinder(d_pilot / 2, T + h + 2)
    return s


def official(step_path):
    """Place a board's official 3D model on its bracket, for interference checks only. A definition lists the official models
    it fits in official_models (boards/README.md). A model published only as STL is read as a closed mesh. Returns (board,
    parts). Some models are partly surfaces rather than solids (e.g. the ROCK 5B+ PCB), so the shells that belong to no solid
    are returned as parts too"""
    name = os.path.basename(step_path)
    for B in BOARDS:
        if name in B.official_models:
            m = B.official_models[name]
            rot = (m["rotate"] + (0 if B.frame_edge == "s=0" else 180)) % 360   # (l, s) -> (x, y) turns half a turn for s=S
            cx, cy = m["centre"]
            loc = (Pos(0, T + BOARD_Y0 + B.S / 2, Z0 + T + B.standoffs["h"] - m["underside"]) * Rot(0, 0, rot) * Pos(-cx, -cy, 0)
                   * Rot(m.get("tilt", 0), 0, 0))
            if name.lower().endswith(".stl"):
                mesh = TopoDS_Shape(); StlAPI_Reader().Read(mesh, step_path)
                sew = BRepBuilderAPI_Sewing(1e-3); sew.Add(mesh); sew.Perform()
                mk = BRepBuilderAPI_MakeSolid(); mk.Add(TopoDS.Shell(sew.SewedShape()))
                part = Solid(mk.Solid())
                part = part if part.volume > 0 else Solid(part.wrapped.Reversed())
            else:
                part = import_step(step_path)
            if "exclude" in m:   # top-level parts that are not on the board on a bracket, such as the case base it comes on
                missing = set(m["exclude"]) - {c.label for c in part.children}
                if missing:
                    raise SystemExit(f"{name}: no top-level part named {', '.join(sorted(missing))} to exclude")
                part = Compound(children=[c for c in part.children if c.label not in m["exclude"]])
            model = loc * part
            solids = model.solids()
            in_solid = {sh for so in solids for sh in so.shells()}
            return B, [c for c in solids if c.volume > 0.5] + [sh for sh in model.shells() if sh not in in_solid]
    known = ", ".join(n for B in BOARDS for n in B.official_models)
    raise SystemExit(f"{name}: not a known official 3D model (known: {known})")


# ======================= Cradle (for a board with no mounting holes) =======================
CRADLE_FIT = 0.15        # clearance around the held board (per side)
CRADLE_STOP_T = 1.6      # thickness of the end stops beyond the board's short ends
CRADLE_PLATE = 2.0       # thickness of the end plates the screws go through
CRADLE_LEDGE = 5.0       # length of each ledge under a corner of the board, along l
CRADLE_WALL_MIN = 1.0    # thinnest side wall that still prints and holds


def cradle(c, L, S, holes, hole_d):
    """A cradle for a board with no mounting holes (the definition's cradle field, boards/README.md). It is the L x S outline
    that sits on the standoffs, in the outline's coordinates (l, s, h), with h = 0 its underside: it prints that side down,
    without supports. The board rests on ledges under its four corners between two side walls, with end stops beyond its short
    ends. A short lip at the middle of each wall, 45 degrees above and below, snaps over the parts along the board's long edge:
    the walls bend outwards between the end stops to let the board in. End plates beyond the end stops carry the screw holes"""
    l0, l1, s0, s1, h0, h1 = c["board"]
    a0, a1 = l0 - CRADLE_FIT - CRADLE_STOP_T, l1 + CRADLE_FIT + CRADLE_STOP_T     # outer faces of the end stops
    lip = c["lip"]; reach = CRADLE_FIT + lip["over"]                             # how far the lip stands out of the wall
    z_lip = lip["top"] + 0.05 - CRADLE_FIT                                       # its 45-degree underside clears the parts' top
    top = z_lip + 2 * reach                                                      # 0.05 mm at the board's edge
    s = box(0, a0, 0, S, 0, CRADLE_PLATE) + box(a1, L, 0, S, 0, CRADLE_PLATE)
    for w0, w1, e, sg in ((0, s0 - CRADLE_FIT, s0, 1), (s1 + CRADLE_FIT, S, s1, -1)):   # the two long sides; sg points inwards
        s += box(a0, a1, w0, w1, 0, top)
        st = sorted((e - sg * CRADLE_FIT, e + sg * c["stop"]))
        s += box(a0, l0 - CRADLE_FIT, *st, 0, h1 - 0.1) + box(l1 + CRADLE_FIT, a1, *st, 0, h1 - 0.1)
        ld = sorted((e - sg * CRADLE_FIT, e + sg * c["ledge"]))
        s += (box(l0 - CRADLE_FIT, l0 - CRADLE_FIT + CRADLE_LEDGE, *ld, 0, h0)
              + box(l1 + CRADLE_FIT - CRADLE_LEDGE, l1 + CRADLE_FIT, *ld, 0, h0))
        wall = e - sg * CRADLE_FIT
        profile = Polygon((wall - sg * 0.01, z_lip), (wall + sg * reach, z_lip + reach), (wall - sg * 0.01, top), align=None)
        s += extrude(Plane.YZ.offset(lip["l"][0]) * profile, lip["l"][1] - lip["l"][0])   # (s, h) profile, along l
    for l, w in holes:
        s -= Pos(l, w, CRADLE_PLATE / 2) * Cylinder(hole_d / 2, CRADLE_PLATE + 2)
    return s


# ======================= Boards (boards/*.json) =======================
BOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boards")
FIELDS = {"title": True, "notes": False, "size": True, "frame_edge": True, "microsd_edge": False, "holes": True, "hole_d": True,
          "standoffs": True, "openings": False, "windows": False, "parts": True, "official_models": False,
          "cradle": False}   # name: required
STANDOFF_FIELDS = {"h", "d", "pilot", "screw", "foot", "through", "at"}
MODEL_FIELDS = {"rotate", "centre", "underside", "tilt", "exclude"}
CRADLE_FIELDS = {"board", "ledge", "stop", "lip"}
LIP_FIELDS = {"l", "top", "over"}


class Board:
    """A board, read from its definition boards/<name>.json (the fields are described in boards/README.md). The definition is in
    the board's own top-view coordinates, mm: l from 0 to L along one side (usually the long side), s from 0 to S along the
    other. xy() maps them onto the upright-portrait front plate (the "board frame", in bracket-local x and y), with the
    frame_edge edge towards the back plate"""

    def __init__(self, path):
        self.name = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        self._check(d)
        self.title, self.notes = d["title"], d.get("notes", [])
        self.L, self.S = (float(v) for v in d["size"])
        self.frame_edge, self.hole_d, self.holes = d["frame_edge"], d["hole_d"], d["holes"]
        self.standoffs = {k: v for k, v in d["standoffs"].items() if k != "at"}   # h, d, pilot, screw[, foot, through]
        self.standoff_at = d["standoffs"].get("at", self.holes)
        self.openings, self.windows, self.parts = d.get("openings", []), d.get("windows"), d["parts"]
        self.official_models = d.get("official_models", {})
        self.cradle_def = d.get("cradle")
        self._cradle = None
        # the short end at the top in upright portrait is the one that faces the frame in upright landscape and shelf portrait
        self.sd_end = d.get("microsd_edge") == ("l=L" if self.frame_edge == "s=0" else "l=0")

    def _check(self, d):
        """Stop on a definition that cannot be what was meant (a typo in a field name, a hole off the board, a box inside out)"""
        def bad(msg):
            raise SystemExit(f"boards/{self.name}.json: {msg} (see boards/README.md)")
        if not self.name.isalnum() or not self.name.isascii():
            bad("the file name is the board's name in the output file names: letters and digits only")
        for k in set(d) - set(FIELDS):
            bad(f"unknown field {k!r}")
        for k in [k for k, req in FIELDS.items() if req and k not in d]:
            bad(f"missing field {k!r}")
        L, S = d["size"]
        if not (L > 0 and S > 0):
            bad("size is [L, S], both above 0")
        if d["frame_edge"] not in ("s=0", "s=S"):
            bad('frame_edge is "s=0" or "s=S"')
        if d.get("microsd_edge", "l=0") not in ("l=0", "l=L", "s=0", "s=S"):
            bad('microsd_edge is "l=0", "l=L", "s=0" or "s=S"')
        sp = d["standoffs"]
        for k in set(sp) - STANDOFF_FIELDS:
            bad(f"unknown standoffs field {k!r}")
        for k in ("h", "d", "pilot", "screw"):
            if k not in sp:
                bad(f"missing standoffs field {k!r}")
        for l, s in d["holes"]:
            if not (0 < l < L and 0 < s < S):
                bad(f"hole {[l, s]} is off the {L} x {S} board")
        for p in sp.get("at", []):
            if p not in d["holes"]:
                bad(f"standoff {p} is not at one of the holes")
        for r in d.get("openings", []) + [p["box"] for p in d["parts"]]:
            if any(a >= b for a, b in zip(r[::2], r[1::2])):
                bad(f"{r} is not [from, to, ...] with each from below its to")
        for k in set(d.get("windows") or {}) - {"rows", "per_row"}:
            bad(f"unknown windows field {k!r}")
        for f, m in d.get("official_models", {}).items():
            if set(m) - MODEL_FIELDS or not {"rotate", "centre", "underside"} <= set(m):
                bad(f"official_models[{f!r}] has rotate, centre, underside and optionally tilt and exclude")
        c = d.get("cradle")
        if c is not None:
            if set(c) != CRADLE_FIELDS or set(c["lip"]) != LIP_FIELDS:
                bad("cradle has board, ledge, stop and lip, and lip has l, top and over")
            l0, l1, s0, s1, h0, h1 = c["board"]
            if not (l0 < l1 and s0 < s1 and CRADLE_PLATE < h0 < h1 < c["lip"]["top"]):
                bad("cradle board is [l0, l1, s0, s1, h0, h1] with h0 above the end plates and h1 below the lip's top")
            if min(s0, S - s1) - CRADLE_FIT < CRADLE_WALL_MIN:
                bad(f"the cradle's side walls are thinner than {CRADLE_WALL_MIN} mm: make S wider")
            if not l0 <= c["lip"]["l"][0] < c["lip"]["l"][1] <= l1:
                bad("cradle lip l is [from, to] along the board")
            a0, a1 = l0 - CRADLE_FIT - CRADLE_STOP_T, l1 + CRADLE_FIT + CRADLE_STOP_T
            for l, s in d["holes"]:
                if not (l + d["hole_d"] / 2 <= a0 - 1 or l - d["hole_d"] / 2 >= a1 + 1):
                    bad(f"hole {[l, s]} is not in an end plate of the cradle (l up to {a0 - 1:.2f} or from {a1 + 1:.2f}, less the hole)")

    def xy(self, l, s):
        """Board (l, s) -> bracket-local (x, y) on the upright-portrait front plate. Both ways round it is a turn, never a mirror"""
        if self.frame_edge == "s=0":
            return (l - self.L / 2, T + BOARD_Y0 + s)
        return (self.L / 2 - l, T + BOARD_Y0 + (self.S - s))

    def holes_xy(self):
        return [self.xy(l, s) for l, s in self.holes]

    def spacer_xy(self):
        return [self.xy(l, s) for l, s in self.standoff_at]

    def cuts(self):
        """Openings through the front plate as (x0, x1, y0, y1): the definition's openings, then its rows of windows (per_row
        windows in each row, between l = 6 and L - 6, RIB apart)"""
        rects = list(self.openings)
        if self.windows:
            n = self.windows["per_row"]; l0, l1 = 6.0, self.L - 6.0; wl = (l1 - l0 - (n - 1) * RIB) / n
            rects += [(a, a + wl, s0, s1) for s0, s1 in self.windows["rows"] for a in (l0 + i * (wl + RIB) for i in range(n))]
        out = []
        for l0, l1, s0, s1 in rects:
            (xa, ya), (xb, yb) = self.xy(l0, s0), self.xy(l1, s1)
            out.append((min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)))
        return out

    def cradle(self):
        """The cradle as printed, in the outline's coordinates (l, s, h) with h = 0 on the build plate; None for a board that
        is screwed on directly"""
        if self.cradle_def and self._cradle is None:
            self._cradle = cradle(self.cradle_def, self.L, self.S, self.holes, self.hole_d)
        return self._cradle

    def cradle_placed(self):
        """The cradle on the standoffs, in the board frame like ghost()"""
        rot = 0 if self.frame_edge == "s=0" else 180   # xy() is a translation for s=0 and a half turn for s=S
        return (Pos(0, T + BOARD_Y0 + self.S / 2, Z0 + T + self.standoffs["h"]) * Rot(0, 0, rot)
                * Pos(-self.L / 2, -self.S / 2, 0) * self.cradle())

    def ghost(self):
        """Simplified board for display and interference checks: the boxes of the definition's parts, their heights from the
        top of the standoffs (the underside of what sits on them)"""
        z = Z0 + T + self.standoffs["h"]; g = None
        for p in self.parts:
            l0, l1, s0, s1, h0, h1 = p["box"]
            (xa, ya), (xb, yb) = self.xy(l0, s0), self.xy(l1, s1)
            b = box(min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb), z + h0, z + h1)
            g = b if g is None else g + b
        return g

    def bracket(self, series, spacer=False, orient=None):
        if spacer and orient not in (None,) + SPACER_ORIENTS:
            raise ValueError(f"no integrated standoffs in {orient}: on a standing board plate they cannot print without support")
        if orient not in (None, UPRIGHT):
            return oriented(self, series, spacer, orient)
        H = self.L / 2
        s = _l_body(series, H, BOARD_Y0 + self.S)
        for x, y in self.holes_xy():
            s -= Pos(x, y, Z0 + T / 2) * Cylinder(self.hole_d / 2, T + 2)
        for c in self.cuts():
            s -= rrect(*c)
        s = _finish(s, series, H, T + BOARD_Y0 + self.S)
        if spacer:
            sp = self.standoffs
            s = add_spacers(s, self.spacer_xy(), sp["h"], sp["d"], sp["pilot"], sp.get("foot"))
        return s


BOARDS = [Board(p) for p in sorted(glob.glob(os.path.join(BOARD_DIR, "*.json")))]
SERIES = (20, 40, "DIN")


# ======================= Mounting orientations =======================
# The grip only prints one way up, so every orientation keeps it on the build plate (z = Z0) and changes how the board plate sits
# relative to it. A board's holes, openings and standoffs are defined once, on the upright-portrait front plate (the "board frame":
# holes_xy / cuts / spacer_xy / ghost / official_models), and place() moves them, the simplified board and the official 3D models to the
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
    return SD_GAP if B.sd_end and orient in ("upright-landscape", "shelf-portrait") else BOARD_Y0


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
        if hit(p.X, B.hole_d / 2):
            need = max(need, zc - (p.Z - B.hole_d / 2))
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
    L, S = B.L, B.S; g = gap(B, orient); xr = xr_of(series); sp = B.standoffs
    to = lambda xy: [tuple((M * Pos(x, y, Z0)).position) for x, y in xy]

    def rect(c):                                       # an opening of the board frame -> (x0, x1, y0, y1, z0, z1)
        (ax, ay, az), (bx, by, bz) = to([(c[0], c[2]), (c[1], c[3])])
        return min(ax, bx), max(ax, bx), min(ay, by), max(ay, by), min(az, bz), max(az, bz)

    if kind == "upright":                              # landscape: long side forward, the plate still lies on the build plate
        Hp = S / 2
        s = _l_body(series, Hp, g + L, Hb=max(Hp, xr))
        for x, y, _ in to(B.holes_xy()):
            s -= Pos(x, y, Z0 + T / 2) * Cylinder(B.hole_d / 2, T + 2)
        for x0, x1, y0, y1, _, _ in map(rect, B.cuts()):
            y0 = max(y0, T + FIL + 1.0)                # an opening that reaches past the board stops short of the gusset
            if y1 - y0 > 2 * WIN_R + 0.1 and x1 - x0 > 2 * WIN_R + 0.1:
                s -= rrect(x0, x1, y0, y1)
        s = _finish(s, series, Hp, T + g + L)
        if spacer:
            s = add_spacers(s, [(x, y) for x, y, _ in to(B.spacer_xy())], sp["h"], sp["d"], sp["pilot"], sp.get("foot"))
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
        s -= _vcut(kind, _tear(ac(p), p[2], B.hole_d / 2), n0 - 1, n1 + 1)
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
