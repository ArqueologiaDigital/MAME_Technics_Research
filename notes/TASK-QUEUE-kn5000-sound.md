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
| P9 | **★ THE STOPPING INSTRUCTION IS `0xF5AFC3` (named 2026-08-15).** A write tap on the transport word (log: `notes/p9-writer-2026-08-15.log`) finds ONE writer unique to the stop; every other writer (`0xF3ECE9`, `0xF3ECED`) echoes values all run long. Order is now unambiguous: **transport `0x0C` at t=139.47, AccPlayMode `0x00` at t=139.50** (from `0xF3CB3E`) — the stop decision comes first and the accompaniment shutdown follows it. Disassembled (`unidasm -arch tlcs900`, file offset `0x15AFC8`; program ROM maps `0xE00000-0xFFFFFF` mask `0x1FFFFF`): `f5afb2 ld (0x0421),0x0c` / `f5afb7 bit 3,(0x0420)` / `jr NZ` / `f5afbd bit 2,(0x0420)` / `jr Z` / **`f5afc3 ld (0x0420),0x0c`** / `f5afc8 ld (0x3470),0x00` / `ret`. So it is a STOP routine that sets terminal state only when the transport is running (bit 2 set) and bit 3 is clear, then clears `0x3470`. ⚠ The tap reported PC `0xF5AFC8`, the instruction AFTER the write — the tlcs900 prefetch offset the rig warns about; always disassemble before naming. **NEXT: find the CALLER.** The routine is entered with `ld A,0x86; calr 0xf5b084` just above it, and the open question is what condition at t=139.47 decides the song is over — song data, an end-of-track counter, or a spurious trigger. That is where an emulation defect would live, if there is one. | yes | instruction named; caller unknown | Exact measurement, log at `notes/p9-stall-2026-08-15.log`: transport leaves `0x04` **at t=139.48 and goes to `0x0C`** — which this project's own notes define as **terminal STOP** — then to `0x00` by t=140, with AccPlayMode `0x03`→`0x00` and the sub-tick frozen at `0x18`. Up to t=139 everything is healthy (sub-tick cycling 1C/4C/1D/4D/1E/4E). **So the transport is not freezing or hanging: the firmware reaches its own end-of-song state and stops cleanly.** That is a different bug class from "stall" — the question is not "what wedged?" but "why does the sequencer think the song ended at 58%?", which points at the song data or an end-of-track condition rather than at the interrupt/timing path. ⚠ Also: the demo now plays ~8 s LONGER than the recorded 131.5 s. ⚠ A running-maxima probe additionally reports a transport value of `0x10` somewhere in the run; the direct per-second sampling never caught it, so it is unexplained and NOT part of the pinned path. ⚠ Method: `demo_max.lua` reports MAXIMA and cannot show a transition — use `tools/rigs/kn5000_p9_stall.lua`. Earlier text: **★ THE SECOND STALL — re-measured 2026-08-15, and the recorded numbers no longer hold.** Two 150-160 s runs on the current build: the demo is **still healthy at t=139** (transport `0x04`, sub-tick cycling 18/19/1A/48/49/4A) and **stopped by t=140** (transport `0x00`, AccPlayMode `0x03`→`0x00`, sub-tick **frozen at `0x18`**). So it now plays ~8 s LONGER than the recorded 131.5 s, and a running-maxima probe shows transport passing through **`0x10`** on the way — an intermediate state the note does not mention. ⚠ Do not debug against "131.5 s" or "goes to 00": the moment has moved and the path has a step in it. Several things changed underneath since it was written (the INT0 core fix, the NVRAM correction, the detect_period bound). ⚠ Method note: `demo_max.lua` reports running MAXIMA, which is why `0x10` was invisible and the transition unobservable — use `tools/rigs/kn5000_p9_stall.lua`, which logs CURRENT values every second and announces the first departure from `0x04` with its destination. Exact transition second pending a capture in flight. Original text: **★ THE SECOND STALL.** After 3fd44f3 the demo plays 19.26 -> **131.5 s** then `transport` (0x0420) goes 04->00. That is beat 171 of 292 = **58% of the song** (was ~6%). Stuck voices precede it from t~100 s. Reproduced EXACTLY in an independent replicate, both render modes. Deterministic time + a working instrumentation path make this the best-conditioned open bug we have. | yes | the INT0 hunt's method applies directly: timestamped latch logging + LOG_HANDSHAKE |
| P10 | ⛔ **THE OCTAVE ERROR IS A MEASUREMENT ARTIFACT (2026-08-15) — the pitch is correct.** Played a KNOWN keybed note (`:KEY2` field `C4`, MIDI 60) and measured what comes out: **260.87 Hz against an expected 261.626 — −5 cents**, agreed by autocorrelation and spectral peak independently. Not an octave; not a semitone. **The confound:** P10 compared the emulator's *spectral centroid* against a **sine** reference render. A sine's centroid IS its fundamental; a harmonically rich instrument's is far above it. Control, measured on this same correct capture: fundamental MIDI **59.9**, centroid MIDI **85.1**, while a pure sine at that pitch has centroid MIDI **60.0**. So a *correct* note reads ~25 semitones "high" by that metric — larger than the 13 P10 reported. That also explains the noted puzzle that correcting for +12 did not restore the note-by-note match (excess only +0.039): there was no pitch error to correct. ⚠ **Scope:** this tests the KEYBED path only. The demo/sequencer path is untested and could still carry a pitch fault — but it must be measured against a *fundamental*, never a centroid-vs-sine comparison. Rig: `tools/rigs/kn5000_note_capture.lua`. Original text: **★ THE OCTAVE ERROR.** The emulator's onset centroid is MIDI 74-79 vs 61-63 for a reference sine render of the same MIDI — **~13 semitones (about an octave) HIGH**, in BOTH render modes, in every window. Best global shift is a stable **+12 across three captures**. The stuck-voice chord at t>100 s reads out exact semitone intervals **uniformly +35 cents** (PCM +25). ⚠ Correcting for +12 does NOT restore the note-by-note match (excess only +0.039), so there is more than one fault. Suspects: `update_pitch()`, the 0x3524 reg[8] anchor, `pitch_step`'s chunk-relative construction. A uniform octave is far more likely one wrong constant or shift than an undecoded table. | no | oracle is the pass/fail test |
| P11 | **★ `detect_period()`'s acceptance gate.** ⛔ **2026-08-14 (ADJUDICATED — DO NOT LAND THE GATE CHANGE).** Full verdict in `notes/FINDINGS-ic307-page2.md`. Gate-lowering is **falsified on ground truth**: on four chunks whose true period is provably 64, gate 0.30 returns **31.53** — the second harmonic, an octave wrong the other way. Page 2 is **exonerated**: all 11 of its referenced fallbacks are 16-144-sample chunks whose true period *is* N, and `maxlag` ≈ N/3 makes P=N the only answer available *by construction*; its 42 genuinely-wrong chunks are all unreferenced, so the net audible page-2 defect is **zero**. **LAND INSTEAD** the narrow piece: when the gate rejects and **N > 256**, return 0 rather than N<<16 — code-verified loop-neutral, reaches 43 chunks / 35 referenced / 3 audible. **★ The real damage is on PAGE 1** (23 referenced fallbacks ≥512 samples, 3 audible tonal drums) — retarget there. The 42-chunk error is a **search-range** defect (period 64 unreachable at N=128 for any threshold), queue separately. Earlier: **2026-08-14 (second pass): REFRAME BEFORE FIXING.** `class:entry` is now decoded — `bank=(class>>2)&1, page=class&3`, validated by three exact page-size hits (198/168/57) and a 1495-chunk total matching the driver's own figure. Real scale: **543 of 1495 chunks (36%) take the P=N fallback**; gate 0.30 recovers 80. ⚠ **But the zone-slope oracle cannot judge the change**: 94 chunks change period, 321 are referenced by zone sets, **overlap = 0**, so both gates score identically out of blindness, not agreement. And the fallback concentrates in **page 2 (500 of 1050)** which zone sets barely reference (75 of 530 refs) — very likely drums/SFX/one-shots where *aperiodic is the correct answer*. **So the first question is no longer "lower the gate?" but "are page-2 chunks meant to be pitched at all?"** Answer that from the tone records (which chunks melodic voices actually select) before touching the detector. Earlier note: **2026-08-14: quantified offline, no build needed.** `tools/kn5000_period_oracle.py` ports the detector faithfully and sweeps IC307's 198 waves: the shipped `peak >= 0.5` gate leaves **11 waves on the P=N fallback**; a 0.30 gate leaves **6**. So the change recovers 5 waves. ⚠ Whether the recovered periods are CORRECT is still ungraded, because the zone-slope oracle is blocked: the zone table addresses samples as `class:entry` (entries to 0x1B2, 429 distinct) while the global IC307 index has 198 (max 0x0C5), so `entry` is not a global wave index. **Next: decode `class:entry` -> (chip, wave).** Likely `class` selects the waveform chip, in which case most zones resolve to the undumped IC304/305/306 and the oracle can only ever grade the IC307 subset. Original text: **★ `detect_period()`'s acceptance gate.** The `peak >= 0.5` test rejects real periods: `b0p1c35` peaks 0.436 at lag 175. The fallback then sets P=N, so `update_pitch()` resamples by up to 44x. 43 of 565 `P==N` chunks have N>256; 7 are tonal. A measured band-aid (bound the fallback at 256) gives `b0p1c35` events 2171->40 and >6 kHz energy -6.85 -> -17.24 dB at unchanged level — but it treats the symptom. Fix the gate so P=175 and the transposition is a musical 3.9x. | yes | measured, NOT landed |
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
   ★★ **AND THAT `TGMODE bit 1` COST US A DAY.** It is the "free voices whose EG has finished"
   probe, and with it On the firmware tears down a HELD note 0.11-0.16 s after the gate. It is
   why Felipe heard almost every ORGAN & ACCORDION patch stop short while our rigs — which
   always write their own private cfg — measured every one of them sustaining. **A private
   `-cfg_directory` protects the rig and hides the user's bug.** When reproducing a REPORTED
   session, run it once with the reporter's OWN cfg (`KN5_CFGSRC=`) before concluding anything.
   Full account: `notes/FINDINGS-kn5000-eg-level-law.md` §M.
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

