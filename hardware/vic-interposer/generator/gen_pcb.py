"""VIC clock interposer: place the parts, give each pad its net, outline, 2-layer stack, silkscreen.
Run with KiCad's Python (build.sh does).

Coordinates: mm, x right, y down, seen from the top (the VIC's side). The plug J1 sits exactly over the C64's VIC
socket. The socket J2 for the VIC is offset one row (2.54 mm) towards the bottom edge, so the two sets of holes never
meet: each plug pin joins its socket pin with a short track. Everything else is on the extension past pins 20/21,
right beside the clock pins.
"""
import json
import os
import re
import sys

import pcbnew
from design import PARTS, NETCLASSES, DEFAULT_TRACK, DEFAULT_CLEAR

HERE = os.path.dirname(os.path.abspath(__file__))
FPDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "vic-interposer.kicad_pcb")
W, H = 92.0, 27.5
MM = pcbnew.FromMM
X0 = 4.0                         # pin 1 / pin 40 column
YN1, YS1 = 4.0, 4.0 + 15.24      # J1 (plug): rows 21-40 (top) and 1-20 (bottom), as a DIP seen from above
YN2, YS2 = YN1 + 2.54, YS1 + 2.54  # J2 (socket): one row lower


def V(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def dip_targets(yn, ys):
    t = {}
    for n in range(1, 21):
        t[str(n)] = (X0 + (n - 1) * 2.54, ys)
    for n in range(21, 41):
        t[str(n)] = (X0 + (40 - n) * 2.54, yn)
    return t


FIT = {"J1": dip_targets(YN1, YS1), "J2": dip_targets(YN2, YS2)}
# signal order, right to left: cable (J3) -> buffer (U1) -> series resistors (R1, R2) -> switch (SW1) -> the VIC's
# pins 21/22 (top row, x 49.7 / 52.3). PHI0 comes from pin 17 (bottom row) back through U1 and R3 to the cable.
P = {"SW1": (62.5, 4.4, 0),
     "R1": (66.6, 9.4, 0), "R2": (66.6, 12.6, 0),
     "U1": (71.6, 11.0, 0), "C1": (71.6, 7.4, 180), "C2": (71.6, 14.8, 0),
     "R4": (77.0, 9.4, 0), "R5": (77.0, 12.6, 0), "R3": (77.0, 16.2, 0),
     "J3": (84.0, 7.6, 0),
     "TP1": (59.0, 22.8, 0), "TP2": (64.8, 22.8, 0), "TP3": (70.6, 22.8, 0), "TP4": (76.4, 22.8, 0),
     "TP5": (82.2, 22.8, 0)}
BY = {p["ref"]: p for p in PARTS}
PARTS = [p for p in PARTS if p["fp"]]            # (the power flags are schematic-only)
missing = [p["ref"] for p in PARTS if p["ref"] not in P and p["ref"] not in FIT]
assert not missing, missing

# ---------------------------------------------------------------- net names from the schematic's netlist
_nl = open(os.path.join(os.path.dirname(OUT), "netlist.net")).read()
PIN_NET = {}
for m in re.finditer(r'\(net\s+\(code "\d+"\)\s+\(name "((?:[^"\\]|\\.)*)"\)(.*?)\n\t\t\)', _nl, re.S):
    for r_, n_ in re.findall(r'\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', m.group(2)):
        PIN_NET[(r_, n_)] = m.group(1).replace('\\"', '"')

board = pcbnew.NewBoard(OUT)
board.SetCopperLayerCount(2)
ds = board.GetDesignSettings()
ds.m_TrackMinWidth = MM(0.15); ds.m_MinClearance = MM(0.15)
ds.m_ViasMinSize = MM(0.6); ds.m_MinThroughDrill = MM(0.3)
ds.m_HoleClearance = MM(0.25)
ns = ds.m_NetSettings
dflt = ns.GetDefaultNetclass()
dflt.SetTrackWidth(MM(DEFAULT_TRACK)); dflt.SetClearance(MM(DEFAULT_CLEAR))
dflt.SetViaDiameter(MM(0.7)); dflt.SetViaDrill(MM(0.35))
for cname, (tw, cl, members) in NETCLASSES.items():
    nc = pcbnew.NETCLASS(cname)
    nc.SetTrackWidth(MM(tw)); nc.SetClearance(MM(cl)); nc.SetViaDiameter(MM(0.8)); nc.SetViaDrill(MM(0.4))
    ns.SetNetclass(cname, nc)
    for m in members:
        ns.SetNetclassPatternAssignment(m, cname)
netobj = {}
for name in sorted(set(PIN_NET.values())):
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    netobj[name] = ni
link = json.load(open(os.path.join(HERE, "sch_uuids.json")))


def fit(fp, targets):
    names = sorted(targets, key=lambda n: (len(n), n))[:3]
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        pads = {pd.GetNumber(): pd.GetPosition() for pd in fp.Pads()}
        org = fp.GetPosition()
        ref = pads[names[0]]
        dx, dy = MM(targets[names[0]][0]) - ref.x, MM(targets[names[0]][1]) - ref.y
        if all(abs(pads[n].x + dx - MM(targets[n][0])) < MM(0.01) and abs(pads[n].y + dy - MM(targets[n][1])) < MM(0.01)
               for n in targets):
            fp.SetPosition(pcbnew.VECTOR2I(org.x + dx, org.y + dy))
            return
    raise RuntimeError(f"{fp.GetReference()}: no orientation fits")


FPS = {}
for p in PARTS:
    lib, name = p["fp"].split(":")
    fp = pcbnew.FootprintLoad(f"{FPDIR}/{lib}.pretty", name)
    fp.SetFPIDAsString(p["fp"])
    fp.SetReference(p["ref"]); fp.SetValue(p["value"])
    fp.SetField("Description", p["desc"])
    if p.get("mfr"):
        fp.SetField("Manufacturer", p["mfr"]); fp.SetField("MPN", p["mpn"])
    for f_ in fp.GetFields():
        if f_.GetName() in ("Manufacturer", "MPN", "Description"):
            f_.SetVisible(False)
    fp.SetPath(pcbnew.KIID_PATH("/" + link["parts"][p["ref"]]))
    board.Add(fp)
    if p["ref"] in ("J1", "J2"):                # plug and socket strips overlap on purpose: no DIP-body courtyards
        for g in [g for g in fp.GraphicalItems() if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd)]:
            fp.Delete(g)
    if p["ref"] in FIT:
        fit(fp, FIT[p["ref"]])
    else:
        x, y, rot = P[p["ref"]]
        fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
    for pad in fp.Pads():
        key = (p["ref"], pad.GetNumber())
        if key in PIN_NET:
            pad.SetNet(netobj[PIN_NET[key]])
            if p["ref"] == "J3" and PIN_NET[key] == "GND":   # the clocks' ground return: solid to the planes
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    t = fp.Reference()
    t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8))); t.SetTextThickness(MM(0.15))
    FPS[p["ref"]] = fp

