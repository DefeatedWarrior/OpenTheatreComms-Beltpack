# OpenTheatreComms beltpack: KiCad starter pack

Three ready-to-open KiCad projects, one per board, generated from the CadQuery reference model. They were written with
KiCad 7 and open in KiCad 7, 8 and 9 (newer versions offer to upgrade the files on first save).

| Folder | Board | Size | Build |
|---|---|---|---|
| `top_pcb/` | Top PCB under the keys | 99.8 × 26.5 mm curved pill | 1.6 mm, 2 layers |
| `main_pcb/` | Main PCB behind the front | 87.5 × 64.5 mm stepped | 1.6 mm, 4 layers |
| `pack_lid_pcb/` | Battery pack pad board | 24 × 8 mm | 0.8 mm, 2 layers, ENIG |

## What's already in each project

- **Edge.Cuts**: the exact outline with true arcs (front edge R427.4 and back edge R402.6 on the top board).
- **Mounting holes**: M2 NPTH footprints (`H1`…) at the positions the case expects. They are fixed by the case, so leave them where they are.
- **Keep-outs**: on the main board, a no-copper rule area along the left-hand strip (x < −39.5), where the ESP32-S3's
  Wi-Fi antenna and 915 MHz antenna B both sit.
- **Placement guides**: `Place.F` (User.1) shows front/top-side parts, `Place.B` (User.2) shows back/bottom-side parts and `Case.Ref` (User.3)
  shows keycaps, dials, button caps, the OLED glass, the battery outline and case bosses. Notes and height limits are on `Cmts.User`.
- **Datum**: the grid origin and the drill/place origin are set to the board datum, so the status bar coordinates match
  `placement.csv` (flip the sign of Y: KiCad's Y points down).
- **3D**: a locked, board-only footprint `REF**` carries `3d/enclosure_ref.step`, so *View → 3D Viewer* shows the case,
  dials, keycaps, XLR and battery pack around the board. Keep the `3d/` folder next to the project folders.
- **Schematic**: an empty sheet with the title block filled in.

## Suggested workflow

1. Draw the schematic, assign footprints, then *Update PCB from Schematic*.
2. Fill in the `ref` column of the project's `placement_map.csv` with your references (U1, J3, SW2…). Add `rot` in degrees if you want to set
   rotations too.
3. In the PCB editor open *Tools → Scripting Console* and run `exec(open(r"<path>/place_parts.py").read())`. Every listed footprint jumps to its
   position and side. Positions are part centres; footprints anchored on pin 1 (the PEC12R, for example) need a small nudge.
4. Route, then check the fit in the 3D viewer against the enclosure.

## Frames

- **Top PCB**: viewed from above, F.Cu = top side. Origin at the board centre (15 mm behind the case front); +X right, +Y toward the hip edge.
  Encoders at (±37.5, +1.7) on B.Cu, shafts pointing down into the dial hubs.
- **Main PCB**: viewed from the front, F.Cu = front face. Origin at the case centre; +Y up. The bottom edge is at Y = −36.0.
- **Pack pad board**: viewed from the front, same frame as the main PCB.

## Height limits

| Board | Side | Limit |
|---|---|---|
| Top | F (top) | 3.0 mm; 2.5 under keycap flanges (the PTS815 itself); 1.4 under the OLED glass (it sits on 1.5 mm foam) |
| Top | B (bottom) | Encoders 6.5 mm; nothing else inside R17.4 of each dial axis; about 4 mm elsewhere |
| Main | F (front) | 5.0 mm; 4.0 mm behind the button recess (\|x\| < 29, 7.7 < y < 27.1) |
| Main | B (back) | 3.7 mm over the battery pack (x −13.8…39.8, y −31.3…15.3); about 15 mm elsewhere |

## Things the case expects

- Bottom edge, main PCB F side: USB4105 centred x 9.0 with the mouth 0.8 past the edge; PJ-320D at x 22.0 with the nose 2.1 past;
  side tact switch at x −3.0 with the actuator 0.4 past; 3 mm LED at x 32.0, axis 2.0 off the board, bent 90°.
- Front buttons: PTS815 at (−18, 17.4), (0, 17.4), (18, 17.4) on the main PCB F side.
- Board link: 10-way JST SH. BM10B (top entry) on the top board B side at (−10, −1.35); SM10B (side entry) on the main board B side at the
  tab top, x 8, mouth pointing up. Use a 50 mm cable; it folds behind the tab.
- Radio, with switched antenna diversity: LR2021 ANT_LF → unpopulated pi match → pSemi PE4259 SPDT at (25.8, 4.0) → U.FL A at (31, 10.5)
  and U.FL B at (24.5, 10.5), all on the main board B side. Put 100 pF DC-block footprints on the switch ports (fit or bridge per the
  datasheet) and drive CTRL from an ESP32 GPIO. Antenna A sits inside the right end, about 8 mm past the board edge; antenna B sits inside
  the left end, 3 mm past the edge, which is why that strip has no copper.
- Pogo pins: three Mill-Max 0906 at (6/12/18, −15), B side, through-hole; they compress 0.8 mm onto the pack pads.

## Check before layout

Typical sizes not yet confirmed against a drawing: PEC12R body height (6.5), the XLR D-flange (31 × 26 × 2) and depth (21),
the USB4105 body, the PTS815 height variant, the side tact switch, the JST SH bodies, and where your OLED panel's active area sits on its glass.

## Also in this pack

- `dxf/`: the outlines (`*_edge_cuts.dxf`) and the full guide drawings, if you prefer to import graphics yourself.
- `drawings/`: dimensioned drawings of each board and two sections through the case.
- `placement.csv`: every part centre, envelope and height, plus the holes.
