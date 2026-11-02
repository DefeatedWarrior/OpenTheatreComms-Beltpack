"""Write the base station carrier PCB schematic (KiCad 7 format) from design.py: real library symbols, a short wire and a net label
(or power symbol) on every pin, no-connect flags on unused pins, notes per block."""
import uuid, math, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import Q, dump
import symlib
from design import C, BLOCKS

PROJECT = "base_pcb"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", PROJECT + ".kicad_sch")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
NS = uuid.UUID("3b9d6f2e-7c41-4f0a-a8e5-2d6c9b1e4f70")      # fixed namespace: the same design gives the same UUIDs every run
_n = [0]
def _u():
    _n[0] += 1; return str(uuid.uuid5(NS, f"{PROJECT}/{_n[0]}"))
ROOT = str(uuid.uuid5(NS, PROJECT + "/root"))
U = lambda: Q(_u())
def g(v): return round(v / 1.27) * 1.27             # snap to the 50 mil grid
def eff(size=1.27, hide=False, justify=None):
    e = ["effects", ["font", ["size", size, size]]]
    if justify: e.append(["justify"] + justify.split())
    if hide: e.append("hide")
    return e
def prop(name, val, x, y, hide=False, justify=None, ang=0):
    return ["property", Q(name), Q(val), ["at", round(x, 2), round(y, 2), ang], eff(hide=hide, justify=justify)]

items = []; lib_needed = {}; sym_uuid = {}; pwr_n = [0]
def lib_prop(s, name):
    from sexp import find, first
    for p in find(s, "property"):
        if str(p[1]) == name:
            a = first(p, "at"); e = first(p, "effects")
            j = first(e, "justify"); return float(a[1]), float(a[2]), float(a[3]), (" ".join(map(str, j[1:])) if j else None), ("hide" in e)
    return 0, 0, 0, None, False
def place(lib_id, ref, value, x, y, fields, rot=0, in_bom="yes", ref_at=None, val_at=None, dnp=False):
    s = symlib.get(lib_id); lib_needed[lib_id] = s
    u = U(); sym_uuid[ref] = str(u)
    def pp(name, val, at):
        if at: return prop(name, val, at[0], at[1], hide=at[3] if len(at) > 3 else False, justify=at[2], ang=at[4] if len(at) > 4 else 0)
        px, py, pa, j, h = lib_prop(s, name)
        return prop(name, val, x + px, y - py, hide=h, justify=j, ang=pa)
    node = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, rot], ["unit", 1], ["in_bom", in_bom], ["on_board", "yes"], ["dnp", "yes" if dnp else "no"], ["uuid", u],
            pp("Reference", ref, ref_at), pp("Value", value, val_at)]
    for k, v in fields.items(): node.append(prop(k, v, x, y, hide=True))
    for num, *_ in symlib.pins(s): node.append(["pin", Q(num), ["uuid", U()]])
    node.append(["instances", ["project", Q(PROJECT), ["path", Q("/" + ROOT), ["reference", Q(ref)], ["unit", 1]]]])
    items.append(node); return s
def wire(x1, y1, x2, y2):
    items.append(["wire", ["pts", ["xy", round(x1, 2), round(y1, 2)], ["xy", round(x2, 2), round(y2, 2)]], ["stroke", ["width", 0], ["type", "default"]], ["uuid", U()]])
def label(net, x, y, outward):
    ang = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[outward]
    just = {0: "left bottom", 180: "right bottom", 90: "left bottom", 270: "right bottom"}[ang]
    items.append(["label", Q(net), ["at", round(x, 2), round(y, 2), ang], ["fields_autoplaced"], eff(justify=just), ["uuid", U()]])
