"""Ground stitching: join any piece of the ground fill that ended up cut off from the rest.

The ground is poured on both sides after routing. Tracks can fence off a patch of it (with a ground pin or two in it)
from the main ground on that side. Wherever such a patch lies over the main ground on the OTHER side, a via joins
them. The via goes well inside both fills, so it keeps the fills' own clearance from every other net.

    <KiCad python> stitch.py out/hub-board.kicad_pcb       (build.sh runs it after routing)
"""
import sys

import pcbnew

MM = pcbnew.FromMM
VIA_D, VIA_DRILL = 0.6, 0.3
INSET = VIA_D / 2 + 0.1          # how far inside both fills the via's centre must be
RING = [(__import__("math").cos(a * 0.3927), __import__("math").sin(a * 0.3927)) for a in range(16)]


def P(v):
    """A plain copy of a KiCad point (SWIG hands back references into the board that can go stale)."""
    return pcbnew.VECTOR2I(int(v.x), int(v.y))


def pieces(board):
    """Every filled ground outline, as (layer, SHAPE_POLY_SET with just that outline)."""
    out = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND":
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(layer):
                continue
            fp = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(layer))
            try:                                     # KiCad keeps the fill cut into strips: join them back up
                fp.Unfracture()
            except TypeError:
                fp.Unfracture(pcbnew.SHAPE_POLY_SET.PM_FAST)
            fp.Inflate(MM(0.01), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, MM(0.005))   # strips that only touch
            fp.Simplify()                                                                 # become one region
            fp.Inflate(-MM(0.01), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, MM(0.005))
            for i in range(fp.OutlineCount()):
                p = pcbnew.SHAPE_POLY_SET()
                p.AddOutline(fp.COutline(i))
                for h in range(fp.HoleCount(i)):
                    p.AddHole(fp.CHole(i, h))
                out.append((layer, p))
    return out


def joiners(board):
    """Points where ground passes between the two sides, or along one: GND vias and through-hole pads, and the
    ends of GND tracks."""
    pts = []                                  # (x, y, layers) with layers a set
    for t in board.GetTracks():
        if t.GetNetname() != "GND":
            continue
        if t.GetClass() == "PCB_VIA":
            r = pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
            pts.append((P(t.GetPosition()), {pcbnew.F_Cu, pcbnew.B_Cu}, (r + 0.15,)))
        else:
            pts.append((P(t.GetStart()), {t.GetLayer()}, P(t.GetEnd())))
    for fp in board.GetFootprints():
        for pd in fp.Pads():
            if pd.GetNetname() != "GND":
                continue
            sz = pd.GetSize(pcbnew.F_Cu) if pd.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else pd.GetSize(fp.GetLayer())
            lo, hi = sorted((pcbnew.ToMM(sz.x) / 2, pcbnew.ToMM(sz.y) / 2))
            layers = {pcbnew.F_Cu, pcbnew.B_Cu} if pd.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else {fp.GetLayer()}
            pts.append((P(pd.GetPosition()), layers, (lo + 0.15, hi + 0.15)))
    return pts


