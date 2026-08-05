# KN5000 sine oracle — an independent check on demo-song playback

Renders the Feature Demo's own MIDI (preset 18) with **pure sine waves only** — no PCM, no
samples, no soundfont — and cross-correlates it against a capture of the emulator, to test
tempo, timing and absolute pitch independently of the tone generator's sample path.

`findings.md` is the standing result. Read it before running anything: it records what this
oracle CAN and CANNOT judge, and it contains one retraction worth understanding.

## Why it is trustworthy

Everything is scored against a **null built exactly like the measurement**, at a **fixed
alignment** (with the alignment free to re-optimise, a pitch-permuted null nearly ties the real
score — which is how the first version of this oracle fooled itself).

Three nulls: NULL-T displaces note times (kills timing, keeps pitch); NULL-P permutes pitches
(kills pitch, keeps the pitch histogram and timing); NULL-F is flat surface occupancy.
A **positive control** — scoring our own render against itself — pins the detector's own
contribution: 0.780 hit@0 vs 0.297 NULL-P, z = +66.

## Established (full-song run, 112 s of music, 3 captures)

* **Tempo 90.000 bpm**, half-height width 0.50 bpm. Confirms `--bpm 90` to +/-0.25.
* **Timing is correct**: 1.8-2.6x NULL-T at z = +15..+22.
* **Absolute pitch carries essentially no information**: hit@0 - NULL-P = +0.003, where the
  control is +0.483 = 0.6% recovery. Same in PCM mode, so it is not the renderer.
* The emulator is **~13 semitones (an octave) high**; the stuck-voice chord after t~100 s reads
  out exact semitone intervals **uniformly +35 cents**.
* **No time or register structure** — 40 cells, |z| <= 2.65 throughout.

⚠ RETRACTED from the first run: "Parts 7 and 11 are at the correct absolute pitch." That used a
null which displaced TIME only and so did not control for REGISTER. It was a 243-note artefact.

## What it can catch

Tempo/clock regressions; timing and scheduling regressions; note-presence regressions; and it
is a ready-made POSITIVE TEST for a future pitch fix — recovery should climb from 0.6% toward
the control's ceiling and a spike should appear at shift 0.

It CANNOT judge drum-part pitch (a drum note number is a kit key, not a frequency — exclude
Part 15, 39% of the notes), absolute pitch on PCM captures (the analysis locks onto harmonics —
the best PCM shift is +19 = the third harmonic), notes that restart an already-sounding pitch
(23% detector recall — physical, two identical sines give no onset cue), or anything about
timbre, envelope, effects or mix.

## Running it

Capture with a PRIVATE `-cfg_directory` and verify the render mode by reading the port back
every second — `ioport_field:set_value()` TOGGLES a PORT_CONFNAME field rather than assigning,
and MAME persists it. `oracle_long.lua` drives the demo.

    python3 analyse_capture.py <capture.wav> <t0> <t1> spec.npz
    python3 long_search.py      # recover (tempo, offset) exhaustively by FFT
    python3 long_eval.py        # scores + nulls at the fixed alignment
    python3 zone_scan.py        # time/register cells, each with an in-cell null

`render_sine.py` builds the reference. `midiparse.py` is a dependency-free SMF reader (no mido,
scipy or librosa anywhere). `audio.py` is the semitone filterbank and onset detector.

⚠ `corr_surface` evaluates non-negative lags only, so a beat-0 earlier than the window start is
unreachable; `long_search.py` re-origins the beats on the first note to avoid it.

Large WAV deliverables (renders and A/B files) are NOT committed — regenerate with
`render_sine.py` and `make_ab.py`.
