# NEC uPD6383GF — the PARAMETRIC EQ biquad as a Rosetta Stone

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_biquad.py` (imports `kn5000_dsp_class2.py`, which imports
`kn5000_dsp_extract.py`, `kn5000_dsp_coeffs.py`, `kn5000_dsp_params.py`; **none of them
is edited or rewritten**).

**This file is append-only successor material.** It does not edit
`notes/kn5000-dsp-class2.md`, `notes/kn5000-dsp-class2-round2.md`,
`notes/kn5000-dsp-parameters.md`, `notes/kn5000-dsp-coefficients.md`,
`notes/kn5000-dsp-encoding.md`, `notes/kn5000-dsp-header.md` or
`notes/kn5000-dsp-reverb.md`. Corrections to them are recorded in §8 here.

Every claim is tagged **MEASURED**, **INFERRED** or **SPECULATIVE**. §7 lists what is
falsified or explicitly not established. Where a claim was pre-registered, it says so.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_biquad.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
```
Sections: `sections section cursor hostxref class4 rewind`.

---

## Headline

1. **The sixth class-A word is explained, and it is not a hack.** The host writes the
   PARAMETRIC EQ's coefficients in blocks of **stride 6** (`T1 op 70 -> 00 06 0C 12 18`),
   and the section contains exactly **6 class-A words**. Six coefficients per band, six
   multiplies per band. **MEASURED on both sides, from two physically different tables.**
   (§2)
2. **Three-way quantitative agreement on the per-band memory layout** (§3): the signed
   `addr8` displacements inside the section sum to **exactly +4** per band; the two
   channels' state bases differ by **exactly 20 = 5 × 4**; and the host's second `op 70`
   address group is **5 addresses at stride 4**. Three independent instruments, one
   number.
3. **★ THE TWO-CHANNEL CONTROL PASSES, and it passes by a mechanism, not a correlation.**
   Channel 1's setup contains `801.0.00.021` — the *proven* pointer-load idiom with
   immediate 0 — which occurs **exactly once in the entire 96-program corpus** (§4).
   The coefficient cursor is rewound to 0 for channel 1 (**same coefficients**) while
   the state base word `000.2.40.407` becomes `000.2.54.407` (**different state,
   +20**). That is exactly what a stereo EQ must do, and it was predicted before it was
   looked for.
4. **★ The class-8 word is a per-biquad-section marker, 1:1, across 12 images** (§5):
   `count(804.8.16.415) == count(biquad sections)` in 11 of 12 images that contain
   either, including `PEQ+OVERDR+DELAY` where **both counts are 4** and decompose
   additively as 2 (PEQ, 1 band × 2 ch) + 2 (OVERDRIVE tone × 2 ch).
5. **★★ TASK 2, part answered and part killed** (§6). The strict prediction —
   *non-delay effects contain no class-1 word beyond the terminator* — **FAILS**: 6 of
   the 14 non-DRAM images violate it. But `class4` **does** behave as an operand-space
   selector in a stronger, unexpected way: **classes 0, 4, 5 and 8 have a constant
   `addr8` corpus-wide (0x00, 0x01, 0x00, 0x16 over 148 / 54 / 42 / 44 words), i.e. no
   address operand at all.** MEASURED, no exceptions.
6. **★ `C40.1.E0.451` is the compressor's level detector**: present in exactly
   `COMPRESSOR`, `PEQ+COMPRESSOR`, `PEQ+COMPR+DIST`, `PEQ+COMPR+OVERDR` — 4 TP, 0 FP,
   0 FN over 38 images (§6.3).
7. **The topology is discriminated by counting stores** (§3.4): the section has exactly
   **two** P-consumers. A transposed direct-form II (5 multiplies, 2 states, **2**
   stores) fits; a plain direct-form I (5 multiplies, 4 states, **4** stores) does not.
   This is the one place where the biquad's external specification does real work.
