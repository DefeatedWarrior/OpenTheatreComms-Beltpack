"""KiCad hand-off: DXF board outlines (true arcs), placement layers, dimensioned PNG drawings and a size table."""
import os, json, math
import cadquery as cq
from cadquery import Shape, Vector as V
import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(here, "out"); KD = os.path.join(OUT, "kicad"); os.makedirs(KD, exist_ok=True)
info = json.load(open(os.path.join(OUT, "parts_final.json")))
C = info["consts"]
TOP_OFF = 15.0          # top board origin sits 15 mm behind the front face (board centre)

def board_face(name):
    s = Shape.importBrep(os.path.join(OUT, "brep", name + ".brep"))
    if name == "top_pcb":     # view from above: X = x, Y = -(z + 15)  (back edge at the top of the drawing)
        s = s.rotate(V(0, 0, 0), V(1, 0, 0), 90).translate(V(0, -TOP_OFF, 0))
    faces = sorted(s.Faces(), key=lambda f: f.Center().z)
    f = faces[-1]
    assert abs(f.normalAt().z) > 0.999, "not planar"
    return f

def edge_geom(e):
    gt = e.geomType()
    if gt == "LINE":
        a, b = e.startPoint(), e.endPoint(); return ("line", (a.x, a.y), (b.x, b.y))
    if gt == "CIRCLE":
        c = e.arcCenter(); r = e.radius(); a, b, m = e.startPoint(), e.endPoint(), e.positionAt(0.5)
        if (a - b).Length < 1e-6: return ("circle", (c.x, c.y), r)
        ang = lambda p: math.degrees(math.atan2(p.y - c.y, p.x - c.x)) % 360
        a0, a1, am = ang(a), ang(b), ang(m)
        ccw = (am - a0) % 360 < (a1 - a0) % 360
        return ("arc", (c.x, c.y), r, a0, a1) if ccw else ("arc", (c.x, c.y), r, a1, a0)
    pts = [e.positionAt(t / 40) for t in range(41)]
    return ("poly", [(p.x, p.y) for p in pts])

def sample(g, n=64):
    if g[0] == "line": return [g[1], g[2]]
    if g[0] == "poly": return g[1]
    if g[0] == "circle":
        (cx, cy), r = g[1], g[2]; return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]
    (cx, cy), r, a0, a1 = g[1], g[2], g[3], g[4]
    sweep = (a1 - a0) % 360; k = max(4, int(n * sweep / 90))
    return [(cx + r * math.cos(math.radians(a0 + sweep * i / k)), cy + r * math.sin(math.radians(a0 + sweep * i / k))) for i in range(k + 1)]

def outline(name):
    f = board_face(name)
    outer = [edge_geom(e) for e in f.outerWire().Edges()]
    inner = [[edge_geom(e) for e in w.Edges()] for w in f.innerWires()]
    bb = f.BoundingBox()
    return outer, inner, (bb.xmin, bb.ymin, bb.xmax, bb.ymax)

def add_geom(msp, g, layer):
    if g[0] == "line": msp.add_line(g[1], g[2], dxfattribs={"layer": layer})
    elif g[0] == "circle": msp.add_circle(g[1], g[2], dxfattribs={"layer": layer})
    elif g[0] == "arc": msp.add_arc(g[1], g[2], g[3], g[4], dxfattribs={"layer": layer})
    else: msp.add_lwpolyline(g[1], dxfattribs={"layer": layer})

def rect_pts(x, y, w, h): return [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2), (x - w / 2, y - h / 2)]

# ------------------------------------------------------------------ board data in each board's own frame
def key_v(u):
    R_F, R_B, Z_AX = C["R_F"], C["R_B"], C["Z_AX"]
    return -(Z_AX + (math.sqrt(R_F ** 2 - u ** 2) + math.sqrt(R_B ** 2 - u ** 2)) / 2)
boards = {}
# top board: (X, Y) = (x, -z - 15)
tp = []
for p in info["top_parts"]:
    tp.append(dict(label=p["label"], X=p["x"], Y=-p["z"] - TOP_OFF, w=p["w"], h=p["d"], side="F" if p["side"] == "top" else "B", hgt=p["h"]))
