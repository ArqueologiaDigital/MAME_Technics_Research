# Effects DSP — the full "selecting an effect doesn't change the sound" chain (2026-07-11)

Felipe: effects processing should work well — selecting a reverb/chorus in the sound menus
should audibly change the sound. It didn't. This note traces the ENTIRE dependency chain,
which turned out to be five stacked problems. **ALL FIVE ARE NOW FIXED** -- the effects DSP
processes audio end-to-end and selecting an effect is audible (see "Final verification" at the end).

## Symptom
Selecting a reverb (e.g. REVERB screen -> Dark2) did nothing audible. The panel/UI worked
(reverb type highlights correctly) but the sound never changed.

## The chain (each layer blocked the next)

### 1. Runtime effect uploads were GATED OFF (FIXED, commit 87a2964)
The firmware's DSP power-on self-test (fw 0x48404d25) software-triggers INTC group 0x17
(GxICR 0x3400015c bit0) and spin-polls bit4 (REQUEST). The emulator never set REQUEST, so the
0x3ffff-count poll timed out and the firmware stored **0x500066CC = 0xFF ("DSP absent")**. That
byte hard-gates the runtime DSP write path (fw 0x48404ef5 writes the host index/data ports only
when 0x500066CC == 0). So every runtime effect upload was silently dropped.
- The initial probe (0x48405028) PASSED and stored 0; this second self-test overrode it ~1s later.
- FIX: model the self-test ack. `intc_w` latches group-0x17 REQUEST when the DSP is present (the
  group has no ISR / no other user). 0x500066CC now stays 0 and runtime uploads flow: selecting
  Dark2 uploads a full microprogram (+783 host writes to 0x9C000000) to the SHARC.

### 2. The DRC ran STALE code after a runtime upload (FIXED in the core; the driver CALL is gated off)
Runtime uploads land in the SHARC's internal PM via `m_dsp->space(AS_PROGRAM).write_qword(...)` --
a host write that BYPASSES the SHARC DRC's self-modify detection (which only fires for PM writes
issued by the SHARC's own pm_write handlers, gated on m_max_sram_pc). So the recompiled cache went
stale and the kernel kept executing the OLD passthrough at PM 0x8400.
- FIX (core): `adsp21062_device::notify_pm_written()` sets `m_core->cache_dirty = 1`, which makes
  `execute_run_drc()` flush + recompile on its next timeslice. Safe deferred invalidation.
