"""Top PCB circuit: the single source of truth for the schematic and the board.

Board frame (mm): origin at the board centre, +X right, +Y toward the hip (back) edge, viewed from above (F = top side).
Schematic positions are on an A3 sheet (mm, Y down).
"""
R0603 = "Resistor_SMD:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder"
C0603 = "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder"
L0603 = "LED_SMD:LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder"

KEYS = [(-37.5, 1.70, 4.0), (-23.5, 0.67, 3.4), (23.5, 0.67, 3.4), (37.5, 1.70, 4.0)]   # key centre X, Y, LED offset toward the front
STATUS = [(-46.5, 1.70), (46.5, 1.70)]
ENC = [(-37.5, 1.70), (37.5, 1.70)]

C = []   # components
def comp(ref, lib_id, value, fp, pins, sch, pcb=None, mpn="", desc=""):
    C.append(dict(ref=ref, lib_id=lib_id, value=value, fp=fp, pins=pins, sch=sch, pcb=pcb, mpn=mpn, desc=desc))

# ---------------------------------------------------------------- talk keys, key LEDs
for i, (x, y, off) in enumerate(KEYS):
    n = i + 1; sx = 30 + i * 40
    comp(f"SW{n}", "Switch:SW_Push", "PTS815", "Button_Switch_SMD:SW_SPST_PTS810", {"1": "GND", "2": f"KEY{n}"},
         (sx, 48), ("F", x, y, 0), "C&K PTS815 SJM 250 SMTR LFS", f"Talk key {n}")
    comp(f"D{n}", "Device:LED", "red", L0603, {"1": f"LEDK{n}", "2": f"LEDA{n}"},
         (sx, 68), ("F", x, y - off, 180), "Lite-On LTST-C191KRKT", f"Key {n} light")
    comp(f"R{n}", "Device:R", "220", R0603, {"1": "+3V3", "2": f"LEDA{n}"},
         (sx + 16, 68), ("F", x, y - off - 1.9, 180), "0603 1%", f"Key {n} LED current, about 5 mA")
# ---------------------------------------------------------------- status lights (red + green under each light pipe)
for j, (x, y) in enumerate(STATUS):
    side = "L" if x < 0 else "R"
    for k, (col, dy, ry) in enumerate((("red", 0.76, 2.8), ("green", -0.76, -2.8))):
        n = 5 + 2 * j + k; sx = 200 + (2 * j + k) * 34
        comp(f"D{n}", "Device:LED", col, L0603, {"1": f"ST{side}_{col[0].upper()}K", "2": f"ST{side}_{col[0].upper()}A"},
             (sx, 68), ("F", x, y + dy, 0), "Lite-On LTST-C191KRKT" if col == "red" else "Lite-On LTST-C191KGKT", f"Status light {side} {col}")
        comp(f"R{n}", "Device:R", "220", R0603, {"1": "+3V3", "2": f"ST{side}_{col[0].upper()}A"},
             (sx + 13, 68), ("F", x, y + ry, 0), "0603 1%", f"Status {side} {col} current")
# ---------------------------------------------------------------- IO expander
tca = {"~{INT}": "INT_N", "A0": "GND", "A1": "GND", "A2": "GND", "SCL": "SCL", "SDA": "SDA", "VCC": "+3V3", "GND": "GND",
       "P00": "KEY1", "P01": "KEY2", "P02": "KEY3", "P03": "KEY4", "P04": "OLED_RES_N", "P05": None, "P06": None, "P07": None,
       "P10": "LEDK1", "P11": "LEDK2", "P12": "LEDK3", "P13": "LEDK4",
       "P14": "STL_RK", "P15": "STL_GK", "P16": "STR_RK", "P17": "STR_GK"}
comp("U1", "Interface_Expansion:TCA9555PWR", "TCA9555PWR", "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm", tca,
     (85, 165), ("B", 0.0, -4.6, 90), "TI TCA9555PWR", "16-bit I2C IO expander, 0x20, internal 100k pull-ups")
