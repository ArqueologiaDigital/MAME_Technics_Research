# NEC uPD6383GF vs the uPD7720/7725 — is it a family descendant?

KN5000 IC311 effects DSP. Date: 2026-07-22.
Tool: `tools/kn5000_dsp_necfamily.py` (imports `kn5000_dsp_extract.py` and
`kn5000_dsp_encoding.py`; reuses the capture parser shape of `kn5000_dsp_wordfields.py`.
Nothing is rewritten.)

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_necfamily.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
```
Sections: `layouts branch pconsume alu top cond`.

Corpus as always: 91 valid programs, **38 distinct images, 2974 words, 688 distinct**,
plus the cold-boot capture blocks at I-RAM 0 (60 words), 60 (23 words) and 84.

Every claim tagged **MEASURED / INFERRED / PROVEN BY CONSTRUCTION / SPECULATIVE**.

---

## HEADLINE

**The 7725-descendant hypothesis is REJECTED as an encoding model.** Four independent
tests were pre-registered; three fail outright and the fourth is at the trivial floor.
The one architectural idiom that *does* carry over is generic to all horizontal
microcode, not to the 7725 specifically.

**No branch was found — and this round produced, for the first time, a positive reason
why: the effect bodies are demonstrably HAND-UNROLLED.** `algo16` (the 133-word reverb)
contains 32 consecutive words that repeat at period 8 differing *only* in `addr8`;
`algo39` contains 36 words repeating at period 9; the phaser `algo05` 25 words at
period 3. A machine that could loop would loop these — I-RAM is only 384 words and the
reverb eats a third of it. The branch search is not failing because we are looking in
the wrong place; **there is nothing to find in the effect bodies.**

---

## 1. The family idioms, in our own words

### 1.1 uPD7725 (MAME `src/devices/cpu/upd7725/`, `dasm7725.cpp` / `upd7725.cpp:333`)

24-bit word, three instruction TYPES selected by `opcode >> 22`:

| type | name | shape |
|---|---|---|
| 0 | OP | horizontal: everything below happens in one cycle |
| 1 | RT | identical to OP, **plus** return-from-subroutine |
| 2 | JP | 9-bit branch condition [21:13], 11-bit next address [12:2], 2-bit bank [1:0] |
| 3 | LD | 16-bit immediate `opcode >> 6`, 4-bit destination [3:0] |

The OP/RT word allocates, top to bottom:
`psel[21:20]` (which of RAM / IDB / M / N feeds the ALU's second operand — this is where
the **multiplier product** enters, `m`/`n` being the halves of P) · `alu[19:16]` (16 ops:
`nop or and xor sub add sbb adc dec inc cmp shr1 shl1 shl2 shl4 xchg`) ·
`asl[15]` (ACCA or ACCB) · `dpl[14:13]` (DP low nibble nop/inc/dec/clr) ·
`dphm[12:9]` (XOR-modify the DP high nibble — a cheap bit-reversal/stride trick) ·
`rpdcr[8]` (decrement the ROM pointer) · **`src[7:4]` and `dst[3:0]`**, a completely
independent register-to-register move that executes in parallel with the ALU op.

Design idioms worth naming:

1. **Type at the very top**, and it *re-purposes the whole rest of the word*. JP and LD
   share no field position with OP at all.
2. **A parallel move field at the very bottom** (`src`,`dst`), orthogonal to the ALU.
   `dst==0` (`non`) is how you say "no move" — so the low byte is legitimately zero very
   often.
3. **Pointer modification is encoded as tiny mode fields**, not as arithmetic.
4. **Conditions live only inside JP**, in a 9-bit field, and the encoding is
   `cond<<1 | polarity` (JNCA 0x080 / JCA 0x082, JNZA 0x088 / JZA 0x08a, …). Predication
   of ordinary instructions does not exist.
5. **Immediates are carried by their own instruction type** and occupy the *top* 16 bits
   with the destination at the bottom.
6. The register file is tiny and named: ACCA/ACCB, TR/TRB, DP, RP, DR, SR, K/L, SIM/SIL,
   SOL/SOM. `src`/`dst` are 4-bit *enumerations of registers*, not an address space.

### 1.2 The other two NEC cores in MAME are NOT relatives

* `upd177x/upd177xd.cpp` — 16-bit **vertical** ISA, dispatched through a
  `{match, mask}` table (`0x4000/0xe000 = mvi`, `0x6000/0xf000 = jmp abs12`, …), with
  8-bit immediates and 5-bit register indices. Nothing horizontal about it.
* `upd777/upd777dasm.cpp` — likewise a vertical, table-dispatched microcontroller ISA.

**MEASURED (by reading the code): "the NEC DSP family" is not a lineage.** Only the
uPD7720/7725 is horizontal microcode. If the 6383 is a descendant of anything in MAME
it is of the 7725 alone, so that is the only hypothesis worth testing.

### 1.3 What the 6383 has that the 7725 does not

From the CDJ-500 block diagram (pp. 1-15..1-17): 44-bit ALU (vs 16), **two** shifters
(vs one implicit), OVC on input *and* output, **six** address pointers CP/DP/BP1/BP2/
PR1/PR2 plus BNK-R (vs DP/RP), **two** 256×24 RAMs (vs one 256×16), **three** loop
counters LC1–LC3, TR0–TR3, a 2-level stack, an external DRAM delay controller with 17
address bits, 3+3 stereo serial ports, GF1–GF3 flags settable *by instructions*, and a
COND field testing RQ1–RQ3.

**INFERRED:** the extra 12 bits, if the shape carried over, must pay for: 8-bit RAM
addresses instead of 4-bit DP-low modifies (+4), a pointer selector over six pointers
(+3), shifter control (+3–4), and loop/flag control. That is the budget the candidate
layouts below were built to.

---

## 2. Candidate layouts, scored (MEASURED)

Score = Σ over the *other* 36−w bits of `H(bit) − H(bit | field)`: how much a field
explains its neighbours. Three borrowed layouts vs our published one:

| layout | idea |
|---|---|
| `L7725x1` | the 7725 word verbatim in the low 24 bits, top 12 unexplained |
| `L7725x15` | every field scaled ×1.5 (24→36) |
| `LWIDE` | the 7725 *shape* with addresses widened to 8 bits, `src`/`dst` kept at 4 |
| `LOURS` | our published `hi12.class4.addr8.lo12` |

```
  L7725x1   type[35:34] 4/4    score 2.029     psel[23:22] 3/4    score 1.025
            alu[21:18] 11/16   score 3.858     src[7:4]  12/16    score 3.507
            dst[3:0]   15/16   score 4.998
  L7725x15  type[35:33] 7/8    score 2.835     alu[29:24] 19/64   score 2.268
            src[11:6]  18/64   score 4.142     dst[5:0]   22/64   score 4.497
  LWIDE     class[23:20] 9/16  score 3.289     addr[19:12] 122/256 score 4.618
            ptr[11:8]  10/16   score 4.137     src[7:4]   12/16   score 3.507
            dst[3:0]   15/16   score 4.998
  LOURS     hi12  54/4096      score 5.467     lo12  57/4096      score 4.804
