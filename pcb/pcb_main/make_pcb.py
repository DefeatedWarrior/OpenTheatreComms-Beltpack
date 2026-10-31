"""Build the main PCB: footprints and nets from the schematic netlist, placement from design.py (exact positions for the
big parts, an automatic placer for the small ones), a hand-laid RF chain, plane fanouts for GND (In2) and +3V3 (In1),
then Freerouting for everything else.

  python3 make_pcb.py           # everything
  python3 make_pcb.py place     # stop after placement and fanouts (out/placed.kicad_pcb, out/main_pcb.dsn)
  python3 make_pcb.py import    # re-import the last routing session instead of rerouting
"""
import os, sys, json, math, re, subprocess
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from design import C
from sexp import parse, find, first
from pcbgeom import P, Bf, mm, MM, Copper, board_outline, polyset_to_shapely, net_islands
from shapely.geometry import Point, LineString, box as sbox
from shapely.ops import unary_union
from shapely.affinity import translate
from shapely.strtree import STRtree

PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "main_pcb"))
TPL, OUT = os.path.join(HERE, "template"), os.path.join(HERE, "out")
FREEROUTING = "/home/claude/tools/freerouting-1.9.0.jar"
FPLIB = "/usr/share/kicad/footprints"; LOCAL_FP = os.path.join(HERE, "lib", "OpenTheatreComms.pretty")
stage = sys.argv[1] if len(sys.argv) > 1 else "all"
os.makedirs(OUT, exist_ok=True); os.makedirs(PROJ, exist_ok=True)

# ------------------------------------------------------------------ project: net classes, library tables
pro = json.load(open(os.path.join(TPL, "main_pcb.kicad_pro")))
base = pro["net_settings"]["classes"][0]
cls = [base] + [dict(base, name="Power", track_width=0.4, clearance=0.2), dict(base, name="RF", track_width=0.35, clearance=0.25)]
pro["net_settings"]["classes"] = cls
pro["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": p} for p in ("/VBUS", "/SYS", "/BAT", "/LR_VDD", "+3V3", "GND")] + \
                                           [{"netclass": "RF", "pattern": "/RF_*"}]
pro["meta"]["filename"] = "main_pcb.kicad_pro"
json.dump(pro, open(os.path.join(PROJ, "main_pcb.kicad_pro"), "w"), indent=2)
open(os.path.join(PROJ, "fp-lib-table"), "w").write('(fp_lib_table\n  (version 7)\n  (lib (name "OpenTheatreComms")(type "KiCad")(uri "${KIPRJMOD}/lib/OpenTheatreComms.pretty")(options "")(descr "Beltpack parts"))\n)\n')
open(os.path.join(PROJ, "sym-lib-table"), "w").write('(sym_lib_table\n  (version 7)\n  (lib (name "OpenTheatreComms")(type "KiCad")(uri "${KIPRJMOD}/lib/OpenTheatreComms.kicad_sym")(options "")(descr "Beltpack parts"))\n)\n')

# ------------------------------------------------------------------ netlist and symbol uuids
netl = parse(open(os.path.join(OUT, "main_pcb.net")).read())[0]
padnet = {}
for n in find(first(netl, "nets"), "net"):
    name = str(first(n, "name")[1])
    for nd in find(n, "node"): padnet[(str(first(nd, "ref")[1]), str(first(nd, "pin")[1]))] = name
schinfo = json.load(open(os.path.join(OUT, "main_pcb_schinfo.json")))

b = pcbnew.LoadBoard(os.path.join(TPL, "main_pcb.kicad_pcb"))
b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER); b.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
nets = {}
for name in sorted(set(padnet.values())):
    ni = pcbnew.NETINFO_ITEM(b, name); b.Add(ni); nets[name] = ni
GND, V33 = nets["GND"], nets["+3V3"]
EDGE = board_outline(b)

def load_fp(fpid):
    lib, name = fpid.split(":")
    fp = pcbnew.FootprintLoad(LOCAL_FP if lib == "OpenTheatreComms" else os.path.join(FPLIB, lib + ".pretty"), name)
    if fp is None: raise SystemExit("footprint not found: " + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name)); return fp
def put(fp, side, x, y, rot):
    """Place on a side at (x, y) with rotation rot, whatever side the footprint was on before."""
    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(0)
    if fp.IsFlipped() != (side == "B"): fp.Flip(P(x, y), False)
    fp.SetOrientationDegrees(rot)
