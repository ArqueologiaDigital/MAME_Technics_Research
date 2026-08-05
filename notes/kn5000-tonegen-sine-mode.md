# KN5000 tone generator: diagnostic sine render mode (2026-08-05)

`TGMODE` bit 0, live from the MAME menu (Machine Configuration):
`0 = PCM from wave ROM (normal)`, `1 = Sine test tone (no wave ROM PCM)`.

## What it is

A second way to produce a voice's RAW SAMPLE, and nothing else. The two modes differ at
exactly one `if` in `sound_stream_update()`; note on/off, voice allocation, pitch tracking,
the amplitude EG, the TVF, panning, the mixer and the R2s silence interlock are literally the
same code. That is what makes the A/B mean something.

* The sine has its own **Q32 phase accumulator**, not `wave_offset` — that has only 16
  integer bits and is re-based by the loop wrap, so it cannot free-run as a phase.
* Its increment comes from the **absolute frequency** `update_pitch()` already computes.
  `pitch_step` is a CHUNK-RELATIVE resampling ratio (`freq * pitch_period_q16 / 48000`), so
  reusing it would give the wrong note, differently wrong per instrument. `update_pitch()`
  now computes that frequency before its early returns; `pitch_step` itself is untouched.
* `SINE_PEAK = 16384` matches the wave ROM's typical **RMS**, not its peak: the PCM is
  peak-normalised (median chunk peak 32713) with a 5.38 dB median crest factor.

## Regression gate

PCM output is **bit-identical** before and after the change: same binary options,
`-seconds_to_run 70`, 20,160,006 audio bytes, zero differing. Two runs of one binary are also
bit-identical, so the emulator is deterministic and the comparison is meaningful.
⚠ Do NOT compare two runs that were bounded by wall-clock `timeout` instead of
`-seconds_to_run` — they end at different machine times and diverge harmlessly.

## First result (KN5000 Feature Demo)

Fair window 26-38 s, where both modes are producing audio at comparable level:

| mode | L rms | R rms | L clicks (step > 8000) | R clicks |
|---|---|---|---|---|
| PCM  | 1131 | 1871 | **675** | **925** |
| SINE | 1201 | 2226 | **0** | **0** |

Same envelopes, same pitches, same mixer, same voice allocation up to this point — and the
discontinuities vanish completely. **The glitches come from the PCM sample path (data,
addressing, loop points or interpolation), not from the machinery around it.**

## Known limitation, foreseen by design

After ~t=40 s the demo goes quiet in SINE mode while PCM keeps playing (a steady ~6 rms
residual = one held voice). This is the predicted voice-allocation divergence: voices whose
PCM probe finds silence are skipped in PCM mode and get `eg_running` cleared, but they SOUND
in sine mode, so the silence interlock holds `eg_running` set — and `eg_running` is what
`status_r()` reports back to the firmware's voice manager. **A sine-mode capture is a
faithful proxy for the pitch/envelope/mix machinery, NOT for voice allocation.** Use the
window where both modes are active.

## Not settled

* Absolute pitch for voices with `true_note < 0` (demo / rhythm / sequencer) rests on the
  `0x3524` reg[8] anchor, which is a convenience rather than a measurement — the per-chunk
  root pitch is undecoded. Those sines may be octaves off. Only keybed/MIDI notes
  (`true_note >= 0`) give a trustworthy absolute Hz.
* `pitch_offset` still comes from `resolve_note_group()`, which is gated on the wave-ROM
  directory, so sine pitch is not totally ROM-independent.
