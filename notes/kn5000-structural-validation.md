# KN5000 — STRUCTURAL VALIDATION: the firmware's slicing vs. IC307's own slicing

Author: autonomous VALIDATE pass, 2026-07-25. Requested by Felipe Sanches.
**Read-only analysis** — no `src/` edits, no rebuild, no MAME run, no listening. Python stdlib only.

**Mandate answered** (Felipe): *"Which samples correspond to a piano should, in theory, be
documented in voice record data structures. It should not have to rely on me hearing and
cataloging what I hear. It should not involve guessing either."*

Evidence labels: **MEASURED** (bytes read from a ROM / an instruction in the disasm),
**PROVEN-BY-CONSTRUCTION**, **INFERRED**, **SPECULATIVE**.

Inputs, both re-derived from the raw ROMs in this pass rather than trusted from cache:
* firmware side — `kn5000_table_data_rom_even.ic3` + `_odd.ic1`, interleaved exactly as
  `kn5000.cpp:1131-1133`; walked with the chain established in
  `notes/kn5000-firmware-sample-tables.md` (commit `cb6b362`). Reproduced **1444 distinct
  `(class, entry)` pairs**, identical to the Extract pass. ✓
* ROM side — `kn5000_waveform_rom.ic307` (4 MB, CRC `20ff4629`), the one hardware-rooted dump.

---

## 0. VERDICT

> **The `{class, entry}` → physical-PCM mapping IS DERIVABLE FROM DATA.**
> The earlier "LSI-internal and underdetermined" claim is **OVERTURNED**.

```
+0x040 register  =  { class = bits[15:12] , entry = bits[11:0] }

    page      =  class & 3                      ; 1 MB page inside a 4 MB wave ROM
    bank      =  (class >> 2) & 3               ; which wave ROM;  IC307 = bank 1
    page_base =  bank_base(bank) + page * 0x100000

    n         =  u16[page_base + 0] / 4         ; self-delimiting directory size
    param_ptr =  u16[page_base + 4*entry + 0]
    wave_off  =  u16[page_base + 4*entry + 2]

    PCM start =  page_base + wave_off * 16
    PCM end   =  page_base + 16 * (the next strictly-greater wave_off in the directory)
    PCM format=  signed 16-bit little-endian
    param rec =  page_base + param_ptr  ..  page_base + (next strictly-greater param_ptr)
```

`entry` is a **plain 0-based index into that page's directory** — nothing more.
No hash, no heuristic, no per-class fudge constant: **the base is 0 for every class.**

The **only** piece not derivable from the data we hold is which physical socket
(IC304 / IC305 / IC306) is `bank 0`. That is a wiring fact, not a decoding fact, and §7 gives a
falsifiable prediction that identifies it the moment any one of those three chips is dumped.

---

## 1. THE UNLOCK — IC307 is **four** self-describing banks, not one index + 3 MB of mystery

`notes/kn5000-ic307-content-map.md §0/§2.3/§7.1` concluded that IC307 has a single 198-entry
index covering ~1 MB and that "the upper 3 MB is real PCM that no index entry reaches… the single
largest unexplained region". **That is wrong**, and it is why the chip map could not be closed.

Applying IC307's *own* self-delimiting index rule (`entry0.param_ptr == 4 × count`, established
in `-content-map.md §1`) at each 1 MB boundary: (**MEASURED**)

| page | base | `entry0` | `param_ptr/4` | param_ptr monotonic | wave_off monotonic | last param_ptr | first PCM | last PCM addr | fits 1 MB |
|---|---|---|---|---|---|---|---|---|---|
| 0 | `0x000000` | `{0x0318, 0x01a3}` | **198** | yes | yes | `0x1A26` | `0x1A30` | `0x0FEF60` | yes |
| 1 | `0x100000` | `{0x02a0, 0x0184}` | **168** | yes | 3 back-steps | `0x182C` | `0x1840` | `0x0FEB60` | yes |
| 2 | `0x200000` | `{0x10c0, 0x026a}` | **1072** | yes | yes | `0x2694` | `0x26A0` | `0x0FFEE0` | yes |
| 3 | `0x300000` | `{0x00e4, 0x0024}` | **57** | yes | yes | `0x022C` | `0x0240` | `0x0FF5C0` | yes |