comp("C1", "Device:C", "100n", C0603, {"1": "+3V3", "2": "GND"}, (120, 142), ("B", 5.6, -3.4, 90), "0603 X7R 50 V", "U1 decoupling")
comp("R9", "Device:R", "10k", R0603, {"1": "+3V3", "2": "INT_N"}, (22, 128), ("B", -12.2, -8.2, 0), "0603 1%", "INT pull-up")
comp("R10", "Device:R", "4.7k", R0603, {"1": "+3V3", "2": "SDA"}, (34, 128), ("B", -8.6, -6.4, 0), "0603 1%", "I2C pull-up")
comp("R11", "Device:R", "4.7k", R0603, {"1": "+3V3", "2": "SCL"}, (46, 128), ("B", -8.6, -8.2, 0), "0603 1%", "I2C pull-up")
# ---------------------------------------------------------------- OLED (1.3in 128x64 30-pin panel, SH1106, I2C, 0.7 mm solder tail)
oled = {1: "GND", 2: "C2P", 3: "C2N", 4: "C1P", 5: "C1N", 6: "+3V3", 7: None, 8: "GND", 9: "+3V3", 10: "GND", 11: "+3V3",
        12: "GND", 13: "GND", 14: "OLED_RES_N", 15: "GND", 16: "GND", 17: "GND", 18: "SCL", 19: "SDA", 20: "SDA",
        21: "GND", 22: "GND", 23: "GND", 24: "GND", 25: "GND", 26: "IREF", 27: "VCOMH", 28: "VCC_OLED", 29: "GND", 30: "GND"}
# The panel tail leaves the glass toward the back edge and folds round the notch, which keeps every contact at the same X,
# and is soldered flat onto 30 pads on B (0.7 mm pitch, lib/OpenTheatreComms.pretty, written by make_lib.py). Pad 1 is at -X. With the panel's pin 1 at +X (on the left when the
# panel is viewed face up with the tail toward you), panel pin k lands on pad 31 - k. Set False if your panel is the other way.
OLED_PIN1_AT_PLUS_X = True
def oled_pad(k): return 31 - k if OLED_PIN1_AT_PLUS_X else k
comp("J2", "Connector_Generic:Conn_01x30", "OLED tail", "OpenTheatreComms:OLED_Tail_30P_0.7mm_Solder",
     {str(oled_pad(k)): v for k, v in oled.items()}, (192, 165), ("B", 0.0, 5.5, 0), "OLED panel tail soldered to pads (no part)",
     "Solder pads for the panel's 30-lead tail (0.7 mm pitch). Standard 1.3 in SH1106 30-pin pin map; I2C (BS2..0 = 010), address 0x3C")
