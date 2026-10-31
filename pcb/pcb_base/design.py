"""Base station carrier PCB: the single source of truth for the schematic and the board.

A carrier for the Waveshare ESP32-P4-NANO (Ethernet, PoE module option, USB-C), with the beltpack's LR2021 radio and
antenna-diversity switch on two rear SMA connectors, a DC input, the front-panel controls, and an optional NAU88C22 audio
section (local XLR-4 headset and a balanced 4-wire line in and out).

Board frame (mm): origin at the board centre, +X right, +Y toward the REAR panel, viewed from the top (F.Cu, where every
part sits). The board is 150 x 90 mm: x -75..75, y -45..45. The NANO plugs into two 2x13 sockets at the rear left with its
RJ45 flush with the rear edge.

pcb = (side, x, y, rotation) places a part exactly. near = (ref, pad, side) lets make_pcb.py put a small part next to that pad.
"""
R0603 = "Resistor_SMD:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder"
R1206 = "Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder"
C0603 = "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder"
C1206 = "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOD323 = "Diode_SMD:D_SOD-323_HandSoldering"
TVS = "Nexperia PESD5V0S1BA"
W, H = 150.0, 90.0                                   # board size
XR, YR = W / 2, H / 2

C = []
def comp(ref, lib_id, value, fp, pins, block, pcb=None, near=None, mpn="", desc="", dnp=False):
    C.append(dict(ref=ref, lib_id=lib_id, value=value, fp=fp, pins=pins, block=block, pcb=pcb, near=near, mpn=mpn, desc=desc, dnp=dnp))
def R(ref, val, a, b, block, near=None, pcb=None, fp=R0603, mpn="0603 1%", desc="", dnp=False):
    comp(ref, "Device:R", val, fp, {"1": a, "2": b}, block, pcb, near, mpn, desc, dnp)
def Cap(ref, val, a, b, block, near=None, pcb=None, fp=C0603, mpn="", desc="", dnp=False):
    if not mpn: mpn = "0603 X7R" if val.endswith(("n", "p")) else "0603 X5R 10 V"
    comp(ref, "Device:C", val, fp, {"1": a, "2": b}, block, pcb, near, mpn, desc, dnp)
def TP(ref, net, block, near=None, pcb=None):
    comp(ref, "Connector:TestPoint", net.strip("/+").replace("+", ""), "TestPoint:TestPoint_Pad_D1.0mm", {"1": net}, block, pcb, near, "", f"Test pad {net}")

# =============================================================== NANO: Waveshare ESP32-P4-NANO on two 2x13 sockets
# Header pin map from Waveshare's pinout (wiki, "Pinout Definition"); L = the header beside the speaker connector, R = beside the mic.
# Pins the NANO uses itself (SD card, its ES8311 codec, its amplifier, the ESP32-C6 link) are left unconnected here.
B = "NANO"
NANO_L = {1: "NANO_3V3", 2: "+5V", 3: "I2C_SDA", 4: "+5V", 5: "I2C_SCL", 6: "GND", 7: "LR_MISO", 8: None, 9: "GND", 10: None,
          11: "LR_BUSY", 12: "LR_DIO6", 13: "LR_NSS", 14: "GND", 15: "LR_SCK", 16: "LR_MOSI", 17: "NANO_3V3", 18: "ENC_A", 19: "ENC_B",
          20: "GND", 21: "EXP_INT_N", 22: "P4_IO27", 23: "LED_DIN", 24: "I2S_MCLK", 25: "GND", 26: None}
NANO_R = {1: "+5V", 2: None, 3: "GND", 4: "GND", 5: "NANO_3V3", 6: None, 7: "GND", 8: None, 9: "LR_NRESET", 10: "GND", 11: "RF_CTRL",
          12: "I2S_DIN", 13: None, 14: None, 15: "I2S_FS", 16: "I2S_DOUT", 17: "I2S_BCLK", 18: "GND", 19: None, 20: None, 21: None,
          22: None, 23: None, 24: None, 25: "GND", 26: "GND"}