def pads(fp, num): return [Bf(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
def pad1(fp, num): return pads(fp, num)[0]
def move_to(fp, dx, dy): fp.Move(pcbnew.VECTOR2I(MM(float(dx)), MM(float(-dy))))
def shift_pad(fp, num, x, y):
    px, py = pad1(fp, num); move_to(fp, x - px, y - py)
def orient(fp, side, x, y, test):
    for r in (0, 90, 180, 270):
        put(fp, side, x, y, r)
        if test(fp): return r
    raise SystemExit(f"no orientation satisfies the test for {fp.GetReference()}")
def courtyard(fp):
    g = polyset_to_shapely(fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd))
    if g.is_empty:
        bb = fp.GetBoundingBox(False, False); x0, y1 = Bf(bb.GetOrigin()); x1, y0 = Bf(bb.GetEnd()); g = sbox(x0, y0, x1, y1)
    return g

existing = {f.GetReference(): f for f in b.GetFootprints()}
fps = {}
for c in C:
    if c["ref"] in existing: fp = existing[c["ref"]]
    else: fp = load_fp(c["fp"]); b.Add(fp)
    fp.SetReference(c["ref"]); fp.SetValue(c["value"])
    fp.SetPath(pcbnew.KIID_PATH("/" + schinfo["symbols"][c["ref"]]))
    fp.SetProperty("Sheetfile", "main_pcb.kicad_sch"); fp.SetProperty("Sheetname", "")
    if c["mpn"]: fp.SetProperty("MPN", c["mpn"])
    if c["dnp"]:
        fp.SetProperty("DNP", "yes"); fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    for pad in fp.Pads():
        nn = padnet.get((c["ref"], pad.GetNumber()))
        if nn: pad.SetNet(nets[nn])
    ref = fp.Reference(); ref.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8))); ref.SetTextThickness(MM(0.12))
    if c["fp"].split(":")[0] in ("Resistor_SMD", "Capacitor_SMD", "LED_SMD", "Inductor_SMD", "Diode_SMD", "TestPoint") or c["ref"].startswith("H"):
        ref.SetVisible(False)
    fps[c["ref"]] = fp
info = {c["ref"]: c for c in C}

# ------------------------------------------------------------------ exact placements
placed = set()
def done(ref): placed.add(ref)
for c in C:
    if not c["pcb"] or c["ref"] in existing or c["ref"].startswith(("C14", "L1", "C15", "C16", "U7", "C18", "C19", "J5", "J6", "L2", "C20", "J7", "J3")):
        if c["ref"] in existing: done(c["ref"])
        continue
    side, x, y, rot = c["pcb"]; fp = fps[c["ref"]]; r = c["ref"]
    if r == "J1":                                    # USB-C: the footprint's PCB-edge line (local y 3.1) on the bottom edge
        put(fp, "F", x, -36.0 + 3.1, 0)
    elif r == "SW1":                                 # side switch: mounting pads 0.5 mm inside the edge, plunger out over it
        mp = [p for p in fp.Pads() if p.GetNumber() == "MP"][0]
        y0 = -36.0 + 0.5 + 1.05 + mm(mp.GetSize().y) / 2
        put(fp, "F", x, y0, 0); print(f"SW1 plunger tip {y0 - 2.04 + 36.0:+.2f} mm from the bottom edge")
    elif r == "J2":                                  # 3.5 mm jack: nose 2.1 mm past the bottom edge
        put(fp, "F", x, -36.0 + 6.12, 90)
    elif r == "D10":                                 # flashlight LED: lens 1.8 mm past the edge, axis at x = 32
        put(fp, "F", x - 1.27, -37.8 + 6.57, 0)
    elif r == "J4":                                  # JST SM10B on the tab top, mouth up, mounting pads 0.5 mm inside the edge
        put(fp, "B", x, 20.0, 0)
        mp = [p for p in fp.Pads() if p.GetNumber() == "MP"][0]
        top = max(Bf(p.GetPosition())[1] + mm(p.GetSize().y) / 2 for p in fp.Pads() if p.GetNumber() == "MP")
        move_to(fp, 0, (28.5 - 0.5) - top)
    elif r == "U5":                                  # ESP32 module: antenna end (the long courtyard) toward -X
        def ant_left(f):
            cy = courtyard(f).centroid; return cy.x < x - 5
        orient(fp, "B", x, y, ant_left)
    else:
        put(fp, side, x, y, rot)
    done(r)
# XLR wire pads: a row along +X with pad 1 on the left, centred on (-20, -11.6)
j3 = fps["J3"]
orient(j3, "B", -20.0, -11.6, lambda f: pad1(f, "2")[0] > pad1(f, "1")[0] + 2)
px = sum(pad1(j3, str(k))[0] for k in range(1, 6)) / 5; py = pad1(j3, "1")[1]
move_to(j3, -20.0 - px, -11.6 - py); done("J3")

# ------------------------------------------------------------------ RF chain, hand-laid on B (50 ohm CPWG over the In2 ground)
def add_track(a, c_, layer, net, w=0.3, locked=True):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net)
    t.SetLocked(locked); b.Add(t); return t
