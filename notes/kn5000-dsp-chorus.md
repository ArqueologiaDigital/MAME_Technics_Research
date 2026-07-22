# NEC uPD6383GF — the CHORUS / LFO family, and the `212.2` twin test

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_chorus.py` (imports `kn5000_dsp_extract`, `_coeffs`, `_params`,
`_biquadmap`; **none of them is edited**).

**Append-only successor material**, in the same spirit as `kn5000-dsp-semantics.md`. It does
not edit `-effect-map.md`, `-semantics.md`, `-class2-round2.md`, `-biquad*.md`,
`-cursor-general.md`, `-parameters.md`, `-core-draft.md`, `-encoding.md`, `-INDEX.md`,
`-abv.md` or any tool. Corrections to them are collected in §7.

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or **SPECULATIVE**.
§8 lists what is falsified or explicitly not established — including two of the brief's own
premises and one of its hypotheses.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_chorus.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
```
Sections: `dump tap lfo space verify twin`. Runtime ≈ 20 s.

---

## Headline

1. **★★★ THE LFO IS DECODED, AND THE DECODE IS A PHASE ACCUMULATOR WITH A TABLE
   LOOKUP — NOT A COMPUTED SINE.** `hi12 = 0x092` (class A) adds a Q0.23 **phase
   increment in cycles per sample**; `hi12 = 0x094` (class A) consumes the wrap
   constant `0x7FFFFF` in **29 of 29** occurrences with no exception; the waveform
   comes from the table-lookup triplet, whose class-6 `addr8` selects it (§2).
2. **★★★ THE RATE LAW IS `f = c × 44,100 Hz`, AND IT IS CONFIRMED BY NINE ROUND
   NUMBERS.** The nine distinct increments in the ROM decode to
   **0.2, 0.4, 0.6, 1.2, 3.0, 4.0, 5.2, 7.4 and 1000.0 Hz**, each within **0.115 %**
   of a 0.1 Hz grid — and **eight of the nine are bit-exactly `trunc(f·2²³/44100)`**.
   At 48,000 Hz the same constants miss the grid by up to **8.7 %**. This is a
   **third independent derivation of the sample rate**, and it is the kind of check
   that could have failed and did not (§2.2).
3. **★★★ THE RATE'S HOST PARAMETER IS IDENTIFIED, EXACTLY.** The set of coefficient
   slots consumed by `092.A` words equals, **element for element in all 16
   LFO-bearing images (29 slots, 0 mismatches)**, the set of slots written by host
   opcode **`0x65`** (`eval_038F9B`) — and `0x65` is declared by **exactly those 16
   algorithms and no others**. Restricted to T2-confirmed writes, op `0x65` feeds
   **19 class-A words, all 19 of them `092.A.**.200`**: a *pure* opcode, the only
   one of its size in the corpus. `0x65` is **LFO SPEED** (parameter-name index 7,
   unit `Hz`). **MEASURED** (§2.3).
4. **★★ DEPTH is per-voice and lives in the tap idiom.** The modulated-tap idiom's
   second word `192.A.4N.000` is a class-A consumer whose `addr8` walks a per-voice
   parameter block; its default is 0 in every chorus image, i.e. depth is entirely
   host-supplied. For `ENSEMBLE` the six depths are written by host op **`0x77`**,
   whose four T2-confirmed writes are **4/4 `192.A.**.41A`** — closing part of the
   effect-map's "`op 0x77` still undecoded" item (§3.3, §7).
5. **★★ ENSEMBLE'S SIX VOICES ARE THERE, AND THE PREDICTION WAS MADE FIRST.** A
   *non-interpolated* 5-word variant of the tap idiom occurs **6 times** in
   `ENSEMBLE`, with depth `addr8` = `0x40 0x41 0x42 | 0x46 0x47 0x48` — **three
   voices, twice**. The interpolated 7-word idiom occurs **29 times, exactly the
   29 the brief quotes**, and **zero** times in `ENSEMBLE` (§3.2, §4.2).
6. **★★ A NEW SHARED-`lo12` FACT: `lo12 = 0x44C` is "apply the modulation offset",
   and the CLASS selects interpolation.** `CHORUS` uses `C40.3.20.44C`,
   `ENSEMBLE` uses `000.2.00.44C`. Same `lo12`, different class, and exactly the
   difference between an interpolated and a non-interpolated tap. This explains the
   brief's "the interpolation pair is absent from ENSEMBLE" with no new machinery,
   and it is the first *positive* support for the core-draft's conjecture that
   `lo12` carries the route while the class carries the arithmetic (§3.2).
