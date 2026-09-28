[← README](../README.md) · [BLE Protocol](ble-protocol.md) · [Firmware Architecture](firmware-architecture.md) · [Methodology](methodology.md) · **Hardware Setup** · [Open Questions](open-questions.md)

# Hardware Setup Guide

Step-by-step instructions for the hardware in [Methodology's shopping
list](methodology.md#hardware-tooling) — written for a hobbyist with basic soldering experience,
not an embedded-tools background. If you've never used a logic analyzer or a debug probe before,
this is written for you.

**Read this whole page before touching a real device.** The device-facing steps near the end are
genuinely riskier than the ones at the top — do the logic analyzer first, since it can't damage
anything, and don't attempt any device connection until you've read the [Safety](#safety-read-this-first)
section.

## What each tool is for

Quick recap from Methodology, in plain terms:

- **Logic analyzer** — a passive "listening" device. Clip it onto wires on the board and it
  records the digital signals going past, on your computer screen. Cannot damage anything; it
  never sends a signal, only reads.
- **SWD probe (ST-Link V2 from the kit)** — for talking to the **Nuvoton M031**, the second chip
  on the board, over its standard Arm debug port.
- **A USB-serial adapter (CH340 or CP2102) + free software** — for talking to the **TLSR8258**,
  the main chip, over its own different debug protocol (SWire). This is your recovery tool if a
  firmware experiment on that chip ever goes wrong.

## Safety, read this first

- **Static electricity can kill chips.** Before touching the board's internals, touch a grounded
  metal object (a laptop's metal chassis while it's plugged in, a radiator, anything grounded) to
  discharge yourself. Anti-static wrist straps are cheap if you want to be extra careful.
- **Power the board from USB only while probing**, not from its internal battery at the same time
  as a USB-powered tool, to avoid ground-loop or back-powering issues between the device and your
  computer.
- **Do the logic analyzer work first.** It's non-destructive by nature — a good way to get
  comfortable opening the device and finding chips before doing anything that could go wrong.
- **Don't attempt a real firmware upload without the recovery tooling already working.** See
  [Open Questions](open-questions.md) for why a bad transfer is a real, not theoretical, risk.

## Part 1: Logic analyzer

1. **Install [PulseView](https://sigrok.org/wiki/Downloads)** (free, open source, Windows/Mac/Linux
   — this is the software side of the "sigrok" project, and it's what almost every cheap 8-channel
   analyzer like this one is designed to work with).
2. Plug the analyzer into a USB port. No driver install should be needed on modern Windows/Mac/
   Linux; if PulseView doesn't see the device, check its own docs for your specific OS — driver
   quirks on cheap clones are the most common first snag.
3. **Open the device with test hook clips**, and identify the board's chips visually against the
   photos in [Firmware Architecture § Board hardware](firmware-architecture.md#board-hardware) —
   confirm you're looking at the same layout before clipping anything.
4. **Clip GND first**, to a known ground point (a battery negative terminal, or a chip's
   confirmed GND pin) — every other clip's reading is relative to this one, and lead order matters
   less for safety than making sure this connection is solid.
5. In PulseView: select your device, set the **sample rate to the analyzer's max (24MHz)**, hit
   **Run**. You'll see raw digital traces — square waves — on each channel you clipped.
6. **Add a protocol decoder** if you know what bus you're looking at: PulseView's decoder stack
   (right-click a channel → "Add protocol decoder") includes UART, SPI, and I2C — pick the one
   that matches, assign the right pins, and PulseView will translate the raw waveform into actual
   bytes.
7. **What to actually probe for this project**: candidate GPIO lines between the TLSR8258 and the
   Nuvoton M031 (any wire that runs between the two chips, not just to the battery/display/
   buttons), and the SPI flash bus, per [Open Questions](open-questions.md). If you don't know
   which physical pin is which yet, that's fine — capturing "something happens on this wire when
   I press start on the app" is itself useful data, even before you know exactly what it's called.

## Part 2: SWD probe for the Nuvoton M031

**Use the ST-Link V2 that came in the kit directly — you don't need to flash anything first.**
Despite being marketed for STM32, ST-Link V2 speaks standard SWD and works with any Arm Cortex-M
target via the free OpenOCD tool, including the Nuvoton M031.

### Step 0 (recommended): practice on a Blue Pill first

Before connecting anything to the real device, get comfortable with the whole workflow on one of
the two spare STM32F103C8T6 "Blue Pill" boards from the kit — they're a few dollars, extremely
well-documented, and a mistake here costs nothing.

1. Wire the ST-Link V2 to the Blue Pill: **SWCLK → SWCLK, SWDIO → SWDIO, GND → GND, 3.3V → 3.3V**
   (both boards label these pins directly — no soldering needed, jumper wires from the kit are
   enough since the Blue Pill has pin headers).
2. Install [OpenOCD](https://openocd.org/pages/getting-openocd.html) (free).
3. Run: `openocd -f interface/stlink.cfg -f target/stm32f1x.cfg`
4. If it connects, you'll see OpenOCD print the detected chip and enter a listening state. That's
   confirmation your ST-Link, cables, and OpenOCD install all work correctly — the exact same
   chain you'll use on the real device, just pointed at a $2 practice board first.
5. `Ctrl+C` to stop OpenOCD when done.

### Step 1: connect to the real Nuvoton M031

1. **Locate the Nuvoton's SWD pads on the actual device board.** This isn't documented yet in this
   repo — it depends on your specific board revision, and needs visual inspection once the device
   is open. Look for 4 small pads or a tiny header near the chip itself, often labeled (even just
   silkscreened dots) for SWCLK/SWDIO/GND/3V3. A continuity tester (multimeter in beep mode) is
   the reliable way to confirm which pad is which if they're unlabeled — connecting to the wrong
   pin blind is a real risk to avoid.
2. **If there's a labeled header or castellated pads**: jumper wires may be enough, no soldering.
3. **If you need to solder** (bare test points, no header): this is where "minor soldering
   experience" comes in.
   - Use thin (30-32 AWG) wire, pre-tin both the wire tip and the pad with a small amount of
     solder before joining them, and work quickly (a couple of seconds of contact) to avoid heat
     damage to the small pad or nearby components. A fine-tip iron (not a wide chisel tip) makes
     this much easier.
   - Add a small dab of hot glue over the finished joint once cooled, to strain-relieve the wire —
     these pads are small and a tugged wire will lift the pad off the board.
4. **Same OpenOCD command as the practice run**, but with `target/stm32f1x.cfg` swapped for the
   Nuvoton's own target config (Nuvoton publishes OpenOCD-compatible configs for the M0 series —
   check [Nuvoton's own tool page](https://www.nuvoton.com/tool-and-software/debugger-and-programmer/)
   if `target/numicro.cfg` — the generic NuMicro config bundled with recent OpenOCD — doesn't work
   directly for this exact part).
5. Once connected, OpenOCD/a GDB session lets you **dump the chip's flash** (`dump_image` command
   in OpenOCD, or `flash read_bank 0 nuvoton_dump.bin 0 0x10000` for a 64KB M031) — that dump is
   the actual deliverable this whole step exists for: real firmware to load into Ghidra and
   analyze, instead of theorizing about this chip from the outside.

## Part 3: TLSR8258 SWire recovery tooling

This is the one that matters most before any real firmware experiment on the main chip.

1. **Identify your USB-serial adapter's chipset** — check the small chip on the board itself
   (CH340/CH340G or CP2102 printed on it). If it says FTDI anywhere, **do not use it for this
   step** — see [Methodology](methodology.md#hardware-tooling) for why.
2. **Download [`TlsrComSwireWriter`](https://github.com/pvvx/TlsrComSwireWriter)** (free) and
   follow its own wiring diagram — in short: the adapter's **TXD and RXD** go to the TLSR8258's
   single **SWire pin** (yes, both to the same pin — the tool multiplexes them in software), GND
   to GND, and RTS wired for power/reset control per the tool's exact diagram (varies slightly
   depending on whether your target board exposes a separate reset pin).
3. **Locate the TLSR8258's SWire pad** on the board — same visual-inspection/continuity-testing
   approach as the Nuvoton's SWD pads above. Telink's own reference designs typically label this
   pin `SWM`/`SWS` on schematics; on the physical board it may just be an unlabeled test point
   near the chip.
4. **Test the connection on a low-stakes target first if at all possible** before trusting it on
   the real device — if you have any other TLSR82xx-family board (even a cheap dev board bought
   specifically for practice), confirm the tool can read that chip's info before relying on the
   setup for real recovery.
5. **If the connection is flaky**: the most common cause per the tool's own docs is an LED wired
   directly on the RX line interfering with the bit-banged signal timing. The fix is physically
   removing it — find the small LED (and/or its series resistor) near the RXD pin on your adapter
   board, and either desolder it or simply clip one of its legs with flush cutters. This doesn't
   affect the adapter's other functions.

## What you'll actually be able to do once this is all working

- **Confirm or rule out the heater-driver theory** (logic analyzer + Nuvoton flash dump) — the
  single biggest open question in [Open Questions](open-questions.md).
- **Recover from a bad TLSR8258 flash attempt** — the prerequisite this repo's own firmware
  research has flagged repeatedly before any custom OTA payload should be attempted.
- **Independently verify anything in [Firmware Architecture](firmware-architecture.md)** against
  real, live hardware, rather than trusting static analysis of a possibly-stale firmware dump.

## Contributing

If you get further than this guide does — exact SWD/SWire pad locations for a specific board
revision, a working target config for the Nuvoton, a real capture that resolves an open question —
that's exactly the kind of contribution [`CONTRIBUTING.md`](../CONTRIBUTING.md) is asking for.
