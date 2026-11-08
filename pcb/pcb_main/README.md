# Main PCB build scripts

The main PCB (USB-C charging and power path, soft power switch, fuel gauge, ESP32-S3 module, LR2021 radio module with its
RF switch and two U.FL outputs, NAU88C22 codec with the XLR headset and 3.5 mm outputs, accelerometer, IO expander, buttons,
flashlight LED, vibration motor and the link to the top PCB) is generated from one file, `design.py`, which holds every part,
its nets, its schematic block and either an exact board position or a "near" anchor for the automatic placer.

```sh
python3 customlib.py                                  # lib/OpenTheatreComms.kicad_sym and .pretty (codec, charger, gauge, RF switch, radio module, pogo pin, motor)
python3 make_sch.py                                   # out/main_pcb.kicad_sch (A1 sheet, one box per block)
kicad-cli sch export netlist --format kicadsexpr -o out/main_pcb.net out/main_pcb.kicad_sch
python3 chknet.py out/main_pcb.net                    # every net must match design.py
python3 make_pcb.py                                   # place, RF chain, plane fanouts, pin escapes, Freerouting 1.9 on F, In1 and B -> out/routed.kicad_pcb
                                                      # (make_pcb.py place: stop before routing; make_pcb.py import: re-import the last session)
python3 maze.py out/routed.kicad_pcb out/routed.kicad_pcb   # grid router (with rip-up) for whatever Freerouting left
python3 finish_pcb.py                                 # tidy stubs, pours (GND on F, In2 and B; +3V3 on In1), stitching, repair, silk, DRC -> ../kicad_proj/main_pcb/
python3 make_fab.py                                   # Gerbers, drill, placement, BOM, assembly PDF, preview -> ../kicad_proj/main_pcb/fab/
python3 fitcheck.py ../kicad_proj/main_pcb/main_pcb.kicad_pcb   # every part's box against the enclosure solids in ../out/brep
```

Needs KiCad 7+ (`pcbnew` Python module and `kicad-cli`), the KiCad symbol and footprint libraries, Java, `xvfb-run`,
Freerouting 1.9.0 (`FREEROUTING` in `make_pcb.py`), Python `shapely`, `matplotlib` and `cairosvg`, and CadQuery for `fitcheck.py`.

| File | Role |
|---|---|
| `design.py` | Parts, nets, blocks, board positions and placer anchors, part numbers and notes |
| `customlib.py` | The project symbol and footprint library (written to `lib/`, copied into the KiCad project) |
| `symlib.py`, `sexp.py` | Read KiCad library symbols, read and write S-expressions |
| `make_sch.py`, `chknet.py` | Schematic writer and netlist check |
| `pcbgeom.py` | Board-frame transforms, copper model for via placement, per-net connectivity check |
| `make_pcb.py`, `maze.py`, `route2.py`, `finish_pcb.py` | Board build (`route2.py`: an optional second Freerouting round; `fixroute.py`: rip up spots by hand; `movepart.py`: move a stuck two-pad part next to its net) |
| `make_fab.py`, `make_assembly.py`, `render_board.py` | Fab outputs, assembly sheets and the preview |
| `fitcheck.py`, `zoomplot.py`, `render.py` | Enclosure clash check and debug plots |
| `template/` | The starter board (outline, mounting holes, antenna keep-out) the build starts from |

Board frame: origin at the enclosure centre, +X right, +Y up, viewed from the front. F (top copper) faces the front shell,
B faces the battery pack. The layer stack is F signal + GND, In1 signal + +3V3 pour, In2 solid GND plane, B signal + GND.

How the routing is set up: GND never goes to the router. Every GND pad gets its own via (or a short track to an
exposed pad), done by script before routing, and those vias and tracks go to Freerouting as keep-outs. +3V3 pads get
their vias the same way, but +3V3 is then routed like any other (power) net, because In1 is a routing layer as well as
the +3V3 pour and the pour alone can be cut into pieces by the tracks on it. The fine-pitch chips (codec, fuel gauge,
accelerometer) and the USB-C VBUS pads get scripted escape vias first, and the auto-placer leaves a free ring round the
fine-pitch chips and 0.35 mm between parts, because Freerouting can't get out of a 0.5 mm-pitch QFN reliably on its own.
The RF chain (LR2021 to the switch to the two U.FLs) is laid by script as 0.35 mm coplanar waveguide over the In2 ground
and locked. The codec's support parts are placed after its fan, beside the via of the pin each one serves.
Freerouting usually leaves a couple of connections in the crowded lower middle; `maze.py` finishes most of them
(its rip-up is off by default, `MAZE_RIPTOTAL=N` turns it on, but on this board it tends to cascade).
