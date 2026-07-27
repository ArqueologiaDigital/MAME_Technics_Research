# ADJUDICATE AND APPLY, round 4 — what was applied, and what it cost

Companion to `kn5000-roms-disasm/dsp/analysis/adjudication-round4.md`
(2026-07-27). NEC **uPD6383GF-3BA**, Technics SX-KN5000 IC311.

Inputs adjudicated: `dram-cursor-closure.md` (the 42 delay-DRAM words),
`store-gate.md` (the bit-7 store gate), `register-space.md` (the register space).

```
cd ~/compartilhado/kn5000-roms-disasm
python3 dsp/tools/adjudicate4.py all         # every number, ~2 min
python3 dsp/verify.py                        # BYTE-MATCH OK
python3 dsp/tools/dsp_coverage.py
python3 dsp/tools/retraction_sweep.py        # premise P16 is new
~/compartilhado/kn7000_mame/tools/upd6383d_diff.sh
```

## APPLIED TO THE EMULATOR: one guard, and it REMOVES a decode

`upd6383d.h` **guard 7** carried an escape clause:

```cpp
    const u16 f = hi_f31(hi12(w));
    if (f == 1 && lo_act(w) != LO_ACT_ACC_BUS)  return false;
    if (f != 1 && f != 2)                       return false;
```

Its stated justification was *"the CLEAR is UNOBSERVABLE exactly when the ACTION
is `LO_ACT_ACC_BUS`, because that substitutes the bus for the accumulator's own
feedback term and the old accumulator cannot reach the result."*

**That argument enumerates two of the three surviving gates.** It is true for
`b7_f31_1_off` (no clear) and `b7_f31_1_keepclear` (clear before the ALU). It is
false for `b7_f31_1_clrlate`, which defers the clear to **after** the word's own
ALU step, where it sets the result to **0** whatever the ACTION was.
`store-gate.md` §4 widens the class-(1,1) survivor set from three hand-named
gates to **21 of 33 canonical effects**, and its first family is literally
`-/clr:{never,before,after}` — so the round that was supposed to settle the gate
made the escape *less* defensible, not more.

Now:

```cpp
    if (hi_f31(hi12(w)) != 2)                   return false;
```

**Price, MEASURED, and it is one word.** `upd6383d.h` claimed *"138 at (1,1) of
which 107 carry ACTION 0x00 and execute"*. They do not execute: 106 of the 107
are refused by the SRC/ACTION anchoring guard (`store-gate.md` item G). Exactly
one corpus word ever reached the escape — `092.A.01.1C0`, the LFO ramp step at
header I-RAM 37, slot 37 of the cold-boot frame. It becomes PARTIAL.

The same change is in `dsp/tools/dsp_disasm.py`; `tools/upd6383d_diff.sh` reports
**MIRRORS AGREE, 3057/3057** on text and on the three execution predicates.

`upd6383.cpp` is comment-only: `st_suppressed()` is now unreachable from
`alu_step()` (guard 7 refuses every class-(1,1) store word), but the call stays
because the same predicate is applied on the input-stage path and the two must
never disagree.

## COMMENTS CORRECTED IN THE DEVICE

1. **`HI_B7`'s doc block.** bit 7 being *in the condition* is now **FORCED**, not
   assumed: `store-gate.md` item C runs all nine enumerated conditions against
   two witnesses that disagree about the same `hi12[3:1]` (the biquad needs class
   (0,1) to store — suppressing it is 51.090 dB wrong; the LFO needs class (1,1)
   not to) and exactly two survive, `b7 & f31 == 1` and `b7 & f31 != 2`. They
   differ only where `alu_decoded()` already refuses, so the choice costs zero
   words.
2. **What the suppressed case DOES is forced only NEGATIVELY.** 0 of 17 928
   survivors write `mem[ptr]` at class (1,1) — but 21 of 33 effects survive, in
   three families, including ★ `LOAD` (bit 7 as a memory-port DIRECTION bit).
   The device implements one point in that set; it is sound only because guard 7
   now refuses the whole class.
3. **The "13 corpus words" is CORRECT and `store-gate.md` item F's falsification
   of it is WITHDRAWN.** Both numbers are right and they count different sets:
   **13** over the 3057-word corpus this comment names (38 distinct body images
   **plus** the 83-word resident kernel), **11** over the 38 body images alone,
   which is what `gate_settle.py:images()` walks. The kernel contributes 2.
   `adjudicate4.py mirror` prints all three censuses.
4. The bit-4 census is one word short in the old comment: 708 words carry bit 4
   over the full corpus, not 707.

## APPLIED FROM THE OTHER TWO PASSES: nothing

* **`dram-cursor-closure.md`** shipped nothing by its own decision, and this pass
  agrees — its own item B (the descriptor base is per-unit state) is confirmed by
  `register-space.md` E2 *measuring* the two bases, but neither result decodes an
  instruction. Its item I contradiction is dissolved (below) rather than acted on.
