#!/usr/bin/env python3
"""Compose the tapee HAT silkscreen artwork and write it as hole-free SVG polygons.

Run with the OpenCV Python:  ~/tools/opencv/bin/python compose.py PADS.d356
Inputs:  build/glyphs.json (from glyphs.py), logo-small.png, the board's IPC-D-356 pad list.
Outputs: build/top.svg, build/bottom.svg (+ .json with the import position), build/preview_*.png

Everything is drawn on a 100 px/mm canvas in board coordinates (board = x 100..165, y 70..100),
pads/vias/holes are cut out with clearance, then traced back to polygons. Konnect's SVG import
fills every sub-path, so each hole is cut into its outline with a zero-width keyhole bridge.
"""
import json, math, re, sys
import cv2
import numpy as np

S = 100                      # px per mm
X0, Y0, BW, BH = 100.0, 70.0, 65.0, 30.0
STROKE = 0.2                 # line art width, mm
SILK_PAD_CLR = 0.2           # silk to pad clearance, mm
EDGE_CLR = 0.3

G = json.load(open("build/glyphs.json"))

def px(v): return int(round(v * S))
def P(x, y): return (px(x - X0), px(y - Y0))
def canvas(): return np.zeros((px(BH), px(BW)), np.uint8)

# ------------------------------------------------------------------ text
def _xf(pts, cx, cy, rot, bb):
    (x0, y0, x1, y1) = bb
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    a = math.radians(rot); c, s = math.cos(a), math.sin(a)
    out = []
    for x, y in pts:
        u, v = x - mx, y - my
        out.append((cx + u * c + v * s, cy - u * s + v * c))   # rot>0 = counter-clockwise on screen
    return out

def glyph_bb(gid, scale=1.0):
    pts = [p for c in G[gid]["contours"] for p in c]
    xs = [p[0] * scale for p in pts]; ys = [p[1] * scale for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

def fill_nested(img, contours, fg, bg):
    """contours in px; draw with even-odd semantics using nesting depth."""
    arrs = [np.array(c, np.int32) for c in contours if len(c) > 2]
    depth = []
    for i, a in enumerate(arrs):
        p = (float(a[0][0]), float(a[0][1]))
        depth.append(sum(1 for j, b in enumerate(arrs) if j != i and cv2.pointPolygonTest(b, p, False) > 0))
    for d in sorted(set(depth)):
        for a, dd in zip(arrs, depth):
            if dd == d:
                cv2.fillPoly(img, [a], fg if d % 2 == 0 else bg)

def text(img, gid, cx, cy, rot=0, max_w=None, knockout=False, pad=0.3):
    sc = 1.0
    bb = glyph_bb(gid)
    if max_w and bb[2] - bb[0] > max_w:
        sc = max_w / (bb[2] - bb[0])
    bb = glyph_bb(gid, sc)
    cons = [[P(*q) for q in _xf([(x * sc, y * sc) for x, y in c], cx, cy, rot, bb)] for c in G[gid]["contours"]]
    if knockout:
        x0, y0, x1, y1 = bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad
        r = min(0.35, (y1 - y0) / 2)
        box = []
        for (ccx, ccy, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
            for k in range(7):
                a = math.radians(a0 + k * 15)
                box.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))
        cv2.fillPoly(img, [np.array([P(*q) for q in _xf(box, cx, cy, rot, bb)], np.int32)], 255)
        fill_nested(img, cons, 0, 255)
    else:
        fill_nested(img, cons, 255, 0)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    return (w, h) if rot % 180 == 0 else (h, w)

# ------------------------------------------------------------------ line art helpers
def line(img, pts, w=STROKE):
    cv2.polylines(img, [np.array([P(*p) for p in pts], np.int32)], False, 255, max(1, px(w)), cv2.LINE_8)
def poly(img, pts, w=STROKE, fill=False):
    a = np.array([P(*p) for p in pts], np.int32)
    if fill: cv2.fillPoly(img, [a], 255)
    else: cv2.polylines(img, [a], True, 255, max(1, px(w)), cv2.LINE_8)
def circle(img, c, r, w=STROKE, fill=False, color=255):
    cv2.circle(img, P(*c), px(r), color, -1 if fill else max(1, px(w)), cv2.LINE_8)
