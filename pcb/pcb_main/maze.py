"""A small grid router for the last connections Freerouting leaves: for each net that is still in several pieces,
an A* search on F.Cu, B.Cu and, as a last resort, In1.Cu (0.1 mm grid, 8 directions, vias where a via fits) from one
piece to the next, keeping 0.2 mm from every other net, the board edge and the antenna keep-out. Routes start and end
on a pad centre, a via centre or a point on a track's centre line, so KiCad sees them connected.

  python3 maze.py in.kicad_pcb out.kicad_pcb
"""
import os, sys, math, heapq
import numpy as np
import pcbnew
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import P, Bf, mm, MM, polyset_to_shapely, board_outline, net_islands
from shapely.geometry import Point, LineString, box as sbox

G = float(os.environ.get("MAZE_GRID", "0.1")); X0, Y0 = -52.0, -42.0; NX, NY = int(100 / G), int(76 / G)
LAY = (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu)        # In1 (the +3V3 plane layer) only at a higher cost
LCOST = (1.0, 1.0, 1.2)
WIDTH = {"/VBUS": 0.4, "/SYS": 0.4, "/BAT": 0.4, "/LR_VDD": 0.4, "+3V3": 0.4}
CLR = 0.2
def cell(x, y): return int(round((y - Y0) / G)), int(round((x - X0) / G))

def raster(geoms, grow):
    """Cells whose centre lies within `grow` of a geometry (conservative by most of a cell)."""
    im = Image.new("1", (NX, NY), 0); d = ImageDraw.Draw(im)
    for g in geoms:
        g = g.buffer(grow + G * 0.71, quad_segs=4)
        for p in getattr(g, "geoms", [g]):
            if p.is_empty or p.geom_type != "Polygon": continue
            d.polygon([((x - X0) / G, (y - Y0) / G) for x, y in p.exterior.coords], fill=1)
    return np.array(im, dtype=bool)

def objects(b):
    """Every copper object: (net, layer, geometry, kind, extra) with kind pad/track/via; vias and PTH pads on every layer."""
    out = []
    for f in b.GetFootprints():
        for p in f.Pads():
            g = polyset_to_shapely(p.GetEffectivePolygon())
            if g.is_empty: continue
            for L in LAY:
                if p.IsOnLayer(L) or p.HasHole(): out.append((p.GetNetname(), L, g, "pad", ((f.GetReference(), p.GetNumber()), Bf(p.GetPosition()))))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c = Bf(t.GetPosition()); g = Point(c).buffer(mm(t.GetWidth()) / 2)
            for L in LAY: out.append((t.GetNetname(), L, g, "via", c))
        elif t.GetLayer() in LAY:
            ln = LineString([Bf(t.GetStart()), Bf(t.GetEnd())])
            out.append((t.GetNetname(), t.GetLayer(), ln.buffer(mm(t.GetWidth()) / 2), "track", ln))
    return out

def keepouts(b):
    """Rule areas (the board's and the footprints', e.g. under a U.FL): track and via keep-out polygons per layer."""
    zs = list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]
    trk = {L: [] for L in LAY}; via = []
    for z in zs:
        if not z.GetIsRuleArea(): continue
        g = polyset_to_shapely(z.Outline())
        if g.is_empty: continue
        for L in LAY:
            if z.IsOnLayer(L) and z.GetDoNotAllowTracks(): trk[L].append(g)
        if z.GetDoNotAllowVias() and any(z.IsOnLayer(L) for L in LAY): via.append(g)
    return trk, via

def pieces_of(net, islands, objs):
    mine = [o for o in objs if o[0] == net]
    res = []
    for isl in islands:
        refs = set(map(tuple, isl))
        got = [o for o in mine if o[3] == "pad" and o[4][0] in refs]
        rest = [o for o in mine if o[3] != "pad"]
        grown = True
        while grown:
            grown = False
            for o in list(rest):
                if any(o2[2].distance(o[2]) < 0.005 and (o[3] == "via" or o2[3] == "via" or o2[1] == o[1]) for o2 in got):
                    got.append(o); rest.remove(o); grown = True
        res.append(got)
    return res

