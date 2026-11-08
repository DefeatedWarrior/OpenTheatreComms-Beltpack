"""Board-frame helpers shared by the top PCB scripts: coordinate transforms, a shapely copper model (with a spatial index)
for finding free spots for vias, and a geometric connectivity check per net."""
import pcbnew
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

MM = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(MM(float(150 + x)), MM(float(105 - y)))
def Bf(v): return (pcbnew.ToMM(v.x) - 150.0, 105.0 - pcbnew.ToMM(v.y))
def mm(v): return pcbnew.ToMM(v)
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)

def chain_pts(ch):
    return [Bf(ch.CPoint(i)) for i in range(ch.PointCount())]
def polyset_to_shapely(sps):
    polys = []
    for i in range(sps.OutlineCount()):
        outer = chain_pts(sps.Outline(i))
        holes = [chain_pts(sps.Hole(i, h)) for h in range(sps.HoleCount(i))]
        if len(outer) >= 3: polys.append(Polygon(outer, [h for h in holes if len(h) >= 3]))
    return unary_union(polys) if polys else Polygon()
def board_outline(b):
    sps = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(sps); return polyset_to_shapely(sps)

def copper_items(b):
    """(net, layer, geometry, kind, ref) for every pad, track and via; vias and PTH pads appear on both layers."""
    out = []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            g = polyset_to_shapely(pad.GetEffectivePolygon())
            if g.is_empty: continue
            for L in LAYERS:
                if pad.IsOnLayer(L): out.append((pad.GetNetname(), L, g, "pad", (fp.GetReference(), pad.GetNumber())))
    for t in b.GetTracks():
        w = mm(t.GetWidth()) / 2
        if t.GetClass() == "PCB_VIA":
            g = Point(*Bf(t.GetPosition())).buffer(w)
            for L in LAYERS: out.append((t.GetNetname(), L, g, "via", None))
        elif t.GetLayer() in LAYERS:
            a, c = Bf(t.GetStart()), Bf(t.GetEnd())
            g = LineString([a, c]).buffer(w) if a != c else Point(a).buffer(w)
            out.append((t.GetNetname(), t.GetLayer(), g, "track", None))
    return out

def net_islands(b, skip=("", "GND")):
    """For every net with 2+ pads: the groups of pads that copper joins. One group means the net is complete."""
    items = [it for it in copper_items(b) if it[0] not in skip and not it[0].startswith("unconnected")]
    res = {}
    by_net = {}
    for i, it in enumerate(items): by_net.setdefault(it[0], []).append(i)
    for net, idx in by_net.items():
        parent = {i: i for i in idx}
        def f(i):
            while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
            return i
        geoms = [items[i][2].buffer(0.001) for i in idx]
        tree = STRtree(geoms)
        for a, ia in enumerate(idx):
            for bpos in tree.query(geoms[a]):
                ib = idx[bpos]
                if ib <= ia or items[ia][1] != items[ib][1]: continue
                if geoms[a].intersects(geoms[bpos]): parent[f(ia)] = f(ib)
        first_of = {}
        for i in idx:                                   # a through-hole pad or via is one item on both layers
            key = items[i][4] if items[i][3] == "pad" else (items[i][3], items[i][2].centroid.coords[0]) if items[i][3] == "via" else None
            if key is None: continue
            if key in first_of: parent[f(i)] = f(first_of[key])
            else: first_of[key] = i
        groups = {}
        for i in idx:
            if items[i][3] == "pad": groups.setdefault(f(i), set()).add(items[i][4])
        if sum(len(g) for g in groups.values()) >= 2: res[net] = list(groups.values())
    return res

class Copper:
    """Copper per layer, tagged by net, with a spatial index; new tracks and vias go in a small side list."""
    def __init__(self, b):
        self.b = b; self.base = {L: [] for L in LAYERS}; self.extra = {L: [] for L in LAYERS}; self.holes = []
        for net, L, g, kind, ref in copper_items(b):
            if kind != "track" or True: self.base[L].append((net, g, kind))
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.HasHole():
                    x, y = Bf(pad.GetPosition()); self.holes.append(Point(x, y).buffer(mm(pad.GetDrillSize().x) / 2))
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                x, y = Bf(t.GetPosition()); self.holes.append(Point(x, y).buffer(mm(t.GetDrillValue()) / 2))
        self.tree = {L: STRtree([g for _, g, _ in self.base[L]]) for L in LAYERS}
        self.edge = board_outline(b); self.inner = {}
    def add_track(self, t):
        if t.GetClass() == "PCB_VIA":
            x, y = Bf(t.GetPosition()); g = Point(x, y).buffer(mm(t.GetWidth()) / 2)
            for L in LAYERS: self.extra[L].append((t.GetNetname(), g, "via"))
            self.holes.append(Point(x, y).buffer(mm(t.GetDrillValue()) / 2))
        else:
            a, c = Bf(t.GetStart()), Bf(t.GetEnd())
            g = LineString([a, c]).buffer(mm(t.GetWidth()) / 2) if a != c else Point(a).buffer(mm(t.GetWidth()) / 2)
            if t.GetLayer() in self.extra: self.extra[t.GetLayer()].append((t.GetNetname(), g, "track"))
    def clear(self, geom, net, layers, clearance=0.2, pads_any_net=True, edge=0.5):
        """True when geom keeps `clearance` from every other-net item (and from every pad, if asked) on the layers."""
        if edge not in self.inner: self.inner[edge] = self.edge.buffer(-edge)
        if not self.inner[edge].contains(geom): return False
        probe = geom.buffer(clearance)
        for L in layers:
            cands = [self.base[L][i] for i in self.tree[L].query(probe)] + self.extra[L]
            for n, g, kind in cands:
                if (n != net or (pads_any_net and kind == "pad")) and g.distance(geom) < clearance: return False
        return True
    def via_ok(self, x, y, net, r=0.3, clearance=0.2):
        g = Point(x, y).buffer(r)
        if any(h.distance(g) < 0.25 for h in self.holes if h.distance(Point(x, y)) < 3): return False
        return self.clear(g, net, LAYERS, clearance)
