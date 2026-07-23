# NEC uPD6383GF — NAMING every class-A multiply's coefficient (the C-RAM ⋈ host join)

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-23.
Tool: `tools/kn5000_dsp_namedcoeff.py` (imports `_class2` / `_params`; **neither edited,
no audio, the core stays DISABLED**).

The lever that made this pass possible and was absent from `-paramsemantics.md`: the
disassembler now emits an **absolute** C-RAM address on every class-A word
(`-spaces.md` JOB 1, base 0x00 MEASURED, +1 per class-A). Joined to the host's own
per-effect coefficient map (`-parameters.md` T1, `-cursor-general.md` the reverb/biquad
decode), each multiply's coefficient cell gets a **name / role**:

```
   class-A multiply  ->  C-RAM[base + k]  ->  host T1: which OPCODE wrote that cell
                     ->  the opcode's ROLE / the effect's NAMED coefficient
```

Claims tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED**, **SPECULATIVE**.
The caveat of the brief is respected throughout: **"role known" (from the named
coefficient) is kept DISTINCT from "operation known" (forced by dataflow)**. §6 is misses.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_namedcoeff.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom
# sections: biqctl table coverage neighbours unknowns
```

---

## Headline

1. **★★ THE BIQUAD-ORDER CONTROL PASSES (validate-the-join-first).** In PARAMETRIC EQ
   the class-A words at C-RAM `0x00..0x05` are the SOLVED biquad section words **in the
   right order** `b1, b0, b2, -a1, -a2, makeup` — 6/6, byte-exact against `-semantics.md`
   §3.1. The join is not mis-ordering the coefficients, so it is trustworthy. **MEASURED.**
2. **★★ 391 of the 822 class-A multiplies now carry a NAMED coefficient — 47.6 %**
   (was 0 named; the previous pass could pin only *arrays*). Of those, **255 are PROVEN**
   (the solved biquad/reverb/compressor) and 136 INFERRED (opcode role). The whole
   PARAMETRIC EQ (60/60) and the whole reverb (33/33) are named; EXCITER 18/22, SINGLE
   DELAY 13/18, the PEQ-combos 13–22 each. §2.
3. **★ Two frequent UNDECODED class-A families gained a firm operand ROLE** (present-AND-
   absence, ≥ 97 %): `202.A.*.415` = a **mix/tap** gain (39 named of 42, 97 %) and
   `102.A.*.64B` = the **reverb diffuser decay** gain (9/9, 100 %). §4.
4. **★ Neighbour propagation CONFIRMS the biquad's two class-2 stores by role across the
   whole corpus** (not one fit): `102.2.*.687` follows an EQ multiply 30/30 (100 %) and
   `000.2.*.647` 29/29 (100 %) — the DF-I `acc+=P;S3←B` and `acc←P;S1←A` of `-semantics.md`,
   now pinned by present-and-absence. Two damping neighbours (`212.A.*.415`, `202.2.*.407`)
   follow a damping multiply 100 %. §3. **No NEW opcode was dataflow-FORCED** — these are
   confirmations + role assignments, kept honestly distinct from a full decode (§5, §6).
5. **A join hazard was found and fixed before it inflated the score.** T1 records are
   0x00-**padded** to a fixed width (`op0x74 = "1D 00 00 00"`); those padding zeros were
   falsely claiming C-RAM`0x00`, minting a bogus "input/tone" role on ~19 multiplies
   (the LFO-phase `092.A`/`094.A` words). Dropping 0x00 at operand-index > 0 removed the
   entire spurious role — 410→391 named, and `092.A`/`094.A` correctly read **never named**
   now. **This is the instrument-blindness the brief warned about, caught and corrected.**
6. **The disassembler was NOT edited.** The names are **effect-contextual** (they need the
   per-effect T1 join) and **role-level**, not operation-level; per the caveat a role must
   not be laundered into a generic opcode mnemonic. Coverage stays **18.3 %** — nothing new
   is a full word decode. §5.

---

## 1. The positive control — biquad coefficient ORDER (MEASURED)

```
  C-RAM[0x00] =      b1  word 000.A.00.1D3   OK
  C-RAM[0x01] =      b0  word 212.A.01.412   OK
  C-RAM[0x02] =      b2  word 202.A.01.1D5   OK
  C-RAM[0x03] =     -a1  word 202.A.01.1D4   OK
  C-RAM[0x04] =     -a2  word 202.A.00.1D5   OK
  C-RAM[0x05] =  makeup  word 212.A.FF.407   OK      -> biquad-order control: PASS