# the plug's 40 pin-to-socket tracks, straight and short: each plug pin to the socket pin one row below it (the two
# clock pins excepted: they go through the switch, the router joins those)
for n in range(1, 41):
    if n in (21, 22):
        continue
    a = next(pd for pd in FPS["J1"].Pads() if pd.GetNumber() == str(n))
    b = next(pd for pd in FPS["J2"].Pads() if pd.GetNumber() == str(n))
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(a.GetPosition()); t.SetEnd(b.GetPosition())
    net = a.GetNetname()
    t.SetWidth(MM(0.6 if net in ("+5V", "GND", "VDD") else 0.4))
    # top-row pins (21-40): their socket pin is below on the same column: track on the top; bottom row likewise
    t.SetLayer(pcbnew.F_Cu)
    t.SetNet(a.GetNet()); t.SetLocked(True)
    board.Add(t)

# ---------------------------------------------------------------- the buffer's power, laid by hand
# U1's pads are 0.35 mm at 0.5 mm pitch: the router couldn't bring its 0.6 mm power tracks in, so pin 8 (+5V) gets a
# short track to C1 (turned so its +5V pad faces the chip), and pin 4 (GND) plus each capacitor's ground pad a via
# down to the ground plane on the back. The router then only has to bring +5V to C1.
def padpos(ref, num):
    pd = next(pd for pd in FPS[ref].Pads() if pd.GetNumber() == num)
    return pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y), pd.GetNetname()


