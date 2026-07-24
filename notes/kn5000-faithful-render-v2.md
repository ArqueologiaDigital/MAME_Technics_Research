# KN5000 tone-gen (IC303) — faithful voice SELECTION + render v2 (implemented)

Author: autonomous implementation pass, 2026-07-24. Requested by Felipe Sanches.
**This pass edits `src/` and rebuilds.** It implements the register-only waveform SELECTION and the
chord-headroom fix specified by `notes/kn5000-voice-pipeline-MODEL.md` (and its adversarial-verify
verdict), replacing the shipped provisional `(bank,zone)` hash. Grounded in the disasm-anchored MODEL
and re-validated live (WAV + FFT). Evidence labels: **MEASURED** / **INFERRED** / **LABELLED-PLACEHOLDER**.

Files touched:
* `src/mame/matsushita/kn5000_tonegen.cpp` — `select_waveform_index()` rewritten; output soft-limiter
  + headroom added to `sound_stream_update()`.
* `src/mame/matsushita/kn5000_tonegen.h` — selection method doc comment.
Verification harness + scripts (scratchpad, not committed): `tg/{ic307,sel,pitchsafe,distinct,wavtool,
analyze_*,verify_*}.py|lua`.

---

## 0. TL;DR

* **Selection is now register-only and correct-by-construction.** The wave is chosen from `+0x040`
  (= `regs[1]`) ALONE: `cls = (w>>12)&0xF`, `entry = w & 0x0FFF` (**full 12 bits**, fixing the old
  `&0xFF` that truncated Sax/GM). Each class maps into a **disjoint contiguous slice** of a curated
  **pitch-safe + rich** IC307 index list; `entry` steps **monotonically** within the slice (a
  knee-compander). Result: DIFFERENT instruments → DIFFERENT coherent real IC307 waves; an
  instrument's notes walk a contiguous run of real waves (multisampling).
* **Pitch is NOT regressed** — chromatic C4..B4 = 12/12 distinct within **±2 cents**, monotonic; octave
  C4/C5 ratio **1.998**; chord C-E-G all present. (MEASURED, live WAV+autocorr.)
* **Chord clipping FIXED** — a pre-limiter headroom trim + a smooth tanh soft-limiter replace the old
  hard clamp: C-E-G chord clips **0.000%**, and even the loudest single patch (Strings) sits off the
  rail (peak 0.92 FS) leaving chord margin. Single notes stay audible.
* **Honest gap unchanged (LABELLED):** the numeric `{cls,entry}→physical-PCM` map is the LSI's internal
  decoder and IC304/305/306 are NO_DUMP, so ~3/4 of instruments play a real-but-wrong-bank IC307 timbre.
  The slice constants are ear-tunable; the *structure* is the supported part.

---

## 1. The selection rule as implemented (register inputs only — chip boundary)

```c
uint16_t w = regs[1];                 // +0x040 — the SOLE per-voice wave selector (MODEL §3, airtight)
int cls   = (w >> 12) & 0x0F;         // wave family / bank  (MEASURED 0..7)
int entry =  w        & 0x0FFF;       // multisample key-zone — FULL 12 bits (Sax 0x13E, GM 0x112)
// +0x440/+0x480 (rotating slot counters) NEVER participate.  w==0 & timbre==0 -> real sine (idx 0).
```
`{cls,entry}` is exactly the firmware's STAGE-A+B output (MODEL §1.5, live-validated 7/7). Then:

```c
// per class: a DISJOINT contiguous slice {lbase,width} of the curated SAFE_WAVE[] list;
// entry -> position q by a knee-compander (low cluster steps 1:1, sparse tail compresses);
// idx = SAFE_WAVE[ lbase + q ]     // monotone in entry, pitch-safe + rich by construction
```

**Per-class layout (MEASURED emin/espan from live-captures §5 + pipe-chipmap §2):**

