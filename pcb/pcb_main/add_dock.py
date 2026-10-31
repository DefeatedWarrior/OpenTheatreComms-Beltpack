"""Add the dock connection to the finished main board.

J12  JST SH 4-pin vertical (BM04B-SRSS-TB) on the back face at the bottom edge, below the battery pack (pack underside
     y -31), so its plug points backward into the 5 mm strip under the pack. A flat 4-wire cable runs back from it to the
     dock contact board lying in the case bottom, where the dock's spring pins land.
D12  B5819W Schottky, DOCK_VBUS (anode) -> VBUS (cathode). Dock power charges the pack like USB-C does. The diode stops
     USB-C's 5 V from reaching the exposed contacts when a cable is plugged in. D+/D- are shared with the USB-C (full
     speed, short stub); U1 (USBLC6) already protects them.

Places both parts in free space (J12 near the USB-C, D12 next to J12 pin 1), then maze.py routes DOCK_VBUS, VBUS,
USB_DP and USB_DN. J12's ground pin and mounting pads get vias into the ground pour.

  python3 add_dock.py board.kicad_pcb
"""
import os, sys, math
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgeom import P, Bf, mm, MM, Copper, polyset_to_shapely, LAYERS
from shapely.geometry import Point, LineString

path = sys.argv[1]
b = pcbnew.LoadBoard(path)
if any(f.GetReference() in ("J12", "D12") for f in b.GetFootprints()): sys.exit("dock parts already on the board")
FP = "/usr/share/kicad/footprints"
def load(lib, name, ref, val):
    f = pcbnew.FootprintLoad(f"{FP}/{lib}.pretty", name); f.SetReference(ref); f.SetValue(val)
    f.SetFPID(pcbnew.LIB_ID(lib, name)); b.Add(f); return f
dock = pcbnew.NETINFO_ITEM(b, "/DOCK_VBUS"); b.Add(dock)
N = lambda n: b.FindNet(n)
j = load("Connector_JST", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical", "J12", "Dock")
d = load("Diode_SMD", "D_SOD-123", "D12", "B5819W")
jn = {"1": "/DOCK_VBUS", "2": "/USB_DP", "3": "/USB_DN", "4": "GND", "MP": "GND"}
for p in j.Pads(): p.SetNet(N(jn[p.GetNumber()]))
for p in d.Pads(): p.SetNet(N("/VBUS" if p.GetNumber() == "1" else "/DOCK_VBUS"))
for f in (j, d): f.SetPosition(P(500, 500))
b.Save(path); b = pcbnew.LoadBoard(path)
j = [f for f in b.GetFootprints() if f.GetReference() == "J12"][0]; d = [f for f in b.GetFootprints() if f.GetReference() == "D12"][0]

# lone ground stitching vias in the strip under the pack: make room (the pours stay connected through the rest)
tracked = set()
for t in b.GetTracks():
    if t.GetClass() == "PCB_TRACK": tracked |= {(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)}
removed = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND" and (t.GetPosition().x, t.GetPosition().y) not in tracked:
        vx, vy = Bf(t.GetPosition())
        if 20.5 < vx < 30.0 and vy < -31.5: b.Delete(t); removed += 1
print("stitching vias removed from the strip:", removed)
cu = Copper(b)
crt_of = lambda f, s: polyset_to_shapely(f.GetCourtyard(pcbnew.B_CrtYd if s == "B" else pcbnew.F_CrtYd))
def others(s, skip):
    o = [crt_of(f, "B" if f.IsFlipped() else "F") for f in b.GetFootprints()
         if f.GetReference() not in skip and not f.GetReference().startswith("TP") and (f.IsFlipped() == (s == "B") or f.GetReference().startswith("H"))]
    return o + [Point(*Bf(f.GetPosition())).buffer(2.7) for f in b.GetFootprints() if f.GetReference().startswith("H")]
keep = [polyset_to_shapely(z.Outline()) for z in b.Zones() if z.GetIsRuleArea()]
j1 = [f for f in b.GetFootprints() if f.GetReference() == "J1"][0]
usb_pts = [Bf(p.GetPosition()) for p in j1.Pads() if p.GetNetname() in ("/USB_DP", "/USB_DN")]
ucx, ucy = sum(x for x, _ in usb_pts) / len(usb_pts), sum(y for _, y in usb_pts) / len(usb_pts)
ymin = cu.edge.bounds[1]

def put(f, x, y, rot, side):
    f.SetPosition(P(x, y)); f.SetOrientationDegrees(0)
    if f.IsFlipped() != (side == "B"): f.Flip(P(x, y), False)
    f.SetOrientationDegrees(rot)
def fab_box(f):
    xs, ys = [], []
    for g in f.GraphicalItems():
        if g.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab):
            r = g.GetBoundingBox(); xs += [pcbnew.ToMM(r.GetX()) - 150, pcbnew.ToMM(r.GetRight()) - 150]; ys += [105 - pcbnew.ToMM(r.GetY()), 105 - pcbnew.ToMM(r.GetBottom())]
    return min(xs), min(ys), max(xs), max(ys)
