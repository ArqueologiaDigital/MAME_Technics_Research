# NEC uPD6383GF — the `lo12` ALU field, solved from the biquad

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-26.
Code: `src/devices/cpu/upd6383/upd6383.cpp` (`exec_alu()`), `upd6383d.{h,cpp}`.
Scratch tools: `alu_model.py`, `alu_model2.py`, `alu_uniform.py`, `cxx_mirror.cpp`,
`corpus.py`, `bits.py`, `bits2.py`, `pairs.py`, `pairing.py` (session scratchpad).

Every claim is tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **FORCED**,
**CONSISTENT**, **INFERRED** or **OPEN**. §8 lists what this pass FALSIFIES.
§7 enumerates every alternative the constraints still admit — it does not pick
silently.

> **Concurrency, and a three-way convergence.** Two sibling passes attacked the
> same field from different directions on the same day:
> `notes/dsp-alu-structure.md` (commit `19ca831`) from the vocabulary
> statistics, and `notes/dsp-alu-crossval.md` (commit `8b3f8e7`) from the
> all-pass motif, the LFO and the input stage. **All three agree on the field
> map** — the bit-11/bit-5 lock marking the same eleven-value pointer family,
> the boundary at bit 5, and the same four operand sources. This note took the
> third route: derive the ARITHMETIC from the one block whose transfer function
> is known independently, then check it numerically.
>
> Where they were sharper, this note yields: §3.2 now uses the **5-bit**
> `lo12[10:6]` source field of `dsp-alu-structure.md` §5, not the 2-bit reading
> the first draft of the header carried, and the core was changed to match.
> Where they conflict — the crossval note's B1, that `lo12` cannot carry the
> operation — the conflict is real, **measurable, and resolved in §7-A8**:
> the alternative it implies is numerically IDENTICAL on the biquad, so this
> note enumerates it instead of claiming against it.
>
> Nothing in `kn5000-roms-disasm/dsp/` is edited here. §10 is the sync list.

---

## Headline

1. **★★★ The accumulator operation is NOT in `lo12`.** What the earlier search
   reported as three different per-word accumulator ops (`NONE` / `ADD-P` /
   `SET-P`) is not a `lo12` field at all: it is the store on `hi12` bit 4 also
   **CLEARING** the accumulator, plus the product register being **CONSUMED**
   by the add. With those two, one uniform ALU reproduces the whole biquad —
   and the one alternative that also reproduces it puts the op in `hi12`, not
   `lo12` (§7-A8). Either way, `lo12` carries **routing**. (§4)
2. **★★★ `lo12[10:6]` is the OPERAND SOURCE SELECT**, and the four codes the
   biquad exercises are exactly the four registers the CDJ-500 block diagram's
   datapath can put on that bus: `0x10` accumulator, `0x19` temp register A,
   `0x1A` temp register B, `0x07` `mem[ptr]`. FORCED on 8/8 words of the
   biquad; CONSISTENT corpus-wide. (§3.2)
3. **★★★ It answers R1's residual by itself.** `102.A.**.64B` — the reverb
   diffuser multiply that the all-pass constraint solve proved *cannot* read
   `mem[p]` and *cannot* read the incoming accumulator — is `0x19`: **temp
   register A**. That is the one route R1 could name only as "something else"
   (`analysis/r1-allpass-motif.md` §9). Two more agreements in §3.3.
4. **★★ A ONE-BIT RIGHT SHIFT exists on the `y[n-1] → y[n-2]` state path, and
   it is FORCED** — remove it and the biquad is **77 dB** wrong. Its origin is
   in the firmware: `−a1/a0` is written at `2^22` and `−a2/a0` at `2^23`
   (MEASURED, `kn5000-dsp-biquad-coeffs.md` §4), so the two recursion cells
   *cannot* hold the same binary point. This is the first confirmed instance of
   the "shift/scale sub-field" the ALU was expected to carry. (§5)
5. **★★ The 144 survivors of the 19,674,720-point semantic search are cut to
   ONE, by the ENCODING and not by more mathematics.** Words `[2]` and `[4]` of
   the section are the *same 36-bit word* except for `addr8`, so they cannot
   carry two different latch stores — which kills every survivor family that put
   the state writes there. (§8, F1)
6. **★ ACCEPTANCE TEST, numerical.** The shipped C++ reproduces the transfer
   function of **8 distinct real ROM coefficient banks** to **max 0.094 dB /
   4.03°**, and the residual falls with signal level, i.e. it is 24-bit state
   quantisation, not a structural error. Ablations: no accumulator clear = **57
   dB**, no one-bit shift = **77 dB**. (§6)
