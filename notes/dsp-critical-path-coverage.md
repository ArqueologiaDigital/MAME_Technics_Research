# uPD6383GF — DECODE COVERAGE ON THE CRITICAL PATH

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-26. **TASK C** of Felipe's redirect:

> "investigate what is needed to wire the sound-path of the DSP and which instructions would be
> executed. Then use that information to guide our next steps in decoding the instruction set"

This note answers the *coverage* half: it cross-references **what the disassembler decodes today**
against **what actually executes in one sample frame**, and turns the result into a **blocking
list** ranked by *does this word stop audio*, deliberately **not** by corpus frequency.

Reproduce — **every** number in this note comes out of one tool:

```
python3 tools/kn5000_dsp_critpath.py
    # defaults: notes/data/kn5000_dsp1_upload_coldboot.txt
    #           ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom
```

It joins the live cold-boot uC-IF capture (`tools/kn5000_dsp_wordfields.py`), the static ROM
corpus (`tools/kn5000_dsp_extract.py`) and the living disassembler
(`kn5000-roms-disasm/dsp/tools/dsp_disasm.py`, the byte-faithful mirror of
`src/devices/cpu/upd6383/upd6383d.cpp`). It decodes nothing new — it only asks the disassembler
what it can read, over the words that actually run.

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **DETERMINED**, **INFERRED** or
**OPEN**. §7 is the misses. **Nothing in the KN5000 driver was touched; the core is still
instantiated `set_disable()`d; no audio path was added.**

---

## Headline

1. **★★★ THE HEADLINE NUMBER IS NOT 18 % OR 9 %. ON THE FRAME PATH IT IS 10.5 %, AND ON THE PARTS
   THAT CARRY AUDIO IN AND OUT IT IS 0 %.** The live cold-boot frame is 286 instruction slots
   (header 60 + CHORUS 70 + epilogue 23 + REVERB 133) and **30 of them are decoded**. The 83-word
   scaffolding — the only code that touches the audio boundary — is **3 of 83**, and all three are
   the same instruction (`ldptr`). **MEASURED.** (§3)
2. **★★★ NOT ONE DECODED WORD SITS ON THE AUDIO BOUNDARY.** All six decoded forms move data
   between the coefficient cursor, the data pointer, the accumulator and P. **None** touches
   DI/DO, the external delay DRAM, the stack, a flag or the frame strobe. So the decoded subset
   cannot get a sample *in*, cannot get one *out*, and cannot even enter a body. **PROVEN BY
   CONSTRUCTION** from the six forms themselves. (§1, §4)
3. **★★★ THE SIMPLEST AUDIO-CARRYING PROGRAM IN THE MACHINE HAS ZERO DECODED WORDS.**
   `NO OPERATION` (algo 0, 49 words) is the dry pass-through that `programs.tsv` records as the
   image loaded for **42 effect slots** (of the 91 valid ones in a 100-entry `ALGO_TABLE`) — and
   **0 of its 49 words** are decoded. Seven other images are also at zero
   (`ENSEMBLE`, `DISTORTION`, `FUZZ`, `COMPRESSOR`, `VIBRATO`, `RING MODULATOR`, `MIX UP`);
   **8 of 38 images in total**. **MEASURED.** (§3.3)
4. **★★ THE CORE, IF ENABLED TODAY, WOULD STOP AT I-RAM 49 AND NEVER REACH A BODY.**
   `upd6383.cpp:554-557` treats *every* `is_end && class4==1 && addr8∈{0E,0F}` word as the end of
   the frame (`m_icount = 0`, line 584). `-headerdecode.md` §2 **PROVED BY CONSTRUCTION** that
   I-RAM 49 is a **CALL**, not the end. So the halt is attached to the wrong word: the frame would
   terminate on unit 0's call. **MEASURED by code reading** (file:line above). (§4.2)
5. **★★ A NEW HARD CONSTRAINT: THE COEFFICIENT CURSOR CANNOT BE A SINGLE FREE-RUNNING COUNTER.**
   The header executes **21 strict class-A words (22 with bit 23) before the unit-0 call** and
   contains **no `rstcur`**; the epilogue adds 9 more; there is exactly **one** `rstcur` in 2974
   body words. Yet every effect's coefficients are MEASURED to be uploaded at C-RAM base **0x00**
   (`-origin-capture.md`, 16/16 swept effects). Therefore a word or a hardware action **we have
   not decoded** rebases or banks the cursor at the unit call. Until it is found, *every*
   coefficient read in *every* body is at an unknown offset. **MEASURED (the counts); the
   conclusion is forced.** (§5, blocker B5)
6. **★★ THE SCAFFOLDING IS A VOCABULARY ISLAND, SO CORPUS STATISTICS CANNOT REACH IT.**
   **71 of its 79 distinct words and 65 of its 75 families occur ZERO times in the 2974 body
   words**, and its most frequent undecoded family occurs **three** times. Classes **9, C and D**,
   the route family `lo12 ∈ {0x445,0x446}`, the pointer siblings `0x820/0x822/0x825/0x827` and
   `hi12 = 0xC00` are all **scaffolding-only, 0/2974**. Frequency ranking — the method that
   produced the current worklist — is structurally blind to exactly the words that carry the
   audio. **MEASURED.** (§3.2, §6)
