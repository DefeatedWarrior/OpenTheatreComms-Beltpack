"""Project footprints for the top PCB. Writes lib/OpenTheatreComms.pretty/OLED_Tail_30P_0.7mm_Solder.kicad_mod.

The 1.3 in 128x64 30-pin OLED panels (SH1106 / SSD1306, 34.5 x 23 mm glass) end in a solder tail: 30 leads, 0.40 mm wide
at 0.70 mm pitch (20.3 mm first to last), 2.0 mm of bare lead at the end, tail 22 mm wide, two alignment marks 16 mm apart.
The tail wraps round the board's back-edge notch and is soldered flat onto these pads on B.Cu. No paste: the pads are
tinned and the tail is soldered with an iron last, after all reflow (the panel would not survive the hot plate).

Pad k holds the tail lead at position k counted from -X in this footprint (the board places it so panel pin 31 - k lands
on pad k; see design.py). Local frame: pads centred on y = 0; tail end at y = -1.2, board edge at y = +5.8 (when placed
at board y = 5.5 on B)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
P, N, PW, PL = 0.70, 30, 0.45, 3.0
TAIL_END, EDGE, MARK_Y, HALF_W = -1.2, 5.8, 3.55, 11.0
o = ['(footprint "OLED_Tail_30P_0.7mm_Solder" (version 20221018) (generator pcbnew) (layer "F.Cu")',
     '  (descr "Solder pads for a 1.3 in 30-pin OLED panel tail: 30 leads, 0.4 mm wide, 0.7 mm pitch, 2 mm bare lead; tail 22 mm wide, alignment marks 16 mm apart. No paste: solder by iron after reflow.")',
     '  (attr smd)',
     '  (fp_text reference "REF**" (at 0 -2.4) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
     '  (fp_text value "OLED_Tail_30P_0.7mm_Solder" (at 0 6.6) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))',
     '  (fp_text user "1" (at 11.7 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
     '  (fp_text user "30" (at -12.0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))']
def line(x0, y0, x1, y1, layer, w): o.append(f'  (fp_line (start {x0} {y0}) (end {x1} {y1}) (stroke (width {w}) (type default)) (layer "{layer}"))')
# tail outline on the fab layer; side guides on silk (clear of the pads)
for x0, y0, x1, y1 in ((-HALF_W, TAIL_END, HALF_W, TAIL_END), (HALF_W, TAIL_END, HALF_W, EDGE), (-HALF_W, TAIL_END, -HALF_W, EDGE)):
    line(x0, y0, x1, y1, "F.Fab", 0.1)
for s in (-1, 1):
    line(s * HALF_W, TAIL_END, s * HALF_W, EDGE - 0.6, "F.SilkS", 0.12)
    line(s * HALF_W, TAIL_END, s * (HALF_W - 0.3), TAIL_END, "F.SilkS", 0.12)
    o.append(f'  (fp_circle (center {s * 8.0} {MARK_Y}) (end {s * 8.0 + 0.5} {MARK_Y}) (stroke (width 0.12) (type default)) (fill none) (layer "F.SilkS"))')
o.append(f'  (fp_rect (start {-HALF_W - 0.3} {TAIL_END - 0.6}) (end {HALF_W + 0.3} {PL / 2 + 0.3}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))')
for k in range(1, N + 1):
    x = round((k - (N + 1) / 2) * P, 3)
    o.append(f'  (pad "{k}" smd roundrect (at {x} 0) (size {PW} {PL}) (layers "F.Cu" "F.Mask") (roundrect_rratio 0.25))')
o.append(')')
d = os.path.join(HERE, "lib", "OpenTheatreComms.pretty"); os.makedirs(d, exist_ok=True)
open(os.path.join(d, "OLED_Tail_30P_0.7mm_Solder.kicad_mod"), "w").write("\n".join(o) + "\n")
print("written")
