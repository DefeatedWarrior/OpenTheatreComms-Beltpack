"""Shared geometry for the final beltpack (concept v16 shape)."""
import json, math, os
import cadquery as cq
from cadquery import Solid, Vector as V, Color
OUT = os.path.dirname(os.path.abspath(__file__))
W, H, D0, T = 105.0, 77.0, 30.0, 2.2
R_B = 400.0; R_F = R_B + D0; Z_AX = -D0 - R_B; R_CF, R_CB = 8.0, 8.0; FLAT = W / 2 - R_CF
SL_Y0, SL_S, SL_C, SL_ANG = H / 2, 1.0, 0.0, -90.0     # 'slope' frame = flat top: (u, v, n) -> (u, H/2 + n, -v)
ROW_V = 15.0                                        # key/screen row centre, mm back from the front
KEYS = [(-37.5, 13.0, 13.0), (-23.5, 10.0, 10.0), (23.5, 10.0, 10.0), (37.5, 13.0, 13.0)]   # big 1/4 sit over the dial axes   # u, width, depth
OLED_ACT = (0.0, ROW_V, 29.42, 14.7); GW, GH, GV0 = 34.5, 23.0, ROW_V - 11.5
XE = W / 2 - D0 / 2                                  # centres of the semicircular ends
DR_TOP, DH = D0 / 2, 12.0; DR_BOT = DR_TOP - DH * math.tan(math.radians(15.0))   # sides 15 deg off vertical, wide end up, flush
SHOULDER_R = 4.0
DX = XE; DZ = None; DY1 = H / 2 - 7.6; DY0 = DY1 - DH
CAP_H = 7.0
BAND = 1.6

def back_z(x, off=0.0): return Z_AX + math.sqrt((R_B + off) ** 2 - x ** 2)
def W_(s): return cq.Workplane("XY").add(s) if isinstance(s, cq.Shape) else s
def solid(wp):
    s = wp.val() if isinstance(wp, cq.Workplane) else wp
    if isinstance(s, cq.Compound) and len(s.Solids()) == 1: return s.Solids()[0]
    return s
def box(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    return Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
def cylY(x, z, r, y0, y1): return Solid.makeCylinder(r, abs(y1 - y0), V(x, min(y0, y1), z), V(0, 1, 0))
def cylZ(x, y, r, z0, z1): return Solid.makeCylinder(r, abs(z1 - z0), V(x, y, min(z0, z1)), V(0, 0, 1))
def rrect(w, h, z0, z1, r, cx=0.0, cy=0.0):
    return cq.Workplane("XY").sketch().rect(w, h).vertices().fillet(r).finalize().extrude(abs(z1 - z0)).translate((cx, cy, min(z0, z1)))
def axis_cyl(r, y0=-H / 2 - 8, y1=H / 2 + 8): return Solid.makeCylinder(r, y1 - y0, V(0, y0, Z_AX), V(0, 1, 0))
def arc_shell(r0, r1, y0=-H / 2 - 8, y1=H / 2 + 8): return W_(axis_cyl(r1, y0, y1)).cut(axis_cyl(r0, y0 - 1, y1 + 1))
def to_slope(s): return W_(s).rotate((0, 0, 0), (1, 0, 0), SL_ANG).translate((0, SL_Y0, 0))
def text_solid(t, size, depth): return cq.Workplane("XY").text(t, size, depth, font="DejaVu Sans", kind="bold", halign="center", valign="center")

def front_z(x, off=0.0): return Z_AX + math.sqrt((R_F + off) ** 2 - x ** 2)
def _mid(c, p, q, r):
    v1 = ((p[0] - c[0]), (p[1] - c[1])); v2 = ((q[0] - c[0]), (q[1] - c[1]))
    n1, n2 = math.hypot(*v1), math.hypot(*v2); m = (v1[0] / n1 + v2[0] / n2, v1[1] / n1 + v2[1] / n2); nm = math.hypot(*m)
    return (c[0] + r * m[0] / nm, c[1] + r * m[1] / nm)
def plan_solid(i):
    rf, rb, rr = R_F - i, R_B + i, D0 / 2 - i
    zc = Z_AX + math.sqrt((R_B + D0 / 2) ** 2 - XE ** 2)
    th = math.atan2(XE, zc - Z_AX); L = 600.0; y0, y1 = -H / 2 - 8, H / 2 + 8
    wedge = (cq.Workplane("XZ").polyline([(0.0, Z_AX), (L * math.sin(th), Z_AX + L * math.cos(th)), (-L * math.sin(th), Z_AX + L * math.cos(th))])
             .close().extrude(y1 - y0).translate((0, y1, 0)))
    sector = W_(arc_shell(rb, rf)).intersect(wedge)                      # radial ends meet the end discs exactly
    for sx in (-1, 1): sector = sector.union(cylY(sx * XE, zc, rr, -H / 2 - 8, H / 2 + 8))
    return sector

def fillet_poly(plane, pts, radii):
    n = len(pts); data = []
    for i in range(n):
        P, Pp, Pn, r = pts[i], pts[i - 1], pts[(i + 1) % n], radii[i]
        if r <= 0: data.append((P, P, None)); continue
        ui = (P[0] - Pp[0], P[1] - Pp[1]); li = math.hypot(*ui); ui = (ui[0] / li, ui[1] / li)
        uo = (Pn[0] - P[0], Pn[1] - P[1]); lo = math.hypot(*uo); uo = (uo[0] / lo, uo[1] / lo)
        th = math.acos(max(-1.0, min(1.0, ui[0] * uo[0] + ui[1] * uo[1]))); t = r * math.tan(th / 2)
        A = (P[0] - ui[0] * t, P[1] - ui[1] * t); B = (P[0] + uo[0] * t, P[1] + uo[1] * t)
        w = (uo[0] - ui[0], uo[1] - ui[1]); lw = math.hypot(*w); w = (w[0] / lw, w[1] / lw); d = r / math.cos(th / 2)
        data.append((A, B, (P[0] + w[0] * (d - r), P[1] + w[1] * (d - r))))
    wp = cq.Workplane(plane).moveTo(*data[0][1])
    for i in list(range(1, n)) + [0]:
        A, B, M = data[i]; wp = wp.lineTo(*A)
        if M is not None: wp = wp.threePointArc(M, B)
    return wp.close()

EDGE_R = 3.5
def key_v(u): return -(Z_AX + (math.sqrt((R_F) ** 2 - u ** 2) + math.sqrt(R_B ** 2 - u ** 2)) / 2)

def body(i):
    b_ = plan_solid(i).intersect(box(-W, W, -H / 2 + i, H / 2 - i, -120, 20))
    r = max(EDGE_R - i, 0.4)
    for sel in (">Y", "<Y"):
        for rt in (r, r * 0.7, r * 0.5):
            try: b_ = b_.faces(sel).edges().fillet(rt); break
            except Exception: continue
        else: print("fillet skipped", sel, i)
    return b_

DZ = Z_AX + math.sqrt((R_B + D0 / 2) ** 2 - XE ** 2)

