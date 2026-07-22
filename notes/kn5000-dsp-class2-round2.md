# NEC uPD6383GF — CLASS 2, round two: the all-pass reframe

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_class2b.py` (imports `kn5000_dsp_extract.py`,
`kn5000_dsp_coeffs.py`, `kn5000_dsp_params.py`, `kn5000_dsp_class2.py`; none of them is
rewritten or edited).

**This file is the append-only successor to `notes/kn5000-dsp-class2.md`, which is left
untouched.** Where the two disagree, this one carries the correction and says so
explicitly. Companions: `notes/kn5000-dsp-reverb.md`,
`notes/kn5000-dsp-parameters.md`, `notes/kn5000-dsp-coefficients.md`,
`notes/kn5000-dsp-encoding.md`, `notes/kn5000-dsp-header.md`.

Every claim is tagged **MEASURED**, **INFERRED** or **SPECULATIVE**. §8 lists what is
falsified or explicitly not established.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_class2b.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
```
Sections: `allpass dataflow order header bands`.

---

## Headline

1. **The all-pass reframe SPLITS.** Its *storage* half is confirmed decisively; its
   *algebra* half is falsified as stated. Round one's "phaser contradiction" is
   dissolved, but not the way the reframe predicted (§1).
2. **NEW ROLE, defended with controls: `880.1.60.xxx` + `880.1.20.xxx` is the
   external-DRAM bracket.** Predicts the DRAM label at **MCC +0.944**, 24 TP, 1 FP,
   0 FN over 38 images, p = 2.6e-9. **The PHASER has neither** — only `880.1.30`.
   (This upgrades a reverb-note INFERENCE to a corpus-wide MEASURED predictor.)
3. **NEW ROLE: `104.2.00.000` is an all-pass marker, not a delay read.** Scored against
   a *pre-registered* all-pass label: MCC +0.881, p = 6.8e-5, and **absent from all 20
   images that do use the external DRAM but have no all-pass** (chorus, flanger, single
   delay, multi-tap delay, vibrato, ensemble, …).
4. **NEW IDIOM (MEASURED): the internal-RAM all-pass section**, a 3-word triple
   `102.2.<c>.1CD / 212.2.01.412 / 104.2.<s>.1D5` with **`c + s == 0xFF`**, occurring in
   exactly **3 of 38 images** — PHASER (18), S.DELAY+PHASER (8), ENHANCER (4) — and
   nowhere else.
5. **★ ENHANCER RESOLVED.** Round one's only image with visibly wrong labels is an
   **all-pass phase-shifter**: it carries the triple, `104.2.00.000` and `082.2.00.1C0`.
   That explains *both* round-one anomalies (its biquad false-negative and its LFO false
   positive) as **label** errors, not predictor errors. Round one's "next experiment 4"
   is closed.
6. **★★ 4-vs-5 BANDS RESOLVED IN FAVOUR OF FIVE, three ways** (§5). The round-one
   CORRECTION ("8 sections = 4 bands") is itself wrong; **10 sections = 5 bands × 2
   channels**, and the "45 coefficients ≈ 5 bands × 3" reading is *also* void.
7. **★★ PROOF BY CONSTRUCTION: the firmware builds class-2 words** (§4). A fourth
   writer, `LABEL_038922`, emits the bit pattern `000.2.00.000` — round one's "NOP" —
   by explicitly setting the `class4` nibble to 2. In the poke family `class4` is
   **constructed as an address-space selector**, MEASURED byte by byte.
8. **NEW PARTITION OF CLASS 2, from ORDER not from bits** (§3): P(previous word is class
   A) is **bimodal**, with values pinned at exactly 1.000 and exactly 0.000 at
   p < 1e-11. Class 2 splits into **P-consumers** (must follow a multiply) and
   **non-consumers**. Round one's "class 2 does not decompose" negative was about
   *bitfields*; it does decompose along the datapath.

---

## 1. ★ THE ALL-PASS REFRAME — verdict: half confirmed, half falsified

The reframe: a phaser is a cascade of all-passes and a reverb diffuser is *also*
all-pass, so a word shared by both is expected if it is an **all-pass primitive**. The
stated prediction was:

> the words implementing the **ALGEBRA** should be COMMON to phaser and reverb, while
> the words implementing the **STORAGE ACCESS** should DIFFER.

### 1.1 The storage half — CONFIRMED, and it generalises (MEASURED)

