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
    pw = dict(cls[0]); pw.update(name="Power", track_width=0.25, clearance=0.2); cls.append(pw)
pro["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": "+3V3"}, {"netclass": "Power", "pattern": "GND"}]
pro["meta"]["filename"] = "top_pcb.kicad_pro"
os.makedirs(PROJ, exist_ok=True)
json.dump(pro, open(os.path.join(PROJ, "top_pcb.kicad_pro"), "w"), indent=2)

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
        fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
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
assert padxy(j2, "MP")[0][1] > padxy(j2, "1")[0][1], "J2 entry must face the back edge"
assert padxy(j2, "1")[0][0] < 0, "J2 pad 1 expected at -X (design.oled_pad assumes it)"
for e in ("ENC1", "ENC2"):
    sh = padxy(fps[e], "SH"); assert padxy(fps[e], "C")[0][1] < sh[0][1] - 5, e + " pins should face the front"
assert padxy(fps["J1"], "1")[0][1] > padxy(fps["J1"], "MP")[0][1], "J1 pin row should face the back"
j2.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)                    # GND pads join the B pour under the connector body
for pad in fps["U1"].Pads():                                            # fine-pitch GND pins: solid to the pour
    if pad.GetNetname() == "GND": pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

# no tracks under the FPC connector body on B: the pour there becomes a GND bar joining the back ends of its GND pads
ra = pcbnew.ZONE(b); ra.SetIsRuleArea(True); ra.SetLayer(pcbnew.B_Cu); ra.SetZoneName("J2 GND bar")
ra.SetDoNotAllowTracks(True); ra.SetDoNotAllowVias(False); ra.SetDoNotAllowCopperPour(False)
ra.SetDoNotAllowPads(False); ra.SetDoNotAllowFootprints(False)
ol = ra.Outline(); ol.NewOutline()
for x, y in ((-9.0, 4.75), (9.0, 4.75), (9.0, 6.3), (-9.0, 6.3)): ol.Append(MM(float(150 + x)), MM(float(105 - y)))
b.Add(ra)

# silkscreen: the stacked status LEDs' outlines touch; keep the outline on the red one only (polarity is on the assembly drawing)
for ref in ("D6", "D8"):
    fp = fps[ref]; cy = Bf(fp.GetPosition())[1]
    for g in list(fp.GraphicalItems()):
        if g.GetClass() == "MGRAPHIC" and g.GetLayer() == pcbnew.F_SilkS:
            fp.Remove(g)
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
# J2: the GND pads join a B-side copper area under the connector body; stitch it to the F pour
for vx in (-6.5, -2.5, 2.5, 6.5):
    if cu.via_ok(vx, 5.55, "GND"): cu.add_track(add_via(vx, 5.55, GND))
print("fanout skipped:", skipped)
b.Save(os.path.join(OUT, "placed.kicad_pcb"))
dsn = os.path.join(OUT, "top_pcb.dsn")
ok = pcbnew.ExportSpecctraDSN(b, dsn); print("DSN", ok)
if stage == "place": sys.exit(0)

# ------------------------------------------------------------------ autoroute everything except GND (that goes to the pours)
txt = open(dsn).read()
m = re.search(r'\(class kicad_default "" (.*?)\n\s*\(circuit', txt, re.S)
toks = [t for t in re.findall(r'"[^"]*"|\S+', m.group(1)) if t not in ("+3V3", "GND")]
txt = txt[:m.start(1)] + " ".join(toks) + txt[m.end(1):]
extra = '''    (class Power +3V3
      (circuit (use_via Via[0-1]_600:300_um))
      (rule (width 250) (clearance 200.1))
    )
    (class GND GND
      (circuit (use_via Via[0-1]_600:300_um))
      (rule (width 400) (clearance 200.1))
    )
'''
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
  log = subprocess.run(["xvfb-run", "-a", "java", "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", "40"],
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

b.Save(os.path.join(OUT, "routed.kicad_pcb"))

