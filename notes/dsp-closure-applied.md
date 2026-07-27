# APPLYING the adjudication — the accumulator is an adder, and the store is gated

NEC **uPD6383GF-3BA** (Technics SX-KN5000, IC311). Date: **2026-07-26**.
No hardware. Static analysis, the ROM corpus, constraint solving and the live
emulator only.

Labels: **MEASURED** / **PROVEN BY CONSTRUCTION** / **FORCED** / **CONSISTENT** /
**FALSIFIED** / **OPEN**.

Companion analysis (the derivation, with every number):
`kn5000-roms-disasm/dsp/analysis/acc-adder.md`.

---

## 0. Result in one page

| # | what | label |
|---|---|---|
| **A** | ★ **THE ADJUDICATION.** Two of the three incoming passes had reached OPPOSITE determinations about the same instruction field and neither could see it: the LFO pass FORCED that the `lo12` ACTION acts **before** the `hi12[3:1]` operation, SINGLE DELAY FORCED the **opposite** order — because `sec_singledelay()` never passed `actfirst` and silently took the shipped default. Re-derived from the ROM, **both are right about the answer and wrong about the mechanism**: each block demands `acc = bus + P` at the word where its sum forms, one at `hi12[3:1] == 1` and one at `== 0`. No ordering gives both. **One adder does.** | **FORCED** |
| **B** | ★ **The joint search over THREE independent numeric contexts has a unique answer.** Bit-identity with the PARAMETRIC EQ biquad × the SINGLE DELAY comb × all 29 LFO blocks, over 2160 × 3240 × 181 440 enumerated points → **18 survivors**, all agreeing: the adder, `ACTION 0x00` = "the bus replaces the accumulator's own feedback term", and the **shipped** store timing. | **FORCED** |
| **C** | ★ **APPLIED, and it moves the fully-decoded count for the first time in two passes: 80 → 108 of 285 frame slots.** Words executing *something* stay at 199 — the 28 moved from PARTIAL to DECODED. Distinct undecoded words in the frame **123 → 119**. | **MEASURED** |
| **D** | ★ **THE CLOSURE RESIDUE DID NOT MOVE: still +121 on 1 130 880 of 1 130 880 complete frames.** Predicted before the run (nothing adopted here touches a pointer displacement) and confirmed to the unit. It is not a defect this pass could fix; TARGET 1 showed it is a **located hole**, not an arithmetic error. | **MEASURED**, prediction **HIT** |
| **E** | ★ **NO FRAME COMPLETES. 100 % still trapped, and the audio is still exactly the dry mix.** 177 of 285 slots are still undecoded. The deliverable is §5, the updated ranked blocker list. | **MEASURED** |
| **F** | **A falsification with a price, paid.** The shipped model stored the accumulator on every bit-4 word. The LFO forces that wrong wherever `hi12` bit 7 is set, and only two of the four gate cases are settled — so **19 corpus words LOSE a decode they should never have had**, and the disputed cases now trap. A pass that only adds is a pass that is not checking itself. | **MEASURED** |
| **G** | **The biquad is untouched, and that is measured rather than argued.** The generated mirror (which lifts `exec_alu()` verbatim out of the device) produces a **bit-identical impulse response** before and after, on all 16 candidate coefficient banks; the published per-band figures reproduce exactly (algo39 bands 0–4 = 0.00205 / 0.00463 / 0.00123 / 0.00119 / 0.00116 dB; algo99 flat PEQ = 0.07502 dB / 4.025°). | **MEASURED** |
| **H** | Safety holds. **DSPCFG Off is BIT-IDENTICAL to the published pre-change binary** over a capture that can fail (4 104 003 samples, 1 033 581 non-zero, peak 21 894); On is bit-identical to Off; `-validate kn5000` clean, exit 0; the cap, the overrun guard and the wait-word termination all still fire; the input-stage audit still passes and can still fail; mirrors agree **3057/3057**; `verify.py` **BYTE-MATCH OK**. | **MEASURED** |

---

## 1. What was adjudicated

Three passes arrived at once. The conflicts, and how each was settled **by
re-deriving from the ROM** rather than by preferring a source:

