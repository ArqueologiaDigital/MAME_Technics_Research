# The ADVANCE pass — pushing the frame to the edge of what is proven, and finding the address generator switched off

NEC **uPD6383GF-3BA** (Technics SX-KN5000, IC311). Date: **2026-07-26**.
No hardware. Static analysis, the ROM corpus, constraint solving and the live
emulator only.

Labels used throughout: **MEASURED** / **PROVEN BY CONSTRUCTION** / **FORCED** /
**INFERRED** / **EDUCATED GUESS** / **OPEN**. Nothing here is a recording.

---

## 0. Result in one page

| # | what | label |
|---|---|---|
| **A** | ★ **A LIVE DEFECT, THE OPPOSITE POLARITY OF THE ONE THE ALU PASS CAUGHT.** The ALU pass found a word being *executed* on a superseded field. This pass found something *decoded* that was **not being executed**: the signed pointer post-increment and the coefficient cursor advance read **no part of `lo12`**, so they never needed the ALU decode — yet the core performed them only for the twelve whitelisted K6 words. The ~92 words that *did* execute were addressing D-RAM and C-RAM through a generator that had skipped every undecoded word's contribution. | **MEASURED** |
| **B** | The size of it: over the cold-boot frame the D-RAM pointer's net displacement was **−259** with only the executing words moving it and is **−135** with every word moving it; the coefficient cursor advanced **37** times instead of **73**. A decoded `mac (p),c+` late in the frame was reading a cell ~124 away from the right one and a coefficient ~36 cells early. | **MEASURED** |
| **C** | Words executing per frame **92 → 199 of 285**. But only **80 execute FULLY** (that number is unchanged): the other 119 have their *addressing* executed and their arithmetic is still unknown, and they count against the frame exactly like a trap. Words that execute **nothing at all**: 193 → **86**. | **MEASURED** |
| **D** | ★ **NO FRAME COMPLETES, and it was never going to.** 100 % of frames are still discarded. This is the expected outcome and it is stated plainly: 205 of 285 slots are still undecoded, spread over 123 distinct words. The useful product is §4, the ranked blocker list. | **MEASURED** |
| **E** | ★ **FRAME CLOSURE BECAME A REAL MEASUREMENT AND IMMEDIATELY FAILED.** The criterion is **FORCED**, not assumed. With the walk now complete the residue is **+121 on 1 130 880 of 1 130 880 complete frames**. Under the previous code it was measuring our coverage; now it measures the machine, and it says part of the model is wrong. Candidates enumerated in §3, none chosen. | **FORCED** (the criterion), **MEASURED** (the failure) |
| **F** | **The ALU is at its proven ceiling.** Every candidate relaxation was measured and priced (§2). None is proven, so none was applied — and the price list is the useful output, because it says which single unknown is worth the most slots. | **MEASURED** |
| **G** | Two **PREDICT-THEN-CHECK MISSES**, both reported: the "dead source" widening buys **0** words, and the action-`0x07` mode hole — the defect twin of the bit-4 guard — is **not** firing anywhere (303/303 of the executing `L=07` words are mode 2). The guard was added anyway, at zero cost. | **MEASURED** |
| **H** | Safety holds: **DSPCFG Off is BIT-IDENTICAL to the published pre-change binary** over a capture that can fail (1 033 679 non-zero samples, peak 21 894); On is bit-identical to Off; `-validate` clean, exit 0; the cap, the overrun guard and the wait-word termination all still fire; no hang; mirrors agree 3057/3057; `verify.py` BYTE-MATCH OK. | **MEASURED** |

---

## 1. ★ The address generator was switched off for 193 words of every frame

### 1.1 The argument

Two of this machine's addressing effects do not read `lo12` at all:

```
   ptr_postinc()     class4 & 7 == 2   ->  p += (s8)addr8      MEASURED
   coeff_consumer()  class4 == 0xA     ->  cursor++            FORCED (K4)
```

K6 already relied on exactly that to walk the input stage's pointer without
decoding its arithmetic. What was never re-examined is that the same reasoning
applies to **every** word: a word whose ALU is unknown still has a *known*
pointer delta and a *known* cursor effect, and the D-RAM pointer and the
coefficient cursor are **shared resources**. Skipping an undecoded word's
contribution does not leave the model neutral — it leaves every *decoded* word
downstream addressing the wrong cell.

