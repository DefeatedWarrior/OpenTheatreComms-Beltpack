"""Finish the routed top PCB: GND pours on both layers, stitching vias, fill, save into the KiCad project, DRC report.
Reads out/routed.kicad_pcb written by make_pcb.py."""
import os, sys, math, shutil
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")   # so the DRC can find the stock libraries
os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pcbgeom import P, Bf, mm, MM, Copper, polyset_to_shapely
from shapely.geometry import Point
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "top_pcb"))
OUT = os.path.join(HERE, "out")
b = pcbnew.LoadBoard(os.path.join(OUT, "routed.kicad_pcb"))
GND = b.FindNet("GND")
for z in list(b.Zones()):
    if not z.GetIsRuleArea(): b.Remove(z)
def add_via(x, y, net, locked=False):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(net)
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLocked(locked); b.Add(v); return v

# ------------------------------------------------------------------ GND pours on both layers, stitching vias, fill
def add_zone(layer):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(GND); z.SetZoneName("GND")
    ol = z.Outline(); ol.NewOutline()
    for x, y in ((-52, -16), (52, -16), (52, 17), (-52, 17)): ol.Append(MM(float(150 + x)), MM(float(105 - y)))
    z.SetLocalClearance(MM(0.2)); z.SetMinThickness(MM(0.2))
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.35))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z); return z
zones = [add_zone(pcbnew.F_Cu), add_zone(pcbnew.B_Cu)]
def fill():
    b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