def groups(ps, joins):
    parent = list(range(len(ps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def at(pt, layers, r=0.0):
        """Pieces at a point; with r, pieces touching a ring round it (a pin or via meets the fill by its
        spokes, and its centre sits in the relief gap)."""
        if not r:
            return [i for i, (l, p) in enumerate(ps) if l in layers and p.Contains(pt, -1, MM(0.05))]
        ring = [pcbnew.VECTOR2I(int(pt.x + MM(rr * c)), int(pt.y + MM(rr * s_)))
                for rr in r for c, s_ in RING]
        return [i for i, (l, p) in enumerate(ps) if l in layers and any(p.Contains(q, -1, MM(0.02)) for q in ring)]

    for j in joins:
        if len(j) == 3 and isinstance(j[2], tuple):     # a pin or via: its size
            hit = at(j[0], j[1], j[2])
        elif len(j) == 2:
            hit = at(j[0], j[1])
        else:                                 # a track: the pieces under its two ends are joined
            hit = at(j[0], j[1]) + at(j[2], j[1])
        for a in hit[1:]:
            parent[find(a)] = find(hit[0])
    comp = {}
    for i in range(len(ps)):
        comp.setdefault(find(i), []).append(i)
    return list(comp.values())


def spot(a, b):
    """A point at least INSET inside both pieces, or None."""
    s = a.CloneDropTriangulation() if hasattr(a, "CloneDropTriangulation") else pcbnew.SHAPE_POLY_SET(a)
    s.BooleanIntersection(b)
    s.Inflate(-MM(INSET), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.01))
    best = None
    for i in range(s.OutlineCount()):
        o = s.COutline(i)
        bb = o.BBox()
        area = bb.GetWidth() * bb.GetHeight()
        if best is None or area > best[0]:
            c = bb.Centre()
            pt = P(c) if s.Contains(c) else P(o.CPoint(0))
            best = (area, pt)
    return best[1] if best else None


TIE_W = 0.4                      # a tie from a spoke-less ground pin out to the fill


TIE_CLEAR = 0.25                 # a tie's clearance to every other net (the board's rule is 0.2)


def clear(board, layer, a, b, w):
    """True when a track a-b of width w on this layer keeps TIE_CLEAR from every other net's copper."""
    seg = pcbnew.SHAPE_SEGMENT(a, b, MM(w))
    gap = MM(TIE_CLEAR)
    for fp in board.GetFootprints():
        for q in fp.Pads():
            if q.GetNetname() != "GND" and q.IsOnLayer(layer) and q.GetEffectiveShape(layer).Collide(seg, gap):
                return False
    for t in board.GetTracks():
        if t.GetNetname() != "GND" and t.IsOnLayer(layer) and t.GetEffectiveShape(layer).Collide(seg, gap):
            return False
    return True


def tie_orphans(board, ps):
    """A ground pin whose thermal relief got no spokes at all sits in its gap, touching no fill. A short track
    straight out to the fill joins it: only where every point of the track beyond the relief gap is inside the
    fill (shrunk by half the track), so it can't come near another net."""
    added = 0
    ends = [P(e) for t in board.GetTracks() if t.GetNetname() == "GND" and t.GetClass() == "PCB_TRACK"
            for e in (t.GetStart(), t.GetEnd())]
    for fp in board.GetFootprints():
        for pd in fp.Pads():
            if pd.GetNetname() != "GND":
                continue
            if any(pd.HitTest(e) for e in ends):           # a ground track already lands on it
                continue
            pth = pd.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
            layers = (pcbnew.F_Cu, pcbnew.B_Cu) if pth else (fp.GetLayer(),)
            sz = pd.GetSize(layers[0])
            lo, hi = sorted((pcbnew.ToMM(sz.x) / 2, pcbnew.ToMM(sz.y) / 2))
            c = P(pd.GetPosition())

            def pt(r, cs):
                return pcbnew.VECTOR2I(int(c.x + MM(r * cs[0])), int(c.y + MM(r * cs[1])))

            mine = [p for l, p in ps if l in layers]
            if any(p.Contains(pt(r, cs), -1, MM(0.02)) for p in mine for r in (lo + 0.15, hi + 0.15) for cs in RING):
                continue                                   # it has spokes
            done = False
            for layer in layers:
                for l, p in ps:
                    if l != layer or done:
                        continue
                    shrunk = pcbnew.SHAPE_POLY_SET(p)
                    shrunk.Inflate(-MM(TIE_W / 2 + 0.05), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.01))
                    for cs in sorted(RING, key=lambda d: (abs(d[0]) > 0.01 and abs(d[1]) > 0.01)):   # straight first
                        edge = hi if abs(cs[0]) > 0.01 and abs(cs[1]) > 0.01 else (
                            pcbnew.ToMM(sz.x) / 2 if abs(cs[0]) > 0.5 else pcbnew.ToMM(sz.y) / 2)
                        rs = [edge + 0.3 + 0.05 * k for k in range(13)]           # 0.6 mm of track in the fill
                        if all(shrunk.Contains(pt(r, cs)) for r in rs):
                            t = pcbnew.PCB_TRACK(board)
                            t.SetStart(c); t.SetEnd(pt(rs[-1], cs)); t.SetWidth(MM(TIE_W)); t.SetLayer(layer)
                            t.SetNet(board.FindNet("GND"))
                            board.Add(t)
                            added += 1
                            done = True
                            break
            if not done:                                   # else: straight to the nearest ground pin, if clear
                for other in sorted((q for f in board.GetFootprints() for q in f.Pads()
                                     if q.GetNetname() == "GND" and (q.GetPosition() - c).EuclideanNorm() > MM(0.5)),
                                    key=lambda q: (q.GetPosition() - c).EuclideanNorm()):
                    if (other.GetPosition() - c).EuclideanNorm() > MM(3.0):
                        break
                    oc = P(other.GetPosition())
                    for layer in layers:
                        if other.IsOnLayer(layer) and clear(board, layer, c, oc, TIE_W):
                            t = pcbnew.PCB_TRACK(board)
                            t.SetStart(c); t.SetEnd(oc); t.SetWidth(MM(TIE_W)); t.SetLayer(layer)
                            t.SetNet(board.FindNet("GND"))
                            board.Add(t)
                            added += 1
                            done = True
                            break
                    if done:
                        break
            if not done:
                print(f"  {fp.GetReference()} pin {pd.GetNumber()}: no room for a ground tie")
    return added


def stitch(board, rounds=4):
    added = 0
    for _ in range(rounds):
        filler = pcbnew.ZONE_FILLER(board)
        filler.Fill(board.Zones())
        ps = pieces(board)
        tied = tie_orphans(board, ps)
        if tied:
            added += tied
            continue                                       # refill with the ties in, then look again
        gs = groups(ps, joiners(board))
        if len(gs) <= 1:
            break
        area = lambda g: sum(ps[i][1].Area() for i in g)     # noqa: E731
        gs.sort(key=area, reverse=True)
        main = gs[0]
        new = 0
        for g in gs[1:]:
            for i in g:
                li, pi = ps[i]
                for m in main:
                    lm, pm = ps[m]
                    if lm == li:
                        continue
                    pt = spot(pi, pm)
                    if pt is not None and no_via_here(board, pt):
                        pt = None                               # under the silkscreen (or another no-via area)
                    if pt is None or any(t.GetClass() == "PCB_VIA" and (t.GetPosition() - pt).EuclideanNorm()
                                         < MM(VIA_D + 0.3) for t in board.GetTracks()):
                        continue
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(pt); v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL))
                    v.SetNet(board.FindNet("GND"))
                    board.Add(v)
                    new += 1
                    break
                else:
                    continue
                break
        added += new
        if not new:
            break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    ps = pieces(board)
    left = len(groups(ps, joiners(board))) - 1
    return added, left


