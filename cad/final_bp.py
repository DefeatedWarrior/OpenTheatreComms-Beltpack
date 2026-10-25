"""OpenTheatreComms beltpack - final reference model with real component envelopes.

Frame: x across the pack (ends at +-52.5), y up (top face at +38.5), z out from the hip (front face at z=0, back ~-30).
Everything else (shell shape, dial geometry, front recess) is the approved concept v16.
"""
import sys, os, math, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import *

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
t0 = time.time()
def log(*a): print(f"[{time.time() - t0:6.1f}s]", *a, flush=True)

def fz(x, off=0.0): return front_z(abs(x), off)
def bz(x, off=0.0): return back_z(abs(x), off)
def N(y): return y - H / 2                      # flat-top frame n from y
def clip(s): return W_(s).intersect(B0)

# ---------------------------------------------------------------- stack-up
Y_TOP = H / 2 - T            # 36.3  top plate underside / shell split
Y_CAP = H / 2 - CAP_H        # 31.5  TPU cap edge = knob pocket ceiling
R_SPLIT = R_B + T            # 402.2 back shell inner radius
TP0, TP1 = 31.6, 33.2        # top PCB (1.6)
SW_H = 2.5                   # C&K PTS815 height
GL_Y0 = TP1 + 1.5            # OLED glass on 1.5 mm foam spacer -> 34.7..36.1
GL_T = 1.4
AA_V = 13.65                 # OLED active-area centre, mm back from the front
GL_V0, GL_V1 = 4.0, 27.0     # glass 23.0 deep: 2.3 border at the front, 6.0 FPC border at the back (verify)
OLED_ACT = (0.0, AA_V, 29.42, 14.7)
ENC_W, ENC_D, ENC_H, ENC_L = 12.5, 13.4, 6.5, 15.0   # PEC12R body (height assumed) and shaft length from seating plane
ENC_Y0 = TP0 - ENC_H         # 25.1 body bottom
SHAFT_Y0 = TP0 - ENC_L       # 16.6 shaft tip
MZ1, MZ0 = -8.2, -9.8        # main PCB front / back faces
REC_DEPTH, REC_COVE = 2.0, 1.8
REC_TOP, REC_W = DY1 - DH / 2, 54.0; REC_BOT = REC_TOP - 15.0
FB_Y = REC_TOP - 7.5
FBTN = [("Back", -18.0, "round"), ("Function", 0.0, "pill"), ("Menu", 18.0, "round")]
XLR_X = -24.0; XLR_Z = (fz(24.0) + bz(24.0)) / 2
XLR_FW, XLR_FD, XLR_FT = 31.0, 26.0, 2.0          # D-size flange (x by z), thickness
XLR_HOLES = [(XLR_X - 12.0, XLR_Z + 9.5), (XLR_X + 12.0, XLR_Z - 9.5)]   # diagonal M3 pair, 24 x 19 pitch
USB_X, USB_Z = 9.0, MZ1 + 3.16 / 2
TRRS_X, TRRS_Z = 22.0, MZ1 + 2.5
PWR_X, PWR_Z = -3.0, MZ1 + 1.75
LAMP_X, LAMP_Z = 32.0, MZ1 + 2.0
PACK = (-13.5, 39.5, -31.0, 15.0, -13.5)          # x0, x1, y0, y1, front face z
PK_CLR = 0.3
END_SCREWS = [(sx * (DX + 13.6 * math.cos(math.radians(50))), DZ + sz * 13.6 * math.sin(math.radians(50))) for sx in (-1, 1) for sz in (1, -1)]
TOP_PCB_HOLES = [(sx * 20.0, z) for sx in (-1, 1) for z in (-6.0, -25.5)]
MAIN_HOLES = {"H1": (-30.0, -9.0), "H2": (38.0, 12.0), "H3": (-6.0, 25.5), "H4": (38.0, -32.5), "H5": (-10.0, -32.5)}
BACK_SCREWS = {"S1": (-22.0, 25.0), "S2": (22.0, 25.0), "S3": (-30.0, -9.0), "S4": (-41.0, -33.0)}
STATUS = [(sx * 46.5, DZ) for sx in (-1, 1)]
RAIL_X = 10.0
MAIN_PTS = [(-13.0, -36.0), (41.0, -36.0), (41.0, 16.0), (21.0, 16.0), (21.0, 28.5), (-21.0, 28.5),
            (-21.0, 16.0), (-46.5, 16.0), (-46.5, -14.3), (-13.0, -14.3)]

PARTS = []
def add(name, shape, rgb, group, label, desc="", printed=False, explode=(0, 0, 0), price=None, src=None):
    PARTS.append(dict(name=name, shape=solid(shape), rgb=rgb, group=group, label=label, desc=desc,
                      printed=printed, explode=list(explode), price=price, src=src))

CASE = (0.19, 0.21, 0.24); TPU = (0.93, 0.68, 0.10); CAP = (0.33, 0.36, 0.40); BLACK = (0.07, 0.07, 0.08)
GLASS = (0.04, 0.05, 0.07); PLATE = (0.13, 0.14, 0.16); SILVER = (0.78, 0.79, 0.81); PIPE = (0.85, 0.95, 0.88)
PCB = (0.05, 0.36, 0.20); GOLD = (0.85, 0.68, 0.25); WHITE = (0.92, 0.92, 0.90); DIAL = (0.12, 0.12, 0.13)
CELL = (0.16, 0.32, 0.62); FLEX = (0.80, 0.50, 0.15); NICKEL = (0.62, 0.63, 0.64); HUB = (0.42, 0.44, 0.47)

def ob_y(w, d, r, x, z, y0, y1):
    """Rounded rectangle w (x) by d (z), extruded along y."""
    return W_(rrect(w, d, min(y0, y1), max(y0, y1), r)).rotate((0, 0, 0), (1, 0, 0), -90).translate((x, 0, z))

# ================================================================= shell
log("shell")
B0 = body(0)
CAV = plan_solid(T).intersect(box(-W, W, -H / 2 + T, Y_TOP, -120, 20))
for rt in (1.3, 0.9, 0.5):
    try: CAV = CAV.faces("<Y").edges().fillet(rt); break
    except Exception: continue
