"""Stage 2: autoroute with Freerouting, then add ground fills. Run with KiCad's Python. (S.M.B.B. copy: neckdown on, so
the 0.5 mm ground and supply tracks narrow where they meet a fine-pitch chip pin.)"""
import os
import random
import re
import subprocess
import sys
import time

import pcbnew

PCB = sys.argv[1]
MM = pcbnew.FromMM

def shuffle_nets(path, seed):
    """Freerouting is deterministic: the same .dsn always routes the same way. Its result depends on the order
    of the nets, though, so each new attempt gets the nets in a different order: sorted by name first (KiCad's own
    order changes between runs), then shuffled with the attempt number as the seed, so attempt N is repeatable."""
    lines = open(path).read().split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip() == "(network")
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("    (class "))
    blocks, cur = [], []
    for l in lines[start + 1:end]:
        cur.append(l)
        if l == "    )":
            blocks.append(cur)
            cur = []
    assert not cur, "unexpected .dsn layout"
    blocks.sort(key=lambda b: b[0])          # a fixed starting order: KiCad's varies run to run
    if seed > 1:
        random.Random(seed).shuffle(blocks)
    lines[start + 1:end] = [l for b in blocks for l in b]
    open(path, "w").write("\n".join(lines))


def gnd_zone(board, layer):
    """A ground pour over the whole board on one layer. On the back (B.Cu) it goes in before routing: Freerouting
    then treats GND as a plane and drops a via from each ground pin to it, instead of drawing ground tracks."""
    gnd = board.FindNet("GND") or board.FindNet("/GND")
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET(); ls.AddLayer(layer); z.SetLayerSet(ls); z.SetNet(gnd)
    z.SetLocalClearance(MM(0.3)); z.SetMinThickness(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)   # no ground copper left cut off by tracks
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
    ol = z.Outline(); ol.NewOutline()
    bb = board.GetBoardEdgesBoundingBox()
    W, H = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    for x, y in [(0.6, 0.6), (W - 0.6, 0.6), (W - 0.6, H - 0.6), (0.6, H - 0.6)]:
        ol.Append(MM(x), MM(y))
    board.Add(z)


MIN_TRACK = 0.15


def fix_vias(board):
    """A via brought back from Freerouting can get its net class's drill on a smaller via (a 0.6 mm via with a
    0.6 mm hole: no copper ring). Any via whose ring is under 0.15 mm gets the small via's 0.3 mm drill; any track
    narrowed below the board's minimum goes back up to it."""
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetWidth() - t.GetDrillValue() < MM(0.3):
            t.SetDrill(MM(0.3) if t.GetWidth() <= MM(0.9) else t.GetWidth() - MM(0.6))
        elif t.GetClass() == "PCB_TRACK" and t.GetWidth() < MM(MIN_TRACK):
            t.SetWidth(MM(MIN_TRACK))       # neckdown halves a 0.25 mm track to 0.125: the board's minimum is 0.15


MARGIN = float(os.environ.get("ROUTE_MARGIN", "0.05"))   # Freerouting lands a few hundredths inside its clearance


def bump(board, d):
    """Every net class's clearance up (or back down) by d mm: the router is given a little more room than the rules."""
    ns = board.GetDesignSettings().m_NetSettings
    classes = [ns.GetDefaultNetclass()] + [ns.GetNetClassByName(n) for n in ns.GetNetclasses()]
    for nc in classes:
        if nc is not None:
            nc.SetClearance(nc.GetClearance() + MM(d))


TIMEOUT = int(os.environ.get("ROUTE_TIMEOUT", "3600"))   # seconds per Freerouting run
# ROUTE_OPT_ALL=1: every attempt with Freerouting's optimizer on (slower; a dense board like the timing module needs it
# to finish its last few connections)
OPT_ALL = os.environ.get("ROUTE_OPT_ALL", "0") == "1"
ATTEMPTS = int(os.environ.get("ROUTE_ATTEMPTS", "12"))
FIRST_SEED = int(os.environ.get("ROUTE_SEED", "1"))     # try other net orders: ROUTE_SEED=13 bash build.sh
PARALLEL = int(os.environ.get("ROUTE_PARALLEL", "4"))   # net orders routed side by side (routing uses one core each)
OPTIMIZE = os.environ.get("ROUTE_OPTIMIZE", "1") == "1"  # tidy the winning route once at the end
OUT = os.path.dirname(os.path.abspath(PCB))
WORK = os.path.join(OUT, "route_work")
os.makedirs(WORK, exist_ok=True)
FR = os.path.expanduser("~/.local/bin/freerouting")
FR_ARGS = ["--router.autorouter.max_passes=200", "--router.automatic_neckdown=true", "--gui.enabled=false"]


