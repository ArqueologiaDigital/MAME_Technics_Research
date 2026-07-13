# MAME base resync — 2026-07-13

Resynced the upstream MAME base the KN7000 overlay builds on, after ~1 month of drift.

## Base moved
- **From**: `446413a7510` = `mame0288-260` (2026-06-13), on the fork branch `i7000-upstream-pr-v2`
  (which carries 6 unrelated transac/i7000 commits).
- **To**: `957e9dec1b4` = `mame0288-701` (2026-07-14), clean `upstream/master`.
- **Gap**: 447 commits, same 0.288 dev cycle (no release boundary).

## Branch layout in the `../mame` repo (do NOT lose these)
- `kn7000-base` — NEW branch at `upstream/master` (957e9dec1b4). **This is the KN7000 build base**;
  `build.sh` rsyncs from whatever `../mame` is checked out to, so keep `../mame` on `kn7000-base`
  for KN7000 work.
- `i7000-upstream-pr-v2` — UNTOUCHED, still has its 6 commits (transac/gaspump/i7000 skeleton work
  for other projects). Preserved per Felipe's request.
- `kn7000-base-446413a` — tag pinning the OLD base for Plan-B rollback.

## Two fixes the resync required (both committed with this note)
1. **SHARC fork: `drcuml_state` constructor gained a 7th param.** Upstream commit 75f8b2b1f81
   (R. Belmont, DRC sequence-length invalidation) added `max_sequence_length`. Our fork's call in
   `src/devices/cpu/sharc/sharc.cpp` now passes `COMPILE_FORWARDS_BYTES` as arg 7, matching
   upstream's own sharc.cpp.
2. **`build.sh` DRC_CPUS patch was a no-op (latent bug, exposed by the fresh build).** The idempotency
   check was `'"ADSP2106X"' not in s2`, but `"ADSP2106X"` always appears in cpu.lua as the SHARC's CPU
   token (`CPUS["ADSP2106X"]`), so the check was always false and `ADSP2106X` never got added to
   `DRC_CPUS` -> `CPU_INCLUDE_DRC` stayed false in the SHARC-only focused build -> the DRC backend
   (drcuml/drc_cache/uml) failed to link. The old build tree had it from a stale earlier state; deleting
   the tree for the fresh build exposed it. Fixed the check to look at the `DRC_CPUS = { "ADSP2106X"`
   line specifically.

## Other upstream changes to our forked files (assessed, NOT folded in)
- `spi_sdcard.cpp`: 1 commit (40d0f1125be, cosmetic `std::has_single_bit`) — our fork supersedes; skipped.
- `mn10300`: 0 upstream changes.
- The 3 scripted-patch anchors (cpu.lua MN10300, mame.lst kn5000, ui.cpp show_warnings) all still exist
  upstream and applied cleanly.

## Verified
Clean fresh build against the new base (all compiles, links). Runtime smoke test PASSED: boots,
CUSTOMIZE LED cpr_led0 0->1 on menu open, DEMO button handshake works.

## Plan-B rollback (if ever needed)
`git -C ../mame checkout kn7000-base-446413a`, then delete the build tree and rebuild — returns to the
exact pre-resync known-good state (overlay is committed; nothing destructive was done).
