#!/usr/bin/env python3
"""Parametric 3D model of the DP-EH500 panel thermal printer (Adafruit "Nano" #2752 type).

Run:  ~/tools/cadquery/bin/cq-python cad/printer/dp_eh500.py
Out:  cad/printer/dp_eh500.step (coloured assembly), cad/printer/dp_eh500.stl

Coordinate system (mm):
  origin = centre of the flange's rear face, i.e. the front surface of the panel it mounts in
  +X = right (seen from the front), +Z = up (paper exits at the top), -Y = towards the viewer.
  Front cover sits at Y < 0, the body sits behind the panel at Y > 0.

Sources for the numbers:
  [M] Measured on the real printer with calipers (2026-11-15). Numbers refer to the measuring sheet (cad/measure/measure_cad.png, kept locally).
  [S] Scaled from a side photo of the real printer, calibrated with [M] 4 and 13 (about +-0.5 mm).
  [P] Scaled from Adafruit's front photo of the same model (about +-1 mm).
  [R] Scaled from a photo of the real printer's back, calibrated with [M] 17 and 18 (about +-1 mm).
  [C] Scaled from photos of the first printed clamp bar on the real printer (2026-11-20), calibrated with
      the bar's known sizes (about +-1 mm).
  [E] Estimate. Not measured and not visible in any photo.
"""
from pathlib import Path

import cadquery as cq

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- dimensions
FLANGE_W = 78.6  # [M1]
FLANGE_H = 39.2  # [M2]
FLANGE_T = 1.6  # [M11]
HOLE_D = 2.6  # [M5]
HOLE_X = 75.0  # [M6] centre to centre
HOLE_Z_UPPER = 14.8  # [M7] below the flange top edge
HOLE_Z_LOWER = 33.0  # [M8] below the flange top edge

COVER_W = 70.7  # [M3]
COVER_H = 44.2  # [M4] cover top to bottom of the hinge
COVER_TOP_DROP = 2.0  # [S] cover top sits this far below the flange top
COVER_D_MAX = 6.7  # [M12] highest point of the curved lid, in front of the flange
COVER_D_TOPBAR = 4.5  # [S] front of the fixed bar above the paper slot
COVER_D_LID_TOP = 5.6  # [S] lid front at its top edge
COVER_D_LID_BOT = 5.3  # [S] lid front at its bottom edge
COVER_D_HINGE = 4.5  # [S] hinge strip below the lid
LID_MAX_DROP = 15.0  # [S] where the lid is highest, below the cover top
LID_BOT_DROP = 39.4  # [S] lid bottom edge, below the cover top
SLOT_DROP = 9.9  # [M9] top edge of the paper slot, below the FLANGE top (matches the side photo)
SLOT_W = 56.7  # [M10]
SLOT_H = 0.8  # [E]
TOOTH_PITCH, TOOTH_H = 1.0, 0.6  # [P] tear teeth

RECESS_W, RECESS_H = 50.7, 20.3  # [P] finger recess on the lid
RECESS_TOP_DROP = 15.9  # [P] below the cover top
RECESS_DEPTH = 0.8  # [E]
SEAM = 0.3  # [E] lid seam groove width and depth
LID_INSET = 1.2  # [P]

UPPER_W = 71.3  # [M17] widest point just behind the flange
UPPER_TOP_DROP = 0.6  # [M14/S] top of the body below the flange top
UPPER_BOT_DROP = 22.3  # [S]
UPPER_D = 30.2  # [S] behind the flange back face (the PCB sits right behind it). NOTE (2026-11-20): the real
#                 back is not a solid face. Beside the PCB, thin black walls frame open windows onto the motor and
#                 rollers, so nothing at the back can take a load. Modelled as a solid box because the walls
#                 aren't measured.
BUCKET_W = 61.4  # [M18] width of the lower paper bucket
BUCKET_D = 23.4  # [S]
BODY_H = 44.4  # [M13] tallest point behind the flange (upper block top to bucket bottom)
BUCKET_R = 10.0  # [S] rounded rear-bottom edge of the bucket
LEDGE_DROP, LEDGE_T, LEDGE_D = 38.7, 1.3, 22.7  # [S] thin side ledge level with the flange bottom