So the restriction to twelve whitelisted words was not a safety property. It was
a defect, and of the same family as the one the ALU pass caught: a mismatch
between what the analyses had established and what the executor did with it.

### 1.2 The size of it — MEASURED

Cold-boot frame, 285 slots (60-word header → CHORUS body at 84 → header 50..59 →
133-word ROOM REVERB at 200 → 23-word epilogue → the wait word at I-RAM 82):

| quantity | only executing words act | **every word acts** |
|---|---|---|
| net D-RAM pointer displacement | **−259** | **−135** |
| coefficient-cursor advances | **37** | **73** |

Neither is a rounding error. A `mac (p),c+` in the epilogue was reading a D-RAM
cell ~124 away from the one the microcode meant and a coefficient ~36 cells
early. Every audio number this device could ever have produced was wrong at the
*address* level, before any arithmetic question was reached.

### 1.3 The line that is NOT crossed

`hi12` bit 4 — the accumulator store — is **deliberately not generalised**. It
writes the accumulator, and the accumulator of a frame in which 205 words did not
compute is not the chip's; performing it would put invented data into real cells.
It stays confined to the K6 twelve, where the note established which cells those
stores can reach (X+0, X+1, X+3, X+4, X+6, never the two input latches) and where
a per-frame audit re-checks the claim instead of asserting it.

**The rule, stated so it survives:** *execute what ADDRESSES, never what
COMPUTES.*

### 1.4 What it changed, live

`upd6383: FRAME REPORT`, DSPCFG On, 1 368 001 frames, cold boot + a 30 s playing
programme:

```
   last frame: 285 slots = 80 DECODED + 119 PARTIAL (addressing only) + 86 TRAP
```

| | before | after |
|---|---|---|
| words executing **something** | 92 | **199** of 285 |
| words executing **fully** (ALU too) | 80 | **80** — unchanged, and honestly so |
| words executing **nothing** | 193 | **86** |
| distinct `(class4, lo12)` pairs in the frame | 87 | 87 |
| ...with at least one DECODED occurrence | 15 | 15 |
| distinct 36-bit words still undecoded | 123 | 123 |
| frames completed | 0 | **0** |

**The fully-decoded count did not move, and that is the honest headline.** No new
semantics were guessed to make a number go up. What moved is the count of words
the device can do *anything* correct with, and the correctness of the ~80 that
were already executing.

The worklist now starts at I-RAM word 0, which it should always have done: the
first word of every frame is undecoded. `0 words fully DECODED before the first
undecoded one` is a more useful thing to read than the old figure, which excluded
the K6 twelve from the count by construction.

---

## 2. The ALU is at its proven ceiling — with a price list

The brief's question is "how far do the PROVEN semantics allow". The answer is
**not one word further**, and the way to make that answer useful is to price
every step that would go further. Each row is a relaxation of `alu_decoded()`,
measured over the cold-boot frame.