8. **A fresh instance of the exact blindness that produced the retracted "4 bands"**
   (§1.1): byte-identical search finds **8** sections in the corpus outside algo 39;
   near-miss-tolerant search finds **27**. Nine of the ten PEQ-bearing combination
   effects are invisible to a byte-identical search.

---

## 1. The section, and how many there are

### 1.1 The instrument matters (MEASURED)

Tool section `sections`. Reference = `algo39` words 5..13. Counting windows that differ
from the reference in at most *d* words:

```
   algo name                    d=0  d=1  d=2
     33 OVERDRIVE                 0    0    2
     35 EXCITER                   0    0    2
     39 PARAMETRIC EQ             8   10   10
     71 PEQ+CHORUS                0    2    2
     72 PEQ+S.DELAY               0    1    2
     73 PEQ+FLANGER               0    2    2
     74 PEQ+VIBRATO               0    2    2
     75 PEQ+COMPRESSOR            0    2    2
     96 PEQ+COMPR+DIST            0    2    2
     97 PEQ+COMPR+OVERDR          0    2    2
     98 PEQ+DIST+DELAY            0    2    2
     99 PEQ+OVERDR+DELAY          0    2    4
```

At `d = 0` the corpus appears to contain the section only in algorithm 39, and only 8
times. At `d = 2` it contains **27 sections in 12 images**. The round-one CORRECTION's
"4 bands" was produced by a `d = 0` search; the same instrument, applied corpus-wide,
would have hidden ten whole effects. **This note's search is `d ≤ 2` throughout, and the
reason is stated before the counts.**

### 1.2 Only two of the nine words ever vary (MEASURED)

Over all 27 sections, words **[1]..[7] are byte-identical without exception**. The two
that vary are:

```
   [0]  000.A.00.1D3   also 022.A.00.1D3 (algo72 ch0), 102.A.00.1D3 (algo33, algo99
                       overdrive stage), 212.A.00.1D3 (algo35)
                       -- only hi12 changes; class4=A, addr8=00, lo12=1D3 always
   [8]  000.2.03.647   also 000.2.AD.647, 000.2.C1.647, 000.2.B0..C0.647,
                       880.1.30.647  -- only addr8 changes (once, the whole class)
```

> **INFERRED, strong:** word [0] is the multiply that brings the **input sample** in
> (`hi12` selects *which* signal, and the section is otherwise source-agnostic), and
> word [8] is the **hand-off** to whatever comes next (`addr8` selects where). The
> seven words between them are a fixed, source-independent second-order kernel.
> This is the opposite of the reverb/phaser result in round two §1.2, where the operand
> source was baked into the whole arithmetic word — here the machine *does* have a
> reusable kernel, because everything it touches is reached through cursors.

### 1.3 Band counts (MEASURED)

* algo 39 `PARAMETRIC EQ`: **10 sections** at 5, 14, 23, 32, 41 | 59, 68, 77, 86, 95 =
  5 bands × 2 channels. Round two §5 is confirmed by a third route.
* Every PEQ *combination* effect: **2 sections** = 1 band × 2 channels — confirmed
  independently by the host map, which gives those effects **two** `op 70` addresses
  (`algo71: 02 12`, `algo72: 00 0A`, `algo75: 00 0F`, `algo96: 00 13`, `algo99: 00 14`)
  against algo 39's **ten**.
* algo 99 `PEQ+OVERDR+DELAY`: **4 sections**, and algo 33 `OVERDRIVE` alone has **2**.
  2 + 2 = 4. **MEASURED additivity across a composite effect.**
* `OVERDRIVE` and `EXCITER` carry the same section: those effects have tone-shaping
  biquads, which their `filt` label in `IMG_CAT` already asserted.

---

## 2. ★ The sixth class-A word — resolved by the host write map

The brief's sharpest question. The section is