keep = []
for sx in (-1, 1):
    cx = sx * DX
    keep.append(Solid.makeCone(DR_BOT + 2.2, DR_TOP + 2.2, DH + 1.2, V(cx, DY0 - 0.6, DZ), V(0, 1, 0)))   # knob well wall
    keep.append(cylY(cx, DZ, DR_BOT + 2.2, DY0 - 2.6, DY0 - 0.59))                                        # well floor 16.3..18.3
rec_back = W_(rrect(REC_W + 2 * T, REC_TOP - REC_BOT + 2 * T, -14, 5, 6.0 + T, 0, (REC_TOP + REC_BOT) / 2)) \
    .intersect(arc_shell(R_F - REC_DEPTH - T, R_F))
for k in keep: CAV = CAV.cut(k)
CAV = CAV.cut(rec_back)
shell = W_(B0).cut(CAV)

# --- top face (flat-top frame)
for u, kw, kd in KEYS:
    shell = shell.cut(to_slope(cylZ(u, key_v(u), kw / 2 + 0.3, -T - 1, 2)))
au, av, aw, ah = OLED_ACT
shell = shell.cut(to_slope(rrect(aw + 1.6, ah + 1.6, -T - 1, 2, 2.0, au, av))).cut(to_slope(rrect(aw + 3.4, ah + 3.4, -0.5, 2, 3.0, au, av)))
for u in (-29.9, -17.45, 17.45, 29.9):
    shell = shell.union(to_slope(rrect(1.2, 12.0, -0.2, 1.9, 0.6, u, key_v(u))))
for x, z in STATUS:
    shell = shell.cut(cylY(x, z, 1.3, Y_TOP - 1, H / 2 + 2))
# --- front: ribs, name band, recess, buttons
MARK, BAND_HW, BAND_Y0, BAND_Y1, MARGIN = "OpenTheatreComms", 34.0, -27.0, -19.0, 1.2
probe = cq.Workplane("XY").text(MARK, 10.0, 1.0, font="DejaVu Sans", kind="bold", halign="center", valign="center").val().BoundingBox()
MARK_SIZE = 10.0 * min((2 * BAND_HW - 2 * MARGIN - 1.0) / (probe.xmax - probe.xmin), (BAND_Y1 - BAND_Y0 - 2 * MARGIN) / (probe.ymax - probe.ymin))
mark = cq.Workplane("XY").text(MARK, MARK_SIZE, 10.0, font="DejaVu Sans", kind="bold", halign="center", valign="center")
mb = mark.val().BoundingBox(); dy = (BAND_Y0 + BAND_Y1) / 2 - (mb.ymin + mb.ymax) / 2
for k in range(-10, 11):
    x = k * 3.6; zc = fz(abs(x) + 0.7) - 0.7
    if abs(x) <= BAND_HW + 0.7:
        shell = shell.cut(box(x - 0.7, x + 0.7, -H / 2 + 7, BAND_Y0 - 1.0, zc, 2)).cut(box(x - 0.7, x + 0.7, BAND_Y1 + 1.0, H / 2 - 7, zc, 2))
    else:
        shell = shell.cut(box(x - 0.7, x + 0.7, -H / 2 + 7, H / 2 - 7, zc, 2))
shell = shell.cut(W_(mark.val().translate(V(0, dy, -5.0))).intersect(arc_shell(R_F - 0.6, R_F + 10)))
rec = W_(rrect(REC_W, REC_TOP - REC_BOT, -12, 5, 6.0, 0, (REC_TOP + REC_BOT) / 2)).intersect(arc_shell(R_F - REC_DEPTH, R_F + 10))
try: rec = rec.faces("<Z").edges().fillet(REC_COVE)
except Exception as e: print("cove skipped", e)
shell = shell.cut(rec)
for nm, x, kind in FBTN:
    zc = fz(x) - REC_DEPTH
    shell = shell.cut(rrect(20.6, 8.6, zc - 4, zc + 1, 4.3, x, FB_Y) if kind == "pill" else cylZ(x, FB_Y, 4.8, zc - 4, zc + 1))
# --- dial pockets, shoulder, hub bearing
for sx in (-1, 1):
    cx = sx * DX
    outer = box(cx, sx * (W / 2 + 5), DY0 - 0.6, DY1 + 0.6, -120, 20)
    shell = shell.cut(W_(cylY(cx, DZ, DR_TOP + 0.6, DY0 - 0.6, DY1 + 0.6)).intersect(outer))
    shell = shell.cut(Solid.makeCone(DR_BOT + 0.6, DR_TOP + 0.6, DH + 1.2, V(cx, DY0 - 0.6, DZ), V(0, 1, 0)))
    yb = DY0 - 0.6; r0 = DR_TOP - SHOULDER_R
    ring = W_(cylY(cx, DZ, DR_TOP + 0.5, yb - SHOULDER_R, yb + 0.01)).cut(cylY(cx, DZ, r0, yb - SHOULDER_R - 1, yb + 1))
    ring = ring.cut(Solid.makeTorus(r0, SHOULDER_R, V(cx, yb - SHOULDER_R, DZ), V(0, 1, 0)))
    shell = shell.cut(ring.intersect(box(cx, sx * (W / 2 + 5), yb - SHOULDER_R - 1, yb + 1, -120, 20)))
    shell = shell.cut(cylY(cx, DZ, 4.4, DY0 - 4.0, DY0))
# --- bottom face
shell = shell.cut(box(XLR_X - XLR_FW / 2 - 0.2, XLR_X + XLR_FW / 2 + 0.2, -H / 2 - 1, -H / 2 + 1.0, XLR_Z - XLR_FD / 2 - 0.2, XLR_Z + XLR_FD / 2 + 0.2))
shell = shell.cut(cylY(XLR_X, XLR_Z, 12.0, -H / 2 - 1, -H / 2 + T + 1))
for x, z in XLR_HOLES: shell = shell.cut(cylY(x, z, 1.6, -H / 2 - 1, -H / 2 + T + 0.5))
shell = shell.cut(ob_y(13.0, 7.0, 3.0, USB_X, USB_Z, -H / 2 - 1, -H / 2 + T + 0.5))
shell = shell.cut(cylY(TRRS_X, TRRS_Z, 3.2, -H / 2 - 1, -H / 2 + T + 0.5))
shell = shell.cut(cylY(PWR_X, PWR_Z, 2.75, -H / 2 - 1, -H / 2 + T + 0.5)).cut(cylY(PWR_X, PWR_Z, 4.0, -37.0, -H / 2 + T + 0.3))   # counterbore for the plunger flange
shell = shell.cut(cylY(LAMP_X, LAMP_Z, 1.65, -H / 2 - 1, -H / 2 + T + 0.5))
# --- battery opening (pack is the back face there)
px0, px1, py0, py1, pz = PACK
pack_clear = box(px0 - PK_CLR, px1 + PK_CLR, py0 - PK_CLR, py1 + PK_CLR, pz + PK_CLR, -60)
shell = shell.cut(pack_clear)
log("shell done")

