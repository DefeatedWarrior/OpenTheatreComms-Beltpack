"""Main PCB circuit: the single source of truth for the schematic and the board.

Board frame (mm): origin at the case centre, +X right, +Y up, viewed from the FRONT (F.Cu = front face, toward the buttons).
The back face (B.Cu) carries the ESP32-S3, the radio, the codec and the pogo pins and faces the battery pack.

pcb = (side, x, y, rotation) places a part exactly. near = (ref, pad, side) lets make_pcb.py put a small part next to that pad.
"""
R0603 = "Resistor_SMD:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder"
R1206 = "Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder"
C0603 = "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder"
C1206 = "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOD323 = "Diode_SMD:D_SOD-323_HandSoldering"
TVS = "Nexperia PESD5V0S1BA"

C = []
def comp(ref, lib_id, value, fp, pins, block, pcb=None, near=None, mpn="", desc="", dnp=False):
    C.append(dict(ref=ref, lib_id=lib_id, value=value, fp=fp, pins=pins, block=block, pcb=pcb, near=near, mpn=mpn, desc=desc, dnp=dnp))
def R(ref, val, a, b, block, near=None, pcb=None, fp=R0603, mpn="0603 1%", desc="", dnp=False):
    comp(ref, "Device:R", val, fp, {"1": a, "2": b}, block, pcb, near, mpn, desc, dnp)
def Cap(ref, val, a, b, block, near=None, pcb=None, fp=C0603, mpn="", desc="", dnp=False):
    if not mpn: mpn = "0603 X7R" if val.endswith(("n", "p")) or val in ("100n",) else "0603 X5R 10 V"
    comp(ref, "Device:C", val, fp, {"1": a, "2": b}, block, pcb, near, mpn, desc, dnp)
def TP(ref, net, block, near=None, pcb=None):
    comp(ref, "Connector:TestPoint", net.strip("/+").replace("+", ""), "TestPoint:TestPoint_Pad_D1.0mm", {"1": net}, block, pcb, near, "", f"Test pad {net}")

# =============================================================== POWER: USB-C, charger, power path, LDO, soft power, fuel gauge
B = "Power"
usb = {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
       "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN", "A8": None, "B8": None, "S1": "GND"}
comp("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", usb, B,
     pcb=("F", 9.0, "edge", 0), mpn="GCT USB4105-GF-A", desc="USB 2.0 Type-C receptacle: charging, firmware and USB serial")
R("R1", "5.1k", "CC1", "GND", B, near=("J1", "A5", "F"), desc="Sink pull-down (5 V default)")
R("R2", "5.1k", "CC2", "GND", B, near=("J1", "B5", "F"), desc="Sink pull-down (5 V default)")
comp("U1", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
     {"1": "USB_DN", "6": "USB_DN", "3": "USB_DP", "4": "USB_DP", "5": "VBUS", "2": "GND"}, B, near=("J1", "A6", "F"),
     mpn="ST USBLC6-2SC6", desc="USB data and VBUS ESD")
comp("U2", "OpenTheatreComms:TP4056", "TP4056", "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm_ThermalVias",
     {"4": "VBUS", "8": "VBUS", "1": "CHG_TEMP", "2": "CHG_PROG", "5": "BAT", "7": "CHG_CHRG_N", "6": "CHG_STDBY_N", "3": "GND", "9": "GND"}, B,
     pcb=("B", 16.0, -26.0, 0), mpn="TOPPOWER TP4056 (ESOP-8)", desc="Li-ion charger, about 800 mA with R3 = 1.5k")
R("R3", "1.5k", "CHG_PROG", "GND", B, near=("U2", "2", "B"), desc="Charge current: about 1200/R3 A (1.5k = 800 mA; 2.4k = 500 mA)")
R("R4", "6.2k", "VBUS", "CHG_TEMP", B, near=("U2", "1", "B"), desc="NTC divider top: charging allowed from about 2 to 44 C with a 10k B3435 pack NTC")
R("R5", "0", "CHG_TEMP", "GND", B, near=("U2", "1", "B"), desc="Fit only if the pack has no NTC (disables the temperature check)", dnp=True)
Cap("C1", "10u", "VBUS", "GND", B, near=("U2", "4", "B"))
Cap("C2", "10u", "BAT", "GND", B, near=("U2", "5", "B"))
comp("D1", "Diode:SS14", "SS14", "Diode_SMD:D_SMA", {"2": "VBUS", "1": "SYS"}, B, near=("U2", "4", "B"), mpn="SS14 (SMA)",
     desc="Power path: USB feeds the system while the charger fills the cell")
