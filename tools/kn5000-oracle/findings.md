# A sine-only oracle for KN5000 demo-song playback

M = MEASURED, I = INFERRED.

---

# SECOND RUN — 2026-08-06, after the INT0 fix (commit 3fd44f3)

The first run (kept below) only ever saw ~10 s of music. This run sees **112 s**, and
three of its five headline conclusions do not survive.

| claim | first run | SECOND RUN |
|---|---|---|
| tempo recoverable from audio | 90.0 ± 1 bpm | **90.000 bpm, peak 0.50 bpm wide** (M) — confirmed, 3.5x sharper |
| emulator TIMING reproduces the MIDI | YES, z=+24..+28 | **YES, z=+18** (M) — confirmed on 9x the notes |
| emulator ABSOLUTE PITCH reproduces the MIDI | "1.2–1.5x its null" | **NO — 0.6% of the control's pitch information** (M) |
| some parts ARE at the correct pitch (7, 11) | YES, argmax k=0 | ⚠ **RETRACTED** (M). No part clears z=3 against a pitch-permuted null |
| per-sample-zone tuning trim | inferred | ⚠ **NOT SUPPORTED** (M). See §4 |
| the sine-mode stall | ~10 s after the music starts | **now ~112 s**, but the song still stops at 58% (M) |

## 0. What was captured, and how

Published binary `/home/fsanches/compartilhado/kn7000-emulator/kn7000`, mtime
2026-08-05 23:06 — the same minute as commit 3fd44f3. It does not wedge.

* `AREA` = **0x06 ("Other")**, the driver default. `TGMODE` came from a **private
  `-cfg_directory`**, never from `set_value()` (which toggles a PORT_CONFNAME field),
  and the nav script **printed `ports[":TGMODE"]:read()` every emulated second** — 0x01
  for all 233 s of the sine run, 0x00 for all 233 s of the PCM run. MAME's own rewrite
  of the private cfg on exit agrees.
* Private `-nvram_directory` as well: no `nvram1` at all (so no work DRAM carried over
  from a previous run), `nvram2` copied from the published tree.
* `oracle_long.lua` = `sine_early.lua`'s button sequence (demo engaged at t=12 s) minus
  the TGMODE poking, plus the per-second provenance print.

| capture | mode | engaged | length | music |
|---|---|---|---|---|
| `long_sine.wav` | sine (TGMODE 0x01) | t=12 s | 232 s | 19.26–131.5 s |
| `long_pcm.wav` | PCM (TGMODE 0x00) | t=12 s | 232 s | 19.26–131.5 s |
| `long_sine2.wav` | sine, independent replicate | t=20 s | 145 s | 27.3–139.5 s |

## 1. Tempo — 90.000 bpm, and the peak is 3.5x sharper (M)

Joint (tempo, offset) search, 50–220 bpm on a 0.25 bpm grid, shift 0, whole capture:

| capture / window | peak | half-height | width | first run |
|---|---|---|---|---|
| sine 18–132.5 s (114 s) | **90.00 bpm** | 89.75–90.25 | **0.50 bpm** | 1.75 bpm on 30 s |
| sine 18–100 s (82 s) | **90.00 bpm** | 89.50–90.50 | **1.00 bpm** | |
| sine replicate 26–141 s | **90.00 bpm** | 89.75–90.50 | **0.75 bpm** | |
| PCM 18–132.5 s | **90.00 bpm** | (occupancy 14%, coarse floor high) | fine 0.18 | |
| CONTROL 18–215 s | **90.00 bpm** | 89.75–90.25 | **0.50 bpm** | — |

Refined on a 0.02 bpm grid: **90.000 bpm**, one tempo aligning the whole 114 s.
`t0`(MIDI beat 0) = **17.419 s**; the first note (beat 3.031) lands at 19.440 s.
The best rival tempo in 50–220 bpm (135.0 bpm, 0.196) scores 26% below the peak (0.264),
and the profile floor is 0.147.

