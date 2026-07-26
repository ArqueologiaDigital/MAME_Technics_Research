# uPD6383GF (IC311) — WIRING THE SOUND PATH

**Date:** 2026-07-26. **Task:** what must be modelled, at the board level, for audio to flow
through the KN5000's primary effects DSP — and what the minimal, safe MAME change set is.

This is the **hardware-side** companion to `notes/dsp-critical-path-coverage.md` (which ranks the
*instruction* decoding work by what blocks audio). That note asks "which words must be decoded";
this one asks "where does the sample come from, where does it go, and what clocks it". Read them
together: this note supplies the pin/net facts that note's §B3/§B4 were reasoning about without.

Everything below is labelled **MEASURED** (read directly off a schematic/pin table/source file),
**INFERRED** (a conclusion forced by measured facts), or **SPECULATIVE**. Primary sources:

* **KN5000 service manual**, `kn5000-docs/service_manual/technics_sx-kn5000.pdf`
  * PDF p.28 = manual **II-3/II-4**, "BLOCK (A) Diagram" — functional audio flow, thick line =
    *Tone Signal*, thin = *Control Signal* (the legend is printed on the page).
  * PDF p.29 = manual **II-5/II-6**, "BLOCK (B) Diagram" — the analog amplifier chain.
  * PDF p.34 = manual **II-15/II-16**, "TONE GENERATOR SECTION (A) P.C. Diagram" — IC303.
  * PDF p.35 = manual **II-17/II-18**, "TONE GENERATOR SECTION (B) P.C. Diagram" — IC310, IC311,
    IC313, IC308, IC309.
* **Pioneer CDJ-500/CDJ-500G service manual** RRV1087, `kn5000_project/pioneer_cdj-500_cdj-500g_rrv1087.pdf`
  pp. **1-15..1-17** — the uPD6383GF block diagram and 100-pin table (as IC302).
* The MAME tree: `src/mame/matsushita/kn5000.cpp`, `src/mame/matsushita/kn5000_tonegen.cpp`,
  `src/devices/cpu/upd6383/`.

---

## HEADLINE — three facts that change the plan

1. **IC311 is a SEND/RETURN INSERT on the tone generator, not an output-path device.** Its wet
   output goes *back into IC303*, which mixes it; the final stereo mix leaves IC303 on a
   *different* bus, goes through **IC310** (DSP2), and only then reaches the DAC. **MEASURED**
   (BLOCK (A), p.28; net-level on pp.34/35). Consequence: the dry sound can never be lost by a
   broken IC311 model — the safety property the task asks for is a property of the *hardware*,
   not a bypass we have to bolt on.

2. **All three serial audio inputs and all three outputs are wired on this board.** DI1←SDOA,
   DI2←SDOB, DI3←SDO1(TG), DO1→SDIA, DO2→SDIB, DO3→(leaves the block). **MEASURED.** This
   **falsifies** `dsp-critical-path-coverage.md` §B3's bound *"the chip has three serial input
   ports and this board uses one stereo pair"*, and it re-opens the reading of the two opening
   blocks at I-RAM 0..11: they need not be an L/R pair at all — they can be two different input
   ports, each of which is *already* stereo because LRCKI selects L/R on every DI line.

3. **`Fs-RST` is strapped INACTIVE on the KN5000.** Pin 13 (Fs-RST) and pin 14 (Fs-MASK) both go
   to **+5D**. **MEASURED** (p.35). Per the CDJ pin table those two pins are *emulator-mode
   overrides* — "pull up in regular modes". The per-frame program-counter reset the project has
   been attributing to "the Fs-RST / PC-RST pins" is therefore driven **entirely by the chip's
   internal `PC-RST`**, which the CDJ block diagram (p.1-15) draws coming out of the **TIMING**
   block. The cadence is set by the audio frame clock on **LRCKI**, which **IC303 generates**.

---

## 1. AUDIO IN — how the sample reaches IC311

### 1.1 The nets (MEASURED)

IC303 (TC183C230002, the tone generator LSI) carries six serial-audio pins on its left edge and
two more on its top edge — read off p.34, with the series damping resistors that identify the
driving end:

| IC303 pin | name | series R | net | goes to |
|---|---|---|---|---|
| 3 | **SDIA** (in) | — | `SDIA` | ← IC311 **DO1** (via R333 220 Ω) |
| 4 | **SDOA** (out) | **R308 470 Ω** | `SDOA` | → IC311 **DI1** (pin 20) |
| 5 | **SDIB** (in) | — | `SDIB` | ← IC311 **DO2** (via R332 220 Ω) |
| 6 | **SDOB** (out) | **R309 470 Ω** | `SDOB` | → IC311 **DI2** (pin 21) |
| 196 | **SDO0** (out) | **R314 470 Ω** | `SDO0` | → IC310 **SDI** (pin 6) |
| 197 | **SDO1** (out) | **R313 470 Ω** | `SDO1` | → IC311 **DI3** (pin 22) |
| 207 | **BCK** (out) | **R312 220 Ω** | `BCK` | → IC311 17 & 19, IC310 4, IC313 14 |
| 208 | **LRCK** (out) | **R311 220 Ω** | `LRCK` | → IC311 18, IC310 5, IC313 16 |