7. **★ COVERAGE, RESTATED HONESTLY.** Body corpus 267/2974 = 9.0 % by vocabulary (18.3 % counting
   operand roles). Scaffolding 3/83 = 3.6 %. Live frame 30/286 = 10.5 %. Simplest frame
   (`NO OPERATION` in unit 0) 29/265 = 10.9 %. **No figure moves in this pass** — this note
   decodes nothing, it maps what is missing. (§3)

---

## 1. What the disassembler decodes TODAY — the six forms, and what a core must DO

Source of truth: `kn5000-roms-disasm/dsp/tools/dsp_disasm.py:88-97` (`decoded()`), mirrored in
`src/devices/cpu/upd6383/upd6383d.cpp:344-359`. The executed semantics are
`src/devices/cpu/upd6383/upd6383.cpp:589-655`.

| # | word form | mnemonic | what the core must DO | evidence | in core? |
|---|---|---|---|---|---|
| 1 | `000.2.00.000` | `nop` | nothing | **PROVEN BY CONSTRUCTION** — sub-CPU writer `LABEL_038922` emits exactly this pattern | ✔ (empty branch, `upd6383.cpp:591`) |
| 2 | `801.0.NN.821` | `ldptr #$NN` | `dp ← NN` (**which** of CP/DP/BP1/BP2/PR1/PR2 is UNKNOWN) | **PROVEN BY CONSTRUCTION** — built at sub-CPU `LABEL_0387E6` | ✔ `m_dp = ad` (`:603`) |
| 3 | `801.0.00.021` | `rstcur` | `cursor ← 0` | **VERIFIED** on algo 39: class-A counts 0,6,12,18,24 \| `rstcur` \| 0,6,12,18,24 | ✔ `m_cursor = 0` (`:610`) |
| 4 | `202.A.dd.1D5` | `mac (p)+dd` | `acc += P ; P = coef[cursor++] × mem[p] ; p += (s8)dd` | **DETERMINED** — all 144 survivors of a 19,674,720-point search agree; impulse response exact on 9 ROM banks | ✔ (`:612-632`) |
| 5 | `202.A.dd.1D4` | `mac.lb (p)+dd` | as `mac`, plus `latchB ← mem[p]` | **DETERMINED**, same search | ✔ (same branch, `:621`) |
| 6 | `212.A.dd.407` | `mulst (p)+dd` | `mem[p] ← acc ; P = coef[cursor++] × acc ; p += (s8)dd` | **DETERMINED UNIQUELY** | ✔ (`:633-655`) |

**All six are implemented.** The "DECODED-but-not-implemented-in-the-core" bucket is therefore
**empty at word level** — but *not* at semantics level; see §4.3, which is where the real gap is.

**Resources the six forms touch:** the implicit coefficient cursor (C-RAM), one data pointer
(D-RAM), `acc`, `P`, `latchB`. **Resources they do NOT touch:** DI1-3 / DO1-3 serial audio,
the external delay DRAM, STACK1/STACK2, LC1-LC3, GF1-GF3 / RQ1-RQ3, BNK-R, `Fs`. Every one of
those is on the sound path.

Two further caveats on the six, both already stated in the sources and both material:

* **Which of C-RAM / D-RAM is which is UNKNOWN** — the assignment in the core is explicitly
  "arbitrary" (`upd6383.cpp:52-59`).
* **`ldptr`'s register is UNKNOWN**, and there is an unresolved conflict about which *space* it
  addresses. See blocker **B6**.

---

## 2. What executes in one sample frame

**INFERRED (strong)**, from `-headerdecode.md` §3, `-pointer.md` §2 and the `Fs-RST`/`PC-RST` pins:

```
   Fs edge -> PC := 0
    0.. 11   two opening blocks              <- the INPUT stage (candidate)
   12.. 48   preamble: LFOs, mixes, unit-0 pointer setup
       49    400.1.0E.000     CALL unit 0  -> I-RAM  84.. body ..RETURN to 50
   50.. 58   unit-1 pointer setup
       59    400.1.0F.007     CALL unit 1  -> I-RAM 200.. body ..RETURN to 60
   60.. 67   unit-0 return block   (I-RAM 64 = host patch slot, unit tag 0x0E)
   68.. 72   unit-1 return block   (I-RAM 71 = host patch slot, unit tag 0x0F)
   73.. 81   OUTPUT stage
       82    C00.A.47.407     wait for the frame strobe
```

The live cold-boot capture pins the two bodies exactly: the `@84` upload is **byte-identical to
ROM algo 1 (CHORUS, 70 words)** and the `@200` upload to **ROM algo 16 (ROOM REVERB 1, 133
words)** — verified by direct comparison, **MEASURED**. So the machine's real frame at cold boot
is **60 + 70 + 23 + 133 = 286 slots**, which is exactly the number `-headerdecode.md` §3 predicted
and it re-checks here.

---

## 3. The census

### 3.1 Decoded coverage per region — **MEASURED**

| region | words | decoded | undecoded | % decoded | which forms |
|---|---|---|---|---|---|
| header, I-RAM 0..59 | 60 | **2** | 58 | 3.3 % | `ldptr` ×2 |
| epilogue, I-RAM 60..82 | 23 | **1** | 22 | 4.3 % | `ldptr` ×1 |
| unit-0 body @84 (CHORUS) | 70 | **1** | 69 | 1.4 % | `mac` ×1 |
| unit-1 body @200 (REVERB) | 133 | **26** | 107 | 19.5 % | `mac` ×7, `nop` ×19 |
| **LIVE FRAME (the above)** | **286** | **30** | **256** | **10.5 %** | |
| simplest frame (NO OPERATION in unit 0) | 265 | 29 | 236 | 10.9 % | |
| scaffolding alone (header+epilogue) | 83 | **3** | 80 | **3.6 %** | `ldptr` ×3 |
| all 38 ROM bodies | 2974 | 267 | 2707 | 9.0 % | `mac` 134, `nop` 62, `mac.lb` 35, `mulst` 35, `rstcur` 1 |

