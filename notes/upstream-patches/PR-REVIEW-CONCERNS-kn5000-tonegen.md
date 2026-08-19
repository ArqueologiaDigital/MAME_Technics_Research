# KN5000 tone generator PR -- things to address before submission

Branch: `kn5000_minimal_tonegen` in `~/compartilhado/mame-pr-tonegen` (3 commits off upstream/master).
Written 2026-08-19. Tick items off here as they are done, and re-run the verification after each one:
the 4141-gate / RMS 1361 measurement depends on several of these code paths.

## Tier 1 -- likely to block the PR

- [ ] **1. The generated pitch table** (`kn5000_pitch_trim.hxx`, 1509 lines).
  ROM-derived data checked into the source tree, when the machine already loads that same ROM at
  runtime. Two objections: copyright, and "why is this not computed?".
  **Plan:** derive it at start-up from the sub-CPU program region instead, with the DRIVER doing the
  descriptor walk and handing the result to the device (keeps the sound device from reaching into
  another chip's ROM). Deletes ~1500 lines and adapts to whichever BIOS is selected.
  **Also:** find out what the numbers actually MEAN -- whether they reduce to something structural
  (root note + a small correction) that needs neither a table nor a ROM walk.

- [ ] **2. The synthesized sine.** The machine emits a timbre the hardware never produced. MAME's
  norm is silence when data is missing. **Plan:** restructure so PCM is the real path and the
  oscillator is the documented fallback while IC304-306 are NO_DUMP; consider asking upstream in an
  issue first, before writing the PR twice.

- [ ] **3. Scheduler manipulation in the latch handlers.**
  - [ ] `perfect_quantum()` per write -> declare once in machine_config via `config.set_perfect_quantum()`.
  - [ ] `abort_timeslice()` -- probably redundant (generic_latch::write already synchronizes). MEASURE
        whether removing it changes the gate count; drop it if not.
  - [ ] `acknowledge_w(0)` before `write()` -- papers over generic_latch's change-only callback from
        outside. **Plan:** stop using generic_latch_8_device for IC22/IC23; implement the pair in the
        driver as a u8 plus an explicit /INT0 pulse per write, which states the hardware claim honestly.

## Tier 2 -- will draw comments; cheap

- [ ] **4. Note-off heuristic** (`case 0x0900`, 1 ms wall-clock guard). Put the measurement that
      justifies 1 ms in the comment, or decode the register properly.
- [x] **5. Hand-off mute** -- FIXED 2026-08-19, and it was a real defect rather than a caveat to
      document. F000 is the PERCUSSION hand-off (83.1% of class-5 hand-offs, ~0% elsewhere; that
      class plays at a single fixed pitch), so muting on a zero low byte silenced the drum kit. The
      firmware frees those voices itself, 457/457, so the mute was not protecting the allocator.
      Removed; SINE_PEAK cut 3 dB for headroom. Gates 4141 unchanged, rms 1361/1243 -> 4295/5017,
      clipping 0.21% -> 0.01%. Evidence: tools/kn5000-rootpitch/handoff_probe.py.
- [ ] **6. `SILENT_HOLDOFF = 4720`** encodes the firmware's bank-poll period into the chip model.
      Re-express as a time (~100 ms of inaudibility) justified as a decay threshold.
- [ ] **7. Performance:** lambda constructed inside the per-sample loop; doubles throughout; two
      `std::tanh` per output sample at 48 kHz x 64 voices. Hoist, use floats, cheaper clip curve.
- [ ] **8. `int const ch = int(&v - m_voice);`** -- pointer arithmetic to recover a loop index.
- [ ] **9. `STREAM_RATE = 48000` hardcoded** while the device is instantiated with clock 0 and the
      real converters run at 44.1 kHz. Either derive from the clock or document why not.
- [ ] **10. Calibrated-by-ear constants** (EG rate law D = 4.0 and T127 = 0.0034, SINE_PEAK = 16384,
      soft-clip knee 0.85). Already labelled; expect to be asked to justify or derive them.

## Administrative

- [ ] PR description written, including the mandatory AI-disclosure paragraph naming model and
      version (draft: `notes/upstream-patches/PR-DRAFT-kn5000-tonegen.md`).
- [ ] Decide: one PR with all three commits, or split the tmp94c241 fix out on its own.
- [ ] Felipe to listen to `~/compartilhado/kn5000-demo-tonegen-sine.wav` and judge whether the NOTES
      are right (the timbre is deliberately not the instrument's).

## Verification to re-run after each change

    cd ~/compartilhado/mame-pr-tonegen && ./build_kn5000.sh
    DEMO_PRESS_AT=40 ./kn5000 kn5000 -rompath ~/compartilhado/kn7000-emulator/roms-upstream \
      -window -nothrottle -skip_gameinfo -seconds_to_run 140 -wavwrite /tmp/v.wav \
      -autoboot_delay 1 -autoboot_script ~/compartilhado/kn7000_mame/tools/rigs/kn5000_tg_writes.lua
    python3 ~/compartilhado/kn7000_mame/tools/wav_rms.py /tmp/v.wav --window 5 --from 55 --to 135 --min-rms 200

PASS = 4141 note-on gates across all four banks, and every window above threshold.

---

## Added 2026-08-19, from the register census

- [ ] **11. The envelope has FOUR segments and the advance rule is wrong.**
  `+0x8C0` is a fourth EG word in the same `(target << 8) | rate` format, written at the gate.
  Measured over 1641 demo notes: 65 use it, and their shape is unambiguous --
  `seg0 897F` (attack) / `seg1 FF00` / `seg2 4E00` (hold at a sustain level) / `seg3 00D4`
  (**decay to zero**). The other 1576 have `seg3 = 0000` and do the decay in seg2 (`427F`).
  The decode is now implemented (four segments, advance while `eg_seg < 3`).

  **But it is INERT, and that exposes a deeper problem.** Segments advance when the level reaches
  the target, and rate 0 means hold. Nearly every note programs `seg1 = FF00` -- target 0xFF at
  rate 0 -- so the envelope rises to seg0's target, loads seg1, cannot move with a zero step, and
  PARKS THERE FOR THE WHOLE NOTE. Segments 2 and 3 are never reached by any note in the capture.
  Adding the fourth segment changed the 140 s demo render bit-for-bit not at all.

  So one of these is false, and the bus cannot say which:
  * rate 0 means "hold" (the current model, inherited from the reference implementation);
  * the advance is level-triggered rather than timed;
  * `0000` means "segment unused" and the envelope stops at the last programmed one.

  Whichever it is, the current model sustains every note at its attack target instead of following
  the programmed contour, which is a bigger inaccuracy than the missing fourth segment was.
  Evidence: `tools/kn5000-rootpitch/` capture analysis; the shapes are in this file's history.
