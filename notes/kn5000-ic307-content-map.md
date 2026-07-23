# KN5000 IC307 waveform ROM — complete content map + metadata decode

Author: autonomous ROM-byte analysis pass, 2026-07-23. Requested by Felipe Sanches.
**Read-only ROM analysis** — no `src/` edits, no MAME build/run. All figures produced with
stdlib Python over the raw dump (helper scripts kept in scratchpad, not committed).

Builds on and refines `notes/kn5000-waveform-rom-banking.md`, `notes/kn5000-wave-number.md`,
and `kn5000-docs/waveform-rom-format.md`. Where this note **corrects or sharpens** those, it
is called out.

Evidence labels: **MEASURED** (read directly from the bytes), **INFERRED** (deduction from
measurements), **SPECULATIVE** (educated guess, unproven).

File analysed: `kn7000-emulator/roms/kn5000/kn5000_waveform_rom.ic307`
4,194,304 bytes (0x400000), CRC 20ff4629, md5 d779ac5782c63d5e911bf5c6559c6bd6.
Loaded at MAME `waveform` region offset 0xC00000 (`kn5000.cpp:1070`).

---

## 0. TL;DR

* **Complete byte accounting — nothing unaccounted (MEASURED, sums to 4,194,304 exactly):**

  | Region | Range | Bytes | Contents |
  |---|---|---|---|
  | Index table | 0x000000–0x000317 | 792 | 198 entries × 4 |
  | Parameter records | 0x000318–0x001A2F | 5,912 | 198 variable-length records |
  | **PCM, page-0 (indexed)** | 0x001A30–0x0FEF60 | 1,037,616 | 186 unique waveforms, entries 0–190 |
  | **PCM, tail / pages 1–3 (un-indexed)** | 0x0FEF60–0x3FFFC0 | 3,149,920 | ~3 more MB of PCM the 16-bit index can't reach |
  | Fill | 0x3FFFC0–0x3FFFFF | 64 | 0xFF padding |

  There is **no fill other than the final 64 bytes**: the ROM is 97–99 % non-zero PCM across
  all 4 MB (64 KB-block density scan). The only "empty" bytes in the whole chip are the 64-byte
  0xFF tail plus three tiny 80-sample near-silence pads at page boundaries (§2.3).

* **The index only describes the first ~1 MB.** The 16-bit `wave_offset` field ×16 tops out at
  `0xFFFF*16 = 0xFFFF0`, so entries 0–190 cover 0x1A30–0xFEF60 (page 0). The upper **3 MB
  (0x0FEF60–0x3FFFC0) is real PCM that no index entry reaches** — the 7 tail entries (191–197)
  all point at its *start* (0xFEF60) and the rest is addressed by an external page/bank select
  the custom LSI applies. This confirms and localises the "upper-3 MB anomaly" flagged in the
  banking note. (MEASURED.)

* **Metadata fully decoded — and it carries MORE than the earlier "no tuning" verdict.**
  A record = `{uint16 wave_start}` + a list of `{value:8, flag:8}` words + a terminator.
  Decoded across all 198 records (§3):
  - **Key-zone split boundaries** — flag 0x00, value = key number (dominantly multiples of 8,
    descending). These define the multisample keyboard map. (MEASURED, strong.)
  - **Per-zone / per-key FINE-TUNE offsets** — flags 0x01/0x08/0x0A/0x11/0x13/0x1A/0x1C/0x23…,
    value clustered 0xEA–0xFF = small **signed-negative pitch trims** (0xFF=−1, 0xF0=−16).
    Records 180 and 181 are *pure* detune tables of 53 and 130 such entries. **So tuning DOES
    live in IC307**, as per-key detune deltas — a refinement of `kn5000-wave-number.md §3`
    which folded these into "envelope segments". (MEASURED.)
  - **Terminator** — flag 0xC0 (=0x80|0x40), value = the final zone's key boundary. (MEASURED.)
  - **Absolute root note: NOT stored.** The pitch origin is implied by zone placement + the
    firmware semitone pitch table, not an IC307 field. (MEASURED-absence, §3.4.)
  - **Loop start/end: NOT stored.** No field is wider than one byte; waves reach 1.5 M samples
    (needs ≥21-bit offsets); the flag vocabulary is a small structured set incompatible with
    embedded 16-bit offsets. The PCM *is* loopable (autocorr r=0.99, §2.2) but the chip must
    loop autonomously. (MEASURED-absence, §3.4.)

* **Multisample grouping is explicit in the zone boundaries (MEASURED, §4).** 198 entries →
  186 unique waveforms; the 12 "extra" entries are one waveform reused across transposed key
  zones. E.g. entries 191–197 share wave 0xFEF6 with split points stepping **+8 semitones per
  entry** (`56,40 → 64,48 → … → 104,88`); entries 185–190 share 0xFCA6 identically. This IS the
  "wave number → instrument+zone" map for those waves.

* **Undumped ROM model (INFERRED, §5):** IC304/305/306 are almost certainly **the same
  container** — a 198-ish-entry index + param records + signed-16-LE PCM + a ~3 MB page-addressed
  tail — each holding different instrument families. A faithful placeholder needs that structure,
  not fabricated timbres.

---

## 1. Index table — MEASURED, confirms prior work

198 entries × 4 bytes at offset 0, each `{uint16 param_ptr, uint16 wave_offset}` LE.
PCM byte address = `wave_offset × 16`.

* `entry0 = {param_ptr=0x0318, wave_offset=0x01A3}`. `0x0318 = 792 = 198×4` → the index is
  self-delimiting; entry0's param_ptr points at the first byte past the table. **198 confirmed.**