def add_via(x, y, net, locked=True, d=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetDrill(MM(drill)); v.SetWidth(MM(d)); v.SetNet(net)
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLocked(locked); b.Add(v); return v
BC = pcbnew.B_Cu
def rf_route(pts, net):
    for a_, c_ in zip(pts, pts[1:]):
        if a_ != c_: add_track(a_, c_, BC, net, w=0.35)
u6 = fps["U6"]
p11, p17 = pad1(u6, "11"), pad1(u6, "17")
c6 = Bf(u6.GetPosition())
assert p11[0] < c6[0] - 4, f"LR2021 ANT_LF should face -X (toward the switch); it is at {p11}"
Y = p11[1]
vert_up = lambda f: pad1(f, "1")[1] > pad1(f, "2")[1] + 1.0 and abs(pad1(f, "1")[0] - pad1(f, "2")[0]) < 0.01
vert_dn = lambda f: pad1(f, "1")[1] < pad1(f, "2")[1] - 1.0 and abs(pad1(f, "1")[0] - pad1(f, "2")[0]) < 0.01
horiz_r = lambda f: pad1(f, "1")[0] > pad1(f, "2")[0] + 1.0
def place_rf(ref, test, padn, x, y):
    fp = fps[ref]; orient(fp, "B", x, y, test); shift_pad(fp, padn, x, y); done(ref); return fp
c14 = place_rf("C14", vert_up, "1", p11[0] - 2.3, Y)
l1 = place_rf("L1", horiz_r, "1", pad1(c14, "1")[0] - 1.9, Y)
c15 = place_rf("C15", vert_up, "1", pad1(l1, "2")[0] - 1.9, Y)
c16 = place_rf("C16", horiz_r, "1", pad1(c15, "1")[0] - 1.9, Y)
u7 = fps["U7"]; orient(u7, "B", 0, 0, lambda f: pad1(f, "5")[0] > pad1(f, "1")[0] + 1)
shift_pad(u7, "5", pad1(c16, "2")[0] - 1.75, Y); done("U7")
rf1, rf2 = pad1(u7, "1"), pad1(u7, "3")
for pin, cref, jref, net_sw, net_ant in (("1", "C18", "J5", "RF_SW_1", "RF_ANT_A"), ("3", "C19", "J6", "RF_SW_2", "RF_ANT_B")):
    p = pad1(u7, pin); s = 1 if p[1] > Y else -1
    cx, cy = p[0] - 1.9, p[1] + s * 1.6
    cap = place_rf(cref, vert_up if s < 0 else vert_dn, "1", cx, cy)           # pad 1 toward the switch row
    cp2 = pad1(cap, "2")
    j = fps[jref]
    orient(j, "B", 0, 0, lambda f, s=s: (pad1(f, "1")[1] - pads(f, "2")[0][1]) * s < -0.3 and abs(pads(f, "2")[0][1] - pads(f, "2")[1][1]) < 0.01)
    shift_pad(j, "1", cp2[0], cp2[1] + s * 2.0); done(jref)
    rf_route([p, (cx, p[1]), (cx, cy)], nets["/" + net_sw])
    rf_route([cp2, pad1(j, "1")], nets["/" + net_ant])
rf_route([p11, pad1(c14, "1"), pad1(l1, "1")], nets["/RF_LF"])
rf_route([pad1(l1, "2"), pad1(c15, "1"), pad1(c16, "1")], nets["/RF_LF_M"])
rf_route([pad1(c16, "2"), pad1(u7, "5")], nets["/RF_SW_C"])
# 2.4 GHz footprint above the module's ANT_HF pad
up = 1 if p17[1] > c6[1] else -1
assert abs(p17[1] - c6[1]) > 4, "ANT_HF expected on the top or bottom side of the module"
l2 = place_rf("L2", vert_dn if up > 0 else vert_up, "1", p17[0], p17[1] + up * 2.35)
# then left along the module's top edge (the board edge is too close above): shunt C20, then the U.FL facing +X
c20 = place_rf("C20", vert_up if up > 0 else vert_dn, "1", pad1(l2, "2")[0] - 1.9, pad1(l2, "2")[1])
j7 = fps["J7"]; orient(j7, "B", 0, 0, lambda f: pad1(f, "1")[0] > pads(f, "2")[0][0] + 0.3 and abs(pads(f, "2")[0][0] - pads(f, "2")[1][0]) < 0.01)
shift_pad(j7, "1", pad1(c20, "1")[0] - 1.9, pad1(l2, "2")[1]); done("J7")
rf_route([p17, pad1(l2, "1")], nets["/RF_HF"])
rf_route([pad1(l2, "2"), pad1(c20, "1"), pad1(j7, "1")], nets["/RF_HF_M"])
# the module's four ground pads underneath: a via in each (they can't fan out from under the module)
for p in fps["U6"].Pads():
    if p.GetNumber() == "12" and math.dist(Bf(p.GetPosition()), c6) < 3.5:
        add_via(*Bf(p.GetPosition()), nets["GND"])

# ------------------------------------------------------------------ automatic placement of the small parts
HOLES = [Bf(fps[h].GetPosition()) for h in ("H1", "H2", "H3", "H4", "H5")]
KEEP = unary_union([sbox(-50, -14.3, -39.5, 14.5)] + [Point(h).buffer(3.2) for h in HOLES])
ANT = sbox(-50, -14.3, -39.5, 14.5).buffer(0.25, join_style=2)    # antenna keep-out (no copper), with a margin
INNER = EDGE.buffer(-0.6)
side_obst = {"F": [], "B": []}
ESC_RING = {"U8": 1.5, "U4": 1.0, "U11": 1.0}                                   # fine-pitch parts keep a free ring for their signal escapes
def add_obstacle(fp):
    s = "B" if fp.IsFlipped() else "F"; side_obst[s].append(courtyard(fp).buffer(ESC_RING.get(fp.GetReference(), 0.0), join_style=2))
    o = "F" if s == "B" else "B"; oL = pcbnew.F_Cu if o == "F" else pcbnew.B_Cu
    for pad in fp.Pads():
        if pad.HasHole():                                    # through-hole parts block the other side too
            x_, y_ = Bf(pad.GetPosition()); side_obst[o].append(Point(x_, y_).buffer(mm(pad.GetSize().x) / 2 + 0.3))
        elif pad.IsOnLayer(oL):                              # copper on the other side (the exposed pad of a thermal-via footprint)
            side_obst[o].append(polyset_to_shapely(pad.GetEffectivePolygon()).buffer(0.3))
for r in placed:
    if r != "REF**": add_obstacle(fps[r])
for num in ("A4", "A9"):                                  # USB VBUS escapes: track and via straight behind each VBUS pad
    p = [q for q in fps["J1"].Pads() if q.GetNumber() == num][0]; x_, y_ = Bf(p.GetPosition()); top = y_ + mm(p.GetBoundingBox().GetHeight()) / 2
    side_obst["F"].append(sbox(x_ - 0.45, top, x_ + 0.45, top + 1.3)); side_obst["B"].append(Point(x_, top + 0.85).buffer(0.55))
sp = [Bf(q.GetPosition()) + (mm(q.GetBoundingBox().GetHeight()) / 2,) for q in fps["J1"].Pads() if q.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
top = max(y_ + h_ for _, y_, h_ in sp)                     # USB-C: keep the strip behind the signal pads free for their tracks
side_obst["F"].append(sbox(min(x_ for x_, _, _ in sp) - 0.3, top, max(x_ for x_, _, _ in sp) + 0.3, top + 2.4))
shapes = {}
def local_shapes(fp, side):
    key = (fp.GetFPIDAsString(), side)
    if key not in shapes:
        out = {}
        for r in (0, 90):
            put(fp, side, 0, 0, r); out[r] = courtyard(fp)
        shapes[key] = out
    return shapes[key]
GAP = 0.35                                               # space between courtyards, for routing channels
def try_place(ref, side, tx, ty, rmax=14.0):
    fp = fps[ref]; sh = local_shapes(fp, side)
    tree = STRtree(side_obst[side]) if side_obst[side] else None
    for rad in [0.0] + [0.5 * k for k in range(2, int(rmax / 0.5) + 1)]:
        n = 1 if rad == 0 else max(8, int(2 * math.pi * rad / 0.6))
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = round(tx + rad * math.cos(a), 2), round(ty + rad * math.sin(a), 2)
            for r in (0, 90):
                g = translate(sh[r], x, y)
                if not INNER.contains(g) or g.intersects(KEEP): continue
                if tree is not None and any(side_obst[side][i].distance(g) < GAP for i in tree.query(g.buffer(GAP))): continue
                put(fp, side, x, y, r); add_obstacle(fp); done(ref); return True
    return False
# the codec's support parts are placed later, next to the fan vias of the pins they serve (see below)
LATE = {"C27": "27", "C28": "32", "FB1": "31", "C22": "31", "C21": "31", "C29": "2", "C30": "1", "C37": "5", "C38": "4",
        "C23": "13", "C24": "14", "C26": "26", "C25": "26", "R27": "23", "R28": "25"}
pending = [c for c in C if c["ref"] not in placed and c["near"] and c["ref"] not in LATE]
failed = []
for _ in range(6):
    left = []
    for c in pending:
        aref, apad, side = c["near"]
        if aref not in placed: left.append(c); continue
        ax, ay = pad1(fps[aref], apad)
        if not try_place(c["ref"], side, ax, ay) and not try_place(c["ref"], "B" if side == "F" else "F", ax, ay, 20.0):
            failed.append(c["ref"])
    pending = left
    if not pending: break
print("auto-placed:", len([c for c in C if c["near"]]) - len(LATE) - len(failed) - len(pending), "failed:", failed, "unresolved:", [c["ref"] for c in pending])
missing = [c["ref"] for c in C if c["ref"] not in placed and c["ref"] not in LATE]
assert not missing, f"unplaced: {missing}"
def placement_check():
    # placement check: courtyard overlaps on each side, and through-holes under the other side's parts
    probs = []
    for s in ("F", "B"):
        fl = [f for f in b.GetFootprints() if f.GetReference() != "REF**" and f.IsFlipped() == (s == "B") and not f.GetReference().startswith("H")
              and (f.GetReference() not in LATE or f.GetReference() in placed)]
        gs = [courtyard(f) for f in fl]; tree = STRtree(gs)
        for i, g in enumerate(gs):
            for j in tree.query(g):
                if j > i and gs[j].intersection(g).area > 0.05: probs.append(f"{s}: {fl[i].GetReference()} overlaps {fl[j].GetReference()}")
        for f in b.GetFootprints():
            if f.IsFlipped() == (s == "B"): continue
            for pad in f.Pads():
                if not pad.HasHole() or mm(pad.GetDrillSize().x) <= 0.5: continue      # vias in exposed pads are fine under a body
                hp = Point(*Bf(pad.GetPosition())).buffer(mm(pad.GetSize().x) / 2)
                for k in tree.query(hp):
                    if gs[k].intersects(hp): probs.append(f"{s}: {fl[k].GetReference()} sits on a hole of {f.GetReference()}")
    # pad copper of different nets closer than 0.2 mm on either outer layer (any footprint, either side)
    for L in (pcbnew.F_Cu, pcbnew.B_Cu):
        pl = [(f.GetReference(), p.GetNumber(), p.GetNetname() or f"{f.GetReference()}.{p.GetNumber()}", polyset_to_shapely(p.GetEffectivePolygon()))
              for f in b.GetFootprints() for p in f.Pads() if p.IsOnLayer(L) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH
              and (f.GetReference() not in LATE or f.GetReference() in placed)]
        pt = STRtree([g for *_, g in pl])
        for i, (r1, n1, net1, g1) in enumerate(pl):
            for j in pt.query(g1.buffer(0.2)):
                r2, n2, net2, g2 = pl[j]
                if j > i and net1 != net2 and r1 != r2 and g1.distance(g2) < 0.2: probs.append(f"{'F' if L == pcbnew.F_Cu else 'B'}: pad {r1}.{n1} touches {r2}.{n2}")
    print("placement problems:", sorted(set(probs)) or "none")
    return probs
placement_check()

# board text, then save the placement
txt = pcbnew.PCB_TEXT(b); txt.SetText("OpenTheatreComms beltpack  main PCB  rev 0.1"); txt.SetLayer(pcbnew.B_SilkS)
txt.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0))); txt.SetTextThickness(MM(0.15)); txt.SetPosition(P(-28.0, -1.0)); txt.SetMirrored(True); b.Add(txt)
b.Save(os.path.join(OUT, "placed_nofanout.kicad_pcb"))

