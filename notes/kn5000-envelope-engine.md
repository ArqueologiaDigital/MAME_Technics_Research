# KN5000 SOFTWARE amplitude envelope — the engine the prior pass missed

Author: autonomous RE pass, 2026-07-23. Requested by Felipe Sanches.

**Corrects** `notes/kn5000-vs-kn7000-tonegen-design.md` and `notes/kn5000-envelope-trace.md`,
which concluded the KN5000 "has no per-note envelope" and leans on the raw PCM
sample + a static velocity level. **That verdict was wrong.** Felipe's objection —
"the machine has a GUI for setting envelope values, so the envelope is real and
applied somewhere" — is correct. This note finds where and how.

Evidence labels: **MEASURED** (read from disassembly), **PROVEN-BY-CONSTRUCTION**
(follows directly from a traced code path), **INFERRED** (strong deduction),
**SPECULATIVE**.

Source: KN5000 SUB-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
(labels are ROM addresses: `LABEL_0xxxxx` = address 0x0xxxxx); symbols
`symbols/{subcpu,maincpu}_symbols_reference.txt`.

---

## TL;DR — the corrected verdict

**The KN5000 DOES have a per-note, multi-stage, multi-domain envelope.** It is a
**SOFTWARE envelope generator running in the SUB CPU**, clocked by the audio timer
tick, that walks active voices and **rewrites the IC303 level register over the
note's lifetime**. It is *not* in the note-on register writer (which is why the
prior pass, which only inspected `ToneGen_WriteVoiceParams` and the boot block,
missed it). It is in the **periodic `Audio_Process_Init` pipeline** — specifically
the per-voice envelope steppers **`LABEL_026E5B` (amplitude)** and **`LABEL_026EC3`
(expression/2nd domain)**, which call **`ToneGen_WriteSingleReg` (0x02D41B)** to
write IC303 `0x100000/0x100002` every time an envelope segment fires.

The user-facing GUI exists too, and it is a full synth edit section, not just
organ drawbars: **`SEAMPENV1/2`, `SEPITENV1/2`, `SEFILENV1/2`** (Sound-Edit
AMP/PITCH/FILTER **ENVELOPE**) title functions in the MAIN CPU — the KN5000 exposes
amp + pitch + filter envelopes, *the same three domains as the KN7000*. The prior
note's claim "there is no AMPLITUDE/PITCH/FILTER ENVELOPE edit screen like the
KN7000's" is **falsified** (see §5).

So the two tone generators are far more alike than the prior pass concluded: **same
conceptual envelope design (per-note, multi-stage, per-domain amp/pitch/filter,
driven by patch bytes + velocity + keyscale), implemented at a different LAYER** —
KN7000 = hardware EG clocked by the chip; KN5000 = software EG clocked by the
sub-CPU audio tick.

---

## 1. The named tables (task item 1) — MEASURED

Contents (disasm L616-624), each **18 bytes** = 18 per-voice-group slots:

```
Voice_AttackDecay_Widths   (0x00F507):  20 10 04 0C 00 00 00 00 00 00 00 00 00 00 00 00 40 40
Voice_EnvelopeRate_Lookup  (0x00F519):  0C 06 06 04 04 04 04 04 02 02 02 02 02 02 02 06 40 40
Voice_CommandIndexTable    (0x00F4EC):  ... (27 entries, selects which of the 18 groups)
```

- **`Voice_AttackDecay_Widths`** = per-group **stage WIDTHS (durations)**: 0x20, 0x10,
  0x04, 0x0C ticks … tail groups 16/17 = 0x40.
- **`Voice_EnvelopeRate_Lookup`** = per-group **envelope RATES**: 0x0C, 0x06, 0x04, 0x02 …
  tail groups = 0x40. Small = slow, matching a rate/step meaning.

**How indexed / by what (MEASURED — init routine `LABEL_021ECB`, L12980-13060):**
`LABEL_021ECB(A)` loops `i = 0..17` and copies `table[i]` into a per-group state
block at **base 0x112D, stride 0x1E (30 bytes)**:

```
for i in 0..17:
    if A == 0:  (0x112D + i*0x1E)[0] = Voice_AttackDecay_Widths[i]     ; boot: LD WA,0 / CALL 021ECB (L38146)
    else:       (0x112D + i*0x1E)[0] = Voice_EnvelopeRate_Lookup[i]    ; mode reload (L23675/23681)
    (0x112D + i*0x1E)[1] = 0                                            ; stage index
    for stage in 0..6:  (0x112D + i*0x1E)[2 + stage*4] = 0 (dword)      ; 7-stage accumulators
```

