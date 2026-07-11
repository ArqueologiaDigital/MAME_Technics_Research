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
