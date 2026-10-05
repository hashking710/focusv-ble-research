[← README](../README.md) · **BLE Protocol** · [Firmware Architecture](firmware-architecture.md) · [Methodology](methodology.md) · [Hardware Setup](hardware-setup.md) · [Open Questions](open-questions.md)

# BLE Protocol Reference

Reverse-engineered from the official Focus V web app (a React Native / Expo web export served
at `focusv.app`, which the iOS/Android apps also wrap — so this is the same code path across
platforms, not a third-party reimplementation). No source maps are published, so everything
here comes from reading the shipped, minified app logic directly, cross-checked wherever
possible against live captures from real hardware.

Applies to the **Quantum / Aeris / Sport** device family, which are protocol-identical (same
GATT services, same characteristics, same opcodes throughout). Retail naming differs from the
internal device-type strings the app uses:

| Internal type | Retail name |
|---|---|
| `QUANTUM` | Carta 2 |
| `SPORT` | Carta Sport |
| `AERIS` | Aeris |
| `CARTA` | Carta / Carta Classic (legacy, separate protocol — see below) |

Quantum/Aeris/Sport share identical services, characteristics, and opcodes, but **the model
can still be read over BLE**. The official app reads a model code from the standard User Data
service (`0x181C`), characteristic `0x2A90`, on every connect, and buckets it by prefix:
`D9*` = Quantum (Carta 2), `E5*` = Aeris, `S3*` = Sport. The serial number is in `0x2A8A` of the
same service. `user_data` has to be listed in Web Bluetooth's `optionalServices` to reach it.
(An earlier version of this document said this was impossible. That conclusion came from
checking only Device Information's `0x2A24`, which the app never reads.)

The legacy `CARTA` bucket is a **different, older protocol** (see the OTA section below for one
concrete difference) and is not covered in detail here — modern "Carta 2" hardware speaks the
Quantum/Aeris/Sport protocol, not this legacy one.

## Transport

- Desktop/mobile web client: `navigator.bluetooth` (Web Bluetooth).
- Native mobile apps: presumably a native BLE stack (e.g. `react-native-ble-plx`) speaking the
  same GATT services — the underlying protocol constants are shared, not web-specific.
- Web Bluetooth capture via `chrome://bluetooth-internals` works against the real web app in
  Chrome/Edge (desktop or Android) with zero setup — since the web client *is* the official app,
  this captures the real protocol live, not an approximation.

## GATT map

```
Custom command service:      1011123E-8535-B5A0-7140-A304D2495CB7
  read/notify characteristic: 1011123E-8535-B5A0-7140-A304D2495CB8
  write characteristic:       1011123E-8535-B5A0-7140-A304D2495CB9

OTA (firmware) service:      00010203-0405-0607-0809-0A0B0C0D1912
  OTA write characteristic:   00010203-0405-0607-0809-0A0B0C0D2B12
  (read + write-without-response only — no notify/indicate, confirmed via live
  GATT enumeration on real hardware)

Standard BLE services also used:
  Generic Access   (0x1800) -> Device Name        (0x2A00)
  Device Info      (0x180A) -> Model Number        (0x2A24)
                             -> Serial Number       (0x2A25)
                             -> Hardware Revision   (0x2A27)
                             -> Software Revision   (0x2A28)
                             -> Manufacturer Name   (0x2A29)
  Battery Service  (0x180F) -> Battery Level        (0x2A19)  (defined but unused — see below)
```

The custom command service/characteristic UUIDs are identical across Carta/Quantum/Aeris/Sport
— devices are told apart by advertised name (`CARTA`) or by scanning for the custom service UUID
and reading the model/serial from Device Information.

**Model code → device family**, read from Device Information's Serial/Model fields:

| Model code prefix | Family |
|---|---|
| `D9BL`, `D9CL`, `D9MI`, `D9GR`, `D9FO`, `D9MN`, `D9BO`, `D9OE` | Quantum |
| `E5*` | Aeris |
| `S3*` | Sport |

### Connection flow

1. `requestDevice` — filter on name `CARTA`, or on the custom service UUID for
   Quantum/Aeris/Sport.
2. `gatt.connect()`, get the primary custom service, get both characteristics.
3. For Quantum/Aeris/Sport: also fetch `device_information`, `battery_service`, `user_data`.
4. Subscribe to notifications on the read characteristic.
5. **Send a date/time write early and just listen** — the device responds to any date/time write
   with a full state dump (atomizer resistance, live telemetry, all four preset-table sync
   packets, all five LED preset acks, a timeout-ack reading, and a screensaver-status packet).
   This is the cheapest way to get a full snapshot of device state rather than querying each
   piece individually.

### Feature availability differs by device type

Even though the protocol is identical, the app's own UI gates two features by device type:

- **Screensaver is Quantum-only.** Aeris and Sport don't expose the screensaver menu at all —
  most likely a hardware difference (display capability), not an app-side restriction.
- **The 30-minute device/LED timeout option is Quantum-only.** Aeris/Sport cap out at 15 minutes
  for both timeouts.
- **Device lock is Quantum-only** (main-screen "device control" row).

Everything else (LED presets, vibration, Low Power Mode, general settings) is shared across all
three. Recalibration, the manual atomizer override and the live PID dialog are gated on the app's
build profile (`appBuildType === 0`, internal builds), so the public app never shows them.

## Packet framing

No checksum or CRC. Framing is purely positional: `byte[0]` is the opcode, `byte[1]` is usually
a length/type tag, and the **last byte of the packet mirrors byte[0]** as a simple sentinel — not
a real integrity check. Multi-byte numeric fields are **big-endian** (`value = 256*hi + lo`)
unless noted otherwise.

## Write commands (app → device)

| Opcode | Len | Purpose | Layout |
|---|---|---|---|
| `0xCC` | 16 | Set temp/session and **start heating** | `[CC,10, flowerTempHi,Lo, concTempHi,Lo, scaleFlag, flowerDurHi,Lo, concDurHi,Lo, flowerRank, concRank, marker, 00, CC]`. Whichever mode you're setting gets its real target; the *other* mode's position must be echoed with its current live value (from the `0x99` state packet) or you'll clobber it. `scaleFlag`: `0x11`=°F, `0x22`=°C. `marker=0xA5` **starts heating** (confirmed live — this is a genuine remote-start capability, not gated behind a physical button). |
| `0xCC` | 16 | Extend an active session (~10s) | Same shape, `marker = (0x66, 0x0A)` two-byte pair. |
| `0xCC` | 16 | Cancel / stop an active session | Same shape, `marker = 0xAF`. |
| `0xCC` | 16 | Test-fire / short preview | Same shape, `marker = (0x66, 0x0A)`. |
| `0xCC` | 16 | *Custom firmware only, beta* — save ramp waypoint 1-5 | Same shape, `marker ∈ {0xB1..0xB5}`. No-op (unrecognized) on stock firmware. See [Firmware Architecture](firmware-architecture.md#custom-firmware-device-native-hardware-ramp-beta). |
| `0xCC` | 16 | *Custom firmware only, beta* — arm the device-native ramp | Same shape as the normal start row above, `marker = 0xA5`, but with a fixed sentinel temperature (150°F) in place of a real target. Behaves as an ordinary (if unreachable) start command on stock firmware. |
| `0xCC` | 16 | *Custom firmware only, beta* — set the built-in preset offset | Same shape, `marker = 0xBB`, with the offset (signed, −10 to +15 °F) in byte 14. Byte 14 is never read by the stock `0xCC` handler on any of the three devices, and the custom slot, durations and preset ranks are written back unchanged. No-op on stock firmware. |
| `0x77` | 12 | Pre-OTA date/time set (distinct from `0xDD`'s date/time write) | `[77,0C, yearHi,Lo, month, day, hour, minute, 0,0,0, 77]` |
| `0xDD` | 12 | Set date/time (also triggers a full state-dump response — see Connection flow) | `[DD,0C, yearHi,Lo, month, day, hour, min, 00,00,00, DD]` |
| `0x11` | 12 | Apply device settings / session sync / power off | See full breakdown below |
| `0xD1` | 7 | Device/LED timeout | `[D1,07, ledHi,Lo, deviceHi,Lo, D1]` — **LED timeout first**, device timeout second, in seconds (official choices 60/300/600/900, plus 1800 on Quantum) |
| `0xDE` | 4 | Manual atomizer-type override (internal-only menu in the official app) | `[DE,04, code, DE]` — 0 = auto-detect, 160 = flower, 96/80 = concentrate (old), 64 = concentrate (new). Current override is reported by the `0xDF` notify. |
| `0x88` | 19 | Save flower session-preset table (5 slots) | See "Session presets" below |
| `0x66` | 19 | Save concentrate session-preset table (5 slots) | Same shape, concentrate side |
| `0xEE`/`0xE1`/`0xE2`/`0xE3`/`0xE4` | 20 | Save LED preset, ranks 1-5 | See "LED presets" below |
| `0x83` | 6 | Erase screensaver | `[83,06, slot, 00,00, 83]` — slot: 1=primary, 2=secondary, 3=both |
| `0x80` | 6 | Save/select screensaver slot metadata (not the image transfer itself) | `[80,06, a, b, c, 80]` — 3 params, exact roles unconfirmed |
| `0xFA` | 7 | Session-log **request** | `[FA,07, startHi,Lo, endHi,Lo, FA]` — asks for records start..end (1-based; end = lifetime flower + concentrate count from `0xAA`). Answered by `0xFC`/`0xFF` notifies. |
| `0xFD` | 7 | Session-log "mark as read" | Same shape as `0xFA` — sent by the official app after it has stored the records server-side |
| `0xAE` | 4 | **Device-specific — see below** | `[AE,04,AE,AE]` — confirmed working on real hardware |
| `0xAC` (hidden, not sent by the official app) | var | Stage a custom Bluetooth name (Aeris/Sport) | `[AC, n, name...]` — up to 17 chars; stages only, applies nothing until `0xAF` |
| `0xAF` (hidden, not sent by the official app) | var | Apply the staged Bluetooth name (Aeris/Sport) | `[AF, n, name...]` — up to 12 more chars (29 total); applies via the device's own BLE stack, doesn't disconnect |
| `0xCD` | 6 | Request calibration status | `[CD,06,DD,00,00,CD]` — response via `0xC2` notify (not consistently observed to fire from a bare status query — see [Open Questions](open-questions.md)) |
| `0xC1` | 6 | Trigger recalibration (overwrites factory calibration data) | `[C1,06,77,00,00,C1]` — device must be below 120°F/48°C first (checked client-side) |
| `0x81` | 6 | Screensaver status refresh query | `[81,06,44,00,00,81]` — answered by the `0x82` notify |
| `0x72`/`0x74`/`0x76` | var | Screensaver image transfer (shared transport with legacy-OTA-style framing, **not** real firmware OTA — see below) | See "Screensaver image transfer" below |

Real firmware OTA is a **separate wire protocol** entirely — see its own section below. Do not
experiment with the OTA characteristic casually; malformed writes risk corrupting the device's
flash.

### `0xAE` is not the same command on every device

`[AE,04,AE,AE]` does something genuinely different depending on the device — confirmed by firmware
decompile on all three, not just inferred from behavior:

- **Carta 2**: a real, confirmed **factory reset**. Rewrites the flower/concentrate preset tables
  (custom slot + 5 ranked slots, both °F and °C, plus durations) back to their firmware-default
  values, then runs further reset routines (presumed LED/screensaver/flash-save, not individually
  traced). This is the device this project actually recovered using `0xAE`, live, after a
  screensaver-related incident.
- **Aeris / Carta Sport**: restores the device's **advertised Bluetooth name** to its hardcoded
  default ("AERIS" / "CARTA SPORT") and deliberately disconnects — it is **not** a factory reset on
  these two devices, despite `0xAE` initially appearing to power off a Sport during early testing.
  That observation is now fully explained: the deliberate disconnect looked like a power-off from
  the outside.

On Aeris/Sport, `0xAC` (stage a name) and `0xAF` (apply the staged name — a completely different
context from the `0xAF` *marker byte* used inside `0xCC` session-stop packets, see above) are the
real custom-rename mechanism; `0xAE` is specifically the "restore factory default name" case of the
same underlying feature, not a separate reset path. Applying a name (`0xAF`) or restoring the
default (`0xAE`) both arm the same deferred-settings-save mechanism used for ordinary settings
persistence (~5 second delay) — staging a name with `0xAC` alone does not.

Carta 2's factory-reset default values, confirmed from the real `PROD-111224` decompile (matches
live-captured values):

| | Custom | Slots 1-5 |
|---|---|---|
| Flower °F | 330 | 340, 350, 370, 390, 410 |
| Flower °C | 166 | 171, 177, 188, 199, 210 |
| Concentrate °F | 475 | 480, 495, 515, 535, 565 |
| Concentrate °C | 246 | 248, 257, 268, 279, 296 |
| Flower duration (s) | 240 | 240 ×5 |
| Concentrate duration (s) | 60 | 60, 55, 50, 45, 40 |

### `0x11` — settings apply / session sync / power off (full breakdown)

```
byte 0:  0x11              opcode
byte 1:  0x0C (12)         length
byte 2:  sub-command:      0x00 = normal apply/keep-alive, 0xAF = POWER OFF
byte 3:  temperature scale: 0x11 = °F, 0x22 = °C
byte 4:  derived LPM code: 0x02 = Low Power Mode on, 0x08 = off (redundant re-encoding of byte 10)
byte 5:  flower session-preset ranking (0-5, 0 = custom/typed value)
byte 6:  concentrate session-preset ranking
byte 7:  LED preset ranking (1-5)
byte 8:  unknown flag, always echoed unchanged — never observed as the field actually written
byte 9:  Vibration Level (0-10)
byte 10: Low Power Mode flag (0/1)
byte 11: 0x11              footer
```

### LED presets — full color format

Editing a preset's colors (distinct from selecting one by rank, which is `0x11` byte[7]) uses a
dedicated 20-byte command, one opcode per rank slot:

```
rank 1: write 0xEE, ack/readback 0xEA
rank 2: write 0xE1, ack/readback 0xE9
rank 3: write 0xE2, ack/readback 0xE8
rank 4: write 0xE3, ack/readback 0xE7
rank 5: write 0xE4, ack/readback 0xE6
```

Payload: `[opcode, 0x14(20), S, P, R1,G1,B1, R2,G2,B2, R3,G3,B3, R4,G4,B4, R5,G5,B5, opcode]`

- `S`: hi nibble = Glass Top Brightness (0-15), lo nibble = Base Brightness (0-15).
- `P`: hi nibble = Pattern (1-5: `Rotate`, `Fade Out`, `Disco`, `Blink`, `Static`), lo nibble =
  Pattern Speed (0-15).
- Five `R,G,B` triplets — a preset is a 5-color sequence (can be a gradient or five identical
  triplets for a flat color), not a single color.

There is **no BLE read path for saved LED preset contents** — the official app's own "current
settings" view is just what it remembers sending this session, not a device readback. The
20-byte save-ack (`0xEA`/etc.) is the only genuinely device-sourced confirmation, and it's a full
echo of the saved preset.

### Session presets — 5-slot temp/duration table

Write, 19 bytes, opcode `0x88` (flower) or `0x66` (concentrate):
```
[opcode, 0x13(19), slot1(3B), slot2(3B), slot3(3B), slot4(3B), slot5(3B), scale, opcode]
```
Read-side sync packets (`0x55`/`0x33`/`0x44`/`0x22`, 18 bytes) use the same 3-byte-per-slot
layout:
```
per-slot: [tempHi, tempLo, durationSeconds]     temp = 256×tempHi + tempLo
```
Editing one slot re-sends all 5 with only the target slot's 3 bytes changed.

### The `0x99` state/handshake packet

The device's full live-state broadcast, sent continuously (also the first packet on connect,
used to detect flower-vs-concentrate). 20 bytes:

```
byte 0:  0x99                     opcode
byte 1:  0x14 (20)                length
byte 2:  atomizer/session state:  0xA0=flower/current, 0x60/0x50=concentrate/old,
                                    0x40=concentrate/new, 0x30=concentrate/max, 0x00=none
                                    (the atomizer *generation* — 'old' atomizers are open-loop
                                    and don't report TCR/PID telemetry at all; 'new'/'max' do)
byte 3:  temperature scale:       0x11=°F, 0x22=°C
byte 4:  packed nibble pair:      hi = active flower preset ranking (0-5), lo = concentrate.
                                    With a rank of 1-5, the device heats to that slot of the
                                    preset table; bytes 8-11/14-15 only apply at rank 0.
byte 5:  seconds remaining in the running session (0 = idle) — the official app shows it as
                                    its m:ss countdown
byte 6-7:  live measured temperature, in the device's current display unit — no conversion
                                    needed. Confirmed via a real capture: idle baseline ~78,
                                    climbed smoothly to a commanded 510°F target, held there,
                                    then declined during cooldown.
byte 8-9:  16-bit — flower set-temperature (custom-value role, used when ranking = 0)
byte 10-11: 16-bit — concentrate set-temperature (same role, concentrate side)
byte 12: Battery Level, 0-100 (%)
byte 13: packed nibble pair — hi = active LED preset ranking (1-5, 0=none), lo = Screen
                                    Brightness (0-15, raw hex digit)
byte 14: flower duration (custom-value companion to byte 8-9)
byte 15: concentrate duration (custom-value companion to byte 10-11)
byte 16: packed nibble pair — hi = Device Locked flag, lo = Charging flag (0/1)
byte 17: packed nibble pair — hi = Vibration Level (0-10, allows hex digit 'A' as literal 10),
                                    lo = Low Power Mode flag
byte 18: seconds until sleep/auto-off, scaled: real seconds = 2.5 × byte[18] (truncated)
byte 19: 0x99                     footer
```

### Screensaver image transfer

Distinct from firmware OTA, but shares the `0x72`/`0x74`/`0x76` opcodes and the **normal**
write characteristic (not the OTA characteristic).

1. **Prepare the image**: crop/resize to exactly 240×240, convert to raw RGB565 pixel data.
2. **Start the transfer session** — `0x72`. Current-generation firmware (software revision date
   ≥ 2022-11-26) uses the 5-byte form `[72,05,11,slot,72]`; older firmware uses a 4-byte form
   `[72,04,11,72]` with no slot byte.
3. **Wait for the `0x73` session-ready ack** — `[0x73,0x04,0x22,0x73]` — before sending any
   blocks. This is required, not optional: sending blocks before the device confirms it has
   entered receive mode gets them silently dropped. On real hardware this ack took **~5 seconds**
   to arrive (plausibly a flash-sector erase happening before the device is ready) — a client
   should allow a generous margin (15s+) and treat a timeout as a hard failure, not a "proceed
   anyway."
4. **Stream the image, 16 bytes at a time** — `0x74`, `[74, dataLen+3, blockIndexHi, blockIndexLo,
   ...16 data bytes]`. **No additional flow-control ack was observed on real hardware** despite
   a plausible-looking `0x75` "page-write ack" opcode existing in the app's source — waiting for
   it made transfers ~15x slower and did not appear anywhere in a live capture. A uniform,
   moderate per-block delay (the app itself paces sends, not a tight loop) is the
   confirmed-working approach.
5. **Finish/verify** — `0x76`, `[76,04,44,76]`, sent once the last block completes.
6. **Status refresh** — `0x81` → `0x82` notify, ~250ms after the transfer session resets.

The device does **not** report transfer-validation failures over BLE — a corrupted or
malformed transfer can complete with no protocol-level error, while silently discarding the
result. Always verify via a follow-up `0x82` status read rather than trusting that the write
promises resolving means the device accepted the data. If a device ends up in a bad state after
an experimental transfer, `0xAE` (factory reset) is a confirmed, real recovery path — a power
cycle alone will not necessarily clear app-visible confusion caused by a bad transfer.

### Real firmware OTA — a completely separate protocol

**This is not the same mechanism as the screensaver transfer above**, despite superficially
sharing some opcode values. Real firmware updates use:

- A **separate GATT characteristic** — the OTA write characteristic (`...2B12`) under its own
  service, not the normal command characteristic.
- The update binary's header is validated client-side before any transfer starts: bytes at hex
  offset 8-11 of the file must read ASCII `KNLT` (this is the same 40-byte custom header
  described in [Firmware Architecture](firmware-architecture.md)).
- **Sequence**:
  1. Set date/time over the *normal* characteristic (`0x77`, see write table above).
  2. Wait ~350ms.
  3. Over the OTA characteristic: `[0x00, 0xFF]` — session start/erase trigger. No
     `[opcode,len,...,opcode]` framing — this sub-protocol is raw.
  4. Over the OTA characteristic: `[0x01, 0xFF]` — begin transfer.
  5. Per-block loop: each block is **20 raw bytes** — 2-byte block index (byte-swapped) + 16
     data bytes + 2-byte CRC16 (byte-swapped). The CRC16 is the standard reflected poly-`0xA001`
     algorithm (CRC-16/ARC family), seeded `0xFFFF`, computed over the 18 bytes [index + data].
     No opcode byte prefixes a block — the index is the only framing.
  6. Progress ping over the **normal** characteristic, every 8 blocks (firmware built on/after
     2023-11-04 only): `[0xA4, 0x04, percent, 0xA4]`.
  7. Finish, over the **OTA characteristic**: 6 raw bytes — `[0x02, 0xFF, lastIndexLo,
     lastIndexHi, (~lastIndex & 0xFFFF)Lo, (~lastIndex & 0xFFFF)Hi]` (final index plus its
     bitwise complement as an integrity check). This is a **different** finish packet from the
     screensaver's `0x76` — do not conflate the two.

The OTA characteristic itself has **no notify/indicate capability** (confirmed via live GATT
enumeration) — a client gets zero feedback on this channel; the only signal is the progress ping
on the normal characteristic. Getting the CRC polynomial, seed, or byte order wrong here risks
the device rejecting or misinterpreting the transfer — see
[Firmware Architecture](firmware-architecture.md) for what happens on the device side, and
[Open Questions](open-questions.md) for what's still unconfirmed about this path.

**This is one mechanism, not two** — it writes whatever file it's given, starting at the device's
fixed base address, with no notion of "this is a patch" vs "this is a stock image." Reverting a
device (pushing the original stock file back over a currently-patched one) goes through this exact
same code, the exact same checks, with no size comparison against what's currently installed
anywhere in the path (confirmed independently on all three devices — see
[Firmware Architecture](firmware-architecture.md)).
[`tools/ota-flash.html`](../tools/ota-flash.html) in this repo is a standalone implementation of
this sequence for exactly that purpose: push either direction, from any machine, without the main
app. Keep whatever stock file you started from — it's the revert path.

**Legacy Carta devices use a genuinely different, ASCII-hex-based OTA sub-protocol** (each 32-byte
firmware chunk becomes an ASCII hex string with a checksum suffix, sent as UTF-8 text) — not
covered in detail here since modern hardware doesn't use it.

## Notify/read packets (device → app)

| Opcode | Frame | Meaning |
|---|---|---|
| `0xAA` | len 19 | Dab counters, eight 16-bit fields: `byte[2-3]`/`[4-5]` = lifetime flower/concentrate sessions, then today, week, month (flower first each time). Fires during the connect-time sync burst, not continuously. |
| `0xFC` | len 18 | One session-log record: `[FC, len, idx(2), count(2), atomizer\|preset, year(2), month, day, hour, minute, durationSec, temp(2), unit, FC]` — atomizer hi nibble `A` = flower, `3`–`6` = concentrate; lo nibble = preset slot (0 = custom); unit `0x11`=°F / `0x22`=°C |
| `0xFF` | len 6 | Session-log placeholder for an index the device no longer has: `[FF, len, idxHi, idxLo, FF, FF]` |
| `0xDF` | len 4 | Current manual atomizer override (`byte[2]` uses the same codes as `0xDE`) |
| `0xBB` | len 10 | Status/ack |
| `0x99` | len 20 | Device/session state — see full breakdown above |
| `0x55` | — | Preset-table sync, flower, °F |
| `0x33` | — | Preset-table sync, concentrate, °F |
| `0x44` | — | Preset-table sync, flower, °C |
| `0x22` | — | Preset-table sync, concentrate, °C |
| `0xEA`/`0xE9`/`0xE8`/`0xE7`/`0xE6` | len 20 | LED-preset-save acknowledgment, ranks 1-5 — a full echo of the saved preset, not a bare ack |
| `0xDD` | var | Session-log streaming — `byte[1]` nonzero = raw log chunk; zero = live per-sample telemetry record (see breakdown below) |
| `0xCE` | len 7 | Live atomizer resistance — `byte[2-3]` = flower ohms, `byte[4-5]` = concentrate ohms |
| `0x82` | len 8 | Screensaver settings/status — `byte[2]`/`byte[3]` = current Order/Time settings, `byte[5]`/`byte[6]` = slot 1/slot 2 "has a screensaver saved" flags (0/1), `byte[4]` unmapped |
| `0xD2` | len 7 | Ack/readback for `0xD1`, same field order (LED timeout, then device timeout) — confirmed to echo exactly what was just sent |
| `0xC2` | len 8 | Response to `0xCD`/`0xC1` (calibration) — `byte[2]` = success flag, `byte[3-4]`/`byte[5-6]` = flower/concentrate ohms |
| `0x73` | len 4 | Screensaver transfer session-ready ack (see transfer sequence above) |

### `0xDD` per-sample telemetry record (when `byte[1] == 0`)

```
byte 3-4:   16-bit — NTC (thermistor) temperature, °C native
byte 5-6:   16-bit — TCR-derived temperature (only meaningful for 'new'/'max' atomizers)
byte 7-8:   16-bit — live Power Output (raw)
byte 9-10:  16-bit — live PID "Kt" gain (raw, unscaled)
byte 11-12: 16-bit ÷100 — live PID "Kp" gain
byte 13-14: 16-bit ÷100 — live PID "Ki" gain
byte 15-16: 16-bit ÷100 — live PID "Kd" gain
```

This is a real-time telemetry stream, not a one-shot summary — it fires repeatedly throughout a
session. Whether the device is running closed-loop PID at all is itself reported: 'old'
(legacy) atomizers run without PID or TCR sensing at all ("Legacy Mode").

## Confirmed temperature/duration limits, per device and mode

| Device | Flower °F | Flower °C | Concentrate °F | Concentrate °C | Flower duration (s) | Concentrate duration (s) |
|---|---|---|---|---|---|---|
| Quantum | 275-500 | 145-260 | 365-635 | 185-335 | 120-240 | 20-120 |
| Sport | 275-500 | 145-260 | 365-635 | 185-335 | 120-240 | 20-120 |
| Aeris | 275-500 | 145-260 | 365-600 | 185-315 | 120-240 | 20-60 |

These are the limits the official app's temperature steppers actually clamp to (main screen and
preset editor alike). Its exported `*AtomizerMin/MaxFlowerTemp` constants (300/460 °F) are only
the starting value when nothing is selected, and an earlier version of this table used them by
mistake. The °C limits are separate literals in the app, not conversions of the °F ones.

## Recommended build order for a client

1. Connect + read device info (standard GATT only) — validates your BLE stack works at all.
2. Read live telemetry (`0xAA` / `0x99`) — read-only, safe.
3. Set temperature / stop session / power off (`0xCC`/`0x11`) — the core interactive loop.
4. Device settings (`0x11`, `0xD1`).
5. LED presets.
6. Session presets and session-log retrieval.
7. Screensaver (image upload path is more involved — see above).
8. Recalibration — low payoff for a personal client, skip unless specifically needed.
9. Firmware OTA — don't implement unless deliberately building an updater; highest risk of
   anything in this document.

## Known gaps

- `0x82`'s `byte[4]` — setter confirmed, but no UI reference found to say what it drives.
- `0xCD` (calibration status query) has not been reliably observed to produce an `0xC2`
  response from a bare query alone — may require `0xC1` (the actual recalibration trigger) to
  have run first, or some other precondition.
- `0x80`'s exact 3 parameters (screensaver slot-select metadata) remain unconfirmed.
- Whether a bare `0xFA` session-log request (without the official app's follow-up `0xFD`) is
  enough on its own for the device to stream `0xFC` records. That's how the official app's code
  reads, but it hasn't been confirmed live.
