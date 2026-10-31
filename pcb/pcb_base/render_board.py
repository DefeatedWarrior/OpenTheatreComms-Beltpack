"""Photo-style preview of the base station carrier PCB (green mask, ENIG pads, white silk), both sides, from kicad-cli layer SVGs.
  python3 render_board.py board.kicad_pcb out.png"""
import sys, os, subprocess, tempfile, io
import numpy as np, cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbgeom import Bf, mm

pcb, out = sys.argv[1], sys.argv[2]
W = 2400
tmp = tempfile.mkdtemp()
def layer(name, mirror):
    svg = os.path.join(tmp, f"{name}_{int(mirror)}.svg")
    cmd = ["kicad-cli", "pcb", "export", "svg", "-o", svg, "--layers", name, "--page-size-mode", "2", "--exclude-drawing-sheet",
           "--black-and-white", "--drill-shape-opt", "0"]
    if mirror: cmd.append("--mirror")
    subprocess.run(cmd + [pcb], check=True, capture_output=True)
    png = cairosvg.svg2png(url=svg, output_width=W)
    a = np.array(Image.open(io.BytesIO(png)).convert("RGBA"))[:, :, 3]
    return a > 40

b = pcbnew.LoadBoard(pcb)
holes = []
for fp in b.GetFootprints():
    for pad in fp.Pads():
        if pad.HasHole():
            holes.append((*Bf(pad.GetPosition()), mm(pad.GetDrillSize().x) / 2, mm(pad.GetDrillSize().y) / 2, pad.GetOrientationDegrees()))
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA": holes.append((*Bf(t.GetPosition()), mm(t.GetDrillValue()) / 2, mm(t.GetDrillValue()) / 2, 0))
from pcbgeom import board_outline
_o = board_outline(b).bounds
BX0, BX1, YC = _o[0], _o[2], (_o[1] + _o[3]) / 2           # board outline extent (board frame)

def side(top):
    pre = "F" if top else "B"
    edge = layer("Edge.Cuts", not top)
    cu, mask, silk = layer(f"{pre}.Cu", not top), layer(f"{pre}.Mask", not top), layer(f"{pre}.Silkscreen", not top)
    H = edge.shape[0]
    # board interior: flood-fill the outline raster from its centre
    from scipy.ndimage import binary_fill_holes, binary_closing
    ys, xs = np.nonzero(edge); cx, cy = int((xs.min() + xs.max()) / 2), int((ys.min() + ys.max()) / 2)
    board = binary_fill_holes(binary_closing(edge, iterations=2))
    # pixel transform from the outline's X extent (mirrored on the bottom view)
    sx = (xs.max() - xs.min()) / (BX1 - BX0)
    def px(x, y):
        X = (x - BX0) * sx + xs.min() if top else (BX1 - x) * sx + xs.min()
        Y = cy - (y - YC) * sx
        return X, Y
    rgb = np.zeros((H, W, 3), np.uint8); rgb[:] = (246, 246, 243)
    rgb[board] = (24, 88, 56)                                # solder mask over FR4
    rgb[board & cu] = (40, 120, 76)                          # copper under mask
    rgb[board & mask] = (196, 178, 128)                      # mask opening on bare FR4
    rgb[board & mask & cu] = (219, 180, 84)                  # ENIG pads
    rgb[board & silk & ~mask] = (240, 240, 236)
    img = Image.fromarray(rgb)
    d = ImageDraw.Draw(img)
    for x, y, rx, ry, rot in holes:
        X, Y = px(x, y); r = max(rx, ry) * sx if abs(rx - ry) > 0.01 else rx * sx
        if abs(rx - ry) > 0.01:                              # slots: draw as a rounded line
            import math
            L = (max(rx, ry) - min(rx, ry)) * sx; ang = math.radians(rot + (90 if ry > rx else 0))
            dx, dy = math.cos(ang) * L, -math.sin(ang) * L
            if not top: dx = -dx
            d.line([(X - dx, Y - dy), (X + dx, Y + dy)], fill=(246, 246, 243), width=int(2 * min(rx, ry) * sx))
            for s_ in (-1, 1): d.ellipse([X + s_ * dx - min(rx, ry) * sx, Y + s_ * dy - min(rx, ry) * sx, X + s_ * dx + min(rx, ry) * sx, Y + s_ * dy + min(rx, ry) * sx], fill=(246, 246, 243))
        else:
            d.ellipse([X - r, Y - r, X + r, Y + r], fill=(246, 246, 243))
    bbox = (max(0, xs.min() - 30), max(0, ys.min() - 30), min(W, xs.max() + 30), min(H, ys.max() + 30))
    return img.crop(bbox)

top, bot = side(True), side(False)
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
pad = 60; gap = 90; head = 120
Wt = max(top.width, bot.width) + 2 * pad
sheet = Image.new("RGB", (Wt, head + top.height + gap + bot.height + 70), (246, 246, 243))
dr = ImageDraw.Draw(sheet)
dr.text((pad, 30), "Base station carrier PCB, rev 0.1", font=ImageFont.truetype(FB, 40), fill=(29, 36, 48))
dr.text((pad, 82), "150 x 90 mm, 2 layers, 1.6 mm. Top face (every part) and bottom face (mirrored). Rear edge at the top.", font=ImageFont.truetype(F, 24), fill=(100, 108, 120))
sheet.paste(top, (pad, head))
dr.text((pad, head + top.height + 12), "Top (F): NANO sockets, DC input, radios and SMAs, OLED socket, keys, dial, RGB lights", font=ImageFont.truetype(F, 22), fill=(29, 36, 48))
y2 = head + top.height + gap
sheet.paste(bot, (pad, y2))
dr.text((pad, y2 + bot.height + 12), "Bottom (B), mirrored: routing and ground pour only", font=ImageFont.truetype(F, 22), fill=(29, 36, 48))
sheet.save(out); print(out, sheet.size)
