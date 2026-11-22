# Silkscreen artwork

Generates the URW Gothic labels, the tapee cutaway drawing and the logo for both silkscreens.

```sh
cd pcb/art
~/tools/cadquery/bin/cq-python glyphs.py strings.json build/glyphs.json          # text outlines
~/tools/konnect/bin/kicad-cli pcb export ipcd356 -o build/pads.d356 ../tapee_hat.kicad_pcb
~/tools/opencv/bin/python compose.py build/pads.d356                             # writes build/el_*.svg + manifest.json
```

Each entry in `build/manifest.json` is imported with Konnect `import_svg_logo` at its `x`, `y`,
`layer`, with `width_mm = import_width_mm`. Two Konnect 0.13 quirks are worked around:

- the import shrinks drawings by 25.4/96, so `import_width_mm` is the real width × 96/25.4;
- only the first outline of an imported shape survives a save, so every element is written as one
  outline: holes are cut in with zero-width keyhole bridges (horizontal) and separate pieces are
  joined with zero-width bridges (vertical). Stroke width is 0, so bridges don't print.

Pads (from the IPC-D-356 file) and mounting holes are cut out with 0.2 mm clearance. Vias are tented,
so the art may cross them. Bottom art is drawn as seen from below and mirrored before import.
