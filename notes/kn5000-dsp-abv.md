# ASCII Book Viewer (`.ABV`) reverse-engineering — and what NEC's PC-9800 Technical
# Data Book actually says about the uPD6380 DSP

*Side-quest for the KN5000 effects DSP (NEC uPD6383GF, undocumented ISA). Its sibling
uPD6380 is the audio DSP of the PC-98GS / PC-9801-73 sound boards, and NEC's own
technical data books ship as `.ABV` electronic books.*

Tool: `tools/abv_extract.py`. Sources:
`/home/fsanches/compartilhado/pc98_tdb/PC98Docs1stEd.iso` (1st ed., 1994) and
`PC98TDB.ISO` (later ed., incl. a Windows 95 volume).

**Result in one line: the container is fully decoded — the "compression" was a
red herring, the whole book is plain Shift-JIS with every byte complemented
(`b ^ 0xFF`) — and all six volumes plus all embedded figure/table bitmaps now
extract cleanly. The books document the uPD6380 only through its DOS driver API;
they contain no instruction set and no register-level host protocol.**

---

## 1. The ISOs

Walk the ISO9660 root directory directly (`abv_extract.py iso <iso>`), no mount needed:

| ISO | file | LBA | dir-entry size |
|---|---|---|---|
| PC98Docs1stEd.iso | `ABV.EXE` | 99 | 175 616 |
| | `ABV.HLP` | 185 | 72 569 |
| | `BI.ABV` | 221 | 200 000 000 |
| | `HW.ABV` | 97 878 | 200 000 000 |
| | `INSTALL.EXE` | 195 535 | 25 840 |
| | `MM.ABV` | 195 548 | 200 000 000 |
| PC98TDB.ISO | `ABV.EXE` | 40 241 | 195 584 |
| | `ABV.HLP` | 40 202 | 78 684 |
| | `APL.ABV` | 25 081 | 30 967 246 |
| | `HW.ABV` | 10 362 | 30 144 231 |
| | `WIN95.ABV` | 8 094 | 4 617 443 |

★ **The 200 000 000 sizes in the 1st-edition directory are placeholders.** The real
payload length is the `u32` at offset `+0x04` of the `.ABV` itself; everything past it
is filler. `MM.ABV` is 0x007CABC0 = 8 170 432 bytes, not 200 MB. The earlier
"entropy 8.00 bits/byte body" reading was measuring that filler — the *actual*
book data sits below it at ~3.5 bits/byte and is not compressed at all.

The viewer **was** found (`ABV.EXE`, a Borland C++ 16-bit NE for Windows 3.1,
15 segments, `CS:IP 0x10000`, imports KERNEL/USER/WIN87EM/COMMDLG, window class
`BookView`, exported thunks such as `@BOOKWNDPROC$QUIUIUIL`, `@INDEXDLGPROC$…`,
`@BIGBMPDLGPROC$…`). **It was not needed** — the format fell to direct analysis
before disassembly was necessary, so no decompressor had to be reversed. Both
editions' `ABV.EXE` share the same segment layout; segment 15 is the DGROUP.

## 2. `.ABV` container layout

All multi-byte fields are little-endian and **byte-granular — nothing is 2-aligned**
(this is what made the earlier scan look "mis-aligned by a byte"; it wasn't, the
structures genuinely start on odd offsets).

```
+0x00  u16  0x0032            record id
+0x02  u16  0x0001            version
+0x04  u32  file_length       real payload size          (MM: 0x007CABC0)
+0x08  u32  ...               counters
+0x14  u32  off_A             secondary section          (MM: 0x00744D13)
+0x18  u32  off_TEXT          start of the linear text pool (MM: 0x007A373B)
+0x1c  u32  off_B             secondary section          (MM: 0x007407EF)
+0x20  u32  0x0000019E
+0x24  Shift-JIS title, PLAIN (not complemented), NUL-padded
       e.g. "PC-9800シリーズ テクニカルデータブック MULTIMEDIA編"
+0x65  u32  off_TEXT (repeated)
+0x69  u32  n_entries         (MM: 0x38D1)
+0x6d  u32[n_entries]         page-record offset table, monotonically increasing
                              MM: 0x3FA09, 0x3FD37, 0x4CF63, 0x54E37, 0x5628D, …
```

