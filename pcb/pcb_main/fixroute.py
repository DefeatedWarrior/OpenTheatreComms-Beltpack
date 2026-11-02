"""Help Freerouting with the last few connections on a routed board: rip up the unlocked routing inside some circles,
give some pads a locked escape via, then hand the board to route2.py.

  python3 fixroute.py in.kicad_pcb out.kicad_pcb
Edit CLEAR and ESCAPE below for the case at hand."""
import os, sys, math
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import P, Bf, mm, MM, Copper
from shapely.geometry import Point, LineString, box as sbox
from shapely.ops import unary_union

CLEAR = [((12.3, -24.5), 3.6), ((12.8, -20.8), 2.0), ((-9.4, -12.8), 2.2), ((-2.6, -14.6), 1.8), ((19.1, -22.5), 1.5)]
ESCAPE = [("U4", "8"), ("U4", "7"), ("U9", "1"), ("C29", "2"), ("C35", "1")]

b = pcbnew.LoadBoard(sys.argv[1])
fps = {f.GetReference(): f for f in b.GetFootprints()}
zones = unary_union([Point(c).buffer(r) for c, r in CLEAR])
gone = 0
for t in list(b.GetTracks()):
    if t.IsLocked(): continue
    g = Point(*Bf(t.GetPosition())) if t.GetClass() == "PCB_VIA" else LineString([Bf(t.GetStart()), Bf(t.GetEnd())])
    if g.intersects(zones): b.Delete(t); gone += 1
print("ripped up", gone)
b.Save(sys.argv[2]); b = pcbnew.LoadBoard(sys.argv[2]); fps = {f.GetReference(): f for f in b.GetFootprints()}
HOLES = [Bf(fps[h].GetPosition()) for h in ("H1", "H2", "H3", "H4", "H5")]
KEEP = unary_union([sbox(-50, -14.3, -39.5, 14.5)] + [Point(h).buffer(3.2) for h in HOLES])
cu = Copper(b)
def add_track(a, c_, layer, net, w):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net); t.SetLocked(True); b.Add(t); return t
def add_via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(net)
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLocked(True); b.Add(v); return v
def escape(fp, pad, w=0.2, dmin=0.7, dmax=3.4):
    L = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
    x, y = Bf(pad.GetPosition()); cx, cy = Bf(fp.GetPosition()); dx, dy = x - cx, y - cy
    n = (1.0 if dx > 0 else -1.0, 0.0) if abs(dx) > abs(dy) else (0.0, 1.0 if dy > 0 else -1.0)
    t = (-n[1], n[0]); bb = pad.GetBoundingBox(); half = (mm(bb.GetWidth()) if n[0] else mm(bb.GetHeight())) / 2
    a = (x + n[0] * (half + 0.25), y + n[1] * (half + 0.25)); nn = pad.GetNetname(); cands = []
    for k in range(int((dmax - dmin) / 0.15) + 1):
        for sl in [0.25 * j * sg for j in range(0, 9) for sg in ((1,) if j == 0 else (1, -1))]:
            cands.append((dmin + 0.15 * k + abs(sl) * 0.6, dmin + 0.15 * k, sl))
    for _, d, sl in sorted(cands):
        vx, vy = x + n[0] * (half + d) + t[0] * sl, y + n[1] * (half + d) + t[1] * sl
        if Point(vx, vy).within(KEEP.buffer(-2.8)) or not cu.via_ok(vx, vy, nn): continue
        pts = [(x, y), a, (vx, vy)]
        if not cu.clear(LineString(pts).buffer(w / 2), nn, [L], 0.2, pads_any_net=False): continue
        for it in [add_via(vx, vy, pad.GetNet())] + [add_track(p_, q_, L, pad.GetNet(), w) for p_, q_ in zip(pts, pts[1:])]: cu.add_track(it)
        return (round(vx, 2), round(vy, 2))
    return None
for ref, num in ESCAPE:
    pad = [p for p in fps[ref].Pads() if p.GetNumber() == num][0]
    print("escape", ref, num, escape(fps[ref], pad))
b.Save(sys.argv[2])
