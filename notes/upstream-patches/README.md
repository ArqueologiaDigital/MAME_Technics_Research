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

# KN5000 driver series (kn5000-01 … kn5000-30)

## ⛔ SUBMISSION HOLD on kn5000-30 (added 2026-07-21) — do NOT submit it as it stands

> Full state, artefact map and measurement rules for this hold: **`notes/kn5000-cpserial-INDEX.md`**.

**`kn5000-30` is correct about phantom bytes and incomplete about everything else. Submitting it
alone would export a worse bug than the one it fixes.** It must not go upstream until the link is
actually fixed (see below). Everything else in the series is unaffected.

**★ HOLD REAFFIRMED 2026-07-21 (second adjudication).** The receiver-side resync (option B) that
this hold was originally waiting for has now been implemented and verified three ways, and it is a
**bit-for-bit no-op** — it cannot even execute after a wedge. Its reachable variants (B+C and B′)
restore bit framing but still dispatch **false button presses** on the `b3` repro, which is exactly
what option C was rejected for. So the hold does **not** lift, and the remaining route is the
sender-side handshake (option A). Details below and in
`notes/kn5000-cpserial-receiver-resync-candidate.md`.

**★★ HOLD REAFFIRMED AGAIN 2026-07-21 (third adjudication — option A).** The sender-side handshake
was implemented in full (polite sender *and* the modelled SCLK-low bus request on PF.6) and verified
three ways. It is a big improvement on paper — `a1`, `b1`, `b3`, the whole phase sweep and the
444-press soak all go from DEAD to LIVE, and the boot-window phase stops deciding the outcome — but
it is **rejected**, because it breaks configurations the shipped build handles:
`x_sim2` (two buttons pressed at the same instant) goes LIVE→**DEAD plus a false ENTERTAINER
dispatch**, and `pfx3` (three presses from a cold boot) turns `RIGHT1 Piano` into
`RIGHT1 Sound Name Error`. Both reproduced independently, byte-identical md5s. The fault is one
block — the "only ask for a bus that is free" deferral in `idle_detect_callback` — which re-phases
the INTA request into the middle of the firmware's receiver teardown, after which the 100 ms
liveness valve *rewinds a byte the CPU has already partly taken*: A's escape hatch manufactures the
misframe A existed to avoid. Full adjudication and the patch:
`notes/kn5000-cpserial-sender-handshake-candidate.{md,patch}`. **Three candidates have now been
built and rejected at this step; the hold stays until one passes on the whole repro suite,
`x_sim2` and `pfx3` included.**

kn5000-30 gates the RX latch on the external clock. That kills the 521 phantom bytes exactly as
claimed. It also opens a **mid-byte gate-close race** that did not exist before it: if the firmware
clears IOC while the control panel is still shifting a byte in, `m_rx_clock_count` is stranded at
1..7, the `(m_rx_clock_count != 8)` term in `timer_callback`'s `need_clock` is then permanently
true, and the internal baud generator **free-runs forever** — 663,146 to 3,221,718 dead edges
measured. Those edges retrigger the cpanel's 50 µs sliding idle detector faster than it can expire,
so INTA is never re-asserted and **the panel link is dead for the rest of the session**. Repro: a
handful of button presses during the boot window plus a later burst; the boot-window presses lose
nothing themselves, they shift the phase of the panel's packet cadence so a later packet collides.
Pre-30 the bit counter always self-cleared within 8 edges, so this could not happen.

Felipe's hardware testimony (he owns and plays a real KN5000): *"the original KN5000 control panel
does not get corrupted by button presses during the boot sequence."* So this is an emulation defect,
not faithful behaviour, and "it matches hardware" is not an available defence.

**The trade kn5000-30 currently makes: 521 phantom bytes that always scrambled but always
recovered, exchanged for 0 phantoms plus a phase-dependent condition that kills the link outright.**

What must land with it, in order of preference:

