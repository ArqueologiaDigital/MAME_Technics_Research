# ADJUDICATE AND APPLY — the three passes, and the one thing in them that was FORCED

NEC **uPD6383GF-3BA** (Technics SX-KN5000, IC311). Date: **2026-07-27**.
No hardware. Static analysis, the ROM corpus, constraint solving and the live
emulator only.

Labels: **MEASURED** / **PROVEN BY CONSTRUCTION** / **FORCED** / **CONSISTENT** /
**INFERRED** / **EDUCATED GUESS** / **FALSIFIED** / **OPEN**.

Inputs adjudicated:
`dsp/analysis/allpass-adder-rerun.md` (TARGET 1),
`dsp/analysis/output-stage-decode.md` (TARGET 2),
`dsp/analysis/retraction-sweep.md` (TARGET 3).

---

## 0. Result in one page

| # | statement | label |
|---|---|---|
| **A** | ★ **THE CLOSURE RESIDUE IS GONE. +121 → +0.** Live, over 1 344 001 frames: the last frame's net D-RAM pointer displacement is **+0**, and **1 080 959 of 1 106 880** complete frames close (was **960**). The cause was never the ALU: it is what walking ONE pointer through a machine that **rebases per unit** produces. | **MEASURED** |
| **B** | ★ **What was applied is exactly one thing, and it is the only FORCED item in the three passes that was not already in the core**: at the per-unit CALL the D-RAM operand pointer is set to **`0x05 \| (unit << 7)`**. No word gains a semantic; every word that trapped still traps. | **FORCED** (value), **OPEN** (which instruction) |
| **C** | ★ **THE APPLIED NUMBER WAS RE-DERIVED FROM THE ROM BEFORE IT WAS APPLIED, BY A ROUTE THE ORIGINAL PASS DID NOT USE — and it is host-free.** The shared 83-word kernel names six mode-1 absolute indices in the unit-1 half (`0x85 0x8A 0x8C 0x8D 0x8F 0xD0`); the reverb body's own mode-2 pointer walk reaches **all six** at **exactly one origin of 256**, and it is `0x85`. Control over all 256: mean **0.33**, sd **0.85**, sole winner, z = **+6.7**. §2.3. | **MEASURED**, new |
| **D** | ★ **X SETTLES ON 0xFF AND THE DI LATCHES LAND ON 0x01 / 0x04** — `output-stage-decode.md` §3.5's map, live: X = `0xFF` on **1 080 098 of 1 106 880** complete frames (97.58 %), runner-up 1 064. Before the rebase X drifted and the map could not be tested at all. The input-stage audit still reports **MISMATCHED 0**. | **MEASURED**, a prediction of the map |
| **E** | ★ **NO FRAME COMPLETES. 1 344 001 of 1 344 001 still trap and every return is still discarded.** 285 slots = **108 DECODED + 91 PARTIAL + 86 TRAP**, unchanged to the word. The coverage table is unchanged to the digit. Applying a *pointer* changes what the executing words address, not how many of them execute. | **MEASURED** |
| **F** | **TARGET 1 requires NO code change.** Its two "forced half-codes" are already what ships (`ACTION 0x00` routes the bus into the accumulator; `ACTION 0x19` = `tempA ← bus`), its `ACTION 0x00 = load` survives (the all-pass rejects every machine either way, so it forces nothing there, and the joint solve's 18/18 stands), and its `SRC 0x00` conflict is a genuine two-context disagreement ⇒ it keeps trapping. §1.2. | **adjudicated** |
| **G** | ★ **A REAL GAP IN THE MIRROR DISCIPLINE, found and closed.** `upd6383d_diff.sh` compared **`text()` only**. `decoded()` reaches the text; **`has_addressing()` and `addressing_only()` do not** — the corpus contains `?word` lines with and without an addressing effect that render identically, and those two predicates decide whether a word's pointer arithmetic runs. A divergence there would have moved every pointer in the machine with the mirror check still saying AGREE. The harness now prints `D/A/K` beside every word. Result: **3057/3057 on text AND all three predicates.** §5. | **MEASURED** |
| **H** | **No shipped code rests on a retracted premise** — re-verified, not inherited: `retraction_sweep.py code` reports 9 LIVE and **all 9 are retraction prose**, read individually. `P15` (the D-RAM origin is OPEN / the +121 is a defect) is **added to the premise table** and propagated: 0 LIVE anywhere. | **MEASURED** |
| **I** | **Safety holds.** DSPCFG **Off** is **bit-identical** to the published build over a capture that carries real audio (1 276 567 non-zero samples, peak 22 268); **On** is bit-identical to Off; `-validate kn5000` exit 0 and silent; cap / overrun / wait-word terminations all still fire with **identical counts**; `verify.py` **BYTE-MATCH OK**; mirrors agree 3057/3057. | **MEASURED** |
| **J** | **One of my own tests was killed by its own control, and it is reported as such.** "33 of 37 unit-0 bodies read cell `0x05` before writing it" looked like independent support for `E0 = 0x05`. Over all 256 candidate origins the mean is **32.99**, sd **0.19**: it is a **baseline**, not evidence. z = +0.1, rank 250 of 256. §2.4. | **FALSIFICATION**, of this pass's own first idea |

---

## 1. The adjudication

### 1.1 What the three passes actually leave to apply

The brief's rule is *implement only what is FORCED or PROVEN*. Walked item by
item, the three passes contain exactly **one** forced statement that the shipped
core did not already implement.

| pass | forced item | already in the core? |
|---|---|---|
| T1 | the all-pass negative result survives the adder (0 cascades from 74 508 loop survivors) | it is a **negative**; nothing to apply |
| T1 | `ACTION 0x00` touches the accumulator | **yes** — `LO_ACT_ACC_BUS` is the adder's `SRC_TERM = bus` |
| T1 | `ACTION 0x19` captures **from the bus** into `tempA` | **yes** — `LO_ACT_CAP_TA2` → `m_ta = L` |
| T1 | the obstruction is slot 4's **write**, not the clear | a diagnosis, not a semantic |
| T2 | **`base = 0x05 \| (unit << 7)`, and a rebase between the CALLs exists** | ★ **NO — this is the change** |
| T2 | `X = 0xFF`; frame closes; residue 0 | a **consequence** of the above, not a separate change |
| T2 | `ACTION 0x07` on a mode-1 word does **not** write `reg[addr8]` | **yes** — `alu_decoded()` guard 6 already refuses it; what it gains is a *positive reason*, applied to **both** mirrors as comment |
| T2 | `w73`/`w78` are not one instruction | neither is decoded; nothing to apply |
| T3 | nothing shipped rests on a retracted premise | re-verified (item **H**) |
| T3 | the "pointer never returns" defect is re-opened and is the same phenomenon as `+121` | ★ **answered by the T2 item above** |

**The adjudication in one sentence:** TARGET 3 said the missing absolute reload
would most likely be found by decoding the output stage; TARGET 2 decoded the
output stage and found the *value*; the two dovetail, and applying the value is
the whole of this pass's code change.

### 1.2 The three conflicts, and how each was settled

**(i) `SRC 0x00` — the reverb needs `DR`, SINGLE DELAY forbids it.**
`allpass-adder-rerun.md` reports `DR` in 52 696/52 696 reverb loop survivors and
in **0 of 5 635** SINGLE DELAY survivors. That is a **flat contradiction between
two contexts**, and the rule is that an unproven word keeps trapping. `SRC 0x00`
is **not** in `_ANCHORED_SRC` in either mirror and **stays out**. Nothing applied.
*(Note the asymmetry that makes this a real conflict rather than a preference:
the reverb's 52 696 all fail the numeric test, so the reverb is not evidence
**for** `DR` — it is evidence that the reverb's structural filter cannot exclude
it. SINGLE DELAY's 0/5 635 is the stronger of the two and still not a proof.)*

**(ii) `ACTION 0x00` — `load` (joint solve, 18/18) vs `add`-like (all-pass, 9 520
of 9 660).** Settled **for `load`, which is what ships**, and the reason is not a
tie-break: the all-pass search **rejects every one of those 9 660 machines
numerically**, so it forces nothing about `ACTION 0x00` at all — it only reports
what a *rejected* set would have needed. A property of an empty survivor set is
not a constraint. The joint solve's 18/18 is an actual forcing and stands.

**(iii) The output-stage map's own internal tension — `w45` and `w53`.**
Not in any of the three passes; found while re-deriving. `w45 = 010.A.00.20C` and
`w53 = 010.9.D0.20C` are the **same `lo12`** in mode 2 and mode 1 — visibly one
operation in two addressing modes — yet under the adopted map they land at
`E0+0` and `E1+75`, which is **not** symmetric. Two readings were enumerated and
one is falsified:

* *the map is shifted*: `E0 = 0x50`, `E1 = 0xD0` makes them symmetric **and
  satisfies both closure routes** (`0xD0 + 123 − 1 = 0x4A`, and `0x4A + 6 = 0x50`)
  — a second, self-consistent solution of the closure equations that
  `output-stage-decode.md` §4 does not mention. ⇒ **FALSIFIED by §3.1**: with
  `E = 0x50` the PARAMETRIC EQ 40-cell run lands at `0x9B`, not `0x50`, so the
  one derivation with no free parameter excludes it.
* *the asymmetry is real*. ⇒ **held, and independently checked**: I walked the
  reverb body under `E1 = 0x85` and both cells are genuinely externally supplied
  — `0x85` is read at body word 5 and never written, and `0xD0` is **read at body
  word 7 before anything writes it**, which is exactly what `w53`'s absolute
  deposit requires. §2.3.

---

## 2. Re-deriving the applied number from the ROM

Nothing below is taken from the notes; it is recomputed from
`original_ROMs/kn5000_subprogram_v142.rom` with an independent walker.

### 2.1 The displacements (reproduced exactly)

```
   d( 0..44) = +6     d(45..49) = +0     d(50..58) = +2     d(59) = +0
   d(60..82) = -1     reverb (algo 16, the ONE unit-1 image) net = -133 = +123 (mod 256)
   net(body0) over the 37 unit-0 images: {-16, -9, -7, -5, -4, +5, +6, +112}  -- EIGHT values
```

Eight values is the whole forcing of the rebase's **existence**: `E1` cannot be
reached by walking from `E0`, whatever `E0` is.

### 2.2 …and one thing the note's favourite candidate does not survive

`output-stage-decode.md` §7.1 offers `800.1.60.00B` at I-RAM **54** as the
best-shaped rebase site (EDUCATED GUESS). Measured here: **`d(55..58) = +2`**
(`w55` and `w57`, `+1` each). So a rebase *at w54* delivers `E1 + 2` to the body,
not `E1` — siting it there requires the value **`0x83`**, not `0x85`. The note
anticipated this in passing ("or `0x83`/`0x84`, the pre-`w55`/`w57` variants") but
did not connect it to the site argument. **The pointer value at BODY ENTRY is
`0x85` under every admissible siting**, and that invariant — not a site — is what
the core implements.

### 2.3 ★ A NEW derivation, and it uses no host data at all

All three of `output-stage-decode.md`'s derivations run through the **host's**
zero-fill. That makes them one family. Here is a fourth that is entirely the
microcode against itself:

> The shared kernel names 12 mode-1 **absolute** indices — `0x05 0x06 0x0E 0x0F
> 0x20 0x60` and `0x85 0x8A 0x8C 0x8D 0x8F 0xD0`. Six are in the unit-1 half.
> Ask: for which entry pointer does the reverb body's **mode-2 pointer walk**
> reach those six cells? Under item **B** (one 256-cell RAM) the two routes must
> agree; under the two-space alternative every agreement is chance.

```
   E1 = 0x85 : 6 of 6      <-- ADOPTED, and the SOLE winner over all 256 origins
   E1 = 0x83 : 4     E1 = 0x87 : 4     E1 = 0x88 : 4     E1 = 0x8A : 4
   control over all 256 origins: mean 0.33  sd 0.85  max 6  z = +6.7
```

Sharpest single instance: the pointer is at `E1 + 75` at body word 7, and `w53`
stores absolutely at `0xD0`, so `E1 = 0xD0 − 75 = 0x85` — **one origin of 256, no
free parameter, no host data.** The unit-0 side by the same method:
`E0 = 0x05` scores 119 and is **rank 1 of 256** (z = +4.5), weaker only because
the low cells sit near the walk start and `0x03`/`0x04`/`0x06` score 90…93.

This also gives item **B** (the register file and the D-RAM are one RAM) its
first test that does not route through the host.

### 2.4 ★ The control that killed my other idea

Before the above I tried a simpler check: *33 of 37 unit-0 bodies READ cell
`0x05` before writing it, and 37 of 37 touch it.* It looked like support.
Control over all 256 candidate origins:

```
   mean 32.99   sd 0.19   max 33   rank of 0x05: 250 of 256   z = +0.1
```

It is a **baseline**: the walk starts at `E`, so the first mode-2 word touches `E`
at every origin, and "read-before-write of the entry cell" is a property of the
image's first word. **Reported, not quietly dropped** — it is the same failure
mode as `output-stage-decode.md`'s own P-10 (a shuffled control that did not
destroy the peak), committed one pass later by a different route.

---

## 3. ★ THE RE-MEASUREMENT

Live, `DSPCFG On`, cold boot + a 28 s keybed regression programme, **1 344 001
frames**. The **same** programme and the **same** pre-init nvram were used for the
before and after runs; `kn7000-emulator/nvram` was not touched.

| | before | after |
|---|---|---|
| words executing **something** | 199 of 285 | **199** of 285 |
| words executing **FULLY** | 108 | **108** |
| words executing **nothing** | 86 | **86** |
| distinct undecoded words **in the frame** | 119 | **119** |
| distinct undecoded words over the whole run | 122 | **122** |
| ended on the wait word / CAP / OVERRUN | 1 106 880 / 210 241 / 26 880 | **identical** |
| **frames completed** | 0 | **0** |
| ★ **CLOSURE RESIDUE, last frame** | **+121** | ★ **+0** |
| ★ **complete frames that CLOSED** | **960** of 1 106 880 | ★ **1 080 959** of 1 106 880 |
| residue min / max over complete frames | −1 / +121 | **−1 / +116** |
| ★ **frame-entry pointer X** | drifting (untestable) | ★ **0xFF on 1 080 098 (97.58 %)** ⇒ latch cells **0x01 / 0x04** |
| input-stage audit | 1 117 440 both-reads, 0 MISMATCHED | **identical**, 638 678 non-zero, peak `0x56FC00` |

### 3.1 The residue — say it loudly

```
    net D-RAM pointer displacement, last frame +0
    over every COMPLETE frame (1106880 of them): min -1  max +116  (VARIES between frames)
    frames that closed 1080959 of 1106880
    (frames that did NOT complete, and so denied the NEXT frame its
     entry pointer: 210241 capped + 26880 overrun)
```

**The 25 921 that do not close are predicted, not excused.** A complete frame can
only close if its *entry* pointer was the steady-state one, i.e. if the frame
before it also completed — and 237 121 frames end on the slot cap or on the I-RAM
overrun guard (all of them at boot, before the host has finished uploading).
The report now prints that denominator alongside the count so a shortfall reads
as arithmetic; and it will read as a **broken counter** if it ever reports
100.00 % on a run that also reports capped frames.

### 3.2 The rebase audit — a criterion that can fail, and did not

```
    unit 0 (I-RAM  84): 1112640 calls, the walk ALREADY delivered 0x05 on 1079999 (97.06 %)
    unit 1 (I-RAM 200): 1085760 calls, the walk ALREADY delivered 0x85 on       0 ( 0.00 %)
```

The unit-1 rebase does real work on **100 %** of calls — forced, since no walk can
deliver `0x85`. The unit-0 rebase is a **no-op on 97.06 %**, which is the closure
model's own prediction (the header walk from `X = 0xFF` lands on `0x05` by
itself) and is *measured* rather than assumed. Had unit 0 come out load-bearing,
the closure arithmetic would have been wrong somewhere.

