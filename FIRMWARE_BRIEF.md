# OpenTheatreComms firmware brief

You're writing the software for OpenTheatreComms, a DIY full-duplex wireless theatre intercom (think Clear-Com FreeSpeak or
Hollyland Solidcom, but open and cheap). It has three parts: **beltpacks** (ESP32-S3), **base stations** (ESP32-P4) and a
**mixer server** (a Linux PC). Custom PCBs for 2 beltpacks and 1 base are on order. I'm in Australia.

## Where to work

- This folder is the whole project. **Write only inside `Firmware/`** (create it). Treat everything else as read-only
  reference: never edit, move or delete files outside `Firmware/`.
- Run `git init` in `Firmware/` and commit in small, working steps with clear messages.
- Reference material in this folder:
  - `Board files/kicad_proj/<board>/README.md`: what each board does, **GPIO and expander pin maps, I2C addresses, power
    and audio wiring**. `fab/<board>_schematic.pdf` and `fab/<board>_bom.csv` are the full schematic and parts list.
    Boards: `main_pcb` (beltpack main), `top_pcb` (beltpack top: keys, OLED, lights, dials), `base_pcb` (base station
    carrier), `pack_lid_pcb` and `dock_contact_pcb` (contacts only, no firmware).
  - `Datasheets/`: NAU88C22 codec, LR2021 module, ESP32-P4-NANO schematic and drawings. Fetch any other datasheet you need
    (LR2021/LR20xx chip, LP5024, TCA9555, MAX17048, LIS3DH, SH1106, TP4056) from the manufacturer.
  - `JLC order/`: what was actually bought.
- **The board READMEs and schematics are the source of truth.** Where this brief and a README disagree, the README wins:
  tell me, and note it in `Firmware/docs/DECISIONS.md`.

## What to build, and in what order

Lay `Firmware/` out like this (adjust if you have a good reason, and say why):

```
Firmware/
  common/      protocol definitions shared by everything (packet formats, IDs, constants) + tests
  bringup/     board test apps: beltpack_test (ESP32-S3), base_test (ESP32-P4)
  beltpack/    ESP-IDF project, ESP32-S3
  base/        ESP-IDF project, ESP32-P4
  server/      Go mixer server + web UI
  tools/       flashing, log capture, simulators
  docs/        ARCHITECTURE.md, DECISIONS.md, BRINGUP.md, OPERATING.md, PROTOCOL.md
```

Work on two tracks at once:

1. **Bring-up test firmware (needed first, the boards arrive soon).** One app per board with a serial menu over USB that
   tests each part on its own, prints PASS/FAIL with the measured values, and has an "all tests" mode. It should be useful
   for finding assembly faults (solder bridges, dead chips, swapped wires), so print what was expected next to what was read.
   - Beltpack:
     - I2C scan: expect 0x18, 0x1A, 0x20, 0x21, 0x28, 0x36, 0x3D.
     - Both expanders' inputs live.
     - Each key, button and dial, with a live readout.
     - The LP5024 stepping each of the six RGB LEDs through red, green and blue.
     - OLED test pattern.
     - Codec: ID read, then a mic-to-earpiece loopback for the XLR headset and the 3.5 mm one, plus a 1 kHz tone out.
     - Jack sense, vibration motor, flashlight.
     - Battery gauge voltage and charge state, charger pins, USB present, accelerometer.
     - LR2021: chip ID, a CW tone at 915 MHz for a range check, and a ping test between two boards that reports RSSI, SNR
       and packet loss.
     - Antenna switch A/B with RSSI each way.
     - Soft power hold and off.
   - Base:
     - I2C scan.
     - Keys, Menu, Back, dial and its push.
     - All 12 WS2812 lights.
     - OLED.
     - LR2021 radio 1: ID, ping with a beltpack, antenna switch.
     - Ethernet link and DHCP.
     - USB host enumerating a beltpack.
   - Write `docs/BRINGUP.md`: how to flash each board, what each test should show, and what a failure usually means.
2. **The real system**, following the build milestones below.

## System design (summary of the architecture doc; keep `docs/ARCHITECTURE.md` as the living copy)

- **Radio:** Semtech LR2021 (Elecrow module) on **915–928 MHz** using **FLRC** at about 0.975 Mb/s. 2.4 GHz is a later
  fallback; its antenna isn't fitted in v1. Australian LIPD class licence: up to 1 W EIRP. Default to a modest TX power,
  set from config, and keep 917–928 MHz as the default band (phones sit just below 915).
- **TDMA:** every cell runs a **20 ms frame** and hops channel every frame: beacon → join slot → uplink slots (one per
  pack) → mix gap → downlink slots (one per pack). Each uplink carries an ~8-byte header (pack ID, sequence, 4-bit key mask,
  call flag, battery, link quality, control flag) plus one Opus frame. Each downlink carries that pack's personal mix.
  No audio retransmission. Control messages (config, key profiles, levels) ride the control flag and are acknowledged
  and retried.