Read the epilogue row twice. **The output stage of the machine is one `ldptr` away from
completely unknown.**

### 3.2 The scaffolding is a vocabulary island — **MEASURED**

```
   distinct words in header+epilogue                        79
   ... that occur in NO body word (of 2974)                 71   (90 %)
   distinct (hi12,class4,lo12) families                     75
   ... that occur in NO body                                65   (87 %)
   most frequent undecoded family in the scaffolding         3 occurrences (801.0.**.825)
```

Class census (**MEASURED**):

| class4 | header | epilogue | 2974 bodies |
|---|---|---|---|
| 9 | 1 | **5** | **0** |
| C | 0 | **1** | **0** |
| D | 0 | **1** | **0** |
| 8 | 1 | 1 | 42 |
| A | 21 | 1 | 822 |
| 2 | 16 | 3 | 1550 |

and `hi12 = 0xC00`: **0 in the header, 2 in the epilogue (I-RAM 76 and 82), 0 in 2974 body words**.

### 3.3 Per-image decoded count — **MEASURED**

Eight of the 38 distinct images contain **zero** decoded words:

```
   NO OPERATION 0/49   ENSEMBLE 0/96   DISTORTION 0/42   FUZZ 0/42
   COMPRESSOR   0/40   VIBRATO  0/53   RING MODULATOR 0/46   MIX UP 0/64
```

At the other end: `PARAMETRIC EQ` 41/105 (39.0 %), `MULTI TAP DELAY` 15/68, `PEQ+S.DELAY` 11/54,
`ROOM REVERB 1` 26/133. The decoded subset is concentrated in exactly the two families that were
solved analytically (biquad, reverb diffuser) and is absent from everything else.

`NO OPERATION` matters disproportionately: `programs.tsv` records it as the image loaded for
**42 effect slots**. It is the machine's own dry pass-through — the *simplest audio-carrying
program that exists* — and the disassembler cannot read one word of it.

---

## 4. Classification of the executed words

### 4.1 DECODED-and-implementable — 30 of 286 (10.5 %)

`ldptr` ×3 (I-RAM 42, 50, 69), `mac` ×8, `nop` ×19. That is the whole list.

### 4.2 DECODED-but-WRONGLY-DISPATCHED in the core — 1 word class, and it is fatal

`upd6383.cpp:554-557` ends the frame on any `is_end && class4==1 && addr8 ∈ {0x0E,0x0F}` word.
`-headerdecode.md` §2.1 **PROVED BY CONSTRUCTION** that I-RAM 49 is a **CALL** (the header loads
`0x821/0x827/0x825` twice, at 42-44 and 50-52, so a body must run and return in between). A core
started at PC = 0 today therefore executes 50 words, hits I-RAM 49, sets `m_frame_done` and stops
— **the bodies never run at all**. The comment at `:584` already flags the stop as SPECULATIVE;
this note upgrades that to *known-wrong for the header's copy of the word*. (Not a bug in shipping
MAME: the device is disabled.)

### 4.3 DECODED SEMANTICS the core does NOT apply — the real second bucket

Two word-level facts are MEASURED but are deliberately **not** acted on outside the six forms
(`upd6383.cpp:570-577`, "one bit of a 36-bit word is not a decode"). That discipline is right, and
it is also a measurable hole:

| MEASURED semantic | evidence | frame path (286 slots) | body corpus |
|---|---|---|---|
| class-A word consumes `coef[cursor++]` | cursor base 0x00, +1/class-A, 16/16 swept effects | **74 class-A words, 66 not executed** | 822 class-A, 618 not executed |
| `hi12` bit 4 = `mem[ptr] ← acc` | `0x212 = 0x202+bit4`, `0x092 = 0x082+bit4`; absence control 0/410 | **65 bit-4 words, 65 not executed** | 680 bit-4, 645 not executed |

So on the live frame the core would execute **not one** accumulator store, and would leave the
cursor 66 positions behind. Any partial enable of the core must fix this first or its C-RAM
addresses are nonsense.

### 4.4 UNDECODED — 256 of 286, ranked in §5

---

## 5. THE BLOCKING LIST

Ranked by **how much the word blocks audio**, not by frequency. Tier 0-1 words stop the machine
dead; tier 2 words make it compute on the wrong memory; tier 3 words make the *sound* wrong.

---

### B1 — the unit-tagged transfer word `xxx.1.{0E,0F}.xxx` **[TIER 0 — nothing executes without it]**

* **Fields.** `class4 == 1`, `addr8 == unit index` (0x0E = unit 0, 0x0F = unit 1), `hi12` bit 10
  set / bit 11 clear, `lo12` free. Observed `hi12`: `400 428 424 420 42C 612 604 602 504`
  — i.e. `0x400 | {000,028,024,020,02C,212,204,202,104}`, an END bit riding on an ordinary
  microword.