```

Exhaustive best window per width, for calibration:

```
  width 2: [20:19] 3.233   width 3: [3:1] 4.085    width 4: [3:0] 4.998
  width 5: [6:2] 5.984     width 6: [7:2] 7.130    width 8: [9:2] 7.096
```

**MEASURED:** `[3:0]` is the best-scoring 4-bit window in the whole word (4.998) and
`[7:2]`/`[6:2]` the best 6/5-bit windows. So **the bottom of the word is genuinely where
the densest structure is**, which is the one place the 7725 analogy points correctly.
But note `[6:2]` and `[7:2]` beat `[7:4]`+`[3:0]` — the strong window is *offset by two
bits* from a nibble pair. That is the first hint that the low bits are **not** carved as
`src(4)|dst(4)`.

---

## 3. TEST (a) — src/dst nibbles at the bottom: **FAILS**

**Prediction stated first:** if `[7:4]`=src and `[3:0]`=dst in the 7725 sense, then the
measured **P-consumer split** must be explained by one of them (in the 7725, whether a
word consumes the product is decided by `psel` selecting `m`/`n`, and the move field is
the other route by which P reaches a register).

Measured over the 1546 class-2 words that have a predecessor, baseline
`P(prev is class A) = 0.309`, trivial purity floor `max(base,1−base) = 0.691`:

```
  src[7:4]        7 vals   purity 0.724     (+0.033 over floor)
  dst[3:0]       12 vals   purity 0.691     (EXACTLY the floor: zero information)
  psel[23:22]     1 val    purity 0.691     (the field is constant inside class 2)
  psel[33:32]     3 vals   purity 0.691     (floor)
  alu[21:18]      4 vals   purity 0.691     (floor)
  lo12 low byte  24 vals   purity 0.770
  lo12 hi nibble  6 vals   purity 0.708
  --- best field of any width <= 6 in the entire word:
  [33:28]        14 vals   purity 0.829     13.1% of words in decisive groups
  [31:26]        12 vals   purity 0.782
  [ 7: 2]        20 vals   purity 0.769
