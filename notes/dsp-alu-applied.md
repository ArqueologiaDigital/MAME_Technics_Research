# The uPD6383 ALU, reconciled and applied — `lo12` routes, `hi12[3:1]` operates

**NEC uPD6383GF-3BA** (Technics SX-KN5000, IC311). Date 2026-07-26. No hardware:
static analysis of the ROM corpus, constraint solving, and the live emulator.

Brief: *"reconcile the three `lo12` passes into one semantics, implement it,
measure it."* The three passes are `notes/dsp-alu-structure.md` (vocabulary
statistics), `notes/dsp-alu-biquad.md` (the PARAMETRIC EQ block) and
`notes/dsp-alu-crossval.md` (all-pass / LFO / input stage).

Labels: **MEASURED** (counted), **PROVEN BY CONSTRUCTION** (read out of the
bytes that build it), **FORCED** (the only assignment a stated rule admits),
**DETERMINED**, **CONSISTENT**, **INFERRED**, **OPEN**. Where a constraint
system admits several assignments they are **enumerated**, never silently
picked.

**Concurrency.** `kn5000-roms-disasm/dsp/instruction-set.md`, `dsp/tools/` and
`dsp/analysis/` were read, never written. §9 is the sync list.

---

## 0. The result in one page

| # | statement | status |
|---|---|---|
| **R1** | **The operation is NOT in `lo12`.** It is in `hi12[3:1]`. All three passes set out to "decode the `lo12` ALU field"; that framing is wrong and the correction is the main result. | **FORCED** |
| **R2** | `hi12[3:1]` codes: **0 = `acc ← P`**, **1 = `acc += P`**, **2 = `acc` unchanged** (established on class 8 only). The other five codes are unknown. | **FORCED** (0,1) / **DETERMINED** (2 on class 8) |
| **R3** | **The product register is NOT consumed** by the accumulate. It holds until the next multiply. | **CONSISTENT** (see §2.4 — the biquad cannot distinguish it; nothing else contradicts it) |
| **R4** | `lo12` = `G[11] · SRC[10:6] · M[5] · ACTION[4:0]`, three passes agreeing independently. `SRC`: `07` mem[p], `10` acc, `19` tempA, `1A` tempB. `ACTION`: `07` mem[p]←bus, `13` tempA←bus, `14` tempB←bus, `12`/`15` no side effect. | **MEASURED** (boundaries) / **FORCED** (the nine codes, on the biquad) |
| **R5** | The biquad **pins the `hi12[3:1]` mapping**: swapping codes 0 and 1 destroys the transfer function (**999 dB**, i.e. the output is zero at every measured frequency). This is new — the previous pass could only say the `f31` reading was *indistinguishable from* the uniform one, not that the biquad constrains it. | **MEASURED** |
| **R6** | The biquad **independently forces R1's operand-before-store ordering**: latching the bus operand after the `hi12` bit-4 store instead of before costs **999 dB**. R1 (`dsp/analysis/r1-allpass-motif.md` F2) forced the same ordering on a completely different block, the reverb all-pass. Two blocks, one rule. | **MEASURED** |
| **R7** | **A defect in the shipped decode, found and fixed.** The previous predicate tested `lo12` *alone*, so it also executed **class-1 external delay-RAM words** — `900.1.60.1D5` (35 sites), `880.1.20.407` (16), `800.1.60.1D5` (6) — as ordinary on-chip arithmetic. R1 FORCED those to be DRAM accesses. 62 words in three wrong classes (1, 5, 6) were being executed as arithmetic; they now trap. | **MEASURED** |
| **R8** | **A live out-of-bounds read in the disassembler**, fixed. `text()` rendered the operand as `SRC[lo_src(word)]` over a **four**-entry array, but `lo_src()` had been widened from two bits to five; the four anchored codes are `0x07/0x10/0x19/0x1A` and **every one is past the end of the array**. It ran on every trap-log line and in `unidasm`. | **MEASURED** |
| **R9** | The LFO's two constants are exactly an increment and a wrap: `C-RAM[0x00] = 0x72`, and `114/2²³ × 44100 = **0.5993 Hz**` — the 0.6 Hz the firmware asks for. Two candidate wrap operations survive (a 2²³ `AND`, and a conditional subtract); both are enumerated, neither is executed. | **MEASURED** / **OPEN** |
| **R10** | **Coverage went DOWN, correctness went up.** Corpus 1146 → **1030** words (37.5 % → 33.7 %); live frame **89 → 87** of 285. 166 words left the executable set (62 category errors + 104 unanchored operation codes) and 50 joined on four new routing codes. | **MEASURED** |

