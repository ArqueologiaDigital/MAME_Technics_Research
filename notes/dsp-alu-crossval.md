# The ALU field — cross-validated from the all-pass, the LFO and the input stage

**NEC uPD6383GF-3BA** (Technics SX-KN5000, IC311). Brief: *"now decode the ALU
field"*, i.e. `lo12` = bits[11:0] of the 36-bit word. Date 2026-07-26.

No hardware. Everything is static analysis of the ROM corpus plus the three
constraint systems named in the brief. Every claim carries a label:
**MEASURED** (counted over the ROM), **PROVEN BY CONSTRUCTION** (read out of the
bytes that build it), **FORCED** (the only assignment a stated rule admits),
**CONSISTENT**, **INFERRED**, **EDUCATED GUESS**, **OPEN**. Where a constraint
system admits several assignments they are **enumerated**, never silently picked.

**Scope / concurrency.** Per the brief, `kn5000-roms-disasm/dsp/instruction-set.md`,
`dsp/tools/dsp_disasm.py` and `dsp/analysis/*` were **read but not edited**. §9
lists what should be synced there. The scripts are committed alongside this note in
`kn7000_mame/tools/dsp_alu_crossval/` (stdlib only, re-runnable) and every number
below is printed by one of them.

---

## 0. The result in one page

The brief's framing — *"the arithmetic is the `lo12` field; decode it and the chip
can compute"* — **is wrong in a way that matters, and the evidence is three
independent minimal pairs.** `lo12` does **not** determine the operation. It is a
second horizontal microword, structurally just like `hi12`, and it carries the
**operand routing**; the operation select lives (at least partly) in `hi12`.

| # | statement | status |
|---|---|---|
| **A1** | `lo12` is a **horizontal microword**, not an enumerated opcode. Re-running the exact test that established this for `hi12`: 82 distinct values, **56 Hamming-distance-1 pairs** against a popcount-matched null of 15.1 ± 3.6 ⇒ **z = +11.3**. The same test on `hi12` over the same corpus gives z = +8.9. `lo12` is *more* microword-like than `hi12`. | **MEASURED** |
| **A2** | The field boundary is at **bit 5**. Over all nine contiguous splits, `lo12[4:0] ∥ lo12[11:5]` has the **lowest mutual information between the halves** (1.540 bits, vs 2.105 at bit 4 and 1.976 at bit 7). | **MEASURED** |
| **A3** | `lo12[8:6]` is a clean 3-bit sub-field: its six observed values partition the 82 `lo12` values into six non-overlapping families (the whole `0x1Cx/0x1Dx` group is `f3=7`; the whole DRAM group `2C7/2D4/2D5/2D9/2DA` is `f3=3`; …). This is the high-MI triple in the bit-pair MI matrix (0.31–0.38 between all three pairs, against ≤0.21 everywhere else). | **MEASURED** |
| **A4** | `lo12` bits **11 and 5 co-occur** (10 of 11 values) and mark the pointer-load / control family `{820,821,822,825,827,839,864,8BC,921,C63}` (+`021` = `rstcur`, bit 5 only). They are not datapath bits. | **MEASURED** |
| **B1** | **`lo12` cannot be the operation.** `092.A.dd.200` and `094.A.dd.200` are identical in `class4`, `addr8` and `lo12`, differ only in `hi12[3:1]`, address the same D-RAM cell, and consume C-RAM[+0] = `0x000072` (0.6 Hz) and C-RAM[+1] = `0x7FFFFF`. **No single binary operation applied twice with those two constants produces a 0.6 Hz ramp** (enumerated: `+ − × min max and or`) ⇒ the two words compute different things. | **FORCED** |
| **B2** | Second witness: `102.A.**.64B` is a **class-A multiply** and `880.1.20.64B` is an **external-DRAM WRITE** (R1-FORCED). Same `lo12`, 16 and 28 sites. | **MEASURED** |
| **B3** | Third witness: `lo12 = 0x407` is `mulst` on `212.A.dd.407` (**DETERMINED**) and is also the frame terminator `C00.A.47.407`, a wait/sync word that encodes its own I-RAM address in bits[24:17] (**MEASURED**). 265 sites, 17 distinct `(hi12,class4)`. | **MEASURED** |
| **C1** | **New sub-field localisation.** R1's exceptionless 44/44-vs-0/56 DRAM-write-source split is **exactly a split on `lo12[11:5]`**: `0x32` on both positives, `{0x16, 0x20}` on all negatives. Two minimal pairs cross the split *with `lo12[4:0]` held fixed* — `0x655`(32,15) 16/16 vs `0x2D5`(16,15) 0/3; `0x64B`(32,0B) 28/28 vs `0x40B`(20,0B) 0/7. ⇒ the write-data source is selected by the **upper** half, and the lower half says nothing about it. | **MEASURED** |
| **C2** | **The reverb's ladder separator is not reverb-specific.** The 5-word shape `[DRAM READ] │ *.A.*.655/695 │ filler │ 212.2.00.419 │ 880.1.20.64B` occurs at **28 sites in 15 images** including `NO OPERATION`, `SINGLE DELAY` and the whole S.DELAY family. It is the machine's generic **single-tap delay with feedback**. R1 §8 analysed it as a reverb "drain"; it is a general idiom. | **MEASURED** |
| **C3** | `*.A.*.655` sits at distance **exactly 1** after a DRAM read in 23 of 25 sites ⇒ its multiplicand is the delay-line read data. A `lo12` role R1 did not have. | **MEASURED** |
| **D1** | **The acceptance test in the brief cannot be run as stated.** Every sample passes through the input stage's 3-coefficient recursive section and the 30-word mix block before any body sees it, and those coefficients are values this project has never captured. §7 gives a **ratio test** that cancels them exactly. | **FORCED** |
| **D2** | `NO OPERATION` (algo 0) is **not** a pass-through: 49 words, two complete delay-tap idioms with DRAM read *and* write, 8 coefficient multiplies. | **MEASURED** |

