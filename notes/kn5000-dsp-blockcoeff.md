# NEC uPD6383GF — decoding the BLOCK-UPLOAD coefficient opcodes (the C-RAM join, level 2)

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-23.
Tool: `tools/kn5000_dsp_blockcoeff.py` (imports `_class2`, `_params`, `_namedcoeff`;
**none edited, no audio, the DSP core stays DISABLED**).

Successor to `-namedcoeff.md`, which named 391/822 class-A multiplies by joining each
multiply's absolute C-RAM cursor address to the host's **individually-addressed** T1
coefficient writers, and concluded that the remaining 431 were chiefly where the bank is
**block-uploaded** by a wide opcode. This note decodes those block layouts from the
sub-CPU v1.42 writers and folds them into the join.

Claims tagged **MEASURED / PROVEN BY CONSTRUCTION / INFERRED / SPECULATIVE**. §6 = misses.
"role known" (from the named coefficient) is kept DISTINCT from "operation known"
(dataflow-forced), exactly as in `-namedcoeff.md`.

Reproduce:
```
python3 tools/kn5000_dsp_extract.py <subcpu_v142.rom> /tmp/progs
python3 tools/kn5000_dsp_blockcoeff.py <subcpu_v142.rom> /tmp/progs <maincpu_v10.rom>
# sections: blocks biqctl ensemble coverage delta
```

---

## Headline

1. **★★ THE OPCODE→EVAL→WRITER CHAIN IS PINNED FROM THE DISPATCH TABLE.** The
   translator's jump table `OFFSETS_14745` (`0x03CB8E + off[opcode-0x61]`) maps each
   opcode to its handler; anchored on **op0x62=038EAC, op0x63=038EB9, op0x65=038F9B,
   op0x68=03925E** — four independently note-confirmed points — the whole chain resolves.
   It **agrees with the `_params.py` table for every block opcode**, so the identities
   below are not a fresh guess. **MEASURED.**
2. **★★ EACH BLOCK OPCODE'S LAYOUT IS DECODED FROM ITS WRITER.** The two C-RAM writer
   primitives are `0387E6` (set-pointer `801.0.NN.821` + datum `A..26`) and its
   continuation `0388B3` (datum-only `A..26`, relying on the DSP pointer auto-increment);
   the D-RAM pair is `038539`/`03846C` (`000.1.NN.000` + `A..15`) and continuation
   `038606`. Counting the writer calls in each block routine gives the span (§2).
   **PROVEN BY CONSTRUCTION.**
3. **★★★ 500 of 822 class-A multiplies now carry a NAMED coefficient — 60.8 %** (was
   391 / 47.6 %). **+109 of the 431 previously-unnamed are now named** (op0x73 = 103,
   op0x77 = 6). SINGLE DELAY 18/18, PHASER 11/14, FLANGER 12/18, the S.DELAY-combos
   +8..+12 each. §3.
4. **★ BOTH POSITIVE CONTROLS PASS.** The biquad order stays **6/6** (`b1,b0,b2,-a1,-a2,
   makeup` at C-RAM 00..05); op0x77 predicts ENSEMBLE's **3 voices × 2 channels = 6 taps
   at C-RAM 02 04 06 | 09 0B 0D** and names exactly those 6 — the prediction was the
   chorus note's, checked here from the C-RAM side. §4.
5. **★ A FREQUENT UNKNOWN WORD GAINED AN OPERAND ROLE.** `202.A.**.655` (20 occ) is now
   a **filter-section coefficient** in 19/20 (95 %) — a new operand role on a family the
   `-core-draft.md` worklist carried as undecoded. §5.
6. **★ THE BRIEF'S OP-LIST IS CORRECTED, and a self-inflicted over-reach was caught.**
   Of the five opcodes the brief named, only **0x73 and 0x77 write C-RAM** (and 0x24 was
   already a single C-RAM cell); **0x6B and 0x6C write the D-RAM/state space** (`038539`),
   so they cannot name a class-A multiply. And the span-5 op0x73 block **over-reached onto
   the MEASURED LFO words** (`092.A`/`094.A`) in PHASER — caught, guarded, 6 claims
   revoked and reported, not scored. §6.