**The acceptance test passes.** Worst error **0.094 dB / 4.03°** over 8 distinct
ROM coefficient banks, 11 section instances, 4 programs — run on the arithmetic
that *ships*, not on a re-implementation (§5).

**The reverb test does not run, and no impression is offered in its place**
(§6): zero of the 45 all-pass core words of `ROOM REVERB 1` is executable, so
there is no tail to measure. The one thing that *is* measured is that there is
also no *spurious* tail: DSPCFG On is byte-identical to Off.

---

## 1. What the three passes agreed on, and how many agreements that is

The field map is the strongest thing here because **three methods that share no
code and no data reduction produced it independently**:

| | method | result |
|---|---|---|
| `dsp-alu-structure.md` | Hamming-1 closure + inter-half mutual information over the 82-value vocabulary | boundary at bit 5/6, bits 11+5 = the control family, `[10:6]` = source, `[4:0]` = action |
| `dsp-alu-biquad.md` | fitting the PARAMETRIC EQ section against the firmware's own bilinear designer | the same boundaries, and **which** code is which for 4 sources + 5 actions |
| `dsp-alu-crossval.md` | minimal pairs in the all-pass, the LFO and the input stage | the same boundaries, plus the falsification that put the operation in `hi12` |

**Count of independent agreements on the map: 3 of 3 on the boundaries, 2 of 3
on the code assignments** (the statistics pass constrains the boundaries but
cannot name codes). Where they *conflicted* — the biquad said the operation was
absent from the instruction, the cross-validation said it was in `hi12` — the
conflict was informative in exactly the way the brief predicted: it meant a
sub-field boundary was in the wrong *word*, not in the wrong bit.

### 1.1 The one conflict, adjudicated

`dsp-alu-biquad.md` §4 shipped a **uniform** ALU: every word does `acc += P`,
`P := 0`, and no per-word operation exists. `dsp-alu-crossval.md` B1 showed that
cannot be complete. **The adjudication goes to the cross-validation**, and the
argument is short enough to check:

> `092.A.dd.200` and `094.A.dd.200` are identical in `class4`, in `addr8` and in
> **all twelve `lo12` bits**. In 12 of 20 images they address the **same** D-RAM
> cell with the pointer frozen. They consume `C-RAM[+0]` and `C-RAM[+1]`, which
> the cold-boot capture MEASURED as `0x000072` and `0x7FFFFF`. That cell must
> end up a 0.6 Hz ramp. Under the uniform ALU the two words are the *same
> instruction*, so the cell would receive `phase + 0x72 + 0x7FFFFF` per frame ≈
> 22 kHz. **The uniform ALU cannot run the LFO.**

The biquad could not see this because, in its nine words, "load `P`" and "add
`P`" happen to coincide at both places they differ (§2.4). So the uniform
reading was never wrong *about the biquad* — it was under-determined, and a
second block determined it.

**This is a falsification of the framing all three passes inherited from the
brief** ("the arithmetic is the `lo12` field"), and it is the kind of result
this project has learned to value: the earlier claim was not sloppy, it was
under-constrained, and naming the missing constraint is what closed it.

---

## 2. The operation field — `hi12[3:1]`

### 2.1 The LFO arithmetic, checked numerically

`C-RAM[0x00] = 0x000072 = 114`. At the firmware's own 44 100 Hz
(`LABEL_03925E` converts milliseconds with `ms × 0xAC44 / 0x3E8`):

```
    114 / 2^23 × 44100 = 0.5993 Hz
```

which is the 0.6 Hz the CHORUS parameter asks for, to three digits. So
`C-RAM[+0]` is a **per-frame phase increment** and `C-RAM[+1] = 0x7FFFFF` is a
**2²³ wrap**. MEASURED. (The earlier notes asserted "the increment is `f/44100`
in Q0.23" from the *encoder* side; this is the same statement checked from the
*decoder* side, and it is the reason the pair has to be two operations.)

### 2.2 What the wrap word can be — ENUMERATED, none chosen

Simulating `phase = op₂(phase + 114, 0x7FFFFF)` for 400 000 frames and measuring
the ramp rate at the zero crossings:

```
    AND        acc &= K                0.5993 Hz   <-- survivor
    MOD/wrap   if acc >= K: acc -= K   0.5993 Hz   <-- survivor
    ADD        acc += K            22050.2756 Hz
    SUB        acc -= K            22050.2756 Hz
    OR         acc |= K            22050.0000 Hz
    XOR        acc ^= K            22050.0000 Hz
    MIN / LOAD / NONE               no ramp at all
    MAX                             an artefact of the 24-bit mask, not a phase ramp
```