| relaxation | frame slots it would buy | status | why it was NOT applied |
|---|---|---|---|
| `L = 0x00` **and** `SRC = 0x00` both read as "default" | **37** | **OPEN** | `L=0x00` is the single most common action code in the corpus (824 words) and `SRC=0x00` the second most common source (615). `dsp-alu-structure.md` P-F explicitly **MISSED** on "`SRC=0x00` = no operand" (47/615 counter-examples). Nothing anchors either. |
| `L = 0x00` alone | 18 | OPEN | as above |
| `L = 0x19` = "capture into latch A" | **13** | **INFERRED, and internally contradicted** | `dsp-alu-structure.md` §9 gives two structural corroborations (SINGLE DELAY, the reverb all-pass core), both labelled *CONSISTENT, not FORCED*. Against it: the same note's `lo12[2:0]`-as-destination pattern puts latch A at `[2:0] == 3` and `0x19` has `[2:0] == 1`. A reading that fights the only other structure we have is not proven. |
| `HI_ACC_HOLD` (`hi12[3:1] == 2`) allowed off class 8 | 1 | **FORCED AGAINST** | the LFO's `094.A.dd.200` carries this code and *must* do something (the 2^23 wrap). "Unchanged" is right only where the biquad determines it. |
| `SRC = 0x00` alone | 1 | OPEN | as above |
| class 0 (mode 0) with anchored routing and no memory action | **0** | OPEN | costs nothing to refuse |
| the internal REGISTER FILE (mode 1, no escape) executed | 14 | space **MEASURED**, semantics OPEN | R2 §1.2 measured that mode 1 non-escape *is* a register file indexed by `addr8` (324/324, and the host writes the same space). What a word *does* with the register is not decoded: their `lo12` routes use codes `0x00`, `0x01`, `0x02`, `0x05`, `0x08` — all unanchored. |
| the external delay-DRAM family | **42** | address **PROVEN BY CONSTRUCTION**, direction **OPEN** | R3 proved the address is `DESCRIPTOR_CELL[cursor] + G` from the host bank behind pointer `…825`; the descriptor bank is never routed into any modelled memory, and R3 §6.3 **falsified** the `addr8` read/write rule. Two of the thirteen words have a FORCED direction; eleven do not. |

Two of these were tested as **PREDICT-THEN-CHECK** and both **MISSED** — recorded
because a miss is cheaper to publish than to rediscover:

* **the dead source.** Under the shipped model the bus operand `L` is consumed by
  exactly two things, an action in `{07,13,14}` and the class-A multiply. For a
  word whose action is `0x12`/`0x15` (DETERMINED: no side effect) and whose class
  is not A, the SOURCE code is therefore **dead** and the source guard does no
  work. Predicted: a useful widening. **MEASURED: 1029 → 1029 corpus words, 0
  frame slots.** Every word in this machine with an anchored action and an
  unanchored source is either class A or uses an operand-consuming action.
* **the action-`0x07` mode hole** — see §5.

---

## 3. ★ FRAME CLOSURE — a criterion that is FORCED, and that now fails

### 3.1 Why the criterion is forced, not assumed

The previous pass introduced the net D-RAM pointer displacement as a convergence
criterion and justified it by the host's absolute addressing of state — an
argument that rests on the mode-1 register file and the mode-2 D-RAM being one
256-cell RAM, which `isa-adjudication.md` §5.1 leaves **OPEN**.

There is a much stronger version that needs none of that. K6 **FORCED** that
exactly two D-RAM cells in the whole 3057-word machine are read and never
written, and that they are the audio input latches. The serial receivers write
them; **no instruction does**. So their addresses are a property of the *chip*,
fixed. The microcode reads them at `ptr+2` and `ptr+5`. For that to work on every
LRCK period, **the pointer at PC-restart must be identical every frame** —
therefore the net displacement over a frame is **0 (mod 256)**, full stop.

### 3.2 It fails, and by a fixed amount

```
   FRAME CLOSURE ... net displacement must be 0 mod 256:
       net D-RAM pointer displacement, last frame +121
       over every COMPLETE frame (1130880 of them): min -1  max +121
       frames that closed 960 of 1130880
```

The representative cold-boot frame's residue is **+121**, and the static walk
independently computes **−135 ≡ +121 (mod 256)** — PREDICT-THEN-CHECK, **HIT**,
to the unit. The 960 closing frames and the `−1` minimum are boot-time frames
that reach the wait word before the bodies have been uploaded; the statistic is
now restricted to frames that actually completed, because a frame that hit the
384-slot cap never finished its program and its residue measures nothing.

Per region (static, cold-boot frame):

```
   header  0..49      +8
   CHORUS body        -9        (enters at +6, leaves at -3)
   header 50..59      +2
   ROOM REVERB body   -133      (enters at -1, leaves at -134)
   epilogue           -1
   ------------------------
   net                -135  =  +121 (mod 256)
```

### 3.3 What is falsified — candidates ENUMERATED, none chosen

