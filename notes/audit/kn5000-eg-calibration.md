# KN5000 IC303 — EG CALIBRATION (closes GAP CAL-1)

Author: autonomous calibration pass, 2026-07-26. Requested by Felipe Sanches.

Scope: the two laws the four-segment envelope generators (`+0x800/+0x840/+0x880` = EG-A, and the
sibling triples in groups 9 and 10) need before they can be run at all:

* **(a) LEVEL → linear gain** — the segment target byte's meaning.
* **(b) RATE → segment time** — the segment rate byte's meaning.

Evidence labels: **MEASURED** (a ROM byte, a ROM instruction, or a live observation made for this
pass) · **INFERRED** (deduction from measured facts) · **SPECULATIVE** (unproven).

Sources and how to read the citations
* **asm L\<n\>** = 1-based line in
  `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`.
* **sub ROM** = `kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom` (196 608 B).
  **address → file offset = `addr − 0xEF00`**, re-pinned in this pass against
  `Voice_AttackDecay_Widths` (`20 10 04 0C 00×12 40 40`, asm L609) at file `0x607` ↔ addr `0xF507`
  and `Voice_EnvelopeRate_Lookup` at `0x619` ↔ `0xF519`. 2/2.
* **main ROM** = `kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom` (2 MiB); file offsets are
  exact, addresses use the `+0xE00000` base implied by
  `OVERALL TOUCH SENSITIVITY` (file `0xD3D42`).
* **cpp:\<n\>** = `kn7000_mame/src/mame/matsushita/kn5000_tonegen.cpp` at HEAD of this pass.

---

## 0. TL;DR — the two laws

**(a) LEVEL — DERIVED, no free parameter beyond one global headroom scalar.**

```
    gain(L) = 2 ^ ((L - 255) / 16)                 L = segment target byte, 0..255
            = 0.376287 dB per level unit
            L = 255 -> 1.000000 ( 0.00 dB)      L = 128 -> 0.004079 (-47.79 dB)
            L =   0 -> 0.000016 (-95.95 dB)     full span 95.95 dB
```

16 level units = one factor of two, **derived from the ROM**, not fitted: the firmware's own
linear↔log converter (table `0x010764`, sub ROM file `0x1864`) is bit-exactly
`T[i] = round(128·log2(2^(i>>4) · (1 + (i&15)/16)))` for **256 of 256 entries**, which *is* the
statement that an 8-bit level code carries a 4-bit binary exponent and a 4-bit mantissa — one octave
per 16 counts. §2.

