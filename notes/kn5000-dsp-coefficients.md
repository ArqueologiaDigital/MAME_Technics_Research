# KN5000 uPD6383GF coefficient streams — decode, inventory, and the KN7000 cross-check

Date: 2026-07-22.
Scope: the **PARAM_TABLE** side of the KN5000 effects DSP (IC311, NEC uPD6383GF-3BA).
Companion tool: `tools/kn5000_dsp_coeffs.py`.
Sibling work: `tools/kn5000_dsp_extract.py` (the ALGO_TABLE / I-RAM microcode) and
`notes/kn5000-dsp-encoding.md` (instruction encoding — a different author, different file).

This document answers a question Felipe posed directly: *do the numerical constants
in the KN5000's effects DSP reappear in the KN7000's, which we have already
disassembled?* The short answer is **no** — and that negative is stated here with
its measurement, because the same pass produced a large positive result the
question did not anticipate: **the KN5000 coefficient stream decodes cleanly, and
its delay-line lengths and per-preset reverb banks now read as engineering data.**

Everything below is derived statically from
`kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom` (Sub CPU, 196608 bytes,
ROM base 0xEF00) and `kn5000_v10_program.rom` (Main CPU). No emulator run was needed.

---

## 1. The stream format (MEASURED)

`PARAM_TABLE` at **0x0001EF0C**, 100 × 32-bit LE pointers, **59 distinct**. Each
pointer walks the same level-1 bytecode the algorithm streams use, with a
strikingly uniform opcode sequence across all 100 slots:

```
[0 4 (0 4)? 5 4 1 2 4 F]
```

one or two type-0 records, then type-5, type-1, and finally one type-2 record,
each separated by a bare type-4 command byte, terminated by 0xF. This matches
`kn5000-docs/audio-subsystem.md`'s independent description ("the number of
H0/H5/H2 groups varies by effect type"). Two payload shapes:

* **type 0 / 1 / 5** — 3-byte header, then a run of **5-byte entries**
* **type 2** — 3-byte header, then a run of **3-byte (24-bit) words**

### 1.1 The 5-byte entry (DERIVED here)

```
byte0      mode
byte1..3   24-bit big-endian payload
byte4      selector / destination tag
```

Mode census over all 100 slots: `0x00` ×431, `0x08` ×215, `0x0A` ×1707, `0x0B` ×44.
The observed nibbles line up with the documented handler-0 three-way branch
(*0x00 = static, 0x0A = raw, else = param-modified*), which is what fixed the
field boundaries.

| mode | meaning | evidence |
|---|---|---|
| 0x00 | static small value, selector always 0x00; payloads cluster at 0x1050 / 0x10E0 / 0x1500 / 0x1140 — these look like **DSP register addresses**, not audio data | 431 entries, all payloads in 0x1000–0x1D00 |
| 0x08 | param-modified entry; **every** payload > 0xFFFF and of the form 0x01xxxx (0x10008, 0x10268, …) — a flag byte plus a 16-bit base value the level-2 translator scales by a user parameter | 215 entries, 0 payloads ≤ 0xFFFF |
| 0x0A | "raw" write. **1634 of 1707 payloads are ≤ 0xFFFF** — these are *16-bit DSP register values*, matching the documented SPI register-write protocol (`value_high`, `value_low`). The remaining 73 are full-range Q0.23 | selectors 0x15 / 0x4C / 0xCC |
| 0x0B | **integer delay length in DRAM words** — see §3 | 44 entries; selector 0x15/0x95 |

### 1.2 The type-2 record is where the real coefficients live (MEASURED)

**1770 24-bit words, 209 distinct.** Decoded as signed Q0.23 they are
unambiguously audio coefficients — 158 of the 1770 are negative, and the top of
the distribution is a list of exact round decimals:

```
400000  +0.50000000  x333        7FFEC3  +0.99996221  x42
000000  +0.00000000  x114        7FE11C  +0.99905729  x42
200000  +0.25000000  x104        7B403B  +0.96289766  x42
517CC1  +0.63661969  x53   <-- 2/pi
066666  +0.04999995  x46         800000  -1.00000000  x27
50A3D7  +0.63000000  x23         600000  +0.75000000  x24
428F5C  +0.51999998  x20         333333  +0.39999998  x23
```

