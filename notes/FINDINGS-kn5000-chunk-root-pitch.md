# KN5000 per-chunk root pitch — measured from the register bus

2026-08-06. Everything below is computed from a capture of the IC303 register bus (address
latch 0x100000 / data 0x100002) — **no audio, no spectral analysis**. 5384 note-ons over 130 s,
156 distinct wave selectors. Tools preserved at `tools/kn5000-rootpitch/`.

## 1. ★ CORRECTS AN OVER-BROAD RETRACTION OF MINE

I retracted two things together. Only one deserved it.

* **RETRACTED, correctly:** "Parts 7 and 11 sound at the correct absolute pitch."
* **NOT retracted — it is MEASURED:** "the pitch offset varies per chunk." That is arithmetic on
  captured registers plus the firmware's own table, not an inference from audio.

**The mechanism behind the false positive, found independently and before my correction arrived:
TIME-LOCKED CROSS-PART COLLISION.** The parts play the same harmony and their per-selector errors
differ by musical intervals, so a wrongly-pitched voice of one part lands on *another* part's true
pitch at the same instant. A time-displacement null cannot reproduce that; a pitch-permuted null
can. Decoding each note-on with the firmware's own per-selector constant C recovers the demo's
MIDI notes (Part 2 361/369, Part 7 92/92, Part 8 95/95, Part 11 79/79), so per note we know which
voice played it and at what pitch it rendered:

| window | part | n | `hit_any` (the oracle's test) | null | **`hit_own`** |
|---|---|---|---|---|---|
| sine-B | Part 7 | 30 | 0.267 | 0.088 | **0.067** |
| sine-B | Part 11 | 22 | 0.364 | 0.105 | **0.000** |
| sine-A | Part 8 | 57 | 0.316 | 0.092 | **0.000** |
| sine-A | Part 2 | 176 | 0.136 | 0.120 | **0.000** |

`hit_any` reproduces the old ordering and z-values exactly; `hit_own` is zero.
⇒ **`hit_any` is not a valid criterion for a pitch fix.** Use `hit_own`.

## 2. Why the emulator is sharp — `rendered − asked`, from registers

```
 +7 : 2112  39.2%      -4 : 445  8.3%      -2 : 165  3.1%      +6 :  95 1.8%
+18 :  615  11.4%      +3 : 395  7.3%      +2 : 132  2.5%      +0 :  44 0.8%  <- correct
+19 :  587  10.9%      -3 : 315  5.9%     +56 : 133  2.5%     +12 :   0 0.0%  <- EMPTY
```
Median rendered 76.4 vs median asked 66.0 = **+10.4 st**; per-20 s centroid offset +8.5..+17.1.
That is the oracle's "onset centroid 74-79 vs 61-63, ~13 semitones high" — same number, from the
registers instead of from audio.

**Why no single correction works: the error is PER SELECTOR and MULTIMODAL** — at least eight
modes above 1%. The best global shift fixes 39.2%; **+12 fixes 0.0%**.

⚠ **THE `+12` DOES NOT EXIST IN THE REGISTER STREAM AT ALL.** Whatever produces a spectral
best-shift of +12 lives in the oracle's detector or in the PCM path (a `detect_period` octave
error doubles the PCM rate) — **not** in the pitch `update_pitch()` asks for. Chase separately.

## 3. The static chord — a five-of-five cross-check between registers and audio

At t~105 s, 25 voices gated. Frequencies predicted from their registers vs the oracle's measured
spectrum:

| register-predicted | oracle-measured |
|---|---|
| 224.6 / 252.1 / 267.1 / 299.8 / 336.5 Hz | 224.5 / 252 / 267 / 300 / 336.5 Hz |

Five of five to 0.2 Hz. All five ask MIDI 50/52/53/55/57 and sit on **one selector `0x3086`, C=0**,
whose anchor error is exactly **+7.36 st = 7 semitones + 36 cents**.
⇒ "exact semitone intervals, uniformly +35 cents" is **the fractional part of ONE selector's
error**. It is **+7, not +12**. Two other voices in that same chord (selectors `007F`, `008F`)
render at −3.62 and −2.61 simultaneously — which is the per-chunk variation, directly observed.

## 4. The root pitch is THREE BITS

* The trim table exists: `notes/data/kn5000-pitch-trim-table.tsv`, 1444 selectors, 94.7%
  single-valued. Integer-note decode **70.4%** vs a permuted-C null of **15.1 ± 6.9%**, and
  **0.9%** for the `0x3524` anchor. Melodic-part note recovery 97.8-100%. The residual 29.6% are
  the traced `2*fine + detune` terms (all < 0.4 st, so the note still rounds correctly) plus
  ambiguous-C selectors.