### 3.3 Coverage — unchanged to the digit, as predicted

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

**This is the honest shape of the result.** A pointer is not a decode. The frame
now addresses the *right* cells; it still cannot *compute*.

### 3.4 Does any frame complete? **NO.**

0 of 1 344 001. 100.00 % trap and every return is discarded, so the audible
output is exactly the dry tone generator and the EQ-vs-biquad check has nothing
to run on. That is the same answer as before this pass and it will stay that
answer until an ALU code is decoded, not a pointer.

---

## 4. PREDICT-THEN-CHECK

Recorded before the code was touched.

| | prediction | result |
|---|---|---|
| **P-1** | residue → +0 on the last frame; "frames that closed" rises to **most but not all** of the denominator, the remainder being complete frames whose predecessor did not complete | **HIT**, including the caveat: 1 080 959 of 1 106 880 |
| **P-2** | min/max stop being −1/+121 | **HIT** (−1 / +116) |
| **P-3** | `dp` at the body entries becomes 0x05 / 0x85 in the trap log | **MISS — of my instrument, not the claim.** The trap log is a **first-sighting** list, one line per distinct word, populated during boot; its `dp=` is not a steady-state reading. Re-tested with the rebase audit (§3.2) and the closure arithmetic: **the claim holds** |
| **P-4** | X settles on 0xFF ⇒ latch cells 0x01 / 0x04 | **HIT**, 97.58 % — and it had **no instrument**, so one was added (§3, `WHERE THE WINDOW SAT`) rather than assumed |
| **P-5** | the input-stage audit still says MISMATCHED 0 | **HIT** (and it can fail: the pointer now lands on the real map, so a frame store overwriting a latch before w4/w8 read it would show) |
| **P-6** | 199 / 108 / 86 and 122 distinct unchanged | **HIT**, to the word |
| **P-7** | no frame completes | **HIT**, 0 of 1 344 001 |
| **P-8** | DSPCFG Off bit-identical; On identical to Off | **HIT** |
| **P-9** | the unit-0 rebase is a no-op in steady state | **HIT**, 97.06 % — and the shortfall is exactly the non-completing frames |
| **P-10** | wait / cap / overrun counts unchanged | **HIT** |

