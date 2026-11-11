"""Top PCB circuit: the single source of truth for the schematic and the board.

Board frame (mm): origin at the board centre, +X right, +Y toward the hip (back) edge, viewed from above (F = top side).
Schematic positions are on an A3 sheet (mm, Y down).
"""
R0603 = "Resistor_SMD:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder"
C0603 = "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder"
RGB = "LED_SMD:LED_LiteOn_LTST-C19HE1WT"

# Which LP5024 RGB channel (LEDk = OUT3k..OUT3k+2) drives each light, chosen so every light's lines leave the driver on the
# side facing it: D1..D4 are the talk keys 1-4, D5 / D6 the left / right status lights.
LED_CH = {"D1": 0, "D2": 1, "D5": 2, "D3": 3, "D4": 4, "D6": 5}
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
    k = LED_CH[f"D{n}"]
    comp(f"D{n}", "Device:LED_RGBA", "RGB", RGB, {"1": f"L{k}_R", "2": f"L{k}_G", "3": f"L{k}_B", "4": "+3V3"},
         (sx, 68), ("F", x, y - off, 180), "Lite-On LTST-C19HE1WT", f"Key {n} light (LP5024 LED{k})")
# ---------------------------------------------------------------- status lights: one RGB LED under each light pipe
for j, (x, y) in enumerate(STATUS):
    side = "L" if x < 0 else "R"; k = LED_CH[f"D{5 + j}"]
    comp(f"D{5 + j}", "Device:LED_RGBA", "RGB", RGB, {"1": f"L{k}_R", "2": f"L{k}_G", "3": f"L{k}_B", "4": "+3V3"},
         (200 + j * 40, 68), ("F", x * 45.8 / 46.5, y, 0), "Lite-On LTST-C19HE1WT", f"Status light {side} (LP5024 LED{k})")
# ---------------------------------------------------------------- RGB LED driver: TI LP5024 on the board's I2C, address 0x28 (ADDR1 = ADDR0 = GND)
# OUT[3k], OUT[3k+1], OUT[3k+2] = LEDk red, green, blue (TI's recommended order for the LEDk_BRIGHTNESS registers).
# Full-scale current 105 x 0.7 V / R1 = 4.9 mA per colour with 15k: plenty behind a light pipe, and it leaves the blue and
# green chips' forward voltage (about 2.7 V at 5 mA) headroom on the 3.3 V anode supply. Its I2C broadcast address is 0x3C,
# so the OLED moves to 0x3D (SA0 high).
lp = {"27": "+3V3", "30": "LED_EN", "29": "SCL", "28": "SDA", "25": "GND", "26": "GND", "31": "IREF_LED", "32": "VCAP_LED", "33": "GND"}
for k in range(6):
    for m, col in enumerate("RGB"): lp[str(3 * k + m + 1)] = f"L{k}_{col}"
lp.update({str(n): None for n in range(19, 25)})                     # OUT18-OUT23 unused
comp("U2", "OpenTheatreComms:LP5024", "LP5024RSMR", "Package_DFN_QFN:VQFN-32-1EP_4x4mm_P0.4mm_EP2.8x2.8mm", lp,
     (300, 165), ("B", 25.5, -1.0, 0), "TI LP5024RSMR", "24-channel I2C RGB LED driver, 0x28: six RGB LEDs; EN from the expander (P05, high by its pull-up at power-up)")
comp("R1", "Device:R", "15k", R0603, {"1": "IREF_LED", "2": "GND"}, (330, 150), ("B", 22.6, -6.0, 180), "0603 1%", "LP5024 full-scale current, 4.9 mA")
comp("C13", "Device:C", "1u", C0603, {"1": "VCAP_LED", "2": "GND"}, (330, 170), ("B", 22.4, -4.4, 180), "0603 X5R", "LP5024 internal LDO cap")
comp("C14", "Device:C", "1u", C0603, {"1": "+3V3", "2": "GND"}, (330, 190), ("B", 27.4, -4.8, 0), "0603 X5R", "LP5024 supply")
# ---------------------------------------------------------------- IO expander
tca = {"~{INT}": "INT_N", "A0": "GND", "A1": "GND", "A2": "GND", "SCL": "SCL", "SDA": "SDA", "VCC": "+3V3", "GND": "GND",
       "P00": "KEY1", "P01": "KEY2", "P02": "KEY3", "P03": "KEY4", "P04": "OLED_RES_N", "P05": "LED_EN", "P06": None, "P07": None,
       "P10": None, "P11": None, "P12": None, "P13": None, "P14": None, "P15": None, "P16": None, "P17": None}
