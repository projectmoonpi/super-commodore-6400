# Tidal Array 6400 - Tidal (C)lock firmware (MicroPython for the Raspberry Pi Pico H), rev 0.1
# Designed and Created by Project Moon Pi.
#
# At power-on it sets the Si5351 up for the two NTSC C64 clocks and opens every port's gate, so each C64 plugged in
# runs from the one master clock. Then it waits for commands over USB (a serial console: Thonny, or
# `mpremote connect auto` from the Mac):
#
#   status              each port's PHI0: is a C64 there, and how far (in dot clocks) it is behind port 1
#   drop P N            drop N dot-clock pulses on port P (1-4): that C64 slows by N dot periods, then carries on
#   align               drop pulses until every C64's PHI0 is in step with port 1's (the clock-phase alignment)
#   lines P L           drop L whole raster lines' worth of pulses on port P (65 cycles x 8 = 520 pulses a line),
#                       gently: one pulse per CPU cycle. For lining up raster lines (the C64 test program says how many)
#   help
#
# Wiring (the Tidal (C)lock board, hardware/boards/tidal-clock): I2C0 SDA GP0, SCL GP1 (Si5351 at 0x60); gates EN1-EN4 on
# GP2-GP5 (high = pulses pass); each port's PHI0 in on GP6-GP9; the ungated dot clock on GP10.
# GP11 tells the two editions apart: held low by a 1k resistor on the through-hole board (hardware/boards/
# tidal-clock-tht, Adafruit's Si5351 board: its crystal wants the 10 pF load setting), open on the SMT board (its own
# Kyocera CX3225GB crystal: 8 pF). Same pins, same commands otherwise.

import time
import rp2
from machine import I2C, Pin

SI5351 = 0x60
EN_BASE, PH_BASE, DOT_PIN, EDITION_PIN = 2, 6, 10, 11
NPORTS = 4
DOT_HZ = 315_000_000 / 22 * 4 / 7          # 8.181818 MHz
SYS_HZ = 125_000_000


# ---------------------------------------------------------------- the clock synthesizer
def si_write(i2c, reg, data):
    i2c.writeto_mem(SI5351, reg, bytes(data))


def params(a, b, c):
    """Si5351 multisynth parameters (AN619): P1, P2, P3 packed into its 8 registers."""
    f = (128 * b) // c
    p1 = 128 * a + f - 512
    p2 = 128 * b - c * f
    p3 = c
    return [(p3 >> 8) & 0xFF, p3 & 0xFF, (p1 >> 16) & 0x03, (p1 >> 8) & 0xFF, p1 & 0xFF,
            ((p3 >> 12) & 0xF0) | ((p2 >> 16) & 0x0F), (p2 >> 8) & 0xFF, p2 & 0xFF]


def edition():
    """'THT' when GP11 is held low (the through-hole board's strap), else 'SMT'."""
    return "THT" if Pin(EDITION_PIN, Pin.IN, Pin.PULL_UP).value() == 0 else "SMT"


XTAL_LOAD = {"SMT": 0x92,                          # 8 pF: the SMT board's Kyocera CX3225GB 25 MHz crystal
             "THT": 0xD2}                          # 10 pF: the Adafruit board's crystal (Adafruit's own library setting)


def start_clocks(i2c, board="SMT"):
    si_write(i2c, 3, [0xFF])                       # all outputs off while setting up
    si_write(i2c, 16, [0x80] * 8)                  # all output drivers powered down
    si_write(i2c, 183, [XTAL_LOAD[board]])         # the crystal's load capacitance (bits 7-6)
    si_write(i2c, 149, [0x00])                     # no spread spectrum
    si_write(i2c, 26, params(32, 4, 55))           # PLL A: 25 MHz x (32 + 4/55) = 801.818182 MHz
    si_write(i2c, 42, params(56, 0, 1))            # MS0: / 56 = 14.318182 MHz (colour clock)
    si_write(i2c, 50, params(98, 0, 1))            # MS1: / 98 = 8.181818 MHz (dot clock)
    si_write(i2c, 165, [0, 0])                     # no phase offsets
    si_write(i2c, 177, [0x20])                     # reset PLL A: the two outputs start in step
    si_write(i2c, 16, [0x4F, 0x4F])                # CLK0, CLK1: integer mode, from PLL A, multisynth, 8 mA
    si_write(i2c, 3, [0xFC])                       # CLK0 and CLK1 on


# ---------------------------------------------------------------- dropping dot pulses (PIO)
# The gate's flip-flop samples EN on each falling edge of the dot clock. This program waits for a falling edge,
# drops the chosen ports' EN for exactly one dot period, and so removes exactly one pulse from each of them.
@rp2.asm_pio(out_init=(rp2.PIO.OUT_HIGH,) * 4, set_init=(rp2.PIO.OUT_HIGH,) * 4)
def dropper():
    pull(block)                                    # the EN pattern while dropping (0 = drop on that port)
    wait(1, pin, 0)
    wait(0, pin, 0)                                # a falling edge: EN now changes safely while the clock is low
    out(pins, 4)
    wait(1, pin, 0)
    wait(0, pin, 0)                                # the next falling edge sampled EN = 0: one pulse dropped
    set(pins, 15)


