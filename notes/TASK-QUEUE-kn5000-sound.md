# KN5000 sound work — pending task queue (2026-08-06)

Written to survive context compaction. Status of each is honest: what is DONE is measured,
what is PENDING has not been started.

## Currently RUNNING (do not duplicate)

| # | task | agent state |
|---|---|---|
| R1 | MixedCase re-casing of the 483 new sub-CPU labels + the 12 wrong-name fixes | running |
| R2 | Oracle re-run over the FULL 194.6 s demo (was measured on a 13 s sliver) | running |

## PENDING — parallelisable

These touch disjoint files/tools and can all run at once. The only shared resources are
(a) the MAME build tree — **only ONE agent may build**, others use the published binary at
`~/compartilhado/kn7000-emulator`; and (b) the disasm repo — serialise commits there.

| # | task | needs build? | notes |
|---|---|---|---|
| P1 | ~~PCM glitch attribution~~ **DONE 2026-08-06 (`5fd8067`)** — lead hypothesis (derived loops) **REFUTED**: seams fired 13/6794 events (0.19%), overrun clamp 0, and statically the derived seam step is a median **0.68x** the 99th-percentile ordinary step inside the same loop. The 130 ms burst = voices 50+51 on `b0 p0 c155`, an **UNDUMPED socket** playing an unrelated recording CORRECTLY (needs a dump, not code). ★ The one real emulation defect found: **`detect_period()` INVENTS a period** — its `(samples <= 2048) ? (samples<<16) : 0` fallback fires when the autocorrelation peak misses a `>=0.5` gate, so `b0p1c35` (peak **0.436 at lag 175** — a REAL period, rejected) gets P=N=1496 and a TONAL recording is resampled **33.3x**. On the real IC307 dump, so not a substitution artefact. Fix the ACCEPTANCE GATE, not the fallback. See P11. Original text: Full plan already written: `notes/TODO-kn5000-pcm-glitch-attribution.md`. Lead hypothesis: the sustain loops are NOT in the ROM — `compute_loop()` derives them — so a loop whose length is not a whole number of periods splices at every wrap. ⚠ Re-measure the burst first: it was characterised BEFORE the INT0 fix (3fd44f3) and may have moved or gone. | yes (instrumentation) | step 3 of that plan is a static pass over all 1495 chunks needing NO emulator |
| P2 | ~~Per-chunk tuning trim~~ **HYPOTHESIS NOT SUPPORTED — see P10.** ⚠⚠ **RETRACTED 2026-08-06:** "Parts 7 and 11 are at the correct absolute pitch" was a 243-note artefact of a null that displaced TIME only and so did not control for REGISTER. Against a pitch-permuted null over the full song, NO part clears z=3 (Parts 7/11 sit at z=+0.34/+0.94) at note counts where the positive control reaches z=+2.8..+20.5; PCM agrees, so it is not the sine renderer. Overall pitch recovery is **0.6%** (hit@0 - NULL-P = +0.003 vs the control's +0.483). A 40-cell time/register scan finds |z| <= 2.65 everywhere — **there is no zone to localise.** Do not restart this without new evidence. | no | superseded by P10 |
| P3 | **Stuck EG voices.** Type A voices park at their final EG segment target forever at ~-77 dB (~2 LSB vs the 0.5 LSB silence threshold), so `eg_running` never clears. PCM decay was masking an envelope that never terminates. NOT what stalled the demo (refuted), but still a real defect. | yes | `eg_level_to_gain` already special-cases level 0 as true silence, so the law expects zero to be reachable |
| P4 | **Triage the 130 uncommitted `[UNCERTAIN]` findings** in `kn5000-roms-disasm/symbols/proposals/`. Several are real bugs, not naming quibbles: a claimed off-by-0x68 in the part-record base (region 12 measures 0x041368, region 4 says 0x041300); a possible 0xFF return from `Voice_Selector_FindBestSlot` used as a word-table subscript; an out-of-range table read in `Voice_ToneTableRamp_Down`; slot resolvers that store before bounds-checking. | no | pure analysis |
| P5 | **~60 addresses where the build and the curated symbol reference disagree** (regions 5/7/8/12 enumerate them: 0x026769, 0x02684A, 0x026975, 0x026AAA, 0x026BDC, 0x026E5B, 0x026EC3, 0x0271BC, 0x027A46, …). Someone must pick one set deliberately. | no | do AFTER R1 lands to avoid conflicts |
| P6 | **788 remaining `LABEL_` placeholders** in the ASL archive at addresses no region agent named — the honest remaining backlog. | no | do AFTER R1 |
| P7 | ~~**"Sound Name Error"**~~ **CLOSED 2026-08-06 — not reproducible** (0 events in 514 s over 5 conditions incl. both historical deterministic bad cases; a forced one-byte control reproduces it exactly, so the detector is not blind). It was never a bad sound number: the value is a 7-bit inter-CPU REQUEST TAG and the "lookup" is a spin waiting for the SubCPU's tagged reply on channel 3 (DE=0x0E00 is a TIMEOUT, not a table size). Almost certainly downstream of the INT0 wedge fixed by 3fd44f3. See notes/FINDINGS-sound-name-error.md. Original text: `fee694` writes the fallback string into the sound-name buffer when the lookup at `fee55a` fails — it scans records (byte 7 = sound number) and fails on the 0xFFFF end marker. So something requests a sound number that is not in the table. Never chased to the requester. | maybe | may have been a downstream symptom of the INT0 wedge — RE-CHECK IT STILL HAPPENS first |
| P9 | **★ THE SECOND STALL.** After 3fd44f3 the demo plays 19.26 -> **131.5 s** then `transport` (0x0420) goes 04->00. That is beat 171 of 292 = **58% of the song** (was ~6%). Stuck voices precede it from t~100 s. Reproduced EXACTLY in an independent replicate, both render modes. Deterministic time + a working instrumentation path make this the best-conditioned open bug we have. | yes | the INT0 hunt's method applies directly: timestamped latch logging + LOG_HANDSHAKE |
| P10 | **★ THE OCTAVE ERROR.** The emulator's onset centroid is MIDI 74-79 vs 61-63 for a reference sine render of the same MIDI — **~13 semitones (about an octave) HIGH**, in BOTH render modes, in every window. Best global shift is a stable **+12 across three captures**. The stuck-voice chord at t>100 s reads out exact semitone intervals **uniformly +35 cents** (PCM +25). ⚠ Correcting for +12 does NOT restore the note-by-note match (excess only +0.039), so there is more than one fault. Suspects: `update_pitch()`, the 0x3524 reg[8] anchor, `pitch_step`'s chunk-relative construction. A uniform octave is far more likely one wrong constant or shift than an undecoded table. | no | oracle is the pass/fail test |
| P11 | **★ `detect_period()`'s acceptance gate.** The `peak >= 0.5` test rejects real periods: `b0p1c35` peaks 0.436 at lag 175. The fallback then sets P=N, so `update_pitch()` resamples by up to 44x. 43 of 565 `P==N` chunks have N>256; 7 are tonal. A measured band-aid (bound the fallback at 256) gives `b0p1c35` events 2171->40 and >6 kHz energy -6.85 -> -17.24 dB at unchanged level — but it treats the symptom. Fix the gate so P=175 and the transposition is a musical 3.9x. | yes | measured, NOT landed |
| P8 | **Upstream the INT0 fix.** `3fd44f3` removes MAME's tmp94c241 acceptance-time /INT0 level re-assertion. It is a CPU-core fix affecting any tmp94c241 driver, so it belongs upstream. Follow the PR workflow (`MAME-PR-HANDOFF.md`, `tools/sync-check.sh`). | yes | also re-check commit c11209d's original motivation is still satisfied — it is (voice names verified present) |

## PENDING — NOT parallelisable / blocked on hardware

| # | task | blocker |
|---|---|---|
| H1 | **★ Re-dump IC14** (`kn5000_rhythm_data_rom.ic14`). Its A19/A21 are transposed; the driver de-scrambles at load via ROM_CONTINUE and it is marked BAD_DUMP. Schematic proves the board is wired straight, so the dump is at fault. AD18/AD20 are pins 2 and 44, adjacent across the NC at pin 1 — where an adapter mis-maps. IC307's dump is CLEAN, so its procedure is the one to reuse. | Felipe's hardware |
| H2 | **★★ Dump IC304 / IC305 / IC306** (waveform ROMs). Currently BAD_DUMP copies of IC307, and `kn5000.cpp` records that **~75% of sounds select them** — so most instruments in the demo play a real-but-WRONG waveform. This is very likely the single largest audible defect and no software fix touches it. | Felipe's hardware |

## Decisions Felipe still owes

* Naming case for FUTURE work — R1 settles the existing 483 as MixedCase.
* The ~60 build-vs-reference disagreements (P5).

## Standing measurement rules earned in this investigation

1. `ioport_field:set_value()` **TOGGLES** a `PORT_CONFNAME` field, it does not assign, and MAME
   persists the value in `cfg/*.cfg` — so you get `saved XOR arg`. Always use a PRIVATE
   `-cfg_directory` and VERIFY by reading the port back every second.
2. ⚠ CORRECTED 2026-08-06: the PUBLISHED `kn7000-emulator/cfg/kn5000.cfg` carries **no AREA
   override** — only TGMODE bit 1 and ENCODER=73. The AREA=2 was in the BUILD-TREE cfg at the
   time. Region did change whether the old wedge reproduced, so still always state which AREA a
   measurement used — but verify the cfg rather than assuming, and always use a private
   `-cfg_directory`.
3. Always `-seconds_to_run`, never a wall-clock `timeout`, when comparing two runs — otherwise
   they end at different machine times and diverge harmlessly. The emulator IS bit-deterministic.
4. Always `rm -f nvram/kn5000/nvram1` first — 1 MB of work DRAM is persisted as NVRAM.
5. tlcs900 `RDOP` prefetches PC+3: a read tap on an instruction's own address counts the
   PREVIOUS instruction. Put taps at target+3 with a byte-lane mask.
6. Compute the NULL for every claim, AND CHECK THE NULL CAN FAIL. Three hypotheses here died to
   their own null. ⚠ 2026-08-06: my own headline claim "sine mode has 0 clicks, so the defect is
   in the PCM sample path" used a null THAT CANNOT FAIL — at the demo's sine level an 8000 step
   would need a >21 kHz fundamental. A criterion that cannot fail is not a pass, and I enforced
   that rule on others while breaking it myself.
6b. ⚠ A step detector is NOT a glitch detector. `|dx| > 8000` is reached by any full-scale
   content above ~1.9 kHz, so drums and SFX trip it by being played CORRECTLY.
7. `build.sh` exits 0 EVEN ON COMPILE FAILURE — grep for `error:` and check binary mtime/size.
