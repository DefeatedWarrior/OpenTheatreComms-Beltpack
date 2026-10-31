"""Render the top PCB as PNG previews with kicad-cli SVG export + cairosvg.
  python3 render.py board.kicad_pcb outprefix [check|fab]
check: copper, courtyards and case references (for placement review); fab: what the board will look like."""
import sys, subprocess, os, cairosvg
from PIL import Image
pcb, pre = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "check"
sets = {
    "check": {"top": "F.Cu,F.Courtyard,F.Fab,User.3,User.1,Edge.Cuts", "bottom": "B.Cu,B.Courtyard,B.Fab,User.3,User.2,Edge.Cuts"},
    "fab": {"top": "F.Cu,F.Mask,F.Silkscreen,Edge.Cuts", "bottom": "B.Cu,B.Mask,B.Silkscreen,Edge.Cuts"},
    "copper": {"top": "F.Cu,Edge.Cuts", "bottom": "B.Cu,Edge.Cuts"},
}[mode]
outs = []
for view, layers in sets.items():
    svg = f"{pre}_{view}.svg"
    cmd = ["kicad-cli", "pcb", "export", "svg", "-o", svg, "--layers", layers, "--page-size-mode", "2", "--exclude-drawing-sheet"]
    if view == "bottom": cmd.append("--mirror")
    subprocess.run(cmd + [pcb], check=True, capture_output=True)
    png = f"{pre}_{view}.png"
    cairosvg.svg2png(url=svg, write_to=png, output_width=2400, background_color="white")
    outs.append(png)
ims = [Image.open(p).convert("RGB") for p in outs]
W = max(i.width for i in ims); H = sum(i.height for i in ims) + 20
sheet = Image.new("RGB", (W, H), "white"); y = 0
for i in ims: sheet.paste(i, (0, y)); y += i.height + 20
sheet.save(f"{pre}_{mode}.png"); print(f"{pre}_{mode}.png", sheet.size)