The shipped fit `gain = 2^((level−231)/10)` (cpp:499-501) is wrong in **both** constants: **K = 10
should be 16** (0.602 vs 0.376 dB/unit — the shipped law is 1.6× too steep and implies a 153 dB
register range in a 96 dB chip) and **REF = 231 should be 255** (the shipped law saturates for the
top 25 codes). Worst-case discrepancy on a value the firmware actually writes: **+28.7 dB** (the
piano's SUST2 target `0x40`, shipped −100.5 dB vs derived −71.9 dB). §2.6.

**(b) RATE — the *structure* is derived; the *seconds* are NOT in the ROM and must not be invented.**

```
    segment word  = (target_level << 8) | (flag << 7) | rate[6:0]
    rate = 0x7F -> the maximum ramp speed (hard-coded as the attack rate, asm L19399)
    rate = 0    -> HOLD: the segment does not move and the EG stops there
                   (proved by the clamp asymmetry: DECAY1's rate is clamped to [4,127],
                    DECAY2's to [0,127] — asm L19424-19427 / L19304-19312)
    speed is a SPEED, not a time: higher rate = faster ramp
    ramp is linear in the LOG domain (= exponential in amplitude)
    segment ends when the target is reached; the FIRMWARE learns this by POLLING the chip
    (+0x180 level readback and the per-bank active-voice bitmap), never by counting time
```

The absolute seconds are **NOT DERIVABLE** from either CPU's ROM, and the reason is positive rather
than "we didn't find it": the firmware never needs a time, because it discovers segment completion by
reading the chip back (`LABEL_02219F` asm L13334-13348). A full scan of the sub ROM for exponential /
time-shaped tables found only LFO tables, all traced to their consumers (§3.5).

What *is* derivable is that a **linear** rate→speed law is **FALSIFIED** by the firmware's own data,
and that the encoding must be exponential with **≈ 4–6 rate counts per doubling** (§3.6). The HLE
should therefore carry **one** named, bounded, explicitly-CALIBRATED constant, and §3.7 gives the
20-minute measurement on Felipe's real KN5000 that replaces it with a number.

**(c) SANITY — the held piano note sustains.** Under (a) + (b) the default Piano renders as
`attack to −9.8 dB in ~3 ms → decay toward −68.9 dB → HOLD`, i.e. a real piano contour: audible for
~10 s and then genuinely over. It does **not** collapse to inaudibility the way the shipped law's
−100 dB reading of the same registers would. §4.

---

## 1. Where the numbers in the registers come from (MEASURED)

Two contiguous 101-entry **fader tables** convert a 0..100 patch parameter into the 8-bit level byte,
and one contiguous 101-entry table converts a 0..100 patch parameter into the rate byte. They are
laid out back to back, which independently confirms all three lengths:

| table | address | file | length | role |
|---|---|---|---|---|
| `LVL_A` | `0x011899` | `0x2999` | 101 | level fader (used for the PEAK target, asm L18982) |
| `LVL_B` ("LOG") | `0x0118FE` | `0x29FE` | 101 | level fader (SUST1/SUST2 and every software update) |
| `RATE` | `0x011963` | `0x2A63` | 101 | parameter → rate byte, 0..127 |
| `BIPOLAR` | `0x0119C8` | `0x2AC8` | 51 | signed ±50 → ±128 expansion (`LABEL_022B68` asm L14422) |

```
LVL_B (0x0118FE), param 0..100 -> level byte:
  255 248 241 237 233 231 229 227 225 222 218 214 210 208 206 204 202 200 198 196
  194 192 190 188 186 184 182 180 178 176 174 172 170 168 166 164 162 160 158 156
  154 152 150 148 146 144 142 140 138 136 134 132 130 128 126 124 122 120 118 116
  114 112 110 108 106 104 102 100  98  96  94  92  90  88  86  84  82  80  78  76
   74  72  70  68  66  64  62  60  58  56  54  52  50  48  46  42  38  30  22  16
    4
RATE (0x011963), param 0..100 -> rate byte:
    0   4   8  10  12  14  16  18  20  22  24  26  28  30  32  34  36  38  40  42
   44  46  48  49  50  51  52  53  54  55  56  57  58  59  60  61  62  63  64  65
   66  67  68  69  70  71  72  73  74  75  76  77  78  79  80  81  82  83  84  85
   86  87  88  89  90  91  92  93  94  95  96  97  98  99 100 101 102 103 104 105
  106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 121 122 123 124 126
  127
```

### 1.1 The envelope descriptor — the single routine that builds the whole EG

`LABEL_025A9E` (asm L19395-19469) is the definitive builder; transcribed exactly, with
`desc` = the tone record's envelope block:

```
slot[+0x3c] = (PEAK        << 8) | 0x7F              ; asm L19396-19402  << ATK rate HARD-CODED
                                                     ;   (the literal `OR BC,007fh` is L19399)
HL          = LVL_B[desc[+0x09]]                     ; asm L19403-19409  SUST1 level
DE          = LVL_B[desc[+0x0b]]                     ; asm L19410-19416  SUST2 level
BC          = RATE [desc[+0x0a]]                     ; asm L19417-19423  DECAY1 rate
WA          = max(BC, 4)                             ; asm L19424-19427  << FLOOR OF 4
slot[+0x3e] = (HL << 8) | WA                         ; asm L19429-19435  -> chip +0x840
if desc[+0x0d] bit5:                                 ; asm L19436-19439
    WA          = RATE[desc[+0x0c]]                  ; asm L19440-19446  DECAY2 rate (NO floor)
    slot[+0x40] = (DE << 8) | WA                     ; asm L19447-19453  -> chip +0x880
    slot[+0x46] = LVL_B[desc[+0x0d]]                 ; asm L19454-19461
else:                                                ; asm L19463 (LABEL_025B58)
    slot[+0x40] = (DE << 8)                          ; asm L19464-19467  DECAY2 rate = 0
```

The alternate note-on path `LABEL_025636` (asm L18944-19092) builds `+0x800` the same shape but takes
the ATK rate from the patch instead of hard-coding it:
`+0x800 = (level << 8) | RATE[rec[+0x28]]` (asm L19076-19085) — so slow-attack patches are possible.

`LABEL_02591D` (asm L19240-19340) re-applies **key follow** to the rate before shipping:
`rate' = clamp(rate ± tone[+0x20], 4, 127)` for `+0x840` (asm L19304-19307, `BC=0x7F DE=4`) and
`clamp(..., 0, 127)` for `+0x880` (asm L19309-19312, `BC=0x7F DE=0`); the ± sign comes from bit 9 of
`desc[+0x27][+0x18]` (asm L19256-19278 vs L19280-19301).

### 1.2 The main-CPU GUI proves the four-segment structure — MEASURED

The Sound-Edit envelope page's field labels, in page order, main ROM file `0x112072` (≈ addr
`0xF12072`; duplicated at file `0x112722` "PAGE1/2" and file `0x1162D8`):

```
ENVELOPE   KEYOFF   ATK   PEAK   DECAY1   SUST1   DECAY2   SUST2   RELEASE
```

That is exactly `(time, level)` × 3 plus a release time, and it lands 1:1 on the registers:

| GUI pair | descriptor bytes | staging | chip register | LIVE Piano C4 |
|---|---|---|---|---|
| **ATK / PEAK** | `rec[+0x28]` / level chain | `blk+0x18` | **`+0x800`** | `E5 7F` |
| **DECAY1 / SUST1** | `desc[+0x0a]` / `desc[+0x09]` | `blk+0x1A` | **`+0x840`** | `48 4C` |
| **DECAY2 / SUST2** | `desc[+0x0c]` / `desc[+0x0b]` | `blk+0x1C` | **`+0x880`** | `40 00` |
| **RELEASE** | key-up recompute (`LABEL_026769`) | `blk+0x2C/+0x2E` | `+0x800`/`+0x840` | `8B80 / 8B00` |

A second page (file `0x11217D`, `0x1128DE`) is `ENVELOPE / KEY FOLLOW / TOUCH / ATK / DECAY /
RELEASE / RANGE / ATTACK / DECAY` — the **key follow of the envelope times**, i.e. the user-facing
control for exactly the `rate ± tone[+0x20]` term found in `LABEL_02591D`. **PREDICT-THEN-CHECK: HIT**
(the key-scaling was read out of the disassembly first; the GUI page was found afterwards).