**Two further misses worth the ink**, both found by controls I ran on myself:

* **the read-before-write test** (§2.4) — a baseline, z = +0.1. Killed.
* **the `0xD0` control, first attempt** — I coded the write branch before the read
  branch and concluded `0x85` was *not* in the read-never-written set. The store
  is latched **after** the bus in `exec_alu()`; fixing the order reversed the
  answer. A control that is wrong in the *helpful* direction is the dangerous
  kind, and this one was wrong in the unhelpful direction only by luck.

---

## 5. ★ The mirror gap (item G)

`tools/upd6383d_diff.sh` built a C++ harness and diffed `text()` against
`dsp_disasm.py`'s `text()`, 3057 lines. That covers `decoded()` — a decoded word
renders as a mnemonic, an undecoded one as `?word`/`~word` — but it does **not**
cover `has_addressing()` or `addressing_only()`: the corpus contains `?word` lines
with and without an addressing effect and they render **identically**. Those two
predicates decide whether an undecoded word's pointer post-increment and cursor
advance are performed, i.e. whether the frame is PARTIAL or TRAP, and since the
ADVANCE pass they run on **every** word. A divergence there would have moved every
pointer in the machine while the mirror check said AGREE.

Found by accident: reconstructing the live frame's `108/91/86` split statically
gave `106/93/86`. The harness now emits `D/A/K` flags beside every word and both
sides changed together:

```
    MIRRORS AGREE -- 3057/3057 words render identically in C++ and Python
                    (text AND the three execution predicates D/A/K)
```

⇒ the 2-word difference is **not** mirror drift; it is that the live unit-0 body
is not byte-identical to the ROM image I reconstructed with. That remains OPEN
and is on the blocker list.

---

## 6. What is applied, precisely

* `upd6383.h`: `DRAM_UNIT_BASE = 0x05`, `DRAM_UNIT_STRIDE = 0x80`, with the
  three-step derivation and an explicit statement of **what is not forced** (the
  site).
* `upd6383.cpp` `run_frame()`: on a CALL (stack empty) `m_dp = base`. **Not** on
  the RETURN — the closure arithmetic needs the body's exit pointer to survive
  into the header words after it.
* two counters per unit (`calls`, `walk already agreed`) and a 256-bucket
  frame-entry-pointer histogram, both printed in the frame report. Diagnostics
  only, no criterion compiled in, `logerror` like the rest of the report.
* comments: the ldptr block (the origin is no longer OPEN), the K6 latch block
  (there is a steady state again, and X is 0xFF), the closure block, and
  `alu_decoded()` guard 6's new **positive** reason — the last one in **both**
  mirrors, identically.
* `retraction_sweep.py`: premise **P15** added, plus both selftest controls. Its
  `exempt` list was shortened at the same time, because `exempt` *drops* a line
  before classification and can therefore hide a retraction that ought to be
  visible; the two forms kept are the ones that are not assertions at all.

