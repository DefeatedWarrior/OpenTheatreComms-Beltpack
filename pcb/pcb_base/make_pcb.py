"""Build the base station carrier PCB: footprints and nets from the schematic netlist, exact placement for the big parts,
an automatic placer for the small ones, a hand-laid RF chain, GND fanouts to the In1 plane, then Freerouting.

Stack: F.Cu parts + signals + GND pour, In1.Cu solid GND (the RF reference), In2.Cu signals + +3V3 pour, B.Cu signals + GND pour.
Every part is on the top side.

  python3 make_pcb.py           # everything
  python3 make_pcb.py place     # stop after placement and fanouts (out/placed.kicad_pcb, out/base_pcb.dsn)
  python3 make_pcb.py import    # re-import the last routing session instead of rerouting
"""
import os, sys, json, math, re, subprocess
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from design import C, XR, YR
from sexp import parse, find, first
from pcbgeom import P, Bf, mm, MM, Copper, board_outline, polyset_to_shapely, net_islands
from shapely.geometry import Point, LineString, box as sbox
from shapely.ops import unary_union, nearest_points
from shapely.affinity import translate
from shapely.strtree import STRtree

NAME = "base_pcb"
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", NAME))
TPL, OUT = os.path.join(HERE, "template"), os.path.join(HERE, "out")
FREEROUTING = "/home/claude/tools/freerouting-1.9.0.jar"
FPLIB = "/usr/share/kicad/footprints"; LOCAL_FP = os.path.join(HERE, "lib", "OpenTheatreComms.pretty")
stage = sys.argv[1] if len(sys.argv) > 1 else "all"
os.makedirs(OUT, exist_ok=True); os.makedirs(PROJ, exist_ok=True)
POWER_NETS = ("/VIN_RAW", "/VIN", "/BUCK_SW", "/BUCK_OUT", "+5V", "+3V3", "/LR_VDD", "/VDDA_COD")

# ------------------------------------------------------------------ project: net classes, library tables
pro = json.load(open(os.path.join(TPL, NAME + ".kicad_pro")))
base = pro["net_settings"]["classes"][0]
pro["net_settings"]["classes"] = [base, dict(base, name="Power", track_width=0.5, clearance=0.2), dict(base, name="RF", track_width=0.35, clearance=0.25)]
pro["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": p} for p in POWER_NETS + ("GND",)] + [{"netclass": "RF", "pattern": "/RF_*"}]
pro["meta"]["filename"] = NAME + ".kicad_pro"
json.dump(pro, open(os.path.join(PROJ, NAME + ".kicad_pro"), "w"), indent=2)
open(os.path.join(PROJ, "fp-lib-table"), "w").write('(fp_lib_table\n  (version 7)\n  (lib (name "OpenTheatreComms")(type "KiCad")(uri "${KIPRJMOD}/lib/OpenTheatreComms.pretty")(options "")(descr "Base station parts"))\n)\n')
open(os.path.join(PROJ, "sym-lib-table"), "w").write('(sym_lib_table\n  (version 7)\n  (lib (name "OpenTheatreComms")(type "KiCad")(uri "${KIPRJMOD}/lib/OpenTheatreComms.kicad_sym")(options "")(descr "Base station parts"))\n)\n')

# ------------------------------------------------------------------ netlist and symbol uuids
netl = parse(open(os.path.join(OUT, NAME + ".net")).read())[0]
padnet = {}
for n in find(first(netl, "nets"), "net"):
    name = str(first(n, "name")[1])
    for nd in find(n, "node"): padnet[(str(first(nd, "ref")[1]), str(first(nd, "pin")[1]))] = name
schinfo = json.load(open(os.path.join(OUT, NAME + "_schinfo.json")))

b = pcbnew.LoadBoard(os.path.join(TPL, NAME + ".kicad_pcb"))
b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER); b.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_MIXED)
nets = {}
for name in sorted(set(padnet.values())):
    ni = pcbnew.NETINFO_ITEM(b, name); b.Add(ni); nets[name] = ni
GND = nets["GND"]
EDGE = board_outline(b)
FC = pcbnew.F_Cu

def load_fp(fpid):
    lib, name = fpid.split(":")
    fp = pcbnew.FootprintLoad(LOCAL_FP if lib == "OpenTheatreComms" else os.path.join(FPLIB, lib + ".pretty"), name)
    if fp is None: raise SystemExit("footprint not found: " + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name)); return fp
