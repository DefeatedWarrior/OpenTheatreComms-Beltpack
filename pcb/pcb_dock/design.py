"""Dock contact board: the beltpack's charge and USB contacts, set into the case bottom. Every part, its nets and position.

Frame: board-local, x 0..22, y 0..11 (+Y up), 0.8 mm thick. F.Cu is the outside face: four 2.5 mm ENIG pads at 4 mm pitch
where the dock's spring pins land. B.Cu faces into the case: a JST SH 4-pin side-entry socket (SM04B-SRSS-TB, 2.9 mm tall) whose
mouth faces the y = 0 edge, toward the main board. A flat 4-way SH cable runs 1:1 to the main board's J12 (BM04B vertical,
on the main board's back face below the battery pack): pin 1 VBUS, 2 D-, 3 D+, 4 GND. On the main board, D12 feeds dock VBUS into the pack's
VBUS and keeps the USB-C's 5 V off these pads; D+/D- join the ESP32-S3's USB, protected by the main board's USBLC6.
Seen from outside, left to right: GND, D+, D-, VBUS (the socket's pins 4-1 sit right behind them).
"""
C = []
def comp(ref, lib_id, value, fp, pins, block, pcb=None, mpn="", desc="", dnp=False):
    C.append(dict(ref=ref, lib_id=lib_id, value=value, fp=fp, pins=pins, block=block, pcb=pcb, near=None, mpn=mpn, desc=desc, dnp=dnp))

W, H = 22.0, 11.0
PAD_Y = 8.6
VIA_Y = 6.65                     # one row of vias between the socket pins and the contact pads
B = "Dock"
for ref, net, x, d in (("J1", "GND", 5.0, "GND"), ("J2", "D+", 9.0, "D+"), ("J3", "D-", 13.0, "D-"), ("J4", "VBUS", 17.0, "VBUS")):
    comp(ref, "Connector:TestPoint", d, "TestPoint:TestPoint_Pad_D2.5mm", {"1": net}, B, pcb=("F", x, PAD_Y, 0),
         mpn="PCB pad (ENIG)", desc=f"Dock contact pad (outside face): {d}")
comp("J5", "Connector_Generic_MountingPin:Conn_01x04_MountingPin", "To main J12", "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal",
     {"1": "VBUS", "2": "D-", "3": "D+", "4": "GND", "MP": None}, B, pcb=("B", 11.0, 3.3, 180), mpn="JST SM04B-SRSS-TB(LF)(SN)",
     desc="Cable to the main board's J12, pin for pin (4-way JST SH, same-side ends)")
for ref, x in (("H1", 1.8), ("H2", 20.2)):
    comp(ref, "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", {}, B, pcb=("F", x, H / 2, 0),
         mpn="", desc="M2 fixing into the case bottom")

BLOCKS = [("Dock", "Dock contacts: four ENIG pads for the dock's spring pins, cabled to the main board's J12")]
NETS = sorted({n for c in C for n in c["pins"].values() if n})
