"""Test coupons cut from the rev B case: small prints that check fits before the full parts."""
import cadquery as cq, os, zipfile
from cadquery import Solid, Vector as V
B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "brep")
O = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coupons")
P = {n[:-5]: cq.Shape.importBrep(os.path.join(B, n)) for n in os.listdir(B) if n.endswith(".brep")}
def box(x0, x1, y0, y1, z0, z1): return Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
def piece(part, *bx): return P[part].intersect(box(*bx))
C = {
 "1_keys":   [("top_plate", piece("top_plate", -48, -16, 30, 42, -33, 1)), ("keycap_1", P["keycap_1"]), ("keycap_2", P["keycap_2"])],
 "2_buttons":[("front_shell", piece("front_shell", -27, 5, 7, 27, -10, 1)), ("front_back", P["front_back"]), ("front_function", P["front_function"])],
 "3_dial":   [("front_shell", piece("front_shell", 22, 54, 13, 37, -33, 1)), ("knob_right", P["knob_right"]), ("hub_right", P["hub_right"])],
 "4_pack_snap": [("back_shell", piece("back_shell", 0, 26, -37, -22, -40, 0)), ("battery_pack", piece("battery_pack", 0, 26, -37, -22, -40, 0))],
 "5_dock_pocket": [("front_shell", piece("front_shell", 12, 39, -39, -33, -25, -7))],
 "6_tpu_corner": [("front_shell", piece("front_shell", 28, 56, -39, -29, -40, 2)), ("back_shell", piece("back_shell", 28, 56, -39, -29, -40, 2)),
                  ("tpu_bottom", piece("tpu_bottom", 28, 56, -42, -29, -40, 3))],
}
files = []
for name, parts in C.items():
    for pn, s in parts:
        f = os.path.join(O, f"{name}__{pn}.stl"); cq.exporters.export(cq.Workplane().add(s), f, tolerance=0.03, angularTolerance=0.1)
        bb = s.BoundingBox(); files.append(f)
        print(f"{name:14s} {pn:15s} {bb.xlen:5.1f} x {bb.ylen:5.1f} x {bb.zlen:5.1f} mm  {s.Volume()/1000:5.1f} cm3  valid={s.isValid()}")
with zipfile.ZipFile(os.path.join(O, "beltpack_revB_test_coupons.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    for f in files: z.write(f, os.path.basename(f))
    z.write(os.path.join(O, "README.md"), "README.md")