So each of the 18 groups gets a **30-byte envelope state block**: `[0]=width/rate,
[1]=stage index, [2..29]=7 × 32-bit accumulators`. **Seven stages of per-group
envelope state** — this alone refutes "no envelope machinery." `A` selects whether
the block is seeded with the *width* table or the *rate* table (boot uses widths).

`TONEGEN_READ_RELEASE` (0x03D100, L51527) is a red herring for amplitude: it is the
**note-EVENT decoder** on the keyboard/event FIFO at **0x110000** (a different chip
region than IC303's 0x100000). It handles an incoming *release event* (clears
velocity, recomputes pitch via `ToneGen_Calc_Pitch`). Not the amplitude EG. Decoded
for completeness; the amplitude engine is elsewhere.

---

## 2. The periodic envelope PROCESSOR (task item 2, the crux) — MEASURED / PROVEN-BY-CONSTRUCTION

### The clock
- **Timer ISR** `0x01FB76` (dispatched via `OFFSETS_F460`) sets **bit1 of 0x103E**
  periodically (`SCF / STCF A,(103Eh)` with A=1, L38-area / L9490-9510). MEASURED.
- **`Audio_Main_Loop` (0x01FAE3)**: `BIT 1,(103Eh) → RES 1 → CALL Audio_Process_Init`
  (L9428-9433). MEASURED.
- **`Audio_Process_Init` (0x034CDA, L38150)** alternates on toggle `0x041342`:
  - path A: `LABEL_027A46` + `LABEL_03611E`
  - path B: **`LABEL_02219F`** + **`LABEL_027AC4`**

  Both paths run each audio tick (on alternate calls). MEASURED.

### The per-voice envelope step — `LABEL_026E5B` (amplitude) — MEASURED

Called from the dirty-voice flush in `027A46`/`027AC4` (L22646, L22732) for every
slot whose envelope-active flag `(+0x2f) bit15` is set:

```
LABEL_026E5B(slot):                     ; slot = 0x04308E + n*0x47
    IZ = slot[+0x2f]                    ; 16-bit envelope counter (bit15=active, hi byte=coarse steps, lo=fine)
    if bit15(IZ):
        IZ -= 0x0100                    ; << advance envelope one step per tick
        if (IZ & 0x7F00) == 0:          ; coarse counter reached a segment boundary
            WA = slot[+0]               ; voice number -> IC303 register index (group-0 gate/level reg)
            BC = slot[+0x2d]            ; the segment's LEVEL word
            CALL ToneGen_WriteSingleReg ; << REWRITE IC303 LEVEL over the note's lifetime
            CALL LABEL_022587           ; -> LABEL_021EA1: advance envelope stage
            RES 15, IZ
    if bit7(IZ):                        ; fine sub-counter
        IZ -= 1
        if (IZ & 0x7F) == 0:
            CALL LABEL_02CD71           ; load NEXT segment (recompute level, re-upload)
            IZ &= 0x7F
    slot[+0x2f] = IZ
```

**`ToneGen_WriteSingleReg` (0x02D41B, L29919)** is the definitive IC303 write:
```
    RES 7,(P6) ; LD (100000h),WA        ; latch register index (voice# = group-0 base reg)
    SET 7,(P6) ; LD (100002h),IZ        ; write data (the ramped level)  << P6.7 = CS strobe
```
This **is** the register-indirect IC303 write the prior notes attributed only to
note-on. Here it is being driven **periodically, per active voice, with a
time-varying level** — the software amplitude envelope. PROVEN-BY-CONSTRUCTION.

### The 2nd-domain step — `LABEL_026EC3` — MEASURED
Same shape on `slot[+0x31]/[+0x35]`; its writer `LABEL_02D670` targets IC303 reg
**`voice + 0x180`** (the expression/level register). So a *second* per-voice
envelope drives the +0x180 register in parallel. (A third — pitch/filter — is
implied by the GUI, §5; its exact register not pinned here.)

