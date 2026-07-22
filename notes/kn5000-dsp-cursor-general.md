# NEC uPD6383GF — does the coefficient cursor generalise?  The reverb, decoded

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_cursorgen.py` (imports `_extract`, `_class2`, `_biquad`,
`_biquadmap`, `_params`; **none of them is edited**).

**Append-only successor material.** This note does not edit
`notes/kn5000-dsp-biquad-map.md`, `-biquad-coeffs.md`, `-biquad.md`, `-reverb.md`,
`-class2*.md`, `-coefficients.md`, `-parameters.md`, `-encoding.md`, `-header.md`
or `-INDEX.md`. Corrections to them are collected in §7.

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or
**SPECULATIVE**. §8 lists what is falsified or not established.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_cursorgen.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom
```
Sections: `bank hostxref compress reverb ladders state`.

---

## Headline

1. **★★★ The cursor model generalises, and a completely new measurement proves
   it.** The coefficient bank the program loader uploads contains **exactly one
   word per class-A word, plus one spare**: `bank == classA + 1` in **26 of the
   38 distinct images**, and every exception is separately accounted for (§1).
   The loader's word count and the microprogram's class-A count are produced by
   different tools that know nothing of each other. **MEASURED.**
2. **★★★ 192 of 197 coefficient-space `T1` addresses fall inside the cursor's
   reachable range** `[base, base + classA + deficit)`, and the **five that do
   not are all one group in one image** — algo 39's `op 0x70` second group,
   which §5 identifies as **state-space** addresses, not coefficients. So the
   corrected score is **197/197**. The deficit used in the bound is measured
   from the *bank size*; the addresses come from the *host's parameter ROM*.
   Two unrelated instruments agree per image (§2). **MEASURED.**
3. **★★★ THE REVERB IS DECODED.** Nine motif repetitions, one class-A word
   each; the cursor hands them bank slots `0x98 0x99 0x9A 0x9B 0x9C |
   0xA1 0xA2 0xA3 0xA4`. For `ROOM REVERB 1` those are
   **0.750 0.630 0.520 0.500 0.400 | 0.630 0.620 0.520 0.400** — two strictly
   **descending diffuser ladders**, exactly the prediction. It holds in **9 of
   the 12 presets** (§3). Every remaining class-A word lands on the bank entry
   the reverb note had already labelled from the coefficient side alone: input
   scaling triple, two damping triples, the two mirrored output tails.
4. **★★ The 9-vs-10 off-by-one is resolved, and overshoots.** The three
   "separators" at words 11, 59 and 101 are **not separators**: each is a
   full external-DRAM bracket (`880.1.60.2DA … 880.1.20.64B`) containing one
   class-A word, gain **0.500** in all three. The program has **12 balanced
   DRAM brackets**, not 9 (§3.2). **MEASURED.**
5. **★★ The compressor's `+4` is confirmed by a second, independent instrument
   and bounded to 11 candidate words.** The bank-size deficit is `+8` in **all
   four** compressor-bearing images (36, 75, 96, 97) = **4 per stage × 2
   stages**, reproducing the `T1`-derived `+4` exactly (§4). The consumers are
   located to the eleven-word tail common to every compressor stage. The
   *specific* instruction is still **NOT IDENTIFIED**.
6. **★★ TASK C: the "two cells in each space" lead is FALSIFIED, and the four
   cells are measured directly.** The parameter stream's op-0 records clear the
   state region through the `000.1.NN.000` pointer — **the second space, not the
   `801.0` coefficient space** — so all four cells live in **one** space (§5).
   The number cleared is **exactly 4 per biquad section** in six images
   (`PEQ` 10 sections → 41 cells; `PEQ+OVERDR+DELAY` 4 → 16; `OVERDRIVE`,
   `EXCITER`, `PEQ+S.DELAY`, `PEQ+DIST+DELAY` 2 → 8; `PEQ+COMPRESSOR` and
   `PEQ+COMPR+DIST` → 4 + 4 at bases `0x50` and `0x54`). **MEASURED.**
