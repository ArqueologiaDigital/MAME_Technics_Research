# K6 — the AUDIO INPUT STAGE, I-RAM 0..11, decoded statically

**NEC uPD6383GF-3BA (Technics SX-KN5000 IC311).** Roadmap item **K6**. Date 2026-07-26.

The live audio path traps on 100.00 % of frames and the trap list starts at I-RAM word 0 —
**nothing enters the chip**, so everything downstream is untestable. This note decodes the
twelve words of the input stage far enough to say *where the incoming sample lands*, *how many
samples enter*, and *what a core must do so that one arrives*.

No hardware was used and none is needed for anything claimed here. Every statement is tagged
**MEASURED** (counted over the ROM corpus / the cold-boot capture), **PROVEN BY CONSTRUCTION**
(read out of the ROM bytes that produce it), **FORCED** (the only assignment a stated rule
admits), **INFERRED**, **EDUCATED GUESS**, or **OPEN**. Where a constraint system admits several
assignments they are enumerated, not chosen.

**Scope note.** Per the concurrency rule for this pass, `kn5000-roms-disasm/dsp/tools/dsp_disasm.py`,
`dsp/instruction-set.md` and `dsp/analysis/*` were **read but not edited**. §10 lists what should
be synced into that tree later.

---

## 0. Executive summary

| # | finding | status |
|---|---|---|
| 1 | The twelve words match the canned Sub-CPU blob at `0x01E496` **byte for byte, 12/12**, and the record decodes exactly as K5's bytecode rule predicts (`op 3, len 303, cmd 0x01, I-RAM 0x0000, 60 words`). | **PROVEN BY CONSTRUCTION** |
| 2 | **The block split is 0..6 / 7..11, not 0..5 / 6..11.** Three independent lines agree. The brief's proposed 6+6 split is **FALSIFIED**. | **MEASURED** |
| 3 | The data-pointer walk of the twelve words is fully determined by the established class-2/A rule; it touches exactly **seven cells, X+0 .. X+6**, where `X` is the pointer at I-RAM 0. | **FORCED** |
| 4 | ⚠ **DOWNGRADED — see the banner below §0.** Over the *whole frame* (kernel + epilogue + all 38 body images) exactly **two** cells are READ and NEVER WRITTEN: **X+2 and X+5**. No word can have written them before they are read, and no `880` DRAM bracket is open across them. They are the only externally-supplied operands in the machine ⇒ **X+2 and X+5 are the two audio input latches. Exactly two samples enter the chip per frame — one per block.** | ~~MEASURED + FORCED~~ → **INFERRED (STRONG)**; the "never written" half rests on finding 5 |
| 5 | ⚠ **FALSIFIED — see the banner below §0.** ~~Those two + the whole I/O window X+0..X+6 are touched by **0 of the 38 body images** (0 of 2974 body words). The input cells are private to the kernel.~~ Under the completed shared-pointer walk it is **79 of 79**. | ~~MEASURED (38/38)~~ → **FALSIFIED** (`analysis/closure-pointer.md` item F) |
| 6 | **Two CHANNELS (L and R), not two ports.** One PC sweep per LRCK period ⇒ one pass must produce a stereo result; the reverb's MEASURED mirrored L/R output tails prove the result *is* stereo; only two samples enter ⇒ they are L and R. The board reads **one** of its three wired DI ports. §4.2 of `kn5000-dsp-headerdecode.md` reached the same conclusion **from a premise that is now false** ("this board uses one stereo pair") — the conclusion survives, its reason does not. | **INFERRED (strong)** |
| 7 | **DESTINATION, over-determined 37×:** the input stage does *not* hand cells to the bodies. It hands the **accumulator** to the header's mix block, which deposits the per-unit send with `w45` (unit 0) / `w53` (unit 1) at exactly **the cell the body reads first**. `w45`'s cell *is* the unit-0 entry pointer (FORCED: `addr8 = 0`, and w46..w49 do not move the pointer), and **38 of 38 body images make offset +0 their first D-RAM access; 34 of 38 READ it**. | **FORCED + MEASURED** |
| 8 | The unit-1 (reverb) send has a **2-cell discrepancy**: `w55`/`w57` advance the pointer by +1 each between `w53`'s store and the call. Three resolutions are enumerated; none is chosen. | **OPEN** |
| 9 | A closed, origin-free loop: **`iw0` writes X+0 and the epilogue's `w80`/`w81` read X+0 in the same frame; the epilogue's `w79` writes X+1 and `iw2` reads it in the NEXT frame.** This is forced by the pointer rule alone, with no assumption about any pointer-load word. It is the dry path plus a one-sample feedback. | **FORCED** |
| 10 | **X+3 is written (`iw3`) and never read anywhere in the frame.** Either a hardware register (a DO/side-chain latch) or a dead store. | **OPEN** |
| 11 | By-product, and it matters for K3: **the host window's `801.0.NN.821` and the in-I-RAM `801.0.NN.821` cannot target the same space.** If the I-RAM form aimed at C-RAM the chorus's MEASURED bank base 0x00 would be impossible; if the host form aimed at D-RAM the reverb's coefficient block at 0x90..0xB4 would land on top of this input window. | **MEASURED (both directions)** |
| 12 | By-product: the cold-boot capture's 20-value stream at C-RAM 0x00 is the **CHORUS body's** bank, not the header's — confirmed by `C-RAM[0x01] = 0x7FFFFF` matching the chorus's 2nd class-A word, the LFO wrap constant (29/29 elsewhere), and `C-RAM[0x00] = 0x000072` being an LFO rate (0.6 Hz). The header's own 23-slot bank is **not written anywhere in the cold-boot capture**, so **the four input-stage coefficients are UNKNOWN values**. | **MEASURED** |

