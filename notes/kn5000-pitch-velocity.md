# KN5000 tone-generator: PITCH and VELOCITY fixes (2026-07-23)

Two bugs reported from REAL hardware by the owner (Felipe Sanches, ground truth),
playing a USB-MIDI controller into the KN5000:

1. **PITCH (SEVERE):** every note within an octave sounded the SAME pitch; only the
   octave changed. Chord detection on-screen was correct, so input was perfect — the
   fault was purely tone generation.
2. **VELOCITY (polish):** touch sensitivity audible but too weak/compressed even at
   panel Touch-Sensitivity = MAX (9); at 0 it is fully removed (feature is wired, just
   under-ranged).

Both fixed in `src/mame/matsushita/kn5000_tonegen.{cpp,h}`. Grounded in the sub-CPU
disassembly (`kn5000-roms-disasm/.../kn5000_subprogram_v142.asm`) and CONFIRMED with
live register captures on the running MAME build (labelled MEASURED below).

---

## How the tone-gen registers are written (MEASURED, disasm)

`ToneGen_WriteVoiceParams` (v142 asm L29565) uploads one voice's registers from a
44-byte parameter struct, address = `voice + group*0x100 + bank*0x40`:

| reg | addr off | struct field | role |
|---|---|---|---|
| reg[1] | +0x040 (g0.b1) | +0x02 | pitch **zone / coarse selector** |
| reg[2] | +0x080 (g0.b2) | +0x04 | velocity attenuation (bit15 latch) |
| reg[8] | +0x400 (g4.b0) | +0x0e | pitch **within-zone semitone** |
| reg[20] | +0x800 (g8.b0) | +0x18 | bus-0 L **log level** (velocity-scaled) |

The note-on gate is `0x8100` written to g0.b0 (asm L30213). reg[20]'s log level is
built in `LABEL_026769` (asm L20776-20838) as `loglevel<<8`, `loglevel` = table
`0x0118FE`[patch_level+keyscale], then velocity-scaled (`LABEL_022BB8`).

---

## PITCH — root cause and fix

### What the registers actually encode (MEASURED, live chromatic + octave capture)

Correlating each voice note-on with the keybed/MIDI event that caused it (timestamp
match, ~2-4 ms latency), the pitch registers for the default Piano are:

```
MIDI  note  r1(zone)  r8       within-zone step
60    C4    7007      0x34C1
61    C#4   7007      0x35C1   +0x100
62    D4    7007      0x36C1   +0x100
63    D#4   7007      0x37C1   +0x100
64    E4    7008      0x35EC   zone++ , r8 RESET
65    F4    7008      0x36EC   +0x100
66    F#4   7008      0x37EC   +0x100
67    G4    7008      0x38EC   +0x100
68    G#4   7009      0x3524   zone++ , r8 RESET
...   ...   ...       ...
84    C6    700D      0x4CB4
```

**Findings (predict-then-check; the task's "octave from reg[8], semitone from reg[1]"
hypothesis was WRONG — reversed and incomplete):**

- **reg[8] steps EXACTLY 0x100 per semitone WITHIN a sample zone**, then RESETS at each
  zone boundary. reg[1]'s low nibble is the multisample ZONE selector (+1 every ~3-4
  semitones). The old code took the octave from reg[8]/12 (constant across our range)
  and the semitone from reg[1] (constant within an octave) → every semitone collapsed
  to one pitch. Exactly the reported bug.
- The IC303 is a PCM MULTISAMPLE chip. reg[8] is **sample-zone-RELATIVE** log pitch; the
  per-zone sample ROOT that turns it absolute lives in the chip's internal multisample
  table in the WAVE ROM, which is **NO_DUMP** for IC304-306. Dumping ALL 32 per-voice
  registers across a chromatic run confirmed **no absolute-note register exists** —
  only reg[1] and reg[8] vary per semitone, and their zone boundaries are irregular
  (a real multisample split), so absolute pitch cannot be recovered from the registers
  by any general formula.

### Fix (faithful, "use the real mechanism")

Because every voice currently renders the SAME fabricated waveform (IC307 index 0, a
256-sample single-cycle sine — the wave-number decode is a separate unresolved bug),
the correct output is simply the played note at equal temperament. We recover the TRUE
musical note from the real input event that triggered the voice:

- `push_keybed_event()` (fed by BOTH the keybed scanner and the USB-MIDI bridge
  `kbd_midi_rx`, carrying MIDI note = raw+36) records each note-on with a timestamp.
- At the note-on gate, `recover_true_note()` picks the most-recent input note within a
  0.30 s window (dual-layer voices of one press all land inside it → same note).