# ------------------------------------------------------------------ plane fanouts: GND to In2 (and the outer pours), +3V3 to In1
cu = Copper(b)
# ------------------------------------------------------------------ signal escapes: pins the router cannot reach on its own get a short
# locked track straight out of the pad and a via, so Freerouting starts from a via it can reach on either side
def side_of(fp, pad):
    x, y = Bf(pad.GetPosition()); cx, cy = Bf(fp.GetPosition())
    if fp.GetReference() == "J1": return (0.0, 1.0), x - cx                  # USB-C pads: into the board
    dx, dy = x - cx, y - cy
    if abs(dx) > abs(dy): return (1.0 if dx > 0 else -1.0, 0.0), dy * (1.0 if dx > 0 else -1.0)
    return (0.0, 1.0 if dy > 0 else -1.0), -dx * (1.0 if dy > 0 else -1.0)
def escape(fp, pad, w=0.2, dmin=0.7, dmax=3.4, fan=0):
    """fan = +1/-1 lets the via drift only toward +t/-t (a fan away from the middle of the row); 0 allows both."""
    L = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
    x, y = Bf(pad.GetPosition()); n, _ = side_of(fp, pad); t = (-n[1], n[0])
    bb = pad.GetBoundingBox(); half = (mm(bb.GetWidth()) if n[0] else mm(bb.GetHeight())) / 2
    a = (x + n[0] * (half + 0.25), y + n[1] * (half + 0.25))
    nn = pad.GetNetname(); cands = []
    lat = [0.25 * k for k in range(0, 11)]
    lat = [0.0] + [v * sg for v in lat[1:] for sg in ((1, -1) if fan == 0 else (fan,))]
    for k in range(int((dmax - dmin) / 0.15) + 1):
        d = dmin + 0.15 * k
        for sl in lat: cands.append((d + abs(sl) * 0.6, d, sl))
    for _, d, sl in sorted(cands):
        vx, vy = x + n[0] * (half + d) + t[0] * sl, y + n[1] * (half + d) + t[1] * sl
        if Point(vx, vy).buffer(0.3).intersects(ANT) or not cu.via_ok(vx, vy, nn): continue
        pts = [(x, y), a, (vx, vy)]
        if LineString(pts).buffer(w / 2).intersects(ANT): continue
        if not cu.clear(LineString(pts).buffer(w / 2), nn, [L], 0.2, pads_any_net=False): continue
        items = [add_via(vx, vy, pad.GetNet())] + [add_track(p_, q_, L, pad.GetNet(), w=w) for p_, q_ in zip(pts, pts[1:])]
        for it in items: cu.add_track(it)
        return True
    return False