comp("Q1", "Transistor_FET:AO3401A", "AO3401A", SOT23, {"1": "VBUS", "3": "BAT", "2": "SYS"}, B, near=("U2", "5", "B"), mpn="AOS AO3401A",
     desc="Power path: battery to system when USB is absent (gate held at VBUS when present)")
R("R6", "100k", "VBUS", "GND", B, near=("Q1", "1", "B"), desc="Pulls the power-path gate low when USB is unplugged")
Cap("C3", "22u", "SYS", "GND", B, near=("D1", "1", "B"), fp=C1206, mpn="1206 X5R 10 V")
comp("U3", "Regulator_Linear:TLV75733PDBV", "TLV75733", "Package_TO_SOT_SMD:SOT-23-5", {"1": "SYS", "2": "GND", "3": "PWR_EN", "4": None, "5": "+3V3"}, B,
     pcb=("B", -2.5, -31.0, 0), mpn="TI TLV75733PDBVR", desc="3.3 V, 1 A LDO; EN is the soft power switch")
Cap("C4", "1u", "SYS", "GND", B, near=("U3", "1", "B"))
Cap("C5", "10u", "+3V3", "GND", B, near=("U3", "5", "B"))
Cap("C6", "22u", "+3V3", "GND", B, near=("U3", "5", "B"), fp=C1206, mpn="1206 X5R 10 V")
# soft power: the button lifts EN, the ESP32 holds it, and the button is also read through Q2
comp("SW1", "Switch:SW_Push", "Power", "Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010", {"1": "SYS", "2": "PWR_BTN"}, B,
     pcb=("F", -3.0, "edge", 0), mpn="Alps SKRTLAE010", desc="Side-push power button on the bottom edge: hold to switch on or off, tap for the flashlight")
comp("D2", "Device:D_Schottky", "BAT54WS", SOD323, {"2": "PWR_BTN", "1": "PWR_EN"}, B, near=("U3", "3", "B"), mpn="Diodes BAT54WS")
comp("D3", "Device:D_Schottky", "BAT54WS", SOD323, {"2": "PWR_HOLD", "1": "PWR_EN"}, B, near=("U3", "3", "B"), mpn="Diodes BAT54WS")
R("R7", "100k", "PWR_EN", "GND", B, near=("U3", "3", "B"))
R("R8", "100k", "PWR_BTN", "GND", B, near=("SW1", "2", "F"))
comp("Q2", "Transistor_FET:BSS138", "BSS138", SOT23, {"1": "PWR_BTN", "2": "GND", "3": "PWR_BTN_N"}, B, near=("SW1", "2", "F"), mpn="onsemi BSS138",
     desc="Reads the power button (low when pressed)")
R("R9", "10k", "PWR_HOLD", "GND", B, near=("D3", "2", "B"), desc="Keeps the LDO off until the firmware asserts PWR_HOLD")
comp("U4", "OpenTheatreComms:MAX17048", "MAX17048", "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm",
     {"3": "BAT", "2": "BAT", "1": "GND", "6": "GND", "8": "I2C_SDA", "7": "I2C_SCL", "5": "FG_ALRT_N", "4": "GND", "9": "GND"}, B,
     pcb=("B", 12.0, -20.0, 0), mpn="Analog MAX17048G+T10", desc="Battery fuel gauge on the cell directly, I2C 0x36")
Cap("C7", "100n", "BAT", "GND", B, near=("U4", "3", "B"))
for ref, net, x, d in (("J8", "BAT", 6.0, "Battery +"), ("J9", "CHG_TEMP", 12.0, "Pack NTC"), ("J10", "GND", 18.0, "Battery -")):
    comp(ref, "Connector_Generic:Conn_01x01", d, "OpenTheatreComms:MillMax_0906_SpringPin", {"1": net}, B, pcb=("B", x, -15.0, 0),
         mpn="Xinyangze YZ08415060P-02", desc=f"Spring pin onto the pack pad board (4.5 mm free, 4.0 working, 3.7 fully in; 0.8 mm tail): {d}")