| conflict | settled how | outcome |
|---|---|---|
| **ACTION `0x00` = `acc ← bus` before the operation (LFO)** vs **`acc += bus` after it (SINGLE DELAY)** | put both blocks, plus the biquad, into ONE search over ONE declared model space that also contains a non-sequential reading | **BOTH SUPERSEDED.** The ACTION is a selector on the accumulator's adder. The unique survivor computes what each pass computed, in a mechanism neither had |
| **`ACTION 0x19` captures tempA — from the bus or from the accumulator?** (`action-field.md` left it free) | strengthen SINGLE DELAY: deliver the input through the MEASURED pointer walk into a real D-RAM, randomise every unset register, drop the arbitrary-scale match | **`tempA ← bus`, FORCED 72/72** |
| **the LFO's bit-7 store gate** (`lfo-ramp.md`, three survivors, "NOT adopted") | re-derive in an independently-parameterised space | **CONFIRMED** — `always` has 0 of 181 440 survivors here too; adopt the part all survivors agree on and **trap** the rest |
| **`hi12[3:1] == 2` = "AND the coefficient"** (an `instruction-set.md` survivor) | biquad bit-identity | **FALSIFIED.** It changes the section |
| **`SRC 0x00`: `mem[ptr]` (SINGLE DELAY, now 72/72) vs the delay-read register (the reverb, 52 696/52 696)** | neither context can be made to yield | **UNRESOLVED — refused.** 30 frame slots left on the table rather than pick |
| **TARGET 1's closure work** | nothing in it is applicable: its results are a falsification, a site set and a localisation, and it explicitly adopted nothing | **nothing applied**, and the residue is re-measured as a check |

**A falsification I did not expect to have to make, about the tool that produced
one of the inputs.** Re-run with the order enumerated, the old SINGLE DELAY
search has **22 050** survivors at the LFO's order — and there `ACTION 0x00` is
*unconstrained* (35 of 35 values, "no effect" included). The block passes by
computing `fb·(x[n] + v[n−D])`, the comb reference **times fb**, which the
arbitrary-scale matcher accepted. So that model does not merely fail to decide
the order: at act-first it FORCES the *opposite* capture semantics with equal
formal confidence. **A determination that flips when an unvaried parameter is
varied is not a determination**, and this is the second time in this project that
a too-small search space produced a confident wrong answer.

---

## 2. What was applied

`src/devices/cpu/upd6383/upd6383.{cpp}` and `upd6383d.{h,cpp}`, mirrored into
`kn5000-roms-disasm/dsp/tools/dsp_disasm.py`.

### 2.1 The accumulator step

```
   acc  <-  SRC_TERM  +  P_TERM

      SRC_TERM = bus                    if lo12[4:0] == 0x00
               = 0                      if hi12[3:1] == 0        (acc <- P)
               = acc                    otherwise
      P_TERM   = 0                      if hi12[3:1] == 2        (no product)
               = P                      otherwise
```

**On every word whose ACTION is not `0x00` this is the previous code exactly** —
PROVEN BY CONSTRUCTION, and MEASURED as bit-identity of the generated biquad
mirror. The bus enters at the accumulator's own scale (`L << ACC_SHIFT`), which
is the scale `acc_to_datum()` reads back and `LO_ACT_ST_BUS` writes, so
`acc ← acc` round-trips.

### 2.2 ACTION `0x19` = `tempA ← bus`

A second capture pair beside `0x13`/`0x14` (`0x19 = 0x13 + 6`,
`0x1A = 0x14 + 6`). This settles a reading `dsp-frame-advance.md` §2 priced at 13
frame slots and called *"INFERRED, and internally contradicted"* — and it
resolves **against** the `lo12[2:0]`-as-destination pattern, which put tempA at
`[2:0] == 3` while `0x19` has `[2:0] == 1`.

### 2.3 The bit-7 store gate — and the words it costs

```
   bit7 == 0                     -> store and clear      (the biquad's case)
   bit7 == 1 && hi12[3:1] == 2   -> store and clear      (3 of 3 gates agree)
   bit7 == 1 && hi12[3:1] == 1   -> NO STORE             (3 of 3 gates agree)
                                    ...the CLEAR is DISPUTED, so the word is
                                    executed ONLY when its ACTION is 0x00, where
                                    the adder's SRC term replaces the
                                    accumulator feedback and the clear cannot be
                                    observed.  Otherwise it TRAPS.
   bit7 == 1 && hi12[3:1] otherwise -> the gates disagree outright  -> TRAP
```