**What this does to the roadmap.** "Decode `lo12`" is not one task, it is two: decode
`lo12` (routing) *and* decode `hi12[3:1]` (operation). Implementing a `lo12`-only ALU
would produce a core that is confidently wrong — the LFO would accumulate its wrap
constant, and the reverb write would take its data from the wrong register.

---

## 1. Corpus hygiene — two malformed images, and a number the brief inherited

Before any statistic: my first parse produced **40** distinct images / 3237 words /
**167** distinct `lo12`, against the brief's "2788 words, 80 distinct `lo12`, 121
`(class4,lo12)` pairs". The discrepancy is real and it is my parse that was wrong.

`kn5000_dsp_extract.parse_stream` returns two images that are **misaligned parses,
not microprograms**: algo **79** (`GEQ`, 48 words, **22** of them with non-zero
bits 36..39) and algo **88** (`ROOM`, 132 words, **78** bad). "Bits 36..39 are always
zero" is MEASURED across the whole corpus, so any image violating it is not a
program. They are exactly the two images the generated `dsp/disasm/` tree already
omits. **MEASURED.**

Dropping them gives the canonical corpus, which I verified **word-for-word identical**
to the generated tree on all 38 shared images:

```
   kernel (I-RAM 0..59)      60 words
   epilogue (I-RAM 60..82)   23 words
   38 distinct body images 2974 words
   ----------------------------------
   total                   3057 words   82 distinct lo12   123 (class4,lo12) pairs
```

Independent confirmation that this is the right population: my store-precedence base
rate comes out **703/3017 = 23.3 %**, which is bit-for-bit the corrected figure in
`instruction-set.md` ("over the canonical 40 blobs"). All numbers below are on this
corpus. The brief's 80/121 are this corpus's 82/123 (its 2788 word count is a
slightly different filter and is the only figure that does not reconcile).

**By-product worth acting on:** the algo-79 stream is named **`GEQ`** — a graphic
equaliser, i.e. a *fourth* EQ-family program directly relevant to the biquad
constraint system, and it currently has no `.dsm`. Its stream needs a different
record walk, not a different disassembler.

---

## 2. What `lo12` actually is — the measured field map

```
  11    10     9     8   7   6    5     4   3   2   1   0
+-----+-----+-----+------------+-----+--------------------+
| CTL |  ?  |  ?  |     f3     | CTL |       low5         |
+-----+-----+-----+------------+-----+--------------------+
```

* **bit 11 + bit 5 — CTL.** Set together on 10 of 11 values, all of them the
  pointer-load / control family (`820 821 822 825 827 839 864 8BC 921 C63`), plus
  `021` (`rstcur`) with bit 5 only. 95 and 96 words. **MEASURED.**
* **`f3` = bits[8:6].** Six values, and they partition the value space cleanly:

  | f3 | n | the `lo12` values |
  |---|---|---|
  | 0 | 1433 | `000 007 00B 021 200 207 20C 20D 216 219 21A 402 404 407 40B 40E 412 413 415 417 419 41A 41D 820` |
  | 1 | 344 | `041 05B 445 446 447 448 44C 44D 451 452 455 647 64B 64D 655 864 C63` |
  | 2 | 102 | `087 287 680 687 688 68B 692 695 8BC` |
  | 3 | 196 | `0C7 2C7 2D4 2D5 2D9 2DA 4C8 4CD 6CE 6D5` |
  | 4 | 48 | `107 700 921` |
  | 7 | 931 | `1C0 1C1 1C3 1C8 1CD 1CE 1D1 1D3 1D4 1D5 1DA` |

  `f3 = 7` is the entire `mac`/`mac.lb` family; `f3 = 3` is the entire external-DRAM
  family plus the table-lookup pair `4C8/4CD`. **MEASURED.** Meaning **OPEN**.
* **bits 10 and 9** are ordinary flags (1220 and 455 words).
* **`low5` = bits[4:0]** — the least-coupled half (A2). 25 of 32 values used. The
  same `low5` recurs across many upper halves: `low5 = 0x15` appears with uppers
  `{0E,16,20,22,32,34,36}`, `low5 = 0x07` with 17 different uppers. That reuse is
  what makes the split visible at all.

**How the six decoded forms sit in this map** (`lo12 = UPPER:low5`):

| form | `lo12` | UPPER | low5 | f3 |
|---|---|---|---|---|
| `mac` `202.A.dd.1D5` | 1D5 | 0E | 15 | 7 |
| `mac.lb` `202.A.dd.1D4` | 1D4 | 0E | 14 | 7 |
| `mulst` `212.A.dd.407` | 407 | 20 | 07 | 0 |
| R1 ladder multiply `102.A.**.64B` | 64B | 32 | 0B | 1 |
| DRAM READ `880.1.60.2D4` | 2D4 | 16 | 14 | 3 |
| DRAM WRITE `880.1.20.655` | 655 | 32 | 15 | 1 |

`mac` and `mac.lb` differ only in `low5` (15 vs 14) and differ only in "latch B ←
mem[p]". `mac` and the DRAM WRITE share `low5 = 0x15` across different uppers.
**CONSISTENT with UPPER = operand source, low5 = a secondary route/latch select;
INFERRED, not proven** — §6 lists what breaks it.

---

## 3. CONTEXT 1 — the all-pass motif

