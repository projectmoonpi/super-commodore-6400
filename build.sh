#!/bin/bash
# Build the Super Commodore 6400 programs and the disk, then test them in the two-machine simulator.
#   build/sc6400.d64   "PACK LEADER" (the C64 you watch) and "PACK CORE" (every other C64)
#   build/sc6400-leader.crt, build/sc6400-core.crt   the same two as cartridge images
# ./build.sh --nosim skips the simulator test.
set -e
cd "$(dirname "$0")"
mkdir -p build
acme -v1 -l build/job.sym src/job.asm
acme -v1 -l build/core.sym src/core.asm
acme -v1 -l build/leader.sym src/leader.asm
acme -v1 -f cbm -DAUTO=1 -l build/leader-auto.sym -o build/leader-auto.prg src/leader.asm 2>&1 | grep -v "already chosen" || true
c1541 -format "super c6400,64" d64 build/sc6400.d64 \
  -write build/leader.prg "pack leader" -write build/core.prg "pack core" </dev/null >/dev/null
python3 tools/make_crt.py
cc -O2 -Wall -o build/packsim tools/packsim.c
ls -l build/leader.prg build/core.prg build/sc6400.d64 build/*.crt
if [ "$1" != "--nosim" ]; then
  python3 tools/simcheck.py
fi
