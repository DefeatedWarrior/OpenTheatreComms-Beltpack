"""Build the top PCB: footprints and nets from the schematic netlist, placement from design.py, GND fanout vias,
autorouting with Freerouting, GND pours on both layers with stitching vias, then a DRC report.

  python3 make_pcb.py            # everything
  python3 make_pcb.py place      # stop after placement (writes out/placed.kicad_pcb and out/top_pcb.dsn)
"""
import os, sys, json, math, re, shutil, subprocess
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from design import C
from sexp import parse, find, first
from pcbgeom import P, Bf, mm, MM, Copper, board_outline
from shapely.geometry import Point, LineString

PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "top_pcb"))
TPL = os.path.join(HERE, "template")
OUT = os.path.join(HERE, "out")
FREEROUTING = "/home/claude/tools/freerouting-1.9.0.jar"
FPLIB = "/usr/share/kicad/footprints"
stage = sys.argv[1] if len(sys.argv) > 1 else "all"
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ project file with net classes
pro = json.load(open(os.path.join(TPL, "top_pcb.kicad_pro")))
cls = pro["net_settings"]["classes"]
if not any(c["name"] == "Power" for c in cls):
    pw = dict(cls[0]); pw.update(name="Power", track_width=0.25, clearance=0.15); cls.append(pw)
cls[0]["clearance"] = 0.15
for c_ in cls:
    if c_["name"] == "Power": c_["clearance"] = 0.15                                    # Default: JLC 2-layer allows 0.1; the LP5024 fan-out needs 0.15
if not any(c["name"] == "Fine" for c in cls):                # nets on the LP5024's 0.4 mm pins
    fn = dict(cls[0]); fn.update(name="Fine", track_width=0.15, clearance=0.15); cls.append(fn)
FINE = ["/L%d_%s" % (k, c_) for k in range(6) for c_ in "RGB"] + ["/SDA", "/SCL", "/IREF_LED", "/VCAP_LED", "/LED_EN"]
pro["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": "+3V3"}, {"netclass": "Power", "pattern": "GND"}] + \
    [{"netclass": "Fine", "pattern": n} for n in FINE]
pro["meta"]["filename"] = "top_pcb.kicad_pro"
os.makedirs(PROJ, exist_ok=True)
json.dump(pro, open(os.path.join(PROJ, "top_pcb.kicad_pro"), "w"), indent=2)
shutil.copytree(os.path.join(HERE, "lib"), os.path.join(PROJ, "lib"), dirs_exist_ok=True)     # the OLED tail pads and the LP5024 symbol
open(os.path.join(PROJ, "sym-lib-table"), "w").write('(sym_lib_table\n  (version 7)\n  (lib (name "OpenTheatreComms")(type "KiCad")(uri "${KIPRJMOD}/lib/OpenTheatreComms.kicad_sym")(options "")(descr "Top PCB parts"))\n)\n')
open(os.path.join(PROJ, "fp-lib-table"), "w").write('(fp_lib_table\n  (version 7)\n  (lib (name "OpenTheatreComms")(type "KiCad")(uri "${KIPRJMOD}/lib/OpenTheatreComms.pretty")(options "")(descr "Top PCB parts"))\n)\n')

# ------------------------------------------------------------------ schematic netlist (pad -> net) and symbol uuids
netl = parse(open(os.path.join(OUT, "top_pcb.net")).read())[0]
padnet = {}
for n in find(first(netl, "nets"), "net"):
    name = str(first(n, "name")[1])
    for nd in find(n, "node"): padnet[(str(first(nd, "ref")[1]), str(first(nd, "pin")[1]))] = name
schinfo = json.load(open(os.path.join(OUT, "top_pcb_schinfo.json")))

b = pcbnew.LoadBoard(os.path.join(TPL, "top_pcb.kicad_pcb"))
nets = {}
for name in sorted(set(padnet.values())):
    ni = pcbnew.NETINFO_ITEM(b, name); b.Add(ni); nets[name] = ni
GND = nets["GND"]

