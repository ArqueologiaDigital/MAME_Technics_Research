# Where is the KN7000 flash updater? — 2026-08-09

**This refutes `rom-backup-and-update-format.md` §2.2.** That section concluded the
resident updater lives in the un-dumped top 0x90FF of the program flash
(0x487F6F01–0x487FFFFF). It does not.

## What started it

Owner hardware read, 2026-08-09, via the instrument's own MEMORY DUMP screen on a
PROGRAM build **893** machine: **0x487F55CF–0x487FFFFF is one block of 0xFF**, with
code immediately below. A factory-programmed resident block would be build-independent,
so this null applies to our build 941 too.

## Verdicts

| hypothesis | verdict |
|---|---|
| H1 resident block in the top 0x90FF of program flash | **REFUTED** |
| H2 the update writes the payload and leaves the rest erased | **SUPPORTED** (describes the payload; silent about the machine) |
| H3 the updater is in the dumped 8 MB, unidentified | **REFUTED** (uncompressed forms) |
| H4 the updater is loaded from the update floppy | **REFUTED** for the disks we hold |
| H5 the updater is in another device | **SUPPORTED** — the only survivor; which device is UNDECIDED |

## The cross-reference evidence was a byte-misframing artifact

§2.2 rested partly on "33 dword cross-references into 0x487Fxxxx, several past the dump
end". Two independent kills:

1. **Noise floor.** Scanning 4,157,185 unaligned positions for a 37,119-byte window has
   an expected *random* yield of ~36 hits. The scan finds 12 — below chance.
2. **Mechanism identified.** At **0x485D6860** there is an 8-byte-record
   `{u32 id, u32 handler}` table: `21 00 00 00 | 00 7e 48 48`, `33 00 00 00 | a7 7f 48 48`,
   `b0 00 01 00 | bc 7f 48 48`, then six `00 00 00 00 | ea 7f 48 48`, then
   `0f 00 00 00 | 60 7e 48 48`. Every real pointer (0x48487E00, 0x48487FA7, 0x48487FBC,
   0x48487FEA, 0x48487E60) is **inside** the dumped image. Read three bytes early they
   become the phantoms 0x487FA700, 0x487FBC00 and 0x487FEA00×6. The "individually
   improbable" six-fold repeat is one default handler slot, repeated six times.

An opcode-anchored `imm32` scan (28k+ sites) finds **zero** references into
0x487F6F01–0x48800000, and a linear disassembly of 0x48400000–0x4858FFFF yielding
128,781 branch targets finds **zero** real branches above 0x487F6F00.

Also retracted: "the updater UI strings appear in neither ROM" is not evidence. On the
KN5000 — where we hold genuine chip dumps — the updater's UI is **bitmaps**, so those
ASCII strings are absent from a genuine KN5000 program dump too.

## H3's four instruments (each with a measured control)

- **AMD unlock idiom**, all immediate encodings: 4 hits in program, 1 in table; three
  control constant pairs with comparable load counts score 0/0/0 in both — floor is zero.
  The only real flash driver in the whole 8 MB is **0x4847E7C0–0x4847FB96**, hardwired to
  absolute `0x9680AAAA`/`0x96805554` — that is **custom-data flash IC21, not IC16/IC17**.
- **Command sequences as data tables** (u8 and both u16 orders): 0 in the KN7000 program
  image, 0 in the table image, 0 in the KN5000 program image.
- **The uncached write alias**: proven by the firmware's own boot (work RAM 0x50000000
  written through 0x90000000 at 0x48410070; 0x4C000000/0x8C000000; 0x56800000/0x96800000),
  so the program-flash command window would be **0x88400000** — and imm32 loads with high
  byte 0x88 number **zero** in both images.
- **Per-64KB code-density map**: the table half contains no MN10300 code at all (max 1 hit
  per 64 KB across 63 blocks, vs 103–970 in program code blocks). A relocatable blob would
  spike.

Residual loophole, stated honestly: a **packed/compressed** updater cannot be excluded by
these tests. Nothing supports it, and the KN5000 analogue is not packed.