> ⚠⚠ **RETRACTION BANNER — added 2026-07-26 by the retraction sweep
> (`kn5000-roms-disasm/dsp/analysis/retraction-sweep.md`, premise P9). FINDING 5 IS
> FALSIFIED AND FINDING 4 IS DOWNGRADED.** Nothing is deleted; this note called its own
> soft step, and the sweep is only propagating what the note itself warned about.
>
> **What this note flagged, in §4.1 step 1:** *"(This one step is not origin-free — it
> uses the standing reading that `801.0.NN.821` loads the data pointer, which fixes the
> offset between `X` and the bodies' origins.)"*
>
> **K3 WITHDREW EXACTLY THAT READING.** `0x821` addresses the COEFFICIENT space
> (`dsp/analysis/k3-pointers.md` §4, **FORCED**). With no per-body origin the bodies
> inherit the kernel's pointer across the CALL boundary, and `closure_pointer.py window`
> re-ran step 1 under the completed walk:
>
> ```
>    unit-0 body entry = X+6;  kernel I/O window = X+0..X+6;  latches X+2, X+5
>       images whose walk enters X+0..X+6 : 79 of 79      (was: 0 of 38)
>       images that touch an INPUT LATCH  : 10 of 79
>    the cold-boot frame's unit-1 reverb touches BOTH latches
> ```
>
> * **Finding 5 is FALSE as stated.** "The input cells are private to the kernel" was a
>   property of a withdrawn origin model, not of the corpus.
> * **Finding 4 keeps its identification but loses its FORCED label.** "Read and never
>   written over the whole frame" no longer holds, so the two cells are the audio input
>   latches by **INFERENCE (strong)**, not by forcing. The *offsets* +2 / +5 survive
>   untouched — finding 3 is an origin-free walk of the twelve words.
> * **KNOCK-ON, and it is the important one: §5's frame-closure loop, and every
>   downstream use of "the closure criterion is FORCED", inherit this.** See the banner
>   on §5, `dsp-frame-advance.md` §3.1, and `analysis/closure-pointer.md` item F.
> * **Finding 6 is unaffected** — it was already re-derived from independent evidence
>   after its own premise ("this board uses one stereo pair") was falsified. That is the
>   propagation this note did right, and the model for the rest.
> * **The shipped MAME device is SAFE and was checked**: the DI deposit happens at frame
>   start and the kernel reads the cells in words 4/8 before any body runs, so a body
>   entering the window cannot corrupt a read that already happened; and the input-stage
>   audit is a **comparison**, not an assertion, so a wrong cell map reports MISMATCHED
>   rather than lying. Only the *labels* in `upd6383.h` were corrected.

---

## 1. The blob, checked byte for byte (**PROVEN BY CONSTRUCTION**)

`kn5000_subprogram_v142.rom`, CPU `0x01E496` = file `0x00F596` (offset −`0x00EF00`).
Applying K5's bytecode rule (`op = b0>>4`, `len = (((b0&0x0F)<<8)|b1) − 2`):

```
31 31 | 01 00 00 | 00 92 20 12 0D  0C 0A 0E 00 00  00 84 20 26 80 ...
 ^b0 b1   ^cmd ^I-RAM word address 0x0000        ^ 60 x 5-byte words

op = 3, len = 0x131-2 = 303 = 3 + 60*5
```

**PREDICT-THEN-CHECK — PASSED, 12/12, zero mismatches.** Every word of the live trap list is the
ROM byte string:

```
iw 0  00 92 20 12 0D   092.2.01.20D      iw 6  04 00 A0 04 19   400.A.00.419
iw 1  0C 0A 0E 00 00   C0A.0.E0.000      iw 7  00 90 A0 11 C8   090.A.01.1C8
iw 2  00 84 20 26 80   084.2.02.680      iw 8  00 84 20 11 C0   084.2.01.1C0
iw 3  00 12 2F F1 CE   012.2.FF.1CE      iw 9  00 12 2F F1 D5   012.2.FF.1D5
iw 4  02 04 20 21 CE   204.2.02.1CE      iw10  02 82 A0 14 17   282.A.01.417
iw 5  02 02 A0 04 48   202.A.00.448      iw11  04 00 20 14 47   400.2.01.447
```

So the input stage is a **literal canned image**; nothing in it is computed by the firmware, and
no reading of it can be an artefact of a mis-parsed upload.

