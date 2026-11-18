"""Super Commodore 6400 - Pack Clock, rev 0.1: one master clock for up to 4 C64s (the bench-test instrument).

    Si5351A (25 MHz crystal)  CLK0 = 14.318182 MHz colour clock, CLK1 = 8.181818 MHz dot clock, both from one PLL
                              (801.818 MHz = 25 MHz x 32 4/55) through whole dividers 56 and 98: exact, locked
                              together, 50 % duty.
    per port                  the dot clock through a glitch-free gate (74HCT74 flip-flop, clocked on the dot clock's
                              falling edge, + 74HCT08 AND): the Pico can drop exactly one dot pulse on one machine,
                              to slide it into step with the others; the colour clock is never gated.
    Raspberry Pi Pico H       sets the Si5351 up (I2C), drives the 4 gates, watches each machine's PHI0 (back from
                              its interposer, through a 1k / 2k divider to 3.3 V) to measure how far apart the
                              machines are, talks to the Mac over USB.
    5 V for the 74HCT logic   from the Pico's VBUS (USB); 3.3 V for the Si5351 and the input buffer from its 3V3.

Each port is a 6-way box header, wired as the VIC clock interposer's J3: 1 GND, 2 DOT, 3 GND, 4 COLOR, 5 GND,
6 PHI0 (in). Run build.sh after changing anything here. Designed and Created by Project Moon Pi.
"""

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_C08 = "Capacitor_SMD:C_0805_2012Metric"
FP_SO14 = "Package_SO:TSSOP-14_4.4x5mm_P0.65mm"
FP_QFN = "Package_DFN_QFN:QFN-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm"
FP_XTAL = "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm"
FP_PICO = "Module:RaspberryPi_Pico_Common_THT"
FP_IDC = "Connector_IDC:IDC-Header_2x03_P2.54mm_Vertical"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
FP_LED = "LED_SMD:LED_0603_1608Metric"
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


RES = {"2k": "RC0603FR-072KL", "22": "RC0603FR-0722RL", "33": "RC0603FR-0733RL", "100": "RC0603FR-07100RL", "1k": "RC0603FR-071KL",
       "4.7k": "RC0603FR-074K7L", "10k": "RC0603FR-0710KL", "100k": "RC0603FR-07100KL"}


def R(val, a, b, grp, desc=""):
    r = nxt("R")
    part(r, "Device:R", val, FP_R, {1: a, 2: b}, grp, desc, "Yageo", RES[val])
    return r


def C(val, a, b, grp, desc=""):
    r = nxt("C")
    if val == "10uF":
        part(r, "Device:C", val, FP_C08, {1: a, 2: b}, grp, desc, "Murata", "GRM21BR61C106KE15L")
    else:
        part(r, "Device:C", val, FP_C, {1: a, 2: b}, grp, desc, "Murata", "GRM188R71H104KA93D")
    return r


# ---------------------------------------------------------------- the Pico H (on two 20-way sockets)
pico = {3: "GND", 8: "GND", 13: "GND", 18: "GND", 23: "GND", 28: "GND", 38: "GND",   # (33, AGND: joined to GND inside the Pico)
        36: "+3V3", 40: "+5V",
        1: "SDA", 2: "SCL",                                        # I2C0 to the Si5351
        4: "EN1", 5: "EN2", 6: "EN3", 7: "EN4",                    # GP2-GP5: the dot-clock gates
        9: "PH1_IN", 10: "PH2_IN", 11: "PH3_IN", 12: "PH4_IN",     # GP6-GP9: each machine's PHI0 (PIO reads 4 at once)
        14: "DOT_REF"}                                             # GP10: the ungated dot clock, for PIO timing
part("A1", "MCU_Module:RaspberryPi_Pico", "Pico H", FP_PICO, pico, "pico",
     "Raspberry Pi Pico H (headers fitted), plugged into two 20-way sockets", "Raspberry Pi", "SC0917")

# ---------------------------------------------------------------- the clock synthesizer
part("U1", "Oscillator:Si5351A-B-GM", "Si5351A-B-GM", FP_QFN,
     {1: "XA", 2: "XB", 3: "GND", 4: "SCL", 5: "SDA", 6: "GND", 7: "GND", 13: "COLOR_SRC", 12: "DOT_SRC",
      10: "+3V3", 11: "+3V3", 14: "+3V3", 18: "+3V3", 20: "+3V3", 21: "GND"}, "synth",
     "Clock synthesizer: CLK0 colour 14.318182 MHz, CLK1 dot 8.181818 MHz (A0, SSEN, OEB tied low)",
     "Skyworks", "SI5351A-B-GM")
