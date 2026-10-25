# Beltpack boards: KiCad hand-off

All sizes in mm. The shapes come from `final_bp.py` (CadQuery), which also builds the case, so changing a constant there and
re-running `export_boards.py` regenerates everything here.

## Files

| File | Use |
|---|---|
| `*_edge_cuts.dxf` | Board outline only, with true arcs. In the PCB editor use File → Import → Graphics, layer **Edge.Cuts**, scale 1, units mm. |
| `*.dxf` | Same outline plus layers `Holes`, `Place_F`, `Place_B` and `Mech` (part envelopes, keycaps, dials, case bosses). Import onto **User.1 / User.2** as a placement guide. |
| `*_drawing.png` | Dimensioned drawing of each board. |
| `placement.csv` | Every part centre, envelope and height, plus the mounting holes, in each board's frame. |

## Frames

- **Top PCB**, viewed from above (top side = F.Cu). Origin at the board centre; +X to the right, +Y toward the back (hip) edge.
  The front edge is R427.4 and the back edge R402.6, both centred at (0, +415.0). The ends are R12.4 about (±37.5, +1.7).
- **Main PCB**, viewed from the front (front face = F.Cu). Origin at the case centre; +Y up. The bottom edge is y = −36.0.
- **Pack pad board**, viewed from the front, in the case frame (it spans x 0…24, y −19…−11).

## Boards

| Board | Size | Thickness | Mounting | Height limits |
|---|---|---|---|---|
| Top PCB | 99.8 × 26.5 curved pill | 1.6, 2 layers | 4 × M2 (2.2 mm holes) at (±20, −9.0), (±20, +10.5) into top-plate bosses | F: 3.0 (2.5 under keycap flanges, 1.4 under the OLED glass). B: encoders 6.5; nothing else inside R17.4 of each dial axis; ≈4 elsewhere |
| Main PCB | 87.5 × 64.5 stepped | 1.6, 4 layers | 5 × M2: H1 (−30, −9) is an 18 mm M-F standoff, H2 (38, 12), H3 (−6, 25.5), H4 (38, −32.5), H5 (−10, −32.5) | F: 5.0 (4.0 inside |x| < 29, 7.7 < y < 27.1, behind the button recess). B: 3.7 over the battery pack (x −13.8…39.8, y −31.3…15.3); ≈15 elsewhere |
| Pack pad board | 24 × 8 | 0.8, ENIG | glued into the pack | 3 pads, 3 mm, at x 6/12/18, y −15 |

## Things the case expects

- **Bottom-edge parts** (main PCB, F side): USB4105 centred x 9.0 with its mouth 0.8 past the edge; PJ-320D centred x 22.0, nose 2.1 past the edge;
  side tact switch centred x −3.0 with its actuator 0.4 past the edge; 3 mm LED at x 32.0, axis 2.0 off the board, lens 1.8 past the edge.
- **Front buttons**: PTS815 at (−18, 17.4), (0, 17.4), (18, 17.4) on the F side. The printed caps press straight down on them.
- **Top keys**: PTS815 centred under each keycap; the cap flange sits on the switch, so keep the switch height at 2.5.
- **Encoders**: PEC12R footprints on the B side of the top board at (±37.5, 1.7); the shaft points down into the dial hub.
- **OLED**: glass 34.5 × 23.0 sits on 1.5 mm foam on the F side, its FPC wraps round the back-edge notch (|X| < 16) to a connector on the B side near (0, 8).
- **Board link**: 10-way JST SH. Top board B side at (−10, −1.35), top-entry; main board B side at the tab top, x 8, side-entry pointing up.
- **Radio**: U.FL at (31, 10.5), B side. Keep copper back from the right-hand edge; the flex antenna sits on the inside of the right end, about 8 mm away.
- **ESP32-S3**: antenna end flush with the left edge (x −46.5); no copper on any layer under the antenna (x < −39.5).
- **Pogo pins**: three Mill-Max 0906 at (6/12/18, −15), B side, THT. They compress 0.8 mm onto the pack pads.

## Check before layout

These envelopes are typical figures, not confirmed against a drawing: PEC12R body height (6.5), the XLR D-flange (31 × 26 × 2) and depth (21),
USB4105 body, PTS815 height variant, the side tact switch, JST SH bodies, and where your OLED panel's active area sits on the glass.