def hand_track(points, net, w=0.3):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(x0, y0)); t.SetEnd(V(x1, y1)); t.SetWidth(MM(w)); t.SetLayer(pcbnew.F_Cu)
        t.SetNet(netobj[net]); t.SetLocked(True)
        board.Add(t)


def hand_via(x, y, net):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y)); v.SetWidth(MM(0.7)); v.SetDrill(MM(0.35)); v.SetNet(netobj[net]); v.SetLocked(True)
    board.Add(v)


x8, y8, _ = padpos("U1", "8")
c1v = next(padpos("C1", n) for n in ("1", "2") if padpos("C1", n)[2] == "+5V")
hand_track([(x8, y8), (x8 + 0.75, y8), (x8 + 0.75, c1v[1] + 0.9), (c1v[0], c1v[1])], "+5V")
x4, y4, _ = padpos("U1", "4")
hand_track([(x4, y4), (x4 - 0.8, y4), (x4 - 1.2, y4 + 0.4)], "GND")   # out, then down clear of pin 3's pad
hand_via(x4 - 1.2, y4 + 0.4, "GND")
for ref, dy in (("C1", -1.0), ("C2", 1.0)):
    gx, gy, _ = next(padpos(ref, n) for n in ("1", "2") if padpos(ref, n)[2] == "GND")
    hand_track([(gx, gy), (gx, gy + dy)], "GND")
    hand_via(gx, gy + dy, "GND")

# ---------------------------------------------------------------- outline, rounded corners
import math                                            # noqa: E402
R_ = 1.5
for (x1, y1, x2, y2) in ((R_, 0, W - R_, 0), (W, R_, W, H - R_), (W - R_, H, R_, H), (0, H - R_, 0, R_)):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
for cx, cy, a0 in ((R_, R_, 180), (W - R_, R_, 270), (W - R_, H - R_, 0), (R_, H - R_, 90)):
    arc = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
    arc.SetCenter(V(cx, cy))
    arc.SetStart(V(cx + R_ * math.cos(math.radians(a0)), cy + R_ * math.sin(math.radians(a0))))
    arc.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
    arc.SetLayer(pcbnew.Edge_Cuts); arc.SetWidth(MM(0.1)); board.Add(arc)

# a thin no-track border all round, so nothing runs along the edge
for x0, y0, x1, y1 in ((0, 0, W, 0.5), (0, H - 0.5, W, H), (0, 0, 0.5, H), (W - 0.5, 0, W, H)):
    e = pcbnew.ZONE(board)
    e.SetIsRuleArea(True); e.SetDoNotAllowTracks(True); e.SetDoNotAllowVias(True); e.SetDoNotAllowZoneFills(False)
    e.SetDoNotAllowPads(False); e.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); e.SetLayerSet(ls)
    o = e.Outline(); o.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        o.Append(MM(x), MM(y))
    board.Add(e)

import silk                                            # noqa: E402
silk.fixed(board)

pcbnew.SaveBoard(OUT, board)
_pro = os.path.splitext(OUT)[0] + ".kicad_pro"
try:
    _cfg = json.load(open(_pro))
except (OSError, ValueError):
    _cfg = {}
_cfg.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {}).update(
    {"lib_footprint_mismatch": "ignore", "lib_footprint_issues": "ignore",
     # the plug's 40 pins sit inside the socket's outline by design: the socket stands over the plug's pins
     "pth_inside_courtyard": "ignore"})
json.dump(_cfg, open(_pro, "w"), indent=2)
print("placed", len(PARTS), "parts on", OUT)