7. **★★ The `T1 op 0x70` second group is explained** — the biquad-map note's
   open question. `0x64 0x68 0x6C 0x70 0x74`, stride **4**, is the **per-band
   state base of channel 1**: `0x50 + 20 + 4·band`, where `0x50` is the state
   region the same algorithm's op-0 stream clears and `20 = 5 bands × 4 cells`
   is precisely the "+20 channel delta" the biquad note measured (§5.2).
8. **★ Unit 1 has a coefficient-space base of `0x80`** (§1.2). Reverb programs
   load at I-RAM 200 and their banks at `0x90`; the effect-level opcode `0x63`
   writes `0x06` in every unit-0 image and `0x86` in the reverb. **MEASURED.**

---

## 1. TASK A — the bank-size test

### 1.1 The prediction, stated before it was run

> If the cursor advances +1 per class-A word and never repeats within a program,
> then the coefficient bank the loader uploads must hold **exactly as many words
> as the program has class-A words**. Nothing links the two: the microcode is a
> stream of 36-bit words in one ROM table, the bank is a stream of 24-bit words
> in another.

### 1.2 The result (MEASURED, tool section `bank`)

```
  bank == classA + 1  in 26 of 38 images:
      CHORUS  MODULATED CHORUS  ENHANCER  FLANGER  PHASER  ENSEMBLE
      SINGLE DELAY  DISTORTION  OVERDRIVE  FUZZ  EXCITER  AUTO PAN  VIBRATO
      RING MODULATOR  MIX UP  S.DELAY+CHORUS  S.DELAY+S.DELAY  S.DELAY+FLANGER
      S.DELAY+VIBRATO  S.DELAY+PHASER  PEQ+CHORUS  PEQ+S.DELAY  PEQ+FLANGER
      PEQ+VIBRATO  PEQ+DIST+DELAY  PEQ+OVERDR+DELAY

  deficit = bank - classA - 1, per exception:
      PARAMETRIC EQ    -30   channels SHARE (60 class-A, 30 distinct + 1 spare)
      MULTI TAP DELAY   -4   the cursor OVERRUNS the bank -- see below
      NO OPERATION      +2
      AUTO WAH          +1     AUTO WAH+S.DELAY  +1
      ROOM REVERB 1     +3
      GATED REVERB      +4     ROCK ROTARY       +4
      COMPRESSOR        +8     PEQ+COMPRESSOR    +8
      PEQ+COMPR+DIST    +8     PEQ+COMPR+OVERDR  +8
```

The `+1` is the spare: algo 39 loads its 30 band words at `0x00` and then
**one further word separately at `0x1E`** with its own pointer load
(`801.0.1E.821`), which is how the biquad-map note found the region in the first
place. That word is never reached by the cursor.

* **`PARAMETRIC EQ` = −30 is the model working, not failing.** The rewind
  `801.0.00.021` at word 58 sends the cursor back to 0, so channel 1 re-reads
  channel 0's 30 words. `60 − 30 = 30`. **Consistent with the rewind, MEASURED.**
* **`MULTI TAP DELAY` is the one genuine failure**: 18 class-A words, only 15
  bank words, and **no `801` rewind anywhere in its body**. Either it contains a
  rewind in an encoding not yet recognised, or three of its class-A words do not
  consume. **NOT EXPLAINED** (§8).
* The `+8` group is §4.

**Unit 1's base (MEASURED).** All unit-0 images (I-RAM 84) load their banks at
`0x00`. `ROOM REVERB 1` loads at I-RAM 200 and its bank at `0x90`
(`801.0.90.821`, then `801.0.AE.821`). Independently, the effect-level opcode
`0x63` writes `0x06` in every unit-0 image and `0x86` in the reverb: a **`+0x80`
displacement**. **INFERRED:** the two resident effect units are given the two
halves of the 256-word coefficient RAM, unit 0 low and unit 1 from `0x80`.

## 2. TASK A — every host address against the reachable range

Tool section `hostxref`. Coefficient-space opcodes are those whose writer is
`LABEL_0387E6` (descriptor field `+0`, the `801.0.NN.821` space; parameters note
§2), **less** `0x74`/`0x21` (identical in every image — global level/balance) and
`0x67`/`0x6A`, whose addresses are always `≥ 0x26` and `0x56..0x5F` and which
therefore address the external-DRAM delay registers, not coefficients.

