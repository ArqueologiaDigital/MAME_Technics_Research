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

---

# RESULT 2026-08-06 — the plan was carried out. Two causes, and a correction to the method

Everything above is the plan as written on 2026-08-05 and is left intact. What follows is what
the measurements said. **The lead hypothesis (derived sustain loops) is REFUTED.**

Vehicle: current tree (post `3fd44f3`), DSP compiled out, `-seconds_to_run 80`, AREA = 2 from a
private cfg, `TGMODE` read back every 5 s and printed (PCM run reads 0, sine run reads 1).
The Feature Demo is entered by three panel presses at t = 20 / 21.8 / 23.6.

## 0. Re-measurement first: the burst SURVIVED 3fd44f3, in the same place

| | L clicks | R clicks | where |
|---|---|---|---|
| **PCM** | 814 | 956 | 895 of the 956 R clicks are inside **30.16–30.29 s** |
| **SINE** | **0** | **0** | — |

The burst is still a right-channel-only, near-full-scale noise event: R rms rises from 14 to
26 137 over ~130 ms, peaks pinned at 32 767, then both channels fall to silence. Same 200 ms
neighbourhood as the pre-3fd44f3 measurement, so nothing moved.

## 1. The instrumentation, and its own null

`LOG_GLITCH` (VERBOSE bit 7) watches each voice's OWN post-pan contribution and accumulates a
**per-chunk census** printed once at `device_stop`; `LOG_GLITCHEV` (bit 9) adds one line per
event; `LOG_WINDOW` (bit 8) dumps every output sample over one window. All default OFF.

Three gates were run before any number below was believed:

* **Non-perturbing.** PCM audio is bit-identical with and without the instrumentation
  (3 840 001 frames, `cmp` clean), and identical again across a further two runs.
* **The wav IS the device.** The `LOG_WINDOW` dump over 30.10–30.32 s is **10 560 consecutive
  samples, 100 % identical to the capture, at zero offset** (max |diff| 1 LSB on R, rounding).
  So `stream.start_time()` is exact and the capture carries no resampler, effect or latency.
  MAME's default `Filters`/`Compressor`/`Reverb`/`Equalizer` chain is present but every one of
  them is `mode == 0` = a straight `copy()`.
* **In-device count == capture count.** The device counted **1716** mix clicks (>8000); the
  capture has 1716 sample positions where L or R steps by >8000. Exact.

⚠ **METHOD TRAP, cost ~1 h.** `LOG_GLITCHEV` output is LOST on a long run: an 80 s run kept
289 of the burst's events, the identical 32 s run kept all 2804 — a uniform ~1-in-6.5 survival,
same ratio for both detectors, with the audio bit-identical. Anything counted from a per-event
log over a long run is an undercount. That is why the census exists.

## 2. Where the clicks come from (per-voice, threshold 4000, whole 80 s, census)

**6794 events. Three chunks are 94.3 % of them.**

| chunk | events | real? | N | P | P==N | max step | wraps | clamps |
|---|---|---|---|---|---|---|---|---|
| b0 p0 c155 | 2778 (40.9 %) | **0** | 2816 | 0 | no | 1.00× | 0 | 0 |
| b0 p1 c35  | 2171 (32.0 %) | **0** | 1496 | 1496 | **yes** | **33.30×** | 4 | 0 |
| b1 p0 c157 | 1459 (21.5 %) | 1 | 352 | 352 | **yes** | 5.15× | 0 | 0 |
| 15 others  | 386 (5.7 %) | | | | | | 9 | 0 |

Against the plan's cause table:

| bucket | verdict |
|---|---|
| **loop seam** | **REFUTED — 13 of 6794 events (0.19 %) had the wrap firing on that sample.** The static pass agrees: over all 1495 IC307 chunks the derived seam step is a **median 0.68×** the 99th-percentile ordinary step inside the same loop, i.e. typically SMALLER than the audio already there. |
| **chunk overrun** | **REFUTED — the safety clamp engaged 0 times in 80 s.** |
| **bad geometry** | none: no `N == 0`, no `loop_end == 0`, no `loop_start >= loop_end`, and 0 chunks of 1495 exceed the 16.16 position range. |
| **substituted bank** | 78.4 % of events are on `wave_real == 0`. **A correlate, not a mechanism** — it decides WHICH recording is read, not whether reading it clicks (b1p0c157 is on the real IC307 dump and is 21.5 % of the events). |
| **pitch aliasing** | 55.0 % of events come from chunks whose resampling ratio exceeds 4×. See §4. |
| **gain step** | none observed. |

## 3. The 130 ms right-channel burst = v50 + v51 on b0 p0 c155, and it is NOT a render defect

`LOG_WINDOW` blames each of the 895 clicks on the voice whose own contribution moved most:
**894 of 895 (99.9 %) are voice 50 or voice 51**, both on `b0 p0 c155`, `vol = 0/32767`
(hard right — which is why the burst is one channel), `env = 255`, `eg = 249 → gain 0.771`.

Its geometry says the render did nothing wrong: `P = 0` (correctly detected as aperiodic),
`pitch_step = 1.00×` (played exactly as recorded), `wrap = 0`, `clamp = 0`. **The chunk itself
is noise**: zero-crossing rate 0.369, median adjacent-sample step 3087, max 51 831, peak 29 803,
and a flat rms (~6000) across all eight eighths, i.e. a sustained noise waveform meant to loop,
not a one-shot. 2816 samples = 58.7 ms, so the ~130 ms burst is it looping about twice.

**And SINE MODE HAS THE SAME BURST** — R rms 24 497 vs PCM's 26 137 over the same 10 ms grid,
same onset, same decay, and **zero clicks**. So the LEVEL is shared machinery, not the sample
path; only the noise is the sample path's.