def arc(img, c, rx, ry, a0, a1, w=STROKE):
    pts = [(c[0] + rx * math.cos(math.radians(a)), c[1] + ry * math.sin(math.radians(a)))
           for a in np.linspace(a0, a1, max(8, int(abs(a1 - a0) / 3)))]
    line(img, pts, w)
def rrect(img, x0, y0, x1, y1, r, w=STROKE, fill=False):
    pts = []
    for (ccx, ccy, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        pts += [(ccx + r * math.cos(math.radians(a0 + k * 15)), ccy + r * math.sin(math.radians(a0 + k * 15))) for k in range(7)]
    poly(img, pts, w, fill)
def gear(img, c, r, teeth=8, w=STROKE):
    pts = []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        rr = r if (i % 4) in (0, 1) else r * 0.72
        pts.append((c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)))
    poly(img, pts, w)
    circle(img, c, r * 0.28, w)

def logo(img, x, y, h):
    src = cv2.imread("logo-small.png", cv2.IMREAD_UNCHANGED)
    alpha = src[:, :, 3] if src.shape[2] == 4 else 255 - cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    dark = cv2.cvtColor(src[:, :, :3], cv2.COLOR_BGR2GRAY) < 128
    m = ((alpha > 128) & dark).astype(np.uint8) * 255
    H = px(h); W = int(round(m.shape[1] * H / m.shape[0]))
    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_AREA)
    m = (m > 127).astype(np.uint8) * 255
    ox, oy = P(x, y)
    img[oy:oy + H, ox:ox + W] |= m
    return W / S

# ------------------------------------------------------------------ keep-outs
def keepouts(d356, side):
    ko = canvas()
    for l in open(d356):
        if not l.startswith(("317", "327")): continue
        if l[20:26].strip() == "VIA": continue   # vias are tented (board setup), silk may cover them
        m = re.search(r'A(\d\d)X([+-]\d+)Y([+-]\d+)X(\d+)Y(\d+)R(\d+)', l)
        acc, x, y, w, h, r = m.groups()
        acc = int(acc)
        if l.startswith("327") and acc != (1 if side == "top" else 2): continue
        x, y = int(x) * 2.54e-3, -int(y) * 2.54e-3
        w, h = int(w) * 2.54e-3, int(h) * 2.54e-3
        if int(r) in (90, 270): w, h = h, w
        c = SILK_PAD_CLR
        if h == 0:  # round pad
            circle(ko, (x, y), w / 2 + c, fill=True)
        else:
            cv2.rectangle(ko, P(x - w / 2 - c, y - h / 2 - c), P(x + w / 2 + c, y + h / 2 + c), 255, -1)
    for hx, hy in ((103.5, 73.5), (161.5, 73.5), (103.5, 96.5), (161.5, 96.5)):
        circle(ko, (hx, hy), 1.35 + 0.45, fill=True)
    # board edge band and rounded corners
    edge = np.full_like(ko, 255)
    rrect(edge, X0 + EDGE_CLR, Y0 + EDGE_CLR, X0 + BW - EDGE_CLR, Y0 + BH - EDGE_CLR, 3 - EDGE_CLR, fill=True)
    edge = cv2.bitwise_not(edge) if False else edge
    inside = canvas(); rrect(inside, X0 + EDGE_CLR, Y0 + EDGE_CLR, X0 + BW - EDGE_CLR, Y0 + BH - EDGE_CLR, 3 - EDGE_CLR, fill=True)
    return ko | cv2.bitwise_not(inside)

# ------------------------------------------------------------------ polygons + keyholes
def area(p):
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))

def keyhole(outer, holes):
    poly_ = list(outer)
    if area(poly_) < 0: poly_.reverse()
    hs = []
    for h in holes:
        h = list(h)
        if area(h) > 0: h.reverse()
        hs.append(h)
    hs.sort(key=lambda h: -max(p[0] for p in h))
    for h in hs:
        mi = max(range(len(h)), key=lambda i: h[i][0]); M = h[mi]
        best = None
        n = len(poly_)
        for i in range(n):
            a, b = poly_[i], poly_[(i + 1) % n]
            if (a[1] > M[1]) != (b[1] > M[1]):
                t = (M[1] - a[1]) / (b[1] - a[1])
                xi = a[0] + t * (b[0] - a[0])
                if xi >= M[0] and (best is None or xi < best[0]):
                    best = (xi, i)
        if best is None:
            continue  # should not happen for a hole inside its outer
        xi, i = best
        I = (xi, M[1])
        hr = h[mi:] + h[:mi] + [M]
        poly_ = poly_[:i + 1] + [I] + hr + [I] + poly_[i + 1:]
    return poly_

