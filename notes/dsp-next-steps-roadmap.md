# uPD6383GF (IC311) — NEXT STEPS: wire the sound path, then decode what runs on it

KN5000 effects DSP, NEC uPD6383GF-3BA. Date: 2026-07-26. This is the **synthesis** of the three
analyses Felipe's redirect produced, and the plan that comes out of them:

| | note | commit | what it answers |
|---|---|---|---|
| **A** | `notes/dsp-audiopath-wiring.md` | `088e3f6` | where the sample comes from, where it goes, what clocks it |
| **B** | `notes/dsp-perframe-execution.md` | `cb84127` | which instruction words actually execute, in order, per sample |
| **C** | `notes/dsp-critical-path-coverage.md` | `3d7b1d8` | which of those are decoded, and which block audio |

Everything is tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **DETERMINED**, **INFERRED**,
**SPECULATIVE** or **FALSIFIED**. §1 adjudicates the contradictions between A, B and C by going
back to the sources. §6 is new measurement made in this pass, reproducible with
`tools/kn5000_dsp_nextsteps.py`. §7 is what this pass did **not** get.

**Nothing in the driver was touched. The core is still instantiated `set_disable()`d
(`kn5000.cpp:1147`). No audio path was added. The disassembler was not edited.**

---

## 0. SCOPE — the kernel and one reverb

Felipe narrowed the search deliberately, and the narrowing is well chosen:

* the **KERNEL** = the resident scaffolding the host uploads once and never replaces: the 60-word
  common header at I-RAM 0..59 and the 23-word epilogue at 60..82. **83 words.**
* **ONE REVERB** = the 133-word image at I-RAM 200..332. This is not one effect among many: over
  all 100 algorithm streams in the Sub CPU ROM there is **exactly one** image that ever loads at
  I-RAM 200, and algos 16..27 (all twelve reverb presets) share it byte-for-byte (**MEASURED**, B
  §3). **Unit 1 runs these same 133 words in every frame of every effect.**

So the scope is **216 words** — and those 216 words are not a sample of the machine, they are the
**floor of every frame it ever runs**. Nothing outside them can produce sound on its own, and
everything outside them is one effect among 38.

Two supporting facts make the narrowing correct rather than merely convenient:

* the reverb is the **best-understood block on the whole path** — 133 words in only 31 families,
  26 decoded, all 33 of its class-A coefficients named, and its algorithm solved structurally
  (`kn5000-roms-disasm/dsp/algorithms/reverb.md`);
* the kernel is the **worst-understood** — 83 words, 75 families, **3** decoded, and 65 of those
  families occur **zero** times in the 2974-word body corpus (C §3.2). Every frequency-ranked
  worklist this project has produced is structurally blind to it.

---

## 1. ADJUDICATIONS — the contradictions between A, B and C

### 1.1 "three DI/DO wired" (A) vs "this board uses one stereo pair" (C §B3) → **A**

C's sentence *"the chip has three serial input ports and this board uses one stereo pair"* carries
**no source**; it sits in a paragraph whose actual measurement is *"`addr8 == 0x03` never occurs in
the header"*. A read the schematic: IC303 `SDOA`(p4,R308 470 Ω)→`DI1`(20), `SDOB`(p6,R309)→`DI2`(21),
`SDO1`(p197,R313)→`DI3`(22); `DO1`(23,R333)→`SDIA`(p3), `DO2`(24,R332)→`SDIB`(p5), `DO3`(25,R331)→
off-block — cross-checked against BLOCK (A) on p.28, which draws the same six arrows.
**Adjudicated for A: a sourced direct read of two independent drawings beats an unsourced
inference.** C's *measurement* survives intact; only its gloss is struck.

**And the two are not actually in tension.** C's own MISS report says the two opening blocks
(I-RAM 0..6 and 7..11) agree on `hi12` in 3 of 5 slot pairs and **never** on `lo12`
(`680`↔`1C0`, `1CE`↔`1D5`, `419`↔`447`). That is exactly what A's "two different **ports**"
reading predicts *if the port/route is carried in `lo12`* — and "`lo12` = route, `class4` =
arithmetic" is already the highest-ranked structural hypothesis in `-core-draft.md` §6. See §1.4:
this pass adds a third, independent line of evidence for it.

### 1.2 `hi12 == 0xC40` — "envelope detector" vs "12-bit immediate format" → **B, reinforced**

B §6.2 settles the collision `-headerdecode.md` §4.1 flagged, against the envelope reading: `0xC4_`
occurs in 19 of 38 programs **including the reverb** (`C40.1.80.000` ×4 — a reverb tank has no level
detector), and `hi12[11:8] == 0xC` is the already-MEASURED "bits[23:12] are a 12-bit immediate"
format (`-header.md` §6). **Accepted.** Two additions from this pass:

* Applied to the kernel it makes the whole C-family read cleanly as *one opcode + one immediate*
  (§6.B): the five `lo12 = 0x820` loads carry 448/658/786/1111/1201, and — new — **I-RAM 48 and 56
  are the SAME opcode**, `hi12 = 0xC64`, with immediates `0x5A2` and `0x6A2` and `lo12`
  `0x000`/`0x007`. B §6.6 and A both describe these as *"a class-5 / class-6 twin"*; **that twin is
  an artifact of reading `class4` as a class inside the escape family.** The real difference between
  the two per-unit words is bits [11:8] of a 12-bit immediate, 5 vs 6. **Correction, MEASURED.**
* The disassembler still fires `hi == 0xC40 → envelope detector` above its own C-format rule, so it
  mislabels all 13 kernel C-words including both output-stage slots. B recommended demoting it; that
  is still not applied and it should be (one-line reorder in `dsp_disasm.py::annotate()` and
  `upd6383d.cpp::annotate()`).

### 1.3 "the two patched words are written by firmware that computes a level from a UI parameter" (B §8) → **FALSIFIED**

This was the "cheapest high-value experiment" both B and C pointed at. It was run (§6.C) and it
came back **negative in a way that is more useful than a positive would have been**:

> **MEASURED.** In the entire 192 KB `kn5000_subprogram_v142.rom` there are **exactly four** writes
> to I-RAM 64 / 71, and they are literal 5-byte constants at ROM `0x00F6CD`, `0x00F6D8` (set A) and
> `0x00F707`, `0x00F712` (set B), each immediately preceded by its I-RAM slot number (`01 00 40` /
> `01 00 47`) inside a canned uC-IF transfer script. **Nothing is computed. The output stage has
> exactly two states.**

So there is no level-computing writer to read. The question changes from *"what function does the
host evaluate"* to *"what binary condition selects script A or script B"* — which is a different,
still-static, still-cheap experiment (**K5-E1** below).

