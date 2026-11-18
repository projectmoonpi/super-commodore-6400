"""Tidal (C)lock, through-hole edition: place the parts, give each pad its net, outline, 2-layer stack, silkscreen.
Run with KiCad's Python (build.sh does). Coordinates: mm, x right, y down, seen from the top.

The Pico H across the top left (USB at the left edge, for the Mac's cable); the Adafruit Si5351 board top right, its
7-pin row along its lower edge; the five DIP chips in a row across the middle in signal order (inverter, flip-flops,
AND gates, colour buffers); the four ports along the bottom edge, each with its four resistors standing above it;
scope points down the left; M3 holes in the corners. Every part is through-hole: nothing smaller than a DIP pin.
"""
import json
import math
import os
import re
import sys

import pcbnew
from design import PARTS, NETCLASSES, DEFAULT_TRACK, DEFAULT_CLEAR

HERE = os.path.dirname(os.path.abspath(__file__))
FPDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "tidal-clock-tht.kicad_pcb")
W, H = 100.0, 93.0
MM = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


# ---------------------------------------------------------------- the Adafruit board (from its Eagle file)
# 30.48 x 21.59 mm; its 7-pin row 2.54 mm in from one long edge; seen from above with the row at the bottom, the
# pins run CLK0, CLK1, CLK2, SCL, SDA, GND, VIN left to right, the first 7.62 mm in from the left edge.
SYN_X, SYN_ROW = 61.5, 22.0                               # its left edge, and the y of its pin row
SYN_BOX = (SYN_X, SYN_ROW + 2.54 - 21.59, SYN_X + 30.48, SYN_ROW + 2.54)
FIT = {"M1": {str(k): (SYN_X + 7.62 + 2.54 * (k - 1), SYN_ROW) for k in range(1, 8)}}

PX = {1: 20.0, 2: 40.0, 3: 60.0, 4: 80.0}                 # port centres along the bottom edge
CHIP_X = {"U2": 20.0, "U3": 35.0, "U5": 50.0, "U4": 65.0, "U6": 80.0}   # pin 1 of each DIP (pins 1-7 run down)
CHIP_Y = 45.0
P = {"A1": (34.0, 14.5, 90),                              # the Pico's centre (its USB end at the left, x 9)
     "H1": (4.0, 4.0, 0), "H2": (96.0, 4.0, 0), "H3": (4.0, 89.0, 0), "H4": (96.0, 89.0, 0),
     "D1": (93.0, 41.0, 0),
     "TP1": (6.0, 49.0, 0), "TP2": (6.0, 53.5, 0), "TP3": (6.0, 58.0, 0), "TP4": (6.0, 62.5, 0), "TP5": (6.0, 67.0, 0)}
for u, x in CHIP_X.items():
    P[u] = (x, CHIP_Y, 0)
for k, x in PX.items():
    P[f"J{k}"] = (x - 2.54, 85.0, 90)                       # (pin 1: the header centred under its resistors)


def place_by(desc_or_nets, xy, rot=0):
    """Put the first unplaced part with this description (or these nets) at xy (its pin 1)."""
    for p in PARTS:
        if p["ref"] in P or p["ref"] in FIT or not p["fp"]:
            continue
        nets = set(p["pins"].values())
        if (isinstance(desc_or_nets, str) and p["desc"].startswith(desc_or_nets)) or \
                (isinstance(desc_or_nets, set) and desc_or_nets <= nets):
            P[p["ref"]] = (xy[0], xy[1], rot)
            return p["ref"]
    raise KeyError(desc_or_nets)


# axial resistors lie flat, 10.16 mm between holes: rot 0 runs right from pin 1, rot 270 runs down from it
place_by({"COLOR_SRC", "COLOR"}, (64.0, 28.5)); place_by({"DOT_SRC", "DOT"}, (64.0, 31.8))
place_by({"DOT", "DOT_REF"}, (64.0, 35.1))
place_by("Si5351 board supply", (78.0, 28.5)); place_by("3.3 V bulk", (86.0, 29.0))
for k in range(1, 5):
    place_by(f"gate {k} open until", (39.0, 28.5 + 3.3 * (k - 1)))
place_by("5 V bulk", (55.0, 32.0))
for u, x in CHIP_X.items():
    place_by(f"{u} decoupling", (x + 2.5, 41.6))