- **A — sender-side handshake. IMPLEMENTED, MEASURED, ADJUDICATED A REGRESSION, NOT LANDED
  (2026-07-21).** The panel re-arms instead of clocking while the CPU's receiver is closed
  (`IOC && RXE` fanned out from the serial core), holds its shift register on the CPU's own command
  clock, and requests the bus by pulling SCLK low on PF.6 as `CPanel_SM_StartTX:781-787` expects.
  It fixes far more than B or C ever did — every known pre-existing repro goes LIVE and the boot
  phase stops mattering — but it **breaks two configurations the shipped build handles**:
  `x_sim2` (two simultaneous presses) → dead panel + a false ENTERTAINER dispatch, and `pfx3`
  (three presses from cold boot) → `Sound Name Error`. Isolated to the `idle_detect_callback`
  "only ask for a bus that is free" deferral plus the `abandon_inta_cycle()` rewind; disabling only
  that deferral restores the pristine screens on both repros, which makes **A′ = A minus rule 5**
  the obvious next candidate — but it must be measured on the whole suite, not on the two repros
  that motivated it. Full adjudication and the patch:
  `notes/kn5000-cpserial-sender-handshake-candidate.{md,patch}`.
  → `KN7000/side-quests/pending/kn5000_cpserial_sender_handshake.txt`
  **Recorded there, not landed:** the `IOC && RXE` fan-out itself is a genuine fidelity improvement
  (RXE is set at exactly one site in v10 and cleared at seven) and is worth keeping in any successor;
  and `drop_ext == 0`, A's own headline acceptance number, is a **tautology** under A — do not accept
  it as evidence again.
- **B — receiver-side byte-boundary resync. IMPLEMENTED, MEASURED, ADJUDICATED INERT, NOT LANDED
  (2026-07-21).** Resetting `m_rx_clock_count = 8` on the **closed→open gate transition only** is a
  **bit-for-bit no-op on every known repro**, because the wedge destroys B's own precondition: the
  free-running generator keeps the cpanel's idle detector retriggered, INTA never returns, the ISR
  never sets IOC=1, and the transition B waits for never happens (`resync = 0` everywhere;
  `wclose = wopen + 1` in every wedged run). Worse, the two variants that make it *reachable* —
  B+C, and the strictly better "hold the counter in reset for the whole shut window" (B′, which
  makes C unnecessary by construction) — both reproduce **option C's rejection symptom** on the
  `b3` repro: a phantom `<Db>` on a FIRST boot from empty NVRAM, dead MENU presses, a press landing
  on the wrong part. Byte-boundary resync restores **bit** framing, not **packet** framing.
  Full adjudication, the patch and the deterministic repros:
  `notes/kn5000-cpserial-receiver-resync-candidate.{md,patch}`, `notes/kn5000-cpserial-repros/`.
  → `KN7000/side-quests/pending/kn5000_cpserial_receiver_resync.txt`
  **Fidelity item recorded there, not landed:** if a receiver-side resync is ever revisited, the
  gate must first move from IOC to **RXE** (SC1MOD bit 5, unmodelled). The claim that the firmware
  always moves the two together is false — `cpanel_routines.s` writes IOC alone at eleven sites —
  and a resync makes that skew load-bearing.