### 1.3 Correction: `+0x8C0` is **not** "EG-A segment 3"

`notes/audit/kn5000-audit-registers.md` §1.6 labels `+0x8C0` (reg 23) "EG-A segment 3 (terminal,
target 0x00)". Its builder `LABEL_02492D` (asm L17646-17657) is a *different* encoding:

```
low byte = LABEL_022B68( part[+0x3d] + part[+0x3e] )      ; asm L17648-17654
LABEL_022B68 (asm L14422-14444) = signed bipolar expansion through BIPOLAR[0x0119C8],
                                  input clamped to +-50, output -128..+127
```

The MEASURED Piano value `0x00B0` therefore decodes as **−80 signed**, not "rate 0x30 + flag". A
signed ±128 quantity is not the `[0,127]`/`[4,127]` unsigned rate the three real segments use, and
the four-field GUI has no fourth `(time, level)` pair to spend on it. **`+0x8C0`'s role is UNDECODED**
— do not model it as a segment. (The EG really has three programmed segments plus a release that is
delivered by rewriting segments 0 and 1.)

---

## 2. LAW (a) — LEVEL byte → linear gain

### 2.1 The decisive evidence: table `0x010764` is an exact log2 identity — MEASURED

`LABEL_0232C7` (asm L15195-15214) builds chip register `+0x080` from a sum of level parameters:

```
BC = tone[+0x0c] + tone[+0x10] + slot[+0x33]
WA = clamp(BC, 0, 255)                        ; LABEL_0232B3 asm L15180-15191
BC = WA * 2                                   ; word index
WA = u16le[0x010764 + BC]                     ; asm L15207-15208   << 256-entry u16 table
WA = WA + WA                                  ; asm L15209
(0451D0h) = WA | <nibble> | 0x8000            ; -> chip +0x080 bits 11:0
```

Dumped and fitted (`tools`: 12 lines of stdlib Python, §7):

```
    T[i] = round( 128 * log2( 2^(i>>4) * (1 + (i&15)/16) ) )       EXACT for 256 of 256 entries
    T[0]=0  T[16]=128  T[32]=256  T[48]=384 ... T[240]=1920  T[255]=2042
```

`2^(i>>4) · (1 + (i&15)/16)` is precisely the decode of an 8-bit **4-bit-exponent / 4-bit-mantissa**
float. So the table's job is: *take an 8-bit level code whose scale is one octave per 16 counts and
whose mantissa is linearly interpolated, and emit an exact 12-bit log2 at 256 counts per octave.*

**That is the law.** The 8-bit level code is a log-domain amplitude with

```
    16 counts per factor of 2   =   6.0205999 / 16   =   0.376287 dB per count
```

MEASURED (256/256 exact fit of an identity, no free parameter).

### 2.2 Corroboration 1 — the maximum-loudness limiter steps in exact 3 dB — MEASURED

`LABEL_026769` (asm L20791-20800) caps the level with `IZ = min(IZ, LVL_B[CAP[rec[+0x18]]])`,
`CAP` = `0x011ADF` (file `0x2BDF`) = `31 31 35 39 3D 41 45 49 4D`:

```
   pos 0..8 -> param 49 49 53 57 61 65 69 73 77 -> level 136 136 128 120 112 104 96 88 80
   consecutive positions differ by exactly 8 level units = 8 x 0.376287 = 3.010 dB
```

A nine-position limiter in **exactly 3.01 dB steps**. Under the shipped `K = 10` the same table would
step 4.82 dB — not a number anyone designs a control around.

### 2.3 Corroboration 2 — three registers, one 96 dB domain — MEASURED

| register | width | scale implied | full span |
|---|---|---|---|
| EG target byte (`+0x800/+0x840/+0x880` high byte) | 8 bits | 16 counts/octave | 255/16 = 15.94 oct = **95.96 dB** |
| `+0x080` payload (`2·T[i]`, max 4084) | 12 bits | 256 counts/octave | 4084/256 = 15.95 oct = **96.06 dB** |
| level readback (`AND HL,3FFFh; SRL 5,HL`, asm L13341-13342) | 13 bits | 512 counts/octave | 8191/512 = 16.00 oct = **96.31 dB** |

Three independent register formats, one amplitude domain, one dynamic range — and it is the dynamic
range of the 16-bit PCM path. The readback's `>>5` also tells us the chip's internal level
accumulator carries the 8-bit level plus **5 fractional bits**, i.e. it can move in steps of
1/32 level unit = 0.0118 dB. INFERRED (the mask and shift are MEASURED; the interpretation is the
only one that makes the three formats agree).

### 2.4 Corroboration 3 — the voice manager's threshold is exactly 8 octaves — MEASURED

`LABEL_02222A` (asm L13343-13346) compares the readback byte against `0x80`:

```
   L = 128  ->  (128 - 255) * 0.376287 = -47.79 dB   =  exactly -7.9375 octaves
```

−48 dB is a textbook "this voice is quiet enough to reuse" threshold. Under `K = 10` the same
comparison would sit at −62.0 dB.

### 2.5 THE LAW

