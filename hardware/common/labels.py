"""Part numbers on the silkscreen, every part labelled.

House rule (every board, every project): a number reads the same way as its part. A vertical part's number is
turned 90 degrees and sits above or below it (below first, so rows come out uniform); a flat part's number is flat.

Each part's reference goes right beside it (above, below, left or right, flat or turned) where it sits clear of
every pad, every other part's body, other printing and the board edge. Where there is no room beside it, the
number goes in the nearest clear spot with a short dashed line to its part (as on the M.O.S.S. breakout board).

The most crowded parts choose first (the ones with the fewest places their number could go), so a roomy part
never takes the only spot a tight one had.

    import labels; labels.place(board, skip={"J1", ...}, size=0.8)      # from a KiCad python script

Returns (beside, with_line, not_placed) lists of references.
"""
import math
import os

import pcbnew

MM, TO = pcbnew.FromMM, pcbnew.ToMM
GAP = 0.1           # label to its own part
CLEAR = 0.1         # label to anything else
PAD_LINE = 0.15     # dashed line to any pad (its half width, the mask opening, the silk clearance)
DASH = 0.4          # dash length (and the gap between dashes)
LINE_W = 0.15     # the board maker's finest silkscreen line
MAX_LINE = 6.0      # longest dashed line
ROOMY = 6           # a part with this many clear spots right beside it skips the wider search
KEEP = 150          # the best places kept per part
GROUP = "part-number-lines"   # the dashed lines are kept in this group, so a second run replaces them


def _r(box, grow=0.0):
    return (TO(box.GetX()) - grow, TO(box.GetY()) - grow,
            TO(box.GetX() + box.GetWidth()) + grow, TO(box.GetY() + box.GetHeight()) + grow)


def _grow(r, g):
    return (r[0] - g, r[1] - g, r[2] + g, r[3] + g)


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _union(rs):
    return (min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs))


def _seg_hits(p, q, r):
    """Does segment p-q pass through rect r? (Liang-Barsky clip)"""
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for pp, qq in ((-dx, p[0] - r[0]), (dx, r[2] - p[0]), (-dy, p[1] - r[1]), (dy, r[3] - p[1])):
        if pp == 0:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def _segs_cross(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def _near(r, p):
    return (min(max(p[0], r[0]), r[2]), min(max(p[1], r[1]), r[3]))


LINES = {}          # ref -> its dashed line's segments (the last place() run), so a board script can redraw one


def dashed(board, p, q, layer, group=None):
    """A dashed line from p to q (mm), a dash at both ends; returns its segments."""
    L = math.hypot(q[0] - p[0], q[1] - p[1])
    k = max(3, int(round(L / DASH)))
    k += (k + 1) % 2                                    # odd: a dash at both ends
    if group is None:
        group = next((g for g in board.Groups() if g.GetName() == GROUP), None)
    segs = []
    for i in range(0, k, 2):
        s0 = (p[0] + (q[0] - p[0]) * i / k, p[1] + (q[1] - p[1]) * i / k)
        s1 = (p[0] + (q[0] - p[0]) * (i + 1) / k, p[1] + (q[1] - p[1]) * (i + 1) / k)
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT); seg.SetLayer(layer); seg.SetWidth(MM(LINE_W))
        seg.SetStart(pcbnew.VECTOR2I(MM(s0[0]), MM(s0[1]))); seg.SetEnd(pcbnew.VECTOR2I(MM(s1[0]), MM(s1[1])))
        board.Add(seg)
        if group is not None:
            group.AddItem(seg)
        segs.append(seg)
    return segs


