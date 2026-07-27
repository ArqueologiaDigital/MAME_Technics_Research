# ADJUDICATE AND APPLY — the comb stands, its two corollaries do not

NEC **uPD6383GF-3BA** (Technics SX-KN5000, IC311). Date: **2026-07-27**.
No hardware. Static analysis, the ROM corpus, constraint solving and the live
emulator only.

Labels: **MEASURED** / **PROVEN BY CONSTRUCTION** / **FORCED** / **CONSISTENT** /
**INFERRED** / **EDUCATED GUESS** / **FALSIFIED** / **OPEN**.

Inputs adjudicated:
`dsp/analysis/schroeder-topology.md` (TARGET 1 — the reverb core is a comb),
`dsp/analysis/action00-discriminator.md` (TARGET 2 — `ACTION 0x00` is not forced),
`dsp/analysis/dark-words.md` (TARGET 3 — the 86 words that execute nothing).
Derivation: `dsp/analysis/blocking-read.md`.

---

## 0. Result in one page

| # | statement | label |
|---|---|---|
| **A** | ★★★ **THE `SRC 0x00` CONTRADICTION IS DISSOLVED, AND THE SHARED ASSUMPTION WAS PRINTED IN THE TABLE ALL ALONG.** `action-field.md` §8 lists two rows of reverb-vs-SINGLE-DELAY disagreement: `SRC 0x00` (`DR` 52 696/52 696 vs 0 of 5 145) **and the read latency** (`land ∈ {0,1}` vs `land = −1`, a **BLOCKING** read, FORCED 5 145/5 145). The second causes the first. `action_search` enumerates `LANDS = (0,1,2,7,8)` and **omits the blocking read**, so inside the reverb's space the fresh delay sample had exactly one route to the ALU — `SRC 0x00 = DR`. Restore it and the reverb reaches slot 3 through the read word's **own anchored ACTION `0x14` (`tempB ← bus`)**: **3 206** comb machines survive (published 112) with `SRC 0x00` at **six** values, and **2 310** in the sequential model with `SRC 0x00` **perfectly uniform, 385 each**. | **MEASURED** |
| **B** | ★★★ **TWO OF TARGET 1'S HEADLINE RESULTS ARE WITHDRAWN, AND THE THIRD SURVIVES.** `SRC 0x00 = DR` FORCED and `ACTION 0x19 = tB ← bus` FORCED are artefacts of the omitted read model. ★★ **And its conditional FALSIFICATION of the strict vocabulary is itself FALSIFIED**: with the blocking read `ACTION 0x19`'s accumulator half comes out **FORCED to "no effect"** (3 206/3 206 strict, 2 310/2 310 sequential) and `tA ← bus` has 13 855 survivors in the joint row where it had 0. **The comb topology itself stands and is broadened** — 0 all-pass matches in every row. | **FORCED** / **FALSIFIED** |
| **C** | ★★ **THE CODE CHANGE IS LABELS, AND THAT IS THE HONEST OUTCOME.** Walked item by item, the three passes contain **nothing FORCED that the core does not already implement**, and one thing it implements with a **wrong label**. `ACTION 0x00 = load` is relabelled **FORCED → CONSISTENT** in both mirrors (`instruction-set.md` already carried TARGET 2's banner; `upd6383d.h` and `dsp_disasm.py` did not). `ACTION 0x19 = tempA ← bus` keeps its FORCED label because the challenge to it is withdrawn. **No word gains or loses an executable semantic.** | **adjudicated** |
| **D** | ★ **RE-MEASURED, AND NOTHING MOVED — AS PREDICTED.** 1 344 001 frames: 285 slots = **108 DECODED + 91 PARTIAL + 86 TRAP**, 122 distinct undecoded words, terminations 1 106 880 / 210 241 / 26 880, input-stage audit 0 MISMATCHED — the whole frame report is **byte-identical** to the pre-change run (`diff` clean). Coverage table unchanged to the digit. | **MEASURED** |
| **E** | ★ **THE CLOSURE RESIDUE STAYS +0.** Last frame **+0**; **1 080 959 of 1 106 880** complete frames close; min −1 / max +116; X = `0xFF` on 97.58 %. A regression here would have been serious; there is none. | **MEASURED** |
| **F** | ★ **NO FRAME COMPLETES. 1 344 001 of 1 344 001 still trap** and every return is discarded, so the audible output is exactly the dry tone generator and there is no reverb tail to look for. 177 of 285 slots are undecoded. The deliverable is §5, the ranked blocker list. | **MEASURED** |
| **G** | ★★ **A DEGENERATE PARAMETER IN BOTH PUBLISHED SPACES.** `land = 0` and `land = 1` are the **same machine** — `exec_rep` makes both first visible at slot 1 — so "read lands +n: 2 values, CONSISTENT" was one machine counted twice. 4 000/4 000 symbolically identical; every published split is exactly 50/50. The comparison is shown able to say *different* (`land 0` vs `2`: 290/300; vs `−1`: 264/300). | **PROVEN BY CONSTRUCTION** |
| **H** | ★★ **A THIRD CROSS-BLOCK TENSION, ENUMERATED IN EVERY RUN SINCE TARGET 1 AND NEVER PRINTED.** The comb search's `tbsh` (the tempB `>>1`) is **FORCED to 0 in every STRICT row** — 112/112 in TARGET 1's *own published* row — while the biquad forces the shift (77 dB). Stated at its real strength: only a **92.1 %** majority in the joint row, so it is a tension inside a hypothesis. Recorded in `exec_alu()` with three enumerated candidate resolutions; **not acted on**. | **MEASURED**, **OPEN** |
| **I** | ★ **A TOP-RANKED LEAD OF TARGET 3, TESTED AND FALSIFIED IN ONE PASS.** `dark-words.md` §4.5 proposed that pointer register `0x827` is the delay-descriptor cursor base — "the highest possible payoff per unit of work in the dark set", 42 slots from 2 — and named the test: does an affine map take its payloads `{0x6C, 0x64}` to R3 candidate (iii)'s per-unit bases `{0x26, 0x00}`? **No map in the declared family does, in either orientation**, and the reason is arithmetic rather than a search: the payload difference is **8** and the target difference **38**, ratio **4.75**. The family is shown able to hit reachable targets. | **FALSIFIED** |
| **J** | **Safety holds.** DSPCFG **Off** is **bit-identical** to the published build over a capture that carries real audio and can fail (1 276 567 non-zero samples, peak 22 268); **On** is bit-identical to Off, so trapped frames still contribute **zero**; `-validate kn5000` exit 0 and **silent**; cap / overrun / wait-word terminations fire with identical counts; mirrors agree **3057/3057** on text *and* the three execution predicates; `dsp/verify.py` **BYTE-MATCH OK**; no `.dsm` regenerated. | **MEASURED** |

---

## 1. The adjudication

### 1.1 The three conflicts, and how each was settled by re-deriving from the ROM

| conflict | TARGET 1 says | TARGET 2 says | TARGET 3 says | settled |
|---|---|---|---|---|
| **`SRC 0x00`** | `DR`, FORCED in every row; "contradiction #2 **reinstated**, the highest-value experiment on this chip" | never `DR` (0 of 5 832); the reverb's demand is a condition of a **refuted** premise | not `DR` — H-DIR + R3 §6.3 agree only under `mem[ptr]`/`acc` (4/4) | ★ **the reverb is INDIFFERENT.** Not a contradiction at all once the read model matches |
| **`ACTION 0x19`** | `tB ← bus` FORCED (strict); `tA ← acc` + a bus route FORCED (joint) ⇒ the strict vocabulary is FALSIFIED | `tempA ← bus`, FORCED 108/108 | — | ★★ **TARGET 2. `0x19`'s accumulator half is FORCED to "no effect" under the blocking read** — the falsification is itself falsified |
| **`ACTION 0x00`** | `load` FORCED given the bit-4 clear | not FORCED — 33 survivors, load 15 / add 12 / rload 6, locked to the store gate | — | ★ **TARGET 2**, and TARGET 1's own support weakens: 896 of 3 206 (adder) and **absent** among the 2 310 sequential survivors |

**The shared assumption, in one sentence:** *two blocks were being solved under
different DRAM read models, and the block whose read model could not deliver the
fetched word to the read word's own bus is the block that "required" a second
route for it.*

That is the same shape as the adder adjudication — both sides right about the
answer, wrong about the mechanism — and it was reached the same way, by taking
the contradiction seriously enough to look at what the two searches did *not*
share rather than at what they concluded.

### 1.2 The route, from the ROM, with no search

```
   slot 0 880.1.60.2D4  ESC src=0B dram-rd  act=14 -> tempB <- bus   ANCHORED
   slot 3 012.2.00.680      src=1A tempB    act=00                   reads tempB
```

`dark-words.md` §10.3 named this ACTION `0x14` and asked that any nested-comb
model satisfy both halves of the read/write pair. Nothing had used it, because
with a *pipelined* read the read word's bus carries the previous repetition's
word and the capture is useless. Under a blocking read it carries `w[r]`.
Symbolically, with **`SRC 0x00 = zero`**:

```
   MULTIPLICAND = P+N        write value = P+N        (P = t[r-1], N = w[r])
   exit tA=Q tB=N acc=Q DR=N
   delay-loop filter -> ['bus', 'acc_before', 'acc_after', 'M']
```

— the **identical** comb stage TARGET 1 published, with `SRC 0x00` reading
nothing.

★ **And the same mechanism is visible in the block that forced the blocking read
in the first place.** SINGLE DELAY's own five words, printed by the tool:

```
   880.1.60.2D9  ESC src=0B dram-rd  act=19   <- the DRAM READ carries ACTION 0x19
   202.A.B8.655      src=19 tempA    act=15   <- and the NEXT word multiplies tempA
   000.2.48.000      src=00 (OPEN)   act=00   <- x arrives HERE, not the delayed sample
   212.2.00.419      src=10 acc      act=19 ST
   880.1.20.64B  ESC src=19 tempA    act=0B   <- the DRAM WRITE
```

**Both blocks put the fetched sample into a temp register with the read word's own
ACTION and consume it in the following word** — `0x14`/tempB in the reverb,
`0x19`/tempA in SINGLE DELAY. That is why SINGLE DELAY forces the blocking read,
and it is a structural argument, not a numeric one. It also explains why SINGLE
DELAY's `SRC 0x00` is `mem[ptr]`: that word is where *x* arrives, not the delay.

### 1.3 What that leaves to apply — nothing executable

| pass | forced item | already in the core? |
|---|---|---|
| T1 | the reverb core is a **comb**, not an all-pass | a **negative** about a hypothesis; nothing to apply |
| T1 | `SRC 0x00 = DR`, `ACTION 0x19 = tB ← bus`, "the strict vocabulary is falsified" | ★ **WITHDRAWN by this pass** — nothing to apply, and nothing to un-apply |
| T1 | `ACTION 0x00 = load` given the clear | already ships; **the LABEL is wrong** |
| T2 | `sttime = before`, `ACTION 0x19 = tempA ← bus`, `op2 = hold` | **yes**, all three |
| T2 | `ACTION 0x00` is **CONSISTENT, not FORCED**; relabel it | ★ **the change** (comments, both mirrors) |
| T2 | `SRC 0x00 ∈ {mem[ptr], acc}` | **two values ⇒ keeps trapping.** Nothing applied |
| T3 | the dark-set boundary theorem; no dark word has modelled addressing | a property of predicates the core already has |
| T3 | the descriptor cursor has no consumer in the model | already stated at `upd6383.cpp:1019` |
| T3 | the published blocker list is not a partition (41 → 42; buckets sum 179 vs 177) | ★ **corrected in `dsp-closure-applied.md` §5** |
| T3 | H-DIR (SRC `0x0B` ⇔ READ) | **CONSISTENT 4/4, not FORCED** ⇒ not applied |

---

## 2. What was applied, precisely

`src/devices/cpu/upd6383/upd6383d.h`, `upd6383.cpp`,
`kn5000-roms-disasm/dsp/tools/dsp_disasm.py`,
`kn5000-roms-disasm/dsp/tools/r1_allpass_solve.py`,
`notes/dsp-closure-applied.md`, plus three analysis notes.
**Every edit to the two device files and to `dsp_disasm.py` is a comment.**

1. `LO_ACT_ACC_BUS` (`0x00`): the accumulator **adder** stays FORCED; **which
   half `0x00` selects is relabelled CONSISTENT**, with the census that broke the
   18/18 (SINGLE DELAY and the biquad are blind by construction) and the
   `act00`↔store-gate coupling. `load` still ships and the comment says why.
2. `LO_ACT_CAP_TA2` (`0x19`): keeps **FORCED**; the comment records TARGET 1's
   challenge and its withdrawal, with the numbers on both sides.
3. `LO_SRC_TB`: the reverb's `tbsh = 0` recorded against the biquad's `>>1`, with
   three enumerated candidate resolutions and the statement that the shift stays.
4. `action_search()` gains an explicit `lands=` parameter so the read model is
   chosen at the call site instead of inherited; `schroeder2` gains rows 8/9/10;
   a new section `blockread` carries the argument and four controls.
5. `dsp-closure-applied.md` §5 gains a correction banner (T3 item E).

**Not applied, deliberately:** `SRC 0x00` (two values); `ACTION 0x00`'s capture
half (`tA ← acc`, forced 3 206/3 206 **inside a topology hypothesis, in one
block** — method rule 2); `tbsh = 0` (contradicts a MEASURED reconstruction);
H-DIR (CONSISTENT, not forced); the delay-DRAM family (two open unknowns).

---

## 3. ★ THE RE-MEASUREMENT

Live, `DSPCFG On`, cold boot + the same 28 s keybed programme and the same
pre-init nvram as the previous pass. `kn7000-emulator/nvram` was not touched.

| | before | after |
|---|---|---|
| words executing **something** | 199 of 285 | **199** of 285 |
| words executing **FULLY** | 108 | **108** |
| words executing **nothing** | 86 | **86** |
| distinct undecoded words over the run | 122 | **122** |
| ended on wait word / CAP / OVERRUN | 1 106 880 / 210 241 / 26 880 | **identical** |
| **frames completed** | 0 of 1 344 001 | **0 of 1 344 001** |
| ★ **closure residue, last frame** | **+0** | ★ **+0** |
| ★ **complete frames that CLOSED** | 1 080 959 of 1 106 880 | **1 080 959 of 1 106 880** |
| residue min / max | −1 / +116 | **−1 / +116** |
| frame-entry pointer X | `0xFF` on 97.58 % | **identical** |
| input-stage audit | 1 117 440 both-reads, 0 MISMATCHED | **identical**, 638 678 non-zero, peak `0x56FC00` |

`diff` of the two 32-line frame reports is **empty**. This was the prediction —
the pass changes comments — and it is measured rather than assumed, because a
build that silently changed behaviour would show here.

### 3.1 Coverage — unchanged to the digit

```
  region                         words   tier1   tier1%    tier2    t1+t2%
  resident kernel I-RAM 0..82       83      14    16.9%       17     37.3%
     ...header  I-RAM  0..59        60      12    20.0%       14     43.3%
     ...output stage 60..82         23       2     8.7%        3     21.7%
     ...output stage AS LINKED      23       4    17.4%        1     21.7%
  reverb image (algo 16)           133      69    51.9%       32     75.9%
  FRAME FLOOR kernel + reverb      216      83    38.4%       49     61.1%
  FRAME FLOOR as linked            216      85    39.4%       47     61.1%
  all 38 distinct body images     2974    1234    41.5%      329     52.6%

  images with ZERO tier-1 words: 0 of 38
  distinct undecoded words   : 443      distinct undecoded FAMILIES: 133
```

### 3.2 Does any frame complete? **NO.**

0 of 1 344 001, 100.00 % trapped. The audible output is exactly the dry tone
generator; there is no tail to inspect and the EQ-vs-biquad check has nothing to
run on. **An adjudication that removes a false constraint does not decode a
word** — what it buys is that the next pass is not chasing a contradiction that
was never there.

---

## 4. PREDICT-THEN-CHECK

Recorded in the scratch `PREDICTIONS.md` before any measurement.

| # | prediction | result |
|---|---|---|
| **PR-1** | `land = 0` ≡ `land = 1`; every published LAND split is 50/50 | **HIT** — 4 000/4 000, and 8 260/8 260, 56/56, 6 370/6 370 |
| **PR-2** | comb machines survive the blocking read | **HIT** — 3 206 / 2 310 / 34 815 |
| **PR-3** | `SRC 0x00 = DR` stops being forced | **HIT**, and stronger: the sequential row is *perfectly uniform* |
| **PR-4** | `tA ← bus` becomes available for `ACTION 0x19` | **HIT** — 630 of 3 206, 13 855 of 34 815 |
| **PR-5** | `ACTION 0x00 = load` stays the plurality | ★ **PARTIAL MISS** — plurality under the adder, **absent** under the sequential model |
| **PR-6** | the all-pass still matches 0 | **HIT**, every row (explicitly counted: 0 of 3 206) |
| **PR-7** | the new survivors will **FORCE** `escact = 1` | ★ **MISS** — 3 178 of 3 206. The 28 exceptions are the *old* `SRC 0x00 = DR` route, which the blocking read also enables; the cross-tab shows all 28 carry `DR`, and the 56 `tB ← bus` survivors are exactly those 28 plus their twins |
| **PR-8** | no frame completes, nothing in the report moves | **HIT** — `diff` empty |
| **PR-9** | *(not predicted)* `tbsh = 0` was already forced in TARGET 1's own strict row | ★ **UNFORESEEN** — a field enumerated in every run and never printed |

---

## 5. ★ THE UPDATED RANKED BLOCKER LIST

**All 177 undecoded slots of the cold-boot frame**, by *reach* (a slot with N
blockers is counted N times, so this is a ranking, not a partition — the
correction TARGET 3 made to the previous list). Static walk, unit-0 = CHORUS @84,
unit-1 = ROOM REVERB @200, reproducing the live `108/91/86` exactly.

```
   DRAM-ADDR         42 slots (  0 PARTIAL,  42 TRAP)  13 distinct
   DRAM-DIR          42 slots (  0 PARTIAL,  42 TRAP)  13 distinct
   SRC-00            40 slots ( 30 PARTIAL,  10 TRAP)  26 distinct
   SRC-0B            20 slots (  1 PARTIAL,  19 TRAP)   5 distinct
   HI31-2            17 slots ( 17 PARTIAL,   0 TRAP)   9 distinct
   ACT-0B            17 slots ( 10 PARTIAL,   7 TRAP)   7 distinct
   ACT-0E            14 slots ( 11 PARTIAL,   3 TRAP)  12 distinct
   MODE1-SPACE       12 slots (  0 PARTIAL,  12 TRAP)  12 distinct
   B7GATE            11 slots (  9 PARTIAL,   2 TRAP)  11 distinct
   ACT07-OFFMODE2    11 slots (  1 PARTIAL,  10 TRAP)   8 distinct
   SRC-11            10 slots (  8 PARTIAL,   2 TRAP)  10 distinct
   ACT-0D             9 slots (  8 PARTIAL,   1 TRAP)   9 distinct
   SRC-08             9 slots (  9 PARTIAL,   0 TRAP)   9 distinct
   ST-OFFMODE2        9 slots (  3 PARTIAL,   6 TRAP)   8 distinct
   C-DEST-000         8 slots (  1 PARTIAL,   7 TRAP)   5 distinct
```

**#1 — the external delay-DRAM: `DRAM-ADDR` + `DRAM-DIR`, 42 slots, 2 unknowns.**
Unchanged as rank 1, and it exclusively owns the delay line: **all 42 accesses
are dark, so the external DRAM is never read and never written in any frame**
(T3 item D). What this pass adds is that **`DRAM-DIR` is now cheaper than it
looks**: H-DIR (`SRC 0x0B` ⇔ READ) is 4/4 against 2/4 for the falsified `addr8`
rule, and both blocks now agree on the *shape* — the read word carries an
anchored capture ACTION (`0x14` reverb, `0x19` SINGLE DELAY) and the write word
sources tempA (`0x15`/`0x0B`, no capture). **The experiment is unchanged and is
still the largest single move available**: model the descriptor bank from the
host's tag-`0x4C` packets and run the cursor's per-frame closure test — the same
test that produced `+0` for the operand pointer, and the only one of the two
pointers this machine walks that has never been testable.
★ *And one route to it is now closed*: `0x827` is **not** the cursor base under
R3 candidate (iii) — item **I**.

**#2 — `SRC 0x00`, 40 slots (30 PARTIAL + 10 TRAP), 26 distinct words.** ★ **It
is no longer a contradiction and it is no longer a search.** `DR` is refused by
three independent routes with no dissenter; what remains is `mem[ptr]` vs `acc`,
and TARGET 2 MEASURED exactly what decides it: `mem[ptr]` is forced **only while
SINGLE DELAY's two input-mix coefficients are `0.0000`**, which is true of the
ROM image and which the host can overwrite at run time.
**Experiment, and it is a capture rather than a solve:** run the emulator, log
every host C-RAM write that lands on those two cells while algo 9 is linked, and
see whether either ever becomes non-zero. If not, `SRC 0x00 = mem[ptr]` is forced
in the machine as it actually runs, and 40 slots move.

**#3 — the bit-7 store-gate CLEAR (`B7GATE`, 11 frame slots, 130 corpus words).**
TARGET 2 proved this is the **same question** as `ACTION 0x00`: in all 33 joint
survivors `add`/`rload` occur only on a late-clearing gate. It is the primary
half, and `ACTION 0x00` is downstream of it. TARGET 2's shortest live probes
stand: `092.2.00.700` (SRC `0x1C`) and the PHASER `w53`/`w54` pair.

**#4 — `ACTION 0x0B` (17 slots) and `ACT-0E` (14 slots).** `0x0B` sits on the
reverb's own multiply word, and the comb search now leaves it completely free in
both halves (7 × 5 values, uniform) — so the reverb cannot settle it and a
different block must.

**#5 — the tempB `>>1` (item H).** Not a slot count: a *correctness* blocker.
Two blocks disagree about a shift that is live in the shipped ALU, and if the
reverb is right the biquad's factor of two is in the wrong place. Cheapest test:
find a block that reads tempB with a capture code other than `0x14`/`0x1A`, or
one that reads it in a mode other than 2.

**#6 — the C-format destination (`C-DEST-*`, 18 slots over four codes).**
TARGET 3's experiment needs no numerics at all: match each destination code to
the Sub CPU routine that constructs or patches it (K3 found seven writers, K5
three).

---

## 6. Safety

* **`-validate kn5000`**: exit 0, **silent** (0 lines of output).
* **DSPCFG Off, published pre-change binary vs this build**: WAV **BIT-IDENTICAL**
  (`cmp` clean, 8 064 050 bytes = 4 032 003 samples, 3 ch × 1 344 001 frames).
  **The capture can fail**: 1 276 567 non-zero samples, peak 22 268 — boot, then a
  fixed chord programme on the keybed from 10 s to 27 s.
* **DSPCFG On vs Off, this build**: **BIT-IDENTICAL** (same md5). Every frame
  still traps, so **trapped frames contribute ZERO**.
* **All three terminations still fire**, with identical counts: 1 106 880 on the
  wait word, 210 241 on the 384-slot cap, 26 880 on I-RAM overrun. MAME exited
  normally, exit 0, no hang, no leaked process.
* **The input-stage audit still passes and can still fail**: 1 117 440 frames with
  both port reads, **0 MISMATCHED**, 638 678 carrying a non-zero sample.
* **Mirror agreement**: `tools/upd6383d_diff.sh` — **MIRRORS AGREE, 3057/3057**,
  text *and* the three execution predicates `D/A/K`.
* **Byte-match**: `dsp/verify.py` — **BYTE-MATCH OK**. No `.dsm` regenerated (no
  rendering changed).
* Build: `build.sh` clean, 0 `error:` / `Error [0-9]` in the log, binary mtime
  advanced, 74 405 928 bytes. `tools/publish-binary.sh` run.

---

## 7. Reproducing

```bash
cd ~/compartilhado/kn5000-roms-disasm
python3 dsp/tools/r1_allpass_solve.py blockread                # the argument + 4 controls
SCH_PARTS=search SCH_ROW=1  python3 dsp/tools/r1_allpass_solve.py schroeder2   # -> 112 (mirror check)
SCH_PARTS=search SCH_ROW=8  python3 dsp/tools/r1_allpass_solve.py schroeder2   # -> 3206
SCH_PARTS=search SCH_ROW=9  python3 dsp/tools/r1_allpass_solve.py schroeder2   # -> 34815
SCH_PARTS=search SCH_ROW=10 python3 dsp/tools/r1_allpass_solve.py schroeder2   # -> 2310
python3 dsp/tools/dsp_coverage.py
python3 dsp/verify.py
~/compartilhado/kn7000_mame/tools/upd6383d_diff.sh

cd ~/compartilhado/kn7000-emulator
./kn7000 kn5000 -rompath ./roms -window -nomaximize -skip_gameinfo -nothrottle -log \
    -nvram_directory <scratch>/nv -cfg_directory <scratch>/cfg_on \
    -autoboot_script <scratch>/audio.lua -wavwrite <scratch>/on.wav
grep -A32 'FRAME REPORT' error.log
```
