"""Debug plot of copper around points: python3 zoomplot.py board.kicad_pcb out.png B:x,y,half [F:x,y,half ...]"""
import sys, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbgeom import copper_items
from shapely.geometry import box
b = pcbnew.LoadBoard(sys.argv[1]); items = copper_items(b)
views = [(v.split(":")[0], *map(float, v.split(":")[1].split(","))) for v in sys.argv[3:]]
fig, axs = plt.subplots(1, len(views), figsize=(7 * len(views), 7))
axs = axs if len(views) > 1 else [axs]
for ax, (side, cx, cy, h) in zip(axs, views):
    L = pcbnew.B_Cu if side == "B" else pcbnew.F_Cu; win = box(cx - h, cy - h, cx + h, cy + h)
    for net, LL, g, kind, r in items:
        if LL != L or not g.intersects(win): continue
        g = g.intersection(win)
        for p in getattr(g, "geoms", [g]):
            if p.geom_type == "Polygon":
                ax.fill(*p.exterior.xy, color={"GND": "#2e7d32", "+3V3": "#c62828"}.get(net, "#1565c0" if net.startswith("/RF") else "#9e9e9e"), alpha=0.75)
        if kind == "pad" and h <= 6: ax.text(*g.centroid.coords[0], f"{r[0]}.{r[1]}", fontsize=6, ha="center")
    for fp in b.GetFootprints():
        if fp.IsFlipped() != (side == "B"): continue
        x, y = pcbnew.ToMM(fp.GetPosition().x) - 150, 105 - pcbnew.ToMM(fp.GetPosition().y)
        if abs(x - cx) < h and abs(y - cy) < h and h > 6: ax.text(x, y, fp.GetReference(), fontsize=7, ha="center", color="k")
    ax.set_xlim(cx - h, cx + h); ax.set_ylim(cy - h, cy + h); ax.set_aspect("equal"); ax.set_title(f"{side} side around ({cx}, {cy}), board frame")
plt.tight_layout(); plt.savefig(sys.argv[2], dpi=80)