The page offsets are odd because records simply are not aligned. `MM.ABV` page 1 at
`0x3FA09` begins with the `u16` fields `0002 0002 000E 0013 0004 0000…`, then a
layout block, then a plain-Shift-JIS font name `"1ＭＳ ゴシック"` at `0x3FAF0`,
then a run of text/attribute records of the shape
`u16 kind, u16 len, len bytes of complemented Shift-JIS`
— e.g. at `0x3FBE8`: `2A 00 | 02 00 | 6E 19` = kind 0x2A, 2 bytes, `6E 19 ^ FFFF`
= `0x91E6` = 第. Kind 0x1F/0x2A/0xC4 carry glyph runs with per-run x/y and size.

### 2.1 The text obfuscation

Body text is **Shift-JIS XOR 0xFF**, nothing more. Proof — the first bytes of the
`MM.ABV` text pool at `0x7A373B` are
`7E BF 6E 19 CE 6A 6B 7E BF 7C 82 7C 74 …`, complement to
`81 40 91 E6 31 95 94 81 40 83 7D 83 8B …`, which decodes as:

> 　第1部　マルチメディア概要　第1章　仕様概要PC-9821,PC-98GSは従来のPC-9801に
> マルチメディアへ対応するためのハードウェアを付加した機種である.…

(Figure names, figure captions and font names are stored **plain**, i.e. NOT
complemented — only the flowing body text is.)

The region from `off_TEXT` to `file_length` is one continuous complemented
Shift-JIS stream containing the entire running text of the volume, with `$Name`
markers introducing each command/anchor. That is the easy way to read a book:

```
tools/abv_extract.py text PC98Docs1stEd.iso 195548 -o MM.txt
```

| volume | title | text pool | chars |
|---|---|---|---|
| `BI.ABV` | …BIOS編 | 0x00D90525, 280 957 B | 166 817 |
| `HW.ABV` (1st ed) | …HARDWARE編 | 0x01E06F0F, 163 293 B | 101 051 |
| `MM.ABV` | …MULTIMEDIA編 | 0x007A373B, 160 901 B | 109 463 |
| `APL.ABV` | …アプリケーション開発編 | 0x01D0C38B, 508 483 B | 314 207 |
| `HW.ABV` (2nd ed) | …HARDWARE編 | 0x01C90651, 192 662 B | 118 686 |
| `WIN95.ABV` | …Windows95編 | 0x004519E9, 88 826 B | 57 193 |

### 2.2 Figures and tables

★ **Every table and every diagram in these books is a bitmap, not text.** They are
stored as ordinary, *uncompressed* Windows `BITMAPFILEHEADER` + `BITMAPINFOHEADER`
blobs embedded verbatim, and can be carved byte-for-byte:

```
tools/abv_extract.py bmp PC98Docs1stEd.iso 195548 -o mmbmp
```

`MM.ABV` holds 478 BMP blobs / 238 distinct figures (4 240 108 bytes — i.e. the
bulk of the file); 1st-ed `HW.ABV` holds 1292 blobs. Each figure is described by a
record containing a 30×30 598-byte icon (`tbl.bmp` for tables, `fig.bmp` for
figures), the plain name `mt40501.bmp`, the plain Shift-JIS caption, and a `u32`
absolute file offset to the real image. `abv_extract.py bmp` resolves name→image by
looking for a `u32` in the 1 KiB before the name string that equals a known BMP
offset (largest match wins, which discards the icon) and writes an `index.txt` of
`file / offset / size / caption`.

Verified: `mt40501.bmp` (272×372, 1 bpp) renders as the DSP function table
reproduced below; `mf10303.bmp` (475×244) as the PC-98GS block diagram.

## 3. What the books say about the uPD6380

### 3.1 Hardware (MULTIMEDIA編 第1部 3.1, figure `mf10303.bmp`)