def unconnected(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)


def no_via_here(board, pt):
    """True inside any no-via rule area (the silkscreen keep-outs, the edge keep-outs), via size included."""
    for z in board.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowVias() and z.Outline().Collide(pt, MM(VIA_D / 2)):
            return True
    return False


def via_ok(board, pt, outline):
    """Room for a ground via here: clear of other nets on both sides, of every hole, of the edges and keep-outs."""
    if not outline.Contains(pt):
        return False
    if no_via_here(board, pt):
        return False
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        if not clear(board, layer, pt, pt, VIA_D):
            return False
    for f in board.GetFootprints():
        for q in f.Pads():
            if q.GetDrillSize().x and (q.GetPosition() - pt).EuclideanNorm() < (q.GetDrillSize().x / 2
                                                                               + MM(VIA_D / 2 + 0.5)):
                return False
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" and (t.GetPosition() - pt).EuclideanNorm() < MM(VIA_D + 0.3):
            return False
    return True


def dedupe_vias(board):
    """Only one ground via per spot (an earlier stitch run may have stacked them)."""
    seen, gone = [], 0
    for t in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]:
        p = P(t.GetPosition())
        if any((p - q).EuclideanNorm() < MM(0.05) for q in seen):
            board.Delete(t)
            gone += 1
        else:
            seen.append(p)
    return gone


