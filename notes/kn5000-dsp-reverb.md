# The KN5000 reverb, read as a reverb

NEC uPD6383GF-3BA (KN5000 IC311). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_reverb.py` (imports `kn5000_dsp_extract.py` and
`kn5000_dsp_coeffs.py`; neither is rewritten).
Companions: `notes/kn5000-dsp-encoding.md` (instruction fields),
`notes/kn5000-dsp-coefficients.md` (coefficient banks + effect-name table).

The method, in Felipe Sanches' words: *"as a clue of what each instruction does,
you could perhaps try to identify the overall structure of typical reverb
algorithms and compare to the now labeled reverb programs."* Bit statistics
cannot produce semantics. A reverb, however, has a **known** shape, and the name
table tells us which programs are reverbs. That converts structure into meaning.

Every claim is tagged **MEASURED**, **INFERRED** or **SPECULATIVE**.

**Headline (MEASURED):** the 133-word reverb program is built from an
**8-instruction motif repeated 9 times**, in two blocks of 5 and 4; the motif is
**byte-identical** at every repetition, and 5 of its 8 words occur in **exactly
the 13 reverb programs and nowhere else** in the 96-program corpus. The delay
lengths are **not** in the microcode — they are **DRAM address pairs in the
parameter stream**, in a contiguous-tiling form that occurs in the 13 reverb
slots and in **none** of the other 57 named effects. Two chains of 5 delay
buffers each, matching the **two 5-gain ladders** already found in the
coefficient bank.

---

## 0. The textbook priors (what we were looking for, stated before looking)

* **Schroeder (1962):** N parallel feedback **combs** (`y = x + g·z^-D·y`, `g`
  ~0.7–0.85, D mutually prime) summed, then 2–3 **series all-passes**
  (`w = x + g·d`, `y = d − g·w`) to smear the echo density.
* **Moorer (1979):** Schroeder plus a **one-pole lowpass inside each comb's
  feedback loop** (air/wall absorption), plus a bank of early-reflection taps in
  front.
* **Dattorro (1997) / Gardner:** a figure-of-eight **tank**: an input diffuser of
  series all-passes feeding a loop containing *absorbing all-passes*
  (a damping filter embedded in the all-pass feedback) and long delays.
* **Giveaway signatures.** An all-pass uses the **same** delay with `+g` on the
  feed-forward and `−g` on the feedback. A comb is one delay times one gain
  summed back. Damping is a one-pole lowpass **inside** the loop. A diffuser
  ladder has **monotonically ordered gains** and **increasing delays**.
* The coefficient note already reports, in the reverb banks, one-pole damping
  poles (0.99996 / 0.99906 / 0.96290), `−1.0` inverting taps, and two 5-gain
  ladders. Those are exactly the fingerprints above.

The KN7000 reverb (`kn7000_disassembly/dsp/reverb-algorithm.md`) is a Moorer /
Dattorro hybrid: filtered early reflections, a **4-all-pass series diffuser**
(all `k = 0.618`), one **absorbing all-pass**, and **two lowpass-damped feedback
combs**, closed by an output tone filter and a stereo-decorrelation delay. It is
used here as a *structural* reference only. The numeric cross-check between the
two machines was already run and came back negative; it is not redone.

---

## 1. THE MOTIF (MEASURED)

`tools/kn5000_dsp_reverb.py` section 1, on `algo20.bin` (CONCERT REVERB 1,
ROM pointer `0x001C701`, 133 words, loads at I-RAM 200 — the largest program in
the ROM and the one shared by all twelve reverb presets).

The longest repeating instruction sequence is **8 words long** and occurs at
word indices **19, 27, 35, 43, 51, 77, 85, 93** (8 exact, non-overlapping) plus
a **9th near-copy at 69** that differs in exactly one field (`addr8` of its 6th
word: `102.A.**BA**.64B` instead of `102.A.**00**.64B`):

```
   idx+0   880.1.60.2D4      class 1  (control / non-memory family)   addr8=0x60
   idx+1   104.2.00.000      class 2  (memory-referencing)
   idx+2   000.2.00.419      class 2
   idx+3   012.2.00.680      class 2
   idx+4   880.1.20.655      class 1  (control / non-memory family)   addr8=0x20
   idx+5   102.A.00.64B      class A  (memory-referencing)
   idx+6   000.2.00.000      class 2
   idx+7   000.2.00.000      class 2