nano = {f"L{k}": v for k, v in NANO_L.items()} | {f"R{k}": v for k, v in NANO_R.items()}
NX, NY = -41.5, YR - 1.64 - 25.0                     # NANO centre: its RJ45 (1.64 mm past its edge) flush with the rear edge
comp("U1", "OpenTheatreComms:ESP32-P4-NANO", "ESP32-P4-NANO", "OpenTheatreComms:ESP32-P4-NANO_Sockets", nano, B, pcb=("F", NX, NY, 180),
     mpn="Waveshare ESP32-P4-NANO (SKU 29026) on 2x 2x13 2.54 mm female sockets, 8.5 mm",
     desc="ESP32-P4 board: Ethernet (PoE module option), USB-C, Wi-Fi 6 co-processor. Plugs in RJ45-first toward the rear")
TP("TP1", "P4_IO27", B, near=("U1", "L22", "F"))
TP("TP2", "NANO_3V3", B, near=("U1", "L17", "F"))
R("R1", "4.7k", "+3V3", "I2C_SDA", B, near=("U1", "L3", "F"), desc="I2C pull-up: fit only if the NANO's own pull-ups are absent", dnp=True)
R("R2", "4.7k", "+3V3", "I2C_SCL", B, near=("U1", "L5", "F"), desc="I2C pull-up: fit only if the NANO's own pull-ups are absent", dnp=True)

# =============================================================== POWER: DC input buck to the NANO's 5 V rail, 3.3 V LDO
# The 5 V rail is the NANO's own VCC_5V. The NANO's USB-C feeds it through a reverse-blocking switch and its PoE module
# feeds it directly; the DC input adds a third source through D2, so whichever is plugged in powers everything.
B = "Power"
comp("J1", "Connector:Barrel_Jack_MountingPin", "DC 7-24 V", "Connector_BarrelJack:BarrelJack_CUI_PJ-063AH_Horizontal",
     {"1": "VIN_RAW", "2": "GND", "MP": "GND"}, B, pcb=("F", -8.0, "rear", 180), mpn="CUI PJ-063AH (5.5 x 2.1 mm, centre +)",
     desc="DC input, 7-24 V, centre positive. Optional: the NANO's USB-C or a PoE module also powers the station")
comp("D1", "Diode:SS34", "SS34", "Diode_SMD:D_SMA", {"2": "VIN_RAW", "1": "VIN"}, B, near=("J1", "1", "F"), mpn="SS34 (SMA)", desc="Reverse polarity protection")
comp("D3", "Device:D_TVS", "SMAJ26A", "Diode_SMD:D_SMA", {"1": "VIN", "2": "GND"}, B, near=("D1", "1", "F"), mpn="SMAJ26A", desc="Input surge clamp")
Cap("C1", "10u", "VIN", "GND", B, near=("U2", "3", "F"), fp=C1206, mpn="1206 X7R 50 V")
comp("U2", "Regulator_Switching:AP63205WU", "AP63205WU", "Package_TO_SOT_SMD:TSOT-23-6",
     {"3": "VIN", "2": "VIN", "4": "GND", "5": "BUCK_SW", "6": "BUCK_BST", "1": "BUCK_OUT"}, B, pcb=("F", -8.0, 25.0, 0),
     mpn="Diodes AP63205WU-7", desc="5 V, 2 A synchronous buck, 3.8-32 V in")
Cap("C2", "100n", "BUCK_BST", "BUCK_SW", B, near=("U2", "6", "F"))
comp("L1", "Device:L", "4.7u", "Inductor_SMD:L_Bourns-SRN4018", {"1": "BUCK_SW", "2": "BUCK_OUT"}, B, near=("U2", "5", "F"),
     mpn="4.7 uH, 2.5 A, 4x4 mm (Bourns SRN4018-4R7M or equal)")
Cap("C3", "22u", "BUCK_OUT", "GND", B, near=("L1", "2", "F"), fp=C1206, mpn="1206 X5R 10 V")
Cap("C4", "22u", "BUCK_OUT", "GND", B, near=("L1", "2", "F"), fp=C1206, mpn="1206 X5R 10 V")
comp("D2", "Diode:SS34", "SS34", "Diode_SMD:D_SMA", {"2": "BUCK_OUT", "1": "+5V"}, B, near=("L1", "2", "F"), mpn="SS34 (SMA)",
     desc="Joins the DC supply to the NANO's 5 V rail; blocks USB or PoE from back-feeding the buck")