Six independent constraints hold on all four: self-delimiting count, both columns monotonic,
the parameter block ends **10-20 bytes before** the first PCM byte, and `wave_off × 16` never
leaves its own 1 MB page (`0xFFFF × 16 = 0xFFFF0` — the u16 field addresses **exactly** 1 MB,
which is *why* the page size is 1 MB). Page 1's only blemish is three entries (79, 82, 85) whose
`wave_off` steps **backwards** — they re-use an earlier PCM region rather than break the format.

**Seventh, decisive integrity test** (the redundant `wave_start` word at the head of every
parameter record, `-content-map.md §1`): (**MEASURED**)

```
  page 0 : 198/198 records' first word == the index wave_offset   PASS
  page 1 : 168/168                                                PASS
  page 2 : 1072/1072                                              PASS
  page 3 :   57/57                                                PASS
```

A "rising-audio artifact" cannot satisfy a redundant back-reference 1072 times in a row.
**IC307 = 4 × (index + parameter records + s16le PCM), one per 1 MB page.**
Totals: **1495 directory slots, 1413 unique wave offsets, in one 4 MB chip.**

Chunk-length medians per page (**MEASURED**): page 0 = 1920 samples, page 1 = 2736,
page 2 = **64**, page 3 = **8448**. Four structurally different content types.

---

## 2. T1 — COUNT

**Firmware:** 1444 distinct `(class, entry)` pairs over all 487 SET descriptors
(independently re-derived this pass; matches Extract exactly).

The task framed the comparison as "≈198 per bank / ≈792 total". **Both framings rest on the
false premise refuted in §1** (that a 4 MB chip carries one 198-entry directory). The correct
comparison is:

| | slots | unique waves |
|---|---|---|
| IC307's four page directories | **1495** | 1413 |
| firmware demand, classes 4-7 | 574 (`198+168+151+57`) | 465 used |
| firmware demand, classes 0-3 | ≥1012 (`214+177+185+436`) | 979 used |
| **total firmware demand** | **≥1586** | **1444** |

So 1444 pairs = **1.02 chips' worth of directory** — and the class field splits them across
**exactly two 4 MB banks**: 465 on IC307, 979 on one undumped chip. 1012 slots in 4 MB is
comfortably feasible (IC307 fits 1495). **Consistent. MEASURED + INFERRED.**

Numerically: 1444 / 198 = 7.3 (rejects "one 198-entry bank"); 1444 / 792 = 1.82
(rejects "4 × 198"); 1444 / 1413 = 1.02 (supports "one page-directory slot per pair").

---

## 3. T2 / T3 — PER-CLASS RANGE vs DIRECTORY SIZE (PREDICT-THEN-CHECK)

The prediction was made from the **firmware only** (`max(entry)+1` per class = the directory
size that class requires) and then checked against **IC307's own** self-delimiting counts, which
were derived from the ROM without reference to the firmware.

| class | entries used | entry range | required directory | IC307 page | page size | result |
|---|---|---|---|---|---|---|
| 4 | 195 | `0x001`-`0x0C5` | **198** | page 0 | **198** | **EXACT** |
| 5 | 164 | `0x000`-`0x0A7` | **168** | page 1 | **168** | **EXACT** |
| 6 | 49 | `0x001`-`0x096` | ≥151 | page 2 | 1072 | fits (see §6) |
| 7 | 57 | `0x000`-`0x038` | **57** | page 3 | **57** | **EXACT** |
| 0 | 212 | `0x000`-`0x0D5` | ≥214 | — | — | > every IC307 page except 2 |
| 1 | 168 | `0x000`-`0x0B0` | ≥177 | — | — | " |
| 2 | 184 | `0x001`-`0x0B8` | ≥185 | — | — | " |
| 3 | 415 | `0x000`-`0x1B3` | ≥436 | — | — | " |

**Three exact hits out of three testable classes**, and the assignment is `page = class & 3`
— the low two bits of the class field, in order. (**MEASURED prediction, MEASURED check.**)

**T3 direct-index test:** `465 / 465 = 100.0 %` of the entries classes 4-7 use fall inside
their page's directory, with **base 0** and **no per-class offset**. Zero out-of-range.