comp("J11", "Connector_Generic:Conn_01x02", "Battery (JST XH)", "Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical", {"1": "BAT", "2": "GND"}, B,
     pcb=("F", 18.5, -11.0, 0), mpn="JST B2B-XH-A(LF)(SN)",
     desc="Battery input in parallel with the spring pins (pin 1 +). A cell here has no NTC: fit R5 to turn the charger's temperature check off")
comp("J12", "Connector_Generic_MountingPin:Conn_01x04_MountingPin", "Dock", "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal",
     {"1": "DOCK_VBUS", "2": "USB_DP", "3": "USB_DN", "4": "GND", "MP": "GND"}, B, pcb=("B", 26.5, -31.5, 180), mpn="JST SM04B-SRSS-TB(LF)(SN)",
     desc="Dock: cable to the contact board in the case bottom (1 VBUS, 2 D+, 3 D-, 4 GND)")
comp("D12", "Device:D_Schottky", "B5819W", "Diode_SMD:D_SOD-123", {"1": "VBUS", "2": "DOCK_VBUS"}, B, pcb=("B", 28.0, -25.0, 270),
     mpn="B5819W (SOD-123)", desc="Dock power into VBUS; keeps USB-C's 5 V off the exposed dock contacts")
R("R10", "33k", "VBUS", "VBUS_DET", B, near=("U2", "4", "B"))
R("R11", "100k", "VBUS_DET", "GND", B, near=("U2", "4", "B"))
for ref, net in (("TP1", "VBUS"), ("TP2", "SYS"), ("TP3", "BAT"), ("TP4", "+3V3"), ("TP5", "GND")):
    TP(ref, net, B, near=("U2", "5", "B") if net in ("VBUS", "SYS", "BAT") else ("U3", "5", "B"))

# =============================================================== MCU: ESP32-S3-WROOM-1-N8R8
B = "MCU"
esp = {"1": "GND", "40": "GND", "41": "GND", "2": "+3V3", "3": "ESP_EN",
       "4": "I2S_BCLK", "5": "I2S_FS", "6": "I2S_DOUT", "7": "I2S_DIN", "8": "I2S_MCLK", "9": "INT_N", "10": "PWR_HOLD", "11": "VIB_EN",
       "12": "I2C_SDA", "17": "I2C_SCL", "13": "USB_DN", "14": "USB_DP", "15": None, "16": None, "18": "LR_NSS", "19": "LR_MOSI", "20": "LR_SCK",
       "21": "LR_MISO", "22": "LR_BUSY", "23": "LR_DIO6", "24": "LR_NRESET", "25": "RF_CTRL", "26": None, "27": "ESP_IO0", "28": None, "29": None,
       "30": None, "31": "ENC_L_A", "32": "ENC_L_B", "33": "ENC_R_A", "34": "ENC_R_B", "35": "LAMP_EN", "36": "UART_RX", "37": "UART_TX",
       "38": None, "39": "JACK_SENSE"}
comp("U5", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N8R8", "RF_Module:ESP32-S3-WROOM-1", esp, B, pcb=("B", -33.25, 5.0, "antenna_left"),
     mpn="Espressif ESP32-S3-WROOM-1-N8R8", desc="MCU: Opus, radio timing, UI. Antenna end over the no-copper strip")
Cap("C8", "10u", "+3V3", "GND", B, near=("U5", "2", "B"))
Cap("C9", "100n", "+3V3", "GND", B, near=("U5", "2", "B"))
R("R12", "10k", "+3V3", "ESP_EN", B, near=("U5", "3", "B"))
Cap("C10", "1u", "ESP_EN", "GND", B, near=("U5", "3", "B"), desc="EN delay")
for ref, net in (("TP6", "ESP_EN"), ("TP7", "ESP_IO0"), ("TP8", "UART_TX"), ("TP9", "UART_RX")):
    TP(ref, net, B, near=("U5", "3", "B"))

# =============================================================== RADIO: LR2021 module, diversity switch, U.FLs, 2.4 GHz footprint
B = "Radio"
lr = {"1": "LR_VDD", "2": "LR_NSS_M", "3": "LR_SCK_M", "4": "LR_MOSI_M", "5": "LR_MISO_M", "6": "GND", "7": "LR_DIO6", "8": "LR_DIO5", "9": "LR_BUSY",
      "10": "LR_NRESET", "11": "RF_LF", "12": "GND", "13": "GND", "14": "GND", "15": "LR_TXRX_EN", "16": None, "17": "RF_HF",
      "18": "GND", "19": "GND", "20": "GND"}