7. **★ THE `2/π` HYPOTHESIS FOR THE LFO IS FALSIFIED.** `0x517CC1` occurs in eight
   images — `NO OPERATION`, `GATED REVERB`, `COMPRESSOR`, `AUTO WAH` and four
   `PEQ+COMPR*` combinations — and **not one of them contains an LFO read**. The
   constant belongs to the envelope detector, as `-effect-map.md` §6.3 already had
   it. The brief's "strongly suggests the LFO is computed" is **wrong**, and the
   table-lookup reading is what survives (§2.4).
8. **★ TASK B: the `212.2`/`212.A` twin rule HOLDS FOR THE WRITE AND FAILS AS A
   GENERAL RULE.** `hi12 = 0x212` = "write to `mem[ptr]`" independently of class;
   `212.2.**.000` (88 of its 103 occurrences have `addr8 = 0x00`, and it is
   immediately preceded by a `*.415` word 20 times) is the **plain store**, i.e.
   `212.A.FF.407` minus the coefficient fetch and minus the routing code.
   **But bit 23 is NOT a multiply-enable** — the phaser's nine-section chain has
   **eight sections containing zero class-A words**, and they are all-passes, which
   need a gain. Bit 23 is a **cursor-fetch enable**. And the generalisation fails
   outright: across the 17 `hi12` values carrying both forms, only **12 of 102**
   `lo12` values are shared between the classes (11.8 %) (§5).
9. **★ THE CHORUS/LFO HYPOTHESIS SPACE WAS ENUMERATED (34,992 points) BUT IS NOT
   SCOREABLE, AND NO WINNER IS DECLARED.** The biquad fell because an independent
   ground truth existed. Here there is none, and saying so is the result (§4.1).

---

## 1. What was already established, and is used unchanged

From `-encoding.md`, `-semantics.md`, `-biquad-map.md`, `-cursor-general.md`,
`-class2-round2.md`, `-effect-map.md`:

* the field map `hi12[35:24] . class4[23:20] . addr8[19:12] . lo12[11:0]`;
* the implicit **coefficient cursor**, +1 per class-A word, reset by `801.0.00.021`;
* the **signed `addr8` post-increment** data pointer;
* `hi12 = 0x082` = LFO read; `hi12 = 0x094` = phase accumulator (INFERRED there,
  now upgraded); the 3-word table-lookup triplet and its class-6 selector;
* `880.1.60`/`880.1.20` = the external-DRAM bracket; mode-`0x0B` records = tap
  lengths in DRAM words; 44,100 Hz;
* the host parameter machinery: T1 (`opcode → DSP address`) and T2 (the parameter
  bytecode with defaults).

Nothing above is re-derived. Everything below is new.

## 2. THE LFO

### 2.1 The block, read off `VIBRATO` (algo 50), the minimal case (**MEASURED**)

`VIBRATO` is 53 words, two taps, two LFOs, and its coefficient bank is
`00:0 01:0 02:c 03:1.0 04:0 05:0.5 | 06:c 07:1.0 08:0 09:0.5 | 0A:0 0B:0 0C:0.25`
— a visibly **repeated three-slot record `{c, 1.0000, 0}`**, once per channel.
Walking the cursor onto the program:

```
   w13  092.A.00.200   c[02] = 0x0002F8 = +0.00009060   <- PHASE INCREMENT
   w14  082.2.00.1C0                                    <- LFO READ
   w15  094.A.00.200   c[03] = 0x7FFFFF = +0.99999988   <- WRAP / SCALE
   w16  000.2.00.447
   w17  092.2.00.700                                    <- table-lookup driver
   w18  000.A.00.1D5   c[04] = 0                        <- phase offset
   w19  182.2.00.000
   w20  040.0.00.C63   \
   w21  000.6.18.4CD    >  the table-lookup triplet, table 0x18
   w22  012.4.01.1CE   /
   w23  104.2.FE.1CE
   w24  102.2.00.000
   w25  000.A.00.415   c[05] = +0.5000                  <- DEPTH (host op 0x66)
```

and the same thirteen words again at `w28..w40` for the second channel.

### 2.2 The rate law (**MEASURED**, and it is the strongest number in this note)

`094.A` consumes `0x7FFFFF` in **29 of 29** occurrences across the 16 LFO images —
one value, no exceptions. `0x7FFFFF` is `1 − 2⁻²³`, i.e. the accumulator's modulus.
`092.A` consumes a small positive constant, different per effect. Under the reading
*"`092.A`: phase += c; `094.A`: wrap at 1.0"*, the frequency must be `f = c·Fs`.

**The prediction was stated before the check: if that is right, the DEFAULTS the
designers wrote should be round numbers of Hz. Nothing forces nine unrelated
24-bit constants to be round.**