```
   192 / 197 coefficient-space T1 addresses lie inside [base, base+classA+deficit)
   the 5 exceptions are ALL algo 39's op 0x70 second group (0x64 68 6C 70 74)
   -> state space, see sect. 5.2.   Corrected: 197/197.
```

Per image the bound is tight in exactly the informative way: the addresses that
sit **beyond `classA` but inside the deficit** are

```
   GATED REVERB      2   (0x16, 0x17 vs classA 22, deficit +4)
   ROOM REVERB 1     2   (0xB1, 0xB2 vs 0x90+33, deficit +3)
   COMPRESSOR        1   (0x0D  vs classA 10, deficit +8)
   AUTO WAH+S.DELAY  1   (0x15  vs classA 21, deficit +1)
   PEQ+COMPRESSOR    1   (0x19  vs classA 22, deficit +8)
   PEQ+COMPR+DIST    2   (0x22, 0x24 vs classA 30, deficit +8)
   PEQ+COMPR+OVERDR  2   (0x25, 0x2B vs classA 36, deficit +8)
```

**Every image whose host map overruns the class-A count has a positive bank
deficit large enough to cover the overrun, and no image with a zero deficit
overruns.** The deficit is measured from the loader; the overrun from the host
parameter ROM. **MEASURED**, and it is the sharpest corroboration in this note
that the missing consumers are real instructions, not a bookkeeping error.

## 3. TASK B — ★★★ THE REVERB

### 3.1 The prediction, stated before it was run (per the brief)

> The motif's 8 words have no varying fields, so nothing inside a stage names its
> operands. If the cursor is implicit, the operands are determined by **position**.
> With one class-A word per stage the cursor must advance one coefficient per
> diffuser stage. Stages 1–5 should pick up the 0.63→0.50 ladder and stages 6–9
> the 0.73→0.50 ladder that the reverb note derived from the coefficient bank
> alone. If they do not line up, the cursor is per-family, not global.

### 3.2 The result (MEASURED, tool section `reverb`)

Motif at words 19 27 35 43 51 | 69 77 85 93; class-A word at `+5`; bank 37 words
at `0x90..0xB4`.

```
  stage  motif@  classA@  coef   ROOM REVERB 1   CONCERT REVERB 1   chain
    1      19      24     0x98     +0.750           +0.750            0
    2      27      32     0x99     +0.630           +0.630            0
    3      35      40     0x9A     +0.520           +0.620            0
    4      43      48     0x9B     +0.500           +0.600            0
    5      51      56     0x9C     +0.400           +0.500            0
    6      69      74     0xA1     +0.630           +0.730            1
    7      77      82     0xA2     +0.620           +0.720            1
    8      85      90     0xA3     +0.520           +0.700            1
    9      93      98     0xA4     +0.400           +0.600            1
```

**PREDICTION MET.** Both chains are strictly descending gain ladders, one gain
per stage, with the gains assigned by nothing but cursor position. For
`CONCERT REVERB 1` chain 1 is `0.730 0.720 0.700 0.600` — the head of the reverb
note's "LADDER B (0.73→0.50)" — and chain 0 is `0.750 0.630 0.620 0.600 0.500`,
i.e. the note's "LADDER A" **preceded by the 0.750 at bank index 8**. The
prediction is confirmed with a **one-slot correction to the ladder boundaries**:
the stage gains are bank `[8..12]` and `[17..20]`, not `[9..13]` and `[17..21]`.

The whole program's class-A walk lands on the reverb note's independently
derived bank reading, entry for entry:

```
   [  2][  3][  4]  0x90 0x91 0x92  +0.250 +0.500 +0.500   input scaling triple
   [  7][  8][  9]  0x93 0x94 0x95  +0.384 +0.198 -0.206   damping triple #1
   [ 12]            0x96            +0.500               DRAM stage (see below)
   [ 17]            0x97            +0.200               op 0x75 writes here
   [ 24..56]        0x98..0x9C      the chain-0 ladder    5 motif stages
   [ 60]            0x9D            +0.500               DRAM stage
   [ 65][ 66][ 67]  0x9E 0x9F 0xA0  +0.438 +0.363 -0.415   damping triple #2   <- op 0x76
   [ 74..98]        0xA1..0xA4      the chain-1 ladder    4 motif stages
   [102]            0xA5            +0.500               DRAM stage
   [107][108][109]  0xA6 0xA7 0xA8  +0.438 +0.363 -0.415   damping triple #3   <- op 0x76
   [115..118]       0xA9..0xAC      +0.358 +0.500 +0.493 +0.390   LEFT output tail
   [126..129]       0xAD..0xB0      +0.200 +0.200 +0.450 +0.500   RIGHT output tail
```

