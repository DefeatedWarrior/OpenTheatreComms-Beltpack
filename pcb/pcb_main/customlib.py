"""Project library for the main PCB: symbols and footprints KiCad's stock libraries don't have.
Writes lib/OpenTheatreComms.kicad_sym and lib/OpenTheatreComms.pretty/*.kicad_mod."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sexp import Q, dump
LIB = os.path.join(HERE, "lib"); os.makedirs(os.path.join(LIB, "OpenTheatreComms.pretty"), exist_ok=True)

def eff(size=1.27, hide=False, justify=None):
    e = ["effects", ["font", ["size", size, size]]]
    if justify: e.append(["justify", justify])
    if hide: e.append("hide")
    return e

def box_symbol(name, ref, footprint, datasheet, desc, left, right, top=(), bottom=(), min_w=10.16):
    """Rectangle symbol. Each pin list holds (number, name, type); None leaves a gap. Pins sit on a 2.54 grid."""
    n = max(len(left), len(right)); ln = max([len(p[1]) for p in left + right if p] + [4])
    w = max(min_w, round((ln * 1.27 * 2 + 5.08) / 2.54) * 2.54)
    h = max(n, 2) * 2.54 + 2.54
    nt = max(len(top), len(bottom))
    w = max(w, nt * 2.54 + 5.08)
    x0, y0 = -w / 2, h / 2
    pins = []
    def pin(num, nm, typ, x, y, ang):
        pins.append(["pin", typ, "line", ["at", round(x, 2), round(y, 2), ang], ["length", 2.54],
                     ["name", Q(nm), eff()], ["number", Q(num), eff()]])
    for i, p in enumerate(left):
        if p: pin(p[0], p[1], p[2], x0 - 2.54, y0 - 2.54 - i * 2.54, 0)
    for i, p in enumerate(right):
        if p: pin(p[0], p[1], p[2], -x0 + 2.54, y0 - 2.54 - i * 2.54, 180)
    for i, p in enumerate(top):
        if p: pin(p[0], p[1], p[2], -(len(top) - 1) * 1.27 + i * 2.54, y0 + 2.54, 270)
    for i, p in enumerate(bottom):
        if p: pin(p[0], p[1], p[2], -(len(bottom) - 1) * 1.27 + i * 2.54, -y0 - 2.54, 90)
    yb = -y0
    return ["symbol", Q(name), ["in_bom", "yes"], ["on_board", "yes"],
            ["property", Q("Reference"), Q(ref), ["at", round(x0, 2), round(y0 + 1.27, 2), 0], eff(justify="left")],
            ["property", Q("Value"), Q(name), ["at", round(x0, 2), round(yb - 1.27, 2), 0], eff(justify="left")],
            ["property", Q("Footprint"), Q(footprint), ["at", 0, 0, 0], eff(hide=True)],
            ["property", Q("Datasheet"), Q(datasheet), ["at", 0, 0, 0], eff(hide=True)],
            ["property", Q("Description"), Q(desc), ["at", 0, 0, 0], eff(hide=True)],
            ["symbol", Q(name + "_0_1"), ["rectangle", ["start", round(x0, 2), round(y0, 2)], ["end", round(-x0, 2), round(yb, 2)],
                                          ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]],
            ["symbol", Q(name + "_1_1")] + pins]

P_IN, P_OUT, P_IO, P_PWR, P_PO, P_PAS, P_OC, P_NC = "input", "output", "bidirectional", "power_in", "power_out", "passive", "open_collector", "no_connect"
SYMS = [
    box_symbol("NAU88C22", "U", "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm_ThermalVias",
               "https://www.nuvoton.com/export/resource-files/DS_NAU88C22_DataSheet_EN_Rev1.1.pdf",
               "Nuvoton NAU88C22 stereo audio codec with BTL speaker driver, QFN-32",
               left=[("1", "LMICP", P_IN), ("2", "LMICN", P_IN), ("3", "LLIN/GPIO2", P_IO), ("4", "RMICP", P_IN), ("5", "RMICN", P_IN),
                     ("6", "RLIN/GPIO3", P_IO), None, ("19", "LAUXIN", P_IN), ("20", "RAUXIN", P_IN), None, ("32", "MICBIAS", P_PO), ("27", "VREF", P_PAS),
                     None, ("11", "MCLK", P_IN), ("8", "BCLK", P_IO), ("7", "FS", P_IO), ("10", "DACIN", P_IN), ("9", "ADCOUT", P_OUT)],
               right=[("31", "VDDA", P_PWR), ("14", "VDDB", P_PWR), ("13", "VDDC", P_PWR), ("26", "VDDSPK", P_PWR), None,
                      ("30", "LHP", P_OUT), ("29", "RHP", P_OUT), ("21", "AUXOUT1", P_OUT), ("22", "AUXOUT2", P_OUT), ("25", "LSPKOUT", P_OUT),
                      ("23", "RSPKOUT", P_OUT), None, ("16", "SCLK", P_IN), ("17", "SDIO", P_IO), ("15", "CSB/GPIO1", P_IO), ("18", "MODE", P_IN)],
               bottom=[("28", "VSSA", P_PWR), ("12", "VSSD", P_PWR), ("24", "VSSSPK", P_PWR), ("33", "EP", P_PWR)]),
    box_symbol("TP4056", "U", "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm_ThermalVias", "https://wiki.adom.inc/ray/tp4056",
               "1 A linear Li-ion charger, ESOP-8",
               left=[("4", "VCC", P_PWR), ("8", "CE", P_IN), ("1", "TEMP", P_IN), ("2", "PROG", P_PAS)],
               right=[("5", "BAT", P_PO), ("7", "~{CHRG}", P_OC), ("6", "~{STDBY}", P_OC)],
               bottom=[("3", "GND", P_PWR), ("9", "EP", P_PWR)]),
    box_symbol("MAX17048", "U", "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm",
               "https://www.analog.com/media/en/technical-documentation/data-sheets/MAX17048-MAX17049.pdf",
               "1-cell ModelGauge fuel gauge, I2C 0x36, TDFN-8 2x2",
               left=[("3", "VDD", P_PWR), ("2", "CELL", P_IN), ("1", "CTG", P_IN), ("6", "QSTRT", P_IN)],
               right=[("8", "SDA", P_IO), ("7", "SCL", P_IN), ("5", "~{ALRT}", P_OC)],
               bottom=[("4", "GND", P_PWR), ("9", "EP", P_PWR)]),
    box_symbol("PE4259", "U", "Package_TO_SOT_SMD:SOT-363_SC-70-6", "https://psemi-old.bonfirela.com/pdf/datasheets/pe4259ds.pdf",
               "pSemi PE4259 SPDT RF switch, 10 MHz-3 GHz, single-pin control (pin 6 = VDD)",
               left=[("5", "RFC", P_PAS), None, ("4", "CTRL", P_IN), ("6", "VDD", P_PWR)],
               right=[("1", "RF1", P_PAS), None, ("3", "RF2", P_PAS)], bottom=[("2", "GND", P_PWR)]),
    box_symbol("LR2021_Module_Elecrow", "U", "OpenTheatreComms:LR2021_Elecrow_10x10mm",
               "https://www.elecrow.com/wiki/elecrow-lr2021-lora-module.html",
               "Elecrow LR2021 module (LMM16121D): Semtech LR2021, 32 MHz TCXO, sub-GHz and 2.4 GHz ports, 20 castellated pads",
               left=[("1", "VDD", P_PWR), None, ("2", "NSS", P_IN), ("3", "SCK", P_IN), ("4", "MOSI", P_IN), ("5", "MISO", P_OUT), None,
                     ("10", "NRESET", P_IN), ("9", "BUSY", P_OUT), ("7", "DIO6", P_IO), ("8", "DIO5", P_IO), ("15", "TX/RX_EN", P_IO)],
               right=[("11", "ANT_LF", P_PAS), None, ("17", "ANT_HF", P_PAS), None, ("16", "NC", P_NC)],
               bottom=[("6", "GND", P_PWR), ("12", "GND", P_PWR), ("13", "GND", P_PWR), ("14", "GND", P_PWR), ("18", "GND", P_PWR),
                       ("19", "GND", P_PWR), ("20", "GND", P_PWR)]),
]
lib = ["kicad_symbol_lib", ["version", 20220914], ["generator", "kicad_symbol_editor"]] + SYMS
open(os.path.join(LIB, "OpenTheatreComms.kicad_sym"), "w").write(dump(lib) + "\n")

# ------------------------------------------------------------------ footprints
def fp_text(kind, text, x, y, layer, size=1.0, hide=False):
    t = ["fp_text", kind, Q(text), ["at", x, y], ["layer", Q(layer)]]
    if hide: t.append("hide")
    t.append(["effects", ["font", ["size", size, size], ["thickness", round(size * 0.15, 3)]]])
    return t
def rect(x0, y0, x1, y1, layer, w):
    return ["fp_rect", ["start", x0, y0], ["end", x1, y1], ["stroke", ["width", w], ["type", "default"]], ["fill", "none"], ["layer", Q(layer)]]
def line(x0, y0, x1, y1, layer, w):
    return ["fp_line", ["start", x0, y0], ["end", x1, y1], ["stroke", ["width", w], ["type", "default"]], ["layer", Q(layer)]]
def circle(cx, cy, r, layer, w):
    return ["fp_circle", ["center", cx, cy], ["end", round(cx + r, 3), cy], ["stroke", ["width", w], ["type", "default"]], ["fill", "none"], ["layer", Q(layer)]]
def smd(num, x, y, w, h, shape="roundrect"):
    p = ["pad", Q(num), "smd", shape, ["at", round(x, 3), round(y, 3)], ["size", w, h], ["layers", Q("F.Cu"), Q("F.Paste"), Q("F.Mask")]]
    if shape == "roundrect": p.append(["roundrect_rratio", 0.25])
    return p
def tht(num, x, y, d, drill, shape="circle"):
    return ["pad", Q(num), "thru_hole", shape, ["at", x, y], ["size", d, d], ["drill", drill], ["layers", Q("*.Cu"), Q("*.Mask")]]
def write_fp(name, descr, attr, items):
    fp = ["footprint", Q(name), ["version", 20221018], ["generator", "pcbnew"], ["layer", Q("F.Cu")], ["descr", Q(descr)], ["attr", attr]] + items
    open(os.path.join(LIB, "OpenTheatreComms.pretty", name + ".kicad_mod"), "w").write(dump(fp) + "\n")

# Elecrow LR2021 module: 10 x 10 mm, 20 castellated pads at 1.27 mm, five per side, numbered anticlockwise from the top of the
# left side (pin 1). Pads run 0.9 mm inside to 1.0 mm outside the module edge for hand soldering. CHECK against Elecrow's drawing.
items = [fp_text("reference", "REF**", 0, -7.2, "F.SilkS"), fp_text("value", "LR2021_Elecrow_10x10mm", 0, 7.2, "F.Fab"),
         fp_text("user", "${REFERENCE}", 0, 0, "F.Fab"), rect(-5, -5, 5, 5, "F.Fab", 0.1), rect(-6.25, -6.25, 6.25, 6.25, "F.CrtYd", 0.05),
         line(-5.1, -5.1, -5.1, -3.6, "F.SilkS", 0.12), line(-5.1, -5.1, -3.6, -5.1, "F.SilkS", 0.12), circle(-6.0, -3.5, 0.15, "F.SilkS", 0.3)]
# From Elecrow's own Eagle design of the module (package "10*10MM"): 5 castellated pads per side at 1.27 mm, pin 1 at the
# top of the left side seen from the top, numbered anticlockwise, and four 1.2 mm ground pads underneath (P$41-44, all
# GND; numbered 12 here so they take the GND net). LR_PIN1_SIDE moves pins 1-5 to another side if ever needed.
LR_PIN1_SIDE = os.environ.get("LR_PIN1_SIDE", "L")
E, L, W = 5.05, 1.9, 0.8
SIDES = {"L": lambda o: (-E, o, L, W), "B": lambda o: (o, E, W, L), "R": lambda o: (E, -o, L, W), "T": lambda o: (-o, -E, W, L)}
ORDER = "LBRT"; k0 = ORDER.index(LR_PIN1_SIDE)
for sdx in range(4):
    side = ORDER[(k0 + sdx) % 4]
    for i in range(5):
        x_, y_, w_, h_ = SIDES[side](-2.54 + 1.27 * i)       # left top-to-bottom, bottom left-to-right, right bottom-to-top, top right-to-left
        items.append(smd(str(1 + 5 * sdx + i), x_, y_, w_, h_))
for gx, gy in ((-0.3, 0.3), (1.7, 0.3), (-0.3, 2.3), (1.7, 2.3)):          # from Elecrow's module design file (top view)
    items.append(smd("12", gx, gy, 1.2, 1.2, shape="rect"))
write_fp("LR2021_Elecrow_10x10mm", f"Elecrow LR2021 module (LMM16121D), 10x10 mm, 20 castellated pads at 1.27 mm plus 4 ground pads, per Elecrow's module design file; pins 1-5 on side {LR_PIN1_SIDE}.",
         "smd", items)

# Spring pin, through-hole tail: 1.0 mm hole for the LCSC Xinyangze YZ08415060P-02 (0.8 mm tail); also takes a Mill-Max 0906
items = [fp_text("reference", "REF**", 0, -2.2, "F.SilkS"), fp_text("value", "MillMax_0906_Pogo", 0, 2.2, "F.Fab"),
         circle(0, 0, 0.95, "F.Fab", 0.1), circle(0, 0, 1.3, "F.CrtYd", 0.05), tht("1", 0, 0, 1.6, 1.0)]
write_fp("MillMax_0906_SpringPin", "Spring pin, through-hole: 1.0 mm hole for an 0.8 mm tail (Xinyangze YZ08415060P-02); a Mill-Max 0906 (0.43 mm tail) also fits, loosely.", "through_hole", items)

# 8 mm coin vibration motor glued to the board, with two pads for its flying leads
items = [fp_text("reference", "REF**", 0, -5.2, "F.SilkS"), fp_text("value", "Coin_Motor_8mm", 0, 5.2, "F.Fab"),
         circle(0, 0, 4.0, "F.Fab", 0.1), circle(0, 0, 4.0, "F.SilkS", 0.12), circle(0, 0, 4.3, "F.CrtYd", 0.05),
         rect(4.6, -2.3, 7.4, 2.3, "F.CrtYd", 0.05), smd("1", 6.0, -1.2, 1.6, 1.4), smd("2", 6.0, 1.2, 1.6, 1.4),
         fp_text("user", "+", 7.7, -1.2, "F.SilkS", 0.8)]
write_fp("Motor_Coin_8mm_LeadPads", "8 x 2.7 mm coin vibration motor, glued down, flying leads to two pads", "smd", items)
print("custom library written:", [s[1] for s in SYMS])
