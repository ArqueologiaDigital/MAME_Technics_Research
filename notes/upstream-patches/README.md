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

# KN5000 driver series (kn5000-01 … kn5000-29)

**Added 2026-07-20.** Everything the KN5000 has that upstream MAME does not, extracted from the
local MAME tree's unmerged branches and rebased onto `kn7000-base` (= upstream + the cpanel-ioport
move). The same files are carried as overlay files in `src/` and symlinked by `build.sh`, so the
overlay and this series are two views of one thing.

**Verified 2026-07-20**: `git am kn5000-*.patch` on a pristine `kn7000-base` worktree applies all
25 with zero fuzz, and the resulting tree is **byte-identical** to the overlay files in `src/`
(13 files compared with `cmp`). The overlay builds and `-validate kn5000` passes.

Provenance: `kn5000_pr6` (18 commits, rebased — the 3-way merge dropped the parts of its "major
rework" commit that upstream had already merged as PR #15143 and kept the rest), plus six
cherry-picks from `kn5000_research_tonegen`, plus the two `kn5000_research_datawheel` commits
squashed and re-implemented against the device-owned input ports. AI co-authorship trailers were
stripped: submission is under the project owner's authorship.

| # | file | what |
|---|---|---|
| 01 | kn5000-01-driver-rework-subcpu-payload-cpanel-keybed.patch | SubCPU payload load, NVRAM factory-defaults init (`nvram2_init`, checksum matching LABEL_FEF93B), 61-key keybed HLE feeding the tone generator FIFO at 0x110000 |
| 02 | kn5000-02-tmp94c241-16bit-timer-irq.patch | **CPU core**: 16-bit timer interrupt generation + flip-flop gating |
| 03 | kn5000-03-fdc-address-map-portd.patch | FDC address mapping and PORT D bit 6 (dskchg) |
| 04 | kn5000-04-tmp94c241-8bit-uart.patch | **CPU core**: 8-bit UART mode for the serial channels (this is what makes MIDI possible) |
| 05 | kn5000-05-midi-output-tx0.patch | MIDI out via TX0 → `midi_port` |
| 06 | kn5000-06-fdc-registers-pc-at.patch | FDC register layout corrected to the PC AT arrangement |
| 07-13 | kn5000-07…13 | `kn5000_tonegen_device` (IC303) and its seven refinement steps: PCM playback, pitch register location + scaling, volume semantics, stereo pan, waveform select, release envelope, linear interpolation |
| 14 | kn5000-14-dsp1-stub-ic311.patch | `kn5000_dsp1_device` stub (IC311 DS3613GF-3BA) |
| 15 | kn5000-15-floppy-dd-to-hd.patch | floppy drive type DD → HD |
| 16 | kn5000-16-timer0-to-fdc-tc.patch | Timer 0 output (TO0) → FDC Terminal Count |
| 17 | kn5000-17-code-style-cleanup.patch | upstream style compliance |
| 18 | kn5000-18-sns-nmi-payload-checksum.patch | SNS NMI payload checksum via a boot-time write tap — gives NVRAM persistence without a core change |
| 19 | kn5000-19-hdae5000-ata-intrq.patch | HD-AE5000: real `ata_interface_device` + INTRQ → INT9, CS0/CS1 split; drops `feature::DISK` |
| 20 | kn5000-20-mn89304-vga-findings.patch | documents the MN89304 LCD controller (4-bit RAMDAC, 8x row-offset, extended SEQ/CRTC) |
| 21-24 | kn5000-21…24 | tone-gen voice hold timer, DSP1 ready → SubCPU Port H bit 0, removal of the Feature Demo stuck-parts workaround, and the final voice-timing fix for the undumped waveform ROMs |
| 25 | kn5000-25-program-data-wheel.patch | TEMPO/PROGRAM data wheel: an infinite relative encoder owned by the cpanel device, declared as an adjuster and reported as the segment 0x0B status byte (bit 7 CW / bit 6 CCW, neutral 0x00 on stop) that the firmware reads at DRAM[0x8E55]; wrap-aware per-scan delta slewed one detent per packet, plus a draggable layout knob using the shared slider/knob library. **Held back deliberately — see below.** |
| 26 | kn5000-26-intercpu-latch-int0-handshake.patch | **CPU core + driver (regression fix, 2026-07-20).** Restores the inter-CPU-latch INT0/handshake workarounds dropped in the PR-branch cleanup (fixes 10 & 12 in kn5000-docs/subcpu-payload-loading.md): `tmp94c241_device::clear_int0_level()` + its use from the latch READ wrappers (synchronously clear the receiver's `/INT0`, which `generic_latch::read()` otherwise only de-asserts through a deferred `synchronize()`, causing spurious per-byte ISR re-fires), and `acknowledge_w(0)`-if-pending + `abort_timeslice()` in the latch WRITE wrappers. Without these the 192 KB SubCPU payload arrived scrambled → "Sound Name Error". After: decompressed payload bit-identical to the reference ROM. **Belongs logically in patch 01's driver + patch 02's core on the next full regeneration; kept as a separate incremental patch here to avoid disturbing the byte-identical-verified 01-25 stack.** Note it does NOT by itself clear the on-screen error — the SubCPU reply path (missing DSP2/ComIF/serial wiring) is a separate follow-up. |
| 27 | kn5000-27-intercpu-parity-int0-mstat.patch | **CPU core + driver (parity fix, 2026-07-20).** Two more inter-CPU workarounds the upstream-cleanup rebase dropped vs the working `kn5000_aided_by_claude` branch: (a) `tmp94c241::tlcs900_check_irqs` no longer re-asserts the INT0 level-detect flag after taking the IRQ (re-asserting spins INT0 before the SubCPU handshake resolves and starves the cooperative scheduler); (b) the KN5000 MainCPU Port Z read restores the MSTAT read-back (`m_mstat | com_select | (sstat<<2)`) — bits 0-1 are the MainCPU's own MSTAT outputs, which real hardware reads back and the firmware uses to track the handshake. KN5000-only; `-validate` clean for all five models; KN7000 home unaffected. **These are necessary parity fixes but do NOT by themselves clear "Sound Name Error"** — the remaining cause is a SubCPU receive-HDMA-ch0 / cooperative-scheduler deadlock (the scheduler idles with no ready task and its XSSP leaks into the code); fully characterised in `side-quests/findings/kn5000_driver_findings.md` (2026-07-20 deep trace). Belongs logically in patch 01/02 on the next full regeneration; kept incremental to preserve the byte-identical 01-25 stack. **SUPERSEDED by kn5000-28 — kn5000-26/27 matched the aided-branch *tip*, which the oracle bisect proved is itself broken.** |
| 28 | kn5000-28-int0-reassert-portz-2026-02-17-oracle.patch | **CPU core + driver (regression fix, 2026-07-20 — oracle bisect).** The oracle-timeline bisect proved the `kn5000_aided_by_claude` *tip* (2da2648) is broken with the identical "Sound Name Error", and that the true last-known-good state is the **2026-02-17** commit `f8cd34a8` — built as an oracle it shows real names (Piano / Bigband Brass / Modern E.P.1), keeps XSSP bounded and the SubCPU scheduler alive. Corrects kn5000-27 (which matched the broken tip) toward that oracle: (a) `tmp94c241::tlcs900_check_irqs` restores the **guarded** INT0 level-detect re-assertion — re-assert `INTE0AD |= 0x08` only when no HDMA channel steals INT0 (`m_dma_vector[ch] != 0x0a`); the ISR-driven receive path needs this or a still-pending, still-asserted /INT0 byte is never re-serviced (path-3 stall), while an unconditional re-assert would spuriously re-read stale latch data during HDMA body transfers; (b) MainCPU Port Z read drops the MSTAT read-back (the oracle reads back only `COM_SELECT | (SSTAT<<2)`). KN5000-only; `-validate` clean; KN7000 home unaffected (MN10300). **Necessary but NOT sufficient** — with both applied the receive still freezes (n=480 @ t≈9.8, XSSP still leaks). The remaining cure is the SubCPU cooperative-scheduler *pacing* stall: the overlay bursts the ~480-block payload transfer in ~8 s where the oracle paces it over ~24 s (giving the scheduler time to run every task between blocks), traceable to the SubCPU peripheral work the overlay dropped vs 2026-02-17 (the SC1 Computer-Interface INTTX1/INTRX1 heartbeat that wakes a scheduler task — census: oracle 21× INTRX1, overlay 0×; plus DSP2/MN19413 and the audio-mixer window). Full write-up in `side-quests/findings/kn5000_driver_findings.md` (2026-07-20 oracle bisect). **The actual root cause turned out to be elsewhere — see kn5000-29; the re-assert/Port-Z corrections here are correct alignments to the 2026-02-17 oracle but were not the cure.** |
| 29 | kn5000-29-remove-sns-checksum-tap-soundname-cure.patch | **★ THE "Sound Name Error" CURE (driver, 2026-07-20 — third oracle = upstream mainline).** Building CURRENT upstream mainline MAME's kn5000 as a third oracle showed it **works** (real names) despite being a minimal skeleton (raw inter-CPU latch, no ComIF/DSP2, none of this overlay's HLE) — the one thing it lacks is this overlay's **SNS payload-checksum write tap**. That tap intercepted Boot_DisplayScreen's clearing of MainCPU DRAM[0xFFD4] and substituted a checksum computed from the DRAM checksum regions (0xF180/0xF980) at that early instant. The firmware's `SubCPU_Payload_Verify` reads DRAM[0xFFD4]==0 as "no stored checksum → do a FRESH decompress-and-transfer of the SubCPU firmware payload"; the tap's non-zero (wrong-for-that-moment) value instead sent it down "payload already valid → skip transfer", so the SubCPU ran with no/stale firmware, never answered the 0x2B sound-name query, and its cooperative scheduler idled with no ready task and leaked its stack (the INTT3 leak documented in kn5000-28's notes). Removing the tap restores the fresh transfer. **Isolation:** with ONLY the tap removed (overlay tmp94c241/latch/HLE otherwise unchanged) **all three names appear — RIGHT1 Piano, RIGHT2 Bigband Brass, LEFT Modern E.P.1 — on both fresh and persisted NVRAM, and XSSP stays bounded ~0x40680 across 40 s (no leak)**; the exploratory upstream-tmp94c241 / raw-latch / HLE-stub swaps are NOT needed. KN5000-only; `-validate` clean; KN7000 home unaffected; payload path untouched (e6b4cf7 preserved). |

### Suggested split into PRs
- **PR 6 (peripherals)**: 01-17 — the cohesive "bring the rest of the KN5000 online" batch that the
  branch review already proposed. 02 and 04 touch the shared TMP94C241 core and could be split out.
- **PR 7 (NVRAM persistence)**: 18, standalone.
- **PR 8 (HD-AE5000 + misc research)**: 19-24.
- **PR 9 (data wheel)**: 25. **Keep this one last and hold it back until the firmware path is
  resolved.** The transport it implements is verified correct against the firmware's own boot-time
  `20 0B` query (segment 0x0B lands in DRAM[0x8E55] as 0x80/0x40 with the neutral 0x00 in between),
  but the KN5000 firmware consumes that byte **only during boot**: in steady state it never requests
  or stores it, and the UI is driven from a different, signed path (SwbtWr event type 0xA9, payload
  0x21 at DRAM[0xC07D], routed through a ±7 acceleration table at ROM 0xEA98E2) whose producer lives
  in the not-yet-disassembled NAKA ROM region. So turning the wheel is **not yet visible on screen**.
  The patch is worth keeping staged — the input, the widget and the encoding are right — but it
  should not be submitted as a working feature. Full evidence:
  `KN7000/side-quests/findings/kn5000_data_wheel_findings.md`.

### Deliberately NOT in the series
- `kn5000_power_off_nmi` (2 commits) adds a **core** `MACHINE_NOTIFY_POWER_OFF` machine phase. Patch
  18's write-tap achieves the same NVRAM result without touching core MAME, so the core change is
  left as a reference approach only, not staged for submission.
- `kn5000_research_techmanager` (9 commits): the KN5000-as-a-centronics-peripheral-of-a-PC rig for
  TechManager5000, including a `kn5000_cable` device, a `pc_lpt` PS/2 bidirectional mode and a
  refactor of `kn5000_state` from `driver_device` to `device_t`. Genuinely interesting research, but
  a whole architecture on its own and not close to PR shape.
- `kn5000_pr6_hdae5000` (1 commit) is an earlier form of what patch 19 does.
- The SSF slide-transition experiment on `kn5000_research_tonegen` was reverted by its own author on
  the branch; the revert pair is skipped.
