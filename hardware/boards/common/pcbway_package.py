"""PCBWay order packages for the Super Commodore 6400 THROUGH-HOLE boards (the bench-test pair), plus the DigiKey
parts list for building them yourself. Follows ~/CLAUDE CODE PROJECTS/PCBWAY-ORDERS.md (from the Competition Timer's
package script). Every part on these boards is through-hole, so the two versions per board are:

    A_FULL-ASSEMBLY_all-THT   PCBWay makes the board and solders every part (sockets, chips in their sockets). The
                              two plug-in modules (Raspberry Pi Pico H, Adafruit Si5351 board) are NOT on PCBWay's
                              list: they plug into the sockets PCBWay fits; buy them yourself (DigiKey list).
    B_BARE-BOARD_you-solder   PCBWay makes the bare board only; every part comes from DigiKey and you solder it.

The Gerbers are the same for both versions; each folder carries its own copy so it is complete on its own.
Also writes manufacturing/bom/SC6400-THT-bench-set_DigiKey.xlsx + .csv (1 Tidal (C)lock + 2 TLIs + 2 clock cables),
with DigiKey's own part numbers and live stock (moss-dash's DigiKey connector).

    python3 hardware/boards/common/pcbway_package.py          (from the project root; needs openpyxl)
"""
import collections
import csv
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
KC = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
KPY = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3"
OUT = os.path.join(ROOT, "manufacturing", "pcbway")
BOMDIR = os.path.join(ROOT, "manufacturing", "bom")
DIGIKEY = os.path.expanduser("~/CLAUDE CODE PROJECTS/moss-dash/tools/assembly")

COMMON = ["2 layers, 1.6 mm FR-4, 1 oz copper both sides",
          "Solder mask BLUE, silkscreen WHITE (both sides)",
          "Surface finish: HASL lead-free",
          "Min track/space 0.15/0.2 mm, min drill 0.3 mm (vias 0.6 mm)",
          "Vias tented, not filled (no via-in-pad). No fine-pitch parts: 2.54 mm pitch throughout, no mask-bridge "
          "concerns"]

SOCKET14 = ("On Shore Technology", "ED14DT", "14-pin DIP socket")
BOARDS = [
    dict(folder="1_TIDAL-CLOCK-THT", short="TCLK", rel="hardware/boards/tidal-clock-tht/generator/out/tidal-clock-tht.kicad_pcb",
         title="Tidal (C)lock, through-hole edition, rev 0.1 (the master clock, 4 ports)",
         # parts whose footprint is really a socket for a plug-in module: PCBWay fits the socket only
         socket_for={"A1": [("Sullins Connector Solutions", "PPTC201LFBN-RC", 2,
                             "20-way female header: the Pico H's two sockets (pins 1-20, 21-40)")],
                     "M1": [("Sullins Connector Solutions", "PPTC071LFBN-RC", 1,
                             "7-way female header: the Adafruit Si5351 board's socket")]},
         loose=[("A1", "Raspberry Pi", "SC0917", 1, "Raspberry Pi Pico H (headers fitted): plugs into A1's sockets"),
                ("M1", "Adafruit", "2045", 1, "Adafruit Si5351A clock generator board (header fitted, pins down): "
                                              "plugs into M1's socket, chip side up")],
         ic_sockets=["U2", "U3", "U4", "U5", "U6"],
         notes=[]),
    dict(folder="2_TLI-THT", short="TLI", rel="hardware/boards/tidal-link-tht/generator/out/tidal-link-tht.kicad_pcb",
         title="Tidal Link Interface (TLI), through-hole edition, rev 0.1 (one per C64, in its VIC-II socket)",
         socket_for={}, loose=[], ic_sockets=["U1"],
         notes=["J1 (the plug, 40 round pins) is fitted from the BOTTOM: pins point DOWN, soldered on the TOP. Cut "
                "one Mill-Max 350-10-164-00-006000 64-pin strip into two 20-pin strips (one per row). Fit J1 FIRST.",
                "J2 (the VIC-II socket) is two 20-way socket strips on the TOP, one per row, soldered on the bottom, "
                "fitted AFTER J1 (its holes are one row in from J1's, so the two never share a hole).",
                "Keep every lead on the bottom trimmed flush (under 1.5 mm): the board sits about 7 mm above the "
                "C64's motherboard."]),
]
VERSIONS = [("A_FULL-ASSEMBLY_all-THT", "FULL-ASSEMBLY", True),
            ("B_BARE-BOARD_you-solder", "BARE-BOARD", False)]