```

**MEASURED, and it is decisive: `dst[3:0]` carries literally zero information about
P-consumption, and neither 7725 `psel` position carries any either.** The best predictor
in the whole word is `[33:28]` — inside `hi12`, exactly where our existing notes already
place the operation. `src[7:4]` beats the floor by 0.033, which given 7 values is not
worth a claim.

**Secondary control, and it also fails.** If `lo12`'s low byte were `src|dst` and the
high nibble an independent field, the high nibble could not be a near-function of the
low byte. Measured: **of 42 distinct low bytes, only 13 map to more than one high
nibble** (e.g. `00 → {0,2,7}`, `21 → {0,9}`, `CE → {1,6}`). 29 of 42 are single-valued.
That is the opposite of independence and reproduces the published observation.

> **VERDICT: analogy (a) FAILS.** The bottom byte of the 6383 word is not a 7725-style
> `src|dst` pair. It is a densely-coupled 6-bit-ish encoding centred on `[7:2]`, and the
> P-consumption decision is made in `hi12`, at the top.

**A second, independent falsification of the same analogy, PROVEN BY CONSTRUCTION.** The
firmware builds `801.0.NN.821` byte by byte as *load pointer with 8-bit immediate NN*.
The immediate sits at **`[19:12]`, the middle of the word**. In the 7725's LD type the
immediate occupies the *top* 16 bits and the destination the bottom nibble. The one
instruction on this chip whose encoding we know for certain has its immediate in the
wrong place for a 7725 descendant.

---

## 4. TEST (b) — an ALU-op field inside class 2: **PARTIAL, and it is not where the
7725 puts it**

**Prediction:** a real 3–5 bit ALU-op field shows up as a **local peak** in partition
score, not merely as a high number (wide/high-entropy windows always score high).

Over the 1550 class-2 words (429 distinct), local peaks:

```
  width 3:  [3:1] 4.448*   [10:8] 4.218*   [7:5] 2.406*   [16:14] 2.771*
  width 4:  [11:8] 4.218*  [13:10] 3.256*  [31:28] 2.583*  [21:18] 2.383*
  width 5:  [6:2] 5.606*   [12:8] 4.950*   [32:28] 3.230*  [16:12] 3.213*
```

**MEASURED:** there are exactly **two** strong, well-isolated peaks in the low half —
**`[6:2]` (14 values, 5.606)** and **`[11:8]` / `[12:8]` (6 and 11 values, 4.218/4.950)**
— separated by a scoring trough at `[9:5]`(1.936) and `[11:9]`(1.642).

**INFERRED:** class 2 *does* decompose, but as **`lo12 = [11:8] · [7:2] · [1:0]`**, not
as the nibble triple round one tried. Two adjacent small fields with a 2-bit remainder
at the very bottom. This is a genuine improvement over round one's negative — round one
reported "class 2 does not decompose" at nibble boundaries, and the boundary is indeed
not at a nibble.

**But it is not the 7725 layout.** In the 7725 the ALU op is at `[19:16]`, immediately
under the type/psel; here the strong fields are at the *bottom*, and the corresponding
window `[21:18]` scores 2.383 with only 4 values inside class 2 — mid-table, and it is
at the purity floor (0.691) for the P-consumer test in §3.

> **VERDICT: analogy (b) FAILS as a position claim, but the *method* pays off.** New,
> defensible sub-boundary inside `lo12`: **[11:8] and [7:2]**. INFERRED, moderate.

---

## 5. TEST (c) — instruction type in the top bits: **FAILS as stated; class4 behaves
like a type, in the middle of the word**

**Prediction:** if `class4[23:20]` is a 7725-style TYPE, the other fields' *meaning*
should change with it, visible as a disjoint vocabulary — not merely a shifted
distribution.

```
  class  n     H(hi12) H(addr8) H(lo12)  hi12 values shared with class 2
    2   1550    3.31    3.97     3.55     27/27
    A    822    3.07    3.49     3.12     17/24
    1    322    1.66    2.10     3.45      1/13     <-- essentially DISJOINT
    0    101    1.64    0.00     1.66      1/7
    6     53    0.00    1.58     0.56      1/1
    8     42    0.37    0.00     0.81      0/2
