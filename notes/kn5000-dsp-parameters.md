# NEC uPD6383GF — the parameter translator, and the first semantic anchors

KN5000 IC311 effects DSP. Companion to `notes/kn5000-dsp-encoding.md`,
`notes/kn5000-dsp-coefficients.md`, `notes/kn5000-dsp-reverb.md` and
`notes/kn5000-dsp-header.md`.

Tool: `tools/kn5000_dsp_params.py`. Every number below is printed by

```
python3 tools/kn5000_dsp_params.py \
    kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom \
    kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom
```

Claims are tagged **MEASURED**, **INFERRED** or **SPECULATIVE**. §10 lists what is
falsified or explicitly not established.

**Why this note exists.** Everything previously known about this chip was structural or
statistical. The uPD6383GF core is *not* emulated (`src/mame/matsushita/kn5000_dsp.cpp`
is host-interface-only: it captures the byte stream, executes nothing, produces no
audio), so "measure it in the emulator" was never available. The route taken instead:
**the firmware already knows what the fields mean**, because the user edits effect
parameters by name on screen. This note decodes the translator that sits between
"user sets DELAY L = 25 ms" and "these bytes go to the DSP".

**Headline results.**

1. The parameter path emits exactly the `801.0.NN.821` and `000.1.NN.000` words the
   header note guessed at — and it builds `NN` as *an 8-bit C-RAM/D-RAM address*.
   The pointer-set-then-stream idiom is now proven by construction, not inferred.
2. **The sample rate is 44 100 Hz, read out of the firmware**, not assumed: the sub-CPU
   converts a millisecond parameter to DRAM words with `ms * 0xAC44 / 0x3E8`.
3. The user value range is **0..99** (`/0x63`), and there is a second range **0..180**
   (`/0xB4`, degrees).
4. A per-algorithm table gives, for every one of 59 effects, the exact set of DSP
   addresses each parameter writes.
5. Independent confirmation of the reverb note: the 12 reverb presets (algo 16..27)
   share one parameter map, byte-identically, differing only in constants.

---

## 0. The call chain (MEASURED, sub-CPU v1.42 disassembly)

```
DSP_WriteParameter          0x03C190   (symbols file: 0x03C190; task brief agrees)
  -> DSP_ParameterWriteEngine   0x03C9E6   (NOT 0x03C190 as the brief's older note said)
       -> DSP_PerParameterTranslator 0x03CAAE  (brief said 0x03CAAC — off by two)
            -> LABEL_03CF53          resolve (opcode, operand) -> DSP address
            -> one of 25 eval helpers  scale the user value -> 24-bit coefficient
            -> one of 4 writers        emit the DSP words
                 LABEL_0387E6 / LABEL_03846C / LABEL_038539 / LABEL_038922
                   -> DSP_DispatchData  (one byte at a time to the host port)
```

`DSP_WriteParameter(WA = unit, BC = algorithm, DE, XIX = effect state struct)`
(asm lines 50339..50420). It selects two pointers:

```
    XDE (T1) = *(0x0001F22C + 4*algorithm)     "opcode -> DSP address" map
    XBC (T2) = *(0x0001F09C + 4*algorithm)     parameter bytecode stream
```
plus the per-unit parameter block `XIX + 56*unit + 12` and the constant `0x014777`.

**MEASURED, and it settles the per-unit state layout:** the index arithmetic is
`XDE = ((unit*8 - unit)*8) + 8` = `56*unit + 8`, then `+4`, i.e. **56 bytes of effect
state per unit, user parameter values starting at offset +12**. Unit 1 with algorithm
9 or 10 bypasses the arrays and uses hard-coded pairs (`0x01E17F`/`0x01E19E`,
`0x01E40A`/`0x01E42D`) — the same pair shape, so those two are ordinary T1/T2 tables
that simply are not in the arrays.

---

## 1. The two per-algorithm tables (MEASURED format, decoded for all 100 slots)

### T1 — the "opcode → DSP address" map (`0x0001F22C[algo]`)