Cap("C5", "22u", "+5V", "GND", B, near=("D2", "1", "F"), fp=C1206, mpn="1206 X5R 10 V")
comp("U3", "Regulator_Linear:TLV75733PDBV", "TLV75733", "Package_TO_SOT_SMD:SOT-23-5", {"1": "+5V", "2": "GND", "3": "+5V", "4": None, "5": "+3V3"}, B,
     pcb=("F", 35.0, 8.0, 0), mpn="TI TLV75733PDBVR", desc="3.3 V, 1 A LDO for the radio, codec and expander (separate from the NANO's own 3.3 V)")
Cap("C6", "1u", "+5V", "GND", B, near=("U3", "1", "F"))
Cap("C7", "10u", "+3V3", "GND", B, near=("U3", "5", "F"))
Cap("C8", "22u", "+3V3", "GND", B, near=("U3", "5", "F"), fp=C1206, mpn="1206 X5R 10 V")
comp("D4", "Device:LED", "green", "LED_SMD:LED_0603_1608Metric_Pad1.05x0.95mm_HandSolder", {"1": "PWR_LED_K", "2": "+3V3"}, B, near=("U3", "5", "F"),
     mpn="Lite-On LTST-C191KGKT", desc="Power light")
R("R3", "1k", "PWR_LED_K", "GND", B, near=("D4", "1", "F"))
for ref, net in (("TP3", "VIN"), ("TP4", "+5V"), ("TP5", "+3V3"), ("TP6", "GND")):
    TP(ref, net, B, near=("U3", "2", "F"))

# =============================================================== RADIO: LR2021 module, diversity switch, two rear SMAs, 2.4 GHz footprint
# Same circuit as the beltpack's main PCB, so both ends run the same radio firmware.
B = "Radio"
lr = {"1": "LR_VDD", "2": "LR_NSS_M", "3": "LR_SCK_M", "4": "LR_MOSI_M", "5": "LR_MISO_M", "6": "GND", "7": "LR_DIO6", "8": "LR_DIO5", "9": "LR_BUSY",
      "10": "LR_NRESET", "11": "RF_LF", "12": "GND", "13": "GND", "14": "GND", "15": "LR_TXRX_EN", "16": None, "17": "RF_HF",
      "18": "GND", "19": "GND", "20": "GND"}
comp("U4", "OpenTheatreComms:LR2021_Module_Elecrow", "LR2021", "OpenTheatreComms:LR2021_Elecrow_10x10mm", lr, B, pcb=("F", 53.0, 19.0, 90),
     mpn="Elecrow LR2021 module (LMM16121D)", desc="915-928 MHz FLRC radio; 2.4 GHz port for fallback")
for ref, a, b_, pin in (("R4", "LR_NSS", "LR_NSS_M", "2"), ("R5", "LR_SCK", "LR_SCK_M", "3"), ("R6", "LR_MOSI", "LR_MOSI_M", "4"), ("R7", "LR_MISO", "LR_MISO_M", "5")):
    R(ref, "470", a, b_, B, near=("U4", pin, "F"), desc="SPI series resistor (module guide)")
R("R8", "100k", "+3V3", "LR_NRESET", B, near=("U4", "10", "F"))
comp("FB1", "Device:FerriteBead_Small", "0R", "Inductor_SMD:L_0603_1608Metric_Pad1.05x0.95mm_HandSolder", {"1": "+3V3", "2": "LR_VDD"}, B,
     near=("U4", "1", "F"), mpn="0603 0R (or Murata BLM18PG121SN1D)", desc="Radio supply link: the module has its own ferrite")
Cap("C9", "47u", "LR_VDD", "GND", B, near=("U4", "1", "F"), fp=C1206, mpn="1206 X5R 6.3 V", desc="Module bulk (guide: 47u + 10u + 100n)")
Cap("C10", "10u", "LR_VDD", "GND", B, near=("U4", "1", "F"))
Cap("C11", "100n", "LR_VDD", "GND", B, near=("U4", "1", "F"))
Cap("C12", "DNP", "RF_LF", "GND", B, mpn="0603 C0G, tune", desc="Pi match shunt (module side), fit when tuning", dnp=True)
R("L2", "0", "RF_LF", "RF_LF_M", B, mpn="0603 0R or RF inductor", desc="Pi match series element: 0R until tuned")
Cap("C13", "DNP", "RF_LF_M", "GND", B, mpn="0603 C0G, tune", desc="Pi match shunt (switch side), fit when tuning", dnp=True)
Cap("C14", "100p", "RF_LF_M", "RF_SW_C", B, mpn="0603 C0G 50 V", desc="DC block (switch RFC)")
comp("U5", "OpenTheatreComms:PE4259", "PE4259", "Package_TO_SOT_SMD:SOT-363_SC-70-6",
     {"5": "RF_SW_C", "4": "RF_CTRL_S", "6": "RF_SW_VDD", "1": "RF_SW_1", "3": "RF_SW_2", "2": "GND"}, B,
     mpn="pSemi PE4259-63", desc="Antenna diversity switch, RF1 = antenna A when CTRL is high")