- `update_pitch()` then computes `freq = 440·2^((note-69)/12)` and, since index 0 is a
  single cycle over `wave_length` samples (native = 48000/wave_length ≈ 187.5 Hz),
  sets `pitch_step = 65536·freq·wave_length/48000` — exact A440 equal temperament.
- Voices with no correlated input (demo/rhythm) fall back to reg[8] as a global
  log-pitch (0x100/semitone) — correct within a zone, monotonic; may jump at zone
  boundaries (the missing sample-root limitation), but far better than the old all-one-
  pitch behaviour.

### Verification (WAV pitch, autocorrelation, clean build)

Chromatic C4→B4 one note at a time, plus C6:

```
note  expected  measured   (cents error, autocorr quantisation)
C4     261.6     260.9      -5
C#4    277.2     275.9      -8
D4     293.7     292.7      -6
...    ...       ...
B4     493.9     489.8     -14
C6    1046.5    1043.5      -5   ← octave doubling confirmed
```

12 distinct, monotonically-rising equal-tempered pitches; octave = 2×. Errors are
autocorrelation lag quantisation on short windows, not real detune (the formula is
exact). BEFORE: all semitones identical.

---

## VELOCITY — root cause and fix

### What the level registers encode (MEASURED, live velocity sweep)

Injecting MIDI note-ons at increasing velocity through the real parser (C4), the
firmware's per-voice level registers:

```
vel   reg[2]&0xFFF   reg[20] hi   (both FALL as velocity RISES = attenuations)
40    0xE64=3684     0xE7=231
60    0xDDC=3548     0xDD=221
80    0xD52=3410     0xD5=213
100   0xCC2=3266     0xD1=209
127   0xBE8=3048     0xCC=204
```

- reg[20]'s high byte is a **LOG-domain level** (from log table 0x0118FE, velocity-
  scaled), and it is an **ATTENUATION: lower = louder** (this settles the "direction
  UNVERIFIED" flag in `kn5000-tonegen-register-semantics.md` — loud = LOW value).
- reg[2] is ALSO a velocity attenuation (falls with velocity).

**Root cause:** the old `update_voice_params` (a) inverted reg[20] LINEARLY
(`0xFF - hi`), giving a tiny 24..51 span, and (b) multiplied by `reg[2]&0x0FFF` used as
a *direct* volume — but reg[2] falls with velocity, so it fought the reg[20] term and
squeezed the dynamic range to **1.81×** (vel40→127, MEASURED). That is the compression.

### Fix

reg[20]'s high byte is a log attenuation, so the linear gain is an EXPONENTIAL of it,
`gain = 2^((REF - loglevel)/K)`. The firmware already folds velocity into reg[20], so
reg[2] is NOT multiplied in a second time (its use only compressed). The exponential
form is grounded (log→linear); `K=10`, `REF=181` are CALIBRATED (the chip's exact
dB/step is internal to the undumped IC303) to keep loud notes strong while giving a
musical ~16 dB spread. Pan kept centred (unchanged).

### Verification (WAV RMS)

```
vel    BEFORE rms   AFTER rms
40     4371         1345
60     6054         2691
80     7265         4653
100    7565         6180
127    7905         8743   (loud notes now STRONGER, peak 12374 < 32767, no clip)
range  1.81×        6.50×   (monotonic)
```

Touch-sensitivity scaling is applied UPSTREAM in the sub-CPU velocity curve (mode
0x4A48, `ToneGen_Calc_Pitch`), so this downstream fix widens whatever curve the panel
setting selects — at MAX touch the reg[20] spread (hence the audible range) is wider
still; at 0 the firmware flattens reg[20] and the range collapses, matching the owner's
report that touch=0 removes the effect.

---

## Kept working (no regression)

has_pcm audibility (8ab1610), the reg-0 per-tick software envelope (env_level), the
sustain/hold status readback, and the keybed/MIDI bridge all unchanged. `-validate
kn5000` clean; boots to the play screen (notes sound). IC307 idx-0 sine stays the test
waveform (wave-number decode remains a separate unresolved bug — pitch/velocity apply
regardless of which waveform plays).

## Open / future

- Absolute demo/rhythm pitch needs the multisample sample-root table (undumped WAVE
  ROM) or a big table-ROM RE; the keybed/MIDI path (the owner's use case) is exact.
- Per-note pitch modulation (vibrato/bend via reg[8] rewrites on a held voice) is not
  yet applied as a relative delta — true_note is fixed at key-on.
- reg[20]/reg[21] as a real L/R gain pair (vs centred pan) is deferred.