Model-free cross-check (autocorrelation of the broadband onset function, no MIDI
involved): lags 0.1653 / 0.3413 / 0.5013 s = one, two and three sixteenths of a
0.6667 s beat.

Search validation: run on our own render, where the truth is bpm = 90.000 and the first
note is at 22.021 s by construction, the same code returns **90.000 bpm, t0 = 22.016 s
(5 ms error), shift 0 at 0.659 against 0.229 for the runner-up**.

**The `--bpm 90` default from 9cbe6cc is correct and is now measured to ±0.25 bpm.**

## 2. Headline scores — FIXED alignment, every null through the same code (M)

`melodic` excludes MIDI tracks 10 and 16 (Part 9, Part 15): a drum note number is a kit
key, not a frequency. Part 15 alone is 39% of the file.

Window 18–100 s (the music before the stuck-voice drone of §6):

| run | subset | n | hit@0 | NULL-T | NULL-P | NULL-F | z vs T | BLIND |
|---|---|---|---|---|---|---|---|---|
| CONTROL our own render | all | 2375 | 0.662 | 0.135 | 0.259 | 0.039 | +75.2 | 0.991 |
| CONTROL our own render | melodic | 1205 | **0.780** | 0.133 | **0.297** | 0.039 | +66.1 | 1.000 |
| SINE `long_sine.wav` | all | 2467 | 0.255 | 0.133 | 0.246 | 0.088 | +17.8 | 0.835 |
| SINE `long_sine.wav` | melodic | 1251 | **0.353** | 0.183 | **0.350** | 0.088 | +15.5 | 0.886 |

Window 18–132.5 s (everything the emulator produced):

| run | subset | n | hit@0 | NULL-T | NULL-P | NULL-F | z vs T |
|---|---|---|---|---|---|---|---|
| CONTROL | melodic | 2074 | 0.758 | 0.135 | 0.304 | 0.044 | +83.2 |
| SINE | all | 3754 | 0.261 | 0.136 | 0.245 | 0.080 | +22.2 |
| SINE | melodic | 2111 | 0.352 | 0.196 | 0.340 | 0.080 | +18.1 |

NULL-T = same notes and pitches, times displaced by a random 2–40 beats. NULL-P = same
times, pitches permuted among the notes (kills pitch, keeps the histogram). NULL-F =
surface occupancy.

**Timing: confirmed.** hit@0 is 1.8–2.6x NULL-T at z = +15 to +22, on 9x the notes.

**Pitch: gone.** The pitch-specific quantity is hit@0 − NULL-P:

| melodic, 18–100 s | control | sine |
|---|---|---|
| hit@0 − NULL-P | **+0.483** | **+0.003** |

The emulator recovers **0.6%** of the control's absolute-pitch information. The first
run's "1.2–1.5x the pitch-permuting null" was a 243-note artefact.

## 3. Per-part — ⚠ the first run's positive result is RETRACTED (M)

The first run scored each part against a **time-displacement** null and read
"argmax shift = 0" as evidence of correct absolute pitch. That null does not control for
**register**: a part living in one octave scores well simply because the emulator has
onsets in that octave at those times. The pitch-permuted null does control for it, and it
is calibrated here on our own render, where the pitches are right by construction.

Window 18–100 s, one null per part, 40 permutation draws each:

| part | n | sine hit@0 | sine NULL-P | sine excess | z | **control excess** | control z |
|---|---|---|---|---|---|---|---|
| POOLED MELODIC | 1251 | 0.353 | 0.352 | **+0.002** | +0.13 | **+0.485** | **+43.3** |
| Part 0 (0x00) | 110 | 0.573 | 0.580 | −0.007 | −0.15 | +0.557 | +15.3 |
| Part 1 (0x02) | 161 | 0.255 | 0.243 | +0.012 | +0.36 | +0.366 | +13.4 |
| Part 2 (0x01) | 383 | 0.211 | 0.224 | −0.013 | −0.82 | +0.370 | +18.8 |
| Part 3 (0x0B) | 20 | 0.000 | 0.055 | −0.055 | −1.11 | +0.268 | +2.8 |
| Part 5 (0x09) | 19 | 0.579 | 0.346 | +0.233 | +2.83 | +0.581 | +5.7 |
| **Part 7 (0x03)** | 192 | 0.521 | 0.510 | **+0.011** | **+0.34** | +0.593 | +20.5 |
| Part 8 (0x04) | 95 | 0.474 | 0.504 | −0.031 | −0.68 | +0.278 | +6.9 |
| Part 10 (0x06) | 76 | 0.197 | 0.275 | −0.078 | −1.66 | +0.371 | +8.5 |
| **Part 11 (0x07)** | 79 | 0.544 | 0.506 | **+0.039** | **+0.94** | +0.271 | +5.4 |
| Part 12 (0x11) | 40 | 0.425 | 0.296 | +0.129 | +2.38 | +0.755 | +12.7 |
| Part 13 (0x12) | 51 | 0.275 | 0.165 | +0.110 | +2.55 | +0.540 | +10.6 |

On the full 18–132.5 s window (up to 2111 melodic, 641 in one part) no part's k=0 excess
exceeds ±0.13 and no |z| exceeds 2.4. **The PCM capture agrees**: pooled k=0 excess
−0.007 (z = −0.80), no part above z = +1.53 — so this is not a property of the sine
renderer.

**Not one part reaches z = 3, at note counts where the control reaches z = +2.8 to +20.5.**
Parts 7 and 11 — the first run's two "correct" parts — sit at +0.34 and +0.94. Their high
raw hit rates (0.52, 0.54) are entirely explained by register plus timing.

For continuity, the same parts scored the first run's way (against the time-displacement
null). It still looks impressive, which is exactly why the second null was needed:

| part (18–100 s) | n | hit@0 | NULL-T | z | argmax k |
|---|---|---|---|---|---|
| Part 7 (0x03) | 192 | 0.521 | 0.196 | +11.3 | **+2** (was 0) |
| Part 11 (0x07) | 79 | 0.544 | 0.157 | +9.5 | **+4** (was 0) |
| Part 8 (0x04) | 95 | 0.474 | 0.146 | +9.1 | +7 |
| Part 0 (0x00) | 110 | 0.573 | 0.284 | +6.7 | +19 |
| Part 2 (0x01) | 383 | 0.211 | 0.183 | +1.5 | +4 |
| Part 15 (0x0C) drums | 1084 | 0.156 | 0.080 | +9.3 | +12 |

The control's per-part argmax is **k = 0 for every part** except Part 3 (n = 20).

## 4. The per-chunk-trim inference — ⚠ NOT SUPPORTED (M)

Both observations it rested on change on the long capture.

**(a) "The global semitone histogram is flat."** It is not. The melodic hit rate rises
smoothly from 0.04 at k = −24 to a broad hump over k = +2…+12, peaking at **k = +7
(0.4325)**, with k = 0 at 0.3533. But the hump carries **no pitch information** — the
pitch-permuted null tracks it almost exactly:

| k | −12 | −7 | −2 | **0** | +2 | +3 | **+7** | +12 |
|---|---|---|---|---|---|---|---|---|
| sine hit | 0.145 | 0.247 | 0.345 | **0.353** | 0.390 | 0.392 | **0.432** | 0.380 |
| sine NULL-P | 0.183 | 0.249 | 0.307 | **0.352** | 0.348 | 0.345 | **0.355** | 0.341 |
| excess | −0.038 | −0.002 | +0.037 | **+0.002** | +0.042 | +0.048 | **+0.077** | +0.039 |

The hump is the emulator's own register habit: its onsets sit higher than the score, so
sliding the score up finds more of them. The largest excess anywhere is +0.077 at k = +7,
1.2x its null — against the control's **+0.485 at k = 0, 2.6x its null**, with every
other k ≤ 0.24 beside a 0.780 peak.

