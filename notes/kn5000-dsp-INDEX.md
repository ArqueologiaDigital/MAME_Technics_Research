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
| `kn5000-dsp-blockcoeff.md` | ★★★ **DECODES the block-upload coefficient opcodes and extends the C-RAM join to 500/822 (60.8 %)**. From the dispatch table (`OFFSETS_14745`, anchored on op0x62/63/65/68) the opcode→eval→writer chain is pinned; counting the C-RAM writer primitives (`0387E6` set-ptr + `0388B3` auto-increment continuations) gives each block's span: **op0x73 = 5-cell computed bilinear section** (14 delay/all-pass effects), **op0x77 = 1 cell/voice** (ENSEMBLE's 6 depths at C-RAM 02 04 06 09 0B 0D — control PASSES), op0x71 = 5-cell (dead), op0x75 = the reverb's D-RAM bulk upload (4/iter from ROM tables — NOT C-RAM). **+109 of the 431 unnamed** (op0x73 103, op0x77 6). Brief corrected: **op0x6B/0x6C/0x75 write D-RAM state, not C-RAM**, so name no multiply. Caught + revoked a span-5 **over-reach onto the MEASURED LFO words** (`092.A`/`094.A`, 6 claims). New operand role `202.A.**.655` = filter coeff (19/20). Biquad order 6/6 PASS. Coverage 18.3 % unchanged (roles ≠ full decodes). Disassembler NOT edited. Tool `tools/kn5000_dsp_blockcoeff.py` |
| `kn5000-dsp-namedcoeff.md` | ★★★ **NAMES every class-A multiply's coefficient** by joining the disassembler's absolute C-RAM address (`-spaces.md` JOB 1) to the host T1 coefficient map + the decoded biquad/reverb. **Biquad-order control PASSES** (b1,b0,b2,-a1,-a2,makeup at C-RAM 00..05). **391/822 multiplies (47.6 %) now carry a named coefficient** (255 PROVEN); PARAMETRIC EQ 60/60, reverb 33/33. NEW operand ROLES on two frequent undecoded families: `202.A.*.415`=mix/tap gain (97 %), `102.A.*.64B`=reverb diffuser decay (100 %). Neighbour propagation **re-confirms the biquad's two class-2 stores** (`102.2.687`/`000.2.647`) by role present-and-absence (30/29, 100 %). Caught + fixed a join hazard (op0x74 "1D 00 00 00" padding zeros falsely naming C-RAM 0x00). **No new opcode dataflow-forced; role known kept distinct from operation known; coverage unchanged 18.3 %; disassembler NOT edited** (names are effect-contextual + role-level). Tool `tools/kn5000_dsp_namedcoeff.py` |
| `kn5000-dsp-spaces.md` | ★★★ **the C-RAM/D-RAM SPACE SELECTOR, DECIDED** (`tools/kn5000_dsp_spaces.py`): there is **NO encoded selector field** — the space is **pointer-identity**. C-RAM (coeffs) is reached ONLY via the implicit cursor (base 0x00 MEASURED, +1 per class-A word), D-RAM (state) ONLY via the signed-`addr8` data pointer, external delay RAM ONLY via the `880` bracket; **no word ever names a single C-RAM cell** (labelled biquad: 0 single-cell C-RAM accessors), so no `hi12` bit can select and the prediction that one would **MISSES**. Controls hold present-AND-absence (coeffs 197/197 cursor-reachable; state only via `+2`/`000.1`; 18/38 images have a C-address == a D-address, so the number never names the space). **JOB 1 SHIPPED: the disassembler now prints absolute `; C-RAM[0xNN]` on all 822 class-A words** (base 0x00, class-A advance not bit-23 → make-up gain stays at `NN+5`); `-validate` kn5000+kn7000 clean, coverage unchanged 18.3 % |
| `dsp-critical-path-coverage.md` | ★★★ **DECODE COVERAGE ON THE CRITICAL PATH** (`tools/kn5000_dsp_critpath.py`). Re-computes coverage over what actually RUNS (header 60 + unit-0 body + epilogue 23 + unit-1 body) instead of over the body corpus: the live cold-boot frame is **286 slots, 30 decoded = 10.5 %**, the 83-word scaffolding is **3/83 = 3.6 %** and all three are the same `ldptr`, and **NOT ONE decoded word touches the audio boundary** (DI/DO, delay DRAM, stack, flags, Fs). `NO OPERATION` — the dry pass-through loaded for **42 effect slots** — has **0 of 49** words decoded; **8 of 38 images are at zero**. New hard constraint: the header runs **21 class-A words with no `rstcur`** before the unit-0 CALL, yet body coefficients are MEASURED at C-RAM base 0x00 ⇒ **an undecoded word must rebase/bank the cursor**. The scaffolding is a **vocabulary island** (71/79 words, 65/75 families occur 0× in 2974 body words; classes 9/C/D, `lo12` 445/446, `hi12` 0xC00 and the pointer siblings 820/822/825/827 are all 0/2974) — so **frequency ranking is structurally blind to the audio path**. Also: the core's frame-end test (`upd6383.cpp:554-557`) fires on I-RAM 49, which is PROVEN to be a **CALL**, so an enabled core would stop before any body ran. Ships **the BLOCKING LIST B1–B13** ranked by *does this stop audio*. Decodes nothing; coverage unchanged |
| `dsp-perframe-execution.md` | ★★★ **THE PER-FRAME EXECUTION TRACE** (`tools/kn5000_dsp_perframe.py`): the exact ordered list of words that execute in ONE 44.1 kHz sample frame, from a capture taken today (byte-identical to the archived cold boot). **256–326 slots, each word EXACTLY ONCE** (through 265, cold-boot CHORUS+reverb **286** — the `-headerdecode.md` §3 prediction CONFIRMED, corpus max **326** CONFIRMED). ★ The corpus denominator is the wrong one: the audio path is the **83 scaffolding words** (header 0..59 + epilogue 60..82), **75 families of which 65 occur in NO effect body**, only **3 decoded**. ★ Exactly ONE image loads at I-RAM 200, so the **reverb runs in every frame of every effect** (floor = 216 words / 104 families / 29 decoded). ★ CORRECTIONS: `hi12==0xC40` is the **12-bit-immediate FORMAT**, not an envelope detector (it occurs in the reverb 4× and in 3 of the 4 host-patched wet-level words) — the disassembler's rule order mislabels them; the `880.1.60/20` DRAM **"bracket" is FALSIFIED as a bracket** (16 vs 18 / 14 vs 20 / 13 vs 16 per frame, never balanced); the `lo12=0x820` immediates **cannot be loop counts** (448..1201 vs a 567-cycle frame budget). ★ NEW OPEN: the coefficient cursor must be re-based twice per frame (0x00 / 0x90) and no word on the path is known to do it; `rstcur` is in 1 of 38 programs. Roadmap ranked by what blocks AUDIO: input stage (0..11) > output stage (60..82, incl. the two patched levels) > `880.1.**` DRAM (13 % of every frame) > cursor re-base > the reverb's six hot families (54 execs/frame) — explicitly NOT the corpus worklist's top three, which are all inside bodies |
| `dsp-audiopath-wiring.md` | ★★★ **WIRING THE SOUND PATH — the board-level plan** (service manual pp.28/29/34/35 + CDJ-500 RRV1087 pp.1-15..1-17). ★ **IC311 is a SEND/RETURN INSERT on IC303, not an output-path device**: its wet output goes back into IC303, the main mix leaves on `SDO0` → IC310 → IC313 PCM69AU, so **the dry sound can never be lost by a broken IC311 model** — the safety property is hardware, not a bypass. ★ **All three DI and all three DO are wired** (`SDOA/SDOB/SDO1` → `DI1/DI2/DI3`; `DO1/DO2` → `SDIA/SDIB`, `DO3` off-block) — FALSIFIES "this board uses one stereo pair". ★ **`Fs-RST` (13) and `Fs-MASK` (14) are strapped +5D = INACTIVE**: the per-frame PC restart is the chip's **internal PC-RST**, cadenced by **LRCKI**, which **IC303** generates. ★ Delay DRAM: only `A0..A8` reach IC309, **pins 55-62 (A9-A16) carry no net**, **MD1-MD4 = 0b1111** — the open question is "8 or 9 column bits", do NOT widen the map. ★ MAME change set (option **C**, the tone generator owns the frame: one `run_frame()` per output sample), gate default Off, `+=` after an untouched dry mix. ★ OPEN: **O-1 sample rate** (firmware 44,100 vs MAME's 48,000 stream vs a scanned crystal that divides to neither), O-2 17/18 delay bits, O-3 port routing, **O-4 the IC303-side send/return levels are NOT established**, O-7 emulator mode is strapped off ⇒ **no PC trace without board modification** |
| `dsp-next-steps-roadmap.md` | ★★★ **THE PLAN: wire the sound path, then decode what runs on it** (`tools/kn5000_dsp_nextsteps.py`) — synthesis of the three notes above, scoped as Felipe asked to **the KERNEL + ONE REVERB (216 words = the floor of every frame)**. Adjudicates their contradictions against the sources. ★ **What comes out today if we enabled it: DIGITAL SILENCE, provably** — `trap()` changes no state and every path to the DO latches is undecoded ⇒ **listening is not a usable feedback signal until K1/K5/K6 land**; use trap histograms, PC-sequence and C-RAM-address assertions instead. ★ KERNEL alone = **83 words, 75 families, 3 decoded (3.6 %)**; kernel+reverb = **216 / 104 / 29 (13.4 %)**, and the two halves **share exactly ONE word** (`880.1.20.2D5`). ★ NEW MEASURED: the four host-patch words are **literal constants in Sub CPU ROM** (`0xF6CD/0xF6D8` = script A, `0xF707/0xF712` = script B) — **nothing is computed, the output stage has exactly TWO states**, written as a **mute/restore bracket around every body reload**, so the DSP-side return level is **constant and is NOT the user's depth control** (narrows O-4); per slot the pair is an **exact ×2 / ×4** in bits [24:12]. ★ NEW MEASURED: the **D-RAM pointer walk** gives the reverb a **14-cell footprint anchored exactly on `ldptr #$50`** (first whole-program positive control of the addressing model) while NO OPERATION/COMPRESSOR/EQ scatter ⇒ a ready-made **scored search for the pointer-register file**; the reverb's terminator `612.1.0F.000` is the **only** terminator with `hi12` bit 4, so it **stores the accumulator**, landing on **0xCD**. ★ Ranked attack list **K1..K7** (kernel) then **R1..R4** (reverb), each with a concrete STATIC / LIVE / HARDWARE experiment — centrepiece **R1**: solve the reverb's 8-word all-pass motif as a constraint system against the MEASURED ladder gains, the same method that solved the biquad to 0.000e+00. ★ The exact hardware recordings that would settle the rest (H1 reverb impulse response first) |
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
* ⚠ **RETRACTED — was: "Data-pointer ORIGIN: unit 0 = `0x70`, unit 1 = `0x50`, loaded by the common
  header at I-RAM 42/50 … the pointer does not return over a program pass, it is reloaded every
  frame."** **K3 FORCED that `lo12 = 0x821` addresses the COEFFICIENT space**, so it is neither the
  D-RAM operand pointer nor the cursor (`dsp/analysis/k3-pointers.md` §4); the runner-up `0x827` was
  then **falsified at 0 of 85 streams** (`isa-adjudication.md` §5.1). **NOTHING IN THE DECODED SET
  LOADS THE D-RAM POINTER.** The "does not return" problem this bullet declared solved is therefore
  **re-opened, and it is exactly the +121 frame-closure residue** measured on 1 130 880 of
  1 130 880 complete frames (`dsp-frame-advance.md` §3, `analysis/closure-pointer.md`). The origin
  is **OPEN**; the reload SITE is localised to I-RAM 50…78. See `analysis/retraction-sweep.md` P1/P13.
