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
- **The real OTA-receive GATT write callback, and where updates land: resolved on all three
  devices. Both earlier models were wrong.** Each device's write callback was found the same way:
  locate the OTA characteristic's UUID bytes in the image, then follow the GATT attribute-table
  entry that references them to its write-callback pointer. Each 16-byte block is written to
  `block_index*16 + base` through the device's normal flash-write primitive:
  - **Aeris**: callback at disassembly `0x116ec` (write dispatcher `0x11688`), OTA struct at RAM
    `0x843a48`, `base` at `+0x1c`.
  - **Carta 2**: callback at `0x189ec`, struct at `0x843a20`, `base` at `+0x1c`.
  - **Carta Sport**: callback at `0xe2cc`. The fields are laid out differently (struct
    `0x842988`, `base` at `+0x24` = `0x8429ac`), and the OTA opcode is read from other packet
    offsets. The mechanism is the same.

  A later pass corrected an earlier conclusion that `base` is never written and stays `0`. That
  conclusion came from checking only the setters near the callback. The real setter is in the
  boot path. It reads the chip's boot-bank register `0x80063e`. When the device runs from bank 0,
  it copies the second bank's address into `base`; when it runs from bank 1, it sets `base` to `0`.
  - Sport: `0xdd82`–`0xddd4`
  - Aeris: `0xd4dc`–`0xd516`, copying `0x843a50` (struct `+0x8`)
  - Carta 2: `0x147dc`–`0x14816`, copying `0x843a28` (struct `+0x8`)

  That `+0x8` field is the bank address the SDK's `bls_ota_set_fwSize_and_fwBootAddr` call sets
  once at early boot: Aeris `0x62e` (124 KB / `0x20000`), Carta 2 `0x4ce` (248 KB /
  `0x40000`). So an update always goes to the bank the device isn't running from.

  **Finalize, resolved too (traced on the Sport):**
  - During the transfer, the new image's flag byte (header offset 8) is held at `0xFF` (`0xe0ac`).
  - On completion, `0xe05c` writes the new flag and clears the old one.
  - The device then reboots through `0x109c`.
  - The boot ROM starts the bank with the valid flag.

  At every boot, the SDK init and the app's own wipe loops erase the bank the device isn't
  running from, which is why an in-order transfer never issues an erase. A second erase inside
  each callback only runs on a sequence gap.

  The real client (`terpline-web`'s `lib/protocol/ota.ts`) sends blocks indexed from 0 with no
  address or bank field. That matches: the device picks the bank, not the client. Full write-up:
  [Firmware Architecture § Real firmware OTA mechanism](firmware-architecture.md#real-firmware-ota-mechanism--dual-bank).

## Firmware

- 🔬 **What the Nuvoton M031 actually does.** Open again now that the heater-driver theory above
  is retired — the TLSR8258 side has nothing else obviously missing a destination, so there's no
  current firmware-level lead pointing at a specific job for this chip. Needs its own flash dump
  and analysis (standard Arm/SWD, not the Telink TC32 toolchain used elsewhere in this repo) or
  logic-analyzer work on its pins to make any progress — not something static analysis of the
  TLSR8258 image alone can resolve further.
- **Boot-time firmware bank/validity selection — mostly resolved.** The Carta 2 boot check
  reads the `KNLT` header at `0` and then erases from `0x40000` (or from `0` when the header at
  `0` isn't valid). This is the dual-bank wipe of the bank the device isn't running from. See the
  resolved OTA item above. **Still open:** the bank choice itself is made before any code in this
  image runs, by the TLSR8258's mask-ROM bootloader reading each bank's flag byte. That ROM isn't
  part of the dumped image, so its exact rules (for example, what it does if both flags are
  valid) can't be read from it. What the image shows matches Telink's documented multi-boot
  scheme, and register `0x80063e` reports the result.
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
  checksum, but not proven. Also still open: whether the OTA finalize code (located on the Sport at `0xe05c`; not yet
  checked for header reads beyond the flag byte), or a
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
(the bank addresses, header field layout, or any of the still-unresolved items above)
should be treated as a snapshot of one build, not a guaranteed-current spec, until independently
re-confirmed against whichever build a given device is actually running. The cleanest way to
re-verify: capture live BLE traffic during a real update rather than relying on static analysis
of a possibly-stale binary.

## Contributing

If you resolve any of the above (or find something new), a PR with the specific evidence (a live
capture, a decompiled function, a cross-reference in the app's own source) is very welcome —
these notes are meant to be a living reference, not a final word.