```

**MEASURED: class 1 shares exactly ONE of its 13 `hi12` values with class 2, and class 8
shares none of its 2.** Classes 2 and A share 17 of 24 — consistent with the established
"they differ only in bit 23". So `class4` *does* re-purpose `hi12`: it passes the type
test, at `[23:20]`.

Splitting `class4` into a 7725-ish type+select pair does **not** work:

```
  class4[23:22]  {0:2003, 1:107, 2:864}   score 1.025
  class4[21:20]  {0:196, 1:323, 2:2425, 3:30}   score 1.890
```

The *lower* half scores nearly twice the upper half — the reverse of the required
type-above-select ordering. And the true top bits are unremarkable:

```
  [35:34] {0:2528, 1:38, 2:351, 3:57}   score 2.029
  [35:33] score 2.835      [35:32] score 3.205
```

vs `class4[23:20]` at 3.289 with fewer values.

> **VERDICT: analogy (c) FAILS.** The 6383 has a type field with real 7725-like
> behaviour (it re-purposes the fields around it), but it is at **[23:20]**, not at the
> top, and it does not decompose into type+select. This also explains the published
> non-universality of `class4`: a type field is only a type field *for the types that
> use it*; the host-poke region is a different upload path entirely.
>
> **Family reading (INFERRED):** "a small type field that re-purposes the rest of the
> word" is a horizontal-microcode idiom, not a 7725 fingerprint. Every horizontal
> machine has one. Its presence is not evidence of descent.

---

## 6. TEST (d) ★ — BRANCHES

### 6.1 The scan

Every contiguous field of width 7–12, at every offset, with left-shifts of 0/1/2 (the
7725's next address sits at `[12:2]`, i.e. shifted), tested against **each program's own
I-RAM extent** `[load, load+len)`. 2974 words, 38 images.

Best raw hit rates, against a chance baseline of `mean_len / 2^(w+shift)`:

```
  field        in-range     rate   chance  ratio  images
  [15: 4]<<2   454/2974    0.153    0.005  31.96   38/38
  [16: 5]<<2   423/2974    0.142    0.005  29.78   35/38
  [31:20]<<2   371/2974    0.125    0.005  26.12   30/38
  [18: 7]<<2   303/2974    0.102    0.005  21.33   34/38
```

These ratios look impressive and are **artefacts**. `addr8` at `[19:12]` is known to be
an operand address concentrated in `0x00..0x10` / `0xF0..0xFF`; any window overlapping
it inherits a clumped distribution, and a clumped distribution trivially over-hits a
50-word window. `[15:4]<<2` overlaps `addr8` in four bits. No field passes the rarity
filter *and* looks like a target rather than an operand.

### 6.2 The relocation discriminator — the only test with real power, and it is NEGATIVE

One image loads at I-RAM 200 (length 133); the other 37 load at 84. An **absolute**
next-address field must carry values in 200..332 in that image and in 84..216 in the
others. Best fields:

```
  field       P(in own extent | unit1)  P(in unit0 extent | unit1)  P(own | unit0)
  [21:13]<<0            0.647                     0.248                 0.099
  [22:15]<<2            0.647                     0.248                 0.099
  [ 9: 1]<<0            0.376                     0.000                 0.039
  [34:25]<<2            0.226                     0.000                 0.040
```

**MEASURED and fatal:** the best field puts **64.7 % of the unit-1 program's words**
inside its own extent. A branch target field that fires on two words in three is not a
branch target field — it is a wide window over clumped operand bits. And in the unit-0
programs the same field fires on only 9.9 %, so it is not even consistent. `n = 1`
unit-1 image caps the power of this test regardless.

### 6.3 ★ THE POSITIVE RESULT: the bodies are UNROLLED

Masking out `addr8` and looking for the longest run of words that repeat at a fixed
period differing in *nothing but `addr8`*:

```
  algo16 (reverb, 133 words, unit 1) : 32 words repeating at period 8   -> 5 iterations
  algo39 (105 words)                 : 36 words repeating at period 9   -> 5 iterations
  algo05 (phaser, 106 words)         : 25 words repeating at period 3   -> 9 sections
  algo68 (110 words)                 : 10 words at period 3