* **(P-1) SOME WORD RELOADS THE POINTER, and we do not decode it. FAVOURED.**
  Nothing loads the D-RAM operand pointer at all today: K3 withdrew `0x821` (it
  addresses C-RAM), and the adjudication **falsified** `0x827` at **0 of 85**
  streams. Under (P-1) "net == 0" is simply the wrong criterion — the right one is
  "the pointer at PC-restart is constant", which any absolute reload makes true
  automatically. The evidence that there is such a word: the header carries **five
  undecoded C-format words whose `lo12` is `0x820`** — the register-load selector
  `0x20`, whose register K3 lists as OPEN — at I-RAM **15, 22, 29, 31 and 40**,
  plus `801.0.6C.827` at 43 and `801.0.64.827` at 51.
  *Not pursued here*: the `A`/`B` split of the C-format immediate is FAMILY-LOCAL
  to `(hi12 & 0xFFE) == 0xC40` and **none of those five is in that family**, so
  their payload field is not established. Reading `addr8` as the payload gives
  `0x92, 0x12, 0x57, 0xB1, 0xC0`; reading `imm13 >> 5` gives `20, 24, 34, 37, 14`.
  Neither series lands the unit-0 body on `0x50` or the unit-1 body on `0xD0`, the
  two MEASURED state-block bases — so if one of them *is* the load, the payload
  field is a third thing. **OPEN, and the experiment is in §4.**
* **(P-2)** the post-increment rule is not `class4 & 7 == 2` everywhere. It is
  MEASURED, but predominantly on **body** words; the kernel is where it is least
  tested and the kernel is where the C-format and escape words cluster.
* **(P-3)** the CALL/RETURN sequencer (EDUCATED GUESS **G-5**) orders the frame
  wrongly, or enters a body the real machine skips. Note the disconnect vectors
  are **42/50**, not 84/200 — a disconnected unit runs its own setup block and
  returns, which is a *different* pointer walk.
* **(P-4)** some words are **CONDITIONAL**. The part has a COND field (CDJ-500
  block diagram) that nothing in this decode models. A conditional pointer move
  would make the residue signal-dependent — testable, see §4.

---

## 4. ★ THE RANKED BLOCKER LIST

Ranked by **frame slots occupied** in the cold-boot frame (285 slots, 205 of them
undecoded). `A` = the word's addressing is now executed and only its arithmetic
blocks the frame.

### #1 — `lo12[4:0]` ACTION codes that are not anchored — **61 slots, 31 distinct words** (all `A`)

*Where*: header 11, CHORUS 13, **REVERB 35**, epilogue 2.
*Fields*: class 2/8/A, source anchored, action ∈ `{00:51, 19:14, 0E:11, 0B:10, 0D:8, 08:6, 1A, 0C, 17}`.

Worst offenders, all in the reverb's eight-times-repeated all-pass core:

```
   000.2.00.419  x9   src=10 acc   act=19
   012.2.00.680  x9   src=1A tempB act=00   (carries hi12 bit 4)
   102.A.00.64B  x8   src=19 tempA act=0B   the gain multiply
   082.2.00.1C0  x5   src=07 mem   act=00
```

*What the neighbours imply*: R1's constraint solve FORCED that `102.A.**.64B`
takes a multiplicand that is a sum of two registers; `dsp-alu-structure.md` §9
offers the resolution R1 did not have — that the multiplicand is **one** register
(latch A) that an earlier word in the software pipeline already loaded with the
sum, which requires `L=0x19` to be "capture into latch A". That reading is
CONSISTENT in two independent programs and contradicted by the `lo12[2:0]`
destination pattern.

**Proposed experiment (static, cheap, decisive):** re-run
`dsp/tools/r1_allpass_solve.py` with the multiplicand **restricted to a single
register that also feeds the delay write**, exactly as §9 asks. If the survivor
set collapses and the two role assignments R1 could not separate become one,
`L=0x19` is anchored and 13 frame slots and the reverb's core motif open at once.
If it does not collapse, `L=0x19` is falsified and the `[2:0]` pattern wins.
**Either outcome is a result.**

### #2 — `lo12` BOTH halves unanchored — **42 slots, 29 distinct words** (all `A`)

*Where*: header 12, CHORUS 15, REVERB 14, epilogue 1.
Dominated by `104.2.00.000` ×9 (`src=00 act=00 f31=2`) and a family of `xxx.?.??.000`.

