# KN5000 tone-generator (IC303 / TC183C230002) — THE DEFINITIVE VOICE-PIPELINE MODEL

Author: autonomous synthesis pass, 2026-07-24. Requested by Felipe Sanches.
**Synthesis only** — no `src/` edits, no rebuild. This note UNIFIES and ADJUDICATES the seven
prior pipeline/stage notes into one end-to-end model, re-grounding the load-bearing claims
directly in the v142 sub-CPU disasm and the driver, and re-checking every cross-note conflict
against the live-capture ground truth. It is the single reference the HLE should be built against.

Evidence labels: **MEASURED** (read live / from ROM bytes / from disasm), **INFERRED** (deduction
from measured data), **SPECULATIVE** (unproven), **PROVEN-BY-CONSTRUCTION** (follows a traced path).

Sources (each independently re-verified this pass):
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm` (label
  `LABEL_02XXXX` = runtime DRAM address; code runs decompressed in sub RAM `map(0,0x0fffff).ram()`).
* main-CPU disasm `kn5000-roms-disasm/archive/asl/maincpu/kn5000_v10_program.asm`.
* driver `kn7000_mame/src/mame/matsushita/kn5000.cpp`; HLE `kn5000_tonegen.{cpp,h}`.
* the ground-truth dataset `notes/kn5000-live-captures.md` (16 SOUND-GROUP instruments × 7 notes,
  the full IC303 note-on register stream) and the stage notes `kn5000-pipe-{tonerecord,partialset,
  resolver,registers,chipmap}.md`, `kn5000-ic307-content-map.md`, `kn5000-{tone-record,wave-number,
  real-sample-select,faithful-render,pitch-velocity,tonegen-register-semantics}.md`.

Disasm anchors re-verified this pass (byte-read, not paraphrased): the six +0x040 builders
`LABEL_022A3F..022AE7` (asm L14295-14361), the SET-index read `LABEL_032682` (L34747-34770,
`LD C,(XBC+002h)`), the register burst `ToneGen_WriteVoiceParams` (L29565+, struct+off→reg
+0x0N0), and the driver wave-ROM map (`kn5000.cpp` L1152-1164: IC304/305/306 = **BAD_DUMP copies
of IC307**, IC307 real at region 0xC00000).

**Governing principle (never violated below):** IC303 is driven ONLY through its hardware
interface — register-address latch `0x100000`, register-data `0x100002`, keybed `0x110000`. It has
NO access to sub-CPU RAM. So the per-voice waveform selection MUST already be encoded in the
register writes the chip receives; the HLE selects from **register inputs only**.

---

## 0. TL;DR — the whole model in one screen

```
 PANEL SOUND-GROUP + sound
        │  main-CPU: SOUND_DATA_SECTION_PTRS[group] → per-sound {lo,hi} 16-bit tone selector
        │            (program ROM 0xE023B0 / e.g. BRASS 0xE06BB0→0xE06DB0; asm L36399-36447)
        ▼
 inter-CPU latch (0x140000→0x120000, MicroDMA ch2→ch0; cmd=(chan<<5)|(len-1), 0xE1 bulk)
        │  (the resident tone/voice DB is copied ONCE at boot: main 0x830000→sub 0x050000 verbatim,
        │   +4 more 64KB chunks — SubCPU_Send_Payload; so every tonerec ptr 0x05xxxx..0x09xxxx has a
        │   ROM twin at ptr-0x7E0000. PROVEN: ROM 0x83253A == live sub 0x05253A, byte-identical.)
        ▼
 sub-CPU tonerec  = 0x041368 + part*0x11F + 0x6E + zone*0x25      (runtime-built, per part/zone)
        │  first 0x18 bytes = six LE pointers ptr[0..5]; trailer holds tonerec[+0x1a] (legacy bank)
        │  ptr0 → tone-header record: {type, bank@+1, SET@+0x02, N×0x51 partial blocks, 16B NAME}
        ▼
 STAGE A  LABEL_032682 → LABEL_03248B   :  SET = ptr0[+0x02]  (+ ptr0[+0x01], part, note)
        │                                    → absolute SET-descriptor pointer  (→ desc+0x1b/+0x1f)
        ▼
 STAGE B  LABEL_023849  (first precompute in the note-on chain LABEL_02B4E3):
        │   key   = (desc+0x06 >> 8) & 0x7F                    ; note ± per-instrument keyscale
        │   zs    = ptrC[key]           ; ptrC = 128-entry note→zoneslot keytable
        │   E     = ptrA[4 + zs]        ; ptrA = zoneslot→record-index remap
        │   rec   = ptrB + E*stride     ; ptrB = partial-record array; stride from SET[0] bits5/6/7
        │   +0x040 = rec[0]             ; the six builders LABEL_022A3F..022AE7
        ▼
 44-byte chip scratch 0x0451CC  ──ToneGen_WriteVoiceParams (L29565)──►  IC303 registers
        │   +0x02→+0x040(WAVE) +0x04→+0x080(level,bit15=gate) +0x06→+0x0C0 +0x0a→+0x140
        │   +0x0e→+0x400(PITCH) +0x10→+0x440 +0x12→+0x480 +0x16→+0x500 +0x18..+0x2a→+0x800..+0xA40(env)
        ▼
 IC303 :  wave selected by the 16-bit +0x040 = { class[15:12] , entry[11:0] }  and NOTHING ELSE.
          The chip's internal address decoder turns {class,entry} into a chip-select (IC304-307) +
          a ROM address; each chip's own 198-entry index → PCM start; the chip loops the sustain
          autonomously (IC307 stores NO root, NO loop points — only per-key fine-tune).