Corpus rarity (**MEASURED**, 2974 body words in 38 images): **11 of the 12 `(hi12, class4, lo12)`
families and 12 of the 12 exact words occur ZERO times in any body.** The one family that is not
kernel-exclusive is `iw9 = 012.2.FF.1D5` (2 body occurrences). `iw3` is byte-identical to
epilogue `w79` — the input stage and the output stage share one word, and §5 shows they are two
halves of the same loop.

---

## 2. The STRUCTURE: two blocks, 0..6 and 7..11 — and the brief's split is falsified

The brief proposed "two parallel six-word blocks, iw 0..5 and iw 6..11". **That is wrong.**
Three independent lines put the boundary between 6 and 7:

**(a) The END-OF-BLOCK bit — MEASURED.** `is_eob(w) = (hi12 & 0xC00) == 0x400` is the series
definition (`kn5000-dsp-headerdecode.md` §1): bit 10 set, format-escape bit 11 clear. It fires in
the 60-word header at indices **6, 11, 14, 19, 21, 23, 24, 28, 33, 36, 39, 41, 49, 59** — 14
blocks — and in the bodies exactly once per image, always the **last** word (38/38). Blocks end
*on* the marked word. So the first two blocks are **0..6** and **7..11**, and — as the same rule's
own best witnesses — block 42..49 ends on the unit-0 CALL and 50..59 on the unit-1 CALL.
`iw6` and `iw11` are the two block terminators; under the brief's split `iw6` would be a block
*opener*, which the same bit contradicts everywhere else in the machine.

**(b) Header word 1 names the second block — MEASURED, INFERRED reading.** `iw1 = C0A.0.E0.000`
is a C-format word; under K5's split (`A = bits[24:17]`, `B = bits[16:12]`) its `imm13 = 0x0E0 =
7 × 32`, i.e. **A = 7, B = 0**, and I-RAM 7 is exactly the first word of the second block. K5
flagged this as a free by-product; it is now the *second* line of evidence, and it is
independent of (a). *Honest limit:* `C0A` is not the `C40` opcode for which the A/B split was
measured, so the reading is INFERRED. Corroboration for the split being an I-RAM address in this
family: `w48 = C64.5.A2.000` → **A = 45** and `w56 = C64.6.A2.007` → **A = 53**, and I-RAM 45 / 53
are exactly the per-unit send-store words of the blocks those two words sit in (§6). That is one
relation seen twice (`A = own address − 3`), not two independent facts, and it is reported as
such.

**(c) The pointer walk — FORCED.** The walk (§3) makes 7..11 a self-contained five-word run that
starts where 0..6 stops, with its own store/read/store/read/read shape. The brief's split would
cut `iw5`/`iw6` (which both address the *same* cell, X+4) apart from each other.

**The word-level alignment between the blocks**, after dropping the two words block A has and
block B does not (`iw1`, the C-format word, and `iw4`):

```
   iw0  092.2.01.20D  <->  iw7  090.A.01.1C8     hi12 differ in bit 1; same addr8 +1; both STORE
   iw2  084.2.02.680  <->  iw8  084.2.01.1C0     hi12 IDENTICAL
   iw3  012.2.FF.1CE  <->  iw9  012.2.FF.1D5     hi12 IDENTICAL, addr8 IDENTICAL (-1), both STORE
   iw5  202.A.00.448  <->  iw10 282.A.01.417     both class A (coefficient), lo12 both kernel-unique
   iw6  400.A.00.419  <->  iw11 400.2.01.447     hi12 IDENTICAL (END OF BLOCK)
```

3 of 5 pairs share `hi12` exactly and 4 of 5 share `class4 mod 8`. Under the brief's split only
2 of 6 pairs match at all. The blocks are **parallel but not identical**: block A carries two
extra words and a wider pointer excursion.

---

## 3. The pointer walk and the cell map (**FORCED**)

Rule used, unchanged from `kn5000-dsp-addressing.md` §1 (MEASURED there):
`class4 & 7 == 2` (classes **2** and **A**) ⇒ operate on `mem[ptr]`, then
`ptr ← (ptr + signed8(addr8)) & 0xFF`; every other class leaves the pointer alone.
`hi12` bit 4 ⇒ the word STORES the accumulator to `mem[ptr]`. `class4` bit 3 ⇒ the word fetches
the next coefficient (implicit cursor, +1).

No word in I-RAM 0..11 loads a pointer, so the whole walk is fixed by one unknown, `X` = the data
pointer at I-RAM 0:

```
 iw    word           cls a8    cell     act    cursor
  0  092.2.01.20D      2  +1    X+0    STORE      -
  1  C0A.0.E0.000      -   -     -    (C-format: imm13 = 0x0E0, A=7, B=0; no pointer effect)
  2  084.2.02.680      2  +2    X+1    read       -
  3  012.2.FF.1CE      2  -1    X+3    STORE      -
  4  204.2.02.1CE      2  +2    X+2    read       -
  5  202.A.00.448      A  +0    X+4    read     C-RAM[cur+0]
  6  400.A.00.419      A  +0    X+4    read     C-RAM[cur+1]   END OF BLOCK
 -------------------------------------------------------------- block A | block B
  7  090.A.01.1C8      A  +1    X+4    STORE    C-RAM[cur+2]
  8  084.2.01.1C0      2  +1    X+5    read       -
  9  012.2.FF.1D5      2  -1    X+6    STORE      -
 10  282.A.01.417      A  +1    X+5    read     C-RAM[cur+3]
 11  400.2.01.447      2  +1    X+6    read       -             END OF BLOCK
                                              pointer leaves at X+7