### 1.4 "`hi12`/`class4`/`addr8` track the effect selection" (C §B4) → **FALSIFIED; it is a reload bracket**

C inferred that the patch words track *which* effect is selected. The live capture says they track
the *reload event*. From `notes/data/kn5000_dsp1_upload_parametriceq.txt`, in stream order
(**MEASURED**):

```
   ... 64 ← C40.A.80.445 (B) ... 64 ← C40.5.40.445 (A) | upload unit-0 body @84 | 17 coefficient pokes |
       64 ← C40.A.80.445 (B) ... 64 ← C40.5.40.445 (A) | upload unit-0 body @84 | ...
```

Set **A** is written immediately **before** every unit-0 body upload; set **B** after the
coefficients are in place. Two values, alternating, across many different effect selections. Three
consequences, all load-bearing:

1. **The DSP-side output level is a constant.** It does not vary with the effect, and it does not
   vary with the user's DSP-depth control. **Therefore the depth control acts somewhere else** —
   inside IC303's return mix, or in the C-RAM coefficients. This sharpens A's open item **O-4** into
   a falsifiable statement and tells the O-4 experiment where *not* to look.
2. The bracket shape is exactly what a **mute / restore around a program swap** looks like, which is
   ordinary engineering: you do not want the tail of the old program running while its code is being
   overwritten word by word.
3. Per slot the two constants are an **exact left shift** in bits [24:12]: slot 64 `0x0540 → 0x0A80`
   (×2), slot 71 `0x0640 → 0x1900` (×4). The second needs `hi12` bit 0 to be part of the immediate,
   i.e. the field spans **[24:12]**, 13 bits. Two independent slots both landing on an exact power of
   two is not what an arbitrary pair of constants does. **INFERRED (moderate, n = 2): the immediate
   is a linear level and A is the reduced one.** Decisive tests in **K5**.

### 1.5 Frame timing — A's `Fs-RST` correction → **accepted**

Pins 13 (`Fs-RST`) and 14 (`Fs-MASK`) are both strapped to +5D, i.e. inactive; the per-frame PC
restart is the chip's **internal PC-RST** off the TIMING block, cadenced by **LRCKI**, which IC303
generates (p.35, and the CDJ-500 block diagram p.1-15). The substance — one PC sweep per sample, no
software loop — is unchanged and strengthened, because the inhibit is strapped off too.
`instruction-set.md`'s "Control flow" wording should be fixed.

### 1.6 The `880.1.60/20` "bracket" → **B's falsification accepted**

Per frame the counts are 16 vs 18 (through), 14 vs 20 (chorus), 13 vs 16 (EQ) — a bracket must
balance over a cyclic frame and these never do. What survives is `addr8 ∈ {0x20,0x30,0x60}` selecting
among a few DRAM operations with the real operand in `lo12`. Inside the reverb they still alternate
strictly, so a *sequence* reading (address phase / data phase) is live; a *nesting* reading is dead.

### 1.7 "`run_frame()` reuses the existing dispatch loop" (A §5.2) vs "the core stops at I-RAM 49" (C §4.2) → **both right, and the plan must change**

A's change set says to reuse `execute_run()`'s decode/dispatch loop. C read the code and found that
the loop ends the frame on **any** `is_end && class4 == 1 && addr8 ∈ {0E,0F}` word
(`upd6383.cpp:554-557` sets `ending`, `:581-586` sets `m_frame_done` / `m_icount = 0`) — and
`-headerdecode.md` §2.1 **PROVED BY CONSTRUCTION** that I-RAM 49 is a **CALL**. Verified by reading
those exact lines today. **So reusing the loop unchanged reproduces a known-wrong halt at word 49
and no body ever runs.** The wiring plan below therefore folds the minimum of **K1** into the
plumbing: not a decode of the word, but a measured call/return *sequencer*.

### 1.8 Sample rate, 44,100 vs 48,000 (A, O-1) → **44,100 is the better-supported figure**

A reports IC303's crystal as `36.8688 MHz`, which divides to neither rate, and calls it unresolved.
A point A did not make, which moves the balance: **`36.8688 MHz` is not a stock crystal value, and
`33.8688 MHz` is** — it is the canonical 768 × 44,100 audio crystal, and it shares the digit string
`8688` exactly. `36.864 MHz` (768 × 48,000) is the other stock value and does *not* share it. A
first-digit 3→6 misread on a 1996 scan is a far more economical explanation than a non-existent part.
Combined with the firmware's direct `ms × 0xAC44 / 0x3E8` (= ×44100/1000) conversion, **INFERRED
(strong): the DSP frame rate is 44,100 Hz.** Still worth Felipe reading X301's marking — his
testimony outranks both the scan and this argument.

This does **not** block the plumbing (the frame is driven by whatever rate the tone-generator stream
runs at) but it does mean MAME's 48,000 Hz tone-generator stream (`kn5000_tonegen.cpp:76`) makes
every delay and reverb time come out **8.8 % short**. Flagged, not changed — changing the stream rate
touches the shipped audio path and the envelope-rate maths at `:710`.

---

## 2. THE WIRING PLAN — the minimal, safe change set

### 2.1 Who owns the frame

The topology is a **cycle**: IC303 → IC311 → IC303 (A §1, §2, MEASURED). IC311 is a **send/return
insert on the tone generator**, not an output-path device: the main mix leaves IC303 on `SDO0`,
goes through IC310 (MN19413) and only that reaches the DAC. MAME's stream graph cannot express a
cycle without a delay element, so the **tone generator owns the call** (A's option C): one DSP frame
per output sample, called from inside `kn5000_tonegen_device::sound_stream_update()`. That is not a
shortcut — IC303 generates LRCK, so IC311's frame *is* IC303's word clock, and `run_frame(3 stereo
in, 3 stereo out)` is literally the DI1..DI3 / DO1..DO3 pins over one LRCK period. It satisfies the
chip-boundary rule: no device reads another device's RAM.

### 2.2 File by file

**`src/devices/cpu/upd6383/upd6383.h` / `.cpp`**

1. Six input and six output audio latches as device state, named for the pins and the CDJ-500 block
   diagram's registers: `m_di[3][2]`, `m_do[3][2]` (24-bit signed), `save_item()`-ed.
2. `void run_frame(const s32 (&di)[3][2], s32 (&do_)[3][2]);` — one LRCK period: latch DI, `m_pc = 0`,
   run slots, present DO.
3. **The frame must NOT reset the register file.** Only the PC restarts. Evidence (MEASURED
   positions, INFERRED consequence): the first load in the frame that *can* set an 8-bit D-RAM
   pointer is at **I-RAM 42** (`801.0.70.821`) — the five earlier loads at 15/22/29/31/40 are
   C-format words carrying 12-bit immediates of 448..1201, far too large for a 256-cell pointer, so
   they address a different register class. Words 0..41 — including the whole input stage at
   0..11 — therefore run on a pointer left behind by the *previous* frame's epilogue (whose last
   loads are I-RAM 62 `825←$26`, 69 `821←$90`, 77 `822←$86`). A `run_frame()` that zeroes `m_dp`,
   `m_cursor` or `m_acc` per frame would break the machine's own state threading.