---

# END-OF-DAY STATE 2026-08-06

## Shipped defaults (all in kn5000_tonegen.cpp device_start; each has an env override)

| switch | default | why |
|---|---|---|
| `KN5000_EGLAW` | **lin** (`=log` reverts) | FITTED, not derived. The log law is bit-exact from ROM 0x010764 but drives sustains to -53..-76 dB, below the silence interlock -> `status_r()` reports silent -> firmware writes 0x7E00 and DEALLOCATES the channel 0.13-0.31 s into a hold. That is the "strings decay" bug: a voice TEARDOWN, not a low level. |
| `KN5000_LVL080` | **on** (`=off`) | +0x080 as the per-voice output level. JOINT with EGLAW — neither works alone (lin alone clips 7.65%; together 0.0000%). |
| `KN5000_HANDOFF` | **off** (`=ctrl`) | The decode is DERIVED and correct (bit 8 never set, 1814/1814). Enabling it put "extreme noise" through Felipe's speakers. ⚠ NOT because of undumped banks — RETRACTED — but because 738 of 739 un-muted notes are IC307 page-1 recordings that `detect_period()` cannot pitch, played at 11.5x-19x. Blocked on P11. |
| `KN5000_UNDUMPED` | **mute** (`=play`) | Felipe's spec: PCM mutes undumped sockets, SINE plays everything. Mute is after pan, before mix, so allocation/status_r are untouched. |