```

**Fields that vary between repetitions: NONE.** Eight of the nine occurrences
are bit-for-bit identical; the ninth differs only in `addr8`. This is the first
important negative of this note and it is stated up front:

> **The delay lengths and gains are NOT immediates inside the repeated stage.**
> The coefficient note's prediction ("reverb taps must be immediates inside the
> microprogram") is **FALSIFIED for the repeated stages**. §2 shows where they
> actually are.

A byte-identical repeated stage is the signature of a machine that walks its
operands with **auto-incrementing pointer registers**. The uPD6383GF block
diagram (CDJ-500 manual p. 1-15) has six of them — `CP`, `DP`, `BP1`, `BP2`,
`PR1`, `PR2` — plus a bank register. **INFERRED:** each repetition consumes the
next coefficient from C-RAM and the next delay descriptor from the external-DRAM
address registers, with no instruction field changing.

### 1.1 Program skeleton (MEASURED)

```
     0.. 10   prologue                (input scaling, pre-delay write)
    11.. 15   separator  880.1.60.2DA / 000.A.00.695 / 000.2.BA.000 /
                         212.2.00.419 / 880.1.20.64B
    16.. 18   block-1 head
    19.. 58   ***** 5 x MOTIF *****            <- chain 0
    59.. 63   separator  (same five-word shape, 000.2.F3.407)
    64.. 68   block-2 head
    69..100   ***** 4 x MOTIF ***** (first is the addr8=0xBA variant)  <- chain 1
   101..105   separator  (same shape, 000.2.FE.407)
   106..110   epilogue head
   111..130   output stage: two  C40.1.80.000  pairs at 111/112 and 122/123
                             framing two near-identical 9-word tails
   131        880.1.60.40E
   132        612.1.0F.000   <- the terminator landmark (encoding note §6.1)
```

The three separators are the same five-word shape with one `addr8` immediate
changing (`0xBA`, `0xF3`, `0xFE`) — **INFERRED:** the per-block C-RAM/D-RAM
cursor reload. The output stage's two near-identical 9-word tails (113–121 and
124–130) differ only in `addr8` immediates and are **INFERRED** to be the
**left and right output channels** — the same stereo mirroring the coefficient
bank shows (§3).

### 1.2 THE CONTROL — mandatory, and it passes (MEASURED)

Searching the exact 8-word motif across all **96 extracted programs / 7108
words**:

| algo | name | words | occurrences |
|---|---|---|---|
| 8 | **GATED REVERB** | 102 | 4 |
| 16–27 | ROOM/PLATE/CONCERT/DARK/BRIGHT/WAVE REVERB 1&2 | 133 | 8 each |

**13 of 96 programs, and all 13 are reverbs.** Zero hits in the compressor, the
parametric EQ, the chorus family, the delays, the rotary speakers, the
distortions, the phaser, the exciter or the auto-pan.

Per-word, the discrimination is just as sharp. Of the 8 motif words, **5 occur
in exactly 13 programs each — the same 13**:

```
   8801602D4   115 occurrences, 13 programs   <- reverb-exclusive
   000200419   115 occurrences, 13 programs   <- reverb-exclusive
   012200680   115 occurrences, 13 programs   <- reverb-exclusive
   880120655   115 occurrences, 13 programs   <- reverb-exclusive
   102A0064B   101 occurrences, 13 programs   <- reverb-exclusive
   104200000   122 occurrences, 16 programs
   000200000   273 occurrences, 27 programs   <- generic (NOP candidate, §5)
```

So the motif is **not** a generic DSP idiom. It is the reverb's stage.

---

## 2. WHERE THE DELAY LENGTHS LIVE (MEASURED)

The reverbs carry **no mode-0x0B delay entries** (coefficient note §4). §1 shows
they are not immediates in the repeated stage either. They are in the **op-5
mode-0x0A entry stream**, which the coefficient note read as "16-bit DSP
register values". For the reverbs those values are **external-DRAM addresses**,
emitted **in pairs**, and the pairs **tile the delay arena contiguously**.

CONCERT REVERB 1 (slot 20), op-5 mode-0x0A payloads in emission order:

```
  40FA 0000 | 51E2 4000 | 52FF 513B | 5460 51E2 | 56D1 52FF | 5A16 5460 |
  5B06 56D1 | 5C06 5A16 | 5DB9 5B06 | 5F0C 5C06 | 60CE 5DB9 | 6272 5F0C |
  43A5 4617 | 47F7 430B | 457A 4615 | 3FFF 60CE