**Two survivors.** Both are the identity on an in-range value, which is why
either one is compatible with the biquad's class-8 word (§2.3). Neither is
implemented: a wrap needs an operand route, and the route `lo12 = 0x200` selects
(`SRC = 0x08`) is not anchored.

### 2.3 Why code 2 is executed on class 8 and nowhere else

The biquad's word `[6]` is `804.8.16.415`, `hi12[3:1] = 2`, and the
reconstruction **DETERMINES** that the accumulator comes out of it unchanged
(any operation that is *not* the identity there costs 82 dB or 999 dB — §5.2).
Whether that is because code 2 is a no-op, or because it is the wrap of §2.2 and
the sum is in range, is **OPEN**. Both readings give the same result on this
word, so executing it as "unchanged" is correct under either — and that is the
whole justification, which is why the device admits code 2 **only on class 8**
and traps the other 73 sites.

MEASURED: in the corpus, `class4 == 8 && hi12[3:1] == 2` is exactly the 35
`804.8.**.415` words, so the class guard and the exact-form guard coincide here.

### 2.4 Where the biquad *can* and *cannot* see the operation — with numbers

The section, with `hi12[3:1]` on each word:

```
 [0] 000.A.00.1D3  f31=0   ld.ta  (p)   P = b1*x1 ; tempA <- x1
 [1] 212.A.01.412  f31=1   mac    acc   ST: mem<-acc, acc:=0 ; acc += P ; P = b0*x
 [2] 202.A.01.1D5  f31=1   mac    (p)   acc += P ; P = b2*x2
 [3] 202.A.01.1D4  f31=1   mac.tb (p)   acc += P ; P = A1*y1 ; tempB <- y1
 [4] 202.A.00.1D5  f31=1   mac    (p)   acc += P ; P = A2*y2
 [5] 102.2.FF.687  f31=1   mac.st tb    acc += P -> the sum is complete
 [6] 804.8.16.415  f31=2   post   acc   the post-sum step -- acc unchanged
 [7] 212.A.FF.407  f31=1   mac.st acc   ST: mem<-acc, acc:=0 ; P = G*v
 [8] 000.2.03.647  f31=0   ld.st  ta    acc <- P = the band output
```

*Cannot see*: whether `P` is consumed. At `[0]` the product register still holds
the previous band's `G·v`, which is also what the accumulator holds, so "load
it" and "add nothing to it" are the same number; at `[8]` the accumulator was
cleared at `[7]`, so "load" and "add" are the same number. **MEASURED: the two
readings agree to 0.094 dB, i.e. bit for bit** (§5.2, row 4).

*Can see*: **which code is which.** Swap codes 0 and 1 and the section produces
zero output at every measured frequency (**999 dB**, §5.2 row 2). Ignore the
field entirely and accumulate on every word and it is **82 dB** wrong (row 3).
So the biquad does not merely tolerate the `hi12[3:1]` reading — it **pins the
assignment**, and the LFO independently says the field exists. Those are two
different blocks agreeing, which is the proof the brief asked for.

---

## 3. The routing field — `lo12`, and the two defects it was hiding

### 3.1 The map

```
   11 10            6 5 4               0
  +--+---------------+-+-----------------+
  |G |      SRC      |M|     ACTION      |
  +--+---------------+-+-----------------+
```

`SRC` (4 of 18 observed codes read): `07` `mem[ptr]` · `10` accumulator ·
`19` tempA · `1A` tempB.
`ACTION` (5 of 24 read): `07` `mem[ptr] ← bus` · `13` `tempA ← bus` ·
`14` `tempB ← bus` · `12`, `15` no side effect.
`M` (bit 5) marks the pointer/cursor/table family, 96 of 3057 words, no
exceptions either way. `G` (bit 11) is locked to it, 95 of 96.

### 3.2 The predicate that ships, and what each guard is for

```
  class4 ∈ {2, 8, A}                        ... the on-chip datapath classes
  lo12 bit 11 clear and lo12 bit 5 clear    ... not the control family
  SRC ∈ {07,10,19,1A} and ACTION ∈ {07,12,13,14,15}
  hi12[3:1] ∈ {0, 1}, or 2 on class 8
```

**The class guard is the fix for a real defect.** The old predicate looked at
`lo12` and nothing else, so:

```
   words the OLD predicate executed and the NEW one refuses:  166
      hi12[3:1] = 2 off the class-8 post-sum form              73
      class 1  -- the external delay-RAM bracket               54     <-- category error
      hi12[3:1] = 4                                            16
      class 6  -- the table-lookup idiom                        7     <-- category error
      hi12[3:1] = 5                                             7
      hi12[3:1] = 3                                             6
      hi12[3:1] = 7                                             2
      class 5                                                   1     <-- category error
```

