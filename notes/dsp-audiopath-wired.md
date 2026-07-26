# uPD6383GF (IC311) — THE AUDIO PATH IS WIRED (experimental, default OFF)

**Date:** 2026-07-26. **Commit:** the change set of `notes/dsp-audiopath-wiring.md` §5.2 /
`notes/dsp-next-steps-roadmap.md` §2.2, implemented.

> ⚠ **ARCHIVAL TRACE — READ THE ANNOTATIONS, NOT THE LABELS** (banner added
> 2026-07-26 by the retraction sweep,
> `kn5000-roms-disasm/dsp/analysis/retraction-sweep.md`).
> The per-word listings in this file are a **verbatim record of what the
> disassembler printed on the day**, and several of the labels it printed have
> since been **withdrawn**. They are deliberately **not** rewritten: the wrong
> label *is* the evidence, and editing it would destroy the record of the bug.
> Withdrawn labels you will see below, with what replaced them:
>
> | printed here | status | replaced by |
> |---|---|---|
> | `envelope / level detector` (`hi12 == 0xC40`) | **FALSIFIED at all 61 sites** | a 13-bit C-format **immediate load** (`analysis/k5-output-stage.md` §2.3) |
> | `external-DRAM bracket OPEN / CLOSE` (`880.1.60/20`) | **FALSIFIED** | one is a **READ**, the other a **WRITE** (R1, FORCED — `analysis/r1-allpass-motif.md` §5) |
> | anything implying the D-RAM pointer origin `0x70` / `0x50` | **FALSIFIED** | `0x821` is a **C-RAM** pointer (K3, FORCED); the D-RAM origin is **OPEN** |
>
> The **word bytes, the slot order and the counts in this file are unaffected** and
> remain the measurement they always were.


This note says **what was built**, **every guess that was made and why**, and **what the option
actually does today** — which is *nothing audible*, exactly as `dsp-next-steps-roadmap.md` §2.4
predicted, and the useful output is the trap report at the end.

Labels used throughout: **MEASURED** (read off a schematic, a source file, or a run of the
emulator), **INFERRED** (forced by measured facts), **EDUCATED GUESS** (a defensible choice made
because no hardware is available — never a measurement).

---

## 0. HEADLINE

| | |
|---|---|
| what was wired | IC303 (tone generator) → `run_frame()` → IC303, one uPD6383GF frame per output sample |
| gate | `PORT_CONFNAME` **"Effects DSP IC311 (EXPERIMENTAL - incomplete ISA)"**, port `DSPCFG`, **default Off** |
| audio with the gate OFF | **BIT-IDENTICAL to the pre-change binary.** MEASURED, 3 captures, 14,961,609 samples, **0 differing** |
| audio with the gate ON | **BIT-IDENTICAL to the gate OFF.** MEASURED, 3,456,003 samples, **0 differing** — every frame traps, every return is discarded |
| frames run in a 24 s capture | **1,104,369**, of which **1,104,369 (100.00 %) trapped** |
| decoded fraction of a real frame | **30 of 285 slots (10.5 %)** — MEASURED live, and it matches `dsp-critical-path-coverage.md` §4.1's static prediction of *30 of 286* exactly |
| cost | emulation speed 78.3 % → 62.6 % with the gate ON (this machine, same capture) |

**The option is not an audio feature. It is a DECODING INSTRUMENT.** What it produces is §6: the
ranked list of words that block audio, measured on the microcode that is actually resident in a
running KN5000 rather than on a static corpus.

---

## 1. WHAT WAS IMPLEMENTED

### 1.1 `src/devices/cpu/upd6383/upd6383.{h,cpp}`

* **The six serial-audio latches** `m_di[3][2]` / `m_do[3][2]` — DI1..DI3 / DO1..DO3, L and R —
  as real device state, `save_item()`-ed. These are the `DI1L-R … DO3R-R` boxes on the CDJ-500
  block diagram (p. 1-15), so they belong to the chip.