`0x517CC1 / 2^23 = 0.63661969`; **2/π = 0.63661977**. Agreement to 8×10⁻⁸, i.e.
to the last bit of Q0.23, appearing 53 times. This is the classic
sine-approximation / LFO-normalisation constant and is by itself a confirmation
that the Q0.23 reading is correct — a wrong word size or endianness cannot
produce 2/π to 1 LSB. Likewise `0x7FFEC3`/`0x7FE11C`/`0x7B403B` (0.99996 /
0.99906 / 0.96290) are textbook one-pole smoothing/damping poles, and −1.0
(`0x800000`, 27 occurrences) is the inverting tap you expect in an all-pass.

**Correction to the working assumption in the task brief:** the mode-0x0A entries
are *mostly not* Q0.23 coefficients — they are 16-bit register values. The Q0.23
coefficients are the type-2 record. Both are handled by the tool.

---

## 2. The effect-name table — every slot now has a name (MEASURED)

`kn5000_v10_program.rom` holds a **descending** table of 16-char names at stride 18
(`NAME 0x00 0xFF`), last entry (index 0, " NO OPERATION ") at file offset
**0x33568**. Anchor check: index 20 reads `CONCERT REVERB 1`, which is the single
algorithm-ID↔name pair independently documented in
`kn5000-docs/audio-subsystem.md` ("Word[0] … 0x0014 = algorithm 20 = CONCERT
REVERB 1"). `tools/kn5000_dsp_coeffs.py --names` asserts on that anchor.

The name table cross-validates the whole parse in a way that is hard to fake:
**every one of the 44 slots named `----------` (unused) shares one and the same
parameter pointer 0x001735E with an 11-entry null program, and every named slot
has its own.** Slot 0 (`NO OPERATION`) uses that same null program. If the record
walk were misaligned the unused slots would not fall out as an exact equivalence
class.

---

## 3. DELAY LENGTHS — the headline result (MEASURED)

Mode 0x0B, 44 entries, 30 distinct. Read as integers they are delay-line lengths
in words of the external DRAM the uPD6383GF drives on A0–A16 (131072 words max —
per the Pioneer CDJ-500 service manual, pins 43–80, the RAS/CAS/WE + A0–A16 +
I/O1–16 "external RAM for digital delay"). 40 of 44 fall inside that limit.

Sorted by effect, the taps are *self-evidently correct*:

| id | effect | delay taps (samples) | reading |
|---|---|---|---|
| 1 | CHORUS | **200, 720, 1240, 1760** | 4 taps, **exactly equally spaced by 520** — a 4-voice chorus |
| 2 | MODULATED CHORUS | **200, 650, 1100, 1550** | 4 taps, **exactly equally spaced by 450** |
| 6 | ENSEMBLE | **200, 200, 200, 664, 664, 664** | 3 voices × 2 (stereo pair), two delay stages |
| 71 | PEQ+CHORUS | **200, 520, 840, 1160** | 4 taps, spacing 320 — a shallower chorus |
| 50 | VIBRATO | 200, 620 | single modulated pair |
| 74 | PEQ+VIBRATO | 200, 600 | ditto |
| 56 | MIX UP | 200, 640 | ditto |
| 15 | ROCK ROTARY | **160, 502, 862** | horn / drum / cabinet |
| 53 | ROTARY SPEAKER | **160, 502, 862** | **byte-identical to ROCK ROTARY** — same delay network, different coefficient bank |
| 3 | ENHANCER | 7718, 15437 | 15437 ≈ 2×7718+1 |
| 64 | S.DELAY+CHORUS | 6850, 7170, 15025, 15345 | two delay pairs, each offset by 320 (the PEQ+CHORUS spacing) |
| 67 | S.DELAY+VIBRATO | 7825, 15900 | |
| 4 | FLANGER | 12800, 140800 | 140800 = **11 × 12800** and exceeds A16 — see caveat |
| 73 | PEQ+FLANGER | 12800, 153600 | 153600 = **12 × 12800** and exceeds A16 |
| 66 | S.DELAY+FLANGER | 1964800, 4057600 | far beyond A16 — see caveat |

The equal-spacing structure (520 / 450 / 320) and the exact ROCK ROTARY ≡ ROTARY
SPEAKER identity are the strongest internal confirmations that mode 0x0B is a
delay length and that the byte fields are cut in the right places. Neither would
survive a misparse.

**Caveat, stated openly:** four values (140800, 153600, 1964800, 4057600) exceed
the 131072-word address space. They are all in *flanger* slots and all are exact
small multiples of a base (11×, 12×). The most likely reading is that mode 0x0B
carries a *sweep range* or *LFO period* in the flanger case rather than a raw tap
address, but I have not proved that — it is INFERRED and flagged. The tool's
`delays_of()` returns them unfiltered; the summary in `main()` reports them as-is.

### 3.1 Sample rate

I take **fs = 48 kHz**. Reasons, in order of strength:
1. The KN5000 tone generator is documented at 48 kHz stereo
   (`kn5000-docs/tone-generator.md`: "Sound output | Stereo 48kHz"; the waveform
   engine is described as 64-voice PCM at 48 kHz). The effects DSP sits on the
   same serial audio bus.
2. The CDJ-500 manual (pins 17–19, 26–29) shows BCLK/LRCK/XFs as *programmable
   dividers of the system clock in master mode* — the chip imposes no rate, so
   the host decides. That kills any argument from the CDJ side (which, being a CD
   player, would run 44.1 kHz — a different rate on the same silicon).

This is an ASSUMPTION, not a measurement; the tool exposes it as `FS` and every
ms figure below scales linearly.

At 48 kHz: CHORUS taps = 4.17 / 15.0 / 25.8 / 36.7 ms. ROTARY = 3.3 / 10.5 /
18.0 ms. Both are squarely in the textbook ranges for those effects, which is a
weak but real sanity check on the rate.

---

## 4. Reverb preset banks — twelve presets, one program (MEASURED)

Slots 16–27 (ROOM/PLATE/CONCERT/DARK/BRIGHT/WAVE REVERB 1&2) all use algorithm
program **0x001C701** (133 I-RAM words, the largest in the ROM) and each carries
**37 type-2 coefficients**. Diffing the twelve banks column-by-column:

* **Columns 0–2 are constant across all twelve**: +0.25, +0.50, +0.50 — input
  scaling / summing, not preset character.
* **Columns 14/15/16 are byte-identical to columns 22/23/24** in every preset, and
  **columns 28/29/30 identical to 34/35/36**. Two coefficient *triples*, each
  duplicated. INFERRED reading: a **stereo pair** — the same 3-coefficient filter
  or tap-gain trio instantiated for L and R. This is measured (the duplication is
  exact); the "stereo" label is the inference.
* The triples move together across presets in the way the names predict:

| preset | col14 | col15 | col16 |
|---|---|---|---|
| CONCERT REVERB 1 | +0.2734 | +0.3573 | −0.1829 |
| BRIGHT REVERB 1 | +0.3217 | +0.4155 | −0.2854 |
| PLATE REVERB 1 | +0.3217 | +0.3484 | −0.2441 |
| ROOM REVERB 2 | +0.3745 | +0.3723 | −0.3315 |
| DARK REVERB 1 | +0.3745 | +0.5000 | −0.3745 |
| ROOM REVERB 1 | +0.4385 | +0.3630 | −0.4153 |

  Read as `(b0, a1, a2)` of a second-order section with complex poles
  (`|pole| = sqrt(|col16|)`), the pole radius runs 0.428 (CONCERT, most open) →
  0.612 (DARK, most damped), and the pole angle stays in a narrow 65–74° band
  across all twelve. That ordering is musically coherent. **But** the sign
  convention is unproven and the stability test (|a2|<1) is satisfied trivially
  by every value here, so it discriminates nothing. **Marked INFERRED.** A
  falsifiable next step: read the 133-word microprogram at 0x001C701 and see
  whether these three C-RAM cells are consumed by a 2-multiply recursive section.
* Columns 9–13 and 17–21 are a repeating 5-gain ladder (0.63, 0.52, 0.50, 0.40,
  0.50 / 0.63, 0.62, 0.52, 0.40, 0.50) — INFERRED: series all-pass diffuser gains,
  the same shape as the KN7000's 4-allpass diffuser but with different values.
* Columns 28–30 hold the strongly preset-dependent values (WAVE 1 = 0.335/0.255,
  PLATE 2 = 0.755/0.395, DARK 1 = 0.700/0.500) — INFERRED: tail feedback / decay.

**Data hygiene note:** slot 25 (BRIGHT REVERB 2) has **38** type-2 words, not 37,
so its column alignment is shifted by one from index 5 onward and its column in
the table above must be ignored. Not investigated further.

The reverbs carry **no mode-0x0B delay lengths at all**. Their delay-line lengths
must therefore be immediates inside the 133-word microprogram, exactly as on the
KN7000 (where the early-reflection taps are `M7` immediates in the code and only
the *gains* live in the DM bank). That is a genuine **structural** parallel
between the two machines — see §5.

---

## 5. The KN7000 correlation — VERDICT: NEGATIVE

Two independent comparisons, both run by `tools/kn5000_dsp_coeffs.py --kn7000`.

### 5.1 Coefficient values

KN5000: 208 distinct coefficients (type-2 Q0.23 plus the full-range mode-0x0A).
KN7000: 548 distinct IEEE-754 floats in (1e-4, 1.0] recovered word-aligned from
the 81 effects-DSP record bodies listed in `kn7000_disassembly/dsp/records.tsv`
(image `kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin`, both
endiannesses tried).

```
                       KN5000    KN7000    shared (tol 1e-6)
round to 2 decimals        31        16        12
not round                 175       530         2   (+0.125, -0.125)
```

* The **12 shared round values** are `0.05 0.10 0.18 0.20 0.25 0.30 0.40 0.50
  0.60 0.70 0.90 1.00`. There are only ~100 two-decimal values in [0,1]; if both
  designers drew their round constants independently from that pool, the expected
  overlap is 31×16/100 ≈ **5**. Twelve is more than five, but the pool is not
  uniform — *every* audio engineer reaches for 0.25/0.5/0.7 — so this excess is
  evidence of shared *habit*, not shared *data*. It is not a correlation between
  the two algorithm sets.
* The **only two non-round shared values are ±0.125**, which is 2⁻³ and therefore
  a shift, not a coefficient.
* **Zero** arbitrary coefficient is shared. None of the KN7000's signature
  constants appears anywhere in the KN5000 set: 0.618 (the reverb's `k`), 0.5614
  (wet level), 0.876, 0.2435, 0.111, 0.243 — all absent. Symmetrically, the
  KN5000's most distinctive constant, **2/π = 0.63662 (53 occurrences)**, does not
  appear in the KN7000 records or in any of the nine `kn7000_disassembly/dsp/*.md`
  documents.

A naive chance baseline (drawing same-size random float sets from elsewhere in
the KN7000 program image) predicts 1.8 ± 1.3 matches against 16 observed, which
*looks* significant — but that baseline is wrong, because it samples arbitrary
floats while both real sets are heavily biased toward round decimals. Once the
sets are split as above, the apparent signal disappears entirely. **Recording
this because it is exactly the sort of number that could have been reported as a
correlation.**

### 5.2 Delay lengths — Felipe's strongest hypothesis, FALSIFIED

The premise was that a delay tap of N milliseconds is the same physical quantity
on either instrument and so should survive the change of chip. It does not, and
the reason is instructive.

KN5000 taps (samples, ≤131072): 160 200 502 520 600 620 640 650 664 720 840 862
1100 1160 1240 1550 1760 6850 7170 7718 7825 12800 15025 15345 15437 15900

KN7000 taps (samples, from the nine dsp/*.md docs): 8 10 26 38 64 112 120 200 240
250 257 314 364 400 511 512 544 800 849 1000 1280 1422 1498 1536 2002 2370 2498
3712 3770 4000 5000 5239 8000 14464 16232 23990 32768

**Intersection: {200}.** One value, and it is a round number.

Converted to milliseconds and matched with a ±0.3 ms window (KN7000 at its
documented 44.1 kHz):

| assumed KN5000 fs | KN5000 taps within 0.3 ms of any KN7000 tap |
|---|---|
| 32 kHz | 2 of 26 |
| 44.1 kHz | 7 of 26 |
| 48 kHz | 4 of 26 |

Over 26×37 = 962 pairs with a 0.3 ms window spanning a 5–500 ms range, those
counts are consistent with chance and do not discriminate between rates. **No
delay-length correlation, and the ms-domain test cannot even pin the sample
rate.**

**Why the hypothesis fails — and this is the real finding.** Both machines design
their delay lines in **round sample counts, not round milliseconds**. KN5000:
160, 200, 520, 600, 640, 720, 840, 1100, 1160, 1240, 1550, 1760, 12800. KN7000:
200, 250, 400, 512, 800, 1000, 4000, 5000, 8000, 32768. Neither list is round in
time; both are round in memory. Delay lengths on these instruments are chosen as
*addresses in a delay buffer*, and a designer moving to a new chip with a new
buffer geometry re-picks them from scratch. The physical-quantity argument would
hold for a spec sheet; it does not hold for the implementation.

### 5.3 What *does* survive: structure, not numbers

The two effect sets are not numerically related, but they are architecturally
recognisable as the same design school:

| | KN5000 (uPD6383GF, 1994) | KN7000 (ADSP-21065L, 2000) |
|---|---|---|
| delay taps | immediates in the microprogram (reverbs) or a separate mode-0x0B stream | `M7` immediates in the microprogram |
| gains | separate coefficient bank per preset | separate DM bank per record |
| reverb topology | 5-gain all-pass ladder ×2 + stereo-mirrored filter triples | 4-allpass diffuser + combs + stereo decorrelation |
| presets per program | 12 reverb presets share one 133-word program | multiple records share `rec51/52/53` structure with different banks |
| rotary | ROCK ROTARY and ROTARY SPEAKER share a delay set, differ only in coefficients | same pattern in `tremolo-rotary-family.md` |

The **"one program, many coefficient banks"** discipline is identical on both
machines. That is a continuity of engineering practice across a chip generation,
and it is worth saying — but it is a qualitative claim and it is labelled as one.

---

## 6. Effect-type identification from coefficients alone

With the name table in hand this became a validation exercise rather than a
guessing game, so these are checks, not predictions:

* **Chorus family (1, 2, 6, 71)** — identified by 4–6 evenly spaced short taps
  (200–1760 samples) plus the 2/π LFO constant. ✔ matches names.
* **Rotary (15, 53)** — three taps 160/502/862 with no even spacing (horn/drum are
  physically different distances). ✔
* **Reverb family (16–27)** — 37-coefficient banks, no explicit delay stream, many
  small feedback gains and one negative per triple. ✔
* **EQ / dynamics (33 PARAMETRIC EQ, 30 COMPRESSOR, 26–29 distortion family)** —
  no delay entries at all; PARAMETRIC EQ has the *largest* mode-0x0A register-value
  count in the ROM (45), consistent with 5 bands × 3 coefficients written as
  register pairs through the documented 0x0000/0x0010/0x0020… band map. COMPRESSOR
  has only 7 — a threshold/ratio/attack/release handful. ✔
* **Presets with ZERO coefficients (57–60 STANDARD/PERCUSSIVE/SYMPHONIC/DEEP
  SPACE, 79 GEQ, 88–91 ROOM/KARAOKE/BATH ROOM/STAGE)** — these have parameter
  streams with no type-2 record at all. INFERRED: they are *combination presets*
  that configure other slots via the register-address tables at 0x1F09C / 0x1F22C
  rather than owning a coefficient bank. Consistent with their names being room
  presets and a graphic EQ.

The one thing coefficients alone could **not** do is separate the twelve reverb
presets from each other without the names — their banks differ only in magnitude,
not in shape.

---

## 7. Reproducing

```
python3 tools/kn5000_dsp_coeffs.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom \
    --names ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom \
    --kn7000 ~/compartilhado/kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin \
             ~/compartilhado/kn7000_disassembly/dsp/records.tsv \
    --csv /tmp/kn5000_coeffs.csv
```

## 8. Open threads

1. **Confirm mode 0x0B for flangers.** Four values exceed A16. Read the flanger
   microprogram and see whether the second value is consumed as a sweep range.
2. **Confirm the second-order-section reading** of reverb columns 14/15/16 by
   disassembling 0x001C701 and checking whether those C-RAM cells feed a
   2-multiply recursion. This is the one inference in §4 that a single
   disassembly pass could settle.
3. **Find the reverb delay-line lengths**, which are inside 0x001C701 as
   immediates. Once recovered they can be compared against the KN7000's
   1536/3712/5239/16232/14464 — a second, independent shot at §5.2. My prediction,
   on the evidence of §5.2, is that they will not match either.
4. **BRIGHT REVERB 2's 38th word** — is it a real extra coefficient or a
   record-length quirk?
5. **Mode 0x00 payloads** (0x1050, 0x10E0, 0x1140, 0x1500 …) are almost certainly
   DSP register addresses. Cross-referencing them with the per-algorithm register
   table at 0x1F09C would name them.

## 9. Falsified along the way

* *"Mode 0x0A payloads are the Q0.23 coefficients"* (the working assumption in the
  brief) — **false**. 96% of them are ≤ 0xFFFF and are 16-bit register values. The
  Q0.23 coefficients are the type-2 record.
* *"Delay times in ms should reappear across the two instruments"* — **false**, and
  §5.2 explains why: both designs are round in samples, not in time.
* *"16 shared float values vs a 1.8 chance baseline is a correlation"* — **false**;
  the baseline was mis-specified. Splitting round from non-round removes the
  entire effect.
