"""Build ready-to-open KiCad projects (one per board) from the DXF hand-off.

Each project has: the board outline on Edge.Cuts with true arcs, M2 mounting-hole footprints, copper keep-outs,
placement guides on User layers (Place.F, Place.B, Case.Ref), notes on Cmts.User, the grid/aux origin at the
board datum used in placement.csv, and a board-only footprint carrying the enclosure STEP so the 3D viewer shows
the case around the board. Written with KiCad 7's pcbnew API, so it opens in KiCad 7, 8 and 9.
"""
import os, json, math, uuid, datetime
import ezdxf, pcbnew

here = os.path.dirname(os.path.abspath(__file__))
KD = os.path.join(here, "out", "kicad"); PRJ = os.path.join(here, "kicad_proj")
info = json.load(open(os.path.join(KD, "boards.json")))
OX, OY = 150.0, 105.0                      # board datum on the A4 sheet (mm)
MM = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(MM(float(OX + x)), MM(float(OY - y)))     # DXF (Y up) -> KiCad (Y down)

BOARDS = {
    "top_pcb": dict(title="Beltpack top PCB", layers=2, thick=1.6, holes_ref="H",
                    model=dict(rot=(-90.0, 0.0, 0.0), off=(0.0, -15.0, -33.2)),
                    notes=["Viewed from above; F.Cu = top side (keys, OLED, status LEDs). B.Cu: encoders, OLED FPC connector, JST SH, IO expander.",
                           "Datum (grid origin) = board centre, 15 mm behind the case front. +X right, +Y toward the hip (back) edge.",
                           "Height: F 3.0 mm max (2.5 under keycap flanges, 1.4 under the OLED glass). B: encoders 6.5; nothing else inside R17.4 of each dial axis."]),
    "main_pcb": dict(title="Beltpack main PCB", layers=4, thick=1.6, holes_ref="H",
                     model=dict(rot=(0.0, 0.0, 0.0), off=(0.0, 0.0, 8.2)),
                     keepouts=[("Antennas: no copper (ESP32 Wi-Fi + 915 MHz antenna B)", [(-47.5, -14.3), (-39.5, -14.3), (-39.5, 14.5), (-47.5, 14.5)])],
                     notes=["Viewed from the front; F.Cu = front face (buttons, USB-C, 3.5 mm, power, lamp, motor). B.Cu: ESP32-S3, LR2021, codec, U.FL, JST SH, pogo pins.",
                            "Datum (grid origin) = case centre. +X right, +Y up. Bottom edge at Y = -36.0.",
                            "Height: F 5.0 mm max (4.0 behind the button recess). B 3.7 mm max over the battery pack outline, about 15 elsewhere.",
                            "Antenna diversity: LR2021 ANT_LF -> pi match -> PE4259 SPDT -> U.FL A (right end) / U.FL B (left end). Control from an ESP32 GPIO.",
                            "Keep copper back from both ends: antenna A is about 8 mm past the right edge; antenna B is 3 mm past the left edge, so the left strip (x < -39.5) is a no-copper area."]),
    "pack_lid_pcb": dict(title="Beltpack battery pad board", layers=2, thick=0.8, holes_ref="H",
                         model=dict(rot=(0.0, 0.0, 0.0), off=(0.0, 0.0, 13.5)),
                         notes=["Viewed from the front; F.Cu = pad side (BAT+, NTC, BAT-), ENIG.", "Datum = case centre, same frame as the main PCB."]),
}
LAYER_MAP = {"Edge.Cuts": pcbnew.Edge_Cuts, "Place_F": pcbnew.User_1, "Place_B": pcbnew.User_2, "Mech": pcbnew.User_3}

def seg(board, a, b, layer, w=0.1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(a); s.SetEnd(b); s.SetLayer(layer); s.SetWidth(MM(w)); board.Add(s)
def arc(board, c, r, a0, a1, layer, w=0.1):
    sweep = (a1 - a0) % 360 or 360
    pt = lambda a: (c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)))
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(P(*pt(a0)), P(*pt(a0 + sweep / 2)), P(*pt(a0 + sweep))); s.SetLayer(layer); s.SetWidth(MM(w)); board.Add(s)
def circle(board, c, r, layer, w=0.1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_CIRCLE); s.SetStart(P(*c)); s.SetEnd(P(c[0] + r, c[1])); s.SetLayer(layer); s.SetWidth(MM(w)); board.Add(s)
def text(board, s_, pos, layer, size=0.8, left=True):
    t = pcbnew.PCB_TEXT(board); t.SetText(s_); t.SetPosition(pos); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(size * 0.15))
    if left: t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(t)

def hole_fp(board, ref, x, y, d):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_2.2mm_M2")); fp.SetReference(ref); fp.SetValue("MountingHole_2.2mm_M2")
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    pad = pcbnew.PAD(fp); pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(pcbnew.VECTOR2I(MM(d), MM(d))); pad.SetDrillSize(pcbnew.VECTOR2I(MM(d), MM(d))); pad.SetLayerSet(pad.UnplatedHoleMask())
    pad.SetPos0(pcbnew.VECTOR2I(0, 0)); fp.Add(pad)
    for layer, r, w in ((pcbnew.F_CrtYd, 2.45, 0.05), (pcbnew.B_CrtYd, 2.45, 0.05), (pcbnew.Cmts_User, 2.2, 0.15)):
        c = pcbnew.FP_SHAPE(fp); c.SetShape(pcbnew.SHAPE_T_CIRCLE); c.SetStart0(pcbnew.VECTOR2I(0, 0)); c.SetEnd0(pcbnew.VECTOR2I(MM(r), 0))
        c.SetLayer(layer); c.SetWidth(MM(w)); fp.Add(c)
    fp.Reference().SetPos0(pcbnew.VECTOR2I(0, MM(-3.2))); fp.Value().SetPos0(pcbnew.VECTOR2I(0, MM(3.2))); fp.Value().SetLayer(pcbnew.F_Fab)
    fp.SetPosition(P(x, y)); board.Add(fp)

