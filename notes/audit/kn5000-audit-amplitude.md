# KN5000 IC303 HLE audit — dimension: AMPLITUDE / ENVELOPE / VELOCITY

Author: autonomous audit pass, 2026-07-26. Requested by Felipe Sanches.

Scope: the sub-CPU "software EG" (`LABEL_026E5B` amplitude / `LABEL_026EC3` expression) versus the
HLE's `env_level`; the `reg[20]` (+0x800) level polarity and the `K=10 / REF=231` calibration; the
key-bed velocity curve (`ToneGen_Calc_Pitch`, tables T1 / TOUCH / T2) and the driver's inverse
`KEYBED_TIME[]`; the expression register +0x180; the panel TOUCH SENSITIVITY setting.

Evidence labels: **MEASURED** (read from the ROM bytes / disassembly, or from a live capture made
for this audit), **INFERRED** (deduction from measured facts), **SPECULATIVE** (unproven).

Sources
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
  (`LABEL_0xxxxx` = runtime address).
* ROM `kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom` (196 608 B).
  **Address → file offset = `addr − 0xEF00`** — pinned by locating `Voice_AttackDecay_Widths`
  (`20 10 04 0C 00×12 40 40`, asm L609) at file offset 0x607 ↔ documented address 0xF507, and
  `Voice_EnvelopeRate_Lookup` at 0x619 ↔ 0xF519. 2/2.
* HLE `kn7000_mame/src/mame/matsushita/kn5000_tonegen.{cpp,h}`, driver `kn5000.cpp`
  (line numbers as of commit `e8f2be9`; symbol names given too, since the file is being edited
  concurrently by the other audit dimensions).
* **Live captures made for this audit** (isolated nvram copy; `kn7000-emulator/nvram` untouched) —
  see §5.

Cross-dimension: this note deliberately does **not** re-litigate gaps already filed by the
concurrent VOICE-LIFECYCLE audit (`notes/audit/kn5000-audit-voicelife.md`). Where we overlap I say
so and add only the amplitude-specific measurement. One of its findings (its GAP 6 `{rate, signed
target}` hypothesis for +0x800) is **contradicted** by evidence from this dimension — see §3 GAP 4
and §6.

---

## 1. What the FIRMWARE does (MEASURED, cited)

### 1.1 The key-bed byte is a TIME, and the velocity curve is fully in ROM

`ToneGen_Read_Voice_Data` (0x03D0C5, asm L51500) reads the 16-bit key-bed word at **0x110000** as
`{high = E, low = L}`; `E == 0xFF` is the note-off marker, `L` bit 7 set = note-on. `ToneGen_Calc_Pitch`
(0x03D11F, asm L51556-51637) converts `E` to a MIDI velocity. Transcribed exactly:

```
note = (L & 0x7F) + 0x24                         ; asm L51557-51560   (MIDI = raw + 36)
if !(L & 0x80): velocity = 0; return             ; asm L51561-51562   (note-off)
x    = T1[E]                                     ; asm L51565-51566   table 0x01F43E
y    = (TOUCH[mode].gain * (x - K0)) / K1        ; asm L51570-51586   signed MULS/DIVS
z    = y + TOUCH[mode].offset                    ; asm L51587-51594
if (note % 12) in {1,3,6,8,10}:                  ; asm L51596-51612   << the FIVE BLACK KEYS
        z -= TOUCH[mode].black                   ; asm L51613-51621
z    = clamp(z, 0, 255)                          ; asm L51622-51636
velocity = T2[z]                                 ; asm L51635-51638   table 0x01F53E
```

All five constants dumped from the ROM (MEASURED):

| symbol | address | file offset | contents |
|---|---|---|---|
| `K0` | 0x01F418 | 0x10518 | word **77** (0x4D) |
| `K1` | 0x01F41A | 0x1051A | word **128** (0x80) |
| `TOUCH` | 0x01F420 | 0x10520 | 10 modes × 3 bytes `{gain, offset, black-key trim}` |
| `T1` | 0x01F43E | 0x1053E | 256 B, monotone **DECREASING** 255…0 |
| `T2` | 0x01F53E | 0x1063E | 256 B, monotone **INCREASING** 1…127 |

The three tables are exactly contiguous (0x01F420 + 30 = 0x01F43E; 0x01F43E + 256 = 0x01F53E),
which independently confirms their sizes.

```
TOUCH[]   gain  off  black          reachable velocity (white / black key)
 mode 0     0   208    0            80 .. 80   (TOUCH OFF: one fixed velocity)   /  80..80
 mode 1    16   199    3            62 .. 93                                     /  59..90
 mode 2    32   189    6            42 ..105                                     /  36..99
 mode 3    48   180    8            24 ..118                                     /  16..110
 mode 4    64   171   11            13 ..127                                     /  10..121
 mode 5    80   161   14             7 ..127                                     /   4..127
 mode 6    96   152   16             2 ..127   << power-on default               /   2..127
 mode 7   112   143   19             2 ..127                                     /   2..127
 mode 8   128   134   22             2 ..127                                     /   2..127
 mode 9   144   130   24             2 ..127                                     /   2..127
```