def start(name, dsn, optimize):
    """Freerouting on one .dsn, in the background. The optimizer (its slow, many-core tidy-up stage) stays off while
    net orders are being tried: it never changes whether a board routes, only how neat the tracks are."""
    ses = os.path.join(WORK, name + ".ses")
    logp = os.path.join(WORK, name + ".log")
    if os.path.exists(ses):
        os.remove(ses)
    log = open(logp, "w")
    args = [FR, "-de", dsn, "-do", ses] + FR_ARGS + [f"--router.optimizer.enabled={'true' if optimize else 'false'}"]
    return dict(name=name, ses=ses, log=logp, fh=log, t0=time.time(),
                proc=subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, cwd=WORK))


def finish(job):
    """Wait for a run; True if it wrote a result. Its log is added to out/route.log either way."""
    try:
        job["proc"].wait(timeout=max(1, TIMEOUT - (time.time() - job["t0"])))
    except subprocess.TimeoutExpired:
        job["proc"].kill(); job["proc"].wait()
    job["fh"].close()
    with open(os.path.join(OUT, "route.log"), "a") as log:
        log.write(f"\n===== {job['name']} =====\n" + open(job["log"]).read())
    return os.path.exists(job["ses"])


def fr_result(job):
    """Freerouting's own verdict, (unrouted, violations), from the last 'stage completed' line of its log.
    (KiCad's unrouted count is no use here: it includes every ground pin until the fill goes in.)"""
    res, fixed = None, 0
    for line in open(job["log"]):
        m = re.search(r"stage completed.*?\((\d+) unrouted and (\d+) violations\)", line)
        if m:
            res = (int(m.group(1)), int(m.group(2)))
        m = re.search(r"Board has (\d+) pre-existing clearance violation", line)
        if m:                                    # the generator's own fixed vias, which no route can change (KiCad's
            fixed = int(m.group(1))              # DRC is the judge of those): only the router's own count
    return (res[0], max(0, res[1] - fixed)) if res else (999, 999)


def load_routed(base_path, ses):
    b = pcbnew.LoadBoard(base_path)
    if not pcbnew.ImportSpecctraSES(b, ses):
        return None
    fix_vias(b)
    b.BuildConnectivity()
    return b


def ground_left(ses):
    """How many connections a route leaves once the ground is poured on both sides: tracks can fence off a patch
    of ground, and two complete routes can differ here."""
    b = load_routed(BASE, ses)
    if b is None:
        return 999
    gnd_zone(b, pcbnew.F_Cu)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    return b.GetConnectivity().GetUnconnectedCount(False)


def export(board, path, seed):
    bump(board, MARGIN)
    assert pcbnew.ExportSpecctraDSN(board, path), "DSN export failed"
    bump(board, -MARGIN)
    shuffle_nets(path, seed)


# the starting board: ground plane on the back (Freerouting then drops a via to it instead of routing GND)
base = pcbnew.LoadBoard(PCB)
gnd_zone(base, pcbnew.B_Cu)
BASE = os.path.join(WORK, "base.kicad_pcb")
pcbnew.SaveBoard(BASE, base)

# 1. net orders, PARALLEL at a time, optimizer off; stop once one routes everything cleanly
best = None                     # (score, seed, board)
seeds = list(range(FIRST_SEED, FIRST_SEED + ATTEMPTS))
while seeds and not (best and best[0] == (0, 0, 0)):
    batch, seeds = seeds[:PARALLEL], seeds[PARALLEL:]
    jobs = []
    for seed in batch:
        dsn = os.path.join(WORK, f"attempt{seed}.dsn")
        export(pcbnew.LoadBoard(BASE), dsn, seed)
        jobs.append((seed, start(f"attempt{seed}", dsn, optimize=OPT_ALL)))
    print(f"routing net orders {batch[0]}-{batch[-1]} side by side...", flush=True)
    for seed, job in jobs:
        if not finish(job):
            print(f"routing attempt {seed}: no result (ran past {TIMEOUT} s)", flush=True)
            continue
        score = fr_result(job)
        if score[:2] == (0, 0):                  # complete: does its ground come out whole after the fill?
            score = score + (ground_left(job["ses"]),)
        else:
            score = score + (999,)
        mins = (time.time() - job["t0"]) / 60
        print(f"routing attempt {seed}: {score[0]} unrouted, {score[1]} violation(s), "
              f"{score[2] if score[2] < 999 else '-'} left after the ground fill  ({mins:.0f} min)", flush=True)
        if best is None or score < best[0]:
            b = load_routed(BASE, job["ses"])
            if b is not None:
                best = (score, seed, b)