```

Complete access history of the window over one whole frame (kernel 0..59 + epilogue 60..82 +
CHORUS at 84 + REVERB at 200), in execution order:

```
 X+0 :  W iw0            ->  r epi w80  ->  r epi w81
 X+1 :  r iw2            ->  W epi w79                       (written LAST, read FIRST: one-frame loop)
 X+2 :  r iw4                                                <-- READ, NEVER WRITTEN
 X+3 :  W iw3                                                <-- WRITTEN, NEVER READ
 X+4 :  r iw5 -> r iw6   ->  W iw7                           (read-before-write: one-frame state cell)
 X+5 :  r iw8 -> r iw10                                      <-- READ, NEVER WRITTEN
 X+6 :  W iw9 -> r iw11  ->  W w35 -> r w36 -> W w37 -> r w41
 X+7 :  r w13 ... W w39                                      (mix accumulator, 15 accesses)
 X+8 :  r w28 -> W w30 -> r w32                              (mix accumulator)
 X-1, X-2, X-3, X-4, X+9 : never touched
```

---

## 4. What ENTERS the chip: X+2 and X+5, and nothing else

### 4.1 The argument (**MEASURED + FORCED**)

A cell that a program **reads and never writes** is supplied from outside the instruction stream.
Over the entire frame — the 60-word header, the 23-word epilogue **and all 38 body images (2974
words)** — the only such cells inside the kernel's I/O window are **X+2 and X+5**.

Three ways the claim could be wrong, all checked:

1. *A body writes them.* **No.** Simulated for all 38 images: **0 of 38** touch any of X+0..X+6,
   read or write. (This one step is not origin-free — it uses the standing reading that
   `801.0.NN.821` loads the data pointer, which fixes the offset between `X` and the bodies'
   origins. See §9.1.)
2. *An external-DRAM bracket deposits into them.* **No.** I-RAM 0..11 contains **no `880`/`800`/
   `900` word at all**; the first DRAM word of the frame is `w12 = 880.1.20.2D5`, which executes
   *after* both reads and, being class 1, cannot move the pointer off X+7. Nothing can have
   deposited into X+2 or X+5 before `iw4`/`iw8` read them.
3. *The host writes them.* Absurd at audio rate, and the cold-boot capture writes only C-RAM
   (§9.1) and the `000.1.NN.000` state space.

⇒ **X+2 and X+5 are the audio input latches. Exactly two samples enter the chip per frame,
one per block.** `iw4` reads block A's; `iw8` and `iw10` both read block B's.

### 4.2 PORTS or CHANNELS — the answer is CHANNELS, and here is the chain

* **One PC sweep per LRCK period.** Established in `dsp-audiopath-wiring.md` §3.1 (IC303
  generates LRCK; the internal PC-RST is cadenced by LRCKI) and corroborated numerically here:
  the largest program pair in the corpus is 326 slots, which needs 14.4 MHz at 1×Fs against the
  25 MHz part, but **28.8 MHz at 2×Fs — over the clock**. A half-period sweep is therefore
  ruled out for the big programs. **MEASURED/INFERRED.**
* **One pass must therefore produce a stereo result**, because the effect return *is* stereo:
  the reverb's coefficient bank has MEASURED **mirrored LEFT/RIGHT output tails** at
  `C-RAM[0xA9..0xB0]` (`algorithms/reverb.md`, 33/33 coefficients named).
* **Only two samples enter.** §4.1.

⇒ the two are **L and R**, and the two blocks are the **left and right channel chains**. The
board wires three DI lines; **this microcode reads one of them**. Which one is **not decidable
from the microcode** — the latch→cell map is a chip property. Enumerated:

| reading | consequence | evidence |
|---|---|---|
| **(A) DI-latches are channel-major, stride 3** — `[DI1L DI2L DI3L DI1R DI2R DI3R]` | X+2 and X+5 are L and R **of the same port**, for any port index, because they differ by exactly **3** | the Δ = 3 is exact and unexplained otherwise; **EDUCATED GUESS** |
| (B) port-major, stride 2 — `[DI1L DI1R DI2L DI2R DI3L DI3R]` | X+2 and X+5 would be L of port *k* and R of port *k+1* — a mismatched stereo pair | possible but implausible for a stereo chain |
| (C) the latches are not in this window at all and X+2/X+5 are fed some other way | the port question stays open | not excluded |

**What would settle it:** one address-bus trace from an enabled core against real hardware, or
the µPD6383 datasheet's D-RAM memory map. Statically, nothing in the corpus names a port.

### 4.3 The two blocks are parallel but NOT symmetric

Block A reads two operands — X+1 (the one-frame feedback cell, §5) and X+2 (its input latch) —
and produces two stores, X+0 (consumed by the epilogue, §5) and X+3 (consumed by nobody, §0/10).
Block B reads its latch **twice** (X+5 at `iw8` and again at `iw10`, the second time with a
coefficient) and produces X+4 (a one-frame state cell) and X+6, which is the **only** input-stage
product the header's mix block touches. So the two channels are *not* processed by identical
code, and any model that assumes they are will be wrong. **MEASURED.**

---

## 5. The frame-closure loop — origin-free (**FORCED**)

> ⚠ **PARTIALLY INHERITED FROM FINDING 5 — banner added 2026-07-26.** The *loop* in this
> section (`iw0` writes X+0, the epilogue's `w80`/`w81` read X+0 in the same frame;
> `w79` writes X+1 and `iw2` reads it in the NEXT frame) is a pointer-rule walk and is
> **genuinely origin-free — it SURVIVES**, and `closure-pointer.md` item D confirmed its
> relation `X = Y − 1` independently from the closure side (**PREDICT-THEN-CHECK: HIT**).
> What does **not** survive is the use made of this section to label the **frame-closure
> CRITERION** as FORCED: that route runs through finding 4/5, which are retracted above.
> The criterion is now **CONSISTENT**, not FORCED. See `analysis/retraction-sweep.md` P10.

The epilogue's last three class-2 words are `w79 = 012.2.FF.1CE` (STORE, −1),
`w80 = 104.2.00.1CE` (read, +0), `w81 = 102.2.00.000` (read, +0). Let `Y` be the pointer at w79.
Then w79 stores at `Y` and leaves `Y−1`; w80 and w81 both read `Y−1`; the frame ends with the
pointer at `Y−1`; the next frame starts at `X = Y−1`. Therefore, **with no assumption whatever
about which register any pointer-load word loads**:

```
   epilogue w79  STOREs X+1   ->  next frame's iw2 READs X+1      (one-sample feedback)
   iw0           STOREs X+0   ->  same frame's epilogue w80/w81 READ X+0   (within-frame path)