```c
// KN5000 IC303 amplitude: the 8-bit level code is log2 x 16, full scale at 255.
// DERIVED from sub-CPU table 0x010764 (exact float8 -> 128*log2 identity, 256/256).
static constexpr double KN5000_DB_PER_LEVEL = 6.0205999132 / 16.0;   // 0.376287 dB
static inline double kn5000_level_to_gain(int L)          // L = 0..255
{
    return std::pow(2.0, (double(L) - 255.0) / 16.0);      // 255 -> 1.0, 0 -> -95.95 dB
}
```

Integer form — the curve is a 16-entry mantissa table plus a shift, because every 16 counts is
**exactly** one halving:

```c
// gain_q30(L) = MANT_Q30[L & 15] >> (15 - (L >> 4)),  Q30 keeps the -96 dB tail exact
static const uint32_t MANT_Q30[16] = {                    // round(2^30 * 2^((m-15)/16))
     560640218u,  585461881u,  611382493u,  638450708u,
     666717336u,  696235434u,  727060411u,  759250125u,
     792865000u,  827968132u,  864625413u,  902905651u,
     942880699u,  984625594u, 1028218693u, 1073741824u };
// max error over all 256 codes: 0.00043 dB
```

*(Do not build this in Q15: at `L < 96` the exact gain is below 2^−12 and a 16-bit fixed point
runs out of bits — the truncating shift is off by up to 6 dB at the very bottom of the curve. Q30,
or plain `double`, reproduces the whole 96 dB.)*

Full 256-entry Q15 curve (`round(32767 · 2^((L−255)/16))`), for reference / test vectors:

```
     1,     1,     1,     1,     1,     1,     1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
     1,     1,     1,     1,     1,     1,     1,     1,     1,     2,     2,     2,     2,     2,     2,     2,
     2,     2,     2,     2,     2,     3,     3,     3,     3,     3,     3,     3,     4,     4,     4,     4,
     4,     4,     5,     5,     5,     5,     5,     6,     6,     6,     6,     7,     7,     7,     8,     8,
     8,     9,     9,    10,    10,    10,    11,    11,    12,    12,    13,    13,    14,    15,    15,    16,
    17,    17,    18,    19,    20,    21,    22,    23,    24,    25,    26,    27,    28,    29,    31,    32,
    33,    35,    36,    38,    40,    41,    43,    45,    47,    49,    52,    54,    56,    59,    61,    64,
    67,    70,    73,    76,    79,    83,    87,    91,    95,    99,   103,   108,   112,   117,   123,   128,
   134,   140,   146,   152,   159,   166,   173,   181,   189,   197,   206,   215,   225,   235,   245,   256,
   267,   279,   292,   304,   318,   332,   347,   362,   378,   395,   412,   431,   450,   469,   490,   512,
   535,   558,   583,   609,   636,   664,   693,   724,   756,   790,   825,   861,   899,   939,   981,  1024,
  1069,  1117,  1166,  1218,  1272,  1328,  1387,  1448,  1512,  1579,  1649,  1722,  1798,  1878,  1961,  2048,
  2139,  2233,  2332,  2435,  2543,  2656,  2773,  2896,  3024,  3158,  3298,  3444,  3597,  3756,  3922,  4096,
  4277,  4467,  4664,  4871,  5086,  5312,  5547,  5792,  6049,  6317,  6596,  6888,  7193,  7512,  7844,  8192,
  8554,  8933,  9329,  9742, 10173, 10623, 11094, 11585, 12098, 12633, 13193, 13777, 14387, 15024, 15689, 16384,
 17109, 17866, 18657, 19483, 20346, 21247, 22187, 23170, 24196, 25267, 26385, 27554, 28774, 30047, 31378, 32767,
```

**Variant worth knowing about.** The firmware's own converter treats the code as a *float8*
(piecewise-linear mantissa) rather than an exact exponential. If the chip does the same, the true
curve is `F(L)/F(255)` with `F(L) = 2^(L>>4)·(1+(L&15)/16)`. The two differ by at most **0.42 dB**
(mid-mantissa) and agree exactly every 16 counts. Use the exact exponential; the float8 variant is a
sub-0.5 dB refinement that only a hardware A/B could justify.

### 2.6 CHECK against the shipped fit `2^((L − 231)/10)` — the discrepancy

Requested explicitly by the task. `min(gain, 1.0)` applied to the shipped law as in cpp:558.

| what | L | derived gain | derived dB | shipped gain | shipped dB | Δ dB |
|---|---|---|---|---|---|---|
| Piano PEAK (seg 0) | 229 | 0.324210 | −9.78 | 0.870551 | −1.20 | **−8.58** |
| Drum PEAK | 231 | 0.353553 | −9.03 | 1.000000 | 0.00 | **−9.03** |
| Bass PEAK | 213 | 0.162105 | −15.80 | 0.287175 | −10.84 | −4.97 |
| Piano SUST1 (seg 1) | 72 | 0.000361 | −68.86 | 0.000016 | −95.73 | **+26.87** |
| Piano SUST2 (seg 2) | 64 | 0.000255 | −71.87 | 0.000009 | −100.54 | **+28.67** |
| Drum SUST1 = SUST2 | 116 | 0.002426 | −52.30 | 0.000345 | −69.24 | +16.93 |
| Bass SUST1 = SUST2 | 138 | 0.006291 | −44.03 | 0.001586 | −55.99 | +11.97 |
| release target | 139 | 0.006570 | −43.65 | 0.001700 | −55.39 | +11.74 |
| voice-manager threshold | 128 | 0.004079 | −47.79 | 0.000793 | −62.01 | +14.22 |
| terminal target | 0 | 0.000016 | −95.95 | 0.000000 | −139.08 | +43.12 |
| unity / pre-note | 255 | 1.000000 | 0.00 | 1.000000 | 0.00 | 0.00 |

