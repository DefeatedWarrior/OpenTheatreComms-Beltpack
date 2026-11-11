# OpenTheatreComms: KiCad projects

The five v1 boards, each a finished KiCad project (schematic, routed board, `fab/` outputs and a README). They were
written with KiCad 7 and open in KiCad 7, 8 and 9 (newer versions offer to upgrade the files on first save). Every board
passes DRC with 0 errors and 0 unconnected pads. The Python that generates them is in `../pcb/`; the order is in `../order/`.

| Folder | Board | Size | Build |
|---|---|---|---|
| `main_pcb/` | Beltpack main board behind the front: ESP32-S3, LR2021 radio, codec, power, connectors | 87.5 × 64.5 mm stepped | 1.6 mm, 4 layers |
| `top_pcb/` | Beltpack top board under the keys: OLED, four keys, six RGB lights (LP5024), both dials, IO expander | 99.8 × 26.5 mm curved pill | 1.6 mm, 2 layers |
| `pack_lid_pcb/` | Battery pack pad board (spring-pin contacts) | 24 × 8 mm | 0.8 mm, 2 layers |
| `dock_contact_pcb/` | Dock contact board in the case bottom | 22 × 11 mm | 0.8 mm, 2 layers |
| `base_pcb/` | Base station carrier for the ESP32-P4-NANO | 150 × 90 mm | 1.6 mm, 2 layers |

All five are ordered with leaded HASL (see `../order/ORDER_README.md`).

Each project keeps the CadQuery reference layers it started from: `Place.F` (User.1), `Place.B` (User.2) and `Case.Ref`
(User.3) show where the case expects parts, and a locked board-only footprint `REF**` carries `3d/enclosure_ref.step`, so
*View → 3D Viewer* shows the case around the beltpack boards. Keep the `3d/` folder next to the project folders.
`place_parts.py` is the original placement helper (from `placement_map.csv`); the finished boards no longer need it.

## Frames

- **Top PCB**: viewed from above, F.Cu = top side. Origin at the board centre (15 mm behind the case front); +X right, +Y toward the hip edge.
  Encoders at (±37.5, +1.7) on B.Cu, shafts pointing down into the dial hubs.
- **Main PCB**: viewed from the front, F.Cu = front face. Origin at the case centre; +Y up. The bottom edge is at Y = −36.0.
- **Pack pad board**: viewed from the front, same frame as the main PCB.
- **Dock contact and base boards**: see their own READMEs.

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
- Radio, with switched antenna diversity: LR2021 ANT_LF → unpopulated pi match → PE4259-type SPDT (HX4259-63 fitted) at (25.8, 4.0) → U.FL A at (31, 10.5)
  and U.FL B at (24.5, 10.5), all on the main board B side. Put 100 pF DC-block footprints on the switch ports (fit or bridge per the
  datasheet) and drive CTRL from an ESP32 GPIO. Antenna A sits inside the right end, about 8 mm past the board edge; antenna B sits inside
  the left end, 3 mm past the edge, which is why that strip has no copper.
- Pogo pins: three Xinyangze YZ08415060P-02 at (6/12/18, −15), B side, through-hole (1.0 mm holes); the pack pads sit 4.0 mm
  from the back face (the pins' working height). J11, a JST XH 2-pin battery input, sits on the front at (18.5, −11).

## Check against the parts you buy

Typical sizes not yet confirmed against a drawing: PEC12R body height (6.5), the XLR D-flange (31 × 26 × 2) and depth (21),
the USB4105 body, the PTS815 height variant, the side tact switch, the JST SH bodies, and where your OLED panel's active area sits on its glass.

## Also in this pack

- `dxf/`: the outlines (`*_edge_cuts.dxf`) and the full guide drawings, if you prefer to import graphics yourself.
- `drawings/`: dimensioned drawings of each board and two sections through the case.
- `placement.csv`: every part centre, envelope and height, plus the holes.
