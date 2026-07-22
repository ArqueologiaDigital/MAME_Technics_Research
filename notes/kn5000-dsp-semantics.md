# NEC uPD6383GF — instruction SEMANTICS by constraint solving

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_semantics.py` (imports `kn5000_dsp_extract` and
`kn5000_dsp_biquadmap`; **neither is edited**).

**Append-only successor material.** It does not edit `notes/kn5000-dsp-biquad-map.md`,
`-biquad-coeffs.md`, `-biquad.md`, `-cursor-general.md`, `-class2*.md`, `-effect-map.md`,
`-necfamily.md`, `-encoding.md`, `-header.md`, `-reverb.md`, `-coefficients.md`,
`-parameters.md`, `-datasheet-hunt.md` or `-INDEX.md`. Corrections to them are in §7.
It does not touch `notes/kn5000-dsp-abv.md` or `tools/abv_*.py`.

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or
**SPECULATIVE**. §8 lists what is falsified or explicitly not established.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_semantics.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
```
Sections: `model space search verify reverb`. Runtime ≈ 60 s.

---

## Headline

1. **★★★ THE BIQUAD SECTION IS SOLVED, AND THE SOLUTION IS FORCED.** An exhaustive
   sweep of **19,674,720** explicitly enumerated semantic assignments leaves **144**
   that reproduce the biquad exactly, and those 144 are **one dataflow** modulo four
   observationally-equivalent binary choices *inside a single section*. The topology
   that a year of note-writing "refused every textbook form" is **DIRECT FORM I with
   four state cells and four writes — two of the four writes folded into multiply
   instructions**, which is why only two of them showed up as stores (§2, §3).
2. **★★★ IMPULSE-RESPONSE AGREEMENT IS EXACT.** Running the recovered semantics as an
   interpreter on **nine real ROM coefficient blocks** — `OVERDRIVE` ×2, `EXCITER` ×2,
   `PARAMETRIC EQ` ×5 — against the transfer function computed directly from the same
   words gives `max|err| = 0.000e+00` (bit-identical in double precision) over 64
   samples, for every block (§4).
3. **★★★ `[7]` IS DETERMINED UNIQUELY** by the search, by all 144 survivors, with no
   residual freedom: `212.A.FF.407` **multiplies the make-up gain by the ACCUMULATOR
   and writes the accumulator into the state cell `S2`**. So the recursion runs on the
   *unscaled* sum and the make-up gain is applied only on the way out — which is
   exactly why the sixth coefficient is the reciprocal of the numerator scaling and why
   the parameter path never writes it. The biquad-map note's INFERENCE is now **forced
   by the arithmetic**, not argued from three data points.
4. **★★ `hi12 = 0x212` = "write the operand into `mem[ptr]` and multiply by it."**
   `[1]` and `[7]` are the only two words in the section carrying it, and `[7]` is
   *determined* to be exactly that. Reading `[1]` the same way places the input write
   `S0 ← x[n]` on `[1]` and closes one of the four residual choices (§3.2). **INFERRED,
   from the encoding, independently of the mathematics.**
5. **★★ `lo12 ∈ {0x1D3, 0x1D4}` = "read into a carry latch"; `0x1D5` = "read, no
   latch"; `0x647`/`0x687` = "consume P and store latch A/B".** `[0]` (`1D3`) and `[3]`
   (`1D4`) are precisely the two memory reads whose value has to be re-written into
   *another* cell later in the section (the `x2←x1` and `v2←v1` shifts); `[2]` and `[4]`
   (`1D5`) are precisely the two whose value does not. That is a 2-of-4 coincidence the
   ISA had no reason to produce unless the low bits tag the latch (§3.2). **INFERRED.**
6. **★★ The class-8 word `804.8.16.415` now has a mechanism.** It sits between the
   instant the sum `v[n]` is complete (`[5]`) and the instant `v[n]` becomes stored
   recursive state (`[7]`). A rescale / round / saturate belongs exactly there, and
   nowhere else — which is why class 8 occurs in **filter-bearing images and nowhere
   else** (MCC +0.947, biquad-map §6). The biquad-map note could only say "not a
   general shifter"; the model says *why* there is no other place for it (§3.3).
   **INFERRED**; the operation itself is still not identified.
