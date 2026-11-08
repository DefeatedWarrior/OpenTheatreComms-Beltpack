"""Fab and assembly outputs for the top PCB, written to kicad_proj/top_pcb/fab/:
Gerbers + Excellon drill (zipped for upload), pick-and-place CSV, BOM CSV, assembly drawings (PDF), preview renders."""
import os, sys, csv, zipfile, subprocess, shutil, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from design import C
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "top_pcb"))
PCB = os.path.join(PROJ, "top_pcb.kicad_pcb"); SCH = os.path.join(PROJ, "top_pcb.kicad_sch")
FAB = os.path.join(PROJ, "fab"); GER = os.path.join(FAB, "gerbers")
shutil.rmtree(FAB, ignore_errors=True); os.makedirs(GER)
def cli(*a): subprocess.run(["kicad-cli", *a], check=True, capture_output=True)

cli("pcb", "export", "gerbers", "-o", GER + "/", "--layers",
    "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts", "--subtract-soldermask", "--use-drill-file-origin", PCB)
cli("pcb", "export", "drill", "-o", GER + "/", "--format", "excellon", "--drill-origin", "plot", "--excellon-units", "mm",
    "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", PCB)
with zipfile.ZipFile(os.path.join(FAB, "top_pcb_gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(glob.glob(GER + "/*")): z.write(f, os.path.basename(f))
cli("pcb", "export", "pos", "-o", os.path.join(FAB, "top_pcb_placement.csv"), "--side", "both", "--format", "csv", "--units", "mm",
    "--use-drill-file-origin", PCB)
cli("sch", "export", "pdf", "-o", os.path.join(FAB, "top_pcb_schematic.pdf"), SCH)

# BOM grouped by value + footprint + MPN
groups = {}
for c in C:
    if c["lib_id"] == "Mechanical:MountingHole": continue
    k = (c["value"], c["fp"].split(":")[1], c["mpn"])
    g = groups.setdefault(k, dict(refs=[], desc=c["desc"], side=set()))
    g["refs"].append(c["ref"]); g["side"].add({"F": "top", "B": "bottom"}[c["pcb"][0]])
def refkey(r):
    import re; m = re.match(r"([A-Z]+)(\d+)", r); return (m.group(1), int(m.group(2)))
rows = sorted(groups.items(), key=lambda kv: refkey(sorted(kv[1]["refs"], key=refkey)[0]))
with open(os.path.join(FAB, "top_pcb_bom.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Qty", "References", "Value", "Footprint", "Part", "Side", "Notes"])
    for (val, fp, mpn), g in rows:
        refs = sorted(g["refs"], key=refkey)
        w.writerow([len(refs), " ".join(refs), val, fp, mpn, "/".join(sorted(g["side"])), g["desc"] if len(refs) == 1 else ""])
subprocess.run([sys.executable, os.path.join(HERE, "make_assembly.py")], check=True, capture_output=True)
subprocess.run([sys.executable, os.path.join(HERE, "render_board.py"), PCB, os.path.join(FAB, "top_pcb_preview.png")], check=True, capture_output=True)
drc = os.path.join(HERE, "out", "drc.rpt")
if os.path.exists(drc): shutil.copy(drc, os.path.join(FAB, "top_pcb_drc.rpt"))
print("fab files:", sorted(os.listdir(FAB)), len(os.listdir(GER)), "gerber/drill files")
