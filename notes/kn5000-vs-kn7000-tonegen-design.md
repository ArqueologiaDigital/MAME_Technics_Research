# KN5000 vs KN7000 tone-generator DESIGN — a firmware-level comparison

> ## ⚠ SUPERSEDED IN PART (2026-07-23) — see `notes/kn5000-envelope-engine.md`
>
> **This note's verdict "(a) INFERRED NO — the KN5000 has no per-note envelope" is
> WRONG and is retracted.** A follow-up pass found the envelope engine the analysis
> below missed. Felipe's objection ("the GUI sets envelope values, so it must be
> applied") is correct.
>
> The KN5000 has a **per-note, multi-stage, multi-domain SOFTWARE envelope** running
> in the SUB CPU, clocked by the audio timer tick — steppers **`LABEL_026E5B`
> (amplitude)** / **`LABEL_026EC3`** in the periodic `Audio_Process_Init` pipeline
> (`027A46`/`027AC4`), which call **`ToneGen_WriteSingleReg` (0x02D41B)** to rewrite
> the IC303 level register (`0x100000/0x100002`) over the note's lifetime. Seeded
> from patch bytes (0x832000 tone record) + velocity + keyscale. The GUI is a full
> synth Sound-Edit section with **AMP + PITCH + FILTER envelope** pages
> (`SEAMPENV/SEPITENV/SEFILENV`, MAIN CPU 0xF039CD…) — falsifying §3's "there is no
> AMP/PITCH/FILTER ENVELOPE edit screen."
>
> **Why this note was wrong:** §2-§3 inspected only the NOTE-ON writer
> (`ToneGen_WriteVoiceParams`) and the boot block; the envelope is not a chip
> register block written at note-on, it is a **software loop in the periodic tick**
> that was never traced (and the trace ran the wrong, wedged binary). The tables
> `Voice_AttackDecay_Widths`/`Voice_EnvelopeRate_Lookup` this note names in passing
> ARE the per-stage width/rate tables, seeded into 18 seven-stage state blocks at
> 0x112D by `LABEL_021ECB`.
>
> **Corrected verdict:** (a) **YES** — a software EG, same conceptual shape as the
> KN7000's (per-note, multi-stage, amp/pitch/filter, patch+velocity+keyscale driven),
> at a different LAYER (KN7000 = chip hardware; KN5000 = sub-CPU software clocked by
> the audio tick). (b) The envelope core IS shareable in concept after all. The
> "sample-driven, no ADSR" reading below is the retracted error. **Read
> `kn5000-envelope-engine.md` instead; the §4-§5 sample-playback/pitch/wave-addressing
> comparisons below remain valid.**

---

Author: autonomous RE pass, 2026-07-23. Requested by Felipe to **re-open** the
prior HLE-level verdict (`notes/kn5000-tonegen-sharing.md`) and test two theses at
the *firmware* level:

- **(a)** Does the KN5000 have an ADSR envelope in firmware that the HLE ignores —
  structurally like the KN7000's per-note 7-param EG?
- **(b)** Are the two tone-generator DESIGNS similar enough that, once BOTH HLEs are
  complete, a shared synthesis core becomes viable?

This pass compares the **CPU→chip programming**, not the two MAME classes. Every
firmware claim is tagged **MEASURED** (read from disassembly/source), **INFERRED**
(strong deduction from measured facts), **PROVEN-BY-CONSTRUCTION** (follows from the
code path), or **SPECULATIVE**.

Sources: KN5000 SUB CPU disasm `kn5000-roms-disasm/v142/subcpu/kn5000_subprogram_v142.s`;
KN5000 docs `kn5000-docs/{tone-generator,audio-subsystem,waveform-rom-format,sound-parameter-protocol,sound-categories,table-data-rom}.md`;
KN7000 notes `tg-voice-register-semantics.md`, `tg-envelope-implementation-plan.md`,
`tg-envelope-sweep-results.md`; both HLEs in `src/mame/matsushita/`.

