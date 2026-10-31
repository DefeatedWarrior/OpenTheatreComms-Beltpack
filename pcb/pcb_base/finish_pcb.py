"""Finish the routed base station carrier PCB: GND on F.Cu, In1 and B.Cu, +3V3 on In2, stitching vias, a repair pass that joins stray
GND pour fragments, then save into the KiCad project with its library and run the DRC. Reads out/routed.kicad_pcb."""
import os, sys, math, shutil
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import P, Bf, mm, MM, Copper, polyset_to_shapely
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "base_pcb"))
OUT = os.path.join(HERE, "out")
b = pcbnew.LoadBoard(os.path.join(OUT, "routed.kicad_pcb"))
GND, V33 = b.FindNet("GND"), b.FindNet("+3V3")

# tidy: escape vias the router didn't use (connected on one layer only) and the stubs that led to them
def tidy(b):
    removed = 0
    while True:
        tr = [t for t in b.GetTracks() if t.GetNetname() not in ("GND", "+3V3", "")]
        pads = {}
        for f in b.GetFootprints():
            for p in f.Pads():
                g = polyset_to_shapely(p.GetEffectivePolygon())
                for L in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu):
                    if p.IsOnLayer(L) or (p.HasHole() and L in (pcbnew.In1_Cu, pcbnew.In2_Cu)): pads.setdefault((p.GetNetname(), L), []).append(g)
        segs = [(t, t.GetNetname(), t.GetLayer(), LineString([Bf(t.GetStart()), Bf(t.GetEnd())]), mm(t.GetWidth()) / 2) for t in tr if t.GetClass() == "PCB_TRACK"]
        vias = [(t, t.GetNetname(), Point(*Bf(t.GetPosition())), mm(t.GetWidth()) / 2) for t in tr if t.GetClass() == "PCB_VIA"]
        kill = []; trimmed = []
        for v, n, pt, r in vias:
            layers = {L for s_, nn, L, g, hw in segs if nn == n and g.distance(pt) < r}
            layers |= {L for (nn, L), gs in pads.items() if nn == n and any(g.distance(pt) < r for g in gs)}
            if len(layers) <= 1: kill.append(v)
        for t, n, L, g, hw in segs:
            for end in (Point(g.coords[0]), Point(g.coords[-1])):
                ok = any(pg.distance(end) < 0.01 for pg in pads.get((n, L), []))
                ok = ok or any(v not in kill and nn == n and vp.distance(end) < r for v, nn, vp, r in vias)
                ok = ok or any(t2 is not t and n2 == n and L2 == L and g2.distance(end) < hw2 for t2, n2, L2, g2, hw2 in segs)
                if not ok:
                    # a T-junction: another track ends on this one's middle, so cut back to it instead of deleting
                    joins = [Point(g2.coords[k]) for t2, n2, L2, g2, hw2 in segs if t2 is not t and n2 == n and L2 == L for k in (0, -1)
                             if g.distance(Point(g2.coords[k])) < hw and Point(g2.coords[k]).distance(end) > 0.01]
                    if joins:
                        far = Point(g.coords[-1]) if end.equals(Point(g.coords[0])) else Point(g.coords[0])
                        j = min(joins, key=lambda p: p.distance(end)); j = g.interpolate(g.project(j))
                        if end.equals(Point(g.coords[0])): t.SetStart(P(j.x, j.y))
                        else: t.SetEnd(P(j.x, j.y))
                        trimmed.append(t); break
                    kill.append(t); break
        if not kill and not trimmed: return removed
        for k in kill: b.Delete(k)
        removed += len(kill)
print("tidy: removed", tidy(b), "unused vias and stubs")
b.Save(os.path.join(OUT, "tidied.kicad_pcb")); b = pcbnew.LoadBoard(os.path.join(OUT, "tidied.kicad_pcb"))
GND, V33 = b.FindNet("GND"), b.FindNet("+3V3")
for z in list(b.Zones()):
    if not z.GetIsRuleArea(): b.Remove(z)
def add_via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(net)
    v.SetViaType(pcbnew.VIATYPE_THROUGH); b.Add(v); return v