# ================================================================= split
top_plate = shell.intersect(box(-W, W, Y_TOP, H, -120, 20))
rest = shell.intersect(box(-W, W, -H, Y_TOP, -120, 20))
back_shell = rest.intersect(axis_cyl(R_SPLIT))
front_shell = rest.cut(axis_cyl(R_SPLIT))
log("split done")

# --- top plate: tongue, PCB bosses, end-screw countersinks
tongue = W_(plan_solid(T + 0.15)).intersect(box(-W, W, Y_TOP - 1.8, Y_TOP + 0.01, -120, 20)).cut(plan_solid(T + 1.15))
for x, z in END_SCREWS: tongue = tongue.cut(cylY(x, z, 2.6, Y_TOP - 3, Y_TOP + 1))
tongue = tongue.cut(box(-GW / 2 - 1.0, GW / 2 + 1.0, Y_TOP - 3, Y_TOP + 1, -40, -20))      # clear the OLED glass and FPC at the back
top_plate = top_plate.union(tongue)
for x, z in TOP_PCB_HOLES:
    top_plate = top_plate.union(cylY(x, z, 2.2, TP1, Y_TOP + 0.3)).cut(cylY(x, z, 0.8, TP1 - 1, Y_TOP + 1.2))
for x, z in END_SCREWS:
    top_plate = top_plate.cut(cylY(x, z, 1.15, Y_TOP - 1, H / 2 + 2)).cut(Solid.makeCone(1.15, 2.0, 0.85, V(x, 36.95, z), V(0, 1, 0)))
    top_plate = top_plate.cut(cylY(x, z, 2.0, 37.79, H / 2 + 3))
# --- front shell: end-screw bosses, PCB standoffs, back-shell bosses, XLR bosses
def fs_add(s):
    global front_shell
    front_shell = front_shell.union(W_(s).intersect(B0).cut(axis_cyl(R_SPLIT)).cut(pack_clear))
for x, z in END_SCREWS:
    fs_add(cylY(x, z, 2.2, Y_CAP, Y_TOP))
    front_shell = front_shell.cut(cylY(x, z, 0.8, Y_CAP + 0.8, Y_TOP + 1))
for nm, (x, y) in MAIN_HOLES.items():
    z_in = fz(x, -REC_DEPTH - T) if (abs(x) < REC_W / 2 + T and REC_BOT - T < y < REC_TOP + T) else fz(x) - T
    fs_add(cylZ(x, y, 2.5, MZ1, z_in + 0.8))
    front_shell = front_shell.cut(cylZ(x, y, 1.6, MZ1 - 0.1, MZ1 + 4.0))
for nm in ("S1", "S2"):
    x, y = BACK_SCREWS[nm]
    fs_add(cylZ(x, y, 2.6, bz(x, T + 0.01), -20.5))
    front_shell = front_shell.cut(cylZ(x, y, 1.6, bz(x, T) - 0.1, bz(x, T) + 4.0))
x, y = BACK_SCREWS["S4"]
fs_add(box(x - 2.6, x + 2.6, -H / 2 + T - 0.5, y + 2.6, -30, -20.5))
front_shell = front_shell.cut(cylZ(x, y, 1.6, -31, -26.0))
for x, z in XLR_HOLES:
    fs_add(cylY(x, z, 3.0, -H / 2 + T - 0.3, -H / 2 + T + 5.0))
    front_shell = front_shell.cut(cylY(x, z, 2.0, -H / 2 + T - 1, -H / 2 + T + 5.5))
log("front shell done")

# --- back shell: screw holes, belt rails, latch dimple
for nm, (x, y) in BACK_SCREWS.items():
    back_shell = back_shell.cut(cylZ(x, y, 1.15, -50, 0)).cut(cylZ(x, y, 2.1, -50, bz(x) + 1.3) if nm != "S4" else cylZ(x, y, 2.1, -50, -31.29 + 0.9))
for sx in (-1, 1):
    x = sx * RAIL_X; zb = bz(x)
    rail = W_(box(x - 1.5, x + 1.5, 16.0, 31.0, zb - 1.0, zb + 0.4)).union(box(x - 2.5, x + 2.5, 16.0, 31.0, zb - 2.0, zb - 1.0))
    back_shell = back_shell.union(rail)
back_shell = back_shell.cut(Solid.makeSphere(0.9, V(0, 29.0, bz(0)), angleDegrees1=-90, angleDegrees2=90))
log("back shell done")

add("front_shell", front_shell, CASE, "Enclosure", "Front shell", "PETG/ASA. Curved ribbed front, both round ends, bottom face. Holds the main PCB on 5 heat-set M2 inserts, the knob wells and the XLR.", True, (0, 0, 34))
add("back_shell", back_shell, CASE, "Enclosure", "Back shell", "Hip-side skin with the battery opening and two dovetail rails for the belt plate. 4 x M2 screws.", True, (0, 0, -30))
add("top_plate", top_plate, CASE, "Enclosure", "Top plate", "Carries the keycaps, OLED and top PCB as one module; 4 x M2 countersunk screws at the ends, hidden under the TPU cap.", True, (0, 52, 0))