- **C — livelock guard. IMPLEMENTED, MEASURED, ADJUDICATED NOT READY, NOT LANDED.** Qualifying the
  `(m_rx_clock_count != 8)` term removes the free-run but **not** the wedge: framing loss alone can
  still kill the panel (reproduced), no strand ever resyncs (`ll_exit_clean = 0` across 342 exits in
  two independent passes), and keeping the link alive while permanently misframed makes the machine
  dispatch **false button presses the user never made** — phantom transposes `<Db>`/`<D >`/`<G >`,
  spurious PANEL MEMORY recalls, MENU:DISK opening ENTERTAINER. Full adjudication and the patch
  itself: `notes/kn5000-cpserial-livelock-guard-candidate.md` + `.patch`.

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
| 25 | kn5000-25-program-data-wheel.patch | TEMPO/PROGRAM data wheel: an infinite relative encoder owned by the cpanel device, declared as an adjuster and driven interactively. On each detent the HLE deposits the wheel's scan-table entry `[0x19, ±delta, 0xFF]` at MainCPU DRAM 0x8E94 — the table the firmware's main-loop poll `Encoder_ValueScanAndSync` consumes (descriptor 0x19 → SwbtWr 0xA9/0x21 → UI event 0x1C0001F → focused dial handler). Sign-inverted (CW = tempo up) per the ROM 0xEA98E2 accel curve; wrap-aware per-scan delta slewed one detent per entry, plus a draggable layout knob using the shared slider/knob library. **WORKING & verified on screen** — turning the wheel steps the on-screen tempo one BPM per detent, up for CW / down for CCW, and holds when it stops. Kept last in the series (a small HLE poke of the tonegen encoder register, honestly noted in the code). |
| 26 | kn5000-26-intercpu-latch-int0-handshake.patch | **CPU core + driver (regression fix, 2026-07-20).** Restores the inter-CPU-latch INT0/handshake workarounds dropped in the PR-branch cleanup (fixes 10 & 12 in kn5000-docs/subcpu-payload-loading.md): `tmp94c241_device::clear_int0_level()` + its use from the latch READ wrappers (synchronously clear the receiver's `/INT0`, which `generic_latch::read()` otherwise only de-asserts through a deferred `synchronize()`, causing spurious per-byte ISR re-fires), and `acknowledge_w(0)`-if-pending + `abort_timeslice()` in the latch WRITE wrappers. Without these the 192 KB SubCPU payload arrived scrambled → "Sound Name Error". After: decompressed payload bit-identical to the reference ROM. **Belongs logically in patch 01's driver + patch 02's core on the next full regeneration; kept as a separate incremental patch here to avoid disturbing the byte-identical-verified 01-25 stack.** Note it does NOT by itself clear the on-screen error — the SubCPU reply path (missing DSP2/ComIF/serial wiring) is a separate follow-up. |
| 27 | kn5000-27-intercpu-parity-int0-mstat.patch | **CPU core + driver (parity fix, 2026-07-20).** Two more inter-CPU workarounds the upstream-cleanup rebase dropped vs the working `kn5000_aided_by_claude` branch: (a) `tmp94c241::tlcs900_check_irqs` no longer re-asserts the INT0 level-detect flag after taking the IRQ (re-asserting spins INT0 before the SubCPU handshake resolves and starves the cooperative scheduler); (b) the KN5000 MainCPU Port Z read restores the MSTAT read-back (`m_mstat | com_select | (sstat<<2)`) — bits 0-1 are the MainCPU's own MSTAT outputs, which real hardware reads back and the firmware uses to track the handshake. KN5000-only; `-validate` clean for all five models; KN7000 home unaffected. **These are necessary parity fixes but do NOT by themselves clear "Sound Name Error"** — the remaining cause is a SubCPU receive-HDMA-ch0 / cooperative-scheduler deadlock (the scheduler idles with no ready task and its XSSP leaks into the code); fully characterised in `side-quests/findings/kn5000_driver_findings.md` (2026-07-20 deep trace). Belongs logically in patch 01/02 on the next full regeneration; kept incremental to preserve the byte-identical 01-25 stack. **SUPERSEDED by kn5000-28 — kn5000-26/27 matched the aided-branch *tip*, which the oracle bisect proved is itself broken.** |
| 28 | kn5000-28-int0-reassert-portz-2026-02-17-oracle.patch | **CPU core + driver (regression fix, 2026-07-20 — oracle bisect).** The oracle-timeline bisect proved the `kn5000_aided_by_claude` *tip* (2da2648) is broken with the identical "Sound Name Error", and that the true last-known-good state is the **2026-02-17** commit `f8cd34a8` — built as an oracle it shows real names (Piano / Bigband Brass / Modern E.P.1), keeps XSSP bounded and the SubCPU scheduler alive. Corrects kn5000-27 (which matched the broken tip) toward that oracle: (a) `tmp94c241::tlcs900_check_irqs` restores the **guarded** INT0 level-detect re-assertion — re-assert `INTE0AD |= 0x08` only when no HDMA channel steals INT0 (`m_dma_vector[ch] != 0x0a`); the ISR-driven receive path needs this or a still-pending, still-asserted /INT0 byte is never re-serviced (path-3 stall), while an unconditional re-assert would spuriously re-read stale latch data during HDMA body transfers; (b) MainCPU Port Z read drops the MSTAT read-back (the oracle reads back only `COM_SELECT | (SSTAT<<2)`). KN5000-only; `-validate` clean; KN7000 home unaffected (MN10300). **Necessary but NOT sufficient** — with both applied the receive still freezes (n=480 @ t≈9.8, XSSP still leaks). The remaining cure is the SubCPU cooperative-scheduler *pacing* stall: the overlay bursts the ~480-block payload transfer in ~8 s where the oracle paces it over ~24 s (giving the scheduler time to run every task between blocks), traceable to the SubCPU peripheral work the overlay dropped vs 2026-02-17 (the SC1 Computer-Interface INTTX1/INTRX1 heartbeat that wakes a scheduler task — census: oracle 21× INTRX1, overlay 0×; plus DSP2/MN19413 and the audio-mixer window). Full write-up in `side-quests/findings/kn5000_driver_findings.md` (2026-07-20 oracle bisect). **The actual root cause turned out to be elsewhere — see kn5000-29; the re-assert/Port-Z corrections here are correct alignments to the 2026-02-17 oracle but were not the cure.** |
| 29 | kn5000-29-remove-sns-checksum-tap-soundname-cure.patch | **★ THE "Sound Name Error" CURE (driver, 2026-07-20 — third oracle = upstream mainline).** Building CURRENT upstream mainline MAME's kn5000 as a third oracle showed it **works** (real names) despite being a minimal skeleton (raw inter-CPU latch, no ComIF/DSP2, none of this overlay's HLE) — the one thing it lacks is this overlay's **SNS payload-checksum write tap**. That tap intercepted Boot_DisplayScreen's clearing of MainCPU DRAM[0xFFD4] and substituted a checksum computed from the DRAM checksum regions (0xF180/0xF980) at that early instant. The firmware's `SubCPU_Payload_Verify` reads DRAM[0xFFD4]==0 as "no stored checksum → do a FRESH decompress-and-transfer of the SubCPU firmware payload"; the tap's non-zero (wrong-for-that-moment) value instead sent it down "payload already valid → skip transfer", so the SubCPU ran with no/stale firmware, never answered the 0x2B sound-name query, and its cooperative scheduler idled with no ready task and leaked its stack (the INTT3 leak documented in kn5000-28's notes). Removing the tap restores the fresh transfer. **Isolation:** with ONLY the tap removed (overlay tmp94c241/latch/HLE otherwise unchanged) **all three names appear — RIGHT1 Piano, RIGHT2 Bigband Brass, LEFT Modern E.P.1 — on both fresh and persisted NVRAM, and XSSP stays bounded ~0x40680 across 40 s (no leak)**; the exploratory upstream-tmp94c241 / raw-latch / HLE-stub swaps are NOT needed. KN5000-only; `-validate` clean; KN7000 home unaffected; payload path untouched (e6b4cf7 preserved). |
| 30 | kn5000-30-cpserial-rx-phantom-byte-gate.patch | **⛔ SUBMISSION HOLD (reaffirmed twice on 2026-07-21) — see the hold notice at the top of this section; do NOT submit without a fix for the mid-byte gate-close race landed in the SAME PR, and none has passed yet: all three candidates — C (livelock guard), B (receiver-side resync) and A (sender-side handshake) — were built, verified three ways and rejected. B is measurably INERT and its reachable variants dispatch false button presses; A fixes every previously known repro but regresses two schedules the shipped build handles (`x_sim2`, `pfx3`). This patch is correct about phantom bytes but opens a mid-byte gate-close race that can kill the panel link for the whole session.** **★ CONTROL-PANEL "scrambled buttons" CURE (shared CPU-serial core, 2026-07-21 — upstream-relevant).** The panel occasionally responded to a press with the wrong function and put a phantom `<Db>` transpose on the home screen that nobody asked for. Root cause is in the **shared** TMP94C241 synchronous-serial model, not any button table (the SEG.bit map, layout inputtags and cpanel dispatch were byte-verified identical to upstream). `tmp94c241_serial_device::sioclk()` latched an RX byte + fired INTRX on **every** 8 rising edges regardless of clock source; while the CPU is the clock master transmitting a command (internal baud generator, IOC=0) those same edges also completed a bogus full-duplex "RX during TX" byte from the idle RXD line — one **phantom byte per command byte sent**. A phantom `0x00` decodes as right-panel segment 0 = the TRANSPOSE row (the `<Db>`), and an odd phantom count inside a framed burst swaps the (header,state) pairing, so PIANO (seg2,0x01) reads as (seg1,0x02) = ORCHESTRAL PAD — timing-dependent, hence intermittent. **Behavioural oracle diff** (instrument both ends): the cpanel `send_byte()` count exactly equals the *externally clocked* (IOC=1) RX bytes — 190==190 — while every phantom is internally clocked with IOC=0 (521 of them), a perfect partition with zero cross terms. Fix: gate the RX bit-count/latch on the external clock actually being selected (`(SCxMOD&3)==0 && IOC`), mirroring the sender's own start-gate and the existing internal-clock suppression in `timer_callback`. After: **sent == received (96==96, all IOC=1), phantoms 521→0, no phantom transpose**; every silk-labelled press opens its promised screen (PIANO→SOUND PIANO, DISK→DISK MENU, MENU:SOUND→SOUND MENU, MENU:MIDI→MIDI, part-select) from a clean home savestate at three different emulated phases each. UART transfer modes drive their RX from `timer_callback`, so this synchronous-mode gate never touches MIDI. KN5000/KN1500 device only (KN7000/KN6000 are MN10300); `-validate` clean for kn5000/kn1500/kn7000/kn6000/kn6500/kn2400; sound names (kn5000-29) and tempo wheel (kn5000-25) intact; KN7000 reverb path untouched. **This bug almost certainly affects mainline MAME's PR5 KN5000 panel too** — and so, now, does the livelock it introduces, which is exactly why it must not be submitted alone. |

### Suggested split into PRs
- **PR 6 (peripherals)**: 01-17 — the cohesive "bring the rest of the KN5000 online" batch that the
  branch review already proposed. 02 and 04 touch the shared TMP94C241 core and could be split out.
- **PR 7 (NVRAM persistence)**: 18, standalone.
- **PR 8 (HD-AE5000 + misc research)**: 19-24.
- **PR 9 (data wheel)**: 25. **WORKING — turning the wheel now edits the on-screen tempo** (up for
  clockwise, down for counter-clockwise, one BPM per detent, holding when it stops), verified live.
  The wheel is not a control-panel-serial input in steady state: the firmware reads it with a
  main-loop poll, `Encoder_ValueScanAndSync` (ROM 0xFC5761), which walks an encoder scan table at
  MainCPU DRAM 0x8E94 — 3-byte entries `[record_id, delta, mask]`. record_id 0x19 selects descriptor
  0xED9C1E[0x19] = {A9,21,00,FF}, emitting SwbtWr event 0xA9/0x21 (DRAM 0xC07D=0x21, 0xC07E=signed
  delta) → UI event 0x1C0001F → the focused widget's dial handler (the tempo box on the home screen).
  So the cpanel HLE deposits that entry directly on each detent (sign-inverted via the ROM 0xEA98E2
  accel curve so CW raises the tempo), respecting the firmware's idle discipline (it clears the table
  to 0xFF each main-loop iteration, so an entry is re-presented per detent and nothing is written
  while the wheel is still). Kept last in the series because the poke is a high-level model of the
  tone-generator encoder register that feeds 0x8E94 — a fully device-accurate model would emulate
  that register so the firmware's poll reads the wheel naturally (noted in the code). Full evidence:
  `KN7000/side-quests/findings/kn5000_data_wheel_findings.md`.