Corpus census, MEASURED (3057 words, 707 carrying bit 4):

```
   b7=0                      store+clear (biquad-verified)   527
   b7=1 f31=2                store+clear (3 gates agree)      29
   b7=1 f31=1                NO store; clear disputed        138   (107 ACTION 0x00
                                                                   -> execute;
                                                                   31 -> trap)
   b7=1 f31 in {0,5}         gates disagree -> trap           13
```

**19 corpus words lose a decode.** They are `292.A.01.412` ×4, `292.A.01.1D5` ×3,
`192.A.03.1D5` ×3 and six more, all `(bit7 = 1, hi12[3:1] = 1)` with an ACTION
that makes the disputed clear visible, plus one at `hi12[3:1] = 0`. The shipped
model was executing them with an unconditional store that **0 of 181 440**
machines can reconcile with the LFO.

The same gate is applied to the K6 whitelist's store in `exec_addressing_only()`.
MEASURED: none of the twelve carries bit 7, so it changes nothing today — a hole
closed before it opens, like the two guards before it.

### 2.4 What was NOT applied, and what it costs

| refused | why | frame slots left |
|---|---|---|
| `SRC 0x00 = mem[ptr]` | FORCED in SINGLE DELAY (72/72) — and the reverb ladder's own filter requires it to be the delay-read register (52 696/52 696). **Two contexts, two answers, unresolved** | **30** |
| `SRC 0x08 = unity multiplicand` | FORCED by the LFO (1224/1224) but only on **class-A** words; `010.9.D0.20C` carries it off class A and nothing tests that | 8 |
| `hi12[3:1] == 2` off class 8 | two survivors (`hold`, `AND 0x7FFFFF`) that differ | 3 |
| the store WRAP (the LFO's 2²³) | three survivors | 0 today |
| the CLEAR at `(bit7, f31) = (1, 1)` with ACTION ≠ `0x00` | two survivors | 9 |

---

## 3. ★ THE RE-MEASUREMENT

Live, `DSPCFG On`, cold boot + the 28 s regression programme, 1 368 001 frames:

```
   last frame: 285 slots = 108 DECODED + 91 PARTIAL (addressing only) + 86 TRAP
```

| | before | after |
|---|---|---|
| words executing **something** | 199 of 285 | **199** of 285 |
| words executing **FULLY** | 80 | ★ **108** |
| words executing **nothing** | 86 | **86** |
| distinct undecoded words **in the frame** | 123 | **119** |
| distinct undecoded words over the whole 28 s run | 128 | **122** |
| **frames completed** | 0 | **0** |
| **★ CLOSURE RESIDUE** | **+121** on 1 130 880/1 130 880 | ★ **+121** on 1 130 880/1 130 880 |

### 3.1 The closure residue — unchanged, and that was the prediction

```
   FRAME CLOSURE ... net displacement must be 0 mod 256:
       net D-RAM pointer displacement, last frame +121
       over every COMPLETE frame (1130880 of them): min -1  max +121
       frames that closed 960 of 1130880
```

**PREDICT-THEN-CHECK, HIT.** Written before the run: *"the closure residue stays
+121, because nothing adoptable moves a pointer."* Every code this pass anchors
lives in `lo12`; the pointer walk reads `class4` and `addr8` only. The static
walk still computes −135 ≡ +121 (mod 256), agreeing with the live core to the
unit.

**What that now means is different from what it meant last pass.** TARGET 1
established that (a) the closure equation is **degenerate in the payload** — an
absolute reload closes the frame for *any* value, so closure constrains the
**site**, not the immediate; (b) the five `lo12 = 0x820` header words are
**excluded on siting** (a reload at I-RAM 15/22/29/31/40 puts both algorithm-
dependent body nets in its tail, and the unit-0 pool has 8 distinct net
displacements over 37 images); (c) the admissible sites are I-RAM 50…78; and (d)
the criterion's own **FORCED** label does not survive, because K6 finding 5 rests
on a reading K3 withdrew. So `+121` is **a located hole, not an arithmetic
error**, and no ALU work can close it. It is re-measured here as a *check that
nothing broke*, which is what it is now good for.

### 3.2 Does a frame complete? **NO.**

100.00 % of frames still trap and their return is still discarded. There is no
audio to check for a decaying tail, and the EQ acceptance test was run anyway (as
a regression, §4) rather than as a frame result. 177 of 285 slots remain
undecoded across 119 distinct words.

---

## 4. SAFETY — every check reproduced

* **`-validate kn5000`**: clean, **exit 0**.
* **DSPCFG Off, published pre-change binary vs this build**: WAV
  **BIT-IDENTICAL**, 8 208 050 bytes = 4 104 003 samples (3 ch × 1 368 001 frames
  @ 48 kHz), `cmp` clean.
  **The capture can fail**: 1 033 581 non-zero samples, peak 21 894 — boot, a 4 s
  sustained C4, its release, a chromatic 12/12 across the middle octave and a
  held C-E-G chord.
  *(A process note worth recording: the first run of this check compared the
  published binary against itself, because `build.sh` writes to
  `kn7000_mame_build/` and `tools/publish-binary.sh` had not been run yet. It
  "passed" and meant nothing. Caught by grepping the DSP log for the new
  mnemonics and finding none.)*
* **DSPCFG On vs Off, this build**: **BIT-IDENTICAL**. Every frame still traps,
  so every return is still discarded — **trapped frames contribute ZERO**.
* **The three terminations all still fire**: 1 130 880 frames ended on the wait
  word, 210 241 on the 384-slot cap, 26 880 on I-RAM overrun. MAME exited
  normally, exit 0, no hang, no leaked process.
* **The input-stage audit still passes and can still fail**: 1 141 440 frames in
  which both port reads executed, **0 mismatched**, 517 980 carrying a non-zero
  sample, peak `0x558600`. This is a genuine re-test — 28 more words per frame
  now execute their ALU, and the gate changed which stores land.
* **The biquad, on the arithmetic that ships**: the generated mirror's impulse
  response is **identical before and after** on all 16 candidate banks. Published
  figures reproduced exactly:
  `algo39` bands 0–4 = 0.00205 / 0.00463 / 0.00123 / 0.00119 / 0.00116 dB;
  `algo99` flat PEQ = 0.07502 dB / 4.025°.
  *(The mirror generator had to be repaired first: `exec_alu()` had grown calls
  to `coeff_consumer()` and `cursor_fetch()` that its shim did not declare, so it
  no longer compiled. That is the design working — it failed loudly instead of
  drifting — but it means the harness had not been re-run since the K4 pass.)*
* **Mirror agreement**: `tools/upd6383d_diff.sh` — **MIRRORS AGREE, 3057/3057**.
* **Byte-match**: `dsp/verify.py` — **BYTE-MATCH OK**, kernel + epilogue + 91
  valid algorithm streams, 38 distinct images. All 41 `.dsm` listings were
  regenerated (189 lines changed: 124 `mac.b`, 28 `mac.ta2`, 17 `ld.ta2`, 19
  words that lost their decode to the gate, 1 `~word`).

---

## 5. ★ THE UPDATED RANKED BLOCKER LIST

Ranked by frame slots in the cold-boot frame (285 slots, **177 undecoded** over
**119 distinct words**). Static walk, unit-0 = CHORUS @84, unit-1 = ROOM REVERB
@200.

```
   external delay-DRAM (mode-1 escape)               41 slots, 12 distinct
   lo12[10:6] SOURCE unanchored                      37 slots, 24 distinct
   lo12[4:0] ACTION unanchored                       26 slots, 18 distinct
   C-format immediate word                           18 slots, 12 distinct
   internal REGISTER FILE (mode 1, no escape)        12 slots, 12 distinct
   bit-4 store GATE disputed (bit7)   -- NEW          9 slots,  9 distinct
   lo12 BOTH halves unanchored                        9 slots,  9 distinct
   other ESCAPE word (mode != 1)                      9 slots,  6 distinct
   lo12 bit-11 modifier (register-load family)        7 slots,  7 distinct
   class 9 -- addressing mode unknown                 4 slots,  4 distinct
   hi12[3:1] operation unproven off class 8           3 slots,  3 distinct
   class 6 / class 4 -- addressing mode unknown       4 slots,  3 distinct
```

> ## ⚠ CORRECTION — THIS LIST IS NOT A PARTITION AND ITS COUNTS ARE NOT ADDITIVE
> (2026-07-27, `kn5000-roms-disasm/dsp/analysis/dark-words.md` item E)
>
> The twelve buckets above sum to **179** against the **177** undecoded slots
> stated three lines earlier, because a word carrying two unknowns is charged to
> two buckets. And the first bucket is **42, not 41**: `880.1.30.8BC` also carries
> the `lo12` bit-11 modifier and was counted only in that bucket.
>
> **The RANKING survives** — the delay-DRAM family is rank 1 by reach on 37 of 37
> unit-0 bodies, and it is also rank 1 on the two leverage metrics `dark-words.md`
> introduces — but the numbers must not be arithmetic-ed with. The strict
> partition of the 86 TRAP slots by *blocker set* is in `dark-words.md` §3.1
> (delay-DRAM 42 / C-format 17 / mode-1 space 12 / unknown class 12 / class-0
> register load 3 = 86 exactly), and that is the list to use for per-unknown
> leverage. This one remains useful only as a per-unknown *reach* count.

### #1 — the external delay-DRAM family — **42 slots, 13 distinct** (corrected)

`880.1.60.2D4` ×9, `880.1.20.655` ×9, `900.1.60.1D5` ×4, `880.1.20.2C7` ×4, …
The **address** is PROVEN BY CONSTRUCTION (`DESCRIPTOR_CELL[cursor] + G`, R3); the
**direction** is OPEN and R3 §6.3 falsified the `addr8` rule. It is now the
largest blocker, and the only one whose *mechanism* is already understood.
**Experiment**: route the host's tag-`0x4C` packets into a modelled descriptor
bank and advance a descriptor cursor per DRAM word. That executes no arithmetic
but makes R3's counting identity a **live** check that can fail.

### #2 — `lo12[10:6]` SOURCE unanchored — **37 slots, 24 distinct**

```
   unanchored SOURCE codes by frame slots:  00: 30   08: 8   11: 8   13: 4   0B: 1   1C: 1
```

`SRC 0x00` alone is 30 of them, and it is now **the single highest-value unknown
in the ISA**. It also has the project's sharpest live contradiction: SINGLE DELAY
FORCES `mem[ptr]` at 72/72 and the reverb ladder's delay-loop filter requires the
delay-RAM read register at 52 696/52 696. **Experiment**: the reverb requirement
is a *necessary condition of an assumption the same search refutes* (0 cascades),
so the way to settle it is to find a **third** block carrying `SRC 0x00` whose
algorithm is independently known — the compressor's envelope (`0.750000` and
`0.636620 ≈ 2/π`) is the obvious candidate and is undecoded for a reason that
overlaps: `hi12[3:1] == 5`.