4. **Do not reuse `execute_run()`'s `ending` halt** (§1.7). `run_frame()` needs the call/return
   sequencer of **K1**: a 2-entry stack; a unit-tagged word with an empty stack **calls** (tag
   `0x0E`→84, `0x0F`→200 — the observed entry table, labelled as observed, not derived); with a
   non-empty stack it **returns**. Frame ends on the word at I-RAM 82 **or** a 384-slot cap. Both:
   the cap alone masks decode errors, the wait word alone hangs on a program that never reaches it.
5. Counters, exposed: slots executed, traps, frames ended on the cap rather than the wait word.
   `execute_run()` and `set_disable()` stay exactly as they are — under this design the device never
   needs scheduler time.

**`src/mame/matsushita/kn5000_tonegen.h` / `.cpp`**

6. A device handle to the DSP plus `bool m_dsp_enabled`.
7. In `sound_stream_update()` (`:1763`), per sample, **before** `stream.put()` (`:2033-2034`): build
   the three stereo sends, call `run_frame()`, `+=` the returns into `mix_l`/`mix_r`, then the
   existing `softclip()`. **The dry `mix_l`/`mix_r` computation is not touched.**
8. Send levels are **not established** (A §5.3, and §1.4 above narrows where to look). Interim:
   full stereo mix to all three sends at unity, `// PLACEHOLDER` — faithful *mechanism*, stand-in
   *level*, drop-in-replaceable, exactly as `fake-with-the-real-mechanism` prescribes.

**`src/mame/matsushita/kn5000.cpp`**

9. `PORT_CONFNAME` "Effects DSP IC311 (EXPERIMENTAL — incomplete ISA)", **default Off**.
10. Wire tonegen↔DSP next to `KN5000_TONEGEN(config, m_tonegen, 0)` (`:1151`). Leave
    `m_dsp1->set_disable()` (`:1147`) and the speaker routes (`:1152-1153`) **unchanged**.
11. Update the `dsp1_delay_map` comment (`:587-614`) with A's measured facts — only `DSP1A0..A8`
    reach IC309, pins 55..62 (`A9`..`A16`) carry no net, `MD1..MD4 = 0b1111`, so the open question is
    "8 or 9 column bits" — and **do not change the map bounds**.

### 2.3 The safety property

> **The tone generator's dry mix never passes through IC311. The DSP can only ADD.**

Guaranteed three times: **by the hardware** (the main mix leaves IC303 on `SDO0`, a bus IC311 is not
on; the sends are copies — MEASURED); **by the code** (the mix is untouched and the return is a `+=`
after it, so a `run_frame()` that returns zeros leaves the output bit-identical); **by the gate**
(default Off ⇒ `run_frame()` is not called at all). Plus: **discard a frame's return entirely if any
word trapped** — a partially-executed frame is not "a bit wrong", it is arbitrary.

Declare the known approximation: a real *insert* effect (distortion, compressor) presumably has its
dry part removed inside IC303, so with the gate On such a part will be heard dry **plus** wet until
§1.4/O-4 is solved.

### 2.4 What would come out TODAY if we enabled it — **digital silence, and that is a problem**

Not garbage. **Exactly zero, and provably so.** Three stages of "enable it anyway", each checked
against the code and the trace:

| if we enabled… | what executes | what reaches DO | why |
|---|---|---|---|
| the core as written | I-RAM 0..49 — **50 words, 48 of which trap**, 2 `ldptr` apply — then `m_frame_done` at word 49 | **nothing** | `upd6383.cpp:554-557,581-586`; I-RAM 49 is a CALL (§1.7) |
| + the K1 sequencer | the full 265/286-word frame; **29/30 words do anything** | **nothing** | no decoded word touches DI/DO, the delay DRAM, the stack, a flag or Fs (C §1 — PROVEN BY CONSTRUCTION from the six forms) |
| + a guessed input/output cell | the reverb runs on real input, **26 of its 133 words** | a few coefficient multiplies of the input; the tank never accumulates because every DRAM word traps | reverb decode 19.5 %, all nine all-pass sections' DRAM words undecoded |

The reason it is silence rather than noise is structural and worth stating plainly: **`trap()`
changes no state** (`upd6383.cpp:503-518` — two counters and a log line, then `continue` at `:587`),
so an undecoded word is a no-op, and
**every** path from a sample to the DO latches is undecoded. The partial decode fails *safe*.

**The consequence for the roadmap is the important part: listening is not a usable feedback signal
until K1, K6 and K5 are all done.** Until then the only criteria that can fail are non-audio ones —
the trap histogram, PC-sequence assertions, and C-RAM/D-RAM address assertions. Any staged plan that
proposes to "enable it and hear whether it improves" has no measurement in it. (Standing rule:
*prove the instrument can SEE the failure before reporting its absence*.)

### 2.5 Order of work

1. **Plumbing first** (§2.2 steps 1-5, 6-11) — inert, gate Off, cannot regress anything, and it makes
   every later decode testable the moment it lands.
2. **K1 + K2** — the frame *sequence*. Verifiable with **no audio at all**: assert the PC visits
   0..49, 84.., 50..59, 200..332, 60..82 and repeats at the stream rate.
3. **K3 + K4 + K7** — the *addresses*. Verifiable against the MEASURED C-RAM map: after one frame,
   the coefficients the reverb read must be the ones the host wrote at 0x90...
4. **K5 + K6** — the audio boundary. First point at which sound is possible; gate it on a spectral
   A/B against a real recording (§5, H2), not on "it makes a noise".
5. **R1..R4** — make the reverb *right*.

---

## 3. THE EXECUTION PICTURE

Every word on the path executes **exactly once** per frame: the PC is restarted by the sample clock,
the bodies are hand-unrolled, two exhaustive branch-field scans are negative, and the cycle budget
(25 MHz / 44.1 kHz = **567 cycles** for 216-326 words = 1.74-2.21 cycles/word) leaves no room for a
loop of consequence. (Caveat: `LC1-LC3` exist on the pin table; if one of the 125 undecoded families
is a repeat, these counts are lower bounds.)

### 3.1 The KERNEL alone — 83 words