comp("U6", "OpenTheatreComms:LR2021_Module_Elecrow", "LR2021", "OpenTheatreComms:LR2021_Elecrow_10x10mm", lr, B, pcb=("B", 33.0, 3.0, 180),
     mpn="Elecrow LR2021 module (LMM16121D)", desc="915-928 MHz FLRC radio; 2.4 GHz port for fallback")
for ref, a, b_ in (("R13", "LR_NSS", "LR_NSS_M"), ("R14", "LR_SCK", "LR_SCK_M"), ("R15", "LR_MOSI", "LR_MOSI_M"), ("R16", "LR_MISO", "LR_MISO_M")):
    R(ref, "470", a, b_, B, near=("U6", {"R13": "2", "R14": "3", "R15": "4", "R16": "5"}[ref], "F"), desc="SPI series resistor (module guide)")
R("R17", "100k", "+3V3", "LR_NRESET", B, near=("U6", "10", "B"))
comp("FB2", "Device:FerriteBead_Small", "0R", "Inductor_SMD:L_0603_1608Metric_Pad1.05x0.95mm_HandSolder", {"1": "+3V3", "2": "LR_VDD"}, B,
     near=("U6", "1", "B"), mpn="0603 0R (or Murata BLM18PG121SN1D)", desc="Radio supply link: the module has its own ferrite; fit a 120R bead here only if 3V3 noise needs it")
Cap("C11", "47u", "LR_VDD", "GND", B, near=("U6", "1", "B"), fp=C1206, mpn="1206 X5R 6.3 V", desc="Module bulk (guide: 47u + 10u + 100n)")
Cap("C12", "10u", "LR_VDD", "GND", B, near=("U6", "1", "B"))
Cap("C13", "100n", "LR_VDD", "GND", B, near=("U6", "1", "B"))
# 915 MHz chain, on B along y = 0.46 from the module's ANT_LF pad toward -X: shunt, series, shunt, DC block, switch, DC blocks, U.FLs
Y = 0.46
Cap("C14", "DNP", "RF_LF", "GND", B, pcb=("B", 26.0, Y - 0.9, 90), mpn="0603 C0G, tune", desc="Pi match shunt (module side), fit when tuning", dnp=True)
R("L1", "0", "RF_LF", "RF_LF_M", B, pcb=("B", 24.0, Y, 0), mpn="0603 0R or RF inductor", desc="Pi match series element: 0R until tuned")
Cap("C15", "DNP", "RF_LF_M", "GND", B, pcb=("B", 22.0, Y - 0.9, 90), mpn="0603 C0G, tune", desc="Pi match shunt (switch side), fit when tuning", dnp=True)
Cap("C16", "100p", "RF_LF_M", "RF_SW_C", B, pcb=("B", 20.0, Y, 0), mpn="0603 C0G 50 V", desc="DC block (switch RFC)")
comp("U7", "OpenTheatreComms:PE4259", "PE4259", "Package_TO_SOT_SMD:SOT-363_SC-70-6",
     {"5": "RF_SW_C", "4": "RF_CTRL_S", "6": "RF_SW_VDD", "1": "RF_SW_1", "3": "RF_SW_2", "2": "GND"}, B, pcb=("B", 17.3, Y, "rfc_right"),
     mpn="pSemi PE4259-63", desc="Antenna diversity switch, RF1 = antenna A when CTRL is high")
R("R18", "1k", "RF_CTRL", "RF_CTRL_S", B, near=("U7", "4", "B"))
R("R19", "1k", "+3V3", "RF_SW_VDD", B, near=("U7", "6", "B"))
Cap("C17", "100n", "RF_SW_VDD", "GND", B, near=("U7", "6", "B"))
Cap("C18", "100p", "RF_SW_1", "RF_ANT_A", B, pcb=("B", 14.6, Y + 2.0, 90), mpn="0603 C0G 50 V", desc="DC block (RF1)")
Cap("C19", "100p", "RF_SW_2", "RF_ANT_B", B, pcb=("B", 14.6, Y - 2.0, 90), mpn="0603 C0G 50 V", desc="DC block (RF2)")
comp("J5", "Connector:Conn_Coaxial", "Antenna A", "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", {"1": "RF_ANT_A", "2": "GND"}, B,
     pcb=("B", 13.8, Y + 5.6, 90), mpn="Hirose U.FL-R-SMT-1(10)", desc="Antenna A (right-end flex antenna)")