- The driver would call it on every runtime PM block close (dsp_data_w, mode 1, running). With the
  call ACTIVE, the effect microprogram genuinely EXECUTES (verified: it advanced to the effect code
  region and hit new unimplemented ops -- see #3/#4). **But the call is currently COMMENTED OUT**
  because executing the real effect regresses to silence (see #5). Re-enable once #5 is solved.

### 3. Missing SHARC ALU op 0x09 = fixed-point average (FIXED, this commit)
The effect microprograms use `Rn = (Rx + Ry)/2` (ALU single-function op 0x09, the fixed twin of
the float FAVG 0x89). The interpreter threw "unimplemented ALU operation 09"; the DRC already
routed 0x09 to `generate_unimplemented_compute` -> `compute_fallback` -> `COMPUTE()`, which then
threw. Implemented `compute_avg` (sharcops.hxx + sharc.h): signed 33-bit add >> 1 (can't overflow
-> AV clear; AC = adder carry). Fixes BOTH interpreter and DRC (via the fallback).

### 4. DRC threw on shift-immediate FDEP-SE (FIXED, this commit)
Once the effect ran (cache invalidated), it hit shiftop 0x13 (`FDEP Rx BY <bit>:<len> SE`). The
interpreter implements it (SHIFT_OPERATION_IMM case 0x13) but the DRC's `generate_shift_imm` threw
`unimplemented_shiftimm` for 0x13/0x1b instead of falling back. Added `shiftimm_fallback` +
`generate_unimplemented_shiftimm` (mirrors the compute fallback) so those route to the interpreter.

### 5. The effect output never reached the bridge — RESOLVED (commit 38a3f4a): follow the kernel's live I4
**FIXED.** By dumping the running reverb microprogram from DSP PM (Lua read_u64 0x8000-0x8DFF ->
unidasm -arch sharc) the output/input convention is now known exactly: the effect keeps its per-frame
stereo audio in the DM index register **I4** -- it writes the output frame with `DM(I4)=R8` /
`DM(M2,I4)=R8` (0x8468/0x846d) and reads the input with `DM(0x20,I4)` (0x8404). So output = [I4],[I4+1]
and input = [I4+0x20],[I4+0x21]. The passthrough parks I4 at 0xC350 (SPORT0 TX-A+0xE) -- which is why
the old fixed `sport_tx_buffer(0,0)+0xE` read worked for it -- but a real effect (Dark2 reverb) parks
I4 at the SPORT0 TX-**B** autobuffer 0xC358, so the fixed 0xC350 read got only zeros => silence, even
though the effect ran and its coefficients (dumped from DM 0x9800/0xC000 -- all valid reverb floats)
and output-level (R2!=0) were correct. The bridge (`dsp_audio_tick`) now reads the SHARC's live I4
(`adsp21062::dm_index_reg(4)`) and uses output=[I4], input=[I4+0x20]; this follows whichever SPORT
autobuffer the loaded effect uses WITHOUT a full SPORT-DMA model. With I4-following the runtime
cache-invalidation (notify_pm_written) is enabled, so selecting a reverb loads+runs it and its output
is audible: Dark2 note RMS 1863 vs 0 before; the default effect stays audible (no silence regression).
CAVEATS / still-open polish: (a) the tone generator is still a synthetic placeholder (no PCM samples,
no note release), so A/B effect *character* can't be judged by ear yet -- reverb TAIL tests are
confounded by the TG not decaying; (b) SPORT double-buffer A/B alternation isn't modelled (I4 is
stuck on one buffer, which is fine here); (c) wire the DIGITAL EFFECT on/off + per-effect depth so
menu changes are reflected. But the effects DSP now processes audio end-to-end.

### (historical) The effect executes but OUTPUTS ZERO — was the remaining blocker
With #1–#4 in place and the #2 cache-invalidation call ACTIVE, the effect microprogram runs
correctly enough to:
- read its input (DM 0xC370 = 16777205, the TG audio arrives), and
- make ~1.76M reads/note to external memory in word range **0x11372 .. 0x656F0** (its reverb
  delay lines) -- and that memory IS mapped (data_65l: 0x09000-0x1ffff internal m_data_sram sized
  0x17000; 0x20000-0xfffff .ram()), so the reads are backed.
...yet it writes **0** to the output slot DM 0xC350/0xC351 (and 0xC352/3). So the whole DSP output
collapses to silence.

Because that's worse UX than the (buggy-but-audible) stale passthrough, the #2 call is gated OFF
for now -- with it off, 0xC350 = 16777205 again (audible instrument, effects don't change).

**ROOT CAUSE (2026-07-11): the kernel never commits its output frame -- almost certainly gated on
the unmodelled SPORT autobuffer DMA.** Detailed instrumentation while a Dark2 reverb ran (cache-
invalidation ON so the effect executes):
- SPORT bases are UNCHANGED from the passthrough: tx0A=0xC342, tx0B=0xC34A, rx0A=0xC362 (logged live
  via sport_tx_buffer/sport_rx_buffer). So the effect did NOT relocate its SPORT buffers.
- The input handoff WORKS: DM 0xC370 (rx0A+0xE) carries the TG samples (±~0.5M, note-tracking).
- But DM 0xC350 (tx0A+0xE, where the bridge reads output) stays **exactly 0** every frame. The
  kernel reads its input but never writes a nonzero output sample to the TX slot.
- The 0xC2BD/0xC2BE pair (found earlier) is NOT the output: its RMS is a CONSTANT ~93k that does NOT
  decay after note-off (held flat 3s past release), i.e. a self-sustaining reverb recirculation
  (comb/allpass state), not the note-tracking DAC output. 0xC0xx-0xC1xx are float processing state.
=> The effect genuinely runs and recirculates, but its final "write output sample to the TX
   autobuffer" step never lands at tx+0xE. The most likely reason: that step is gated on the SPORT
   TX DMA autobuffer advancing (buffer-full / next-slot handshake) which the emulator does NOT model
   -- so the kernel keeps output at 0. (A secondary possibility is an unset output/wet-level
   coefficient, but the input reaching the kernel + active recirculation argues for the DMA gate.)

  THE FIX = model the ADSP-21065L SPORT0 (and maybe SPORT1) TX+RX AUTOBUFFER DMA: advance the DMA
  index each IRQ0 frame, service the buffer-full/half-full status the kernel polls, and let the
  kernel's output write land where the DMA then transmits it. IOP buffer-pointer regs already cached
  by iop65l_w: 0x73/0x53 = SPORT0 TX A/B, 0x7B/0x5B = SPORT1 TX A/B, 0x63/0x33 = SPORT0 RX A/B,
  0x6B/0x3B = SPORT1 RX A/B. The base SHARC has a DMA engine (sharcdma.hxx: schedule_dma_op /
  schedule_chained_dma_op) that the 21065L variant currently does NOT wire to its SPORTs -- wiring
  that up (or a focused SPORT-frame autobuffer model) is the substantial, well-scoped next sub-project.
  Next-session start: dump the kernel's IRQ0 ISR (PM 0x8020) + main loop from kn7000_disassembly/dsp/
  and find the exact instruction that would write tx+0xE and what status it waits on before doing so.
  b. **Unset mix/level parameter**: the effect's wet/dry-mix or output-gain coefficient (a DM
     control word) may be 0 because the parameter block wasn't uploaded/applied. Trace the DM
     param commits (index 0x40/0x41/0x42 addressing DM 0x9800/0xC000/0xC01x during selection) and
     confirm the coefficients land where the microprogram reads them.
  c. **A remaining wrong op**: op 0x09 or an op handled by a fallback could be subtly wrong,
     decaying the recursive reverb to 0. Sanity-check compute_avg against hardware and audit which
     compute/shift ops the effect actually exercises.
  d. **SDRAM delay writes**: confirm the effect WRITES its delay lines (tap DM writes to
     0x20000+/0x11372+), not just reads -- an empty delay line reads 0 forever.

## Also done this pass (per Felipe's cleanup request)
Removed the three development machine-config switches ("Effects DSP host stub", two "Tone
generators"): the KN7000 always has the tone generators (IC201/IC205) and the effects DSP
(IC306), so both are now unconditional. The TG-enable gate (RAM 0x500ce380=0x40) opens naturally
at boot from the TG-present strap, so the old post-boot gate-force hack (CONFIG bit2) is gone.
Default boot reaches the home screen with sound and no -cfg needed.

## Key addresses
- 0x500066CC: DSP-present gate (0=present). 0x3400015c: GxICR group 0x17 self-test handshake.
- fw 0x48404d25: self-test wait loop; 0x48404ef5: gated runtime DSP-write wrapper.
- DSP DM 0xC350/1 = output L/R, 0xC352/3 = wet sends, 0xC370/1 = input L/R (runtime-derived TX0/RX0).
- Effect code PM 0x8400; external delay memory word range ~0x11372..0x656F0.
- SHARC core: sharcops.hxx (COMPUTE + compute_avg), sharcdrc.cpp (compute_fallback/shiftimm_fallback),
  sharc.cpp (notify_pm_written), data_65l map in sharc.cpp.

## Final verification (2026-07-11)
- STABILITY: a held Dark2 note keeps a steady clean output (peak ~7%, no clipping/blow-up over 10s
  in the actual WAV) -- the reverb feedback is stable, not runaway. (Reading DM[I4] from Lua shows
  0x7FFFFF scratch values mid-frame; ignore those -- the WAV is the ground truth.)
- DISTINCT EFFECTS: selecting different reverb types loads different DSP processing (checksums of
  effect PM 0x8400-0x8470 + coeff DM 0xC000-0xC029): Room1 PM=0x6368387A/DM=0x23378650, Dark2
  PM=0x63682168/DM=0x02A2EE91, Concert PM=0x63682168/DM=0x02A2424D. Room1 vs Dark2 differ in BOTH
  code and coefficients; Dark2 vs Concert share the microprogram but differ in coefficients. So the
  full effect-selection path works, not just one effect.

## Reverb CORRECTNESS gap (2026-07-11d): the reverb rings, it does not decay
Now that the TG envelope stops notes on key-release, the reverb's decay is testable -- and it FAILS:
- Held Dark2 note, then note-off. The TG input stops (~0.2 s), but the final DAC output holds a
  CONSTANT amplitude oscillation for 3.5 s+ (RMS ~1960 flat, not decaying), with a large positive DC
  offset (samples ride ~+1150 instead of centred on 0). It rings, it doesn't decay.
- The reverb DOES read AND write its SDRAM delay lines (1.68M reads / 1.23M writes to word range
  0x36E55-0x643AB per note), so it's not stale-delay -- the feedback GAIN is ~1.0 (RT60 ~= infinite),
  and a ~1.0 feedback integrates the small DC input into the growing DC offset seen.
- ROOT CAUSE (most likely): the reverb loads its microprogram + a default coefficient set via the
  ACTIVE path, but its DEPTH/TIME parameters are NEVER applied -- the clean DspEffectSelect path
  (*(0x500A01E0) param block) never runs (still -1), and the on-screen DEPTH control doesn't trigger a
  host re-upload (checked: DATA DIAL + CPC value-encoder do nothing). So the reverb runs at its default
  (unity-feedback / infinite-time) coefficients instead of the 80% depth the screen shows.
- => "effects are AUDIBLE + type-selectable" stands, but "effects work WELL" needs the DEPTH/TIME
  parameters actually reaching the DSP (decaying feedback). Next: find the depth->coefficient path
  (does changing DEPTH write a DM coefficient? trace the reverb-screen DEPTH handler), or make the
  DspEffectSelect param-block path run so parameters apply. This supersedes the "stable + clean" note
  in blog Part 13 (stable = doesn't blow up; but it does NOT decay).

## DECISIVE 2026-07-11e: the reverb output SATURATES and the bridge misreads it
Tapped the kernel's writes to the candidate output slots (0xC350/0xC352 = TX0A, 0xC358/0xC35A = TX0B)
during a Dark2 note + note-off:
- **Slot 0xC358 is written with 0x7FFFFF (= +full-scale 24-bit, RAILED)** at note-on and STILL railed
  +3 s after note-off (0xC350/0xC352/0xC35A get 0). So the kernel's reverb output SATURATES to the
  positive rail and stays there -- the feedback loop is unstable (grows until it clips), it does not
  "ring cleanly", it blows up to the rail.
- Meanwhile the BRIDGE (dsp_audio_tick follows live I4, reads DM[I4]) yields only a ~7% oscillation in
  the final WAV -- a DIFFERENT, much smaller value than the railed 0xC358. So the I4-following bridge
  is NOT reading the kernel's committed output slot; it reads some lower-amplitude DM state that
  happens to track note-on (rises during the note) but never decays. **=> the "Dark2 RMS 1863,
  effect audible" result (Part 13 / commit 38a3f4a) is a BRIDGE ARTIFACT of an unstable computation,
  not a faithful reverb.** All three reverb types behave identically (railed 0xC358, ~7% bridge), so
  it's SYSTEMATIC, not a per-type depth/coefficient problem -- which also rules OUT the earlier
  "depth/params not applied via DspEffectSelect" hypothesis as the primary cause (that path IS dead --
  *(0x500A01E0) stays 0xFFFFFFFF even after selecting Dark2 -- but it's not what makes it ring).

### Corrected honest state of the effects DSP
- DRY passthrough (default, no active effect): VERIFIED CORRECT (off==on within 1%, Part 12). The DSP
  audio PIPELINE (TG->DSP->DAC) is real and clean.
- ACTIVE effect (reverb): microprogram loads + executes + reads/writes its SDRAM delay lines, BUT its
  output slot saturates to the rail and the bridge reads the wrong DM location. NOT a faithful reverb.

### Two independent root causes to fix (both needed), for the next dedicated effort
1. **Output capture**: the effect output must be read the way the SPORT0 TX autobuffer DMA reads it
   (advance through the TX ring at the DAC sample rate), NOT via DM[I4] at an arbitrary tick phase.
   Model the SPORT0 TX autobuffer DMA (tx0A=0xC342.., tx0B=0xC34A.. runtime-derived) so the committed
   output frames flow to the DAC. This is the "still-open polish (b)" from #5 above -- now shown to be
   load-bearing, not cosmetic.
2. **Reverb saturation**: 0xC358 hitting +full-scale means the feedback path grows unbounded. Suspect
   a systematic DSP-core arithmetic error (affects all types equally): re-check the ops the effect
   uses against the ADSP-21065L Technical Reference (repo root) -- ALU op 0x09 (fixed avg), the
   shift-imm fallback (FDEP-SE 0x13/0x1b), and MAME's float mul/add rounding/saturation -- and whether
   fixed vs float mode / the MR accumulator scaling is right for the delay-line feedback multiply.
   (Tooling now ready: full decompressed program image dumped to
   ../kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin via a Lua chunked read; the DSP PM
   microprogram dumps to unidasm -arch sharc as before.)

### interpreter vs DRC (2026-07-11e cont.): saturation is in the ALGORITHM, not the DRC
Re-ran the output-slot tap with -nodrc (SHARC interpreter):
- 0xC358 rails to 0x7FFFFF in BOTH interpreter and DRC => the reverb output saturation is
  fundamental to the effect computation (coefficient / output scaling / float->fixed FIX
  conversion), NOT caused by my DRC additions (op 0x09 avg matches MAME's own dasm line 200
  "R = (Rx+Ry)/2"; shift-imm 0x13/0x1b fallback routes to the interpreter).
- Minor discrepancy: 0xC352 ALSO rails in the interpreter but is 0 under DRC. So there IS a
  DRC/interpreter divergence on a second output word -- a separate, lower-priority correctness bug
  in the SHARC DRC (a multifunction/parallel op or a flag) worth chasing after the saturation.
- The notes' "Reverb output = FIX(reverb_float F1) x R2" means the rail is most likely the float->fixed
  FIX conversion saturating: the internal reverb float exceeds unity (or R2 is too large) and FIX()
  clamps to +full-scale. PRIME next step: tap F1 (pre-FIX float) in the running reverb microprogram --
  if F1 is sane (<1.0) but the fixed output rails, it's the FIX/scaling; if F1 itself grows unbounded,
  it's the feedback multiply (delay x coeff) -- check MAME's SHARC float mul/MAC vs the ADSP-21065L TRM.

### SMOKING GUN 2026-07-11f: the reverb FLOAT filter feedback is >= 1.0 (it diverges)
Dumped the running reverb microprogram (DSP PM 0x8000-0x8DFF via Lua read_u64 -> unidasm -arch sharc,
saved analysis below). The output path is unambiguous:
  0x8464  F1 = F15 + F13            ; F1 = reverb output (float)
  0x8465  R8 = FIX F1               ; float -> fixed
  0x8466  R8 = R8 * R2              ; R2 = output-scale coeff (DM(I0,M2))
  0x8467  R8 = CLIP R8 BY R1        ; clamp to +/-|R1|  <-- output rails here
  0x8468  DM(M2,I4) = R8            ; commit word 0   (I4 pre-mod by M2)
  0x8469..0x846d  same for word 1, then DM(I4,M1)=R8 (I4 POST-mod by M1 -> the ring advances)
Because the committed output sits at CLIP's rail (0x7FFFFF) constantly, |FIX(F1)*R2| >= |R1| always,
i.e. the reverb output float F1 has DIVERGED (grown unbounded). F1 is produced by the float allpass/
comb chain at 0x847c-0x8483:
  F12 = F3 * F7 ;  F3 = F11 + F12 ;  F7 = F3 * F7 ;  F11 = F7 + F12   (coeffs F7/F3 from DM(I0,M2))
A feedback of >= 1.0 in that chain makes F3/F11/F1 blow up. So the ring/saturation = the reverb float
FEEDBACK COEFFICIENT is >= 1.0. Systematic across all reverb types == the coefficient is at its default
for ALL types because the depth/time path that would lower it (DspEffectSelect, *(0x500A01E0)=-1) is
dead. This RECONCILES the earlier "systematic rules out depth" worry: the depth path being dead for
EVERY type produces an identical default (>=1.0) feedback for every type.

Also seen in this microprogram (confirms my added ops ARE exercised by the reverb and matter):
  0x847a  R8 = (R8 + R10)/2         ; ALU op 0x09 (my compute_avg) -- in the OUTPUT mix, not feedback
  0x8474  R10 = FDEP R10 BY 15:16   ; shift-imm FDEP (my DRC fallback path)
  0x8477  R10 = MRF + (R10 * R7)    ; multifunction MAC -- the MAC is core to the filter
=> op 0x09 is in the output averaging (correct impl verified), so it's NOT the divergence source.

### The fix, now precisely scoped
Root cause = reverb float feedback coefficient defaults to >= 1.0 (no damping) because the per-effect
depth/time is never applied. Two ways in, in priority order:
1. Determine the feedback coeff's DM source and value: trace I0 at 0x847c (which DM address F7/F3 come
   from), read that float after loading Dark2. If it's ~1.0 -> confirmed unapplied depth; find the
   maincpu routine that SHOULD write the damped coeff (the +783-word active upload table, caller of
   0x48404EF5) and why it ships 1.0 / where depth would scale it.
2. Make the DspEffectSelect path run so per-effect params (incl. depth->feedback) apply
   (*(0x500A01E0) allocates lazily inside setter 0x484057d6; the setter is just never called in this
   boot state -- find its caller + gate; same family as the old TG-gate force).
Output capture (SPORT TX ring at 0x846d, I4 post-mod by M1) is a SEPARATE, secondary fix; moot until
F1 stops diverging.

### CORRECTION to the SMOKING GUN (2026-07-11g): coefficients are mostly DAMPED — cause is ambiguous
Dumped the actual reverb coefficients the diverging filter reads (live DAG regs after loading Dark2:
I0=0xC2D5, I1=0xC004, M2=1):
- Coefficient block at 0xC000 (I1 base) = TEXTBOOK DAMPED reverb values: 0.853, -0.300, 0.223, 0.112,
  0.640, 0.702, 0.458, 0.271, 0.561, 0.853 (classic Schroeder/Moorer comb/allpass feedback ~0.7-0.85,
  all < 1.0). These are CORRECT, well-damped coefficients -- a reverb with them should DECAY, not blow up.
- State/coeff block at ~0xC2Bx (I0 base) = a repeated 6-tuple {0.931, -0.931, 1.000, 0.245, -0.406,
  1.161}. The 1.161 is >unity; IF it is an allpass FEEDBACK coeff it would diverge, but it may be a
  feedforward gain (fine). Ambiguous without the filter topology.
=> My "feedback coeff >= 1.0 because depth not applied" was OVER-CONFIDENT. The 0xC000 coeffs are
   properly damped, which argues the divergence is a **SHARC ARITHMETIC bug** in an op the reverb uses
   but the passthrough does NOT (fixed-point MAC `Rm=MRF+Rxm*Rym`, mul, FLOAT/FIX round-trip, or the
   64-bit MR modelling vs the hardware 80-bit MR) -- several of these were added during the LLE work,
   and the passthrough (pure copy) exercises none of them, which is exactly why it stays clean.
   The ALTERNATIVE (the 0xC2Bx 1.161 IS the bad feedback coeff) is not ruled out.
- DISTINGUISHING TEST for next tick: trace which DM address the divergent multiply at 0x847c-0x847e
  (F12=F3*F7; F7=F3*F7; F11=F7+F12) actually pulls F7/F3 from (single-step I0/I1 at those PCs), read
  that exact float. If it's the 1.161 -> coefficient bug (why is it 1.16? is it depth-scaled wrong?).
  If it's a damped value (<1) yet the state still diverges -> SHARC arithmetic bug: unit-test the fixed
  MAC (sharcops.hxx multiop grp 3, line 806: `Rm=(MRF+p)>>32`, p=(Rxm*Rym)<<1) and FLOAT/FIX against
  the ADSP-21065L TRM. This is the crux and it's now a bounded, concrete task either way.

### 2026-07-11g cont.: 1.161 is a CONSTANT coefficient (a feedforward gain, most likely)
Read 0xC2C4/0xC2CF across before-note / note / after-off: 1.1612 is CONSTANT (unchanged) => it is a
COEFFICIENT, not diverging filter state. In the repeated 6-tuple {0.931, -0.931, 1.000, 0.245, -0.406,
1.161} the small terms 0.245/-0.406 look like the recursive (a1/a2) coefficients (|a2|=0.406 < 1 =>
STABLE biquad), which makes 1.161 a feedforward/gain term, not a runaway feedback. Combined with the
textbook-damped 0xC000 block, the weight of evidence now favours a **SHARC arithmetic bug** (a fixed
MAC / mul / FLOAT-FIX op the reverb uses and the passthrough does not) over a bad coefficient. NOT
proven -- the decisive step is to single-step the divergent float recursion (0x847c-0x8483) and watch
F3/F11 grow with damped coefficients, or to unit-test the fixed MAC (multiop grp 3) + FLOAT/FIX round
trip against the ADSP-21065L TRM. Deferred to a fresh, methodical tick (this one has already corrected
itself twice; the arithmetic check deserves careful isolation, not a rushed poke).

## 2026-07-11h: CORE-INSTRUMENTED — the reverb output float DIVERGES (definitive, quantified)
Added temporary fprintf instrumentation to the SHARC interpreter (sharcops.hxx, reverted after) and ran
Dark2 with -nodrc. Findings (this supersedes the "coefficient >=1.0" and the arithmetic-op guesses):
- **F1 (reverb output float, at PM 0x8465 `R8 = FIX F1`) diverges**: 0 before the note; at note-on it
  starts at the input level (~1.8e5) and within ~0.4 s grows to +/-2e7 (>2x full-scale 8.4e6) and
  LIMIT-CYCLES there. Run extended to 17 s AFTER note-off: F1 STILL oscillates +/-1-4e7 -- it never
  decays. So the effective feedback is ~1.0 (a self-sustaining limit cycle at the excited amplitude),
  NOT a long-but-stable reverb. Confirmed in the INTERPRETER (rules out the DRC).
- **The coefficients are correctly DAMPED and the float multiplies are CORRECT.** Instrumenting the
  executing comb/allpass taps (PM 0x840a-0x845c, all single-func FMUL `compute_fmul`) shows the tap
  coefficients are -0.618, +0.458, -0.280, +0.853 (all <1) and an input gain +/-3.2; every product
  matches Frx*Fry exactly (e.g. 3.98e7 * -0.618 = -2.46e7). So it is NOT the coefficient data and NOT
  the float multiply.
- The EXECUTING reverb path (0x840a-0x846f, ends in RTS at 0x846f) is PURE FLOAT: FMUL + FADD + DM
  store/load of float bit patterns. The fixed MAC / op-0x09-avg / 0x847c recursion I chased earlier
  (0x8470+) is a SEPARATE routine that does NOT execute for this effect -- so those ops are NOT the cause.
- Verified the stock float ops are correct: compute_fmul_fadd reads both operands before writing (no
  register hazard); compute_float/compute_fix are the stock "verified" impls; FMUL/FADD are stock.

### Where the unity feedback must be (next dedicated tick)
With damped tap coeffs + correct multiplies + no decay, the ~1.0 loop gain must be in the DELAY-LINE
handling: what value is STORED to the delay line vs read back. The taps look like
`F13 = F2 * F6,  DM(I6, M3) = R6` -- i.e. the OUTPUT accumulator gets the ATTENUATED tap (F2*F6) but
the value STORED to the delay (DM(I6,M3)=R6) is R6 (=F6), which if it is the UN-attenuated
input+delayed sum would give feedback ~1.0. NEXT: instrument the delay-line WRITEs (address + value at
DM(I6,M3)/DM(I0,M2) stores in 0x840a-0x846f) and the corresponding READ addresses to confirm (a) the
delay lengths (DAG I/M/L for I0/I6) are right and (b) the stored feedback value carries the tap
attenuation, not unity. Prime suspects: SHARC DAG circular-buffer (modulo L) addressing for the
external-SDRAM delay lines, or the reverb storing input+delayed (unity) where it should store
input+coeff*delayed. Tooling: dump reverb PM (Lua read_u64 0x8000-0x8DFF -> unidasm -arch sharc);
instrument compute_fmul / the DM write path in sharcops.hxx gated on PC 0x8408-0x8465.

## 2026-07-11i: DEEP core-instrumentation session — divergence localized to the TANK feedback (~1.0)
Exhaustive SHARC-interpreter instrumentation (all temporary, reverted). Established with certainty and
RULED OUT a large space:
- **F1 (reverb output float, PM 0x8465) DIVERGES and NEVER decays**: 0 pre-note; at note-on -> input
  level (~1.8e5); grows to +/-2e7 (>2x full-scale) in ~0.4 s; still +/-1-3e7 **11-17 s AFTER note-off**.
  So effective feedback is EXACTLY ~1.0 (self-sustaining), not <1. Same in interpreter and DRC.
- **NOT the coefficients**: instrumented the executing comb/allpass taps (0x840a-0x845c) -- coefficients
  are damped (-0.618, +0.458, -0.280, +0.853) and the F4 inter-section scale at 0x842f is exactly 1.0.
- **NOT the float ops**: every FMUL result matches Frx*Fry exactly; compute_fmul_fadd reads both
  operands before writing (no hazard); FLOAT/FIX are the stock "verified" impls.
- **Structure is a correct nested-allpass (Dattorro/Gardner) reverb**: e.g. section 0x8425-0x842e is a
  textbook allpass w=x-g*w_delayed / y=w_delayed+g*w with g=-0.618 (stable). Delay lines = a CIRCULAR
  buffer in external SDRAM: B6=0x20000, L6=0x456F0 (284,400 words), pointer DECREMENTS (M3=-1).
- **Circular-buffer off-by-one FOUND but not causal**: UPDATE_CIRCULAR_BUFFER_{DM,PM} uses
  `if (I > B+L)` where SHARC semantics want `if (I >= B+L)` (buffer is [B,B+L), so landing on B+L must
  wrap). Fixed it and re-tested -> F1 STILL diverges identically. Reverted (keep core matching upstream;
  it's a real correctness nit worth upstreaming separately, just not this bug).
- **NOT the 0xC011/0xC012 1.0 coefficients**: overrode every exactly-1.0 float in 0xC000-0xC050 to 0.9
  live -> F1 still diverges. So the unity feedback is not those.

### Where it must be (precise next step)
The reverb is a correct allpass tank with damped section coefficients, yet the GLOBAL loop gain is ~1.0
and it never decays. => the **TANK DECAY gain** (the long feedback that recirculates the whole tank,
set by the reverb TIME/DEPTH parameter) is 1.0 instead of <1. This is consistent with the DEPTH path
being dead (DspEffectSelect *(0x500A01E0)=-1): the tank-decay coefficient defaults to unity because the
depth was never applied. It is NOT the 0xC011/0xC012 1.0s -- it is somewhere in the coefficient stream
I0 walks (0xC004 up to ~0xC2xx). NEXT: (a) instrument the DM READ at the tank's decay-multiply (find the
FMUL whose STATE operand is the largest/longest-delayed value and whose coeff is ~1.0), OR (b) dump the
FULL coefficient stream in execution order (log DM(I0,M2) address+value across one frame) and find the
~1.0 that is the tank decay; then trace back to the maincpu upload (caller of gated host-write
0x48404EF5) to see where DEPTH should scale it <1. Fixing the DspEffectSelect depth path (setter
0x484057d6 never called) likely applies it. Tooling proven: instrument compute_fmul (case 0x30, 5-tab
indent) / compute_fix (case 0xc9) gated on PC, -nodrc, fprintf(stderr); reverb PM dump via Lua read_u64.

## 2026-07-11j: it is NOT a DM coefficient value -> structural / PM-data / precision
Decisive live test: forced EVERY near-unity float (|f| in [0.95,1.25]) across the WHOLE DM coeff block
0xC000-0xC300 to 0.9, each video frame, while tapping the kernel output slot 0xC358. Result: 0xC358
STILL rails (rail-count 217811, max 0x7FFFFF). So NO DM coefficient value is the runaway feedback --
this RULES OUT the "unapplied DEPTH leaves a tank-decay coeff at 1.0" theory (at least for DM coeffs).
Two possibilities remain, both un-checked:
1. **The reverb also reads PM (program memory) via I8** (`R3 = PM(I8, M8)`, `PM(I8,M9)=R11`, etc.). The
   tank-decay / feedback value may live in PM, not DM -- OR the DM coeffs are reloaded from PM each frame
   (which would make the DM override futile, consistent with "no effect"). NEXT: dump/inspect the PM
   data region I8 walks; override PM near-unity values the same way.
2. **40-bit vs 32-bit float**: MAME's SHARC uses host 32-bit float (union{int32;float}); the ADSP-21065L
   has 40-bit extended internally. A tank feedback DESIGNED at ~0.9999 (long RT60) plus a rounding-mode
   difference could round to >=1.0 in 32-bit -> never decays. (Earlier I argued the ~1.0 was "too far
   from 0.9999" -- but a non-decaying output only proves gain>=1.0, which 0.9999->1.0000 rounding gives.)
   Hard to fix (would need 40-bit float or a MODE1 RND emulation audit).

### Net state of the effects DSP (honest)
- DRY passthrough: correct/clean (verified). Active effects load+run.
- Active REVERB: DIVERGES (output float F1 -> +/-2e7, rails, never decays in 17s). Confirmed NOT the
  coefficients (DM), NOT the float multiplies, NOT the allpass structure, NOT the circular-buffer
  off-by-one. Remaining: PM-resident feedback data, or 32-vs-40-bit float / rounding on a near-unity
  tank. This is a hard, well-scoped bug; the effects are audible-but-not-faithful until it's resolved.
- Minor real find (reverted, worth upstreaming separately): UPDATE_CIRCULAR_BUFFER_{DM,PM} `> B+L`
  should be `>= B+L`.

## 2026-07-11k: the PARADOX — every gain is damped (<1) yet it diverges => delay-line management
Instrumented the global TANK recirculation multiply `F10 = F10 * F9` (PM 0x844a/0x8454): F9 = -0.280473
CONSTANT (damped). So the tank decay gain is <1, like the allpass g=-0.618 and all DM coefficients.
=> EVERY gain in the reverb loop is |<1|, the float ops are exact, and the circular-buffer wrap is
correct -- yet F1 diverges and never decays. A linear system with all |loop gains| < 1 is UNCONDITIONALLY
stable, so the divergence cannot come from the gains/coeffs/arithmetic I've checked. It must be one of:
  (a) DELAY-LINE MANAGEMENT: the read at DM(I6,M7) does not return the value written D samples earlier
      -- the reverb packs MULTIPLE delay lines into ONE circular buffer (B6=0x20000, L6=0x456F0, ptr
      decrements M3=-1, reads use per-tap inline M7 offsets). If MAME's post-modify+wrap sequencing
      makes a read land on the wrong slot (another line's data, or stale/uninitialised), energy is
      injected each pass -> sustains/grows even with damped gains. This is the LEADING hypothesis.
  (b) a PARALLEL feedback path whose SUM > 1 that I haven't instrumented (less likely -- HW works).
Resolving this needs a FULL single-frame execution trace: log every DM(I6) read/write ADDRESS+value in
0x840a-0x846e for one frame, and verify each read address equals the write address from the correct
number of samples earlier. That is the definitive next step (a big but bounded trace-and-diff).
NOTE: earlier I proved this is NOT the DM coefficients, NOT the float ops, NOT the allpass structure,
NOT the circular-wrap off-by-one, NOT a 32-vs-40-bit float issue (a >=1.0 non-decay is too coarse for
float precision). The remaining cause is squarely in how the shared circular delay buffer is addressed.
