import os, json, math
import cadquery as cq
from cadquery import Shape, Vector as V, Face
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, PathPatch
from matplotlib.path import Path as MPath
here = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(here, "out")
info = json.load(open(os.path.join(OUT, "parts_final.json")))
cols = {p["name"]: p for p in info["parts"]}
import importlib.util
def col(n):
    if n.startswith(("front_shell", "back_shell", "top_plate")): return "#3a4049"
    if n.startswith("tpu"): return "#e8ad1c"
    if n.startswith(("knob",)): return "#222326"
    if n.startswith("hub"): return "#7b8088"
    if "pcb" in n: return "#1f7a4d"
    if n.startswith("enc"): return "#c3c6cb"
    if n.startswith(("keycap", "front_")): return "#5b6370"
    if n.startswith("oled"): return "#111827"
    if n.startswith(("cell",)): return "#3558a6"
    if n.startswith("battery"): return "#4b5059"
    if n.startswith("belt"): return "#2a2d33"
    return "#9aa1ab"
def section(axis, val, names, title, fn, xlim, ylim, labels):
    fig, ax = plt.subplots(figsize=(9, 9 * abs(ylim[1] - ylim[0]) / abs(xlim[1] - xlim[0]) + 0.6), dpi=160)
    big = 400
    if axis == "x": pl = Face.makePlane(big, big, V(val, 0, -20), V(1, 0, 0))
    else: pl = Face.makePlane(big, big, V(0, 0, val), V(0, 0, 1))
    for n in names:
        s = Shape.importBrep(os.path.join(OUT, "brep", n + ".brep"))
        try: sec = s.intersect(pl)
        except Exception as e: continue
        for f in sec.Faces():
            ow = f.outerWire(); verts, codes = [], []
            for wi, w in enumerate([ow] + f.innerWires()):
                pts = []
                for e in w.Edges():
                    k = 24 if e.geomType() != "LINE" else 1
                    ps = [e.positionAt(t / k) for t in range(k + 1)]
                    if pts and (ps[0] - V(*pts[-1])).Length > (ps[-1] - V(*pts[-1])).Length: ps = ps[::-1]
                    pts += [(p.x, p.y, p.z) for p in ps]
                xy = [(p[2], p[1]) if axis == "x" else (p[0], p[1]) for p in pts]
                area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(xy, xy[1:] + xy[:1]))
                if (area > 0) == (wi > 0): xy = xy[::-1]          # outer CCW, holes CW
                verts += xy + [xy[0]]; codes += [MPath.MOVETO] + [MPath.LINETO] * (len(xy) - 1) + [MPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MPath(verts, codes), fc=col(n), ec="#111", lw=0.4, zorder=2))
    for (x, y, t) in labels: ax.annotate(t, (x, y), fontsize=7, color="#111", ha="left", zorder=5, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    ax.set_xlim(min(xlim), max(xlim)); ax.set_ylim(*ylim); ax.set_aspect("equal")
    ax.set_title(title, fontsize=10, loc="left"); ax.grid(alpha=0.15)
    ax.set_xlabel("z (mm, front = 0)" if axis == "x" else "x (mm)"); ax.set_ylabel("y (mm)")
    if axis == "x": ax.invert_xaxis()
    fig.savefig(os.path.join(OUT, "kicad", fn), bbox_inches="tight", facecolor="white"); plt.close(fig)
names = [p["name"] for p in info["parts"]]
section("x", 37.5, names, "Section through the right dial axis (x = 37.5), looking from the left", "section_dial.png", (5, -42), (8, 44),
        [(-30, 41, "TPU cap"), (-2, 34, "top PCB"), (-3, 27, "PEC12R body"), (-3, 21, "hub + tyre"), (-3, 15.0, "well floor")])
section("x", 0.0, names, "Section on the centre line (x = 0), looking from the left", "section_centre.png", (5, -42), (-44, 44),
        [(-14, 37.2, "OLED on foam"), (-14, 30.0, "top PCB"), (-9.6, 0, "main PCB"), (-15, -5, "104050 cell"), (-31, 0, "belt plate"),
         (3.5, 23.5, "Function"), (-19.5, 18.2, "pack hook"), (-9, -40.5, "power button")])