def _ray_hit_up(poly_, M):
    """Nearest edge of poly_ hit by the ray from M towards -y (up): (y, edge index) or None."""
    best = None
    n = len(poly_)
    for i in range(n):
        a, b = poly_[i], poly_[(i + 1) % n]
        if (a[0] > M[0]) != (b[0] > M[0]):
            yi = a[1] + (M[0] - a[0]) / (b[0] - a[0]) * (b[1] - a[1])
            if yi < M[1] and (best is None or yi > best[0]):
                best = (yi, i)
    return best

def merge_all(polys):
    """Join separate (hole-free) polygons into ONE weakly simple polygon with zero-width bridges.
    Konnect/KiCad keep only the first outline of a multi-outline shape, so each side's art must
    be a single outline. Holes were keyholed with horizontal bridges; polygons are merged here with
    vertical bridges (top-down, ray going up), so the two kinds can never be collinear or touch.
    Rays that miss everything end on a zero-width horizontal spine just above the artwork."""
    polys = [list(p) if area(p) > 0 else list(reversed(p)) for p in polys]
    polys.sort(key=lambda p: min(q[1] for q in p))
    if len(polys) == 1:
        return polys[0]
    xs_all = [q[0] for p in polys for q in p]
    ys = min(q[1] for q in polys[0]) - 0.03
    first = polys[0]
    mi = min(range(len(first)), key=lambda i: (first[i][1], first[i][0])); M = first[mi]
    S0 = (M[0], ys)
    merged = first[mi:] + first[:mi] + [M, S0, (max(xs_all), ys), S0, (min(xs_all), ys), S0]
    for q in polys[1:]:
        mi = min(range(len(q)), key=lambda i: (q[i][1], q[i][0])); M = q[mi]
        yi, i = _ray_hit_up(merged, M)
        I = (M[0], yi)
        merged = merged[:i + 1] + [I] + q[mi:] + q[:mi] + [M, I] + merged[i + 1:]
    return merged

def trace(img, min_area=0.006):
    cons, hier = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None: return []
    hier = hier[0]
    def depth(i):
        d = 0
        while hier[i][3] >= 0: i = hier[i][3]; d += 1
        return d
    out = []
    to_mm = lambda c: [(X0 + p[0][0] / S, Y0 + p[0][1] / S) for p in cv2.approxPolyDP(c, 0.7, True)]
    for i, c in enumerate(cons):
        if depth(i) % 2: continue
        if cv2.contourArea(c) / S / S < min_area: continue
        holes = []
        k = hier[i][2]
        while k >= 0:
            if cv2.contourArea(cons[k]) / S / S >= 0.004:
                holes.append(to_mm(cons[k]))
            k = hier[k][0]
        o = to_mm(c)
        if len(o) >= 3:
            out.append(keyhole(o, [h for h in holes if len(h) >= 3]))
    return out

PX_PER_MM_BUG = 96 / 25.4   # Konnect's import_svg_logo shrinks by 25.4/96; pre-compensate the width

def write_svg(polys, name):
    polys = [merge_all(polys)]
    xs = [p[0] for q in polys for p in q]; ys = [p[1] for q in polys for p in q]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    w, h = x1 - x0, y1 - y0
    body = "\n".join('<path fill="#000" d="M' + " L".join(f"{x - x0:.4f},{y - y0:.4f}" for x, y in q) + ' Z"/>' for q in polys)
    open(f"build/{name}.svg", "w").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.4f}mm" height="{h:.4f}mm" viewBox="0 0 {w:.4f} {h:.4f}">\n{body}\n</svg>\n')
    json.dump({"x": round(x0, 4), "y": round(y0, 4), "width_mm": round(w, 4), "height_mm": round(h, 4),
               "import_width_mm": round(w * PX_PER_MM_BUG, 6), "points": len(polys[0]),
               "polygons": len(polys)}, open(f"build/{name}.json", "w"))
    print(f"{name}: {len(polys)} polygons, x={x0:.3f} y={y0:.3f} w={w:.3f} h={h:.3f}")