# ================================================================= TPU caps
log("tpu")
G = body(-BAND); ring = W_(G).cut(B0)
for name, sgn in (("tpu_top", 1), ("tpu_bottom", -1)):
    zone = box(-W, W, sgn * (H / 2 - CAP_H), sgn * (H / 2 + BAND + 0.01), -120, 20)
    cap = ring.intersect(zone).cut(W_(plan_solid(3.5)).intersect(box(-W, W, sgn * (H / 2 - 0.5), sgn * (H / 2 + 6), -120, 20)))
    if sgn < 0:
        cap = cap.cut(box(XLR_X - XLR_FW / 2 - 0.6, XLR_X + XLR_FW / 2 + 0.6, -H, -H / 2 + 1, XLR_Z - XLR_FD / 2 - 0.6, XLR_Z + XLR_FD / 2 + 0.6))
        cap = cap.cut(ob_y(13.6, 7.6, 3.3, USB_X, USB_Z, -H, -H / 2 + 1)).cut(cylY(TRRS_X, TRRS_Z, 3.6, -H, -H / 2 + 1))
        cap = cap.cut(cylY(PWR_X, PWR_Z, 3.2, -H, -H / 2 + 1)).cut(cylY(LAMP_X, LAMP_Z, 2.0, -H, -H / 2 + 1))
    add(name, cap, TPU, "Enclosure", "TPU top cap" if sgn > 0 else "TPU bottom cap",
        "TPU 95A in the department colour; stretches over the top/bottom 7 mm and hides the end screws." if sgn > 0 else
        "TPU 95A bumper; cut round the XLR flange and every bottom opening.", True, (0, 72 if sgn > 0 else -50, 0))

# ================================================================= knobs (TPU tyre on a PETG hub)
for sx, side in ((-1, "left"), (1, "right")):
    cx = sx * DX
    tyre = W_(Solid.makeCone(DR_BOT, DR_TOP, DH, V(cx, DY0, DZ), V(0, 1, 0)))
    for k in range(36):
        a = 2 * math.pi * k / 36; ca, sa = math.cos(a), math.sin(a)
        p0 = V(cx + DR_BOT * ca, DY0, DZ + DR_BOT * sa); p1 = V(cx + DR_TOP * ca, DY1, DZ + DR_TOP * sa)
        d_ = p1 - p0; tyre = tyre.cut(Solid.makeCylinder(0.75, d_.Length + 2, p0 - d_.normalized() * 1.0, d_.normalized()))
    tyre = tyre.cut(cylY(cx, DZ, 9.8, DY0 + 1.0, DY1 + 1)).cut(cylY(cx, DZ, 4.2, DY0 - 1, DY0 + 1.1))
    add(f"knob_{side}", tyre, DIAL, "Controls", f"{side.capitalize()} dial tyre",
        "TPU 95A truncated cone, 12 mm tall, 36 grip flutes. Hollow: the encoder body sits inside it.", True, (sx * 34, 0, 0))
    hub = W_(cylY(cx, DZ, 9.8, DY0 + 1.0, ENC_Y0 - 0.5)).union(cylY(cx, DZ, 4.0, DY0 - 3.0, DY0 + 1.05))
    bore = W_(cylY(cx, DZ, 3.05, SHAFT_Y0 - 0.0, ENC_Y0)).cut(box(cx + 1.55, cx + 4, SHAFT_Y0 - 1, ENC_Y0 + 1, DZ - 4, DZ + 4))
    hub = hub.cut(bore)
    add(f"hub_{side}", hub, HUB, "Controls", f"{side.capitalize()} dial hub",
        "PETG insert bonded into the tyre. D-bore on the 6 mm flatted shaft; its stem runs in a bearing hole in the well floor.", True, (sx * 34, -14, 0))

# ================================================================= keys, buttons, light pipes
for i, (u, kw, kd) in enumerate(KEYS):
    v = key_v(u)
    cap = W_(cylZ(u, v, kw / 2, -T, 1.6)).faces(">Z").edges().fillet(1.5)
    cap = cap.union(cylZ(u, v, kw / 2 + 0.8, N(TP1 + SW_H), -T))
    cap = cap.cut(text_solid(str(i + 1), 6.5 if kw > 12 else 5.0, 1.0).rotate((0, 0, 0), (0, 0, 1), 180).translate((u, v, 1.1)))
    add(f"keycap_{i+1}", to_slope(cap), CAP, "Controls", f"Talk key {i+1}",
        "Translucent PETG cap, flange retained under the top plate, sits straight on a PTS815; key LED lights it from below.", True, (0, 64, 0))
for nm, x, kind in FBTN:
    zf = fz(x) - REC_DEPTH; z1 = zf + 0.9; zi = fz(x, -REC_DEPTH - T)
    b_ = (rrect(20.0, 8.0, zi, z1, 4.0, x, FB_Y) if kind == "pill" else W_(cylZ(x, FB_Y, 4.5, zi, z1)))
    b_ = b_.faces(">Z").edges().fillet(0.6)
    if kind == "pill": b_ = b_.union(rrect(8.0, 1.4, z1 - 0.1, z1 + 0.6, 0.6, x, FB_Y))
    if nm == "Menu": b_ = b_.union(cylZ(x, FB_Y, 1.2, z1 - 0.1, z1 + 0.6))
    fl = W_(rrect(21.6, 9.6, zi - 0.9, zi + 0.2, 4.8, x, FB_Y) if kind == "pill" else cylZ(x, FB_Y, 5.3, zi - 0.9, zi + 0.2))
    b_ = b_.union(fl.intersect(axis_cyl(R_F - REC_DEPTH - T - 0.05)))      # flange follows the curved wall
    b_ = b_.union(cylZ(x, FB_Y, 1.0, MZ1 + SW_H, zi - 0.85))
    add(f"front_{nm.lower()}", b_, CAP, "Controls", f"{nm} button", "PETG cap with a flange behind the recess wall; plunger onto a PTS815 on the main PCB.", True, (0, 0, 46))
pw = W_(cylY(PWR_X, PWR_Z, 2.5, -H / 2 + 0.2, -37.0)).union(cylY(PWR_X, PWR_Z, 3.5, -36.98, -36.45))
add("power_plunger", pw, CAP, "Controls", "Power button", "Recessed 0.2 mm below the bottom face so it is hard to knock; long-press to turn on/off.", True, (0, -42, 0))
for i, (x, z) in enumerate(STATUS):
    add(f"status_pipe_{'LR'[i]}", cylY(x, z, 1.2, TP1 + 0.6, H / 2), PIPE, "Display", "Status light pipe", "2.4 mm clear rod over an 0603 RGB/white LED on the top PCB.", False, (0, 60, 0))