```
     raw       c              f @44100     f @48000    trunc(f·2^23/44100)
      38    0.00000453      0.1998 Hz     0.2174 Hz         38  == raw     FLANGER
      76    0.00000906      0.3995 Hz     0.4349 Hz         76  == raw     PHASER
     114    0.00001359      0.5993 Hz     0.6523 Hz        114  == raw     CHORUS
     228    0.00002718      1.1986 Hz     1.3046 Hz        228  == raw     AUTO PAN
     570    0.00006795      2.9966 Hz     3.2616 Hz        570  == raw     MIX UP
     760    0.00009060      3.9954 Hz     4.3488 Hz        760  == raw     VIBRATO
     989    0.00011790      5.1993 Hz     5.6591 Hz        989  == raw     MOD CHORUS
    1407    0.00016773      7.3968 Hz     8.0509 Hz       1407  == raw     MIX UP
  190217    0.02267563    999.9954 Hz  1088.4304 Hz     190215  != raw     RING MOD

    worst relative distance to a 0.1 Hz grid:  @44100 = 0.1145 %   @48000 = 8.7189 %
```

Eight of the nine are the **exact truncation** `trunc(f·2²³/44100)` of a round
frequency; the ninth (`RING MODULATOR`, nominally 1 kHz) is off by **+2 LSB**
(0.0005 % in frequency) and was evidently generated by a different expression — a
small, honest anomaly, reported rather than hidden.

> **ASSIGNED (MEASURED): `092.A.**.200` = "phase accumulator += coefficient", the
> coefficient being the LFO frequency in cycles per sample. `094.A.**.200` =
> "wrap/scale the phase by the coefficient", constant `0x7FFFFF` = 1.0.
> LFO rate in hertz = `coefficient × 44,100`.**

This also **re-derives the sample rate a third time**, independently of
`-parameters.md`'s `ms × 0xAC44 / 0x3E8` and of the delay-tap millisecond figures.

### 2.3 What sets the RATE, from the host side (**MEASURED**)

**Prediction, before the check:** if `092.A`'s coefficient is the LFO rate, the set
of addresses consumed by `092.A` words must equal, exactly, the set written by one
host opcode, and that opcode must appear in the LFO images and nowhere else.

```
   CHORUS     092.A slots [0x00]                op 0x65 writes [0x00]          OK
   MOD CHOR.  [0x00,0x02]                       [0x00,0x02]                    OK
   FLANGER    [0x05,0x09]                       [0x05,0x09]                    OK
   PHASER     [0x00,0x0C]                       [0x00,0x0C]                    OK
   ENSEMBLE   [0x00]                            [0x00]                         OK
   AUTO PAN   [0x01,0x04]                       [0x01,0x04]                    OK
   VIBRATO    [0x02,0x06]                       [0x02,0x06]                    OK
   RING MOD   [0x00,0x03]                       [0x00,0x03]                    OK
   MIX UP     [0x00,0x02,0x04]                  [0x00,0x02,0x04]               OK
   S.DELAY+CHORUS / +FLANGER / +VIBRATO / +PHASER, PEQ+CHORUS / +FLANGER / +VIBRATO
                                                                            all OK
   agree 16, disagree 0   (29 addresses)
   algorithms declaring host op 0x65 at all: exactly those 16
```

Restricted to T2-**confirmed** writes (unreferenced T1 operand slots discarded — see
§6 on that instrument blindness), op `0x65` feeds 19 class-A words and **all 19 are
`092.A.**.200`**. It is one of only seven *pure* opcodes in the whole corpus, and by
far the largest.

The user-facing parameter list (main ROM `0x0324D5`) has **index 7 = `LFO SPEED`,
unit `Hz`**. Its writer is `eval_038F9B` via `0x038539`. **INFERRED (strong):
host opcode `0x65` = LFO SPEED.**

### 2.4 Is the waveform tabulated or computed? (**MEASURED negative + INFERRED positive**)

**Prediction:** the brief proposes `0x517CC1` (= 2/π to 1 LSB, 53 occurrences) as
evidence of a computed sine. If so it must occur in LFO-bearing images.

```
   algo  0 NO OPERATION      2/pi x1   has an LFO read: False
   algo  8 GATED REVERB      2/pi x1   False
   algo 36 COMPRESSOR        2/pi x2   False
   algo 52 AUTO WAH          2/pi x1   False
   algo 70, 75, 96, 97 (PEQ+COMPR* family)      False
```

**Zero of eight.** The hypothesis is **FALSIFIED**. (The "53 occurrences" figure in
the brief counts the constant across all *program slots*; over the 38 distinct
images it is 12 occurrences in 8 images.)

What is left is the table-lookup triplet, and it is now doing real work: it sits
immediately after the accumulator block and immediately before the depth multiply,
which is exactly where "phase → waveform" belongs.

```
   table 0x18  x29   LFO images only
   table 0x1A  x 1   ENSEMBLE
   table 0x1E  x 3   ENSEMBLE, S.DELAY+CHORUS, PEQ+CHORUS
   table 0x20  x 3   CHORUS, MODULATED CHORUS, ENSEMBLE
   table 0x28  x17   every distortion image, and ROCK ROTARY's drive stage
```