The single question behind both #1 and #2 is **what `SRC = 0x00` and `L = 0x00`
mean**. They are the two largest OPEN codes in the ISA (615 and 824 corpus words).
`dsp-alu-structure.md`'s best surviving reading for `SRC=0x00` is *the implicit /
default source, plausibly the coefficient itself* (`P = coef × 1`), which would
also explain the LFO's `092.A.00.200` "phase += increment".

**Proposed experiment (static):** the LFO is the one block whose *output* is known
numerically — `114/2^23 × 44100 = 0.5993 Hz`, and `dsp-alu-applied.md` §2.1
already checks the arithmetic. Solve for `SRC=0x00`'s value by requiring the LFO
words `092.A.00.200` / `094.A.00.200` to produce that ramp under each candidate
(`coef × 1`, `0`, `mem[ptr]`, the previous `L`). Only one should survive; the
constraint is numeric and tight.

### #3 — the external delay-DRAM family — **42 slots, 13 distinct words** (0 `A`)

*Where*: header 4, CHORUS 10, **REVERB 28**. Predicate: mode 1 **with** the format
escape, C-format-guarded.

```
   880.1.60.2D4  x9    880.1.20.655  x9    900.1.60.1D5  x4    880.1.20.2C7  x4
   880.1.20.2D5  x3    880.1.60.2DA  x3    880.1.20.64B  x3    800.1.60.00B  x2   (+5 more)
```

*Status*: the **address** is PROVEN BY CONSTRUCTION (`DESCRIPTOR_CELL[cursor] + G`,
one descriptor cell per DRAM word in program order, from the host bank behind
pointer `…825` / tag `0x4C`). The **direction** is OPEN — R3 §6.3 falsified the
`addr8` rule, and only `(0x60, 0x2D4)` = READ and `(0x20, 0x655)` = WRITE are
FORCED. This is the largest family whose *mechanism* is already understood, which
makes it the best value in the list.

**Proposed experiment (static, then live):** route the host's tag-`0x4C` packets
into a modelled descriptor bank (the uC-IF currently accepts-and-ignores every
command but `0x01`) and advance a descriptor cursor on every DRAM word. That
alone executes no arithmetic, but it makes R3's counting identity a **live**
check: the number of descriptor cells consumed per frame must equal the number
the host wrote, per program, and it can fail. Direction then follows from a
second constraint: a delay line must be read before it is written within a frame,
which orders the pairs.

### #4 — C-format immediate words — **18 slots, 12 distinct words** (0 `A`)

*Where*: header 8, CHORUS 4, REVERB 4, epilogue 2.

```
   C40.3.20.44C x4   C40.1.80.000 x4   C0A.0.E0.000   C0A.2.92.820   C04.3.12.820
   C42.4.57.820      C0A.4.B1.820      C4A.1.C0.820   C64.5.A2.000   C64.6.A2.007  (+2)
```

Five of these carry `lo12 = 0x820` — the **register-load selector `0x20`** — and
they are the strongest candidate for the missing D-RAM pointer load (§3.3 P-1).
The blocker is that the `A`/`B` payload split is **FAMILY-LOCAL** to
`(hi12 & 0xFFE) == 0xC40` (57/57 in, 2/11 out) and none of the five is in that
family.

**Proposed experiment (static, high value):** solve the payload field for this
sub-family from the closure constraint itself. Require that the frame's net
pointer displacement be 0 (mod 256) — the FORCED criterion of §3.1 — under each
candidate field extraction (`addr8`, `imm13>>5`, `imm13 & 0xFF`, `imm13>>4`, …)
and each candidate "which of the five is the last one to fire". The frame walk is
285 slots and the search space is small; there are 91 parameter streams to
cross-check against, and the answer must work for **all** of them. This is the
one experiment that could close §3 outright.

### #5 — the internal REGISTER FILE (mode 1, no escape) — **14 slots, 14 distinct words**

