#!/usr/bin/env python3
"""Build Guide 1: the two-core user-port link cable.  -> docs/guides/SC6400-Guide-1-Link-Cable.pdf

Every diagram is drawn here (reportlab), so the guide stays in step with the wiring in src/common.asm.
Designed and Created by Project Moon Pi.
"""
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "guides" / "SC6400-Guide-1-Link-Cable.pdf"
LOGO = ROOT / "docs" / "img" / "project-moon-pi-logo.png"
IMG = ROOT / "docs" / "img"

W, H = letter
M = 54                                      # margin
NAVY = HexColor("#16244a")
ACCENT = HexColor("#c8102e")
SOFT = HexColor("#eef2fa")
GREY = HexColor("#8a8f99")
LIGHT = HexColor("#d9dde5")
OK = HexColor("#1b7f3b")

# wire colours (12-way rainbow ribbon order)
WIRE = {
    "brown": HexColor("#7a4a1e"), "red": HexColor("#d22b2b"), "orange": HexColor("#f08a1c"),
    "yellow": HexColor("#f2d21b"), "green": HexColor("#2e9e44"), "blue": HexColor("#2f62d0"),
    "violet": HexColor("#8a3fc0"), "grey": HexColor("#9a9a9a"), "white": HexColor("#ffffff"),
    "black": HexColor("#111111"),
}
DATA = [("PB0", "C", "brown"), ("PB1", "D", "red"), ("PB2", "E", "orange"), ("PB3", "F", "yellow"),
        ("PB4", "H", "green"), ("PB5", "J", "blue"), ("PB6", "K", "violet"), ("PB7", "L", "grey")]
TOP = [str(i) for i in range(1, 13)]
BOT = list("ABCDEFHJKLMN")
PIN_NAME = {"1": "GND", "2": "+5V", "3": "RESET", "4": "CNT1", "5": "SP1", "6": "CNT2", "7": "SP2", "8": "PC2",
            "9": "ATN", "10": "9VAC", "11": "9VAC", "12": "GND", "A": "GND", "B": "FLAG", "C": "PB0",
            "D": "PB1", "E": "PB2", "F": "PB3", "H": "PB4", "J": "PB5", "K": "PB6", "L": "PB7", "M": "PA2",
            "N": "GND"}
NEVER = {"2", "3", "10", "11"}