- **PR 10 (control-panel serial) — ⛔ BLOCKED**: 30. Not submittable on its own; it needs a fix for
  the mid-byte gate-close race landed alongside it, and **all three candidates have now been built,
  verified three ways each, and rejected**: C (livelock guard) is a guard, not a cure and dispatches
  false presses; B (receiver resync) is measurably **inert**, and both of its reachable variants
  dispatch false presses on `b3`; A (sender handshake) fixes every previously known repro but
  **regresses** `x_sim2` and `pfx3` against the shipped build. See the submission hold at the top of
  this section. When a successor does pass, note that the fix and `kn5000-30` **must travel
  together in this same PR** — 30 alone exports the livelock, and a sender-side fix alone would sit
  on top of the phantom bytes 30 removes. A is driver-side (`kn5000_cpanel.*`, `kn5000.cpp`) plus a
  small callback in the shared `tmp94c241_serial` core, whereas B was purely core, so a successor
  along A's lines is a natural single PR with 30. Patches 26-29 are unaffected and independent of
  this hold.

### Deliberately NOT in the series
- **Option C, the CP-serial livelock guard** (2026-07-21). Implemented, built and put through three
  independent verification passes; **adjudicated not ready and reverted**. It removes kn5000-30's
  free-running baud generator but not the wedge (framing loss alone still kills the panel), never
  resyncs (`ll_exit_clean = 0` across 342 measured strand exits), and by keeping a permanently
  misframed link alive it makes the machine dispatch false button presses — phantom transposes,
  spurious PANEL MEMORY recalls, MENU:DISK opening ENTERTAINER. Kept, with its full adjudication and
  an applies-clean patch, at `notes/kn5000-cpserial-livelock-guard-candidate.{md,patch}`; land it
  only together with a fix that actually restores the link — which, as of 2026-07-21, does not
  exist.