## EG structure — DERIVED from the sub-CPU ROM, settled

`+0x800` ATTACK, `+0x840` DECAY1->SUST1 (rate floored 4), `+0x880` DECAY2->SUST2 (floored 0),
built from partial couples (+39,+40)/(+41,+42)/(+43,+44). **All three are KEY-DOWN segments;
segment 2 is TERMINAL; there is NO release segment** (an 8 s held note gets ZERO register writes
between the note-on burst and key-off; key-off writes only +0x800/+0x840 at rate 0). `+0x8C0` is
a level|pan word, not a fourth segment. ⇒ "we run into release while the key is held" is REFUTED.

## Bank reality (measured, both demos)

| demo | on IC307 | undumped | **share of rendered ENERGY undumped** |
|---|---:|---:|---:|
| organ | 92.9% | 7.1% | **75.5%** |
| piano | 84.8% | 15.2% | 0.35% |

⚠ The organ's LOUDEST layer (64 bass note-ons) is undumped, so muting costs it 7.4 dB and its
bass line. Default patches for **strings, brass, synth, guitar** are bank 0 = IC304 = undumped,
so they render NOTHING in PCM. **"Strings are silent" != "strings decay"** — always separate.

## Blocked on ONE hardware measurement

`R`, the gain-staging reference (which level code is full scale), is not in the firmware and now
blocks THREE changes: the EG law, the hand-off level, and overall gain staging. Ask Felipe to
hold one piano note at max velocity and report line-output peak relative to the clip point.

