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
| `kn5000-dsp-paramnames.md` | ★ the **name→slot binding LOCATED** (supersedes §4/§10 "NOT FOUND"): it is **not a table** — a per-effect list of name indices in the UI object-property DB, drawn by `DspItem0CngFunc`/`F3561F` (`name = 0xE324D5 + 17*(RAM[0x29AC+slot]-1)`), loaded by `LABEL_F457CF` via property reader `FDC6E7`. Explains the fixed-stride scan's blindness. Constraint-propagation reported as a MISS (count-check needs the object DB) |
| `kn5000-dsp-class2.md` | class-2 round one **plus a correction and its retraction — read all three** |
| `kn5000-dsp-class2-round2.md` | ★ most recent and most reliable: all-pass reframe, P-consumer test, class4-as-space-selector |
| `kn5000-dsp-biquad.md` | (in progress) operand-level semantics from the PARAMETRIC EQ |
| `kn5000-dsp-biquad-map.md` | coefficient→multiply mapping, the make-up gain, class 8 |
| `kn5000-dsp-cursor-general.md` | the generalised coefficient cursor; the reverb decoded |
| `kn5000-dsp-effect-map.md` | ★ the per-effect structural map of **all 38 images**, the table-lookup idiom, MULTI TAP DELAY resolved |
| `kn5000-dsp-semantics.md` | ★★★ the biquad section **SOLVED by exhaustive constraint search** (19.7 M assignments, 144 survivors = one dataflow): Direct Form I, four state cells, **two of the four writes folded into multiply instructions**; `[7]` determined uniquely (make-up gain × accumulator, writes `S2`); exact impulse-response agreement on 9 real ROM banks; the reverb all-pass cross-check and its numbers |
| `kn5000-dsp-avsdrv.md` | ★ **`AVSDRV.SYS` v5.10 ACQUIRED** from NEC's own server (inside NEC's free MS-DOS 6.2 update module `UPDOS62.EXE`, via Wayback) and **VERIFIED** as the real uPD6380 driver (`MOV DX,0A462h/0A464h`, `AVSDRV$$`, three `INT 0D9h` installs) — but its payload is LZ-packed behind an `AVSLOAD$` loader, so the upload loop / 19 microprograms / word size are still unread. Next step and reproduce recipe inside |
| `kn5000-dsp-core-draft.md` | ★ the MAME **device + disassembler** (`src/devices/cpu/upd6383/`), the six decoded forms and their evidence, the live-I-RAM-vs-static-extraction acceptance test, and **the undecoded-word worklist ranked by frequency** (655 distinct words, 185 families, 9 % of the corpus decoded) |
| `kn5000-dsp-hi12.md` | ★★★ `hi12` decoded as a **horizontal microword** (HD-1 closure z = +7.9): bit 11 = format escape, bit 10 = end (see below), bit 4 = write acc to `mem[ptr]`; bits [9:8] and [3:1] proven fields with unknown meaning; four negative searches for the pointer origin |
| `kn5000-dsp-pointer.md` | ★★★ **THE POINTER ORIGIN IS FOUND** by running the core: the loads are in the **common header**, which every static search excluded by construction. Unit 0 `0x70`, unit 1 `0x50`, via the `0x821` register (`0x825` falsified by aliasing, `0x827` the runner-up). Plus a per-frame **dispatch model** that explains why no branch word carrying 84/200 exists, and the **falsification of "bit 10 = END OF PROGRAM"** as a bit meaning (14 occurrences in the 60-word header, 12 of them interior) |
| `kn5000-dsp-necfamily.md` | ★ the uPD7725-descendant hypothesis, **REJECTED** (6 of 8 borrowed structures fail); the bodies are proved HAND-UNROLLED, which is why no branch exists to find; new `lo12` sub-boundary `[11:8]‖[7:2]` |
| `kn5000-dsp-paramsemantics.md` | ★ the **parameter → cell → reader chain**: propagates the named parameter list into the reading instruction. Positive controls PASS (LFO read `082` = the UI LFO-control reader, 0 false-neg; biquad 5/5; VOLUME/REV SEND tail `0x90`/`0x06`). NEW operand-meaning: the compressor's `C40` envelope-detector coefficient = ATTACK/RELEASE time constant. NEGATIVE: **no comparator opcode exists** — no `hi12` is unique to the threshold effects; the branchless bodies compute gain arithmetically. Coverage unchanged 18.3 %. Tool `tools/kn5000_dsp_paramsemantics.py` |
| `kn5000-dsp-origin.md` | ★★ CONTINUOUS whole-frame execution (`tools/kn5000_dsp_origin.py`): the EQ origin is **0x19** (unique, geometric) and — with the COMPLETE reverb host map (a low block `{19..1E}` the trace note lacked) — the **reverb's low state pointer SHARES it across the unit boundary**, superseding trace-Q1's "no common constant". But the origin's SOURCE is **still not a decoded word** (model A→0x70, model B→0x06, no immediate is 0x19) and CANNOT be, because the header is effect-independent while origins are per-effect → both hypotheses (a)/(b) FALSIFIED; the survivor is a **per-effect HOST descriptor-poke**. Concrete next step: capture the uC-IF stream with PARAMETRIC EQ selected in MAME (no hardware). New lead: epilogue `0x822<-#$86` = reverb high-block base ⇒ the escape-loads are the state pointers |
| `kn5000-dsp-origin-capture.md` | ★★ CAPTURED the uC-IF host stream with PARAMETRIC EQ selected in MAME (`tools/kn5000_dsp_origincap.{lua,py}`) to test `-origin.md` §4's prediction. **PREDICTION FALSIFIED**: there is NO `0x19` pointer poke (nor any per-effect origin poke) in the EQ stream. Positive control PASSES (captured EQ body == static algo39, byte-identical; snapshot + RAM verified). What the stream DOES contain: **every one of 16 swept effects frames its coefficient upload identically** — opens `26.825`, sets coefficient base `00.821` (`0x00`, the SAME for all), streams per-effect sections all anchored at `0x00`, closes `90.821`; only the section count/spacing is per-effect (EQ = `00,06,0C,12,18` = 5 bands×6, plus `1E`=30 extent). The `0x19`/reverb-`0x07` origins were a single-pointer modelling artifact; the real machine uses several pointer registers + the C-RAM/D-RAM split, with **state** on the header's effect-independent `0x6C`/`0x70` and **coefficients** on host base `0x00`. Disassembler NOT upgraded (origin falsified, not proven). Coverage unchanged 18.3% |
| `kn5000-dsp-spaces.md` | ★★★ **the C-RAM/D-RAM SPACE SELECTOR, DECIDED** (`tools/kn5000_dsp_spaces.py`): there is **NO encoded selector field** — the space is **pointer-identity**. C-RAM (coeffs) is reached ONLY via the implicit cursor (base 0x00 MEASURED, +1 per class-A word), D-RAM (state) ONLY via the signed-`addr8` data pointer, external delay RAM ONLY via the `880` bracket; **no word ever names a single C-RAM cell** (labelled biquad: 0 single-cell C-RAM accessors), so no `hi12` bit can select and the prediction that one would **MISSES**. Controls hold present-AND-absence (coeffs 197/197 cursor-reachable; state only via `+2`/`000.1`; 18/38 images have a C-address == a D-address, so the number never names the space). **JOB 1 SHIPPED: the disassembler now prints absolute `; C-RAM[0xNN]` on all 822 class-A words** (base 0x00, class-A advance not bit-23 → make-up gain stays at `NN+5`); `-validate` kn5000+kn7000 clean, coverage unchanged 18.3 % |
| `kn5000-dsp-trace.md` | ★ the pointer-arithmetic TRACE (`tools/kn5000_dsp_trace.py`) settling the three addressing residuals: **Q1 origin STILL NOT PINNED** (EQ needs 0x19, reverb ~0xA6, neither a header register, no unified offset → core left un-edited, absolute addressing NOT implemented); **Q2 wrap = 256** INFERRED with a MEASURED floor > 0xCF (mod-128 ruled out by host pokes); **Q3 modes 3/4/5 freeze `addr8` at a constant, only mode 6's `addr8` is an operand (the table selector)** |

