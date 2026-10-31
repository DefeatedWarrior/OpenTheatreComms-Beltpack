"""Fab and assembly outputs for the base station carrier PCB, written to kicad_proj/base_pcb/fab/:
Gerbers + Excellon drill (zipped for upload), pick-and-place CSV, BOM CSV, assembly drawings (PDF), preview renders."""
import os, sys, csv, zipfile, subprocess, shutil, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from design import C
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "base_pcb"))
PCB = os.path.join(PROJ, "base_pcb.kicad_pcb"); SCH = os.path.join(PROJ, "base_pcb.kicad_sch")
FAB = os.path.join(PROJ, "fab"); GER = os.path.join(FAB, "gerbers")
shutil.rmtree(FAB, ignore_errors=True); os.makedirs(GER)
def cli(*a): subprocess.run(["kicad-cli", *a], check=True, capture_output=True)

cli("pcb", "export", "gerbers", "-o", GER + "/", "--layers",
    "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts", "--subtract-soldermask", "--use-drill-file-origin", PCB)
cli("pcb", "export", "drill", "-o", GER + "/", "--format", "excellon", "--drill-origin", "plot", "--excellon-units", "mm",
    "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", PCB)
with zipfile.ZipFile(os.path.join(FAB, "base_pcb_gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(glob.glob(GER + "/*")): z.write(f, os.path.basename(f))
cli("pcb", "export", "pos", "-o", os.path.join(FAB, "base_pcb_placement.csv"), "--side", "both", "--format", "csv", "--units", "mm",
    "--use-drill-file-origin", PCB)
cli("sch", "export", "pdf", "-o", os.path.join(FAB, "base_pcb_schematic.pdf"), SCH)

# BOM grouped by value + footprint + MPN; the side comes from the board (the placer may move a part to the other side)
import pcbnew
SIDE = {f.GetReference(): ("bottom" if f.IsFlipped() else "top") for f in pcbnew.LoadBoard(PCB).GetFootprints()}
groups = {}
for c in C:
    if c["lib_id"] == "Mechanical:MountingHole" or c["lib_id"] == "Connector:TestPoint": continue
    k = (c["value"], c["fp"].split(":")[1], c["mpn"], c["dnp"])
    g = groups.setdefault(k, dict(refs=[], desc=c["desc"], side=set()))
    g["refs"].append(c["ref"]); g["side"].add(SIDE[c["ref"]])
def refkey(r):
    import re; m = re.match(r"([A-Z]+)(\d+)", r); return (m.group(1), int(m.group(2)))
rows = sorted(groups.items(), key=lambda kv: refkey(sorted(kv[1]["refs"], key=refkey)[0]))
with open(os.path.join(FAB, "base_pcb_bom.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Qty", "References", "Value", "Footprint", "Part", "Side", "Notes"])
    for (val, fp, mpn, dnp), g in rows:
        refs = sorted(g["refs"], key=refkey)
        w.writerow([0 if dnp else len(refs), " ".join(refs), ("DNP " if dnp else "") + val, fp, mpn, "/".join(sorted(g["side"])),
                    ("Not fitted. " if dnp else "") + (g["desc"] if len(refs) == 1 else "")])
subprocess.run([sys.executable, os.path.join(HERE, "make_assembly.py")], check=True, capture_output=True)
subprocess.run([sys.executable, os.path.join(HERE, "render_board.py"), PCB, os.path.join(FAB, "base_pcb_preview.png")], check=True, capture_output=True)
drc = os.path.join(HERE, "out", "drc.rpt")
if os.path.exists(drc): shutil.copy(drc, os.path.join(FAB, "base_pcb_drc.rpt"))
print("fab files:", sorted(os.listdir(FAB)), len(os.listdir(GER)), "gerber/drill files")
# 1:1 print (A4 landscape, print at 100 %) for checking the NANO sockets against the hole marks before ordering
cli("pcb", "export", "pdf", "-o", os.path.join(FAB, "base_pcb_print_1to1.pdf"), "--layers", "F.Cu,F.Silkscreen,Edge.Cuts", "--black-and-white", PCB)