R("R9", "1k", "RF_CTRL", "RF_CTRL_S", B, near=("U5", "4", "F"))
R("R10", "1k", "+3V3", "RF_SW_VDD", B, near=("U5", "6", "F"))
Cap("C15", "100n", "RF_SW_VDD", "GND", B, near=("U5", "6", "F"))
Cap("C16", "100p", "RF_SW_1", "RF_ANT_A", B, mpn="0603 C0G 50 V", desc="DC block (RF1)")
Cap("C17", "100p", "RF_SW_2", "RF_ANT_B", B, mpn="0603 C0G 50 V", desc="DC block (RF2)")
comp("J2", "Connector:Conn_Coaxial", "Antenna A", "Connector_Coaxial:SMA_Molex_73251-2120_EdgeMount_Horizontal", {"1": "RF_ANT_A", "2": "GND"}, B,
     pcb=("F", 62.0, "rear", 180), mpn="Molex 73251-2120 SMA edge-mount jack, 1.6 mm board", desc="Antenna A (915 MHz whip)")
comp("J3", "Connector:Conn_Coaxial", "Antenna B", "Connector_Coaxial:SMA_Molex_73251-2120_EdgeMount_Horizontal", {"1": "RF_ANT_B", "2": "GND"}, B,
     pcb=("F", 44.0, "rear", 180), mpn="Molex 73251-2120 SMA edge-mount jack, 1.6 mm board", desc="Antenna B (915 MHz whip)")
R("L3", "0", "RF_HF", "RF_HF_M", B, mpn="0603 0R or RF inductor", desc="2.4 GHz match series element", dnp=True)
Cap("C18", "DNP", "RF_HF_M", "GND", B, mpn="0603 C0G, tune", desc="2.4 GHz match shunt", dnp=True)
comp("J4", "Connector:Conn_Coaxial", "2.4 GHz", "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", {"1": "RF_HF_M", "2": "GND"}, B,
     mpn="Hirose U.FL-R-SMT-1(10)", desc="2.4 GHz fallback antenna: footprint only in v1", dnp=True)

# =============================================================== UI: OLED header, encoder, talk keys, RGB status lights, IO expander
B = "UI"
tca = {"~{INT}": "EXP_INT_N", "A0": "+3V3", "A1": "GND", "A2": "GND", "SCL": "I2C_SCL", "SDA": "I2C_SDA", "VCC": "+3V3", "GND": "GND",
       "P00": "KEY1", "P01": "KEY2", "P02": "KEY3", "P03": "KEY4", "P04": "KEY_MENU", "P05": "KEY_BACK", "P06": "ENC_SW", "P07": "HS_DET",
       "P10": "LR_DIO5", "P11": "LR_TXRX_EN", "P12": None, "P13": None, "P14": None, "P15": None, "P16": None, "P17": None}
comp("U6", "Interface_Expansion:TCA9555PWR", "TCA9555PWR", "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm", tca, B, pcb=("F", 30.0, -3.0, 0),
     mpn="TI TCA9555PWR", desc="IO expander at 0x21 (A0 high): keys, encoder push, headset sense, radio DIO5 and TX/RX enable")
Cap("C19", "100n", "+3V3", "GND", B, near=("U6", "24", "F"))
R("R11", "10k", "+3V3", "EXP_INT_N", B, near=("U6", "1", "F"))
comp("J5", "Connector_Generic:Conn_01x04", "OLED", "Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical",
     {"1": "GND", "2": "+3V3", "3": "I2C_SCL", "4": "I2C_SDA"}, B, pcb=("F", -50.0, -12.0, 90),
     mpn="1x4 female socket for a 1.3 in 128x64 I2C OLED module (SH1106, address 0x3C)",
     desc="OLED module socket: GND, VCC, SCL, SDA (check your module's pin order)")