Tools: `tools/kn5000_dsp_extract.py` (all 100 programs from ROM), `_wordfields`, `_encoding`,
`_reverb`, `_coeffs`, `_header`, `_params`, `_class2`, `_class2b`, `_biquad`,
`_biquadcoeffs`, `_biquadmap`, `_cursorgen`, `_effectmap`, `_semantics`, `_hi12`, `_pointer`,
`_spaces` (C-RAM/D-RAM selector + absolute C-RAM addresses).
Archived cold-boot capture: `notes/data/kn5000_dsp1_upload_coldboot.txt`.

## Established

* 5 bytes = one **36-bit instruction**, right-aligned big-endian (bits 36–39 always zero).
* 3 bytes = one **24-bit coefficient**, signed **Q0.23** (`0x517CC1` = 2/π, 53 occurrences).
* **44,100 Hz**, derived from the firmware's own `ms × 0xAC44 / 0x3E8`.
* I-RAM map: 0–59 header, 60–82 stub, 84–193 unit 0, 200–332 unit 1, 352–382 host poke.
  **Both effect units are resident at once.**
* Terminator `class4==1 && addr8 ∈ {0x0E,0x0F}`; that `addr8` is a **unit index** (91/91). The
  halt itself is `hi12` bit 10 — but only **within an effect body**: the common header carries
  that bit 14 times in 60 words, so "bit 10 = end of PROGRAM" is falsified as a bit meaning and
  "end of segment / return" is what survives (`-pointer.md` §5).