> **VERDICT (INFERRED, strong): the LFO waveform is TABULATED, not computed.**
> Three independent supports: (a) the 2/π falsification above; (b) the class-6
> selector, which has no meaning in a computed sine; (c) the user parameter list
> contains **index 48 `LFO WAVEFORM`** and **index 49 `OSC WAVEFORM`** — the
> firmware exposes waveform *selection*, which is what a table bank is for.

**NOT ESTABLISHED: where the tables live.** `0x18/0x1A/0x1E/0x20/0x28` are 8-bit
values in the *class-6 `addr8`* field, so they are base addresses in some 256-entry
space — plausibly the C-RAM the `-INDEX.md` backlog item 1 is about. The stride-2
family `18/1A/1E/20` is **too closely spaced to be phase offsets of one waveform**
(2/256 of a cycle ≈ 2.8°, which decorrelates nothing), so they are more likely
distinct waveforms or distinct table pages. **SPECULATIVE**; this note does not
choose, and the tables' contents are not in the extracted stream.

### 2.5 What sets the DEPTH (**INFERRED**)

Two mechanisms, both measured in position and neither with a default in the ROM:

* the **global** depth: the class-A word immediately after the triplet's
  `012.4.01.1CE`/`104.2.**.1CE` pair — `000.A.**.415` in `VIBRATO` (c[05] = 0.5),
  `000.A.00.415` and `010.A.00.1D5` in `CHORUS` (c[09] = c[0A] = 0.5). Host op
  `0x66` writes these; its T2 default is `0x400000` = **+0.5** in `CHORUS`,
  `VIBRATO` and `ROCK ROTARY`. `0x66` is the corpus's second-largest opcode (41
  T2-confirmed class-A consumers) and is **not** pure, so "op 0x66 = DEPTH" is
  **INFERRED, weak** — it is a general "level" opcode.
* the **per-voice** depth: the tap idiom's `192.A.4N.000` word, whose `addr8` walks
  a per-voice block (§3.1). In `ENSEMBLE` these are `192.A.4N.41A` and host op
  `0x77` writes exactly them (4/4 T2-confirmed).

## 3. THE MODULATED TAP

### 3.1 The interpolated idiom (**MEASURED**)

```
   [0]  9xx.1.60.1D5      DRAM read transaction OPEN
   [1]  192.A.4N.000      class A -- per-voice DEPTH; addr8 walks the voice block
   [2]  082.2.00.1C0      LFO READ                       byte-invariant
   [3]  C40.3.20.44C      apply modulation, WITH fraction byte-invariant
   [4]  A00.0.00.041      interpolation partner           byte-invariant
   [5]  880.1.20.2C7      DRAM read CLOSE -> the tap      byte-invariant
   [6]  102.A.xx.4C8      class A -- per-voice output gain
```

**29 occurrences, in 10 distinct images, with no near misses and no exceptions** —
the same 29 the brief quotes for the `C40.3.20.44C + A00.0.00.041` pair, now
resolved into a complete 7-word transaction. The control is clean: **every**
`C40.3.20.44C` in the corpus is followed by `A00.0.00.041 | 880.1.20.2C7`, 29 of 29.

Words `[2] [3] [4] [5]` are **byte-identical in every occurrence**; only `[0]`'s
`addr8` (always `0x60`), `[1]`'s and `[6]`'s vary.

### 3.2 The non-interpolated variant, and the `0x44C` fact (**MEASURED / INFERRED**)

```
   800.1.20.1D5 | 192.A.4N.41A | 082.2.00.1C0 | 000.2.00.44C | 880.1.20.2D9
```

Six occurrences, all in `ENSEMBLE`. The middle word carries **the same `lo12`
(`0x44C`)** as the interpolated form's `C40.3.20.44C`, in a different class and
without the `A00.0.00.041` partner.

> **ASSIGNED (INFERRED): `lo12 = 0x44C` = "offset the DRAM address by the
> modulation value". Class 3 (`C40.3.20.44C`) additionally keeps the fractional
> part and pairs with `A00.0.00.041` to interpolate; class 2 (`000.2.00.44C`)
> truncates.** This is the note's cheapest new decoding, and it is the first
> positive evidence for `-core-draft.md` §6 item 2's conjecture that `lo12` carries
> the route and the class carries the arithmetic.

### 3.3 The per-voice pointer walk (**MEASURED**)

```
   CHORUS            [1].addr8  0x40 0x41 0x44 0x44   [6].addr8  0xC3 0xC1 0xBF 0xBD
   MODULATED CHORUS  0x40 0x41 0x44 0x44              0xC3 0xC1 0xBF 0xBD
   ENSEMBLE          0x40 0x41 0x42 0x46 0x47 0x48    (all [6] = 0x00)
   VIBRATO           0x40 0x41                        0xBD 0xAD
   ROCK ROTARY       0x40 0x5B 0x50                   0xBE 0xA6 0xA7
   S.DELAY+CHORUS    0x3C 0x4B 0x40 0x4F              0xC2 0xC0 0xBE 0xBC
   PEQ+CHORUS        0x40 0x4F 0x48 0x57              0xBE 0xBC 0xB6 0xB4
```