comp("C2", "Device:C", "1u", C0603, {"1": "C1P", "2": "C1N"}, (222, 138), ("B", 8.5, 1.2, 180), "0603 X5R", "SH1106 charge-pump flying cap (1 uF per the panel reference circuit)")
comp("C3", "Device:C", "1u", C0603, {"1": "C2P", "2": "C2N"}, (234, 138), ("B", 11.9, 1.2, 180), "0603 X5R", "SH1106 charge-pump flying cap (1 uF per the panel reference circuit)")
comp("C4", "Device:C", "4.7u", C0603, {"1": "VCC_OLED", "2": "GND"}, (222, 168), ("B", -13.5, 1.7, 0), "0603 X5R 25 V", "VPP (OLED drive) reservoir")
comp("C5", "Device:C", "4.7u", C0603, {"1": "VCOMH", "2": "GND"}, (234, 168), ("B", -10.1, 1.7, 0), "0603 X5R 25 V", "VCOMH")
comp("C6", "Device:C", "4.7u", C0603, {"1": "+3V3", "2": "GND"}, (246, 168), ("B", 7.8, -0.6, 0), "0603 X5R 10 V", "Charge-pump supply (VBAT pin)")
comp("C7", "Device:C", "1u", C0603, {"1": "+3V3", "2": "GND"}, (258, 168), ("B", 3.0, 1.7, 0), "0603 X5R 10 V", "Logic supply (VDD pin)")
comp("R12", "Device:R", "560k", R0603, {"1": "IREF", "2": "GND"}, (246, 138), ("B", -6.7, 1.7, 0), "0603 1%", "Segment current reference: 560k per the panel reference circuit (12.5 uA max)")
# ---------------------------------------------------------------- dials: Alps EC11N (PEC12R footprint) with the datasheet RC filter on A and B
for e, (x, y) in enumerate(ENC):
    side = "L" if x < 0 else "R"; n = e + 1; sy = 118 + e * 50
    comp(f"ENC{n}", "Device:RotaryEncoder", "PEC12R", "Rotary_Encoder:RotaryEncoder_Bourns_Vertical_PEC12R-3x17F-Nxxxx",
         {"A": f"ENC_{side}_A_RAW", "B": f"ENC_{side}_B_RAW", "C": "GND"}, (305, sy + 10), ("B", x, y, 90),
         "Alps EC11N1520402", f"{'Left' if side == 'L' else 'Right'} dial: Alps EC11, 30 detents / 15 pulses, no switch, mounted upside-down on B (fits the PEC12R footprint)")
    base = 13 + 4 * e; cbase = 8 + 2 * e
    sg = 1 if x > 0 else -1
    for ch, k in (("A", 0), ("B", 1)):
        ry = -7.6 - 1.8 * k
        comp(f"R{base + 2 * k}", "Device:R", "10k", R0603, {"1": "+3V3", "2": f"ENC_{side}_{ch}_RAW"}, (330 + 12 * k, sy),
             ("F", sg * 33.2, ry, 0 if sg < 0 else 180), "0603 1%", "Encoder pull-up")
        comp(f"R{base + 2 * k + 1}", "Device:R", "10k", R0603, {"1": f"ENC_{side}_{ch}_RAW", "2": f"ENC_{side}_{ch}"}, (354 + 12 * k, sy),
             ("F", sg * 29.8, ry, 0 if sg < 0 else 180), "0603 1%", "Encoder series R")
        comp(f"C{cbase + k}", "Device:C", "10n", C0603, {"1": f"ENC_{side}_{ch}", "2": "GND"}, (380 + 12 * k, sy),
             ("F", sg * 26.4, ry, 0 if sg < 0 else 180), "0603 X7R 50 V", "Encoder filter cap")
# ---------------------------------------------------------------- board link to the main PCB
link = {"1": "GND", "2": "+3V3", "3": "SDA", "4": "SCL", "5": "INT_N", "6": "ENC_L_A", "7": "ENC_L_B", "8": "ENC_R_A", "9": "ENC_R_B", "10": "GND"}
comp("J1", "Connector_Generic:Conn_01x10", "Main PCB link", "Connector_JST:JST_SH_BM10B-SRSS-TB_1x10-1MP_P1.00mm_Vertical", link,
     (330, 228), ("B", -13.0, -2.4, 0), "JST BM10B-SRSS-TB", "JST SH 10-way top entry; 50 mm cable to SM10B on the main PCB tab")
comp("C12", "Device:C", "10u", C0603, {"1": "+3V3", "2": "GND"}, (352, 228), ("B", -12.2, -6.4, 0), "0603 X5R 10 V", "Bulk at the link connector")
for h, (hx, hy) in enumerate(((-20.0, -9.0), (-20.0, 10.5), (20.0, -9.0), (20.0, 10.5))):     # same order as the template
    comp(f"H{h+1}", "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", {}, (28 + 16 * h, 252), ("F", hx, hy, 0), "", "M2 into the top-plate boss")

# PCB tuples are (side, x, y, rotation in degrees, CCW seen from the top). Encoders are anchored on the shaft centre.
NETS = sorted({n for c in C for n in c["pins"].values() if n})