def place(board, skip=(), size=0.8, thickness=None, step=0.25, max_line=MAX_LINE, via_cost=0.4, width=None):
    """width: letter width in mm (narrower than size = condensed text: the same legible height in less room)."""
    thickness = thickness or size * 0.15
    width = width or size
    for g in list(board.Groups()):                          # an earlier run's dashed lines
        if g.GetName() == GROUP:
            for it in list(g.GetItems()):
                board.Delete(it)
            board.Delete(g)
    e = _r(board.GetBoardEdgesBoundingBox())
    inside = (e[0] + 0.5, e[1] + 0.5, e[2] - 0.5, e[3] - 0.5)
    outline = pcbnew.SHAPE_POLY_SET()                       # the board itself: not in a cut-out or a notch
    have_outline = board.GetBoardPolygonOutlines(outline, False)
    fps = [fp for fp in board.GetFootprints() if len(fp.Pads())]

    # ---- the fixed things on each side: pads, part bodies, printing, vias
    sides = {}
    for side, cu, silk, fab in ((0, pcbnew.F_Cu, pcbnew.F_SilkS, pcbnew.F_Fab),
                                (1, pcbnew.B_Cu, pcbnew.B_SilkS, pcbnew.B_Fab)):
        pads, bodies, pieces, printed = [], {}, {}, []
        for fp in fps:
            ref, mine = fp.GetReference(), []
            for p in fp.Pads():
                if p.IsOnLayer(cu):
                    r = _r(p.GetBoundingBox())
                    pads.append((r, ref)); mine.append(r)
            for g in fp.GraphicalItems():
                if (g.GetLayer() == fab or g.GetLayer() == silk) and (1 if fp.IsFlipped() else 0) == side:
                    mine.append(_r(g.GetBoundingBox()))
                if g.GetLayer() == silk:
                    printed.append((_r(g.GetBoundingBox()), ref))
            if (1 if fp.IsFlipped() else 0) == side and mine:
                bodies[ref] = _union(mine)                  # its own outline, to sit beside
                pieces[ref] = mine                          # what others must keep off, piece by piece
            t = fp.Reference()                              # the numbers we leave alone count as printing
            if ref in skip and t.IsVisible() and t.GetLayer() == silk:
                printed.append((_r(t.GetBoundingBox()), None))
        for d in board.GetDrawings():
            if d.GetLayer() == silk:
                printed.append((_r(d.GetBoundingBox()), None))
            elif d.GetLayer() == pcbnew.Edge_Cuts:          # the edges, inner cut-outs and notches too
                printed.append((_grow(_r(d.GetBoundingBox()), 0.3), None))
        vias = [_r(t.GetBoundingBox()) for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
        sides[side] = dict(pads=pads, bodies=bodies, pieces=pieces, printed=printed, vias=vias, silk=silk,
                           labels=[], lines=[])

    todo = [fp for fp in fps
            if fp.GetReference() not in skip and fp.GetReference() in sides[(1 if fp.IsFlipped() else 0)]["bodies"]]
    dims = {}
    for fp in todo:
        t = fp.Reference()
        t.SetVisible(True); t.SetLayer(sides[(1 if fp.IsFlipped() else 0)]["silk"]); t.SetMirrored((1 if fp.IsFlipped() else 0) == 1)
        t.SetTextSize(pcbnew.VECTOR2I(MM(width), MM(size))); t.SetTextThickness(MM(thickness))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        t.SetKeepUpright(False)
        d = {}
        for ang in (0, 90):
            t.SetTextAngleDegrees(ang); t.SetPosition(pcbnew.VECTOR2I(0, 0))
            bb = _r(t.GetBoundingBox())
            d[ang] = (bb[2] - bb[0], bb[3] - bb[1])
        dims[fp.GetReference()] = d

    # ---- every place each number could go, checked against the fixed things
    def candidates(fp, max_line=max_line, wide=False):
        ref = fp.GetReference(); S = sides[(1 if fp.IsFlipped() else 0)]; b = S["bodies"][ref]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        reach = _grow(b, max_line + 3)
        pads = [(r, k) for r, k in S["pads"] if _hit(r, reach)]
        bodies = [(k, r) for k, rs in S["pieces"].items() if k != ref for r in rs if _hit(r, reach)]
        bodies.append((ref, b))
        printed = [(r, k) for r, k in S["printed"] if k != ref and _hit(r, reach)]
        vias = [v for v in S["vias"] if _hit(v, reach)]

        def box_ok(box):
            if not (inside[0] <= box[0] and box[2] <= inside[2] and inside[1] <= box[1] and box[3] <= inside[3]):
                return None
            if have_outline and not outline.Contains(
                    pcbnew.VECTOR2I(MM((box[0] + box[2]) / 2), MM((box[1] + box[3]) / 2))):
                return None
            g = _grow(box, CLEAR)
            if any(_hit(g, r) for r, _ in pads):
                return None
            if any(_hit(box if k == ref else g, bb) for k, bb in bodies):
                return None
            if any(_hit(g, r) for r, _ in printed):
                return None
            if any(_hit(box, v) for v in vias):
                return None if via_cost is None else via_cost    # None: never over a via (its hole cuts the print)
            return 0.0                                                       # how much a via is avoided is the board's call

        # the house rule: a number reads the same way as its part. A vertical part gets its number turned 90 and
        # above or below it (below first, so a row of parts comes out uniform); a flat part gets a flat number.
        # Anything else is a fallback, kept only when the right spot is taken.
        bw, bh = b[2] - b[0], b[3] - b[1]
        orient = "v" if bh > bw * 1.15 else "h" if bw > bh * 1.15 else "sq"

        def fit(ang, side):
            if orient == "v":
                if ang == 90 and side in ("below", "above"):
                    return 0.0 if side == "below" else 0.05
                return 1.5 if ang == 90 else 2.2
            if orient == "h":
                if ang == 0:
                    return 0.0 if side == "below" else 0.05 if side == "above" else 0.3
                return 2.0
            return ang * 0.002 + (0.0 if side == "below" else 0.05)

        out = []
        for ang in (0, 90):
            w, h = dims[ref][ang]
            for slide in (0, -0.4, 0.4, -0.8, 0.8, -1.2, 1.2):
                for side, x, y in (("above", cx + slide, b[1] - GAP - h / 2), ("below", cx + slide, b[3] + GAP + h / 2),
                                   ("left", b[0] - GAP - w / 2, cy + slide), ("right", b[2] + GAP + w / 2, cy + slide)):
                    box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                    pen = box_ok(box)
                    if pen is not None:
                        out.append((abs(slide) * 0.3 + fit(ang, side) + pen, x, y, ang, box, None))
        if sum(1 for c in out if c[0] < 0.5) >= ROOMY and not wide:
            return out                                       # plenty of room beside it: no need to look further
        n = int((max_line + 1.5) / step)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                x, y = cx + i * step, cy + j * step
                for ang in (0, 90):
                    w, h = dims[ref][ang]
                    box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                    if _hit(_grow(box, GAP + 0.3), b):
                        continue                                       # that close, it's "beside" (done above)
                    pen = box_ok(box)
                    if pen is None:
                        continue
                    best = None
                    for z in (_near(b, (x, y)), ((b[0] + b[2]) / 2, b[1]), ((b[0] + b[2]) / 2, b[3]),
                              (b[0], (b[1] + b[3]) / 2), (b[2], (b[1] + b[3]) / 2)):
                        a = _near(box, z)
                        L = math.hypot(z[0] - a[0], z[1] - a[1])
                        if L < 1.15 or L > max_line:
                            continue
                        ux, uy = (z[0] - a[0]) / L, (z[1] - a[1]) / L
                        p, q = (a[0] + ux * 0.12, a[1] + uy * 0.12), (z[0] - ux * 0.3, z[1] - uy * 0.3)
                        if _seg_hits(p, q, _grow(b, 0.15)):            # not skimming along its own part
                            continue
                        if any(_seg_hits(p, q, _grow(r, PAD_LINE)) for r, k in pads if k != ref):
                            continue
                        if any(_seg_hits(p, q, _grow(bb, 0.1)) for k, bb in bodies if k != ref):   # clear of others: no mix-ups
                            continue
                        if any(_seg_hits(p, q, _grow(r, 0.1)) for r, _ in printed):
                            continue
                        if via_cost is None and any(_seg_hits(p, q, _grow(v, 0.1)) for v in vias):
                            continue                                    # a dashed line over a via loses dashes
                        if best is None or L < best[0]:
                            best = (L, p, q)
                    if best:
                        turned = (orient == "v" and ang != 90) or (orient == "h" and ang != 0)
                        out.append((3.0 + best[0] + pen + (0.5 if turned else 0.0), x, y, ang, box,
                                    (best[1], best[2])))
        return out

    def conflict(c1, c2):
        """Do two placed numbers (with their lines) get in each other's way?"""
        _, _, _, _, b1, l1 = c1
        _, _, _, _, b2, l2 = c2
        if _hit(_grow(b1, CLEAR), b2):
            return True
        if l1 and _seg_hits(l1[0], l1[1], _grow(b2, 0.1)):
            return True
        if l2 and _seg_hits(l2[0], l2[1], _grow(b1, 0.1)):
            return True
        if l1 and l2 and _segs_cross(l1[0], l1[1], l2[0], l2[1]):
            return True
        return False

    side_of = {fp.GetReference(): (1 if fp.IsFlipped() else 0) for fp in todo}
    all_c = {fp.GetReference(): sorted(candidates(fp), key=lambda c: c[0])[:KEEP] for fp in todo}
    placed = {}

    def free(ref, c, ignore=()):
        return not any(conflict(c, pc) for r, pc in placed.items()
                       if r not in ignore and r != ref and side_of[r] == side_of[ref])

    left = sorted(all_c)
    lost = []
    live = {r: list(all_c[r]) for r in left}
    newest = None
    while left:
        if newest:
            nr, nc = newest
            for r in left:
                if side_of[r] == side_of[nr]:
                    live[r] = [c for c in live[r] if not conflict(c, nc)]

        def rank(r):                                         # the most crowded first: fewest good choices
            good = sum(1 for c in live[r] if c[0] < 3.0)
            return (good if good else 1000 + len(live[r]), live[r][0][0] if live[r] else 0)
        ref = min(left, key=rank)
        left.remove(ref)
        if live[ref]:
            placed[ref] = live[ref][0]; newest = (ref, live[ref][0])
        else:
            lost.append(ref); newest = None

    # the stuck ones may reach further (a longer dashed line), into whatever room is left
    for ref in list(lost):
        far = [c for c in sorted(candidates(next(f for f in todo if f.GetReference() == ref), max_line * 1.5, True),
                                 key=lambda c: c[0]) if free(ref, c)]
        all_c[ref] = sorted(all_c[ref] + far, key=lambda c: c[0])
        if far:
            placed[ref] = far[0]; lost.remove(ref)

    # last: a little tighter (still clear of everything, by less) for the few still without a place
    global CLEAR, GAP
    keep = CLEAR, GAP
    CLEAR, GAP = 0.05, 0.05
    try:
        for ref in list(lost):
            tight = [c for c in sorted(candidates(next(f for f in todo if f.GetReference() == ref), wide=True),
                                       key=lambda c: c[0]) if free(ref, c)]
            all_c[ref] = sorted(all_c[ref] + tight, key=lambda c: c[0])
            if tight:
                placed[ref] = tight[0]; lost.remove(ref)
    finally:
        CLEAR, GAP = keep

    # repair: a number with nowhere to go takes a spot from ones that can go elsewhere, and so on (a few deep)
    def relocate(ref, depth, busy):
        for c in all_c[ref]:
            blockers = [r for r, pc in placed.items()
                        if r != ref and side_of[r] == side_of[ref] and conflict(c, pc)]
            if len(blockers) > 3 or any(r in busy for r in blockers):
                continue
            if blockers and depth == 0:
                continue
            saved = {r: placed.pop(r) for r in blockers}
            old = placed.get(ref)
            placed[ref] = c
            if all(relocate(r, depth - 1, busy | {ref} | set(blockers)) for r in blockers):
                return True
            for r in blockers:                               # undo
                placed[r] = saved[r]
            if old is None:
                del placed[ref]
            else:
                placed[ref] = old
        return False

    for ref in list(lost):
        snapshot = dict(placed)
        if relocate(ref, 4, frozenset()):
            lost.remove(ref)
        else:
            placed.clear(); placed.update(snapshot)

    if os.environ.get("LABEL_DEBUG"):
        for ref in lost:
            print("   ", ref, "places it could have gone:", len(all_c[ref]),
                  [(round(c[1], 2), round(c[2], 2), c[3], [r for r, pc in placed.items() if conflict(c, pc)])
                   for c in all_c[ref][:6]])
    group = pcbnew.PCB_GROUP(board); group.SetName(GROUP); board.Add(group)
    LINES.clear()
    by_ref = {fp.GetReference(): fp for fp in todo}
    beside, lined = [], []
    for ref in lost:
        by_ref[ref].Reference().SetVisible(False)
    for ref, (_, x, y, ang, box, line) in placed.items():
        fp = by_ref[ref]; t, S = fp.Reference(), sides[(1 if fp.IsFlipped() else 0)]
        t.SetTextAngleDegrees(ang); t.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        if line is None:
            beside.append(ref); continue
        p, q = line
        LINES[ref] = dashed(board, p, q, S["silk"], group)
        lined.append(ref)
    return beside, lined, lost
