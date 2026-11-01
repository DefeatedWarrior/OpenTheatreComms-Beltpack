"""Build the v1 order: per board, a JLC BOM + CPL for the side JLC assembles (Economic PCBA, one side), the Gerber zip, and
a hand-fit list; plus one LCSC cart for everything soldered by hand, rounded up to LCSC's minimum and multiple.

  python3 build_order.py lcsc_info.json        (lcsc_info.json: LCSC stock / minimum / multiple / price, read from lcsc.com)

Units: 2 beltpacks (main, top, pack lid) and 1 base station. JLC assembles 2 of each assembled board.
"""
import os, sys, csv, json, re, math, pickle, shutil, importlib.util
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
import pcbnew
FX = 1.43   # USD -> AUD (Wise mid-market, 30 Oct 2026); LCSC and JLC prices are listed in USD
HAND_SUB = {"C14663": "C1591", "C57112": "C1589", "C1002": "C19330", "C470892": "C48031087"}   # PE4259: LCSC has none; ZHHXDZ HX4259-63-ST is pin- and logic-identical   # JLC-only or out of stock at LCSC: same value, LCSC stock
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
IDX = pickle.load(open("/tmp/claude-0/-home-claude/9660d662-dc3d-52a1-975c-6584461bcbcb/scratchpad/jlc/idx.pkl", "rb"))
ROT_DB = "/tmp/claude-0/-home-claude/9660d662-dc3d-52a1-975c-6584461bcbcb/scratchpad/ext/JLCKicadTools/jlc_kicad_tools/cpl_rotations_db.csv"
LCSC = json.load(open(sys.argv[1])) if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else {}
OUT = os.path.join(HERE, "JLC order")

UNITS = {"main_pcb": 2, "top_pcb": 2, "base_pcb": 1, "pack_lid_pcb": 2, "dock_contact_pcb": 2}       # boards actually built
JLC_QTY = 2                                                                  # boards JLC assembles per design (its minimum)
SIDE = {}                                                                    # no JLC assembly: every part is hand-fitted (paste stencils)
# Cost cut: JLC keeps only the extended parts that are hard by hand; every other extended part is hand-soldered
KEEP_AT_JLC = {"C15134": "LIS3DH (LGA)", "C914209": "NAU88C22 (QFN)", "C22371519": "WS2812B-Mini-V3J (12 per board)",
               "C2682616": "MAX17048 (TDFN 2 x 2)",
               "C470892": "PE4259 (LCSC has none; JLC has 84)"}
SKIP_BLOCKS = {"base_pcb": {"Audio"}}                                        # base station v1: radio only, audio section unfitted
NAMES = {"main_pcb": "Beltpack main", "top_pcb": "Beltpack top", "base_pcb": "Base station", "pack_lid_pcb": "Beltpack pack lid", "dock_contact_pcb": "Beltpack dock contacts"}
DESIGN = {"main_pcb": "pcb_main", "top_pcb": "pcb_top", "base_pcb": "pcb_base", "pack_lid_pcb": "pcb_lid", "dock_contact_pcb": "pcb_dock"}