esc_fail = []; ESC_DONE = set()
def run_escapes(lst):
    for e in lst:
        fp = fps[e[0]]; pad = [p for p in fp.Pads() if p.GetNumber() == e[1]][0]
        if not escape(fp, pad, w=e[2], fan=e[3]): esc_fail.append(f"{e[0]}.{e[1]}")
        else: ESC_DONE.add((e[0], e[1]))
run_escapes([("J1", "A4", 0.4, 0), ("J1", "A9", 0.4, 0)])               # VBUS pads first: their spots are reserved in placement
BODY = {}
def body(fp):
    """The part's own body (fab outline), which fanout vias and tracks stay out of."""
    r = fp.GetReference()
    if r not in BODY:
        xs, ys = [], []
        for g in fp.GraphicalItems():
            if g.GetClass() == "MGRAPHIC" and g.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab):
                bb = g.GetBoundingBox(); x0, y1 = Bf(bb.GetOrigin()); x1, y0 = Bf(bb.GetEnd()); xs += [x0, x1]; ys += [y0, y1]
        BODY[r] = sbox(min(xs), min(ys), max(xs), max(ys)) if xs else Point(0, 0).buffer(0.01)
    return BODY[r]
def via_path_ok(x, y, vx, vy, net, layer, fp=None, w=0.3):
    if Point(vx, vy).buffer(0.3).intersects(ANT) or LineString([(x, y), (vx, vy)]).buffer(w / 2).intersects(ANT) or not cu.via_ok(vx, vy, net): return False
    if fp is not None:
        bd = body(fp)
        if bd.area > 1.0 and (bd.buffer(0.25).contains(Point(vx, vy)) or not LineString([(x, y), (vx, vy)]).intersection(bd.buffer(-0.45)).is_empty): return False
    return cu.clear(LineString([(x, y), (vx, vy)]).buffer(w / 2), net, [layer], 0.2, pads_any_net=False)