* **`register-space.md`**'s one FORCED result (the `is_c40` immediate is 8 bits)
  re-derives `output-stage-decode.md`'s payload rule and makes no word
  executable. Its `+1` auto-increment describes the HOST write port, which lives
  in `tools/kn5000_dsp_params.py`, not in `src/`.
* **`store-gate.md`**'s `SRC 0x00 = FEEDBACK L` is a statement about a user
  parameter's *default value*, not about an instruction. `SRC 0x00` stays
  CONSISTENT and its 30 PARTIAL + 10 TRAP slots keep trapping.

## THE COLLISION THAT MATTERED — and it needed no code

`dram-cursor-closure.md` item I reports a live contradiction: MULTI TAP's taps
sit **above** its "line base 0" while ROOM REVERB's read sits **on the region
floor** with its writes above, and *"at least one of {the alignment, H-DIR, R1's
forced read slot, the rotation sign} is wrong"*.

**None of the four. The two halves are stated in different units.** MEASURED over
486 + 384 descriptor cells: every unit-0 value ≤ `0x8000` and every unit-1 value
≥ `0x7FFF`. Unit-0's region floor is `0` and unit-1's is `0x8000`; a descriptor
cell is always an **absolute address**. Restated in one unit both algorithms say
the identical thing — one cell holds the floor, every other cell is above it.
There is no rotation-sign disagreement in the corpus.

What *is* wrong is the **alignment**: every reverb block carries at least two
**interior** cells that cannot be an address inside its own region (`0x1E` =
32767 at index 30 of 32 in 12 of 12; `0x01` = 0 in eleven of twelve), and a rigid
1:1 map with one phase δ cannot skip an interior slot. `δ = 0` is the best
*rigid* map and says nothing about whether a rigid map is the right shape.

## RE-MEASUREMENT

Live, `DSPCFG On`, cold boot + the same 28 s keybed programme, same nvram/cfg.

| | before | after |
|---|---|---|
| words executing **something** | 199 of 285 | **199** of 285 |
| words executing **FULLY** | 108 | ★ **107** |
| words executing **addressing only** | 91 | ★ **92** |
| words executing **nothing** | 86 | **86** |
| ended on wait word / CAP / OVERRUN | 1 106 880 / 210 241 / 26 880 | **identical** |
| **frames completed** | 0 of 1 344 001 | **0 of 1 344 001** |
| ★ **closure residue, last frame** | **+0** | ★ **+0** |
| ★ complete frames that CLOSED | 1 080 959 of 1 106 880 | **identical** |
| residue min / max, entry pointer X | −1 / +116, `0xFF` 97.58 % | **identical** |
| input-stage audit | 1 117 440 both-reads, 0 MISMATCHED | **identical** |

Coverage moves only in the kernel rows: frame floor tier-1 83 → 82
(38.4 % → 38.0 %), tier-1+2 61.1 % → 60.6 %. The 38 body images are unchanged
(2974 words, 1234 tier-1, 41.5 % / 52.6 %) because the word is in the header.

## SAFETY

* Build clean — 0 `error:` / `Error [0-9]`; binary **74 405 928** bytes, mtime
  advanced; `tools/publish-binary.sh` run.
* `-validate kn5000` — **exit 0, zero bytes of output**.
* `dsp/verify.py` — **BYTE-MATCH OK**; no `.dsm` regenerated.
* `tools/upd6383d_diff.sh` — **MIRRORS AGREE, 3057/3057**.
* **Audio bit-identical, on a capture that can fail**: DSPCFG Off *and* On,
  before *and* after, all four WAVs are `ed4353643dd5ffbf2a526634e5831203` —
  1 344 001 frames, 1 276 567 non-zero samples, peak 22 268. Trapped frames still
  contribute exactly zero, so removing a decode from a frame that traps anyway
  cannot move the output, and that is measured rather than argued.

## ★ FOR WHOEVER PICKS UP THE DELAY-DRAM FAMILY

1. **The reverb's delay-line lengths are readable from the ROM with no
   instruction decode at all** — `adjudicate4.py segments` prints all twelve
   presets. ROOM REVERB 1 is an 11-segment contiguous partition
   `83 172 356 513 739 240 119 247 428 616 360`, pre-delay 800, long head 8905.
2. **The brief's `[127, 435, 489, 183, 522]` is retracted** — `r3-delaydram.md`
   §5(c) halved-payload correction, which never propagated. Filed as
   `retraction_sweep.py` premise **P16** (7 LIVE sites). An impulse test must be
   ≥ 4 × 8905 = 35 620 samples, and ≥ 50 784 to recirculate the whole region.
3. **The `|R| = 1` resurrection is alive and pinned to two words** —
   `E30.C.00.404` and `82E.8.0F.000`. The other twelve candidates are refused
   (nine are C-format; three address cells the descriptor space does not have,
   including `859.0.86.822`, which is the unit-1 VOLUME pointer).
4. **Do not re-run the rigid phase scan.** Solve the cell→word map as a
   *matching* problem against the 12 boundary addresses, with the two
   non-address cells assigned to whatever consumes region constants.