`[1].addr8` is positive and ascends within an image; `[6].addr8` is negative as a
signed post-increment. Under the MEASURED post-increment rule this is **one data
pointer that walks up a per-voice parameter block and is rewound at the end of the
voice**. `ENSEMBLE`'s `0x40 0x41 0x42 | 0x46 0x47 0x48` is the clearest case:
consecutive per-voice slots, three of them, twice.

## 4. THE SEARCH, AND WHY IT DOES NOT TERMINATE THE WAY THE BIQUAD'S DID

### 4.1 The space, and the honest verdict

The machine model is a strict extension of `-semantics.md` §1: `acc`, `P`, `mem[]`,
`cursor`, `ptr` unchanged, plus a DRAM address latch `ADDR`, a fraction latch
`FRAC`, and the decoded `phase`. The target semantics is

```
   y = c · ( (1−f)·d[b + ⌊m⌋] + f·d[b + ⌊m⌋ + 1] ),   m = depth · lfo(t)
```

Free choices per idiom word, enumerated explicitly:

```
   [0] ADDR <- {base, base+mod, mod}                                  3
   [1] P <- c[cur]·{mem[ptr], LFO, ADDR}  ×  ADDR += {0, P, nothing}  3×3
   [2] LFO <- {table result, phase, mem[ptr]}                         3
   [3] FRAC <- {frac(ADDR), acc, LFO}                                 3
   [4] {Lprev <- d[ADDR], ADDR += 1, nothing}                         3
   [5] blend with {Lprev, none} × {F, 1−F}                            4
   [6] P <- c[cur]·{D, acc} × acc {+=P, <-P, none}                    6
   which word latches the fraction                                    2
   ---------------------------------------------------------------------
   TOTAL points enumerable                                       34,992
```

Excluded a priori, listed so the space cannot be mistaken for one narrowed until it
was unique:

| | restriction | why |
|---|---|---|
| X1 | the LFO **waveform** is not searched | decoded separately in §2; no ROM observable depends on its shape |
| X2 | **linear** interpolation only | exactly one class-A word follows the DRAM close, so a higher-order interpolator has nowhere to live |
| X3 | the tap **base** is the mode-`0x0B` value | MEASURED elsewhere |

> **THE SPACE WAS NOT SCORED, AND NO WINNER IS DECLARED. That is the result, not a
> shortfall of effort.** The biquad fell because an *independent* ground truth
> existed: `H(z)` computable from the same ROM coefficients, against which a
> candidate either produced `max|err| = 0.000e+00` or did not. For the modulated
> tap there is no such thing in the ROM: the depth and rate **defaults are
> host-written**, the waveform table is **not in the extracted stream**, and the
> output is a delayed copy of an arbitrary input. Every one of the 34,992
> assignments produces "a modulated fractional delay"; they differ only in
> quantities nothing in the ROM pins down. Announcing a survivor here would be
> reporting a fit, and this project has enough corrections already.

What *can* be done is to cut the space with checks that can fail:

* **C1 — field invariance.** **Five** of the seven words are byte-identical in all 29
  occurrences. A word that never varies carries no per-tap operand address, so
  `[2]` and `[3]` cannot take `mem[ptr]` as their operand — that needs a per-tap
  `addr8`. This eliminates one branch at each: **34,992 → 15,552**, measured, and
  falsifiable had any occurrence varied. It is a reduction, not a solution.
* **C2 — the pointer walk** of §3.3 forces `[1]` and `[6]` to be the two per-voice
  cursor consumers, which is what the coefficient accounting independently shows.

### 4.2 The falsifiable checks the brief asked for, and their outcomes

| check | prediction | outcome |
|---|---|---|
| **voice count** — `ENSEMBLE` is 3 × stereo, so **six** modulated taps | stated before counting | **PASS, exactly.** 6 non-interpolated idioms, depth `addr8` `40 41 42 \| 46 47 48` |
| **idiom vs tap reads** — idioms ≤ `880.1.20` reads in every image, strictly fewer where a static long delay exists | stated before counting | **PASS.** `S.DELAY+CHORUS` 6 reads / 4 modulated; `S.DELAY+VIBRATO` 4 / 2; equality everywhere else |
| **periodicity** — the rate law must give the LFO period | — | **PASS**, and it gives round Hz (§2.2). `CHORUS` 0.5993 Hz = 73,584 samples; `VIBRATO` 3.9954 Hz = 11,038 samples; `RING MODULATOR` 999.995 Hz = 44.1 samples |
| **tap spacing 520 = the delay excursion** | — | **FAILS, and the failure is informative** (below) |
| **rotary pair explained by coefficients alone** | — | **VACUOUS — the premise is false** (below) |

