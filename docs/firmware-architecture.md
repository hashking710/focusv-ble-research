[← README](../README.md) · [BLE Protocol](ble-protocol.md) · **Firmware Architecture** · [Methodology](methodology.md) · [Open Questions](open-questions.md)

# Firmware Architecture Reference

Reverse-engineered from the OTA firmware image for the Quantum/Aeris/Sport device family (a
Focus V "Carta 2" identifies internally as Quantum — see [BLE Protocol](ble-protocol.md)). This
covers the main SoC's firmware: chip identification, boot chain, the confirmed session/PID
control loop, flash layout, and the real firmware-update mechanism.

**A caveat that applies to this whole document**: the firmware analyzed here is one specific
build. Software updates for these devices have been observed in the wild that are newer than
what any publicly-reachable manifest currently serves (see [Open Questions](open-questions.md)) — general
architecture (boot chain, session/PID loop, flash layout patterns) is unlikely to change much
between point releases, but anything specific to the OTA mechanism itself should be treated as
a working model for *a* build, not necessarily *the current* one, until cross-checked.

## Chip and toolchain

**Telink TLSR8258** — confirmed from the physical part marking on a real board (`TLSR8258
F1KET48`), a 32-bit RISC-like TC32 core (similar to but not identical to ARM Thumb — generic ARM
Thumb disassemblers decode it at best ~56% correctly). Telink publishes a real datasheet and SDK
for this exact part, which turns out to matter a lot in practice — see the callout below.