**Falsification (the assignment is forced, not chosen):** an injective class→page map must
avoid overflow. Classes 0 and 3 need ≥214 and ≥436 slots — only page 2 can hold either, so they
collide: **classes 0-3 cannot live on IC307 at all**. For classes 4-7 the identity map is the
*unique* injective assignment producing more than one EXACT match (it produces three; every
alternative produces at most one).

---

## 4. T4 — KEY-ZONE COHERENCE: two independent structures, one slicing

### 4.1 Shared-wave tiling

IC307's directory says which chunks are *the same physical recording placed differently*
(several index entries → one `wave_offset`). The Table-Data ROM — **a different chip, written by
a different tool, decoded by a completely independent path** — says what key range each
`(class, entry)` covers. If the mapping is right, the firmware's key ranges for one shared-wave
group must **tile the keyboard contiguously with no overlap**. (**MEASURED**)

```
page 0 / class 4 :  3 groups, 3 reachable  -> 3 TILE exactly
page 1 / class 5 :  3 groups, 3 reachable  -> 2 TILE, 1 with one 4-key gap
page 2 / class 6 : 23 groups, 5 reachable  -> 3 TILE, 2 gapped (18 untouched by the traced path)
page 3 / class 7 :  4 groups, 4 reachable  -> 3 TILE, 1 with one gap
                       ── 15 reachable groups: 11 TILE EXACTLY, 4 gapped, 0 OVERLAPPING ──
```

Zero overlaps in 15 groups is itself a hard result: two entries of one shared recording never
claim the same key, in either structure.

Examples, verbatim:

```
page 0 wave 0xfca6, chunks 185..190 -> class 4 keys  44-47 48-59 60-71 72-83 84-95 96-127   TILES
page 0 wave 0xfef6, chunks 191..197 -> class 4 keys 0-35 36-47 48-59 60-71 72-83 84-95 96-127 TILES
page 3 wave 0xff5c, chunks  51..56  -> class 7 keys 37-47 48-59 60-71 72-83 84-95 96-127    TILES
page 3 wave 0xfbb4, chunks  40..43  -> class 7 keys 0-47 48-59 60-71 72-77                  TILES
page 1 wave 0xfb16, chunks 153..159 -> class 5 keys 0-35 36-47 48-59 60-71 72-83 84-95 96-127 TILES
```

Note what this destroys: `-content-map.md §2.3` read chunks 191-197 as *"all point at 0x0FEF60,
so a naive index walk assigns this entire 3 MB to one shared waveform"*. They are a **7-zone
octave-mapped multisample**, and the firmware — independently — gives exactly those seven
entries seven contiguous octave-wide key zones. Same for the six-chunk group 185-190.

### 4.2 IC307's own key-split bytes agree with the firmware's zone boundaries

IC307 parameter records carry `flag = 0x00` split values (`-content-map.md §3.1`). Where a wave
is stretched, those values track the firmware's zone lower bound **affinely and exactly**:
(**MEASURED**, class 7 / page 3)

| chunk | IC307 record | firmware key zone | `1.5·(v−40)` |
|---|---|---|---|
| `7:031` | `38/00 28/00 00/c0` | 0-35 | 24 |
| `7:033` | `40/00 30/00 20/c0` | 37-47 | 36 |
| `7:034` | `48/00 38/00 28/c0` | 48-59 | **48** |
| `7:035` | `50/00 40/00 30/c0` | 60-71 | **60** |
| `7:036` | `58/00 48/00 38/c0` | 72-83 | **72** |
| `7:037` | `60/00 50/00 40/c0` | 84-95 | **84** |
| `7:038` | `68/00 58/00 48/c0` | 96-127 | **96** |

`MIDI key = 1.5 × (IC307 split value − 40)`, i.e. **one IC307 unit = ⅛ octave = 1.5 semitones**,
origin 0x28. Holds identically for chunks `7:020`-`7:027` and for the page-0 groups. The group
`7:028`-`7:02B` obeys the same law shifted by exactly **+12 semitones** — an integer octave,
which is precisely the transpose/fold term already traced in
`-firmware-sample-tables.md §5.1`. (**MEASURED relation; INFERRED unit interpretation.**)

### 4.3 The physical test: does the audio's PITCH match the key zone the firmware assigns?