```
    record: [u16 big-endian total_length][u8 opcode][u8 address ...]
    terminator: a u16 whose high byte is 0xF0
```
`address[i]` is the **8-bit DSP RAM address** used when the stream names
`(opcode, operand=i)`. Example, algorithm 1 = CHORUS (`T1 = 0x000163A2`... see tool
output; the printed map is):

```
    op 66 -> 09 0A          op 65 -> 00      op 63 -> 06
    op 21 -> 90             op 74 -> 1D 00 00 00
```

### T2 — the parameter bytecode stream (`0x0001F09C[algo]`)

```
    record: [u16 big-endian total_length][ instruction ... ] 0x7A
    instruction: [u8 opcode][u8 operand][immediate bytes ...]
```
`0x7A` terminates a record (`CP WA,007Ah` at 0x03CBC6). The translator reads the
opcode at 0x03CBB6, the operand at 0x03CB18, resolves the address through
`LABEL_03CF53`, calls the eval helper (which consumes the immediates), then the writer.

**One record = one user parameter.** The user's value is fetched as a *signed 16-bit
word* from an array (`LD DE,(XWA)` / `EXTS XDE` at 0x03CB4C..0x03CB58) indexed by the
translator's `DE` argument — i.e. from the 56-byte per-unit state block at +12.
With 22 bytes available that is **at most 11 parameters per unit**; the measured
maximum record count over all 59 algorithms is 17, so records and UI parameters are
*not* 1:1 for the largest effects. **INFERRED**, and a caveat: some records are
constants that the user never sees (see §5).

### Validation of the algorithm index (MEASURED, zero exceptions)

The main-CPU effect **name** table is `name[algo] = ROM_main[0x33568 - 18*algo]`
(the reverb note's anchor "algo 20 = CONCERT REVERB 1" fixes the origin at algo 0 =
`NO OPERATION`). Cross-checking the two ROMs:

* every algorithm whose name is the placeholder `----------` has `T2 == NULL` —
  **all 41 of them, no exceptions**;
* no algorithm named `----------` has a stream.

That is a hard consistency check across two physically separate ROMs, and it confirms
both the name-table stride/direction and the pointer-array indexing.

The name table also has its own descending pointer array at main-CPU `0x032A7A`
(stride 4, `[u16 offset][00 E3]`), which re-derives the stride-18 layout independently.

---

## 2. ★ The writers: what the DSP actually receives (MEASURED, byte-for-byte)

`LABEL_0387E6` (asm 45484..) emits, for address `A` and 24-bit value `v`
(`A = descriptor_field + address_from_T1`):

```
    0x08, 0x01, (A>>4)&0x0F, ((A<<4)&0xF0)|8, 0x21          <- 5 bytes = one 36-bit word
    0x0A, (v>>1)&0x7F, (v>>9)&0xFF, (v>>1)&0xFF, ((v<<7)&0x80)|0x26
```

Decoded with the established field map (`hi12.class4.addr8.lo12`):

```
    word 1 = 801 . 0 . AA . 821          <- AA is the 8-bit DSP RAM address
    word 2 = A?? . ? . ?? . ??6          <- the coefficient
```

`LABEL_03846C` and `LABEL_038539` are the same routine against a different memory:

```
    0x00, 0x00, 0x10|((A>>4)&0x0F), (A<<4)&0xF0, 0x00
    0x0A, (v>>1)&0x7F, (v>>9)&0xFF, (v>>1)&0xFF, ((v<<7)&0x80)|0x15

    word 1 = 000 . 1 . AA . 000
    word 2 = A?? . ? . ?? . ??5
```

**This is the anchor the project has been missing.**

* `801.0.NN.821` — the header note (§7) inferred from position and idiom that this is
  "load pointer with 8-bit immediate NN", and that a poke burst is
  *pointer-set then stream values*. **It is now MEASURED**: `NN` is literally computed
  as an address by the firmware, and the following `0xA__` word is the datum.
  The header note's 15 observed `801.0.NN.821` pokes with
  `NN ∈ {00,09,0A,1E,26,50,6E,8C,90,97,9E,A6,AC,AE,B2}` are exactly the address set
  this table produces (compare §5's per-algorithm maps — `09,0A` is CHORUS, `90` is
  universal, `97,9E,A6,AC,B2` are the reverb block).