```
    [0] 000.A.00.1D3   class A     multiply
    [1] 212.A.01.412   class A     multiply
    [2] 202.A.01.1D5   class A     multiply
    [3] 202.A.01.1D4   class A     multiply
    [4] 202.A.00.1D5   class A     multiply
    [5] 102.2.FF.687   class 2     P-CONSUMER (round two: lo12 687 must follow class A)
    [6] 804.8.16.415   class 8     the only class-8 word in the section
    [7] 212.A.FF.407   class A     multiply  <- the SIXTH
    [8] 000.2.03.647   class 2     P-CONSUMER (round two: lo12 647 must follow class A)
```

Six multiplies where a biquad needs five. **The answer is that the band really does have
six coefficients**, and it comes from the host side, which knows nothing about this
microcode:

```
    algo 39 PARAMETRIC EQ   T1 op 70 -> 00 06 0C 12 18 | 64 68 6C 70 74
                            first group: 5 addresses, STRIDE 6
    T2: 15 records, op70 operands 0,0,0 1,1,1 2,2,2 3,3,3 4,4,4
                            5 bands x (frequency, Q, gain)
```

* **MEASURED:** the host reserves **6 words per band** for coefficients.
* **MEASURED:** the section contains **6 class-A words**.
* 5 bands × 6 = **30** coefficient words, spanning `0x00..0x1D` — which is exactly the
  span implied by bases `00, 06, 0C, 12, 18`.

> **ROLE (INFERRED):** each class-A word consumes one word of the band's 6-word
> coefficient block, through a cursor that advances implicitly by one per class-A word
> (which is why `addr8` in the class-A words is *not* the coefficient address — it is
> doing something else; see §3). The identity of the sixth coefficient is
> **NOT ESTABLISHED**; a per-band output level and a fixed-point scale exponent are both
> consistent with everything measured, and neither is claimed.
* **NOT ESTABLISHED:** which of the six is b0/b1/b2/a1/a2. The three-way `hi12` grouping
  ({[0]} = 000, {[1],[7]} = 212, {[2],[3],[4]} = 202) is a real structure and is the
  obvious place to attack next, but assigning names to it would be exactly the seductive
  nine-jobs-nine-words fit the brief warns about, so it is not done here.

**Control against the P-consumer statistic (round two §3):** the two class-2 words are
the *only* two P-consumers in the section, and each immediately follows a class-A word.
**0 violations over all 10 sections × 2 consumers.** The accumulation happens where the
order statistic says it must.

---

## 3. ★★ The per-band memory layout, from the signed `addr8` walk

### 3.1 The arithmetic (MEASURED)

Reading `addr8` as a signed 8-bit displacement and excluding the class-8 word (justified
below):

```
   [0] 000.A.00.1D3  addr8  +0   running  +0
   [1] 212.A.01.412  addr8  +1   running  +1
   [2] 202.A.01.1D5  addr8  +1   running  +2
   [3] 202.A.01.1D4  addr8  +1   running  +3
   [4] 202.A.00.1D5  addr8  +0   running  +3
   [5] 102.2.FF.687  addr8  -1   running  +2
   [6] 804.8.16.415  class 8 -- EXCLUDED
   [7] 212.A.FF.407  addr8  -1   running  +1
   [8] 000.2.03.647  addr8  +3   running  +4
                                 -------  +4  per band
```

`0xFF` is `-1`; round two's phaser idiom (`c + s == 0xFF`) already suggested a signed
reading, and here the reading is forced by the totals.

### 3.2 Three independent confirmations of "4 words per band" (MEASURED)

| instrument | value |
|---|---|
| signed `addr8` total inside one section | **+4** |
| channel-1 state base minus channel-0 state base (`000.2.54.407` − `000.2.40.407`) | **0x14 = 20 = 5 × 4** |
| host `T1 op 70`, second address group `64 68 6C 70 74` | 5 addresses, **stride 4** |

Three tables that know nothing about each other. **INFERRED:** each band owns a **4-word
state block** in the pointer-walked space, five bands per channel, 20 words per channel,
channel 0 at base `0x40` and channel 1 at base `0x54`.

### 3.3 Why the class-8 word is excluded (MEASURED, a real negative)