**The 520 check fails and should.** `CHORUS`'s four taps are `200 / 720 / 1240 /
1760`, i.e. **four independent voices**, each with its own `192.A` depth slot. 520
is the gap *between* voices, not a sweep range. The only thing it constrains is an
upper bound: a peak excursion beyond ±260 samples would let adjacent voices cross.
`MODULATED CHORUS` spaces at 450, `PEQ+CHORUS` at 320, `VIBRATO` at 420 — spacings
that track the number of voices, not any modulation depth. Reporting 520 as an
excursion would have been wrong.

**The rotary-pair premise is false.** `ROCK ROTARY` (15) and `ROTARY SPEAKER` (53)
are identical in **every respect the tooling can see**: microcode byte-identical,
mode-`0x0B` delays identical, **all 38 static coefficient slots identical (0
differing)**, the *same* T1 pointer `0x016E85`, and T2 record contents
byte-identical (at different addresses). They differ only in the effect **name**.
So there are no "different banks", the check passes vacuously, and it confirms
nothing about the decode. Reporting it as a confirmation would be dishonest.

That check did turn up something real, though: **`ROCK ROTARY` is the one modulated
image with NO `092.A` word at all.** Its two rotor speeds (`0.320` / `0.420` at
slots `0x10` / `0x14`) reach the chip through host op `0x69` (`eval_0392AC`, the
`/180`-degree scaler) at slots `0x0F` / `0x13`. **The machine therefore has a second
rate mechanism, and this note does not decode it.**

## 5. TASK B — the `212.2` family and the twin rule

### 5.1 The family, counted (**MEASURED**)

```
   class lo12  count images        class lo12  count images
     2   000    103   32             A   415     11    4
     A   412     42   15             2   00B      9    9
     A   1D5     35   20             2   1D5      6    3
     A   407     35   13             2   447      5    4
     2   412     30    3             A   000      2    1
     2   419     28   13             A   1D3      2    1
     2   407     21   20             2   41D      2    1
     2   1CD     19   14             A   655/452   1    1
```

### 5.2 The twin test, predicted then run

**Prediction, stated before the test.** If bit 23 is a pure multiply-enable and
`0x212` means "write the operand into `mem[ptr]` and multiply by it"
(`-semantics.md` §3.2), then in the phaser's nine identical all-pass sections the
eight carrying `212.2.01.412` perform the same *write* as the ninth's
`212.A.B0.412`, and only the ninth also fetches a coefficient. That predicts each of
the eight is still arithmetically complete — i.e. contains its own class-A word.

**Result (MEASURED):**

```
   PHASER, sections at 12 15 18 21 24 27 30 33 36 39 | 71 74 77 80 83 86 89 92 95 98
   class-A words per section:   0 0 0 0 0 0 0 0 0 1  |  0 0 0 0 0 0 0 0 0 1
```

**Eighteen of the twenty sections contain ZERO class-A words**, and they are
first-order all-passes (the `c + s == 0xFF` triple, `-class2-round2.md` §1.4), which
require a gain. **Prediction (a) FAILS.** Two repairs survive and this note does not
choose between them:

* **R1** — class-2 words *do* multiply, taking the coefficient from an explicitly
  addressed location (`102.2.<c>.1CD`'s `addr8`) rather than from the cursor. Bit 23
  is then a **cursor-fetch enable**, not a multiply enable.
* **R2** — all nine stages share one gain held in a register, fetched once, so eight
  sections genuinely need no fetch. Plausible for a phaser (one LFO sweeps all
  stages together) but it leaves the *ascending* `addr8` walk `45 46 … 4D` in the
  `102.2` words to explain as pure state addressing.

Either way, **"bit 23 = multiply" is not the right statement**, and this corrects
both `-encoding.md`'s roles list and `-semantics.md`'s model note. R1 is the reading
that also explains the cursor accounting (bank size = class-A count + 1) exactly.

### 5.3 What `212.2.**.000` is (**INFERRED, strong**)

```
   addr8 distribution: 0x00 ×88, then 0xF1 0xBE ×2 and eleven singletons  (n = 103)

   16×   000.2.00.415  << 212.2.**.000 >>  000.A.00.415
    5×   000.2.00.40E  << 212.2.**.000 >>  880.1.60.000
    5×   000.2.00.40E  << 212.2.**.000 >>  02A.2.00.000
    4×   000.A.00.415  << 212.2.**.000 >>  092.2.00.700