Prediction, made before looking: if `880.1.60.2D4` / `880.1.20.655` open and close an
**external-DRAM** transaction, then the PHASER — whose all-passes are one-sample and
live in internal RAM — **must not contain any `880.1.60` or `880.1.20` word**, and every
effect that does use the delay memory **must**.

Tool section 1a, all 38 images, `880.1.XX` class-1 words:

```
   PHASER            dram=0   30x2                <-- NO bracket.  PREDICTION HOLDS.
   DISTORTION/FUZZ/OVERDRIVE/EXCITER/COMPRESSOR/
   PARAMETRIC EQ/AUTO PAN/AUTO WAH/PEQ+COMPR*     dram=0   30x2 only
   REVERB x12        dram=1   20x14 30x1 60x13
   GATED REVERB      dram=1   20x9  30x1 60x10
   CHORUS/FLANGER/…  dram=1   20x4  30x1 60x1
   NO OPERATION      dram=0   20x2  30x1 60x3     <-- the one false positive
```

Predictor "contains both `880.1.60` and `880.1.20`" against the DRAM label:
**TP 24, FP 1, FN 0, TN 13, MCC = +0.944, hypergeometric p = 2.6e-9.**

* **MEASURED.** `880.1.30` is present in essentially every program (2× in the no-DRAM
  ones, as prologue/epilogue framing) and carries no information about DRAM.
* **INFERRED, now strong:** `880.1.60.*` opens and `880.1.20.*` closes an external-DRAM
  transaction. The reverb note asserted this from *one* program's internal structure;
  it now survives a 38-image control with a single false positive.
* The false positive is `NO OPERATION`, the 49-word through program — the same image
  that is round one's false positive for the envelope word `0xC40`. **SPECULATIVE:** the
  bypass program still runs the DRAM refresh/framing so the delay memory does not lose
  state while an effect is deselected. Not tested; stated as the weak point.

**So: the storage half of the reframe is confirmed. The phaser's all-passes are not in
the delay memory, and the instruction that proves it is not a class-2 word at all.**

### 1.2 The algebra half — FALSIFIED AS STATED (MEASURED)

If the algebra were storage-independent, the phaser and the reverb should share the
arithmetic words and differ only in the bracket. They do not. Tool section 1b:

```
   880.1.60.2D4   2 images: GATED REVERB, REVERB x12
   104.2.00.000   5 images: ENHANCER, GATED REVERB, PHASER, REVERB x12, S.DELAY+PHASER
   000.2.00.419   2 images: GATED REVERB, REVERB x12
   012.2.00.680   2 images: GATED REVERB, REVERB x12
   880.1.20.655   2 images: GATED REVERB, REVERB x12
   102.A.00.64B   2 images: GATED REVERB, REVERB x12
```

**Only ONE of the six stage words is shared with the phaser.** The reverb's arithmetic
words `000.2.00.419` and `012.2.00.680` and its gain multiply `102.A.00.64B` occur in no
phaser. Conversely the phaser's own all-pass words (§1.4) occur in no reverb.

**MEASURED conclusion: the uPD6383GF has no storage-independent "all-pass algebra"
instruction.** The operand *source* is part of the instruction: reading the delay
memory's data buffer is a different instruction from reading a C-RAM/D-RAM word, so the
whole arithmetic word changes with the storage. **INFERRED**, and it is the reason the
reframe's algebra prediction had to fail — it is a real fact about the ISA, obtained by
stating a falsifiable prediction and having it fail.

### 1.3 What the one shared word IS (INFERRED, with controls)

`104.2.00.000` is the reframe's payoff. **Pre-registered label**, written into the tool
before any membership was printed (`ALLPASS` in `kn5000_dsp_class2b.py`): all-pass-based
effects are, from the effect NAME plus textbook DSP alone,
`{REVERB x12, GATED REVERB, PHASER, S.DELAY+PHASER}`. **ENHANCER is deliberately left
at 0**, making it a possible false positive — the harder test.

```
   members : ENHANCER, GATED REVERB, PHASER, REVERB x12, S.DELAY+PHASER
   TP=4 FP=1 FN=0 TN=33     MCC = +0.881     hypergeometric p = 6.8e-5
```

**THE CONTROL, and it is the decisive one.** If the word were any kind of delay-memory
access it would appear in the effects that demonstrably use the delay memory. The 20
images that carry the DRAM bracket of §1.1 but **lack** `104.2.00.000`:

```
   AUTO WAH+S.DELAY, CHORUS, ENSEMBLE, FLANGER, MIX UP, MODULATED CHORUS,
   MULTI TAP DELAY, PEQ+CHORUS, PEQ+DIST+DELAY, PEQ+FLANGER, PEQ+OVERDR+DELAY,
   PEQ+S.DELAY, PEQ+VIBRATO, ROCK ROTARY, S.DELAY+CHORUS, S.DELAY+FLANGER,
   S.DELAY+S.DELAY, S.DELAY+VIBRATO, SINGLE DELAY, VIBRATO
```

MULTI TAP DELAY is the discriminating case: nothing on this machine reads the delay line
harder, and it does not contain the word.

> **ROLE (INFERRED): `104.2.00.000` is specific to the ALL-PASS topology.**
> Round one's negative — "it cannot mean *read the delay*" — is **correct and is
> upheld**; what the reframe adds is the positive reading it blocked.
> **NOT ESTABLISHED:** which step of the all-pass it is. Its position argues against any
> tidy story: in the reverb motif it sits at `idx+1`, immediately after the DRAM open;
> in the phaser and the enhancer it sits *after* the last section of a chain. Once per
> stage in the reverb (9×), once per chain in the phaser (2×). A "chain terminator"
> reading fits the phaser and not the reverb, and is therefore **not claimed**.

### 1.4 NEW: the internal-RAM all-pass section (MEASURED)

The phaser's chain, read off `algo05.bin` directly (words 12..41):

```
    102.2.45.1CD      102.2.46.1CD   …   102.2.4D.1CD
    212.2.01.412      212.2.01.412       212.2.01.412
    104.2.BA.1D5      104.2.B9.1D5   …   104.2.B2.1D5
    ---- 9 sections, then:
    102.2.4E.1CD / 212.A.B0.412 / 104.2.00.000
```

* **`c + s == 0xFF` for every single section**, in both channels
  (`45/BA … 4D/B2` and `4F/B0 … 57/A8`). Two cursors walking one 256-word space from
  opposite ends, or two mirrored arrays. **MEASURED**; which reading is right is
  **NOT ESTABLISHED**.
* The **last** section of each chain replaces `212.2.01.412` with `212.A.B0.412` /
  `212.A.B1.412` — the *class-A* twin of the same word, with a real address. This is the
  minimal pair round one used to argue about bit 23, now with context: within one
  homogeneous chain, eight sections use the class-2 form and the ninth uses the class-A
  form. **INFERRED:** bit 23 here is not "does a multiply happen" — the section that
  multiplies is structurally identical to the eight that (on that reading) do not.
  This **strengthens round one's own §5 caveat** that bit 23 may select the multiplier
  *operand* rather than enable the multiplier.
* Searched over all 38 images (tool section 1d), the triple with the `c+s == 0xFF`
  constraint occurs in **PHASER (18), S.DELAY+PHASER (8), ENHANCER (4)** and
  **zero times in the other 35 images**, including every reverb.

> **ROLE (INFERRED, strong): this triple is one first-order all-pass section held in
> internal RAM.** Control: it is absent from every DRAM-based effect and from every
> non-all-pass effect. Its address pairs are absent from the phaser's T1 host-parameter
> map, so the `c` values are static coefficients, consistent with the parameters note.

### 1.5 ★ ENHANCER, closed

Round one: *"ENHANCER is the one image whose textbook description this analysis clearly
has wrong"* — the sole false negative of the biquad test and the sole false positive of
the LFO test. **MEASURED from the microcode:** ENHANCER contains four copies of the
all-pass triple (`3E/C1, 42/BD, 48/B7, 4C/B3`), two occurrences of `104.2.00.000`, and
two occurrences of `082.2.00.1C0`, the LFO read.

**An enhancer on this machine is a modulated phase-shifter, not a filter.** So:

* its biquad **false negative is not a miss** — it has no biquad because it has no
  biquad, and round one's `0x647/0x687` predictor is **perfect** on a corrected label;
* its LFO **false positive is not a miss** — it does have a modulator, and round one's
  `0x082` predictor is **perfect** on a corrected label;
* it is a **true positive** for `104.2.00.000`, not a false one, so §1.3's MCC +0.881
  is a floor.

`IMG_CAT[3]` in `kn5000_dsp_class2.py` should read `('ENHANCER', 1, 1, 0, 0)` rather than
`(…, 1, 0, 0, 1)`. That file is round one's and is **not edited here**; the correction is
recorded in this note per the append-only rule.

---

## 2. HOST-WRITE DATA-FLOW CORRELATION — a clean, surprising, honest result