part("Y1", "Device:Crystal_GND24", "25MHz", FP_XTAL, {1: "XA", 3: "XB", 2: "GND", 4: "GND"}, "synth",
     "25 MHz crystal, 8 pF (the Si5351's internal load set to 8 pF)", "Kyocera AVX", "CX3225GB25000D0HEQCC")
C("100nF", "+3V3", "GND", "synth", "Si5351 VDD")
C("100nF", "+3V3", "GND", "synth", "Si5351 VDDO")
R("4.7k", "SDA", "+3V3", "synth", "I2C pull-up")
R("4.7k", "SCL", "+3V3", "synth", "I2C pull-up")
R("22", "COLOR_SRC", "COLOR", "synth", "series termination")
R("22", "DOT_SRC", "DOT", "synth", "series termination")
R("33", "DOT", "DOT_REF", "synth", "to the Pico")

# ---------------------------------------------------------------- the gates
part("U2", "74xx:74HCT04", "74HCT04", FP_SO14,
     {1: "DOT", 2: "DOT_N", 3: "DOT_N", 4: "DOT_B", 5: "GND", 9: "GND", 11: "GND", 13: "GND", 7: "GND", 14: "+5V"},
     "gates", "DOT_N (flip-flops' clock: they change on the dot clock's falling edge), DOT_B (5 V dot clock)",
     "Texas Instruments", "SN74HCT04PWR")
ff = {}
for u, (a, b) in (("U3", (1, 2)), ("U4", (3, 4))):
    part(u, "74xx:74HCT74", "74HCT74", FP_SO14,
         {1: "+5V", 2: f"EN{a}", 3: "DOT_N", 4: "+5V", 5: f"G{a}",
          13: "+5V", 12: f"EN{b}", 11: "DOT_N", 10: "+5V", 9: f"G{b}", 7: "GND", 14: "+5V"},
         "gates", f"gate flip-flops, ports {a} and {b}", "Texas Instruments", "SN74HCT74PWR")
part("U5", "74xx:74LS08", "74HCT08", FP_SO14,
     {1: "DOT_B", 2: "G1", 3: "D1", 4: "DOT_B", 5: "G2", 6: "D2", 9: "DOT_B", 10: "G3", 8: "D3",
      12: "DOT_B", 13: "G4", 11: "D4", 7: "GND", 14: "+5V"},
     "gates", "the gated dot clocks", "Texas Instruments", "SN74HCT08PWR")
part("U6", "74xx:74LS08", "74HCT08", FP_SO14,
     {1: "COLOR", 2: "+5V", 3: "C1", 4: "COLOR", 5: "+5V", 6: "C2", 9: "COLOR", 10: "+5V", 8: "C3",
      12: "COLOR", 13: "+5V", 11: "C4", 7: "GND", 14: "+5V"},
     "gates", "colour clock buffers (an AND with one input high), never gated", "Texas Instruments",
     "SN74HCT08PWR")
for u in ("U2", "U3", "U4", "U5", "U6"):
    C("100nF", "+5V", "GND", "gates", f"{u} decoupling")
C("10uF", "+5V", "GND", "gates", "5 V bulk")
C("10uF", "+3V3", "GND", "synth", "3.3 V bulk")
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
         f"to C64 {k}'s VIC clock interposer (J3)", "Wurth Elektronik", "61200621621")

# ---------------------------------------------------------------- power light, scope points, mounting holes
part("D1", "Device:LED", "green", FP_LED, {1: "GND", 2: "LED_A"}, "pico", "power light", "Lite-On",
     "LTST-C191KGKT")
R("1k", "+5V", "LED_A", "pico", "power light")
for ref, net, colour, mpn in (("TP1", "COLOR", "orange", "5003"), ("TP2", "DOT", "yellow", "5004"),
                              ("TP3", "DOT_B", "white", "5002"), ("TP4", "GND", "black", "5001"),
                              ("TP5", "GND", "black", "5001")):
    part(ref, "Connector:TestPoint", net, FP_TP, {1: net}, "pico", f"scope test point ({colour})", "Keystone", mpn)
for i in range(1, 5):
    part(f"H{i}", "Mechanical:MountingHole", "M3", FP_HOLE, {}, "pico", "M3 mounting hole")
# (no power flags: the Pico's symbol already marks VBUS, 3V3 and GND as the board's power)

NETCLASSES = {"Power": (0.4, 0.15, ["+5V", "GND"]),
              # 3.3 V: a few tens of mA (Si5351, one buffer, pull-ups), and five of its pins on the 0.5 mm QFN
              "Power33": (0.25, 0.15, ["+3V3"]),
              "Clock": (0.3, 0.15, ["COLOR*", "DOT*", "D?", "C?", "PDOT*", "PCOL*", "G?"])}
DEFAULT_TRACK, DEFAULT_CLEAR = 0.25, 0.15
