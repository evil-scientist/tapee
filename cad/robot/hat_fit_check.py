#!/usr/bin/env python3
"""Fit check: the tapee HAT (pcb/tapee_hat.kicad_pcb, read only) stacked on the Pi Zero inside the robot body.

Run:  ~/tools/cadquery/bin/cq-python cad/robot/hat_fit_check.py   (from the repository root)

Reads part positions from the HAT's courtyards, gives each part a typical height (table H below), adds the
plugged-in cables and the room they need to bend, and reports clashes with every robot part plus the gap to
the body. Writes no files. Re-run it after moving parts on the PCB (e.g. the USB-C connector J4).
"""
import math, re, sys
from pathlib import Path
import cadquery as cq
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cad/robot")); sys.argv = ["x"]
import tapee_robot as t

STACK = 11.0  # Pi top to HAT underside with a standard 8.5 mm 2x20 socket on the Pi's male header
HAT_Z0 = t.PI_Z + 1.6 + STACK
HAT_T = 1.6
ZT = HAT_Z0 + HAT_T

def to_robot(xk, yk):  # KiCad (mm, Y down) -> robot frame; Pi is turned 180 deg, ports to the back
    return 32.5 - (xk - 100) + t.PI_C[0], (yk - 100) + 15 + t.PI_C[1]

def rbox(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))

s = (ROOT / "pcb/tapee_hat.kicad_pcb").read_text()
fps = {}
for m in re.finditer(r'\n\t\(footprint "([^"]+)"', s):
    nxt = s.find('\n\t(footprint "', m.start() + 5); blk = s[m.start(): nxt if nxt > 0 else len(s)]
    ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
    ax, ay, ar = re.search(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk).groups()
    ax, ay, ar = float(ax), float(ay), math.radians(float(ar or 0))
    pts = [(float(a), float(b)) for g in re.finditer(r'\(fp_(?:line|rect|poly)\s.*?\(layer "[FB]\.CrtYd"\)', blk, re.S)
           for a, b in re.findall(r'\((?:start|end|xy) ([-\d.]+) ([-\d.]+)\)', g.group(0))]
    if not pts: continue
    rob = [to_robot(ax + x * math.cos(ar) + y * math.sin(ar), ay - x * math.sin(ar) + y * math.cos(ar)) for x, y in pts]
    xs, ys = [p[0] for p in rob], [p[1] for p in rob]
    fps[ref] = (min(xs), max(xs), min(ys), max(ys))

# component heights above the HAT top [datasheet values / typical]
H = {"C1": 10.5, "C3": 8.0, "J2": 7.0, "J3": 8.5, "J5": 10.0, "J4": 3.3, "D1": 2.4, "D2": 2.4, "JP1": 0.7,
     "U1": 1.1, "C2": 1.3, "C4": 1.3, "R1": 0.6, "R2": 0.6, "R3": 0.6, "R4": 0.6}
items = {}
board = rbox(t.PI_C[0] - 32.5, t.PI_C[0] + 32.5, t.PI_C[1] - 15, t.PI_C[1] + 15, HAT_Z0, ZT).edges("|Z").fillet(3)
items["HAT board"] = board
for ref, h in H.items():
    x0, x1, y0, y1 = fps[ref]
    items[ref] = rbox(x0, x1, y0, y1, ZT, ZT + h)
x0, x1, y0, y1 = fps["J1"]
items["J1 socket (under)"] = rbox(x0, x1, y0, y1, HAT_Z0 - 8.5, HAT_Z0)
# mated plugs and the room their cables need
x0, x1, y0, y1 = fps["J2"]; items["J2 plug + cable bend"] = rbox(x0 + 0.5, x1 - 0.5, y0 + 0.5, y1 - 0.5, ZT, ZT + 21)
x0, x1, y0, y1 = fps["J3"]; items["J3 Dupont + wire bend"] = rbox(x0, x1, y0, y1, ZT, ZT + 24.5)
x0, x1, y0, y1 = fps["J5"]; items["J5 wires (15 mm straight)"] = rbox(x0, x1, y1, y1 + 15, ZT + 1, ZT + 8)
x0, x1, y0, y1 = fps["J4"]; yc = (y0 + y1) / 2
mouth = x1  # USB-C opening faces +X (robot's left side wall)
items["J4 USB-C straight plug (22 mm)"] = rbox(mouth - 1, mouth + 22, yc - 6.2, yc + 6.2, ZT - 2.2, ZT + 5.0)
items["J4 USB-C right-angle plug (14 mm)"] = rbox(mouth - 1, mouth + 14, yc - 6.2, yc + 6.2, ZT - 2.2, ZT + 5.0)

parts = {k: v[0] for k, v in t.build().items()}
parts.update({k: v[0] for k, v in t.bought_parts().items()})
skip = {("J1 socket (under)", "pi_parts")}  # the socket sits on the Pi's header: that is the mating, not a clash
print(f"HAT underside Z {HAT_Z0:.1f}, top Z {ZT:.1f}; seam Z {t.ZM:.1f}")
for name, sh in items.items():
    hits, near = [], []
    for pn, ps in parts.items():
        if (name, pn) in skip: continue
        try:
            vol = sh.intersect(ps).val().Volume()
        except Exception:
            vol = 0.0
        if vol > 0.05:
            hits.append(f"{pn} ({vol:.1f} mm3)")
    bb = sh.val().BoundingBox()
    wall = min(sh.val().distance(parts["lower_half"].val()), sh.val().distance(parts["upper_half"].val()))
    print(f"{name:34s} X {bb.xmin:6.1f}..{bb.xmax:6.1f} Y {bb.ymin:6.1f}..{bb.ymax:6.1f} Z {bb.zmin:5.1f}..{bb.zmax:5.1f}"
          f"  gap to body {wall:5.1f}  {'CLASH: ' + ', '.join(hits) if hits else 'ok'}")
x0, x1, y0, y1 = fps["J4"]
print("J4 USB-C mouth at X %.1f, Y %.1f, Z %.1f, facing +X (the robot's left side wall, which has no hole)"
      % (x1, (y0 + y1) / 2, ZT + 1.6))
print("rear opening (centre x, width, centre z, height):", t.REAR_OPEN)