Cap("C20", "10u", "+3V3", "GND", B, near=("J5", "2", "F"))
keys = (("SW1", "KEY1", 10.0, "Talk 1"), ("SW2", "KEY2", 26.5, "Talk 2"), ("SW3", "KEY3", 43.0, "Talk 3"), ("SW4", "KEY4", 59.5, "Talk 4"))
for ref, net, x, d in keys:
    comp(ref, "Switch:SW_Push", d, "Button_Switch_THT:SW_PUSH-12mm", {"1": "GND", "2": net}, B, pcb=("F", x, -35.0, "centre"),
         mpn="12 x 12 mm tactile switch with round cap", desc=f"{d} key (channel {d[-1]})")
comp("SW5", "Switch:SW_Push", "Menu", "Button_Switch_THT:SW_PUSH_6mm", {"1": "GND", "2": "KEY_MENU"}, B, pcb=("F", -25.0, -26.0, "centre"),
     mpn="6 x 6 mm tactile switch, 13 mm tall", desc="Menu key")
comp("SW6", "Switch:SW_Push", "Back", "Button_Switch_THT:SW_PUSH_6mm", {"1": "GND", "2": "KEY_BACK"}, B, pcb=("F", -25.0, -38.0, "centre"),
     mpn="6 x 6 mm tactile switch, 13 mm tall", desc="Back key")
comp("ENC1", "Device:RotaryEncoder_Switch", "EC11", "Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm",
     {"A": "ENC_A", "B": "ENC_B", "C": "GND", "S1": "ENC_SW", "S2": "GND"}, B, pcb=("F", -10.0, -33.0, "centre"),
     mpn="EC11 encoder with push switch, 20 mm shaft", desc="Menu dial")
for ref, net in (("R12", "ENC_A"), ("R13", "ENC_B")):
    R(ref, "10k", "+3V3", net, B, near=("ENC1", net[-1], "F"))
    Cap("C" + str(21 + int(ref[-1]) - 2), "10n", net, "GND", B, near=("ENC1", net[-1], "F"), desc="Encoder debounce")
# RGB status lights: 4 channel lights above the talk keys, then 8 beltpack lights in a row; one data line, 5 V supply
comp("U7", "74xGxx:74AHCT1G125", "74AHCT1G125", "Package_TO_SOT_SMD:SOT-23-5", {"1": "GND", "2": "LED_DIN", "3": "GND", "4": "LED_D0", "5": "+5V"}, B,
     pcb=("F", 0.0, -16.0, 0), mpn="74AHCT1G125 (SOT-23-5)", desc="3.3 V to 5 V level shift for the LED data line")
Cap("C25", "100n", "+5V", "GND", B, near=("U7", "5", "F"))
R("R14", "33", "LED_D0", "LED_D1", B, near=("U7", "4", "F"), desc="LED data series resistor")
LEDS = [(f"LED{i + 1}", x, -24.0, f"Channel {i + 1}") for i, x in enumerate((10.0, 26.5, 43.0, 59.5))] + \
       [(f"LED{i + 5}", 10.0 + i * 8.0, -14.0, f"Beltpack {i + 1}") for i in range(8)]
for i, (ref, x, y, d) in enumerate(LEDS):
    comp(ref, "LED:WS2812B", "WS2812B-Mini", "OpenTheatreComms:LED_WS2812B-Mini-V3J_3.5x3.5mm",
         {"4": f"LED_D{i + 1}", "2": f"LED_D{i + 2}" if i < len(LEDS) - 1 else None, "1": "+5V", "3": "GND"}, B, pcb=("F", x, y, 180),
         mpn="Worldsemi WS2812B-Mini-V3J", desc=f"{d} light, under a light pipe")
    Cap(f"C{26 + i}", "100n", "+5V", "GND", B, near=(ref, "1", "F"))

# =============================================================== AUDIO (optional): codec, local XLR-4 headset, 4-wire line in and out
# Fit only if wanted: everything in this block is a normal part, but the station works without it.
B = "Audio"
cod = {"1": "MICL_P", "2": "MICL_N", "3": None, "4": "LINE_IN_P", "5": "LINE_IN_N", "6": None, "7": "I2S_FS", "8": "I2S_BCLK", "9": "I2S_DIN",
       "10": "I2S_DOUT", "11": "I2S_MCLK", "12": "GND", "13": "+3V3", "14": "+3V3", "15": "GND", "16": "I2C_SCL", "17": "I2C_SDA", "18": "GND",
       "19": None, "20": None, "21": None, "22": None, "23": "SPK_P", "24": "GND", "25": "SPK_N", "26": "+3V3", "27": "COD_VREF", "28": "GND",
       "29": "LINE_OUT_P", "30": "LINE_OUT_N", "31": "VDDA_COD", "32": "MICBIAS", "33": "GND"}