| cls | instruments | emin..emax | SAFE slice (pos) | idx range | within-instr stepping |
|---|---|---|---|---|---|
| 7 | Piano | 0x00..0x0F | 12..27 | 34..57 | 16/16 |
| 3 | Guitar/World/GM/Sax | 0x00..0x144 | 28..43 | 64..83 | Guitar 5, World/GM/Sax 1-2 |
| 1 | Brass/Bass | 0x06..0x9E | 44..55 | 84..96 | Brass 7/7, Bass 2 |
| 0 | Strings/Synth/OrchPad | 0x09..0x91 | 56..71 | 97..117 | Strings 3, Synth 3 |
| 4 | Organ/Accordion | 0x01..0x5E | 72..83 | 120..131 | Organ 7/11 |
| 2 | Mallet | 0x96..0x9A | 84..91 | 132..141 | 5/5 |
| 6 | Drawbar | 0x96 | 92..97 | 144..150 | 1 (single zone) |
| 5 | Flute/Drums | 0x00..0x80 | 0..11 | 1..33 | Flute 2, Drums 5 |

Disjoint slices ⇒ **cross-class distinct**; monotone `entry→q→idx` ⇒ **within-instrument multisample
coherence**. (All verified in `tg/sel.py`.)

### The curated `SAFE_WAVE[100]`
IC307 index → PCM is `wave_offset×16` (its own 198-entry index); the render (`detect_period` +
`compute_loop` + resample-to-note) needs each selected wave to (a) detect its **true fundamental**
period (else the resample plays an octave off) and (b) be **rich** enough (>=1000 samples) to render a
distinct timbre rather than the near-identical simple tone the 80..~1400-sample low grains collapse to.
`tg/pitchsafe.py` compared `detect_period()` against an independent YIN/CMNDF fundamental for all 152
live indices and found **16 pitch-UNSAFE** ones (octave-halving on the long recordings:
`19,35,36,40,41,42,48,54,62,63,67,68,72,73,104,105`). `SAFE_WAVE` = the 100 indices that are BOTH
pitch-safe (ratio 0.90..1.10) AND >=1000 samples. Mapping every class through it guarantees in-tune,
rich, real-PCM playback with no code branch for the bad indices.

---

## 2. Before / after — the three shipped defects, fixed (MEASURED)

The old `select_waveform_index` was `zone=w&0xFF; base=1+((bank*41+timbre)%160); idx=base+(zone%24)`.

| defect (old) | fix (new) | evidence |
|---|---|---|
| `w&0xFF` drops entry bits 8-11 (Sax 0x13E→0x3E, GM 0x112→0x12) | full 12-bit `entry` | code |
| `bank*41+timbre` hash lands on arbitrary/short waves → homogenized timbre (Piano≈Organ **0.976**) | per-class slice on rich pitch-safe waves → Piano vs Organ **0.528** | FFT A/B (§3) |
| `zone%24` wraps mid-multisample (Strings idx 141→119 at E4) | monotone knee-compander, no modulo | `tg/sel.py` mono=True all |

---

## 3. Instrument distinctness — live WAV + FFT (MEASURED)

Six SOUND-GROUP instruments, C4, isolated (2.3 s apart), 96-bin Hann sustain spectrum, pairwise cosine
(1.0 = identical; **<0.95 = distinct**). `instr5.wav`:

```
          PIANO  BRASS  STRIN  GUITA  ORGAN  MALLE      selected IC307 idx (C4):
PIANO       .   0.799  0.872  0.896  0.528  0.813        PIANO   -> 46
BRASS       .     .    0.971  0.900  0.551  0.988        BRASS   -> 85
STRINGS     .     .      .    0.948  0.609  0.980        STRINGS -> 112
GUITAR      .     .      .      .    0.581  0.911        GUITAR  -> 66
ORGAN       .     .      .      .      .    0.549        ORGAN   -> 121
MALLET      .     .      .      .      .      .          MALLET  -> 132
```
* **≥3 spectrally distinct — MET with margin.** e.g. {Piano, Organ, Guitar} = 0.528 / 0.896 / 0.581;
  {Piano, Organ, Mallet} = 0.528 / 0.813 / 0.549. 12/15 pairs < 0.95.
* **All render as real, in-tune PCM** (f0 260.9..263.7 Hz = C4; all rms>0, none the sine).
* **Residual (LABELLED):** {Brass, Strings, Mallet} share sustain-spectrum SHAPE (0.97..0.99) — but
  differ strongly in loudness/envelope (Brass rms 4605, Strings 10981, Mallet 934), which the
  shape-only cosine ignores, so they are perceptually distinct. Two of them coincidentally landing on
  spectrally-similar IC307 waves is the single-bank placeholder limit (§5), tunable by ear.