7. **★ Decode coverage 8.8 % → 39.6 % of the corpus** (270 → 1212 of 3057
   words; 36 → 272 distinct words), and **43 → 89 of the 285 words executed per
   frame**. The audio is still BIT-IDENTICAL with the DSP gate on *and* off —
   every frame still traps, so nothing leaks. (§9)
8. **★ `lo12` bit 5 partitions the field.** The eleven values that carry it —
   `021 820 821 822 825 827 839 864 8BC 921 C63` — are *exactly* the pointer-
   register / cursor-reset / table-lookup family, 96 of 3057 words, no
   exceptions in either direction. MEASURED. (§3.1)

---

## 1. Where the constraint comes from

The PARAMETRIC EQ (image rep algo 39, unit 0, I-RAM 84) is the only block in
the corpus whose arithmetic is known **independently of the DSP**: the sub-CPU
designs its coefficients itself, with a textbook `tan()`-based bilinear
designer (`LABEL_03A933`), and that routine is decoded to the constant
(`notes/kn5000-dsp-biquad-coeffs.md`, PROVEN BY CONSTRUCTION). So for this one
program we know the exact transfer function the microcode must compute, the
exact coefficient in every C-RAM cell, and therefore the exact sequence of
arithmetic the nine words must perform.

The section is nine words, repeated **ten times byte for byte** (5 bands × 2
channels), with `rstcur` between the channels. MEASURED:

```
 #  word          class  ptr  coeff   what the biquad needs
 0  000.A.00.1D3    A     0   +0 b1   P = b1*x[n-1] ; keep x[n-1] for later
 1  212.A.01.412    A     0   +1 b0   cell0 <- x[n] ; acc = b1*x[n-1] ; P = b0*x[n]
 2  202.A.01.1D5    A     1   +2 b2   acc += P      ; P = b2*x[n-2]
 3  202.A.01.1D4    A     2   +3 A1   acc += P      ; P = A1*y[n-1] ; keep y[n-1]
 4  202.A.00.1D5    A     3   +4 A2   acc += P      ; P = A2*y[n-2]
 5  102.2.FF.687    2     3    -      acc += P  (the sum is complete) ; cell3 <- y[n-1]
 6  804.8.16.415    8     3    -      the post-sum step
 7  212.A.FF.407    A     2   +5 G    cell2 <- y[n] ; P = G*y[n]
 8  000.2.03.647    2     1    -      acc <- the band output ; cell1 <- x[n-1]
```

Pointer walk `0 0 1 2 3 3 3 2 1`, net `+4` (from the signed `addr8`, MEASURED).
Cells: `0 = x[n-1]`, `1 = x[n-2]`, `2 = y[n-1]`, `3 = y[n-2]`.

The **band input arrives in the accumulator** and the **band output leaves in
the accumulator** — the ten sections are a cascade, and word `[1]`'s `hi12` bit
4 is what commits the input to `cell0`. That is a real extra constraint the
earlier search did not have: it ran each section standalone with `acc = 0`, so
it could not see what the accumulator must contain at a section boundary.

### 1.1 The coefficients are real, and one band is a positive control

Algorithm 39's default C-RAM bank, straight out of the Sub ROM (MEASURED):

```
   C-RAM  +0 b1     +1 b0     +2 b2     +3 A1     +4 A2     +5 G
   band0  E94DC5    D216A0    4BE6A5    16B23A    440573    800000
   band1  936A5A    400000    2CA749    6C95A5    A6B16C    800000
   band2  D445EF    400000    EEA7BE    2BBA10    22B082    800000
   band3  E2DAF3    400000    E29D98    1D250C    3AC4CE    800000
   band4  EFBE48    400000    DA12DF    1041B7    4BDA41    800000
```

Bands 1–4 are **exactly flat**: `b0 = 0x400000 = 1.0` in Q1.22, `b1 = −A1` to
1 LSB, and `b2 = −A2` **once A2 is read at 2^23 and b2 at 2^22** — e.g. band 1
has `b2 = 0x2CA749 = 2926409` and `A2 = 0xA6B16C = −5852820 ≈ −2 × 2926409`.
That factor-of-two relationship is a **direct numerical confirmation of the Q
formats the firmware's scale constants declare**, from a completely different
place in the ROM, and it is what makes §5's shift unavoidable.

