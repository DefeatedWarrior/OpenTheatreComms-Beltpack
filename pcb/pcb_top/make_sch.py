"""Write the top PCB schematic (KiCad 7 format) from design.py: real library symbols, a short wire and a net label
(or power symbol) on every pin, no-connect flags on unused pins, notes per block."""
import uuid, math, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import Q, dump
import symlib
from design import C

PROJECT = "top_pcb"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", PROJECT + ".kicad_sch")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
ROOT = str(uuid.uuid4())
U = lambda: Q(str(uuid.uuid4()))
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
def place(lib_id, ref, value, x, y, fields, rot=0, in_bom="yes", ref_at=None, val_at=None):
    s = symlib.get(lib_id); lib_needed[lib_id] = s
    u = U(); sym_uuid[ref] = str(u)
    def pp(name, val, at):
        if at: return prop(name, val, at[0], at[1], hide=at[3] if len(at) > 3 else False, justify=at[2], ang=at[4] if len(at) > 4 else 0)
        px, py, pa, j, h = lib_prop(s, name)
        return prop(name, val, x + px, y - py, hide=h, justify=j, ang=pa)
    node = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, rot], ["unit", 1], ["in_bom", in_bom], ["on_board", "yes"], ["dnp", "no"], ["uuid", u],
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

conn = {}
for c in C:
    x, y = g(c["sch"][0]), g(c["sch"][1])
    fields = {"Footprint": c["fp"], "Datasheet": "~"}
    if c["mpn"]: fields["MPN"] = c["mpn"]
    if c["desc"]: fields["Description"] = c["desc"]
    two_v = c["lib_id"] in ("Device:R", "Device:C")
    dx = 3.0 if c["lib_id"] == "Device:C" else 2.0
    s = place(c["lib_id"], c["ref"], c["value"], x, y, fields,
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
# power flags: power enters through J1
for k, net in enumerate(("+3V3", "GND")):
    x, y = g(372 + 14 * k), g(222)
    place("power:PWR_FLAG", f"#FLG{k+1:02d}", "PWR_FLAG", x, y, {"Footprint": "", "Datasheet": "~"})
    wire(x, y, x, y + 2.54)
    power(net, x, y + 2.54, (0, 1))

NOTES = [
    ("Talk keys and key lights\nC&K PTS815 under each keycap, red 0603 LED inside the cap, about 5 mA", 22, 26),
    ("Status lights\nRed + green 0603 pair under each end light pipe", 198, 26),
    ("IO expander, I2C address 0x20\nKeys in, key/status lights and OLED reset out.\nThe I2C pull-ups live here; leave them off the main PCB.", 22, 104),
    ("OLED: 1.3 in 128x64 white, GME12864-110 (SH1106)\nI2C mode, address 0x3C. 30-pin 0.5 mm FPC into a ZIF on B.\nCheck the pin map and contact side against your panel's drawing.", 160, 104),
    ("Dials: Bourns PEC12R-4215F-N0024 on the B side\nDatasheet RC filter on A and B (10k pull-up, 10k series, 10 nF)", 288, 84),
    ("Link to the main PCB: JST SH 10-way, 50 mm cable\n1 GND, 2 +3V3, 3 SDA, 4 SCL, 5 INT, 6-9 dial A/B, 10 GND", 288, 200),
    ("M2 mounting holes into the top-plate bosses", 22, 240),
]
for t_, x, y in NOTES: text(t_, x, y)
items.append(["text", Q("OpenTheatreComms beltpack - top PCB"), ["at", 22, 18, 0], eff(size=3.0, justify="left bottom"), ["uuid", U()]])

sch = ["kicad_sch", ["version", 20230121], ["generator", "eeschema"], ["uuid", Q(ROOT)], ["paper", Q("A3")],
       ["title_block", ["title", Q("Beltpack top PCB")], ["date", Q("2026-10-26")], ["rev", Q("0.1")], ["company", Q("OpenTheatreComms")],
        ["comment", 1, Q("Keys, key and status lights, OLED, dials, IO expander. Generated from pcb_top/design.py")]],
       ["lib_symbols"] + list(lib_needed.values())] + items + [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]]]
open(OUT, "w").write(dump(sch) + "\n")
json.dump(dict(root=ROOT, symbols=sym_uuid, conn=conn), open(OUT.replace(".kicad_sch", "_schinfo.json"), "w"), indent=1)
print("wrote", OUT, len(items), "items,", len(conn), "nets")
