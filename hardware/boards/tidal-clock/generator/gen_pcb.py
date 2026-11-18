"""Tidal (C)lock: place the parts, give each pad its net, outline, 2-layer stack, silkscreen.
Run with KiCad's Python (build.sh does). Coordinates: mm, x right, y down, seen from the top.

The Pico H across the top (USB at the left edge, for the Mac's cable); the synthesizer and crystal at the left;
the logic in signal order left to right (inverter, flip-flops, AND gates, colour buffers); the four ports along the
bottom edge, each with its four resistors right above it; scope points down the left; M3 holes in the corners.
"""
import json
import os
import re
import sys

import pcbnew
from design import PARTS, NETCLASSES, DEFAULT_TRACK, DEFAULT_CLEAR

HERE = os.path.dirname(os.path.abspath(__file__))
FPDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "tidal-clock.kicad_pcb")
W, H = 100.0, 80.0
MM = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


FIT = {}
PX = {1: 20.0, 2: 40.0, 3: 60.0, 4: 80.0}             # port centres along the bottom edge
P = {"A1": (34.5, 14.5, 90),           # the Pico's centre (its USB end at the left, x 9)
     "H1": (4.0, 4.0, 0), "H2": (96.0, 4.0, 0), "H3": (4.0, 76.0, 0), "H4": (96.0, 76.0, 0),
     "U1": (17.0, 38.0, 0), "Y1": (11.8, 37.25, 270),  # the crystal at XA/XB (left side), XB facing the chip
     "U2": (28.0, 48.0, 0), "U3": (40.0, 48.0, 0), "U5": (52.0, 48.0, 0), "U4": (64.0, 48.0, 0),
     "U6": (76.0, 48.0, 0),
     "D1": (92.0, 10.0, 90),
     "TP1": (6.0, 47.0, 0), "TP2": (6.0, 51.5, 0), "TP3": (6.0, 56.0, 0), "TP4": (6.0, 60.5, 0), "TP5": (6.0, 65.0, 0)}
for k, x in PX.items():
    P[f"J{k}"] = (x, 71.5, 90)
BY = {p["ref"]: p for p in PARTS}
# the passives: next to what they serve, found by their nets
def place_by(desc_or_nets, xy, rot=90):
    for p in PARTS:
        if p["ref"] in P or not p["fp"]:
            continue
        nets = set(p["pins"].values())
        if (isinstance(desc_or_nets, str) and p["desc"] == desc_or_nets) or \
                (isinstance(desc_or_nets, set) and desc_or_nets <= nets):
            P[p["ref"]] = (xy[0], xy[1], rot)
            return p["ref"]
    raise KeyError(desc_or_nets)


# round the Si5351 (QFN-20: XA/XB/SCL/SDA left, the clock outputs CLK0/CLK1 on the right between 3.3 V pins):
# each part beside the pins it serves
place_by("Si5351 VDD", (16.0, 33.6), 0); place_by("Si5351 VDDO", (17.5, 41.6), 0)
place_by({"SDA", "+3V3"}, (11.8, 41.4), 0); place_by({"SCL", "+3V3"}, (11.8, 43.2), 0)
place_by({"COLOR_SRC", "COLOR"}, (21.4, 37.4), 0); place_by({"DOT_SRC", "DOT"}, (21.4, 39.6), 0)
place_by({"DOT", "DOT_REF"}, (25.0, 41.2), 0)
for u in ("U2", "U3", "U4", "U5", "U6"):
    x, y, _ = P[u]
    place_by(f"{u} decoupling", (x, y - 5.0), 0)
place_by("5 V bulk", (30.0, 27.6), 0); place_by("3.3 V bulk", (24.0, 31.0), 0)
for k in range(1, 5):
    place_by(f"gate {k} open until the Pico says otherwise", (36.0 + 3.0 * k, 30.0))
    x = PX[k]
    place_by(f"port {k} dot clock out", (x - 4.5, 61.0))
    place_by(f"port {k} colour clock out", (x - 1.5, 61.0))
    place_by(f"port {k} PHI0 in", (x + 1.5, 61.0))
    place_by(f"port {k}: no cable reads low", (x + 4.5, 61.0))