def fanout(pad, layer, net, rmax=1.2, fp=None):
    """A via on the pad's net within rmax of the pad edge, joined by a straight track that clears every other net."""
    x, y = Bf(pad.GetPosition()); bb = pad.GetBoundingBox(); sx, sy = mm(bb.GetWidth()) / 2, mm(bb.GetHeight()) / 2
    nn = net.GetNetname(); cands = []
    w = 0.2 if min(mm(pad.GetSize().x), mm(pad.GetSize().y)) < 0.5 else 0.3
    for k in range(-int((sx + rmax + 0.3) / 0.2), int((sx + rmax + 0.3) / 0.2) + 1):
        for j in range(-int((sy + rmax + 0.3) / 0.2), int((sy + rmax + 0.3) / 0.2) + 1):
            vx, vy = x + k * 0.2, y + j * 0.2
            ex, ey = max(abs(vx - x) - sx, 0), max(abs(vy - y) - sy, 0)
            dd = math.hypot(ex, ey)
            if 0.3 <= dd <= rmax: cands.append((dd, vx, vy))
    for dd, vx, vy in sorted(cands):
        if via_path_ok(x, y, vx, vy, nn, layer, fp, w):
            v = add_via(vx, vy, net); t_ = add_track((x, y), (vx, vy), layer, net, w=w); cu.add_track(v); cu.add_track(t_); return True
    return False
def to_same_net_pad(pad, layer, net, fp, connected):
    """Join the pad to the exposed pad, or to an already connected neighbour, of the same net in the same footprint."""
    x, y = Bf(pad.GetPosition()); nn = net.GetNetname()
    others = [q for q in fp.Pads() if q.GetNetname() == nn and q is not pad and q.IsOnLayer(layer)]
    others.sort(key=lambda q: (0 if q.GetNumber() in ("33", "9", "41") else 1, math.dist(Bf(q.GetPosition()), (x, y))))
    for q in others:
        if q.GetNumber() not in ("33", "9", "41") and (fp.GetReference(), q.GetNumber()) not in connected: continue
        qx, qy = Bf(q.GetPosition())
        if math.dist((qx, qy), (x, y)) > (4.0 if q.GetNumber() in ("33", "9", "41") else 1.3): continue
        if q.GetNumber() in ("33", "9", "41"):                  # exposed pad: straight in to its nearest edge, not to its centre
            ep = polyset_to_shapely(q.GetEffectivePolygon()).buffer(-0.15)
            if not ep.is_empty:
                from shapely.ops import nearest_points
                qx, qy = nearest_points(ep, Point(x, y))[0].coords[0]
        g = LineString([(x, y), (qx, qy)]).buffer(0.1)
        if cu.clear(g, nn, [layer], 0.2, pads_any_net=False):
            t_ = add_track((x, y), (qx, qy), layer, net, w=0.2); cu.add_track(t_); return True
    return False
# codec, before the plane fanouts: every signal and +3V3 pin gets a via on a fan (its ground pins join the exposed pad)
u8 = fps["U8"]; rows = {}; FANNED = set()
for p in u8.Pads():
    if p.GetNetname() in ("GND", "") or p.GetNetname().startswith("unconnected"): continue
    n, u = side_of(u8, p); rows.setdefault(n, []).append((abs(u), u, p.GetNumber()))
def try_via(fp, pad, n, t, d, sl, w=0.2):
    L = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
    x, y = Bf(pad.GetPosition()); bb = pad.GetBoundingBox(); half = (mm(bb.GetWidth()) if n[0] else mm(bb.GetHeight())) / 2
    a = (x + n[0] * (half + 0.25), y + n[1] * (half + 0.25)); nn = pad.GetNetname()
    vx, vy = x + n[0] * (half + d) + t[0] * sl, y + n[1] * (half + d) + t[1] * sl
    if Point(vx, vy).buffer(0.3).intersects(ANT) or not cu.via_ok(vx, vy, nn): return False
    pts = [(x, y), a, (vx, vy)]
    if LineString(pts).buffer(w / 2).intersects(ANT): return False
    if not cu.clear(LineString(pts).buffer(w / 2), nn, [L], 0.2, pads_any_net=False): return False
    for it in [add_via(vx, vy, pad.GetNet())] + [add_track(p_, q_, L, pad.GetNet(), w=w) for p_, q_ in zip(pts, pts[1:])]: cu.add_track(it)
    return True