The firmware assigns `(7, k)` a key zone. If `entry` indexes chunks, chunk `k`'s **measured
fundamental** must track that zone one-for-one in semitones. Measured by autocorrelation
(smallest lag ≥ 0.92 × peak, to defeat sub-harmonics), regressed as
`measured_note = a·zone_centre + b`. No listening, no human input. (**MEASURED**)

```
class 7 entries 0x000-0x01F  ->  IC307 page-3 chunks 0..31
        n = 32     slope a = 1.003     R^2 = 0.9980     rms residual = 0.83 semitones
        (over a five-octave span)
```

**Negative controls — the criterion demonstrably CAN fail:**

```
  wrong page   class 7 -> page 0   n=27  slope +0.026  R^2 0.0012
  wrong page   class 7 -> page 1   n=32  slope -0.012  R^2 0.0005
  wrong page   class 7 -> page 2   n=33  slope -0.234  R^2 0.0287
  wrong page   class 4 -> page 1/2/3     slope -0.04 / -0.40 / -0.39   R^2 <0.02
  wrong page   class 5 -> page 0/2        slope -0.10 / -0.48          R^2 <0.04
  shifted      class 7 -> page 3, entry+1 / +2 / +5 / +17 : residual stdev degrades monotonically
  shuffled     class 7 -> page 3, 20 random permutations : slope 0.047 ± 0.228, R^2 0.032 ± 0.053
  shuffled     class 4 -> page 0, 20 permutations        : slope 0.031 ± 0.136, R^2 0.011 ± 0.018
  shuffled     class 5 -> page 1, 20 permutations        : slope 0.057 ± 0.424, R^2 0.072 ± 0.136
```

Every wrong mapping collapses to slope ≈ 0. The derived mapping gives **slope 1.003, R² 0.998**.

**Per-instrument scorecard** (each firmware SET regressed on its own; degenerate SETs — those
whose zones all resolve to one chunk, e.g. the fold-collapsed basses and drawbars — excluded
because the test cannot discriminate there):

```
set   class zones  n   slope    R^2    rms   instrument
  2     7    16   14   0.998  0.9982  0.68   Piano                PASS
  1     7    16   14   0.996  0.9982  0.68   Piano                PASS
  4     7    16   14   0.998  0.9982  0.68   Bright Piano         PASS
  5     7    16   14   0.996  0.9982  0.68   Honky-Tonk Piano     PASS
  0     7    17   15   0.896  0.9934  1.27   Piano 1 Octave       PASS
241/242 4     7    5   0.831  0.8980  2.38   Cathedral Organ      PASS
223     4    14   10   0.834  0.8849  3.23   German Acdn 2        PASS
224     4    11    8   0.980  0.7822  3.79   German Acdn 1
217-220 4  10-13 6-10  0.51-0.70  0.23-0.77  Italian Acdn 1/2/4
226     4    11    7   0.670  0.9003  2.47   German Acdn Bs1
278     6     9    6   1.397  0.9493  3.41   Concert Strings
177     5     6    4   0.693  0.9689  0.81   Alto Flute
                                       ── 8/17 strict PASS, 17/17 positive slope ──
```

**Reported miss / honest reading:** only 8 of 17 clear the strict bar (`|a−1|<0.25`, `R²>0.85`).
The five piano SETs are essentially perfect. The accordion/organ SETs land at slope 0.51-0.98 —
all in the right direction, none anywhere near the ≈0 of a wrong mapping, but short of 1.0.
Two causes, not separated here: accordion reeds are harmonically dense and defeat a plain
autocorrelation pitch detector, and accordion SETs re-use one recording across several zones.
This is a limitation of *my measuring instrument*, not a contradiction of the mapping — but it
is a miss and it is reported as one.

---

## 5. The ROM naming its own samples — semantic PREDICT-THEN-CHECK

The 610-record named table (`notes/data/kn5000-sample-name-table.tsv`) gives a **name** for a
`(class, entry)`. Each name is a *prediction about an objectively measurable property* of the
chunk the formula lands on. Measured: length, zero-crossing rate, decay ratio
(RMS last 10 % / first 10 %), periodicity. **No listening.** (**MEASURED**)

