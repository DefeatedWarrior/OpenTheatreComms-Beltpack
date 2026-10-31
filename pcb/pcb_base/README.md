# Base station carrier PCB, rev 0.1

The OpenTheatreComms base station: a carrier for the Waveshare ESP32-P4-NANO with the beltpack's LR2021 radio, a DC input,
and the front-panel controls. It has no audio of its own: the operator's headset is a beltpack plugged into the NANO's
USB-C (or USB-A) port, which the base runs as its local station. The NANO brings Ethernet (for AES67), USB and an optional PoE
module; the carrier brings everything else.

![Preview](fab/base_pcb_preview.png)

| | |
|---|---|
| Size | 150 x 90 mm, 1.6 mm FR4, 4 layers, four M3 corner holes |
| Stack | F parts + signals + GND pour, In1 solid GND (under the RF lines), In2 signals + 3.3 V pour, B signals + GND pour |
| Parts | All on the top side (JLC Economic assembly, top). Hand-fit: NANO sockets, DC jack, SMAs, LR2021, keys, dial, OLED socket, wire pads |
| DRC | 0 errors, 0 unconnected. 32 warnings, all cosmetic: silkscreen clipped by pad openings, a few overlapping labels, and three library-mismatch notes for the edited footprints |

## What plugs in where

| Rear edge (left to right) | Front area (left to right) |
|---|---|
| NANO: RJ45 (PoE with Waveshare's module) and USB-A | OLED module (1.3 in, 128x64, I2C SH1106) on a 4-pin socket |
| DC jack, 7-24 V, 5.5 x 2.1 mm, centre + | Menu and Back keys, menu dial (EC11 with push) |
| | Four talk keys (12 mm), each with an RGB channel light |
| SMA antenna B, SMA antenna A (915 MHz), Molex 73251-2120 edge jacks | Row of eight RGB beltpack lights |

The NANO's USB-C points toward the front, under the case lid. It's both the flashing port and where the operator's
beltpack plugs in, so the case needs an opening there (or a short USB-C extension to the front panel).

Lights: twelve WS2812B-Mini-V3J (3.5 x 3.5 mm, JLC-assembled) on one 5 V data chain from GPIO32 through the 74AHCT1G125 shifter: channel lights 1-4 first, then pack lights 1-8.

## Power

Any of three sources powers the station, and they can be connected together:

1. **NANO USB-C** (5 V): through the NANO's own reverse-blocking switch.
2. **PoE** (802.3af): Waveshare's PoE module plugs onto the NANO's PoE header and feeds its 5 V rail.
3. **DC jack** (7-24 V): SS34 reverse protection, SMAJ26A clamp, AP63205 5 V 2 A buck, then SS34 D2 onto the NANO's 5 V rail.

The carrier takes its 5 V from that rail (header pins L2, L4, R1) and makes its own 3.3 V with a TLV75733 (radio,
expander, OLED). The NANO's own 3.3 V is left to the NANO.

## NANO pin map

| GPIO | Header pin | Use | GPIO | Header pin | Use |
|---|---|---|---|---|---|
| 7 / 8 | L3 / L5 | I2C SDA / SCL (shared with the NANO's ES8311 at 0x18) | 20 / 21 / 22 / 23 | L13 / L15 / L16 / L7 | LR2021 NSS / SCK / MOSI / MISO |
| 5 | L11 | LR2021 BUSY | 4 | L12 | LR2021 DIO6 (IRQ) |
| 3 | R9 | LR2021 NRESET | 2 | R11 | Antenna switch (high = A) |
| 33 / 46 / 47 / 48 / 6 | L24 / R17 / R15 / R16 / R12 | Free (were the codec's I2S) | 24 / 25 | L18 / L19 | Dial A / B |
| 26 | L21 | Expander interrupt | 32 | L23 | RGB light data (via a 5 V level shifter) |
| 27 | L22 | Spare (test pad TP1) | | | |

Left unconnected because the NANO uses them: GPIO 0/1 (32 kHz crystal option), 37/38 (UART0, the USB-C serial port),
36 (strapping), 45 (SD power), 53 (its speaker amplifier), 54 and the C6 lines (its Wi-Fi chip).

I2C addresses: NANO's ES8311 0x18, TCA9555 expander 0x21, OLED 0x3C.
Expander: P00-P03 talk keys 1-4, P04 Menu, P05 Back, P06 dial push, P07 free, P10 LR2021 DIO5, P11 LR2021 TX/RX enable.

## Radio

Same circuit as the beltpack: LR2021 module, pi match (C12, L2, C13: 0 ohm and two unfitted shunts until tuned), DC block,
PE4259 switch (GPIO2 high = antenna A), DC blocks, two edge SMA jacks. The RF lines are 0.35 mm on the top layer over the
In1 ground (about 50 ohm on JLC's 7628 stack). The 2.4 GHz port has a footprint-only match and U.FL (J4).

Radio capacity, for the firmware: eight beltpack uplinks plus four channel mixes downlink at Opus 24 kbps is about
300 kbps of audio, well inside the LR2021's 915 MHz FLRC rates, so one radio covers 8 packs on 4 channels with TDMA.

## Check before ordering

1. **NANO sockets.** Positions are from Waveshare's own drawing (DXF, 2026-03-31). Plug a NANO into two loose sockets on
   a printout of `fab/base_pcb_print_1to1.pdf` at 100 % on A4, or check a header against the drawing, before ordering.
2. **OLED pin order.** The socket is GND, VCC, SCL, SDA, the most common order for 1.3 in I2C modules, but some modules
   swap GND and VCC. Check yours.
3. **PoE module height.** It sits on top of the NANO, whose board is about 12.6 mm above the carrier (8.5 mm socket,
   2.5 mm header, 1.6 mm board). Measure the module on your NANO before designing the case lid.
4. **Wi-Fi.** The NANO's Wi-Fi antenna (on its C6 module) sits 11 mm above the carrier's ground pour, which detunes it a
   little. The station uses Ethernet, so this only matters if you use Wi-Fi for setup.
5. **RF.** Tune C12, L2, C13 with a VNA, as on the beltpack.

## Rebuilding

Generated from `pcb_base/design.py`: `python3 customlib.py`, `python3 make_sch.py`, `kicad-cli sch export netlist -o
out/base_pcb.net out/base_pcb.kicad_sch`, `python3 chknet.py out/base_pcb.net`, `python3 make_pcb.py`, `python3 finish_pcb.py`,
`python3 dangle.py` (removes the few track stubs the tidy pass leaves), `python3 make_fab.py`.
