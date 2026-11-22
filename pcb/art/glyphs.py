#!/usr/bin/env python3
"""Dump URW Gothic glyph outlines for the silkscreen strings as flattened polygons.

Run with the CadQuery Python (it has fontTools):
    ~/tools/cadquery/bin/cq-python glyphs.py strings.json build/glyphs.json
Each string becomes a list of closed contours in mm, y pointing down,
with (0, 0) at the top-left of the cap height box and the given cap height.
"""
import json, sys
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen

FONTS = {
    "demi": "/usr/share/fonts/opentype/urw-base35/URWGothic-Demi.otf",
    "book": "/usr/share/fonts/opentype/urw-base35/URWGothic-Book.otf",
}

class FlatPen(BasePen):
    def __init__(self, gs, steps=8):
        super().__init__(gs); self.c = []; self.cur = None; self.steps = steps
    def _moveTo(self, p): self.cur = [p]; self.c.append(self.cur)
    def _lineTo(self, p): self.cur.append(p)
    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps; u = 1 - t
            self.cur.append((u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                             u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]))
    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps; u = 1 - t
            self.cur.append((u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0], u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1]))
    def _closePath(self): self.cur = None
    _endPath = _closePath

def outline(text, cap, weight="demi", tracking=0.0):
    f = TTFont(FONTS[weight]); gs = f.getGlyphSet(); cmap = f.getBestCmap()
    capH = f["OS/2"].sCapHeight or 740
    s = cap / capH
    x = 0.0; contours = []
    for ch in text:
        g = cmap.get(ord(ch))
        if g is None:
            raise SystemExit(f"glyph for {ch!r} missing in {weight}")
        pen = FlatPen(gs); gs[g].draw(pen)
        for c in pen.c:
            contours.append([[round(x + px * s, 4), round(cap - py * s, 4)] for px, py in c])
        x += gs[g].width * s + tracking
    return {"contours": contours, "advance": x, "cap": cap}

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    out = {k: outline(v["text"], v["cap"], v.get("weight", "demi"), v.get("tracking", 0.0)) for k, v in spec.items()}
    json.dump(out, open(sys.argv[2], "w"))
    print(f"{len(out)} strings -> {sys.argv[2]}")
