#!/bin/sh
# Stage and zip the KiCad starter pack from kicad_proj/ and out/kicad/
set -e
HERE=$(cd "$(dirname "$0")" && pwd); STAGE=$(mktemp -d); Z=$STAGE/beltpack_kicad
mkdir -p $Z/dxf $Z/drawings $Z/3d
for n in top_pcb main_pcb pack_lid_pcb; do
  mkdir -p $Z/$n
  cp $HERE/kicad_proj/$n/$n.kicad_pro $HERE/kicad_proj/$n/$n.kicad_pcb $HERE/kicad_proj/$n/$n.kicad_sch $HERE/kicad_proj/$n/placement_map.csv $Z/$n/
done
cp $HERE/kicad_proj/3d/enclosure_ref.step $Z/3d/
cp $HERE/kicad_proj/place_parts.py $HERE/kicad_proj/README.md $HERE/out/kicad/placement.csv $Z/
cp $HERE/out/kicad/*.dxf $Z/dxf/
cp $HERE/out/kicad/*_drawing.png $HERE/out/kicad/section_*.png $Z/drawings/
rm -f "$1"; (cd $STAGE && zip -qr "$1" beltpack_kicad); rm -rf $STAGE
echo "$1"