The lever: `notes/kn5000-dsp-parameters.md` proves where the host writes user
parameters (`descriptor + T1[opcode][operand]`, as 8-bit C-RAM/D-RAM addresses). So for
every effect we know which RAM addresses its *user* coefficients land at. Cross-
reference against the `addr8` of its own microcode.

Tool section 2, over all 445 T1 entries in the 38 images:

```
    class-2 addr8 matched :   84   chance expectation  30.3   enrichment x2.77
    class-A addr8 matched :   20   chance expectation  15.9   enrichment x1.26
    occurrence-weighted   :   class 2  111/1550 = 0.072    class A  32/822 = 0.039
```

Two MEASURED facts, both worth stating plainly:

1. **80 % of the addresses the host writes user parameters to (355 of 445) appear as
   `addr8` NOWHERE in that effect's own microcode.** The code does not name its own
   parameter registers. That is exactly what a pointer machine looks like, and it is an
   independent confirmation, from a completely different direction, of round one's §6.2
   ("`addr8` is a displacement off an advancing pointer") and of the reverb note's
   byte-identical stage.
2. **When a host address *is* named, it is named by a class-2 instruction, not a class-A
   one** — 2.77× enrichment versus 1.26×, and 7.2 % vs 3.9 % occurrence-weighted.

Fact 2 is the **opposite** of the naive expectation. If class A is the MAC family, the
coefficient operand should be class A's. The reading that survives:

> **INFERRED:** the class-A MAC takes its coefficient through a **pointer**, while the
> few explicitly-addressed operands — level/mix/feedback scalars written by the host —
> are moved by class-2 instructions. Class 2 is the family that touches named RAM;
> class A is the family that streams through cursors. This is consistent with, and
> sharper than, round one's §5 "class 2 is the non-multiplying datapath".

**A confound that had to be ruled out, and was (MEASURED, negative).** T1 addresses are
*offsets* added to a per-unit relocation base, so a per-image constant `K` might align
them. Sweeping all 256 values of `K` per image, the best `K` lands in `0xE0..0xFF` for
33 of 39 images with apparent z-scores of 3–5. **This is an artefact and is rejected**:
88 % of all `addr8` values already lie in `0x00..0x10 ∪ 0xF0..0xFF` (round one §6.2), so
any small negative `K` drags T1's small values into the dense band. **No relocation base
is recoverable this way**, and the numbers above are reported at `K = 0`.

Per-effect extremes (tool section 2): `REVERB x12`, `PARAMETRIC EQ`, `PEQ+OVERDR+DELAY`,
`DISTORTION` and `FUZZ` name **zero** of their host addresses; `AUTO WAH` (4 of 9),
`EXCITER` (4 of 10) and `S.DELAY+FLANGER` (6 of 22) name the most. **INFERRED:** the
programs with the most regular repeated structure are exactly the ones that use pure
pointer walking — which is the same cancellation round one's §6.4 identified.

---

## 3. ★ SEQUENCE STRUCTURE — class 2 DOES decompose, along the datapath

Round one measured distributions. A datapath also imposes **order**: whatever consumes
the multiplier product `P` must sit immediately after a multiply. Tool section 3
computes, for every `hi12` and `lo12` value of class 2, P(the previous instruction is
class A). Baseline **0.309**.

```
  hi12    n   P(pred=A)   binomial p
  082    64     1.000      2.1e-33     MUST-FOLLOW-A
  182    54     1.000      2.7e-28     MUST-FOLLOW-A
  204    50     0.920      1.8e-19     MUST-FOLLOW-A
  202    55     0.836      8.1e-16     MUST-FOLLOW-A
  C40    12     1.000      7.4e-07     MUST-FOLLOW-A
  020     9     0.778      5.1e-03
  092    48     0.333      4.1e-01     (indifferent)
  012    71     0.000      4.2e-12     NEVER-FOLLOWS-A
  02A    40     0.000      3.9e-07     NEVER-FOLLOWS-A
  026    26     0.000      6.8e-05     NEVER-FOLLOWS-A
  028    18     0.000      1.3e-03     |  the whole 0x02x family
  02E    15     0.000      4.0e-03     |  is at exactly zero
  022    15     0.000      4.0e-03     |
  0A2     8     0.000      5.2e-02     |

  lo12    n   P(pred=A)   binomial p
  647    38     0.895      7.7e-14     MUST-FOLLOW-A
  687    43     0.814      1.1e-11     MUST-FOLLOW-A
  447    49     0.776      2.3e-11     MUST-FOLLOW-A
  1C0   100     0.640      9.2e-12
  1CE    87     0.000      1.2e-14     NEVER-FOLLOWS-A
  40E    78     0.000      3.2e-13     NEVER-FOLLOWS-A
  419    44     0.000      8.9e-08     NEVER-FOLLOWS-A
  412    30     0.000      1.6e-05     NEVER-FOLLOWS-A
  415    23     0.000      2.1e-04     NEVER-FOLLOWS-A
  680    22     0.000      3.0e-04     NEVER-FOLLOWS-A
  1D5   107     0.131      1.6e-05     (depleted)
  000   461     0.332      1.5e-01     (indifferent, as a NOP must be)
```

