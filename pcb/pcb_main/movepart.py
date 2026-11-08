"""Move a two-pad part that the routers couldn't connect next to copper of its net, and wire it there:
pad 1 by a straight track to the nearest copper of its net, pad 2 (GND) by a short track to a new via.

  python3 movepart.py board.kicad_pcb REF
"""
import os, sys, math
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import P, Bf, mm, MM, Copper, polyset_to_shapely
from shapely.geometry import Point, LineString
path, ref = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(path)
fp = [f for f in b.GetFootprints() if f.GetReference() == ref][0]
p1, p2 = [p for p in fp.Pads() if p.GetNumber() == "1"][0], [p for p in fp.Pads() if p.GetNumber() == "2"][0]
net1, net2 = p1.GetNetname(), p2.GetNetname()
# take away the part's own routing (stubs to its pads)
for pad in (p1, p2):
    pg = polyset_to_shapely(pad.GetEffectivePolygon())
    for t in list(b.GetTracks()):
        if t.GetNetname() != pad.GetNetname(): continue
        g = Point(*Bf(t.GetPosition())) if t.GetClass() == "PCB_VIA" else LineString([Bf(t.GetStart()), Bf(t.GetEnd())])
        if g.distance(pg) < 0.05: b.Delete(t)
b.Save(path); b = pcbnew.LoadBoard(path)
fp = [f for f in b.GetFootprints() if f.GetReference() == ref][0]
cu_net = [(Bf(t.GetStart()), Bf(t.GetEnd()), t.GetLayer()) for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net1]
anchors = []
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetname() == net1 and f.GetReference() != ref:
            anchors.append((Bf(p.GetPosition()), pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu))
for a, c, L in cu_net:
    ln = LineString([a, c])
    anchors += [((ln.interpolate(k * 0.25).x, ln.interpolate(k * 0.25).y), L) for k in range(int(ln.length / 0.25) + 1)]
fp.SetPosition(P(500, 500))                       # out of the way while the copper model is built
cu = Copper(b)
others = {s: [polyset_to_shapely(f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)) for f in b.GetFootprints()
              if f.GetReference() not in (ref, "REF**") and (f.IsFlipped() == (s == "B") or f.GetReference().startswith("H"))] for s in "FB"}
for s in "FB":                                    # mounting holes: the screw head and the case boss around them
    others[s] += [Point(*Bf(f.GetPosition())).buffer(2.7) for f in b.GetFootprints() if f.GetReference().startswith("H")]   # standoff r 2.5 (front), screw head r 2 (back)
best = None
cx, cy = (sum(a[0][0] for a in anchors) / len(anchors), sum(a[0][1] for a in anchors) / len(anchors))
def ring(c, rs=(0.9, 1.1, 1.3, 1.5)):
    for r in rs:
        for k in range(16):
            a_ = 2 * math.pi * k / 16; yield c[0] + r * math.cos(a_), c[1] + r * math.sin(a_)
for (ax, ay), L in anchors:
    for side in ("B" if L == pcbnew.B_Cu else "F", "F" if L == pcbnew.B_Cu else "B"):
        LP = pcbnew.B_Cu if side == "B" else pcbnew.F_Cu
        for dx in [k * 0.25 for k in range(-20, 21)]:
            for dy in [k * 0.25 for k in range(-20, 21)]:
                if math.hypot(dx, dy) > 5.0: continue
                for rot in (0, 90, 180, 270):
                    x, y = ax + dx, ay + dy
                    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(0)
                    if fp.IsFlipped() != (side == "B"): fp.Flip(P(x, y), False)
                    fp.SetOrientationDegrees(rot)
                    crt = polyset_to_shapely(fp.GetCourtyard(pcbnew.B_CrtYd if side == "B" else pcbnew.F_CrtYd))
                    if any(o.intersects(crt) for o in others[side]): continue
                    q1, q2 = [polyset_to_shapely(p.GetEffectivePolygon()) for p in sorted(fp.Pads(), key=lambda p: p.GetNumber())]
                    if not cu.clear(q1, net1, [LP], 0.22, pads_any_net=False) or not cu.clear(q2, net2, [LP], 0.22, pads_any_net=False): continue
                    c1 = Bf([p for p in fp.Pads() if p.GetNumber() == "1"][0].GetPosition())
                    c2 = Bf([p for p in fp.Pads() if p.GetNumber() == "2"][0].GetPosition())
                    if LP == L:                                   # straight to the net on the same layer
                        tr = LineString([c1, (ax, ay)])
                        if tr.length > 0.01 and not cu.clear(tr.buffer(0.1), net1, [L], 0.2, pads_any_net=False): continue
                        if tr.buffer(0.3).intersects(q2): continue
                        route1 = [("t", c1, (ax, ay), L)]; used = tr
                    else:                                         # pad 1 -> via -> the net on the other layer
                        route1 = None
                        for vx, vy in ring(c1):
                            if not cu.via_ok(vx, vy, net1) or Point(vx, vy).buffer(0.5).intersects(q2): continue
                            t1, t2 = LineString([c1, (vx, vy)]), LineString([(vx, vy), (ax, ay)])
                            if t2.length > 5.0 or not cu.clear(t1.buffer(0.1), net1, [LP], 0.2, pads_any_net=False) or t1.buffer(0.3).intersects(q2): continue
                            if t2.length > 0.01 and not cu.clear(t2.buffer(0.1), net1, [L], 0.2, pads_any_net=False): continue
                            route1 = [("t", c1, (vx, vy), LP), ("v", (vx, vy)), ("t", (vx, vy), (ax, ay), L)]; used = LineString([c1, (vx, vy)]); break
                        if route1 is None: continue
                    via = None
                    for vx, vy in ring(c2):
                        if not cu.via_ok(vx, vy, net2): continue
                        vt = LineString([c2, (vx, vy)])
                        if Point(vx, vy).buffer(0.5).intersects(q1) or vt.buffer(0.3).intersects(q1) or used.distance(Point(vx, vy)) < 0.6: continue
                        if any(r_[0] == "v" and math.dist(r_[1], (vx, vy)) < 0.9 for r_ in route1): continue
                        if not cu.clear(vt.buffer(0.15), net2, [LP], 0.2, pads_any_net=False): continue
                        via = (vx, vy); break
                    if via is None: continue
                    score = sum(math.dist(r_[1], r_[2]) for r_ in route1 if r_[0] == "t") + (2.0 if LP != L else 0) + 0.2 * math.hypot(x - cx, y - cy)
                    if best is None or score < best[0]: best = (score, x, y, rot, side, LP, route1, via)
