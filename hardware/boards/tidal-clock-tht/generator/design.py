"""Super Commodore 6400 - Tidal (C)lock, THROUGH-HOLE EDITION, rev 0.1: one master clock for up to 4 C64s.

The same circuit as the SMT edition (hardware/boards/tidal-clock), built from parts you can solder by hand and buy
today, so the bench test can start before any assembled board arrives:

    Adafruit Si5351A board (#2045)  the clock synthesizer, ready made (its own 25 MHz crystal and 3.3 V regulator),
                                    plugged into a 7-way socket. CLK0 = 14.318182 MHz colour, CLK1 = 8.181818 MHz
                                    dot, exactly as on the SMT edition. Powered from the Pico's 3.3 V, so its I2C
                                    pull-ups stay at 3.3 V (the Pico's pins are not 5 V tolerant).
    74HCT04 / 74HCT74 / 74HCT08     the glitch-free gates and colour buffers, in DIP-14 (socketed).
    Raspberry Pi Pico H             on two 20-way sockets, as on the SMT edition.
    GP11 (Pico pin 15) tied to GND  tells the firmware this is the through-hole edition (the Adafruit board's
                                    crystal wants a 10 pF load setting; the SMT edition's wants 8 pF).

Same ports (6-way box headers, wired as the Tidal Link Interface's J3: 1 GND, 2 DOT, 3 GND, 4 COLOR, 5 GND,
6 PHI0 in), same firmware. Run build.sh after changing anything here. Designed and Created by Project Moon Pi.
"""

FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
FP_C = "Capacitor_THT:C_Rect_L4.0mm_W2.5mm_P2.50mm"
FP_CP = "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm"
FP_DIP = "Package_DIP:DIP-14_W7.62mm_Socket"
FP_PICO = "Module:RaspberryPi_Pico_Common_THT"
FP_SYNTH = "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical"
FP_IDC = "Connector_IDC:IDC-Header_2x03_P2.54mm_Vertical"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
FP_LED = "LED_THT:LED_D3.0mm"
FP_HOLE = "MountingHole:MountingHole_3.2mm_M3"
NPORTS = 4

PARTS = []


def part(ref, lib, value, fp, pins, group, desc="", mfr="", mpn=""):
    PARTS.append(dict(ref=ref, lib=lib, value=value, fp=fp, pins={str(k): v for k, v in pins.items()}, group=group,
                      desc=desc, mfr=mfr, mpn=mpn))


_n = {"R": 0, "C": 0}


def nxt(k):
    _n[k] += 1
    return f"{k}{_n[k]}"


RES = {"22": "MFR-25FBF52-22R", "33": "MFR-25FBF52-33R", "1k": "MFR-25FBF52-1K", "2k": "MFR-25FBF52-2K",
       "10k": "MFR-25FBF52-10K"}


def R(val, a, b, grp, desc=""):
    r = nxt("R")
    part(r, "Device:R", val, FP_R, {1: a, 2: b}, grp, desc + " (1/4 W metal film)", "Yageo", RES[val])
    return r


def C(val, a, b, grp, desc=""):
    r = nxt("C")
    if val == "10uF":
        part(r, "Device:C_Polarized", val, FP_CP, {1: a, 2: b}, grp, desc + " (25 V electrolytic: + to the long lead)",
             "KEMET", "ESK106M025AC3AA")
    else:
        part(r, "Device:C", val, FP_C, {1: a, 2: b}, grp, desc, "TDK", "FG18X7R1H104KNT06")
    return r


# ---------------------------------------------------------------- the Pico H (on two 20-way sockets)
pico = {3: "GND", 8: "GND", 13: "GND", 18: "GND", 23: "GND", 28: "GND", 38: "GND",   # (33, AGND: joined to GND inside the Pico)
        36: "+3V3", 40: "+5V",
        1: "SDA", 2: "SCL",                                        # I2C0 to the Si5351 board
        4: "EN1", 5: "EN2", 6: "EN3", 7: "EN4",                    # GP2-GP5: the dot-clock gates
        9: "PH1_IN", 10: "PH2_IN", 11: "PH3_IN", 12: "PH4_IN",     # GP6-GP9: each machine's PHI0 (PIO reads 4 at once)
        14: "DOT_REF",                                             # GP10: the ungated dot clock, for PIO timing
        15: "EDITION"}                                             # GP11 held low (R below): "through-hole edition"
part("A1", "MCU_Module:RaspberryPi_Pico", "Pico H", FP_PICO, pico, "pico",
     "Raspberry Pi Pico H (headers fitted), plugged into two 20-way sockets (Sullins PPTC201LFBN-RC x2)",
     "Raspberry Pi", "SC0917")

# ---------------------------------------------------------------- the clock synthesizer: Adafruit's board
part("M1", "Connector_Generic:Conn_01x07", "Adafruit 2045", FP_SYNTH,
     {1: "COLOR_SRC", 2: "DOT_SRC", 4: "SCL", 5: "SDA", 6: "GND", 7: "+3V3"}, "synth",
     "Adafruit Si5351A clock generator board (#2045), its 7-pin header in a 7-way socket (Sullins PPTC071LFBN-RC): "
     "CLK0, CLK1, CLK2 (unused), SCL, SDA, GND, VIN", "Adafruit", "2045")