Two separate defects:

1. **`K = 10` is 1.6× too steep.** It implies 153.5 dB across the register — 57 dB more than the
   chip's own amplitude domain can express (§2.3). Every *difference* between two levels is
   overstated by 60 %.
2. **`REF = 231` is not the ceiling.** The firmware's clamp is `[0, 0xFF]` (`LABEL_023328` asm
   L15237-15248) and the fader tables top out at 255, so 231 saturates 25 codes; expressed in
   velocity (the audit's fit `L = 156.8 + 0.7343·vel`, touch mode 6) that is **26 of 127 velocities
   rendering identically**.

Velocity response, same fit, both laws:

```
   vel   2  ->  L=158.3  derived -36.40 dB   shipped -43.79 dB
   vel  40  ->  L=186.2  derived -25.90 dB   shipped -26.99 dB
   vel  64  ->  L=203.8  derived -19.27 dB   shipped -16.38 dB
   vel 100  ->  L=230.2  derived  -9.32 dB   shipped  -0.46 dB
   vel 127  ->  L=250.1  derived  -1.86 dB   shipped   0.00 dB   (clipped from vel 102 up)
   span vel 2..127:      derived  34.54 dB   shipped  43.79 dB (of a nominal 55.3, clipped)
```

**The derived law also happens to be the one the AMPLITUDE audit guessed at.** Its GAP 3 listed
`K = 16.05 (0.375 dB/unit) → 34.4 dB` as the "musical" alternative to K = 10. That number is now
**derived**: it is exactly 16, and the velocity span is 34.54 dB.

### 2.7 What is still free — and it is one scalar, not a curve

`gain(255) = 1.0` is the register's arithmetic ceiling, not a proven 0 dBFS point. The chain from
level to the DAC also passes through `+0x080` (a second, finer log amplitude — §2.3) and `+0x0C0`
(the per-patch scalar, registers-audit GAP 5), neither of which the HLE applies. So a **single global
headroom scalar** remains undetermined. Two facts bound it:

* Adopting the derived law without any make-up drops a single mf note by **8.58 dB** versus today's
  build. That is not a regression of *direction* or *audibility* (velocity ordering and dynamics are
  unchanged and improved), and today's build already peaks at 32654/32767 with **no** headroom, so
  the drop is in the right direction for the chord-clipping watch item.
* It must be applied **after** the EG, never folded into `REF` — folding make-up into `REF` is what
  turned the shipped constant into a silent limiter (§2.6 defect 2).

---

## 3. LAW (b) — RATE byte → segment time

### 3.1 The word layout — MEASURED

```
    +0x800 / +0x840 / +0x880  =  (target_level << 8) | (bit7 flag) | rate[6:0]
```

* Note-on path never sets bit 7: `RATE[]` maxes at 127 (§1) and the alternate builder ORs the literal
  `0x7F` (asm L19399).
* The software update path always sets it and always leaves the rate 0:
  `LABEL_02682F` (asm L20831-20838) `WA = IZ; SLA 8,WA; SET 7,WA -> +0x800` and
  `WA = IZ; SLA 8,WA -> +0x840`. LIVE: `0xFF80`, `0x8B80`, `0xA280` — bit 7 set, rate 0, in every
  case.
* **Bit 7's meaning is NOT decoded.** It cleanly separates "note-on programmed the EG" from
  "software is commanding a level", which is all that can be said from the ROM. (The HLE already uses
  exactly that discrimination at cpp:585 and it is correct as a *discriminator*.)

### 3.2 rate 0x7F = fastest, rate 0 = HOLD — MEASURED

Three independent facts, none of which needs the chip:

1. **`0x7F` is hard-coded as the attack rate** in `LABEL_025A9E` (asm L19399, literal `OR BC,007fh`)
   and is the value in the firmware's neutral default word `0xFF7F` (`LABEL_0272A3` asm L21915,
   `LDW (0451E4h),0ff7fh`). A hard-coded, always-used attack value must be the "no ramp / as fast as
   possible" end.
   LIVE: `+0x800` low byte = `0x7F` on the piano's two partials, the drum and the bass, and in
   285/285 note-ons of the register audit's census.
2. **`0` is forbidden where the envelope must move, and allowed only where it must stop.**
   DECAY1's rate is `max(rate, 4)` (asm L19424-19427) and again `clamp(·,4,127)` after key follow
   (asm L19304-19307); DECAY2's is `clamp(·,0,127)` (asm L19309-19312) and is simply omitted (=0)
   when the descriptor's "has DECAY2" bit is clear (asm L19463-19467). A firmware that refuses to put
   0 on the segment that must ramp, and defaults to 0 on the segment that must not, is telling you
   0 means *stop*.
3. LIVE: `+0x880` (DECAY2) is `xx00` on 197/197 rhythm note-ons with `SUST2 == SUST1` — "hold here",
   consistent with (2).

Consequence for the HLE: a segment with rate 0 freezes the EG at that segment's level. **This is what
lets a held note sustain** (§4) and it is derived, not chosen.

### 3.3 The clock that would count the ticks — MEASURED (ROM) and MEASURED (live)

