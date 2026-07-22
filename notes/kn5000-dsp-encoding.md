# NEC uPD6383GF — instruction encoding: what the microcode corpus proves

KN5000 IC311 effects DSP. Companion to `notes/kn5000-dsp-coefficients.md` (owned by a
different investigation — this file deliberately does not touch coefficients except
where they falsify a hypothesis about the code).

Tool: `tools/kn5000_dsp_encoding.py` (reuses `tools/kn5000_dsp_extract.py`).
Corpus: the 100-entry `ALGO_TABLE` at `0x0001ED7C` in
`kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom`.

Every claim below is tagged **MEASURED**, **INFERRED** or **SPECULATIVE**. Nothing in
the "field map" section is a decoded instruction; we do not have one yet, and saying
otherwise would poison later work.

---

## 0. Notation

The 36-bit word is written field-aligned in four groups, which is how
`kn5000_dsp_encoding.fmt36()` renders it:

```
    hi12 . c4 . addr8 . lo12
   [35:24] [23:20] [19:12] [11:0]
```

so the raw 5-byte record `08 80 13 00 0B` (printed elsewhere as `088013000B`) is the
36-bit word `0x88013000B` = **`880.1.30.00B`**.

⚠ A trap that cost time here: `%010X` prints a 36-bit word as **ten** nibbles, not
nine. The leading nibble is padding. Earlier hand-analysis in this project that read
"`0880`" as the top field was off by one nibble.

## 0b. Corpus hygiene (MEASURED)

96 of 100 `ALGO_TABLE` pointers yield I-RAM blocks, but **algo 79 and algo 88 parse to
load addresses 1520 and 3376** — outside the 384-word I-RAM. Their pointers do not lead
to a valid bytecode stream (their words, e.g. `8002030080`, `409001A34E`, are unlike
anything else in the corpus and would have skewed every statistic). All numbers below
**exclude them**: 91 programs, **38 distinct images**, 2974 words, 688 distinct words.