- **Audio:** 16 kHz mono, 20 ms blocks (320 samples), **Opus** (VoIP mode, ~24 kb/s, in-band FEC). Packet-loss
  concealment, a 1–2 frame jitter buffer, sidetone under 5 ms (local) with an adjustable level, and drift correction by
  inserting or dropping samples. Target mouth-to-ear latency: ~50–60 ms.
- **Beltpack:**
  - **Tasks:** core 0 runs only the radio, driven by a hardware timer. Core 1 runs audio, control, UI and power.
  - **Memory:** no heap allocation during a show; tasks talk through fixed queues.
  - **Keys:** four talk keys, each latching, momentary, or auto (tap latches, hold is momentary). The key mask is resent
    every frame, so a lost packet can't leave a talk stuck open.
  - **Dials:** the left dial sets the listen levels for keys 1–2, the right dial for keys 3–4.
  - **Buttons:** Back, Function (default Reply) and Menu.
  - **OLED:** key labels, levels, battery, link state, caller.
  - **Link states:** boot → scan → join → connected → handover → lost → scan. When lost, show "No link" and play
    silence or a soft tone.
- **Base station:** a radio-to-Ethernet bridge with the frame clock locked by **PTP**, using the ESP32-P4 Ethernet
  hardware timestamps. All bases transmit together and receive together.
  - **Radios:** two radios on one frequency give diversity (keep the best CRC/RSSI copy), and spare radios listen to
    neighbouring cells. Only radio 1 is fitted in v1, but support up to 3 as the board allows.
  - **Roaming:** make-before-break handover between bases.
  - **No server:** if the server goes quiet in networked mode, keep beaconing and show "No server" on the packs.
- **Mixer server (Go, Linux):**
  - **Per frame:** decodes every uplink, mixes each listener's mix-minus (their own voice removed) with per-channel listen
    levels, encodes, and sends to the right base.
  - **Configuration:** owns channel assignments, key profiles (per pack or per role, changeable live, pushed to packs and
    saved in their NVS), names, slot tables and handover decisions.
  - **Redundancy:** main and hot-standby servers both mix; a base switches to the standby's mix within a frame if the main's
    is missing.
  - **Logging:** packet loss and dropouts per pack, for walk tests.

## Decisions I've made

