"""Copy each part's description, maker and part number from design.py onto the routed board's footprints, so a
wording change never needs a re-route.   <KiCad python> sync_fields.py <generator folder> <board.kicad_pcb>"""
import sys

import pcbnew

sys.path.insert(0, sys.argv[1])
from design import PARTS  # noqa: E402

b = pcbnew.LoadBoard(sys.argv[2])
n = 0
for p in PARTS:
    fp = b.FindFootprintByReference(p["ref"])
    if not fp:
        continue
    fp.SetValue(p["value"])
    fp.SetField("Description", p["desc"])
    if p.get("mfr"):
        fp.SetField("Manufacturer", p["mfr"]); fp.SetField("MPN", p["mpn"])
    for f_ in fp.GetFields():
        if f_.GetName() in ("Manufacturer", "MPN", "Description"):
            f_.SetVisible(False)
    n += 1
pcbnew.SaveBoard(sys.argv[2], b)
print(f"fields: {n} parts brought up to date")