comp("J6", "Connector:Conn_Coaxial", "Antenna B", "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", {"1": "RF_ANT_B", "2": "GND"}, B,
     pcb=("B", 13.8, Y - 5.6, 270), mpn="Hirose U.FL-R-SMT-1(10)", desc="Antenna B (left-end flex antenna)")
R("L2", "0", "RF_HF", "RF_HF_M", B, pcb=("B", 31.73, 10.6, 90), mpn="0603 0R or RF inductor", desc="2.4 GHz match series element", dnp=True)
Cap("C20", "DNP", "RF_HF_M", "GND", B, pcb=("B", 29.9, 12.3, 0), mpn="0603 C0G, tune", desc="2.4 GHz match shunt", dnp=True)
comp("J7", "Connector:Conn_Coaxial", "2.4 GHz", "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", {"1": "RF_HF_M", "2": "GND"}, B,
     pcb=("B", 31.73, 13.6, 90), mpn="Hirose U.FL-R-SMT-1(10)", desc="2.4 GHz fallback antenna: footprint only in v1", dnp=True)

# =============================================================== AUDIO: codec, XLR-4 and 3.5 mm headsets, mic preamp slot
B = "Audio"
cod = {"1": "MICL_P", "2": "MICL_N", "3": None, "4": "MICR_P", "5": "MICR_N", "6": None, "7": "I2S_FS", "8": "I2S_BCLK", "9": "I2S_DIN",
       "10": "I2S_DOUT", "11": "I2S_MCLK", "12": "GND", "13": "+3V3", "14": "+3V3", "15": "GND", "16": "I2C_SCL", "17": "I2C_SDA", "18": "GND",
       "19": None, "20": None, "21": None, "22": None, "23": "SPK_P", "24": "GND", "25": "SPK_N", "26": "+3V3", "27": "COD_VREF", "28": "GND",
       "29": "HP_R", "30": "HP_L", "31": "VDDA_COD", "32": "MICBIAS", "33": "GND"}
comp("U8", "OpenTheatreComms:NAU88C22", "NAU88C22", "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm_ThermalVias", cod, B,
     pcb=("B", -5.0, -22.0, 0), mpn="Nuvoton NAU88C22YG", desc="Codec, I2C 0x1A, MODE low = 2-wire. Mics up to about 55 dB gain, BTL output for XLR earpieces")
comp("FB1", "Device:FerriteBead_Small", "600R", "Inductor_SMD:L_0603_1608Metric_Pad1.05x0.95mm_HandSolder", {"1": "+3V3", "2": "VDDA_COD"}, B,
     near=("U8", "31", "B"), mpn="Murata BLM18PG601SN1D")
Cap("C21", "10u", "VDDA_COD", "GND", B, near=("U8", "31", "B"))
Cap("C22", "100n", "VDDA_COD", "GND", B, near=("U8", "31", "B"))
Cap("C23", "4.7u", "+3V3", "GND", B, near=("U8", "13", "B"), desc="Codec VDDC/VDDB bulk (datasheet fig. 32: 4.7u + 0.1u per supply; C24 is the 0.1u)")
Cap("C24", "100n", "+3V3", "GND", B, near=("U8", "14", "B"))
Cap("C25", "10u", "+3V3", "GND", B, near=("U8", "26", "B"))
Cap("C26", "100n", "+3V3", "GND", B, near=("U8", "26", "B"))
Cap("C27", "4.7u", "COD_VREF", "GND", B, near=("U8", "27", "B"))
Cap("C28", "4.7u", "MICBIAS", "GND", B, near=("U8", "32", "B"), desc="MICBIAS filter (datasheet fig. 32: 4.7u)")
# XLR-4 male, Clear-Com wiring: 1 mic common, 2 mic +, 3 earpiece -, 4 earpiece +; pad 5 for the shell
comp("J3", "Connector_Generic:Conn_01x05", "XLR-4 wires", "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
     {"1": "GND", "2": "XLR_MIC", "3": "XLR_EAR_N", "4": "XLR_EAR_P", "5": "GND"}, B, pcb=("B", -24.5, -11.6, 90),
     mpn="Neutrik NC4MD-L-1 (wired)", desc="Wire pads for the panel XLR-4 male: 1 mic common, 2 mic +, 3 ear -, 4 ear +, 5 shell")