`T1` being **decreasing** is the proof that the key-bed byte is a make-to-break **TIME** (short time
= hard strike). `TOUCH[mode].black` is a per-key-colour mechanical compensation: the black keys of a
real 61-key bed travel differently, so the firmware subtracts a mode-scaled trim for `note % 12 ∈
{C#,D#,F#,G#,A#}`. At mode 6 the trim costs **16 index units ⇒ −16 velocity** across most of the
range (MEASURED: mean −13.7 over all 127 velocities, max −16).

### 1.2 TOUCH SENSITIVITY = sub-CPU byte `*(0x4A48)`

* `ToneGen_Init` (0x03D016, asm L51416) sets `*(0x4A48) = 6` at payload start-up.
* `Audio_CmdHandler_A0_BF` (asm L51386-51401), reached from `CMD_DISPATCH_TABLE` entry 5
  (asm L579 — command bytes **0xA0-0xBF**, dispatched on bits 7:5), accepts a payload
  `{0x01, n}` with `n ≤ 9` and stores `*(0x4A48) = n`. Payload `{0x00, 0x01}` sets `*(0x4A4A) = 1`
  (note echo back to the main CPU by DMA).
* The main-CPU UI strings `OVERALL TOUCH SENSITIVITY` (ROM 0xED3D4A and 0xED441C) and
  `INITIAL TOUCH` (0xED4524) are the pages that would drive it.

### 1.3 The per-voice LEVEL — `LABEL_026769` (0x026769, asm L20754-20842)

This is the routine that builds what the HLE reads as `regs[20]`. Transcribed:

```
part = voice[+0x17]                              ; partial parameter block
rec  = voice[+0x23]                              ; tone record
i    = clamp(part[+0x2d] + (int8)rec[+0x6c], 0, 100)   ; L20765-20775, clamp = LABEL_022B19 (L14379, BC=100 DE=0)
IZ   = LOG[i]                                    ; L20776-20780   table 0x0118FE
if rec[+0x0a] bit0 and !(voice[+1] bit8):        ; L20781-20790
        IZ = min(IZ, LOG[CAP[rec[+0x18]]])       ; L20791-20800   CAP = table 0x011ADF
if part[+0x35] != 0:                             ; velocity scaling — LABEL_022BB8 (L14463)
        v   = clamp((voice[+8] >> 8) & 0x7F, part[+0x31], part[+0x32])
        IZ += (int8(part[+0x35]) * (v - part[+0x30])) >> 5
        IZ  = clamp(IZ, 0, 255)                  ; L20828  -> LABEL_023328 (L15237): [0, 0xFF]
struct[+0x2C] = (IZ << 8) | 0x0080               ; L20831-20835  -> register +0x800
struct[+0x2E] = (IZ << 8)                        ; L20836-20839  -> register +0x840
```

**LOG table 0x0118FE (file 0x29FE), the reachable window `i = 0..100` (MEASURED):**

```
i:    0   1   2   3   4   5   6   7   8   9  10  11  12 ...  94  95  96  97  98  99 100
LOG: 255 248 241 237 233 231 229 227 225 222 218 214 210 ...  46  42  38  30  22  16   4
```
A gentle −2/step over most of the travel with a plunge to near-zero at the far end — the shape of a
fader, not of a gain. Combined with `IZ = min(IZ, LOG[CAP[…]])` reading as a **maximum-loudness
limiter**, and with the release recomputation dropping it (§1.6), the table's **output is a
log-domain LEVEL, higher = louder**, and its **input is an attenuation-like 0..100 parameter**.

**The firmware's own ceiling is 255**: `LABEL_023328` (asm L15237-15248) clamps the final value to
`[0, 0xFF]` with an *unsigned* `CP BC,0FFh`. There is no other bound.

### 1.4 There are THREE level pairs, all built the same way

| builder | asm | writes to sub-RAM | reaches registers |
|---|---|---|---|
| `LABEL_026769` | L20831-20839 | 0x0451F8 / 0x0451FA (= struct +0x2C/+0x2E) | **+0x800 / +0x840** |
| `LABEL_026975` | L21083-21088 | 0x0451FC / 0x0451FE (= struct +0x30/+0x32) | +0x900 / +0x940 |
| `LABEL_026AAA` | L21215-21220 | 0x045200 / 0x045202 (= struct +0x34/+0x36) | +0x9C0 / +0xA00 |

All three pack `(IZ << 8) | low`. `LABEL_02D436` (asm L29936) is the burst that ships all six.
`LABEL_026BDC` (asm L21222-21236) is the "silence" variant: it zeroes the two *other* pairs and
keeps only `(voice[+0x46] << 8) | 0x80` on +0x800 — i.e. silencing is done by zeroing the
sends, not by zeroing +0x800.

Consequence for the HLE: `regs[20]` is the correct single amplitude source; `regs[2]` must **not**
be multiplied in a second time (the current code is right about this — see §4).

### 1.5 The group-0/bank-0 word is a COMMAND, and its low byte is NOT an amplitude

`LABEL_025589` (asm L18856-18906) builds `voice[+0x2d]`:

```
p    = part[0]
mag  = 0x00FF - ((p & 0x3F) << 2)        ; bits 7:0 -> 0xFF down to 0x03
if p != 0: SET bit8                      ; asm L18869
word = mag | 0xF000  or  mag | 0xFE00    ; asm L18885/18891/18897, mode *(0x04134C) in {0,5,6}
word = LABEL_02552A(word)                ; asm L18813-18855: ORs 0x0E00 / sets bit9 /
                                         ;  ORs 0x7000 / sets bit12, from part flags at 0x04138D
```
and `LABEL_0255F3` (asm L18907-18942) — used by voices with **no partial block** — writes a bare
`0xF000` / `0xFE00`, i.e. **magnitude 0x00**.

`LABEL_02552A` only ever touches bits 9-12; the magnitude occupies bits 7:0 and bit 8 is an
independent flag. Because bit 8 is set *exactly when* the magnitude is below 0xFF, **bit 8 set ⟺
magnitude < 0xFF**.

**MEASURED in two live captures — this field never carries an envelope.** Across the 68 register
writes of one held C4 and the 988 writes of a running 16-Beat-1 rhythm, group-0/bank-0 took exactly
**three** values: `0x8100` (gate), `0xF0FF` (keybed piano) / `0xF000` (every one of 38 rhythm
voices), `0x7E00` (idle). Never a ramp, never an intermediate value.

Since the rhythm's drums must be audible on the real instrument and every one of them is commanded
with magnitude `0x00`, **the low byte cannot be a linear amplitude**. Its meaning is *not decoded*.

### 1.6 The "software EG" writes far less than `kn5000-envelope-engine.md` claims

`LABEL_026E5B` (0x026E5B, asm L21467-21512) is the amplitude stepper. Re-read against the capture:

```
IZ = voice[+0x2f]
if bit15(IZ):  IZ -= 0x0100
               if (IZ & 0x7F00) == 0:      ; only when the COARSE counter expires
                       ToneGen_WriteSingleReg(voice, voice[+0x2d])   ; asm L21486
                       LABEL_022587(voice) ; advance stage
                       RES 15, IZ
if bit7(IZ):   IZ -= 1
               if (IZ & 0x7F) == 0: LABEL_02CD71(voice)   ; load next segment
voice[+0x2f] = IZ
```

**PREDICT-THEN-CHECK — MISS.** `notes/kn5000-envelope-engine.md` §2 states the stepper "rewrites the
IC303 level register **every audio tick**" and that this "is the software amplitude envelope". The
register stream falsifies it: the write is gated on a coarse counter reaching a segment boundary,
and in both captures it fired **once per note**. Neither did the +0x800 level ramp: a whole note is
2-3 level writes (pre-note, note-on, key-up). **There is no per-tick software amplitude ramp in the
register stream.** The prior note's mechanism reading was right; its *rate* claim was not.

What the level actually does, MEASURED on one C4 (voice 0, default `Piano`):

```
t=14.426357  +0x840 = FF00     pre-note pair (Voice_NoteOff on the channel, asm L28660-28680)
t=14.426360  +0x800 = FF80
t=14.426839  +0x800 = E57F     note-on burst  -> level 0xE5 = 229
t=14.426841  +0x000 = 8100     GATE
t=14.427392  +0x000 = F0FF     command word, magnitude 0xFF
   (1.6 s of held note: NOT ONE further write to any level register)
t=16.035777  +0x800 = 8B80     key-up        -> level 0x8B = 139
t=16.035767  +0x840 = 8B00
t=16.118876  +0x0C0 = 0000     teardown, 83 ms later
t=16.118878  +0x000 = 7E00
```
`0x8B80` / `0x8B00` is **exactly** `(IZ<<8)|0x80` / `(IZ<<8)` with `IZ = 0x8B` — §1.3's formula,
predicted then confirmed. **HIT.**

### 1.7 The expression domain — `LABEL_026EC3` (0x026EC3, asm L21513-21770)

A second stepper on `voice[+0x31]/[+0x35]`, writing register **+0x180** through `LABEL_02D670`
(0x02D670, asm L30169: `addr = voice + 0x180`). It runs a genuine per-tick **accumulator**:
`IZ = voice[+0x33] + voice[+0x36]` (or `+0x38` in the 0x1000 branch), compared against `0xFF00`,
clamped against the ceiling `voice[+0x3a]`, stored back to `voice[+0x33]` (asm L21646-21694,
L21707-21760). At the branch limit it writes the constant pair `+0x840 = 0xFF00`, `+0x800 = 0xFF80`
(asm L21617-21627, L21728-21753).

### 1.8 IC303 is READ, and only through one door

The **only** IC303 readback in the whole payload is `DAC_Write_Sample` (asm L11479-11483):
`RES 7,(P6); LD (100000h),WA; LD HL,(100000h)` — latch a register index, read 16 bits back from
**0x100000**. There is no read of 0x100002 anywhere in the ROM.