That register habit is directly measurable (M). Centroid of the detected-onset
distribution over the pitch axis, same detector, same music:

| window | sine | PCM | our render |
|---|---|---|---|
| 18–76 s | 74.16 | 77.97 | 61.90 |
| 18–100 s | 76.81 | 76.96 | 62.30 |
| 76–100 s | 78.92 | 77.08 | 60.65 |
| 100–131 s | 70.84 | 74.08 | 62.53 |

**The emulator sounds ~13 semitones — about an octave — above where the score puts it**,
in both render modes and in every window including the clean early block. That is why the
best global shift is +12. It is a centroid of onsets, not of notes, and our render puts
the drum tracks at their kit-key numbers, so the two columns are not strictly
commensurable — but the direction and the rough size are not in doubt, and no permutation
null is needed to see them. ⚠ Correcting for it does NOT fix the pitch: at k = +12 the
excess over NULL-P is still only +0.039.

**(b) "The best global shift is unstable between captures."** ⚠ **It is not.** It is now
**+12 in all three**: `long_sine.wav` 18–100 s, `long_sine.wav` 18–132.5 s, and the
independent replicate `long_sine2.wav` 26–141 s (different engage time, separate boot).
The whole profile replicates, not just its peak:

| shift | −7 | −5 | −1 | **0** | +3 | +5 | +7 | **+12** | +17 | +19 | +24 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| capture A | 0.194 | 0.199 | 0.209 | 0.264 | 0.247 | 0.256 | 0.284 | **0.326** | 0.221 | 0.229 | 0.211 |
| capture B | 0.188 | 0.216 | 0.214 | 0.252 | 0.267 | 0.280 | 0.310 | **0.349** | 0.235 | 0.230 | 0.219 |

The first run's "+7 on one capture and +12 on the other, i.e. noise" was a 13-second
window. But stability here only means the emulator has a fixed register bias — not that
it is transposed, because the permutation null eats the whole effect.

**A third, new measurement points away from a tuning trim altogether.** From t ≈ 100 s
the output is a static chord of stuck voices (§6), so its frequencies can be read off
exactly:

| | measured Hz | MIDI (fractional) | intervals |
|---|---|---|---|
| sine | 224.5, 252, 267, 300, 336.5 | 57.35, 59.35, 60.35, 62.37, 64.36 | 2.00, 1.00, 2.02, 1.99 |
| PCM | 446.5, 501, 531, 669 | 69.25, 71.25, 72.25, 76.25 | 2.00, 1.00, 4.00 |

Identical at t = 105, 110 and 120 s. **The intervals are exact semitones and the whole
chord is uniformly sharp** — +35 cents in sine mode, +25 cents in PCM. A per-zone trim
scattering pitches could not give exactly-semitone intervals across five simultaneous
voices; a constant tuning offset (or one wrong root) would. And a uniform ±35 cents is
*inside* the oracle's half-semitone band, so it is not what destroys the pitch score.

**(I)** What the scores are consistent with: the emulator plays a plausible set of
pitches at the right times, but the assignment of *which* pitch to *which* event is
wrong — which is literally what NULL-P models. That points at note DISPATCH / event
DECODE rather than at arithmetic in `update_pitch()`.

One prediction of the dispatch story was tested and **failed**. If the right pitches were
merely landing at the wrong moment or in the wrong order inside a bar, relaxing the time
tolerance would recover them:

| ± tolerance | 40 ms | 80 | 160 | 320 | 640 | 1280 |
|---|---|---|---|---|---|---|
| sine excess over NULL-P | +0.012 | +0.018 | +0.019 | +0.033 | +0.048 | +0.033 |
| control excess over NULL-P | +0.456 | +0.424 | +0.378 | +0.327 | +0.238 | +0.127 |

Even with ±0.96 beat of slack the emulator recovers a tenth of the control's excess. The
notes are not merely mis-ordered in time; the pitches themselves are wrong.

## 5. Does accuracy vary over time or by register? NO — it is uniformly absent (M)