* **`bool run_frame(const s32 (&di)[3][2], s32 (&do_)[3][2])`** — one LRCK period:
  1. latch DI1..DI3 (24-bit two's complement, sign-extended in `s32`);
  2. `m_pc = 0` **and only the PC** — the register file threads across frames on purpose (words
     0..41, including the whole input stage at 0..11, run on pointers left by the *previous*
     frame's epilogue; the first load that can set an 8-bit D-RAM pointer is at I-RAM 42);
  3. execute, reusing `execute_run()`'s decode/dispatch for the six decoded forms;
  4. present DO1..DO3.
* **THREE terminations, none redundant.**

  | termination | why it must exist | frames in the 24 s capture |
  |---|---|---:|
  | the frame-wait word `C00.A.47.407` | the real end of the frame | **915,249** (82.9 %) |
  | a hard **384-slot cap** | the wait word is itself undecoded; without a cap a mis-decode hangs MAME, and at boot I-RAM is all zeros so there *is* no wait word to reach | **162,240** (14.7 %) |
  | **I-RAM overrun** (PC ≥ word 384) | see §5, this was a real defect found by running it | **26,880** (2.4 %) |

* **The safety property:** a frame that trapped **any** word returns `false` *with `do_` already
  zeroed*, so an unchecked caller is still safe. A partially-executed effect frame is not "a bit
  wrong", it is arbitrary.
* **Counters and a report at `device_stop()`**: frames run / trapped / capped / overrun, and the
  first 48 offending words **in execution order** — §6.
* Per-word trap histogramming runs only in a **window of 256 frames after every I-RAM write**
  (a new microprogram is the only thing that can introduce an unseen word). Outside the window
  traps are still counted. Without this, a `std::map` lookup at 48 kHz × 285 words is a real cost.
* `execute_run()` and `set_disable()` are **untouched**. The device still gets no scheduler time.

### 1.2 `src/mame/matsushita/kn5000_tonegen.{h,cpp}`

* An `optional_device<upd6383_device>` handle and an `optional_ioport` gate, both set by the driver.
* In `sound_stream_update()`, **after** the dry mix is complete and **before** `stream.put()`:
  build the three stereo sends, call `run_frame()`, and **add** the returns.
  The dry `mix_l`/`mix_r` computation is **not touched**; the added term is a separate local that
  is a literal `0` whenever the gate is off.
* The gate is read **once per stream update**, not per sample, so it responds to the MAME menu
  without costing anything per sample.
* `device_stop()` reports frames sent / returns usable, and says plainly when every return was
  discarded.

### 1.3 `src/mame/matsushita/kn5000.cpp`

* `PORT_START("DSPCFG")` + `PORT_CONFNAME(0x01, 0x00, …)`, **default Off**.
* `m_tonegen->set_dsp1(m_dsp1)` and `set_dsp1_enable_port(":DSPCFG")` — the DSP is wired to the
  **tone generator**, not to a speaker, because that is where the board puts it. The speaker
  routes and `m_dsp1->set_disable()` are unchanged; **nothing new reaches the speakers**.
* `dsp1_delay_map()`'s comment now carries the MEASURED board facts (§4) and the map bounds are
  **unchanged**.

---

## 2. WHY THIS IS SAFE — and why that is not a choice we made

> **The tone generator's dry mix never passes through IC311. The DSP can only ADD.**

1. **By the hardware.** IC311 is a **send/return insert on IC303**, not an output-path device.
   MEASURED, service manual pp. 34/35 and BLOCK (A) p. 28:
   `IC303 SDOA/SDOB/SDO1 → IC311 DI1/DI2/DI3`, `IC311 DO1/DO2 → IC303 SDIA/SDIB`, while the
   **main mix leaves IC303 on SDO0** → IC310 (MN19413) → IC313 (PCM69AU) → the analog board.
   IC311 is not on that bus. The sends are *copies*.
2. **By the code.** `mix_l`/`mix_r` are finished before the DSP is called and the return is a
   separate accumulator added at the end. A `run_frame()` that returns zeros leaves the output
   bit-identical — and that is not a hope, it is §3's measurement.
3. **By the gate.** Default Off ⇒ `run_frame()` is not called at all.
4. **By the discard rule.** Any trap ⇒ the whole frame's return is zero.

**Known approximation, declared:** a real *insert*-type effect (distortion, compressor) presumably
has its dry part removed from the main mix **inside IC303**, which cannot be modelled until the
send levels of G-2 are found. So with the gate On and a working insert effect, the part would be
heard dry **plus** wet rather than wet only.

---

## 3. THE MEASUREMENTS

Harness: `run_wav.sh` in the session scratchpad — isolated pre-init `nvram2` copy, isolated
`cfg`/`snap`/`error.log`, visible window, `timeout`-wrapped, `-wavwrite` (3 ch, 48 kHz, audio on
ch1), the gate driven from Lua via `field.user_value`.

### 3.1 MUST-NOT-REGRESS, gate OFF — all pass

| check | result |
|---|---|
| `-validate kn5000` | **clean**, exit 0, no output |
| boots to the play screen | **yes** — `PMEM: 1-`, `16 Beat 1`, ♩=120, RIGHT1 Piano / RIGHT2 Bigband Brass / LEFT Modern E.P.1 |
| **bit-identical to the pre-change binary** | **YES**, three programmes, **0 differing samples of 14,961,609** (see 3.2) |
| held note sustains | **yes** — C4 held 20.0→22.0 s: peak rms 2536, still 380.7 rms at the moment of release (−16.5 dB), far above a 0.0 floor. (The default patch is **Piano**, so a −16.5 dB decay over 2 s is the patch, not a fault; the criterion that can fail is "the voice is torn down early and reads 0", and it does not.) |
| release decays monotonically | **yes** — post-key-off rms 256 → 18 → 0, **0 non-monotone steps** |
| pitch chromatic 12/12 | **12/12 detected**, monotone ascending, all distinct, max \|error\| **5.6 cents**, mean 3.0 |
| exact octave | C4 262.16 Hz / C5 524.62 Hz → ratio **2.0012** (want 2.0000) |
| chord C-E-G | all three tones present; weakest chord tone / strongest off-tone = **13.4×**; 0 clipped samples |
| 42 rapid notes | **42/42 sounded** |
| a fresh note after them | **yes**, peak rms 2309 |
| velocity direction | **NOT re-measured — and it cannot be, through the emulated key bed:** `kn5000.cpp` drives every ioport key press with a fixed `KEYBED_VELOCITY = 100`, so an ioport-driven test has no velocity axis at all. It is covered **by construction** by the bit-identity result: the rendering path is byte-for-byte unchanged, so every velocity behaviour with it. Varying it for real needs the MIDI→keybed bridge (`-kbdmidi`) or the touch-sensitivity sweep at sub-CPU `0x4A48`. |

### 3.2 The bit-identity result (the strongest of the lot)

Reference binary built from the parent commit's sources; identical run harness.

| programme | samples | new binary, gate OFF | new binary, gate ON |
|---|---:|---|---|
| `play_c4` — one held C4 | 3,456,003 | **BIT-IDENTICAL** | **BIT-IDENTICAL** |
| `pitchtest` — 12 chromatic + octave + chord | 5,716,803 | **BIT-IDENTICAL** | not run |
| `stress` — 42 rapid notes + a fresh note | 5,788,803 | **BIT-IDENTICAL** | not run |

That the **gate ON** column is also bit-identical is the point: it is the audible confirmation of
"every frame traps ⇒ every return is discarded ⇒ the DSP contributes exactly zero".

### 3.3 Cost

| | gate OFF | gate ON |
|---|---:|---:|
| MAME average speed, same 24 s capture, same machine | 78.26 % | 62.60 % |

---

## 4. THE DELAY MAP — comment updated, bounds NOT changed

MEASURED (service manual BLOCK (A) p. 28 and the schematic p. 35), now recorded in
`kn5000.cpp`:

* the IC311↔IC309 bus is **`DSP1A0-DSP1A8` and `DSP1D0-DSP1D15`** — **nine** address lines;
* IC311 pins **55..62 (`A9`..`A16`) carry no net at all**; the chip multiplexes row/column itself
  via its own RAS/CAS/WE (pins 43/44/45);
* **MD1..MD4 (pins 32..35) are all strapped to the VDD rail, = 0b1111** — the "external RAM type
  for digital delay and connection conditions" straps.

This **supersedes** the old comment's framing ("the bus is A0-A16, 17 lines, exactly half the
part"). The open question is now sharply **"8 or 9 column bits"**, i.e. 17 or 18 address bits, and
`MD1-MD4 = 0b1111` is the field that decides it — with no known encoding.

**Nothing was widened.** The driver map stays `0x00000-0x1ffff` and the device's `AS_DELAY` space
config stays 18 bits (that is the *part's* size). Both now carry a comment saying why. The wrap
point is what would silently corrupt every reverb tap length.

---

## 5. A DEFECT THIS WORK FOUND (and fixed)

**MEASURED, first run:** with the call/return sequencer, a frame whose body region has not been
uploaded yet — or whose "body" is zeros — walks the PC **straight off the end of the 384-word
I-RAM**. The first ON-state capture produced **3,440,640 "unmapped iram memory read" complaints
and a 213 MB log** in 24 emulated seconds.

What the real chip does with a PC past word 383 is **UNKNOWN** (wrap? stall until the next
PC-RST?). So the fix does **not** invent a wrap: `run_frame()` ends the frame, counts it as an
overrun, and discards the return like any other anomaly. Log: 213 MB → 171 KB. Speed: 47.4 % →
62.6 %.

*(A second thing looked like a defect and was not: the first frame report came out with its
heading missing. That was `stdout` and `stderr` being merged into one redirect, not a formatting
bug — MAME's `-log` `error.log` shows the report intact. Recorded so nobody "fixes" it again.)*

---

## 6. WHAT THE OPTION ACTUALLY PRODUCES TODAY — the worklist

### 6.1 It produces silence, and that was the prediction

`dsp-next-steps-roadmap.md` §2.4 predicted **digital silence, provably**, because `trap()` changes
no state and every path from a sample to the DO latches is undecoded. **CONFIRMED:** gate ON is
bit-identical to gate OFF over 3,456,003 samples.

### 6.2 PREDICT-THEN-CHECK — two hits, stated before they were run

| prediction | source | measured | verdict |
|---|---|---|---|
| the cold-boot frame is **60 + 70 + 23 + 133 = 286** slots | `dsp-critical-path-coverage.md` §2 | **285 slots + the frame-wait word = 286** | **HIT, exact** |
| **30 of 286** words are decoded-and-implementable (10.5 %) | `dsp-critical-path-coverage.md` §4.1 | 285 slots, **255 traps ⇒ 30 decoded** (10.5 %) | **HIT, exact** |

**How much do those two "hits" actually prove?  Less than they look — corrected 2026-07-26 after
an adversarial re-read.** Both the prediction and the measurement are sums over *the same five
regions* of *the same captured upload*, so they are largely a **self-consistency check**, not an
independent test:

* What the run **does** establish: the program resident in the live I-RAM at that moment really is
  the one the static analysis assumed — the unit-0 body's tagged terminator lands at 84+69, i.e.
  it is the **70-word CHORUS** and not the 49-word NO OPERATION — and no other word on the
  executed path accidentally matches the tagged pattern. That is worth having.
* What it **does not** establish: **G-5's mechanism.** "A straight-line PC would give 83" is true
  but it is not the competing hypothesis; *any* transfer mechanism that visits those five regions
  once each — a jump table, host-loaded entry registers, a different stack discipline — yields the
  same 286. The measurement cannot discriminate between them, so it must not be quoted as
  evidence that the call/return model is right.

It also confirms which unit-0 body is resident at cold boot (**70 words = CHORUS**, not the
49-word NO OPERATION).

Also visible in the worklist: **I-RAM 42 is absent from it**. That is `801.0.70.821` = `ldptr #$70`
— one of the three decoded words on the kernel path — so the decoded subset really is executing.

### 6.3 The first offending words, IN EXECUTION ORDER

The kernel traps on its **very first word** and on 47 of its first 48. This is the head of the
`device_stop()` report:

```
 0.  iw  0  009220120D   092.2.01.20D  hi12{ST f31=1 ?7 res=080}
 1.  iw  1  0C0A0E0000   C0A.0.E0.000  hi12{ESC f31=5 ?10 res=400}   [C-format: 12-bit immediate]
 2.  iw  2  0084202680   084.2.02.680  hi12{f31=2 ?7 res=080}
 3.  iw  3  00122FF1CE   012.2.FF.1CE  hi12{ST f31=1}
 4.  iw  4  02042021CE   204.2.02.1CE  hi12{f98=2 f31=2}
 5.  iw  5  0202A00448   202.A.00.448  hi12{f98=2 f31=1} cur+
 6.  iw  6  0400A00419   400.A.00.419  hi12{END} cur+
 7.  iw  7  0090A011C8   090.A.01.1C8  hi12{ST ?7 res=080} cur+
 8.  iw  8  00842011C0   084.2.01.1C0  hi12{f31=2 ?7 res=080}
 9.  iw  9  00122FF1D5   012.2.FF.1D5  hi12{ST f31=1}
10.  iw 10  0282A01417   282.A.01.417  hi12{f98=2 f31=1 ?7 res=080} cur+
11.  iw 11  0400201447   400.2.01.447  hi12{END}
...
42.  iw 43  080106C827   801.0.6C.827  [pointer-load sibling, target register UNKNOWN]
43.  iw 44  0801025825   801.0.25.825  [pointer-load sibling, target register UNKNOWN]
46.  iw 47  080080C000   800.8.0C.000  [class 8: post-sum step, OPERATION UNKNOWN]
47.  iw 48  0C645A2000   C64.5.A2.000  [C-format: 12-bit immediate]
```

**Words 0..11 are the AUDIO INPUT stage** (`dsp-critical-path-coverage.md` §B3, roadmap K6). All
twelve trap. Nothing enters the chip, which is the first reason there is no sound.

### 6.4 Ranked by how often they execute — the live census

169 distinct undecoded words were seen. Excluding the all-zero word of the pre-upload frames, the
top of the list is, in one number, **the reverb**:

| count | word | reading on record |
|---:|---|---|
| 34,816 | `880.1.60.2D4` | external-DRAM bracket OPEN (INFERRED) |
| 34,816 | `880.1.20.655` | external-DRAM bracket CLOSE (INFERRED) |
| 34,816 | `104.2.00.000` | all-pass marker — step UNKNOWN |
| 34,816 | `012.2.00.680` | all-pass: `d_in <- x + t` (the WRITE) |
| 34,816 | `000.2.00.419` | all-pass: `y <- d_out - t` (its partner) |
| 30,464 | `102.A.00.64B` | gain multiply (same op in the phaser all-pass and the reverb diffuser) |
| 11,520 | `880.1.60.2DA` / `880.1.20.64B` | second DRAM bracket pair |
| 11,520 | `212.A.00.415` / `212.2.00.419` | writes `mem[ptr]` (bit 4), class-independent |
| 10,240 | `C40.1.80.000` | envelope / level detector (INFERRED) |
| 8,960 | `202.2.00.407` , `012.2.FF.1CE` | — |

(Counts are within the sampled detail windows, so they are *relative*, not absolute.)

**This independently confirms the roadmap's ranking, from a live run rather than a static corpus
count:** the top five are exactly **R1** (the 8-word all-pass motif) and **R3** (the delay-DRAM
bracket words), and the roadmap called R1 "the highest-leverage decode in the machine".

### 6.5 So the worklist, unchanged in order but now measured

1. **K6 — the input stage, I-RAM 0..11.** 12 of 12 trap; the sample never enters. Nothing
   downstream can matter until this is decoded.
2. **K5 — the output stage, I-RAM 60..82.** Nothing can leave either.
3. **R1 — the all-pass motif** (5 of the 6 most-executed words in the machine).
4. **R3 — the `880.1.**` delay-DRAM bracket** (the other one).
5. **K3/K4 — the pointer file and the cursor rebase**, which decide *which cells* all of the above
   touch.

---

## 7. THE GUESSES — every one, with why / what would settle it / what changes if wrong

All five are marked in the source with the words **EDUCATED GUESS** and the same three fields.
None of them is a measurement and none may be quoted as one.

### G-1 — THE ABSOLUTE SAMPLE RATE. *(load-bearing)*

* **Decided:** exactly **one DSP frame per tone-generator output sample**.
* **Why:** correct **in kind** whatever the number is, because IC303 *generates* LRCKI (pin 208
  via R311; BCK on pin 207 via R312) and IC311's `Fs-RST`/`Fs-MASK` are strapped +5D = inactive
  (MEASURED, p. 35), so the DSP's frame rate **is** the tone generator's sample rate by
  construction.
* **UNRESOLVED — the number.** The sub-CPU firmware converts a user millisecond parameter with
  `ms × 0xAC44 / 0x3E8` = ×44100/1000 (`LABEL_03925E`), so the **firmware says 44,100 Hz**. MAME's
  tone generator allocates its stream at **48,000 Hz** (`kn5000_tonegen.cpp`, `device_start`, and
  `SAMPLE_RATE = 48000.0` in the EG-rate maths). IC303's crystal X301 reads **36.8688 MHz** on the
  1996 scan, which divides to **neither** (36.864 = 768 × 48 k and 33.8688 = 768 × 44.1 k are the
  two stock parts that would; `33.8688` shares the digit string `8688`).
* **What would settle it:** Felipe reading X301's marking off the board — his testimony outranks
  the scan and this argument — or locating IC303's LRCK divider.
* **What changes if it is wrong:** every delay and reverb time **in seconds**, and the
  interpretation scale of any frequency-domain coefficient, by 48000/44100 = **+8.8 %**.
  What does **not** change: the per-frame instruction budget (25 MHz / 44.1 kHz = 566.9 cycles for
  256..326 slots; at 48 kHz it is 520.8, still comfortable), the wiring, or any line of
  `run_frame()`.

### G-2 — THE SEND LEVELS ARE PLACEHOLDERS

* **Decided:** a **unity** stereo send of the finished dry mix.
* **Why:** the per-voice send levels are genuinely **not established**. They are **not** the
  per-voice registers `+0x8C0` / `+0x900..+0x9C0` — those were checked and are envelope-generator
  stage words written in `(seg0, seg1)` pairs — and the effect-depth controllers `CC 0x91/0x97/0x9B`
  never reach IC303 at all. Unity is the only level that adds no invented structure. The
  *mechanism* (a stereo send at LRCK rate, a stereo return added to the mix) is faithful and
  drop-in-replaceable; only the number is a stand-in.
* **What would settle it:** the **0x130000** register block — 4 channels × 8 registers, written by
  `DSP_Init_Channels` (sub-CPU `0x01FC95`) and `DSP_Write_Channel` (`0x01FCDE`), associated with
  IC311 but explicitly *not* its uC-IF. Tap it in MAME while moving the DSP EFFECT / REVERB depth
  sliders and diff — the same live-capture method that bound the parameter names.
* **What changes if it is wrong:** the **wet balance**, and the fact that today changing a part's
  DSP depth does not change the wet level at all. Falsifiable exactly that way.

### G-3 — WHICH DI/DO PORT EACH BLOCK SERVES

* **Decided:** feed the **same** dry stereo pair to all three wired inputs DI1/DI2/DI3, and sum
  the wired returns.
* **Why:** all three DI and all three DO are wired on this board (MEASURED), but which of the two
  opening blocks at I-RAM 0..11 reads which **port**, and which of the closing words at I-RAM
  73..78 writes which port, is not decoded. The port index is expected to be a small field in
  those 12 words and that field has not been located.
* **What would settle it:** resolving that field. The prediction on record is that it takes
  exactly **three** distinct values across those words — falsifiable against 12 words.
* **What changes if it is wrong:** which effect unit hears what. With one dry source feeding
  everything, a per-port routing error is currently **invisible**, which is itself a reason to
  treat any future "it sounds right" as weak evidence.

### G-4 — DO3 IS IGNORED

* **Decided:** sum **DO1 and DO2 only**.
* **Why:** DO1→SDIA and DO2→SDIB come back into IC303 and are part of its mix by construction
  (MEASURED). **DO3** (pin 25, R331) leaves the tone-generator block entirely on a long run
  heading out of the area; it is not the DAC (that is IC310) and it is not one of IC303's six
  serial ports (all six are accounted for). Adding an unknown-destination output into this mix
  would invent a route the board does not have.
* **What would settle it:** tracing that net. Candidates: the CN2/CN3 option-connector region
  (HD-AE5000 side), or a monitor/record tap.
* **What changes if it is wrong:** nothing audible here — DO3 would be a route to somewhere else
  on the machine, needing its own model.

### G-5 — THE CALL/RETURN SEQUENCER

* **Decided:** a word with the END bit (hi12 bit 10, bit 11 clear), `class4 == 1` and
  `addr8 ∈ {0x0E, 0x0F}` transfers control — it **CALLs** the tagged unit's body when the 2-entry
  stack is empty and **RETURNs** when it is not; entry table `0x0E → I-RAM 84`, `0x0F → I-RAM 200`.
* **Why:** without it the frame is a straight line 0..82 and the two effect **bodies never
  execute**, so the trap report — the whole value of the option today — would cover the kernel
  only. `dsp-next-steps-roadmap.md` §1.7 says the same thing and folds this into the plumbing.
  The *sequence* is PROVEN BY CONSTRUCTION: the header loads the same three pointer registers
  twice (I-RAM 42-44 `#$70/#$6C/#$25` and 50-52 `#$50/#$64/#$25`) and no body word in 2974
  contains a pointer load, so unit 0's body must run between 44 and 50; I-RAM 49 and 59 are the
  only tagged words in the header; the last word of 38 of 38 bodies is tagged; there are **zero**
  tagged words anywhere else in 7108 words; and the chip has exactly a two-level stack.
* **UNRESOLVED — the mechanism.** The entry addresses are **not in the word** (`addr8` is 8 bits
  and two exhaustive bitfield scans for 84/200 were negative), so they are either a hard-wired
  2-entry vector or host-loaded entry registers. **The table 0x0E→84 / 0x0F→200 is OBSERVED** — it
  is where the host puts the bodies in every captured upload — **not derived.** Also unresolved:
  what `hi12 = 0x612` (= END | 0x212, an accumulator store) does *in addition*, on its 5 words.
* **What would settle it:** an effect whose body the host loads somewhere other than 84/200, or
  the instruction set.
* **What changes if it is wrong:** the **PC order within the frame**, hence which words appear in
  the trap report and in what order. It cannot change the audio, because every frame is discarded.
  **It is NOT confirmed by the 286-slot measurement** — see §6.2: that number is a sum over the
  same five regions the guess assumes, and every rival transfer mechanism produces it too. G-5
  remains wholly unconfirmed.

### And one modelling choice that is not on the list, but should be visible

The **frame-wait word performs nothing**. It is class 0xA (which under the cursor rule would
advance the coefficient cursor) *and* C-format (which would make `class4` immediate data instead)
— an open contradiction. Rather than pick a side, the frame stops there and the word does no work.
That is a gap, not a decode.

---

## 8. WHAT THIS DOES *NOT* DO

* It does not decode a single new instruction.
* It does not make any sound. It cannot, until **K6** (input) and **K5** (output) are decoded —
  §6.5.
* It does not settle the sample rate, the delay-memory size, the send levels, the port indices or
  DO3.
* It does not change the shipped machine in any way: the option defaults Off and the OFF-state
  audio is bit-identical to before.

What it *does* do is make every future decode **testable the moment it lands**: decode one word,
turn the option on, and the report says whether the frame still traps and where. That is the whole
point of doing the plumbing first.

---

## 9. INDEPENDENT ADVERSARIAL RE-VERIFICATION (2026-07-26, second agent)

Everything below was re-measured **on the published binary** with a fresh harness, not taken from
§3. The reference binary (`kn7000_ref`, parent-commit sources, no `run_frame` symbol, no `DSPCFG`
port) was reused; the published binary is `md5 d4215394…` and matches
`kn7000_mame_build/kn7000`.

| what | measured | verdict |
|---|---|---|
| gate OFF vs **pre-change binary**, 3 programmes | c4 3,456,003 + pitch 5,716,803 + stress 5,788,803 = **14,961,609 samples, 0 differing** | **BIT-IDENTICAL — reproduced** |
| gate ON vs gate OFF, the **same** 3 programmes | **14,961,609 samples, 0 differing** (§3 had only run `play_c4` ON) | **BIT-IDENTICAL** |
| gate ON vs pre-change binary (`play_c4`) | 3,456,003 samples, 0 differing | BIT-IDENTICAL |
| `-validate kn5000` | exit 0, **zero output** | clean |
| boots to the play screen | `PMEM: 1-` / `16 Beat 1` / ♩=120 / Piano · Bigband Brass · Modern E.P.1 | yes |
| held C4, release | peak rms 2536.0, 380.7 at release (−16.5 dB), floor 0.0; release 256→18→0, **0** non-monotone steps | matches §3.1 exactly |
| chromatic / octave / chord | **12/12** ascending, \|err\| max **5.1** mean **4.1** cents; C4 262.39 / C5 524.05 → **1.9972**; triad 3/3, weakest-in/strongest-off **5.3×**, 0 clipped | pass (different estimator to §3.1, same conclusion) |
| 42 rapid notes + a fresh one | **42/42**, fresh-note peak rms 2309 | pass |
| **ON from the FIRST sample** (seeded `cfg`, not toggled at t=1) **plus 16 soft resets mid-run** | **1,152,001 frames sent = 24.00 s × 48 kHz exactly**, 0 usable, 914,880 wait-word + 210,241 cap + 26,880 overrun = 1,152,001; audio bit-identical to the same run with the gate off; exit 0 | **no hang, no crash, no leak** |
| the 384-slot cap really fires | 162,240 frames (toggled) / **210,241** (ON from boot) | yes |
| log volume is bounded | ON adds a **constant ≈58 KB** over OFF whether the run is 24 s or 40 s (198,655 B for both a 24 s and a 40 s capture); 169 first-sighting lines, one per distinct word | rate-limiting works |
| per-word histogram cost control works | **1,911,552** of **300,086,415** traps were histogrammed = **0.64 %** | the 256-frame window is real |
| cost | 2 instances in parallel, same load: OFF 57.05 / 56.85 %, ON 50.78 / 50.66 %; ON-from-boot 47.91 % vs 53.58 % → **≈11 % relative**, only when On | acceptable |

**Structural safety, re-derived from the source rather than from the runs:**

* `run_frame()` has **exactly one `return`** (upd6383.cpp:1016) and the zeroing loop above it runs
  on every path, so `do_` is never left uninitialised or stale.
* Every DSP-side pointer is **width-bounded**: `m_cursor`/`m_dp` are `u8`, so C-RAM/D-RAM stay
  inside their 256-word spaces; `m_pc` is guarded against the 384-word I-RAM; `m_sp` only ever
  indexes `m_stack[0]`. The external delay DRAM is **not touched at all** by `run_frame()`.
* **The DSP cannot influence the emulated machine.** `m_dsp1` is only ever *written*
  (`host_w`, kn5000.cpp:1111); there is no `host_r`, and `porth_read` — the DSP-ready line — is
  `set_constant(0x01)`. Nothing the core computes can reach the TLCS-900s.
* **Two labelling defects found and fixed** in this pass: `upd6383.h`'s FRAME LANDMARKS header
  called all of its constants MEASURED, which mislabelled the invented `FRAME_SLOT_CAP`; and §6.2
  oversold the 286-slot match as a check on G-5 (see the correction there).

**Nuance worth stating once:** with the gate off the dry mix is bit-identical *and always will
be*. Once a future decode makes a return non-zero, `softclip(mix + wet)` means the dry component's
rendering also changes — that is a shared saturating mix, which is what IC303 does, not a bypass
violation. "Bit-identical with the gate ON" is a property of *today's* all-trapping state, not a
promise.