7. **★ THE REVERB CROSS-CHECK PASSES ON INSTRUCTION COUNTS, and it costs the brief one
   premise.** The only first-order all-pass realisable with **exactly one multiply** is
   `t = g·(x + d_out) ; d_in = x + t ; y = d_out − t`, and it needs exactly one add
   feeding the multiplier, the multiply, one add and one subtract. The 8-word motif has
   exactly one class-A word (gain from the cursor, the measured descending ladders) and
   exactly **three** non-multiplying arithmetic words, one of which — `104.2.00.000` —
   is the corpus-wide all-pass marker that appears in every all-pass effect and no
   other. **But it requires a SUBTRACT** (§5). The "no subtract exists" premise is
   therefore about a *storage convention* (negated `a1`, `a2`), not about the ALU.
8. **★ Numbers for the diffuser chain.** With the nine measured `CONCERT REVERB 1` gains
   and the reverb note's nine delay lengths, each stage's impulse energy is
   **1.000000000** (a true all-pass), the nine-stage cascade is loss-less to 3 ppm, echo
   density is **28.4 taps/ms** in the first 8000 samples, and 99 % of the energy has
   arrived by **392 ms** with a peak |h| of 0.043 (§5.3). A pure diffuser cascade does
   **not** decay — the decay must come from the damping filters and the recirculation
   *outside* the motif, so "does it decay like a reverb" is **not** answered here.

---

## 1. The machine model

Bounded by the CDJ-500 block diagram (pp. 1-15..1-17). Nothing outside it is invented;
the model uses a strict subset:

```
   acc      one accumulator                              (ACCA)
   P        the pending multiplier product                (MPLY -> P)
   mem[]    the STATE space, the '000.1.NN.000' pointer space; four cells per
            biquad section, cleared at program load       (cursor-general sect. 5.2)
   cursor   the implicit COEFFICIENT pointer into the '801.0' space, +1 per
            class-A word                                  (biquad-map sect. 2, MEASURED)
   ptr      the signed addr8 POST-increment data cursor    (biquad note, MEASURED)
   xin      the stage input bus
   TA, TB   two carry latches (TR0..TR3 on the diagram) written by a memory-reading
            multiply and read back by a later store
```

An instruction is `state -> state` with three unknown parts: what it does with the
**pending** product (`{none, ADD-P, SET-P}`), where its **own operand** comes from
(`{MEM, XIN, ACC}`), and what it **writes** to `mem[ptr]` (`{nothing, XIN, ACC, TA,
TB}`). Class-A words additionally do `P ← coefficient[cursor++] × operand`.

Fixed, not searched, because each is already MEASURED or PROVEN BY CONSTRUCTION:

* the pointer walk `S0 S0 S1 S2 S3 | S3 | S2 S2 | S1`, net **+4** per band, read off the
  signed `addr8` post-increments;
* the coefficient order `b1 b0 b2 −a1/a0 −a2/a0 makeup`, **one per class-A word**;
* class A multiplies, class 2 does not (bit 23);
* words `[5]` and `[8]` consume `P`, no other word in the section does.

## 2. The hypothesis space, and how much of it was covered

```
   SRC per class-A word (6 words)      3^6  =      729
   cell-writer selection (4 cells)     2^4  =       16
   written value per writer                    2..6 each
   ACC_OP free at [0], [1], [8]                      8
   section output register                           2
   ------------------------------------------------------
   TOTAL points ENUMERATED                   19,674,720     ALL VISITED
```

**Excluded a priori** — every restriction is listed here so that the result cannot be
mistaken for a search over a space quietly narrowed until it had one answer:

| | restriction | why |
|---|---|---|
| R1 | class-A `SRC ∉ {external-DRAM data buffer, DI latches}` | the biquad-bearing images contain **no** `880.1.60`/`880.1.20` bracket at all (class2-round2 §1.1) |
| R2 | exactly **one** write per state cell per sample, by one of the two words whose pointer sits on that cell | no-write makes the filter time-varying; two writes to one cell in one pass is redundant |
| R3 | `[2] [3] [4] [5]` accumulate; `[7]` does not | with fewer than five accumulates fewer than five products reach the sum; `[7]`'s predecessor's product was already consumed by `[5]` |
| R4 | read-before-write inside one instruction | |
| R5 | class 8 is the identity on the modelled state | it is the one word the P-consumer statistic pins at 0.000 |