`804.8.16.415` has `addr8 = 0x16 = +22`. Including it would make the per-band total
`+26`, so the channel delta would have to be 130, not the measured 20. **Therefore the
class-8 word does not touch this cursor.** §6.1 gives the independent reason: *every*
class-8 word in the corpus has `addr8 = 0x16`, so the field is not an address there at
all.

### 3.4 Post-increment, not pre-increment — and what that decides (INFERRED)

If `addr8` were added *before* the access, word [8] (`+3`) would write into the *next*
band's state block, which is wrong. If it is added *after*, the accesses are

```
   [0] S0   [1] S0   [2] S1   [3] S2   [4] S3   [5] S3   [7] S2   [8] S1
   and the cursor leaves the section pointing at S4 = the next band's S0.
```

Four distinct cells `S0..S3` — matching the stride-4 block exactly — and the cursor ends
where the next band needs it. **INFERRED: the displacement is a post-increment.**

**The store count, and the topology it kills.** Exactly **two** words in the section are
P-consumers ([5] and [8]), so at most two memory writes happen per band per sample —
into `S3` and `S1`.

> **PREDICT THEN CHECK.** A textbook direct-form I biquad needs **four** state updates
> (`x2<-x1, x1<-x, y2<-y1, y1<-y`). A transposed direct-form II needs **two**
> (`s1' = b1*x + s2 - a1*y`, `s2' = b2*x - a2*y`). The section provides two.
> **Direct form I is not what this section computes**, unless a store hides in the
> class-8 word or a single write is two words wide — neither of which is established.
> **INFERRED, and the strongest topological statement this note makes.**
> Residual puzzle, stated honestly: DF-II-T needs only two state words, and the block is
> four. The other two cells are written by nothing in the section. **NOT ESTABLISHED.**
* **NOT ESTABLISHED:** which of `S0..S3` is which. Cells are visited in the order
  S0,S0,S1,S2,S3,S3,S2,S1 and only S3 and S1 are written.

---

## 4. ★ THE TWO-CHANNEL CONTROL (the mandatory one)

The brief's demand: the channels must share coefficients and differ in state; if a
"state" address does not differ between the groups, the assignment is wrong. The 9-word
sections are byte-identical between the groups, so the difference must live in the gap
between index 41's section and index 59's — and it does.

```
   ch0 setup                 ch1 setup (words 50..58)
   [  0] 000.2.0B.1CD        [ 53] 000.2.0A.1CD     addr8  -1
   [  1] 000.2.00.40E        [ 52] 000.2.F7.000
   [  2] 212.2.00.000        [ 55] 212.2.02.000     addr8  +2
   [  3] 02A.2.00.000        [ 56] 02A.2.00.000     identical
   [  4] 000.2.40.407        [ 57] 000.2.54.407     addr8  +20  (0x14)
                             [ 50] 028.2.00.000
                             [ 51] 880.1.30.407
                             [ 54] 000.2.FF.1CE
                             [ 58] 801.0.00.021     <-- unique in the whole corpus
```

**Two facts, both MEASURED:**

1. **`000.2.40.407` vs `000.2.54.407` is a perfect minimal pair** — same `hi12`, same
   `class4`, same `lo12`, `addr8` differing by exactly **20**, the size of one channel's
   five 4-word state blocks. **The state addresses do differ between the channels, and
   by exactly the predicted amount.** The control passes.
2. **`801.0.00.021` occurs exactly ONCE in all 96 programs**, and it is in channel 1's
   setup, immediately before channel 1's first section. `hi12 = 0x801` and the 8-bit
   immediate in `addr8` are the *proven-by-construction* pointer-load form
   `801.0.NN.821` (parameters note §2); this one differs only in bit 11 of `lo12`.

