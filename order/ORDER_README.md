# OpenTheatreComms v1 order (hand assembly)

This order covers **2 beltpacks + 1 base station**. The 4-slot charging dock comes later, as a separate order.

**Buy lists in this folder:**

- `JLC_boards.csv`: the five boards and the settings to pick for each.
- `LCSC_cart_upload.csv`: upload to LCSC's BOM tool. `LCSC_cart_hand_parts.csv` is the same cart with what each line is for.
- `Other_suppliers.csv`: everything else, grouped by shop, with rough prices.

- **JLC:** makes the boards and the solder-paste stencils. It assembles nothing.
- **You:** fit every part, from one LCSC cart plus a few other suppliers.
- **Base station:** no audio section. The operator's headset is a beltpack plugged into the base by USB-C.
- **Prices:** Australian dollars, from JLC's and LCSC's own listings on 31 Oct 2026, converted at 1 USD = 1.43 AUD. JLC,
  LCSC and Elecrow charge in USD, so your card's exchange fee comes on top.

## 1. JLCPCB: boards and stencils (one cart)

| Folder | Board settings | Stencil (in the same PCB order) |
|---|---|---|
| `Beltpack main` | 4 layers, 1.6 mm, JLC04161H-7628 stack, **HASL lead-free**, qty 5 | **Top and bottom**, as two small stencils (100 x 100 mm option) |
| `Beltpack top` | 2 layers, 1.6 mm, **HASL lead-free**, qty 5 | **Top and bottom**, as two small stencils, or one sheet if JLC accepts both sides in 100 x 100 mm |
| `Base station` | 4 layers, 1.6 mm, JLC04161H-7628 stack, **HASL lead-free**, qty 5 | **Top only**, standard frameless stencil (the board is too big for the small option) |
| `Beltpack pack lid` | 2 layers, **0.8 mm**, **ENIG**, qty 5 (its pads are spring contacts: gold stays clean) | none |
| `Beltpack dock contacts` | 2 layers, **0.8 mm**, **ENIG**, qty 5 (dock spring pins land on its pads) | none (one SMD socket, iron it) |

- **Stack:** the 4-layer boards need the 7628 stack because the RF lines were sized for it.
- **Vias:** the beltpack main board has 27 vias with 0.2 mm holes, JLC's 4-layer minimum. If the quote shows a small-hole
  fee, that's why.
- **Finish:** HASL lead-free on the main, top and base boards. Reflow melts the HASL into each joint and pulls the parts flat.
  The main board's finest parts (the LGA accelerometer, the 0.4 mm QFN codec and the TDFN fuel gauge) get a slightly less even
  paste print on HASL than on ENIG. Use plenty of flux and inspect them closely. The pack lid stays ENIG because its pads are
  bare spring contacts.

Upload each `*_gerbers.zip` and set the options above. Each zip carries both sides' paste layers, with paste on every SMD
pad, unfitted ones included. Don't turn on PCB Assembly.

**Stencil costs:** small stencils are US$3 each, and the base station's standard stencil is about US$7. That's about A$27
in all.

**Not needed any more:** the MAX17048 pre-order, the JLC rotation preview and the extended-part fees. All of those went
with JLC's assembly.

## 2. LCSC: every part

Upload `LCSC_cart_upload.csv` to LCSC's BOM tool (two columns: LCSC part number, quantity), or use
`LCSC_cart_hand_parts.csv` to see what each line is for. Place it from JLC's parts manager, or tick "ship with JLCPCB
order", so it travels in the same box as the boards.

- **Size and cost:** 75 lines, **about A$135**, including the base antennas. Everything ships from stock.
- **Quantities and spares:** already rounded up to LCSC's minimum and multiple. Small parts include spares: +20% or at
  least 2 for passives, +1 for other parts under US$1. The accelerometer, fuel gauge and codec get one spare each,
  because they're the easiest to ruin.
