# KN5000 IC303 — what the audit pass ACTUALLY changed (and what it deliberately did not)

Implementation pass following the six audit dimensions (`kn5000-audit-{registers,timbre,pitch,
amplitude,voicelife,output}.md`) and their adversarial verifications. Requested by Felipe Sanches,
2026-07-26.

Evidence labels as in the audits: **MEASURED** (ROM bytes / disasm line / a value read off a running
machine) / **INFERRED** / **CALIBRATED** (a free constant, bounded by data but not derivable).

Everything below is register-only: the HLE's inputs remain the address latch `0x100000`, the data
port `0x100002` and the key-bed port `0x110000`. Nothing reads sub-CPU RAM at runtime.

---

## 0. TL;DR

| # | change | evidence | audible effect |
|---|---|---|---|
| 1 | **`+0x100` is the per-voice TVF (filter/brightness) and is now rendered** | 12/12 predict-then-check, 3 of them live this pass | Bright / Piano / Mellow Piano are no longer the same sound |
| 2 | **Key-bed velocity: the five BLACK KEYS have their own inverse table** | ROM tables, exact | a black key was -6.34 dB against the same white key; now -0.32 dB |
| 3 | **The release fade starts from the level the note was HELD at** | `+0x800` low-byte bit 7, MEASURED 4 writers | the key-up CLICK (a 54 dB single-sample collapse) is gone |
| 4 | **`process_key_off` is idempotent** | two callers, 41 ms apart, MEASURED | a released note can no longer be re-armed to full amplitude |
| 5 | four wrong comments corrected, one stale recommendation struck, docs-site fixed | — | none |

**Deliberately NOT shipped, with the reason MEASURED, not assumed:** unmuting the accompaniment
(§3.1). It is a genuine defect, it was implemented, it was measured, and it makes the instrument
*worse* until a second, still-undecoded thing is decoded. That measurement — and the disproof of the
"per-tick software envelope" model that three of the six audits rest on — is the most important
finding of this pass.

---

## 1. THE HEADLINE: `+0x100` is a filter, and it is now rendered

### 1.1 What was wrong

Three PIANO variants that are **byte-identical in every register the HLE read** — captured live on
the sub-CPU bus this pass, voices 0-5, one C4 at the driver's fixed `KEYBED_VELOCITY = 100`:

```
                +040          +400   +800    | +080   +0C0  +100  +140
 Piano          7007 / 7017   34C1   E57F    | 0E52   7400  2466  6FDA
 Bright Piano   7007 / 7017   34C1   EA7F    | 0E64   5A00  2470  5BDA
 Mellow Piano   7007 / 7017   34C1   EA7F    | 0EC2   5A00  2450  5BDA
                ^^^^^^^^^^^   ^^^^   ^^^^      the HLE read NONE of these
                the HLE read these
```

Bright and Mellow agree in `+0x040` (same recording), `+0x400` (same pitch) **and** `+0x800` (same
level). They can only differ through registers the device ignored.

### 1.2 The decode (MEASURED)

Chain: note-on `LABEL_02B4E3` (v142 asm **L26803**) → `LABEL_024102` (**L16748**) → `LABEL_023D01`
(**L16312**) → `LABEL_022C06` (**L14509**) → clamp `LABEL_022BF2` (**L14494**) → emitter
`LABEL_024444` (**L17106**) → `ToneGen_WriteVoiceParams` L29619.

```
V = clamp( VP[0x4d] + (int8)PART[0x67]
           + ((int8)VP[0x37] * (int8)KSCURVE[VP[0x36]>>5][velocity & 0x7F]) >> 5   ; velocity curve
           + ((int8)VP[0x3c] * (clamp(note,VP[0x3a],VP[0x3b]) - VP[0x39])) >> 5    ; key follow
           + 0x18 , 0, 0x78 )
+0x100 = ((VP[0x4e] & 7) << 13) | 0x0400 | V
```
(`>>5` is `SRA 5`, a flooring shift; `MULS` is signed; KSCURVE = 7 x 128 signed bytes at 0x011519.)

**BIT 10 IS THE GATE, and it is exact.** `SET 0ah` occurs at exactly six places in the whole
sub-program — asm **L16346, L16429, L16476, L16542, L16790, L16832** — and **all six store to
`desc+0x42`**, i.e. to this register. Every builder that computes a cutoff sets it; nothing else in
the ROM sets it. The firmware's own "no TVF" constant is `0x017F` (`LABEL_022DA1`, asm **L14697**)
and the percussion path ships `0x0000`: both leave bit 10 **clear**.

