# uPD6383GF — the field structure of `lo12`

**KN5000 IC311 (NEC uPD6383GF-3BA) effects DSP.  This note answers ONE question:
what are the SUB-FIELDS of `lo12`?**  It does *not* claim to have decoded the ALU.
It finds the boundaries, assigns meanings where an existing DETERMINED / FORCED
result anchors them, enumerates the alternatives where two readings survive, and
says explicitly which bits are still unexplained.

Everything here is reproduced by

```
python3 tools/kn5000_dsp_lo12.py            # all sections
python3 tools/kn5000_dsp_lo12.py checks     # just the predict-then-check
```

which reads the committed listings in `kn5000-roms-disasm/dsp/disasm/*.dsm`.
No number below is a remembered figure; if the tool disagrees with the note, the
tool is right.

> **Concurrency.** Nothing in `kn5000-roms-disasm/dsp/` is edited by this pass.
> §12 lists what should be synced into `dsp/instruction-set.md` and
> `dsp/tools/dsp_disasm.py` by whoever owns that tree.

---

## 0. The answer, up front

```
  11    10      6   5   4        0
 +---+-----------+---+------------+
 | G |    SRC    | R |     L      |
 +---+-----------+---+------------+
   |       |       |       |
   |       |       |       +--- lo12[4:0]  ACTION      (5 bits, 24 of 32 codes used)
   |       |       +----------- lo12[5]    REGISTER-WRITE MODE
   |       +------------------- lo12[10:6] SOURCE SELECT (5 bits, 18 of 32 used)
   +--------------------------- lo12[11]   register FILE / bank  (locked to R)
```

* `R` (**bit 5**) and `G` (**bit 11**) are **LOCKED**: 95 of the 96 words that
  carry one carry both.  They are not two independent flags in this corpus — they
  are a 2-bit **MODE** that takes only `00` (2904 words, *datapath*) and `11`
  (95 words, *register write*), plus `01` exactly **once** (`rstcur`).  `10` never
  occurs.  **MEASURED.**
* `SRC` = `lo12[10:6]` selects **which register / bus supplies the word's
  operand**.  **INFERRED**, anchored on three DETERMINED forms and one FORCED one.
* `L` = `lo12[4:0]` says **what is done with it**.  **INFERRED**, five codes
  anchored, nineteen open.
* In the register-write mode, `lo12[2:0]` names **which register** is loaded and
  `G` selects the **file** (coefficient side vs data side).  **PROVEN BY
  CONSTRUCTION for `lo12=0x821` (`ldptr`); VERIFIED for `0x021` (`rstcur`);
  INFERRED for the four siblings.**

### Independent convergence — and one disagreement

`notes/dsp-alu-crossval.md` (commit `8b3f8e7`, written concurrently and from a
different starting point — the all-pass motif, the LFO and the K6 input stage
rather than the vocabulary statistics) reaches the **same decomposition**: the
bit-11/bit-5 control pair marking the same 11-value pointer/cursor family, the
same boundary, `lo12[4:0]` as the ACTION half, and the same four operand sources.
Two analyses that share no method and no anchor set agreeing on the field map is
worth more than either of them alone, and its §8b already records the join from
the other side.

**One disagreement, and it is measurable.**  The in-flight `upd6383d.h` header
reads the operand field as **2 bits, `lo12[7:6]`** (`ACC/TA/TB/MEM`).  That is
the low 2 bits of the 5-bit field measured here, and for the eight values its
`alu_decoded()` whitelist covers the two readings agree exactly — so there is no
bug today.  But applied to the rest of the corpus the 2-bit reading **merges
roles this note can distinguish**:

| `lo12[7:6]` | merges (5-bit `SRC`, n) |
|---|---|
| `MEM` | `07` mem[ptr] **929**, `0B` delay-RAM **106**, `13` table **87**, `1B` 2, `03` 1 |
| `ACC` | `10` acc **702**, `00` none/implicit **615**, `08` LFO phase **83**, `1C` LFO out **46**, `04` 1 |
| `TA` | `19` latch A **139**, `11` vector-file **77**, `01` 36, `05` 1 |
| `TB` | `1A` latch B **76**, `06` 1, `02` 1, `0A` 1 |

The separations are not cosmetic: `SRC=0x0B` is **0 of 106** class A where
`SRC=0x07` is 372 of 929 (P-C), `SRC=0x13` is **87/87** exactly two forms (P-E),
and `SRC=0x1C` is **46/46** one `hi12` (P-D).  Reading them all as "MEM" or "ACC"
would make the delay-RAM operand indistinguishable from D-RAM and the LFO
indistinguishable from the accumulator.  **Recommendation: widen `lo_src()` to
`(w >> 6) & 0x1F` and keep the four anchored codes as named constants.**

The single most useful consequence: `lo12` is **not** an opcode.  Like `hi12` it
is a decomposable field, it is **orthogonal to `hi12`** (the biquad motif proves
it — §8), and it is **fixed by the dataflow role of the word**, not by the
instruction.