# ---------------------------------------------------------------- watching PHI0 (PIO)
# Four PHI0 inputs sampled together every 8 ns, 8 samples a word, into a buffer for analysis.
@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_LEFT, autopush=True, push_thresh=32)
def sampler():
    wrap_target()
    in_(pins, 4)
    wrap()


class PackClock:
    def __init__(self):
        self.board = edition()
        self.i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400_000)
        start_clocks(self.i2c, self.board)
        dot = Pin(DOT_PIN, Pin.IN)
        self.drop_sm = rp2.StateMachine(0, dropper, freq=SYS_HZ, in_base=dot, out_base=Pin(EN_BASE),
                                        set_base=Pin(EN_BASE))
        self.drop_sm.active(1)
        self.ph = [Pin(PH_BASE + k, Pin.IN) for k in range(NPORTS)]

    def drop(self, port, n):
        """Drop n dot pulses on one port (1-4). The program takes one at a time, two dot periods each."""
        mask = 0x0F & ~(1 << (port - 1))
        for _ in range(n):
            self.drop_sm.put(mask)

    def capture(self, words=128):
        """1024 samples (8 us) of all four PHI0 lines, as a list of 4-bit values in time order."""
        sm = rp2.StateMachine(1, sampler, freq=SYS_HZ, in_base=Pin(PH_BASE))
        buf = bytearray(words * 4)
        dma = rp2.DMA()
        ctrl = dma.pack_ctrl(size=2, inc_read=False, treq_sel=5)   # DREQ 5 = PIO0 state machine 1's RX FIFO
        dma.config(read=sm, write=buf, count=words, ctrl=ctrl, trigger=True)
        sm.active(1)
        while dma.active():
            pass
        sm.active(0)
        dma.close()
        out = []
        for i in range(words):
            w = int.from_bytes(buf[4 * i:4 * i + 4], "little")
            for s in range(7, -1, -1):             # the oldest sample is in the top nibble
                out.append((w >> (4 * s)) & 0xF)
        return out

    def rising_edges(self, samples, port):
        bit = 1 << port
        return [i for i in range(1, len(samples)) if samples[i] & bit and not samples[i - 1] & bit]

    def status(self):
        s = self.capture()
        ns = 1e9 / SYS_HZ
        dot_ns = 1e9 / DOT_HZ
        e = [self.rising_edges(s, k) for k in range(NPORTS)]
        result = []
        for k in range(NPORTS):
            if len(e[k]) < 2:
                result.append((k + 1, None))
                continue
            period = (e[k][-1] - e[k][0]) * ns / (len(e[k]) - 1)
            if not e[0]:
                result.append((k + 1, (period, None)))
                continue
            lag = ((e[k][0] - e[0][0]) * ns) % (8 * dot_ns)      # how far behind port 1, within one CPU cycle
            result.append((k + 1, (period, lag / dot_ns)))
        return result

    def align(self, tries=6):
        for _ in range(tries):
            st = self.status()
            done = True
            for port, r in st[1:]:
                if not r or r[1] is None:
                    continue
                lag = round(r[1]) % 8                # in dot periods: 0 = in step
                if lag:
                    self.drop(port, 8 - lag)          # dropping pulses only ever delays a machine
                    done = False
            time.sleep_ms(5)
            if done:
                return True
        return False

    def lines(self, port, n):
        """n raster lines' worth of dot pulses (65 cycles x 8 = 520 a line), never more than one per CPU cycle, so the
        machine only ever slows a little and never stops (each put takes ~20 us in MicroPython anyway)."""
        for _ in range(n * 520):
            self.drop(port, 1)
            time.sleep_us(1)


def console(pc):
    print(f"Tidal (C)lock ({pc.board} edition) ready: 14.318182 + 8.181818 MHz on all ports. Type help.")
    while True:
        try:
            cmd = input("tidal> ").split()
        except EOFError:
            return
        if not cmd:
            continue
        try:
            if cmd[0] == "status":
                for port, r in pc.status():
                    if r is None:
                        print(f"port {port}: no C64 (no PHI0)")
                    else:
                        period, lag = r
                        mhz = 1000 / period
                        print(f"port {port}: PHI0 {mhz:.4f} MHz" + ("" if lag is None else f", {lag:.2f} dot clocks behind port 1"))
            elif cmd[0] == "drop":
                pc.drop(int(cmd[1]), int(cmd[2]))
                print("dropped", cmd[2], "on port", cmd[1])
            elif cmd[0] == "align":
                print("in step" if pc.align() else "could not line every port up: check the cables")
            elif cmd[0] == "lines":
                pc.lines(int(cmd[1]), int(cmd[2]))
                print("port", cmd[1], "moved", cmd[2], "raster lines later")
            else:
                print("status | drop P N | align | lines P L | help")
        except Exception as ex:                       # keep the console alive whatever is typed
            print("error:", ex)


pc = PackClock()
console(pc)
