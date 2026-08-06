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
