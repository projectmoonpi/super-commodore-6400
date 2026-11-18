"""Tidal Link Interface (through-hole edition) silkscreen: everything printed on the board, top and back. Kept apart from the placement so
it can be redrawn on a routed board:   <KiCad python> silk.py out/tidal-link-tht.kicad_pcb
Rules: memory pcb-silkscreen-rules (every part labelled, descriptors in brackets, logo D, nothing over vias,
header pin names on the back, no Claude line on the board)."""
import json
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
MM = pcbnew.FromMM
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
import labels                                   # noqa: E402

NO_REF = {"J1", "TP1", "TP2", "TP3", "TP4", "TP5", "R1", "R2", "R3", "R4", "R5"}   # (J1: underneath; the rest printed in columns below)                                 # the plug: underneath, its pins are the C64's


def V(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def text(board, s, x, y, size=0.9, bold=False, align="center", angle=0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s); t.SetPosition(V(x, y)); t.SetLayer(layer)
    w = size * 0.8 if size <= 0.9 else size
    t.SetTextSize(pcbnew.VECTOR2I(MM(w), MM(size)))
    t.SetTextThickness(MM(max(0.15, size * (0.2 if bold else 0.14))))
    t.SetTextAngleDegrees(angle)
    t.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT}.get(
        align, pcbnew.GR_TEXT_H_ALIGN_CENTER))
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def line(board, x0, y0, x1, y1, layer=pcbnew.F_SilkS, w=0.15):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(V(x0, y0)); s.SetEnd(V(x1, y1)); s.SetLayer(layer); s.SetWidth(MM(w))
    board.Add(s)


def apply(board):
    fixed(board)
    part_numbers(board)


