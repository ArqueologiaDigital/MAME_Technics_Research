# TODO — attribute the KN5000 PCM playback glitches to specific voices

Parked 2026-08-05. Written while the evidence was fresh; pick this up when we return to
debugging **PCM** playback. Right now the focus is the sine mode instead.

## What we already know (measured, not assumed)

Feature Demo, DSP compiled out, ROM de-scramble in place, `-seconds_to_run 70`:

* Audio runs ~26 s to ~57 s. Watchdog `00` and transport `04` throughout — sequencing is fine.
* Of 948 click-like steps (`|x[n]-x[n-1]| > 8000`) across 31 s, **893 fall inside 200 ms**:

  | window | L rms | R rms | R clicks | R clipping |
  |---|---|---|---|---|
  | 30.00–30.10 | 3381 | 252 | 0 | 0.000% |
  | **30.10–30.20** | 2406 | **11865** | **385** | **0.229%** |
  | **30.20–30.30** | 1606 | **16026** | **508** | **2.562%** |
  | 30.30–30.40 | 1235 | 5.9 | 0 | 0.000% |

* So: a ~200 ms full-scale noise burst, **right channel only**, RMS up ~50×, then both
  channels drop to near-silence for ~0.5 s. Outside it, 0–11 clicks/s (ordinary attacks).
* **The same passage in SINE mode has ZERO clicks** at comparable loudness (fair window
  26–38 s: PCM 675 L / 925 R, sine 0 / 0). Envelope, pitch, panning, mixer and allocation
  are the same code in both modes, so the defect is in the **PCM sample path** — the data,
  its addressing, the loop points, or the interpolation.

Hard-panned + noise-like + clipping is the signature of ONE voice reading garbage, not of a
systemic mixing fault.

## The prime suspect, stated up front

**The sustain loops are ours, not the ROM's.** `kn5000_tonegen.cpp` says the ROM stores no
loop points and `compute_loop()` derives one per chunk. A derived loop whose length is not a
whole number of periods, or whose endpoints straddle a chunk boundary, splices unrelated
audio at every wrap — which is exactly what hundreds of clicks in 200 ms looks like
(a loop only a few hundred samples long wraps ~hundreds of times in 200 ms).

Second suspect: **chunk-extent overrun.** `pcm_samples` is computed as "distance to the next
higher `wave_offset` in the directory". Any chunk whose real recording is shorter than that
gap plays into whatever follows it.

Third: **the substituted banks.** IC304-306 are `BAD_DUMP` copies of IC307, and
`kn5000.cpp` notes ~75% of sounds select them. A chunk index valid on one page can be out of
range or point at an unrelated recording on the substituted one.

## Method

### 1. Attribute each click to a voice

Add a temporary `LOG_GLITCH` mask to `kn5000_tonegen.cpp`. In `sound_stream_update()`, keep
the previous per-voice contribution and, when `|contribution[n] - contribution[n-1]|` exceeds
a threshold (start at 4000), log one line:

```
t, ch, bank/page/chunk, wave_real, wave_start, wave_samples, loop_start, loop_end,
wave_offset before and after, pitch_step, env_level, eg_level, volume_l, volume_r,
s0, s1, and whether the loop wrap fired on this sample
```

Measure the PER-VOICE contribution, not the mix: a click in the sum can be two voices
crossing. Filter to `volume_r >> volume_l` to isolate the burst's owner.

### 2. Classify the cause

Each logged click should fall into exactly one bucket:

| bucket | test |
|---|---|
| loop seam | the wrap fired on this sample — compare `s[loop_end-1]` against `s[loop_start]` |
| chunk overrun | `sample_pos >= wave_samples`, i.e. the safety clamp engaged |
| bad geometry | `wave_samples == 0`, `loop_end == 0`, `loop_start >= loop_end`, or `wave_start + wave_samples*2` outside the chunk's directory extent |
| substituted bank | `wave_real == false` |
| pitch | `pitch_step` large enough to alias (say > 4×) |
| gain step | the source samples are continuous but `env_level`/`eg_level` jumped — a machinery bug after all, and the sine A/B says this should be empty |

### 3. Cross-check statically, no emulator

`parse_page_directories()` already yields every chunk's `[pcm_start, pcm_start + samples*2)`.
Offline, for all 1495 chunks of IC307:

* Does `compute_loop()`'s derived loop produce a discontinuity at the seam? Compute
  `|s[loop_end-1] - s[loop_start]|` and compare against the null of ordinary steps inside the
  same chunk. Rank the worst chunks and check whether the demo's voices are among them.
* Does any chunk's declared extent run past where its own recording actually ends (a long run
  of near-silence before the next chunk, or a discontinuity at `pcm_start + samples*2`)?

This is cheap, needs no run, and — if the loop hypothesis is right — should find the guilty
chunks before any instrumentation is written.

### 4. Confirm the null

Run the same instrumentation over (a) a quiet passage and (b) sine mode. Sine mode has zero
clicks by measurement, so the instrument must fire zero times there. If it fires, the
detector is wrong and every number above it is worthless.

## Pitfalls

* **Compare per-voice, not the mix.** Two clean voices can sum to a step.
* `-seconds_to_run N`, never a wall-clock `timeout`, or two runs end at different machine
  times and diverge for no reason. Verified: the emulator is bit-deterministic run to run.
* Delete `nvram/kn5000/nvram1` before every run — the driver persists 1 MB of work DRAM as
  NVRAM and a stale one changes behaviour.
* The burst is at a fixed machine time only because the whole run is deterministic; any
  change to the driver moves it. Re-locate it after each rebuild rather than trusting 30.1 s.
* Clipping and clicks are different faults. Sine mode also clipped 375 samples in the fair
  window while producing zero clicks, so clipping alone is a level problem, not a data one.
