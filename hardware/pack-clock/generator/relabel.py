"""Place the part numbers on a routed module: beside each part, or with a dashed line, never over a via.
    <KiCad python> relabel.py out/timing-module.kicad_pcb"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import silk  # noqa: E402

path = sys.argv[1]
b = pcbnew.LoadBoard(path)
silk.part_numbers(b)
pcbnew.SaveBoard(path, b)