`G = 0x800000` is the make-up gain, `−2.0` in Q1.22. It is the one cell of each
six the parameter path never rewrites (`biquad-coeffs.md` §5: the host writes
**five** words at stride 5; algorithm 39's stride-6 blocks carry one padding
cell each). It is not unused — the sixth class-A word reads it — it is simply
**static**, and `−2.0` is exactly what undoes the designer's own `/2.0`
pre-halving of `b0,b1,b2` (`biquad-coeffs.md` §3.2). Section gain is therefore
**−1**: unity magnitude, inverted. INFERRED (strong) and used in §7-A6.

---

## 2. What the earlier search left open, and why

`notes/kn5000-dsp-semantics.md` §3.1 enumerated 19,674,720 assignments and left
**144 survivors** agreeing on `mac`, `mac.lb` and `mulst`. Its residual freedom
was declared as "four observationally-equivalent binary choices". Two of them
are resolved here by the ENCODING (§8 F1) and two by the CASCADE (§1).

More important: its hypothesis space contained a per-word
`ACC_OP ∈ {NONE, ADD, SET}` and **never offered a store-that-clears**. It also
*fixed* `[7]` to `NONE` a priori (its restriction R3), which is a restriction,
not a result. The uniform model below sits **outside** that space; it does not
contradict anything the search determined.

---

## 3. The sub-field structure of `lo12`

3057 corpus words; **82 distinct `lo12` values**; 68 of the words are C-format
(`(hi12 & 0xFFE) == 0xC40` or `hi12[11:8] == 0xC`) where the low bits are
immediate data, not `lo12`, and are excluded, leaving **110 distinct
`(class4, lo12)` pairs**.

### 3.1 bit 5 = the pointer/cursor mode bit — MEASURED

```
   over the 38 body images (2974 words):        021(1) 839(1) 864(1) 8BC(24) 921(1) C63(53)   =  81 words, 6 values
   plus the kernel + epilogue (3057 words):   + 820(5) 821(3) 822(1) 825(3) 827(2)            =  96 words, 11 values
```

That set is *exactly* `rstcur` (`021`), the pointer-load siblings
(`820/821/822/825/827`), the three unexplained `839/864/921`, and the
table-lookup head `C63`. **No datapath word carries it and no pointer-family
word lacks it.** `lo12` bit 11 is a strict subset of it (10 of the 11).

Note where the five `82x` values are: **only** in the kernel and the epilogue,
never in a body. That is an independent re-derivation, from a bit nobody had
read, of the established fact that *no body word anywhere in the 2974-word
corpus contains a pointer load* (`kn5000-dsp-headerdecode.md`) — the bit and the
listing agree without being made to.

### 3.2 `lo12[10:6]` = the OPERAND SOURCE SELECT — FORCED on the biquad

| code | source | biquad words that force it |
|---|---|---|
| `0x10` | accumulator | `407` (`P = G·acc`), `412` (`P = b0·x`, x is in acc), `415` |
| `0x19` | temp register **A** | `647` — writes `mem[ptr]` with the value word `[0]` kept |
| `0x1A` | temp register **B** | `687` — writes `mem[ptr]` with the value word `[3]` kept |
| `0x07` | `mem[ptr]` | `1D3`, `1D4`, `1D5` — the three memory-reading multiplies |

The **width** of the field is not settled by the biquad — the eight words it
uses would be separated by the low two bits alone. It is settled by
`notes/dsp-alu-structure.md` §5, which shows corpus-wide that the 2-bit reading
merges roles that are cleanly separated at 5 bits (`0x0B` delay-RAM vs `0x07`
mem[ptr]: 0-of-106 vs 372-of-929 class A; `0x13` table: 87/87 exactly two
forms; `0x1C` LFO out: 46/46 one `hi12`). **The core uses the 5-bit reading.**
Coarse census over the 2893 non-pointer-mode words of the 38 body images
(`tools/kn5000_dsp_alu.py <subrom> fields`), grouped by the low two bits so it
is comparable with the anchors:

```
   ...00 (acc family)     1426   cls1:117 cls2:907 cls6:7 cls8:38 clsA:357
   ...01 (tempA family)    280   cls0:35 cls1:55 cls2:113 cls3:30 cls5:1 clsA:46
   ...10 (tempB family)     75   cls2:67 clsA:8
   ...11 (mem family)     1112   cls0:2 cls1:133 cls2:463 cls4:53 cls6:46 cls8:4 clsA:411
```