> **INFERRED, and it was predicted before it was looked for:** `801.0.00.021` reloads
> the **coefficient** cursor to 0 so that channel 1 re-reads the *same* 30 coefficient
> words channel 0 used. That is required, because the host writes **one** coefficient set
> for algorithm 39 (`T1 op 70` first group has five bases, not ten).
>
> **THE CROSS-CHECK, and it is the good one.** In the *combination* effects the host
> writes **two** coefficient bases per band (`algo71: 02 12`, `algo72: 00 0A`,
> `algo75: 00 0F`, `algo96: 00 13`, `algo99: 00 14`) — the channels there do **not**
> share coefficients. **Prediction: those images should not contain the rewind.**
> **CHECK: none of them contains `801.0.NN.021` at all.** The word exists once in the
> corpus and only in the one program that needs it.

**Host cross-check on the coefficient addresses (MEASURED):** the region the microcode's
coefficient cursor walks — base 0, six words per section, five sections — is
`0x00..0x1D`, and the addresses the host writes PEQ coefficients to are
`0x00, 0x06, 0x0C, 0x12, 0x18` with 6-word blocks, i.e. `0x00..0x1D`. They are the same
region. (Both are pre-relocation offsets; the descriptor base of parameters note §7 is
added to the host side at run time, so this is an agreement of *layout*, not of absolute
addresses. Stated as such.)

---

## 5. ★ The class-8 word: a per-section marker (MEASURED)

`804.8.16.415` is the only class-8 word in the section, and it sits between the two
P-consumers. Counting it against the sections found in §1:

```
   algo  name                 804.8.16.415   sections
     15  ROCK ROTARY               1             0      <-- the only mismatch
     33  OVERDRIVE                 2             2
     35  EXCITER                   2             2
     39  PARAMETRIC EQ            10            10
     71  PEQ+CHORUS                2             2
     72  PEQ+S.DELAY               2             2
     73  PEQ+FLANGER               2             2
     74  PEQ+VIBRATO               2             2
     75  PEQ+COMPRESSOR            2             2
     96  PEQ+COMPR+DIST            2             2
     97  PEQ+COMPR+OVERDR          2             2
     98  PEQ+DIST+DELAY            2             2
     99  PEQ+OVERDR+DELAY          4             4
```

**11 of 12 images match exactly, including the 10-vs-10 and the 4-vs-4.** The two other
class-8 words in the corpus are `80A.8.16.000` (ROCK ROTARY, PEQ+COMPR+OVERDR; 4
occurrences) and `804.8.16.1DA` (AUTO WAH, AUTO WAH+S.DELAY; 4 occurrences) — the AUTO
WAH form appears in exactly the two images with a sweeping filter and no biquad section,
which is a consistent picture but is not scored here.

> **What the class-8 word IS: NOT ESTABLISHED.** Its position (after the accumulate,
> before the last multiply) and §6.1 (class 8 = class 0 with the multiply bit set, and
> class 0/8 have no address operand) together say it is an *operand-less* operation on
> the accumulator — a shift, a saturate, a round, or the transfer of the accumulated sum
> into the multiplier's K/L latch for word [7]. The last of those would explain why
> word [7] multiplies something that is not a fresh memory read. **SPECULATIVE**, and
> deliberately not resolved: `addr8 = 0x16` is a constant whose meaning is unknown.

---

## 6. TASK 2 — is `class4` an address-space selector for body words?

### 6.1 ★ It is, in a way nobody predicted (MEASURED, no exceptions)

Corpus-wide `class4` histogram over 96 programs:

```
   class 0    148      class 4     54      class 8     44
   class 1    981      class 5     42      class A   1546
   class 2   3630      class 6     54      never observed: 7 9 B C D E F
```

And `addr8` conditioned on the class:

```
   class 0:   1 distinct addr8 over   148 words   <-- CONSTANT 0x00
   class 1:   7 distinct addr8 over   981 words
   class 2: 105 distinct addr8 over  3630 words
   class 3:   2 distinct addr8 over    33 words
   class 4:   1 distinct addr8 over    54 words   <-- CONSTANT 0x01
   class 5:   1 distinct addr8 over    42 words   <-- CONSTANT 0x00
   class 6:   5 distinct addr8 over    54 words
   class 8:   1 distinct addr8 over    44 words   <-- CONSTANT 0x16
```