# ------------------------------------------------------------------ top artwork
def tapee_cutaway(img, ox, oy, k=1.0):
    """Front cutaway of the tapee robot (concept A5) in a 16.8 x 15.3 mm box at (ox, oy)."""
    T = lambda x, y: (ox + x * k, oy + y * k)
    cx, cy = 8.4, 9.6
    # body: dome head (upper half ellipse) + shallower lower half, feet, ears
    arc(img, T(cx, cy), 7.6 * k, 7.8 * k, 180, 360)
    arc(img, T(cx, cy), 7.6 * k, 4.6 * k, 0, 180)
    for fx in (3.4, 11.4):
        rrect(img, *T(fx, 14.15), *T(fx + 1.8, 14.95), 0.25 * k, fill=True)
    for ex, sgn in ((cx - 7.35, -1), (cx + 7.35, 1)):
        rrect(img, *T(min(ex, ex + sgn * 0.9), 4.2), *T(max(ex, ex + sgn * 0.9), 6.4), 0.2 * k)
    # seam / mouth line (the printer's paper slot)
    line(img, [T(cx - 7.6, cy), T(cx + 7.6, cy)])
    # strap with goggles
    for yy in (4.45, 5.95):
        hw = 7.6 * math.sqrt(max(0.0, 1 - ((cy - yy) / 7.8) ** 2))
        line(img, [T(cx - hw + 0.15, yy), T(cx - 3.05, yy)])
        line(img, [T(cx - 1.35, yy), T(cx + 1.35, yy)])
        line(img, [T(cx + 3.05, yy), T(cx + hw - 0.15, yy)])
    for gx in (cx - 3.0, cx + 3.0):
        circle(img, T(gx, 5.2), 1.75 * k, color=0, fill=True)
        circle(img, T(gx, 5.2), 1.65 * k, w=0.3)
        circle(img, T(gx, 5.2), 1.05 * k)
        circle(img, T(gx + 0.25, 5.35), 0.42 * k, fill=True)
    # brain gear between the eyes
    gear(img, T(cx, 2.95), 0.8 * k, teeth=8)
    # button cap on top, plunger, switch
    arc(img, T(cx, 1.65), 1.25 * k, 0.95 * k, 180, 360)
    line(img, [T(cx - 1.25, 1.65), T(cx + 1.25, 1.65)])
    # ticket coming out of the mouth
    tk = [T(cx - 1.9, cy - 0.05), T(cx - 1.9, 7.35)]
    zz = [T(cx - 1.9 + i * 0.475, 7.35 - (0.3 if i % 2 else 0)) for i in range(9)]
    line(img, tk + zz + [T(cx + 1.9, cy - 0.05)])
    for ty, tw in ((8.15, 2.6), (8.85, 1.8)):
        line(img, [T(cx - tw / 2, ty), T(cx + tw / 2, ty)], 0.16)
    # printer (cutaway): case, paper roll, print head
    rrect(img, *T(2.6, cy + 0.6), *T(9.3, 13.4), 0.35 * k)
    circle(img, T(5.0, 11.95), 1.15 * k)
    circle(img, T(5.0, 11.95), 0.35 * k, fill=True)
    line(img, [T(6.15, 11.95), T(7.4, cy + 0.6)])            # paper path to the head
    rrect(img, *T(7.0, cy + 0.85), *T(8.9, cy + 1.45), 0.1 * k, fill=True)
    # Pi Zero with its header
    rrect(img, *T(10.0, 11.3), *T(14.1, 13.4), 0.3 * k)
    for i in range(6):
        circle(img, T(10.55 + i * 0.6, 11.85), 0.16 * k, fill=True)
    # wires: Pi -> printer, Pi -> button switch
    line(img, [T(10.0, 12.6), T(9.3, 12.6)], 0.16)
    line(img, [T(10.0, 13.0), T(9.3, 13.0)], 0.16)
    line(img, [T(13.5, 11.3), T(14.3, 9.0), T(14.1, 6.9), T(13.7, 4.6), T(12.2, 3.05), T(10.2, 2.2)], 0.16)

