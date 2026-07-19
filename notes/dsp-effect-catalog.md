# KN7000 effects-DSP catalog — what each SHARC program does

Companion to the committed disassembly tree at
`kn7000_disassembly/dsp/` + `kn7000_disassembly/disasm/dsp/` (regenerate with
`make disasm-dsp`). This note is the human-readable synthesis: the DSP's runtime
model, how the CPU selects/downloads effects, the **confirmed** effect-type →
record map, and per-record algorithm identifications.

Produced 2026-07-09 by a 13-agent reverse-engineering pass over the disassembly,
with the family groupings **verified by byte-diffing the extracted PM code** and
a consistency-critic pass. Legitimate preservation: everything here was
recovered from firmware we already have; no physical DSP or undumped ROM was
needed.

## 1. The device and the pool

IC306 is an Analog Devices **ADSP-21065L** ("SHARC", part `S21065LKS240`),
host-booted by the MN10300 — it has no boot ROM of its own. Its programs live in
the MN10300 program flash as **80 download records** at CPU
`0x486BCEC4..0x486CE68D`, streamed to the DSP host port (index `0x98000000`,
data `0x9C000000`). Record/block format and the verified PM repack recipe are in
`kn7000_disassembly/dsp/README.md`.

Roles: **1 kernel** (rec04), **4 SDRAM self-tests** (rec00–03, *not* audio),
**72 effect microprograms** (rec05–76), **3 LFO-waveform data records**
(rec77–79).

## 2. Runtime model (the kernel, rec04) — high confidence

The resident kernel is downloaded once at boot; every effect loads *on top of
it* at PM `0x8400`. From the disassembly (`disasm/dsp/rec04_kernel_*.asm`,
labels in `dsp/sym/rec04.sym`):

- **PM `0x8000` = interrupt vector table** (4 words/vector). Only two vectors
  carry real code: **RSTI** (`0x8004`: `IDLE` then `JUMP 0x8071`) and **IRQ0**
  (`0x8020`). Every other vector — SOVFI, TMZHI, VIRPTI, IRQ1, IRQ2, and all
  four SPORT rx/tx — is an `RTI` stub. So **IRQ0 is the single wired interrupt**
  (the per-frame/sample tick), configured edge-sensitive (`MODE2=0x18011`,
  `IMASK` bit8, `MODE1 0x3000` = IRPTEN+NESTM). IRQ0's handler just sets `R13=1`
  and toggles `MODE2` bit6 as an ISR→main-loop handshake.
- **Reset handler `0x8071`**: enable IRQ0, `IDLE`, `CALL 0x8D00` (boot-init),
  then the **main loop `0x8078`**: spin on `R13`, load base pointers
  (`I1=0xC004` params, `I8=0x9800` state, `I12=0x9C40`, `I4` coeff cursor), then
  a fixed chain of per-unit dispatch calls (`0x80F7`/`0x80FB`) that walk the
  slots with strides **0x50 words state @0x9800** and **0x4D words params
  @0xC000**. The `FLAG3` input pin is polled at `0x8098`.
