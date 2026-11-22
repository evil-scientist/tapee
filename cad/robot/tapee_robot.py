#!/usr/bin/env python3
"""tapee robot body: detailed, printable model (approved concept A5).

Run:  ~/tools/cadquery/bin/cq-python cad/robot/tapee_robot.py [--check]
Out:  cad/robot/tapee_robot.step       coloured assembly (printed parts, printer, Pi, switch, M3 screws)
      cad/robot/stl/<colour>_<part>.stl each printed part, already turned to its print orientation
      cad/robot/render/                 render inputs (parts.json + STLs) for cad/render.py
      --check also reports overlaps between parts that must not touch

Frame: Z up, -Y is the face, +X is the robot's left (your right when you face it). Table at Z = 0.
The printer is panel-mounted in the flat face of the bottom half and held from behind by a clamp bar.
The body splits along the printer's paper-slot line. All fixings are M3 screws threaded into printed
pilot holes, apart from glued decoration.
"""
import json
import math
import sys
from pathlib import Path

import cadquery as cq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "printer"))
import dp_eh500 as prn  # noqa: E402

# ---------------------------------------------------------------- body shape
A, B = 70.0, 54.0  # half-width and half-depth of the elliptical body
Z0, BASE_H, DOME_H = 8.0, 78.0, 52.0  # body bottom (feet below), round lower part, dome height
J = Z0 + BASE_H  # dome starts here
TOP = J + DOME_H
WALL = 2.5
BOTTOM_CH = 2.0  # chamfer on the bottom edge (prints without overhang)
YF = -42.0  # flat front face

# ---------------------------------------------------------------- tolerances and screws
FIT = 0.2  # gap per side for glued and pressed parts
SLIDE = 0.25  # gap between the top half and the bottom half's lip
M3_CLEAR, M3_PILOT = 3.4, 2.7  # M3 screws thread straight into 2.7 mm printed holes
M3_HEAD_D, M3_HEAD_H = 5.7, 1.65  # button-head M3

# ---------------------------------------------------------------- face
EZ, EX = J, 30.0  # goggle centres
RING_OD, LENS_D, PUPIL_D = 40.0, 27.0, 12.0
STRAP_H, STRAP_T, STRAP_DIP = 16.0, 3.0, 4.0
EAR_D, EAR_OUT = 26.0, 9.0  # ear plate diameter, outer face distance from the body side

# ---------------------------------------------------------------- printer, seam, clamp
PY = YF + WALL + prn.FLANGE_T  # printer origin (flange back face): the flange sits INSIDE, against the inner face
#                                 of the wall (fitted that way by the user, 2026-11-21); only the cover pokes out
PZ = 15.0 - prn.COVER_BOT  # printer cover bottom 15 mm above the table
ZM = PZ + prn.SLOT_TOP  # the seam runs along the printer's paper slot
CUT_CLEAR = 0.4  # gap around the printer body in the face cut-out
LIP_T, LIP_H = 1.6, 6.0  # alignment lip on the bottom half
SEAM_SCREW_T = (20, 160, 55, 125)  # angles of the four seam screws (0 = robot's left, 90 = back)
SEAM_SCREW_DZ = 5.0  # screw height above the seam
CLAMP_Z0 = 50.0  # top of the clamp towers
TOWER_X, TOWER_Y = 46.0, -3.5  # clamp towers (already printed in the lower half: don't move them)
TOWER_D = 10.0  # front-to-back size of the towers
# Printer cradle (2026-11-21): sits on the floor under the paper bucket so the printer doesn't hang from the face,
# and its rear lip hugs the bucket's rounded rear-bottom edge (solid plastic; the back above it is hollow). Its posts
# step onto the printed towers through slots: slide it forward until the flange is pinned against the inside of the
# face, then tighten the two bolts.
FLOOR = Z0 + WALL  # top of the floor inside the bottom half
BUCKET_Z = PZ + prn.BODY_BOT  # underside of the printer's bucket
BUCKET_Y1 = PY + prn.BUCKET_D  # back of the bucket
CRADLE_FRONT = PY + 0.5  # front of the cradle, 0.5 mm behind the bucket's front: room to slide forward
CRADLE_REAR = BUCKET_Y1 + 4.0
CRADLE_SIDE = 0.3  # gap beside the bucket
CRADLE_LIP_H = 3.5  # side lips above the bucket's underside (the printer's side ledges are 5 mm up)
CRADLE_REAR_H = 8.0  # rear lip height: hugs the bucket's rounded rear-bottom edge
COL_Y0, COL_Y1 = -18.0, TOWER_Y - TOWER_D / 2 - 0.3  # posts stand just in front of the towers
TAB_Z0, TAB_Z1 = CLAMP_Z0 + 0.2, CLAMP_Z0 + 8.0  # tabs over the tower tops
CRADLE_SLIDE = 2.0  # the slots let the cradle slide this far either way

# ---------------------------------------------------------------- Pi Zero W
PI_C = (0.0, 16.0)  # board centre; ports face the back
PI_Z = Z0 + WALL + 4.0  # board underside (standoff height 4)
REAR_OPEN = (-11.0, 40.0, 17.75, 12.5)  # rear cable opening: centre x, width, centre z, height