**Not applied, deliberately:** `SRC 0x00` (conflicting contexts), the `w63`/`w70`
readings R-1/R-2 (enumerated, neither chosen), `w46`/`w54` as the rebase
instruction (EDUCATED GUESS, and §2.2 shows it needs a different value), and
every ACTION/SRC code the three passes leave OPEN.

---

## 7. ★ NEXT BLOCKER LIST, ranked

Ranked by *what stands between the machine and a frame that completes*, which is
the only metric that matters now: 177 of 285 slots are still undecoded and **any
one of them** discards the frame.

| # | blocker | why it is first | what would settle it |
|---|---|---|---|
| **1** | **`880.1.NN.*` — the external delay-DRAM family.** 324 corpus sites, present in the kernel at I-RAM 12 and 26 and at the head of 37 of 38 bodies. Direction (read vs write) is **not** in `addr8` (R3 §6.3 falsified that) | it is the single largest undecoded family on the frame path and it sits *before* almost everything else, so no downstream word can be validated while it is opaque | the tag-0x4C descriptor bank is PROVEN; solve the address form `DESCRIPTOR_CELL[cursor] + G` against MULTI TAP DELAY, whose tap structure is externally known |
| **2** | **`ACTION 0x00`'s accumulator half — `load` vs `add`-like.** T1 calls it "the highest-value discriminator left"; two contexts (joint solve 18/18 for `load`, all-pass 9 520/9 660 for `−bus`) and the second is a property of a **rejected** set | it is the one ALU parameter on which two independent solves point different ways, and it gates the accumulator on 107 corpus words | a **fourth** context in which the two differ observably — the LFO ramp at `actfirst = 0` is the nearest candidate and has not been run against it |
| **3** | **`SRC 0x00`.** reverb needs `DR` in 52 696/52 696; SINGLE DELAY forbids it in 0 of 5 635 | a flat contradiction, and until it breaks every word carrying `SRC 0x00` traps | the reverb's arm is evidence only if the reverb core is an all-pass, which is **falsified** — so re-run the reverb arm under `sec_schroeder` (T1's own recommended next acceptance test) and see whether `DR` survives |
| **4** | **The five C-format words with selector `0x20`** (I-RAM 15, 22, 29, 31, 40) plus `801.0.6C.827` / `801.0.64.827` | they were the favoured carriers of the pointer reload; the reload's **value** is now known, so these words can be tested against a known answer instead of searched blind | ask which of them, given a semantic, reproduces `base = 0x05 \| (unit<<7)` at the CALL — a 1-unknown fit now, not a search |
| **5** | **`w63` / `w70` — R-1 vs R-2** (`output-stage-decode.md` §7.2), the only two words carrying `0x05` and `0x85` in an aligned field | they are the *only* candidates in the machine for the instruction that performs what this pass just applied at the CALL | R-1 is contradicted by `hi12` bit 0 differing; R-2 by guard 6's forcing. A third reading has not been enumerated — do that first |
| **6** | **Which unit-0 body the live machine actually runs.** Static reconstruction of the live frame gives `106/93/86` against the live `108/91/86` on the closest ROM image (algo 1, 70 words), with the trap count and the 119 distinct exact | it means the I-RAM the host uploads is **not** byte-identical to an algorithm-table image, and every static frame reconstruction inherits that error | dump I-RAM live at the wait word and diff it against the table — one `-autoboot_script`, no new decode |
| **7** | **`w67` (`980.5.20.402`) and `w78`** — the machine's only two mode-5 words, both in the output stage; and `SRC 0x0A`, which occurs **once** in 3057 words | the output stage is still the least-decoded region on the chip at **8.7 %** tier-1 | nothing in the corpus separates them; this one needs the datasheet or a hardware trace, and should be stated as such rather than searched |