- **Cheaper beltpack parts:** Xinyangze YZ08415060P-02 spring pins (C7471674, about A$0.66 each, instead of Mill-Max at
  about A$4) in the main board's now 1.0 mm holes; Alps EC11N1520402 encoders (C470704, about A$1.90, instead of Bourns
  PEC12R at about A$5) on the same footprint; and a JST XH 2-pin battery socket (J11, C158012). The case redesign should put
  the pack pads 4.0 mm from the main board's back face (the pins' working height) and check the EC11 shaft length.
- **Antenna switch:** **ZHHXDZ HX4259-63-ST** (C48031087) instead of pSemi's PE4259. LCSC has no PE4259, and JLC's
  stock can't be bought for hand assembly. The datasheet shows identical pins (RF1, GND, RF2, CTRL, RFC, VDD) and logic
  (CTRL high = RF1 = antenna A), in the same SC-70-6 package.
- **Base SMA jacks:** MyAntenna A-SMA-KE-13.5A (C22467594), which fits the Molex footprint.
- **Base antennas:** BAT WIRELESS BW915JWX105-10KJ, 915 MHz whips (C496579).

Four more swaps, because LCSC doesn't stock the original part:

| Original | LCSC part | What it is |
|---|---|---|
| C14663 | C1591 | 100n X7R |
| C57112 | C1589 | 10n X7R |
| C1002 | C19330 | Murata BLM18AG601 600R bead |
| GCT USB4105 | C165948 | HRO TYPE-C-31-M-12, same land pattern |

Each board folder has a `*_hand_fit.csv` listing every part on that board, and which side it goes on.

## 3. Other suppliers

| Part | Qty | Where |
|---|---|---|
| LR2021 LoRa module | 3 | Elecrow, US$6.90 each |
| Waveshare ESP32-P4-NANO (SKU 29026) | 1 | **Waveshare direct**, from about US$19. Core Electronics has it for A$61 if you need it sooner |
| Waveshare PoE module for the NANO (optional) | 1 | Waveshare, in the same order |
| 915 MHz U.FL flex antenna (FPC, 15 x 65 mm, 200 mm lead), beltpacks | 4 | Core Electronics CE09458, A$2.30 each. Check 65 mm fits the pack ends before buying |
| 8 mm coin vibration motor, 3 V | 2 | Core Electronics (same order as the antennas), AliExpress |
| 1.3 in 128x64 I2C OLED module (SH1106), base | 1 | AliExpress. Check its pin order is GND, VCC, SCL, SDA |
| Beltpack Li-ion cells with a JST XH 2-pin plug | 2 | Your choice. Check the plug polarity: J11 pin 1 is + |
| 1.3 in 128x64 OLED panel, SH1106, 30-pin 0.7 mm solder tail (beltpack top) | 3 (one spare) | AliExpress item 1005006789720033, colour "sh1106 white", A$1.79 each |
| JST SH 4-pin cable, 1.0 mm pitch, 40–60 mm, beltpack J12 to the dock contact board, wired pin 1 to pin 1 (check with a meter: they come straight and reversed) | 2 | AliExpress (packs of 10, about A$3) |
| **REAN** XLR-4 panel connector (headset), beltpacks | 2 | Jaycar, element14 AU (about A$8) |
| Beltpack cells | per the enclosure | |

## 4. Assembly

**Supplies:**

- Solder paste: Sn63/Pb37 or SAC for first sides, and low-temperature SnBi (138 °C) for second sides.
- A plastic card and Kapton tape.
- A hot plate.
- Hot air.
- Flux, solder wick, fine tweezers and magnification.

**Holding the board flat.** You get 5 of each board and use 2. Tape the spares around the board you're pasting so the
stencil lies flat. Use them as standoffs when the other side already has parts on it.

**Order of work** (about 10–12 hours in all):

1. **Base station, about 2 hours.** Start here because it's single-sided and the easiest.
   - Paste the top side and place the SMD parts: the buck circuit, LDO, TCA9555, buffer and the 12 WS2812B-Mini lights.
   - Reflow on the hot plate. Keep it short: the lights are heat-sensitive.
   - Then fit the LR2021 module, SMAs, sockets, switches, encoder and DC jack.
