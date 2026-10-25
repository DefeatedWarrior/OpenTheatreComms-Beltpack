"""STEP of everything that is not a PCB or a PCB-mounted part, for KiCad's 3D viewer."""
import os, json
import cadquery as cq
from cadquery import Shape, Color
here = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(here, "out")
info = json.load(open(os.path.join(OUT, "parts_final.json")))
COLS = {}
EXCL = ("top_pcb", "main_pcb", "pack_lid_pcb", "pack_pads", "sw_", "led_", "oled_zif", "jst_", "io_exp", "enc_", "usb_c", "trrs",
        "lamp_led", "vib_motor", "esp32s3", "lr2021", "ufl", "codec", "charger", "ldo", "pogo_")
import importlib.util, sys
rgb = {"front_shell": (0.19, 0.21, 0.24), "back_shell": (0.19, 0.21, 0.24), "top_plate": (0.19, 0.21, 0.24), "tpu_top": (0.93, 0.68, 0.10),
       "tpu_bottom": (0.93, 0.68, 0.10), "belt_plate": (0.13, 0.14, 0.16), "battery_pack": (0.24, 0.26, 0.29), "cell": (0.16, 0.32, 0.62),
       "xlr4": (0.78, 0.79, 0.81), "antenna": (0.80, 0.50, 0.15), "oled_glass": (0.04, 0.05, 0.07)}
assy = cq.Assembly(name="enclosure_ref"); n = 0
for p in info["parts"]:
    nm = p["name"]
    if nm.startswith(EXCL): continue
    s = Shape.importBrep(os.path.join(OUT, "brep", nm + ".brep"))
    c = rgb.get(nm) or ((0.12, 0.12, 0.13) if nm.startswith("knob") else (0.33, 0.36, 0.40) if nm.startswith(("keycap", "front_", "power")) else (0.5, 0.52, 0.55))
    assy.add(s, name=nm, color=Color(*c, 1.0)); n += 1
fn = os.path.join(here, "..", "kicad", "3d", "enclosure_ref.step")
assy.export(fn)
print(n, "parts ->", fn, os.path.getsize(fn) // 1024, "kB")