def load_design(d):
    p = os.path.join(ROOT, d, "design.py"); sys.path.insert(0, os.path.dirname(p))
    spec = importlib.util.spec_from_file_location(d + "_design", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    sys.path.pop(0); return m.C

# ------------------------------------------------------------------ part choices
# Chips, connectors and the like, by the MPN in the design (LCSC number, note). Passives are picked below.
MPN = {
    "ST USBLC6-2SC6": ("C7519", ""), "TOPPOWER TP4056 (ESOP-8)": ("C16581", ""), "SS14 (SMA)": ("C2480", ""),
    "AOS AO3401A": ("C15127", ""), "AOS AO3400A": ("C20917", ""), "onsemi BSS138": ("C7420339", "any BSS138 (same SOT-23 pinout)"),
    "TI TLV75733PDBVR": ("C485517", ""), "Diodes BAT54WS": ("C7502694", "any BAT54WS"), "Nexperia PESD5V0S1BA": ("C19224", ""),
    "Analog MAX17048G+T10": ("C2682616", ""), "Espressif ESP32-S3-WROOM-1-N8R8": ("C2913201", ""), "pSemi PE4259-63": ("C470892", ""),
    "Nuvoton NAU88C22YG": ("C914209", ""), "TI TCA9555PWR": ("C465732", ""), "ST LIS3DHTR": ("C15134", ""),
    "Murata BLM18PG601SN1D": ("C1002", "600R 0603 bead (any 600R at 100 MHz)"),
    "600R 0603 ferrite bead (Sunlord GZ1608D601TF or equal)": ("C1002", ""),
    "0603 0R (or Murata BLM18PG121SN1D)": ("C21189", "0R link"), "0603 0R or RF inductor": ("C21189", "0R until tuned"),
    "GCT USB4105-GF-A": ("C165948", "HRO TYPE-C-31-M-12: same land pattern; the GCT part is out of stock"),
    "PJ-320D": ("C431535", "SHOU HAN PJ-320D: pads match the footprint"), "JST SM10B-SRSS-TB": ("C160409", ""),
    "Hirose U.FL-R-SMT-1(10)": ("C88374", "U.FL-R-SMT-1(80), same part, bigger reel"), "Alps SKRTLAE010": ("C110293", ""),
    "C&K PTS815 SJM 250 SMTR LFS": ("C2689510", ""), "Lite-On LTST-C191KRKT": ("C125099", ""), "Lite-On LTST-C191KGKT": ("C125098", ""),
    "Hirose FH12-30S-0.5SH(55)": ("C506793", ""), "JST BM10B-SRSS-TB": ("C160396", ""),
    "3 mm white LED, 20 mA": ("C282138", "Everlight 204-15UTC, white, 3 mm"),
    "Diodes AP63205WU-7": ("C2071056", ""), "SS34 (SMA)": ("C8678", ""), "SMAJ26A": ("C19077543", ""),
    "4.7 uH, 2.5 A, 4x4 mm (Bourns SRN4018-4R7M or equal)": ("C1330726", "Bourns SRN4018TA-4R7M"),
    "Xinyangze YZ08415060P-02": ("C7471674", "Xinyangze spring pin: 4.5 mm free, 4.0 working, 3.7 fully in; 0.8 mm tail in the 1.0 mm hole"),
    "Alps EC11N1520402": ("C470704", "Alps EC11, no switch, 30 detents / 15 pulses; fits the PEC12R footprint"),
    "JST B2B-XH-A(LF)(SN)": ("C158012", "JST XH 2-pin battery input, pin 1 +"),
    "JST SM04B-SRSS-TB(LF)(SN)": ("C160404", "Dock socket on the main board (J12)"),
    "JST BM04B-SRSS-TB(LF)(SN)": ("C495539", "JST BM04B-SRSS-TBT: the same socket in other tape packaging (the -TB is out of stock)"),
    "B5819W (SOD-123)": ("C8598", "Dock power diode"),
    "74AHCT1G125 (SOT-23-5)": ("C7484", "TI SN74AHCT1G125DBVR"), "Worldsemi WS2812B-Mini-V3J": ("C22371519", ""),
    "Molex 73251-2120 SMA edge-mount jack, 1.6 mm board": ("C22467594", "MyAntenna A-SMA-KE-13.5A edge SMA: same pads as the Molex footprint, a fifth of the price"), "CUI PJ-063AH (5.5 x 2.1 mm, centre +)": ("C22434582", ""),
    "12 x 12 mm tactile switch with round cap": ("C136701", "HRO K2-1103DP, 12 x 12 x 12 mm"),
    "6 x 6 mm tactile switch, 13 mm tall": ("C2837523", "Kinghelm KH-6X6X13H-TJ"),
    "EC11 encoder with push switch, 20 mm shaft": ("C470742", "Alps EC11E09244BS (push switch)"),
    "Waveshare ESP32-P4-NANO (SKU 29026) on 2x 2x13 2.54 mm female sockets, 8.5 mm": ("C64320", "2x 2x13 female sockets per board (the NANO itself: Waveshare)"),
    "1x4 female socket for a 1.3 in 128x64 I2C OLED module (SH1106, address 0x3C)": ("C2718488", "1x4 female socket (the OLED module: elsewhere)"),
    "Lite-On LTST-C191KGKT ": ("C125098", ""),
}
# parts no LCSC number covers: (where to buy, note)
OTHER = {
    "Elecrow LR2021 module (LMM16121D)": "Elecrow (elecrow.com), LR2021 LoRa module",
    "Mill-Max 0906-1-15-20-72-14-11-0": "element14 / DigiKey / Mouser (Mill-Max 0906-1-15-20-72-14-11-0)",
    "8 x 2.7 mm coin vibration motor, 3 V": "8 mm coin vibration motor, 3 V, flying leads (Core Electronics or AliExpress)",
    "Bourns PEC12R-4215F-N0024": "element14 AU / DigiKey (LCSC only has the -S0024 switch version, 28 in stock)",
}
NOT_A_PART = ("Neutrik", "OLED panel tail")                     # wire pads for panel connectors (bought with the case hardware)

def rank(p): return (p["attrs"].get("Basic/Extended") == "Basic", p["lib"] == "expand", p["stock"])
def num(x):
    try: return float(x)
    except Exception: return None
RVAL = {"k": 1e3, "M": 1e6}
def rparse(v):
    v = v.strip(); m = re.fullmatch(r"([\d.]+)([kM]?)", v); return float(m.group(1)) * RVAL.get(m.group(2), 1) if m else None
CVAL = {"p": 1e-12, "n": 1e-9, "u": 1e-6}
def cparse(v):
    m = re.fullmatch(r"([\d.]+)([pnu])", v.strip()); return float(m.group(1)) * CVAL[m.group(2)] if m else None
PCACHE = {}
def pick_passive(c):
    fp = c["fp"].split(":")[1]; pkg = "1206" if "1206" in fp else "0603"
    key = (c["lib_id"], c["value"], pkg, c["mpn"])
    if key in PCACHE: return PCACHE[key]
    best = None
    if c["lib_id"] == "Device:R" or (c["lib_id"] == "Device:FerriteBead_Small" and c["value"] in ("0R", "0")):
        val = 0.0 if c["value"] in ("0", "0R") else rparse(c["value"])
        cands = [p for p in IDX.values() if p["attrs"].get("Package") == pkg and num(p["attrs"].get("Resistance")) is not None
                 and abs(num(p["attrs"]["Resistance"]) - val) <= 1e-6 * max(val, 1)
                 and (val == 0 or abs(num(p["attrs"].get("Tolerance")) or 99) <= 1.0) and p["stock"] > 2000]
        best = max(cands, key=rank) if cands else None
    elif c["lib_id"] == "Device:C":
        val = cparse(c["value"]); m = re.search(r"([\d.]+) ?V", c["mpn"]); vmin = float(m.group(1)) if m else 16.0
        diel = ("C0G", "NP0") if "C0G" in c["mpn"] else ("X7R",) if "X7R" in c["mpn"] else ("X5R", "X7R")
        cands = [p for p in IDX.values() if p["attrs"].get("Package") == pkg and num(p["attrs"].get("Capacitance")) and val
                 and abs(num(p["attrs"]["Capacitance"]) - val) < 1e-3 * val and (num(p["attrs"].get("Rated Voltage")) or 0) >= vmin
                 and p["attrs"].get("Temperature Coefficient") in diel and p["stock"] > 2000]
        best = max(cands, key=rank) if cands else None
    PCACHE[key] = (best["lcsc"], "") if best else (None, "no match")
    return PCACHE[key]

def choose(c):
    """(lcsc or None, note, other-supplier text or None)"""
    if c["lib_id"] in ("Device:R", "Device:C") or (c["lib_id"] == "Device:FerriteBead_Small" and c["value"] in ("0R", "0")):
        if c["mpn"] in MPN: return MPN[c["mpn"]] + (None,)
        l, n = pick_passive(c); return l, n, None
    if c["mpn"] in MPN: return MPN[c["mpn"]] + (None,)
    if c["mpn"] in OTHER: return None, "", OTHER[c["mpn"]]
    return None, "NOT MAPPED", None

# ------------------------------------------------------------------ rotation corrections (kicad-jlcpcb-tools / JLCKicadTools logic)
ROTS = []
for row in list(csv.reader(open(ROT_DB)))[1:]:
    if row: ROTS.append((re.compile(row[0].strip().strip('"')), int(float(row[1]))))
def jlc_rotation(fp):
    rot = fp.GetOrientation().AsDegrees()
    if fp.IsFlipped(): rot = (180 - rot) % 360
    name = str(fp.GetFPID().GetLibItemName()); best = None
    for rx, corr in ROTS:
        m = rx.search(name)
        if m and (best is None or len(m.group(0)) > best[0]): best = (len(m.group(0)), corr)
    return (rot + (best[1] if best else 0)) % 360, (best[1] if best else 0)
def jlc_position(fp):
    pads = [p for p in fp.Pads() if p.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_PTH)]
    if not pads: c = fp.GetPosition()
    else:
        bb = pads[0].GetBoundingBox()
        for p in pads[1:]: bb.Merge(p.GetBoundingBox())
        c = bb.GetCenter()
    return pcbnew.ToMM(c.x) - 150.0, 105.0 - pcbnew.ToMM(c.y)