That matters concretely. The obvious alternative gate — "0x7F means bypass" — would have rendered
every **drum kit** with a *closed* filter: Brush / Dance / House / Electric / Synth / Sound-Effect
Kit all compute `V = 0`, and they reach the chip as `0x0000`. Bit 10 classifies them correctly as
"no filter".

The emitter's live controller offset (`LABEL_024366`, asm **L17006**) does
`AND WA,0ff80h / OR WA,HL`, so it replaces only the low 7 bits and bit 10 survives — which is why
the filter coefficient is recomputed on **every** `+0x100` write rather than sampled at key-on.

### 1.3 PREDICT-THEN-CHECK — 12/12

Recomputed from the ROM bytes with an independent script (`scratchpad/tvf.py`), no reference to any
audit's numbers:

| check | result |
|---|---|
| Piano at C4, velocity 100 | 0x66 **HIT** |
| Piano / Bright / Mellow at C4, effective velocity 58 (the older capture) | 0x4E / 0x61 / 0x45 **3/3 HIT** |
| Piano at C2/E4/G4/A4/C6, velocity 100 | 0x66 / 0x67 / 0x68 / 0x69 / 0x6D **5/5 HIT** |
| **live this pass**, Piano / Bright / Mellow at C4, `KEYBED_VELOCITY = 100` | `0x2466` / `0x2470` / `0x2450` → V = 102 / 112 / 80 **3/3 HIT** |

The last row is the load-bearing one: it was predicted from the patch bytes *before* the run.

### 1.4 The one CALIBRATED constant, and what bounds it

How many cents of cutoff one unit of V is worth belongs to the undumped LSI. It is **bounded by the
firmware's own data**, and the bounds pick the value:

* **`V = 0x78` must be effectively open.** It is the clamp ceiling; **504 of the 1046** partial
  blocks reach it at velocity 127, and they include *Applause*, *Gun Shot* and *Helicopter* —
  broadband recordings that cannot be dull. ⇒ `FC(0x78) ≈ 20 kHz`.
* **No pitched stock patch may be silenced.** The darkest patch-level value in the whole table is
  **V = 32** (*Vocal Ah*, both partials, C4 at velocity 100). Keeping its first formant (~800 Hz)
  requires **≤ 63 cents/unit**. At the 100 cents/unit that would make the key-follow depth `0x20`
  exactly 1:1 — the "natural unity point" the timbre audit proposed — *Vocal Ah* would sit at
  **202 Hz**, i.e. inaudible. **100 cents/unit is REFUTED by the firmware's own patch data.**

**50 cents/unit** is taken: safely inside `(0, 63]`, it puts the floor of the entire computed range
(`V = 0`) at **625 Hz** so the filter can never silence a voice, and it makes the measured
ppp→fff swing of a median block (36 units) 1.5 octaves of brightness.

The filter **slope** is likewise not decoded (the main-CPU Sound Editor has LPF/HPF/BPF/BCF pages,
so a *type* selector exists; `+0x100` bits[15:13] and bit 7 are the only plausible carriers and
neither is established). **One pole** is the minimal, conservative choice, and it is labelled as such
in the code.

### 1.5 BEFORE / AFTER (MEASURED)

Method: the same note slot rendered by the pre-change binary and by the new one. The register stream
is **byte-identical between the two runs** (verified write-for-write), so the audio delta is the HLE
change and nothing else. Piano / Bright Piano / Mellow Piano, C4 + C5 + C6, key-bed velocity 100,
1.5 s window from the onset. `E>3k` = fraction of spectral energy above 3 kHz.

```
                    V    fc        centroid          E>3k                 level
  Bright Piano C4  112  15874 Hz   -0.28 %           -4.98 %              -0.006 dB
  Bright Piano C5  112  15874 Hz   -0.14 %           -3.14 %              -0.004 dB
  Bright Piano C6  112  15874 Hz   -0.16 %           -3.29 %              -0.010 dB
  Piano        C4  102  11892 Hz   -0.54 %           -9.41 %              -0.011 dB
  Piano        C5  102  11892 Hz   -0.27 %           -6.27 %              -0.009 dB
  Piano        C6  102  11892 Hz   -0.29 %           -6.86 %              -0.020 dB
  Mellow Piano C4   80   6300 Hz   -1.68 %          -27.60 %              -0.039 dB
  Mellow Piano C5   80   6300 Hz   -1.06 %          -23.72 %              -0.041 dB
  Mellow Piano C6   80   6300 Hz   -1.34 %          -26.94 %              -0.129 dB
```