## The KN5000 template (re-derived, not cited)

De-interleaving `kn5000_table_data_rom_even.ic3` + `odd.ic1` as 16-bit words gives, at CPU
**0x9FA000**: `Technics KN5000 Program  DATA FILE 1/2`, `... 2/2`, `... PCK`,
`Technics KN5000 Table    DATA FILE 1/2` — the update-disk signature records. The block
runs **0x9FA000–0x9FFFCF, the top 0x6000 of the 2 MB table-data MASK ROM**, and contains a
real flash driver at 0x9FB903 (`lda XIZ,0x300000` / `add XWA,0xAAAA` / `ld (XWA),0x00AA` /
`ld (XIZ+0x5554),0x0055` / `ld (XWA),0x00A0`). Its own interrupt vector table sits at
0x9FFF00.

Decisively: the KN5000's **resident firmware cannot write its own program flash either** —
its in-ROM driver at 0xEF3740–0xEF3E00 uses bases 0x280000/0x300000/0x380000 only, and
0xE00000-based command addresses return zero hits in both images. **The updater lives in a
device no update can erase.** That is the pattern to look for on the KN7000.

## Architectural correction

**IC16 + IC17 are ONE 8 MB pair spanning 0x48000000–0x487FFFFF** — 21 address lines
(A2–A22) on a 32-bit bus, corroborated by the firmware's own service ROM test at
0x4849FC54 (a1=0x48000000, a0=0x48000002, 0x200000 iterations of a 4-byte stride = 8 MB,
under the screen row `PROGRAM ROM:      IC16 = , IC17 =`). So the "table ROM" is the
**lower half of the same flash pair**, not a separate chip, and the idea of an unread
upper half at 0x48800000–0x48BFFFFF is refuted.

That makes **0x483E94D4–0x483FFFFF (93,484 bytes)** — the top of the lower half — the only
part of the 8 MB nobody has ever read, and the exact positional analogue of the KN5000's
0x9FA000.

## Probe list for the instrument (ranked)

| # | address | why | expect |
|---|---|---|---|
| 1 | **0x483FFF00** | top of the lower half; KN5000 positional analogue; the only unread part of the 8 MB | dense code / vector table / ASCII, or 0xFF |
| 2 | **0x40000000** | IC18 rhythm window — the prober at 0x4843D6DC strncmps `Technics Rhythms` at region_base+0x10000, so the first 64 KB of each window is *not* rhythm data | non-0xFF means a device is there |
| 3 | **0x97800000** | IC19 picture ROM (C3CBMD000098, 64 Mbit mask): **no update disk targets it**, so it survives every flash operation by construction — exactly the KN5000 property | graphics data, or better |
| 4 | **0x97FFFF00** | top of IC19 — the KN5000 template position translated | code/vectors, 0xFF, or a mirror of probe 3 |
| 5 | 0x483E9400 | bounds the hole from below on a build-80 table | our build 84 ends 0x483E94D3 |

## Size

**Unknown — we cannot yet say it exists in any reachable flash.** For scale, the KN5000's
analogous block is 0x6000 = 24,576 bytes ≈ 96 screenfuls at 256 bytes.

## Warnings

- ⚠ **Do NOT probe 0x88400000.** The +0x40000000 uncached-alias convention is real, so
  that is the program flash's *command* window.
- ⚠ If probe 1 shows real content, **do not run a TABLE update** on that instrument until
  the region is dumped — the table payload ends at 0x483E94D3 and erase-sector geometry
  may take the block with it.
- ★ Preservation risk found on the way: the shipped firmware **can erase and fully rewrite
  the 2 MB custom-data flash IC21** — 0x4847FB68 is a whole-chip programmer.
- MAME's `mn10300_device::device_reset()` **hardcodes the reset PC to 0x48400000** and this
  has never been checked against hardware.
- Do not re-run raw byte-pattern searches for addresses in 0x487Fxxxx / 0x483Fxxxx without
  a noise floor. That is the error this document corrects.
