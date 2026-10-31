"""Build the dock contact board from design.py: a fresh 22 x 10 mm outline on the starter board's settings, footprints at their
design positions, each socket pin taken through a via to its contact pad, silk labels, then DRC and save into
kicad_proj/dock_contact_pcb/."""
import os, sys, json, shutil
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from design import C, W, H, PAD_Y
from pcbgeom import P, Bf, MM
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "dock_contact_pcb"))
OUT = os.path.join(HERE, "out"); TPL = os.path.join(HERE, "template")
FPLIB = "/usr/share/kicad/footprints"

b = pcbnew.LoadBoard(os.path.join(TPL, "dock_contact_pcb.kicad_pcb"))
for d in list(b.GetDrawings()): b.Delete(d)                      # the starter board's pack-lid outline and guides
for f in list(b.GetFootprints()): b.Delete(f)
R = 1.0                                                          # outline: rounded rectangle
def seg(a, c_):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*a)); s.SetEnd(P(*c_)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
def arc(c_, start, end):
    import math
    mx, my = (start[0] + end[0]) / 2 - c_[0], (start[1] + end[1]) / 2 - c_[1]; k = R / math.hypot(mx, my)
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(P(*start), P(c_[0] + mx * k, c_[1] + my * k), P(*end))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
seg((R, 0), (W - R, 0)); seg((W, R), (W, H - R)); seg((W - R, H), (R, H)); seg((0, H - R), (0, R))
arc((W - R, R), (W - R, 0), (W, R)); arc((W - R, H - R), (W, H - R), (W - R, H)); arc((R, H - R), (R, H), (0, H - R)); arc((R, R), (0, R), (R, 0))
ds = b.GetDesignSettings(); ds.SetAuxOrigin(P(0, 0)); ds.SetGridOrigin(P(0, 0))

info = json.load(open(os.path.join(OUT, "dock_contact_pcb_schinfo.json")))["symbols"]
nets = {}
for n in sorted({n for c in C for n in c["pins"].values() if n}):
    ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
fps = {}
for c in C:
    lib, name = c["fp"].split(":")
    fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name)); fp.SetReference(c["ref"]); fp.SetValue(c["value"])
    if c["ref"] in info: fp.SetPath(pcbnew.KIID_PATH("/" + info[c["ref"]]))
    if c["lib_id"] in ("Connector:TestPoint", "Mechanical:MountingHole"):
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    side, x, y, rot = c["pcb"]
    b.Add(fp); fp.SetPosition(P(x, y))
    if side == "B": fp.Flip(P(x, y), False)
    fp.SetOrientationDegrees(rot)
    for pad in fp.Pads():
        if c["pins"].get(pad.GetNumber()): pad.SetNet(nets[c["pins"][pad.GetNumber()]])
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    for g in list(fp.GraphicalItems()):
        if g.GetLayer() == pcbnew.F_SilkS: g.SetLayer(pcbnew.F_Fab)
        elif g.GetLayer() == pcbnew.F_CrtYd and c["lib_id"] == "Connector:TestPoint": g.SetLayer(pcbnew.Dwgs_User)
    fps[c["ref"]] = fp

def track(a, c_, net, w, L):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(L); t.SetWidth(MM(w)); t.SetNet(nets[net]); b.Add(t)
def via(p, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(*p)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(nets[net]); b.Add(v)
# socket pin -> straight up on B to a via (staggered), then on F to its contact pad
pins = {p.GetNumber(): Bf(p.GetPosition()) for p in fps["J5"].Pads() if p.GetNumber() != "MP"}
pads = {fps[r].Pads()[0].GetNetname(): Bf(fps[r].GetPosition()) for r in ("J1", "J2", "J3", "J4")}
net_of = {"1": "VBUS", "2": "D+", "3": "D-", "4": "GND"}
order = sorted(pins, key=lambda n: pins[n][0])                  # socket pins left to right
for i, n in enumerate(order):
    net = net_of[n]; px, py = pins[n]; tx, ty = pads[net]; w = 0.5 if net in ("VBUS", "GND") else 0.25
    inner = i in (1, 2)
    vy = py + 0.775 + 0.7                                        # every via in one row just above the socket pins
    track((px, py), (px, vy), net, w, pcbnew.B_Cu); via((px, vy), net)
    if inner:                                                    # straight up beside the pad, then into its side
        track((px, vy), (px, PAD_Y), net, w, pcbnew.F_Cu); track((px, PAD_Y), (tx, PAD_Y), net, w, pcbnew.F_Cu)
    else:                                                        # outer pins: across under the pads, then up into the pad
        track((px, vy), (tx, vy), net, w, pcbnew.F_Cu); track((tx, vy), (tx, ty), net, w, pcbnew.F_Cu)
def text(s, x, y, layer, size=0.8, mirror=False):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetLayer(layer); t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * 0.15)); t.SetPosition(P(x, y)); t.SetMirrored(mirror); b.Add(t)
for net, (x, y) in pads.items(): text(net.replace("VBUS", "V+"), x, 9.0, pcbnew.B_SilkS, 0.8, True)
# (no title silk: the board is too small for it beside the socket)

os.makedirs(PROJ, exist_ok=True)
pcb_out = os.path.join(PROJ, "dock_contact_pcb.kicad_pcb")
b.Save(pcb_out)
shutil.copy(os.path.join(TPL, "dock_contact_pcb.kicad_pro"), os.path.join(PROJ, "dock_contact_pcb.kicad_pro"))
shutil.copy(os.path.join(OUT, "dock_contact_pcb.kicad_sch"), os.path.join(PROJ, "dock_contact_pcb.kicad_sch"))
b2 = pcbnew.LoadBoard(pcb_out)
rpt = os.path.join(OUT, "drc.rpt")
pcbnew.WriteDRCReport(b2, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
print("".join(l for l in open(rpt) if l.startswith("** Found")))