# ================================================================= top PCB and its parts
log("top pcb")
tpcb = W_(plan_solid(2.6)).intersect(box(-W, W, TP0, TP1, -120, 20))
for x, z in END_SCREWS: tpcb = tpcb.cut(cylY(x, z, 2.9, TP0 - 1, TP1 + 1))
tpcb = tpcb.cut(W_(axis_cyl(R_B + 4.0)).intersect(box(-16, 16, TP0 - 1, TP1 + 1, -120, 20)))
for x, z in TOP_PCB_HOLES: tpcb = tpcb.cut(cylY(x, z, 1.1, TP0 - 1, TP1 + 1))
add("top_pcb", tpcb, PCB, "Electronics", "Top PCB", "1.6 mm FR4, 2 layers. Keys, OLED, status LEDs on top; both encoders, OLED connector, IO expander and the JST SH link underneath.", False, (0, 26, 0))
TOPP = []   # (name, label, x, z, w, d, h, side) for drawings
def top_part(name, label, x, z, w, d, h, side, rgb=BLACK, desc="", src=None):
    y0, y1 = (TP1, TP1 + h) if side == "top" else (TP0 - h, TP0)
    s = box(x - w / 2, x + w / 2, y0, y1, z - d / 2, z + d / 2)
    add(name, s, rgb, "Electronics", label, desc, False, (0, 26, 0), src=src)
    TOPP.append(dict(name=name, label=label, x=x, z=z, w=w, d=d, h=h, side=side))
for i, (u, kw, kd) in enumerate(KEYS):
    v = key_v(u)
    top_part(f"sw_key{i+1}", f"PTS815 (key {i+1})", u, -v, 4.2, 3.2, SW_H, "top", (0.25, 0.25, 0.27), "C&K PTS815 SJM 250 SMTR LFS, 4.2 x 3.2 x 2.5 mm SMD tact.", "PTS815")
    top_part(f"led_key{i+1}", "0603 key LED", u, -v + (4.0 if kw > 12 else 3.4), 1.6, 0.8, 0.55, "top", WHITE, "0603 LED under the translucent keycap (alert flash).", "0603")
for i, (x, z) in enumerate(STATUS):
    top_part(f"led_status_{'LR'[i]}", "0603 status LED", x, z, 1.6, 0.8, 0.55, "top", WHITE, "Status LED under the light pipe.", "0603")
top_part("oled_zif", "OLED FPC connector", 0.0, -23.0, 18.0, 4.0, 1.2, "bottom", (0.85, 0.85, 0.80), "Placeholder: 0.5 mm ZIF or solder pads for the panel's FPC (pin count depends on the panel).", None)
top_part("jst_top", "JST BM10B-SRSS-TB", -10.0, -13.65, 13.0, 4.3, 4.4, "bottom", WHITE, "JST SH 10-pin top-entry, cable to the main PCB.", "JST SH")
top_part("io_exp", "TCA9535PWR", 8.0, -16.0, 7.8, 6.4, 1.2, "bottom", BLACK, "16-bit I2C IO expander, TSSOP-24: keys and LEDs.", "TCA9535")
for sx, side in ((-1, "left"), (1, "right")):
    cx = sx * DX
    enc = W_(box(cx - ENC_W / 2, cx + ENC_W / 2, ENC_Y0, TP0, DZ - ENC_D / 2, DZ + ENC_D / 2))
    shaft = W_(cylY(cx, DZ, 3.0, SHAFT_Y0, ENC_Y0 + 0.01)).cut(box(cx + 1.5, cx + 4, SHAFT_Y0 - 1, ENC_Y0 - 0.3, DZ - 4, DZ + 4))
    add(f"enc_{side}", enc.union(shaft), SILVER, "Electronics", "PEC12R encoder",
        "Bourns PEC12R-4215F-N0024: 12 mm, no bushing, 15 mm insulated flatted shaft, 24 detents / 24 pulses, no switch. Mounted upside-down on the top PCB.", False, (0, 26, 0), src="PEC12R")
    TOPP.append(dict(name=f"enc_{side}", label="PEC12R encoder", x=cx, z=DZ, w=ENC_W, d=ENC_D, h=ENC_H, side="bottom"))
# OLED
glass = to_slope(box(-GW / 2, GW / 2, GL_V0, GL_V1, N(GL_Y0), N(GL_Y0 + GL_T)))
add("oled_glass", glass, GLASS, "Display", "1.3 in OLED", "Bare 1.3 in 128 x 64 SH1106 panel, 34.5 x 23.0 x 1.4, AA 29.42 x 14.7, on 1.5 mm foam tape.", False, (0, 40, 0), src="OLED")
add("oled_spacer", to_slope(box(-15, 15, 6.5, 21.0, N(TP1), N(GL_Y0))), (0.25, 0.25, 0.25), "Display", "Foam spacer", "1.5 mm double-sided foam tape.", False, (0, 33, 0))
fpc = to_slope(box(-6, 6, GL_V1 - 0.6, GL_V1 - 0.5, N(TP0 - 0.3), N(GL_Y0 + 0.1))).union(to_slope(box(-6, 6, 25.0, GL_V1 - 0.5, N(TP0 - 0.4), N(TP0 - 0.3))))
add("oled_fpc", fpc, FLEX, "Display", "OLED FPC", "Panel tail wraps round the notch in the PCB back edge to the connector underneath.", False, (0, 26, 0))

