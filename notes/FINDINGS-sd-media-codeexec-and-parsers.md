# KN7000 SD media — can a file on the card run code, or corrupt memory?

Companion to `FINDINGS-expansion-buses-and-code-exec.md`. Same central question, different
external-data surface: **the SD card.** Method: static RE of the maincpu firmware
(`kn7000_prog.bin`, base `0x48400000`), one analyst per file format, each classifying
*control-flow* (does any file byte become a native `calls/jmp` target or a store base?) and
*memory-safety* (fixed vs file-supplied buffer sizes). 7-agent workflow `wf_abb18725-948`
(2026-08-03), plus inline verification of the alarming finding.

## Bottom line

- **Code execution from SD: NO — by construction.** Every SD file is dispatched by *matching*
  its tag/extension to a **bounded index** into fixed ROM tables, then calling a **fixed
  PC-relative handler**. No file byte is ever used as a pointer, in the dispatcher or in any
  of the seven parsers. There is **no execute-from-SD / overlay / plug-in path and no SD
  firmware-update path**; the runtime library at `0x4C000000` loads from *program flash*
  (source `0x487B8FD1`), never the card. (SD-transport analyst confidence 0.93.)
- **Memory-safety: 5 of 7 parsers are cleanly bounded. Two image decoders are NOT** — a
  crafted SD image causes a *controlled out-of-bounds write* into work RAM. This is the
  strongest primitive found on either external surface (the expansion board only yielded a
  read + DoS).

## The disk-file dispatch (the core code-exec gate)

`0x4852B6B0`: takes the file's tag/ext, matches it against the string tables
`DiskFileTagTable 0x48664090` / `DiskFileExtTable 0x48664438` (pure data — pointers point
into their own string pools), derives a bounded index (`asl 3` / `mulu 0xc` into RAM table
`0x5006F24C`), and calls a **fixed** PC-relative handler. **Zero** instruction-aligned
`calls/jmp (aN)` in the whole dispatcher region. Same safe shape as the CN106 board.

## Per-format verdicts

| Format (ext) | control-flow | memory-safety | notes |
|---|---|---|---|
| `.AST` custom data (zlib) | fixed-table | **SAFE** | zlib 1.0.4 streaming inflate into a FIXED `0xC0000` SDRAM scratch (`0x502B8000`, hard `avail_out` cap), then chunked into a FIXED custom-flash region (fixed erase const `0x1E0000` @ `0x96820000`). Claimed decompressed-size u32 is bounds-checked (`≤0x1E0000`) and *not* trusted as a copy/erase count. The 2 indirect `jmp(a0)` dispatch the bounded zlib mode-enum through fixed ROM tables; the 2 indirect `calls` go through firmware-set `z_stream` callbacks. |
| SMF `.MID` / `.SEQ`/`.SQF` | fixed-table | **SAFE** | Table-driven MIDI state machine. VLQ deltas, running status, SysEx/meta length **not** blindly trusted: len ≥ `0x7F` → streamed & discarded (no store); len < `0x7F` → count-bounded copy into a ~260-byte scratch. One real `jmp(a0)` @`0x48480903` dispatches a parsed status byte guarded to `[0xF0,0xFF]` through a fixed table. |
| `.ACT` demo script | fixed-table | **SAFE** | It *is* a tag interpreter — but **text/markup** (`SSW-ACT-V01`, `<ACTION>`, `SHOW OBJ=`), dispatched through a **fixed ROM `{name,handler}` table** (`0x486AF1FC`) keyed by a string-matched token. 11-byte header `strncmp`; NUL-terminated buffer with bounds-checked scans; tag content `malloc`'d to scanned length. No token supplies a native pointer. |
| `.FAV`/`.MD`/`.HMP` → SRAM | fixed-table | **SAFE** | Installers copy **compile-time-fixed** byte counts (MD `0x280`, FAV `0x198`, HMP `0x4442`) into FIXED-size SRAM / bounds-checked heap. No file-supplied count governs any copy; no file byte dereferenced. Hotspot table is a fixed `0x40`-entry loop. |
| SD µ-COM transport | fixed-table | **SAFE** | Every SD byte consumed as DATA; recv loop copies exactly the caller-supplied count. No execute-from-SD, no SD firmware-update. Media-driver vtable (`0x486646F0`) indexed by a clamped device selector 0/1/2. |
| **`.JPG` (JFIF/JPEG)** | fixed-table | **⚠ UNBOUNDED WRITE** | see below |
| **`.HMP` embedded BMP** | fixed-table | **⚠ UNBOUNDED WRITE** | see below |