* Roles: pointer-load `801.0.NN.821` (**proven by construction** — as a pointer-load *form*; its
  TARGET is C-RAM, not the data pointer, see above), NOP `000.2.00.000` (**proven**),
  `104.2.00.000` = all-pass marker (MCC +0.881), `hi12=0x082` = LFO read,
  `lo12 ∈ {647,687}` = biquad non-multiply steps, P-consumer/non-consumer split.
  ⚠ **Three entries were REMOVED from this list on 2026-07-26, all falsified** (kept visible here
  rather than deleted): **"bit 23 = multiplier"** — it is the **CURSOR-FETCH** enable, 18 of the
  phaser's 20 all-pass sections fetch no coefficient and still need gains (`-axes.md` §2.2);
  **"`880.1.60/20.*` = external-DRAM bracket (MCC +0.944)"** — R1 **FORCED** that one is a **READ**
  and the other a **WRITE**, the opposite assignment having zero survivors in all three machine
  models (`analysis/r1-allpass-motif.md` §5); **"`hi12=0xC40` = envelope detector"** — wrong on
  **all 61 sites**, the family is a 13-bit **immediate load** (`analysis/k5-output-stage.md` §2.3).
* PARAMETRIC EQ = 5 bands × 2 channels (confirmed three ways; an earlier "4 bands" was retracted).
* **Coefficient cursor**: implicit, +1 per class-A word, reset by `801.0.00.021`; biquad block
  `+0=b1 +1=b0 +2=b2 +3=−a1/a0 +4=−a2/a0 +5=make-up gain`.
  ⚠ **RETRACTED — was: "unit 1's bank base is `+0x80`."** K4 **falsified** the C-RAM halving:
  the 60-cell resident table at `0x50..0x8B` **straddles `0x80`**, unit 1's bank starts at **`0x90`**
  (the first 16-aligned cell after it) and it is a **software** allocation. The real `+0x80` lives
  in the **class-1 register file**, a different space (`analysis/k4-cursor.md` §1, §4). Also: the
  cursor's reset TARGET is a per-unit **base register** that nothing in the instruction stream
  loads — modelling it as 0 is a labelled placeholder, not a decode.
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