**MEASURED: the statistic is bimodal.** Values sit at *exactly* 1.000 or *exactly*
0.000, never near the 0.309 baseline except for the generic ones. With n = 64 and
P = 1.000 the binomial p is 2e-33; with n = 87 and P = 0.000 it is 1e-14. This is not a
weak trend.

> **INFERRED: class 2 partitions into P-CONSUMERS and NON-CONSUMERS.**
> The MUST-FOLLOW-A group takes the product of the immediately preceding multiply — an
> accumulate, a shift-and-store, a saturate. The NEVER-FOLLOWS-A group cannot, and is
> pure addressing / data movement / control.

**Controls and consistency checks, all of which pass:**

* The **NOP** `lo12 = 0x000` sits at 0.332 ≈ baseline (p = 0.15). A word with no
  datapath role must be order-indifferent, and it is. Had `000` come out at 1.000 or
  0.000 the whole partition would be a positional artefact.
* `0x647` and `0x687` — round one's **biquad** state/output words — are both
  MUST-FOLLOW-A (0.895 / 0.814). They sit after five consecutive MACs and must consume
  the accumulated result. **Independent corroboration of round one §4.2 from a
  statistic round one never computed.**
* `hi12 = 0x082` — round one's **LFO read** — is MUST-FOLLOW-A at **exactly 1.000, 64/64**.
  Round one described "a three-word LFO idiom of which the class-2 word is the
  non-multiplying middle" preceded by a class-A word with `hi12 ∈ {092,192}`. The order
  statistic reproduces that with no exceptions.
* `hi12 = 0xC40` — round one's **envelope detector** — is 12/12 MUST-FOLLOW-A, matching
  its "always preceded by `104.A.00.1D5`" rigidity.
* The `0x02x` `hi12` family — the one round one's §3.1 tried and failed to split into
  `U/V/W` bitfields — is at **exactly 0.000 for all five of its values with n ≥ 8
  (`022, 026, 028, 02A, 02E`), 114 occurrences, not one exception**.
  Round one could not separate it by bits; order separates it cleanly. **The two results
  are compatible: class 2 has no separable bitfields (round one, MEASURED) but does have
  a datapath-imposed partition (here, MEASURED).**

**NOT ESTABLISHED:** whether "consumes P" means accumulate, store, or saturate; and
whether the partition is binary or graded (`0x1C0` at 0.640 and `0x1D5` at 0.131 are
genuinely intermediate, and are not classified).

---

## 4. ★★ PROOF BY CONSTRUCTION — the firmware builds a class-2 word

`notes/kn5000-dsp-parameters.md` §2 found three writers (`LABEL_0387E6`, `LABEL_03846C`,
`LABEL_038539`) constructing `801.0.NN.821` and `000.1.NN.000`. It listed a **fourth**,
`LABEL_038922` (the writer for opcode `0x68`, whose eval helper `LABEL_03925E` is the
`ms × 44100/1000` delay converter), but never decoded it. Here it is, sub-CPU v1.42
disassembly lines 45660–45805, **MEASURED byte by byte**:

```
    DispatchCommand(1)                                     ; record command byte
    DispatchData(0)                                        ; preamble 1
    DispatchData(V) ; V++                                  ; preamble 2  (address cursor)

    if  (arg @ XSP+012h) != 0x63:                          ; --- word 1, branch A
        0x00, 0x00, (D>>4)&0x0F, (D<<4)&0xF0, 0x00         ; D = XSP+010h + XSP+008h
    else:                                                  ; --- word 1, branch B
        0x00, 0x00, 0x20,       0x00,        0x00

    if  (arg @ XSP+006h) == 0:                             ; --- word 2, branch A
        0x08, 0x00, 0x80, 0xB4, 0x07
    else:                                                  ; --- word 2, branch B
        0x0C|((V>>7)&2), (V>>7)&1, (V<<1)&0xFF, 0x04, 0x07
```

