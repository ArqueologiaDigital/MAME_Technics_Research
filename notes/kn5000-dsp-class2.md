# NEC uPD6383GF — CLASS 2, the largest unread instruction group

KN5000 IC311 effects DSP. Date: 2026-07-22.
Tool: `tools/kn5000_dsp_class2.py` (imports `kn5000_dsp_extract.py`,
`kn5000_dsp_coeffs.py`, `kn5000_dsp_params.py`; none of them is rewritten).
Companions: `notes/kn5000-dsp-encoding.md` (field map, terminator),
`notes/kn5000-dsp-reverb.md` (the reverb stage), `notes/kn5000-dsp-coefficients.md`,
`notes/kn5000-dsp-header.md`, `notes/kn5000-dsp-parameters.md`.

Every claim is tagged **MEASURED**, **INFERRED** or **SPECULATIVE**. §9 lists what is
falsified or explicitly not established.

---

## Headline

1. **NEGATIVE (MEASURED): class 2 does not decompose into sub-fields.** Neither `hi12`
   nor `lo12` splits into independent parts; inside class 2 they are two *coupled
   enumerated codes* of 27 and 28 values using 82 of 756 combinations. Every candidate
   bitfield split is ruled out in §3, with the numbers.
2. **POSITIVE (INFERRED, strong): the class-2/class-A distinction is
   multiply-vs-no-multiply.** Controlling for program length, the number of class-A
   words correlates **+0.44** with the size of the effect's coefficient bank and the
   number of class-2 words correlates **−0.36**. Class 2 is the *non-multiplying*
   datapath: moves, adds, state shuffling.
3. **POSITIVE (INFERRED, strong, three independent role assignments with controls):**
   * `lo12 ∈ {0x647, 0x687}` — the two non-multiply words of a **biquad filter
     section**. 15 of 38 program images, **zero false positives**, one false negative.
   * `hi12 = 0x082` — a **modulation-source (LFO) read**. Present in **all 17**
     LFO-bearing images, one false positive.
   * `hi12 = 0xC40` — an **envelope / level detector** step. Present in **all 7**
     envelope-following images, one false positive (the do-nothing program).
4. **addr8 VERDICT (INFERRED): class-2 `addr8` is not uniformly an absolute address.**
   A byte-identical section repeated 10 times over 5 different EQ bands proves that in
   at least one idiom `addr8` must be a small displacement applied to an advancing
   pointer; the phaser proves that in another idiom it is a direct index walking two
   256-word arrays. Both modes exist; class 2 and class A share the same address space.
5. **NEGATIVE (MEASURED): the reverb stage's own class-2 words resist this method.**
   `104.2.00.000` also appears in the PHASER, which has no delay line at all, so it
   cannot mean "read the delay". Reported as a contradiction, not explained away.

---

## 0. Corpus hygiene — a correction to the earlier notes (MEASURED)

The encoding note excludes algorithms **79** and **88** as malformed. Three more have
the same defect and were never caught: **89 (KARAOKE), 90 (BATH ROOM), 91 (STAGE)**.
Each parses to a 132-word "image" that

* does **not** end with the terminator landmark (`class4==1 && addr8∈{0x0E,0x0F}`),
* contains **zero class-2 words** — impossible for real effect code, which is 51–56 %
  class 2,
* has a class histogram unlike anything else in the corpus
  (`{0:57, 3:1, 4:18, 5:3, 6:5, 7:4, 8:23, 9:5, 10:5, 14:11}`),
* begins `001.4.56.C80 / 147.4.A8.002 / F76.A.10.147 …`, words that occur nowhere else.

Excluding all five gives **91 valid programs, 6532 words, 688 distinct** — exactly the
figures the encoding note reports for its 91-program corpus, which is the independent
check that this is the right exclusion set. The task brief's "841 distinct words" is
the 96-program figure and includes 153 words of junk from these five streams. The
class-2 count is unaffected: **429 distinct class-2 words either way**, because the
malformed streams contribute none.