```

**The final register-only selection rule (what the HLE must key on):**

```c
uint16_t w = regs[1];                 // +0x040 — the ONLY per-voice wave-selection register
int   cls   = (w >> 12) & 0x0F;       // MEASURED: per-instrument wave FAMILY / bank  (0..7 seen)
int   entry =  w        & 0x0FFF;      // MEASURED: multisample KEY-ZONE index — FULL 12 bits
                                       //   (not 8: Sax entry 0x13E, GM 0x112 overflow a byte)
// entry = { page = entry>>8 , local = entry&0xFF }  — page bit distinguishes Sax/GM (page 1)
// +0x440/+0x480 are per-note-on voice/DMA SLOT COUNTERS — NEVER select on them.
```

`{cls, entry}` is exactly the value the firmware computes from (SET index, played note) via STAGE
A+B and is the only wave-selection information IC303 ever receives (§3, airtight). Root pitch is
NOT in the registers (it lives in the undumped chips) — the HLE gets absolute pitch from the played
note (§5). The numeric `{cls,entry}→physical-PCM` map is the chip's black box (§4); with only IC307
dumped, the HLE uses a **labelled placeholder** that preserves the two properties that ARE supported
(per-class banding + consecutive-entry→consecutive-index multisample coherence) — §7, §9.

---

## 1. The end-to-end chain, stage by stage (MEASURED, with cites)

### 1.1 Main-CPU selection → delivery (MEASURED; `-pipe-tonerecord.md`)
Panel SOUND-GROUP+sound → main indexes `SOUND_DATA_SECTION_PTRS` (0xE023B0, 16 dwords) → a per-sound
3-byte record `{lo,hi,0xFF}` (e.g. BRASS `SOUND_DATA_BRASS_PTRS` 0xE06BB0→records at 0xE06DB0, asm
L36447). The `{lo,hi}` pair is a 16-bit **tone selector** shipped to the sub-CPU over the inter-CPU
latch (main writes `0x140000`→sub `/INT0`; bulk via TMP94C241 MicroDMA ch2→ch0; framing
`(chan<<5)|(len-1)`, `0xE1`=bulk). The **resident tone/voice DB is not re-sent per selection** — it
is copied ONCE at boot (`SubCPU_Send_Payload`, main asm): **main 0x830000→sub 0x050000 verbatim** (+4
more 64 KB chunks to 0x0A0000). Cross-validated byte-for-byte: ROM 0x83253A == live sub-RAM 0x05253A.
Consequence used throughout: any tonerec pointer `S` (0x05xxxx..0x09xxxx) has a ROM twin at
`S-0x7E0000`, so the whole DB is statically readable. (The exact voice-change opcode and the routine
that writes the tonerec's 6 pointers are INFERRED, not isolated — the one honest gap on this stage.)

### 1.2 The tonerec (MEASURED live; `-tone-record.md`, `-voice-pipeline.md`)
`tonerec = 0x041368 + part*0x11F + 0x6E + zone*0x25`. First 0x18 bytes = six LE pointers `ptr[0..5]`
into the resident DB; then a 0x0D-byte trailer with `tonerec[+0x1a]` (legacy bank). Live (RIGHT1=
Piano p0 / RIGHT2=Brass p1 / LEFT=E.P. p2):
```
Piano p0: ptr0=0x05253A  ptr0[+0x02]=0x00  tonerec[+0x1a]=0x00
Brass p1: ptr0=0x05B66C  ptr0[+0x02]=0x38  tonerec[+0x1a]=0x00
E.P.  p2: ptr0=0x0532B7  ptr0[+0x02]=0x06  tonerec[+0x1a]=0x00
```
* **ptr0** → tone-header record: `{ +0x00 type=00, +0x01 bank/flags, +0x02 SET index, … , N×0x51
  partial blocks, 16-byte NAME }`. The NAME field is the UI sound name (the "Sound Name Error" data).
* **ptr1** → per-partial key-zone/scaling table (groups delimited by `7F 7F 7F`).
* **ptr2..5** → 15-byte oscillator records `flag | START(3B) | 00 | LOOP(3B) | 00 | 0C | rate | 42
  80 42 00`. **These START/LOOP 24-bit values are sub-CPU DRAM pointers (0x02xxxx–0x03xxxx, inside
  the 1 MB sub DRAM), feeding firmware-side envelope/LFO/fine-tune math — NOT waveform-ROM addresses,
  and they NEVER reach IC303** (§8 ledger item #1; the "24-bit sample address" trap, retired).

### 1.3 `ptr0[+0x02]` = multisample SET index — ALL 17 verified (MEASURED, static ROM == live)
Read as `C` in `LABEL_032682` (asm L34751 `LD C,(XBC+002h)`). All 16 SOUND-GROUP defaults + Modern
E.P. match live (`-pipe-tonerecord.md §5`): Piano 0x00, Guitar 0x14, Strings 0x64, Brass 0x38, Flute
0x40, Sax 0x4C, Mallet 0x09, World 0x1F, Organ 0x58, OrchPad 0x64, Synth 0x79, Bass 0x2B, Drawbar
0x88, AccReg 0x51, GM 0x70, Drums 0x00, E.P. 0x06. **SET is per-group-scoped, not global** (Piano &
Drums both 0x00; Strings & OrchPad both 0x64).

### 1.4 STAGE A — SET index → SET-descriptor pointer (MEASURED disasm; `-pipe-partialset.md §2`)
`LABEL_032682`→`LABEL_03248B` decompose the SET byte as a *structured address*: `SET&0x30` = primary
family (dispatch), `SET&0xC0` = sub-family, `SET&0x0F` = group, `ptr0[+0x01]&0x7F` = fine slot. The
composite `idx = ((SET&0x0F)<<7) + (ptr0[+0x01]&0x7F)` indexes runtime tables (`*(0x045310)` base =
0x050000, `*(0x045314)` tone-bank struct) → an absolute **SET-descriptor pointer**, stored to
desc+0x1b/+0x1f (asm L26969). (Stage A's *arithmetic* is fully traced; its *input tables* are runtime
data read live, not re-derived from boot ROM — the end-to-end chain is validated in §1.5 regardless.)

### 1.5 STAGE B — SET pointer → +0x040 = rec[0] (MEASURED disasm + LIVE-VALIDATED 7/7)
`LABEL_023849` (asm L15805, first precompute called by the note-on builder `LABEL_02B4E3` L26813)
walks:
```
SETp = *(desc+0x1f)
ptrA = *(SETp+1)+base ; ptrB = *(SETp+5)+base ; ptrC = *(ptrA)+base     (base=0x050000)
key  = (desc+0x06>>8)&0x7F ; zs = ptrC[key] ; E = ptrA[4+zs]
rec  = ptrB + E*stride     ; +0x040 = rec[0]
```
stride chosen from **SET[0] bits 5/6/7** by one of six builders `LABEL_022A3F..022AE7`
(asm L14295-14361, byte-verified this pass). Each builder is literally:
```
MULS_DE <stride> ; LDA XBC,XBC+DE ; LD (XWA+00fh),XBC ; ORW (XWA+001h),<class> ; LD WA,(XBC) ; LD (0451CEh),WA
```
i.e. `rec = set_base + zone*stride`, store the partial pointer to desc+0x0f, OR a **pitch-class
constant into desc+0x01** (7000/5000/3000/1000/4000/none), and copy **rec[0] → scratch 0x0451CE →
register +0x040**. Strides: 022A3F=0x0F, 022A61=0x0C, 022A83=0x0D, 022AA4=0x0A, 022AC5=0x06,
022AE7=0x04. LIVE `decode_walk.lua` reconstructed rec[0] for Piano/Guitar/Organ **7/7 exact** vs the
register capture (Piano C2..C6 → 7001/7004/7007/7008/7008/700A/700D). **CRITICAL:** the class OR'd
into desc+0x01 is the *pitch* class and is INDEPENDENT of +0x040's high nibble — Piano runs builder
022AC5 (ORs 4000) yet its +0x040 nibble is **7**; the +0x040 nibble is `rec[0]` DATA, not the builder
class (this retires `-voice-pipeline.md §3.2`'s builder→instrument table; §8 item #2).

---

## 2. The register file IC303 receives (MEASURED; `-pipe-registers.md`, burst L29565)

Address = `(group<<8)|(bank<<6)|channel`, channel = voice 0..63. HLE `reg_idx = group_map[group]*4 +
bank` (h L204). One `ToneGen_WriteVoiceParams` call = one oscillator; struct 0x0451CC bursts verbatim:

| scratch | → reg | HLE reg | role (MEASURED) | per-instrument? |
|---|---|---|---|---|
| +0x02 | **+0x040** | regs[1] | **WAVE select = {class<<12 \| entry}** | **YES — the selector** |
| +0x04 | +0x080 | regs[2] | output level; **bit15 = voice-arm gate** (SET on load L29594, RES at end L29907) | per-velocity |
| +0x06 | **+0x0C0** | regs[3] | timbre 1 (filter/level) | **YES (const)** |
| +0x08 | +0x100 | regs[4] | TVF/filter, weak key-follow | per-note (continuous) |
| +0x0a | **+0x140** | regs[5] | timbre 2 / detune | **YES (const)** |
| +0x0c | +0x180 | regs[6] | LFO/mod/pan | per-osc |
| +0x0e | +0x400 | regs[8] | **PITCH** (log, zone-relative, +0x100/semitone) | per-note |
| +0x10 | +0x440 | regs[9] | osc1 slot counter (bank\|rotating), **NOT a wave index** | slot only |
| +0x12 | +0x480 | regs[10] | osc2 slot counter | slot only |
| +0x14 | +0x4C0 | regs[11] | voice-type config (0x4400) | const |
| +0x16 | **+0x500** | regs[12] | timbre 3 | **YES (const)** |
| +0x18..+0x2a | +0x800..+0xA40 | regs[20..] | multi-stage ENVELOPE (Piano decays, Brass swells, Strings/Flute sustain @0xAE00 sentinel) | level/env |
| (const) | +0x000 | regs[0] | arm `0x8100`; after all osc, key-on strobe `0xF0FF`; per-tick soft-env `0xF0\|mag` | gate |

**The zone-boundary test (decisive, `-pipe-registers.md §4a`):** across a multisample split, **+0x040
is the ONLY register that changes at the zone boundary**. +0x100/+0x800…+0xA40 vary *continuously
within a zone* (E4→G4 share Piano zone 8 yet these differ) → pitch/filter/envelope key-scaling, NOT a
zone-quantized address. The extended block (+0x540…+0x640, +0x1C0) written by the streamed voices is a
**per-instrument constant** (Flute 0x0120, Sax 0x00E0, invariant over 3 octaves) → stream control, not
an address. Nothing wave-selection-shaped hides anywhere but +0x040.

---

## 3. The wave-selection core — +0x040 only, and it carries NO address (MEASURED, airtight)

`+0x040 = rec[0] = { class = bits[15:12], entry = bits[11:0] }`.

* **class (high nibble)** = per-instrument-family bank. Instrument-constant (MEASURED across 16):
  Strings/OrchPad/Synth=0, Brass/Bass=1, Mallet=2, Guitar/Sax/World/GM=3, Organ/Accordion=4,
  Flute/Drums=5, Drawbar=6, Piano=7. It is `rec[0]>>12` DATA (not the builder class; §1.5). 8 classes
  observed → **not** a raw 2-bit chip select.
* **entry (low 12 bits)** = multisample key-zone index, chosen by the played note via STAGE B's
  ptrC⊗ptrA remap; piecewise-constant, stepping at split points (Piano 001→004→007→008→00A→00D up the
  keyboard). Reuses low values across instruments (instrument-*relative*, not a global ROM index).
  **Full 12 bits** — Sax 0x13E, GM 0x112, World 0xC6/0xE1 overflow a byte; `entry>>8` = a page bit
  (Sax/GM live on page 1).
* **DRUM KITS** is the exception: entry jumps non-monotonically per key (5024/5041/5069/5072/… — a
  per-key drum map, not a pitched multisample).

**Airtight closure (`-pipe-chipmap.md §1`):** the full partial records were pulled from the
reconstructed Table-Data ROM — each is `{ +0x040 word }{ signed fine-tune words 0xEA–0xFF }`, **no
IC307 offset, no `wave_offset`, no 24-bit address**. So the ONLY wave-selection information IC303 ever
receives is the 16-bit `{class,entry}`. The physical PCM address is resolved *inside* the LSI. This is
the chip boundary in its strongest form: the address demonstrably is NOT in the register stream, so
the encoding is the chip's internal ROM decoder — not "another register we haven't found."

---

## 4. What the chip does with {class,entry} → IC307 PCM (the honest black box)

The `{class,entry} → (chip, PCM offset)` function is the TC183C230002's **internal address decoder**:
it chip-selects among IC304-307 from `class`, drives the ROM address from `entry`, and each chip's
own on-ROM index (IC307 format: 198-entry `{param_ptr, wave_offset}` at offset 0; PCM = wave_offset×16,
signed-16-LE; `-ic307-content-map.md`) yields the PCM start. **This function is not in the firmware,
not in the Table-Data ROM, not in the register stream, and not derivable from IC307 alone — and
IC304/305/306 are NO_DUMP.** So the exact numeric map is **underdetermined**.

What IS supported about its structure (MEASURED / strong-INFERRED, `-pipe-chipmap.md §3-§4`):
* `class` selects the chip/bank (8 classes vs 4 chips ⇒ a `class→chip` LUT or `{chip:2,layer:1}`
  split, SPECULATIVE which).
* `entry = {page:hi, local:lo}` selects the zone within the chip (Sax/GM exceed the 198-entry page-0
  index ⇒ a page bit; matches IC307's own physical layout = a 198-entry page-0 index + a ~3 MB
  page-1..3 tail addressed by a coarse select).
* **Consecutive IC307 indices are a coherent multisample family** (MEASURED: spectrally-adjacent
  entries 1.6× closer than random) — so mapping consecutive `entry` values to consecutive indices
  yields a coherent instrument.

IC307's per-record data carries **per-key FINE-TUNE** (signed-negative trims, records 180/181 are pure
53/130-entry detune tables) and **key-zone splits**, but **NO absolute root and NO loop points**
(MEASURED-absence): the chip loops the sustain autonomously and the root is implied by zone placement +
the firmware pitch table. In the driver, IC304-306 currently mirror IC307 (`kn5000.cpp` L1161-1163),
so any computed address reads *real* PCM — a voice landing on the "wrong" bank plays a
real-but-wrong-instrument timbre (the accepted placeholder for ~3/4 of sounds), never silence.

---

## 5. Root / pitch handling for the multi-cycle waves (MEASURED; `-pitch-velocity.md`, `-faithful-render.md`)

The registers carry only **zone-relative** pitch: +0x400 steps exactly 0x100/semitone WITHIN a
multisample zone and RESETS at each zone boundary; the per-zone sample ROOT that makes it absolute is
in the undumped chips. Dumping all 32 per-voice registers across a chromatic run confirmed **no
absolute-note register exists**. Therefore absolute pitch CANNOT be recovered from registers alone.

Faithful resolution (shipped, "use the real mechanism"): recover the TRUE played note from the real
input event (keybed scanner / USB-MIDI, both via `push_keybed_event`; note = raw+36), correlate it to
the voice at key-on (`assign_chord_notes` pairs the set of keying voices with the set of input notes
by pitch order, so chords pair correctly), then drive `freq = 440·2^((note-69)/12)`. Because playback
loops/resamples the recording so its **detected fundamental period** recurs at `freq`, pitch is
decoupled from the recording's (un-stored) native root — real PCM timbre AND exact equal-tempered
pitch simultaneously. Verified live: C4=262, C5=524 (exact octave), C-E-G = 262/330/392 all present.
**Residual:** demo/rhythm (non-keyboard) voices have no correlated input → fall back to +0x400 as a
zone-relative log-pitch (correct within a zone, may jump at zone boundaries). This is the honest limit
of register-only pitch for sequenced voices.

---

## 6. Playback spec — full multi-cycle + autonomous sustain loop (MEASURED; shipped)

Per selected IC307 waveform (all real PCM):
1. **Detect the fundamental period** P by biased normalized autocorrelation past the first negative
   zero-crossing (`detect_period`; skips the lag-0 shoulder that mis-detects a sine). ROM is periodic
   (autocorr r≈0.99). No clean P and too long ⇒ fall back to IC307 index 0 (real sine).
2. **Derive a sustain loop** (`compute_loop`): IC307 stores no loop points, so pick a region in the
   recording BODY (≥ N/3 in, ending ~1 period before the tail) whose length is an integer number of
   periods (seam pitch-continuous), slid within ±½ period to minimize the seam discontinuity.
3. **Render**: play the whole recording once from sample 0 (real attack + timbral evolution), then
   loop `[loop_start, loop_end)` while held/ringing; 16.16 fixed-point, linear interp wrapping the tail
   sample to loop_start. **Pitch** = `step = 65536·freq·P/48000` (fundamental recurs at `freq`).
   **Amplitude** = the firmware's per-tick soft-envelope magnitude (regs[0] low 9 bits, `0xF0|mag`
   rewritten every audio tick) × a lifecycle release fade × the log-domain velocity gain (regs[20] hi
   byte = attenuation, louder=lower value ⇒ `gain = 2^((REF-loglevel)/K)`).

This is faithful in mechanism (real PCM, real attack, chip-autonomous-style loop, firmware envelope);
the single-bank IC307 limit (§4) and the derived (not-stored) loop are the labelled approximations.

---

## 7. Instruments → IC307, honestly (the crux, with the current-code defects)

The MEASURED per-instrument `{class, entry-set}` (from the ptrB partial arrays, `-pipe-chipmap.md §2`;
entry-set = the multisample zones):

| instr | cls | entry set (full 12-bit) |
|---|---|---|
| PIANO | 7 | 0x00..0x0F (16) | GUITAR | 3 | 0x00-03, 0x40,0x41,0x48 |
| BRASS | 1 | 0x06..0x0C | STRINGS | 0 | 0x73,75,77,79,7B,7D,7F,81,91 |
| SYNTH | 0 | 0x09, 0x19..0x1F, 0x28-2A | ORGAN | 4 | 0x01..0x0A, 0x13 |
| WORLD | 3 | 0xC5-C8, 0xE1..0xE8 | SAX | 3 | 0x13E..0x144 | GM | 3 | 0x112..0x116 |

`class` alone does NOT identify a voice (class 3 = Guitar/Sax/World/GM; class 0 =
Strings/OrchPad/Synth), and — MEASURED — `{class,entry}` alone does not either in exactly one case:
**STRINGS and ORCHESTRAL PAD share class 0 AND overlapping entries** (both step through 0x73..0x7F;
at C2 both are literally `0x0073`). They are distinguished only by the **timbre triple / filter**
(Strings +0C0/140/500 = 7F/7F/7F; OrchPad = 7F/66/00) and by oscillator layering (OrchPad is +3 osc).
This is the faithful reading: two string-family voices legitimately **share the PCM wave** and differ
in filter+envelope+layers — the timbre triple's real role is a FILTER, not wave selection.

**The current shipped `select_waveform_index` (cpp L648) has three MEASURED defects** (verified by
running the 16 instruments' live +0x040 streams through it — `scratchpad/verify_sel.py`):
1. `zone = regs[1] & 0xFF` drops entry bits 8-11 → Sax 0x13E→0x3E, GM 0x112→0x12, World 0xC6/0xE1
   lose the page bit that distinguishes those zones.
2. `base = 1+((bank*41+timbre)%160)` is an arbitrary hash that lands on harsh/inharmonic IC307 waves
   (Piano→idx44 with H4/H8 ≫ fundamental, Brass→25, GM→77) — this is the harshness Felipe hears.
3. `idx = base + (zone%24)` applies `%24` to the low byte, so any instrument whose entry exceeds 0x18
   **wraps** and the multisample stepping goes NON-MONOTONIC: STRINGS idx {141→119} at E4, ORCHPAD
   {99→79} at C6 — the timbre jumps mid-keyboard. Broken for most instruments.

**The best-supported placeholder structure** (per-class band + monotone entry) makes an instrument's
consecutive zones map to *consecutive* IC307 indices (coherent multisample) and gives each class its
own band (cross-class distinct). NOTE: `-pipe-chipmap.md §6.3`'s literal `1+((cls*23+entry)%184)` is
the right *structure* but its exact constants still wrap at the high end (verified: ACCREG 181→3,
Drums scatter) — so the **numbers remain a labelled placeholder, tunable by Felipe's ear**, not a
decode. §9 states a wrap-free formulation.

---

## 8. Contradiction ledger — every cross-note conflict, adjudicated against the captures

1. **"24-bit sample addresses in ptr[2..5] select the instrument"** (`kn5000-real-sample-select.md
   §1`) — **FALSIFIED.** Those START/LOOP values are 0x02xxxx–0x03xxxx = sub-CPU DRAM pointers (inside
   the 1 MB sub DRAM), feeding firmware envelope/LFO/fine-tune; the full note-on capture shows **no
   24-bit value is ever latched to IC303**, and the wave is carried by +0x040=rec[0] via the SEPARATE
   ptr0→SET→ptrB chain (§1.5, live 7/7). `real-sample-select.md`'s **render fix (§3, multi-cycle +
   sustain loop) is sound and shipped**; only its §1 selection theory is retired. (The task's exact
   "24-bit sample address" trap.)
2. **Builder→instrument mapping** (`kn5000-voice-pipeline.md §3.2`: Piano=022A3F/class7,
   Guitar=022A83, Brass=022AA4, Organ=022AC5) — **WRONG.** Live: Piano=022AC5/stride6, Guitar/Organ/
   Mallet=022AE7/stride4 (`-pipe-partialset.md §5`, disasm L14341/L14353 re-verified). The six builders
   are record-STRIDE selectors; the class they OR (into desc+0x01) is the *pitch* class, ≠ the +0x040
   nibble. Adjudicated: +0x040 nibble = `rec[0]` DATA (Piano's is 7 though its builder ORs 4000).
3. **"+0x440 = wave number 0 for every instrument"** (`kn5000-wave-number.md §0`) — **PARTIALLY
   CORRECTED.** True only for the 11 ordinary voices; Flute/Sax/World/Organ/GM write NONZERO +0x440
   (`-live-captures.md` COR#1). But (COR#2, decisive: same note C4 ×5 → +0x440 increments 0x40→0x44
   while +0x040/+0x400 hold) it is a **per-note-on rotating slot counter (bank|slot)**, never a wave
   index. Both notes agree it must NOT be selected on. `-resolver.md` supplies the mechanism: the
   resolver `LABEL_02177E`'s tables are 0xFF-empty at runtime = a voice/DMA-slot allocator.
4. **entry width** — earlier notes call it "the low byte"; **widen to 12 bits** (Sax 0x13E, GM 0x112).
   Adjudicated in favour of `-pipe-partialset.md`/`-chipmap.md` (MEASURED overflow).
5. **`select_waveform_index` current behaviour** — notes describe three historical versions (12-timbre
   synth palette → high-byte-fingerprint hash → the current (bank,zone) hash). **The shipped code is
   the (bank,zone) hash with the three §7 defects** (read this pass from `kn5000_tonegen.cpp`, the
   authority; the palette and the pure-fingerprint-hash are superseded — `faithful-render.md`/
   `wave-number.md §4` describe retired versions).
6. **IC307 "no tuning"** (`kn5000-wave-number.md §3`) vs `-ic307-content-map.md` — adjudicated:
   **no root, no loop, but per-key FINE-TUNE YES** (records 180/181 pure detune tables). MEASURED.

---

## 9. FINAL specification the HLE must implement (register-inputs only)

### 9.1 Selection rule (chip-boundary-safe; use the extraction verbatim)
```c
uint16_t w = regs[1];                       // +0x040 — the sole wave-selection register
int cls   = (w >> 12) & 0x0F;               // instrument wave-family / bank
int entry =  w        & 0x0FFF;             // multisample key-zone — FULL 12 bits
if (w == 0 && timbre_triple_all_zero) idx = 0;   // degenerate/boot → real IC307 sine
// +0x440/+0x480 never participate.