class Guide:
    def __init__(self):
        OUT.parent.mkdir(parents=True, exist_ok=True)
        self.c = canvas.Canvas(str(OUT), pagesize=letter)
        self.c.setTitle("Super Commodore 6400 - Build Guide 1: the user-port link cable")
        self.c.setAuthor("Project Moon Pi")
        self.page = 0

    # ---- page furniture -------------------------------------------------------------------
    def new_page(self, title, step=None):
        if self.page:
            if self.page > 1:                   # (no footer on the cover)
                self.footer()
            self.c.showPage()
        self.page += 1
        c = self.c
        c.setFillColor(NAVY)
        c.rect(0, H - 64, W, 64, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(M, H - 42, title)
        if step:
            c.setFont("Helvetica", 10)
            c.drawRightString(W - M, H - 40, step)
        self.y = H - 92

    def footer(self):
        c = self.c
        c.setFont("Helvetica", 8)
        c.setFillColor(GREY)
        c.drawString(M, 30, "Super Commodore 6400 - Build Guide 1: the user-port link cable")
        c.drawRightString(W - M, 30, f"Designed and Created by Project Moon Pi   -   page {self.page}")

    def para(self, text, size=10.5, lead=14, width=None, x=None, color=black, font="Helvetica", gap=6):
        """Simple word-wrapped paragraph; **bold** runs are allowed."""
        c = self.c
        x = M if x is None else x
        width = (W - 2 * M) if width is None else width
        words = []
        bold = False
        for i, part in enumerate(text.split("**")):
            for w in part.split():
                words.append((w, bold))
            bold = not bold
        line, lw = [], 0
        def flush():
            nonlocal line, lw
            cx = x
            for w, b in line:
                f = font + "-Bold" if b and font == "Helvetica" else font
                c.setFont(f, size)
                c.setFillColor(color)
                c.drawString(cx, self.y, w)
                cx += c.stringWidth(w + " ", f, size)
            self.y -= lead
            line, lw = [], 0
        for w, b in words:
            f = "Helvetica-Bold" if b else font
            ww = c.stringWidth(w + " ", f, size)
            if lw + ww > width and line:
                flush()
            line.append((w, b))
            lw += ww
        if line:
            flush()
        self.y -= gap

    def heading(self, text, size=13):
        self.c.setFont("Helvetica-Bold", size)
        self.c.setFillColor(NAVY)
        self.c.drawString(M, self.y, text)
        self.y -= size + 6

    def bullets(self, items, size=10.5, indent=14):
        for it in items:
            self.c.setFillColor(ACCENT)
            self.c.circle(M + 4, self.y + 3.5, 2, stroke=0, fill=1)
            self.para(it, size=size, x=M + indent, width=W - 2 * M - indent, gap=2)
        self.y -= 4

    def box(self, x, y, w, h, fill=SOFT, stroke=LIGHT):
        self.c.setFillColor(fill)
        self.c.setStrokeColor(stroke)
        self.c.roundRect(x, y, w, h, 8, stroke=1, fill=1)

    def note(self, text, color=ACCENT, title="Important"):
        c = self.c
        lines = max(2, len(text) // 95 + 2)
        h = 18 + lines * 13
        self.box(M, self.y - h + 10, W - 2 * M, h, fill=HexColor("#fff4f4") if color == ACCENT else SOFT,
                 stroke=color)
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(M + 12, self.y - 6, title)
        self.y -= 22
        self.para(text, x=M + 12, width=W - 2 * M - 24, size=10, lead=13)
        self.y -= 8

    def image(self, path, x, y, w):
        im = ImageReader(str(path))
        iw, ih = im.getSize()
        h = w * ih / iw
        self.c.drawImage(im, x, y - h, w, h)
        self.c.setStrokeColor(LIGHT)
        self.c.rect(x, y - h, w, h, stroke=1, fill=0)
        return h

    # ---- drawings ---------------------------------------------------------------------------
    def wire_swatch(self, x, y, colour, w=26, h=9, label=None):
        c = self.c
        c.setFillColor(WIRE[colour])
        c.setStrokeColor(black)
        c.setLineWidth(0.6)
        c.roundRect(x, y, w, h, 3, stroke=1, fill=1)
        if label:
            c.setFont("Helvetica-Bold", 6.5)
            c.setFillColor(white if colour in ("brown", "red", "blue", "violet", "black", "green") else black)
            c.drawCentredString(x + w / 2, y + 2.3, label)

    def connector(self, x, y, pitch=34, colour_of=None, title=None, show_names=True, highlight=None):
        """Solder-side view of the 24-way connector: top row 1-12, bottom row A-N, pin 1 top left."""
        c = self.c
        w = pitch * 12 + 16
        c.setFillColor(HexColor("#2b2b2b"))
        c.setStrokeColor(black)
        c.roundRect(x, y, w, 74, 6, stroke=1, fill=1)
        for row, pins, yy in ((0, TOP, y + 50), (1, BOT, y + 22)):
            for i, p in enumerate(pins):
                cx = x + 8 + pitch * i + pitch / 2
                col = None
                if colour_of:
                    col = colour_of.get(p)
                if p in NEVER:
                    c.setFillColor(HexColor("#5a1010"))
                elif col:
                    c.setFillColor(WIRE[col] if col in WIRE else col)
                else:
                    c.setFillColor(HexColor("#c9a43b"))
                c.setStrokeColor(white if col == "black" else black)
                c.setLineWidth(0.8)
                c.circle(cx, yy, 8.5, stroke=1, fill=1)
                c.setFont("Helvetica-Bold", 8)
                light = col in ("yellow", "white", "orange", "grey") or (not col and p not in NEVER)
                c.setFillColor(black if light else white)
                c.drawCentredString(cx, yy - 3, p)
                if show_names:
                    c.setFont("Helvetica", 6.5)
                    c.setFillColor(NAVY if p not in NEVER else ACCENT)
                    if row == 0:
                        c.drawCentredString(cx, y + 80, PIN_NAME[p])
                    else:
                        c.drawCentredString(cx, y - 10, PIN_NAME[p])
        if title:
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(NAVY)
            c.drawString(x, y + 94, title)
        return w

    def resistor(self, x, y, w=46):
        c = self.c
        c.setFillColor(HexColor("#d9c9a3"))
        c.setStrokeColor(black)
        c.roundRect(x, y - 6, w, 12, 5, stroke=1, fill=1)
        for i, col in enumerate(("#f08a1c", "#f08a1c", "#7a4a1e", "#c9a43b")):   # 330 ohm: orange orange brown gold
            c.setFillColor(HexColor(col))
            c.rect(x + 9 + i * 8 + (6 if i == 3 else 0), y - 6, 4, 12, stroke=0, fill=1)


def build():
    g = Guide()
    c = g.c

    # ======== 1. cover ========
    g.page = 1
    c.setFillColor(black)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.drawImage(ImageReader(str(LOGO)), W / 2 - 110, H - 300, 220, 220, mask="auto")
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(W / 2, H - 350, "SUPER COMMODORE 6400")
    c.setFont("Helvetica", 16)
    c.drawCentredString(W / 2, H - 380, "Build Guide 1")
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(W / 2, H - 420, "The User-Port Link Cable")
    c.setFont("Helvetica", 12.5)
    c.drawCentredString(W / 2, H - 448, "Two Commodore 64s, one cable, twice the computing power")
    # a little picture of the result
    for i, (x0, col) in enumerate(((W / 2 - 190, "#2f62d0"), (W / 2 + 40, "#d22b2b"))):
        c.setFillColor(HexColor("#233366"))
        c.roundRect(x0, 150, 150, 92, 8, stroke=0, fill=1)
        c.setFillColor(HexColor(col))
        c.rect(x0 + 14, 170, 122, 56, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x0 + 75, 132, "LEADER (core 0)" if i == 0 else "CORE 1")
    c.setStrokeColor(HexColor("#f2d21b"))
    c.setLineWidth(4)
    c.bezier(W / 2 - 40, 196, W / 2 - 10, 230, W / 2 + 10, 160, W / 2 + 40, 196)
    c.setFillColor(HexColor("#aab6d6"))
    c.setFont("Helvetica", 10)
    c.drawCentredString(W / 2, 92, "Version 0.1  -  for software release 0.1.0  -  NTSC Commodore 64")
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(W / 2, 64, "Designed and Created by Project Moon Pi")

    # ======== 2. goals ========
    g.new_page("Your goals", "Start here")
    g.heading("Where you start")
    g.bullets([
        "**Two NTSC Commodore 64s** that work, any board revision, each with a power supply and a monitor or TV.",
        "**A way to load programs on each one:** a 1541 or SD2IEC with the disk sc6400.d64, a Kung Fu Flash with "
        "the .prg or .crt files, or the cartridge images burned to EPROM cartridges.",
        "**The parts on page 3.** About $25 for the cable, plus tools you probably already have.",
    ])
    g.heading("Where you finish")
    g.bullets([
        "A **finished, tested link cable** that joins the two C64s through their user ports.",
        "The leader C64 shows **CORES 2**. The benchmark runs on one core in about **60 seconds**, and on two cores "
        "in about **31 seconds**: a speed-up of about **1.95 times**, shown on screen.",
        "You can watch the two machines share the work. The leader's tiles are blue; core 1's are red, orange and "
        "yellow.",
    ])
    g.heading("Time and skill")
    g.para("About 2 hours. You need basic soldering: wires onto solder eyelets, and resistors in line with wires. "
           "No board building, and no changes to the C64s.")
    g.heading("Where this step fits")
    # roadmap strip
    steps = [("1", "Two C64s on a\nuser-port cable", True), ("2", "Clock-injection\nbench test", False),
             ("3", "Cartridge pod +\n2-port hub", False), ("4", "8-port hub,\n8 cores, video wall", False)]
    bw, gap, y0 = 112, 14, g.y - 70
    for i, (n, t, on) in enumerate(steps):
        x0 = M + i * (bw + gap)
        g.box(x0, y0, bw, 64, fill=NAVY if on else SOFT, stroke=NAVY)
        c.setFillColor(white if on else NAVY)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(x0 + 10, y0 + 40, n)
        c.setFont("Helvetica-Bold" if on else "Helvetica", 9.5)
        for k, ln in enumerate(t.split("\n")):
            c.drawString(x0 + 30, y0 + 44 - k * 12, ln)
        if on:
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(HexColor("#f2d21b"))
            c.drawString(x0 + 10, y0 + 8, "THIS GUIDE")
        if i < 3:
            c.setStrokeColor(NAVY)
            c.setLineWidth(2)
            c.line(x0 + bw + 2, y0 + 32, x0 + bw + gap - 2, y0 + 32)
    g.y = y0 - 22
    g.para("The finished Super Commodore 6400 joins **8 or more C64s** through a shared-memory hub on their cartridge "
           "ports, all running from one clock. This cable is the first step. It proves the software, the protocol "
           "and the speed-up on real machines, using parts you can buy today.")
    g.note("This cable carries signals only, no power. Only ever plug it in or unplug it with BOTH computers "
           "switched off.", title="Safety")

    # ======== 3. parts and tools ========
    g.new_page("Parts and tools", "Page 3")
    g.heading("Parts")
    rows = [
        ("2", "24-way card-edge connector, 0.156\" pitch, solder eyelets, free-hanging, for a 0.062\" (1.6 mm) "
              "board edge", "EDAC 355-024-500-201 (DigiKey). Alternative: EDAC 307-024-500-202 (with mounting "
              "ears) or Sullins EBM12DRXH"),
        ("0.6 m", "12-conductor rainbow ribbon cable, 28 AWG, 0.05\" pitch (brown, red, orange, yellow, green, blue, "
                  "violet, grey, white, black, brown, red)", "3M 3302/12, or any 12-wire colour-coded ribbon. "
                  "Or 11 lengths of 24 AWG stranded hook-up wire."),
        ("8", "Resistor 330 ohm, 1/4 W, 5% (bands: orange orange brown gold)", "Stackpole CF14JT330R (DigiKey)"),
        ("30 cm", "Heat-shrink tubing 1/8\" (3 mm), black", "Alpha Wire F221B1/8 BK100 (DigiKey)"),
        ("10 cm", "Heat-shrink tubing 1/2\" (13 mm), black, for the cable ends", "Alpha Wire F221B1/2 BK210 "
                  "(DigiKey)"),
        ("15 cm", "Bare tinned copper wire, about 22 AWG, for the ground links", "Any. A cut-off resistor lead "
                  "also works."),
        ("1", "Paint pen or nail polish, white or yellow", "To mark pin 1 on each connector"),
    ]
    y = g.y
    c.setFillColor(NAVY)
    c.rect(M, y - 4, W - 2 * M, 18, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(M + 6, y + 1, "Qty")
    c.drawString(M + 50, y + 1, "Part")
    c.drawString(M + 300, y + 1, "Part number / where")
    y -= 20
    for i, (q, part, pn) in enumerate(rows):
        g.y = y
        top = y
        g.para(part, size=9.5, lead=12, x=M + 50, width=240, gap=0)
        y1 = g.y
        g.y = top
        g.para(pn, size=9.5, lead=12, x=M + 300, width=W - 2 * M - 306, gap=0, color=NAVY)
        y2 = g.y
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(black)
        c.drawString(M + 6, top, q)
        y = min(y1, y2) - 6
        c.setStrokeColor(LIGHT)
        c.line(M, y + 8, W - M, y + 8)
    g.y = y - 8
    g.heading("Tools")
    g.bullets([
        "Soldering iron (fine tip) and solder; a heat gun or lighter for the heat-shrink.",
        "Wire strippers for 28 AWG, and side cutters.",
        "**A digital multimeter (DMM).** Any handheld one will do if it has these three settings: **DC volts** "
        "(marked V with a straight line, or VDC), **resistance** (marked ohm or with the omega sign) and "
        "**continuity** (the beeper, usually marked with a sound-wave symbol). You use it to find pin 1 on your C64, "
        "and to test the cable before it ever touches a computer. You don't need an oscilloscope, a logic probe or a "
        "clamp meter for this build.",
        "Masking tape and a pen, to label the ends A and B.",
    ])
    g.note("The connectors have no key, so they can go on upside down. That's why page 4 shows you how to find "
           "pin 1 on your C64 with the digital multimeter, and why you mark pin 1 on each connector before soldering.",
           color=NAVY, title="Why the paint pen and the digital multimeter matter")

    # ======== 4. know the user port ========
    g.new_page("Know the user port", "Page 4")
    g.para("The user port is the wide edge connector on the back of the C64. It has 12 contacts on top "
           "(**1 to 12**) and 12 underneath (**A to N**; there is no G or I). The cable uses only these:")
    g.bullets([
        "**C, D, E, F, H, J, K, L:** the 8 data lines (PB0 to PB7).",
        "**8 (PC2)** and **B (FLAG)**: the handshake. Each machine's PC2 goes to the other's FLAG.",
        "**1, 12, A, N:** ground.",
    ])
    colour_of = {p: col for _, p, col in DATA}
    colour_of.update({"8": HexColor("#ffffff"), "B": HexColor("#ffffff"), "1": "black", "12": "black",
                      "A": "black", "N": "black"})
    g.connector(M + 18, g.y - 150, colour_of=colour_of,
                title="The C64 user port, seen from behind the computer (pin 1 top left)")
    g.y -= 190
    # legend
    lx = M + 18
    for label, col in (("used: data", "#c9a43b"), ("used: handshake", "#ffffff"), ("ground", "#111111"),
                       ("NEVER connect", "#5a1010"), ("not used", "#c9a43b")):
        pass
    c.setFont("Helvetica", 9)
    items = [("Data (coloured as the wire that goes there)", WIRE["green"]), ("Handshake: 8 and B", white),
             ("Ground", WIRE["black"]), ("NEVER connect: +5 V, RESET, 9 V AC", HexColor("#5a1010")),
             ("Not used (gold)", HexColor("#c9a43b"))]
    for i, (t, col) in enumerate(items):
        x0 = lx + (i % 2) * 250
        y0 = g.y - (i // 2) * 16
        c.setFillColor(col)
        c.setStrokeColor(black)
        c.circle(x0 + 5, y0 + 3, 5, stroke=1, fill=1)
        c.setFillColor(black)
        c.drawString(x0 + 16, y0, t)
    g.y -= 58
    g.heading("Find pin 1 on YOUR C64 (do this once per computer)")
    g.para("Diagrams are easy to read backwards, so let the computer tell you. Switch the C64 **on**, with nothing "
           "plugged into the user port. Set the **digital multimeter to DC volts** (the 20 V range, if it doesn't choose "
           "the range itself). Black lead in the **COM** socket, red lead in the **V** socket.")
    g.bullets([
        "Put the black probe on the **top contact at the left end** (pin 1, ground).",
        "Touch the red probe to the **next top contact** (pin 2). It reads **+5 V**: you have found pin 1. Stop here.",
        "If it reads 0 V, try the same at the **right end**. If +5 V is there, the numbering on your C64 runs from "
        "the right. Mark that end as pin 1 instead.",
        "Never short pin 2 (+5 V) to anything, and keep probes away from pins 10 and 11 (9 V AC).",
    ])
    g.note("Mark pin 1 on the C64's case with the paint pen, and mark the pin 1 end of each connector the same "
           "way. Then the connector can only go on one way: paint dot to paint dot, top to top.",
           color=NAVY, title="Mark it")

    # ======== 5. wiring diagram ========
    g.new_page("The wiring diagram", "Page 5")
    g.para("Each wire runs from end A to end B. The 8 data lines go straight through, each with a 330 ohm "
           "resistor at end A. The two handshake wires **cross**: pin 8 at one end goes to pin B at the other. "
           "Ground pins 1, 12, A and N are linked together at each end, and one black wire joins the two ends.")
    top = g.y - 10
    xa, xb = M + 70, W - M - 70
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(NAVY)
    c.drawCentredString(xa, top, "END A")
    c.drawCentredString(xb, top, "END B")
    rows = [(f"{n}  pin {p}", f"pin {p}  {n}", col, p, p) for n, p, col in DATA]
    y = top - 26
    rh = 30
    for i, (la, lb, col, pa, pb) in enumerate(rows):
        yy = y - i * rh
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(black)
        c.drawRightString(xa + 8, yy - 3, la)
        c.drawString(xb - 8, yy - 3, lb)
        c.setStrokeColor(black)
        c.setLineWidth(5.6)
        c.line(xa + 16, yy, xb - 16, yy)
        c.setStrokeColor(WIRE[col])
        c.setLineWidth(4)
        c.line(xa + 16, yy, xb - 16, yy)
        g.resistor(xa + 40, yy)
        c.setFont("Helvetica", 8)
        c.setFillColor(NAVY)
        c.drawString(xa + 140, yy + 6, f"wire {i + 1}: {col}")
    # handshake crossing
    yh1 = y - 8 * rh - 6
    yh2 = yh1 - 34
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(black)
    c.drawRightString(xa + 8, yh1 - 3, "PC2  pin 8")
    c.drawRightString(xa + 8, yh2 - 3, "FLAG  pin B")
    c.drawString(xb - 8, yh1 - 3, "pin 8  PC2")
    c.drawString(xb - 8, yh2 - 3, "pin B  FLAG")
    for (y1, y2, col, lab) in ((yh1, yh2, "white", "wire 9: white"), (yh2, yh1, "brown", "wire 11: the 2nd brown")):
        c.setStrokeColor(black)
        c.setLineWidth(5.6)
        c.line(xa + 16, y1, xb - 16, y2)
        c.setStrokeColor(WIRE[col])
        c.setLineWidth(4)
        c.line(xa + 16, y1, xb - 16, y2)
        c.setFont("Helvetica", 8)
        c.setFillColor(NAVY)
        c.drawString(xa + 60, y1 + (6 if y1 > y2 else -12), lab)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(ACCENT)
    c.drawCentredString(W / 2, yh2 - 26, "The handshake wires CROSS: pin 8 at one end goes to pin B at the other end, both ways.")
    # ground
    yg = yh2 - 58
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(black)
    c.drawRightString(xa + 8, yg - 3, "GND  1, 12, A, N")
    c.drawString(xb - 8, yg - 3, "1, 12, A, N  GND")
    c.setStrokeColor(HexColor("#555555"))
    c.setLineWidth(5.6)
    c.line(xa + 16, yg, xb - 16, yg)
    c.setStrokeColor(WIRE["black"])
    c.setLineWidth(4)
    c.line(xa + 16, yg, xb - 16, yg)
    c.setFont("Helvetica", 8)
    c.setFillColor(NAVY)
    c.drawString(xa + 140, yg + 6, "wire 10: black")
    c.setFont("Helvetica", 9)
    c.setFillColor(GREY)
    c.drawString(xa + 140, yg - 22, "wire 12 (the 2nd red) is not used: cut it off flush at both ends.")
    g.y = yg - 48
    g.note("Pins 2 (+5 V), 3 (RESET), 10 and 11 (9 V AC) must never be connected. They have no wire, and "
           "nothing may touch them. Pins 4, 5, 6, 7, 9 and M are not used either.", title="Never connect")

    # ======== 6. solder maps ========
    g.new_page("Solder maps: which wire goes where", "Page 6")
    g.para("These show the back of each connector, the solder eyelets, held the way it plugs onto the C64: "
           "**paint dot (pin 1) at the top left**, cable running away from the computer. The two ends differ only "
           "at pins 8 and B.")
    base = {p: col for _, p, col in DATA}
    base.update({"1": "black", "12": "black", "A": "black", "N": "black"})
    ea = dict(base); ea["8"] = "white"; ea["B"] = "brown"
    eb = dict(base); eb["8"] = "brown"; eb["B"] = "white"
    g.connector(M + 18, g.y - 135, colour_of=ea, title="END A  (with the 8 resistors)")
    g.y -= 160
    g.para("End A: **pin 8 = white** (wire 9), **pin B = the 2nd brown** (wire 11). Pins C to L each go through a "
           "330 ohm resistor. Black to pin A.", size=10, x=M + 18, width=W - 2 * M - 18)
    g.y -= 14
    g.connector(M + 18, g.y - 135, colour_of=eb, title="END B")
    g.y -= 160
    g.para("End B: **pin 8 = the 2nd brown** (wire 11), **pin B = white** (wire 9). Pins C to L are wired "
           "straight, with no resistors. Black to pin A.", size=10, x=M + 18, width=W - 2 * M - 18)
    g.y -= 10
    g.heading("Ground links (both ends)")
    g.para("Join pins **1 and 12** (both ends of the top row) and **A and N** (both ends of the bottom row) with "
           "bare wire, and join the two rows at one end with a short link from 1 to A. Solder the black wire to pin "
           "A. Keep the bare links clear of the eyelets they pass over: slide 1/8\" heat-shrink over them.")

    # ======== 7. build steps ========
    g.new_page("Build it, step by step", "Page 7")
    steps = [
        ("Cut and prepare the cable",
         "Cut 60 cm of the 12-way ribbon. At each end, split the wires apart for 5 cm and strip 3 mm of each. Cut wire "
         "12 (the 2nd red) off flush at both ends. Put a tape flag on each end: **A** and **B**."),
        ("Mark the connectors",
         "Put a paint dot next to the pin 1 eyelet of each connector, so it shows from the solder side. Slide the "
         "1/2\" heat-shrink onto the cable now, one piece for each end, before you solder anything."),
        ("End A: resistors on the data pins",
         "Bend one lead of each 330 ohm resistor into a hook and solder it to eyelets **C, D, E, F, H, J, K, L**. Cut "
         "the free leads to 8 mm. Slide a 2 cm piece of 1/8\" heat-shrink onto each data wire, solder the wire to the "
         "free lead (brown to C's resistor, red to D's, and so on), then shrink the tubing over the joint."),
        ("End A: handshake and ground",
         "Solder **white to pin 8**, and **the 2nd brown to pin B**. Add the ground links (page 6), then solder black "
         "to pin A."),
        ("End B",
         "The same, but **without resistors**: the data wires go straight onto C to L. Here **the 2nd brown goes to "
         "pin 8**, and **white to pin B**. Add the ground links, and black to pin A."),
        ("Finish",
         "Check every joint is shiny, and that no strand bridges two eyelets. Slide the 1/2\" heat-shrink over the "
         "back of each connector and shrink it, to hold the wires and stop them pulling on the joints."),
    ]
    for i, (t, body) in enumerate(steps, 1):
        c.setFillColor(NAVY)
        c.circle(M + 12, g.y + 3, 12, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(M + 12, g.y - 1, str(i))
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(M + 32, g.y, t)
        g.y -= 16
        g.para(body, x=M + 32, width=W - 2 * M - 32, size=10.2, lead=13.5)
        if i == 3:                                   # the in-line resistor joint
            y0 = g.y - 18
            x0 = M + 60
            c.setFillColor(HexColor("#c9a43b"))
            c.circle(x0, y0, 8, stroke=1, fill=1)
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(black)
            c.drawCentredString(x0, y0 - 2.5, "C")
            c.setStrokeColor(HexColor("#888888"))
            c.setLineWidth(1.5)
            c.line(x0 + 8, y0, x0 + 30, y0)
            g.resistor(x0 + 30, y0)
            c.line(x0 + 76, y0, x0 + 100, y0)
            c.setFillColor(HexColor("#333333"))
            c.roundRect(x0 + 86, y0 - 5, 40, 10, 3, stroke=0, fill=1)
            c.setStrokeColor(black)
            c.setLineWidth(5)
            c.line(x0 + 126, y0, x0 + 230, y0)
            c.setStrokeColor(WIRE["brown"])
            c.setLineWidth(3.6)
            c.line(x0 + 126, y0, x0 + 230, y0)
            c.setFont("Helvetica", 8)
            c.setFillColor(NAVY)
            c.drawString(x0 - 6, y0 - 20, "eyelet")
            c.drawString(x0 + 34, y0 - 20, "330 ohm")
            c.drawString(x0 + 84, y0 - 20, "heat-shrink")
            c.drawString(x0 + 150, y0 - 20, "brown wire (PB0) to end B")
            g.y = y0 - 36

    # ======== 8. test before plugging in ========
    g.new_page("Test before it touches a computer", "Page 8")
    g.para("Use the **digital multimeter** on the cable alone, with nothing plugged in: black lead in **COM**, red "
           "lead in the **V / ohm** socket. Each check below names the setting to use. Tick each line. **Every line must pass "
           "before you plug the cable into a C64.**")
    tests = [(f"A-{p}  to  B-{p}  ({n})", "RESISTANCE (2k range): 310 to 350 ohm") for n, p, _ in DATA]
    tests += [("A-8  to  B-B   (PC2 to FLAG)", "CONTINUITY: beeps"), ("A-B  to  B-8   (FLAG to PC2)", "CONTINUITY: beeps"),
              ("A-1  to  B-1   (ground)", "CONTINUITY: beeps"), ("A-1 to A-12 to A-A to A-N, same at B", "CONTINUITY: beeps")]
    g.heading("Connections that must be there")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(GREY)
    c.drawString(M + 18, g.y + 2, "CHECK")
    c.drawString(M + 300, g.y + 2, "DMM SETTING: WHAT YOU SHOULD SEE")
    g.y -= 16
    y = g.y
    for t, want in tests:
        c.setStrokeColor(NAVY)
        c.rect(M, y - 2, 10, 10, stroke=1, fill=0)
        c.setFont("Helvetica", 10)
        c.setFillColor(black)
        c.drawString(M + 18, y, t)
        c.setFillColor(OK)
        c.drawString(M + 300, y, want)
        y -= 16
    g.y = y - 8
    g.heading("Connections that must NOT be there (DMM on CONTINUITY: no beep)")
    no = [
        "Each data pin to its neighbours, at both ends: C-D, D-E, E-F, F-H, H-J, J-K, K-L.",
        "Any data pin to ground (pin A).",
        "Pin 8 to pin B at the same end (they must only join across the cable).",
        "Pins 2, 3, 10 and 11 to anything at all.",
    ]
    for t in no:
        c.setStrokeColor(NAVY)
        c.rect(M, g.y - 2, 10, 10, stroke=1, fill=0)
        g.para(t, x=M + 18, width=W - 2 * M - 18, gap=3)
    g.note("On RESISTANCE, a data line reads about 330 ohm because of its resistor at end A. Close to 0 ohm means "
           "that resistor is bridged by solder. OL (or 1 at the left on older meters) means open: a broken joint or wire. "
           "The continuity beeper can't test the data lines: most beep only below about 50 ohm, so a good 330 ohm "
           "line stays silent.", color=NAVY, title="Reading the digital multimeter")

    # ======== 9. first run ========
    g.new_page("First run", "Page 9")
    g.bullets([
        "**Both C64s off.** Plug end A into the leader, the C64 with the monitor you will watch. Plug end B into "
        "the other C64. Paint dot to paint dot.",
        "Switch on the **core** C64 and load **PACK CORE** (or plug in its cartridge). It shows "
        "\"CORE: WAITING FOR THE LEADER\".",
        "Switch on the **leader** and load **PACK LEADER**. Within a second it shows **CORES 2**, and the core's "
        "screen changes to \"CORE 1: LINKED TO THE LEADER\".",
        "Press **1**: the leader draws the picture alone. Then press **2**: both draw it. Each run's time and "
        "speed-up appear below the picture.",
    ])
    y = g.y
    h1 = g.image(IMG / "core-waiting-vice.png", M, y, 236)
    g.image(IMG / "leader-menu-2-cores-sim.png", M + 252, y, 236)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(NAVY)
    c.drawString(M, y - h1 - 12, "The core, waiting (step 2)")
    c.drawString(M + 252, y - h1 - 12, "The leader after pressing 1 and then 2")
    g.y = y - h1 - 34
    g.heading("Write down your results")
    for lab in ("1 core:   ________ s", "2 cores:  ________ s     speed-up ________ x",
                "Expected: about 60 s and 31 s, a speed-up of about 1.95 x"):
        c.setFont("Helvetica", 11)
        c.setFillColor(black if "Expected" not in lab else GREY)
        c.drawString(M + 10, g.y, lab)
        g.y -= 20

    # ======== 10. troubleshooting + credits ========
    g.new_page("If something is wrong", "Page 10")
    trouble = [
        ("The leader shows CORES 1",
         "The core must be running before the leader scans: start PACK CORE, then press S on the leader. Check that "
         "both ends are on the right way round (paint dots), and redo the tests on page 8."),
        ("The leader freezes while running on 2 cores",
         "A handshake wire is broken or swapped. Check A-8 to B-B and A-B to B-8 on page 8. Pin 8 must never go to "
         "pin 8."),
        ("Some tiles in the core's colours are scrambled",
         "A data wire is broken, swapped or bridged. Test C to L again, including the neighbour tests."),
        ("The core's screen stays on WAITING",
         "The leader never reached it. Check the cable as above, then press S on the leader."),
        ("Times are much longer than expected",
         "Make sure both machines are NTSC C64s. A PAL C64 runs about 4% slower, and the leader assumes NTSC "
         "timing when it shows seconds."),
    ]
    for t, body in trouble:
        c.setFont("Helvetica-Bold", 11.5)
        c.setFillColor(NAVY)
        c.drawString(M, g.y, t)
        g.y -= 15
        g.para(body, x=M + 12, width=W - 2 * M - 12, size=10.2, lead=13.5)
    g.y -= 6
    g.heading("Credits")
    g.para("Design, software, guide and the Project Moon Pi logo: Project Moon Pi. User port pinout and CIA 6526 "
           "behaviour: the Commodore 64 Programmer's Reference Guide and the MOS 6526 datasheet. Part data: "
           "DigiKey. Diagrams drawn with ReportLab (BSD licence). Emulator screenshots: VICE (GPL). Commodore 64 "
           "is a trademark of its owners; Project Moon Pi is not affiliated with them. Built with Claude Code "
           "(Anthropic).", size=9.5, lead=12.5)
    c.drawImage(ImageReader(str(LOGO)), W / 2 - 40, 60, 80, 80, mask="auto")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(NAVY)
    c.drawCentredString(W / 2, 48, "Designed and Created by Project Moon Pi")
    g.footer()
    c.save()
    print(f"wrote {OUT} ({g.page} pages)")


if __name__ == "__main__":
    build()
