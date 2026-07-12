# SHARC core fixes — upstream (MAME) submission patches

Generated from the KN7000 fork. These target MAME's shared `src/devices/cpu/sharc/` core and are
general ADSP-2106x fixes (not KN7000-specific). Full technical rationale: ../sharc-upstream-patch-series.md.

## Patches (apply in order)
1. **01-alusat-add-sub.patch** — MODE1 ALUSAT in the DRC's single ADD/SUB. THE headline: a real
   DRC-vs-interpreter divergence (the DRC wrapped fixed-point ALU results; the interpreter saturated
   per MODE1.ALUSAT, TRM B-6). Any SHARC program using saturate-then-reflect logic (triangle LFOs)
   diverges. Touches sharcdrc.cpp + sharcops.hxx (interp reference already correct).
2. **02-alusat-full-family.patch** — extends ALUSAT to the rest of the DRC integer ALU family
   (ADDC/SUBB, NEG, carry-in, INC/DEC, dual add/sub) via generate_fixed_alusat_tail. sharc.h + drc.
3. **03-alusat-specialization-MIXED.patch** — ★ NOT upstream-clean as-is: bundles the DRC
   translation-time ALUSAT specialization (upstream-worthy: bakes the flag at compile time, flushes
   the cache on MODE1 change) WITH a KN7000-specific 60->66 MHz clock change in kn7000.cpp. SPLIT
   before submitting: keep the sharcdrc.cpp hunk, drop the kn7000.cpp hunk.
4. **04-native-fixed-mac.patch** — native UML for the multifunction fixed-point MAC family (multiop
   0x06/0x08-0x16 = MRF±Rx*Ry SSF/SSFR + parallel add/sub/avg), which the SHARC DRC never
   implemented (was interpreter fallback). Verified BIT-IDENTICAL vs the interpreter.

5. **05-native-single-fn-fixed-multiplier.patch** — native UML for the SINGLE-function fixed-point
   multiplier (signed*signed general forms 0x70-0x7f/0xb0-0xbf/0xf0-0xff = Rx*Ry / MR+Rx*Ry / MR-Rx*Ry).
   The DRC sent the ENTIRE fixed multiplier family to the interpreter; this is a real hot path (measured
   ~66M interpreter fallbacks per second of SHARC audio DSP -- the single-function multiplier, distinct
   from #4's multi-function MAC). Verified BIT-IDENTICAL vs the interpreter. Unsigned/mixed-sign + SAT/RND
   forms still fall back (can be added later). sharcdrc.cpp only; upstream-clean.

## Verification standard
Every fix restores DRC == interpreter (or interpreter == TRM). The reverb WAV A/B (bit-identical
before/after) is the oracle used throughout the KN7000 work.

## Not included (documented in the catalogue, want a maintainer's call / more testing)
- Circular-buffer wrap off-by-one (`>` vs `>=`): correct per TRM but changes output by ~2 samples on
  the KN7000 reverb (delay lines DO hit the boundary) -- held.
- AVG/SSFR rounding, FIX-overflow UB, pre-modify circular wrap: identified spec deviations, low-risk,
  each with a TRM citation in the catalogue.

## Note
These are session-generated convenience patches; the canonical source is the fork's git history
(commits 2d308c7, b942366, b1028bd, cd8c720). A maintainer PR should cherry-pick + split #3.