## 1. INVENTORY (MEASURED)

91 programs, **38 distinct images** (42 slots share the 49-word `NO OPERATION`
program, 12 share the 133-word reverb).

| class4 | occurrences | distinct words |
|---|---|---|
| 0 | 148 | 10 |
| 1 | 981 | 37 |
| **2** | **3630** | **429** |
| 3 | 33 | 2 |
| 4 | 54 | 1 |
| 5 | 42 | 1 |
| 6 | 54 | 5 |
| 8 | 44 | 3 |
| A | 1546 | 200 |

Class 2 is **55.6 % of all code** and **62.4 % of the vocabulary**.

**Field occupancy inside class 2.** Three word bits have *zero* variance across all
3630 class-2 words: **bit 24** (`hi12` bit 0), **bit 11** and **bit 5** (`lo12` bits 11
and 5). Corpus-wide those bits are 2.4 %, 3.8 % and 3.7 % set (encoding note §3), so
class 2 is where the near-dead bits are dead. `hi12` takes 27 values (of 4096) and
`lo12` takes 28 (of 4096); `addr8` takes 105 of 256.

**Position and runs.** Class 2 is spread evenly through a program — mean normalised
position 0.484, median 0.500, decile histogram
`[391 459 321 273 357 383 425 432 275 314]`. It is 4/91 first words and **0/91 last
words** (the last word is always the class-1 terminator). Run lengths:
1×491, 2×490, 3×261, 4×46, 5×25, 6×8, 8×51, 10×44, longest 30. The 8- and 10-long
spikes are the reverb stage and the PEQ/phaser sections.

## 2. THE JOINT (hi12, lo12) STRUCTURE (MEASURED)

```
H(hi12) = 2.99 bits over 27 values
H(lo12) = 3.28 bits over 28 values
MI(hi12, lo12) = 1.17 bits         (1.96 bits measured over ALL classes)
combinations used: 82 of 27x28 = 756
```

Restricting to one class *reduces* the coupling (1.96 → 1.17 bits) but does not remove
it. The table (tool section 3) is dominated by `hi12 = 0x000`, which pairs with 17 of
the 28 `lo12` values, and by `lo12 = 0x000`, which pairs with 17 of the 27 `hi12`
values. `000.2.00.000` — both zero — is the most-shared non-trivial word in the corpus.

**INFERRED:** `hi12` and `lo12` are two *operation slots*, each with an idle encoding of
zero, and `000.2.00.000` is both slots idle — a NOP. This is consistent with the reverb
note's independent inference of that word as a pipeline slot, and with the DEC decoder
block on the CDJ-500 block diagram (p. 1-15): a decoded, not horizontally fanned-out,
word. It is **not proven**; a single 24-bit enumerated opcode split across the two ends
of the word would look the same.

## 3. ★ DOES CLASS 2 DECOMPOSE? — a clean negative (MEASURED)

The task was to look for sub-fields inside `hi12`/`lo12` now that the class is fixed:
source select, destination select, ALU function, accumulator, shifter. **It does not
work, and here is what rules it out.**

### 3.1 The 27 `hi12` values look decomposable and are not

```
 000 000000000000 x1638   002 000000000010 x48     010 000000010000 x2
 012 000000010010 x255    020 000000100000 x10     022 000000100010 x15
 024 000000100100 x2      026 000000100110 x26     028 000000101000 x18
 02A 000000101010 x42     02C 000000101100 x42     02E 000000101110 x139
 082 000010000010 x67     090 000010010000 x12     092 000010010010 x90
 0A2 000010100010 x8      0A6 000010100110 x6      102 000100000010 x122
 104 000100000100 x229    112 000100010010 x4      182 000110000010 x96
 202 001000000010 x133    204 001000000100 x50     212 001000010010 x517
 282 001010000010 x4      292 001010010010 x2      C40 110001000000 x53
```