| | |
|---|---|
| words per frame | **83** (header 0..59 = 60, epilogue 60..82 = 23) |
| distinct words | **79** |
| distinct `(hi12,class4,lo12)` families | **75** |
| decoded | **3** (**3.6 %**) — `ldptr #$70`, `ldptr #$50`, `ldptr #$90`, i.e. **one** instruction, three times |
| class census | `0`:11 `1`:15 `2`:19 `3`:1 `4`:2 `5`:2 `6`:1 `8`:2 `9`:5 `A`:23 `C`:1 `D`:1 |
| families absent from all 2974 body words | **65 of 75** |
| most frequent undecoded family within it | **3** occurrences |

Execution order, with the stages located (B §1, §5.1):

```
   PC := 0   (register file NOT reset -- sect. 2.2 step 3)
    0.. 11   INPUT STAGE, two blocks (0..6, 7..11), 12 words, 11/12 families unique to here
   12.. 41   LFO / mixes / five 12-bit-immediate loads (lo12=0x820: 448 658 786 1111 1201)
   42.. 48   unit-0 setup: ldptr #$70 | 0x827<-$6C | 0x825<-$25 | ... | 0xC64 imm 0x5A2
       49    400.1.0E.000        CALL unit 0   -> I-RAM 84.., RETURNs to 50
   50.. 58   unit-1 setup: ldptr #$50 | 0x827<-$64 | 0x825<-$25 | ... | 0xC64 imm 0x6A2
       59    400.1.0F.007        CALL unit 1   -> I-RAM 200.., RETURNs to 60
   60.. 72   per-unit return blocks; 64 and 71 are the ONLY words the host ever patches
   73.. 78   OUTPUT STAGE proper -- the machine's only class-C and class-D words
   79.. 81   final arithmetic, in ordinary BODY vocabulary
       82    C00.A.47.407        frame terminator
```

### 3.2 The KERNEL + the REVERB — 216 words, the floor of every frame

| | kernel | reverb | floor |
|---|---:|---:|---:|
| words per frame | 83 | 133 | **216** |
| distinct words | 79 | 49 | **127** |
| distinct families | 75 | 31 | **104** |
| decoded | 3 (3.6 %) | 26 (19.5 %) | **29 (13.4 %)** |

**MEASURED, new (§6.A): the kernel and the reverb share exactly ONE word — `880.1.20.2D5` — and two
families, `000.2.**.000` and `880.1.**.2D5`.** 127 = 79 + 49 − 1. The two halves of the floor are
almost disjoint vocabularies: the reverb is a tight loop-unrolled arithmetic kernel (133 words, 31
families, an 8-word motif repeated nine times), the kernel is wide non-repetitive control/IO
microcode (83 words, 75 families). **They need different instruments and this is why the roadmap
splits at exactly that seam.**

Adding the unit-0 through program (`NO OPERATION`, 49 words, loaded for 42 of the 91 valid effect
slots) gives the full **265-word** frame at **29/265 = 10.9 %** decoded. The corpus envelope is
**256 … 326** words. Traffic per through frame: 64 class-A coefficient multiplies, 73 cursor
fetches, 56 accumulator stores, 36 delay-DRAM words.

### 3.3 The output stage has exactly two states

**MEASURED, new (§6.C).** Only four writes to I-RAM 64/71 exist in the whole ROM:

| slot | set A (before a body upload) | set B (after the coefficients) | relation |
|---|---|---|---|
| 64 (unit 0, `lo12 = 0x445`) | `C40.5.40.445`, imm13 `0x0540` = 1344 | `C40.A.80.445`, imm13 `0x0A80` = 2688 | **× 2 exactly** |
| 71 (unit 1, `lo12 = 0x446`) | `C40.6.40.446`, imm13 `0x0640` = 1600 | `C41.9.00.446`, imm13 `0x1900` = 6400 | **× 4 exactly** |

`lo12` is invariant per slot while everything above it changes — the cleanest single piece of
evidence anywhere in the corpus for **"`lo12` names the destination/route"**, and it sits on the
output stage. Together with §1.1 (the two input blocks agree on `hi12`, never on `lo12`) and C §B10
(the three DETERMINED multiply forms differ from 618 undecoded class-A words **only** in `lo12`),
that makes **"`lo12` = route, `class4`/`hi12` = the operation"** the single most load-bearing
structural hypothesis on the path, now supported from three independent directions.

---

## 4. THE DECODING ROADMAP — kernel first, then reverb