def put(fp, side, x, y, rot):
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
def pad_centre(fp):
    """Centre of the part's pads (for switches and the encoder, whose footprint origin is pin 1)."""
    xs = [Bf(p.GetPosition()) for p in fp.Pads() if p.GetNumber() not in ("", "MP")]
    return sum(x for x, _ in xs) / len(xs), sum(y for _, y in xs) / len(xs)

fps = {}
for c in C:
    fp = load_fp(c["fp"]); b.Add(fp)
    fp.SetReference(c["ref"]); fp.SetValue(c["value"])
    fp.SetPath(pcbnew.KIID_PATH("/" + schinfo["symbols"][c["ref"]]))
    fp.SetProperty("Sheetfile", NAME + ".kicad_sch"); fp.SetProperty("Sheetname", "")
    if c["mpn"]: fp.SetProperty("MPN", c["mpn"])
    if c["dnp"]:
        fp.SetProperty("DNP", "yes"); fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    for pad in fp.Pads():
        nn = padnet.get((c["ref"], pad.GetNumber()))
        if nn: pad.SetNet(nets[nn])
    ref = fp.Reference(); ref.SetTextSize(pcbnew.VECTOR2I(MM(0.9), MM(0.9))); ref.SetTextThickness(MM(0.14))
    if c["fp"].split(":")[0] in ("Resistor_SMD", "Capacitor_SMD", "Inductor_SMD", "TestPoint") or c["ref"].startswith("H") or c["ref"].startswith("LED"):
        ref.SetVisible(False)
    for g in list(fp.GraphicalItems()):                  # net-less copper lines in a footprint (the Molex SMA ties its vias to its
        if g.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu): g.SetLayer(pcbnew.Dwgs_User)   # ground pads with them): the GND pour does that job
    fps[c["ref"]] = fp
info = {c["ref"]: c for c in C}

# ------------------------------------------------------------------ exact placements
placed = set()
def done(ref): placed.add(ref)
RF_HAND = ("C12", "L2", "C13", "C14", "U5", "C16", "C17", "L3", "C18", "J4")
for c in C:
    if not c["pcb"] or c["ref"] in RF_HAND: continue
    side, x, y, rot = c["pcb"]; fp = fps[c["ref"]]; r = c["ref"]
    if r == "J1":                                    # DC jack: mating face (local y = 12) on the rear edge
        put(fp, "F", x, YR - 12.0, 180)
    elif r in ("J2", "J3"):                          # edge SMA, body out over the rear edge
        put(fp, "F", x, YR - 2.155, 90)                      # Molex 73251-2120: its PCB-edge line (local x = 2.155) on the rear edge
    elif rot == "centre":                            # switches and the encoder: placed by their pad centre, pins left-right
        put(fp, "F", x, y, 0); cx, cy = pad_centre(fp); move_to(fp, x - cx, y - cy)
        if r == "ENC1":                              # encoder: centre on the shaft (between the mounting tabs)
            mp = pads(fp, "MP"); sx_ = (mp[0][0] + mp[1][0]) / 2; sy_ = (mp[0][1] + mp[1][1]) / 2; move_to(fp, x - sx_, y - sy_)
    else:
        put(fp, side, x, y, rot)
    done(r)

# ------------------------------------------------------------------ RF chain, hand-laid on F (50 ohm over the In1 ground)
def add_track(a, c_, layer, net, w=0.3, locked=True):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net)
    t.SetLocked(locked); b.Add(t); return t