* All 198 `param_ptr` values are **monotonically non-decreasing**, 0x0318 … 0x1A26, all inside
  the param area. **All 198 `wave_offset×16` values are monotonically non-decreasing**,
  0x001A30 … 0x0FEF60 — no entry points backwards, none points outside 0..4 MB. (MEASURED.)
* Every record's first word equals its index `wave_offset` — **198/198 match** (redundant cache).

## 2. PCM regions

### 2.1 Page-0 indexed PCM (0x001A30–0x0FEF60, 1,037,616 bytes)

Signed 16-bit LE. 186 unique waveforms across index entries 0–190. All 198 chunks classify as
**"audio"** (non-trivial peak+RMS) — there are **no zero-length, silent, or degenerate entries**.
Full per-chunk table in §6.

* **Index 0 (0x1A30, 256 samples) = a mathematically near-perfect single sine cycle**:
  mean abs error 0.3 LSB, max 0.5 LSB from `32767·sin(2πi/256)`. The only single-cycle wave;
  test/fallback tone. (MEASURED — confirms docs.)
* All other 185 are **multi-cycle recordings**, 80 … tens-of-thousands of samples. Peaks reach
  full-scale (≈0x7FFF) on almost every chunk → the PCM is normalised. Most chunks start on a
  zero crossing (`z0=1`) but many do **not** end on one (`z1=0`) — consistent with samples that
  are meant to *loop* rather than one-shot.

### 2.2 The PCM is periodic (loopable) but no loop points are stored — MEASURED