tmech = []
for u, v, kw in info["keys"]: tmech.append(("circle", (u, v - TOP_OFF), kw / 2, "keycap"))
tmech.append(("rect", (0.0, (C["GL_V0"] + C["GL_V1"]) / 2 - TOP_OFF), (34.5, C["GL_V1"] - C["GL_V0"]), "OLED glass 34.5 x 23.0"))
tmech.append(("rect", (0.0, C["AA_V"] - TOP_OFF), (29.42, 14.7), "active area"))
for sx in (-1, 1):
    tmech.append(("circle", (sx * C["DX"], -C["DZ"] - TOP_OFF), 15.0, "dial (below)"))
    tmech.append(("circle", (sx * C["DX"], -C["DZ"] - TOP_OFF), 17.4, "no B-side parts inside"))
for x, z in info["end_screws"]: tmech.append(("circle", (x, -z - TOP_OFF), 2.2, "case boss"))
boards["top_pcb"] = dict(parts=tp, holes=[(x, -z - TOP_OFF, 2.2) for x, z in info["top_holes"]], mech=tmech)
# main board: (X, Y) = (x, y), viewed from the front (F = front face)
mp = [dict(label=p["label"], X=p["x"], Y=p["y"], w=p["w"], h=p["h"], side="F" if p["face"] == "front" else "B", hgt=p["t"]) for p in info["main_parts"]]
px0, px1, py0, py1, pz = C["PACK"]
mmech = [("rect", ((px0 + px1) / 2, (py0 + py1) / 2), (px1 - px0, py1 - py0), "battery pack behind (B parts max 3.7 mm)"),
         ("rect", (C["XLR_X"], -27.0), (19.5, 21.0), "XLR-4 body"),
         ("rect", (-43.0, 5.0), (7.0, 18.0), "no copper: ESP32 antenna"),
         ("rect", (44.5, -11.0), (7.0, 38.0), "flex antenna on the end wall"),
         ("circle", (-18.0, 17.4), 5.3, "button cap"), ("rect", (0.0, 17.4), (21.6, 9.6), "button cap"), ("circle", (18.0, 17.4), 5.3, "button cap")]
holes = [(x, y, 2.2) for nm, (x, y) in info["main_holes"].items()]
boards["main_pcb"] = dict(parts=mp, holes=holes, mech=mmech, hole_names=list(info["main_holes"].keys()))
boards["pack_lid_pcb"] = dict(parts=[dict(label=f"pad {n}", X=x, Y=-15.0, w=3.0, h=3.0, side="F", hgt=0) for n, x in (("BAT+", 6.0), ("NTC", 12.0), ("BAT-", 18.0))], holes=[], mech=[])

TITLES = {"top_pcb": "Top PCB  (viewed from above, top side = F.Cu)", "main_pcb": "Main PCB  (viewed from the front, front face = F.Cu)",
          "pack_lid_pcb": "Battery pack pad board  (viewed from the front)"}