The class-1 entries are `900.1.**.1D5` (29 words), `880.1.**.407` (16) and
`800.1.**.1D5` (6). R1's constraint solve FORCED `880.1.60.2D4` to be the
external-DRAM **read** and `880.1.20.655` the **write**, with zero surviving
alternatives; `900.1.60.*` is the same bracket (the cross-validation pass listed
missing it as one of its own six recorded misses). Executing a delay-RAM access
as an on-chip multiply-accumulate is precisely the plausible-but-wrong behaviour
this device exists to refuse — and it was in the shipped build for one commit.

**Newly executable: 50 words on 4 routing codes** the old whitelist did not
contain — `655` (38, `SRC` tempA), `695` (5, tempB), `413` (4, acc + capture
tempA), `692` (3, tempB).

### 3.2a What the disassembler now prints

The whole PARAMETRIC EQ section renders with real mnemonics — the operation from
`hi12[3:1]`, the routing from `lo12`, the coefficient fetch and the pointer walk
from `class4`/`addr8`, and the store from `hi12` bit 4:

```
   0  ld.ta   (p),c+,(p)+0                          ; C-RAM[0x00]
   1  mac     acc,c+,(p)+1 ; mem[p]<-acc, acc=0     ; C-RAM[0x01]
   2  mac     (p),c+,(p)+1                          ; C-RAM[0x02]
   3  mac.tb  (p),c+,(p)+1                          ; C-RAM[0x03]
   4  mac     (p),c+,(p)+0                          ; C-RAM[0x04]
   5  mac.st  tb,(p)-1
   6  post    acc
   7  mac.st  acc,c+,(p)-1 ; mem[p]<-acc, acc=0     ; C-RAM[0x05]
   8  ld.st   ta,(p)+3
```

`ld` = `acc ← P`, `mac` = `acc += P`, `post` = the class-8 step; the `.ta`/`.tb`/
`.st` suffix is the `lo12[4:0]` side effect; `,c+` is the class-A coefficient
fetch. Before this change the same nine words printed as `mac`/`alu` with an
out-of-bounds operand name (§3.3) and no operation at all.

### 3.3 The out-of-bounds read

`upd6383d.cpp text()` had `static const char *const SRC[4]` indexed by
`lo_src(word)`. `lo_src()` was widened from `(w>>6)&3` to `(w>>6)&0x1f` when the
five-bit reading landed; the table was not. The four anchored source codes are
`0x07`, `0x10`, `0x19`, `0x1A` — **all four index past the end of a 4-entry
array**. It ran on every `LOG_TRAP` line and in `unidasm`. Replaced with a
`switch`, which cannot acquire the defect again.

---

## 4. The final table — `(class4, lo12)` → what the device does

Every `(class4, lo12)` pair in the 3057-word corpus that the device executes.
`n` = corpus occurrences; `exe` = how many of them pass the operation guard
(the rest carry an unanchored `hi12[3:1]` and trap).

| class4 | lo12 | n | exe | SRC | ACTION | status |
|---|---|---|---|---|---|---|
| A | `1D5` | 291 | 254 | `mem[p]` | — | **FORCED** (biquad `[2]`,`[4]`) |
| 2 | `407` | 203 | 189 | acc | `mem[p]←bus` | **FORCED** (biquad `[7]` at class A) |
| A | `415` | 146 | 146 | acc | — | **FORCED** (biquad `[6]` at class 8) |
| 2 | `1D5` | 109 | 60 | `mem[p]` | — | **FORCED** |
| A | `412` | 49 | 49 | acc | — | **FORCED** (biquad `[1]`) |
| 2 | `687` | 43 | 39 | tempB | `mem[p]←bus` | **FORCED** (biquad `[5]`) |
| A | `1D4` | 42 | 42 | `mem[p]` | `tempB←bus` | **FORCED** (biquad `[3]`) |
| 2 | `647` | 38 | 38 | tempA | `mem[p]←bus` | **FORCED** (biquad `[8]`) |
| A | `407` | 37 | 37 | acc | `mem[p]←bus` | **FORCED** (biquad `[7]`) |
| A | `1D3` | 36 | 36 | `mem[p]` | `tempA←bus` | **FORCED** (biquad `[0]`) |
| 8 | `415` | 35 | 35 | acc | — | **DETERMINED** (post-sum, identity) |
| 2 | `412` | 30 | 30 | acc | — | **CONSISTENT** (field decode) |
| A | `655` | 25 | 25 | tempA | — | **CONSISTENT** (field decode) |
| 2 | `415` | 24 | 24 | acc | — | **CONSISTENT** |
| 2 | `1D4` | 4 | 4 | `mem[p]` | `tempB←bus` | **CONSISTENT** |
| 2 | `1D3` | 4 | 4 | `mem[p]` | `tempA←bus` | **CONSISTENT** |
| 2 | `413` | 4 | 4 | acc | `tempA←bus` | **CONSISTENT** |
| A | `695` | 5 | 5 | tempB | — | **CONSISTENT** |
| A | `692` | 3 | 3 | tempB | — | **CONSISTENT** |

