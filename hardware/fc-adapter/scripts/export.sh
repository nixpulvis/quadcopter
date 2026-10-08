#!/bin/sh
# Export renders (docs/) and fab outputs (fab/, not committed) with kicad-cli.
set -e
cd "$(dirname "$0")/.."
PCB=fc-adapter.kicad_pcb
mkdir -p docs fab/gerbers
kicad-cli pcb export svg --page-size-mode 2 --exclude-drawing-sheet \
  -l F.Cu,F.Mask,F.SilkS,Edge.Cuts -o docs/board-top.svg $PCB
# KiCad 7 draws B.Cu over B.SilkS in a combined SVG, so plot the bottom in two
# passes and stack them for the PNG.
kicad-cli pcb export svg --page-size-mode 2 --exclude-drawing-sheet --mirror \
  -l B.Cu,Edge.Cuts -o docs/board-bottom.svg $PCB
kicad-cli pcb export svg --page-size-mode 2 --exclude-drawing-sheet --mirror \
  -l B.Mask,B.SilkS,Edge.Cuts -o fab/bottom-silk.svg $PCB
kicad-cli sch export svg --exclude-drawing-sheet -o docs fc-adapter.kicad_sch
mv docs/fc-adapter.svg docs/schematic.svg
kicad-cli pcb export gerbers -l F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,Edge.Cuts \
  --subtract-soldermask -o fab/gerbers/ $PCB
kicad-cli pcb export drill --format excellon --excellon-separate-th -o fab/gerbers/ $PCB
(cd fab && rm -f fc-adapter-gerbers.zip && zip -qj fc-adapter-gerbers.zip gerbers/*)
python3.12 scripts/jlcpcb.py   # fab/jlcpcb-bom.csv + fab/jlcpcb-cpl.csv for assembly
if command -v rsvg-convert >/dev/null; then
  for f in board-top schematic; do
    rsvg-convert -w 1600 -b white docs/$f.svg -o docs/$f.png
  done
  rsvg-convert -w 1600 -b white docs/board-bottom.svg -o docs/board-bottom.png
  rsvg-convert -w 1600 fab/bottom-silk.svg -o fab/bottom-silk.png
  python3 -c "from PIL import Image; a=Image.open('docs/board-bottom.png').convert('RGBA'); \
b=Image.open('fab/bottom-silk.png').convert('RGBA'); a.alpha_composite(b); a.convert('RGB').save('docs/board-bottom.png')"
fi
