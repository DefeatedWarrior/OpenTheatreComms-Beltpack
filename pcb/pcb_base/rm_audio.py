"""Remove the optional audio section from the finished base board: its 38 parts, every track and via of the audio-only
nets and of the I2S / headset-detect nets (now single-ended), and the stubs on shared nets (I2C, +3V3, GND) that ran only
to audio pads. Everything else stays exactly as routed.

  python3 rm_audio.py board.kicad_pcb
"""
import os, sys
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import Bf, polyset_to_shapely, net_islands
from shapely.geometry import Point
from shapely.ops import unary_union
import design_audio as design            # a copy of design.py from before the audio block was taken out (one-off script)
path = sys.argv[1]
b = pcbnew.LoadBoard(path)
aud = {c["ref"] for c in design.C if c.get("block") == "Audio"}
nets_aud = {n for c in design.C if c["ref"] in aud for n in c["pins"].values() if n}
nets_keep = {n for c in design.C if c["ref"] not in aud for n in c["pins"].values() if n}
drop_nets = {"/" + n for n in nets_aud - nets_keep} | {"/" + n for n in ("HS_DET", "I2S_BCLK", "I2S_DIN", "I2S_DOUT", "I2S_FS", "I2S_MCLK")}
gone = []
for f in list(b.GetFootprints()):
    if f.GetReference() in aud:
        gone += [polyset_to_shapely(p.GetEffectivePolygon()) for p in f.Pads()]
        b.Delete(f)
gone_area = unary_union(gone).buffer(0.05)
n_net = 0
for t in list(b.GetTracks()):
    if t.GetNetname() in drop_nets: b.Delete(t); n_net += 1
# dead ends on the shared nets: only tracks/vias that ended on an audio pad, followed back while they stay dead ends
pads = {}
for f in b.GetFootprints():
    for p in f.Pads(): pads.setdefault(p.GetNetname(), []).append(polyset_to_shapely(p.GetEffectivePolygon()))
seeds = set()
for t in b.GetTracks():
    if t.GetClass() == "PCB_TRACK":
        for e in (t.GetStart(), t.GetEnd()):
            if gone_area.contains(Point(*Bf(e))): seeds.add((t.GetNetname(), e.x, e.y))
n_stub = 0
while seeds:
    net, x, y = seeds.pop()
    items = [t for t in b.GetTracks() if t.GetNetname() == net and (
        (t.GetClass() == "PCB_TRACK" and ((t.GetStart().x, t.GetStart().y) == (x, y) or (t.GetEnd().x, t.GetEnd().y) == (x, y))) or
        (t.GetClass() == "PCB_VIA" and (t.GetPosition().x, t.GetPosition().y) == (x, y)))]
    on_pad = any(pp.distance(Point(*Bf(pcbnew.VECTOR2I(x, y)))) < 0.01 for pp in pads.get(net, []))
    vias = [t for t in items if t.GetClass() == "PCB_VIA"]; trs = [t for t in items if t.GetClass() == "PCB_TRACK"]
    if on_pad or len(trs) > 1 or (vias and len(trs) > 1): continue
    if vias and len(trs) == 0: continue                                   # a via that reaches a pour on another layer: keep
    for t in trs:
        other = t.GetEnd() if (t.GetStart().x, t.GetStart().y) == (x, y) else t.GetStart()
        b.Delete(t); n_stub += 1; seeds.add((net, other.x, other.y))
    for v in vias:
        b.Delete(v); n_stub += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(path)
b = pcbnew.LoadBoard(path)
inc = {n: len(g) for n, g in net_islands(b, skip=("", "GND")).items() if len(g) > 1}
print(f"removed {len(aud)} parts, {n_net} tracks/vias on dropped nets, {n_stub} stub pieces; incomplete nets: {inc}")