* `000.1.NN.000` — the header note (§8) saw the minimal pair `000.1.06.000` /
  `000.1.86.000` and speculated bit 7 was "a direction or L/R-channel bit".
  **That is refuted**: `0x06` and `0x86` are simply two different 8-bit addresses,
  and both are real parameter targets (`0x06` is the universal address in 37 effects,
  `0x86` is its reverb-family counterpart).
* The two writers differ only in the low byte of the data word (`0x26` vs `0x15`) and
  in `class4` of the pointer word (`0` vs `1`). **INFERRED: two address spaces —
  C-RAM and D-RAM, both 256×24 per the CDJ-500 block diagram.** Which is which is
  *not* established.
* `hi12 = 0xA00 | ((v>>1)&0x7F)` for the data word matches the coefficient note's
  `A__` poke form exactly (`A06.1.1E.315`, `A37.6.D1.D15`, `A79.E.E1.C95` — note the
  `…15` tails, which are the `038539` family).

The 24-bit value is scattered across the data word as
`W[23:16]=v[16:9]`, `W[15:8]=v[8:1]`, `W[7]=v[0]`, `W[30:24]=v[7:1]`.
Bits `W[23:7]` therefore form a **contiguous 17-bit field holding v[16:0]** — and 17
bits is exactly the external DRAM address width (A0–A16) on the block diagram.
`W[30:24]` duplicates `v[7:1]`. **SPECULATIVE:** the instruction has one 17-bit
immediate plus a 7-bit secondary field that the firmware happens to fill with the same
bits; the duplication is in the code and is not an artefact of this analysis.

---

## 3. ★★ The sample rate, read out of the firmware (MEASURED)

`LABEL_03925E` (asm 46462..) — one of the eval helpers:

```
    LD XBC, 0000ac44h        ; 44100
    CALL LABEL_03D8CA        ; 32x32 -> 32 multiply (MUL/MUL/ADD, asm 47xxx)
    LD XBC, 000003e8h        ; 1000
    CALL LABEL_03DC5F        ; 32-bit divide (DIV)
    ADD XHL, (XSP + 004h)    ; + a 24-bit base offset from the stream
```

i.e. **`DRAM_words = milliseconds * 44100 / 1000 + base`**.

The task brief was right to warn that the CDJ-500's 44.1 kHz proves nothing about the
KN5000 — but this is the KN5000's own sub-CPU, converting *its own* user-facing
millisecond parameter into *its own* delay-line word count. There is nothing to assume:
**the uPD6383GF delay line in the KN5000 runs at 44 100 Hz.**

(Two further range constants in the same family, both MEASURED:
`LABEL_0392AC` divides by `0xB4` = 180 → a degrees parameter, matching the `PHASE` /
`PAN 1..4` names; `LABEL_039206` divides by `0x63` = 99 → the standard 0..99 value
range.)

### 3.1 The delay-time anchor

With the rate fixed, the already-published DRAM word counts become times:

| quantity | words | **44.1 kHz** | (32 kHz) | (48 kHz) |
|---|---|---|---|---|
| chorus taps | 200 / 720 / 1240 / 1760 | **4.54 / 16.3 / 28.1 / 39.9 ms** | 6.3 / 22.5 / 38.8 / 55.0 | 4.2 / 15.0 / 25.8 / 36.7 |
| chorus tap spacing | 520 | **11.8 ms** | 16.3 | 10.8 |
| rotary taps | 160 / 502 / 862 | **3.63 / 11.4 / 19.6 ms** | 5.0 / 15.7 / 26.9 | 3.3 / 10.5 / 18.0 |
| full DRAM (17-bit) | 131072 | **2.97 s** | 4.10 | 2.73 |

4.5–40 ms for chorus and 3.6–19.6 ms for a rotary-speaker horn/drum delay are textbook
values; at 32 kHz the chorus tail reaches 55 ms, which is late-chorus/short-slapback
territory. **INFERRED, supporting:** the 44.1 kHz reading is the musically correct one,
consistent with the firmware constant. The maximum delay the hardware can address is
**2.97 s**, which sits neatly above the longest user-facing `REVERB TIME` value list in
the main ROM (0.1 … 20.0 s is a *reverb decay time*, not a delay length — see §4).