PCB_W = 52.5  # [C] edges at about X -28.5 and +24.0 (was 51.0 [R] from the photo of the back)
PCB_T = 1.8  # [S]
PCB_REAR = 32.0  # [M15] flange back face to the PCB rear face
PCB_TOP_DROP, PCB_BOT_DROP = 0.6, 33.8  # [R/S] covers the back of the upper block and a bit below
PCB_X = -2.2  # [C] PCB centre, left-right (seen from the front)
PCB_PARTS_H = 3.8  # [C] tallest parts on the PCB's rear face (ICs, feed switch, connector) above the PCB rear;
#                    the first clamp bar, 5.4 mm clear of the black back face, touched them
CONN_X = 11.6  # [R] connector centre, left-right (seen from the front)
CONN_Z_DROP = 29.6  # [R] connector centre below the flange top
CONN_W, CONN_H, CONN_D = 15.0, 6.0, 7.0  # [R/E] 5-pin header (GND RX TX DTR VH), mating face to the rear
CABLE_CLEAR = 43.0  # [M16] flange back face to the end of the plugged-in cable

# derived Z levels (flange centred on Z = 0)
FT = FLANGE_H / 2
COVER_TOP = FT - COVER_TOP_DROP
COVER_BOT = COVER_TOP - COVER_H
SLOT_TOP = FT - SLOT_DROP
UPPER_TOP = FT - UPPER_TOP_DROP
UPPER_BOT = FT - UPPER_BOT_DROP
BODY_BOT = UPPER_TOP - BODY_H
FF = -FLANGE_T  # flange front face (Y)


def box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def yz_prism(sketch_fn, width):
    """Extrude a profile drawn in the YZ plane (local x = Y, local y = Z) symmetrically along X."""
    return sketch_fn(cq.Workplane("YZ", origin=(-width / 2, 0, 0))).close().extrude(width)


def xz_prism(sketch_fn, y0=-30, depth=60):
    """Extrude a profile drawn in the XZ plane (local x = X, local y = Z) through Y from y0 to y0+depth."""
    return sketch_fn(cq.Workplane("XZ", origin=(0, y0, 0))).close().extrude(-depth)


def lid_curve(lid_top, lid_bot, n=8):
    """Points on the lid's side profile: parabolas meeting at the highest point (COVER_D_MAX)."""
    z_apex = COVER_TOP - LID_MAX_DROP

    def pt(z_end, d_end, t):
        return (FF - (COVER_D_MAX - (COVER_D_MAX - d_end) * t * t), z_apex + (z_end - z_apex) * t)

    upper = [pt(lid_top, COVER_D_LID_TOP, i / n) for i in range(n - 1, -1, -1)]  # just below lid top .. apex
    lower = [pt(lid_bot, COVER_D_LID_BOT, i / n) for i in range(1, n + 1)]  # just below apex .. lid bottom
    return upper + lower