BENCH = {"TCLK": 1, "TLI": 2}                      # the bench test: one Tidal (C)lock, two C64s
CABLES = [("Amphenol ICC (FCI)", "71600-006LF", 4, "6-way IDC socket (2x3, 2.54 mm), press onto the ribbon: "
           "2 per clock cable, 2 cables"),
          ("3M", "3365/06 300SF", 4, "6-conductor grey ribbon, 1.27 mm pitch, ordered in FEET: two cables, "
           "keep each under 30 cm (clock signals)")]

BOLD = Font(bold=True)
HEAD_FILL = PatternFill("solid", fgColor="DDEBF7")
NOTE_FILL = PatternFill("solid", fgColor="FFF2CC")


def sheet(wb, title, header, rows, widths, first=False, note_col=None):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title[:31]
    ws.append(header)
    for c in ws[1]:
        c.font = BOLD; c.fill = HEAD_FILL; c.alignment = Alignment(vertical="center", wrap_text=True)
    for r in rows:
        ws.append(r)
        if note_col is not None and r[note_col]:
            ws.cell(ws.max_row, note_col + 1).fill = NOTE_FILL
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.freeze_panes = "A2"
    return ws


def clean_mpn(mpn):
    """'310-87-120-41-001101 (x2)' -> ('310-87-120-41-001101', 2, ''); a bracketed remark becomes a note."""
    m = re.match(r"^(\S+)\s*\((x(\d+)|[^)]*)\)\s*$", mpn.strip())
    if not m:
        return mpn.strip(), 1, ""
    if m.group(3):
        return m.group(1), int(m.group(3)), ""
    return m.group(1), 1, m.group(2)


PLAIN = {"61200621621": "6-way box header (2x3, 2.54 mm, shrouded)",
         "JS202011CQN": "DPDT slide switch (INT / EXT clock)",
         "350-10-164-00-006000": "64-pin round-pin header strip: cut into two 20s (the plug)",
         "310-87-120-41-001101": "20-way machined socket strip (two: the VIC-II socket)",
         "5001": "scope test point, black", "5002": "scope test point, white", "5003": "scope test point, orange",
         "5004": "scope test point, yellow"}
CP_NOTE = "Electrolytic: + (long lead) to the + mark"
ASSEMBLY_NOTES = {
    "TCLK": {"C2": CP_NOTE, "C8": CP_NOTE,
             "D1": "LED: short lead (cathode, flat side) in the SQUARE pad, long lead in the round pad",
             "A1": "Sockets: Pico H plugs in with its USB end at the board's left edge"},
    "TLI": {"J1": "Plug pins: fitted from the BOTTOM (pins point down), soldered on top. FIT FIRST.",
            "J2": "Two socket strips on TOP (one per row), soldered on the bottom. Fit after J1.",
            "C2": CP_NOTE},
}