**9/9 monotone in the firmware's own cutoff value** (112 > 102 > 80 ⇒ progressively more HF
removed), across three octaves, with the level essentially unchanged (≤ 0.13 dB). It is timbre, not
loudness, and the *sample* is untouched — `+0x040` is identical for all three, so all three are still
the same piano recording.

Bright vs Mellow directly, onset-aligned, C4:

```
                 BEFORE                          AFTER
  E(>3k)         0.2004 % -> 0.1915 %  (-4.4 %)  0.1904 % -> 0.1387 %  (-27.2 %)
  centroid       384.4 Hz -> 387.7 Hz  (+0.9 %)  383.3 Hz -> 380.9 Hz  (-0.6 %)
```
BEFORE, the -4.4 % is render-phase noise with the *wrong sign* (Mellow measured slightly *brighter*
than Bright); Piano vs Bright before is 0.2004 % vs 0.2004 %, residual 0.0019 — the two are the same
audio up to a gain, exactly as `kn5000-variant-diagnosis.md` §3.1 reported. AFTER, the difference is
systematic and in the direction the firmware's cutoff dictates.

### 1.6 Honest note on the SIZE of the effect

The absolute change is small on these notes, and the reason is **a different, still-open gap**, not
the filter: IC307 page 3 chunk 0x07 (the C4 piano layer) has its own fundamental at **~1077 Hz** and
99.97 % of its energy between 1 and 6 kHz, and the HLE plays it for C4 by stretching it ~2 octaves
down, so its harmonics land below 3 kHz where a 6.3-15.9 kHz low-pass has little to act on. That
stretch is the pitch dimension's known "per-chunk root pitch is not decoded" gap
(`kn5000-audit-pitch.md` GAP 6). The filter is correct and monotone; how much of it you *hear* on the
piano will grow when the root-pitch gap closes.

---

## 2. THE OTHER FIXES

### 2.1 Key-bed velocity: the black keys have their own curve (MEASURED, exact)

`ToneGen_Calc_Pitch` (asm **L51595-L51616**) divides the note by 12 and, when the remainder is
**10, 8, 6, 3 or 1** — A#, G#, F#, D#, C#, since MIDI 36 (the bottom of the 61-key bed) is a C —
subtracts `TOUCH[mode*3+2]` (table 0x01F422, **= 16** at the power-on touch mode 6) from the
intermediate before the velocity lookup. A black key must be struck harder for the same velocity,
which is what a real key bed does.

The driver had one inverse table. Feeding it for a black key under-reports by a mean of **13.5** and
up to **16** velocity units (recomputed from the ROM this pass). Both tables are now derived as
`raw = argmin |firmware(raw, keyclass) - v|`:

* white 117/127 exact, max error 1 (the previously shipped table scored **97/127**, max error 2 — so
  the white keys get slightly *more* accurate too);
* black 109/127 exact, max error 1;
* velocity 100 — the fixed velocity the PC-keyboard path uses — maps to raw 42 in **both** the old
  and the new white table, so that path is bit-identical.

MEASURED end to end, C4 vs C#4 at the same MIDI velocity 100: **-6.34 dB → -0.32 dB**.

### 2.2 The release fade starts from the HELD level — the key-up click is gone

The firmware's release burst (`LABEL_02D436`, asm L29936) writes, in order,
`+0x840, +0x940, +0xA00, +0x800, +0x900, +0x9C0` — MEASURED byte-for-byte on the bus:

```
  26.338045 840 8B00 | 26.338048 940 AE00 | 26.338051 A00 4FB0
  26.338054 800 8B80 | 26.338057 900 AE00 | 26.338060 9C0 4FB0
```