def build():
    # ---------------------------------------------------------------- flange
    flange = box(-FLANGE_W / 2, FLANGE_W / 2, FF, 0, -FT, FT)
    for sx in (-1, 1):
        for drop in (HOLE_Z_UPPER, HOLE_Z_LOWER):
            flange = flange.cut(cq.Workplane("XZ").center(sx * HOLE_X / 2, FT - drop)
                                .circle(HOLE_D / 2).extrude(10, both=True))

    # ---------------------------------------------------------------- front cover (curved lid profile)
    lid_top = SLOT_TOP - SLOT_H
    lid_bot = COVER_TOP - LID_BOT_DROP

    def profile(w):
        return (w.moveTo(FF, COVER_TOP)
                .lineTo(FF - COVER_D_TOPBAR + 0.8, COVER_TOP)
                .threePointArc((FF - COVER_D_TOPBAR + 0.23, COVER_TOP - 0.23), (FF - COVER_D_TOPBAR, COVER_TOP - 0.8))
                .lineTo(FF - COVER_D_TOPBAR, lid_top + 0.4)
                .lineTo(FF - COVER_D_LID_TOP, lid_top)
                .spline(lid_curve(lid_top, lid_bot), includeCurrent=True)
                .lineTo(FF - COVER_D_HINGE, lid_bot - 0.3)
                .lineTo(FF - COVER_D_HINGE, COVER_BOT + 2.5)
                .threePointArc((FF - COVER_D_HINGE + 0.73, COVER_BOT + 0.73), (FF - COVER_D_HINGE + 2.5, COVER_BOT))
                .lineTo(FF, COVER_BOT))

    cover = yz_prism(profile, COVER_W)
    cover = cover.edges("|Y").fillet(0.8)
    skin = lambda t: cover.cut(cover.translate((0, t, 0)))  # material within t mm of the front surface

    # paper slot with saw-tooth tear edge along its top
    pts = [(-SLOT_W / 2, SLOT_TOP - SLOT_H), (-SLOT_W / 2, SLOT_TOP)]
    x = -SLOT_W / 2
    for _ in range(int(SLOT_W / TOOTH_PITCH)):
        pts += [(x + TOOTH_PITCH / 2, SLOT_TOP - TOOTH_H), (x + TOOTH_PITCH, SLOT_TOP)]
        x += TOOTH_PITCH
    pts.append((SLOT_W / 2, SLOT_TOP - SLOT_H))
    slot = cq.Workplane("XZ", origin=(0, -30, 0)).polyline(pts).close().extrude(-60)
    cover = cover.cut(slot.intersect(skin(3.0)))

    # lid seam: U-shaped groove down the sides and across the bottom of the lid
    lx = COVER_W / 2 - LID_INSET
    seam = (box(-lx, lx, -30, 30, lid_bot, lid_top)
            .cut(box(-lx + SEAM, lx - SEAM, -31, 31, lid_bot + SEAM, lid_top + 1)))
    cover = cover.cut(seam.intersect(skin(SEAM)))

    # finger recess
    rz = COVER_TOP - RECESS_TOP_DROP - RECESS_H / 2
    recess = (cq.Workplane("XZ", origin=(0, -30, 0)).center(0, rz).rect(RECESS_W, RECESS_H)
              .extrude(-60).edges("|Y").fillet(1.5))
    cover = cover.cut(recess.intersect(skin(RECESS_DEPTH)))

    # ---------------------------------------------------------------- body behind the flange
    upper = box(-UPPER_W / 2, UPPER_W / 2, 0, UPPER_D, UPPER_BOT, UPPER_TOP)
    bucket = (box(-BUCKET_W / 2, BUCKET_W / 2, 0, BUCKET_D, BODY_BOT, UPPER_BOT + 0.5)
              .edges("|X and >Y and <Z").fillet(BUCKET_R))
    ledge = box(-UPPER_W / 2, UPPER_W / 2, 0, LEDGE_D, FT - LEDGE_DROP - LEDGE_T, FT - LEDGE_DROP)
    housing = flange.union(cover).union(upper).union(bucket).union(ledge)

    # ---------------------------------------------------------------- electronics
    pcb = box(PCB_X - PCB_W / 2, PCB_X + PCB_W / 2, PCB_REAR - PCB_T, PCB_REAR, FT - PCB_BOT_DROP, FT - PCB_TOP_DROP)
    cz = FT - CONN_Z_DROP
    conn = box(CONN_X - CONN_W / 2, CONN_X + CONN_W / 2, PCB_REAR, PCB_REAR + CONN_D,
               cz - CONN_H / 2, cz + CONN_H / 2)
    # space the plugged-in cable needs (not a physical part: keep it clear in an enclosure)
    keepout = box(CONN_X - 7, CONN_X + 7, PCB_REAR + CONN_D, CABLE_CLEAR, cz - 4, cz + 4)
    # envelope of the components on the PCB's rear face (they are not modelled one by one)
    parts = box(PCB_X - PCB_W / 2 + 1, PCB_X + PCB_W / 2 - 1, PCB_REAR, PCB_REAR + PCB_PARTS_H,
                FT - PCB_BOT_DROP + 1, FT - PCB_TOP_DROP - 0.5)
    return housing, pcb, conn, keepout, parts


if __name__ == "__main__":
    housing, pcb, conn, keepout, parts = build()
    asm = cq.Assembly(name="DP-EH500")
    asm.add(housing, name="housing", color=cq.Color(0.08, 0.08, 0.09))
    asm.add(pcb, name="pcb", color=cq.Color(0.05, 0.45, 0.15))
    asm.add(conn, name="connector", color=cq.Color(0.95, 0.95, 0.92))
    asm.add(parts, name="pcb_parts_envelope", color=cq.Color(0.2, 0.2, 0.22, 0.5))
    asm.add(keepout, name="cable_keepout", color=cq.Color(1.0, 0.3, 0.3, 0.25))
    asm.export(str(OUT / "dp_eh500.step"))

    solid = housing.union(pcb).union(conn)
    cq.exporters.export(solid, str(OUT / "dp_eh500.stl"), tolerance=0.02, angularTolerance=0.1)

    bb = solid.val().BoundingBox()
    print(f"bounding box (no cable): X {bb.xmin:.2f}..{bb.xmax:.2f} ({bb.xlen:.2f})  "
          f"Y {bb.ymin:.2f}..{bb.ymax:.2f} ({bb.ylen:.2f})  Z {bb.zmin:.2f}..{bb.zmax:.2f} ({bb.zlen:.2f})")
    print(f"cover front (max) to cable end: {COVER_D_MAX + FLANGE_T + CABLE_CLEAR:.1f} mm")