def lines(board, parts, version_full):
    """The parts list as lines: (refs, qty per board, mfr, mpn, value, footprint, note). Modules plugged into
    sockets become their socket; IC sockets get their own line; loose modules are listed only for version B."""
    groups = collections.OrderedDict()
    key = lambda r: (r.rstrip("0123456789"), int("0" + r[len(r.rstrip("0123456789")):]))  # noqa: E731
    for p in sorted(parts, key=lambda p: key(p["ref"])):
        if not p["bom"]:
            continue
        if p["ref"] in board["socket_for"]:
            for mfr, mpn, n, what in board["socket_for"][p["ref"]]:
                g = groups.setdefault((mfr, mpn), dict(refs=[], qty=0, value=what, fp="through-hole", notes=set()))
                g["refs"].append(p["ref"]); g["qty"] += n
                g["notes"].add("Socket only: the module plugs in later (not supplied by PCBWay)")
                note = ASSEMBLY_NOTES[board["short"]].get(p["ref"])
                if note:
                    g["notes"].add(note)
            continue
        mpn, mult, remark = clean_mpn(p["mpn"])
        # the value for R / C / U / D ("33", "100nF", "74HCT14"); the plain description for the rest (test points,
        # headers, switch: their "value" is a net or a label)
        what = p["value"] if p["ref"].rstrip("0123456789") in ("R", "C", "U", "D") else \
            PLAIN.get(mpn, p["desc"][:60])
        g = groups.setdefault((p["mfr"], mpn), dict(refs=[], qty=0, value=what, fp=p["footprint"], notes=set()))
        g["refs"].append(p["ref"]); g["qty"] += mult
        if remark:
            g["notes"].add(remark)
        note = ASSEMBLY_NOTES[board["short"]].get(p["ref"])
        if note:
            g["notes"].add(note)
    if board["ic_sockets"]:
        refs = board["ic_sockets"]
        groups[(SOCKET14[0], SOCKET14[1])] = dict(
            refs=[f"{r} socket" for r in refs], qty=len(refs), value=SOCKET14[2], fp="DIP-14 (300 mil)",
            notes={"Solder the socket; press the IC in afterwards, notch to the notch mark"})
        for (mfr, mpn), g in groups.items():
            if any(r in refs for r in g["refs"]):
                g["notes"].add("IC goes IN a socket (separate line): do not solder the IC")
    out = [(", ".join(g["refs"]), g["qty"], mfr, mpn, g["value"], g["fp"], "; ".join(sorted(g["notes"])))
           for (mfr, mpn), g in groups.items()]
    if not version_full:
        out += [(ref, n, mfr, mpn, what, "plug-in module", "Plugs into the socket") for ref, mfr, mpn, n, what in board["loose"]]
    return out


