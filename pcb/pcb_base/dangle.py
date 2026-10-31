"""Remove track stubs the DRC reports as dangling (left by the tidy pass at the codec fan), then re-run the DRC."""
import os, re, sys
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints"); os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.abspath(os.path.join(HERE, "..", "kicad_proj", "base_pcb", "base_pcb.kicad_pcb")); RPT = os.path.join(HERE, "out", "drc.rpt")
for it in range(3):
    txt = open(RPT).read()
    hits = re.findall(r"\[track_dangling\].*?\n.*?\n\s+@\(([\d.]+) mm, ([\d.]+) mm\): Track \[([^\]]*)\]", txt)
    if not hits: break
    b = pcbnew.LoadBoard(PCB); n = 0
    for x, y, net in hits:
        p = pcbnew.VECTOR2I(pcbnew.FromMM(float(x)), pcbnew.FromMM(float(y)))
        for t in list(b.GetTracks()):
            if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net and (t.GetStart() - p).EuclideanNorm() < 2000 or \
               t.GetClass() == "PCB_TRACK" and t.GetNetname() == net and (t.GetEnd() - p).EuclideanNorm() < 2000:
                if pcbnew.ToMM(t.GetLength()) < 1.0: b.Delete(t); n += 1; break
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(PCB)
    b2 = pcbnew.LoadBoard(PCB); pcbnew.WriteDRCReport(b2, RPT, pcbnew.EDA_UNITS_MILLIMETRES, True)
    print("removed", n, "dangling stubs")
print("".join(l for l in open(RPT) if l.startswith("** Found")))
