# Autonomous work status — sound-subsystem implementation

This file is the resume point for the autonomous cron loop. Felipe is away for
many hours (started 2026-07-09 ~23:xx). Keep it updated at the end of every work
chunk: what is DONE, what is IN PROGRESS, what is NEXT. Read it first on every
cron tick.

**KN5000 control-panel serial: the entry point is `notes/kn5000-cpserial-INDEX.md`** — state,
artefact map, the four adjudicated candidates and the measurement rules. That work is **PAUSED at
Felipe's request** (2026-07-21); the "NEXT = A′" in the tick below is a plan, not a go-ahead.

## TICK 2026-07-21 (latest) — ⛔ KN5000 PANEL: OPTION **A** BUILT, VERIFIED 3×, **REGRESSION**,
## NOT LANDED. **ALL THREE OPTIONS ARE NOW SPENT. NEXT = A′ (A minus its idle-wait deferral).**
A = the sender-side handshake, implemented at BOTH staging levels: `IOC && RXE` fanned out from
`tmp94c241_serial` to the cpanel HLE, re-arm instead of clocking, hold the shift register on the
CPU's own command clock, and the modelled SCLK-low bus request on PF.6.

**It fixes a great deal, and it is still rejected.** `a1`, `b1`, `b3`, the whole phase sweep and
the 444-press soak all go **DEAD → LIVE**; boot-window presses take effect and stop poisoning later
packets; `-validate` clean; KN7000/KN1500 boot screens bit-identical. But it **loses to the SHIPPED
build** on two deterministic schedules (both re-run byte-identically in the adjudication):

* **`x_sim2`** — two buttons pressed at the SAME INSTANT (PIANO + ORCHESTRAL PAD, 20× at 0.6 s):
  pristine LIVE with all four liveness screens correct; A **DEAD**, frozen on ENTERTAINER / VOCAL
  REVERB — a page neither pressed button can reach = **option C's false-dispatch symptom**.
* **`pfx3`** — THREE presses from a cold boot: pristine `RIGHT1 Piano`; A `RIGHT1 Sound Name Error`.

**Root cause = ONE block**, isolated in two independent configs via the build's `KN5A_NOIDLEWAIT=1`
knob: the late "only ask for a bus that is free" deferral in `idle_detect_callback`
(`kn5000_cpanel.cpp:1049-1055`) re-phases the INTA request into the middle of `CPanel_SM_RXByteN`'s
teardown (`FC47C9`); the panel then holds mid-byte on the **100 ms** deadline and
`abandon_inta_cycle()` **rewinds a byte the CPU has already taken k bits of**. A's escape hatch
manufactures the misframe A existed to avoid.

**★ AND A'S HEADLINE NUMBER IS A TAUTOLOGY:** `drop_ext == 0` cannot increment under A (the panel
emits an edge only when `IOC && RXE`, tested in the same callback; the latch gate is the weaker
`IOC` alone). It read 0 with the panel dead. Every other counter read clean in the `pfx3` run that
visibly regressed. Gate future work on `strand_entry` / `strand_exit_mid` / `PHASE_HIST` bucket
count / `tmr_dead` / `cp_qmax` / `max_rearm` — and the PIXEL DIFF. Also: `bprime_FIRED = 0` in an A
run with 28 mid-byte strands ⇒ B′ is BLIND to the sender-side failure, so its zero proves nothing.

**NEXT = A′ = A minus rule 5** (and probably minus the `abandon` rewind). Both counterexamples
return to the pristine screens with only that block disabled — two data points, not a verification;
measure on the WHOLE suite (a1, b1, b3, ph000/007/017/033/050, soak, `x_sim2`, `x_multi`, `pfx3`,
`bootwin`). Untouched by C, B and A alike: the CPU tears its receiver down MID-BYTE between edges.
KEEP from A: the `IOC && RXE` fan-out, the shift-register hold (`cp_hold` 7k–10k real bits/run), the
PF.6 request. NEVER re-add: an INTA re-pulse while stalled (kills `b3` —
`INTA_HandleCountdown:697-698` decrements the firmware's receive-ring write pointer).

Candidate + adjudication: `notes/kn5000-cpserial-sender-handshake-candidate.{md,patch}`; repros
(now incl. `x_sim2`, `pfx3`, `x_multi`, `bootwin`, `s4`): `notes/kn5000-cpserial-repros/`;
findings: `KN7000/side-quests/findings/kn5000_button_mapping_findings.md`; blog Part 75.
**kn5000-30's SUBMISSION HOLD STAYS (third reaffirmation).** Tree reverted; rebuilt binary
byte-identical to the published one (`52818738929b4056179d115d8ca1ad7f`); nothing published.

## TICK 2026-07-21 (later) — ⛔ KN5000 PANEL: OPTION **B** BUILT, VERIFIED 3×, **INERT**, NOT LANDED.
## Both receiver-side options are now spent. **NEXT = OPTION A (sender-side handshake).**
B = resync the byte boundary on the closed→open receive-gate transition. Implemented exactly as the
brief specified, built, three independent verifications (repro acceptance, no-regression,
adversarial). **It is a BIT-FOR-BIT NO-OP** on `a1`, `b1`, `b3`, all five phase offsets, a 444-press
soak and a 38-press playing session — every snapshot PNG and every counter identical to pre-change.

**Why (proof, not guess): the wedge destroys B's own precondition.** After a strand the free-running
generator keeps the cpanel's 50 µs idle detector retriggered → INTA never returns → `INTA_HANDLER`
never runs → `or 0xd5,0x01` (IOC=1) never executes → **the gate never reopens**, so the transition B
triggers on never happens. Measured in every wedged run: `wclose = wopen + 1`, `resync = 0`,
`rx_final ∈ {4,5,6,7}`. That zero is NOT blind — the same counter reads 1 (`a1`) and 3 (`b3`) when
the option-C guard is enabled alongside. `exit_midbyte = 0` is VACUOUS (no reopen ⇒ no exit to
classify) — do not report it as a pass.

**★ The new, decisive result: the reachable variants fail too.** B+C, and the strictly better
**B′** (`if (!ext_clock) { m_rx_clock_count = 8; m_rx_shift_register = 0; }` — holds the counter in
reset for the whole shut window, so the free-run cannot start and C becomes unnecessary by
construction; snapshot-bit-identical to B+C) both reproduce **option C's rejection symptom** on `b3`:
phantom `<Db>` on a FIRST boot from empty nvram, MENU:DISK and MENU:SOUND changing 0 px, "LIVE PIANO"
opening LEFT/ORCHESTRAL PAD. Control: `soak` (444 presses, 0 strands) is perfectly clean ⇒ the
trigger is the strand *recoveries*, not press count/rate. **Resync restores BIT framing, not PACKET
framing** — the lost byte still shifts the (header,state) pairing.

**==> THE RESIDUE IS LOSS, NOT MISFRAME.** No receiver-side change can reconstruct a byte that was
never delivered. **Option A is now the live task**
(`KN7000/side-quests/pending/kn5000_cpserial_sender_handshake.txt`). Keep B′ as belt-and-braces to
land WITH A, where it should be measurably inert; if it is not inert, A is incomplete.

**Also recorded:** the brief's faithfulness premise is FALSE — `cpanel_routines.s` writes IOC **alone**
at eleven sites, so IOC ≠ RXE; a resync makes that skew load-bearing, so the RXE gate (SC1MOD bit 5,
unmodelled) must land before/with any future resync, not after. A scratchpad binary named
`optC/kn7000_cleanC_backup` is **not** a pre-change reference (it is the option-C build) — the only
trustworthy one is the published `kn7000-emulator/kn7000`, md5 `52818738…`. Pre-existing, not B's:
"Sound Name Error" in long sessions is session-state dependent and NOT a misroute symptom (bit-identical
pre-B) — worth its own quest.

**Tree state:** reverted and proven (`grep -rn "m_rx_gate_open\|KN5B" src/` empty; rebuilt binary
byte-identical md5 `52818738…` to the published copy, so `publish-binary.sh` had nothing to do).
kn5000-30's ⛔ SUBMISSION HOLD **stays**, reaffirmed in all three places in
`notes/upstream-patches/README.md`. Adjudication + patch + deterministic repros:
`notes/kn5000-cpserial-receiver-resync-candidate.{md,patch}`, `notes/kn5000-cpserial-repros/`
(a1/b1/b3 + phase sweep + soak + README). **Any future gate in this area MUST include `b3`** — `a1`
alone passes variants `b3` kills. Blog Part 74.

## TICK 2026-07-21 — ⛔ KN5000 PANEL: kn5000-30 is INCOMPLETE and now on SUBMISSION HOLD.
## Option C (livelock guard) built, verified 3×, ADJUDICATED NOT READY, NOT LANDED.
**Corrects the earlier "scrambled panel FIXED" tick.** kn5000-30 (b17fb8b) really did kill the 521
phantom RX bytes, but it opened a **mid-byte gate-close race**: close the RX gate while the panel is
still shifting a byte in and `m_rx_clock_count` is stranded at 1..7, so the `(m_rx_clock_count != 8)`
term in `timer_callback`'s `need_clock` is permanently true and the internal baud generator FREE-RUNS
(663,146 … 3,221,718 dead edges). Those edges retrigger the cpanel's 50 µs sliding idle detector
faster than it can expire → INTA never re-asserted → **panel link DEAD for the session** (queue wedged
at 106/338/653 bytes). The earlier "latent, never observed firing" filing was wrong: IT FIRES.
Discriminator is NOT the drop count (S5 dropped 25 and recovered; S4 dropped 12 and died) — it is
whether latching resumes MID-BYTE. Boot-window presses lose nothing themselves; they shift the PHASE
of the panel's packet cadence so a LATER packet collides. Felipe's hardware: a real KN5000 panel is
NOT corrupted by presses during boot → emulation bug, "faithful" is not an available defence.

**Option C = qualify that term.** Implemented, built, smoke-tested, three independent verification
passes. REJECTED, tree reverted (rebuilt binary byte-identical md5 `52818738…` to the published copy;
`publish-binary.sh` had nothing to do). Why: (1) it does not remove the wedge — framing loss ALONE
kills the panel, reproduced naturally (config `b3`, 220 drifting-interval presses: guard on, all four
pixel-liveness probes 0 px, `dead=3638` only); (2) `ll_exit_clean = 0` across **342** strand exits in
two passes, every one MIDBYTE-REOPEN, 106 s idle soak never resyncs; (3) keeping a misframed link
ALIVE is destructive — false button presses nobody made: `<Db>`/`<D >`/`<G >` phantom transposes, a
PANEL MEMORY recall with tempo 120→80, DRUM KITS opening the OCTAVE dialog, MENU:DISK → ENTERTAINER.
`b1` (6 boot presses + 33 at 2 Hz = ordinary playing) triggers it.

**KEEP (C proved these, B will want them):** provably inert when healthy (`dead=0` in 20 healthy runs,
GUARD vs NOGUARD pixel-identical), TX integrity perfect 22/22, free-run genuinely gone where it occurs
(1.4–3.2 M → 16–33 k edges), kn5000-30's phantom suppression exact (`drop_int/8 == tx_bytes ==
cpanel_recv`). **TRAP:** the `phantom` counter is a TAUTOLOGY post-kn5000-30 (sioclk only latches when
the gate is open) — a zero from it proves nothing; use the arithmetic. **S1–S5 is INDICATIVE ONLY** —
two passes could not replay S3/S4; the deterministic repros are `a1` (90 presses @0.15 s from t=30),
`b1`, `b3`.

**NEXT = option B** (receiver-side resync on the closed→open transition ONLY, never on every
`scNcr_w`), then option A (sender-side handshake, `CPanel_SM_StartTX:781-787`). Briefs:
`KN7000/side-quests/pending/kn5000_cpserial_{receiver_resync,sender_handshake}.txt`. Rejected C patch +
full adjudication: `notes/kn5000-cpserial-livelock-guard-candidate.{md,patch}`. Hold recorded in
`notes/upstream-patches/README.md`. Blog Part 73 + a second erratum on Part 71.

## TICK 2026-07-21 — ★ KN5000 TEMPO/PROGRAM WHEEL DONE: turning it edits the on-screen tempo
Implemented the resume point from `side-quests/findings/kn5000_data_wheel_findings.md` ADDENDUM 2.
The KN5000 wheel is NOT a control-panel-serial input in steady state — the firmware reads it with a
main-loop poll (`Encoder_ValueScanAndSync` 0xFC5761) from an encoder scan table at MainCPU DRAM
0x8E94 (3-byte entries `[record_id, delta, mask]`). HOOKUP (`kn5000_cpanel.{cpp,h}`): the cpanel got
a `required_device<cpu_device> m_maincpu{*this, ":maincpu"}`; on each detent (the existing wrap-aware
one-detent-per-scan slew) it now writes `[0x19, -step, 0xFF] + 0xFF` at 0x8E94 via
`m_maincpu->space(AS_PROGRAM)`, SIGN-INVERTED so CW = tempo up (ROM 0xEA98E2 accel curve inverts),
and writes ONLY on a detent (firmware clears the table to 0xFF each main loop — re-present per detent,
nothing while still). The proven-no-op segment-0x0B emission was removed. 0x8E94 confirmed MainCPU
RAM (maincpu_mem 0x000000-0x0fffff DRAM). VERIFIED LIVE via the DRIVER path (drove `:cpanel:ENCODER`
`field.user_value` = what the layout widget does; BPM READ-POLLED at 0xFC62, write-taps blind here):
HOME ♩=120 → CW → **141** (up), holds; → CCW → **109** (down), holds. Both directions, one step per
detent, STOPS cleanly (no KN7000-style runaway). Snapshots captured. Direct-0x8E94 cross-check
reproduced the ADDENDUM-2 clamp (+3→40, −3→163). REGRESSION: `-validate` clean
kn5000/kn7000/kn6000/kn6500/kn2400; KN5000 names still real (Piano/Bigband Brass/Modern E.P.1,
kn5000-29 intact); KN7000+KN6000 boot zero layout-script errors (share slider_lib.lua, untouched);
KN7000 reverb oracle bit-stable ×2 AND provably unaffected (diff touches only `kn5000_cpanel.*`,
which the KN7000 machine does not instantiate — only comment refs in kn7000.cpp). Patch **kn5000-25**
regenerated in place (kept last, message + README PR-9 note rewritten "held back/no-op" → "WORKING";
round-trips byte-identical). Built + published. Findings ADDENDUM 3; side-quests/README updated.

## ☆ FELIPE WISH (2026-07-20/21): PERMANENT, NON-HACKY KN5000 boot-splash animation
Long-term want. CONTEXT (corrected): the SNS payload-checksum write tap removed by
kn5000-29 (the sound-names cure) was ALSO what made the KN5000 boot splash ("Technics
KN-5000 IN COLOUR") play. Removing it traded splash-for-names. Felipe wants BOTH,
non-hacky. MECHANISM fully mapped (see side-quests/findings/kn5000_driver_findings.md
2026-07-21): the splash shows only when SubCPU_Payload_Verify (0xEF092B) passes; the
verify checksums DRAM 0xF180/0xF980 vs reference words at DRAM[0xFFD4/0xFFD2]. Live
watchpoint: pc=EF18DF clears FFD4/FFD2=0 at t=0, the verify reads them at t=4
(pc=EF0941) BEFORE the payload transfer (t~18) — so a persisted checksum is wiped
before the verify. The tap seeded FFD4=checksum(current regions) right at the clear so
the verify ALWAYS passed -> "payload OK" -> SPLASH, but "payload OK" also makes the
firmware SKIP the transfer -> empty (non-persistent) SubCPU RAM -> Sound Name Error.
INTRINSIC TENSION: verify-PASS = splash but skip-transfer (no names); verify-FAIL =
transfer (names) but no splash. MAME gaps: (1) no maincpu cycles run after the shutdown
signal (schedule_exit -> eat_all_cycles; nvram_save at machine.cpp:375 runs BEFORE
MACHINE_NOTIFY_EXIT at :416) so the ROM power-off NMI that stores the checksum can't
run; (2) the t=0 EF18DF clear. NEXT (a design task for Felipe, not a one-liner):
disassemble EF18DF (is the clear unconditional?) + EF092B (what exactly is compared,
and is the transfer truly skipped on pass); decide the emulation model (persist SubCPU
RAM to legitimize a skipped transfer, OR keep the transfer unconditional and only
report welcome-screen status OK); provision the reference checksum via a
device_nvram_interface at nvram_save (plain call at exit, no cycles) rather than a
boot-time re-entrant tap. Names cure (kn5000-29) stands on its own meanwhile.

## ★ KN5000 PRIORITY (Felipe 2026-07-20): SOUND NAME ERROR > tempo wheel
To avoid subagents colliding on shared KN5000 files, Felipe set the order:
  1. TOP: fix the "Sound Name Error" (SubCPU reply path — the dropped DSP2/MN19413/ComIF/serial
     wiring; microDMA payload already fixed + byte-verified, commit e6b4cf7). Agent a0c5df63d2428dd5b
     owns kn5000.cpp + tlcs900/tmp94c241 + any new device files for this.
  2. DEFERRED (not abandoned): the TEMPO/PROGRAM DATA WHEEL. Layout/Lua side CONFIRMED WORKING by
     Felipe's real mouse (rotates); only the driver->firmware tempo hook is unfinished. RESUME POINT:
     the wheel EDITS TEMPO on real hardware (Felipe insists — ground truth; the static "no BPM writer"
     read is wrong/incomplete). Chase PsParaBoxProc / the focused-parameter path writing BPM 0xFC62 via
     the generic parameter machinery (no tempo-specific writer exists BY DESIGN); resolve which record
     id the focused path consumes vs the 0x21 we were injecting; set a watchpoint on 0xFC62 and turn the
     wheel to find the writer PC. Patch kn5000-25 stays LAST/held-back. Do NOT run a wheel agent
     concurrently with a Sound-Name agent — they share kn5000 files.
RULE: only ONE agent may hold the KN5000 driver files at a time until the driver stabilises.

## ★ SIDE-QUESTS = THE IDLE-TIME TASK QUEUE (Felipe 2026-07-20)
CHECK /home/fsanches/compartilhado/KN7000/side-quests/ REGULARLY — Felipe drops new tasks there.
Structure (see its README.md): pending/ = to do, fully_solved/ = done, ignore_these_ones_for_now/ =
parked, findings/ = one write-up per quest (flat; findings do NOT move when status changes).
WORKFLOW per quest: do the work -> write/refresh findings/<quest>_findings.md -> `git mv` the brief
from pending/ to fully_solved/ ONLY when genuinely delivered (an honest documented LIMITATION is fine;
an open sub-task is not) -> update the README status section -> commit in the KN7000 repo.
PRIORITY: side-quest pending/ items rank ABOVE generic CONVERT growth in idle time (they are Felipe's
explicit asks). CONVERT remains the default when pending/ is empty.

CURRENT pending/:
  1. kn6000_and_kn6500_control_panels.txt — [IN FLIGHT this session] service manuals at
     ~/compartilhado/KN6000/technics_sx-kn6000-sm.pdf + service_manual_kn6500.pdf; write the cpanel
     declarations for both, refactoring to a shared base device + per-model derived classes (Felipe's
     evidence: KN6000 buttons are accepted but MIS-MAPPED, while the TEMPO/PROGRAM wheel already works
     perfectly => the protocol is shared, only the matrix differs). Decide whether KN6000/KN6500 share
     one source file based on measured commonality.
  2. floppy_disk_save_and_load_self_test.txt — BLOCKED on the unmodelled power-on keybed-matrix read
     (B3+B4 entry combo); two routes in findings/floppy_self_test_findings.md.

## ★ FELIPE'S QUEUE 2026-07-20 (explicit: "do all of the autonomous software queue items")
Execution order (driver-side items SERIALIZE on build-tree+display; launch next as each completes):
  A. [DONE 2026-07-20 — see the TICK below] r4-rA damp-bank RE + the two live DSP experiments
     (u8 DM dump, DspEffectSelect unit-role capture).
  B. [DONE 2026-07-20 — see the TICK below] Per-part effect depth bank decode + fix (cold
     chorus/multi panel toggle audible) + bridge unit feeds rewired to the true units
     (e1a94f4 + d316228; notes/per-part-depth-bank.md).
  C. [DONE 2026-07-20 — see the TICK below] INTC + timers into the mn10300 core (e8429c8 core +
     02f2595 integrate; KN6000 timer hacks RETIRED — the real core TM5 drives its boot at the
     true 500 Hz ms rate).
  D. [NEXT] Siblings: KN2400/2600 to first screen; KN6000/6500 text rendering. NOTE: the "KN6000
     real timer" prerequisite is already DONE by item C — D starts from a real-TM5 baseline.
  PARALLEL TRACK: [IN FLIGHT] CONVERT growth (tempo/TM5 chain, then TG note path) — kn7000_disassembly.
Rules unchanged: commit-as-you-go, publish after rebuilds, visible video, blog per the proactive bar,
tick this file after each item. PENDING FELIPE: Phase C dump-kit go-ahead, SHARC submission, wet-level A/B.

## ★ STANDING IDLE-TIME DIRECTIVE (Felipe, 2026-07-19)
★ SCORE TRACKING (Felipe 2026-07-20): every CONVERT pass MUST finish with
`python3 tools/coverage_score.py --append` in kn7000_disassembly and report the new
SOURCE COVERAGE % in its tick. Two numbers: byte-match is 100% by construction
(.incbin passthrough proves nothing); SOURCE COVERAGE = share of the image that is real
re-assemblable assembly. Baseline 2026-07-20: 17.89% (743,770 / 4,157,185 bytes),
925 functions, 71 .byte escapes. History: kn7000_disassembly/notes/coverage-history.tsv.

Use ALL idle autonomous time to IMPROVE THE DISASSEMBLY — both:
- maincpu (kn7000_disassembly repo): grow the CONVERT set (66 fns re-assemblable of 2302 named), name
  more functions/constants from reflection tables + RE notes, keep the 100% byte-match invariant.
- DSP algorithms (kn7000_disassembly/dsp): annotate the SHARC effect microprograms record-by-record
  (reverb/chorus/multi/EQ structure, delay-line topology, coefficient roles), enrich sym/recNN.sym,
  use kn7000_mame/tools/dis_sharc.sh. The MULTI-unit pinning + EQ insert RE feed directly off this.
Every cron tick with no higher-priority queued item = disassembly work. ★ EXTENDED (Felipe): the
GOAL is ALL DSP programs FULLY DOCUMENTED — per understood record: algorithm doc in
kn7000_disassembly/dsp/, docs-site page where warranted, and a PROACTIVE blog post. Work through
records.tsv systematically (reverb in flight; then chorus, multi, SOUND-DSP variants, EQ, kernel).
PENDING FELIPE ANSWER: Phase C dump-tooling prep offer (update-disk + SD-sink readback) — awaiting go.
IN FLIGHT: SHARC upstream prep agent (apply-tests/rebase/A-B/datasheet cross-check).

## TICK 2026-07-20 — KN5000 regression: maincpu→subcpu payload microDMA was SCRAMBLED (FIXED)
Felipe: "Sound Name Error in KN5000 now; used to work with the microDMA payload transfer." His
testimony was right and overrides the prior agent's "IC304-306 undumped" note (a missing WAVE ROM
silences a voice, it does not make a NAME fail — names travel the inter-CPU latch). Root cause: the
overlay came from the cleaned-up PR branches (kn5000_pr6 / _research_tonegen); the upstream-cleanup
rebase DROPPED three load-bearing driver-side latch workarounds the working kn5000_aided_by_claude
branch had (fixes 10 & 12 in kn5000-docs/subcpu-payload-loading.md): the latch READ wrappers that
synchronously clear the receiver's /INT0 (generic_latch::read() defers the CLEAR through
synchronize() → the TMP94C241 level-detect re-assertion re-fired the receive ISR spuriously per byte),
plus acknowledge_w(0)-if-pending + abort_timeslice() in the WRITE wrappers. Result: the 192 KB
payload arrived corrupt (measured 58 515 / 62 804 wrong bytes in blocks 7/8). FIX (kn7000_mame
e6b4cf7 + patch kn5000-26 56ce9a0): restored tmp94c241_device::clear_int0_level() + the read/write
wrappers, matching aided_by_claude. VERIFIED: decompressed payload now BIT-IDENTICAL to the reference
(0 mismatches); -validate passes kn5000/kn7000/kn6000/kn6500/kn2400; KN7000 still boots home w/ real
names. STILL OPEN (separate cause of the on-screen error): the SubCPU receives the 0x2B query 527x but
emits 0 replies; the overlay ALSO dropped the SubCPU DSP2 (MN19413) / ComIF / serial wiring that
aided_by_claude had — that (needs the mn19413 device, absent here) is the next step. Full write-up:
KN7000 side-quests/findings/kn5000_driver_findings.md (2026-07-20 section).

## TICK 2026-07-20 — ★★★ THE KN6000 SINGS: kn6000_tonegen_device SHIPPED, pitch verified in tune
Side quest `kn6000_tone_generator` DELIVERED (kn7000_mame bb1ab85, KN7000 e7f7692).
The previous tick shipped the shared base and said "NO kn6000_tonegen_device SHIPPED, on
purpose". Both reasons it gave are now gone.

AUDIO (the real test) — FFT of a `-wavwrite` capture, key-bed note held on kn6000:
  C4 (60) 261.63 expected -> **261.72 Hz**  (+0.01 semitone)
  G4 (67) 392.00 expected -> **392.14 Hz**  (+0.01 semitone)
  C5 (72) 523.25 expected -> **523.44 Hz**  (+0.01 semitone)
Correct across more than an octave = real resolved pitch, not one lucky anchor. Timbre is
still the placeholder sine (wave ROMs undumped); pitch/polyphony/timing/7-param amp EG are
the firmware's own. kn6000 -> MACHINE_IMPERFECT_SOUND.

BLOCKER 1 (per-plane map, was ~20 planes INCONCLUSIVE) — **the firmware enumerates itself.**
Note-on routine 0x484948CB = a straight blit of the 0xA0-byte shadow image (0x50043100 +
slot*0xA0) into the chip, one writer call per register with each destination OR-ed in as a
literal. Reading them off in order gives the COMPLETE map, every byte of the record
accounted for. The proposed live per-plane sweep became a CONFIRMATION, not the method —
worth remembering: check whether the firmware already enumerates a map before sweeping for it.
  gate = cls 0x0000 idx 0 (0x87FF/0x8000); amp EG = cls 0x0004/5/6 (confirmed BY LITERAL —
  the damp routine 0x484947B3 writes the same 0xA280/0xA200 the KN7000 writes to r0/r1);
  18-bit pitch = cls 0x5000 (shadow +0x74, u32 high half extends the class nibble);
  level = cls 0x4000 (default 0x3FFF); banks at 4/8/C, release burst {4,5,8,9,C,D}.

★ FALSIFIED: the spec's "plane 0x20 = send matrix on BOTH chips". On the KN6000 cls
0x8000-0x9000 are PER-VOICE wave/sample params (blit sources them from shadow +0x8C..+0x9C).
The matrix is in the 0xA0xx family instead (same row<<8|part<<4|reg shape, rebased); its
row->bus map is UNVERIFIED so the device does not drive the effect gains from it.

BLOCKER 2 (note->pitch routine) — **dissolved, not reversed.** Same trick as the KN7000: the
firmware computes the pitch and publishes it. Record initialiser 0x48493D80 writes
+0x08 = 0x80|(pitch16>>8), +0x0A base pitch16, +0x0C notePitch16 — field-for-field the
KN7000 layout at the same 0xB4 stride.
★ THE TRAP (only a live check caught it; the static read looked perfect): there are TWO
0xB4 arrays and only one is indexed by SLOT. The library array 0x502858F8 is indexed by
note-event ELEMENT — C4 and C5 both filled records 00/01 while going to slots 0/1 and 2/3.
Read **0x5027AF28**, the per-TG-SLOT copy the firmware makes at note-on (0x48492F20).
KN6500 equivalents (own build, own config): rec 0x5027AF1C, shadow 0x500430AC.

★ NEW BLOCKER, precisely characterised: **KN6500 emits ZERO TG writes on a key press**
(live-probed). Same correct device + binding, but its voice engine never starts — a
boot/enable-gate difference from the KN6000, NOT a decode problem. Stays MACHINE_NO_SOUND.
**This is the obvious next task.**

LEFT UNDECODED ON PURPOSE (evidence does not support them): effect-send matrix, aux/mode
word (=> every voice treated as MANAGED; safe because the KN6000 writes a UNIVERSAL key-up
gate), record type, even/odd companion pairing.

TOOLING: tools/kn6000_tg_probe.lua NEW (taps the single TG window, locks the first slot of a
burst, samples the voice record AT the note-on pitch write, scans all 64 records so the
slot<->record mapping is measured not assumed).
tools/audio_playnote_wav.lua FIXED — the previous tick flagged it stale; it was broken TWICE
OVER and the second fault is invisible until the first is fixed: (1) by-NAME lookup of
"Key C4" in :KEYS0 (the 61-key bed moved C4 to :KEYS1 bit 8 AND renamed the field to "C4");
(2) the frame-notifier handle was dropped, so Lua GC'd the subscription. Either alone = a
silent capture with a cheerful status line. Now resolves the key arithmetically from a MIDI
note (KN_NOTE/KN_AT/KN_OFF) and ERRORS LOUDLY.

REGRESSION HELD: kn7000 reverb/keybed oracle **c3b67ea711ce3c00f8ae2af1e07651cb**
bit-identical x3 (twice pre-publish, once on the final published binary). -validate clean on
kn7000/kn6000/kn6500/kn2400/kn2600/kn5000. Built + published.

## TICK 2026-07-20 — ★★★ QUEUE ITEM C COMPLETE: INTC + TM4/TM5 timers live in the mn10300 CORE (KN6000 timer hacks retired)
Two-stage migration mirroring the SIO precedent (9bb2de8 -> 9eb0e4b): core stage **e8429c8**
(mn10300.{h,cpp}: byte-exact port of the driver INTC HLE — GxICR w1c-per-lane semantics, IAGR
<<3/<<2 latch-at-accept quirks, EXTMD accumulate, group-0x17 DSP self-test self-ack — plus TM5
with load-pulse/count-enable/live-retempo semantics, IOCLK=clock()/2 /8; all save-stated;
delivery via the core's own maskable line + a board-configured per-level vector table) and
integrate stage **02f2595** (kn7000.cpp -310/+112: driver INTC/tmr7 code+maps deleted;
intc_assert = thin forwarder so all peripheral call sites unchanged; vectors set in
machine_config — kn7000 0x4C03DDA0 / lvl6 0x4C03DE26, kn6000 all-levels 0x90000000; the three
quirk hooks ride the new devcbs intc_ack_cb/intc_accept_cb/intc_extmd_cb = c11 re-delivery /
c11 clear-at-accept / panel-ATN EXTMD edge re-arm w/ driver-side m_extmd_prev shadow; SD
group-0x1B pokes via intc_icr_set/clear).
**KN6000/KN6500 hacks RETIRED**: the sys_tick 1 kHz group-7 piggyback is GONE — the firmware
programs the core's real TM5 (base 0xFA0/mode 0x81) and the ms ISR runs at the TRUE hardware
rate 2.0005 ms (~500 Hz; the old 1 kHz hack was double-rate, as the memory suspected). The
0x340010a0-a3 counter placeholder superseded by the real TM5BC down-count; a4-af keeps the
placeholder (TM6+ unmodeled). KEPT: the 2 s sys-tick boot delay (guards the group-6 scheduler
tick vs RTOS object creation — group-6 HLE matter, not TM5).
GAUNTLET (published binary, visible video): kn7000 home + BALLAD list + SD MENU (all 9 items,
toggle verified) + DEMO plays ~20 s (WAV RMS 2229; beat phase 0x50149664 advancing = TM5->core
group 7->96-PPQN ISR); **reverb oracle c3b67ea711ce3c00f8ae2af1e07651cb bit-stable x2** (fresh
cfg + pristine SD — total audio-path parity to the last bit); kn6000 play screen boots with the
hacks retired, ms-counter 4973->9971 over t=10..20 (=500 Hz real rate); -validate clean both.
Harness: kn7000-emulator/intc_core_verify.lua (companion to sio_core_verify.lua).
GOTCHA (pre-existing, not a regression): a keybed press at t=28 on the settled home screen is
SILENT with a fresh default cfg (TG gate config-dependent); the oracle's t=16 press sounds. Same
on the pre-migration build (oracle hash identical) — worth a look someday, separate from C.

## TICK 2026-07-20 — ★★★ QUEUE ITEM B COMPLETE: bridge feeds on the TRUE units + the per-part DEPTH BANK decoded (cold CHORUS/MULTI audible)
Two commits (kn7000_mame e1a94f4 + d316228), built+validated+published, oracle clean:
- **B1 — unit-feed rewiring**: the bridge's chorus/sound-dsp feeds were wrong-slot placeholders
  (chorus fed u4 = an insert-pool slot, sound-dsp fed u9 = the actual CHORUS unit; each audible only
  because the OTHER effect's algorithm lived in its slot). Rewired per the item-A live map: CHORUS ->
  u9 (in 0xC376/7, ret 0xC356/7), SOUND-DSP -> u2 = RIGHT1 insert (in 0xC366/7, ret 0xC346/7);
  MULTI (u1) + REVERB (u0) were already right. A/B (b1.lua): all four true returns nonzero
  (u0 235304 / u1 87608 / u2 171845 / u9 526585), old u4 slot dead, DAC on-vs-off diff RMS 113.6,
  control run clean. **Oracle UNCHANGED bit-stable x2 = c3b67ea711ce3c00f8ae2af1e07651cb** (u0
  untouched; other feeds gated on send>0 = 0 in the oracle scenario) — no re-baseline.
- **B2 — the depth bank DECODED (notes/per-part-depth-bank.md)**: group-0x20 = a PER-PART SEND
  MATRIX, addr = 0x8000|row<<8|part<<4|reg (row0=reverb send [hi byte = dest part 3], row1=chorus
  [hi 0x0B], row2=multi [**hi = ON marker 6/8**], row3=level/depth bank, regA=[direct|return]).
  The old "depth channels 0x30-0x3B" = row3; "sends 0x06/0x07" = row0 of parts 6/7. Writer chain:
  setter family 0x4C037D0F..0x4C037F10 (level low7 merged into shadow 0x500CE2B0+part*0x10; call
  entries at movm+5 — bp the movm start NEVER fires; MDR = return addr in dbg printf), refresh
  orchestrator 0x4C004E30 gating on PART RECORD 0x500B5340+idx*0x54C (+0 bit3 = the part-insert /
  SOUND-DSP flag, +0x62&0xE000, +0x14; RIGHT1 = record 0x10, TG part 9). ★ COLD-TOGGLE ROOT CAUSE:
  insert off -> the zero path (0x4C005083) writes LEVEL 0 to every row; the real depths live only
  in the record (+0x15 chorus 0x3C, +0x16 multi 0x50); the ON state is hardware-visible ONLY via
  the LED (chorus) / row2 base nibble (multi). Cold press = exactly 5 TG writes, zero DSP-port
  writes (b2cap2.lua). DRIVER FIX (labeled HLE): multi = row2 ON-marker decode + default 0x50;
  chorus = gate on the firmware's own CHORUS LED (new cpanel chorus_led()/multi_led() getters) +
  default 0x3C; firmware-written levels always win. A/B (b2ab.lua): cold CHORUS+MULTI, NO
  sound-dsp: u9 ret 520948 / u1 84484 / u2 stays 0; control all-zero; DAC diff RMS 76.9; demo
  regression (env14.lua) + keybed + clean release pass. Oracle re-verified on the B2 build:
  **c3b67ea711ce3c00f8ae2af1e07651cb x2** — unchanged.
  RE gotchas recorded: MN10300 `call` enters setters at movm+5; watchpoint-reported pc = NEXT
  instruction; Lua string.format eats %08X in debugger printf actions (escape as %%08X).
  OPEN (deep): per-part audio separation (single-mix approximation stands); PART-SETTING depth
  edits with insert OFF aren't tracked (firmware never emits them).

## TICK 2026-07-20 — ★★★ QUEUE ITEM A COMPLETE: r4..rB DECODED (pitch+filter EGs) + DSP UNIT MAP LIVE-CAPTURED + u8 EQ FLAT SETTLED
Three live-instrumentation investigations in one pass (agent runs a1/a1b/a3/a3b.lua, logs in
kn7000-emulator/):
- **A1 — the "damp bank" r4..rA is NOT a damp bank: it is the PITCH EG (r4/r5/r6 + r7 hi =
  TOTAL DEPTH) and the FILTER EG (r8/r9/rA + rB lo = START POINT), each in the amplitude EG's
  exact [rate|level] 3-pair layout.** Column-verified on the FILTER ENVELOPE (page 3/4) and
  PITCH ENVELOPE (2/3) screens; filter/pitch level bytes are SIGNED (0 = screen 40); CUTOFF
  ADJUST folds into every filter level byte; RLS never reaches the TG (like amplitude);
  page-1 MODE/CUTOFF/RESO edits (LPF→BPF, 21.1K→392Hz) leave group 0 untouched — the STATIC
  filter lives elsewhere (open). The rA-hi release correlation = the filter DCY2 rate (organs
  slam the filter shut at key-up, pads sweep it); driver heuristic kept, semantics documented
  (comment-only kn7000.cpp change, no behavior change, no re-baseline). The key-up burst =
  pitch-EG reset + filter closure to −0x50 at rate 0x22 (the damper is a filter sweep). Full
  table: notes/tg-envelope-sweep-results.md RESULT 4. Multi-sound survey (16 groups + 8
  pianos) captured in a1_run.log.
- **A3 — DSP unit roles are LIVE FACT and three labels flip: u0=REVERB, u9=CHORUS,
  u7=MIC REVERB; MULTI runs on u1; per-part Sound-DSP on u2..u6 (RIGHT1=u2); u8=EQ.**
  Param-block tap (0x500A01E0 → 0x5009EB58; type at +8, double-buffer ptr flip at +0) + host
  download-port tap while driving the GUIs. GUI map: Room1/Plate1/Concert1/Dark1 = u0 types
  0x10/0x12/0x14/0x16 (rec53/54/51/55); "…2" partners = DM-only voicings (no type write, no
  PM upload); Chorus1-4 = u9 0x52 (rec49), GM Chorus1-4 = u9 0x02 (rec07); Multi CrossDelay =
  u1 0x0C (rec15). kernel-architecture §8's "MULTI=u6" REFUTED (bank↔line is per-PAIR:
  reverb 0xC362, multi 0xC364, chorus 0xC376); scrub-stub host choreography captured live
  (CALL slot flipped around every swap). PANEL MEMORY recall = full 10-unit resync (found by
  accident: CPR_SEG6 0x40 / CPR_SEG3 0x40 are PMEM 2/5, NOT menus). Docs updated:
  kernel-architecture.md §6/§8/§9, reverb-algorithm.md §3/§6/§7 (GUI map now pinned),
  dsp-effect-catalog.md §3+§5 labels, records.tsv. NEW note (primary record):
  notes/dsp-unit-roles-live-capture.md.
- **A2 — u8 EQ flat bank SETTLED: the host bank at flat is an EXACT mirror bank (H≡1)**,
  computed from the GUI FC row 125/500/1k/2k/8k (= rec23's pole values; rec34's ROM DM
  template is never used at runtime). The old "15% diff at flat" was a measurement artifact.
  Preset encodings dumped live (Treble Boost = +8 dB unity-DC S5 shelf; Radio mid-boost +
  treble cut; No Hi Hat = S4 notch; presets move poles AND zeros; EQ soft key R1 = ORIGINAL
  restore; bank uploads DM-only, no DspEffectSelect, even with EQ:OFF).
  dynamics-eq-exciter.md §5.4 resolved.
- **Item B hand-off**: the MAME bridge feeds chorus to u4 and sound-dsp to u9 — both
  wrong-slot placeholders per the new map; fixing the feeds to u9/u2 (+ per-part depth bank)
  is exactly item B's scope.
- Gotchas for future GUI drives: authoritative soft keys = the cpanel PORT_NAMEs (LCDL1-5 =
  CPL_SEG0 0x02/08/20/01/04, LCDR1-5 = CPR_SEG5 0x10/CPR_SEG5 0x20/CPR_SEG7 0x01/CPR_SEG6
  0x01/CPR_SEG5 0x01); PROGRAM MENUS = CPR_SEG0 0x04; EQUALIZER = PROGRAM MENUS → LCDL2 →
  LCDR5. Host download payload streams AFTER the DMAC commit (capture accordingly).

## TICK 2026-07-20 — ★★★ TG AMPLITUDE ENVELOPE: SWEEP DONE + FULL 7-STAGE EG SHIPPED (Felipe's directed task)
The ENVELOPE-screen sweep ran (env9-11.lua) and DECODED the amplitude EG: it is r0/r1/r2 as
[rate hi | level lo] pairs (r0=ATK|PEAK, r1=DCY1|SUS1, r2=DCY2|SUS2; higher rate byte = faster;
screen->rate is a nonlinear curve table) and **r3 = the GATE (0x87FF note-on / 0x8000 key-up,
written for EVERY class — organ included, falsifying the 07-11 'gate-follow sounds get no key-up
write' sweep reading)**. r4..rA are NOT the EG (chip-side damp/aux bank; rA-hi release correlation
stands). Screen RLS + SUSTAIN PEDAL never reach the TG in the audition path (open; full-class
diffs byte-identical). Full table: notes/tg-envelope-sweep-results.md (commit 4b3c14a).
IMPLEMENTED (4fa66d4): full ATTACK->DCY1->SUS1->DCY2->SUS2->RELEASE chain in kn7000_tonegen —
per-sound attack from r0 hi (edited ATK=52 audibly swells ~1.3 s, wav-verified vs instant-attack
control), pianos two-stage-decay to true silence, organs hold; release = r3 gate-off (universal)
at the rA damp default, overridden by the managed burst's r0 rate. Rate law PROVISIONAL:
T=13*2^(-rate/20) s (anchored to the shipped piano 6 ms/1.8 s). A/B: default piano+organ
byte-similar (no regression), demo songs play, published.
REVERB ORACLE re-baselined (intentional TG change): **c3b67ea711ce3c00f8ae2af1e07651cb**
(bit-identical x2, clean decay; nota cda5332). SWEEP GOTCHAS for every future Lua session:
(1) write-taps installed at t=0 DIE during boot — install after t>=25 s; (2) NEVER run two MAME
instances on one SD image (second boots degraded: TG idle frozen, keybed dead); (3) keybed
fields are GM-renamed ('C4') — press by PORT+MASK (:KEYS1 0x0100); (4) ENVELOPE screen edits =
balance-button columns (ATK=PART3 .. SUSTAIN=PART10), hold = ~12.7 steps/s auto-repeat.
OPEN: where screen RLS lands (needs a WRITE-saved sound or normal-play release trace); r4..rA
bank true role (filter-EG probe inconclusive); exact chip rate curve (needs real HW).

## TICK 2026-07-19 — ★★★★ FULL-COVERAGE MILESTONE: EVERY DSP PROGRAM DOCUMENTED (DSP-doc directive COMPLETE)
Final batch rec58-61 / rec67-69 / rec70-72 / rec75-76 documented (kn7000_disassembly 415c3d1,
NEW dsp/final-batch-algorithms.md); blog Part 46 "The whole pool, written down" (mame-blog
df89f6c). **The standing directive's goal is REACHED: kernel + 4 probes + all 72 effect
programs + 3 data records = the entire pool has full algorithm annotation** (README now
carries the complete inventory table + a state-of-the-documentation note). Findings:
- ★ rec58-61 (mic reverbs Room/Karaoke/Stage/Cave, unit 7) = a THIRD reverb architecture:
  series-allpass (Schroeder) tank at HALF SAMPLE RATE — FLAG3 = fs/2 frame-parity strobe
  (design requires strict alternation; kernel scrolls I3 only on high frames, in u7's call
  delay slot), program phase-splits 3+3 allpasses across the parity, 1 I3 word = 2 samples
  (18000 w = 816 ms reach). Audio-rate unity-DC LPs = decimator + 2 interpolators. Room
  RT60 ~2.3 s / Stage 3.2 / Cave 3.7; Karaoke = tank collapsed to ONE 363 ms k=0.7 echo
  (zero-gain APs = pure delays) + 91 ms stereo offset. CLOSES kernel opens: FLAG3 function,
  {u6,u7} shared-window corner (u7 uses NO I6/I2), and why boot init skips zeroing MSGR2
  (= the mic reverbs' I3-cursor cell). FLAG3's physical driver still untraced (function =
  design fact) — the emulator's DSP model will need the fs/2 strobe if u7 is ever fed.
- ★ rec67-69 (BRASS SIMULATOR1-3) = physical-modeling cluster: shared 2-state nonlinear
  "lip" ODE (u'=x-v-0.0667u^3-0.7u^2; zero-at-equilibrium output = transient-only
  distortion), cubic +-2/3 clipper (rec62's), +6 dB Nyquist shelves. rec67 = the pool's only
  PITCH TRACKER (once-per-cycle period detector -> period-locked +-T/2 ping-pong grain tap);
  rec68 = naked model 4x-oversampled; rec69 = lip COUPLED to a 512-smp Karplus-Strong bore
  (fb -0.8 through (1+z^-1)/2, odd-mode comb ~43 Hz) feeding back into the lip equation.
- ★ combis = exact engine quotations: rec70 (= GUI Feedback Chorus AND Delay+Chorus) = float
  rec13-echo -> 1-voice rec06 chorus geometry; rec71 = echo 8000/8000 -> rec09's flanger
  (0.70 float regen, mono LFO + negation); rec72 = echo -> rec27's vibrato (full-replace,
  +-112 smp); rec75/76 = ONE PM, engine A/B split in DATA (float-stored curve A/B LUTs +
  PM-state tone-smoother pole 0/0.8) with the family AGC as the advertised "COMP".
  Combi LFO rates ship REAL (0.673/1.346 Hz), unlike the chorus-family placeholders.
REMAINING on the DSP side = LIVE experiments only: (1) u8 DM coefficient dump (EQ flat
question), (2) DspEffectSelect (0x48405815) unit/type/slot capture (unit numbering + send-bank
order), (3) FLAG3 net + rec67 grain character on real hardware. NEXT idle-time track per the
standing directive = maincpu CONVERT growth (66 fns re-assemblable of 2302 named) + naming.

## TICK 2026-07-19 — ★★★ MODULATION/PITCH CLUSTER + GUI GROUP TABLE FULLY DECODED (DSP-doc directive)
Batch rec11/27/28/29/32/33/49/50/57 documented (kn7000_disassembly ce32444, NEW
dsp/modulation-pitch-family.md); blog Part 45 (mame-blog); catalog addendum §7.6 in THIS repo.
Findings:
- ★ GUI GROUP TABLE true layout = {u16 count, char name[16], u16 0, u32 list_ptr} (24B) — the
  §7.5 bank-byte pairings put some names on the NEIGHBOR's list. Complete name->type->record walk
  (both copies) now in modulation-pitch-family.md §1. Renames: rec13=DUAL DELAY, rec47=REVERSE
  WAH, rec48=LFO Wah, rec46=LFO Filter, rec62-65=DISTORTED AMP, rec17/37/38=DISTORTION group,
  rec18/39/40=OVERDRIVE, rec19=FUZZ, rec06 also = Sound-DSP Chorus (0x01), rec33=menu group SPACE.
- rec28/29 suspicion RESOLVED: rec28 = AUTO WAH (Wah1-5, 0x34) = rec74's wah standalone
  (IDENTICAL polynomial: a1=1.99594-1.28e^2, a2=-(1-0.1e+0.02e^2), g=0.05e-0.01e^2; parked
  447 Hz at r=1/g=0, sweeps to 6.4 kHz at the 0.8 cap, y=4g(w-w2)); rec29 = PEDAL WAH (Wah1-3,
  0x33) = same resonator but the audio detector is DEAD CODE — sweep source = host cell c004
  (pedal), fixed-point smoother then 5.8/46 ms glide. Fork fossil like rec24's dead LFO.
- rec11 = GUI ENSEMBLE (0x06/0x0E): hexaphase 3-voice chorus (one LFO re-read at +0/67.5/135 deg;
  R depths NEGATIVE 0xFFC00000 = antiphase in data; 6 phases cover the cycle). M13=+0x50 idiom.
- rec27 = VIBRATO: wet-only single tap, NO dry, MONO source, 1.35 Hz quadrature pair, ~21 cents.
- rec32 = MIXUP: burst vibrato — modulators are PRODUCTS sin(1.35 Hz)*sin(21.5 Hz quad pair) =
  beating 20.2/22.9 Hz; bursts swell/null 2.7x/s, to +-3.1 semitones at template peaks, mono src.
- rec33 = SPREADER (group Space, 2 params): stereo widener = 16 float FIR coeffs IN PM STATE
  (two channel-swapped 8-sample decorrelation FIRs) + identical +8.2 dB @349 Hz bells (unity
  DC/Nyq) + antiphase UNITY mono Haas echoes 12.3/18.1 ms (rec08's 800-smp constant doubled).
- rec49 (CHORUS-screen Chorus1-4, unit9) / rec50 (TRIO CHORUS, insert): THIRD LFO idiom —
  overflow-reflect TRIANGLE oscs (IF AV inc=-inc; signed inc in PM state; 0.386 Hz) + magic-circle
  sine 7.72 Hz; taps/ch {tri, -tri, sine} = 2 contrary CONSTANT-SLOPE detunes (+-7.8 / +-14.5
  cents) + shimmer; rec49 adds mirror-flat tone slot + exact +2.0 dB Nyquist shelf; template
  stereo degenerate (host phases decorrelate — osc2 exists for R).
- rec57 = VOICE CHANGER (0x78, Vocal Effect): dual wrapped-saw granular detune; windows=|phase|
  antiphase triangles (sum==0.5, each ZERO at the other tap's wrap = jump-free equal-gain
  crossfade); grain 0.743 s; L -12.7 / R +12.7 cents. ★ R input reads DM(0x1F,I4) = the PREVIOUS
  slot's R input — in KN7000 AND KN6000 builds (fact; bug-vs-intent open). Distinct from rec66's
  reflected-ramp engine (no gate/AGC/telemetry).
records.tsv: 9 rows re-identified conf high + 17 group-name corrections; syms rewritten x9;
addenda in 5 docs; listings regenerated.
REMAINING undocumented queue (updated): rec58-61 mic reverbs (unit-7 'Chorus'), rec67-69 BRASS
SIM, rec70/71/72 combi back-ends, rec75/76 COMP+X+DELAY; unit-role live capture + u8 DM dump
still open.

## TICK 2026-07-19 — ★★ EXCITER + DYNAMICS + EQs + DISTORTION MAP (DSP-doc directive)
Tone-shaping batch rec20/21/25/22/23/34 + rec17/18/19/38/39/40 documented (kn7000_disassembly
634ba34, NEW dsp/dynamics-eq-exciter.md); blog Part 44 "The exciter was real too" (mame-blog
8d9abdc); routing-note update in THIS repo (effect-multi-unit-routing.md 2026-07-19 section).
Findings:
- rec20 (0x23, GUI EXCITER1-3): the REAL harmonic exciter completing Part 43's contrast — static
  drive -> 33-pt PWL LUT (= rec37's template curve) -> resonant BP 3556 Hz r=.758 whose g=0.2125
  makes the peak UNITY (harmonic-band selector) -> wet 0.5 ADDED TO DRY x c00b master (template 0).
- rec21=rec25 (0x24/0x29 Comp/Limiter, identical PM): peak detector |(L+R)<<9| atk 1/32 (0.73 ms)/
  rel 1/2048 (46 ms); gain = 1/3+(2^31/6)/env via RECIPS + 3 NEWTON iters (full precision — the
  distortion AGCs keep the seed), clamp 2.0 below 0.1 where the curve meets it EXACTLY; static law
  out=e/3+1/6 = soft knee gliding 6:1 -> 1.5:1; stereo-linked; CLIP 24-bit = the final rail.
- rec22 (0x25 SLOW ATTACKER, 28 words): two-target gain slew — thr 0.125: open tau 2^15 smp =
  743 ms (the swell), close tau 2^7 = 2.9 ms (reset for the next note). rec12's gate machine
  pointed at the attack.
- rec23/rec34 (0x27 Parametric EQ / 0x4F unit-8 EQUALIZER): SAME 5-section cascade (1st + 3
  biquads + 1st); template numerators = BIT-EXACT MIRRORS of denominators (H=1, provably flat)
  with poles PRE-PLACED at ~124 Hz + octave-spaced mids (496/992/1985 param; 484/969/1940 5-band)
  + high; presets move only the zeros. ★ KERNEL CORRECTION: helper 0x831B IS this cascade
  (LCNTR=3 = the biquad loop, NOT "3-tap interpolation"); rec34 = 13-word wrapper, rec23 = the
  inlined twin. ★ u8 MASTER-INSERT ANSWERED (static): rec34 = pure in-line full-replace (no
  wet/dry/makeup), matches u8's copy-through empty stub; NO DSP-side chaining — the TG must close
  unit0->u8->DAC. Open: live u8 DM dump c004..c019 (host bank appears NON-mirror even at flat —
  explains the 2026-07-12 15% diff; doubles as the EQ-active baseline).
- Distortion cluster byte-diffed: rec38 = rec37 +-2 words (levels; bank -> resonant LP 1744 Hz =
  Fat); rec40 = rec39 +-4 (levels + Haas 400->200; mid-bump bank); rec18/39/40 = GROUP-B engine
  (PM-state tone smoother 0.10/0.40 host-rewritable + unity-DC biquad; rec39 shares one bank via
  a MODIFY(I0,-8) rewind); rec17/19 = filterless group A (rec19: rail curve, release 1/128 FASTER
  than attack, drive clamp 2.0 = -6 dB below-threshold gate). Three LUT curves pinned (knee A
  7.5/1.5/0.5; smooth B 8/2.67/...; rail C 10.67/4.33/~0.08).
records.tsv 13 rows -> conf high; syms rewritten x12 + rec04 label; listings regenerated.
REMAINING undocumented queue (updated): rec11 (0x06/0x0E chorus), rec27 VIBRATO, rec28/29 (bank-
0x38 wahs — "dynamics + biquad" now suspicious given this family), rec32 MIXUP, rec33 SPREADER,
rec49/50 choruses, rec57 VOICE CHANGER, rec58-61 mic reverbs, rec67-69 BRASS SIM, rec70/71/72
combi back-ends, rec75/76 COMP+X+DELAY; unit-role live capture + u8 DM dump still open.

## TICK 2026-07-19 — ★★ ENHANCER DECODED + TRUE PHASERS + GATE REVERB (DSP-doc directive)
Batch rec08/10/47/73/12 documented (kn7000_disassembly a8526d0, NEW dsp/phaser-enhancer-gate.md);
blog Part 43 "What the Enhancer enhances" published (mame-blog b2928cc). Findings:
- rec08 (0x03, GUI Enhancer1-6): the Technics ENHANCER is NOT an exciter — zero nonlinearity. It is
  a PHASE-ROTATION loudness/width processor: 4x 1st-order allpass k=0.876 (1-smp states in the DM
  param cells, -360deg midband) -> complementary unity-gain LP 400 Hz + HP 2.04 kHz, per-band Q31
  gains, sum ADDED to dry (+6 dB extremes, mid scoop) + ch0 delayed 800 smp (18.1 ms) vs ch1 delay 0
  = Haas widener. No feedback (old "comb+allpass reverb" reading dead). Exciter = rec20 separately.
- rec10 (0x05/0x0D): the pool's TRUE PHASER — the LFO output IS the allpass coefficient (k=0.876
  +-0.12 Q31, f90 28 Hz-1.9 kHz, no bilinear/Newton needed for 1st-order), 5+5 stages, LFOs in
  permanent quadrature (+90deg phase template), float cascade feedback c008, wet-only x2 — notches
  form at the TG send mix. rec73 (0x44 DELAY+PHASER) = rec13's echo (8000/10000 smp, 0.6) in FLOAT
  undamped -> 3-stage same cascade (mono LFO, 0.6 fb) w/ INTERNAL 50/50 dry/wet.
- rec47 (0x90, GUI Wah1-8 bank 0x3A): NOT a phaser — the FOURTH WAH: rec46/48 bilinear+Newton engine
  (q=0.125, Q=8 BP) swept by an ENVELOPE (attack 1/256 / release 1/2048 as floats) DOWNWARD:
  4.27 kHz at silence closing to 197 Hz loud (opposite law to rec74).
- rec12 (0x08, REVERB-screen Short/Medium/Long Gate): the GATE REVERB — mono tank of 3 Schroeder APs
  849/1422/1498 smp (k .6/.6/.4; k12 lives in PM state 9801) in a -0.5 loop through a unity-DC damp
  (loop 85.5 ms, RT60(DC)~0.85 s) + out-of-loop AP 2002 decorrelator; gate OUTSIDE the loop (tank
  rings while shut): thr 0.2 (~-56 dBFS), attack tau 22.7 ms, HOLD counter (gate time = 0x7FFFFFFF -
  PM9804, preset-set), release x0.999/smp (157 ms), 4-instruction retrigger debounce that works ONLY
  because ALUSAT saturates -1+-1. records.tsv 5 rows -> conf high; syms rewritten x5 (rec10 "5/6
  stages" was a miscount: 5+5); insert-effects doc follow-up note; listings regenerated drift-clean.
REMAINING undocumented queue (updated): rec11 (0x06/0x0E chorus), rec17-19 distortion variants,
rec20 EXCITER, rec21/25+22 comp/limiter/slow-attacker, rec23/34 EQs, rec27 VIBRATO, rec28/29 (bank-
0x38 wahs), rec32 MIXUP, rec33 SPREADER, rec38-40 distortion detail, rec49/50 choruses, rec57 VOICE
CHANGER, rec58-61 mic reverbs, rec67-69 BRASS SIM, rec70/71/72 chorus combis, rec75/76 COMP+X+DELAY;
unit-role live capture still open.

## TICK 2026-07-19 — ★★★ ROTARY SPEAKER FOUND + GUI DESCRIPTOR TABLE DECODED (DSP-doc directive)
The rotary question is SETTLED (kn7000_disassembly e35a563, dsp/tremolo-rotary-family.md): the GUI
ROTARY SPEAKER / ROCK ROTARY is the 8-preset identical-PM family rec30/35/36/41-45 + rec16 ("modulated-
delay chorus, conf low" until now) — a FULL LESLIE: drive -> PWL saturation table -> 1.57 kHz smoother
-> crossover (helper 0x8300 = parallel drum resonator 500.5 Hz + horn bandpass 1985-4888 Hz preset-
voiced) -> helper 0x830B = TWO magic-circle sin/cos rotors with 93 ms RATE GLIDE (state {target,
current,-1}; drum 5.512 Hz / horn 6.431 Hz = exactly 7:6) -> Doppler taps (horn quadrature mic pair
320+-29 smp = +-43 cents, drum antiphase 160+-40 = +-51 cents); rec16 = same program rebuilt
(ASHIFT-8 vs LSHIFT-8+NOP), Rock voicing. KEY ENABLER: the ROM's GUI preset-descriptor table decoded
(600 entries @0x4858FB8C..; params/name16/type/nparams/ptr/id + group tables @~0x4870FE00) — GUI name
-> type -> record is now ROM FACT for every effect screen: Tremolo1-8=rec24 (in-phase AM, rec26+1
instr, dead quadrature LFO), Auto Pan1-7=rec26 (quadrature AM), Ring Mod.1-4=rec31 (bipolar AM,
344.5 Hz audio carrier INTENTIONAL), Vocal Harmonizer=rec66 (3-voice reflected-tap granular pitch
shifter, just-maj7 template +386.0/+702.0/+1088.0 integer cents, host telemetry via IOP reg 0x0C),
GUI Enhancer1-6=rec08 (unit-0 tension RESOLVED), Gate reverbs=rec12, Vibrato=rec27, Mixup=rec32,
Spreader=rec33, VoiceChanger=rec57, mic Room/Karaoke/Stage/Cave=rec58-61, Brass sim=rec67-69,
Delay+X=rec70-73, Autowah+Delay=rec74 (touch-wah reading CONFIRMED). records.tsv: 14 rows
re-identified + ~45 stamped with ROM-fact names; syms rewritten rec16/24/26/30/31/35/36/41-45/66.
Blog Part 42 published. REMAINING undocumented queue: rec08 (Enhancer engine), rec10/47/73 (phasers),
rec11/16-detail... actually rec11/27/32/33/49/50/57 detail, rec12 gate-reverb topology, rec17-19
distortions, rec21/22/25/28/29 dynamics/wah, rec23/34 EQs, rec58-61 mic reverbs, rec66 constant-level
detail (conditioning polynomial), rec67-72 composites, rec75/76; unit-role live capture still open.

## TICK 2026-07-19 — ★ REVERB FULLY DOCUMENTED + BLOG PART 38 PUBLISHED (DSP-doc directive, item 1 done)
The reverb annotation is COMPLETE (kn7000_disassembly 2888f7f: dsp/reverb-algorithm.md + deep syms
rec51-56 + records.tsv relabels): rec51-56 = ONE Moorer-style reverberator (2 damped combs 368/328 ms,
tank decay -0.2435 -> RT60(DC) ~1.8 s, matches the live tail) with Dattorro-style 4-allpass input
diffusion (k=0.618), absorbing AP 118.8 ms, 258-word stereo-decorrelation line — all delay lengths
exact from the -1/sample cursor address arithmetic; rec51=54=55=56 byte-identical PM, rec52/53 differ
only in 4 early-tap immediates; rec53's integer-ms early taps pin fs=44.1 kHz; the unit-9 "Reverb"
whitelist records rec06/07/09 are actually choruses + a flanger (tail-incapable) — the real reverb sat
under the "Enhancer" label. Open (doc §7): GUI-name<->preset + unit-role mapping; decisive experiment =
breakpoint DspEffectSelect 0x48405815 while switching Room1->Dark2. Blog Part 38 "The reverb was filed
under Enhancer" published (mame-blog cb17200). NEXT per the records.tsv sweep: the chorus family
rec06/07/09 (already partially decoded by this pass — quadrature 2-tap engine traced, LFO-rate
templates still PROVISIONAL) then the multi/SOUND-DSP inserts.

## TICK 2026-07-19 — ★★ SHARC UPSTREAM SERIES SUBMISSION-READY (prep agent complete)
The upstream patch series is REGENERATED, REBASED and VERIFIED against the current base (kn7000-base
@957e9dec1b4). notes/upstream-patches/ now holds a 9-file `git am`-able series (old 01-05 replaced;
00-consolidated kept, still clean): 01-03 = INTERPRETER implementations (fixed AVG; general single-fn
fixed multiplier decode; multifunction fixed-MAC forms) -- NEW FINDING: the old series' failure was NOT
the 630c68d average dependency but 2d308c7's interp hunk patching the FORK-ONLY MAC block from 3aca274,
and upstream's interpreter THROWS on all general fixed-multiplier forms, so the interp slices must lead
the series to keep the in-tree oracle; 04-06 = ALUSAT DRC series (kn7000.cpp 66MHz hunk dropped from
b1028bd); 07-09 = native DRC MAC/multiplier/AVG. VERIFIED: cumulative git-apply CLEAN zero-offset on
pristine base, final tree byte-identical to the rebased fork replay, ALL 9 intermediate states compile
(g++ -fsyntax-only, real MAME flags). RUNTIME ORACLE: money.lua reverb on the published binary, 2 runs
BIT-IDENTICAL, new current-era baseline md5 44b09b9d0eaae59d9a65e5b4f4e72ec0 (0787b60c is historical --
release-ramp/effect-return/SIO changes moved the WAV; ab_before.wav preserved in the 07-16 snapshot).
DATASHEET CROSS-CHECK (§A device PR gate): TR appendices Table F-1 CONFIRMS vector base 0x8000 =
"beginning of Block 0", RSTI offset 0x04 (reset 0x8004), IRQ0 0x8020, external space 0x20000; catalogue
§A corrected (0x20004/0x20000 were base-2106x values); DM windows 0x9800/0xC000 stay RE-derived (UM
ch.5 not in our PDFs) -- device PR unblocked with that labelled. Felipe's checklist = bottom of
notes/sharc-upstream-patch-series.md. Scratch worktree cleaned; ../mame untouched (branch/tree).

## TICK 2026-07-19 — ★★ SIO->MN10300-CORE REFACTOR SHIPPED (Felipe's request, wf_920ebe24 complete)
Core 9bb2de8: on-chip SIO (3ch, 0x34000800-2F) implemented IN mn10300_device via internal address_map
(MN10200 precedent; addrmap.cpp appends device internal maps AFTER the driver map -> core window wins,
neighboring driver INTC/timer entries untouched). Byte-exact register semantics incl. the deliberate
ch2-status-bit omission; per-channel devcbs sio_tx_cb/sio_tx_done_cb/sio_rx_rdy_cb/sio_rx_enable_cb +
public sio_rx_push/sio_rx_ready; save-stated. Integrate 9eb0e4b: kn7000.cpp -172/+62 (sio_r/sio_w/state
removed, devcbs wired: ch0->cpanel + 40us tx-done timer->grp 0x11, ch1/2->MIDI UARTs + grp 0x12/0x14;
endpoints repoint to m_maincpu->sio_rx_push). All 5 MN10300 models inherit. VERIFIED: build clean,
-validate kn7000+kn6000, published; live home/BALLAD/SD-MENU/kn6000-boot snapshots match pre-refactor.
DONE: blog Part 37 published (mame-blog 736dd4a, "What the ancestor knew"); roadmap item 2 flipped by
the SIO workflow itself (kn5000-docs 0c17afa); Parts 35+36 earlier (fb7f139). MEMORY refreshed (new
kn7000-session-2026-07-18-results memory + index line). SESSION QUEUE now EMPTY of committed follow-ups;
remaining big items all need Felipe (Phase C dumps, reverb A/B) or are next-of-kin refactors
(INTC/timers into the core, SHARC upstream submission prep).

## TICK 2026-07-19 (Felipe back, interactive) — TWO WORKFLOWS IN FLIGHT, do not duplicate
1. wf_5774e9e1-d0b "rhythm-names-offbyone": **COMPLETE 2026-07-19 (see the two ~05:xx ticks below)**
   — hypothesis falsified, split is faithful, no code change; bug note CLOSED, verifier committed.
2. wf_920ebe24-bf2 "sio-into-mn10300-core" (FELIPE REQUESTED): **COMPLETE 2026-07-19 ~02:3x.**
   Core stage 9bb2de8 (mn10300_device models the 3-channel SIO via an internal address map,
   MN10200-precedent; per-channel devcb: sio_tx_cb / sio_tx_done_cb / sio_rx_rdy_cb /
   sio_rx_enable_cb + public sio_rx_push/sio_rx_ready). Integrate stage 9eb0e4b (driver HLE
   retired: sio_r/sio_w + m_sio_* state + the 0x34000800 map entry gone; endpoints repointed at
   m_maincpu->sio_rx_push; devcbs bound in kn7000(machine_config) -- ch0 tx->cpanel/tx-done->40us
   panel_txdone->grp 0x11/rx-rdy->0x10/rx-enable->cpanel, ch1/ch2 tx->MIDI UARTs, rx-rdy->0x12/0x14).
   KN6000/6500/2400/2600 inherit via kn7000(config). Sole semantic delta: ch0 no longer asserts
   0x10 on an RX-ring OVERRUN drop (unreachable in practice, 64-byte ring drained per interrupt).
   LIVE-VERIFIED on the published binary: kn7000 home + BALLAD genre list + SD MENU (snaps
   kn7000-emulator/snap/kn7000/0007-0009.png, script sio_core_verify.lua), kn6000 play screen ==
   notes/img/kn6000-boot-playscreen.png (snap/kn6000/0002.png). -validate clean both. Published.
   Roadmap docs item 2 (kn7000-roadmap.md "Architecture") flipped to done. BLOG PART 37 UNBLOCKED.
Cron is now every 20 min (:07/:27/:47). ★ STANDING RULE from Felipe (2026-07-19, saved to memory):
BLOG PROACTIVELY — whenever there is something to tell, write the post without being asked.
IN FLIGHT ALSO: blog agent writing Parts 35 (style-names fix incl. the falsified off-by-one) + 36
(SD round-trip + the toggle retraction). QUEUED: Part 37 = the SIO->mn10300-core refactor, WRITE IT
as soon as wf_920ebe24 lands (include the MN10200-ancestry angle from blog Part 34).

## SESSION 2026-07-18 AUTONOMOUS PLAN (Felipe away a few hours, standing green light)

DONE this session (all committed):
- run.sh attaches the bundled SD card by default (kn7000_mame 8a7d8b2) — fixes "ERROR 93 regardless of cover".
- cpanel-input refactor BOTH drivers: 22 CP{board}_SEG{col} button ioports moved into the cpanel DEVICE
  (device_input_ports()); layout tags now "cpanel:CP…". KN7000 df73be3 (verified: build+validate+listxml+boot,
  published); KN5000 efc8d90 in ../mame (compiles clean; link blocked only by pre-existing genie/Qt env issue).
- TECHNI-CHORD ANSWERED: pure software (harmony engine 0x48472EBA, style jump table 0x485BC3B4, interval
  tables 0x485BC390, ZERO TG-register writes; params 0x8080/81/82). Nothing extra to emulate.
- SIO-in-CPU-core analysed: mn10300 core models NO on-chip peripherals; the mn10200 parent core is the
  template (on-chip serial/timers modelled in-core). Identified NEXT-step refactor serving all MN10300 models.
- Docs site FULLY REFRESHED + committed (kn5000-docs 13cece5): roadmap (new "Architecture & code
  organization" section = the 3 items above), NEW kn7000-technichord.md, NEW kn7000-design-language.md,
  control-panel/sound/effects/storage pages refreshed, nav+index wired, Jekyll builds clean.

MORE DONE (this session, continued):
- BLOG PARTS 30-34 PUBLISHED (mame-blog c9d77c8): all 5 posts written in-series-voice, every cited
  commit/address verified against the tree first; posts.json appended in original format (36 entries).
- tools/dis_sharc.sh committed (9908572): one-liner SHARC PM disasm from 8-byte-LE-slot images
  (live Lua dumps + kn7000_disassembly/build/dsp extracts); verified vs the known kernel vector table.

## TICK 2026-07-19 ~02:3x (UTC, next day) — DSP CHORUS FAMILY DOCUMENTED (rec06/07/09) + blog Part 39
Standing directive (document every DSP program) continued past the reverb: full algorithm doc
dsp/chorus-family-algorithms.md in kn7000_disassembly (commit e1a668b) for the three mislabeled
unit-9 "Reverb"-whitelist records — rec06 = quadrature two-voice ensemble/celeste chorus (250+-64
smp taps, antiphase stereo), rec07 = same engine + 0.15 cross-mixed second LFO (template 7.15 Hz),
rec09 = stereo resonant flanger (300+-64 smp FLOAT taps, 0.70 float regen, indep per-channel LFOs).
Shared design language pinned: internal I2 ring only (kernel grants 0x400-word arenas, PM
0x8085/0x8088..), f = fs*incr/2^31 sine LFOs, 16.16 fractional taps, wet-only; the c028..c040 sine
table = the slot data records rec77-79 (sine/tri/square) overwrite -> LIVE LFO waveform morphing.
TWO CORRECTIONS to committed annotation: rec09 LFO phase template 0x20000000 = 90deg (not 45deg;
2^31 wrap, 4/16 steps); kernel MODE1 0x3000 = IRPTEN+ALUSAT (bit13), NOT NESTM -> rec07's +-1.15
modulator sum saturates at +-1.0, swing stays +-64 smp. fs/256 templates quantified absurd (+-157%
pitch dev) -> host-rewrite near-certain, still PROVISIONAL. GUI candidates (PROVISIONAL, via alias
types 0x2C/0x2D/0x0B in the units1-6 whitelist): Celeste / Mod. Cel. / Flanger. Syms enriched
(rec04/06/07/09), records.tsv updated, listings regenerated. Blog Part 39 "Three ways to wobble a
delay line" published (mame-blog 852a5fd). NEXT record family: the Multi/Sound-DSP inserts (start
w/ the big =rec30 chorus family or the phasers) or the resident kernel rec04 itself.

## TICK 2026-07-19 — ★★★ RESIDENT KERNEL (rec04) FULLY DOCUMENTED + MULTI-UNIT ANSWERED (u6) + blog Part 40
The DSP-doc directive's centerpiece: dsp/kernel-architecture.md in kn7000_disassembly (commit
85525e2), every claim PM/DM-quoted, register decodes pinned vs the ADSP-21065L TRM (PDF in repo
root). BIG DECODES: (1) the host protocol IS the 21065L host interface — "reg" indices = the
chip's own IOP registers: reg0 probe 0x20 = SYSCON reset value (HBW=16), 0x0B = MSGR3 (probe
verdicts), 0x40/41/42 = IIEP0/IMEP0/CEP0, 0x1C = DMAC0 (0xA1 = 16<->48 PM commit / 0x41 = 16<->32
DM / 0xA0 = park), data port = the EPB0 FIFO (why index-once-then-hammer works). No checksums.
(2) audio fabric TRM-PINNED: 8 SELF-CHAINING SPORT DMA TCBs (DM 0xC306+, CP+0x8000 = own TCB) ->
8 words/line/sample: TX0A=0xC342 TX0B=0xC34A TX1A=0xC352 RX0A=0xC362 RX0B=0xC36A RX1A=0xC372 (+2
armed-but-unused spares); std mode 24-bit external clock/FS (TG = timing master). (3) mainloop:
10 host-patched CALL slots (slot9 recycles the 0x8D00 boot-init PM); ISR sets MODE2 0x40 = BUSLK
(bus LOCK, corrects "handshake flag") -> host coeff bursts land race-free in the frame tail =
the mid-note hot-patch mechanism; DM(0x2F) = IOSTAT driving the FLAG4 PIN (hw frame-busy strobe);
DM(0x20)=0x3A2 = SDRDIV refresh (corrects "input default"). (4) delay manager: per-slot window
tables (u0 = 0x10748 = 1.53s SDRAM = reverb; u1-u5 0x7918; {u6,u7} & {u8,u9} share) + 6 overlapped
arena-SCRUB stubs (0x80A6+, countdown table 0x9C40) = zero-fill a slot before a new effect.
★ MULTI QUESTION (which slot serves TG send 0x8298) ANSWERED-PROVISIONAL: 3 send banks <-> 3 read
RX lines (4th line readerless, no 4th bank); anchors reverb=u0 (bank0=RX0A) + Chorus-whitelist
u7 on RX0B (bank1) => MULTI bank2 -> RX1A {u8 EQ-locked, u9 wrong whitelist, u6} => **u6** (in
0xC378/9 out 0xC358/9, the slot the +0x0A I4 hop serves). Prior candidates u1/u2/u3/u5 EXCLUDED;
"u6 chorus twin" = the MULTI slot's boot default (rec06 via insert alias 0x2C); SOUND DSP really
lives among u1-u5 (MAME bridge's u9 feed = placeholder). Decisive live test = watch RX1A go
nonzero with MULTI depth>0. rec04.sym enriched to FULL coverage (vector table per TRM E-5, call
slots, scrub stubs, TCB/ring labels; 4 corrections: BUSLK/IOSTAT-FLAG4/SDRDIV/CAFRZ); records.tsv
+ README updated; listings regenerated (drift-clean). Blog Part 40 "A four-kilobyte operating
system" published (mame-blog e7de85e). NEXT (directive): remaining record families — the Multi/
Sound-DSP inserts (=rec30 chorus family, phasers, waveshapers), the unit-7 chorus rec58-61
(FLAG3-gated), EQ rec34, unit-0 reverb-family aliases; then per-record docs are complete.

## TICK 2026-07-19 — ★★ MULTI/SOUND-DSP INSERT FAMILIES DOCUMENTED (10 records, 3 identities corrected) + blog Part 41
DSP-doc directive: dsp/insert-effects-algorithms.md in kn7000_disassembly (commit b3798c7) — the
wah / distortion / delay insert families at the reverb-doc standard, syms enriched (rec13/14/15/
37/46/48/62-65/74), records.tsv relabeled, listings regenerated drift-clean. THE CORRECTIONS:
(1) rec74 (0x46) "tremolo-rotary" = **TOUCH WAH**: no LFO — env follower (atk 1/256, rel 1/2048)
-> QUADRATIC coeff map (g=0.05e-0.01e^2, a1=1.996-1.28e^2) sweeping a bandpass 443 Hz (quiet;
r=1.0 but g=0 => silent by construction) -> ~8.3 kHz (loud) + per-channel echo 4000/5000 smp fb
0.6. (2) rec46/48 (0x8C/0x91) "modulated-allpass phasers" have NO allpass: they compute the FULL
BILINEAR TRANSFORM PER SAMPLE (LFO sweeps g=tan(pi f/fs) linearly; RECIPS + 3 Newton iters for
the denominator reciprocal). rec46 = FIVE 2nd-order LP sections Q=1 (10-pole sweep 19.6 Hz-2.79
kHz @1.35 Hz; old "AllpassStage6" was the output-scale load); rec48 = ONE bandpass Q=8 (+18 dB,
56 Hz-6.56 kHz @0.336 Hz) = the crying-wah voicing. Unlike the chorus family, shipped LFO rates
are MUSICAL (incr in PM state 0x9800). (3) rec62-65 (0x64-67) = textbook cubic clipper y=x-x^3/3
railed EXACTLY at +-2/3 (continuous), DC-block HP 100 Hz, sign-guarded 70 Hz smoother, 4 UNITY-DC
tone banks (A: peak r=.901@2.91k / B: NOTCH exactly there + 322 Hz poles / C: 1.05 kHz honk / D:
softened A). Their AGC prologue is INERT as downloaded (env cell c004 never written under kernel
M4=-2 => drive pinned at the 4.0 clamp; host-writes-c004 = PROVISIONAL); the WORKING AGC is rec37
(0x82): env in PM state, gain 0.111+8.35e8/env meeting the 4.0 clamp EXACTLY at 0.1FS, driving a
33-pt PWL knee-curve TABLE waveshaper (in the c028 window = host-replaceable transfer curve!) +
Haas stereo (L delayed 400 smp, R inverted). (4) echo family rec13/14/15 (0x09/0A/0C): unity-DC
damping in the regen + 0.004/0.996 LEVEL SMOOTHER (fade-in ~30 ms, no zipper); rec13 = dual-mono
181.4/226.8 ms fb 0.6; rec14 = PANNING multi-tap (4 equal taps 136/272/408/544 ms, out banks
0/.3/.6/.9 vs .9/.6/.3/0 = repeats WALK across the field; regen host-gated); rec15 = CROSS-
FEEDBACK ping-pong 90.7/99.8 ms (L<-R, R<-L) — structurally the GUI MULTI default "Cross Delay"
(name PROVISIONAL). NO ROTARY SPEAKER found in the pool; best remaining candidates = tremolo-pan
rec24/26/31 + rec66 (biggest insert). Blog Part 41 "Three wah pedals and no rotary speaker"
(mame-blog 0e81044). STILL UNDOCUMENTED after this pass: rec08/12/16-33 (dynamics/EQ/tremolo-pan/
choruses incl. the 8-preset rec30 family), rec38-40 detail, rec47/50/57/66-73/75/76, unit-7
rec58-61, EQ rec34, unit-9 rec49/70 — next tick continues the sweep (tremolo-pan family first to
settle the rotary question).

## TICK 2026-07-19 ~05:3x — rhythm-names workflow CLOSED (acted on the no-bug verdict; docs+verifier committed)
Acting stage for the tick below: since the verdict is "faithful split, no off-by-one", NO change to
tools/gen_technics_rhythms.py, the installed kn7000_rhythms_synthetic.rom, or the driver — no
rebuild/republish needed (nothing on disk changed; both staged ROM copies remain valid). Durable
documentation instead (commit 1566cb0): notes/rhythm-name-list-bug.md gained a CLOSED section (the
full faithful-split story + decisive bytes); the byte-exact verifier is now tools/genre_truth.py
(portable argparse version, output reproduced line-for-line vs the diagnosis run); full evidence
report committed as notes/genre-name-ground-truth.txt (per-slot tables for all 16 genres + final
verdict). Re-run any time: `python3 tools/genre_truth.py` (defaults = published emulator ROMs +
decompressed program image). Felipe-facing summary: the screen is telling the truth — C&W slot 1
and the other 167 placeholder names await the Phase C hardware dump of the ~4.1MB rhythm flash.

## TICK 2026-07-19 ~05:0x — Phase B follow-up: Felipe's genre-list split VERIFIED FAITHFUL (no off-by-one)
Felipe observed (published build): Latin&World + March&Waltz all-real, C&W all-real EXCEPT slot 1
("COUNTRY 01 ?"), 60s&70s slot 1 real-looking, everything else placeholders. Offline byte-precise
ground-truth analysis (scratchpad genre_truth.py/.txt) CONFIRMS this is exactly the firmware's own
data, NOT a generator bug: the 52 secondary (0x4000-class) nametable entries are 0x4000..0x4033 in
panel order = C&W slots 2-14 (13, "Country Rock".."Cajun Country") + March&Waltz 1-12 (12) +
Latin&World 1-26 (26) + 60s&70s slot 1 (1, 0x4033 = "70s Orchestra", table 0x376B56 — REAL, not a
coincidence). C&W slot 1 (ID 0x000514 -> idx 0x294 -> entry @file 0x3E87E7 = 0x00A8) is plain LOCAL
record 168 whose name lived only on the undumped rhythm flash -> honest placeholder. Synthetic ROM's
nametable+subtable byte-IDENTICAL to the intact copy; simulated resolver (0x48433AC4) returns the
same class+index for all 220 factory IDs on both images, zero divergences, no 0x8000-indirects in
any factory list. 168 LOCAL + 52 SECONDARY = 220. NOTHING TO FIX; the "52 = Latin26+March12+C&W14"
guess was wrong (C&W contributes 13, 60s&70s 1). Felipe-facing: the split he sees is the honest
truth; C&W slot 1 + the other 167 names await the Phase C hardware dump.

## TICK 2026-07-19 ~03:4x (local 00:4x) — ★★★ SD SAVE->LOAD ROUND-TRIP COMPLETE: THE SD WRITE PATH WORKS END-TO-END
GOAL met in full (save validated + load-back validated + distinguishable-state proof). WHY THE OLD
PROBE STALLED (snapshot review, criterion 0): in the SD SAVE MENU "TECHNICS FORMAT" is on soft-key
ROW 2 and "SD-SOUND (SMF) FORMAT" on ROW 4 — ROW 1 IS BLANK; sdsave1.lua pressed LCDR1 into the
empty row (snaps 0002-0006 byte-identical). SECOND latent blocker found: sdcard_from_real_kn7000.img
is root-owned mode 644 — MAME as fsanches can NEVER write it; all write tests ran on a writable
working copy (sdcard_work.img). Backup of the pristine dump made FIRST at
kn7000_scratchpad_snapshot/sdcard_backup_pre_save.img (md5 c3bcea2346cb3bb7d803e8c48aebce78 = original,
verified unchanged after all runs). THE FLOW (all soft keys now mapped): home -> SD CARD LOAD toggle
-> SD MENU -> LCDR2 (SAVE MENU) -> LCDR2 (TECHNICS FORMAT) -> SD SAVE browser (PAGE 1/3: SAVE AS SONG
naming field; FOLDER/SONG lists w/ 01 preselected; content list CURRENT PANEL/PANEL MEMORY/SEQUENCER/
COMPOSER/SOUND MEMORY/PERFORMANCE PADS/EFFECT MEMORY; SAVE=LCDR1, SONG NAMING=LCDR2, FOLDER
RENAME=LCDR5) -> LCDR1 -> ATTENTION "file already exists...Are You Sure?" (YES=LCDR3=CPR_SEG7 0x01,
NO=LCDR4=CPR_SEG6 0x01) -> LCDR3 -> ~15 s of card writes -> "COMPLETED!". EVIDENCE: (1) image md5
CHANGED c3bcea23->68cf2667 (first save) ->c1c33830 (BALLAD save); (2) 154 sectors rewritten in a
textbook FAT pattern — FAT@98/129, dirs@256/288, data clusters 372-437/512+; dir decode: the real
card ALREADY HELD a TECHNICS structure (TFLD001/01001KN7.{EFC,TM,LSW,PMT,MSP,CMP,SQT,ACT} +
KN7000MN.{INF,BAK} — hence the overwrite dialog; the "empty" browser slots are BLANK NAMES, not
absent files, likely also the ERROR-83 story); save rewrote KN7000MN.BAK + the song's .TM/.PMT/.SQT;
(3) browser free space dropped 123,552KB->123,488KB. ROUND-TRIP PROOF (strongest): run D pressed
RHYTHM GROUP BALLAD (CPL_SEG2 0x08, home rhythm -> "BALLAD 01 ?") before saving; run E on a FRESH
BOOT (default rhythm "8&16BT 01 ?") did SD MENU -> LCDR1 -> LOAD browser (LOAD=LCDR1) -> LOAD
(~95k SPI reads) -> home now shows **RHYTHM "BALLAD 01 ?"** — the saved panel state came back off
the card. spi_sdcard write path: CMD24 handler writes straight to the image, ignores incoming data
CRC (no init-value trap on writes; reads needed the init-0 fix, writes don't). SHIPPED: run.sh now
attaches a WRITABLE WORKING COPY by default (sdcard_work.img auto-created from the pristine dump on
first run; delete it to factory-reset; pristine dump stays read-only) — publish-binary.sh heredoc +
live kn7000-emulator/run.sh + README bullet ("The SD card works, including saving"). Scripts
archived: tools/sd_roundtrip_save.lua / tools/sd_roundtrip_load.lua (full key map in headers);
throwaway probes sdsave2-5/sdload_rt.lua + snaps left in kn7000-emulator. NEXT (SD): SONG NAMING
dialog (LCDR2 in the save browser) for named saves; SD-SOUND (SMF) FORMAT save leg (SAVE MENU row 4);
give folder01/song01 a visible name so the load/play demos show a titled song; blank-name files vs
ERROR 83 hypothesis test.

## TICK 2026-07-19 ~02:4x (local 07-18 23:4x) — ★★ PHASE B INSTALLED & VERIFIED: THE "8 BEAT 1" BUG IS FIXED (style lists show per-slot names)
The synthetic "Technics Rhythms" resource is INSTALLED in the driver and LIVE-VERIFIED (kn7000_mame
09fc7e5, built + published). Install: new optional ROM_REGION32_LE(0x400000, "rhythms") in
ROM_START(kn7000) loading kn7000_rhythms_synthetic.rom (0x3EB07F bytes, BAD_DUMP CRC 1fff54c5
SHA1 c6c9615c40745096b436ec98e9c61d83295b7ebb; regenerated bit-identical to the Phase B binary by
tools/gen_technics_rhythms.py, staged in kn7000_mame_build/roms/kn7000 + kn7000-emulator/roms/kn7000).
Mapped at the last-resort probe window 0x54E00000 — from machine_start() via install_rom, NOT a
maincpu_mem entry: ★ GOTCHA (found via segfault) — the map is shared with KN6000/6500 (no "rhythms"
region) AND is constructed during the validity check, where memregion() has no machine and CRASHES;
runtime install sidesteps both. -validate clean. EVIDENCE (ballad_verify.lua / latin_verify.lua in
kn7000-emulator, snap/kn7000/): 0007=home (boot clean; home rhythm name now "8&16BT 01 ?"),
0008=BALLAD list = "BALLAD 01 ?".."BALLAD 10 ?" PAGE 1/2 (distinct placeholders, matches the
generator's --verify prediction exactly), 0011=LATIN & WORLD list = REAL factory names ("Bossanova 1",
"Bossanova 2", "Beguine", "Rhumba", "Bolero", "Cha Cha", "Samba", "Samba Rock", "Salsa",
"Tango Argent") PAGE 1/3. Lua-probed live: magic "Technics Rhythms" reads at 0x54E00000; the
earlier-probed 0x54E10000 lands mid-resource (0x17 0x00 0x10 f4..., no magic) so the selector inits
from the right base. Honest labeling everywhere: placeholders end in " ?"; the 168 factory names stay
unrecoverable until the Phase C hardware dump (then: dump IC21/IC18+IC20, replace the synthetic ROM
with the real image + real map base). REMAINS: nothing for Phase B; Felipe-facing note = lists now show
52 real + 168 " ?" names.

## TICK 2026-07-19 ~00:2x (cron) — ★ PHASE B COMPLETE (synth resource built); SD SAVE probe stalled (uninvestigated)
PHASE B (wf_b672d391-0c8) LANDED, tool committed a012fdd (tools/gen_technics_rhythms.py), binary at
scratchpad/technics_rhythms_synth.bin. DECISIVE FACTS: (1) the table-ROM copy @0x483E828C is an INTACT
DIRECTORY (count=0xDD=221, full 0x800 nametable, all 169 local + 8 aux offsets) with ZERO record
payload — BORN truncated at 0x1248 bytes (tail cleanly erased, not a bad dump). (2) ★ the 931
previously-decoded names are MUSIC STYLIST names, NOT rhythm names (StyleRecordTable 0x4873BEE8 =
stylist table; rhythm resolution never touches it). (3) REAL index formula idx=((id&0xF00)>>1)|(id&0x7F);
prog-ROM reverse map 0x48734EE4 (idx -> genre<<8|slot) VERIFIED 220/220. (4) the 168 plain-entry
display names exist ONLY on the undumped ~4.1MB rhythm flash (exhaustive negative search: all sibling
firmwares = count-1 stubs, KN5000 ROMs, .AST, manual, web archives — none have them). (5) 52 secondary
names DO decode from intact 0x48244F78 ("Country Rock".."70s Orchestra"). Synth strategy: verbatim
intact directory + stub aux records (byte-justified) + 169 local records cloned from stub record 0
(real 0x530A-byte "8 Beat 1" record; name field rewritten per-slot; 60 slots size-truncated safely).
NEXT (Phase B install): add ROM_REGION + map at 0x54E00000 in kn7000.cpp loading the generated binary
(label SYNTHETIC; real names where known, genre+slot-derived names otherwise), build, publish, verify
BALLAD list (SEG00 0x10... use the RHYTHM GROUP BALLAD button + snapshot) shows per-slot names not 10x
"8 Beat 1". Note Felipe-facing: the 168 factory names are UNRECOVERABLE without the Phase C hardware
dump — the synthetic list will show honest placeholders + 52 real names.
SD SAVE probe (sdsave1.lua, this tick): reached SD SAVE MENU -> pressed LCDR1 (TECHNICS FORMAT
candidate) -> ZERO new SPI R/W, image md5 unchanged — the save flow did not engage; snapshots
0000-0006 in kn7000-emulator/snap/kn7000 UNREVIEWED (do that first next tick; maybe the SAVE MENU's
keys differ or a dialog needs another key).

## TICK 2026-07-18 ~23:0x — ★★ RETRACTION + RESOLUTION: SD MENU SOFT KEYS ALL WORK (my sweep was a stale-state artifact)
The wf_194ce2c2-824 empirical digger FALSIFIED the 21:5x tick's conclusion. **SD CARD LOAD
(:cpanel:CPR_SEG1 0x80) is a TOGGLE** (home->SD MENU, SD MENU/any-sub-screen->home, even dismisses
ERROR dialogs) — my un-state-verified sweep pressed LCDR keys against the WRONG screen. With a
pixel-probe-verified menu pre-state: **ALL 9 SD MENU items open via their soft keys** — LCDR1 ->
**SD LOAD BROWSER READING THE REAL CARD** (volume KN7000_MAME, PAGE 1/3, FOLDER+SONG lists,
123,552KB free), LCDR2 SD SAVE MENU, LCDR3 SD SONG MEDLEY, LCDR4/5 SD-AUDIO/SD-SOUND PLAY (ERROR 83
"file empty" = the real card's FIRST FILE IS EMPTY; the play path itself runs), LCDL1-4 SD TOOLS/
PREFERENCES/FAVORITE SONGS/CUSTOM STYLE. DIAL/PAGE = no-op on this screen; EXIT works. No patch
needed. Scripted recipe: from home press CPR_SEG1 0x80, wait ~2s, VERIFY the menu, then the soft key
(0.4s press). Digger scripts: kn7000-emulator/sdnav_*.lua. LESSON (recorded): always verify the
pre-state screen before attributing a press result; SD CARD LOAD toggles. The static digger's gate
speculation ("boot paints menu w/o mode entry") is MOOT, but its MILK RE is durable gold: screen
records (SD MENU @0x486809B9 title 0x104 mode 0x18, selectors right 0x10-0x14 left 0x90-0x93 ->
tags/titles incl. LOAD sel 0x10 -> title 0x105), the full dispatch chain (PanelButtonDispatch
0x484ADB59 -> pump 0x484145FF -> resolver 0x4841473A -> ApPostEvent 0x50005/0x50006 -> PsMenuBoxProc
0x4841CCC8 hit-test view+0x28 -> AcTitleMenuProc 0x4841D0EC actions), mode/title vars 0x5000097C/
0x5000099C, SD-state getter 0x4855E80C. FOLLOW-UP (sdload_deep.lua, this tick): browser confirmed
live — "KN7000_MAME" volume, 123,552KB free, FOLDER+SONG lists render but the slots are EMPTY
("0% used" = the bundled card image holds almost no content); the browser's LOAD key fired ~96k SPI
data-port reads (real card traffic) and returned home; ERROR 83 on play paths = empty first file,
consistent. **The entire SD UI chain works; the gap is card CONTENT.** NEXT (SD): a SAVE->LOAD
ROUND-TRIP entirely in-emulator — SD MENU -> LCDR2 (SD SAVE MENU: TECHNICS FORMAT / SD-SOUND (SMF)
FORMAT) -> save CURRENT PANEL to a slot (watch for a naming dialog), verify FAT writes reach the
host image (spi_sdcard write path + image mtime/content), then LOAD it back and confirm. That
validates the write path AND creates content for the load/play demos.

## TICK 2026-07-18 ~22:4x — ★ PHASE A LANDED (probe windows -> physical ICs); PHASE B (synthetic resource) LAUNCHED
Phase A committed (4e77f57, notes/table-rom-structure.md): **0x54E00000 is a SOFTWARE last-resort
constant, not a real KN7000 aperture** (every data chip is 4/8MB on aligned selects; the 74VHC139
quadrant for 0x548xxxxx is drawn N.C.) -> the labeled-SYNTHETIC install at 0x54E00000 is the honest
emulator fix; the REAL "Technics Rhythms" home is IC21 @0x57000000 (32Mbit factory flash, size-twin
of KN5000 rhythm_data IC14) or the factory-set part of the custom flash IC18/IC20 @0x56000000
(+0x96800000 = its +0x40000000 uncached AMD-cmd mirror; custom CE ignores A23). 0x40010000/0x40610000/
0x40810000 = nothing (sibling-model windows). Phase C (hardware dump w/ Felipe) should read 0x56000000/
0x57000000/0x57800000 + live-probe 0x54E00000. BONUS: a TRUNCATED copy of the real resource exists in
the DUMPED table ROM at 0x483E828C (directory entry [83], magic verified; deep records cut off).
**Phase B workflow wf_b672d391-0c8 LAUNCHED**: decode the truncated copy + build style-ID->name
correlation -> gen_technics_rhythms.py + synthetic binary + resolver self-check. When it lands: add the
ROM_REGION + map at 0x54E00000 in kn7000.cpp (label SYNTHETIC), build, publish (ONLY once the SD
workflow frees the display), verify the BALLAD list shows real names.

## TICK 2026-07-18 ~22:2x (cron) — blog/docs polish while both background tasks run
Both investigations still in flight (SD-nav workflow wf_194ce2c2-824 0/3 done, its MAME runs own the
display -- do NOT rebuild/publish or run MAME until it lands; Phase A agent mid-work, has already
committed table-ROM findings incl. ★ entry [83] 0x483E828C = 'Technics Rhythms' in the DUMPED table
flash, previously mislabeled 'Technics Pads' -- potentially the real name resource, await its final
report). Done this tick: mame-blog kn7000 device blurb brought current (c97311c, blurb-only diff);
kn5000-docs mame-branch-review.md gained the SHARC-core contribution series section (941cdcd, site
rebuilt clean). NEXT unchanged; when the SD workflow lands, act on its answer (that is the SD
end-to-end blocker); when Phase A lands, evaluate whether 0x483E828C obviates the synthetic install.

## TICK 2026-07-18 ~21:5x — SD nav: LCDR soft keys DEAD on the sound-present SD MENU (root-cause workflow running)
Empirical sweep (sdload1-4.lua in the session scratchpad): the machine boots INTO the SD MENU (Felipe's
cfg = sound-present strap); the card MOUNTS (spi reads ~89k by t=30). Pressing the LCDR soft keys
(post-refactor tags :cpanel:CPR_SEG5 0x10/0x20, CPR_SEG7 0x01, CPR_SEG6 0x01, CPR_SEG5 0x01):
LCDR1/3/5 -> fall back to the HOME/play screen (the events act as PART RIGHT1/LEFT/? ON), LCDR2/4 ->
nothing. ZERO SPI delta (no transient screen; rapid 0.6s snapshots). SD CARD LOAD (:cpanel:CPR_SEG1
0x80, ev2040/arg0A6A) from home DOES reopen the SD MENU. KEY FACT: bank A and the old bank map the
LCD soft keys to the SAME events (ev2000/ev2001 args 0x10xx-0x14xx; bankA_dump.txt vs
panel-button-names.md) -- at TICK 07-12 12:10 (sound-absent) ev2001/arg1000 opened LOAD; now the same
event is consumed by the part framework -> the SCREEN INTERCEPTION is what changed, not the mapping.
Lead: AcIntTitleMenuSDProc @0x485736B7. Root-cause workflow wf_194ce2c2-824 running (2 static-RE
diggers: screen-record/soft-key table + ev2001 dispatch-chain gating; 1 empirical sweep: LCDL keys,
DATA dial, PAGE, EXIT, CPSD switches). NOTE for future Lua: anchor install_*_tap results in _G or
they get GC'd and stop counting.

NEXT (in order; pick the first unfinished):
2. SD end-to-end: boot with the default card, navigate SD MENU (SEG0D 0x80) -> LOAD (SEG11 0x10),
   select a file, verify a LOAD completes (bytes flow via 0x9805000C); then try SD-Song playback.
3. "8 Beat 1" Phase A (ungated groundwork): map name-resource probe windows 0x40010000/0x40610000/
   0x40810000/0x54E00000/0x54E10000/0x57000000 to physical ICs from service_manual/; append a
   window->chip table to notes/table-rom-structure.md.
4. tools/dis_sharc.sh: SHARC companion to dis.sh (dump PM + unidasm -arch sharc at basepc, dd-offset fix).
5. Notes reconciliation: retire stale "shared root cause" framing in
   notes/sequenced-playback-and-style-data-rootcause.md (chord-finder pitch RESOLVED by de4fc88; only
   the "8 Beat 1" name resource remains); update panel-completion-plan.md to the current 154/101 state.
6. SIO->mn10300-core refactor (bigger; only start if time allows; design in the roadmap Architecture section).
Rules: commit as you go; publish-binary.sh after driver rebuilds; -skip_gameinfo; visible video only.

## TICK 2026-07-13 ~night(25) — BLOG Part 29: "The recompiler that forgot to saturate" (the SHARC/MAME contribution story)
Durable deliverable (rule h) building on last tick's P5 audit: wrote mame-blog Part 29 -- the story of the
SHARC bugs the KN7000 surfaced in MAME's SHARED core (not KN7000-specific): the MODE1 ALUSAT
recompiler-vs-interpreter divergence (DRC wrapped fixed-ALU add/sub where the interpreter clamped -> the
reverb feedback railed) + the never-implemented native fixed multiplier family (~82M interpreter fall-backs
/22s reverb -> <500k, >99%, bit-identical). Framed as "preservation gives back to the shared toolchain":
these live on the base 2106x SHARC device, so fixing them for the KN7000 fixes them for every SHARC system
in MAME; 3 perf patches verified apply-clean to upstream, ALUSAT series needs the documented small rebase,
submission is Felipe's. Committed (mame-blog 31 kn7000 posts; posts.json-driven, no Jekyll build). No code
change. NOTE: recent ticks are polish/consolidation/docs (the driver is mature; see the night(23)
STATE-OF-THE-EMULATOR summary) -- productive autonomous fodder is genuinely low.

## TICK 2026-07-13 ~night(24) — P5 advanced: 3 SHARC perf fixes verified UPSTREAM-READY; ALUSAT dependency+order pinned
Did the one clean, non-gated, non-blocked task from the state summary: audited the SHARC fixes for upstream
submission. FINDINGS (notes/sharc-upstream-patch-series.md "EXTRACTION" section): the fixes are already
CLEAN, SHARC-only logical COMMITS (not the "39 entangled hunks" the catalogue feared) -- directly
`git format-patch`-able. APPLY-TESTED each against a clean upstream MAME (../mame @ 446413a7510):
- **cd8c720 (native MAC), bb2d516 (native single-fn multiplier), e487bb7 (native DRC ALU average): APPLY
  CLEANLY to upstream as-is -- IMMEDIATELY submittable.** (Three perf patches, ready today.)
- ALUSAT (2d308c7/b942366/b1028bd): sharcdrc.cpp hunks apply but the sharcops.hxx interpreter hunk fails at
  L811 -- it DEPENDS on commit 630c68d's parallel-op op-0x09 AVERAGE line. Submission order for the
  correctness series: extract 630c68d's sharcops.hxx op-0x09 hunk first (630c68d is mixed: 4 sharc + 2
  kn7000 files), THEN 2d308c7 -> b942366 -> b1028bd (or rebase the three onto upstream).
So P5 autonomous prep is now MAXIMAL: 3 patches verified upstream-ready, the ALUSAT dependency/order pinned;
the rebase + per-patch reverb-WAV A/B + actual submission are the human-supervised finish (Felipe's
authorship). No code change (analysis + doc). The commits are all clean SHARC-only except b1028bd (1 clock
line in kn7000.cpp -- drop that hunk) and 630c68d (mixed -- extract its op-0x09 hunk).

## TICK 2026-07-13 ~night(23) — CORRECTION: effects are LARGELY DONE (4 audible); my recent chorus/multi work was re-discovery
Finally read the AUTHORITATIVE effects note **notes/effect-multi-unit-routing.md** (should have been first).
It establishes (2026-07-12): FOUR effects routed + validated audible -- reverb (u0 rec56, production-quality)
+ chorus (u4 rec06) + SOUND-DSP (u9) + MULTI -- coexisting robustly (DAC peak 2443, 0 clipped), with
PER-EFFECT returns fixed (commit fa06930). So the "chorus/multi blocked" I chased across night(20-22) was a
METHOD artifact: (1) I enabled MULTI with the GLOBAL toggle SEG10 0x04 instead of the real per-part enable
**PART SETTING p2 (MULTI ON=SEG09 0x40, DEPTH=SEG0A 0x01, with another effect active to force the 0x8298
refresh)**; (2) I measured unit-1 slot 0xC344, but MULTI's exact UNIT is unresolved (u5/rec10 candidate) so
0 there is not "silent". Corrected notes/per-part-effect-model.md to point at the authoritative note.
GENUINELY-OPEN effect refinements (all DEEP + flagged SUPERVISED in that note, because they touch the
working reverb or need heavy DSP-kernel RE): (a) pin MULTI's unit via the kernel SPORT RX channel->unit
decode (rec04; ch 0x29 -> input slot); (b) EQ (u8 rec34) master-insert with an active-detect guard; (c)
FLAG3 4 records (pitch-shift + specialty reverbs) full frame model.

### ★ HONEST STATE-OF-THE-EMULATOR (for future ticks -- avoid re-spinning)
The KN7000 driver is MATURE. DONE: boots, panel (buttons/sliders/data-dial-faithful), sound plays,
reverb+chorus+sound-dsp+multi routed/audible, DSP LLE+DRC, SD mounts, MIDI, tempo/demo/accompaniment, all
P1-P5. Recent autonomous ticks (data dial x5, chorus/multi x4) hit DIMINISHING RETURNS -- largely
confirming/ re-discovering already-documented facts. The REMAINING high-value work is NOT good autonomous
fodder: it is either SUPERVISED (the effect refinements above touch the Felipe-praised reverb; C-group SHARC
TRM fixes change reverb output -- both need his ear/OK), BLOCKED on external inputs (real PCM = undumped
wave ROMs; floppy FORMAT = RTOS Heisenbug; reverb loudness/EQ makeup = his ear), or already COMPLETE. So the
best next moves are: ship the P5 SHARC patch series upstream (catalogue is complete + submission is his
call), OR wait for Felipe to direct the supervised effect/reverb work, OR small durable polish (docs/blog).
Flagging this so a tick doesn't burn effort re-deriving settled results.

## TICK 2026-07-13 ~night(22) — reached the MULTI EFFECT screen (P2 scenario); chorus/multi audibility is a KNOWN DEFERRED issue
Pursued the night(21) lead (select an effect type to make MULTI audible). REACHED the MULTI EFFECT type
screen (press-and-hold MULTI = SEG10 0x04 -> "MULTI EFFECT PAGE 6/8": center type list Overdrive..Cross
Delay, side Shallow1-8 presets) -- this IS Felipe's P2 "MULTI EFFECT PAGE n/8" screen, now reachable (PAGE
works). Side soft-keys move the highlight (selected Shallow1->Shallow5, confirmed by snapshot). BUT multi
slot 0xC344 stayed 0 through every selection + a MULTI toggle. The DATA DIAL does NOT scroll the type list
either (8th screen with no visible dial effect; the list uses the ˅ soft-key / GROUP cursor).
★ KEY: this is ALREADY DOCUMENTED. notes/effects-sweep-results.md (P1 sweep) established that effect-type
NAVIGATION is COMPLETE (press-and-hold open; GROUP cursor SEG09 0x04/0x08; PAGE rocker SEG0B 0x10/0x20;
side soft-keys; EXIT SEG0B 0x80) and that REVERB types are audible but CHORUS/MULTI/SOUND-DSP give "no
audible effect" -- DEFERRED as the multi-unit send/return audibility model (notes/effect-multi-unit-routing.md).
So I was partly re-discovering known ground; should have read effects-sweep-results.md first. GENUINELY-NEW
detail added to notes/per-part-effect-model.md: the per-part DEPTH channels 0x30-0x3B (+ sends 0x06/0x07)
are written but NOT decoded; and MULTI's global send ch 0x29 IS set + unit 1 IS fed, yet 0xC344 is exactly 0
=> the multi microprogram itself isn't producing (DSP-side model), not a driver send/feed bug.
NET this tick: confirmed the P2 MULTI EFFECT screen is reachable + navigable; chorus/multi audibility remains
the known deferred multi-unit routing task (larger, lower priority; reverb -- the important effect -- works).
No code change (the earlier debug log was net-zero, already reverted+rebuilt+published last tick).

## TICK 2026-07-13 ~night(21) — CHORUS/MULTI root cause FOUND: they need an effect-TYPE selected (algorithm upload), not just a send
Cracked why chorus/multi never activate. Added a temporary [FXSEND] logerror in the tonegen group-0x20 decode,
ran with `-log`, and pressed the effect toggles. FINDINGS: (1) the KN7000 effect model is PER-PART -- the
firmware writes sends (0x03xx family) + depths (0x85xx family) on MANY channels (0x06/0x07/0x09/0x0B/0x29/0x2C
+ the whole 0x30-0x3B depth bank), and the driver only decodes a handful (reverb 0x0B, multi 0x29, sdsp 0x09,
+ returns) -- a partial decode, but it does NOT block chorus/multi. (2) MULTI (SEG10 0x04) DOES set its send
(ch 0x29 -> m_gain_multi=0.63) AND dsp_audio_tick DOES feed unit 1 -- yet output 0xC344 stays 0. ROOT CAUSE:
the multi DSP ALGORITHM isn't loaded. MULTI/CHORUS are TYPE-selectable effects; the send+feed is correct but
the kernel needs an effect TYPE selected (the "MULTI EFFECT PAGE n/8" screen) to upload the unit microprogram.
Without a type, the unit runs null -> 0. REVERB works (algorithm always loaded); SOUND DSP works (SEG0F 0x08
loads a default type); MULTI/CHORUS have no default type. (3) CHORUS toggle SEG11 0x04 writes NO ch 0x19 --
so it's not the chorus send toggle; real chorus enable is elsewhere. NET: this is NOT a driver bug -- the
send/feed path is modelled correctly; the missing piece is USER-side effect-TYPE selection (a panel flow).
So the "chorus/multi blocked" story is now understood: reach the MULTI EFFECT / CHORUS TYPE select screen,
pick a type -> the DSP uploads the algorithm -> the existing send+feed produces output. Debug log was
temporary (added+removed, net-zero code; rebuilt+published clean). Full: notes/per-part-effect-model.md.
The per-part send/depth DECODE GAP (0x30-0x3B etc.) is a separate, larger, lower-priority future task.

## TICK 2026-07-13 ~night(20b) — ★ DATA-DIAL RESOLVED toward FAITHFUL: 0x10 is PROCESSED (not inert), visible-consumer question isolated
Broad RAM diff (0x50060000-70000, u32) while driving 0x10 full-range on the idle home screen: 45 words
changed, FAR beyond the latch -- the dial's events are actively CONSUMED. The event queue buffer fills
(0x5006BC78+, [0x10,remapped,0xFF]; raw pos remapped via table 0x48613188), head/tail advance, a per-turn
dial-position LOG accumulates (0x5006BF44+), and CP-layer state (0x5006BEEC/BEF0) updates. Firmware refs to
those addresses ALL sit in the CP/dial handler range 0x484AD8xx-0x484AE2xx (input layer, NOT display code).
So 0x10 is a FUNCTIONAL relative encoder that processes each position + posts change events = possibility
(a) FAITHFUL, NOT a delivery gap, NOT vestigial. **The "does the data dial work" question is now SETTLED:
it works at the CP/event layer; the wiring is CORRECT + confirmed.** The only remaining unknown is the
VISIBLE UI CONSUMER -- which focused screen's cursor/value subscribes to the dial event (none of the 7
tested does) -- a UI-event-routing detail, not a defect. Corrects the earlier "inert" framing (it does
nothing VISIBLE, but is fully processed). No code change. Full: notes/slider-cp-protocol.md. Data-dial saga
effectively CLOSED (functional + faithful); the visible demo screen is a minor optional follow-up.

## TICK 2026-07-13 ~night(20) — DATA-DIAL: 0x10 affects NEITHER screen NOR sound; KN5000 data-wheel doc cross-referenced
Decisive narrowing of the data-dial question. Sound test (/tmp/dial_tg.lua): sustained note settled, drove
0x10 full-range, counted TG writes 0x98050000-0f settled-vs-driving = 42 vs 42 (no spike, no reverb change).
So **0x10 does NOT modulate the sound -- it is NOT a MIDI-CC controller** (modwheel/pitch/etc.). Combined with
7 screens of no visible navigation, 0x10 generates events (latch follows, queued like the working APC/SEQ pot)
that affect NEITHER screen NOR sound in any tested context.
KEY REFERENCE FOUND: **kn5000-docs/data-wheel-investigation.md** -- the SISTER product's data-wheel forensics.
It shows (KN5000, TLCS-900): the data wheel is a NAVIGATION control that posts UI event 0x1C0001F; its
transport is SEGMENT-0x0B BUTTON PACKETS (bit7=CW/bit6=CCW); and TYPE-2 encoder packets were explicitly the
WRONG system (firmware treated them as MIDI CC). Different CPU so code doesn't port, but the DESIGN reframes
the KN7000 question. Two live possibilities: (a) 0x10 IS the wheel but its nav-event consumer isn't acted on
by any reachable screen (faithful); (b) the real nav wheel is BUTTON-STYLE CW/CCW and 0x10 is vestigial.
DECISIVE NEXT (KN5000 doc's own method, ported): MAME debugger -- drive 0x10, watch the input-queue consumer /
UI-nav-event write; nav event fires => (a); nothing => hunt a button-style wheel. Wiring stays (schematic-
grounded ROTA/ROTB->AD0=0x10, harmless, no regression). No code change. Full: notes/slider-cp-protocol.md.

## TICK 2026-07-13 ~night(19) — DATA-DIAL thoroughly explored (7 screens + panel-memory angle): visible consumer NOT found
Tested the last two untested dial-consumer contexts: SEQUENCER PLAY (SEG0D 0x08) and EASY RECORD
(SEG0C 0x08). The dial is INERT in both (latch 0x5006BEA0 follows = events fire, 0 px visible). That is
SEVEN screens now (home, DISK MENU, R1/R2 OCTAVE, DEMO menu, sound-select, SEQ PLAY, EASY RECORD) with no
visible dial navigation on any. Also found in the LAYOUT: the big right-hand wheel is `panel_memory_dial`
(gen_lay 725) but it is DECORATIVE (no inputtag), and PANEL MEMORY SET is a separate button (SEG13 0x40) --
so the wheel is (per the author) associated with PANEL-MEMORY/registration recall, and the IPT_DIAL "DATA
DIAL" port I wired to 0x10 is not bound to any clickable layout element (it responds to MAME's keyboard/mouse
dial mapping only). CONCLUSION (honest): 0x10 is a relative encoder that GENERATES firmware events correctly
(verified: latch follows; [0x10,val,0xFF] -> the same live input queue 0x5006bcf8 the working APC/SEQ pot
uses), but its VISIBLE effect could not be triggered on any reachable screen. Two possibilities remain and
need REAL-HARDWARE confirmation to decide: (a) FAITHFUL -- the KN7000 UI is soft-key/PAGE driven and the
wheel's role is a narrow panel-memory/value-entry context I never cornered; or (b) a delivery GAP -- the
events reach the queue but a consumer step that would move a cursor is missing. The wiring stays (correct +
additive, no regression); this is now a documented open question for Felipe, not a chase to continue
headlessly. No code change. Full: notes/slider-cp-protocol.md.

## TICK 2026-07-13 ~night(18) — P2 PAGE re-validated on the sound-select; data-dial conclusion firmed; chorus/multi still blocked
All P1-P5 already addressed, so this tick firmed up loose ends via reliable soft-key navigation (using the
LAYOUT bindings, gen_lay.py -- NOT the stale panel-button-names.md, which mislabels e.g. PIANO as SEG0C 0x01
when it is actually SEG10 0x10). Concrete outcomes:
1. **P2 PAGE re-validated on a FRESH paged screen** (the PIANO sound-select, PAGE 1/3): PAGE UP (SEG0B 0x10)
   1/3->2/3->3/3, PAGE DOWN (SEG0B 0x20) back to 2/3 -- read straight off the yellow n/3 badge. P2 (which
   was first confirmed on SD LOAD) generalises. Solid.
2. **DATA DIAL conclusion FIRMED (5 screens now tested):** home, DISK MENU, R1/R2 OCTAVE, DEMO menu, and now
   the SOUND-SELECT -- NONE respond to the dial (latch 0x5006BEA0 follows every time = events generated, but
   0 px visible change). The KN7000 UI is entirely SOFT-KEY + PAGE driven (◄► arrows -> side keys; PAGE
   badge -> PAGE up/down). So the dial is FAITHFULLY inert on these screens; its events are consumed only in
   a specific value-entry/SEQUENCER context not yet reached. The earlier "sound-select is the dial's
   consumer" hypothesis is DISPROVEN (sound-select = soft-keys). Dial wiring stays correct (generates events
   to the same live queue as the working APC/SEQ pot); a visible demo needs the sequencer.
3. **CHORUS/MULTI still blocked:** tried global toggles (SEG11/SEG10 0x04), the OVERTURE demo, a factory
   E.P. sound preset (Vintage E.P.1, confirmed selected), and the DIGITAL EFFECT button (SEG10 0x08) -- NONE
   light the chorus (0xC34A) or multi (0xC344) output slots. They are per-part effects gated on a per-part
   depth (0x8198/0x8298) that no default/preset/toggle sets; confirming them needs an explicit multi-step
   effect-depth edit (a settings-screen flow not yet cracked). Reverb + SOUND DSP remain the 2/4 confirmed.
NAVIGATION AID for future ticks: **gen_lay.py is the authoritative button->binding source** (layout is
correct; panel-button-names.md has stale/wrong labels). Confirmed bindings this session: DEMO=SEG06 0x40,
demo OVERTURE=SEG00 0x02, PIANO sound group=SEG10 0x10, sound-select right-col row2=SEG11 0x20, PAGE
up/down=SEG0B 0x10/0x20, REVERB=SEG0F 0x04, SOUND DSP=SEG0F 0x08. No code change (investigation tick).

## TICK 2026-07-13 ~night(17b) — P5 catalogue COMPLETED (added the single-fn multiplier, the real hot-path fix)
Audited the SHARC upstream catalogue (notes/sharc-upstream-patch-series.md) against the ACTUAL fork-vs-
upstream diff (mame/ vs kn7000_mame_build/, sharc/: sharcdrc.cpp 384 lines/39 hunks, sharcops.hxx 155,
sharc.cpp 109, sharc.h 105). Found a GAP: the catalogue's perf section D only listed the MULTIFUNCTION MAC
block (which the KN7000 kernel never uses -- 0 multiop fallbacks), but the ACTUAL hot-path fix -- the native
SINGLE-FUNCTION fixed multiplier (SS forms 0x70-7f/0xb0-bf/0xf0-ff, commit bb2d516, 66M fallbacks gone) --
was undocumented. Added it as D.1 (the highest-impact perf patch) and rewrote the upstreaming plan around
TWO headline series: B.1 ALUSAT (correctness) + D.1 single-fn multiplier (perf), both on the base
adsp21062_device (benefit every 2106x SHARC in MAME), logically independent, mostly-disjoint code. Catalogue
is now the COMPLETE map. Actual git-patch extraction NOT done (submission is Felipe's under his authorship;
39 mixed hunks need hunk-by-hunk split + per-patch A/B -- a submission-time task, not a prep gap).
So P5 prep = as complete as it can be pre-submission. **All P1-P5 now addressed** (P1 sweep clean, P2
PAGE/CONTRAST done, P3 DRC native, P4 fully resolved night16/17, P5 catalogue complete). No code change.

## TICK 2026-07-13 ~night(17) — P4 loud-input rail RE-CHECK = CLEAN (P4 now fully addressed); demo playback robust
Re-checked P4's "loud-input rail" under a genuinely loud full mix (not just a single note): played the
firmware's OVERTURE DEMO (DEMO=SEG06 0x40 -> menu -> OVERTURE=SEG00 0x02) and characterized the reverb
output 0xC342 across the whole song. RESULT: only 2/871 frames touch full scale (0.23% = rare brief
transients = the DSP's faithful ALUSAT saturation), and the **DAC output NEVER clips** (clean-cfg speaker
WAV peaks at 41% FS, 0 samples >= 32000). So NO loud-input rail problem -- the reverb handles a loud
full-orchestral song cleanly. **P4 is now fully addressed** (0x8238 decoded earlier + loudness resolved as
faithful night(16) + loud-input rail clean this tick).
BONUS: even the OVERTURE demo drives ONLY the reverb (chorus/multi/sdsp slots stay 0 the whole song) ->
confirms those three are per-part effects absent from the default factory mix; reverb is the always-on
primary effect. Demo playback works (reverb builds 325K->8.4M with the arrangement) = robustness confirm of
the tempo-timer + accompaniment + reverb chain under a real multi-voice song. No code change (measurement
tick). Reusable: DEMO song = SEG06 0x40 then OVERTURE = SEG00 0x02 (left soft-key row 1). Full: reverb-toggle-findings.

## TICK 2026-07-13 ~night(16) — SOUND DSP effect confirmed audible+toggleable; P4 reverb-loudness RESOLVED (faithful)
Two clean outcomes, no code change (measurement + reasoning tick):
1. **P4 loudness question ANSWERED:** reverb ON being ~2x quieter than OFF is FAITHFUL to the decoded
   registers -- OFF = full dry direct; ON = the DSP return only (crossfade mutes direct), which is the DSP's
   dry+wet scaled by send 0.80 * TOTAL-DEPTH 0.63 ~= 0.5. The "keep dry full" fix would need a wet-only
   return + separate dry path, but the captured crossfade MUTES the direct when reverb is on, so the fix
   CONTRADICTS the RE. Verdict: do NOT change it (rule g); only Felipe's ear on real HW could show the
   capture's interpretation is subtly wrong. At MAX depth ON ~= OFF. (Full reasoning: reverb-toggle-findings.)
2. **SOUND DSP = 2nd effect unit confirmed audible + toggleable.** Default: only the reverb unit is active at
   boot (chorus/multi/sound-dsp slots = 0). SEG0F 0x08 (which the layout's gen_lay PE_BITS ALREADY binds as
   SOUND DSP -- so the layout is right; panel-button-names.md's "RIGHT2 ON" is the stale outlier) enables it:
   slot 0xC356 0->1.8M, DAC chord RMS 1953->2414 (+24%), toggles back off on 2nd press. The SEG0F row is the
   DIGITAL-EFFECT row (0x04=REVERB, 0x08=SOUND DSP), it does NOT touch the part indicators.
REUSABLE METHOD: keybed chord (KEYS1 0x0100/0x1000/0x8000) + sample DSP output slots
mach.devices[":dsp"].spaces["data"]:read_u32(0xC342 rev / 0xC344 multi / 0xC34A chorus / 0xC356 sdsp).
NEXT (follow-up): find the CHORUS + MULTI enable buttons (not in SEG0F) and confirm those two units audible;
reconcile panel-button-names.md's SEG0F row with the (correct) layout bindings.

## TICK 2026-07-13 ~night(15) — ★★★ REVERB CONFIRMED AUDIBLE + ON/OFF TOGGLE WORKS (Felipe's explicit ask, RESOLVED)
Measured the crown-jewel reverb end-to-end now that its last blocker (SHARC divergence) is fixed. Objective
probe (no ear needed): play a keybed C chord, sample the DSP reverb output 0xC342 + send input 0xC362 as a
peak envelope, AND capture a CLEAN speaker WAV (custom cfg, NO MAME host audio_effects -- the shipped cfg's
host "Reverb" would confound).
RESULT: **REVERB WORKS.** Reverb ON (default, flag 0x500C0758 bit9=true): after note-off the reverb OUTPUT
keeps ringing ~1 s AFTER the send input has gone to 0 (14732->9353->3831->974->385) = a genuine exponential
TAIL, ~24% FS, no rail/clip. **TOGGLE WORKS:** SEG0F 0x04 flips the reverb flag true->false (confirms it IS
the REVERB button, NOT "RIGHT1 ON" as the button-names map claims); with reverb OFF the send=0 (muted) and
there's no tail (speaker WAV decays fast, dry). So ON=wet tail, OFF=dry. **This RESOLVES Felipe's complaint
"I cannot toggle reverb on/off in the emulator as I can on the real KN7000."**
Demo WAV for his ear: KN7000/reverb_toggle_demo.wav (6 s A/B). No code change this tick -- it was a
confirmation that the prior fixes (divergence + send-bus model + bridge) combine to a working audible reverb.
P4 LOUDNESS (was ear-blocked -> now quantified): reverb ON is ~2.4x quieter than OFF during the note
(RMS 1780 vs 4205) because ON routes the DAC to the DSP return only (send0.80*ret1.0*depth0.63~=0.5) vs the
full dry when OFF. Candidate makeup-gain fix documented but NOT applied unsupervised (rule g -- alters the
praised reverb); needs Felipe's ear to confirm the balance. Full detail: notes/reverb-toggle-findings.md.
KEYBED note-trigger recipe (reusable): set KEYS1 fields 0x0100/0x1000/0x8000 = C4/E4/G4 chord; DSP reverb
output read = mach.devices[":dsp"].spaces["data"]:read_u32(0xC342), sign-extend 24-bit.

## TICK 2026-07-13 ~night(14) — ★ DATA dial WIRED & shipped (IPT_DIAL -> CP wire 0x10); event-gen disasm-confirmed
Made the big DATA value-wheel FUNCTIONAL (commit 14ed7cb, built+published). The driver already had a dead
`IPT_DIAL` "DATA DIAL" port + a `seg_to_addr[0x1A]=0x10` "VALUATOR wire" placeholder that nothing read;
panel_scan now forwards the IPT_DIAL accumulator as a CP TYPE-2 frame [0x10, POSITION] on change (same
handshake-poison guard as the APC/SEQ pot). MAME's IPT_DIAL is a relative accumulator = exactly what wire
0x10's handler wants (it diffs successive positions).
IDENTIFICATION CONCLUSIVE (disasm, not a guess): handler 0x484AD6B0 does a RELATIVE diff (returns 0xFFFF
unchanged / value on change) -> a relative ENCODER, rules out absolute pitch-bend; and on a change the
caller 0x484AD2CD emits a [id, value, 0xFF] event via enqueue 0x484AD519 -> a genuine panel event. Plus
schematic ROTA/ROTB encoder + elimination (0x17=tempo confirmed, 0xD0-D3=pots).
VERIFIED (driver path, no injection): setting the IPT_DIAL field from Lua makes the firmware's 0x10 latch
0x5006BEA0 track it exactly (set 3,6,..30 -> latch 00,03,..1E); buttons still deliver (DISK MENU still opens).
HONEST SCOPE: on-screen nav needs a FOCUSED value-edit field; the 3 reachable screens (home=no focus,
DISK MENU + R1/R2 OCTAVE = soft-key-edited) show no visible change when the dial is turned = FAITHFUL. A
headless "dial scrolls a list" screenshot wasn't captured (the seg->function map is unreliable -- SEG13 0x02
opened OCTAVE, which the map calls TRANSPOSE -- so reaching sound/style-select is unproductive headlessly).
★ QUEUE-LIVENESS PROOF (removes most of the doubt): the 0x484AD2CD->0x484AD519 change path pushes the
[0x10,value,0xFF] event into queue 0x5006bcf8 -- the SAME queue the VERIFIED-WORKING APC/SEQ pot (0xD2) uses
via the SAME path. So the delivery is proven live; only the per-id consumer ACTION differs. The dial reaches
a real working consumer. Visible confirmation still wants an interactive turn on a sound/style-select screen.
KEY TIMING (all future visual probes): the musical-notes image at t=8-11 is the BOOT SPLASH; the PMEM home
screen appears at t~=13. Full detail: notes/slider-cp-protocol.md. NEXT (optional): interactive visible
confirm on a value-edit screen, or trace the 0x484AD519 consumer for the EV_DIALUP/DOWN focus routing.

## TICK 2026-07-13 ~night(13) — TEMPO/PROGRAM knob & DATA dial IDENTIFIED (0x17 relative encoder / 0x10 nav dial)
Pursued making the data dial / tempo knob functional (the last two unmodelled rotary controls). Identified
both by live CP-frame injection on the HOME screen + reading the on-screen tempo (crotchet=NNN):
- **0x17 = the TEMPO/PROGRAM knob** (center). Injecting it changes the tempo; 0x10 does not.
- **0x17 is a RELATIVE encoder**, not an absolute pot: distinct absolute injects gave non-monotonic tempos
  (0x40→184, 0x80→56, 0x20→88, 0xF0→72, 0x10→88). The tempo moves by the DIFF of consecutive positions.
- **0x10 = the big DATA dial** (navigates/edits the focused field; no home-screen tempo effect).
- TIMING FINDING (useful for all future visual probes): the musical-notes image at t=8-11 is the BOOT
  SPLASH; the PMEM home screen appears at **t≈13**. Probe after t=13, not t=8.
DELIBERATELY NOT SHIPPED: wiring either as an absolute PORT_ADJUSTER would be a wrong-mapping guess (erratic
tempo) -> violates faithful-first. Correct future wiring (documented in notes/slider-cp-protocol.md): a
draggable knob whose adjuster DELTA accumulates into a wrapping uint8 position emitted as [0x17, pos&0xFF];
the firmware diffs -> smooth relative tempo control. Needs a draggable-knob element + delta-accumulator in
panel_scan; a focused next task, not rushed at session tail. Full data + method in slider-cp-protocol.md.

## TICK 2026-07-13 ~night(12k) — apply_svg.py ID-matching branch DONE + verified (layout collaboration loop complete)
Implemented + tested the RELIABLE ID-matching branch of tools/apply_svg.py. When the adjusted SVG keeps our
stable ids (group.index.ref, stamped by lay_to_svg; Inkscape preserves them), each element maps EXACTLY to
its .lay placement and its <bounds> is rewritten from the SVG position; fuzzy only if no ids. VERIFIED 3
ways: (1) no-op self-test -- apply the unedited ID-tagged export -> 0 changes / 478 ids seen (SVG-pos <->
.lay-bounds round-trip is exact); (2) synthetic +40,+25 move of the HELP text -> detected as exactly 1
change; (3) --apply patches HELP bounds 149,838 -> 189,863 then restored via gen_lay.py. So the layout
collaboration loop is COMPLETE: THE WORKFLOW = (a) `python3 tools/lay_to_svg.py` exports the ID-tagged B&W
SVG; (b) Felipe edits it in Inkscape; (c) `python3 tools/apply_svg.py that.svg --apply` merges his positions
back onto the .lay; (d) rebuild + publish. Felipe's CURRENT (id-less) adjusted SVG still reports FUZZY and
won't auto-apply -- his APC/SEQUENCER text fix is in; the rest await an ID-tagged round OR manual per-item.

## TICK 2026-07-13 ~night(12j) — built apply_svg.py; PROVED the current adjusted SVG can't be safely auto-applied
Built tools/apply_svg.py (pipeline gen_lay.py -> base .lay -> apply_svg.py adjusted.svg -> patched .lay;
matches each placement to the SVG, rewrites <bounds>, keeps bindings; DRY BY DEFAULT, --apply to patch).
Dry-ran it on Felipe's kn7000_layout_adjusted.svg: it is NOT safely auto-applicable. His Inkscape edit
FLATTENED the groups and dropped our stable IDs, so matching falls back to fuzzy string/nearest-centre ->
(a) duplicate short labels (+, -, VOLUME, 1) mismatch to far instances (d up to 542px), (b) deleted elements
match wildly, (c) animated slider knobs match the wrong state, (d) 250+ shapes fail to match at all within
radius. Even radius-guarded, applying it would misalign labels from their (unmoved) shapes -> would violate
rule g. So I did NOT apply it. RELIABLE PATH = the ID-tagged export (lay_to_svg stamps group.index.ref,
Inkscape preserves it): Felipe's NEXT edit on the re-exported ID SVG matches EXACTLY. NEXT: implement+test
the ID-matching branch in apply_svg.py against a real ID-tagged round (the no-op self-test: run it on my own
ID SVG -> 0 changes). For the current round, the clear correctness fix (APC/SEQUENCER) is already applied;
specific individual changes can be applied manually on request.

## TICK 2026-07-13 ~night(12i) — Felipe's adjusted layout SVG (fine_tuning loop) + docs + workflow fix
Felipe returned side-quests/kn7000_layout_adjusted.svg (his Inkscape edit of the B&W layout SVG). Diffed it
vs my export: his changes are FINE COSMETIC refinements (~30 small label/position nudges; renders near-
identical), not a re-layout. Applied the ONE clear CORRECTNESS fix: APC/SEQ -> APC/SEQUENCER (real-panel
spelling; display name decoupled from the VOL_APCSEQ key; wider bound; moved apcseq_vol_led clear). Rebuilt
+ published (md5-matched). The remaining ~30 nudges are cosmetic + intricate to apply to the PROCEDURAL
gen_lay.py (the LED overlap illustrated the fiddliness) and my SVG uses fixed-font text vs MAME's scale-to-
bounds (positions map, font sizes differ). WORKFLOW FIX: added STABLE per-element IDs (group.index.ref) to
tools/lay_to_svg.py + re-exported -- Inkscape preserves IDs, so the NEXT round matches back to the exact
.lay element trivially (a merge tool can then apply positions reliably). NEXT: build tools/apply_svg.py
(gen_lay.py -> base.lay -> apply Felipe's SVG positions by ID -> final.lay) to apply his positional edits
faithfully and survive regeneration; then push the current round's meaningful moves (SEQUENCER RESET/COUNT
INTRO labels, slider-label y, SOUND/PART/GLOBAL group headers).
Also: kn5000-docs kn7000-control-panel.md -- corrected 0x484AD680 (it's the latched/continuous-control
dispatch, NOT switches) + added the Continuous-controls/volume-fader section (type-2 frames, 0xD0-D3,
APC/SEQ=0xD2 driven in MAME). Jekyll rebuilt.

## TICK 2026-07-13 ~night(12h) — BLOG Part 26 (the slider journey) landed
Wrote mame-blog Part 26 "The slider that jammed the panel" -- the full slider arc as an honest RE story:
non-draggable -> wrong-tree red herring -> all-views fix -> the raw-ADC wrong turn -> CP-protocol discovery
(TYPE 2 frames) -> live ring-injection validation -> 0xD2=APC/SEQ via MUTE-9 write-correlation -> the
queue-poison bug (a premature boot frame wedged ALL panel delivery, buttons included) -> working. Committed
+ posts.json entry (28 entries). No Jekyll build needed (mame-blog is app.js/posts.json driven, not the
kn5000-docs Jekyll site). OPEN slider refinements still: apcseq_vol_led soft-takeover; bind MAIN/MIC/LINE-IN
(0xD0/D1/D3, same MUTE-correlation method).

## TICK 2026-07-12 ~night(12g) — ★★ DONE: APC/SEQ VOLUME slider is now FUNCTIONAL (drives the firmware)
Completed the sliders functional binding (Felipe's sliders.txt core ask). Identified **0xD2 = APC/SEQ** by
RAM write-correlation (its write-set overlaps MUTE UP 9's -- which edits the same setting -- by 44 addresses
vs exactly 20 for 0xD0/D1/D3; matches service-manual VR1102=AD2). Driver: panel_scan emits the CP TYPE 2
frame [0xD2, DATA] via panel_queue on VOL_APCSEQ change, DATA = 255-adjuster*2.55 (handler 0x484AD772 inverts
+ remaps through monotonic ramp 0x48613508 -> louder when dragged up). ★ VERIFIED: the 0xD2 latch 0x5006BEA6
tracks the slider (vol 100->0xFF, 0->0x00, 50->0x80); buttons still reach the ring (no panel regression).
Rebuilt + published (md5-matched).
★ GOTCHA found+documented: do NOT emit a panel frame before the firmware services the panel handshake -- an
undelivered frame sits in the response queue and blocks ALL later ATN kicks (buttons included), because
panel_queue only kicks the ATN when the queue was_idle. Fix = a 'synced' flag records the pot on the first
scan without emitting; emit only on a real move (hardware soft-takeover). Full: notes/slider-cp-protocol.md.
OPEN refinements: (a) apcseq_vol_led soft-takeover; (b) bind MAIN/MIC/LINE-IN (0xD0/D1/D3, same method).

## TICK 2026-07-12 ~night(12f) — ★ sliders read path SOLVED (CP protocol, not ADC); injection confirmed live
Pursued the sliders FUNCTIONAL binding (make the APC/Seq slider change the firmware value). KEY FINDING
(supersedes the raw-ADC hypothesis): the 4 volume pots + data wheel/pitch-mod/pedal are digitised by a panel
sub-CPU and delivered as **TYPE 2 CP-protocol frames [ADDR,DATA]** (dispatch 0x484AD680, table 0x48613108) --
which the driver ALREADY models. Enumerated the 6 controls; the 4 volume pots are wire ADDRs **0xD0-0xD3**
(latch RAM 0x5006BEA1/2/3/6, per-control invert/÷2 + remap taper). ★ CONFIRMED LIVE, no rebuild
(/tmp probe): injecting [0xD0,0xAA] into the CP RX ring (0x5006BDB4, head@0x5006BDB2) latched 0x5006BEA3=0xAA
-- the handler ran, sliders are injectable end-to-end. So functional sliders = emit the right 0xDx frame on
VOL_APCSEQ change (panel_queue or the RX-ring write). OPEN: (a) ID which 0xDx = APC/SEQ -- attempt 1 via
display was CONFOUNDED by the demo screensaver (auto-starts on inactivity); use RAM correlation vs MUTE UP 9
(demo-immune) or suppress the demo; (b) then wire the driver. Full: notes/slider-cp-protocol.md.

## TICK 2026-07-12 ~night(12e) — ★ FIXED: volume sliders now draggable on all views (Felipe bug)
Felipe: sliders not draggable by clicking the layout (only the MAME analog menu worked); LinnDrum's are.
ROOT CAUSE: the slider <script> (gen_lay.py) installed the pointer-drag callbacks on ONLY the "Compact"
view. The 4 faders live in the left_block group, which also appears in "Full Unit" and "Left Block" views;
MAME remembers the selected view per system in .cfg, so on any non-Compact view (e.g. Full Unit) the faders
had no set_pointer_updated_callback -> not draggable. FIX (committed, rebuilt, published): loop all views,
wire every one containing the sliders (all-views pattern, same as MAME esq1/linndrum/mpc60). Now Compact,
Full Unit, Left Block are all wired.
RED HERRING corrected: an early grep of kn7000_mame/src/emu (the fork's STALE source tree) suggested the
engine lacked set_resolve_tags_callback / the pointer API -> WRONG. The binary builds from
kn7000_mame_build/src, whose src/emu is an UPSTREAM RSYNC that HAS the full pointer API. Always grep the
BUILD tree (kn7000_mame_build/src), not kn7000_mame/src, for engine questions.
Verification limit: layout scripts run in a sandbox (no _G) in a SEPARATE Lua state from autoboot, and the
recomputed callback fires at init (input ports unreadable) -> couldn't headlessly simulate a real mouse
drag. Drag math verified structurally (library byte-identical to esq1's; clickarea bounds span the knob
travel exactly). Felipe to confirm the drag works. Full: side-quests/findings/sliders_findings.md.
GOTCHA for future ticks: `_G` is NIL in layout <script> sandboxes -- never reference it there.

## TICK 2026-07-12 ~night(12d) — sliders ADC investigation + blog Part 25 + B3+B4 correction
- CORRECTION (Felipe): B3+B4 is a REAL entry (floppy test directly), NOT a misremembering; C#3+D#3+C#4
  loads the full menu. Fixed the record in findings, fdc-architecture addendum 28, memory, status(12).
- SLIDERS side-quest investigated: sliders already draggable + APC/SEQ LED added (done); the FUNCTIONAL
  binding needs the slider ADC read path. Found (service manual): VR1102=APC/SEQ VOLUME on the main-CPU
  ADC (AD2); VR1103=MAIN/VR1104=MIC/VR1105=LINE-IN on AD0/1/3. mn10300 core has NO ADC model, but the
  MN103002A peripherals are driver-mapped (0x34000000 via io_r), so the ADC is interceptable IF its
  address is found -- and it ISN'T yet (io-map.md shows no ADC block; 0x340 reads are all INTC/SIO/timer).
  NEXT: live-probe the APC/Seq-volume screen to find the register that tracks the slider, then return
  VOL_APCSEQ there. Full: side-quests/findings/sliders_findings.md.
- BLOG Part 25 "The colour the firmware cannot know" (mame-blog): the panel LEDs -- firmware knows WHICH
  lamp (PanelSwitchClassTable, validated) but not its COLOUR (physical); Felipe's green/red spec + the
  lay_to_svg color-verify + B&W collaboration tool. Committed + posts.json entry added.

## TICK 2026-07-12 ~night(12c) — SIDE-QUEST DONE: LEDs checklist (colours + adds/removes)
Implemented Felipe's LEDs_in_the_layout.txt in tools/gen_lay.py; regenerated kn7000.lay, REBUILT the
driver (SUBTARGET=kn7000, layout recompiled), PUBLISHED, md5-matched. Verified via tools/lay_to_svg.py
--leds (renders LEDs in lit colours) — chromium-checked against the list.
- Recolour: every panel LED RED except the 31 GREEN ones Felipe listed (APC MODE / Sound-Arranger SET+
  OFF-ON, RHYTHM CUSTOM+MEMORY, MUSIC STYLIST, AUTO SETTING, beats 2-4, SOUND-GROUP MEMORY, all 4
  SEQUENCER, SD, TEMPO, BANK VIEW, PANEL MEMORY 1-8, CUSTOM PANEL/CUSTOMIZE/FAVORITES, + the 2 new).
  Green placements = exactly 31 (one-for-one with the list). Flipped ~40 LEDs green->red.
- Added: APC/SEQ VOLUME LED (green, id apcseq_vol_led -- driver can drive it once the value path is
  wired, see sliders.txt), SD CARD PLAY/PAUSE LED (green), FILL IN 1&2 LEDs (were missing, red), 3
  keyboard split-point indicators (red + down-arrow `split_arrow` element; positions placeholder, Felipe
  refines via the SVG loop). Removed the SPLIT POINT button LED.
- Rebuilt binary boots to home screen, panel intact (no regression). Refreshed the fine_tuning SVG
  (477 placements). Full: side-quests/findings/leds_in_the_layout_findings.md.
Remaining layout side-quest: sliders.txt -- sliders ALREADY draggable (slider_lib.lua + add_vertical_
slider for all 4 faders in Compact); the APC/SEQ VOLUME LED is now added; still open = the FUNCTIONAL
binding (APC/Seq slider actually changing the firmware APC volume + LED reflecting slider==value) which
needs RE of the APC-volume control target.

## TICK 2026-07-12 ~night(12b) — SIDE-QUEST DONE: B&W SVG export of the panel layout (fine_tuning)
Felipe's "fine_tuning_the_layout" side-quest: produce a black-and-white SVG of the current layout so he
can edit positions/dimensions/labels and I apply them back. DELIVERED:
- New tool `tools/lay_to_svg.py`: flattens one view of kn7000.lay (default "Compact", groups compose at
  1:1 translate) into a single standalone B&W SVG — every button/slider/LED/dial as white-fill/black-
  outline shape at exact panel position, labels as black text (468 placements). Committed.
- Output `../KN7000/side-quests/kn7000_layout.svg` (+ kn7000_layout_preview.png). Verified FAITHFUL via
  chromium headless (matches the panel exactly). ImageMagick can't render `<g transform>` — use chromium.
- Bugs fixed en route: self-closing-tag stroke insertion; nested-<svg> → `<g transform>` (renderability);
  double-escaped `&amp;` labels.
- Collaboration loop + the SVG(absolute)→gen_lay.py(group-local) coord mapping documented in
  side-quests/findings/layout_svg_export_findings.md. NEXT (when Felipe returns his edited SVG): diff and
  apply position/dimension/label changes to tools/gen_lay.py (subtract group offsets: left_block +(0,997),
  right_block +(1000,997), screen_block +(0,0), sd_block +(750,915)), regenerate, rebuild, publish.
Other open layout side-quests (not yet started): LEDs_in_the_layout.txt (add/remove/recolor a checklist of
LEDs), sliders.txt (APC/SEQ Volume LED + draggable sliders + bind APC slider to input).

## TICK 2026-07-12 ~night(12) — ★ SELF-TEST: TWO real entries (B3+B4 = floppy test only; C#3+D#3+C#4 = full menu)
CORRECTION (per Felipe, both verified on REAL hardware): B3+B4 (2 keys) loads the Floppy SAVE/LOAD test
DIRECTLY (that test only -- the MORE DIRECT FDC path); C#3+D#3+C#4 (3 keys) loads the full Service
Diagnostic MENU (service manual §8: "hold C#3,D#3,C#4, turn on power; release after the service screen").
My earlier "B3+B4 was a misremembering" was WRONG -- it is a real alternative shortcut. Retracted. §8.4 SAVE/LOAD: insert formatted floppy, press START (MUTE UP 10),
repeats save/load/compare, counts OK/NG on LCD, STOP (MUTE UP 8) interrupts.
- Retested FIFO injection (0x98050004) with the CORRECT three keys (idx C#3=0x0D,D#3=0x0F,C#4=0x19) BOTH
  flooding (->black LCD, boot starved) and gentle-periodic (->NORMAL home screen). => the keybed FIFO is
  DEFINITIVELY NOT the power-on combo source (now proven with authoritative keys, not just tentatively).
  The combo is a RAW keybed-matrix scan and/or panel/CP SIO read at power-on — unmodeled by the driver.
- Mapped the SCREEN MANAGER for force-navigation: register fn 0x4842A717 copies each screen struct
  {config@0,handler@4,count@8,dataTable@0xc} into SCREEN TABLE **0x5011FAAC + tableIndexID*16**. Service
  screens: idx 0x104->cfg 0x00040004/0x4842A802; 0x105->0x00040009/0x4842CB02; 0x106->0x0004000A/0x4842CB4A.
  Lookup-by-ID = 0x484294A6; sub-entry (0x18-byte items) lookup = 0x484295A4; context var 0x5000757C.
  (0x4842A802 is a GENERIC screen handler, not service-specific.)
NEXT (two paths, in side-quests/findings/floppy_self_test_findings.md + fdc-architecture.md add.28):
  A) FAITHFUL — find+model the raw boot combo read (candidates: 0x9CC00000 GPIO / panel SIO 0x34000809->
     ring 0x5006BDB0); B) HACK (clearly-labelled) — pin the screen-manager "goto screen ID"/current-screen
     var, poke to idx 0x104, map START (MUTE UP 10)/STOP (MUTE UP 8) panel buttons, run w/ floptest_fat12.img.

## TICK 2026-07-12 ~night(11) — SELF-TEST (Felipe "resume"): dispatcher found; combo NOT via FIFO; FDC OK at boot
Resumed the FD SAVE/LOAD self-test. Progress:
- Ruled out the keybed FIFO (0x98050004) as the B3+B4 combo source: FIFO read-tap injection (cycling ->
  runtime TRANSPOSE; single hold -> nothing) never enters the test, and a FULL BOOT TRACE (from reset)
  shows 0x98050004 is read ONLY by the runtime drain 0x484480A2 (25 reads) -- no boot combo check there.
  Also: Lua set_value can't fire the music-key PORT_CHANGED. So the combo is read via a RAW/panel source.
- Found the service-test menu builder **0x4849F860** (boot-init 0x4842A59E; registers the FD SAVE/LOAD +
  EV_TEST menu from tables 0x4874ACD4/ADC4/AF1C/AF90/AFF8 + handlers 0x4842A802/CB02 via register fn
  0x4842A717). Menu is always REGISTERED; only ENTRY is combo-gated.
- ★ The boot trace independently CONFIRMS the FDC model: the boot FDC init drives MSR 0x98020008 (read 51x)
  + FIFO 0x9802000A -- the FDC @0x98020000 model is correctly exercised at boot. (Reinforces that the
  format's failure is the RTOS-dispatch Heisenbug, not the FDC.)
NEXT: the combo source is the panel/CP protocol (sub-CPU SIO 0x34000800 -> ring 0x5006bdb0) or an early raw
keybed scan -- analyse how the power-on key/panel state is formed + where B3+B4 is tested, then model/inject
it. Since the self-test's STOP/START are PANEL positions (MUTE UP 8/10), also try panel-button (SEG)
injection at boot (B3+B4 may be panel matrix positions, not music keys). Then run w/ floptest_fat12.img,
watch OK/NG -> validates the FDC end-to-end via the DIRECT FdTest path. Full: side-quests/findings/ +
fdc-architecture.md addenda 25-27.

## TICK 2026-07-12 ~night(10) — SIDE-QUEST: floppy SAVE/LOAD self-test (Felipe) -- direct-FDC path, entry narrowed
Felipe's side-quest (side-quests/floppy_disk_save_and_load_self_test.txt): boot holding music keys B3+B4 ->
a floppy SAVE/LOAD FACTORY test that reads/writes real data and counts OK/NG. ★ HIGH VALUE: this test uses
the SERVICE-TEST reflection path (FdTestRunFunc 0x484A14B6 / FdIoFunc 0x484A1766) that drives the FDC
DIRECTLY -- it should BYPASS the RTOS class-5 dispatch HEISENBUG that blocks the normal FORMAT, so it is the
way to VALIDATE the FDC @0x98020000 end-to-end (and confirm the format's failure is purely the emulation
timing bug, not the FDC). Findings (full: side-quests/findings/floppy_self_test_findings.md; fdc-
architecture.md addendum 25):
- Test located (strings VA ~0x48607000-0x4860B000: "FD SAVE/LOAD TEST", "FLOPPY DISK SAVE&LOAD", "DISK
  EV_TEST", OK/NG). B3 = key idx 0x17 (KEYS1 0x0080, GM59); B4 = idx 0x23 (KEYS2 0x0008, GM71).
- ENTRY BLOCKER: Lua field:set_value() does NOT fire the music-key PORT_CHANGED->kbd_push (verified: 0 FIFO
  events even on the play screen). A read-tap on the FIFO 0x98050004 returning B3/B4 DID reach the runtime
  keybed (set "TRANSPOSE: C") but did NOT enter the self-test -> the entry uses a SEPARATE power-on
  raw-keybed-matrix scan (likely via the sub-CPU / an early boot read), not the runtime FIFO.
- NEXT: find that power-on held-key detect in the early boot + inject/model it (read-tap on the matrix
  address, or poke the detected-mode var); insert floptest_fat12.img; map START (MUTE UP 10) / STOP (MUTE
  UP 8); run + watch OK/NG. If the direct-FDC save/load runs to OK, the FDC modelling is validated e2e.

## TICK 2026-07-12 ~night(9) — floppy dispatch localized (disk-task never runs); pivot to SHARC DRC remainder
Non-masking tap diagnostic (Heisenbug preserved): during a normal format, 0 writes to the disk-task's
cmd/FDC-path markers (0x5006be91, 0x50000010-23, 0x5006BC19, packet) -- vs 811/27793 in the masked run. So
the async disk-task dispatch (class-5 handler) NEVER RUNS in the fast run; the format posts its command but
the task isn't scheduled in time -> ERROR 08. Divergence = the RTOS dispatch, not the FDC. Non-masking taps
have reached their limit (can show it didn't run, not why -- the timing is exactly what masks the bug).
fdc-architecture.md addendum 24. FLOPPY PARKED at this refined boundary; FDC hardware = the shipped
milestone. Pivoting to a concrete DRC-coverage improvement (part 23's documented remainder: the last SHARC
interpreter-fallback, an ALU averaging op) since the floppy is at a fundamental engine-timing wall.

## TICK 2026-07-12 ~night(8) — consolidated the FDC milestone (blog + docs); -sound none also ruled out
Floppy Heisenbug: added `-sound none` to the rule-out list (still 0 FDC -> not the sound subsystem;
fdc-architecture.md addendum 23). With SHARC-DRC / -debug / perfect_quantum / sound all ruled out and the
bug un-observable at instruction level, the floppy FORMAT stays parked at the engine-timing boundary.
CONSOLIDATED the genuine milestone (FDC located + modelled) into deliverables:
- **Blog: KN7000 part 24 "The disk controller was in the manual"** (mame-blog, committed) -- the RE story:
  two wrong FDC addresses, then the service-manual schematic (decoder IC1 -> Y2 = FDC.CS = 0x98020000),
  firmware confirmation (PC/AT regs, N82077AA), software-DMA via the 0x98010000 DACK, and the honest
  Heisenbug edge (nearly published "it formats now" on a trace -- caught it, a 3rd wrong answer avoided).
- **Docs: kn5000-docs kn7000.md corrected** (committed, Jekyll rebuilt clean) -- 0x98020000 was mislabelled
  "sound-subsystem control"; now documented as FDC IC103 (N82077AA) with the register layout + CS decode.
So this multi-tick floppy effort's shippable outcome = the FDC HARDWARE is correctly located/modelled/wired
(committed, faithful, no regression, driven at boot) + documented (blog + docs). The FORMAT feature remains
blocked on the emulation-timing Heisenbug (a future/fresh-angle problem, not a firmware/RE gap).

## TICK 2026-07-12 ~night(7) — ★★ floppy FORMAT blocked on an OBSERVATION-SENSITIVE emulation HEISENBUG
Decisive characterization (bp-counter diagnostic under -debug -debugger none, 6 RAM-increment breakpoints):
with the breakpoints the format REACHES the FDC (FDCdisp 0x48400084 = 27793 hits). So breakpoints -- like
the debugger trace -- MASK the bug. The pattern is unambiguous:
  memory TAPS (no per-instruction overhead) -> format errors before the FDC (0 accesses)   [BUG present]
  trace OR breakpoints (per-instruction overhead) -> format reaches the FDC (thousands)      [BUG masked]
=> It's a HEISENBUG: instruction-level observation slows the maincpu just enough to win a timing-sensitive
event race that the fast normal run loses (-> the disk-task dispatch errors -> ERROR 08 before the FDC).
Ruled out: SHARC DRC (-nodrc), -debug itself, set_perfect_quantum (all still fail in a normal run).
NET (honest): the RE is CORRECT + COMPLETE and the FDC HARDWARE MODELLING IS THE MILESTONE of this
multi-tick effort -- FDC @ 0x98020000 (N82077AA, schematic+firmware proven), PC/AT regs, INTC group 0x18
software-DMA via 0x98010000, all committed, faithful, no regression, and exercised by the BOOT FDC init.
The FORMAT does not complete because of an EMULATION-ENGINE timing bug (a lost event race in the RTOS
disk-task dispatch), NOT a firmware/RE gap. It resists diagnosis (observer effect). fdc-architecture.md
addenda 14-22.
NEXT (if pursued): memory-tap (no masking) the RTOS scheduler tick + INTC GxICR writes during a normal
format and correlate RAM state at the divergence to identify the awaited event and why its emulated
delivery is a hair too late; then fix that device's timing. OTHERWISE the floppy FORMAT is reasonably
parked here (FDC hardware done) and effort can move elsewhere -- all of Felipe's P1-P5 priorities are done.

## TICK 2026-07-12 ~night(6) — CORRECTION: "format reaches FDC" was a TRACE ARTIFACT; real blocker = dispatch race
Integrity correction to night(5): the "format issues FORMAT TRACK + busy-polls MSR" (fx2.tr, 230k) was an
OBSERVER ARTIFACT of `dbg:command("trace")`. Ruled out every emulated-time cause -- SHARC DRC (-nodrc),
-debug itself (-debug -debugger none, no trace), and set_perfect_quantum(maincpu) ALL still show the format
touching the FDC **0 times** and erroring (ERROR 08) before any FDC access. ONLY the trace command masks it.
So the real behaviour = the format errors in the class-5 disk-task SOFTWARE dispatch BEFORE the FDC (exactly
the night/night(2) finding), and it is timing/async-sensitive (the trace's heavy per-instruction wall-clock
overhead is the only thing that changes it -> likely a host-audio-thread race, not emulated-time).
NET STATE (honest, all committed, no regression):
- ★ FDC correctly LOCATED (0x98020000), MODELLED (N82077AA), and WIRED (INTC group 0x18 + DACK 0x98010000
  software-DMA) -- schematic + firmware proven, faithful, and exercised by the BOOT FDC init. Major win:
  the core "where is the FDC" mystery (~12 prior ticks) is SOLVED.
- ✗ The FORMAT still fails: it errors in the class-5 dispatch before reaching the FDC, so the DMA wiring
  isn't exercised by a format yet. This dispatch race is the true remaining blocker (deep; perf-quantum
  and DRC ruled out). fdc-architecture.md addenda 15-21.
NEXT (fresh budget): memory-tap the class-5 error-decision (0x484ADxxx / disk-op result) in a NORMAL run vs
the trace run to find the diverging branch; investigate the DSP-bridge host audio thread as the race source
(does bypassing/synchronising it let the format reach the FDC?). Once the format reaches the FDC reliably,
the shipped DMA wiring should carry FORMAT TRACK to completion (write a FAT12 disk).

## TICK 2026-07-12 ~night(5) — FDC fully modelled + wired (0x98020000 + DMA); [see night(6) correction above]
Completed the FDC hardware model + wiring (all committed, faithful, NO boot regression):
- FDC = N82077AA @ **0x98020000** (schematic decoder IC1 Y2 + firmware PC/AT regs). ✓
- Software-DMA WIRED: FDC.DRQ/INTRQ -> **intc_assert(0x18)** (GxICR 0x34000160, the FDC ISR 0x48402140's
  group); FDC.DACK slot **0x98010000** -> m_fdc->dma_r()/dma_w(). So a DRQ raises the interrupt whose ISR
  moves one byte via 0x98010000 <-> the RAM buffer -- the mechanism a real FORMAT TRACK uses. ✓
- Decoded the firmware's MSR busy-poll (0x48400190): waits for (MSR & 0x1F)==0 = command-complete, 500-tick
  timeout. FORMAT TRACK = 6 FIFO bytes, DMA mode (DOR 0x1C).
★ NEW BLOCKER (deeper, pre-existing, NOT the FDC): the format reaches the FDC **only under the debugger**.
  -debug -debugger none: format issues FORMAT TRACK + busy-polls MSR (fx2.tr, 230k). Plain runs (memory
  taps, incl. before any FDC change): the format touches the FDC **0 times**, shows ERROR 08, returns to
  the DISK menu -- it errors in the class-5 disk-task SOFTWARE dispatch BEFORE any FDC access. Real HW
  formats disks, so this is an EMULATION race in the RTOS disk-task dispatch (the debugger's scheduling
  masks it; MAME emulates in emulated-time so a pure CPU/timer ratio shouldn't shift -> genuine race,
  suspect interrupt-ordering or the DSP-bridge audio thread). fdc-architecture.md addenda 16-19.
NEXT (the real fix now): find why the class-5 disk task errors before the FDC in a NORMAL run -- memory-tap
the ERROR-08 decision (0x484ADxxx / completion byte / disk-op result) in a no-debugger run and diff the
branch vs the debugger run. Once the format reaches the FDC reliably, the DMA wiring should carry FORMAT
TRACK to completion (writes a FAT12 disk). The FDC itself is DONE + correct.

## TICK 2026-07-12 ~night(4) — CORRECTION: "ERROR 08 gone" was FALSE (Felipe's manual nav); FDC still not reached
RETRACTION (integrity): the "ERROR 08 gone" in tick night(3) was a MISREAD. That test used fast nav timing
that pressed buttons before screens loaded, so my presses didn't register -- Felipe had manually navigated
the format (he told me: "I pressed some buttons for you"), and I mistook his PLEASE-WAIT screen for my fix
working. A clean, properly-paced, snapshot-verified run (nav confirmed: DISK menu -> FORMAT-type page 2/2
-> PAGE UP -> ATTENTION -> YES) shows **ERROR 08 STILL happens, and the FDC at 0x98020000 is touched 0
times during the entire nav + format-execute** (tap armed from t=0). So:
- The FDC-at-0x98020000 model (commit 7a30aaf) is CORRECT HARDWARE (schematic-proven, and the firmware's
  boot init at 0x484000B5 does drive it -- that runs before the autoboot tap installs, so it isn't in the
  0-count). It stays as faithful emulation. But it does NOT fix the FORMAT.
- The FORMAT still errors in the SOFTWARE path BEFORE reaching any FDC command code (0x484027xx). This is
  the same class-5-dispatch blocker found earlier (night/night(2)): the format posts a class-5 disk
  command, the disk task errors without hardware I/O -> ERROR 08. Media-present uses strap 0x98070000
  bits10/11 (0x484D7751), NOT the FDC's DSKCHG, and forcing it didn't help.
UPDATE (same tick): a DEBUGGER TRACE of the format-execute (correct nav) shows the format DOES reach and
drive the FDC after all -- FDC micro-op dispatcher 0x48400084 (14x, DOR reset primitives) + format code
0x484027xx, then it **busy-polls MSR (0x98020008) 230,052x at PC 0x48400145** waiting for the FORMAT TRACK
command (DMA mode, DOR bit3 set) to complete. It hangs because NO DMA occurs (0x98010000 DACK + the MN10300
DMAC are untouched) so the command never finishes. So ERROR 08 = FDC-command-timeout, and the FDC IS the
right hardware -- the fix is FDC COMMAND COMPLETION, not a different address. (The earlier no-debugger tap
run showing 0 FDC accesses is a timing-sensitive divergence of the FDC-reset state machine 0x50000010/20 --
re-verify by tapping PC 0x48400145 without the debugger.) fdc-architecture.md addendum 16.
NEXT (clear path to a working format): (1) disassemble the MSR-poll helper at 0x48400145's callee -> which
MSR bit the firmware waits for; (2) map 0x98010000 (FDC.DACK) -> m_fdc->dma_r()/dma_w() so the FORMAT-TRACK
data phase transfers; (3) assert FDC TC (terminal count) at the byte count to end the command; (4) confirm
the N82077AA executes FORMAT TRACK + sets MSR/INT so the poll exits. The service-manual schematic
(FDC=N82077AA@0x98020000, DMA=0x98010000, IRQ/DRQ/TC pins) is the asset for all of this.

## TICK 2026-07-12 ~night(3) — ★★★ FLOPPY: FDC found at 0x98020000 (service manual) + modelled (correct HW)
The "new information" the floppy needed was in the repo all along: **service_manual/technics_sx-kn7000_
keyboard.pdf** (160pp). RE of the schematic + firmware CRACKED the floppy:
- **The FDC (IC103, C1DB00000607) is at 0x98020000.** Chip-select decoder IC1 (TC74VHC138F, MAIN 1/5 pg
  101) sub-decodes the 0x98000000 CS region by A16-A18: Y2 = FDC.CS = 0x98020000 (Y4=0x98040000 TG fixes
  the base; Y1=0x98010000 = FDC.DACK -- that's why the old "FDC@0x98010000" guess never saw regs). It is
  an **N82077AA / PC-AT-compatible** part (full DOR/DIR set), NOT upd72067, NOT 0x9CC00000 (dead-code red
  herring). CPU = MN103002A.
- Firmware drives PC/AT registers there (movbu, D16-D23 byte lane): **+4=DOR** (boot /RESET pulse
  @0x484000B5), **+8=MSR/DSR**, **+A=data FIFO**, **+E=DIR/CCR** (disk-change/DSKCHG @0x48402623). Register
  = (offset>>1)&7. The driver had this region mislabelled "sound control" (io_r returned 0) -> the
  disk-change read returned garbage -> media check failed -> ERROR 08.
- **HARDWARE MODEL SHIPPED (commit 7a30aaf):** replaced the default-OFF experimental upd72067@0x9CC00000
  with a real, always-on **N82077AA @ 0x98020000** (per-offset PC/AT handlers fdc_r/fdc_w, carved out of
  the io window AFTER it so it wins; removed the FDCEXP switch). Boot: NO regression (reaches play screen).
  This is faithful hardware (schematic-proven) and the boot init drives it. [NOTE: the "ERROR 08 gone"
  first claimed here was FALSE -- see tick night(4) retraction. The format still fails; the FDC is not
  reached by the format-execute.]
- NAV TIMING (Felipe's note): press the format-nav buttons SLOWER -- wait for each screen to fully load
  before the next press (PAGE UP was being pressed before the FLOPPY DISK FORMAT screen finished loading).
  Verified working timing: ~7s (420 frames) settle per step.

## TICK 2026-07-12 ~night(2) — priorities re-confirmed DONE; floppy at a boundary (SD-worker vs class-5 split)
Cron tick handed the 2026-07-11 priority list. RE-VERIFIED all five are already complete (earlier ticks):
- **P1 effects sweep = CLEAN.** Re-read wf_46aaaf77-352 + the completed re-run: 241 segments / 12 runs,
  **FAIL=0 SUSPECT=0 PASS=241**; divergence report 79/79 PASS; the old Chorus SUSPECT resolved in the R1B
  rerun (uploads reach the DSP, e.g. GM Chorus3 = 594). Nothing to fix.
- **P2 PAGE/CONTRAST = DONE + USER-CONFIRMED** (commits f614862, e414769; PAGE validated on SD LOAD 1/3-3/3).
- **P3 DRC MAC-native UML = DONE** (e487bb7, bit-identical, 82M->500k fallbacks). **P4 0x8238 = decoded
  constant 0x0800, loud-input covered by sweep. P5 SHARC catalogue = packaged** (notes/upstream-patches/,
  4 files). NB upstream SUBMISSION (opening a MAME PR) is outward-facing -> needs Felipe's explicit OK,
  not auto-done.
So the only genuinely-open thread is the FLOPPY (Felipe's freshest request). New findings this tick (RE):
- The SD path works via the disk WORKER 0x4854AD90 which blocks on **RTOS receive object 9** (0x4C03D36D)
  and dispatches command types 2/3 to **device methods via `calls (a1)`** (a1 = method ptr from the cmd/
  device ctx; type2 -> 0x4854B330 lookup, type3 -> 0x4854AFEE). The FORMAT instead posts a **class-5
  message (id 0x00050006) to task table 0x5000757C** -- a DIFFERENT mechanism that never reaches the
  worker (worker 0x4854AD90 ran 0x across the 1.6s format trace). 0x484D7930 (heavily executed) is a
  PERIODIC TIMER (wrapping counters 0x50150f47/48 via 0x484B3179), not the command handler -- earlier
  "state machine gated on 0x5006cc81" was that timer, not the op.
- Combined with addenda 11-13: parallel engine 0x484A4FBA = dead; transport 0x4854BF60 + kickoff
  0x484D7490 = 0 static callers (runtime method ptrs, never invoked for floppy); format touches ZERO
  hardware; result = ERROR 08. The floppy command path is INCOMPLETELY WIRED vs SD in this firmware image.
- HONEST ASSESSMENT: ~12 ticks have disproven every obvious FDC address (0x9CC00000/0x98010000/bit15 all
  dead) and shown the floppy op never drives hardware. Progress now needs NEW INFORMATION: the service
  manual's FDC (IC103) schematic/bus decode, or a logic-analyzer capture of a real KN7000 formatting a
  disk, to locate the true FDC interface. This is a diminishing-returns boundary; recommend PAUSING the
  floppy deep-dive pending that, rather than a 13th speculative tick. Nav + format-executes-to-ERROR-08 +
  the full RE are preserved (fdc-architecture.md addenda 8-13, memory [[kn7000-floppy-fdc]]).

## TICK 2026-07-12 ~night — ★ FLOPPY FORMAT: it's NOT a hang, it's ERROR 08; parallel-FDC path DISPROVEN
Felipe: "we should be able to create+mount a floppy image, format it via the KN7000 screen; investigate
and fix." ultracode ON -> 5-agent workflow + live RE. RESULTS (all reliable):
- **RETRACTED the bit15 "root cause" (git f556ba4).** Proven by full-image unidasm + pointer scan: the
  parallel-FDC engine **0x484A4FBA is DEAD CODE** -- zero callers (no call/jmp/bra target, no pointer, no
  task descriptor), preceded by `ret` so no fall-through. FDC init 0x4854D835's ONLY caller is 0x484A4FE3
  *inside* the dead engine. So the 0x9CC00000 uPD765 experiment AND the strap bit15 change target dead
  code. io_r 0x38000 now returns bit15 unconditionally set (moot, honest). Rule (g).
- **★★ THE FORMAT DOES NOT HANG -- it runs, fails, and shows "ERROR 08! An error has occurred while the
  disk was formatting... may be faulty" within ~2s** (snapshot-verified). Far more tractable than a hang.
- **The format-execute touches ZERO disk hardware** (taps: 0x9CC000xx=0, 0x9805000C=0, 0x34000160-17f=0
  except a brief 0x3400016c handshake, command reg 0x50005200 no observed write). The error is decided in
  firmware BEFORE any real I/O.
- **Disk-present check 0x484D7751 returns 5 = "NO DISK"**: 0x484D7713 returns 1 (my TG-present strap sets
  0x98070000 bits1,2), so it uses strap bits 11/10 -> type map {00->5(nodisk),01->1,10->2,11->3}; my strap
  has bits10/11=0 -> type 5. BUT forcing bits10/11 (type 3 via read-tap) does NOT clear ERROR 08 -> the
  disk-present type is not the (sole) gate.
- **The format-execute runs the disk-command PROCESSOR 0x484ADxxx** (ends ~0.13s after YES, then idle): it
  builds a command packet at RAM 0x5006bee2 with an XOR checksum (loop 0x484AD9B0, indexed by 0x5006bef0
  cmp 7), via the 0x4854BCxx disk fns + the 0x3400016c handshake. The packet is built but **no worker
  transmits it** (0x9805000C never written) -> ERROR 08. Consistent with a74728a8: SD has a worker task
  (0x4854AD90, created unconditionally) but **there is no floppy worker** -- the floppy command is built
  and never serviced/transmitted.
- LIKELY TRUE ROOT CAUSE: **firmware floppy-worker/dispatch gap** (no task transmits the built packet), OR
  a floppy driver-init gated on a hardware-present check that fails. NEXT: (a) disassemble the 0x484ADxxx
  command processor + find where the ERROR-08 result is set (is it a timeout on a transmit, or an immediate
  bail?); (b) check the driver vtable 0x4867B948 [0-5] inits for a floppy driver gated on a HW check I can
  satisfy; (c) find who (if anyone) is meant to consume the 0x5006bee2 packet + the 0x3400016c handshake
  semantics. fdc-architecture.md addendum 11-12.
- TOOLING (important, saves hours next tick): **single-line Bash commands work; multi-line compound
  commands wedge the virtiofs mount** (fd exhaustion -> `sudo -n /usr/local/sbin/drop-caches`). Trace via
  **`-debug -debugger none`** (debugger available, machine NOT paused) + `mach.debugger:command("trace f")`.
  Memory taps work but **ranges must be 4-byte aligned** (end low bits set, e.g. 0x..03/0x..0f/0x..ff).
  `register_frame_done` reliable; PC sampling via `cpu.state["PC"].value`. Snapshots via `mach.video:snapshot()`.

## TICK 2026-07-12 ~evening(2) — EXPERIMENTAL opt-in FDC SHIPPED at 0x9CC00000 (Felipe-authorized)
Felipe: "implement a clearly-labeled experimental FDC at 0x9CC00000/uPD765 best-guess, accepting it may
not work / may need reverting." DONE (commit 526c270):
- New config switch **"Experimental floppy (FDC) at 0x9CC00000"**, DEFAULT OFF. When ON, maps UPD72067
  MSR@0x9CC00000 + FIFO@0x9CC00001 (only 2 bytes -- SD scan-enable 0x9CC00004 + SD switches 0x9CC00008
  stay RAM). Runtime-gated in fdc_r/fdc_w (cfg isn't applied at machine_start); OFF falls through to
  LCD-RAM so it's byte-identical to before. INTRQ/DRQ -> logging stubs (MN10300 IRQ line unknown).
- VERIFIED: OFF = zero regression (boots to PMEM home + note plays); ON = boots to home AND the FDC
  engages (boot disk-init read of 0x9CC00000 pc 0x4854D725 now hits msr_r()). Does NOT make the floppy
  work: the FORMAT stalls upstream (disk task never services the command -> 0x9CC00000 never accessed
  during a format). Faithful labelled best-guess, revert = leave switch OFF. Detail: fdc-architecture.md
  addendum 8. TO TEST ON: cfg `<port tag=":FDCEXP" type="CONFIG" mask="1" defvalue="0" value="1"/>`.

## TICK 2026-07-12 ~evening — FDC: format WAIT mechanism found (stack-walk); disk cmd never serviced
Felipe: "use your knowledge of the FDC to implement it properly." Investigated toward that; the honest
blocker is now precisely located but a faithful implementation is NOT yet possible (would be a guess).
KEY RELIABLE FINDINGS (memory-tap stack-walk; bpset is UNUSABLE -- addendum 5):
- The format's execute handler polls status byte **0x5006BC19** at **0x484A593E** and waits for it to
  become a disk-command COMPLETION CODE **0xFB / 0xFC / 0xF6**. It stays **0x00** forever -> times out.
  So the disk command is posted but NEVER completes (not even an error) -> the servicing handler that
  does the FDC I/O + writes the completion code never runs.
- The format reaches **ZERO hardware anywhere 0x00-0xBF** (comprehensive tap) -- the disk command stalls
  in software before any device access.
- The disk hardware is the **0x9CC00000 latch** (disk code 0x4854Dxxx reads/writes 0x9CC00000/+9/+1B/+1FC;
  phantom buttons share the chip at 0x9CC00008). BUT the driver currently backs all of 0x9C000000-
  0x9CFFFFFF with **dumb RAM** (`map(...).ram().share("lcdbuf")`), so any disk-controller behavior is
  absent. Even so, the format never reaches 0x9CC00000 -> the servicing gap is upstream.
IMPLEMENTATION PATH (next ticks, each needs more RE): (1) find the SETTER of 0x5006BC19 (the completion
writer in the disk task) + why it doesn't run -- is the disk task created/scheduled? (2) determine the
0x9CC00000 disk-controller register semantics from 0x4854Dxxx (drive-select/motor/status + the uPD765
data/status) WITHOUT breaking the SD/phantom-button sharing; (3) model it so the command completes. Not
shipping a speculative FDC (rule g). Full detail: notes/fdc-architecture.md addenda 5-6.

## TICK 2026-07-12 ~late — FDC ARCHITECTURE fully reversed (Felipe's disasm ask); FDC=0x9C/0x9E candidate
Per Felipe "inspect the disassembly to understand how the FDC works" -> **notes/fdc-architecture.md**
(comprehensive). Key new findings this tick:
- **The FORMAT is a poll-for-completion loop**: after YES (SEG13 0x01) it spins ~2700x reading disk-state
  status bytes 0x5006BC19/BC23/BC24 (getters 0x4849FBD8/0x484A4F9C/0x484A4FAB), waiting for the DISK TASK
  to set them; the task never completes (its FDC I/O stalls) -> timeout -> back to DISK menu. The format
  posts its command via 0x484298A0 -> dispatcher 0x484285E4 -> task table 0x5000757C.
- **Candidate FDC hardware is in the 0x9C/0x9E region, NOT 0x98**: the bit-15-gated factory diagnostic
  (0x484A4FBA reads strap 0x98070000, `btst 0x8000`) exercises 0x9CE00000/04/08 (data), 0x9CC00009 (ctrl
  bit), 0x9CC001FC, 0x90C00000, 0x90008020. Driver deliberately sets strap bit15 to skip this diagnostic.
  The format does NOT call these (verified 0 breakpoint hits) -- they're the factory path -- but the disk
  task's real FDC I/O likely uses the same 0x9C/0x9E hardware. 0x98010000 stays a weaker unconfirmed
  candidate (a CS base only).
- EXHAUSTIVELY CONFIRMED: the format reaches ZERO disk/FDC hardware (tapped 0x30-0x9B, all clean) and posts
  NO class-5/6 disk-task command (0x484298A0 breakpoint: 0 hits) -- so the earlier "format posts to a disk
  task" inference was WRONG (corrected in fdc-architecture.md addendum 4, rule g). The format's own handler
  polls status bytes 0x5006BC19/23/24 and times out, but that handler has NOT been located (reached via
  MILK GUI screen dispatch, not a simple event). NEXT: a CPU INSTRUCTION TRACE across the YES press
  (SEG13 0x01 on the ATTENTION screen) to find the format-execute handler + its abort branch + what it
  waits on -- THEN the FDC hardware path (the getter-caller bpset via d@sp was too slow at 1345 fires/format
  + syntax-fiddly; use `trace` to a file gated to the YES window instead). Full detail + verified facts:
  notes/fdc-architecture.md (10 dated sections) + floppy-fdc-investigation.md.

## TICK 2026-07-12 ~afternoon — FLOPPY MODELED + DISK MENU OPENS + FORMAT TOOL REACHED; red dialog fixed
Session deliverables (all committed):
1. **FDC + 3.5" HD floppy WIRED** (a936d5a): real `upd72067_device` + `floppy_connector` at the
   0x98010000 CS candidate (io_r/io_w 0x8000-0xffff -> fdc_r/fdc_w). Drive = FLOPPY_35_HD (KN7000
   formats 1.44M 2HD, reads 720K 2DD — KN5000's 35dd corrected). Formats = default_pc_floppy_formats
   (raw .img round-trip; KN5000's mfm set can't). Build-link fix: genie listed upd765.o but `make`
   won't re-archive liboptional.a when the member LIST changes only — delete the stale archive to force
   a full re-archive (documented in floppy notes). Blank test imgs in kn7000_mame_build/floptest_*.img.
2. **★ DISK MENU OPENS: SEG0D 0x04 ("DISK"), NOT SEG0D 0x40** — prior "floppy-device-gated" conclusion
   RETRACTED (wrong button). From the DISK menu, SEG11 0x10 reaches the **FLOPPY DISK FORMAT** tool
   (1.44M 2HD / 720K 2DD). Felipe's format tool is REACHABLE.
3. **Red "known problems" startup dialog SUPPRESSED** (12639a3, Felipe's explicit ask): build.sh patches
   ui.cpp `show_warnings = !skip_gameinfo()`; run.sh passes -skip_gameinfo. Memory saved
   (kn7000-skip-startup-warning). GOTCHA for scripted runs: ALWAYS pass -skip_gameinfo or the autoboot
   never loads (the warning blocks emulation before frame 1).
4. Audio UNCHANGED (rule g): 0 FDC-region accesses during boot/idle/menu/audio -> io_r/io_w FDC change is
   inert for the reverb/audio path (bit-identical).

**★ FLOPPY NAV FULLY MAPPED + FORMAT EXECUTES (save-state soft-key sweeps, floppy_softkey_sweep.lua /
floppy_yes_sweep.lua):** DISK menu = SEG0D 0x04; FLOPPY DISK FORMAT (2/2, type select) = SEG11 0x10;
ATTENTION confirm (1/2, "Are You Sure? YES/NO") = PAGE UP SEG0B 0x10; **YES = SEG13 0x01** -> the format
EXECUTES ("ERASE WAIT!..") and returns to the DISK menu. (NO/back = SEG12 0x01.) The LCD soft-keys are a
scramble; these bits act as soft-keys only in this menu context.
**KEY: the format EXECUTES but ABORTS at a pre-FDC software gate (never touches ANY FDC hardware).**
Debugger breakpoints on ALL disk-driver/FAT/block funcs (0x4853282e/0x485328b5/0x4846da31/0x485335ff/
0x48532468/0x48532643/0x4846d800) fire ZERO times during the format; exhaustive read+write taps show only
normal TG/sound/DSP/SD + GPIO panel-scan traffic; the image is unchanged. **0x98010000 is UNCONFIRMED, NOT
disproven** (correction): it IS a chip-select base (boot 0x484009D0 -> 0x32000804=0x98010000) with no other
0x98 claimant, but no code path exercises the FDC (boot: 0 hits; format: aborts early; dir/LOAD: unreachable
+ device-not-ready). The UPD72067 there is harmless (0 accesses, audio bit-identical) and MAY be correct;
comments corrected to "unconfirmed" (rule g). NEXT EXPERIMENT: model the UPD72067 drive-ready/disk-present
status at 0x98010000 and re-test the format -- if its pre-gate then advances to a real FDC access,
0x98010000 is CONFIRMED. Full detail + tools: notes/fdc-architecture.md + floppy-fdc-investigation.md
2026-07-12 (6)-(10). Runner gotchas: use
register_frame_done (NOT add_machine_frame_notifier) + integer mach.time.seconds; never -log (floods);
save-state (m:save/m:load) makes soft-key sweeps clean; -skip_gameinfo mandatory for scripted runs.
**FDC ARCHITECTURE fully reversed from disassembly (Felipe's ask): notes/fdc-architecture.md** -- the
VFS/device-table layering (drive A: -> table 0x500079F8 -> registered driver method = the FDC I/O), block
read/write (0x4846DA31 `calls (a2)` = the FDC method, a runtime ptr cached via 0x50071254), the test-mode
RTOS path (FdIoFunc 0x484A1766 etc. post class-5/6 msgs to a disk task), and the separate FORMAT path
that aborts at a pre-FDC gate. Open question = the FDC's PHYSICAL address (runtime ptr; NOT in 0x98);
capture it by a live VFS file-op (dir/LOAD) that populates 0x50071254, then read a2 at 0x4846DA31's calls.

## ★★★ FULL GREEN-LIGHT MANDATE 2026-07-11 (Felipe, away many hours)
"Keep improving the driver autonomously. Assume my answer is 'yes, let's do it!' for everything.
Use cron jobs so you don't stop." Priority: (1) finish panel LEDs/buttons, (2) MAIN GOAL = effects
DSP processing working well (notes/dsp-effects-improvement-plan.md; DSP LLE is GREENLIT, SD-menu
blocker gone), (3) keep improving: rest of SD-card features, declare MIDI in/out ports, emulate the
floppy drive, hook the 4 volume sliders to what they control (some digitally set sound levels ->
sound subsystem) + make them draggable via the Lua slider lib. For PAGE/CONTRAST buttons Felipe
said: make an EDUCATED GUESS, he'll test + we refine. Cron: b9660922 (every 23 min).

## 2026-07-11g: DSPAUDIO CONFIG SWITCH REMOVED (Felipe) — native REVERB button is the only control
The bridge always follows the TG bus crossfade now; no config needed. CONSEQUENCE until the SHARC
divergence (step 3) is fixed: a fresh boot follows the firmware default (reverb ON) -> the first
note rails until REVERB is pressed OFF. This is the faithful routing; the divergence remains the
one open reverb item (reference-diff harness). Verified on fresh cfg: identical toggle behavior.

## 2026-07-11i: LOUD-DISTORTION HUNT (Felipe's report) — 3 workflows of eliminations; ROOT STILL OPEN
ELIMINATED with evidence (wf_64813f74-f36 + wf_e3d8b476-79b): dropped host level writes (the "index"
is the literal SHARC IOP register address -- stock host-DMA protocol; nothing load-bearing dropped);
input word alignment (kernel SPORT SLEN=23, 24-bit right-justified = our format); blocked boot
compile (REFUTED -- all 10 unit queues fill+drain at t=1.87-2.5s with compiled levels wet=0.101/
dry=1.0; the 0x50000038 stage byte is a red herring). LEARNED + SHIPPED: TOTAL DEPTH is TG-side
(sub-TG 0x8338=0x8500|depth per step; up=:SEG0B 0x04 / down=:SEG0B 0x08 on the reverb screen) -- now
honored in the bridge (DSP return x depth/127). Panel reverb TYPE select = queue-unit 0 (PM 0x8400,
Dark2=:SEG12 0x01 works, full 27-transaction reload verified). 0x8238=0x0800 written per depth step
(meaning unknown).
★ ROOT CAUSE STILL OPEN: the chain SELF-SATURATES on excitation, INPUT-INDEPENDENT (railed at
0x7FFFFF even with input trimmed -18dB; identical peak at depth 80 vs 0 pre-fix). Tail = rail for
~1.2s post-release then HARD CUT (timed mechanism?). PRIME SUSPECT: the ALUSAT fix (2d308c7) covered
DRC single-function ADD/SUB only -- ADDC/SUBB (cases 0x05/0x06) and the DUAL add/sub compute forms
still WRAP in the DRC; any effect using those in reflect/feedback logic re-creates the rec49-class
rail. NEXT: (1) extend ALUSAT to ALL DRC integer ALU forms (0x05/0x06, dual add/sub, multifunction
natives if any); (2) re-test with -nodrc (interpreter fully saturates) -- IF -nodrc SOUNDS CLEAN,
that alone proves the remaining-DRC-ops theory and the fix list; (3) then re-calibrate levels if
still needed. The 1.2s hard-cut = investigate after saturation is gone.

## ★★★★ TICK 2026-07-12 ~12:10 — SD LOAD FILE BROWSER WORKS + PAGE buttons validated on a real paged screen
Two demonstrable validations this tick (SD image sdtest.hd = FAT16 "KN7000 TEST", 64MB, attached via
-harddisk):
1. **SD LOAD file browser is FULLY FUNCTIONAL**: SD MENU (SEG0D 0x80) -> LOAD (R1 = SEG11 0x10) opens
   "SD LOAD, PAGE 1/3, SD-SOUND, 65,268KB free (0% used)" with FOLDER/SONG columns + FOLDER/ALPHABET/
   NUMBER sort + PREV/NEXT. The card is DETECTED, the 64MB FAT16 MOUNTS, free space is correct. The
   earlier "ERROR 93: SD lid is open" was correctly just NO CARD attached (SDCOVER default closed, but
   card-present=false). So SD file-ops work end-to-end with a card. (Confirms the SD subsystem is more
   complete than 'just mounts' -- the browser UI works.)
2. **PAGE Up/Down VALIDATED on a real multi-page screen** (the exact priority-2 scenario): SD LOAD is
   PAGE 1/3; PAGE UP (SEG0B 0x10) -> 2/3 (data-type load categories: CURRENT PANEL/PANEL MEMORY/SEQ/
   EFFECT MEMORY/FAVORITES/ALL CUSTOM STYLE...) -> 3/3; PAGE DOWN (SEG0B 0x20) -> 2/3 (md5-identical to
   the first 2/3). So PAGE Up/Down work correctly (1<->2<->3). Priority-2 PAGE fix re-confirmed on live
   paged content, not just MULTI EFFECT.
No code change (validation of existing functionality). SD LOAD note: it uses the SD-SPI path directly
(device struct 0x50071254 stays zero -- the disk-driver/FDC abstraction is floppy-only, as established).
Useful for the floppy: an SD image attaches via `-harddisk sdtest.hd`.

## TICK 2026-07-12 ~11:35 — FLOPPY fully mapped: disk path inits only on a FILE OP (SD menu bypasses via SPI)
Decisive RAM evidence: 0x98010000 appears NOWHERE in RAM; the disk device struct 0x50071250 is ALL ZEROS
(disk-driver abstraction not initialized); device table 0x5000097c = UI-object descriptors, not HW types.
KEY INSIGHT: the SD MENU works because it drives the SD card via the SD-SPI transport (0x9805000C)
DIRECTLY, bypassing the disk-driver/FDC abstraction. The FLOPPY path (driver[0] 0x4853282e -> block-read
0x4846da31 -> FDC(a1)) only runs on a Load/Save FILE OP selecting drive A:. So the FDC base isn't stored
until a file op runs -> confirming the FDC (0x98010000 candidate) + its register offsets needs a live
file op = deep menu nav + a modelled floppy drive.
FLOPPY GROUNDWORK NOW COMPLETE (RE phase): chip = uPD765-family (IC103 C1DB00000607, CS/DACK/TC/DRQ);
address = 0x98010000 (strong candidate; 0x98030000/0x98020000/0x98060000 eliminated); path = file-op ->
disk-init 0x4846d800 -> device struct 0x50071254 -> block-read 0x4846da31 -> FDC(a1); uPD765 stub scaffold
committed (labelled). The MODELING phase (wire MAME upd765 + floppy_image_device @0x98010000, drive the
file-op path, RE the KN7000 disk format, wire the 3 driver slots) is a DEDICATED multi-tick effort best
done WITH Felipe: he can insert a real floppy image + test menu navigation interactively. Full detail:
notes/floppy-fdc-investigation.md.

★ OVERALL STATE: all 5 priorities done/ear-blocked; effects excellent + suite-validated; DRC hot path
native (>99% fewer fallbacks); per-effect returns fixed; panels verified; chorus-depth + per-part model
+ floppy all thoroughly MAPPED. The remaining big items (floppy MODELING, per-part effect refactor,
reverb/wet loudness) each need Felipe (disk image / interactive test / his ear) or a dedicated multi-tick
push. Autonomous RE groundwork is essentially exhausted; recommend scoping the modeling work with Felipe.

## TICK 2026-07-12 ~11:10 — FLOPPY: FDC address narrowed to 0x98010000 (0x98030000 eliminated); stub narrowed
Continued Felipe's floppy thread. Firmware literal search resolved the FDC address candidates:
0x98030000 = ZERO firmware refs -> FDC NOT there (removed from stub). 0x98010000 = programmed as a
chip-select BASE by the boot bus-controller (mov 0x98010000,d0 -> (0x32000804) @0x484009D0), so it's a
valid CS region + the strong FDC candidate (free slot vs +0=DSP/+2,6=sound/+4,5=TG/+7=strap). Narrowed
the uPD765 stub to 0x98010000 only; reverb A/B BIT-IDENTICAL; rebuilt+published. FDC still not accessed
(0 hits) -- only touched on a real disk op, which the deeply device-gated DISK menu doesn't reach (last
tick: gate is a layered device-descriptor/UI check, FDC base is a runtime pointer in struct 0x50071254
set up by disk driver 0x4853xxxx). STATE: FDC = uPD765-family @ ~0x98010000 (best candidate); stub
scaffold in place; the mystery is GONE. Remaining floppy work = dedicated multi-tick: satisfy the
drive-present/device gate to open the DISK menu -> confirm the FDC slot + register offsets from the live
op -> wire MAME upd765 + floppy_image + KN7000 disk format + the 3 driver slots. Full detail:
notes/floppy-fdc-investigation.md. (All other priorities remain done/ear-blocked.)

## TICK 2026-07-12 ~10:40 — Felipe's request: stubbed uPD765 @0x98010000 -> DISK menu does NOT open (gate is deeper)
Per Felipe "stub the uPD765 at 0x98010000 and see if the disk menu opens": DONE (committed, labelled
HACK; also stubbed 0x98030000). RESULT: the DISK MENU (SEG0D 0x40) still does NOT open, and the FDC stub
is NEVER accessed (0 hits). The DISK-MENU handler BAILS at an earlier DRIVE-PRESENT gate before reaching
the FDC. Traced 3-4 levels: disk driver 0x48582CF0 checks a device-type/status (must be 0x11, else bail);
0x484A593E checks 0xfb/0xfc error codes; the 0x11 comes from 0x4842b30c -> 0x48414a4f -> a device-
descriptor TABLE at **0x5000097c** (index*4). So the gate is embedded in the layered disk stack (FS ->
block device -> FDC), matching the original "heavily abstracted" finding. Reverb A/B BIT-IDENTICAL (stub
audio-harmless); published. NEXT (multi-step, no longer a mystery): trace how the device-descriptor at
0x5000097c gets its type (a drive-detect GPIO / FDC probe?), satisfy the drive-present gate so the menu
opens -> then the FDC stub is reached and its exact register offsets appear -> confirm 0x98010000 vs
0x98030000 -> wire MAME upd765 + floppy_image + disk format + the 3 driver slots. The uPD765 scaffold is
in place. Full trace: notes/floppy-fdc-investigation.md.

## TICK 2026-07-12 ~10:15 — FLOPPY groundwork: FDC = uPD765-family, address NARROWED to 0x98010000/0x98030000
Advanced the highest-value remaining feature (floppy) with bounded static-RE (service manual) + live
elimination. FINDINGS: IC103 = FDC, custom part C1DB00000607; signal set FDC.CS/DACK/TC/DRQ = a
uPD765-family DMA floppy controller (MAME has upd765). FDC.CS is a CS-decoder SIBLING of TGCS(TG
0x98040000)/ADSPAB(DSP 0x98000000) -> the FDC is in the 0x98000000-0x9807ffff window (driver io_r/io_w
catch-all). Live elimination (fdcaddr.lua): 0x98060000 = SOUND CONTROL (0xEA periodic write, PC
0x4854D1A8) RULED OUT; the free CS slots 0x98010000 / 0x98030000 are the FDC candidates. CHICKEN-AND-EGG:
DISK MENU (SEG0D 0x40) bails at an early drive-present gate before touching the FDC, so a live disk op
can't pin the exact slot until that gate is satisfied. NEXT (dedicated floppy effort, now well-scoped):
stub uPD765 at the candidates + satisfy the drive-present gate to open the DISK menu, OR read the
main-board CS-decoder schematic to pin FDC.CS; then wire upd765 + floppy_image_device + KN7000 disk
format + the 3 driver slots (floppy=0x4853282e). No code change (rule g -- don't guess the exact slot).
Durable: chip family (uPD765), address region (0x98010000/0x98030000), and the gate are now KNOWN --
this converts the floppy from "runtime-pointer mystery" to a scoped modeling task. Full detail:
notes/floppy-fdc-investigation.md.

## TICK 2026-07-12 ~09:40 — DISK/SD MENU buttons live-verified (priority-2 check): SD works, DISK floppy-gated
Bounded priority-2 check triggered by last tick's "DISK MENU didn't open": is the DISK MENU button
mislabeled (like PAGE/CONTRAST were)? Live probe (menuprobe.lua + diskclean.lua) settles it:
- **SD MENU (SEG0D 0x80) VERIFIED WORKING** -- opens the full SD MENU (SD TOOLS/PREFERENCES/FAVORITE
  SONGS/CUSTOM STYLE/LOAD/SAVE/SONG MEDLEY/SD-AUDIO/SD-SOUND PLAY). Driver mapping CORRECT.
- **DISK MENU (SEG0D 0x40) does NOTHING from HOME** (md5-identical) = FLOPPY-DEVICE-GATED (adjacent SD
  MENU works + SD is modeled; the floppy/FDC IC103 is not). Will open once the floppy is modeled. No
  mislabel; SEG0D 0x40 label plausibly correct (ROM descriptor SEG0D.6 = event 0x2016).
- The "SEG12 b7 = DISK MENU" service-manual note CONFLICTS with the ROM descriptor (SEG12.7 = 0x2010
  context-dependent Sound Group) and the live SD menu -> corrected/disregarded in panel notes.
So NO button fix warranted; the DISK menu's only blocker is the unmodeled floppy (confirms the floppy is
the real gate, not a mapping). Corrected a misleading note (rule g). No code change. This RESOLVES the
open "DISK MENU didn't open" question from the floppy exploration: it's device-gating, not a button bug.

## TICK 2026-07-12 ~08:45 — DRC perf changes REGRESSION-VALIDATED across the effect suite (clean)
Bounded, high-certainty verification of the shipped native single-fn multiplier + ALU average (the most
recent code changes; previously only reverb-A/B'd). Re-ran the multiplier/average-heavy divergence sweep
runs on the CURRENT binary (native ops): R1 reverb + M3 (LFO filter/wah) + M4 (distortion complex/vocal)
+ S4 (flanger/phaser) = 79 segments. RESULT: FAIL=0, SUSPECT=0, ZERO rails, ZERO clips. Stronger: R1
fpeak values are IDENTICAL to the pre-DRC-change 241-effect sweep (Concert2=11.6%FS, Dark1=8.6%,
Plate2=8.1% -- exact match) -> the native ops produce BIT-IDENTICAL audio across the effect families,
not just the reverb. So the DRC hot-path work (82M->500k fallbacks, >99%) is confirmed robust suite-wide.
No code change (verification only). Closes the DRC perf work with suite-wide confidence.

## TICK 2026-07-12 ~09:15 — floppy exploration (FDC not reached; 0x84000000 false lead ruled out); honest completion
Applied the new register-read-at-tap capability to the highest-value remaining feature (floppy). Result:
FDC still not reached. SEG0D 0x40 ("DISK MENU") did NOT open a disk menu (LCD stayed HOME); the heavy
0x84000000 reads it triggered are MODELED RAM (alias of 0x44000000), NOT the FDC (false lead now ruled
out). Boot-only external-bus hits: 0x32000000 (bus/chip-select controller) + 0x8C000000 (upload). The FDC
(IC103) only appears on a real disk Load/dir op deep in the DISK menu, which needs reliable menu
navigation + likely a floppy image -- a genuine multi-tick task. Groundwork saved in
notes/floppy-fdc-investigation.md so the next attempt skips the dead end. No code change.

★ HONEST COMPLETION ASSESSMENT: the productive autonomous scope is COMPLETE. All 5 priorities done or
ear-blocked; driver in excellent shape. This session shipped: clean reverb (ALUSAT+sign-ext+TDM), FOUR
audible effects with correct per-effect returns, 241-effect divergence sweep (0 rails/clips), SHARC DRC
hot path native (82M->500k fallbacks, >99%, bit-identical), PAGE/CONTRAST buttons, upstream SHARC
catalogue (consolidated + split patches), blog Parts 16-23, docs. Deep RE mapped: per-part effect model,
chorus-depth mechanism (0x500CE342), + a reusable stack-walk/register-read tracing capability.
REMAINING threads ALL need Felipe or are big multi-tick: floppy (big; needs disk image + FDC model +
format RE), volume sliders (need per-part audio separation), reverb/wet loudness cal (ear-blocked),
chorus-depth apply (mapped, minor, deferred). Recommend: further large work be scoped WITH Felipe on
return. Autonomous ticks will continue only where genuinely bounded value exists (no manufactured rabbit
holes).

## TICK 2026-07-12 ~08:40 — chorus-depth DEFINITIVELY mapped (addr 0x500CE342) + 2 corrections; thread CLOSED (minor)
Used the register-read-at-tap capability to finish mapping the chorus-depth mechanism (and correct two of
my own earlier errors): the per-effect DEPTH array is **0x500CE340** (sound-dsp @+0, CHORUS depth @+2 =
0x500CE342). It is WRITTEN on EVERY effect toggle by PC 0x4C037DA8 -- value 0 in the cold-chorus context,
0x3C in the sound-dsp context. CORRECTS my prior "depth is STORED not computed" (I'd tapped 0x500Bxxxx and
missed 0x500Cxxxx) -- it's COMPUTED per toggle. The value differs by the per-part iteration context (A1
part-settings pointer 0x500BA862 cold vs 0x500BA800 sound-dsp + the bit2 gate from func 0x4C005000). Full
map: emitter 0x4C036FBA <- wrapper 0x4C037DB9 <- send-writer 0x4C005000 (bit2-gated depth read) -> depth
store 0x4C037DA8 -> 0x500CE342. CLOSING this thread: thoroughly mapped, MINOR (chorus audible via its
screen; only the quick home toggle leaves depth 0), diminishing returns. Reusable stack-walk +
register-read-at-tap capability is the durable win (also unblocks the floppy FDC trace). No code change
(rule g). Full detail: notes/per-part-effect-application.md.
HONEST STATE: all 5 priorities done/ear-blocked; driver in excellent shape. Remaining threads: floppy
(valuable, BIG multi-tick, needs a disk image + format RE + the FDC model), volume sliders (need per-part
separation), reverb/wet loudness cal (ear-blocked), chorus-depth (mapped, minor, deferred). The productive
autonomous scope is essentially complete; the biggest remaining lever (per-part effect model / floppy) is
a multi-tick effort best scoped with Felipe.

## TICK 2026-07-12 ~08:00 — REUSABLE stack-walk capability + chorus depth-read logic traced
Unblocked the caller-tracing wall. MAME has NO Lua debug/bp interface without -debug, BUT cpu.state
exposes PC/SP/A0-A3/D0-D3/MDR -> at a DATA-access write-tap, read SP and walk the stack for lib return
addresses (0x4C0xxxxx) = the CALLER CHAIN. REUSABLE (also unblocks the deferred floppy FDC-base trace).
Applied to the chorus send: recovered caller chains (cold vs sound-dsp), both through send-writer func
0x4C005000 + emitter wrapper 0x4C037DB9. Disasm of 0x4C005000 = the DEPTH-READ LOGIC:
  depth = (bit2 of *(a0) set) ? *(a0+0x15) : 0   ; a0=*(0x20,sp); +0x15=chorus depth byte
Cold path -> 0 (gate bit2 clear); sound-dsp path -> 0x3C. So the stored depth (0x3C confirmed) is gated
by an 'apply' bit2 of *(a0); the cold chorus-toggle context has it clear. FAITHFUL-vs-GAP now narrowed:
does the cold chorus-toggle context legitimately leave bit2 clear (faithful lazy apply) or should it be
set (gap)? NEXT = find where bit2 of *(a0) gets set (the apply trigger; the 0x4C03B301 layer only in the
sound-dsp chain is the part-effect recompute that satisfies it). No code change (rule g). Durable:
reusable stack-walk technique + the chorus depth structure (a0->+0x00 bit2 apply gate, +0x15 depth).
Full trace: notes/per-part-effect-application.md. CORRECTS+SUPERSEDES the prior deferral ('needs
debugger-level tracing') -- the stack walk IS the tool, and the trace advanced substantially. Still a
minor user-facing issue (chorus audible via screen); all 5 priorities remain done/ear-blocked.

## TICK 2026-07-12 ~07:25 — chorus-depth trace: CORRECTED a wrong inference; deferring (tooling limit)
Continued the chorus-depth trace. Empirical data-read tap on the descriptor array 0x500CE404: it is
read once on REVERB toggle, ZERO on chorus/sound-dsp toggles. So last tick's INFERENCE that the
0x4C009000 per-part loop is the chorus-apply is FALSIFIED -- it's the REVERB per-part apply. The
chorus/sound-dsp/multi sends use a DIFFERENT, untraced apply path (the sound-dsp chorus-depth 0x0B3C
goes through it). Corrected notes/per-part-effect-application.md (rule g -- the prior inference was
hedged; now falsified + fixed). TOOLING LIMIT: MN10300 instruction fetches don't fire read-taps, so
loop execution is only detectable via a data access the routine makes -- further trace of the chorus
apply needs debugger-level (bpset) tracing. DEFERRING this deep thread: it's a minor user-facing issue
(chorus IS audible via its screen; only the quick home-screen toggle leaves depth 0), and it has hit
diminishing returns across several ticks. DURABLE from the trace: effect enable flags @0x500C0758;
reverb per-part apply loop 0x4C009000 -> 0x4C03A660 -> descriptor array 0x500CE404 (stride 0x130, type
@+0x10); emitter 0x4C036FBA. All 5 priorities remain done/ear-blocked; driver in excellent shape.
Honest status: the productive autonomous scope is largely complete; remaining threads are deep RE
(chorus-apply path, per-part model) or ear-blocked (reverb/wet loudness cal).

## TICK 2026-07-12 ~07:00 — mapped the per-part effect application system (chorus-depth RE, no fix yet)
Pursued the chorus-depth-on-cold-toggle question (user-facing: press CHORUS -> LED on but depth 0 =
inaudible until a sound-dsp/part-effect interaction applies stored depth 0x3C). Static RE (unidasm) +
live PC/RAM capture established: (1) chorus send ALWAYS written by emitter 0x4C036FBA (cold=depth0,
sounddsp=depth0x3C); (2) depth 0x3C is STORED, not computed on the toggle (0 writes of 0x3C to
0x500B0000-FFFF during a sound-dsp toggle); (3) effect ENABLE flags = 0x500C0758 (reverb=bit9, setters
0x4C00908F+ that ONLY set the flag, no send write); (4) apparent per-part apply loop 0x4C009000 (parts
0..0x22) -> send-writer 0x4C03A660 keyed off part-descriptor array 0x500CE404 (stride 0x130, type byte
@+0x10). MODEL: global enable toggle sets a flag+LED; a SEPARATE per-part apply pass writes the sends
with stored depths. Faithful-vs-gap precisely scoped: does the CHORUS-enable handler trigger the apply
loop (gap if yes-on-HW-not-emu; faithful if it relies on a later recompute)? NEXT = trace callers of
0x4C009000 + disasm the chorus-enable handler. No code change (rule g -- don't fake the apply). Durable:
advances the per-part effect model (deferred enabler for chorus-depth + APC/SEQ volume + per-effect
sends). Full map: notes/per-part-effect-application.md. ALL 5 PRIORITIES remain done/ear-blocked.

## ★★★★★ TICK 2026-07-12 ~06:33 — DRC hot path COMPLETE: native ALU average too; 82M -> <500k fallbacks (>99%)
Finished priority 3. After last tick's native single-fn multiplier (66M fallbacks gone), the biggest
remaining fallback was the fixed-point ALU AVERAGE (op 0x09, Rn=(Rx+Ry)/2, ~3M/reverb -- the 21065L
effect microprograms use it for reverb/filter interpolation). Implemented native UML (commit e487bb7):
overflow-free signed average + exact flags (AC=carry of the 32-bit Rx+Ry, AV=0, AN/AZ from result, rest
cleared, gated on liveness). VERIFIED reverb BIT-IDENTICAL (md5 0787b60c; the AC carry is exact).
Instrumented confirm: total DSP fallbacks now UNDER 500k/22s-reverb (counter at 500k threshold never
fired) -- down from 82M originally (>99% reduction; the DSP DRC hot path is now essentially fully
native). Built + published (06:33), clean-build A/B bit-identical. Wall-clock still host-noise-bound.
Both patches (single-fn multiplier + ALU average) belong in the upstream SHARC catalogue. ALL PRIORITIES
DONE: P1 sweep clean, P2 PAGE/CONTRAST done, P3 DRC hot path native (this), P4 0x8238/loudness done/ear-
blocked, P5 catalogue current. Remaining open threads are deep/ear-blocked: chorus-depth-on-cold-toggle
(per-part effect-depth static RE), per-part effect model refactor, reverb/wet loudness cal (Felipe's ear).

## ★★★★★ TICK 2026-07-12 ~06:20 — PRIORITY 3 (real hot path): native SINGLE-function fixed multiplier, 66M fallbacks GONE
Data-driven. Instrumented the SHARC DRC compute-fallback and found the effects kernel's hot path is NOT
the multi-function MAC (which I made native earlier -- and which the kernel NEVER uses; 0 multiop
fallbacks) but the SINGLE-function fixed-point multiplier: ~82M interpreter fallbacks per 22s reverb,
~66M of them signed*signed general mult/MAC (0x78 Rx*Ry=27M, 0xB8 MR+=15M, 0xF8 MR-=12M, 0xBC=9M,
0x7C=3M). The DRC sent the WHOLE fixed multiplier family to generate_unimplemented_compute (interpreter
fallback). IMPLEMENTED native UML for the SS general forms (0x70-7f/0xb0-bf/0xf0-ff) mirroring the
interpreter + the existing native multi-fn MAC. VERIFIED: reverb WAV BIT-IDENTICAL (md5 0787b60c...);
fallbacks 82M->~3M/run (96% down), sf-mult-SS 66M->0. Wall-clock too noisy on this host to quantify
(64-69% both before/after) but the interpreter-call elimination is definitive. Built+published (06:20).
Commit bb2d516. Remaining ~3M fallbacks = mostly ALU average u0:09 (20x smaller, easy follow-up) +
non-SS/SAT-RND multiplier (rare). This CORRECTS priority 3's premise (the multiop MAC wasn't the hot
path; the single-fn multiplier was). NEXT: (optional) native ALU average u0:09; add this to the upstream
SHARC catalogue (priority 5); blog. Also from earlier this tick: chorus/multi buttons WORK (LED evidence,
manual); chorus-depth-on-cold-toggle is a per-part effect-depth detail (static RE, deferred).

## TICK 2026-07-12 ~06:15 — chorus/multi toggle RESOLVED: buttons WORK (not a panel bug); it's an effect-DEPTH detail
Investigated last tick's chorus/multi "toggle doesn't engage" flag. DECISIVE via (1) the USER MANUAL
(p~2518: "Press the CHORUS/REVERB/MULTI button to turn it on. These effects are applied to all the
sounds") = they are DIRECT global toggles; (2) LED OUTPUT DIFF (scratchpad/retcap/ledcheck.lua): a COLD
CHORUS press toggles cpr_led29 0->1, cold MULTI -> cpr_led28, REVERB=cpr_led27 (matches prior RE),
SOUND DSP=cpr_led19. So the FIRMWARE PROCESSES the cold chorus/multi press and the panel HLE delivers it
-- THE BUTTONS WORK. NO panel-button-mapping bug. My last two ticks' "context-dependent / doesn't engage"
framing was WRONG -- I watched the SEND (lagging) instead of the LED (immediate). CORRECTED in notes.
REAL REMAINING (subtler, effect-depth, NOT panel): a cold chorus toggle -> LED on but SEND (0x8198 low =
per-part chorus DEPTH) stays 0 even after playing (clincher.lua) = on-but-inaudible; after a SOUND DSP
toggle the same press writes send=0x3C (audible). So depth application is gated on an effect-bus refresh
that the part-effect (sound-dsp) path triggers, not the cold global toggle. Likely default per-part chorus
depth=0; unresolved whether faithful (need a depth set on the CHORUS screen) or a depth-apply gap. Belongs
to the per-part effect-depth model (future RE). NOT changing anything (rule g). No code change this tick
(pure RE/correction). Also: manual text extracted to /tmp/kn7000_manual.txt (useful reference).

## TICK 2026-07-12 ~05:45 — stress-validated the per-effect return fix; ruled out sliders; flagged a panel loose end
Surveyed the breadth mandate: MIDI in AND out are DONE (TX->mdout1/mdout2 wired, line 2833+), SD done.
Volume sliders: MAIN=post-DAC master gain (analog model, faithful); APC/SEQ needs per-part accompaniment
separation (the big refactor) and MIC/LINE-IN have NO input source in the sim + no firmware ADC read path
-> NOT a clean win, deferred with reasoning.
STRESS-VALIDATED last tick's per-effect return fix (scratchpad/retcap/excite*.lua): each effect isolated
+ 8-key cluster (loudest realistic input): SOUND DSP isolated (reverb OFF) -> own slot 0xC356 peak 488644
(5.8%FS), 0 rails (fix AUDIBLE in isolation + STABLE under load; before fix = muted); REVERB -> 16.0%FS,
0 rails; DAC across the run = 0 clips. Excitation-dependent caveat from the divergence sweep substantially
CLOSED (loudest input hits <=16%FS, far from the 94% rail; sweep already covered all TYPES).
NEW PANEL FINDING (flag for priority-2 panel work): CHORUS (SEG11 0x04) + MULTI (SEG10 0x04) on/off
toggles did NOT engage their send (ch19.r8/ch29.r8 stayed 0) via scripted home-screen press, though cap3's
isolated per-button diff DID see ch19.r8 move -> these two effect-toggle bits look CONTEXT-DEPENDENT
(matches panel-completion-plan's note on context-dependent 0x2010 args). SOUND DSP + REVERB toggles engage
reliably. Chorus/multi AUDIO already validated via the sweep's screen-nav. Loose end, NOT a fix bug.
No code change this tick (validation only) -> no rebuild/publish. Full writeup: notes/effect-return-routing.md.

## ★★★★★ TICK 2026-07-12 ~05:15 — PER-EFFECT DSP RETURNS: reverb-off no longer mutes other effects
Resolved+FIXED the open faithfulness question (chorus/multi/sounddsp were scaled by the reverb return
gret -> reverb-off wrongly muted them). Live sub-TG bus capture (scratchpad/retcap, per-effect isolated
toggle diff; GOTCHA: latch=low-half mask 0xFFFF / data=high-half mask 0xFFFF0000, both at off 0x98050000)
proved each effect owns a DISTINCT return and the REVERB button moves ONLY the reverb's:
REVERB=ch03.rA(0x803A), SOUND DSP=ch09.rA(0x809A), MULTI=ch06.rA(0x806A), CHORUS=send-only(no return
register), DIGITAL EFFECT=separate subsystem(no TG-bus write). FIX (fa06930): tonegen captures ch09.rA->
m_gain_dsp_ret + ch06.rA->m_gain_multi_ret; bridge scales SOUND DSP by gdsp_ret, MULTI by gmul_ret,
CHORUS drops gret (fixed makeup); panel_scan polls them. VERIFIED: (1) reverb-only BIT-IDENTICAL
(money.lua md5 0787b60c... unchanged -- reverb-on => gret==per-effect returns so no change; effects-off
=> gated); (2) reverb OFF + SOUND DSP ON: unit-9 slot 0xC356 peak 231293 (2.8%FS) now reaches DAC via
ch09.rA (was xgret=0 muted). No divergence regression (reverb-on path unchanged; effects already swept
clean). Built+published. RE: notes/effect-return-routing.md + notes/retcap-harness/. NEXT: docs+blog;
chorus makeup + *_WET=0.60 still ear-cal (Felipe).

## ★★★★★ TICK 2026-07-12 ~04:35 — PRIORITY 1 CLOSED: divergence sweep = 241 selections, ZERO rails/clips
Re-ran the full effect-type sweep on the CURRENT four-effect binary (the Jul-11 sweep predated the
four-effect wiring). 241 selections across ALL four effect screens: Reverb 8, Chorus 8, Multi 14
families (incl. distortion bench: DistortedAmp/Distortion/Fuzz/Overdrive), Sound-DSP bank (enhancer,
paramEQ, ringmod, vibrato, autopan, tremolo, 2 rotaries, flanger, phaser, celeste, exciter, autowah).
TWO independent signals: (1) 60Hz frame sampler on DSP out-slots 0xC342-0xC359 (rail=0x7FFF00=94%FS,
catches self-excitation even over silence); (2) DAC int16 clip check from the WAV. RESULT: FAIL=0
SUSPECT=0, max fpeak 11.6%FS (Concert2), 0 railed frames, 0 clips over 241 segs. Uploads confirmed the
DSP was reprogrammed (up_sel>0 on 170/196 non-baseline). LOAD-BEARING: flanger/phaser/rotary (same
clip-and-fold triangle-LFO arithmetic that sank the reverb) all pass at ~5%FS -> the ALUSAT+MAC fix
GENERALIZES to the whole class, not just the reverb. Scope caveat: non-reverb units mostly ran over
near-silence (sends~0 until depth set) -> proves no program SELF-excites (the input-independent failure
that actually bit us); excitation-dependent heavy-drive artifacts = separate lower-risk follow-up.
DELIVERABLES: notes/effect-sweep-divergence-result.md, notes/effect-sweep-verdicts.json (241 PASS),
notes/divergence_report.py, notes/effect-sweep-final-table.txt. PUBLISHED: blog Part 21 "Every effect,
no rails" (posts.json=23), docs kn7000-effects-dsp.md (sweep paragraph), Jekyll rebuilt OK.
ALL PRIORITIES NOW DONE/BLOCKED: P1 CLOSED (this). P2 PAGE/CONTRAST done+user-confirmed. P3 native MAC
0x06/0x08-0x16 done+bit-identical. P4 0x8238 decoded(closed)+loud-input effectively covered by sweep;
loudness-cal ear-blocked. P5 catalogue in good shape. OPEN faithfulness Q logged (shared-vs-per-effect
DSP return; rule g, needs Felipe/RE). No unblocked priority work remains this tick.

## TICK 2026-07-12 ~04:00 — PRIORITY 1 divergence sweep RE-RUN on the current four-effect binary
The Jul-11 sweep (wf_46aaaf77) predated the four-effect wiring (only reverb reached audio then), so its
"chorus SUSPECT/no-change" is stale/resolved. RE-RUNNING the full 227-segment sweep (R1B chorus + M1-M5
multi + S1-S5 sounddsp) against the CURRENT binary (kn7000 built 02:52), memory-safe (FX_TAP=false frame
sampler). New divergence-focused reporter: scratchpad/fxtest/divergence_report.py (FAIL=rail/clip,
SUSPECT>=50%FS, calibrated vs R1 reverb healthy band 4-12% FS; rail thr 0x7FFF00=94%FS).
RESULTS SO FAR (all PASS, 0 rails, 0 clips): R1 reverb 8/8, R1B chorus 8/8 (uploads confirmed 282-647),
M1 multi delay/attacker 21/21 (uploads 90-471). Chain grinding through M2-S5 (distortion/fuzz/modulation
= the stress cases) in the bg; waiter bwzs7g623 will report. Also: priority 3 (native MAC 0x06/0x08-0x16)
CONFIRMED done+bit-identical; priority 4 0x8238 CONFIRMED decoded (constant, closed); priority 5
catalogue in good shape (03/04 in sync, 01/02 layered). CODE REVIEW of the four-effect mix: correct;
one OPEN faithfulness Q logged (chorus/multi/sounddsp wets scaled by gret -> reverb-off mutes them;
shared-vs-per-effect DSP return unresolved, rule g, flagged for Felipe).

## TICK 2026-07-12 ~03:30 — EQ feasibility confirmed (insert model works; active-detection pending)
Tested EQ (unit 8) insert: feeding it unit-0's output -> near-identical peak (254056 vs 254059, flat
EQ passes level) = it IS a functional master INSERT. But avg per-frame diff ~39806 even flat (biquad
phase/delay) -> always-inserting would break the bit-identical reverb guard. Faithful EQ must be
CONDITIONAL (insert only when gains nonzero); remaining piece = EQ-active detection (DSP-coeff-vs-flat
or main-CPU EQ-gain RAM). Lower value (flat default) + complication -> EQ documented as a
lower-priority refinement, not forced. FOUR audible effects (reverb+chorus+SOUND-DSP+MULTI) is the
strong validated stopping point for the effects work; EQ (insert, active-detect pending) + FLAG3 4
records (deep frame model) remain the harder/lower-value items. All priorities done/Felipe-blocked.

## TICK 2026-07-12 ~03:10 — four effects validated robust; EQ deferral documented
FOUR-EFFECT ROBUSTNESS: all part-effects (chorus+SOUND-DSP+MULTI) + reverb, 18-note cluster held ->
DAC 0 clipped (peak 2443 > reverb-only 2085 = effects contribute; summing robust under stress). EQ
(u8) DEFERRED with rationale: it's a master/INSERT (no send channel), flat 0dB default, and inserting
it would break the bit-identical reverb guard even flat -> needs active-detection + conditional insert
(harder, lower value than the sends). 4 audible effects (reverb+chorus+SOUND-DSP+MULTI) is the solid
validated state; EQ + the 4 FLAG3 records remain (both harder/different). All priorities done/Felipe-
blocked; PAGE/CONTRAST user-confirmed. Ear/HW pending: wet levels, reverb loudness, circular-wrap OK.

## ★★★★★ TICK 2026-07-12 ~02:50 — FOURTH audible effect: MULTI (unit 1)
Cracked MULTI's unit with a SHARPER method: diff the DM coeff blocks between two MULTI TYPES (delay
vs distortion) so the constant effect-bus refresh cancels -> UNIT 1 rewrote 43 words (rec15, comb+
delay -- matches MULTI's Cross-Delay default), unambiguous vs 1-5 noise (earlier u5 candidate was
noise). Feeding u1 outputs cleanly (112264). SHIPPED (669a66a): tonegen captures MULTI send 0x8298
(verified low byte==on-screen MULTI DEPTH, 82), tick feeds u1 in 0xC364 + sums u1 return 0xC344 as
independent wet; DSP output ring now 8-wide (reverb/chorus/sound-dsp/multi). VERIFIED: reverb
bit-identical all-off (A/B 0/2.11M), MULTI on -> send 82, u1 out 89650, DAC 0 clip/rail. Docs + blog
Part 20 amended (the recipe's 'edge' crossed by a sharper measurement, not a guess).
FOUR audible effects: REVERB(u0)+CHORUS(u4,0x8198)+SOUND DSP(u9,0x8098)+MULTI(u1,0x8298). Only EQ
(u8, master/insert) + the 4 FLAG3 records remain. The coeff-TYPE-diff is the definitive unit-ID method
now. Same first-cut approximations (whole-mix feed; *_WET=0.60 need ear cal).

## TICK 2026-07-12 ~02:15 — MULTI unit unconfirmed (rule g, held); milestone documented
SPORT decode attempt: the DSP-side RX-DMA layout is readable (unit inputs scattered: u0=0xC362,
u4=0xC36A, u8=0xC372, u9=0xC376, u6=0xC378 -- no simple channel->slot pattern), but the TG->slot
channel routing lives in the MAIN firmware (TG SPORT config), not the DSP kernel -- a deeper untraced
RE. Combined with u5=rec10(phaser) mismatching MULTI's Cross-Delay default, MULTI's unit is NOT
confirmed -> NOT shipped (rule g). Documented the exact remaining piece (TG SPORT channel->slot map).
Published blog Part 20 "A repeatable recipe" (the coeff-diff unit-ID method + SOUND DSP as 3rd voice +
where the recipe stops at MULTI). posts.json=22.
STATE: 3 audible effects (reverb+chorus+SOUND-DSP), validated coexisting, reverb pristine. MULTI =
send-confirmed, unit blocked on the TG-SPORT channel-map decode (main firmware). EQ = master/insert.
FLAG3 4 records = deep frame model. PAGE/CONTRAST user-confirmed. All priorities 1-5 done/Felipe-
blocked. Ear/HW items pending Felipe: wet levels, reverb loudness, circular-wrap OK.

## TICK 2026-07-12 ~01:55 — MULTI send confirmed (0x8298), unit pending SPORT decode
Followed the MULTI plan: fixed the navigation (proven timing), enabled MULTI WITH SOUND DSP active to
force the refresh -> MULTI send 0x8298 low byte = 127 = on-screen MULTI DEPTH (snapshot-verified MULTI
ON). No CALL re-patch (MULTI runs on a loaded unit). BUT its unit isn't cleanly identifiable: coeff-
diff is refresh-noise-dominated and the weak candidate (u5=rec10 phaser) mismatches MULTI's Cross-
Delay default. Per rule (g), NOT guess-feeding. The clean path = decode the kernel SPORT RX DMA
channel->unit map (channel 0x29 -> unit input slot) -- a deeper RE, deferred. 3 audible effects
(reverb+chorus+SOUND-DSP) remain the solid validated state; MULTI is send-confirmed + unit-pending.

## ★ 2026-07-12 USER-CONFIRMED: PAGE Up/Down + CONTRAST Up/Down are correctly mapped (Felipe)
Felipe confirmed directly: "contrast up/down and page up/down are all correctly mapped now." Priority
2 CLOSED and user-validated. Mapping (shipped f614862): PAGE = pseudo-part 0x18 (SEG0B 0x10 up /
0x20 down); CONTRAST = pseudo-part 0x1D (SEG05 0x04 + / 0x08 -). No further work needed here.

## TICK 2026-07-12 ~01:30 — three effects validated coexisting; MULTI blocked on enable
Combined test PASS: reverb + chorus(u4 250282) + SOUND DSP(u9 290906) all audible at once, 0 rails,
DAC 0 clipped -- multi-wet summing robust. MULTI extension BLOCKED: its send 0x8298 stayed 0 with the
tried enable recipe (block-refresh quirk + unverified p2 MULTI masks); coeff-diff confounded by the
block refresh. MULTI's unit is elsewhere (u5 rec10 leading, NOT u9=SOUND DSP -- they're independent
effects). TO DO: verify p2 MULTI masks via snapshot, force the 0x8298 refresh (another effect active),
confirm send tracks MULTI DEPTH, then feed-test u5. THREE audible effects remain the solid state
(reverb+chorus+SOUND DSP); reverb bit-identical guard holds; tree clean, binary published.

## ★★★★ TICK 2026-07-12 ~01:10 — THIRD audible effect: SOUND DSP (unit 9)
Big tick: (1) RESOLVED unit-0 = the reverb (rec56, stable; type=coefficients, no re-patch). (2)
IDENTIFIED SOUND DSP = unit 9 (rec49) via enabling-time DM-coefficient diff; verified unit 9 outputs
938389 when fed. (3) SHIPPED SOUND DSP audibility (660ad59): tonegen captures send 0x8098 (verified
low byte == on-screen SOUND DSP DEPTH), tick feeds unit-9 (0xC376) + sums return (0xC356) as an
independent wet; DSP output ring widened to 6 (reverb/chorus/sound-dsp). VERIFIED: reverb bit-identical
all-off (A/B 0/2.11M), SOUND DSP enabled -> send=40, unit-9 out 266447, DAC 0 clip/rail. Docs updated.
THREE audible effects now: REVERB (u0) + CHORUS (u4) + SOUND DSP (u9). Same first-cut approximations
(whole-mix feed; CHORUS_WET/DSP_WET=0.60 need ear calibration). NEXT: MULTI (send 0x8298, same
mechanism -- identify its unit via coeff-diff + feed); EQ (u8 master/insert, different); FLAG3 4
records (deep). The effect-audibility mechanism (identify unit via coeff-diff -> feed input -> sum
return, gated) is now proven+repeatable.

## TICK 2026-07-12 ~00:50 — chorus robustness PASS + SHARC upstream patches packaged
- CHORUS ROBUSTNESS (dense input): PASS. Chorus + 18-note cluster held -> DAC peak 2186, 0 clipped
  (chorus unit rec06 self-CLIPs; feed is bounded). Production-robust like the reverb.
- PRIORITY 5 DONE (packaging): notes/upstream-patches/ = 4 SHARC-core patch files (ALUSAT add/sub,
  full family, specialization, native MAC) + PR-ready README (apply order, headline = real
  DRC-vs-interpreter divergence, verification = DRC==interpreter/reverb WAV A/B, caveat that patch
  #3 bundles the KN7000 66MHz clock change to split out). Canonical source = fork git history.
STATE: all priorities 1-5 done or Felipe-blocked. Chorus = shipped/validated/robust/documented 2nd
effect; reverb pristine. Remaining big work = the other send effects (blocked on the SPORT
channel->unit decode -- do NOT guess-feed) + the FLAG3/ping-pong frame model for the 4 gated records.
Two ear/HW items await Felipe (chorus CHORUS_WET level; reverb ON/OFF loudness) + the circular-wrap
OK. Tree clean, binary published.

## TICK 2026-07-12 ~00:35 — definitive unit map + chorus mix validated
- DEFINITIVE unit->record map (live PM signature match): u0=rec56 (audible panel-reverb slot),
  u4/u6=rec06 CHORUS (validates my chorus target), u8=rec34 EQ, u9=rec49. Resolves the long-standing
  unit0 confusion; the chorus feed is confirmed correct.
- rec06 chorus is WET-ONLY (traced: input->delay->modulated read->output, dry not re-added), so
  summing the chorus return with the main is structurally CORRECT -- no dry-doubling. Only CHORUS_WET
  (0.60) needs ear calibration (~69% modulation may be slightly high; Felipe's call).
NEXT effects (now that units are mapped): EQ (u8, rec34) is a master/insert (0dB flat by default,
needs the series-insert integration + user gains); SOUND DSP/MULTI need their send-channel->unit
mapping (0x8098/0x8298) which is not yet pinned -- do NOT guess-feed a unit (the unit-7 lesson).
Chorus is the solid, faithful, shipped non-reverb effect; reverb pristine; tree clean.

## TICK 2026-07-12 ~00:15 — chorus milestone documented (blog + docs)
Chorus wet decoupled from reverb depth (prior chunk). Published blog Part 19 "A second voice" (the
first audible non-reverb effect + the honest FLAG3 red-herring correction). Updated the docs site
kn7000-effects-dsp.md emulation-status (chorus audible via unit-4 send/return; multi/sound-DSP/EQ are
follow-ups; FLAG3 gates only 4/72 records). Jekyll rebuilt. posts.json=21.
NEXT (effects, future ticks): identify + feed the SOUND DSP unit (send 0x8098/0x80C8) and MULTI unit
(send 0x8298) the same way chorus was done; EQ (unit 8) is a master/insert (different integration);
calibrate CHORUS_WET + resolve dry-doubling (unit-4 out = dry+wet or wet-only) -- needs Felipe's ear.

## TICK 2026-07-12 ~00:05 — chorus wet DECOUPLED from reverb depth (refinement)
Fixed the shipped chorus's level coupling: the chorus return is now an INDEPENDENT wet added
post-crossfade (own CHORUS_WET level, follows gret but not gdepth), carried separately in the DSP
output ring. Reverb bit-identical off (A/B 0/2.11M); chorus-on re-verified (unit-4 250282, 69% LFO
modulation), now independent of reverb depth. REMAINING chorus refinements: calibrate CHORUS_WET vs
real balance (needs Felipe's ear); pick u4 vs u6 vs both from the send matrix; handle the dry-doubling
question (unit-4 output = dry+wet or wet-only?). NEXT effects to make audible (same feed mechanism):
identify SOUND DSP unit (send 0x8098/0x80C8) + MULTI unit (send 0x8298) + EQ (unit 8, master) and
feed them. FLAG3-gated 4 records = the deep ping-pong part.

## ★★★★ TICK 2026-07-11 ~23:55 — FIRST AUDIBLE NON-REVERB EFFECT: chorus works!
Caught + corrected a prior error (FLAG3 was overstated: only 4/72 records gate on it; chorus is
non-gated). DECISIVE TEST proved chorus units (4/6 = rec06) OUTPUT when fed. IMPLEMENTED audible
chorus (9a3c392): tonegen captures chorus send 0x8198; tick feeds unit-4 input (0xC36A = raw TG x
send) + sums unit-4 return (0xC34A) into the DAC; gated on send>0 so REVERB BIT-IDENTICAL off
(A/B 0/2.11M). VERIFIED enabled: send=63, unit-4 out 250282 (0 rail/clip), DAC shows chorus LFO
MODULATION (69% depth ~1Hz) = a real chorus. Reverb pristine. Opt-in (only when user enables chorus).
FIRST-CUT approximations (documented): whole-mix feed (not per-part); chorus return summed BEFORE the
reverb crossfade -> level couples to reverb depth/wet (decouple next); single unit u4 (u6 is a twin).
MECHANISM GENERALIZES: EQ (unit8, 0xC352/0xC372), multi, sound-DSP = feed their units the same way.
REMAINING (refinements, next ticks): (1) decouple chorus level from the reverb crossfade (sum as an
independent wet post-crossfade); (2) calibrate the chorus level + pick u4 vs u6 vs both from the send
matrix; (3) extend to EQ/multi/sound-DSP; (4) handle the 4 FLAG3-gated records (pitch-shift + extra
reverbs) via the FLAG3/ping-pong frame model (the genuinely deep part). Blog-worthy milestone.

## TICK 2026-07-11 ~23:25 — multi-unit effects: investigation CONCLUDED with implementation roadmap
Completed the FLAG3/kernel-routing decode and consolidated the whole multi-unit investigation into an
actionable IMPLEMENTATION ROADMAP (top of notes/effect-multi-unit-routing.md). FINAL PICTURE:
- The non-reverb effects are HELD DISABLED by the DSP FLAG3 input, which is a GLOBAL double-buffer
  handshake (kernel `8098: IF FLAG3_IN, MODIFY(I3,M3=-1)` + ASTAT ping-pong toggle 8099), NOT a
  per-effect enable. Our simplified one-frame-per-IRQ0 bridge is correct for the FLAG3-INDEPENDENT
  reverb but structurally can't run the gated effects (they live on the ping-pong phase we never run).
- Making them audible needs a FAITHFUL SPORT-DMA double-buffered frame model (drive FLAG3/ping-pong
  so all units run on the right phase) + per-effect send feeds (send matrix decoded) + return summing.
  Large, touches the working reverb's frame model -> SUPERVISED. Roadmap step 1 = decode what drives
  the FLAG3 pin (IC306 schematic + firmware).
- Reverb pristine (bit-identical), binary published, tree clean.

## ★ PROJECT STATE SUMMARY (2026-07-11 late)
Priorities 1-5 are DONE or blocked; the driver is in an excellent, stable state:
- Reverb: clean, robust (dense-input tested), all 8 types PASS, native-MAC DRC, bit-identical guard.
- Navigation: PAGE/CONTRAST fixed+verified; all effect types reachable.
- Effects sweep triaged; envelopes, wave pack, sound all shipped earlier.
- Docs + blog (Parts 1-18) current.
TWO ITEMS NEED FELIPE (both asked, pending): (1) OK to apply the TRM-correct circular-wrap fix
(2-sample inaudible reverb change, catalogue C.1, ready)? (2) real-HW reverb ON/OFF loudness ratio.
ONE BIG FEATURE scoped for a supervised session: audible chorus/EQ/multi/sound-DSP (the FLAG3/SPORT
frame model, roadmap above).
Remaining autonomous-safe polish if future ticks want work: upstream-submit the SHARC catalogue;
per-model doc passes; minor verification. No further risky/unsupervised changes to the DSP audio path.

## TICK 2026-07-11 ~23:10 — multi-unit routing: FLAG3-gate root cause found (kernel-routing decode)
Advanced the kernel-routing half of the multi-unit puzzle (static decode + live/experiment). FINDINGS:
- All 10 unit CALL slots ARE patched + run every frame (confirmed live PM 0x8080-0x80A0); units aren't
  dormant at the CALL level.
- ★ ROOT CAUSE of silent effects: the chorus program (rec58) and 4 others open with
  'IF NOT FLAG3_IN, JUMP skip' -- they gate on the SHARC FLAG3 INPUT pin. rec49 reverb / rec56
  enhancer do NOT, so they always run (why reverb is audible). MAME models flag[3]+set_flag_input()
  but the driver NEVER drives DSP FLAG3 -> stays 0 -> gated effects permanently skip -> silent.
- Experiment (forcing FLAG3=1) REFINED it: FLAG3 also feeds the kernel mainloop
  (8098: IF FLAG3_IN, MODIFY(I3,M3)) so forcing it constant CHANGED the reverb WAV. FLAG3 is a GLOBAL
  per-frame signal, not a clean per-effect enable. Reverted; reverb bit-identical.
NET: the effects aren't mis-routed -- they're HELD DISABLED at the DSP FLAG3 gate, which is unmodeled
AND globally woven into the frame loop. NEXT (deeper, supervised): decode the full FLAG3 protocol
(what drives the pin, when -- likely tied to the ping-pong ASTAT toggle 0x8099 -- and the CPU control
source), then drive set_flag_input(3,...) faithfully + feed the unit sends. Full decode in
notes/effect-multi-unit-routing.md. Reverb pristine, binary published.

## TICK 2026-07-11 ~22:55 — multi-unit routing: send matrix DECODED, kernel-routing blocker found
Pursued the BIG win (audible chorus/EQ/DSP) via wf_ff73662f-062. RESULT: decoded the effect-send
matrix fully (CHORUS send = 0x8198, low byte = per-part depth; enable recipe live-verified incl. the
SOUND-DSP-forces-block-refresh firmware quirk) and implemented a SAFE unit-7 feed. A/B guard PASSED
(reverb bit-identical with chorus off, 0/2.11M). BUT hit the real blocker: feeding unit-7's input
slot makes its input nonzero (306484) yet the unit produces NO output -- a scan of ALL return slots
showed ONLY unit 0 (reverb) outputs. So the kernel's per-frame routing is NOT a fixed slot map; the
firmware configures which unit is wired into the audio path internally, and only unit 0 is live.
Multi-unit audibility needs the KERNEL-ROUTING decode (how the firmware programs each unit's I/O
pointers + what makes unit 7 join the active chain), not just an input feed. REVERTED the incomplete
audible path (dead DSP writes, no benefit); reverb pristine (bit-identical, republished). Full decode
+ blocker in notes/effect-multi-unit-routing.md.
STATUS: all of priorities 1-5 done or Felipe-blocked. Big win is 50% done (send matrix) with the
kernel-routing half scoped as the next (deeper, best-supervised) step. Tree clean, binary published.
QUESTIONS FOR FELIPE (both pending): (1) OK to apply the TRM-correct circular-wrap fix (2-sample
inaudible reverb change)? (2) real-HW reverb ON/OFF loudness ratio for calibration?

## TICK 2026-07-11 ~22:05 — pursuing the BIG win: multi-unit routing (audible chorus/EQ/DSP)
Mandate = keep improving, don't wait for approval. Attacking the last substantive gap SAFELY (reverb
path stays untouched; any new unit path must leave the reverb WAV BIT-IDENTICAL with its effect off).
- Launched wf_ff73662f-062 (RE + live) to decode: which group-0x20 register is the chorus/DSP SEND
  (vs the known reverb send 0x80B8 / depth 0x8338 / wet-dry 0x803A), how a channel routes to a unit,
  and the PANEL recipe that makes a nonzero chorus send (unit 7 currently gets ZERO input in all
  states reached so far).
- Integration point confirmed: dsp_audio_tick (kn7000.cpp) feeds unit-0 in (0xC362) + reads unit-0
  return (0xC342). A chorus path = additionally feed unit-7 in (0xC370) + sum unit-7 return (0xC350).
  BLOCKER to resolve: the tonegen produces ONE mixed stream (no per-part/per-bus separation), so
  feeding unit 7 faithfully needs either the send-matrix decode (per-channel chorus send) or a
  clearly-labeled whole-stream approximation.
- A/B GUARD READY: reverb-isolation baseline /tmp/ab_before.wav (md5 0787b60c...) still matches the
  published binary. Rule: implement multi-unit ONLY if the reverb WAV stays bit-identical with the
  new effect off; else revert + document the decode.
Next: on workflow return, implement if clean+safe, else bank the decode for a supervised session.

## TICK 2026-07-11 ~21:50 — documentation milestone + 0x8238 decode
- 0x8238 DECODED (priority 4 item CLOSED): it's a CONSTANT (0x0800), not a depth control -- stepping
  TOTAL DEPTH moves only 0x8338's low byte (0x8550<->854D); 0x8238 is the reverb-send channel's fixed
  output-bus base, co-written but invariant. Depth model (0x8338 -> m_gain_depth) is complete.
- BLOG Part 18 "The buttons that lied" published (PAGE/CONTRAST were mislabeled pseudo-part rockers;
  the detective story + live proof). posts.json = 20 entries.
- DOCS site updated + rebuilt (Jekyll OK): kn7000-control-panel.md gets the PAGE/CONTRAST emulation
  mapping table (pseudo-part 0x18/0x1D -> SEG0B/SEG05); kn7000-effects-dsp.md gets the audible-effects
  status (single send+return path -> only reverb audible; multi-unit model scoped).
REMAINING QUEUE (for next ticks): multi-unit send/return model (the BIG win: audible chorus/EQ/DSP;
needs per-bus TG output + multi-send bridge; multi-day, best supervised given risk to the working
reverb); loudness ON/OFF calibration (needs Felipe's real-HW ear ref); circular-wrap re-apply
(awaiting Felipe's OK -- 2-sample reverb change); upstream submission of the SHARC catalogue.
STATE: reverb clean+robust; navigation complete; native MAC bit-identical; all priorities 1-5 either
done or blocked on Felipe (loudness ear-ref, circular-wrap OK). Tree clean, binary published.

## TICK 2026-07-11 ~21:35 — robustness PASS; nav complete; circular-wrap verified-but-held
- LOUD-INPUT RAIL RECHECK (priority 4): PASS. 18-note cluster slammed + held 3s w/ reverb ON ->
  0 near-rail DSP writes / 617,400 (0.00%), DAC peak 2085, 0 clipped samples, clean tail. Reverb is
  production-robust under dense/loud play (not just single notes).
- NAVIGATION COMPLETE: the PAGE rocker fix (SEG0B, last tick) IS the within-group TYPE page control
  (live-verified: MULTI EFFECT PAGE walks a group's type pages, Cross Delay -> Shallow1-16/Normal
  1-16). Sweep's "unfound type-page control" was wrong-button. Group cursor SEG09 + PAGE rocker SEG0B
  = ALL effect types reachable. Both open items closed in notes/effects-sweep-results.md.
- CIRCULAR-WRAP FIX (priority 5): applied to both engines, built, A/B'd -> changes reverb by 2
  samples/2.11M (delay lines DO hit the boundary; RE's "unchanged" was wrong). TRM-correct but
  modifies the user-praised reverb -> REVERTED, held for Felipe's OK (rule g). Ready to re-apply
  (catalogue C.1). Reverb binary unchanged (bit-identical to reference).
REMAINING QUEUE: multi-unit send/return model (makes chorus/EQ/DSP audible -- BIG win, needs per-bus
TG output + multi-send bridge; multi-day); loudness ON/OFF calibration (needs Felipe's ear ref);
0x8238 decode; circular-wrap re-apply (awaiting OK); upstream submission.
QUESTION FOR FELIPE: OK to apply the TRM-correct circular-buffer wrap fix? It's a 2-sample
(inaudible) change to the reverb but the spec-correct behavior.

## TICK 2026-07-11 ~21:25 — chorus triaged (single-path limit); native DRC MAC shipped (bit-identical)
PRIORITY 1 (chorus SUSPECT) RESOLVED as EXPLAINED not a bug: live taps prove only unit 0 gets
signal; chorus(u7)/EQ(u8)/u9 get ZERO input even with CHORUS toggled ON. Our bridge models ONE
send (TG->u0 input 0xC362) + ONE return (u0 0xC342); real HW routes per-part sends to multiple
units via the TG group-0x20 matrix (fully captured, 64ch x 0x10) and sums all returns. Making
chorus/EQ/DSP audible = scoped multi-unit send/return model (notes/effect-multi-unit-routing.md;
deferred, multi-day). Reverb (unit 0) is faithful. Sweep CHORUS/EQ/DSP reclassified EXPLAINED.
PRIORITY 3 (DRC MAC-native) DONE: implemented native UML for the fixed MAC family (multiop
0x06/0x08-0x16 = MRF+-Rx*Ry SSF/SSFR + parallel add/sub/avg), removing the per-op interpreter
fallback in the effect hot path. **BIT-IDENTICAL reverb WAV (md5 match, 0/2.11M samples differ)** —
proven equal to the interpreter. Flags gated on liveness; ALUSAT baked. -str ~75% (30s); host too
noisy (58-81% same binary) to quantify the gain. Upstream catalogue D marked DONE.
REMAINING QUEUE: multi-unit send/return model (makes chorus/EQ/DSP audible — the big effect win);
within-group TYPE page-flip control (unfound); complete MULTI/SOUND-DSP batch health tests;
loudness calibration + 0x8238; apply the safe circular-wrap fix (catalogue C.1) with A/B; upstream.

## ★ TICK 2026-07-11 ~21:05 — PAGE/CONTRAST FIXED + VERIFIED; effects-sweep triaged
PAGE Up/Down and CONTRAST Up/Down SOLVED (wf_86ccde00-860 RE + live verify) and shipped (f614862):
they are pseudo-part events in the ordinary 0x2000/0x2001 family, NOT the SEG16/17 valuator wires
the guesses used. **PAGE = SEG0B 0x10 (up) / 0x20 (down)** (was mislabeled BASS ON/OFF);
**CONTRAST = SEG05 0x04 (+) / 0x08 (-)** (was PADS ON/OFF). LIVE-VERIFIED: MULTI EFFECT walks
6/8->7->8->7->6->5, both directions, title unchanged. Layout artwork repointed; wrong SEG16/17/19/1A
guess bits -> IPT_UNUSED (valuator wires). My earlier brute-force MISSED this because it skipped
SEG00-0x0B. (A synchronous RE agent wrongly concluded "undumped scanner, unmappable" -- it used the
wrong dispatch table; the workflow agent's concrete dispatch-row evidence was right and verified.)
EFFECTS SWEEP (wf_46aaaf77-352) triaged -> notes/effects-sweep-results.md + notes/
effect-selection-recipes.json (224 recipes): ALL 8 REVERB TYPES PASS (distinct tails, 0 clip, 0 rail,
decay to zero). CHORUS = no audible effect (SUSPECT: likely RIGHT1 chorus send=0 by default OR
return unwired -- investigate). MULTI/SOUND-DSP batch tests incomplete (OOM); re-run needed.
REMAINING QUEUE: chorus send/return check; within-group TYPE page-flip control (unfound); complete
MULTI/SOUND-DSP batch health tests; DRC MAC-native perf; loudness calibration; upstream prep.
LESSON: background workflows DO survive across cron-tick turns (both orphaned workflows completed
detached) -- check journals on each tick before re-running.

## TICK 2026-07-11 ~20:35 — PAGE/CONTRAST: guesses DISPROVEN live; shared up/down pair; RE in progress
EMPIRICAL (live probe, MULTI EFFECT screen stuck at PAGE 6/8, 128-candidate brute-force w/ PNG
page-digit diff): the current driver guesses (SEG16 0x01 PAGE UP, SEG17 0x01 PAGE DOWN) DO NOT page
-- proven wrong. No tested normSeg (0x0C-0x1A,0x20 × all 8 bits) pages while staying on MULTI EFFECT.
KEY INSIGHT: the HELP button-name legend (table 0x48394d06, null-sep, indexed by button id) has
"LCD CONTRAST" (idx 62) but NO "PAGE UP/DOWN" entry -> PAGE Up/Down and Contrast Up/Down are the SAME
physical up/down pair (manual: "use the Contrast Up/Down buttons or Tempo/Program wheel"); pressing
LCD CONTRAST re-purposes them. So find ONE up/down pair. Candidates nS16(ev1005)/nS17(ev1004,t=4
auto-repeat) via wire 0xD0/0xD1 may be DIAL/ENCODER deltas not bit presses (my bit-press didn't
page). NEXT: RE the "PAGE %d/%d" render var + its writer + the DATA/DIAL wire protocol (wires
0xD0-0xD3) to name the true button/event; then live-verify + fix driver + layout. Do NOT ship a new
guess (rule g). MULTI screen open recipe VERIFIED: hold :SEG10 0x04 ~2.5s.

## TICK 2026-07-11 ~20:10 — PAGE/CONTRAST investigation launched; upstream catalogue banked
- Effects sweep wf_46aaaf77-352 did NOT complete (died with prior session; journal shows only
  'started', no recipes). Deferred: re-run AFTER PAGE nav is fixed (MULTI's 8 pages need it).
- ★ PAGE/CONTRAST: launched wf_86ccde00-860 (RE agent finds true events from panel-function
  descriptor table 0x48603758 + string pool -> normSeg.bit; live agent verifies by watching the
  "PAGE n/m" indicator on snapshots). Current driver has GUESSES: SEG16/17 PAGE, SEG19/1A CONTRAST.
  When it returns: fix the driver ports (faithful, no guesses), rebuild, publish, commit.
- Priority 5 (upstream prep): wrote notes/sharc-upstream-patch-series.md — ALUSAT (applied, HIGH),
  circular-wrap off-by-one + premod + AVG/SSFR rounding + FIX UB (identified, need MAME A/B), MAC
  multiop perf. NOT applying the circular-wrap fix yet (touches reverb delay lines -> needs a MAME
  A/B, which would contend with the running workflow's MAME phase; do it in a dedicated tick).
- DRC MAC-native (priority 3): confirmed the fixed-MAC multiop cases 0x06/0x08-0x12/0x14-0x16 fall
  back to generate_unimplemented_compute (interpreter call) in the frame hot path; the reverb's sine
  oscillators use them. Deferred (correctness-critical; needs interpreter-A/B), do in a focused tick.

## ★★★ AUTONOMOUS MANDATE 2026-07-11 EVENING (Felipe away many hours; cron 529b597d every 23min)
GREEN LIGHT standing. Queue (in order):
1. EFFECTS SWEEP TRIAGE: workflow wf_46aaaf77-352 (running at handoff) = navigator recipes +
   batched health tests over many effect types (REVERB 8 types, CHORUS 4, MULTI pages, SOUND DSP 8).
   Read results from the session workflow journal; fix every FAIL/SUSPECT; re-verify; publish.
2. ★ PAGE UP/DOWN buttons WRONGLY MAPPED (Felipe: some nav screens inaccessible). Find real bank-A
   events; live-verify on a paged screen (MULTI EFFECT "PAGE n/8" indicator on snapshots). Then
   CONTRAST Up/Down (events unknown; old guesses in the driver were never confirmed — panel notes
   0x20B5-0x20BD cluster SEG1D-1F). Fix driver ports + layout; commit.
3. DRC PERF: native UML for the multifunction MRF-MAC block (multiop 0x06/0x08-0x16) — the
   remaining interpreter-fallback in the frame hot path. A/B a reverb WAV vs interpreter for
   correctness; measure speed. (ALUSAT specialization + 66MHz landed: kernel = 44100 frames/s.)
4. Reverb ON/OFF loudness question (~-5dB at depth 0x50 — needs real-HW ear ref, ask Felipe when
   back), 0x8238 decode, loud-input rail recheck.
5. Upstream-prep SHARC patch series (ALUSAT both commits, circ-wrap, premod wrap, AVG/SSFR
   rounding, FIX UB).
DONE THIS EVENING: reverb CLEAN end-to-end (sign-extension + TDM wiring); TOTAL DEPTH wired; DRC
ALUSAT complete + specialized; 66MHz; kernel 44100 fps; blog Part 17; docs site updated (Jekyll
gotcha: use JEKYLL_NO_BUNDLER_REQUIRE=true).

## ★★★★★★ 2026-07-11m: REVERB IS CLEAN — sign-extension poison + true send/return wiring (SHIPPED)
The 'reverb-ON noise' saga is RESOLVED (wf_b58b1fda-df3 + this commit):
1. THE POISON: dsp_audio_tick wrote TG input zero-filled (&0xffffff) but the kernel programs SPORTs
   DTYPE=01 = SIGN-EXTENDED (SPCTL 0x013CB173, TRM ch9) → every negative sample = +2×FS rectified
   pedestal → every unit's own output CLIP railed (u6 chorus ×2 makeup first, PC 0x8A4E). Explains
   ALL 'input-independent rail' history. Fix: write sign-extended words. 400,415 rails → 0.
2. THE WIRING: no TX slot feeds a DAC — all 4 SPORT TX pins loop into the TG (SDIE0-3); the TG mixes
   direct + returns (our 0x803A/0x8338 crossfade model was structurally right!) into its own DAC
   out. TX frame = per-unit I/O map: u0 C342/43 (in C362/63), u1 C344/45, u2 C346/47, u3 C348/49,
   u4 C34A/4B, u5 C34C/4D, u6 C358/59, u7 C350/51, u8 C352/53, u9 C356/57. TG send → u0 input;
   crossfade return = u0 return. I4-following heuristic RETIRED (it parked on u6 = fed the chorus,
   listened to the chorus).
VERIFIED: rev ON = clean pitched audio (harmonic/noise 22.8×), idle silent, smooth tail → digital 0,
no clip; dry + toggle unchanged. FOLLOW-UPS: (a) kernel frame overrun ~21.4k/44.1k frames (pace IRQ0
to kernel completion or raise SHARC clock — wet path currently effectively half-rate); (b) ON/OFF
loudness calibration (ON ≈ −5dB vs dry at depth 0x50; needs real-HW reference — Felipe's ear);
(c) loud-input rail re-check post-rewire; (d) DRC ALUSAT perf reclaim (translation-time
specialization); (e) upstream the SHARC fix catalogue.

## ★ 2026-07-11l: "STILL NOISY" (Felipe) — ROOT SHARPENED: unit6 (rec06 @0x8A00) rails the TDM bus
CORRECTION to the 11k optimism: the ALUSAT completion made DRC == interpreter, but BOTH still emit
clipped garbage when reverb is ON: the audible signal = the RAILED [I4] slot x depth x master (14.8k
= 8388607x0.63x0.64x32767/8388607-ish); the "smooth tail" was the CLIP DUTY CYCLE decaying, not
clean audio. Probes (all -nodrc, taps + PC capture):
- The SPORT TX frame 0xC342-0xC359 is a MULTICHANNEL TDM frame (every slot written once/frame by a
  kernel copy loop); nearly every slot rails during a note. The RX/staging region 0xC362-0xC379
  carries SANE note-correlated decaying levels (27k-924k) -> input side is fine.
- 0xC350/1 always zero; 0xC344/5 never rail but don't silence post-note; 0xC34B sane during note.
- ★ FIRST RAILED WRITER (unanimous, 30/30 samples): **PC 0x8A4E = UNIT 6 = rec06 relocated to PM
  0x8A00, writing slot 0xC359** -- rails from note start. Unit4 is also rec06 (0x8800). One unit
  poisons the bus; the chain inherits.
NEXT SESSION (precise): (1) disassemble rec06 at offset ~0x4E (listing rec06_*.asm, base-relative)
+ dump unit6's compiled DM params (0xC000+6*0x4D=0xC1CE.., 0x9800+6*0x50=0x99E0..) -- why does its
output stage rail at sane input? (compiled param wrong/missing for THIS unit? a code op still
misbehaving? which bus slot does it READ -- maybe a railed slot from C342/3?). (2) Decode the
kernel's SPORT0 TX MULTICHANNEL config (boot-init IOP writes incl. the 0xA000-0xA008/0xB000-0xB00E
global block) to learn WHICH TX slot pair feeds the real main DAC -- then repoint the bridge from
I4-following to the true DAC slots permanently. (3) After unit6 is understood, re-judge levels.

## ★★★★★ 2026-07-11k: ALUSAT COMPLETE — REAL REVERB AT FULL DRC SPEED (shipped)
Extended the ALUSAT clamp to EVERY native DRC integer ALU form (ADDC/SUBB 0x05/06, NEG 0x22, CI
forms 0x25/26, INC/DEC 0x29/2a, dual add/sub 0x78-7F both halves) via shared helper
generate_fixed_alusat_tail (I6=wrapped, I7=V captured live, clamp SAR^0x80000000, AN/AZ fixed;
dual form skips per-half flag micro-corrections). DRC now matches the interpreter reverb
sample-for-sample through the audible tail; smooth exponential decay; no rail; no hard cut; dry
1731 untouched; toggle clean. Felipe's loud-distortion report RESOLVED. FOLLOW-UPS: (1) DRC perf
dropped 76%->56% in -str boot metric (per-add MODE1 test) -- optimize by specializing ALUSAT at
translation time + cache flush on MODE1 change (machinery exists: cache_dirty); (2) absolute level
judgment: reverb-ON note = ~8.6x dry (14.8k vs 1731) -- determine the real hardware ON/OFF loudness
ratio (0x803A/0x8338/0x8238 semantics; 0x8238=0x0800 per depth step still undecoded); (3) upstream
the SHARC fixes (ALUSAT family, circ-wrap off-by-one, premod wrap, AVG/SSFR rounding, FIX UB).

## ★★ 2026-07-11j DISCRIMINATOR RESULT: -nodrc = REAL REVERB (smooth exponential tail!) — DRC-gap theory PROVEN
Interpreter run (reverb ON default, C4 1s): pre-note 0; note 14901 (not DAC-railed); tail rms
5420→5058→5542→3164→180→3 over 3.5s = a genuine smooth reverb decay, NO hard cut. The remaining
loud-distortion + rail + 1.2s hard-cut are DRC-ONLY: the un-saturated DRC integer forms. EXACT FIX
LIST for next session (mechanical): extend the ALUSAT clamp (pattern from 2d308c7) to DRC cases
0x05 (ADDC) / 0x06 (SUBB), the dual add/sub compute form, and audit any other native DRC integer
ALU emissions (grep UML_ADD/UML_SUB in generate_compute) — interpreter is the reference (fully
saturating). THEN re-measure levels: interpreter note is still ~8.6x dry (14901 vs 1731) — decide
whether that's the correct hardware ratio (return 0.63 x chain makeup) or needs the TG-return
semantics refined (0x803A pair vs 0x8338 vs 0x8238 roles). WORKAROUND available today: -nodrc plays
real reverb at ~36-50% speed.

## ★★★★ 2026-07-11h: THE EFFECT-CHAIN DIVERGENCE IS FIXED (2d308c7) — MODE1 ALUSAT in the DRC
Root cause of the 6-session reverb-wash saga: kernel sets MODE1 ALUSAT (BIT SET 0x3000 @PM 0x8074;
old listing mis-read it as NESTM — NESTM is 0x800). rec49-family triangle LFOs = saturating add +
IF-AV reflect; MAME's DRC did wrapping UML_ADD/SUB with zero ALUSAT support → each LFO became a
permanent ±2^31 two-sample rail bounce (onsets 0.216/0.648/1.080s, free-running, input-independent)
thrashing the delay taps at fs/2 = the never-decaying garbage. Interpreter was already correct
(hence idle-clean interp observations); fixed the DRC add/sub (temp + COND_V capture + clamp
SAR^0x80000000 + AN/AZ correction) and the fork's MAC-block parallel adds. ELIMINATED en route:
corrupted uploads (49,269 writes replayed bit-exact — wf_c6d2e140-eec), 40-bit-precision hypothesis
(all recursions float32-stable — wf_08fbdf6e-df9), idle LFO drift (stable ±0.64%/272k ticks).
VERIFIED: idle boot silent forever; reverb-ON tails decay to digital zero (+2s); toggle + dry
unchanged; DRC ~76%. REMAINING POLISH (new, smaller): (1) gain staging hot → clips during held
notes (suspect: dropped host mixer indices 0x43/0x4B 'level triplets' = wet/return levels never
reach the kernel?); (2) tail ends in a HARD CUT ~1.2s post-release, not exponential (suspect: a
dynamics/gate unit in the chain, or the unit0 frame countdown 0x34AE8; investigate). Upstream-worthy
catalogue: this ALUSAT fix + circ-wrap off-by-one + premod-no-wrap + AVG/SSFR rounding + FIX
overflow UB (notes/dsp-effect-execution-chain.md).

## ★★★ 2026-07-11f: REVERB TOGGLE WORKS AUDIBLY (TG bus routing modeled)
Felipe's reverb-toggle request: inspection (wf_870ba134-582) proved the toggle was NEVER broken in
firmware/UI/LED (flag 0x500C0758 bit9, cpr_led27, hold->REVERB screen all work); the missing piece
was the TG OUTPUT-BUS/EFFECT-SEND hardware model (toggle = 7 sub-TG group-0x20 writes: ch3 regA
007F<->7F00 [direct|dsp-return] DAC pair, chB reg8 send 0x66<->0; NOT a DSP host-port op). ALSO
CORRECTED: *(0x500A01E0)=-1 is NORMAL idle; the DspEffectSelect pipeline RUNS today (74 index +158
data writes on sound select). SHIPPED: tonegen group-0x20 capture + routing gains; bridge send-scale
+ DAC crossfade. VERIFIED (DSPAUDIO=On): toggle OFF instantly mutes the wash + notes play clean dry
direct; ON returns through the DSP. Set DSPAUDIO=On (Machine Configuration) to hear it; default
stays Bypassed until the parked SHARC divergence is fixed (then flip default).

## ★★★ 2026-07-11c: DONOR-SAMPLE WAVE PACK SHIPPED — real timbres replace the sine
Felipe's request (better placeholder wave ROM) DONE end-to-end (workflow wf_44d926b3-dd3 + commit):
- RESEARCH: (1) runtime sample select DECODED = aux word bank(13:12)+zone(7:0), pitch is zone-relative
  0x400/semi, NO addresses cross the bus (TG has an in-ROM directory, format unknown, not needed for
  MAME); 0x80xx quad = mixer record (refuted as address); channel decode = 64 ch x 0x10. (2) JK tone
  tables fully mapped: 1139 named sounds, layer wave selector {group,sub} at layer+0x04, 856 NAMED
  physical waves @JK+0x1B8EF. (3) KN5000 donors: ONLY IC307 is genuine (ic304-6 in kn5000_original_roms
  are the KN5000 project's own synthetic banks -- provenance flag raised); 186 waves extracted
  (tools/extract_kn5000_waves.py) with pitch/loop manifest.
- SHIPPED: tools/make_wave_pack.py + wave_pack_map.json -> kn7000_waves_synthetic.rom (16MB, magic
  KN7WVSY2, provenance block, normalized donors, crossfaded tail loops; in kn7000-emulator/roms/kn7000/).
  Driver: optional ROM region "wavepack" (BAD_DUMP hashes; update via tool output); tonegen resolves
  (bank,zone) at note-on -> donor PCM, linear interp, loop, step=freq/root; sine fallback.
- VERIFIED: piano/organ/guitar real harmonic spectra at correct pitch; envelopes/life-cycles unchanged.
- LIMITS (honest): 14 zone ranges = the captured family anchors; other sounds -> sine fallback. One
  donor per family stretched across the keybed (no multisample). Root pitches are autocorrelation
  estimates (possible octave errors, e.g. mallet w74 -- fix by editing wave_pack_map.json + rebuild).
  Drums unmapped. Full notes: notes/wave-select-decode-and-donor-plan.md.

## ★★★ 2026-07-11b: ENVELOPE LIFE-CYCLE CLASSES SHIPPED (2089290) — Felipe's requested refinement
All 11 sound families now have correct note life-cycles (WAV-verified). Three classes at note-on:
GATE_FOLLOW (aux 0x1C02-word bit15; brass/sax/organ — the sub TG hosts the keybed FIFO and key-gates
them itself; driver couples kbd_push make/break → tonegen key_context/key_break), MANAGED (firmware
record type rec+0x02&0x7C in {04,08,10,20,40} → hold at SUS1 until the firmware's computed 6-write
burst), ONESHOT (pluck classes → held decay continues to 0). Plus dies-shape (nonzero r9/rA lows,
24/24 sweep-validated): held piano/bass fade like real instruments. Grounded by workflow
wf_c8e2bf8d-0c1 (11-family sweep 2x + key-off RE: emitter lib 0x4C0376E3, values computed from tone
data *(rec+0x3C) via curves 0x486D2649/13; skip = type dispatch 0x4C004295/0x4C036D3F). Details:
notes/tg-envelope-implementation-plan.md tail.

## ★★★ RESOLVED 2026-07-11: the forever-note + no-dry-sound (Felipe's report) — SHIPPED (a53fdcb)
Root causes (all proven + fixed; full detail notes/tg-envelope-implementation-plan.md tail):
1. **TG release NEVER fired**: the firmware does NOT write 0x0001=0xC000 at key release (boot/steal
   only -- FALSIFIES the Part-14 claim). Real release = 6-write ramp rewrite to the note's ODD
   companion block (+0x10=0x9180 +0x11=0x9100 +0x14/15=0xAE00 +0x18/19=0x22B0), targeted at the odd
   block even for single-voice notes. FIX: reg0 rewrite (hi<0xFF) releases gated pair members gated
   >20ms. Notes now decay-to-sustain and release to true silence on PC-key AND MIDI paths (verified).
2. **No dry path existed**: speakers heard ONLY the DSP, whose boot-default effect diverges (rails)
   after any note; no panel button reaches the DSP (effect OFF = DspEffectSelect(unit,0) THROUGH
   record via the DEAD 0x500A01E0/mailbox/task-7 path -- firmware-RE confirmed). FIX: new machine
   config "Effects DSP audio path (EXPERIMENTAL)", default BYPASSED (dry TG) -- flip to route through
   the DSP (the old wash behavior, verified both ways). DSP still boots/runs regardless.
3. Extras: note-on now requires a programmed EG (kills boot-sweep junk voices audible on the dry
   path); keybed FIFO 16->64; comment lies fixed. Blog Part 14 erratum published (mame-blog).
KNOWN LIMITATION: plucked sounds (guitar family) get NO key-up write from the firmware (natural-decay
samples); placeholder holds their sustaining layer at SUS1 forever. NEXT RE: the 7-stage chain
(DCY2->SUS2 continuation; guitar layer B r7=7F00 SUS2=3FF1 data captured).
LUA GOTCHA (add to every future script): manager.machine.time.seconds is INTEGER seconds; use
seconds + attoseconds/1e18. This masqueraded as a phantom "+1s WAV offset" all session.
Firmware-RE bonus (workflow agent, static): full DSP-driver module map -- UI setters fill param block
*(0x500A01E0) (lazy-alloc from RTOS mailbox 5), commit 0x48405B27 -> mailbox 6 -> RTOS task 7
(0x48405B97) does ALL host-port writes via HAL 0x48404E8D call sites 0x48404F11/0x48404F5E; effect
records live in RAM table 0x500066E0 (ROM 0x487B7248 is its .data init image; explains zero code refs);
"OFF" = type 0 = a real 60-byte THROUGH record (ROM 0x486BEBA9). The whole effect-select UI depends on
the dead param path => reverb on/off CANNOT work in the current boot state (separate from the parked
divergence bug).

## ★★ FELIPE IS BACK (2026-07-11) — cron loop STOPPED; new directed task
Felipe returned, cron b9660922 cancelled. His report from hands-on testing of the published binary:
(1) a single MIDI-controller note sounds FOREVER; (2) turning reverb off makes NO difference. He wants
the effect enable/disable mechanism checked and a genuinely DRY sound path to validate the ADSR
envelope by ear. Investigation running (workflow wf_1cc23600-247): live repro matrix (KEYS1 vs MIDI
file, wash measurement, REVERB-OFF probing) + firmware OFF-path static RE + driver audit. Prime
suspects: the BOOT-DEFAULT DSP effect washes forever like Dark2 (so any note -> everlasting output),
and/or effect-OFF never reaches the DSP. Note: kbd_midi_rx parsing verified correct by inspection
(handles running status + vel-0 note-offs; though its 'clamped into range' comment lies -- out-of-range
notes are DROPPED).

## ★ SESSION 2026-07-11p-s — reverb: all components verified; it's a ~1% loop-gain problem (PARKED)
More reverb diagnosis (no rebuilds -- Lua PM-patching + disasm). Key results:
- CORRECTED the "6.4s delay" lead: the reverb builds up in ~0.4s, so its delays are SHORT (~60ms); the
  build-to-2e7 is normal resonant gain (input x Q). The real bug is narrow: it DOESN'T DECAY after
  note-off (loop gain >= 1 despite every coefficient < 1).
- Verified MORE components correct: the 10-section CALL(DB) chain + delay-slot MODIFY(I6) timing, and
  MAME's delayed-branch pipeline. So ALL per-instruction components are now verified correct.
- SECTION-MUTING (Lua NOP of section CALLs): muting ANY section stops the rail but SILENCES the reverb
  (series chain) -> the divergence is a GLOBAL TANK LOOP through all 10 sections with gain ~= 1.0, not
  one bad section.
- CONCLUSION: this is a "loop gain 0.99 vs 1.0" problem (a long "Dark2" reverb MAME tips over unity). It
  needs a DIFFERENTIAL REFERENCE (a 2nd known-good ADSP-2106x running the same code+inputs) to see the
  ~1% per-frame drift. Single-CPU instrumentation is exhausted. **The reverb divergence is now PARKED.**
- RECOMMENDATION (next effects work): (a) test OTHER effect types (chorus/EQ/distortion/delay) that
  lack the near-unity feedback loop -- if those process correctly + stably, the effects DSP is largely
  functional and only long reverbs are affected (a big partial win); or (b) build the reference-diff
  harness. Full detail: notes/dsp-effect-execution-chain.md sections 2026-07-11p..s.
- No shipped change (all diagnostic). DRY passthrough correct; default boot clean.

## ★ SESSION 2026-07-11l-o — reverb characterized to the limit of incremental instrumentation
Deep core-instrumentation session (all reverted; tree clean; binary republished). Progress on the reverb:
- The "divergence" is a large signal (~2e7 = input x Q) that SUSTAINS (doesn't decay), NOT exponential.
  Magnitude-INDEPENDENT (a 50 ms blip sustains the same DC as a 2 s note) -> RULES OUT float precision.
- CLEARED as the accumulator: DM coefficients (all damped), the float ops (exact), PM(I8)@0x9800 (holds
  COEFFICIENTS not state), DM 0xC1xx (a descriptor TABLE), the circular-wrap off-by-one, the MODIFY
  instruction (audited -- correct).
- FULL-FRAME DM(I6) TRACE: every SDRAM tap does WRITE at X then READ at X-1, and X-1 is overwritten next
  frame -> each tap's delay is ~L6/rate = **~6.4 s (the full buffer)**. A reverb needs ms delays; ~6.4 s
  for every tap = a frozen, non-decaying wash = EXACTLY the symptom. So the LEADING root cause is now:
  MAME produces the WRONG (full-buffer) delay length for the reverb taps. The buffer SCROLL (1/frame) is
  managed by the DSP kernel's OUTER loop (the reverb subroutine saves/restores I6 at 0x8401/0x8402/
  0x846c/0x846e); MODIFY(I6,+0x10747) at frame entry is correct. So if the delays are wrong it's in the
  outer-loop I6 management or a DAG subtlety MAME runs differently than the ADSP-21065L.
- HONEST ASSESSMENT: 4 sessions of incremental instrumentation have CHARACTERIZED this thoroughly but
  not fixed it. The efficient path forward is a REFERENCE-DIFF: run the same reverb microprogram on a
  known-good ADSP-2106x model (or hand-simulate one frame) and diff MAME's I6 trajectory / the delayed
  values frame-by-frame -- that pinpoints the exact addressing divergence. Incremental core-tracing has
  hit diminishing returns. Full detail: notes/dsp-effect-execution-chain.md sections 2026-07-11l..o.
- Effects remain audible-but-not-faithful; the DRY passthrough is correct; default boot is the clean dry
  sound (divergence only if a user selects a reverb). No shipped change (all diagnostic).

## ★ SESSION 2026-07-11k — reverb paradox pinned + blog Part 15 (honest correction of Part 13)
- Instrumented the global TANK recirculation gain (`F10 = F10 * F9`, PM 0x844a): F9 = -0.280 CONSTANT
  (damped). So EVERY gain in the reverb is |<1| (allpass -0.618, tank -0.28, all coeffs damped), the
  float ops are exact, the structure is a correct Dattorro/Gardner nested all-pass -- yet F1 diverges.
  A linear system of sub-unity gains is UNCONDITIONALLY STABLE, so the energy must come from the
  DELAY-LINE management (reads landing on wrong slots in the single shared 284,400-word circular SDRAM
  buffer). That is now the sole remaining hypothesis; the definitive next step is a full-frame trace of
  every DM(I6) read/write ADDRESS, checking each read returns the sample written the right # of steps
  earlier. Details: notes/dsp-effect-execution-chain.md section 2026-07-11k.
- INTEGRITY: blog Part 13 over-claimed ("the reverb is audible... stable, not a runaway"). Wrote
  mame-blog Part 15 ("The reverb that wouldn't decay") honestly correcting it -- the reverb DIVERGES;
  the "stable tail" was the I4-following bridge reading a moving ring slot, not the railed real output.
  The 4 core fixes in Part 13 stand. (mame-blog is a static JS blog: edit posts/kn7000/*.md + posts.json,
  NO build needed; it is SEPARATE from the kn5000-docs Jekyll site.)
- Confirmed this tick: MIDI in/out fully wired already (done); the 3 unwired volume sliders control
  external audio the emulator doesn't model (MIC/LINE-IN via IC309 ADC) or need accompaniment-voice
  classification (APC/SEQ) -- not cleanly wireable, correctly left as placeholders. Panel-LED next steps
  need the layout generator's cpr_led range extended past 80 + physical placement.
- Binary rebuilt clean (instrumentation reverted) + republished; boots to PMEM home, no regression.

## ★ SESSION 2026-07-11j — deep SHARC core-instrumentation of the reverb divergence (READ notes/dsp-effect-execution-chain.md tail)
Spent this session localizing the reverb divergence with temporary SHARC-interpreter instrumentation
(all reverted; tree clean; binary republished). RESULT = big elimination, root cause still open:
- CONFIRMED: the reverb output float F1 grows from the input to +/-2e7 (>2x full-scale), rails, and
  NEVER decays (still +/-1-3e7 17 s after note-off) => effective feedback ~1.0. Same interp & DRC.
- RULED OUT: the DM coefficients (all damped -0.618/0.458/-0.280/0.853; forcing ALL near-unity DM
  coeffs 0xC000-0xC300 to 0.9 still rails), the float multiplies (exact), the allpass structure
  (correct Dattorro/Gardner, g=-0.618), compute_fmul_fadd (no hazard), FLOAT/FIX (stock verified),
  op 0x09, and the circular-buffer off-by-one (real nit `> B+L` should be `>= B+L`, fixed+tested,
  NOT causal, reverted).
- REMAINING SUSPECTS (next tick): (1) the reverb also reads PM via I8 (`R3 = PM(I8,M8)`) -- the
  tank-decay feedback may live in PM, or DM coeffs are reloaded from PM each frame (why the DM override
  did nothing); dump/override the PM data. (2) 32-bit host float vs the 21065L 40-bit extended + MODE1
  rounding on a near-unity tank feedback. Full trace + the exact instrumentation recipe are in
  notes/dsp-effect-execution-chain.md sections 2026-07-11h/i/j.
- No shipped change this session (all diagnostic). Effects remain audible-but-not-faithful; DRY
  passthrough is correct. Consider whether the next tick continues this (PM dump) or pivots to a
  completable item (MIDI port declaration, volume-slider ADC, panel punch-list) for visible progress.

## ★★★ CORRECTION 2026-07-11d — the effects RUN but the reverb RINGS (not "working well" yet)
The 2026-07-11 update below over-claimed. Careful A/B measurement (now possible thanks to the TG
release envelope) shows the active reverb does NOT decay:
- Single fresh Dark2 note, note-off at t: the TG input stops (~0.2 s) but the DAC output holds a
  CONSTANT-amplitude oscillation for 3.5 s+ (no decay), plus a growing DC offset. Tested 3 reverb
  types -- ALL ring identically (decay ratio +2.8s/+0.3s ~= 1.0). So it's SYSTEMATIC, not per-type.
- The reverb DOES process each note (reads input at DM[I4+0x20]=1.3M peak, reads+WRITES its SDRAM
  delay lines 1.68M/1.23M per note over word range 0x36E55-0x643AB). It builds up a wet signal --
  but with feedback ~= 1.0 it never decays and ACCUMULATES across notes (so a later "silence" window
  still shows the ring from earlier notes; that earlier looked like "input-independent garbage" but
  it's the undecayed tail).
- ROOT CAUSE: the effect CODE loads + runs (via the active path maincpu 0x48404EDD -> HAL 0x48404E8D),
  but its DEPTH/TIME PARAMETERS -- which set the feedback < 1.0 -- are NEVER applied. The clean
  DspEffectSelect path (param block *(0x500A01E0)+unit*0x120, unit9=Reverb) never runs: *(0x500A01E0)
  stays -1. So the reverb runs at default (unity-feedback / infinite-RT60) coefficients instead of the
  "TOTAL DEPTH: 80" the screen shows. The on-screen DATA DIAL / value-encoder do NOT trigger a host
  re-upload either.
- Honest status: DSP AUDIO PIPELINE works (TG->DSP->speaker; the DRY passthrough is clean, off==on
  within 1%, verified Part 12). Active effects LOAD + EXECUTE. But the reverb is NOT a faithful/usable
  reverb yet -- it rings. "Effects audible + type-selectable" is true; "effects work WELL" is NOT yet.
- UPDATE 2026-07-11g (SUPERSEDES the "depth not applied" framing below): deeper diagnosis shows the
  reverb output SATURATES to the rail (0x7FFFFF at slot 0xC358, in BOTH interpreter and DRC), i.e. the
  float recursion DIVERGES; and the "audible effect" was a BRIDGE ARTIFACT (I4-following reads a moving
  SPORT-ring slot, not the railed commit). Dumped the running reverb's coefficients: 0xC000 block =
  textbook-DAMPED (0.85/0.70/0.64/..), and the one >unity value (1.161 at 0xC2C4) is a CONSTANT
  feedforward gain (the recursive a1/a2 terms 0.245/-0.406 are stable). So the leading hypothesis is
  now a **SHARC ARITHMETIC BUG** in an op the reverb uses but the passthrough doesn't (fixed MAC
  `Rm=MRF+Rxm*Rym` sharcops.hxx multiop grp3 line 806, mul, or FLOAT/FIX round-trip -- added during the
  LLE), NOT the depth. NEXT (fresh methodical tick): single-step the divergent float recursion
  0x847c-0x8483 (watch F3/F11 grow with the damped coeffs) OR unit-test the fixed MAC + FLOAT/FIX vs
  the ADSP-21065L TRM (repo root). The DspEffectSelect depth path IS dead (*(0x500A01E0)=-1, setter
  0x484057d6 never called) but that is NOT what makes it diverge. Tooling: decompressed program image
  at ../kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin; reverb PM dumps via Lua read_u64 ->
  unidasm -arch sharc. Full chain: notes/dsp-effect-execution-chain.md (sections CORRECTNESS gap ->
  DECISIVE -> SMOKING GUN -> CORRECTION -> 1.161-constant). The default boot sound is the clean DRY
  passthrough (verified off==on); divergence only manifests if a user actively SELECTS a reverb, so no
  shipped-default change was made.

## ★ SESSION UPDATE 2026-07-11 (DSP effect-execution chain + config cleanup) — READ notes/dsp-effect-execution-chain.md
DONE + committed (87a2964, 630c68d, e859261):
- **Config switches REMOVED per Felipe** ("Effects DSP host stub" + the two "Tone generators"):
  the KN7000 always has the TGs (IC201/IC205) + effects DSP (IC306), so both are now unconditional.
  TG-enable gate (0x500ce380=0x40) opens naturally at boot from the TG-present strap; the post-boot
  gate-force hack (old CONFIG bit2) is gone. Default boot = home screen (PMEM A-) + audible, no -cfg.
- **DSP-present handshake FIXED**: firmware self-test (fw 0x48404d25) software-triggers INTC group
  0x17 (GxICR 0x3400015c) + polls bit4; emulator never ack'd -> 0x500066CC=0xFF -> runtime DSP-write
  gate (0x48404ef5) slammed shut -> effect selection never reached the DSP. intc_w now latches
  group-0x17 REQUEST when the DSP is present. 0x500066CC stays 0; selecting Dark2 uploads +783 words.
- **SHARC core**: implemented ALU op 0x09 (fixed-point average) + shift-imm DRC fallback (FDEP-SE);
  added notify_pm_written() (host PM-write -> cache_dirty) so runtime uploads aren't run stale.
- SD slot cover: explained (only observable with -harddisk image on an SD screen; not a bug).
★★ EFFECTS ARE NOW AUDIBLE + VERIFIED STABLE (commits 38a3f4a, 82633cc) ★★ The last blocker is SOLVED.
  Verified: a held Dark2 note holds a CLEAN steady output (peak ~7%, no clipping/blow-up over 10s) --
  reverb feedback is stable, not runaway. Default effect stays audible; boot reaches PMEM home; no
  crashes. Also done this session: MAIN VOLUME slider wired (commit 959c1a6), 3 dev config switches
  removed (commit 87a2964), blog Part 13 published (mame-blog 0b3d46a). CAVEAT for judging effects by
  EAR: the tone generator is still a synthetic placeholder (sine + short envelope) because the 4 PCM
  wave ROMs are undumped -- effect character A/B needs a real voice. NEXT POLISH (optional, not
  blockers): wire DIGITAL EFFECT on/off + per-effect DEPTH so menu param changes are audible; verify
  different reverb TYPES load distinct microprograms; a richer placeholder timbre would make effects
  easier to judge by ear (label clearly as placeholder). Details below.

(historical, now solved) The last blocker was SOLVED. By disassembling the
  running reverb (dump DSP PM via Lua read_u64 -> unidasm -arch sharc), the kernel keeps its per-frame
  audio in DM index reg I4: output=[I4], input=[I4+0x20]. The passthrough parks I4 at 0xC350 but a real
  effect parks it at the SPORT0 TX-B autobuffer 0xC358 -- the old fixed TX0+0xE=0xC350 read missed it.
  Fix: adsp21062::dm_index_reg(4) exposes live I4; dsp_audio_tick now follows it (no full SPORT-DMA
  model needed). notify_pm_written() cache-invalidation is ENABLED, so selecting a reverb runs it and
  its output reaches the DAC (Dark2 RMS 1863 vs 0). Default effect stays audible; boot still reaches
  PMEM home. REMAINING POLISH (not blockers): (a) tone generator is a synthetic placeholder (no PCM
  samples / no note release) so effect *character* can't be judged by ear yet -- needs the wave ROMs
  or a better TG; (b) wire DIGITAL EFFECT on/off + per-effect DEPTH so menu param changes are audible;
  (c) SPORT A/B double-buffer alternation unmodelled (fine for now). See dsp-effect-execution-chain.md.

## ★ SESSION UPDATE 2026-07-11b (TG amplitude envelope — Felipe's task) — commit 6a90e62
DONE: the placeholder TG had a HARDCODED envelope; now it's DRIVEN BY THE FIRMWARE's per-sound EG.
- The firmware writes a 7-halfword amplitude EG per voice (group-0 regs 0x04-0x0A = ATK PEAK DCY1
  SUS1 DCY2 SUS2 RLS) before each note-on; tg_write used to drop them. Disassembly (lib 0x4C03741A)
  shows r4..rA are copied straight from the voice tone-data.
- Decoded via live piano-vs-organ/strings capture: r4/r5/r6 constant (fast attack); **r7 = SUS1 the
  sustain LEVEL** (piano 0x2C ~35% -> decays; organ/strings 0x7F max -> sustains). r8=DCY2 r9=SUS2
  rA=RLS. kn7000_tonegen_device now caches r4..rA and runs a per-voice attack->decay-to-sustain->
  hold->release envelope (decay time from r8, calibrated to the Concert Grand's ~1.8s). VERIFIED on
  the raw TG output (DSP input 0xC378): held PIANO decays 1.09M->671k, held ORGAN holds ~1.11M.
- REFINED (commit e05efe9): rA = RELEASE rate (a SOUND PAD capture pinned it -- pad rA=0x04 fades
  slowly, organ rA=0xAE stops fast, piano rA=0x25 medium; firmware DOES mute the TG on key release so
  it fires). Release coef now from rA, calibrated to piano 0x25 -> 0.15s. VALIDATED across 5 sounds
  (piano/organ/strings/pad/mallet): sustain (r7), decay time (r8), release (rA) all firmware-driven --
  e.g. a mallet decays faster (r8=AE -> 0.42s) than a piano (r8=99 -> 1.8s) to the same low sustain.
- STILL PROVISIONAL (labelled in code): exact chip RATE curve; the ATTACK (r4/r5/r6 constant across
  all 5 sounds so fixed ~6ms -- a per-sound attack likely lives in r0-r3 which DO vary, but needs a
  genuine slow-attack sound to pin); SUS2/DCY2 (r9/r8) as a true 2-stage decay. Measurement caveat:
  the dry TG envelope is masked by the reverb tail in the final WAV. Full trace: notes/tg-envelope-*.

## ★ SESSION UPDATE 2026-07-11c (research tick: floppy groundwork + effect-control probe)
- FLOPPY (IC103) investigation: notes/floppy-fdc-investigation.md. The disk stack is deeply layered
  (FAT read 0x485335FF -> disk-type dispatcher 0x48532468 -> 3-driver table @0x486646f0 [floppy/SD/USB]
  -> FS-device create 0x4846d800 with an "A:\" drive-letter config -> block read 0x4846da31 whose FDC
  register base is a RUNTIME pointer). FDC NOT touched at boot. Locating it needs a live disk op (drive
  DISK MENU + floppy image) + a breakpoint on 0x4846da39, so it's a dedicated multi-tick task. Deferred.
- EFFECT CONTROLLABILITY: reverb TYPE selection is confirmed controllable (distinct microprograms per
  type, verified earlier). The DEPTH control was NOT re-locatable: neither the DATA DIAL nor the CPC
  value-encoder guesses (SEG16-1A) trigger a DSP host re-upload on the REVERB screen. Depth is likely
  applied as an in-DSP DM coefficient (not a host re-upload) and/or its on-screen control is one of the
  still-unconfirmed value buttons; hard to A/B by ear (placeholder TG + reverb tail masking). Left as a
  future refinement -- the MAIN effects goal (audible + type-selectable) is already met.

## NEXT-TICK CANDIDATES (pick highest value; sound subsystem is now mature)
- FLOPPY DRIVE (Felipe's list): the KN7000 has a 3.5" FDD (service manual Part VI Disk Drive p122-137;
  DISK MENU = Load/Save/DIRECT PLAY/Medley/Tools). UI-level symbols found (DiskInfoProc, FormatDisk,
  TestDiskFunc 0x484A0A32 [a msg dispatcher, NOT the FDC], DiskAttention 0x4851719F). The LOW-LEVEL
  FDC I/O is in the library/disk task -- NOT yet located; find it (trace the FAT-read 0x485335FF back
  to the sector read, or the disk-driver task) before modelling an FDC device + floppy image. Big task.
- TG envelope ATTACK (the one remaining ADSR piece): r4/r5/r6 are CONSTANT across all 5 sounds tried
  (fast attack) -- likely the base sounds all have a fixed attack and the amp-edit ATTACK TIME edit is
  what varies it (r0-r3 vary per-sound but read as level/key-scale). Needs a genuine slow-attack patch
  (blocked on menu navigation) or the chip datasheet. Low urgency; current fixed ~6ms is fine for the
  base sounds.
- DSP effects DEPTH / DIGITAL EFFECT on-off (Felipe's "hear a parameter change"): types verified to
  load distinct microprograms; depth/on-off still to verify -- hard to A/B by ear (reverb masks, and
  placeholder TG), so measure via DSP coefficient changes.

## Hard rules (do not violate)
- **NEVER run MAME with `-video none`** (see memory `never-video-none`). Display
  is available (DISPLAY=:0, wayland-0). Run with visible video.
- Commit notes/plans/code FREQUENTLY (small commits, clear messages).
- After any driver rebuild: run `tools/publish-binary.sh` to refresh the
  host-accessible `kn7000-emulator/` copy (memory `publish-kn7000-binary`).
- After any website edit: rebuild the Jekyll site with Option B
  (`jekyll build -s ~/compartilhado/kn5000-docs -d /tmp/kn-site`) — memory
  `technics-docs-site-build`.
- If the mount throws "Too many open files in system" (ENFILE): run
  `sudo -n /usr/local/sbin/drop-caches` (memory `virtiofsd-enfile-fix`). The
  `--inode-file-handles=prefer` fix is already applied and holding.
- Preservation integrity: reusing another model's ROM is an UNVERIFIED HACK
  until proven (memory `cross-model-rom-integrity`). Placeholder wave ROMs are
  clearly labelled synthetic — fine for bring-up.

## Build / run cheat-sheet
- Driver source: `kn7000_mame/src/mame/matsushita/kn7000.cpp`
- Build dir: `kn7000_mame_build/` — build with the project's usual make (SUBTARGET
  kn7000). Binary: `kn7000_mame_build/kn7000`.
- Run: `cd kn7000_mame_build && ./kn7000 kn7000 -rompath roms -seconds_to_run N
  -nothrottle -autoboot_delay 0 -autoboot_script /path.lua` (NO -video none).
- Lua gotchas: RETAIN every `emu.add_machine_frame_notifier(...)` and
  `install_read_tap/install_write_tap(...)` return value in a `_G` table or GC
  unsubscribes it silently. Program space is 32-bit: taps must cover aligned
  4-byte units (`base..base+3`). Keybed: ports `:KEYS0`/`:KEYS1`, fields "Key C4"
  etc; `field:set_value(1/0)`.

## Current branch: phase-c-stage2 (kn7000_mame)

## DONE
- Phase A: effects-DSP host stub gated by PORT_CONFNAME (verified).
- DSP full disasm+docs (80 records) in kn7000_disassembly (committed).
- Cross-model DSP compare (KN6000==KN6500) committed.
- Placeholder wave ROM generator committed.
- Phase C Stage 0: bring-up sine synth device (KN7000_TONEGEN), audible on PC key.
- Phase C Stage 2 plumbing: io_w routes TG writes to m_tonegen->tg_write();
  m_tg_reg widened to [2][0x10000]; pitch capture (0x2000/0x3000).
- virtiofsd root cause fixed (--inode-file-handles=prefer).
- Website: kn7000 sound-subsystem / effects-dsp / gui-map pages added.

## ★★ MILESTONE COMPLETE 2026-07-10 — KN7000 makes firmware-driven sound

The KN7000 now produces AUDIBLE, correctly-pitched notes driven by its own firmware
voice engine. Committed (96c702c) + published (kn7000-emulator/ binary @ 00:57).

## ★ PANEL BANK DISCOVERY 2026-07-10 — the driver's panel was mapped to the WRONG model

Re-RE'ing the disk/SD navigation exposed a bigger issue. The firmware has TWO panel
button-descriptor tables selected by the model/TG strap (dispatch 0x484ADB59 ->
0x484ABAFD=*(0x5006BE94); ==0 -> bank A 0x48614978, !=0 -> bank B 0x486149FC; flag from
strap 0x98070000 bit1 via probe 0x484D7713). **Bank A = the KN7000** (has the SD switches
SEG1D=0x20B5..BA; TG present = real hw). Bank B = a no-TG variant (NOT the KN6000 --
its firmware doesn't contain bank B's layout). The driver's panel PORT_NAMEs + layout +
navigation were all built against bank B (when the driver falsely reported TG absent), so
now that sound is default-on (TG present -> bank A, correct) the buttons are mislabelled
-- SOUND buttons misbehave, DISK moved to SEG0D.b6, "Fn 2016" placeholders exposed.
RUNTIME-CONFIRMED: SEG14.b3 -> "SOUND-RIGHT1 SAX & WOODWIND" screen. Full bank-A SOUND
GROUP + DISK positions in notes/panel-bank-A-is-the-kn7000.md.

✅ PANEL BANK-A REBUILD COMPLETE (2026-07-10):
- STAGE 1 (commit 913636b/9f0bbf8 lineage): the driver's SEG ports (PORT_NAME) rewritten to
  bank A from the workflow-verified table (wf_bdf3b275-55c, 3 families + adversarial verify).
- STAGE 2 (commit 9f0bbf8): the clickable kn7000.lay inputtag/inputmask bindings + state-driven
  LEDs rebound to bank A. Every physical button keeps its position+label; only its bit changed.
  pair_h() generalised (seg2=) for cross-SEG split pairs; MEMORY/EW EXPANSION now bound; PART
  SELECT + CONDUCTOR groups fully bound. Full map: notes/panel-layout-bankA-bindings.md.
  VERIFIED: no dup/phantom bindings (all 132 bits real), MAME renders with no layout errors,
  and END-TO-END -- pulsing the PIANO artwork bit (SEG10 0x10) opens SOUND-RIGHT1-PIANO; the
  8&16 BEAT genre bit (SEG02 0x80) opens RHYTHM-8&16 BEAT.
REMAINING (unchanged, not blocking): the ev2010 menu-tab family + 5 unnamed ev2040 apps + the
CPC control column (SEG16-20/1B) want a bank-A runtime snapshot probe; a full empirical bank-A
function-button LED re-sweep is polish (genre+sound-group LEDs already re-keyed by state identity).
The SD/DISK navigation re-RE stays under the USER-PAUSED SD subsystem (do not pursue autonomously).

## ★ STUCK-NOTES FIXED 2026-07-10 (commit 09870dc) — key-bed make/break is bit7, not velocity 0
Felipe: the key bed emitted key-on but never key-off (stuck notes, seen as CHORD FINDER
rectangles staying drawn; both MIDI + PC keys). ROOT CAUSE (firmware RE, unambiguous): the
voice-event FIFO word (0x98050004) encodes MAKE/BREAK in **bit 7 of the key byte**, not the
velocity — firmware btst 0x80 at 0x484480e5 (routes on/off) + 0x48448151 (decoder: bit7=0 ->
compute pitch/gate ON, bit7=1 -> clear gate). The driver sent releases as (key, velocity 0) =
bit7 CLEAR -> read as ANOTHER note-on -> stuck. FIX: releases push (key | 0x80) velocity 0xFF
(0xFF also skips the sustain/hold re-latch at 0x484480fa -> 0x501496a2). Both kbd_key (PC) and
kbd_midi_rx (MIDI). Verified: FIFO tap press=0x6418/release=0xFF98(bit7=1); disasm; and CHORD
FINDER held-key dots MOVE F->G (don't accumulate) on release. Published. notes/keybed-fifo-makebreak.md.
(Bonus: confirmed the STAGE-2 bank-A LCD soft-key SEG11 0x01 toggles CHORD FINDER on APC SELECT.)

## Felipe punch-list + DSP plan 2026-07-11 (commits 78b4bbd / 96bb5e8)
Panel: TRANSPOSE/OCTAVE +/- swap fixed + the 6 SD CARD buttons wired to SDSW (done). Genre LEDs
re-verified correct (all 16 light their PANEL_LED output on selection). PANEL MEMORY SET, CUSTOM
PANEL, PAGE/CONTRAST: investigated, NOT reliably determinable (SET!=ev2011 disproven; CUSTOM PANEL
ev20B4=generic latch; PAGE/CONTRAST=CPC value column, SEG20=tempo) -> left unbound, not guessed
(need the CPC switch matrix). Detail: notes/panel-selftest-validation.md.
★ NEW MAJOR EFFORT (Felipe): make the effects DSP audibly process effects. Thorough phased plan in
notes/dsp-effects-improvement-plan.md -- exploits the now-working panel to drive effect selection +
instrument the DSP uploads. 4 hypotheses (selection/execution/mix/parameters); the SD-menu blocker
that parked f3-effect-loading.md is GONE (play screen reachable + effect buttons mapped). First step
= one instrumented Phase A+B run (tap 0x9C000000 + *(0x500A01E0), drive REVERB via the panel).

## ★ PANEL BUTTONS + LEDs VALIDATED/FIXED 2026-07-10 (Felipe: use the SW&LED self-test; map all buttons)
Used the firmware's OWN self-test data as the authoritative source (commits faa9aa4 / cdf64f5 / 82d520a):
- BUTTON VALIDATION: PanelSwitchClassTable @0x4860C9F4 (switch#=normSeg*8+bit -> [LED row,col] or
  special class). Cross-checked vs the bank-A INPUT_PORTS -> the real-button set MATCHES, no phantoms
  (SEG16-1B/20 correctly have no LED = CPC value column; SEG1D = SD switches; UNUSED bits = empty slots).
- DECORATIVE BUTTONS MAPPED (empirical app/screen sweep) + bound in the layout + named in INPUT_PORTS:
  PANEL MEMORY 1-8 (ev2010 arg 0-7 recall; clickable pie-slice buttons on the dial, slice order per
  Felipe = [2,1,8,7,6,5,4,3]), BANK VIEW (ev2013), NEXT BANK (ev2012), FAVORITES (ev20AE), MUSIC
  STYLIST / CUSTOMIZE / SD MENU / SEQUENCER PLAY / EASY RECORD (ev2040 apps). Verified live (PM1->PMEM A-1).
- LED MAP SOLVED + APPLIED (firmware-authoritative, live-validated): led=(remap[row]&0x3f)*8+col_index,
  board=cpl if remap[row]&0xc0 (row-remap table @0x48615058; row/col from PanelSwitchClassTable). Validated
  live: genre0->cpl_led2, ROCK&POP->cpl_led18, PIANO->cpr_led44, PM1->cpr_led72 (all exact). gen_lay.py now
  computes PANEL_LED[(SEG,mask)] for all 91 button LEDs, replacing the old bank-B/state-identity guesses.
  Full detail: notes/panel-selftest-validation.md. Diagnostic-mode boot entry = dead end for key injection
  (sub-CPU reads the combo, not the note FIFO -- verified); static-table approach supersedes it.
STILL OPEN (minor): CUSTOM PANEL / PANEL MEMORY SET (no distinct event found), PAGE / CONTRAST (CPC
value-encoder column -- a value-input model, not a simple bind). Also earlier this session: KEYBED
STUCK-NOTES fix (make/break = bit7; commit 09870dc).

★ USED THE SELF-TEST (Felipe: "use the LED & Button self-test mode"; commit bd53933). Enabler
tools/panel_selftest.lua holds flag 0x5006BFB2=1 -> button presses route to the firmware's InOut
test handler 0x484A0CB0, which lights each switch's LED from PanelSwitchClassTable (LED appears
~1s after press, ACCUMULATES, per the manual). RAN it: pressing each button lights EXACTLY its
PANEL_LED formula LED -- 24/27 in a membership sweep across all row ranges (incl. rows 14-19: BRASS
cpr81/SAX cpr80/PM1 cpr72/PM8 cpr15 -- the ones I was unsure of, now firmware-confirmed). So the
firmware's OWN self-test validates the button->LED map. LIMITATION (honest): the full test SCREEN
("ALL DEVICE OK") can't be entered -- the boot key-combo C#3+D#3+C#4 is read by the panel/key
SUB-CPU, NOT modeled at power-on (verified: FIFO key injection does nothing); and forcing the flag
on the HOME screen is a hybrid (home screen also processes the button -> leakage). Doesn't weaken
the map (switch-class LED == normal-op LED, separately proven). Full screen would need modeling the
sub-CPU power-on key report OR forcing the MILK test-window create (0x4849F8F0 -> 0x4842a717) -- a
larger focused effort. Detail: notes/panel-selftest-validation.md.
CRON TICK 2026-07-11: diagnosed the leakage ROOT CAUSE (disassembly-confirmed): dispatch 0x484ADB59
reads the flag @0x484ADB72, calls the test handler 0x484A11E1 (lights the LED) @0x484ADB7C, then
FALLS THROUGH @0x484ADB85 to the normal dispatch -> the button event is ALWAYS posted + consumed by
the focused screen. So flag-forcing on the home screen is INHERENTLY hybrid (LED test + real
function); the only clean self-test needs the test SCREEN. LED validation unaffected (0x484A11E1
lights the correct switch-class LED). Documented. Awaiting Felipe's steer on whether to model the
sub-CPU power-on key report (offered) to enter the full screen -- do NOT start that deep RE unattended.

## Cron-tick verification (2026-07-10, post panel buttons/LEDs)
Re-verified the PUBLISHED deliverable after the panel button/LED work + republish: binary md5-identical
to the build tree; DEFAULT boot reaches the PMEM home/play screen with the full new layout (RHYTHM/SOUND
LEDs lit, PANEL MEMORY dial with its 8 clickable buttons + LEDs) and no fault; sound intact (C4 = 262 Hz,
RMS 2685). The layout changes are input/display artwork only and cannot touch the sound engine -- confirmed.

## Cron-tick verification (2026-07-10, post panel bank-A STAGE 2)
Re-verified the PUBLISHED deliverable (kn7000-emulator/, run as Felipe will) after the layout
rebuild + republish. DEFAULT boot (empty cfg -> driver defaults, TG-sound bit1 ON) reaches the
PMEM home/play screen (PMEM A-, RHYTHM 8 Beat 1, RIGHT1 Concert Grand, full mixer) with the
NEW bank-A panel -- no SD menu, no fault. Sound intact: pressing C4 yields a clean 262 Hz
fundamental (RMS 2685 vs 0.0 silence; the layout change is input-binding artwork only and cannot
touch the sound engine -- confirmed). Also cleaned a dirty cfg my in-session test runs had left in
the published dir (a stale forced CONFIG bit2 + stray key remaps) back to the minimal default.
Lua gotcha logged: PORT_GM_NOTE renames the keybed field to "C4" (not "Key C4") -- match on "C4".

## ★★★★★★ SD CARD MOUNTS 2026-07-10 (commit bf0c9a2) — the SD data path is COMPLETE

The last mount blocker is SOLVED: the DATA-BLOCK CRC16. The firmware verifies the CSD's
CRC16 (routine 0x4854c919: init d1=0 then the 0x1021 MSB-first loop = SD-spec init 0x0000),
but MAME's util::crc16_creator inits to 0xFFFF -> every CSD read failed CRC (traced: read
primitive 0x4854c3ab reached the CRC compare 3x, mismatch 3x) -> initflag 0x5016064c never
set -> mount state 4. FIX: patched spi_sdcard (overlay) sd_data_crc16() with init 0x0000
for CSD/CID/data reads. RESULT (verified, -harddisk sdtest.hd + cover closed): full init
CMD0/1/59/9/16/10, mount worker completes -> **SD state 3 (MOUNTED), card-ready
0x50083bc2=1, initflag=1** -- reaching state 3 read the boot sector + FAT from the host
image, so cmd-3 sector reads work end-to-end. Default boot unchanged (no card = home).

NEXT: SD menus ON SCREEN. The sound-present panel descriptor bank (A, 0x48614978) remapped
the soft-keys + the DISK button vs the old sound-absent bank -- the previous DISK(SEG12
0x80)/SD MENU(SEG03 0x80)/SD-AUDIO(SEG0F 0x20) path now lands on PMEM/SOUND screens (DISK
now selects a panel-memory preset). Re-RE the disk/SD navigation under bank A, then
directory listing / file browse / SD-Song(SMF) + SD-Audio playback, and the SD IN USE LED.
Checklist: notes/sd-card-emulation-plan.md.

## SD SPI STACK COMPLETE THROUGH CSD 2026-07-10 (commits 9279ba0/3457304/b8bd72c)

Transport DONE + proven. Full mailbox RE (wf_6a5ed26e-8d4, 6/6 confirmed): bone-stock SD
SPI master, no CPSD protocol. Driver: 0x9805000C = SPI byte latch -> MAME spi_sdcard;
CHIP SELECT = GPIO 0x36008004 bit1 (active-low); patched spi_sdcard (overlay) appends
CRC16 to the CMD9 CSD block. The firmware's card-init 0x4854b691 now runs the whole SD
init correctly framed: CMD0->01, CMD1->00, CMD59 self-test x3, CMD9 -> VALID CSD read
back. Card presence edge-driven (-harddisk file.hd; sdtest.hd=64MB FAT16). LAST BLOCKER:
CMD9 read primitive 0x4854c3ab errors before CSD parse 0x4854c6f3 (cmd9-site 3x, parse
0x) -- a post-data check (btst 0x0400/0x1200) or CSD field. Once initflag 0x5016064c=1,
mount completes -> SD menus open. Details: notes/sd-card-emulation-plan.md Phase 2 #2.
Boot unchanged (85% home screen, no card).

## SD SPI TRANSPORT WORKING 2026-07-10 (Felipe: implement the transport; commits 9279ba0/3457304)

DONE what Felipe asked: captured the mailbox protocol + implemented the SD transport HLE.
The "mailbox" at 0x9805000C is a byte-wide SPI MASTER (handshake ICR 0x34000170 grp 0x1C);
the firmware speaks STOCK SD SPI (10x 0xFF, CMD0 40..95, CMD1, CMD9 CSD). Driver clocks
each 0x9805000C write's 8 bits through MAME's spi_sdcard (m_sdcard; -harddisk file.hd) +
asserts grp 0x1C. VERIFIED: CMD0->0x01, CMD1->0x00, CMD9->CSD answered correctly. Card
presence = edge-driven (insert edge at t=6 if image attached; else ERROR 93). Both boot
paths reach the home screen. NEXT (mount completion): the worker card-check 0x4854b597
needs initflag 0x5016064c!=0, set indirectly by a disk-worker init sub-command (0x4854afee,
addr @0x4854b0ae/b11a) -- chicken-egg with card-init; the in-flight command-layer finder
(wf_6a5ed26e-8d4, 1/6 in) is resolving which sub-command runs the full CSD-parse init.
Details: notes/sd-card-emulation-plan.md Phase 2 section. Test image: sdtest.hd (64MB FAT16).

## SD TRANSPORT IDENTIFIED 2026-07-10 (autonomous tick; notes commit 1f0667a)

Traced VFS device 'C' fops (@0x500079D8) -> command poster 0x4847030e -> disk-worker
msg type 3 -> handler 0x4854afee (cmd switch: 3=read/4=write/8,A,B,C=control) ->
transfer primitive 0x4854c3ab (0x200-byte sectors, cmd block @0x50007ee4). **The
hardware = a strobed 16-bit mailbox: register 0x9805000C (sound-bank io window) +
handshake via ICR 0x34000170 (ext-int group 0x1C), shadow @0x50005200.** This is the
register PC 0x4854BF74 already writes 20k times at boot (the probe idling against our
zero stub). NEXT: live-capture the strobe/data protocol during boot-probe + a mount
attempt (fire the plumbed insert edge), RE wait helpers 0x4854bb89/bc8f/c94d/c1d5,
then HLE the mailbox against a host FAT image so card-init 0x485630de succeeds.

## SD PANEL SWITCHES LIVE + 61-KEY MIDI BED 2026-07-10 (commit f673b74)

Felipe asked for the SD-panel inputs + host-key/MIDI keybed. DONE + verified:
 - SDSW port (VOL-/+, SKIP<</>>, STOP, PLAY/PAUSE) -> active-low byte 0x9CC00008
   bits0-5 -> events 0x20B5..BA; layout sd_block elements clickable. Pressing
   SD VOLUME+ on a stock boot yields the FAITHFUL "ERROR 93! SD lid is open"
   (empty slot) -- the SD panel input path works end-to-end.
 - Key bed = full 61 keys (C2..C7), every key with PORT_GM_NOTE markup (USB-MIDI
   via MAME's midi input provider plays the whole bed); PC tracker keys kept on
   C4..C6. Verified C2=65.4Hz, C7=2093Hz.
NEXT for SD: the card data transport behind card-init 0x485630de (VFS device 'd'
= "C:"), host FAT image, insert-card action (m_sd_insert_timer plumbed).

## ★★★★★★ SOUND ON BY DEFAULT 2026-07-10 — SD-menu boot solved (PHANTOM BUTTONS; commit d53539d)

THE MILESTONE: a stock boot now reaches the PMEM home screen WITH WORKING SOUND (C4 =
262 Hz, no cfg). The "TG-present boot lands on the SD menu" mystery = SIX PHANTOM BUTTON
PRESSES: the SD front-panel switch register (byte 0x9CC00008, ACTIVE-LOW) read 0x00 as
plain RAM = all pressed -> UI takeover. Fixed (idle switches); TG sound switch now
DEFAULTS ON; the bit2 gate-poke is OBSOLETE. Also: black-LCD regression from the ch2
keep-alive was found by the workflow and FIXED (2d6590a) -- **ch2 = MIDI-2, NOT CPSD**
(the whole ch2-CPSD theory is retired; injected bytes wedge the boot).

SD state (workflow wf_d6998fbd-c86, 8/8 CONFIRMED, full detail in
notes/sd-card-emulation-plan.md RESOLUTION): state machine is DEMAND-driven (entry
0x485519b7, called at post-prologue 0x485519bc); DiskInit runs at boot; triggers =
card-detect TRANSITION (group-0x1B ICR 0x3400016C bit4 1->0) -> insert msg 0x107020bb,
then a user SD action. Driver models the EMPTY slot (faithful) + a plumbed insert
timer. NEXT (SD Phase 2): RE what card-init 0x485630de touches = the real card data
transport (behind VFS device-'d' fops, table 0x500079f8, SD = drive "C:"); HLE it
against a host FAT image; then wire the insert action + the 6 SD-panel switches
(events 0x7020B5..BA) as input ports. Tooling lessons in the notes (d@ vs dword@;
post-prologue callers).

## ★★★★★ SD/CPSD LINK ALIVE 2026-07-10 (SUPERSEDED by the section above — ch2=MIDI-2) (Felipe UN-PAUSED SD; commits 0f00f9a, 4882ec8)

Felipe: "let's work on the SD card interface!" -- the pause is lifted. ROOT CAUSE of the
SD dormancy found in hours: it was never dormant -- an SD link task spins from boot on a
link-ready check (helper 0x484b2889 polls ch2 status bit6|bit4, ~65k calls/s) and our HLE
never set TxRDY. Fixed status semantics (bit6=TxRDY, bit4=RxRDY, bit7=RX EMPTY), captured
the firmware's first CPSD TX (0xFE ping at boot t=1.37), and stood up a CPSD HLE
(cpsd_rx_byte + periodic 0xFE keep-alive): the firmware now marks CPSD ALIVE
(0x50150f55 bit6 set, watchdog parked). CH2 SPEAKS MIDI FRAMING (real-time dispatcher
0x484b2454: F8 Clock->tempo, FA/FB/FC transport, FE alive; F0..F7 SysEx -> lib MIDI
engine 0x4C024A1F) -- CPSD streams SD-Song MIDI + SysEx-wrapped control/status.
Corrections: "bit6 breaks boot" does NOT reproduce; the 0x90200000 "SD register bank"
(2026-07-08) was a MISREAD (sound-parameter DB IDs; adversarially confirmed) -- the
serial link is the ENTIRE SD path. Perf note: boot ~61% (SD task now runs; expect to
improve when the handshake completes and the task stops retrying).

OPEN (workflow wf_d6998fbd-c86 in flight, 2/8 results in): (1) what dispatches/gates the
SD state machine 0x48551f80 (still never runs; state block zero); (2) the TG-strap
boot-to-SD-menu wait condition; (3) the SysEx status/command frame payloads (the real
protocol). NEXT on workflow completion: implement the status frames, aim for the SD
menus opening (plan Phase 0/1), then host-FAT-image backing (Phase 2). See
notes/sd-card-emulation-plan.md BREAKTHROUGH section.

## ★★★★★ CORRECT MUSICAL PITCH 2026-07-10 — demo/chord-finder/keybed all in tune (commit de4fc88)

Felipe asked for correct DEMO pitches; root cause found + fixed. TG pitch class
0x2401 is NOT absolute pitch: pitch18 = ((class bit0)<<16)|data is SAMPLE-ZONE-
RELATIVE (descriptor tuning baked in). Fix = resolve musical pitch from the lib
voice record (0x500AF940 + slot*0xB4, +0x0C notePitch16 = musical pitch in 1/256
semis incl. all transposes; race-free before the TG write; drums=0x4280 const ->
legacy fallback; held-voice rewrites = relative bends; class-0x2400 note-ons no
longer dropped; keybed FIFO = key INDEX -> KN_KEY codes -36). Validated: keybed
C4=261.6Hz exact; demo bass == sequence blob; **CHORD FINDER NOW PLAYS TRUE C-E-G**
(the old "garbage voicing" = NULL-descriptor pitch math, bypassed by the resolve).
Full RE: notes/tg-pitch-pipeline.md (workflow-verified). NOTE: pitch-formula
finder/verify results may still land in wf_a8b4db86-02c journal — harvest for the
descriptor-inversion appendix (documentation-only; implementation already shipped).

## ★★★★ TEMPO TIMER MODELED 2026-07-10 — DEMOS & RHYTHM ACCOMPANIMENT PLAY (commit 60d5392)

THE DEMO STALL IS FIXED. Root cause: ALL sequenced playback is clocked by on-chip 16-bit
timer TM5 (mode 0x34001082 / reload 0x34001092 / count 0x340010A2, underflow -> INTC
group 7 = 96-PPQN tick ISR 0x48447084; reload = 1,250,000/BPM on 2 MHz) — previously
unmodeled, so demos played 1 note then froze and rhythm START/STOP did nothing. Now: the
DEMO Overture plays continuously (screens advance) and rhythm accompaniment plays on
START/STOP. Verified live (base=0x28B0=1,250,000/120 at q=120 exactly as disassembled).

THREE SYMPTOMS, TWO ROOT CAUSES (full study + research plan:
notes/sequenced-playback-and-style-data-rootcause.md):
 - demo stall = TM5 (FIXED);
 - "8 Beat 1" list + chord-finder garbage pitch = SHARED missing style/custom-flash
   data: name resource probed at unmapped windows (0x40010000/0x40610000/0x40810000/
   0x54E00000/0x54E10000) -> count=1 stub -> every name falls back; chord-finder part
   0x21 tone block (0x500D0B34) left at NULL boot default -> garbage pitch math
   (root-invariant 0x37B0 = descriptor exponent 7 = note-independent). Chord finder
   retested post-timer-fix: still garbage, as predicted (data, not clock).
Phase B (resource hunt in distributed data) DONE 2026-07-10: EXHAUSTIVE NEGATIVE — not
in the .AST payload, not in the kn7-14 TABLE update disks (their decompressed image ==
our dump byte-size, same truncation), not in kn7-16/CD-ROM/scd7000/cb7-update. The
factory rhythm/style flash was never distributed. NEXT per the plan: Phase A
(service-manual chip-select map for windows 0x40xxxxxx/0x54Exxxxx), Phase C (real-HW
flash dump via the ROM-backup route — needs Felipe), Phase D (labeled-synthetic name
resource at 0x54E00000, ~3KB, full recipe + probe mechanics in the appendix of
notes/sequenced-playback-and-style-data-rootcause.md — a clean, well-scoped item but a
DESIGN CALL (synthetic data policy) — get Felipe's nod first).

## ★★★ SD-MENU BLOCKER SOLVED 2026-07-10 — playable sound on the PLAY SCREEN (commit dbe0786)

The long-standing conflict is broken. Reporting the TG-present strap AT BOOT opens the
gate BUT advances boot into the paused SD subsystem (-> SD menu). FIX: leave the strap
CLEAR (normal boot to the PMEM home/play screen) and force the TG-enable gate open AFTER
boot instead -- voices then sound ON THE PLAY SCREEN with NO SD menu. Verified: C4 ->
262 Hz on the home screen (screenshot).
 - New CONFIG bit2 (default OFF): "Tone generators / firmware sound (play screen, no SD
   menu)". A timer forces RAM 0x500ce380 = 0x40 ~10 s post-boot and holds it (via the
   maincpu bus). Prefer bit2 over bit1 for playable sound. cfg: one <port mask="4"
   value="4">. Combine with bit0 (DSP) for TG->DSP->speaker on the play screen.
 - This is a workaround for the paused SD subsystem, not real-hardware behaviour -- but it
   makes the instrument PLAYABLE with sound on the normal screen. Root SD cause still open
   (kn7000-sd-strap-gate).
 - CHORD FINDER now usable: HOME -> APC MODE (SEG03 0x02) -> CHORD FINDER (SEG0F 0x40) ->
   the CF screen; the EAR = "MUTE PART 15 ON" = SEG07 0x10 (Felipe's tip), fires a chord.

CHORD-FINDER PITCH RESOLVED (as a DIAGNOSIS, not a code fix) 2026-07-10 -- see
chord-finder-navigation.md UPDATE (b): the tonegen decode is CORRECT (keybed verified exact
over an octave; keybed+CF share the pitch writer PC 0x4C036FBA). The CF's wrong pitch is the
FIRMWARE computing GARBAGE voicing (root-change test: C-Maj vs E-Maj give different non-
musical intervals; note-offs present; 2nd press not ignored). It's the accompaniment/voicing
data+state gap, NOT a decode/already-playing/note-off bug. NEXT = trace the pitch source
above 0x4C036FBA; do NOT fake a transpose.

DEMO OVERTURE 2026-07-10 -- see UPDATE (c): DEMO (SEG09 0x40, held) -> DEMONSTRATION menu ->
LCD LEFT 1 (SEG03 0x08) = OVERTURE -> "Welcome to SX-KN7000" splash. Intro note plays a
clean IN-TUNE F2 (sound engine renders sequenced data correctly), but playback then STALLS
(splash frozen 90 s, no audio after ~t24; CPU runs varied code = higher-level wait, not a
spin). Pre-existing (stalls without the gate-poke too). Open thread: demo/sequencer won't
advance past the first event.

REVERB (still open, now more tractable): the play screen did NOT auto-run DspEffectSelect
-- *(0x500A01E0) stays -1, so the per-unit param path isn't active; the effects that DO
load come from the lower path (maincpu 0x48404EDD). NEXT: with the play screen reachable,
try the panel effect-selection buttons (SOUND DSP / DIGITAL EFFECT) to make the firmware
select a reverb, then the active upload path loads it. See notes/f3-effect-loading.md.

## ★★ F.3 AUDIO ROUTING WORKS 2026-07-10 — TG audio flows THROUGH the effects DSP (audible)

The tone-generator audio now runs through the ADSP-21065L and out to the speakers.
Felipe confirmed AUDIBLE: DSP off = TG passes through unchanged; DSP on = the output
sounds DIFFERENT (the DSP is processing the sound). Committed kn7000_mame 4514170,
published, blog pending. Built on the verified F.3 research (notes/f3-implementation-
plan.md) + runtime probes (notes/f3-iop-runtime-capture.md).

What shipped:
 - Step 1 (aliasing, commit 61556c3): 21065L internal SRAM 0x9000-0x1FFFF now shared
   across the PM and DM buses (address-map handlers with the core's <<16/>>16 48-bit
   convention, DRC-safe) so the biquad reads the host-loaded coefficients (verified
   PM(0x9800)==DM(0x9800)) instead of zeros.
 - Step 2 (commit 4514170): iop65l_w walks the kernel's DMA transfer-control blocks to
   derive the 8 SPORT autobuffer bases at runtime (TX0=0xC342, RX0=0xC362, etc.).
 - Verified the audio contract by probe: 1 stereo frame per IRQ0 (2 out words/int ->
   44.1kHz/sample, tick rate is right), in/out are contiguous 8-frame rings 0x20 apart,
   default passthrough copies in->out. SPORTs externally clocked; audio via DMA not PIO.
 - Step 3 (routing): kn7000_dsp_bridge_device between TG and speakers; its stream and the
   dsp_audio_tick swap frames through two rings (feed TG->DSP input, take DSP output->
   speakers). Transparent when the DSP is off (no regression, verified).

CFG GOTCHA (cost hours): the CONFIG bits are SEPARATE PORT_CONFNAME fields -> the cfg
needs one <port> line PER bit with its own mask: bit0 (DSP) = mask "1" value "1", bit1
(TG sound) = mask "2" value "2". A single mask="3" value="2" line does NOT set bit1.

RESOLVED (commit f83a6a1): the "different sound" was a ring-MISALIGNMENT artifact, now
fixed. Root cause: without the modelled SPORT DMA advancing the autobuffer index, the
kernel writes its output frame to a FIXED position each IRQ0 (tapped: always 0xC350/
0xC351) and reads input 0x20 below (0xC370/0xC371) -- NOT a cycling ring. The tick
walked pos 0..7 so only 1/8 hit the real slot (~0.125 == the measured 0.126 attenuation)
-> the rest stale -> attenuation + clicks. FIX = fixed addresses TX0+0xE (out) / RX0+0xE
(in). Now spectrally VERIFIED CLEAN: DSP-on == DSP-off tone within 1% (RMS + fundamental
ratio 1.01), no added HF -- a faithful dry passthrough through the DSP. Bridge sync also
hardened (bounded rings, prime+hold-last, no bypass/DSP mixing). How to A/B compare:
capture off = CONFIG bit1 only, on = bit0+bit1, both press "Key C4" at t>=16, -wavwrite,
Goertzel at 262 Hz (see the /tmp analysis this session).

NEXT / open:
 - AUDIBLE EFFECT: the default slot (PM 0x8400) is a dry copy, so off==on. FINDING
   (tapped PM 0x8400-0x8420 writes over a boot+note): ZERO writes -- the firmware does
   NOT upload any effect microprogram by default, so the DSP runs the dry passthrough
   (correct, matches off==on). To hear reverb/chorus the firmware must be driven to
   SELECT an effect (host DspEffectSelect -> uploads rec05-76 to PM 0x8400). NEXT:
   figure out the trigger -- likely a panel/effect selection, and it may be gated by the
   SD-menu boot state (the TG gate lands on the SD menu, not the play screen, where
   effect selection normally happens). When an effect IS loaded, re-derive the +0xE
   output offset (it's the passthrough's I4 landing; a real effect may write elsewhere --
   tap the TX0 region write address as done this session).
 - SD-card menu still shows when the TG gate is opened (known: kn7000-sd-strap-gate) --
   separate issue, sound works regardless of screen.
 - Dry/wet mix + SPORT1 role: only if the output is 100% wet (hardware may sum a dry
   bypass). PM/DM 40-bit data path unmodelled (fine unless an effect enables it).

## ★★ DSP DRC ENABLED 2026-07-10 (Felipe: "port the ops to sharcdrc.cpp — yes let's do it!")

The SHARC now runs on MAME's recompiler, not the interpreter: DSP-on went from
~36-48% to ~72% real time — essentially the DSP-off speed (the machine is now
MN10300-interpreter-bound, the SHARC is near-free). Committed kn7000_mame 3fa7e3a,
published. Felipe also provided the ADSP-21065L Technical Reference PDF (in the repo
root) — used it to confirm the 21065L memory map (internal SRAM 0x8000-0x1FFFF,
external memory 0x20000+, IVT at 0x8000).

What the DRC needed (MAME's SHARC DRC was 2106x-only; sharcdrc.cpp + sharcfe.cpp now
overlaid too, symlinked by build.sh):
 - `m_dsp->enable_recompiler()` in the driver (the DRC is opt-in per driver).
 - Interrupt vectoring: hardcoded 0x20000 -> `irq_vector_base()` (0x8000).
 - Front-end loop map: `l2 == 1` assert -> device internal-memory base (so the
   kernel's DO..UNTIL loops compile).
 - Internal-SRAM fast path (m_blocks, unpopulated on the 21065L): keyed off new
   `drc_sram_base()`; 21065L returns out-of-range so all accesses go through the
   address map. THE SEGFAULT was the kernel clearing an external delay buffer at
   0x20000, which the 2106x path treated as internal SRAM -> null m_blocks store.
 - Mapped the 21065L's real memory: internal SRAM 0x8000-0x1FFFF + external SDRAM
   0x20000-0xFFFFF (delay lines; also needed for F.3 audio).
 - Fixed-point multiplier/MAC ops (single + multi function): the DRC stubbed them
   to abort; `generate_unimplemented_compute` now falls back to the interpreter's
   COMPUTE() for the one instruction (fast-ireg flush + astat pack/unpack around
   the C-call). Blocks compile instead of forcing whole-device interpretation.
 - `BIT TOGGLE ASTAT` (main-loop ping-pong flag): implemented (was abort).
Perf caveat is RESOLVED. Remaining SHARC-DRC follow-ups (not blocking): self-
modifying-PM invalidation is disabled for the 21065L (fine — effect programs are
host-uploaded, not SHARC-written; but effect-SWITCHING may need block invalidation
on the host PM write); PM/DM internal-SRAM aliasing not modelled (filter state read
via PM 0x9800 currently reads its own PM RAM, not the uploaded DM coefficients) --
matters for correct AUDIO (F.3), not for running.

## Cron-tick verification (2026-07-10, post-F.2)
Published binary re-verified: `kn7000-emulator/kn7000` is byte-identical (md5
e50d8ac2…) to the validated build-tree binary; a fresh default-config run boots
cleanly to the home screen (PMEM A-, no faults). Artifact healthy. NOTE: the cron
prompt's "awaits Felipe's greenlight / plateau" context is STALE — Felipe greenlit
the DSP LLE and F.1+F.2 are DONE (below). F.3 (SPORT audio) is next but has an
external dependency (the ADSP-21065L Hardware Reference is NOT in the repo — only
the 14-page EP datasheet) needed to pin the SPORT-DMA memory map, so it is NOT a
safe unattended start (guessing the map would risk wrong audio). Leave F.3 for a
focused session / Felipe's input on scope + the ~5% perf tradeoff. See the F.3 plan
+ open question in notes/sound-subsystem-plan.md.

## ★★ MILESTONE COMPLETE 2026-07-10 — DSP effects kernel BOOTS & RUNS (F.1 + F.2)

Felipe greenlit the DSP LLE ("go build it", "go ahead with F.2"). The recovered
ADSP-21065L (IC306) effects kernel now host-boots and runs to its IRQ0-driven main
loop inside MAME — no faults. Committed kn7000_mame `3aca274`, published.

- **F.1** (earlier): `adsp21065l_device` SHARC variant added (fork of MAME's 2106x
  core: sharc.h/.cpp overlaid, symlinked by build.sh; internal PM 0x8000-0x8fff,
  DM 0x8000-0xffff + IOP stub). KN7000 boots with it present (halted).
- **F.2 upload**: `dsp_data_w` decodes the host-boot stream — 8 blocks / 805 words
  (4 DM: 9800/9C40/C000/C302, 4 PM: 8000/8300/8400/8D00), framed reg-0x40 addr /
  reg-0x1C block cmd (0xA1 PM-commit, 0x41 DM-commit, 0xA0 end) / index-0x04 stream
  (48-bit PM = 3x16 LSW-first → wbuf[2]:[1]:[0]; 32-bit DM = 2x16 low-first).
  Uploaded words match the disasm EXACTLY (PM 0x8005/0x807a/0x8300). **RELEASE point
  = the final _bare_ 0xA0** (block-open flag: 0xA1/0x41 opens, 0xA0 closes; a 0xA0
  with no open block and words>0 is the "go"). The FIRST 0xA0 is a 0-word reset
  handshake — releasing there ran the DSP into garbage (the earlier bug).
- **F.2 SHARC-core fixes** (sharcops.hxx now also overlaid): `irq_vector_base()`
  virtual = 0x8000 for the 21065L (taken IRQ vectors to base+which*4; IRQ0=0x8020);
  `reset_pc()` = 0x8004 (MAME primes daddr=pc+1 and executes daddr first → first-exec
  0x8005 = JUMP init, skipping the boot-wait IDLE at 0x8004, which our glue has
  already satisfied). Implemented the missing fixed-point **multiplier/MAC ops** the
  kernel's biquad-seed routine uses: single-function MRF/MRB = Rx*Ry and MR ± Rx*Ry
  (signed/unsigned, integer/fractional, MR select, round); multi-function parallel
  MAC+ALU multiop 0x06, 0x08-0x16, 0x20-0x2f. (These were genuine gaps in MAME's
  SHARC interpreter — general, not 21065L-specific.)
- **F.2 driver tick**: `dsp_audio_tick` (emu_timer) pulses the SHARC's IRQ0 at a
  provisional **44.1 kHz** (`DSP_FRAME_HZ`) once the kernel is released. Only ASSERT
  is needed (the core auto-clears the pending bit when it TAKES the interrupt). This
  stands in for the SPORT/codec frame sync until F.3.
- **Validated**: with CONFIG bit0 "Effects DSP host stub" ON, the DSP reaches its
  main loop — distinct PCs 0x8021 (IRQ0 ISR: R13=1 "frame arrived"), 0x807b/0x80f8
  (mainloop), no faults over 12 s. Default boot (stub OFF, DSP halted) still reaches
  the home screen unchanged (screenshot verified).
- **Perf caveat**: the SHARC runs on MAME's INTERPRETER at ~5% realtime with the
  44.1 kHz tick. So the stub stays **opt-in / default OFF**. Speeding it up (SHARC
  DRC — needs my mult ops + vector-base/reset_pc ported to sharcdrc.cpp; and/or a
  lower real IRQ0 rate once the SPORT block size is known) is a follow-up.

### NEXT — F.3 SPORT audio (make the effect actually process the audio stream)
Model the SHARC's serial ports (SPORT) so audio flows TG output → DSP → DAC, and
replace the synthetic 44.1 kHz IRQ0 tick with the real SPORT/codec frame sync that
paces the kernel. Kernel refs: init 0x8D00 sets up SPORTs/SDRAM/DMA; IRQ0 ISR 0x8020
sets R13=1; mainloop 0x807a consumes a frame. See notes/sound-subsystem-plan.md (F.3)
and the DSP disasm (kn7000_disassembly/disasm/dsp/rec04_kernel_*.asm).

What shipped:
0. Sound is an OPT-IN machine-config switch: CONFIG bit1 "Tone generators /
   firmware sound (experimental)", DEFAULT OFF. OFF = known-good home-screen boot,
   silent (gate 0x7F) — NO regression, verified. ON = gate open + sound, but boot
   then rests on the SD menu (paused SD subsystem). Enable via Tab -> Machine
   Configuration, or cfg CONFIG value=2. (Same pattern as the DSP host-stub switch.)
1. TG gate opened (when the switch is ON): io_r(0x98070000) sets strap bits 1,2
   (TG present) -> gate flag 0x500ce380 = 0x40 -> firmware programs voices per note.
2. SD Card menu at boot: opening the TG gate advances boot into the SD subsystem,
   which is separately PAUSED (notes/sd-card-emulation-plan.md), so it lands on the
   SD Card menu instead of the home screen. NOT caused by the CPSD probe (verified:
   menu shows with the probe both on and off) and NOT by card-detect ("no card"
   forced -> still SD menu). This is a known SD-HLE gap, tracked separately. Sound
   and the key bed WORK regardless of the displayed screen (melody renders correct
   pitches from the SD-menu boot state).
3. kn7000_tonegen_device synthesizes from the firmware's TG writes:
   - pitch from class 0x2401: note = 60 + (data - 0xC838)/1024  (+0x400/semitone,
     C4=0xC838=MIDI60). VALIDATED spectrally: C4/E4/G4/C5 fundamentals = 262/330/
     392/523 Hz (dominant), no clipping.
   - note-on = 0x2401 write; note-off = 0x0001=0xC000 mute; per-voice attack/decay
     envelope (self-limiting since this sound rings until stolen).
   - placeholder SINE timbre (wave ROMs undumped).

### REMAINING / NEXT (refinements, not blockers) — for the cron loop to continue
DONE: gate fix, firmware-driven synth, pitch decode, opt-in switch (home-screen boot
preserved + verified), publish, website sound page, blog Part 10, memory. DONE (cron
tick 2026-07-10): exponential voice decay (natural, verified); corrected
notes/tg-voice-register-semantics.md with the dynamic capture (pitch=0x2401,
note-off=0x0001=0xC000 -- superseded the wrong static guesses). Remaining, in value order:
1. Quantitative envelope/level decode: the per-voice group-0x00 registers (0x0000-
   0x000D, key-scaled: 0x0001 C4=5400/C5=6300; 0x0004-0x000A = AE00/2C00/9900/35E8/
   25B0; 0x2009=5FFF level) encode the firmware's real attack/decay/sustain rates +
   level. Decode the rate/level encoding (cross-ref kn5000-docs tone-generator.md
   ToneGen_WriteVoiceParams ~L411-444) and drive the synth envelope from them instead
   of the fixed exponential. Also velocity (kbd_push high byte -> level).
2. Velocity: the firmware passes velocity (kbd_push high byte); map it to level.
3. Effects DSP: Phase A host stub verified; next is running/emulating the SHARC
   effect on the audio stream (reverb/chorus) — large; see notes/sound-subsystem-plan.md.
4. Placeholder wave ROMs for a richer-than-sine timbre (kn7000_disassembly/tools/
   make_placeholder_waveroms.py) — but the tonegen would need to honour the firmware's
   sample-select writes to be meaningful; low priority vs the honest sine.
5. SD subsystem (separate, PAUSED): finishing it would let boot reach the home screen
   WITH sound enabled (removing the opt-in trade-off). See notes/sd-card-emulation-plan.md.
6. Cross-model sound RE: INVESTIGATED, KN6000 audio DEFERRED (2 cron ticks 2026-07-10).
   KN6000 DOES drive its TGs live on key-bed notes (no strap gate; boots to play screen,
   no SD block). BUT its pitch is NOT extractable by register-diffing: class 0x5800 is a
   fine/detune field (clusters, non-monotonic), and the pitch-varying info is in the
   group-0x00 voice-param registers (0x0000/0x0004 move ~6-9/semitone, not clean) — a
   separate channel space + multisample. Cracking it needs STATIC RE of the KN6000
   note→pitch routine (unidasm on kn6000_program; analog of KN7000's 0x4844812D) or the
   undumped IC13/IC14 table + wave ROMs. Do NOT enable kn6000/kn6500 sound with a
   wrong-pitch guess. Full notes: sound-cross-model-kn6000-kn6500.md. KN5000/KN2400
   still unchecked.

DONE (cron tick 2026-07-10 #3): honor the firmware's per-voice LEVEL (class 0x2009) in
the synth (normalized so the default 0x5FFF = unity → current sound unchanged, verified;
softer/louder levels now flow through). Groundwork for velocity/voice-balance.

### PLATEAU NOTE — the KN7000 sound is in a strong, complete state; remaining work is
### either large multi-session or blocked. Honest triage:
- **Envelope RATES (attack/decay/sustain): BLOCKED.** The KN5000 doc confirms the
  hardware EG rate→time law is UNDOCUMENTED (its own emulation punts to a linear fade).
  Decoding it needs hardware observation or deep RE we can't do from the register values
  alone. Current exponential decay is a reasonable honest placeholder. Do not guess rates.
- **KN6000/KN6500 audio: DEFERRED** — pitch needs static RE of its note→pitch routine
  (see sound-cross-model-kn6000-kn6500.md). KN5000/KN2400/KN2600 unchecked.
- **SD subsystem: USER-PAUSED** (memory kn7000-sd-strap-gate). Fixing it would let KN7000
  boot to the home screen WITH sound (removing the opt-in switch) and unblock sound-
  selection — but respect the pause; do not sink ticks into it autonomously.
- **Real timbre: ROM-BLOCKED** — the 4 PCM wave ROMs are undumped.

## ★★★ EFFECTS-DSP LLE GREENLIT BY FELIPE (2026-07-10) — BUILDING IT (Phase F)

Felipe said "greenlight the DSP LLE — go build it." Phased build; verify build+boot at each
step; never break the working KN7000. Key facts (all validated, see sharc-lle-assessment.md):
MAME has the 2106x SHARC core (ADSP21062/21060); 21065L internal map PM 0x8000-0x8Dxx / DM
0x9800-0x9Cxx + 0xC000-0xC3xx / SDRAM 0x80000+; IOP stub set 0x08-0x0F,0x28-0x3C,0x53-0x7B,
0xE0-0xFC; host-upload protocol reg0x40=addr, 0x1C=0xA1 PM/0x41 DM (validated live, 258 blocks);
ext-port DMA ch 8/9. CRITICAL CORE FINDING: adsp21062_device::m_blocks is PRIVATE and pm_r/pm_w
use a block-interleave scheme hardcoded to the 21062 geometry -> the 21065L variant CANNOT live
in kn7000.cpp; it needs the SHARC core FORKED into the repo (MN10300 precedent:
kn7000_mame/src/devices/cpu/<core>/ symlinked into kn7000_mame_build/src/...).

PROGRESS:
- F.1-STEP-0 ✅ DONE + committed (kn7000.cpp) + PUBLISHED: instantiated ADSP21062 in kn7000()
  (host-boot mode, idle). KN7000 boots to the home screen, no fatalerror, SHARC compiled+linked.
  BUILD LEARNINGS (important, in build.sh now / cpu.lua):
    * Adding the SHARC needs REGENIE=1 + USE_QTDEBUG=0 (REGENIE else fails on Qt 'moc').
    * LATENT MAME BUG fixed: cpu.lua DRC_CPUS names the SHARC "ADSP21062" but its flag is
      "ADSP2106X" -> SHARC-only builds fail to link drcuml. build.sh now idempotently adds
      "ADSP2106X" to DRC_CPUS.
    * Canonical build = kn7000_mame/build.sh (SOURCES=kn7000.cpp,kn1500.cpp; registers both in
      mame.lst). After REGENIE churn, a STALE libmame_kn7000.a (only kn7000.o, missing kn1500.o)
      caused 'undefined driver_kn1500' -> fix = delete build/.../bin/.../mame_kn7000/libmame_kn7000.a
      + generated .../drivlist.o, rebuild WITHOUT REGENIE. So: REGENIE once to add a device, then
      rm the stale mame archive, then plain make.
- F.1-STEP-1 ✅ DONE + committed + PUBLISHED: forked sharc.h/.cpp into the overlay
  (kn7000_mame/src/devices/cpu/sharc/, symlinked by build.sh). Added **adsp21065l_device**:
  plain-RAM 21065L maps (PM map(0x8000,0x8fff).ram(); DM map(0x8000,0xffff).ram() covering
  0x9800/0xC000; IOP 0x00-0xFF -> iop65l_r/w stubs returning 0/accepting). Changed m_blocks
  required_->optional_shared_ptr_array. Driver now instantiates ADSP21065L (host-boot, idle).
  VERIFIED: KN7000 boots to home screen, no fatalerror. **F.1 IS COMPLETE — the SHARC variant
  exists in MAME and integrates.** (No REGENIE needed for STEP-1 — new device type in an
  existing source file; just symlink + plain make.)

  === F.2 (NEXT) — driver host-boot glue: actually load + run the DSP program ===
  The firmware host-boots via 0x98000000(index)/0x9C000000(data): reg 0x40=target addr,
  reg 0x1C=0xA1(PM commit)/0x41(DM commit)/0xA0(end), then streams words (3x16 per 48-bit PM
  word via fw 0x484050B8; 2x16 per DM word via 0x4840511A). PLAN for kn7000.cpp dsp_data_w /
  io_w (extend the existing Phase-A stub):
    1. Track the DSP index writes: reg 0x40 -> latch m_dsp_dl_addr (2x16); reg 0x1C -> m_dsp_dl_mode
       (0xA1 PM / 0x41 DM / 0xA0 end).
    2. On data-port writes while mode=PM: accumulate 3x16 -> one 48-bit word -> write to the SHARC
       PM at m_dsp_dl_addr via m_dsp->space(AS_PROGRAM).write_qword(addr<<?,word) [addr in words;
       program space is -3 granularity -> check the byte/word addressing]; addr++. Mode=DM:
       accumulate 2x16 -> 32-bit -> m_dsp->space(AS_DATA).write_dword; addr++.
    3. On reg 0x1C=0xA0 (end/sync): the kernel record is fully loaded -> RELEASE the SHARC from
       host-boot so it runs. Check how BOOT_MODE_HOST releases (model2.cpp copro_boot clears
       INPUT_LINE_HALT; sharc.cpp device_reset host path). May need set_input_line(INPUT_LINE_HALT,
       CLEAR) or the sharc host-boot-done path. Kernel entry = reset vector (SDRAM POST first).
    4. VERIFY: tap the SHARC PC (m_dsp->state) advancing through 0x8xxx; no iop fatalerror (the
       iop65l stubs handle it); ideally the SDRAM POST reg 0x0B readback. Gate all this behind the
       existing CONFIG bit0 "Effects DSP host stub" switch (default OFF) so it's opt-in until F.3.
  CAUTION: the driver's 0x9C bank currently maps dsp_data_r/w only for 0x9c000000-3 (the rest is
  lcdbuf RAM). The program-space write granularity (-3) means PM addresses may be byte vs word --
  verify with a small test (write one known word, read it back via m_dsp->space).
  === F.3 (after F.2) — SPORT audio: TG output -> DSP -> DAC (the big new piece) ===
- F.1-STEP-1: fork sharc.h+sharc.cpp into the repo, add adsp21065l_device (21065L PM/DM maps +
  IOP stubs), swap m_dsp to it.
- F.2: driver host-boot glue (latch reg0x40 addr; on 0x1C 0xA1/0x41 DMA the streamed words into
  the SHARC internal PM/DM; release it). Verify the kernel runs (PC advances, no fatalerror).
- F.3: SPORT audio (TG output -> DSP -> DAC). The big new piece.

### DECISION POINT FOR FELIPE (reached 2026-07-10, cron tick #5) [SUPERSEDED — greenlit above]
The sound subsystem is at a strong, complete plateau: the KN7000 makes firmware-driven,
correctly-pitched sound (opt-in switch; home-screen boot preserved), fully documented
(website + blog Part 10). The ONE remaining big piece — the effects-DSP LLE — is now
FULLY SPEC'd and ready to build (memory map + IOP set derived; MAME SHARC core confirmed),
but it is a LARGE, shared-MAME-core effort (new adsp21065l device variant + SPORT audio
from scratch) whose payoff is a reverb/chorus on the placeholder sine until the wave ROMs
are dumped. Autonomous cron ticks have (correctly) NOT undertaken that shared-core surgery
unattended — the risk of leaving the build broken overnight outweighs it, and it deserves
Felipe's explicit go-ahead. **When Felipe returns: decide whether to commit to the DSP LLE
(F.1-F.3).** Everything is ready so it can start fast (see notes/sharc-lle-assessment.md §5
+ IOP set).

Safe SMALL items a cron tick CAN do autonomously without that decision (pick one if
resuming): ~~validate the host-upload path~~ DONE (tick #6 — runtime upload cross-validates
the §5 memory map + the F.2 protocol; see sharc-lle-assessment.md + tools/dsp_upload_capture.lua);
~~cross-model KN5000 sound check~~ DONE (tick #7 — §6 of sound-cross-model-kn5000.md resolves
the KN5000 hypotheses against the working KN7000; cross-model sound docs KN5000/6000/6500 now
complete); minor doc/website polish; re-verify the published binary.
Avoid: risky shared-core changes, the user-paused SD subsystem, wrong-pitch guesses.

DONE (tick #9, 2h cron): FINAL QA of the PUBLISHED deliverable (kn7000-emulator/, run as
Felipe will). Default boot = home screen, gate 0x7F silent (no regression); switch ON (CONFIG
bit1) = correct-pitch sound C4/G4/C5 = 262/392/523 Hz, no clipping. Confirmed the publish
packaging (binary+roms+run.sh) works end-to-end; no leftover cfg (default stays OFF). Nothing
else to do this tick — plateau holds.

CRON CADENCE (tick #8): slowed the autonomous cron from every-20-min to **every 2 hours**
(job c0d0df57) during the plateau — the safe-small-item menu is nearly exhausted and the big
item awaits Felipe. The 2h prompt says: do at most ONE genuinely-useful safe item per tick, or
nothing. Felipe can ask for a faster cadence anytime; his return is a normal message that
resumes work immediately regardless of cron timing.

DONE (tick #8): brought the persistent memory current — the kn7000-sound-subsystem memory
still said "awaiting Felipe's review / run the TG diagnostic" (badly outdated) and cited the
wrong pitch class (0x3000); corrected to "KN7000 sings, pitch=0x2401, DSP LLE awaits greenlight",
and fixed the MEMORY.md index lines. (Memory persists via the filesystem; no git needed.)

NOTE (tick #7): the safe-small-item menu is nearly exhausted and the sound subsystem is at a
strong, complete, well-documented plateau. The remaining substantial work (effects-DSP LLE)
needs Felipe's greenlight on the shared-core effort. Future autonomous ticks: prefer
re-verifying the published binary / minor polish over inventing marginal work; do NOT start
the shared-core SHARC build unattended. The KN7000-sings milestone + all RE/validation is
committed and published; everything is ready for Felipe's DSP decision.

### NEXT MAJOR EFFORT (pending greenlight) = the EFFECTS DSP (Phase F, LLE) — in the cron goal.
Feasibility CONFIRMED this tick: MAME has a 2106x SHARC core (ADSP21062/21060, same ISA as
the 21065L); the 80 DSP programs are recovered+disassembled. Full analysis in
notes/sharc-lle-assessment.md. It is a LARGE multi-session build (the 21065L I/O
personality + SPORT audio have no MAME precedent), so tackle it in phases across ticks:
  F.1 — add an `adsp21065l_device` subclass in src/devices/cpu/sharc/ (adsp21060 pattern):
        21065L internal PM/DM maps, IOP regs as LOGGED stubs (replace the fatalerror
        defaults at sharc.cpp:367/443). Wire it into the kn7000 SUBTARGET build; verify it
        BUILDS and the KN7000 still boots (device present, unused). SAFE, additive.
        >>> PREREQUISITES DONE (cron tick 2026-07-10 #4), both derived from the recovered
        program (no full datasheet needed) — see notes/sharc-lle-assessment.md §5 + IOP set:
        - Internal memory map: PM (48-bit) 0x8000-0x8Dxx (effects @0x8400); DM 0x9800-0x9Cxx
          + 0xC000-0xC3xx; IOP 0x00-0xFF; external SDRAM (plain .ram) at 0x80000+.
        - IOP stub set (offsets the program touches; base core fatalerrors on the NEW ones):
          handled: 0x02,0x08-0x0F(host mailbox, heavy),0x20; NEW stubs: 0x28-0x3C, 0x53-0x7B,
          0xE0-0xFC; system IMASK/IRPTL modeled by core. Ext-port DMA = ch 8/9 (not 6/7).
        So the SUBCLASS CAN BE WRITTEN DIRECTLY next tick. NOTE the caveat recorded in the
        assessment (F.3 SPORT audio is large; DSP processes the placeholder sine until wave
        ROMs are dumped) — a good point for Felipe to confirm committing the effort; but F.1
        itself is safe/additive and proves the recovered DSP programs run on MAME's SHARC.
  F.2 — driver boot glue: host-upload the recovered DSP program via the 0x98000000(index)/
        0x9C000000(data) port (model2.cpp copro_ctl1_w/external_dma_write pattern). Verify
        the SHARC loads the kernel record and runs (PC advances, no fatalerror).
  F.3 — SPORT audio: stream TG output → DSP → DAC through the (new) serial-port model.
        Verify the effect processes audio. This is the genuinely new, biggest piece.
Each phase is one-or-more ticks; commit + verify build/boot at each step; never break the
working KN7000 driver. If a tick can't safely complete a phase, do a bounded sub-step and
record where it stands.

## ★ BREAKTHROUGH 2026-07-10 — the TG gate is found and validated

**Root cause of "no sound": a TG-enable gate flag `0x500ce380` in library RAM
(0x7F = disabled, 0x40 = enabled), tested by ~30 library wrappers that suppress
every per-voice write when it is 0x7F.** It is set from a **probe of the hardware
strap word `0x98070000`** at firmware `0x484d7713`: it tests bit1 (0x02) and bit2
(0x04). If bit1 is CLEAR the probe returns 3 = "no TG" and the gate stays 0x7F.

The MAME driver's io_r returns `0x8000 | (rearsw & 0x1000)` for `0x98070000`
(kn7000.cpp ~line 559) → bits 1,2 are zero → probe = 3 → **gate closed forever**.
The real KN7000 HAS tone generators, so those strap bits must be set.

VALIDATED live (Lua read-tap forcing `data | 0x0006` on 0x98070000):
- gate flag `0x500ce380` becomes **0x0040 (ENABLED)**.
- On a key press the firmware now WRITES TG voice registers: **class 0x3000 =
  13-bit pitch** (C4→0x0BE8, E4→0x0E52…), classes 0x0001/0x0002 = per-voice
  level/env, from PC 0x4C036FDD. TWO voices allocated per note (dual-layer sound).
  Previously: zero. This is "the firmware driving the notes."

CONSEQUENCE (observed by Felipe on video): with the gate open, boot progresses
further and lands on the **SD Card menu** instead of the home screen. Bits 1,2 are
read ONLY by the TG probe (all 14 strap readers mapped), so the SD menu is NOT a
strap-bit side effect — it is the known-flaky SD subsystem now being reached
because sound-init completes. Must handle so boot reaches the play screen.

Subagent full map saved (region2 == 0x4C library image; runtime = flash+0x0384702F).
Key RAM: per-voice HW shadow `0x500ca0b0` stride 0x84 (+0x54 = pitch dword, low 13
bits → class 0x3000); voice state `0x500af940` stride 0xB4; gate `0x500ce380`;
voice-active bitmap `0x500d288c`. TG write primitive: voice<0x40→SUB(0x98050000),
≥0x40→MAIN(0x98040000); reg addr = (voice<<4)|classIndex.

### NEXT (revised, in priority order)
1. Apply the strap fix in the driver (set the TG-present bit(s) on 0x98070000).
   Decide bit1-only (probe=2) vs bits1,2 (probe=1) — both open the gate; pick the
   hardware-accurate one. Rebuild, verify voice writes appear WITHOUT the Lua patch.
2. Keep boot on the play/home screen despite the gate being open: investigate why
   the SD Card menu auto-opens (likely SD card-detect / CPSD); make boot land on
   the play screen (e.g. SD card absent by default). See memory kn7000-sd-strap-gate.
3. Wire the tonegen to SYNTHESIZE from the real TG voice writes: decode class
   0x3000 pitch (map 13-bit code→Hz), key-on/level (0x0001/0x0002), gate voices.
   Replace the Stage-0 kbd_key sine with firmware-driven voices. Publish binary.
4. Calibrate the pitch code→Hz map from several notes; handle the 2-voices-per-note.

## IN PROGRESS — Stage 2 gating question (SIGNIFICANT PROGRESS 2026-07-09)
Does the FIRMWARE emit TG voice writes when a keybed note is played? Answer so
far: **NO — the note is fully received but never becomes a voice.** Established
by a series of Lua tap diagnostics (all runs WITH video):

CONFIRMED end-to-end input path:
- `field:set_value()` on `:KEYS0` DOES fire `kbd_key` (bring-up sine audible in
  -wavwrite at the press times; peaks ~4100-4265).
- The firmware CONSUMES every note-on/off from the FIFO at 0x98050004: PC
  0x484480A3 read note 60/64/67 vel 100 then 0 (C4/E4/G4). 6/6 consumed.
- FIFO poll histogram: ONLY the program.asm reader 0x484480A2/B7 polls at runtime
  (~67k polls each); region2's own reader at 0x487f11a6 does NOT poll during play.
  => the "double-reader steals the note" hypothesis is DISPROVED.

CONFIRMED the play->TG path never fires:
- During the press window: **0** TG writes of ANY non-idle class. The only
  non-idle TG writes in the whole run are BOOT-TIME:
  * groups 0x04/0x0C (channel-config sweep, data 0) from 0x4C037023/0x4C03702F
  * group 0x8000 params (idx 8/A, e.g. a=8008 d=0300, a=800A d=7F00) 426x at t=0
    from 0x4C036FBA  -- boot voice/param init, NOT note voicing.
  * 0xFC08..0xFC0B idle refresh (~390x each) continuously.
- My earlier assumed pitch class 0x2000/0x3000 and key-on 0x4014 NEVER appear at
  runtime. The low-level TG driver lives in the **0x4C region** (0x4C036xxx-
  0x4C037xxx, self-loaded lib ROM); region2 (0x487eff80) is a second TG writer.

DATA FLOW so far: keybed FIFO -> 0x484480A2 -> 0x4844812D (note->pitch via tables
0x48731534 / 0x487314F4/F6/F8, div-by-12; writes a per-key struct via a0; does
NOT touch TG). Then region2 flush 0x487eff80 emits ONLY idle. So the missing link
is the VOICE ALLOCATOR: something must assign the note to a free TG channel, load
the current sound's waveform/params, set pitch+key-on. That never runs / is gated.

LEADING HYPOTHESES for the gate (to resolve): (a) no playable Sound assigned to
the keyboard part in the emulated boot state (cf. known 8-Beat-1 / .AST / style
templating bugs); (b) a "sound-engine active / part-enabled / local-control"
flag never set; (c) play path waits on a stubbed subsystem (DSP / sound handshake).
A background subagent is statically mapping region2's flush + the gate (RAM
addresses + test instruction). Await it, then target the specific flag/struct.

MORE STATIC DETAIL (2026-07-10):
- The 0x4C-region TG driver == program_region2.asm ROM image. Mapping:
  lib X == program ROM 0x487B8FD1 + (X - 0x4C000000). So runtime 0x4C036F80 ==
  ROM 0x487EFF80. The block 0x487eff69..0x487f0078 is a set of low-level TG
  register-WRITE PRIMITIVES: channel<0x40 -> SUB(0x98050000), >=0x40 ->
  MAIN(0x98040000); reg value built as (chan<<20)|hi|lo. Idle refresh & boot init
  just call these leaves. The voice-flush LOOP/ALLOCATOR is their CALLER (subagent
  is finding it).
- Keybed task 0x48448015 (RTOS-scheduled, no direct callers) reads FIFO via
  0x4844807c/0x484480a2, decodes each note with 0x4844812d into a STACK-LOCAL
  struct (sp+0xc), gathers up to 16 notes into a stack array (sp+0x12), and
  RETURNS without voicing. Flag 0x50007768 and latch 0x501496a2 are internal
  hold/sustain state (self-consumed). 0x50007764 = a pending-count gate: when
  nonzero it calls 0x48448206 instead of reading the FIFO. => this path drains
  keybed events; the actual note->voice allocation is a DIFFERENT task that is not
  emitting -> strongly consistent with hypothesis (a)/(b): no playable performance
  loaded at boot, so the voicer allocates nothing.

DECISION: do NOT rabbit-hole further on the boot-performance gate in parallel
with the subagent (it overlaps the known .AST/style/8-Beat-1 boot bugs, a large
separate effort). Two productive tracks that are UNBLOCKED by the gate:
  T1 (this session): build+verify the tonegen's TG voice-register -> audio
     synthesis engine, driven by INJECTED voice writes (Lua simulating what the
     firmware would write), so the synth path is proven end-to-end and ready.
     Requires reconstructing the TG register map from the DRIVER CODE (subagent
     result), not runtime observation.
  T2: Stage 1 — load placeholder wave-ROM bank-0 samples into the tonegen so it
     plays a wavetable timbre instead of a pure sine (independent, committable).

## NEXT (in order)
1. Re-run /tmp/ktd.lua diagnostic WITH VIDEO; read RESULT + FIFO consumed count.
2. If firmware consumes the note but writes no voice regs → the sound engine is
   in a non-playing UI state; investigate what selects a playable Part/voice
   (Chord Finder / SOUND select). If it never consumes → input path or firmware
   key-scan not reached; inspect how the real key matrix reaches the firmware.
3. Once firmware-driven voice writes appear: map pitch (0x2000/0x3000 13-bit) →
   Hz and key-on (0x4014 strobe) → note gate; drive the tonegen synth from the
   real voice writes (replace the direct note_on tap). Read placeholder wave
   bank-0 samples (Stage 1) for timbre.
4. Rebuild, publish-binary, commit. Update this file + website + memory.

## Plan of record
`kn7000_mame/notes/sound-subsystem-plan.md` (rev2 + execution log). The full
multi-phase plan (A..H) lives there; follow it in order, deferring phases that
need the physical unit (G/H).

## 2026-07-19 — disassembly CONVERT track: Techni-Chord engine (maincpu)
DONE (kn7000_disassembly a3cb3f5, kn5000-docs d25bb31, blog part 47):
- CONVERT set 66 -> 84 functions, byte-match held at 100% throughout.
  Converted the complete Techni-Chord harmony engine: TechniChordCompute
  (0x48472EBA), all 14 voicing routines (0x4847304C..0x48473732), the off
  handler, TechniChordOrchestratorPart (0x48472E5B) and the aug/dim
  root-fold helper (0x48473766); gen_program_s.py now merges
  kn7000_manual.sym (manual names = region-1 split boundaries, *_entry =
  register-save `call` entries, FUNC_DOC comment blocks, FUNC_END caps).
- DISCOVERY: style param 0x8081 is stored in a LEGACY order, not GUI grid
  order — GUI maps through 14 halfwords @0x485EC940 (0,1,2,4,...,13,3);
  DUET 1 is stored LAST (param 13, grid slot 3). Docs page had
  OCTAVE/HARDROCK addresses shifted one routine; corrected + verified 3
  ways vs the users manual (REEDS=4-note matrix 0x485BBE64; unsplit trio
  = the 3 chord-independent fixed-interval routines; DUET 1 = CLOSE
  clamped to 1 note). KN6000 embeds the same pool+map.
NEXT maincpu convert target suggestion: the panel dispatch chain
(PanelTransaction/PanelTxState1-6/PanelRxState8/PanelButtonDispatch —
already named in kn7000_manual.sym and fully RE'd in
notes/panel-serial-protocol.md; boundaries now emitted by the generator),
or the SD state machine (notes in kn7000-sd-strap-gate memory + disk
worker RE).

## 2026-07-19 — disassembly CONVERT track: panel serial protocol + button dispatch (maincpu)
DONE (kn7000_disassembly d6028b6 / 2a81fa5 / 3ab87fd):
- CONVERT set 84 -> 111, byte-match held at 100% throughout. Converted the
  COMPLETE control-panel chain: PanelTransaction/PanelSignOnRequest/
  PanelStatusPoll/PanelWaitLinkIdle/PanelTxKick, the 3 ISRs (Atn/TxDone/Rx),
  transfer states PanelTxState1-6 + PanelRxState8-9 + idle/rearm, PanelTxPump,
  PanelErrorRecovery, PanelHeaderValidate, both decode pumps, PanelFrameDecode
  and PanelButtonDispatch -- each with a FUNC_DOC header citing
  panel-serial-protocol.md. ~70 new kn7000_manual.sym names cover the whole
  pipeline (FIFO primitives, latched-control handlers, GPIO switch scan incl.
  the 0x9CC00008 phantom-button source, event records, the 5 descriptor action
  types, PanelEventPost) + LibIntcEnable/Disable (0x4C03DCC8/0x4C03DD3F).
- DISCOVERIES this pass: (1) the state table 0x48613034 has 11 slots -- a
  previously undocumented RX state 9 (0x484ACCF6, reply-countdown/turnaround),
  idle slots 0/7/10 -> 0x484ACE38, and an unreferenced link-rearm 0x484ACE42;
  (2) two-entry-ABI corrections: PanelTransaction/PanelTxKick/
  PanelButtonDispatch canonical movm starts are at -3/-5/-5 bytes from their
  documented call entries (0x484AC2A5/0x484AC51E/0x484ADB54); (3) mode-B has
  its own wire-normalization table 0x48613620 (twin of 0x486135A0); (4) the
  runtime poll/dispatch entries PanelPollTick 0x484AD801 +
  PanelSwEventDispatchAll 0x484ADB29 have NO static caller/pointer anywhere in
  either ROM image -- runtime-registered.
- TOOLING: encoder gained and/or imm16,psw (FA FC/FD); the generator now
  repairs unidasm's F4-page LENGTH BUG (movbu register-indexed printed as one
  byte + phantom re-decode) from the ROM bytes. Converted source now has ZERO
  .byte escapes outside the annotated boot header (was 42) -- also cleaned the
  Techni-Chord matrix reads retroactively.
NEXT maincpu convert target suggestion: the SD state machine (disk worker
0x48551F8D + the 0x4854xxxx service cluster; notes in kn7000-sd-strap-gate
memory) or the tempo/TM5 chain (ISR 0x48447084, TM5 regs 0x340010x2, the
96-PPQN dispatch -- notes/tg-pitch-pipeline.md + sound-subsystem memory).

## 2026-07-19 — disassembly CONVERT track: the SD-card subsystem (maincpu)
DONE (kn7000_disassembly 14c72e1 / aca8abd):
- CONVERT set 111 -> 185 (+74), byte-match held at 100% throughout (incl.
  the clean-rebuild check); still ZERO .byte escapes outside the boot
  header. Converted the COMPLETE SD path: disk worker (DiskInit/
  DiskWorkerTask/blocking+async posters/SdWorkerCmdHandler), the card-init
  chain (SdCardInitFull CMD0/1/59/9/16/10 ladder + SdCardIdentify CSD
  parse), the whole SPI transport on 0x9805000C (send/recv, response/
  token/busy scanners, SdCommandSend, read/write block incl. CRC16 verify,
  SdDataCrc16 init-0, SdCmdCrc7), the slot GPIO/power layer, and the
  UI-side mount state machine (SdStateMachineTick states 0..4,
  SdCardInsertMsgHandler 0x107020BB, SdMountWorker/SdMountDone,
  SD_Get/SetState, mount gates). ~115 new kn7000_manual.sym names.
- DISCOVERIES this pass (upgrading the sd-card-emulation-plan notes):
  (1) SdCardInitFull retries with a THREE-RATE SPI clock fallback ladder
  (SdSpiClockSet modes 0xC/0xB/0xA = rate 1/2/3 + inter-byte gap 4/0xE/
  0x1C -> latch 0x9805000E = rate|0x80; per-rate gap count 0x50005200 is
  the spin bound in SdSpiSendByte); (2) the "wait helpers" guessed in the
  notes are really: 0x4854bb89 = clock-rate set, 0x4854c94d = CRC7,
  0x4854c1d5 = slot-sense busy wait (0x9cc00009 bit0), 0x4854bc8f = CS
  assert; (3) command frames carry {clockMode,respType,cmd[6]} — the
  clockMode field doubles as the SdSpiClockSet arg (CMD0/CMD1 run forced
  slow); (4) the boot-time 20,000-write storm on 0x9805000C =
  SdSlotDischarge's 0x00 flush train (rails off, presence latched into
  the 0x50005204 override); (5) hardware subtype (PanelSubTypeGet,
  0x484d7751): subtype 4 has NO slot GPIO bank (detect forced present,
  WP/sense 0) — MAME runs subtype 5 (strap 0x98070000 bits11:10=00),
  which is why the ICR-0x3400016c detect modeling works; (6) drive-letter
  class table: 'A'/'J'/'K' = floppy-class, rest = SD-class; (7) verified
  lib kernel helpers: LibDiv32 0x4C0019D5, LibTickSleep 0x4C03DD74 (lib
  tick 0x500d3c58), LibMsgSend/Receive 0x4C03D219/0x4C03D36D.
NEXT maincpu convert target suggestion: the tempo/TM5 chain (96-PPQN ISR
0x48447084, TM5 regs 0x340010x2 — notes/tg-pitch-pipeline.md + the
sound-subsystem memory) or the TG note path (note-on/release writers RE'd
in the forever-note fix, tg-pitch-pipeline.md).

## 2026-07-19 — DSP pool vs SHARC core: instruction-coverage audit (Felipe's question)
DONE (kn7000_disassembly 7a88e42): tools/check_sharc_coverage.py +
dsp/instruction-coverage.md — decoded ALL 6,499 PM words of the 80-record
effects pool (exact mirror of MAME's decode: sharcops_table.cpp top-level,
compute/shiftop/sysreg subfields) and cross-checked every used class
against the core the build links (overlay sharcops.hxx/sharcdrc.cpp/
sharcfe.cpp + stock compute.hxx; symlinks verified in kn7000_mame_build).
RESULT: 69 classes used; 66 native in BOTH interpreter and DRC; 2
DRC-fallback-only, correct but interp-called (FDEP-SE imm x34, ABS Rx
x28); ★ ONE GENUINE GAP: "Rn = SAT MRF (SF)" (single-function multiplier
op 0x09), ONE instruction, rec12 GATE REVERB @PM 0x8438, executed every
quiet-gate frame -> interpreter THROWS and the DRC fallback hits the same
throw. Selecting Sound-DSP Medium/Short/Long Gate (type 0x08) in the
emulator WILL fatalerror. Fix is a few lines in sharcops.hxx (oper==0
SAT corner of the general multiplier decode; DRC inherits via fallback);
in rec12 MRF is always 0 there so the correct result is simply R3=0.
NOT fixed (audit was no-core-changes). Also: ALUSAT interaction clean for
the whole used set (kernel sets MODE1 0x3000 once, no BR/SRCU bits ever);
section-C TRM deviations vs usage: C.4 SSFR-rounding UNREACHABLE (pool
has zero SSFR fixed forms), C.5 FIX-overflow masked by global ALUSAT,
C.3 AVG truncation = 17 records' output mixes at -0.25 LSB, C.1 circular
wrap still the staged-pending-approval item.
NEXT: implement SAT MRF/MRB (+RND siblings while there) in sharcops.hxx,
rebuild, load Gate Reverb live to confirm, then publish-binary.

## 2026-07-20 00:xx — SAT MRx IMPLEMENTED (Gate Reverb live-verified) + last two DRC fallbacks native; series = 12 patches (Felipe-directed)
DONE (kn7000_mame core + kn7000_disassembly checker):
- sharcops.hxx: full SAT MRx family (mul op 0x00-0x0F) in the general-
  multiplier oper==0 corner — TRM B-57: SI/UI/SF/UF x Rn/MR x MRF/MRB,
  integer forms clamp (64-bit MR model => fractional forms pass MR1
  through), flags MN(sign-in-format)/MV=0/MU(frac underflow)/MI=0.
  RND (0x18-0x1F) still throws (pool has zero uses).
- sharcdrc.cpp: native SAT MRx (mirrors interp exactly, liveness-gated
  flags); native ABS Rx (ALU 0x30, AV+STKY-AOS corner, translation-time
  ALUSAT clamp, AS=input sign); native FDEP(SE)-imm (shiftop 0x13,
  shift-by-zero routed through flag-generating ops). => the ENTIRE used
  pool (69 classes) is now 100% DRC-NATIVE, zero fallbacks in use.
- ORACLE: money.lua A/B on the rebuild = BIT-IDENTICAL
  (44b09b9d0eaae59d9a65e5b4f4e72ec0). publish-binary.sh done.
- LIVE GATE REVERB (the coverage report's crash scenario): SOUND DSP
  screen -> group "Reverb" (FIRST in center list) -> Short Gate. Upload
  lands in effect slot 2 (PM 0x8638 = 0000305003909300, Lua-verified);
  10+s + keybed note, no fatalerror, DRC AND -nodrc. Snapshots:
  scratchpad snap8/kn7000/0000-0003.png (0002 = Short Gate selected).
  GUI GOTCHAS (recorded in instruction-coverage.md + series notes):
  Gates are NOT on the hold-REVERB screen (2 pages Room..Stadium);
  group-list scroll-up = :cpanel:CPC_SEG9 0x01; pressing the stored
  preset with the insert OFF uploads NOTHING (short-press SOUND DSP
  CPR_SEG3 0x08 to toggle, or pick a different preset); slots =
  0x8400+unit*0x100, don't search record-native addresses.
- tools/check_sharc_coverage.py support tables updated -> EXIT 0;
  instruction-coverage.md verdict updated (gap CLOSED, 2026-07-20 section).
- upstream staging: 10-sat-mr-family / 11-native-abs-drc /
  12-native-fdep-se-imm-drc generated from a real series worktree
  (957e9dec1b4 + 01-09), full 12-stack git-am-clean, C++20 syntax-pass;
  README.md + sharc-upstream-patch-series.md updated.
NEXT: (a) wet-level calibration & MULTI unit id (unchanged), (b) consider
RND MRx while the TRM is open if any future pool uses it, (c) Felipe's
upstream submission now has 12 patches.

## 2026-07-20 late: CONVERT track — tempo/TM5 + TG primitives (185 -> 236)

kn7000_disassembly grew by 51 re-assembled functions, byte-match kept
(clean-rebuild `make verify` OK, zero new .byte escapes):

- TEMPO/TM5 MODULE (39 fns, commits 3f1e97a/92b7bf9): TempoTick96Isr
  0x48447084 fully decoded — the five "tick consumers" are 10-byte CLOCK
  CONSUMER blocks {beat-in-bar, beats-per-bar, tick-in-beat 0..0x5F, free
  tick ctr, flags} at 0x50149666/70/7A/84/8E (+count-in ctl 0x50149698);
  flag bits recovered (bit15 RUN .. bit7 bar-wrap). DISCOVERY: the
  "transport" fns are the INCOMING MIDI realtime handlers — 0x484B23F1/
  0x484B2451 (both MIDI RX paths) dispatch 0xF8->0x48447361, 0xFA->
  0x48447445, 0xFB->0x484475C3, 0xFC->0x48447712; 0x50149656 is the
  MIDI-clock-SLAVE flag (prop 0x2020), NOT "stop" — when slaved TM5 is
  re-programmed per received 0xF8 (reload = 2*dt_ms*0x7D0/4, fn
  0x48447891) and each consumer HOLDS at 24-PPQN boundaries
  (tick%4==3) until the next real clock steps it (0x48446e29). MIDI
  clock OUT = 0xF8 every 4th tick; count-in = metronome-clock bar wraps
  counted to 0x5014969A. Metronome click engine named (part 0x20, note
  0x10/0x11 vel 0x6A/0x54/0x34, state 0x5003A530..3A).
- LIBRARY WINDOW OPENED (12 fns, commits 4cab465/97fb4da): gen_program_s
  now converts code-region-2 functions under a shifted .mnbase
  (0x4C000000 = file 0x3B8FD1, per library-rom-loading.md) — PC-relative
  encodings byte-exact at the 0x4C link address. First batch = the TG
  note-path bottom layer: TgVoiceRegWrite 0x4C036F98 (slot<0x40 -> TG A
  0x98050000/2 else TG B), global 18-shift broadcast writes, TgCmdReadA/B
  readback, TgVoiceStatusRead (cmd 0xFC01, gate 0x500CE380==0x7F skips),
  TgVoiceRecordReset/Ptr (0x500CA0B0 stride 0x84, ROM template
  0x4858766C), TgVoiceSlotService (0x500AF940 stride 0xB4 class
  dispatch), LibDiv32, LibTickSleep.
- TG NOTE PATH CONVERTED (2026-07-20 tick, kn7000_disassembly 935b614/
  83fdb4b/b321b2f — the previous NEXT, DONE): 23 lib + 9 region-1
  functions -> 268 total (233 region-1 + 35 lib), zero new .byte
  escapes, make verify 100% after clean rebuild. The whole chain
  TgPartKeyEvent 0x4C036EA4 -> TgNoteOn 0x4C036837 (class dispatch:
  melodic/drum 0x80..0x83/table-class 0x40) -> TgElemNoteOnStd
  0x4C030A9D -> TgVoiceGateOn/GateOff + TgVoiceEgBurstWrite is real
  source now. DISCOVERIES (tg-envelope-sweep-results.md RESULT 5):
  0x500CA0B0+slot*0x84 = shadow reg cache, 4-byte entries [lo=note-on|
  hi=release]; the managed key-up 6-write burst = TgVoiceEgBurstWrite
  0x4C0376E3 flushing the release halves of r0,r1,r4,r5,r8,r9; h1/h2/h3
  = amp/pitch/filter release computers (h1's rate sum CONTAINS the
  screen RLS param via part-FX rec +0x48 -> RESULT-2 open RESOLVED;
  desc2+0x3E = the folded CUTOFF ADJUST); sustain pedal = TgPartKeyEvent
  key-off with hold-query 0x4C02E0F9 == 0 -> mark-only (0x4C02E2C7), no
  voice release; r3 key-up value = the cached +0x0A per-note value.
  Filter/pitch EG naming reconciled WITH the a1 live decode (b321b2f).
  Tempo-sync param layer 0x484478E7..0x48447F33 (0xD001-0xD003 trio +
  0x70xxxx property dispatcher) also converted.
NEXT (CONVERT track): the melodic voice allocator 0x4C034FF5 (slot
choice + steal policy, the last unnamed core of TgNoteOn), the drum
builders 0x4C03595F/0x4C035D21, pitch calc internals 0x4C02FB7E/
0x4C02FBE3, and the hold/sustain state machine 0x4C02E0F9/0x4C02E2C7.

## 2026-07-20: CONVERT track — the voice allocator + steal engine (268 -> 309)

The previous NEXT is DONE (kn7000_disassembly 6fd75da/ec57390): 41 new
library functions, 309 total re-assemblable (233 region-1 + 76 lib),
zero new .byte escapes, clean-rebuild `make verify` 100%.

- STEAL POLICY DOCUMENTED PRECISELY (new note: notes/tg-voice-allocator.md,
  static RE): every hw slot has a 0x2C-byte node (0x500D1278+slot*0x2C,
  +0x28 note/+0x29 slot/+0x2A polled level) on class rings inside list
  arrays with PER-SIDE POLYPHONY QUOTAS (+0/+1 quota, +2/+3 active;
  per-part array = *(0x500D0C64+part*0x1C), global active 0x500D1238,
  global free 0x500D1258 w/ class-6 head 0x500D1274 = first choice).
  TgVoiceNodePick 0x4C03ACC9 walks the pool's ROM steal-order list
  (0x485879D8 pool desc -> 0x486D3844/53/61/6C): retired (6) first,
  releasing (5..2), HELD (1,0) LAST, global ring before own-part at
  each priority; side policy 0x08/0x10 filters by slot < 0x40 (TG A/B).
  Quota overflow -> TgVoiceMigrateFind (ROM order 0x486D383C) migrates
  an opposite-side donor to the global array = the TG A/B rebalancer.
  TgVoiceStatusSweep retires gone voices (cmd 0xFC08 vs sustain mask
  0x500D288C) and grades steal candidates by polled envelope level
  (cmd 0xFC02, <0x80 -> fade-kick to steal fodder).
- DRUM PITCH LAW: the drum stagers (TgDrumStageStd 0x4C03587E class
  0x10, TgDrumStageTable 0x4C035BE5 class 0x40) just call
  TgPitchInitCalc_entry with the kit zone's (often NULL) descriptor --
  the legacy 0x4280 path enters there, no allocator-side drum formula.
- PEDAL TIMING: TgPartHoldQuery 0x4C02E0F9 = hold gate (part flags
  bit6) + TOP-NOTE promotion (releasing the highest note rewrites the
  survivors' class-0x3000 word, bit14 cleared); under hold the key-off
  is MARK-ONLY (TgPartHoldMark 0x4C02E2C7 -> the part's 0x500AD5A8
  block), no TG write until pedal release collects the marks.
- Pitch/level internals: TgPitchZoneFold = +-0xC00 OCTAVE fold into the
  sample's key window; TgPartPitchWordCalc applies per-scale-degree
  microtuning (partrec+0x4A[note%12]) at every note-on; TgLevelResolve
  = mute/solo/part-link/velocity+expression.
NEXT (CONVERT track): the remaining TgNoteOn internals — the repeat-note
damp tables + 0x4C033CB3 (class-bit2 note-on programmer) and the
key-off collection sweep that consumes TgPartHoldMark's marks (find it
via callers of 0x500AD5A8+0x26/+0x27); then the choke/kill helpers
0x4C00C0B1/0x4C0115AA under TgVoiceSlotService.

## 2026-07-20: CONVERT track -- the note-path closure + THE GLIDE (309 -> 341)

The previous NEXT is DONE and the TG note-path DISPATCH LAYER is CLOSED
(kn7000_disassembly b5b3d4f/a4dc9dc): 32 new library functions, 341
total re-assemblable (233 region-1 + 108 lib), make verify 100% (one
new auto-escaped non-minimal call encoding in TgElemNoteOnFresh).
Every dispatch target of TgPartKeyEvent -> TgNoteOn ->
TgVoiceSlotService is now source; below remain only leaf param
fetchers, raw shadow-cache writers, and the soft-float runtime.

- ★ MAJOR REINTERPRETATION (code-settled, notes/tg-voice-allocator.md
  new section + blog Part 54): the "pedal-release collection sweep"
  DOES NOT EXIST as such -- 0x4C02E5AD (TgPartGlideTick) is the
  PORTAMENTO tick and the 0x500AD5A8+part*0x10C +0x26.. block is the
  part's MONO/PORTAMENTO state (+0x26 current note, +0x27 previous,
  +0x28..+0x2C tick/step counters, +0x30/+0x38 SOFT-DOUBLE per-step
  pitch deltas, +0x40/+0x42 interpolated offset). TgPartGlidePlan
  0x4C02D79A plans the ramp in software IEEE doubles (100.0/12.0/
  256.0/+-5.0; curve ROM 0x486D319C with a double rate coeff).
  partrec bit6 = mono/legato (top-note promotion = mono priority),
  bit7 = portamento. Part 52's mark-only measurement stands; the
  damper's actual bookkeeping is the held-node flags + sustain mask
  0x500D288C, and its part-flags gate is still OPEN.
- Dispatch decode: staged class bit2 = FRESH strike -> TgElemNoteOnFresh
  0x4C033CB3 (full shadow image: pitch chain, level word, 4 EG
  segments + amp EG, even+odd banks); bit1 = RESTRIKE ->
  TgElemNoteOnStd (misnamed "std"); drum/table -> near-twin
  TgKitElemNoteOn 0x4C013547. Key-off per class: drum TgDrumKeyOff-
  Program 0x4C00C0B1 (own amp-release calc 0x4C00AD48, same curve ROM
  0x486D2649), table TgTableKeyOffProgram 0x4C0115AA, restrike
  TgElemKeyOffRelease 0x4C013F0F -- all end in the TgVoiceEgBurstWrite
  6-write burst. Kit classes 0x81..0x83 fire a PCM ONE-SHOT layer
  (TgNoteOnKitLayer 0x4C03678F: gate-on + immediate gate-off).
- The voice-list engine named: TgVoiceListBuild 0x4C03B3B5 + 8 wrappers
  + 7 ring-walk helpers = how everything enumerates voices (flags 0x80
  = collect-AND-release walk following the slot ring; part order-ring
  heads at 0x500D0C64+part*0x1C +4 sounding / +8 releasing; +0xC =
  16-byte slot bitmask for the pending-release marks, node flag bit11).

NEXT (CONVERT track): the layer below the dispatch -- the melodic zone
param fetchers 0x4C00FD4E..0x4C00FFF5 + kit/table fetchers 0x4C011F31/
0x4C0121D8, the raw EG/shadow writers 0x4C03A214/0x4C03A2BF/0x4C037C1B
family, and the SOFT-FLOAT double runtime (0x4C0007E7/0x4C000856/
0x4C000879/0x4C000B1C/0x4C001629/0x4C0016AC/0x4C0019F2 + the mul
0x4C000523) as its own module; live-session question for the runtime
track: the damper pedal's part-flags gate into the held-voice policy.

## 2026-07-20: CONVERT track -- the SOFT-FLOAT LIBM + the fetcher leaves (341 -> 382)

The previous NEXT is DONE and then some (kn7000_disassembly ddb6468/
3a673d1/c04145a/2622d0b): 41 new library functions, 382 total
re-assemblable (233 region-1 + 149 lib), make verify 100%.

- ★ THE FIRMWARE SHIPS A FULL IEEE-754 DOUBLE LIBM (lib 0x4C000000..
  0x4C001A00, no FPU anywhere): not just the glide helpers -- add/sub/
  mul/div/cmp + unpack/pack cores + 6 int<->double converters, AND an
  errno-style math library: frexp/ldexp/modf/LOG/EXP/POW (pow =
  modf-split, integer part by repeated squaring, fraction via
  exp(frac*log(x))), errno cell 0x500AD390 (1=domain 2=range), DBL_MAX
  saturation, ln2/sqrt2/ln(DBL_MAX) constants, log's coeff table at ROM
  0x48586198. ABI: doubles on the caller's arg area (8,sp)/(0xC,sp) +
  (0x10,sp)/(0x14,sp), result d0(lo):d1(hi). CORRECTION to the glide
  note: 0x4C000523 is NOT the mul, it is LibI32ToF64 (mul = 0x4C000874
  entry 0x879). All 21 converted; the only known callers are the
  portamento pair, so the libm is 99% dead weight -- linked-in compiler
  runtime.
- Encoder milestone (3a673d1): mn10300_asm now encodes addc/subc,
  rol/ror, bvc/bvs/bnc/bns (fields per mn103dasm.cpp) -- the soft-float
  carry chains emit real assembly; image-wide .byte fallbacks 43 -> 5
  (all five = the ROM toolchain's own non-minimal call encodings).
- The zone param fetchers decoded (15 converted): desc2 UI bytes ->
  hw units through the +-50 sensitivity curve ROM 0x486D2713 (negative
  = negated mirror), key scaling via the 0x486D1354/0x486D13D4 pair;
  the three filter-EG level calcs all fold the CUTOFF ADJUST desc2+0x3E
  into per-segment offsets +0x3F/+0x41/arg(+0x43/+0x45). Kit set
  0x4C011F2F..0x4C012225 = byte-for-byte twins (second link) serving
  TgKitElemNoteOn. Plus TgPartElemLastSet, the EG-segment pair
  TgVoiceEgSegParamGet/FlagTest (tone-TYPE feature records ROM
  0x486D2ED5+type*0x27), and TgVoiceRouteFieldSet (shadow +0x40 bits
  12..19; mode 0 = hw-config remap via PanelSubTypeGet).
- ★ PEDAL (static piece, live gate still queued): the sustain-mask
  consumer scan found TgStageHeldPolicyShed 0x4C0147AD inside
  TgSlotAllocate -- parts > 0x12 lose the HELD bit7 of pool bytes +4/+5
  when the active high water 0x500D287A hits 0x40/0x60 (threshold by
  context byte 0x500D2878): under load the damper holds at most 2
  elements per note. Also TgVoicePoolReset 0x4C014803 (cold init:
  force-off sweep, quota ROM 0x486D379C, order-head ROM 0x486D37B0,
  mask block 0x500D287C/8C/9C cleared).

NEXT (CONVERT track): the remaining leaves under the note-on
programmers -- the pitch chain internals 0x4C0311F3/0x4C0312A2/
0x4C031330 + the level-word tails 0x4C03162C/0x4C03178C/0x4C02BF8B,
the per-slot force-off 0x4C037244 (TgVoicePoolReset's sweep target) and
the status readers around it, and the curve helpers 0x4C011ABC/
0x4C0118F5/0x4C011ACE under TgVoiceEgSegParamGet; then the amp-EG
computer family around 0x4C009F03/0x4C00AD43 cited by the key-off docs.
Live-session question unchanged: the damper's partrec-bit6 gate.

## 2026-07-20: CONVERT track -- the LEVEL chain + the type-7 EG time-ramp (382 -> 422)

The previous NEXT is DONE (kn7000_disassembly 86f0350): 40 new library
functions, 422 total re-assemblable (233 region-1 + 189 lib), make
verify 100% byte-identical, encoder fallbacks still 5. All static RE.

- ★ MISNOMER FIXED: the "pitch chain internals" 0x4C0311F3/0x4C0312A2/
  0x4C031330 are the NOTE LEVEL chain (they only FOLLOW TgPitchRuntime-
  Calc in program order). TgNoteLevelVariationCalc = per-note level
  humanization (desc mode bits 15..14: velocity-sense offset from tone
  block +0x91 / PSEUDO-RANDOM level off the 1 kHz tick 0x50151BFC /
  set level-word bit15-bit16 + neutral 0x40) -> librec+0x50;
  TgVoiceNoteLevelCalc folds it with part level + expression into the
  7-bit level at shadow +0x24; TgElemLevelBaseCalc computes librec+0x12
  /+0x14 (base level term) incl. the VELOCITY/KEY FADE crossfade zones
  desc2+0x1C..0x27 (hard edge -0x200, slopes -0x40*d/(hi-lo)).
- Level-word tails: TgAmpEgAttackRateCalc (curve ROM 0x486D25E4 ->
  shadow r0 HI) + TgAmpEgDecayRatePairCalc (0x486D2649 -> librec+0x64/
  +0x66 -> r1/+8 HI) + TgLevelTermFinalize (part/group-master gains
  0x500C0760..66, mono/legato mutes, log->hw ROM 0x486D1BD4).
- ★ NEW MODULE, whole gap 0x4C011730..0x4C011F2F closed (17 fns): the
  per-part TYPE-7 EG TIME-RAMP. State 0x50009D38+part*8 {flags, cntA
  (max 0x4F), cntB (max 0x96), scaleA/scaleB Q8.8}; enable = tone type
  7 AND partrec halfword bit 0x1000; a tick dispatcher walks all 0x22
  parts through an engage/release edge machine ramping the scales via
  curve ROMs 0x4858712C/0x4858717C, live-refreshing sounding voices
  (part class-reg list 0x500C9848 built by TgPartClassRegCollect
  0x4C00FBCA from table 0x500C59E4+part*0x36 + tag ROM 0x485870F0 ->
  TgGlobalRegWriteBoth; per-slot writes librec+0x28/+0x2A low-14 ->
  TG classes 0x0401/0x0405). TgVoiceEgSegParamGet's type-7 "curve
  helpers" are its scale getters. OPEN: which panel feature drives
  partrec bit12 (candidate: part sustain/damper response) -- a live
  session could toggle SUSTAIN and watch 0x50009D38.
- Force-off family: TgVoiceStealSilence 0x4C03713A = the ONLY writer
  of the r1/r2=0xC000 boot/steal pattern (TgSlotAllocate steal path;
  closes that erratum thread), TgVoiceForceOff 0x4C037244 (pool-reset
  sweep, rate 0xA2 + EG-seg clears), soft (0x7F) + damp-only variants,
  TgVoiceEgSegRegsWrite (r8..rB from shadow +0x18..+0x22).
- DRUM-side zone fetcher set 0x4C009F01..0x4C00A1F7 = the THIRD link
  of the melodic/kit fetcher family (same ROMs 0x486D2713/1354/13D4),
  serving the class-0x10 drum programmers around TgDrumAmpReleaseCalc.

NEXT (CONVERT track): the remaining neighbours -- the level hooks
0x4C006A17 (part+note level term used by TgLevelResolve/TgVoiceNote-
LevelCalc) and 0x4C00685C (TgLevelTermFinalize's tuning hook) with
their module 0x4C0068xx..0x4C006Axx, the shadow byte writers
0x4C037B1A/0x4C037B4A + the 0x4C03783B raw helper cited by TgElemKey-
OffRelease (gap 0x4C037759..0x4C037A34), the 0x4C03A3CD function after
TgPartEgRampCache54Scaled (partrec bit-0x2000 test seen), and the
region between TgLevelTermFinalize's end 0x4C02C153 and TgPartGlide-
Plan 0x4C02D795 (starts with an elem/tone-record walker at 0x4C02C153).
Live-session question: SUSTAIN toggle vs 0x50009D38 (see OPEN above).

## 2026-07-20: CONVERT track -- the CONTROLLER MOD-MATRIX + the LFO/mod runtime (422 -> 467)

The previous NEXT is DONE (kn7000_disassembly b49139f): 45 new library
functions, 467 total re-assemblable (233 region-1 + 234 lib), make
verify 100% byte-identical, encoder fallback lines unchanged. All
static RE. Tooling note: unidasm's mn10300 has a LENGTH BUG on the F4
page (2-byte register-indexed moves printed as 1 byte -> a phantom
instruction from the postbyte); gen_program_s.disasm_function already
resyncs -- when hand-reading, use its corrected listing, not raw
unidasm (the scratchpad dislib2.py wrapper).

- ★ THE "LEVEL HOOKS" ARE A MOD MATRIX: 0x4C0067CD..0x4C006ED1 = the
  part CONTROLLER MOD-MATRIX. Per part, 3 mod sources; per destination
  a value/depth halfword pair array (partrec+0x66+dest*0xC+i*2 /
  +0x6C+dest*0xC+i*2) and route/sign mask bytes partrec+0x53A+bank*4;
  sum = value*depth/0x100 over routed sources. Six siblings by enable
  bit: 0x02 PITCH (TgPitchNoteResolve's "part offset resolve"), 0x04
  LEVEL term (TgLevelTermFinalize), 0x08 FILTER (+sbyte partrec+0x44),
  0x10 CUTOFF, 0x20 NOTE LEVEL (TgLevelResolve/TgVoiceNoteLevelCalc),
  0x40 (note-on programmers). partrec+0x52C = the 12-bit dest-enable
  mask, recomputed from the 3 bank tables partrec+0x34C+bank*0x78
  (12 dest records, stride 0xA) by TgPartModDestEnableUpdate.
- The 0x4C02C153..0x4C02D795 region = the LFO/MOD RUNTIME ENGINE:
  TgVoiceModSlotUpdate/TgVoiceModLfoStep step 8-byte mod slots
  (per-voice librec+0x82+u*8, per-part partstate+0x4A+bank*0x30+u*8;
  {val,flags,phase,,depth,,target}, +-0x1FFF), TgPartModDestApply/
  RefreshAll latch the part GLOBAL regs (class 0x0400, dests cached at
  partstate+2+dest*2; masks ROM 0x486D1224/0x486D123C),
  TgVoiceModDepthWrite = the per-voice depth regs (units 0..3 ->
  classes 0x0409/0x0402/0x040D/0x0406, cache rec+0x2C/+0x30/+0x2E/
  +0x32). TgPartModSlotSweep + TgVoicePeriodicService are the two
  periodic sweeps hosting TgPartGlideTick (the 0x4C02D2F8/0x4C02D552
  call sites). Voice lifetime ticks: +0x52 = release countdown
  (bit15 hi-byte -> gate-off+key-off; bit7 low7 -> slot service),
  +0x54 level word auto-ramp modes 0x7000 (ramp/damp/target) via
  TgVoiceLevelRampTick. TgPartCutoffResolve = key-follow ROM
  0x486D23E4 * depth >> 5 + matrix + partrec+0x45, clamp 0..0x70.
- ★ partrec bit-0x2000 (bit13) STATIC ANSWER: it selects the
  GRACEFUL/EXTENDED path family -- graceful +0x52 release countdown
  (vs immediate key-off) in both sweeps, the TYPE-7 EG-ramp scaled
  part registers in TgPartModDestRefreshAll (partstate+0x1A/+0x1C/
  +0x1E via 0x4C00F9B4 sels 0x10/0x11/0x20), the TgVoiceZoneVeloGate
  skip, and forced mod units 2/3 when tone desc+0x44 nibble == 0xD.
  (partrec bit12/0x1000 = the type-7 ramp ENABLE, still awaiting its
  panel trigger -- live SUSTAIN question stays queued.)
- Raw writer gaps closed (0x4C037759..0x4C037A34, 0x4C037B1A..
  0x4C037C16): EG reg group writers classes 1/2/5/6/9/A (0x4C03783B =
  TgVoiceEgRegsWriteRaw_entry, closing the TgElemKeyOffRelease cite),
  librec+0x4C/+0x50 = the two effect-SEND words (classes 0x2800/
  0x2C00), note level = class 0x000C, TgVoiceFadeLevelGateOff (level
  word low13 + bit14 clear + gate off), class-8/9 rate hi/lo setters,
  class-0x4000..0x5000 filter word group.
- Part TONE/PROGRAM setup module 0x4C03A3CD..0x4C03A779: per-class mod
  setup (melodic w/ jump tables 0x485879B4/0x48587990 on desc+0x44's
  nibble; drum; table), dispatch by desc+0x10 & 0xCF, TgPartProgramSet
  (tone block +6/+7/+8 = the tone address) + the all-parts init
  (program 0x20).

NEXT (CONVERT track): the apply layer under the tone-mod setup --
0x4C0394A4 / 0x4C039D83 / 0x4C0396E7 / 0x4C0399DD (the mod source
read) / 0x4C039C61 / 0x4C038942 / 0x4C038503 (sample desc getter) /
0x4C0385xx, i.e. the 0x4C038503..0x4C03A20F gap between the note-path
and the EG helpers; plus the mod-matrix CONFIG setters around
0x4C005876..0x4C0067CD (the callers at 0x4C00664A/0x4C006708 that
write the +0x34C bank tables and call TgPartModDestEnableUpdate) and
the retrigger satellites 0x4C01349C / 0x4C033C0F / 0x4C03089B.
Live-session questions unchanged (SUSTAIN vs 0x50009D38; partrec
bit12 panel trigger).

## 2026-07-20: CONVERT track -- the PART TONE APPLY layer + the mod-matrix WRITE side (467 -> 510)

The previous NEXT is DONE (kn7000_disassembly 91b6254 + ac52418): 43
new library functions, 510 total re-assemblable (233 region-1 + 277
lib), `make verify` 100% byte-identical, encoder fallback lines
unchanged (5). All static RE; no MAME was run.

- The 0x4C038503..0x4C03A20F gap is the PART TONE APPLY LAYER. Tone
  block = 0x500CE404+part*0x130: +0 = the resolved tone DESCRIPTOR
  pointer, +8/+7/+6 = the program / bank-lo / bank-hi bytes
  TgPartProgramSet writes, +0x4A = the cached EG halfwords,
  +0x60+u*0x34 = the four mod-unit blocks. Leaf accessors
  TgPartToneProgramGet/BankLo/BankHi/DescPtr/IsTableClass.
- ★ A LOCAL-EDIT SHADOW EXISTS: every fetch/apply entry comes in a
  plain and a *Sel flavour; the *Sel front ends ask 0x4C00C6BF whether
  the part is running its LOCAL EDIT copy and, if so, read/write the
  RAM record 0x500C1183+idx*0x8E instead of the resource record
  (0x501496B8+0x70F7+idx*0x8E / the banked lookup 0x484496CE through
  0x5003A5A4/A8/AC + 0x5003A554/58/5C). SAME 0x8E stride on both sides
  -- the RAM copy is a byte-for-byte edit shadow of the resource one.
- TgPartProgramApply (0x4C038942, 2.9 KB) is the program-change
  rebuild; it and TgPartProgramHandlerDispatch key off {program,
  handler} hash tables (0x48587830/0x485878B0/0x48587930) indexed by
  the tone-block program byte.
- TgPartModUnitParamGet (0x4C0399DD) = THE mod-source read cited by
  TgVoiceModSlotUpdate/TgVoiceModLfoStep: tone block +0x60+unit*0x34
  +0x22+idx*2. TgPartModUnitRampStep (0x4C039A09, the sweep call site)
  interpolates the curve ROM 0x486D1E54 in DOUBLE PRECISION -- the
  only soft-float user in the mod runtime.
- ★ partrec bit13 CONFIRMED AGAIN, independently: TgPartEgRampBuild
  (0x4C039D83) runs TgPartEgRampInit and then RETURNS IMMEDIATELY
  unless partrec (0x500B5340+part*0x54C) halfword bit 0x2000 is set.
- ★ THE MOD-MATRIX WRITE SIDE IS NOW READ: TgPartModConfigSet
  (0x4C006333) and its STORE-ONLY twin TgPartModConfigStore
  (0x4C00603B) take a parameter byte (&0x7F, valid 1..0x2E) through
  46-entry jump tables (0x48586710 / 0x48586658) and store scaled
  values into partrec +0x66+dest*0xC+src*2 (value) / +0x6C+dest*0xC
  (depth) -- exactly the layout the TgPartModSum* resolvers read. The
  setter then re-collects the part's live voices (TgVoiceListCollect-
  PartAll -> TgPartModVoicesRefreshA/B/C -> TgPartModVoiceApply) so an
  edit is audible immediately; the store-only twin is the bulk/preset
  path. Mask cases call TgPartModDestEnableUpdate to rebuild
  partrec+0x52C.
- ★ ROUTE vs SIGN DISAMBIGUATED: TgPartModRouteMaskSet (0x4C005673)
  uses the per-dest ROM bit tables 0x485865EC (route) / 0x485865F0
  (sign) to OR/AND partrec +0x53A+dest*4 = ROUTE and +0x53C+dest*4 =
  SIGN. Six byte-identical value-scaling twins feed the cases
  (0x4C005730/5766/579C/57D2/580B/583E; bipolar = flags bit7,
  value*depth<<8 / 0x1FC0), plus TgModDepthScaleRom (ROM 0x486D1E90 /
  0x7F) and TgModDepthScaleClamp (0..0x1FFF, the mod-slot range).
- ★ ERRATUM to the 2026-07-20 mod-matrix notes: the scaling bytes
  +0x43 and +0x4C used by the TgPartModRetrigger satellites
  (TgPartCtrlSenseKit/Melodic/Elem, 0x4C01349C / 0x4C033C0F /
  0x4C03089B) are read from the TONE DESCRIPTOR (tone block +0 ->
  desc), NOT from the part record -- earlier docs saying "partrec+0x43"
  conflated the two. All three share one gate: global halfword
  0x500C0758 bit 0x0200 + partrec bit0, amount partrec+0x13.

NEXT (CONVERT track): the rest of the same gap, 0x4C037D14..0x4C038503
(15 functions, all verified alignment-clean: 0x4C037D14 / 0x4C037D8C /
0x4C037E08 / ... / 0x4C03833F, the module feeding the tone accessors);
then the local-edit shadow module around 0x4C00C233..0x4C00C6BF
(TgPartAuxRecPtr's neighbours 0x4C00C25D / 0x4C00C28F / 0x4C00C2BF /
0x4C00C2FB / 0x4C00C6BF -- the predicate that selects the RAM copy),
and the resource-side region-1 fetchers 0x4844A434 / 0x4844ABF7 /
0x484496CE / 0x48449790. Live-session questions unchanged (SUSTAIN vs
0x50009D38; partrec bit12 panel trigger).

## 2026-07-20: queue item D COMPLETE -- ★ THE 6-ITEM QUEUE IS DONE

D1 (KN2400/KN2600 to first screen) shipped earlier as 94fb292. D2
(KN6000/KN6500 text) is now RESOLVED AS A CHARACTERIZED, PROVEN
BLOCKER -- commit 208d3fd, full write-up in notes/kn6000-kn6500-boot.md.

- ★ THE TEXT SUBSYSTEM IS NOT BROKEN. Wrapper 0x484180DB runs 42x with
  its gate *(0x50010384) open; the text drawer 0x48418112 runs 40x with
  the same font ids (0/3/4/0x0B) the KN7000 uses. What is missing is the
  FONT DATA.
- ROOT CAUSE: the font init 0x48420312 copies five font-descriptor
  pointers out of the TABLE-ROM HEADER at 0x48000200..0x210. KN7000
  (table ROM dumped) => 48000240/4800E880/4801221C/480237A4/0. KN6000 =>
  ASCII garbage, because the driver's "table" region is a PLACEHOLDER:
  verified byte-identical to program bytes 0x200000+ (IK2 loaded twice).
  IC13/IC14 (QSIGX3C16008/16007) have NEVER been dumped.
- PROVEN by a diagnostic that is NOT and will NOT be shipped: injecting
  the KN7000 table ROM's font region renders the KN6000 play screen with
  complete text (snap/kn6000/0017.png). Cross-model mask-ROM substitution
  would misrepresent the device -- integrity policy holds.
- ★ TWO REUSABLE TOOLING LESSONS (both caused the previous pass's wrong
  "the blitter never executes" reading):
  (1) MN10300 movm-prologue functions are called at ENTRY+2 -- an entry
      breakpoint never fires though the function runs constantly.
  (2) A ROM search for an absolute address returns the OPERAND offset,
      which is MID-INSTRUCTION; breakpointing it silently never hits.
  Also: write-taps miss the compositor path -- dump the UI INDEX PLANE,
  not the framebuffer.
- KN6000 display model recovered (KN7000's, relocated): index plane
  0x5020042C, companion 0x50225C2C, CLUT 0x5024F458, compositor
  0x4C006EE0-0x4C006FAF.
- NOT A RACE: five consecutive boots are byte-identical (SHA1 of decoded
  pixels 280c82361f52); the drawer runs 40x every time. Item C's TM5
  retirement did not affect this path. (One live run DID show text --
  that was the injection experiment, not intermittency.)
- No regressions: kn7000 boots to home with full text, kn2400 boots,
  -validate clean on kn7000/kn6000/kn2400, binary published.

OPEN for Felipe (ROM-manifest call, not an emulation change): the four
kn6000/kn6500 "table" ROM_LOADs have NO emulation effect (blanking to
0xFF gives a byte-identical screen) and imply IC13/IC14 dumps exist.
Consider replacing them with NO_DUMP entries or dropping them for
ROMREGION_ERASEFF. Driver comment now states the situation explicitly.

QUEUE STATUS: A DONE, B DONE, C DONE, D DONE -- ★ FELIPE'S 6-ITEM
SOFTWARE QUEUE IS COMPLETE. The parallel CONVERT track continues per the
standing idle-time directive. Remaining PENDING-FELIPE items are
unchanged: Phase C dump-kit go-ahead, SHARC upstream submission, DSP
wet-level A/B by ear. NEW top blocker for the KN6xxx line: a hardware
dump of IC13/IC14 (fonts, and likely the TG sample maps too).

## 2026-07-20: CONVERT track -- the TG COLD BRING-UP + the LOCAL-EDIT SHADOW (510 -> 545)

The previous NEXT is DONE (kn7000_disassembly 63f78a0): 35 new
functions, 545 total re-assemblable (236 region-1 + 309 lib), `make
verify` byte-identical after a CLEAN rebuild, encoder fallback lines
unchanged (5). All static RE; no MAME was run and nothing was built in
../kn7000_mame_build.

- The 0x4C037D0F..0x4C0384C4 gap = the TG OUTPUT-CHANNEL REGISTER FILE.
  Thirteen channels shadowed at 0x500CE2B0+chan*0x10, mirrored to the
  chip via TgVoiceRegWrite_entry with the channel in the 20-bit SLOT
  field, so the composed address halfword is 0x8008+chan*0x10 (bit15
  set = the NON-VOICE register space -- distinct from the per-voice
  slot 0..0x3F classes). The shadow is a 4-segment level envelope:
  +0/+2/+4 halfwords (classes 0x8008/0x8108/0x8208; rate = bits 11..8,
  level = bits 6..0), +8 long (class 0x8308, same plus a 5-bit field at
  bits 16..12), +0xC long (class 0x800A, two 7-bit levels). Every field
  has a level-only setter and a rate+level setter (TgChanEgSeg0..3
  LevelSet/Set, TgChanOutLevelPairSet).
- Which channel a part uses: part record 0x500B5340+part*0x54C halfword
  +0x62 bits 10..8 -> ROM map 0x486D109A (value 8 = "no channel", the
  caller 0x4C004DE4 returns early). Channel defaults = the 13 x 16-byte
  ROM image 0x4858759C.
- Global registers: TgGlobalRegsA0LoadA/B push classes 0xA000..0xA008
  from an 18-byte image (0x486D11F4 / 0x486D1208 -- the B twin writes
  the CONSTANT 0x00008000 for 0xA000..0xA006 and only reads +0x10);
  TgGlobalRegsB0LoadA/B push classes 0xB000..0xB00E from 8 halfwords
  (0x486D11D4 / 0x486D11E4, which differ in exactly one halfword).
  All gated on the TG-enable cell 0x500CE380 != 0x7F.
- ★ THE TG-ENABLE GATE STORY IS NOW COMPLETE IN SOURCE. TgChipReset-
  SideA (0x4C03819E) / SideB (0x4C03833A) call the strap probe, set
  0x500CE380 = 0x7F ("no TG", every register writer becomes a no-op)
  UNCONDITIONALLY, and only when the probe does NOT return 3 write 0x40
  and actually reset: pulse 1 -> 0x98050010 x3 and 3 -> 0x98050004 x3
  (B: 0x98040010 / 0x98040004), load both global blocks, copy the
  0x84-byte ROM template 0x4858766C into all 0x40 (A) / 0x80 (B) voice
  records 0x500CA0B0+slot*0x84 with gate-on/off/silence, write 0x100
  sample entries from 0x48587700/2, and load the 13 channel defaults.
  This is exactly the gate the driver forces open via the CONFIG bit --
  the forcing is now understood as "write 0x40 where the strap made the
  firmware write 0x7F".
- ★ ERRATUM (feeds the pending blog Part 9 strap retraction): the probe
  is now named TgStrapProbe (0x484D7713) and converted. It reads
  halfword 0x98070000 and returns 3 when bit 0x02 is CLEAR, 2 when bit
  0x04 is clear, else 1. The bits are 0x02/0x04 -- earlier notes said
  "bit1/bit2". Its neighbours TgStrapProbeZero (0x484D7736, returns 0)
  and TgStrapProbeSideB (0x484D773A, bit 0x01) are converted too.
- ★ THE LOCAL-EDIT SHADOW: layout EXACT and contiguous in .bss --
    0x500BDB04 + idx*0x2C8   AUX EDIT RECORDS, but ONLY idx 0x10/0x11/
        0x12 exist (TgPartAuxRecPtr returns NULL otherwise), so the
        three occupy exactly 0x500C0784..0x500C0FDC. The 0x2C8 divides
        with nothing left over: header 0x54 + 4 x 0x7A mod units at
        +0x54 + 4 x 0x23 elements at +0x23C.
    0x500C0FDC               a 423-byte tone-descriptor SCRATCH copy.
    0x500C1183 + idx*0x8E    THE SHADOW proper -- 0x8E is the resource
        record's own stride, dividing as header 0x10 + 2 x 0x1C at
        +0x10 + 2 x 0x23 at +0x48 = 0x8E exactly.
- ★ LIFECYCLE (the question this tick was asked to settle):
  * PREDICATE: TgPartLocalEditActive (0x4C00C6BF) = bit0 of the byte
    0x500C58AE + part*9 -- the 9-byte per-part EDIT-STATE record. Every
    *Sel front end in the tone-apply layer consults it (~30 call sites
    from 0x4C00EDF5 on). TgPartLocalEditFlagB reads bit1 of the same
    byte.
  * POPULATE: TgPartLocalEditRecBuild (0x4C00C783) takes the resource
    record from TgPartVoiceRecFetch_entry, copies its first 0x48 bytes
    VERBATIM, then lets the region-1 fetcher 0x48449813 replace the
    +0x10 sub-record (unless resource byte +0xD bit1 is set) and the
    +0x2C one (unless bit2). So the shadow is byte-for-byte the
    resource record EXCEPT for those two banked sub-records.
    TgPartAuxRecBuild (0x4C00C6E9) does the aux side: 0x23C bytes of
    the tone descriptor, then each tone-block mod unit (+0x60+unit*0x34
    -> ptr, 0x7A bytes) over +0x54+unit*0x7A.
  * REFRESH: TgPartAuxElemRecBuild / TgPartLocalEditElemRecBuild write
    one 0x23-byte element sub-record each.
  * INVALIDATE: THERE IS NO FREE OR CLEAR IN THE MODULE. The copies are
    permanent per-part buffers; an edit is discarded only by REBUILDING
    from the resource record. So "does my edit survive?" reduces
    entirely to who clears bit0 of 0x500C58AE+part*9 and who re-runs
    the builders -- neither of which is in this module.
- NOT settled, deliberately: which UI action SETS 0x500C58AE+part*9
  bit0, and therefore the PANEL MEMORY recall interaction. The setter
  is not in 0x4C00C233..0x4C00C890 and the builders have no lib-
  internal callers other than the 0x4C00C96C driver. No blog post this
  tick -- the lifecycle answer is real but half a chain short of a
  user-visible claim, and inventing the recall behaviour would be
  exactly the kind of over-claim the series must not make.

NEXT (CONVERT track): (1) finish the local-edit shadow's own gap --
the ~25 remaining tiny field accessors 0x4C00C318..0x4C00C6BF (all
`ret [d2], 4` leaves over the same two record families, boundaries
already scanned clean) plus the driver 0x4C00C890 / 0x4C00C96C that
calls TgPartAuxRecBuild_entry and loops the four mod units; (2) hunt
the WRITER of 0x500C58AE+part*9 bit0 to close the edit-state
lifecycle (grep the lib for the 9-byte stride, then region 1); (3) the
region-1 resource fetchers 0x4844A434 / 0x4844ABF7 / 0x484496CE /
0x48449790 -- 0x48449813 is now a confirmed caller target from
TgPartLocalEditRecBuild, so this group is the natural next region-1
cluster; (4) the channel-EG CALLER module 0x4C004DE4..0x4C005673, the
last unconverted block before TgPartModRouteMaskSet. Live-session
questions unchanged (SUSTAIN vs 0x50009D38; partrec bit12 panel
trigger).

## 2026-07-20: CONVERT track -- THE LOCAL-EDIT LIFECYCLE CLOSED (545 -> 588)

The previous NEXT is DONE (kn7000_disassembly d46b232): 43 new
functions, 588 total re-assemblable (244 region-1 + 344 lib), `make
verify` byte-identical after a CLEAN rebuild, encoder fallback lines
unchanged (5). All static RE; no MAME was run and nothing was built in
../kn7000_mame_build.

- Item (1) DONE: the 0x4C00C318..0x4C00C6BF gap = 25 leaf FIELD
  ACCESSORS over the aux edit record. Get/set pairs for header +0x45/
  +0x46/+0x47 and for mod-unit bytes +0x04/+0x05/+0x06/+0x19/+0x28/
  +0x2A/+0x2C/+0x2E, plus bit7-only setters for +0x52/+0x56/+0x5A.
  ★ The ranged ones are driven by the offset applier 0x4C00A820: read
  the field, add a SIGNED delta, clamp through 0x4C00A7BE to +/-0x64
  (100) or +/-0x7F, write back -- i.e. these are SOUND EDIT parameters
  with a +/-100 display range, not internal state. The +0x19 setter
  writes the low 7 bits and destroys bit7 by design.

- ★★ Item (2) SETTLED -- THE WRITER EXISTS AND THE CHAIN IS CLOSED.
  It was ~150 bytes past the end of the block the last tick scanned.
  * SET: TgPartLocalEditActivate (0x4C00CB3F, entry 0x4C00CB44) sets
    bit0 of 0x500C58AE+part*9, then TgPartAuxRecRefresh_entry,
    TgPartEditStateDefaults_entry (seeds bytes 1..6 from ROM
    0x486D3192) and a tone re-apply. Called LAZILY from the five SOUND
    EDIT parameter APIs (0x4C00D047, 0x4C00E8D3, 0x4C00EAA0,
    0x4C00F170, 0x4C01466C) -- the shadow springs into existence the
    first time a parameter is touched. Its guard is
    `if (0x10<=part<=0x12 || (flags&3)==3)` whose second half is DEAD
    (falls into `if (flags&1) return`), so only parts 0x10/0x11/0x12
    can ever be edited -- matching the three allocated aux records.
  * SET/FOCUS: TgPartLocalEditSelect (0x4C00CBC2) parks the current
    edit part in the global 0x500C59E0 (0xFF = none) and CLEARS the
    outgoing part's flag -- moving SOUND EDIT focus discards the
    previous part's edit.
  * CLEAR: TgPartLocalEditClear (0x4C00E5C0) = 9 instructions, one
    zero-byte store over the flag byte. Nothing is freed; the shadow
    keeps the user's values but stops being consulted, and the next
    activation rebuilds it from the resource record.
  * ★ THE USER-VISIBLE LINK: the third caller is TgPartProgramSet
    (0x4C03A6F2) -- ALREADY converted and already documented as
    "rebuild through the 0x4C00E5C0/0x4C009C8D/... chain". That first
    address was the local-edit clear all along. TgPartProgramSet is the
    ONLY writer of a part's voice in the firmware, and it clears the
    edit BEFORE reloading anything. So: assigning a voice to a part
    unconditionally discards that part's sound edit. PANEL MEMORY
    recall follows by elimination (a recall that restores part sounds
    has no other route), but the panel->command hop itself was NOT
    traced by hand -- the blog states the tight claim only.
  * BONUS: TgPartProgramSet's only non-boot caller is the 0xC0 case of
    a byte-stream interpreter at 0x4C003D4A reading the queue
    0x500AD39C. It is MIDI-SHAPED: status & 0xF0 -> 0x90 note-on
    (TgPartKeyEvent), 0xA0, 0xB0, 0xC0 program change, 0xD0, 0xE0,
    0xF0 -- but over 34 PARTS, not 16 channels, with longer payloads.
    The library's internal control path speaks MIDI's opcodes.

- Item (3) PARTIALLY DONE: converted the region-1 VOICE-RESOURCE BANK
  FETCHERS 0x484496C9 / 0x4844978B / 0x484497CB / 0x484497E0 /
  0x48449810 / 0x4844981D / 0x4844982A / 0x4844987C. Five banks; class
  code 0..4 (from 0x485713DB) -> descriptor 0x5003A5A4+class*4 + load
  base 0x5003A554+class*4 (records stored as offsets, base re-added).
  Descriptor +0x04/+0x14 = record directories, +0x18 = element table
  (stride 0x23). Record geometry 0x8E = header 0x10 + 2 x 0x1C at +0x10
  + 4 x 0x7A mod units at +0x54 -- exactly what the RAM shadow mirrors.
  Overrides indirect through 0x484494E4(part, rec+0x0D or +0x11); 0xFF
  = "no override" -> the *Default* leaves.
  ★ BOUNDARY LESSON AGAIN: the first fetcher's true prologue is
  0x484496C9, not the 0x484496CE call target the handoff listed.
  0x4844A434 / 0x4844ABF7 were not reached this tick.

- Item (4) NOT started (0x4C004DE4..0x4C005673).

- BLOG: Part 59 written and committed (mame-blog a83b959), "One byte
  decides whether your edit survives" -- the chain now supports a real
  user-visible claim, with the PANEL MEMORY hop explicitly marked as
  inference rather than traced.

NEXT (CONVERT track): (1) the remaining region-1 resource fetchers
0x4844A434 / 0x4844ABF7 and the classifier 0x485713DB / 0x48570C46 that
produces the bank class code -- naming the five banks would let the
resource docs say WHICH banks (factory / expansion / user?) exist;
(2) the SOUND EDIT parameter APIs themselves, 0x4C00CCBA..0x4C00D0B0
and 0x4C00E8xx..0x4C00F4xx, which are the callers that activate the
shadow -- converting them would name the actual edit parameters and let
the docs site describe SOUND EDIT properly; (3) the offset applier
module 0x4C00A7BE..0x4C00A900 (the +/-100 clamp + delta apply) which is
small and directly user-visible; (4) still open: the channel-EG caller
module 0x4C004DE4..0x4C005673. Live-session questions unchanged
(SUSTAIN vs 0x50009D38; partrec bit12 panel trigger).

## 2026-07-20b: CONVERT track -- DIGITAL DRAWBAR + LFO EDIT (588 -> 618)

kn7000_disassembly 92e8372: 30 new functions, 618 total re-assemblable
(244 region-1 + 374 lib), `make verify` byte-identical after a CLEAN
rebuild, encoder fallback lines unchanged (5). All static RE; no MAME
was run and nothing was built in ../kn7000_mame_build.

The handoff's item (2) -- "name the actual edit parameters the user
sees" -- is DONE for two screens, and the new mapping doc is
notes/sound-edit-parameters.md.

- ★★ DIGITAL DRAWBAR (0x4C00A1F7..0x4C00A90C, 20 functions) is fully
  mapped. Per-part record 0x500082C8+part*0x1C: nine drawbar levels as
  4-BIT nibbles packed three to a 12-bit word (+0x00/+0x02/+0x04),
  PERCUSSIVE TONE as 2 bits (+0x06), the four value rows as SIGNED
  OFFSET bytes (+0x08 ATTACK TIME, +0x09 RELEASE TIME, +0x0A
  PERCUSSIVE TONE DECAY, +0x0B LEVEL), derived level words
  +0x0C/+0x0E/+0x10, Jazz/Rock TYPE flag +0x19.
  * The nibbles are NOT in display order: ROM scatter table 0x486D10A0
    maps word0 -> slots 0,1,6 / word1 -> 3,5,8 / word2 -> 2,4,7. That
    is why the five setters (0x4C00A5C7 / A5FB / A653 / A6AB / A702)
    hand the drawbars over TWO AT A TIME in screen order, the fifth
    carrying drawbar 9 plus the two percussive-tone bits.
  * ★ The four value rows are DIFFERENTIAL. TgPartDrawbarOffsetApply
    (0x4C00A7E5) writes the registration words into aux mod-unit fields
    +0x04/+0x05 and then ADDS the offset bytes to the sound's existing
    tone parameters: units 0..2 take perc decay/level into aux
    +0x28/+0x2E (0..100), unit 3 takes attack into aux +0x19 (0..0x7F)
    and release into aux +0x2A/+0x2C (0..100). So "ATTACK TIME +12"
    means something different on every organ patch.
  * The rows are indices, not values: setters look the nibble up in the
    signed ladder 0x48586E84 (0..7,-8..-1) and scale it.
  * ★ Item (3) of the handoff (the +/-100 offset applier) fell out here:
    TgEditOffsetAddClamp 0x4C00A7BC/_entry 0x4C00A7BE =
    clamp((u8)cur + (s8)delta, min, max), max 0x64 or 0x7F. It is the
    SHARED applier behind every offset-style edit parameter, which is
    where the manual's recurring "+/-100" ranges come from.

- ★ LFO EDIT (0x4C00CCBA..0x4C00D0AC, 10 functions) structure settled.
  TWELVE LFO groups really exist in ROM table 0x486D2ED5 (stride 0x27),
  each with four (speed, depth, ...) triples at +0x00/+0x03/+0x06/+0x09
  = the four destination pages (PITCH MOD / AMP / FILTER / PAN). The
  group is the low nibble of tone-descriptor byte +0x44; jump table
  0x48586F28 routes it to EIGHT different unpackers (the groups do not
  share a layout), each writing an 8-byte block at +0x45 of the SOUND
  EDIT record 0x500C0784+(part-0x10)*0x2C8 (parts 0x10..0x12 only,
  matching TgPartLocalEditActivate's guard).
  NOT settled, deliberately: which of the 8 block bytes is SPEED /
  PHASE / WAVE / DELAY / DEPTH / TOUCH, and whether the bit7 toggle
  (TgPartEditLfoFlagSet 0x4C00D047) is KEYSYNC or CONNECTION. Both need
  a live session driving the screen -- guessing them would be exactly
  the over-claim the docs must not make.

- Handoff item (4), the region-1 fetchers 0x4844A434 / 0x4844ABF7 and
  the bank classifier 0x485713DB / 0x48570C46, was RECONNOITRED but not
  converted. Boundaries rescanned: the classifier's true prologue is
  0x485713D6 (not the 0x485713DB call target) and its twin's is
  0x48570C41 (not 0x48570C46). Both are bank SEARCH loops: for source
  1,2,3,4(,5) ask 0x48448C0F(source) whether that source is present
  (-> 0x4844A3D4), then a per-source lookup (0x48571585 / 0x485715F8 /
  0x4857166B / ...) with the key (arg2<<16)|(arg1<<8)|arg0 -- i.e. a
  MIDI-shaped bank-MSB / bank-LSB / program triple, matching the
  SOUND EXPLORER screen's "[32.11-1" annotations. The returned source
  number IS the class code 1..5 the resource fetchers use. Naming the
  five banks still needs 0x4844A3D4 read out.

NEXT (CONVERT track): (1) the region-1 bank classifier pair
0x485713D6 / 0x48570C41 + the presence probe 0x4844A3D4 -- naming the
five banks (factory / expansion / user / GM2 / drum?) is the last hop
and would let the resource docs say WHICH banks exist; (2) the twelve
near-identical SOUND EDIT flag refreshers 0x4C00EDE4..0x4C00F127 (they
copy single bits out of the part-setting record 0x500B5340+part*0x54C
into SOUND EDIT record bytes +0x4D/+0x4E/+0x4F/+0x51 -- uniform,
cheap, and they finish section 3 of notes/sound-edit-parameters.md);
(3) the remaining resource fetchers 0x4844A434 / 0x4844ABF7; (4) still
open: the channel-EG caller module 0x4C004DE4..0x4C005673. Live-session
questions: the LFO block byte roles + the KEYSYNC/CONNECTION toggle
(above), SUSTAIN vs 0x50009D38, partrec bit12 panel trigger.

## Tick 2026-07-20 — KN6000 table/font ROM: placeholder retired, TEXT RENDERS

- The kn6000/kn6500 `"table"` ROM_LOADs were verified to be a **placeholder, not a
  dump**: `kn6xxx_table_even/odd.rom`'s low 1 MB is byte-for-byte the program ROM's
  upper 1 MB (the region reproduced program bytes 0x200000..0x3fffff, i.e. IK2/IKV2
  loaded twice) and their high 1 MB is all 0xFF. They had zero emulation effect.
- Felipe's call: replace them with the **KN7000's table ROM flagged BAD_DUMP** so the
  models are usable, with the truth stated in the driver comment — rather than NO_DUMP.
- Shipped, plus `ROM_FILL(0x000000, 0x000200, 0xff)`: loading the KN7000 table ROM
  whole makes the KN6000 derail to a permanently BLACK screen (black at t=6..40 s);
  blanking just the identity header before the font-pointer block at 0x200 gives the
  full play screen **WITH TEXT** (PMEM: A-, 8 Beat 1, ♩=120, part names, voice names).
  Verified from the PUBLISHED folder and confirmed by Felipe on the live display.
- **The real fix is still a hardware dump of IC13 (QSIGX3C16008) / IC14 (QSIGX3C16007)**
  on the KN6000 and C3FBMD000069/68 on the KN6500 — undumped. Nothing table-derived on
  a KN6xxx screen is KN6xxx-authentic. That dump likely also unblocks their TG sample maps.
- KN6500: measured no benefit yet (identical screen loaded/blanked/header-intact) — its
  font path diverges and needs tracing. KN2400/KN2600: never had a placeholder, and
  injecting the KN7000 table changes nothing (they read nothing from 0x48000000) — a
  different cause. No regressions: kn7000 boots home with text, kn2400 boots.

## AUTONOMOUS-STATUS tick — CONVERT track, 2026-07-20 (618 -> 652)

Handoff items (1), (2) and (3) all landed. `kn7000_disassembly` commit
036e68b; both flash images still rebuild **100% byte-identical**
(`make verify`).

- ★ **THE FIVE VOICE-RESOURCE BANK SOURCES ARE NAMED.** New write-up:
  `notes/sound-bank-classes.md`. The classifier's key is the MIDI triple
  the SOUND EXPLORER screen prints ("[32.11-1"):
  `key = (bank MSB << 16) | (bank LSB << 8) | program`. Byte order
  confirmed independently by `CustomVoiceRecFetch` (0x4844A42F), which
  reads a stored 3-byte `{program, LSB, MSB}` record and passes it
  straight to `VoiceRecFetchBanked_entry`. The classifier probes sources
  1..4 for presence, first hit wins, and the winning SOURCE NUMBER is
  the class code:
    class 0 INTERNAL 0x48000000 (dir *(0x48000018)) = factory presets
    class 1 0x57000000 = factory read-only data flash
    class 2 0x56000000 = CUSTOM flash (disk-programmed)
    class 3 0x41000000
    class 4 0x41800000
  Sources 1..4 are validated identically by the boot archive parser
  0x48449EF4..0x4844A3D1: `*(base)+base == base+0x200` plus a 16-byte
  compare against the ROM string **"Expansion Board"** at 0x485B8518,
  then presence byte `0x501496B4+n` is set. `VoiceBankSourceFlagGet`
  0x4844A3D4 reads it; two sibling probes (0x4844A3EE/0x4844A3F2) are
  `return 0` stubs in this firmware.
  DELIBERATELY NOT CLAIMED: which SOUND GROUP panel button (MEMORY vs
  EW EXPANSION) is which of classes 1..4 — the firmware uses the same
  signature for all four windows and only the address differs. Needs a
  live session with a card/board fitted.
  All ten per-source lookups are one shape: a multiplicative-hash bucket
  walk with base-relative offsets (params at `dir+0x24`, buckets at
  `dir+0x0C`, chain link +0 / key +4 / payload +8). Family B
  (`VoiceParamBank*`) additionally reads bit15 as "invalid" and degrades
  exact -> LSB rounded to a multiple of 8 -> LSB-only -> 0x7F7F default.

- Item (2): the SOUND EDIT flag refreshers are **NINE, not twelve** —
  0x4C00EDE4..0x4C00F12A. (Standing lesson again: the handoff count came
  from call targets; rescanning prologues gives nine.) All converted;
  section 3 of `notes/sound-edit-parameters.md` now has the full field
  table (+0x4D/+0x4E/+0x4F/+0x51 bit7 and bits0-6, plus whole bytes
  +0x52/+0x53) and their sources in `0x500B5340+part*0x54C`. Eight are
  straight mirrors; `TgSoundEditFlag51Bit7Refresh` (0x4C00EFA8) derives
  its bit from a 2-bit mode field at +0x62 bits11-12 plus +0x00 bit3,
  +0x62 bits14-15 and byte +0x14 — left unnamed pending a live session.

- Item (3): `CustomVoiceRecFetch` 0x4844A42F/34 (resource block
  0x4848463F() + 0x1A7 + idx*0x8E, else error 0x26 + the triple
  fallback) and `UserVoiceRecPtr` 0x4844ABF7 (`*(0x501496B8) + 0x70F7 +
  idx*0x8E`, the user/MEMORY record leaf). Also named+converted the
  family-B record fetcher `VoiceParamRecFetchBanked` 0x48449925/2A
  (bank descriptor `+0x1C` directory + index*0x10).

- unidasm GOTCHA worth recording: at 0x4844A3E3 unidasm prints
  `f4  movbu (d0,a0),d0` consuming ONE byte and then shows a phantom
  `00  clr d0` — which made the presence probe look like it always
  returned 0. The real encoding is the two-byte `f4 00`; the encoder
  round-trips it and `make verify` proves it. Do not read semantics off
  a single unidasm line in the F0/F4 groups.

NEXT (CONVERT track): (1) the SIBLING classifiers immediately after the
two converted ones — 0x48571056 and 0x4857176B (and further on) have the
identical five-source shape and are probably the rhythm/style and other
resource kinds; converting them would extend `sound-bank-classes.md`
into a general resource-archive chapter; (2) still open from before: the
channel-EG caller module 0x4C004DE4..0x4C005673; (3) the boot archive
parser itself 0x48449EF4..0x4844A3D1 (four near-identical blocks, cheap,
and it is the code that decides what a fitted expansion looks like).
Live-session questions unchanged: LFO block byte roles, the
KEYSYNC/CONNECTION toggle, the six SOUND EDIT low-bit sources, and which
panel button maps to bank classes 1..4.

## AUTONOMOUS-STATUS tick — CONVERT track, 2026-07-20 (652 -> 689)

Handoff item (1) landed, with a **negative answer to the question it was
asked**. `kn7000_disassembly` commit 16a3b54; both flash images still
rebuild **100% byte-identical** (`make verify`), zero `.byte` escapes in
the 37 new functions.

- ★ **THE SIBLING CLASSIFIERS ARE NOT THE RHYTHM/STYLE ONES.** All four
  (0x48571056, 0x4857176B, 0x48571CA0, 0x485720D2) are four MORE hash
  directories inside the SAME five voice archives. An archive's sound
  directory carries **six** parallel hash tables, each a (bucket-table,
  descriptor) pair, descriptor = `{u16 mult, nbuckets, countA, countB}`:
    `+0x08/+0x20` u32 -> u16  family B `VoiceParamBank*`
    `+0x0C/+0x24` u32 -> u16  family A `VoiceBank*`
    `+0x28/+0x2C` u16 -> rec  `VoiceListIndexOfBank`
    `+0x30/+0x34` u16 -> rec  `VoiceListEntryByIndex`
    `+0x38/+0x3C` u16 -> rec  `VoiceListIndexMapAtoB`
    `+0x40/+0x44` u32 -> u8   `VoiceAttrClassify`
  Each archive also carries a **kind byte** `*(u8*)(window + *(window))`
  (`VoiceArchiveKindByte` 0x48571C41 + a byte-identical twin at
  0x48572073); the index classifiers **skip any fitted source whose kind
  differs from the requested one**, which is how one window can hold
  more than one resource kind.
- The layer's purpose is **two global index spaces** over the merged
  list of every fitted archive — space A (byte-wide, `VoiceArchiveCountA`
  0x48572225) and space B (halfword-wide, `VoiceArchiveCountB`
  0x485722E0) — a local index becoming global by adding the running sum
  of `(count+1)` over preceding sources. The tone/drum selection grids
  walk a fixed triple (verbatim from `ToneSelGridSe` 0x484DF84E ->
  0x484DF863 -> 0x484DF883, repeated in `TsetGridSe`, `DrumTsetGridSe`,
  `DrumMainGridSe`, `DrumLfoGridSe`):
    `(bank LSB, program)` -> index A -> (`+1`) index B -> (`&0x7FFF`)
    -> `(kind, byte0, byte1)`.
  `VoiceListEntryByIndex` is the exact INVERSE of `VoiceListIndexOfBank`.
- ★ **NO STYLE-DATA CONNECTION.** Every caller of this layer in the whole
  image is a voice/drum SELECTION GRID; nothing probes a rhythm/style
  window and no style-shaped key enters these directories. Recorded
  prominently in `notes/sequenced-playback-and-style-data-rootcause.md`
  so the Phase C dump case is not mis-credited: this pass rules out one
  candidate shortcut, it does not sharpen the case. A style-side
  equivalent, if it exists, is a separate and still-unfound code path.
- Write-up: `notes/sound-bank-classes.md` **Part 2** (the six-directory
  table, the two index spaces, the grid call sequence, the full function
  map).
- DELIBERATELY NOT CLAIMED: which UI axis space A and space B each are
  (group ordinal vs sound ordinal is the natural reading, but the code
  does not say so); and the meaning of the byte `VoiceAttrClassify`
  returns (0xFF = none) — its only wrapper `VoiceAttrByteGet`
  (0x48449B14, staging through the scratch byte 0x5003A5B8) has **no
  caller in this image**.
- STANDING LESSON held a fifth pass: the handoff addresses 0x48571056 /
  0x4857176B were prologues this time, but the leaf helpers were not —
  the `retf`/`rets` key-compare and hash leaves start 2-3 bytes after the
  preceding `ret` (0x485713B7 not 0x485713B5, 0x48571C23 not 0x48571C21,
  0x48572055, 0x485725E9), and unlike family A's hash they carry **no
  register-save prologue** at all. Rescan; do not interpolate.

NEXT (CONVERT track): (1) the **boot archive parser 0x48449EF4..
0x4844A3D1** — four near-identical blocks, cheap, and it is the code
that decides what a fitted expansion looks like (still unconverted after
two handoffs); (2) the **channel-EG caller module 0x4C004DE4..
0x4C005673**, open for several passes now; (3) the module immediately
after this one, 0x48572607.., which starts with the same
`movm [d2,d3,a2,a3] / add -0x10,sp / mov a1,a3` shape as
`VoiceListIndexOfBank` — likely a further index variant worth a boundary
scan; (4) for the STYLE question specifically, stop looking in the shared
archive-directory layer and start from the rhythm/style resource fetchers
themselves. Live-session questions unchanged: LFO block byte roles, the
KEYSYNC/CONNECTION toggle, the six SOUND EDIT low-bit sources, which
panel button maps to bank classes 1..4, and now the two index spaces'
UI meaning.

## AUTONOMOUS-STATUS tick — CONVERT track, 2026-07-20 (689 -> 729)

**FORTY functions converted** across the three open handoff items;
`kn7000_disassembly` commits **6b52e50** (+32) and **d16917b** (+8). Both
flash images still rebuild **100% byte-identical** (`make verify`), **zero
`.byte` escapes** in the new code.

- Item (1) DONE, and it was **ONE function, not four**: the boot archive
  parser is 0x48449EF4..0x4844A3D4, four near-identical INLINE blocks. Per
  window (0x57000000 / 0x56000000 / 0x41000000 / 0x41800000): header
  self-check `*(base)+base == base+0x200`, then two 16-byte signature
  compares against `"Expansion Board "` (0x485B8518) at `*(base+4)` and
  `*(base+8)`; present -> presence byte 0x501496B4+n = 1, archive ID
  `*(base + *(base))` -> 0x501496A4+n*4, and slot n+1 of the five parallel
  descriptor arrays 0x5003A554/68/7C/90/A4 from `dir = base + *(base+0x0C)`,
  `dir + *(dir+0x14)` and that `+0x0C`; absent -> every slot aliases the
  INTERNAL bank (index 0, built from table ROM `*(0x48000018)`). Corrected
  the stale symbol `0x4844A000 CustomFlashArchiveParse`, which sat in the
  middle of this function.
- Item (2) DONE: the channel-EG caller module 0x4C004DE4..0x4C00566E is
  **eight** functions = the **GLOBAL EFFECT-CHANNEL REFRESHERS**, the caller
  layer above the output-channel register file at 0x4C037D0F. Seven own one
  fixed global channel (1, 3, 5, 6, 7, 0x0B, 0x0C) and are re-run by the
  effect ENABLE setters at lib 0x4C00908F+; 0x4C0053B3 / 0x4C005433, named
  in `notes/reverb-toggle-findings.md` as the "lib consumers" of the reverb
  flag 0x500C0758, live inside two of them. The eighth (0x4C004DE4) is the
  per-PART variant (channel = partrec+0x62 bits 10..8 through ROM
  0x486D109A). DELIBERATELY NOT CLAIMED: which panel effect each fixed
  channel is — only bit9 = reverb is identified anywhere.
- Item (4), THE STYLE QUESTION, taken from the rhythm/style side as advised:
  the **whole style NAME module 0x484332F9..0x48433C1E (22 functions)** plus
  the resource **WINDOW PROBE** 0x4843D6D7 and the eight table-ROM segment
  accessors around it are now source. Three style SOURCES (built-in resource
  / MEMORY / CUSTOM) selected by style-ID bits 0x00700000, the name
  select+commit path, the 20 variation-record slots 0x50034BCC[], the
  record-bind layer that publishes a style into the pattern player's runtime
  view at 0x50122DC0.., and the built-in name resolver.
- ★ **CORRECTION TO MY OWN FIRST WRITE-UP OF THIS TICK.** I initially framed
  the style finding as new. It is mostly NOT: `notes/rhythm-name-list-bug.md`
  (2026-07-07) and blog Part 35 already established the count 0xDD = 221, the
  intact table-ROM directory, the ~4.1 MB resource size, the 0x54E00000
  install window and the shipped 52-real-names synthetic. Section **2a-bis**
  of `notes/sequenced-playback-and-style-data-rootcause.md` has been rewritten
  to say so up front. What the conversion actually adds:
  (a) STATIC confirmation of why `*(0x50034B7C) = 0x483E82BF` — at its tail
  `StyleBuiltinNameTableInit` overwrites the name-table pointer with the
  TABLE-ROM copy's `u24BE(+0x1B)` **regardless of which resource the probe
  won**, so the real name table is structurally guaranteed and a synthetic
  can never substitute its own; that is why the shipped synthetic's numbering
  lines up.
  (b) NEW: `StyleVariationNameGet` (0x484335BF) resolves VARIATION names
  through the **library resource dispatcher** (lib 0x4C0149FA, resource id
  0x0000D00A -> ROM pointer table 0x48736078), not through the flash resource
  — so variation names were never blocked by the missing dump.
  (c) NEW: only the BUILT-IN one of the three style sources depends on the
  missing flash; MEMORY (0x484355E2 / 0x484355F8) and CUSTOM (0x4848457D /
  0x4843E107..0x4843E128) have their own fetchers.
  (d) Where the truncation falls, for the record: full 0x800-entry name table
  intact, **177 of 221** sub-table offsets, **zero** name records, surviving
  offsets monotonic to +0x3E5D75 (~4.08 MB).
  **NOT claimed:** nothing here recovers a name or shortcuts Phase C.
  LESSON: before writing up a "finding", grep the existing notes AND the blog
  summaries for it. I nearly shipped a blog post re-announcing Part 35.
- Item (3), the module at 0x48572607.., was SCOPED but NOT converted: it is
  ~31 functions and it is a THIRD directory family — a hash directory
  resident in the PROGRAM ROM (params 0x4876398C/8E, buckets 0x48763990,
  u16 keys, 2-byte payloads) with the same graceful-degrade chain as family
  B (exact -> LSB & ~0x3F -> MSB rounded to a multiple of 8 -> LSB only ->
  0x7F/0x7F). Its callers are all in the voice-resource area (0x48449264,
  0x48449281, 0x48449416, 0x4844C31B, 0x4844CB48), so it is voice, not
  style. Left for the next tick.
- STANDING LESSON held a sixth pass: **three of the pre-existing style
  symbols were on call ENTRY addresses, not function starts** (0x48433300 /
  0x48433400 / 0x48433AC4 -> real prologues 0x484332F9 / 0x484333FF /
  0x48433ABF), and two functions in each of the style and EG modules have
  **no register-save prologue at all** (0x48433919, 0x48433A80, and five of
  the eight channel refreshers). Rescan; never interpolate.

NEXT (CONVERT track): (1) the program-ROM directory family at
0x48572607..0x485731FB (~31 functions, scoped above — the third and last of
the three directory families); (2) the effect ENABLE setters themselves at
lib 0x4C00908F.., which are the callers of the channel refreshers just
converted and are the place where the 0x500C0758 bits other than bit9 could
finally be pinned to panel buttons; (3) the MEMORY / CUSTOM style sources
0x484355E2 / 0x484355F8 / 0x4848457D / 0x4843E107..0x4843E128, which are the
only style paths that do NOT depend on the undumped flash. Live-session
questions unchanged, plus: which panel effect owns each fixed global channel
(1, 3, 5, 6, 7, 0x0B, 0x0C).

## AUTONOMOUS-STATUS tick — CONVERT track, 2026-07-20b (729 -> 773)

**FORTY-FOUR functions converted**, `kn7000_disassembly` commit **887169f**.
Both flash images still rebuild **100% byte-identical** (`make verify`, clean
`build/`); **zero new `.byte` escapes** (the 5 in `src/program.s` are the
pre-existing boot-header ones plus the one known non-minimal `call`).

- NEXT item (2) DONE and it is the whole **TG GLOBAL-PARAMETER MODULE
  0x4C008CBB..0x4C009837** — not just "the effect enable setters". Master
  volume / master tune / group gains, the effect ENABLE bits, and the
  **COMMAND DISPATCHER** that drives every one of them.
- ★ `TgGlobalParamCommand` **0x4C0092B3** (entry 0x4C0092B9) is **ONE**
  function: id 9..0x50, `slot = (id-8) & 0x3F` in the 64-entry program-ROM
  key/handler table **0x48586C60** (`u32 key = id-8`, `u32 handler`), and the
  ~30 handler blocks are **inline**, all returning through its frame. Its
  **only** caller is the sound-command byte-stream interpreter **0x4C003ED3**
  — so every global TG parameter is set by a two-byte stream message, never by
  a direct call from the UI.
- ★ **THE BIT MAP IS PARTLY CLOSED** (write-up: new file
  `notes/effect-enable-bits.md`). Each enable handler re-runs the global
  channel refreshers converted last tick, and each refresher gates on the same
  bit, so the bit -> sub-TG-channel edge is static fact; crossing it with the
  LIVE per-effect send/return capture in `effect-return-routing.md` names two:
  - **bit9 = REVERB** — handler id 0x40 refreshes chan **3** + chan **0x0B**,
    exactly the live reverb RETURN ch03.rA and SEND ch0B.r8. (Bit9=reverb was
    already known from the button trace; this is an independent structural
    confirmation, not a new claim.)
  - **bit12 = MULTI** (NEW) — handler id 0x45 refreshes chan **0x0C** + chan
    **6**, and chan 6 is the live-captured MULTI return ch06.rA.
  - bit13 (id 0x46) -> chan 1, bit14 (id 0x47) -> chan 5, bit10 (id 0x41) and
    bit4 (id 0x42) refresh no channel: **DELIBERATELY NOT NAMED**. CHORUS
    (ch19) and SOUND DSP (ch09) are per-part matrix rows, not global channels,
    so their enables are not observable in this halfword — the natural guess
    that bit10/bit4 are them is NOT claimed.
  - bit11 (chan 7) has no setter here at all; it is set/cleared at
    0x4C00840E / 0x4C008420 and is the most widely READ bit in the image
    (the whole per-part apply layer 0x4C0046E6..0x4C004F41 gates on it).
- NEW side facts: bits 1..3 of 0x500C0758 are a **3-VALUE ROUTE FIELD**
  (`TgEffectRouteSelect`, id 0x29), and **route value 3 forces REVERB ON** —
  `TgEffectEnableReverb(0)` takes the enable path anyway when bit3 is set.
  0x500C075A bit3/bit4 are the (INVERTED) gates for the group master gains
  0x500C0760 / 0x500C0762 that `TgLevelTermFinalize` was already documented to
  apply, and bit5 gates the SUB master-volume term — the read side and the
  write side of those three now meet.
- ANTI-DUPLICATION check ran BEFORE writing anything: grepped the notes tree
  and `mame-blog/posts/kn7000/*.md` for 0x500C0758 / 0x48586C60. Only bit9 was
  ever published (blog Part 27, and `per-part-effect-application.md` had
  bit9/bit10/bit11 as unnamed). **No blog post written** — one new bit name
  plus a dispatcher table does not clear the series bar on its own; it belongs
  in the notes. If bits 10/4 later resolve to CHORUS/SOUND DSP, the whole
  CPU-side-meets-DSP-side story becomes post-worthy.
- STANDING LESSON held a SEVENTH pass: **twelve** of the 44 starts are
  prologues 2-6 bytes ahead of the address the callers use (0x4C008CBB not
  0x4C008CC0, 0x4C0092B3 not 0x4C0092B9, ...) and **twenty-five** of them are
  bare leaves with no prologue at all. Also a fresh gotcha for the disasm
  helper: `unidasm` will happily decode past the end of a short `dd` window
  and print phantom instructions from the zero padding — always dump more
  bytes than you intend to read.

NEXT (CONVERT track): (1) the **program-ROM directory family
0x48572607..0x485731FB** (~31 functions, the third and last directory family;
scoped two ticks ago, still untouched); (2) the **MEMORY / CUSTOM style
sources** 0x484355E2 / 0x484355F8 / 0x4848457D / 0x4843E107..0x4843E128;
(3) for the effect-bit question specifically, stop looking in the library and
go to the **PRODUCER of the command ids** — the maincpu code that builds the
two-byte sound-command messages consumed by 0x4C003ED3 — because that is where
a panel button and a command id sit in the same basic block, and it is the
only remaining way to name bits 4/10/13/14. Live-session questions unchanged.

## CONVERT tick 2026-07-20 -- the SOUND-COMMAND PRODUCERS (773 -> 808)

Took target (1) from the previous tick: the region-1 code that BUILDS the
two-byte sound-command messages. **35 functions converted, `make verify`
byte-exact, clean rebuild at the end.** kn7000_disassembly commit 348551b.

- ★ **The "sound-command byte stream" is an internal MIDI stream.** The
  interpreter is **0x4C003B31** (not 0x4C003ED3 -- that address is just the
  *0xFx case* inside it). It dispatches on `status & 0xF0`: 0x9x note,
  0xAx, 0xBx control change, 0xCx program change, 0xDx, 0xEx -> the TG
  global module's other entry 0x4C008C74, and **0xFx + two data bytes ->
  `TgGlobalParamCommand(id, value)`**. Producers build a length-prefixed
  buffer `{ len, status, data... }` and call the writer **0x4C003A65**
  (32 call sites image-wide). Named on the library side:
  `SndCmdStreamWrite` / `SndCmdStreamGetByte` / `SndCmdStreamSkipToStatus`
  / `SndCmdStreamInterpret`.
- ★ **Exactly three region-1 producers of 0xFx messages exist** (found by
  both a code scan and a data-region scan for the template
  `03 F0 <id 9..0x50> <val<=0x7F>`):
  `SndCmdEmitUnitCc` 0x48410FB0 (id 0x35), `SndCmdEmitGlobalDepth`
  0x48411101 (ids 0x32 / 0x33 / 0x34, value = `pct * 0x7F / 0x63`), and
  `SndCmdSendReverbPartsApply` 0x4844B334 (the only ROM-resident template,
  0x485B85EC = `{3, 0xF0, 0x2B, 0x7F}` = `TgReverbPartsApply(0x7F)`).
- **Converted:** the SOUND-UNIT SETTING module 0x484104C7..0x4841202C (26
  functions -- five param-DB groups 0xB010..0xB050 read via `LibParamGet`,
  applied to the TG and re-broadcast), the canned-message sender, and the
  PART-FLAG message builders 0x484A0B39..0x484A0CB0 (8).
- **HONEST NEGATIVE on the bit question:** the effect ENABLE ids 0x40..0x47
  have **no region-1 producer at all**. Nothing in the maincpu image builds
  a 0xFx message with those ids, so bits 4/10/13/14 could NOT be named this
  tick. They are driven from the **library**: the id list at **0x485870F0**
  (`01..0b 10 11 20 40..4b ff`) is referenced only from library code around
  **0x4C00FB94**. That consumer is the next place to look -- the earlier
  plan ("go to the maincpu producer") is hereby retracted as a dead end for
  the enable bits, though it did pin the *depth* controls.
  Write-up: `notes/effect-enable-bits.md` section 6.
- What the trace DID pin: id 0x32 -> 0x500082BE -> chan 0x0B (the
  live-captured REVERB SEND) is produced by a **percent-valued** control
  (0..99 -> 0..127) -- the shape of a front-panel depth control, and the
  first time a region-1 control and the reverb send channel appear in one
  basic block.
- ANTI-DUPLICATION ran first: grepped notes/ and mame-blog/posts/kn7000/ for
  0x4C003ED3 / 0x4C003A17 / 0x48586C60 / 0x485870F0. Nothing published.
  **No blog post** -- a producer trace with a negative result on the bits
  does not clear the series bar; it belongs in the notes.
- STANDING LESSON, eighth pass: the unidasm **f4-page phantom** bit again
  (0x484104FB decodes as `cmp 0x85,a1 / movbu d1,(0xcbcb)` in the raw
  listing -- pure garbage; the real bytes are `f4 b5` + `85 06`). The
  byte-exact rebuild is the only trustworthy check. Also: 0x4C003ED3 being
  cited as "the interpreter" for two ticks was exactly this class of error
  -- a mid-function address mistaken for an entry point.

NEXT (CONVERT track): (1) the **library consumer of the id list 0x485870F0
around 0x4C00FB94** -- the last route to naming enable bits 4/10/13/14;
(2) the **program-ROM directory family 0x48572607..0x485731FB** (~31
functions, still untouched, scoped three ticks ago); (3) the MEMORY /
CUSTOM style sources 0x484355E2 / 0x484355F8 / 0x4848457D /
0x4843E107..0x4843E128.

## CONVERT tick 2026-07-20b -- the VOICE-DIRECTORY family (808 -> 839)

Took targets (1) and (2) from the previous tick. **31 functions converted,
`make verify` byte-exact, clean rebuild.** kn7000_disassembly commit a2c21c9.

- ★★ **TARGET (1) IS A DEAD LEAD, AND IT IS NOW RETRACTED.** The library
  consumer of the byte list **0x485870F0** around 0x4C00FB94 was read: it is
  the per-part **class-register TAG table** of the sub-TG register cache --
  the very table the already-named `TgPartClassRegCollect` 0x4C00FBC5 walks
  in parallel with `0x500C59E4 + part*0x36`. **Different id space from
  `TgGlobalParamCommand`**: twelve of its 27 tags are 0x00..0x0B, below the
  dispatcher's minimum id of 9, and no dispatcher id ever traced (0x14 0x19
  0x1A 0x20 0x21 0x29 0x2B 0x32..0x35 0x48..0x4B) appears in it. The overlap
  on 0x40..0x4B is a numeric **coincidence**. Companion tables found:
  0x48587030 maps `tag & 0x3F` -> dense slot 0..0x0E, 0x485870B0 -> 0x0F..0x1A.
  Two of the three collectors there (0x4C00FB3C, 0x4C00FC3C) have **no caller
  in the image at all** -- unused library code.
- **VERDICT ON BITS 4/10/13/14: still unnamed, and BOTH static routes are now
  exhausted** (no region-1 producer of ids 0x40..0x47; no library route via
  0x485870F0). Written up as `notes/effect-enable-bits.md` section 7, with the
  retraction stated plainly.
  **QUEUED LIVE TASK** (the only thing left that can settle it): on the play
  screen with sound (CONFIG bit2), watch halfword `0x500C0758` / break on
  `TgGlobalParamCommand` 0x4C0092B3 while pressing REVERB, CHORUS, SOUND DSP,
  MULTI, DIGITAL EFFECT and the per-part effect keys; log
  `(button, id, value, 0x500C0758 before/after)`. A sweep that moves none of
  the four bits is itself a result (they would be dead in this firmware).
- **TARGET (2) DONE and it is the whole gap 0x48572607..0x48572F46** -- the
  third and last MILK open-hash **DIRECTORY FAMILY**, five tables, same
  generated shape as VoiceList*/VoiceBank*: `{u16 count, u16 modulus}` header,
  modulus-sized chain-head array, `{u32 next, key, payload}` records,
  `{Find, KeyEqual, HashIndex}` triple, HashIndex = `(key*count)/modulus`.
  New structural fact: each table carries a **PROBE CASCADE** on top that
  retries with progressively coarser keys (drop the low byte, round the high
  byte down to a multiple of 8, mask the low byte to 0xC0) before giving up.
  Tables: 0x4876398C (986, u16 key, 2-byte payload), 0x48763F5C + 0x48764944
  (570 each), 0x4876532C (645, 12-byte), 0x48765D14 (582, **u32 key**
  `(part<<16)|(bank<<8)|program`, folding parts 0x28..0x2F onto 0x20..0x27 --
  the same folding `VoiceModRecFetch` already does). Callers are the thin
  wrappers 0x4844910D..0x4844943F next to VoiceRecFetchBanked /
  VoiceParamRecFetchBanked / VoiceAttrByteGet.
- ★ Same gap also yielded the **SOUND EDIT TARGET REGISTRY**: three 4-byte
  slots 0x50006194 / 0x50006198 / 0x5000619C = `{valid, b0, b1, b2}`, one per
  edit target 0x10/0x11/0x12 -- the same three parts the SOUND EDIT record
  0x500C0784+(part-0x10)*0x2C8 covers. `SoundEditRefSet` 0x48572E6B is called
  by AcCompareToggleSeProc / VwSnameSeProc / OctShiftSe / RightSplitSe /
  LeftSplitSe / MonoPolySe and the rest of the "Se" handlers;
  `SoundEditRefInvalidatePost` 0x48572EF1 posts event **0x90C00000** and
  `SoundEditSelEventHandler` 0x48572D61 is the sink that clears the slot.
  Its sibling event 0x900000 loads the **DRUM note selection 0x5009260C**
  that `DrumNoteSelGet` returns to DrumNoteSelSeProc.
- Plus `VoiceBankIdToAlias`/`FromAlias` (0x0E <-> 0x11, 0x1E <-> 0x23) and the
  constants `VoiceBankIdSource1`/`Source2` behind them, taken only after
  `VoiceBankSourcePresent` reports the expansion archive fitted.
- NEW TOOL, committed: **`kn7000_disassembly/tools/dis_view.py`** -- read-only
  named linear disassembly of any CPU range, reusing gen_program_s.py's
  F4-length-bug-aware decoder. MAME's `mn10300_disassembler::disassemble_f4`
  returns length **1** for a 2-byte instruction (mn103dasm.cpp), which is the
  root cause of the "f4-page phantom" that has now bitten this track nine
  times. Use dis_view.py instead of raw unidasm for reading from here on.
  (An upstream one-character MAME fix -- `return 2 | SUPPORTED;` -- is worth
  filing; noted alongside the SHARC series in `sharc-upstream-patch-series.md`
  territory, submission is Felipe's.)
- ANTI-DUPLICATION ran first: grepped notes/ and mame-blog/posts/kn7000/ for
  0x485870F0 / 0x48587030 / 0x4876398C / 0x50006194 / 0x5009260C. Only
  0x485870F0 and TgPartClassRegCollect were previously mentioned (this file's
  0x4C011730 module tick), and the effect-bit lead in effect-enable-bits.md.
  **No blog post** -- a directory family plus a retraction does not clear the
  series bar. If the queued live sweep names bits 4/10/13/14 (or proves them
  dead), *that* is the post.
- STANDING LESSON, ninth pass: the "cited address is really mid-function" trap
  again -- 0x4C00FB94 is not a function start, it is the `mov 0x485870F0, a0`
  operand inside TgPartClassRegCollect's sibling. Nine of this pass's 31
  starts are prologues 2-5 bytes before the address callers use, and eleven
  are bare `retf`/`rets` leaves with no prologue at all.

NEXT (CONVERT track): (1) the **MEMORY / CUSTOM style sources** 0x484355E2 /
0x484355F8 / 0x4848457D / 0x4843E107..0x4843E128 (scoped four ticks ago,
still untouched); (2) the small **validated-index getter/setter block**
0x485731FB..0x48573287+ (five index variables 0x500062FC..0x5000630C, each
range-checked against a count from 0x48579303 / 0x485792FA / 0x4857B251 /
0x4857B249; ~14 functions, but naming them needs the 0x48575xxx / 0x48577xxx
callers read first); (3) `InitializeBlock34` 0x48572F46 and the rest of the
block up to AcIntTitleMenuSDProc 0x485736B7. Live task queued above.

## CONVERT tick 2026-07-20c -- the "TCMP" style container + the SD browser cursors (839 -> 898)

Took both scoped targets. **59 functions converted, `make verify` byte-exact,
clean rebuild.** kn7000_disassembly commits 52bd978 (33) and 1d16d8a (26).

- ★★ **TARGET (1) DONE, and the two style sources that WORK are now source.**
  StyleNameSourceSet picks a source from the style-ID bits 0x00700000; the
  built-in arm needs the resource window StyleResourceWindowProbe never finds in
  emulation, but MEMORY and CUSTOM have their own fetchers and those are now
  converted: `MemStyleRecPtr` 0x484355E2 / `MemStyleVarRecPtr` 0x484355F8 /
  `MemStyleRecData` 0x48435614, `CustStyleRecPtr` 0x4843E107 /
  `CustStyleVarRecPtr` 0x4843E10C / `CustStyleRecData` 0x4843E128, and
  `CustomStyleBlockFetch` 0x4848457D.
- ★ **NEW STRUCTURAL FACT: MEMORY and CUSTOM are the SAME container format**,
  parameterised only by the style count N. The header is the "TCMP" layout the
  table ROM's segment 2 also carries (ROM template 0x487312E8):
  `+0x00 "TCMP"`, `+0x04 00 00`, `+0x06 u16BE checksum`,
  `+0x08 u24BE checksum start (0x70)`, `+0x0B u24BE length (0x1B00 HALFWORDS)`,
  `+0x13 u24BE bump-allocator top`, `+0x70 N style records stride 0x80`,
  `+0x70+N*0x80 N*20 variation records stride 0xE0`, then the event-stream heap.
  MEMORY = RAM 0x50180000, 0x25800 bytes, **N = 3** (variations at +0x1F0, heap
  at +0x3670); CUSTOM = a flash block with **N = 1** (records +0x70, variations
  +0xF0). 0x70 + N*0x80 in both cases; the numbers 0x1F0/0x3670/0x0003 sit in
  the ROM template verbatim.
- ★ **CUSTOM flash located: bank 0x96820000, RAM-shadowed at 0x5037A000**
  (0x6000 words written back through FlashProgram128Words), status halfword
  *(0x50001298) (-1 = absent), and a **20-entry** slot descriptor array at
  0x96820002 + slot*2. `CustomSoundEditRecFetch` hands out 0x2C8-byte records
  from a slot's block -- the same stride as the SOUND EDIT record
  0x500C0784+(part-0x10)*0x2C8.
- Also converted the five BIG-ENDIAN field primitives the whole style path funnels
  through -- `LoadU24BE` 0x48440363 / `StoreU24BE` 0x48440378 / `LoadU16BE`
  0x4844038B / `StoreU16BE` 0x48440398 / `SumU16BE` 0x484403A5 (0x484403A7 was
  already cited by StyleResourceVerify) -- and `MemStyleAreaStreamsVerify`, which
  states the **pattern-stream grammar** outright: a variation's stream opens with
  a 0xF4 bar marker, closes with 0xF5, and must contain exactly
  `MemStyleVarBarCount = (rec[0x10]+1) * ((rec[0x11]&7)+1)` markers, walked with
  RhySysexLen for 0xF0 SysEx and RhyEventLenByStatus for channel events.
- **OPEN DISCREPANCY, flagged not resolved:** kn7000_manual.sym's
  `RamCodeOverlayImage` note claims the boot code overlay is copied to **RAM
  0x50180000**. That is exactly MEM_STYLE_AREA, whose 0x25800-byte extent is
  hard-coded in `MemStyleAllocFits`. Both cannot be true; the style side is the
  one with instruction-level evidence this tick. Someone should re-read the
  0x4843B1A0 block copy before trusting the overlay destination.
- ★ **TARGET (2) DONE, and reading the callers first is what identified it** --
  0x485731FB..0x485733BC is the **SD CARD browser cursor** block. Callers are the
  Get*ListFunc list-content suppliers and the MainSDAudListSel_* /
  MainSDSndListSel_* / MainSDSndListEdit_* soft-key handlers:
  `0x500062FC` SD AUDIO song, `0x50006300` SD AUDIO list (clamped),
  `0x50006304` SD SOUND song, `0x50006308` SD SOUND list (clamped),
  `0x5000630C` SD SOUND play channel 0..0x0F (clamped),
  `0x50006310/14` LIST EDIT default list/entry, `0x50006318/1C` LIST EDIT
  current list/entry, `0x50006322` LIST EDIT move direction (+/-1 only).
  Every setter re-reads a LIVE count before committing -- which is why the
  cursors stay sane across a card swap. Two shapes: plain setters DROP an
  out-of-range index, "clamped" ones SATURATE to 0 / count-1. The two LIST EDIT
  cursors that address a list deliberately accept `index == count` -- that
  one-past-the-end slot is the NEW LIST / insert row. Counts:
  `SdAudListCountGet` (byte 0x50007F3C), `SdAudListEntryCountGet` (u16 at the
  audio list directory **0x501720F0 + list*0x18 + 0x12**), `SdSndListCountGet`,
  `SdSndListEntryCountGet`.
- ★ **UPSTREAM PATCH STAGED (the one asked for):**
  `notes/upstream-patches/mn10300-01-dasm-f4-length.patch` --
  `mn10300_disassembler::disassemble_f4` returns length **1** for a 2-byte
  instruction. It reads `opcodes.r8(pc + 1)` and prints its operands, and every
  sibling F-page handler (f0/f1/f2/f3/f5/f6) returns 2; F4 is the lone typo.
  Concrete misread, verified this tick: at **0x484357C7** the bytes
  `f4 02 | fa c8 f5 00 | c8 07` (`movbu (d0,a2),d0` + `cmp 0xf5,d0` + `beq`)
  come out of stock unidasm as FOUR lines, two of them invented
  (`movbu d0,(0xc8fa)` and `udf20 d0,d0`), resyncing only at 0x484357CD.
  3,440 F4 instructions in code region 1 alone. Fix is one character
  (`return 2 | SUPPORTED;`); patch is git-format-patch shaped like the SHARC
  series, Felipe's authorship, and `patch --dry-run -p1` clean against the
  pristine mn103dasm.cpp in kn7000_mame_build. The upstream-patches README is
  now titled as the **single index of everything staged for upstream** with a
  non-SHARC section on top. NOT applied to the overlay core (the overlay does
  not carry mn103dasm.cpp at all; only the CPU core files, whose own
  mn10300_insn_length.h already gets F4 right and documents the dasm bug).
  Submission is Felipe's.
- ANTI-DUPLICATION ran first: grepped notes/ and mame-blog/posts/kn7000/ for
  0x484355E2 / 0x4848457D / 0x4843E107 / 0x485731FB / 0x500062FC / 0x96820000.
  Only the two scoping lines in this file and style-name-build.md's source table.
  **No blog post** -- a container format plus a cursor block is notes material.
  (If the "TCMP" layout later lets us SYNTHESISE a working style container and
  kill the "8 Beat 1" fallback for the built-in source too, *that* is the post.)
- STANDING LESSON, tenth pass: two of this pass's cited addresses were again
  mid-function (0x484403A7 and 0x4848457D are the `_entry` points, prologues at
  0x484403A5 / 0x48484578), and 25 of the 59 starts are bare `retf`/`rets`
  leaves with no prologue at all (both targets are accessor-heavy). The new habit that worked: verify every
  claimed `_entry` by counting call sites for BOTH candidate addresses -- the
  prologue address should have zero.

NEXT (CONVERT track): (1) `InitializeBlock34` 0x48572F46 up to
AcIntTitleMenuSDProc 0x485736B7 (the last untouched slice of that block, and it
calls straight into the cursor block just converted); (2) the **SD SOUND LIST
EDIT engine** behind the cursors -- 0x4857B264 / 0x4857B2CC / 0x4857C28E /
0x4857C388 / 0x4857C3C3 / 0x4857C588 / 0x4857C679, the list-directory
read/insert/delete primitives (the cursors are converted but the thing they
index is not); (3) the **MEMORY style WRITER** side -- 0x484354F0..0x48435561
and 0x4843E07E.. build the 0x3C/0x14 variation records this tick only taught us
to read. Live task (effect enable bits 4/10/13/14) still queued from tick b.

## CONVERT tick 2026-07-20d -- the "TCMP" style container WRITER (898 -> 924)

Took scoped target (1), the ★ one, plus target (2). **26 functions converted,
`make verify` byte-exact, clean rebuild from scratch also byte-exact.**
kn7000_disassembly commit f4a4788. NO MAME runs, no builds in
../kn7000_mame_build (read-only use of these notes).

- ★★ **TARGET (1) DONE -- the round trip is closed.** Last pass converted
  everything that READS a "TCMP" container; this pass converted everything that
  BUILDS one. MEMORY area builder: `MemStyleAreaHeaderInit` 0x4843531A /
  `MemStyleAreaHeaderRestamp` 0x48435336 / `MemStyleRecInit` 0x484353AF /
  `MemStyleRecInitAll` 0x484353E9 / `MemStyleVarRecInit` 0x484353FE /
  `MemStyleAreaVarStreamsInit` 0x484354DE / `MemStyleAreaLoadFactory` 0x4843B15B /
  `MemStyleAreaValidate` 0x4843B1B5 / `MemStyleAreaValidateOrInit` 0x4843B1F6.
  Edit ops: `MemStyleStyleClear` 0x4843BF64 / `MemStyleVarClear` 0x4843BF2B /
  `MemStyleVarCopy` 0x4843B22E. Import: `StyleBlockKindClassify` 0x48434645 /
  `MemStyleLegacyBlockUpconvert` 0x48435221 / `MemStyleImportBlock` 0x48435280 /
  `MemStyleImportBlockStyle` 0x484352DB / `MemStyleSlotImport` 0x48435198 /
  `CustStyleImportToMem` 0x4843E000. Export: `MemStyleExportSize` 0x4843DDD2 /
  `MemStyleExportToCustom` 0x4843DEC7 / `CustStyleAllocPtrGet` 0x4843DE07 /
  `CustStyleAllocPtrSet` 0x4843DE1C / `CustStyleVarRecDataSet` 0x4843DE30 /
  `StyleRefIdMark` 0x4843DE50 / `StyleRefIdApply` 0x4843DE8D. Plus target (2)
  `InitializeBlock34` 0x48572F46 (one big function to 0x485731FB: the block-34
  MILK class table -- class IDs 0x220..0x22B with method tables 0x487666FC..
  and the seven 0x486AE0xx entries registered through 0x48431838).

- ★ **WHAT A TCMP WRITER MUST PRODUCE** (asked for explicitly; full text now in
  kn7000_manual.sym, this is the summary). Header, all multi-byte fields BE:
  `+0x00 "TCMP"`, `+0x04 00 00`, `+0x06 u16BE checksum`, `+0x08 u24BE cksum
  start = 0x70`, `+0x0B u24BE cksum length = 0x1B00 HALFWORDS`, `+0x0E u16BE
  (carried, unvalidated)`, **`+0x10 u24BE container length`** (MEMORY = the
  0x25800 capacity; CUSTOM = the used size -- `MemStyleExportToCustom` ends by
  copying the allocator top over it), `+0x13 u24BE bump-allocator top`,
  **`+0x16 u16BE N`** (the style count; the export path proves it by
  `StoreU16BE(dest+0x16, 1)`), `+0x18` a fixed 0x18-byte tail then 0x20 padding
  to 0x70. Then N style records (stride 0x80), N*20 variation records (stride
  0xE0), then the heap. The checksum covers **exactly** the record block:
  3*0x80 + 60*0xE0 = 0x3600 bytes = 0x1B00 halfwords from 0x70, which is why
  the descriptor is a constant `MemStyleAreaChecksumInit` just stamps.
  Style record: `+0x00` 13-byte name, `+0x10/0x20/0x30/0x40` four 13-byte
  variation names, `+0x50` twenty ABSOLUTE variation indices (template holds
  0..19, `MemStyleRecInit` adds style*0x14 -> style 0 owns 0x00..0x13 etc).
  Variation record: `+0x00` kind, `+0x03` bit4 pair flag, `+0x04..0x0B` eight
  per-part bytes, `+0x10/+0x11` the `MemStyleVarBarCount` inputs, `+0x15` u24BE
  stream offset. Stream: **`+0x00` the VARIATION INDEX**, `+0x01` u24BE event
  length L (total size L+4), `+0x04` events opening 0xF4 and closing 0xF5 with
  exactly `MemStyleVarBarCount` 0xF4 markers. The byte just under the allocator
  top must be 0xF5, so streams have to be allocated contiguously with no tail
  slack. Empty prototypes live in ROM right after the record templates:
  `0x487314B8` = `00 00 00 05 F4 F4 F4 F4 F5` (4 bars) and `0x487314C5` =
  `00 00 00 09 F4 x8 F5` (8 bars), picked so the marker count matches the
  `rec[0x11]=3` the builder writes. **Synthesis was NOT attempted this pass**
  (per the brief) -- but everything a synthesiser needs is now written down,
  and `MemStyleExportToCustom` is a complete worked example of building a
  container from nothing but templates and a record block.

- ★★ **THE FLAGGED CONTRADICTION IS RESOLVED, and the sym file was the wrong
  one.** `RamCodeOverlayImage` 0x48035D08 is **not a code overlay**. The live
  evidence behind that note (`LibMemCopy(dest=0x50180000, src=0x48035d08,
  len=0xa96c)`, 44036 writes spanning 0x50180000..0x5018A964) is real, but the
  routine is `MemStyleAreaLoadFactory` 0x4843B15B and both ends are DATA:
  0x4843B160 does `LibMemSet(0x50180000, 0, 0x25800)` -- MEM_STYLE_AREA, at its
  documented extent -- and then `TableRomSeg02PtrSize` (0x4843D7EF) returns
  `0x48000000 + dir[2] = 0x48035D08`, length `dir[3]-dir[2] = 0x40674-0x35D08
  = 0xA96C`. Byte-level confirmation: the chunk starts with ASCII `TCMP`,
  header checksum 0x00CC, start 0x70, length 0x1B00 HW, **allocator top
  0x00A969** (= the observed span ending at 0x5018A964), **N = 3 at +0x16**, and
  three real style names " Easy 8 Beat " / "Easy 16 Beat " / " Easy Swing  ".
  Nothing calls into 0x50180000. Renamed **`FactoryMemStyleContainer`**;
  notes/table-rom-format.md already had it right as the `'TCMP'` chunk.
  MEM_STYLE_AREA's 0x25800 extent stands unchanged. **Downstream fix:**
  notes/kn2400-boot.md carried the same misreading and built on it; a correction
  block is now inline there, including the consequence that "the KN2400 never
  populates its code overlay" is NOT a boot blocker -- the missing copy is the
  factory *style* container, which a keyboard boots fine without, so the
  0x50180000 write-tap is a red herring for that derail. (The library self-load
  finding in that note is unaffected.)

- ★ **SECOND CORRECTION, found while converting:** a variation stream's first
  byte is the **VARIATION INDEX**, not the zero "kind" byte last tick's header
  comment claimed. `MemStyleAreaStreamsVerify` at 0x484357D4 does
  `movbu (a3),d1 / extbu d2 / cmp d2,d1` against the loop counter and returns -3
  on mismatch; all three writers stamp it (`movbu <var>,(stream)` right after
  the copy in MemStyleAreaVarStreamsInit / MemStyleExportToCustom /
  CustStyleImportToMem); and the factory container has `stream[0] == var` for
  all 60 variations. kn7000_manual.sym's StreamsVerify line is corrected in
  place with the retraction visible.

- ANTI-DUPLICATION ran first: grepped notes/ and mame-blog/posts/kn7000/ for
  MemStyleExportToCustom / CustStyleImportToMem / 0x48435403 / 0x484354E3 /
  0x4843B160 / MemStyleVarClear -- zero hits outside this file.
  **No blog post yet.** The bar the last tick set was explicit: the post is
  "we synthesised a working container and killed the '8 Beat 1' fallback".
  We now have the recipe but not the dish. A post about a struct layout alone
  does not clear the series bar.

- STANDING LESSON, eleventh pass: the trap this time was a *stale symbol*
  rather than a mid-function address -- `RamCodeOverlayImage` had a plausible
  name, a real trace behind it, and a cited address (`~0x4843b1a0`) that is a
  two-byte `bra` in the middle of the routine that actually does the work.
  Rounding a caller address to "~" hid the fact that nobody had ever read the
  prologue. Also: 7 of this pass's 26 starts are prologues 3-5 bytes before the
  address callers use, and 0x4843B1F9 has 10 call sites against 0 for its
  prologue 0x4843B1F6 -- the count-both-candidates habit paid off again.

NEXT (CONVERT track): (1) the **SD SOUND LIST EDIT engine** behind the cursors
(0x4857B264 / 0x4857B2CC / 0x4857C28E / 0x4857C388 / 0x4857C3C3 / 0x4857C588 /
0x4857C679) -- still untouched, and it is the directory the converted cursors
index; (2) the rest of the InitializeBlock34 block, 0x485733BC..0x485736B7;
(3) **the container SYNTHESIS experiment** now that the writer contract is
written down -- build a minimal N=1 "TCMP" block offline in Python, run it past
the three verifiers by hand (signature / checksum / streams), and see whether a
synthetic container could stand in for the built-in style source that
StyleResourceWindowProbe never finds. That one, if it works, IS the blog post.
Live task (effect enable bits 4/10/13/14) still queued from tick b.

## AUTONOMOUS-STATUS tick — 2026-07-20, CONVERT track: TCMP CONTAINER SYNTHESIS

The experiment the last tick set up ran, offline, no MAME, no build.

DONE: `kn7000_disassembly/tools/tcmp_build.py` (commit 1e891a8) builds a
"TCMP" style container from the documented recipe and re-implements the
firmware's verifiers in Python, transcribed from the converted assembly:
MemStyleAreaSignatureVerify 0x48435749, MemStyleAreaChecksumVerify 0x484356BD
(+ SumU16BE), MemStyleAreaStreamsVerify 0x4843579E (+ MemStyleVarBarCount,
RhySysexLen, RhyEventLenByStatus), MemStyleAreaValidate 0x4843B1B5,
MemStyleAreaValidateOrInit 0x4843B1F6.

- ORACLE PASSES: all five return +1 on the real FactoryMemStyleContainer
  0x48035D08 (table ROM seg 2, N=3), the checksum reproducing the stored
  0xCC00 over 0x70..0x3670. That is what makes the port trustworthy.
- SYNTHETIC PASSES the same five. Its 0x70 header is byte-identical to the
  factory's except the checksum and the allocator top; the 60 variation
  records agree 60/60 on the pair bit rec[3]&0x10 and on rec[4..0x0B].
- Seven negative controls (corrupt signature, flipped record byte, wrong
  stream[0] index, removed 0xF4 marker, one byte of tail slack, changed
  meter field) all get rejected — the verifiers are not vacuous.
- Byproduct: the style record's two u16 fields are at +0x70, not +0x68;
  kn7000_manual.sym corrected in place. `make verify` still 100%.

★★ VERDICT ON THE ACTUAL QUESTION — NEGATIVE, and it is a clean negative.
**A synthetic TCMP container cannot stand in for the built-in style source
and cannot fix "8 Beat 1".** The built-in path does not consume a TCMP
container at all. StyleBuiltinNameTableInit 0x484332F9 requires a "Technics
Rhythms" NAME RESOURCE — 16-byte ASCII signature plus a u24BE directory at
+0x18 (count block, 0xDD = 221) / +0x1B (u16 name index table) / +0x1E
(3-byte offset sub-table) / +0x21 (secondary sub-table) / +0x24 (fallback
string, literally "  8 Beat 1    " in the program-ROM stub 0x48729988). A
TCMP container carries a checksum descriptor and a bump allocator at those
offsets and dies at the first strncmp; MemStyleAreaSignatureVerify rejects a
name resource just as fast. Different formats for different things — pattern
data with an event-stream heap vs a name/offset directory spanning ~4 MB of
undumped flash — and nothing in the image converts between them. This
re-derives statically the fix that already shipped (synthetic "Technics
Rhythms" resource at 0x54E00000, 52 real names, 168 awaiting Phase C).

NO BLOG POST. The previous tick set the bar explicitly — "the recipe, not
the dish" — and this pass produced a recipe plus a ruled-out shortcut, not a
fixed bug. Notes only: kn7000_disassembly/notes/tcmp-container-synthesis.md
and a new closing section in notes/sequenced-playback-and-style-data-
rootcause.md.

STANDING LESSON, twelfth pass: a format that validates is not a format that
is WANTED. Both readers were converted and both were correct; the error the
experiment was designed to catch was in the assumption connecting them, and
the only way to catch it was to read the consumer's first strncmp rather than
the producer's struct. Build the oracle before trusting the port: the
factory container passing all five verifiers is the only reason the
synthetic's pass means anything.

NEXT (CONVERT track), unchanged from the last tick minus item 3: (1) the SD
SOUND LIST EDIT engine (0x4857B264 / 0x4857B2CC / 0x4857C28E / 0x4857C388 /
0x4857C3C3 / 0x4857C588 / 0x4857C679); (2) the rest of InitializeBlock34,
0x485733BC..0x485736B7. Live task (effect enable bits 4/10/13/14) still
queued from tick b.

---

## TICK 24 — KN6000/KN6500 CONTROL PANELS (side quest, 2026-07-20)

DONE. Both models now have a correct, dedicated panel device; the quest moved
to side-quests/fully_solved/. Code: 74ff1f6. Notes: notes/kn6000-panel-matrix.md.

Felipe's report was the whole diagnosis: "presses are accepted but the mapping
is all wrong, yet the TEMPO/PROGRAM wheel works PERFECTLY". Both halves of that
sentence are load-bearing, and together they say exactly where the seam is. The
wheel working proves the CP wire protocol is shared across the MN10300 models;
the mapping being wrong proves the matrix contents are not. Measured:

  19 cells same event, 123 DIFFERENT, 8 KN6000-only, 9 KN7000-only
  -> 88% of populated button cells differ from the KN7000.

Split on that seam: kn_cpanel_base_device holds the protocol (frame parse,
handshake, ATN/RX dance, reply queue, scan, all three analog controllers);
kn7000_cpanel_device and kn6000_cpanel_device supply ONLY geometry + LED decode.
Driver holds the panel by base type; kn6000() device_remove()s and re-installs.

COMMONALITY MEASURED BEFORE DECIDING (Felipe asked for this explicitly): the
KN6000 and KN6500 descriptor tables are BYTE-IDENTICAL -- 30 segments, 164
button-bits, zero differing entries -- so one class serves both. No speculative
second derived class.

METHOD WORTH REUSING: two independent sources, cross-checked rather than
merged. Firmware descriptor arrays gave GEOMETRY (seg/bit, authoritative);
service-manual schematics gave NAMES. They agreed cell-for-cell on all 150
button-bits, and the manual CORRECTED a firmware-only guess (the 6 pads share
three columns as 1/4, 2/5, 3/6, not 1/2, 3/4, 5/6 -- positional ordering would
have got that wrong and it would have looked fine). The single strongest datum:
a wire-trace found exactly ONE unfitted switch position on the CPR board
(SEG9/SW3) and the ROM table has exactly ONE hole there (normSeg 0x12 bit 3).

STANDING LESSON, thirteenth pass: when a symptom has a working part and a
broken part, the boundary between them IS the refactor. The wheel was not a
curiosity to explain away -- it was the proof of which code is shared. Don't
design the class split from taste; read it off the failure.

LIVE-VERIFIED (the proof is a button doing what its silk says, not just
responding): POP -> RHYTHM screen header POP; PIANO -> SOUND-RIGHT 1 category
PIANO with real voice names; DISK -> DISK MENU; PROGRAM MENU -> PROGRAM MENUS.
KN6500 opens the same screens. KN7000 unregressed (PROGRAM MENUS / DISK MENU
LOAD / PIANO). Build clean; -validate kn7000/kn6000/kn6500/kn2400; published.

HONEST LIMITATION, not papered over: the LED decode is GENERIC. The hardware
LED coordinates are now fully traced (rows Q20-Q25 x SEG columns, 74LS138
decode is CM[2:0] = row+1 because Y0 is unconnected) and tabulated in the
notes -- but how that maps onto the protocol's [register][bit] is unconfirmed,
and there is no KN6000 layout to display an LED anyway. Bind it when artwork
exists, against the built-in "Panel SW & LED test" (service manual p.22 7.5).

NEXT: unchanged CONVERT track. Newly unblocked by this tick: a real KN6000
layout is now drawable -- the port tags and button names exist.

================================================================================
TICK 2026-07-20 -- KN6000 ARTWORK: the OTHER half of the wrong-mapping bug
================================================================================

Felipe, testing interactively: "the KN6000 STILL shows incorrect button mapping
when I click the panel. Can you create a .lay file based on the drawings found
on the service manuals?"

He was right, and the previous tick's verification had a hole in it. The matrix
device was correct -- but kn6000() inherits kn7000(), which does
set_default_layout(layout_kn7000), and there was no KN6000 layout to override
it. So the KN6000 was DRAWN as a KN7000: every clickable element at a KN7000
position, with a KN7000 legend, bound to a KN7000 cell. Clicking "PIANO" sent
the KN7000's PIANO cell.

STANDING LESSON, fourteenth pass: the previous verification pressed PORTS.
Pressing a port bypasses the artwork entirely -- it tests the matrix and nothing
else. For a panel bug the test must go through the thing the user actually
touches. A green test that skips the broken layer is worse than no test, because
it buys false confidence. Drive the user's path, not the convenient one.

DONE:
- tools/lay_kit.py -- the layout vocabulary (palette, E/TXTS registries,
  elem/two/label/P/L/panel_bg/pair_h/wrap2) extracted from gen_lay.py so a
  second model can be drawn without forking it. Behaviour-preserving: kn7000.lay
  regenerates BYTE-IDENTICAL (checked before/after).
- tools/gen_kn6000_lay.py -> src/mame/layout/kn6000.lay. Geometry + silkscreen
  from the SX-KN6000 service manual pp.5-6 (the owner's-manual "Controls and
  functions" two-page top view of the whole panel). Flattened the same way the
  KN7000 layout is: screen_block (LCD + flanking soft keys + the two 4x4
  category grids + MUTE row + PAGE/HOLD/EXIT) and three lower blocks.
- kn7000.cpp kn6000(): #include "kn6000.lh" + set_default_layout(layout_kn6000);
  build.sh symlinks the new .lay (MAME globs src/mame/layout/*.lay).

THE MANUAL CONFIRMED THE MATRIX A THIRD TIME. Read row-major, the 16 RHYTHM
GROUP legends land exactly on the 6/6/4 split over CPL_SEG0/1/2 bits 2-7 and the
16 SOUND GROUP legends on CPR_SEG0/1/2 bits 0-5 -- firmware descriptors, the
schematic switch inventory and now the panel drawing all agree.

COVERAGE IS ASSERTED, NOT ASSUMED: the generator cross-checks the layout's
bindings against kn6000_cpanel.cpp's INPUT_PORTS and prints
"COVERAGE: 150/150 named matrix cells placed", listing any MISSING or EXTRA
cell. A driver rename or a new button can no longer silently desync the artwork.
Each placement also carries its silk name parsed live from the driver, so the
comment cannot drift from the binding.

LIVE-VERIFIED, driven from the .lay's OWN elements (tag+mask read out of the
layout, so each press is equivalent to clicking that drawn button):
POP -> RHYTHM/POP; BALLROOM & SHOW TIME -> RHYTHM/BALLROOM & SHOW; MEMORY LOAD
-> RHYTHM/MEMORY; PIANO -> SOUND-RIGHT 1/PIANO; DRUM KITS -> DRUM KITS;
SOUND EXPLORER -> SOUND EXPLORER; DISK -> DISK MENU; PROGRAM MENU -> PROGRAM
MENUS; DEMO -> DEMONSTRATION; SEQUENCER EASY REC -> EASY RECORD; PANEL MEMORY 5
-> PMEM home (a recall, correct). KN6500 loads the same layout, PIANO/POP open
the right screens. KN7000 keeps its own layout, unregressed. Build clean,
-validate passes for kn7000/kn6000/kn6500, binary published.
Test harness: tools/kn6000_layout_clicktest.lua (KN6000_CLICKTEST env).

HONEST LIMITATION, again not papered over: LEDs are DRAWN where the manual shows
them but carry NO output name, so they stay dark. The KN6000 [register][bit]
decode is still unconfirmed and a guessed binding would be a false claim dressed
as artwork. Also decorative/absent on purpose: pitch-bend & modulation wheels,
the trackball ball (its RESET/MODE switches ARE bound), the CONTRAST trimmer
(analog, not a matrix cell), the POWER switch, the keyboard bed.
Not evidence either way: state-toggle buttons (SPLIT POINT, TECHNI-CHORD, SOUND
DSP, BANK VIEW, MUSIC STYLIST) change no screen -- they need the LED work.

NEXT: unchanged CONVERT track. Newly unblocked here: the KN6000 LED binding now
has somewhere to land -- run the built-in Panel SW & LED test against this
artwork and bind the dots.

================================================================================
TICK 2026-07-20 -- TONE GENERATOR: split out, and the chips ARE the same
================================================================================

Felipe asked directly: "do the KN6000/KN6500 use the same tone generator? If
so, can it be shared -- maybe split it out of the KN7000 into a device the
other models can use too?" Then, correcting the framing: "even though these
chips have different model numbering, they may be similar, so perhaps they
could inherit from a common parent class."

He was right, and the first framing of this task was wrong. The brief leaned
on the part numbers -- KN7000 = 2x C1BB00000709, KN6000/KN6500 = 1x
D82398GD001 -- and concluded "different chip, little to share". Part numbers
are not evidence of architecture. The firmware is.

STANDING LESSON, fifteenth pass: two parts with different numbers can still
be one design, and two firmwares from one source tree will tell you so. Test
the SOFTWARE that drives the hardware, not the label on the package. This is
the same shape as the panel finding (protocol shared, matrix differed) -- and
we should have expected it, because it is the same shared codebase.

THE DECISIVE DATUM: the KN6000's tone-generator write primitive at 0x4849465B
is BYTE-IDENTICAL to the KN7000's TG-A leg at 0x4C036F7C --
81 f8c510 fc8700000598 fae0ffff fc8302000598. The KN7000's writer is that
same routine with a chip-select branch (cmp 0x40,d0) wrapped around it. The
two-chip KN7000 path is literally a parameterised generalisation of the
one-chip KN6000 path.

Also shared, all cited in notes/kn6000-tonegen-spec.md: the packed command
word (slot<<20)|(class<<16)|data with an IDENTICAL bitfield split; dual
asl-20/asl-18 addressing modes; 16 halfword regs per voice as four 4-reg
banks of [rate|level] EG pairs; the literals 0xFF80/0xFF00, 0xA280/0xA200,
0x7F80/0x7F00, 0xC000, 0x87FF; the 18-bit pitch built by the same
and-0x00018000 / or-0x4000 idiom with bit 16 in class bit 0; plane 0x20
(send matrix) and 0x28 (global bank) at the SAME numbers; 0xB4-stride voice
record, 0x130-stride part block, 34-part model.
FALSIFIED along the way: the "group field shifted one bit" hypothesis. The
split is identical; only the plane NUMBERING is remapped.

DONE:
- f940b22 kn7000_tonegen.{cpp,h} -- the 541-line inline device moved out of
  kn7000.cpp, mirroring the cpanel split. Proven PURE CODE MOTION textually
  (only the 5 method signatures change shape; no logic/constant/comment
  touched) and behaviourally (oracle bit-identical).
- 75d091c kn_tonegen.{cpp,h} -- shared base. Split drawn where the evidence
  draws it: base = the MECHANISM proven identical on both chips (envelope
  state machine + rate->seconds law, per-voice state, gate-follow coupling,
  effect-send/return gains, wave pack, stream/render; voice count is a ctor
  parameter). Derived = the NUMBERING (tg_write decode, two-chip mapping).
- a04c7f9 notes/kn6000-tonegen-spec.md -- comparison table with a firmware
  address per row, the four INCONCLUSIVE points, what a kn6000_tonegen needs,
  and the blockers.

NO kn6000_tonegen_device SHIPPED, on purpose: its plane map has only three
points pinned, and its audio is blocked on the undumped IC13/IC14 table ROMs
and the un-reversed note->pitch routine regardless. It is now a small,
obvious addition -- a second tg_write() decode over the base -- rather than
a speculative device that cannot be exercised.

REGRESSION IS THE POINT, and it held at BOTH steps:
  reverb/keybed oracle  c3b67ea711ce3c00f8ae2af1e07651cb (documented baseline,
    reproduced on the pre-split build FIRST, then after the split, then again
    after the base-class factoring)
  demo-button capture   53b02f539c76ccba78a8058df033390d (A/B'd against a
    REBUILT PRE-SPLIT BINARY -- a real before/after, not a re-run)
Build clean; -validate kn7000/kn6000/kn6500/kn2400; published. KN6000 still
boots to its play screen with its own panel (screenshot-verified).

TOOLING GOTCHAS FOUND (cost time, recorded so the next tick skips them):
- tools/audio_playnote_wav.lua is STALE: it presses a ":KEYS0" field by the
  name "Key C4", which no longer matches, so it captures SILENCE. Use the
  money.lua style instead (press :KEYS1 by MASK 0x0100) -- masks survive
  renames, names do not.
- A DEMO press via :cpanel:CPL_SEG6 0x40 does NOT start the demonstration
  (verified silent on the PRE-SPLIT binary too, so it is a recipe problem,
  not a regression -- and that A/B is exactly why the pre-split rebuild was
  worth doing). The working DEMO recipe is still unknown; find it before
  citing "demo plays" as a check again.
- kn6000/kn6500 ROMs are MISSING from the build tree (roms/ has only kn2400
  and kn7000), so publish-binary.sh warns and skips them; the published
  folder still has them from earlier runs. Harmless today, but a clean
  rebuild of the tree would lose them -- restage before relying on it.

NEXT: the architecture question is settled, so the KN6000 TG gap is now
exactly two items -- (1) a per-plane live sweep on the KN6000 (it already
boots and its voice engine runs on key presses; reuse
tools/stage2_tg_diagnostic.lua) to turn the spec's INCONCLUSIVE rows into a
complete plane map, and (2) static RE of its note->pitch routine. Neither is
blocked on anything. Otherwise the CONVERT track is unchanged.

## Tick 2026-07-20 — KN5000 joins the family binary (side quest)

DONE: the unmerged KN5000 work is now IN this repo. There is only ONE MAME repo in
the VM (kn5000_project/mame is the same directory; mame-sony-video and seven
.claude/worktrees are worktrees of it). Its six active KN5000 branches were
inventoried against a freshly-fetched upstream; `kn5000_pr6` (18) was rebased onto
kn7000-base, six confirmed fixes cherry-picked from `kn5000_research_tonegen`, and
`kn5000_research_datawheel` re-implemented against the device-owned ports. Result:
13 overlay files under src/ (tmp94c241{,_serial}, hdae5000, kn5000{,_cpanel,_dsp,
_tonegen}, kn5000.lay) + notes/upstream-patches/kn5000-01..25-*.patch, indexed in
that README with a PR 6-9 split. The two are PROVEN identical: `git am` of the 25
patches on a pristine kn7000-base yields byte-identical files (cmp, 13/13).

BUILD PUZZLE SOLVED: the old "only driver_kn5000 undefined" link failure was NOT a
drivlist filter bug -- upstream mame.lst already has an @source:matsushita/kn5000.cpp
anchor, so the filtered list emits driver_kn5000 while SOURCES never compiled it.
Fix = name kn5000.cpp AND its device .cpp files in SOURCES (done in build.sh, with
the reason written next to it). kn5000 now rides in the SAME kn7000 binary.

VERIFIED LIVE: -validate passes for all seven (kn1500/2400/2600/5000/6000/6500/7000
-- no regression from the shared tmp94c241/hdae5000 overlays), and kn5000 boots to
its main play screen (PMEM: 1-, USA March 2/4, ♩=120). "Sound Name Error" x3 is
expected: waveform ROMs IC304-306 undumped. publish-binary.sh ships roms/kn5000 via
its own block (per-IC filenames, not the even/odd *.rom pair MODELS assumes), so
`./run.sh kn5000 -window` works from the published folder.

GOTCHA for whoever rebases these branches next: they are 1429 commits behind, and
their "major driver rework" commit is HALF-merged (PR #15143 took the cpanel HLE but
NOT the SubCPU payload / NVRAM defaults / keybed HLE). Resolve conflicts TOWARDS
upstream. Two breakages only surface at compile time: duplicate machine_start/
machine_reset decls, and tmp94c241_device::m_serial went PRIVATE after the branches
were cut (use rxd0()/txd0()).

OPEN: the data wheel is wired and reachable (:cpanel:ENCODER) but NOT behaviourally
confirmed -- a full Lua sweep on the play screen changes nothing, consistent with it
being a menu-only control. Confirm it from a parameter screen before claiming it.
Full write-up: KN7000/side-quests/findings/kn5000_driver_findings.md

================================================================================
TICK 2026-07-20 -- ROM PRESERVATION: authoritative private repo + one regeneration path
================================================================================

PROBLEM (infrastructure, not emulation): publish-binary.sh copied ROMs ONE WAY out of
the DISPOSABLE build tree (`cp -u`, never deleting), and a model whose ROMs had gone
missing produced only a quiet mid-run warning before silently shipping a STALE set.
The build tree had emptied out, so for most ROMs the PUBLISHED folder had become the
only surviving copy -- one `rm -rf` from unrecoverable, with the recipes scattered
across half a dozen notes.

SHIPPED:

1. NEW PRIVATE REPO /home/fsanches/compartilhado/technics_roms (commit e86b23e) is now
   the AUTHORITATIVE home of every ROM artifact. Build tree + kn7000-emulator/ are
   derived copies again.
     roms/{kn7000,kn6000,kn6500,kn2400,kn5000}  the driver ROM sets (57 files, 226 MB)
     sources/<model>/   the .SLD update-disk payloads every ROM regenerates FROM
     media/             Felipe's own SD-card dump (existed only in kn7000-emulator/)
     MANIFEST.tsv       size+md5+sha1+crc32, cross-referenced against the CRC/SHA1 the
                        MAME driver declares -- all 16 declared hashes MATCH
     verify.sh          checks the tree against the manifest
   PRIVACY GUARD (copyrighted firmware + personal media): no remote configured, plus a
   pre-push hook that refuses every push. Versioned at hooks/pre-push with
   install-hooks.sh, because git does not version .git/hooks and a fresh clone would
   otherwise start UNPROTECTED. Both paths tested (refuses; TECHNICS_ROMS_ALLOW_PUSH=1
   overrides). Plain git, NOT LFS, and the README justifies it: an LFS pointer without
   its server is data loss, a plain git object is self-contained, and ROMs are
   write-once so blob churn is a non-issue.

2. ★ EVERY SHIPPED ROM IS REGENERABLE -- verified by rebuilding all 14 driver ROMs from
   the preserved sources and comparing md5. ALL 14 MATCHED BIT-FOR-BIT. New
   tools/make-roms.sh {check,generate,restore,list} + notes/rom-provenance.md.
     - kn7000 program+table: self-validating against the disks' own SMCK*.INF oracle
       (program total 0x18CE8702, table 0x13DCD1A3, all 16 blocks match).
     - kn6000/kn6500/kn2400: IK1+IK2 / IKV1+IKV2 / LKG1+LKG2. NO committed script did
       this before -- ad hoc, outputs only. Gap now closed.
     - rhythms_synthetic: gen_technics_rhythms.py reproduces it exactly.
     - waves_synthetic: extract_kn5000_waves.py + make_wave_pack.py reproduce it
       exactly. CORRECTION -- this was assumed non-regenerable; it is NOT. Its real
       dependency is the genuine KN5000 wave dumps (now in roms/kn5000/).

3. PUBLISH IS NOW SELF-HEALING + LOUD (45c04a4). Step 0 tops the build tree up from
   technics_roms; missing ROMs are a HARD ERROR with a prominent end-of-run summary
   (override PUBLISH_ALLOW_MISSING_ROMS=1). Verified by deleting kn6000+kn6500 from the
   build tree: publish restored all 8 files from the repo and shipped correctly.

WHAT COULD NOT BE RECONSTRUCTED (stated plainly, not invented): the .exe -> .SLD step.
The distributed archives are DOS self-extracting installers; the SLD payload is NOT
stored verbatim inside them (magic absent, no matching byte runs -- only the filename
strings appear, as directory entries). Recovering a .SLD means running the installer
under DOSBox and reading its floppy image. Hence the extracted .SLD files ARE the
practical primary source, and are now committed in technics_roms/sources/.

ERRATUM FIXED: notes/mame-pr-rom-manifest.md claimed the KN7000 ROMs were even/odd of
"JK1.SLD (program) and JK2.SLD (table)". Wrong -- JK2 is the PROGRAM image's second
half; the table is JKT1+JKT2 (kn7-14). Corrected, with the retired kn6xxx_table_* rows
flagged as never having been a dump of IC13/IC14.

VERIFICATION: ./build.sh exit 0; publish exit 0 with ZERO missing-ROM warnings;
published ROM md5s UNCHANGED vs the pre-change baseline (provenance relocated, ROMs
untouched). kn7000 (home PMEM screen), kn6000 (play screen w/ text), kn2400 (play
screen; text rendering still WIP as documented) all boot -- snapshot-verified,
visible video.

================================================================================
TICK 2026-07-20 (late): KN5000 TEMPO/PROGRAM DATA WHEEL -- verdict + widget shipped,
                        screen-visible change HONESTLY NOT achieved
================================================================================

TASK: "does the KN5000 wheel work like the KN6000/KN7000 one? if so reuse the code."

VERDICT: SAME PURPOSE, DIFFERENT PROTOCOL -- and the KN5000's single wheel is the
functional MERGE of the KN7000's TWO rotaries (KN7000: TEMPO/PROGRAM on wire 0x17 as a
SIGNED STEP the firmware ACCUMULATES, plus a separate DATA dial on wire 0x10; KN5000:
ONE wheel labelled TEMPO/PROGRAM, reported as segment 0x0B DIRECTION BIT-FLAGS,
bit7=CW bit6=CCW, carrying NO magnitude). Do not wire a second KN5000 rotary.

KEY FIRMWARE CORRECTION (supersedes kn5000-docs/data-wheel-investigation.md):
DRAM[0x8E55]/[0x8E6A] are BOOT-ONLY. 0x8e55 appears at exactly ONE site in the whole
v10 maincpu disassembly (the CPanel_ButtonPollLoop settling query). The UI is fed by a
DIFFERENT, SIGNED path: SwbtWr event type 0xA9 + payload 0x21 at DRAM[0xC07D], with the
step at DRAM[0xC07E] run through a +/-7 ACCELERATION TABLE at ROM 0xEA98E2 (dumped;
index 16 = zero, and the curve INVERTS SIGN). Nothing in the disassembly converts the
0x8E55 bit-flags into that signed count -- the producer is in the NON-disassembled NAKA
region (~0xF9xxxx-0xFDxxxx). This FALSIFIES hypotheses H2/H3 in that doc:
Encoder_PrepareCallback writes event type 0xAA, not 0xA9.
Also corrected: the neutral 0x00 idle byte IS required, but because
CPanel_RX_ButtonPacket does `ex (xhl),a` + `xor` (changed-bits mask) -- repeating a
direction byte yields an EMPTY mask and is silently dropped. Not because of 0x8E6A.

MEASURED (not assumed), DISPLAY=:0 -window, write-tap on DRAM[0x8E55]:
 * STEADY STATE: navigate MENU:SOUND -> LEFT 4 (MASTER TUNING, numeric page), sweep
   ~9.5s => driver emitted 112 encoder packets, ZERO reached DRAM[0x8E55]; before/after
   snapshots byte-identical. NOT "menu-only" and NOT a bad packet format.
 * BOOT WINDOW (positive control): same code path lands PERFECTLY --
   value=80 / 00 / 80 / 00 ... i.e. transport + format + encoding are PROVEN CORRECT.
 => The wheel is a FIRMWARE-SIDE DEAD END in steady state, not a wiring mistake.
 Supporting: the MENU:SOUND vocal-reverb page shows a highlighted VOLUME field AND
 LIGHTS THE TEMPO/PROGRAM LED (firmware really does arm the dial there), and the panel
 BUTTONS on those screens work -- so the target screens were right.

SHIPPED anyway (correct, documented, not claimed to "work"):
 * REUSED VERBATIM: tools/slider_lib.lua add_rotary_knob + install_slider_callbacks +
   poll_rotary_wheels, now in src/mame/layout/kn5000.lay, replacing the old PASSIVE
   (non-draggable) finger script. Layouts can't include files, so it's inlined;
   tools/refresh_kn5000_lay_script.py re-inlines it (mirrors gen_lay.py / gen_kn6000_lay.py).
 * REUSED AS A PATTERN, re-encoded: kn5000_cpanel is a standalone device_t (TLCS-900,
   different protocol), NOT a kn_cpanel_base_device subclass -- sharing a base would be
   wrong. Adopted the KN7000 pipeline: PORT_ADJUSTER instead of IPT_DIAL (infinite
   encoder), RAW adjuster field read (live().value, NOT the interpolated port read --
   the KN7000's hard-won lesson), wrap-aware delta (>50 -> -=101), one-detent-per-scan
   slew, m_encoder_synced so startup emits no phantom detent. Driver trace verified:
   clean `delta=1` per-detent stream + neutral idle.

VERIFICATION: ./build.sh 0; -validate CLEAN for kn5000/kn7000/kn6000/kn6500/kn2400/
kn2600; publish-binary 0; kn7000 + kn6000 boot with ZERO layout-script errors (their
wheels share slider_lib.lua, which was NOT modified).

NEXT LEVER for the wheel: the acceleration table pins the exact numeric domain the
missing producer must emit (small signed counts, +/-1 typical) -- a watchpoint on
DRAM[0xC07E] constrained to that domain is far tighter than the old "some value 0x21".

Patch series: kn5000-25-program-data-wheel.patch REGENERATED (not duplicated), still
LAST, and README.md now says explicitly to HOLD IT BACK until the firmware path is
resolved. Findings: KN7000/side-quests/findings/kn5000_data_wheel_findings.md

--------------------------------------------------------------------------------
TICK 2026-07-20 (later): KN5000 wheel -- SECOND PASS. Producer FOUND; the TEMPO
                         acceptance test is FALSIFIED at firmware level.
--------------------------------------------------------------------------------
Felipe: wheel NOW ROTATES under real mouse drag (layout/Lua reuse CONFIRMED by
human input -- that caveat is cleared) but does not change TEMPO.

PRODUCER FOUND (was "unlocated"): it is NOT hand-written code -- that is why
grepping for a routine writing event type 0xA9 found nothing. It is a ROM
DESCRIPTOR, 0xED9B86 = {A9,21,00,FF}, entry 0x19 of the table at 0xED9C1E,
copied into the event by the GENERIC emitter FileIO_ProcessMaskAndShift
(0xFC580A) which stages {A9,21,delta,mask} at DRAM 0x8E7C. The byte pair A9 21
occurs EXACTLY ONCE in the 2 MB image. Full chain: CP serial -> RX_MultiBytePacket
(0xFC4A40) -> ring 0x200AD -> scan table 0x8E94 -> Encoder_ValueScanAndSync
(0xFC5761) -> descriptor -> emitter -> queue 0xC039 -> dispatcher 0xFDB328
(writes 0xC080=A9, 0xC07D=21, 0xC07E=signed delta) -> CtrlPanel_HandleSerialPort
-> accel table 0xEA98E2 -> PostEvent 0x1C0001F -> GroupBox_HandleCursorNav.

WHICH MESSAGE: only CPanel_RX_MultiBytePacket (types 6/7) can produce record id
0x19, because only there is the record id a SYNTHESISED running index
W = (header&0xC0)|(seed&0x1F). Button packets put the RAW HEADER there and header
0x19 decodes as packet type 3 (Sync) -- structurally impossible. Type 2 headers
are restricted to 0x1x/0x5x/0x9x/0xDx. This INDEPENDENTLY re-confirms the earlier
negative: segment 0x0B maps to descriptor 0x0B = subcode 0x0E, NOT 0x21.
Tried emitting `30 19 <delta>`: signature still did NOT fire. OPEN CATCH: for W
with bit4 set (0x19 has it) the handler REPLACES the data byte with
ENCODER_HANDLER_TABLE[1] = 0xFC6DEE = `ld HL,1; ret` = CONSTANT 1, so as
disassembled that route cannot carry a variable signed delta. Either the panel
uses a different seed/panel-bit combo or another route reaches the descriptor.
That single framing detail is the whole remaining unknown.

*** THE TEMPO ACCEPTANCE TEST IS WRONG (evidence, not excuse) ***
 1. GroupBox_HandleCursorNav (ui_control_panel.s:3847) keeps ONLY THE SIGN of the
    accelerated value and re-dispatches whichever dial triple the FOCUSED SCREEN
    registered (0x3EF52/56.., written by SetDialUpEvent 0xF9A579 /
    SetDialDownEvent 0xF9A58A, ~100 callers). The +/-7 curve collapses to 1 bit.
    The wheel is a GENERIC FOCUSED-WIDGET control, not a tempo control.
 2. NO ADDITIVE WRITER OF THE BPM EXISTS. BPM = 9-bit field at DRAM 0xFC62
    (default 120, clamp 40..300), reload = 80,000,000/(BPM*64) via
    SeqTimer_UpdateTempoReg (0xFCA318). Zero add/sub/inc/dec hits on 0xFC62 or its
    mirror 0xBD3A across the whole 2 MB. Writers are ONLY: song/style load
    (0xF20433), the clamp, and the inter-CPU/MIDI set (0xFCB42C). TAP TEMPO is a
    button bit that never reaches the BPM word. Home-screen widget AcTempoBoxProc
    (0xF9D256) handles 0x1C0001C/0C/0B/02/01 -- NOT the dial event 0x1C0001F.
 => "turn wheel -> play-screen tempo digits change" is not a behaviour this
    firmware has. The honest acceptance test is a FOCUSED PARAMETER FIELD on a
    screen that called SetDialUpEvent/SetDialDownEvent.
 CAVEAT NOT PAPERED OVER: PsParaBoxProc's parameter-change logic was not fully
 traced, so a dedicated tempo EDIT screen registering a dial triple that reaches
 0xFC62 through the parameter system is not ruled out.

DRIVER: all research scaffolding (ENCMODE port, send_raw_pair/send_multibyte/
send_encoder_packet, osd_printf traces) REVERTED -- shipped tree is the clean
committed version. build 0; -validate clean kn5000/kn7000/kn6000; kn5000 boots,
zero layout-script errors. Patch kn5000-25 unchanged and still held back.
Findings: KN7000/side-quests/findings/kn5000_data_wheel_findings.md (ADDENDUM).

================================================================================
2026-07-20 tick -- ★ KN5000 "Sound Name Error" SOLVED (kn5000-29): SNS checksum tap was the cause
================================================================================
THIRD ORACLE settled it: built CURRENT upstream mainline MAME (upstream/master
ecf0add) kn5000 -- it WORKS (real names) despite being a minimal skeleton (raw
latch, stub HLE, no ComIF/DSP2, NO SNS tap). So the overlay was BREAKING boot.
ROOT CAUSE: the overlay's SNS payload-checksum WRITE TAP on MainCPU DRAM[0xFFD4].
It intercepted Boot_DisplayScreen's zero-clear and substituted a checksum computed
too early (from DRAM 0xF180/0xF980 before they hold the expected values). The
firmware reads DRAM[0xFFD4]==0 as "no stored checksum -> FRESH decompress+transfer
of the SubCPU payload"; the tap's non-zero value sent it down "already valid ->
SKIP transfer", so the SubCPU ran with no/stale firmware, never answered the 0x2B
sound-name query, and its scheduler idled + leaked (the XSSP stack leak). Every
prior symptom (leak, missing INTRX1 heartbeat, reply stopping) was downstream of
the SubCPU never getting its firmware. FIX kn5000-29 (committed b1cf7db): REMOVE
the tap. ISOLATION: with ONLY the tap removed (overlay tmp94c241/latch/HLE
otherwise unchanged, kn5000-28 still applied) -> ALL THREE NAMES (RIGHT1 Piano /
RIGHT2 Bigband Brass / LEFT Modern E.P.1, rhythm 16 Beat 1) on both fresh + persisted
NVRAM; XSSP BOUNDED ~0x40680 across 40s (Lua poll of :subcpu XSSP; broken state
descended to ~0x2D38A). The upstream-tmp94c241/raw-latch/HLE-stub experiments are
NOT needed. -validate clean; KN7000 home unaffected (Concert Grand/Bigband Brass/
Modern E.P.); payload path untouched (e6b4cf7 preserved). kn5000-28 retained
(correct 02-17 alignment, not the cure). Three throwaway worktrees removed; all
instrumentation reverted; clean rebuild + publish-binary shipped. Blog part written.
Full write-up: KN7000/side-quests/findings/kn5000_driver_findings.md (2026-07-20 SOLVED).

================================================================================
2026-07-20 tick -- KN5000 ORACLE BISECT: premise corrected, regression fixed (kn5000-28), full cure still open
================================================================================
Ran the oracle-timeline bisect. BIG CORRECTION: kn5000_aided_by_claude *tip*
(2da2648) is ALSO broken -- built it as an oracle, shows the identical "Sound
Name Error" (receive-HDMA INTTC0 freezes ~t=7.2, XSSP leaks). So kn5000-26/27
"restore parity with aided" matched a BROKEN reference. The TRUE working state is
the 2026-02-17 commit f8cd34a8: built as the real oracle it shows REAL NAMES
(Piano / Bigband Brass / Modern E.P.1), XSSP bounded, scheduler alive, reply DMA
13x, SC1 ComIF INTTX1+INTRX1 heartbeat steady (screenshot-verified).
REGRESSION (commit 3ea9904): removed the GUARDED INT0 level-detect re-assertion.
FIX kn5000-28 (committed c11209d): restore it -- re-assert INTE0AD|=0x08 only when
no HDMA channel steals INT0 (m_dma_vector[ch]!=0x0a); + drop the Port Z MSTAT
read-back kn5000-27 added (oracle reads back COM_SELECT|(SSTAT<<2) only). KN5000-
only; -validate clean; KN7000 home unaffected (verified: Concert Grand/Bigband
Brass/Modern E.P.). NECESSARY BUT NOT SUFFICIENT -- receive still freezes n=480
@t~9.8. RULED OUT this pass (don't re-chase): timer rate (identical 168/0.5s in
healthy window), serial storm (ours fires FEWER), UART mode (SubCPU never writes
SCxMOD), Port H hack (present both), latch handshake (byte-identical), Port Z (0
effect). REMAINING CAUSE (the cure): SubCPU cooperative-scheduler PACING stall --
overlay bursts the ~480-block payload in ~8s where the oracle paces it over ~24s,
starving a scheduler task (INTT3 leak). Traces to the SubCPU peripheral work the
overlay DROPPED vs 2026-02-17: the SC1 Computer-Interface heartbeat that wakes a
task (census: oracle INTRX1 21x, overlay 0x), DSP2/MN19413 (device absent from
tree), audio-mixer window. NEXT = reinstate that SubCPU-side work / per-block
processing that paces the transfer (larger than a tmp94c241 hunk; touches wiring
near the cpanel-device boundary). Full write-up:
KN7000/side-quests/findings/kn5000_driver_findings.md (2026-07-20 oracle bisect).
Oracle worktree removed; all instrumentation reverted; clean rebuild shipped.

================================================================================
2026-07-20 tick -- KN5000 "Sound Name Error" ROOT-CAUSED (DSP2-wiring theory FALSIFIED)
================================================================================
Followed method (watchpoint, not assumption). Full write-up:
KN7000/side-quests/findings/kn5000_driver_findings.md (dated 2026-07-20 later).

CHAIN: payload transfer is CLEAN (SubCPU code 0x0F000-0x2DFFF byte-identical to
ref kn5000_subprogram_v142.rom; only the runtime-cleared 0x2E000-0x2FFFF buffer
differs) -> SubCPU boots, idles in `jr T,$` at 0x01FF1F (all work is IRQ-driven)
-> at t~11.3 a CPU store with a CORRUPT destination pointer overwrites the
SubCPU's own 0x60-0x7F command handler code at 0x035893 (0x035893: AF->00;
ref handler = `af 06 23 ld XHL,(XSP+6)`) with 8-byte linked-list nodes that
belong at ~0x1078 -> the play-screen sound-name query is delivered as a 0x60-0x7F
command, MICRODMA_CH0_HANDLER dispatches CMD_DISPATCH_TABLE[3]=0x035893 via
`call T,XWA` into the now-zeroed code -> NOP-sled -> SubCPU derails -> never
answers name queries -> "Sound Name Error" on RIGHT1/RIGHT2/LEFT (screenshot).

RULED OUT (do not re-chase): (a) DSP2/mn19413/ComIF/serial wiring -- mn19413 is a
pure write-only sink, cannot change control flow; (b) audio HLE (kn5000_tonegen/
kn5000_dsp1) -- stubbing 0x100000-0x11FFFF & 0x130000-0x13FFFF to noprw(0) STILL
derails; (c) payload corruption; (d) undumped boot ROM (0 exec there in-window);
(e) the micro-DMA engine -- instrumented tlcs900_process_hdma/software_dma: they
fire ~65K x for the legit block-8 load (t~5) and NEVER after t=7.

OPEN: the corrupt-pointer store (0x035888 vs ~0x1078). Next = log PC+regs in the
shared tlcs900 WRMEM byte path when SubCPU writes 0x035888-98, disasm the store,
walk the base register back to the wrong value; diff vs kn5000_aided_by_claude
(which did NOT derail). Pragmatic "make it not derail" stop-gap possible.

DRIVER: all my instrumentation REVERTED -- shipped tree is the clean committed
version (kn5000.cpp + tmp94c241.cpp git-clean). No code fix committed (would be
speculative). Did NOT touch cpanel/layout/slider_lib/kn5000-25 (wheel agent).

--- 2026-07-20 REFINEMENT: the corruption is a STACK LEAK (Timer-3 scheduler tick) ---
Continued from the tick above. The "corrupt store to 0x035888" is actually STACK
PUSHES: the SubCPU system stack pointer XSSP LEAKS DOWNWARD ~8.6 KB/s until it sits
in the code region. Polled XSSP: 0x040688(t6) -> 0x03FF2A(t7.6, enters code) ->
0x036580(t11) -> 0x033924(t12); its top crosses 0x035893 at ~t11.3 (== the AF->00).
Instrumented IRQ-take/RETI: INTT1(Timer1,vec54)=32 takes/32 RETIs (balanced), but
INTT3(Timer3,vec5C)=22 takes / 0 RETIs -- its handler (0x01FDC8, the cooperative-
scheduler tick) does `jrl T,0x02070C` into the dispatcher, never RETI, leaking a
~28-byte context save each tick. CPU core is NOT at fault at instruction level:
int-entry pushes 6 (PC+SR), op_RETI pops 6; push/pop SR = 2; long push/pop = 4; the
tmp94c241 IRQ-mask loop is byte-identical to upstream tmp95c061. => scheduler
save/restore imbalance: a SubCPU task never gets cleanly restored, prime suspect a
task BLOCKED on an emulated-hw event that never resolves (top candidate: response
DMA ch2 / INTTC2 -- the SubCPU emits only 15 reply bytes then goes quiet). Stubbing
audio HLE to 0 did NOT stop the leak. NEXT: trace one INTT3 cycle, find which task
0x02070C/0x02011A fails to restore and what it waits on (verify DMA ch2 fires INTTC2
+ clears wait flag DRAM 0x10E8). Fixing the blocked task likely stops the leak AND
restores the name replies. All instrumentation reverted (overlay tmp94c241.cpp git-
clean; build-tree tlcs900.h/900tbl.hxx restored from ../mame). Full write-up in
KN7000/side-quests/findings/kn5000_driver_findings.md.

================================================================================
2026-07-20 tick -- KN5000 "Sound Name Error": leak DEEP-TRACED to a SubCPU
                   receive-DMA/scheduler DEADLOCK; 2 aided-parity fixes shipped
                   (necessary, NOT sufficient); root device hunk NOT isolated
================================================================================
Full write-up: KN7000/side-quests/findings/kn5000_driver_findings.md
(2026-07-20 "deep trace" section). Commits kn7000_mame 9fc71dd + af2c6af.

EXONERATED: tlcs900 CPU core is BYTE-IDENTICAL to kn5000_aided_by_claude
(diff of build-tree tlcs900.cpp/900tbl.hxx/tlcs900.h vs the aided branch = 0
lines). So the leak is entirely in the overlay tmp94c241.{cpp,h} / kn5000.cpp.

SHIPPED (kn5000-27, KN5000-only, -validate clean x5, KN7000 home = real names):
 (a) tmp94c241 check_irqs no longer RE-ASSERTS the INT0 level flag after taking
     the IRQ (aided deliberately removed it; ours had re-introduced it).
 (b) kn5000 MainCPU Port Z read restores the MSTAT read-back (m_mstat | ...).
 => Both are correct parity fixes but the XSSP leak trajectory is BYTE-IDENTICAL
    before/after and the screen still shows "Sound Name Error". Necessary, not
    sufficient.

MECHANISM (disassembled): SubCPU cooperative scheduler w/ software nesting
counter DRAM 0x10D2. XSSP is reclaimed ONLY by a task-switch/dispatch (ld XSP,
0x00040B1E at 0x01FF3F, gated on current-task 0x1046!=0; OR ld XSP,(task+4) at
0x01FF6F). The ONE path that does NOT reload XSP = entered-from-idle (0x1046==0)
with NO ready task -> 0x01FF18 idle 0x01FF1F. Real HW leaves that state within a
tick (a task becomes ready); OUR build enters it at ~t=7.5 and NEVER leaves ->
leak ~8.6KB/s -> corrupts handler 0x035893 (~t=11) -> derail -> error.

WHY no task ever becomes ready: the RECEIVE HDMA ch0 STALLS. MainCPU streams
64KB blocks (loop 0xEF3436, E1/E2/E3 framed) to latch 0x140000; SubCPU receives
via HDMA ch0 (DMAV0=0x0A/INT0, 4-byte packets -> 0x0010F0, INTTC0 on done). The
INT0 LINE toggles ~616K times (every MainCPU write) but HDMA ch0 completes only
~480 times -> INTTC0 bursts to t~7.85 then FREEZES -> no command packet
processed -> no task linked ready -> idle/leak. Self-reinforcing deadlock (ch0
re-arm needs a ready task needs INTTC0 needs ch0 armed). Reply path (HDMA ch2 /
Timer2 / busy-wait DRAM 0x10E8 / INTTC2) WORKS (2 blocks then done, not stuck).

RULED OUT: core; latch wrappers (identical to aided); handshake ports (identical
but the now-fixed MSTAT read-back); CN12 check-terminal (defaults Off); reply
DMA/INTTC2; audio HLE; serial-int wiring (disabling only SLOWED the leak).

NEXT: BUILD kn5000_aided_by_claude (accept 1429-behind) as an oracle for its
INTTC0/HDMA-ch0 timeline; and/or bisect the INT0-flag lifecycle during HDMA
(check_hdma/process_hdma "clear triggering flag" + hdma_targeted skip vs
execute_set_input level-detect on the acknowledge_w(0)->write() edge pair --
suspect a deferred synchronize() edge-collapse dropping the INT0 assert for HDMA
once the SubCPU only polls ch0 occasionally). All instrumentation reverted;
build-tree tlcs900.cpp restored from ../mame; overlay tree = only kn5000-27.

---
## Tick 2026-07-21 — KN5000 "scrambled control panel" root-caused (no fix landed)

Felipe: "the control panel is responding to button presses completely scrambled"
(+ spurious `<Db>` transpose on the home screen, nobody pressed transpose).

FINDING: NOT a mapping bug and NOT our regression. The SEG.bit->button table,
kn5000.lay inputtags, cpanel finder-array indexing, and the TMP94C241 synchronous
serial transport are ALL byte-identical to the pristine upstream oracle (efc8d90);
the port-move refactor is faithful (verified by diff). The scramble is an inherent,
timing-fragile CP-serial FRAMING corruption in the imported HLE: the cpanel sends
correct (header,state) bytes but the main CPU clocks in ~184 PHANTOM bytes
(traced 250 recv vs 66 sent). Phantom 0x00 = right-panel segment 0 = TRANSPOSE row
(= Felipe's phantom `<Db>`); an ODD phantom count inside a framed burst swaps
header<->state, so PIANO (seg2,0x01) reads as (seg1,0x02) = ORCHESTRAL PAD.
Bisected: already corrupt at the f1b605d import (predates inter-CPU/tempo/sound-name
work; our timing changes only altered the flavour, `<G>`->`<Db>`). Oracle can't
A/B the mapping live because efc8d90 KN5000 won't boot to a stable screen without
our sound-name cure.

TRIED + REVERTED (none fixed it): disable inter-CPU perfect_quantum/abort_timeslice
(broke boot); tight perfect_quantum(2us) during self-clock (no effect, 250kHz timer
already ~4us); idle cpanel TXD high at TX-complete (no effect; damaging phantoms are
in the CPU-transmit/INTA-handshake window). Full write-up:
../KN7000/side-quests/findings/kn5000_button_mapping_findings.md

NEXT: make the CP-serial framing robust -- re-align the main-CPU serial-RX byte
boundary at each cpanel INTA burst start (symmetric to the cpanel's own
m_rx_waiting_for_start gate), so exactly the intended bytes are counted per burst.
Protocol-timing work; verify against boot/sound-name/tempo (all "just landed").
Tree clean at HEAD; clean binary rebuilt + published.

---
## Tick 2026-07-21 — KN5000 "scrambled control panel" FIXED & SHIPPED (kn5000-30)

Felipe: "push on now!" — land the real fix for the scrambled panel + phantom `<Db>`.

ROOT CAUSE PINNED (behavioural oracle diff, both ends instrumented live): the SHARED
TMP94C241 synchronous-serial RECEIVER over-counts clock edges. `tmp94c241_serial_device::
sioclk()` latched an RX byte + fired INTRX on EVERY 8 rising edges regardless of clock
source. Synchronous serial is full-duplex, so while the main CPU is clock master shifting
a COMMAND byte OUT (internal baud gen, IOC=0), the same 8 edges shift 8 meaningless bits IN
off the idle RXD line → one phantom RX byte + spurious INTRX PER command byte sent. Phantom
0x00 = right-panel segment 0 = TRANSPOSE row = the `<Db>`; an ODD phantom count in a framed
burst swaps the (header,state) pair → PIANO (seg2,0x01) reads as (seg1,0x02)=ORCHESTRAL PAD
(timing-dependent → intermittent). PROOF: cpanel send_byte()=190 == externally-clocked
(IOC=1) RX bytes=190, while 521 phantoms are ALL internally-clocked IOC=0 — perfect
partition, zero cross terms. (No pristine-oracle A/B needed: the protocol is the reference —
sender provably correct, IOC is the firmware's own receive-enable set in its INTRX1 ISR.)

FIX (kn5000-30, shared core, upstream-relevant): gate the RX bit-count/latch on the external
clock actually being selected — `((m_serial_mode & 0x03)==0) && BIT(m_serial_control,0)` —
mirroring the sender's start-gate and the existing internal-clock suppression in
timer_callback. AFTER: send_byte()==RX (96==96, all IOC=1), phantoms 521→0, no phantom
transpose (home shows `<C >`). UART transfer modes drive RX from timer_callback, so the MIDI
channel is untouched.

VERIFIED LIVE (savestate-isolated, 3 emulated phases each, read the PNGs): PIANO→SOUND RIGHT1
PIANO, DISK→DISK MENU, MENU:SOUND→SOUND MENU, MENU:MIDI→MIDI MENU, POP&BALLAD→RHYTHM POP&BALLAD
(LED lit), PART SELECT RIGHT1→part focus (home intact, no scramble). All stable across phases.
REGRESSION: -validate clean kn5000/kn1500/kn7000/kn6000/kn6500/kn2400; sound names (kn5000-29)
real; tempo wheel (kn5000-25) intact; KN7000 boots normally (change is in a device KN7000 never
instantiates — MN10300). Instrumentation fully reverted; clean rebuild (0 CPDBG strings);
tools/publish-binary.sh done.

COMMITS: kn7000_mame b17fb8b (fix) + 0022bb6 (kn5000-30 patch + README). KN7000 findings +
this tick. Blog Part 71 "The buttons that hallucinated" (mame-blog c99f46e). Full write-up:
../KN7000/side-quests/findings/kn5000_button_mapping_findings.md (2026-07-21 FIXED section).