* **NEW STRUCTURAL RESULT.** Define `ROOT = 256*nat + 0x80 + C` with `nat` the HLE's measured
  period. Over **all 343** single-C chunks on the dumped chip (no selection on the answer),
  `ROOT mod 3072` clusters at 1723 units: **92.7% within ±25 cents, against a uniform null of
  4.2%**; median deviation 3.3 cents; per class 98.8 / 71.2 / 100 / 100%. The audit's four
  per-page constants (123.9 / 126.7 / 129.1 / 137.8) agree to 5.5 cents — **they are one
  constant.** Every recording in IC307 is tuned to the same pitch class; only its OCTAVE differs.
  ⇒ **The undecoded per-chunk root is exactly 3 bits (8 values).** Everything else is already in
  the PCM.
* **Where those 3 bits are NOT** (all null-gated): not in the parameter records — byte-identical
  records disagree on the octave in 17 of 38 groups, pairwise agreement 34.6% vs a 19.1% null,
  and a control feature absent from every record ("chunk index >> 4") "signals" at z=+8.7, which
  shows the whole feature family is positional autocorrelation; not in any per-voice register
  (32 registers x 76 selectors; `+0x0C0`=0x7F00, `+0x4C0`=0x4400, `+0x840`=0xFF00 constant for
  every chunk, `+0x080` not a function of the selector); not recoverable by "play it near its
  native rate" (48% demo-weighted, 15% key-slot-weighted).

⚠ **52% of the demo's note-ons select classes 0-3 = the UNDUMPED IC304/305/306**, where the
measured period belongs to a substituted recording. Any period-based fix is meaningless there.
The firmware table is unaffected.

## 5. Recommendation, with falsifiable predictions

Bake the C table for `true_note < 0` voices, replacing the `0x3524` anchor:
`note = (regs[8] − 0x80 − C(regs[1])) / 256`.

1. **Register-level, no audio** (re-run `tap.lua` + `parts.py`): per-part median error collapses
   from {+7.36, −3.52, +2.29, +7.36} to **0.00**, and `|err| <= 0.5` from 0.0-4.3% to **>= 95%**.
   **Below 90% falsifies it.**
2. **Oracle:** `hit_own` must go 0.00 -> **>= 0.8** for Parts 2/7/8/11. `hit_any` is NOT valid —
   it already reads 0.25-0.50 with the pitch entirely wrong.
3. The global-shift histogram must grow a spike at 0 (today 0.8%; control ~10%).
4. Key-bed notes (`true_note >= 0`) must be **bit-identical**.

## 6. A separate single-constant lead

A ~**−1.9 octave** global offset in `log2(playback rate)`, consistent with the HLE's
"step 1.0 = 48 kHz" being about two octaves off the ROM's real playback clock. Independent of the
trim, and exactly the kind of single wrong constant worth checking on its own.

`gt.json` in `tools/kn5000-rootpitch/` is the reusable per-chunk ground-truth octave vector that
any future decode must reproduce.

---

# 7. ★ SOLVED for the keybed: Felipe's "Jazz Flute is an octave high" is `detect_period`

2026-08-06, later. Felipe, playing the emulator from a MIDI controller on the current build:

> "With 'Jazz Flute' selected (Flute sound group, LCD LEFT 2), I noticed a pitch
> discontinuity in which all notes in the range Db4 until F#4 (including both extrema)
> sound like they're 1 octave higher pitch than they should sound."

**REPRODUCED EXACTLY, and the field is decoded. It is not the root octave.**

## 7.1 What it is

`tools/kn5000_patch_probe.lua` selects Jazz Flute by its LCD soft key (FLUTE + LEFT 2 —
confirmed on the LCD snapshot) and plays a chromatic sweep of the whole 61-key bed;
`tools/kn5000_sweep_pitch.py` measures the rendered pitch of every note. MEASURED, 61 notes:

| MIDI | note | selector | chunk | rendered vs asked |
|---|---|---|---|---|
| 36..72 | C2..C5 | `5003` | 3 | **ok** (ratio 1.00) |
| **73..78** | **Db5..Gb5** | **`5004`** | **4** | **+12 semitones (ratio 1.98)** |
| 79..84 | G5..C6 | `5005` | 5 | ok |
| 85..96 | Db6..C7 | `5006` | 6 | ok |

