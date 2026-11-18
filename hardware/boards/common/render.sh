#!/bin/bash
# Board renders for the README and guides, in the board's own solder mask colour (blue SMT, green through-hole).
#   bash render.sh <board.kicad_pcb> <out-name-without-.png> [width height zoom] [top|bottom|both]
set -e
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
PCB=$1; OUT=$2; W=${3:-2400}; H=${4:-1900}; Z=${5:-1.0}; SIDES=${6:-top}
[ "$SIDES" = both ] && SIDES="top bottom"
for s in $SIDES; do
  f=$OUT.png; [ "$6" = both ] && f=$OUT-$s.png
  $K pcb render --side $s --quality high --use-board-stackup-colors -w $W -h $H --zoom $Z -o "$f" "$PCB" 2>&1 | grep -i -E "error|created" || true
done