## Open, ranked
1. **P11 `detect_period()`'s acceptance gate** — now the top item: it blocks the hand-off decode
   (738 organ notes, all on the GOOD ROM). It rejects real periods (0.436 peak at lag 175) and
   falls back to declaring the whole recording one cycle.
2. 553 organ `FE00` notes still attenuated by something else.
3. P9 the second stall at t=131.5 s. 4. BUG-1 FindBestSlot 0xFF -> +85 semitones.

## Rigs built today (all default-off, all with a metric that CAN fail)
`tools/kn5000_capture_hold.sh` + `kn5000_hold_note.lua` + `kn5000_hold_analyze.py` (one key held,
one voice — the WAV IS the envelope; `sus_db` moves -47.4 -> -2.0 between arms);
`kn5000_collapse_detect.py` (CLICK/INAUDIBLE/OK, validated at sine level);
`kn5000_tgbus_trace.lua`; `kn5000_handoff_probe.lua`; `kn5000_capture_perf.sh`.

⚠⚠ **SEVEN criteria this session were structurally incapable of failing, all mine, and one put
extreme noise through Felipe's speakers.** rms/peak/clipping CANNOT detect a wrong-recording or a
dead-envelope defect. Before quoting a number, ask whether it would differ if the bug were absent.


---

# 2026-08-06 late — `detect_period()` is now the ROOT OF THREE SEPARATE SYMPTOMS

P11 is no longer one bug among several. It is confirmed, DERIVED, as the cause of:

1. **Jazz Flute MIDI 73-78 sounding +12 semitones** (Felipe, MIDI controller). `detect_period()`
   returns **20.948** samples for bank1/page1/chunk 4 where YIN returns **10.436** — ratio
   **2.007**, an exact period DOUBLING. Neighbouring flute chunks agree to 0.6%; rendered audio
   peaks at ~1110 Hz vs 1112.6 predicted. Zone boundaries MIDI 73/79/85.
2. **The organ "extreme noise"** when `KN5000_HANDOFF=ctrl` is enabled: 738 of 739 un-muted notes
   are IC307 page-1 recordings the estimator cannot pitch; the fallback declares the whole
   recording one cycle and plays it at **11.5x-19x**.
3. **The t=35-37 s left-channel cluster** in the Feature Demo (the original P11 finding): a
   rejected autocorrelation peak of **0.436 at lag 175** falls back to P=N=1496 and resamples a
   tonal recording by **33.3x**.

**SCOPE: 15 exact-integer-ratio failures among the 402 real recordings.** (The 83 non-integer
disagreements with YIN are NOT claimed as defects.)

## Why it was NOT fixed, and what a fix needs

A minimal sub-multiple guard repairs Felipe's chunk and **breaks 0 of the 304 currently-correct
ones** — but leaves **14 of the 15**, and 3 of those need a *multiple* test rather than a
sub-multiple one. That makes it an ESTIMATOR REPLACEMENT, not a guard.

⚠ **The oracle problem:** our only independent pitch reference is YIN, and validating a
YIN-derived replacement against YIN is circular. A real fix needs an oracle that is not YIN —
candidates: the wave directory's own parameter block (does it carry a root/period field we have
not decoded?), the firmware's own key-split boundaries, or Felipe playing the affected patches
and reporting the interval.

★ This is now the highest-value single fix available: it is on the GOOD ROM, needs no hardware
constant, and unblocks the hand-off decode (738 organ notes) as well as the two pitch symptoms.

## Awaiting Felipe
* ⭐ **The ORGAN patch names, as shown on the LCD, that decay for him.** Measured: 18 of 20
  sustain flat to 30 s; the one that decays (Soul Organ) has segment-2 level 0x04 = max
  attenuation, i.e. designed to. "Almost all" and "one of twenty" cannot both hold, and velocity
  (flat 15->127) and polyphony (16 s hold survived six strikes) are both REFUTED.
* Does a held note decay with nothing else playing at all?
* Theatre Accomp (p2/2 LCD RIGHT 2) should also be silent — all partials on undumped bank 0.

## Rig lesson (the eighth this session)
A ten-patch sweep returned ten holds, ten envelopes and ten clean `sus_db` rows while **seven
patches had silently re-used one selector** after the panel drifted to another screen. It read as
"nine of ten sustain"; it meant "one patch, nine times". Two later runs drifted onto the BASS
group *while passing* a distinct-selector check. **A distinct-selector check is necessary but NOT
sufficient — the LCD snapshot is the arbiter.**