```

The cursor hands the six biquad cells to the six class-A words of the section in exactly
the Direct-Form-I order the constraint search fixed. Had the join mis-ordered them (e.g.
counted bit-23 words instead of class-A, which would mis-place the make-up gain), this
control would fail. It passes on every band of every PEQ-bearing image (§2 shows PEQ 60/60).

## 2. The named-coefficient table + coverage (MEASURED / PROVEN / INFERRED)

`host_coeff_map` builds, per effect, `C-RAM address → (opcode, operand, cell)` from the
T1 map restricted to the **+0 (C-RAM coefficient) writers**, with the multi-cell
coefficients EXPANDED: **op0x70 → 6 cells/band** (b1..makeup), **op0x76 → 3 cells/entry**
(the damping filter, `-cursor-general.md` §6). The reverb (the only unit-1 image) is
named from its **fully-decoded bank** (`-cursor-general.md` §3.2/3.3): input-scaling
`0x90..92`, three damping triples `0x93/9E/A6`, the two diffuser ladders `0x98..9C` /
`0xA1..A4` (REVERB TIME), the L/R output tails `0xA9..B0` (ER.LEVEL / mix).

```
  class-A words in corpus (38 images) : 822
  NAMED (land on a host +0 coeff cell): 391   (47.6 %)     PROVEN 255 / INFERRED 136
  unnamed                             : 431

  named by ROLE:  EQ 180   mix/tap 82   damping 45   coeff 29   output-level 19
                  decay 13   mix 8   gain-computer 6
```

Fully-named effects: **PARAMETRIC EQ 60/60**, **reverb 33/33**. High: EXCITER 18/22,
ENHANCER 18/26, SINGLE DELAY 13/18, PEQ+combos 13–22 each. Low where coefficients are
**block-uploaded** by a wide opcode (0x24/0x77/0x73/0x6B/0x6C) rather than individually
T1-addressed — CHORUS 3/19, COMPRESSOR 1/10, RING MODULATOR 1/6 — those cells are still
absolute-addressed by the cursor, just not individually named by the host map (§6).

Role legend (evidence):
```
  EQ            op0x70   biquad coefficient                        PROVEN (semantics.md)
  damping       op0x76 / reverb triples   HIGH DAMP GAIN filter    PROVEN (cursor-general 6)
  decay         reverb ladder / op0x75    REVERB TIME diffuser     PROVEN (cursor-general 3.2)
  output-level  op0x21 -> 0x90            VOLUME, 0..0.8 dB law     PROVEN (parameters 5)
  gain-computer op0x72                    THRESHOLD/RATIO           PROVEN (paramsemantics 3)
  mix / input-gain / mix/tap  op0x66 / reverb tails                INFERRED (eval helper + reverb)
  coeff         other +0 writers                                   INFERRED
```

## 3. Neighbour propagation — the P-consumer that follows a named multiply

For every named multiply of role X, tally the **(hi12,cl,lo12) of the following word**.
A following family dominated by one predecessor-role is that role's accumulate/store.
Present-AND-absence across ALL effects (n = distinct occurrences):

```
  following word   n    dominant predecessor-role   verdict
  102.2.687       30    EQ            100%           biquad acc+=P;S3<-latch B   [PINNED]
  000.2.647       29    EQ            100%           biquad acc<-P;S1<-latch A   [PINNED]
  212.A.412       28    EQ             96%           (the biquad b0 word itself) [PINNED]
  202.A.1D4       28    EQ             96%           (the biquad -a1 word)       [PINNED]
  212.A.415       10    damping       100%          damping accumulate          [PINNED]
  202.2.407        9    damping       100%          damping store               [PINNED]
  204.2.1CD       23    mix/tap        83%           follows a mix/tap multiply
```

**`102.2.687` and `000.2.647` are exactly the biquad's two class-2 stores** already
decoded by the exhaustive constraint search (`-semantics.md` §3.1, words `[5]` and `[8]`).
Here they are re-confirmed **from a completely different direction** — by the ROLE of the
product they consume, over 30/29 instances spread across every PEQ-bearing effect, with a
clean absence elsewhere. That is the present-and-absence control the rules demand, and it
turns the biquad's two folded stores from "unique constraint-search survivor" into
"pinned by cross-effect dataflow". The damping pair (`212.A.415`, `202.2.407`) are the
analogous accumulate/store of the 3-word damping filter, now **role-known** (100 %).

## 4. Frequent UNKNOWN words — the operand ROLE of their coefficient

For each frequent class-A family, the role of its **named** coefficient across effects.
A family whose coefficient is consistently one role gains that operand role:

```
  class-A family   occ  named   dominant coeff-role      verdict
  202.A.*.415       42    39     mix/tap        97%      ROLE = output/tap mix gain  [ROLE]
  102.A.*.64B       16     9     decay         100%      ROLE = reverb diffuser gain [ROLE]
  212.A.*.412       42    28     EQ             96%      (biquad b0 -- already decoded)
  202.A.*.1D4       35    28     EQ             96%      (biquad -a1)
  212.A.*.407       35    30     EQ            100%      (biquad make-up = mulst)
  000.A.*.1D3       28    25     EQ             96%      (biquad b1 = mac)
  212.A.*.415       11    10     damping       100%      ROLE = damping tap gain     [ROLE]
  000.A.*.1D5       53    11     damping        82%      (mostly damping; below thresh)
  092.A.*.200       29     0     (never named)           the LFO phase word -- unnamed (correct)
