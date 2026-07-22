# NEC uPD6383GF — the biquad section, coefficient by coefficient

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_biquadmap.py` (imports `kn5000_dsp_biquad.py`, which imports
`kn5000_dsp_class2.py` → `_extract` / `_coeffs` / `_params`; **none of them is edited**).

**Append-only successor material.** It does not edit `notes/kn5000-dsp-biquad.md`,
`notes/kn5000-dsp-biquad-coeffs.md`, `notes/kn5000-dsp-class2*.md`,
`notes/kn5000-dsp-parameters.md`, `notes/kn5000-dsp-coefficients.md`,
`notes/kn5000-dsp-encoding.md`, `notes/kn5000-dsp-header.md` or
`notes/kn5000-dsp-reverb.md`. Corrections to them are in §8.

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or
**SPECULATIVE**. §9 lists what is falsified or not established.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_biquadmap.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
```
Sections: `section srctest sixth static class8 align score cursormap decode layout`.

---

## Headline

1. **★★★ The coefficient cursor is measured, not assumed.** The number of class-A words
   that precede a biquad section — reset to 0 by the `801.0.00.021` rewind — **is** the
   coefficient block address the host writes for that band. It reproduces `T1 op 0x70`
   **entry for entry** in 8 images, including all ten of `PARAMETRIC EQ`'s
   (`0 6 12 18 24 | 0 6 12 18 24` vs host `00 06 0C 12 18`, channel 1 sharing after the
   rewind). **MEASURED.** (§2)
2. **★★★ The advance is +1 per class-A word, so a section consumes SIX coefficient
   words, and the sixth is real.** 5 bands × 6 = 30 = exactly the region the program
   loader fills (`801.0.00.821` then 30 words, then `801.0.1E.821` + 1 word). (§2.2, §3)
3. **★★★ The five names are pinned to slots by INVERTING REAL COEFFICIENTS**, not by
   emission order alone (§4). Read as `+0 = b1, +1 = b0, +2 = b2, +3 = −a1/a0` (Q1.22)
   and `+4 = −a2/a0` (Q0.23), the static banks come out as textbook filters with **round
   ISO frequencies**:
   * `OVERDRIVE` → **4000.0 Hz, Q = 0.7070**, numerator exactly **(1, 2, 1)** — a
     Butterworth **lowpass**, gain 0.6666.
   * `EXCITER` → **4000.0 Hz, Q = 0.1000**, numerator exactly **(1, 0, −1)** — a
     **bandpass**, peak gain 1.0000, i.e. the helper's mode 1.
   * `PARAMETRIC EQ` defaults → **5000, 250, 2500, 4000, 6300 Hz**, all **Q = 0.1000**,
     bands 2–5 **exactly flat** (`b ≡ a`, DC gain 1.0000).
   Five significant figures of agreement with `tan(π f0/44100)`, on filters nobody
   designed for this test.