def add_via(x, y, net, locked=True, d=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetDrill(MM(drill)); v.SetWidth(MM(d)); v.SetNet(net)
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLocked(locked); b.Add(v); return v
def rf_route(pts, net):
    for a_, c_ in zip(pts, pts[1:]):
        if math.dist(a_, c_) > 1e-3: add_track(a_, c_, FC, net, w=0.35)
u4 = fps["U4"]; c4 = Bf(u4.GetPosition())
p11, p17 = pad1(u4, "11"), pad1(u4, "17")
assert p11[1] > c4[1] + 4, f"LR2021 ANT_LF should face the rear (+Y); it is at {p11}"
X = p11[0]
vert = lambda f: abs(pad1(f, "1")[0] - pad1(f, "2")[0]) < 0.01 and pad1(f, "1")[1] < pad1(f, "2")[1] - 1.0     # pad 1 below pad 2
horiz_r = lambda f: pad1(f, "1")[0] > pad1(f, "2")[0] + 1.0                                                     # pad 1 right of pad 2
horiz_l = lambda f: pad1(f, "1")[0] < pad1(f, "2")[0] - 1.0
def place_rf(ref, test, padn, x, y):
    fp = fps[ref]; orient(fp, "F", x, y, test); shift_pad(fp, padn, x, y); done(ref); return fp
# up the line from ANT_LF: shunt C12 (to the side), series L2, shunt C13, DC block C14, then the switch
y_ = p11[1] + 2.0
l2 = place_rf("L2", vert, "1", X, y_ + 0.5)
c12 = place_rf("C12", horiz_r, "1", X - 1.7, pad1(l2, "1")[1])            # shunts: pad 1 beside the line, pad 2 (ground) further left
c13 = place_rf("C13", horiz_r, "1", X - 1.7, pad1(l2, "2")[1])
c14 = place_rf("C14", vert, "1", X, pad1(l2, "2")[1] + 1.9)
u5 = fps["U5"]
orient(u5, "F", 0, 0, lambda f: pad1(f, "5")[1] < pad1(f, "2")[1] - 1 and pad1(f, "1")[0] > pad1(f, "3")[0] + 1)   # RFC row down, RF1 right
shift_pad(u5, "5", X, pad1(c14, "2")[1] + 1.75); done("U5")
rf1, rf2 = pad1(u5, "1"), pad1(u5, "3")
for pin, cref, jref, net_sw, net_ant, s in (("1", "C16", "J2", "RF_SW_1", "RF_ANT_A", 1), ("3", "C17", "J3", "RF_SW_2", "RF_ANT_B", -1)):
    p = pad1(u5, pin)
    cap = place_rf(cref, horiz_l if s > 0 else horiz_r, "1", p[0] + s * 2.4, p[1] + 1.6)     # pad 1 toward the switch
    cp1, cp2 = pad1(cap, "1"), pad1(cap, "2")
    j = pad1(fps[jref], "1")
    rf_route([p, (p[0], cp1[1]), cp1], nets["/" + net_sw])
    rf_route([cp2, (j[0], cp2[1]), j], nets["/" + net_ant])
rf_route([p11, pad1(l2, "1")], nets["/RF_LF"]); rf_route([pad1(c12, "1"), pad1(l2, "1")], nets["/RF_LF"])
rf_route([pad1(l2, "2"), pad1(c14, "1")], nets["/RF_LF_M"]); rf_route([pad1(c13, "1"), pad1(l2, "2")], nets["/RF_LF_M"])
rf_route([pad1(c14, "2"), pad1(u5, "5")], nets["/RF_SW_C"])
# 2.4 GHz footprint off the module's ANT_HF pad (left side): series L3, shunt C18, U.FL
assert p17[0] < c4[0] - 4, f"ANT_HF expected on the module's left side; it is at {p17}"
l3 = place_rf("L3", horiz_r, "1", p17[0] - 2.3, p17[1])
c18 = place_rf("C18", lambda f: abs(pad1(f, "1")[0] - pad1(f, "2")[0]) < 0.01 and pad1(f, "1")[1] > pad1(f, "2")[1] + 1, "1", pad1(l3, "2")[0] - 1.9, p17[1])
j4 = fps["J4"]; orient(j4, "F", 0, 0, lambda f: pad1(f, "1")[0] > pads(f, "2")[0][0] + 0.3 and abs(pads(f, "2")[0][0] - pads(f, "2")[1][0]) < 0.01)
shift_pad(j4, "1", pad1(c18, "1")[0] - 1.9, p17[1]); done("J4")
rf_route([p17, pad1(l3, "1")], nets["/RF_HF"]); rf_route([pad1(l3, "2"), pad1(c18, "1"), pad1(j4, "1")], nets["/RF_HF_M"])
for p in u4.Pads():                                   # the module's ground pads underneath: a via in each
    if p.GetNumber() == "12" and math.dist(Bf(p.GetPosition()), c4) < 3.5: add_via(*Bf(p.GetPosition()), GND)

# ------------------------------------------------------------------ automatic placement of the small parts (top side)
HOLES = [Bf(fps[h].GetPosition()) for h in ("H1", "H2", "H3", "H4")]
OLED = sbox(-68.5, -45.0, -31.5, -13.5)               # under the OLED module (on an 8.5 mm socket): keep free
KEEP = unary_union([Point(h).buffer(4.0) for h in HOLES] + [OLED])
INNER = EDGE.buffer(-0.8)
obst = []
ESC_RING = {"U8": 1.5}
def add_obstacle(fp):
    obst.append(courtyard(fp).buffer(ESC_RING.get(fp.GetReference(), 0.0), join_style=2))
for r in placed:
    add_obstacle(fps[r])
for t_ in b.GetTracks():                               # the RF chain's tracks
    if t_.GetClass() == "PCB_TRACK": obst.append(LineString([Bf(t_.GetStart()), Bf(t_.GetEnd())]).buffer(0.5))
shapes = {}
def local_shapes(fp):
    key = fp.GetFPIDAsString()
    if key not in shapes:
        out = {}
        for r in (0, 90):
            put(fp, "F", 0, 0, r); out[r] = courtyard(fp)
        shapes[key] = out
    return shapes[key]
GAP = 0.4
def try_place(ref, tx, ty, rmax=16.0):
    fp = fps[ref]; sh = local_shapes(fp)
    tree = STRtree(obst)
    for rad in [0.0] + [0.5 * k for k in range(2, int(rmax / 0.5) + 1)]:
        n = 1 if rad == 0 else max(8, int(2 * math.pi * rad / 0.6))
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = round(tx + rad * math.cos(a), 2), round(ty + rad * math.sin(a), 2)
            for r in (0, 90):
                g = translate(sh[r], x, y)
                if not INNER.contains(g) or g.intersects(KEEP): continue
                if any(obst[i].distance(g) < GAP for i in tree.query(g.buffer(GAP))): continue
                put(fp, "F", x, y, r); add_obstacle(fp); done(ref); return True
    return False
# codec support parts go next to the fan vias of the pins they serve (below)
LATE = {"C44": "27", "C45": "32", "FB2": "31", "C39": "31", "C38": "31", "C46": "2", "C47": "1", "C48": "4", "C49": "5",
        "C40": "13", "C41": "14", "C43": "26", "C42": "26", "R17": "23", "R18": "25", "C50": "29", "C51": "30"}
pending = [c for c in C if c["ref"] not in placed and c["near"] and c["ref"] not in LATE]
failed = []
for _ in range(6):
    left = []
    for c in pending:
        aref, apad, _s = c["near"]
        if aref not in placed: left.append(c); continue
        ax, ay = pad1(fps[aref], apad)
        if not try_place(c["ref"], ax, ay): failed.append(c["ref"])
    pending = left
    if not pending: break
print("auto-placed:", len([c for c in C if c["near"]]) - len(LATE) - len(failed) - len(pending), "failed:", failed, "unresolved:", [c["ref"] for c in pending])
missing = [c["ref"] for c in C if c["ref"] not in placed and c["ref"] not in LATE]
assert not missing, f"unplaced: {missing}"
def placement_check():
    probs = []
    fl = [f for f in b.GetFootprints() if not f.GetReference().startswith("H") and (f.GetReference() not in LATE or f.GetReference() in placed)]
    gs = [courtyard(f) for f in fl]; tree = STRtree(gs)
    for i, g in enumerate(gs):
        for j in tree.query(g):
            if j > i and gs[j].intersection(g).area > 0.05: probs.append(f"{fl[i].GetReference()} overlaps {fl[j].GetReference()}")
        if not EDGE.buffer(0.01).contains(g) and fl[i].GetReference() not in ("J1", "J2", "J3"): probs.append(f"{fl[i].GetReference()} crosses the board edge")
    pl = [(f.GetReference(), p.GetNumber(), p.GetNetname() or f"{f.GetReference()}.{p.GetNumber()}", polyset_to_shapely(p.GetEffectivePolygon()))
          for f in fl for p in f.Pads() if p.IsOnLayer(FC) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH]
    pt = STRtree([g for *_, g in pl])
    for i, (r1, n1, net1, g1) in enumerate(pl):
        for j in pt.query(g1.buffer(0.2)):
            r2, n2, net2, g2 = pl[j]
            if j > i and net1 != net2 and r1 != r2 and g1.distance(g2) < 0.2: probs.append(f"pad {r1}.{n1} touches {r2}.{n2}")
    print("placement problems:", sorted(set(probs)) or "none")
    return probs
placement_check()

def silk(text, x, y, size=1.0, layer=pcbnew.F_SilkS, mirror=False):
    t = pcbnew.PCB_TEXT(b); t.SetText(text); t.SetLayer(layer); t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(size * 0.15))
    t.SetPosition(P(x, y)); t.SetMirrored(mirror); b.Add(t)