*Where*: header 4, epilogue **8**, one per body. The space is MEASURED (R2 §1.2:
324/324, and the host writes the same indices); `addr8` bit 7 is the effect UNIT
(K4/R2, five positional confirmations, no counter-example). Named cells: `0x06` /
`0x86` = the per-unit OUTPUT LEVELS (PROVEN BY CONSTRUCTION), `0x50` / `0xD0` =
the per-unit STATE-BLOCK BASE (MEASURED).

This family is **where the audio leaves the chip** — `w73`/`w78` present unit 0 to
DO1 and unit 1 to DO2 — so nothing audible can ever happen until it executes.
Blocker: the `lo12` routes here use `0x00, 0x01, 0x02, 0x05, 0x08` and one of the
six output-stage-only source codes that occur exactly once each in the whole
machine (`087 0C7 107 15B 19B 287`). A code that occurs once cannot be solved
from the corpus.

**Proposed experiment (LIVE, and it is the only one in this list that needs the
emulator):** the two output levels are known numbers — unit 0 `+0.500000`, unit 1
`+0.183992`, written by the host as the last two actions of cold boot. Model the
register file, execute the level reads, and check whether any candidate reading of
`w73`/`w78` produces an output that scales by exactly those factors when the host
changes them. The host *does* change them (every effect-parameter edit), so this
is a live, repeatable, falsifiable test with a known answer.

### #6 — other ESCAPE words (mode ≠ 1) — **13 slots, 10 distinct words**

`A00.0.00.041` ×4 (13 bodies carry it), `809.0.00.839`, `801.0.6C.827`,
`801.0.64.827`, `800.8.0C.000`, `980.5.20.402`, `E30.C.00.404`, `82E.8.0F.000`,
+2. `hi12` bit 11 selects the memory SPACE (R2 §1) and modes 4/5/C/D appear only
here. Four are the output stage's four bit-4 words — the machine's **only** words
carrying bit 4 outside the ordinary D-RAM/register modes.

### #7 — `lo12[10:6]` SOURCE unanchored, action anchored — **8 slots, 8 distinct words**

Sources `0x11` (×5 — the family that contains the call-vector words `445`/`446`,
DETERMINED destination, source field OPEN), `0x08` (LFO phase), `0x00`.

### #8–#11 — the small residue — **7 slots**

class 0 (`040.0.00.C63`, `142.0.00.C63`), class 6 (the table-lookup idiom
`000.6.18.4CD` + `000.6.20.407`), class 4 (`012.4.01.1CE` ×2), and one class-2
word with `hi12[3:1] == 2` off class 8 (`504.2.00.1D5`). Modes 0, 4 and 6 are
addressing modes whose *space* is unknown, so these cannot even have their
addressing executed.

### The list behind the list

If the question is "which single unknown unblocks the most", it is not a family —
it is a **code**:

```
   unanchored ACTION codes, by frame slots:  00:51  19:14  0E:11  0B:10  0D:8  08:6  ...
   unanchored SOURCE codes, by frame slots:  00:28  08:8   11:8   13:4   0B:1  1C:1
```