**Scoring.** A candidate had to reproduce the biquad on **two generic random coefficient
6-vectors first** (seeded, printed by the tool) and only then on the real `OVERDRIVE`
bank. The generic vectors are the control: a real bank contains zeros and repeats
(`EXCITER`'s `b1` is exactly 0, `OVERDRIVE`'s `b0 == b2`) which a wrong assignment could
exploit. **MEASURED: 144 of 19,674,720 survive.**

## 3. The solution

### 3.1 What every one of the 144 survivors agrees on (**MEASURED**)

```
   word            ptr   operand      P-op          write
   [0] 0000A001D3  S0    MEM          {SET-P|none}  {-|XIN}
   [1] 0212A01412  S0    {MEM|XIN}    {ADD-P|SET-P} {-|XIN}
   [2] 0202A011D5  S1    MEM          ADD-P         {-|latch[0]}
   [3] 0202A011D4  S2    MEM          ADD-P         -
   [4] 0202A001D5  S3    MEM          ADD-P         {-|latch[3]}
   [5] 01022FF687  S3    -            ADD-P         {-|latch[3]}
   [6] 0804816415  S2    -            -             -
   [7] 0212AFF407  S2    ACC          none          ACC
   [8] 0000203647  S1    -            {ADD-P|SET-P} {-|latch[0]}
   section output register: P|acc
```

* **DETERMINED, no freedom at all:** `[2]`, `[3]`, `[4]`, `[6]`, and — the one that
  matters — **`[7]`**: `212.A.FF.407` multiplies the make-up gain by the **accumulator**
  and writes the **accumulator** into `S2`.
* **CONSTRAINED to two:** which of `[0]`/`[1]` writes `x[n]` into `S0`; which of
  `[2]`/`[8]` writes the latched `x[n−1]` into `S1`; which of `[4]`/`[5]` writes the
  latched `v[n−1]` into `S3`; whether the sum is started by `SET-P` at `[1]` or by an
  accumulator that is already zero; whether the section's output is read from `acc` or
  from `P` (identical whenever `[8]` is `SET-P`).
* `2 × 2 × 2 × ... = 144`. **These are observationally equivalent within one section**;
  no amount of biquad data can separate them.

### 3.2 The two encoding arguments that break two of the four (**INFERRED**)

* `[1]` and `[7]` are **the only two words in the section with `hi12 = 0x212`**, and
  `[7]` is *determined* to be a write-and-multiply. Reading `hi12 = 0x212` as **"write
  the operand into `mem[ptr]` and multiply by it"** puts the `S0` write on `[1]`.
  Corroboration from outside the section: the phaser's all-pass triple contains
  `212.2.01.412` in eight sections and the class-A twin `212.A.B0.412` in the ninth
  (class2-round2 §1.4) — i.e. the same "write" word with and without the multiply, which
  is what this reading predicts bit 23 does.
* `[0]` (`lo12 = 0x1D3`) and `[3]` (`lo12 = 0x1D4`) are **exactly** the two memory reads
  whose value must be re-written into another cell later in the section; `[2]` and `[4]`
  (`lo12 = 0x1D5`) are **exactly** the two whose value must not. Reading `1D3`/`1D4` as
  *"read into carry latch A/B"* and `0x647`/`0x687` as *"consume P and store latch
  A/B"* puts the `S1` and `S3` writes on `[8]` and `[5]` — the two P-consumers — and is
  the only reading in which those two words do anything the class-A accumulate does not
  already do.

### 3.3 The preferred reading, in full