The shape is what two pipeline temporaries should look like: the tempB family
is the rarest thing in the machine (75 words), tempA next (280).

### 3.3 Three independent agreements the field was not fitted to

* **`102.A.**.64B` → `0x19` (tempA).** R1's constraint solve established that
  this multiply's operand is neither `mem[p]` nor the incoming accumulator, and
  could only say "something else" (`r1-allpass-motif.md` §9). The field names it.
* **`880.1.20.655` (delay-DRAM WRITE) → `0x19` (tempA).** The write data comes
  out of a temporary — which is what a software-pipelined delay line does.
* **`880.1.60.2D4` (delay-DRAM READ) → SRC `0x0B` (the delay-RAM member of the
  `mem` family, which only the 5-bit reading separates from `mem[ptr]`) and
  ACTION `0x14` = *capture into temp B*.** So the read data lands in a
  temporary rather than in the accumulator — which is exactly why R1 MEASURED
  that **"the DRAM read data becomes visible 2..5 words later"**. The word's
  own fields predict the latency R1 had to observe.
* And the pair is **asymmetric in the way a software-pipelined delay line has
  to be**: the read fills temp **B** (`2D4`, ACTION `0x14`) while the write
  drains temp **A** (`655`, SRC `0x19`). One temporary per direction.

### 3.4 `lo12[4:0]` = the ACTION — five of twenty-four codes pinned

| code | operation | pinned by |
|---|---|---|
| `0x13` | `tempA ← bus` | `1D3` (word `[0]`) |
| `0x14` | `tempB ← bus` | `1D4` (word `[3]`); CONSISTENT on `2D4`, the delay-RAM read |
| `0x07` | `mem[ptr] ← bus` | `647`, `687` (words `[8]`, `[5]`); consistent on `407` |
| `0x15` | no temp / memory side effect | `1D5`, `415` |
| `0x12` | no temp / memory side effect | `412` |

The 5-bit reading is what makes `0x15` cover both `1D5` and `415` and `0x07`
cover all three of `407`/`647`/`687`: at four bits those pairs would still
agree, but `lo12` bit 4 would be left as an unexplained free bit. Here it is
simply part of the ACTION code — `0x07` is the memory store, `0x12..0x15` are
the temp-register group.

The **pairing** of a capture code with a source code is FORCED, not named: the
value word `[0]` keeps is the value word `[8]` stores, so `0x3` and source `01`
are the same register; likewise `0x4` and source `10`. Calling them A and B is
arbitrary; the pairing is not.

Per-image counts of the four latch words (MEASURED) — the capture/store pairing
balances exactly in 13 of 17 images that contain any of them, including all ten
sections of algorithm 39 (`10/10/10/10`):

```
   image                        1D3  1D4  647  687
   prog39_parametric_eq          10   10   10   10
   prog33_overdrive               2    2    2    2
   prog35_exciter                 2    2    2    2
   prog71..prog98 (8 images)      2    2    2    2   each
   prog99_peq_overdr_delay        4    4    4    4
   prog15_rock_rotary             1    2    1    1   <-- unbalanced
   prog52_auto_wah                0    2    2    4   <-- unbalanced
   prog70_auto_wah_s_delay        0    2    2    4   <-- unbalanced
   prog97_peq_compr_overdr        2    4    2    2   <-- unbalanced
   kernel                         0    0    1    0   <-- unbalanced
   TOTAL                         36   42   41   43
```

The four unbalanced images are reported, not explained away: those programs use
the temporaries for something the biquad does not do, and that is a worklist
item (§10).

### 3.5 What is still OPEN inside `lo12`

* **fourteen of the eighteen SOURCE codes** — `dsp-alu-structure.md` §5 names
  four more from context (`0x0B` delay-RAM, `0x13` table, `0x08`/`0x1C` LFO);
  the biquad anchors none of them and this note claims none of them.
* **nineteen of the twenty-four ACTION codes.**
* **`0x12` vs `0x15`** — the biquad cannot see the difference, because `0x412`
  always carries `hi12` bit 4 in it and `0x415` never does.
* **bit 11** — locked to bit 5 in this corpus, so it carries no separable
  evidence here.

---

## 4. THE UNIFORM ALU