def add_track(a, c_, layer, net, w=0.3):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net); b.Add(t); return t
def add_zone(layer, net, prio=0):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(net); z.SetZoneName(net.GetNetname()); z.SetAssignedPriority(prio)
    ol = z.Outline(); ol.NewOutline()
    for x, y in ((-76, -46), (76, -46), (76, 46), (-76, 46)): ol.Append(MM(float(150 + x)), MM(float(105 - y)))
    z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2)); z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.35))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z); return z
# +3V3 pieces the router left apart: a via from one pad of each loose piece down to the In2 +3V3 pour
from pcbgeom import net_islands
cu0 = Copper(b)
for piece in sorted(net_islands(b, skip=("", "GND")).get("+3V3", []), key=len, reverse=True)[1:]:
    ok = False
    for ref, num in sorted(piece):
        fp = b.FindFootprintByReference(ref); pad = [p for p in fp.Pads() if p.GetNumber() == num][0]
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
        x, y = Bf(pad.GetPosition())
        for r_ in [0.2 * k for k in range(3, 20)]:
            for k in range(16):
                vx, vy = x + r_ * math.cos(k * math.pi / 8), y + r_ * math.sin(k * math.pi / 8)
                if cu0.via_ok(vx, vy, "+3V3") and cu0.clear(LineString([(x, y), (vx, vy)]).buffer(0.15), "+3V3", [pcbnew.F_Cu], 0.2, pads_any_net=False):
                    v = add_via(vx, vy, V33); t_ = add_track((x, y), (vx, vy), pcbnew.F_Cu, V33, w=0.3); cu0.add_track(v); cu0.add_track(t_); ok = True; break
            if ok: break
        if ok: break
    print("+3V3 loose piece", sorted(piece)[:3], "joined to the In2 pour" if ok else "NOT JOINED")
GL = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.B_Cu)
zones = {pcbnew.F_Cu: add_zone(pcbnew.F_Cu, GND), pcbnew.In1_Cu: add_zone(pcbnew.In1_Cu, GND), pcbnew.In2_Cu: add_zone(pcbnew.In2_Cu, V33),
         pcbnew.B_Cu: add_zone(pcbnew.B_Cu, GND)}
def fill():
    b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
def filled(L): z = zones[L]; return polyset_to_shapely(z.GetFilledPolysList(L))
fill()

# +3V3 is routed like any other net (In2 is a signal layer as well as the +3V3 pour), so the pour needn't be one piece
g1 = filled(pcbnew.In2_Cu); print("+3V3 pour pieces on In2:", len(getattr(g1, "geoms", [g1])))