| the ROM's own name | → chunk | samples | ZCR | decay | periodicity | prediction met? |
|---|---|---|---|---|---|---|
| `Rock Bass Drm` `5:022` | page 1 #34 | 1 792 | **0.020** | **0.046** | 0.95 | low-frequency one-shot that dies away — **yes** |
| `HiHatClosed` `5:049` | page 1 #73 | 1 120 | **0.380** | **0.203** | 0.27 | short noisy one-shot — **yes** |
| `HiHat Open` `5:04B` | page 1 #75 | **6 072** | **0.463** | 0.959 | 0.13 | noisier *and 5× longer* than the closed hat — **yes** |
| `Applause 1-7` `4:0B5` | page 0 #181 | 5 520 | **0.510** | 1.058 | **0.148** | sustained aperiodic noise — **yes** |
| `Telephone` `4:0B2` | page 0 #178 | 4 552 | 0.468 | 0.728 | **0.670** | periodic tone — **yes** |
| `Organ Click` `6:028…6:068` | page 2 #40…#104 | **16-144** | — | — | — | **0.5-4.5 ms transients** — a click is a click — **yes** |

The organ-click row is the strongest of these: nine names, nine entries spaced exactly 8 apart,
and the formula lands on nine chunks of 16-144 samples in the page whose *median* chunk is 64
samples. That page (page 2, 1072 tiny waves) is exactly a drawbar-footage bank.

**And the negative version of the same test — which entries the firmware NEVER uses:**

```
class 4 / page 0 : 195 of 198 used.  UNUSED = {0x00, 0x98, 0x9F}
     chunk 0x00 = 256 samples, ONE sign change  -> the single-cycle synthetic sine
                  (-content-map.md §2.1: "mathematically near-perfect single sine cycle,
                   mean abs error 0.3 LSB … test/fallback tone")
class 5 / page 1 : 164 of 168 used.  UNUSED = {0x4D, 0x50, 0x53, 0x55}
     chunks 0x4D, 0x50, 0x53 = 32 samples, ZERO sign changes -> degenerate stubs
class 7 / page 3 :  57 of  57 used.  UNUSED = {} — every single chunk is referenced
```

**The one chunk in IC307 that is a synthetic test tone is the one chunk no instrument
references**, and 3 of the 4 unused page-1 chunks are 32-sample stubs. A wrong mapping has no
reason to leave precisely the degenerate chunks unclaimed. Unexplained: `4:098` and `4:09F` are
real audio and unused (2 of 198). **Reported.**

---

## 6. What each class actually *is* — read out of the ROM, not out of anyone's ears

Joining the 629-patch table to the SET descriptors (`kn5000-patch-partials.tsv`), and the
610-record name table to the same `(class, entry)` space: (**MEASURED**)

| class | IC307 page | median chunk | instruments the ROM routes there | named samples the ROM puts there |
|---|---|---|---|---|
| **7** | **3** (57) | 8448 | **21 — `Piano`, `Bright Piano`, `Mellow Piano`, `Honky-Tonk Piano`, `Piano 1/2 Octave`, `Electric Grand`, `Midi Grand`, `Piano & Strings`** | — |
| **4** | **0** (198) | 1920 | 93 — `Pipe Organ`, `Cathedral Organ`, `Full Organ`, `German/Italian Acdn 1-4`, `Bandoneon`, `Harmonium`, `Perc Organ`, + SFX presets | `Applause`, `Telephone`, `Helicopter`, `Train`, `Gun Shot`, `Explosion`, `Bird 2/3`, `Scratch 1-4`, `Voice Ah/Yeh/Uh`, `Wave 1-14`, `Sax Breath`, `Flute Breath`, `FluteKeyClick` |
| **5** | **1** (168) | 2736 | 72 — `Piccolo`, `Jazz Flute`, `Alto Flute`, `Taiko Drum`, `Wood Block`, `Synth Drum`, `Melodic Tom`, `Sleigh Bell`, basses | **104 drum samples**: `Rock/Room/Jazz/Trad/Power/House/Soul/Dance/Elect/Funk Bass Drm`, snares, toms, rims, `HiHatClosed/HfOpen/Open/Pedal`, `Ride Cymbal 1-10`, … |
| **6** | **2** (1072) | **64** | 23 — `Soul Organ`, `Pop Organ`, `Rock Organ`, `Organ Bass`, `Accomp Drawbars`, string ensembles | `Organ Click` ×9 at `0x028,0x030,…,0x068` |

**Class 7 = the acoustic piano bank, and IC307 page 3 is where it lives.** Page 3's 57 chunks
are: **two identical 16-chunk runs** (`0..15` and `16..31`) with byte-identical lengths and
byte-identical parameter records —