**Above all of them, the standing fact:** the frame floor is 38.4 % tier-1 and
**no frame completes**. Every item on this list is worth exactly as much as it
moves that number.

---

## 8. Safety

| check | result |
|---|---|
| DSPCFG **Off**, published build vs this build, 28 s programme with real audio | **BIT-IDENTICAL** (md5 `ed4353643dd5ffbf2a526634e5831203`; 1 276 567 non-zero samples, peak 22 268 — a capture that can fail) |
| DSPCFG **On** vs **Off**, this build | **BIT-IDENTICAL** |
| trapped frames contribute ZERO | unchanged — 100.00 % trap, every return discarded |
| 384-slot cap / I-RAM overrun guard / wait-word termination | all still fire, counts **identical** to the baseline (210 241 / 26 880 / 1 106 880) |
| `./kn7000 -validate kn5000` | exit 0, **silent** |
| boots | yes — cold boot to the play screen in both runs |
| `tools/upd6383d_diff.sh` | **MIRRORS AGREE — 3057/3057**, now including `D/A/K` |
| `dsp/verify.py` | **BYTE-MATCH OK** |
| `retraction_sweep.py selftest` | **PASSED**, both directions, including the new P15 |
| `retraction_sweep.py code` | 23 hits, **9 LIVE — all 9 read and confirmed retraction prose** |
| processes left running | none |

