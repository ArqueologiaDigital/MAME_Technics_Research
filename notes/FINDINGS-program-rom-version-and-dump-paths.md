# KN7000 program-ROM: non-destructive revision identification & dump paths

Goal: the project owner holds a KN7000 whose main-program flash (IC16, `0x48400000`–`0x487FFFFF`) is an
**undocumented earlier revision** that should be archived **without desoldering** the part. This note
documents what the instrument's own firmware diagnostics can and cannot do toward that. Source:
4-agent RE workflow `wf_3074c3c8-fc0` (4/4, 0 errors) + inline verification. Companion to the
wave-ROM dump tutorial and `rom-dumping-roadmap`.

## TL;DR

- **Identify the revision non-destructively: SOLVED, trivially.** The firmware has a built-in
  **SOFTWARE VERSION** screen that prints `PROGRAM : NNNN` — a decimal build number read from a single
  `u16` at program-flash offset **`0x33660C`** (`cpu 0x4873660C`). In our reference image it reads
  **941** (`0x03AD`). The owner opens that screen and reads their revision number off the LCD. No
  tools, no risk. An earlier revision will show a *smaller* integer.
- **Dump the full CONTENTS via firmware alone: NOT POSSIBLE.** No diagnostic ever emits program-flash
  *bytes* to any capturable channel (MIDI/serial/disk) — the ROM device test reports only **OK/NG** on
  the LCD, and the firmware-update path is strictly **write-only** (disk→flash). There is no
  program-flash equivalent of the wave-bus read port. Full-content archival therefore needs **hardware**
  (an in-circuit clip read, non-destructive since reading doesn't modify the chip) **or** a
  code-execution route (get the CPU to run a small flash-reader that streams bytes out an observable
  port — the harder research path, separately tracked).

## 1. The SOFTWARE VERSION screen — the identification win

- Window `MpVW` / `IvMpVerWinProc` (`0x484887CB`); per-component boxes `AcProgVerBoxProc` (`0x48488897`),
  `AcTableVerBoxProc` (`0x484888FB`), `AcRhythmVerBoxProc` (`0x4848895F`), `AcAromVerBoxProc` (`0x48488A0B`).
- Each box prints a `%4d` decimal version number. Format strings (program flash):
  `PROGRAM : %4d` @`0x485D67E0`, `TABLE   : %4d` @`0x485D67F0`, `RHYTHM  : %4d` @`0x485D6800`,
  `PICTURE : %4d` @`0x485D6810`; header `--- SOFTWARE VERSION ---` @`0x485D5D9C`.
- The PROGRAM number is loaded `mov (0x4873660C),d0 ; movhu d0,(0x50007DC4)` and formatted via lib
  helper `0x4C001A48`. **Verified:** bytes at file `0x33660C` = `AD 03 00 00` → `u16 = 941`.
- `GetTtSoftverID` (`0x48488AAC`) is a separate 2-instruction stub that just returns the constant
  `0x00100000` (a format/API id, not the build number).
- **Archival use:** (a) the owner reads `PROGRAM : NNNN` off their unit to *name* the revision; (b) once
  their flash is dumped by any means, the same `u16` at the equivalent of `0x4873660C` re-identifies it.

## 2. §8.1 "ROM device test" — integrity only, no fingerprint

- `RomTestRunFunc` (`0x4849FDCF`, menu wrapper) → `MainRomTestFunc` (`0x4849FDF8`, gated `d1==0x1060000`).
- Program-flash sub-test `helperA` (`0x4849FC54`): sweeps **`0x48000000`–`0x487FFFFF`** (8 MB = table ROM
  + program flash, jointly) as two interleaved halfword streams (`movhu (a1),d0; inc4 a1; add d0,(acc)`),
  `0x200000` iterations, computing two 32-bit **additive** sums (low/high halfwords). No CRC.
- The pass is run **twice** and the two sums compared for **self-consistency** (does the flash read back
  identically?). The expected-value seed table at `0x4860C9A0/A8` is **all zeros** in this image, so it is
  *not* a golden-checksum compare — just a read-consistency check. Result is **OK/NG only**; the sums live
  on the stack and are discarded, never displayed or emitted.
- **Invoke:** hold **C#3 + D#3 + C#4** and power on; release at the service screen; PAGE to
  *"8.1 ROM device test"*; press **EXECUTE**. OK/NG in ~20 s. (Service §8, confirmed on the MN10300
  sibling KN2400/2600; same firmware family. Screen widgets: `PROGRAM ROM: IC16 =`, `RHYTHM ROM: IC18 =`,
  `CUSTOM FLASH: IC21 =`, `PICTURE ROM: IC19 =`, `EXECUTE` near `0x48609728`.)
- **Archival use:** confirms the owner's flash reads back cleanly (integrity), but **cannot fingerprint a
  revision** — no number is shown. However the algorithm is now fully specified, so a unique fingerprint
  can be computed **offline** from any dump: two 32-bit additive halfword sums over `0x48000000`–`0x487FFFFF`.

## 3. §8.12 "WAVE EXPANSION BOARD test" — not program flash

`BoardRomTestRunFunc` (`0x484A401E`) checksums the optional SY-EW SOUND-RAM expansion windows
(`0x57/0x56/0x41` buses), OK/NG on LCD. Irrelevant to program-flash archival; documented for completeness.

## 4. Byte-readout verdict — no firmware-mediated dump

Decisive negative: **no** KN7000 main-CPU diagnostic streams program-flash bytes to MIDI SysEx, a serial
port, or disk. The ROM test emits UI OK/NG events only; the firmware-update path is write-only
(disk→flash via the `.AST`/flash-program chain, `FlashProgram128Words 0x4847F9F7`), with no read-back to
file. There is no CPU-observable program-flash read port analogous to the TG wave-read port. So the
firmware can **identify** the revision but not **reproduce** it.

## What this means for archiving the owner's unit

1. **Now (zero risk):** photograph the SOFTWARE VERSION screen (`PROGRAM : NNNN`) and record the §8.1
   OK/NG. That *names and integrity-checks* the revision immediately.
2. **Full contents (pick one):**
   - **In-circuit clip read of IC16** with the CPU held in reset — non-destructive (reading doesn't
     modify the chip; this avoids the desolder/corruption risk that motivated the whole question). Most
     pragmatic path; see `rom-dumping-roadmap`.
   - **Code-execution dumper** — the only *firmware-only* route to full contents (a small CPU-run
     reader streaming flash out an observable port). Tracked separately; uncertain, since no proven
     memory-corruption→PC path exists yet.
3. Once dumped by any route, compute the §8.1 additive-sum fingerprint and read the `0x33660C` version
   cell to cross-check identity.

*Provenance: workflow `wf_3074c3c8-fc0`, neutral preservation-RE framing (0 safeguard blocks). Version
cell value (941) and format strings verified inline.*