for ref, net in (("D4", "XLR_MIC"), ("D5", "XLR_EAR_N"), ("D6", "XLR_EAR_P")):
    comp(ref, "Device:D_TVS", "PESD5V0S1BA", "Diode_SMD:D_SOD-323_HandSoldering", {"1": net, "2": "GND"}, B,
         near=("J3", {"D4": "2", "D5": "3", "D6": "4"}[ref], "B"), mpn=TVS, desc="Headset ESD")
R("R20", "0", "XLR_MIC", "MICL_IN", B, near=("U8", "2", "B"), desc="Preamp bypass: remove when U9 and its parts are fitted")
Cap("C29", "1u", "MICL_IN", "MICL_N", B, near=("U8", "2", "B"), desc="XLR mic AC coupling")
Cap("C30", "1u", "MICL_P", "GND", B, near=("U8", "1", "B"), desc="Pseudo-differential reference")
# mic preamp slot (unfitted): OPA365 non-inverting, gain 1 + 47k/2.2k = 22.4 (27 dB), biased at mid-supply
comp("U9", "Amplifier_Operational:OPA365xxDBV", "OPA365", "Package_TO_SOT_SMD:SOT-23-5", {"5": "+3V3", "2": "GND", "3": "PRE_IN", "4": "PRE_FB", "1": "PRE_OUT"}, B,
     near=("R20", "1", "B"), mpn="TI OPA365AIDBVR", desc="Optional dynamic-mic preamp (slot, unfitted)", dnp=True)
Cap("C31", "1u", "XLR_MIC", "PRE_IN", B, near=("U9", "3", "B"), dnp=True)
R("R21", "100k", "PRE_IN", "PRE_VMID", B, near=("U9", "3", "B"), dnp=True)
R("R22", "10k", "+3V3", "PRE_VMID", B, near=("U9", "3", "B"), dnp=True)
R("R23", "10k", "PRE_VMID", "GND", B, near=("U9", "3", "B"), dnp=True)
Cap("C32", "10u", "PRE_VMID", "GND", B, near=("U9", "3", "B"), dnp=True)
R("R24", "47k", "PRE_OUT", "PRE_FB", B, near=("U9", "4", "B"), dnp=True)
R("R25", "2.2k", "PRE_FB", "PRE_G", B, near=("U9", "4", "B"), dnp=True)
Cap("C33", "22u", "PRE_G", "GND", B, near=("U9", "4", "B"), fp=C1206, mpn="1206 X5R 6.3 V", dnp=True)
R("R26", "0", "PRE_OUT", "MICL_IN", B, near=("U9", "1", "B"), desc="Preamp output link", dnp=True)
Cap("C34", "100n", "+3V3", "GND", B, near=("U9", "5", "B"), dnp=True)
# earpiece: BTL by default; for headsets with pin 3 tied to pin 1, swap R27 for a 100u 1206 cap, remove R28 and fit R29
R("R27", "0", "SPK_P", "XLR_EAR_P", B, near=("U8", "23", "B"), fp=R1206, mpn="1206 0R", desc="BTL link (or a 100u 1206 cap for single-ended)")
R("R28", "0", "SPK_N", "XLR_EAR_N", B, near=("U8", "25", "B"), desc="BTL link (remove for single-ended)")
R("R29", "0", "XLR_EAR_N", "GND", B, near=("J3", "3", "B"), desc="Single-ended option: earpiece - to ground", dnp=True)
# 3.5 mm TRRS (CTIA): tip L, ring 1 R, ring 2 ground, sleeve mic
comp("J2", "Connector_Audio:AudioJack4", "3.5 mm TRRS", "Connector_Audio:Jack_3.5mm_PJ320D_Horizontal",
     {"T": "TRRS_T", "R1": "TRRS_R", "R2": "GND", "S": "TRRS_MIC"}, B, pcb=("F", 22.0, "edge", "nose_down"), mpn="PJ-320D",
     desc="3.5 mm headset jack, stereo out, electret mic in (CTIA)")