| what | rate | period |
|---|---|---|
| timer ISR — payload handler-table entry `INT_HANDLER_14` → `LABEL_01FB41` (asm L295, L9454) | **488.28 Hz** | 2.048 ms |
| audio tick — `SET 1,(103Eh)`, 1 of the 6 round-robin phases (`OFFSETS_F460` asm L562) | **81.38 Hz** | 12.288 ms |
| `Audio_Process_Init` path A / path B (alternating, asm L38151-38160) | **40.69 Hz** | 24.576 ms |

Derivation from the ROM alone: of the four 8-bit timers only **timer 1** is started —
`SET 1,(T8RUN)`, asm L9330, and TREG0/2/3 are loaded but their run bits never set (asm L9321-9331).
`T01MOD = 0x1D` selects φT256 as timer 1's clock; `TREG1 = 0x14` = 20. With fSYS = 20 MHz (10 MHz
XTAL × the CPU's internal doubler, `kn5000.cpp:1016`) and φT256 = fSYS/2048:
20e6 / 2048 / 20 = **488.28 Hz**.

**PREDICT-THEN-CHECK: HIT.** Live measurement (`scratchpad/tickrate.lua`, sampling the ISR's own
32-bit counter at sub-CPU RAM `0x1040`, three 10 s windows): 488.307 / 488.307 / 488.276 Hz.

A third, purely-static confirmation: `Audio_Main_Loop` un-mutes the output when `(1040h) > 0x3E8`
(asm L9422-9425) — 1000 ticks = **2.048 s** of power-on mute. A round number falls out.

### 3.4 Correction — the software counters are one-shot DELAYS, not envelope ramps

The task brief and `notes/kn5000-envelope-engine.md` §2 both describe `slot[+0x2f]` as an envelope
counter with a coarse half that rewrites the chip level every segment. Re-read against the ROM:

* `slot[+0x2f]` is **seeded as a byte**: `LABEL_03421E` (asm L37174) returns `L`, stored
  `LD A,L; EXTZ WA; LD (XIZ+02fh),WA` (asm L27198-27200). Value range `0x0000..0x00FF`.
* **No instruction in the payload ever sets bit 15 of `slot[+0x2f]`.** All 29 references to offset
  `02fh` were enumerated: one read (L21472), one store (L21508), five `LDW …,0000h`, one
  `ORW …,0080h` (L29374), one seed (L27200), the rest are `CP` against a *different* struct. So the
  coarse half of `LABEL_026E5B` — the `SUB IZ,0100h` / `ToneGen_WriteSingleReg` / `LABEL_022587`
  branch — **never executes in v142.**
* The surviving half is `bit7 = armed`, `bits6:0 = countdown`, decremented once per audio tick, and
  it fires `LABEL_02CD71` **once**. It is armed at note-*off* (`CPW (XBC+02fh),0; ORW (XBC+02fh),
  0080h`, asm L29372-29374) — i.e. it is a **release delay in audio ticks**, N × 12.288 ms, N ≤ 127
  (≤ 1.56 s).

