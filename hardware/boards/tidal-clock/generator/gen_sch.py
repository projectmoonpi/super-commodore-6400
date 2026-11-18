"""Write tidal-clock.kicad_sch from design.py: one sheet, the parts in boxed blocks, every connected pin tagged with its net's name (a global label on the pin's end), every
unused pin marked no-connect.

Pins with the same label are one net, so the drawing is exact even without wires between blocks. KiCad's ERC and
the board's schematic-parity check confirm it (build.sh). Run with python3.
"""
import json
import math
import os
import sys
import uuid

import sexpr
from sexpr import Sym, find
from design import PARTS
from schlib import lib_symbol, pins_of, sym_box, eff, R4

PROJECT = "tidal-clock"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, f"{PROJECT}.kicad_sch")
PAGE_W, PAGE_H = 420.0, 297.0                           # A3, landscape
try:
    _old = json.load(open(os.path.join(HERE, "sch_uuids.json")))
except (OSError, ValueError):
    _old = {}
ROOT = _old.get("root") or str(uuid.uuid4())
OLD = _old.get("parts", {})
items, lib_syms, uuids = [], {}, {}
G = 2.54


def snap(v):
    return round(round(v / 1.27) * 1.27, 4)


def U():
    return [Sym("uuid"), str(uuid.uuid4())]


def pin_dirs(sym, unit):
    """{pin: angle the pin points INTO the body} for one unit (lib angles: 0 right, 90 up)."""
    out = {}

    def walk(node):
        for c in node:
            if isinstance(c, list) and c and c[0] == "pin":
                at = sexpr.first(c, "at")
                out[sexpr.first(c, "number")[1]] = float(at[3]) if len(at) > 3 else 0.0
            elif isinstance(c, list) and c and c[0] == "symbol":
                if c[1].rsplit("_", 2)[-2] not in ("0", str(unit)):
                    continue
                walk(c)
    walk(sym)
    return out


def units_of(sym):
    us = sorted({int(c[1].rsplit("_", 2)[-2]) for c in find(sym, "symbol")} - {0})
    return us or [1]


def label_width(p):
    return max([len(n or "") for n in p["pins"].values()] + [4]) * 1.1 + 4