def masks(piece):
    region = {L: raster([o[2] for o in piece if o[1] == L], -0.05) for L in LAY}
    padreg = raster([o[2] for o in piece if o[3] == "pad" and o[1] in LAY[:2]], 0.22)       # no new via in or right next to a pad
    anchor = {L: np.zeros((NY, NX), bool) for L in LAY}
    for net, L, g, kind, ex in piece:
        if kind == "pad": pts = [ex[1]]
        elif kind == "via": pts = [ex]
        else: pts = [(p.x, p.y) for p in (ex.interpolate(k * G) for k in range(int(ex.length / G) + 1))]
        for x, y in pts:
            iy, ix = cell(x, y)
            if 0 <= iy < NY and 0 <= ix < NX: anchor[L][iy, ix] = True
    return region, anchor, padreg

VGAP = int(round(0.7 / G))                                                  # cells (0.7 mm) of track between two vias of one route
def astar(SR, SA, SP, TR, TA, TP, block, vblock, soft=None, vsoft=None, pen=30.0, layers=None):
    use = range(len(LAY)) if layers is None else layers
    starts = [(li, iy, ix, 0) for li in use for iy, ix in zip(*np.nonzero(SA[LAY[li]]))]
    tmask = np.zeros((NY, NX), bool)
    for li in use: tmask |= TA[LAY[li]]
    ty, tx = np.nonzero(tmask)
    if not starts or len(ty) == 0: return None
    cy, cx = ty.mean(), tx.mean()
    def h(iy, ix): return math.hypot(iy - cy, ix - cx) * 0.9
    move = [~block[L] | SR[L] | TR[L] for L in LAY]
    vok = ~vblock & ~SP & ~TP
    best, prev, pq = {}, {}, []
    for s in starts: best[s] = 0.0; heapq.heappush(pq, (h(s[1], s[2]), 0.0, s))
    D = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    n = 0
    while pq:
        f, c, s = heapq.heappop(pq)
        if c > best.get(s, 1e18): continue
        li, iy, ix, cd = s; n += 1
        if TA[LAY[li]][iy, ix] and cd == 0:
            out = [s]
            while s in prev: s = prev[s]; out.append(s)
            return [(a, b_, c_) for a, b_, c_, _ in out[::-1]]
        if n > 5_000_000: return None
        for dy, dx, k in D:
            y2, x2 = iy + dy, ix + dx
            if not (0 <= y2 < NY and 0 <= x2 < NX) or not move[li][y2, x2]: continue
            if dy and dx and not (move[li][iy + dy, ix] and move[li][iy, ix + dx]): continue      # no corner cutting
            s2 = (li, y2, x2, max(cd - 1, 0)); c2 = c + k * LCOST[li] + (pen if soft is not None and soft[li][y2, x2] else 0.0)
            if c2 < best.get(s2, 1e18): best[s2] = c2; prev[s2] = s; heapq.heappush(pq, (c2 + h(y2, x2), c2, s2))
        if vok[iy, ix] and cd == 0:
            for lj in use:
                if lj == li or not move[lj][iy, ix]: continue
                s2 = (lj, iy, ix, VGAP); c2 = c + 25.0 + (2 * pen if vsoft is not None and vsoft[iy, ix] else 0.0)
                if c2 < best.get(s2, 1e18): best[s2] = c2; prev[s2] = s; heapq.heappush(pq, (c2 + h(iy, ix), c2, s2))
    return None