7. **The disassembler was NOT edited; source coverage stays 18.3 %.** The block layouts
   are proven-by-construction but the coefficient ROLES are effect-contextual and
   INFERRED — a named role is not a full word decode, and this series does not launder
   one into the other (as `-namedcoeff.md` §5).

---

## 1. The dispatch, decoded (MEASURED)

`DSP_PerParameterTranslator` (sub-CPU 0x03CB18…): `opcode 0x21→03CEE2`, `0x24→03CEBC`,
`0x40→03CE9F`; otherwise `WA = opcode-0x61`, bounds-checked to `[0,0x18]`, then
`target = 0x03CB8E + OFFSETS_14745[WA]` (25 × u16). Each handler calls one eval helper,
then one writer (or the eval helper IS a block writer and there is no trailing writer).

```
   op    eval       writer(s) after eval        anchor / status
   0x62  038EAC     0387E6                        params §6 "0x62, 0 bytes"   ✓
   0x63  038EB9     03846C                        params §5 curve selector    ✓
   0x65  038F9B     038539                        chorus §2.3 LFO SPEED        ✓
   0x68  03925E     038922                        params §3 ms→samples         ✓
   0x70  0397F3     0387E6 ×3 (imm 00/10/20)      biquad designer (known)
   0x71  03A933     0387E6 + 0388B3×4 (per branch)  ← block, C-RAM
   0x73  039ABD     0387E6 + 0388B3×4              ← block, C-RAM
   0x75  03869B     038539 + 038606×3, N iters     ← block, D-RAM
   0x77  03B646     0387E6 (1 per call)            ← single computed C-RAM cell
   0x24  03A4B7     0387E6 (1 per call, imm 19)    single computed C-RAM cell
   0x6B  03943B     038539 (1 per call, imm 14)    single D-RAM cell
   0x6C  0394CD     038539 (1 per call, imm 14)    single D-RAM cell
```

## 2. The block layouts (PROVEN BY CONSTRUCTION)

| op | routine | space | span | source of the values | used by |
|---|---|---|---|---|---|
| 0x70 | 0397F3 | C-RAM | **6** | computed biquad (b1,b0,b2,−a1,−a2,makeup) | PARAMETRIC EQ + combos |
| 0x73 | 039ABD | C-RAM | **5** | FP-computed bilinear section, 2 params → 5 coeffs | 14 delay / all-pass effects |
| 0x71 | 03A933 | C-RAM | **5** | FP-computed, 3 filter-type branches | **declared by NO effect** |
| 0x77 | 03B646 | C-RAM | **1**/call | FP-computed per-voice depth, 3 type branches | ENSEMBLE |
| 0x76 | 039D98 | C-RAM | **3** | fixed damping/tone triple | reverbs, damped effects |
| 0x75 | 03869B | D-RAM | **4**/iter × N | **ROM descriptor tables**, not the stream | reverb (state) |
| 0x24 | 03A4B7 | C-RAM | **1**/call | FP-computed gain curve (imm 19) | AUTO WAH |
| 0x6B/0x6C | 03943B/0394CD | D-RAM | **1**/call | computed (imm 14) | delay/state effects |

**op0x73 (039ABD).** One `0387E6` (base = `T1[op][operand]`) + four `0388B3` → the five
consecutive C-RAM cells `base .. base+4`. The body is linear (its one branch, `AND L,0F0h;
JR NZ`, selects between two coefficient-lookup modes and re-converges *before* any write),
so all five always execute. Two 24-bit input constants per call (e.g. FLANGER
`C147AE / 3EB851`) are turned by the FP kernel (`03DD36/03E290/03D533/03D92C/03E2C0/03D44C`
with ROM constants at `0x012DB3…`) into the five output coefficients — the same shape as
op0x70's bilinear biquad, minus the make-up gain.