```

`addr8 = 0x00` (no pointer advance) and `lo12 = 0x000` (no read/latch/route code),
sitting after a `*.415` level word and before the next block. Under
`hi12 = 0x212` = "write to `mem[ptr]`":

> **ASSIGNED (INFERRED): `212.2.00.000` = the plain store — "write the accumulator
> into `mem[ptr]`", with no coefficient fetch, no pointer advance and no routing.**
> It is `212.A.FF.407` minus everything the class-A form adds, which is exactly the
> twin relation the brief asked about, and it is the most universal store in the
> corpus (32 of 38 images) — which is what a plain store should be.

### 5.4 Does the twin relation generalise? (**MEASURED — NO**)

```
   hi12   nA    n2   lo12 SHARED         lo12 A-only          lo12 2-only
   000   192   564   1D5,415             1D3,219,412,452,455  000,1C8,1CD,1CE,407
   212   129   223   000,1D5,407,412     1D3,415,452,655      00B,1CD,419,41D,447
   202   234    55   1D5                 1D4,216,415,655,695  000,1C8,1CD,407
   102    70   120   (none)              1D3,1D4,1D5,4C8,64B  000,1CD,687
   104    16   127   1D5                 179                  000,1CE,407
   092    29    48   (none)              200                  1D5,700
   012     1    71   1D5                 —                    1C0,1D1,447,655,680
   ... 10 more

   17 hi12 values carry BOTH a class-A and a class-2 form
    8 of them share at least one lo12 between the classes
   shared lo12 / all lo12  =  12 / 102  =  0.118