2. **Beltpack top, about 1–1.25 hours each.**
   - Paste and place the top side (resistors, LEDs, PTS815 buttons) and reflow on the hot plate.
   - Flip the board onto spare boards, paste the bottom with low-temp paste, place the parts (TCA9555,
     link connector, caps) and reflow with hot air.
   - Hand-solder the encoders. Clip off each EC11N's two dummy pins first (the unused switch positions, 7 mm past the
     mounting tabs): the footprint has no holes for them.
   - **OLED last, by iron.** The pads have no paste and must stay off the hot plate: the panel can't take reflow heat.
     Tin the 30 pads on the bottom side (labelled 1 and 30), lay the panel face up on the top side, wrap its tail
     round the notch in the back edge, line up the tail's two alignment marks with the circles on the silkscreen, then
     drag-solder with plenty of flux. Check for bridges with a meter: pins 18 to 20 are I2C, the rest are mostly ground.
3. **Beltpack main, about 3–3.5 hours each.**
   - **Bottom side first, on the hot plate.** Paste and place the accelerometer, codec, fuel gauge, antenna switch,
     TCA9555, the regulators and their passives, the U.FLs, the vertical dock socket J12 (bottom edge) and its diode D12,
     and the ESP32 module.
     Reflow flat on the hot plate. The
     fine-pitch parts come out best on a flat first-side reflow.
   - Check the LGA and QFN under magnification. The LIS3DH has no visible joints: if the board misbehaves later, it's the
     first suspect, and you have a spare.
   - Fit the LR2021 module with an iron or hot air. It's castellated.
   - **Top side second.** Rest the board on spare boards, paste with low-temp paste, place the 55 parts (USB-C, jack,
     buttons, LEDs, passives) and reflow with hot air, one area at a time.
   - Then the through-hole parts: the spring pins (from the back, flange flat on the pad), the JST XH battery socket J11 on
     the front, and the motor leads.
4. **Dock contacts, 5 minutes each.** Iron the side-entry JST SH socket onto the inside face (no paste needed for one
   part). Check the cable with a meter before fitting: J12 pin 1 (VBUS) must reach the contact board socket's pin 1.

**Tips:** Check every fine-pitch part under magnification. Fix bridges with flux and wick. Clean off the flux and check
the 3.3 V rail for shorts before powering up.

## 5. Before you press order

I've checked every Gerber zip: the outlines, layer counts, drills and paste layers are right on all five boards, and DRC
shows no errors. These checks are yours, because they depend on parts in your hands:

1. **Base station NANO sockets.** Print `base_pcb_print_1to1.pdf` from the base station fab folder (`Board files/kicad_proj/base_pcb/fab`) at 100 % scale on A4. Push two loose
   sockets into a NANO and check they land on the hole marks.
2. **Base station OLED pin order** on the module you buy (see section 3).
3. **Beltpack top OLED panel:** when it arrives, check its pin 1 is on the left with the panel face up and the tail toward you,
   as on the listing's drawing.
4. **Battery plug polarity:** J11 pin 1 is +. Check your cells' plugs with a meter.
5. **Schematic values:** a read-through of each schematic PDF, especially the charger's NTC and R5.
6. **Gerbers in JLC's viewer** when you upload: one last look at each board.

The case comes after the boards, so the fit is unchecked: the spring-pin height, the flex antenna length, the dock cable
path and the encoder shafts.

## Rough total

| Where | What | Approx. A$ |
|---|---|---|
| JLCPCB | 5 board types (5 of each; ENIG on the pack lid and dock contacts), 5 stencils, shipping | 150 |
| LCSC | every part and the base antennas, shipped with the JLC boards | 140 |
| Elecrow | 3 LR2021 modules, shipping | 47 |
| Waveshare | ESP32-P4-NANO, shipping | 40 |
| Core Electronics | 4 flex antennas, 2 coin motors, shipping | 25 |
| AliExpress | 1.3 in OLED module and 2 beltpack OLED panels | 25 |
| REAN XLRs | 2 headset connectors for the packs | 16 |
| **Total** | | **about A$440** |

Not included: paste and tools, beltpack cells, enclosures and the optional PoE module (about A$15). The JLC line is an
estimate until you see JLC's quote.
