#!/bin/sh
# Render pcb/tapee_hat_render.png: a flat preview of both sides of the HAT, top above bottom
# (bottom as seen from below), in the real colours: black mask, ENIG gold pads, yellow silkscreen.
# Run from anywhere after changing the board. Intermediate layer images go to pcb/art/build/.
set -e
here=$(cd "$(dirname "$0")" && pwd)
B="$here/../tapee_hat.kicad_pcb"
K=~/tools/konnect/bin/kicad-cli
I=~/tools/inkscape/bin/inkscape
mkdir -p "$here/build" && cd "$here/build"

svg2png() { "$I" "$1.svg" --export-type=png --export-background=white --export-width=2600 -o "$1.png" >/dev/null 2>&1; }
for side in F B; do
  m=""; [ $side = B ] && m="--mirror"
  for L in SilkS Mask Cu; do
    $K pcb export svg --layers $side.$L,Edge.Cuts --mode-single --fit-page-to-board --exclude-drawing-sheet \
      --black-and-white $m -o r_${side}_$L.svg "$B" >/dev/null
    svg2png r_${side}_$L
  done
done
$K pcb export svg --layers Edge.Cuts --mode-single --fit-page-to-board --exclude-drawing-sheet --black-and-white \
  -o r_edge.svg "$B" >/dev/null
$K pcb export svg --layers Edge.Cuts --mode-single --fit-page-to-board --exclude-drawing-sheet --black-and-white \
  --mirror -o r_edgeB.svg "$B" >/dev/null
svg2png r_edge; svg2png r_edgeB

~/tools/opencv/bin/python - "$here/../tapee_hat_render.png" <<'EOF'
import sys, cv2, numpy as np
def ld(n): return cv2.imread(n, cv2.IMREAD_GRAYSCALE) < 128
outs = []
for side, en in (('F', 'r_edge.png'), ('B', 'r_edgeB.png')):
    edge = ld(en); h, w = edge.shape
    ff = (~edge).astype(np.uint8) * 255  # board interior: flood fill from the centre inside the outline
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (w // 2, h // 2), 128)
    inside = ff == 128
    silk, msk, cu = (ld(f'r_{side}_{L}.png') & ~edge for L in ('SilkS', 'Mask', 'Cu'))
    img = np.full((h, w, 3), 255, np.uint8)
    board = inside | msk
    img[board] = (18, 18, 18); img[board & cu] = (38, 38, 38)      # black mask, copper under mask
    img[msk] = (60, 175, 215); img[silk & ~msk] = (20, 215, 250)   # ENIG gold, yellow silkscreen
    outs.append(img)
out = np.vstack([outs[0], np.full((30, outs[0].shape[1], 3), 255, np.uint8), outs[1]])
cv2.imwrite(sys.argv[1], cv2.resize(out, (1800, int(out.shape[0] * 1800 / out.shape[1])), interpolation=cv2.INTER_AREA))
print("wrote", sys.argv[1])
EOF
