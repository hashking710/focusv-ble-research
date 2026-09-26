[← README](../README.md) · [BLE Protocol](ble-protocol.md) · [Firmware Architecture](firmware-architecture.md) · [Methodology](methodology.md) · **Open Questions**

# Open Questions

What's still unresolved, as a current punch list rather than a log of how each item was chased.
See [Firmware Architecture](firmware-architecture.md) and [BLE Protocol](ble-protocol.md) for
everything that *is* confirmed. Items tagged 📡 (planned BLE sniffer) or 🔬 (planned logic analyzer) are specifically targeted by
the hardware tooling planned in the [README's Roadmap section](../README.md#roadmap) — not yet
started, but scoped against these exact gaps rather than "more reverse engineering in general."

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
  firmware image (the entire cooperative scheduler, every GPIO write, the analog-register bus,
  the confirmed-empty interrupt vector table) found no duty-varying or PWM-style output write
  anywhere. Two live possibilities: (a) dedicated hardware (a PWM peripheral configured once at
  init and left running autonomously) that this kind of search wouldn't surface, or (b) a
  **separate companion MCU** handles high-current heater switching, talked to over a serial link
  from this chip — the app's own configuration references a distinct "battery MCU" firmware
  update path, though its manifest endpoints returned no published content when checked, so this
  couldn't be confirmed or ruled out that way.
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
- **Two unexplained 4-byte fields in the 40-byte custom header**, ahead of the `KNLT` magic.
  Purpose unconfirmed — not a standard CRC32/Adler32.
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