The eye sees an obvious split: bit 0 dead, bit 6 dead (only `C40` sets it), a 3-bit
group at [3:1] that takes **all eight values** in the `0x02x` family, a 2-bit group at
[5:4] that takes only 0/1/2, and a high group [11:7] taking 0..5 (plus `C40` = 24).
So test it: `U = hi12[11:7]`, `V = hi12[5:4]`, `W = hi12[3:1]`.

```
 (U,V,W) combinations used: 27 of 6 x 3 x 8 = 168
 MI(U,V) = 0.30   MI(U,W) = 0.74   MI(V,W) = 0.73
 H(U)+H(V)+H(W) = 4.61 bits   vs   H(hi12) = 2.99 bits
```

Independent sub-fields would give MI ≈ 0 and the entropies would add. They do not:
1.6 bits of the 4.6 are redundancy between the supposed fields, and only 16 % of the
product space is used. **The split is refuted.**

### 3.2 `lo12` is a single enumerated code (MEASURED)

```
 000 x1301  00B x14   1C0 x227  1C8 x8    1CD x350  1CE x129  1D1 x2   1D5 x152
 2C7 x6     407 x431  40B x2    40E x224  412 x30   413 x4    415 x34  419 x258
 41D x4     447 x133  44C x12   44D x2    647 x39   655 x12   680 x121 687 x44
 688 x42    68B x1    6CE x1    700 x47
```

Split as `[11:8] . [7:0]`: **MI = 1.80 bits against H([11:8]) = 1.92 bits.** The high
nibble is very nearly a *function* of the low byte — it carries almost no independent
information. `lo12` behaves as one 28-entry enumeration, not two fields.

### 3.3 What this means

**MEASURED conclusion: class 2 is not a horizontal microcode word with separable
control fields.** `hi12` and `lo12` are two sparse enumerations chosen together by a
code generator, and the pairs that occur are dictated by what the operation is, not by
independent knobs. This is the negative result the brief asked to be reported plainly,
and it changes strategy: the way in is **which effects use a value**, not which bits it
sets. That is §4.

## 4. ★★ SEMANTICS BY EFFECT TOPOLOGY — three defensible role assignments

### 4.1 Method, and why it is a fair test

Every one of the 38 distinct program images was labelled from its **effect name only**,
with four textbook-DSP flags — `dram` (uses the external delay memory), `lfo` (has a
periodic modulator), `env` (has a level/envelope follower), `filt` (has a tunable
multi-pole filter). The table is in the tool (`IMG_CAT`) so it can be argued with.
Then every one of the 27 `hi12` and 28 `lo12` values was scored, as a *predictor of a
category*, over the 38 images by Matthews correlation.

This is a control-first design: a value that means "read the delay line" **must** appear
in delay effects and **must not** appear in effects without a delay line. Three values
pass at a level that survives Bonferroni correction for all 220 tests run
(27+28 values × 4 categories); everything else is reported too, including the near
misses.

### 4.2 `lo12 ∈ {0x647, 0x687}` = the biquad section — the strongest result

**MCC = +0.947 against `filt`. 15 members, ZERO false positives, one false negative.**
Exact hypergeometric p = 1.0e-9; Bonferroni-corrected over 220 tests, p = 2.3e-7.

```
 members  : AUTO WAH, AUTO WAH+S.DELAY, EXCITER, OVERDRIVE, PARAMETRIC EQ,
            PEQ+CHORUS, PEQ+COMPRESSOR, PEQ+COMPR+DIST, PEQ+COMPR+OVERDR,
            PEQ+DIST+DELAY, PEQ+FLANGER, PEQ+OVERDR+DELAY, PEQ+S.DELAY,
            PEQ+VIBRATO, ROCK ROTARY
 false +  : none
 false -  : ENHANCER
```

Every effect whose name contains PEQ, WAH, EQ, EXCITER, OVERDRIVE or ROTARY, and
nothing else. No reverb, no delay, no chorus, no flanger, no phaser, no distortion, no
compressor-without-EQ. The two values **co-occur exactly** — the same 15 images.