* Corpus: **91 valid programs**, 38 distinct images (79/88/89/90/91 malformed).
* **Data-pointer ORIGIN: unit 0 = `0x70`, unit 1 = `0x50`** (`kn5000-dsp-pointer.md`), loaded by
  the common header at I-RAM 42/50 immediately before each unit's terminator. The pointer does
  **not** return over a program pass — it is **reloaded every frame**.
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
1. ~~**C-RAM vs D-RAM.**~~ **RESOLVED** (`kn5000-dsp-spaces.md`, `tools/kn5000_dsp_spaces.py`).
   The two 256×24 spaces are **NOT distinguished by an encoded field** — the space is
   **pointer-identity**: C-RAM via the implicit coefficient cursor, D-RAM (state) via the
   signed-`addr8` data pointer, external delay RAM via the `880` bracket. No word single-cell-
   addresses C-RAM, so there is nothing for a selector bit to pick; the `hi12`-bit prediction
   MISSES. Controls hold across families (present AND absence). **JOB 1 also shipped**: the
   disassembler now prints absolute `; C-RAM[0xNN]` coefficient addresses (base 0x00 MEASURED)
   on every class-A word. STILL OPEN: the D-RAM absolute BASE (the origin `0x19` residual,
   `-addressing.md` §5), so D-RAM absolutes are still withheld.