---

## 1. Corpus, and why it differs from the brief's

| corpus | words | distinct `lo12` | `(class4,lo12)` pairs |
|---|---|---|---|
| committed listings: kernel 60 + epilogue 23 + 38 bodies 2974 | **3057** | 82 | 123 |
| the brief's: the `?word` (undecoded) lines only | **2787** ("2788") | **80** | **121** |
| **this note's**: all listing words, minus the 57 `hi12&0xFFE==0xC40` C-format words | **3000** | **80** | 118 |

The vocabularies agree exactly at **80 values**.  The brief's counts are lower
only for `000` (538 vs 600), `1D5` (301 vs 435) and `407` (230 vs 265) — by
exactly the `nop` (62), `mac` (134) and `mulst` (35) line counts.  **The decoded
words are the semantic anchors of this whole analysis, so excluding them would
throw away the evidence**; this note keeps them.  The 121-vs-118 pair difference
is the C-format words, where `class4` is immediate data and not a class at all.
(MEASURED, `kn5000_dsp_lo12.py census`.)

---

## 2. `lo12` DECOMPOSES — the same test that established `hi12`

The 80-value vocabulary contains **55 Hamming-distance-1 pairs**.  A
popcount-matched null (500 draws of 80 values with the identical popcount
profile) gives **15.2 ± 3.7**.

```
z = +10.8
```

Every bit except bit 5 has between 3 and 8 Hamming-1 partners, spread over all
positions.  **MEASURED.**  An enumerated 12-bit opcode has no reason to look like
this; a bit-field does.  This is the same argument (and the same statistic) that
`notes/kn5000-dsp-hi12.md` used to establish that `hi12` is a horizontal
microword, so the two halves of the word are now known to be structured the same
way.

Per-bit Hamming-1 partner counts, most informative first:

| bit | pairs | the pairs (with occurrence counts) |
|---|---|---|
| 0 | 8 | `1D4/1D5`(42/435) `1C0/1C1` `412/413` `446/447` `2D4/2D5` `44C/44D` `820/821` |
| 9 | 7 | `000/200`(584/68) `447/647` `455/655` `0C7/2C7` `007/207` `44D/64D` `087/287` |
| 6 | 6 | `407/447`(265/52) `415/455` `412/452` `287/2C7` `695/6D5` `087/0C7` |
| 1 | 6 | `415/417` `445/447` `1D1/1D3` `820/822` `825/827` `1C1/1C3` |
| 7 | 5 | `655/6D5` `44D/4CD`(3/46) `448/4C8`(1/41) `007/087` `207/287` |
| 4 | 5 | `407/417` `402/412` `1C3/1D3` `445/455` `1C1/1D1` |
| 3 | 5 | `415/41D` `1C0/1C8` `412/41A` `680/688` `445/44D` |
| 2 | 5 | `1D1/1D5` `419/41D` `448/44C` `821/825` `413/417` |
| 10 | 4 | `007/407`(4/265) `287/687` `00B/40B` `2D5/6D5` |
| 8 | 3 | `007/107` `821/921` `05B/15B` |
| 11 | 1 | `021/821` |
| **5** | **0** | — |

**Bit 5 is the only bit that is never toggled alone.**  That is the first clue.

---

## 3. The bit-11 / bit-5 LOCK, and what the locked family is

| | values | occurrences |
|---|---|---|
| bit 11 set | 10 | 95 |
| bit 5 set | 11 | 96 |
| bit 11 **without** bit 5 | **0** | 0 |
| bit 5 **without** bit 11 | **1** (`0x021`) | **1** |

**MEASURED.**  And the 96-word family is *exactly* the vocabulary the ISA
reference already calls the register loads, with nothing else in it:

| `lo12` | n | what it is | status |
|---|---|---|---|
| `C63` | 53 | table-lookup idiom word 1 (`040.0.00.C63` / `142.0.00.C63`) | MEASURED landmark |
| `8BC` | 24 | `880.1.30.8BC` (DRAM framing) + `040.0.00.8BC` | MEASURED landmark |
| `820` | 5 | pointer-load sibling (only ever in C-format words) | INFERRED |
| `821` | 3 | `ldptr #$NN` | **PROVEN BY CONSTRUCTION** |
| `825` | 3 | pointer-load sibling | INFERRED |
| `827` | 2 | pointer-load sibling | INFERRED |
| `839` | 2 | `809.0.00.839` / `80B.0.00.839` | OPEN |
| `822` | 1 | pointer-load sibling (`859.0.86.822`, epilogue w77) | INFERRED |
| `864` | 1 | `040.0.00.864` | OPEN |
| `921` | 1 | `050.0.00.921` | OPEN |
| `021` | 1 | `rstcur` — reset the coefficient cursor | **VERIFIED** |