Decoded with the established field map (`hi12.class4.addr8.lo12`, low 36 bits of the
5-byte group — verified against the parameters note's `801.0.NN.821` recipe, which this
decode reproduces exactly):

| emitted bytes | word | note |
|---|---|---|
| `00 00 (D>>4)&F (D<<4)&F0 00` | **`000.0.DD.000`** | `DD = D & 0xFF`, an 8-bit RAM address; `class4 = 0` |
| `00 00 20 00 00` | **`000.2.00.000`** | `class4 = 2`, address 0, everything else zero |
| `08 00 80 B4 07` | `800.8.0B.407` | cf. header word I-RAM 47 = `800.8.0C.000` |
| `0C.. .. 04 07` | `hi12/class4/addr8` all carry bits of `V` | the tap/address cursor |

**Three things this proves outright, beating any inference in these notes:**

1. **`class4` in the poke family is CONSTRUCTED as an address-space selector, not as an
   opcode class.** The four writers differ in exactly that nibble: `LABEL_0387E6` emits
   `class4 = 0` (`801.0.NN.821`), `LABEL_03846C`/`LABEL_038539` emit `class4 = 1`
   (`000.1.NN.000`, via `0x10 | ((A>>4)&0xF)`), and `LABEL_038922` emits `class4 = 0`
   *or* `class4 = 2` from two branches of one routine. **MEASURED.** Combined with the
   parameters note's "two address spaces — C-RAM and D-RAM", there are **at least
   three** selectable targets, and the third one is selected by `class4 = 2`.
2. **The bit pattern `000.2.00.000` is emitted deliberately by firmware**, as
   "space 2, address 0, no payload", in the branch where the routine has *no address to
   send*. Round one and the reverb note both inferred that word to be a NOP / idle
   pipeline slot from position and field-emptiness alone. **This is a mechanism for that
   inference**, and §3 adds a third independent line: `lo12 = 0x000` is the one common
   value that is order-*indifferent* (P = 0.332 vs baseline 0.309, p = 0.15). Three
   independent arguments, one conclusion.
3. **A cross-link to the header.** The header contains `C0A.2.92.820` — `lo12 = 0x820`,
   one below the proven pointer-load `801.0.NN.821`, with `class4 = 2` and an 8-bit
   address `0x92`. Read through (1) this is *the same pointer-load, aimed at the third
   address space*. **INFERRED**, and it is the only reading of a header class-2 word
   this project has.

**Honest scope limit.** All of this is proven for the **host-poke word population**. It
does *not* automatically transfer to the effect-body instruction stream, where the same
nibble position is the "class" this whole line of work is named after. Whether the body
words' `class4` is also an address-space selector is **NOT ESTABLISHED** — but it is now
the leading hypothesis, and it would explain, at a stroke, why class 2 refuses to
decompose into control bitfields (§3.3 of round one) while behaving as two coupled
enumerations: *the word is an operation code plus a memory selector, not a horizontal
microword.*

---

## 5. ★★ THE 4-vs-5 BAND CONTRADICTION — resolved, in favour of FIVE

Round one claimed the PARAMETRIC EQ's 9-word biquad section repeats **10×** (5 bands ×
2 channels). Its own appended CORRECTION measured only **8** byte-identical repetitions
and concluded "4 bands × 2 channels", flagging the coefficient note's "45 registers ≈ 5
bands × 3" as an unresolved disagreement.

**Both are wrong, and the resolution is clean.** Relaxing "byte-identical" to "differs in
exactly one word" (tool section 5):

```
   byte-identical 9-word sections : 8   at [5, 14, 23, 32, 59, 68, 77, 86]
   sections differing in ONE word : 2
       start 41   word 8 is 000.2.AD.647   (reference 000.2.03.647)
       start 95   word 8 is 880.1.30.647   (reference 000.2.03.647)

   => 10 sections = 5 BANDS x 2 CHANNELS
```

The sections are at 5, 14, 23, 32, **41** | 59, 68, 77, 86, **95** — two contiguous runs
of **five**, not two groups of four with a gap. The gap round one saw *is* the fifth
section: its final word carries a different `addr8` (`0xAD` instead of `0x03`, i.e. the
end-of-bank cursor rewind) in channel 0, and is promoted to a class-1 word
(`880.1.30.647`) in channel 1 where the program is about to end. **MEASURED.** Note
that `lo12 = 0x647` — the biquad word — is preserved in all ten.

