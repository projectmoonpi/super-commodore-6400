"""Super Commodore 6400 - Tidal Link Interface (TLI), THROUGH-HOLE EDITION, rev 0.1: the VIC clock interposer.

The same job as the SMT edition (hardware/boards/tidal-link), built from parts you can solder by hand:
    74HCT14 (DIP-14)   the buffer: two Schmitt-trigger inverters in series per signal (6 inverters = the 3 signals),
                       so each clock comes out the right way up and cleaned up, as the SMT edition's 74LVC3G17 does
    JS202011CQN        the through-hole version of the same C&K INT/EXT slide switch
    axial resistors, radial capacitors, the same plug pins, socket strips, box header and test points

Plugs into a C64's VIC-II socket; the VIC-II plugs into it. Every pin passes straight through except the two
clock inputs, which go through the slide switch:

    INT  the VIC gets the C64's own clocks, exactly as without the board (pins 21, 22 straight through)
    EXT  the VIC gets the master clock from the Tidal (C)lock board, through the buffer on this board

VIC-II pinout (6567 / 8562 / 8565 are the same; Commodore 64 Programmer's Reference Guide, appendix N):
    21  PHI COLOR  colour clock in: 14.31818 MHz on NTSC
    22  PHI IN     dot clock in:     8.18182 MHz on NTSC (the VIC divides it by 8 for the CPU's PHI0)
    17  PHI 0      the system clock the VIC makes (out): buffered and sent back to the Tidal (C)lock board
The board takes its 5 V from the VIC's own VCC (pin 40). No soldering on the C64: it uses only the VIC's socket.
Run build.sh after changing anything here. Designed and Created by Project Moon Pi.
"""

FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C = "Capacitor_THT:C_Rect_L4.0mm_W2.5mm_P2.50mm"
FP_CP = "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm"
FP_DIP = "Package_DIP:DIP-40_W15.24mm"
FP_SOCK = "Package_DIP:DIP-40_W15.24mm_Socket"
FP_BUF = "Package_DIP:DIP-14_W7.62mm_Socket"
FP_SW = "Button_Switch_THT:SW_CK_JS202011CQN_DPDT_Straight"
FP_IDC = "Connector_IDC:IDC-Header_2x03_P2.54mm_Vertical"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"

VIC_PINS = {1: "DB6", 2: "DB5", 3: "DB4", 4: "DB3", 5: "DB2", 6: "DB1", 7: "DB0", 8: "~{IRQ}", 9: "~{LP}",
            10: "~{CS}", 11: "R~{W}", 12: "BA", 13: "VDD", 14: "COLOR", 15: "S~{LUM}", 16: "AEC", 17: "PHI0",
            18: "~{RAS}", 19: "~{CAS}", 20: "GND", 21: "PHCL", 22: "PHIN", 23: "A11", 24: "A0", 25: "A1",
            26: "A2", 27: "A3", 28: "A4", 29: "A5", 30: "A6", 31: "A7", 32: "A8", 33: "A9", 34: "A10",
            35: "DB11", 36: "DB10", 37: "DB9", 38: "DB8", 39: "DB7", 40: "+5V"}

PARTS = []


def part(ref, lib, value, fp, pins, group, desc="", mfr="", mpn=""):
    PARTS.append(dict(ref=ref, lib=lib, value=value, fp=fp, pins={str(k): v for k, v in pins.items()}, group=group,
                      desc=desc, mfr=mfr, mpn=mpn))


# the plug (to the C64's socket) and the socket (for the VIC): the same pins, except the two clock inputs
plug = {n: (f"MB_{s}" if n in (21, 22) else s) for n, s in VIC_PINS.items()}
sock = {n: (f"VIC_{s}" if n in (21, 22) else s) for n, s in VIC_PINS.items()}
part("J1", "Connector_Generic:Conn_02x20_Counter_Clockwise", "PLUG (C64 VIC socket)", FP_DIP, plug, "vic",
     "40 round pins underneath: two 20-pin strips that plug into the C64's VIC-II socket", "Mill-Max",
     "350-10-164-00-006000 (one 64-pin strip, snapped into two 20s)")
part("J2", "Connector_Generic:Conn_02x20_Counter_Clockwise", "SOCKET (VIC-II)", FP_DIP, sock, "vic",
     "VIC-II socket on top: two 20-pin machined socket strips, one per row (open between them, so the plug's "
     "solder joints underneath stay clear)", "Preci-Dip", "310-87-120-41-001101 (x2)")