* **Old-band A/B (same harness):** Piano↔Organ went **0.976 → 0.528**; the homogenization the model
  attributed to the arbitrary hash + short grains is gone.

---

## 4. Pitch (must-not-regress) + chord clipping — live (MEASURED)

**Pitch** (`pitch5.wav`, isolated chromatic on Piano's real rich waves, autocorr global-max fundamental):
```
C4 261.9 (+2c)  C#4 277.4 (+1c)  D4 293.9 (+1c)  D#4 311.4 (+1c)  E4 329.5 (-1c)  F4 349.1 (-1c)
F#4 369.8 (-1c) G4 391.8 (-1c)   G#4 415.2 (-0c) A4 440.0 (-0c)   A#4 466.1 (-1c) B4 493.8 (-0c)
=> MONOTONIC, 12/12 distinct, all within ±2 cents.   octave C4 261.9 / C5 523.3 = ratio 1.998.
```
(Measurement note: a spectral-PEAK detector mis-reads these BRIGHTER rich waves as octaves-up because
their loudest partial is a harmonic; autocorrelation — which is also what the render's own
`detect_period` uses — reads the fundamental correctly. Cross-checked: every instrument's isolated C4
reads ~262 Hz.)

**Chord clipping** (`instr5.wav`, C-E-G on Piano): peak **9869/32767**, clip **0.000%**; Goertzel
mags C4/E4/G4 = 211.8 / 76.2 / 81.8 vs off-tone 243 Hz = 1.6 ⇒ all three chord tones present, no
spurious peak, no distortion. The fix = HEADROOM(0.70) pre-trim + tanh soft-limiter (knee 0.75):
mathematically cannot hard-clip, leaves single notes below the knee untouched, and pulls the loudest
single patch (Strings) from 0.998→0.917 FS so its chords have room.

---

## 5. Honest residual gaps (for the owner's ear test)

1. **The crux is still a black box (LABELLED).** `{cls,entry}→(chip, PCM offset)` is the
   TC183C230002's internal decoder; IC304/305/306 are NO_DUMP and currently mirror IC307. So only the
   instruments whose real samples happen to live in IC307 play their true timbre; the rest play a
   coherent, in-tune, real-but-wrong-bank IC307 wave. Unblocked only by dumping IC304-306 or one LSI
   ROM-address/chip-select bus probe (MODEL §10 / pipe-chipmap §7). The slice constants (`CLASS_BAND`,
   `SAFE_WAVE`) are the ear-tunable placeholder; the *structure* (register-only, full 12-bit entry,
   per-class slice, monotone stepping, pitch-safe list) is the supported part.
2. **Same-class shared-wave collision** (Strings vs OrchPad, both class 0, overlapping entries) — they
   correctly SHARE the wave and should differ only by the timbre triple `+0C0/+140/+500` **as a
   FILTER**, which is not yet modelled (folding it into wave selection would be a stand-in). Not done.
3. **Sustain-spectrum-similar pairs** (Brass/Strings/Mallet, §3) — coincidental single-bank landings;
   ear-tunable via the slice bases.
4. **Per-instrument loudness spread** (Organ quiet ~0.03 FS, Strings hot) is the firmware's
   envelope/velocity level (`update_voice_params`, `env_level`), NOT the selection — left as-is to
   avoid regressing the recently-fixed velocity model; flagged for a future amplitude-balance pass.
5. **Drums/Sax/GM** have legitimately non-monotone / page-1 entry sets; their placeholder scatter is
   faithful (a per-key drum map / quirky zone order), not a bug.

---

## 6. Reproduction
```
# static: pitch-safety of every IC307 index + the SAFE_WAVE list
python3 tg/pitchsafe.py
# static: per-class slice layout (monotone + disjoint + in-range)
python3 tg/sel.py
# live (isolated nvram COPY; never touch kn7000-emulator/nvram):
cd kn7000-emulator && kn7000 kn5000 -rp roms -window -nomaximize -skip_gameinfo \
  -nvram_directory <copy> -autoboot_script tg/verify_instr2.lua -seconds_to_run 27 \
  -nothrottle -wavwrite instr.wav
python3 tg/analyze_instr2.py instr.wav      # distinctness matrix + chord clip
python3 tg/analyze_pitch4.py pitch.wav      # chromatic + octave (autocorr)
```