```
   [0]  0000A001D3   P = b1  * S0 (= x[n-1]) ;  latch A <- S0
   [1]  0212A01412   S0 <- x[n] ;  acc = P ;  P = b0 * x[n]
   [2]  0202A011D5   acc += P ;  P = b2  * S1 (= x[n-2])
   [3]  0202A011D4   acc += P ;  P = -a1 * S2 (= v[n-1]) ;  latch B <- S2
   [4]  0202A001D5   acc += P ;  P = -a2 * S3 (= v[n-2])
   [5]  01022FF687   acc += P   -- the sum v[n] is complete ;  S3 <- latch B   (v2<-v1)
   [6]  0804816415   class 8: the filter-output step on acc (rescale/round/saturate)
   [7]  0212AFF407   S2 <- acc  (v1<-v)  ;  P = makeup * acc     -- the section output
   [8]  0000203647   acc <- P ;  S1 <- latch A                   (x2<-x1)
```

**This is textbook Direct Form I.** The reason the biquad and cursor-general notes could
not make any textbook form fit is now visible and is a single fact: **two of the four
state writes are folded into multiply instructions** (`[1]` writes the new input, `[7]`
writes the new recursion value), so only two of them appear as "stores", and DF-I looked
like it needed four instructions it did not have. The state cells are

```
   S0 = x[n-1]      S1 = x[n-2]      S2 = v[n-1]      S3 = v[n-2]
```

where `v` is the **unscaled** sum and `y = makeup × v`. The four cells cleared to zero at
program load (cursor-general §5.2) are exactly these.

## 4. The impulse-response test (**MEASURED**)

The recovered semantics were implemented as an interpreter and run on an impulse for 64
samples, against the transfer function computed directly from the *same* ROM words:

```
   algo 33 OVERDRIVE      block +02   max|err| = 0.000e+00   h[0..3] = +0.057198 +0.184110 +0.255994 +0.229601
   algo 33 OVERDRIVE      block +0B   max|err| = 0.000e+00   h[0..3] = +0.057198 +0.184110 +0.255994 +0.229601
   algo 35 EXCITER        block +03   max|err| = 0.000e+00   h[0..3] = +0.729565 +0.332234 -0.243305 +0.041741
   algo 35 EXCITER        block +0E   max|err| = 0.000e+00   h[0..3] = +0.729565 +0.332234 -0.243305 +0.041741
   algo 39 PARAMETRIC EQ  block +00   max|err| = 0.000e+00   h[0..3] = +1.434738 +1.218055 -1.177505 +0.229718
   algo 39 PARAMETRIC EQ  block +06   max|err| = 0.000e+00   h[0..3] = -2.000000 +0.000000 +0.000001 +0.000002
   algo 39 PARAMETRIC EQ  block +0C   max|err| = 0.000e+00   h[0..3] = -2.000000 +0.000000 +0.000001 +0.000001
   algo 39 PARAMETRIC EQ  block +12   max|err| = 0.000e+00   h[0..3] = -2.000000 +0.000000 +0.000001 +0.000001
   algo 39 PARAMETRIC EQ  block +18   max|err| = 0.000e+00   h[0..3] = -2.000000 +0.000000 +0.000000 +0.000000
```

**Honest scope.** This is a *consistency* test, not independent evidence: the semantics
were selected by requiring exactly this agreement on `OVERDRIVE`, so the other eight
blocks are the generalisation check, not the discovery. What it adds is real all the
same:

* the four **flat** PEQ default bands come out as `h = [−2, 0, 0, 0]` — a pure gain of
  −2 and nothing else, over 64 samples. Independent, quantitative confirmation of the
  make-up-gain reading of `NN+5` (`0x800000` = −2.0000, biquad-map §3) *and* of the
  "bands 2–5 are exactly flat at power-on" reading (§4 there), now from the code rather
  than from the coefficients;
* `OVERDRIVE`'s section is stable and decays; `EXCITER`'s alternates sign as its
  bandpass numerator `(1, 0, −1)` requires.

## 5. The reverb cross-check

### 5.1 What the biquad model predicts, before looking at the reverb

The biquad forced two things that are *not* about biquads: a class-A word multiplies **one
coefficient from the cursor by one operand**, and a class-2 word can be a two-operand ALU
step feeding the multiplier. So a one-multiply DSP stage is possible, and any effect that
needs one gain per stage should show **one class-A word per stage plus enough class-2
words to do the adds**.

### 5.2 What the motif is, and what an all-pass costs (**MEASURED / MEASURED**)