```

This is the positive explanation for three accesses that were otherwise orphans, and it is the
reason the frame-start pointer is **not** reset by hardware: if PC-RST also reset the data
pointer, `w79`'s store and `w80`/`w81`'s reads would have no counterpart anywhere in the machine.
**INFERRED (strong)** for the no-reset premise; **FORCED** for the loop given it.

Absolute value, for reference only: under the standing reading that `801.0.NN.821` loads the data
pointer, the epilogue's `w69 = 801.0.90.821` gives `Y = 0x90` and **`X = 0x8F`**, so the window is
D-RAM `0x8F..0x97`, sitting immediately above the epilogue's class-1 cell cluster `0x85..0x8F`
and immediately above the 60-cell host table the firmware loads at `0x50..0x8B` and then stops
(cold-boot transfers 5..10 set the pointer to 0x8C and write nothing). Tidy — but it inherits
`kn5000-dsp-addressing.md` §5's unresolved origin (the biquad wants 0x19, not 0x70), so **the
absolute address is INFERRED, the relative structure is FORCED.**

---

## 6. THE DESTINATION — forced, and over-determined 37 times

The brief's decisive constraint was "the input stage writes X, the unit-0 body first reads X".
**The chain is one hop longer than that**, and the extra hop is what makes it provable.

**The input stage does not hand a cell to the bodies.** Its cells (X+0..X+6) are touched by
0 of 38 body images (§4.1). It hands the **accumulator** to the header's mix block (I-RAM 12..41,
which works in X+6/X+7/X+8), and the mix block's result is deposited per unit:

```
   w42  801.0.70.821   load pointer                       w50  801.0.50.821
   w43  801.0.6C.827                                      w51  801.0.64.827
   w44  801.0.25.825                                      w52  801.0.25.825
   w45  010.A.00.20C   STORE acc -> mem[ptr], addr8 = 0   w53  010.9.D0.20C   STORE, class 9
   w46  800.1.60.00B                                      w54  800.1.60.00B
   w47  800.8.0C.000   class 8, no pointer move           w55  000.2.01.007   +1
   w48  C64.5.A2.000   C-format, A = 45                   w56  C64.6.A2.007   C-format, A = 53
   w49  400.1.0E.000   CALL unit 0                        w57  000.2.01.000   +1
                                                          w58  000.1.8A.007
                                                          w59  400.1.0F.007   CALL unit 1
```

**Unit 0 — FORCED.** `w45` has `addr8 = 0x00`, so it stores at the pointer and does not move it;
`w46` (class 1), `w47` (class 8), `w48` (C-format) and `w49` (class 1) cannot move it either.
**The cell `w45` writes IS the unit-0 body's entry pointer.** No origin is needed for this.

**The bodies agree, 38/38 — MEASURED.** Simulating each image from its entry pointer:

```
   first D-RAM access is at offset +0 from the entry pointer :  38 of 38 images
   and it is a READ                                          :  34 of 38
   the 4 exceptions (phaser, ensemble, s.delay+chorus, peq+vibrato) all open with the
   LFO idiom `092.A.dd.200`, whose first word carries the bit-4 STORE; they write +0 first
   and read it two or four words later