* **Where.** Header **I-RAM 49** (`400.1.0E.000`) and **I-RAM 59** (`400.1.0F.007`) = the two
  CALLs. Last word of **38 of 38** bodies (mean normalised position **1.000**) = the RETURNs.
  Shapes: `(1,0x0E,0x000)` ×35, `(1,0x0E,0x407)` ×2, `(1,0x0F,0x000)` ×1. **Zero** occurrences
  anywhere else in 7108 words across 96 streams.
* **What neighbours imply.** PROVEN BY CONSTRUCTION that I-RAM 49 transfers and control returns
  (register reuse at 42-44 / 50-52). The chip has a **2-level stack** (CDJ-500 block diagram) —
  exactly deep enough for header→body, no more. Call and return share one encoding and are told
  apart by context.
* **Bounds already in hand.** The `addr8` is the unit index (91/91), *not* an address — `addr8`
  is 8 bits and the body entries are 84 and 200, so the target is **not in the word**. Two
  exhaustive bitfield scans for a branch target are negative. So the transfer is either a
  **2-entry vector** (tag → fixed entry) or **host-loaded entry registers**.
* **Open.** Which of the two; and what datapath work the word still performs (`612` = END|`212` =
  END + accumulator store — the FLAGGED unexplained case, 5 occurrences).

---

### B2 — the frame-wait word `C00.A.47.407` @ I-RAM 82 **[TIER 0 — no per-sample cadence]**

* **Fields.** `hi12 = 0xC00` (bit 11 ESCAPE set ⇒ bits[10:0] mean something else; under the
  MEASURED escape rule `hi12[11:8]==C` the bits **[23:12] = 0xA47 are a 12-bit IMMEDIATE**, so the
  "class A / addr8 0x47" reading is void here).
* **Where.** The **last** word of the epilogue, i.e. the last word of the frame. `hi12 = 0xC00`
  occurs **0 times in 2974 body words** and **twice in the epilogue** — I-RAM **76**
  (`C00.9.84.000`) and I-RAM **82**.
* **Bounds.** The epilogue (I-RAM 60..82) contains **no end-of-block word at all** — a block that
  never ends is a block closed by hardware; the pins are named `Fs-RST` / `PC-RST`; the header is
  re-entered every sample because it reloads the pointer registers rather than the bodies
  restoring them.
* ⚠ **Caveat this note adds.** `-headerdecode.md` §3 identifies I-RAM 82 as the wait using
  "`hi12 == 0xC00` occurs zero times in 2974 body words". That statement is true, but it does
  **not** single out word 82 — word 76 shares the same `hi12`. The identification rests on
  **position** (last word of the frame), which is still good evidence, but the `hi12` argument
  should not be quoted as if it were unique.
* **Open.** Whether 82 is a *wait* (stall until Fs) or merely the last word before a hardware PC
  reset, and what `0xA47` selects. What word 76 is.

---

### B3 — the AUDIO INPUT block, I-RAM 0..11 **[TIER 1 — no sample enters]**

```
    0  092.2.01.20D      7  090.A.01.1C8
    1  C0A.0.E0.000      8  084.2.01.1C0
    2  084.2.02.680      9  012.2.FF.1D5
    3  012.2.FF.1CE     10  282.A.01.417
    4  204.2.02.1CE     11  400.2.01.447   END OF BLOCK
    5  202.A.00.448
    6  400.A.00.419      END OF BLOCK
```

* **Where / how often.** The first two blocks of the frame, executed once per sample, before
  anything else. **All 12 words occur 0 times in 2974 body words**; 11 of the 12 families do too.
* **What neighbours imply.** `202.A.00.448` (I-RAM 5) shares `hi12 = 0x202` and `class4 = 0xA`
  **exactly** with the DETERMINED `mac`/`mac.lb` forms and differs only in `lo12`
  (`0x448` vs `0x1D5`/`0x1D4`; Hamming distance 7, so this is a *family* argument, not a
  near-miss argument). If `class4` really is the arithmetic and `lo12` the route — the open
  hypothesis of `-core-draft.md` §6 — then I-RAM 5 is a multiply-accumulate with a different
  operand route, i.e. the input already exists by then. That would put the actual input capture at
  **I-RAM 0..4** (and 7..9). `addr8 = 0xFF` at I-RAM 3 and 9 is the established signed −1
  post-decrement. **INFERRED, weak — it depends on an unproven hypothesis.**
* **Bounds.** `addr8 == 0x03` never occurs in the header, so this is **not** a three-way
  DI1/DI2/DI3 sweep; the chip has three serial input ports and this board uses one stereo pair.
* ⚠ **MISS this note reports.** `-headerdecode.md` §4.2 presents these as a near-parallel L/R
  pair. Word-for-word, the parallelism is **weaker than that reading suggests**: the two blocks
  agree on `hi12` in only 3 of 5 slot pairs (`084`/`084`, `012`/`012`, `400`/`400`) and **never**
  on `lo12` (`680`↔`1C0`, `1CE`↔`1D5`, `419`↔`447`). They are structurally similar but they are
  **not** copies of one another with a channel index swapped. The stereo reading stays
  **SPECULATIVE** and should not be leaned on.
* **Also unresolved here.** `-headerdecode.md` §4.1's flag stands: three of the four values the
  host patches into the epilogue's wet-level slots are `hi12 = 0xC40`, which `-effect-map.md`
  calls the *envelope detector*. `0xC40` occurs **57 times in 19 body images** (mean normalised
  position 0.570) and as **three of the four host-written wet-level values**
  (`C40.5.40.445`, `C40.A.80.445`, `C40.6.40.446`; the fourth is `C41.9.00.446`). One of the two
  identifications must give.