fill()
def filled(z): return polyset_to_shapely(z.GetFilledPolysList(z.GetLayer()))
both = filled(zones[0]).intersection(filled(zones[1])).buffer(-0.45)
cu = Copper(b)
holes_xy = [Bf(f.GetPosition()) for f in b.GetFootprints() if f.GetReference().startswith("H")]
gvias = [Bf(t.GetPosition()) for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
added = 0
for gy in [y_ * 0.5 for y_ in range(-26, 30)]:
    for gx in [x_ * 0.5 for x_ in range(-100, 101)]:
        if not both.contains(Point(gx, gy)): continue
        if any(math.hypot(gx - hx, gy - hy) < 3.4 for hx, hy in holes_xy): continue
        if any(math.hypot(gx - vx, gy - vy) < 3.0 for vx, vy in gvias): continue
        if not cu.via_ok(gx, gy, "GND", clearance=0.3): continue
        v = add_via(gx, gy, GND, locked=False); cu.add_track(v); gvias.append((gx, gy)); added += 1
print("stitching vias", added)
fill()

# ------------------------------------------------------------------ repair: join every pour fragment and GND pad to the main GND
from shapely.geometry import LineString
def add_track(a, c_, layer, net, w=0.3):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net); b.Add(t); return t
def gnd_graph():
    """Fragments of both pours plus GND vias and through-hole GND pads, grouped into connected sets."""
    frags = []
    for z in zones:
        g = filled(z)
        for poly in getattr(g, "geoms", [g]):
            if not poly.is_empty: frags.append((z.GetLayer(), poly))
    links = [Point(*Bf(t.GetPosition())).buffer(0.3) for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == "GND" and pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                links.append(Point(*Bf(pad.GetPosition())).buffer(0.5))
    parent = list(range(len(frags)))
    def find_(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for lk in links:
        hit = [i for i, (_, poly) in enumerate(frags) if poly.intersects(lk)]
        for i in hit[1:]: parent[find_(i)] = find_(hit[0])
    main = find_(max(range(len(frags)), key=lambda i: frags[i][1].area))
    return frags, [find_(i) == main for i in range(len(frags))]
def try_via_in(region, other):
    """A via that touches `region` (a stray fragment on this layer) and lands in `other` (main GND on the other layer)."""
    tgt = region.buffer(-0.05).intersection(other.buffer(-0.15))
    if tgt.is_empty: return None
    x0, y0, x1, y1 = tgt.bounds
    step = max(0.2, math.sqrt((x1 - x0) * (y1 - y0) / 600.0))
    nx, ny = max(2, int((x1 - x0) / step) + 1), max(2, int((y1 - y0) / step) + 1)
    c = tgt.representative_point()
    pts = sorted(((x0 + (x1 - x0) * i / (nx - 1), y0 + (y1 - y0) * j / (ny - 1)) for i in range(nx) for j in range(ny)),
                 key=lambda p: c.distance(Point(p)))
    for x, y in pts:
        if tgt.contains(Point(x, y)) and cu.via_ok(x, y, "GND"):
            v = add_via(x, y, GND); cu.add_track(v); return (x, y)
    return None
for it in range(4):
    frags, ok = gnd_graph()
    mainF = [p for (L, p), k in zip(frags, ok) if k and L == pcbnew.F_Cu]
    mainB = [p for (L, p), k in zip(frags, ok) if k and L == pcbnew.B_Cu]
    from shapely.ops import unary_union
    main = {pcbnew.F_Cu: unary_union(mainF), pcbnew.B_Cu: unary_union(mainB)}
    other = {pcbnew.F_Cu: main[pcbnew.B_Cu], pcbnew.B_Cu: main[pcbnew.F_Cu]}
    fixes = 0
    for (L, poly), k in zip(frags, ok):                     # stray pour fragments
        if not k and try_via_in(poly, other[L]): fixes += 1
    for fp in b.GetFootprints():                            # SMD GND pads that no main pour reaches
        for pad in fp.Pads():
            if pad.GetNetname() != "GND" or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
            L = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            shp = polyset_to_shapely(pad.GetEffectivePolygon())
            if main[L].intersects(shp.buffer(0.05)): continue
            x, y = Bf(pad.GetPosition()); done = False
            cands = sorted(((x + dx * 0.25, y + dy * 0.25) for dx in range(-28, 29) for dy in range(-28, 29)),
                           key=lambda p: math.hypot(p[0] - x, p[1] - y))
            for vx, vy in cands:
                d = math.hypot(vx - x, vy - y)
                if d < 0.6 or d > 7.0: continue
                if main[L].buffer(-0.2).contains(Point(vx, vy)):             # a short track into the main pour is enough
                    seg = LineString([(x, y), (vx, vy)]).buffer(0.1)
                    if cu.clear(seg, "GND", [L], 0.15, pads_any_net=False):
                        t_ = add_track((x, y), (vx, vy), L, GND, w=0.2); cu.add_track(t_); fixes += 1; done = True; break
                lands = other[L].buffer(-0.35).contains(Point(vx, vy)) or main[L].buffer(-0.35).contains(Point(vx, vy))
                if not lands or not cu.via_ok(vx, vy, "GND"): continue
                seg = LineString([(x, y), (vx, vy)]).buffer(0.15)
                if not cu.clear(seg, "GND", [L], 0.2, pads_any_net=False): continue
                v = add_via(vx, vy, GND); t = add_track((x, y), (vx, vy), L, GND); cu.add_track(v); cu.add_track(t)
                fixes += 1; done = True; break
            if not done: print("  could not reach", fp.GetReference(), pad.GetNumber())
    print("repair pass", it, "fixes", fixes, "stray fragments", ok.count(False))
    if not fixes: break
    fill()

# ------------------------------------------------------------------ save into the project, DRC
for fp in b.GetFootprints():                                           # hole labels would sit under the top-plate bosses
    if fp.GetReference().startswith("H"): fp.Reference().SetVisible(False)
pcb_out = os.path.join(PROJ, "top_pcb.kicad_pcb")
b.Save(pcb_out)
shutil.copy(os.path.join(OUT, "top_pcb.kicad_sch"), os.path.join(PROJ, "top_pcb.kicad_sch"))
rpt = os.path.join(OUT, "drc.rpt")
b2 = pcbnew.LoadBoard(pcb_out)                                         # reload so the project's net classes apply
pcbnew.ZONE_FILLER(b2).Fill(b2.Zones()); b2.Save(pcb_out)
pcbnew.WriteDRCReport(b2, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
print("".join(l for l in open(rpt) if l.startswith("**")))