if best is None and "--free" in sys.argv:
    for (ax, ay), L in anchors[:1]:
        pass
    for rad in [0.5 * k for k in range(2, 25)]:
        for k in range(max(8, int(2 * math.pi * rad / 0.5))):
            a_ = 2 * math.pi * k / max(8, int(2 * math.pi * rad / 0.5)); x, y = cx + rad * math.cos(a_), cy + rad * math.sin(a_)
            for side in ("B", "F"):
                LP = pcbnew.B_Cu if side == "B" else pcbnew.F_Cu
                for rot in (0, 90):
                    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(0)
                    if fp.IsFlipped() != (side == "B"): fp.Flip(P(x, y), False)
                    fp.SetOrientationDegrees(rot)
                    crt = polyset_to_shapely(fp.GetCourtyard(pcbnew.B_CrtYd if side == "B" else pcbnew.F_CrtYd))
                    if any(o.intersects(crt) for o in others[side]): continue
                    q1, q2 = [polyset_to_shapely(p.GetEffectivePolygon()) for p in sorted(fp.Pads(), key=lambda p: p.GetNumber())]
                    if not cu.clear(q1.buffer(0.3), net1, [LP], 0.2, pads_any_net=False) or not cu.clear(q2, net2, [LP], 0.22, pads_any_net=False): continue
                    c2 = Bf([p for p in fp.Pads() if p.GetNumber() == "2"][0].GetPosition())
                    via = next(((vx, vy) for vx, vy in ring(c2) if cu.via_ok(vx, vy, net2) and not Point(vx, vy).buffer(0.6).intersects(q1)
                                and cu.clear(LineString([c2, (vx, vy)]).buffer(0.15), net2, [LP], 0.2, pads_any_net=False)), None)
                    if via is None: continue
                    best = (0, x, y, rot, side, LP, [], via); break
                if best: break
            if best: break
        if best: break
if best is None: sys.exit(f"no spot for {ref}")
score, x, y, rot, side, LP, route1, via = best
fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(0)
if fp.IsFlipped() != (side == "B"): fp.Flip(P(x, y), False)
fp.SetOrientationDegrees(rot)
n1, n2 = b.FindNet(net1), b.FindNet(net2)
def track(a, c, L, net, w):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetLayer(L); t.SetWidth(MM(w)); t.SetNet(net); b.Add(t)
def addvia(p, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(*p)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH); b.Add(v)
for r_ in route1:
    if r_[0] == "t" and math.dist(r_[1], r_[2]) > 0.01: track(r_[1], r_[2], r_[3], n1, 0.2)
    elif r_[0] == "v": addvia(r_[1], n1)
c2 = Bf([p for p in fp.Pads() if p.GetNumber() == "2"][0].GetPosition())
addvia(via, n2); track(c2, via, LP, n2, 0.3)
b.Save(path)
print(f"{ref} moved to ({x:.2f}, {y:.2f}) rot {rot} on {side}; {net1} joined by {len(route1)} pieces; {net2} via at ({via[0]:.2f}, {via[1]:.2f})")
