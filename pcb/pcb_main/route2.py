"""Second routing round: take a routed board, export it with its routing in place (GND and +3V3 hidden as in make_pcb.py),
let Freerouting finish the remaining connections, and re-import.

  python3 route2.py [in_board] [passes] [out_board]      # defaults: out/routed.kicad_pcb 30 out/routed.kicad_pcb
  python3 route2.py in_board import [out_board]          # re-import out/route2.ses without rerouting
"""
import os, sys, re, math, subprocess
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sexp import parse, find, first
from pcbgeom import P, Bf, MM, board_outline, net_islands
from shapely.geometry import Point, LineString
OUT = os.path.join(HERE, "out")
FREEROUTING = "/home/claude/tools/freerouting-1.9.0.jar"
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "routed.kicad_pcb")
passes = sys.argv[2] if len(sys.argv) > 2 else "30"
dst = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, "routed.kicad_pcb")
b = pcbnew.LoadBoard(src)
EDGE = board_outline(b)
nets = {b.FindNet(i).GetNetname(): b.FindNet(i) for i in range(b.GetNetCount())}

def add_track(a, c_, layer, net, w):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net); b.Add(t); return t
def add_via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(net)
    v.SetViaType(pcbnew.VIATYPE_THROUGH); b.Add(v); return v

dsn = os.path.join(OUT, "route2.dsn"); ses = os.path.join(OUT, "route2.ses")
pcbnew.ExportSpecctraDSN(b, dsn)
txt = open(dsn).read()
VIA = re.search(r'\(via "(Via\[[^"]*)"\)', txt).group(1)
m = re.search(r'\(class kicad_default "" (.*?)\n\s*\(circuit', txt, re.S)
special = {"/VBUS", "/SYS", "/BAT", "/LR_VDD", "GND", "+3V3"}
toks = [t for t in re.findall(r'"[^"]*"|\S+', m.group(1)) if t not in special]
txt = txt[:m.start(1)] + " ".join(toks) + txt[m.end(1):]
extra = f'''    (class Power /VBUS /SYS /BAT /LR_VDD +3V3
      (circuit (use_via {VIA}))
      (rule (width 400) (clearance 200.1))
    )
    (class Planes GND
      (circuit (use_via {VIA}))
      (rule (width 400) (clearance 200.1))
    )
'''
i = txt.index("  )\n  (wiring"); txt = txt[:i] + extra + txt[i:]
for netname in ("GND",):
    txt = re.sub(r'(\(net ' + re.escape(netname) + r'\s*\(pins )([^)]*)\)', lambda m_: m_.group(1) + m_.group(2).split()[0] + ")", txt, count=1)
txt = "\n".join(l for l in txt.split("\n") if "(net GND)" not in l)
kos = []
def ko(geom, layer):
    pts = " ".join(f"{(150 + x) * 1000:.1f} {-(105 - y) * 1000:.1f}" for x, y in list(geom.exterior.coords)[:-1])
    kos.append(f'    (keepout "" (polygon {layer} 0 {pts}))\n')
for tr in b.GetTracks():
    if tr.GetNetname() != "GND": continue
    if tr.GetClass() == "PCB_VIA":
        g = Point(*Bf(tr.GetPosition())).buffer(0.31, quad_segs=2); ko(g, "F.Cu"); ko(g, "B.Cu"); ko(g, "In1.Cu")
    else:
        g = LineString([Bf(tr.GetStart()), Bf(tr.GetEnd())]).buffer(0.16, quad_segs=2); ko(g, tr.GetLayerName())
i = txt.index(f'    (via "{VIA}")'); txt = txt[:i] + "".join(kos) + txt[i:]
# In1 (the +3V3 plane) becomes a third routing layer, at a cost, for the few routes the outer layers can't take
txt = txt.replace("(layer In1.Cu\n      (type power)", "(layer In1.Cu\n      (type signal)", 1)
ars = """    (autoroute_settings
      (fanout off) (autoroute on) (postroute on) (vias on)
      (via_costs 50) (plane_via_costs 5) (start_ripup_costs 100) (start_pass_no 1)
      (layer_rule F.Cu (active on) (preferred_direction horizontal) (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 2.0))
      (layer_rule In1.Cu (active on) (preferred_direction horizontal) (preferred_direction_trace_costs 1.2) (against_preferred_direction_trace_costs 2.0))
      (layer_rule In2.Cu (active off) (preferred_direction vertical) (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 2.0))
      (layer_rule B.Cu (active on) (preferred_direction vertical) (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 2.0))
    )
"""
i = txt.index("\n    )\n", txt.index("    (layer B.Cu")) + 7; txt = txt[:i] + ars + txt[i:]     # right after the layer list
edge = EDGE.buffer(-0.32, join_style=2)
pts = " ".join(f"{(150 + x) * 1000:.1f} {-(105 - y) * 1000:.1f}" for x, y in list(edge.exterior.coords))
m2 = re.search(r"\(boundary\s*\(path pcb 0 [^)]*\)", txt)
txt = txt[:m2.start()] + f"(boundary\n      (path pcb 0 {pts})" + txt[m2.end():]
open(dsn, "w").write(txt)
if passes != "import":
    if os.path.exists(ses): os.remove(ses)
    log = subprocess.run(["xvfb-run", "-a", "java", "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", passes],
                         capture_output=True, text=True, timeout=7000, cwd=OUT)
    print("freerouting rc", log.returncode)

tracks = list(b.GetTracks())
locked_geo = [(t.GetNetname(), t.GetLayer(), LineString([Bf(t.GetStart()), Bf(t.GetEnd())])) for t in tracks if t.GetClass() == "PCB_TRACK" and t.IsLocked()]
locked_vias = [(t.GetNetname(), Bf(t.GetPosition())) for t in tracks if t.GetClass() == "PCB_VIA" and t.IsLocked()]
for t in tracks:
    if not t.IsLocked(): b.Delete(t)
S = parse(open(ses).read())[0]; routes = first(S, "routes")
res = first(routes, "resolution"); scale = 1.0 / (1000.0 * float(res[2]))
LAY = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu}
def sxy(a, c_): return (float(a) * scale - 150.0, 105.0 + float(c_) * scale)
nt = nv = 0
for n in find(first(routes, "network_out"), "net"):
    net = nets[str(n[1])]
    for w in find(n, "wire"):
        pth = first(w, "path"); layer = LAY[str(pth[1])]; width = float(pth[2]) * scale
        pts = [sxy(pth[k], pth[k + 1]) for k in range(3, len(pth) - 1, 2)]
        for a_, c_ in zip(pts, pts[1:]):
            if math.hypot(c_[0] - a_[0], c_[1] - a_[1]) < 0.005: continue
            if any(nn == str(n[1]) and ll == layer and g.distance(Point(a_)) < 0.01 and g.distance(Point(c_)) < 0.01 for nn, ll, g in locked_geo): continue
            add_track(a_, c_, layer, net, width); nt += 1
    for v in find(n, "via"):
        xy = sxy(v[2], v[3])
        if any(nn == str(n[1]) and math.dist(xy, q) < 0.01 for nn, q in locked_vias): continue
        add_via(*xy, net); nv += 1
print("imported", nt, "track segments,", nv, "vias")
b.Save(dst); b = pcbnew.LoadBoard(dst)
incomplete = {n: [sorted(x) for x in g] for n, g in net_islands(b, skip=("", "GND")).items() if len(g) > 1}
print("incomplete nets:", len(incomplete), incomplete or "none")