---

### B4 — the AUDIO OUTPUT stage, I-RAM 73..82 **[TIER 1 — no sample leaves]**

```
   73  E30.C.00.404   cur+     <- class C: 1 word in the whole machine, 0/2974 in bodies
   74  C16.9.AB.000   cur+        (hi12[11:8]==C: bits[23:12] = immediate 0x9AB)
   75  82E.8.0F.000   cur+     <- class 8 post-sum step, OPERATION UNKNOWN
   76  C00.9.84.000   cur+        (immediate 0x984)
   77  859.0.86.822            <- pointer-load sibling, 0x822 <- #$86
   78  A3C.D.9F.287   cur+     <- class D: 1 word in the whole machine, 0/2974 in bodies
   79  012.2.FF.1CE            <- BODY vocabulary; hi12 bit 4 = store acc to mem[ptr], p -= 1
   80  104.2.00.1CE            <- BODY vocabulary, 22 corpus occurrences
   81  102.2.00.000            <- BODY vocabulary, 34 occurrences, "gain multiply"
   82  C00.A.47.407            <- B2, the frame wait
```

* **The split is informative.** I-RAM **79-81 use ordinary body vocabulary** (a bit-4 store and
  two multiply-family words) — that is the final *arithmetic*. I-RAM **73-78 are scaffolding-only**
  and contain the only class-C and class-D words in the entire machine. If a DO write exists as an
  instruction, it is in **73..78**.
* **What the host says.** The only two words the host ever patches at runtime are **I-RAM 64**
  (`011.9.0E.445`) and **I-RAM 71** (`011.9.0F.446`) — per-unit, after both bodies have run, unit
  tags in `addr8`, `lo12` invariant per slot (`0x445`/`0x446`, **0/2974 in bodies**) while
  `hi12`/`class4`/`addr8` track the effect selection (observed host values `C40.5.40.445`,
  `C40.A.80.445`, `C40.6.40.446`, `C41.9.00.446`). **INFERRED (strong):** these are the per-unit
  **effect-return / wet-level** words, and `0x445`/`0x446` name the two return buses.
* **Bounds.** `-origin.md` reads I-RAM 77's `0x822 ← #$86` as the reverb high-block base, i.e.
  the escape-form loads are state pointers.
* **Open.** Everything about 73, 74, 76, 78. These six words are the single densest concentration
  of unknown-and-unique encoding in the machine.

---

### B5 — the missing CURSOR REBASE / BANK SWITCH **[TIER 1 — every coefficient is at the wrong address]**

* **The measurement.** Header: **21 strict class-A words, 22 words with bit 23, 0 `rstcur`**, all
  before the unit-0 call. Epilogue: 1 class-A, 9 bit-23, 0 `rstcur`. Bodies: **1 `rstcur` in
  2974 words** (algo 39's mid-program rewind).
* **The contradiction.** Every effect's coefficient upload is MEASURED to be anchored at C-RAM
  base **0x00**, identically for all 16 swept effects. A single free-running cursor would be at
  21 (or 22) when the unit-0 body starts, so the body's first `mac` would read C-RAM[0x15], not
  C-RAM[0x00].
* **Corroboration that the two banks are separate.** `-headerdecode.md` §5, **MEASURED**:
  (coefficients uploaded) − (cursor-fetching body words) is +1 in 18 of 38 images and within
  −3..+9 in 35 of 38 — **never near +23**. The header therefore runs on its own fixed coefficient
  bank.
* **So what is missing.** Either (a) an undecoded word in the header rebases the cursor / switches
  **BNK-R** at the unit call, or (b) the CALL itself rebases it in hardware, or (c) there is more
  than one cursor. **No candidate word has been identified.** This is the cheapest high-value
  target on the list, because the answer is inside 83 words that are already on disk.
* **Note for whoever enables the core.** The present core accidentally gets base 0x00 right *only
  because* it never executes the header's class-A words (they are undecoded, and undecoded words
  do not advance `m_cursor`). Decode any of them without solving this and the C-RAM addresses
  immediately become wrong.

---

### B6 — the pointer-register family, and which SPACE `ldptr` addresses **[TIER 2 — everything reads the wrong cells]**

* **On the frame path:** 11 pointer loads, **3 decoded** (all `lo12 = 0x821`).

```
   header  15  C0A.2.92.820    43  801.0.6C.827    50  801.0.50.821  (decoded)
           22  C04.3.12.820    44  801.0.25.825    42  801.0.70.821  (decoded)
           29  C42.4.57.820    51  801.0.64.827
           31  C0A.4.B1.820    52  801.0.25.825
           40  C4A.1.C0.820
   epilog  62  801.0.26.825    77  859.0.86.822    69  801.0.90.821  (decoded)
```

  All 11 occur **0 times in 2974 body words** — no body contains a pointer load at all.
* **The core models ONE data pointer.** The chip has six (CP, DP, BP1, BP2, PR1, PR2) plus BNK-R.
  Which register each `lo12` names is UNKNOWN.