`0xB1..0xB4` are loaded but never reached (the `+3` deficit).

**The 9-vs-10 off-by-one, resolved (MEASURED).** The reverb note called words
11–15, 59–63 and 101–105 "separators". They are not: each is a complete
external-DRAM bracket `880.1.60.2DA … 880.1.20.64B` with exactly one class-A word
inside, consuming coefficients `0x96`, `0x9D`, `0xA5` — **+0.500 in all three**.
Counting `880.1.60.*` opens and `880.1.20.*` closes in the body gives **12
balanced brackets** (words 11 19 27 35 43 51 59 69 77 85 93 101), i.e. **12 delay
taps**: 9 motif stages plus 3 single-multiply stages. That is more than the 10
recirculating buffers the address chains gave, so the shortfall the reverb note
flagged is gone, and the arithmetic now runs the other way — the code has room
for more taps than the tiling identified. **INFERRED:** the three extra brackets
are the pre-delay write and the two chain heads.

### 3.3 The host map, against the stage slots (MEASURED)

```
   op 0x76 -> 0x9E   HITS  == the head of damping triple #2   (word 65)
   op 0x76 -> 0xA6   HITS  == the head of damping triple #3   (word 107)
   op 0x75 -> 0x97   HITS  == word 17
   op 0x66 -> 0xA9 0xAA 0xAB 0xAC   HITS   == the LEFT output tail, exactly
   op 0x66 -> 0xAF 0xB0             HITS   == the last two of the RIGHT tail
   op 0x66 -> 0xB1 0xB2             beyond the cursor's last slot
```

The left output tail is reproduced **exactly**: four consecutive host addresses
on four consecutive class-A words. The right tail is **displaced by +2**: the
cursor puts it at `0xAD..0xB0`, the host writes `0xAF..0xB2`. This is a small
instance of the same species as the compressor's `+4` — two non-class-A
coefficient consumers between word 118 and word 126. The candidate set is tight:
the words between them are `202.2.08.1CD`, `090.2.FB.40E`, `212.2.05.000`
(words 119–121, present only after the *left* tail), the `C40.1.80.000` pair
(122/123), `000.2.FB.407` and `880.1.20.2D5`. The `C40` pair can be **excluded**
by symmetry — the identical pair at 111/112 precedes the left tail and demonstrably
consumes nothing, since `0xA9` lands on word 115. So the two consumers are among
`{202.2.08.1CD, 090.2.FB.40E, 212.2.05.000}`. **MEASURED bound, not identified.**

### 3.4 Across the twelve presets (MEASURED, tool section `ladders`)

All twelve share the one 133-word image, so the stage→slot map is fixed; only
the bank changes.

```
   descending in BOTH chains: ROOM 1/2, PLATE 1, CONCERT 1/2, DARK 1/2, WAVE 1/2   (9/12)
   not descending:            PLATE REVERB 2, BRIGHT REVERB 1, BRIGHT REVERB 2
```

`PLATE REVERB 2` and `BRIGHT REVERB 1` carry the **same multiset** of gains as
`ROOM REVERB 1` ({0.75, 0.63, 0.52, 0.50, 0.40}) in a permuted order — a
scrambled diffuser schedule is a legitimate design choice, so this is not
evidence against the mapping. `BRIGHT REVERB 2` is the only preset with a
**38-word** bank; its stage gains read one slot late (`0.200 0.750 0.630 …`),
consistent with one extra word early in its bank. Reported, not explained.

## 4. TASK A — the compressor's `+4`

**The `+4` is reproduced by an instrument that never looks at `T1`.** Bank size
minus class-A count minus one is `+8` in all four compressor images, and each has
**two** compressor stages:

