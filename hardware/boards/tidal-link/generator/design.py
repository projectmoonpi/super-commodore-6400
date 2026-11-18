"""Super Commodore 6400 - Tidal Link Interface (TLI), rev 0.1: the VIC clock interposer, one per C64.

Plugs into a C64's VIC-II socket; the VIC-II plugs into it. Every pin passes straight through except the two
clock inputs, which go through a slide switch:

    INT  the VIC gets the C64's own clocks, exactly as without the board (pins 21, 22 straight through)
    EXT  the VIC gets the master clock from the Tidal (C)lock board, through a buffer on this board

VIC-II pinout (6567 / 8562 / 8565 are the same; Commodore 64 Programmer's Reference Guide, appendix N):
    21  PHI COLOR  colour clock in: 14.31818 MHz on NTSC
    22  PHI IN     dot clock in:     8.18182 MHz on NTSC (the VIC divides it by 8 for the CPU's PHI0)
    17  PHI 0      the system clock the VIC makes (out): buffered and sent back to the Tidal (C)lock board, so it can
                   measure how far apart the machines are
The board takes its 5 V from the VIC's own VCC (pin 40). No soldering on the C64: it uses only the VIC's socket.
Run build.sh after changing anything here. Designed and Created by Project Moon Pi.
"""

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_DIP = "Package_DIP:DIP-40_W15.24mm"
FP_SOCK = "Package_DIP:DIP-40_W15.24mm_Socket"
FP_BUF = "Package_SO:VSSOP-8_2.3x2mm_P0.5mm"
FP_SW = "Button_Switch_SMD:SW_DPDT_CK_JS202011JCQN"
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
     "350-10-120-00-001000 (x2)")
part("J2", "Connector_Generic:Conn_02x20_Counter_Clockwise", "SOCKET (VIC-II)", FP_DIP, sock, "vic",
     "VIC-II socket on top: two 20-pin machined socket strips, one per row (open between them, so the plug's "
     "solder joints underneath stay clear)", "Preci-Dip", "310-87-120-41-001101 (x2)")

# the clock selector: pole A = dot clock (pin 22), pole B = colour clock (pin 21); 1-2 / 4-5 = INT, 2-3 / 5-6 = EXT
part("SW1", "Switch:SW_DPDT_x2", "INT/EXT", FP_SW,
     {1: "MB_PHIN", 2: "VIC_PHIN", 3: "DOT_EXT", 4: "MB_PHCL", 5: "VIC_PHCL", 6: "COLOR_EXT"}, "clock",
     "Clock source: INT = the C64's own, EXT = the Tidal (C)lock board. Switch only with the C64 off.", "C&K",
     "JS202011JCQN")

# buffer: the cable's two clocks in, PHI0 out to the cable (so the cable never loads the C64's system clock)
part("U1", "74xGxx:74LVC3G17", "74LVC3G17", FP_BUF,
     {1: "EXT_DOT", 7: "DOT_BUF", 3: "EXT_COLOR", 5: "COLOR_BUF", 6: "PHI0", 2: "PHI0_BUF", 4: "GND", 8: "+5V"},
     "clock", "Triple Schmitt-trigger buffer, 5 V", "Texas Instruments", "SN74LVC3G17DCUR")
part("R1", "Device:R", "33", FP_R, {1: "DOT_BUF", 2: "DOT_EXT"}, "clock", "series termination", "Yageo",
     "RC0603FR-0733RL")
part("R2", "Device:R", "33", FP_R, {1: "COLOR_BUF", 2: "COLOR_EXT"}, "clock", "series termination", "Yageo",
     "RC0603FR-0733RL")
part("R3", "Device:R", "33", FP_R, {1: "PHI0_BUF", 2: "PHI0_OUT"}, "clock", "series termination", "Yageo",
     "RC0603FR-0733RL")
part("R4", "Device:R", "100k", FP_R, {1: "EXT_DOT", 2: "GND"}, "clock", "holds the input low with no cable",
     "Yageo", "RC0603FR-07100KL")
part("R5", "Device:R", "100k", FP_R, {1: "EXT_COLOR", 2: "GND"}, "clock", "holds the input low with no cable",
     "Yageo", "RC0603FR-07100KL")
part("C1", "Device:C", "100nF", FP_C, {1: "+5V", 2: "GND"}, "clock", "decoupling", "Murata", "GRM188R71H104KA93D")
part("C2", "Device:C", "10uF", FP_C, {1: "+5V", 2: "GND"}, "clock", "bulk decoupling", "Murata",
     "GRM188R61A106KE69D")

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
                                    "PHI0_OUT"])}
DEFAULT_TRACK, DEFAULT_CLEAR = 0.25, 0.15

# power flags: the 5 V and ground come in from the VIC's socket (no regulator here), so ERC is told so
part("#FLG1", "power:PWR_FLAG", "PWR_FLAG", "", {1: "+5V"}, "test")
part("#FLG2", "power:PWR_FLAG", "PWR_FLAG", "", {1: "GND"}, "test")