**op0x77 (03B646).** Three type branches, each ending in a single `0387E6`. Called once
per T2 record, so it writes **one** C-RAM cell per voice; ENSEMBLE issues six records.

**op0x71 (03A933).** Three branches (`WA==0/1/2` = filter type), each `0387E6 + 0388B3×4`
= a 5-cell block. **No effect in the corpus declares op0x71**, so it never runs — decoded
for completeness only.

**op0x75 (03869B).** The reverb's bulk uploader, and it writes the **D-RAM** space
(`038539`+`038606`, tail `0x15`), not C-RAM. It reads a per-parameter descriptor length
(`0x24`=36→9 iters for unit 0, `0x20`=32→8 iters for unit 1) and, per iteration, pulls
**four** 24-bit values from ROM tables (`0x01EAFA/01EB67/01EBD4` unit-0,
`0x01EC41/01ECA5/01ED09` unit-1, selected by the parameter's descriptor index) and streams
them to consecutive D-RAM cells with a `1/0x60` DRAM-bracket between iterations. Because it
is D-RAM/state it cannot name a class-A (C-RAM) multiply; the reverb bank is already named
via the PROVEN slot overlay (`-namedcoeff.md` §2), so this decode **corroborates** the
reverb map without adding names.

**op0x6B/0x6C** likewise write single **D-RAM** cells (`038539`). The brief's premise that
0x6B/0x6C block-upload C-RAM coefficients is therefore **corrected**: they are single-cell
state writers, and they name no class-A multiply (§6).

## 3. Coverage (MEASURED)

```
   class-A words in corpus (38 images) : 822
   NAMED  (land on a host C-RAM coeff) : 500   (60.8 %)     was 391 (47.6 %)
   unnamed                             : 322

   named by ROLE:  EQ 180  filter 103  mix/tap 82  damping 45  coeff 29
                   output-level 19  decay 13  mix 8  depth 6  gain-computer 6 ...

   newly named vs -namedcoeff.md: op0x73 = 103, op0x77 = 6   (+109 of the 431)
```

Effects that jumped: **SINGLE DELAY 13→18/18**, **FLANGER 2→12/18**, **PHASER 4→11/14**,
S.DELAY+S.DELAY 4→16, S.DELAY+FLANGER 6→18, S.DELAY+PHASER 8→19, ENSEMBLE 0→6. Still low
where the coefficients are neither T1-addressed nor a decoded block (CHORUS 2/19,
COMPRESSOR 1/10, RING MODULATOR 0/6 — §6).

## 4. Positive controls (both PASS)

```
   biquad order  C-RAM 00..05 = b1,b0,b2,-a1,-a2,makeup    6/6      PASS
   ENSEMBLE      op0x77 T2-confirmed operands 0..5
                 -> C-RAM 02 04 06 | 09 0B 0D              6 taps   PASS
                 (predicted "3 voices x 2 channels" first, then checked)
```

The ENSEMBLE control is the one the brief demanded: op0x77 names its six per-voice depths
and predicts the exact tap addresses. The block map does not disturb the biquad order
(the EQ has no op0x73/0x77), and the **T1-padding hazard did not reappear** for blocks:
expansion is driven by **T2-confirmed operands only**, so op0x73's FLANGER block at real
base `0x00` is kept while padding zeros never mint a bogus `C-RAM[0x00]` (the `base==0 &&
operand>0` guard, and the T2-confirmation, both hold).

## 5. A frequent unknown word that gained an operand role

```
   class-A family   occ   named   dominant role (share)          verdict
   202.A.**.655      20     20     filter        19/20  95%       ROLE = filter-section coeff
   102.A.**.4C8      41     10     filter         9/10  90%       (weak: only 10/41 named)
```

`202.A.**.655` is present in the delay/all-pass effects and its op0x73-block coefficient is
a **filter-section coefficient** 19 of 20 times, with a clean absence elsewhere. **ROLE
KNOWN** (not operation-forced): the exact class-A micro-op is the usual mac-family, but its
operand is now fixed as an op0x73 all-pass/comb coefficient. `102.A.4C8` (the chorus note's
per-voice output gain) also picks up the filter role in op0x73 contexts but is too sparsely
named to claim.

## 6. Misses, over-reach, and what remains (reported as prominently as the hits)

* **The span-5 op0x73 block OVER-REACHES onto the MEASURED LFO words.** In PHASER the
  op0x73 block based at `0x0A` would cover `0C/0D`, which are the LFO **phase increment**
  (`092.A.**.200`) and **wrap constant** (`094.A.**.200`, `0x7FFFFF`) that `-chorus.md`
  §2.2 pinned 29/29. Those cells hold baked-in LFO constants, not op0x73 outputs. The
  MEASURED LFO decode **wins**; the block claim yields. **6 claims revoked** (PHASER 2,
  S.DELAY+PHASER 4) and left unnamed. This is the instrument-blindness the brief warned
  of, caught by the present-and-absence check, not scored away. It also means op0x73's
  *effective* footprint is context-clipped where an LFO constant sits inside its nominal
  5-cell span — an honest limit of the fixed-span model.
* **op0x6B / op0x6C are NOT C-RAM block writers** (brief premise corrected): single D-RAM
  cells. **op0x75 writes D-RAM** state, not class-A coefficients. So three of the "block"
  opcodes name no multiply; only **op0x73 and op0x77** (and the already-counted single
  op0x24) do.
* **op0x71 is dead in the corpus** — decoded (5-cell, 3 types) but declared by no effect.
* **322 multiplies remain unnamed.** They are (a) the CHORUS/COMPRESSOR/RING-MOD families
  whose coefficients are neither T1-addressed nor a decoded C-RAM block, (b) cells written
  by the D-RAM writers (op0x75/6B/6C) that the class-A cursor nonetheless reaches only via
  the state pointer, and (c) the LFO/phase words (correctly never named). Naming more needs
  either the CHORUS coefficient source or a live C-RAM address trace from the enabled core.
* **The op0x73/op0x71/op0x77 coefficient VALUES are computed by an FP kernel** whose exact
  transfer function (which of the 5 cells is b0 vs −a1, and from which of the 2 input
  params) is **not decoded here** — only the cell COUNT and BASE are proven. Role is
  INFERRED "filter section", not the per-cell biquad assignment op0x70 has.
* **All static.** The core is disabled; nothing was executed.

## 7. Cross-checks to earlier notes

| earlier claim | source | status here |
|---|---|---|
| op0x77 = ENSEMBLE per-voice depth, 4/4 `192.A.**.41A` | chorus §3.3 | **CONFIRMED and extended to 6/6** from the C-RAM side (02 04 06 09 0B 0D) |
| `092.A`/`094.A` = LFO increment / wrap `0x7FFFFF`, 29/29 | chorus §2.2 | **UPHELD, and given precedence** over the block map (the over-reach guard) |
| the 431 unnamed are chiefly block-uploaded | namedcoeff §6 | **CONFIRMED for op0x73/op0x77**; refined — op0x75/6B/6C are D-RAM, not the cause |
| op0x70 = 6-cell biquad; op0x76 = 3-cell damping | namedcoeff §2 | **SAME MECHANISM** re-derived: block base + auto-increment continuations |
| op0x75 → 0x97 "reverb decay" | parameters §5 | **REFRAMED**: op0x75 is the whole reverb D-RAM bulk-upload (4/iter from ROM tables), 0x97 is one cell of it |
| coverage 18.3 % | hi12 | **UNCHANGED** — block layouts are proven, but the roles are INFERRED, not full decodes |