**Reading (INFERRED): `lo12[5]` = "this word writes an ADDRESS/INDEX REGISTER
instead of doing datapath work"; `lo12[11]` = which register FILE.**

The evidence for the `bit 11` half is one word — but it is a good one.
`801.0.NN.821` (`ldptr`) and `801.0.00.021` (`rstcur`) have **identical `hi12`,
identical `class4`, identical `lo12[10:0]`**, and differ *only* in bit 11.  One
loads the **data pointer** (D-RAM side); the other resets the **coefficient
cursor** (C-RAM side).  So bit 11 = the address-space / file select, and
`rstcur` is not a special instruction at all — it is `ldptr` aimed at the other
file with `addr8 = 0`.  **INFERRED, n = 1.**

A second, independent trace of the same boundary: `hi12` **bit 6** (which
`instruction-set.md` currently lists as "no reading") implies the family.  Over
every word with `hi12` bit 6 set and `hi12` bit 11 (ESC) clear, `lo12` bit 5 is
set **62 of 62**.  The remaining 34 members of the family all carry `hi12`
bit 11 (ESC) instead (`880`, `801`, `809`, `80B`, `859`, `C0A`, `C04`, `C42`,
`C4A`).  **MEASURED.**  So `hi12` bit 6 gets a first reading out of this:
*non-escape marker for the register-write form.*

### Prediction, and a MISS

> **P-A.** A register-write word does not also store the accumulator, so it
> should never carry `hi12` bit 4.

**MISS, 3 of 96.**  `859.0.86.822` (epilogue w77), `050.0.00.8BC`
(ENSEMBLE w1), `050.0.00.921` (MULTI TAP DELAY w33).  All three have
`hi12` bit 6 **and** bit 4.  Reported, not explained.  93/96 is not a rule.

---

## 4. Where the boundary is — the cut analysis

Restricted to the **2904 datapath words** (mode `00`), for each 2-way split of
`lo12`: how many codes each half actually uses, the occurrence-weighted mutual
information between the halves (a real field boundary has **low** MI), and
`H(class4 | high half)`.

| cut | #hi codes | of | #lo codes | of | **I (bits)** | H(class4 \| hi) |
|---|---|---|---|---|---|---|
| 1 | 62 | 2048 | 2 | 2 | 0.897 | 0.760 |
| 2 | 52 | 1024 | 4 | 4 | 1.650 | 0.802 |
| 3 | 38 | 512 | 8 | 8 | 1.952 | 0.869 |
| 4 | 27 | 256 | 15 | 16 | 1.979 | 0.955 |
| **5** | **18** | 128 | **24** | 32 | **1.327** | 1.238 |
| **6** | **18** | 64 | **24** | 64 | **1.327** | 1.238 |
| 7 | 11 | 32 | 37 | 128 | 1.787 | 1.318 |
| 8 | 6 | 16 | 47 | 256 | 1.781 | 1.475 |
| 9 | 4 | 8 | 56 | 512 | 1.374 | 1.583 |
| 10 | 2 | 4 | 65 | 1024 | 0.939 | 1.699 |

`H(class4)` unconditioned = 1.759.  Cuts 1 and 10 are degenerate (a 1-bit half
cannot carry much MI).  **Among the interior cuts, 5/6 is a clear minimum of the
mutual information (1.327 vs 1.78–1.98 either side), and it is the only cut where
BOTH halves are strongly constrained** — 18 of a possible 32 and 24 of a possible
32.  Cuts 5 and 6 give the same numbers because bit 5 is constant (0) inside the
datapath mode; taking bit 5 out as the mode flag makes the boundary land at
**bit 6**.  **MEASURED.**

Drawn as a grid (`lo12[11:6]` rows × `lo12[5:0]` columns), the lock is visible as
strict block structure: rows ≥ `0x20` occupy only columns ≥ `0x20`, never the
others, and vice versa.

---

## 5. `SRC = lo12[10:6]` — the operand-source select

18 of the 32 codes are used.  Conditional entropies over the 2904 datapath
words, `SRC` against the other 5-bit half `L = lo12[4:0]` (lower = knows more):

| target | H(target) | H( · \| SRC) | H( · \| L) |
|---|---|---|---|
| `class4` | 1.759 | 1.238 | **1.111** |
| `class4` bit 3 (cursor fetch) | 0.891 | 0.740 | **0.567** |
| `class4 & 7 == 2` (pointer inc) | 0.666 | **0.500** | 0.567 |
| `hi12` | 3.924 | **2.827** | 2.894 |
| `hi12` bit 11 (ESC) | 0.528 | **0.350** | 0.398 |
| `addr8 == 0` | 0.969 | 0.860 | **0.731** |

**Neither half dominates**, which is itself evidence that they are two real,
different fields rather than one field split at the wrong place: `SRC` knows more
about the *escape* and the *pointer class* (the addressing side), `L` knows more
about the *cursor fetch* and about `addr8` (the operation side).  Reported this
way because the first draft of this note claimed `SRC` was the best predictor
outright — it is not, and `L` beats it on three of the six targets.