def both_fills(board, inset):
    """Points on a 0.5 mm grid that are at least `inset` inside the ground fill on both sides."""
    f, b = pcbnew.SHAPE_POLY_SET(), pcbnew.SHAPE_POLY_SET()
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND":
            continue
        if z.IsOnLayer(pcbnew.F_Cu):
            f.Append(z.GetFilledPolysList(pcbnew.F_Cu))
        if z.IsOnLayer(pcbnew.B_Cu):
            b.Append(z.GetFilledPolysList(pcbnew.B_Cu))
    for ps in (f, b):
        ps.Inflate(MM(0.01), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, MM(0.005))
        ps.Simplify()
        ps.Inflate(-MM(0.01 + inset), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, MM(0.005))
    f.BooleanIntersection(b)
    bb = f.BBox()
    out = []
    for x in range(bb.GetLeft(), bb.GetRight(), MM(0.5)):
        for y in range(bb.GetTop(), bb.GetBottom(), MM(0.5)):
            v = pcbnew.VECTOR2I(x, y)
            if f.Contains(v):
                out.append(v)
    return out


def bridge(board, tries=6, max_vias=300):
    """Last resort, checked by KiCad's own connectivity: from a ground pin that isn't on the main ground, a short
    ground track to a new via (nearest spots first); each try is kept only if the unrouted count drops."""
    added = 0
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    outline.Inflate(-MM(VIA_D / 2 + 0.6), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.01))
    gnd = board.FindNet("GND")
    for _ in range(tries):
        n = unconnected(board)
        if n == 0:
            break
        c = board.GetConnectivity()
        pads = [q for f in board.GetFootprints() for q in f.Pads() if q.GetNetname() == "GND"]
        size = {}
        for q in pads:
            size[q.m_Uuid.AsString()] = len(c.GetConnectedItems(q))
        main = max(size.values())
        loose = [q for q in pads if size[q.m_Uuid.AsString()] < main]
        done = False
        for q in loose:
            pc = P(q.GetPosition())
            spots = sorted(((r, cs) for r in (1.2, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0) for cs in RING), key=lambda x: x[0])
            # a plain track out to fill on the same side first, then a track and a via to the other side
            for with_via in (False, True):
                for r, cs in spots:
                    v = pcbnew.VECTOR2I(int(pc.x + MM(r * cs[0])), int(pc.y + MM(r * cs[1])))
                    if with_via and not via_ok(board, v, outline):
                        continue
                    if not with_via and not outline.Contains(v):
                        continue
                    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                        if not q.IsOnLayer(layer) or not clear(board, layer, pc, v, TIE_W):
                            continue
                        t = pcbnew.PCB_TRACK(board)
                        t.SetStart(pc); t.SetEnd(v); t.SetWidth(MM(TIE_W)); t.SetLayer(layer); t.SetNet(gnd)
                        board.Add(t)
                        via = None
                        if with_via:
                            via = pcbnew.PCB_VIA(board)
                            via.SetPosition(v); via.SetWidth(MM(VIA_D)); via.SetDrill(MM(VIA_DRILL)); via.SetNet(gnd)
                            board.Add(via)
                        if unconnected(board) < n:
                            added += 1
                            done = True
                            break
                        board.Delete(t)
                        if via is not None:
                            board.Delete(via)
                    if done:
                        break
                if done:
                    break
                if done:
                    break
            if done:
                break
        if not done:                                   # a via anywhere that's in the fill on both sides,
            spots = both_fills(board, INSET)           # nearest the loose pins first
            spots.sort(key=lambda v: min((v - P(q.GetPosition())).EuclideanNorm() for q in loose))
            tried = 0
            for v in spots:
                if tried >= max_vias:
                    break
                if not via_ok(board, v, outline):
                    continue
                tried += 1
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(v); via.SetWidth(MM(VIA_D)); via.SetDrill(MM(VIA_DRILL)); via.SetNet(gnd)
                board.Add(via)
                if unconnected(board) < n:
                    added += 1
                    done = True
                    break
                board.Delete(via)
        if not done:
            break
    return added, unconnected(board)


if __name__ == "__main__":
    path = sys.argv[1]
    b = pcbnew.LoadBoard(path)
    gone = dedupe_vias(b)
    if gone:
        print(f"  {gone} stacked via(s) removed")
    added, left = stitch(b)
    more, n = bridge(b)
    added += more
    left = n
    pcbnew.SaveBoard(path, b)
    print(f"ground stitching: {added} via(s)/tie(s) added"
          + (f", {left} connection(s) still unrouted" if left else ", all ground joined"))