silk("OpenTheatreComms base station  carrier  rev 0.1", 0.0, -2.0, 1.2, pcbnew.B_SilkS, True)
silk("OLED module", -50.0, -30.0, 1.5)
for i, x in enumerate((10.0, 26.5, 43.0, 59.5)): silk(f"TALK {i + 1}", x, -43.3, 1.0)
silk("ANT A", 62.0, 36.5, 0.9); silk("ANT B", 44.0, 36.5, 0.9); silk("DC 7-24V", -8.0, 30.2, 0.9)
b.Save(os.path.join(OUT, "placed_nofanout.kicad_pcb"))

# ------------------------------------------------------------------ codec fan: every signal and +3V3 pin gets a via on a fan
cu = Copper(b)
def side_of(fp, pad):
    x, y = Bf(pad.GetPosition()); cx, cy = Bf(fp.GetPosition()); dx, dy = x - cx, y - cy
    if abs(dx) > abs(dy): return (1.0 if dx > 0 else -1.0, 0.0), dy * (1.0 if dx > 0 else -1.0)
    return (0.0, 1.0 if dy > 0 else -1.0), -dx * (1.0 if dy > 0 else -1.0)
def try_via(fp, pad, n, t, d, sl, w=0.2):
    x, y = Bf(pad.GetPosition()); bb = pad.GetBoundingBox(); half = (mm(bb.GetWidth()) if n[0] else mm(bb.GetHeight())) / 2
    a = (x + n[0] * (half + 0.25), y + n[1] * (half + 0.25)); nn = pad.GetNetname()
    vx, vy = x + n[0] * (half + d) + t[0] * sl, y + n[1] * (half + d) + t[1] * sl
    if not cu.via_ok(vx, vy, nn): return False
    pts = [(x, y), a, (vx, vy)]
    if not cu.clear(LineString(pts).buffer(w / 2), nn, [FC], 0.2, pads_any_net=False): return False
    for it in [add_via(vx, vy, pad.GetNet())] + [add_track(p_, q_, FC, pad.GetNet(), w=w) for p_, q_ in zip(pts, pts[1:])]: cu.add_track(it)
    return True
