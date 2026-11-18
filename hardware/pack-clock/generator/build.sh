#!/bin/bash
# VIC clock interposer full rebuild: schematic -> board -> (route) -> checks. ROUTE=1 bash build.sh to autoroute.
set -e
cd "$(dirname "$0")"
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
F='fontconfig|stdpbase|assert'

python3 gen_sch.py
mkdir -p out && cp pack-clock.kicad_sch out/
$K sch export netlist --format kicadsexpr -o out/netlist.net out/pack-clock.kicad_sch 2>&1 | grep -v -i -E "$F" || true
$KPY gen_pcb.py out/pack-clock.kicad_pcb 2>&1 | grep -v -i -E "$F" || true
$KPY ../../common/silk_keepout.py out/pack-clock.kicad_pcb --no-refs 2>&1 | grep -E "keep-out" || true
if [ "${ROUTE:-0}" = 1 ]; then
  ROUTE_PARALLEL=${ROUTE_PARALLEL:-4} ROUTE_ATTEMPTS=${ROUTE_ATTEMPTS:-8} $KPY route.py out/pack-clock.kicad_pcb 2>&1 | grep --line-buffered -E "rout|optimi|finishing|exit" || true
  $KPY tidy.py out/pack-clock.kicad_pcb 2>&1 | grep -E "tidy" || true
  $KPY stitch.py out/pack-clock.kicad_pcb 2>&1 | grep -v -i -E "$F" || true
  $KPY relabel.py out/pack-clock.kicad_pcb 2>&1 | grep -E "part numbers" || true
  $KPY ../../common/silk_keepout.py out/pack-clock.kicad_pcb --check 2>&1 | grep -E "silkscreen|via at" || true
fi
$K sch erc -o out/erc.rpt out/pack-clock.kicad_sch 2>&1 | grep -i violation || true
$K pcb drc --schematic-parity --format json -o out/drc.json out/pack-clock.kicad_pcb >/dev/null 2>&1 || true
python3 - <<'PY'
import json, collections
d = json.load(open("out/drc.json"))
print("DRC violations:", dict(collections.Counter(v["type"] for v in d["violations"])) or "none")
print("unrouted:", len(d["unconnected_items"]))
print("schematic parity:", dict(collections.Counter(v["type"] for v in d.get("schematic_parity", []))) or "none")
PY
