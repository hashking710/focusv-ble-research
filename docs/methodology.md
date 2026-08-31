[← README](../README.md) · [BLE Protocol](ble-protocol.md) · [Firmware Architecture](firmware-architecture.md) · **Methodology** · [Open Questions](open-questions.md)

# Methodology

How this research was done, and specific tooling gotchas worth knowing before repeating any of
it — particularly the Ghidra/Telink TC32 setup, which has a couple of non-obvious traps.

## Toolchain setup

1. **Ghidra** with the community [`Telink_TC32` processor module](https://github.com/rgov/Ghidra_TELink_TC32)
   (fixes pulled from [trust1995's fork](https://github.com/trust1995/Ghidra_TELink_TC32)). No
   prebuilt `.sla` ships with the module — compile the SLEIGH spec locally via
   `support/sleigh.bat` (or the equivalent shell script) before it'll load.
2. **Headless import** of the stripped binary (40-byte custom header removed — see
   [Firmware Architecture](firmware-architecture.md)) as raw binary, language
   `Telink_TC32:LE:16:default`, full auto-analysis.
3. **Independently validate the disassembler**, don't trust a community module blindly: build a
   real `tc32-elf-as`/`objdump`/`ld`/`objcopy` toolchain (a disposable Linux container works well
   if the Windows-hosted mirror is unstable) and do a full assemble→link→extract→disassemble
   round-trip on a known input to confirm the assembler produces correct TC32 machine code. Then
   cross-check the real firmware's disassembly between the two toolchains — they should match
   byte-for-byte at every point checked. This is what makes every address/behavior claim in the
   other docs trustworthy rather than a single-tool guess.
4. **[GhidraMCP](https://github.com/LaurieWired/GhidraMCP)** (plugin + Python MCP bridge)
   connects an AI coding assistant directly to a running Ghidra CodeBrowser session, giving
   programmatic access to the decompiler — this is what makes functions past the entry
   dispatcher actually tractable to work through quickly. If the plugin's default port conflicts
   with something else already running locally, it's configurable via
   `Edit → Tool Options → GhidraMCP HTTP Server`.

## Gotcha: named registers are not trustworthy for this processor module

The community `Telink_TC32` module's register/symbol map (`Telink_TC32.pspec`) is a **verbatim TI
MSP430 special-function-register map** — `IE1`, `IFG1`, `DCOCTL`, `WDTCTL`, `TACTL`, and so on,
addresses included. This is a completely different chip family from Telink TC32. The module was
clearly built to get *instruction decoding* right (independently verified via the toolchain
cross-check above, and that remains solid) but the peripheral/register *naming* is leftover
MSP430 boilerplate that was never replaced.

**Practical effect**: any named register Ghidra shows in decompiled output is not a real Telink
special-function register — it's an MSP430 name coincidentally sitting at whatever address, and
should not be used to infer what hardware peripheral is actually being touched. This doesn't
undermine conclusions based on runtime behavior/call patterns rather than register names, but it
rules out "search by named ADC/Timer register" as a strategy, and is a reason for general caution
about trusting any Ghidra-suggested peripheral identification on this module without independent
confirmation.

## Gotcha: Ghidra's auto-analysis leaves valid code unclaimed by any function

Large stretches of already-valid, reachable code can be left **unwrapped in any `Function`
object** by auto-analysis, even though the bytes disassemble correctly. `get_function_by_address`
/ `decompile_function_by_address`-style calls return "no function found" for these, because they
only see committed `Function` records, not raw disassembly.

Two things that make this confusing before you know to look for it:

1. A location Ghidra has typed as *data* (e.g. shown as a float value in the data inspector)
   silently blocks `Create Function` until you `Clear Code Bytes` first, then `Disassemble`, then
   `Create Function` — in that order.
2. Ghidra's Decompile panel will show a plausible-looking `UndefinedFunction_<addr>` result for
   **any** cursor position with disassembled code under it, even with zero `Function` object
   committed — this is an ad-hoc preview, not proof `Create Function` succeeded. The real
   confirmation is the colored function-signature banner appearing directly above the line in the
   **Listing** view.

The fix, one address at a time: `Clear Code Bytes` → `Disassemble` → `Create Function`. This
turns "no function found" into a real, cleanly decompilable function. When a chain of addresses
all resolve to what looks like "the same giant merged blob" no matter which one you start from,
that's often this issue rather than genuinely tangled logic — worth checking before concluding a
region "doesn't decompose into separate functions."

## General approach

- **Prefer ground truth over inference wherever possible.** Locating the actual hardware reset
  vector and tracing forward from there is more reliable than following calls backward from a
  BLE-write dispatcher and hoping to eventually reach unrelated subsystems (like a control loop)
  that may not be reachable that way at all.
- **Cross-validate app-side and firmware-side findings against each other.** Several protocol
  details (packet field layouts, a checksum algorithm, a magic-header offset) were confirmed by
  matching a firmware-side finding against the exact packet-assembly code in the app's own
  JavaScript, rather than trusting either side alone.
- **Live hardware testing resolves what static analysis can't.** Some behavior (exact ack
  timing, whether a documented code path actually fires for a specific real operation, physical
  button-gesture detection) is not reliably determinable from static analysis alone — a
  BLE capture tool (`chrome://bluetooth-internals` against the real web app is enough for most
  of this, since the web client *is* the official app) resolves these quickly and is worth
  reaching for rather than continuing to guess from source.
- **Retract cleanly when a working theory turns out wrong.** Several early theories in this
  research (an open-loop heating model, a "dual-bank OTA" address pair that turned out to be
  screensaver storage, a suspected button-input source that turned out to be a tick counter) were
  wrong and later corrected. Recording *why* a theory was wrong, not just deleting it, kept the
  research from re-chasing the same dead end twice.