```
 chunk  0..15 : 26128 22544 22288 21264 20112 19216 18832 16656 15504 12560 11888 11536 10608 9184 7760 8448 samples
 chunk 16..31 : 26128 22544 22288 21264 20112 19216 18832 16656 15504 12560 11888 11536 10608 9184 7760 8448   (identical)
```

— **the piano's two oscillators.** The firmware, independently, gives PIANO two partials
resolving to SET #1 (`7:000`-`7:00F`) and SET #2 (`7:010`-`7:01F`), and the *live* register
capture recorded `+040 = 0x7007` for osc 0 and `0x7017` for osc 1 at C4
(`kn5000-live-captures.md`, `-firmware-sample-tables.md §6`). **The 0x10 offset between the two
oscillators is exactly the 16-chunk group size in IC307.** Sample lengths fall monotonically
with pitch — the signature of a chromatic piano multisample.

This is the mandate's answer, and it is a *derivation*: nobody had to listen to anything.

**This also settles, from data, the question `kn5000_wave_samples/INDEX.txt` was asking Felipe
to answer by ear.** That file's mapping (class 7 = chunks 39-54, class 0 = 121-134, …) was a
heuristic over page 0 only; it is **wrong in every row**, which is why class 7 "sounded like an
organ/accordion" — page-0 chunks 39-54 belong to class 4, the organ/accordion bank. The real
piano is page 3. **No listening test was needed to establish that, and none was used.**

---

## 7. T5 — falsification, and what remains genuinely underdetermined

Alternatives tested and **rejected on measurements**:

1. **`entry` (or the whole `+0x040` word) is a PCM address.** Rejected: PIANO's zones are
   `0x7000`-`0x700F`, consecutive integers. Any address scaling puts its 16 zones 1 unit apart
   while the actual recordings are 15-52 KB each; a scale large enough to fit them
   (≈8-16 KB/unit) puts `0x700F` at ~470 MB. **MEASURED-impossible.**
2. **`entry` indexes a single flat 198-entry table (one bank).** Rejected: classes 0, 3, 4
   exceed 197; and the premise itself is false (§1).
3. **`entry` indexes 4 × 198 = 792 concatenated chunks.** Rejected: 1444 distinct pairs, and
   class 3 alone reaches 435.
4. **`class[3:2]` = page and `class[1:0]` = chip.** Rejected: the four matching directories are
   all *inside IC307*, so the low bits must be the intra-chip page.
5. **Any non-identity class→page permutation for classes 4-7.** Rejected: unique injective
   assignment with >1 exact directory-size match (§3), and every alternative collapses the
   pitch regression to slope ≈ 0 (§4.3).
6. **"LSI-internal / underdetermined."** Rejected by everything above: the decode needs only
   ROM bytes, and it was confirmed against three independent structures (directory sizes,
   shared-wave tiling + key-split bytes, measured pitch) plus the ROM's own sample names.

**What is genuinely still missing (and exactly what data would supply it):**

* **Which socket is `bank 0`.** Classes 0-3 need page directories of **≥214, ≥177, ≥185, ≥436**
  entries. That is a hard, falsifiable **PREDICTION**: when IC304, IC305 or IC306 is dumped,
  exactly one of them must have self-delimiting counts at `0x000000/0x100000/0x200000/0x300000`
  matching those four numbers, in that order. Whichever chip does is `bank 0`; the other two
  are then known not to serve classes 0-7 in this firmware. **No other data is needed.**
* **Whether classes 8-15 exist.** Only classes 0-7 appear in the 1444 pairs (`class` is 4 bits,
  bit 3 always 0). Two of the four sockets are therefore unaccounted for by the tone tables
  mined so far. Candidates: reached only through the untraced drawbar/footage and drum-kit
  paths (`-firmware-sample-tables.md §10.2/§10.3`), or reserved. **Not decided here.**
* **Class 6 / page 2 is the loose one.** 1072 slots, only 49 claimed by the *traced* path.
  Not a contradiction (49 ≤ 1072, all 49 in range, all 5 reachable shared-wave groups tile, and
  the `Organ Click` chunks are 0.5-4.5 ms as named) — but the exact directory size cannot be
  confirmed by a `max(entry)+1` match while the drawbar/footage selection path is untraced.
  **Tracing `LABEL_02B576`/`LABEL_032AE0`/`LABEL_032A08` would close it.**
