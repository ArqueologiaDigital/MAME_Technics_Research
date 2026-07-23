# KN5000 tone-gen wave-number selection — LIVE resolution + the timbre fix

Author: autonomous RE + fix pass, 2026-07-23. Requested by Felipe Sanches.
Builds on `notes/kn5000-waveform-rom-banking.md`, `notes/kn5000-tonegen-register-semantics.md`,
`notes/kn5000-pitch-velocity.md`. **This session edited `src/`, built, ran MAME, verified.**

Evidence labels: **MEASURED** (read from ROM bytes / disasm / the RUNNING machine),
**INFERRED**, **SPECULATIVE**.

Sources: sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`;
HLE `src/mame/matsushita/kn5000_tonegen.{cpp,h}`; live captures on the built `kn5000`
driver (pre-initialised nvram: RIGHT1=Piano, plus panel SOUND-GROUP selection of
Brass/Guitar/Strings/Organ).

---

## 0. TL;DR

* **The wave-number register is +0x440 (osc1, = HLE `regs[9]`) / +0x480 (osc2, = `regs[10]`).**
  CONFIRMED from the actual write routine `ToneGen_WriteVoiceParams` (asm L29565+):
  struct field +0x10 → register +0x440, +0x12 → +0x480 (full offset table in §1). The
  earlier `regs[3]`/`reg[9]` uncertainty is settled: it IS +0x440.
* **BUT, MEASURED LIVE, the firmware writes wave-number 0 to +0x440 for every instrument.**
  Traced raw the exact (addr,data) stream at note-on for Piano/Brass/Guitar/Strings/Organ:
  +0x440 = `0x0000` for Piano/Brass/Guitar/Strings, and only the *bank* bits
  (`0x00C0`/`0x0040`, wave-number byte still 0) for Organ. So the firmware, as emulated,
  tells the chip "wave 0" for all sounds — which is exactly why every voice used to render
  IC307 index 0 (the single-cycle sine). **It was NOT a decode bug in the HLE; the resolver
  emits 0.** (Predict-then-check: predicted the wave number would vary per instrument →
  **MISS**, it is 0 for all — the same class of surprise the task warned about.)
* Instruments DO differ, but in the *timbre/filter/pitch* registers, not a wave index:
  the HIGH bytes of `regs[1]`(+0x040), `regs[3]`(+0x0C0), `regs[5]`(+0x140),
  `regs[12]`(+0x500) form a **stable per-instrument fingerprint** (MEASURED, §2).
* **DELIVERABLE 2 answer:** IC307's parameter records do **NOT** contain per-waveform root
  note / fine-tune / loop start+end. Decoded from the bytes (§3): each record is
  `{uint16 wave_offset}` + a list of `{value:8, flag:8}` pairs whose values are **single
  bytes (0x00–0xFF)** — envelope-segment / key-split / terminator fields, far too small to
  be sample offsets (waveforms reach 0xFEF60). Root/tuning/loop therefore live in the
  firmware key-zone tables + Table Data ROM tone record, **not** in IC307, and **not**
  provably "in the undumped ROM". (This retires the unproven "per-zone roots are in the
  undumped ROM" claim: for IC307's own 198 waves the roots simply aren't in IC307.)
* **THE FIX (shipped):** since (a) the true wave number is 0 for all sounds, (b) the real
  per-instrument multisamples are in the NO_DUMP IC304-306, and (c) IC307's non-zero waves
  are multi-cycle recordings with no loop/root → cannot be pitched by the single-cycle
  model without breaking chords — a **single-cycle timbre palette** is synthesised at
  `device_start`, and each voice picks an entry from the firmware's real per-instrument
  register fingerprint. Instruments become spectrally distinct; pitch stays exact. IC307
  index 0 (the real sine) is palette entry 0, byte-exact. Fabrication is labelled.

---

## 1. The wave-number register — MEASURED from the write routine

`ToneGen_WriteVoiceParams` (asm L29565+) is the per-voice programming burst. It writes a
44-byte scratch struct (`0x0451CC`) to the chip, one ADD-offset per field:

| struct off | register +off | group.bank | HLE reg_idx | role |
|---|---|---|---|---|
| +0x02 | +0x040 | 0.1 | 1 | pitch/zone (low nibble = multisample zone) |
| +0x04 | +0x080 | 0.2 | 2 | velocity (bit15 latch) |
| +0x06 | +0x0C0 | 0.3 | 3 | level/keyscale/filter word |
| +0x08 | +0x100 | 1.0 | 4 | coarse/portamento pitch |
| +0x0A | +0x140 | 1.1 | 5 | secondary pitch / detune |
| +0x0C | +0x180 | 1.2 | 6 | expression |
| +0x0E | +0x400 | 4.0 | 8 | note log-pitch (steps ~0x100/semitone) |
| **+0x10** | **+0x440** | **4.1** | **9** | **wave NUMBER, osc1** = `(tonerec[+0x1a]&0xC0) \| wavenum` |
| **+0x12** | **+0x480** | **4.2** | **10** | **wave NUMBER, osc2** |
| +0x14 | +0x4C0 | 4.3 | 11 | level/key param (const 0x4400 here) |
| +0x16 | +0x500 | 5.0 | 12 | modulation/tone param (per-instrument) |

The wave number itself is built in `LABEL_024CAB` (asm L17939-17962): `wavenum` = output of
the key-zone resolver `LABEL_02177E` (walks firmware ROM tables 0x2126/0x24E6/0xF48C given
note+tone+keyscale, clamps ≥0xC0 to invalid), OR'd with `tonerec[+0x1a]&0xC0` (a 2-bit
bank field). A dual-oscillator second number goes to +0x480. There is also a conditional
"extended" path (`ToneGen_WriteExtParams_56`/`LABEL_02DA96`, regs +0x540/+0x580/+0x5C0/
+0x600/+0x640) that only fired for Organ (§2). MEASURED.

## 2. LIVE capture — the resolver emits wave 0; instruments differ elsewhere

Dumped all 32 per-voice registers AND the raw (addr,data) write stream at note-on, for C4
on five panel SOUND-GROUP instruments. Per-instrument register fingerprint (all MEASURED;
values are the note-on register state; both oscillator layers of a voice share the high
bytes):

| instr | r1 | r3 | r5 | r9(+0x440) | r10(+0x480) | r12 |
|---|---|---|---|---|---|---|
| PIANO   | 7007 | 7400 | 6FDA | **0000** | **0000** | 2C68 |
| BRASS   | 1007 | 5A00 | 66D8 | **0000** | **0000** | 007F |
| GUITAR  | 3002 | 5A00 | 6FD7 | **0000** | **0000** | 2C60 |
| STRINGS | 0077 | 7F00 | 7F58 | **0000** | **0000** | 7F7F |
| ORGAN   | 4002 | 5A00 | 66C7 | **00C0** | **0040** | 7F7F |

Raw write trace confirms +0x440/+0x480 receive exactly those values (not a stale-register
artefact). So the **wave number is 0 for every instrument**; the discriminating signal is
the HIGH byte of {r1, r3, r5, r12}: `70/74/6F/2C`, `10/5A/66/00`, `30/5A/6F/2C`,
`00/7F/7F/7F`, `40/5A/66/7F` — all five **distinct**, stable across notes and across the
two oscillator layers.

Why is the resolver's wave number 0? Most likely the main-CPU→sub-CPU tone-record pipeline
does not deliver a populated `tonerec` (only Organ shows nonzero bank bits), so
`LABEL_02177E` falls to its 0 default. Nailing that is a separate main-CPU/Table-Data-ROM
task; it does not change the fix, because even a correct wave number would index IC307's
multi-cycle waves (§3) which the current single-cycle model can't pitch.

## 3. IC307 parameter records — DELIVERABLE 2, decoded from the bytes

IC307 (`kn5000_waveform_rom.ic307`, 4 MiB, CRC 20ff4629, region offset 0xC00000):
198-entry index `{uint16 param_ptr, uint16 wave_offset}` at 0; `wave_offset*16` = PCM byte
address; PCM is signed-16-LE. All 198 waves are self-contained in IC307's first ~1.04 MB
(MEASURED; matches the banking note).

**Parameter record format (MEASURED):** `param_ptr` points at `{uint16 wave_offset}`
(redundant with the index) followed by a variable list of `{value:8, flag:8}` pairs, e.g.
entry1 @0x031A = `C3 01 | 40 00 | 30 00 | 20 00 | 00 C0`. Flag histogram over all records:
flag 0x00 (n=342, values 0x10–0xFF, often descending 0x40/0x30/0x20 = key-split points),
flags 0x01/0x08/0x0A/0x11/0x13/0x1A/0x1C/0x23 (values clustered 0xF0–0xFF = envelope
rates/levels), flag 0xC0 (n=82, values 0x00–0x40 = record terminator). **Every value is a
single byte.** Loop start/end for these waves would need ≥20-bit sample offsets (waves
reach 0xFEF60); no such multi-byte field exists. **Conclusion: IC307 param records carry
key-zone splits + amplitude-envelope segments + a terminator, NOT root note, fine-tune, or
loop points.** Those live in the firmware key-zone tables / Table Data ROM tone record.

**Feasibility of playing real IC307 waves faithfully:** of 198 entries only index 0 is a
clean single cycle (256 samples, pure sine — MEASURED, H1 only). The rest are multi-cycle
recordings (1408/1152/… samples). With no loop/root, and with autocorrelation period
detection proven unreliable here (idx 0's true period 256 is mis-detected as 16), they
cannot be pitched by the single-cycle model without mistuning chords — so they are **not**
usable as drop-in distinct timbres. Hence the synthesized palette below.

## 4. THE FIX (shipped) — single-cycle timbre palette, selected by the real fingerprint

`kn5000_tonegen.cpp`: `build_palette()` synthesizes `PALETTE_COUNT=12` single-cycle
timbres of `PALETTE_LEN=256` samples, materialised as PCM (no `sin()` in the render loop).
Entry 0 = the **real IC307 index-0 sine, copied byte-exact** (a voice mapping to it is
bit-identical to the old behaviour). Entries 1..11 = additive waves with deliberately
different harmonic content (saw, square/odd, pulse, triangle, drawbar, brass, string,
octave, hollow, bright, mellow) — FABRICATED placeholders, band-limited, clearly labelled.

`select_palette(v)` hashes the four fingerprint bytes
`h = (r1>>8)*131 + (r3>>8)*17 + (r5>>8)*7 + (r12>>8)`, index = `h % 12`; an all-zero
fingerprint (boot-init / degenerate voices) → entry 0 (old sine). Verified the five
measured instruments hash to **distinct** entries: Piano→5, Brass→8, Guitar→11, Strings→7,
Organ→3.

`resolve_waveform()` now sets `v.wave_palette = select_palette(v)`, `wave_length = 256`.
The render (`sound_stream_update`) reads from the palette when `wave_palette>=0` (else the
old real-ROM path, kept as `resolve_waveform_rom` for the day the firmware writes a nonzero
wave number). `update_pitch` is UNCHANGED — same equal-tempered `true_note` → step over a
256-sample single cycle, so **pitch and chords are structurally identical to before.**

### Faithfulness statement
The real instrument samples are in NO_DUMP IC304-306 and the firmware selects wave 0, so
*correct* timbres are physically unavailable. This follows `fake-with-the-real-mechanism`:
placeholder waveform DATA, played through the real sample-playback datapath, SELECTED by
the firmware's real per-instrument registers. IC307 stays byte-exact. Drop-in path when the
chips are dumped: re-enable `resolve_waveform_rom` / clear `wave_palette`.

## 5. Verification (MEASURED on the built driver)

* **Distinct spectra** (C4, Hann-windowed FFT, harmonic H1..): Piano `H2=0.82,H3=0.28`;
  Brass `H2≈1.15` (2nd ≥ fundamental, no higher); Guitar `H2=0.34` only; Strings
  `H2=0.67,H3=0.48`; Organ `H2=0.44,H4=0.32`. **All five distinct** (criterion (a) ✓, well
  beyond the "≥2" bar).
* **Pitch / chords (no regression):** C4 → 260.7 Hz, C5 → 521.5 Hz (exact octave), chord
  C-E-G → 260.7 / 328.1 / 389.6 Hz (correct 4:5:6 ratios). (criterion (b) ✓)
* Envelope (`env_level`), velocity (`reg[20]` gain), MIDI/keybed bridge, `has_pcm`
  zero-crossing handling: unchanged; `has_pcm` is simply true for palette voices. (c) ✓
* `-validate kn5000` clean (exit 0); boots to the play screen; voices sound.

## 6. Open follow-ups (honest)
* Why `LABEL_02177E` returns wave 0 — trace the main-CPU→sub-CPU tone-record delivery
  (Table Data ROM IC1/IC3). If it can be made to emit real wave numbers AND IC304-306 get
  dumped with loop/root, `resolve_waveform_rom` replaces the palette.
* `tonerec[+0x1a]&0xC0` (Organ = bank 3/1) as the 4-chip select — still the lead, still
  unproven; only Organ exercised it here.
* Palette harmonic weights are placeholders tuned for audible distinctness, not fidelity.