# ================================================================= main PCB and its parts
log("main pcb")
mpcb = fillet_poly("XY", MAIN_PTS, [1.0] * len(MAIN_PTS)).extrude(MZ1 - MZ0).translate((0, 0, MZ0))
for nm, (x, y) in MAIN_HOLES.items(): mpcb = mpcb.cut(cylZ(x, y, 1.1, MZ0 - 1, MZ1 + 1))
add("main_pcb", mpcb, PCB, "Electronics", "Main PCB", "1.6 mm FR4, 4 layers suggested. Vertical behind the front: MCU, radio, codec, power, the three front buttons and every bottom connector.", False, (0, 0, 0))
MAINP = []
def main_part(name, label, x, y, w, h, t, face, rgb=BLACK, desc="", src=None, solid_=None):
    z0, z1 = (MZ1, MZ1 + t) if face == "front" else (MZ0 - t, MZ0)
    s = solid_ if solid_ is not None else box(x - w / 2, x + w / 2, y - h / 2, y + h / 2, z0, z1)
    add(name, s, rgb, "Electronics", label, desc, False, (0, 0, 0), src=src)
    MAINP.append(dict(name=name, label=label, x=x, y=y, w=w, h=h, t=t, face=face))
for nm, x, kind in FBTN:
    main_part(f"sw_{nm.lower()}", f"PTS815 ({nm})", x, FB_Y, 4.2, 3.2, SW_H, "front", (0.25, 0.25, 0.27), "C&K PTS815, front button switch.", "PTS815")
# USB-C (GCT USB4105-GF-A): mouth 0.8 past the board edge
uy0 = MAIN_PTS[0][1] - 0.8
usb = W_(box(USB_X - 4.47, USB_X + 4.47, uy0, uy0 + 7.35, MZ1, MZ1 + 3.16)).edges("|Y").fillet(1.2)
usb = usb.cut(ob_y(8.34, 2.56, 1.2, USB_X, USB_Z, uy0 - 1, uy0 + 6.0)).union(box(USB_X - 3.3, USB_X + 3.3, uy0 + 0.6, uy0 + 6.1, USB_Z - 0.35, USB_Z + 0.35))
main_part("usb_c", "USB4105-GF-A", USB_X, uy0 + 7.35 / 2, 8.94, 7.35, 3.16, "front", SILVER, "GCT USB4105-GF-A USB 2.0 Type-C receptacle, 16-pin top-mount (dims to verify).", "USB4105", usb)
# 3.5 mm TRRS (PJ-320D)
ty0 = MAIN_PTS[0][1]
trrs = W_(box(TRRS_X - 3.0, TRRS_X + 3.0, ty0, ty0 + 12.0, MZ1, MZ1 + 5.0)).union(cylY(TRRS_X, TRRS_Z, 2.5, ty0 - 2.1, ty0 + 0.01)).cut(cylY(TRRS_X, TRRS_Z, 1.8, ty0 - 3, ty0 + 9))
main_part("trrs", "PJ-320D", TRRS_X, ty0 + 6.0, 6.0, 12.0, 5.0, "front", BLACK, "PJ-320D 3.5 mm 4-pole SMD jack, 14.1 x 6.0 x 5.0 incl. nose.", "PJ-320D", trrs)
# power switch (side-actuated tact)
pws = W_(box(PWR_X - 3.1, PWR_X + 3.1, -35.6, -32.0, MZ1, MZ1 + 3.5)).union(cylY(PWR_X, PWR_Z, 0.8, -36.4, -35.59))
main_part("sw_power", "Side tact (TL1014)", PWR_X, -33.8, 6.2, 3.6, 3.5, "front", (0.25, 0.25, 0.27), "Side-actuated SMD tact switch, e.g. E-Switch TL1014 (dims assumed 6.2 x 3.6 x 3.5).", "TL1014", pws)
# lamp LED (3 mm THT, bent 90 deg)
lamp = W_(cylY(LAMP_X, LAMP_Z, 1.5, -H / 2 + 0.7 + 1.5, -32.6)).union(Solid.makeSphere(1.5, V(LAMP_X, -H / 2 + 0.7 + 1.5, LAMP_Z))).union(cylY(LAMP_X, LAMP_Z, 1.9, -33.6, -32.6))
main_part("lamp_led", "3 mm white LED", LAMP_X, -34.5, 3.8, 5.3, 3.8, "front", WHITE, "3 mm THT white LED, legs bent 90 deg, through a 3.3 mm hole: the flashlight.", "LED3", lamp)
mot = cylZ(32.0, -20.0, 4.0, MZ1, MZ1 + 2.7)
main_part("vib_motor", "Coin vibration motor", 32.0, -20.0, 8.0, 8.0, 2.7, "front", NICKEL, "8 x 2.7 mm coin motor, stuck to the board and driven by a SOT-23 MOSFET.", "motor", mot)
# back face
main_part("esp32s3", "ESP32-S3-WROOM-1", -33.25, 5.0, 25.5, 18.0, 3.1, "back", SILVER, "Espressif ESP32-S3-WROOM-1-N8R8, 25.5 x 18 x 3.1, PCB antenna at the left end (keep copper clear under it).", "ESP32S3")
main_part("lr2021", "LR2021 module", 33.0, 3.0, 10.0, 10.0, 2.5, "back", (0.15, 0.15, 0.17), "Elecrow LR2021 module, 10 x 10 x 2.5, 20 castellated pads at 1.27 mm.", "LR2021")
main_part("ufl", "U.FL (A)", 31.0, 10.5, 3.0, 3.0, 1.25, "back", GOLD, "Hirose U.FL-R-SMT-1 for antenna A (right end).", "UFL")
main_part("ufl_b", "U.FL (B)", 24.5, 10.5, 3.0, 3.0, 1.25, "back", GOLD, "Hirose U.FL-R-SMT-1 for antenna B (left end).", "UFL")
main_part("rf_switch", "PE4259 RF switch", 25.8, 4.0, 2.0, 2.1, 1.0, "back", BLACK, "pSemi PE4259 SPDT, SC-70-6, 10 MHz-3 GHz, single-pin control from an ESP32 GPIO: switched antenna diversity.", "PE4259")
main_part("rf_match", "RF match + DC block", 26.0, 7.2, 3.0, 1.6, 0.6, "back", (0.55, 0.45, 0.30), "Unpopulated pi network between the module and the switch, plus 100 pF DC-block footprints on the switch ports.", None)
main_part("codec", "NAU88C22YG", -6.0, -25.0, 5.0, 5.0, 0.9, "back", BLACK, "Nuvoton NAU88C22 codec, QFN-32 5 x 5 (needs hot air / hot plate).", "NAU88C22")
main_part("charger", "Li-ion charger", -2.0, -31.5, 4.9, 3.9, 1.6, "back", BLACK, "1 A Li-ion charger, ESOP-8 (TP4056 class).", None)
main_part("ldo", "3.3 V LDO", 20.0, -31.0, 3.0, 3.0, 1.2, "back", BLACK, "1 A LDO, SOT-23-5 (e.g. TLV75733).", None)
main_part("jst_main", "JST SM10B-SRSS-TB", 8.0, 28.5 - 4.25 / 2, 13.0, 4.25, 2.9, "back", WHITE, "JST SH 10-pin side-entry at the top of the tab, cable from the top PCB.", "JST SH")
for i, x in enumerate((6.0, 12.0, 18.0)):
    pg = W_(cylZ(x, -15.0, 0.9, MZ0 - 2.7, MZ0)).union(cylZ(x, -15.0, 0.5, PACK[4], MZ0 - 2.6))
    main_part(f"pogo_{i+1}", "Mill-Max 0906 pogo", x, -15.0, 1.8, 1.8, 3.7, "back", GOLD, "Mill-Max 0906-1-15-20-72-14-11-0 spring pin (4.5 mm tall, 1.4 mm stroke), compressed 0.8 onto the pack pads.", "0906", pg)