```
   [0] 880.1.60.2D4   external-DRAM bracket OPEN   -> d_out
   [1] 104.2.00.000   the all-pass marker
   [2] 000.2.00.419
   [3] 012.2.00.680
   [4] 880.1.20.655   external-DRAM bracket CLOSE  -> d_in
   [5] 102.A.00.64B   the ONE class-A word: g from the cursor
   [6] 000.2.00.000   NOP
   [7] 000.2.00.000   NOP
```

The **only** first-order all-pass realisable with exactly one multiply is

```
   t     = g * (x + d_out)
   d_in  = x + t
   y     = d_out - t          =>   H(z) = (-g + z^-N) / (1 - g z^-N)
```

(the two-multiply Schroeder form `d_in = x + g·d_out ; y = d_out − g·d_in` is what the
reverb note quotes; the identity above is its one-multiplier equivalent, and it is
**exact**, not an approximation). Its cost, beyond the delay read and the delay write, is
**one add feeding the multiplier, the multiply, one add, one subtract** — three
non-multiplying arithmetic words.

**The motif has exactly one class-A word and exactly three non-multiplying arithmetic
words**, and one of the three is `104.2.00.000`, the marker that occurs in every
all-pass-bearing image and in no other (MCC +0.881, class2-round2 §1.3) and that is the
**only** word shared between the reverb stage and the phaser's internal-RAM all-pass
(§1.2 there). Its position — immediately after the DRAM read, immediately before the
multiply chain — is exactly where `x + d_out` must be computed. **INFERRED, and it is
the strongest positional argument this project has for that word.**

> **The cross-check therefore PASSES on counts and position, and it is not a fit:** the
> instruction budget was fixed by the biquad, the motif was fixed by the ROM, and the
> all-pass identity was fixed by algebra. Nothing was tuned.
>
> **It does NOT determine which of `000.2.00.419` and `012.2.00.680` is the add and which
> is the subtract**, and it does **not** explain the *order*: the class-A multiply sits
> at `[5]`, **after** the DRAM close at `[4]`, so the value written to the delay line
> cannot be `x + t` computed in this stage unless `880.1.20.*` latches the write
> **address** (OF-RAM ADDR.R on the diagram) with the data taken from DATA BUF later, or
> the machine is pipelined across the stage boundary. **NOT ESTABLISHED** (§8).

### 5.3 The numbers (**MEASURED**)

Per-stage energy, with the nine measured `CONCERT REVERB 1` gains (cursor slots
`0x98..0x9C | 0xA1..0xA4`) and the reverb note's nine delay lengths:

```
   g = 0.750  N =  452   impulse energy = 1.000000000
   g = 0.630  N =  978   impulse energy = 1.000000000
   g = 0.620  N = 1077   impulse energy = 1.000000000
   g = 0.600  N =  691   impulse energy = 1.000000000
   g = 0.500  N =  789   impulse energy = 1.000000000
   g = 0.730  N =  638   impulse energy = 1.000000000
   g = 0.720  N = 1462   impulse energy = 1.000000000
   g = 0.700  N =  496   impulse energy = 1.000000000
   g = 0.600  N =  774   impulse energy = 1.000000000
```

Every stage is a **true all-pass** to nine digits — the recovered structure is
energy-preserving with the ROM's own gains, which is what a diffuser must be and what a
mis-recovered structure would not be.

The nine-stage cascade, driven by an impulse:

```
   10 % of the energy has arrived by   3553 samples (  80.6 ms)
   50 %                                6930 samples ( 157.1 ms)
   90 %                               11665 samples ( 264.5 ms)
   99 %                               17306 samples ( 392.4 ms)
   echo density  5158 taps above 1e-6 in the first 8000 samples  (28.4 taps/ms)
   total energy  0.999997   peak |h| = 0.043136 at n = 6086
```

**Interpretation, stated carefully.** 28 taps/ms with no single echo above 0.043 is a
dense, flat, colourless diffuser — exactly what nine cascaded all-passes with descending
gains are *for*. It is **not** a reverb tail: the cascade is loss-less by construction
(total energy 1.000), so it neither decays nor sustains. The decay must come from the
damping triples and the recirculation the cursor-general note maps at bank slots
`0x93..0x95`, `0x9E..0xA0`, `0xA6..0xA8` — none of which is inside the motif. **The brief's
"check the impulse response actually decays like a reverb" cannot be answered by the
diffuser alone, and reporting a decay here would be reporting an artefact.**