comp("U1", "Interface_Expansion:TCA9555PWR", "TCA9555PWR", "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm", tca,
     (85, 165), ("B", 0.0, -4.6, 90), "TI TCA9555PWR", "16-bit I2C IO expander, 0x20, internal 100k pull-ups")
comp("C1", "Device:C", "100n", C0603, {"1": "+3V3", "2": "GND"}, (120, 142), ("B", 5.6, -3.4, 90), "0603 X7R 50 V", "U1 decoupling")
comp("R9", "Device:R", "10k", R0603, {"1": "+3V3", "2": "INT_N"}, (22, 128), ("B", -12.2, -8.2, 0), "0603 1%", "INT pull-up")
comp("R10", "Device:R", "4.7k", R0603, {"1": "+3V3", "2": "SDA"}, (34, 128), ("B", -8.6, -6.4, 0), "0603 1%", "I2C pull-up")
comp("R11", "Device:R", "4.7k", R0603, {"1": "+3V3", "2": "SCL"}, (46, 128), ("B", -8.6, -8.2, 0), "0603 1%", "I2C pull-up")
# ---------------------------------------------------------------- OLED (1.3in 128x64 30-pin panel, SH1106, I2C, 0.7 mm solder tail)
oled = {1: "GND", 2: "C2P", 3: "C2N", 4: "C1P", 5: "C1N", 6: "+3V3", 7: None, 8: "GND", 9: "+3V3", 10: "GND", 11: "+3V3",
        12: "GND", 13: "GND", 14: "OLED_RES_N", 15: "+3V3", 16: "GND", 17: "GND", 18: "SCL", 19: "SDA", 20: "SDA",
        21: "GND", 22: "GND", 23: "GND", 24: "GND", 25: "GND", 26: "IREF", 27: "VCOMH", 28: "VCC_OLED", 29: "GND", 30: "GND"}
# The panel tail leaves the glass toward the back edge and folds round the notch, which keeps every contact at the same X,
# and is soldered flat onto 30 pads on B (0.7 mm pitch, lib/OpenTheatreComms.pretty, written by make_lib.py). Pad 1 is at -X. With the panel's pin 1 at +X (on the left when the
# panel is viewed face up with the tail toward you), panel pin k lands on pad 31 - k. Set False if your panel is the other way.
OLED_PIN1_AT_PLUS_X = True
def oled_pad(k): return 31 - k if OLED_PIN1_AT_PLUS_X else k
comp("J2", "Connector_Generic:Conn_01x30", "OLED tail", "OpenTheatreComms:OLED_Tail_30P_0.7mm_Solder",
     {str(oled_pad(k)): v for k, v in oled.items()}, (192, 165), ("B", 0.0, 5.5, 0), "OLED panel tail soldered to pads (no part)",
     "Solder pads for the panel's 30-lead tail (0.7 mm pitch). Standard 1.3 in SH1106 30-pin pin map; I2C (BS2..0 = 010), address 0x3D (SA0 = D/C# high: 0x3C is the LP5024 broadcast)")
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
comp("C12", "Device:C", "10u", C0603, {"1": "+3V3", "2": "GND"}, (352, 228), ("B", -17.0, 1.0, 180), "0603 X5R 10 V", "Bulk at the link connector, wired straight to its pins 1 and 2")
for h, (hx, hy) in enumerate(((-20.0, -9.0), (-20.0, 10.5), (20.0, -9.0), (20.0, 10.5))):     # same order as the template
    comp(f"H{h+1}", "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", {}, (28 + 16 * h, 252), ("F", hx, hy, 0), "", "M2 into the top-plate boss")

# PCB tuples are (side, x, y, rotation in degrees, CCW seen from the top). Encoders are anchored on the shaft centre.
NETS = sorted({n for c in C for n in c["pins"].values() if n})
