# K6 APPLIED — a sample now ENTERS the uPD6383GF (IC311)

**NEC uPD6383GF-3BA, Technics SX-KN5000 IC311, in MAME.** Date 2026-07-26.
Implements `notes/dsp-k6-input-stage.md` (commit `3688509`) in the MAME core.

The decode said *where* the incoming sample lands. This note is what happened when the core was
made to do it, and — more importantly — **how it was proved**, because "audio enters the chip" is
exactly the kind of claim this project has been burned by before.

Labels: **MEASURED** (a run of the emulator or a count over a file), **FORCED** (the only
assignment a stated rule admits), **INFERRED**, **EDUCATED GUESS**, **OPEN**.

---

## 0. HEADLINE

| | before | after |
|---|---:|---:|
| words EXECUTED before the first trap, per frame | **0 of 286** | **12** |
| words executed per frame (decoded + addressing-only) | 30 of 285 | **43 of 285** (15.1 %) |
| the first offender | `iw 0` `092.2.01.20D` | **`iw 12` `880.1.20.2D5`** |
| frames in which a sample reached the microcode | **0** | **925,809** |
| ... and the microcode read back exactly what was latched off DI | — | **925,809, MISMATCHED 0** |
| peak sample that entered and was consumed | — | **0x279100** (= the dry mix's own peak × 256) |
| audio with the gate **OFF** | — | **BIT-IDENTICAL**, 14,961,609 samples, **0 differing** |
| audio with the gate **ON** | dry | **still exactly dry** — 3,456,003 samples, 0 differing vs OFF |

**Nothing audible changed, and that is the design.** The twelve words' *addressing* is decoded;
their *ALU* is not, so the accumulator they leave behind is not the chip's, and every frame is
still discarded. What changed is that the machine is now **observable**: the first trap has moved
off word 0, so everything downstream is reachable for the first time.

---

## 1. WHAT WAS IMPLEMENTED

### 1.1 A THIRD word state, not a second

`src/devices/cpu/upd6383/upd6383d.{h,cpp}` now classifies a word three ways:

| state | predicate | what the device does | counted as |
|---|---|---|---|
| decoded | `decoded()` — the six established forms | full semantics | executed |
| **addressing-only** | **`addressing_only()` — the twelve K6 words** | **pointer walk + store enable + cursor fetch, NO ALU** | **PARTIAL** |
| unknown | everything else | nothing at all | TRAP (the worklist) |

Folding the new state into either of the others would have been wrong in a different way each
time: into `decoded` it would claim an arithmetic nobody has, into `trap` it would keep the chip
deaf. `PARTIAL` counts against a frame **exactly like a trap** — see §4.

**Matched by exact 36-bit WORD VALUE, never by I-RAM position.** MEASURED over
`kn5000-roms-disasm/dsp/disasm/*.dsm`: each of the twelve occurs exactly **once** in the 60-word
header and **zero** times in the 2974-word body corpus, with one deliberate exception — the
epilogue's `w79` is byte-identical to the header's `w3`. So the whitelist cannot reach a word the
decode did not cover, and it *does* reach `w79`, which is the K6 note's own frame-closure loop
(its §5). That is why **13** words go partial per frame, not 12 (§5, prediction P2).

### 1.2 The deposit — `latch_inputs_to_dram()`

Once per frame, **before I-RAM word 0**, because that is when the serial receivers do it: they do
not wait to see whether the microcode is interested.

```
    IC303 SDOA/SDOB/SDO1 -> DI1/DI2/DI3 pins -> m_di[port][ch]
                         -> D-RAM[X+2], D-RAM[X+5]          <- the K6 result
                         -> header w4 / w8 read them as ORDINARY MEMORY
```

`X` = the data pointer at PC-restart, **not** a constant: the register file threads across frames,
so the window moves with it and the deposit follows. Only the **offsets** are used, and they are
the FORCED part.

### 1.3 `exec_addressing_only()`

Three effects, all MEASURED elsewhere, none invented here:

```
    hi12 bit 4    ->  mem[ptr] <- ACC
    class4 bit 3  ->  cursor += 1
    addr8         ->  ptr += signed8(addr8)
```

and for the stage's one C-format word (`iw1`, `C0A.0.E0.000`) **nothing at all** — it has no
class4, no addr8, no memory operand and no cursor effect, so a SAFE NO-OP is the whole of it.
The ALU is untouched: `m_acc` is left exactly as it was.

**Declared consequence:** the stores therefore write an *arbitrary* accumulator into the cells
`X+0, X+1, X+3, X+4, X+6`. That is not swept under a rug — it is the reason the frame is
discarded, and §3.3's audit re-checks **every single frame** that no such store landed on an input
latch.

### 1.4 The disassembler

A new `~word` prefix (`?word` stays the worklist, untouched) plus an `{addr: …}` group showing
what the device really performs, and a per-word role string. **No mnemonic was invented** — naming
an operation nobody has decoded is precisely what that file refuses to do. Rendered by the real
MAME disassembler object via `tools/kn5000_dsp_dasm_harness.cpp`:

```
 0 ~word 0x009220120D ; 092.2.01.20D {addr: ST mem[p], p+1}  [K6 input stage, header w0: …]
 4 ~word 0x02042021CE ; 204.2.02.1CE {addr: rd mem[p], p+2}  [… *** THE PORT READ, block A *** …]
 5 ~word 0x0202A00448 ; 202.A.00.448 {addr: rd mem[p], cur+, p+0}  … ; C-RAM[0x00]
 8 ~word 0x00842011C0 ; 084.2.01.1C0 {addr: rd mem[p], p+1}  [… *** THE PORT READ, block B *** …]
```

The printed walk reproduces `dsp-k6-input-stage.md` §3's table word for word — an independent
re-derivation, since the C++ computes it from the bits rather than from the note.

---

## 2. THE PREDICT-THEN-CHECK SCORECARD

Written to `k6_predictions.txt` **before** the first ON-state run.

| # | prediction | measured | verdict |
|---|---|---|---|
| P1 | input stage stops trapping; 12 words execute before the first trap; the new first offender is `iw 12 = 880.1.20.2D5` | **12**, `iw 12 880.1.20.2D5` | **HIT, exact** |
| P2 | **13** partial words per frame, not 12, because `w79` is `w3`'s twin | last frame **13 partial** | **HIT, exact** |
| P3 | audit matched == audited, mismatched == 0 | **925,809 / 925,809 / 0** | **HIT, exact** |
| P4 | steady state `X = 0x8F`, deposit at D-RAM **0x91 / 0x94** | `X=8F -> D-RAM[91]/[94]` | **HIT, exact** |
| P5 | slots per frame unchanged at 285 | **285** | **HIT, exact** |
| P6 | frames kept = 0, so ON stays identical to OFF | 0 kept; 3,456,003 samples, 0 differing | **HIT** |
| P7 | OFF bit-identical to the published binary | 14,961,609 samples, **0 differing** | **HIT** |
| P8 | non-zero-input frames ≈ 8 % (a 2 s note in 24 s) | **98,590 of 925,809 = 10.65 %** | **HIT, approximate** (P8 was stated as "roughly") |

**No misses.** One thing did surprise the run and is recorded rather than smoothed over: see §3.4.

---

## 3. THE PROOF THAT A SAMPLE ENTERED — four independent legs

Harness: `run_wav.sh` in the session scratchpad (isolated pre-init `nvram2`, isolated
`cfg`/`snap`/`error.log`, visible window, `timeout`-wrapped, `-wavwrite` 3 ch @ 48 kHz, the gate
driven from Lua). Programme: `play_c4.lua` — one C4 held 20.0 → 22.0 s, 24 s total.

### 3.1 (a) The words no longer trap — MEASURED

```
    frames run          1104369
    frames with PARTIAL words (addressing executed, ALU unknown) 947889
    partial words executed, all frames 12025917
    last frame: 285 slots, 13 partial, 242 traps
    MOST RECENT REPRESENTATIVE FRAME: 285 slots, 13 partial, 242 traps.
    12 words EXECUTED before the first trap.
      0.  iw  12  08801202D5   880.1.20.2D5  [external-DRAM bracket CLOSE (INFERRED)]
```

`grep UNDECODED` over the whole log returns **zero** occurrences of any of the twelve words.
Before this change the same list began `0. iw 0 009220120D`.

### 3.2 (b) The value is real and non-zero while a note plays — MEASURED

The eight `LOG_INPUT` lines (budgeted, `INPUT_LOG_FRAMES = 8`, first non-silent frames):

```
IN frame 912280: X=8F  DI1 L=FFF800 R=000000 -> D-RAM[91]/[94]; microcode read back L=FFF800 R=000000  MATCH
IN frame 912281: X=8F  DI1 L=FFDB00 R=000000 -> D-RAM[91]/[94]; microcode read back L=FFDB00 R=000000  MATCH
… (8 lines, all MATCH)
```

### 3.3 (c) It landed where the microcode reads it — MEASURED, on every frame

The device audits itself. Not an assertion in a note: a **comparison** between the value latched
off the DI pins and the value the port-read words actually took out of D-RAM.

```
    INPUT-STAGE AUDIT (the two D-RAM cells at ptr+2 / ptr+5, read by header w4/w8):
        frames in which both port reads executed  925809
        ... value read back == value latched off DI1  925809   MISMATCHED 0
        ... of those, frames carrying a NON-ZERO sample  98590
        peak |sample| that entered and was read  0x279100 (2593024)
```

**An independent, whole-run cross-check against the AUDIBLE OUTPUT** (`wavcmp`-style analysis of
the same capture, python stdlib):

* the eight logged `DI1 L` values, converted back to 16-bit units, occur **exactly once** in the
  entire 24-second dry-output WAV — at sample **960,280 = t 20.0058 s**, 5.8 ms after the key
  press. Not "a similar waveform": the exact 8-sample sequence, unique in 1.15 M samples.
* the implied offset between the DSP's frame counter and the WAV is **exactly 48,000 samples =
  1.000 s**, which is exactly the `-autoboot_delay 1` at which the Lua script switches the gate
  on. Two clocks that were never fitted to each other agree to the sample.
* whole-run census: output samples with a non-silent stereo pair, from t = 1.0 s onwards =
  **98,590**. The core's independently-counted "frames carrying a NON-ZERO sample" = **98,590**.
  **Difference 0.** Every non-silent sample the instrument produced entered the chip.

`peak |sample| = 0x279100 = 2,593,024 = 10,129 × 256`, and 10,129 is the measured peak of WAV
ch1 — i.e. the send really is the finished dry mix at the FORCED 16→24-bit scale, not a stale or
invented buffer.

### 3.4 (d) THE AUDIT CAN FAIL — demonstrated, not argued

A criterion that cannot fail is not a pass. A build was made with **one line changed** — the
deposit aimed at `X+1 / X+4` instead of `X+2 / X+5` — and re-run on the identical programme:

```
    INPUT-STAGE AUDIT (the two D-RAM cells at ptr+1 / ptr+4, read by header w4/w8):
        frames in which both port reads executed  925809
        ... value read back == value latched off DI1  827219   MISMATCHED 98590
        peak |sample| that entered and was read  0x000000 (0)
        *** THE DEPOSIT AND THE READ DISAGREE -- the cell map is wrong ***
```

**98,590 mismatches — precisely, and only, the frames that carry a signal.** The 827,219
"matched" are the silent ones, where both sides are zero; the report shows that honestly rather
than hiding it in a percentage. So the audit discriminates right-from-one-cell-wrong on **100 %
of the frames where it could possibly matter**, and `peak entered = 0` says nothing real got in.
The wrong build was then reverted and the final binary rebuilt.

### 3.5 The ANOMALY, recorded rather than smoothed over

All eight logged frames show `R=000000` while `L` is non-zero. That looks like a broken right-hand
send. It is not: the WAV cross-check shows **ch2 is genuinely 0 at exactly those eight samples**
(the note's right channel starts a few samples later and is ~0.7 % quieter — peak 10,060 vs
10,129), so those `R=0` values are the tone generator's own output. Over the whole run the right
channel is non-zero in 98,296 samples and every one of them passed the audit.

---

## 4. SAFETY — unchanged, and re-measured on the committed binary

| check | result |
|---|---|
| `-validate kn5000` | **clean, exit 0, no output** |
| gate **OFF** vs the **reference** binary (parent of the audio-path commit), 3 programmes | **14,961,609 samples, 0 differing — BIT-IDENTICAL** |
| gate **OFF** vs the **currently published** binary, directly (`play_c4`) | **3,456,003 samples, 0 differing** |
| gate **ON** vs gate **OFF** (`play_c4`) | **3,456,003 samples, 0 differing** — the DSP contributes exactly zero |
| `clean` test | now `traps == 0 && partials == 0 && hit_wait && !overrun` — a PARTIAL word discards the frame like a trap |
| 384-slot cap | still fires: **162,240** frames |
| I-RAM overrun guard | still fires: **26,880** frames |
| hang | none; every run exited on its own, `error.log` 140–197 KB (no runaway logging) |

The OFF path is untouched by construction — `dsp_on` gates `run_frame()` in the tone generator and
nothing outside `upd6383*` changed except one log string — but it was measured anyway, twice: once
against the parent-commit reference and once directly against the published binary, so the claim
does not rest on a previous session's transitivity.

*Speed was **not** measured this session: two of the runs were executed in parallel, which
contaminates MAME's average-speed figure. The only clean single-run number is 61.39 % for the
published binary with the gate OFF. No cost claim is made.*

## 4a. Regression list, gate OFF — all pass (final binary)

| check | result |
|---|---|
| boots to the play screen | **yes** — `PMEM: 1-`, `16 Beat 1`, ♩=120, RIGHT1 Piano / RIGHT2 Bigband Brass / LEFT Modern E.P.1 |
| held note | peak rms **2536**, still **380.7** at release (−16.5 dB), floor 0.0. The analyser prints `SUSTAIN: NO` against its 25 %-of-peak rule; the default patch is **Piano**, so a −16.5 dB decay over 2 s is the patch. The criterion that *can* fail — "the voice is torn down early and reads 0" — does not fire. Identical to the recorded baseline |
| release decays monotonically | rms 256 → 18 → 0, **0 non-monotone steps** |
| chromatic | **12/12 detected**, monotone ascending, all distinct, max \|err\| **5.6 cents**, mean 3.0 |
| exact octave | C4 262.16 / C5 524.62 → ratio **2.0012** |
| chord C-E-G | all three present; weakest chord tone / strongest off-tone **13.4×**; **0 clipped** |
| 42 rapid notes | **42/42 sounded** |
| a fresh note after them | **yes**, peak rms **2309** |

Every number is identical to the pre-change baseline — as bit-identity requires. Velocity is still
not re-measurable through the emulated key bed (fixed `KEYBED_VELOCITY = 100`); it is covered by
construction by the bit-identity result.

---

## 5. WHAT THIS DOES **NOT** ESTABLISH

1. **The ALU.** All twelve words still have an OPEN `lo12`. The accumulator the input stage leaves
   is wrong even though every address is right. **This is now the single blocking unknown for
   audio**, and it is why the return is still discarded.
2. **The next hop.** `dsp-k6-input-stage.md` §6 established that the *bodies* read the cell written
   by the mix block's `w45`, not the input latch — the chain is
   `latch -> (mix block, I-RAM 12..41) -> w45 -> body entry`. This work proves the **first** hop
   (latch → the cell `w4`/`w8` read) and nothing beyond it. The mix block is entirely undecoded,
   starting at the new first offender `iw 12`.
3. **Which DI port.** `IN_PORT = 0` (DI1) is an **EDUCATED GUESS**; the latch→cell map is a chip
   property. It is currently *unobservable*, because the driver feeds the same dry pair to all
   three DI ports (G-3). *What would settle it:* an address-bus trace against real hardware, or
   the µPD6383 D-RAM memory map.
4. **Which latch is L and which is R.** `X+2 = L, X+5 = R` is the **EDUCATED GUESS** of
   `dsp-k6-input-stage.md` §4.2 reading (A) (channel-major, stride 3). Swapping them would not
   change any measurement in this note.
5. **The four input-stage coefficients** are values this project has never captured
   (`dsp-k6-input-stage.md` §9.2). The cursor now advances +4 per frame through them; what it
   reads is whatever the host left in C-RAM.
6. **The absolute origin.** `X = 0x8F` is INFERRED (it inherits `kn5000-dsp-addressing.md` §5's
   unresolved origin); everything structural here is origin-free and would hold at any `X`.

---

## 6. THE NEXT TARGET

```
    iw 12   880.1.20.2D5    external-DRAM bracket CLOSE (INFERRED)   <-- THE NEW FIRST OFFENDER
    iw 13   282.2.00.000
    iw 14   400.A.00.000    END OF BLOCK (falls through)
    iw 15   C0A.2.92.820    pointer-load family sibling
    iw 16   192.A.00.455  \
    iw 17   292.A.00.455   |  the MIX BLOCK, I-RAM 12..41
    iw 18   182.A.00.415  /
```

That is the block the K6 decode says carries the input stage's accumulator to `w45`, i.e. to the
cell the unit-0 body reads first (over-determined 37×). Decoding it is what would let the audit be
extended from "the sample reached the microcode" to "the sample reached the effect".

Second target, and the one that unmutes audio: the **`lo12` ALU field**. The kernel-only routes
`0x20D`, `0x448`, `0x417` (each 0× in 2974 body words) are named in `dsp-k6-input-stage.md` §10 as
the best handles.

---

## 7. TO SYNC INTO `kn5000-roms-disasm/dsp/` (nothing was edited there — concurrency rule)

1. `tools/dsp_disasm.py` — render class-2/A words with their pointer delta and store flag, as the
   MAME disassembler now does (`{addr: ST mem[p], p+1}`). The C++ renderer's output for I-RAM 0..11
   is in §1.4 and can be diffed against the python's.
2. `sym/kernel.sym` — `InCh0` (w0), `InCh1` (w7), `InLatchL` (w4), `InLatchR` (w8).
3. `instruction-set.md` — a third state exists now: "addressing decoded, ALU open". Worth naming,
   because the same situation will recur for every block decoded from here on.
4. `analysis/` — `dsp-k6-input-stage.md` plus this note's §3 (the audit and its falsification are
   reusable for every later stage: deposit, execute, compare, then deliberately break it).

---

## 8. REPRODUCTION

```bash
# build
cd kn7000_mame && ./build.sh          # returns 0 even on failure: grep the log for 'error:'

# gate ON, one C4, 24 s, WAV + error.log
run_wav.sh k6_on play_c4.lua 1
grep -A22 "FRAME REPORT" runs/k6_on/error.log     # the audit + the worklist
grep "IN frame"          runs/k6_on/error.log     # the 8 non-silent input frames

# bit-identity, gate OFF, three programmes
run_wav.sh off_c4 play_c4.lua 0 ; run_wav.sh off_pitch pitchtest.lua 0 ; run_wav.sh off_stress stress.lua 0
wavcmp.py "play_c4=runs/off_c4/out.wav=runs/ref_c4/out.wav" ...

# the falsification: flip IN_LATCH_L_OFF/IN_LATCH_R_OFF in upd6383.h from 2/5 to 1/4,
# rebuild, re-run -- MISMATCHED must become exactly the non-silent frame count.

# the disassembler rendering (build recipe at the top of the harness source)
g++ ... -o dasmharness tools/kn5000_dsp_dasm_harness.cpp .../upd6383d.o ... && ./dasmharness kernel60.bin
```
