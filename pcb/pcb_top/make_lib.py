"""Project footprints for the top PCB. Writes lib/OpenTheatreComms.pretty/OLED_Tail_30P_0.7mm_Solder.kicad_mod.

The 1.3 in 128x64 30-pin OLED panels (SH1106 / SSD1306, 34.5 x 23 mm glass) end in a solder tail: 30 leads, 0.40 mm wide
at 0.70 mm pitch (20.3 mm first to last), 2.0 mm of bare lead at the end, tail 22 mm wide, two alignment marks 16 mm apart.
The tail wraps round the board's back-edge notch and is soldered flat onto these pads on B.Cu. No paste: the pads are
tinned and the tail is soldered with an iron last, after all reflow (the panel would not survive the hot plate).

Pad k holds the tail lead at position k counted from -X in this footprint (the board places it so panel pin 31 - k lands
on pad k; see design.py). Local frame: pads centred on y = 0; tail end at y = -1.2, board edge at y = +5.8 (when placed
at board y = 5.5 on B)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
P, N, PW, PL = 0.70, 30, 0.45, 3.0
TAIL_END, EDGE, MARK_Y, HALF_W = -1.2, 5.8, 3.55, 11.0
o = ['(footprint "OLED_Tail_30P_0.7mm_Solder" (version 20221018) (generator pcbnew) (layer "F.Cu")',
     '  (descr "Solder pads for a 1.3 in 30-pin OLED panel tail: 30 leads, 0.4 mm wide, 0.7 mm pitch, 2 mm bare lead; tail 22 mm wide, alignment marks 16 mm apart. No paste: solder by iron after reflow.")',
     '  (attr smd)',
     '  (fp_text reference "REF**" (at 0 -2.4) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
     '  (fp_text value "OLED_Tail_30P_0.7mm_Solder" (at 0 6.6) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))',
     '  (fp_text user "1" (at 11.7 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
     '  (fp_text user "30" (at -12.0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))']
def line(x0, y0, x1, y1, layer, w): o.append(f'  (fp_line (start {x0} {y0}) (end {x1} {y1}) (stroke (width {w}) (type default)) (layer "{layer}"))')
# tail outline on the fab layer; side guides on silk (clear of the pads)
for x0, y0, x1, y1 in ((-HALF_W, TAIL_END, HALF_W, TAIL_END), (HALF_W, TAIL_END, HALF_W, EDGE), (-HALF_W, TAIL_END, -HALF_W, EDGE)):
    line(x0, y0, x1, y1, "F.Fab", 0.1)
for s in (-1, 1):
    line(s * HALF_W, TAIL_END, s * HALF_W, EDGE - 0.6, "F.SilkS", 0.12)
    line(s * HALF_W, TAIL_END, s * (HALF_W - 0.3), TAIL_END, "F.SilkS", 0.12)
    o.append(f'  (fp_circle (center {s * 8.0} {MARK_Y}) (end {s * 8.0 + 0.5} {MARK_Y}) (stroke (width 0.12) (type default)) (fill none) (layer "F.SilkS"))')
o.append(f'  (fp_rect (start {-HALF_W - 0.3} {TAIL_END - 0.6}) (end {HALF_W + 0.3} {PL / 2 + 0.3}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))')
for k in range(1, N + 1):
    x = round((k - (N + 1) / 2) * P, 3)
    o.append(f'  (pad "{k}" smd roundrect (at {x} 0) (size {PW} {PL}) (layers "F.Cu" "F.Mask") (roundrect_rratio 0.25))')
o.append(')')
d = os.path.join(HERE, "lib", "OpenTheatreComms.pretty"); os.makedirs(d, exist_ok=True)
open(os.path.join(d, "OLED_Tail_30P_0.7mm_Solder.kicad_mod"), "w").write("\n".join(o) + "\n")
print("written")

# ------------------------------------------------------------------ symbols: TI LP5024 (RSM, VQFN-32 4x4), pins per TI SLVSEB8B
from sexp import Q, dump
def eff(size=1.27, hide=False, justify=None):
    e = ["effects", ["font", ["size", size, size]]]
    if justify: e.append(["justify", justify])
    if hide: e.append("hide")
    return e
def box_symbol(name, ref, footprint, datasheet, desc, left, right, top=(), bottom=(), min_w=10.16):
    n = max(len(left), len(right)); ln = max([len(p[1]) for p in left + right if p] + [4])
    w = max(min_w, round((ln * 1.27 * 2 + 5.08) / 2.54) * 2.54); h = max(n, 2) * 2.54 + 2.54
    w = max(w, max(len(top), len(bottom)) * 2.54 + 5.08); x0, y0 = -w / 2, h / 2; pins = []
    def pin(num, nm, typ, x, y, ang):
        pins.append(["pin", typ, "line", ["at", round(x, 2), round(y, 2), ang], ["length", 2.54], ["name", Q(nm), eff()], ["number", Q(num), eff()]])
    for i, p in enumerate(left):
        if p: pin(p[0], p[1], p[2], x0 - 2.54, y0 - 2.54 - i * 2.54, 0)
    for i, p in enumerate(right):
        if p: pin(p[0], p[1], p[2], -x0 + 2.54, y0 - 2.54 - i * 2.54, 180)
    for i, p in enumerate(bottom):
        if p: pin(p[0], p[1], p[2], -(len(bottom) - 1) * 1.27 + i * 2.54, -y0 - 2.54, 90)
    return ["symbol", Q(name), ["in_bom", "yes"], ["on_board", "yes"],
            ["property", Q("Reference"), Q(ref), ["at", round(x0, 2), round(y0 + 1.27, 2), 0], eff(justify="left")],
            ["property", Q("Value"), Q(name), ["at", round(x0, 2), round(-y0 - 1.27, 2), 0], eff(justify="left")],
            ["property", Q("Footprint"), Q(footprint), ["at", 0, 0, 0], eff(hide=True)],
            ["property", Q("Datasheet"), Q(datasheet), ["at", 0, 0, 0], eff(hide=True)],
            ["property", Q("Description"), Q(desc), ["at", 0, 0, 0], eff(hide=True)],
            ["symbol", Q(name + "_0_1"), ["rectangle", ["start", round(x0, 2), round(y0, 2)], ["end", round(-x0, 2), round(-y0, 2)],
                                          ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]],
            ["symbol", Q(name + "_1_1")] + pins]
PI, PO, PB, PW = "input", "output", "bidirectional", "power_in"
lp = box_symbol("LP5024", "U", "Package_DFN_QFN:VQFN-32-1EP_4x4mm_P0.4mm_EP2.8x2.8mm", "https://www.ti.com/lit/ds/symlink/lp5024.pdf",
                "24-channel 12-bit PWM I2C constant-current RGB LED driver",
                left=[("27", "VCC", PW), ("30", "EN", PI), ("29", "SCL", PI), ("28", "SDA", PB), ("25", "ADDR0", PI), ("26", "ADDR1", PI),
                      ("31", "IREF", "passive"), ("32", "VCAP", "passive"), None, ("33", "GND", PW)],
                right=[(str(k + 1), f"OUT{k}", "open_collector") for k in range(24)])
lib = ["kicad_symbol_lib", ["version", 20220914], ["generator", "kicad_symbol_editor"], lp]
open(os.path.join(HERE, "lib", "OpenTheatreComms.kicad_sym"), "w").write(dump(lib) + "\n")
print("symbol written")