def power(net, x, y, outward):
    pwr_n[0] += 1; lid = "power:GND" if net == "GND" else "power:+3V3"
    # GND points down by default, +3V3 up; turn them so they sit beyond the stub
    if net == "GND": rot = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[outward]
    else: rot = {(0, -1): 0, (0, 1): 180, (1, 0): 270, (-1, 0): 90}[outward]
    d = 4.3 if net == "GND" else 4.0
    tx, ty = x + outward[0] * d, y + outward[1] * d
    j = {(1, 0): "left", (-1, 0): "right", (0, 1): None, (0, -1): None}[outward]
    if rot == 90 and j: j = {"left": "right", "right": "left"}[j]     # KiCad mirrors justification for this orientation
    place(lid, f"#PWR{pwr_n[0]:03d}", net, x, y, {"Footprint": "", "Datasheet": ""}, rot=rot,
          ref_at=(x, y, None, True), val_at=(tx, ty, j, False, 90 if rot in (90, 270) else 0))
def junction(x, y): items.append(["junction", ["at", round(x, 2), round(y, 2)], ["diameter", 0], ["color", 0, 0, 0, 0], ["uuid", U()]])
def noconnect(x, y): items.append(["no_connect", ["at", round(x, 2), round(y, 2)], ["uuid", U()]])
def text(t, x, y, size=1.5):
    items.append(["text", Q(t), ["at", x, y, 0], eff(size=size, justify="left top"), ["uuid", U()]])

def extent(c):
    """Box (x0, y0, x1, y1) around a symbol at the origin, including stubs, labels and power symbols (sheet coords, y down)."""
    s = symlib.get(c["lib_id"]); xs, ys = [0.0], [0.0]
    for num, name, px, py, ang, _ in symlib.pins(s):
        net = c["pins"].get(num, c["pins"].get(name))
        ax, ay = px, -py; o = (-round(math.cos(math.radians(ang))), round(math.sin(math.radians(ang))))
        L = 2.54 if c["lib_id"].startswith(("Connector", "Interface")) else 1.27
        reach = 0 if net is None else L + (6.5 if net in ("GND", "+3V3") else 1.2 + 1.05 * len(net))
        xs += [ax - 2.0 * (o[0] == 0), ax + o[0] * reach + 2.0 * (o[0] == 0)]; ys += [ay - 1.5 * (o[1] == 0), ay + o[1] * reach + 1.5 * (o[1] == 0)]
    if c["lib_id"] in ("Device:R", "Device:C"): xs.append(3.0 + 1.0 * max(len(c["ref"]), len(c["value"])) + 2)
    else:
        xs += [min(xs) - 1, max(xs) + 1]; ys += [min(ys) - 3.5, max(ys) + 3.5]
    return min(xs), min(ys), max(xs), max(ys)

SHEET_W, SHEET_H, M = 841.0, 594.0, 18.0           # A1 landscape
BW = 258.0                                          # block width
pos, block_boxes = {}, []
for bname, btitle in BLOCKS:
    parts = [c for c in C if c["block"] == bname]
    parts.sort(key=lambda c: (-len(c["pins"]) if len(c["pins"]) > 3 else 0))
    x = y = 0.0; rowh = 0.0; local = {}
    for c in parts:
        x0, y0, x1, y1 = extent(c); w, h = x1 - x0 + 9, y1 - y0 + 12
        if x + w > BW and x > 0: x = 0.0; y += rowh; rowh = 0.0
        local[c["ref"]] = (x - x0 + 2, y - y0 + 2); x += w; rowh = max(rowh, h)
    block_boxes.append((bname, btitle, BW, y + rowh + 14, local))
bx = by = M; rowh = 0.0
for bname, btitle, w, h, local in block_boxes:
    if bx + w > SHEET_W - M: bx = M; by += rowh + 10; rowh = 0.0
    for ref, (lx, ly) in local.items(): pos[ref] = (bx + lx, by + 14 + ly)
    items.append(["text", Q(btitle), ["at", bx, by + 6, 0], eff(size=2.2, justify="left top"), ["uuid", U()]])
    items.append(["polyline", ["pts", ["xy", bx - 4, by], ["xy", bx + w, by], ["xy", bx + w, by + h], ["xy", bx - 4, by + h], ["xy", bx - 4, by]],
                  ["stroke", ["width", 0.15], ["type", "dash"]], ["fill", ["type", "none"]], ["uuid", U()]])
    bx += w + 12; rowh = max(rowh, h)
print("sheet used to", round(by + rowh), "of", SHEET_H)