---

## 4. ★ The user-facing names, units and value lists (MEASURED, main-CPU ROM)

Found immediately below the effect-name table:

| table | address | layout |
|---|---|---|
| parameter names | `0x0324D5` | 85 entries, 16 chars + `':'`, stride **17** |
| parameter units | `0x03241A` | 2 chars per entry, same index |
| value list "0.1 … 20.0" | `0x0322F0` | 32 entries, 4 chars, `0xFF`-terminated |
| value list "40 … 16k" | `0x032390` | 27 entries, 4 chars — ISO ⅓-octave centres |
| value list "+0.5 … +12.0" | `~0x032270` | dB, `0xFF`-terminated at `0x0322EF` |
| effect names | `0x033568` | 18 chars, **descending** by algorithm |
| effect-name pointers | `0x032A7A` | stride 4 |

The unit alignment was fixed by **predict-then-check**: assert *a priori* that
`LFO SPEED`/`SLOW LFO SPEED` are Hz, `WIND UP`/`WIND DOWN` are s, `DELAY L`/`DELAY R`
and `GATE TIME`/`MASK TIME`/`PRE DELAY` are ms, `REVERB TIME` is s. Sweeping every
base offset in `0x032400..0x03242F`, the base `0x03241A` scores **12 of 13** and every
other candidate scores ≤ 4. The full 85-entry list (tool section 6) then reads
correctly throughout — `HARS TIME L/R` ms, `FAST LFO SPEED L/R` Hz,
`BAND EMPHASIS FC` Hz, `ATTACK/RELEASE RATE` s, `DELAY 1..4` ms.

The names are the vocabulary the translator serves: `DEPTH`, `FEEDBACK`, `LFO SPEED`,
`REVERB TIME`, `PRE DELAY`, `HIGH DAMP GAIN`, `ER.LEVEL`, `THRESHOLD`, `RATIO`,
`WAH CENTER FC`, `PAN 1..4`, `DELAY 1..4`, `PHASE`, `SWEEP RANGE`, …

**NOT ESTABLISHED (and this is the gap):** the table that says *which* of these 85 names
belongs to *which* parameter slot of *which* algorithm. A search of the whole main-CPU
ROM for any fixed-stride byte table whose rows 16..27 repeat identically twelve times
(which they must, if the twelve reverbs share a parameter list, as their T2 streams show
they do) returned **no candidate at any stride 4..16**. The mapping is therefore not a
flat table; it is probably built per screen. See §10.

---

## 5. The per-algorithm parameter maps (MEASURED)

59 algorithms have streams; 445 records total. Tool section 3 prints all of them. Three
records are near-universal:

| instruction | address | present in | immediate |
|---|---|---|---|
| `op 0x63 #00` | **0x06** | 37/59 algorithms | 1 byte, a curve selector |
| `op 0x21 #00` | **0x90** | 37/59 algorithms | 6 bytes, always `000000 666666` |
| `op 0x74 #00` | **0x1D** | 26/59 algorithms | 1 byte |

`op 0x21` is the one opcode whose handler is **MEASURED without ambiguity**: the
dispatcher at `LABEL_03CEE2` calls `LABEL_039206` explicitly (asm 51236..). And
`LABEL_039206` is:

```
    v1 = 3 bytes from the stream, sign-extended, <<8      (a Q0.23 constant)
    v2 = 3 bytes from the stream, sign-extended, <<8
    out = (v1>>8) + ((v2 - v1)>>8) * user_value / 99
```

— a **linear interpolation of the 0..99 user value onto the coefficient range
[v1, v2]**, via `LABEL_03CF07` (which is the "read a 24-bit big-endian constant"
primitive, asm 51260..).

So: **in 37 of the 59 effects, one parameter is linearly mapped from 0..99 onto
0.0 … 0.8 (0x666666 in Q0.23) and written to DSP address 0x90, with identical endpoints
every time.** A control that (a) every effect has, (b) always has the same range, and
(c) always lands at the same address is, on the KN5000's UI, the wet level.