```

So **the send cell = the body's input cell**, agreed by **37 independent unit-0 images** plus the
one unit-1 image, over 38 separately-authored microprograms. That is the over-determination the
method asked for. Nothing else in the frame is a candidate: no body contains a pointer load
(0 of 2974 words), so a body cannot go looking anywhere else.

**Unit 1 — a 2-cell discrepancy, OPEN.** `w53` stores at the pointer, but `w55` and `w57` each
advance it by +1 before the call, so the reverb's entry pointer is **`w53`'s cell + 2**, and the
reverb's first access (`w1 = 000.2.89.415`, a read at +0) is 2 cells above the store.
Resolutions, none chosen:

1. **`w55`/`w57` do not move the pointer.** They are `000.2.01.007` and `000.2.01.000`; the
   second occurs 10× in bodies as an ordinary pointer mover, which argues against.
2. **`w53` is not the unit-1 send store.** It is **class 9**, not class A — a different
   addressing mode — and `addr8 = 0xD0` rather than `0x00`. Under mode 1 it may not write
   `mem[ptr]` at all.
3. **The unit-1 send arrives by a third route** (e.g. the reverb reads it out of the accumulator
   at `w1`/`w2`, which its bit-4 store at `w2` is consistent with).

The unit-0 result does not depend on which of these is right.

---

## 7. Per-word verdict, I-RAM 0..11

| iw | word | pointer / store | verdict | what is claimed |
|---|---|---|---|---|
| **0** | `092.2.01.20D` | STORE `mem[X+0]`; ptr +1 | **FORCED** (effect) / **OPEN** (ALU) | deposits into the cell the **epilogue's w80/w81 read** (§5). `lo12 = 0x20D` occurs **0×** in 2974 body words — kernel-exclusive, and adjacent to `0x20C`, the `lo12` of both per-unit send stores w45/w53 |
| **1** | `C0A.0.E0.000` | none | **INFERRED** | C-format immediate, `A = 7, B = 0`; **7 = the first word of block B**. No memory, no pointer, no cursor effect ⇒ **treat as a no-op for input purposes** |
| **2** | `084.2.02.680` | read `mem[X+1]`; ptr +2 | **FORCED** (effect) / **OPEN** (ALU) | reads the **one-frame feedback cell** the epilogue wrote at w79 |
| **3** | `012.2.FF.1CE` | STORE `mem[X+3]`; ptr −1 | **FORCED** (effect) / **OPEN** (sink) | byte-identical to epilogue `w79`. Its cell is **written and never read** anywhere in the frame — a hardware register or a dead store |
| **4** | `204.2.02.1CE` | read `mem[X+2]`; ptr +2 | **FORCED** | **THE PORT READ of block A.** X+2 is read and never written by any of 3057 words |
| **5** | `202.A.00.448` | read `mem[X+4]`; ptr +0; **C-RAM[cur+0]** | **FORCED** (effect) | first of block A's two coefficient multiplies; `lo12 = 0x448` occurs **0×** in the bodies |
| **6** | `400.A.00.419` | read `mem[X+4]`; ptr +0; **C-RAM[cur+1]**; END OF BLOCK | **FORCED** (effect) | block A terminator; still does its datapath work (MEASURED for bit 10) |
| **7** | `090.A.01.1C8` | STORE `mem[X+4]`; ptr +1; **C-RAM[cur+2]** | **FORCED** (effect) | writes back the cell iw5/iw6 read ⇒ X+4 is a **one-frame state cell** (a filter/DC state, not an input) |
| **8** | `084.2.01.1C0` | read `mem[X+5]`; ptr +1 | **FORCED** | **THE PORT READ of block B** |
| **9** | `012.2.FF.1D5` | STORE `mem[X+6]`; ptr −1 | **FORCED** (effect) | `lo12 = 0x1D5` is the DETERMINED `mac` route; the only input-stage product the mix block consumes |
| **10** | `282.A.01.417` | read `mem[X+5]`; ptr +1; **C-RAM[cur+3]** | **FORCED** | reads block B's port latch a **second** time, this time with a coefficient; `lo12 = 0x417` occurs **0×** in the bodies |
| **11** | `400.2.01.447` | read `mem[X+6]`; ptr +1; END OF BLOCK | **FORCED** (effect) | block B terminator; hands X+6 to the accumulator, pointer leaves at X+7 where the mix block picks up |

`cur` = the cursor value at I-RAM 0. **The four coefficients are UNKNOWN values** — §9.2.

**Which word is "the port read"?** `iw4` and `iw8`/`iw10`, by the cell they address, **not** by
their opcode. There is no special "read DI" instruction here: the input stage uses ordinary body
vocabulary (`0x1CE`, `0x1C0`, `0x1D5`) and the port-ness is entirely in the **address**. That is
the single most useful thing this note establishes for an emulator, and it explains why every
opcode-level search for an I/O instruction in this block came up empty.

---

## 8. MINIMUM EXECUTABLE SEMANTICS — what a core must do for a sample to enter

Two things, and they are separable:

**(1) Present the samples.** Before I-RAM word 0 of each frame, write the two incoming samples
into D-RAM at **`X+2`** and **`X+5`**, where `X` is the data pointer at PC-restart (i.e. the value
the previous frame left; at cold start any value works, because §5's loop re-establishes it).
Which sample is which is the enumeration of §4.2; the honest default is
`mem[X+2] = DI_L`, `mem[X+5] = DI_R` of one port, LABELLED as EDUCATED GUESS (A).

**(2) Execute the twelve words' MEASURED skeleton** instead of trapping them. For every class-2/A
word:

```
   cell   = ptr
   if hi12 & 0x10 :  mem[cell] <- ACC                     // bit 4, MEASURED
   if class4 & 8  :  coef = C-RAM[cursor++]               // cursor fetch, MEASURED
   ptr = (ptr + signed8(addr8)) & 0xFF                    // MEASURED