**Two fully independent confirmations of "five", from the host side (MEASURED):**

* **T2, the parameter bytecode stream: 17 records, of which 15 are
  `70:00 70:00 70:00 70:01 70:01 70:01 70:02 70:02 70:02 70:03 70:03 70:03 70:04 70:04
  70:04`** — **five operand groups of three parameters each**. Five bands × (frequency,
  Q, gain). The remaining two records are the universal `63:00` and `21:00`.
* **T1, the opcode → address map: `op 70 -> 00 06 0C 12 18 | 64 68 6C 70 74`** —
  **five addresses at stride 6 and five at stride 4**. **INFERRED:** a 6-word
  coefficient block and a 4-word state block per band, five bands, one channel's worth.

So the microcode, the parameter stream and the address map all say **five**, and the
round-one correction's "four" was an artefact of demanding byte-identity.

**And the "45 coefficients" argument is void in both directions (MEASURED).** The
PARAMETRIC EQ's static coefficient bank is **45 values of which 43 are exactly zero**
(the only non-zeros are `0x000040` and `0x004000` at indices 43 and 44). It is a
**zero-fill of the biquad coefficient+state area**, not a set of band coefficients —
which fits 5 × (6 + 4) = 50 words of scratch far better than any "5 × 3" reading, and
which is why the number could never be made to factor. `notes/kn5000-dsp-coefficients.md`'s
"45 registers ≈ 5 bands × 3" reached the right band count by the wrong route.

**This makes PARAMETRIC EQ the best-understood program on this chip**: 5 bands × 2
channels of second-order sections, five class-A MACs each (b0, b1, b2, a1, a2), the two
class-2 words `0x687`/`0x647` consuming the result, coefficients at
`base + 6k`, state at `base + 4k`, and a UI of 15 parameters in five groups of three.

---

## 6. THE HEADER'S CLASS-2 WORDS — a free partition (MEASURED)

The 60-word common header (`notes/kn5000-dsp-header.md`; ROM `0x01E496`) contains 16
class-2 words, in a control/IO context the effect bodies never show. Tool section 4:

```
  092.2.01.20D   084.2.02.680   012.2.FF.1CE   204.2.02.1CE
  084.2.01.1C0   012.2.FF.1D5   400.2.01.447   282.2.00.000
  C0A.2.92.820   512.2.00.44D   692.2.00.415   000.2.00.2D9
  012.2.01.655   504.2.00.1D5   000.2.01.007   000.2.01.000

  hi12 shared with bodies : 000 012 092 204 282
  hi12 HEADER-ONLY        : 084 400 504 512 692 C0A
  lo12 shared with bodies : 000 1C0 1CE 1D5 415 447 44D 655 680
  lo12 HEADER-ONLY        : 007 20D 2D9 820
```

* **INFERRED:** the 5 shared `hi12` and 9 shared `lo12` values are generic data
  movement; the 6 + 4 header-only values are control / IO / DRAM-controller setup, the
  vocabulary the effect bodies have no reason to contain.
* **★ A CORRECTION TO THE REVERB NOTE.** It reports `880.1.20.655` and `012.2.00.680` as
  "reverb-exclusive words". The *words* are; the `lo12` values are **not** —
  `012.2.01.655` and `084.2.02.680` are both in the header, one of them (`…655`)
  differing from the reverb's only in `hi12` and `addr8`. **MEASURED.** The exclusivity
  belonged to the whole 36-bit word, and any future decode must not treat
  `lo12 = 0x655/0x680` as reverb semantics.
* `000.2.01.000` and `012.2.01.655` are the only two header class-2 words that occur
  *exactly* in the bodies, which is the quantitative form of the same point: the header
  and the bodies barely overlap at the word level (2 of 16) but overlap heavily at the
  `lo12` level (9 of 13).
* `C0A.2.92.820` is discussed in §4 item 3.

---

## 7. Corrections this note makes to earlier notes