```

Take the pairs as `(end, start)`. **Every other pair chains exactly**
(`start_k == end_{k-1}`), and the two interleaved phases give two contiguous
runs:

```
 chain 0   0x513B -> 0x52FF -> 0x56D1 -> 0x5B06 -> 0x5DB9 -> 0x60CE
           lengths   452   978   1077   691   789                 (5 buffers)
 chain 1   0x4000 -> 0x51E2 -> 0x5460 -> 0x5A16 -> 0x5C06 -> 0x5F0C -> 0x6272
           lengths  4578   638   1462   496   774   870           (6 buffers)
```

The tiling is **exact**: `sum(chain 0) = 3987 = 0x60CE − 0x513B` and
`sum(chain 1) = 8818 = 0x6272 − 0x4000`, to the word. A misparse cannot produce
that. Both chains sit far inside the DRAM controller's A0–A16 limit of 131072
words (the whole reverb arena is 0x4000..0x6272, 8818 words). The first chain-1
segment, **4578 samples ≈ 95 ms**, is the odd one out by an order of magnitude
and is **INFERRED** to be the input **pre-delay** line, not a recirculating
stage.

That leaves **5 + 5 = 10 recirculating delay buffers**, against **5 + 4 = 9**
motif repetitions in the code. The residual one is **INFERRED** to be handled by
the block-1 head at words 16–18 or the prologue; this off-by-one is *not*
resolved and is flagged.

### 2.1 THE CONTROL for the address chains — also mandatory, also passes (MEASURED)

Running the "contiguous `(end,start)` chain of ≥3 segments" detector on all 100
parameter streams:

```
  DETECTED (13 distinct effects):
     GATED REVERB, ROOM REVERB 1/2, PLATE REVERB 1/2, CONCERT REVERB 1/2,
     DARK REVERB 1/2, BRIGHT REVERB 1/2, WAVE REVERB 1/2
  NOT FOUND: the other 57 named effects
```

The same 13 slots that carry the motif, arrived at by a completely independent
route (parameter stream vs. microcode). **Two independent reverb detectors, the
same 13 programs.** The chorus family — which *does* have explicit delay taps,
in mode-0x0B — is not detected, exactly as it should not be.

### 2.2 THE RATIO / MUTUAL-PRIMALITY TEST — a partial NEGATIVE (MEASURED)

The classical prior says reverb delay lengths are **mutually prime** and lie in
a ratio band of roughly 1:1.5–1:2. Tested explicitly:

| preset | chain | lengths | coprime pairs | overall gcd | max/min |
|---|---|---|---|---|---|
| ROOM REVERB 1 | 0 | 127 435 489 183 522 | 4/10 | 1 | 4.11 |
| CONCERT REVERB 1 | 0 | 452 978 1077 691 789 | 6/10 | 1 | 2.38 |
| CONCERT REVERB 1 | 1 | 638 1462 496 774 870 (+4578) | 0/15 | **2** | 9.23 |
| PLATE REVERB 1 | 0 | 452 1090 1548 691 1373 | 7/10 | 1 | 3.42 |
| WAVE REVERB 1 | 0 | 452 1490 4148 691 2173 | 7/10 | 1 | 9.18 |
| GATED REVERB | 0 | 858 1263 1120 1780 | 2/6 | 1 | 2.07 |

**Verdict: the mutual-primality prior is NOT satisfied.** Typically only about
half the pairs are coprime, and CONCERT REVERB 1's chain 1 is *entirely even*
(gcd 2). This is a genuine negative and it is reported as such rather than
quietly dropped. Two readings, neither proved:

* **INFERRED:** these buffers are **all-passes / diffusers**, not parallel
  Schroeder combs. The mutual-primality rule is a *comb* rule — it exists to
  stop coincident echo periods in a parallel comb bank. A series diffuser does
  not need it, and the KN7000's own diffuser delays (313, 607, 1227, 2587) are
  likewise not mutually prime.
* **SPECULATIVE:** the designer simply did not apply the rule.

The **ratio band**, in contrast, is respected in chain 0 of every preset: 2.1–4.1
for ROOM/PLATE/CONCERT/GATED, widening to 9.2 only for WAVE (whose name promises
the most extreme tail). Within a chain the lengths are also **not monotonic**
(452, 978, 1077, 691, 789), which is a diffuser's characteristic scramble rather
than a comb bank's ordered ladder.

### 2.3 THE FALSIFIABLE PRESET TEST — mostly passes (MEASURED)

If these numbers are really the reverb's delay lines, then the **preset names
must predict their total size**: a ROOM is small, a CONCERT hall is large.
Total arena per preset:

```
   ROOM REVERB 1       8103 words   168.8 ms      <- smallest, as predicted
   ROOM REVERB 2      11661         242.9
   CONCERT REVERB 1   12805         266.8
   BRIGHT REVERB 1    14619         304.6
   PLATE REVERB 1     15119         315.0
   DARK REVERB 2      16719         348.3
   PLATE REVERB 2     16919         352.5
   BRIGHT REVERB 2    17019         354.6
   CONCERT REVERB 2   17409         362.7
   DARK REVERB 1      17419         362.9
   WAVE REVERB 2      21619         450.4
   WAVE REVERB 1      25019         521.2      <- largest, as predicted