R1 (`dsp/analysis/r1-allpass-motif.md`) forced the structure. What it forces about
`lo12`, restated as routing, plus what this pass adds.

### 3.1 The `lo12` readings the motif implies

```
   slot0  880.1.60.2D4   hi12{ESC,b7}       f31=0
   slot1  104.2.00.000   hi12{f98=1}        f31=2
   slot2  000.2.00.419   hi12{}             f31=0
   slot3  012.2.00.680   hi12{ST}           f31=1
   slot4  880.1.20.655   hi12{ESC,b7}       f31=0
   slot5  102.A.00.64B   hi12{f98=1}        f31=1
```

| `lo12` | UPPER:low5 | what the context forces | status |
|---|---|---|---|
| `2D4` | 16:14 | start an external delay-DRAM **READ**; data visible **2..5** words later | **FORCED** (R1 F1, F6) |
| `655` | 32:15 | external delay-DRAM **WRITE**; data = whatever the immediately preceding `hi12` bit-4 store put in `mem[ptr]` (16/16) | **FORCED** (F1) + **MEASURED** |
| `64B` | 32:0B | (a) on `880.1.20`, the same WRITE with a different low5 (28/28 store-preceded); (b) on `102.A`, the ladder **multiply** | **FORCED** (F1) / **MEASURED** |
| `64B` on `102.A` | 32:0B | multiplicand is **neither** `mem[p]` **nor** the incoming `acc`. Under a 2-input ALU it is the word's own ALU result (`acc ± DR`); under a 3-input ALU it is `mem[ptr]` in 260 of 336 survivors | **FORCED under the 2-input model only** (R1 F8) — **model-dependent, enumerated** |
| `419` | 20:19 | consumes the external-DRAM read register `DR`. Family B: `acc ← acc − DR`. Family A: `acc ← DR − P` | R1 FORCES that it uses `DR`; **the form is NOT settled** |
| `680` | 34:00 | carries `hi12` bit 4; the store takes `acc` **before** this word's own ALU step. Family B: `acc ← DR − P`. Family A: `acc ← P + mem[p]` | store timing **FORCED** (F2); ALU **NOT settled** |
| `000` | 00:00 | Family B: `acc ← acc ± P`. Family A: **no job at all** (all 33 modelled ops work) | **NOT settled** |

### 3.2 New: the write-source split is a split on `lo12[11:5]` — C1

R1 established that among the six `880.1.20.*` forms, `lo12 ∈ {64B, 655}` is
preceded by a bit-4 store 44/44 and `lo12 ∈ {2C7, 40B, 2D9, 2D5}` 0/56, against a
23.3 % base rate, and concluded "`lo12` selects the write-data source". Resolving
those six into the A2 sub-fields:

```
   880.1.20.2C7   UP=16 LOW=07   40 sites    0 store-preceded    0.0 %
   880.1.20.64B   UP=32 LOW=0B   28 sites   28                 100.0 %
   880.1.20.655   UP=32 LOW=15   16 sites   16                 100.0 %
   880.1.20.40B   UP=20 LOW=0B    7 sites    0                   0.0 %
   880.1.20.2D9   UP=16 LOW=19    6 sites    0                   0.0 %
   880.1.20.2D5   UP=16 LOW=15    3 sites    0                   0.0 %
   880.1.60.2D4   UP=16 LOW=14   (the READ)
```

The split is **exactly `UPPER == 0x32`**, and it survives holding `low5` fixed:

* `0x655`(32,**15**) 16/16 vs `0x2D5`(16,**15**) 0/3
* `0x64B`(32,**0B**) 28/28 vs `0x40B`(20,**0B**) 0/7

⇒ **the DRAM write-data source is carried in `lo12[11:5]`, and `lo12[4:0]` carries
none of it.** **MEASURED.** This is the first time a *sub-field* of `lo12` has been
tied to a specific datapath decision.

Corollary R1 flagged as a caveat and this settles in its favour: the four
zero-percent forms **are not writes** — they are a different DRAM operation
(`UPPER = 0x16` is 106 words, 99 of them class-1, **0 % cursor-fetch and 0 % store**;
it is an address/read family, not a data family).

### 3.3 New: the "separator" is a generic delay tap — C2

R1 §8 reported the ladder separator as a reverb-specific drain whose class-A word
clobbers `P` (its one visibly unclosed model). The same five-word shape occurs at
**28 sites in 15 images**:

```
  algo0  NO OPERATION  w26 : 880.1.60.2D9 │ 000.A.09.655 │ 000.2.F7.000 │ 212.2.00.419 │ 880.1.20.64B
  algo9  SINGLE DELAY  w5  : 880.1.60.2D9 │ 202.A.B8.655 │ 000.2.48.000 │ 212.2.00.419 │ 880.1.20.64B
  algo16 ROOM REVERB 1 w11 : 880.1.60.2DA │ 000.A.00.695 │ 000.2.BA.000 │ 212.2.00.419 │ 880.1.20.64B
  algo65 S.DELAY+S.DEL w8  : 880.1.60.2D9 │ 202.A.01.655 │ 000.2.FF.000 │ 212.2.00.419 │ 880.1.20.64B
  ... 28 sites, 15 images
```

Read as a delay tap with feedback this is exactly right, and it pins two `lo12`
roles the reverb alone could not:

* `*.A.*.655` / `*.A.*.695` — **multiply the delay-line read data by the cursor
  coefficient**. `202.A.*.655` is at distance **exactly 1** after a DRAM read in
  20/20 sites, `000.A.*.655` 2/2, `212.A.*.655` 1/1, `*.A.*.695` 5/5. **MEASURED.**