### #3 — `lo12[4:0]` ACTION unanchored — **26 slots, 18 distinct** (was 61/31)

```
   unanchored ACTION codes by frame slots:  0E: 11   0B: 10   0D: 8   08: 6   17,1A,0C: 1
```

`102.A.00.64B` ×8 — the reverb all-pass core's gain multiply — is the largest.
`action-field.md` proved exhaustively that **no** assignment of the core's codes
makes it a first-order all-pass under this ALU, and located the obstruction in
the accumulator **CLEAR** (the only one of nine relaxations that moves the count
off zero). This pass does not touch that: the core's slot-3 word `012.2.00.680`
has `bit7 = 0`, so the new gate does not reach it. **The clear outside the biquad
remains the highest-value open question in the ALU.**

### #4 — C-format immediate words — **18 slots, 12 distinct**

`C40.3.20.44C` ×4, `C40.1.80.000` ×4, and the five `lo12 = 0x820` words. ★ **This
entry is DOWNGRADED**: the previous list called the five `0x820` words "the one
experiment that could close §3 outright". TARGET 1 **falsified that on siting** —
a reload at I-RAM 15/22/29/31/40 cannot produce an algorithm-independent pointer,
whatever its payload field is. Their payload is still OPEN; closure says only
what they are *not*.