def fixed(board):
    for d in [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]:
        board.Delete(d)
    for fp in board.GetFootprints():
        fp.Reference().SetVisible(fp.GetReference() not in NO_REF)
        if fp.GetReference() in ("J1", "J2"):    # drawn below instead: the two socket strips and the notch
            for g in [g for g in fp.GraphicalItems() if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]:
                fp.Delete(g)
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    # ---- top: the two socket strips (one per VIC row), and the VIC's notch end (pins 1 and 40)
    x0, x1 = 4.0 - 1.45, 4.0 + 19 * 2.54 + 1.45
    for yc in (4.0 + 2.54, 4.0 + 15.24 + 2.54):
        for (a, b, c, d) in ((x0, yc - 1.4, x1, yc - 1.4), (x0, yc + 1.4, x1, yc + 1.4), (x0, yc - 1.4, x0, yc + 1.4),
                             (x1, yc - 1.4, x1, yc + 1.4)):
            line(board, a, b, c, d, F)
    text(board, "NOTCH", 1.15, 14.16, 0.9, bold=True, angle=90)         # the VIC's notch goes at this end
    text(board, "1", 2.0, 22.9, 0.9, bold=True)                          # pin 1 of the VIC's socket
    # ---- top
    def pad(ref, num):
        pd = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
        return pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)
    p1, p3 = pad("SW1", "1"), pad("SW1", "3")
    text(board, "INT", p1[0] - 0.6, 1.1, 0.8, bold=True)    # pin 1 end: the C64's own clocks
    text(board, "EXT", p3[0] + 0.6, 1.1, 0.8, bold=True)    # pin 3 end: the Tidal (C)lock board
    text(board, "(POWER OFF ONLY)", 54.3, 21.6, 0.8, angle=90)   # the switch: upright, between the VIC and the TPs
    # the scope points and the resistor column: numbers printed by hand in straight columns (the part-number
    # placer would scatter them in this tight corner)
    for ref, what in (("TP1", "(PHI0)"), ("TP2", "(DOT)"), ("TP3", "(COLOR)"), ("TP4", "(GND)"), ("TP5", "(GND)")):
        x, y = pad(ref, "1")
        text(board, f"{ref} {what}", x + 2.0, y, 0.8, align="left")
    for ref in ("R1", "R2", "R3", "R4", "R5"):
        x, y = pad(ref, "2")
        text(board, ref, x + 1.3, y, 0.8, align="left")
    j3 = board.FindFootprintByReference("J3")
    jx, jy = pcbnew.ToMM(j3.GetPosition().x), pcbnew.ToMM(j3.GetPosition().y)
    text(board, "(TO TIDAL (C)LOCK)", jx + 1.27, jy - 6.3, 0.8)
    text(board, "TIDAL LINK INTERFACE (TLI)", 28.0, 12.6, 1.4, bold=True)      # under the chip: seen with it out
    text(board, "TIDAL ARRAY 6400   THT rev 0.1", 28.0, 15.0, 0.9)
    # ---- back: the side that faces the C64
    text(board, "THIS SIDE DOWN: INTO THE VIC-II SOCKET", 28.0, 8.0, 1.0, bold=True, layer=B)
    text(board, "< PIN 1", 4.0 + 3.6, 17.4, 0.9, bold=True, layer=B)   # above-right of pin 1's hole, pointing at it
    text(board, "CLOCK SWITCH: ONLY WITH THE POWER SWITCHED OFF", 28.0, 23.2, 0.9, layer=B)
    add_logo(board, os.path.join(HERE, "logo_silk.json"), (16.0, 12.4), 6.6, B, mirror=True)
    text(board, "Designed and Created by Project Moon Pi", 34.0, 11.6, 0.9, bold=True, layer=B)
    text(board, "Tidal Link Interface (TLI)", 34.0, 13.3, 0.8, bold=True, layer=B)
    text(board, "Tidal Array 6400   THT rev 0.1", 34.0, 14.9, 0.8, layer=B)
    # J3's pin names on the back, as the rule asks: the edge row (2, 4, 6) and the inner row (1, 3, 5)
    pads = {pd.GetNumber(): pd.GetPosition() for pd in j3.Pads()}
    names = {"1": "G", "2": "DOT", "3": "G", "4": "COL", "5": "G", "6": "PHI0"}
    for n, pos in pads.items():
        x, y = pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)
        dx = 2.2 if int(n) % 2 == 0 else -2.2
        text(board, names[n], x + dx * 1.15, y, 0.8, bold=int(n) % 2 == 0, layer=B)


def part_numbers(board):
    beside, lined, lost = labels.place(board, skip=NO_REF, size=0.8, width=0.64, thickness=0.15)
    print(f"part numbers: {len(beside)} beside their parts, {len(lined)} with a dashed line"
          + (f", NOT PLACED: {' '.join(lost)}" if lost else ""))


def add_logo(board, path, centre, width_mm, layer, mirror):
    data = json.load(open(path))
    s = width_mm / data["width_px"]
    cx, cy = centre
    x_left, y_top = cx - width_mm / 2, cy - data["height_px"] * s / 2
    ps = pcbnew.SHAPE_POLY_SET()
    for y, runs in data["rows"]:
        for x0, x1 in runs:
            if mirror:
                x0, x1 = data["width_px"] - x1, data["width_px"] - x0
            ps.NewOutline()
            for px, py in [(x0, y), (x1, y), (x1, y + 1), (x0, y + 1)]:
                ps.Append(MM(x_left + px * s), MM(y_top + py * s + (0.0005 if py > y else -0.0005)))
    ps.Simplify(); ps.Fracture()
    for i in range(ps.OutlineCount()):
        piece = pcbnew.SHAPE_POLY_SET(); piece.AddOutline(ps.COutline(i))
        sh = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
        sh.SetPolyShape(piece); sh.SetFilled(True); sh.SetWidth(0); sh.SetLayer(layer)
        board.Add(sh)


if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1])
    apply(b)
    pcbnew.SaveBoard(sys.argv[1], b)
    print("silkscreen redrawn on", sys.argv[1])