The change cannot move the audio **by construction**: it writes one 8-bit
register inside `run_frame()`, `run_frame()` is only called when the DSPCFG
ioport is On (default **Off**), and every frame's return is discarded anyway.
The bit-identity check above is run regardless, because "by construction" is an
argument and the WAV is a measurement.

---

## 9. Reproducing

```bash
# the re-derivation (static, no emulator)
cd ~/compartilhado/kn5000-roms-disasm
python3 dsp/tools/output_stage.py dram        # the host-side derivations
python3 dsp/tools/output_stage.py closure     # the frame walk
python3 dsp/tools/output_stage.py control     # ... with the answer destroyed
python3 dsp/tools/dsp_coverage.py
python3 dsp/tools/retraction_sweep.py selftest && python3 dsp/tools/retraction_sweep.py code

# the mirrors and the byte match
~/compartilhado/kn7000_mame/tools/upd6383d_diff.sh   # MIRRORS AGREE (text + D/A/K)
python3 dsp/verify.py                                # BYTE-MATCH OK

# the live measurement
cd ~/compartilhado/kn7000-emulator
./kn7000 kn5000 -rompath ./roms -window -nomaximize -skip_gameinfo -nothrottle -log \
    -nvram_directory <scratch>/nv -cfg_directory <scratch>/cfg_on \
    -autoboot_script <scratch>/audio.lua -wavwrite <scratch>/on.wav
#   <scratch>/cfg_on/kn5000.cfg:
#     <port tag=":DSPCFG" type="CONFIG" mask="1" defvalue="0" value="1" />
#   <scratch>/audio.lua: a fixed keybed chord sequence 10..27 s, exit at 28 s;
#   the ioport lookup MUST use the full tag, machine.ioport.ports[":KEY2"].
grep -A31 'FRAME REPORT' error.log
```