Autocorrelation on chunk 64 (0x414D0, a long sustained tone) peaks at lag 92 with r = **0.988** —
a clean repeating period. So the waveforms are genuinely loopable pitched material; the *absence*
of loop metadata in the records (§3.4) means the tone-generator chip finds/loops the sustain
region itself. (Predict-then-check: predicted "multi-cycle, no clean loop" from the earlier note
→ **partial miss** — they DO have a strong short-term period; what's true is that the loop
*boundaries* aren't in IC307, not that the audio is aperiodic.)

### 2.3 The un-indexed 3 MB tail (0x0FEF60–0x3FFFC0, 3,149,920 bytes) — MEASURED + INFERRED

Index literal view: entries 191–197 all carry `wave_offset=0xFEF6` → they all point at
**0x0FEF60**, and being the last entries, the chunk "runs to the FF pad" = the whole 3 MB.
So a naive index walk assigns this entire 3 MB to one shared waveform (the docs' "~1.5 M-sample"
wave). That is the honest *index-literal* accounting but is not the physical story:

* The tail is **continuous dense PCM** (RMS 4k–20k throughout, never silent for more than ~150
  samples) — it is not one 36-second note; it is *more waveforms* the index cannot name.
* **Three near-silence pads sit exactly 160 bytes (80 samples) below each 1 MB boundary:**
  audio ends at **0x0FFF60, 0x1FFF60, 0x2FFF60**, each padding up to 0x100000 / 0x200000 /
  0x300000. Three identical occurrences at the same offset-relative-to-a-power-of-two is a
  real structural signal, not coincidence. **INFERRED: IC307 is organised as 4 × ~1 MB pages;**
  page 0 is the indexed region, pages 1–3 are additional PCM addressed by a coarse page/bank
  select outside the 16-bit `wave_offset` (the `tonerec[+0x1a]&0xC0` candidate from the banking
  note is the prime suspect — 2 bits = 4 pages = 4 chips).
* The apparent "index tables" at 0x100000 / 0x200000 / 0x300000 noted earlier are **coincidental**:
  those offsets contain full-amplitude audio (RMS ≈10 k, hundreds of sign-flips per 1 KB), not
  low-valued table data. The "1072 monotonic entries at 0x200000" is a rising-audio artifact.
  (MEASURED — retires that red herring.)

### 2.4 Fill (0x3FFFC0–0x3FFFFF, 64 bytes)

64 bytes of 0xFF. The **only** true fill in the ROM. (MEASURED.)

## 3. Parameter records — full decode (MEASURED)

Record `i` spans `param_ptr[i]` → next-greater `param_ptr` (param_ptrs are monotonic). Layout:

```
uint16 wave_start          ; == the index wave_offset (redundant), 198/198 verified
{ value:8, flag:8 } × N    ; little-endian word = (value | flag<<8)
                           ; terminated by a flag with bit7|bit6 set (0xC0 family)
```

Record-size histogram (bytes): 2×1, 4×31, 6×25, 8×44, 10×46, 12×6, 14×14, then a long tail of
one-offs up to **850 bytes** (record 173). Small records = a few zone splits; the big records
(173–181, 226–850 B) = long per-key detune tables.

### 3.1 flag = 0x00 → key-zone split boundary

345 occurrences. Values dominated by **multiples of 8** (0x40×103, 0x30×81, 0x20×60, 0x38×23,
0x28×22, 0x18×8, 0x48×6, 0x50×4…), listed **descending** within a record. These are the
key-split points of the multisample map. (A handful exceed 0x7F, so it is a "key/split index",
not a pure 0–127 MIDI field.) Example — entry 2 `wave_start=0x0273`, splits `64,48,32`.

### 3.2 flags 0x01/0x08/0x0A/0x11/0x13/0x1A/0x1C/0x23 (+ minor 0x02/09/0B/10/12/14/19/1B/1D/22/24/25/2B/2C/2D) → per-zone FINE-TUNE

By far the bulk of all pairs (0x08 n=542, 0x01 n=506, 0x1c n=234, 0x23 n=235, 0x0a n=239,
0x11 n=219, 0x13 n=123, 0x1a n=100 …). **Values cluster tightly in 0xEA–0xFF** = signed bytes
−1 … −22. Read as **small negative pitch/tuning trims** applied per key-zone. Decisive evidence
they are tuning, not audio-offsets: records **180** (`wave_start=0xF4BF`, 53 tune pairs, no
zones) and **181** (`0xF604`, 130 tune pairs) are *entirely* such offsets — a per-key detune
table spanning the keyboard, exactly what a multisampled instrument needs to stay in tune.
The differing high-nibble (0x0_, 0x1_, 0x2_) plus low bits look like a (zone-group, sub-index)
tag; not fully pinned (§7), but the *value* semantics (signed fine-tune) are clear. (MEASURED.)

### 3.3 flag = 0xC0 family (0xC0 n=83, 0xC5 n=7; also bare 0x80 n=13, 0x40 n=9) → terminator/markers

`0xC0 = 0x80|0x40`. Value 0x00–0x40 = the final zone's key boundary carried on the terminator
word. Bare 0x40 (mid-marker) and 0x80 (end) appear rarely inside long records. This matches the
docs' 0x40/0x80/0xC0 marker scheme. (MEASURED.)

### 3.4 Root note / loop — the explicit absence proof (MEASURED)

* **Root note (absolute):** there is no per-record byte or word that reads as a single MIDI root.
  The only note-valued field (flag 0x00) is a *list* of split boundaries, and a waveform is reused
  under *different* boundaries by different entries (§4) — incompatible with a fixed root. Pitch
  origin therefore comes from the firmware semitone pitch table (`kn5000-docs` §Sample Rate),
  not IC307.
* **Loop start/end:** would need ≥21-bit sample offsets (waves reach 0xFEF60+ region, 1.5 M
  samples). **Every field in every record is a single byte**; there is no 2-, 3- or 4-byte field
  anywhere. If loop offsets were packed as byte pairs the `flag` bytes would take high-entropy
  arbitrary values; instead flags are a small structured vocabulary (~40 symbols, dominated by
  <0x30 and the 0x40/0x80/0xC0 markers). So loop points are provably **not** encoded in the
  records. (MEASURED-absence — confirms the banking note and the docs' leaning.)

## 4. Multisample grouping — MEASURED

198 index entries → **186 unique wave offsets** → only **3 shared-offset groups**:
`{182,183}` (wave 0xF8B6), `{185…190}` (0xFCA6), `{191…197}` (0xFEF6). The zone boundaries make
the multisample structure explicit — successive entries reuse one recording, each shifted **+8
semitones**:

```
185 fca6  64 48 32 16      191 fef6  56 40
186 fca6  72 56 40 24      192 fef6  64 48
187 fca6  80 64 48 32      193 fef6  72 56
188 fca6  88 72 56 40      194 fef6  80 64
189 fca6  96 80 64 48      195 fef6  88 72
190 fca6 104 88 72 56      196 fef6  96 80
                           197 fef6 104 88 0
```

This is a textbook keyboard multisample map: one waveform stretched across the keyboard in
octave-ish zones, each zone re-pitched, with the per-key detune tables (§3.2) trimming residual
error. Adjacent short-record runs with related lengths/timbres (e.g. entries 1–3 all split
`64,48,32` over three similar ~1–2.8 KB waves; entries 20–33 a run of ~2 KB chunks) are the
zones of single split instruments. The finer "which named preset" mapping is NOT in IC307 —
it is in the firmware key-zone resolver + Table Data ROM (see `kn5000-wave-number.md`).

## 5. Model of the undumped ROMs IC304/305/306 — INFERRED / SPECULATIVE

IC307 is the one dumped, hardware-rooted example of a KN5000 wave bank. From its format the three
NO_DUMP chips are modelled as:

* **Same container (INFERRED, high confidence):** a header index at offset 0
  (`{param_ptr, wave_offset}` × ~200, self-delimiting via `entry0.param_ptr = count×4`), a
  variable-length parameter-record block, then signed-16-LE PCM with `wave_offset×16` addressing,
  a **~3 MB page-addressed tail**, and a small 0xFF pad at 0x3FFFC0. Each chip is one selectable
  ~4-page bank.
* **Different instrument families (SPECULATIVE):** IC307's 186 waves cannot cover the KN5000's
  hundreds of presets, so IC304–306 hold the remaining families (pianos/keys, guitars/basses,
  strings/pads, brass/reeds, drums…). Which chip holds which is unknown — it depends on the
  unresolved 2-bit page/bank select (§2.3).
* **Faithful placeholder spec (for a future drop-in):** replicate the *structure*, not invented
  content — a 198-entry self-delimiting index, valid 1-zone param records (`wave_start` + a
  0xC0 terminator), signed-16-LE PCM (index 0 = a real 256-sample sine like IC307), 0xFF pad.
  Load `BAD_DUMP`. When a real chip is dumped it replaces the file byte-for-byte with zero code
  change. (Matches the banking note's Option A; this note supplies the measured field semantics
  it should carry.)

## 6. Full 198-chunk table (MEASURED)

Columns: idx, param_ptr, wave_offset, start, end, bytes, samples, class, peak, rms, dc,
z0/z1 (starts/ends on zero-crossing), dup (shares a wave_offset with the previous entry).
`end` = next strictly-greater `wave_offset×16` (last group runs to the 0xFF pad).

```
  0 0x0318 0x01a3 00001a30-00001c30      512     256 audio pk32767 rms23170 dc     0 z10
  1 0x031a 0x01c3 00001c30-00002730     2816    1408 audio pk32753 rms11815 dc   126 z10
  2 0x0324 0x0273 00002730-00003030     2304    1152 audio pk32762 rms15584 dc   159 z10
  3 0x032c 0x0303 00003030-000035b0     1408     704 audio pk32767 rms13900 dc   -19 z10
  4 0x0336 0x035b 000035b0-000039b0     1024     512 audio pk32690 rms10229 dc   107 z10
  5 0x033a 0x039b 000039b0-00003eb0     1280     640 audio pk31040 rms 9816 dc  -327 z10
  6 0x033e 0x03eb 00003eb0-00004230      896     448 audio pk31118 rms11102 dc    60 z10
  7 0x0342 0x0423 00004230-00004370      320     160 audio pk28256 rms13242 dc   292 z10
  8 0x0346 0x0437 00004370-00004410      160      80 audio pk30307 rms12795 dc   936 z00
  9 0x034a 0x0441 00004410-00004510      256     128 audio pk31083 rms11941 dc  -188 z00
 10 0x0350 0x0451 00004510-00004a10     1280     640 audio pk31973 rms 9056 dc    22 z10
 11 0x0354 0x04a1 00004a10-00004f10     1280     640 audio pk32429 rms14460 dc    36 z10
 12 0x0358 0x04f1 00004f10-00005290      896     448 audio pk30142 rms15091 dc   358 z10
 13 0x035c 0x0529 00005290-00005690     1024     512 audio pk30766 rms14184 dc   583 z10
 14 0x0360 0x0569 00005690-00005c10     1408     704 audio pk25254 rms11290 dc    73 z10
 15 0x0364 0x05c1 00005c10-00005fd0      960     480 audio pk21753 rms10032 dc   -57 z10
 16 0x0368 0x05fd 00005fd0-000064d0     1280     640 audio pk31651 rms15020 dc   -62 z10
 17 0x036c 0x064d 000064d0-00006bd0     1792     896 audio pk32643 rms16595 dc  -366 z10
 18 0x0370 0x06bd 00006bd0-000070d0     1280     640 audio pk32578 rms19563 dc  -353 z11
 19 0x0374 0x070d 000070d0-000073d0      768     384 audio pk32767 rms14480 dc   748 z10
 20 0x0378 0x073d 000073d0-000082d0     3840    1920 audio pk31248 rms 9773 dc   156 z10
 21 0x037e 0x082d 000082d0-00008ad0     2048    1024 audio pk27801 rms 7422 dc   125 z10
 22 0x0384 0x08ad 00008ad0-000092d0     2048    1024 audio pk25776 rms 7865 dc   121 z10
 23 0x038a 0x092d 000092d0-00009750     1152     576 audio pk26003 rms 7069 dc    89 z10
 24 0x0390 0x0975 00009750-00009d50     1536     768 audio pk26778 rms 8468 dc    84 z10
 25 0x0396 0x09d5 00009d50-0000a650     2304    1152 audio pk32748 rms 6495 dc   -28 z10
 26 0x039c 0x0a65 0000a650-0000b190     2880    1440 audio pk25837 rms 6048 dc    27 z10
 27 0x03a2 0x0b19 0000b190-0000c090     3840    1920 audio pk31382 rms 9160 dc   191 z10
 28 0x03a8 0x0c09 0000c090-0000c890     2048    1024 audio pk27701 rms 7602 dc   161 z10
 29 0x03ae 0x0c89 0000c890-0000d090     2048    1024 audio pk25960 rms 7287 dc   184 z10
 30 0x03b4 0x0d09 0000d090-0000d510     1152     576 audio pk30148 rms 7960 dc   171 z10
 31 0x03ba 0x0d51 0000d510-0000db10     1536     768 audio pk24044 rms 7581 dc   172 z10
 32 0x03c0 0x0db1 0000db10-0000e410     2304    1152 audio pk32573 rms 6754 dc   116 z10
 33 0x03c6 0x0e41 0000e410-0000ef50     2880    1440 audio pk29149 rms 6915 dc   127 z10
 34 0x03cc 0x0ef5 0000ef50-00012b60    15376    7688 audio pk31869 rms11231 dc   -77 z10
 35 0x03d0 0x12b6 00012b60-00015f70    13328    6664 audio pk32638 rms 9181 dc   -69 z10
 36 0x03d6 0x15f7 00015f70-00019100    12688    6344 audio pk32118 rms10463 dc   -85 z10
 37 0x03de 0x1910 00019100-0001ba50    10576    5288 audio pk32636 rms11668 dc   -69 z00
 38 0x03ec 0x1ba5 0001ba50-0001e320    10448    5224 audio pk32629 rms10897 dc   -63 z11
 39 0x03f8 0x1e32 0001e320-00022870    17744    8872 audio pk32127 rms11974 dc  -119 z00
 40 0x0478 0x2287 00022870-00025e90    13856    6928 audio pk32599 rms10399 dc    50 z10
 41 0x047c 0x25e9 00025e90-000290b0    12832    6416 audio pk32094 rms 9719 dc    -1 z10
 42 0x0480 0x290b 000290b0-0002a8b0     6144    3072 audio pk32422 rms 9801 dc    35 z10
 43 0x0484 0x2a8b 0002a8b0-0002c3b0     6912    3456 audio pk32713 rms 8235 dc     3 z10
 44 0x0488 0x2c3b 0002c3b0-0002d6b0     4864    2432 audio pk29154 rms 8334 dc    14 z10
 45 0x048c 0x2d6b 0002d6b0-0002f1b0     6912    3456 audio pk29767 rms 8314 dc    17 z10
 46 0x0490 0x2f1b 0002f1b0-000304b0     4864    2432 audio pk32120 rms11043 dc    30 z10
 47 0x0496 0x304b 000304b0-00033ad0    13856    6928 audio pk32734 rms 9702 dc    40 z10
 48 0x049a 0x33ad 00033ad0-00036cf0    12832    6416 audio pk32556 rms10598 dc    -4 z10
 49 0x049e 0x36cf 00036cf0-000384f0     6144    3072 audio pk32408 rms 9939 dc    31 z10
 50 0x04a2 0x384f 000384f0-00039ff0     6912    3456 audio pk32767 rms 8222 dc    -5 z10
 51 0x04a6 0x39ff 00039ff0-0003b2f0     4864    2432 audio pk27815 rms 8910 dc    16 z10
 52 0x04aa 0x3b2f 0003b2f0-0003cdf0     6912    3456 audio pk29505 rms10835 dc    10 z10
 53 0x04ae 0x3cdf 0003cdf0-0003e0f0     4864    2432 audio pk32636 rms12649 dc   107 z00
 54 0x04b8 0x3e0f 0003e0f0-0003edf0     3328    1664 audio pk32711 rms 5881 dc   -45 z10
 55 0x04be 0x3edf 0003edf0-0003f670     2176    1088 audio pk32724 rms 9953 dc    59 z10
 56 0x04c4 0x3f67 0003f670-0003fcf0     1664     832 audio pk32654 rms 8054 dc    98 z10
 57 0x04ca 0x3fcf 0003fcf0-000404f0     2048    1024 audio pk24673 rms 5428 dc    32 z10
 58 0x04d0 0x404f 000404f0-000406f0      512     256 audio pk26469 rms10447 dc  -297 z10
 59 0x04d8 0x406f 000406f0-00040870      384     192 audio pk32634 rms12857 dc   822 z01
 60 0x04e0 0x4087 00040870-00040ab0      576     288 audio pk31099 rms13899 dc   230 z10
 61 0x04e8 0x40ab 00040ab0-00040bd0      288     144 audio pk29298 rms10131 dc   458 z10
 62 0x04f0 0x40bd 00040bd0-00041150     1408     704 audio pk32767 rms 5614 dc   -80 z10
 63 0x04f6 0x4115 00041150-000414d0      896     448 audio pk32767 rms 7522 dc   -94 z10
 64 0x04fc 0x414d 000414d0-0004c5f0    45344   22672 audio pk32560 rms 7688 dc   -63 z10   (period~92, r0.99)
 65 0x0500 0x4c5f 0004c5f0-00051800    21008   10504 audio pk32632 rms 9124 dc   -85 z00
 66 0x0516 0x5180 00051800-00058050    26704   13352 audio pk32110 rms10053 dc   -47 z00
 67 0x0530 0x5805 00058050-0005c6e0    18064    9032 audio pk32606 rms10016 dc   -63 z10
 68 0x0540 0x5c6e 0005c6e0-000606f0    16400    8200 audio pk32362 rms10572 dc   -46 z10
 69 0x055e 0x606f 000606f0-00072c10    75040   37520 audio pk32452 rms12631 dc   -51 z10  (largest single wave)
 70 0x0564 0x72c1 00072c10-0007a330    30496   15248 audio pk32683 rms 9530 dc    -3 z10
 71 0x0568 0x7a33 0007a330-0007d540    12816    6408 audio pk31095 rms 9553 dc    22 z10
 72 0x0570 0x7d54 0007d540-00080110    11216    5608 audio pk32629 rms11028 dc    67 z00
 73 0x0578 0x8011 00080110-000829c0    10416    5208 audio pk32618 rms11976 dc    52 z10
 74 0x0584 0x829c 000829c0-00089650    27792   13896 audio pk32633 rms12185 dc    80 z10
 75 0x059a 0x8965 00089650-0008ae50     6144    3072 audio pk32758 rms 8800 dc   106 z10
 76 0x05a2 0x8ae5 0008ae50-0008ec50    15872    7936 audio pk32688 rms10465 dc    66 z10
 77 0x05aa 0x8ec5 0008ec50-00091650    10752    5376 audio pk32705 rms12850 dc    33 z10
 78 0x05b2 0x9165 00091650-00092750     4352    2176 audio pk32487 rms 3902 dc     7 z11
 79 0x05ba 0x9275 00092750-00093a50     4864    2432 audio pk32536 rms 5762 dc     3 z10
 80 0x05c2 0x93a5 00093a50-00094f50     5376    2688 audio pk32691 rms 6835 dc    23 z10
 81 0x05ca 0x94f5 00094f50-00096350     5120    2560 audio pk32744 rms 6634 dc    -4 z10
 82 0x05d4 0x9635 00096350-00096fd0     3200    1600 audio pk32200 rms 9105 dc   -40 z10
 83 0x05de 0x96fd 00096fd0-00097ad0     2816    1408 audio pk32673 rms10380 dc   -11 z10
 84 0x05e8 0x97ad 00097ad0-000984d0     2560    1280 audio pk32539 rms 9864 dc     7 z10
 85 0x05f0 0x984d 000984d0-000991d0     3328    1664 audio pk32742 rms10105 dc     7 z10
 86 0x05f8 0x991d 000991d0-000998d0     1792     896 audio pk32457 rms11098 dc   -62 z10
 87 0x0600 0x998d 000998d0-0009a0d0     2048    1024 audio pk32531 rms10383 dc   -57 z10
 88 0x0608 0x9a0d 0009a0d0-0009b1d0     4352    2176 audio pk32551 rms 6881 dc     7 z10
 89 0x0612 0x9b1d 0009b1d0-0009c3d0     4608    2304 audio pk32568 rms 7118 dc   -80 z10
 90 0x061c 0x9c3d 0009c3d0-0009cdd0     2560    1280 audio pk32508 rms 9141 dc   -10 z10
 91 0x0626 0x9cdd 0009cdd0-0009d950     2944    1472 audio pk32587 rms 9421 dc    43 z10
 92 0x0630 0x9d95 0009d950-0009e6d0     3456    1728 audio pk32767 rms 9230 dc    52 z10
 93 0x063a 0x9e6d 0009e6d0-0009f550     3712    1856 audio pk32767 rms 8366 dc    82 z10
 94 0x0644 0x9f55 0009f550-0009fd50     2048    1024 audio pk32710 rms11247 dc   132 z10
 95 0x064c 0x9fd5 0009fd50-000a0650     2304    1152 audio pk32733 rms10737 dc   -77 z10
 96 0x0656 0xa065 000a0650-000a10d0     2688    1344 audio pk32543 rms11994 dc   -56 z10
 97 0x0660 0xa10d 000a10d0-000a1e50     3456    1728 audio pk32767 rms 8411 dc   -14 z10
 98 0x066a 0xa1e5 000a1e50-000a2ed0     4224    2112 audio pk32767 rms 7578 dc    28 z10
 99 0x0674 0xa2ed 000a2ed0-000a37d0     2304    1152 audio pk31869 rms12810 dc   -34 z10
100 0x0682 0xa37d 000a37d0-000a4490     3264    1632 audio pk32638 rms13635 dc   228 z10
101 0x0690 0xa449 000a4490-000a4d50     2240    1120 audio pk32639 rms14079 dc   -86 z10
102 0x069e 0xa4d5 000a4d50-000a5750     2560    1280 audio pk32767 rms 7159 dc    21 z10
103 0x06a8 0xa575 000a5750-000a6150     2560    1280 audio pk32767 rms 7481 dc    20 z10
104 0x06b2 0xa615 000a6150-000a7950     6144    3072 audio pk32686 rms 8816 dc   -26 z10
105 0x06bc 0xa795 000a7950-000a8650     3328    1664 audio pk32706 rms 9747 dc    14 z10
106 0x06c6 0xa865 000a8650-000a9350     3328    1664 audio pk32767 rms 7795 dc   -40 z10
107 0x06ce 0xa935 000a9350-000aa250     3840    1920 audio pk32767 rms 7397 dc   -33 z10
108 0x06d6 0xaa25 000aa250-000aabd0     2432    1216 audio pk32331 rms 8842 dc   -37 z10
109 0x06e0 0xaabd 000aabd0-000ab650     2688    1344 audio pk32114 rms 9342 dc   -44 z10
110 0x06e8 0xab65 000ab650-000ac3d0     3456    1728 audio pk32696 rms10237 dc    51 z10
111 0x06f2 0xac3d 000ac3d0-000ad3d0     4096    2048 audio pk32149 rms10760 dc    50 z10
112 0x06fc 0xad3d 000ad3d0-000adc90     2240    1120 audio pk32767 rms10391 dc   -21 z10
113 0x0704 0xadc9 000adc90-000aef90     4864    2432 audio pk32634 rms 8935 dc    -1 z10
114 0x070c 0xaef9 000aef90-000af6d0     1856     928 audio pk32119 rms 9953 dc  -157 z10
115 0x071a 0xaf6d 000af6d0-000afc50     1408     704 audio pk32123 rms11482 dc   175 z10
116 0x0728 0xafc5 000afc50-000b02d0     1664     832 audio pk29310 rms10147 dc   164 z10
117 0x0736 0xb02d 000b02d0-000b0ad0     2048    1024 audio pk32640 rms13319 dc  -317 z10
118 0x0744 0xb0ad 000b0ad0-000b0ed0     1024     512 audio pk32109 rms13310 dc     5 z10
119 0x0752 0xb0ed 000b0ed0-000b13f0     1312     656 audio pk31613 rms14701 dc  -109 z10
120 0x0760 0xb13f 000b13f0-000b20b0     3264    1632 audio pk32385 rms11069 dc   -52 z10
121 0x076a 0xb20b 000b20b0-000b3eb0     7680    3840 audio pk32440 rms 4848 dc    12 z10
122 0x0772 0xb3eb 000b3eb0-000b72b0    13312    6656 audio pk32767 rms 6827 dc   -12 z10
123 0x077c 0xb72b 000b72b0-000b84b0     4608    2304 audio pk31815 rms 6832 dc    73 z10
124 0x0784 0xb84b 000b84b0-000b97b0     4864    2432 audio pk32767 rms 6491 dc    67 z10
125 0x078c 0xb97b 000b97b0-000ba8b0     4352    2176 audio pk32767 rms 6542 dc    11 z10
126 0x0796 0xba8b 000ba8b0-000bb3b0     2816    1408 audio pk32214 rms 6625 dc    16 z10
127 0x079e 0xbb3b 000bb3b0-000bbfb0     3072    1536 audio pk32659 rms 6571 dc   -12 z10
128 0x07a6 0xbbfb 000bbfb0-000bce30     3712    1856 audio pk32607 rms 7931 dc    47 z10
129 0x07b0 0xbce3 000bce30-000bde30     4096    2048 audio pk32526 rms 7034 dc    66 z10
130 0x07b8 0xbde3 000bde30-000bf930     6912    3456 audio pk32767 rms 7114 dc    26 z10
131 0x07c2 0xbf93 000bf930-000c1430     6912    3456 audio pk32631 rms 6532 dc    33 z10
132 0x07cc 0xc143 000c1430-000c2a30     5632    2816 audio pk32707 rms 5377 dc    -9 z10
133 0x07d4 0xc2a3 000c2a30-000c31b0     1920     960 audio pk32635 rms14128 dc   -74 z10
134 0x07e0 0xc31b 000c31b0-000c3a30     2176    1088 audio pk32126 rms13031 dc  -234 z10
135 0x07ec 0xc3a3 000c3a30-000c3ef0     1216     608 audio pk31615 rms13641 dc   149 z10
136 0x07f8 0xc3ef 000c3ef0-000c54f0     5632    2816 audio pk24469 rms 5436 dc    39 z10
137 0x0800 0xc54f 000c54f0-000c6d70     6272    3136 audio pk32425 rms 9169 dc    56 z10
138 0x0808 0xc6d7 000c6d70-000c7a70     3328    1664 audio pk32075 rms 8108 dc    23 z10
139 0x0810 0xc7a7 000c7a70-000c8a70     4096    2048 audio pk32458 rms 8942 dc   -23 z10
140 0x081a 0xc8a7 000c8a70-000c9df0     4992    2496 audio pk32767 rms 7932 dc    38 z10
141 0x0822 0xc9df 000c9df0-000cb370     5504    2752 audio pk32765 rms 8378 dc    -9 z10
142 0x0828 0xcb37 000cb370-000cb970     1536     768 audio pk32767 rms10150 dc    32 z10
143 0x0830 0xcb97 000cb970-000cbf70     1536     768 audio pk32767 rms 8681 dc    -4 z10
144 0x0838 0xcbf7 000cbf70-000cd470     5376    2688 audio pk32677 rms 7895 dc    -2 z10
145 0x0842 0xcd47 000cd470-000cec70     6144    3072 audio pk32767 rms 8218 dc    41 z10
146 0x084c 0xcec7 000cec70-000cf970     3328    1664 audio pk32382 rms 8519 dc   296 z10
147 0x085a 0xcf97 000cf970-000d0030     1728     864 audio pk32126 rms12050 dc  -205 z10
148 0x0868 0xd003 000d0030-000d0830     2048    1024 audio pk32374 rms11200 dc  -202 z10
149 0x0876 0xd083 000d0830-000d10f0     2240    1120 audio pk32122 rms11126 dc  -142 z10
150 0x0884 0xd10f 000d10f0-000d24f0     5120    2560 audio pk32608 rms 8654 dc    48 z10
151 0x088e 0xd24f 000d24f0-000d42f0     7680    3840 audio pk32767 rms12515 dc    50 z10
152 0x0898 0xd42f 000d42f0-000d60f0     7680    3840 audio pk32711 rms13012 dc    55 z10
153 0x08a2 0xd60f 000d60f0-000d76e0     5616    2808 audio pk30073 rms10022 dc    53 z00
154 0x08b4 0xd76e 000d76e0-000d8cd0     5616    2808 audio pk32708 rms10459 dc    75 z00
155 0x08f4 0xd8cd 000d8cd0-000da2d0     5632    2816 audio pk29803 rms 6123 dc    27 z10
156 0x090e 0xda2d 000da2d0-000db300     4144    2072 audio pk24673 rms 5484 dc    13 z01
157 0x0916 0xdb30 000db300-000db5c0      704     352 audio pk30580 rms10096 dc    54 z00
158 0x098e 0xdb5c 000db5c0-000dc580     4032    2016 audio pk30841 rms 9662 dc   -36 z00
159 0x09fe 0xdc58 000dc580-000ddab0     5424    2712 audio pk32624 rms 9680 dc   -34 z01
160 0x0a48 0xddab 000ddab0-000ddc50      416     208 audio pk28782 rms10158 dc   684 z01
161 0x0a52 0xddc5 000ddc50-000dde30      480     240 audio pk32627 rms12647 dc   359 z00
162 0x0a96 0xdde3 000dde30-000df260     5168    2584 audio pk32610 rms11660 dc    26 z01
163 0x0ad4 0xdf26 000df260-000dfba0     2368    1184 audio pk32300 rms 9174 dc    95 z01
164 0x0ae0 0xdfba 000dfba0-000dff20      896     448 audio pk32378 rms15718 dc  -735 z01
165 0x0afa 0xdff2 000dff20-000e0720     2048    1024 audio pk32633 rms 7425 dc   -47 z11
166 0x0afe 0xe072 000e0720-000e0fd0     2224    1112 audio pk32358 rms12459 dc  -210 z01
167 0x0b30 0xe0fd 000e0fd0-000e1880     2224    1112 audio pk31616 rms12442 dc  -235 z11
168 0x0b54 0xe188 000e1880-000e29d0     4432    2216 audio pk32285 rms10474 dc  -112 z01
169 0x0bac 0xe29d 000e29d0-000e3b20     4432    2216 audio pk32094 rms11056 dc  -267 z01
170 0x0c08 0xe3b2 000e3b20-000e50c0     5536    2768 audio pk32368 rms10300 dc   -43 z01
171 0x0c82 0xe50c 000e50c0-000e5b90     2768    1384 audio pk30547 rms11373 dc  -466 z01
172 0x0cac 0xe5b9 000e5b90-000e6320     1936     968 audio pk32602 rms15226 dc    16 z01
173 0x0cc6 0xe632 000e6320-000e7c20     6400    3200 audio pk32374 rms12003 dc    24 z10  (record 850B: detune table)
174 0x1018 0xe7c2 000e7c20-000e9520     6400    3200 audio pk32634 rms12248 dc  -147 z00  (record 702B)
175 0x12d6 0xe952 000e9520-000eb310     7664    3832 audio pk32369 rms12115 dc  -141 z00  (record 554B)
176 0x1500 0xeb31 000eb310-000eec30    14624    7312 audio pk32355 rms11023 dc  -149 z01  (record 346B)
177 0x165a 0xeec3 000eec30-000f0840     7184    3592 audio pk32363 rms11595 dc   -73 z00
178 0x16e6 0xf084 000f0840-000f2bd0     9104    4552 audio pk32615 rms10703 dc    34 z00
179 0x1748 0xf2bd 000f2bd0-000f4bf0     8224    4112 audio pk32604 rms12766 dc    34 z00  (record 226B)
180 0x182a 0xf4bf 000f4bf0-000f6040     5200    2600 audio pk32636 rms12178 dc   -11 z11  (record: 53 detune-only)
181 0x1896 0xf604 000f6040-000f8b60    11040    5520 audio pk32620 rms11779 dc     5 z00  (record 262B: 130 detune-only)
182 0x199c 0xf8b6 000f8b60-000fa660     6912    3456 audio pk32749 rms10227 dc   -40 z10
183 0x19a6 0xf8b6 000f8b60-000fa660     6912    3456 audio pk32749 rms10227 dc   -40 z10 DUP
184 0x19b0 0xfa66 000fa660-000fca60     9216    4608 audio pk32766 rms11983 dc   -29 z10
185 0x19ba 0xfca6 000fca60-000fef60     9472    4736 audio pk32752 rms12091 dc    -0 z10
186 0x19c4 0xfca6 000fca60-000fef60     9472    4736 audio pk32752 rms12091 dc    -0 z10 DUP
187 0x19ce 0xfca6 000fca60-000fef60     9472    4736 audio pk32752 rms12091 dc    -0 z10 DUP
188 0x19d8 0xfca6 000fca60-000fef60     9472    4736 audio pk32752 rms12091 dc    -0 z10 DUP
189 0x19e2 0xfca6 000fca60-000fef60     9472    4736 audio pk32752 rms12091 dc    -0 z10 DUP
190 0x19ec 0xfca6 000fca60-000fef60     9472    4736 audio pk32752 rms12091 dc    -0 z10 DUP
191 0x19f6 0xfef6 000fef60-003fffc0  3149920 1574960 audio pk32767 rms11061 dc    13 z10 (=3MB tail, pages 1-3)
192 0x19fe 0xfef6 000fef60-003fffc0  3149920 1574960 DUP
193 0x1a06 0xfef6 000fef60-003fffc0  3149920 1574960 DUP
194 0x1a0e 0xfef6 000fef60-003fffc0  3149920 1574960 DUP
195 0x1a16 0xfef6 000fef60-003fffc0  3149920 1574960 DUP
196 0x1a1e 0xfef6 000fef60-003fffc0  3149920 1574960 DUP
197 0x1a26 0xfef6 000fef60-003fffc0  3149920 1574960 DUP
```

## 7. Still-unexplained regions / fields (the honest open list)

1. **The 3 MB un-indexed tail's addressing (§2.3).** We can see it is 3 pages of PCM ending in
   1 MB-aligned silence pads, but the mechanism that selects a page (the 2-bit
   `tonerec[+0x1a]&0xC0` candidate) is unproven, and there is **no in-IC307 index that names
   the individual waves inside pages 1–3**. This is the single largest unexplained region.
2. **The fine-tune flag's high bits.** The *value* semantics (signed negative trim) are solid,
   but the flag grouping (0x0_/0x1_/0x2_ families, low-bit sub-index) is only partially read —
   it may encode which oscillator/zone-group the trim applies to. Not pinned.
3. **flag 0xC5 (value 0x00, n=7) and the bare 0x40/0x80 markers** inside long records — treated
   as terminator/marker variants but their exact distinction from 0xC0 is unconfirmed.
4. **A few flag-0x00 values exceed 0x7F** (e.g. 0x80, and higher in long records) — so the
   "key split = MIDI note" reading is approximate; those out-of-range values are unexplained
   (could be zone-count headers or a different sub-field).
5. **The base sample rate** is not stored in IC307 (open in the docs) — playback rate comes
   entirely from the firmware pitch register.
6. **Why the firmware resolver emits wave 0 for every instrument** (from `kn5000-wave-number.md`)
   — orthogonal to the ROM content, but it means none of the rich structure mapped here is
   currently exercised by the emulated firmware. That is a main-CPU/Table-Data-ROM task.

---

### Corrections to prior docs this note makes
* `kn5000-docs/waveform-rom-format.md` should note: (a) the "very long wave" shared by 7 entries
  is really the **un-indexed 3 MB page tail**, not one 1.5 M-sample instrument; (b) the param
  records **do** carry per-key fine-tune (records 180/181 are pure detune tables) — the "does the
  format encode tuning?" open question is answered *yes for fine-tune, no for root/loop*; (c) the
  1 MB page-boundary silence pads (0x0FFF60/0x1FFF60/0x2FFF60) evidence a 4-page organisation.
* `kn5000-wave-number.md §3` "NO root/tuning/loop" → sharpen to "**no root, no loop; fine-tune
  YES** (per-key signed-byte detune, flags 0x01/0x08/…)".