---

## TL;DR verdict

- **(a) INFERRED NO.** The KN5000 SUB CPU does **not** program a per-voice
  multi-stage ADSR into IC303. Its note-on writes 22 registers (MEASURED); **none is
  an EG rate/level block** analogous to the KN7000's group-0 `r0..rB`. The chip's
  group-0 banks are control/pitch/velocity/waveform, *not* envelope. The KN5000's
  amplitude contour is **sample-driven + a static velocity→level curve + a coarse
  software housekeeping tick** — not a synthesized ADSR. **This substantially
  *refutes* the "designs are similar, KN5000 just needs the KN7000's ADSR" thesis.**
  ONE caveat keeps the door ajar (below): per-patch "envelope" bytes *exist* in the
  MAIN-CPU ROM but their application path to IC303 is untraced.
- **(b) PARTIAL.** The two chips share the *sample-playback* half of the design
  (PCM wavetable, **index-not-address** wave addressing — identical model — and
  **CPU-precomputed pitch published to a per-voice register**). They **diverge on the
  envelope model**: the KN7000's NEC chip exposes THREE parallel 7-param EGs
  programmed per note; the KN5000's Toshiba chip receives no per-note EG at all. A
  shared *PCM+pitch+wave-index* core is plausible; a shared *envelope* core is not,
  because one side doesn't have one to share.

The prior HLE pass concluded "~0% shared." That conclusion **survives** — but its
stated reason ("two devices modelled at different levels") was incomplete. The
deeper, firmware-grounded reason is that **the KN5000 genuinely does less envelope
work in firmware.** The envelope-less KN5000 HLE is *closer to the firmware truth*
than the task's framing assumed.

---

## 1. The two architectures (MEASURED)

| | KN5000 | KN7000 |
|---|---|---|
| TG chip | Toshiba **TC183C230002** (IC303), 64 voices | 2× NEC **D82398GD001** (IC201/205), 128 voices |
| Who drives it | a **dedicated SUB CPU** (TMP94C241) running a GM-style sound-module firmware; the MAIN CPU sends MIDI-like events over an inter-CPU latch | the **MN10300 MAIN CPU** directly, no sub-processor |
| Host write primitive | **register-indirect**: latch 16-bit reg-addr @0x100000, then data @0x100002, P6.7 = CS strobe (`ToneGen_WriteVoiceParams` 0x02D0FD, disasm L20737) | **plane word**: `(ch&0x3f)<<20 \| class \| data`, split to addr/data ports 0x98040000/0x98050000 (dispatcher 0x487EFF69) |
| Reg-address encoding | `group[15:8] \| bank[7:6] \| channel[5:0]`, 32 regs/voice = 8 groups × 4 banks | `group[15:10] \| voice[9:4] \| index[3:0]`, voice stride 0x10 |

The two-CPU split matters: on the KN5000 the tone generator is behind a **self-contained
sound-module driver** (its own MIDI dispatch, CC handlers, voice allocator). The
"patch" a user hears is chosen by Program Change; the SUB CPU maps it to a waveform
and a fixed register template. On the KN7000 the arranger CPU programs every EG byte
of every note itself.

---

## 2. Per-voice DATA MODEL — side by side

### KN5000 note-on register set (MEASURED — `ToneGen_WriteVoiceParams`, L20737-21112)

22 register/data pairs from a 44-byte struct, in emission order:

| reg (ch=0) | struct off | meaning (from docs + code) |
|---|---|---|
| +0x040 | +2 | **pitch increment** (semitone ratio, 0x8000 = 1.0×; from table 0x01217D) |
| +0x080 | +4 | voice-mode/velocity, **bit15 = latch SET** |
| +0x0C0 | +6 | waveform control (cleared on note-off) |
| +0x100 | +8 | interpolated pitch (portamento/legato) |
| +0x140 | +10 | secondary pitch offset (detune) |
| +0x180 | +12 | velocity/expression coefficient |
| +0x400 | +14 | note-key info (note<<8, bit15 active) |
| +0x440/+0x480/+0x4C0 | +16/+18/+20 | group-4 banks 1/2/3 ("level/key param", **meaning open**) |
| +0x500 | +22 | modulation param (group-5) |
| **+0x000** | — | **KEY-ON = 0x8100** (constant, mid-sequence) |
| +0x840/+0x880 | +26/+28 | **pan L / pan R** (0=silent, 0x3C=center, 0x78=full) |
| +0x8C0 | +30 | DSP/effects send level |
| +0x900..+0x9C0 | +32..+38 | 4 aux/effect sends |
| +0xA00/+0xA40 | +40/+42 | aux params |
| +0x080 | +4 | rewritten, **bit15 = latch CLEAR** |

**There is no attack/decay/sustain/release rate or level register in this set.**
The only time-relevant per-voice quantities are pitch, a static velocity/expression
coefficient, and the level/pan words.

### KN7000 note-on register set (MEASURED — `tg-envelope-sweep-results.md`, RESULT 1/4/5)

The group-0 block `r0..rB` written per note is **three parallel 7-param EGs** in one
layout (each register = `[rate hi | level lo]`):

```
r0=[amp ATK|PEAK]  r1=[amp DCY1|SUS1]  r2=[amp DCY2|SUS2]   r3 = GATE (0x87FF on / 0x8000 up)
r4=[pit ATK|PEAK]  r5=[pit DCY1|SUS1]  r6=[pit DCY2|SUS2]   r7 = [pitch TOTAL DEPTH | …]
r8=[flt ATK|PEAK]  r9=[flt DCY1|SUS1]  rA=[flt DCY2|SUS2]   rB = [… | filter START POINT]
```
These bytes are copied per-note from the tone descriptor (`TgElemNoteOnStd`
0x4C030A9D; shadow cache 0x500CA0B0+slot*0x84), and at key-up the release halves are
recomputed (`TgKeyOffAmpRelease/Pitch/Filter` 0x4C031949/1F07/2490) and flushed as a
6-write burst (`TgVoiceEgBurstWrite` 0x4C0376E3). The screen ATTACK/DECAY/SUSTAIN
map 1:1 onto these registers (pixel-verified sweep). **This is a fully
CPU-programmed, per-note, three-domain envelope.**

### The decisive contrast

The two chips' **group-0 means opposite things**:

| group-0 | KN5000 | KN7000 |
|---|---|---|
| banks/indices | control / pitch-inc / velocity / waveform | **the entire amp+pitch+filter EG** |

There is no register in the KN5000 note-on that corresponds to the KN7000's
`r0/r1/r2` amp-EG. **MEASURED, and it is the crux of thesis (a).**

---

## 3. THE ENVELOPE — where does the KN5000's amplitude shape come from?

Four independent lines of evidence, all pointing the same way:

1. **The note-on register set has no EG block** (MEASURED, §2). The 22 writes carry
   pitch, velocity coefficient, level, pan, sends — no rate/level ADSR.

2. **The "unknown" group-4 registers are written as ZERO at voice setup.** The voice
   working-struct base is 0x0451cc; the setup path clears the group-4 fields
   (`stiw_da 0x0451dc,0 / 0x0451de,0 / 0x0451e0,0` = struct +16/+18/+20, L12801-12804)
   and defaults volume to near-mute `0x0451e4=0xff7f`. So group-4 is **not** carrying
   per-tone envelope shaping — it is zero. (MEASURED.)

3. **The wave-ROM parameter records contain no envelope.** Their high-byte flags are
   key-zone boundaries (0x00), per-key tuning (0x01/0x08), transition/loop markers
   (0x0A/0x40), header (0x1C), end (0x80/0xC0) — **key zones, tuning, loop points, no
   ADSR** (`waveform-rom-format.md` §2, MEASURED). So the chip does **not** read an
   envelope from the sample record the way it reads loop points.