for k in range(1, 5):
    x = PX[k]
    for dx, what in ((-4.8, f"port {k} dot clock out"), (-1.6, f"port {k} colour clock out"),
                     (1.6, f"port {k} PHI0 in"), (4.8, f"port {k}: no cable reads low")):
        place_by(what, (x + dx, 64.5), 270)
place_by({"+5V", "LED_A"}, (80.0, 38.4))
place_by("edition strap", (5.5, 40.0))
PARTS = [p for p in PARTS if p["fp"]]
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
ds.m_TrackMinWidth = MM(0.15); ds.m_MinClearance = MM(0.2)   # (0.15: the router necks down between Pico pins)
ds.m_ViasMinSize = MM(0.6); ds.m_MinThroughDrill = MM(0.3)   # (the ground-stitching vias: 0.6 / 0.3)
ds.m_HoleClearance = MM(0.25)
ns = ds.m_NetSettings
dflt = ns.GetDefaultNetclass()
dflt.SetTrackWidth(MM(DEFAULT_TRACK)); dflt.SetClearance(MM(DEFAULT_CLEAR))
dflt.SetViaDiameter(MM(0.8)); dflt.SetViaDrill(MM(0.4))
for cname, (tw, cl, members) in NETCLASSES.items():
    nc = pcbnew.NETCLASS(cname)
    nc.SetTrackWidth(MM(tw)); nc.SetClearance(MM(cl)); nc.SetViaDiameter(MM(0.9)); nc.SetViaDrill(MM(0.45))
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


def rect(fp, layer, box, w=0.05):
    x0, y0, x1, y1 = box
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetLayer(layer); s.SetWidth(MM(w))
        fp.Add(s)


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
    if p["ref"] in FIT:
        fit(fp, FIT[p["ref"]])
    else:
        x, y, rot = P[p["ref"]]
        fp.SetOrientationDegrees(rot)
        if p["ref"] == "A1":                     # the Pico's origin isn't its middle: centre its pins on (x, y)
            fp.SetPosition(V(x, y))
            xs = [pd.GetPosition().x for pd in fp.Pads()]; ys = [pd.GetPosition().y for pd in fp.Pads()]
            cx, cy = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
            fp.SetPosition(pcbnew.VECTOR2I(fp.GetPosition().x + MM(x) - cx, fp.GetPosition().y + MM(y) - cy))
        else:                                    # everything else: pin 1 at (x, y)
            fp.SetPosition(V(x, y))
            p1 = next((pd for pd in fp.Pads() if pd.GetNumber() == "1"), None)
            if p1 is not None:
                d = fp.GetPosition() - p1.GetPosition()
                fp.SetPosition(V(x, y) + d)
    if p["ref"] == "M1":                         # the Adafruit board's outline: its courtyard, so nothing sits under it
        for g in [g for g in fp.GraphicalItems() if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.F_SilkS)]:
            fp.Delete(g)
        rect(fp, pcbnew.F_CrtYd, (SYN_BOX[0] - 0.25, SYN_BOX[1] - 0.25, SYN_BOX[2] + 0.25, SYN_BOX[3] + 0.25))
    for pad in fp.Pads():
        key = (p["ref"], pad.GetNumber())
        if key in PIN_NET:
            pad.SetNet(netobj[PIN_NET[key]])
            if p["ref"].startswith("J") and PIN_NET[key] == "GND":   # the clocks' ground return: solid
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    t = fp.Reference()
    t.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0))); t.SetTextThickness(MM(0.15))
    FPS[p["ref"]] = fp

# ---------------------------------------------------------------- outline, rounded corners
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
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
import stackup                                         # noqa: E402  (green mask = the through-hole edition)
stackup.apply(OUT, "Green")
_pro = os.path.splitext(OUT)[0] + ".kicad_pro"
try:
    _cfg = json.load(open(_pro))
except (OSError, ValueError):
    _cfg = {}
_cfg.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {}).update(
    {"lib_footprint_mismatch": "ignore", "lib_footprint_issues": "ignore",
     # every pin is through-hole: a ground pin with one spoke to a top-side island is joined to the back pour too
     "starved_thermal": "ignore"})
json.dump(_cfg, open(_pro, "w"), indent=2)
print("placed", len(PARTS), "parts on", OUT)