* **★ CONFLICT this note surfaces, and does NOT resolve.** The *same* fully-decoded form
  `801.0.NN.821` is used by the **host** to set **C-RAM coefficient destinations** — for
  PARAMETRIC EQ the observed framing is `26.825 / 00.821 / 1E.821 / 00.821 / 06.821 / 0C.821 /
  12.821 / 18.821 / 90.821`, and `0x00/0x06/0x0C/0x12/0x18` are exactly the EQ's five biquad
  coefficient blocks and `0x1E = 30 = 5×6` their extent (**MEASURED**, `-origin-capture.md`) —
  while the **header** uses it for the per-unit `0x70`/`0x50` that `-pointer.md` reads as the
  **D-RAM state** origin, and the core implements as `m_dp` (`upd6383.cpp:598`). One form cannot
  address both spaces unless the space is decided elsewhere (BNK-R? a second field?) or the two
  uses are different registers. Corroborating oddity: the epilogue's I-RAM 62 (`26.825`) and
  I-RAM 69 (`90.821`) are **byte-identical to the host's coefficient-upload open and close
  words**.
* **Discriminating experiment (cheap, no hardware).** Capture the uC-IF stream for two effects
  whose C-RAM extents differ (EQ = 0x1E, ENSEMBLE = 6 cells) and check whether a `.825` or a
  `.821` load ever carries a value inside the MEASURED **state** block `{0x64,0x68,0x6C,0x70,
  0x74}`. If `.821` never does outside the header, `.821` is the coefficient pointer and the
  core's `m_dp` assignment is wrong.

---

### B7 — `hi12` bit 4 and the class-A cursor advance, on undecoded words **[TIER 2 — see §4.3]**

Not new unknowns — **known semantics the core withholds**. 65 of 65 bit-4 words and 66 of 74
class-A words on the live frame. Any staged enabling of the core must decide this explicitly.

---

### B8 — the class-2 routing backbone `000.2.**.xxx` **[TIER 3 — the signal does not move]**

| family | corpus | images | live frame | simplest frame |
|---|---|---|---|---|
| `000.2.**.407` | 132 | 31 | 11 | 8 |
| `000.2.**.40E` | 77 | 37 | 5 | 4 |
| `000.2.**.1CD` | 49 | 28 | 5 | 3 |
| `000.2.**.000` | 40 | 24 | — | 6 |
| `000.2.**.1CE` / `000.2.**.447` | 140 / 34 | | | |

`hi12 = 0x000` means **every enable clear** — 27.2 % of the corpus, and the NOP is one of them,
which is what a horizontal microword predicts. Class 2 = pointer post-increment **without**
cursor fetch. These are the words that move samples between D-RAM cells; the whole distinction
between them is carried in `lo12`, and `lo12` has a MEASURED sub-boundary at `[11:8]‖[7:2]`
(`-necfamily.md`). `NO OPERATION` is built almost entirely from this family.

---

### B9 — `212.2.**.000`, the plain store **[TIER 3 — nearly decoded]**

103 occurrences over 32 images (88 of them the exact word `212.2.00.000`), mean normalised
position 0.512. Bit 4 gives `mem[ptr] ← acc`; `lo12 = 0x000` asks nothing further — which is
itself the corroboration that the store is named in `hi12`. **This is the closest thing on the
list to a free decode**: what is unknown is only whether the word does anything *else*.

---

### B10 — the undecoded class-A multiplies **[TIER 3 — 618 of 822]**

`000.A.**.415` (91/27 images), `202.A.**.415` (42/13), `212.A.**.1D5` (35/20), `212.A.**.412`
(42/15), `102.A.**.4C8` (41/14), `102.A.**.64B` (16/2, ×9 in the reverb). Their **operand role**
is often known (`202.A.*.415` = mix/tap gain, 97 %; `102.A.*.64B` = reverb diffuser decay, 100 %;
500 of 822 class-A words have a named coefficient) but their **micro-operation** is not. Note the
shape of the problem: `202.A.dd.1D5`/`1D4` and `212.A.dd.407` *are* determined, so this family
differs from the solved ones **only in `lo12`** — which is why `-core-draft.md` §6 already ranks
"`lo12` = route, `class4` = arithmetic" as the highest-value structural test.

---

### B11 — the external delay-DRAM bracket `880.1.{60,20,30}.***` **[TIER 4 — blocks delay/reverb only]**

231 occurrences over all 38 images, plus **two in the header** (I-RAM 12 `880.1.20.2D5` and
I-RAM 26 `880.1.20.40B` — both the `0x20` CLOSE form, and there is **no `880.1.60` OPEN anywhere
in the header**, which is odd and unexplained. The nearest thing to an open is `800.1.60.00B` at
I-RAM 46 and 54 — same `class4`/`addr8`, but `hi12 = 0x800`, not `0x880`, so it is a different
family and the asymmetry is real). Mean normalised body position
0.500. INFERRED as OPEN (`0x60`) / CLOSE (`0x20`) / framing (`0x30`), MCC +0.944 over the
DRAM-using effects. Needed by CHORUS, all delays and the reverb; **not** needed by PARAMETRIC EQ,
DISTORTION, FUZZ or COMPRESSOR. Hardware bound: IC309 = M5M44260AJ-7S, **16-bit** data, so a
delayed sample is truncated to 16 bits going out and coming back — that is real behaviour, not a
shortcut. **Open:** whether `0x20` latches an address or data.

---

### B12 — class 8, the post-sum step **[TIER 4 — level/format wrong, but audio flows]**

