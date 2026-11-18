#!/usr/bin/env python3
"""Run the leader (and a core) in packsim, then check and show the results.

  tools/simcheck.py [--solo] [--maxit N]

- Renders each machine's screen to build/sim-<n>.png (bitmap rows 0-19, text rows 20-24).
- Checks every tile in the leader's picture against a Python copy of the job's fixed-point maths.
- Counts which core computed which tile (by the tile's colours).
- Prints the times and the speed-up the leader measured.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
CHARGEN = Path("/Applications/Emulators/vice-x86-64-gtk3-3.8/VICE.app/Contents/Resources/share/vice/C64/"
               "chargen-901225-01.bin")
PAL = [(0, 0, 0), (255, 255, 255), (129, 51, 56), (117, 206, 200), (142, 60, 151), (86, 172, 77),
       (46, 44, 155), (237, 241, 113), (142, 80, 41), (85, 56, 0), (196, 108, 113), (74, 74, 74),
       (123, 123, 123), (169, 255, 159), (112, 109, 235), (178, 178, 178)]   # colodore
PALSCR = [0x6e, 0x28, 0x5d, 0x4a, 0x98, 0xbc, 0x64, 0x53]


def sym(path):
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r"\s*(\S+)\s*=\s*\$([0-9a-f]+)", line)
        if m:
            out[m[1]] = int(m[2], 16)
    return out


X0, XW, Y0, YH = -742, 1178, -294, 589          # the job's view, 8.8 fixed point


def ref_pixel(px, py, maxit):
    """The job's maths exactly: 8.8 fixed point, products floored to 8.8."""
    def s16(v):
        v &= 0xFFFF
        return v - 0x10000 if v & 0x8000 else v
    cx, cy = X0 + (px * XW) // 160, Y0 + (py * YH) // 160
    zx, zy, it = cx, cy, 1
    while True:
        ax, ay = abs(zx), abs(zy)
        if ax >= 512 or ay >= 512:
            break
        x2, y2 = (ax * ax) >> 8, (ay * ay) >> 8
        if x2 + y2 >= 1024:
            break
        p = (ax * ay) >> 8
        neg = (zx < 0) != (zy < 0)
        d = -2 * p if neg else 2 * p
        zy, zx = s16(d + cy), s16(x2 - y2 + cx)
        it += 1
        if it == maxit:
            return 0
    return 1 + it % 3


def ref_tile_bytes(t, maxit):
    tx, ty = t % 10, t // 10
    out = bytearray(32)
    for line in range(8):
        for cell in range(4):
            b = 0
            for k in range(4):
                b = (b << 2) | ref_pixel(tx * 16 + cell * 4 + k, ty * 8 + line, maxit)
            out[cell * 8 + line] = b
    return out


def tile_addr(t):
    tx, ty = t % 10, t // 10
    return 0x6000 + ty * 320 + tx * 32, ty * 40 + tx * 4


def render(dump, path):
    ram, col, vic = dump[:65536], dump[65536:66560], dump[66560:66624]
    bg = vic[0x21] & 15
    img = Image.new("RGB", (320, 200))
    px = img.load()
    for row in range(25):
        for c in range(40):
            off = row * 40 + c
            if row < 20:
                scr = ram[0x5C00 + off]
                cols = [bg, scr >> 4, scr & 15, col[off] & 15]
                for y in range(8):
                    b = ram[0x6000 + row * 320 + c * 8 + y]
                    for k in range(4):
                        v = (b >> (6 - 2 * k)) & 3
                        px[c * 8 + 2 * k, row * 8 + y] = px[c * 8 + 2 * k + 1, row * 8 + y] = PAL[cols[v]]
            else:
                ch = ram[0x5800 + off]
                fg = col[off] & 15
                for y in range(8):
                    b = ram[0x4800 + ch * 8 + y]
                    for x in range(8):
                        px[c * 8 + x, row * 8 + y] = PAL[fg if b & (0x80 >> x) else bg]
    img.resize((640, 400), Image.NEAREST).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", action="store_true", help="leader only, no core on the link")
    ap.add_argument("--maxit", type=int, default=32)
    ap.add_argument("--maxcycles", type=int, default=2_000_000_000)
    a = ap.parse_args()

    args = [str(BUILD / "packsim"), str(CHARGEN), str(BUILD / "leader-auto.prg")]
    if not a.solo:
        args.append(str(BUILD / "core.prg"))
    args += [str(BUILD / "sim"), str(a.maxcycles)]
    r = subprocess.run(args, capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip())
    if r.returncode not in (0,):
        sys.exit("simulation did not finish")

    lead = (BUILD / "sim.0.bin").read_bytes()
    render(lead, BUILD / "sim-0.png")
    if not a.solo:
        core = (BUILD / "sim.1.bin").read_bytes()
        render(core, BUILD / "sim-1.png")

    bad, by = 0, {}
    for t in range(200):
        bm, off = tile_addr(t)
        want = ref_tile_bytes(t, a.maxit)
        if lead[bm:bm + 32] != want:
            bad += 1
            if bad <= 3:
                print(f"tile {t}: got {lead[bm:bm + 8].hex()} want {want[:8].hex()}")
        owner = PALSCR.index(lead[0x5C00 + off]) if lead[0x5C00 + off] in PALSCR else -1
        by[owner] = by.get(owner, 0) + 1
    print(f"picture check: {200 - bad}/200 tiles match the reference")
    print("tiles by core (last run): " + ", ".join(f"core {k}: {v}" for k, v in sorted(by.items())))

    s = sym(BUILD / "leader-auto.sym")
    rcyc, rten = s["rcyc"], s["rten"]
    t1 = None
    for k in range(8):
        cyc = int.from_bytes(lead[rcyc + 4 * k:rcyc + 4 * k + 4], "little")
        ten = int.from_bytes(lead[rten + 2 * k:rten + 2 * k + 2], "little")
        if cyc:
            t1 = t1 or cyc
            print(f"{k + 1} core{'s' if k else ' '}: {cyc:>11,} cycles = {ten / 10:6.1f} s   "
                  f"speed-up {t1 / cyc:.3f}x")


if __name__ == "__main__":
    main()
