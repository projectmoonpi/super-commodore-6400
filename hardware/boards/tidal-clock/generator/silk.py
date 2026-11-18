"""Tidal (C)lock silkscreen: everything printed on the board, top and back. Kept apart from the placement so it can be
redrawn on a routed board:   <KiCad python> silk.py out/tidal-clock.kicad_pcb
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
_spec = importlib.util.spec_from_file_location(   # the interposer's text and logo helpers (its file is silk.py too)
    "vci_silk", os.path.join(HERE, "..", "..", "tidal-link", "generator", "silk.py"))
_vci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vci)
text, add_logo = _vci.text, _vci.add_logo

NO_REF = {"H1", "H2", "H3", "H4"}


def pos(board, ref):
    fp = board.FindFootprintByReference(ref)
    return pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)


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
        text(board, f"(COMP {k})", x, y - 7.5, 1.0, bold=True)
    for ref, what in (("TP1", "(COLOR)"), ("TP2", "(DOT)"), ("TP3", "(DOT 5V)"), ("TP4", "(GND)"), ("TP5", "(GND)")):
        x, y = pos(board, ref)
        text(board, what, x + 3.0, y, 0.8, align="left")
    ax, ay = pos(board, "A1")
    text(board, "(USB TO MAC)", 3.0, ay + 1.5, 0.8, angle=90)  # upright beside the Pico's USB socket
    x, y = pos(board, "D1")
    text(board, "(POWER)", x, y + 2.6, 0.8)
    text(board, "TIDAL (C)LOCK", 76.0, 33.0, 1.8, bold=True)
    text(board, "TIDAL ARRAY 6400   SMT rev 0.1", 76.0, 35.6, 0.9)
    # ---- back: title, logo, credit, and the ports' pin names (the rule: header pin names on the back)
    # (in the open area on the right, behind the title: no via may go under printing, so it must stay clear of
    # the logic chips' fan-out)
    add_logo(board, os.path.join(HERE, "logo_silk.json"), (68.0, 33.5), 7.0, B, mirror=True)
    text(board, "Tidal (C)lock", 84.0, 31.0, 1.4, bold=True, layer=B)
    text(board, "Tidal Array 6400   SMT rev 0.1", 84.0, 33.0, 0.8, layer=B)
    text(board, "Designed and Created by", 84.0, 35.0, 0.8, bold=True, layer=B)
    text(board, "Project Moon Pi", 84.0, 36.6, 0.8, bold=True, layer=B)
    names = {"1": "G", "2": "DOT", "3": "G", "4": "COL", "5": "G", "6": "PHI0"}
    for k in range(1, 5):
        j = board.FindFootprintByReference(f"J{k}")
        for pd in j.Pads():
            x, y = pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)
            n = pd.GetNumber()
            dy = -1.7 if int(n) % 2 == 0 else 1.7        # each row's names beside it
            text(board, names[n], x, y + dy, 0.8, bold=int(n) % 2 == 0, layer=B)


def part_numbers(board):
    beside, lined, lost = labels.place(board, skip=NO_REF, size=0.8, width=0.64, thickness=0.15)
    print(f"part numbers: {len(beside)} beside their parts, {len(lined)} with a dashed line"
          + (f", NOT PLACED: {' '.join(lost)}" if lost else ""))


if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1])
    apply(b)
    pcbnew.SaveBoard(sys.argv[1], b)
    print("silkscreen redrawn on", sys.argv[1])