```

* **ROOM is the smallest pair and WAVE is the largest pair.** Under a random
  assignment of four families to four rank positions the chance of getting both
  ends right is 1/12 ≈ 0.083.
* The `2` variant is larger than the `1` variant in 4 of 6 families
  (ROOM, PLATE, CONCERT, BRIGHT); DARK and WAVE invert.
* PLATE and CONCERT come out interleaved rather than cleanly ordered.

Not a knock-out, but a real, pre-registered prediction that the data respects at
both extremes. **The values are also physically sane as reverb**: 3–90 ms per
buffer, a 95 ms pre-delay, 8–25 k words of DRAM.

### 2.4 An alternative reading of the same numbers (stated for honesty)

The two chains **overlap in address space** (chain 0 spans 0x513B..0x60CE, which
lies inside chain 1's 0x4000..0x6272), and merging all boundaries gives a single
strictly increasing partition:

```
   0x4000 513B 51E2 52FF 5460 56D1 5A16 5B06 5C06 5DB9 5F0C 60CE 6272
   elementary segments: 4411 167 285 353 625 837 240 256 435 339 450 420
```

so each emitted pair spans **two adjacent elementary segments**. Two ways to
read this:

* **(a) preferred, INFERRED** — two staggered cursors (the chip has `BP1/BP2`
  *and* `PR1/PR2`) over shared multi-tap delay memory, giving 5 + 5 lines. This
  is preferred because it is **corroborated twice independently**: by the 5 + 4
  motif blocks in the code (§1.1) and by the **two 5-gain ladders** in the
  coefficient bank (§3).
* **(b) SPECULATIVE** — 11 elementary buffers, each stage reading a window of
  two. Nothing here excludes it.

---

## 3. TOPOLOGY, cross-checked against the 37-word coefficient bank (MEASURED
layout, INFERRED labels)

CONCERT REVERB 1's type-2 bank, laid out against the structure above:

```
  idx  value                          reading (INFERRED)
   0    +0.250                     }  input scaling / summing.  MEASURED:
   1    +0.500                     }  constant across all twelve presets
   2    +0.500                     }
   3    +0.4656  }
   4    +0.3590  }  triple, one negative -> a 2nd-order section or a
   5    -0.4521  }  one-pole+zero damping filter
   6    +0.500
   7    +0.180
   8    +0.750
   9    +0.630  }
  10    +0.620  }
  11    +0.600  }  ***** LADDER A: 5 monotonically decreasing gains *****
  12    +0.500  }
  13    +0.500  }
  14    +0.2734 }
  15    +0.3573 }  triple, one negative
  16    -0.1829 }
  17    +0.730  }
  18    +0.720  }
  19    +0.700  }  ***** LADDER B: 5 monotonically decreasing gains *****
  20    +0.600  }
  21    +0.500  }
  22    +0.2734 }
  23    +0.3573 }  MEASURED: byte-identical to 14/15/16  -> stereo mirror
  24    -0.1829 }
  25..36  tail / output mix (0.358 0.500 0.493 | 0.600 0.450 0.450 0.450 |
                             0.500 0.321 0.600 | 0.450 0.450)
