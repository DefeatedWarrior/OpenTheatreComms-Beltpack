# Top PCB build scripts

The top PCB (keys, key and status lights, OLED connector, both dials, IO expander, link to the main PCB) is generated
from one file, `design.py`, which holds every part, its nets, its schematic position and its board position.

```sh
python3 make_lib.py                                   # the OLED tail pads footprint
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
| `make_lib.py` | Writes `lib/OpenTheatreComms.pretty`: the 30 solder pads (0.7 mm) for the OLED panel's tail |
| `symlib.py`, `sexp.py` | Read KiCad library symbols, read and write S-expressions |
| `make_sch.py`, `chknet.py` | Schematic writer and netlist check |
| `pcbgeom.py` | Board-frame transforms, copper model for via placement, per-net connectivity check |
| `make_pcb.py`, `finish_pcb.py` | Board build |
| `make_fab.py`, `render.py` | Fab outputs and PNG previews |
| `template/` | The starter board (outline, holes, guides, enclosure 3D reference) the build starts from |

Board frame: origin at the board centre, +X right, +Y toward the hip (back) edge, viewed from above (F = top).