4. **The only user-facing "envelope" controls are organ/percussion-specific or DSP
   effects** (`sound-parameter-protocol.md`, MEASURED): `LswDrawAttack/LswDrawRelease`
   (drawbar-organ attack/release), `LswPercDecay/LswPercLevel` (organ percussion), and
   the `SLOW ATTACKER`/`COMPRESSOR` (`ATTACK/RELEASE` at name-idx 0x2A/0x2B) which are
   **DSP effect** parameters, not voice EG. There is **no general AMPLITUDE/PITCH/FILTER
   ENVELOPE edit screen** like the KN7000's (users-manual p172-173). The KN5000 simply
   does not expose a per-tone ADSR to the user.

**What the KN5000 does instead (MEASURED):**
- **Static velocity→level+pan.** `Voice_Level_ComputeTriplet` (L6970) builds a
  level triplet from a velocity/expression lookup at ROM 0x0118fe, applies a per-voice
  **modulation-depth matrix** (reads modulation coefficients at struct +9/+11/+13/+17/
  +19/+20/+21 and scales via `Pan_ScaleWithVelocity`/`Detune_ScaleSymmetric`), then
  packs the results into the group-8/9 level/pan/send registers (0x0451ec/ee/f0). This
  runs **once at note-on** (a modulation *depth*, not a time ramp). `ToneGen_Calc_Pitch`
  doc note: `velocity_volume = (vel²/4)+63`, range 63-4095.
- **A coarse software housekeeping tick.** `Voice_TickNoteDecay` (L12823) decrements a
  per-voice counter (reload 4, at 0x04135f) and, when it fires, re-runs
  `Voice_SetPanning` + `ToneGen_WriteVoiceParams` — a periodic re-write that can
  implement slow portamento/level drift, but is **not** a per-sample amplitude ramp.
- **Voice lifecycle via a priority list.** `VoiceNode_UpdateEnvState`/`BeginRelease`
  (L3825-3856) toggle state bits (+34 bits 0x1/0x2/0x3/0x8) to move a voice through
  key-on → sustaining → release **for allocation/stealing**, not to generate amplitude.
- **Note-off** = write waveform-ctrl `+0xC0=0x0000` then voice-ctrl `+0x00=0x7E00`
  (`ToneGen_WriteNoteKey`), i.e. mute + idle. No release *ramp* is programmed; the
  chip/sample tails off.

**Conclusion (INFERRED, strong):** the KN5000's amplitude behaviour is carried by
**the PCM sample itself** (multi-cycle instrument recordings that already contain the
natural attack/decay — `waveform-rom-format.md` confirms most waveforms are long
multi-cycle recordings, not single-cycle wavetables) plus a **static velocity level**.
Any hardware EG inside IC303 is driven by **fixed template values, not per-tone data**
(the template at ROM 0x012115 supplies constants that setup does not override except
for pitch/velocity/routing). The KN5000 does **not** have the KN7000's programmable
per-note ADSR.

### The one caveat that keeps thesis (a) technically open (MEASURED fact, untraced path)

Per-patch data in the MAIN-CPU **Table Data ROM 0x832000-0x850000** is documented to
include "multi-layer synthesis parameters — **envelope**, filter, LFO, effects
routing" (`table-data-rom.md` L149, `sound-categories.md` L176). Because the KN5000
and KN7000 **share a codebase**, the patch-record *format* very likely carries EG
fields whether or not the KN5000 chip consumes them. I found **no traced path** by
which those envelope bytes become IC303 register writes: the SUB CPU note-on emits no
EG, and Program Change only selects a waveform/template. So today the honest reading
is: **the format has envelope fields; the KN5000 datapath does not apply them to the
chip as a per-note ADSR.** IF a future trace of `0x832000 patch → MAIN CPU sound
engine → inter-CPU command → SUB CPU register write` shows envelope bytes reaching a
group-4/5 register (or a software ramp), thesis (a) flips to YES. That trace is the
**single decisive follow-up** (sized in §7). Until then: **INFERRED NO.**