> **MEASURED, and this is the real Task-2 result:** `class4` determines *whether the
> instruction has an address operand at all*. Classes **0, 4, 5, 8** never vary `addr8`
> in 288 words; classes **1, 2, 3, 6, A** do. That is precisely the behaviour of an
> operand-space field in which some encodings mean "no memory operand", and it transfers
> round two §4's proof-by-construction from the host-poke population to the body words —
> in a weaker form (the *field's job* transfers; the *specific values* do not).

**Bit 3 of `class4` is the multiply bit (MEASURED, corroborating).** Only 12 distinct
words exist in the corpus in both bit-3 polarities, and **every one of those 12 pairs is
2 ↔ A**; no 0↔8, 1↔9, 3↔B pair exists. Combined with `A = 2|8` and `8 = 0|8`, the
consistent reading is `class4 = {multiply bit} : {3-bit operand space 0..6}`, with only
spaces 0 and 2 ever used with the multiplier. **INFERRED.** This also reframes the
class-8 word of §5: it is *a multiply with the operand-less space*, which is why the
section is better described as six memory-operand multiplies plus one operand-less one.

### 6.2 The strict prediction — STATED, THEN FALSIFIED (MEASURED)

> **PREDICTION (pre-registered in the tool, from the brief):** if `class4 = 1` selects
> the external DRAM, effects with no external delay memory should contain **no class-1
> word other than the terminator**.

Every one of the 38 distinct images contains class-1 words (3 to 33 of them). Removing
the terminator and the known `880.1.30.*` framing family (round two §1.1):

```
   non-DRAM images with NO non-framing class-1 word:  8
      PHASER, DISTORTION, OVERDRIVE, FUZZ, EXCITER, PARAMETRIC EQ, AUTO PAN, AUTO WAH
   non-DRAM images that VIOLATE the prediction:       6
      NO OPERATION, COMPRESSOR, RING MODULATOR,
      PEQ+COMPRESSOR, PEQ+COMPR+DIST, PEQ+COMPR+OVERDR
```

**The prediction fails: 6 of 14.** It is worth being blunt about it, because it was the
project's leading hypothesis. What survives is narrower and is exactly what round two
already had: the specific pair `880.1.60.*` / `880.1.20.*` is the DRAM bracket
(TP 24 / FP 1 / FN 0, the FP still `NO OPERATION`), and it is the *word*, not the
*class*, that carries the information.

Two of the six violations are not DRAM traffic at all:

* `RING MODULATOR` has a lone `880.1.60.000` with no matching `880.1.20.*` — half a
  bracket, which under the round-two reading is an open transaction that never closes,
  i.e. probably not a delay access.
* the four compressor images violate through `C40.1.E0.451`, which is §6.3.

### 6.3 ★ `C40.1.E0.451` is the compressor's level detector (MEASURED)

```
   C40.1.E0.451  x8   COMPRESSOR, PEQ+COMPRESSOR, PEQ+COMPR+DIST, PEQ+COMPR+OVERDR
```

Every compressor-bearing image, twice each (one per channel); **4 TP, 0 FP, 0 FN over
38 images**; hypergeometric p = 1/C(38,4) = 1.4e-5. This extends round one's
`hi12 = 0xC40` = envelope/level detector to a specific class-1 word, and it explains a
third of the §6.2 violations as detector reads rather than delay reads. `REVERB x12`'s
`C40.1.80.000` (×4) is the same family at a different address.

### 6.4 C-RAM vs D-RAM — NOT RESOLVED, and here is why (MEASURED)

The chip has C-RAM 256×24 and D-RAM 256×24 plus a bank register `BNK-R`. If `class4`
distinguished them, the addressed classes would split into two comparable populations.
They do not: of the 6244 addressed words, **3630 are class 2 and 1546 are class A**
(which is class 2 with the multiply bit), leaving 981 class-1, 33 class-3 and 54
class-6. **`class4` does not separate C-RAM from D-RAM in the body words.** Candidates
that remain, none tested here:

* **the cursor identity.** The PEQ section walks *one* cursor across five different
  `lo12` values (`1D3, 412, 1D5, 1D4, 687, 407, 647` all participate in the +4 total),
  so `lo12` is not a per-word pointer selector for that pointer — but it could still
  select *which* of CP/DP/BP1/BP2/PR1/PR2 an instruction uses, with the section simply
  happening to use one of them throughout. Untested.
* **`BNK-R`.** Nothing in the corpus has been identified as writing it.
* **The one hard datum** remains the parameters note's: the host's two writer families
  target two different memories, distinguished there by `class4` 0 vs 1 in the *poke*
  words. That says the two memories exist and are separately addressable from the host;
  it says nothing about how a body instruction picks one.

---

## 7. The rewind word — NOT DECODED, stated as such

Word [8] across every PEQ-bearing image (tool section `rewind`):

```
   39 PARAMETRIC EQ    03 03 03 03 AD | 03 03 03 03  880.1.30.647
   71 PEQ+CHORUS       C1 | B9        73 PEQ+FLANGER   C1 | BB
   72 PEQ+S.DELAY      C1 | BD        74 PEQ+VIBRATO   C1 | BB
   75 PEQ+COMPRESSOR   C1 | BC        96 PEQ+COMPR+DIST C1 | BC
   97 PEQ+COMPR+OVERDR C1 | BA        98 PEQ+DIST+DELAY C1 | BD
   99 PEQ+OVERDR+DELAY C1 BD | B9 B5  (PEQ, overdrive tone | same, ch1)
   33 OVERDRIVE        B4 | B0        35 EXCITER        C0 | BC
```

**MEASURED:** `0x03` (= +3, the mid-chain advance) occurs only inside algorithm 39's
chains. The *last* section of a channel always carries a large value in `0xAD..0xC1`
(negative if signed), and **channel 0's value is `0xC1` in all nine one-band PEQ
combination effects** while channel 1's varies per effect (`0xB9..0xBD`).

> **INFERRED, weak:** the last section of a chain hands the cursor to whatever runs next;
> channel 0 always hands to channel 1's PEQ (identical shape, hence the constant `0xC1`),
> and channel 1 hands to the *following effect block*, which is what differs between
> `PEQ+CHORUS` and `PEQ+FLANGER` (hence the variation).
> **NOT ESTABLISHED, and it does not close:** on the signed-displacement reading,
> algorithm 39's channel-0 value should differ from the one-band effects' by the extra
> 16 state words its chain walked, and the measured difference is
> `0xC1 − 0xAD = 20`, not 16. A residual of exactly one band's state block is
> unexplained. **The alternative — that `addr8` here is an absolute pointer reload
> rather than a displacement — is equally consistent with everything above and is not
> excluded.** No reading is claimed.

---

## 8. Corrections and cross-checks against the earlier notes

| earlier claim | source | status here |
|---|---|---|
| 10 sections = 5 bands × 2 channels | round two §5 | **CONFIRMED** by a third route (host `T1 op 70` has 10 entries vs 2 for the one-band variants) and by the tolerant search |
| "the biquad section repeats 8× = 4 bands" | class2 note CORRECTION (already retracted) | **stays refuted**; §1.1 shows the same `d=0` instrument hides 10 further images corpus-wide |
| `lo12 ∈ {647, 687}` are the biquad's non-multiply words | class2 note §4.2 | **UPHELD and sharpened**: they are the section's only two P-consumers, 0 violations in 10 sections |
| `647/687` MUST-FOLLOW-A | round two §3 | **CONFIRMED**, 20/20 in algo 39 |
| `801.0.NN.821` = pointer load with 8-bit immediate | parameters note §2, MEASURED | **used as the key**; the variant `801.0.00.021` is the channel-1 coefficient rewind |
| `addr8` is a displacement off an advancing pointer | class2 note §6.2, round two §2 | **CONFIRMED quantitatively** for the first time: signed, post-increment, +4 per band, 20 per channel |
| `c + s == 0xFF` in the phaser | round two §1.4 | **supported**: `0xFF` here is unambiguously `-1` |
| body-word `class4` is an address-space selector | round two §4/§9.1, leading hypothesis | **PARTLY CONFIRMED, PARTLY KILLED** (§6.1, §6.2) |
| `IMG_CAT[3]` ENHANCER should be `(…,1,1,0,0)` | round two §1.5 | not applied (that file is round one's and is not edited); the class-1 tables here print ENHANCER's original label |
| bit 23 = the multiplier | class2 note §5 | **supported by a new argument** (§6.1): only 2↔A pairs exist, never 1↔9 or 3↔B |

**A caveat on `IMG_CAT`.** The `dram` labels used in §6.2 are round one's, unrepaired.
`ENHANCER` is labelled `dram=1` there and round two argues it is an internal-RAM
all-pass; it passes §6.2 either way (it has a real DRAM bracket), so nothing here turns
on it. The `filt` labels are likewise round one's, and §1.3's discovery that `OVERDRIVE`
and `EXCITER` carry biquad sections is consistent with `filt=1` for both.

---

## 9. Falsified, or explicitly not established

* **"Non-delay effects contain no class-1 word beyond the terminator."** **FALSIFIED**
  (§6.2), 6 of 14 non-DRAM images violate it.
* **`class4` as a clean C-RAM / D-RAM selector.** **NOT SUPPORTED** (§6.4): 83 % of
  addressed words are class 2 or class A.
* **The identity of the six coefficients** (which is b0/b1/b2/a1/a2 and what the sixth
  is). NOT ESTABLISHED (§2); the `hi12` grouping 000 | 212,212 | 202,202,202 is the
  handle.
* **Which of `S0..S3` is which state variable.** NOT ESTABLISHED (§3.4). Only two of the
  four are written per sample, which is why direct form I is rejected but no form is
  asserted.
* **What the class-8 word does**, and what `addr8 = 0x16` means in it (§5).
* **The rewind word** (§7): a residual of exactly 4 (one band's state block) defeats the
  displacement reading, and the absolute-reload reading is not excluded.
* **Why `ROCK ROTARY` has one `804.8.16.415` and no biquad section** — the single
  mismatch in §5.
* **`NO OPERATION`** continues to be the corpus's problem child: it is the false positive
  for the DRAM bracket (round two §1.1), for `0xC40` (round one §4.4) and for §6.2 here.

## 10. Next experiments, in order of value

1. **Read the coefficients numerically.** Algorithm 39's static coefficient bank is
   45 words of which 43 are zero (round two §5) — a scratch zero-fill — so the live
   values come from the host at `0x00..0x1D`. Drive the parameter path with a known
   (frequency, Q, gain) triple through `op 0x70`'s eval helper, print the six words it
   produces, and fit them to a textbook peaking-EQ biquad. That converts §2 from
   "six coefficients" to "these six coefficients", and it would name all six at once.
   This is by far the highest-value next step, and it does not require the emulator.
2. **Decode `op 0x70`'s eval helper** in the sub-CPU disassembly. It is the routine that
   turns 3 user parameters into 6 DSP words; its arithmetic *is* the coefficient
   assignment.
3. **Attack the state block with the same lever.** `T1 op 70`'s second group
   (`64 68 6C 70 74`) is never referenced by algorithm 39's T2 stream. Find who reads
   `T1[op][operand + nbands]` — that code knows the state layout by construction.
4. **Test the cursor-identity hypothesis for C-RAM vs D-RAM** (§6.4) by checking whether
   any single program walks two independent cursors with disjoint `lo12` sets.
5. **Score `804.8.16.1DA` against the AUTO WAH pair** properly (§5), and find out what
   `ROCK ROTARY` is doing with its lone class-8 word.