Block diagram "サウンドブロックダイアグラム(PC-98GS, PC-9801-73)":

```
YM2608 ─ VOL1 ─┐                                 ┌─ D/A OUT1 ─ MIX ─ FRONT LINE OUT
        └ VOL2 ─┴ MIX ─────────────┐              │
LINE IN ─ VOL3 ─┐                  ├ IN2 ─┐       ├─ D/A OUT2 ─ MIX ─ REAR  LINE OUT
        └ VOL4 ─┴ MIX ─ A/D ───────┘      │       │
CD-DA ── D/A ─ VOL5 ───────────────  IN1 ─┴ DSP μPD6380 ──┘        (dashed = digital L/R)
                                             ↕ メインメモリ (main memory)
```

So: two **digital** stereo inputs IN1 (CD-DA, PC-98GS only) / IN2 (A/D of
FM+LINE-IN), two digital outputs OUT1 (front) / OUT2 (rear) each feeding a D/A,
and a bidirectional path to host main memory (that is how PCM/ADPCM record and
replay run through the same chip). PC-9801-73 has no CD-DA leg.

Prose (第1部 3.1 ■DSP): the DSP runs one — and only one — of the effect functions
at a time; its performance is independent of CPU load and interrupts; ADPCM is
implemented *on the DSP* (16/8-bit sample → 4-bit delta and back).

I/O ports documented: `0188H`/`018AH` (YM2203-compatible addr·status / data),
`018CH`/`018EH` (YM2608 extension), `A460H` = ID field (D7..D4 read = ID,
D1..D0 write = MODE, 0 = YM2203 mode, 1 = YM2608 mode) — figure `mt10304.bmp`,
`mf10301.bmp`. ★ **`A462H` / `A464H` do not appear anywhere in any of the six
volumes.** Neither does any I-RAM/GF/OVF description. The books deliberately stop
at the driver boundary.

### 3.2 Host protocol = a DOS driver API, `INT 0D9H` (第4部 PCMドライバ)

`AVSDRV.SYS` (needs MS-DOS ≥ 5.0; `/E` for EMS, needs 4 contiguous physical pages
from segment `0C000H`; device name `AVSDRV$$`). Commands in `AH`
(table `mt40101.bmp`; Carry = error, `AH` = status on error):

| AH | name | function |
|---|---|---|
| 00H | `$INITDRV` | initialise the PCM/DSP driver |
| 01H | `$INITFUNC` | **load a DSP function**, `AL` = function number (§3.3) — resets that function's parameters to defaults |
| 02H | `$ASKFUNC` | read back the currently loaded function number |
| 03H | `$SETPARAM` | **set the parameters of the loaded function**, `ES:BX` → parameter block |
| 04H | `$GETPARAM` | read parameters back, `CX` = count, `ES:BX` → block |
| 05H/06H | `$SETVOL`/`$GETVOL` | electronic volumes VOL1…VOL5, 0H…FH |
| 07H/08H | `$SETMIX`/`$GETMIX` | IN1:IN2 mixing rate, 00H…0AH = 100:0 … 0:100 |
| 09H/0AH | `$SETMUTE`/`$GETMUTE` | front+rear output mute |
| 0BH/0CH | `$SETFREQ`/`$GETFREQ` | 00H 44.10 / 01H 33.08 / 02H 22.05 / 03H 16.54 / 04H 11.03 / 05H 8.27 / 06H 5.52 / 07H 4.13 kHz |
| 0DH/0EH | `$SETPCM`/`$GETPCM` | PCM I/O mode 0…8, mono/stereo, 8/16-bit (16-bit is **big-endian**: high byte first) |
| 10H | `$PCMTRN` | PCM/ADPCM record/replay, `ES:BX` → PCB |
| 11H | `$STPTRN` | abort |
| 12H | `$SNSTRN` | transfer status |

`$INITFUNC` / `$ASKFUNC` / `$SETPARAM` / `$GETPARAM` are marked "GS73" — i.e. they
exist only on the two DSP-equipped products. Loading a function while recording or
replaying is an error.