# the clock selector: pole A = dot clock (pin 22), pole B = colour clock (pin 21). On this through-hole switch pin 6
# sits beside pin 1 and pin 4 beside pin 3, so 1-2 / 6-5 = INT, 2-3 / 5-4 = EXT
part("SW1", "Switch:SW_DPDT_x2", "INT/EXT", FP_SW,
     {1: "MB_PHIN", 2: "VIC_PHIN", 3: "DOT_EXT", 6: "MB_PHCL", 5: "VIC_PHCL", 4: "COLOR_EXT"}, "clock",
     "Clock source: INT = the C64's own, EXT = the Tidal (C)lock board. Switch only with the C64 off.", "C&K",
     "JS202011CQN")

# buffer: the cable's two clocks in, PHI0 out to the cable (so the cable never loads the C64's system clock)
# 74HCT14: 1A 1, 1Y 2, 2A 3, 2Y 4, 3A 5, 3Y 6, GND 7, 4Y 8, 4A 9, 5Y 10, 5A 11, 6Y 12, 6A 13, VCC 14
part("U1", "74xx:74HC14", "74HCT14", FP_BUF,
     {1: "EXT_DOT", 2: "DOT_N", 3: "DOT_N", 4: "DOT_BUF",
      5: "EXT_COLOR", 6: "COLOR_N", 9: "COLOR_N", 8: "COLOR_BUF",
      11: "PHI0", 10: "PHI0_N", 13: "PHI0_N", 12: "PHI0_BUF", 7: "GND", 14: "+5V"},
     "clock", "Hex Schmitt-trigger inverter, used as 3 buffers (2 inverters each). In a 14-pin socket (On Shore ED14DT)",
     "Texas Instruments", "SN74HCT14N")
part("R1", "Device:R", "33", FP_R, {1: "DOT_BUF", 2: "DOT_EXT"}, "clock", "series termination", "Yageo", "MFR-25FBF52-33R")
part("R2", "Device:R", "33", FP_R, {1: "COLOR_BUF", 2: "COLOR_EXT"}, "clock", "series termination", "Yageo", "MFR-25FBF52-33R")
part("R3", "Device:R", "33", FP_R, {1: "PHI0_BUF", 2: "PHI0_OUT"}, "clock", "series termination", "Yageo", "MFR-25FBF52-33R")
part("R4", "Device:R", "100k", FP_R, {1: "EXT_DOT", 2: "GND"}, "clock", "holds the input low with no cable",
     "Yageo", "MFR-25FRF52-100K")
part("R5", "Device:R", "100k", FP_R, {1: "EXT_COLOR", 2: "GND"}, "clock", "holds the input low with no cable",
     "Yageo", "MFR-25FRF52-100K")
part("C1", "Device:C", "100nF", FP_C, {1: "+5V", 2: "GND"}, "clock", "decoupling", "TDK", "FG18X7R1H104KNT06")
part("C2", "Device:C_Polarized", "10uF", FP_CP, {1: "+5V", 2: "GND"}, "clock",
     "bulk decoupling (25 V electrolytic: + to the long lead)", "KEMET", "ESK106M025AC3AA")

# the cable to the Tidal (C)lock board: grounds between the signals
part("J3", "Connector_Generic:Conn_02x03_Odd_Even", "CLOCK LINK", FP_IDC,
     {1: "GND", 2: "EXT_DOT", 3: "GND", 4: "EXT_COLOR", 5: "GND", 6: "PHI0_OUT"}, "clock",
     "6-way box header: ribbon to the Tidal (C)lock board", "Wurth Elektronik", "61200621621")

# scope test points (Hantek DSO5102P probes clip on here, never on the C64 board)
for ref, net, colour, mpn in (("TP1", "PHI0", "white", "5002"), ("TP2", "VIC_PHIN", "yellow", "5004"),
                              ("TP3", "VIC_PHCL", "orange", "5003"), ("TP4", "GND", "black", "5001"),
                              ("TP5", "GND", "black", "5001")):
    part(ref, "Connector:TestPoint", net, FP_TP, {1: net}, "test", f"scope test point ({colour})", "Keystone", mpn)

NETCLASSES = {"Power": (0.6, 0.15, ["+5V", "GND", "VDD"]),
              "Clock": (0.3, 0.15, ["MB_PHIN", "MB_PHCL", "VIC_PHIN", "VIC_PHCL", "DOT_EXT", "COLOR_EXT",
                                    "DOT_BUF", "COLOR_BUF", "EXT_DOT", "EXT_COLOR", "PHI0", "PHI0_BUF",
                                    "PHI0_OUT", "DOT_N", "COLOR_N", "PHI0_N"])}
DEFAULT_TRACK, DEFAULT_CLEAR = 0.25, 0.2

# power flags: the 5 V and ground come in from the VIC's socket (no regulator here), so ERC is told so
part("#FLG1", "power:PWR_FLAG", "PWR_FLAG", "", {1: "+5V"}, "test")
part("#FLG2", "power:PWR_FLAG", "PWR_FLAG", "", {1: "GND"}, "test")