```

**MEASURED.** This is independently corroborated by the published all-pass work: the
phaser's nine sections are written out literally with `c + s == 0xFF` walking two
cursors, and the coefficient cursor advances +1 per class-A word with the reverb's
section starts at 0,6,12,18,24 — an *implicit* cursor is only usable in straight-line
code, because a loop would have to reset it.

> **INFERRED, strong: the per-sample effect bodies contain NO control flow whatsoever.**
> A machine with the LC1–LC3 loop counters the block diagram shows, and only 384 words
> of I-RAM, that nevertheless unrolls a 5-iteration 8-word reverb block into 40 words,
> is telling us its loop machinery is not available (or not worth it) inside a
> per-sample body. The branch search has been failing because there is nothing there.

### 6.4 The header and stub — still the only place left

The 60-word header @0 and 23-word stub @60 were scanned the same way, looking for fields
that yield an in-extent value in a *rare* number of words (≤ len/6):

```
  block @0  (60 words):  [17: 6]<<2  10 words, values {0,28,32,44}
                         [21:15]<<2   9 words, values {0,4,16,40,48,52,56}
                         [24:17]<<2   9 words, values {28,32,36,44,48,56}
  block @60 (23 words):  [ 6: 0]<<1   3 words, values {66,68,74}
                         [11: 5]<<0   3 words, value  {65}
                         [12: 6]<<2   3 words, value  {64}
```

**Not a claim.** With 60 words and hundreds of (field, shift) combinations tried, three
in-extent hits is well inside what chance delivers; the tool prints these as leads, not
findings. The `@60` hits are mildly interesting only because the stub is 23 words long
and 64/65/66/68/74 all land in its first half — but `<<1`/`<<2` shifts on a 7-bit field
make small values cheap. **NOT ESTABLISHED.**

> **BRANCH-SEARCH VERDICT: still no branch, now with a reason.** The scan is negative in
> the bodies (and the bodies are proved not to need one), and underpowered in the 83
> scaffolding words. **The next real move is not a wider scan — it is a runtime capture
> of the PC**, or the datasheet.

---

## 7. TEST (e) — the COND field: **untestable on this corpus**

A COND field that is almost always "always" should be a small field dominated by one
value, with the tail *richer in the header* than in the straight-line bodies. Fields
≥ 80 % dominated in the bodies, ranked by (header tail rate)/(body tail rate):

```
  field     body top-val share   header top-val share   tail ratio
  [35:34]         0.850                 0.581              2.80
  [21:20]         0.815                 0.581              2.27
  [22:21]         0.808                 0.594              2.11
  [30:29]         0.905                 0.884              1.22
  [27:26]         0.857                 0.852              1.04
