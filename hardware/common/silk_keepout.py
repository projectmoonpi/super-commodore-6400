"""Keep vias out from under the silkscreen.

A via is a drilled hole: any printing that crosses one is cut away by the board maker, even when the via is tented.
So, before routing, every piece of silkscreen (part numbers, descriptors, part outlines, logos, art, dashed lines) gets
a no-via rule area under it, on both sides (a via goes through both). Tracks may still run under the printing: the
solder mask covers them.

    <KiCad python> silk_keepout.py board.kicad_pcb            add the no-via areas (replaces an earlier run's)
    <KiCad python> silk_keepout.py board.kicad_pcb --no-refs  the same, leaving the part numbers (placed after routing)
    <KiCad python> silk_keepout.py board.kicad_pcb --check    list any silkscreen that crosses a via
"""
import sys

import pcbnew

MM = pcbnew.FromMM
NAME = "silk keep-out"
MARGIN = 0.15            # how far beyond the printing a via must stay


def silk_shapes(board, refs=True):
    """Everything printed on either side, as one SHAPE_POLY_SET (letters and drawn shapes). refs=False leaves the
    part numbers out (for a generator that places vias before the numbers are placed)."""
    ps = pcbnew.SHAPE_POLY_SET()
    silk = (pcbnew.F_SilkS, pcbnew.B_SilkS)

    def box(item):
        bb = item.GetBoundingBox()
        o = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()),
                     (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
            o.Append(x, y)
        o.SetClosed(True)
        ps.AddOutline(o)

    def shape(item, layer):
        try:
            item.TransformShapeToPolygon(ps, layer, 0, MM(0.01), pcbnew.ERROR_OUTSIDE)
        except Exception:                                   # noqa: BLE001  (older signature or odd item: its box)
            box(item)

    def text(t):
        """The letters themselves (their strokes), not the whole box round the text."""
        try:
            t.TransformTextToPolySet(ps, 0, MM(0.01), pcbnew.ERROR_OUTSIDE)
        except Exception:                                   # noqa: BLE001
            box(t)

    lines = set()                                         # the part numbers' dashed lines (labels.py's group)
    if not refs:
        for g in board.Groups():
            if g.GetName() == "part-number-lines":
                lines |= {it.m_Uuid.AsString() for it in g.GetItems()}
    for d in board.GetDrawings():
        if d.GetLayer() not in silk or d.m_Uuid.AsString() in lines:
            continue
        if d.GetClass() in ("PCB_TEXT", "PCB_TEXTBOX"):
            text(d)
        else:
            shape(d, d.GetLayer())
    for fp in board.GetFootprints():
        for t in ((fp.Reference(), fp.Value()) if refs else (fp.Value(),)):
            if t.IsVisible() and t.GetLayer() in silk:
                text(t)
        for g in fp.GraphicalItems():
            if g.GetLayer() not in silk:
                continue
            if g.GetClass() in ("PCB_TEXT", "PCB_TEXTBOX", "PCB_FIELD"):
                if g.IsVisible():
                    text(g)
            else:
                shape(g, g.GetLayer())
    ps.Simplify()
    return ps


def _boxes(ps, tile=1.0):
    """Cover a silk polygon set with plain rectangles (Freerouting chokes on thousands of curved outlines): one box
    per outline, or, for a sparse outline (a part's outline frame, a long slanted line), the 1 mm tiles it touches."""
    out = []
    T = MM(tile)
    for i in range(ps.OutlineCount()):
        o = ps.COutline(i)
        bb = o.BBox()
        x0, y0, x1, y1 = bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()
        w, h = x1 - x0, y1 - y0
        one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(o)
        for hh in range(ps.HoleCount(i)):
            one.AddHole(ps.CHole(i, hh))
        area = one.Area()
        if w * h <= 0 or (area >= 0.45 * w * h and ps.HoleCount(i) == 0) or max(w, h) <= T * 1.5:
            out.append((x0, y0, x1, y1))
            continue
        nx, ny = max(1, -(-w // T)), max(1, -(-h // T))
        sx, sy = w / nx, h / ny
        for a in range(int(nx)):
            for b in range(int(ny)):
                tx0, ty0 = int(x0 + a * sx), int(y0 + b * sy)
                tx1, ty1 = int(x0 + (a + 1) * sx), int(y0 + (b + 1) * sy)
                t = pcbnew.SHAPE_POLY_SET(); t.NewOutline()
                for x, y in ((tx0, ty0), (tx1, ty0), (tx1, ty1), (tx0, ty1)):
                    t.Append(x, y)
                t.BooleanIntersection(one)
                if t.OutlineCount():
                    tb = t.BBox()
                    out.append((tb.GetLeft(), tb.GetTop(), tb.GetRight(), tb.GetBottom()))
    return out


def _rect(x0, y0, x1, y1):
    r = pcbnew.SHAPE_POLY_SET(); r.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        r.Append(int(x), int(y))
    return r


def add(board, margin=MARGIN, via_gap=0.35, refs=True):
    """refs=False: only the fixed printing (names, logos, art, outlines); for a board whose part numbers are placed
    after routing, round the vias (labels.place(via_cost=None)), where numbers + dashed lines would starve the router."""
    for z in [z for z in board.Zones() if z.GetIsRuleArea() and z.GetZoneName() == NAME]:
        board.Delete(z)
    keep = silk_shapes(board, refs)
    m = MM(margin)
    ps = pcbnew.SHAPE_POLY_SET()
    for x0, y0, x1, y1 in _boxes(keep):
        ps.BooleanAdd(_rect(x0 - m, y0 - m, x1 + m, y1 + m))
    # vias already on the board (a generator's fan-out) that clear the printing itself: a square hole round each,
    # wide enough that the router's own clearance doesn't count the via as sitting in the no-via area
    holes = pcbnew.SHAPE_POLY_SET()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            r = t.GetWidth(pcbnew.F_Cu) // 2
            if not keep.Collide(t.GetPosition(), r):
                g = r + MM(via_gap); p = t.GetPosition()
                holes.BooleanAdd(_rect(p.x - g, p.y - g, p.x + g, p.y + g))
    if holes.OutlineCount():
        ps.BooleanSubtract(holes)
    ps.Simplify()
    n = 0
    for i in range(ps.OutlineCount()):
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowTracks(False); z.SetDoNotAllowZoneFills(False)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        z.SetZoneName(NAME)
        o = z.Outline()                    # built inside the zone (a SetOutline'd copy would be freed by Python)
        o.AddOutline(ps.COutline(i))
        for h in range(ps.HoleCount(i)):
            o.AddHole(ps.CHole(i, h))
        board.Add(z)
        n += 1
    return n


def check(board):
    """(via position, net) for every via that sits under silkscreen."""
    ps = silk_shapes(board)
    out = []
    for t in board.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        r = t.GetWidth(pcbnew.F_Cu) // 2
        p = t.GetPosition()
        if ps.Collide(pcbnew.VECTOR2I(p.x, p.y), r):
            out.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), t.GetNetname()))
    return out


if __name__ == "__main__":
    path = sys.argv[1]
    b = pcbnew.LoadBoard(path)
    if "--check" in sys.argv:
        bad = check(b)
        print(f"silkscreen over vias: {len(bad)}" + "".join(f"\n  via at ({x:.2f}, {y:.2f}) {n}" for x, y, n in bad[:40]))
        sys.exit(1 if bad else 0)
    n = add(b, refs="--no-refs" not in sys.argv)
    pcbnew.SaveBoard(path, b)
    pts = sum(z.Outline().FullPointCount() for z in b.Zones() if z.GetZoneName() == NAME)
    print(f"silk keep-out: {n} no-via area(s) under the silkscreen, {pts} corners")