`real = 0`: the voice selected **bank 0**, one of the UNDUMPED sockets (IC304/305/306), and got
IC307's page-0 chunk 155 by the driver's `BAD_DUMP` substitution. **We are hearing an unrelated
recording, correctly rendered.** Nothing here is fixable in the tone generator; it needs a dump.

## 4. The real emulation defect: `detect_period()` invents a period, and `update_pitch()` then
## resamples by up to 33×

`detect_period()` ends with

```c
// No fundamental. A short recording is itself ~one cycle; a long aperiodic one
// (drum hit, applause) has none -> 0, and the caller plays it as recorded.
return (samples <= 2048) ? (samples << 16) : 0;
```

That branch is reached when the autocorrelation peak fails the `peak >= 0.5` acceptance gate.
For `b0 p1 c35` (N = 1496) the peak is **0.436 at lag 175** — a real period, rejected — so the
fallback declares the whole 1496-sample recording to be ONE CYCLE, i.e. a 32 Hz fundamental.
`update_pitch()` then computes `step = freq * P / 48000`, and at the note the demo plays that
is **33.30×**: linear interpolation reading every 33rd sample. The recording is **tonal**
(zcr 0.039, rms 17 417), so the result is broadband inharmonic noise — a genuine, audible
artefact, and the source of the whole t = 35–37 s left-channel cluster.

Static scope over all 1495 chunks: **565 chunks have `P == N`**, of which **522 have N <= 256**
(essentially all of page 2 — the genuine single-cycle drawbar footage waves, which need this
branch) and **43 have N > 256** (up to N = 2016 → 44× at C6). Of those 43, **7 are tonal**
(zcr < 0.10) and are where the artefact is audible rather than merely noise-on-noise.
`b1 p0 c157` proves this is not a substituted-bank problem: it is on the REAL IC307 dump.

### Candidate fix, MEASURED (not landed)

Bounding that fallback at 256 samples instead of 2048 (so a recording too long to be a single
cycle is declared aperiodic and played at its native rate, exactly as `b0 p0 c155` already is):

| | no fix | fix |
|---|---|---|
| mix clicks over 80 s | 1716 | 1574 |
| `b0 p1 c35` per-voice events | 2171 | **40** |
| energy above 6 kHz, t = 35.0–37.2 | −6.85 dB of total | **−17.24 dB** |
| L rms, same window | 1994 | 2245 |

A 10.4 dB drop in the high band with the level essentially unchanged is exactly the signature
of removing the aliasing. **But it is only a partial answer, and the honest reading is that it
treats a symptom**: the primary failure is that `detect_period()` REJECTED a period it had
found (0.436 < 0.50). Fixing the acceptance gate would give `P ≈ 175` and a musically correct
3.9× transposition instead of either 33× garbage or a 1× wrong pitch. That is the next move,
and it needs the `peak >= 0.5` threshold justified against the corpus rather than re-tuned.

## 5. ⚠ CORRECTION — the step detector is not a glitch detector, and the sine null cannot fail

This bit invalidates part of "What we already know" at the top of this file, so it is stated
plainly.

* `|x[n] − x[n−1]| > 8000` is reached by **any full-scale content above ~1.9 kHz**
  (a sine of amplitude A steps by at most `2A·sin(πf/fs)`). A drum, cymbal or SFX recording
  trips it hundreds of times a second **by being played correctly**. That is why the candidate
  fix moves `b1 p0 c157` from 1459 events to 2914: at native rate the noise it contains steps
  MORE, not less. The count measures high-frequency content, not artefacts.
* **"SINE mode has ZERO clicks" is not evidence of what it was taken to be.** At the demo's
  sine level (rms ~2200, amplitude ~3100) an 8000 step would need a fundamental above 21 kHz —
  physically impossible. The null is satisfied trivially, and *a criterion that cannot fail is
  not a pass*. The A/B still proves the burst's LEVEL is machinery (§3), which is worth having,
  but it does NOT establish "the defect is in the PCM sample path".
* A future pass should grade a step against the **local step distribution of the same voice**
  (the static pass's null: seam vs the 99th percentile inside the same loop), or against
  spectral continuity — not against a fixed threshold.

## 6. What is left

1. **`detect_period()`'s acceptance gate.** Why is `peak >= 0.5` rejecting 0.436 on a clearly
   pitched recording, and what does the corpus say the threshold should be? 46 chunks return
   `P == 0` and 565 return `P == N`; both populations deserve a look with the gate re-derived.
2. Then, and only then, the `samples <= 2048` bound — it is the fallback's blast radius, and
   the 43 chunks it mis-serves are enumerated above.
3. The burst needs **a dump of IC304/305/306**, not code.
4. Open, and NOT a click question: two voices reach ~0.77 gain hard-panned right, ~23 dB above
   the surrounding programme, and softclip. Sine mode does the same, so it is the level law,
   not the sample path. Worth asking Felipe what the demo actually sounds like there.

### Reproduce

```
cd ~/compartilhado/kn7000_mame_build ; rm -f nvram/kn5000/nvram1
DISPLAY=:0 timeout 1800 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo -autoboot_delay 0 \
  -seconds_to_run 80 -cfg_directory <private, AREA=2, TGMODE=0> -oslog \
  -autoboot_script <nav> -wavwrite out.wav
```
with `#define VERBOSE (LOG_GLITCH)` in `kn5000_tonegen.cpp`. The census is the last thing
printed. Add `LOG_GLITCHEV` only for runs shorter than ~35 s (see the trap in §1).