| SRC | n | proposed meaning | status | evidence |
|---|---|---|---|---|
| `07` | 929 | **D-RAM `mem[ptr]`** | **anchored on DETERMINED** | `1D5` = `mac` and `1D4` = `mac.lb` both read `mem[p]`; the whole `1Cx/1Dx` group is the D-RAM operand group |
| `10` | 702 | **the accumulator** | **anchored on DETERMINED** | `407` = `mulst`, `P = coef × acc`; every other member (`415`, `412`, `419`, `40E`) sits where the biquad/all-pass operate on `acc` |
| `00` | 615 | none / implicit | INFERRED (weak — see P-F) | `000` (nop), `00B`, `007` |
| `19` | 139 | **latch A** | INFERRED | `647`, whose existing annotation is "P-consumer, **stores latch A**" |
| `0B` | 106 | **external delay-RAM data** | INFERRED, very strong | 99/106 sit on the `880.1.xx` delay-RAM word, and **0 of 106 are class A** — a delay-RAM word never fetches a coefficient |
| `13` | 87 | **table-lookup operand** | INFERRED, very strong | exactly two forms exist: class-6 `4CD` (the lookup) and class-A `4C8` (the multiply); 87/87 |
| `08` | 83 | LFO phase register | INFERRED | `092.A.00.200` phase accumulate, `094.A.00.200` wrap; 68/83 carry `hi12` `09x` (`092`/`094`/`09A`) |
| `1A` | 76 | **latch B** | INFERRED | `687`, annotated "P-consumer, **stores latch B**" |
| `11` | 77 | *the link / vector register file?* | OPEN | contains `445`/`446`, the two per-unit **CALL VECTOR** words (DETERMINED destination), plus `447`(52) `44C`(12) `455` `44D` `452` `448` |
| `1C` | 46 | LFO / modulation output | INFERRED, strong | one value only (`0x700`), and **46/46** occur with `hi12 = 0x092`, the LFO read |
| `01` | 36 | OPEN | OPEN | `041` with `hi12=0xA00`, class 0, in 13 bodies |
| `02`,`03`,`04`,`05`,`06`,`0A` | 1 each | **output-stage-only sources** | MEASURED (location), OPEN (meaning) | `087 0C7 107 15B 19B 287` occur **only** in the 23-word epilogue, one each — the shape of per-channel output-port selectors |
| `1B` | 2 | OPEN | OPEN | `6CE`, `6D5` |
| — | 96 | (register-write mode; `SRC` there is `00 01 02 04 11`) | | |

**Cumulative: 2783 of 2904 datapath words (95.8 %) carry a `SRC` code that has
some reading; 1631 (56.2 %) carry one anchored on a DETERMINED form.**

The strongest structural fact behind "SRC = operand source" is that the two
words the reverb's all-pass core uses to *move the same value* — the delay-RAM
write `880.1.20.655` and the gain multiply `102.A.00.64B` — carry **the same
`SRC` (`0x19`)** and differ only in `L`.  See §9.

### Predictions, checked

| | prediction | result |
|---|---|---|
| **P-B** | `SRC=0x0B` ⇒ a class-1 delay-RAM word | **MISS 7/106** — `020.2.00.2C7` ×6 (all in ENSEMBLE), `000.2.00.2D9` ×1 (kernel w25).  All seven sit *adjacent* to delay-RAM traffic: the `2C7` is followed by `002.2.xx.680` in 6/6 and then by `800.1.20.1D5` in 4/6; the `2D9` is immediately followed by `880.1.20.40B`.  So they are plausibly still delay-RAM operands on a word that is not itself the access — but the clean form of the claim is false. |
| **P-C** | `SRC=0x0B` is never class A (no coefficient fetch on a delay-RAM word) | **PASS 106/106** |
| **P-D** | `SRC=0x1C` occurs only with `hi12=0x092` | **PASS 46/46** |
| **P-E** | `SRC=0x13` has exactly two forms, `6.4CD` and `A.4C8` | **PASS 87/87** |
| **P-F** | `SRC=0x00` = "no operand", so never class A | **MISS 47/615** — `182.A.00.000` ×12, `192.A.4x.000` ×15, etc.  A class-A word with `lo12=0x000` *does* fetch a coefficient, so `SRC=0x00` is **not** "no source".  Best surviving reading: *the implicit/default source* (plausibly the coefficient itself, i.e. `P = coef × 1`), which would also explain `092.A.00.200` "phase += increment".  **OPEN.** |

---

## 6. `L = lo12[4:0]` — the action code

24 of 32 codes are used.  **Never used: `09 0A 0F 10 18 1C 1E 1F`.**