---

## 4. PITCH — same idea, different encoding (MEASURED)

| | KN5000 | KN7000 |
|---|---|---|
| where computed | SUB CPU `ToneGen_Calc_Pitch` 0x03D11F | MAIN CPU pitch calc; note→pitch16 resolved from the library voice record |
| method | `octave=(note+36)/12`, `semitone=rem` → 16-bit **semitone-ratio** from table 0x01217D (0x8000=1.0×); octave applied separately | `note_x256` in **1/256-semitone** units; sample-zone-relative `pitch18=((cls&1)<<16)\|data`; published as class 0x2401 = **+0x400 per semitone**, C4 = 0x0000C838 |
| representation on the wire | semitone-ratio register (+0x040) + octave-derived note-key (+0x400) | one absolute pitch word per octave-doubling scale |
| shared idea? | **YES** — both **precompute pitch in the CPU and publish it to a per-voice register**; the chip does not derive pitch from a note number itself |

So pitch is the **same architectural idea** (CPU-resolved pitch written to a per-voice
register), realized with different numeric encodings (ratio+octave vs a linear
1/256-semitone word). PROVEN-BY-CONSTRUCTION from both pitch routines.

---

## 5. WAVE ADDRESSING — identical model (MEASURED)

Both chips are **index-not-address** players:
- The CPU never writes a raw ROM byte pointer. It writes a compact **waveform/tone
  index** to a per-voice register (KN5000 group-0 bank-3 `+0x0C0`; KN7000 one of the
  group-4/group-40 registers, not yet pinned because the wave ROMs are undumped).
- The chip resolves index→ROM address **itself** by reading an index/parameter table
  at the very start of the wave ROM. KN5000 format is fully documented
  (`waveform-rom-format.md`: 198×4-byte index entries `{param_ptr, wave_offset}`,
  `byte_addr = wave_offset×16`, loop/keyzone/tuning in variable-length param records).
  The KN7000 note (`tg-voice-register-semantics.md` §3) infers the *same* model for
  IC201/205 and cites the KN5000 as the template.

**This is the strongest genuine design overlap.** Both are ROM-PCM samplers whose
sample selection is an index into a chip-read table. (SHARED, MEASURED for KN5000 /
INFERRED for KN7000 pending its ROM dump.)

---

## 6. VERDICTS

### (a) Does the KN5000 have an ADSR the HLE ignores? — **INFERRED NO**

- The SUB CPU programs **no per-voice ADSR** into IC303 (MEASURED, §2-§3). The
  KN7000's defining feature — three per-note 7-param EGs in group-0 — has **no
  counterpart** in the KN5000 register set.
- What the KN5000 HLE *does* ignore is smaller and real: the **velocity→level curve**
  (lookup 0x0118fe / `(vel²/4)+63`) and the periodic housekeeping re-write. Neither is
  an ADSR; modelling them is a *level-accuracy* refinement, not a missing envelope.
