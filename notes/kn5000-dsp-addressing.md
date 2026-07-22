# NEC uPD6383GF — the data-pointer ADDRESSING RULE

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_addressing.py` (imports `kn5000_dsp_params.py`; nothing is edited).
Follows `kn5000-dsp-pointer.md`, which found the pointer ORIGIN and named the pointer-DELTA
rule as *"the single binding unknown"* (§8 item 2, INDEX backlog 1b). This note settles the
composition — how `addr8` forms the address each word reads/writes — and reproduces all three
falsifiers plus an exact host-write/body-read coincidence.

Claims are tagged **MEASURED**, **INFERRED**, **PROVEN BY CONSTRUCTION**, or **SPECULATIVE**.
§6 lists what is still open. **No audio, the core stays instantiated DISABLED, and the core is
NOT edited** (§5 says why not yet).

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_addressing.py
```

---

## Headline

1. **★★★ THE RULE.** `class4` is *not* one enumerated field. It is **`bit3 = multiplier-enable
   (bit 23) ‖ bits[2:0] = an addressing MODE`**, and the data pointer is moved by **exactly one
   mode**:

   > **MODE 2 (`class4 & 7 == 2`, i.e. classes 2 and A):**
   > `operand cell = mem[ptr]` ; then `ptr ← (ptr + signed8(addr8)) mod 256` — a **signed
   > post-increment on an 8-bit pointer**.
   > **Every other mode (classes 0, 1, 3, 4, 5, 6, 8) leaves the data pointer unchanged**; their
   > `addr8` is a DRAM sub-op (class 1), a table selector (class 6), an immediate, or unused.

   This is the naive "signed post-increment, classes {2,A} move it" rule with the **two
   corrections that make it close**, both forced by data:
   * **(a) the pointer is 8-bit and WRAPS** (§4). The reverb's "leaves any 256-cell window"
     failure (`-pointer.md` §3) was a *no-wrap artefact*: an 8-bit pointer cannot leave 0..255.
   * **(b) class 8 does NOT move it** (§2). Mode 000 (`class 8 = mult ‖ 000`) shares low bits with
     class 0, whose `addr8` is always 0; class 8's `addr8 = 0x16` is **not** a pointer delta, and
     the biquad breaks unless it is ignored.

   The **derivation of the mode field is not new to this note**: `class2-round2.md` §4 proved BY
   CONSTRUCTION, byte by byte from the sub-CPU firmware, that in the host-poke word family `class4`
   is an **address-space selector** (writers emit `class4 = 0`, `1`, or `2` to aim the same
   pointer load at different spaces). This note carries that reading into the effect bodies and
   shows it closes.

2. **★★★ F2 (BIQUAD) — reproduced AND matched to the host, exactly.** algo 39 PARAMETRIC EQ's
   9-word motif repeats **ten** times; under the rule the per-band step is **+4, all ten, no
   exception** — and the pointer visits `S0 S1 S2 S3` contiguously within a band, `class8` frozen.
   **The host writes biquad STATE at `{64,68,6C,70,74}` — five bands, stride 4** — and there is
   an origin (`0x19`) under which channel-0's five band cells are **`64 68 6C 70 74`, 5 of 5**
   (§3). The **stride is origin-free and it is an EXACT match** (+4 body ↔ +4 host). This is the
   strongest host-write/body-read coincidence the project has, and it is *external* to any decode
   of the body. **MEASURED.**

3. **★★ F1 (PHASER) — the shared tap resolves to ONE cell, the sweep is +1/section.** All 18
   all-pass sections' tap reads (`102.2.<c>.1CD`) land on the **single** cell `0x76` (origin 0x70),
   while the section base advances `+1` per stage (`212.2.01.412`) — a phaser sweeping its stages
   across contiguous cells over a stationary far tap, which is correct DSP behaviour (§3).
   `0x76` is **not** in the phaser's host map, and it should not be: `class2-round2.md` §1.4 shows
   the `c` values are *static* coefficients, not host-swept. **MEASURED.**

4. **★★ F3 (REVERB) — the pointer is stationary across the diffusers, and it stays in range.**
   algo 16's nine diffuser stages have data-pointer net move **zero in 8 of 9** (the ninth carries
   the input/output mixing); every intra-stage `class 2/A` `addr8` is `0x00`, so the C-RAM pointer
   does not move between stages — the diffuser delays live in **external DRAM** via the
   `880.1.60/20` brackets, a *separate* addressing mechanism (`class2-round2.md` §1.1). With the
   8-bit wrap the whole-program excursion is trivially in 0..255. **MEASURED.**

5. **★ IT STAYS UNIMPLEMENTED IN THE CORE, ON PURPOSE.** The composition rule is solid; the
   absolute ORIGIN is not (§3, §6): the origin that lands the biquad on the host block is `0x19`,
   which is **none** of the three pointer registers the header loads (`0x70`/`0x6C`/`0x25`). Until
   that residual is closed the core would compute plausible-but-unverified absolute addresses,
   which is exactly the failure mode `-pointer.md` §5 exists to avoid. **The rule is documented;
   the core edit waits for the origin.**