for n, row in rows.items():                       # a fan: vias 0.9 mm apart on a line 1.6 mm beyond the pad ends
    t = (-n[1], n[0]); row = sorted(row, key=lambda r: r[1]); k = len(row); um = sum(r[1] for r in row) / k
    order = sorted(range(k), key=lambda i: abs(row[i][1] - um))
    for i in order:
        _, u, num = row[i]; pad = [p for p in u8.Pads() if p.GetNumber() == num][0]
        v = um + (i - (k - 1) / 2) * 0.9
        ok = any(try_via(u8, pad, n, t, d, v - u + dv) for d in (1.6, 1.9, 1.3, 2.2, 2.5) for dv in (0, 0.15, -0.15, 0.3, -0.3))
        if not ok: run_escapes([("U8", num, 0.2, (1 if u > um else -1))])
        FANNED.add(num)
run_escapes([("U4", "7", 0.2, 0), ("U4", "8", 0.2, -1), ("U4", "5", 0.2, 1)])
run_escapes([("U11", "10", 0.2, 0), ("U11", "11", 0.2, -1), ("U11", "9", 0.2, 1), ("U11", "6", 0.2, 0), ("U11", "4", 0.2, 0)])  # accelerometer (0.5 mm LGA; its middle GND pin first)

# codec support parts: each one next to the fan via of the codec pin it serves, front side first (the front is free over
# the codec), so VREF, MICBIAS, the analog supply and the mic coupling all stay within a couple of millimetres of their pins
for t_ in b.GetTracks():
    if t_.GetClass() == "PCB_VIA":
        g_ = Point(*Bf(t_.GetPosition())).buffer(0.5); side_obst["F"].append(g_); side_obst["B"].append(g_)
    elif t_.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
        side_obst["F" if t_.GetLayer() == pcbnew.F_Cu else "B"].append(LineString([Bf(t_.GetStart()), Bf(t_.GetEnd())]).buffer(mm(t_.GetWidth()) / 2 + 0.2))
late_where = {}
for ref, pin in LATE.items():
    pad = [p for p in u8.Pads() if p.GetNumber() == pin][0]; px_, py_ = Bf(pad.GetPosition()); nn_ = pad.GetNetname()
    vias_ = [Bf(t_.GetPosition()) for t_ in b.GetTracks() if t_.GetClass() == "PCB_VIA" and t_.GetNetname() == nn_]
    ax_, ay_ = min(vias_, key=lambda v: math.dist(v, (px_, py_))) if vias_ else (px_, py_)
    ok_ = try_place(ref, "F", ax_, ay_, 6.0) or try_place(ref, "B", ax_, ay_, 6.0) or try_place(ref, "F", ax_, ay_, 14.0)
    late_where[ref] = (("F" if not fps[ref].IsFlipped() else "B") if ok_ else "FAILED", round(math.dist(Bf(fps[ref].GetPosition()), (ax_, ay_)), 1))
print("codec support parts (side, mm from their via):", late_where)
assert all(v[0] != "FAILED" for v in late_where.values())
placement_check()
cu = Copper(b)                                            # the new parts' pads into the copper model
skipped, connected = [], set()
todo = []
for fp in b.GetFootprints():
    L = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or pad.GetNetname() not in ("GND", "+3V3"): continue
        if fp.GetReference() == "U5" and pad.GetNumber() == "41": continue      # ESP32 ground pad: its own via array
        if pad.GetNumber() == "33" and fp.GetReference() == "U8": continue       # codec exposed pad: footprint thermal vias
        if fp.GetReference() == "U8" and pad.GetNumber() in FANNED: continue      # codec +3V3 pins: on the fan
        if (fp.GetReference(), pad.GetNumber()) in ESC_DONE: continue            # already has its own via
        if fp.GetReference() == "U6" and math.dist(Bf(pad.GetPosition()), Bf(fp.GetPosition())) < 3.5: continue   # module ground pads: via in pad
        if pad.GetNumber() == "9" and fp.GetReference() == "U2": continue        # charger exposed pad: footprint thermal vias
        todo.append((fp, pad, L))
todo.sort(key=lambda t: 0 if t[0].GetReference().startswith("U") else 1)      # chips first: their pins have the fewest ways out
for rmax in (1.2, 2.2, 3.5):
    left = []
    for fp, pad, L in todo:
        if to_same_net_pad(pad, L, pad.GetNet(), fp, connected): connected.add((fp.GetReference(), pad.GetNumber())); continue
        if fanout(pad, L, pad.GetNet(), rmax, fp): connected.add((fp.GetReference(), pad.GetNumber()))
        else: left.append((fp, pad, L))
    todo = left
