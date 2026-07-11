# Effects DSP — the full "selecting an effect doesn't change the sound" chain (2026-07-11)

Felipe: effects processing should work well — selecting a reverb/chorus in the sound menus
should audibly change the sound. It didn't. This note traces the ENTIRE dependency chain,
which turned out to be five stacked problems. Four are now fixed; the fifth (effect output = 0)
is the remaining blocker.

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

### 5. The effect executes but OUTPUTS ZERO — the remaining blocker (OPEN)
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

**ROOT CAUSE IDENTIFIED (2026-07-11): the unmodelled SPORT autobuffer DMA.** Scanning ALL DM
writes in 0xC000-0xFFFF while a Dark2 reverb ran showed the effect DOES write output -- to
**0xC2BD/0xC2BE** (a small L/R pair, 132248/132239) plus float processing state at 0xC058-0xC1D2 --
but it writes NOTHING to **0xC350**, where `dsp_audio_tick` reads (`obuf = sport_tx_buffer(0,0)+0xE`).
The bridge's "kernel writes to a FIXED position each IRQ0" assumption only holds for the passthrough;
a real effect relocates its output because the SPORT TX autobuffer DMA index (which the emulator
does NOT advance -- see the dsp_audio_tick comment) determines the write position. So:
  THE FIX = model the ADSP-21065L SPORT0/1 transmit+receive AUTOBUFFER DMA so the kernel's per-frame
  output lands at a position the bridge tracks (or read back the live SPORT DMA pointer each frame
  instead of the fixed TX0+0xE). IOP regs for the buffer pointers: 0x73/0x53 = SPORT0 TX A/B,
  0x7B/0x5B = SPORT1 TX A/B, 0x63/0x33 = SPORT0 RX A/B, 0x6B/0x3B = SPORT1 RX A/B (sharc.cpp
  iop65l_r/w). This is the same "runtime-derived SPORT buffers" stopgap the memory notes mention;
  it needs to become a real autobuffer model for effects to be audible. Substantial, own sub-project.

Other hypotheses now demoted (the SPORT-DMA one above is primary):
  a. (was output routing -- CONFIRMED as the SPORT-DMA issue above)
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
