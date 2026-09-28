[← README](../README.md) · [BLE Protocol](ble-protocol.md) · [Firmware Architecture](firmware-architecture.md) · [Methodology](methodology.md) · [Hardware Setup](hardware-setup.md) · **Open Questions**

# Open Questions

What's still unresolved, as a current punch list rather than a log of how each item was chased.
See [Firmware Architecture](firmware-architecture.md) and [BLE Protocol](ble-protocol.md) for
everything that *is* confirmed. Items tagged 📡 (planned BLE sniffer, not yet sourced) or 🔬
(logic analyzer / SWD probe, hardware now sourced — see
[Methodology § Hardware tooling](methodology.md#hardware-tooling)) are specifically targeted by
the hardware tooling described in the [README's Roadmap section](../README.md#roadmap), scoped
against these exact gaps rather than "more reverse engineering in general."

## Recently resolved

- **Physical button-gesture detection.** Resolved once the exact chip (Telink TLSR8258) was
  identified from a real board photo and cross-referenced against its public SDK — the firmware
  polls `reg_gpio_pd_in` (real GPIO input register, not previously locatable via the Ghidra
  module's incorrect register names) every scheduler tick with a standard software debounce. See
  [Firmware Architecture § Physical button input](firmware-architecture.md#physical-button-input).
  This was the exact case that motivated identifying the chip precisely in the first place —
  general lesson in [Methodology](methodology.md).

## Firmware

- 🔬 **Where the heating-element output is actually driven.** An exhaustive search of the main
  TLSR8258 firmware image (the entire cooperative scheduler, every GPIO write, the analog-register
  bus, the confirmed-empty interrupt vector table) found no duty-varying or PWM-style output write
  anywhere. **Leading theory**: a separate, real Nuvoton M031TD2AE (Arm Cortex-M0, 12× 16-bit PWM
  channels) MCU confirmed to exist on the same board (see
  [Firmware Architecture § Board hardware](firmware-architecture.md#board-hardware)) drives it —
  not just because it has the peripherals for it, but because the confirmed PID loop computes a
  real output value every tick with nowhere on-chip to go, and the M031 is physically positioned
  near the board's high-current leads rather than near the display connector (the display itself
  is separately fully accounted for on the TLSR8258 side, ruling that out as the M031's job).
  **Every standard external comms peripheral on the TLSR8258 (I2C, SPI, MSPI, UART) has now been
  checked against the complete real register map and ruled out as a data link to the M031** — SPI
  is the display, MSPI is the on-chip flash controller, I2C has no real hits, and the UART (though
  genuinely initialized and enabled at boot) never references its own data/status registers
  anywhere in the image, meaning it never actually transmits or receives a byte. That leaves two
  live possibilities static analysis alone can't distinguish: a plain bit-banged GPIO signal (a
  software-timed pulse the M031 could read via its own timer-capture input, a different code shape
  than the duty-register search above would catch) rather than a proper bus, or no data link at
  all — the M031 running its own independent closed loop from its own ADC, with the TLSR8258's PID
  output used only for BLE telemetry/on-screen display. **Not proven at the firmware level** — the
  M031's own flash hasn't been dumped or analyzed at all; that's a new target requiring standard
  Arm/SWD tooling, not the Telink TC32 setup used everywhere else in this repo (see
  [Methodology § Hardware tooling](methodology.md#hardware-tooling) — this is now in progress). The
  logic-analyzer work would still help confirm which physical chip actually switches the heater
  current, independent of a firmware dump.
- **Boot-time firmware bank/validity selection.** A validity check (KNLT header magic at real
  flash address `0`) and an erase-target decision between address `0` and a staging area at
  `0x40000` are confirmed (see [Firmware Architecture](firmware-architecture.md)), but no evidence exists in this image
  of a hardware bank-remap mechanism — the boot chain always executes from a single fixed
  location. What actually decides which bytes end up at address `0` before the CPU starts
  executing (mask-ROM bootloader, or something else) is not part of this dumped image and
  couldn't be determined by analyzing it.
- 📡 **The real OTA-receive GATT write callback.** The separate OTA characteristic (see
  [BLE Protocol](ble-protocol.md)) is confirmed at the protocol level, but the firmware-side function that
  actually receives those 20-byte CRC16'd blocks and where the erase-trigger flag gets set were
  not located after several different search strategies (address-by-address decompilation,
  whole-image literal-constant search, and a GUI-assisted pass once Ghidra's function-boundary
  gaps were fixed). A promising-looking lead (a jump-table-driven sub-dispatcher near the erase
  logic) turned out to be unrelated session-cancel/temperature-limit-clamping code, not the OTA
  path — recorded here so it isn't re-chased.
- 📡 **The `0x40000` → `0x0` finalize/copy step.** Following from the point above — assuming the
  two-phase stage-then-copy model in [Firmware Architecture](firmware-architecture.md) is correct, the code that
  performs the final copy (and whatever self-flash-safety handling it needs, since this would be
  overwriting the flash region it may itself be executing from) has not been located.
- **Two 4-byte fields in the 40-byte custom header, ahead of the `KNLT` magic — now mostly
  resolved.** Direct byte comparison of two real firmware files (different device targets,
  completely different size and content) showed these two fields are **identical across both** —
  they're fixed constants, not a content-derived checksum, and can be copied verbatim into a
  patched image with no computation needed. Confirmed separately that the firmware's own boot-time
  validity check (`FUN_00005558` in the private research notes) reads only 9 header bytes and
  checks exactly one of them (the `K` of `KNLT`) — nothing else in the header is validated by any
  code found in this image. **What's still open**: a much narrower 2-byte field (offset 12-13)
  that does genuinely vary between builds and doesn't match CRC16, CRC32, or Adler32 against any
  tried candidate byte range — likely an opaque build/sequence tag rather than a validated
  checksum, but not proven. Also still open: whether the still-unlocated OTA-finalize code, or a
  silicon mask-ROM bootloader entirely outside this image, checks anything beyond what's confirmed
  here.
- **A handful of protocol-level fields** with unconfirmed exact meaning even though their byte
  positions are known — see [BLE Protocol](ble-protocol.md)'s own "Known gaps" section (an unmapped screensaver
  status byte, the exact calibration-status query/response pairing, screensaver slot-select
  metadata).

## A live firmware-version caveat

Firmware builds have been observed running on real hardware that are newer than what any
currently-reachable public update manifest serves — meaning the specific binary this research was
performed against may not exactly match what's shipping right now. General architecture (boot
chain, the session/PID control loop, flash layout conventions) is unlikely to shift much between
point releases of the same firmware family, but anything specific to the OTA mechanism itself
(the exact staging address, header field layout, or any of the still-unresolved items above)
should be treated as a snapshot of one build, not a guaranteed-current spec, until independently
re-confirmed against whichever build a given device is actually running. The cleanest way to
re-verify: capture live BLE traffic during a real update rather than relying on static analysis
of a possibly-stale binary.

## Contributing

If you resolve any of the above (or find something new), a PR with the specific evidence (a live
capture, a decompiled function, a cross-reference in the app's own source) is very welcome —
these notes are meant to be a living reference, not a final word.
