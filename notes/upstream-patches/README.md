# Upstream (MAME) submission patches

**This directory is the single index of everything staged for upstream MAME.** Most of it is the
SHARC series (below); non-SHARC patches use a device-name prefix instead of the numeric series.

## Non-SHARC patches

| file | device | what |
|---|---|---|
| mn10300-01-dasm-f4-length.patch | cpu/mn10300 | disassembler: the F4 page is **2 bytes**, not 1 — `disassemble_f4` reads `opcodes.r8(pc + 1)` and prints its operands but returns length 1, so linear disassembly desynchronises after every F4 and invents 1-2 phantom instructions before resyncing. One-character fix (`return 2 | SUPPORTED;`); every sibling F-page handler (f0/f1/f2/f3/f5/f6) already returns 2. |

`mn10300-01` is a standalone one-liner, independent of the SHARC series, and applies cleanly to the
pristine mn103dasm.cpp in kn7000_mame_build (verified 2026-07-20 with `patch --dry-run -p1`).
Concrete misread cited in the commit message: KN7000 firmware 0x484357C7 `f4 02` + `fa c8 f5 00`
comes out as three instructions instead of two. 3,440 F4 instructions in that ROM's main code
region alone; this bug has bitten the kn7000_disassembly CONVERT track nine times, and
`kn7000_disassembly/tools/dis_view.py` exists only to work around it. Submission is Felipe's.

# SHARC core fixes

## ★ 2026-07-20 extension: patches 10-12 (SAT MRx + native ABS + native FDEP(SE)-imm)
Three new patches extend the series (generated the same way: committed on a throwaway worktree of
957e9dec1b4 with 01-09 applied, format-patch, Felipe's authorship, upstream-facing messages):

| # | file | what |
|---|---|---|
| 10 | 10-sat-mr-family.patch | interpreter + DRC-native: fixed-point SAT MRx family (op 0x00-0x0f, TRM B-57; both engines previously CRASHED — a KN7000 Gate Reverb executes `Rn = SAT MRF (SF)` every quiet frame) |
| 11 | 11-native-abs-drc.patch | DRC: native `Rn = ABS Rx` (ALU 0x30; upstream DRC fatals, interpreter has it — incl. AV+STKY-AOS overflow corner and translation-time ALUSAT clamp) |
| 12 | 12-native-fdep-se-imm-drc.patch | DRC: native immediate `FDEP (SE)` (shiftop 0x13; upstream DRC fatals, interpreter has it) |

Verified (2026-07-20): the full 12-patch stack `git am`s cleanly on pristine 957e9dec1b4; the final
tree's sharc.cpp + sharcdrc.cpp pass the same g++ -fsyntax-only (C++20, real include set) check; the
overlay build carrying the equivalent changes is bit-identical on the reverb A/B oracle
(md5 44b09b9d0eaae59d9a65e5b4f4e72ec0) and survives a LIVE Gate Reverb (rec12) load + 10 s run in
both DRC and interpreter (was: instant fatalerror). Patch 10 goes with PR B; 11/12 are standalone
DRC-crash fixes that can ride along.

## ★ The 9-patch series (regenerated 2026-07-19, rebased onto upstream 957e9dec1b4)
Patches 01-09 are a **clean, ordered, self-contained `git am`-able series** against pristine upstream
MAME (kn7000-base @957e9dec1b4). Verified (2026-07-19):
- each patch applies with `git apply --check` at its point in the series, **zero offsets/fuzz**;
- the cumulative result is **byte-identical** to replaying the fork's sharc commits (nothing lost in
  the rebase);
- **every intermediate state compiles** (g++ -fsyntax-only of sharc.cpp + sharcdrc.cpp with the real
  MAME include set/flags, C++20);
- authorship: Felipe (format-patch from rebased cherry-picks of the fork commits; commit messages
  rewritten upstream-facing, TRM citations + "restores DRC == interpreter" framing already in).
Patches 01-04 and 07-09 also apply to pristine upstream *individually*; 05/06 need their ALUSAT
predecessors. Series order is the required order.