existing = {f.GetReference(): f for f in b.GetFootprints()}
fps = {}
def put(fp, side, x, y, rot):
    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(0)
    if side == "B": fp.Flip(P(x, y), False)
    fp.SetOrientationDegrees(rot)
def padxy(fp, num): return [Bf(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]

for c in C:
    side, x, y, rot = c["pcb"]
    lib, name = c["fp"].split(":")
    if c["ref"] in existing: fp = existing[c["ref"]]                 # the template's mounting holes
    else:
        fp = pcbnew.FootprintLoad(os.path.join(HERE, "lib", lib + ".pretty") if lib == "OpenTheatreComms" else os.path.join(FPLIB, lib + ".pretty"), name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name)); b.Add(fp)
        put(fp, side, x, y, rot)
    fp.SetReference(c["ref"]); fp.SetValue(c["value"])
    fp.SetPath(pcbnew.KIID_PATH("/" + schinfo["symbols"][c["ref"]]))
    fp.SetProperty("Sheetfile", "top_pcb.kicad_sch"); fp.SetProperty("Sheetname", "")
    if c["mpn"]: fp.SetProperty("MPN", c["mpn"])
    if c["lib_id"] == "Device:RotaryEncoder":                         # anchor on the shaft (midpoint of the two SH tabs)
        sh = padxy(fp, "SH"); mx = sum(p[0] for p in sh) / 2; my = sum(p[1] for p in sh) / 2
        fp.Move(pcbnew.VECTOR2I(MM(float(x - mx)), MM(float(-(y - my)))))
    for pad in fp.Pads():
        nn = padnet.get((c["ref"], pad.GetNumber()))
        if nn: pad.SetNet(nets[nn])
    # small parts: reference only on the fab layer (assembly drawing); keep silk refs on the big parts
    small = c["fp"].split(":")[0] in ("Resistor_SMD", "Capacitor_SMD", "LED_SMD")
    ref = fp.Reference()
    ref.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8))); ref.SetTextThickness(MM(0.12))
    if small: ref.SetVisible(False)
    fps[c["ref"]] = fp

# orientation checks for the parts whose direction matters
j2 = fps["J2"]
assert padxy(j2, "1")[0][0] < 0, "J2 pad 1 expected at -X (design.oled_pad assumes it)"
for e in ("ENC1", "ENC2"):
    sh = padxy(fps[e], "SH"); assert padxy(fps[e], "C")[0][1] < sh[0][1] - 5, e + " pins should face the front"
assert padxy(fps["J1"], "1")[0][1] > padxy(fps["J1"], "MP")[0][1], "J1 pin row should face the back"
j2.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)                    # GND pads join the B pour (the GND bar between the pads and the notch)
for pad in fps["U1"].Pads():                                            # fine-pitch GND pins: solid to the pour
    if pad.GetNetname() == "GND": pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

# no tracks between the tail pads and the notch on B: the pour there becomes a GND bar joining the back ends of its GND pads
ra = pcbnew.ZONE(b); ra.SetIsRuleArea(True); ra.SetLayer(pcbnew.B_Cu); ra.SetZoneName("J2 GND bar")
ra.SetDoNotAllowTracks(True); ra.SetDoNotAllowVias(False); ra.SetDoNotAllowCopperPour(False)
ra.SetDoNotAllowPads(False); ra.SetDoNotAllowFootprints(False)
ol = ra.Outline(); ol.NewOutline()
for x, y in ((-10.6, 6.4), (10.6, 6.4), (10.6, 8.6), (-10.6, 8.6)): ol.Append(MM(float(150 + x)), MM(float(105 - y)))
b.Add(ra)

for ref, (x, y) in (("U1", (0.0, -4.6)), ("J1", (-13.0, -3.3))):          # references clear of the pads
    fps[ref].Reference().SetPosition(P(x, y))

# board text on the bottom silk
txt = pcbnew.PCB_TEXT(b); txt.SetText("OpenTheatreComms beltpack  top PCB  rev 0.1"); txt.SetLayer(pcbnew.B_SilkS)
txt.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8))); txt.SetTextThickness(MM(0.12)); txt.SetPosition(P(0, -10.6)); txt.SetMirrored(True)
b.Add(txt)