def jlc_info(l):
    p = IDX.get(l)
    if not p: return dict(cls="not stocked at JLC", stock=0, price=None, ext=None)
    cls = p["attrs"].get("Basic/Extended", "Extended"); cls = "Preferred" if p["lib"] == "expand" and cls != "Basic" else cls
    pr = None
    for t in p.get("price") or []:
        if pr is None or t["qFrom"] <= 10: pr = t["price"]
    return dict(cls=cls, stock=p["stock"], price=pr, ext=(cls == "Extended"))

# ------------------------------------------------------------------ build
shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
if os.path.exists(os.path.join(HERE, "ORDER_README.md")): shutil.copy(os.path.join(HERE, "ORDER_README.md"), os.path.join(OUT, "README.md"))
hand_all, other_all, summary, problems = {}, {}, [], []
for board in ("main_pcb", "top_pcb", "base_pcb", "pack_lid_pcb", "dock_contact_pcb"):
    C = {c["ref"]: c for c in load_design(DESIGN[board])}
    b = pcbnew.LoadBoard(os.path.join(ROOT, "kicad_proj", board, board + ".kicad_pcb"))
    odir = os.path.join(OUT, NAMES[board]); os.makedirs(odir)
    gz = os.path.join(ROOT, "kicad_proj", board, "fab", board + "_gerbers.zip"); shutil.copy(gz, os.path.join(odir, f"{board}_gerbers.zip"))
    bom, cpl, hand = {}, [], []
    for fp in b.GetFootprints():
        r = fp.GetReference(); c = C.get(r)
        if c is not None and c.get("block") in SKIP_BLOCKS.get(board, ()): continue
        if c is None or c.get("dnp") or r.startswith(("H", "TP")) or c["lib_id"] in ("Connector:TestPoint", "Mechanical:MountingHole"): continue
        if any(k in c["mpn"] for k in NOT_A_PART) or board == "pack_lid_pcb": continue
        l, note, other = choose(c)
        side = "B" if fp.IsFlipped() else "F"
        smd = all(p.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_NPTH) or pcbnew.ToMM(p.GetDrillSizeX()) <= 0.5 for p in fp.Pads())   # thermal vias are fine
        jlc_side = SIDE.get(board) == side
        hand_only = other is not None or not smd or r in ("J2", "J3") and board == "base_pcb" or r == "U6" and board == "main_pcb" or r == "U4" and board == "base_pcb"
        if l and not hand_only and (jlc_info(l)["ext"] or jlc_info(l)["cls"] == "not stocked at JLC") and l not in KEEP_AT_JLC: hand_only = True
        if l is None and other is None: problems.append(f"{board} {r} {c['mpn'] or c['value']}: {note}")
        if jlc_side and not hand_only and l:
            g = bom.setdefault(l, dict(comment=c["mpn"] if c["lib_id"] not in ("Device:R", "Device:C") else f"{c['value']} {c['mpn']}", refs=[],
                                         fp=c["fp"].split(":")[1], note=note))
            g["refs"].append(r)
            x, y = jlc_position(fp); rot, corr = jlc_rotation(fp)
            cpl.append((r, f"{x:.4f}", f"{y:.4f}", "Top" if side == "F" else "Bottom", f"{rot:.0f}", corr))
        else:
            hand.append((r, c, l, note, other, side))
    key = lambda s: (re.match(r"[A-Z]+", s).group(0), int(re.search(r"\d+", s).group(0)))
    # Paste layers (JLC's stencil for its side, your stencils for yours): no paste on pads that get no part from that
    # stencil: unfitted parts (DNP, base audio) on both sides, and the parts you fit by hand on JLC's side
    if board != "pack_lid_pcb":
        import tempfile, subprocess, zipfile
        nofit = set()   # unfitted pads (DNP, base audio) keep their paste, by choice: pre-tinned for fitting later
        handjlc = {r for r, c, l, note, other, side in hand if SIDE.get(board) and side == SIDE[board]}
        b2 = pcbnew.LoadBoard(os.path.join(ROOT, "kicad_proj", board, board + ".kicad_pcb")); stripped = {"F": set(), "B": set()}
        for fp in b2.GetFootprints():
            r = fp.GetReference(); side = "B" if fp.IsFlipped() else "F"
            if r in nofit or r in handjlc:
                for p in fp.Pads():
                    ls = p.GetLayerSet()
                    for pl, sd in ((pcbnew.F_Paste, "F"), (pcbnew.B_Paste, "B")):
                        if ls.Contains(pl): ls.RemoveLayer(pl); stripped[sd].add(r)
                    p.SetLayerSet(ls)
        td = tempfile.mkdtemp(); tp = os.path.join(td, board + ".kicad_pcb"); b2.Save(tp)
        subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "-o", td + "/", "--layers", "F.Paste,B.Paste", "--subtract-soldermask", "--use-drill-file-origin", tp], check=True, capture_output=True)
        newf = {f: open(os.path.join(td, f), "rb").read() for f in os.listdir(td) if f.endswith((".gtp", ".gbp"))}
        zp = os.path.join(odir, f"{board}_gerbers.zip"); old = zipfile.ZipFile(zp); items = [(n, old.read(n)) for n in old.namelist()]; old.close()
        assert set(newf) <= {n for n, _ in items}, (newf.keys(), [n for n, _ in items])
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for n, d in items: z.writestr(n, newf.get(n, d))
        print(board, "no paste on: F", sorted(stripped["F"], key=key), "| B", sorted(stripped["B"], key=key))
    # JLC BOM + CPL
    if bom:
        with open(os.path.join(odir, f"{board}_JLC_BOM.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
            for l, g in sorted(bom.items(), key=lambda kv: key(sorted(kv[1]["refs"], key=key)[0])):
                w.writerow([g["comment"], ",".join(sorted(g["refs"], key=key)), g["fp"], l])
        with open(os.path.join(odir, f"{board}_JLC_CPL.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
            for row in sorted(cpl, key=lambda r_: key(r_[0])): w.writerow(row[:5])
    # hand list per board
    with open(os.path.join(odir, f"{board}_hand_fit.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Designator", "Value", "Part", "LCSC Part #", "Side", "Other supplier", "Note"])
        for r, c, l, note, other, side in sorted(hand, key=lambda h: key(h[0])):
            w.writerow([r, c["value"], c["mpn"], HAND_SUB.get(l, l) or "", "top" if side == "F" else "bottom", other or "", note])
    # tallies
    n_units = UNITS[board]
    for r, c, l, note, other, side in hand:
        if l: hand_all.setdefault(l, dict(qty=0, refs=[], desc=c["mpn"] if c["lib_id"] not in ("Device:R", "Device:C") else f"{c['value']} {c['mpn']}", note=note))
        if l: hand_all[l]["qty"] += n_units * (2 if c["mpn"].startswith("Waveshare") else 1); hand_all[l]["refs"].append(f"{NAMES[board]} {r}")
        if other: other_all.setdefault(other, dict(qty=0, refs=[]))["qty"] += n_units; other_all.setdefault(other, dict(qty=0, refs=[]))["refs"].append(f"{NAMES[board]} {r}")
    ext = sorted({l for l in bom if jlc_info(l)["cls"] == "Extended"}); nostock = sorted({l for l in bom if jlc_info(l)["cls"] == "not stocked at JLC"})
    cost = sum((jlc_info(l)["price"] or 0) * len(g["refs"]) * JLC_QTY for l, g in bom.items())
    summary.append(dict(board=board, name=NAMES[board], jlc_side=SIDE.get(board), jlc_lines=len(bom), jlc_parts=sum(len(g["refs"]) for g in bom.values()),
                        extended=ext, nostock=nostock, parts_cost=round(cost, 2), hand=len(hand),
                        low_stock=[f"{l} ({jlc_info(l)['stock']})" for l in bom if 0 < jlc_info(l)["stock"] < 20 * JLC_QTY * len(bom[l]["refs"])]))
# LCSC cart: spares, then the LCSC minimum and multiple
cart = []
merged = {}
for l, h in hand_all.items():
    l2 = HAND_SUB.get(l, l); m = merged.setdefault(l2, dict(qty=0, refs=[], desc=h["desc"], note=h["note"] or ("ZHHXDZ HX4259-63-ST: same pinout and control logic as PE4259 (CTRL high = RF1)" if l == "C470892" else f"replaces JLC's {l} (not stocked at LCSC)" if l2 != l else "")))
    m["qty"] += h["qty"]; m["refs"] += h["refs"]
# off-board parts bought in the same LCSC cart
if "C22467594" in merged: merged["C22467594"]["desc"] = "SMA jack, edge mount, 1.6 mm board (fits the Molex 73251-2120 footprint)"
merged.setdefault("C496579", dict(qty=0, refs=[], desc="Antenna, 915 MHz rubber whip, SMA male, 105 mm", note="BAT WIRELESS BW915JWX105-10KJ"))
merged["C496579"]["qty"] += 2; merged["C496579"]["refs"].append("Base station J2/J3 (off board)")
other_all.setdefault("Core Electronics CE09458 915 MHz U.FL flex antenna, 15 x 65 mm, 200 mm lead (A$2.30)", dict(qty=4, refs=["Beltpack main J5, J6 (two per pack)"]))
for l, h in sorted(merged.items(), key=lambda kv: kv[1]["desc"]):
    p = IDX.get(l, {}); info = LCSC.get(l, {})
    passive = re.match(r"[\d.]+[pnuRkM]?\s+0603|[\d.]+[pnu]?\s+1206|^\d", h["desc"]) is not None
    need = h["qty"] + (max(2, math.ceil(h["qty"] * 0.2)) if passive else (1 if h["qty"] >= 2 else 0))   # spares: small parts get lost
    if (info.get("tiers") or [[0, 0]])[0][1] >= 1.0: need = h["qty"]                                  # no spares on parts over US$1
    if l in ("C15134", "C2682616", "C914209"): need = h["qty"] + 1                                       # LGA / TDFN / QFN: one spare each
    mn, mult = info.get("min") or 1, info.get("mult") or 1
    q = max(need, mn); q = math.ceil(q / mult) * mult
    unit = None
    for qf, pr in (info.get("tiers") or []):
        if q >= qf: unit = pr
    cart.append(dict(lcsc=l, qty=q, need=h["qty"], mpn=info.get("mpn") or p.get("mfr", ""), desc=h["desc"], stock=info.get("stock"),
                     min=mn, mult=mult, unit=unit, total=round(q * unit, 2) if unit else None, refs="; ".join(h["refs"]), note=h["note"]))
with open(os.path.join(OUT, "LCSC_cart_hand_parts.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["LCSC Part Number", "Quantity", "Manufacturer Part", "Description", "Needed (2 beltpacks + 1 base)", "LCSC stock", "LCSC min", "LCSC multiple", "Unit price (A$)", "Line total (A$)", "Used on", "Note"])
    for x in cart: w.writerow([x["lcsc"], x["qty"], x["mpn"], x["desc"], x["need"], x["stock"], x["min"], x["mult"], round(x["unit"] * FX, 4) if x["unit"] else None, round(x["total"] * FX, 2) if x["total"] else None, x["refs"], x["note"]])
with open(os.path.join(OUT, "LCSC_cart_upload.csv"), "w", newline="") as f:          # the two columns LCSC's BOM tool needs
    w = csv.writer(f); w.writerow(["LCSC Part Number", "Quantity"])
    for x in cart: w.writerow([x["lcsc"], x["qty"]])
# Everything not on the LCSC cart, by supplier. The design-derived lines are checked against other_all so a design change can't drift.
auto = {"8 mm coin vibration motor": 2, "LR2021": 3, "CE09458": 4}
for k, q in auto.items():
    got = [v["qty"] for kk, v in other_all.items() if k in kk]
    if got != [q]: problems.append(f"other-supplier quantity for {k}: design says {got}, buy list says {q}")
if len(other_all) != len(auto): problems.append(f"new other-supplier part in the design: {sorted(other_all)}")
OTHER_BUY = [  # supplier, part, qty, approx A$ each (None = varies), used on, note
    ("Elecrow (elecrow.com)", "LR2021 LoRa module (LMM16121D)", 3, 6.90 * FX, "Beltpack main U6 (x2); Base station U4", "US$6.90 each"),
    ("Waveshare (waveshare.com)", "ESP32-P4-NANO, SKU 29026", 1, 19 * FX, "Base station", "Core Electronics has it for about A$61 if you need it sooner"),
    ("Waveshare (waveshare.com)", "PoE module for the ESP32-P4-NANO (optional)", 0, 15, "Base station", "Only if you want PoE power"),
    ("Core Electronics", "CE09458 915 MHz U.FL flex antenna, 15 x 65 mm, 200 mm lead", 4, 2.30, "Beltpack main J5, J6 (two per pack)", "Check 65 mm fits the pack ends"),
    ("Core Electronics or AliExpress", "8 mm coin vibration motor, 3 V, flying leads", 2, None, "Beltpack main M1", ""),
    ("AliExpress", "1.3 in 128x64 I2C OLED module (SH1106)", 1, None, "Base station", "Check its pin order is GND, VCC, SCL, SDA"),
    ("AliExpress (item 1005006789720033, colour \"sh1106 white\")", "1.3 in 128x64 OLED panel, SH1106, 30-pin 0.7 mm solder tail", 3, 1.79, "Beltpack top J2", "One spare. The tail solders straight to the board"),
    ("AliExpress", "JST SH 4-pin cable, 1.0 mm pitch, 40-60 mm, same-side (pin 1 to pin 1), pack of 10 (2 needed)", 1, 3.0, "Beltpack main J12 to the dock contact board", "Packs of 10, about A$3. Check with a meter"),
    ("Jaycar or element14 AU", "REAN 4-pin XLR panel connector (headset)", 2, 8.0, "Beltpack", ""),
    ("Your choice", "Beltpack Li-ion cells with a JST XH 2-pin plug", 2, None, "Beltpack J11", "Check the plug polarity: pin 1 must be +"),
]
with open(os.path.join(OUT, "Other_suppliers.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Supplier", "Part", "Quantity (2 beltpacks + 1 base)", "Approx. A$ each", "Approx. A$ line", "Used on", "Note"])
    for s, p, q, each, used, note in OTHER_BUY:
        w.writerow([s, p, q, round(each, 2) if each else "", round(each * q, 2) if each else "", used, note])
JLC_BUY = [  # folder, gerber zip, layers, thickness, finish, stencil
    ("Beltpack main", "main_pcb_gerbers.zip", 4, "1.6", "HASL (with lead) (JLC04161H-7628 stack)", "Frameless 380 x 280 mm, Top + Bottom on a single stencil, 0.10 mm"),
    ("Beltpack top", "top_pcb_gerbers.zip", 2, "1.6", "HASL (with lead)", "Frameless 380 x 280 mm, Top + Bottom on a single stencil, 0.12 mm"),
    ("Base station", "base_pcb_gerbers.zip", 2, "1.6", "HASL (with lead)", "Frameless 380 x 280 mm, Top only, 0.12 mm"),
    ("Beltpack pack lid", "pack_lid_pcb_gerbers.zip", 2, "0.8", "HASL (with lead)", "None"),
    ("Beltpack dock contacts", "dock_contact_pcb_gerbers.zip", 2, "0.8", "HASL (with lead)", "None"),
]
with open(os.path.join(OUT, "JLC_boards.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Folder", "Upload", "Layers", "Thickness (mm)", "Surface finish", "Quantity", "Stencil", "PCB Assembly"])
    for fo, z, L, t, fin, st in JLC_BUY: w.writerow([fo, z, L, t, fin, 5, st, "Off"])
json.dump(dict(summary=summary, cart=cart, other=other_all, problems=problems), open(os.path.join(HERE, "order_summary.json"), "w"), indent=1)
for s in summary: print(s)
print("cart lines", len(cart), "cart total A$", round(FX * sum(x["total"] or 0 for x in cart), 2), "missing LCSC info:", [x["lcsc"] for x in cart if x["unit"] is None])
print("problems:", problems)