---

## 1. THE RULE, STATED PRECISELY

```
   word = hi12[35:24] . class4[23:20] . addr8[19:12] . lo12[11:0]

   class4 decomposes:  bit 23      = multiplier enable          (already MEASURED, -encoding.md)
                       bits 22:20  = addressing MODE
                                        000 -> no pointer move  (classes 0, 8)
                                        001 -> DRAM bracket / control (class 1: 880.*)
                                        010 -> C-RAM DATA POINTER: signed addr8 POST-increment
                                        011 -> class 3 (modulation offset, no move)
                                        100 -> table lookup (class 4/6, no move)
                                        101 -> class 5 (addr8 == 0)
                                        110 -> class 6 (table selector in addr8, no move)

   pointer semantics for MODE 010:
       cell   = ptr                         (operate on mem[ptr] BEFORE moving)
       ptr    = (ptr + signed8(addr8)) & 0xFF
```

`signed8(addr8) = addr8 - 256 if addr8 & 0x80 else addr8`. **MEASURED** for the biquad and phaser
(the walks below are exact); **INFERRED** that the wrap modulus is 256 (the pointer is the 8-bit
`addr8`-width register; the reverb needs *a* wrap and 256 is the width) — see §4.

The mode reading of `class4` is **PROVEN BY CONSTRUCTION** for the poke family (`class2-round2.md`
§4) and **INFERRED (strong)** for the bodies here, because it is what makes classes 2/A the sole
pointer-movers *and* explains why class 8 (same low bits as class 0) is frozen while class 2 (same
low bits as class A) moves.

## 2. WHY CLASS 8 MUST BE FROZEN — the biquad forces it

The SOLVED biquad motif (`-semantics.md`, Direct Form I) walks `S0 S0 S1 S2 S3 | S3 | S2 S2 | S1`,
net **+4**. Word `[6] = 804.8.16.415` is class 8 with `addr8 = 0x16 (+22)`. If class 8 moved the
pointer the walk would jump +22 mid-band and the four state cells would be nonsense. The only
assignment that reproduces DF-I is **class 8 does not move the pointer** — so the delta gate is the
low three bits (`== 2`), not merely "is `addr8` non-zero". `class 8 = mult ‖ mode 000`; mode 000 is
also class 0, which always carries `addr8 == 0`, so the two are consistent under one rule.
**MEASURED** (the tool prints the S0..S3 visit with `[6]` frozen).

## 3. THE THREE FALSIFIERS, MEASURED

### F2 — biquad `+4`/band, matched to the host state block

```
   motif starts (algo 39): 5 14 23 32 41 | 59 68 77 86 95   (10 = 5 bands x 2 channels)
   per-band S0 stride     : 4 4 4 4 4 4 4 4 4                 (host STATE stride = 4)   EXACT
   within band 0          : S0 S0 S1 S2 S3 | S3 | S2(frozen) S2 | S1   (DF-I, -semantics.md)

   host writes STATE at {64,68,6C,70,74}, COEFF at {00,06,0C,12,18}
   origin 0x19  -> channel-0 band cells = 64 68 6C 70 74   == host state   5/5
```

The **coefficient** side matches too, through the *other* mechanism: the motif has **six**
class-A words (the implicit coefficient cursor, +1 each), and the host writes coefficients at
**stride 6** `{00,06,0C,12,18}`. So one biquad band = a 6-word coefficient block streamed by the
cursor + a 4-word state block walked by the pointer, and **both strides match the host exactly**.
This is the host-write/body-read coincidence the method asked for, and it lands. **MEASURED.**

### F1 — phaser: one shared tap, `+1`/section sweep

```
   origin 0x70:  all-pass tap READS (102.2.<c>.1CD) -> { 76 }   (ALL 18 sections, one cell)
                 section base WRITES (212.2.01.412)  -> BB..CD   (sweeps +1 per section)
```

The `-N`/`+N` of the `104`/`102` pair returns the pointer to the section base each stage; the
`212.2.01.412` write advances it `+1`. Because the base advances `+1` and the tap distance `N`
grows `+1` per stage, the far tap `base - N` is **constant at `0x76`** — the shared cell. Exactly
the sweeping-phaser behaviour, and `0x76` is a static coefficient (absent from the host map, as it
must be). **MEASURED.**

### F3 — reverb: stationary pointer, in range by wrap

```
   9 diffuser stages (880.1.60.2D4):  data-pointer net move zero in 8 / 9
   origin 0x50, NO wrap : excursion -176 .. 80   (leaves 0..255)   <- the old "failure"
   origin 0x50, 8-bit WRAP: every cell in 0..255 BY CONSTRUCTION
```

The diffuser delays are in **external DRAM** (`880` brackets, a separate mechanism), so the C-RAM
pointer is stationary across the stages; the only excursions are the input/output mixing, and an
8-bit pointer wraps them harmlessly. The `-pointer.md` §3 "reverb leaves any 256-cell window under
all 512 class subsets" result was measured **without** the wrap; with the wrap it dissolves.
**MEASURED.**