```

`[21:20]` and `[22:21]` are just the halves of `class4`, whose header/body distribution
difference is already published (class 2 is 51 % of bodies but 27 % of the header). They
are re-detections, not a COND field. `[35:34]` is the top pair, with a 2.8× tail ratio —
the only candidate that is *not* an obvious re-detection, and 155 header words is far
too few to defend it.

> **VERDICT: (e) UNTESTABLE.** The COND field certainly exists (the pin table says so),
> but a corpus of straight-line code, where every instruction executes unconditionally,
> is precisely the corpus in which the condition field is pinned to its "always" value
> and therefore invisible. This is not a failure of the search; it is a structural limit
> of the data.

---

## 8. Verdict on the descendant hypothesis

| analogy | verdict |
|---|---|
| a small instruction TYPE field re-purposing the rest of the word | **HOLDS** — `class4[23:20]`, class-1 `hi12` disjoint from class-2 (1/13 shared). But this is generic horizontal-microcode design, **not a 7725 fingerprint**. |
| TYPE at the very top of the word | **FAILS** — `[35:34]` scores 2.029 and `[35:32]` 3.205 vs `class4[23:20]` 3.289 with fewer values; `class4` does not split into type+select (the *lower* half scores higher). |
| `src[7:4]` / `dst[3:0]` at the bottom | **FAILS** — `dst[3:0]` has *exactly zero* information about the P-consumer split; the best low window is `[7:2]`, offset from the nibble grid; `lo12`'s high nibble is a near-function of its low byte (29/42 single-valued). |
| `psel` selecting the multiplier product | **FAILS** — both 7725-position candidates sit at the purity floor (0.691); the P-consumption decision lives in `hi12[33:28]` (0.829). |
| ALU op as a 4-bit field under the type | **FAILS as position** — `[21:18]` scores 2.383 and is at the P-consumer purity floor; the real peaks are `[6:2]` and `[11:8]`. |
| immediates in their own type, at the top of the word | **FAILS, PROVEN BY CONSTRUCTION** — the firmware's `801.0.NN.821` puts the 8-bit immediate at `[19:12]`, mid-word. |
| JP with a wide next-address field | **NOT FOUND**, and the bodies are proved unrolled (§6.3). |
| COND field | **UNTESTABLE** on straight-line code. |

**CONCLUSION (INFERRED, and I would defend it): the uPD6383GF is not usefully modelled
as a widened uPD7725.** Six of eight borrowed structures fail against fixed points we
already hold, and the two that "hold" hold for reasons that would hold for *any*
horizontal microcoded DSP. The 6383 is a later, much larger machine (44-bit ALU, two
shifters, six pointers, external DRAM controller) and its word is carved on its own
terms: **the operation lives in `hi12` at the top, the type at `[23:20]`, the operand
address at `[19:12]`, and a two-field control group at `[11:8]`+`[7:2]` at the bottom** —
which is close to the *reverse* of the 7725's layout.

**What this redirects.** Stop trying to borrow an ISA. The two things that would actually
move the work are (1) the datasheet, and (2) a runtime capture that shows the chip's
*behaviour* rather than its code — a PC trace, or a single-stepped upload. Neither is
statistical.

---

## 9. Revised field map, with confidences

```
   35                    24 23  20 19        12 11    8 7      2 1  0
  +------------------------+------+------------+-------+--------+----+
  |          hi12          |class4|   addr8    |  op4  |  op6   | ?? |
  |   operation / P-source |=type |  operand   |       |        |    |
  +------------------------+------+------------+-------+--------+----+
```

| field | reading | confidence | what would confirm it |
|---|---|---|---|
| `[19:12]` `addr8` | operand address / 8-bit immediate | **HIGH** (published minimal pair ±115; PROVEN BY CONSTRUCTION as an immediate in the pointer-load) | a runtime RAM-access trace |
| `[23:20]` `class4` | instruction TYPE — re-purposes `hi12` | **MEDIUM-HIGH** (new: class-1 `hi12` shares 1/13 values with class 2; class 8 shares 0/2) | a second type whose `hi12` vocabulary is disjoint again |
| `[35:24]` `hi12` | the operation, incl. the multiplier-product source | **MEDIUM** (new: `[33:28]` is the best P-consumer predictor in the word, purity 0.829 vs floor 0.691) | decode any one instruction |
| `[11:8]` | a small control field | **LOW-MEDIUM** (new: isolated local peak, 4.218/4.950, 6 values, trough on both sides) | a minimal pair varying only these 4 bits |
| `[7:2]` | a ~14-value control field, the densest window in the word | **LOW-MEDIUM** (new: best width-5/6 window anywhere, 5.606/7.130; NOT nibble-aligned) | ditto |
| `[1:0]` | remainder — possibly padding or a 2-bit selector | **SPECULATIVE** | — |
| a branch/next-address field | **absent from the effect bodies** | **MEDIUM** as a negative (unrolling, §6.3) | a PC trace, or the header decoded |
| a COND field | exists (pins) but is invisible here | **untestable** | conditional code, i.e. the header |

The one strictly *new* structural claim in this file is the `lo12` sub-boundary at
`[11:8] | [7:2] | [1:0]`, and it is INFERRED at moderate confidence from a partition-score
local-peak argument only. **It is not a decoded field and must not be cited as one.**

---

## 10. Falsified / not established here

* **"The 6383 is a widened 7725."** Rejected, §8, six independent failures.
* **"`src`/`dst` nibbles sit at the bottom."** Rejected: `dst[3:0]` purity = the floor
  exactly (0.691 vs 0.691).
* **"The immediate is at the top like the 7725's LD."** Rejected by construction.
* **"The high raw branch-hit rates ([15:4]<<2, ratio 32×) mean something."** Rejected as
  an `addr8` clumping artefact — the field overlaps `addr8` by four bits.
* **"The `@60` stub contains a jump to 64/65/66."** NOT ESTABLISHED — three hits out of
  hundreds of tried (field, shift) pairs on 23 words is chance.
* **NOT claimed:** that `[7:2]` is "the ALU op". It is the densest window; naming it
  would be exactly the seductive retrofit this investigation was warned against.