```
   COMPRESSOR         classA 10  bank 19   +8   = 4 per stage x 2
   PEQ+COMPRESSOR     classA 22  bank 31   +8
   PEQ+COMPR+DIST     classA 30  bank 39   +8
   PEQ+COMPR+OVERDR   classA 36  bank 45   +8
```

The chain arithmetic closes with 9 slots per compressor stage. In
`PEQ+COMPRESSOR` (algo 75): PEQ band at 0–5, compressor at 6–14 with
`op 0x72 -> 0x0A = 6+4` (standalone `COMPRESSOR` has `op 0x72 -> 0x04 = 0+4`,
the same in-stage offset), and the second PEQ section at `6+9 = 15 = 0x0F`,
which is exactly what the host writes. **The `+4` is therefore not an error in
the cursor model; it is four real coefficient fetches by non-class-A
instructions inside the compressor's gain computer.**

Of the brief's three candidates, "a coefficient block that starts at a non-zero
base" is **excluded** (the first PEQ section still lands on `0x00`, and the
offset appears *between* stages, not before the first one), and "a different
rewind" is **excluded** (no `801` word anywhere in these bodies, and a rewind
would give a *negative* deficit). The surviving candidate is the brief's first:
**instructions that consume coefficient words without being class A.**

Localisation (tool section `compress`): the eleven `(hi12, class, lo12)`
families present in every compressor stage and in **no** zero-deficit image:

```
   000.2.40E   012.2.1C0   026.2.000   028.2.000   0A2.2.000   102.2.000
   212.2.000   428.1.000   880.1.407   C40.1.451   C40.2.000
```

Four of these eleven consume one word each. `C40` is the already-labelled
envelope-detector family and appears **twice per stage** (`C40.2.C0.000` and
`C40.1.E0.451`); "each `C40` word fetches two coefficients" would give exactly
four, and is the most attractive reading — but it is **FALSIFIED by CHORUS**,
which contains four `C40.2.*` words and has deficit **0**. **NOT IDENTIFIED.**

## 5. TASK C — the four state cells

### 5.1 The lead, tested (MEASURED — and it FAILS)

> **The brief's lead:** the two-latch inference says a class-A word reads one
> operand from C-RAM and one from D-RAM, so the four state cells may be two in
> each space, and the read order that fits no textbook topology may be two
> interleaved streams.

Every algorithm's parameter stream begins with **op-0 records that clear its
state**: a pointer word `000.1.NN.000` followed by *n* writes of zero. That
pointer is the **second** address space — the one writers `LABEL_038539` /
`LABEL_03846C` use with descriptor field `+2` — and it is **not** the
`801.0.NN.821` coefficient space the bank is loaded through. A program clears
its state through **one pointer in one space**.

> **The "two cells in each space" reading is FALSIFIED.** All four cells are in
> the same space. What the two-latch structure buys is the *other* split, the one
> the biquad-map note proposed: a class-A word takes its **coefficient** from the
> implicit cursor in the `801.0` space and its **data operand** from the signed
> `addr8` cursor in the `000.1` space. One operand from each latch, nothing to
> select. **This note therefore CONFIRMS the biquad-map §7 reading and kills its
> stated alternative.**

### 5.2 Four cells per section, counted directly (MEASURED, tool section `state`)

Cleared cells in the `0x50..0x7F` window, against the number of 9-word biquad
sections found in the microcode (d ≤ 3):

```
   PARAMETRIC EQ      10 sections   0x50 x30 + 0x6D x11 = 41   (10 x 4 = 40, +1)
   PEQ+OVERDR+DELAY    4 sections   0x50 x16                   EXACT
   OVERDRIVE           2 sections   0x50 x8                    EXACT
   EXCITER             2 sections   0x50 x8                    EXACT
   PEQ+S.DELAY         2 sections   0x50 x8                    EXACT
   PEQ+DIST+DELAY      2 sections   0x50 x8                    EXACT
   PEQ+COMPRESSOR      2 sections   0x50 x4 + 0x54 x4 = 8      EXACT, and SPLIT
   PEQ+COMPR+DIST      2 sections   0x50 x4 + 0x54 x4 = 8      EXACT, and SPLIT
   PEQ+FLANGER         2 sections   0x50 x12   (8 + 4 for the flanger all-pass)
   PEQ+VIBRATO         2 sections   0x50 x12
   PEQ+CHORUS          2 sections   0x50 x16   (chorus needs its own cells)
```