PACK_UNDERSIDE = -31.0
holes = [(*Bf(p.GetPosition()), mm(p.GetDrillSize().x) / 2) for f in b.GetFootprints() for p in f.Pads()
         if p.HasHole() and f.GetReference() not in ("J12", "D12")]          # pegs and leads poke through: keep the body off them                                           # battery pack: x -13.5..39.5, y -31..15, behind the board
def fits(f, side, obs, extra=(), edge=0.8):
    crt = crt_of(f, side)
    if (edge >= 0 and not cu.edge.buffer(-edge).contains(crt)) or any(k.intersects(crt) for k in keep): return None
    for p in f.Pads():                                           # copper at least 0.4 mm from the board edge
        if not cu.edge.buffer(-0.4).contains(polyset_to_shapely(p.GetEffectivePolygon())): return None
    if any(o.intersects(crt) for o in list(obs) + list(extra)): return None
    L = pcbnew.B_Cu if side == "B" else pcbnew.F_Cu
    for p in f.Pads():
        if not p.IsOnLayer(L): continue
        if not cu.clear(polyset_to_shapely(p.GetEffectivePolygon()), p.GetNetname(), [L], 0.22, pads_any_net=False): return None
    return crt

best = None
for side in ("B",):                                              # back face: the plug points into the strip under the pack
    obs_j = others(side, ("J12", "D12"))
    for x in [k * 0.5 for k in range(-26, 81)]:                  # x -13..40, under the pack
        for y in [k * 0.25 for k in range(-144, -123)]:          # y -36..-31
            for rot in (0, 180):                                 # pin row along the edge
                put(j, x, y, rot, side)
                body = fab_box(j)                                    # the housing (and the plug above it) must clear the pack
                if body[3] > PACK_UNDERSIDE - 0.3 or body[1] < cu.edge.bounds[1] + 0.1: continue
                if any(bx0 - 0.4 < hx < bx1 + 0.4 and by0 - 0.4 < hy < by1 + 0.4 for hx, hy, r in holes for bx0, by0, bx1, by1 in [body]): continue
                cj = fits(j, side, obs_j, edge=-3.0)                 # courtyard may overhang the edge; pads are checked
                if cj is None: continue
                p1 = Bf([p for p in j.Pads() if p.GetNumber() == "1"][0].GetPosition())
                score = math.hypot(x - ucx, y - ucy)
                if best and score >= best[0]: continue
                dbest = None
                for dside in ("B", "F"):
                    obs_d = others(dside, ("J12", "D12"))
                    for dx in [k * 0.5 for k in range(-16, 17)]:
                        for dy in [k * 0.5 for k in range(-4, 17)]:
                            for drot in (0, 90, 180, 270):
                                put(d, p1[0] + dx, p1[1] + dy, drot, dside)
                                if fits(d, dside, obs_d, [cj] if dside == "B" else []) is None: continue
                                a = Bf([p for p in d.Pads() if p.GetNumber() == "2"][0].GetPosition())
                                dd = math.dist(a, p1) + (1.5 if dside != "B" else 0)
                                if dbest is None or dd < dbest[0]: dbest = (dd, p1[0] + dx, p1[1] + dy, drot, dside)
                if dbest is None: continue
                best = (score, x, y, rot, side, dbest)
if best is None: sys.exit("no spot for J12/D12")
score, x, y, rot, side, (dd, dx, dy, drot, dside) = best
put(j, x, y, rot, side); put(d, dx, dy, drot, dside)
# ground vias next to J12 pin 4 and the mounting pads
cu = Copper(b)
L = pcbnew.B_Cu if side == "B" else pcbnew.F_Cu
def gnd_via(pad):
    c = Bf(pad.GetPosition())
    for r in (0.9, 1.1, 1.3, 1.6, 2.0):
        for k in range(16):
            a = 2 * math.pi * k / 16; vx, vy = c[0] + r * math.cos(a), c[1] + r * math.sin(a)
            if not cu.via_ok(vx, vy, "GND"): continue
            t = LineString([c, (vx, vy)])
            if not cu.clear(t.buffer(0.15), "GND", [L], 0.2, pads_any_net=False): continue
            v = pcbnew.PCB_VIA(b); v.SetPosition(P(vx, vy)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(N("GND")); b.Add(v)
            tr = pcbnew.PCB_TRACK(b); tr.SetStart(P(*c)); tr.SetEnd(P(vx, vy)); tr.SetLayer(L); tr.SetWidth(MM(0.3)); tr.SetNet(N("GND")); b.Add(tr)
            cu.add_track(v); cu.add_track(tr); return True
    return False
gv = [gnd_via(p) for p in j.Pads() if p.GetNetname() == "GND"]
b.Save(path)
print(f"J12 at ({x:.2f}, {y:.2f}) rot {rot} on {side} (body y {fab_box(j)[1]:.2f}..{fab_box(j)[3]:.2f}); D12 at ({dx:.1f}, {dy:.1f}) rot {drot} on {dside}; ground vias {gv}")
