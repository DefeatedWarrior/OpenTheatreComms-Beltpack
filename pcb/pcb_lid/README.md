# pcb_lid: build scripts for the pack lid PCB

Everything in `kicad_proj/pack_lid_pcb/` is generated from `design.py` (every part, its nets and its board position).

| Step | Command | Output |
|---|---|---|
| 1. Schematic | `python3 make_sch.py` | `out/pack_lid_pcb.kicad_sch`, `out/pack_lid_pcb_schinfo.json` (deterministic UUIDs, so footprint links survive a rebuild) |
| 2. Netlist check | `kicad-cli sch export netlist -o out/pack_lid_pcb.net out/pack_lid_pcb.kicad_sch` then `python3 chknet.py` | Should report 3 nets, 0 mismatches |
| 3. Board | `python3 make_pcb.py` | `kicad_proj/pack_lid_pcb/pack_lid_pcb.kicad_pcb` (+ schematic copy), DRC in `out/drc.rpt` |
| 4. Fab | `python3 make_fab.py` | `kicad_proj/pack_lid_pcb/fab/`: Gerbers + drill zip, schematic PDF, previews, DRC |

The board starts from `template/pack_lid_pcb.kicad_pcb` (the 24 x 8 mm outline and the enclosure reference). Needs KiCad 7
(pcbnew Python and kicad-cli), plus `cairosvg` and Pillow for the previews.