# ---------------------------------------------------------------- button (12 x 12 mm tactile switch)
SWITCH_W, SWITCH_BODY_H = 12.0, 3.6
SWITCH_H = 10.8  # [M] bottom of the switch body to the top of its white cap
CAP_D, PLUNGER_D = 22.0, 12.4
CAP_BOTTOM = TOP + 1.0  # cap underside at rest
RET_TOP = TOP - WALL - 1.5  # retainer disc under the top, 1.5 mm of lift before it stops
RET_T = 2.0
SW_TOP = RET_TOP - RET_T - M3_HEAD_H - 0.3  # the retainer screw head presses the switch
SW_BASE = SW_TOP - SWITCH_H
HOLDER_T, HOLDER_BOSS_X = 2.0, 15.0

FEET = ((-38, -24), (38, -24), (-38, 24), (38, 24))


# ================================================================ helpers
def body(off=0.0):
    """Body offset inwards by off (negative = grown), including the flat front at YF + off."""
    a, b = A - off, B - off
    base = (cq.Workplane("XY").ellipse(a, b).extrude(J - (Z0 + off)).translate((0, 0, Z0 + off))
            .edges("<Z").chamfer(max(BOTTOM_CH - 0.4 * max(off, 0), 0.4)))
    sph = cq.Workplane("XY").sphere(50).val().transformGeometry(
        cq.Matrix([[a / 50, 0, 0, 0], [0, b / 50, 0, 0], [0, 0, (DOME_H - off) / 50, 0]]))
    dome = (cq.Workplane("XY").add(sph).translate((0, 0, J))
            .intersect(cq.Workplane("XY").box(400, 400, 200, centered=(True, True, False)).translate((0, 0, J))))
    flat = cq.Workplane("XY").box(400, 200, 400).translate((0, YF + off - 100, 0))
    return base.union(dome).cut(flat)


OUTER, INNER = body(0), body(WALL)


def slab(z0, z1):
    return cq.Workplane("XY").box(400, 400, z1 - z0, centered=(True, True, False)).translate((0, 0, z0))


def skin(t):
    return body(-t).cut(OUTER)


def front_prism(sketch):
    return sketch(cq.Workplane("XZ", origin=(0, -90, 0))).extrude(-90)


def cyl(p, axis, d, length, both=False):
    """Cylinder of diameter d starting at p along axis (or centred on p if both)."""
    axis = cq.Vector(*axis).normalized()
    s = cq.Solid.makeCylinder(d / 2, length, cq.Vector(*p) - (axis * (length / 2) if both else cq.Vector()), axis)
    return cq.Workplane("XY").add(s)


def orient(shape, n, p):
    """Turn a part built along +Z at the origin so +Z points along n, then move it to p."""
    n = cq.Vector(*n).normalized()
    z = cq.Vector(0, 0, 1)
    axis = z.cross(n)
    if axis.Length < 1e-9:
        s = shape if n.z > 0 else shape.rotate((0, 0, 0), (1, 0, 0), 180)
    else:
        s = shape.rotate((0, 0, 0), axis.toTuple(), math.degrees(math.acos(max(-1.0, min(1.0, z.dot(n))))))
    return s.translate(tuple(p))


def wall_point(t_deg, z, out=0.0):
    t = math.radians(t_deg)
    n = cq.Vector(math.cos(t) / A, math.sin(t) / B, 0).normalized()
    return cq.Vector(A * math.cos(t), B * math.sin(t), z) + n * out, n


def dome_point(x, y_sign, z, out=0.0):
    k = math.sqrt(1 - ((z - J) / DOME_H) ** 2)
    y = y_sign * B * k * math.sqrt(max(0.0, 1 - (x / (A * k)) ** 2))
    n = cq.Vector(x / A ** 2, y / B ** 2, (z - J) / DOME_H ** 2).normalized()
    return cq.Vector(x, y, z) + n * out, n


def compound(shapes):
    return cq.Workplane("XY").add(cq.Compound.makeCompound([s.val() for s in shapes]))


