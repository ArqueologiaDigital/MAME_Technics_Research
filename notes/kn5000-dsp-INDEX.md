# KN5000 effects DSP — index and backlog

Entry point for the NEC uPD6383GF (IC311) work. Read this first; it maps the other notes and lists
what is still open. Companion to `kn5000-cpserial-INDEX.md`, which indexes the control-panel work.

## State in one paragraph

IC311 is an **NEC uPD6383GF-3BA** — long mis-recorded as "DS3613GF-3BA, custom ASIC, no public
documentation", which was a transcription error. It is documented as IC302 in the Pioneer
CDJ-500/CDJ-500G service manual (`kn5000_project/pioneer_cdj-500_cdj-500g_rrv1087.pdf`, pages
1-15..1-17). The MAME device captures the host byte stream (host interface only — **the DSP core is
not emulated, there is no audio and no execution**). All 100 effect algorithms are extractable
statically from the Sub CPU ROM. The word format, coefficient format, sample rate, memory map and
several instruction roles are established. **The instruction set is not decoded.**

## The notes, and when to read them

| note | contains |
|---|---|
| `kn5000-dsp-encoding.md` | the field map `hi12[35:24].class4[23:20].addr8[19:12].lo12[11:0]`, the terminator landmark, the refuted opcode-field hypothesis |
| `kn5000-dsp-coefficients.md` | Q0.23 decode, delay taps, effect name table, the refuted KN7000 correlation |
| `kn5000-dsp-reverb.md` | the reverb motif and topology (two ladders of five all-pass diffusers) |
| `kn5000-dsp-header.md` | I-RAM memory map, the unit index, host poke region |
| `kn5000-dsp-parameters.md` | proof-by-construction of the pointer-load, 44.1 kHz, parameter names, dB curve |
| `kn5000-dsp-class2.md` | class-2 round one **plus a correction and its retraction — read all three** |
| `kn5000-dsp-class2-round2.md` | ★ most recent and most reliable: all-pass reframe, P-consumer test, class4-as-space-selector |
| `kn5000-dsp-biquad.md` | (in progress) operand-level semantics from the PARAMETRIC EQ |
| `kn5000-dsp-biquad-map.md` | coefficient→multiply mapping, the make-up gain, class 8 |
| `kn5000-dsp-cursor-general.md` | the generalised coefficient cursor; the reverb decoded |
| `kn5000-dsp-effect-map.md` | ★ the per-effect structural map of **all 38 images**, the table-lookup idiom, MULTI TAP DELAY resolved |
| `kn5000-dsp-semantics.md` | ★★★ the biquad section **SOLVED by exhaustive constraint search** (19.7 M assignments, 144 survivors = one dataflow): Direct Form I, four state cells, **two of the four writes folded into multiply instructions**; `[7]` determined uniquely (make-up gain × accumulator, writes `S2`); exact impulse-response agreement on 9 real ROM banks; the reverb all-pass cross-check and its numbers |
| `kn5000-dsp-avsdrv.md` | ★ **`AVSDRV.SYS` v5.10 ACQUIRED** from NEC's own server (inside NEC's free MS-DOS 6.2 update module `UPDOS62.EXE`, via Wayback) and **VERIFIED** as the real uPD6380 driver (`MOV DX,0A462h/0A464h`, `AVSDRV$$`, three `INT 0D9h` installs) — but its payload is LZ-packed behind an `AVSLOAD$` loader, so the upload loop / 19 microprograms / word size are still unread. Next step and reproduce recipe inside |
| `kn5000-dsp-core-draft.md` | ★ the MAME **device + disassembler** (`src/devices/cpu/upd6383/`), the six decoded forms and their evidence, the live-I-RAM-vs-static-extraction acceptance test, and **the undecoded-word worklist ranked by frequency** (655 distinct words, 185 families, 9 % of the corpus decoded) |
| `kn5000-dsp-necfamily.md` | ★ the uPD7725-descendant hypothesis, **REJECTED** (6 of 8 borrowed structures fail); the bodies are proved HAND-UNROLLED, which is why no branch exists to find; new `lo12` sub-boundary `[11:8]‖[7:2]` |

Tools: `tools/kn5000_dsp_extract.py` (all 100 programs from ROM), `_wordfields`, `_encoding`,
`_reverb`, `_coeffs`, `_header`, `_params`, `_class2`, `_class2b`, `_biquad`,
`_biquadcoeffs`, `_biquadmap`, `_cursorgen`, `_effectmap`, `_semantics`.
Archived cold-boot capture: `notes/data/kn5000_dsp1_upload_coldboot.txt`.

## Established

* 5 bytes = one **36-bit instruction**, right-aligned big-endian (bits 36–39 always zero).
* 3 bytes = one **24-bit coefficient**, signed **Q0.23** (`0x517CC1` = 2/π, 53 occurrences).
* **44,100 Hz**, derived from the firmware's own `ms × 0xAC44 / 0x3E8`.
* I-RAM map: 0–59 header, 60–82 stub, 84–193 unit 0, 200–332 unit 1, 352–382 host poke.
  **Both effect units are resident at once.**
* Terminator `class4==1 && addr8 ∈ {0x0E,0x0F}`; that `addr8` is a **unit index** (91/91).
* Corpus: **91 valid programs**, 38 distinct images (79/88/89/90/91 malformed).
* Roles: pointer-load `801.0.NN.821` (**proven by construction**), NOP `000.2.00.000` (**proven**),
  bit 23 = multiplier, `880.1.60/20.*` = external-DRAM bracket (MCC +0.944), `104.2.00.000` =
  all-pass marker (MCC +0.881), `hi12=0x082` = LFO read, `hi12=0xC40` = envelope detector,
  `lo12 ∈ {647,687}` = biquad non-multiply steps, P-consumer/non-consumer split.