The previously published statistics (573-word live capture: "bits [35:33] take all 8
values, 0:211 5:124 4:98…") are not repeated here; they were taken over a different and
smaller sample and are superseded by the 2974-word static corpus.

---

## 1. What the CDJ-500 block diagram (page 1-15) constrains

Read directly off the diagram, plus the pin table on 1-16/1-17. **MEASURED** (it is a
published document) as to what blocks exist; **INFERRED** as to the encoding budget.

Datapath, one 24-bit internal data bus (**IDB**) tying everything together:

* **I-RAM 384×36** feeding **PC** through a block explicitly labelled **DEC** (decoder).
  A decoder sitting between I-RAM and the datapath is the diagram's own statement that
  this is *not* raw horizontal control — the 36 bits are decoded, not fanned straight
  out to control lines. But 36 bits into a decoder that must also carry an operand
  address is a *compact-but-wide* word: expect several small independent fields rather
  than one opcode plus operands.
* **MPLY 24×24** with two input latches **K** and **L**, product register **P**,
  feeding a **44-bit ALU** with **ACCA/ACCB**, a **SHIFTER** on each side and **OVC**
  (overflow control) blocks on both the input and output paths.
* **C-RAM 256×24** and **D-RAM 256×24**, both on the IDB. Pointers **CP**, **DP**,
  **BP1**, **BP2**, **PR1**, **PR2** and a bank register **BNK-R** address them.
* **UCPC**, **PC**, **STACK1**, **STACK2**, **STA-R**, **CNT-R**, loop counters
  **LC1–LC3**, timers/registers **TR0–TR3**, **SMD**, **PDPS**, **M**.
* External DRAM controller for the digital delay: **OFP**, **OF-RAM ADDR.R**,
  **DATA BUF**, RAS/CAS/WE, **A0–A16** (17 address bits ⇒ up to 128K words) and
  **I/O1–16** (16-bit external samples, i.e. the delay memory is 16-bit while the core
  is 24-bit).
* Serial audio **DI1–DI3** in / **DO1–DO3** out, each with L and R latches
  (`DI1L-R/DI1R-R` … `DO3L-R/DO3R-R`) — 6 in, 6 out at 24 bits.
* Host: µC-IF (parallel or serial, `P/S` pin 89), **EI-R/EO-R/STS-R**, flags
  **GF1–GF3** ("can be set, reset and toggled **by instructions**", pin 83–85) and
  **RQ1–RQ3** ("controlled from the host CPU, and can be **verified by the COND field
  in instructions**", pin 86–88).
* **BRAKST** is named in the pin table (pin 12 `BR-AK`: "reset by the BRAKST
  instruction") — one confirmed mnemonic, an emulator-mode break acknowledge.

**Field budget, INFERRED.** The two data RAMs are 256 deep ⇒ 8-bit addresses. Two
explicit RAM addresses would eat 16 of 36 bits and leave 20 for an ALU op, a multiplier
op, shifter control, accumulator select, a COND field and pointer updates. That is
tight. The presence of six dedicated address *pointers* (CP/DP/BP1/BP2/PR1/PR2) is the
usual architectural answer: **one explicit address in the word, the other operand
reached through a pointer register**. So the prediction going in was: exactly **one**
8-bit address field, plus a pointer/bank selector, plus dense control. Section 4
confirms exactly one wide field of exactly 8 bits.

The COND field is documented to exist and to test RQ1–RQ3; therefore conditional
execution is per-instruction and its encoding is somewhere in the word. We have not
located it (see §7).

---

## 2. The high-bits opcode hypothesis is REFUTED

**Hypothesis under test:** bits [35:33] or [35:32] are a global opcode field.

**Test 1 — pairwise mutual information over all 36 bits (MEASURED).** A global opcode
field must be statistically coupled to most of the rest of the word: knowing the opcode
must constrain what the operand fields can be. Measured over the 688 distinct words,
the MI matrix is **block-diagonal with small, weakly-coupled blocks**. Essentially all
of the 630 bit pairs are below MI = 0.05. The strongest couplings are all *local*:

```
  b7–b8  0.556   b17–b19 0.523   b6–b7  0.458   b16–b17 0.428
  b6–b8  0.389   b16–b19 0.351   b0–b2  0.350   b8–b10  0.294
  b4–b23 0.250   b20–b21 0.228   b21–b35 0.192  b25–b28 0.163
```

Bit 35 has MI ≥ 0.1 with **exactly two** other bits (b21 = 0.19, b20 = 0.16) and
< 0.05 with the other 33. A global opcode bit cannot look like that. Same for b34
(max MI 0.09), b33 (max 0.14), b32 (max 0.11).

**Test 2 — partition quality (MEASURED).** For each candidate field, group the corpus
by its value and measure how much *more* constant the remaining 36−w bits become inside
each group than they are corpus-wide (sum over bits of purity gain). A real opcode
scores high. Sweeping every width-2..6 field at every position:

```
   [7:2]   32 vals  score 2.228   purifies bits 0,1,8,10,23,25
   [13:8]  28 vals  score 2.068   purifies bits 0,1,2,6,7,25
   [6:2]   20 vals  score 2.027
   [23:18] 19 vals  score 1.961
   ...
   [35:32] 11 vals  score 0.961   <- the hypothesised opcode field, mid-table
   [35:33]  8 vals  score ~0.8
```

The best-scoring fields are in the **low** half of the word, not the high half. The
high-bit fields are unremarkable.

**Verdict (MEASURED): the high bits of the uPD6383GF instruction word are not a global
opcode field.** The earlier suggestive statistic (bits [35:33] taking all 8 values with
a skewed distribution) is real but is just the marginal distribution of a sparse control
region; it is not evidence of an opcode. This does not mean the high bits are
meaningless — see §3, where the top 12 bits are shown to be a highly structured control
region using only 1.3% of their value space.

**INFERRED consequence:** the word is closer to **horizontal/VLIW microcode with several
independent control fields** than to a compact opcode+operand instruction, tempered by
the DEC block on the diagram. There is no single field you can read to say "this is a
MAC and that is a branch".

---

## 3. Field-value-space census — where the structure actually is (MEASURED)

Over the 2974-word corpus:

| field | name | distinct values | of space | coverage | H |
|---|---|---|---|---|---|
| [35:24] | hi12 | 54 | 4096 | **1.3 %** | 3.98 |
| [23:20] | class4 | 9 | 16 | 56.2 % | 1.88 |
| [19:12] | addr8 | **122** | 256 | **47.7 %** | 4.22 |
| [11:0] | lo12 | 57 | 4096 | **1.4 %** | 4.34 |

This is the single most informative table in this document.

* `hi12` and `lo12` each use **~1.4 % of their value space**. They are *not* immediates
  or addresses; they are sparse, enumerated control encodings — exactly what you get
  when several small independent fields are packed side by side and only a handful of
  legal combinations are ever emitted by a code generator.
* `addr8` uses **half of 0..255** and is the only field in the word that does. Its
  neighbours are hemmed in by low-entropy bits: bit 11 is set in only 3.8 % of words,
  and bit 20 in 11.8 %, while bits 12–19 all sit between 20 % and 31 %.
* Sliding an 8-bit window across the word, coverage peaks **exactly** at [19:12]
  (47.7 %) and falls off symmetrically ([15:8] 32.8 %, [17:10] 41.8 %, [20:13] 30.1 %,
  [11:4] 10.5 %). A window that straddles a field boundary always covers less than one
  that is aligned to it. The peak locates the field.

**Per-bit entropy (MEASURED), high→low**, for anyone re-deriving this:
```
b35 14.4%  b34  4.7%  b33 27.1%  b32 18.0%  b31 19.6%  b30  5.2%
b29  6.4%  b28 22.3%  b27  4.8%  b26 11.8%  b25 46.4%  b24  2.4%
b23 29.2%  b22  4.8%  b21 78.8%  b20 11.8%  b19 20.4%  b18 24.7%
b17 30.8%  b16 24.2%  b15 23.9%  b14 21.4%  b13 24.0%  b12 28.6%
b11  3.8%  b10 39.5%  b9  16.5%  b8  33.1%  b7  40.2%  b6  47.5%
b5   3.7%  b4  33.2%  b3  24.6%  b2  55.1%  b1  32.3%  b0  54.9%
```
Bits 24, 5, 11, 22, 34, 27 are near-dead (< 5 % set) — plausible field padding or
rarely-used mode bits. Bit 21 is set 78.8 % of the time.

---

## 4. `addr8` = [19:12] is a RAM address field — the decisive minimal pair (MEASURED)

Algorithms **32** and **34** are two 42-word images that differ in **exactly four
words**, and in those four words they differ in **nothing but bits [19:12]**:

```
  w 6  092.2.F9.700   vs  092.2.86.700    addr8 -115
  w 8  182.2.07.000   vs  182.2.7A.000    addr8 +115
  w16  000.2.F0.40E   vs  000.2.7D.40E    addr8 -115
  w17  212.2.10.000   vs  212.2.83.000    addr8 +115
```

All four deltas are **exactly ±115 (0x73) modulo 256**, two negative and two positive.
Four independent 8-bit values in the same program, all moved by the same magnitude, in
two matched signed pairs, with **every other bit of all four instructions unchanged**.

* **MEASURED:** bits [19:12] form a single 8-bit field that varies independently of the
  rest of the word, and the two algorithm variants differ only in that field's value.
* **INFERRED:** it is a memory address or pointer offset. An 8-bit field wrapping mod
  256 matches the 256×24 C-RAM/D-RAM exactly.
* **SPECULATIVE:** the ±115 pattern in matched pairs looks like two delay lines whose
  read and write ends were both moved — i.e. these two algorithm slots are the same
  effect at two different delay times. Nothing here proves that; it is the natural
  reading, not a demonstration.

Supporting statistic (MEASURED): the number of distinct `addr8` values a program uses
correlates with **program length**, r = **0.632** (n = 96), but barely with the number
of coefficients that program uploads, r = **0.135**. So `addr8` is a general operand
address that scales with how much code there is — it is **not** primarily a
coefficient index into C-RAM. (Coefficient counts taken from `PARAM_TABLE` at
`0x0001EF0C`, 11–38 coefficients per algorithm.)

A second, weaker minimal pair: algos {15,53} vs 67 (86 words, 79 differ, so mostly a
different program) nevertheless contains two clean `addr8`-only diffs, `0x40→0x3C`
(−4) and `0xBE→0xC1` (+3).

---

## 5. `class4` = [23:20] partitions the ISA (MEASURED)

Grouping the corpus by [23:20] — 9 of 16 values used — gives a partition with real
explanatory power, because it predicts **whether the `addr8` field is used at all**:

```
 [23:20]    n   hi12 vals  addr8 vals  lo12 vals   top hi12 classes
    2    1550      27        105          28       000:564 212:223 104:127 102:120
    A     822      24         72          21       202:234 000:192 212:129 102:70
    1     322      13          7          18       880:231 900:35  C40:12  428:12
    0     101       7          1           8       040:53  A00:35  142:7
    6      53       1          5           2       000:53
    4      53       1          1           1       012:53
    8      42       2          1           3       804:39  80A:3
    3      30       1          2           2       C40:30
    5       1       1          1           1       C40:1
```

* Classes **2** and **A** are 80 % of all code and are the only ones where `addr8`
  ranges widely (105 and 72 distinct values). **INFERRED: these are the
  memory-referencing datapath instructions.** They differ only in bit 23.
* Class **1** (322 words) uses only **7** distinct `addr8` values across 322
  instructions — the field is being used as a small enumerated selector, not an address.
  This class contains *every* program's first word and *every* program's last word
  (§6). **INFERRED: class 1 is the non-memory / control / I-O family.**
* Classes 0,3,4,6,8 are small and each is dominated by a single `hi12` value — they look
  like individual special instructions rather than families.

**This is as close to an "opcode field" as the corpus supports, and it is at [23:20],
not in the high bits.** It is only 4 bits and only 9 values, so it cannot be the whole
operation selector; `hi12` and `lo12` clearly carry more. MI(hi12,lo12) = 1.96 bits
against H(hi12) = 3.98 and H(lo12) = 4.34 — the two control regions are strongly
coupled to each other, which is what you expect if the *operation* is spread across
both of them rather than living in one contiguous opcode.

---

## 6. Structural landmarks

### 6.1 The end-of-program word — a perfect landmark (MEASURED)

**Signature: `class4 == 1` and `addr8 ∈ {0x0E, 0x0F}`.**

* Present as the **final word of 91 of 91 programs**.
* Occurs **0 times** anywhere else in the 2974-word corpus.

100 % recall, 100 % precision. The eleven observed final words:

```
  400.1.0E.000   400.1.0E.407   420.1.0E.000   424.1.0E.000   428.1.0E.000
  42C.1.0E.000   504.1.0E.407   602.1.0E.000   604.1.0E.000   612.1.0E.000
  612.1.0F.000
```

`class4`, `addr8` and `lo12` are essentially fixed; all the variation is in `hi12`
(9 values: 400,420,424,428,42C,504,602,604,612 — note bits 34,33 and 31,30,29,28,27,26
carrying it, with bits 35 and 24 always 0).

**INFERRED:** this is the per-sample loop terminator — an unconditional branch back to
the frame start, or a "wait for next sample" / end-of-frame instruction. Every program
is a once-per-sample loop, so exactly one such word per program is required and the
data matches that requirement exactly.

**SPECULATIVE:** the varying `hi12` bits are a good candidate for the **GF1–GF3**
set/reset/toggle encoding — the diagram says GF flags are manipulated by instructions,
and signalling "frame done" to the host at the end of the loop is the obvious use. The
bits are grouped as if two or three independent 2-bit set/reset/toggle sub-encodings
(`4x` vs `6x` vs `5x` in the top nibble-pair). **Not demonstrated.**

### 6.2 The entry idiom (MEASURED)

81 of 91 programs begin with a `hi12 == 0x880`, `class4 == 1` word; 83 of 91 have one as
their **second-to-last** word too. The entire `hi12 == 0x880` family (231 words) uses
only three `addr8` values — `0x20`, `0x30`, `0x60` — and 21 distinct full words:

```
  880.1.30.00B  880.1.30.8BC  880.1.30.000  880.1.30.407  880.1.30.447  880.1.30.647
  880.1.20.2C7  880.1.20.2D5  880.1.20.2D9  880.1.20.40B  880.1.20.64B  880.1.20.655
  880.1.60.00B  880.1.60.000  880.1.60.02D9 880.1.60.2D4  880.1.60.40B  880.1.60.40E
  880.1.60.41A  880.1.60.447
```

**INFERRED:** class-1 / `hi12=0x880` is a framing instruction family that brackets the
per-sample loop: three variants (`addr8` 0x20/0x30/0x60) selecting *something*
three-valued, with `lo12` carrying a sub-operand. **SPECULATIVE:** given the diagram's
three serial inputs DI1–DI3 and three outputs DO1–DO3, a three-valued selector on the
instruction that opens and closes a sample loop is very suggestive of **audio I/O
port select**. Untested.

### 6.3 The 60-word common header at I-RAM 0..59

Not present in this corpus. Every one of the 91 valid streams writes a **single** I-RAM
block at word 84 or 200. The 0..59 header and the 60..82 algorithm-change stub are
uploaded by a different code path (Sub CPU init, not `ALGO_TABLE`) and would have to be
captured at runtime or located separately in the ROM. **This is the biggest missing
piece of the corpus** — the header is the code that is guaranteed to contain the
loop control (LC1–LC3), the host handshake and the DRAM-delay setup.

### 6.4 Loop control / BRAKST

**Not located.** No candidate has been identified for LC1–LC3 loop instructions or for
BRAKST. That is consistent with §6.3: a per-sample effect body is straight-line code;
the loop machinery lives in the missing common header.

---

## 7. Relocation test: inconclusive, but one observation

Only **one** distinct image loads at I-RAM 200 (the 133-word program shared by algos
16–27); all other 37 distinct images load at 84. No image appears at both addresses, so
the clean "same bytes at two addresses" test cannot be run.

The one falsifiable observation (MEASURED): the 200-loaded program's terminator is
`612.1.**0F**.000` where every 84-loaded program's terminator is `xxx.1.**0E**.000` —
the `addr8` field differs by **+1**, not by 200 − 84 = **+116**.

**INFERRED, n = 1:** whatever `addr8` selects in the terminator is a per-unit resource
index (unit 0 → 0x0E, unit 1 → 0x0F), not a relocated program-counter target. If the
last instruction were a branch back to the program's own start with an absolute target,
we would expect +116. We do not see it.

**Caveat:** with a single program at address 200 this is one data point, and `addr8` is
only 8 bits while I-RAM is 384 words deep — an absolute I-RAM target could not fit in
`addr8` anyway, so this test never had much power. A stronger version needs a runtime
capture of the same effect loaded into both units.

---

## 8. Field map — what can be defended

```
   35                    24 23  20 19        12 11                     0
  +------------------------+------+------------+------------------------+
  |         hi12           |class4|   addr8    |          lo12          |
  +------------------------+------+------------+------------------------+
```

| field | status | evidence |
|---|---|---|
| **[19:12] `addr8`** — an 8-bit operand address / pointer value | **INFERRED, strong** | only field with wide value coverage (122/256); peak of the sliding-window coverage curve; the algo-32/34 minimal pair varies it and nothing else, by ±115 mod 256; r = 0.63 with program length; matches 256-deep C-RAM/D-RAM |
| **[23:20] `class4`** — an instruction-class field | **INFERRED, moderate** | 9/16 values; cleanly separates memory-referencing code (classes 2,A: 80 % of words, `addr8` wide) from control/framing code (class 1: `addr8` reduced to 7 values) |
| **[35:24] `hi12`**, **[11:0] `lo12`** — sparse control regions, several sub-fields each | **MEASURED as sparse; decomposition UNKNOWN** | 54/4096 and 57/4096 values used; MI(hi12,lo12) = 1.96 bits so the operation is spread across both |
| terminator = `class4==1 && addr8∈{0E,0F}` | **MEASURED** | 91/91 final words, 0 false positives |
| entry idiom = `hi12==0x880 && class4==1` | **MEASURED** | 81/91 first words, 83/91 penultimate words |
| bits 24, 5, 11, 22, 34, 27 near-dead | **MEASURED** | < 5 % set each |
| high bits are a global opcode | **REFUTED** | §2 |
| `addr8` is a coefficient index | **REFUTED** | r = 0.135 with coefficient count vs r = 0.632 with program length |

**No instruction is decoded.** Not one. We can say where the operand address lives and
we can find the end of a program with certainty, and that is the honest extent of it.
Statistical structure is not semantics: knowing that [19:12] is an address does not tell
us *which* RAM it addresses, whether it is direct or a pointer offset, or what the
instruction does with the value.

---

## 9. Falsified along the way

* **"Bits [35:33]/[35:32] are the opcode."** Refuted in §2 by two independent tests.
  The suggestive marginal distribution was a red herring.
* **"`addr8` indexes uploaded coefficients."** Refuted in §4 by the correlation split.
* **"96 algorithms are usable data."** Two of them (79, 88) are malformed and were
  quietly skewing the earlier bit statistics.
* **"The last word relocates when the program moves to I-RAM 200."** Not supported; the
  observed delta is +1, and `addr8` is too narrow to hold an I-RAM address anyway (§7).

---

## 10. The single most promising next experiment

**Capture the 60-word common header at I-RAM 0..59 and the 23-word stub at 60..82.**

Everything this analysis could not find — LC1–LC3 loop control, BRAKST, the COND field
testing RQ1–RQ3, the GF flag manipulation, the external-DRAM delay setup, the host
handshake — is by construction *not* in the per-effect bodies, because those are
straight-line per-sample code. It is in the scaffolding, and the scaffolding is the one
part of the program that is uploaded by a code path we have not traced.

Concretely: find the Sub CPU routine that writes I-RAM block 0 (grep the disassembly
`kn5000_subprogram_v142.asm` for the bytecode emitter feeding opcode-3 records with an
I-RAM word address of 0 or 60, near the DSP bytecode interpreter at `0x03C2CB`), and
extract that stream the same way `kn5000_dsp_extract.py` walks `ALGO_TABLE`. 83 words of
scaffolding, containing the only control flow in the machine, is a far richer target
than another 38 straight-line effect bodies.

Second priority: a runtime capture of one effect loaded into **both** units, to settle
§7 properly.

---

## ADDENDUM (main agent, 2026-07-22): the common header is already captured

This note's closing recommendation is to go hunting in the Sub CPU for the emitter that writes
I-RAM 0..59, on the grounds that the header "is not in this corpus". Correct about the ROM
`ALGO_TABLE` corpus, but the header does not need to be hunted: **the live capture already has
it.** The `kn5000_dsp1` device records the uC-IF byte stream, and a cold boot uploads

  * I-RAM 0..59  — 60 words, the common header, uploaded **three times, byte-identical**
  * I-RAM 60..82 — 23 words, the algorithm-change stub

Both are in `kn5000_dsp1_upload.txt` from any cold-boot run. No new instrumentation is required.

### The prediction holds, and strongly

Measured against the 841-word vocabulary of the 96 extracted effect bodies:

| block | words | distinct | **never seen in any effect body** |
|---|---|---|---|
| header @0   | 60 | 57 | **51 / 57  (89%)** |
| stub   @60  | 23 | 23 | **21 / 23  (91%)** |

So ~90% of the header's vocabulary is machinery that appears nowhere in the per-sample effect
code — exactly where this note predicts the loop control (LC1-LC3), `BRAKST`, the `COND` field,
the GF flag manipulation and the DRAM-delay setup must live, since the effect bodies are
straight-line code.

The `class4` field distributions differ accordingly. Header: `{0:8, 1:8, 2:16, 3:1, 4:2, 5:1,
6:1, 8:1, 9:1, 10:21}` over 60 words. Bodies: `{0:82, 1:37, 2:429, 3:4, 4:17, 5:4, 6:9, 7:4,
8:30, 9:9, 10:207, 14:9}` over 841. Class 2 dominates the bodies (51%) but is a minority in the
header (27%), while class 10 is proportionally far heavier in the header.

The terminator landmark also appears in the header, so the header self-terminates like a program.

### Terminator independently re-verified

`class4 == 1 && addr8 in {0x0E, 0x0F}` was re-checked against all 96 extracted images:
**91/96 end with it, and it occurs 0 times anywhere else in 7108 words.** The 5 misses are the
malformed streams this note already flags (loads outside the 384-word I-RAM). Confirmed.

### Revised next experiment

Skip the emitter hunt. Analyse the 83 header+stub words that are already on disk — they are a
small, high-value corpus containing the control-flow machinery the effect bodies lack, and 90% of
their vocabulary is unique to them.