### The lifecycle/poll manager — `LABEL_02219F` (path B) — MEASURED
Walks 16 voice control-blocks (base **0x148D, stride 0x27**), and for each:
- **READS** the IC303 level readback (`ADD WA,0180h; CALL DAC_Write_Sample` — a
  reg-index read of `0x100000`), masks to 14 bits, `>>5`, stores into `(voice+0x25)`;
  when the level has fallen below `0x80` it advances the envelope stage
  (`LABEL_021E83`) or, for dead voices, **silences** them via `LABEL_02B4A1`
  (writes IC303 `voice+0xC0=0x0000`, `voice+0x00=0x7E00`) and deallocates
  (`LABEL_02150D`). This is voice-stealing + segment sequencing driven by polling
  the chip's current level. MEASURED.

**Per-voice envelope STATE (sub-CPU RAM) — MEASURED:**
| field | meaning |
|---|---|
| slot `+0x2d` | current segment **LEVEL** word written to IC303 (e.g. `0xF000\|lvl` normal, `0xFE00\|lvl` release; L18925-18933) |
| slot `+0x2f` | **amplitude envelope counter** — bit15 active, hi byte = coarse step count (width), lo byte = fine rate |
| slot `+0x31 / +0x35` | 2nd-domain (expression) counter/level |
| voice `+0x22` | stage-flag byte (bits 0/1/2/3/7 = stage transitions; L12945 `LABEL_021EA1`) |
| voice `+0x25` | current level readback from chip (poll) |
| voice `+0x26` | per-voice rate loaded at note-on (from `Voice_SFX_ModulationTable` 0xF633+5) |

---

## 3. Stage structure (task item 3) — MEASURED + INFERRED

- **Multi-stage, multi-domain.** Stage progression lives in the state-flag byte
  `voice+0x22` (`LABEL_021EA1`/`021E83`, L12945-12980): bit7 = released/dead, and
  bits 1/2/3 step attack → decay → sustain (`RES 3; SET 2`, `SET 1`). Segment
  advance is scheduled through a **doubly-linked-list scheduler** (three link pairs
  per voice at `+0/+4`, `+8/+c`, `+10/+14`; insert/remove `LABEL_021C5B..021E15`)
  — the envelope is *time-ordered* across voices, not a fixed per-sample loop.
  MEASURED.
- **Level per stage** = `slot[+0x2d]`, recomputed each segment by
  `LABEL_02CD71` → `LABEL_026769` (velocity/keyscale level via log table
  **0x0118FE**) and packed as `0xF000|lvl` (sustain/normal) or `0xFE00|lvl`
  (release), the mask chosen by mode var **0x04134C** (release modes 5/6 → `0xFE00`;
  L18916-18933, L25555-25626). MEASURED.
- **Rate/width per stage** = `slot[+0x2f]` seeded at note-on from the patch tone
  record (§4) blended with keyscale; decremented `-0x100`/tick (coarse) and `-1`/tick
  (fine). So segment *duration* is set by the width byte, segment *steepness* by the
  fine-rate byte. MEASURED (mechanics) / INFERRED (that this equals a classic ADSR
  A/D/S/R with ~4 stages/domain — the flag bits and the two masks strongly imply
  attack/decay/sustain + a distinct release).
- **Curve:** the ramp is **piecewise-linear between target levels** (linear counter
  decrement), but the level *targets* pass through the **logarithmic** velocity/level
  table 0x0118FE, so the perceived contour is quasi-exponential. INFERRED.
- **Velocity + keyscale feed in** at each segment's level recompute
  (`LABEL_026769/026975/026AAA`, L20754-21112): base level from 0x0118FE indexed by
  a patch byte, `+` velocity scaling (`LABEL_022BB8`), `+` key-scaling
  (`LABEL_022B2A`), clamped 0..0xFF. MEASURED.

---

## 4. GUI → engine path (task item 4) — MEASURED + PROVEN-BY-CONSTRUCTION

The note-on envelope-rate seed is computed from **patch tone-record fields** carried
from the MAIN CPU Table-Data ROM `0x832000` over the inter-CPU protocol
(`LABEL_0253FE`, L18653-18700):

```
DE = tone_record[+0x0f]                       ; envelope rate/width base
   + (subrecord[+0x5c] - 0x40)                ; a bipolar depth trim
   + tone_record[+0x66]                       ; keyscale/offset
   clamp 0..0x7F ; <<8                         ; -> seeds slot[+0x2f] coarse field
   (mode 0x04134C selects release vs normal)
```

Fields `+0x0f / +0x12 / +0x66` of the tone record and `+0x5c` of its sub-record are
the **per-patch envelope bytes**. `table-data-rom.md` already documents 0x832000 as
holding "envelope, filter, LFO" per-patch parameters — this is the datapath by which
those bytes reach the sub-CPU EG. PROVEN-BY-CONSTRUCTION (the fields are read and
become the counter seed).

