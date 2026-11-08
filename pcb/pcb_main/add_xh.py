"""Add J11, a JST XH 2-pin battery input (pin 1 BAT, pin 2 GND), to the finished main board, in parallel with the spring pins.

Searches every free spot (front, or back outside the battery pack), checks the through-hole pads against copper on all four
layers, and places it nearest the BAT net; maze.py then routes pin 1 to BAT (0.4 mm). Pin 2 joins GND through the
pours (In2 is solid GND). Also opens the spring-pin holes J8-J10 to 1.0 mm for the cheaper LCSC pins.

  python3 add_xh.py board.kicad_pcb
"""
import os, sys, math
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import P, Bf, mm, MM, Copper, polyset_to_shapely, LAYERS, INNER
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union

path = sys.argv[1]
b = pcbnew.LoadBoard(path)
BATN, GNDN = "/BAT", "GND"

# --- spring pins: 1.0 mm holes (pads stay 1.6 mm)
for f in b.GetFootprints():
    if f.GetReference() in ("J8", "J9", "J10"):
        for p in f.Pads(): p.SetDrillSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))

# --- J11
if any(f.GetReference() == "J11" for f in b.GetFootprints()): sys.exit("J11 already on the board")
lib = "/usr/share/kicad/footprints/Connector_JST.pretty"
fp = pcbnew.FootprintLoad(lib, "JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical")
fp.SetReference("J11"); fp.SetValue("Battery (JST XH)")
fp.SetFPID(pcbnew.LIB_ID("Connector_JST", "JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical"))
b.Add(fp)
nb, ng = b.FindNet(BATN), b.FindNet(GNDN)
for p in fp.Pads(): p.SetNet(nb if p.GetNumber() == "1" else ng)
fp.SetPosition(P(500, 500))

cu = Copper(b)
crt_of = lambda f, s: polyset_to_shapely(f.GetCourtyard(pcbnew.B_CrtYd if s == "B" else pcbnew.F_CrtYd))
others = {s: [crt_of(f, "B" if f.IsFlipped() else "F") for f in b.GetFootprints()
              if f.GetReference() != "J11" and (f.IsFlipped() == (s == "B") or f.GetReference().startswith("H"))] for s in "FB"}
for s in "FB":
    others[s] += [Point(*Bf(f.GetPosition())).buffer(2.7) for f in b.GetFootprints() if f.GetReference().startswith("H")]
otherside_pads = {s: [polyset_to_shapely(p.GetEffectivePolygon()).buffer(0.3) for f in b.GetFootprints()
                      if f.GetReference() != "J11" and f.IsFlipped() != (s == "B") for p in f.Pads()] for s in "FB"}
keep = [polyset_to_shapely(z.Outline()) for z in b.Zones() if z.GetIsRuleArea()]
PACK = box(-13.5, -31.0, 39.5, 15.0)                       # battery pack behind the back face: no tall parts there
anchors = []
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetname() == BATN and f.GetReference() != "J11" and not p.HasHole():
            anchors.append((Bf(p.GetPosition()), pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu))
for t in b.GetTracks():
    if t.GetClass() == "PCB_TRACK" and t.GetNetname() == BATN and t.GetLayer() in LAYERS:
        ln = LineString([Bf(t.GetStart()), Bf(t.GetEnd())])
        anchors += [((ln.interpolate(k * 0.25).x, ln.interpolate(k * 0.25).y), t.GetLayer()) for k in range(int(ln.length / 0.25) + 1)]

def inner_clear(g, net, cl=0.25):
    return not any(n != net and tg.distance(g) < cl for n, tg in cu.inner_tracks)
def hole_clear(c, r):
    return all(h.distance(Point(*c)) > r + 0.5 for h in cu.holes if h.distance(Point(*c)) < r + 3)

W = 0.4
best = None
xs = [x * 0.5 for x in range(-90, 91)]; ys = [y * 0.5 for y in range(-70, 71)]
for side in ("F", "B"):
    LP = pcbnew.F_Cu if side == "F" else pcbnew.B_Cu
    for x in xs:
        for y in ys:
            for rot in (0, 90, 180, 270):
                fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(0)
                if fp.IsFlipped() != (side == "B"): fp.Flip(P(x, y), False)
                fp.SetOrientationDegrees(rot)
                crt = crt_of(fp, side)
                if not cu.edge.buffer(-1.0).contains(crt): continue
                if side == "B" and crt.intersects(PACK): continue
                if any(k.intersects(crt) for k in keep): continue
                if any(o.intersects(crt) for o in others[side]): continue
                pads = {p.GetNumber(): p for p in fp.Pads()}
                q = {n: polyset_to_shapely(p.GetEffectivePolygon()) for n, p in pads.items()}
                if any(any(o.intersects(q[n]) for o in otherside_pads[side]) for n in q): continue
                ok = True
                for n, net in (("1", BATN), ("2", GNDN)):
                    c = Bf(pads[n].GetPosition())
                    if not cu.clear(q[n], net, list(LAYERS), 0.25, pads_any_net=False) or not inner_clear(q[n], net) or not hole_clear(c, 0.5):
                        ok = False; break
                if not ok: continue
                c1 = Bf(pads["1"].GetPosition())
                d = min(math.dist(a_[0], c1) for a_ in anchors)
                if best is None or d < best[0]: best = (d, x, y, rot, side, [])
if best is None: sys.exit("no spot for J11")
d, x, y, rot, side, route = best
fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(0)
if fp.IsFlipped() != (side == "B"): fp.Flip(P(x, y), False)
fp.SetOrientationDegrees(rot)
# silk: mark + by pin 1
lay = pcbnew.B_SilkS if side == "B" else pcbnew.F_SilkS
c1 = Bf([p for p in fp.Pads() if p.GetNumber() == "1"][0].GetPosition())
txt = pcbnew.PCB_TEXT(b); txt.SetText("+"); txt.SetLayer(lay); txt.SetTextSize(pcbnew.VECTOR2I(MM(1.2), MM(1.2))); txt.SetTextThickness(MM(0.2))
cx, cy = Bf(fp.GetPosition())
txt.SetPosition(P(c1[0] + (c1[0] - cx) * 0.0 + (1.9 if rot in (0, 180) else 0), c1[1] + (0 if rot in (0, 180) else 1.9)))
if side == "B": txt.SetMirrored(True)
b.Add(txt)
filler = pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
b.Save(path)
print(f"J11 at ({x:.2f}, {y:.2f}) rot {rot} on {side}; nearest BAT copper {d:.1f} mm (maze.py routes it)")