place_by({"+5V", "LED_A"}, (89.0, 10.0))
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
board.SetCopperLayerCount(4)
board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)     # solid ground plane
board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)     # solid 5 V plane
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
    if p["ref"] in FIT:
        fit(fp, FIT[p["ref"]])
    else:
        x, y, rot = P[p["ref"]]
        fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
        if p["ref"] == "A1":                     # the Pico's origin isn't its middle: centre its pins on (x, y)
            xs = [pd.GetPosition().x for pd in fp.Pads()]; ys = [pd.GetPosition().y for pd in fp.Pads()]
            cx, cy = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
            fp.SetPosition(pcbnew.VECTOR2I(fp.GetPosition().x + MM(x) - cx, fp.GetPosition().y + MM(y) - cy))
    for pad in fp.Pads():
        key = (p["ref"], pad.GetNumber())
        if key in PIN_NET:
            pad.SetNet(netobj[PIN_NET[key]])
            if p["ref"].startswith("J") and PIN_NET[key] == "GND":   # the clocks' ground return: solid
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    t = fp.Reference()
    t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8))); t.SetTextThickness(MM(0.15))
    FPS[p["ref"]] = fp

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
    ls = pcbnew.LSET()
    for L_ in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.AddLayer(L_)
    e.SetLayerSet(ls)
    o = e.Outline(); o.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        o.Append(MM(x), MM(y))
    board.Add(e)

# the two inner planes go in before routing: the router drops a via from each ground or 5 V pin to its plane
for layer, net in ((pcbnew.In1_Cu, "GND"), (pcbnew.In2_Cu, "+5V")):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET(); ls.AddLayer(layer); z.SetLayerSet(ls); z.SetNet(netobj[net])
    z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
    o = z.Outline(); o.NewOutline()
    for x, y in ((0.6, 0.6), (W - 0.6, 0.6), (W - 0.6, H - 0.6), (0.6, H - 0.6)):
        o.Append(MM(x), MM(y))
    board.Add(z)
# a 3.3 V island in the 5 V layer, under the Si5351 corner: the synthesizer's five 3.3 V pins (0.5 mm pitch) and
# the parts round it drop a via straight into it. (Higher priority: it cuts its own hole in the 5 V plane.)
ISLAND = (8.0, 28.5, 25.8, 45.0)
z = pcbnew.ZONE(board)
ls = pcbnew.LSET(); ls.AddLayer(pcbnew.In2_Cu); z.SetLayerSet(ls); z.SetNet(netobj["+3V3"]); z.SetAssignedPriority(1)
z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
o = z.Outline(); o.NewOutline()
for x, y in ((ISLAND[0], ISLAND[1]), (ISLAND[2], ISLAND[1]), (ISLAND[2], ISLAND[3]), (ISLAND[0], ISLAND[3])):
    o.Append(MM(x), MM(y))
board.Add(z)

import silk                                            # noqa: E402
silk.fixed(board)

VIA_D, VIA_DRILL = 0.6, 0.3
# the crystal's two tracks and pin 14's way into the 3.3 V island, laid by hand: the QFN's corner is too tight for
# the router (positions from the pads; clearances worked out against pins 3, 15, C1 and R3)
HAND = []                                              # (x0, y0, x1, y1, net, half width): the fan-out keeps clear


def _hand(points, net, w=0.25):
    for _a, _b in zip(points, points[1:]):
        HAND.append((_a[0], _a[1], _b[0], _b[1], net, w / 2))
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(*_a)); t.SetEnd(V(*_b)); t.SetWidth(MM(w)); t.SetLayer(pcbnew.F_Cu)
        t.SetNet(netobj[net]); t.SetLocked(True); board.Add(t)


def _pad(ref, num):
    pd = next(pd for pd in FPS[ref].Pads() if pd.GetNumber() == num)
    return pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)


