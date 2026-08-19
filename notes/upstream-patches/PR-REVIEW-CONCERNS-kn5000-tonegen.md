# KN5000 tone generator PR -- things to address before submission

Branch: `kn5000_minimal_tonegen` in `~/compartilhado/mame-pr-tonegen` (3 commits off upstream/master).
Written 2026-08-19. Tick items off here as they are done, and re-run the verification after each one:
the 4141-gate / RMS 1361 measurement depends on several of these code paths.

## Tier 1 -- likely to block the PR

- [x] **1. The generated pitch table** -- DONE 2026-08-19. `kn5000_pitch_trim.hxx` deleted from both
  trees. The driver walks the firmware's multisample SET descriptors in the `table_data` mask ROM at
  `machine_start()` and hands the constants to the device, so nothing firmware-derived is checked in
  and the table follows whichever firmware revision is running. The walk also honours the flags
  bit-1 rule the generated table missed, correcting 112 of 1444 selectors that carried a fabricated
  +49..+65 semitone offset; ambiguous selectors drop 77 -> 68. Verified: 1444 constants from 487
  descriptors, checksum identical to the reference walker, boot silent, demo 4141 gates.
  PR diff fell from 2092 to 824 insertions. Revert tags: `pre-romwalk-2026-08-19` (PR),
  `pre-romwalk-overlay-2026-08-19` (overlay).
  ⚠ FOLLOW-UP: the audit tooling (`kn5000_pitch_audit.py`, `gen_kn5000_pitch_trim.py`, the oracle
  scripts) still reads the old tsv/hxx and therefore describes the PRE-FIX table. It will disagree
  with the emulator on those 112 selectors until it is repointed at the walk.

- [ ] **2. The synthesized sine.** The machine emits a timbre the hardware never produced. MAME's
  norm is silence when data is missing. **Plan:** restructure so PCM is the real path and the
  oscillator is the documented fallback while IC304-306 are NO_DUMP; consider asking upstream in an
  issue first, before writing the PR twice.

- [~] **3. Scheduler manipulation in the latch handlers** -- PARTLY DONE 2026-08-19.
  - [x] `abort_timeslice()` -- REMOVED. Measured: dropping both calls left the demo capture
        bit-identical (4141 gates, same latch totals, same rms), so it was a no-op. generic_latch's
        write already synchronizes.
  - [x] `perfect_quantum()` per write -- KEPT, and now justified in the source. The idiomatic
        `config.set_perfect_quantum(m_maincpu)` is NOT equivalent: measured over the demo it lets
        the link wedge twice and loses 47% of the note-ons (4141 -> 2215, count frozen for the last
        20 s). A reviewer asking "why not the normal way?" now gets a number.
  - [ ] `acknowledge_w(0)` before `write()` -- ATTEMPTED AND REVERTED. Replacing IC22/IC23 with a
        plain byte pair plus explicit `/INT0` assertion killed the link outright: 65 gates, silence.
        What that established, which is useful for the PR discussion:
          * `set_input_line()` acts only on a CHANGE, so "every write asserts" is silent after the
            first byte -- the line is already high.
          * `clear_int0_level()` and `set_input_line(CLEAR_LINE)` are not interchangeable: one
            retires the CPU's internal flag immediately, the other updates the line state that
            change-detection reads.
          * doing BOTH on read still did not work, so generic_latch's `synchronize()` ordering is
            doing something a direct model does not reproduce.
        So the existing code is not merely a workaround -- it depends on ordering semantics that are
        not trivially replaceable. Revisit only with a reason better than style.

## Tier 2 -- will draw comments; cheap

- [ ] **4. Note-off heuristic** (`case 0x0900`, 1 ms wall-clock guard). Put the measurement that
      justifies 1 ms in the comment, or decode the register properly.
- [x] **5. Hand-off mute** -- FIXED 2026-08-19, and it was a real defect rather than a caveat to
      document. F000 is the PERCUSSION hand-off (83.1% of class-5 hand-offs, ~0% elsewhere; that
      class plays at a single fixed pitch), so muting on a zero low byte silenced the drum kit. The
      firmware frees those voices itself, 457/457, so the mute was not protecting the allocator.
      Removed; SINE_PEAK cut 3 dB for headroom. Gates 4141 unchanged, rms 1361/1243 -> 4295/5017,
      clipping 0.21% -> 0.01%. Evidence: tools/kn5000-rootpitch/handoff_probe.py.
- [~] **6. `SILENT_HOLDOFF = 4720`** -- CANNOT be made principled without fixing the underlying
      race. Re-expressing it as STREAM_RATE/10 (100 ms) STALLS the demo: note-ons fall 4141 -> 2796
      and freeze at t=121. Freeing a voice at a different moment changes what the allocator sees,
      which shifts firmware timing, which trips the inter-CPU link race. Value kept at 4720 with
      that measurement in the source. Revisit when the race itself is understood.
- [x] **7. Performance** -- DONE 2026-08-19, partly by measuring rather than changing. The lambda
      is hoisted and the voice loop indexed (demo capture bit-identical, so provably a pure
      refactor). The doubles and `tanh` STAY: measured cost of the whole device is 1.65 percentage
      points of emulation speed (82.34% with sound, 83.99% with -sound none, same 140 s demo), so
      trading exactness for a fraction of 2% is a bad deal.
- [x] **8.** Pointer arithmetic for the loop index -- DONE, the loop is indexed.
- [x] **9. `STREAM_RATE`** -- DONE. The header now states that IC303's clock is not established,
      that the device is instantiated with clock 0, that the converters run at 44.1 kHz, and that
      this should become a function of the clock once it is known. RELEASE_SAMPLES is expressed
      against it so it keeps its meaning.
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

- [x] **11. The envelope** -- DONE 2026-08-19, both halves.
  `+0x8C0` is a fourth EG word in the same `(target << 8) | rate` format; 65 of 1641 demo notes use
  it to decay to zero while segment 2 holds a sustain level.

  The advance rule was also wrong, and that mattered more. Reading rate 0 as a HOLD parked every
  note at its attack target -- segments 2 and 3 were unreachable on every note in the capture, and
  adding the fourth segment changed the render bit-for-bit not at all.

  Resolved in favour of: **rate 0 means jump to the target now, and an all-zero word is an unused
  segment the envelope stops at.** The argument is the firmware's own behaviour rather than taste:
  the allocator reads each voice's envelope level back through status_r and tests
  `(V & 0x3FFF) >> 5` against `0x80`. A note parked at its attack target (~0xCC) can never satisfy
  that test, so under the old reading the firmware was polling for a condition its own envelope
  shape made impossible. Under the new one the note decays to ~0x42 and crosses it.

  NOT verified against hardware -- the discriminator is internal consistency, not a measurement of
  the instrument. Demo: 4141 gates, no stall, rms 946/853 -> 936/805 (the decay that was missing).

---

## ⚠ About the "4141 note-on gates" figure

It is a signal, not an invariant. Measured values across builds this session: 4141, 4363 (with
-sound none), 2796 (with SILENT_HOLDOFF rounded to 4800). The demo's completion is timing-fragile,
and changes with no musical meaning can move it. QUOTE IT AS A RANGE, and treat the real failure
criterion as the STALL -- a gate count that freezes and never advances again -- rather than any
particular total.
