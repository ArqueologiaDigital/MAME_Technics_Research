# KN7000 table ROM (`kn7000_table.rom`) format — resource archive

Mapped `kn7000_table.rom` (mapped at 0x48000000-0x483FFFFF; the file is the
decompressed 0x3E94D4-byte image, flagged BAD_DUMP but structurally intact). It is a
**resource archive** with a directory of 32-bit little-endian offsets at the very
start.

## Directory @0x48000000
An array of `u32` offsets (relative to 0x48000000). Entry [0]=0x200 marks the end of
the directory / start of the payload, so the directory is 0x200 bytes = 128 slots, of
which **85 are non-zero**. Each entry points to a section. Class histogram of the 85:
**57 JPEG, 21 misc-data, 2 "Technics Pads", 1 each of ZZZJ / TCMP / TPAD / text.**

Head of the directory:
```
[  0] 0x48000200  config / pointer block (starts 40 02 00 48 80 e8 00 48 = ptrs)
[  1] 0x48034858  'ZZZJ'  (ZZZ = 5A5A5A section delimiter, +J)
[  2] 0x48035D08  'TCMP'  chunk  (rhythm/composer style data — see below)
[  3] 0x48040674  'TPAD'  chunk  (performance-pad data)
[  4] 0x4804238C  "Technics Pads   " (a performance-pad bank)
[  5] 0x4805667C  data
[  6] 0x4806EA98  text?
[  7] 0x48139EE8  data (a JPEG group header: "84\nZZZ\nZZZ\n" then JFIF)
[  9..] 0x48139EF0 …            57 JPEG images referenced directly
[ 83] 0x483E828C  "Technics Pads" (second pad bank)
```

## `TCMP` chunk @0x48035D08 (rhythm/composer style data)
```
54 43 4d 50  00 00 cc 00  00 00 70 00  1b 00 00 00   "TCMP" ....
02 58 00 00  a9 69 00 03  00 60 0d 08  04 02 02 01   ...
02 0f 00 00  00*  20 20 20 20 …                       (name field padded w/ spaces)
```
FourCC `TCMP` then a header (count `0x1b`=27 at +0xC; `00 60`=96 looks like ticks/beat;
`04 02 02 01` = time-signature / pattern params). **The built-in rhythm-style names
live inside/after this chunk**: e.g. "Easy 8 Beat" @0x48035D7E (= TCMP+0x76), and the
style-name clusters found across 0x35D7E–0x549CC ("8 Beat", "Ballad"×13, "Waltz"×17,
"March"×11) fall in the TCMP + following data sections. So **TCMP is the container for
the built-in rhythm/style patterns + their names** — the exact data the rhythm-style
list (see rhythm-name-list-bug.md) reads.

## `TPAD` chunk @0x48040674 (performance-pad data)
```
54 50 41 44  00 00 e1 3d  00 00 d0 00  03 a8 00 00   "TPAD" ....
00 a0 00 00  1d 16 00 03  00 60 10 06  10 02 00 02   ...
```
FourCC `TPAD` then a header of the same shape (`00 60`=96 ticks/beat again;
`10 06 10 02` params). Followed at 0x4804238C by the "Technics Pads" bank name — this
is the **Performance-Pad (MSP)** preset data. A second "Technics Pads" bank is at
directory entry [83] (0x483E828C).

## JPEG images
**119 JFIF images total** (scan for `FF D8 FF E0 00 10 "JFIF"`), 0x480566E8 …
0x483DEF88 — the bulk of the ROM. 57 are top-level directory entries; the rest are
sub-images grouped under section headers (e.g. the "84\nZZZ\n" group header at
0x48139EE8). These are the Music Stylist / on-screen graphics (cf. sym
`MusicStylistJpgData` 0x4847B137). Each is a standard baseline JPEG and can be
extracted directly by SOI→EOI.

## Relevance / next
- **TCMP is the rhythm-style container** the "all 8 Beat 1" bug reads from — decoding
  its per-style record layout (name field offset, pattern pointers, the `0x1b`=27
  count) would show how styles are indexed and may reveal why the list defaults.
- The 119 JPEGs are trivially extractable for preservation (SOI/EOI carving).
- Directory entries [5],[6],[7] (data/text) are not yet identified.


## TCMP per-record layout (decoded)
Header is 0x70 bytes (0x35D08..0x35D78); records follow at 0x35D78, stride **0x80**:
```
rec+0x00: name, 16 bytes (ASCII, space-padded, NUL-terminated)
rec+0x10..0x4F: 4 alternate-name slots (16 bytes each; usually all-spaces / empty)
rec+0x50..0x63: 20 pattern indices (consecutive globally: rec0=0x00..0x13, rec1=0x14..0x27, ...)
rec+0x64..0x6F: zero
rec+0x70..0x7F: params (clean records = 44 00 44 00 00.. )
```
Only the first **3 records have clean names**: `Easy 8 Beat`, `Easy 16 Beat`,
`Easy Swing` — the "Easy"/one-touch preset styles. Records 3+ decode as non-text with
the fixed 0x80 stride, so past record 2 the chunk holds the referenced **pattern data**
(the 20-index arrays point into it). Header +0xC = 0x1B (27) — a count whose exact
referent (patterns? sub-records?) is still open. Records end ~0x36AF8, well before TPAD
(0x40674), so 0x36AF8..0x40674 is the Easy-style pattern pool.

## Genre (rhythm-selection) styles = variable-length `f5`-marker records
The *rhythm-menu* styles are NOT the TCMP "Easy" set. They live later in the archive
(BALLAD genre: 13 records starting 0x4804AF62; WALTZ: 17; MARCH: 11) as
**variable-length** records: `[0xF5 marker][name, NUL-terminated][params 03 03 00 00
ff..][MIDI pattern data: 90 3c 43 ... note-on events]`. Example names: "Pop Ballad
Piano", "EP Ballad Maj/Min", "Angel Ballad", "Ballad Backing". This is the **same
record shape as the program-ROM user-style area** (0x4872AB44, also `f5`-marker). Their
lengths vary (0xE7..0x5DAA apart) because the embedded MIDI pattern data varies. A
list build must scan `f5` markers / use a pointer table to enumerate a genre's styles.