| L | n | proposed meaning | status | anchor |
|---|---|---|---|---|
| `15` | 707 | **`acc += P`** | INFERRED, anchored on DETERMINED | `202.A.dd.1D5` = `mac` |
| `07` | 455 | **write the `SRC` operand to a destination** | **INFERRED, strong** | one rule that replaces three separate annotations: `407`(SRC=acc)="`mem[p] ← acc`" (DETERMINED), `647`(SRC=latch A)="stores latch A", `687`(SRC=latch B)="stores latch B".  Also `2C7` = the delay-RAM write, and **all four of the output stage's `L=07` words** (`087 0C7 107 287`, one each, on four sources that occur nowhere else). |
| `14` | 58 | **`acc += P` and capture the operand into latch B** | INFERRED, anchored on DETERMINED | `202.A.dd.1D4` = `mac.lb`.  `hi12` bit 4 co-occurs **0 / 58** — a capture word never also stores. |
| `13` | 40 | capture the operand into latch A, `acc` untouched | INFERRED | `1D3`, biquad word 0 (`P = b1·S0 ; latch A ← S0`) |
| `12` | 85 | `acc ← P` (load, not accumulate) | INFERRED | `412`, biquad word 1 (`S0 ← x ; acc = P`).  **`hi12` bit 4 co-occurs 77/85 = 90.6 %** — by far the highest of any `L` code, i.e. this action nearly always comes with the accumulator store. |
| `19` | 89 | *capture the operand into latch A* | INFERRED (see §9) | SINGLE DELAY: `880.1.60.2D9` (read → ?) then `202.A.B8.655` (SRC=latch A) multiplies it; and `212.2.00.419` (SRC=acc) immediately before the delay-RAM write `880.1.20.64B` (SRC=latch A) |
| `00` | 824 | **OPEN** — *not* "no action" | OPEN | contains `000` (nop) but also `200` (LFO phase accumulate, which certainly acts) and `700`, `1C0`, `680` |
| `0D` | 203 | OPEN | | `1CD`(152) `4CD`(46) `44D` `64D` `20D` |
| `0E` | 227 | OPEN | | `1CE`(144) `40E`(82) `6CE` |
| `0B` | 82 | OPEN | | `64B`(44) `00B`(27) `40B`(10) `68B` |
| `08` | 52 | OPEN | | `4C8`(41) `1C8`(9) `448` `688` |
| `01 02 03 04 05 06 0C 11 16 17 1A 1B 1D` | 79 total | OPEN | | |

**1345 of 2904 datapath words (46.3 %) carry an `L` code whose reading is anchored
on a DETERMINED form.  Both fields have a reading on 1281 words (44.1 %).**

### Is `L` really two fields, `[4:3]` + `[2:0]`?  TESTED, NOT SUPPORTED

The eye says yes — `lo12[2:0]` looks like a destination selector, with four
anchors that all agree:

| `lo12[2:0]` | n | the anchors that land there |
|---|---|---|
| 3 | 126 | `1D3` → latch A |
| 4 | 73 | `1D4` = `mac.lb` → latch B |
| 5 | 913 | `1D5` = `mac` → accumulator |
| 7 | 456 | `407` = `mulst`, `647`, `687`, `2C7`, and the four output-stage port words → memory / port |
| 0 | 876 | `000` = nop → nothing |

and the **register-write mode uses `lo12[2:0]` exactly that way**: the shared
header loads three different pointer registers back-to-back at I-RAM 42–44 —
`801.0.70.821`, `801.0.6C.827`, `801.0.25.825` — i.e. destinations `1`, `7`, `5`,
and repeats the identical triple at 50–52 for unit 1.  Same three codes, three
distinct registers, MEASURED.

But the statistics do **not** support the split as an independent 2 + 3:

* `[4:3]` on its own predicts almost nothing (`H(class4 | [4:3]) = 1.407` vs
  1.759 unconditioned; `H(hi12 | [4:3]) = 3.488` vs 3.924).
* the `[4:3] × [2:0]` table is **strongly coupled**, not a product — 99.5 % of
  the mass is in 14 of its 32 cells (and 92 % in 8), and the marginals do not
  factor:

```
          D0    D1    D2    D3    D4    D5    D6    D7
   M=0   824    36     1     1     1     1     1   455
   M=1    52     0     0    82    14   203   227     0
   M=2     0     2    85    40    58   707     1     1
   M=3     0    89    18     3     0     2     0     0
```

**Two readings survive; ENUMERATED, not silently picked:**

* **L-1 (used above).** `lo12[4:0]` is ONE 5-bit action code.  Simpler, matches
  the statistics, and is what this note's tables use.
* **L-2.** `lo12[2:0]` = destination register (3 = latch A, 4 = latch B,
  5 = accumulator, 7 = memory/port, 0 = none) and `lo12[4:3]` = a mode that
  qualifies it.  Matches the four semantic anchors and the register-mode
  parallel, but leaves `[4:3]` with no reading and does not explain the coupling.

The discriminator would be a fifth anchor in a *different* `[4:3]` row with the
same `[2:0]`.  We do not have one.