def enclosure_fp(board, model):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("OpenTheatreComms", "REF_Enclosure")); fp.SetReference("REF**"); fp.SetValue("Enclosure 3D reference")
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY)
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False); fp.Value().SetLayer(pcbnew.F_Fab)
    m = pcbnew.FP_3DMODEL(); m.m_Filename = "${KIPRJMOD}/../3d/enclosure_ref.step"
    m.m_Offset = pcbnew.VECTOR3D(*model["off"]); m.m_Rotation = pcbnew.VECTOR3D(*model["rot"]); m.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
    fp.Models().push_back(m)
    fp.SetPosition(P(0, 0)); fp.SetLocked(True); board.Add(fp)

def keepout(board, name, pts, ncu):
    z = pcbnew.ZONE(board); z.SetIsRuleArea(True); z.SetZoneName(name)
    for f in (z.SetDoNotAllowCopperPour, z.SetDoNotAllowVias, z.SetDoNotAllowTracks, z.SetDoNotAllowPads): f(True)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET(); [ls.AddLayer(l) for l in ([pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu] if ncu == 4 else [pcbnew.F_Cu, pcbnew.B_Cu])]
    z.SetLayerSet(ls); o = z.Outline(); o.NewOutline()
    for x, y in pts: p = P(x, y); o.Append(p.x, p.y)
    board.Add(z)

SCH = """(kicad_sch (version 20230121) (generator eeschema)
  (uuid {u})
  (paper "A4")
  (title_block (title "{t}") (date "{d}") (rev "0.1") (company "OpenTheatreComms"))
  (lib_symbols)
  (sheet_instances (path "/" (page "1")))
)
"""
today = datetime.date.today().isoformat()
for name, B in BOARDS.items():
    folder = os.path.join(PRJ, name); os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".kicad_pcb")
    board = pcbnew.NewBoard(path)
    board.SetCopperLayerCount(B["layers"])
    ds = board.GetDesignSettings(); ds.SetBoardThickness(MM(B["thick"]))
    ls = board.GetEnabledLayers()
    for l in (pcbnew.User_1, pcbnew.User_2, pcbnew.User_3, pcbnew.Cmts_User, pcbnew.F_Fab, pcbnew.B_Fab, pcbnew.F_CrtYd, pcbnew.B_CrtYd): ls.AddLayer(l)
    board.SetEnabledLayers(ls)
    board.SetLayerName(pcbnew.User_1, "Place.F"); board.SetLayerName(pcbnew.User_2, "Place.B"); board.SetLayerName(pcbnew.User_3, "Case.Ref")
    ds.SetAuxOrigin(P(0, 0)); ds.SetGridOrigin(P(0, 0))
    tb = board.GetTitleBlock(); tb.SetTitle(B["title"]); tb.SetCompany("OpenTheatreComms"); tb.SetRevision("0.1"); tb.SetDate(today)
    tb.SetComment(0, "Outline, holes and placement guides from the CadQuery reference model (cad/final_bp.py)")
    # outline + guides from the full DXF
    doc = ezdxf.readfile(os.path.join(KD, name + ".dxf"))
    for e in doc.modelspace():
        layer = LAYER_MAP.get(e.dxf.layer)
        if layer is None: continue
        t = e.dxftype()
        if t == "LINE": seg(board, P(e.dxf.start.x, e.dxf.start.y), P(e.dxf.end.x, e.dxf.end.y), layer)
        elif t == "ARC": arc(board, (e.dxf.center.x, e.dxf.center.y), e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle, layer)
        elif t == "CIRCLE":
            if layer == pcbnew.Edge_Cuts and e.dxf.radius <= 1.6: continue
            circle(board, (e.dxf.center.x, e.dxf.center.y), e.dxf.radius, layer, 0.1 if layer == pcbnew.Edge_Cuts else 0.08)
        elif t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points()]
            for a, b_ in zip(pts, pts[1:]): seg(board, P(*a), P(*b_), layer, 0.08)
        elif t == "TEXT": text(board, e.dxf.text, P(e.dxf.insert.x, e.dxf.insert.y), layer, 0.7)
    for i, (x, y, d) in enumerate(info["boards"][name]["holes"]): hole_fp(board, f"{B['holes_ref']}{i+1}", x, y, d)
    for nm, pts in B.get("keepouts", []): keepout(board, nm, pts, B["layers"])
    enclosure_fp(board, B["model"])
    bb = info["summary"][name]["bbox"]
    for k, line in enumerate(B["notes"]): text(board, line, P(bb[0], bb[1] - 10 - 2.2 * k), pcbnew.Cmts_User, 1.0)
    pcbnew.SaveBoard(path, board)
    open(os.path.join(folder, name + ".kicad_sch"), "w").write(SCH.format(u=uuid.uuid4(), t=B["title"], d=today))
    print(name, "->", path)

# placement_map.csv per project: the snap script reads it (fill in the "ref" column)
import csv
for name in BOARDS:
    with open(os.path.join(PRJ, name, "placement_map.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["part", "side", "x", "y", "rot", "ref"])
        for p in info["boards"][name]["parts"]: w.writerow([p["label"], p["side"], round(p["X"], 2), round(p["Y"], 2), "", ""])