b.BuildConnectivity()

# ------------------------------------------------------------------ track and via helpers
def add_via(x, y, net, locked=True):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(net)
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLocked(locked); b.Add(v); return v
def add_track(a, c_, layer, net, w=0.3, locked=True):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net)
    t.SetLocked(locked); b.Add(t); return t


# OLED passives: adjacent FPC pins fan out in order to their caps (planar, so pre-routed and locked)
def pre(path, net):
    for a_, c_ in zip(path, path[1:]): add_track(a_, c_, pcbnew.B_Cu, net, w=0.2, locked=True)
jp = {n: padxy(j2, str(n))[0] for n in (26, 27, 28, 29)}
c2 = {k: padxy(fps["C2"], k)[0] for k in "12"}; c3 = {k: padxy(fps["C3"], k)[0] for k in "12"}
assert abs(c2["2"][0] - jp[26][0]) < 0.4 and c3["1"][0] > c3["2"][0], "charge-pump caps not where the fan-out expects"
cl = {r: {k: padxy(fps[r], k)[0] for k in "12"} for r in ("C4", "C5", "R12")}
assert cl["C4"]["1"][0] < cl["C5"]["1"][0] < cl["R12"]["1"][0], "OLED supply caps not where the fan-out expects"
# left side, mirrored: VCC (pad 3) to C4, VCOMH (pad 4) to C5, IREF (pad 5) to R12
jp.update({n: padxy(j2, str(n))[0] for n in (3, 4, 5)})
for n, (cap, k, yrun) in {26: (c2, "2", None), 27: (c2, "1", 2.05), 28: (c3, "2", 2.5), 29: (c3, "1", 2.95),
                          5: (cl["R12"], "1", None), 4: (cl["C5"], "1", 2.5), 3: (cl["C4"], "1", 2.95)}.items():
    x0, y0 = jp[n]; xc, yc = cap[k]; net = j2.FindPadByNumber(str(n)).GetNet()
    pre([(x0, y0), (x0, yc + 0.25), (xc, yc)] if yrun is None else [(x0, y0), (x0, yrun), (xc, yrun), (xc, yc)], net)
# ------------------------------------------------------------------ GND fanout vias for every SMD GND pad (locked, before routing)
cu = Copper(b)
def fanout(pad, layer, dists=(1.15, 1.5, 1.9, 2.4)):
    x, y = Bf(pad.GetPosition()); sx, sy = mm(pad.GetBoundingBox().GetWidth()) / 2, mm(pad.GetBoundingBox().GetHeight()) / 2
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)]
    dirs.sort(key=lambda d: -abs(d[0] * sx + d[1] * sy))              # prefer leaving along the pad's long axis
    for d in dists:
        for dx, dy in dirs:
            vx = x + dx * (sx + 0.3 + d - 1.0) if dx else x
            vy = y + dy * (sy + 0.3 + d - 1.0) if dy else y
            if not cu.via_ok(vx, vy, "GND"): continue
            seg = LineString([(x, y), (vx, vy)]).buffer(0.15)
            if not cu.clear(seg, "GND", [layer], 0.2, pads_any_net=False): continue
            v = add_via(vx, vy, GND); t = add_track((x, y), (vx, vy), layer, GND)
            cu.add_track(v); cu.add_track(t); return (vx, vy)
    return None

skipped = []
for fp in b.GetFootprints():
    if fp.GetReference() == "J2": continue
    L = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
    for pad in fp.Pads():
        if pad.GetNetname() == "GND" and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
            if fanout(pad, L) is None: skipped.append(f"{fp.GetReference()}.{pad.GetNumber()}")
# J2: the GND pads join the B-side GND bar above them; stitch it to the F pour
for vx in (-9.0, -6.0, -2.5, 2.5, 6.0, 9.0):
    if cu.via_ok(vx, 7.9, "GND"): cu.add_track(add_via(vx, 7.9, GND))
