"""Fab outputs for the pack lid PCB, written to kicad_proj/pack_lid_pcb/fab/: Gerbers + Excellon drill (zipped for upload),
schematic PDF, DRC report and a preview of both faces. The board has no parts to place (its pads are the product)."""
import os, sys, zipfile, subprocess, shutil, glob
import cairosvg
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "pack_lid_pcb"))
PCB = os.path.join(PROJ, "pack_lid_pcb.kicad_pcb"); SCH = os.path.join(PROJ, "pack_lid_pcb.kicad_sch")
FAB = os.path.join(PROJ, "fab"); GER = os.path.join(FAB, "gerbers")
shutil.rmtree(FAB, ignore_errors=True); os.makedirs(GER)
def cli(*a): subprocess.run(["kicad-cli", *a], check=True, capture_output=True)
cli("pcb", "export", "gerbers", "-o", GER + "/", "--layers", "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts",
    "--subtract-soldermask", "--use-drill-file-origin", PCB)
cli("pcb", "export", "drill", "-o", GER + "/", "--format", "excellon", "--drill-origin", "plot", "--excellon-units", "mm",
    "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", PCB)
with zipfile.ZipFile(os.path.join(FAB, "pack_lid_pcb_gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(glob.glob(GER + "/*")): z.write(f, os.path.basename(f))
cli("sch", "export", "pdf", "-o", os.path.join(FAB, "pack_lid_pcb_schematic.pdf"), SCH)
for side, layers in (("front", "F.Cu,F.Mask,F.Silkscreen,Edge.Cuts"), ("back", "B.Cu,B.Mask,B.Silkscreen,Edge.Cuts")):
    svg = os.path.join(FAB, f"preview_{side}.svg")
    args = ["pcb", "export", "svg", "-o", svg, "--layers", layers, "--page-size-mode", "2", "--exclude-drawing-sheet"]
    if side == "back": args.append("--mirror")
    cli(*args, PCB)
    png = os.path.join(FAB, f"pack_lid_pcb_{side}.png")
    cairosvg.svg2png(url=svg, write_to=png, output_width=1600, background_color="white"); os.remove(svg)
    from PIL import Image, ImageOps
    im = Image.open(png).convert("RGB"); bb = ImageOps.invert(im).getbbox()
    if bb: im.crop((max(bb[0] - 20, 0), max(bb[1] - 20, 0), bb[2] + 20, bb[3] + 20)).save(png)
drc = os.path.join(HERE, "out", "drc.rpt")
if os.path.exists(drc): shutil.copy(drc, os.path.join(FAB, "pack_lid_pcb_drc.rpt"))
print("fab files:", sorted(os.listdir(FAB)), len(os.listdir(GER)), "gerber/drill files")