// Physical model — EXACT once IC304-306 are dumped (drop-in):
//   chip  = class_to_chip(cls);                       // LSI chip/bank select (unknown LUT)
//   page  = entry >> 8;  local = entry & 0xFF;         // page + within-page index
//   pcm   = chip_base(chip) + resolve_onROM_index(chip, page, local);

// Interim placeholder over the single real bank (IC307), LABELLED, wrap-free, ear-tunable:
//   give each class a contiguous IC307 band; map entry MONOTONICALLY inside it
//   (consecutive entry -> consecutive index = coherent multisample), no modulo wrap:
//       idx = clamp( band_base[cls] + (entry - entry_min[cls]), 1, 189 );
//   band_base[]/entry_min[] sized per class from §7's entry sets; exact indices are Felipe's ear.
//   For the ONE {cls,entry} collision (Strings vs OrchPad, both cls0 ~0x73-0x7F): faithfully they
//   SHARE the wave — either accept it (correct once a FILTER models the timbre triple) OR apply a
//   small per-class band shift keyed on the timbre-triple hi-bytes ONLY (labelled compensation for
//   the absent filter model), never letting it break the monotone-entry stepping.
```
Corrections vs shipped: (1) full 12-bit `entry`, not `&0xFF`; (2) monotone-entry within a per-class
band, not an arbitrary `bank*41+timbre` hash landing on harsh waves; (3) no `%24` wrap; (4) keep
+0x440 out. Selection is DECOUPLED from pitch and playback.

### 9.2 Playback spec
Full multi-cycle play-through from sample 0 → autonomous derived sustain loop (integer periods,
seam-minimized), 16.16 linear-interp. Pitch = `65536·freq·P/48000` with `freq` from the recovered
played note (equal temperament; chords paired by `assign_chord_notes`), `P` = detected period;
no-input voices fall back to +0x400 zone-relative pitch. Amplitude = firmware per-tick soft-envelope ×
log-domain velocity gain × lifecycle release. IC307 index 0 (real sine) is the period-unknown fallback.

---

## 10. Honest residual gaps
1. **The `{class,entry}→physical-PCM` numbers are a black box** (§4) — needs IC304/305/306 dumped, OR
   one hardware probe of the LSI's ROM-address + chip-select lines while playing a known instrument+
   note (whose `{class,entry}` is in §7). Until then ~3/4 of instruments play real-but-wrong-bank PCM.
2. **Absolute pitch for sequenced (non-keyboard) voices** cannot be register-derived (no root register);
   only the keyboard/MIDI path is exact (§5).
3. **The timbre triple is not yet a filter** — folding it into wave selection (as any distinctness
   placeholder does) is a stand-in; the faithful architecture applies it as a TVF and lets same-wave
   instruments (Strings/OrchPad) differ by filter, not wave.
4. Stage A's boot-time base tables, the voice-change opcode + tonerec-pointer writer (§1.1/§1.4), the
   extended-block DMA semantics (+0x540…+0x640), the `class→chip` LUT, and the exact `entry` page/index
   bit-split are INFERRED, not pinned.
5. DRUM KITS is a per-key drum map (non-monotone entry), not a pitched multisample — its placeholder
   scatter is expected, but its per-key→wave map is not decoded.

## 11. Reproduction
* Disasm anchors: `grep -n 'LABEL_022A3F\|LABEL_032682\|ToneGen_WriteVoiceParams' <v142.asm>`;
  read L14295-14361 / L34747 / L29565.
* Table-Data ROM twin of any sub pointer `S`: region offset `S-0x20000` (== main `S+0x7E0000`);
  `region[4k,4k+1]=even[2k,2k+1]`, `region[4k+2,4k+3]=odd[2k,2k+1]`.
* Live capture dataset: `notes/kn5000-live-captures.md` (§4 per-note, §5 zone stepping).
* Selection arithmetic check (current vs proposed, no MAME): `scratchpad/verify_sel.py`.
* Live re-validation harness (isolated nvram copy, never touch `kn7000-emulator/nvram`):
  `-nvram_directory <copy> -autoboot_script decode_walk.lua -seconds_to_run 20`, press notes after
  t≈9.5 s (pre-t9 note-ons program +0x040=0), ≤56 note-ons/run (64-voice pool, no free within a run).