## 6. Determined / constrained / unknown — the summary the brief asks for

| word | status | semantics |
|---|---|---|
| `[7] 212.A.FF.407` | **DETERMINED** (all 144) | `P = makeup × acc` ; `mem[S2] ← acc` |
| `[2] 202.A.01.1D5` | **DETERMINED** | `acc += P` ; `P = b2 × mem[S1]` |
| `[3] 202.A.01.1D4` | **DETERMINED** (operand, P-op) | `acc += P` ; `P = −a1 × mem[S2]` ; latch |
| `[4] 202.A.00.1D5` | **DETERMINED** (operand, P-op) | `acc += P` ; `P = −a2 × mem[S3]` |
| `[0] 000.A.00.1D3` | operand DETERMINED (`MEM`), rest **CONSTRAINED to 2** | `P = b1 × mem[S0]` ; latch, and possibly the `S0 ← x` write |
| `[1] 212.A.01.412` | **CONSTRAINED to 2**, broken by `hi12 = 0x212` | `S0 ← x[n]` ; `P = b0 × x[n]` |
| `[5] 102.2.FF.687` | P-op DETERMINED, write **CONSTRAINED to 2** | `acc += P` ; `mem[S3] ← latch B` |
| `[8] 000.2.03.647` | **CONSTRAINED to 2×2** | `acc ← P` ; `mem[S1] ← latch A` |
| `[6] 804.8.16.415` | **UNKNOWN**, but its *place* is determined | a step on `acc` between "sum complete" and "sum becomes state" — rescale/round/saturate |
| `104.2.00.000` | **INFERRED** | `acc ← x + d_out` (the all-pass sum) |
| `000.2.00.419`, `012.2.00.680` | **CONSTRAINED to a 2-permutation** | one is `d_in ← x + t`, the other `y ← d_out − t` |
| `880.1.60.*` / `880.1.20.*` | unchanged | DRAM read / write bracket; whether `.20` latches address or data is **UNKNOWN** and is what the motif's ordering turns on |
| `addr8 = 0x16` on class 8 | **UNKNOWN** | unchanged |

## 7. Corrections and cross-checks to earlier notes

| earlier claim | source | status here |
|---|---|---|
| "Direct Form I is REJECTED (needs 4 state updates; only 2 P-consumers exist)" | the brief, and biquad note §3 | **REFUTED.** DF-I is the answer; two of its four writes are folded into multiply instructions (`[1]`, `[7]`), so only two ever looked like stores (§3.3) |
| "Transposed DF-II fits the store count but leaves a residual" | the brief | **SUPERSEDED**: TDF-II cannot multiply five coefficients against four *different* cells, which is what the pointer walk measures |
| "the cell walk refuses every textbook form; only two of four cells are ever written" | biquad-map §7, cursor-general §5.3 | **RESOLVED** (§3.3). All four are written; two of the writes are inside class-A words |
| "`[7]` reads `S2`, the same cell `[3]` read" | biquad-map §7 | **CORRECTED**: `[7]`'s operand is the **accumulator**; its `addr8 = 0xFF` is pure pointer arithmetic and its `S2` access is a **write**, not a read (**DETERMINED**, §3.1) |
| the sixth multiply is the section's output make-up gain (INFERRED, strong) | biquad-map §3 | **UPGRADED to forced**: it is the only assignment in 19.7 M that works, and it multiplies the accumulator (§3.1) |
| the circular-buffer reading of the four cells is "the more attractive hypothesis" | cursor-general §5.3 | **FALSIFIED**: the cells are a fixed `x1 x2 v1 v2`, shifted explicitly by two latch-stores |
| class 8 is "a rescale/round/saturate confined to filter outputs — SPECULATIVE" | biquad-map §6.2 | **CORROBORATED with a mechanism** (§3.3): it is the only slot between "sum complete" and "sum stored as state" |
| bit 23 "may select the multiplier operand rather than enable the multiplier" | class2-round2 §1.4 | **SUPPORTED**: `212.x.xx.412` with and without bit 23 = the same write, with and without a coefficient fetch — which is also why the cursor's bank-size test works |
| "no subtract is available — that is WHY `a1`, `a2` are stored negated" | the brief | **CORRECTED (§5.2)**: the negated storage is a *convention* that keeps the biquad a pure MAC chain. The reverb's all-pass needs `d_out − t`, so the ALU **must** subtract |
| `PARAMETRIC EQ` bands 2–5 are exactly flat at power-on | biquad-map §4 | **CONFIRMED from the code**: `h = [−2, 0, 0, 0]` over 64 samples (§4) |