```
    L    := src[ lo12[10:6] ]   07 mem[ptr]  10 acc  19 tempA  1A tempB
    if hi12 bit 4 :  mem[ptr] <- acc ; acc := 0            <-- store AND CLEAR
    acc  += P ; P := 0                                     <-- P is CONSUMED
    lo12[4:0] :  13 -> tempA <- L   14 -> tempB <- L   07 -> mem[ptr] <- L
    if class4 == A :  P := coef[cursor++] * L
    if class4 & 7 == 2 :  ptr += (s8)addr8
```

`L` is latched **before** anything else. That is the same rule R1 FORCED for the
bit-4 store ("store = after" has zero survivors in all three models,
`r1-allpass-motif.md` F2), and it is what lets `212.A.FF.407` write the
accumulator to memory *and* multiply by it in one word.

Walk the section with it (`acc = x` on entry, `P = 0`):

```
 [0] 1D3  L=cell0=x1 ; tempA<-x1 ; acc += 0 (still x) ; P = b1*x1
 [1] 412  L=acc=x    ; bit4: cell0<-x, acc:=0 ; acc += P = b1*x1 ; P = b0*x
 [2] 1D5  L=cell1=x2 ; acc += P                       ; P = b2*x2
 [3] 1D4  L=cell2=y1 ; tempB<-y1 ; acc += P           ; P = A1*y1
 [4] 1D5  L=cell3=y2 ; acc += P                       ; P = A2*y2
 [5] 687  L=tempB    ; acc += P  -> the sum v is complete ; cell3<-tempB
 [6] 415  L=acc      ; acc += 0  -> identity, as measured
 [7] 407  L=acc=v    ; bit4: cell2<-v, acc:=0 ; acc += 0 ; nibble 7: cell2<-v ; P = G*v
 [8] 647  L=tempA=x1 ; acc += P = G*v = the band output ; cell1<-tempA
```

Nine words, one operation. `[0]`, `[6]` and `[7]` "do nothing to the
accumulator" **for free**, because `P` was already consumed — no `NONE` op is
needed anywhere.

**The store-and-clear on `hi12` bit 4 is the one genuinely new hardware claim
here.** It is FORCED by the section (the two words that carry bit 4 are exactly
the two at which the accumulator must restart from zero, and without it the
result is 57 dB wrong) and it is the natural end-of-MAC-chain primitive, but the
biquad only ever exercises it where the store and the clear coincide, so §7-A3
lists the alternative.

---

## 5. The fixed point, and the forced one-bit shift

The firmware writes `b1, b0, b2, −a1/a0` at `2^22` and `−a2/a0` at `2^23`
(MEASURED, `biquad-coeffs.md` §4; numerically re-confirmed in §1.1 here). Write
the five accumulated terms with unknown cell scales `2^p, 2^q, 2^r, 2^t` for
`x[n-1], x[n-2], y[n-1], y[n-2]` and an unknown product shift `s`:

```
   b1 : 2^(22+p-s)     b0 : 2^(22+u-s)     b2 : 2^(22+q-s)
   A1 : 2^(22+r-s)     A2 : 2^(23+t-s)
```

They must be one scale, so `p = q = r = u` and **`t = r − 1`**: the `y[n-2]`
cell holds **half** the scale of the `y[n-1]` cell. The only path between them
is `cell2 --(word [3])--> tempB --(word [5])--> cell3`, so **one of those two
words shifts right by one**. It cannot be word `[4]`'s read, because `[4]` is
`202.A.00.1D5` and `[2]` is `202.A.01.1D5` — the same word but for `addr8`, and
`[2]` must not shift. **FORCED.** Ablation: 77 dB.

The remaining alignment is `22 = P_SHIFT + ACC_SHIFT`, split between the
multiplier output and the "read the accumulator as a 24-bit datum" path. Only
the **total is forced**: every split from 2 to 12 gives numerically identical
results on all eleven banks (below 2 the 44-bit ALU overflows; above 12 the
truncation starts to show). The core uses 6/16 because that keeps the whole
48-bit product inside the 44-bit ALU with room for the five-term sum — the only
physical consideration that discriminates at all.

**The class-8 word is a numerical no-op on this path**, which is why the older
paper analysis matched at `0.000e+00` with it as the identity: with the
alignment above, "the sum is complete" and "the sum is a 24-bit datum" are the
same number, so nothing needs rescaling. Its *position* stays determined and its
*operation* stays OPEN — but §7-A5 now excludes a whole class of candidates.

---

## 6. THE ACCEPTANCE TEST — numbers, not impressions

