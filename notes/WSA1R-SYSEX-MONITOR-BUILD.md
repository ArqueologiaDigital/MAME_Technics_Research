# The WSA1R SysEx debug monitor — build log

**Design: `HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md` §A5. Code: `tools/wsa1r-sysex-monitor/`.**
Authorised by Felipe 2026-09-14 ("implement the custom rom"), reversing that file's earlier
do-not-build decision.

Purpose: a bidirectional debug channel over MIDI, so µPD6383 probe microcode can be loaded and
its results read back as exact integers rather than inferred from audio. Decode coverage stands
at **1397 undecoded of 7273 pooled words (80.8 %)**, and this is the instrument meant to turn the
remaining ~321 distinct shapes into an automatable sweep.

---

## Status

| step | state |
|---|---|
| Toolchain — assemble TLCS-900 | ✅ `llvm-mc -triple=tlcs900` from the project's own backend |
| Target identified | ✅ `prom_a` = `qsigcwsa1ax.ic12`, CPU 1 (`tmp95c061`), mapped `0xF80000` |
| Free space found and verified | ✅ 2506 bytes of `0x0E` at `0xFBA236`, 2423 still spare |
| Hook point found | ✅ one 4-byte instruction at `0xFA586E` |
| Monitor written and assembled | ✅ 83 bytes, milestone 1 (IDENT), **zero RAM used** |
| Patcher with refusal gates | ✅ 4 gates, all passing |
| Cross-checked, second toolchain | ✅ MAME's own `unidasm` reads back the intended code |
| Patch live in the running machine | ✅ read out of CPU 1's address space by Lua |
| Patched ROM boots | ✅ `wsa1r` runs (expected WRONG CHECKSUMS notice) |
| **End-to-end over MIDI** | ⛔ **not yet** — needs a MIDI source, see below |
| Transmit-from-ISR safety | ⛔ unproven |

## What was built

**83 bytes**, milestone 1 only: `F0 7E 7D 01 F7` → `F0 7E 7D 7F 01 00 F7`.

The three findings that made it small and safe:

1. **A same-width hook.** `MIDI_RX_SysExData` (`0xFA586E`) is called for every data byte of an
   accepted SysEx. Its first four bytes `f0 a9 c9 66` become `jp 0xFBA246` — and `jp abs24` is
   exactly four bytes. The routine has one caller (`MIDI_RX_DataByte`, `0xFA576D`) and is only
   ever entered at its first byte, so nothing after the patch is reachable; the remaining original
   bytes stay in place as documentation. **Restoring the ROM is a four-byte write.**
2. **A free state bit.** `(0xA9)` is the firmware's SysEx state byte, and **bit 5 is tested by
   `MIDI_RX_SysExData` and set nowhere in the firmware** (`FINDINGS-midi-port.md`). Its lifecycle
   is exactly right: `MIDI_RX_SysExStart` does `ld (0xa9),0x01`, clearing it at every `F0`. The
   monitor uses it as "this message is mine", which also makes the firmware skip our bytes.
3. **A constant reply.** The IDENT response is a ROM table, so milestone 1 needs **no RAM
   allocation anywhere** — the only state is that one borrowed bit.

## Verification

* ★ **Two independent toolchains agree.** `llvm-mc` assembles it; MAME's own disassembler reads
  the patched image back as exactly the intended instructions, all four branch targets correct.
  The `call 0xf41e3c` inside the monitor is **byte-identical** to the ROM's own at `0xFA587D`,
  which is the strongest single check that the assembler and the machine agree.
* ★ **Live in the machine**, not merely on disk: `verify_in_emu.lua` reads `0xFA586E` =
  `1B 46 A2 FB`, `0xFBA246` = `F2 A9 00 00 C8`, and the reply table = `F0 7E 7D 7F 01 00 F7` out
  of CPU 1's own program space while the firmware runs.
* ⚠ The claim-path unit test initially failed on **my** error, not the monitor's: MAME exposes
  TLCS-900 registers **bank-qualified** (`XDE0`…`XDE3`), so `cpu.state["DE"]` is a nil index.
  Fixed by setting all four banks, since which is live depends on RFP.

## ⛔ The blocker that had to be fixed first, and it was not mine

`wsa1r` **segfaulted on every start** — `l7a1429_device`'s constructor, a `rep stos` running off
the object. It reproduced identically on the **stock** ROM, so the patch was never implicated
(the control was run before interpreting). Cause: `WSA1R_ENABLE_ACOUSTIC_HLE` changes
`sizeof(l7a1429_device)` from **8952 to 2112880** bytes, and MAME's build system does not treat
`-D` flags as a dependency, so two object files built days apart disagreed. Fixed, and made
self-diagnosing — see the ABI GUARD note in `acoustic_modeling.h` and commit `5b32b3a`.

⚠ Worth keeping in mind: an incremental tree will re-create this whenever the macro is toggled.
The guard now says so in words instead of crashing.

## Next, in order

1. **End-to-end over MIDI.** MAME's `midiin` image device either parses its argument as a
   Standard MIDI File or hands the name to the OSD MIDI layer as a live port. Both routes exist
   here: MAME enumerates ALSA's "Midi Through Port-0", and the host has `amidi`/`aconnect`.
   * a **`.mid` file** carrying the SysEx is deterministic and needs no daemon — best for
     automated regression.
   * a **live ALSA port** is how an external program talks to it interactively.
   * ⚠ **A PTY will not work for `midiin`**: MAME does support PTYs (`/dev/pts` prefix,
     `posixptty.cpp`), but `midiin_device::call_load` tries to *parse* its file as a Standard MIDI
     File before falling back to a named port, so a raw byte stream never reaches it. Raw PTY
     access would need the UART bridged to an rs232-style image instead — a driver change.
2. **Settle the transmit-from-ISR question.** Tap `0xF40ED4` and confirm the reply is queued and
   the machine survives. If it is not re-entrant, move the reply to a main-loop hook.
3. **Milestone 2**: a byte counter (needs RAM — none is allocated yet), then `LOAD`, `POKE`,
   `RUN`, `DUMP`, and the `RQ`/`GF` commands that §A5 argues could locate the chip's COND field
   and its GF-setting instruction.

⚠ Nothing here has been near the hardware, and nothing should be until step 1 passes.
