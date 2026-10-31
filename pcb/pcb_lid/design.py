"""Pack lid PCB (the battery pack's contact board): every part, its nets and its board position.

Frame: viewed from the front, same frame as the main PCB (origin at the case centre, +Y up). The board is 24 x 8 mm,
x 0..24, y -19..-11, 0.8 mm thick, set into a recess in the pack's front face. F.Cu faces the main PCB: three 3 mm
contact pads under the main PCB's Mill-Max spring pins (J8 BAT+ at x 6, J9 NTC at x 12, J10 BAT- at x 18, y -15) and three
plated wire holes for the cell's leads (red BAT+, yellow or white NTC, black BAT-). The back sits on the cell, so
nothing is mounted there.
"""
C = []
def comp(ref, lib_id, value, fp, pins, block, pcb=None, mpn="", desc="", dnp=False):
    C.append(dict(ref=ref, lib_id=lib_id, value=value, fp=fp, pins=pins, block=block, pcb=pcb, near=None, mpn=mpn, desc=desc, dnp=dnp))

B = "Pack"
for ref, net, x, d in (("J1", "BAT+", 6.0, "BAT+"), ("J2", "NTC", 12.0, "NTC"), ("J3", "BAT-", 18.0, "BAT-")):
    comp(ref, "Connector:TestPoint", d, "TestPoint:TestPoint_Pad_D3.0mm", {"1": net}, B, pcb=("F", x, -15.0, 0),
         mpn="PCB pad (ENIG)", desc=f"Contact pad under the main PCB's spring pin: {d}")
for ref, net, x, d in (("J4", "BAT+", 2.2, "Cell + (red)"), ("J5", "NTC", 9.0, "Pack NTC (10k, B 3435)"), ("J6", "BAT-", 21.8, "Cell - (black)")):
    comp(ref, "Connector_Generic:Conn_01x01", d, "Connector_Wire:SolderWire-0.25sqmm_1x01_D0.65mm_OD1.7mm", {"1": net}, B, pcb=("F", x, -15.0, 0),
         mpn="Wire, 0.25 mm2 (24 AWG)", desc=f"Wire hole: {d}")

BLOCKS = [("Pack", "Pack lid: contact pads for the beltpack spring pins, wire holes for the cell's leads and its NTC")]
NETS = sorted({n for c in C for n in c["pins"].values() if n})