and IC311 (D6383GF-3BA on the silkscreen; = uPD6383GF-3BA), right-hand pin column, p.35:

```
   pin 30 TEST      -> GND
   pin 25 DO3       -> R331 220 -> (leaves the tone-generator block; see 2.3)
   pin 24 DO2       -> R332 220 -> SDIB  -> IC303 pin 5
   pin 23 DO1       -> R333 220 -> SDIA  -> IC303 pin 3
   pin 22 DI3       <- SDO1                <- IC303 pin 197
   pin 21 DI2       <- SDOB                <- IC303 pin 6
   pin 20 DI1       <- SDOA                <- IC303 pin 4
   pin 19 XFsI      <- BCK
   pin 18 LRCKI     <- LRCK
   pin 17 BCLKI     <- BCK
   pin 14 Fs-MASK   -> +5D      (PC-RST inhibit -- INACTIVE)
   pin 13 Fs-RST    -> +5D      (external PC reset -- INACTIVE)
   pin 11 BR-RQ     -> +5D      (break request -- INACTIVE)
   pin  8 RDY       -> R334 4.7k -> +5D  (open-drain, pulled up)
```

Cross-check: BLOCK (A) (p.28) draws exactly these six thick "Tone Signal" arrows on the bottom
edge of the IC311 block, in the order `DI3 DI1 DI2 DO1 DO2 DO3`, and the four that go to IC303
land on its `SDO1 / SDOA / SDOB / SDIA / SDIB` ports. Two independent drawings agree.

### 1.2 Not from the delay DRAM, not from a codec

The delay DRAM (IC309) is **private to IC311** — it is written and read only by the DSP's own
RAS/CAS/WE and is not on any audio path in or out (§4). There is no ADC anywhere near IC311:
the only analog input in this subsystem is the **microphone**, and it goes to **IC310**'s on-chip
stereo ADC (`AINL` pin 93, `AINR` pin 85, fed through IC312 and R329/R330 220 Ω), **not** to
IC311. **MEASURED**, p.35.

### 1.3 How many channels, and in what format

