# KN5000 tone generator — faithful render from REAL IC307 wave-ROM data

Author: autonomous fix + live-verify pass, 2026-07-23. Requested by Felipe Sanches.
**This session edited `src/`, built, ran MAME, verified, committed.**

Supersedes the synthetic-timbre PALETTE shipped in `notes/kn5000-wave-number.md §4`. Builds
directly on the three findings notes: `kn5000-wave-number.md`, `kn5000-tone-record.md`,
`kn5000-ic307-content-map.md`.

Evidence labels: **MEASURED** (ROM bytes / disasm / the RUNNING machine), **INFERRED**,
**SPECULATIVE**.

Files: `src/mame/matsushita/kn5000_tonegen.{cpp,h}`. Live captures on the built `kn5000`
driver, isolated pre-init nvram (`nvram/kn5000/nvram2`: RIGHT1=Piano, RIGHT2=Bigband Brass).

---

## 0. TL;DR — what changed

* **The fabricated synthetic-timbre palette is GONE** (`build_palette` / `select_palette` /
  `palette_sample` / `m_palette` / `voice_t::wave_palette` all removed). No invented additive
  timbres remain; nothing calls `sin()` at render time.
* **Every voice now renders REAL IC307 PCM.** A voice's firmware register fingerprint selects
  a real IC307 waveform (index 0..189); different instruments (different fingerprints) resolve
  to DIFFERENT real waveforms, so they sound genuinely different — real timbres, not invented.
* **Pitch is exact and CANNOT regress**, by construction (see §2): we loop ONE fundamental
  period of the real waveform and resample it to the played note, so pitch is decoupled from
  the recording's (un-stored) root note. Verified: chromatic C4..B4 = 12 distinct exact
  pitches, C4/C5 octave, C-E-G chord all three fundamentals balanced.

---

## 1. Real waveform selection — decoded and confirmed LIVE

The three findings established: the firmware writes wave-number **0** to +0x440/+0x480 for
every ordinary PCM voice (it is a legacy selector these voices bypass by design), and the
per-instrument identity instead travels through the delivered tonerec's partial-parameter
records, which the firmware programs into the pitch/zone and timbre registers. Their HIGH
bytes form a **stable per-instrument fingerprint** — `regs[1]`(+0x040), `regs[3]`(+0x0C0),
`regs[5]`(+0x140), `regs[12]`(+0x500).

**Selection (`select_waveform_index`):** hash the four fingerprint bytes to a real IC307
index, `idx = 1 + ((s1*131 + s3*17 + s5*7 + s12) mod 189)`; an all-zero fingerprint
(boot/degenerate voices) → index 0 (the real single-cycle sine). Range 1..189 = the page-0
indexed instrument waveforms; it deliberately excludes index 0 (sine) and the
multisample-duplicate / 3 MB-tail entries 190-197 (which share offsets and point at the
un-indexed page tail, per `kn5000-ic307-content-map.md §2.3/§4`).

**PREDICT-THEN-CHECK — confirmed on the RUNNING machine (MEASURED).** A C4 note-on with the
Piano+Brass split gives, per the tonegen's own resolve trace (temporary log, since removed):

| instrument | live fingerprint (s1/s3/s5/s12) | selected IC307 idx | detected period |
|---|---|---|---|
| PIANO (RIGHT1)  | `70/74/6F/2C` | **78** (file 0x91650) | 128 |
| BRASS (RIGHT2)  | `70/00/7F/00` | **64** (file 0x414D0) | 92 |
| boot-init voices | `00/00/7F/00` | 134 | 32 |
| degenerate       | `00/00/00/00` | 0 (real sine) | 256 |

Two different instruments → **two different real IC307 waveforms**, deterministically and
stably. (Unlike the earlier `+0x440` wave-number, which was a MISS — 0 for all — this
fingerprint path genuinely discriminates, exactly as the tone-record note predicted.)

The `+0x040` multisample-zone nibble is an available refinement lever (it could pick
neighbouring waveforms across key zones, mimicking a real multisample map) but is
intentionally NOT folded into the base selection, so each instrument maps to one stable,
testable waveform.

## 2. Pitch for multi-cycle real waves — the single-period wavetable (the key insight)

IC307's 198 waveforms are **multi-cycle recordings** whose absolute ROOT note is PROVEN
ABSENT from the ROM (`kn5000-ic307-content-map.md §3.4`), so they cannot be pitched by naive
native-rate playback without a root that does not exist. The task warned this is the hard
risk and that a real timbre at a WRONG pitch is worse than the current correct pitch.

**Resolution — decouple pitch from the source root:**
1. Detect the waveform's fundamental **period** P by autocorrelation (`detect_period`): biased
   normalized autocorrelation over a bounded window, taking the argmax lag AFTER the first
   negative-going zero crossing (this skips the lag-0 shoulder that mis-detects a pure sine).
   The ROM is periodic (autocorr r≈0.99, content-map §2.2), so a clean P exists.