comp("U8", "OpenTheatreComms:NAU88C22", "NAU88C22", "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm_ThermalVias", cod, B,
     pcb=("F", 15.0, 6.0, 0), mpn="Nuvoton NAU88C22YG",
     desc="Codec, I2C 0x1A, MODE low = 2-wire. Headset mic left, 4-wire in right (differential), earpiece on the BTL speaker pair, 4-wire out on the headphone pair (BTL)")
comp("FB2", "Device:FerriteBead_Small", "600R", "Inductor_SMD:L_0603_1608Metric_Pad1.05x0.95mm_HandSolder", {"1": "+3V3", "2": "VDDA_COD"}, B,
     near=("U8", "31", "F"), mpn="600R 0603 ferrite bead (Sunlord GZ1608D601TF or equal)")
Cap("C38", "10u", "VDDA_COD", "GND", B, near=("U8", "31", "F"))
Cap("C39", "100n", "VDDA_COD", "GND", B, near=("U8", "31", "F"))
Cap("C40", "4.7u", "+3V3", "GND", B, near=("U8", "13", "F"), desc="Codec VDDC/VDDB bulk (datasheet: 4.7u + 0.1u per supply)")
Cap("C41", "100n", "+3V3", "GND", B, near=("U8", "14", "F"))
Cap("C42", "10u", "+3V3", "GND", B, near=("U8", "26", "F"))
Cap("C43", "100n", "+3V3", "GND", B, near=("U8", "26", "F"))
Cap("C44", "4.7u", "COD_VREF", "GND", B, near=("U8", "27", "F"))
Cap("C45", "4.7u", "MICBIAS", "GND", B, near=("U8", "32", "F"), desc="MICBIAS filter (datasheet: 4.7u)")
# local headset, XLR-4 male on the front panel, Clear-Com wiring: 1 mic common, 2 mic +, 3 earpiece -, 4 earpiece +; pad 5 = shell
comp("J6", "Connector_Generic:Conn_01x05", "Headset XLR-4", "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
     {"1": "GND", "2": "XLR_MIC", "3": "XLR_EAR_N", "4": "XLR_EAR_P", "5": "GND"}, B, pcb=("F", -72.5, -20.0, 0),
     mpn="Neutrik NC4MD-L-1 (panel, wired)", desc="Wire pads for the front-panel XLR-4 male: 1 mic common, 2 mic +, 3 ear -, 4 ear +, 5 shell")
for ref, net, pin in (("D5", "XLR_MIC", "2"), ("D6", "XLR_EAR_N", "3"), ("D7", "XLR_EAR_P", "4")):
    comp(ref, "Device:D_TVS", "PESD5V0S1BA", SOD323, {"1": net, "2": "GND"}, B, near=("J6", pin, "F"), mpn=TVS, desc="Headset ESD")
Cap("C46", "1u", "XLR_MIC", "MICL_N", B, near=("U8", "2", "F"), desc="Headset mic AC coupling")
Cap("C47", "1u", "MICL_P", "GND", B, near=("U8", "1", "F"), desc="Pseudo-differential reference")
R("R15", "0", "XLR_MIC", "HS_DET", B, near=("J6", "2", "F"), dnp=True, desc="Headset sense (unfitted): reads the mic line through R16")
R("R16", "100k", "+3V3", "HS_DET", B, near=("U6", "11", "F"), desc="Headset sense pull-up")
R("R17", "0", "SPK_P", "XLR_EAR_P", B, near=("U8", "23", "F"), fp=R1206, mpn="1206 0R", desc="BTL link (or a 100u 1206 cap for single-ended)")
R("R18", "0", "SPK_N", "XLR_EAR_N", B, near=("U8", "25", "F"), desc="BTL link (remove for single-ended)")
R("R19", "0", "XLR_EAR_N", "GND", B, near=("J6", "3", "F"), desc="Single-ended option: earpiece - to ground", dnp=True)
# 4-wire: balanced line in (XLR-3 female) into the right mic pair, balanced line out (XLR-3 male) from the headphone pair (BTL)
comp("J7", "Connector_Generic:Conn_01x03", "4-wire in", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     {"1": "GND", "2": "FW_IN_P", "3": "FW_IN_N"}, B, pcb=("F", 10.0, 41.5, 90),
     mpn="Neutrik NC3FD-L-1 (panel, wired)", desc="Wire pads for the rear XLR-3 female 4-wire input: 1 ground, 2 hot, 3 cold")