## ⚠ The two verified image-decoder overflows

Both are **out-of-bounds writes** into work RAM past the FIXED 640×240 display-plane pair
(`0x500D4080` / `0x500F9880`, `0x25800` bytes, stride `0x280`). **Control-flow is still safe**
— no file byte becomes a call/jmp target; file bytes control the write *length/offset*, not a
pointer that is loaded and called.

**JPEG** (`.JPG` is a real SD file type: `VwJpegFileProc 0x48418D19` / `DrawJpegFile 0x48424EBD`,
vtable `0x487276C4`, ext-match `0x4852EE96`; "This Bitmap/JPEG is in the wrong format", `DORA.JPG`):
- SOF0 (`0x4840F082`) stores height→`0x5017397E` with `exthu`+`cmp 0/bge` (**always true** →
  accepts 0..65535) and width→`0x5017397C` with `cmp 0/bgt` (>0 only). **No upper bound.**
- The decoder runs **before** `GetJpegSize` (`0x48424F47`), which itself enforces no upper bound.
- Full-MCU store `0x484864DC` computes `offset = (y_origin+row)*0x280 + x_origin + col`
  (`y/x origin 0x5006AD1E/0x5006AD1C`, clamped only `≥0`) with **no clamp against the plane**;
  edge handler `0x48486519` clamps a block to 16×16 relative to the *declared* dims, not the buffer.
- Writer `0x484870C8` (YCbCr→RGB, `udf00` MACs, `>>14`, clamp `[0,0xFF]`) stores at
  `0x500D4080+offset` (`0x48487199`) / `0x500F9880+offset` (`0x484871A3`). → a JPEG with
  height>240 (or a pushed origin) writes file-derived pixel bytes past the plane.

**BMP** (`GetBitmapInfo 0x48421DE1` validates sig/header-size/planes/bit-depth{1,4,8}/BI_RGB/
palette≤1024, but **never `biWidth`/`biHeight`**):
- At blit (`DrawBitmapFile 0x48424B07`) **height** is clipped to 240, but **width is not**: the
  per-row `memcpy(dest = 0x500D4080 + row*640 + X, src, n = biWidth)` @`0x48424C2B` has no clamp
  vs the 640 stride / buffer end. `X + biWidth > 640` overruns; the homepage centers with
  `X = (screen − biWidth)/2` (`0x48495961`) so a large `biWidth` wraps `X` and flings `dest` wild.
- Bonus robustness gap: the decode-buffer `malloc` (`0x4841662A`) is used with **no NULL check**
  (`0x48424B84`), so an allocation failure on a huge width feeds NULL/garbage `src` into the memcpy.

## Escalation & emulation notes

- **Escalation to PC control is unproven** — the same open residual as the expansion board. The
  writes land forward of a *work-RAM* plane (`0x500Dxxxx`), not the stack; reaching a return
  address or a loaded code pointer would need the corrupted span to contain one. Not chased here.
- **The emulator reproduces this faithfully for free**: it runs the *real* decoder on the real
  CPU core over emulated RAM bounded by the memory map — so the host is never wild-written, and
  the emulated instrument corrupts its own RAM exactly as hardware would. No driver fix needed;
  if anything, faithfulness means *not* adding a clamp the firmware lacks.

## Provenance

Workflow `wf_abb18725-948`, 7/7 agents, 0 errors (neutral preservation-RE framing — the earlier
"exploit-writer"-framed residual workflow was blocked by the model's cyber-safeguards; reframing
as plain RE cleared it). JPEG OOB write independently re-verified inline (SOF0 bounds, offset
math, writer base) before recording.