```

If `class4` were a free bit orthogonal to the rest of the word, the `lo12` sets
would coincide. They overlap by **11.8 %**. `102` and `092` — two of the largest
families — share **nothing**. **The twin relation does not generalise into a decoding
rule.** It holds for `0x212` because `hi12` carries the write there; it is not a
property of bit 23.

## 6. What this instrument is blind to

Stated explicitly, because three self-inflicted errors in this project came from not
asking.

1. **The T1 opcode→address map over-counts.** A raw T1 scan attributes every operand
   slot an opcode *declares* to that opcode, including slots the T2 stream never
   references. Op `0x74` declares `1D 00 00 00`; the three `0x00` entries are
   placeholders, and a raw scan therefore credits op `0x74` with 36 `092.A` hits it
   does not make. All opcode↔word statistics in §2.3 and §2.5 are **T2-confirmed
   only** (with ambiguous record parses reduced to the intersection of their
   solutions). The raw-scan numbers are ~2× larger and are wrong.
2. **The idiom matcher is a fixed-length exact pattern with three wildcards.** It
   found the 29 interpolated taps, and it found **zero** in `ENSEMBLE` — which would
   have looked like "ENSEMBLE has no modulated taps" had the near-miss scan not
   surfaced the 5-word variant. This is the same failure mode as the earlier
   byte-identical search that found 8 of 27 sections. Both idioms are now matched
   separately, and the tool prints near misses.
3. **`class-6` is not 53/53 over the raw file set.** Scanning all 96 extractable
   programs finds **58** class-6 words, five of which are *not* in a triplet
   (`0x20 0x74 0x80 0xE8`, plus a second `0x20`) — **all five inside algo 88**, one
   of the five images the corpus documents as malformed. Excluding the malformed
   images restores the effect-map's 53/53 exactly. The earlier figure is right; a
   naive re-count is not.
4. **Nothing here was executed on hardware or in an emulator.** The DSP core is
   still disabled (`-core-draft.md` §5). Everything is static.
5. **The LFO table contents are not observed at all.** The decode says a table is
   read and which selector chooses it; it says nothing about what is in it.

## 7. Corrections and additions to earlier notes

| earlier claim | source | status here |
|---|---|---|
| `hi12 = 0x094` = "LFO phase accumulator", INFERRED weak (MCC +0.948) | effect-map §6.3 | **UPGRADED to MEASURED and made precise**: it consumes the wrap constant `0x7FFFFF`, 29/29. The *increment* is on `092.A`, not `094.A` |
| `hi12 = 0x092` = "LFO / table-driver stage", INFERRED weak | effect-map §6.3 | **DETERMINED**: `092.A.**.200` is the phase-increment add; its coefficient is the rate in cycles/sample. `092.2.**.700` (the class-2 form) remains the table driver and is a *different* word |
| `0x517CC1` (2/π) "strongly suggests the LFO is computed" | the brief | **FALSIFIED** (§2.4): zero of its 8 images has an LFO read |
| `C40.3.20.44C` + `A00.0.00.041` = fractional-delay interpolation, role INFERRED | effect-map §6.3 | **UPHELD and extended**: they are words `[3]`/`[4]` of a complete 7-word transaction, 29/29, and `lo12 0x44C` is shared with `ENSEMBLE`'s non-interpolated form |
| "the interpolation pair is not in ENSEMBLE" | effect-map §6.3, the brief | **EXPLAINED**: ENSEMBLE uses the class-2 variant of the same `lo12` and truncates (§3.2) |
| `op 0x77` and ENSEMBLE's six entries — undecoded | effect-map §5.3, §8 | **PARTLY CLOSED**: op `0x77`'s T2-confirmed writes are 4/4 `192.A.**.41A`, i.e. the per-voice depth slots of the six ENSEMBLE voices |
| bit 23 = "the multiplier" / multiply-enable | encoding.md roles, semantics §1 | **CORRECTED**: it is a **cursor-fetch** enable. Eighteen phaser all-pass sections have zero class-A words (§5.2) |
| "bit 23 may select the multiplier operand rather than enable the multiplier" | class2-round2 §1.4 caveat | **CONFIRMED as the correct reading** |
| `212.2.**.000` — the highest-value undecoded family | core-draft §4, §6 item 1 | **DECODED as the plain store** (§5.3) |
| "decoding what bit 23 removes … is the cheapest real gain available" and would give a general rule | core-draft §6 item 1 | **HALF-RIGHT**: `0x212` decoded; the general rule **does not exist** (12/102 lo12 overlap, §5.4) |
| ROCK ROTARY and ROTARY SPEAKER = "byte-identical microcode with different banks" | the brief | **CORRECTED**: the banks are identical too, as are the delays, the T1 map and the T2 records. They are the same effect listed twice |
| "44,100 Hz, proven twice" | INDEX, parameters §7 | **PROVEN A THIRD TIME**, independently (§2.2) |
| op `0x70` = biquad coefficient writer | biquad-map | **CROSS-CHECKED here**: 13 of its 15 T2-confirmed consumers are `000.A.**.1D3`, the biquad's `b1` word. A free consistency check of the method |

## 8. Falsified, or explicitly not established

* **The LFO is computed from a 2/π sine approximation** — **FALSIFIED** (§2.4).
* **Bit 23 is a multiply-enable** — **FALSIFIED** (§5.2).
* **The class-A/class-2 twin relation is a general decoding rule** — **FALSIFIED**
  (§5.4). It holds for `0x212` for a reason specific to `0x212`.
* **The 520-sample CHORUS tap spacing is a modulation excursion** — **FALSIFIED**;
  it is inter-voice spacing (§4.2).
* **ROCK ROTARY / ROTARY SPEAKER differ in their coefficient banks** — **FALSIFIED**;
  they differ only in name (§4.2).
* **NOT ESTABLISHED — the modulated tap's word-level semantics.** The space was
  enumerated (34,992) and cut to 15,552 by a falsifiable invariance argument, but it
  cannot be scored from the ROM alone. No assignment is claimed (§4.1).
* **NOT ESTABLISHED — where the LFO waveform tables live**, what is in them, and
  whether `0x18/1A/1E/20` are separate waveforms or pages (§2.4).
* **NOT ESTABLISHED — ROCK ROTARY's rate mechanism.** It has no `092.A` word; its
  rotor speeds arrive via host op `0x69`. A second, undecoded rate path (§4.2).
* **NOT ESTABLISHED — the R1 vs R2 repair** of the phaser's coefficient source
  (§5.2), and therefore what `102.2.<c>.1CD`'s `addr8` addresses.
* **NOT ESTABLISHED — whether host op `0x66` is "DEPTH".** It is the general level
  opcode (41 consumers, 8 distinct word forms); the depth *slots* are identified by
  position, not by the opcode.
* **Everything outside this family**: `COND`, `BRAKST`, the header words, class 8,
  C-RAM vs D-RAM, DSP2. Untouched.

## 9. What would close the remaining gaps, ranked

1. **Read the waveform tables.** The class-6 `addr8` values are base addresses in a
   256-entry space. If the host ever *writes* that space — the parameter list has
   `LFO WAVEFORM` as a user parameter, so something must — the sub-CPU disassembly
   has the writer, and the tables come with it. This is the single highest-value
   next step and needs no new data.
2. **Decode host op `0x69`** (`eval_0392AC`, the `/180`-degree scaler) and with it
   `ROCK ROTARY`'s second rate mechanism. Small, self-contained, already localised.
3. **Settle R1 vs R2** on the phaser by checking whether `102.2.45.1CD … 4D` address
   nine *coefficients* or nine *state cells*: if the host ever writes `0x45..0x4D`,
   they are coefficients and R1 wins. The T1 map for algo 5 answers this directly.
4. **A live LFO read-back.** With the core enabled, sampling the phase accumulator
   over 100 ms would confirm the rate law dynamically — but the static evidence
   (nine round frequencies, bit-exact truncation, a pure host opcode) is already
   stronger than most dynamic checks would be.
5. **Apply §3.2's class-selects-arithmetic reading to the `lo12 = 0x415` group**
   across classes A/2/8, which `-core-draft.md` §6 item 2 ranks second overall and
   which now has a precedent.