Impulse of `2^22` (half full scale), 4096 samples, DFT at 12 frequencies from
20 Hz to 20 kHz, against `H(z)` computed directly from the same C-RAM words.
**Run on the arithmetic that actually ships** (`cxx_mirror.cpp` is a
copy-for-copy mirror of `upd6383_device::exec_alu()`):

```
   algo39 PARAMETRIC EQ  band 0     max |err| = 0.00205 dB   0.0082 deg
   algo39 PARAMETRIC EQ  band 1     max |err| = 0.00463 dB   0.0053 deg
   algo39 PARAMETRIC EQ  band 2     max |err| = 0.00123 dB   0.0061 deg
   algo39 PARAMETRIC EQ  band 3     max |err| = 0.00119 dB   0.0062 deg
   algo39 PARAMETRIC EQ  band 4     max |err| = 0.00116 dB   0.0062 deg
   algo33 OVERDRIVE tone stage      max |err| = 0.00066 dB   0.0241 deg
   algo35 EXCITER band              max |err| = 0.09405 dB   1.7201 deg
   algo99 PEQ+OVERDR+DELAY flat PEQ max |err| = 0.07502 dB   4.0252 deg

   distinct coefficient banks       8
   WORST over all of them           0.09405 dB
```

**How many independent sections agree: 8 distinct coefficient banks, in 11
section instances, across 4 different programs.** Within algorithm 39 that is
all five bands, and the same nine words serve both channels, so all **ten**
sections of the reference program are covered by five distinct banks.

**The residual is quantisation, and it is shown to be**: on the worst bank
(EXCITER, the highest-Q of the eight) the error falls monotonically with signal
level —

```
   impulse 2^10 : 41.155 dB     impulse 2^18 :  2.049 dB
   impulse 2^14 : 18.027 dB     impulse 2^22 :  0.094 dB
```

— which is what additive 24-bit state noise inside a high-Q recursion does and
what a structural error does not (a structural error is *scale-invariant*).

**Ablations — a criterion that cannot fail is not a pass** (worst over all 8
banks):

```
   full model (total alignment 22, split 6/16)     0.074 dB
   without the accumulator CLEAR on hi12 bit 4    57.193 dB
   with the one-bit shift on the tempB CAPTURE     0.074 dB   <-- INDISTINGUISHABLE, see 7-A1
   without the one-bit shift at all               76.610 dB
   total alignment 21 instead of 22               76.136 dB
   total alignment 23 instead of 22               90.712 dB
   a DIFFERENT split of the same total (2/20)      0.074 dB   <-- the split is NOT forced
   a DIFFERENT split of the same total (12/10)     0.074 dB
   ALT: hi12[3:1] selects the accumulator op       0.074 dB   <-- INDISTINGUISHABLE, see 7-A8
   ALT above, but WITHOUT the bit-4 clear         61.179 dB
```

The last two rows matter: the **accumulator clear is required under BOTH
readings of the accumulator op**, which is the strongest thing that can be said
for it from this block alone.

**Implementation equivalence**: the shipped C++ and the Python model in which
the decode was derived agree at **max |diff| = 0** over 512 samples × 11 section
instances.

---

## 7. Alternatives the constraints still admit — ENUMERATED

* **A1. Where the one-bit shift sits.** On the tempB **bus source** (`lo12[7:6]
  == 10`, what the core implements) or on the tempB **capture** (`lo12[3:0] ==
  4`). Indistinguishable inside the biquad, which always pairs them. It would be
  decided by a program that captures into tempB and then *multiplies* by it —
  `0x692`/`0x695` (class A, source `10`, 8 words) are the candidates.
* **A2. The `P_SHIFT` / `ACC_SHIFT` split.** Only the total (22) is forced; 2..12
  are numerically identical. Chosen: 6/16, on the 44-bit-ALU argument.
* **A3. What clears the accumulator.** Attached here to `hi12` bit 4. It could
  instead ride on `lo12` — but then `000.2.40.407` (no bit 4) would clear too,
  and the two words that need it are exactly the two that carry bit 4, so
  parsimony puts it on bit 4. NOT independently confirmed.
* **A4. Word `[1]`'s multiplicand.** `acc` or `mem[ptr]` — the same number,
  because bit 4 has just written one into the other. The SRC field breaks the
  tie by encoding (`0x412` → `00` = acc), it is not broken by the mathematics.
* **A5. What class 8 / `lo12 = 0x415` computes.** Anything that is the identity
  on a completed sum survives: round-to-nearest below the datum LSB, a
  saturation that does not fire, an OVC/flag update. **EXCLUDED**: any shift —
  `>>1` costs 84 dB and `<<1` 82 dB.
