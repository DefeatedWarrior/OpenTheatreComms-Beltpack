import json, os, csv
here = os.path.dirname(os.path.abspath(__file__)); KD = os.path.join(here, "out", "kicad")
b = json.load(open(os.path.join(KD, "boards.json")))
rows = []
for board, frame in (("top_pcb", "X = across, Y = toward the back (origin: board centre)"), ("main_pcb", "X = across, Y = up (origin: case centre)"), ("pack_lid_pcb", "X = across, Y = up (case frame)")):
    for p in b["boards"][board]["parts"]:
        rows.append(dict(board=board, part=p["label"], side=p["side"], x=round(p["X"], 2), y=round(p["Y"], 2), w=round(p["w"], 2), h=round(p["h"], 2), height=round(p["hgt"], 2)))
    for i, (x, y, d) in enumerate(b["boards"][board]["holes"]):
        rows.append(dict(board=board, part=f"M2 hole {i+1}", side="-", x=round(x, 2), y=round(y, 2), w=d, h=d, height=0))
with open(os.path.join(KD, "placement.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for r in rows: print(r)
print(b["summary"])
