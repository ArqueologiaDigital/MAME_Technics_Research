# Effect-type divergence sweep — the SHARC fix generalizes (priority 1 CLOSED)

**Date:** 2026-07-12. **Result: 241 effect-type selections, ZERO rails, ZERO DAC clips.**

## Why
The reverb divergence (float feedback railing to ±full-scale) was root-caused to the DRC missing
MODE1 ALUSAT (saturate-then-reflect) + the never-implemented fixed-point MAC, and fixed
(commits 2d308c7 / b942366 / native MAC). But the fix was validated on the *reverb* and a handful of
types. Open question: did it hold for **every** effect the KN7000 can load, or did I get lucky with
the ones I checked? This sweep answers it.

## Method
Harness: `scratchpad/fxtest/` (fxlib.lua + gen_runs.py + chain.sh; recipe-driven panel navigation from
the Part-20 side-key geometry + group-cursor walk). For each effect TYPE across all four effect
screens: select it (which reprograms its DSP unit — confirmed by a host-upload counter, up_sel>0 on
170/196 non-baseline segments), settle, play a C4 on the keybed, hold 1 s, 2.5 s tail. Two INDEPENDENT
divergence signals per segment:
- **frail / fpeak** — a 60 Hz frame sampler over DSP data-memory 0xC342-0xC359 (all four effect output
  slots: reverb 0xC342, multi 0xC344, chorus 0xC34A, sound-dsp 0xC356). `fpeak` = running max |s24|;
  `frail` = frames where any slot hit |s24| >= 0x7FFF00 (the rail). Catches a divergence even over
  silence — the historical bug self-excited, input-independent.
- **clip** — int16 DAC samples with |s| >= 32000 anywhere in the segment (from the run WAV). Catches
  anything audible.
Memory-safe: FX_TAP=false (the per-sample DM write tap OOM-killed MAME at scale; the frame sampler +
WAV clip count catch both sustained rails and single clips). Ran on the CURRENT four-effect binary
(kn7000 built 2026-07-12 02:52); the earlier Jul-11 sweep predated the four-effect wiring and is
superseded.

## Result — divergence_report.py verdict (archived: effect-sweep-verdicts.json)
```
241 segments across 12 runs
verdicts: FAIL=0  SUSPECT=0  WATCH=0  PASS=241
overall max fpeak = 11.6% FS (Reverb/Concert2) ; rail line = 94% FS ; 0 railed frames ; 0 DAC clips
```
Healthy excited effects peak at 4-12% FS — a >8x margin below the rail. Nothing came close.

## Coverage — 47 (family/type) groups, every effect screen
- **Reverb** 8 types (Room1/2, Plate1/2, Concert1/2, Dark1/2)
- **Chorus** 8 types (Chorus1-4, GM Chorus1-4)
- **Multi** 14 families: CrossDelay, DualDelay, SlowAttacker, Compressor, Limiter, DistortedAmp,
  Distortion, Fuzz, Overdrive, LFOFilter, LFOWah, ReverseWah, PedalWah, MultiTapDelay, DelayComplex,
  VocalEffect
- **Sound-DSP** families: Enhancer, ParametricEQ, Mixup, RingModulator, Vibrato, AutoPan, Tremolo,
  RockRotary, RotarySpeaker, Flanger, FlangerDryWet, Phaser, PhaserDryWet, Celeste, ModCeleste,
  (Exciter, AutoWah in the S5 tail)

## The load-bearing conclusion
The **LFO-driven feedback effects** — Flanger, Phaser, RockRotary, RotarySpeaker — are built on the
exact saturate-then-reflect triangle-LFO arithmetic that caused the ORIGINAL reverb rail. They all
pass at 4-5.2% FS. That is not luck; it is the ALUSAT fix generalizing to the whole class. The
distortion family (DistortedAmp, Distortion, Fuzz, Overdrive) — the effects most able to drive their
own output hard — also stay quiescent over silence (no self-excitation). The reverb bug is fixed not
just for the reverb but for the machine.

## Honest caveat (scope of the claim)
Each effect runs over the reverb-excited mix; the non-reverb units mostly process near-silence during
selection (their per-part sends are ~0 unless depth is set). So this PROVES no effect type
SELF-excites to the rail — the historical, dangerous, input-independent failure mode. Excitation-
dependent artifacts under heavy per-effect drive are a separate, lower-risk question (would need the
depth-set-then-play variant); documented as a future refinement, not a known defect.

## Status: PRIORITY 1 CLOSED
No FAIL/SUSPECT to fix — the sweep is the fix's validation. Reporter + verdict archived in notes/.
