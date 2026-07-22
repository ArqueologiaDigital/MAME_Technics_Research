# NEC uPD6383GF — the second operand route, and whether the word is a product of axes

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_axes.py` (imports `kn5000_dsp_extract`, `_coeffs`, `_params`,
`_biquadmap`, `_chorus`; **none of them is edited**, and **no earlier note is edited** —
corrections are collected in §7).

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or **SPECULATIVE**.
§8 lists what is falsified, including **one of my own predictions, which missed**.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_axes.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
```
Sections: `phaser rotary axes predict coverage`. Runtime ≈ 2 s.

---

## Headline

1. **★★★ THE SECOND OPERAND ROUTE IS THE DATA POINTER, AND THE PHASER PROVES IT BY
   ARITHMETIC.** In each of the phaser's all-pass sections the three `addr8` deltas
   **sum to exactly zero** — `(0x45+k) + 1 − (0x46+k) = 0` — so the pointer is back
   where it started and **every section addresses the SAME operand cell**. This holds
   in **30 of 38** sections across three images, and the **8 exceptions are exactly the
   last section of each chain** (every one of them ends in the all-pass marker
   `104.2.00.000`, every one has a class-A middle word), where the pointer deliberately
   leaves the chain. So the twenty sections do not need twenty gains: they share one,
   fetched via `mem[ptr]` instead of via the coefficient cursor. **MEASURED**, and it
   uses no pointer origin, no class-skip rule and no host data (§2.2).
2. **★★★ R1 IS FALSIFIED, R2 IS CONFIRMED, AND THE HOST MAP AGREES.** The chorus note
   left two repairs open. **R1** (the ascending `0x45..0x4E` are twenty explicitly
   addressed coefficients) requires the host to write those addresses. It writes
   **none** of them, in any of the three phaser images — for algo 5 the host's whole
   universe is `00 02 05 06 08 09 0A 0C 13 14 1D 90`. And §2.2 shows those bytes are
   not addresses at all. **R2** — one shared gain — is what the arithmetic measures
   directly (§2.3).
3. **★★★ THE REVERB IS THE CONTROL, AND IT PASSES.** If the class-2 form exists
   *because* the gain is shared, an all-pass family whose gains genuinely differ per
   stage must use the class-A form. The reverb's nine diffusers each carry their **own**
   `102.A.00.64B`, and the pointer **never moves** inside a section (net delta 0 in 8 of
   9; the ninth is the ladder-to-ladder transition). **Same `hi12 = 0x102` in both
   families** — the phaser's `102.2.<k>.1CD` and the reverb's `102.A.00.64B`. This could
   have failed and did not (§2.5).
4. **★★ THE BRIEF'S DECOMPOSITION IS WRONG IN ITS ASSIGNMENT AND WRONG IN ITS
   INDEPENDENCE.** `hi12` is not subordinate: it is constant (`0x102`) across the two
   families that differ in *both* class and `lo12` while doing the same job. What varies
   with the operand source is **class + `lo12` together**. And the fields are not
   independent axes at all: against a non-circular observable, adding `class4` to
   `lo12` buys **+0.264 of class4's own 1.105 adjusted bits — 76 % redundant**; `hi12`
   plus `lo12` is 66 % redundant. A product space would be additive; every pair is
   strongly **negative**-synergy (§4.3).
5. **★★ MY OWN ROCK ROTARY PREDICTION MISSED, AND THE MISS IS THE RESULT.** I predicted
   its rate would arrive by the same pointer route, which requires op `0x69`'s addresses
   `0x0F`/`0x13` **not** to be cursor slots. They **are** cursor slots, consumed by
   `102.A.40.1D5` and `182.A.FF.1D4`. ROCK ROTARY has no missing-operand problem at all:
   what it lacks is the `092.A` **phase-accumulator idiom**, not an operand. **The two
   anomalies are different mechanisms**, and the brief's "if one explains both, that is
   strong" does not get to apply (§3).
6. **★ THE PAYOFF IS REAL BUT SMALL, AND IT IS NOT THE PRODUCT MODEL'S.** Coverage goes
   **9.0 % → 17.5 %** (267 → 520 of 2974 words), all of it from *measured idioms*, each
   scoped to the images where it was actually read. The product model's headline number
   — "47.0 % of the corpus has a `lo12` we know in some class" — **is not a decode**, and
   §5 says why in the tool's own output (§6).