* `212.2.00.419` — the word that carries the bit-4 store feeding the write.
  28/28 at distance exactly 3 after the read. **MEASURED.**

So the reverb's `000.2.00.419` (core slot 2) and the delay tap's `212.2.00.419`
share a `lo12` that only ever appears downstream of a DRAM read — 44 of its 45 sites
in the whole machine. **The single exception is `400.A.00.419` = kernel `iw6`**,
which sits in a block K6 measured to contain no DRAM word at all (§5.4).

### 3.4 Does this settle R1's family A vs family B? — No, and here is why

I tried to settle it and failed; both attempts are reported because both are
informative.

**Attempt 1 (failed).** If `UPPER = 0x32` meant "operand = the DRAM data path", then
`880.1.20.64B` (write) and `102.A.00.64B` (multiply with multiplicand `DR`) would
agree, and R1's 3-input branch would be selected. **Falsified by `0x647`**, which is
also `UPPER = 0x32` and is **0/41 after a DRAM read**, across many images. `UPPER`
alone does not select the DRAM path.

**Attempt 2 (failed).** `012.2.00.680` (slot 3) is 16/16 within 3 words after a DRAM
read, which would say it consumes `DR` — family B. But the other `hi12` variants of
the *same* `lo12` are **0/7** (`002.2.xx.680` ×6 in ENSEMBLE, `084.2.02.680` = kernel
`iw2`). The 16/16 is a tautology: `012.2.00.680` occurs **only** inside the motif.
No information. (My first run of this control also under-counted, see §8.)

**Net:** §3.2's UPPER result strengthens R1's §7.1 corpus argument — the split is
now localised to a sub-field rather than to a whole 12-bit value, and the 44/44 half
gains 28 more sites in 13 more images (§3.3). That argument ranks **family B**.
Everything else stays as R1 left it. **The 2-way choice is not closed.**

---

## 4. CONTEXT 2 — the LFO, and the falsification it forces

### 4.1 The measurement

`lo12 = 0x200` occurs 68 times and is the most tightly constrained value in the
machine:

```
   68 / 68 are class A (cursor fetch)          base rate 26.3 %
   68 / 68 carry hi12 bit 4 (store acc)        base rate 22.6 %
   only four hi12 values ever carry it:
       092.A.dd.200   f31=1   n=29    phase accumulate, coeff = C-RAM[+0]
       094.A.dd.200   f31=2   n=29    wrap,             coeff = C-RAM[+1]
       09A.A.00.200   f31=5   n= 9    COMPRESSOR / kernel iw30, always SOLO
       412.A.00.200   f31=1   n= 1    kernel iw33
```

In **12 of 20** images the pair addresses the **same D-RAM cell** with the pointer
frozen (`addr8 = 0` on both, and on the `082.2.00.1C0` between them) — CHORUS,
MODULATED CHORUS, FLANGER, AUTO PAN, VIBRATO, MIX UP, S.DELAY+FLANGER,
S.DELAY+VIBRATO, S.DELAY+PHASER, PEQ+CHORUS, PEQ+FLANGER. In the other 8 the two
words sit on different cells (PHASER +0/+14, ENSEMBLE +0/+5, COMPRESSOR +11/−52,
RING MODULATOR, S.DELAY+CHORUS, PEQ+VIBRATO, PEQ+COMPRESSOR ×3). **MEASURED** —
reported because the "same cell" premise is *not* universal and the earlier notes
did not say so.

CHORUS is the clean witness and it is the one whose constants are MEASURED: the
cold-boot capture gives `C-RAM[0x00] = 0x000072` (= 0.6 Hz at 44.1 kHz) and
`C-RAM[0x01] = 0x7FFFFF` (the wrap constant, 29/29 across the corpus).

### 4.2 The forced conclusion — B1

Two words. One cell. Two constants. The cell must end up a 0.6 Hz ramp.

Suppose both words performed the **same** operation `⊕`. Then per frame the cell
receives `phase ⊕ 0x72 ⊕ 0x7FFFFF`. Enumerating every binary operation an
accumulator ALU can offer:

| `⊕` | result | LFO? |
|---|---|---|
| `+` | `phase + 0x800071` per frame ≡ `phase − 0x7FFF8F` (24-bit) | ≈ 22 kHz, **no** |
| `−` | `phase − 0x800071` | ≈ 22 kHz, **no** |
| `×` (Q0.23) | `phase · 8.6e-6 · 1.0` | collapses to 0 in two frames, **no** |
| `min` | `min(phase, 0x72)` | constant, **no** |
| `max` | `max(phase, 0x7FFFFF)` | constant, **no** |
| `and` / `or` | `phase & 0x72` / `phase \| 0x7FFFFF` | constant, **no** |

**No single operation works.** ⇒ the two words compute different things. They are
identical in `class4`, `addr8` **and `lo12`**, and differ only in `hi12` bits 1 vs 2
(`f31` = `hi12[3:1]`, values 1 and 2). ⇒ **the operation select is not in `lo12`.**
**FORCED.**

`09A.A.00.200` (`f31 = 5` = `hi12` bits {1,3}) is a third value on the same `lo12`,
used **solo** — never in a pair — in COMPRESSOR, PEQ+COMPRESSOR, PEQ+COMPR+DIST,
PEQ+COMPR+OVERDR and in the kernel's own mix block at `iw30`. A compressor envelope
follower is exactly the third operation you would want on a `(cell, coefficient)`
route. **CONSISTENT.**

### 4.3 What `lo12 = 0x200` therefore means

Everything the three words share, and nothing they do not:

> **`0x200` (UPPER 0x10, low5 0x00, f3 0) = "second ALU operand ← the fetched
> coefficient; memory operand ← `mem[ptr]`; result written back through the `hi12`
> bit-4 store".** It is the *coefficient-into-the-adder* route (the multiplier is
> bypassed) — which is why every one of its 68 sites is class-A **and** storing, and
> why no other `lo12` in the corpus is locked to both.

**INFERRED (strong).** The alternative — that `0x200` routes the coefficient into
the *multiplier* and the accumulate is implicit — is not excluded, but then the
0.6 Hz rate constant would be a multiplicand rather than an increment and the ramp
would not be linear in time. **Enumerated, not chosen.**

`082.2.00.1C0` (the middle word, same cell, class 2 ⇒ **no** coefficient, no store)
reads the phase cell into the datapath. `lo12 = 0x1C0` is 103 words, `hi12 ∈ {002,
012, 082, 084, 092}`, and `hi12 = 0x082` carries **only** this `lo12`, 64/64.
**MEASURED**; the "modulation-source read" role is **INFERRED** and unchanged.

### 4.4 The store-timing conflict this opens — OPEN

R1 **FORCED** (zero survivors for the alternative, in all three models) that a
`hi12` bit-4 store takes the accumulator **before** that word's own ALU step. That
was established on **one word**, `012.2.00.680`.

A phase accumulator needs the opposite on `092.A.00.200`: `acc ← mem[P] + rate`,
**then** `mem[P] ← acc`. With store-before, the word writes the stale accumulator
over the phase and the LFO cannot run.

Three resolutions, **enumerated, none chosen**:

1. **Store timing is encoded per word.** The two words differ in `hi12` bit 7
   (`0x012` has it clear, `0x092` set). `hi12` bit 7 is currently rendered as a
   *speculative* "index/address domain" bit with no reading. "bit 7 = store takes
   the ALU result" is a **LEAD** that costs nothing to test and would reconcile both
   results exactly.
2. **R1's F2 is right and the LFO reading is wrong** — e.g. the phase lives in the
   accumulator across the triple and the cell is only a spill slot. This survives
   the 8 images where the pair is on *different* cells (§4.1) better than the
   same-cell reading does.
3. **Two accumulators.** The block diagram has ACCA and ACCB; if `f31` steers which
   one the store takes, "before/after" is the wrong axis entirely. This is also R1's
   own §8 escape hatch for the separator's `P` clobber.

---

## 5. CONTEXT 3 — the input and mix stages

K6 (`notes/dsp-k6-input-stage.md`) FORCED the addressing of I-RAM 0..11 and showed
the stage hands the **accumulator** to the mix block at 12..41. What arithmetic that
forces:

### 5.1 The pointer walk, with the sub-fields resolved

```
 iw  word           f31 ST cell   cursor  lo12 = UPPER:low5 (f3)
  0  092.2.01.20D    1  Y  X+0      -      10:0D (0)   kernel-exclusive lo12
  1  C0A.0.E0.000    5  n   --      -      00:00 (0)   C-format, datapath no-op
  2  084.2.02.680    2  n  X+1      -      34:00 (2)
  3  012.2.FF.1CE    1  Y  X+3      -      0E:0E (7)
  4  204.2.02.1CE    2  n  X+2      -      0E:0E (7)   <- THE LEFT INPUT LATCH
  5  202.A.00.448    1  n  X+4     +0      22:08 (1)   kernel-exclusive lo12
  6  400.A.00.419    0  n  X+4     +1      20:19 (0)   EOB
  7  090.A.01.1C8    0  Y  X+4     +2      0E:08 (7)
  8  084.2.01.1C0    2  n  X+5      -      0E:00 (7)   <- THE RIGHT INPUT LATCH
  9  012.2.FF.1D5    1  Y  X+6      -      0E:15 (7)   the `mac` route, on class 2
 10  282.A.01.417    1  n  X+5     +3      20:17 (0)   kernel-exclusive lo12
 11  400.2.01.447    0  n  X+6      -      22:07 (1)   EOB
```

### 5.2 The arithmetic block B forces

`X+4` is **read at `iw5` with coefficient `cur+0`, read again at `iw6` with `cur+1`,
and written at `iw7` with `cur+2`** — read-before-write on a cell no body touches
(K6: 0 of 38 images) and no other kernel word touches. Driven by the input latch
`X+2` read one word earlier at `iw4`.

That shape is a **first-order recursive section with three coefficients** — the
canonical input conditioner (DC blocker / one-pole de-emphasis / input trim with
smoothing). It is not a gain: a gain needs one coefficient and no state cell, and a
pure gain would not read the state cell twice. **FORCED (the shape); OPEN (which of
the standard first-order forms).**

Block A is *not* symmetric with block B (K6 §4.3, MEASURED): it reads two operands
(`X+1`, the one-frame feedback cell the epilogue wrote, and `X+2`, its latch) and
produces two stores (`X+0`, which the epilogue reads back in the same frame, and
`X+3`, which nothing reads). So the two channels are conditioned by **different**
code and any model that assumes a symmetric stereo pair is wrong.

### 5.3 The `lo12` readings this context implies

