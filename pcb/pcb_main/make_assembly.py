"""Hand-assembly drawings for the top PCB: one page per side (bottom drawn as seen from below), pads, part bodies,
large reference labels and the values placed on that side. Writes fab/assembly.pdf and fab/assembly_{top,bottom}.png."""
import os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import Bf, mm, polyset_to_shapely, board_outline
from design import C
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "main_pcb"))
b = pcbnew.LoadBoard(os.path.join(PROJ, "main_pcb.kicad_pcb"))
edge = board_outline(b)
info = {c["ref"]: c for c in C}
GROUP = {"SW": "#e8d9b0", "D": "#f3c6c6", "R": "#d6e4f0", "L": "#d6e4f0", "C": "#d9ecd6", "U": "#e3d5ee", "J": "#f1e0c8", "Q": "#efe3c8", "FB": "#e0e0e0", "TP": "#ffffff", "M": "#e0e0e0", "H": None}
def colour(ref):
    for k, v in GROUP.items():
        if ref.startswith(k): return v
    return "#eeeeee"

def page(top, pdf, png):
    fig, ax = plt.subplots(figsize=(16.5, 13.5)); ax.set_aspect("equal"); ax.axis("off")
    sgn = 1 if top else -1                                   # bottom view is mirrored left-right
    def T(xs): return [sgn * x for x in xs]
    for g in getattr(edge, "geoms", [edge]):
        x, y = g.exterior.xy; ax.fill(T(x), y, color="#fbfbf8", ec="#555", lw=1.2, zorder=0)
    rows = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref == "REF**": continue
        on_side = (not fp.IsFlipped()) == top
        L = pcbnew.F_Cu if top else pcbnew.B_Cu
        for pad in fp.Pads():
            if not pad.IsOnLayer(L): continue
            g = polyset_to_shapely(pad.GetEffectivePolygon())
            for p in getattr(g, "geoms", [g]):
                x, y = p.exterior.xy; ax.fill(T(x), y, color="#c9a447" if on_side else "#d8d8d8", lw=0, zorder=2)
        if ref.startswith("H"):
            x, y = Bf(fp.GetPosition()); ax.add_patch(plt.Circle((sgn * x, y), 1.1, color="#888", zorder=3)); continue
        if not on_side: continue
        cy = polyset_to_shapely(fp.GetCourtyard(pcbnew.F_CrtYd if top else pcbnew.B_CrtYd))
        x0, y0, x1, y1 = cy.bounds if not cy.is_empty else (0, 0, 0, 0)
        if not cy.is_empty:
            ax.add_patch(plt.Rectangle((min(sgn * x0, sgn * x1), y0), abs(x1 - x0), y1 - y0, fc=colour(ref), ec="#444", lw=0.6, alpha=0.55, zorder=1))
        cx, cyy = (x0 + x1) / 2, (y0 + y1) / 2
        small = (x1 - x0) * (y1 - y0) < 8
        dn = info.get(ref, {}).get("dnp")
        ax.text(sgn * cx, cyy, ref, ha="center", va="center", fontsize=6 if small else 10, weight="bold", color="#9a9a9a" if dn else "#1b1f24", zorder=5)
        c = info.get(ref)
        if c: rows.append((ref, ("DNP " if c["dnp"] else "") + c["value"], c["mpn"]))
        # polarity: mark LED cathodes and pin 1 of the multi-pin parts
        for num in ("1",) if (ref.startswith("D") or ref.startswith("U") or ref.startswith("J")) else ():
            p1 = [Bf(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
            if p1: ax.plot(sgn * p1[0][0], p1[0][1], marker="o", ms=4, color="#c0392b", zorder=6)
    ax.set_xlim(-49, 44); ax.set_ylim(-40, 31)
    side = "TOP (F) - seen from above" if top else "BOTTOM (B) - seen from below (mirrored)"
    ax.set_title(f"Beltpack main PCB rev 0.1 - assembly, {side}", fontsize=15, loc="left", pad=12)
    import re
    def key(r): m = re.match(r"([A-Z]+)(\d+)", r[0]); return (m.group(1), int(m.group(2)))
    rows.sort(key=key)
    lines, cur = [], ""
    for r, v, _ in rows:
        e = f"{r}: {v}"
        if len(cur) + len(e) + 3 > 170: lines.append(cur); cur = ""
        cur = (cur + "   " + e) if cur else e
    lines.append(cur)
    fig.text(0.04, 0.05, "\n".join(lines) + "\nGrey labels: not fitted (DNP).  Red dot: LED cathode / pin 1.  Grey pads: the other side.  Board frame in mm, origin at the centre.",
             fontsize=9.5, family="DejaVu Sans Mono", va="bottom")
    pdf.savefig(fig); fig.savefig(png, dpi=110, bbox_inches="tight"); plt.close(fig)

with PdfPages(os.path.join(PROJ, "fab", "assembly.pdf")) as pdf:
    page(True, pdf, os.path.join(PROJ, "fab", "assembly_top.png"))
    page(False, pdf, os.path.join(PROJ, "fab", "assembly_bottom.png"))
for f in ("assembly_top.pdf", "assembly_bottom.pdf"):
    p = os.path.join(PROJ, "fab", f)
    if os.path.exists(p): os.remove(p)
print("assembly drawings written")