★ This is as close to a *host protocol* as the books get: microcode upload is
entirely hidden inside `AVSDRV.SYS`. `$INITFUNC` clearly triggers an I-RAM load of
the selected effect microprogram, but neither the port sequence nor the image
format is documented. **The next concrete step for anyone wanting the real
protocol is to obtain and disassemble `AVSDRV.SYS` itself** — its `INT 0D9H`
`AH=01H` handler contains the I-RAM upload loop and, embedded in the driver, the
19 uPD6380 microprograms. That is a far better target than these books.

### 3.3 The 19 DSP functions (table `mt40501.bmp`, verified render)

| № | name | effect |
|---|---|---|
| 00H | `$Thru` | through |
| 01H | `$Echo` | echo |
| 02H | `$LPF` | low-pass filter |
| 03H | `$HPF` | high-pass filter |
| 04H | `$Geq` | graphic equaliser |
| 05H | `$Rev` | reverb |
| 06H | `$Hall` | hall |
| 07H | `$Loc` | sound-image localisation |
| 08H | `$Adj` | localisation correction |
| 09H | `$Pan` | panning |
| 0AH | `$Chor` | stereo chorus |
| 0BH | `$Doubl` | doubling |
| 0CH | `$Flang` | flanger |
| 0DH | `$Vibrt` | vibrato |
| 0EH | `$Ensem` | ensemble |
| 0FH | `$Pitch` | pitch shifter |
| 10H | `$Surr` | surround |
| 11H | `$Kara` | pseudo-karaoke (centre-cancel) |
| 12H | `$ADPCM` | ADPCM record/replay |

Only one may be resident at a time — a strong hint about the size of the uPD6380
instruction RAM.

### 3.4 Parameter blocks (tables `mt40503`…`mt40522`, all bytes)

All delay times and frequencies are quoted at the 44.1 kHz reference rate and are
scaled by κ (`mt40502.bmp`): 44.10 → 1.00, 33.08 → 1.33, 22.05 → 2.00,
16.54 → 2.67, 11.03 → 4.00, 8.27 → 5.33, 5.52 → 8.00, 4.13 → 10.68.
Delay times multiply by κ, frequencies divide by κ — i.e. **the microprograms are
sample-count based and the driver simply reinterprets the units**, which also
explains "lower the sample rate to get longer delays".

* `$Thru` (`mt40503`) +0..+3 = front-L / rear-L / front-R / rear-R output level, 0…100.
* `$Echo` mono (`mt40504`) +0 method(=0), +1..+4 four output levels, +5 L/R-summed
  feedback 0…100 (default 100), +6 reserved, +7 L/R-summed delay 0…180
  (0…360×κ ms, default 20×κ), +8 reserved.
* `$Echo` stereo (`mt40505`) +0 method(=1), +1..+4 outputs, +5/+6 L/R feedback,
  +7/+8 L/R delay 0…180 (0…180×κ ms).
* `$LPF` (`mt40506`) +0..+3 outputs, +4/+5 L/R cutoff index 0…9 →
  200/300/500/700/850 Hz, 1.3/2/3/5/20 kHz (÷κ), default 9.
* `$HPF` (`mt40507`) +4/+5 cutoff index 0…7 → 50/100/500 Hz, 1/3/5/7/10 kHz (÷κ), default 0.
* `$Geq` (`mt40508`) 16 bytes: per channel, 7 band levels
  63 / 160 / 400 Hz, 1.0 / 2.5 / 6.3 / 12.5 kHz (÷κ) plus a "through" level; 0…100, default 30.
* `$Rev` (`mt40509`) +0 reverb level 0…100 (default 100), +1 reverb time 1…30
  (0.1…3.0×κ s, default 2.0×κ).
* `$Hall` (`mt40510`) +0 initial delay 1…50 (ms×κ, default 20), +1 room size 1…20
  (spacing of early reflections I…IV, ms×κ, default 15), +2 liveness 0…10
  (default 5), +3 reverb time 1…30 (0.1…3.0×κ s, default 2.0×κ), +4 reverse flag 0/1.
  Prose: four early reflections per channel, reflections I–IV plus a diffuse late tail.
