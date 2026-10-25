from PIL import Image, ImageDraw, ImageFont, ImageChops
import os, json
here = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(here, "..", "renders")
info = json.load(open(os.path.join(here, "out", "parts_final.json")))
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(s, b=False): return ImageFont.truetype(FB if b else F, s)
INK, MUTED, BG, ACC = (29, 36, 48), (100, 108, 120), (250, 250, 248), (214, 150, 20)

def load(name, w, h):
    im = Image.open(os.path.join(R, name + ".png")).convert("RGB")
    bg = Image.new("RGB", im.size, im.getpixel((4, 4)))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 18 else 0)
    bb = diff.getbbox() or (0, 0, im.width, im.height)
    pad = 30; bb = (max(0, bb[0] - pad), max(0, bb[1] - pad), min(im.width, bb[2] + pad), min(im.height, bb[3] + pad))
    im = im.crop(bb)
    s = min(w / im.width, h / im.height); im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    cell = Image.new("RGB", (w, h), im.getpixel((2, 2)))
    cell.paste(im, ((w - im.width) // 2, (h - im.height) // 2)); return cell

M, G, CW, CH, CAP = 60, 28, 760, 600, 56
W = M * 2 + CW * 3 + G * 2
cells = [  # name, col, row, colspan, rowspan, caption
    ("r_hero", 0, 0, 2, 2, "Exterior: 105 × 77 × 30 mm shell, TPU caps top and bottom, dials flush with the round ends"),
    ("r_wearer", 2, 0, 1, 1, "Wearer's view: keys, OLED and a status light at each end"),
    ("r_bottom", 2, 1, 1, 1, "Bottom: XLR-4 (D-type), power, USB-C, 3.5 mm, flashlight"),
    ("r_ghost", 0, 2, 1, 1, "See-through: two boards, encoders inside the dials"),
    ("r_int_front", 1, 2, 1, 1, "Front of the internals: buttons and bottom connectors"),
    ("r_int_back", 2, 2, 1, 1, "Back of the internals: ESP32-S3, LR2021, pogo pins"),
    ("r_exploded", 0, 3, 2, 1, "Exploded: top module, shells, main PCB, battery pack, belt plate"),
    ("r_back", 2, 3, 1, 1, "Hip side: belt plate on dovetail rails, doubles as the battery door"),
]
top = 170
rows = 4
H = top + rows * (CH + CAP) + (rows - 1) * G + 150
sheet = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(sheet)
d.text((M, 50), "OpenTheatreComms beltpack", font=font(46, True), fill=INK)
e = info["envelope"]
d.text((M, 112), f"Final reference model with datasheet part envelopes  ·  {e[0]:.0f} × {e[1]:.0f} × 35 mm with TPU caps, {e[2]:.0f} mm deep with the belt plate  ·  66 parts, no clashes",
       font=font(22), fill=MUTED)
for name, c, r, cs, rs, cap in cells:
    x = M + c * (CW + G); y = top + r * (CH + CAP + G)
    w = cs * CW + (cs - 1) * G; h = rs * CH + (rs - 1) * (CH + CAP + G - CH) - (0 if rs == 1 else 0)
    if rs > 1: h = rs * CH + (rs - 1) * (CAP + G)
    sheet.paste(load(name, w, h), (x, y))
    d.text((x + 4, y + h + 12), cap, font=font(19), fill=INK)
fy = H - 110
d.line((M, fy, W - M, fy), fill=(220, 220, 215), width=2)
d.text((M, fy + 22), "Top PCB 99.8 × 26.5 mm curved pill (1.6 mm, 2 layers)   ·   Main PCB 87.5 × 64.5 mm stepped (1.6 mm, 4 layers)   ·   Pack pad board 24 × 8 mm (0.8 mm)",
       font=font(21, True), fill=INK)
d.text((M, fy + 56), "Envelopes from Bourns, Espressif, Elecrow, Nuvoton, C&K, GCT, Molex, Mill-Max, JST and Neutrik data; a few typical sizes are flagged to verify before layout.",
       font=font(18), fill=MUTED)
sheet.save(os.path.join(R, "beltpack_final_sheet.png"), optimize=True)
print(sheet.size)
