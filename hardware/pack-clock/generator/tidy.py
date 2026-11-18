"""After routing: remove any via the router left behind with nothing on its far side (DRC: via_dangling).
    <KiCad python> tidy.py out/pack-clock.kicad_pcb"""
import sys

import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
gone = 0
for t in list(b.GetTracks()):
    if t.GetClass() != "PCB_VIA" or t.IsLocked():
        continue                                   # (the fan-out's own vias are locked and go to the planes)
    touching = [s for s in b.GetTracks() if s.GetClass() == "PCB_TRACK" and s.GetNetCode() == t.GetNetCode()
                and (s.GetStart() == t.GetPosition() or s.GetEnd() == t.GetPosition())]
    if len(touching) <= 1 and t.GetNetname() not in ("GND", "+5V"):
        for s in touching:
            b.Delete(s)
        b.Delete(t)
        gone += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b)
print(f"tidy: {gone} dangling via(s) removed")