- **PM `0x8400` (kernel's own 7 words)** = a **default passthrough** effect:
  read input `DM(0x20,I4)`, write it dry to both L/R outputs, advance state.
  This is what runs in a slot until a real effect is downloaded over it.
- **PM `0x8300`** = four shared float/fixed filter helpers (`0x8300`, `0x830B`,
  `0x831B` a 3-point interpolator, `0x8338`) that effects `CALL`.
- **PM `0x8D00` boot-init** = sets up all DAG circular-buffer registers
  (external delay SDRAM `B6=0x20000`, `L6=0x456F0`; per-unit state
  `B8..15=0x9800`), programs **both SPORTs** (control words `0x013CB173` /
  `0x013C3173`) and their DMA pointers, sets the `WAIT` and external-memory
  (SDRAM) control registers, and zero-fills the external delay RAM with six
  60000-word loops.
- **DM tables**: `0x9800`/`0x9C40`/`0xC000` download as zeroed per-unit
  state/param slabs; `0xC302` holds real data — eight `{src,count,stride,dst}`
  slot I/O descriptors plus a memory-map table for the external delay regions.

So the DSP is a **10-slot effect processor**: an IRQ0-paced loop pulls audio in
over the SPORTs, iterates the effect units (each a downloaded PM@8400 program +
its 0x50-word state + 0x4D-word params), and mixes to the outputs. This matches
the GUI's "up to 5 SOUND DSP + reverb + chorus + EQ" effect structure.

## 3. Host-side select / download mechanism (MN10300) — confirmed

Names added to `kn7000_disassembly/kn7000_manual.sym`. The GUI changes an effect
via `DspEffectSelect(unit, type)` at **`0x48405815`** — note the argument pair is
**(unit 0..9, type 0..0x91)**, *not* (MIDI bank, program) as an earlier note
guessed (proven at the EQ init `0x484102A7`: `unit 8, type 0x4F`). It validates
the pair against a per-unit **whitelist table** (`DspEffectTypeValid 0x48406132`)
and records the type in the unit's parameter struct. A full re-init
(`0x4840603B`) streams the kernel then every nonzero effect record.

**Per-unit whitelists pin down the fixed-function units:**

| unit | whitelist @ | accepts types | = GUI role |
|---|---|---|---|
| 0 | `0x486CE75D` | 0x00, 0x09, 0x10–0x1F | **Enhancer** group (Sound DSP) |
| 1–6 | `0x486CE82D` | large shared set | **Multi / Sound-DSP insert** slots |
| 7 | `0x486CE8FD` | 0x00, 0x58–0x5B | **Chorus** unit |
| 8 | literal `0x4F` | 0x4F only | **Equalizer** (final 5-band bus) |
| 9 | `0x486CE9CD` | 0x00,0x01,0x02,0x04,0x40,0x52 | **Reverb** unit |

## 4. Effect-type → record map — CONFIRMED from ROM

The 146-entry runtime table `0x500066E0` is a boot copy of a **ROM master table
at CPU `0x487B7248`** (146 × 4-byte LE record pointers). Decoding it against the
pool gives the authoritative map below (types sharing a record are stereo/mono
or minor aliases). This is *fact*, not inference — the ordering in the pool
(rec05..rec76) is remapped by this table.

## 5. The catalog

`GUI group` is from the confirmed type-map + whitelists (§3–4). `algorithm` is
from reading the SHARC opcodes (high confidence on the DSP building blocks).
`PM family` marks records whose effect code is **byte-identical** (verified) —
those are pure preset variants (only their DM coefficients differ). `conf` is
the analyst's confidence in the algorithm identification.

| type(s) | rec | GUI group | algorithm (from SHARC opcodes) | PM family | conf |
|---|---|---|---|---|---|
| 0x00 | rec05 | Reverb (unit9) | passthrough | uniq | high |
| 0x01 0x2C | rec06 | Reverb (unit9) | modulated-delay chorus | uniq | high |
| 0x02 0x07 0x2D | rec07 | Reverb (unit9) | modulated-delay chorus | uniq | high |
| 0x03 | rec08 | Multi/Sound-DSP insert (units1-6) | comb+allpass reverb | uniq | medium |
| 0x04 0x0B | rec09 | Reverb (unit9) | modulated-delay chorus | uniq | medium |
| 0x05 0x0D | rec10 | Multi/Sound-DSP insert (units1-6) | modulated-allpass phaser | uniq | medium |
| 0x06 0x0E | rec11 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | uniq | high |
| 0x08 | rec12 | Multi/Sound-DSP insert (units1-6) | dynamics/compressor + delay/filter composite | uniq | low |
| 0x09 | rec13 | Multi/Sound-DSP insert (units1-6) | comb+allpass reverb / delay | uniq | medium |
| 0x0A | rec14 | Multi/Sound-DSP insert (units1-6) | comb+allpass reverb / delay | uniq | medium |
| 0x0C | rec15 | Multi/Sound-DSP insert (units1-6) | comb+allpass reverb / delay | uniq | medium |
| 0x0F | rec16 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | uniq | medium |
| 0x20 | rec17 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion + envelope AGC | uniq | medium |
| 0x21 | rec18 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion + allpass/delay | uniq | medium |
| 0x22 | rec19 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion + short delay | uniq | medium |
| 0x23 | rec20 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion + biquad EQ (enhancer) | uniq | medium |
| 0x24 | rec21 | Multi/Sound-DSP insert (units1-6) | dynamics/compressor-limiter | =rec25 | high |
| 0x25 | rec22 | Multi/Sound-DSP insert (units1-6) | dynamics/compressor-limiter | uniq | medium |
| 0x27 | rec23 | Multi/Sound-DSP insert (units1-6) | biquad EQ (cascaded resonant sections) | uniq | medium |
| 0x28 | rec24 | Multi/Sound-DSP insert (units1-6) | tremolo-pan LFO | uniq | medium |
| 0x29 | rec25 | Multi/Sound-DSP insert (units1-6) | dynamics/compressor-limiter | =rec21 | medium |
| 0x30 | rec26 | Multi/Sound-DSP insert (units1-6) | tremolo-pan LFO | uniq | medium |
| 0x32 | rec27 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus/flanger | uniq | medium |
| 0x34 | rec28 | Multi/Sound-DSP insert (units1-6) | dynamics + biquad (envelope filter) | uniq | low |
| 0x33 | rec29 | Multi/Sound-DSP insert (units1-6) | dynamics + biquad (envelope filter) | uniq | low |
| 0x35 | rec30 | Multi/Sound-DSP insert (units1-6) | modulated-delay + filter (multi-tap, crossfade | =rec35,36,41,42,43,44,45 | low |
| 0x36 | rec31 | Multi/Sound-DSP insert (units1-6) | tremolo-pan LFO | uniq | medium |
| 0x38 | rec32 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | uniq | high |
| 0x39 | rec33 | Multi/Sound-DSP insert (units1-6) | FIR convolution + biquad EQ | uniq | medium |
| 0x4F | rec34 | EQUALIZER (unit8) | biquad EQ | uniq | medium |
| 0x80 | rec35 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | =rec30,36,41,42,43,44,45 | high |
| 0x81 | rec36 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | =rec30,35,41,42,43,44,45 | high |
| 0x82 | rec37 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion | uniq | high |
| 0x83 | rec38 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion | uniq | high |
| 0x84 | rec39 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion | uniq | high |
| 0x85 | rec40 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion | uniq | high |
| 0x86 | rec41 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | =rec30,35,36,42,43,44,45 | high |
| 0x87 | rec42 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | =rec30,35,36,41,43,44,45 | high |
| 0x88 | rec43 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | =rec30,35,36,41,42,44,45 | high |
| 0x89 | rec44 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | =rec30,35,36,41,42,43,45 | high |
| 0x8A | rec45 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | =rec30,35,36,41,42,43,44 | high |
| 0x8C | rec46 | Multi/Sound-DSP insert (units1-6) | modulated-allpass phaser | uniq | high |
| 0x90 | rec47 | Multi/Sound-DSP insert (units1-6) | modulated-allpass phaser | uniq | medium |
| 0x91 | rec48 | Multi/Sound-DSP insert (units1-6) | modulated-allpass phaser | uniq | high |
| 0x52 | rec49 | Reverb (unit9) | modulated-delay chorus | uniq | high |
| 0x53 | rec50 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus | uniq | high |
| 0x14 0x15 | rec51 | Enhancer (unit0) | comb+allpass reverb | =rec54,55,56 | high |
| 0x1E 0x1F | rec52 | Enhancer (unit0) | comb+allpass reverb | uniq | high |
| 0x10 0x11 | rec53 | Enhancer (unit0) | comb+allpass reverb | uniq | high |
| 0x12 0x13 | rec54 | Enhancer (unit0) | comb+allpass reverb | =rec51,55,56 | high |
| 0x16 0x17 | rec55 | Enhancer (unit0) | comb+allpass reverb | =rec51,54,56 | high |
| 0x18 0x19 | rec56 | Enhancer (unit0) | comb+allpass reverb | =rec51,54,55 | high |
| 0x78 | rec57 | Multi/Sound-DSP insert (units1-6) | modulated-delay pitch-shifter (detune) | uniq | medium |
| 0x58 | rec58 | Chorus (unit7) | comb+allpass reverb | uniq | medium |
| 0x59 | rec59 | Chorus (unit7) | comb+allpass reverb | uniq | medium |
| 0x5A | rec60 | Chorus (unit7) | comb+allpass reverb | uniq | medium |
| 0x5B | rec61 | Chorus (unit7) | comb+allpass reverb | uniq | medium |
| 0x64 | rec62 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion | =rec63,64,65 | high |
| 0x65 | rec63 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion | =rec62,64,65 | high |
| 0x66 | rec64 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion | =rec62,63,65 | high |
| 0x67 | rec65 | Multi/Sound-DSP insert (units1-6) | waveshaper/distortion | =rec62,63,64 | high |
| 0x7C | rec66 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus/pitch-shift (multi-stag | uniq | low |
| 0x79 | rec67 | Multi/Sound-DSP insert (units1-6) | waveshaper/nonlinear (+ modulated delay) | uniq | medium |
| 0x7A | rec68 | Multi/Sound-DSP insert (units1-6) | waveshaper/nonlinear | uniq | medium |
| 0x7B | rec69 | Multi/Sound-DSP insert (units1-6) | waveshaper/nonlinear (+ comb) | uniq | medium |
| 0x40 | rec70 | Reverb (unit9) | modulated-delay chorus/ensemble | uniq | medium |
| 0x42 | rec71 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus/flanger | uniq | medium |
| 0x43 | rec72 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus/ensemble | uniq | medium |
| 0x44 | rec73 | Multi/Sound-DSP insert (units1-6) | modulated-delay + series-allpass (phaser/diffu | uniq | medium |
| 0x46 | rec74 | Multi/Sound-DSP insert (units1-6) | modulated-delay / tremolo-rotary (computed LFO | uniq | medium |
| 0x50 | rec75 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus/flanger | =rec76 | medium |
| 0x51 | rec76 | Multi/Sound-DSP insert (units1-6) | modulated-delay chorus/flanger | =rec75 | medium |

### Effect families (byte-verified)

Records with identical PM code (presets of one algorithm): **rec21=rec25**;
**rec30=rec35=rec36=rec41=rec42=rec43=rec44=rec45** (an 8-preset modulated-delay
chorus/ensemble engine — the largest family); **rec51=rec54=rec55=rec56** (with
rec52, rec53 as two more distinct Enhancer-unit algorithms); **rec62=rec63=
rec64=rec65** (4 tone presets of one overdrive/distortion); **rec75=rec76**.
Note rec16 shares the 74-word *size* of the chorus family but its code differs —
it is a distinct variant, not a preset.

> **"Diffusion" here is the audio-DSP term.** An *allpass* filter passes every
> frequency at equal level but delays it; a cascade of allpass sections is a
> *diffuser* that smears a single sharp echo into a dense, smooth tail. It is the
> classic reverb-construction technique (the Schroeder/Moorer reverberator
> designs of the 1960s–70s): comb filters set the decay time and the allpass
> diffusers fill in the echo density so the result sounds like a room rather than
> a series of distinct repeats.

### An honest tension: DSP structure vs GUI unit

Two groups read, at the opcode level, as **comb+allpass diffusion networks** (a
reverb-style DSP building block) yet the host wires them to non-reverb units:

- **rec51–56 → unit 0 = Enhancer** (types 0x10–0x1F). Six records, the only
  6-member family, matching the GUI's 6 Enhancer subtypes — but the code is
  allpass diffusion, not the high-frequency exciter one expects from "Enhancer".
- **rec58–61 → unit 7 = Chorus** (types 0x58–0x5B). Four *distinct* algorithms
  (byte-diff: all four differ), read as allpass diffusion, wired to the Chorus
  unit — i.e. a "symphonic ensemble" style chorus built from diffusion.

Both facts stand; they are not reconciled statically. The GUI-group column is
what the firmware *routes* the record to; the algorithm column is what the code
*does*. A dynamic capture (plan Phase C/D) would settle whether, e.g., the
Enhancer adds a nonlinear stage the static read under-weighted. Similarly the
unit-9 Reverb whitelist maps types 0x01/0x02/0x04 to rec06/rec07/rec09, which
the opcode read called "modulated-delay chorus" — so those reverb-unit programs
are **modulated** reverbs (delay + LFO), consistent with GUI names like "Dark"
or "Concert" that add movement.

### Confirmed vs inferred, at a glance

- **Confirmed** (from ROM tables / hard-coded call sites): the full type→record
  map (§4); rec34 = the 5-band Equalizer (unit 8, type 0x4F); rec05 = thru/null
  (type 0x00); the four unit whitelists and which records each unit can load; the
  PM-identical families (byte-diff).
- **Inferred** (structure + family-size + unit correlation): rec51–56 =
  Enhancer1–6; rec58–61 = Chorus1–4; per-record algorithm classes; the exact
  1:1 reverb name ordering (Room1/Plate1/…) is **not** pinned. Finishing the
  per-record GUI names needs the descriptor-table walk (group jump table
  `0x4858F6AC`, per-effect descriptors `0x48703558` +0x12 = type) or a dynamic
  capture — deferred to plan Phases C/D.

## 6. Data records (rec77–79) — LFO waveform tables

DM-only downloads to `DM 0xC028` (the kernel's LFO/modulation-waveform slot,
which modulated effects read through a post-modified DAG pointer). The three are
alternate **modulation shapes** the host swaps live without reloading an effect:
**rec77 = sine** (bit-identical to the default baked into rec07), **rec78 =
triangle**, **rec79 = square**. Layout: 25 active 1.31 fixed-point entries = one
cycle over 16 samples, plus an 8-entry positive-half guard copy for wrap-free
interpolated reads.

## 7. SDRAM self-tests (rec00–03) — not audio

Correcting the earlier "board-variant probe" guess: these are **power-on
memory tests** of the DSP's external SDRAM (IC307/IC308). Each is a
fill/verify march over the SDRAM banks, publishing a pass/fail word to host
register `0x0B`; the four form a 2×2 matrix of **pattern (0xAAAAAAAA / 0x55555555)
× region (low 0x80000–0xA0000 / high 0xA0000–0xC0000)**. The host runs them at
boot before loading the kernel (the reg-0x0B readback is the "DSP alive" check
the plan's Phase A must answer). They contain no audio DSP.

## 7.5 ★ 2026-07-19 UPDATE — the GUI preset-descriptor table: names are ROM fact now

The deferred "descriptor-table walk" of §5 is done, statically
(`kn7000_disassembly/dsp/tremolo-rotary-family.md` §1). The firmware holds
**~600 preset descriptors** (region CPU `0x4858FB8C..0x48597200`) of the form
`{u16 params[n]; char name[16]; u16 0; u16 type; u16 nparams; u16 0; u32 ptr;
u32 id}` plus group tables (`{ptr,count,name16}`, Sound-DSP list ≈`0x4870FE00`,
menu list ≈`0x48714B00`). Because `type` indexes the confirmed §4 map, **GUI
name → type → record is now ROM fact for every effect screen.** Highlights that
correct or settle rows above:

- **ROTARY SPEAKER (7 presets) / ROCK ROTARY (6)** = rec30/41/42/43/45 and
  rec16/35/36/44 — the "modulated-delay chorus (conf low)" family is a **full
  Leslie simulator** (crossover, dual magic-circle rotors 5.512/6.431 Hz =
  exactly 7:6 with 93 ms rate glide, Doppler taps, saturation front end).
- **Tremolo1–8 = rec24** (in-phase AM), **Auto Pan1–7 = rec26** (quadrature
  AM), **Ring Mod.1–4 = rec31** (bipolar AM, audio-rate carrier) — the three
  "tremolo-pan LFO" rows split into their real identities.
- **Enhancer1–6 = type 0x03 = rec08** — the §5 "honest tension" is RESOLVED:
  the GUI Enhancer group never pointed at rec51–56 (those are the
  REVERB-screen presets: Room1/2=rec53, Plate1/2=rec54, Concert/Long/Large
  Hall=rec51, Dark=rec55, Bright=rec56, Live Stage/Stadium=rec52,
  Medium/Short/Long **Gate**=rec12).
- **Vocal Harmonizer = rec66** (3-voice granular pitch shifter, just-maj7
  template, host telemetry via IOP reg 0x0C); **Voice Changer1/2 = rec57**;
  **Brass simulator1–3 = rec67–69**; mic **Room/Karaoke/Stage/Cave =
  rec58–61** (the unit-7 "Chorus" records are the mic ambience unit);
  **Vibrato1–8 = rec27**, **Mixup1–4 = rec32**, **Spreader = rec33**,
  **Exciter1–3 = rec20**, **Comp.1–4 = rec21** vs **Limiter1–4 = rec25**
  (the two identical-PM dynamics records are the two GUI groups),
  **Slow Attacker1–4 = rec22**, **Autowah+Delay = rec74** (confirms the
  touch-wah re-identification), **Delay+Chorus/Flanger/Vibrato/Phaser =
  rec70–73**, **Comp+Dst/Ovd+Delay = rec75/76**, **Cross Delay presets =
  rec15**, beat-synced **For 2/3/4Beat = rec46 (LFO filter) / rec48 (wah)**.

The §5 algorithm column remains the 2026-07-09 pass; where it disagrees with
`kn7000_disassembly/dsp/records.tsv` (regularly, after the reverb/chorus/
insert/rotary annotation passes), **records.tsv is authoritative**.

## 8. Cross-model note

The KN6000/KN6500 carry the same ADSP-21065L and a **byte-identical** record
pool to each other (80/80). Vs the KN7000, **all 80 records' DM (coefficient)
blocks are byte-identical but the PM (code) was revised — only 3/80 PM match**
(byte-verified; `kn7000_disassembly/dsp/cross-model/`). So this catalogue and its
DM-level facts transfer directly to the KN6xxx; only the code differs.
`gen_dsp_records.py` takes pool bounds as CLI args — the KN6000 listings are
already generated at `dsp/cross-model/kn6000/` (== KN6500).