**Four cells per biquad section is now MEASURED from the host side**, not
inferred from the `addr8` walk. The two `PEQ+COMPR*` images clear them as **two
separate four-word blocks at `0x50` and `0x54`** — one per channel, one section
each — which is the cleanest possible statement of "per-channel and per-band".

**The `T1 op 0x70` second group, explained.** Algo 39 clears `0x50` upward, and
the host's unexplained second group is `0x64 0x68 0x6C 0x70 0x74` — stride **4**,
five entries, one per band, starting at `0x50 + 0x14`. `0x14 = 20 = 5 bands ×
4 cells`. So:

```
   channel 0 band k state base = 0x50 + 4k     (0x50 0x54 0x58 0x5C 0x60)
   channel 1 band k state base = 0x64 + 4k     (0x64 0x68 0x6C 0x70 0x74)  <- op 0x70 group 2
```

and the `+20` channel delta the biquad note measured from the microcode's `addr8`
arithmetic is reproduced exactly by the host's own table. **INFERRED:** because
the two channels *share* coefficients (the rewind), `op 0x70` must still be told
each band's channel-1 state base — the coefficient write is shared, the state
reset is not.

### 5.3 What is still open

The **topology** is not settled. What this note adds is that the search space is
smaller than it was: one space, four cells, per channel per band, cleared to zero
at load. The read/write walk is unchanged
(`S0 S0 S1 S2 S3 | store S3 | S2 | store S1`) and still fits no textbook form.
The **circular-buffer** reading in the brief remains live and is now the more
attractive of the two, since only two of the four cells are written and the
cursor's `+4` per band would rotate the window — but nothing here tests it.
**NOT ESTABLISHED.**

## 6. TASK D — `op 0x76`

Not decoded. Two things were learned in passing and are recorded because they
change what the target *is*:

* **The brief's identification is off by one opcode.** `LABEL_03B646` is the
  handler for **`op 0x77`** (`kn5000_dsp_params.OPCODE_EVAL`), not `0x76`;
  `op 0x76` is `eval_039D98` with writer `LABEL_0387E6`. `op 0x77` occurs in
  exactly one image, `ENSEMBLE` (six entries), which is not a graphic EQ.
* **`op 0x76` is a small-filter designer, not a five-coefficient GEQ writer.**
  In the reverb its two entries `0x9E` and `0xA6` are precisely the heads of the
  two **damping triples** (`+0.438 +0.363 −0.415`, three coefficients, one
  negative) — a one-pole-plus-zero absorbing filter, per channel. **MEASURED.**
  Its entry pairs elsewhere are spaced 3 (`SINGLE DELAY`, `MULTI TAP DELAY`),
  4 (`ENHANCER`) and 7 (`GATED REVERB`) apart, so the block it writes is **not
  a fixed width** and cannot on this evidence confirm or refute the GEQ stride-5
  finding. `GEQ` (algo 79) remains one of the five malformed images.

## 7. Corrections and cross-checks to earlier notes