**Why it is a biquad, not just "a filter effect".** The PARAMETRIC EQ (algo 39, 105
words) is a nine-word section repeated **ten times, byte-identically**:

```
   000.A.00.1D3      class A
   212.A.01.412      class A
   202.A.01.1D5      class A
   202.A.01.1D4      class A
   202.A.00.1D5      class A
   102.2.FF.687      class 2  <-- 0x687
   804.8.16.415      class 8
   212.A.FF.407      class A
   000.2.03.647      class 2  <-- 0x647
```

**Five consecutive class-A words** on a chip with one 24×24 multiplier is exactly the
five multiply-accumulates of a second-order section
(`y = b0·x + b1·x₁ + b2·x₂ − a1·y₁ − a2·y₂`), and ten repetitions is **5 bands × 2
channels** for a machine whose parameter names include `BAND EMPHASIS FC` and whose
coefficient bank holds 45 values. The two class-2 words sit *after* the MAC run.

**INFERRED role:** `0x687` and `0x647` are the two **state-update / output-store** steps
of a biquad — the `x₂←x₁, x₁←x`, `y₂←y₁, y₁←y` shuffle and the accumulator write-out.
Which is which is **not** determined. Supporting: their neighbours are rigidly fixed —
`0x687` is preceded by `202.A.00.1D5` in 35/43 occurrences and followed by
`804.8.16.415` in 35/43; `0x647` is preceded by `212.A.FF.407` in 34/38.

**Honest caveat:** the false negative is real. ENHANCER is labelled `filt` here and has
no `0x647/0x687`. Two readings, neither tested: either an enhancer on this machine is a
harmonic generator with no biquad (in which case the label was wrong and the predictor
is perfect), or the biquad has a second encoding. **Not resolved.**

### 4.3 `hi12 = 0x082` = the modulation-source read

**MCC = +0.948 against `lfo`. 18 members, all 17 LFO images, one false positive.**
p = 6.3e-10 (Bonferroni 1.4e-7).

```
 members : CHORUS, MODULATED CHORUS, FLANGER, PHASER, ENSEMBLE, VIBRATO, AUTO PAN,
           RING MODULATOR, ROCK ROTARY, MIX UP, S.DELAY+{CHORUS,FLANGER,VIBRATO,
           PHASER}, PEQ+{CHORUS,FLANGER,VIBRATO}, ENHANCER
 false + : ENHANCER      false - : none
```

Zero occurrences in any reverb, any pure delay, the compressor, the parametric EQ, the
distortions, the exciter or either wah. **PREDICTION MADE BEFORE THE CHECK:** if this is
an LFO read it must be absent from *all* the envelope-driven effects, because an
envelope follower is not an oscillator — AUTO WAH is the discriminating case, since it
sweeps a filter like a phaser does but is driven by the input level. **AUTO WAH does not
contain it.** That is the prediction the assignment could most easily have failed, and
it passes.

The single word `082.2.00.1C0` accounts for all 67 occurrences and its context is
rigid: preceded by a class-A word with `hi12 ∈ {092,192}`, followed by `094.A.00.200`
or `C40.3.20.44C`. **INFERRED:** a three-word LFO idiom, of which the class-2 word is
the non-multiplying middle — most plausibly the phase-accumulator update or the read of
the modulator into the datapath. **SPECULATIVE** as to which.

The false positive, ENHANCER, is the same image that is the false negative in §4.2;
it is the one program whose textbook description this analysis clearly has wrong.

### 4.4 `hi12 = 0xC40` = the envelope / level detector

**MCC = +0.920 against `env`. 8 members, all 7 envelope images, one false positive.**
p = 6.3e-7 (Bonferroni 1.4e-4).

```
 members : COMPRESSOR, PEQ+COMPRESSOR, PEQ+COMPR+DIST, PEQ+COMPR+OVERDR,
           AUTO WAH, AUTO WAH+S.DELAY, GATED REVERB, NO OPERATION
 false + : NO OPERATION      false - : none
```