| `lo12` | where | what it forces | status |
|---|---|---|---|
| `1CE` (0E:0E) | `iw3` **stores** `X+3`; `iw4` **reads the input latch** `X+2`; epilogue `w79` stores, `w80` reads | one `lo12` covers the port read *and* the frame-loop store/read ⇒ **`lo12` does not encode "read the input port"**; K6's "the port-ness is entirely in the address" is confirmed at the field level | **MEASURED** |
| `1C0` (0E:00) | `iw8` reads the right latch; `082.2.00.1C0` reads the LFO phase | same route, two completely different data ⇒ same conclusion | **MEASURED** |
| `1D5` (0E:15) | `iw9`, a **class-2** word (no cursor fetch, so no coefficient) carrying the DETERMINED `mac` route | `mac`'s full semantics (`acc += P ; P = coef·mem[p]`) cannot all be in `lo12 = 0x1D5`: with no coefficient there is no product to form. The part of `mac` that `0x1D5` can carry is at most **"memory operand ← `mem[p]`"** | **FORCED** |
| `20D`, `448`, `417` | `iw0`, `iw5`, `iw10` | **0 occurrences in 2974 body words** — kernel-only routes, and therefore the three best targets for a decode that cannot be confounded by body idioms | **MEASURED** |
| `419` (20:19) | `iw6` | the **one** exception in the machine to "`0x419` appears only downstream of a DRAM read" (44/45), and it sits in a block with no DRAM word | **MEASURED, OPEN** |

`iw6`'s exception admits two readings, **enumerated**: (i) the input stage
deliberately consumes whatever the previous frame's last DRAM read left in `DR` —
possible but ugly, and it would make the input stage frame-order-dependent;
(ii) `0x419` is not a `DR` route at all and its 44/45 correlation is idiom
membership. Reading (ii) is the conservative one and it weakens §3.1's `0x419` row
to *"R1 forces slot 2 to consume `DR`; the corpus does not independently confirm it"*.

### 5.4 The four unknown coefficients — and what they cost

K6 §9.2 measured that the 20-value stream the host writes at C-RAM 0x00 in the
cold-boot capture is the **body's** bank, not the header's, so **the input stage's
coefficients `cur+0..cur+3` are values this project has never seen**. The mix block
at 12..41 adds ~14 more class-A multiplies on the same unseen bank.

Consequence, and it is the load-bearing one for the brief: **the transfer function
measured from audio-in to audio-out is `H_input · H_body · H_output`, not `H_body`.**
The parametric-EQ acceptance test as stated in the brief would compare
`H_input · H_eq · H_output` against `H_eq` and report a discrepancy that is not the
ALU's fault. §7 fixes this.

---

## 6. Cross-context joins, and the conflict with the biquad

### 6.1 The joins that hold

| `lo12` | context 1 | context 2 | context 3 | consistent? |
|---|---|---|---|---|
| `1C0` | — | LFO phase read (class 2, no coeff) | right input latch read (class 2, no coeff) | ✔ both are "class-2 read of `mem[ptr]`, no coefficient" |
| `1CE` | — | — | store `X+3`, read latch `X+2`, epilogue store+read | ✔ "class-2 touch of `mem[ptr]`", store/read decided by `hi12` bit 4 |
| `1D5` | — | — | `iw9`, class 2 | ✔ only if `0x1D5`'s multiply half comes from `class4` bit 3, not from `lo12` |
| `419` | motif slot 2 + delay tap (`DR` consumer) | — | `iw6`, no DRAM in the block | ✘ **the one hard conflict**, §5.3 |
| `200` | — | LFO accumulate / wrap / compressor | kernel `iw30`, `iw33` | ✔ the kernel's own mix block uses the same envelope route as COMPRESSOR |
| `64B` | ladder multiply **and** DRAM write | — | — | ✔ only under "`lo12` is routing, not operation" (B2) |

### 6.2 The conflict with the biquad path — flagged as the brief asked

I did not run the biquad solve, but its published block is enough to say where the
collision is. The PARAMETRIC EQ section (`prog39`, 9 words, repeated 9×, cursor
positions MEASURED and the coefficients PROVEN):

```
   w5   000.A.00.1D3   f31=0   P = b1*S0 ; latch A <- S0
   w6   212.A.01.412   f31=1   S0 <- x ; acc = P ; P = b0*x
   w7   202.A.01.1D5   f31=1   mac      acc += P ; P = b2*S1
   w8   202.A.01.1D4   f31=1   mac.lb   acc += P ; P = -a1*S2 ; latch B <- S2
   w9   202.A.00.1D5   f31=1   mac      acc += P ; P = -a2*S3
   w10  102.2.FF.687   f31=1            acc += P ; S3 <- latch B
   w11  804.8.16.415   f31=2            class-8 post-sum step, OPERATION UNKNOWN
   w12  212.A.FF.407   f31=1   mulst    S2 <- acc ; P = makeup*acc
   w13  000.2.03.647   f31=0            acc <- P ; S1 <- latch A
```

**The conflict.** §4.2 forces the operation select into `hi12[3:1]` (`f31`). The
LFO's minimal pair says `f31 = 1` and `f31 = 2` are different operations, and the
natural reading is `f31 = 1` = accumulate. The biquad block is **consistent with
that on five of nine words** — `w7 w8 w9 w10` are all `acc += P` at `f31 = 1`, and
`w5` (which does not touch `acc`) is `f31 = 0`. But it **contradicts it on two**:

* `w6` (`212.A.01.412`, `f31=1`) and `w13` (`000.2.03.647`, `f31=0`) are both
  annotated `acc ← P` — the same operation at two different `f31`.
* `w12` (`mulst`, `f31=1`) leaves `acc` **unchanged** in the DETERMINED form, which
  is not "accumulate".

So **`f31` is not a simple 3-value ALU-op enum.** Three ways out, **enumerated**:

1. **`f31` is a bit-set, not an enum.** `f31=1` = `hi12` bit 1, `f31=2` = bit 2,
   `f31=5` = bits {1,3}. Independent enables ("add-enable", "negate/compare-enable",
   "limit-enable") would let `w6` and `w13` differ in a *second* dimension while both
   ending at `acc ← P`. This is also how `hi12` is already known to work (it is a
   MEASURED horizontal microword).