summary = {}
for name, B in boards.items():
    outer, inner, bb = outline(name)
    doc = ezdxf.new("R2010", setup=True); doc.units = ezdxf.units.MM
    for ln, col in (("Edge.Cuts", 2), ("Holes", 1), ("Place_F", 3), ("Place_B", 5), ("Mech", 8)): doc.layers.add(ln, color=col)
    msp = doc.modelspace()
    for g in outer: add_geom(msp, g, "Edge.Cuts")
    for w in inner:
        for g in w: add_geom(msp, g, "Edge.Cuts" if not (len(w) == 1 and w[0][0] == "circle" and w[0][2] <= 1.6) else "Holes")
    for p in B["parts"]:
        msp.add_lwpolyline(rect_pts(p["X"], p["Y"], p["w"], p["h"]), dxfattribs={"layer": "Place_" + p["side"]})
        msp.add_text(p["label"], height=0.8, dxfattribs={"layer": "Place_" + p["side"]}).set_placement((p["X"] - p["w"] / 2, p["Y"] + p["h"] / 2 + 0.4))
    for m in B["mech"]:
        if m[0] == "circle": msp.add_circle(m[1], m[2], dxfattribs={"layer": "Mech"})
        else: msp.add_lwpolyline(rect_pts(m[1][0], m[1][1], m[2][0], m[2][1]), dxfattribs={"layer": "Mech"})
    doc.saveas(os.path.join(KD, f"{name}.dxf"))
    # outline-only file: the one to import as Edge.Cuts
    doc2 = ezdxf.new("R2010", setup=True); doc2.units = ezdxf.units.MM; msp2 = doc2.modelspace()
    for g in outer: add_geom(msp2, g, "0")
    for w in inner:
        if not (len(w) == 1 and w[0][0] == "circle" and w[0][2] <= 1.6):
            for g in w: add_geom(msp2, g, "0")
    doc2.saveas(os.path.join(KD, f"{name}_edge_cuts.dxf"))
    summary[name] = dict(bbox=[round(v, 2) for v in bb], size=[round(bb[2] - bb[0], 2), round(bb[3] - bb[1], 2)],
                         arcs=sorted({round(g[2], 2) for g in outer if g[0] in ("arc", "circle")}))

    # ---------------- drawing
    INK, MUTED, ACC, FCOL, BCOL, MECH = "#1d2430", "#6b7280", "#c2410c", "#0f766e", "#1d4ed8", "#9ca3af"
    W_, H_ = bb[2] - bb[0], bb[3] - bb[1]
    fig_w = 13.0 if name != "pack_lid_pcb" else 7.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * (H_ + 34) / (W_ + 40) + 1.6), dpi=150)
    ax.set_aspect("equal"); ax.axis("off")
    ol = []
    segs = [sample(g) for g in outer]
    cur = segs.pop(0); ol = list(cur)
    while segs:                                   # chain the edges end to end so the fill polygon is ordered
        end = ol[-1]
        k = min(range(len(segs)), key=lambda i: min(math.dist(end, segs[i][0]), math.dist(end, segs[i][-1])))
        sg = segs.pop(k)
        if math.dist(end, sg[-1]) < math.dist(end, sg[0]): sg = sg[::-1]
        ol += sg
    ax.fill([p[0] for p in ol], [p[1] for p in ol], color="#e7efe9", zorder=0)
    for g in outer:
        pts = sample(g); ax.plot([p[0] for p in pts], [p[1] for p in pts], color=INK, lw=1.6, zorder=3)
    for w in inner:
        for g in w:
            pts = sample(g); ax.plot([p[0] for p in pts], [p[1] for p in pts], color=INK, lw=1.0, zorder=3)
    for m in B["mech"]:
        if m[0] == "circle": ax.add_patch(Circle(m[1], m[2], fill=False, ls=(0, (2, 2)), lw=0.7, ec=MECH, zorder=1))
        else: ax.add_patch(Rectangle((m[1][0] - m[2][0] / 2, m[1][1] - m[2][1] / 2), m[2][0], m[2][1], fill=False, ls=(0, (2, 2)), lw=0.7, ec=MECH, zorder=1))
    seen = {"dial (below)", "no B-side parts inside", "case boss", "keycap", "button cap"}
    for m in B["mech"]:
        if m[3] in seen: continue
        seen.add(m[3])
        if m[0] == "circle": ax.text(m[1][0], m[1][1] + m[2] + 0.6, m[3], fontsize=5.5, color=MUTED, ha="center", va="bottom", zorder=4)
        else: ax.text(m[1][0] - m[2][0] / 2 + 0.6, m[1][1] + m[2][1] / 2 - 0.6, m[3], fontsize=5.5, color=MUTED, ha="left", va="top", zorder=4,
                      rotation=90 if m[2][0] < 10 else 0, rotation_mode="anchor") if m[2][0] >= 10 else \
             ax.text(m[1][0], m[1][1], m[3], fontsize=5.5, color=MUTED, ha="center", va="center", rotation=90, zorder=4)
    for p in B["parts"]:
        col = FCOL if p["side"] == "F" else BCOL
        ax.add_patch(Rectangle((p["X"] - p["w"] / 2, p["Y"] - p["h"] / 2), p["w"], p["h"], fill=True, fc=col, alpha=0.10, ec=col, lw=0.9,
                               ls="-" if p["side"] == "F" else (0, (3, 1.5)), zorder=2))
        if p["w"] * p["h"] > 9 or name == "pack_lid_pcb":
            ax.text(p["X"], p["Y"], p["label"].replace(" (", "\n("), fontsize=5.2 if p["w"] < 8 else 6, color=col, ha="center", va="center", zorder=5)
    for i, (x, y, d) in enumerate(B["holes"]):
        ax.add_patch(Circle((x, y), d / 2, fill=False, ec=ACC, lw=1.1, zorder=6))
        ax.plot([x - 2, x + 2], [y, y], color=ACC, lw=0.5, zorder=6); ax.plot([x, x], [y - 2, y + 2], color=ACC, lw=0.5, zorder=6)
        lab = (B.get("hole_names") or [f"M{i+1}" for i in range(len(B["holes"]))])[i]
        ax.text(x + 1.6, y + 1.4, f"{lab} ({x:.1f}, {y:.1f})", fontsize=5.8, color=ACC, zorder=6)
    # overall dimensions
    def dim_h(x0, x1, y, txt):
        ax.annotate("", xy=(x0, y), xytext=(x1, y), arrowprops=dict(arrowstyle="<->", color=INK, lw=0.8, shrinkA=0, shrinkB=0))
        ax.text((x0 + x1) / 2, y - 0.8, txt, fontsize=7.5, color=INK, ha="center", va="top")
    def dim_v(y0, y1, x, txt):
        ax.annotate("", xy=(x, y0), xytext=(x, y1), arrowprops=dict(arrowstyle="<->", color=INK, lw=0.8, shrinkA=0, shrinkB=0))
        ax.text(x + 0.9, (y0 + y1) / 2, txt, fontsize=7.5, color=INK, ha="left", va="center", rotation=90)
    dim_h(bb[0], bb[2], bb[1] - 6, f"{W_:.2f}")
    dim_v(bb[1], bb[3], bb[2] + 5, f"{H_:.2f}")
    ax.plot([bb[0], bb[0]], [bb[1] - 7, bb[1]], color=MUTED, lw=0.4); ax.plot([bb[2], bb[2]], [bb[1] - 7, bb[1]], color=MUTED, lw=0.4)
    ax.plot([bb[2], bb[2] + 6], [bb[1], bb[1]], color=MUTED, lw=0.4); ax.plot([bb[2], bb[2] + 6], [bb[3], bb[3]], color=MUTED, lw=0.4)
    ax.plot([0], [0], marker="+", ms=10, color=INK, zorder=7); ax.text(0.6, 0.6, "0,0", fontsize=6, color=INK, zorder=7)
    if name == "main_pcb":
        for (x0, y0), (x1, y1) in zip(info["main_pts"], info["main_pts"][1:] + info["main_pts"][:1]):
            pass
        notes = ["XLR notch: x < -13.0, y < -14.3", "tab: |x| <= 21.0 up to y = 28.5", "corners R1.0"]
    elif name == "top_pcb":
        R_F, R_B = C["R_F"], C["R_B"]
        notes = [f"front edge R{R_F - 2.6:.1f}, back edge R{R_B + 2.6:.1f} (common centre at X=0, Y=+{(-C['Z_AX'] - TOP_OFF):.1f}, behind the board)",
                 "ends R12.4 about (+-37.5, 1.7)", "FPC notch |X| < 16, 1.4 deep", "4 notches R2.9 for the case bosses"]
    else:
        notes = ["24.0 x 8.0 x 0.8 mm, ENIG", "pads 3.0 mm on 6.0 mm pitch"]
    ax.text(bb[0], bb[3] + 8, TITLES[name], fontsize=11, color=INK, weight="bold", ha="left", va="bottom")
    ax.text(bb[0], bb[3] + 4, "  ·  ".join(notes), fontsize=7, color=MUTED, ha="left", va="bottom")
    if name != "pack_lid_pcb":
        extra = ("   grey circles: keycaps, dials (R15) and their wells (R17.4, no B-side parts inside), case bosses" if name == "top_pcb"
                 else "   grey circles: button caps")
        ax.text(bb[0], bb[1] - 12, "solid = F side   dashed = B side   orange = mounting holes (M2, 2.2 mm)" + extra,
                fontsize=6.5, color=MUTED, ha="left", va="top")
    ax.set_xlim(bb[0] - 4, bb[2] + 12); ax.set_ylim(bb[1] - 15, bb[3] + 12)
    fig.savefig(os.path.join(KD, f"{name}_drawing.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

json.dump(dict(summary=summary, boards={k: dict(parts=v["parts"], holes=v["holes"]) for k, v in boards.items()}), open(os.path.join(KD, "boards.json"), "w"), indent=1)
for k, v in summary.items(): print(k, v)