if best is None:
    sys.exit("no routing attempt finished: the board is left as it was")
score, seed, board = best

finished = 0
# 2. finishing passes: a nearly routed board goes back with its tracks in place, to find the last few connections
for extra in range(1, int(os.environ.get("FINISH_PASSES", "3")) + 1):
    if score[0] == 0 or score[0] > int(os.environ.get("FINISH_MAX", "5")):
        break
    keep = os.path.join(WORK, "best.kicad_pcb")
    pcbnew.SaveBoard(keep, board)
    dsn = os.path.join(WORK, f"finish{extra}.dsn")
    export(board, dsn, 1000 + extra)
    job = start(f"finish{extra}", dsn, optimize=OPT_ALL)
    if not finish(job):
        break
    now = fr_result(job)
    print(f"finishing pass {extra}: {now[0]} unrouted, {now[1]} violation(s)", flush=True)
    if now < score[:2]:
        trial = load_routed(keep, job["ses"])
        if trial is not None:
            score, board = now + (999,), trial
            finished += 1

# 3. the optimizer, once: the winning net order routed again from its own .dsn with the optimizer on (a routed board
# can't go back in: re-exported, Freerouting loses ~200 of its connections and starts over). Kept only if nothing got
# worse. Skipped when the winner needed finishing passes (their tracks came from a re-export too).
if OPTIMIZE and score == (0, 0, 0) and finished == 0:
    print("optimizing: net order %d again, optimizer on..." % seed, flush=True)
    job = start("optimize", os.path.join(WORK, f"attempt{seed}.dsn"), optimize=True)
    if finish(job):
        now = fr_result(job)
        trial = load_routed(BASE, job["ses"])
        if trial is not None and now <= score[:2] and ground_left(job["ses"]) <= score[2]:
            board = trial
            print(f"optimized: {now[0]} unrouted, {now[1]} violation(s)", flush=True)
        else:
            print(f"optimizer result not kept ({now[0]} unrouted, {now[1]} violation(s))", flush=True)
    else:
        print("optimizer ran out of time: keeping the unoptimized route", flush=True)

# ground fill on the top too (the back's plane went in before routing)
gnd_zone(board, pcbnew.F_Cu)
if board.GetCopperLayerCount() == 4 and board.FindNet("+1V1"):   # the timing module: its 3.3 V plane round the tracks (In1, ground,
                                                     # went in before routing)
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.In2_Cu); z.SetLayerSet(ls); z.SetNet(board.FindNet("+3V3"))
    z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetThermalReliefGap(MM(0.25)); z.SetThermalReliefSpokeWidth(MM(0.3))
    ol = z.Outline(); ol.NewOutline()
    bb = board.GetBoardEdgesBoundingBox()
    for x, y in [(0.4, 0.4), (pcbnew.ToMM(bb.GetWidth()) - 0.4, 0.4),
                 (pcbnew.ToMM(bb.GetWidth()) - 0.4, pcbnew.ToMM(bb.GetHeight()) - 0.4), (0.4, pcbnew.ToMM(bb.GetHeight()) - 0.4)]:
        ol.Append(MM(x), MM(y))
    board.Add(z)
    # the RP2350B's 1.1 V core: its own copper on the bottom layer under the chip (the fan-out's +1V1 vias land in it)
    u1 = board.FindFootprintByReference("U1")
    c = u1.GetPosition()
    cx, cy = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
    k = pcbnew.ZONE(board)
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.B_Cu); k.SetLayerSet(ls); k.SetNet(board.FindNet("+1V1"))
    k.SetAssignedPriority(1); k.SetLocalClearance(MM(0.2)); k.SetMinThickness(MM(0.2))
    k.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    o = k.Outline(); o.NewOutline()
    for x, y in ((cx - 8.5, cy - 8.5), (cx + 8.5, cy - 8.5), (cx + 8.5, cy + 8.5), (cx - 8.5, cy + 8.5)):
        o.Append(MM(x), MM(y))
    board.Add(k)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print("routed + filled:", PCB, "tracks:", len(board.GetTracks()))