## 4. THE WRAP — the one INFERRED step, and its evidence

C-RAM/D-RAM are 256×24 (`-header.md`), addressed by an 8-bit pointer. `addr8` is 8 bits, and every
pointer immediate the header loads is 8 bits (`-pointer.md` §1). A register that is 8 bits wide
wraps mod 256 for free — there is no wider register in the model. The reverb *requires* a wrap (its
excursion is 256 wide, §3-F3) and 256 is the only modulus consistent with the RAM size and the
field width. **INFERRED (strong), not MEASURED**: no single reverb word's absolute address has been
independently confirmed, so the wrap is argued from width + the reverb range, not observed.

## 5. WHY THE CORE IS NOT EDITED YET

The composition rule (`ptr += signed8(addr8) mod 256`, mode-gated by `class4 & 7 == 2`) reproduces
all three falsifiers and produces the exact biquad host-coincidence — that part is solid enough to
implement. **But a core that computes *absolute* addresses needs the origin, and the origin is not
nailed:**

* the origin that lands the biquad on the host state block is **`0x19`** (§3-F2), which is **none**
  of the three registers the header loads for unit 0 (`821 -> 0x70`, `827 -> 0x6C`, `825 -> 0x25`).
* two honest readings survive: either the biquad state walks a **fourth** pointer register this
  project has not enumerated (the chip has six: CP/DP/BP1/BP2/PR1/PR2, `-pointer.md` §8.4), or one
  of the pre-motif setup words (`w0 = 000.2.0B.1CD (+11)`, `w4 = 000.2.40.407 (+64)`) is **not** a
  pointer move, which would shift the required origin to `0x00` (if `w0` is inert). Neither is
  decided.

Implementing absolute addressing on an unverified origin is precisely the
"plausible-but-wrong" trap the disabled-core discipline exists to avoid (`-pointer.md` §5). The
**relative** rule (how much the pointer moves, which words move it) is ready; the **base** is not.
So this note ships the rule and the tool, and leaves the core untouched.

## 6. WHAT IS STILL OPEN

1. **The absolute origin / which pointer register the biquad walks.** `0x19` fits, no header
   register gives it, and whether `w0`/`w4` move is undecided (§5). *The* remaining unknown, and it
   is now a one-number question with an external check (the host block) already built.
2. **The wrap modulus is INFERRED, not observed** (§4). One address-bus trace from the enabled core
   would confirm 256 directly.
3. **The phaser modulator write vs the tap.** `-pointer.md` §6 reported the modulator's
   `212.A.04.1D5` landing off the tap `0x76`; under this rule the all-pass *base* writes sweep
   `BB..CD` (correct), and the modulator write is a *different* pointer context — likely a second
   register (item 1). Not chased here.
4. **Modes 011/100/101/110** (classes 3/4/5/6): confirmed **not** to move the C-RAM pointer, but
   what they DO address (table space, modulation offset) is only named, not decoded.

## 7. Corrections to earlier notes

| earlier claim | source | status here |
|---|---|---|
| "the pointer-DELTA rule is the single binding unknown"; "classes {2,A} move it is measurably WRONG" | `-pointer.md` §8.2, INDEX 1b | **REFRAMED, not overturned.** The delta rule *is* signed post-increment on classes {2,A}; the two things that made it look wrong were the **missing 8-bit wrap** (reverb) and **counting class 8 as a mover** (it is class-A-adjacent). With both fixed it reproduces all three falsifiers. |
| the reverb "leaves any 256-cell window under all 512 class subsets" | `-pointer.md` §3 | **EXPLAINED**: measured with no wrap. An 8-bit pointer wraps; the excursion is in range (§4). |
| `class4` bodies "is the class this line of work is named after; whether it is an address-space selector is NOT ESTABLISHED" | `-class2-round2.md` §4 | **CARRIED INTO THE BODIES**: reading `class4 = mult ‖ mode` makes classes {2,A} the sole movers and freezes class 8, and it closes the biquad — evidence the poke-family reading transfers. **INFERRED (strong).** |
| the phaser's shared cell is `0x76` but its modulator writes `0x7B` (a MISS) | `-pointer.md` §6 | **HALF RESOLVED**: the all-pass *base* writes are correct (sweep BB..CD); the modulator write is a different pointer context (§6 item 3), not a delta-rule error. |
| channel bases `0x40`/`0x54` are origin-relative, not an anchor | `-hi12.md` §5.3 | **UPHELD and USED**: the +4 stride is origin-free and matches the host; only the base is free, and it is `0x19` not `0x70` (§5). |

## 8. Coverage

No new word is decoded (the rule is a property of the `class4`/`addr8` *fields*, already counted).
Honest source coverage is **unchanged at 18.3 % (545/2974)**, per `-pointer.md` §9 — and, as there,
counting a structural/machine-state result as vocabulary would be the over-claim the whole series
refuses. The value here is that **every `addr8` in a class-2/A word is now a concrete signed
displacement on a wrapping 8-bit pointer**, and one external check (the biquad host block) pins the
relative layout exactly; only the absolute base remains.