- **Ghidra 12.1.3** with the community `Telink_TC32` processor module
  ([rgov/Ghidra_TELink_TC32](https://github.com/rgov/Ghidra_TELink_TC32)) — SLEIGH spec compiled
  locally, no prebuilt `.sla` ships with it.
- **Independent validation**: a real `tc32-elf-as`/`objdump`/`ld`/`objcopy` toolchain, built and
  run under Linux (the Windows-hosted community mirror crashes on some systems). A full
  assemble→link→extract→disassemble round-trip confirms the assembler produces correct TC32
  machine code, and `tc32-elf-objdump`'s raw disassembly of the real firmware matches Ghidra's
  byte-for-byte at every point checked — genuine ground truth, not a single-tool guess.
- **[GhidraMCP](https://github.com/LaurieWired/GhidraMCP)** for programmatic access to Ghidra's
  decompiler against a live CodeBrowser session.
- **A real, public SDK for this exact chip** —
  [Telink_825X_SDK](https://github.com/denpaforks/Telink_825X_SDK) (`components/drivers/8258/`)
  — gives ground-truth peripheral register addresses that the Ghidra module's bundled register
  names get wrong (see [Methodology](methodology.md)). Cross-referencing against it directly
  resolved the physical-button-input question below, after several sessions of guessing from
  code shape alone couldn't.

See [Methodology](methodology.md) for tooling gotchas specific to this chip/module combination.

## Board hardware

Everything else in this document is about the TLSR8258's own firmware. Identifying the other
chips on the board (from real part photos) turned out to matter for scoping *what's even in this
firmware image in the first place*:

| Chip | Role |
|---|---|
| **Telink TLSR8258** | Main BLE SoC — everything this document otherwise describes: session/BLE handling, the PID control loop, display, flash. |
| **Nuvoton M031TD2AE** (Arm Cortex-M0, 64KB flash, 12× 16-bit PWM channels) | A second, independently-programmable MCU on the same board. Not yet dumped or analyzed — different vendor toolchain entirely (standard Arm, not Telink TC32). Its 12 PWM channels make it a strong candidate for the actual heating-element driver (see [Open Questions](open-questions.md)) — the TLSR8258 image was exhaustively searched for PWM/duty-varying output and found none, which is fully consistent with that logic living on this chip instead. |
| **SouthChip SC8922A** | A 2-3 cell Li-ion boost battery charger IC. Fixed-function analog/mixed-signal silicon — no firmware, not a candidate for anything BLE- or update-related. |

**Practical implication**: if you're looking for heater-output logic, temperature-driven duty
cycles, or anything else this document says was exhaustively searched for and not found in the
TLSR8258 image, the Nuvoton M031 is the next place to look — a genuinely separate analysis effort
from everything else in this repo so far.

**Why heater rather than display, specifically.** The display isn't a live possibility for the
M031 — it's already fully accounted for on the TLSR8258 side (see [Display](#display) below):
the exact real ST7789 command set and gamma tables, driven directly over the TLSR8258's own SPI
peripheral, confirmed by literal register-address match. A more specific argument for heater
control: the confirmed PID loop (see [below](#session-state-machine-and-pid-control-loop))
computes a real output value every tick that has no on-chip destination (the exhaustive PWM/GPIO
search below found nowhere for it to go) — a second MCU with 12 PWM channels, physically
positioned near the board's high-current leads rather than near the display connector, is the
natural place for that value to go.

**Every standard external communication peripheral on the TLSR8258 has now been checked and ruled
out as the transport to the M031.** A literal-pool scan against the complete real register map (all
345 entries from the SDK's `register_8258.h` — I2C, SPI, MSPI, UART, clock/reset, I2S/DMIC, not
just the GPIO/UART/SPI subset checked earlier) found: SPI traces entirely to the display (above);
MSPI traces entirely to the on-chip SPI-NOR flash controller; I2C has zero real hits. The UART is
genuinely initialized and enabled at boot, but its data and status registers — the only two
registers any transmit or receive call could possibly use — have **zero references anywhere in the
firmware image**. That rules the UART out as a data link, rather than leaving it as an open lead:
every one of its register hits is already fully accounted for by the three boot-time
init/enable/mode-config calls, with nothing left unsearched. See [Open Questions](open-questions.md)
for what that leaves open.

## File format

The distributed `.bin` has a **40-byte custom header**:

- Bytes 0-7: two 4-byte fields, purpose unconfirmed (not a standard CRC32/Adler32).
- Bytes 8-11: magic `KNLT` (ASCII) — this is checked both by the app before sending an update,
  and by the firmware itself at boot (see Flash layout below).
- Remaining header bytes: unconfirmed.

All addresses in this document are relative to the file **with that header stripped** (byte 0 of
the stripped image = byte 40 of the original download).

## Boot chain

Confirmed via the actual hardware reset vector — the most reliable ground truth available,
independent of any assumptions about function boundaries.

- **`0x00`-`0x7E`**: interrupt/reset vector table, genuinely all-NOP (64 slots × 2 bytes) —
  verified against raw bytes, not a disassembler artifact. No populated interrupt handlers
  anywhere in this image.
- **`0x80`-`0x112`**: the real reset/startup handler. Checks a boot-reason byte at fixed low
  address `0x4`, sets up the stack(s), zero-fills BSS, copies `.data` from flash to RAM, then
  jumps to `main()`, followed by a jump-to-self trap in case `main()` ever returns.
- **`main()`**: peripheral/clock init, a cold-boot check (with an oscillator-stabilization wait
  on first-ever boot), GPIO pin configuration, then enters the scheduler superloop:

```c
do {
  tick_dispatcher();        // per-tick task dispatcher (BLE queue drain, connection housekeeping)
  *watchdog_feed = 8;
  session_state_machine();  // session/PID/thermal/display tick — see below
} while (true);
```

This is a **single-threaded cooperative scheduler with no preemption anywhere** — the interrupt
vector table is confirmed empty. Any code reasoning about concurrency in this firmware can treat
everything as strictly sequential.

## BLE command handling

Incoming writes on the normal characteristic are queued (a pair of 4-slot ring buffers — one for
fixed 6-byte payloads, one for variable-length ones) and drained by the scheduler's tick
dispatcher, not processed immediately in an interrupt context. The RX opcode dispatcher branches
on the first byte of a write against the documented opcode set (see [BLE Protocol](ble-protocol.md)) and hands
off to per-opcode handlers.

A large portion of this firmware's settings/session/OTA-related logic does **not** decompose into
clean, independently-understandable functions — many different logical entry points (the `0xCC`
handler's marker dispatch, LED-timeout settings, the screensaver transfer state machine) resolve
to the same large, heavily-fallen-through block of code when traced. This is very likely an
artifact of automatic function-boundary detection splitting up what's really a handful of shared
entry points, not five genuinely different copies of similar logic — worth knowing before
assuming a new address is fresh, undiscovered territory.

## Session state machine and PID control loop

The device runs **genuine closed-loop PID temperature control**, not a simple on/off timer as
might be assumed from the marketing material alone.

- **Session-state tick function** — called every scheduler iteration. Operates on a central
  runtime struct holding session state (a byte with observed values `0`, `1`, `3`, `4`, `11`,
  `12`, `13`), a 16-bit countdown decremented once per tick, and drives state transitions
  (playing notification cues at fixed thresholds before a session ends, transitioning through a
  "finishing" state, etc.).
- **PID orchestrator** — pulls the live target temperature from a preset/profile lookup into a
  dedicated struct field, calls the PID math, then periodically logs `(index, temperature,
  power)` triples and transmits them over BLE (the `0xDD` telemetry notify documented in
  [BLE Protocol](ble-protocol.md)).
- **PID math** — textbook: error term (target − measured), an integral term with anti-windup
  clamping, a derivative/rate term, combined into a weighted output, clamped non-negative.
- **Feed-forward overshoot compensation** — bumps the working target temperature up by a tiered
  offset depending on which of three temperature bands the target falls in, to counteract
  thermal/probe lag.
- **Stability detection** — requires the measured temperature to stay within a tolerance window
  for multiple consecutive ticks before declaring "at temperature," guarding against false
  triggers from sensor noise.

**The live target-temperature field is read only once per session/step**, gated behind an
"initialized" flag byte — clearing that flag forces a fresh read from the same struct the `0xCC`
BLE handler writes into. Confirmed (via direct literal-pool byte comparison, not inference) that
the PID orchestrator's struct pointer and the BLE settings-write struct pointer are **the same
runtime struct** — the `0xCC` handler's writes and the PID's setpoint read are already the same
memory, no separate copy step exists.

The **stock re-initialization path has side effects beyond the target temperature** — it also
resets the session-log entry index, an internal power/duty value, and the PID integral
accumulator, among other fields. Anything hooking this re-init path needs to account for that
(e.g. a narrower, purpose-built re-init if only the target temperature should change without
resetting the session log).

### Where the heater output itself is *not*

An exhaustive search — the entire cooperative scheduler, every GPIO write call site, the
Telink analog-register bus, the (confirmed-empty) interrupt vector table — found **no
duty-varying or PWM-style output write anywhere in this image**. Every GPIO write either passes a
boot-time constant or is part of the confirmed ADC sensor-read sequence; none vary with live
sensor/timer state.

This absence is now well explained rather than just a negative result: see
[Board hardware](#board-hardware) above — a separate Nuvoton Cortex-M0 MCU with 12 PWM channels
sits on the same board, not yet analyzed, and is the far more likely home for this logic. See
[Open Questions](open-questions.md) for the current state of this specific item.

## Thermal safety / fault chain

A genuine, ground-truth-confirmed safety subsystem, separate from the PID control loop:

- ADC channel configuration and a full sampling routine (7 samples, hardware-timer-paced,
  insertion-sort median filter to reject noise, fixed-point calibrated conversion).
- Called every tick; averages readings and compares against a fixed threshold. **After 3
  consecutive threshold violations**, escalates to a fault handler that sets fault-state flags,
  logs an error code, and fires a distinct error notification (LED + buzzer pattern) — one branch
  appears to abort an in-progress session.

This subsystem only *reads and checks* — it does not appear to drive the heater output itself.
Any firmware modification should leave this path untouched.

## Physical button input

The GPIO register map (see [Chip and toolchain](#chip-and-toolchain)) is a per-port-group block,
8 bytes apart, with the *input data* register as the first byte of each group and *output data*
as the fourth:

```
Port bases: A=0x800580, B=0x800588, C=0x800590, D=0x800598, E=0x8005a0
  +0: in (read)   +1: ie   +2: oen   +3: out (write)   +4: pol   +5: ds   +6: func   +7: irq_en
```
Ports B and C are configured indirectly through the analog-register bus (see below); A, D, and E
are direct memory-mapped reads/writes.

**Confirmed: the physical button input is read every single scheduler tick**, polling
`reg_gpio_pd_in` (`0x800598`) bits 1 and 5 — two distinct physical inputs — through a textbook
software debounce: 6 consecutive same-state ticks confirms a press, 5 confirms a release, and a
separate 14-tick counter on the second bit distinguishes a short press from a hold. Confirmed
events are written into a small record (tag + tick-count-derived code) that appears to feed the
same style of tag/param dispatch used for BLE commands elsewhere in this firmware, though its
consumer hasn't been traced yet.

A second function, also called every tick, gates on **both** `reg_gpio_pc_in` (`0x800590`) bit 0
and the same `reg_gpio_pd_in` bits — when satisfied, it reconfigures several GPIO *output*
registers at once and calls a helper with char-valued parameters (matching this firmware's
general pattern of using ASCII-char op-codes, e.g. `'t'`/`'v'` for OTA). Plausibly a
button-combo-gated mode/output change; not fully traced.

## Display

A standard ST7789-family TFT LCD driver (240×240 active window on a 240×320 physical GRAM,
matching the screensaver image resolution documented in [BLE Protocol](ble-protocol.md)) — all commands match
the published ST7789 command set exactly, no proprietary quirks.

Confirmed drawing primitives, usable directly from firmware with no BLE transfer involved:
- Set drawing window (CASET/RASET).
- Solid-fill rectangle.
- 1-bit-per-pixel glyph/bitmap draw with independent foreground/background color — the same
  primitive used throughout the stock settings/session UI for on-screen text and numbers.

A local firmware draw call using these primitives is effectively instant compared to a full
BLE-uploaded screensaver image (which takes thousands of individual 16-byte writes).

## Flash layout

Standard SPI NOR flash, textbook opcodes (Read Data `0x03`, Write Enable + Sector Erase `0x06`+
`0x20`, Write Enable + Page Program `0x06`+`0x02`, Read Status Register `0x05` for busy-poll,
JEDEC ID `0x9F`). **Sector erase is required before any write** — writes cannot happen in place
without first erasing the containing 4KB sector.

### Settings sectors

A dozen-plus flash regions, each exactly 4KB (`0x1000`) apart, one setting category per sector,
each with its own sentinel/magic byte (falls back to hardcoded defaults if the sentinel doesn't
match — the standard "never written yet" pattern, since erased NOR flash reads as `0xFF`):

```
0x80000-0x8c000 (several sectors)   general settings
0x8e000                             settings
0xca000                             separate settings category
0xcb000+                            session-log storage (16-byte entries)
```

### Screensaver image storage — corrected

**`0xAC000` and `0x8F000` are the two screensaver image save slots, not firmware A/B banks** (an
earlier working theory in this research, now retracted after directly decompiling the function
that uses them — it renders a saved image from flash onto the LCD; it never writes flash at all).
The address spacing (`0x1D000` = 118,784 bytes) exactly matches one 240×240 RGB565 image
(115,200 bytes) rounded up to a whole number of 4KB sectors — consistent with the two save slots
documented in [BLE Protocol](ble-protocol.md)'s screensaver section.

### Real firmware A/B mechanism

The actual firmware self-update mechanism (as distinct from the screensaver slots above) appears
to be:

- A validity check reads the 40-byte header at the very start of the flash chip (real address
  `0x0`) and checks for the `KNLT` magic at byte offset 8.
- If valid, a large region (61 sectors, ≈244KB — comfortably more than the actual firmware image
  size) is erased starting at real flash address `0x40000`, used as a **staging buffer** for an
  incoming update — the live, running image at address `0x0` is never touched during the
  transfer itself.
- If the header at address `0` is *not* valid, the same erase targets address `0` directly
  instead — most plausibly a recovery/first-flash fallback path, not the normal update route.

**No evidence of a hardware bank-remap register was found** — the confirmed boot chain (above) is
a single, fixed execution location at address `0`. The working model is therefore a two-phase
update: receive and verify the new image at the `0x40000` staging area, then some **separate,
not-yet-located finalize step** erases address `0` and copies the verified bytes down, before a
reboot. See [Open Questions](open-questions.md) — this finalize step, the real GATT write-callback
that receives OTA bytes, and where the erase-trigger flag gets set are all still unconfirmed.

## Open questions

See [Open Questions](open-questions.md) for the full, current list of unresolved items, including
the real OTA-receive code path, boot-time behavior not covered by this image, and the
firmware-version caveat mentioned at the top of this document.