Ranked by *what blocks audio*. Each item: **(a)** why it blocks, **(b)** what is already
constrained, **(c)** the experiment, and whether it is **STATIC** (ROM/corpus only),
**LIVE** (a MAME capture, available today), or **HARDWARE** (needs Felipe's KN5000).

### KERNEL

---

#### K1 — the unit-tagged transfer `xxx.1.{0E,0F}.xxx` (CALL / RETURN) — **TIER 0**

**(a)** Nothing executes without it. The core as written treats it as the end of the frame and stops
at I-RAM 49, before any body (§1.7).

**(b)** `class4 = 1`; `addr8` = the unit index (0x0E = unit 0, 0x0F = unit 1, **91/91**);
`hi12` bit 10 set, bit 11 clear; `lo12` free. Observed `hi12 = 0x400 | {000,028,024,020,02C,212,204,
202,104}` — an END bit riding on an ordinary microword, so the word still does its datapath work.
Header I-RAM 49 and 59 are the two CALLs (PROVEN BY CONSTRUCTION: the header loads `821/827/825`
twice, at 42-44 and 50-52, so a body must run and return between them); the last word of **38 of 38**
bodies is the RETURN. **Zero** occurrences anywhere else in 7108 words. The target is **not** in the
word (`addr8` is 8 bits, the entries are 84 and 200; two exhaustive bitfield scans negative). The
chip has a **2-level stack** — exactly deep enough.

**(c)** **STATIC + implementation decision.** This one does not need more evidence to *sequence*
correctly, only an honest label. Implement: 2-entry stack; tagged word + empty stack ⇒ call the
observed entry for that tag; tagged word + non-empty stack ⇒ return. Comment it as *"entry table
OBSERVED (0x0E→84, 0x0F→200), mechanism (2-entry vector vs host-loaded entry registers) UNKNOWN"*.
The residual question — which of the two mechanisms, and what `hi12 = 0x612` (= END | 0x212, i.e.
END **plus an accumulator store**, 5 occurrences) additionally does — is answered by **R2**.

---

#### K2 — the frame terminator `C00.A.47.407` @ I-RAM 82 — **TIER 0**

**(a)** No per-sample cadence; and under the C-format rule the word's own fields are ambiguous in a
way that shifts every C-RAM address after it.

**(b)** Position is the evidence: the last word of the frame, and the epilogue contains **no
end-of-block word at all** — a block that never ends is a block closed by hardware. ⚠ The published
argument *"`hi12 = 0xC00` occurs zero times in 2974 body words"* is true but does **not** single out
word 82: I-RAM 76 (`C00.9.84.000`) shares it. **New defect (B §6.4):** word 82 is simultaneously
C-format (⇒ `class4` is immediate data) and `class4 == 0xA` (⇒ advances the cursor). Words that are
both: **0 of 2974** body words, **2 of 265** frame words — I-RAM 64 as patched, and this one.

**(c)** **STATIC, and there is a discriminator nobody has used.** §6.D: if word 82 *does* post-
increment the pointer by `+0x47`, then the kernel's opening block lands on D-RAM `0xCC..0xD3` — and
the reverb's own terminator store lands on **`0xCD`**, inside that block, by a completely
independent chain (`ldptr #$50` plus 133 words of body arithmetic). If word 82 does *not* move the
pointer, the input block lands on `0x85` and the two chains have nothing to do with each other. **One
bit of behaviour, two independent computations, one shared landing zone.** Run the pointer walk both
ways over kernel+reverb+each of the 38 bodies and count how often the kernel's I/O block and the
bodies' first/last accesses coincide. Cheap, purely static, and it is a genuine predict-then-check.

---

#### K3 — the pointer-register file: which register each `lo12` load names — **TIER 1**

**(a)** Everything reads the wrong cells. The core models **one** pointer; the chip has six (CP, DP,
BP1, BP2, PR1, PR2) plus BNK-R.

**(b)** 11 pointer loads on the path, **3 decoded** (all `lo12 = 0x821`): header 15/22/29/31/40
(`Cxx.x.xx.820`, C-format, immediates 448-1201 — far too large for an 8-bit D-RAM pointer, so a
**different register class**, plausibly delay-DRAM bases), 42 `821←$70`, 43 `827←$6C`, 44 `825←$25`,
50 `821←$50`, 51 `827←$64`, 52 `825←$25`; epilogue 62 `825←$26`, 69 `821←$90`, 77 `822←$86`. All 11
occur **0 times** in 2974 body words. **★ The conflict C surfaced stands:** the *same* decoded form
`801.0.NN.821` sets **C-RAM coefficient destinations** in the host stream (EQ framing `00.821 /
1E.821 / 06.821 / 0C.821 / 12.821 / 18.821 / 90.821`, where 0x00/06/0C/12/18 are the EQ's five biquad
blocks and 0x1E = 30 their extent — MEASURED) **and** the header's per-unit `$70`/`$50` that the core
implements as the D-RAM pointer `m_dp` (`upd6383.cpp:603`).

**(c)** **STATIC — a scored search, specified precisely.** Extend `tools/kn5000_dsp_nextsteps.py`'s
walk to N registers: assign each load code `{820,821,822,825,827,839}` to one of ≤6 registers and
each memory-touching word to one of them, then **score by footprint compactness**. The objective
function is already calibrated by §6.D under the naive 1-register model: the reverb scores **14
distinct cells out of 256, ten of them contiguous at 0x52..0x61, anchored exactly on `ldptr #$50`**,
and CHORUS 16 — but `NO OPERATION` (13 cells split across 0x2B..0x3F **and** 0x70..0x7F), COMPRESSOR
(15 cells over 0x30..0xFA) and PARAMETRIC EQ (44 cells over 0x70..0xE2) do not. **The correct
assignment is the one that makes all five compact and anchored.** That is a small search with a
falsifiable objective and a known-good positive control. Secondary discriminator (C §B6): check
whether a `.825` or `.821` load ever carries a value inside the MEASURED state block
`{0x64,0x68,0x6C,0x70,0x74}` outside the header — if `.821` never does, `.821` is the *coefficient*
pointer and `m_dp` is assigned to the wrong register.

---

#### K4 — the missing cursor rebase / bank switch — **TIER 1**

**(a)** Every coefficient in every body is read at an unknown offset.

**(b)** MEASURED and mutually contradictory under the current rule: the cursor advances +1 per
`class4 == 0xA` word and is reset only by `rstcur`; the header executes **21 strict class-A words
before the unit-0 CALL** and contains **no `rstcur`**; the epilogue adds more; there is exactly
**one** `rstcur` in 2974 body words; yet every effect's coefficients are uploaded at C-RAM base
**0x00** (16/16 swept effects) and the reverb's bank base is **0x90**. Corroboration that the header
runs its own bank: (coefficients uploaded) − (cursor-fetching body words) is +1 in 18/38 images and
within −3..+9 in 35/38, **never near +23**. Candidates: **BNK-R** switched by the unit tag; or the
register-load family — note `809.0.00.839` at I-RAM **38**, immediately before the unit-0 call, with
`.839` occurring **twice in the entire tree**; and `801.0.90.821` at I-RAM **69**, whose immediate
`0x90` *is* the reverb bank base and which is byte-identical to the word the host uses to close every
coefficient upload.

**(c)** **STATIC, and it has a bit-exact target.** Do not guess the mechanism — *solve for it*. The
reverb's 33 class-A multiplies are named **33/33** against C-RAM 0x90..0xB0
(`dsp/algorithms/reverb.md`). So: for each candidate rebase rule (rebase at the CALL by unit tag;
rebase at `.839`; rebase at `.821`; several cursors), walk the frame and check that the reverb's
33 class-A words land on **exactly** the 33 named cells in the right order. That is a 33-constraint
test with a unique right answer, it costs an afternoon, and the data is already on disk. This is the
same shape of argument that decoded the biquad.

---

#### K5 — the OUTPUT STAGE, I-RAM 60..82 — **TIER 1**

**(a)** The only place a result can leave the chip. Without it, DO never changes and the output is
digital silence no matter what else is decoded (§2.4).

**(b)** I-RAM **79-81 are ordinary body vocabulary** (a bit-4 store and two multiply-family words) —
the final arithmetic. I-RAM **73-78 are kernel-only** and hold the machine's **only class-C and
class-D words** (`E30.C.00.404`, `A3C.D.9F.287`, both 0/2974). If a DO write is an instruction, it
is in 73..78. The two host-patched slots (64, 71) are **two-state constants** (§1.4, §3.3), with the
per-slot `lo12` invariant at `0x445` / `0x446` and the immediate an exact ×2 / ×4 pair.

**(c)** Three experiments, in cost order.

* **K5-E1 — STATIC, cheap, do this first.** The whole resident scaffolding is one contiguous canned
  uC-IF script blob in Sub CPU ROM: header words at `0x00F59B..0x00F6C6`, then **script A**
  (`0x00F6C7`), **script B** (`0x00F701`), then the epilogue block at `0x00F73B`, framed as
  `F0 <16-bit = 0x3002 + payload_len> <cmd> <addr16> <payload>` (verified on both blocks). Find the
  code that walks that blob and **what selects A over B**. Each script also writes three 24-bit
  values to the same three destinations — A: `03B16A 03CD42 03F156`, B: `00716A 026142 01E156` (the
  low byte is invariant per destination, the top 16 bits change). Naming the selector names the two
  states, and the ×2/×4 relation then either becomes a decode or dies. This is the method that
  decoded `ldptr` (`LABEL_0387E6`) and `nop` (`LABEL_038922`): no hardware, no datasheet, no
  running DSP.
* **K5-E2 — LIVE, available today.** Sweep the DSP-depth / reverb-depth UI parameter across its full
  range with the existing capture instrumentation and diff the uC-IF stream. §1.4 proves the answer
  is **not** in I-RAM 64/71, so this locates where the user's depth control actually goes — C-RAM
  coefficients, or a path into IC303. Settles A's **O-4**, which is the difference between "audio
  flows" and "audio flows at the right level".
* **K5-E3 — HARDWARE.** *Exact recording:* hold one sustained note with a **heavy reverb** patch,
  record LINE OUT at **96 kHz / 24-bit**, and while the note is still ringing press the button that
  changes the DSP effect. Prediction under §1.4: a brief step in the **wet** level (≈ −6 dB on unit 0,
  ≈ −12 dB on unit 1) lasting exactly as long as the microcode upload, then a step back. If the wet
  return instead goes fully silent, the immediate is not a linear level and the ×2/×4 relation is a
  coincidence — that is the falsification, and it is worth as much as the confirmation.

---

#### K6 — the AUDIO INPUT stage, I-RAM 0..11 — **TIER 1**

**(a)** Nothing downstream means anything until a sample enters.

**(b)** Twelve words, of which **11 of 12 families occur 0 times** in 2974 body words:

```
    0  092.2.01.20D      6  400.A.00.419   END       (block 1: 0..6)
    1  C0A.0.E0.000      7  090.A.01.1C8
    2  084.2.02.680      8  084.2.01.1C0
    3  012.2.FF.1CE      9  012.2.FF.1D5             (block 2: 7..11)
    4  204.2.02.1CE     10  282.A.01.417
    5  202.A.00.448     11  400.2.01.447   END
```

`addr8 = 0xFF` at 3 and 9 is the established signed −1; `addr8 == 0x03` never occurs, so the port
index is **not** in `addr8`. The two blocks agree on `hi12` in 3 of 5 slot pairs and **never** on
`lo12` — which, given §3.3, now reads as *two different routes*, i.e. **two of the three DI ports**
rather than an L/R pair (L/R is LRCK phase, i.e. hardware, not encoding). `202.A.00.448` shares
`hi12` **and** `class4` exactly with the DETERMINED `mac` and differs only in `lo12`.

**(c)** **STATIC first, then LIVE.** *Static:* run the K3 walk and ask where these 12 words write.
Under the single-pointer model plus K2's `+0x47`, they land on D-RAM `0xCC..0xD3` — an 8-cell block
that no unit's own state block touches, and into which the reverb's terminator stores (§6.D). If K3
confirms the register assignment, the input cells are **determined**, not guessed, and the plumbing
can then be closed honestly. *Prediction to check:* the third input (DI3) must be read somewhere, and
there are only two blocks — so either DI3 is unused by this microcode, or one of the class-9 words
(I-RAM 53, 63, 74, 76 or `2A7.9.05.1C3`) is the third read. Falsifiable against 83 words.
*Live:* none available — the host never patches these words, so there is nothing to differentially
capture. **This item cannot be settled by capture; it is static reasoning or hardware.**

---

#### K7 — bit-4 store and class-A cursor advance on undecoded words — **TIER 2, a decision not a decode**

Two MEASURED semantics the core deliberately withholds from undecoded words: `hi12` bit 4 =
`mem[ptr] ← acc` (`0x212 = 0x202 + bit4`, `0x092 = 0x082 + bit4`, absence control 0/410) and
`class4 == 0xA` consumes `coef[cursor++]`. On the live frame that is **65 of 65** bit-4 words and
**66 of 74** class-A words not acted on. The discipline (*"one bit of a 36-bit word is not a
decode"*) is right and it is also why the present core accidentally gets C-RAM base 0x00 right — it
never executes the header's class-A words. **Decide explicitly before any staged enable, and decide
it together with K4**, because turning the cursor advance on without the rebase makes every
coefficient address wrong at once.

---

### REVERB

The reverb is where the **method that already worked on this chip** applies directly: take an
algorithm known exactly and use it as a constraint system to force the meaning of the words that
implement it. The biquad was solved that way to **0.000e+00** error against the firmware's own
`tan(π f / 44100)` coefficient designer; `mac`, `mac.lb` and `mulst` were DETERMINED that way from a
19,674,720-point search.

---

#### R1 — the 8-word all-pass motif — **the highest-leverage decode in the machine**

**(a)** Nine of the reverb's 133 words-groups are this motif; decoding it decodes ~72 of 133 words of
the one body that runs in **every frame of every effect**.

**(b)** The motif, byte-identical at all nine repetitions (I-RAM 219-226 and eight more):

```
   880.1.60.2D4      DRAM operation #1
   104.2.00.000      "all-pass marker", step UNKNOWN (MCC +0.881)
   000.2.00.419      annotated  y <- d_out - t
   012.2.00.680      annotated  d_in <- x + t     (hi12 bit 4 = store)
   880.1.20.655      DRAM operation #2
   102.A.00.64B      the gain multiply -- coefficient role known 100 %
   000.2.00.000      nop
   000.2.00.000      nop
```

Five of its eight words occur in exactly the 13 reverb programs and nowhere else in the 96-program
corpus. The **target function is known**: a Schroeder all-pass, `w = x + g·d ; y = d − g·w`, in two
ladders of five with **MEASURED descending gains** (ladder 0: 0.750 0.630 0.620 0.600 0.500) read off
C-RAM 0x98..0x9C / 0xA1..0xA4 at bank base 0x90, all 33 class-A coefficients named. The delay lengths
are **not** in the microcode — they are contiguous-tiled external-DRAM address pairs in the parameter
stream, a form that occurs in the 13 reverb slots and in none of the other 57 effects.

**(c)** **STATIC — a constraint search, the same machinery as `tools/kn5000_dsp_semantics.py`.**
Enumerate candidate micro-operations for the six unknown words over the chip's declared resources
(acc, P, latch A/B, `mem[p]`, the DRAM data register, the DRAM address register) and keep only the
assignments for which **all** of the following hold simultaneously:
1. nine repetitions realise the all-pass recursion with the nine MEASURED ladder gains, in order;
2. the DRAM addresses generated match the MEASURED contiguous tiling of the parameter stream;
3. the D-RAM footprint stays inside the reverb's own block (§6.D: `0x52..0x61`);
4. the 16-bit truncation of IC309 is respected (a delayed sample really is truncated — hardware,
   not a shortcut, and it constrains where the rounding step must sit).
Survivors are the decode. This simultaneously answers **R3**'s "does `880.1.20` latch address or
data", because a wrong choice breaks constraint 2.
**Optional HARDWARE ground truth (H2 in §5) turns this from "consistent" into "verified".**

---

#### R2 — the terminator store `612.1.0F.000` — where the unit's result goes

**(a)** If the reverb's result is written by its own terminator, that word *is* the unit-1 half of
the output path, and K5 only has to get it from D-RAM to DO.

**(b)** **New, MEASURED (§6.D):** `hi12 = 0x612 = END | 0x212`, and 0x212 has bit 4 set — so the
reverb's RETURN word **stores the accumulator**. It is the only terminator that does: of the nine
observed terminator `hi12` values (`400 428 424 420 42C 612 604 602 504`) exactly one, `0x612`, has
bit 4. Under the established single-pointer walk that store lands on **D-RAM 0xCD** — outside the
reverb's own `0x52..0x61` block, and inside the `0xCC..0xD3` block the kernel's input stage touches
under K2's reading. C §B1 lists `612` as the "FLAGGED unexplained case"; this is a concrete reading
of it.

**(c)** **STATIC.** Falsify or confirm with K3: if the register assignment survives the compactness
search and the store still lands in the kernel's block, the reverb's output cell is **determined**.
Cross-check: the reverb also stores at `0xDB` early (I-RAM 202, `212.A.81.1D5`, bit 4 set) — the only
other out-of-block touch. Two out-of-block cells, one written first and one written last, is exactly
the shape of an input/output pair. Check whether `0xDB` and `0xCD` are the unit-1 in/out cells by
asking whether the *unit-0* bodies show the same two-cell signature at their own offsets.

---

#### R3 — the `880.1.**` delay-DRAM words — 36 of every frame (13 %)

**(a)** The delay memory **is** the reverb/chorus/delay engine. Without it the tank cannot
accumulate and the reverb is a handful of multiplies.

**(b)** 231 occurrences over all 38 images; on the through frame `2D4`×9, `655`×9, `64B`×5, `2D5`×3,
`2DA`×3, `00B`×2, `2D9`×2, plus `000`/`40B`/`40E`. `addr8 ∈ {0x20,0x30,0x60}` selects among a few
operations, the operand is `lo12`, and the "bracket" reading is FALSIFIED as a bracket (§1.6) though
the strict alternation inside the reverb keeps an address-phase/data-phase reading alive. Hardware
bounds: IC309 is **×16**, so a delayed sample is truncated to 16 bits both ways; only `A0..A8` reach
it, `MD1..MD4 = 0b1111`, and 17-vs-18 address bits is open.

**(c)** **STATIC via R1** (constraint 2 forces it), then **HARDWARE** to pin the address width: see
H3.

---

#### R4 — the class-2 routing backbone inside the reverb

`000.2.**.419` (12), `012.2.**.680` (9), `202.2.**.407` (9), `000.2.**.40E` (3), `212.2.**.419`,
`202.2.**.1CD`. These move samples between D-RAM cells; the entire distinction is in `lo12`, which
has a MEASURED sub-boundary at `[11:8] ‖ [7:2]`. **`212.2.**.000` is the closest thing to a free
decode** anywhere: bit 4 gives `mem[p] ← acc`, `lo12 = 0x000` asks nothing further, 103 occurrences
over 32 images. **STATIC**, and mostly it falls out of R1.

---

### Explicitly NOT on this list

`212.2` vs `212.A`, the `lo12 = 0x415` group, and the table-lookup triple — items 1-3 of the
frequency-ranked worklist in `-core-draft.md` §6. They are frequent, real and *inside effect bodies*.
Decoding all three still yields **silence**, because nothing would get a sample into or out of the
chip. Likewise the LFO and the dynamics idioms: they change *what* you hear, not *whether*.

---

## 5. THE HONEST BOUNDARY

### 5.1 What cannot be determined from what we have

| | why | what would unlock it |
|---|---|---|
| **Which register each pointer code names** (K3) | six registers, one observable; the corpus never uses them independently enough to separate them | the datasheet; or the compactness search reaching a *unique* survivor (it may only narrow) |
| **The DI/DO instruction encoding** (K5/K6) | six candidate words, each occurring **once per frame** — the lowest possible frequency — in a 75-family vocabulary whose maximum multiplicity is **3**. Co-occurrence and frequency methods have literally nothing to bite on | the datasheet; a second independent microcode corpus (below); or hardware |
| **`COND` / predication** | the pin table says instructions can be conditional on RQ1-RQ3; no conditional encoding has ever been found. If a path word is predicated, "executes" ≠ "has an effect" | the datasheet |
| **Whether any word repeats** (`LC1-LC3` exist) | two exhaustive branch scans negative and a 1.74-2.21 cycles/word budget bound the damage, but do not exclude a short repeat | the datasheet; a PC trace |
| **Classes 8, 9, C, D** | 2, 5, 1 and 1 occurrences respectively, **all in the kernel**, and 0/2974 in bodies for 9/C/D | the datasheet; a second corpus |
| **17 vs 18 delay address bits** | `MD1..MD4 = 0b1111` is recorded, its encoding is not | H3, or the datasheet |
| **The sample rate** | firmware says 44,100; the scanned crystal value is not a real part (§1.8) | H4 |

**A PC trace is not obtainable from a KN5000 without board modification.** `SETRDY` (pin 100) is
"set to open in regular modes" and `BR-RQ` is strapped high, so the chip's emulator mode is disabled
on this board (A, O-7). This is useful *negative* information: `kn5000-dsp-necfamily.md` §6 asks for
a PC trace, and this is why one is not free.

**MAME cannot help until K1 + K5 + K6 are done**, because the failure mode of the partial decode is
silence, not divergence (§2.4). There is no gradient to descend.

### 5.2 What Felipe's hardware would settle — the exact recordings

Ordered by value. All at **LINE OUT**, **96 kHz / 24-bit**, effects at a **known, written-down**
parameter setting, and please note the exact effect name and depth value in the filename.

* **H1 — the reverb impulse response. THE single most valuable artifact.**
  `ROOM REVERB 1`, DSP depth at maximum, one short percussive note (or a staccato key press) with
  everything else silent, at least 6 seconds of tail, ideally 3 takes. *Settles:* the tank's tap
  times and gains, i.e. the ground truth the **R1** constraint system is solved against; the delay
  address width (**R3**, O-2) if any tap exceeds 131,072 samples; and the sample rate (**O-1**), since
  a known tap time in ms against a known tap length in words gives Fs directly. A second take with
  `PLATE REVERB 1` at the same depth isolates what the preset changes (coefficients only — the code
  is byte-identical).
* **H2 — the effect-change transient (K5-E3).** Sustained note, heavy reverb, change the DSP effect
  mid-note. *Settles:* what the two output-stage states are, and whether the ×2/×4 immediates are a
  linear level.
* **H3 — the maximum delay time.** A `SINGLE DELAY` (or `MULTI TAP DELAY`) with its time parameter at
  maximum, one click, measure the actual delay. *Settles:* 17 vs 18 delay address bits — if the
  longest achievable delay is ≈ 2.97 s the map is right at 17 bits; if it is ≈ 5.94 s it must be
  widened. Also directly cross-checks Fs.
* **H4 — read X301's marking** on the tone-generator board (§1.8). One photograph. *Settles:* 44,100
  vs 48,000, which scales every delay and reverb time in the emulation.
* **H5 — continuity check IC311 pins 55-62 against IC309** (A, O-2). Confirms A9..A16 are genuinely
  unconnected rather than a scan artifact.

### 5.3 What would unlock the rest

1. **The µPD6383 datasheet / NEC databook.** Still the highest-payoff single item; it would hand over
   the whole ISA. `kn5000-dsp-datasheet-hunt.md` records the search so far.
2. **A second, independent microcode corpus for the same chip.** The uPD6383GF appears as **IC302 in
   the Pioneer CDJ-500/CDJ-500G** — the only other documented user. A dump of that unit's firmware
   would contain a *different* kernel written by a *different* team against the *same* ISA. The
   intersection separates what is the instruction set from what is Technics idiom, and it attacks
   exactly the 65 kernel-only families that no KN5000-internal method can reach. **This has not been
   attempted and it is the most promising untried avenue after the datasheet.** (SPECULATIVE: it is
   not known whether the CDJ-500's DSP microcode lives in a dumped ROM.)
3. **The Sub CPU script interpreter** (K5-E1). Small, certain, and it is next.

---

## 6. NEW MEASUREMENT IN THIS PASS

Reproduce all of it with:

```
python3 tools/kn5000_dsp_nextsteps.py
   # defaults: notes/data/kn5000_dsp1_upload_coldboot.txt
   #           ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom
```

**A. Kernel and kernel+reverb census** (§3.1, §3.2). Kernel 83 words / 79 distinct / 75 families /
3 decoded (3.6 %). Reverb 133 / 49 / 31 / 26 (19.5 %). Floor 216 / 127 / 104 / 29 (13.4 %).
**They share exactly one word (`880.1.20.2D5`) and two families.**

**B. The 13 C-format words on the kernel**, with `imm12 = bits[23:12]` and `imm13 = bits[24:12]`.
New: I-RAM 48 and 56 are the **same opcode** `hi12 = 0xC64` with immediates `0x5A2` / `0x6A2` —
the "class-5 / class-6 twin" is an artifact (§1.2).

**C. Exhaustive Sub CPU ROM scan for writes to I-RAM 64 / 71.** Exactly four, all literal constants,
at ROM `0x00F6CD`, `0x00F6D8`, `0x00F707`, `0x00F712`; per slot an exact ×2 / ×4 pair in bits
[24:12]; live they bracket every unit-0 body reload (§1.3, §1.4, §3.3). Surrounding structure: the
resident header words occupy `0x00F59B..0x00F6C6` and the epilogue block starts at `0x00F73B`, all
framed as `F0 <16-bit = 0x3002 + payload_len> <cmd 01> <addr16> <payload>` (checked on both blocks).

**D. D-RAM pointer walk** under the established single-pointer post-increment rule, anchored at the
header's `ldptr`:

| body | entry `p` | accesses | distinct cells | span | last bit-4 store |
|---|---|---:|---:|---|---|
| **ROOM REVERB (unit 1)** | 0x52 | 100 | **14** | 0x52..0x61 (10 cells) + 0x9D..0x9F + 0xDB | **0xCD** |
| CHORUS | 0x70 | 45 | 16 | 0x6E..0x7E + 0xBB..0xBE + 0x5C | 0x7B |
| NO OPERATION | 0x70 | 40 | 13 | 0x2B..0x3F **and** 0x70..0x7F | 0x2B |
| COMPRESSOR | 0x70 | 35 | 15 | 0x30..0x3F + 0x70..0x7F + 0xEB..0xFA | 0x3C |
| PARAMETRIC EQ | 0x70 | 91 | 44 | 0x70..0xE2 | 0xE1 |

The reverb's footprint — 133 words touching **14 of 256 cells**, ten of them contiguous and anchored
exactly on the value the header loads — is the **first positive control of the addressing model over
a whole program**, and it is strong. CHORUS is nearly as good. The other three are not compact, which
is precisely the signal that **more than one pointer register is in play** (K3) — and it gives that
search a ready-made objective function with a calibrated positive control.

Also new here: the reverb's terminator stores the accumulator (only terminator that does) and under
this walk it lands on **0xCD**, in the block the kernel's input stage touches (K2, R2, §6.D note).

---

## 7. WHAT THIS PASS DID NOT GET

1. **No instruction was decoded.** Coverage is unchanged: 18.3 % corpus-with-roles, 9.0 % body
   vocabulary, **3.6 % on the kernel**, 13.4 % on the kernel+reverb floor. This is a plan and four
   new measurements, not a decode.
2. **The `imm13` reading of the output-stage level rests on n = 2.** Two slots, two values each, both
   exact powers of two. That is suggestive and it is *not* a result. K5-E3 is the falsification.
3. **The `0xCC..0xD3` I/O-block story rests on two unproven assumptions** — that `859.0.86.822` loads
   the working pointer, and that the frame terminator post-increments by `+0x47`. It is offered as
   K2's discriminator precisely because it is falsifiable, not because it is believed.
4. **The K5-E1 script interpreter was not read.** The blob's location, framing and the two scripts'
   contents are measured; the code that walks it and chooses between them is not yet found.
5. **The wiring plan is written, not implemented.** Nothing was built, nothing was enabled, no MAME
   process was run in this pass.
6. **A's §1.1 net list was not independently re-traced.** It was accepted on the strength of two
   agreeing drawings and a sourced 1200 dpi read; H5 is the cheap physical check.