def place(p, x, y, unit, sym):
    """One symbol unit at (x, y), with its labels and no-connects."""
    lib = p["lib"]
    lib_syms[lib] = sym
    pins = pins_of(sym, unit)
    dirs = pin_dirs(sym, unit)
    u_ = (OLD.get(p["ref"]) if unit == 1 else None) or str(uuid.uuid4())
    if unit == 1:
        uuids[p["ref"]] = u_
    bx = sym_box(sym)[0] if sym_box(sym) else (-2, -2, 2, 2)
    node = [Sym("symbol"), [Sym("lib_id"), lib], [Sym("at"), R4(x), R4(y), 0], [Sym("unit"), unit],
            [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes") if p["fp"] and not p["ref"].startswith(("H",)) else Sym("no")],
            [Sym("on_board"), Sym("yes") if p["fp"] else Sym("no")], [Sym("dnp"), Sym("no")],
            [Sym("uuid"), u_],
            [Sym("property"), "Reference", p["ref"], [Sym("at"), R4(x), R4(y - bx[3] - 2.0), 0], eff(1.27)],
            [Sym("property"), "Value", p["value"], [Sym("at"), R4(x), R4(y - bx[1] + 2.0), 0], eff(1.27)],
            [Sym("property"), "Footprint", p["fp"] or "", [Sym("at"), R4(x), R4(y), 0], eff(1.27, True)],
            [Sym("property"), "Datasheet", "~", [Sym("at"), R4(x), R4(y), 0], eff(1.27, True)],
            [Sym("property"), "Description", p["desc"], [Sym("at"), R4(x), R4(y), 0], eff(1.27, True)]]
    if p.get("mfr"):
        node.append([Sym("property"), "Manufacturer", p["mfr"], [Sym("at"), R4(x), R4(y), 0], eff(1.27, True)])
        node.append([Sym("property"), "MPN", p["mpn"], [Sym("at"), R4(x), R4(y), 0], eff(1.27, True)])
    for n in sorted(pins, key=lambda n: (len(n), n)):
        node.append([Sym("pin"), n, U()])
    node.append([Sym("instances"), [Sym("project"), PROJECT,
                 [Sym("path"), "/" + ROOT, [Sym("reference"), p["ref"]], [Sym("unit"), unit]]]])
    items.append(node)
    for n, (px, py) in pins.items():
        at = (R4(x + px), R4(y - py))
        net = p["pins"].get(n)
        if not net:
            items.append([Sym("no_connect"), [Sym("at"), *at], U()])
            continue
        ang = (dirs.get(n, 0) + 180) % 360
        just = "left" if ang in (0, 90) else "right"
        items.append([Sym("global_label"), net, [Sym("shape"), Sym("passive")], [Sym("at"), *at, int(ang)],
                      [Sym("fields_autoplaced"), Sym("yes")], eff(1.0, justify=just), U(),
                      [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [Sym("at"), *at, 0],
                       eff(1.0, True)]])


GROUPS = [("pico", "RASPBERRY PI PICO H, POWER LIGHT, SCOPE POINTS, MOUNTING HOLES"),
          ("synth", "CLOCK SYNTHESIZER: Si5351A, 25 MHz CRYSTAL (CLK0 = COLOUR 14.318182, CLK1 = DOT 8.181818 MHz)"),
          ("gates", "GLITCH-FREE DOT-CLOCK GATES (ONE PER PORT) AND COLOUR BUFFERS"),
          ("ports", "PORTS 1-4 (TO EACH COMPUTER'S TIDAL LINK INTERFACE) AND THE PHI0 INPUTS")]

# shelf packing: each block in its own box, the boxes filling the page left to right, top to bottom
x0, y0, shelf_h = 15.0, 25.0, 0.0
for grp, title in GROUPS:
    members = [p for p in PARTS if p["group"] == grp]
    cells = []
    for p in members:
        sym = lib_symbol(p["lib"])
        for unit in units_of(sym):
            bx = sym_box(sym)
            xs = [b[0] for b in bx] + [b[2] for b in bx]
            ys = [b[1] for b in bx] + [b[3] for b in bx]
            w = (max(xs) - min(xs)) + 2 * label_width(p)
            h = (max(ys) - min(ys)) + 9.0
            cells.append((p, unit, sym, w, h, min(xs), max(ys)))
    # lay the cells out in rows inside the block, at most ~360 mm wide
    maxw = 260.0
    bx_, by_, row_h, used_w, rows = 0.0, 0.0, 0.0, 0.0, []
    placed = []
    for c in cells:
        if bx_ + c[3] > maxw and bx_ > 0:
            bx_, by_ = 0.0, by_ + row_h
            row_h = 0.0
        placed.append((c, bx_, by_))
        bx_ += c[3]
        used_w = max(used_w, bx_)
        row_h = max(row_h, c[4])
    block_w, block_h = used_w + 10, by_ + row_h + 14
    if x0 + block_w > PAGE_W - 10:
        x0, y0 = 15.0, y0 + shelf_h + 12
        shelf_h = 0.0
    for (p, unit, sym, w, h, minx, maxy), cx, cy in placed:
        sx = snap(x0 + 5 + cx + label_width(p) - minx)
        sy = snap(y0 + 12 + cy + maxy + 3)
        place(p, sx, sy, unit, sym)
    items.append([Sym("rectangle"), [Sym("start"), R4(x0), R4(y0)], [Sym("end"), R4(x0 + block_w), R4(y0 + block_h)],
                  [Sym("stroke"), [Sym("width"), 0.3], [Sym("type"), Sym("dash")]], [Sym("fill"), [Sym("type"), Sym("none")]],
                  U()])
    items.append([Sym("text"), title, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), R4(x0 + 3), R4(y0 + 5), 0],
                  eff(3.0, justify="left", bold=True), U()])
    x0 += block_w + 12
    shelf_h = max(shelf_h, block_h)

items.append([Sym("text"), "TIDAL ARRAY 6400  -  TIDAL (C)LOCK  rev 0.1  -  Designed and Created by Project Moon Pi",
              [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), 15.0, 12.0, 0], eff(5.0, justify="left", bold=True), U()])

sch = [Sym("kicad_sch"), [Sym("version"), 20250114], [Sym("generator"), "hub_gen_sch"],
       [Sym("generator_version"), "1"], [Sym("uuid"), ROOT], [Sym("paper"), "A3"],
       [Sym("title_block"), [Sym("title"), "Tidal Array 6400 Tidal (C)lock"], [Sym("rev"), "0.1"],
        [Sym("company"), "Project Moon Pi"], [Sym("comment"), 1, "Designed and Created by Project Moon Pi"], [Sym("comment"), 2, "4 ports: Si5351A + 74HCT gates + Raspberry Pi Pico H"]],
       [Sym("lib_symbols")] + list(lib_syms.values())] + items + \
      [[Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]]]
open(OUT, "w").write(sexpr.dump(sch) + "\n")
json.dump({"root": ROOT, "parts": uuids}, open(os.path.join(HERE, "sch_uuids.json"), "w"), indent=1)
print(f"schematic: {len(PARTS)} parts on {OUT}")