def top_elements():
    """Each element becomes its own single-outline import, so zero-width bridges stay inside it."""
    E = {}
    E["lbl_printer"] = lambda i: text(i, "printer", 139.15, 80.3, knockout=True, max_w=5.6)
    for gid, x in (("p_gnd", 145.0), ("p_rx", 147.5), ("p_tx", 150.0), ("p_dtr", 152.5), ("p_vh", 155.0)):
        E["lbl_" + gid] = (lambda g, xx: (lambda i: text(i, g, xx, 84.95, max_w=2.2)))(gid, x)
    E["lbl_button"] = lambda i: text(i, "button", 163.45, 87.25, rot=90, knockout=True, max_w=7.5)
    E["lbl_usb"] = lambda i: text(i, "usb", 100.95, 91.45, rot=90, knockout=True, max_w=6.2)
    E["lbl_jumper"] = lambda i: text(i, "jumper", 122.2, 85.35, knockout=True, max_w=7.0)
    E["lbl_plus"] = lambda i: text(i, "plus", 109.6, 89.6)
    E["lbl_minus"] = lambda i: text(i, "minus", 114.68, 89.65)
    E["lbl_prn5v"] = lambda i: text(i, "prn5v", 122.25, 98.15, knockout=True, max_w=7.6)
    E["art_robot"] = lambda i: tapee_cutaway(i, 126.95, 84.2, k=1.0)
    E["art_logo"] = lambda i: logo(i, 145.3, 94.85, 4.55)
    lw = 4.55 * 338 / 325
    E["art_tapee"] = lambda i: text(i, "tapee", 145.3 + lw + 0.5 + 3.75, 96.45, max_w=7.5)
    E["art_sub"] = lambda i: text(i, "sub", 145.3 + lw + 0.5 + 3.75, 98.75, max_w=7.5)
    return E

def bottom_elements():
    """Drawn as seen from below; each canvas is mirrored into board coordinates."""
    E = {}
    E["b_logo"] = lambda i: logo(i, 121.0, 78.3, 17.0)
    E["b_tapee"] = lambda i: text(i, "b_tapee", 148.0, 81.6, max_w=13.5)
    E["b_sub"] = lambda i: text(i, "b_sub", 148.0, 86.3, max_w=14.0)
    E["b_sub2"] = lambda i: text(i, "b_sub2", 148.0, 88.0, max_w=14.0)
    E["b_rev"] = lambda i: text(i, "b_rev", 148.0, 90.0, max_w=12.0)
    for n, (gx, r, t, gy) in enumerate(((106.0, 1.5, 10, 92.5), (109.3, 1.0, 8, 93.1), (113.0, 1.6, 10, 92.5))):
        E[f"b_gear{n}"] = (lambda a, b, c, d: (lambda i: gear(i, (a, d), b, teeth=c)))(gx, r, t, gy)
    def circuit(i):
        line(i, [(116.0, 97.3), (121.0, 97.3), (122.2, 96.1), (139.5, 96.1), (140.7, 97.3), (146.0, 97.3)])
        for x in (116.0, 146.0):
            circle(i, (x, 97.3), 0.35, fill=True)
    E["b_circuit"] = circuit
    return E

if __name__ == "__main__":
    import glob, os
    d356 = sys.argv[1]
    for f in glob.glob("build/top*.svg") + glob.glob("build/bottom*.svg") + glob.glob("build/el_*"):
        os.remove(f)
    manifest = []
    for side, elements in (("top", top_elements()), ("bottom", bottom_elements())):
        ko = keepouts(d356, side)
        full = canvas()
        for name, draw in elements.items():
            img = canvas(); draw(img)
            if side == "bottom": img = cv2.flip(img, 1)
            art = cv2.bitwise_and(img, cv2.bitwise_not(ko))
            art = cv2.morphologyEx(art, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
            full |= art
            polys = trace(art)
            if not polys: continue
            write_svg(polys, f"el_{name}")
            m = json.load(open(f"build/el_{name}.json"))
            m.update(name=name, layer="F.SilkS" if side == "top" else "B.SilkS", svg=os.path.abspath(f"build/el_{name}.svg"))
            manifest.append(m)
        prev = cv2.cvtColor(np.full_like(full, 20), cv2.COLOR_GRAY2BGR)
        prev[ko > 0] = (40, 90, 160); prev[full > 0] = (40, 220, 245)
        if side == "bottom": prev = cv2.flip(prev, 1)
        cv2.imwrite(f"build/preview_{side}.png", cv2.resize(prev, (prev.shape[1] // 3, prev.shape[0] // 3), interpolation=cv2.INTER_AREA))
    json.dump(manifest, open("build/manifest.json", "w"), indent=1)
    print(len(manifest), "elements")