The three *independent* families that need a level follower — dynamics (compressor), a
level-swept filter (auto wah) and a level-gated tail (gated reverb) — and nothing else
among the 30 remaining images. The word is always `C40.2.C0.000` (`addr8` fixed at
`0xC0`, `lo12` zero) and its context is **12/12 rigid**: always preceded by
`104.A.00.1D5` and always followed by `182.A.00.000`. A three-word idiom, once per
channel.

The false positive is the 49-word `NO OPERATION` program (shared by 42 of the 91
slots, hence 42 of the 53 total occurrences). **SPECULATIVE:** the through path still
computes an input level, e.g. for a front-panel meter. Not tested; stated as the weak
point of this assignment.

`hi12 = 0x0A2` (MCC +0.722, 4 members, all four compressor images, zero false
positives, p = 4.7e-4) and `0x0A6` (MCC +0.616, 3 members, zero false positives) are the
same story one notch weaker and are **compressor-exclusive**. Together with `0xC40`
they make a small, coherent dynamics sub-vocabulary.

### 4.5 Everything else, for completeness (MEASURED)

The full ranked table is tool section 4. Second tier, none of which is claimed:
`hi12=026` (+0.641 env, 4 FP), `hi12=02A` (+0.568 filt, 4 FP), `hi12=092`/`182`
(+0.574 lfo, 10 FP each — supersets of the `082` set), `lo12=447` (+0.537 lfo),
`lo12=700` (+0.649 lfo, 8 FP). The very common values (`hi12` 000/212, `lo12`
000/1CD/40E/407) score at or near **MCC = 0.000** — as they must, since they appear in
essentially every image. That the *generic* words score zero and the *specific* words
score 0.9+ is itself the evidence that the method is measuring something real and not
manufacturing structure.

## 5. ★ CLASS 2 vs CLASS A: the multiply bit (INFERRED, strong)

Classes 2 and A differ in **one bit, word bit 23**, and between them are 80 % of all
code (encoding note §5). The corpus contains a clean minimal pair across that bit:

```
   PARAMETRIC EQ word 6   212.**A**.01.412
   PHASER        word 13  212.**2**.01.412
```

identical `hi12`, `addr8` and `lo12`; only bit 23 differs. So bit 23 is a modifier on
one operation, not a different operation.

**The test.** If class A multiplies by a coefficient and class 2 does not, then across
programs the class-A count must track the size of the uploaded coefficient bank, and the
class-2 count must not. Program length confounds both, so partial correlations over the
38 images (`PARAM_TABLE` coefficient counts, 5–45 per image):

```
   r(ncoeff, nwords)   = +0.858
   r(ncoeff, n_class2) = +0.549     r(nwords, n_class2) = +0.774
   r(ncoeff, n_classA) = +0.757     r(nwords, n_classA) = +0.691

   partial, controlling for program length:
        ncoeff . n_class2 | nwords = **-0.356**
        ncoeff . n_classA | nwords = **+0.442**
```

**The two classes move in opposite directions.** A longer program has more of both, but
a *coefficient-heavier* program has proportionally more class A and proportionally
*less* class 2.

**INFERRED: word bit 23 enables the multiplier; class A is the MAC family and class 2 is
the non-multiplying datapath — moves, adds, state shuffling, addressing.** Three
independent corroborations:

* PARAMETRIC EQ, the most coefficient-dense image (45 coefficients in 105 words), is
  **60 class A / 31 class 2**, and its biquad section is five class-A words in a row.
* The 133-word reverb, which walks ten gains through pointers, is **33 class A / 67
  class 2** — one multiply per stage (`102.A.00.64B`, already inferred as the gain
  multiply in the reverb note) and four class-2 words around it.
* PHASER is **14 class A / 83 class 2**, and is the one image that argues *against*:
  an all-pass chain needs a multiply per stage and its stages are class 2. This is a
  genuine tension and it is flagged, not smoothed over. One resolution — untested — is
  that bit 23 selects *which* operand goes to the multiplier rather than whether the
  multiplier runs.

## 6. ★ THE `addr8` VERDICT (INFERRED)