| # | file | what | fork commit(s) |
|---|---|---|---|
| 01 | 01-interp-fixed-avg.patch | interpreter: fixed-point AVG op 0x09 (+ sharc.h decl) | slice of 630c68d |
| 02 | 02-interp-general-fixed-multiplier.patch | interpreter: general single-fn fixed multiplier/MAC decode (upstream threw) | slice of 3aca274 |
| 03 | 03-interp-multifunction-fixed-mac.patch | interpreter: multifunction fixed MAC forms 0x06/0x08-0x16 + 0x20-0x2f, ALUSAT-correct parallel ALU | slice of 3aca274 + 2d308c7's interp hunk |
| 04 | 04-alusat-add-sub.patch | DRC: MODE1 ALUSAT in ADD/SUB — **the correctness headline** (real DRC-vs-interpreter divergence) | 2d308c7 (DRC part) |
| 05 | 05-alusat-full-family.patch | DRC: ALUSAT across the whole fixed ALU family (shared tail helper) | b942366 |
| 06 | 06-alusat-specialization.patch | DRC: ALUSAT baked at translation time, cache flush on MODE1 change | b1028bd **minus the kn7000.cpp clock hunk** |
| 07 | 07-native-fixed-mac.patch | DRC: native multifunction fixed MAC family | cd8c720 |
| 08 | 08-native-single-fn-fixed-multiplier.patch | DRC: native single-fn fixed multiplier SS forms — **the perf headline** (~66M fallbacks/run gone) | bb2d516 |
| 09 | 09-native-fixed-avg-drc.patch | DRC: native fixed AVG (last hot fallback) | e487bb7 |

### Why 01-03 exist (2026-07-19 finding, corrects the older analysis)
The old 5-file series failed to apply because 2d308c7's sharcops.hxx hunk patches the **fork-only**
interpreter multifunction-MAC block (added by 3aca274, NOT by 630c68d as previously believed — the
`>> 1` average line in its context is the *parallel* average inside that block, not op 0x09).
Upstream's interpreter also **throws** on the general fixed multiplier forms (it implements only
0x30/0x40/0x70/0xb0/0xb2) and on the whole multifunction fixed-MAC block. Without 02/03 the DRC-native
patches (07/08) would emit ops whose in-tree conformance reference doesn't exist and which the
interpreter cannot run at all. 01-03 carry the interpreter reference implementations first, so every
DRC patch keeps the "interpreter = oracle" story inside the tree.

### Suggested split into PRs
- PR A (correctness): 01 + 04 + 05 + 06 (04-06 = the ALUSAT DRC-vs-interpreter divergence; 01 is tiny
  and standalone). 04 works without 01 if a smaller headline PR is preferred.
- PR B (fixed-point coverage + perf): 02 + 03 + 07 + 08 + 09 (interpreter implementations first, then
  the native DRC emissions measured against them).
- The `adsp21065l_device` variant is NOT in this series (separate PR; datasheet cross-check now done —
  see ../sharc-upstream-patch-series.md §2026-07-19).

## Consolidated diff (kept)
**00-consolidated-vs-upstream-base.patch** — the COMPLETE SHARC-core fork diff vs upstream (both
concerns: all fixes above in their fork form + the 21065L device + fallback plumbing). Still applies
clean to 957e9dec1b4 (re-verified 2026-07-19). Use it to reproduce the full fork state; use 01-09 for
submission.

## Verification standard
Every fix restores DRC == interpreter (or interpreter == TRM). The reverb WAV A/B is the oracle:
historical per-commit baseline md5 0787b60cc3cec696c7aa43bb471b2b1b (preserved at
kn7000_scratchpad_snapshot/tmp-loose-2026-07-16/ab_before.wav); current-era baseline (2026-07-19,
published binary, money.lua, fresh default cfg, pristine SD image, -seconds_to_run 22) md5
**44b09b9d0eaae59d9a65e5b4f4e72ec0**, deterministic across runs. Recipe in
../sharc-upstream-patch-series.md.

## Not included (documented in the catalogue, want a maintainer's call / more testing)
- Interpreter-fallback plumbing for the DRC (compute_fallback/shiftimm_fallback cfuncs): the fork
  routes unimplemented DRC compute/shift-imm ops through the interpreter instead of aborting. A good
  future patch 10, but it changes generate_unimplemented_* semantics — maintainer call.
- SET/TOGGLE-ASTAT bit emission in the DRC (fork addition), circular-buffer wrap off-by-one
  (`>` vs `>=`: TRM-correct but changes the KN7000 reverb by 2 samples — held), AVG/SSFR rounding,
  FIX-overflow UB, pre-modify circular wrap: all catalogued with TRM citations.