u8 = fps["U8"]; rows = {}; FANNED = set(); esc_fail = []
for p in u8.Pads():
    if p.GetNetname() in ("GND", "") or p.GetNetname().startswith("unconnected"): continue
    n, u = side_of(u8, p); rows.setdefault(n, []).append((abs(u), u, p.GetNumber()))
for n, row in rows.items():
    t = (-n[1], n[0]); row = sorted(row, key=lambda r: r[1]); k = len(row); um = sum(r[1] for r in row) / k
    for i in sorted(range(k), key=lambda i: abs(row[i][1] - um)):
        _, u, num = row[i]; pad = [p for p in u8.Pads() if p.GetNumber() == num][0]
        v = um + (i - (k - 1) / 2) * 0.9
        if any(try_via(u8, pad, n, t, d, v - u + dv) for d in (1.6, 1.9, 1.3, 2.2, 2.5, 2.8) for dv in (0, 0.15, -0.15, 0.3, -0.3, 0.45, -0.45)): FANNED.add(num)
        else: esc_fail.append(f"U8.{num}")
for t_ in b.GetTracks():                               # the fan's vias and tracks become obstacles for the support parts
    if t_.GetClass() == "PCB_VIA": obst.append(Point(*Bf(t_.GetPosition())).buffer(0.5))
    else: obst.append(LineString([Bf(t_.GetStart()), Bf(t_.GetEnd())]).buffer(mm(t_.GetWidth()) / 2 + 0.2))
late_where = {}
for ref, pin in LATE.items():
    pad = [p for p in u8.Pads() if p.GetNumber() == pin][0]; px_, py_ = Bf(pad.GetPosition()); nn_ = pad.GetNetname()
    vias_ = [Bf(t_.GetPosition()) for t_ in b.GetTracks() if t_.GetClass() == "PCB_VIA" and t_.GetNetname() == nn_]
    ax_, ay_ = min(vias_, key=lambda v: math.dist(v, (px_, py_))) if vias_ else (px_, py_)
    ok_ = try_place(ref, ax_, ay_, 8.0) or try_place(ref, ax_, ay_, 16.0)
    late_where[ref] = round(math.dist(Bf(fps[ref].GetPosition()), (ax_, ay_)), 1) if ok_ else "FAILED"