### 6.1 It is the same address space class A uses (MEASURED)

Class-2 `addr8` takes 105 of 256 values; class A takes 72. Within individual programs
the two classes' `addr8` sets **share 163 values**. Their high-nibble histograms are the
same shape:

```
  class 2  0:2434 3:47 4:135 5:18 7:16 8:16 A:21 B:95 C:75 F:764   (105 distinct)
  class A  0:1132 3:3  4:44  5:9  8:12 9:1  A:7  B:98 C:11 F:219   ( 72 distinct)
  class 1  0:91 2:343 3:111 6:380 8:48 E:8                         (  7 distinct)
```

Class 1 is completely different (7 values, the selector use the encoding note found).
**INFERRED: class 2 and class A address one common 8-bit operand space.** Which of
C-RAM and D-RAM — or whether a bank bit elsewhere chooses — is **not established**.

### 6.2 It cannot always be an absolute address — the decisive case (MEASURED)

The PARAMETRIC EQ section of §4.2 is repeated **ten times, byte-identically**, with
`addr8` values `0x00, 0x01, 0xFF, 0x03`. Those ten repetitions are five EQ bands ×
two channels; they *must* read ten different coefficient sets and maintain ten
different state pairs. The whole program uses only `{00,02,03,0A,0B,40,54,AD,F7,FF}` in
class 2 and `{00,01,FF}` in class A, against a 45-value coefficient bank.

**A fixed absolute address cannot address ten different bands.** Therefore in this idiom
`addr8` is a **displacement applied to a pointer that advances between sections** —
exactly the CP/DP/BP1/BP2/PR1/PR2 + BNK-R machinery on the block diagram, and exactly
what the reverb note independently inferred from *its* byte-identical stage. The
displacement values `+1, +1, +1, 0, −1` (`0x01,0x01,0x01,0x00,0xFF`) walking a
five-coefficient biquad set are the natural reading.

Supporting distribution statistic: **88.1 % of all class-2 `addr8` values lie within 16
of zero modulo 256** (0x00–0x10 or 0xF0–0xFF), and 87.4 % of class A. For class 1 the
figure is 9.3 %. A field that is 88 % small-signed looks like a displacement.

### 6.3 …but sometimes it plainly is one (MEASURED)

The PHASER's all-pass chain is a three-word section repeated nine times per channel in
which `addr8` is **not** constant:

```
    102.2.45.1CD      102.2.46.1CD      102.2.47.1CD    ...  0x45 -> 0x58 ascending
    212.2.01.412      212.2.01.412      212.2.01.412
    104.2.BA.1D5      104.2.B9.1D5      104.2.B8.1D5    ...  0xBA -> 0xA8 descending
```

Two contiguous runs of twenty addresses each, one ascending and one descending in
lock-step, in the same program: `0x45..0x58` and `0xA8..0xBB`. That is two twenty-entry
arrays indexed directly by the instruction — a coefficient bank and a state bank
(**INFERRED** as to which is which). Neither run appears in the PHASER's `T1` parameter
map (`05 06 08 09 00 0C 13 14 02 0A 06 90 1D`), so these are static coefficients from
`PARAM_TABLE`, not user parameters — no contradiction with the parameter note.

**VERDICT (INFERRED): `addr8` in class 2 carries an 8-bit operand address in the shared
C-RAM/D-RAM space, and the addressing MODE is not carried in `addr8` itself.** Some
class-2 operations take it as a small signed displacement off a pointer register (PEQ
`0x687/0x647`, the whole reverb stage at displacement 0); others take it as a direct
index (PHASER `0x1CD/0x1D5`). Since the mode co-varies with `lo12` and not with any
bit of `addr8`, **INFERRED: the addressing mode is part of the operation enumeration in
`lo12`/`hi12`.** This also disposes of the temptation to read the whole field as signed:
`0x45`, `0x54`, `0xB0`, `0xC0` are used and are not small displacements.

### 6.4 Coefficient-bank correlation (MEASURED, negative)