xa, xb, u1a, u1b, u14 = _pad("Y1", "1"), _pad("Y1", "3"), _pad("U1", "1"), _pad("U1", "2"), _pad("U1", "14")
_hand([xb, (u1b[0] - 0.86, u1b[1]), u1b], "XB")                                  # XB straight across
_hand([xa, (xa[0], xa[1] - 1.2), (u1a[0] - 0.76, xa[1] - 1.2), (u1a[0] - 0.76, u1a[1]), u1a], "XA")  # XA over the top
_hand([u14, (u14[0] + 0.81, u14[1]), (u14[0] + 0.81, u14[1] - 1.7)], "+3V3")       # pin 14 out and up
u1g = _pad("U1", "3")
_hand([u1g, (u1g[0] + 1.0, u1g[1])], "GND")                                      # pin 3 in to the centre ground pad
VIAS_HAND = [(u14[0] + 0.81, u14[1] - 1.7, "+3V3")]
_v = pcbnew.PCB_VIA(board)
_v.SetPosition(V(u14[0] + 0.81, u14[1] - 1.7)); _v.SetWidth(MM(VIA_D)); _v.SetDrill(MM(VIA_DRILL))
_v.SetNet(netobj["+3V3"]); _v.SetLocked(True); board.Add(_v)
# ---------------------------------------------------------------- fan-out to the planes, before routing
# Every surface-mount ground or 5 V pad gets a short track and a via down to its plane (ground In1, 5 V In2), in the
# first spot clear of other pads, vias and printing (a via's hole would cut the printing). Through-hole pins reach
# the planes by themselves. The router is then left with the signals and the 3.3 V rail.
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
import silk_keepout                                    # noqa: E402
_silk = silk_keepout.silk_shapes(board, refs=False)
SILK = []
for _i in range(_silk.OutlineCount()):
    _pc = pcbnew.SHAPE_POLY_SET(); _pc.AddOutline(_silk.COutline(_i))
    _bb = _pc.BBox()
    SILK.append(((pcbnew.ToMM(_bb.GetLeft()), pcbnew.ToMM(_bb.GetTop()), pcbnew.ToMM(_bb.GetRight()),
                  pcbnew.ToMM(_bb.GetBottom())), _pc))
PADS = []
for _fp in board.GetFootprints():
    for _pd in _fp.Pads():
        bb = _pd.GetBoundingBox()
        PADS.append((_pd.GetNetname(), pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                     pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))
VIAS = list(VIAS_HAND)


def seg_clear(p0, p1, net, half=0.15, gap=0.17):
    """The stub from a pad to its via keeps its clearance from every other net's pad, all along its length."""
    for k in range(11):
        x = p0[0] + (p1[0] - p0[0]) * k / 10; y = p0[1] + (p1[1] - p0[1]) * k / 10
        for n, x0, y0, x1, y1 in PADS:
            if n == net:
                continue
            dx = max(x0 - x, 0, x - x1); dy = max(y0 - y, 0, y - y1)
            if (dx * dx + dy * dy) ** 0.5 < half + gap:
                return False
    return True


def clear(x, y, net, r=VIA_D / 2, gap=0.2):
    if not (1.0 < x < W - 1.0 and 1.0 < y < H - 1.0):
        return False
    for n, x0, y0, x1, y1 in PADS:
        if n == net:
            continue
        dx = max(x0 - x, 0, x - x1); dy = max(y0 - y, 0, y - y1)
        if (dx * dx + dy * dy) ** 0.5 < r + gap:
            return False
    for vx, vy, vn in VIAS:
        if ((vx - x) ** 2 + (vy - y) ** 2) ** 0.5 < VIA_D + (gap if vn != net else 0.1):
            return False
    for x0, y0, x1, y1, hn, hw in HAND:               # the hand-laid tracks
        if hn == net:
            continue
        L2 = (x1 - x0) ** 2 + (y1 - y0) ** 2 or 1e-9
        t_ = max(0.0, min(1.0, ((x - x0) * (x1 - x0) + (y - y0) * (y1 - y0)) / L2))
        if ((x - x0 - t_ * (x1 - x0)) ** 2 + (y - y0 - t_ * (y1 - y0)) ** 2) ** 0.5 < r + hw + gap:
            return False
    for (x0, y0, x1, y1), pc in SILK:
        if x0 - r - 0.1 <= x <= x1 + r + 0.1 and y0 - r - 0.1 <= y <= y1 + r + 0.1 and pc.Collide(V(x, y), MM(r + 0.1)):
            return False
    return True