* **A6. `G = −2.0` in Q1.22 with `acc ← P` at `[8]`** versus `acc += P` at `[8]`
  with an effective `−1`. The uniform ALU makes `[8]` an ordinary `acc += P`
  and gets `G·v` only because `[7]` cleared; the *other* reading needs `[7]` not
  to clear and gives the section **−6 dB**. A five-band EQ at flat settings must
  have unity gain, so the implemented reading is the one that survives — but
  that last step is a DESIGN argument (INFERRED, strong), not a measurement.
* **A7. Which temp is "A".** Arbitrary naming; the *pairing* (§3.4) is forced.
* **A8 — THE BIG ONE. "One uniform op with `P` consumed" versus "`hi12[3:1]`
  selects the accumulator op with `P` NOT consumed."** In the section
  `hi12[3:1]` is `0` on words `[0]` and `[8]`, `1` on `[1][2][3][4][5][7]` and
  `2` on the class-8 word `[6]`. Read it as `0 → acc ← P`, `1 → acc += P`,
  `2 → neither`, and stop consuming `P`, and the section computes **exactly the
  same numbers, to the last bit, on all eight ROM banks** (measured: 0.074 dB,
  the same figure). The biquad cannot choose, because at `[0]` the product
  register still holds the band input (`G·v` from the previous band's `[7]`) so
  "load it" and "add nothing" are the same value, and at `[8]` the accumulator
  has just been cleared so "load" and "add" are the same value.

  **`notes/dsp-alu-crossval.md` B1 gives independent, FORCED evidence that
  `hi12[3:1]` does select an operation somewhere**: `092.A.dd.200` and
  `094.A.dd.200` are identical in `class4`, `addr8` and `lo12`, address the same
  D-RAM cell, consume the 0.6 Hz LFO rate and the `0x7FFFFF` wrap constant, and
  no single binary operation applied twice with those two constants makes a
  ramp. So the alternative is the one to **expect to win** once a second block
  is decoded. It is not implemented today only because it is unobservable on the
  block that was decoded, and because it needs a reading of *all* eight
  `hi12[3:1]` codes, not the three the biquad shows. Neither the field map
  (§3), the fixed point (§5) nor the store-and-clear (§4) depends on which way
  this goes — the ablation table shows the clear is required under both.

---

## 8. What this pass FALSIFIES or supersedes

**F1 — the 144 survivors are 1.** Survivor families that put the two state
writes on words `[2]` and `[4]` (they are printed in the tool's own output) are
**impossible**: `[2] = 0202A011D5` and `[4] = 0202A001D5` are the same 36-bit
word except for `addr8`, so they would have to store two *different* temporaries
with identical encoding. Enumerating the four combinations of
`cell1 ∈ {[2],[8]}` × `cell3 ∈ {[4],[5]}`, three die on that argument and only
`([8],[5])` — the "preferred" reading — survives. It is now FORCED, not
preferred.

**F2 — the accumulator op is not in `lo12`, and `[7]`'s "NONE" was never a
result.** `notes/kn5000-dsp-semantics.md`'s restriction R3 ("[7] must be NONE")
was an a-priori restriction that its own note printed inside the results block.
Under either reading of §7-A8 `[7]` is an ordinary word: the store-and-clear
explains it without any per-word op, and the `hi12[3:1]` reading puts the op in
the *other* half of the instruction. What is falsified in both cases is that
`lo12` carries it.

**F3 — `hi12` bit 4 is "store", but not only store.** The MEASURED part
(`0x212 = 0x202 + bit 4`, absence control 0/410 clean) and the FORCED timing
(before the word's own ALU step) stand. The accumulator clear is new.

**F4 — `0x1D4 = "latch B ← mem[p]"` was INFERRED; it is now FORCED**, and the
register it writes is tied by the encoding to the one `0x687` reads.

**F5 — the instruction-set note's "`lo12` selects the MULTIPLICAND ROUTE" is
CONFIRMED and sharpened.** It is bits[7:6] only, and it selects the operand bus
for the *whole word* — the multiplier, the memory write and the temp capture all
take it — not just the multiplier input.

**F6 — the three hi12-specific forms are superseded.** `202.A.dd.1D5`,
`202.A.dd.1D4` and `212.A.dd.407` were never hi12-specific: they were `lo12`
forms observed at one `hi12`. `hi12` bit 4 and `class4` were already MEASURED as
independent controls, so the hi12 restriction was carrying no evidence.

Nothing the earlier search *determined* is contradicted.

---

## 9. What changed in MAME, and what was measured after

`src/devices/cpu/upd6383/`:

* `upd6383d.h` — `lo_src()`, `lo_op()`, `lo_ptrmode()`, the `LO_SRC_*` /
  `LO_OP_*` codes, `alu_decoded()` (an **exact eight-value whitelist**, because
  bits[11:8] and bit 4 are still open and a word that shares an OP nibble while
  differing there is not known to be the same instruction).
* `upd6383d.cpp` — `decoded()` folds the three old forms into the field decode;
  the DECODED FORMS block carries the evidence; `text()` renders
  `mac/alu` + `.ta/.tb/.st` + the bus source; `addressing_only()` now excludes
  fully-decoded words, so the three states stay distinguishable.
* `upd6383.cpp` — `exec_alu()`, `acc_to_datum()`, `P_SHIFT`/`ACC_SHIFT`; both
  `execute_run()` and `run_frame()` route every decoded non-pointer word through
  it. **Latent bug fixed on the way**: both paths tested `hi == 0x000 && cl == 2`
  for `nop` without checking `lo`, which was safe only while `decoded()` was
  narrow; it now requires `lo == 0x000`.

MEASURED after (KN5000, `DSPCFG = On`, one C4 note, 768,170 frames):

| | before | after |
|---|---|---|
| words executed per frame | 43 of 285 (30 decoded + 13 addressing-only) | **89 of 285** (**77 decoded** + 12 addressing-only) |
| corpus words decoded | 270 of 3057 (8.8 %) | **1212 of 3057 (39.6 %)** |
| distinct corpus words decoded | 36 of 759 | **272 of 759** |
| distinct undecoded words still executing | — | 122 |
| frames kept | 0 (100 % trap) | 0 (100 % trap) |

**PREDICTION MADE BEFORE THE RUN, AND CHECKED**: exactly one of the twelve K6
input-stage words (`012.A.dd.1D5`, which the K6 note excluded *because* its
`hi12` is `0x012` and not `0x202`) would graduate from PARTIAL to DECODED.
Measured: partials 13 → 12. **HIT.**

**SAFETY PROPERTY, re-measured, still holds:** the WAV with `DSPCFG = On` is
**byte-identical** to the WAV with it Off (4,896,050 bytes, `cmp` clean). Every
frame still traps — 196 of 285 words per frame — so the return is still
discarded and no audio can leak. The input-stage audit is still clean
(589,610 frames, 0 mismatches, peak `0x279100`).

---

## 10. Sync list for `kn5000-roms-disasm/dsp/` (NOT edited here — an integrate agent owns it)

1. `dsp/instruction-set.md` — replace the three-form table with §4's uniform
   ALU; move `lo12` out of "landmarks" into a decoded field (bit 5, bits[7:6],
   five of bits[3:0]); record F1–F6; update the coverage block (9.0 % → 39.6 %
   by occurrence).
2. `dsp/tools/dsp_disasm.py` — mirror `lo_src`/`lo_op`/`alu_decoded` and the new
   `text()` rendering, then re-run `gen_dsp_disasm.py`; every `?word` whose
   `lo12` is one of the eight becomes a real mnemonic.
3. `dsp/analysis/r1-allpass-motif.md` — §9's open "what does `0x64B` route" is
   answered (tempA); add the `655`/`2D4` agreements from §3.3.
4. `dsp/algorithms/biquad-eq.md` — the "OPEN: what the class-8 word computes"
   line can be narrowed (§7-A5), and the 9-word table can carry the uniform ALU.
5. `notes/kn5000-dsp-semantics.md` — annotate R3 as a restriction, and record
   that the 144 residual is cut to 1 by the encoding.

## 11. Reproduce

```
python3 tools/kn5000_dsp_alu.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom
        # default sections: verify ablate
python3 tools/kn5000_dsp_alu.py <subrom> sweep    # the PSH/ASH split sweep
python3 tools/kn5000_dsp_alu.py <subrom> fields   # the lo12 sub-field census
```

The equivalence of the tool's model and the shipped C++ was checked with a
copy-for-copy mirror of `exec_alu()` compiled standalone (`cxx_mirror.cpp` in
the session scratchpad): max |diff| = 0 over 512 samples x 11 section instances.
`tools/kn5000_dsp_alu.py` is now the authority; if `exec_alu()` changes, re-run
the mirror.