```

**The cross-check lands exactly.** Two 5-gain ladders ↔ two 5-buffer address
chains ↔ two blocks of motif repetitions in the code. Nothing had to be
massaged to make 5 and 5 come out; the ladders were already published in
`notes/kn5000-dsp-coefficients.md` §4 from the coefficient side alone, before
the address chains were found.

### 3.1 The inferred topology

```
  L,R --> input scale (0.25/0.5/0.5) --> pre-delay 4578 (95 ms)
                                              |
                    +-------------------------+
                    |                                        (INFERRED)
            [ CHAIN 0 : 5 stages ]              [ CHAIN 1 : 5 stages ]
            delays 452 978 1077 691 789         delays 638 1462 496 774 870
            gains  .63 .62 .60  .50 .50         gains  .73 .72 .70 .60 .50
            (LADDER A)                          (LADDER B)
                    |                                        |
                    +-------------- damping triples ---------+
                         (14/15/16 == 22/23/24, stereo mirror)
                                     |
                            output stage, two mirrored 9-word tails
                                     |
                                  L      R
```

* **10 recirculating delay stages in two ladders of 5** — MEASURED counts,
  INFERRED grouping.
* **Series all-pass diffusers rather than parallel combs** — INFERRED, on three
  grounds: (i) monotonically decreasing gains in the 0.5–0.73 band is a
  diffuser schedule, not a comb decay ladder (Schroeder combs sit at 0.7–0.85
  and are *not* ordered); (ii) the delays are not mutually prime (§2.2), which a
  parallel comb bank would require; (iii) the delay buffers are contiguous and
  address-chained, i.e. the stages are cascaded through one arena.
* **Damping inside the loop** — INFERRED from the two mirrored `(+,+,−)` triples
  and from the one-pole poles 0.99996 / 0.99906 / 0.96290 already measured in
  the reverb banks. This is Moorer's/Dattorro's absorbing structure, and it is
  the strongest **topological** parallel with the KN7000, whose reverb also
  embeds unity-DC one-pole+zero damps inside its all-pass and comb loops.
* **Stereo by mirroring at the output**, not by two independent reverbs —
  MEASURED (identical coefficient triples at 14–16 and 22–24; two near-identical
  9-word output tails at 113–121 and 124–130 differing only in `addr8`).

### 3.2 Structural comparison with the KN7000

| | KN5000 (uPD6383GF) | KN7000 (ADSP-21065L) |
|---|---|---|
| pre-delay | 4578 words ≈ 95 ms, chain-1 head | early-reflection lines A/B (1536/3712, 1280/2370) |
| diffusion | **2 ladders × 5 stages**, gains 0.63→0.50 and 0.73→0.50 | 4 series all-passes, all `k = 0.618` |
| damping | mirrored `(+,+,−)` triples; poles 0.99996/0.99906/0.96290 | unity-DC one-pole+zero damps inside allpass G and combs H/I |
| tank | **not identified** — no long (>0.2 s) buffer in the reverb arena | 2 damped combs, 16232 / 14464 (368 / 328 ms) |
| stereo | mirrored coefficient triples + mirrored output tail | sign-flipped wet + 1-vs-257-sample tap |
| presets | 12 presets, one 133-word program, one bank each | 6 records, one program, one DM bank each |

The **absence of a long tank delay** is worth stating plainly. The KN5000's
longest recirculating buffer is 1077 samples (22 ms) in CONCERT REVERB 1 and
4148 (86 ms) in WAVE REVERB 1 — an order of magnitude shorter than the KN7000's
328–368 ms combs. **INFERRED:** the KN5000 builds its tail from **ten short
recirculating stages in series** (a Gardner/Dattorro nested-allpass tank) rather
than from a few long combs, which is the cheaper topology on a chip with one
24×24 multiplier and one external DRAM port.

---

## 4. What did NOT survive contact with the data

* **"The reverb delay lengths are immediates inside the microprogram"**
  (the prediction carried over from `kn5000-dsp-coefficients.md` §8 item 3, by
  analogy with the KN7000's `M7` immediates) — **FALSIFIED**. The repeated
  stages are byte-identical; the lengths are DRAM address pairs in the
  *parameter* stream (§2). The KN7000 analogy failed because the uPD6383GF has
  a dedicated external DRAM controller with address registers, so the delay
  geometry is *configuration*, not *code*.
* **"Reverb taps are mutually prime"** — **NOT SATISFIED** (§2.2). Reported as a
  negative; it also argues against a parallel comb bank and for a diffuser
  cascade.
* **"The motif's varying fields are delay taps and gains"** — the motif has **no
  varying fields at all**. Structure was still recoverable, but from the
  parameter stream, not the instruction fields.
* **PLATE < CONCERT by arena size** — not observed; they interleave (§2.3).

---

## 5. Instruction-class meanings the structure will support

Only claims the structural argument actually carries. Each stage performs
exactly one recirculating delay operation: read the line from external DRAM,
multiply by the stage gain, accumulate, write back.

| word | field reading | claim | status |
|---|---|---|---|
| `880.1.60.2D4` | class 1, `hi12 = 0x880`, `addr8 = 0x60` | **opens the external-DRAM transaction for this stage** (read). Class 1 is the non-memory/control family (encoding note §5) and DRAM is not C-RAM/D-RAM, so a DRAM access must be class 1. `hi12 = 0x880` is the framing family whose only three `addr8` values are 0x20/0x30/0x60. | **INFERRED** |
| `880.1.20.655` | class 1, `addr8 = 0x20` | **closes / performs the write-back half** of the same transaction. Exactly one of each per stage, always in this order, always 4 words apart. | **INFERRED** |
| `102.A.00.64B` | class A (memory-referencing) | **the gain multiply** — the one class-A word in the stage, and the one reverb-exclusive word whose `addr8` actually varies (0x00 → 0xBA at the block-2 head). Ten stages, ten gains, one multiplier. | **INFERRED** |
| `104.2.00.000`, `000.2.00.419`, `012.2.00.680` | class 2 | **accumulate / move between ACCA-ACCB and the delay data buffer.** Which is which is *not* determined. | **SPECULATIVE** |
| `000.2.00.000` | class 2, all operand fields zero | **NOP / pipeline slot.** 273 occurrences across 27 programs — the most widely shared non-trivial word, and it appears as a *pair* at the tail of every stage, where a 24×24 multiply's latency would need covering. | **INFERRED** |
| `612.1.0F.000` | class 1, `addr8 = 0x0F` | end of program. Already **MEASURED** in the encoding note (91/91 final words, 0 false positives). | MEASURED |
| `C40.1.80.000` | class 1, `addr8 = 0x80` | appears only as an adjacent **pair**, twice (111/112 and 122/123), framing the two mirrored output tails. **INFERRED:** serial audio output (`DO1L-R`/`DO1R-R`) or a channel-select. | **INFERRED** |

**Not claimed:** which RAM `addr8` selects, whether the class-2 words are adds
or moves, where the `COND` field is, or how the sign of a coefficient is applied
(the all-pass `+g`/`−g` signature was **not** located in the instruction word —
all ladder gains are positive in the bank, so the inversion, if any, is encoded
in `hi12`/`lo12` and remains undecoded).

---

## 6. Reproducing

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom \
    /tmp/progs
python3 tools/kn5000_dsp_reverb.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom \
    /tmp/progs \
    --names ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom
```

## 7. Next experiments, in order of value

1. **Resolve the 9-stages-vs-10-buffers off-by-one** by decoding words 16–18 and
   64–68 (the block heads). If one of them is a compressed 10th stage the model
   closes exactly.
2. **Settle reading (a) vs (b) of §2.4** — two staggered cursors, or 11
   elementary buffers. The 60-word common header at I-RAM 0..59 (already on disk
   per the encoding note's addendum) contains the external-DRAM setup and should
   say which pointer registers are in play.
3. **Find the sign.** An all-pass needs `+g` and `−g` on the same delay. If the
   inversion is not in the coefficient bank it is in `hi12`/`lo12` of the stage.
   Comparing the reverb stage against the GATED REVERB stage (4 repetitions, a
   *gated* i.e. truncated tail) may isolate it.
4. **Verify against hardware/emulation**: load CONCERT REVERB 1, impulse it, and
   check the echo spacing against 452/978/1077/691/789 and the 95 ms pre-delay.
   That is the test that would convert §2 from INFERRED to MEASURED, and it is
   cheap once the DSP is running.