| earlier claim | source | status here |
|---|---|---|
| the biquad section repeats **8×** = 4 bands × 2 ch | class2 note, CORRECTION | **REFUTED (§5)**: 10 sections = 5 bands × 2 ch; T1 and T2 agree independently |
| "45 registers ≈ 5 bands × 3" | coefficients note | **VOID (§5)**: 43 of the 45 are zero; it is a scratch zero-fill. Right answer, wrong reason |
| `104.2.00.000` cannot be decoded because the phaser has no delay line | class2 note §7 | **UPHELD as a negative, SUPERSEDED as a dead end (§1.3)**: it is an all-pass marker |
| ENHANCER's category labels are wrong, unresolved | class2 note §4.2/§4.3/§10.4 | **RESOLVED (§1.5)**: it is an all-pass phase-shifter with an LFO; both round-one predictors are perfect on the corrected label |
| `lo12 = 0x655 / 0x680` are reverb-exclusive | reverb note §1.2 | **CORRECTED (§6)**: both occur in the common header; only the full words are exclusive |
| `880.1.60` / `880.1.20` open/close the DRAM transaction | reverb note §5, INFERRED from one program | **UPGRADED (§1.1)**: 38-image control, MCC +0.944, p = 2.6e-9 |
| `000.2.00.000` is a NOP | reverb note §5 / class2 note §2, INFERRED | **CORROBORATED THREE WAYS (§3, §4)**: firmware constructs it; order-indifferent at p = 0.15 |
| class 2 does not decompose | class2 note §3, MEASURED | **STANDS for bitfields; DOES decompose by datapath order (§3)** |
| bit 23 = multiplier enable | class2 note §5, INFERRED | **WEAKENED (§1.4)**: within one phaser chain, 8 sections use the class-2 form and the 9th the class-A form of the *same* word |

---

## 8. Falsified, or explicitly not established

* **"The all-pass ALGEBRA words are common to phaser and reverb."** **FALSIFIED (§1.2).**
  Only 1 of the 6 reverb-stage words reaches the phaser. The ISA has no
  storage-independent all-pass instruction.
* **"A per-image relocation offset K aligns the T1 addresses with the microcode."**
  **REJECTED as an artefact (§2)** of the `addr8` clustering near zero.
* **"Coefficient operands are class-A operands."** **NOT SUPPORTED (§2)**: the
  enrichment is 2.77× for class 2 and 1.26× for class A.
* **The exact step `104.2.00.000` performs** — its position is inconsistent between the
  reverb (per stage, after the DRAM open) and the phaser (per chain, after the last
  multiply). No reading is claimed.
* **Whether `c + s == 0xFF`** in the phaser means one mirrored array or two arrays.
* **Whether body-word `class4` is an address-space selector** like the poke words'
  (§4). Leading hypothesis; not established.
* **What "consumes P" means** for the MUST-FOLLOW-A group, and the intermediate values
  `lo12 = 0x1C0` (0.640) and `0x1D5` (0.131).
* **The `NO OPERATION` false positive** for the DRAM bracket (§1.1) and for `0xC40`
  (round one §4.4) — the same program fails both controls and is unexplained.
* **Still unknown, unchanged from round one:** which of C-RAM/D-RAM `addr8` selects,
  which of `0x647`/`0x687` is the state shuffle vs the output store, where the COND
  field is, and the meaning of the remaining ~20 `hi12` and ~20 `lo12` values.

## 9. Next experiments, in order of value

1. **Test the "class4 = address space" hypothesis on the body words** (§4). It is now
   the single highest-value question. Concretely: if `class4` selects a memory, then for
   a fixed `(hi12, lo12)` the class should co-vary with which RAM the operand lives in.
   The `212.2.01.412` / `212.A.B0.412` minimal pair inside one phaser chain (§1.4) is the
   cleanest test bed in the corpus.
2. **Decode the phaser all-pass numerically.** Its 18 coefficient addresses are static
   (`PARAM_TABLE`, not T1); read them out, check they are realisable all-pass gains, and
   check the two chains against `SWEEP RANGE`/`PHASE` in the parameter name table. That
   would convert §1.4 from INFERRED to something near proven, exactly as §5 did for
   the EQ.
3. **Apply §3's ordering statistic to class A**, which was not done here. If class A
   splits the same way, the P-consumer/producer structure is a property of the machine
   and not of class 2.
4. **Re-run round one's §4 semantics scoring with the corrected ENHANCER label** (§1.5)
   and with a fifth category `allpass`. Three of round one's four role assignments have
   ENHANCER as their sole error; correcting one label may make all three exact.
5. **Find the third address space.** §4 proves `class4 ∈ {0,1,2}` selects three poke
   targets. The CDJ-500 block diagram offers C-RAM, D-RAM and the external-DRAM
   address/data registers. Which is which should be decidable from *which* parameters
   each writer serves — `LABEL_038922` serves opcode `0x68`, the **milliseconds → DRAM
   words** helper, which points hard at the third space being the delay controller.