**19 of the 123 `(class4, lo12)` pairs execute; 104 trap.** The three control
forms outside this table are unchanged: `000.2.00.000` `nop` and
`801.0.NN.821` `ldptr` (both **PROVEN BY CONSTRUCTION**) and `801.0.00.021`
`rstcur` (**MEASURED**).

### 4.1 A tension this creates, reported not buried

`000.2.00.000` is decoded as an inert `nop` on the evidence that the sub-CPU
writer builds that exact pattern as filler (`LABEL_038922`). But `hi12 = 0x000`
means `hi12[3:1] = 0`, and under R2 that is `acc ← P` — **so the "nop" is not
obviously inert any more.** Three observations, no resolution:

* its 62 sites are mostly **runs** of 2–3 consecutive nops (algo 3 at 94–96,
  algo 8 at 19/20, 27/28, 45/46, 53/54, 61/62, algo 10 at 10/11, 14/15, 18/19),
  and `acc ← P` is **idempotent**, so a run costs no more than a single one;
* the device keeps executing it as inert, which is the **conservative** error —
  it can only under-execute, never invent a value;
* the routing half of the word (`SRC = 0x00`, `ACTION = 0x00`) is unanchored, so
  the field decode would refuse it anyway; the `nop` survives only on its own
  separate, older evidence.

The clean way to settle it is to anchor `SRC = 0x00` (531 corpus words, the
single largest open routing code).

---

## 5. THE ACCEPTANCE TEST — numbers, on the arithmetic that ships

### 5.1 The harness, and why it is stronger than the last one

`tools/kn5000_dsp_alu_mirror.py` **generates** the test harness by lifting the
text of `upd6383_device::acc_to_datum()` and `exec_alu()` verbatim out of
`src/devices/cpu/upd6383/upd6383.cpp`, plus the field accessors and enums out of
`upd6383d.h`. The previous pass used a hand-written mirror; a hand copy is a
second implementation and it can drift silently. This one cannot: if the device
changes and the generator is not re-run, the harness stops compiling or stops
matching.

Impulse of 2²², 4096 samples, hand-rolled DFT (stdlib only) at 12 frequencies
from 20 Hz to 20 kHz, against `H(z)` computed directly from the same C-RAM words
by the firmware's own coefficient convention (`b1,b0,b2,−a1/a0` at 2²²,
`−a2/a0` at 2²³, make-up at 2²²).

```
   algo39 PARAMETRIC EQ  band 0      max |err| = 0.00205 dB   0.008 deg
   algo39 PARAMETRIC EQ  band 1      max |err| = 0.00463 dB   0.005 deg
   algo39 PARAMETRIC EQ  band 2      max |err| = 0.00123 dB   0.006 deg
   algo39 PARAMETRIC EQ  band 3      max |err| = 0.00119 dB   0.006 deg
   algo39 PARAMETRIC EQ  band 4      max |err| = 0.00116 dB   0.006 deg
   algo33 OVERDRIVE tone stage       max |err| = 0.00066 dB   0.024 deg
   algo35 EXCITER band               max |err| = 0.09405 dB   1.720 deg
   algo99 PEQ+OVERDR+DELAY flat PEQ  max |err| = 0.07502 dB   4.025 deg

   distinct coefficient banks   8      section instances  11      programs  4
   WORST over all of them       0.09405 dB   4.0252 deg
```

Per-frequency on the worst bank (EXCITER, the highest-Q of the eight): the error
is `+0.094 dB` at 20 Hz, `+0.057` at 50 Hz, and **below 0.005 dB from 100 Hz
up** — i.e. it is concentrated where a high-Q recursion's state quantisation
shows, not spread across the band as a structural error would be. The level
sweep says the same thing:

```
   impulse 2^10 : 41.155 dB      impulse 2^18 :  2.049 dB
   impulse 2^14 : 18.027 dB      impulse 2^22 :  0.094 dB
```

A structural error is **scale-invariant**; this one falls 4 dB per bit of signal
level. **The residual is 24-bit state quantisation.**

**Implementation equivalence**: the generated C++ and the Python model in
`tools/kn5000_dsp_alu.py` (whose default is now the shipping reading) agree at
`max |diff| = 0` over 11 section instances × 512 samples.

### 5.2 Ablations — a criterion that cannot fail is not a pass