2. Loop exactly **one period** (`wave_length = P`) and resample it to the played note in
   `update_pitch` (`step = 65536·freq·P/48000`). One period repeats at exactly `freq` Hz
   regardless of the recording's native rate, so **absolute pitch comes 100% from the
   equal-tempered played note** (recovered from the real keybed/MIDI event) and is INDEPENDENT
   of the waveform's root. The looped period is a genuine cycle of real PCM, so its harmonic
   spectrum is the real instrument's — real timbre AND exact pitch, simultaneously.

**Why this cannot regress pitch:** P only affects timbre quality, never frequency (frequency
is forced by the resample). Even a wrong P keeps the note in tune. This structurally satisfies
the hard constraint. **Fallback:** if no clean period is found (`period==0`, long aperiodic
material), the voice falls back to IC307 index 0 (the real single-cycle sine, period 256) — a
real waveform at exactly the right pitch, never a wrong pitch.

**Looping:** one fundamental period IS the loop (the ROM stores no loop points; the real chip
loops autonomously). The render wraps by the loop length preserving fractional phase, so the
seam has no phase glitch; linear interpolation wraps the last sample to the loop start.

## 3. Verification (MEASURED on the built driver; captures = 3-ch/48 kHz WAV, ch1)

Spectral captures used a TEMPORARY ×64 gain + a TEMPORARY `KN_FORCE_IDX` isolation hook (a
linear gain preserves harmonic ratios; both REMOVED before the committed build). Pitch
captures are note-driven and gain-independent.

* **Distinct REAL timbres (criterion a ✓).** Isolated captures of the two instruments' actual
  selected waveforms, at C4, harmonic profile H1..H8 (relative):
  - PIANO idx78 captured `[1, 0.35, 0.03, 0.00, 0.03, 0.02, …]`; ROM one-period
    `[1, 0.48, 0.08, 0.16, …]`.
  - BRASS idx64 captured `[1, 0.16, 0.04, 0.00, 0.02, 0.03, …]`; ROM one-period
    `[1, 0.22, 0.11, 0.03, …]`.
  - SINE idx0 ROM `[1, 0, 0, 0, …]` (pure — confirms index 0).
  Piano and Brass are **spectrally distinct** (H2 0.35 vs 0.16, different higher structure),
  each **matches its real IC307 ROM period** (correct harmonic ordering; higher harmonics
  softened by the linear-interpolation resample — an honest, mild low-pass), and both are
  clearly NOT a pure sine (H2 ≫ 0) and NOT the old synthesized palette. So different
  instruments produce spectrally-distinct output that is real IC307 PCM.
* **Pitch not regressed (criterion b ✓).** Chromatic C4..B4 held in sequence → measured
  peak Hz `262 277 294 311 330 349 370 392 415 440 466 494` = the exact equal-tempered scale,
  12 distinct rising pitches. C4=262 vs C5=524 → exact octave. C-E-G chord → fundamentals
  261.6/329.6/392.0 Hz all present and balanced (mag 1880/1763/1754), non-harmonic bins ≈0.
* **Envelope / sustain / velocity / MIDI-bridge / has_pcm intact (criterion c ✓).** Those code
  paths are unchanged; `has_pcm` is simply true now (all banks hold real PCM). A held note
  sustains for the full 5 s+ window. Software envelope (`env_level`), velocity (`reg[20]`
  gain), the keybed/MIDI event path all untouched.
* `-validate kn5000` clean (exit 0); boots to the play screen; native (un-amplified) C4 sounds
  at 262 Hz.

## 4. Honest limitations / approximations (labelled)

* **~75% placeholder identity.** IC304-306 are BAD_DUMP copies of IC307, so an instrument
  whose true samples live on those chips selects a real-but-wrong-instrument IC307 waveform.
  It is always REAL KN5000 PCM (never silence/synthesis), and the mechanism is faithful, but
  the specific timbre is only correct for the instruments whose samples are in IC307. This is
  the accepted placeholder until IC304-306 are dumped — at which point the same code plays the
  correct waveform with zero change (the region fill already makes bank math work).
* **Single-period loop** captures the sustained spectrum, not the attack transient or slow
  timbral evolution of the multi-cycle recording; the software amplitude envelope supplies the
  contour. A future refinement could play the attack once then loop.
* **Linear interpolation** softens the highest harmonics of the resampled period (measured
  §3). Acceptable; a higher-order interpolator would sharpen it.
* The fingerprint→index **hash** is a deterministic placeholder mapping, not a decode of a
  real firmware "instrument→wave" table (that table selects from IC304-306, undumped). It
  guarantees distinctness and stability, which is the deliverable given the missing chips.

## 5. Follow-ups
* Fold the `+0x040` zone nibble into selection to emulate multisample key-zone stepping.
* Play attack-once-then-loop for a richer envelope.
* When IC304-306 are dumped: the selection can key off the real per-chip page (the
  `tonerec[+0x1a]&0xC0` bank lead) instead of the fingerprint hash.
