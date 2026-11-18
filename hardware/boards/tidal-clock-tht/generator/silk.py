"""Tidal (C)lock (through-hole edition) silkscreen: everything printed on the board, top and back. Kept apart from
the placement so it can be redrawn on a routed board:   <KiCad python> silk.py out/tidal-clock-tht.kicad_pcb
Rules: memory pcb-silkscreen-rules (every part labelled, descriptors in brackets, logo D, nothing over vias,
header pin names on the back, no Claude line on the board)."""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
MM = pcbnew.FromMM
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
import labels                                   # noqa: E402
import importlib.util                           # noqa: E402
_spec = importlib.util.spec_from_file_location(   # the TLI's text and logo helpers (its file is silk.py too)
    "tli_silk", os.path.join(HERE, "..", "..", "tidal-link", "generator", "silk.py"))
_tli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tli)
text, line, add_logo = _tli.text, _tli.line, _tli.add_logo

NO_REF = {"H1", "H2", "H3", "H4"}


def pos(board, ref):
    fp = board.FindFootprintByReference(ref)
    return pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)


def pad(board, ref, num):
    pd = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
    return pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)


def apply(board):
    fixed(board)
    part_numbers(board)


def fixed(board):
    for d in [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]:
        board.Delete(d)
    for fp in board.GetFootprints():
        fp.Reference().SetVisible(fp.GetReference() not in NO_REF)
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    # ---- top
    for k in range(1, 5):
        x, y = pos(board, f"J{k}")
        # under its box header, right of where its J number goes (the resistors' numbers fill the row above it)
        text(board, f"(COMP {k})", pad(board, f"J{k}", "3")[0] + 2.2, 91.0, 1.0, bold=True, align="left")
    for ref, what in (("TP1", "(COLOR)"), ("TP2", "(DOT)"), ("TP3", "(DOT 5V)"), ("TP4", "(GND)"), ("TP5", "(GND)")):
        x, y = pos(board, ref)
        text(board, what, x + 2.6, y, 0.8, align="left")
    ax, ay = pos(board, "A1")
    text(board, "(USB TO MAC)", 2.6, 14.5, 0.8, angle=90)   # upright beside the Pico's USB socket
    x, y = pad(board, "D1", "1")
    text(board, "(POWER)", x + 1.27, y + 3.0, 0.8)
    # the Adafruit board: its outline, which way round it goes, and the two ends of its pin row
    c1, c7 = pad(board, "M1", "1"), pad(board, "M1", "7")
    x0, x1, y0, y1 = c1[0] - 7.62, c7[0] + 7.62, c1[1] + 2.54 - 21.59, c1[1] + 2.54
    for a, b, c, d in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        line(board, a, b, c, d, F)
    text(board, "(ADAFRUIT Si5351A BOARD #2045)", (x0 + x1) / 2, y0 + 5.0, 1.0, bold=True)
    text(board, "(CHIP SIDE UP, PIN ROW HERE)", (x0 + x1) / 2, y0 + 7.0, 0.8)
    text(board, "CLK0", c1[0], c1[1] - 2.2, 0.8, bold=True)
    text(board, "VIN", c7[0], c7[1] - 2.2, 0.8, bold=True)
    text(board, "TIDAL (C)LOCK", 16.5, 30.5, 1.8, bold=True)
    text(board, "TIDAL ARRAY 6400", 16.5, 33.2, 0.9)
    text(board, "THROUGH-HOLE EDITION   rev 0.1", 16.5, 35.0, 0.9)
    # ---- back: title, logo, credit (between the Pico's two pin rows), and the ports' pin names
    add_logo(board, os.path.join(HERE, "logo_silk.json"), (17.0, 14.5), 8.0, B, mirror=True)
    text(board, "Tidal (C)lock", 40.0, 11.2, 1.4, bold=True, layer=B)
    text(board, "Tidal Array 6400   THT rev 0.1", 40.0, 13.4, 0.8, layer=B)
    text(board, "Designed and Created by", 40.0, 15.6, 0.8, bold=True, layer=B)
    text(board, "Project Moon Pi", 40.0, 17.2, 0.8, bold=True, layer=B)
    names = {"1": "G", "2": "DOT", "3": "G", "4": "COL", "5": "G", "6": "PHI0"}
    for k in range(1, 5):
        j = board.FindFootprintByReference(f"J{k}")
        for pd in j.Pads():
            x, y = pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)
            n = pd.GetNumber()
            dy = -1.9 if int(n) % 2 == 0 else 1.9        # each row's names beside it
            text(board, names[n], x, y + dy, 0.8, bold=int(n) % 2 == 0, layer=B)


def part_numbers(board):
    beside, lined, lost = labels.place(board, skip=NO_REF, size=1.0, width=0.8, thickness=0.15)
    print(f"part numbers: {len(beside)} beside their parts, {len(lined)} with a dashed line"
          + (f", NOT PLACED: {' '.join(lost)}" if lost else ""))


if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1])
    apply(b)
    pcbnew.SaveBoard(sys.argv[1], b)
    print("silkscreen redrawn on", sys.argv[1])