Each row is a **textual mutation of the generated harness**, so it mutates the
device's own code. Worst error over all 8 banks:

```
   full model (what ships)                                              0.094 dB
   hi12[3:1] codes 0 and 1 SWAPPED (acc<-P <-> acc+=P)                999.000 dB
   hi12[3:1] IGNORED, uniform acc+=P, P kept                           82.040 dB
   hi12[3:1] IGNORED, uniform acc+=P, P CONSUMED  (superseded model)    0.094 dB
   SRC 0x19 / 0x1A swapped (tempA <-> tempB on the bus)                57.624 dB
   ACTION 0x13 / 0x14 swapped (which temp each word captures)          56.764 dB
   ACTION 0x07 (mem[p] <- bus) turned off                              55.893 dB
   class-8 post-sum word made acc+=P instead of unchanged              82.165 dB
   class-8 post-sum word made acc<-P instead of unchanged             999.000 dB
   without the accumulator CLEAR on hi12 bit 4                         65.508 dB
   without the one-bit right shift on the tempB path                   82.165 dB
   the one-bit shift made a LEFT shift                                 61.457 dB
   operand latched AFTER the bit-4 store instead of before            999.000 dB
   total alignment 21 instead of 22                                    81.938 dB
   total alignment 23 instead of 22                                    89.620 dB
   a DIFFERENT split of the same total (P_SHIFT 2 / 20)                 0.094 dB
   a DIFFERENT split of the same total (P_SHIFT 12 / 10)                0.094 dB
```

Reading the table:

* **row 2** is the new result. It is what makes `hi12[3:1]` a *measured*
  assignment on this block and not merely a *tolerated* one.
* **row 4 is a deliberate null.** The superseded uniform model, given its own
  correct initial condition, scores exactly the same 0.094 dB. That is the
  honest statement of what the biquad cannot decide (§2.4) — and the first time
  I ran it I got 7.866 dB, which was **my harness's initial condition, not the
  model**. Recorded as a miss; the fix is in `ablate.py`.
* **row 13** independently reproduces R1's F2 ordering from a different block.
* the last two rows confirm the split of the 22-bit alignment is still **not**
  forced, exactly as `dsp-alu-biquad.md` §7-A2 said.

### 5.3 Why the test is run on the section and not through the machine

The brief's plan — feed the machine an impulse with PARAMETRIC EQ active and
measure the response — **cannot run today, and the reason is measured**: a full
frame still traps (§7), so `run_frame()` discards its return by construction and
the emulator emits exactly the dry signal. `dsp-alu-crossval.md` D1 raised a
second obstacle that is real but secondary — every sample also passes the input
stage's unknown-coefficient recursive section and the 30-word mix block, so the
end-to-end response would be `H_in·H_eq·H_out`. Its **ratio test** (measure at
two cursor settings; `H_in` and `H_out` cancel exactly) is the right instrument
and it is ready to use the day a frame completes.

---

## 6. THE REVERB TEST — it does not run, and here is the exact reason

`ROOM REVERB 1` (algo 16), 133 body words: **50 decoded, 83 trap.** The
all-pass ladder is nine instances of R1's motif, and **not one word of any
instance is executable**:

```
   880.1.60.2D4   x9   the external-DRAM READ            class 1 -- not a datapath class
   880.1.20.655   x9   the external-DRAM WRITE           class 1 -- not a datapath class
   012.2.00.680   x9   d_in <- x + t (the write)         ACTION 0x00 unanchored
   000.2.00.419   x9   y <- d_out - t (its partner)      ACTION 0x19 unanchored
   102.A.00.64B   x8   the ladder gain multiply          ACTION 0x0B unanchored
   104.2.00.000   x9   the all-pass marker               SRC 0x00 unanchored
```

So there is **no tail to measure**, and none is reported. What *is* measured is
the negative control, which is the part that could have gone wrong: with the DSP
gate **On**, the captured WAV is **byte-identical to the gate Off** (4 896 050
bytes, `cmp` clean) — so the partially-executed frames produce **no spurious
tail, no runaway and no NaN**, because the frame return is discarded exactly as
designed.

**What would make the reverb test runnable**, in dependency order: (1) the
class-1 external-DRAM word format — that is R1's `2D4`/`655` pair, already
FORCED as *read* and *write*, needing only an execution model for the delay
address and the read latency R1 measured at 2–5 words; (2) `ACTION` codes
`0x00`, `0x19`, `0x0B`; (3) `SRC` code `0x00`. That is four codes and one word
format for the whole reverb family.

---

## 7. Words executing per frame — MEASURED, live

Same programme both runs (one C4 at 12.0–15.0 s, 17 s total), same isolated
pre-init NVRAM, `-window`, `timeout`-wrapped.