print("codec support parts (mm from their via):", late_where)
assert all(v != "FAILED" for v in late_where.values())
placement_check()

# ------------------------------------------------------------------ GND fanouts: a via to the In1 plane beside every SMD ground pad
cu = Copper(b)
BODY = {}
def body(fp):
    r = fp.GetReference()
    if r not in BODY:
        xs, ys = [], []
        for g in fp.GraphicalItems():
            if g.GetClass() == "MGRAPHIC" and g.GetLayer() == pcbnew.F_Fab:
                bb = g.GetBoundingBox(); x0, y1 = Bf(bb.GetOrigin()); x1, y0 = Bf(bb.GetEnd()); xs += [x0, x1]; ys += [y0, y1]
        BODY[r] = sbox(min(xs), min(ys), max(xs), max(ys)) if xs else Point(0, 0).buffer(0.01)
    return BODY[r]
def fanout(pad, net, rmax=1.2, fp=None):
    x, y = Bf(pad.GetPosition()); bb = pad.GetBoundingBox(); sx, sy = mm(bb.GetWidth()) / 2, mm(bb.GetHeight()) / 2
    nn = net.GetNetname(); cands = []
    w = 0.2 if min(mm(pad.GetSize().x), mm(pad.GetSize().y)) < 0.5 else 0.3
    for k in range(-int((sx + rmax + 0.3) / 0.2), int((sx + rmax + 0.3) / 0.2) + 1):
        for j in range(-int((sy + rmax + 0.3) / 0.2), int((sy + rmax + 0.3) / 0.2) + 1):
            vx, vy = x + k * 0.2, y + j * 0.2
            dd = math.hypot(max(abs(vx - x) - sx, 0), max(abs(vy - y) - sy, 0))
            if 0.3 <= dd <= rmax: cands.append((dd, vx, vy))
    for dd, vx, vy in sorted(cands):
        if not cu.via_ok(vx, vy, nn): continue
        if fp is not None:
            bd = body(fp)
            if bd.area > 1.0 and (bd.buffer(0.25).contains(Point(vx, vy)) or not LineString([(x, y), (vx, vy)]).intersection(bd.buffer(-0.45)).is_empty): continue
        if not cu.clear(LineString([(x, y), (vx, vy)]).buffer(w / 2), nn, [FC], 0.2, pads_any_net=False): continue
        v = add_via(vx, vy, net); t_ = add_track((x, y), (vx, vy), FC, net, w=w); cu.add_track(v); cu.add_track(t_); return True
    return False
def to_ep(pad, fp):
    """A ground pin of a chip with a ground exposed pad: straight in to the exposed pad's nearest edge."""
    ep = [q for q in fp.Pads() if q.GetNetname() == "GND" and q.GetNumber() in ("33", "41") ]
    if not ep: return False
    x, y = Bf(pad.GetPosition()); g = polyset_to_shapely(ep[0].GetEffectivePolygon()).buffer(-0.15)
    if g.is_empty or math.dist(g.centroid.coords[0], (x, y)) > 4.0: return False
    qx, qy = nearest_points(g, Point(x, y))[0].coords[0]
    if cu.clear(LineString([(x, y), (qx, qy)]).buffer(0.1), "GND", [FC], 0.2, pads_any_net=False):
        t_ = add_track((x, y), (qx, qy), FC, GND, w=0.2); cu.add_track(t_); return True
    return False
todo = []
for fp in b.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or pad.GetNetname() != "GND": continue
        if fp.GetReference() == "U8" and pad.GetNumber() == "33": continue                     # codec exposed pad: footprint thermal vias
        if fp.GetReference() == "U4" and math.dist(Bf(pad.GetPosition()), Bf(fp.GetPosition())) < 3.5: continue   # module ground pads: via in pad
        todo.append((fp, pad))
todo.sort(key=lambda t: 0 if t[0].GetReference().startswith("U") else 1)
skipped = []
for rmax in (1.2, 2.2, 3.5):
    left = []
    for fp, pad in todo:
        if fp.GetReference() == "U8" and to_ep(pad, fp): continue
        if not fanout(pad, pad.GetNet(), rmax, fp): left.append((fp, pad))
    todo = left