def emit(b, path, net, w):
    ni = b.FindNet(net); n_seg = 0; geo = []
    pts = [(round(X0 + ix * G, 3), round(Y0 + iy * G, 3), li) for li, iy, ix in path]
    def flush(run):
        nonlocal n_seg
        if len(run) < 2: return
        keep = [run[0]]
        for k in range(1, len(run) - 1):
            a, m, c = keep[-1], run[k], run[k + 1]
            d1 = (m[0] - a[0], m[1] - a[1]); d2 = (c[0] - m[0], c[1] - m[1])
            if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-6 or d1[0] * d2[0] + d1[1] * d2[1] < 0: keep.append(m)
        keep.append(run[-1])
        for a, c in zip(keep, keep[1:]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(P(a[0], a[1])); t.SetEnd(P(c[0], c[1])); t.SetLayer(LAY[run[0][2]]); t.SetWidth(MM(w)); t.SetNet(ni); b.Add(t); n_seg += 1
            geo.append((LAY[run[0][2]], LineString([(a[0], a[1]), (c[0], c[1])]).buffer(w / 2)))
    run = [pts[0]]
    for p in pts[1:]:
        if p[2] != run[-1][2]:
            flush(run)
            v = pcbnew.PCB_VIA(b); v.SetPosition(P(p[0], p[1])); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(ni)
            v.SetViaType(pcbnew.VIATYPE_THROUGH); b.Add(v); n_seg += 1
            geo += [(L, Point(p[0], p[1]).buffer(0.3)) for L in LAY]
            run = [p]
        else: run.append(p)
    flush(run)
    return n_seg, geo

def route(path_in, path_out, in1=True, only=None, skip_nets=()):
    lay_use = None if in1 else (0, 1)
    b = pcbnew.LoadBoard(path_in)
    edge = board_outline(b); ko = sbox(-50, -14.3, -39.5, 14.5)
    edge_ok = {w: raster([edge.buffer(-(0.62 + w / 2)).difference(ko.buffer(w / 2 + 0.25))], -G * 1.42) for w in (0.2, 0.4, 0.6)}
    holes = [Point(*Bf(p.GetPosition())).buffer(mm(p.GetDrillSize().x) / 2) for f in b.GetFootprints() for p in f.Pads() if p.HasHole()]
    global KO_T, KO_V
    KO_T, KO_V = keepouts(b)
    todo = {n: g for n, g in net_islands(b, skip=("", "GND")).items() if len(g) > 1 and (only is None or n in only) and n not in skip_nets}
    print("to route:", sorted(todo))
    queue = sorted(todo); ripped_total = 0; rips = {}
    while queue:
        net = queue.pop(0)
        for attempt in range(8):
            b.Save(path_out); b = pcbnew.LoadBoard(path_out)
            isl = {n: g for n, g in net_islands(b, skip=("", "GND")).items() if len(g) > 1}.get(net)
            if not isl: break
            isl = [list(map(tuple, i)) for i in isl]
            objs = objects(b); w = WIDTH.get(net, 0.2)
            other = {L: [o[2] for o in objs if o[1] == L and o[0] != net] for L in LAY}
            block = {L: raster(other[L], CLR + w / 2) | ~edge_ok[w] | raster(KO_T[L], w / 2) for L in LAY}
            vblock = raster(other[LAY[0]] + other[LAY[1]] + other[LAY[2]] + holes, CLR + 0.3) | ~edge_ok[0.6] | raster(KO_V, 0.3)
            # what may be ripped up: other nets' unlocked tracks and vias (not GND or +3V3 fanouts, not escapes)
            keep_nets = (net, "GND", "") + (() if os.environ.get("MAZE_RIP3V3") else ("+3V3",))
            loose = [(t, t.GetNetname()) for t in b.GetTracks() if not t.IsLocked() and t.GetNetname() not in keep_nets
                     and (not os.environ.get("MAZE_ONLY3V3") or t.GetNetname() == "+3V3")
                     and rips.get(t.GetNetname(), 0) < int(os.environ.get("MAZE_RIPS", "2"))]                      # a net ripped twice already stays put
            def geom(t): return Point(*Bf(t.GetPosition())).buffer(mm(t.GetWidth()) / 2) if t.GetClass() == "PCB_VIA" else LineString([Bf(t.GetStart()), Bf(t.GetEnd())]).buffer(mm(t.GetWidth()) / 2)
            def lays(t): return LAY if t.GetClass() == "PCB_VIA" else (t.GetLayer(),)
            hard_geo = {L: [o[2] for o in objs if o[1] == L and o[0] != net] for L in LAY}
            loose_geo = {L: [geom(t) for t, n in loose if L in lays(t)] for L in LAY}
            own_vias = [Point(o[4]) for o in objs if o[0] == net and o[3] == "via" and o[1] == LAY[0]]
            vblock = vblock | raster(own_vias, 0.55 - G * 0.71)                    # no new via on top of one of our own
            pcs = pieces_of(net, isl, objs)
            src = max(range(len(pcs)), key=lambda i: len(isl[i]))
            SR, SA, SP = masks(pcs[src])
            done_one = False
            for i, pc in enumerate(pcs):
                if i == src: continue
                TR, TA, TP = masks(pc)
                path = astar(SR, SA, SP, TR, TA, TP, block, vblock, layers=lay_use)
                rip = []
                if path is None and ripped_total < int(os.environ.get("MAZE_RIPTOTAL", "0")):
                    # rip-up: only the loose routing counts as soft; everything else stays hard
                    keep_geo = {L: [g for g in hard_geo[L] if not any(g.equals(lg) for lg in ())] for L in LAY}
                    fixed = {L: [o[2] for o in objs if o[1] == L and o[0] != net and not (o[3] in ("track", "via") and any(o[2].equals(lg) for lg in loose_geo[L]))] for L in LAY}
                    hblock = {L: raster(fixed[L], CLR + w / 2) | ~edge_ok[w] | raster(KO_T[L], w / 2) for L in LAY}
                    hvblock = raster(fixed[LAY[0]] + fixed[LAY[1]] + fixed[LAY[2]] + holes, CLR + 0.3) | ~edge_ok[0.6] | raster(KO_V, 0.3) | raster(own_vias, 0.55 - G * 0.71)
                    soft = [raster(loose_geo[L], CLR + w / 2) for L in LAY]
                    vsoft = raster(loose_geo[LAY[0]] + loose_geo[LAY[1]] + loose_geo[LAY[2]], CLR + 0.3)
                    path = astar(SR, SA, SP, TR, TA, TP, hblock, hvblock, soft, vsoft, pen=float(os.environ.get("MAZE_PEN", "30")), layers=lay_use)
                    if path is not None: rip = True
                if path is None: print("  no path for", net, sorted(isl[i])); continue
                n_items, geo = emit(b, path, net, w)
                if rip:
                    gone = set()
                    for t, n in loose:
                        tg = geom(t)
                        if any(L in lays(t) and tg.distance(g) < CLR + 0.01 for L, g in geo): gone.add((t, n))
                    for t, n in gone: b.Delete(t)
                    nets_hit = sorted({n for _, n in gone}); ripped_total += len(nets_hit)
                    for n in nets_hit: rips[n] = rips.get(n, 0) + 1
                    for n in nets_hit:
                        if n not in queue and n not in skip_nets: queue.append(n)
                    print(" ", net, "->", sorted(isl[i]), "items", n_items, "| ripped up", len(gone), "pieces of", nets_hit)
                else: print(" ", net, "->", sorted(isl[i]), "items", n_items)
                done_one = True; break
            if not done_one: break
    b.Save(path_out); b = pcbnew.LoadBoard(path_out)
    left = {n: g for n, g in net_islands(b, skip=("", "GND") + tuple(skip_nets)).items() if len(g) > 1}
    print("still incomplete:", left or "none")

if __name__ == "__main__":
    # +3V3 pieces are joined by the In1 pour, so the grid router leaves that net alone
    route(sys.argv[1], sys.argv[2], skip_nets=("+3V3",))

def connect(b, net, src_pts, dst_pts, layers=(0, 1), w=0.3):
    """Join two groups of existing vias of one net (given as shapely Points) with a route on the given layers."""
    global KO_T, KO_V
    KO_T, KO_V = keepouts(b)
    edge = board_outline(b); ko = sbox(-50, -14.3, -39.5, 14.5)
    eok = {ww: raster([edge.buffer(-(0.62 + ww / 2)).difference(ko.buffer(ww / 2 + 0.25))], -G * 1.42) for ww in (w, 0.6)}
    holes = [Point(*Bf(p.GetPosition())).buffer(mm(p.GetDrillSize().x) / 2) for f in b.GetFootprints() for p in f.Pads() if p.HasHole()]
    objs = objects(b)
    other = {L: [o[2] for o in objs if o[1] == L and o[0] != net] for L in LAY}
    block = {L: raster(other[L], CLR + w / 2) | ~eok[w] | raster(KO_T[L], w / 2) for L in LAY}
    own_vias = [Point(o[4]) for o in objs if o[0] == net and o[3] == "via" and o[1] == LAY[0]]
    vblock = raster(other[LAY[0]] + other[LAY[1]] + other[LAY[2]] + holes, CLR + 0.3) | ~eok[0.6] | raster(KO_V, 0.3) | raster(own_vias, 0.55 - G * 0.71)
    def mk(pts):
        reg = {L: raster([p.buffer(0.3) for p in pts], -0.05) for L in LAY}
        anc = {L: np.zeros((NY, NX), bool) for L in LAY}
        for p in pts:
            iy, ix = cell(p.x, p.y)
            for L in LAY: anc[L][iy, ix] = True
        return reg, anc, np.zeros((NY, NX), bool)
    SR, SA, SP = mk(src_pts); TR, TA, TP = mk(dst_pts)
    path = astar(SR, SA, SP, TR, TA, TP, block, vblock, layers=layers)
    if path is None: return False
    emit(b, path, net, w); return True