```

and for `iw1` (C-format) do nothing at all. That is enough for the sample to enter, the pointer
to arrive at X+7, and the frame to reach the mix block — i.e. enough for the whole machine to
become observable.

**What it is NOT enough for: correct audio.** The ALU operation each `lo12` selects is still
undecoded, so the value the input stage leaves in the accumulator is wrong even though the
addresses are right. Per this project's standing rule (plausible-but-wrong sound is worse than
silence), the recommendation is:

* implement the skeleton **behind the existing default-OFF `DSPCFG` option**;
* keep the frame-return discard, but change the trap accounting so a word whose *addressing* is
  executed and whose *ALU* is unknown is counted **separately** from a word that is wholly
  unknown — the first is progress, the second is the worklist;
* do **not** un-mute the return path until the `lo12` ALU field is decoded.

Per-word disposition for (2): `iw0, iw2, iw3, iw4, iw5, iw6, iw7, iw8, iw9, iw10, iw11` — execute
the skeleton (addressing FORCED, ALU OPEN). `iw1` — **safe no-op**, because it is C-format: it has
no `addr8` field, no `class4` field, no memory operand and no cursor effect, so there is nothing
for it to do to the input path. Its `A = 7` is an I-RAM address, not data.

---

## 9. By-products and corrections

### 9.1 The two `801.0.NN.821` meanings cannot be one meaning (**MEASURED, both directions**)

Decoding the cold-boot capture's host stream (`01 60` window = 5-byte host packets, `01 61` =
raw 3-byte values at the current pointer) gives the C-RAM map the host builds:

```
   x5..x10   reg <- 0x50, 0x6E, 0x8C : 60 values 0x8000,0x8400.. and 0x0000,0x04BE.. -> DRAM tap table
   x22..x30  reg <- 0x90, 0xAE, 0x97, 0x9E, 0xA6, 0xAC, 0xB2 : the REVERB bank
   x36..x39  reg <- 0x00 : 20 values -> the unit-0 effect bank
