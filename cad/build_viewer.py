"""Build the final viewer page (index.html + beltpack.json) from the v3 viewer template."""
import json, os, struct, base64, re
here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(here, "out"); V = os.path.join(here, "viewer")
meta = json.load(open(os.path.join(OUT, "parts_final.json")))
keep = ['name', 'label', 'group', 'desc', 'explode', 'printed', 'price', 'bbox', 'volume']
trim = dict(envelope=meta['envelope'], slope=meta['slope'], oled=meta['oled'], oled_flip=True, oled_n=round(36.13 - 38.5, 3),
            parts=[{k: p[k] for k in keep} for p in meta['parts']])
# GLB -> embedded glTF JSON (the artifact host serves .json but not .glb)
b = open(os.path.join(OUT, "beltpack_final.glb"), "rb").read()
magic, ver, length = struct.unpack("<III", b[:12]); assert magic == 0x46546C67
off = 12; js = None; binb = None
while off < length:
    clen, ctype = struct.unpack("<II", b[off:off + 8]); chunk = b[off + 8: off + 8 + clen]; off += 8 + clen
    if ctype == 0x4E4F534A: js = json.loads(chunk.decode())
    elif ctype == 0x004E4942: binb = chunk
js["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(binb).decode()
json.dump(js, open(os.path.join(V, "beltpack.json"), "w"), separators=(",", ":"))

t = open(os.path.join(here, "..", "viewer", "template_fs.html")).read()
def rep(a, b_, count=1):
    global t
    assert t.count(a) == count, (t.count(a), a[:70]); t = t.replace(a, b_)
rep('<span class="eyebrow">Theatre intercom · concept v3</span>', '<span class="eyebrow">OpenTheatreComms · case rev B</span>')
rep('<span class="chip" id="dims">136 × 96 mm · 28 mm deep at the centre, 35 at the ends · knobs +13 mm</span>',
    '<span class="chip" id="dims">108 × 81 × 35 mm with TPU caps · 39 mm deep with the belt plate</span>')
rep(re.search(r'<p class="lede">.*?</p>', t, re.S).group(0),
    '''<p class="lede"><strong>Rev B: fitted to the boards as ordered, easier to print.</strong> The approved shape with the real parts inside:
        a top PCB under the keys carries the OLED and both encoders (each hangs inside its hollow dial), and a vertical main PCB
        behind the ribbed front carries the ESP32-S3, LR2021 radio, codec and every bottom connector. The 104050 battery pack
        is the back of the case and the belt plate locks it in. Try <em>See-through</em> and <em>Explode</em>; click any part
        for its part number.</p>''')
rep('''<p class="note" style="margin-top:8px">Mass assumes 4 walls and 25% infill, roughly 55% solid. Print the front shell
        face-down with supports under the slope, the back shell standing on its bottom edge, and the battery pack front
        face down. The belt clip is spring steel, not printed.</p>''',
    '''<p class="note" style="margin-top:8px">Mass assumes 4 walls and 25% infill, roughly 55% solid. PETG or ASA for the
        shells, top plate, keys, hubs, pack and belt plate; TPU 95A for the two caps and the dial tyres.</p>
      <p class="note" style="margin-top:8px"><strong>How to print.</strong> Front shell standing on its bottom face (tree supports
        under the two dial-well floors and the shelves over the dials only). Top plate face-down: flat, no supports. Back shell and
        belt plate standing on their bottom edge with a brim (they follow the hip curve). Battery pack standing on its right-hand end
        (least support: under the hooks only). Keycaps flange-down, front buttons and hubs on their flat ends, TPU dials wide end down,
        TPU caps flange-down.</p>''')
rep('''<p class="note">Concept geometry. Bought parts are envelopes from typical datasheet sizes, so check every footprint
        before PCB layout.''', '''<p class="note">Positions come from the v1 KiCad boards. A few bought-part sizes are typical figures to check on
        your parts: the EC11 body height, the XLR flange and the JST SH plugs. Cut the encoder shafts to 15 mm from the encoder
        face if they are longer. Don't fit the main PCB's J11 (JST XH): it is 7 mm tall and the front shell only clears 5.6.''')
rep("const GROUP_ORDER = ['Enclosure', 'Controls', 'Display', 'PCB', 'RF', 'Power', 'Hardware'];",
    "const GROUP_ORDER = ['Enclosure', 'Controls', 'Display', 'Electronics', 'Connectors', 'Radio', 'Power', 'Hardware'];")
rep("const GROUP_TITLE = { Enclosure: 'Enclosure', Controls: 'Controls', Display: 'Keypad and display', PCB: 'Main board', RF: 'Antenna', Power: 'Power', Hardware: 'Hardware' };",
    "const GROUP_TITLE = { Enclosure: 'Enclosure', Controls: 'Controls', Display: 'Display', Electronics: 'Boards and parts', Connectors: 'Connectors', Radio: 'Radio', Power: 'Power', Hardware: 'Hardware' };")
rep("const CASE_PARTS = new Set(['case_front', 'case_back', 'battery_pack', 'belt_clip', 'clip_screw_1', 'clip_screw_2']);",
    "const CASE_PARTS = new Set(['front_shell', 'back_shell', 'top_plate', 'tpu_top', 'tpu_bottom', 'battery_pack', 'belt_plate']);")
rep("const EDGE_PARTS = /^(case_front|case_back|battery_pack|keycap_\\d|knob_(left|right)|reply_key)$/;",
    "const EDGE_PARTS = /^(front_shell|back_shell|top_plate|battery_pack|belt_plate|keycap_\\d|knob_(left|right)|front_(back|function|menu))$/;")
rep("const METAL = /shield|xlr4_shell|xlr4_pins|_nut|_shaft|_pins|usb_c|screw|insert|magnet|springs|esp32_antenna|rf_trace|trrs_collar|belt_clip|ufl|pack_pads/;",
    "const METAL = /xlr4|usb_c|enc_|ufl|pack_pads|dock_pads|pogo|standoff|vib_motor|esp32s3/;")
rep("const INTERNAL = new Set(['esp32_shield', 'lr2021_shield', 'nau88c22', 'cell_pouch', 'antenna_flex', 'keypad_pcb']);",
    "const INTERNAL = new Set(['esp32s3', 'lr2021', 'codec', 'cell', 'antenna', 'antenna_b', 'rf_switch', 'top_pcb', 'main_pcb', 'enc_right', 'dock_pcb']);")
rep(re.search(r"const LABELS = \[.*?\];", t, re.S).group(0), """const LABELS = [
  ['xlr4', 'Headset XLR-4'], ['trrs', '3.5 mm'], ['usb_c', 'USB-C'], ['power_plunger', 'Power'], ['lamp_led', 'Flashlight'],
  ['knob_left', 'Keys 1–2 level'], ['knob_right', 'Keys 3–4 level'], ['oled_glass', 'OLED'], ['keycap_1', 'Talk 1'], ['keycap_4', 'Talk 4'],
  ['front_back', 'Back'], ['front_function', 'Function'], ['front_menu', 'Menu'],
  ['antenna', '915 MHz antenna A'], ['antenna_b', '915 MHz antenna B'], ['lr2021', 'LR2021 radio'], ['rf_switch', 'RF switch'], ['esp32s3', 'ESP32-S3'], ['codec', 'Codec'],
  ['top_pcb', 'Top PCB'], ['main_pcb', 'Main PCB'], ['enc_right', 'EC11 encoder'], ['cell', '2500 mAh cell'], ['dock_pcb', 'Dock contacts'],
  ['battery_pack', 'Battery pack'], ['belt_plate', 'Belt plate'],
];""")
rep(re.search(r"const FACE = \{.*?\};", t, re.S).group(0), """const FACE = {
  xlr4: [0, -1, 0], trrs: [0, -1, 0], usb_c: [0, -1, 0], power_plunger: [0, -1, 0], lamp_led: [0, -1, 0],
  knob_left: [0, 1, 0], knob_right: [0, 1, 0], oled_glass: SN, keycap_1: SN, keycap_4: SN,
  front_back: [0, 0, 1], front_function: [0, 0, 1], front_menu: [0, 0, 1], battery_pack: [0, 0, -1], belt_plate: [0, 0, -1],
};""")
rep("else if (/light_pipe|status_pipe|lamp_lens/.test(name))", "else if (/light_pipe|status_pipe|lamp_led/.test(name))")
rep("else if (name === 'cell_pouch')", "else if (name === 'cell')")
rep("plane.position.copy(slopePt(au, av, -2.2 + 0.03)); plane.rotation.x = -Math.asin(S.s);",
    "plane.position.copy(slopePt(au, av, META.oled_n)); plane.rotation.set(-Math.asin(S.s), 0, META.oled_flip ? Math.PI : 0);")
rep("  buildPartList(); buildPrinted(); applyExplode(0); applyCase(); setView('iso', true);",
    "  buildPartList(); buildPrinted(); applyExplode(0); applyCase(); setView('iso', true);\n  window.__bp = { nodes, byName, camera, controls, scene, updateTags, applyCase, applyExplode };")
rep("const tgt = v === 'exploded' ? new THREE.Vector3(0, 4, -66) : TARGET;", "const tgt = v === 'exploded' ? new THREE.Vector3(0, 0, -12) : TARGET;")
# the artifact host blocks fetching data: URLs, so rebuild the GLB in memory instead of letting GLTFLoader fetch its buffer
rep("new GLTFLoader().load('beltpack.json', (gltf) => {", open(os.path.join(here, "viewer_loader.js")).read().rstrip())
rep("}, undefined, (err) => { loadingEl.textContent = 'The model file did not load. Reload the page to try again.'; console.error(err); });",
    "}, (err) => { loadingEl.textContent = 'The model file did not load (' + (err && err.message || err) + '). Reload the page to try again.'; console.error(err); });")
t = t.replace('/*PARTS_JSON*/', json.dumps(trim, separators=(',', ':'), ensure_ascii=False))
open(os.path.join(V, "index.html"), "w").write(t)
print("index.html", len(t), "bytes; beltpack.json", os.path.getsize(os.path.join(V, "beltpack.json")), "bytes")