skipped = [f"{fp.GetReference()}.{pad.GetNumber()}" for fp, pad in todo]
print("GND fanout skipped:", skipped or "none", " codec fan failures:", esc_fail or "none")

b.Save(os.path.join(OUT, "placed.kicad_pcb"))
dsn = os.path.join(OUT, NAME + ".dsn")
print("DSN", pcbnew.ExportSpecctraDSN(b, dsn))
if stage == "place": sys.exit(0)

# ------------------------------------------------------------------ autoroute: GND is the In1 plane and the pours, so hide it
txt = open(dsn).read()
VIA = re.search(r'\(via "(Via\[[^"]*)"\)', txt).group(1)
m = re.search(r'\(class kicad_default "" (.*?)\n\s*\(circuit', txt, re.S)
special = set(POWER_NETS) | {"GND"}
toks = [t for t in re.findall(r'"[^"]*"|\S+', m.group(1)) if t not in special]
txt = txt[:m.start(1)] + " ".join(toks) + txt[m.end(1):]
extra = f'''    (class Power {" ".join(POWER_NETS)}
      (circuit (use_via {VIA}))
      (rule (width 500) (clearance 200.1))
    )
    (class Planes GND
      (circuit (use_via {VIA}))
      (rule (width 400) (clearance 200.1))
    )
'''
i = txt.index("  )\n  (wiring"); txt = txt[:i] + extra + txt[i:]
txt = re.sub(r'(\(net GND\s*\(pins )([^)]*)\)', lambda m_: m_.group(1) + m_.group(2).split()[0] + ")", txt, count=1)
txt = "\n".join(l for l in txt.split("\n") if "(net GND)" not in l)
kos = []
def ko(geom, layer):
    pts = " ".join(f"{(150 + x) * 1000:.1f} {-(105 - y) * 1000:.1f}" for x, y in list(geom.exterior.coords)[:-1])
    kos.append(f'    (keepout "" (polygon {layer} 0 {pts}))\n')
for tr in b.GetTracks():
    if tr.GetNetname() != "GND": continue
    if tr.GetClass() == "PCB_VIA":
        g = Point(*Bf(tr.GetPosition())).buffer(0.31, quad_segs=2); ko(g, "F.Cu"); ko(g, "B.Cu"); ko(g, "In2.Cu")
    else:
        g = LineString([Bf(tr.GetStart()), Bf(tr.GetEnd())]).buffer(0.16, quad_segs=2); ko(g, tr.GetLayerName())
ko(OLED.buffer(-0.5), "F.Cu")                                                   # (parts only; tracks are fine there, but keep F quiet under the module)
kos.pop()
i = txt.index(f'    (via "{VIA}")'); txt = txt[:i] + "".join(kos) + txt[i:]
txt = txt.replace("(layer In2.Cu\n      (type power)", "(layer In2.Cu\n      (type signal)", 1)
ars = """    (autoroute_settings
      (fanout off) (autoroute on) (postroute on) (vias on)
      (via_costs 50) (plane_via_costs 5) (start_ripup_costs 100) (start_pass_no 1)
      (layer_rule F.Cu (active on) (preferred_direction horizontal) (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 2.0))
      (layer_rule In1.Cu (active off) (preferred_direction vertical) (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 2.0))
      (layer_rule In2.Cu (active on) (preferred_direction horizontal) (preferred_direction_trace_costs 1.2) (against_preferred_direction_trace_costs 2.0))
      (layer_rule B.Cu (active on) (preferred_direction vertical) (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 2.0))
    )
"""
i = txt.index("\n    )\n", txt.index("    (layer B.Cu")) + 7; txt = txt[:i] + ars + txt[i:]
edge = EDGE.buffer(-0.32, join_style=2)
pts = " ".join(f"{(150 + x) * 1000:.1f} {-(105 - y) * 1000:.1f}" for x, y in list(edge.exterior.coords))
m2 = re.search(r"\(boundary\s*\(path pcb 0 [^)]*\)", txt)
txt = txt[:m2.start()] + f"(boundary\n      (path pcb 0 {pts})" + txt[m2.end():]
open(dsn, "w").write(txt)
ses = os.path.join(OUT, NAME + ".ses")
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