---

## 7. The suggestive families the brief named — resolved into the decomposition

| family | what it actually is |
|---|---|
| `1C0 1CD 1CE 1D5` (+`1C1 1C3 1C8 1D1 1D3 1D4 1DA`) | **one `SRC` group**: `SRC = 0x07`, the D-RAM `mem[ptr]` operand.  They differ only in `L`: `00 01 03 08 0D 0E 11 13 14 15 1A`.  This is the largest single group in the corpus (929 words). |
| `407 40E 412 415` (+`402 404 40B 413 417 419 41A 41D`) | **one `SRC` group**: `SRC = 0x10`, the accumulator operand.  Same `L` alphabet: `02 04 07 0B 0E 12 13 15 17 19 1A 1D`.  702 words. |
| `447 44C 455 44D 452 445 446 448` | `SRC = 0x11` — the **same `L` alphabet again**, on an unidentified source.  `445`/`446` are the DETERMINED per-unit CALL VECTOR words, so this source is register-file-ish. |
| `4C8 4CD` | `SRC = 0x13`, the table lookup; `L = 08` and `0D`. |
| `647 64B 64D 655` | `SRC = 0x19` (latch A), `L = 07 0B 0D 15`. |
| `680 687 688 68B 692 695` | `SRC = 0x1A` (latch B), `L = 00 07 08 0B 12 15`. |
| `200 207 20C 20D 216 219 21A` | `SRC = 0x08` (LFO phase). |
| `2C7 2D4 2D5 2D9 2DA` | `SRC = 0x0B` (external delay-RAM). |
| `655` vs `1D5` vs `415` vs `455` vs `695` vs `2D5` vs `6D5` | **the same action `L = 0x15` on seven different sources.**  This is the cleanest single demonstration that the decomposition is real. |
| `C63` | not a datapath word at all — it is in the **register-write mode** (`lo12` bits 11 and 5 both set) and sits in the same family as `ldptr`.  "Loads the table base/index register" is an EDUCATED GUESS; what is MEASURED is only that it is a register write, which is already a change from calling it word 1 of a datapath idiom. |
| `000` | `SRC = 0x00`, `L = 0x00` — both fields at their default.  Not "no-op" in general (47 class-A occurrences). |

---

## 8. `lo12` is fixed by the DATAFLOW ROLE, and is orthogonal to `hi12`

The 9-word biquad section — the one program whose arithmetic is solved exactly —
occurs **34 times** across the corpus.  At every one of its nine slots the `lo12`
is **the same value in all 34 copies**, while `hi12` is **not**:

| slot | operation (from `algorithms/biquad-eq.md`) | `lo12` | SRC | L | `hi12` seen |
|---|---|---|---|---|---|
| w0 | `P = b1·S0 ; latch A ← S0` | `1D3` | 07 mem[p] | 13 latch A | **`000` ×27, `102` ×4, `212` ×2, `022` ×1** |
| w1 | `S0 ← x ; acc = P ; P = b0·x` | `412` | 10 acc | 12 acc←P | `212` ×34 |
| w2 | `acc += P ; P = b2·S1` | `1D5` | 07 | 15 acc+=P | `202` ×34 |
| w3 | `acc += P ; P = −a1·S2 ; latch B ← S2` | `1D4` | 07 | 14 acc+=P, →B | `202` ×34 |
| w4 | `acc += P ; P = −a2·S3` | `1D5` | 07 | 15 | `202` ×34 |
| w5 | `acc += P ; S3 ← latch B` | `687` | **1A latch B** | **07 store** | `102` ×34 |
| w6 | post-sum step (operation unknown) | `415` | 10 acc | 15 | `804` ×34 |
| w7 | `S2 ← acc ; P = makeup·acc` | `407` | 10 acc | 07 store | `212` ×34 |
| w8 | `acc ← P ; S1 ← latch A` | `647` | **19 latch A** | **07 store** | `000` ×33, `880` ×1 |

**MEASURED.**  Two things fall out:

1. **`hi12` and `lo12` are independent fields**, not two halves of one opcode:
   slot w0 carries **four** different `hi12` values with a constant `lo12`, and
   slot w8 two.
2. **w5 and w8 differ ONLY in `SRC`** — `0x1A` vs `0x19` — and their existing
   (independently arrived at, INFERRED) annotations differ *exactly* by which
   latch is stored.  Together with `407` (same `L=0x07`, `SRC=`accumulator,
   DETERMINED to store the accumulator), that is three sources × one action, and
   it collapses three separate hand-written annotations into one rule.