stand = cq.Workplane("XY").polygon(6, 3.5 / math.cos(math.pi / 6)).extrude(MZ0 - bz(-30.0, T) - 0.15).translate((-30.0, -9.0, bz(-30.0, T) + 0.15))
add("standoff_H1", stand.cut(cylZ(-30.0, -9.0, 1.0, -40, 0)), NICKEL, "Hardware", "M2 standoff 18 mm", "M2 male-female hex standoff: holds the main PCB and takes back-shell screw S3.", False, (0, 0, -12))

# ================================================================= XLR-4 (generic D-type, Neutrik D-size envelope)
log("xlr")
fy1 = -H / 2 + 1.0; fy0 = fy1 - XLR_FT
xl = W_(box(XLR_X - XLR_FW / 2, XLR_X + XLR_FW / 2, fy0, fy1, XLR_Z - XLR_FD / 2, XLR_Z + XLR_FD / 2)).edges("|Y").fillet(2.0)
for x, z in XLR_HOLES: xl = xl.cut(cylY(x, z, 1.6, fy0 - 1, fy1 + 1))
xl = xl.cut(cylY(XLR_X, XLR_Z, 9.6, fy0 - 1, fy1 + 1))
body_x = W_(cylY(XLR_X, XLR_Z, 9.75, fy1, fy1 + 18.0)).cut(cylY(XLR_X, XLR_Z, 9.0, fy0 - 1, fy1 + 6.0))
xl = xl.union(body_x).union(cylY(XLR_X, XLR_Z, 8.0, fy1 + 17.99, fy1 + 21.0))
xl = xl.union(cylY(XLR_X, XLR_Z, 9.0, fy1 + 5.99, fy1 + 7.0))
for k in range(4):
    a = math.radians(45 + 90 * k)
    xl = xl.union(cylY(XLR_X + 4.0 * math.cos(a), XLR_Z + 4.0 * math.sin(a), 0.8, fy1 + 1.5, fy1 + 6.5))
add("xlr4", xl, SILVER, "Connectors", "XLR-4 male (D-type)", "Generic D-size panel XLR-4M, front mount: 24 mm cutout, 2 x M3 on 24 x 19, flange 31 x 26 (Neutrik NC4MD-L-1 envelope: verify your part).", False, (0, -30, 0), src="XLR")

# ================================================================= battery pack
log("pack")
px0, px1, py0, py1, pz = PACK
pk = W_(B0).intersect(box(px0, px1, py0, py1, pz, -60))
pk = pk.cut(box(-12.2, 38.2, -29.2, 11.2, -14.6, -25.0)).cut(box(0.0 - 0.2, 24.0 + 0.2, -19.2, -10.8, pz - 0.85, pz + 1))
for x in (2.0, 15.0):                       # top hooks under the back shell edge
    pk = pk.union(box(x - 3, x + 3, py1 - 1.0, py1 + 2.2, bz(x, T) + 0.4, bz(x, T) + 1.4))
pk = pk.union(box(10.0, 16.0, py0 - 2.2, py0 + 1.0, bz(13.0, T) + 0.4, bz(13.0, T) + 1.4))   # bottom snap tooth
add("battery_pack", pk, (0.24, 0.26, 0.29), "Power", "Battery pack", "Printed tray: its back is the case back. Hooks at the top, snap at the bottom; the belt plate locks it in.", True, (0, 0, -50))
add("cell", W_(box(-12.0, 38.0, -29.0, 11.0, -24.8, -14.8)).edges().fillet(0.8), CELL, "Power", "104050 Li-ion cell", "1S 3.7 V 2500 mAh 104050 (10 x 40 x 50) with protection board.", False, (0, 0, -64), src="cell")
lid = W_(box(0.0, 24.0, -19.0, -11.0, pz - 0.8, pz))
for x in (6.0, 12.0, 18.0): lid = lid.cut(cylZ(x, -15.0, 1.5, pz - 0.05, pz + 1))
add("pack_lid_pcb", lid, PCB, "Power", "Pack pad board", "0.8 mm FR4, 3 ENIG pads (BAT+, NTC, BAT-) for the beltpack pogo pins and the charger.", False, (0, 0, -50))
pads = None
for x in (6.0, 12.0, 18.0):
    p = cylZ(x, -15.0, 1.5, pz - 0.05, pz); pads = p if pads is None else W_(pads).union(p)
add("pack_pads", pads, GOLD, "Power", "Pack pads", "Gold pads.", False, (0, 0, -50))

# ================================================================= antennas (switched diversity) + coax
ang = 10.0 / 12.65
def flex_antenna(sx, y0, y1):
    cx = sx * DX
    wedge = cq.Workplane("XZ").polyline([(cx, DZ), (cx + sx * 30 * math.cos(ang / 2), DZ + 30 * math.sin(ang / 2)),
                                         (cx + sx * 30 * math.cos(ang / 2), DZ - 30 * math.sin(ang / 2))]).close().extrude(-60).translate((0, -30, 0))
    return W_(cylY(cx, DZ, 12.75, y0, y1)).cut(cylY(cx, DZ, 12.65, y0 - 1, y1 + 1)).intersect(wedge)