- The prediction embedded in the task ("KN5000 likely needs an ADSR resembling the
  KN7000's; the divergence is a shortcut artifact") is **not supported**. PREDICT-THEN-
  CHECK: I expected to find a hidden KN5000 EG in the "unknown" group-4/5 registers.
  **Miss** — those registers are written as **zero** at setup (L12801-12804). The
  divergence is a **real design difference**, not a stopgap.

### (b) Shared synthesis core once both HLEs are complete? — **PARTIAL**

| layer | shareable? | why |
|---|---|---|
| PCM sample playback (16.16 step, interp, loop) | **plausible** | both are ROM-PCM samplers |
| Wave addressing (index→chip-resolved address) | **yes, same model** | §5 |
| Pitch (CPU-precomputed, published to a voice reg) | **idea shared** | §4; encodings differ |
| Patch/tone descriptor format | **format shared** (codebase) | §3 caveat |
| **Envelope** | **NO** | KN7000 = 3×7-param per-note EG; KN5000 = none programmed |
| Host interface / voice count / sample rate | chip-specific | §1 |

A shared **PCM + wave-index + pitch-publish** helper is defensible *if/when* the
KN7000 HLE gains real-ROM playback (today it plays sine/donor placeholders because
IC203/204/207/208 are undumped). A shared **envelope** core is **not viable** — not
because of an HLE shortcut, but because the KN5000 firmware genuinely has no per-note
EG to share. This **refines** the prior "0% shared algorithms" verdict: the render/
accumulate skeleton is generic-only (agreed), and the *reason* the synthesis diverges
is now firmware-grounded rather than an artifact of unequal HLE effort.

---

## 7. If Felipe still wants the KN5000's dynamics improved (sized, do-NOT-implement here)

The honest HLE-improvement targets for the KN5000 are **level accuracy** and a
**definitive envelope-path trace**, NOT bolting on the KN7000's ADSR:

1. **[decisive, ~½ day] Settle thesis (a) for good.** Trace MAIN-CPU patch data
   `0x832000` → sound engine → inter-CPU command → SUB CPU. Instrument the SUB CPU
   note-on for a *contrasting* pair (a fast-decay piano vs a slow-attack pad/strings)
   and diff **every** IC303 register write, not just the known 22. If a group-4/5
   register (or the `Voice_TickNoteDecay` re-write cadence) varies with the tone's
   attack/decay, the KN5000 *does* have a chip/SW envelope and it becomes a real HLE
   target. If the writes are byte-identical bar pitch/velocity, thesis (a) is closed.
   *This is analysis, and gates everything below.*

2. **[small, ~½ day] Model the velocity→level curve** in `kn5000_tonegen_device`
   (currently `(vel^2/4)+63` approximation vs the firmware's 0x0118fe lookup). Replace
   the linear velocity→volume with the real curve; verify a soft vs hard keystroke
   matches the firmware's level word. Low risk, improves loudness realism.

3. **[medium, only IF step 1 finds an envelope] Model the found envelope.** If step 1
   reveals per-tone rate/level in a group-4/5 register, add a matching EG stage to the
   HLE using the KN7000's `eg_tau(rate)` law as a starting calibration. Do **not**
   assume the KN7000's exact 7-param shape — fit the KN5000's own register semantics.

4. **[do not do] Force the KN7000's 3×7-param EG onto the KN5000.** There is no
   firmware evidence for it; it would be plausible-but-wrong audio — the exact failure
   mode the prior pass warned against.

---

## 8. Honest design-similarity score

| aspect | verdict | label |
|---|---|---|
| Same chip family / part | **No** (Toshiba vs NEC, different register architecture) | MEASURED |
| Sample source (real ROM PCM) | **Same** in HW (both) | MEASURED (KN5000) / by-design (KN7000) |
| Wave addressing (index→chip-resolved) | **Same model** | MEASURED / INFERRED |
| Pitch (CPU-precomputed, published to voice reg) | **Same idea**, different encoding | MEASURED |
| Patch descriptor format (has EG fields) | **Shared** (codebase) | MEASURED (exists) |
| **Per-note ADSR programming** | **KN7000 only** | MEASURED |
| Host interface / voice count / sample rate | chip-specific | MEASURED |

**Overall:** the two are cousins in the **sample-playback + pitch-publish** half of
their design (a genuine, evidence-backed overlap that the prior HLE-only pass
under-credited), but they **diverge sharply on envelope**: the KN7000 is an
envelope-programmable synth voiced per note by the CPU, while the KN5000 is a more
sample-centric player that leans on the recorded sample and a static velocity level.
Felipe's thesis is **half right** — the *architectures rhyme on sampling and pitch* —
and **half wrong** — the KN5000 is **not** missing a KN7000-style ADSR; it never had
one at the chip-programming level.