C("100nF", "+3V3", "GND", "synth", "Si5351 board supply")
C("10uF", "+3V3", "GND", "synth", "3.3 V bulk")
R("22", "COLOR_SRC", "COLOR", "synth", "series termination")
R("22", "DOT_SRC", "DOT", "synth", "series termination")
R("33", "DOT", "DOT_REF", "synth", "to the Pico")

# ---------------------------------------------------------------- the gates (as the SMT edition, in DIP-14)
part("U2", "74xx:74HCT04", "74HCT04", FP_DIP,
     {1: "DOT", 2: "DOT_N", 3: "DOT_N", 4: "DOT_B", 5: "GND", 9: "GND", 11: "GND", 13: "GND", 7: "GND", 14: "+5V"},
     "gates", "DOT_N (flip-flops' clock: they change on the dot clock's falling edge), DOT_B (5 V dot clock). "
     "In a 14-pin socket (On Shore ED14DT)", "Texas Instruments", "SN74HCT04N")
for u, (a, b) in (("U3", (1, 2)), ("U4", (3, 4))):
    part(u, "74xx:74HCT74", "74HCT74", FP_DIP,
         {1: "+5V", 2: f"EN{a}", 3: "DOT_N", 4: "+5V", 5: f"G{a}",
          13: "+5V", 12: f"EN{b}", 11: "DOT_N", 10: "+5V", 9: f"G{b}", 7: "GND", 14: "+5V"},
         "gates", f"gate flip-flops, ports {a} and {b}. In a 14-pin socket (On Shore ED14DT)", "Texas Instruments",
         "SN74HCT74N")
part("U5", "74xx:74LS08", "74HCT08", FP_DIP,
     {1: "DOT_B", 2: "G1", 3: "D1", 4: "DOT_B", 5: "G2", 6: "D2", 9: "DOT_B", 10: "G3", 8: "D3",
      12: "DOT_B", 13: "G4", 11: "D4", 7: "GND", 14: "+5V"},
     "gates", "the gated dot clocks. In a 14-pin socket (On Shore ED14DT)", "Texas Instruments", "SN74HCT08N")
part("U6", "74xx:74LS08", "74HCT08", FP_DIP,
     {1: "COLOR", 2: "+5V", 3: "C1", 4: "COLOR", 5: "+5V", 6: "C2", 9: "COLOR", 10: "+5V", 8: "C3",
      12: "COLOR", 13: "+5V", 11: "C4", 7: "GND", 14: "+5V"},
     "gates", "colour clock buffers (an AND with one input high), never gated. In a 14-pin socket (On Shore ED14DT)",
     "Texas Instruments", "SN74HCT08N")
for u in ("U2", "U3", "U4", "U5", "U6"):
    C("100nF", "+5V", "GND", "gates", f"{u} decoupling")
C("10uF", "+5V", "GND", "gates", "5 V bulk")
for k in range(1, NPORTS + 1):
    R("10k", f"EN{k}", "+3V3", "gates", f"gate {k} open until the Pico says otherwise")

# ---------------------------------------------------------------- the ports
for k in range(1, NPORTS + 1):
    R("33", f"D{k}", f"PDOT{k}", "ports", f"port {k} dot clock out")
    R("33", f"C{k}", f"PCOL{k}", "ports", f"port {k} colour clock out")
    # each C64's 5 V PHI0 to the Pico's 3.3 V input: a 1k / 2k divider (3.33 V), which also holds an empty port low
    R("1k", f"PPH{k}", f"PH{k}_IN", "ports", f"port {k} PHI0 in")
    R("2k", f"PH{k}_IN", "GND", "ports", f"port {k}: no cable reads low")
    part(f"J{k}", "Connector_Generic:Conn_02x03_Odd_Even", f"PORT {k}", FP_IDC,
         {1: "GND", 2: f"PDOT{k}", 3: "GND", 4: f"PCOL{k}", 5: "GND", 6: f"PPH{k}"}, "ports",
         f"to C64 {k}'s Tidal Link Interface (J3)", "Wurth Elektronik", "61200621621")

# ---------------------------------------------------------------- power light, scope points, mounting holes
part("D1", "Device:LED", "green", FP_LED, {1: "GND", 2: "LED_A"}, "pico", "power light, 3 mm green (long lead = +)",
     "Lite-On", "LTL-4231N")
R("1k", "+5V", "LED_A", "pico", "power light")
R("1k", "EDITION", "GND", "pico", "edition strap: GP11 low tells the firmware this is the through-hole board")
for ref, net, colour, mpn in (("TP1", "COLOR", "orange", "5003"), ("TP2", "DOT", "yellow", "5004"),
                              ("TP3", "DOT_B", "white", "5002"), ("TP4", "GND", "black", "5001"),
                              ("TP5", "GND", "black", "5001")):
    part(ref, "Connector:TestPoint", net, FP_TP, {1: net}, "pico", f"scope test point ({colour})", "Keystone", mpn)
for i in range(1, 5):
    part(f"H{i}", "Mechanical:MountingHole", "M3", FP_HOLE, {}, "pico", "M3 mounting hole")

NETCLASSES = {"Power": (0.6, 0.2, ["+5V", "GND"]),
              "Power33": (0.4, 0.2, ["+3V3"]),
              "Clock": (0.3, 0.2, ["COLOR*", "DOT*", "D?", "C?", "PDOT*", "PCOL*", "G?"])}
DEFAULT_TRACK, DEFAULT_CLEAR = 0.25, 0.2