**55 notes correct, 6 an octave high, and the 6 are exactly one multisample zone** — six
semitones, Db to Gb (= F#), both extrema included. Felipe named the same six notes an octave
lower (Db4..F#4); the interval structure, the width and the endpoints match exactly, so this
is his defect with a different octave label on the keys.

## 7.2 Where it is NOT — and this kills the standing hypothesis

The brief expected the undecoded per-chunk **ROOT OCTAVE** (§4: exactly 3 bits). It is not.
These are **keybed voices** (`true_note >= 0`), whose branch of `update_pitch()` never reads
the root at all: `freq` comes from the MIDI note by equal temperament. MEASURED across the
zone boundary, the registers are perfectly chromatic — one selector per zone, `+0x400`
stepping exactly `0x100` per semitone, `pitch_step` doubling exactly per octave, no
discontinuity of any kind at MIDI 73. So the octave cannot enter through the pitch registers.

The only other term is the recording's measured period:

    pitch_step = f_wanted * pitch_period_q16 / 48000

If that period is wrong by a factor k the note renders k times too high **and nothing else
about the voice looks wrong** — same selector decode, same registers, same envelope.

## 7.3 What it is — MEASURED off the ROM, no audio involved

`tools/kn5000_chunk_period.py` rebuilds the page directory with `scan_wave_directories()`'s
own rules, reimplements `detect_period()` faithfully, and compares it against **YIN's
cumulative-mean-normalised difference function** — chosen because rejecting exactly this
octave error is what YIN is *for*, so agreement is meaningful and disagreement is localising.

    page 1, the flute page:
      chunk   samples   detect_P     yin_P    ratio
          0      3128      9.607     9.585    1.002   agree
          1      5096      9.606     9.584    1.002   agree
          2      7704     11.178    11.137    1.004   agree
          3      3208     20.240    20.218    1.001   agree
      *** 4      3144     20.948    10.436    2.007   detect = 2x yin
          5      2840      8.004     7.956    1.006   agree
          6      5960     10.986    10.948    1.003   agree

**`detect_period()` returns exactly twice the true period for chunk 4, and for no other
flute chunk.** 2.007x predicts the note to render at 2.007x its pitch; the spectrum of the
rendered audio at MIDI 73 peaks at ~1110 Hz against 554.4 asked and 1112.6 predicted. Two
independent measurements — ROM autocorrelation and rendered audio — agree to 0.2%.

⇒ **DERIVED, not fitted.** The defect is a period-detection failure in the HLE, in one
chunk. The root octave is not implicated, and §4's "3 bits" remains open and untouched.

## 7.4 Scope: how many more of these are there

Census of all 1495 chunks of IC307, restricted to the 402 real multi-cycle recordings
(`samples >= 1024`; the single-cycle drawbar footage on page 2 has no meaningful YIN answer
and is excluded rather than counted):

    agree 304 | detect = 2x true 9 | detect = 3x true 2 | detect = true/2 4 | other 83

The **15 exact-integer-ratio failures** are the ones this finding covers, with their `+0x040`
selectors — each is a multisample zone that plays at the wrong octave *for every patch that
uses it*:

    page 0: 0x4026 0x4028 0x4029 0x4030 0x4034 0x4036 0x4041 0x4047 0x4048 0x4068
    page 1: 0x5004 (Jazz Flute Db..Gb)  0x5046  0x5064  0x507E
    page 2: 0x6008

⚠ The 83 "other" disagreements are NOT claimed as defects: on inharmonic or noisy material
the two estimators can legitimately differ without either being octave-wrong. Only the clean
integer ratios are being asserted, and only one of them (`0x5004`) is so far confirmed
against rendered audio and against a human listener.

## 7.5 What the fix has to be, and the gate it must pass

Not a table of corrections. `detect_period()` picks the first lag within 8% of the peak
correlation after the first negative-going crossing, which on a recording whose waveform has
two similar halves per period locks onto the double. The principled repair is to make the
estimator octave-robust (YIN's `d'` is the obvious candidate, and is already implemented in
`tools/kn5000_chunk_period.py` for the audit).

Gates any change must pass, all of which CAN fail:

1. `kn5000_chunk_period.py --all` over the four pages: the 15 exact-integer disagreements go
   to 0 and the 304 agreements **stay** agreements. Breaking a currently-correct chunk is a
   regression even if the offender is fixed.
2. The Jazz Flute sweep reads `ok` for all 61 notes, MIDI 36..96 — today 55 ok / 6 at +12.
3. `gt.json` must still be reproduced (§4).
4. Piano and organ demos must not regress.

## 7.6 For Felipe

Fixed-velocity keybed notes were used throughout (the driver's `KEYBED_VELOCITY = 100`); his
controller sends real velocities. That does not affect this finding — the wave zone is
selected by NOTE — but it is the one uncontrolled variable in the rig, and worth saying.

**To re-test:** on Jazz Flute the six notes are the ones the LCD calls Db..F#, in the octave
*above* the one he named if his controller and the KN5000 disagree by an octave. The four
zone boundaries are at MIDI 73, 79 and 85. He should also hear the same octave jump on any
patch built from the other 14 selectors above.