1b. ~~**★ The pointer-DELTA rule**~~ **RESOLVED** (`kn5000-dsp-addressing.md`,
   `tools/kn5000_dsp_addressing.py`). The rule is **signed `addr8` post-increment on an 8-bit
   (wrapping) pointer, gated by `class4 & 7 == 2` (classes 2 and A only)**; `class4 = bit23-mult ‖
   3-bit mode`, carrying the poke-family "class4 = address-space selector" (`-class2-round2.md` §4)
   into the bodies. This is the naive rule plus two data-forced fixes: **8-bit WRAP** (dissolves the
   reverb's "leaves any 256-cell window" — it was measured without wrap) and **class 8 is frozen**
   (biquad forces it). Reproduces all three falsifiers, and the biquad's +4/band walk lands EXACTLY
   on the host STATE block `{64,68,6C,70,74}` (5/5) — the strongest host/body coincidence yet.
   STILL OPEN: the absolute ORIGIN (the fit needs `0x19`, not the header's `0x70`/`0x6C`/`0x25`), so
   the core is left DISABLED and un-edited until the base is pinned. **UPDATE (`-origin.md`): the EQ
   origin `0x19` is now shared by the reverb's low state bank (complete host map), but continuous
   whole-frame execution proves the origin's SOURCE is NOT in the resident program — it is a
   per-effect HOST poke, because the header is effect-independent. Next: capture with the EQ active.**
   **DONE + FALSIFIED (`-origin-capture.md`): the EQ was selected in MAME and the uC-IF stream
   captured — there is NO `0x19` poke and NO per-effect origin at all. All 16 swept effects share
   the SAME coefficient framing (base `0x00` via `00.821`, `26.825`/`90.821` brackets); the `0x19`
   was a single-pointer artifact. The real target is the C-RAM/D-RAM selector (backlog item 1),
   with coefficients at host base `0x00` and state at the header's `0x6C`/`0x70`.**
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
   **Board facts (Felipe, 2026-07-22): IC310 has its own 20 MHz crystal**, against the 25 MHz
   one on IC311 — the two effect processors are independently clocked. Its delay memory is
   **IC308, an M5M418128AJ-6**: 1 Mbit, **8-bit data bus, 9 address pins** (128K × 8, row 9 +
   column 8 = 17 bits) — self-consistent, and a quarter of what IC311 gets. **The 8-bit width
   is unexplained**: 8-bit samples are too coarse for an audio delay, so DSP2 either does two
   accesses per sample or companded storage. Settle that before modelling it.
8. **Emulating the DSP core** in MAME, once enough ISA is known — the payoff being that KN5000
   effects would actually be audible. Circular until the ISA exists, but it is the destination.
   **STARTED (2026-07-22, `kn5000-dsp-core-draft.md`): the device and disassembler now exist
   at `src/devices/cpu/upd6383/`, the KN5000 instantiates the core DISABLED and the host
   uploads land in a real I-RAM (verified byte-identical against the static extraction), and
   the undecoded vocabulary is now a frequency-ranked worklist. Still no ISA and no audio.**

### DSP, parameter-name binding
16. ~~**name→slot binding**~~ **RESOLVED** (`kn5000-dsp-paramlist.md`). The per-effect name-index
    lists were dumped **live** by driving the panel in MAME (SOUND MENU → DSP EFFECT / REVERB, then
    stepping the TYPE selector) and reading `RAM[0x29AA]`/`RAM[0x29AC..]` after each redraw. **50
    distinct effects now have a fully-named, ordered, unit-tagged parameter list** (38 on the DSP
    EFFECT page type 0x0B; 12 reverbs sharing one list + 2 delays on the DIGITAL REVERB page type
    0x0A) — pixel-verified against the LCD. The mechanism from `-paramnames.md` is confirmed exactly
    (1-based index, maincpu space). Validation passed: counts match, families sane, and the DSP-target
    pins (HIGH DAMP GAIN=reverb, THRESHOLD/RATIO=compressor, 5×BAND EMPHASIS=PARAMETRIC EQ, LFO
    SPEED/WAVEFORM only on LFO effects) are proven end-to-end. Tools: `tools/kn5000_dsp_paramlist.py`,
    `tools/kn5000_cycle.lua`, `tools/kn5000_dsp_paramlist_capture.json`. EQUALIZER (0x0C) and ACOUSTIC
    ILLUSION (0x0E) use fixed layouts, not this array. Static object-DB decode no longer needed.

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