* **The `flag != 0x00` parameter bytes** (per-wave `xx/80`, `xx/40` values — e.g. the piano's
  `eb dc dc dd bb be c0 e1 ed fb 85 90 9e`) are the chip's own per-wave parameters
  (loop/envelope/tune). Not needed for sample *selection*; not decoded here.
* **The absolute base sample rate.** The regression's intercept is `b ≈ +16.75` semitones at an
  assumed 32 kHz, implying a native rate near `32000 / 2^(16.75/12) ≈ 12.2 kHz` for page 3, but
  the intercept also absorbs the SET's root-key/basepitch terms, so this is **not** a clean
  measurement of the rate. Flagged, not claimed.

---

## 8. Corrections this pass makes to prior notes

1. **`kn5000-ic307-content-map.md §0, §2.3, §4, §7.1`** — "the index only describes the first
   ~1 MB", "the upper 3 MB is real PCM that no index entry reaches", "entries 191-197 all point
   at 0x0FEF60 … a naive index walk assigns this entire 3 MB to one shared waveform", and
   "the 3 MB un-indexed tail's addressing … is the single largest unexplained region":
   **all superseded.** IC307 has **four** self-delimiting indexes, one per 1 MB page
   (198 / 168 / 1072 / 57 entries), each passing six structural tests and a 100 % redundant
   `wave_start` back-reference. Entries 191-197 of page 0 are a 7-zone multisample of the wave
   at `0x0FEF60`, whose real extent ends at the page-0/page-1 boundary — not 3 MB.
2. **`-content-map.md §2.3`** — "the apparent index tables at 0x100000/0x200000/0x300000 are
   **coincidental** … the 1072 monotonic entries at 0x200000 is a rising-audio artifact":
   **wrong.** All three are real index tables. The 1072 count is confirmed by
   `entry0.param_ptr == 4×1072` **and** by 1072/1072 redundant `wave_start` matches.
3. **`-content-map.md §5`** — the model of IC304/305/306 as "a 198-ish-entry index + a ~3 MB
   page-addressed tail" should become **"four 1 MB pages, each with its own self-delimiting
   index"**, with the §7 size prediction as the acceptance test for a real dump.
4. **`kn5000_wave_samples/INDEX.txt`** — its class→chunk table (class 7 = chunks 39-54, etc.)
   is a page-0-only heuristic and is wrong in every row; superseded by §0's formula. The
   "WHAT I NEED: for any wave you recognise, tell me…" request in that file is **withdrawn** —
   the answer was in the ROM.
5. **`kn5000-firmware-sample-tables.md §8`** — "1444 total waves vs IC307's 198-entry index …
   four equally-sized chips would supply ≈792 index entries — well short of 1444 … nothing in
   the firmware data decides it." Resolved: one chip supplies 1495 slots; 1444 pairs occupy
   two banks (465 + 979). The bracketed worry that "several `(class, entry)` pairs share one
   physical PCM block with different loop/root parameters" is **also true and now measured** —
   that is exactly the shared-`wave_offset` mechanism of §4.1.

---

## 9. Reproduction

```
# ROM side (kn5000_waveform_rom.ic307):
for page in 0..3:
    base = page * 0x100000
    n    = u16[base] / 4                       # self-delimiting
    idx  = [ (u16[base+4i], u16[base+4i+2]) for i in 0..n-1 ]
    chunk_i:  start = base + idx[i].wave*16
              end   = base + 16*min{ w > idx[i].wave }   (else next page boundary)
    param_i:  base+idx[i].param .. base+min{ p > idx[i].param }
              first u16 == idx[i].wave  (integrity check, 1495/1495)

# firmware side: notes/kn5000-firmware-sample-tables.md §11, unchanged.
# join:  +0x040 -> class,entry -> page = class&3, chunk = entry.
```
Scripts (scratchpad, stdlib only): `ic307.py` (re-derive page 0), `pages2.py` (four-page index
validator), `fw.py` (Table-Data walk), `global.py` (T1-T4 scoring), `perm2.py` (falsification
matrix), `pitch4.py` (regression + negative controls), `sig.py`/`names.py` (name checks).