```

* If the **in-I-RAM** `801.0.70.821` (w42) aimed at C-RAM, the unit-0 body's cursor base would be
  ≥ 0x70. It is MEASURED **0x00**. ⇒ the I-RAM form does **not** load the C-RAM pointer.
* If the **host-window** form aimed at D-RAM, the reverb's coefficients at 0x90..0xB4 would be
  written straight over this note's input window at 0x8F..0x97. ⇒ the host form does **not** aim
  at D-RAM.

So K5's caveat ("whether the identical word *inside* I-RAM does the same thing is INFERRED") is
now **decided in the negative**, from two independent directions. `instruction-set.md`'s entry for
`801.0.NN.821` should say so. This also means the standing "`ldptr` loads the data pointer"
reading is *not* contradicted by the host stream — they are different registers or different
spaces, and K3 must enumerate at least two.

**A lead for K3, offered as a lead only:** the two per-unit words `w45 = 010.A.00.20C` and
`w53 = 010.9.D0.20C` are identical except for `class4` (A vs 9) and `addr8` (**0x00** vs
**0xD0**), and the two MEASURED cursor bases are **0x00** (unit 0) and **0x90** (unit 1). Unit 0
matches exactly; unit 1 matches under `addr8 & 0xBF`. n = 2, one exact and one requiring an
unexplained mask — **not a finding**, but it is the only pair of words in the machine positioned
to carry a per-unit cursor base.

### 9.2 The header's own coefficient bank is not in the cold-boot capture (**MEASURED**)

The 20-value stream the host writes at C-RAM 0x00 is the **body's** bank, not the header's:
`C-RAM[0x01] = 0x7FFFFF` is the LFO wrap constant and the chorus's 2nd class-A word is
`094.A.00.200`, the MEASURED wrap consumer (29/29 across the corpus); `C-RAM[0x00] = 0x000072` is
an LFO rate (0.6 Hz at 44.1 kHz); `C-RAM[0x09]/[0x0A]` are later re-poked to 0.1515, matching the
chorus's documented wet level. This independently re-confirms `headerdecode.md` §5 ("the header
runs on its own, separate bank") and **means the four coefficients the input stage multiplies by
(cursor+0..+3) are values this project has never seen.** They must be loaded by something outside
the captured cold-boot window. *What would settle it:* a capture that starts earlier, or the
`op 0..5` bytecode handlers at `0x03C32E + OFFSETS_14739[op]` (pure static work, already on K5's
follow-up list).

### 9.3 Corrections to earlier notes

| earlier claim | where | status |
|---|---|---|
| "two parallel six-word blocks, iw 0..5 and iw 6..11" | the K6 brief | **FALSIFIED** (§2). The blocks are 0..6 and 7..11 |
| "`addr8 == 0x03` never occurs in the header, so this is a **two-channel** structure, not a three-way DI1/DI2/DI3 sweep: **the chip has three ports, this board uses one stereo pair**" | `kn5000-dsp-headerdecode.md` §4.2 | **conclusion UPHELD, reason FALSIFIED.** The board wires all three DI and all three DO (`dsp-audiopath-wiring.md` §2, MEASURED from the service manual), and `addr8` is a pointer delta, so it could never have carried a port index. The two-channel conclusion is re-derived here from the read-never-written cell count + the stereo reverb tails + one sweep per LRCK |
| "the two lo12-different opening blocks is two different input PORTS (DI1 = unit-0 send, DI2 = unit-1 send)" | `dsp-audiopath-wiring.md` §2.4 (offered as a hypothesis with a cheap test) | **NOT SUPPORTED.** The test it proposed — "if I-RAM 0..11 reads two ports, a third input read must exist somewhere" — is now answerable: there is no third input read, and there are only **two** externally-supplied cells in the entire machine |
| "`hi12 == 0xC40` = envelope detector" | `-effect-map.md`, still emitted by the disassembler | **already withdrawn by K5**; nothing here revives it. `iw1` is `C0A`, a different opcode |

---

## 10. Still OPEN

1. **Which port.** §4.2. Needs the D-RAM/latch map — hardware trace or datasheet.
2. **The ALU field.** Every one of the twelve words has a FORCED addressing effect and an OPEN
   arithmetic effect. `lo12` values in play: `0x20D, 0x680, 0x1CE, 0x1C0, 0x1C8, 0x1D5, 0x448,
   0x419, 0x417, 0x447`. Three of them (`0x20D, 0x448, 0x417`) occur **0×** in 2974 body words —
   they are kernel-only routes and the best next targets.
3. **X+3, written and never read.** Hardware register or dead store.
4. **The unit-1 send's 2-cell gap.** §6, three enumerated resolutions.
5. **The four input coefficients.** §9.2 — values unknown, not merely unnamed.
6. **The absolute origin `X`.** Inherits `kn5000-dsp-addressing.md` §5. Everything structural here
   is origin-free; only the absolute 0x8F is not.
7. **`class4 == 1` `addr8`.** In the `880`/`800`/`900` DRAM family it is a sub-op (0x20/0x30/0x60,
   all bit 7 = 0); in the epilogue it is 0x85/0x8A/0x8C/0x8D/0x8F (all bit 7 = 1) and the host's
   own `000.1.NN.000` state-clear packets use the same numbering, hitting 0x06/0x0E/0x85/0x8A.
   "bit 7 of a class-1 `addr8` selects address-vs-sub-op" is a **LEAD**, not a decode.

## 11. To sync into `kn5000-roms-disasm/dsp/` later (nothing was edited there)

1. `instruction-set.md` — the block-terminator reading of bit 10 already agrees; add that
   **I-RAM 0..6 / 7..11 are the two input-channel blocks**, that `X+2`/`X+5` are the input
   latches, and §9.1's negative result about `801.0.NN.821`'s two meanings.
2. `sym/kernel.sym` — labels: `InCh0` (0), `InCh1` (7), `InLatch0` / `InLatch1` on `iw4` / `iw8`,
   `Send0Store` (45), `Send1Store` (53).
3. `tools/dsp_disasm.py` — render class-2/A words with their *pointer delta and store flag*
   (already computable) so a listing shows the walk; do **not** invent an ALU mnemonic.
4. `analysis/` — this note, once the concurrent R1 pass has landed.

## 12. Reproduction

```
# 1. the blob, byte for byte  (rom = kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom)
#    file offset = CPU address - 0x00EF00 ; record: op = b0>>4, len = (((b0&0x0F)<<8)|b1)-2
#    0x01E496 -> op 3, len 303, payload = 01 00 00 + 60*5 bytes

# 2. the pointer walk / cell map / live-in analysis
#    rule: class4 & 7 == 2 -> touch mem[ptr] then ptr += signed8(addr8) mod 256
#          hi12 bit 4      -> the touch is a STORE
#          class4 bit 3    -> cursor += 1
#    frame order: header 0..49 | body @84 | header 50..59 | body @200 | epilogue 60..82
#    body words: kn5000-roms-disasm/dsp/disasm/prog*.dsm ; kernel/epilogue: from the ROM blobs
#    -> "read but never written" over the whole frame = {X+2, X+5}   (+ body-local cells)
#    -> "first D-RAM access of each image is at entry+0": 38/38, read in 34/38

# 3. the host C-RAM map (cold-boot capture, notes/data/kn5000_dsp1_upload_coldboot.txt)
#    cmd 0x01 target 01 60 : 5-byte host packets; 801.0.NN.821 aims the write pointer,
#                            0A aa bb cc dd is a coefficient with tag dd & 0x7F
#    cmd 0x02 target 01 61 : raw 3-byte values at the current pointer
#    -> 0x00..0x13 body bank, 0x50..0x8B DRAM tap table, 0x90..0xB4 reverb bank
```