print("fanout skipped:", skipped)
# the expander's GND pin 12: its fanout goes straight down past the pins to a via near the bottom edge (a via under the
# chip lands on a top-side island once the key and LED lines are routed across it)
_u1 = fps["U1"]; _p12 = [p for p in _u1.Pads() if p.GetNumber() == "12"][0]; _q = Bf(_p12.GetPosition())
_kill = []
for tr in b.GetTracks():
    if tr.GetNetname() == "GND" and tr.GetClass() == "PCB_TRACK" and min(math.dist(Bf(tr.GetStart()), _q), math.dist(Bf(tr.GetEnd()), _q)) < 0.05:
        far = Bf(tr.GetEnd()) if math.dist(Bf(tr.GetStart()), _q) < 0.05 else Bf(tr.GetStart())
        _kill.append(tr)
        _kill += [v for v in b.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == "GND" and math.dist(Bf(v.GetPosition()), far) < 0.05]
for it_ in {id(x): x for x in _kill}.values(): b.Delete(it_)
_dn = (_q[0], _q[1] - 3.2)
add_track(_q, _dn, pcbnew.B_Cu, b.FindNet("GND"), w=0.3); add_via(*_dn, b.FindNet("GND"))
# C12 sits just past the link connector's pins 1 (GND) and 2 (+3V3): short fixed links to both
_j1 = {p.GetNumber(): Bf(p.GetPosition()) for p in fps["J1"].Pads()}
for p in fps["C12"].Pads():
    add_track(Bf(p.GetPosition()), _j1["1" if p.GetNetname() == "GND" else "2"], pcbnew.B_Cu, p.GetNet(), w=0.3)
# LP5024 exposed pad: GND through its pins 25 and 26 (joined below) to the B pour; at about 50 mW it needs no thermal vias
# LP5024: ADDR0 (GND) joins the exposed pad (its thermal vias reach the F pour) with a short stub straight inward
u2 = fps["U2"]; ep = [p for p in u2.Pads() if p.GetNumber() == "33" and p.GetSize().x > MM(2)][0]
ex, ey = Bf(ep.GetPosition()); hw = pcbnew.ToMM(ep.GetSize().x) / 2 - 0.2
for p in u2.Pads():
    if p.GetNetname() == "GND" and p.GetNumber() != "33":
        px, py = Bf(p.GetPosition())
        tx, ty = min(max(px, ex - hw), ex + hw), min(max(py, ey - hw), ey + hw)
        add_track((px, py), (tx, ty), pcbnew.B_Cu if u2.IsFlipped() else pcbnew.F_Cu, p.GetNet(), w=0.2); print("U2 pad", p.GetNumber(), "joined to the exposed pad")
# its VCC pin (27) can't take the 0.25 mm Power width between 0.4 mm pins: a short 0.2 mm stub outward
L2 = pcbnew.B_Cu if u2.IsFlipped() else pcbnew.F_Cu
pp = {p.GetNumber(): Bf(p.GetPosition()) for p in u2.Pads()}
def outward(q, d):
    dx, dy = q[0] - ex, q[1] - ey
    return (q[0] + (d if dx > 0 else -d), q[1]) if abs(dx) > abs(dy) else (q[0], q[1] + (d if dy > 0 else -d))
v33 = b.FindNet("+3V3"); add_track(pp["27"], outward(pp["27"], 1.0), L2, v33, w=0.2)
for n_ in ("28", "29", "30", "31", "32"):                             # the rest of that side: stubs too, so the router fans them in order
    pd = [p for p in u2.Pads() if p.GetNumber() == n_][0]; add_track(pp[n_], outward(pp[n_], 1.0), L2, pd.GetNet(), w=0.15)
# its support parts (placed in design.py with the pad on the pin's net toward the driver): fixed short links from the stubs
def padxy_(ref_, net_): return [Bf(p.GetPosition()) for p in fps[ref_].Pads() if p.GetNetname() == net_][0]
def link(pts, net_, w_):
    for a_, c_ in zip(pts, pts[1:]):
        if math.dist(a_, c_) > 1e-3: add_track(a_, c_, L2, b.FindNet(net_), w=w_)