The brief asked whether class-2 `addr8` spread tracks coefficient-bank size. It does
not, and §6.2 explains why: the programs with the *largest* banks are exactly the ones
that walk them with pointers and therefore use the *fewest* distinct `addr8` values.
The 133-word reverb has 41 coefficients and **12** distinct non-zero class-2 `addr8`
values; PARAMETRIC EQ has 45 coefficients and **9**; PHASER has 32 and **49**. The
encoding note's corpus-wide r = 0.135 was measuring this same cancellation.

## 7. THE REVERB STAGE — what the anchor gives, and what it does not (MEASURED)

The stage (reverb note §1), with what is now known:

```
   880.1.60.2D4     class 1   opens the per-stage external-DRAM transaction  (INFERRED, reverb note)
   104.2.00.000     class 2   -- 5 images: REVERBx12, GATED REVERB, PHASER, S.DELAY+PHASER, ENHANCER
   000.2.00.419     class 2   -- 2 images: REVERBx12, GATED REVERB
   012.2.00.680     class 2   -- 2 images: REVERBx12, GATED REVERB
   880.1.20.655     class 1   closes the transaction                          (INFERRED, reverb note)
   102.A.00.64B     class A   the gain multiply -- and class A is now the MAC family (§5)
   000.2.00.000     class 2   NOP / pipeline slot -- 15 images
   000.2.00.000     class 2
```

**The one thing the anchor does settle:** the stage is *one* class-A word among four
class-2 words, and §5 shows class A is where the coefficient multiply lives. An
all-pass `w = x + g·d`, `y = d − g·w`, `d ← w` needs **one multiply and two adds** —
one class A and the rest class 2. The stage's class split matches the algebra of a
single all-pass exactly. **INFERRED**, and it is the strongest independent support the
reverb note's topology has received.

**The thing it does not settle, stated as a contradiction rather than explained away:**

> `104.2.00.000` occurs in **PHASER** and **S.DELAY+PHASER**. A phaser is a chain of
> one-sample all-pass sections; it has no external delay line at all (the PHASER's
> parameter stream carries zero mode-0x0B delay entries and no address chain). So this
> word **cannot** mean "read the delay output into the multiplier", which is the role
> the all-pass argument wants to assign to the stage's first class-2 word. Any decode
> of the reverb stage that starts by calling `104.2.00.000` a delay read is wrong.

`000.2.00.419` and `012.2.00.680` are cleaner — they occur only in the reverb and gated
reverb images — but *only two images* is not a control, it is a coincidence waiting to
happen. `lo12 = 0x419` scores MCC +0.436 against `dram` with **12 false negatives**,
including MULTI TAP DELAY and the whole chorus family, all of which certainly read the
external delay memory. So `0x419` is not a generic delay read either. **No role is
claimed for any of the four.**

`000.2.00.000` — 273 occurrences over 15 distinct images, all fields zero, appearing as
an adjacent pair after a multiply — remains the NOP the reverb note inferred, and §2
adds the encoding argument (both operation slots idle). **INFERRED.**

## 8. Reproducing

```
python3 tools/kn5000_dsp_extract.py \
    kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_class2.py \
    kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs \
    --names kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom
```

Sections: `inventory fields joint semantics mac addr8 reverb`.

## 9. Falsified, or explicitly not established

* **"Class 2 decomposes into sub-fields."** REFUTED (§3). The `U/V/W` split of `hi12`
  leaves 1.6 bits of redundancy and uses 16 % of its product space; the `[11:8].[7:0]`
  split of `lo12` has MI 1.80 against H 1.92.
* **"`hi12`/`lo12` separate once the class is fixed."** Partly. Coupling drops from
  1.96 to 1.17 bits — real but not separation.
* **"The reverb stage's class-2 words are delay reads/writes."** NOT SUPPORTED (§7);
  `104.2.00.000` occurs in a phaser.
* **"`addr8` is uniformly an absolute address"** and **"`addr8` is uniformly a signed
  displacement."** Both refuted (§6.2 / §6.3). Two modes coexist.