* `$Loc` (`mt40511`) +0 X, +1 Y, −100…100 (also a polar mode: coordinate system 0 =
  cartesian, 1 = polar with R 0…100 and θ 0…180 = 0…360°).
* `$Adj` (`mt40512`) +0..+3 outputs, +4..+7 per-speaker delay 0…180 (ms×κ).
* `$Pan` (`mt40513`) +0 mode 0…3 (0 = rotate right, 1 = rotate left, 2 = L/R ping-pong,
  3 = front/rear ping-pong), +1 rate 1…100 (0.1…10.0 ÷κ Hz).
* `$Chor` / `$Doubl` / `$Flang` / `$Vibrt` / `$Ensem` share a modulated-delay shape:
  four output levels, delay-signal L/R send levels, **modulation centre** 0…250
  (0.0…50.0×κ ms), **modulation frequency** 1…100 (0.1…10.0÷κ Hz), **modulation
  level** (depth) 0…100 (0.0…10.0×κ ms); `$Flang` adds feedback 0…100 (default 30);
  `$Ensem` has two independent modulated delays (defaults 0.5 and 5.0 Hz);
  `$Vibrt` mutes the dry path. Documented "recipes": stereo ≈ 0.2 Hz / 1.0 ms,
  chorus ≈ 0.5 Hz / 5.0 ms, tremolo ≈ 5.0 Hz / 1.0 ms.
* `$Pitch` — L/R pitch in units of 10 cents, two's complement, −120…120 = ∓1 octave.
* `$Surr` — per-speaker delay 0…90 ms×κ (default 50) plus front/rear L and R
  cross-mix rates 0…50 % (default 50).
* `$Kara` — outputs only.

## 4. Relevance to the KN5000 uPD6383GF — honest assessment

* (a) **Instruction set / microcode: NOT PRESENT.** Nothing in any of the six
  volumes describes uPD6380 opcodes, word format, registers or an assembler.
  The books are written for application programmers calling `INT 0D9H`.
* (b) **Host protocol: only the driver-level API** (§3.2). The `A462H`/`A464H`
  I-RAM-modify/GF/OVF bits are *not* in these books.
* (c) **Effect API: fully recovered** (§3.3, §3.4) — and this is genuinely useful.
  It tells us what a 1992-vintage NEC set-maker audio DSP of this family was
  expected to do with one resident program at a time, at 44.1 kHz, with 4-channel
  output, a delay memory scaled in samples, and a parameter set that is
  byte-granular integers in a small contiguous block. The uPD6383 in the KN5000
  is the same product family, and the *shape* of the KN5000 effect records
  (small byte parameter blocks, one program resident per unit, delay times that
  scale with sample rate) matches this closely. Useful as a cross-check for the
  parallel constraint-solving work on KN5000 DSP semantics — not as a decoder.
* (d) **Block diagram and register maps: recovered** (§3.1) as bitmaps.

### Where to look next
1. `AVSDRV.SYS` (and the PC-9801-73/86 driver diskettes) — contains both the
   I-RAM upload sequence and 19 uPD6380 microprograms. Highest value by far.
2. The PC-98GS / PC-9801-73 *service* or *board* documentation, which is where
   `A462H`/`A464H` would be described.
3. `APL.ABV` and `HW.ABV` are now readable too and are worth a general sweep for
   the wider PC-98 preservation community; both are included in the extraction
   commands above.

## 5. Reproduce

```sh
cd kn7000_mame
ISO=/home/fsanches/compartilhado/pc98_tdb/PC98Docs1stEd.iso
python3 tools/abv_extract.py iso  $ISO
python3 tools/abv_extract.py info $ISO 195548          # MM.ABV
python3 tools/abv_extract.py text $ISO 195548 -o MM.txt
python3 tools/abv_extract.py bmp  $ISO 195548 -o mmbmp # 238 figures + index.txt
```