2. **The `w6` / `w13` annotations are the weak link.** Neither is DETERMINED; both
   come from the biquad transfer-function reconstruction, which pins the *sequence*
   of sums exactly (0.000e+00) but does **not** pin which individual word loads vs
   accumulates — a cascade can be re-phased. `w13` `acc ← P` followed by `w14`
   `P = b1·S0'` followed by `w15` `S0' ← acc(old) ; acc ← P` is self-consistent and
   requires R1's **store-before-ALU** on `w15` — a place where the biquad path and
   R1 already agree and which is worth checking first.
3. **The operation is split between `f31` and `f98`.** `hi12[9:8]` is a MEASURED
   field whose accumulator-op reading was tested and failed *on its own*; it was
   never tested jointly with `f31`. `w6` is `f98=2`, `w13` is `f98=0`.

**No resolution is chosen.** What is **not** in doubt either way: the operation is
not in `lo12`, because `092/094.A.dd.200` differ in neither `lo12` nor `class4` nor
`addr8`.

**A second, quieter conflict** with the biquad: `lo12 = 0x415` is the class-8
post-sum step at `w11`/`w20`, and it is also 146 class-A multiplies and 24 class-2
words elsewhere (205 sites, 6 `hi12` values). Whatever `0x415` routes, it routes it
for a multiply *and* for the class-8 post-sum. That is the roadmap's item 2
(`lo12 = 0x415` across classes A/2/8) and it now has a name: `0x415` = `UPPER 0x20 :
low5 0x15`, i.e. the *same* `low5` as `mac` with a different UPPER.

---

## 7. The acceptance test — what is actually runnable

The brief's plan is: impulse/sweep through PARAMETRIC EQ, compare against the
biquad solved to 0.000e+00. As stated it **cannot** discriminate, because of §5.4.
Two fixes, both cheap:

**(1) The ratio test — exact, and it needs no unknown coefficients.**
Everything outside the body is linear and *fixed*: `H_in` and `H_out` do not depend
on the EQ parameters. Measure the EQ program twice at two cursor settings `θ₁`, `θ₂`
and take the ratio:

```
      Y₁(f) / Y₂(f)  =  H_in·H_eq(θ₁)·H_out  /  H_in·H_eq(θ₂)·H_out
                     =  H_eq(θ₁) / H_eq(θ₂)
```