- **Scope:** all three: beltpack firmware, base firmware and the server.
- **Standalone base mode (no PC):** a base must be able to run a small show by itself, mixing on the ESP32-P4 for as many
  packs as it can handle (measure it; I'm guessing 6–10).
  - It hosts the web setup page itself.
  - When a server is on the network, the base becomes a relay and the server takes over. Make that handover clean and
    obvious on the OLED.
  - Packs must behave identically in both modes.
- **Operator station on the base:** the base has no audio of its own. The operator's headset is a beltpack plugged into the
  base's USB, and the base runs it as a local station: same audio and keys, carried over USB instead of radio.
  - Check the ESP32-P4-NANO schematic for which port can be USB host (the board has USB-C and USB-A).
  - The base's four talk keys and lights act as that operator's talk keys.
  - Its eight pack lights show packs 1–8: online, talking, call, low battery.
- **Extras for v1:**
  - **Firmware updates** over USB (plug in, or through the dock contacts, which share the ESP32-S3's native USB) and over
    Wi-Fi in a maintenance mode (boot with a button held; Wi-Fi stays off otherwise).
  - **Program feed and Dante/AES67** on the server: program feed as a listen-only channel (AES67 or a USB audio interface);
    AES67 via PipeWire or aes67-linux-daemon on a second network port; keep the intercom's PTP clock separate from the house
    network.
  - **Calls:** a double-tap on a key calls whoever that key talks to. The receiving pack flashes that key's light, buzzes the
    vibration motor and shows the caller on the OLED. Function = Reply to the last caller by default.
  - **Web setup page** (served by the server, or by the base in standalone mode): name packs, set up channels and key
    profiles, live talk lights and meters, battery and signal per pack, firmware updates.
- **Security:** a shared network key so strangers can't join; AES audio later (the ESP32-S3 has hardware AES).
- **Pairing:** a pack learns the network (ID, key, band) over USB or the dock. Joining over the air is allowed only for
  packs that already have the key.

## Beltpack hardware notes (verify against the README and schematic)

- **ESP32-S3-WROOM-1-N8R8:**
  - Native USB on IO19/20, which also reach the dock contacts.
  - **Soft power:** the side button enables the LDO; firmware must drive **PWR_HOLD (IO17)** high early in boot or the pack
    turns off when the button is released. Releasing PWR_HOLD switches it off. The button also reads on expander P03.
  - Full GPIO, expander and I2C maps are in `main_pcb/README.md`.
- **I2C:** codec NAU88C22 0x1A, LIS3DH 0x18, MAX17048 0x36, main TCA9555 0x21, top TCA9555 0x20, **SH1106 OLED 0x3D**,
  **LP5024 0x28**. The LP5024 also answers its broadcast address 0x3C, which is why the OLED is at 0x3D. Never put anything
  else on 0x3C.
- **Top board:**
  - **Keys:** talk keys 1–4 on top expander P00–P03.
  - **OLED reset:** OLED_RES_N on P04.
  - **LP5024 EN:** on P05, held high by the expander's pull-up at power-up; firmware must still set Chip_EN over I2C.
  - **Lights:** six RGB LEDs on the LP5024: talk keys 1–4 and the left/right status lights. The channel map is in
    `top_pcb/README.md`. Full scale is 4.9 mA per colour, so use the 8-bit brightness and colour registers freely.
  - **OLED:** 1.3 in 128×64 SH1106 (132-column RAM, usually a 2-column offset). Address 0x3D.
  - **Dials:** both on the main board's GPIOs (left IO38/39, right IO40/41), no push switch. The shared expander interrupt
    is IO16.
- **Radio:** LR2021 on SPI (IO10–13), BUSY IO14, DIO6 IRQ IO21, NRESET IO47, antenna switch IO48 (high = antenna A).
  DIO5 and TX/RX enable are on expander P11/P12, so changing them costs an I2C transaction: schedule those changes so they
  never cost a slot, or tell me if a hardware change is needed.
  - Use Semtech's LR20xx driver if it suits, and read the Elecrow module spec in `Datasheets/` for its RF switch and TCXO
    control.
  - **Antenna diversity:** listen on alternate antennas per beacon and use the stronger one for each frame.
- **Audio (NAU88C22, I2S on IO4–7, MCLK IO15):**
  - **XLR-4 headset (dynamic mic):** mic into the codec's left mic input; earpiece on the bridged speaker outputs.
  - **3.5 mm TRRS headset (CTIA, electret):** mic into the right mic input with bias on; earpiece on the headphone outputs.
  - **Jack sense:** IO1 picks between them (check the polarity on the schematic).
- **Other:**
  - Vibration motor IO18, flashlight IO42.
  - Charger state on main expander P04/P05, USB present on P06, gauge alert on P10, accelerometer interrupts on P07/P13.
  - The battery is one Li-ion cell with a gauge: show percentage, warn when low, and switch off cleanly before cutoff.
  - The power button is under the bottom face: a tap toggles the flashlight, a long press switches off.

## Base hardware notes (verify against `base_pcb/README.md`)

- **Board:** a Waveshare ESP32-P4-NANO on the carrier. Ethernet, optional PoE, USB-C and USB-A are on the NANO.
- **Pins and I2C:** pin map, expander map (TCA9555 0x21: keys, Menu, Back, dial push, antenna switch, radio control lines)
  and I2C (OLED module 0x3C, the NANO's ES8311 at 0x18 is unused) are in the README.
- **Radios:** radio 1 is fitted. Radios 2 and 3 share its SPI bus and are unfitted footprints in v1.
- **Lights:** 12 WS2812B-Mini on one data line (GPIO32): talk keys 1–4 first, then pack lights 1–8.

## Milestones (each one proves a risky piece before the next)

1. **Audio loop on a beltpack:** mic → Opus → decode → earpiece with sidetone, on both headset types. Measure CPU load.
2. **Radio link between two boards:** FLRC one way, then both ways in fixed slots, then hopping. Measure loss, air time
   per slot and TX/RX turnaround (the LR2021 is new, so measure rather than trust estimates).
3. **One base, two packs, one channel, in standalone mode:** full duplex end to end. Measure latency.
4. **Channels and controls:** four keys with profiles from the web page, four listen channels, OLED labels, calls,
   reply, levels.
5. **The PC server mode:** the same show through the server, base as relay, plus the program feed.
6. **Power and product polish:** battery, charging, auto power-off, maintenance-mode OTA, USB update, NVS settings,
   pairing.
7. **Capacity:** as many packs per cell as the slot budget allows (target 10–12); measure the standalone mixing limit.
8. **Second base and handover** (later, when I build one): PTP sync measured on a scope, roaming, make-before-break.
9. **Redundancy and AES67:** standby server takeover with no audible gap, and Dante/AES67 bridging.

Until the boards are here, develop on what you can run:
- Host unit tests for protocol, mixing, jitter buffer and key logic.
- A PC simulator of packs and bases talking to the server over UDP.
- ESP-IDF builds that compile cleanly.

I'll flash the boards and send you logs. Make the logs useful for that: timestamps, per-frame stats on demand, and clear
error messages.

## Engineering rules

- **ESP-IDF:** use a current stable release that supports the ESP32-P4, and pin the version in each project.
- **Opus:** use a maintained Opus component for ESP-IDF (Espressif's, or libopus built as a component).
- **Timing:** reliability on show night comes first. Radio timing must never be starved by anything else.
- **Faults:** a fault in one part (OLED, gauge, accelerometer) must never stop audio.
- **Config:** settings live in NVS, and all thresholds (handover margins, TX power, levels) are adjustable, not hard-coded.
- **Docs:** keep `docs/` current as you go; `docs/OPERATING.md` should explain how to run a show.
- **Ask first:** ask me before anything that changes the hardware, the radio band or power limits, or the user-facing
  behaviour above. Otherwise make sensible calls and record them in `docs/DECISIONS.md`.
- **Plan first:** start by reading the board READMEs and schematics, then send me a short plan for the bring-up apps and the
  first two milestones, with any questions, before writing much code.
