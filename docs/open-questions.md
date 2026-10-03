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
- **Where the heating-element output is actually driven.** Resolved by disassembling the device's
  actual current firmware build (`PROD-111224` — the originally-analyzed `PROD-071024` turned out
  to be stale, no longer served to real devices) rather than more static digging on the old one.
  All three devices (Carta 2, Aeris, Carta Sport) drive the heater directly on the TLSR8258 itself:
  a dedicated output routine, called every tick, toggles one GPIO pin on or off depending on where
  the current tick falls within a fixed 500-tick window, against an on-time value the PID step
  computes and clamps each cycle — a software-timed slow PWM, not a hardware PWM-peripheral write.
  That's exactly why the original exhaustive search (for a duty-register-style write) missed it —
  the real mechanism is an ordinary GPIO toggle gated by a tick-window comparison, a different code
  shape entirely. See
  [Firmware Architecture § Where the heater output is driven](firmware-architecture.md#where-the-heater-output-is-driven).
  **This retires the Nuvoton M031 heater-driver theory** this item previously led with — the M031's
  actual role is open again, not resolved.
- **The hardware-ramp patch's per-tick orchestrator and marker-dispatch addresses, for all three
  devices.** Not originally an "open question" entry, but worth recording here the same way: an
  earlier pass had the Carta 2 orchestrator address wrong (carried over from a different,
  stale firmware build) and the marker-dispatch fix architecturally wrong (patched a single leaf
  of a compare chain that the new marker values could never reach). Both caught and fixed by
  re-deriving every address directly against the current build rather than trusting an earlier
  "confirmed" label, including an exhaustive toolchain-only scan (generate the correct instruction
  encoding at every possible position in the firmware, byte-compare against the real file) where
  Ghidra's own auto-analysis couldn't resolve a call site via normal cross-references. Aeris and
  Carta Sport got the same full treatment from scratch, each surfacing its own device-specific
  surprise (Aeris's LED-push gate behaves differently from Sport's; Sport's ROM-divide helper
  lives at a different address than both other devices'). Full details in
  [Firmware Architecture § Custom firmware: device-native hardware ramp](firmware-architecture.md#custom-firmware-device-native-hardware-ramp)
  and in the patch repo itself, [focusv-ramp-firmware](https://github.com/hashking710/focusv-ramp-firmware).
- **A second, different-shaped gap in the Carta 2 ramp patch, caught in a later audit before any
  hardware testing happened.** The shipped 5-site version never suppressed two screen elements
  (`FUN_0000dcac`, `FUN_0000e300`) that the real live-heating refresh routine calls unconditionally
  every tick — `dcac` draws directly over part of the patch's own graph area. Found by reading that
  routine's full real call sequence rather than trusting the original 3-site design's scope. Fixed
  with two more call-site patches (now 7 total), the graph enlarged using the screen space this
  freed, and every other patch site's replacement bytes regenerated fresh since adding code shifted
  their targets. Full details in
  [Firmware Architecture § Custom firmware](firmware-architecture.md#custom-firmware-device-native-hardware-ramp)
  and the patch repo's Carta 2 README.
- **The real OTA-receive GATT write callback, and the finalize/copy step — both resolved, on all
  three devices independently, and the two-phase staging model they were filed under turned out to
  be wrong everywhere.** Found by the same method on each device: locate the OTA characteristic's
  UUID bytes in the image, follow the GATT attribute-table entry that references them to its write
  callback's function pointer, then trace that function. All three use an identical mechanism —
  each incoming block is written directly to its final address as it arrives, at `block_index*16 +
  base`, through the same flash-write primitive used everywhere else in that device's firmware —
  just compiled differently per device:
  - **Aeris**: callback at disassembly `0x116ec` (found via the write dispatcher at `0x11688`).
    `base` is a struct field (RAM `0x843a48+0x1c`). Confirmed nothing in the binary ever writes it
    by finding every one-line setter touching that struct (a cluster at `0x11664`-`0x1168d`) and
    showing none touches `+0x1c`, while `+0x4`/`+0x8` (the pre-erase region's size) are set once at
    early boot (`0x62e`, hardcoded immediates `124`/`0x20000`) — not session-derived. Telink's
    standard BSS zero-init leaves `base` at `0`.
  - **Carta 2**: same shape, same struct layout even (RAM `0x843a20+0x1c`), found the same way
    (callback at `0x189ec`, dispatcher at `0x18cc8`'s neighborhood). Same elimination proof, same
    setter cluster shape (`0x18960`-`0x1898d`), same result: nothing writes `+0x1c`, size is set
    once at boot (`0x4ce`, immediates `248`/`0x40000`) — `base` is `0` here too.
  - **Carta Sport**: structurally different code generation (the compiler used a standalone global
    variable rather than a packed struct for this field, and reads the OTA opcode from different
    packet byte offsets), but the same mechanism underneath: callback at `0xe2cc`, the gap-recovery
    erase loop reads `base` from RAM `0x8429ac` through a single literal-pool reference (`0xe86e`)
    that is the *only* place in the entire 90,900-byte image this variable is ever touched — so it
    too is never written, and stays at its BSS-zero default of `0`.

  Each device was also confirmed to have the matching boot-time pre-erase routine (sweep the target
  region in 4KB sectors, skip ones already blank, called once from main init, never from the live
  OTA path) — which is why an ordinary in-order transfer never issues its own erase call on any of
  the three. All three were cross-checked against the real client (`terpline-web`'s
  `lib/protocol/ota.ts`): it sends 16-byte blocks indexed from 0 with no address/bank field at all,
  which only makes sense if each device's own base is fixed and the same every session — consistent
  with what every binary shows.

  **What this means for the original theory**: Carta 2's boot-time validity check erasing at real
  flash address `0x40000` is real (see below) but is **not** evidence of a staging-then-copy update
  mechanism — the live OTA write path on Carta 2 writes directly to base `0`, same as the other two.
  Whatever the `0x40000` erase is for, it isn't the mechanism `tools/ota-flash.html` or the real app
  use to push an update.

## Firmware

- 🔬 **What the Nuvoton M031 actually does.** Open again now that the heater-driver theory above
  is retired — the TLSR8258 side has nothing else obviously missing a destination, so there's no
  current firmware-level lead pointing at a specific job for this chip. Needs its own flash dump
  and analysis (standard Arm/SWD, not the Telink TC32 toolchain used elsewhere in this repo) or
  logic-analyzer work on its pins to make any progress — not something static analysis of the
  TLSR8258 image alone can resolve further.
- **Boot-time firmware bank/validity selection.** A validity check (KNLT header magic at real
  flash address `0`) is confirmed (see [Firmware Architecture](firmware-architecture.md)). The
  erase this check triggers landing on address `0x40000` on Carta 2 is **not** the live OTA write
  mechanism's staging area — that's now independently confirmed to write directly to base `0` on
  all three devices (see the resolved item above). What the `0x40000` erase on Carta 2's validity
  check is actually for is now the open part of this item: possibly an unrelated recovery/fallback
  path, possibly something else — not re-chased yet since it no longer blocks understanding the
  live update mechanism. Separately and still genuinely open regardless: what actually decides
  which bytes end up at the device's real running address before the CPU starts executing
  (mask-ROM bootloader, or something else) is not part of this dumped image and couldn't be
  determined by analyzing it.
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