```

**Two genuinely new operand-role decodes** (neither was previously named), each with a
clean cross-effect control:

* **`202.A.*.415` = a mix/tap gain** (97 % over 39 named instances). This is one of the
  ranked undecoded families of `-core-draft.md`; its coefficient is now known to be an
  **output/tap mix level**, never a filter or feedback coefficient. **ROLE KNOWN** — the
  exact class-A micro-op is the usual `mac`-family, but the operand's *meaning* is fixed.
* **`102.A.*.64B` = the reverb diffuser decay gain** (100 %). This is the reverb note's
  `102.A.00.64B` "the gain multiply — ten stages, ten gains" (`-reverb.md` §5); the join
  now labels its operand **REVERB TIME-derived decay** directly from the bank slots
  `0x98..0x9C` / `0xA1..0xA4`. **ROLE KNOWN**, corroborating the reverb decode.

`092.A`/`094.A` (the LFO phase accumulator, 29 occ. each) are correctly **never named** —
their operand is not a host coefficient at all; the padding-zero fix (§Headline 5) removed
the false claim that had briefly named them.

## 5. Role known vs operation known — the honest ledger

| result | kind | count / note |
|---|---|---|
| every biquad band cell named `b1..makeup` in order | operation known (already) + name | 60/60 PEQ, control PASS |
| whole reverb bank named (ladders/damping/tails/input) | role known (PROVEN slots) | 33/33 |
| `102.2.687`, `000.2.647` = biquad DF-I stores | operation known (already) — now **pinned by role** | 30 / 29, 100 % |
| `212.A.415`, `202.2.407` = damping accumulate/store | **role known** (100 %) — op not forced | 10 / 9 |
| `202.A.415` = mix/tap gain | **role known** (97 %) | 39 |
| `102.A.64B` = reverb decay diffuser | **role known** (100 %) | 9 |
| 391 class-A multiplies overall | **named coefficient** (role) | 47.6 % |

**No neighbour operation was newly dataflow-FORCED into a full opcode.** The two class-2
words that ARE fully decoded (`…687`, `…647`) were already decoded in `-semantics.md`; this
pass strengthens their evidence to present-and-absence but does not add a new opcode. Every
other gain is **role-level**. Therefore **honest source coverage is unchanged at 18.3 %
(545/2974)** — a validated coefficient role is not a full word decode, and this series does
not launder one into the other. What is genuinely added: an absolute, named coefficient on
391 of 822 multiplies, and firm operand roles on two frequent undecoded families.

## 6. Misses, limits, what remains

* **431 class-A multiplies remain unnamed** — chiefly where the coefficient bank is
  **block-uploaded** by a wide opcode (0x24 imm 19, 0x77 imm 46, 0x73/0x6B/0x6C imm 14)
  instead of the individually-addressed +0 writers the join reads. The cursor still gives
  each an absolute C-RAM cell; naming them needs those block opcodes' internal layout
  decoded (`-parameters.md` §10 "four large opcodes"). This is the next lever.
* **The mix/input/tap roles (op0x66) are INFERRED**, not PROVEN — op0x66's eval helper is
  fixed but its *meaning* is read from the reverb output-tail context and the paramlist,
  not forced. `202.A.415`'s 97 % is strong but not 100 %.
* **The reverb overlay is a per-slot table** (PROVEN by `-cursor-general.md`), applied only
  to the one unit-1 image; it is not a generic mechanism.
* **`092.A`/`094.A` unnamed is a *correct* miss**, not a failure — their operand is the LFO
  phase, not a host coefficient.
* **Predict-then-check honesty:** the brief anticipated "role known" on ~822 multiplies;
  the achievable figure with the individually-addressed host map is **391 (47.6 %)**, and
  the shortfall is a *measured* fact about block-uploaded coefficients, reported here as
  prominently as the hits.
* **All static.** One C-RAM address-bus trace from the enabled core would confirm base 0x00
  / 0x90 and the per-effect bank layout directly.

## 7. Cross-checks to earlier notes

| earlier claim | source | status here |
|---|---|---|
| C-RAM absolute address on every class-A word | `-spaces.md` JOB 1 | **CONSUMED as the join key**; the biquad-order control validates it end-to-end |
| the chain works on *arrays*, not scalars, until the origin is pinned | `-paramsemantics.md` §5 | **EXTENDED**: the C-RAM (coefficient) side needs no D-RAM origin — its base is MEASURED — so scalars ARE nameable on the coefficient side (VOLUME 0x90, op0x75 decay), unlike the D-RAM-state side |
| biquad `[5]`/`[8]` are the two folded class-2 stores | `-semantics.md` §3.1 | **RE-CONFIRMED by role**, present-and-absence 30/29 across effects (§3) |
| reverb `102.A.00.64B` = the diffuser gain multiply, gains 0x98..0x9C/0xA1..0xA4 | `-reverb.md` §5, `-cursor-general.md` §3.2 | **NAMED**: its operand role = REVERB TIME decay, 100 % (§4) |
| op0x74 → "1D 00 00 00" | `-parameters.md` §5 | **the 00s are padding** — a join hazard, filtered (§Headline 5) |
| coverage 18.3 % | `-hi12.md` | **UNCHANGED** — roles are not full decodes |