> **PREDICTION (stated before the check, and only partly confirmable here):**
> address `0x90` is the effect wet/output level. Supporting: it is universal, its range
> is fixed, and 0.8 is a sensible headroom-limited unity. Against: the name list has
> several distinct "DRY/WET" entries (`DELAY DRY/WET`, `CHORUS DRY/WET`,
> `FLANGER DRY/WET`, `PHASER DRY/WET`, `WAH DRY/WET`, `DELAY1/2 DRY/WET`,
> `VIBRATO DRY/WET`), which suggests dry/wet is *per block* and not the universal one;
> the universal one may instead be `DEPTH` (name index 6) or the effect send.
> **Verdict: address 0x90 is a universal, 0..0.8-ranged level. Which of the two names it
> carries is NOT decided.** Marked SPECULATIVE deliberately.

`op 0x63` is the second-best case: its handler is `LABEL_038EB9`, which consumes exactly
one immediate byte — a selector 0/1/2 — and returns `*(TABLE[sel] + 4*user_value)` from
three 100-entry tables. That matches the measured 1-byte immediate exactly.

### The value curve tables (MEASURED)

| table | address | value[1] | value[50] | value[99] |
|---|---|---|---|---|
| CURVE_A | `0x00012483` | -49.83 dBFS | -14.99 dBFS | -3.01 dBFS |
| CURVE_B | `0x00012613` | -27.94 dBFS | -10.51 dBFS | -4.51 dBFS |
| CURVE_C | `0x000127A3` | -32.50 dBFS | -12.79 dBFS | -6.02 dBFS |
| CURVE_D | `0x00012B33` | **-101.06 dBFS** | **-50.00 dBFS** | **-3.01 dBFS** |

**CURVE_D is a clean 1.000 dB-per-step ladder** — value *v* gives
`gain = 0.7071 · 10^((v-99)/20)`, i.e. −3.01 dB at 99, −1 dB per step down, and exactly
0 (mute) at v = 0. Per-step dB min/max/mean printed by the tool are all 1.0000 to four
decimals over v = 1..99. That is a **MEASURED** decibel volume law, and it identifies
`LABEL_038EAC` (`*(0x00012B33 + 4*v)`) as *the* dB volume translator on this machine.
A, B and C are shallower, non-constant-dB curves — depth/mix laws rather than volume.

### The twelve reverbs (MEASURED, independent confirmation)

Algorithms 16..27 (`ROOM REVERB 1` … `WAVE REVERB 2`) share `T1 = 0x0001CB72`
byte-identically:

```
    op 66 -> A9 AA AB AC   AF B0 B1 B2      (two banks of four -> L and R)
    op 67 -> 00 19 1A 1B 1C 1D 1E
    op 76 -> 9E A6          op 75 -> 97      op 63 -> 86
```

and their T2 streams are structurally identical, differing only in constants — five
records each, in the same order, with the same opcodes and operands. This is exactly
the reverb note's finding ("12 presets share one 133-word program at I-RAM 200")
arriving from a completely different direction. Groups also found: algos 15 & 53
(`ROCK ROTARY` / `ROTARY SPEAKER`), 57–60 (`STANDARD`/`PERCUSSIVE`/`SYMPHONIC`/
`DEEP SPACE`), 88–91 (`ROOM`/`KARAOKE`/`BATH ROOM`/`STAGE`).

The twelve reverbs' distinguishing constants:

| algo | name | `op75 → 0x97` | `op66#3/#7 → 0xAC / 0xB2` (upper endpoint) |
|---|---|---|---|
| 16 | ROOM REVERB 1 | 0x0765FD = 0.0578 | 0x3851EB = 0.440 |
| 17 | ROOM REVERB 2 | 0x128F5C = 0.1450 | 0x3851EB = 0.440 |
| 18 | PLATE REVERB 1 | 0x2E76C8 = 0.3629 | 0x4E147A = 0.610 |
| 19 | PLATE REVERB 2 | 0x347AE1 = 0.4099 | 0x4E147A = 0.610 |
| 20 | CONCERT REVERB 1 | 0x179724 = 0.1844 | 0x4CCCCC = 0.600 |
| 21 | CONCERT REVERB 2 | 0x1A4DD2 = 0.2054 | 0x266666 = 0.300 |
| 22 | DARK REVERB 1 | 0x1FBE76 = 0.2480 | 0x599999 = 0.700 |
| 23 | DARK REVERB 2 | 0x1FBE76 = 0.2480 | 0x666666 = **0.800** |
| 24 | BRIGHT REVERB 1 | 0x1FBE76 = 0.2480 | 0x35C28F = 0.420 |
| 25 | BRIGHT REVERB 2 | 0x1C8B43 = 0.2231 | 0x35C28F = 0.420 |
| 26 | WAVE REVERB 1 | 0x2A5E35 = 0.3311 | 0x266666 = 0.300 |
| 27 | WAVE REVERB 2 | 0x2A5E35 = 0.3311 | 0x266666 = 0.300 |

> **PREDICTION, then check.** If `0xAC/0xB2` is a **damping** coefficient (`HIGH DAMP
> GAIN` is name index 35, a reverb parameter), then DARK > BRIGHT must hold.
> **It does, and by the largest margin in the table**: DARK 0.700/0.800 vs BRIGHT
> 0.420/0.420. It is the only pair in the twelve whose names make a directional
> prediction about brightness, and the prediction is correct.
> **Against:** PLATE (0.610) > ROOM (0.440) does not obviously follow, and the same
> ordering would be produced by a decay/feedback coefficient. **Marked INFERRED, weak.**
> The `op75 → 0x97` column orders ROOM < CONCERT < DARK ≈ BRIGHT < WAVE < PLATE, with
> variant 2 ≥ variant 1 in four of six pairs — consistent with a decay/time control but
> not diagnostic.

I am flagging both of these as unproven on purpose. The brief's warning about tidy
stories applies squarely here: the numbers are suggestive, the names are suggestive, and
neither is a decode.

---

## 6. The opcode set (MEASURED coverage, INFERRED bindings)

`DSP_PerParameterTranslator` dispatches (asm 50934):

```
    opcode 0x21 -> LABEL_039206     (explicit, MEASURED)
    opcode 0x24 -> LABEL_03A4B7     (explicit, MEASURED)
    opcode 0x40 -> LABEL_03A4A0     (explicit, MEASURED)
    opcode 0x61..0x79 -> jump table OFFSETS_14745 (25 entries), base 0x0003CB8E
    opcode 0x7A -> end of record
    anything else -> error code 5
```

Immediate sizes, measured over the 445 records (`len - 5` for single-instruction
records):

| op | imm | op | imm | op | imm | op | imm |
|---|---|---|---|---|---|---|---|
| 0x21 | 6 | 0x66 | 6 | 0x6B | 14 | 0x74 | 1 |
| 0x24 | 19 | 0x67 | 3 | 0x6C | 14 | 0x75 | 3 |
| 0x61 | 2 | 0x68 | 8 | 0x6D | 2 | 0x76 | 1 or 2 |
| 0x62 | 0 | 0x69 | 0 | 0x6E | 6 | 0x77 | 46 |
| 0x63 | 1 | 0x6A | 0 | 0x6F | 0 | 0x79 | 7 |
| 0x64 | 3 | 0x70 | 1 | 0x72 | 4 | 0x73 | 6 |

**Honest limitation.** The mapping opcode → eval helper was derived from the jump
table's *address order*, and it does **not** survive the immediate-size check for every
opcode (e.g. it predicts `0x64 → LABEL_038EF6`, which consumes 1 byte, while the
records show 3). It *does* hold for `0x62 → LABEL_038EAC` (0 bytes) and
`0x63 → LABEL_038EB9` (1 byte), and `0x21 → LABEL_039206` (6 bytes) is independent of
the table. **The opcode→helper table baked into the tool is therefore INFERRED and
partially wrong; treat only 0x21, 0x24, 0x40, 0x62 and 0x63 as settled.** Note also
that at least one opcode (0x76) has a *variable* immediate size, so the eval helpers
are not uniformly fixed-width readers, which is why the tool's record splitter searches
rather than assuming.