### #5 — the internal REGISTER FILE (mode 1) — **12 slots, 12 distinct**

Where the audio leaves the chip (`w73`/`w78` present unit 0 to DO1 and unit 1 to
DO2), so nothing audible can happen until it executes. Six of its source codes
occur exactly once each in the whole machine. **Experiment (LIVE, the only one
here that needs the emulator)**: the two output levels are known numbers — unit 0
`+0.500000`, unit 1 `+0.183992` — and the host rewrites them on every effect
edit, so "does the output scale by exactly those factors" is a repeatable,
falsifiable test with a known answer.

### #6 — the bit-4 store gate, disputed cases — **9 slots, 9 distinct** — NEW

Created by this pass, and cheap to close: the three surviving gates differ on 13
corpus words, **nine of them `09A.A.00.200`**, the COMPRESSOR's envelope step at
`hi12[3:1] == 5`. Decoding that one `hi12[3:1]` code settles the gate *and*
attacks #2's third-context problem. **Highest value per unit of work in this
list.**

### #7–#11 — the residue — **27 slots**

`lo12` both halves unanchored (9), other escape words (9), the bit-11 modifier
family (7), classes 9/6/4 whose addressing mode is unknown (8),
`hi12[3:1]` off class 8 (3).

### The list behind the list

Two unknowns dominate everything else:

```
   SRC 0x00                     30 frame slots, 615 corpus words, TWO CONTEXTS DISAGREE
   the delay-DRAM direction     41 frame slots, mechanism already proven
```

and one question is worth more than its slot count: **does `hi12` bit 4 really
clear the accumulator outside the biquad?** It is the only assumption whose
removal moves the reverb search off zero, and the biquad — which is where it came
from — cannot see the case that matters.

---

## 6. PREDICT-THEN-CHECK log

| | prediction, recorded before the measurement | result |
|---|---|---|
| **A-1** | SINGLE DELAY at act-first has **zero** survivors in the OLD model | **MISS.** 22 050 — and the reason is the pass's second-best result (§1) |
| **A-3** | the clash survives randomising SINGLE DELAY's entering state | **HIT** |
| **A-5** | the adder needs the CLEAR moved to the end of the word to run the LFO | **MISS.** `load` *replaces* the feedback term instead of adding to it, so the shipped timing suffices. I had reasoned it out on paper and got it wrong |
| **A-7** | store/clear at the end BREAKS the biquad | **HIT, and stronger**: "store early, clear late" breaks it too, so the biquad FORCES the shipped timing |
| **A-8** | ACTION `0x00` will **not** be adoptable this pass | **MISS, and the good one** |
| **A-9** | the closure residue stays **+121** | **HIT**, to the unit |
| **A-10** | no frame completes | **HIT.** 0 of 1 368 001 |

---

## 7. Reproducing

```bash
# the adjudication (static, no emulator)
cd ~/compartilhado/kn5000-roms-disasm
python3 dsp/tools/acc_adjudicate.py joint            # ~35 min
python3 dsp/tools/r1_allpass_solve.py adjudicate     # the older model, order enumerated

# the mirrors and the byte match
~/compartilhado/kn7000_mame/tools/upd6383d_diff.sh   # MIRRORS AGREE -- 3057/3057
python3 dsp/verify.py                                # BYTE-MATCH OK

# the biquad, on the arithmetic that ships
cd ~/compartilhado/kn7000_mame
python3 tools/kn5000_dsp_alu_mirror.py /tmp/mirror.cpp
g++ -O2 -std=c++17 -o /tmp/mirror /tmp/mirror.cpp

# the live measurement
cd ~/compartilhado/kn7000-emulator
./kn7000 kn5000 -rompath ./roms -window -nomaximize -skip_gameinfo -nothrottle -log \
    -nvram_directory <scratch>/nv -cfg_directory <scratch>/cfg_on \
    -autoboot_script <scratch>/audio.lua -wavwrite <scratch>/on.wav
#   <scratch>/cfg_on/kn5000.cfg:
#     <port tag=":DSPCFG" type="CONFIG" mask="1" defvalue="0" value="1" />
grep -A25 'FRAME REPORT' error.log
```