e27, e31, e32 = outward(pp["27"], 1.0), outward(pp["31"], 1.0), outward(pp["32"], 1.0)
p14, p1_, p13 = padxy_("C14", "+3V3"), padxy_("R1", "/IREF_LED"), padxy_("C13", "/VCAP_LED")
link([e27, p14], "+3V3", 0.2)                                                   # VCC down-right to C14
link([e32, (e32[0], p13[1]), p13], "/VCAP_LED", 0.15)                           # VCAP down, then left into C13
link([e31, (e31[0], p1_[1]), p1_], "/IREF_LED", 0.15)                           # IREF further down, then left into R1
b.Save(os.path.join(OUT, "placed.kicad_pcb"))
dsn = os.path.join(OUT, "top_pcb.dsn")
ok = pcbnew.ExportSpecctraDSN(b, dsn); print("DSN", ok)
if stage == "place": sys.exit(0)

# ------------------------------------------------------------------ autoroute everything except GND (that goes to the pours)
txt = open(dsn).read()
m = re.search(r'\(class kicad_default "" (.*?)\n\s*\(circuit', txt, re.S)
toks = [t for t in re.findall(r'"[^"]*"|\S+', m.group(1)) if t not in ["+3V3", "GND"] + FINE]
txt = txt[:m.start(1)] + " ".join(toks) + txt[m.end(1):]
extra = '''    (class Power +3V3
      (circuit (use_via Via[0-1]_600:300_um))
      (rule (width 250) (clearance 200.1))
    )
    (class GND GND
      (circuit (use_via Via[0-1]_600:300_um))
      (rule (width 400) (clearance 200.1))
    )
''' + "    (class Fine " + " ".join(FINE) + """
      (circuit (use_via Via[0-1]_600:300_um))
      (rule (width 150) (clearance 150.1))
    )
"""
i = txt.index("  )\n  (wiring")
txt = txt[:i] + extra + txt[i:]
# GND is left to the pours: give it a single pin so the router has nothing to connect
txt = re.sub(r'(\(net GND\s*\(pins )([^)]*)\)', lambda m_: m_.group(1) + m_.group(2).split()[0] + ")", txt, count=1)
# keep the router clear of the board edge: its own 0.2 mm boundary clearance plus a boundary drawn 0.32 mm inside
edge = board_outline(b).buffer(-0.32, join_style=2)
pts = " ".join(f"{(150 + x) * 1000:.1f} {-(105 - y) * 1000:.1f}" for x, y in list(edge.exterior.coords))
m2 = re.search(r"\(boundary\s*\(path pcb 0 [^)]*\)", txt)
txt = txt[:m2.start()] + f"(boundary\n      (path pcb 0 {pts})" + txt[m2.end():]
lines = txt.split("\n")
txt = "\n".join(l for l in lines if "(net GND)" not in l)
kos = []
def ko(geom, layer):
    pts = " ".join(f"{(150 + x) * 1000:.1f} {-(105 - y) * 1000:.1f}" for x, y in list(geom.exterior.coords)[:-1])
    kos.append(f'    (keepout "" (polygon {layer} 0 {pts}))\n')
for tr in b.GetTracks():
    if tr.GetNetname() != "GND": continue
    if tr.GetClass() == "PCB_VIA":
        g = Point(*Bf(tr.GetPosition())).buffer(0.31, quad_segs=2); ko(g, "F.Cu"); ko(g, "B.Cu")
    else:
        g = LineString([Bf(tr.GetStart()), Bf(tr.GetEnd())]).buffer(0.16, quad_segs=2); ko(g, tr.GetLayerName())