conn = {}
for c in C:
    x, y = g(pos[c["ref"]][0]), g(pos[c["ref"]][1])
    fields = {"Footprint": c["fp"], "Datasheet": "~"}
    if c["mpn"]: fields["MPN"] = c["mpn"]
    if c["desc"]: fields["Description"] = c["desc"]
    two_v = c["lib_id"] in ("Device:R", "Device:C")
    dx = 3.0 if c["lib_id"] == "Device:C" else 2.0
    s = place(c["lib_id"], c["ref"], c["value"], x, y, fields, dnp=c["dnp"],
              ref_at=(x + dx, y - 1.0, "left") if two_v else None, val_at=(x + dx, y + 1.6, "left") if two_v else None)
    pl = []
    for num, name, px, py, ang, ptype in symlib.pins(s):
        net = c["pins"].get(num, c["pins"].get(name, "__missing__"))
        if net == "__missing__": raise SystemExit(f"{c['ref']} pin {num}/{name} has no net entry")
        ax, ay = x + px, y - py
        o = (-round(math.cos(math.radians(ang))), round(math.sin(math.radians(ang))))
        if net is None: noconnect(ax, ay); continue
        L = 2.54 if c["lib_id"].startswith(("Connector", "Interface")) else 1.27
        pl.append([num, ax, ay, o, net, ax + o[0] * L, ay + o[1] * L])
        conn.setdefault(net, []).append(f"{c['ref']}.{num}")
    # pins in one column that share a power net in an unbroken run get one rail and one power symbol
    cols = {}
    for p in pl:
        key = (p[3], round(p[1] if p[3][0] else p[2], 2)); cols.setdefault(key, []).append(p)
    for key, ps in cols.items():
        horiz = key[0][0] != 0
        ps.sort(key=lambda p: p[2] if horiz else p[1])
        i = 0
        while i < len(ps):
            j = i
            while j + 1 < len(ps) and ps[j + 1][4] == ps[i][4] and ps[i][4] in ("GND", "+3V3") and \
                    abs((ps[j + 1][2] - ps[j][2]) if horiz else (ps[j + 1][1] - ps[j][1])) < 2.6:
                j += 1
            run = ps[i:j + 1]
            for p in run: wire(p[1], p[2], p[5], p[6])
            for p, q in zip(run, run[1:]):            # rail built end to end so every stub joins it
                wire(p[5], p[6], q[5], q[6])
            for p in run[1:-1]: junction(p[5], p[6])
            last = run[-1]
            if last[4] in ("GND", "+3V3"): power(last[4], last[5], last[6], last[3])
            else: label(last[4], last[5], last[6], last[3])
            i = j + 1
# power flags: +3V3 from the LDO, GND from the supplies
fx, fy = g(M + 10), g(SHEET_H - 40)
for k, net in enumerate(("+3V3", "GND")):
    x, y = fx + 14 * k, fy
    place("power:PWR_FLAG", f"#FLG{k+1:02d}", "PWR_FLAG", x, y, {"Footprint": "", "Datasheet": "~"})
    wire(x, y, x, y + 2.54)
    power(net, x, y + 2.54, (0, 1))
items.append(["text", Q("OpenTheatreComms base station - carrier PCB"), ["at", M, M - 6, 0], eff(size=4.0, justify="left bottom"), ["uuid", U()]])

sch = ["kicad_sch", ["version", 20230121], ["generator", "eeschema"], ["uuid", Q(ROOT)], ["paper", Q("A1")],
       ["title_block", ["title", Q("Base station carrier PCB")], ["date", Q("2026-10-30")], ["rev", Q("0.1")], ["company", Q("OpenTheatreComms")],
        ["comment", 1, Q("ESP32-P4-NANO carrier: power, LR2021 radio and RF, front panel, optional codec. Generated from pcb_base/design.py")]],
       ["lib_symbols"] + list(lib_needed.values())] + items + [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]]]
open(OUT, "w").write(dump(sch) + "\n")
json.dump(dict(root=ROOT, symbols=sym_uuid, conn=conn), open(OUT.replace(".kicad_sch", "_schinfo.json"), "w"), indent=1)
print("wrote", OUT, len(items), "items,", len(conn), "nets")