comp("J8", "Connector_Generic:Conn_01x03", "4-wire out", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     {"1": "GND", "2": "FW_OUT_P", "3": "FW_OUT_N"}, B, pcb=("F", 22.0, 41.5, 90),
     mpn="Neutrik NC3MD-L-1 (panel, wired)", desc="Wire pads for the rear XLR-3 male 4-wire output: 1 ground, 2 hot, 3 cold")
for ref, net, j, pin in (("D8", "FW_IN_P", "J7", "2"), ("D9", "FW_IN_N", "J7", "3"), ("D10", "FW_OUT_P", "J8", "2"), ("D11", "FW_OUT_N", "J8", "3")):
    comp(ref, "Device:D_TVS", "PESD5V0S1BA", SOD323, {"1": net, "2": "GND"}, B, near=(j, pin, "F"), mpn=TVS, desc="4-wire ESD")
R("R20", "10k", "FW_IN_P", "FW_IN_PR", B, near=("J7", "2", "F"), desc="Line input pad: with R22, about 12 dB down for +4 dBu lines")
R("R21", "10k", "FW_IN_N", "FW_IN_NR", B, near=("J7", "3", "F"))
R("R22", "4.7k", "FW_IN_PR", "FW_IN_NR", B, near=("J7", "2", "F"), desc="Line input pad shunt (fit 0R in R20/R21 and remove this for low-level sources)")
Cap("C48", "1u", "FW_IN_PR", "LINE_IN_P", B, near=("U8", "4", "F"), desc="4-wire input AC coupling")
Cap("C49", "1u", "FW_IN_NR", "LINE_IN_N", B, near=("U8", "5", "F"), desc="4-wire input AC coupling")
Cap("C50", "10u", "LINE_OUT_P", "FW_OUT_PR", B, near=("U8", "29", "F"), desc="4-wire output DC block")
Cap("C51", "10u", "LINE_OUT_N", "FW_OUT_NR", B, near=("U8", "30", "F"), desc="4-wire output DC block")
R("R23", "100", "FW_OUT_PR", "FW_OUT_P", B, near=("J8", "2", "F"), desc="Output build-out resistor")
R("R24", "100", "FW_OUT_NR", "FW_OUT_N", B, near=("J8", "3", "F"), desc="Output build-out resistor")
R("R25", "10k", "FW_OUT_P", "GND", B, near=("J8", "2", "F"), desc="Pop bleed")
R("R26", "10k", "FW_OUT_N", "GND", B, near=("J8", "3", "F"), desc="Pop bleed")

# =============================================================== mounting: four M3 corner holes
for h, (hx, hy) in (("H1", (-XR + 3.5, -YR + 3.5)), ("H2", (XR - 3.5, -YR + 3.5)), ("H3", (-XR + 3.5, YR - 3.5)), ("H4", (XR - 3.5, YR - 3.5))):
    comp(h, "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", {}, "Power", pcb=("F", hx, hy, 0), desc="M3 into a heat-set insert")

BLOCKS = [("NANO", "Waveshare ESP32-P4-NANO on two 2x13 sockets: Ethernet with a PoE module option, USB-C, Wi-Fi 6. Pins it uses itself are left open"),
          ("Power", "DC input (7-24 V) through a 5 V buck into the NANO's 5 V rail (USB-C or PoE also work), 3.3 V LDO for the carrier, mounting holes"),
          ("Radio", "LR2021 module, 915 MHz pi match, PE4259 antenna diversity switch, two rear SMA jacks; 2.4 GHz port as a footprint only"),
          ("UI", "IO expander (0x21), OLED socket, menu dial, four talk keys, Menu and Back keys, 12 RGB status lights on one data line"),
          ("Audio", "Optional NAU88C22 codec: front XLR-4 headset (BTL earpiece), rear balanced 4-wire line in and out")]
NETS = sorted({n for c in C for n in c["pins"].values() if n})