`LABEL_02219F` (0x02219F, asm L13273-13360) uses it twice per tick:
* `WA = bank(0..3)` → the active-voice bitmap (asm L13279-13281);
* `WA = voice + 0x180` → **the voice's current envelope level**: `AND HL,3FFFh; SRL 5,HL;
  voice[+0x25] = L; if < 0x80 → advance the stage / steal` (asm L13312-13327).

**MEASURED**: on one held C4 the firmware performed 138 reads with a group-0/bank-0 latch and
**18-34 reads with a `g01.b2` (= +0x180) latch** — i.e. it really does poll the per-voice level.
Since the firmware waits for that value to *fall*, the chip owns a level that decays on its own
(INFERRED).

---

## 2. What the HLE does (file:line)

| concern | code | behaviour |
|---|---|---|
| envelope magnitude | `kn5000_tonegen.cpp:230` (`data_w`) | `env_level = min(data & 0x1FF, 0xFF)` (HEAD `e8f2be9`); a temporary audit patch in the working tree makes `0 → 0xFF` |
| where it is applied | `kn5000_tonegen.cpp:1526` (`sound_stream_update`) | `sample = sample * v.env_level / 0xFF` — a linear per-sample VCA |
| level → gain | `kn5000_tonegen.cpp:496-525` (`update_voice_params`) | `K = 10`, `REF = 231`, `gain = min(1, 2^((regs[20]>>8 − REF)/K))`, applied **instantaneously** to `volume_l/r`; pan hardcoded centre |
| release trigger | `kn5000_tonegen.cpp:252` | heuristic: any `group 9 / bank 0` write >1 ms after the gate |
| release shape | `kn5000_tonegen.cpp:1375, 1530-1540` | fixed 2400-sample (50 ms) linear fade |
| register readback | `kn5000_tonegen.cpp:296-316` (`status_r`) | **ignores the latched register**; always returns the keyed-voice bitmap for `bank = m_addr_latch & 3` |
| `data_r` (0x100002) | `kn5000_tonegen.cpp:277-292` | returns 0x8100/0x7E00 — dead code, the firmware never reads 0x100002 |
| expression +0x180 | — | stored as `regs[6]`, never read |
| velocity synthesis | `kn5000.cpp:311-319` `KEYBED_TIME[128]`, used at `kn5000.cpp:235` (MIDI) and `:443` (PC keyboard) | MIDI velocity → key-travel time byte, inverse of §1.1 at **touch mode 6, white key** |
| `sustain_vol` | `kn5000_tonegen.h:104,143` | declared and reset, **never read or written** — dead |

---

## 3. THE DELTA — numbered gaps

### GAP 1 — `env_level` mutes the entire auto-accompaniment section
**What is wrong.** `env_level = min(data & 0x1FF, 0xFF)` (cpp:230) applied as a linear VCA
(cpp:1526). Every rhythm / sequencer voice is commanded with group-0/bank-0 = `0xF000`
(§1.5, `LABEL_0255F3` asm L18907-18942) ⇒ `env_level = 0` ⇒ `sample * 0`.

**Audible consequence. MEASURED**, HEAD binary, `rhy.wav`: with the 16-Beat-1 rhythm running and
**38 voices gated on with valid wave selects and levels** (`+0x800` high bytes 202…231), the
rendered output peaks at **RMS 8.9** — −71 dBFS — versus **RMS 10 590** for a single keybed piano
note in the same build. The accompaniment is inaudible. The residual ~8 RMS is exactly the 2-sample
window between the gate and the `0xF000` that arrives 42 µs later.

**Firmware-derived fix.** Stop using this field as an amplitude. It is a **command parameter**
(bits 15:9 command, bit 8 flag, bits 7:0 parameter) whose meaning is not decoded: the same field is
`0x00` on voices that must sound and `0xFF` on voices that must sound. Keep it decoded and named,
and let the amplitude come from +0x800 (§1.3) alone.
*Note:* the VOICE-LIFECYCLE audit's GAP 8 proposes `env_level = data & 0xFF`; that alone would
**not** fix this — the drums would still be multiplied by 0. Its temporary working-tree patch
(`mag ? min(mag,0xFF) : 0xFF`) does unmute them and is the right stop-gap.
**Confidence: MEASURED** (registers, code path and audio).

### GAP 2 — `REF = 231` is not the firmware's ceiling; it flattens the top 20 % of the velocity range
**What is wrong.** cpp:499 sets `REF = 231` and cpp:517-518 clamps `gain` at 1.0. The firmware's own
ceiling for this byte is **255** (`LABEL_023328`, asm L15237-15248, clamps to `[0,0xFF]`; the log
table's maximum output is 255 at index 0). Everything from 231 to 255 — a quarter of the register's
range — renders identically at full scale.

**Audible consequence. MEASURED** by sweeping the firmware's own touch curve (§5, `sweep.stream`):
one key press, one time byte, `*(0x4A48)` stepped 0→9:

```
touch mode   0     1     3     5     6     7     9
fw velocity  80    83    90    96   100   104   116
+0x800 hi   217   219   222   225   229   233   244        <- MEASURED
HLE gain   0.379 0.435 0.536 0.660 0.871 1.000 1.000       <- clipped from mode 7 up
```
Least squares over those seven points: **`level = 156.8 + 0.7343 · velocity`** (residuals ≤ 2.3).
So `level ≥ 231` for **velocity ≥ 102**: **26 of 127 velocities (20.5 %) all render at exactly the
same loudness.** Playing harder above mf does nothing.

**Firmware-derived fix.** `REF = 255.0` — the register's own arithmetic maximum, enforced by the
firmware's clamp — and drop the `gain > 1.0` clamp (it becomes unreachable). Apply a documented
make-up gain downstream so normal notes keep their level, rather than folding the make-up into REF
where it silently becomes a limiter.
**Confidence: MEASURED** for the clipping and the fit; **INFERRED** that 255 is the intended unity
point (it is the arithmetic maximum, not a proven 0 dBFS).

### GAP 3 — `K = 10` is a fitted number, and the firmware contains an absolute dB anchor we have not used
**What is wrong.** cpp:496 `K = 10.0` — "reg[20] level units per amplitude halving" — is calibration,
not decode; the comment says so. Nothing in the sub-CPU ROM constrains it: the log table
(§1.3) is a linear −2 units per parameter step with no absolute reference, and the 9-entry cap table
0x011ADF steps 4 parameter units = 8 level units per position with, again, no dB label.

**Audible consequence.** K sets the *whole* touch range. At `REF = 255`:

```
K = 10.0   (0.602 dB/unit)   velocity 2..127 spans 55.3 dB
K = 16.05  (0.375 dB/unit)   velocity 2..127 spans 34.4 dB
K =  8.03  (0.750 dB/unit)   velocity 2..127 spans 68.8 dB
```
55 dB of velocity swing is well beyond a real acoustic instrument's; at K=10 the softest playable
note is 58 dB down and effectively inaudible in a mix. The per-mode ranges follow directly
(mode 1 = 13.7 dB, mode 3 = 41.6 dB, mode 6+ = 55.3 dB at K=10).

**Firmware-derived fix — the measurement that would settle it.** The main ROM's service menu
(strings at 0xED1790-0xED187E) has **`(1) SINE WAVE & ROM check (w/o TOUCH)`** and
**`(6) SINE WAVE & ROM check 16dB DOWN`**. Those two tests differ by a *stated 16 dB*. Enter the
check mode, capture `+0x800` in tests 1 and 6, and
```
K = 6.0206 · (level_1 − level_6) / 16
```
gives the chip's dB-per-unit from the manufacturer's own calibration. Until then K must stay
labelled CALIBRATED, and the value should at least be chosen so the total range is musical.
**Confidence: MEASURED** that K is unconstrained by the sub-CPU ROM; the service-mode anchor is
**INFERRED** (the string states 16 dB; that the attenuation is applied via +0x800 rather than in
the DSP or an analogue stage is not yet proven).

### GAP 4 — the level is applied instantaneously, so every note ends in a cliff
**What is wrong.** `update_voice_params` (cpp:462-527) turns `regs[20]`'s high byte into a gain on
the very next sample. The key-up burst drops it 229 → 139 in one write, i.e. −55 dB in one sample
under the current K/REF.

**Audible consequence. MEASURED**, `note.wav`, 10 ms RMS windows, key-up at t = 15.218:
```
t = 15.150   RMS 3415
t = 15.200   RMS 3247
t = 15.250   RMS    3.9      <- -58 dB in under 50 ms
t = 15.300   RMS    0.0
```
There is **no release tail on any sound**. (The 50 ms `release_counter` fade at cpp:1530 is
irrelevant: `volume_l` has already been slammed 3 µs earlier by the +0x800 write, so the fade only
shapes an already-inaudible signal.) The VOICE-LIFECYCLE audit reports the same cliff (its GAP 6)
from an independent capture; this is a second, independent measurement of it.

**Firmware-derived fix.** Make the level a **ramp target**, not an instantaneous gain, and let the
firmware's own polling decide when the note is over: model the +0x180 readback (§1.8) as the
voice's *current* level so `LABEL_02219F` sees it fall below 0x80 only when the ramp really has
decayed. That replaces two arbitrary constants (the 50 ms fade and the 100 ms hold) with one
calibrated slew rate and hands the timing back to the firmware, which is where the real instrument
keeps it.

**Contradicting the VOICE-LIFECYCLE GAP 6 hypothesis.** That note proposes
`+0x800 = {rate[15:8], signed target[7:0]}` because the pre-silence pair is `0xFF00/0xFF80` and the
panic pair `0xA200/0xA280`. Evidence from this dimension says the high byte is a **LEVEL**:
* `LABEL_026769` (asm L20831-20839) puts the *velocity- and patch-dependent, log-table-derived*
  quantity in the **high** byte and a **constant** in the low byte — `0x80` for +0x800, `0x00` for
  +0x840. Under the {rate, target} reading every note would target −128 (silence) and +0x840 would
  target 0, forever, with velocity only changing how fast it got there.
* MEASURED: the high byte tracks velocity monotonically (217→244 for velocity 80→116) and drops at
  release (229→139) — both are level behaviours, and both follow §1.3's formula numerically.
* The captured release word `0x8B80 / 0x8B00` is bit-exact `(IZ<<8)|0x80 / (IZ<<8)`.
The `0xFF80` pre-silence and `0xA280` panic values remain **UNEXPLAINED under either reading** and
are the open question; note that `LABEL_026BDC` (asm L21222-21236) silences a voice by zeroing the
other two bus pairs while leaving +0x800 at a non-zero level, which suggests +0x800 is simply not
the mute control.
**Confidence: MEASURED** for the cliff and for the construction of +0x800; **INFERRED** for the
ramp-target model.

### GAP 5 — the +0x180 expression register is written, polled, and completely absent from the HLE
**What is wrong.** +0x180 is `regs[6]` in the HLE's map (group 1, bank 2) and is never read. Two
distinct things are missing:
1. **The write path.** `LABEL_026EC3` (§1.7) runs a per-tick accumulator and pushes it to +0x180 via
   `LABEL_02D670`. MEASURED at note-on: voice 0 got `0x0000` and voice 1 (its second partial) got
   `0x007F` — the two layers of the same key press differ *only* here and in +0x080.
2. **The read path.** `status_r` (cpp:296-316) ignores the latched register and returns the
   keyed-voice bitmap for `bank = m_addr_latch & 3`. For latch `0x0180 + ch` the firmware therefore
   gets a bitmap; `(bitmap & 0x3FFF) >> 5` is 0 for any small voice number, so **every voice reads
   as "already decayed"** and is torn down at the first poll after key-up (MEASURED: 83 ms).

**Audible consequence.** Release length is a constant ~83 ms for every sound instead of a
patch-programmed decay, and any patch whose loudness contour lives in the expression domain (organ
swells, strings, anything with a slow attack) renders flat.

**Firmware-derived fix.** Decode the latch in `status_r`: `group == 0` → the active-voice bitmap
(current behaviour, keep it); `group == 1 && bank == 2` → return this voice's current envelope
level positioned so that `(v & 0x3FFF) >> 5` is the 0..255 level, i.e. `(level & 0x1FF) << 5`.
The HLE already needs that level for GAP 4; the two fixes are one fix.
*Overlap:* the VOICE-LIFECYCLE audit files the read path as its GAP 3. The **write** path and the
`LABEL_026EC3` accumulator are new here.
**Confidence: MEASURED** for the register traffic in both directions; **INFERRED** for the exact
readback packing.

### GAP 6 — `KEYBED_TIME[]` ignores the firmware's black-key trim
**What is wrong.** `kn5000.cpp:311` inverts §1.1's curve **for a white key only**. The firmware then
subtracts `TOUCH[mode].black` for the five black keys, so the same MIDI velocity arrives at the tone
generator **16 velocity units softer** on C#/D#/F#/G#/A# (mode 6; mean −13.7 over the whole table,
MEASURED).

**Audible consequence.** Playing a chromatic line or any chord with black keys from a MIDI
controller gives a lumpy dynamic: the black notes are consistently quieter — and on velocity-split
patches (24 of them per `notes/kn5000-variant-model.md`) they can select the wrong layer.

**Firmware-derived fix.** The trim exists to compensate the *mechanism*; the driver synthesises the
mechanism, so it must synthesise the compensation too. Two inverse tables —
`KEYBED_TIME_WHITE[]` and `KEYBED_TIME_BLACK[]`, both computed from the ROM curve at mode 6 — so a
given MIDI velocity produces that velocity regardless of key colour. Select on
`(midi_note % 12) ∈ {1,3,6,8,10}` at `kn5000.cpp:235`/`:443`.
**Confidence: MEASURED** (the trim is in the ROM and the delta is computed over all 127 velocities).

### GAP 7 — mid-note EG segment updates are misread as key releases
**What is wrong.** The release detector (cpp:252) fires on any `group 9 / bank 0` write more than
1 ms after the gate. `LABEL_02D436` (asm L29936) — which writes +0x900 — is used for **both** the
key-up burst **and** every envelope-segment reload (`LABEL_02CD71` → `LABEL_02CDDA` → `LABEL_02D436`,
asm L29218-29228), and `LABEL_02CD71` is called from the steppers *while the key is still down*
(asm L21503, L21613, L21723).

**Audible consequence.** A patch whose amplitude envelope actually advances a segment mid-note is
released by the HLE at that moment and dies shortly after its attack. Not observed in these captures
(the default `Piano` never advances a segment), so this is a **latent** systematic error.

**Firmware-derived fix.** Delete the heuristic. Once GAP 4 and GAP 5 are in, the amplitude is fully
determined by +0x800 and the voice ends at the firmware's own `0x7E00` (`LABEL_02B4A1`) — no
"when did the key go up" guess is needed at all.
*Overlap:* the VOICE-LIFECYCLE audit's GAP 5 proposes a deterministic +0x840→+0x940 adjacency
signature instead; that is a better heuristic, but the amplitude dimension's position is that no
heuristic is required.
**Confidence: MEASURED** (the shared code path); **INFERRED** that real patches hit it.

### GAP 8 — the PC-keyboard velocity is fixed, and `process_key_off` re-arms the fade
Two small ones, filed for completeness:
* `kn5000.cpp:287` `KEYBED_VELOCITY = 100` → time byte 42 → firmware velocity **100** at mode 6
  (MEASURED, matches the capture's `+0x800 = 0xE5`). Correct by construction, but it means the PC
  keyboard is touch-insensitive; that is inherent to a digital keyboard and only worth a comment.
* `process_key_off` (cpp:1370-1382) is called twice per note — once by the group-9 heuristic and
  again by the firmware's `0x7E00` 83 ms later — and unconditionally re-arms
  `release_counter = 2400`, restarting a full-amplitude 50 ms fade. Masked today only because the
  level has already collapsed (GAP 4). (Same as VOICE-LIFECYCLE GAP 1.)
* `sustain_vol` (`kn5000_tonegen.h:104`) is dead: declared, reset, never used. Remove it or restore
  its purpose.
**Confidence: MEASURED** (code reading + capture timing).

### GAP 9 — TOUCH SENSITIVITY: the sub-CPU half works, the panel half is UNVERIFIED
**What is right.** MEASURED: writing `*(0x4A48) = m` and pressing the same key moves `+0x800`
exactly as the ROM tables predict — 217 / 219 / 222 / 225 / 229 / 233 / 244 for modes 0/1/3/5/6/7/9.
Mode 0 really is "touch off": the ROM curve collapses to the single velocity 80 for every time byte,
which is precisely Felipe's report that touch=0 removes the effect. So the curve, the mode variable
and the level chain are all correct and complete.

**What is not verified.** MEASURED across a full boot to the PMEM play screen, `*(0x4A48)` takes
exactly two values: `0` at reset and `6` at t = 5.768 s, from `ToneGen_Init` (asm L51416). The main
CPU **never** sends command 0xA0-0xBF `{0x01,n}` during boot, so a stored user setting is not
restored at power-on, and whether the `OVERALL TOUCH SENSITIVITY` page sends it at all was not
exercised in this pass.

**Test that would settle it** (cheap, ~1 run): put a debugger write-watch on sub-CPU `0x4A48`, drive
the panel to the OVERALL TOUCH SENSITIVITY page, change the value, and see whether the watch fires.
If it does not, trace the main-CPU page handler near the UI record at ROM 0xED441C.
**Confidence: MEASURED** for the sub-CPU side and for the boot behaviour; the panel path is
explicitly **UNVERIFIED** — stated rather than assumed.

---

## 4. Audited and found CORRECT (explicitly)

1. **The `regs[20]` polarity fix of 7072b09 is RIGHT.** Higher = louder. Three independent
   confirmations from this dimension: (a) `LABEL_026769` builds the byte from a log table whose
   input is an attenuation-like 0..100 parameter and whose `min()` cap reads as a maximum-loudness
   limiter (§1.3); (b) MEASURED, the key-up recomputation *lowers* it 229 → 139; (c) MEASURED, it
   rises monotonically with velocity across the whole touch sweep. Do not revert this.
2. **Not multiplying `regs[2]` (+0x080) into the gain is RIGHT.** The firmware folds level *and*
   velocity into +0x800 itself (§1.3); +0x800 and +0x840 carry the *same* value (§1.4), so any
   second multiplication would double-count. The old code's 1.81× compression was exactly that bug.
2b. *(caveat, out of this dimension's scope)* the two partials of one key press differ in +0x080
   (`0x8E52` vs `0x8E64`) while sharing +0x800 — so +0x080 does carry *something* per-voice. It is
   simply not the velocity-scaled level.
3. **The exponential form `gain = 2^((level − REF)/K)` is RIGHT.** The value is a log-domain level
   straight out of a log table; a linear inversion (the pre-31fc389 code) was the wrong domain.
   Only the two constants are in question (GAPs 2, 3).
4. **`KEYBED_TIME[]` is a correct inverse of the ROM curve for white keys at mode 6.** Verified by
   recomputing the firmware curve from the ROM bytes and round-tripping all 127 velocities:
   **97 exact, 29 off by 1, 1 off by 2** (velocity 1, which the table cannot reach: the curve's floor
   at mode 6 is 2). Calibrating the inverse at the *power-on default* mode is also the right choice —
   the touch setting is then free to widen or narrow the response, which is what the control is for.
5. **The key-bed wire format is right.** note-on `= (time<<8) | (raw|0x80)`, note-off `= 0xFF00|raw`,
   `raw = MIDI − 36` — matches `ToneGen_Read_Voice_Data` (asm L51500-51530) exactly, including the
   guard that a note-on with time byte `0xFF` would be discarded (`KEYBED_TIME` maxes at 221, so it
   never happens).
6. **`env_level` initialisation to 0xFF at key-on** (cpp:1343) is harmless and correct as a default.
7. **The three-value discrimination in `data_w`** (`0x7E00` idle / `0x81xx` gate / `bit15` other) is
   correct and cannot be confused by `LABEL_02552A`'s routing bits: those only touch bits 9-12, so a
   command word can become `0x9Exx` or `0xF2xx` but never `0x81xx`. Checked exhaustively against the
   four base masks.
8. **`data_r()` (0x100002) is dead but harmless** — the firmware's only readback is at 0x100000
   (`DAC_Write_Sample`, asm L11479-11483). Worth a comment saying so; no behaviour change.

---

## 5. Live captures (reproduction)

Binary `/home/fsanches/compartilhado/kn7000-emulator/kn7000` (mtime 2026-07-26 00:05, i.e. commit
`e8f2be9` *before* the concurrent working-tree patch). All runs timeout-wrapped, `-window
-nomaximize`, isolated nvram copy; `kn7000-emulator/nvram` never touched.

Scripts and outputs in
`/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-b4f1-4ba1-adc0-85474706b167/scratchpad/`:

| script | output | what it shows |
|---|---|---|
| `ampcap.lua` | `cap_m6.stream` (68 writes), `cap_m6.log` | one held C4: the complete register lifecycle of §1.6, plus the read-latch histogram `g00.b0 ×138`, `g01.b2 ×34` |
| `ampcap.lua` + `-wavwrite` | `note.wav` | the release cliff of GAP 4 (RMS 3247 → 3.9) |
| `ampsweep.lua` | `sweep.stream`, `sweep.log` | `*(0x4A48)` swept 0,1,3,5,6,7,9 with one fixed key press ⇒ the velocity→level table of GAP 2 |
| `kn5demo.lua` (`BTN="START/STOP"`) | `rhy.stream` (988 writes), `rhy.wav` | 38 rhythm voices, all commanded `0xF000`; rendered peak RMS 8.9 (GAP 1) |

Lua note: `install_write_tap` / `install_read_tap` handles **must** be stored in a global
(`_G._wtap = …`). A chunk-local is collected as soon as the autoboot script returns and the tap
silently disappears — the first run of this audit recorded 0 events for exactly that reason.

Table extraction (stdlib only), address → file offset `− 0xEF00`:
```
T1    = rom[0x1053E : 0x1063E]      TOUCH = rom[0x10520 : 0x1053E]
T2    = rom[0x1063E : 0x1073E]      LOG   = rom[0x029FE : 0x02AFE]
K0    = u16le(rom, 0x10518) = 77    K1    = u16le(rom, 0x1051A) = 128
CAP   = rom[0x02BDF : 0x02CDF]
```

---

## 6. PREDICT-THEN-CHECK log (misses reported)

**HIT** — predicted `+0x800` would track velocity monotonically upward if the polarity fix was
right. MEASURED 217 → 244 over the touch sweep, monotone, 7/7.

**HIT** — predicted the key-up value would be bit-exact `(IZ<<8)|0x80` from `LABEL_026769`.
MEASURED `0x8B80` on +0x800 and `0x8B00` on +0x840. Exact.

**HIT** — predicted from `LABEL_02219F` that the firmware polls `+0x180` per voice. MEASURED 18-34
reads at latch `g01.b2` per note.

**HIT** — reconstructed the velocity model `level ≈ LOG[att] + (depth·(vel−pivot))>>5` from the
pre-fix capture (`231 @ vel 102`, `204 @ vel 41`) and solved `depth ≈ 15, pivot ≈ 64, LOG ≈ 214`;
it reproduced both points to ±1 before any new capture was taken.

**MISS 1** — I predicted (following the existing HLE and `kn5000-tonegen-register-semantics.md`)
that the group-0/bank-0 low byte was the per-tick amplitude magnitude. The rhythm capture falsified
it: 38 voices that must sound are all commanded with magnitude `0x00`. The field is a command
parameter of undecoded meaning (GAP 1).

**MISS 2** — I predicted, following `kn5000-envelope-engine.md` §2, that the software EG rewrites
the level register *every audio tick*. MEASURED: the write is gated on a coarse counter reaching a
segment boundary and fired **once** per note; `+0x800` moved 2-3 times per note and never ramped.
That note's §2 rate claim should be corrected.

**MISS 3** — I first read the constant pair `+0x840 = 0xFF00 / +0x800 = 0xFF80` in `LABEL_026FDD`
as an envelope *attack peak*, which would have made "255 = loudest" a decoded fact. Reading
`Voice_NoteOff` (asm L28660-28680) showed the identical pair is also written when a channel is
being torn down, so it is not a peak marker. `REF = 255` therefore rests on the firmware's clamp
(`LABEL_023328`) and on the log table's maximum — the register's arithmetic ceiling — not on a
proven 0 dBFS point. GAP 2 is worded accordingly.

---

## 7. Suggested order of work

1. **GAP 1** — unmute the accompaniment (one line; the working-tree stop-gap already does it, but
   the *principled* change is to stop using the field as a VCA and say what it is).
2. **GAP 2** — `REF = 255` + explicit make-up gain; recovers the top 20 % of the velocity range.
3. **GAP 5 + GAP 4 together** — model the +0x180 level readback and make +0x800 a ramp target.
   These are one change and they give real release tails, patch-dependent decay, and let
   **GAP 7** be deleted rather than patched.
4. **GAP 6** — the black-key inverse table (self-contained, ~20 lines in `kn5000.cpp`).
5. **GAP 3** — capture the service check modes 1 and 6 to pin `K` from Technics' own "16 dB DOWN".
6. **GAP 9** — one debugger run to confirm the panel → `0x4A48` path.