This is what the AMPLITUDE audit measured as its MISS 2 ("the write fired once per note; `+0x800`
never ramped"). The mechanism is now explained: there is no software ramp to find. **The entire
amplitude contour lives in the chip**, which is exactly why (b) is not in the ROM.

### 3.5 The seconds are NOT in the ROM — the positive argument

1. **The firmware never needs them.** `LABEL_02219F`/`LABEL_02222A` (asm L13273-13361) discover
   segment completion and voice death by *reading the chip*: the per-bank active-voice bitmap
   (latch = bank 0..3) and the per-voice level (latch = voice + 0x180). A design that polls does not
   carry a rate→time table.
2. **A full scan found none.** Every 16-bit run in the sub ROM with a near-constant ratio over ≥ 12
   entries was extracted and fitted (§7). Eleven exist; all are pitch/LFO tables reachable from
   `LABEL_033B8B` (asm L36688-36714) and `LABEL_022E8A` (asm L14812-14829), at exactly 8.00 or 16.00
   steps per doubling. None is indexed by a rate byte and none is in seconds.
3. **The chip is undumped.** IC303 = Matsushita `TC183C230002`; its EG clock and rate decode are
   internal.

### 3.6 What *is* derivable: a linear rate law is FALSIFIED

Take the MEASURED note-on words (registers audit §1.7) and suppose `speed = rate · R` level-units/s:

```
   Piano   ATK 127 over 229 units  |  DECAY1 76 over 157 units   ->  t_dec / t_atk = 1.15
   Drum    ATK 127 over 231 units  |  DECAY1  4 over 115 units   ->  t_dec / t_atk = 15.8
```

Under a linear law the **piano's whole decay would be 13.7× shorter than the drum's**, and only 15 %
longer than its own attack. A drum's DECAY1 rate of 4 is the clamp floor — the patch asked for *no*
decay and the firmware bumped it to the minimum — so the drum's decay segment must be long enough not
to choke a sample that rings for a few hundred ms; that forces the piano's entire decay under 100 ms.
**FALSIFIED.**

Solving the same two anchors for an exponential encoding `speed = V0 · 2^(rate/D)` — attack
between 2 and 10 ms, held piano still audible (within 40 dB of its peak) for 4 to 10 s — gives

```
   D = 3.8 .. 7.7 rate counts per doubling   (18-point sweep, §7)
   D = 3.8 .. 4.7 if the attack ramps the full 229 units in 2-5 ms
```

i.e. the encoding **must be exponential, with roughly 4 rate counts per doubling of speed**. That is a
bound, MEASURED-anchored at the register end and musically-anchored at the time end; the exact base
is **SPECULATIVE** (4 counts/doubling is also the classic FM-chip EG encoding, which is suggestive
and nothing more).

### 3.7 The parameterised law, its one CALIBRATED constant, and the experiment that kills it

```
    rate == 0            ->  HOLD (segment does not move; EG stops here)         [DERIVED]
    otherwise:
        t(dL, rate) = (dL / 255) * T127 * 2^((127 - rate) / D)                   [FORM: INFERRED]
        dL   = |target - current level|, in level units
        T127 = time for the fastest rate to traverse the full 255-unit range     [CALIBRATED]
        D    = rate counts per doubling of speed, bounded to 3.8..7.7            [CALIBRATED]
```

Placeholder to keep the workflow moving — **label it in the source as CALIBRATED, not derived**:

```
        D    = 4          (tight end of the derived bound; standard hardware encoding)
        T127 = 3.4 ms     (chosen so the Piano's attack is ~3 ms and its decay ~10 s to -40 dB)
```

**The measurement that replaces both constants.** Two recordings on Felipe's real KN5000, ~20 min:

1. Hold one note on `PIANO` (`RIGHT1`) at a fixed velocity, record until silent. Measure the time
   from the attack peak to −40 dB. That is `t(106 units, rate 76)`.
2. Repeat on a patch whose DECAY1 rate differs strongly — `STRINGS` or `ORGAN` (slow) is ideal;
   verify the rate by re-running the register capture (§7) and reading `+0x840`'s low byte.

Two equations, two unknowns: `D = (r2 - r1) / log2( t1·dL2 / (t2·dL1) )` for the two measured rates
`r1 > r2`, then `T127` from either point.
A third recording at a third rate over-determines it and validates the exponential form itself — if
the three points do not lie on a line in `(rate, log t)`, the form is wrong and should be reported
as such rather than forced.

---

## 4. SANITY (c) — the MEASURED Piano / Drum / Bass envelopes under the two laws

MEASURED note-on words (registers audit §1.7, LIVE):

```
   register             +0x800              +0x840              +0x880
   word  = (level<<8)|rate    PEAK / ATK       SUST1 / DECAY1      SUST2 / DECAY2
   Piano  C4                  E5 / 7F            48 / 4C             40 / 00
   Drum   v0                  E7 / 7F            74 / 04             74 / 00
   Bass   v1                  D5 / 7F            8A / 04             8A / 00
```

Applying (a) to the targets and (b) to the rates (with the §3.7 placeholder for the two calibrated
constants):

### Piano — a piano

```
   gate         ATK at rate 127 -> PEAK 0xE5 = -9.78 dB
                    ~3.1 ms if the EG starts from silence (229 units)
                    ~0.3 ms if it starts from the pre-note 0xFF80 write (26 units) -- which of the
                    two is right depends on bit 7's undecoded meaning (§3.1); either is instant
   DECAY1       rate 76, target SUST1 0x48 = -68.86 dB
                    -20 dB below peak after ~4.9 s
                    -40 dB below peak after ~9.7 s
                    reaches SUST1                  after ~14.4 s
   DECAY2       rate 0 -> HOLD at SUST2 0x40 = -71.87 dB, forever
   key-up       LABEL_026769 rewrites seg0/seg1 to 0x8B = -43.65 dB
```

**A HELD PIANO NOTE SUSTAINS.** It is at −10 dB at onset, −30 dB after 5 s, −50 dB after 10 s, and
then genuinely over — the contour of a real piano string, not a decay to inaudibility. Under the
**shipped** law the same three registers read −1.2 / −95.7 / −100.5 dB, i.e. the note would fall
94 dB in one segment: that is the failure mode the task flagged, and it is caused by the constants,
not by running the EG.

### Drum / Bass — the sample carries the contour, the EG stays out of the way

```
   Drum   ATK -> -9.03 dB instantly;  DECAY1 rate 4 -> 115 units would take ~32 days;
          DECAY2 rate 0 -> HOLD.   Effect: a flat -9 dB gate for the sample's whole life.
   Bass   ATK -> -15.80 dB;          DECAY1 rate 4 -> ~21 days;  DECAY2 HOLD.
```

`SUST1 == SUST2` in **197/197** rhythm note-ons and DECAY1 pinned at the clamp floor 4 both say the
same thing: **rhythm and accompaniment patches program no decay at all.**

**Cross-workflow consequence, important for GAP LIFE-1.** A rhythm voice's EG never falls, so *the
EG cannot be what frees rhythm voices*. `LABEL_02222A` (asm L13317-13333) frees a voice only when it
**drops out of the per-bank active-voice bitmap** — which for a one-shot percussion sample can only
mean *the sample reached its end*. So an honest `status_r` must clear a voice's bitmap bit when
**either** the EG has reached true silence **or** a non-looping sample has run out. Reporting silence
from the EG floor alone will still leak all 64 voices during a rhythm.

**And it must not use the −47.8 dB threshold as the silence floor.** That threshold (§2.4) drives
`LABEL_021E83` — *advance the stage* — not the free path; a held piano legitimately spends seconds
below it. The bitmap bit should track true silence (level ≈ 0 / terminal), which is what protects the
MUST-NOT-REGRESS "held notes sustain" item.

---

## 5. PREDICT-THEN-CHECK log (misses included)

| prediction | result |
|---|---|
| the 101-entry level table's neighbours would also be 101 entries (contiguous fader/rate family) | **HIT** — `0x011899`, `0x0118FE`, `0x011963` are exactly back-to-back, 101 each |
| table `0x010764` would be an exponential (antilog) | **MISS** — it is a *logarithm*: `128·log2(float8(i))`. The miss is what produced the law: reading it as float8→log is what fixes 16 counts per octave |
| the sub ROM would contain a rate→time table somewhere | **MISS (informative)** — 11 exponential tables exist, all LFO/pitch, none indexed by a rate byte. The firmware polls instead |
| the ISR would be timer 1 at fSYS/2048/20 = 488.28 Hz | **HIT** — 488.307 / 488.307 / 488.276 Hz over three 10 s windows |
| `slot[+0x2f]`'s coarse half drives a per-tick level ramp (task brief, envelope-engine note §2) | **MISS** — bit 15 is never set anywhere in the payload; the branch is dead code. Explains the AMPLITUDE audit's MISS 2 |
| the EG rate is key-scaled (read out of `LABEL_02591D` first) | **HIT** — the main-CPU GUI has a dedicated `ENVELOPE / KEY FOLLOW / ATK / DECAY / RELEASE` page (main ROM file `0x11217D`) |
| `+0x8C0` is EG-A segment 3 (registers audit §1.6) | **FALSIFIED here** — its low byte is a signed ±128 bipolar value through `BIPOLAR[0x0119C8]`, not a `[0,127]` rate. Role undecoded |
| a linear rate→speed law | **FALSIFIED** by the Piano/Drum register pair (§3.6) |

---

## 6. Corrections this note makes to earlier notes

* `notes/kn5000-envelope-engine.md` §2/§3 — the "software amplitude envelope" that "rewrites the
  IC303 level register every audio tick" does not run: the coarse counter is never armed (§3.4).
  `slot[+0x2f]` is a one-shot **release delay** in 12.288 ms audio ticks.
* `notes/audit/kn5000-audit-registers.md` §1.6/§1.7 — `+0x8C0` is not EG-A segment 3 (§1.3 above).
  The EG has **three** programmed segments; the release is delivered by rewriting segments 0 and 1.
* `notes/audit/kn5000-audit-amplitude.md` GAP 2/GAP 3 — `REF = 255` is confirmed and `K` is no longer
  a free constant: `K = 16` exactly. The proposed service-mode "16 dB DOWN" capture is no longer
  needed for `K` (it would now be a *check*: 16 dB should move `+0x800` by 42.5 level units).
* `kn5000_tonegen.cpp:496-501` — the comment "K and REF are CALIBRATED (the chip's exact dB/step is
  internal to the undumped IC303)" is now false for the level law. The dB/step is in the sub-CPU ROM.