i = txt.index('    (via "Via[0-1]')
txt = txt[:i] + "".join(kos) + txt[i:]
print("GND keep-outs for the router:", len(kos))
open(dsn, "w").write(txt)
ses = os.path.join(OUT, "top_pcb.ses")
if stage != "import":                                                # 'import' reuses the last session file
  if os.path.exists(ses): os.remove(ses)
  log = subprocess.run(["xvfb-run", "-a", "java", "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", "100"],
                     capture_output=True, text=True, timeout=1500, cwd=OUT)
  open(os.path.join(OUT, "freerouting.log"), "w").write(log.stdout + log.stderr)
  print("freerouting rc", log.returncode, [l for l in (log.stdout + log.stderr).splitlines() if "pass" in l.lower() or "unrouted" in l.lower()][-4:])

# ------------------------------------------------------------------ import the session: replace all tracks with the routed ones
for t in list(b.GetTracks()):                                         # keep the locked pre-routes; the session omits fixed wires
    if not t.IsLocked(): b.Remove(t)
locked_segs = {(tuple(round(v, 3) for v in Bf(t.GetStart())), tuple(round(v, 3) for v in Bf(t.GetEnd()))) for t in b.GetTracks()}
locked_geo = [(t.GetNetname(), t.GetLayer(), LineString([Bf(t.GetStart()), Bf(t.GetEnd())])) for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
S = parse(open(ses).read())[0]
routes = first(S, "routes")
res = first(routes, "resolution"); scale = 1.0 / (1000.0 * float(res[2])) if str(res[1]) == "um" else None
LAY = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
def sxy(a, c): return (float(a) * scale - 150.0, 105.0 + float(c) * scale)   # SES y = -KiCad y
nt = nv = 0
for n in find(first(routes, "network_out"), "net"):
    net = nets[str(n[1])]
    for w in find(n, "wire"):
        pth = first(w, "path"); layer = LAY[str(pth[1])]; width = float(pth[2]) * scale
        pts = [sxy(pth[k], pth[k + 1]) for k in range(3, len(pth) - 1, 2)]
        for a, c_ in zip(pts, pts[1:]):
            k = (tuple(round(v, 3) for v in a), tuple(round(v, 3) for v in c_))
            if k in locked_segs or k[::-1] in locked_segs: continue
            if math.hypot(c_[0] - a[0], c_[1] - a[1]) < 0.005: continue          # zero-length stubs at fixed wires
            if any(nn == str(n[1]) and ll == layer and g.distance(Point(a)) < 0.01 and g.distance(Point(c_)) < 0.01 for nn, ll, g in locked_geo): continue
            add_track(a, c_, layer, net, w=width, locked=False); nt += 1
    for v in find(n, "via"):
        add_via(*sxy(v[2], v[3]), net, locked=False); nv += 1
print("imported", nt, "track segments,", nv, "vias")
from pcbgeom import net_islands
incomplete = {n: [sorted(x) for x in g] for n, g in net_islands(b).items() if len(g) > 1}
print("incomplete nets after routing:", incomplete or "none")

# a piece the router left alone: a straight track (either layer) to the nearest same-net pad or track end, when the line is clear
from pcbgeom import Copper
cu = Copper(b)
for n, groups in net_islands(b).items():
    if len(groups) < 2 or n == "GND": continue
    groups = sorted(groups, key=len); main = groups[-1]
    tgt = []
    for ref2, num2 in main:
        pb = [q for q in b.FindFootprintByReference(ref2).Pads() if q.GetNumber() == num2][0]; tgt.append(Bf(pb.GetPosition()))
    tgt += [Bf(e) for tr in b.GetTracks() if tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == n for e in (tr.GetStart(), tr.GetEnd())]
    for piece in groups[:-1]:
        pads_ = [Bf(q.GetPosition()) for ref, num in piece for q in b.FindFootprintByReference(ref).Pads() if q.GetNumber() == num]
        srcs = list(pads_)
        for tr in b.GetTracks():                                      # plus the far end of any stub leaving those pads
            if tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == n:
                s_, e_ = Bf(tr.GetStart()), Bf(tr.GetEnd())
                if any(math.dist(s_, q) < 0.05 for q in pads_): srcs.append(e_)
                if any(math.dist(e_, q) < 0.05 for q in pads_): srcs.append(s_)
        best = None
        for a_ in srcs:
            for c_ in tgt:
                d = math.dist(a_, c_)
                if d < 0.3 or d > 6.0 or (best and d >= best[0]) or any(math.dist(c_, s2) < 0.05 for s2 in srcs): continue
                for L in (pcbnew.B_Cu, pcbnew.F_Cu):
                    if cu.clear(LineString([a_, c_]).buffer(0.1), n, [L], 0.16, pads_any_net=False): best = (d, a_, c_, L); break
        if best:
            cu.add_track(add_track(best[1], best[2], best[3], b.FindNet(n), w=0.2, locked=False)); print("joined", n, sorted(piece), f"{best[0]:.1f} mm")
            continue
        # no straight line: an L (either layer), or a via at the stranded end and then a straight line or an L on the other side
        fine = n in FINE; w_ = 0.15 if fine else 0.2; cl_ = 0.15
        tg2 = list(tgt)
        for tr in b.GetTracks():                                      # points along the main copper too
            if tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == n:
                ln = LineString([Bf(tr.GetStart()), Bf(tr.GetEnd())])
                tg2 += [(ln.interpolate(k * 0.25).x, ln.interpolate(k * 0.25).y) for k in range(int(ln.length / 0.25) + 1)]
        stubs = [LineString([Bf(tr.GetStart()), Bf(tr.GetEnd())]) for tr in b.GetTracks() if tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == n
                 and any(min(math.dist(Bf(tr.GetStart()), q), math.dist(Bf(tr.GetEnd()), q)) < 0.05 for q in pads_)]
        tg2 = [c_ for c_ in tg2 if not any(math.dist(c_, s2) < 0.05 for s2 in srcs) and not any(sg.distance(Point(c_)) < 0.05 for sg in stubs)]
        def ok_path(pts, L):
            return all(cu.clear(LineString([pts[i], pts[i + 1]]).buffer(w_ / 2), n, [L], cl_, pads_any_net=False) for i in range(len(pts) - 1) if math.dist(pts[i], pts[i + 1]) > 1e-3)
        best = None
        for a_ in srcs:
            for c_ in tg2:
                d = abs(c_[0] - a_[0]) + abs(c_[1] - a_[1])
                if d > 8.0 or (best and d >= best[0]): continue
                for corner in ((a_[0], c_[1]), (c_[0], a_[1])):
                    for L in (pcbnew.B_Cu, pcbnew.F_Cu):
                        on_L = any(tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == n and tr.GetLayer() == L and LineString([Bf(tr.GetStart()), Bf(tr.GetEnd())]).distance(Point(c_)) < 0.01 for tr in b.GetTracks()) or c_ in tgt
                        if not on_L: continue
                        start_L = any(tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == n and tr.GetLayer() == L and min(math.dist(Bf(tr.GetStart()), a_), math.dist(Bf(tr.GetEnd()), a_)) < 0.01 for tr in b.GetTracks())
                        need_via = not start_L
                        if need_via and not cu.via_ok(a_[0], a_[1], n): continue
                        if ok_path([a_, corner, c_], L):
                            best = (d + (1.0 if need_via else 0), a_, corner, c_, L, need_via); break
                    if best and best[1] == a_ and best[3] == c_: break
        if best:
            _, a_, corner, c_, L, need_via = best
            if need_via: cu.add_track(add_via(a_[0], a_[1], b.FindNet(n), locked=False))
            for s_, e_ in ((a_, corner), (corner, c_)):
                if math.dist(s_, e_) > 1e-3: cu.add_track(add_track(s_, e_, L, b.FindNet(n), w=w_, locked=False))
            print("joined (L)", n, sorted(piece), "via" if need_via else "", f"{best[0]:.1f} mm")
incomplete = {n: [sorted(x) for x in g] for n, g in net_islands(b).items() if len(g) > 1}
print("incomplete nets after the joins:", incomplete or "none")
b.Save(os.path.join(OUT, "routed.kicad_pcb"))

