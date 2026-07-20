# SHARC core fixes — upstream candidate series

The KN7000 effects DSP (ADSP-21065L) drove several fixes and additions to MAME's shared
`src/devices/cpu/sharc/` core. This file catalogues them for eventual upstreaming to MAME proper —
they are general SHARC/ADSP-2106x correctness issues, not KN7000-specific. TRM = the ADSP-21065L
SHARC DSP Technical Reference (508pp). Grouped by confidence/readiness.

## A. New device variant (KN7000-specific, but clean)
- **`adsp21065l_device`** (commit dba4bea): a 21065L subclass of the 2106x core — internal-SRAM/SDRAM
  personality (code 0x8000+, data 0x9800+/0xC000+, external SDRAM 0x20000+, on-chip IOP register
  set), host-boot mode. ★ CORRECTED + datasheet-checked 2026-07-19 (see the section at the bottom):
  the DEVICE's values are reset PC 0x8004 (effective 0x8005) and IRQ vector base 0x8000 — the
  0x20004/0x20000 previously written here are the BASE 2106x values the subclass overrides. Vector
  base 0x8000 ("beginning of Block 0"), RSTI offset 0x04, IRQ0 0x8020 and external space at 0x20000
  are now CONFIRMED against the TR appendices (Table F-1/App. E); the DM windows 0x9800/0xC000
  remain RE-derived (User's Manual ch. 5 not in our PDFs). Ships as its own device so it does not
  perturb the existing 21060/21062 parts. **Upstream-ready**, labelling the DM-window detail
  RE-derived in the PR.

## B. Correctness fixes — HIGH confidence, verified against the TRM + the running firmware
1. **MODE1 ALUSAT in the recompiler** (commits 2d308c7 + b942366). The DRC compiled every
   fixed-point ALU op as a plain wrapping `UML_ADD`/`UML_SUB` with NO saturation, while the
   interpreter honored `MODE1.ALUSAT` (TRM B-6: overflow → 0x7FFFFFFF / 0x80000000). Any firmware
   running with ALUSAT set (the KN7000 kernel does: `BIT SET MODE1 0x3000`) and using
   saturate-then-reflect logic (triangle LFOs) would see the recompiler diverge from the
   interpreter — here, a permanent ±2^31 two-sample rail bounce. Fixed across the whole family:
   single ADD/SUB (0x01/0x02), ADDC/SUBB (0x05/0x06), NEG (0x22), carry-in forms (0x25/0x26),
   INC/DEC (0x29/0x2a), and dual add/sub (0x78-0x7F). Shared helper `generate_fixed_alusat_tail`.
   The interpreter was the reference. **This is a real recompiler-vs-interpreter divergence in
   mainline MAME** and the strongest upstream candidate.
   - Perf refinement (b1028bd): ALUSAT is specialized at translation time (baked from the current
     MODE1 state; the three `generate_*_mode1_imm` writers emit a `cache_dirty` flush when the bit
     could change) so there is zero per-op overhead when saturation is off and no MODE1 load when on.

2. **Fixed-point AVG (op 0x09) in the DRC** (commit 630c68d): was falling back to the interpreter;
   now emitted natively (with the round-to-nearest caveat noted below).

## C. Correctness fixes — identified, NOT yet applied (low-risk, want a MAME A/B first)
These were found in the TRM conformance review (workflow wf_c6d2e140-eec). Each is a genuine spec
deviation; none is the KN7000 reverb-divergence cause (that was B.1), but all are worth upstreaming.
Apply + A/B a reverb WAV (the reverb exercises circular delay buffers and MACs heavily) before commit.
1. **Circular-buffer wrap off-by-one** (both engines). `UPDATE_CIRCULAR_BUFFER_{DM,PM}`
   (sharcops.hxx:37/52) and the DRC (`generate_update_circular_buffer`, COND_LE at sharcdrc.cpp)
   wrap only when `I > B+L`, but the buffer is `[B, B+L-1]`, so `I == B+L` must also wrap. One
   foreign-word access whenever the post-modified pointer lands exactly on the boundary. Fix: `>` →
   `>=` (interp) and `COND_LE` → `COND_L` at the wrap test (DRC).
   ★ VERIFIED + APPLIED-then-REVERTED 2026-07-11: the fix builds clean on both engines and the reverb
   WAV changes by exactly **2 samples / 2,112,002** (a single note) -- so the KN7000 reverb delay
   lines DO hit the exact boundary (the earlier "unchanged" belief was WRONG). The change is
   TRM-correct and inaudible on this test, but it MODIFIES the user-praised reverb, and denser/longer
   tails could differ by more, so it was reverted pending Felipe's OK rather than shipped unsupervised
   (rule g). READY TO RE-APPLY in one edit (both files, identical `>=`/`COND_L` change) when approved
   -- it is a genuine correctness fix. Both engines must be changed together to keep DRC==interpreter.
2. **Pre-modify addressing never applies circular wrap** (sharcops.hxx pre-modify DM/PM paths).
   MAME wraps only post-modify. Whether HW wraps a pre-modified circular address is specified in the
   User's Manual §4-9 (not in this TRM volume); in the KN7000 all circular delay traffic is
   post-modify (pre-modify appears only on linear I4/SPORT), so this is latent here — confirm against
   the UM before changing.
3. **Fixed AVG rounding** (op 0x09): truncates `(sum>>1)` where TRM B-10 requires round-to-nearest
   with TRUNC=0 (mean −0.25 LSB bias). Output-mix only in the KN7000; still a spec deviation.
4. **SSFR multiplier forms never round**: `compute_mul_ssfr_add/sub` (compute.hxx) and the fork's
   multifunction fixed-MAC block truncate the 1.31 result; TRM B-51/B-52 + Table B-10 require
   round-to-nearest at the MR1/MR0 boundary for register-destination fractional-R forms. (The general
   single-function MAC decode already rounds.) MR alignment itself is conformant (no x2-gain class
   error). NOTE: the reverb's sine oscillators use these SSF MACs — fix carefully, A/B required.
5. **FIX overflow without ALUSAT** returns all-1s on HW (TRM B-39) vs 0x80000000 via C++ UB in MAME;
   **`compute_fmul_fix_scaled` TRUNC direction** truncates toward zero where B-39 specifies toward
   −Infinity (standalone `compute_fix` uses floorf correctly — the pair is inconsistent).

## D. Performance (DONE) — native fixed multiply/MAC in the DRC
The SHARC DRC sent the entire fixed-point multiplier/MAC family to `generate_unimplemented_compute`
(interpreter fallback). Two distinct patches close it; BOTH are strong upstream candidates (a general
recompiler gap, not KN7000-specific) and each was verified BIT-IDENTICAL vs the interpreter (reverb WAV
md5 match, 0/2.11M samples differ), flags gated on liveness, ALUSAT baked at translation time:

1. **Native SINGLE-function fixed multiplier / MAC, signed×signed** (commit bb2d516) — the SS general
   forms **0x70-0x7f = Rx*Ry, 0xb0-0xbf = MR+Rx*Ry, 0xf0-0xff = MR-Rx*Ry**. This is the ACTUAL effects-
   kernel HOT PATH: instrumentation showed ~82M interpreter fallbacks / 22 s reverb, ~66M of them these
   SS multiplies (0x78 Rx*Ry=27M, 0xB8 MR+=15M, 0xF8 MR-=12M, 0xBC=9M, 0x7C=3M). Making them native cut
   fallbacks 82M→~3M (96%), sf-mult-SS 66M→0. Mirrors the interpreter's general fixed multiplier
   (sharcops.hxx). Unsigned/mixed-sign and SAT/RND-destination forms still fall back (rare). ★ This is the
   single highest-impact perf patch — the DRC never implemented it and every 21065L effect leans on it.
2. **Native MULTIFUNCTION fixed MAC block** (multiop 0x06, 0x08-0x12, 0x14-0x16 = `MRF ± Rx*Ry (SSF/SSFR)`
   + parallel add/sub/avg). Implemented earlier; NOTE the KN7000 kernel does NOT use this block (0 multiop
   fallbacks measured) — so its perf value is for OTHER SHARC titles, not the KN7000. 0x07/0x0f (dual
   add/sub) remain fallback.
- Plus the **fixed-point AVG (op 0x09)** native emission (commit 630c68d, listed in B.2) — the largest
  remaining single-function fallback after the multiplier (~3M/run), overflow-free signed average with
  exact AC carry.

## Upstreaming plan
Two independent headline submissions, both demonstrable DRC-vs-interpreter issues in mainline MAME:
- **B.1 (MODE1 ALUSAT)** — the CORRECTNESS headline (the recompiler silently diverged from the interpreter
  on any SHARC program with ALUSAT set). Package: ALUSAT across the DRC fixed-ALU family + the
  translation-time specialization.
- **D.1 (native single-function fixed multiplier)** — the PERFORMANCE headline (the DRC punted the entire
  fixed multiply/MAC family to the interpreter; ~66M fallbacks/run gone). Package: the SS general forms
  0x70-7f/0xb0-bf/0xf0-ff; then D.2 (multifunction MAC) + B.2 (AVG) as follow-ons.
Then (3) the C-group correctness fixes, each with its TRM citation (these change effect output → each wants
a maintainer A/B). The `adsp21065l_device` variant (A) goes separately once its memory map is datasheet-
confirmed. Keep the interpreter as the conformance oracle in the commit messages — every fix restores
DRC==interpreter or interpreter==TRM.

Ordering note: B.1 and D.1 are logically independent (correctness vs perf) and touch mostly different code
(fixed-ALU tail vs the multiplier decode), so they can be split into two clean series. Both live on the base
`adsp21062_device` (NOT the 21065L subclass), so they benefit every 2106x SHARC system in MAME. Extraction
is mechanical but hunk-by-hunk (sharcdrc.cpp has 39 hunks mixing ALUSAT/MAC/multiplier); a submission pass
should build+A/B each patch in isolation (reverb WAV md5) before sending. NOT done here (submission is
Felipe's, under his authorship); this catalogue is the complete map.

## ★ EXTRACTION — the patch series ALREADY EXISTS as clean per-fix commits (2026-07-13 audit)
The "hunk-by-hunk" worry above is OUTDATED: each B/D fix was committed as its own logical, **SHARC-only**
commit (verified: 0 non-SHARC files touched), so they are directly `git format-patch`-able -- no manual hunk
splitting needed. In THIS overlay repo (kn7000_mame):
| Fix | commit(s) | files | non-SHARC files |
|---|---|---|---|
| B.1 ALUSAT (add/sub -> whole fixed-ALU family) | **2d308c7**, then **b942366** | sharcdrc.cpp, sharc.h | 0 |
| B.1 ALUSAT translation-time specialization (+66MHz clock) | **b1028bd** | sharcdrc.cpp (+1 kn7000.cpp: the clock line -- drop that hunk) | 1 (clock only) |
| D.1 native single-function fixed multiplier (66M fallbacks) | **bb2d516** | sharcdrc.cpp | 0 |
| D.2 native multifunction fixed MAC family | **cd8c720** | sharcdrc.cpp | 0 |
| B.2 native fixed-point ALU average (op 0x09) | **e487bb7** | sharcdrc.cpp | 0 |
Extract with e.g. `git format-patch -1 2d308c7`. All target the BASE `adsp21062_device`, so they apply to any
2106x SHARC in mainline.

### APPLY-TEST vs a clean upstream MAME checkout (../mame @ 446413a7510, `git apply --check`, 2026-07-13)
- **cd8c720 (native MAC family), bb2d516 (native multiplier), e487bb7 (native DRC ALU average): APPLY
  CLEANLY to upstream as-is** -- these three PERF patches are IMMEDIATELY submittable (`git format-patch -1
  <hash>` -> send). They touch only the multiplier/MAC/average DECODE regions of sharcdrc.cpp, which
  upstream has unmodified.
- **2d308c7 / b942366 / b1028bd (ALUSAT): do NOT apply cleanly** -- the sharcdrc.cpp hunks apply (offset), but
  the **sharcops.hxx interpreter hunk fails at line 811**: 2d308c7 adds ALUSAT to the interpreter's
  parallel-op ALU (COMPUTE add/sub), and its context includes the `>> 1` AVERAGE line that commit **630c68d**
  added there first. So the ALUSAT patch DEPENDS on 630c68d's interpreter op-0x09 average. SUBMISSION ORDER
  for the correctness series: first the interpreter fixed-point AVERAGE from 630c68d (630c68d is MIXED --
  4 sharc + 2 kn7000 cache-hook files -- so extract just its sharcops.hxx op-0x09 hunk), THEN 2d308c7 ->
  b942366 -> b1028bd. Or rebase the three ALUSAT commits onto upstream to regenerate their context.
REMAINING for a real submission (Felipe's, deferred): build + reverb-WAV-A/B each patch in isolation on
upstream; rewrite commit messages with TRM citations + "restores DRC==interpreter" framing (they already
carry the essence); handle the ALUSAT/average dependency per the order above. The adsp21065l variant (A) and
the C-group correctness fixes go in their own later series. **P5 = as complete as autonomous prep can make
it: 3 perf patches are verified upstream-ready TODAY; the ALUSAT correctness series' dependency + order are
pinned; the rebase/A/B/submit finish is human-supervised (his authorship).**

## ★★ 2026-07-19 — SERIES REGENERATED against the current base; submission-ready
Base: ../mame branch kn7000-base @957e9dec1b4 (sharc files verified identical at the branch's one
local commit efc8d90bd39, so both are equivalent apply targets).

### 1. Apply status of the OLD files vs the current base (before regeneration)
- 00-consolidated: CLEAN. 04-native-fixed-mac: clean at offset -113. 05-native-single-fn: clean at
  offsets -234/-197.
- 01-alusat-add-sub: FAILED (sharcops.hxx:811). 02-alusat-full-family: FAILED (sharcdrc.cpp:4454 — it
  was diffed against the post-01 fork state, never individually applicable). 03-alusat-specialization-
  MIXED: FAILED (sharcdrc.cpp:288 + kn7000.cpp does not exist upstream).

### 2. CORRECTED dependency analysis (supersedes the 2026-07-13 audit's claim)
2d308c7's failing sharcops.hxx hunk does NOT depend on 630c68d's op-0x09 average: it patches the
**fork-only interpreter multifunction-MAC block added by 3aca274** (the `>> 1` line in its context is
that block's *parallel* average). Upstream's interpreter moreover THROWS on the general single-function
fixed multiplier forms (only 0x30/0x40/0x70/0xb0/0xb2 implemented) and on the whole multifunction
fixed-MAC block — so the fork's interpreter implementations (3aca274 slices) are required in-tree for
the "interpreter = conformance oracle" story and for interpreter-mode to run such programs at all.

### 3. Regenerated series (notes/upstream-patches/, 9 files, replaces old 01-05; 00 kept)
01-interp-fixed-avg / 02-interp-general-fixed-multiplier / 03-interp-multifunction-fixed-mac /
04-alusat-add-sub / 05-alusat-full-family / 06-alusat-specialization (kn7000.cpp 66MHz hunk DROPPED) /
07-native-fixed-mac / 08-native-single-fn-fixed-multiplier / 09-native-fixed-avg-drc.
Built by cherry-pick-rebasing the fork commits (630c68d slice -> 3aca274 slices [+2d308c7 interp hunk]
-> 2d308c7 -> b942366 -> b1028bd(-kn7000) -> cd8c720 -> bb2d516 -> e487bb7) onto 957e9dec1b4 in a
throwaway worktree. format-patch output, Felipe's authorship, upstream-facing messages (TRM citations,
DRC==interpreter framing, KN7000 named as the discovery vehicle).

### 4. A/B level achieved (autonomous ceiling)
- **Apply**: all 9 apply `git apply --check`-clean CUMULATIVELY in order on pristine 957e9dec1b4, zero
  offsets; final tree BYTE-IDENTICAL to the rebased replay of the fork commits. 01-04 and 07-09 also
  apply individually; 05/06 need their ALUSAT predecessors.
- **Compile**: every one of the 9 intermediate states passes g++ -fsyntax-only (full semantic pass) of
  sharc.cpp + sharcdrc.cpp with the real MAME flag/include set (C++20, NDEBUG). A full scratch-tree
  MAME link was NOT run (no driver exercises the SHARC in a pristine tree anyway).
- **Runtime oracle**: a pristine-upstream build cannot RUN the reverb (needs the KN7000 driver), so the
  runtime check is on the overlay build, which contains exactly the series' sharc code (verified: the
  series reproduces the fork's sharcops.hxx byte-for-byte; remaining sharcdrc deltas are the excluded
  fork-only extras listed below). Ran the money.lua reverb harness TWICE on the published binary
  (fresh default cfg, pristine SD copy, -seconds_to_run 22 -nothrottle -window, DISPLAY=:0):
  **bit-identical across runs, md5 44b09b9d0eaae59d9a65e5b4f4e72ec0**, non-silent, decaying post-
  release tail present. This is the CURRENT-ERA baseline; the historical 0787b60c baseline (preserved:
  kn7000_scratchpad_snapshot/tmp-loose-2026-07-16/ab_before.wav; money.wav de282bbb from 07-16) no
  longer applies because later intentional changes (a53fdcb release-ramp fix, effect-return routing,
  SIO-in-core) altered the WAV. Per-patch bit-identical DRC==interpreter verification was done
  HISTORICALLY at each fork commit (recorded in AUTONOMOUS-STATUS).
- Excluded fork-only sharc changes (NOT in the series, intentional): compute_fallback/shiftimm_fallback
  interpreter-fallback plumbing, SET/TOGGLE-ASTAT DRC emission, notify_pm_written, drc_sram_base/
  irq_vector_base virtuals + the whole adsp21065l_device personality (device PR), sharcfe changes.

### 5. §A datasheet cross-check (ADSP-21065L-EP.pdf + Technical Reference PDF, repo root)
The TR PDF = the User's Manual APPENDICES volume (A instruction set, B computation, E registers,
F vectors + index); chapters 1-12 (incl. ch.5 Memory) are NOT in it. EP datasheet = 14-page summary,
no address map. Confirmations from what IS there (App. F Table F-1 read visually, App. E SYSCON):
- **CONFIRMED: internal interrupt vector table base = 0x0000 8000, "the beginning of Block 0"** →
  device irq_vector_base()=0x8000 correct; internal SRAM Block 0 starts at normal-word 0x8000 → the
  PM code window at 0x8000+ is right. External vector base = 0x0002 0000.
- **CONFIRMED: RSTI = bit 1, offset 0x04** → host-booted reset PC = 0x8004 → device reset_pc()=0x8004
  (effective first executed 0x8005 via MAME's pipeline prime) correct.
- **CONFIRMED: IRQ0I = bit 8, offset 0x20** → vector 0x8020, matching the kernel's audio IRQ handler.
  SPORT vectors SPR0I 0x28 / SPT0I 0x30 etc. as modelled.
- **CONFIRMED: external memory space begins at 0x0002 0000** (external vector base + App. E IIVT text)
  → the device's external/SDRAM window from 0x20000 is right. SDRAM controller existence: EP datasheet.
- **CONFIRMED: 544K bits dual-ported on-chip SRAM in two blocks** (EP datasheet + SYSCON IMDW0/IMDW1
  per-block width bits).
- **NOT YET CONFIRMED (needs the User's Manual ch. 5, not in our PDFs): Block 1's normal-word base
  address (the RE-derived DM windows 0x9800/0xC000), the IOP-register space upper bound, and the
  invalid/noncontiguous internal ranges.** The IRQ-vector "beginning of Block 0"=0x8000 anchors the
  map; the rest of the internal layout stays RE-derived-but-consistent. → §A catalogue text above
  ("reset PC 0x20004, IRQ vector base 0x20000") described the BASE 2106x, not the 21065L device: the
  actual (and now datasheet-confirmed) 21065L values are reset 0x8004 / vectors 0x8000. Device PR is
  UNBLOCKED for the vector/reset/external-base claims; label the DM-window detail RE-derived in the PR.

### 6. Submission checklist for Felipe
1. `git checkout -b sharc-fixes upstream/master` in a MAME clone, then
   `git am notes/upstream-patches/0[1-9]-*.patch` (or apply PR A = 01+04+05+06 and PR B = 02+03+07+08+09
   separately per README).
2. Full build once (`make SUBTARGET=... `) — series states were syntax-verified here, but run the real
   link + a SHARC-using driver smoke test (any 2106x title) before pushing.
3. Runtime regression on the KN7000 fork: money.lua recipe (below) must stay bit-identical vs
   44b09b9d0eaae59d9a65e5b4f4e72ec0 whenever the overlay resyncs on top of the submitted patches.
4. PR text: lead PR A with the DRC-vs-interpreter divergence (any ALUSAT program silently wrong under
   DRC); lead PR B with the fallback numbers (82M -> <500k per 22 s). Messages already carry both.
5. Reverb recipe: `./run.sh -window -nothrottle -seconds_to_run 22 -autoboot_script money.lua
   -wavwrite out.wav -cfg_directory <fresh> -harddisk <pristine sd copy>`; money.lua = press :KEYS1
   mask 0x0100 at t=16, release t=17 (preserved in kn7000_scratchpad_snapshot/tmp-loose-2026-07-16/).

## ★ 2026-07-20 — series extended to 12: SAT MRx implemented (the Gate-Reverb gap) + last two fallbacks gone native

The instruction-coverage audit (kn7000_disassembly/dsp/instruction-coverage.md) found ONE
crash-capable gap in the whole 6,499-word effects pool: `Rn = SAT MRF (SF)` (multiplier op 0x09),
used once, by rec12 (GATE REVERB) at PM 0x8438 — executed every below-threshold sample frame, so
selecting Medium/Short/Long Gate fatal-errored both engines. Fixed + the two fallback-only classes
made native:

- **Core (overlay, both engines)**: interpreter SAT MRx family 0x00-0x0F in the general-multiplier
  `oper==0` corner (TRM B-57 semantics: format-range clamp, MR0/MR1 transfer, MN/MV/MU/MI; 64-bit MR
  model = fractional forms pass through, integer forms clamp) + DRC-native mirror (flags gated on
  liveness); DRC-native `Rn = ABS Rx` (ALU 0x30, incl. AV+STKY-AOS corner + translation-time ALUSAT
  clamp) and immediate `FDEP (SE)` (shiftop 0x13). RND MRx (0x18-0x1F) still throws — zero uses.
- **Oracle**: money.lua reverb harness on the rebuilt binary = **bit-identical**,
  md5 44b09b9d0eaae59d9a65e5b4f4e72ec0 (none of the new ops are in the non-gate reverb path).
- **Live Gate Reverb**: SOUND DSP screen → group "Reverb" (FIRST group; scroll-up rocker =
  :cpanel:CPC_SEG9 0x01) → Short Gate. Selecting uploads rec12 into effect **slot 2** (PM 0x8638 =
  the SAT word 0000305003909300, Lua-verified; slots = 0x8400+unit*0x100 — do NOT look for
  record-native addresses). 10+ s run + keybed note, no fatalerror, **both DRC and -nodrc**.
  GUI gotchas learned: the (hold-)REVERB screen does NOT contain the Gates (2 pages Room…Stadium);
  pressing the already-stored preset with the insert OFF uploads nothing — short-press SOUND DSP
  (CPR_SEG3 0x08) to toggle the insert or pick a different preset.
- **Coverage checker**: tools/check_sharc_coverage.py updated (support tables + SAT names) → exit 0;
  the used set is now **100% DRC-NATIVE** (no fallback classes remain in use).
- **Staging**: notes/upstream-patches/ now 10-sat-mr-family / 11-native-abs-drc /
  12-native-fdep-se-imm-drc; full 12-stack `git am`s clean on pristine 957e9dec1b4, series-tree
  sharc.cpp+sharcdrc.cpp pass the C++20 -fsyntax-only check. README.md updated (10 → PR B; 11/12 =
  standalone DRC-crash fixes).

## 2026-07-20: reverb-oracle baseline moved (intentional TG change)
The 7-stage amplitude-envelope implementation (kn7000.cpp 4fa66d4, decoded from the
ENVELOPE-screen sweep) changes the TG audio that feeds the oracle, so the money.lua WAV
moved -- same precedent as the a53fdcb release-ramp fix. NEW baseline on the published
binary (fresh cfg, pristine SD copy, recipe unchanged):
**md5 c3b67ea711ce3c00f8ae2af1e07651cb, bit-identical across 2 runs**, non-silent,
note decays to clean silence after release (no stuck notes). References to
44b09b9d0eaae59d9a65e5b4f4e72ec0 above are the pre-envelope era.