42 body occurrences over 15 images (`804.8.16.415` ×35), plus **I-RAM 47** (`800.8.0C.000`) and
**I-RAM 75** (`82E.8.0F.000`) on the scaffolding — the latter inside the output stage. Its
*position* is DETERMINED by the constraint search (between "the sum is complete" and "the sum
becomes stored state"); its **operation** is unknown (rescale / round / saturate?). Class 8 is the
one class the addressing rule freezes (`addr8` is not a post-increment there).

---

### B13 — timbre words: table-lookup triple, LFO, envelope detector **[TIER 5 — sound wrong, audio flows]**

`040.0.00.C63 | 000.6.TT.4CD | 012.4.01.1CE` (accounts for every class-4/6 word, MCC +1.000),
`hi12 = 0x082` LFO read (64/18 images), `092.A.00.200` / `094.A.00.200` phase accumulate and wrap,
`hi12 = 0xC40` envelope detector (57/19). These change **what** you hear, not **whether**. They
should be decoded last, not first — which is the opposite of what a frequency-ranked worklist
recommends.

---

## 6. What this means for the decoding roadmap

The corpus-frequency worklist (`-core-draft.md` §6) and the audio-blocking ranking **disagree
almost completely**, and the reason is structural: the words that carry audio in and out occur
**once per frame** — the lowest possible frequency — and live in a vocabulary that is 90 % disjoint
from the corpus that the statistics were computed over.

| priority | frequency-ranked worklist | audio-blocking ranking (this note) |
|---|---|---|
| 1 | `212.2` vs `212.A` (bit 23) | **B1** unit-tagged CALL/RETURN |
| 2 | the `lo12 = 0x415` group | **B5** cursor rebase / bank switch |
| 3 | table-lookup triple | **B3/B4** the I/O words at I-RAM 0..11 and 73..82 |
| 4 | `880.1.20.*` | **B6** pointer-register identity |
| 5 | *the 83 header+stub words* | **B8/B9/B10** the class-2/class-A backbone |
| 6 | the datasheet | the datasheet (unchanged — still the highest-payoff swing) |

Item 5 of the old list is items 1-4 of the new one. **The single most valuable thing that can be
done next is to work the 83 scaffolding words**, and it needs a different instrument: with a
maximum family multiplicity of 3 there is nothing for a co-occurrence or frequency method to bite
on. What is left is (a) the datasheet, (b) *positional/dataflow* reasoning of the kind that solved
the biquad, and (c) **live differential capture** — patch one epilogue slot from the host, observe
which I-RAM word changes and how the audible effect return changes. (c) is available today
because the host patch mechanism is already exercised and captured.

A staged plan that follows the blocking order, and produces **silence rather than wrong audio**
until each stage is proved:

1. **B1 + B2** — make the frame *sequence* right (call, return, 2-level stack, per-frame PC
   restart). Verifiable with no audio at all: assert that the PC visits 0..49, 84..153, 50..59,
   200..332, 60..82 and repeats at 44.1 kHz.
2. **B5 + B7** — make the *addresses* right (cursor rebase, cursor advance on all class-A words,
   bit-4 stores). Verifiable against the MEASURED C-RAM map: after one frame, the coefficients the
   body read must be the ones the host wrote.
3. **B6** — settle which register/space `ldptr` touches.
4. **B3 + B4** — the audio boundary. Only after this can there be sound, and it should be gated on
   a spectral A/B against the real instrument, not on "it makes a noise".

---

## 7. Misses, corrections and things this pass did NOT get

1. **No word was decoded.** This note is a map of the hole, not a filling of it. Coverage figures
   are unchanged (9.0 % body vocabulary, 18.3 % including operand roles).
2. **The input stage got *weaker*, not stronger.** §5/B3: the "parallel stereo pair" reading of
   I-RAM 0..6 / 7..11 does not survive a word-level comparison — the two blocks never agree on
   `lo12`. I could not replace it with anything better. The `0xC40` envelope-vs-wet-level conflict
   is likewise still open, and this pass adds only that `0xC40` is common in bodies (57/19 images)
   while `0x445`/`0x446` are unique to the epilogue, which mildly favours *"`0xC40` is a shared
   enable pattern, not a role"* over either identification — but that is a lean, not a result.
3. **The frame-wait `hi12` argument is weaker than published** (§5/B2): `0xC00` appears twice in
   the epilogue, so it does not identify I-RAM 82 on its own. Position still does.
4. **A minor disassembler hazard, checked and mostly clean.** `cursor_fetch()`/`coeff_consumer()`
   test bit 23 / `class4 == 0xA` even on `hi12` bit-11 ESCAPE words, where the MEASURED rule says
   bits [23:12] are immediate data and `class4` is not a class. Control: escape words with
   `class4 == 0xA` number **0 in 2974 body words**, **0 in the header** and **1 in the epilogue**
   (I-RAM 82). So the `; C-RAM[0xNN]` annotations are safe; the only affected word is the frame
   wait, where the printed `cur+` is an artifact. Worth a comment in the disassembler; not worth a
   behaviour change while the escape rule is itself INFERRED.
5. **B5 is stated as a contradiction, not solved.** I did not find the rebasing word. The
   candidates I could not rule out are the header's escape-form loads (I-RAM 15, 22, 29, 31, 40)
   and the CALL word itself.
6. **Nothing here was checked by running the core.** All of it is static, over the live-captured
   I-RAM plus the ROM corpus. §4.2's claim about where the core would stop is read off
   `upd6383.cpp:554-557,581-586`, not observed.
7. **DSP2 (IC310, MN19413) is out of scope** and unexamined, as is the question of whether the
   KN5000 routes the tone generator through IC311 as an insert or a send/return — the service
   documentation available here (`kn5000-docs/tone-generator.md`) still lists "trace the PCM audio
   serial bus (BCK/SDOR/SDOF) connections" as an open item, and B3/B4 cannot be finished without
   it.

---

## 8. Appendix — the 83 scaffolding words, with their body-corpus counts

`w` = occurrences of the exact word in 2974 body words; `f` = occurrences of its
`(hi12,class4,lo12)` family. `DEC` marks the three decoded words.

```
 HEADER (I-RAM 0..59)
   ?  0 092.2.01.20D w0 f0        ?  20 000.A.00.64D w0 f0       ?  40 C4A.1.C0.820 w0 f0
   ?  1 C0A.0.E0.000 w0 f0        ?  21 410.A.00.40E w0 f0       ?  41 400.A.00.21A w0 f0
   ?  2 084.2.02.680 w0 f0        ?  22 C04.3.12.820 w0 f0      DEC 42 801.0.70.821  ldptr #$70
   ?  3 012.2.FF.1CE w0 f0        ?  23 692.A.00.415 w0 f0       ?  43 801.0.6C.827 w0 f0
   ?  4 204.2.02.1CE w0 f0        ?  24 692.2.00.415 w0 f0       ?  44 801.0.25.825 w0 f0
   ?  5 202.A.00.448 w0 f0        ?  25 000.2.00.2D9 w0 f0       ?  45 010.A.00.20C w0 f0
   ?  6 400.A.00.419 w0 f0  END   ?  26 880.1.20.40B w6 f7       ?  46 800.1.60.00B w0 f0
   ?  7 090.A.01.1C8 w0 f0        ?  27 012.2.01.655 w12 f12     ?  47 800.8.0C.000 w0 f0   class 8
   ?  8 084.2.01.1C0 w0 f0        ?  28 504.2.00.1D5 w0 f0       ?  48 C64.5.A2.000 w0 f0
   ?  9 012.2.FF.1D5 w0 f2        ?  29 C42.4.57.820 w0 f0       ?  49 400.1.0E.000 w7 f7  CALL unit 0
   ? 10 282.A.01.417 w0 f0        ?  30 09A.A.00.200 w8 f8      DEC 50 801.0.50.821  ldptr #$50
   ? 11 400.2.01.447 w0 f0  END   ?  31 C0A.4.B1.820 w0 f0       ?  51 801.0.64.827 w0 f0
   ? 12 880.1.20.2D5 w2 f2        ?  32 000.A.FF.207 w0 f0       ?  52 801.0.25.825 w0 f0
   ? 13 282.2.00.000 w0 f2        ?  33 412.A.00.200 w0 f0       ?  53 010.9.D0.20C w0 f0  class 9
   ? 14 400.A.00.000 w0 f0  END   ?  34 000.A.FF.407 w0 f0       ?  54 800.1.60.00B w0 f0
   ? 15 C0A.2.92.820 w0 f0        ?  35 012.A.00.1C0 w0 f0       ?  55 000.2.01.007 w0 f0
   ? 16 192.A.00.455 w0 f0        ?  36 400.A.00.000 w0 f0 END   ?  56 C64.6.A2.007 w0 f0
   ? 17 292.A.00.455 w0 f0        ?  37 092.A.01.1C0 w0 f0       ?  57 000.2.01.000 w10 f102
   ? 18 182.A.00.415 w0 f0        ?  38 809.0.00.839 w0 f0       ?  58 000.1.8A.007 w0 f0
   ? 19 512.2.00.44D w0 f0        ?  39 410.A.FF.647 w0 f0       ?  59 400.1.0F.007 w0 f0  CALL unit 1

 EPILOGUE (I-RAM 60..82)
   ? 60 092.1.8D.15B w0 f0        ?  68 092.1.8C.19B w0 f0       ?  76 C00.9.84.000 w0 f0  class 9
   ? 61 012.1.8D.05B w0 f0       DEC 69 801.0.90.821  ldptr #$90 ?  77 859.0.86.822 w0 f0
   ? 62 801.0.26.825 w0 f0        ?  70 2A6.1.85.0C7 w0 f0       ?  78 A3C.D.9F.287 w0 f0  class D
   ? 63 2A7.9.05.1C3 w0 f0        ?  71 011.9.0F.446 w0 f0  PATCH?  79 012.2.FF.1CE w0 f0
   ? 64 011.9.0E.445 w0 f0 PATCH  ?  72 000.1.06.087 w0 f0       ?  80 104.2.00.1CE w22 f57
   ? 65 200.1.8F.1C1 w0 f0        ?  73 E30.C.00.404 w0 f0 classC ? 81 102.2.00.000 w34 f42
   ? 66 000.1.8C.107 w0 f0        ?  74 C16.9.AB.000 w0 f0 class9 ? 82 C00.A.47.407 w0 f0  FRAME WAIT
   ? 67 980.5.20.402 w0 f0        ?  75 82E.8.0F.000 w0 f0 class8
```

Host-written values seen in the two patch slots (cold-boot capture):
`I-RAM 64 ← C40.5.40.445, C40.A.80.445` and `I-RAM 71 ← C40.6.40.446, C41.9.00.446`.