| earlier claim | source | status here |
|---|---|---|
| the coefficient cursor is `+1` per class-A word, reset by `801.0.00.021` | biquad-map §2 | **GENERALISED**: confirmed by bank size in 26/38 images and by 197/197 host addresses (§1, §2) |
| "the `T1 op 0x70` second group `64 68 6C 70 74` is still unexplained" | biquad-map §10 item 5 | **EXPLAINED**: channel-1 per-band **state** bases, `0x50 + 20 + 4k` (§5.2) |
| the compressor `+4` — "the instruction that consumes those four words is unidentified" | biquad-map §9 | **CORROBORATED by a second instrument** (bank size, `+8` = 4 × 2 stages in all four images) and **bounded to 11 word families**; still not identified (§4) |
| "possibly nothing selects C-RAM vs D-RAM: one operand from each" | biquad-map §7 | **SUPPORTED**: the state region is cleared through the `000.1` pointer, the bank loaded through `801.0` (§5.1) |
| "the four state cells may be two in each space" | this brief's lead | **FALSIFIED** (§5.1) |
| state "+4 per band, channel bases 0x40 and 0x54" | biquad note §3 | **REFINED, MEASURED**: absolute bases are `0x50` (ch 0) and `0x64` (ch 1) for algo 39; the `+20` delta is right, and `PEQ+COMPR*` clears `0x50` and `0x54` for its two single-band channels |
| reverb "LADDER A = bank 9..13, LADDER B = 17..21" | reverb note §3 | **CORRECTED by one slot**: the nine motif stages read bank `8..12` and `17..20` (§3.2) |
| reverb: "5 + 4 motif repetitions vs 10 buffers, off-by-one not resolved" | reverb note §2 | **RESOLVED**: 12 balanced DRAM brackets, 9 motif + 3 single-multiply stages at words 11/59/101, gain 0.500 each (§3.2) |
| reverb words 11–15 / 59–63 / 101–105 = "separators, a cursor reload" | reverb note §1.1 | **SUPERSEDED**: they are delay stages with their own coefficient (§3.2) |
| reverb `102.A.00.64B` = "the gain multiply — ten stages, ten gains" (INFERRED) | reverb note §5 | **CONFIRMED, and the gains are now named**: `0x98..0x9C`, `0xA1..0xA4` (§3.2) |
| "the delay lengths and gains are NOT immediates in the repeated stage" | reverb note §1 | **UPHELD, and explained**: they need not be, because the cursor supplies them by position |
| `op 0x76` = `LABEL_03B646`, the GEQ designer | this brief | **CORRECTED**: `LABEL_03B646` is `op 0x77`; `op 0x76` writes 3-word damping filters in the reverb (§6) |
| "91 valid programs, 38 distinct images" | INDEX | **UPHELD** (38 images enumerated here) |

## 8. Falsified, or explicitly not established

* **Four state cells split two-and-two across the two memories.** **FALSIFIED** (§5.1).
* **"Each `C40` word fetches two coefficients", the neat explanation of the
  compressor `+4`.** **FALSIFIED** by `CHORUS` (four `C40.2.*` words, deficit 0) (§4).
* **Which four instructions consume the compressor's extra coefficients.**
  Bounded to eleven families, **NOT IDENTIFIED**.
* **`MULTI TAP DELAY`'s −4** — 18 class-A words, a 15-word bank, no rewind found.
  The one image where the cursor demonstrably overruns its bank. **NOT EXPLAINED.**
* **The reverb's right output tail `+2`.** Bounded to three words (§3.3).
* **`NO OPERATION` +2, `AUTO WAH` / `AUTO WAH+S.DELAY` +1, `GATED REVERB` +4,
  `ROCK ROTARY` +4, `ROOM REVERB` +3.** Same species as the compressor's `+4`,
  none localised.
* **`BRIGHT REVERB 2`'s 38-word bank** and its one-slot ladder displacement.
* **The biquad's topology.** Four cells, two stores, one space — still no
  textbook form (§5.3).
* **`op 0x76`'s block width**, and `op 0x77` / `GEQ` entirely.
* **Whether the unit-1 `+0x80` displacement is a hardware bank bit or a software
  convention.** Measured from two independent places, mechanism unknown (§1.2).

## 9. Next experiments, in order of value

1. **Find the four compressor consumers.** The candidate set is eleven families
   and the target is a single integer per stage; disassembling the sub-CPU's
   compressor parameter path (`op 0x72`, `eval_0398CE`) would say how many words
   it expects the stage to own, and the reverb's right-tail `+2` (three
   candidates) is an even smaller instance of the same puzzle. Solve either.
2. **`MULTI TAP DELAY`.** The only image where the cursor overruns its bank; if
   it hides an unrecognised rewind encoding, that is a new instruction.
3. **Impulse-test the reverb** once the core runs: the stage gains are now
   *named*, so echo density and the 0.75/0.63/0.52/0.50/0.40 ladder are directly
   falsifiable against hardware.
4. **The state topology**, with the circular-buffer reading as the live
   hypothesis and the four zeroed cells per section as the constraint.
5. **`op 0x77` / `ENSEMBLE`** — the actual `LABEL_03B646`, and the only image
   that uses it.