def to_nearby(pad, layer, net):
    """Last resort: a straight track to the nearest connected same-net pad or via (any footprint) within 3.5 mm."""
    x, y = Bf(pad.GetPosition()); nn = net.GetNetname(); cands = []
    for f2 in b.GetFootprints():
        for q in f2.Pads():
            if q.GetNetname() == nn and q is not pad and q.IsOnLayer(layer) and ((f2.GetReference(), q.GetNumber()) in connected or q.HasHole()):
                cands.append(Bf(q.GetPosition()))
    cands += [Bf(t_.GetPosition()) for t_ in b.GetTracks() if t_.GetClass() == "PCB_VIA" and t_.GetNetname() == nn]
    for q in sorted(cands, key=lambda q: math.dist(q, (x, y))):
        if math.dist(q, (x, y)) > 3.5: break
        if cu.clear(LineString([(x, y), q]).buffer(0.1), nn, [layer], 0.2, pads_any_net=False):
            t_ = add_track((x, y), q, layer, net, w=0.2); cu.add_track(t_); return True
    return False
todo = [(fp, pad, L) for fp, pad, L in todo if not to_nearby(pad, L, pad.GetNet())]
skipped = [f"{fp.GetReference()}.{pad.GetNumber()}" for fp, pad, L in todo]
if os.environ.get("FANDEBUG"):
    from collections import Counter
    for (x_, y_) in ((10.8, -3.75), (8.25, -1.2)):
        g_ = Point(x_, y_).buffer(0.3)
        print("  probe", (x_, y_), cu.via_ok(x_, y_, "GND"), [h.centroid.coords[0] for h in cu.holes if h.distance(Point(x_, y_)) < 3 and h.distance(g_) < 0.25][:4],
              cu.clear(g_, "GND", (pcbnew.F_Cu, pcbnew.B_Cu), 0.2), cu.edge.buffer(-0.5).contains(g_))
        for L in (pcbnew.F_Cu, pcbnew.B_Cu):
            print("     ", L, [(n, k) for n, gg, k in [cu.base[L][i] for i in cu.tree[L].query(g_.buffer(0.2))] + cu.extra[L] if gg.distance(g_) < 0.2][:5])
    for fp, pad, L in todo:
        x, y = Bf(pad.GetPosition()); why = Counter(); nn = pad.GetNetname()
        for k in range(-18, 19):
            for j in range(-18, 19):
                vx, vy = x + k * 0.2, y + j * 0.2
                if math.hypot(vx - x, vy - y) < 0.6: continue
                if Point(vx, vy).within(KEEP.buffer(-2.8)): why["keep"] += 1; continue
                if not cu.via_ok(vx, vy, nn): why["via"] += 1; continue
                bd = body(fp)
                if bd.area > 1.0 and (bd.buffer(0.25).contains(Point(vx, vy)) or not LineString([(x, y), (vx, vy)]).intersection(bd.buffer(-0.45)).is_empty): why["body"] += 1; continue
                if not cu.clear(LineString([(x, y), (vx, vy)]).buffer(0.15), nn, [L], 0.2, pads_any_net=False): why["path"] += 1; continue
                why["OK"] += 1
        print("  ", fp.GetReference(), pad.GetNumber(), (round(x, 2), round(y, 2)), dict(why))
print("fanout skipped:", skipped)
run_escapes([("U1", "5", 0.3, 0), ("Q2", "3", 0.2, 0), ("R28", "2", 0.2, 0)])
print("escape failures:", esc_fail or "none")

b.Save(os.path.join(OUT, "placed.kicad_pcb"))
dsn = os.path.join(OUT, "main_pcb.dsn")
print("DSN", pcbnew.ExportSpecctraDSN(b, dsn))
if stage == "place": sys.exit(0)

# ------------------------------------------------------------------ autoroute: GND and +3V3 belong to the planes, so hide them
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
for netname in ("GND",):                      # a single pin each: nothing for the router to connect
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
ses = os.path.join(OUT, "main_pcb.ses")
if stage != "import":
    if os.path.exists(ses): os.remove(ses)
    log = subprocess.run(["xvfb-run", "-a", "java", "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", "40"],
                         capture_output=True, text=True, timeout=5400, cwd=OUT)
    open(os.path.join(OUT, "freerouting.log"), "w").write(log.stdout + log.stderr)
    print("freerouting rc", log.returncode)

# ------------------------------------------------------------------ import: keep the locked pre-routes and fanouts
for t in list(b.GetTracks()):
    if not t.IsLocked(): b.Remove(t)
locked_geo = [(t.GetNetname(), t.GetLayer(), LineString([Bf(t.GetStart()), Bf(t.GetEnd())])) for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
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
            add_track(a_, c_, layer, net, w=width, locked=False); nt += 1
    for v in find(n, "via"):
        add_via(*sxy(v[2], v[3]), net, locked=False); nv += 1
print("imported", nt, "track segments,", nv, "vias")
incomplete = {n: [sorted(x) for x in g] for n, g in net_islands(b, skip=("", "GND")).items() if len(g) > 1}
print("incomplete nets after routing:", incomplete or "none")
b.Save(os.path.join(OUT, "routed.kicad_pcb"))
