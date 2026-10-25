# Snap footprints onto the reference-model positions.
# 1. In this project's placement_map.csv, type your schematic reference (U1, J3, SW2...) in the "ref" column
#    next to each part. Leave "rot" empty to keep the footprint's rotation, or give degrees.
# 2. In the PCB editor: Tools > Scripting Console, then run
#        exec(open(r"<path to>/place_parts.py").read())
# Positions are part centres measured from the grid origin (set to the board datum). Footprints whose anchor
# is pin 1 rather than the body centre (the PEC12R encoders, for example) need a final nudge by hand.
import csv, os, pcbnew
_board = globals().get("_bp_board") or pcbnew.GetBoard()
_src = os.path.join(os.path.dirname(_board.GetFileName()), "placement_map.csv")
_org = _board.GetDesignSettings().GetGridOrigin()
_moved, _missing = [], []
for _row in csv.DictReader(open(_src, newline="")):
    _ref = (_row.get("ref") or "").strip()
    if not _ref:
        continue
    _fp = _board.FindFootprintByReference(_ref)
    if _fp is None:
        _missing.append(_ref); continue
    _back = _row["side"].strip().upper() == "B"
    if _fp.IsFlipped() != _back:
        try:
            _fp.Flip(_fp.GetPosition(), False)
        except TypeError:
            _fp.Flip(_fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    if (_row.get("rot") or "").strip():
        _fp.SetOrientationDegrees(float(_row["rot"]))
    _fp.SetPosition(pcbnew.VECTOR2I(_org.x + pcbnew.FromMM(float(_row["x"])), _org.y - pcbnew.FromMM(float(_row["y"]))))
    _moved.append(_ref)
pcbnew.Refresh()
print("placed:", ", ".join(_moved) or "none", "| not on the board:", ", ".join(_missing) or "none")