## 8. Falsified, or explicitly not established

* **Direct Form I is rejected** — **FALSIFIED** (§3.3).
* **The four state cells are a circular buffer** — **FALSIFIED** (§3.3).
* **`[7]` reads state cell `S2`** — **FALSIFIED**; it writes it (§3.1).
* **"No subtract"** as a statement about the machine — **FALSIFIED** by the reverb (§5.2).
* **Which of `[0]`/`[1]`, `[2]`/`[8]`, `[4]`/`[5]` performs each write.** Constrained to
  2 each; two of the three are broken only by the *encoding* argument of §3.2, which is
  INFERRED, not measured.
* **Whether the sum starts by `SET-P` at `[1]` or by a zeroed accumulator.**
* **What class 8 actually computes**, and `addr8 = 0x16`.
* **Which of `000.2.00.419` / `012.2.00.680` is the add and which the subtract.**
* **The reverb motif's ordering** — the multiply sits after the DRAM close. Either
  `880.1.20.*` latches the write *address* and the data follows from DATA BUF, or the
  stages are pipelined. **NOT ESTABLISHED**, and it is the one place where the reverb
  reading is incomplete.
* **Everything outside the two specifications**: the `COND` field, `BRAKST`, LC1–LC3, the
  header's control words, the compressor's four non-class-A coefficient consumers,
  `MULTI TAP DELAY`'s −4. None of this work touches them.

## 9. What additional observable would close the gap

Ranked by what each would settle and by how cheaply it can be had.

1. **`AUTO WAH`'s `204.2.FE.687 / 804.8.16.1DA / 000.2.FF.647` — already in the corpus,
   costs nothing.** It places the two P-consumers `0x687` and `0x647` adjacent **with no
   multiply between them** (biquad-map §6.2). If they were merely "accumulate the pending
   product", the second would add the same product twice, which no sane code generator
   emits; if they are **latch-stores that also accumulate**, the sequence is exactly a
   two-cell state shuffle with no arithmetic. **Decoding that one triple would break the
   `[5]`/`[8]` write ambiguity from inside the existing data.** This is the single
   cheapest next experiment in the file.
2. **A read-back of the state space during one sample.** Four words per band, in the
   `000.1.NN.000` space, sampled between instructions, would settle all four residual
   choices at once and would confirm `S0 S1 S2 S3 = x1 x2 v1 v2` directly. The host
   interface writes that space (proven, parameters note §2); whether it can *read* it is
   the open question, and it is worth asking of the sub-CPU disassembly before anything
   else.
3. **A PC / single-step trace**, i.e. `BRAKST` and the emulator-mode pins. This is what
   the datasheet hunt was for and it remains the only thing that would settle the
   pipeline question in §5.2 and the whole of the `COND` field.
4. **The phaser, inverted numerically.** Its all-pass triple `102.2.c.1CD / 212.2.01.412 /
   104.2.s.1D5` with `c + s == 0xFF` (class2-round2 §1.4) is a *second*, internal-RAM
   all-pass with a **static** coefficient bank. Under §5.2's reading it must realise the
   same one-multiplier identity in internal RAM, and its gains must be realisable
   all-pass gains — a sharp, cheap falsifier of the whole §5 reading, and one this note
   did not run.
5. **The `80A.8.16.000` and `804.8.16.1DA` section families** (biquad-map §9). Both are
   filter sections of a different shape; the method of §2–§3 applies unchanged and would
   give two more decoded sections, and any of them that turns out to be a *different*
   topology would test whether the DF-I reading is the machine's idiom or one program's.
