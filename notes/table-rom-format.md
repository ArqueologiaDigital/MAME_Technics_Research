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
