import os, sys, json, itertools, time
import cadquery as cq
from cadquery import Shape
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
info = json.load(open(os.path.join(OUT, "parts_final.json")))
shapes = {p["name"]: Shape.importBrep(os.path.join(OUT, "brep", p["name"] + ".brep")) for p in info["parts"]}
# contacts that are meant to touch / mate
OK = {frozenset(x) for x in [("coax", "ufl"), ("coax", "antenna"), ("hub_left", "knob_left"), ("hub_right", "knob_right"),
      ("enc_left", "hub_left"), ("enc_right", "hub_right"), ("oled_glass", "oled_fpc"), ("coax_b", "ufl_b"), ("coax_b", "antenna_b")]}
t = time.time(); bad = []
names = list(shapes)
bbs = {n: shapes[n].BoundingBox() for n in names}
def ov(a, b, e=0.0):
    return not (a.xmax < b.xmin - e or b.xmax < a.xmin - e or a.ymax < b.ymin - e or b.ymax < a.ymin - e or a.zmax < b.zmin - e or b.zmax < a.zmin - e)
n = 0
for a, b in itertools.combinations(names, 2):
    if not ov(bbs[a], bbs[b]): continue
    n += 1
    try: v = shapes[a].intersect(shapes[b]).Volume()
    except Exception as e: v = -1
    if v > 0.05 and frozenset((a, b)) not in OK: bad.append((round(v, 2), a, b))
bad.sort(reverse=True)
print(n, "pairs checked in", round(time.time() - t, 1), "s")
for x in bad: print(x)
print("CLASHES:", len(bad))