`H_in` and `H_out` cancel **exactly**, and the right-hand side is fully known from
the firmware's own coefficient designer. Report `max |20·log₁₀|Y₁/Y₂| −
20·log₁₀|H_eq(θ₁)/H_eq(θ₂)||` in dB over 20 Hz..20 kHz. This is a genuine pass/fail
on the ALU decode and it is immune to §5.4. **The test can fail** — a wrong ALU
gives a ratio that is not a biquad ratio at all.

**(2) Measure `H_in·H_out` separately.** The natural null body is `NO OPERATION`,
but §0/D2 says it is **not** a null: 49 words, two full delay-tap idioms with DRAM
read *and* write, 8 coefficient multiplies. Its response will contain the delay
line. The real null is `EFF_Disconnect` — K5 DETERMINED that it rewrites I-RAM 64/71
to the unit's own header setup block (42/50) instead of the body entry (84/200). A
disconnected unit runs kernel+epilogue and no body. **That** is the measurement of
`H_in·H_out`. (K5 also FALSIFIED the old reading that disconnect *attenuates*: a
disconnected unit goes silent, so the level here is the dry path only.)

**Reverb tail test.** Unchanged and still valid: with the ROM-measured delays
127/435/489/183/522 the first echo of `ROOM REVERB 1` must appear at 127 samples
(2.88 ms at 44.1 kHz) and the ladder must be all-pass — flat magnitude, decaying
envelope. **This test discriminates family A from family B** (R1 O-1): the two
families write *different values* to the delay line, so the tails differ after the
first pass. That is the single highest-value measurement available once the core
runs, and it closes R1's open question for free.

---

## 8. My own misses — PREDICT-THEN-CHECK

Reported because the rules require it and because two of them changed the result.

| # | prediction | what happened |
|---|---|---|
| 1 | The corpus is 40 images / 3237 words / 167 distinct `lo12`. | **Wrong.** Two images (`GEQ`, `ROOM`) are misaligned parses — 22/48 and 78/132 words violate the MEASURED "bits 36..39 are zero". Corpus is 3057 words / 82 `lo12`. Every structural number in §2 was re-run; the conclusions strengthened (`lo12` HD-1 z went from +10.1 to **+11.3**). |
| 2 | `low5 = 0x15` = "adder B ← P" (from `mac`), so `low5 = 0x15` words should follow a class-A multiply more often than base. | **Miss.** 29.8 % vs a 26.3 % base — no effect. The `low5` = adder-source reading is **not supported**; it survives only as the weaker "secondary route/latch select" of §2. |
| 3 | `lo12 = 0x680` consumes `DR`, therefore family B. | **Killed by its own control.** The 16/16 is entirely inside the motif; the other seven sites are 0/7. No information either way. |
| 4 | `UPPER = 0x32` = "the external-DRAM data path". | **Falsified** by `0x647` (also `UPPER 0x32`, **0/41** after a DRAM read). |
| 5 | My DRAM-read detector was `hi12 & 0xF00 == 0x800`. | **Bug.** It missed `900.1.60.*` (35 sites, e.g. CHORUS `w9`/`w18`) and `800.1.60.*`. Corrected detector = `hi12 bit 11 set ∧ class4 == 1 ∧ addr8 == 0x60`; base rate moved 8.7 % → 14.9 % and `0x2C7` moved 4.3 % → 67.4 %. All §3 numbers are post-fix. |
| 6 | The LFO pair always addresses one cell. | **Not universal**: 12 of 20 images yes, 8 no (PHASER, ENSEMBLE, COMPRESSOR, RING MODULATOR, S.DELAY+CHORUS, PEQ+VIBRATO, PEQ+COMPRESSOR ×3). The §4.2 argument is stated on CHORUS, where it is exact, and does not need the general claim. |

The "after a DRAM read" statistic is a **screen, not a proof**: a value at 0 % over
40+ sites in many images cannot be a `DR` route (that is how misses 3 and 4 were
caught), but a value at 100 % may simply live in one idiom. Both directions are used
that way above and nowhere else.

---

## 8b. Independent convergence with `dsp-alu-structure.md`

A concurrent pass (`notes/dsp-alu-structure.md`, `tools/kn5000_dsp_lo12.py`) attacked
the *same* field from the *same* corpus with a different method and a different
reader (it parses the committed `.dsm` listings; this note parses the ROM through
`kn5000_dsp_extract`). The two agree where it matters, which is worth more than
either alone:

| | this note | `dsp-alu-structure.md` | agree? |
|---|---|---|---|
| corpus | 3057 words / 82 `lo12` / 123 pairs | 3057 / 82 / 123 | ✔ identical |
| `lo12` is an opcode? | no — horizontal microword, z = +11.3 | no — decomposable, orthogonal to `hi12` | ✔ |
| bits 11 and 5 | co-occur, 10 of 11 **values**; mark the control/pointer-load family | locked, 95 of 96 **words**; a 2-bit MODE (`00` datapath / `11` register write, `01` once = `rstcur`) | ✔ same fact, two counts |
| the operand field | `lo12[11:5]` (lowest inter-half MI of any split) | `SRC` = `lo12[10:6]` | ✔ **the same field** — within datapath words bit 5 is always 0, so the two differ only in whether the mode bit is carried along |
| the low field | `lo12[4:0]`, 25 of 32 codes | `L` = `lo12[4:0]`, 24 of 32 codes | ✔ |

**One place this note constrains that one.** `dsp-alu-structure.md` labels
`lo12[4:0]` the **ACTION** — "what is done with the operand". §4.2 here shows that
*no* part of `lo12` can distinguish the LFO's accumulate from the LFO's wrap: the two
words are equal in `class4`, `addr8` and all twelve `lo12` bits. So `L` can be a
*routing* action (which port, which latch, which write-back) but it **cannot** be the
arithmetic function. That is a strictly tighter statement than "`lo12` is not an
opcode", and it is the one that decides what a core must read to compute.

`lo12[8:6]` (§A3) and `SRC` are the same bits seen at different granularity; the
six-way partition in §2 is the finer statement and should be carried into whichever
note survives the merge.

---

## 9. To sync into `kn5000-roms-disasm/dsp/` (nothing there was edited)

1. **`instruction-set.md`** — add: `lo12` is a horizontal microword (z = +11.3, the
   same test as `hi12`); the bit-5 boundary; the `f3 = lo12[8:6]` partition; bits
   11+5 = the control/pointer-load marker. Add the **withdrawal**: `lo12` alone
   cannot carry the ALU operation (B1/B2/B3), so the "`lo12` = route, `class4` =
   arithmetic" hypothesis (`-core-draft.md` §6 item 2) should be restated as
   "`lo12` = route, **`hi12`** = arithmetic", with `f31` as the lead and §6.2's
   three enumerated escapes.
2. **`analysis/r1-allpass-motif.md`** — §7.1's write-source split is a split on
   `lo12[11:5]` (two `low5`-matched minimal pairs cross it); §8's "separator" is a
   generic delay tap present at 28 sites in 15 images, not a reverb drain.
3. **`tools/dsp_disasm.py` / `upd6383d.cpp`** — render `lo12` as
   `UPPER:low5 (f3=n)` the way `hi12` is already rendered as flags + residue.
   Annotate the 5-word delay-tap idiom. Do **not** emit an ALU mnemonic from `lo12`.
4. **`tools/gen_dsp_disasm.py`** — algo 79 (`GEQ`, 48 words) and algo 88 (`ROOM`,
   132 words, shared by 88/89/90/91) parse to malformed images and are silently
   dropped; `GEQ` is an EQ-family program and is worth recovering.
5. **`sym/kernel.sym`** — `iw5..iw7` = `InCondB` (the first-order input section on
   `X+4`), `iw4`/`iw8` = `InLatchL`/`InLatchR`.

## 10. Reproducing

```
cd kn7000_mame/tools/dsp_alu_crossval
# corpus (drops the two malformed images, then matches the .dsm tree word-for-word)
python3 fields.py      # A1 (HD-1 z), the f31/lo12 contingency
python3 split.py       # A2 (the bit-5 boundary), A3 (f3), A4 (bits 11+5)
python3 contexts.py    # the three contexts verbatim, with sub-fields resolved
python3 tests.py       # T1 (0x200 68/68), T4 (store-precedence, base 703/3017)
python3 decide.py      # C1: the write-source split is on lo12[11:5]
python3 lfo.py         # the LFO triple in every image; prog00 is not a no-op
python3 fix.py         # the corrected DRAM-read statistic + controls
python3 control.py     # the held-out control that killed prediction 3
python3 final.py       # per-hi12 breakdown; every 0x680 site; the delay-tap idiom
```

Inputs: `kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom` (microcode +
parameter streams) and `kn5000_v10_program.rom` (effect names), through
`kn7000_mame/tools/kn5000_dsp_extract.py`. Python stdlib only.