```
                                     published build      this build
   slots per frame                        285                285
   PARTIAL (addressing only)               12                 12
   TRAPS                                  196                198
   EXECUTING                               89                 87
   words executed before the 1st trap      12                 12
   first offender                 iw 12  880.1.20.2D5   (UNCHANGED)
   frames that trapped                  100.00 %           100.00 %
   distinct trapping words                122                123
```

**No frame completes.** Stated explicitly because the brief asked: 100 % of
frames still trap, every frame's return is still discarded, and the audio is
still exactly the dry mix.

The three distinct words that changed state over the whole run:

```
   now DECODED   000.A.00.695     SRC tempB, ACTION 0x15   -- a new routing code
   now DECODED   012.2.01.655     SRC tempA, ACTION 0x15   -- a new routing code
   now TRAPPING  900.1.60.1D5     class 1 -- an external delay-RAM READ  <-- the fix
   now TRAPPING  000.6.20.407     class 6 -- the table-lookup idiom      <-- the fix
   now TRAPPING  504.2.00.1D5     hi12[3:1] = 2 off class 8
```

**The count went down by two and that is the correct outcome.** Three of the 89
words the published build was executing were being executed *wrongly*: two
external-DRAM accesses and one table-lookup word, all performed as on-chip
multiply-accumulates. A smaller number of words that are right is worth more
than a larger number that contains a category error — and the number is now
measured against a predicate that says *why* each refusal happens, so it can go
back up one anchored code at a time.

---

## 8. PREDICT-THEN-CHECK — including the misses

| # | prediction, made before the run | outcome |
|---|---|---|
| P1 | switching to the `hi12[3:1]` reading leaves the biquad error unchanged at 0.094 dB | **HIT**, exact (0.09405 both) |
| P2 | swapping `hi12[3:1]` codes 0 and 1 **breaks** the biquad — if it did not, the field would be unconstrained and R2 would be worthless | **HIT** (999 dB). The single most load-bearing check here |
| P3 | reading `lo12` as fields covers **more** corpus words than the 8-value whitelist | **MISS**. 1030 vs 1146 — the class and operation guards remove more than the field reading adds |
| P4 | words executing per frame goes **up** from 89 | **MISS**. 87. Same cause as P3 |
| P5 | the class-1 external-DRAM words stop being executed | **HIT** (`900.1.60.1D5` moved to the trap set) |
| P6 | DSPCFG Off stays bit-identical to the published build | **HIT** (§9) |
| P7 | latching the operand after the bit-4 store breaks the biquad, independently reproducing R1's F2 | **HIT** (999 dB) |
| P8 | the "uniform, P consumed" model scores 0.094 dB, not something else | **HIT on the second try.** First run said 7.866 dB; that was my harness giving the superseded model the *wrong initial condition*, not a falsification of it. Fixed and recorded |
| P9 | the 104 s regression programme exercises polyphony and 42 rapid notes audibly | **MISS.** The machine goes silent at t ≈ 30 s under **both** binaries; reordering the events did not move it (§9.1). The bit-identity is unaffected; what it *audibly* covers is smaller than intended, and that is now stated |
| P10 | the shipped C++ (generated from the device) and the Python model agree exactly | **HIT**: 11 section instances × 512 samples, `max \|diff\| = 0` |

Three of the ten are misses. P3/P4 are the same miss and it changed the
headline: this pass makes the decode **more correct and less wide**, which is
not what it set out to do. P9 is a measurement limit, not a result.

---

## 9. SAFETY — the OFF state

* **`-validate`**: clean, exit 0, no output.
* **DSPCFG Off, published build vs this build**: WAV **byte-identical**,
  29 952 050 bytes = **14 976 003 samples (3 ch × 4 992 001 frames @ 48 kHz),
  0 differing** — the same scale as the 14 961 609-sample check the brief names.
  The programme drives boot, a 4 s sustained note and its release, a chromatic
  12/12 across the middle octave, 42 rapid notes, a fresh note, a three-note
  chord and an octave, over 104 s.
* **DSPCFG On vs Off, this build**: byte-identical (4 896 050 bytes, `cmp`
  clean). Frames that trap contribute zero, unchanged.
* The 384-slot cap, the I-RAM overrun guard and the frame-wait termination all
  still fire — in the 17 s run: 579 050 frames ended on the wait word, 162 240
  on the slot cap, 26 880 on I-RAM overrun, and MAME exited normally. No hang.

### 9.1 A limit of that regression, stated because it limits the claim

The 104 s programme *drives* all seven event groups, but the emulated machine
**stops producing sound at t ≈ 30 s** and everything after the chromatic run is
driven-but-silent. Measured per-second envelope of channel 1:

```
   t=0 ..51 s  ..........#oooo.##########ooooo.....................
   t=52..103 s ....................................................
```

So what the byte-identity actually covers **audibly** is boot, the 4 s sustained
note, its release and the full chromatic 12/12 — 20 s of real audio, peak
10 233. The rest is byte-identical silence.

This is **NOT caused by anything in this change**: the published build produces
byte-identical output, silence included, and reordering the programme so the
chord and the octave come last (in case a two-port press was the trigger) made
**no difference at all** — the envelope is identical in both orderings. It is
the pre-existing KN5000 defect `kn7000-emulator/run.sh` already documents ("the
control panel can go dead for the rest of the session"), reproduced here on the
keybed and now with a deterministic trigger worth chasing separately: it wedges
partway through a run of ~12 single key presses.

**What this means for the safety claim**: the bit-identity is real and large
(14 976 003 samples), and the audible part of it covers sustain, release and a
chromatic octave. It does **not** independently exercise polyphony or the rapid
re-trigger path, because this machine will not sound them at that point in the
session — under either binary.

---

## 10. What remains undecoded, in priority order

| what | words | why it is next |
|---|---|---|
| `SRC = 0x00` | 531 | the largest single open code; it also settles the `nop` tension of §4.1 |
| `ACTION = 0x0E` | 172 | second largest; `1CE`/`40E` are the kernel's own store/read idiom |
| `ACTION = 0x0D` | 153 | `1CD` (152 sites) is a class-2 read the mix block leans on |
| `ACTION = 0x00` | 126 | `1C0` is the LFO phase read **and** the right input latch read |
| class-1 word format | 337 | the external delay-RAM bracket; unlocks the whole reverb and delay family |
| `hi12[3:1]` codes 3,4,5,7 | 31 | if `[3:1]` is a **bit-set** rather than an enum (crossval §6.2 escape 1), 3 = 1∪2 and 5 = 1∪4 fall out for free — cheap to test |
| `hi12[3:1] = 2` off class 8 | 73 | resolves with §2.2: pick between the 2²³ `AND` and the conditional subtract |
| `SRC = 0x08` | 82 | the `lo12 = 0x200` coefficient-into-the-adder route; needed for the LFO |

**The single highest-value next step** is the class-1 external-DRAM word format.
It is 337 words, R1 has already FORCED which words are the read and the write and
measured the 2–5 word read latency, and it is the only thing standing between
this core and the reverb tail test — which, per `dsp-alu-crossval.md` §7, would
also settle R1's own open family-A-vs-B question for free.

---

## 11. Sync list for `kn5000-roms-disasm/dsp/` (that tree was NOT edited)

1. `instruction-set.md`: `lo12` is the **operand routing**, not the ALU; add
   `hi12[3:1]` as the accumulator operation with codes 0/1/2 and the evidence in
   §2. Retire the "one uniform operation, `P` consumed" wording.
2. `instruction-set.md`: the class guard — classes 1/3/5/6 are **not** datapath
   classes and their `lo12` must not be read as routing (§3.2).
3. `analysis/r1-allpass-motif.md`: F2's operand-before-store ordering is now
   **independently reproduced by the biquad** (999 dB ablation, §5.2 row 13).
4. `analysis/`: a new note for the LFO pair — the 0.5993 Hz check and the two
   surviving wrap operations (§2.1, §2.2).
5. `tools/dsp_disasm.py`: the source/action rendering, and the `SRC[4]`
   out-of-bounds pattern if that tool shares it (§3.3).
6. `disasm/`: `GEQ` (algo 79) is a fourth EQ-family program with no `.dsm` and
   is directly relevant to this constraint system — flagged by
   `dsp-alu-crossval.md` §1 and still worth recovering.

---

## 12. Reproduce

```bash
cd ~/compartilhado/kn7000_mame

# the corpus, the predicate and the per-frame coverage
python3 tools/kn5000_dsp_alu.py \
        ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom

# the acceptance test on the arithmetic THAT SHIPS
python3 tools/kn5000_dsp_alu_mirror.py /tmp/mirror.cpp
g++ -O2 -std=c++17 -o /tmp/mirror /tmp/mirror.cpp
# ... then score it against ideal_H() -- see accept.py / ablate.py in the
#     session scratchpad, which drive /tmp/mirror over all eight ROM banks
```

Files changed: `src/devices/cpu/upd6383/upd6383.cpp` (`exec_alu`),
`upd6383d.h` (`hi_f31` semantics, `lo_act`, `alu_decoded`), `upd6383d.cpp`
(`decoded`, `text`, the documentation block), and the new generator
`tools/kn5000_dsp_alu_mirror.py`.