4. **★★ The sixth multiply is a per-section OUTPUT MAKE-UP GAIN** (§3). Its operand is
   the block's 6th word, written **once at program load** and **never by the parameter
   path** (`op 0x70` writes five). Measured values, and the identity that closes it:

   | image | 6th word | Q1.22 | live numerator scaling | product |
   |---|---|---|---|---|
   | `PARAMETRIC EQ` (runtime) | `800000` | **−2.0000** | 0.500000 (the helper's fixed ½) | **−1.000** |
   | `OVERDRIVE` | `600201` | **+1.5001** | DC gain 0.6666 | **+1.000** |
   | `EXCITER` | `400000` | **+1.0000** | peak gain 1.0000 | **+1.000** |

   **Three for three**: the sixth coefficient is the reciprocal of the section's
   numerator scaling. For the PEQ it is exactly the ×2 that undoes the designer's
   −6.02 dB headroom halving, with a sign inversion. **MEASURED**; the *sign* is
   unexplained (§9).
5. **★ The `[0]`-is-the-chain-source prediction is FALSIFIED** (§5). All **ten** of
   algorithm 39's sections carry the identical `000.A.00.1D3`; band 1 is not
   distinguished from bands 2–5, in either channel. `hi12` of `[0]` varies **per effect
   stage**, never within a chain (`102` = the overdrive tone stage in both `OVERDRIVE`
   and `PEQ+OVERDR+DELAY`, `212` = `EXCITER`, `022` = `PEQ+S.DELAY` ch0, `292` = `ROCK
   ROTARY`). Cascading is therefore implicit, not addressed.
6. **★ The class-8 word is NOT demonstrably a shifter** (§6). It occurs in **15 images,
   every one of them filter-bearing** (`class8` vs `filt`: TP 15, FP 0, FN 1,
   **MCC +0.947**; the sole FN is `ENHANCER`) and in **no** other image — the opposite of
   what a general fixed-point rescaler would do. The specific "1-bit Q1.22 → Q0.23
   correction" story is killed by two measurements: under the now-measured slot map the
   Q0.23 word is read at `[4]`, **two words before** the class-8 word, and `AUTO WAH`
   carries the same class-8 family **between the same two P-consumers with no multiply
   between them at all**.
7. **★ The `ROCK ROTARY` anomaly is resolved** (§6.3): it *does* have a biquad section,
   at words 17..25, differing from the reference in **three** words (`[0]`, `[1]`, `[8]`).
   The d ≤ 2 instrument that flagged it as "a class-8 word with no section" was one notch
   too tight — the same blindness, one more time.
8. **★ The two-space question moves** (§7): a class-A word reads **two** operands by
   **two different mechanisms** — a coefficient from an implicitly auto-incremented
   pointer (no address field) and a data word from the signed `addr8` post-increment
   cursor. Nothing has to *select* between the two memories, because every multiply
   touches both. That is a concrete answer to "what picks C-RAM vs D-RAM in a body word":
   possibly nothing does.

---

## 1. The section (MEASURED, restated for reference)

```
   idx  word        hi12 cls addr8 lo12  signed  role
   [0] 0000A001D3   000   A    00   1D3    +0   class A multiply   <- only varying word
   [1] 0212A01412   212   A    01   412    +1   class A multiply
   [2] 0202A011D5   202   A    01   1D5    +1   class A multiply
   [3] 0202A011D4   202   A    01   1D4    +1   class A multiply
   [4] 0202A001D5   202   A    00   1D5    +0   class A multiply
   [5] 01022FF687   102   2    FF   687    -1   P-consumer (store)
   [6] 0804816415   804   8    16   415   (+22) class 8, operand-less
   [7] 0212AFF407   212   A    FF   407    -1   class A multiply   <- the SIXTH
   [8] 0000203647   000   2    03   647    +3   P-consumer (store)
```

## 2. ★★★ The coefficient cursor, measured against the host

### 2.1 The prediction, stated before it was run

> If the coefficient pointer advances by exactly one per class-A word and is reset to 0
> by `801.0.00.021`, then **counting class-A words** from the start of a microprogram to
> a biquad section must yield **the address the host writes that band's coefficients to**
> — a number produced by a completely different table (`T1`, in the sub-CPU's parameter
> ROM) that the microcode knows nothing about.

### 2.2 The result (MEASURED, tool section `cursormap`)

```
   algo  name                sections at        class-A prefix          host T1 op70
    39  PARAMETRIC EQ    5 14 23 32 41|59 68 77 86 95   0 6 12 18 24|0 6 12 18 24   00 06 0C 12 18 | (64 68 6C 70 74)
    35  EXCITER                     18  53                     3  14                 03 0E      MATCH
    71  PEQ+CHORUS                   9  60                     2  18                 02 12      MATCH
    72  PEQ+S.DELAY                  4  30                     0  10                 00 0A      MATCH
    73  PEQ+FLANGER                 13  62                     4  20                 04 14      MATCH
    74  PEQ+VIBRATO                 13  55                     4  17                 04 11      MATCH
    98  PEQ+DIST+DELAY               2  48                     0  14                 00 0E      MATCH
    99  PEQ+OVERDR+DELAY   2 23 54 75            0 8 20 28                 00 14      MATCH on the two PEQ sections (0, 20)
    33  OVERDRIVE                   16  47                     2  11                 (no op 70; static bank, see below)
    15  ROCK ROTARY                 17                          5                    (no op 70)
    75  PEQ+COMPRESSOR               2  32                     0  11                 00 0F      off by +4
    96  PEQ+COMPR+DIST               2  48                     0  15                 00 13      off by +4
    97  PEQ+COMPR+OVERDR             2  51                     0  18                 00 16      off by +4
```

* **Algorithm 39 is exact in both channels**: `0 6 12 18 24` = `00 06 0C 12 18`, and after
  the `801.0.00.021` rewind channel 1 counts `0 6 12 18 24` again — **the channels share
  the coefficients**, which is what the biquad note predicted from the rewind word and
  what the host's single five-address group requires.
* **Six per band is forced**: the gaps are 6, so the cursor advances **6 per section**,
  i.e. **one per class-A word** including `[7]`. Five per band would give `0 5 10 15 20`
  and would disagree with the host at every band after the first.
* **The three compressor images miss by exactly +4, all three.** A systematic, equal
  offset is a *finding*, not noise: something in the compressor stage consumes four
  coefficient words through instructions that are not class A. **NOT IDENTIFIED.**
* `PEQ+OVERDR+DELAY` predicts `0` and `20` for its two PEQ sections and the host writes
  `00` and `0x14 = 20`; its other two sections are overdrive tone stages with no `op 70`.

### 2.3 The region, independently (MEASURED, tool section `static`)

Algorithm 39's parameter stream loads its default coefficients with the *proven* pointer
idiom and a single op-2 block:

```
   op1  ... 08 01 00 08 21   = 801.0.00.821   pointer <- 0x00
   op2  30 words:
        +00: E94DC5 D216A0 4BE6A5 16B23A 440573 800000
        +06: 936A5A 400000 2CA749 6C95A5 A6B16C 800000
        +0C: D445EF 400000 EEA7BE 2BBA10 22B082 800000
        +12: E2DAF3 400000 E29D98 1D250C 3AC4CE 800000
        +18: EFBE48 400000 DA12DF 1041B7 4BDA41 800000
   op1  ... 08 01 1E 08 21   = 801.0.1E.821   pointer <- 0x1E
   op2  1 word:  200000
```

**Five blocks of six, 30 words, `0x00..0x1D`, then a separate single word at `0x1E`.**
The block size is in the data, not inferred from a stride. `OVERDRIVE` loads 19 words at
`0x00` (`2 + 6 + 1` twice, plus a trailing `200000`) and its class-A prefixes are 2 and
11 — `2 + 9 = 11`. `EXCITER` loads 23 (`3 + 6 + 2` twice + 1) and its prefixes are 3 and
14. **Every count closes.**

## 3. ★★ The sixth multiply

`[7] 212.A.FF.407` reads coefficient slot **`NN+5`**. What is there:

* **`PARAMETRIC EQ`: `0x800000` in all five bands** — `−2.0000` as Q1.22, `−1.0000` as
  Q0.23. **`op 0x70` never writes it** (it emits five words at `NN+0..NN+4`, proven by
  construction in the coefficients note), so it keeps its load-time value forever.
* `OVERDRIVE`: `0x600201` = `+1.5001` (Q1.22). `EXCITER`: `0x400000` = `+1.0000`.

The identity in headline 4 holds in all three live configurations: **6th word × the
section's numerator scaling = ±1**. `OVERDRIVE`'s static lowpass has DC gain `0.6666` and
its 6th word is `1.5001`; `EXCITER`'s bandpass peaks at `1.0000` and its 6th word is
`1.0000`; the PEQ designer halves its numerator (`DC gain 0.500000`, coefficients note
§7) and its 6th word is `−2.0000`.

> **INFERRED, strong:** the sixth class-A multiply is the section's **output make-up
> gain**, and in the PEQ it is precisely the compensation for the fixed ½ that buys the
> boost case its 6 dB of headroom. Of the brief's three candidates this is the second
> one. The first — a per-band user trim — is **excluded**, because nothing in the
> parameter path ever writes `NN+5`. The third — part of the state update — is
> **excluded**, because the operand is a coefficient-space word, not a state cell.
> **NOT EXPLAINED:** why the PEQ's constant is *negative* while the other two are
> positive. Either the section accumulates the PEQ's sum with the opposite sign, or a
> later stage inverts. Not established (§9).

## 4. ★★★ Coefficient → multiply, and how it was pinned

The naive argument (emission order + one fetch per class-A word) gives

```
   [0] = b1     [1] = b0     [2] = b2     [3] = -a1/a0     [4] = -a2/a0     [7] = make-up
```

That is a mapping produced by counting, so it needs an independent check. The check is
that these are **real numbers in ROM**, and a wrong slot order makes them nonsense.
Tool section `decode`, using only the bilinear identities `4/a0 = 1 − a1 + a2` and
`4K²/a0 = 1 + a1 + a2` with `K = tan(π f0/44100)`:

```
  algo 33 OVERDRIVE  +02: 04E168 0270B4 0270B4 4E0149 C6B45F 600201
      b = [+0.038129 +0.076258 +0.038129]   a = [1 -1.218828 +0.447621]   STABLE
      f0 = 4000.0 Hz   Q = 0.7070   DC gain = +0.6666   Nyquist gain = 0.0000
      numerator shape  b1/b0 = +2.00000  b2/b0 = +1.00000     <== LOWPASS (1,2,1)

  algo 35 EXCITER    +03: 000000 2EB133 D14ECC 1D250C 3AC4CE 400000
      b = [+0.729565 +0.000000 -0.729566]   a = [1 -0.455386 -0.459131]   STABLE
      f0 = 4000.0 Hz   Q = 0.1000   DC gain = 0.0000
      numerator shape  b1/b0 = +0.00000  b2/b0 = -1.00000     <== BANDPASS (1,0,-1)

  algo 39 PARAMETRIC EQ, the five default bands
      +00  f0 = 5000.0 Hz  Q = 0.1000   DC 1.0000  Nyquist 1.0000
      +06  f0 =  250.0 Hz  Q = 0.1000   b == a to 4e-4  (FLAT)
      +0C  f0 = 2500.0 Hz  Q = 0.1000   b == a          (FLAT)
      +12  f0 = 4000.0 Hz  Q = 0.1000   b == a          (FLAT)
      +18  f0 = 6300.0 Hz  Q = 0.1000   b == a          (FLAT)
```

**Everything lands on a table entry.** `250, 2500, 4000, 5000, 6300` are all in the
27-entry ISO ⅓-octave table at `0x012397`; `0.1` is the first entry of the Q table at
`0x012403`; `0.707` is Butterworth. Four of the five PEQ bands are **exactly flat**
(`b ≡ a`, unity at every frequency) — which is what a power-on default parametric EQ
must be, and it is a property no wrong slot order produces.

**Uniqueness (MEASURED, the permutation control).** Over the 9 blocks, only **18 of the
120** slot orders leave every block stable; requiring in addition that every recovered
`f0` sit within 0.2 % of an ISO centre and every `Q` lie in the designer's 0.1…20 range
leaves **6**, and all six agree that `+3 = −a1/a0` and `+4 = −a2/a0` — the denominator
slots are **uniquely determined**, because `f0` and `Q` depend on nothing else. The three
numerator slots are then pinned by shape, not by permutation counting:

* `EXCITER`'s slot `+0` is **exactly zero**, and the only biquad numerator coefficient
  that is identically zero in the helper is **`b1`** (mode 1, bandpass). So `+0 = b1`.
* `OVERDRIVE`'s slot `+0` is **exactly twice** slots `+1` and `+2`, which are equal —
  the `(1, 2, 1)` lowpass numerator, in which only `b1` is the doubled term. Same answer,
  different filter.
* `EXCITER` fixes the remaining pair by **sign**: a bandpass has `b0 = +A/a0 > 0` and
  `b2 = −b0 < 0`; slot `+1` is `+0.7296` and slot `+2` is `−0.7296`. So `+1 = b0`,
  `+2 = b2`.

> **The assignment is therefore MEASURED, and it agrees with the emission order.**
> This **supersedes** the biquad-coefficients note §6, which inferred
> `[1] = b1 … [7] = −a2` by skipping `[0]`: that reading needs only five fetches per
> band, which contradicts §2.2's `0 6 12 18 24`, and it needs `NN+5` to hold `−a2`,
> which contradicts §3's measured constant.

### 4.1 The residual: PEQ band 1's default (MEASURED, unexplained)

Band `+00` inverts to a legitimate stable section at 5000 Hz / Q 0.1 with unity gain at
DC *and* Nyquist, and its `b1` equals `a1` exactly (the helper's verbatim `n1 = a1`
copy). But `b0 = −0.7174` and `b2 = +1.1860`, and a mode-0 peaking numerator requires
`b0 > 0`. The sum and difference are informative: `(b0+b2)/2 = 0.2343` matches
`(1+K²)/a0 = 0.2342` to four digits, and `(b0−b2)/2 = −0.9517` gives `|V| = 1.2427`, i.e.
**|gain| = 1.887 dB with the `AV` term carrying the opposite sign** to the current
boost branch. So the numerator *is* a peaking numerator; only the sign convention of its
outer terms differs from the helper's boost arm. Whether that means "band 1's factory
default is a 1.9 dB dip" or "the cut arm stores `b0`/`b2` swapped" is **NOT ESTABLISHED**
— the block is overwritten the moment the host touches a parameter.

## 5. ★ The `[0]` source-selector test — FALSIFIED

The brief's falsifier, run as specified (tool section `srctest`, 34 sections at d ≤ 2):

```
   algorithm 39, hi12 of word [0] in program order:
       000 000 000 000 000 | 000 000 000 000 000
   distinct values: {000}
```

**The first band of a chain is not distinguished from the fourth.** If `hi12` selected
the operand source, band 1 (channel input) and bands 2–5 (previous band's output) would
differ. They do not — in either channel. **PREDICTION FALSIFIED.**

What `hi12` of `[0]` *does* track (MEASURED):

```
   000  x27  every PEQ section in every image
   102  x4   OVERDRIVE #0/#1 and PEQ+OVERDR+DELAY #1/#3   (the overdrive tone stage)
   212  x2   EXCITER #0/#1
   022  x1   PEQ+S.DELAY #0
   292  x1   ROCK ROTARY -- from the d<=3 aligned window of §6.3, not in this d<=2 table
```

It is **constant within an image and within a chain**, and changes only between *stages
of different kinds*. `102` picking out exactly the overdrive tone stage in two different
algorithms — including the composite one, where it coexists with `000` PEQ sections — is
the cleanest signal in the table.

> **INFERRED:** `hi12` names the *bus or tap* a stage reads, at stage granularity;
> **cascading within a chain is implicit** (the working value stays wherever the previous
> section left it, most plausibly the accumulator), which is why five identical
> instruction words can implement five different bands. This is consistent with the
> section being a reusable kernel and with the fact that a band's *only* per-band state
> is reached through cursors.

## 6. The class-8 word — verdict: not a shifter, as far as anything shows

### 6.1 The whole class-8 vocabulary (MEASURED, 42 words in 15 distinct images)

```
   804.8.16.415   35   ROCK ROTARY, OVERDRIVE, EXCITER, PARAMETRIC EQ, and the 9 PEQ+ combos
   804.8.16.1DA    4   AUTO WAH, AUTO WAH+S.DELAY
   80A.8.16.000    3   ROCK ROTARY, PEQ+COMPR+OVERDR
```

`addr8 = 0x16` in every one — the constant the biquad note already reported, and the
reason the word carries no address operand.

### 6.2 The test the hypothesis fails

> **PRE-REGISTERED (from the brief):** a shifter "should appear wherever fixed-point
> rescaling is needed — e.g. after accumulation, or in effects with gain staging — and
> NOT in pure data movement."

```
   class8 vs filt   TP=15 FP=0 FN=1 TN=22   MCC=+0.947     (FN = ENHANCER)
   class8 vs dram   TP= 8 FP=7 FN=16 TN= 7  MCC=-0.164
   class8 vs lfo    TP= 4 FP=11 FN=13 TN=10 MCC=-0.293
   class8 vs env    TP= 5 FP=10 FN= 2 TN=21 MCC=+0.311
```

Class 8 appears in **filter-bearing images and nowhere else**. Every one of the 22
class-8-free images has gain staging — `COMPRESSOR` has an explicit make-up gain,
`REVERB x12` has twelve of them — and none of them contains a class-8 word. A
general-purpose scaler with that distribution is not credible.

Two further measurements kill the *specific* 1-bit story:

* Under §4's measured slot map the Q0.23 coefficient `−a2/a0` is fetched at **`[4]`**,
  **two instructions before** the class-8 word; the multiply that *follows* the class-8
  word reads `NN+5`, whose PEQ value `0x800000` is the same bit pattern in either format.
  So the scale change does **not** land across the class-8 word.
* `AUTO WAH` carries `804.8.16.1DA` in the analogous slot **between the same two
  P-consumer families and with no multiply between them at all**:
  `204.2.FE.687  [804.8.16.1DA]  000.2.FF.647`. Its position is tied to the **store
  pair**, not to any multiply's operand format.

> **VERDICT:** the shifter reading is **NOT SUPPORTED**. What class 8 correlates with is
> *"this is a filter section's output step"*: one per section, 1:1, and only in filters.
> A rescale/round/saturate confined to filter outputs remains possible and is
> **SPECULATIVE**; nothing measured requires a shift. `addr8 = 0x16` is still unexplained.

### 6.3 ★ `ROCK ROTARY` — anomaly resolved (MEASURED)

Aligning a 9-word window on **every** class-8 word so the class-8 word sits at offset 6
(tool section `align`) and scoring the distance to the reference section:

```
   804.8.16.415 : d=0: 8   d=1: 19   d=2: 7   d=3: 1
   804.8.16.1DA : d=9: 4          80A.8.16.000 : d=9: 3
```

**All 35 occurrences of `804.8.16.415` sit at offset 6 of a window that is the biquad
section to within 3 words.** The one at d = 3 is `ROCK ROTARY` idx 23:

```
   *292.A.00.1D3  *212.A.01.452   202.A.01.1D5  202.A.01.1D4  202.A.00.1D5
    102.2.FF.687   804.8.16.415   212.A.FF.407 *000.2.BB.647
```

Words `[2]..[7]` are byte-identical to the reference; `[0]`, `[1]`, `[8]` differ.
So `ROCK ROTARY` **has** a biquad section (its `filt=1` label was right), and the biquad
note §5's "the only mismatch" was an artefact of a d ≤ 2 cut-off. Its second class-8 word
belongs to a *different* 9-word family (`292.A.01.1D5 182.A.FF.1D4 282.A.01.692
[80A.8.16.000] 212.2.*.447 …`) that occurs in exactly `ROCK ROTARY` and
`PEQ+COMPR+OVERDR` — a second, undecoded section type, not a stray word.

## 7. TASK C — the per-band layout

**Two spaces, two addressing mechanisms, one instruction touching both.**

```
COEFFICIENT space -- implicit auto-increment pointer, no address field in the word
   NN+0   b1        Q1.22   } written by op 0x70 at every parameter edit
   NN+1   b0        Q1.22   }   (LABEL_03A933 -> 0387E6 + 4 x 0388B3)
   NN+2   b2        Q1.22   }
   NN+3   -a1/a0    Q1.22   }
   NN+4   -a2/a0    Q0.23   }
   NN+5   make-up gain      <- load-time constant, never rewritten
   base = 6 x band, region 0x00..0x1D for algo 39; rewound to 0 by 801.0.00.021
   (channel 1 of algo 39 SHARES; the one-band combination effects do not)

STATE space -- signed addr8 post-increment cursor, +4 per band
   S0  read by [0] and [1]
   S1  read by [2],  WRITTEN by [8]
   S2  read by [3] and [7]
   S3  read by [4],  WRITTEN by [5]
   channel bases 0x40 (ch 0) and 0x54 (ch 1) = 5 bands x 4 words apart
```

> **INFERRED:** the two spaces are the chip's **C-RAM and D-RAM**, and a class-A word
> needs no space-selector bit because it reads **one operand from each** — the
> coefficient through the auto-incremented pointer (which is why class-A `addr8` never
> points at a coefficient) and the data word through the `addr8` cursor. This is a
> different answer from the one the open question expected: **nothing has to select**.
> Consistent with the CDJ-500 block diagram, where `MPLY` has two input latches (K and L)
> fed from separate paths.
> **NOT ESTABLISHED:** which of `S0..S3` is `x1/x2/y1/y2`, and hence the topology. The
> cell walk still refuses every textbook form — `[7]` (`−a2`-adjacent under the old
> reading, the make-up gain under the new one) reads `S2`, the same cell `[3]` read, and
> only two of the four cells are ever written. §9.

## 8. Corrections and cross-checks

| earlier claim | source | status here |
|---|---|---|
| `[1]=b1, [2]=b0, [3]=b2, [4]=−a1, [7]=−a2` (INFERRED from emission order, `[0]` skipped) | biquad-coeffs note §6 | **SUPERSEDED**: the coefficient cursor advances **6** per band (§2.2, matching `T1` in 8 images), and `NN+5` holds a measured constant (§3). The map is `[0]=b1 … [4]=−a2, [7]=make-up` |
| "the identity of the six coefficients is NOT ESTABLISHED" | biquad note §9 | **RESOLVED, all six**, and confirmed by inverting real ROM data (§4) |
| "six coefficients per band" (host stride 6) | biquad note §2 | **REINSTATED in substance**: five come from `op 0x70`, the sixth from the program loader. The coefficients note's "five, and the 6th is padding" is right about the *writer* and wrong about the *slot* — `0x05/0x0B/0x11/0x17/0x1D` are not padding, they are loaded with `0x800000` and read every sample |
| `GEQ`'s stride-5 `T1` group proves the block is 5 | biquad-coeffs note §5 | **weakened, not refuted**: `GEQ` (algo 79) is one of the five MALFORMED images, so its microcode cannot be inspected, and it uses `op 0x76` as well. Stride 5 there is consistent with a 5-class-A-word section |
| class-8 word = "a shift, a saturate, or a latch transfer" | biquad note §5, coeffs note §6 | **shifter NOT SUPPORTED** (§6.2); it is filter-section-specific (MCC +0.947) |
| "`ROCK ROTARY` has a class-8 word and no section" | biquad note §5/§9 | **RESOLVED**: it has one, at d = 3 (§6.3) |
| `[0]`'s `hi12` = the operand source, per instance | biquad note §1.2 (INFERRED, strong) | **REFINED**: per *stage*, not per band — constant across a 5-band chain (§5) |
| `801.0.00.021` = channel-1 coefficient rewind | biquad note §4 (INFERRED) | **CONFIRMED numerically**: with the rewind the class-A prefix reproduces `00 06 0C 12 18` for channel 1 too (§2.2) |
| signed `addr8` post-increment, +4 per band | biquad note §3 | **UPHELD**, and now separated cleanly from the coefficient cursor |
| `801.0.NN.821` = pointer load | parameters note §2 | **CONFIRMED a third time**: it is what sets the coefficient bank's load base (§2.3), `0x00` then `0x1E` |
| effect-name → `filt` labels | class2 note `IMG_CAT` | **scored for the first time**: class 8 vs `filt` is TP 15 / FP 0 / FN 1 |

## 9. Falsified, or explicitly not established

* **`[0]`'s `hi12` encodes chain position.** **FALSIFIED** (§5), 10/10 identical in algo 39.
* **Class 8 as a fixed-point shifter**, and specifically as the Q1.22 → Q0.23 correction.
  **NOT SUPPORTED** (§6.2); the scale change does not straddle it and `AUTO WAH` places
  it with no adjacent multiply.
* **The sixth coefficient as a user-controlled per-band trim.** **EXCLUDED** (§3): no
  parameter-path writer ever touches `NN+5`.
* **Why the PEQ's make-up constant is negative** (`−2.0`) while `OVERDRIVE`'s and
  `EXCITER`'s are positive.
* **The compressor images' +4 coefficient offset** (§2.2) — systematic in all three, and
  the instruction that consumes those four words is unidentified.
* **Which of `S0..S3` is which state variable, and the topology.** Unchanged from the
  biquad note: two stores, four cells, and no textbook form fits the read order
  `S0 S0 S1 S2 S3 | S3 | S2 | S1`.
* **`addr8 = 0x16` in class 8**, and what the class-8 operation is.
* **PEQ band 1's default numerator** (§4.1).
* **`ENHANCER`**, the single `filt`-labelled image with no class-8 word.
* **The second 9-word section family** (`80A.8.16.000`, `ROCK ROTARY` +
  `PEQ+COMPR+OVERDR`), and `AUTO WAH`'s (`804.8.16.1DA`). Both are filter sections of a
  different shape and neither is decoded.

## 10. Next experiments, in order of value

1. **Invert the `AUTO WAH` and `80A` section families the same way** — both have static
   coefficient banks and a measurable class-A prefix, so §2/§4's method applies unchanged
   and would give two more decoded section types for very little work.
2. **Find the compressor's four-word coefficient consumer** (§2.2). A +4 offset repeated
   in three images is a labelled arrow pointing at one instruction.
3. **Use the make-up-gain identity as an oracle**: for any newly found section, the 6th
   (or last) coefficient should be the reciprocal of the section's own gain. That is a
   cheap, sharp test for whether a candidate block boundary is right.
4. **`op 0x76` / `GEQ`** — still the cheapest independent check of the block size, and it
   would settle whether the 6th word is universal or PEQ-family-specific.
5. **The state cells.** With the coefficient cursor now measured and separated, the
   `addr8` cursor is the only unknown in the section; the `T1 op 70` second group
   (`64 68 6C 70 74`) is still unexplained and is the obvious lever.