7. **★ THE CEILING ON THE WHOLE METHOD IS MEASURED: only 18 of 58 `lo12` values (31 %)
   ever occur in more than one class.** A `lo12` confined to one class cannot support a
   cross-class prediction at all. Two of the six predictions I set up turned out
   **VACUOUS** for exactly this reason, and I report them as vacuous rather than as hits
   (§5).

---

## 1. What is used unchanged

From `-encoding.md`, `-semantics.md`, `-biquad-map.md`, `-cursor-general.md`,
`-class2-round2.md`, `-effect-map.md`, `-chorus.md`:

* the field map `hi12[35:24] . class4[23:20] . addr8[19:12] . lo12[11:0]`;
* the coefficient **cursor**, +1 per class-A word, reset by `801.0.00.021`;
* the **signed `addr8` post-increment** data pointer;
* `hi12 = 0x212` = write to `mem[ptr]`; `104.2.00.000` = all-pass marker;
* bit 23 = **cursor-fetch** enable (the chorus note's correction, §5.2 there);
* the host parameter machinery T1/T2, used **T2-confirmed only**;
* corpus = the **38 distinct images** of the 91 valid programs, 2974 words, malformed
  streams 79/88/89/90/91 excluded. The tool reproduces `-core-draft.md`'s baseline
  **267 decoded / 9.0 %** exactly, which is the check that the corpus is the same one.

Nothing above is re-derived.

## 2. THE PHASER, AND THE SECOND OPERAND ROUTE

### 2.1 The anomaly, restated precisely (**MEASURED**)

`PHASER` (algo 5) is 106 words and contains two chains of ten all-pass sections. Each
section is three words:

```
   102.2.45.1CD        102.2.46.1CD        ...   102.2.4E.1CD
   212.2.01.412        212.2.01.412              212.A.B0.412
   104.2.BA.1D5        104.2.B9.1D5              104.2.00.000
```

Eighteen of the twenty sections contain **zero class-A words**, so eighteen gains never
touch the coefficient cursor. The census over the corpus:

```
   algo   3 (unnamed)         8 all-pass sections,  4 containing a class-A word
   algo   5 PHASER           20 all-pass sections,  2 containing a class-A word
   algo  68 S.DELAY+PHASER   10 all-pass sections,  2 containing a class-A word
```

In every image the class-A word is the **chain-terminal** section, one per chain.

### 2.2 ★ THE NET-DELTA TEST (**MEASURED**)

**Prediction, stated before running it.** `addr8` is a signed post-increment on the data
pointer (MEASURED elsewhere). If the ascending `0x45, 0x46, …` were *addresses* they
would be arbitrary. If instead they are *increments that bounce the pointer from an
advancing delay cell to a fixed operand cell and back*, then the three deltas of each
section must **cancel exactly**. Nothing forces that; the sum could be anything.

```
   sections with net pointer delta == 0 : 30 / 38
   sections with net delta != 0         :  8

   algo   3 word  15  net  -3   middle word class A   third word 104.2.00.000
   algo   3 word  32  net  -3   middle word class A   third word 104.2.00.000
   algo   3 word  63  net  -3   middle word class A   third word 104.2.00.000
   algo   3 word  79  net  -3   middle word class A   third word 104.2.00.000
   algo   5 word  39  net  -2   middle word class A   third word 104.2.00.000
   algo   5 word  98  net  +9   middle word class A   third word 104.2.00.000
   algo  68 word  38  net  -2   middle word class A   third word 104.2.00.000
   algo  68 word  98  net  +9   middle word class A   third word 104.2.00.000

   every exception's third word is the all-pass marker 104.2.00.000 : True
   every exception's middle word is class A                         : True
```

The eight exceptions are **exactly the eight chain-terminal sections** already identified
in §2.1 by a completely different property (carrying the class-A word). Two independent
descriptions of the same eight words is not something a coincidence supplies.

Worked, for section `k` of chain 1: `(0x45+k) + 1 + (−(0x46+k)) = 0`. The `104.2.**.1D5`
word's `addr8` runs `BA B9 B8 B7 B6 B5 B4 B3 B2` = `−0x46 … −0x4E`, tracking the `102`
word's ascent exactly.

> **ASSIGNED (MEASURED): within an all-pass chain, every section's `102.2.<k>.1CD` word
> addresses ONE AND THE SAME data cell.** The `addr8` walk belongs to the *other* two
> words — the delay-line cells, which advance by one per section (chain 1 spans ten
> consecutive cells, chain 2 the ten after them). The gain is shared, not per-section.

This is the strongest statement in the note because it depends on **nothing**: no pointer
origin, no rule about which classes carry pointer deltas, no host data, no coefficient
decode. It is arithmetic on bytes that are in the ROM.

### 2.3 The host-map test: R1 is dead (**MEASURED**)

The chorus note's **R1** says the class-2 words multiply by a coefficient at an
explicitly addressed location, i.e. `0x45..0x58` are twenty coefficient addresses. The
brief's own external constraint applies: the gains must come from somewhere the host
wrote.

```
   algo   3   chain addr8 : 3E 3F 42 43 48 49 4C 4D
              every address the host T1 even MENTIONS : 00 04 06 08 09 0A 0B 0C 0D 11 12 15 16 1D 90
              chain addr8 values the host ever writes : NONE
   algo   5   chain addr8 : 45 46 47 48 49 4A 4B 4C 4D 4E 4F 50 51 52 53 54 55 56 57 58
              every address the host T1 even MENTIONS : 00 02 05 06 08 09 0A 0C 13 14 1D 90
              chain addr8 values the host ever writes : NONE
   algo  68   chain addr8 : 45 46 47 48 49 4A 4B 4C 4D 4E
              every address the host T1 even MENTIONS : 00 02 03 05 06 07 09 0A 0C 0D 0E 10 11 13 14 15 1D 26 29 90
              chain addr8 values the host ever writes : NONE
```

Note this is the **permissive** form of the test — it uses every address T1 so much as
mentions, including the unreferenced operand slots that the chorus note §6 warns
over-count. Even given that generosity, not one chain byte is a host-written address.

> **R1 FALSIFIED. R2 CONFIRMED** — and confirmed by measurement (§2.2), not merely left
> standing. This closes `-chorus.md` §9 item 3.

### 2.4 What fills the shared cell (**INFERRED**)

Immediately outside each chain sits a block of a shape the chorus note already decoded
piecewise: the table-lookup triplet (LFO waveform), then a depth word `000.A.**.415`,
then a **write** word `212.A.**.1D5` (`hi12 = 0x212` = write to `mem[ptr]`, MEASURED).
Its cursor coefficient:

```
   algo   3 word  38  212.A.FF.1D5   400000 = +0.500000
   algo   3 word  84  212.A.FF.1D5   400000 = +0.500000
   algo   5 word  52  212.A.04.1D5   381062 = +0.438000
   algo   5 word  62  212.A.F5.1D5   381062 = +0.438000
   algo  68 word  53  212.A.08.1D5   381062 = +0.438000
   algo  68 word  63  212.A.F9.1D5   381062 = +0.438000
```

`0x381062 = +0.438000` recurs as the centre value in **both** phaser images, with the
depth word beside it (`0x033333 = 0.025` in algo 5, `0x066666 = 0.05` in algo 68). A
first-order all-pass coefficient of 0.438 swept by ±0.025 is a textbook phaser sweep, and
0.438 is a round number in decimal — a value a designer typed, not one that fell out of
arithmetic.

**MEASURED**: the constants, their positions and their recurrence. **INFERRED**: that the
cell this block writes is the cell the chain reads. **NOT ESTABLISHED**: the pointer's
absolute origin, and therefore the identity of that cell as a number. I traced the
pointer cumulatively and it is *consistent* with the chain cell being the one the
`212.A.**.1D5` block targets, but the trace requires deciding which classes carry pointer
deltas (class-6 `addr8` is a **table selector**, class-1 `addr8` is a DRAM-bracket or unit
code — neither is an increment), and a decode that depends on my choice of what to skip is
not a decode. **I am not claiming the cell's address.**

### 2.5 ★ THE CONTROL: the reverb's ladders (**MEASURED**)

**Prediction, stated before looking.** If the class-2 form exists *because* the gain is
shared and modulated, then an all-pass family whose gains genuinely differ per stage must
use the class-A form — and, having nothing to bounce to, must not move the pointer at all.
The reverb (algo 16, the only unit-1 program, `-reverb.md`: two ladders of five diffusers)
is that family.

```
   algo 16: 9 all-pass markers at [20, 28, 36, 44, 52, 70, 78, 86, 94]
       distinct 8-word section images : 2
       class-A words per section      : [1, 1, 1, 1, 1, 1, 1, 1, 1]
       net pointer delta per section  : [0, 0, 0, 0, 0, -70, 0, 0, 0]

       880.1.60.2D4 | 104.2.00.000 | 000.2.00.419 | 012.2.00.680
       880.1.20.655 | 102.A.00.64B | 000.2.00.000 | 000.2.00.000
```

Every diffuser carries its own `102.A.00.64B`; the pointer is stationary in eight of nine
sections, the ninth (`−70`) being the transition between the two ladders. **The control
passes.**

And it delivers the note's sharpest structural fact:

> **`hi12 = 0x102` is the all-pass gain multiply in BOTH families.** The phaser uses
> `102.2.<k>.1CD`; the reverb uses `102.A.00.64B`. Same operation, same `hi12`, and the
> operand source differs — carried by **class *and* `lo12` together**, not by `lo12`
> alone and not by class alone.

> **ASSIGNED (INFERRED, strong): `102.A.00.64B` = all-pass gain from the cursor;
> `102.2.<k>.1CD` = all-pass gain from `mem[ptr]`.** The second operand route is the
> **data pointer**, and bit 23 selects between them — which is precisely the chorus
> note's "cursor-fetch enable", now with a mechanism attached and a control behind it.

## 3. ROCK ROTARY — THE PREDICTION, AND THE MISS

### 3.1 The prediction, stated before the check

If ROCK ROTARY's missing `092.A` is the same phenomenon as the phaser's missing class-A,
then its rate must arrive on a class-2 word by the pointer route — and therefore the
addresses host op `0x69` writes (`0x0F`, `0x13`) must **not** be coefficient-cursor slots.
A value that travels the pointer route is precisely one the cursor never fetches.

That is falsifiable, and I wrote down the failure mode too: if `0x0F`/`0x13` *are* cursor
slots, ROCK ROTARY has no missing-operand problem and the two anomalies are unrelated.

### 3.2 The check (**MEASURED**)

```
   algo 15 ROCK ROTARY  /  algo 53 ROTARY SPEAKER   (identical images)
       092.A words = 0
       host op 0x69 writes 0F 13
           addr 0F IS a cursor slot -> word 47  102.A.40.1D5   coef 7FFE3B
           addr 13 IS a cursor slot -> word 54  182.A.FF.1D4   coef 7FFFA5
       host op 0x66 writes 10 14
           addr 10 IS a cursor slot -> word 49  302.A.00.655   coef 28F5C2 = 0.320
           addr 14 IS a cursor slot -> word 55  282.A.01.692   coef 35C28F = 0.420
       host op 0x65 (LFO SPEED): NOT DECLARED
```

### 3.3 Verdict — **PREDICTION MISSED**

Both of op `0x69`'s addresses are ordinary cursor slots, consumed by ordinary class-A
words. **ROCK ROTARY's rate travels the normal cursor route. Nothing is missing.**

What is absent is the `092.A` **phase-accumulator idiom**, and the reason is visible in
the coefficients: `0x7FFE3B = +0.99994` and `0x7FFFA5 = +0.999995` are not rates, they are
values just under one — the shape of a rotation/recursive-oscillator coefficient, which is
consistent with op `0x69` being `eval_0392AC`, the degree scaler. ROCK ROTARY appears to
use a **different oscillator algorithm**, not a different operand route. (**SPECULATIVE**:
I did not close the oscillator. Reading `0.99994` as `cos ω` gives ≈ 77 Hz, which is far
too fast for a rotor, so the naive resonator reading does **not** fit and I am not
asserting it. `-chorus.md` §9 item 2 stays open.)

> **One mechanism does NOT explain both.** The brief offered this as the strong case; it
> is not available. Two unrelated effects, two genuinely different causes.

## 4. THE DECOMPOSITION, TESTED

### 4.1 The model, stated falsifiably first

> **M1** `lo12` partitions the corpus into ROUTES: words sharing a `lo12` behave alike in
> position, neighbours and effect-family membership **regardless of class**.
> **M2** `class4` partitions into ARITHMETIC **independently of** `lo12`.
> **M3** bit 23 = cursor fetch.
> **M4 (the consequence that matters)** the 655 undecoded words collapse into a small
> PRODUCT SPACE of (route × operation), so most of the tail is implied by pieces held.

M1 and M2 together predict a specific, measurable signature: the two fields must carry
**different** information about anything outside the word, so knowing both must be worth
roughly the **sum** of knowing each.

### 4.2 Field-versus-field independence (**MEASURED**)

```
   pair                    MI    H(X)    H(Y)     NMI       (2974 words, 38 images)
   hi12 x class4        1.166   3.979   1.880   0.620
   hi12 x addr8         1.416   3.979   4.220   0.356
   hi12 x lo12          1.964   3.979   4.340   0.494
   class4 x addr8       0.930   1.880   4.220   0.495
   class4 x lo12        1.173   1.880   4.340   0.624
   addr8 x lo12         1.608   4.220   4.340   0.381
```

NMI is normalised by `min(H)`, so `class4 × lo12 = 0.624` reads: **62 % of everything the
class nibble says is already said by `lo12`.** M2's independence claim is in trouble
immediately.

### 4.3 ★ Partition quality against NON-CIRCULAR observables (**MEASURED**)

**The trap, and how it is avoided.** Nearly every structural label the project holds —
all-pass marker, DRAM bracket, terminator, NOP, LFO read, P-consumer, table triplet — is
*defined* by `hi12`/`class4`/`lo12`. Scoring "group by `lo12`" against a label defined by
`lo12` is circular and would confirm any model whatsoever. **This is the instrument
blindness that would have wrecked this section**, so the observables below use only
information from outside the word itself:

* **NEIGH** = (`hi12` of the previous word, `hi12` of the next word)
* **IMAGE** = which of the 38 images the occurrence is in
* **POS** = position in the program, in tenths

Each grouping is also run with its labels **shuffled**, which measures how much score you
get for free from merely having many groups. Only `lift = NMI − null` means anything.

```
   grouping           |G|          NEIGH                 IMAGE                  POS
                            NMI   null   lift     NMI   null   lift     NMI   null   lift
   lo12                57  0.756  0.241 +0.515   0.157  0.087 +0.069   0.092  0.034 +0.058
   class4               9  0.737  0.150 +0.587   0.077  0.036 +0.041   0.040  0.009 +0.031
   (lo12,class4)       84  0.766  0.270 +0.496   0.187  0.109 +0.078   0.135  0.050 +0.085
   hi12                54  0.762  0.236 +0.527   0.152  0.090 +0.062   0.079  0.036 +0.043
   (hi12,class4)       77  0.765  0.259 +0.505   0.176  0.104 +0.072   0.104  0.049 +0.055
   (hi12,lo12)        175  0.777  0.328 +0.448   0.307  0.197 +0.110   0.209  0.103 +0.105
   full word          688  0.870  0.518 +0.352   0.516  0.419 +0.097   0.424  0.315 +0.109
```

Read the NEIGH column. `class4`, with **nine** groups, gets a **higher lift than `lo12`
with fifty-seven**. And `(lo12, class4)` — the product — gets a lift **lower than either
part alone**. That is not what a product space looks like. It is what redundancy looks
like.

### 4.4 ★ THE DECISIVE TEST: is the information additive? (**MEASURED**)

Raw MI in bits against NEIGH, permutation-corrected (20 shuffles per grouping):

```
   adj MI (bits)   lo12  2.236    class4  1.105    hi12  2.088
                   (lo12,class4)  2.499    (hi12,lo12)  2.847    (hi12,class4)  2.369

   lo12  + class4 :  synergy -0.841 bits   class4 adds +0.264 of its own 1.105  -> 76 % REDUNDANT
   hi12  + lo12   :  synergy -1.476 bits   lo12   adds +0.759 of its own 2.236  -> 66 % REDUNDANT
   hi12  + class4 :  synergy -0.824 bits   class4 adds +0.280 of its own 1.105  -> 75 % REDUNDANT
```

An additive product space gives synergy ≈ 0. **Every pair is strongly negative.**

> **VERDICT (MEASURED): M2 is FALSIFIED and M4 does not follow.** Over this corpus the
> fields are not independent axes; three quarters of what the class nibble contributes is
> already contributed by `lo12`, and vice versa. The 655-word tail does **not** collapse
> into a small product space.

**The honest caveat, because it cuts the other way.** Redundancy *in the corpus* is not
the same as non-orthogonality *in the encoding*. Real ISAs show exactly this pattern when
usage is idiomatic: certain routes are only ever used with certain arithmetic, so the
fields correlate even though the hardware decodes them separately. This measurement
therefore falsifies the **inference** M4 (that holding one axis implies the tail) without
proving the **encoding** is not fielded. That distinction matters and I am not blurring
it — but M4 was the whole reason to run the test, and M4 is what fails.

That reading is also *corroborated* by `-necfamily.md` §6: the effect bodies are proven
**hand-unrolled** idiom sequences. A corpus of hand-written idioms is exactly a corpus in
which fields co-vary.

## 5. THE PREDICTIONS — HITS AND MISSES

★ The brief's real test: take a `lo12` known in one class, predict what it does in a class
where it is undecoded, check against position and context.

| # | `lo12` | known in | prediction | outcome |
|---|---|---|---|---|
| 1 | `0x407` | A (`212.A.dd.407` = `mulst`, DETERMINED UNIQUELY) | `000.2.**.407` is the same route minus write minus fetch | **UNRESOLVED.** 263 occurrences in **15** `(hi12,class)` forms spread over **4 classes** and 36 images. A `lo12` this promiscuous constrains nothing; the prediction is not checkable against position because the positions are everywhere. |
| 2 | `0x1D5` | A (`202.A.dd.1D5` = `mac`) | `000.2` / `104.2` forms are MAC-shaped with a non-cursor multiplicand | **CONSISTENT, NOT CONFIRMED.** 433 occurrences, 27 forms. Consistency here is cheap — `0x1D5` is the corpus's most common `lo12` and would look consistent with almost any reading. |
| 3 | `0x44C` | 3 (modulation offset, keeping the fraction) | other classes carrying `0x44C` also apply a modulation offset | **HIT, and the cleanest one.** Only **2** forms exist: `C40.3.**.44C` ×29 (10 images) and `000.2.**.44C` ×12 (4 images), and the chorus note independently showed the class-2 form is the non-interpolated tap. A narrow `lo12` gives a real prediction. |
| 4 | `0x200` | A (LFO phase accumulate / wrap) | class-2 `0x200` words touch the LFO phase | **VACUOUS.** All 66 occurrences are class A (`092.A` ×29, `094.A` ×29, `09A.A` ×8). No cross-class instance exists. Reported as vacuous, **not** counted as a hit. |
| 5 | `0x412` | 2 (this note: the all-pass section write) | `212.A.**.412` is the same write plus a cursor fetch | **HIT, weakly.** 79 occurrences, 4 forms, classes {2:30, A:49}; the class-A form is the chain terminal in all three phaser images (§2.1), which is exactly "the same write plus a fetch". Weak because I decoded the class-2 form myself in §2. |
| 6 | `0x821` | 0 (`ldptr`, PROVEN BY CONSTRUCTION) | no other class carries `0x821` — a pointer load has no arithmetic variant | **VACUOUS in the body corpus.** `0x821` occurs **zero** times in the 38 images: pointer loads live in the header/poke stream, not in effect bodies. The prediction is true but empty here. |

**Score: 2 usable hits (#3, #5), 2 vacuous (#4, #6), 2 unresolved (#1, #2), 0 clean
misses.** The pattern is the point: **the predictions that work are the ones where the
`lo12` is rare and narrow, and those are exactly the ones that were already nearly
decoded.** The promiscuous `lo12` values — which is where the 655-word tail actually lives
— give nothing.

### 5.1 The measured ceiling on the method

```
   distinct lo12 values in the corpus            : 58
   lo12 values occurring in MORE THAN ONE class  : 18   (31.0 %)
   occurrences covered by multi-class lo12       : 2132 / 2974  (71.7 %)
```

**69 % of `lo12` values cannot support a cross-class prediction at all**, because they
never appear in a second class. That is a hard ceiling, and it is measured rather than
argued.

## 6. COVERAGE, HONESTLY

Recomputed exactly the `-core-draft.md` way — the six MAME forms over the 38 distinct
images — which reproduces its baseline to the word, confirming the corpus is the same:

```
   words over the 38 distinct images : 2974
   decoded by the six MAME forms     :  267   (9.0 %)      <- -core-draft.md baseline

   added by the chorus note and this note, each SCOPED to the images where it was read:
       103   212.2.**.000  plain store                    (chorus note 5.3, 32 images)
        58   092/094.A.**.200  LFO phase                  (chorus note 2.2, 20 images)
        38   102.2.**.1CD  all-pass gain via mem[ptr]     (this note, 3 images)
        38   212.*.**.412  all-pass section write         (this note, 3 images)
        16   102.A.00.64B  reverb diffuser gain, cursor   (this note, 1 image)
       253   TOTAL

   decoded, revised                  :  520   (17.5 %)
```

The scoping is deliberate. `212.*.**.412` occurs 79 times across 18 images; I read the
chain in **three**, so I count **38**. `102.2.**.1CD` occurs 43 times; 38 are in the
phaser images. Counting the other occurrences would have produced 18.3 % and would have
been an over-claim of exactly the kind this project keeps having to retract.

### 6.1 The number the model would like me to quote, and why I will not

```
   undecoded words whose lo12 is one we claim to KNOW in some class:
       1398 occurrences, 91 distinct (hi12,class,lo12) forms  =  47.0 % of the corpus
```

**That is not a decode and it must not be reported as one.** Knowing a word's `lo12` tells
you (at best) the operand route; its `hi12` — which §2.5 shows is where the *operation*
lives — and its class are still unknown. And §5 shows the cross-class inference the figure
silently assumes is unavailable for 69 % of `lo12` values. A model that "explains" 47 % and
predicts two narrow families is worth the two families.

**9.0 % → 17.5 %. That is the number.**

## 7. Corrections and additions to earlier notes

| earlier claim | source | status here |
|---|---|---|
| R1 vs R2 for the phaser's coefficient source — open | `-chorus.md` §5.2, §8, §9 item 3 | **CLOSED. R1 FALSIFIED** (host writes none of `0x45..0x58`, and §2.2 shows they are not addresses), **R2 CONFIRMED by the net-delta arithmetic** |
| "what `102.2.<c>.1CD`'s `addr8` addresses" — NOT ESTABLISHED | `-chorus.md` §8 | **ANSWERED: it addresses nothing.** It is an increment that cancels within the section |
| bit 23 = cursor-fetch enable (correcting "multiply-enable") | `-chorus.md` §5.2, §7 | **UPHELD and given a MECHANISM**: the non-fetching route is `mem[ptr]`, with the reverb as a passing control (§2.5) |
| `104.2.00.000` all-pass marker — "its *position* differs between reverb and phaser, so the step it performs is unidentified" | `-INDEX.md` backlog 3 | **PARTLY EXPLAINED**: in the phaser it is the chain-terminal section's third word (8/8 exceptions in §2.2); in the reverb it is section-internal with a stationary pointer. The two positions correspond to the two operand routes |
| "`lo12` carries the route while the class carries the arithmetic" — first positive support | `-chorus.md` §3.2, `-core-draft.md` §6 item 2 | **DOWNGRADED.** The `0x44C` evidence stands (§5 #3), but as a *general* decomposition it is **falsified by additivity** (§4.4): 76 % redundancy, negative synergy. The route is not in `lo12` alone — `hi12 = 0x102` is constant across the two families that differ in both class and `lo12` |
| ROCK ROTARY's rate mechanism — NOT ESTABLISHED | `-chorus.md` §8, §9 item 2 | **NARROWED, not closed**: op `0x69`'s slots are ordinary cursor slots, so it is **not** a second operand route. Still open: what oscillator consumes `0.99994` / `0.999995` |
| coverage 9.0 % | `-core-draft.md` §4 | **REPRODUCED EXACTLY** (267/2974), then revised to **17.5 %** by scoped idiom decodes |
| ROCK ROTARY and ROTARY SPEAKER are the same effect listed twice | `-chorus.md` §4.2 | **RE-CONFIRMED** incidentally: identical T1 maps, identical cursor slots, identical words (§3.2) |

## 8. Falsified, or explicitly not established

* **M2 — `class4` partitions independently of `lo12`** — **FALSIFIED** (§4.2, §4.4).
* **M4 — the 655-word tail collapses into a small product space** — **FALSIFIED as an
  inference** (§4.4, §5.1). The long tail is, on this evidence, **genuine**.
* **R1 — per-section explicitly addressed all-pass coefficients** — **FALSIFIED** (§2.3).
* **My own prediction that ROCK ROTARY shares the phaser's mechanism** — **MISSED**
  (§3.3). Two different mechanisms.
* **`lo12` alone names the route** — **FALSIFIED** by the `102.A.00.64B` / `102.2.**.1CD`
  pair, which share `hi12` and differ in `lo12` while doing the same job (§2.5).
* **NOT ESTABLISHED — the shared gain cell's ADDRESS.** §2.2 proves the cell is shared;
  naming it needs the pointer origin, which needs a rule for which classes carry pointer
  deltas, which I do not have (§2.4).
* **NOT ESTABLISHED — that the `212.A.**.1D5` block writes that cell.** Positionally and
  numerically apt (0.438 ± 0.025), but INFERRED (§2.4).
* **NOT ESTABLISHED — ROCK ROTARY's oscillator.** The resonator reading gives ≈ 77 Hz
  against a rotor's ≈ 1–7 Hz and is therefore NOT asserted (§3.3).
* **NOT ESTABLISHED — that the encoding is not fielded.** §4.4 falsifies the inference,
  not the hardware; a fielded decoder with idiomatic usage produces the same statistics
  (§4.4 caveat).
* **Nothing here was executed.** The core is still disabled; everything is static.

## 9. What this instrument is blind to

1. **Circularity was the live danger and it is designed out, not argued away.** Every
   structural label the project holds is defined by the word's own fields; §4.3 therefore
   uses only neighbour `hi12`, image identity and position, and subtracts a permutation
   null. Had I scored `lo12` against "is it the all-pass marker", the model would have
   "passed" gloriously and meant nothing.
2. **The neighbour observable is not innocent either.** `NEIGH` is built from neighbouring
   `hi12`, so the `hi12` row of §4.3 is mildly self-flattering (a word's own `hi12`
   correlates with its neighbours' through idiom repetition). The `lo12` and `class4`
   rows, which carry the verdict, are not affected.
3. **The pointer trace is assumption-laden and is therefore NOT used for any claim.**
   Class-6 `addr8` is a table selector and class-1 `addr8` is a bracket/unit code; a naive
   cumulative sum over all words puts the phaser's pointer at cell 132 and a corrected one
   at cell 11. The load-bearing result (§2.2) is a *difference*, immune to all of this.
4. **The all-pass matcher is an exact 2-word pattern with wildcards** (`102.2.*.1CD` +
   `212.*.*.412`). It finds 38 sections in 3 images. If a phaser variant spells its
   sections differently, this misses it entirely — the same failure mode as the earlier
   byte-identical search that found 8 of 27 sections. The reverb's ladders, which use a
   completely different 8-word idiom, are proof that the shape is not universal.
5. **Six predictions is a small sample**, and I chose them. I chose two that turned out
   vacuous and two that turned out unresolvable, which is at least not a curated set.
6. **Op `0x69`'s eval routine was not disassembled**, only its T1/T2 targets read.

## 10. What would close the remaining gaps, ranked

1. **Pin the data pointer's origin.** One rule — which classes advance the pointer — turns
   every `addr8` in the corpus from a delta into an address, names the phaser's shared
   gain cell, and would let the host map be cross-checked against *every* program at once.
   This is now the single highest-value structural unknown, and §2.2's cancellation is a
   ready-made consistency test for any candidate rule.
2. **Decode `hi12`, not `lo12`.** §2.5 shows the operation lives there (`0x102` = all-pass
   gain multiply, across two families with nothing else in common). The project has been
   mining `lo12`; the evidence says the other end of the word is where the meaning is.
3. **Disassemble `eval_0392AC` (op `0x69`)** and close ROCK ROTARY's oscillator — small,
   localised, and the only thing this note opened and did not close.
4. **The datasheet** (`-INDEX.md` backlog 6). §4.4's honest caveat — corpus redundancy
   does not prove the encoding is unfielded — is exactly the ambiguity a datasheet
   removes in one line, and no amount of further statistics will.