Cap("C35", "100u", "HP_L", "TRRS_T", B, near=("J2", "T", "F"), fp=C1206, mpn="1206 X5R 6.3 V", desc="Headphone DC block (left)")
Cap("C36", "100u", "HP_R", "TRRS_R", B, near=("J2", "R1", "F"), fp=C1206, mpn="1206 X5R 6.3 V", desc="Headphone DC block (right)")
R("R30", "10k", "TRRS_T", "GND", B, near=("J2", "T", "F"), desc="Pop bleed")
R("R31", "10k", "TRRS_R", "GND", B, near=("J2", "R1", "F"), desc="Pop bleed")
R("R32", "2.2k", "MICBIAS", "TRRS_MIC", B, near=("J2", "S", "F"), desc="Electret bias")
Cap("C37", "1u", "TRRS_MIC", "MICR_N", B, near=("U8", "5", "B"), desc="TRRS mic AC coupling")
Cap("C38", "1u", "MICR_P", "GND", B, near=("U8", "4", "B"))
R("R33", "100k", "TRRS_MIC", "JACK_SENSE", B, near=("J2", "S", "F"), desc="Jack sense: the ESP32 reads the mic line (none, TRS or TRRS)")
Cap("C39", "10n", "JACK_SENSE", "GND", B, near=("J2", "S", "F"))
for ref, net in (("D7", "TRRS_T"), ("D8", "TRRS_R"), ("D9", "TRRS_MIC")):
    comp(ref, "Device:D_TVS", "PESD5V0S1BA", "Diode_SMD:D_SOD-323_HandSoldering", {"1": net, "2": "GND"}, B,
         near=("J2", {"D7": "T", "D8": "R1", "D9": "S"}[ref], "F"), mpn=TVS, desc="Headset ESD")

# =============================================================== IO: expander, front buttons, accelerometer, flashlight, vibration, link
B = "IO"
tca = {"~{INT}": "INT_N", "A0": "+3V3", "A1": "GND", "A2": "GND", "SCL": "I2C_SCL", "SDA": "I2C_SDA", "VCC": "+3V3", "GND": "GND",
       "P00": "BTN_BACK", "P01": "BTN_FUNC", "P02": "BTN_MENU", "P03": "PWR_BTN_N", "P04": "CHG_CHRG_N", "P05": "CHG_STDBY_N", "P06": "VBUS_DET",
       "P07": "ACC_INT1", "P10": "FG_ALRT_N", "P11": "LR_DIO5", "P12": "LR_TXRX_EN", "P13": "ACC_INT2", "P14": None, "P15": None, "P16": None, "P17": None}
comp("U10", "Interface_Expansion:TCA9555PWR", "TCA9555PWR", "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm", tca, B, pcb=("B", 0.0, 6.0, 0),
     mpn="TI TCA9555PWR", desc="IO expander at 0x21 (A0 high): buttons, charger, power button, sensors")
Cap("C40", "100n", "+3V3", "GND", B, near=("U10", "24", "B"))
for i, (ref, net, x, d) in enumerate((("SW2", "BTN_BACK", -18.0, "Back"), ("SW3", "BTN_FUNC", 0.0, "Function"), ("SW4", "BTN_MENU", 18.0, "Menu"))):
    comp(ref, "Switch:SW_Push", d, "Button_Switch_SMD:SW_SPST_PTS810", {"1": "GND", "2": net}, B, pcb=("F", x, 17.4, 0),
         mpn="C&K PTS815 SJM 250 SMTR LFS", desc=f"Front button: {d}")
comp("U11", "Sensor_Motion:LIS3DH", "LIS3DH", "Package_LGA:LGA-16_3x3mm_P0.5mm", {"1": "+3V3", "2": None, "3": None, "4": "I2C_SCL", "5": "GND",
     "6": "I2C_SDA", "7": "GND", "8": "+3V3", "9": "ACC_INT2", "10": "GND", "11": "ACC_INT1", "12": "GND", "13": None, "14": "+3V3", "15": None, "16": None}, B,
     pcb=("B", 3.0, -6.0, 0), mpn="ST LIS3DHTR", desc="Accelerometer at 0x18: OLED auto-flip for left or right hip, wake on pick-up, drop detection")
Cap("C41", "100n", "+3V3", "GND", B, near=("U11", "14", "B"))
Cap("C42", "10u", "+3V3", "GND", B, near=("U11", "1", "B"))
comp("D10", "Device:LED", "White 3 mm", "LED_THT:LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm", {"1": "LAMP_K", "2": "LAMP_A"}, B, pcb=("F", 32.0, "edge", "lamp"),
     mpn="3 mm white LED, 20 mA", desc="Flashlight: legs bent 90 degrees, 2 mm above the board, through the bottom face")