* The uPD6383GF has **three serial audio inputs DI1..DI3 and three serial outputs DO1..DO3**
  (CDJ pin table pins 20-22 / 23-25), and the block diagram (p.1-15) shows each of them landing
  in a **pair of 24-bit latches**: `DI1L-R / DI1R-R`, `DI2L-R / DI2R-R`, `DI3L-R / DI3R-R`, and
  symmetrically `DO1L-R / DO1R-R` … `DO3L-R / DO3R-R`. **Every DI/DO line is a stereo pair**,
  with L/R designated by **LRCKI** (pin 18: "Input of L/R channel designation signal for DI1 to
  DI3 input signals and DO1 to DO3 output signals"). **MEASURED.**
* So the KN5000 presents IC311 with **3 stereo sends (6 channels in) and takes 3 stereo returns
  (6 channels out)**. The internal bus is 24-bit (`IDB`, 24 lines to every latch on the block
  diagram), so the sample format inside the chip is **24-bit two's complement**; the coefficient
  format is signed **Q0.23** (established, `instruction-set.md`).
* Sample rate: **44,100 Hz** working figure — **MEASURED from the sub-CPU firmware**, which
  converts a user millisecond parameter into delay-line words with `ms × 0xAC44 / 0x3E8`
  (`LABEL_03925E`; `kn5000-dsp-parameters.md` §3). The chip imposes no rate: in slave mode it
  takes BCLKI/LRCKI from outside (CDJ pins 17-19), and here that outside is IC303.
  ⚠ **See §3.3 for an unresolved arithmetic problem with IC303's crystal.**

### 1.4 What this means for the "two opening blocks" reading

`dsp-critical-path-coverage.md` §B3 treats I-RAM 0..11 as a candidate INPUT stage and reports
(correctly) that the two blocks are *not* copies of one another with a channel index swapped. The
board now says why that is unsurprising: the natural reading of two structurally-similar,
lo12-different opening blocks is **two different input PORTS** (e.g. DI1 = unit-0 send, DI2 =
unit-1 send), each of which is intrinsically stereo. Under that reading the L/R split is *not*
encoded in the instruction stream at all — it is the LRCK phase, i.e. it is hardware, exactly as
the D-RAM/C-RAM space turned out to be pointer identity rather than an encoded field
(`kn5000-dsp-spaces.md`).

**Status: INFERRED, and it is a hypothesis, not a result.** But it is now a *testable* one, and it
is cheap: if I-RAM 0..11 reads two ports, then a third input read (DI3) must exist somewhere in
the frame, and there must be **three** output writes. §B4 already isolates I-RAM 73..78 as the
only place a DO write can live, and it contains the machine's only class-C and class-D words.
**Concrete prediction: the DI/DO port index is a small field in those scaffolding words, and it
takes three distinct values.** That prediction is falsifiable against 12 words.

---

## 2. AUDIO OUT — how IC311's result reaches the DAC

### 2.1 It does not reach the DAC directly (MEASURED)

```
  IC303 SDO0 ──470Ω──► IC310 SDI     (MN19413, DSP2, effect units 2..4, own 20 MHz X302)
  IC310 SDO1 ──470Ω──► IC313  D-A CONVERTER (PCM69AU)  ──► IC314B/IC314A ──► LOUT / ROUT
```

BLOCK (A) (p.28) shows one thick Tone-Signal arrow from **IC310's SDO1** into the **D-A CONVERTER**
block, and from the DAC into the two op-amps. On the schematic (p.35) IC313's serial inputs are
**DA-L (pin 17)** and **DA-R (pin 13)** — two separate data pins, one per channel — with
**WDCK (16) ← LRCK via R341 47 Ω**, **SYSCK (15) ← DACCK via R342 47 Ω**, **BCK (14) ← BCK via
R343 47 Ω**. IC310 has exactly two serial data outputs, `SDO1` (pin 8, through R326 470 Ω) and
`SDO2` (pin 7).

**INFERRED (strong): IC310 SDO1 → IC313 DA-L and IC310 SDO2 → IC313 DA-R** — the block diagram
puts IC310 on the DAC's input, the DAC needs two data lines, and IC310 has two. Not traced
net-for-net on the scan (the R326 run crosses three vertical bus lines in a region where the
1996 scan cannot resolve junction dots from crossings); flagged, not asserted.

### 2.2 So the signal chain, end to end

```
   keybed / MIDI
        │
        ▼
  ┌─────────────────────────── IC303  TONE GENERATOR LSI (TC183C230002) ───────────────────────┐
  │  64-voice PCM from IC304..IC307 → per-voice level/pan → the MIX                             │
  │                                                                                             │
  │   main mix ──► SDO0 ─┐         send A ──► SDOA ─┐        send B ──► SDOB ─┐   send ──► SDO1 │
  │      ▲               │                          │                        │             │   │
  │      │  return A ◄── SDIA ◄───┐  return B ◄── SDIB ◄───┐                 │             │   │
  └──────┼───────────────┼────────┼──────────────────┼─────┼─────────────────┼─────────────┼───┘
         │               │        │                  │     │                 │             │
         │               │        │  DO1              │  DO2│              DI1│          DI2│  DI3
         │               │     ┌──┴──────────────────┴──────┴─────────────────┴─────────────┴─┐
         │               │     │   IC311  uPD6383GF-3BA   effect units 0 and 1                │
         │               │     │   X303 25 MHz · I-RAM 384x36 · C/D-RAM 256x24 each           │
         │               │     │   IC309 M5M44260AJ-7S  4 Mbit delay DRAM (256K x 16)         │
         │               │     └───────────────── DO3 ──► (leaves the block, §2.3) ───────────┘
         │               │
         │               ▼
         │        ┌────────────────────────────────────────────┐
         │        │ IC310 MN19413  effect units 2..4           │ ◄── AINL/AINR: MIC via IC312
         │        │ X302 20 MHz · IC308 M5M418128AJ  1 Mbit    │
         │        └──── SDO1 / SDO2 ──────────────────────────┘
         │                    │
         │                    ▼
         │        ┌───────────────────────────┐
         │        │ IC313  PCM69AU  18-bit DAC│  DA-L / DA-R / WDCK / BCK / SYSCK
         │        └────── LOUT ── ROUT ───────┘
         │                    │
         │                    ▼   IC314B / IC314A  (M5218AFP)
         │            CN9 ──► amplifier board (BLOCK (B), p.29):
         │              MIXING AMP IC4A/IC4B  →  LOW PASS FILTER IC7A/IC7B
         │              →  EQUALIZING IC8A,10A,11A,12A / IC8B,10B,11B,12B
         │              →  IC14A/IC14B  →  CN8/CN1  →  SWA POWER AMPLIFIER  →  speakers
         │              (+ HEADPHONE AMP, LINE OUT, AUX IN, MIC amp IC15 — all ANALOG)
         └── LRCK (208, R311 220Ω) and BCK (207, R312 220Ω) fan out to IC311, IC310 and IC313
```

**There is no digital mixer between IC311 and IC313.** The only summing stages are (a) *inside
IC303*, where the two returns are mixed back into the main mix, and (b) the *analog* MIXING AMP
IC4A/IC4B on the amplifier board, which sums the DAC output with AUX IN and MIC. No board
designated "FAJ" appears anywhere in the KN5000 block diagrams; the analog chain is the one drawn
above. **MEASURED.**

### 2.3 DO3 — honest open item

IC311 **DO3** (pin 25) is connected: R331 220 Ω, and on BLOCK (A) it drops to a long Tone-Signal
run along the bottom of the diagram heading left, out of the tone-generator area. It is **not**
the DAC (that is IC310) and **not** an IC303 port (all six of those are accounted for). Candidates
not discriminated: the CN2/CN3 option connector region (HSG/HD-AE5000 side), or a monitor/record
tap. **OPEN.** It is not on the critical path for making effects audible.

### 2.4 Where the per-unit "effect-return / wet-level" words fit

`dsp-critical-path-coverage.md` §B4 identifies the only two words the host patches at runtime —
I-RAM **64** (`lo12=0x445`, unit tag `0x0E`) and I-RAM **71** (`lo12=0x446`, unit tag `0x0F`) —
sitting in the epilogue **after both bodies have run**. The board now gives that a physical
meaning that fits exactly:

* two host-patched, per-unit words, at the point where the frame's results are handed out,
* two hardware return buses (`DO1`→`SDIA`, `DO2`→`SDIB`), one per effect unit,
* two resident bodies (I-RAM 84 = unit 0, I-RAM 200 = unit 1),
* two unit tags `0x0E` / `0x0F` that split the same way in three unrelated mechanisms
  (`kn5000-dsp-header.md` §3).

**INFERRED (strong): I-RAM 64 and 71 are the wet-level / output-stage words for DO1 and DO2
respectively.** Note this is a *chip-internal* level; there is almost certainly a **second**
return level inside IC303 (the SDIA/SDIB mix gains) which is set over a different path and which
we have **not** located — see §7 open item O-4.

---

## 3. FRAME TIMING

### 3.1 What actually resets the PC (MEASURED, and a correction)

| pin | KN5000 strap | CDJ-500 pin table says | consequence |
|---|---|---|---|
| 13 `Fs-RST` | **+5D** | "Input of program counter reset signal. **Used in the emulator mode. Pull up in regular modes.**" | external PC reset is **not used** |
| 14 `Fs-MASK` | **+5D** | "Input of PC-RST inhibit signal. Used in the emulator mode. Pull up in regular modes." | internal PC-RST is **not inhibited** |
| 18 `LRCKI` | `LRCK` from IC303 pin 208 | L/R designation for DI1-3 and DO1-3 | the frame clock |
| 17 `BCLKI` | `BCK` from IC303 pin 207 | bit clock for DI1-3 and DO1-3 | |
| 19 `XFsI` | `BCK` | "Input for generating the bit clock in the slave mode" | **slave mode** |
| 38 `SEL` | **+5D** (VDD rail with pin 42) | High = XI/XO | crystal, not EOSC |
| 37 `EOSC` | **GND** | pull to GND when unused | consistent |
| 39/40 `XI`/`XO` | **X303 25 MHz** (R327 1 M, R328 47, C334/C335 10 pF) | | core clock |

**MEASURED**, p.35. The CDJ block diagram (p.1-15) draws `PC−RST` as an output of the **TIMING**
block (the block that also drives BCLKO/LRCKO/XFsO1/XFsO2 and takes SEL/EOSC/XI/XO), running to
the **PC**; `Fs-RST` (pin 13) enters the PC on a separate line.

**Correction to the standing project statement.** `instruction-set.md` ("Control flow") and
`kn5000-dsp-INDEX.md` say the PC restart comes from "the Fs-RST / PC-RST pins". On *this* board
`Fs-RST` is tied high and does nothing. The mechanism is **internal PC-RST, derived from the frame
clock the chip receives on LRCKI**. The *substance* of the claim (one PC sweep per sample, no
software loop) is unaffected and is if anything strengthened: the reset is unconditional, because
the KN5000 also strapped away the inhibit.

### 3.2 The budget

```
   core clock            25 MHz              (X303, MEASURED)
   frame rate            44,100 Hz           (firmware, MEASURED -- but see 3.3)
   cycles per frame      25e6 / 44100 = 566.9
   I-RAM                 384 words
   slots executed, cold boot   60 + 70 + 23 + 133 = 286   (dsp-critical-path-coverage.md §2)
   worst-case resident         60 + 23 + 110 + 133 = 326
```

So roughly **2 core cycles per instruction slot** are available, and the machine never fills
I-RAM. Consistent, with room for multi-cycle words. **MEASURED inputs, arithmetic INFERRED.**

### 3.3 ⚠ The crystal arithmetic does not close — an open item

IC303 runs from **X301, printed `36.8688 MHz`** on the schematic (p.34, R304 100, R305 1 M,
C305/C306 6 pF). Read at 1600 dpi the digits are legible but the scan is at the edge of its
resolution. The problem:

```
   36,868,800 = 2^6 x 3 x 5^2 x 7681     (7681 is prime)
   36,868,800 / 44,100 = 836.03...       not an integer
   36,868,800 / 48,000 = 768.10          not an integer
```

**Neither 44.1 nor 48 kHz divides it.** The nearest sane designed value is **36.864 MHz =
768 x 48,000 exactly** (36.8688 is 36.864 + 130 ppm). The nearest 44.1 kHz value is
**33.8688 MHz = 768 x 44,100 exactly**.

Against that, the firmware evidence for 44,100 is direct and hard to argue with (§1.3), and
`kn5000-dsp-parameters.md` §3.1 shows the resulting chorus/rotary tap times are the musically
correct ones at 44.1 kHz. Meanwhile **MAME's tone generator currently runs its stream at
48,000 Hz** (`kn5000_tonegen.cpp:76`, and `SAMPLE_RATE = 48000.0` at :710 in the envelope-rate
maths), and `kn5000-docs/tone-generator.md` quotes "Stereo 48 kHz".

**This is unresolved and it is load-bearing** — it sets the DSP's frame rate, hence every delay
tap and reverb time. It does **not** block wiring the path (both ends simply use whatever rate
the tone generator's stream runs at), but it must be settled before any delay time is called
faithful. See open item **O-1**.

### 3.4 How MAME should clock the core

The hardware answer is unambiguous: **IC303 generates LRCK; one LRCK period = one PC sweep.** The
MAME translation of that is *not* "run the CPU device from the scheduler at 25 MHz and hope", it
is **"execute exactly one frame per output sample, driven by the audio stream"**:

```
  per output sample:
      latch DI1L/R, DI2L/R, DI3L/R  from the input side          (= the DIn-R registers)
      PC := 0
      run instruction slots until the frame-wait word (I-RAM 82, C00.A.47.407)
          or until a hard slot cap (384) -- whichever comes first
      present DO1L/R, DO2L/R, DO3L/R  to the output side         (= the DOn-R registers)
```

The slot cap is a safety net, not a model: `dsp-critical-path-coverage.md` §B2 shows the frame-wait
word is itself undecoded, so until it is, the cap is what ends the frame. Both must be present —
the cap alone would silently mask a decode error in the wait word, and the wait word alone would
hang on any program that never reaches it.

**Do not** drive it off `execute_run()` with `set_disable()` removed and nothing else changed:
that runs 566 cycles of *scheduler* time per frame with no relationship to the audio stream, and
the input/output latches would be sampled at whatever point the scheduler happened to interleave.

---

## 4. DELAY MEMORY — IC309

### 4.1 What is wired (MEASURED)

* **IC309 = M5M44260AJ-7S**, 4 Mbit, organised **262,144 words x 16 bits** (Felipe verified the
  part; `kn5000.cpp:539-542`).
* BLOCK (A) (p.28) labels the IC311↔IC309 connection **`DSP1A0-DSP1A8`** and
  **`DSP1D0-DSP1D15`** — i.e. **9 address lines and 16 data lines**.
* The schematic agrees: IC311 pins 46..54 (`A0`..`A8`) carry nets `DSP1A0`..`DSP1A8`, and pins
  **55..62 (`A9`..`A16`) carry no net at all** — they are unconnected. Pins 65..80 (`I/O1`..
  `I/O16`) carry `DSP1D0`..`DSP1D15`. Pins 43/44/45 = `RAS`/`CAS`/`WE` drive the DRAM directly.
* **MD1..MD4 (pins 32..35) are all strapped to the VDD rail** — the same rail that carries pin 42
  (VDD) and pin 38 (SEL). **So MD1-MD4 = 0b1111.** These are the "select external RAM type for
  digital delay **and connection conditions**" pins (CDJ pin table, pins 32-35). **MEASURED**,
  read at 1200 dpi from p.35. *This value has not been recorded anywhere before and it is exactly
  the field that decides the question below.*

### 4.2 The size question is now sharper, not answered

`kn5000.cpp:546-552` and `:600-613` frame the open question as *"the DSP's bus is A0-A16, 17
lines, exactly half the part — either one bit is left unconnected, or the KN5000 wires something
the CDJ diagram does not show"*. That framing is now **superseded**: **no address pin above A8 is
connected at all**, and the chip does the row/column multiplexing itself (pin table: "Row address
and column address are output at DRAM selection").

The real question is therefore: **how many column bits does the chip emit on A0-A8?**

* If **row 9 + column 8 = 17 bits** → 131,072 words → the current `map(0x00000, 0x1ffff)` is
  right and half of IC309 is unused. This matches the pin table's "A0-A16" address-bus width, and
  it matches how IC308 (DSP2's byte-wide DRAM) has been read (`kn5000-dsp-INDEX.md` item 7).
* If **row 9 + column 9 = 18 bits** → 262,144 words → the map is half the size it should be.
  Weak supporting evidence: two ROM-resident FLANGER tap values, **140,800** and **153,600**
  (`kn5000-dsp-coefficients.md` §3), are **> 131,072 and < 262,144** — they only fit an 18-bit
  space. That note itself flags them as possibly a sweep range rather than a tap address, so this
  is suggestive, not decisive.

**Recommendation: do NOT change the map yet.** The existing comment's instinct is right — the
wrap point *is* what would silently corrupt every reverb tap length. Record the MD strap, and
settle it with a measurement once the core runs (§7, O-2).

### 4.3 Is the existing `AS_DELAY` map right?

Structurally, **yes**:

* `upd6383.cpp:108` declares the space as `("delay", ENDIANNESS_BIG, 16, 18, -1)` — 16-bit data,
  18 address bits, word-addressed. That matches IC309's x16 organisation and is already sized for
  the whole part; only the driver's `map()` limits it.
* `kn5000.cpp:587-614` maps `0x00000-0x1ffff` as plain RAM. Correct in kind (it is a plain DRAM,
  no banking hardware between chip and part), possibly half the right size (§4.2).
* One real modelling consequence, already documented at `kn5000.cpp:594-598` and worth repeating
  because it is easy to lose: the delay line stores **16-bit** samples while the core is
  **24-bit**, so a sample is *truncated going out to the delay and coming back*. That is hardware,
  not a shortcut, and it will be audible in the reverb tail.

---

## 5. THE MAME CHANGE SET

### 5.1 Design decision: who owns the frame

The topology is a **cycle**: `IC303 → IC311 → IC303`. MAME's stream graph cannot express a cycle
without a delay element. Three options:

| option | topology | latency | verdict |
|---|---|---|---|
| **(A)** IC311 becomes a `device_sound_interface` with 6 in / 6 out; TG routes sends to it; DSP outputs route **straight to the speakers** in parallel with the TG's dry | **wrong** — the return no longer passes through IC303's mixer, master volume or the analog chain in the right place | none | rejected: it silently moves the return past the mixer |
| **(B)** as (A), but the returns route **back** into extra TG stream inputs, with a one-block ring buffer breaking the cycle | right | one update block (~ms) | acceptable fallback |
| **(C)** the **tone generator owns the call**: `kn5000_tonegen_device::sound_stream_update()` computes the send buses per sample, calls `m_dsp1->run_frame(in[6], out[6])`, and mixes the returns into its own mix | right | **zero** | **recommended** |

**(C) is recommended, and it is not a shortcut — it is the hardware.** IC303 generates LRCK;
IC311's frame *is* IC303's word clock. Making the tone-generator device drive one DSP frame per
output sample models exactly that relationship. It also satisfies the HLE chip-boundary rule:
`run_frame(6 in, 6 out)` is literally DI1..DI3 / DO1..DO3 over one LRCK period — a real pin-level
interface of the part. No device reads another device's RAM.

### 5.2 File by file

**`src/devices/cpu/upd6383/upd6383.h` / `.cpp`**
1. Add the six input and six output audio latches as real device state, named for the pins:
   `m_di[3][2]`, `m_do[3][2]` (24-bit, signed), `save_item()`-ed like the rest of the register
   file. These are the `DI1L-R … DO3R-R` boxes on the CDJ block diagram, so they belong to the
   chip, not to the driver.
2. Add the frame entry point:
   ```c++
   // One LRCK period.  Latches DI1..DI3, resets the PC (the chip's internal PC-RST,
   // which the KN5000 cannot inhibit -- Fs-MASK is strapped high), executes to the
   // frame-wait word or the slot cap, and presents DO1..DO3.
   void run_frame(const s32 (&di)[3][2], s32 (&do_)[3][2]);
   ```
   Implementation reuses the existing decode/dispatch loop from `execute_run()`; add a
   `m_slot_budget` counter and stop on either the frame-wait word or `IRAM_WORDS`.
3. Add a hard, *loud* guard: if the frame ends on the cap rather than on the wait word, or if any
   word traps, count it. Expose the counters. A frame that hit an undecoded word did **not**
   produce a faithful sample and the driver must be able to know that (see 5.4).
4. Keep `execute_run()` and `set_disable()` exactly as they are. This device stays disabled *as a
   CPU*; it does not need scheduler time under option (C).

**`src/mame/matsushita/kn5000_tonegen.h` / `.cpp`**
5. Add a `required_device<upd6383_device>` (or an optional callback) so the tone generator can
   reach the DSP, plus a `bool m_dsp_enabled`.
6. In `sound_stream_update()` (`kn5000_tonegen.cpp:1763`), per output sample, **before**
   `stream.put()` at :2033-2034:
   * build the send buses `sendA`, `sendB`, `sendC` (stereo each) — see 5.3;
   * if enabled, `m_dsp1->run_frame(...)`;
   * add the returns into `mix_l`/`mix_r` with the return gains;
   * `softclip()` as today.
   The dry `mix_l`/`mix_r` computation is **not touched**.

**`src/mame/matsushita/kn5000.cpp`**
7. Add the gate to `INPUT_PORTS_START(kn5000)`:
   ```c++
   PORT_START("DSPCFG")
   PORT_CONFNAME(0x01, 0x00, "Effects DSP IC311 (EXPERIMENTAL - incomplete ISA)")
   PORT_CONFSETTING(   0x00, DEF_STR(Off))
   PORT_CONFSETTING(   0x01, DEF_STR(On))
   ```
   read in `machine_start`/on change, forwarded to the tone generator. **Default Off.**
8. Wire the tone generator to the DSP in `kn5000(machine_config &)` next to
   `KN5000_TONEGEN(config, m_tonegen, 0)` at `:1151`. **Leave `m_dsp1->set_disable()` (`:1147`)
   in place** — under option (C) the device never needs scheduler cycles.
9. Leave the routes at `:1152-1153` (`m_tonegen->add_route(0/1, …, 1.0)`) **unchanged**. Nothing
   new is added to the speakers; the wet arrives inside the tone generator's own mix, which is
   where the hardware puts it.
10. Update the `dsp1_delay_map` comment block (`:587-614`) with §4.1's measured facts
    (A0-A8 only, A9-A16 unconnected, MD1-MD4 = 1111) and re-state the open size question in its
    sharper form. **Do not change the map bounds.**

Nothing else changes. No new speaker, no new route, no change to the audio path when the gate is
Off, and the shipped default behaviour is byte-for-byte what it is today.

### 5.3 The one thing that is NOT ready: the send levels

To build `sendA`/`sendB`/`sendC` we need to know, per voice, **how much of it goes to each send
bus** — and that is **not established**. It is *not* the per-voice registers `+0x8C0` /
`+0x900..0x9C0` / `+0xA00` / `+0xA40`: `kn5000_tonegen.cpp:334-346` shows, with firmware
citations, that those are envelope-generator stage words written in `(seg0, seg1)` pairs from
consecutive struct words, and that the effect depths (`CC 0x91/0x97/0x9B`) never reach IC303 at
all. So the send path into IC303 is somewhere we have not looked.

**Until that is found, the honest interim is: send the full stereo mix to both buses at unity**,
clearly labelled as a placeholder, exactly as `fake-with-the-real-mechanism` prescribes — the
*mechanism* (a stereo send into DI1/DI2 at LRCK rate, a stereo return added to the mix) is
faithful and drop-in-replaceable; the *level* is a stand-in. This is honest and it is
falsifiable: with real per-voice sends, changing a part's DSP depth will change the wet level, and
today it will not.

### 5.4 THE SAFETY PROPERTY

> **The tone generator's dry mix never passes through IC311. The DSP can only ever ADD to the
> output; it can never subtract from it.**

This is guaranteed **three** times over, which is why it is worth stating as a property rather
than a hope:

1. **By the hardware.** The main mix leaves IC303 on `SDO0`, a bus IC311 is not on. The sends
   (`SDOA`/`SDOB`/`SDO1`) are *copies*. §2.2, MEASURED.
2. **By the code structure.** Under 5.2 step 6 the `mix_l`/`mix_r` computation is untouched and
   the return is a `+=` after it. A `run_frame()` that returns zeros, throws, or is never called
   leaves the output bit-identical.
3. **By the gate.** `PORT_CONFNAME` defaults Off; with it Off, `run_frame()` is not called at all
   and there is not even a code path difference in the mix.

Additional guards that follow from it:

* If a frame traps an undecoded word, **discard that frame's return** (add zero) rather than
  adding a half-computed sample. A partially-executed effect frame is not "a bit wrong", it is
  arbitrary; and `plausible-but-wrong sound is worse than silence` is this project's standing
  rule (`instruction-set.md`, closing paragraph).
* Log the trap rate once per second, not per sample.

**Known approximation to declare up front:** on real hardware an *insert*-type effect
(distortion, compressor) presumably has its dry part removed from the main mix inside IC303, so
switching the DSP off is not silent-but-neutral — it is "the part is heard dry". We cannot model
that until §5.3 is solved. With the gate Off the machine is exactly as it is today; with it On and
a working insert effect, the part will be heard dry **plus** wet. Say so in the comment.

---

## 6. WHAT THIS NOTE CHANGES IN THE EXISTING WRITE-UPS

| where | said | now |
|---|---|---|
| `dsp-critical-path-coverage.md` §B3 | "the chip has three serial input ports and **this board uses one stereo pair**" | **FALSIFIED.** All three DI and all three DO are wired (§1.1). The two opening blocks may be two *ports*, not an L/R pair. |
| `instruction-set.md` "Control flow"; `kn5000-dsp-INDEX.md` | "the PC sweeps I-RAM once per sample frame (**Fs-RST / PC-RST pins**)" | Substance stands; mechanism corrected — `Fs-RST` and `Fs-MASK` are both strapped to +5D and inactive. It is the **internal PC-RST** off the TIMING block, cadenced by LRCKI, which **IC303** drives (§3.1). |
| `kn5000.cpp:546-552`, `:600-613` | "the DSP's bus is A0-A16, 17 lines, exactly half the part; either one bit is left unconnected or the KN5000 wires something the diagram does not show" | Superseded: **A9-A16 are not connected at all**; only A0-A8 reach IC309 and the chip multiplexes internally. The open question is now "8 or 9 column bits", and **MD1-MD4 = 0b1111** is the deciding strap (§4). |
| `kn5000-docs/tone-generator.md` ("Waveform RAM: IC308 …, IC309 …") | lists IC308/IC309 as *waveform* RAM for IC303 | **WRONG.** IC308 is **IC310's** delay DRAM and IC309 is **IC311's** delay DRAM (BLOCK (A), p.28; schematic p.35). Neither is connected to IC303. Worth fixing on the docs site. |
| general | the DSP is "the effects processor" | It is *an* effects processor: **units 0-1**. Units 2-4 are IC310, which is also the **final output stage feeding the DAC**. Nothing reaches the DAC without IC310 (§2.1). |

---

## 7. OPEN UNKNOWNS, ranked by what they block

**O-1 — the sample rate conflict. [blocks: every delay/reverb time]**
Firmware says 44,100 (`ms × 0xAC44 / 0x3E8`, MEASURED). MAME's tone generator runs 48,000
(`kn5000_tonegen.cpp:76`). IC303's crystal reads `36.8688 MHz`, which divides to neither.
*Next step:* find IC303's LRCK divider (the register group that programs it, or `ECKOUT`/`MCKOUT`
on pins 41/42), **or** ask Felipe to read X301's marking off the board — his testimony outranks
the scan. A 33.8688 MHz part would settle it for 44.1 kHz immediately.

**O-2 — 17 or 18 delay address bits. [blocks: correct tap lengths, hence every reverb]**
MD1-MD4 = 1111 is recorded but its encoding is unknown. *Next step, no hardware needed:* once the
core runs, program a delay whose UI value crosses 131,072 words (≈2.97 s at 44.1 kHz) and see
whether it wraps. *Cheaper still:* Felipe can buzz IC311 pins 55-62 to IC309 to confirm they are
genuinely unconnected (the scan says so, but it is a scan).

**O-3 — which port each opening/closing block serves. [blocks: routing correctness]**
Three DI and three DO exist; the frame must read three and write three. Prediction in §1.4;
target words are I-RAM 0..11 and 73..78 (`dsp-critical-path-coverage.md` §B3/§B4).

**O-4 — the IC303-side send and return levels. [blocks: correct wet balance]**
Not the per-voice `+0x8C0`/`+0x900` registers (firmware-cited, `kn5000_tonegen.cpp:334-346`). The
0x130000 block is explicitly *not* part of the uPD6383GF (`kn5000.cpp:259-264`) and is a candidate.
*Next step:* tap 0x100000/0x130000 in MAME while moving the DSP EFFECT / REVERB depth sliders and
diff — the same live-capture method that solved the parameter-name binding.

**O-5 — IC311 DO3's destination.** §2.3. Not on the critical path.

**O-6 — IC310 SDO1/SDO2 → DA-L/DA-R.** INFERRED from counting pins (§2.1). Only matters when
someone models IC310; the DAC is downstream of everything we can change.

**O-7 — MD1..MD4 encoding, `SETRDY`, `BR-AK`.** The `SETRDY` pin (100) is "set to open in regular
modes" and `BR-RQ` is strapped high, so the emulator-mode machinery is disabled on this board —
which is *useful negative information*: no PC trace can ever be obtained from a KN5000 without
board modification. (`kn5000-dsp-necfamily.md` §6 asks for a PC trace; this is why one is not
free.)

---

## 8. RECOMMENDED ORDER OF WORK

1. **Settle O-1** (cheap, and everything downstream is scaled by it).
2. Implement **5.2 steps 1-2** — the six latches and `run_frame()` — with the gate defaulting Off.
   This is inert and cannot regress anything.
3. Implement **5.2 steps 5-9** with the placeholder unity send of §5.3. Still inert by default.
4. Only then attack the decode work in `dsp-critical-path-coverage.md` §5, in its stated tier
   order. With the plumbing already in place, each decoded word can be *heard* the moment it
   lands, which is a far better feedback loop than reading `?word` counts.
5. **O-3** and **O-4** convert "audio flows" into "audio flows correctly".

The plumbing is genuinely independent of the ISA, and doing it first is the difference between a
decoding effort that can be tested and one that cannot.