def coax_run(pts):
    c = None
    for a, b in zip(pts[:-1], pts[1:]):
        d = b - a; seg = Solid.makeCylinder(0.55, d.Length, a, d.normalized())
        c = seg if c is None else W_(c).union(seg)
    for p in pts[1:-1]: c = W_(c).union(Solid.makeSphere(0.55, p))
    return c
add("antenna", flex_antenna(1, -30.0, 8.0), FLEX, "Radio", "915 MHz flex antenna A",
    "Molex 211140-0100, 38 x 10 x 0.1 mm, stuck inside the right end. Diversity antenna A.", False, (24, 0, 0), src="antenna")
add("antenna_b", flex_antenna(-1, -24.0, 14.0), FLEX, "Radio", "915 MHz flex antenna B",
    "Molex 211140-0100, stuck inside the left end, below the dial well and clear of the XLR. Diversity antenna B; it sits a few mm from the ESP32's Wi-Fi antenna.", False, (-24, 0, 0), src="antenna")
add("coax", coax_run([V(49.4, 7.0, DZ), V(47.0, 14.5, -12.5), V(31.0, 14.5, -11.5), V(31.0, 11.2, -11.1)]), (0.1, 0.1, 0.1), "Radio", "1.13 mm coax A",
    "Antenna A pigtail, about 100 mm, routed above the pack.", False, (14, 0, 0))
add("coax_b", coax_run([V(-49.4, 12.0, DZ), V(-46.5, 15.0, -13.0), V(-24.0, 15.0, -11.5), V(24.5, 15.0, -11.5), V(24.5, 11.2, -11.1)]), (0.1, 0.1, 0.1),
    "Radio", "1.13 mm coax B", "Antenna B pigtail, about 150 mm, runs across above the pack and the ESP32.", False, (-14, 0, 0))

# ================================================================= belt plate
pl = W_(arc_shell(R_B - 6.6, R_B - 0.6)).intersect(box(-25, 25, -29, 31, -80, 0)).edges("|Z").fillet(4.0)
for sx in (-1, 1): pl = pl.cut(box(sx * 15.5, sx * 20.5, -26, 13, -80, 0))
pl = pl.cut(W_(arc_shell(R_B - 4.1, R_B)).intersect(box(-15.5, 15.5, -26, 13, -80, 0)))
for sx in (-1, 1):
    x = sx * RAIL_X; zb = bz(x)
    pl = pl.cut(box(x - 1.7, x + 1.7, 15.8, 32, zb - 1.0, zb + 2)).cut(box(x - 2.7, x + 2.7, 15.8, 32, zb - 2.2, zb - 0.9))
pl = pl.cut(box(-5.5, -4.0, 22.0, 32, -80, 0)).cut(box(4.0, 5.5, 22.0, 32, -80, 0))
pl = pl.union(Solid.makeSphere(0.8, V(0, 29.0, bz(0) - 0.6)))
add("belt_plate", pl, PLATE, "Enclosure", "Belt plate", "PETG. Slides up onto the rails until the tongue clicks; doubles as the battery door. Belt slots take up to 38 mm.", True, (0, 0, -76))

# ================================================================= export
log("export", len(PARTS), "parts")
assy = cq.Assembly(name="beltpack_final")
for p in PARTS: assy.add(p["shape"], name=p["name"], color=Color(*p["rgb"], 1.0))
assy.export(os.path.join(OUT, "beltpack_final.step"))
assy.export(os.path.join(OUT, "beltpack_final.glb"), tolerance=0.04, angularTolerance=0.15)
import zipfile
with zipfile.ZipFile(os.path.join(OUT, "beltpack_final_stl.zip"), "w", zipfile.ZIP_DEFLATED) as zf:
    for p in PARTS:
        if p["printed"]:
            fn = os.path.join(OUT, p["name"] + ".stl"); cq.exporters.export(W_(p["shape"]), fn, tolerance=0.02, angularTolerance=0.1)
            zf.write(fn, p["name"] + ".stl"); os.remove(fn)
os.makedirs(os.path.join(OUT, "brep"), exist_ok=True)
for p in PARTS: p["shape"].exportBrep(os.path.join(OUT, "brep", p["name"] + ".brep"))
meta = []
for p in PARTS:
    bb = p["shape"].BoundingBox()
    meta.append(dict(name=p["name"], label=p["label"], group=p["group"], desc=p["desc"], explode=p["explode"], printed=p["printed"],
                     price=p["price"], bbox=[bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax], volume=round(p["shape"].Volume(), 1)))
env = cq.Compound.makeCompound([p["shape"] for p in PARTS if p["group"] == "Enclosure" or p["name"].startswith("knob")]).BoundingBox()
info = dict(envelope=[round(env.xmax - env.xmin, 2), round(env.ymax - env.ymin, 2), round(env.zmax - env.zmin, 2)],
            slope=dict(y0=SL_Y0, s=SL_S, c=SL_C), oled=OLED_ACT, oled_flip=True, parts=meta,
            top_parts=TOPP, main_parts=MAINP, main_pts=MAIN_PTS, main_holes=MAIN_HOLES, top_holes=TOP_PCB_HOLES,
            end_screws=END_SCREWS, back_screws=BACK_SCREWS, keys=[(u, key_v(u), kw) for u, kw, kd in KEYS],
            consts=dict(TP0=TP0, TP1=TP1, MZ0=MZ0, MZ1=MZ1, DZ=DZ, DX=DX, R_B=R_B, R_F=R_F, Z_AX=Z_AX, H=H, W=W, D0=D0,
                        XLR_X=XLR_X, XLR_Z=XLR_Z, USB_X=USB_X, TRRS_X=TRRS_X, PWR_X=PWR_X, LAMP_X=LAMP_X, PACK=PACK,
                        GL_V0=GL_V0, GL_V1=GL_V1, AA_V=AA_V, ENC_Y0=ENC_Y0, SHAFT_Y0=SHAFT_Y0))
json.dump(info, open(os.path.join(OUT, "parts_final.json"), "w"), indent=1)
log("overall", info["envelope"])
