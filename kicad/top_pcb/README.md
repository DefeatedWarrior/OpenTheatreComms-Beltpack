# Top PCB build scripts

The top PCB (keys, six RGB lights, OLED connector, both dials, IO expander, LED driver, link to the main PCB) is generated
from one file, `design.py`, which holds every part, its nets, its schematic position and its board position.

```sh
python3 make_lib.py                                   # the OLED tail pads footprint and the LP5024 symbol
python3 make_sch.py                                   # out/top_pcb.kicad_sch (KiCad 7 format, real library symbols)
kicad-cli sch export netlist --format kicadsexpr -o out/top_pcb.net out/top_pcb.kicad_sch
python3 chknet.py out/top_pcb.net                     # every net must match design.py
python3 make_pcb.py                                   # place, pre-route the FPC fan-outs, GND fanouts, route with Freerouting 1.9 -> out/routed.kicad_pcb
                                                      # (make_pcb.py import: re-import the last routing session without rerouting)
python3 finish_pcb.py                                 # GND pours, stitching, repair, DRC -> ../kicad_proj/top_pcb/
python3 make_fab.py                                   # Gerbers, drill, placement, BOM, assembly PDFs -> ../kicad_proj/top_pcb/fab/
```

Needs KiCad 7+ (`pcbnew` Python module and `kicad-cli`), the KiCad symbol and footprint libraries, Java, `xvfb-run`,
Freerouting 1.9.0 (`FREEROUTING` in `make_pcb.py`), and Python `shapely` and `cairosvg`.

| File | Role |
|---|---|
| `design.py` | Parts, nets, schematic and board positions; `OLED_PIN1_AT_PLUS_X` flips the panel pin order |
| `make_lib.py` | Writes `lib/OpenTheatreComms.pretty` (the 30 solder pads, 0.7 mm, for the OLED panel's tail) and `lib/OpenTheatreComms.kicad_sym` (TI LP5024) |
| `symlib.py`, `sexp.py` | Read KiCad library symbols, read and write S-expressions |
| `make_sch.py`, `chknet.py` | Schematic writer and netlist check |
| `pcbgeom.py` | Board-frame transforms, copper model for via placement, per-net connectivity check |
| `make_pcb.py`, `finish_pcb.py` | Board build |
| `make_fab.py`, `render.py` | Fab outputs and PNG previews |
| `template/` | The starter board (outline, holes, guides, enclosure 3D reference) the build starts from |

Board frame: origin at the board centre, +X right, +Y toward the hip (back) edge, viewed from above (F = top).

## Lights

Six common-anode RGB LEDs (Lite-On LTST-C19HE1WT, 1.6 x 1.6 mm): D1-D4 above the four talk keys, D5 and D6 under the
left and right status light pipes. Each is driven by a TI LP5024 (U2, on the bottom side) on the board's I2C bus, so
every LED takes any colour and brightness from firmware:

| Light | LP5024 channel | Outputs (R, G, B) |
|---|---|---|
| D1, talk key 1 | LED0 | OUT0-OUT2 |
| D2, talk key 2 | LED1 | OUT3-OUT5 |
| D5, status left | LED2 | OUT6-OUT8 |
| D3, talk key 3 | LED3 | OUT9-OUT11 |
| D4, talk key 4 | LED4 | OUT12-OUT14 |
| D6, status right | LED5 | OUT15-OUT17 |

The order follows the board (each light's lines leave the driver on the side facing it); `LED_CH` in `design.py` holds it.

- **Current:** R1 = 15k sets 4.9 mA full scale per colour (105 x 0.7 V / R1); the 12-bit PWM dims from there. The low
  current leaves the green and blue chips (about 2.7 V at 5 mA) headroom on the 3.3 V anode supply.
- **I2C addresses on the beltpack bus:** LP5024 0x28 (ADDR1 = ADDR0 = GND). Its broadcast address is 0x3C, so the OLED
  is strapped to **0x3D** (D/C# high). The IO expander is 0x20.
- **EN** comes from the expander's P05: its internal pull-up holds the driver on from power-up; firmware can pulse it low
  to reset the driver. Expander P10-P17 are now free.