- **Option B, the CP-serial receiver resync** (2026-07-21). Implemented, built, put through three
  independent verification passes (repro acceptance, no-regression, adversarial); **adjudicated
  INERT and reverted**. It is bit-for-bit identical to the pre-change build on all three
  deterministic repros plus a five-point phase sweep, a 444-press soak and a 38-press playing
  session, because the wedge destroys the closed→open gate transition it triggers on. Its reachable
  variants (B+C, and B′ = hold the counter in reset for the whole shut window) restore bit framing
  but reproduce option C's false-button-press symptom on `b3`. Kept, with its full adjudication, the
  patch and the deterministic repro luas, at
  `notes/kn5000-cpserial-receiver-resync-candidate.{md,patch}` and `notes/kn5000-cpserial-repros/`.
- **Option A, the CP-serial sender handshake** (2026-07-21). Implemented in full — receiver state
  (`IOC && RXE`) fanned out to the panel HLE, re-arm instead of clocking, hold the shift register on
  the CPU's own command clock, and the modelled SCLK-low bus request on PF.6 — built, put through
  three independent verification passes, **adjudicated a REGRESSION and reverted**. It is the best
  of the three by a distance (a1/b1/b3/phase sweep/soak all LIVE, boot phase no longer decides the
  outcome, `-validate` clean, KN7000/KN1500 boot screens bit-identical), but a deterministic
  two-simultaneous-presses schedule (`x_sim2`) that the shipped build handles goes dead under A and
  lands on a page neither button can reach, and a three-press cold-boot schedule (`pfx3`) regresses
  a sound name to `Sound Name Error`. Root-caused to the `idle_detect_callback` bus-request deferral
  and the `abandon_inta_cycle()` rewind. Kept, with its full adjudication and an applies-clean
  patch, at `notes/kn5000-cpserial-sender-handshake-candidate.{md,patch}`.
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
