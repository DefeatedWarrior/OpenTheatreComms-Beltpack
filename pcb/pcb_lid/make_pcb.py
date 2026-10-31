"""Build the pack lid PCB from design.py on the starter board (outline, guides, enclosure reference): footprints at their
design positions, short front-side tracks from each wire hole to its contact pad, silk labels, then DRC and save into
kicad_proj/pack_lid_pcb/."""
import os, sys, json, shutil
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from design import C
from pcbgeom import P, Bf, MM
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "pack_lid_pcb"))
OUT = os.path.join(HERE, "out"); TPL = os.path.join(HERE, "template")
FPLIB = "/usr/share/kicad/footprints"

b = pcbnew.LoadBoard(os.path.join(TPL, "pack_lid_pcb.kicad_pcb"))
info = json.load(open(os.path.join(OUT, "pack_lid_pcb_schinfo.json")))["symbols"]
nets = {}
for n in sorted({n for c in C for n in c["pins"].values() if n}):
    ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
fps = {}
for c in C:
    lib, name = c["fp"].split(":")
    fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name)); fp.SetReference(c["ref"]); fp.SetValue(c["value"])
    fp.SetPath(pcbnew.KIID_PATH("/" + info[c["ref"]]))
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)   # board features, nothing to buy
    side, x, y, rot = c["pcb"]
    b.Add(fp); fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(rot)
    for pad in fp.Pads(): pad.SetNet(nets[c["pins"][pad.GetNumber()]])
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    for g in list(fp.GraphicalItems()):                 # the library silk rings would crowd the board; labels instead
        if g.GetLayer() == pcbnew.F_SilkS: g.SetLayer(pcbnew.F_Fab)
        elif g.GetLayer() == pcbnew.F_CrtYd and c["lib_id"] == "Connector:TestPoint": g.SetLayer(pcbnew.Dwgs_User)   # contact pads: copper, not parts
    fps[c["ref"]] = fp
def track(a, c_, net, w):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c_)); t.SetLayer(pcbnew.F_Cu); t.SetWidth(MM(w)); t.SetNet(nets[net]); b.Add(t)
for wire_ref, pad_ref, net, w in (("J4", "J1", "BAT+", 1.0), ("J5", "J2", "NTC", 0.4), ("J6", "J3", "BAT-", 1.0)):
    track(Bf(fps[wire_ref].GetPosition()), Bf(fps[pad_ref].GetPosition()), net, w)
def text(s, x, y, layer, size=0.9, mirror=False):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetLayer(layer); t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * 0.15)); t.SetPosition(P(x, y)); t.SetMirrored(mirror); b.Add(t)
for x, s in ((6.0, "+"), (12.0, "T"), (18.0, "-")): text(s, x, -12.3, pcbnew.F_SilkS, 1.2)
for x, s in ((2.2, "+"), (9.0, "T"), (21.8, "-")): text(s, x, -17.6, pcbnew.F_SilkS, 0.9)
text("OTC pack lid rev 0.1", 12.0, -12.2, pcbnew.B_SilkS, 0.9, True)
for x, s in ((2.2, "RED+"), (9.0, "NTC"), (21.8, "BLK-")): text(s, x, -17.6, pcbnew.B_SilkS, 0.8, True)

os.makedirs(PROJ, exist_ok=True)
pcb_out = os.path.join(PROJ, "pack_lid_pcb.kicad_pcb")
b.Save(pcb_out)
shutil.copy(os.path.join(OUT, "pack_lid_pcb.kicad_sch"), os.path.join(PROJ, "pack_lid_pcb.kicad_sch"))
b2 = pcbnew.LoadBoard(pcb_out)
rpt = os.path.join(OUT, "drc.rpt")
pcbnew.WriteDRCReport(b2, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
print("".join(l for l in open(rpt) if l.startswith("** Found")))
