"""Check every main-board part (courtyard x height) against the enclosure solids of the CAD model.
Board frame equals CAD x/y; the front face is at CAD z = -8.2 (front parts grow toward +z), the back face at z = -9.8."""
import os, sys, json
import cadquery as cq
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS_Shape
from OCP.BRep import BRep_Builder
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import Bf, polyset_to_shapely
CAD = os.path.abspath(os.path.join(HERE, "..", "out", "brep"))
pcb = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "placed.kicad_pcb")
H = {"U5": 3.1, "U6": 2.5, "J1": 3.3, "J2": 5.0, "SW1": 3.5, "SW2": 2.5, "SW3": 2.5, "SW4": 2.5, "J4": 2.9, "J5": 2.5, "J6": 2.5, "J7": 2.5,
     "U2": 1.75, "U10": 1.2, "U11": 1.0, "U8": 0.9, "M1": 2.7, "D10": 3.6, "J3": 1.5, "D1": 2.3, "U4": 0.8}
SKIP = {"main_pcb", "top_pcb"} | {n for n in ("esp32s3", "lr2021", "codec", "charger", "ldo", "usb_c", "trrs", "sw_power", "lamp_led", "vib_motor",
        "jst_main", "ufl", "ufl_b", "rf_switch", "rf_match", "sw_back", "sw_function", "sw_menu", "pogo_1", "pogo_2", "pogo_3", "coax", "coax_b")}
def load(n):
    s = TopoDS_Shape(); BRepTools.Read_s(s, os.path.join(CAD, n + ".brep"), BRep_Builder()); return cq.Shape.cast(s)
solids = {f[:-5]: load(f[:-5]) for f in os.listdir(CAD) if f.endswith(".brep") and f[:-5] not in SKIP}
b = pcbnew.LoadBoard(pcb)
hits = []
for fp in b.GetFootprints():
    r = fp.GetReference()
    if r == "REF**" or r.startswith(("H", "J8", "J9", "J10", "TP")): continue
    back = fp.IsFlipped()
    xs, ys = [], []                                   # the body: fab outline, else courtyard
    for gi in fp.GraphicalItems():
        if gi.GetClass() == "MGRAPHIC" and gi.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab):
            bb = gi.GetBoundingBox(); a0 = Bf(bb.GetOrigin()); a1 = Bf(bb.GetEnd()); xs += [a0[0], a1[0]]; ys += [a0[1], a1[1]]
    if xs: x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    else:
        g = polyset_to_shapely(fp.GetCourtyard(pcbnew.B_CrtYd if back else pcbnew.F_CrtYd))
        if g.is_empty: continue
        x0, y0, x1, y1 = g.bounds
    h = H.get(r, 1.6 if "1206" in fp.GetFPIDAsString() else 1.0)
    z0 = -9.8 - h if back else -8.2
    bx = cq.Solid.makeBox(x1 - x0, y1 - y0, h, cq.Vector(x0, y0, z0))
    for n, s in solids.items():
        try: v = bx.intersect(s).Volume()
        except Exception: continue
        if v > 0.02: hits.append((r, n, round(v, 2)))
print("clashes:", hits or "none")