fanned, missed = 0, []
for fp in board.GetFootprints():
    cx, cy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    for pd in fp.Pads():
        net = pd.GetNetname()
        if pd.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        _px, _py = pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)
        in_island = ISLAND[0] + 1 < _px < ISLAND[2] - 1 and ISLAND[1] + 1 < _py < ISLAND[3] - 1
        if net == "+3V3" and not in_island:
            continue                                # (3.3 V elsewhere: the router's tracks)
        if net == "+5V" and in_island:
            continue                                # (no 5 V plane under the island)
        if net not in ("GND", "+5V", "+3V3"):
            continue
        px, py = pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)
        ux, uy = px - cx, py - cy
        L = (ux * ux + uy * uy) ** 0.5 or 1.0
        ux, uy = ux / L, uy / L                     # outward from the part's middle
        done = False
        if pd.GetNumber() == "21" and fp.GetReference() == "U1":
            continue                                # the Si5351's centre pad: its own vias, below
        for d in (0.9, 1.2, 1.5, 1.9, 2.4):
            for side in (0, 0.6, -0.6, 1.0, -1.0, 1.5, -1.5):
                vx, vy = px + ux * d - uy * side, py + uy * d + ux * side
                if clear(vx, vy, net) and seg_clear((px, py), (vx, vy), net):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(V(px, py)); t.SetEnd(V(vx, vy)); t.SetWidth(MM(0.3)); t.SetLayer(pcbnew.F_Cu)
                    t.SetNet(netobj[net]); t.SetLocked(True); board.Add(t)
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(V(vx, vy)); v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL))
                    v.SetNet(netobj[net]); v.SetLocked(True); board.Add(v)
                    VIAS.append((vx, vy, net))
                    fanned += 1
                    done = True
                    break
            if done:
                break
        if not done:
            missed.append(f"{fp.GetReference()}.{pd.GetNumber()}")
# the Si5351's top 3.3 V pins (18, 20) have no room for vias of their own: a short track joins them above the
# chip, clear of pin 19 between them (pin 20 has its via into the 3.3 V island)
_p18 = next(pd for pd in FPS["U1"].Pads() if pd.GetNumber() == "18")
_p20 = next(pd for pd in FPS["U1"].Pads() if pd.GetNumber() == "20")
_x18, _y = pcbnew.ToMM(_p18.GetPosition().x), pcbnew.ToMM(_p18.GetPosition().y)
_x20 = pcbnew.ToMM(_p20.GetPosition().x)
for (_a, _b) in (((_x20, _y), (_x20, _y - 0.8)), ((_x20, _y - 0.8), (_x18, _y - 0.8)), ((_x18, _y - 0.8), (_x18, _y))):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(V(*_a)); t.SetEnd(V(*_b)); t.SetWidth(MM(0.25)); t.SetLayer(pcbnew.F_Cu)
    t.SetNet(netobj["+3V3"]); t.SetLocked(True); board.Add(t)
# the Si5351's exposed centre pad: four vias in it, down to the ground plane
u1 = FPS["U1"]
ux_, uy_ = pcbnew.ToMM(u1.GetPosition().x), pcbnew.ToMM(u1.GetPosition().y)
for dx in (-0.6, 0.6):
    for dy in (-0.6, 0.6):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(ux_ + dx, uy_ + dy)); v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL))
        v.SetNet(netobj["GND"]); v.SetLocked(True); board.Add(v)
        fanned += 1
print(f"fan-out: {fanned} pads given a via to their plane" + (f", no room at {' '.join(missed)}" if missed else ""))

pcbnew.SaveBoard(OUT, board)
import stackup                                         # noqa: E402  (common/: blue mask = the SMT edition)
stackup.apply(OUT, "Blue")
_pro = os.path.splitext(OUT)[0] + ".kicad_pro"
try:
    _cfg = json.load(open(_pro))
except (OSError, ValueError):
    _cfg = {}
_cfg.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {}).update(
    {"lib_footprint_mismatch": "ignore", "lib_footprint_issues": "ignore",
     # every ground pin also has its own via to the solid inner ground plane, so one spoke to an outer pour is fine
     "starved_thermal": "ignore"})
json.dump(_cfg, open(_pro, "w"), indent=2)
print("placed", len(PARTS), "parts on", OUT)