---

## 7. The descriptor format (12-byte stride) — MEASURED layout, PARTIAL semantics

`DSP_PerParameterTranslator` reads, at `base + 12*index` (asm 50861..50905;
`XBC = index*3; XBC <<= 2` is the stride-12 arithmetic the brief predicted):

```
    +0  u16   base address, used by writer LABEL_0387E6            (801.0.NN.821 space)
    +2  u16   base address, used by writers LABEL_03846C/038539    (000.1.NN.000 space)
    +4  u16   base address, used by writer LABEL_038922
    +6  u16   never read by the translator
    +8  u32   a parameter passed to LABEL_039525 only
```

Each writer receives `descriptor_field + T1_address` as the final 8-bit DSP address
(`LD WA,(XSP+00ch); ADD WA,(XSP+006h)` at the top of every writer). **INFERRED:** the
descriptor is a *relocation base* — one per effect unit / per program load — so that
the same T1 map serves a program loaded at two different C-RAM offsets. That is exactly
the role the `0x0E`/`0x0F` unit index plays in the instruction stream (header note §3).

**Negative result to be explicit about:** the descriptor carries no range, no name, no
unit and no scaling law. All of that lives in the *opcode*, not the descriptor.
**The descriptor is a base-address triple, not a parameter description.** The brief's
"a descriptor that says user value 0..127 → multiply by K → write to address N" is
therefore split across three places: the *range* is in the eval helper (`/99`, `/180`,
`*44100/1000`), the *law* is in the opcode and its curve table, and the *address* is
`descriptor[field] + T1[opcode][operand]`.

---

## 8. The ×2 / ×4 scaling at ROM `0x01E5C7` — VERDICT: not a UI parameter, and the
delay-length reading gains no support

The header note (§4) observed patch words for I-RAM slots 64 and 71 whose bits [24:12]
scale ×2 (1344 → 2688) and ×4 (1600 → 6400), and read that as a delay length or loop
count, noting 30/61/36/145 ms at 44.1 kHz.

What this investigation adds:

1. **Those words are never touched by the parameter translator.** `0x01E5C7` is reached
   only from `DSP_AlgorithmChange` (0x038011), which rewrites the *stub* at I-RAM 60..82
   and pokes I-RAM 64/71. The parameter path writes **C-RAM/D-RAM data addresses**
   (`801.0.NN.821` / `000.1.NN.000`), never I-RAM instruction slots. So the ×2/×4 sets
   are algorithm-selection state, not user-editable parameters, and no on-screen name or
   unit can ever be attached to them by this route. **This is a negative result and it
   redirects the effort**: the header note's suggested experiment ("sweep 0x01E5C7 and
   measure the delay") was aimed at the wrong table.
2. **The ×2/×4 sets do not correspond to effect algorithms.** The T1/T2 arrays index by
   algorithm 0..99 and the ×2/×4 sets are a short list appended to the header stream —
   there is no index arithmetic anywhere that reaches `0x01E5C7 + k*sizeof(set)` from an
   algorithm number. So "which presets are those sets attached to?" has no answer of the
   form the brief anticipated: they are not per-preset.
3. **The delay-length reading is not supported, and one specific alternative is now
   available.** Every genuine delay length in the parameter path is produced by
   `ms * 44100/1000` and written as a *data* word to a C-RAM/D-RAM address; none is ever
   embedded in the [24:12] bits of an I-RAM instruction. Meanwhile §2 shows a real
   17-bit immediate does exist in the data word at `W[23:7]` — so if a DRAM address ever
   appears in an instruction, that is the field it appears in, not [24:12].

**Verdict: the ×2/×4 observation remains an unexplained numeric regularity in the
algorithm-change stub. This work neither confirms nor refutes it as a delay length, but
it removes the reason to believe it, and it rules out reaching it from the UI.**

---

## 9. Cross-checks against the other three notes