The reverb all-pass core repeats the result: **16 occurrences** in the committed
listings (9 in ROOM REVERB 1, 7 in GATED REVERB — the tree keeps one copy per
*distinct image*, where `r1-allpass-motif.md`'s 114 counts every preset stream),
5 of its 6 slots carrying a single `lo12` value in all 16; slot 2 is `000` ×15 /
`407` ×1.

---

## 9. A candidate resolution of R1's "sum of two registers"

`analysis/r1-allpass-motif.md` §9 FORCED that the all-pass multiply
`102.A.**.64B` takes a multiplicand that is **a sum of two registers**, which
neither `mem[p]` nor the incoming accumulator can supply, and concluded that
`0x64B` must therefore route "the word's own ALU result (2-input ALU) or a
pre-built `mem[p]` (3-input ALU)".

Under the `SRC` reading there is a **third possibility R1 did not have on the
table**: the multiplicand is *one* register — **latch A** — that an **earlier
word in the software pipeline already loaded with the sum**.  The six core slots
read:

```
  880.1.60.2D4   SRC=0B delay-RAM   L=14  ; and 2D4 shares L=14 with mac.lb (-> latch B)
  104.2.00.000   SRC=00             L=00
  000.2.00.419   SRC=10 accumulator L=19
  012.2.00.680   SRC=1A latch B     L=00  ; hi12 bit4 -> mem[ptr] <- acc (FORCED, before its own ALU step)
  880.1.20.655   SRC=19 latch A     L=15  ; the delay-RAM WRITE
  102.A.00.64B   SRC=19 latch A     L=0B  ; the gain multiply
```

**The delay-RAM write and the gain multiply take the SAME source.**  That is a
MEASURED fact about the encoding, and it is exactly the signature of the textbook
**one-multiplier Schroeder all-pass**

```
    v[n] = x[n] + g·v[n−D]          <-- the delay input IS the multiplicand
    y[n] = −g·v[n] + v[n−D]
```

in which `d_in` and the multiplicand are *the same value* `v`, held in one
register.  It is **not** the signature of the form written in
`algorithms/reverb.md` (`s = x + w ; t = g·s ; d_in = x + t ; y = w − t`), where
`d_in = x + t` and the multiplicand `s = x + w` are **different** values and would
need two different sources.

**Status: CONSISTENT, not FORCED.**  It rests on `SRC = 0x19` being one register
(INFERRED), and it is a *constraint*, not a decode.  It is worth acting on
because it is cheap to test: re-run `dsp/tools/r1_allpass_solve.py` with the
multiplicand restricted to a **single register that also feeds the delay write**
and see whether the survivor set collapses — and whether the two role assignments
that R1 could not separate become one.

The same shape appears in SINGLE DELAY (algo 9), which is the simplest instance
in the corpus and needs no pipelining argument:

```
  w5  880.1.60.2D9   SRC=0B delay-RAM  L=19        ; read the delay line
  w6  202.A.B8.655   SRC=19 latch A    L=15        ; acc += P ; P = fb x latch A
  w7  000.2.48.000
  w8  212.2.00.419   SRC=10 acc        L=19        ; hi12 bit4 store ; -> latch A
  w9  880.1.20.64B   SRC=19 latch A    L=0B        ; write the delay line
```

Read with `L=0x19` = "capture into latch A", that is `d_in = x + fb·d_out`, a
textbook feedback delay, with the delay-RAM read and the delay-RAM write both
passing through latch A.  **CONSISTENT.**

---

## 10. Alternatives tested and REJECTED

**`lo12` bit 0 = the external-DRAM direction.**  It looked excellent:
`addr8=0x20` (the FORCED WRITE) has bit 0 = 1 in **100/100** words, and the
FORCED read `2D4` and write `655` both agree.  **FALSIFIED** by SINGLE DELAY:
its one delay-line block is `880.1.60.2D9` (bit 0 = 1) followed by
`880.1.20.64B` (bit 0 = 1).  A delay line must *read*; two writes and no read is
impossible.  `addr8` 0x60/0x20 stands as the direction, as R1 forced.  (For the
record, `addr8=0x60` has bit 0 = 0 in only 49/75.)

**`lo12` as an enumerated opcode.**  Rejected by §2 (z = +10.8).

**A clean 2-way product split anywhere other than bit 6.**  Rejected by §4.

**`[4:3]` as an independent 2-bit field.**  Not supported; see §6.

---

## 11. The unexplained residue — bit by bit

| bit(s) | reading | status | what is missing |
|---|---|---|---|
| **11** | register FILE / bank select (C-RAM side vs D-RAM side) | INFERRED, **n = 1** | rests entirely on `021` vs `821`.  Needs a second minimal pair. |
| **10:6** (`SRC`) | operand-source select, 5 bits | INFERRED as a FIELD (MEASURED boundary) | **7 of the 18 used codes have no meaning at all**: `01` (36 words), `11` (77 — the biggest unexplained source, and it holds the CALL VECTOR registers), `02 03 04 05 06 0A` (1 each, epilogue-only), `1B` (2).  The 14 unused codes are unexplained by construction. `00` (615 words) has a reading that FAILED its test (P-F). |
| **5** | register-write mode enable | INFERRED, strong | why it is *duplicated* by bit 11 at all.  3 of its 96 words also carry `hi12` bit 4 (P-A miss). |
| **4** | — | **UNEXPLAINED** | it is a genuine bit (5 Hamming-1 partners, e.g. `402/412`, `1C3/1D3`), but no reading separates its two sides.  Under L-2 it is half of the `[4:3]` mode. |
| **3** | — | **UNEXPLAINED** | same: 5 Hamming-1 partners (`415/41D`, `1C0/1C8`, `412/41A`), no reading. |
| **2:0** | destination-register select (L-2) *or* part of one 5-bit action code (L-1) | INFERRED, two readings ENUMERATED | four anchors (3 = latch A, 4 = latch B, 5 = accumulator, 7 = memory/port).  Code **6** (229 words: `1CE` ×144, `40E` ×82) has no reading at all.  Codes **1** and **2** have readings that *contradict* L-2: `L=0x19` (code 1) reads as "→ latch A", which code 3 already is, and `L=0x12` (code 2) reads as "`acc ← P`", which code 5 already is.  Under L-2 that means either `[4:3]` changes the destination map, or L-2 is wrong.  **OPEN — and this is the sharpest open question in the low field.** |

Put as coverage of the *field structure* rather than of the *meaning*:

* the **boundaries** are MEASURED (§2–§4);
* **95.8 %** of datapath words carry a `SRC` with some reading; **56.2 %** carry
  one anchored on a DETERMINED form;
* only **46.3 %** carry an `L` with an anchored reading, and the single largest
  `L` code (`0x00`, 824 words) is OPEN;
* **44.1 %** of datapath words have a reading for *both* halves.

**So: the field structure of `lo12` is solved to the boundary level and about
half-solved at the code level.  This is not enough to execute the ALU.**  What
would be enough is decoding the `L` codes `00`, `0D`, `0E`, `0B`, `08` (1388
words between them, 48 % of the datapath) — every one of which appears at a
*known* slot of the biquad or the all-pass core, where the required arithmetic is
already written down.  That is the next task, and it is a much smaller search
than the one this note started with.

---

## 12. To sync into `kn5000-roms-disasm/dsp/` (not edited by this pass)

1. `instruction-set.md` — `lo12` is a decomposable field, z = +10.8 (mirror of
   the `hi12` result); the bit-11/bit-5 MODE; the `SRC`/`L` boundary at bit 6.
2. `instruction-set.md` — the `hi12` bit-6 reading (62/62 implies the
   register-write family); it is currently listed as "no reading".
3. `tools/dsp_disasm.py` — the three separate INFERRED annotations for `0x407`,
   `0x647` and `0x687` should become ONE rule keyed on `L = lo12[4:0] == 0x07`
   with the stored register named by `SRC`; likewise `0x1D3`/`0x1D4` keyed on
   `L = 0x13`/`0x14`.  Render `lo12` as `SRC/L` the way `hi12` is rendered as
   flags + residue, so an undecoded word still shows its structure.
4. `analysis/r1-allpass-motif.md` §9 — add the third possibility for `0x64B`'s
   multiplicand (a single register that also feeds the delay write) and re-run
   `r1_allpass_solve.py` under it; note that `880.1.20.655` and `102.A.00.64B`
   share `SRC`, which is a new constraint the solver did not have.
5. `algorithms/reverb.md` — flag that the `s = x + w / d_in = x + t` form is in
   tension with the shared `SRC`, and that the Schroeder `v = x + g·v[n−D]` form
   is not.
6. `analysis/k5-output-stage.md` — the epilogue is the *only* place `SRC` codes
   `02 03 04 05 06 0A` occur, one word each; that is a structural handle on the
   output stage nobody has used yet.
7. `src/devices/cpu/upd6383/upd6383d.h` (this tree, currently in flight) — widen
   `lo_src()` from `(w>>6)&3` to `(w>>6)&0x1F`; see §0's convergence table for
   what the 2-bit form merges.

---

## 13. What is NOT claimed

* No ALU operation is decoded.  Nothing here lets the MAME core execute one more
  word than it does today, and no core change is made by this pass.
* `SRC` = "operand source" is **INFERRED**.  It is anchored on DETERMINED forms
  at two codes and near-certain at three more, and it survived **three of the five**
  falsification attempts aimed at it (P-C, P-D, P-E pass; P-B and P-F MISS).
  The two misses are reported, not explained away.
* The `latch A` / `latch B` identities for `SRC` `0x19` / `0x1A` inherit the
  status of the annotations they rest on, which is **INFERRED**, not measured.
* The `lo12[11]` = file-select reading rests on **one** minimal pair.
* §9 is a *constraint on the reverb*, offered so it can be tested.  It is not a
  claim that R1 was wrong: R1's own result (that the multiplicand is not
  `mem[p]` and not the incoming accumulator) is untouched — only the inference
  that it must therefore be an in-word sum.