Same statistic (hit@0 minus a null that permutes the pitches **inside the cell**, so the
cell's own register and its own onset times are held fixed), 200 draws per cell, run on
the emulator and on our own render side by side, window 18–132.5 s.

| cell | n | sine excess | z | control excess | z |
|---|---|---|---|---|---|
| beats 0–43 (t 17–46 s) | 679 | +0.019 | +1.47 | +0.381 | +24.5 |
| beats 43–85 (t 46–74 s) | 188 | +0.079 | +2.65 | +0.481 | +17.7 |
| beats 85–128 (t 74–103 s) | 416 | +0.013 | +0.66 | +0.500 | +29.0 |
| beats 128–171 (t 103–131 s) | 792 | +0.019 | +1.52 | +0.386 | +26.0 |
| MIDI 48–59 | 251 | +0.011 | +0.75 | +0.162 | +6.9 |
| MIDI 60–71 | 760 | +0.000 | +0.03 | +0.417 | +28.2 |
| MIDI 72–83 | 911 | +0.015 | +1.25 | +0.410 | +27.4 |
| MIDI 84–95 | 126 | −0.007 | −0.27 | +0.434 | +12.5 |

Per part, split EARLY/LATE and LOW/HIGH register: 30 more cells, all |z| ≤ 2.6, no
structure. **There is no zone to localise** — the accuracy does not collapse at a
register boundary because it never rises anywhere. This is the table a future fix has to
move.

## 6. The stall moved; it did not go away (M)

Both render modes show the same structure, so this is firmware / voice-manager, not the
renderer:

* music starts at **t = 19.26 s**, RMS 0.0005–0.11, ordinary musical dynamics;
* **t = 76.0 s**: exactly 0.5 s of *complete* silence, then RMS jumps ~18 dB;
* **t ≈ 100 s**: RMS pins at 0.370 ± 0.005 (sine) / 0.11 (PCM) and the spectrum stops
  changing — the static chord of §4. Stuck voices, not music;
* **t = 131.5 s**: audio stops dead. `transport` (0x0420) goes 04 → 00 between t=130 and
  t=132 and the beat counter freezes at 0x18, while `songptr` keeps advancing.

112 s of music at 90 bpm = **beat 171 of 292 — 58% of the song**. The oracle's own
time-bin table sees the edge: the bin at beats 171–192 (t 131–145 s) has hit@0 0.000 and
BLIND 0.083.

Reproduced exactly in the independent replicate (`long_sine2.wav`, demo engaged 8 s
later): audio 27.3–139.5 s = **112 s again**, `transport` → 00 at t = 140, drone RMS
0.412 ± 0.002 from t = 110 to t = 135.

## 7. Did the INT0 fix change anything audible? YES — from the FIRST note (M)

Old `sine_early.wav` and new `long_sine.wav` use the identical nav script and engage
time, so they are sample-comparable:

* **bit-identical for the first 924 617 samples — up to t = 19.263 s** — then divergent.
  The divergence begins at the first audible note, not at the old stall point. The
  duplicate INT0 dispatch was corrupting the note stream from the very start, not only
  from t ≈ 28 s.
* old: content dies at t ≈ 27.5 s (residual RMS 0.00016, one burst at t = 34.0).
  new: content continues to t = 131.5 s.
* over 21.5–22.0 s both have similar RMS (0.048 vs 0.051, 0.150 vs 0.161) but their
  *difference* is larger than either (0.071, 0.241) — different signals, not a level
  change.

## What this oracle can and cannot catch (revised)

CAN: tempo to ±0.25 bpm; timing / scheduling (z = +18 on 2111 notes); note presence; the
end-of-audio point; and it is a ready-made POSITIVE TEST for a pitch fix — the number to
watch is **hit@0 − NULL-P**, currently **+0.003** where the control is **+0.483**.
CANNOT: drum-part pitch; sub-semitone tuning error (±35 cents is inside one band);
absolute pitch from a PCM capture (its shift profile is a harmonic ladder, best at +24 /
+19 / +7 / +12); anything about timbre, envelope, effects or mix.

## Files left for Felipe

* `long_sine.wav`, `long_pcm.wav`, `long_sine2.wav` — the raw captures (3-channel).
* `ab_long_L_render_R_emulator_sine.wav`, `ab_long_L_render_R_emulator_pcm.wav` —
  18–132.5 s, LEFT = our 90 bpm sine render of the score, RIGHT = the emulator,
  loudness-matched, on one clock.
* `oracle_render_90bpm.wav` — the whole song, 195 s, sines only.

## Tools added this run

`long_search.py` (staged tempo / offset / shift search for long captures),
`long_eval.py` (headline + per-part + time + register at a fixed alignment),
`kprofile.py` (**hit(k) minus its own pitch-permuted null** — the decisive statistic),
`zone_scan.py` (the same statistic per time / register cell),
`tolsweep.py` (excess versus time tolerance), `make_ab.py`, `oracle_long.lua`.

⚠ `long_search.py` re-origins the MIDI beats on the first note. `corr_surface` only
evaluates non-negative lags, so with a window starting at 18 s a true beat-0 time of
17.42 s was **unreachable**, and the search would silently have locked onto a wrong
tempo. Any future change of window must keep this in mind.

---

# FIRST RUN — 2026-08-05 (kept for audit; superseded above)

| claim | verdict |
|---|---|
| tempo recoverable from audio | **YES — 90.0 ± 1 bpm** (M). The converter's 120 default is wrong by 1.33x |
| emulator TIMING reproduces the MIDI | **YES, decisively** — 6-11x its matched null, z = +24..+28 (M) |
| emulator ABSOLUTE PITCH reproduces the MIDI | **NO in aggregate** — 1.2-1.5x the pitch-permuting null vs 2.2x for the control (M) |
| uniformly wrong? | **NO — right for some parts, wrong for others** (M, replicated in 2 captures) |
| systematic octave/semitone offset? | **NOT FOUND** (M). Not a constant transposition, global or per-part |

## Scores (fixed alignment, no re-optimisation; every null built the same way)

| run | subset | n | hit@0 | NULL-T | NULL-P | z |
|---|---|---|---|---|---|---|
| CONTROL (our own render) | melodic | 243 | **0.909** | 0.053 | 0.409 | +59.4 |
| SINE-A sine.wav | melodic | 243 | 0.358 | 0.041 | 0.294 | +24.9 |
| SINE-B sine_early.wav | melodic | 193 | 0.337 | 0.032 | 0.302 | +23.9 |
| PCM det1.wav (pipeline check) | melodic | 679 | 0.365 | 0.146 | 0.323 | +16.2 |

NULL-T = times displaced (kills timing). NULL-P = pitches permuted (kills pitch, keeps histogram).
Against NULL-T the emulator is 6-11x chance: **timing is real**. Against NULL-P only 1.2-1.5x
where the control is 2.2x: **pitch information is nearly absent in aggregate**.

⚠ The SEARCH has its own null: with the alignment free to re-optimise, the pitch-permuted null
nearly ties the real score. That is why every number above is at a FIXED alignment.

## The pitch finding is more specific than "octaves"

Global semitone sweep: the control spikes to 10.2% at k=0; sine.wav is FLAT (2.8% at 0, max 3.0%
at +7). No transposition of any size lines the pitches up. Best global shift is +7 on one capture
and +12 on the other -- same music, same emulator, i.e. noise. Octave errors split
{+24:21, +12:21, -12:14, -24:7}, not signed.

**(I, well-supported)** This is what a PER-SAMPLE-ZONE (per-chunk) tuning trim produces, since a
part crosses several zones as it moves through its range. `update_pitch()`'s own comment calls the
0x3524 reg[8] anchor "a convenience, not a measurement"; its guess of "possibly by octaves"
UNDERSTATES it. No single constant can repair this.

⚠ **SECOND RUN: this inference is NOT SUPPORTED — see §4 above.** The histogram is not
flat, the best shift is stable within a capture, and the stuck-voice chord has exact
semitone intervals.

## The positive: some parts ARE at the correct absolute pitch

⚠ **SECOND RUN: RETRACTED — see §3 above.** The null used here (time displacement) does
not control for register; against a pitch-permuted null no part clears z = 3.

Pooled over two independent sine captures, each against its own matched null:

| part | n | hit@0 | null@0 | z | argmax k | control |
|---|---|---|---|---|---|---|
| **Part 11 (type 0x07)** | 56 | 0.589 | 0.136 | **+9.9** | **0** | 0.781 |
| **Part 7 (type 0x03)** | 74 | 0.514 | 0.073 | **+14.5** | **0** | 0.977 |
| Part 8 (type 0x04) | 36 | 0.389 | 0.042 | +10.4 | +7 (0 second) | 0.917 |
| Part 2 (type 0x01) | 235 | 0.251 | 0.128 | +5.6 | +7 | 0.944 |
| Part 15 (0x0C drums) | 287 | 0.105 | 0.053 | +3.9 | flat | 0.649 |

★ NEXT STEP THIS HANDS US: find what Parts 7/11 have that Parts 2/15 do not. If they sit on
chunks whose tuning trim is 0, that is a direct handle on the undecoded per-chunk root pitch.
Part 15 (drums, 39% of all notes) must be EXCLUDED from any future oracle -- a drum note number
is a kit key, not a frequency.

## Side findings

* ★ **The sine-mode stall is ~10 s AFTER THE MUSIC STARTS, not at a fixed clock time.** Engaging
  the demo at t=12 s instead of 20 s moved the music window from 27.3-37.2 s to 19.25-28 s -- the
  same ~10 s (M). `transport` stayed 04 and `songptr` kept advancing throughout, so whatever stops
  the AUDIO is downstream of the sequencer. Engaging earlier will not widen the window.
  ⚠ **SECOND RUN: fixed by 3fd44f3 — the window is now ~112 s. See §6.**
* The demo MIDI is an UNQUANTISED live performance at 96 ppq (99.51% of consecutive same-beat
  pairs non-decreasing, vs ~50% under a garbage null) -- the decode is sound, the music just is
  not on a grid. Durations ARE quantised (piled at 11 and 23 ticks).
* The emulator's sine output is BURSTY -- RMS falls to exactly 0 between bursts. That is the
  source of the 21-44% "nothing at all" rows.
* On PCM the best global shift is +19 = the third harmonic (3x = +19.02 semitones). The analysis
  is locking onto real pitched content, and this is also why PCM captures cannot judge absolute
  pitch.

## Detector ceiling (measured on our own render)

Recall 0.675 overall, **0.892 on notes with no same-pitch overlap**, 0.232 on notes restarting an
already-sounding pitch (physical: two identical sines give no onset cue). Timing sd 5.7 ms.

## ACTIONABLE

`scripts/build/demo_preset_to_midi.py` should default to **--bpm 90**, not 120.
⚠ **SECOND RUN: confirmed to ±0.25 bpm; already landed as 9cbe6cc.**

## What this oracle can and cannot catch

CAN: tempo/clock regressions (peak 1.75 bpm wide on 30 s); timing/scheduling regressions
(z=+24..+28); note-presence regressions (control pins the detector's own contribution at 0.8%);
per-part pitch correctness for Parts 7/11/5/8; and it is a ready-made POSITIVE TEST for a future
pitch fix -- Part 2's hit@0 should climb from 0.25 toward 0.94.
CANNOT: drum-part pitch, absolute pitch on PCM captures, notes restarting a sounding pitch,
anything about timbre/envelope/effects/mix.

Listen: `oracle_render_90bpm.wav` (whole song, 195 s) and `ab_render_L_emulator_R.wav`
(15 s, LEFT = our render, RIGHT = the emulator).