R("R34", "56", "SYS", "LAMP_A", B, near=("D10", "2", "F"), desc="About 20 mA at 4.2 V; dim with PWM")
comp("Q3", "Transistor_FET:AO3400A", "AO3400A", SOT23, {"1": "LAMP_G", "2": "GND", "3": "LAMP_K"}, B, near=("D10", "1", "F"), mpn="AOS AO3400A")
R("R35", "100", "LAMP_EN", "LAMP_G", B, near=("Q3", "1", "F"))
R("R36", "100k", "LAMP_G", "GND", B, near=("Q3", "1", "F"))
comp("M1", "Motor:Motor_DC", "Vibration", "OpenTheatreComms:Motor_Coin_8mm_LeadPads", {"1": "+3V3", "2": "VIB_N"}, B, pcb=("F", 32.0, -20.0, 0),
     mpn="8 x 2.7 mm coin vibration motor, 3 V", desc="Call alert")
comp("Q4", "Transistor_FET:AO3400A", "AO3400A", SOT23, {"1": "VIB_G", "2": "GND", "3": "VIB_N"}, B, near=("M1", "2", "F"), mpn="AOS AO3400A")
R("R37", "100", "VIB_EN", "VIB_G", B, near=("Q4", "1", "F"))
R("R38", "100k", "VIB_G", "GND", B, near=("Q4", "1", "F"))
comp("D11", "Device:D_Schottky", "BAT54WS", SOD323, {"1": "+3V3", "2": "VIB_N"}, B, near=("M1", "2", "F"), mpn="Diodes BAT54WS", desc="Motor flyback")
Cap("C43", "10u", "+3V3", "GND", B, near=("M1", "1", "F"))
link = {"1": "GND", "2": "+3V3", "3": "I2C_SDA", "4": "I2C_SCL", "5": "INT_N", "6": "ENC_L_A", "7": "ENC_L_B", "8": "ENC_R_A", "9": "ENC_R_B", "10": "GND"}
comp("J4", "Connector_Generic:Conn_01x10", "Top PCB link", "Connector_JST:JST_SH_SM10B-SRSS-TB_1x10-1MP_P1.00mm_Horizontal", link, B,
     pcb=("B", 8.0, "tab_top", 0), mpn="JST SM10B-SRSS-TB", desc="Side-entry JST SH 10, mouth up; same pinout as the top PCB's J1")
R("R39", "4.7k", "+3V3", "I2C_SDA", B, near=("J4", "3", "B"), desc="Only if the top PCB is absent (its pull-ups serve the bus)", dnp=True)
R("R40", "4.7k", "+3V3", "I2C_SCL", B, near=("J4", "4", "B"), desc="Only if the top PCB is absent", dnp=True)
R("R41", "10k", "+3V3", "INT_N", B, near=("J4", "5", "B"), desc="Only if the top PCB is absent", dnp=True)
for h, (hx, hy) in (("H1", (-30.0, -9.0)), ("H2", (38.0, 12.0)), ("H3", (-6.0, 25.5)), ("H4", (38.0, -32.5)), ("H5", (-10.0, -32.5))):
    comp(h, "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", {}, "IO", pcb=("F", hx, hy, 0), desc="M2 into a heat-set insert")

BLOCKS = [("Power", "Power: USB-C, charger with power path, 3.3 V LDO with soft power switch, fuel gauge, battery pins"),
          ("MCU", "ESP32-S3-WROOM-1-N8R8: radio timing, Opus, UI. Native USB for flashing and serial; pads for EN, IO0 and UART0"),
          ("Radio", "LR2021 module, 915 MHz pi match, PE4259 antenna diversity switch, two U.FLs; 2.4 GHz port as a footprint only"),
          ("Audio", "NAU88C22 codec: XLR-4 dynamic headset (BTL earpiece), 3.5 mm TRRS headset (stereo, electret), optional mic preamp slot"),
          ("IO", "IO expander (0x21), front buttons, LIS3DH accelerometer, flashlight, vibration motor, link to the top PCB, mounting holes")]
NETS = sorted({n for c in C for n in c["pins"].values() if n})
