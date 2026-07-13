# SHARC core fixes — upstream candidate series

The KN7000 effects DSP (ADSP-21065L) drove several fixes and additions to MAME's shared
`src/devices/cpu/sharc/` core. This file catalogues them for eventual upstreaming to MAME proper —
they are general SHARC/ADSP-2106x correctness issues, not KN7000-specific. TRM = the ADSP-21065L
SHARC DSP Technical Reference (508pp). Grouped by confidence/readiness.

## A. New device variant (KN7000-specific, but clean)
- **`adsp21065l_device`** (commit dba4bea): a 21065L subclass of the 2106x core — reset PC 0x20004,
  IRQ vector base 0x20000, internal-SRAM/SDRAM personality (code 0x8000+, data 0x9800+/0xC000+,
  external SDRAM 0x20000+, on-chip IOP register set), host-boot mode. Derived from what the recovered
  firmware actually uses; the public summary datasheet omits the internal map. Ships as its own
  device so it does not perturb the existing 21060/21062 parts. **Upstream-ready** once the memory
  map is cross-checked against a real 21065L datasheet (currently RE-derived).

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