`+0x800` (the ramp's **target** level, 0x8B = gain 0.0017) lands **before** the `+0x900` that our
release detector keys on, so `update_voice_params` collapsed the voice by 54 dB in a single sample
and the 50 ms fade then operated on already-silent audio. That is the key-up click.

The discriminator is register-only and needs no timing: **the low byte of `+0x800` carries bit 7 iff
the write is an update rather than a note-on level program.** A note-on level is built by
`LABEL_025636` (asm **L19078-L19085**) as `(level<<8) | TAB_011963[rec+0x28]`, and `TAB_011963[0..100]`
runs 0x00..0x7F — bit 7 clear. Every periodic/release update goes through `LABEL_026769` →
`LABEL_02682F` (asm **L20831-L20838**), which does `SET 7`. Live capture agrees exactly: note-on
`0xE57F` / `0xD17F` / `0xDA7F`, pre-note mute `0xFF80`, key-up `0x8B80`, panic `0xA280`.

So the level the voice was *programmed* with while held is latched, and the release fades from it.
We do **not** pretend to walk to the firmware's target: the chip's ramp **rate** is not decoded, and
inventing one would replace a measured defect with an invented constant.

MEASURED, the 3 s held note's release (20 ms windows, rms):

```
  before   2952 -> 2230 ->    3.5 ->   2.6      (a 54 dB step; the click)
  after    2950 -> 2795 -> 1940   -> 786 -> 21 -> 0
```
Both monotone, no rise. The "after" is the 50 ms fade actually doing its job.

### 2.3 `process_key_off` is idempotent

It is reached from two places — the group-9 release heuristic and the firmware's own `0x7E00` — and
MEASURED, the `0x7E00` arrives **41 ms after** the heuristic has already fired. Re-arming
`release_counter` there restarted the fade at full amplitude, i.e. a released note getting *louder*
again part-way through its release. Now guarded on `key_on`.

### 2.4 Comments and documentation corrected

* `data_w` group0/bank0: the "per-tick software envelope written every audio tick" model is
  **disproved** (§3.1) and the comment now states what the word actually is.
* `data_w` group0/bank2: bit 15 of `+0x080` is the burst **load strobe** (SET at asm L29594, RES at
  L29907), not a "waveform pointer latch".
* `data_w` release detection: "the sub-CPU never writes a 0x7E00 when a held key is released" is
  **false** — it does, from `LABEL_02B4A1` (asm L26770), once its voice manager sees the chip report
  the voice silent.
* `process_key_on`: the resolve reads `+0x040` (regs[1]), not "regs[9]/regs[10]".
* `update_voice_params`: records *why* pan stays centred — every firmware updater writes the **same**
  value to both members of a group-8/9/10 pair (`LABEL_02682F` L20831-20838, `LABEL_026A93`
  L21080-21086, `LABEL_026AAA` L21209-21212, `LABEL_02D620` L30130-30150), which an L/R gain pair
  cannot do.
* `softclip`: the old comment claimed the mix "passes through UNCHANGED below the knee". It does
  not — `HEADROOM = 0.70` is applied to everything. The constant is **not** changed (it is doing real
  anti-clip work: the C-E-G chord peaks at 97.9 % FS *with* it), only the comment.
* `notes/kn5000-tonegen-register-semantics.md` item 3 (`gain_L = reg[20]>>8, gain_R = reg[21]>>8`) is
  **struck**, with the evidence, so nobody implements it later.
* `kn5000-docs/audio-subsystem.md` — the tone-generator bullet list still described a pan model, a
  pitch model and a waveform register that the device has not used for months. Rewritten.

---

## 3. IMPLEMENTED, MEASURED, AND DELIBERATELY REVERTED

### 3.1 The accompaniment mute — and the disproof of the "per-tick envelope" model

`kn5000-audit-registers.md` GAP 1, `kn5000-audit-amplitude.md` GAP 1 and
`kn5000-audit-voicelife.md` GAP 8 all report the same defect: `env_level = min(data & 0x1FF, 0xFF)`
turns the accompaniment's bare `0xF000` into amplitude **0**, and the whole rhythm section renders at
-81 dB. All three are right that the reading is wrong. **All three are wrong about what the word is.**

The word is `slot[+0x2d]`, and it is a **HAND-OFF**, not an envelope:

* it is built by `LABEL_025589` (asm **L18856-L18906**: `mag = 0xFF - 4*(VP[0] & 0x3F)`, `SET 8` iff
  `VP[0] != 0`) or by `LABEL_0255F3` (asm **L18907-L18942**: a **bare** `0xF000`/`0xFE00` with no
  magnitude field at all) — and **both only STORE it into `slot[+0x2d]`**; neither writes the chip;
* **all five** places that ship `slot[+0x2d]` to `+0x000` — asm **L21485, L24100, L24137, L29209,
  L29242** — call `LABEL_022587`, *free the channel*, on the very next line;
* **MEASURED on the live bus this pass** (PC-tagged): it is written **exactly once per note**, from
  `ToneGen_WriteSingleReg` (PC **0x02D42F**), **42 µs** after the gate for a rhythm voice and
  **0.5 ms** after it for a key-bed voice. A 3-second held C4 receives exactly one (`0xF0FF` at
  +0.5 ms) and then **nothing at all** until its release. Over the whole key-bed battery the
  group0/bank0 census is `8100 x44, F0FF x44, 7E00 x44` — one hand-off per note, no per-tick traffic
  of any kind.

So there is no per-tick software envelope on this register. The firmware programs the note, gates it,
ships the hand-off word and **stops managing the note**; the chip's own envelope owns it from there.
The low bits are a per-partial parameter of that hand-off whose meaning is **not established**.

**Why it is not shipped.** Not silencing the handed-off voices was implemented and measured:

```
  rhythm 21-37 s, 16-Beat-1 at the power-on setting
    before / after revert   rms     7.09    peak  5390      (the -81 dB mute)
    with the mute lifted    rms 24720.81    peak 32767      (0.75 FS, rail-pinned)
                            ... and still rms 26126 after STOP was pressed
```

A saturated drone that outlives the STOP button. The cause is the *other* half of the same gap: once
the firmware has handed a voice off and freed its channel it can never send that voice a `0x7E00`, so
on real hardware **the chip must end the note by itself** — and how it does that is exactly what is
still undecoded. Our `status_r` answers "gated on", so the firmware never reclaims the channel
either; MEASURED, voice allocation runs 0,1,2,…,63 and wraps.

I also implemented and reverted the obvious candidate ending rule ("a recording with no measurable
fundamental is a one-shot: play it once and stop"). It did not stop the drone — the rhythm chunks
in play are *not* classified aperiodic — and on its own it can only cut a held aperiodic note
(applause), so it is a risk with no benefit. Reverted.

**Net:** the two defects currently cancel, and lifting only one of them regresses the instrument.
The mute stays, with the full evidence recorded in the code so the next pass starts from the right
model. **The next thing to decode is how the chip ends a handed-off note** — the sustain-loop
information in IC307's per-chunk parameter records is the obvious candidate, and it is also what
`compute_loop` currently has to derive.

### 3.2 `+0x080`'s 12-bit log level — SKIPPED, with evidence

`kn5000-audit-timbre.md` §1.5 decodes `+0x080` bits[11:0] as `256·log2(level)` (exact: the live
`0x0E52` is `2 x LOGTAB[228]`), and its "missed gap 1" proposes folding it in as a second per-voice
level — it is one of the four registers separating Bright from Mellow (Bright `0x0E64` vs Mellow
`0x0EC2` = 94 units = **+2.2 dB**).

**Not implemented, because it is velocity-scaled and the velocity is already folded into `+0x800`.**
MEASURED from the archived velocity sweep (`vd/vcap_A.log`, plain Piano at C4, read with the
*corrected* velocity polarity, so effective velocity rises down the table):

```
  effective velocity  ~46   ...  ~126
  +0x080 low 12       3048  ->  3904   = 856 units at 256/octave = 3.34 oct = 20 dB
  +0x800 high byte     204  ->   254   =  50 units at K=10       = 5 oct    = 30 dB
```

Both carry the velocity. Multiplying them together would give a ~50 dB velocity span against the
~17.5 dB the instrument currently produces — precisely the double-count the existing code comment
warns about, only with the sign of the error now understood. Its absolute reference is not derivable
either. Correctly left alone; the timbre difference is carried by `+0x100`.

### 3.3 Everything else that was NOT implemented

| audit item | verdict | why not |
|---|---|---|
| registers GAP 2 — walk the group 8/9/10 4-segment EGs | REFUTED consequence + unsafe | Bright and Mellow have **byte-identical** EG-A words, so it cannot separate them; and under the shipped level law a segment-2 target of 0x40 is **-99 dB**, so a naive stepper silences every held piano note |
| registers GAP 6 — `+0x180` is pan | REFUTED | the firmware forces it to `0x7F` on an output-bus assignment; the sibling audit reads the same register as expression. Two audits, opposite meanings, same data ⇒ not decoded |
| registers GAP 7 — `+0x100/+0x140` are an LFO | REFUTED | `+0x100` is the TVF (implemented above, 12/12); shipping vibrato the instrument does not have would be inventing |
| timbre GAP 2 — `+0x140` | decode exact, meaning **not established** | the audit itself says do not ship a guess |
| timbre GAP 3 — `+0x080` bits[14:12] pitch class | meaning **not established** | repeats per octave, so it is not a level or a key-scale; needs hardware |
| timbre/registers GAP on `+0x0C0` | scale not derivable | and it is `0x5A00` for **both** Bright and Mellow, so it does not touch the headline problem |
| amplitude GAP 2/3 — `REF = 255`, pin `K` from service mode | blocked | `REF = 255` alone drops the whole instrument by 14.4 dB; it is only safe jointly with a `K` measured from the "16 dB DOWN" service test, which is a hardware run |
| output GAP 3 — 44 100 Hz vs 48 000 Hz | deferred | must change `stream_alloc` and the `step` divisor in one commit or every note goes 8.8 % flat; only 44 aperiodic chunks change audibly, and the tone-generator's own rate is INFERRED, not measured |
| voicelife GAP 5 — decode the release burst by signature | **do not adopt** | the adversarial verification found `LABEL_027FD6` (asm L23045-23142) emits the byte-identical six-register burst, so the signature is not unique, and `LABEL_02CD71` has 10 call sites including MIDI-CC handlers |
| output GAP 7 — raise `HEADROOM` | rejected | it is doing real work: the C-E-G chord peaks at 97.9 % FS *with* the 0.70 trim. Comment fixed instead |

---

## 4. NO-REGRESSION VERIFICATION

Battery driven through the `-kbdmidi` (internal key bed) port, default power-on Piano, isolated
nvram copy; the **same MIDI file** rendered by the pre-change binary and the final one.

| check | before | after |
|---|---|---|
| chromatic C4..B4 | 12/12 distinct, monotonic, worst 11.2 cents | **identical** |
| octave C4 → C5 | 2.0000 (+0.0 cents) | **identical** |
| chord C-E-G, all three present | 260.7 / 328.1 / 389.7 Hz | **identical** |
| chord not clipped | peak 32089 / 32767 | 32075 |
| velocity direction (30 vs 120) | 7.48x (+17.5 dB) | 7.53x (+17.5 dB) |
| sustain of a 3 s held note | 6234 → 2990 rms | 6227 → 2988 rms |
| release monotone, no rise | pass (but a 54 dB cliff) | pass, **smooth** (§2.2) |
| black key vs white at the same velocity | **-6.34 dB** | **-0.32 dB** |
| accompaniment (16-Beat-1) | rms 7.09 | rms 4.07 |
| `-validate kn5000` | clean | clean |
| boots to the PMEM play screen | yes | yes |
| **7/7 battery** | 7/7 | 7/7 |

Sample selection is untouched: the wave-select decode, `decode_wave_select()` and
`resolve_waveform()` are unchanged, and the three piano variants render the same `+0x040` before and
after.

---

## 5. REPRODUCTION

```
# the TVF decode, recomputed from the ROMs and checked against the live captures
python3 <scratchpad>/tvf.py            # 9/9 static + the V distribution that bounds the constant
python3 <scratchpad>/keybed.py         # both key-bed inverse tables + their round-trip scores

# live A/B: same sound, two builds, identical register stream
cd kn7000-emulator
ABOUT=<out> ABKEYS="L1,L2,L1p2" ABNOTES="C4:KEY2:1,C5:KEY3:1,C6:KEY4:1" T_BASE=22 SLOT=10 HOLD=1.6 \
  timeout 400 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo -window -nomaximize \
    -nvram_directory <COPY of scratchpad/nvram2> -autoboot_delay 0 -autoboot_script <s>/tvf/ab.lua \
    -seconds_to_run 54 -nothrottle -wavwrite <out>.wav
python3 <s>/tvf/xcmp.py before.log before.wav after.log after.wav   # per-slot spectral delta

# regression battery
python3 <s>/tvf/mkreg.py reg.mid
./kn7000 kn5000 ... -midiin2 reg.mid -seconds_to_run 46 -nothrottle -wavwrite reg.wav
python3 <s>/tvf/reg.py reg.wav

# NOTE: the key-bed MIDI bridge is MAME's SECOND midiin instance -> use -midiin2 <file>,
# not -kbdmidi (that is the slot-device option and will not take a filename).
```

Panel note (page 1 of the PIANO sound group): `L1 = Piano`, `L2 = Bright Piano`, `L3 = Piano 1
Octave`; `Mellow Piano` is `L1` on **page 2** (press `CPL_SEG2:0x80` after the group button). The
harness reads the selected patch name back out of the live tone record, so a mis-press is visible
rather than silent.
