"""KiCad half of the PCBWay package (run with KiCad's python): on a COPY of the board, put the drill/place origin at the
board's bottom-left corner (so Gerbers, drill files and the placement file share one origin), save it, and dump every
part's data as JSON for pcbway_package.py.

    <KiCad python> pcbway_dump.py board_copy.kicad_pcb parts.json
"""
import json
import sys

import pcbnew

M = pcbnew.ToMM
path, out = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(path)
e = b.GetBoardEdgesBoundingBox()
ox, oy = e.GetLeft(), e.GetBottom()                     # bottom-left corner of the outline
ds = b.GetDesignSettings()
ds.SetAuxOrigin(pcbnew.VECTOR2I(ox, oy))
pcbnew.SaveBoard(path, b)

parts = []
for fp in b.GetFootprints():
    a = fp.GetAttributes()
    if a & pcbnew.FP_EXCLUDE_FROM_BOM and a & pcbnew.FP_EXCLUDE_FROM_POS_FILES:
        continue                                        # mounting holes, test pads, 3D-only models
    f = {fd.GetName(): fd.GetText() for fd in fp.GetFields()}
    p = fp.GetPosition()
    parts.append(dict(
        ref=fp.GetReference(), value=fp.GetValue(), mfr=f.get("Manufacturer", ""), mpn=f.get("MPN", ""),
        desc=f.get("Description", ""), footprint=fp.GetFPID().GetLibItemName().wx_str(),
        tht=bool(a & pcbnew.FP_THROUGH_HOLE), bom=not (a & pcbnew.FP_EXCLUDE_FROM_BOM),
        pos=not (a & pcbnew.FP_EXCLUDE_FROM_POS_FILES),
        x=round(M(p.x - ox), 4), y=round(M(oy - p.y), 4),          # mm from the bottom-left corner, Y up
        rot=round(fp.GetOrientationDegrees() % 360, 2), side="Bottom" if fp.IsFlipped() else "Top"))
json.dump(dict(size=(round(M(e.GetWidth()), 2), round(M(e.GetHeight()), 2)), layers=b.GetCopperLayerCount(),
               thickness=M(ds.GetBoardThickness()), parts=parts), open(out, "w"), indent=1)
print(f"{len(parts)} parts dumped, origin at the board's bottom-left corner")