---

## 7. Reproduction

All static work is stdlib Python over the two ROM images; all of it is a few lines.

```python
rom = open('kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom','rb').read()
off = lambda a: a - 0xEF00                       # address -> file offset

LVL_A = rom[off(0x011899):off(0x011899)+101]     # level fader A (PEAK)
LVL_B = rom[off(0x0118FE):off(0x0118FE)+101]     # level fader B (SUST1/SUST2, updates)
RATE  = rom[off(0x011963):off(0x011963)+101]     # parameter -> rate byte
BIPOL = rom[off(0x0119C8):off(0x0119C8)+51]      # signed +-50 -> +-128
CAP   = rom[off(0x011ADF):off(0x011ADF)+9]       # 3.01 dB limiter positions

# THE LAW: table 0x010764 is float8 -> 128*log2, exactly, 256/256
import struct, math
T = [struct.unpack_from('<H', rom, off(0x010764)+2*i)[0] for i in range(256)]
assert all(T[i] == round(128*math.log2((2**(i>>4))*(1+(i&15)/16))) for i in range(256))
```

Exponential-table scan (§3.5 point 2): walk every 2-byte-aligned run of non-zero u16, keep maximal
sub-runs whose successive ratios stay within 3 % of the first ratio for ≥ 12 entries and span ≥ 8×,
then least-squares `log2(v)` vs index. Eleven hits, all LFO/pitch:
`0x010980` (17.35/oct, poor fit), `0x010A8A` (20.1, poor), `0x011042` **8.025**, `0x0110FC` **8.014**,
`0x01114C` **8.009**, `0x0111BE` **8.011**, `0x01127A` **16.0005** (max rel. err 0.21 %),
`0x011360` **8.010**, `0x0113D8` **8.037**, `0x011416` **15.976**, `0x0114EC` (5.64, poor).

Live tick-rate measurement (§3.3): `scratchpad/tickrate.lua` — samples sub-CPU RAM `0x1040` (the
ISR's own 32-bit counter, `ADD (1040h),XWA` asm L9458) at t = 12/22/32/42 s and divides.

```bash
cd ~/compartilhado/kn7000-emulator
OUT=$S/tickrate timeout 300 ./kn7000 kn5000 -rompath roms -window -nomaximize -skip_gameinfo \
  -nvram_directory $S/nvtick -autoboot_script $S/tickrate.lua -autoboot_delay 0 \
  -video opengl -sound none
```

(Isolated nvram copy; `kn7000-emulator/nvram` untouched; no rebuild — this pass changed no source.)