* PARAMETRIC EQ = 5 bands × 2 channels (confirmed three ways; an earlier "4 bands" was retracted).
* **Coefficient cursor**: implicit, +1 per class-A word, reset by `801.0.00.021`; biquad block
  `+0=b1 +1=b0 +2=b2 +3=−a1/a0 +4=−a2/a0 +5=make-up gain`; unit 1's bank base is `+0x80`.
* **All 38 images are mapped** (`kn5000-dsp-effect-map.md`), 25 high / 13 medium confidence.
* **The 3-word TABLE-LOOKUP idiom** `xxx.0.00.C63 | 000.6.TT.4CD/407 | 012.4.01.1CE` accounts for
  every class-4 and class-6 word (53/53/53) and occurs in exactly the 25 images with an LFO or a
  distortion stage (MCC +1.000); the class-6 `addr8` is the table selector.
* **`op 0x76` writes a fixed 3-word damping/tone filter** (14/14 entries over 5 images).
* The reverb is the **only** unit-1 program in the corpus.

## BACKLOG — open investigations

### DSP, near-term
0. **★ THE BIQUAD IS DECODED** (`kn5000-dsp-semantics.md`). Direct Form I; the cell walk,
   the two "missing" state writes, the make-up gain's operand and the class-8 word's
   *position* are all resolved. What is left there: which of two words performs each of
   three writes (2 each, broken only by an encoding argument), what class 8 computes, and
   the reverb motif's instruction ordering. The cheapest next test is `AUTO WAH`'s
   `204.2.FE.687 / 804.8.16.1DA / 000.2.FF.647` triple, already in the corpus.
1. **C-RAM vs D-RAM.** Two 256×24 spaces plus a bank register; how they are distinguished is
   unknown. Partly folded into the biquad run.
2. **The `COND` field and control flow.** The pin table proves a `COND` field exists and names a
   `BRAKST` instruction, but an exhaustive scan of every contiguous bitfield found **no encoded
   branch** and no field carrying the body entry addresses 84/200. Current model is fall-through
   plus host-driven entry. Likely needs the header's control words understood first.
   **UPDATE (necfamily.md §6): a second, wider scan — every field of width 7–12 at every offset,
   shifts 0/1/2, tested against each program's OWN extent — is also negative, and there is now a
   positive reason: the effect bodies are HAND-UNROLLED (algo16 repeats 32 words at period 8
   varying only `addr8`; algo39 36 words at period 9). There is no loop in a body to branch back
   to. Statistical scanning is exhausted; this needs a PC trace or the datasheet.**
3. **What `104.2.00.000` actually does.** Confirmed as an all-pass marker, but its *position*
   differs between reverb and phaser, so the step it performs is unidentified.
4. **The remaining vocabulary** — after the effect-map pass, **37 `hi12` and 36 `lo12` values**
   still carry no meaning, and image-granularity co-occurrence is mined out. What is left needs
   *position*-level evidence or the datasheet (`kn5000-dsp-effect-map.md` §6.4).
5. ~~**The `NO OPERATION` program** is the sole false positive of two independent controls.~~
   **CLOSED**: it genuinely contains an envelope-detector block (2/π scale, `C40` pair, one-pole
   smoothers) and real DRAM accesses — the controls were right (effect-map §4).
5b. **The partial-cursor-rewind encoding.** `MULTI TAP DELAY` needs a −3 rewind between words 49
   and 52; only two words sit there. The best-posed open question in the file (effect-map §5.1).
5c. **The compressor's four coefficient consumers**, now bounded to three word families
   (effect-map §5.2), and the `804.8.16.1DA` / `80A.8.16.000` section families.

### DSP, bigger swings
6. **Hunt for the actual µPD6383 datasheet or databook.** The CDJ manual was luck; a datasheet
   would hand over the whole ISA — `COND`, `BRAKST`, class encodings — and retire most of the
   inference above. Cheap to attempt, disproportionate payoff. **Recommended before more grinding.**
7. **DSP2 (MN19413, IC310) is entirely untouched.** Bit-banged serial on PF.0/PF.2/PE.6, opcode 0xE
   with command 0x30; its bodies autocorrelate at lag 4, suggesting a **32-bit** word rather than
   36. Effect units 2–4 route to it. A whole second chip awaits.
8. **Emulating the DSP core** in MAME, once enough ISA is known — the payoff being that KN5000
   effects would actually be audible. Circular until the ISA exists, but it is the destination.
   **STARTED (2026-07-22, `kn5000-dsp-core-draft.md`): the device and disassembler now exist
   at `src/devices/cpu/upd6383/`, the KN5000 instantiates the core DISABLED and the host
   uploads land in a real I-RAM (verified byte-identical against the static extraction), and
   the undecoded vocabulary is now a frequency-ranked worklist. Still no ISA and no audio.**

### Elsewhere in the project (not DSP)
9. **Power-down NMI** — the `<Db>` that returns on every warm boot, and the same root cause as the
   scheduled splash-animation quest. MAME's exit path calls `eat_all_cycles()` before NVRAM save, so
   the firmware's power-off code never runs. Fix once, get both. **Highest user-visible value.**
10. **CP-serial packet misframe** — 3–9 malformed frames per run, present in mainline MAME too;
    the real remaining panel bug. See `kn5000-cpserial-INDEX.md`.
11. **Sound Name Error, long-session** (non-PIANO lists) — filed brief, pre-existing.
12. **Floppy self-test** — blocked on an unmodelled power-on keybed read.
13. **KN6500 sound** — voice engine never starts; `MACHINE_NO_SOUND`.
14. **Phase C hardware dumps** — needs Felipe's hardware.
15. **Disassembly coverage / CONVERT growth** — the standing idle-time directive.
