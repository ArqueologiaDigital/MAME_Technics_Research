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
   `>=` (interp) and `COND_LE` → `COND_L` at the wrap test (DRC). The RE notes record that this fix
   leaves the reverb output unchanged (the delay lines rarely hit the exact boundary), so it is safe.
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

## D. Performance opportunity (not a correctness issue)
- **Native UML for the multifunction fixed MAC block** (multiop 0x06, 0x08-0x12, 0x14-0x16 =
  `MRF ± Rx*Ry (SSF/SSFR)` with a parallel add/sub half). These currently fall back to
  `generate_unimplemented_compute` (a per-instruction interpreter call) and sit in the effect
  kernel's per-frame hot path (the reverb's sine oscillators + delay interpolation). Native emission
  would remove the fallback call overhead. Correctness-critical (MR alignment, SSF vs SSFR rounding
  per C.4 above, the parallel-half flags) — implement against the interpreter as reference and A/B a
  reverb WAV bit-for-bit. Tracked as an open perf item.

## Upstreaming plan
B.1 (ALUSAT) is the headline and cleanest submission (a demonstrable DRC-vs-interpreter divergence).
Package as: (1) ALUSAT across the DRC fixed ALU family + the translation-time specialization; (2) the
C-group correctness fixes as a follow-up, each with its TRM citation. The `adsp21065l_device` variant
(A) can go separately once its memory map is datasheet-confirmed. Keep the interpreter as the
conformance oracle in the commit messages — every fix here restores DRC==interpreter or
interpreter==TRM.
