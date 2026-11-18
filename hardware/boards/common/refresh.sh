#!/bin/bash
# Refresh a routed board after text-only changes (names, silkscreen, descriptions), without routing again:
# schematic -> netlist -> silkscreen redrawn -> part numbers -> checks.   bash refresh.sh <board folder> <name>
set -e
cd "$1/generator"
N=$2
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
F='fontconfig|stdpbase|assert'
python3 gen_sch.py
cp $N.kicad_sch out/
$K sch export netlist --format kicadsexpr -o out/netlist.net out/$N.kicad_sch 2>&1 | grep -v -i -E "$F" || true
$KPY ../../common/sync_fields.py . out/$N.kicad_pcb 2>&1 | grep -E "fields" || true
$KPY silk.py out/$N.kicad_pcb 2>&1 | grep -v -i -E "$F" || true
$KPY relabel.py out/$N.kicad_pcb 2>&1 | grep -E "part numbers" || true
$KPY ../../common/silk_keepout.py out/$N.kicad_pcb --check 2>&1 | grep -E "silkscreen|via at" || true
$K sch erc -o out/erc.rpt out/$N.kicad_sch 2>&1 | grep -i violation || true
$K pcb drc --schematic-parity --format json -o out/drc.json out/$N.kicad_pcb >/dev/null 2>&1 || true
python3 - <<'PY'
import json, collections
d = json.load(open("out/drc.json"))
print("DRC violations:", dict(collections.Counter(v["type"] for v in d["violations"])) or "none")
print("unrouted:", len(d["unconnected_items"]))
print("schematic parity:", dict(collections.Counter(v["type"] for v in d.get("schematic_parity", []))) or "none")
PY