**The editor GUI (MAIN CPU) — MEASURED (`symbols/maincpu_symbols_reference.txt`):**
a full **SOUND EDIT** section with per-domain **ENVELOPE** pages:
```
SEPITENV1TITLEFUNC 0xF038CE   SEPITENV2TITLEFUNC 0xF03901   ; PITCH envelope 1/2
SEAMPAMP1/2 0xF03967/0xF0399A                                ; AMP level
SEAMPENV1TITLEFUNC 0xF039CD   SEAMPENV2TITLEFUNC 0xF03A00   ; AMPLITUDE envelope 1/2
SEAMPLFO1 0xF03A33                                           ; AMP LFO
SEFILENV1TITLEFUNC 0xF03BCB   SEFILENV2TITLEFUNC 0xF03BFE   ; FILTER envelope 1/2
```
The user edits AMP/PITCH/FILTER **envelope** pages → values stored in the patch
record → shipped to the sub-CPU → seed `slot[+0x2d]/[+0x2f]` → the software EG above.
**Felipe's premise confirmed:** the GUI exists (three envelope domains) and it drives
the engine.

---

## 5. Comparison to the KN7000 EG (task item 5)

| aspect | KN7000 (`kn7000-sound-subsystem.md`) | KN5000 (this note) |
|---|---|---|
| Where the EG runs | **HARDWARE** in the NEC tone-gen chip; CPU writes rate\|level pairs, chip ramps | **SOFTWARE** in the SUB CPU; CPU decrements a counter each audio tick and writes the level itself |
| Clock | chip-internal (eg_tau rate law) | audio timer ISR (0x103E bit1) → `Audio_Process_Init` → `026E5B`/`026EC3` |
| Domains | **3 parallel**: amp / pitch / filter (r0..rB) | **≥2 confirmed** (amp reg[voice], expression reg[voice+0x180]) + amp/pitch/filter **all present in the GUI** → 3 by design |
| Stages | 4-stage per domain (ATK/PEAK, DCY1/SUS1, DCY2/SUS2, GATE) + 7-stage release ramp | multi-stage via `+0x22` flags + linked-list sequencer; per-segment level+width; distinct release mask (0xFE00) |
| Level curve | rate\|level register pairs; hardware interpolation | piecewise-linear between targets, targets via log table 0x0118FE (≈exponential) |
| Source data | per-note tone descriptor (0x4C03…), velocity | per-patch tone record (0x832000), velocity, keyscale |
| Release | recomputed at key-up, 6-write burst | recomputed per segment (`02CD71`), mask 0xFE00, silence via `02B4A1` |

**Same shape, different layer.** Both are **per-note, multi-stage, per-domain
(amp/pitch/filter) envelopes edited by the user and driven from patch data +
velocity**. The KN7000 offloads the ramp to chip hardware; the KN5000 runs the ramp
in sub-CPU software at the audio-tick rate and pokes the IC303 level register. This
is a **strong architectural rhyme**, not the divergence the prior note claimed.

### What the prior pass missed and why
- It inspected only **`ToneGen_WriteVoiceParams` (0x02D0FD)** (note-on) and the boot
  block, saw no rate/level EG *block* in the 22 note-on writes, and concluded "no
  envelope." **Correct about note-on, wrong about the machine:** the EG isn't
  programmed as a chip register block — it's a **software loop** that *is* the EG,
  living in the `Audio_Process_Init` periodic pipeline it never traced.
- It read the "group-4 written as zero" fact as "no envelope shaping." Those
  registers are zero because the shaping is applied later, per tick, to the group-0
  gate reg and the +0x180 reg by `026E5B`/`026EC3`.
- It ran the WRONG BINARY (stock MAME v0.279, main CPU wedged) so the voice engine
  never executed — no runtime signal to contradict the static misread.

### PREDICT-THEN-CHECK
Predicted: a software envelope that rewrites the IC303 level register periodically.
**Hit** — `026E5B`→`ToneGen_WriteSingleReg` does exactly that, clocked by the timer,
per active voice, with a time-varying level. Predicted the tables would be amplitude
rate/level: **hit** — `Voice_AttackDecay_Widths`/`Voice_EnvelopeRate_Lookup` are
per-group stage widths/rates seeded into 7-stage state blocks. One nuance vs the task
framing: the *lifecycle* half (`02219F`) also **polls** the chip's level readback to
sequence/steal voices — the design is a software EG **plus** a poll-driven segment
sequencer, not a pure write-only ramp.