`L = 0x00` alone accounts for **51 of the 205 undecoded slots**, more than any
family in the ranking. It is also the single most common code in the ISA (824
corpus words) and is explicitly *not* "no action" (`dsp-alu-structure.md` §6:
it contains the LFO's phase accumulate, which certainly acts).

---

## 5. The defect twin — found, guarded, and it was NOT firing

R2 FORCED that `hi12` bit 4's destination is **mode-dependent**, and the previous
pass added a guard refusing bit-4 words off mode 2. Action `0x07` has exactly the
same property and was left open: `LO_ACT_ST_BUS` means *"write the operand to a
destination"*, and `2C7` on a mode-1 escape word is the external DELAY-RAM write
while the output stage's four `L=07` words write the register/port space.
`exec_alu()` writes `mem[ptr]` for it unconditionally — and **class 8 is mode 0**.

**PREDICT-THEN-CHECK:** predicted a live invented D-RAM write on class-8 `L=07`
words. **MISS.** MEASURED over the 3057-word corpus: of the **303** executing
`L=07` words, **303 are mode 2 and 0 are not**; 0 frame slots affected. The guard
was added anyway, for the same reason the bit-4 one was: it costs zero words and
closes a hole before it opens rather than after.

---

## 6. SAFETY

* **`-validate kn5000`**: clean, exit 0.
* **DSPCFG Off, published pre-change binary vs this build**: WAV **BIT-IDENTICAL**,
  8 208 050 bytes = 4 104 003 samples (3 ch × 1 368 001 frames @ 48 kHz), `cmp`
  clean.
  **The capture can fail**: 1 033 679 non-zero samples, peak 21 894. The programme
  is boot, a 4 s sustained C4, its release, a chromatic 12/12 across the middle
  octave and a held C-E-G chord, over ~28 s — deliberately inside the window in
  which this machine reliably sounds (the panel-goes-dead defect that
  `dsp-alu-applied.md` §9.1 documents bites later).
* **DSPCFG On vs Off, this build**: **BIT-IDENTICAL**. Every frame still traps, so
  every return is still discarded. Trapped frames contribute ZERO — unchanged.
* **The three terminations all still fire**: 1 130 880 frames ended on the wait
  word, 210 241 on the 384-slot cap, 26 880 on I-RAM overrun. MAME exited
  normally, exit 0. No hang, no leaked process.
* **The input-stage audit still passes and can still fail**: 1 141 440 frames in
  which both port reads executed, **0 mismatched**, **518 026** of them carrying a
  non-zero sample, peak `0x558600`. The pointer now moves differently (every word
  contributes), so this is a genuine re-test of the cell map, not a carried-over
  result.
* **Mirror agreement**: `tools/upd6383d_diff.sh` — **3057/3057 identical**.
* **Byte-match**: `dsp/verify.py` — **BYTE-MATCH OK**, kernel + epilogue + 91 valid
  algorithm streams, 38 distinct images. No `.dsm` needed regenerating: the only
  predicate change that can reach `text()` is the action-`0x07` guard, and it
  affects zero corpus words (§5).

---

## 7. PREDICT-THEN-CHECK log

| | prediction | result |
|---|---|---|
| **P-1** | executing every word's addressing moves 107 frame slots from TRAP to PARTIAL, giving 80 DECODED + 119 PARTIAL + 86 TRAP | **HIT, exactly.** Live: `285 slots = 80 DECODED + 119 PARTIAL + 86 TRAP` |
| **P-2** | the static frame walk's residue (−135 ≡ +121 mod 256) equals the live one | **HIT, to the unit.** Live `+121` |
| **P-3** | the action-`0x07` mode hole is already firing on live words | **MISS.** 303/303 of the executing `L=07` words are mode 2 |
| **P-4** | the "dead source" widening admits a useful number of words | **MISS.** 1029 → 1029 corpus, 0 frame slots |
| **P-5** | the input audit would break, because the pointer now walks differently | **MISS (good).** 0 mismatched of 1 141 440 — the offsets are relative, so the audit is invariant under the change. Worth recording because it *could* have gone the other way |
| **P-6** | with the closure statistic restricted to complete frames the residue is CONSTANT | **MISS.** min −1, max +121 — boot-time frames reach the wait word before the bodies are uploaded and have their own (shorter) walks. The fully-loaded frame is constant at +121 |

---

## 8. Reproducing

```
# the static frame walk (no emulator) -- replays the captured cold-boot uC-IF
# stream into a 384-word I-RAM image and walks one frame exactly as run_frame()
# does, using the Python mirror's predicates:
#     notes/data/kn5000_dsp1_upload_coldboot.txt  +  dsp/tools/dsp_disasm.py

# the live measurement:
cd kn7000-emulator
./kn7000 kn5000 -rompath ./roms -window -nomaximize -skip_gameinfo -log \
    -nvram_directory <scratch>/nvram -cfg_directory <scratch>/cfg \
    -autoboot_script <scratch>/audio.lua -wavwrite <scratch>/on.wav
#   ... with <scratch>/cfg/kn5000.cfg setting :DSPCFG value="1"
grep -A40 'FRAME REPORT' error.log

# the mirrors, and the byte match:
kn7000_mame/tools/upd6383d_diff.sh          # MIRRORS AGREE -- 3057/3057
cd kn5000-roms-disasm/dsp && python3 verify.py   # BYTE-MATCH OK
```