def union_all(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out.union(s)
    return out


def rivet(d=4.5, h=1.5):
    r = d / 2
    return (cq.Workplane("XY").sphere(r).translate((0, 0, h - r))
            .intersect(cq.Workplane("XY").box(d + 1, d + 1, 5, centered=(True, True, False)).translate((0, 0, -2))))


def phillips(d=6.0):
    head = cq.Workplane("XY").circle(d / 2).extrude(2.6).translate((0, 0, -1.2)).edges(">Z").fillet(0.9)
    for ang in (0, 90):
        head = head.cut(cq.Workplane("XY").box(d * 0.62, 0.8, 1.0).translate((0, 0, 1.4))
                        .rotate((0, 0, 0), (0, 0, 1), ang))
    return head


def m3_screw(length):
    """Button-head M3 screw: head sits on z = 0 facing +Z, shank goes down to -length."""
    head = (cq.Workplane("XY").circle(M3_HEAD_D / 2).extrude(M3_HEAD_H).edges(">Z").fillet(0.8)
            .cut(cq.Workplane("XY").polygon(6, 2.3).extrude(1.0).translate((0, 0, M3_HEAD_H - 1.0))))
    return head.union(cq.Workplane("XY").circle(1.5).extrude(-length))


# ================================================================ halves
def box_y(w, z_top, z_bot):
    return (cq.Workplane("XY").box(w, 40, z_top - z_bot, centered=(True, True, False))
            .translate((0, YF + 10, z_bot)))


def printer_cutout():
    c = CUT_CLEAR
    wide_bot = PZ + prn.FT - prn.LEDGE_DROP - prn.LEDGE_T - c
    wide = box_y(prn.UPPER_W + 2 * c, PZ + prn.UPPER_TOP + c, wide_bot)
    narrow = box_y(prn.BUCKET_W + 2 * c, wide_bot + 1, PZ + prn.BODY_BOT - c)
    return wide.union(narrow)


def seam_screw_points():
    return [wall_point(t, ZM + SEAM_SCREW_DZ) for t in SEAM_SCREW_T]


def seam_blocks():
    """Blocks inside the bottom half that rise above the seam; the top half is screwed to them."""
    out = []
    for t in SEAM_SCREW_T:
        p, n = wall_point(t, ZM)
        blk = (cq.Workplane("XY").box(14, 12, 17).rotate((0, 0, 0), (0, 0, 1), math.degrees(math.atan2(n.y, n.x)))
               .translate((p.x - n.x * 7, p.y - n.y * 7, ZM + 0.5)))
        low = blk.intersect(body(WALL)).intersect(slab(-10, ZM))
        high = blk.intersect(body(WALL + SLIDE)).intersect(slab(ZM, 200))
        out.append(low.union(high))
    blocks = union_all(out)
    for p, n in seam_screw_points():
        blocks = blocks.cut(cyl(p + n * 1, -n, M3_PILOT, 14))
    return blocks


def lip():
    low = INNER.cut(body(WALL + SLIDE + LIP_T)).intersect(slab(ZM - 3, ZM))
    high = body(WALL + SLIDE).cut(body(WALL + SLIDE + LIP_T)).intersect(slab(ZM, ZM + LIP_H))
    return low.union(high).cut(cq.Workplane("XY").box(94, 60, 40).translate((0, -50, ZM)))


def riveted_band():
    band = slab(ZM - 11, ZM - 1).intersect(skin(1.2))
    band = band.cut(cq.Workplane("XY").box(2 * 47, 60, 40).translate((0, YF - 30 + 8, ZM - 6)))
    rivets = [orient(rivet(), wall_point(t, ZM - 6, out=1.2)[1], wall_point(t, ZM - 6, out=1.2)[0])
              for t in range(-30, 211, 15)]
    return band.union(compound(rivets))


def side_vents(sx):
    side = cq.Workplane("XY").box(200, 400, 400).translate((sx * 100, 0, 0))
    panel = (cq.Workplane("YZ", origin=(sx * 90, 0, 0)).center(0, 28).rect(40, 20).extrude(-sx * 60)
             .edges("|X").fillet(3)).intersect(skin(1.2)).intersect(side)
    slots = union_all([cq.Workplane("YZ", origin=(sx * 90, 0, 0)).center(0, z).slot2D(28, 2.2).extrude(-sx * 40)
                       for z in (22, 26, 30, 34)])
    screws = []
    for y in (-16, 16):
        for z in (20.5, 35.5):
            x = sx * A * math.sqrt(1 - (y / B) ** 2)
            n = cq.Vector(x / A ** 2, y / B ** 2, 0).normalized()
            screws.append(orient(phillips(4.6), n, cq.Vector(x, y, z) + n * 1.2))
    return panel.cut(slots).union(compound(screws)), slots


def clamp_towers():
    out = []
    for sx in (-1, 1):
        t = (cq.Workplane("XY").rect(12, TOWER_D).extrude(CLAMP_Z0 - (Z0 + WALL) + 1).edges("|Z").fillet(3)
             .translate((sx * TOWER_X, TOWER_Y, Z0 + WALL - 1)))
        out.append(t.cut(cyl((sx * TOWER_X, TOWER_Y, CLAMP_Z0 + 1), (0, 0, -1), M3_PILOT, 14)))
    return union_all(out)


def pi_holes():
    out = []
    for x, y in ((3.5, 3.5), (61.5, 3.5), (3.5, 26.5), (61.5, 26.5)):
        out.append((PI_C[0] - (x - 32.5), PI_C[1] - (y - 15)))  # board turned 180 degrees: ports to the back
    return out


def pi_standoffs():
    out = []
    for x, y in pi_holes():
        post = cq.Workplane("XY").circle(2.75).extrude(PI_Z - (Z0 + WALL) + 0.5).translate((x, y, Z0 + WALL - 0.5))
        pin = (cq.Workplane("XY").circle(1.2).extrude(2.6).translate((x, y, PI_Z)).edges(">Z").chamfer(0.4))
        out.append(post.union(pin))
    return union_all(out)


def lower_half():
    wall = OUTER.cut(INNER)
    lower = wall.intersect(slab(-10, ZM)).union(lip()).union(seam_blocks())
    lower = lower.union(riveted_band())
    for sx in (-1, 1):
        vents, slots = side_vents(sx)
        lower = lower.cut(slots).union(vents)
    lower = lower.union(clamp_towers()).union(pi_standoffs())
    lower = lower.cut(printer_cutout())
    cx, w, cz, h = REAR_OPEN
    lower = lower.cut(cq.Workplane("XY").box(w, 30, h).edges("|Y").fillet(4).translate((cx, B, cz)))
    for fx, fy in FEET:
        lower = lower.cut(cyl((fx, fy, Z0 - 1), (0, 0, 1), 5.0 + 2 * FIT, WALL + 2))
    return lower


# ================================================================ top half
def dome_lines():
    cut, rivets = [], []
    for sx in (-1, 1):
        cut.append(cq.Workplane("XY").box(1.0, 300, 300).translate((sx * 24, 0, 0))
                   .intersect(OUTER.cut(body(0.7))).intersect(slab(EZ + STRAP_H / 2 + 1, 400))
                   .intersect(cq.Workplane("XY").box(400, 400, 400).translate((0, 200 - 28, 0))))
        for z in (J + 12, J + 26, J + 40):
            p, n = dome_point(sx * 28, 1, z)
            rivets.append(orient(rivet(3.6, 1.2), n, p))
    return union_all(cut), compound(rivets)


def button_bezel():
    ring = (cq.Workplane("XY").circle(15.5).circle(11.6).extrude(30).translate((0, 0, TOP - 20)).intersect(skin(1.6)))
    rivets = []
    for i in range(4):
        a = math.radians(45 + 90 * i)
        x, y = 13.5 * math.cos(a), 13.5 * math.sin(a)
        rivets.append(rivet(2.6, 0.9).translate((x, y, J + DOME_H * math.sqrt(1 - (x / A) ** 2 - (y / B) ** 2) + 1.6)))
    return ring.union(compound(rivets))


NAME_Z = (ZM + EZ - STRAP_H / 2) / 2
NAME_PAD_Y = B + 0.4  # flat pad face on the back of the head
NAME_SCREW_X = 20.5


def nameplate_pad():
    pad = (cq.Workplane("XZ", origin=(0, NAME_PAD_Y, 0)).center(0, NAME_Z).rect(52, 14).extrude(25)
           .edges("|Y").fillet(2)).cut(INNER)
    bosses = [cyl((sx * NAME_SCREW_X, 38, NAME_Z), (0, 1, 0), 7, 14).intersect(INNER) for sx in (-1, 1)]
    return pad.union(union_all(bosses))


def nameplate_holes():
    return union_all([cyl((sx * NAME_SCREW_X, 38, NAME_Z), (0, 1, 0), M3_PILOT, 30) for sx in (-1, 1)])


def ear_holes():
    """Pilot holes and inner bosses for the ear screws."""
    bosses = union_all([cyl((sx * (A - 13), 0, EZ), (sx, 0, 0), 8, 12) for sx in (-1, 1)]).intersect(OUTER)
    holes = union_all([cyl((sx * (A - 15), 0, EZ), (sx, 0, 0), M3_PILOT, 30) for sx in (-1, 1)])
    return bosses, holes


def switch_bosses():
    out = []
    for sx in (-1, 1):
        b = cq.Workplane("XY").circle(3.5).extrude(TOP - SW_BASE).translate((sx * HOLDER_BOSS_X, 0, SW_BASE))
        b = b.intersect(OUTER).cut(cyl((sx * HOLDER_BOSS_X, 0, SW_BASE - 1), (0, 0, 1), M3_PILOT, 10))
        out.append(b)
    return union_all(out)


def upper_half():
    upper = OUTER.cut(INNER).intersect(slab(ZM, 300)).cut(printer_cutout())
    grooves, dome_rivets = dome_lines()
    upper = upper.cut(grooves).union(dome_rivets).union(button_bezel())
    upper = upper.union(nameplate_pad()).cut(nameplate_holes())
    bosses, holes = ear_holes()
    upper = upper.union(bosses).cut(holes)
    upper = upper.union(switch_bosses())
    upper = upper.cut(cyl((0, 0, TOP - 15), (0, 0, 1), PLUNGER_D + 0.8, 30))  # button hole
    for p, n in seam_screw_points():
        upper = upper.cut(cyl(p + n * 2, -n, M3_CLEAR, 8))
    return upper


# ================================================================ glued-on and loose parts
def strap():
    s = slab(EZ - STRAP_H / 2, EZ + STRAP_H / 2).intersect(skin(STRAP_T))
    r = 40  # nose bridge
    for sgn in (1, -1):
        s = s.cut(front_prism(lambda w: w.center(0, EZ + sgn * (STRAP_H / 2 + r - STRAP_DIP)).circle(r)))
    for sx in (-1, 1):  # thinned to 1.5 mm behind the goggles; the goggle parts are notched to sit over it
        s = s.cut(goggle_disc((sx * EX, EZ), RING_OD + 1, YF - 6, YF - 1.5))
    rivets = [orient(rivet(3.6, 1.2), wall_point(t, EZ, out=STRAP_T)[1], wall_point(t, EZ, out=STRAP_T)[0])
              for t in range(30, 151, 20)]
    s = s.union(compound(rivets))
    return s.cut(union_all([cyl((sx * A, 0, EZ), (1, 0, 0), M3_CLEAR, 20, both=True) for sx in (-1, 1)]))


def goggle_disc(c, d, y_front, y_back=YF + 12):
    return cq.Workplane("XZ", origin=(0, y_back, 0)).center(*c).circle(d / 2).extrude(y_back - y_front)


RING_FRONT, LENS_FRONT = YF - 4.0, YF - 2.6


def goggles(strap_shape):
    out = {}
    for side, sx in (("left", 1), ("right", -1)):
        c = (sx * EX, EZ)
        ring = goggle_disc(c, RING_OD, RING_FRONT).cut(goggle_disc(c, LENS_D, RING_FRONT - 1))
        out[f"ring_{side}"] = ring.cut(OUTER).cut(strap_shape)
        lens = goggle_disc(c, LENS_D - 2 * FIT, LENS_FRONT).cut(OUTER).cut(strap_shape)
        out[f"lens_{side}"] = lens.cut(goggle_disc(c, PUPIL_D + 2 * FIT, LENS_FRONT - 1, LENS_FRONT + 0.6))
        out[f"pupil_{side}"] = goggle_disc(c, PUPIL_D, LENS_FRONT - 0.8, LENS_FRONT + 0.6)
    return out


def ears(strap_shape):
    out = {}
    for side, sx in (("left", 1), ("right", -1)):
        x_out = sx * (A + EAR_OUT)
        plate = (cq.Workplane("YZ", origin=(sx * (A - 3), 0, 0)).center(0, EZ).circle(EAR_D / 2)
                 .extrude(sx * (EAR_OUT + 3)).faces(">X" if sx > 0 else "<X").edges().fillet(1.5))
        plate = plate.cut(OUTER).cut(strap_shape)
        plate = plate.cut(cyl((sx * (A - 5), 0, EZ), (sx, 0, 0), M3_CLEAR, 20))
        plate = plate.cut(cyl((x_out + sx, 0, EZ), (-sx, 0, 0), 6.5, 4))  # counterbore for the screw head
        out[f"ear_{side}"] = plate
        bolt = (cq.Workplane("XY").circle(7).extrude(1.0)
                .union(cq.Workplane("XY").polygon(6, 12).extrude(4.0).translate((0, 0, 1.0)).edges(">Z").chamfer(0.6))
                .union(cq.Workplane("XY").circle(3.1).extrude(-1.2)))  # spigot locates it in the counterbore
        out[f"bolt_{side}"] = orient(bolt, (sx, 0, 0), (x_out, 0, EZ))
    return out


def nameplate():
    plate = (cq.Workplane("XZ", origin=(0, NAME_PAD_Y, 0)).center(0, NAME_Z).rect(50, 12).extrude(-2.0)
             .edges("|Y").fillet(2))
    plane = cq.Plane(origin=(0, NAME_PAD_Y + 2.0, NAME_Z), xDir=(-1, 0, 0), normal=(0, 1, 0))
    plate = plate.union(cq.Workplane(plane).text("TAPEE", 7, 0.8, combine=False, halign="center",
                                                  valign="center", font="DejaVu Sans", kind="bold"))
    return plate.cut(union_all([cyl((sx * NAME_SCREW_X, NAME_PAD_Y - 1, NAME_Z), (0, 1, 0), M3_CLEAR, 5)
                                for sx in (-1, 1)]))


def button_parts():
    cap = (cq.Workplane("XY").circle(CAP_D / 2).extrude(6).edges(">Z").fillet(4).translate((0, 0, CAP_BOTTOM))
           .union(cq.Workplane("XY").circle(PLUNGER_D / 2).extrude(CAP_BOTTOM - RET_TOP).translate((0, 0, RET_TOP))))
    cap = cap.cut(cyl((0, 0, RET_TOP - 0.1), (0, 0, 1), M3_PILOT, 8))
    retainer = (cq.Workplane("XY").circle(9).extrude(RET_T).translate((0, 0, RET_TOP - RET_T))
                .cut(cyl((0, 0, RET_TOP - RET_T - 1), (0, 0, 1), M3_CLEAR, 5)))
    w = SWITCH_W + 2 * FIT
    holder = (cq.Workplane("XY").box(40, 16, HOLDER_T, centered=(True, True, False)).edges("|Z").fillet(3)
              .union(cq.Workplane("XY").rect(w + 3.2, w + 3.2).rect(w, w).extrude(3)
                     .translate((0, 0, HOLDER_T)))
              .translate((0, 0, SW_BASE - HOLDER_T)))
    for sx in (-1, 1):
        holder = holder.cut(cyl((sx * HOLDER_BOSS_X, 0, SW_BASE - 5), (0, 0, 1), M3_CLEAR, 10))
        holder = holder.cut(cq.Workplane("XY").box(2.6, 10, 10).translate((sx * 6.2, 0, SW_BASE - HOLDER_T)))  # legs
    switch = (cq.Workplane("XY").box(SWITCH_W, SWITCH_W, SWITCH_BODY_H, centered=(True, True, False))
              .union(cq.Workplane("XY").box(SWITCH_W - 0.5, SWITCH_W - 0.5, SWITCH_H - SWITCH_BODY_H,
                                            centered=(True, True, False)).translate((0, 0, SWITCH_BODY_H)))
              .translate((0, 0, SW_BASE)))
    return cap, retainer, holder, switch


def printer_cradle():
    """Cradle under the printer's bucket, tied to the clamp towers. See the notes at CRADLE_FRONT."""
    bw = prn.BUCKET_W / 2
    xo = bw + CRADLE_SIDE + 2.2
    slab = cq.Workplane("XY").box(2 * xo, CRADLE_REAR - CRADLE_FRONT, BUCKET_Z - FLOOR, centered=(True, False, False))
    parts = [slab.translate((0, CRADLE_FRONT, FLOOR))]
    for sx in (-1, 1):
        lip = cq.Workplane("XY").box(xo - bw - CRADLE_SIDE, BUCKET_Y1 - CRADLE_FRONT - 1, CRADLE_LIP_H, centered=False)
        parts.append(lip.translate((bw + CRADLE_SIDE if sx > 0 else -xo, CRADLE_FRONT, BUCKET_Z)))
        bar = cq.Workplane("XY").box(TOWER_X + 6 - (bw - 3), COL_Y1 - COL_Y0, 6, centered=False)
        parts.append(bar.translate((bw - 3 if sx > 0 else -(TOWER_X + 6), COL_Y0, FLOOR)))
        post = cq.Workplane("XY").box(12, COL_Y1 - COL_Y0, TAB_Z1 - FLOOR, centered=(True, False, False))
        parts.append(post.translate((sx * TOWER_X, COL_Y0, FLOOR)))
        tab = (cq.Workplane("XY").box(12, TOWER_Y + TOWER_D / 2 - COL_Y0, TAB_Z1 - TAB_Z0, centered=(True, False, False))
               .edges("|Z and >Y").fillet(3).translate((sx * TOWER_X, COL_Y0, TAB_Z0)))
        parts.append(tab)
    rear = cq.Workplane("XY").box(2 * (bw - 2), CRADLE_REAR - (BUCKET_Y1 - prn.BUCKET_R), BUCKET_Z + CRADLE_REAR_H - FLOOR,
                                  centered=(True, False, False))
    parts.append(rear.translate((0, BUCKET_Y1 - prn.BUCKET_R, FLOOR)))
    cradle = union_all(parts)
    housing, pcb, conn, _keepout, pcb_parts = (s.translate((0, PY, PZ)) for s in prn.build())
    cradle = cradle.cut(housing).cut(pcb).cut(pcb_parts)
    for sx in (-1, 1):
        slot = (cq.Workplane("XY").slot2D(M3_CLEAR + 2 * CRADLE_SLIDE, M3_CLEAR, angle=90).extrude(TAB_Z1 - TAB_Z0 + 2)
                .translate((sx * TOWER_X, TOWER_Y, TAB_Z0 - 1)))
        cradle = cradle.cut(slot)
    return cradle


def foot():
    f = cq.Workplane("XY").circle(7).workplane(offset=Z0).circle(5).loft()
    return f.union(cq.Workplane("XY").circle(2.5).extrude(WALL - 0.3).translate((0, 0, Z0)))


def pi_zero():
    board = cq.Workplane("XY").box(65, 30, 1.6, centered=False).edges("|Z").fillet(3)
    for x, y in ((3.5, 3.5), (61.5, 3.5), (3.5, 26.5), (61.5, 26.5)):
        board = board.cut(cq.Workplane("XY").center(x, y).circle(1.375).extrude(5, both=True))
    comps = cq.Workplane("XY").box(51, 5, 8.5, centered=False).translate((7, 24, 1.6))
    for x0, w, d, h in ((6.8, 11.2, 7.6, 3.3), (37.4, 8, 5.6, 2.6), (50, 8, 5.6, 2.6)):
        comps = comps.union(cq.Workplane("XY").box(w, d, h, centered=False).translate((x0, -0.5, 1.6)))
    comps = comps.union(cq.Workplane("XY").box(12, 12, 1.2, centered=False).translate((22, 9, 1.6)))
    place = lambda s: (s.translate((-32.5, -15, 0)).rotate((0, 0, 0), (0, 0, 1), 180)
                       .translate((PI_C[0], PI_C[1], PI_Z)))
    return place(board), place(comps)


def slip(drop=45):
    y0 = PY + prn.FF - prn.COVER_D_MAX
    z = PZ + prn.SLOT_TOP - prn.SLOT_H / 2
    pts = [cq.Vector(0, y0 + 3, z), cq.Vector(0, y0 - 1, z), cq.Vector(0, y0 - 6, z - 4),
           cq.Vector(0, y0 - 8, z - 16), cq.Vector(0, y0 - 9, z - drop)]
    path = cq.Wire.assembleEdges([cq.Edge.makeSpline(pts)])
    return cq.Workplane("XZ", origin=(0, pts[0].y, pts[0].z)).rect(56, 0.35).sweep(cq.Workplane().add(path))


def screws():
    """Every M3 screw, as (name, length, shape)."""
    out = []
    for i, (p, n) in enumerate(seam_screw_points()):
        out.append((f"seam_{i}", 8, orient(m3_screw(8), n, p)))
    for sx in (-1, 1):
        out.append((f"clamp_{sx}", 16, m3_screw(16).translate((sx * TOWER_X, TOWER_Y, TAB_Z1))))
        out.append((f"holder_{sx}", 8, orient(m3_screw(8), (0, 0, -1), (sx * HOLDER_BOSS_X, 0, SW_BASE - HOLDER_T))))
        out.append((f"ear_{sx}", 16, orient(m3_screw(16), (sx, 0, 0), (sx * (A + EAR_OUT - 3), 0, EZ))))
        out.append((f"name_{sx}", 12, orient(m3_screw(12), (0, 1, 0), (sx * NAME_SCREW_X, NAME_PAD_Y + 2.0, NAME_Z))))
    out.append(("retainer", 8, orient(m3_screw(8), (0, 0, -1), (0, 0, RET_TOP - RET_T))))
    return out


# ================================================================ assembly
# name: (shape, colour, kind for rendering, print orientation)
#   print orientation: ("bed",) as modelled, ("x", deg) / ("y", deg) rotate first, ("flip",) upside down
COLOURS = {"blue": [0.16, 0.38, 0.85], "yellow": [0.98, 0.8, 0.12], "black": [0.08, 0.08, 0.09],
           "white": [0.96, 0.96, 0.94], "grey": [0.6, 0.61, 0.63], "any": [0.55, 0.55, 0.6],
           "printer": [0.1, 0.1, 0.11], "pcb": [0.1, 0.5, 0.2], "metal": [0.78, 0.78, 0.76],
           "keepout": [1.0, 0.35, 0.35, 0.35]}


def build():
    st = strap()
    parts = {
        "lower_half": (lower_half(), "blue", "shell", ("bed",)),
        "upper_half": (upper_half(), "yellow", "shell", ("bed",)),
        "strap": (st, "black", "outside", ("bed",)),
        "nameplate": (nameplate(), "black", "outside", ("x", 90)),
    }
    for k, v in goggles(st).items():
        colour = "black" if k.startswith(("ring", "pupil")) else "white"
        parts[k] = (v, colour, "outside", ("x", 90))
    for k, v in ears(st).items():
        side = 1 if k.endswith("left") else -1
        if k.startswith("ear"):
            parts[k] = (v, "black", "outside", ("y", 90 * side))
        else:
            parts[k] = (v, "grey", "outside", ("y", 90 * side))  # hex top on the bed, spigot up
    cap, retainer, holder, switch = button_parts()
    parts["button_cap"] = (cap, "white", "outside", ("flip",))
    parts["button_retainer"] = (retainer, "any", "inside", ("bed",))
    parts["switch_holder"] = (holder, "any", "inside", ("bed",))
    parts["printer_cradle"] = (printer_cradle(), "any", "inside", ("bed",))  # supports under the two tabs
    for i, (fx, fy) in enumerate(FEET):
        parts[f"foot_{i}"] = (foot().translate((fx, fy, 0)), "black", "outside", ("bed",))
    return parts


def bought_parts():
    housing, pcb, conn, keepout, pcb_parts = (s.translate((0, PY, PZ)) for s in prn.build())
    board, comps = pi_zero()
    cap, retainer, holder, switch = button_parts()
    out = {"printer": (housing, "printer", "device"), "printer_pcb": (pcb.union(conn).union(pcb_parts), "pcb", "inside"),
           "cable_keepout": (keepout, "keepout", "inside"), "pi_board": (board, "pcb", "inside"),
           "pi_parts": (comps, "metal", "inside"), "switch": (switch, "black", "inside")}
    for name, length, shape in screws():
        out[f"screw_{name}"] = (shape, "metal", "outside" if not name.startswith(("clamp", "holder", "retainer"))
                                else "inside")
    return out


def print_pose(shape, pose):
    if pose[0] == "x":
        shape = shape.rotate((0, 0, 0), (1, 0, 0), pose[1])
    elif pose[0] == "y":
        shape = shape.rotate((0, 0, 0), (0, 1, 0), pose[1])
    elif pose[0] == "flip":
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    bb = shape.val().BoundingBox()
    return shape.translate((-bb.center.x, -bb.center.y, -bb.zmin))


def check(parts, bought):
    """Report overlaps between parts that must not touch."""
    shapes = {k: v[0] for k, v in parts.items()}
    shapes.update({k: v[0] for k, v in bought.items()})
    pairs = [("printer", "lower_half"), ("printer", "upper_half"), ("printer", "printer_cradle"),
             ("printer_pcb", "printer_cradle"), ("printer_pcb", "lower_half"), ("cable_keepout", "pi_parts"),
             ("cable_keepout", "pi_board"), ("cable_keepout", "printer_cradle"), ("pi_board", "lower_half"),
             ("pi_parts", "lower_half"), ("lower_half", "upper_half"), ("strap", "upper_half"),
             ("ring_left", "strap"), ("lens_left", "ring_left"), ("ear_left", "strap"), ("ear_left", "upper_half"),
             ("button_cap", "upper_half"), ("button_retainer", "upper_half"), ("switch_holder", "upper_half"),
             ("switch", "switch_holder"), ("switch", "button_retainer"), ("printer_cradle", "upper_half"),
             ("printer_cradle", "lower_half"), ("nameplate", "upper_half"), ("foot_0", "lower_half"),
             ("bolt_left", "ear_left"), ("pupil_left", "lens_left")]
    print("overlap check (mm^3; contact faces show as ~0):")
    for a, b in pairs:
        try:
            v = shapes[a].intersect(shapes[b]).val().Volume()
        except Exception as e:  # noqa: BLE001
            v = float("nan")
            print(f"  {a:16s} x {b:16s}  failed: {e}")
            continue
        flag = "  <-- overlap" if v > 1.0 else ""
        print(f"  {a:16s} x {b:16s}  {v:9.2f}{flag}")
    gap = shapes["printer_cradle"].val().distance(shapes["printer_pcb"].val())
    print(f"clearance printer_cradle to printer_pcb (incl. parts envelope): {gap:.2f} mm")
    towers = clamp_towers()
    gap = shapes["printer_cradle"].val().distance(towers.val())
    print(f"cradle tabs above the towers: {gap:.2f} mm")
    for k in ("lower_half", "upper_half", "pi_parts", "cable_keepout"):
        print(f"clearance printer_cradle to {k}: {shapes['printer_cradle'].val().distance(shapes[k].val()):.2f} mm")


if __name__ == "__main__":
    parts = build()
    bought = bought_parts()
    if "--check" in sys.argv:
        check(parts, bought)

    asm = cq.Assembly(name="tapee_robot")
    for k, (shape, colour, *_rest) in list(parts.items()) + list(bought.items()):
        asm.add(shape, name=k, color=cq.Color(*COLOURS[colour]))
    asm.export(str(HERE / "tapee_robot.step"))

    stl_dir = HERE / "stl"
    stl_dir.mkdir(exist_ok=True)
    for old in stl_dir.glob("*.stl"):
        old.unlink()
    done = set()
    for k, (shape, colour, kind, pose) in parts.items():
        base = "foot" if k.startswith("foot_") else k
        if base in done:
            continue
        done.add(base)
        name = f"{colour}_{base}{'_x4' if base == 'foot' else ''}.stl"
        cq.exporters.export(print_pose(shape, pose), str(stl_dir / name), tolerance=0.02, angularTolerance=0.1)

    rdir = HERE / "render"
    rdir.mkdir(exist_ok=True)
    explode = {"upper_half": (0, 0, 95), "strap": (0, 0, 150), "button_cap": (0, 0, 185),
               "nameplate": (0, 45, 95), "ear_left": (40, 0, 95), "ear_right": (-40, 0, 95),
               "bolt_left": (70, 0, 95), "bolt_right": (-70, 0, 95), "button_retainer": (0, 0, 75),
               "switch_holder": (0, 0, 60), "switch": (0, 0, 66), "printer_cradle": (0, 30, 40),
               "printer": (0, -80, 0), "printer_pcb": (0, -80, 0), "pi_board": (0, 0, 25), "pi_parts": (0, 0, 25)}
    for side, sx in (("left", 1), ("right", -1)):
        explode.update({f"ring_{side}": (sx * 30, -60, 95), f"lens_{side}": (sx * 30, -95, 95),
                        f"pupil_{side}": (sx * 30, -125, 95)})
    for i in range(4):
        explode[f"foot_{i}"] = (0, 0, -25)
    closed, exploded = [], []
    everything = {k: (v[0], v[1], v[2]) for k, v in parts.items()}
    everything.update(bought)
    everything["paper"] = (slip(), "white", "outside")
    for k, (shape, colour, kind) in everything.items():
        f = rdir / f"c_{k}.stl"
        cq.exporters.export(shape, str(f), tolerance=0.05, angularTolerance=0.15)
        closed.append(dict(file=f.name, color=COLOURS[colour], kind=kind))
        if k in ("paper", "cable_keepout"):
            continue
        d = explode.get(k)
        if d is None and k.startswith("screw_"):
            d = {"seam": (0, 0, 95), "clamp": (0, 30, 40), "holder": (0, 0, 40), "retainer": (0, 0, 55),
                 "ear": None, "name": (0, 70, 95)}[k.split("_")[1]]
            if d is None:
                d = (105, 0, 95) if k.endswith("_1") else (-105, 0, 95)
        f = rdir / f"e_{k}.stl"
        cq.exporters.export(shape.translate(d or (0, 0, 0)), str(f), tolerance=0.05, angularTolerance=0.15)
        exploded.append(dict(file=f.name, color=COLOURS[colour], kind="device" if kind == "inside" else kind))
    bb = cq.Compound.makeCompound([v[0].val() for k, v in parts.items()]).BoundingBox()
    size = f"{bb.xlen:.0f} W x {bb.ylen:.0f} D x {bb.zlen:.0f} H mm"
    manifest = {
        "robot_front": dict(title=f"tapee  ({size})", parts=closed,
                            cutaway="cutaway: printer clamp, Pi on standoffs, button switch under the cap"),
        "robot_back": dict(title="back: nameplate, seam screws, cable opening", parts=closed, camera=[300, 380, 210]),
        "robot_exploded": dict(title="exploded, with the M3 screws", parts=exploded),
    }
    manifest["robot_back_exploded"] = dict(title="", grid=["robot_back", "robot_exploded"])
    (rdir / "parts.json").write_text(json.dumps(manifest, indent=1))
    n_screws = {}
    for name, length, _ in screws():
        n_screws[length] = n_screws.get(length, 0) + 1
    print("built", size, "| seam Z %.1f | switch base Z %.1f" % (ZM, SW_BASE))
    print("M3 button-head screws:", ", ".join(f"{n} x M3x{l}" for l, n in sorted(n_screws.items())))
    print("STLs:", ", ".join(sorted(p.name for p in stl_dir.glob("*.stl"))))