* **"Class-2 `addr8` spread tracks coefficient-bank size."** REFUTED (§6.4), with the
  mechanism identified.
* **89/90/91 are valid programs.** REFUTED (§0). Three more malformed streams than the
  encoding note records.
* **NOT ESTABLISHED:** which of C-RAM/D-RAM `addr8` selects; which of `0x647`/`0x687`
  is the state shuffle and which the output store; what the other 24 `hi12` and 25
  `lo12` values mean; where the COND field is; whether bit 23 is multiplier-enable or
  multiplier-operand-select (the PHASER tension in §5).

## 10. Next experiments, in order of value

1. **Settle bit 23.** The PHASER is the counterexample. Decode one PHASER all-pass
   section by hand against the algebra `y = −a·x + x₁ + a·y₁` and see whether its two
   class-2 words can carry a multiply. If they cannot, the phaser gain must come from
   somewhere else and §5 stands unqualified.
2. **Use the 83-word common header** (`notes/kn5000-dsp-header.md`; already on disk).
   90 % of its vocabulary is unique to it, and it is only 27 % class 2 — so whatever
   class 2 *is*, the header shows it in a different context, next to the loop control
   and the DRAM setup this corpus lacks.
3. **Attack `lo12 = 0x647/0x687` numerically.** The PEQ's 45 coefficients and its 5×2
   biquad sections are a closed system: assign the 45 values to 10 sections and check
   they are realisable biquads (stable poles, sane centre frequencies against the
   ISO ⅓-octave value list at main-CPU `0x032390`). If they are, §4.2 goes from
   INFERRED to something much closer to proven, and the EQ becomes the first fully
   understood program on this chip.
4. **Resolve ENHANCER**, which is the sole false positive of §4.3 and the sole false
   negative of §4.2. One program, and it is the only image whose category labels this
   analysis is visibly getting wrong.

---

## CORRECTION (main agent, verification pass): the biquad section repeats 8x, not 10x

§ on the PARAMETRIC EQ states "a 9-word section repeated **10x** byte-identically = 5 bands x 2
channels". Independently re-checked against the extracted program images. **The structural claim
holds; the count does not.**

MEASURED, by exhaustive search for the most-repeated 9-word block in every program:

  * The maximum 9-word byte-identical repetition **anywhere in the corpus is 8**, in algo39
    (105 words). No program reaches 10.
  * algo39's block starts at indices `[5, 14, 23, 32, 59, 68, 77, 86]` -- **two groups of four**,
    contiguous within each group, with a gap between index 41 and 59.

So the reading is **4 bands x 2 channels = 8**, not 5 x 2 = 10. The "5 bands" figure appears to have
been carried over from the coefficient note's "45 register values ~ 5 bands x 3" rather than
measured off the program, and the two do not agree. Which of the two is right about the band count
is UNRESOLVED -- but the microcode says four sections per channel.

WHAT THE CHECK CONFIRMS, and it is the substantive part:

```
000.A.00.1D3        class A  \
212.A.01.412        class A   |
202.A.01.1D5        class A   >  FIVE CONSECUTIVE class-A multiplies  (b0,b1,b2,a1,a2)
202.A.01.1D4        class A   |
202.A.00.1D5        class A  /
102.2.FF.687        class 2  <- lo12 = 0x687
804.8.16.415        class 8
212.A.FF.407        class A
000.2.03.647        class 2  <- lo12 = 0x647
```

Five consecutive class-A multiplies is exactly a biquad's five coefficients, and **both** of the
`lo12` values this note identifies as "the biquad section's two non-multiply steps" (0x647, 0x687)
are present in that block, in that section, as claimed. The identification survives; only the
multiplicity was wrong.

Also verified from this pass: the corpus correction is exact. Programs **79, 88, 89, 90, 91** are the
five lacking a terminator, and each contains **zero** class-2 words -- confirming they are a
different kind of stream and rightly excluded (96 - 5 = 91).