def main():
    stamp = datetime.date.today().isoformat()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(BOMDIR, exist_ok=True)
    summary, bench = [], collections.OrderedDict()
    for board in BOARDS:
        folder, short = board["folder"], board["short"]
        if os.path.isdir(os.path.join(OUT, folder)):
            shutil.rmtree(os.path.join(OUT, folder))           # (only this script's own folders)
        work = tempfile.mkdtemp(prefix=f"pcbway-{short}-")
        pcb = os.path.join(work, f"{short}.kicad_pcb")
        shutil.copy(os.path.join(ROOT, board["rel"]), pcb)
        pro = os.path.splitext(os.path.join(ROOT, board["rel"]))[0] + ".kicad_pro"
        if os.path.exists(pro):
            shutil.copy(pro, os.path.join(work, f"{short}.kicad_pro"))
        js = os.path.join(work, "parts.json")
        subprocess.run([KPY, os.path.join(HERE, "pcbway_dump.py"), pcb, js], check=True, capture_output=True)
        data = json.load(open(js))
        assert data["layers"] == 2, "this script is for the 2-layer THT boards"
        layers = ["F.Cu", "B.Cu", "F.Silkscreen", "B.Silkscreen", "F.Mask", "B.Mask", "Edge.Cuts"]
        gdir = os.path.join(work, "gerbers")
        os.makedirs(gdir)
        subprocess.run([KC, "pcb", "export", "gerbers", "-o", gdir, "-l", ",".join(layers),
                        "--use-drill-file-origin", "--subtract-soldermask", "--check-zones", pcb],
                       check=True, capture_output=True)
        subprocess.run([KC, "pcb", "export", "drill", "-o", gdir + "/", "--format", "excellon", "--drill-origin", "plot",
                        "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", pcb],
                       check=True, capture_output=True)
        gzip_name = f"{short}-THT_GERBERS_{stamp}.zip"
        gzip_path = os.path.join(work, gzip_name)
        with zipfile.ZipFile(gzip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for fn in sorted(os.listdir(gdir)):
                z.write(os.path.join(gdir, fn), fn)
        gfiles = sorted(os.listdir(gdir))
        parts = data["parts"]
        loose_refs = {r for r, *_ in board["loose"]}

        for vdir, vtag, full in VERSIONS:
            d = os.path.join(OUT, folder, f"{short}-THT_{vdir}")
            os.makedirs(d)
            shutil.copy(gzip_path, os.path.join(d, gzip_name))
            rows = lines(board, parts, full)
            header = ["Item #", "Designator", "Qty", "Manufacturer", "Mfg Part #", "Description / Value",
                      "Package / Footprint", "Type", "Your Instructions / Notes"]
            body = [[i, r[0], r[1], r[2], r[3], r[4], r[5], "THT", r[6]] for i, r in enumerate(rows, 1)]
            if full:
                wb = Workbook()
                sheet(wb, "BOM FULL ASSEMBLY", header, body, [7, 34, 5, 22, 26, 34, 34, 7, 60], first=True, note_col=8)
                wb.save(os.path.join(d, f"{short}-THT_BOM_FULL-ASSEMBLY.xlsx"))
                wb = Workbook()
                cpl = [[p["ref"], p["x"], p["y"], p["side"], p["rot"], "THT"]
                       for p in sorted(parts, key=lambda p: p["ref"]) if p["pos"]]
                sheet(wb, "CPL FULL ASSEMBLY", ["Designator", "Mid X (mm)", "Mid Y (mm)", "Layer", "Rotation", "Type"],
                      cpl, [12, 12, 12, 9, 10, 8], first=True)
                wb.save(os.path.join(d, f"{short}-THT_CPL_FULL-ASSEMBLY.xlsx"))
            else:
                wb = Workbook()
                sheet(wb, "Parts you solder", header, body, [7, 34, 5, 22, 26, 34, 34, 7, 60], first=True, note_col=8)
                wb.save(os.path.join(d, f"{short}-THT_PARTS-YOU-SOLDER_buy-from-DigiKey.xlsx"))
            n_parts = sum(r[1] for r in rows)
            label = ("FULL ASSEMBLY: PCBWay makes the board and solders every part" if full else
                     "BARE BOARD ONLY: PCBWay makes the board; you solder the parts")
            with open(os.path.join(d, "READ ME FIRST.txt"), "w") as fh:
                fh.write(f"{short}-THT  -  {board['title']}\n{label}\n{'=' * 78}\n\n")
                if full:
                    fh.write("Upload to PCBWay (PCB Assembly quote, THROUGH-HOLE assembly):\n"
                             f"  Gerber file:      {gzip_name}\n"
                             f"  BOM:              {short}-THT_BOM_FULL-ASSEMBLY.xlsx\n"
                             f"  Centroid / CPL:   {short}-THT_CPL_FULL-ASSEMBLY.xlsx\n\n")
                else:
                    fh.write("Upload to PCBWay (standard PCB quote, no assembly):\n"
                             f"  Gerber file:      {gzip_name}\n\n")
                fh.write("Order form (2 layers, no layer pop-up):\n"
                         f"  Board size:       {data['size'][0]} x {data['size'][1]} mm\n"
                         + "".join(f"  {n}\n" for n in COMMON))
                if full:
                    fh.write(f"  Assembly:         top side only, 0 SMD parts, {n_parts} through-hole parts "
                             f"({len(rows)} BOM lines)\n")
                    if board["loose"]:
                        fh.write("  NOT for PCBWay:   " + "; ".join(f"{m} {p} ({w.split(':')[0]})" for _, m, p, _, w in
                                                                     board["loose"])
                                 + ": they plug into the sockets PCBWay fits. Buy them yourself (DigiKey list).\n")
                fh.write("\n" + "".join(f"Assembly note: {n}\n" for n in board["notes"]))
                fh.write("\nPlacement file: mm from the board's bottom-left corner (the same origin as the Gerbers and "
                         "drill files), Y up.\n" if full else "")
                fh.write(f"\nGerber zip holds: {', '.join(gfiles)}\n\nBuilt {stamp} by "
                         "hardware/boards/common/pcbway_package.py\nDesigned and Created by Project Moon Pi\n")
        # the bench set: every part (version B's list) times the number of boards
        for refs, qty, mfr, mpn, value, fp, note in lines(board, parts, False):
            k = (mfr, mpn)
            e = bench.setdefault(k, dict(qty=0, value=value, used=[]))
            e["qty"] += qty * BENCH[short]
            e["used"].append(f"{short}: {refs}")
        summary.append(f"{short}-THT: {data['size'][0]} x {data['size'][1]} mm, {data['layers']} layers, "
                       f"{len([p for p in parts if p['bom']])} parts on the board, {len(gfiles)} Gerber/drill files")
        shutil.rmtree(work)
    for mfr, mpn, qty, what in CABLES:
        bench[(mfr, mpn)] = dict(qty=qty, value=what, used=["clock cables"])

    # ---- DigiKey: their part numbers, stock and price for the bench set
    sys.path.insert(0, DIGIKEY)
    import digikey as dk                                       # noqa: E402
    tok = dk.app_token()
    rows, csv_rows, total, short_list = [], [], 0.0, []
    for i, ((mfr, mpn), e) in enumerate(bench.items(), 1):
        p = dk.find(tok, mpn, mfr)
        time.sleep(0.4)
        have = (p or {}).get("QuantityAvailable") or 0
        price = (p or {}).get("UnitPrice") or 0
        dkn = dk.dk_number(p, e["qty"]) if p else None
        line_total = round(price * e["qty"], 2)
        total += line_total
        if not p or have < e["qty"]:
            short_list.append(f"{mfr} {mpn}")
        rows.append([i, mfr, mpn, dkn or "(none found)", e["qty"], e["value"], "; ".join(e["used"]), have, price,
                     line_total])
        csv_rows.append([dkn or "", mpn, mfr, e["qty"], f"SC6400 THT bench: {'; '.join(e['used'])}"[:60]])
    wb = Workbook()
    ws = sheet(wb, "Bench set (1 clock, 2 TLI)",
               ["Item #", "Manufacturer", "Mfg Part #", "DigiKey #", "Qty", "What", "Where it goes", "DigiKey stock",
                "Unit $ (1 pc)", "Line $"],
               rows, [7, 24, 24, 24, 6, 50, 50, 12, 11, 10], first=True)
    ws.append([]); ws.append(["", "", "", "", "", "", "", "", "Total $", round(total, 2)])
    ws.cell(ws.max_row, 9).font = BOLD; ws.cell(ws.max_row, 10).font = BOLD
    base = os.path.join(BOMDIR, "SC6400-THT-bench-set_DigiKey")
    wb.save(base + ".xlsx")
    with open(base + ".csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Digi-Key Part Number", "Manufacturer Part Number", "Manufacturer", "Quantity", "Customer Reference"])
        w.writerows(csv_rows)
    print("\n".join(summary))
    print(f"DigiKey bench set: {len(rows)} lines, about ${total:.2f} at single-piece prices"
          + (f"; SHORT or not found: {', '.join(short_list)}" if short_list else "; everything in stock"))
    print("packages:", OUT, "\nparts list:", base + ".xlsx / .csv")


if __name__ == "__main__":
    sys.exit(main())