---

## 6. Sized HLE plan — model the software envelope in `kn5000_tonegen` (do NOT implement here)

The KN5000 MAME HLE currently ignores this. Plan, sized, gated:

1. **[analysis, ~½ day] Live-confirm the ramp (task item 6).** On our binary
   `/home/fsanches/compartilhado/kn7000_mame_build/kn7000` (KN5000 boots to the play
   screen), pick a fast-decay vs slow-attack sound, hold a note, and watch IC303
   `0x100000/0x100002` writes over time via the debugger. Expect `026E5B`
   (0x02D...) to re-emit the group-0 level reg with a falling/rising value at the
   tick rate, differing per sound. Small/timeout-wrapped captures, isolated nvram.
   Gates the numeric calibration below.
2. **[small, ~½ day] Model the counter.** Add per-voice `env_level` (from `slot+0x2d`),
   `env_counter` (from `slot+0x2f`), stepped each HLE audio frame at the sub-CPU
   tick cadence: `-0x100` coarse; on segment boundary load next target (velocity/
   keyscale via a table matching 0x0118FE) and apply as the voice VCA level.
3. **[medium, ~1 day] Wire the patch bytes.** Route tone-record fields
   `+0x0f/+0x12/+0x66/+0x5c` (0x832000) into the segment width/rate + level targets;
   honor mode 0x04134C for the release mask (0xFE00 vs 0xF000).
4. **[medium] Second + third domains.** Add the +0x180 (expression) envelope and,
   once the pitch/filter registers are pinned, the pitch/filter envelopes — mirror
   the KN7000's 3-domain layout but fit the KN5000's own segment semantics (do NOT
   copy the KN7000's exact 7-param numbers).
5. **[do not] Assume the KN7000 rate law.** Calibrate the KN5000's own counter →
   time mapping from step 1; only borrow `eg_tau` as an initial guess.

Risk: low-to-medium. This replaces the HLE's "sample tail + static velocity level"
with the real time-varying contour and should audibly fix fast-decay/slow-attack
sounds.

---

## 7. Address index (quick reference, all MEASURED)

| routine / symbol | addr | role |
|---|---|---|
| `Voice_AttackDecay_Widths` | 0x00F507 | per-group stage WIDTHS (18 B) |
| `Voice_EnvelopeRate_Lookup` | 0x00F519 | per-group stage RATES (18 B) |
| `LABEL_021ECB` | 0x021ECB | init: seed 0x112D env state blocks from the tables |
| 0x112D (RAM) | — | 18 × 0x1E env state blocks (byte0=width/rate, +2..29 = 7 stage accumulators) |
| `LABEL_02219F` | 0x02219F | periodic lifecycle: poll IC303 level, sequence/steal (path B) |
| `LABEL_027A46` / `LABEL_027AC4` | 0x027A46 / 0x027AC4 | periodic dirty-voice flush (calls the steppers) |
| **`LABEL_026E5B`** | **0x026E5B** | **amplitude envelope step → writes IC303 level** |
| `LABEL_026EC3` | 0x026EC3 | 2nd-domain (expression) envelope step |
| `LABEL_02CD71` | 0x02CD71 | load next envelope segment (recompute + re-upload) |
| **`ToneGen_WriteSingleReg`** | **0x02D41B** | IC303 write: `(100000h)=reg`, `(100002h)=data`, P6.7=CS |
| `LABEL_02D670` | 0x02D670 | IC303 write to reg `voice+0x180` (expression) |
| `LABEL_02B4A1` | 0x02B4A1 | silence a dead voice (reg+0xC0=0, reg+0=0x7E00) |
| `Audio_Process_Init` | 0x034CDA | periodic dispatcher (alternates paths A/B) |
| `Audio_Main_Loop` | 0x01FAE3 | consumes timer flag 0x103E bit1 |
| `LABEL_0253FE` | 0x0253FE | note-on: seed env counter from patch record (0x832000 bytes) |
| `SEAMPENV1/2` `SEPITENV1/2` `SEFILENV1/2` | 0xF039CD.. (MAIN) | Sound-Edit AMP/PITCH/FILTER envelope GUI |
| `TONEGEN_READ_RELEASE` | 0x03D100 | note-EVENT release decoder on FIFO 0x110000 (NOT the amp EG) |