| claim | source | status here |
|---|---|---|
| `801.0.NN.821` = "load pointer with 8-bit immediate NN" | header §7, INFERRED | **MEASURED**: the firmware computes NN as an address |
| poke burst = "set the pointer, then stream values" | header §7, INFERRED | **MEASURED**: writer emits pointer word then data word |
| `A__` form carries the runtime coefficients | coefficients note | **MEASURED**: `hi12 = 0xA00 \| ((v>>1)&0x7F)` |
| 12 reverb presets share one program | reverb note | **CONFIRMED independently**: shared T1, identical stream shape |
| coefficients are signed Q0.23 | coefficients note | **CONFIRMED**: `LABEL_03CF07` reads 3 bytes big-endian, sign-extends, `<<8` |
| bit 7 of `addr8` in class-1 words is L/R or a direction | header §8, SPECULATIVE | **REFUTED**: `0x06` and `0x86` are two ordinary addresses |
| `class4` is data inside some families | header §6 | consistent: in `801.0.NN.821` the address spans [23:20]+[19:12], so `class4` there is address bits |

The address bands are also newly legible: parameter targets cluster in **0x00..0x1E**
(a low block) and **0x86..0xB2** (a high block), with `0x90` universal. The reverb
family uses 0x86, 0x97, 0x9E, 0xA6, 0xA9–0xAC, 0xAF–0xB2 — two mirrored banks of four
at 0xA9.. and 0xAF.., which is what an L/R pair of four-stage reverb sections looks
like. **INFERRED**, and it is a testable prediction for the reverb note's tap chains.

---

## 10. Falsified, or explicitly not established

* **"The descriptor carries per-parameter semantics."** Refuted (§7). It is a triple of
  base addresses. This is close to the brief's anticipated negative result, except that
  the semantics were not absent — they moved into the opcode.
* **"bit 7 of `addr8` in class-1 words is a direction/channel bit."** Refuted (§2).
* **"The ×2/×4 sets at `0x01E5C7` belong to presets."** Refuted (§8): nothing indexes
  them by algorithm.
* **The name→slot mapping.** NOT FOUND (§4). Exhaustive search for a fixed-stride byte
  table with twelve identical consecutive rows (required if the twelve reverbs share a
  parameter list, which their streams show they do) found nothing at any stride 4..16.
  Without it, no parameter *name* can be tied to a DSP *address* by construction — only
  by the weaker family arguments in §5.
* **The identity of address 0x90.** Universal and 0..0.8-ranged (MEASURED); its name is
  not decided (SPECULATIVE).
* **The opcode→eval-helper table** is only partly right (§6); five opcodes are settled.
* **C-RAM vs D-RAM.** The two writer families address two different memories, but which
  is which is not established.
* **Not established:** the exact stack plumbing of the parameter *index* (which record
  corresponds to which slot of the 11-word per-unit value block); the semantics of
  `op 0x74 → 0x1D`; the four large opcodes (0x24, 0x6B, 0x6C, 0x77) that carry 14–46
  immediate bytes.

---

## 11. Most promising next steps

1. **Find the name→slot table on the main CPU.** It is the one missing link. Approach:
   find the code that draws the effect-edit page, and see how it indexes `0x0324D5`.
   The value lists at `0x0322F0` / `0x032390` are almost certainly selected by the same
   descriptor, so whatever indexes them indexes the names.
2. **Use `ms * 44100/1000` as a probe.** `LABEL_03925E` is the only helper that produces
   a DRAM word count. Find every algorithm whose stream uses its opcode; those addresses
   are *delay-line taps by construction*, and can be checked against the reverb note's
   (end,start) tap pairs. That would be the three-way agreement the brief asks for.
3. **Confirm the 44.1 kHz rate against the CDJ-500's programmable-rate pins.** The chip's
   rate is host-programmable; the header's 60 fixed words should contain the divider.
   With a target value now known (44100 from a system clock), the header becomes
   searchable in a way it was not before.
4. **Test the L/R bank prediction.** `0xA9..0xAC` vs `0xAF..0xB2` in the reverb map
   predicts two mirrored four-coefficient sections; the reverb note's 133-word program
   should show two parallel chains reading exactly those C-RAM words.