# stitching: GND vias where F, In1 and B all have GND copper
both = filled(pcbnew.F_Cu).intersection(filled(pcbnew.B_Cu)).intersection(filled(pcbnew.In1_Cu)).buffer(-0.45)
cu = Copper(b)
holes_xy = [Bf(f.GetPosition()) for f in b.GetFootprints() if f.GetReference().startswith("H")]
gvias = [Bf(t.GetPosition()) for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
added = 0
for gy in [y_ * 0.5 for y_ in range(-90, 91)]:
    for gx in [x_ * 0.5 for x_ in range(-150, 151)]:
        if not both.contains(Point(gx, gy)): continue
        if any(math.hypot(gx - hx, gy - hy) < 4.0 for hx, hy in holes_xy): continue
        if any(math.hypot(gx - vx, gy - vy) < 4.0 for vx, vy in gvias): continue
        if not cu.via_ok(gx, gy, "GND", clearance=0.3): continue
        v = add_via(gx, gy, GND); cu.add_track(v); gvias.append((gx, gy)); added += 1
print("stitching vias", added)
fill()

# repair: every GND pour fragment on F/In2/B should join the main GND through vias or through-hole GND pads
def gnd_graph():
    frags = []
    for L in GL:
        g = filled(L)
        for poly in getattr(g, "geoms", [g]):
            if not poly.is_empty: frags.append((L, poly))
    links = [Point(*Bf(t.GetPosition())).buffer(0.3) for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == "GND" and pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH: links.append(Point(*Bf(pad.GetPosition())).buffer(0.4))
    parent = list(range(len(frags)))
    def f_(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for lk in links:
        hit = [i for i, (_, poly) in enumerate(frags) if poly.intersects(lk)]
        for i in hit[1:]: parent[f_(i)] = f_(hit[0])
    main = f_(max(range(len(frags)), key=lambda i: frags[i][1].area if frags[i][0] == pcbnew.In1_Cu else 0))
    return frags, [f_(i) == main for i in range(len(frags))]
def try_via_in(region, others):
    tgt = region.buffer(-0.05).intersection(others.buffer(-0.15))
    if tgt.is_empty: return False
    x0, y0, x1, y1 = tgt.bounds; step = max(0.2, math.sqrt((x1 - x0) * (y1 - y0) / 600.0))
    nx, ny = max(2, int((x1 - x0) / step) + 1), max(2, int((y1 - y0) / step) + 1)
    c = tgt.representative_point()
    for x, y in sorted(((x0 + (x1 - x0) * i / (nx - 1), y0 + (y1 - y0) * j / (ny - 1)) for i in range(nx) for j in range(ny)), key=lambda p: c.distance(Point(p))):
        if tgt.contains(Point(x, y)) and cu.via_ok(x, y, "GND", clearance=0.22):
            cu.add_track(add_via(x, y, GND)); return True
    return False
for it in range(4):
    frags, ok = gnd_graph()
    main = {L: unary_union([p for (LL, p), k in zip(frags, ok) if k and LL == L]) for L in GL}
    fixes = 0
    for (L, poly), k in zip(frags, ok):
        if k: continue
        others = unary_union([main[o] for o in GL if o != L])
        if try_via_in(poly, others): fixes += 1
    print("repair pass", it, "fixes", fixes, "stray fragments", ok.count(False))
    if not fixes: break
    fill()
# +3V3: vias in the In2 pour (informational: +3V3 is also routed)
p1 = filled(pcbnew.In2_Cu)
off = [Bf(t.GetPosition()) for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "+3V3" and not p1.buffer(0.05).contains(Point(*Bf(t.GetPosition())))]
print("+3V3 vias outside the In2 pour:", [tuple(round(v, 2) for v in o) for o in off] or "none")

for fp in b.GetFootprints():
    if fp.GetReference().startswith("H"): fp.Reference().SetVisible(False)

# silkscreen: outline pieces past the board edge go to the fab layer (the jack and LED noses); references and the board
# text move to a clear spot next to their part (or are hidden: the assembly drawing has every reference)
from shapely.geometry import box as sbox
from pcbgeom import board_outline
EDGE_IN = board_outline(b).buffer(-0.3)
def bb(item, grow=0.0):
    r = item.GetBoundingBox(); (x0, y1), (x1, y0) = Bf(r.GetOrigin()), Bf(r.GetEnd()); return sbox(x0 - grow, y0 - grow, x1 + grow, y1 + grow)
moved_silk = 0
for fp in b.GetFootprints():
    for g in list(fp.GraphicalItems()):
        if g.GetClass() == "MGRAPHIC" and g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and not EDGE_IN.contains(bb(g)):
            g.SetLayer(pcbnew.F_Fab if g.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Fab); moved_silk += 1
obst = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
for fp in b.GetFootprints():
    for g in fp.GraphicalItems():
        if g.GetClass() == "MGRAPHIC" and g.GetLayer() in obst: obst[g.GetLayer()].append(bb(g, 0.15))
    for p in fp.Pads():
        for L, cu_ in ((pcbnew.F_SilkS, pcbnew.F_Cu), (pcbnew.B_SilkS, pcbnew.B_Cu)):
            if p.IsOnLayer(cu_) or p.HasHole(): obst[L].append(polyset_to_shapely(p.GetEffectivePolygon()).buffer(0.15))
from shapely.strtree import STRtree
otree = {L: STRtree(v) for L, v in obst.items()}; added = {L: [] for L in obst}
def fits(g, L):
    return EDGE_IN.contains(g) and not any(obst[L][i].intersects(g) for i in otree[L].query(g)) and not any(o.intersects(g) for o in added[L])
def place_text(t, around, L):
    """Try spots on rings round the part's courtyard, nearest first; True when one is clear."""
    cx, cy = around.centroid.x, around.centroid.y; x0, y0, x1, y1 = around.bounds
    t.SetTextAngleDegrees(0); t.SetPosition(P(cx, cy)); tb = bb(t); w_, h_ = tb.bounds[2] - tb.bounds[0], tb.bounds[3] - tb.bounds[1]
    cands = []
    for k in range(0, 8):
        d = 0.25 + 0.35 * k
        for px, py in ((cx, y1 + d + h_ / 2), (cx, y0 - d - h_ / 2), (x1 + d + w_ / 2, cy), (x0 - d - w_ / 2, cy),
                       (x1 + d + w_ / 2, y1 + d + h_ / 2), (x0 - d - w_ / 2, y1 + d + h_ / 2), (x1 + d + w_ / 2, y0 - d - h_ / 2), (x0 - d - w_ / 2, y0 - d - h_ / 2)):
            cands.append((px, py))
    for px, py in cands:
        t.SetPosition(P(px, py)); g = bb(t, 0.05)
        if fits(g, L): added[L].append(g); return True
    return False
hidden = []
for fp in sorted(b.GetFootprints(), key=lambda f: -polyset_to_shapely(f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)).area):
    ref = fp.Reference()
    if not ref.IsVisible() or fp.GetReference() == "REF**": continue
    L = ref.GetLayer(); crt = polyset_to_shapely(fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd))
    if crt.is_empty or not place_text(ref, crt, L): ref.SetVisible(False); hidden.append(fp.GetReference())
for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.B_SilkS:
        spot = None; home = d.GetPosition()
        for gy in [y_ * 0.5 for y_ in range(-80, 80)]:
            for gx in [x_ * 0.5 for x_ in range(-140, 140)]:
                d.SetPosition(P(gx, gy)); g = bb(d, 0.1)
                if fits(g, pcbnew.B_SilkS): spot = (gx, gy); break
            if spot: break
        if spot is None: d.SetPosition(home)
        print("board text at", spot)
print("silk: outline pieces to fab", moved_silk, "| references hidden", hidden)
pcb_out = os.path.join(PROJ, "base_pcb.kicad_pcb")
import json                                               # link every footprint to the symbol in the schematic that ships with it
SYMS = json.load(open(os.path.join(OUT, "base_pcb_schinfo.json")))["symbols"]
for fp in b.GetFootprints():
    if fp.GetReference() in SYMS: fp.SetPath(pcbnew.KIID_PATH("/" + SYMS[fp.GetReference()]))
b.Save(pcb_out)
shutil.copy(os.path.join(OUT, "base_pcb.kicad_sch"), os.path.join(PROJ, "base_pcb.kicad_sch"))
if os.path.exists(os.path.join(PROJ, "lib")): shutil.rmtree(os.path.join(PROJ, "lib"))
shutil.copytree(os.path.join(HERE, "lib"), os.path.join(PROJ, "lib"))
open(os.path.join(PROJ, "base_pcb.kicad_dru"), "w").write("""(version 1)
# Low-current pads: one thermal spoke is enough to join a pad to a pour.
(rule "single spoke"
  (constraint min_resolved_spokes 1))
# The edge SMA jacks' ground pads run to the rear edge by design (they straddle it).
(rule "SMA at the edge"
  (condition "A.insideCourtyard('J2') || A.insideCourtyard('J3')")
  (constraint edge_clearance (min 0.25mm)))
""")
b2 = pcbnew.LoadBoard(pcb_out)
ds = b2.GetDesignSettings(); ds.m_MinThroughDrill = MM(0.2)     # the ESP32 and codec footprints' thermal vias are 0.2 mm
pcbnew.ZONE_FILLER(b2).Fill(b2.Zones()); b2.Save(pcb_out)
rpt = os.path.join(OUT, "drc.rpt")
pcbnew.WriteDRCReport(b2, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
print("".join(l for l in open(rpt) if l.startswith("** Found")))
