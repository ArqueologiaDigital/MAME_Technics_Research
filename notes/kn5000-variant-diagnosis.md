# KN5000 tone-gen — why the *variants* of a sound do not differentiate (DIAGNOSIS)

Author: autonomous DIAGNOSE pass, 2026-07-25. Requested by Felipe Sanches after listening to
the build at `e2f8b60` ("the piano now sounds like a piano", but *"Piano / Bright Piano /
Piano 1 Octave are very similar — I cannot tell them apart. Rock Piano is clearly wrong. The
same applies to many other sounds, e.g. E.Piano 1."*).

**Diagnosis only — no `src/` edits, no rebuild.** The only tracked change is this note.
Everything below is either read out of the firmware's own data structures, or read off the
live register stream of the running machine. **No heuristics, no clustering, no ear-cataloguing,
no invented mappings.** Where something is not derivable it is said so (§8).

Evidence labels: **MEASURED** (ROM bytes, disasm line, or a value read off a live run) /
**INFERRED** / **SPECULATIVE**. Every miss of a prediction is reported (§6).

Builds on and corrects: `kn5000-firmware-sample-tables.md` (`cb6b362`),
`kn5000-structural-validation.md` (`1e1e03e`), `kn5000-datamap-applied.md` (`e2f8b60`),
`kn5000-live-captures.md`, `kn5000-tonegen-register-semantics.md`.

---

## 0. TL;DR — the verdict table

Verdict codes, as posed by the task:
**(a)** the variant difference never reaches the chip;
**(b)** it reaches the chip in `+0x040` but the HLE renders both the same;
**(c)** it reaches the chip in OTHER registers the HLE ignores;
**(D)** the selection is *correct and complete*, but it names PCM on a chip that has never
been dumped (IC304/305/306) — a **missing dump**, not a decode or render defect.

| sound | patch | what the DATA says should differ | what actually reaches IC303 | **VERDICT** |
|---|---|---|---|---|
| **Piano** | #0 | — (reference) | `+040` = `7007`+`7017` @C4 | reference |
| **Bright Piano** | #1 | **nothing in the sample path.** Same `(fine,set)`, same VSEL #3/#4, same SET #1/#2 as Piano. Only 9 bytes of the 0x51 partial block + 2 header bytes differ | `+040` and `+400` **byte-identical to Piano at 3 keys × 6 velocities**; differs only in `+080 +0C0 +100 +140 +800 +8C0 +A00 +A40` | **(c)** |
| **Mellow Piano** | #2 | same as Bright Piano — identical sample path to Piano | ditto; **and identical to Bright Piano in every register the HLE reads** | **(c)** — rendered audio is **100.00 % bit-identical to Bright Piano** |
| **Piano 1 Octave** | #3 | SET **#0** (not #1/#2) *and* partial 0 carries coarse transpose **+12 semitones**, fine **+4** | `+040` = `7019`+`7007` @C4 (**differs** from Piano) and `+400` = `392C` vs `34C1` (**differs**) | **(c)** — both differences reach the chip; the HLE takes pitch from the played MIDI note and never reads `+0x400`, so the octave is dropped. MEASURED: rendered C5/C4 partial ratio **0.146**, *lower* than plain Piano's 0.343 — the opposite of an added octave |
| **Rock Piano** | #5 | single partial → SET **#6**, **class 2**, entries `0x001..0x00B` | `+040` = `2003`/`2005`/`2007` @C3/C4/C5 — **exactly what the data says** | **(D)** — class 2 ⇒ **bank 0 = IC304/305/306, UNDUMPED**. `kn5000.cpp:1161-1163` loads a `BAD_DUMP` copy of IC307 into those sockets, so the machine plays **IC307 page-2 chunks 3/5/7 — class-6 drawbar/footage recordings.** Nothing about the selection is wrong |
| **E.Piano 1** | #9 | single partial, **real 4-way velocity split** (VSEL #11, splits `3C/50/64`) over SET **13/15/11/16**, all **class 2** | `+040` = `202F→2027→201F→2017` as velocity rises (4 distinct zones MEASURED), all class 2 | **(D)** + **(c)** — the velocity split *works and reaches the chip*; the samples are on the undumped bank. A second, detuned voice (`+400` Δ=20) is also emitted and its detune is ignored |
| *Electric Grand* #7 | | SET #8 (class 2); partial 1 fine detune **+1** | `+040` = `200D/200F/2011`; `+400` = `3BC6` vs `3BC8` (Δ=2) | **(D)** + **(c)** |
| *Suitcase E.P.* #11 | | VSEL #10 splits `59/6D/7F` → SET 9/10/12/9, class 2 | `+040` = `2049 / 2064 / 2057` across velocity | **(D)** — split works |
| *Modern E.P.1* #14 | | VSEL #16 splits `3B/4F/63` → SET 22/23/19/24, class 2 | `+040` = `207E→2078→2074→206D`, **all four zones observed** | **(D)** — split works |
| *Honky-Tonk Piano* #6 | | SET #0 both partials, fine transpose **−6 / +6** (a detuned string pair) | `+040` identical for both partials (`7007`); `+400` = `34B5` vs `34D9` | **(c)** — the detune reaches `+0x400` only, which the HLE never reads ⇒ two *identical* voices, no beating |
| *Harpsichord* #16 | | 3 partials: class 1 ×2 + class 4 ×1, third partial coarse **−12** and fold-collapsed | `+040` = `1065` + `1076` + `40A3` @C4 — **exactly** predicted | **(D)** for 2/3 partials (class 1 = bank 0), the third is real IC307 |

**The three things that are actually wrong, ranked by how many sounds they break:**

1. **The undumped bank.** MEASURED over all 629 patches: **312 are entirely on bank 0
   (undumped), 118 are mixed, only 155 are entirely on IC307.** Inside the PIANO sound group
   itself, **14 of 20 variants** touch bank 0. Rock Piano and every E.Piano are in that 14.
   This is not fixable in software.
2. **The HLE reads 3 of the 32 per-voice registers.** `regs[1]` = `+0x040` (wave),
   `regs[20]` = `+0x800` high byte (level), `regs[8]` = `+0x400` (**only** in the fallback
   path for voices with no keybed correlation, `kn5000_tonegen.cpp:571`), plus the gate /
   envelope magnitude in `regs[0]`. **28 of 32 are stored and never read** — including every
   register that carries the Bright/Mellow/Piano difference.
3. **Transpose is dropped.** MEASURED: **273 of 629 patches** carry a non-zero coarse or fine
   transpose in a partial block. It reaches the chip in `+0x400`; the HLE derives pitch from
   `v.true_note`, the played MIDI note (`kn5000_tonegen.cpp:558-561`), so all of it is lost.

Secondary but real: **334 of 629 patches share a byte-identical `+0x040` signature (whole
keyboard × all 4 velocity zones) with at least one other patch** — the largest groups being
44 drum kits and **25 patches that include Piano, Bright Piano and Mellow Piano**. For those,
`+0x040` *cannot* differentiate; only the ignored registers can.

---

## 1. Method

**Static side.** The Table-Data ROM (`kn5000_table_data_rom_even.ic3` + `..._odd.ic1`,
interleaved exactly as `kn5000.cpp:1131-1133` loads them) walked with the chain proven in
`kn5000-firmware-sample-tables.md §5`: patch record → `(fine,set)` → stage A1 → VSEL →
velocity zone → stage A2 → SET descriptor → `ptrC[key]` → `ptrA[4+slot]` → partial record →
`+0x040`.

**Live side.** MAME, published binary, `-window -nomaximize`, isolated **copy** of the
pre-init nvram (`kn7000-emulator/nvram` never touched), boots to the PMEM play screen at
**t ≈ 20 s** on this host. Two write taps on the sub-CPU bus reconstruct the exact ordered
stream to IC303 (`0x100000` = address latch, `0x100002` = data). Note-on bursts are located by
the **gate write itself** (`group0/bank0 = 0x8100`), not by a frame-granular window — an
earlier attempt used a frame window and silently missed most bursts, because the frame
notifier fires only every ~19 ms while the burst lands 1-3 ms after the note.

**Selecting the variants** is done exactly as a player would: press the **PIANO** SOUND-GROUP
button (`CPR_SEG2` 0x01) to open the SOUND screen, optionally **PAGE** (`CPL_SEG2` 0x80), then
the LCD soft key. The screen (screenshotted, `snapA/…/0000.png`) is:

```
 SOUND   RIGHT1/PIANO                         PAGE 1/2 | PAGE 2/2
 L1 Piano            R1 E.Piano 1             | L1 Mellow Piano      R1 Tremolo E.Piano
 L2 Bright Piano     R2 Suitcase E.P.         | L2 Piano 2 Octave    R2 Wurly E.Piano
 L3 Piano 1 Octave   R3 Modern E.P.1          | L3 Honky-Tonk Piano  R3 Modern E.P.2
 L4 Rock Piano       R4 Harpsichord           | L4 Midi Grand        R4 Cembalo
 L5 Electric Grand   R5 Clavi                 | L5 E.Piano 2         R5 Synth Clavi
```

Every selection is **verified**, not assumed: the capture dumps part-0's tonerec and reads the
16-byte ASCII name of the patch record it points at (`ptr0 − 0x66`). All eleven selections
below report their own correct name.

**Velocity** cannot come from the key-bed ports (`keybed_scan()` uses a fixed
`KEYBED_VELOCITY`). It is delivered through the machine's real velocity path: a **format-0 MIDI
file on the `kbdmidi` port** (`-midiin2 <file.mid>`), which `kbd_midi_rx()` turns into
`push_keybed_event((vel<<8)|(raw|0x80))` — the same wire format the key bed uses.
`midiin_device::call_load()` sets `m_sequence_start = max(now, 10 s)`, so file time *T* plays
at emulated time *T*+10 s; the MIDI file is generated from the same schedule table the Lua
script uses.

---

## 2. What the FIRMWARE DATA says each sound should be (100 % static, MEASURED)

Addresses are sub-CPU (`region offset = S − 0x20000`, `main = S + 0x7E0000`).

| patch | name | rec addr | mask | p | FINE(+02) | SET(+03) | coarse(+04) | fine(+05) | VSEL# @addr | splits | 4 × (fine,set) | SET# per vel zone |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Piano | 0524D4 | 05 | 0 | 00 | 01 | +0 | +0 | #3 @076ABA | 7F/7F/7F | (00,01)×4 | 1/1/1/1 |
| 0 | Piano | 0524D4 | 05 | 1 | 00 | 05 | +0 | +0 | #4 @076AC5 | 7F/7F/7F | (00,05)×4 | 2/2/2/2 |
| 1 | Bright Piano | 0525DC | 05 | 0 | 00 | 01 | +0 | +0 | #3 @076ABA | 7F/7F/7F | (00,01)×4 | 1/1/1/1 |
| 1 | Bright Piano | 0525DC | 05 | 1 | 00 | 05 | +0 | +0 | #4 @076AC5 | 7F/7F/7F | (00,05)×4 | 2/2/2/2 |
| 2 | Mellow Piano | 0526E4 | 05 | 0 | 00 | 01 | +0 | +0 | #3 @076ABA | 7F/7F/7F | (00,01)×4 | 1/1/1/1 |
| 2 | Mellow Piano | 0526E4 | 05 | 1 | 00 | 05 | +0 | +0 | #4 @076AC5 | 7F/7F/7F | (00,05)×4 | 2/2/2/2 |
| 3 | Piano 1 Octave | 0527EC | 05 | 0 | 00 | 00 | **+12** | **+4** | #1 @076AA4 | 7F/7F/7F | (00,00)×4 | 0/0/0/0 |
| 3 | Piano 1 Octave | 0527EC | 05 | 1 | 00 | 00 | +0 | +0 | #1 @076AA4 | 7F/7F/7F | (00,00)×4 | 0/0/0/0 |
| 5 | **Rock Piano** | 0529FC | 01 | 0 | 01 | 04 | +0 | +0 | #7 @076AE6 | 7F/7F/7F | (01,04)×4 | **6/6/6/6** |
| 6 | Honky-Tonk Piano | 052AB3 | 05 | 0 | 00 | 00 | +0 | **−6** | #1 @076AA4 | 7F/7F/7F | (00,00)×4 | 0/0/0/0 |
| 6 | Honky-Tonk Piano | 052AB3 | 05 | 1 | 00 | 00 | +0 | **+6** | #1 @076AA4 | 7F/7F/7F | (00,00)×4 | 0/0/0/0 |
| 7 | Electric Grand | 052BBB | 05 | 0 | 03 | 00 | +0 | +0 | #9 @076AFC | 7F/7F/7F | (03,00)×4 | 8/8/8/8 |
| 7 | Electric Grand | 052BBB | 05 | 1 | 03 | 00 | +0 | **+1** | #9 @076AFC | 7F/7F/7F | (03,00)×4 | 8/8/8/8 |
| 9 | **E.Piano 1** | 052E1C | 01 | 0 | 05 | 00 | +0 | +0 | #11 @076B12 | **3C/50/64** | (05,02)(05,04)(05,00)(05,06) | **13/15/11/16** |
| 11 | Suitcase E.P. | 052F8A | 01 | 0 | 04 | 00 | +0 | +0 | #10 @076B07 | **59/6D/7F** | (04,00)(04,04)(05,01)(04,00) | **9/10/12/9** |
| 14 | Modern E.P.1 | 053251 | 01 | 0 | 06 | 00 | +0 | +0 | #16 @076B49 | **3B/4F/63** | (06,04)(06,05)(06,00)(06,06) | **22/23/19/24** |
| 16 | Harpsichord | 053410 | 45 | 0 | 10 | 02 | +0 | +0 | #37 @076C30 | 7F/7F/7F | (10,02)×4 | 42/42/42/42 |
| 16 | Harpsichord | 053410 | 45 | 1 | 10 | 00 | +0 | +0 | #35 @076C1A | 7F/7F/7F | (10,00)×4 | 41/41/41/41 |
| 16 | Harpsichord | 053410 | 45 | 2 | 1F | 80 | **−12** | +4 | #71 @076DA6 | 7F/7F/7F | (1F,80)×4 | 81/81/81/81 |

### 2.1 The SET descriptors these resolve to, and their `+0x040` zone maps (MEASURED)

```
SET #1  @077923  flags 80 stride 6  kmin 0C kmax 78 root 42 pitch 4280   (Piano, osc 1)
   0-35:7:000 36-39:7:001 40-43:7:002 44-47:7:003 48-51:7:004 52-55:7:005 56-59:7:006
   60-63:7:007 64-67:7:008 68-71:7:009 72-75:7:00A 76-79:7:00B 80-83:7:00C 84-87:7:00D
   88-91:7:00E 92-127:7:00F
SET #2  @077932  (Piano, osc 2) — identical zone bounds, entries 0x010..0x01F
SET #0  @077914  (Piano 1 Octave / Honky-Tonk / Piano 2 Octave) — 17 zones; identical to
   SET #1 up to key 63, then jumps to the 0x01x group: 64-67:7:017 68-71:7:018 72-75:7:019
   76-79:7:01A 80-83:7:01B 84-87:7:01C 88-91:7:01D 92-95:7:01E 96-127:7:01F
SET #6  @07796E  (ROCK PIANO)   11 zones, ALL class 2:
   0-39:2:001 40-44:2:002 45-51:2:003 52-57:2:004 58-63:2:005 64-69:2:006 70-74:2:007
   75-79:2:008 80-86:2:009 87-92:2:00A 93-127:2:00B
SET #13/#15/#11/#16 (E.PIANO 1, one per velocity zone) — all class 2, C4 word
   2017 / 201F / 2027 / 202F respectively
SET #8  (Electric Grand) class 2, C4 = 200F
SET #9/#10/#12   (Suitcase E.P.)  class 2, C4 = 2057 / 2064 / 2049
SET #22/#23/#19/#24 (Modern E.P.1) class 2, C4 = 206D / 2074 / 2078 / 207E
SET #42/#41/#81  (Harpsichord) class 1 / class 1 / class 4, C4 = 1065 / 1076 / 40A3
```

### 2.2 The bytes that DO differ between Piano and Bright Piano (MEASURED)

Both patch records are 0x10 name + 0x56 header + 2 × 0x51 partial blocks. Byte-for-byte, the
only differences are:

```
patch header (+0x12..+0x65):  2 bytes    Piano  … 00 5a 43 0a 14 …
                                          Bright … 40 40 43 0a 14 …
partial block 0 (0x51 bytes): 9 bytes    off  +17  +1D  +2E  +36  +37  +3E  +45  +4D  +50
                                Piano      54   fb   0f   41   20   00   46   64   89
                                Bright     56   00   0c   61   17   28   64   67   8b
```

*None of them is in the sample-selection path* (`+0x02` FINE and `+0x03` SET are equal). They
are envelope / level / filter / key-scale fields — §4 shows what they turn into on the bus.

---

## 3. What the machine ACTUALLY sends the chip (LIVE, MEASURED)

Eleven sounds selected from the panel, three keys (C3/C4/C5 at vel 100) and six velocities at
C4. `WAVE` = `+0x040`, `PITCH` = `+0x400`, `tim` = `+0x0C0 / +0x140 / +0x500`.
Each row's selection was verified by reading the patch-record name live.

### 3.1 Piano / Bright Piano / Mellow Piano — the sample stream is IDENTICAL

```
Piano        (rec 0x0524D4)  C3 7004+7014 / C4 7007+7017 / C5 700A+701A   PITCH 28E8 / 34C1 / 41AD
Bright Piano (rec 0x0525DC)  C3 7004+7014 / C4 7007+7017 / C5 700A+701A   PITCH 28E8 / 34C1 / 41AD
Mellow Piano (rec 0x0526E4)  C3 7004+7014 / C4 7007+7017 / C5 700A+701A   PITCH 28E8 / 34C1 / 41AD
   … and identical at vel 20 / 45 / 70 / 90 / 110 / 127 as well.
```

Every register written in the C4 note-on burst, partial 0 (identical picture for partial 1):

```
 off    Piano   Bright  Mellow      HLE reads it?
 +000   8100    8100    8100        gate only
 +040   7007    7007    7007        YES  (wave)          <- SAME
 +080   0CC2    0CCE    0D2C        no                   <- DIFFERS
 +0C0   7400    5A00    5A00        no                   <- DIFFERS
 +100   244E    2461    2445        no                   <- DIFFERS
 +140   6FDA    5BDA    5BDA        no                   <- DIFFERS
 +180   0000    0000    0000        no
 +400   34C1    34C1    34C1        only in the fallback path  <- SAME
 +4C0   4400    4400    4400        no
 +500   2C68    2C68    2C68        no      (low byte = velocity level)
 +800   D17F    DA7F    DA7F        YES  (level)         <- DIFFERS (Piano only)
 +840   404C    404C    404C        no
 +880   3800    3800    3800        no
 +8C0   00B0    0000    0000        no                   <- DIFFERS
 +900/940/980/9C0  AE00 AE00 AE00 FF00  (all three equal)  no
 +A00   36E8    36E8    36F6        no                   <- DIFFERS
 +A40   26B0    26B0    36F6        no                   <- DIFFERS
```

**Bright Piano and Mellow Piano are byte-identical in every register the HLE reads.** The
rendered audio proves it — one C4 vel-100 note per sound, `-wavwrite`, onset-aligned:

```
  BrightPiano vs MellowPiano : corr = 1.000000  lag 0  gain 1.0000  residual 0.000000
                               100.00 % of samples BIT-IDENTICAL
  Piano       vs BrightPiano : corr = 0.998548  lag 0  gain 1.8574 (+5.38 dB)  residual 0.054
                                 0.08 % bit-identical  -> a pure LEVEL scale, nothing else
```

That is the whole of Felipe's "I cannot tell them apart", quantified: to today's HLE
**Bright Piano *is* Mellow Piano**, and Piano differs from both only by a gain.

### 3.2 Piano 1 Octave — the difference DOES reach the chip

```
             partial 0                    partial 1
 C3   WAVE 7007  PITCH 34C9        WAVE 7004  PITCH 28E8
 C4   WAVE 7019  PITCH 392C        WAVE 7007  PITCH 34C1
 C5   WAVE 701C  PITCH 46BB        WAVE 7019  PITCH 3924
```

Partial 1 is Piano's partial 0 verbatim; partial 0 is the same voice **transposed up 12
semitones** — a different key zone (`7019` vs `7007`) *and* a different pitch word
(`392C` vs `34C1`). Both are on the bus. The HLE ignores the pitch word for keyed voices and
resamples every chunk to the played note, so both partials come out at C4. Falsifiable check,
run: if the octave were rendered, the C5 (523 Hz) component would be *stronger* than plain
Piano's. MEASURED on the rendered note (0.05-1.30 s body, Goertzel):

```
  Piano         |C4 261.6| = 107.62   |C5 523.3| = 36.91   C5/C4 = 0.343
  Piano1Octave  |C4 261.6| =  41.96   |C5 523.3| =  6.14   C5/C4 = 0.146   <- LOWER, not higher
```

### 3.3 Rock Piano — the selection is right, the chip is missing

```
 C3 WAVE 2003   C4 WAVE 2005   C5 WAVE 2007   (constant across all six velocities)
```

Exactly the SET #6 zone map of §2.1. Decoded by `decode_wave_select()`:
`class = 2` → `page = class & 3 = 2`, `bank = (class >> 2) & 3 = **0**`, `chunk = entry`.
**Bank 0 is IC304/305/306 — never dumped.** `kn5000.cpp:1161-1163` loads a `BAD_DUMP` copy of
IC307 into all three sockets, so what actually plays is IC307's page 2:

```
 page 2 chunk 3  0x21B2E0..0x21FFB0   9832 samples   (class 6 = drawbar / footage)
 page 2 chunk 5  0x225F80..0x229E10   8008 samples   (class 6 = drawbar / footage)
 page 2 chunk 7  0x232E40..0x23F760  25744 samples   (class 6 = drawbar / footage)
```

Rock Piano is playing **organ drawbar footage recordings**. That is "clearly wrong", and it is
a missing dump — there is nothing to fix in the decode.

### 3.4 E.Piano 1 — the velocity split works, and lands on the same undumped bank

C4, one note per velocity, velocity swept 4…114 in steps of 5:

```
 vel   4..39   WAVE 202F   (SET #16)
 vel  44..69   WAVE 2027   (SET #11)
 vel  74..94   WAVE 201F   (SET #15)
 vel  99..114  WAVE 2017   (SET #13)
```

All four SETs of VSEL #11 appear, and the four SET addresses `0779D7 / 0779F5 / 0779B9 /
077A04` were read live out of the voice descriptor — **exactly** the four the static walk
predicts. Two independent confirmations with different split bytes:

```
 Suitcase E.P.  (splits 59/6D/7F)  vel 20 -> 2049 (SET12) | vel 45 -> 2064 (SET10) | vel >=70 -> 2057 (SET9)
 Modern E.P.1   (splits 3B/4F/63)  vel 20 -> 207E (SET24) | 45,70 -> 2078 (SET19)
                                   vel 90 -> 2074 (SET23) | 110,127 -> 206D (SET22)
```

All of these are class 2 = bank 0 = undumped, so what plays is again IC307 page 2.
E.Piano 1 additionally emits a **second voice with the same WAVE and `+0x400` 20 units higher**
even though its partial map is `0x01` (one partial) — see §6.3.

### 3.5 Honky-Tonk Piano, Electric Grand, Harpsichord (cross-checks)

```
 Honky-Tonk    C4  v0: WAVE 7007 PITCH 34B5   v1: WAVE 7007 PITCH 34D9     (Piano's C4 = 34C1)
 ElectricGrand C4  v0: WAVE 200F PITCH 3BC6   v1: WAVE 200F PITCH 3BC8
 Harpsichord   C4  v0: WAVE 1065 PITCH 3C80   v1: WAVE 1076 PITCH 3C80   v2: WAVE 40A3 PITCH 3508
```

Honky-Tonk's whole identity — two strings pulled apart — lives in `+0x400` alone
(`34B5` / `34D9`, i.e. ∓ around Piano's `34C1`); its `+0x040` is the *same word twice*. Today's
HLE plays two identical voices at the same pitch: no beating, so Honky-Tonk collapses onto
Piano-with-SET-#0. Electric Grand's `+1` fine detune shows up as exactly `+2` in `+0x400`.

---

## 4. What the HLE consumes, exactly

`kn5000_tonegen_device` stores all 32 per-voice registers (`data_w`, line 195) and reads:

| register | reg idx | where | used for |
|---|---|---|---|
| `+0x000` gate | 0 | L205-226 | key on (`0x8100`) / off (`0x7E00`) / per-tick envelope magnitude |
| `+0x040` | 1 | L1058 (`resolve_waveform`), L365 (`voice_pitch_index`) | **the waveform** |
| `+0x400` | 8 | L365, and L571 **only** when `true_note < 0` | voice ordering; pitch only for non-keyed voices |
| `+0x800` | 20 | L474-489 | log-domain level → gain |

Pitch for a keyed voice is `440·2^((true_note−69)/12)` (L558-561), where `true_note` is the
MIDI/key-bed note that caused the voice. **The other 28 registers — including
`+0x080 +0x0C0 +0x100 +0x140 +0x180 +0x8C0 +0xA00 +0xA40`, which is the entire set that
distinguishes Piano from Bright Piano from Mellow Piano — are written by the firmware, latched
by the device, and never read.**

---

## 5. How widespread this is (MEASURED over all 629 patches)

```
 wave-ROM bank each patch's PCM lives on
   entirely bank 1 (IC307, the one real dump)   155
   entirely bank 0 (IC304/305/306, UNDUMPED)    312
   mixed                                        118
   no partials                                   44
                                                ----
                                                629

 patches carrying a non-zero coarse/fine transpose in a partial block   273 / 629
 patches carrying a REAL velocity split (splits != 7F/7F/7F)             24 / 629
 patches whose whole-keyboard x 4-velocity-zone +0x040 signature is
   byte-identical to at least one OTHER patch                           334 / 629
       largest groups: 44 x drum kits;  25 x {Piano, Bright Piano, Mellow Piano, ...}
```

And the PIANO sound group specifically:

```
  #0  Piano            class 7        bank0   0.0 %      #9  E.Piano 1        class 2   100.0 %
  #1  Bright Piano     class 7        bank0   0.0 %      #11 Suitcase E.P.    class 2   100.0 %
  #2  Mellow Piano     class 7        bank0   0.0 %      #14 Modern E.P.1     class 2   100.0 %
  #3  Piano 1 Octave   class 7        bank0   0.0 %      #10 E.Piano 2        class 2   100.0 %
  #4  Piano 2 Octave   class 7        bank0   0.0 %      #12 Tremolo E.Piano  class 2   100.0 %
  #6  Honky-Tonk       class 7        bank0   0.0 %      #13 Wurly E.Piano    class 0,2 100.0 %
  #5  Rock Piano       class 2        bank0 100.0 %      #15 Modern E.P.2     class 2   100.0 %
  #7  Electric Grand   class 2        bank0 100.0 %      #16 Harpsichord      class 1,4  66.7 %
  #8  Midi Grand       class 2,7      bank0  88.9 %      #17 Cembalo          class 1,4  75.0 %
  #18 Clavi            class 1,2,4    bank0  50.0 %      #19 Synth Clavi      class 1   100.0 %
```

**The six variants that are entirely on the real dump are exactly the six that share SETs
#0/#1/#2** — one acoustic-piano multisample. That is why they sound alike *and* why they are
the only six that sound like a piano at all.

---

## 6. PREDICT-THEN-CHECK, including the misses

Everything below was computed from ROM bytes **before** the machine was run.

**HIT — voice-descriptor pointers, 11/11 sounds.** The static walk predicts the VSEL address
and the four SET addresses the firmware will deposit at `tonerec+0x04 … +0x14`. Read live out
of sub-CPU RAM at selection time: all 11 VSEL addresses and all 44 SET addresses exact
(e.g. E.Piano 1 → `076B12` + `0779D7 / 0779F5 / 0779B9 / 077A04`).

**HIT — `+0x040`, 11 sounds × 3 keys × 1-3 partials = 63 words, all exact** (at velocity 100,
and at all six velocities for the sounds without a split). Including Harpsichord's three
partials `1065 / 1076 / 40A3` and its fold-collapsed third partial that stays constant across
the keyboard.

**HIT — the coarse-transpose field is semitones.** Predicted from the *names* before reading
the register: `Piano 1 Octave` partial 0 `+0x04 = 0x0C = +12`; `Piano 2 Octave` `= 0x18 = +24`;
`Honky-Tonk` = a detuned pair `−6 / +6`; `Electric Grand` = a slight detune `+1`. **4/4.**

**HIT — the fine-transpose field lands in `+0x400` at 2 units per count.** Electric Grand
`+1 → +2` (`3BC6`→`3BC8`); Piano 1 Octave `+4 → +8` (`34C1`→`34C9` at C3); Honky-Tonk partial 0
`−6 → −12` (`34C1`→`34B5`). **3/3.**

**MISS #1 — the velocity-zone ORDER is inverted.** `kn5000-firmware-sample-tables.md §5` states
`q = 0 if vel ≤ VSEL[0]; 1 if ≤ VSEL[1]; 2 if ≤ VSEL[2]; else 3`. MEASURED on three independent
instruments, the **softest** note takes `q = 3` and the **loudest** takes `q = 0`. The
comparison is against a value that *falls* with velocity — i.e. a level / attenuation, not the
raw velocity. The traced comparison structure (`LABEL_022844`) is unchanged; only the quantity
being compared is. Crossings, MEASURED (E.Piano 1, splits 60/80/100):

```
   q3 -> q2 between vel 39 and 44      (split byte 0x64 = 100)
   q2 -> q1 between vel 69 and 74      (split byte 0x50 =  80)
   q1 -> q0 between vel 94 and 99      (split byte 0x3C =  60)
```

A crude linear fit `x ≈ 127 − 0.65·vel` reproduces all three, and independently predicts
Suitcase E.P.'s (splits 89/109/127) crossings at lower velocities — which is what its capture
shows (q2 at vel 20, q1 at vel 45, q0 from vel 70). The exact curve is a table and was **not**
identified here (§8.2). **Consequence for this diagnosis: none** — the *set* of four SETs, and
which `+0x040` word each produces, are unaffected; only which one a given velocity picks.

**MISS #2 — Honky-Tonk partial 1.** Predicted `+0x400 = 34C1 + 2·(+6) = 34CD`; MEASURED
`34D9` (`+24`, not `+12`). The three hits above are all on patches whose
`part_base[+0x0a] = 0x0004`; Honky-Tonk's is `0xC004`. See §6.3.

**MISS #3 (attempted measurement that does not discriminate — reported, not used).** A
detuned string pair must amplitude-modulate at the beat frequency, so the rendered Honky-Tonk
envelope was searched for 0.5-8 Hz modulation. It found ~0.15 at ~0.9 Hz — **and so did plain
Piano, which has zero detune.** The control scores the same as the test, so the measurement
cannot fail and earns nothing; it is discarded. The claim "the detune is not rendered" rests
instead on the code (pitch comes from `true_note`, L558-561) plus the fact that both partials
carry the *same* `+0x040` and the HLE resamples by measured period alone.

### 6.3 An unexplained doubling, flagged (SPECULATIVE)

`E.Piano 1` and `Modern E.P.1` both have partial map `0x01` — **one** partial — yet each emits
**two** voices per note, same `+0x040`, `+0x400` differing by 20 and 24 units respectively.
Both have `part_base[+0x0a] = 0xC004`; so does Honky-Tonk (whose partial-1 pitch is the one
that missed). The three patches with `pb0a = 0x0004` in this set (Piano, Piano 1 Octave,
Electric Grand) emit exactly as many voices as their partial map declares and hit the ×2 rule.
`kn5000-live-captures.md §2` already flags `pb0a` bit 15 as marking the "extended /
wave-fallback path". A per-part unison/detune layer controlled by that bit would explain both
observations, but it is **not traced** and is recorded here only as the next thing to look at.

---

## 7. Answering the task's three questions directly

**(1) What SHOULD differ between the variants, per the data** — §2. For
Piano / Bright Piano / Mellow Piano: *nothing in the sample path*. Their entire difference is
9 bytes of the partial block and 2 of the header. For Piano 1 Octave: a different SET (#0) and
a +12-semitone coarse transpose. For Rock Piano: a completely different SET (#6, class 2). For
E.Piano 1: four SETs selected by velocity (#13/#15/#11/#16, class 2).

**(2) Do the variants send DIFFERENT `+0x040`?** — §3.
Piano / Bright / Mellow: **no**, byte-identical at 3 keys × 6 velocities.
Piano 1 Octave: **yes** (`7019` vs `7007` on partial 0).
Rock Piano and every E.Piano: **yes**, and correctly.
Velocity-split sounds: **yes, `+0x040` changes with velocity**, all four zones observed.

**(3) Verdict** — the table in §0. In one line: **the sample-bank level is right *and so is the
patch level as far as the bus is concerned* — the firmware is emitting the variant differences
faithfully. They are lost in two places: on the way out of the chip model (28 of 32 registers
are never read, and pitch is taken from the played note rather than `+0x400`), and in the wave
ROM itself (61 % of the firmware's zone words name a chip that has never been dumped).**

For Rock Piano specifically: **page 2, bank 0, chunks 1-11** (`+0x040 = 0x2001..0x200B`);
bank 0 = IC304/305/306 = **undumped**, therefore expected-wrong, and no software change can
make it right.

---

## 8. Honest gaps

1. **The byte → register transform is not traced.** `+0x080 +0x0C0 +0x100 +0x140 +0x800
   +0x8C0 +0xA00 +0xA40` are measurably per-variant, but none of their bytes is a straight copy
   of any patch-record byte (checked exhaustively: for each register half, no offset in the
   0x51 block or the 0x54 header matches across all captured patches). They are computed —
   through the log/EG tables — by the note-on builder. Identifying which patch field feeds
   which register requires tracing `LABEL_027F96` / `LABEL_027FD6` / `LABEL_02CD71` and the
   tables they index. **This is the single blocking unknown for making the variants differ.**
2. **What each of those registers means to the chip.** `kn5000-tonegen-register-semantics.md`
   labels `+0x0C0` "waveform control" and `+0x040` "pitch"; the later structural work proved
   `+0x040` is the wave selector, so that note's assignment for `+0x0C0` is now unsupported.
   The measured value set across instruments is small and quantized (`0x74 / 0x5A / 0x7F /
   0x6E` in the high byte) which *looks* like a filter/brightness control, but that is
   **SPECULATIVE** and is not asserted here.
3. **The velocity→compare-value curve** (§6, MISS #1) is a table that was not located.
4. **The `pb0a = 0xC004` doubling** (§6.3).
5. **Whether the real IC303 changes timbre in response to those registers at all** cannot be
   settled from the emulator; it needs Felipe's hardware or a datasheet. What *is* settled is
   that the firmware writes different values for different variants, and that today nothing
   downstream looks at them.

---

## 9. Reproduction

```
# STATIC — the firmware walk (python stdlib only)
python3 <scratchpad>/fw/mkimg.py                       # interleave IC3/IC1 -> table_data.bin
python3 <scratchpad>/fw/diag.py 0 1 2 3 5 6 7 9 11 14 16   # full per-patch dump
python3 -c "import fp; print(fp.line(0))"              # one-line fingerprints, +040 streams

# LIVE — select a variant from the panel and capture the register stream
python3 <scratchpad>/vd/mkrun.py 3 run3.mid            # MIDI at the schedule's times (+10 s)
cd kn7000-emulator && VTAG=A \
  VSOUNDS="Piano:CPL_SEG10:2,BrightPiano:CPL_SEG10:1,Piano1Octave:CPL_SEG9:4" \
  timeout 400 ./kn7000 kn5000 -rp roms -window -nomaximize -skip_gameinfo \
    -nvram_directory <copy of scratchpad/nvram2> -snapshot_directory <dir> \
    -midiin2 run3.mid -autoboot_delay 0 -autoboot_script <scratchpad>/vd/vcap2.lua \
    -seconds_to_run 45 -nothrottle -sound none
python3 <scratchpad>/vd/an.py vcap_A.log [-v]          # per note-on register picture

# page-2 sounds: append ":2" to the VSOUNDS entry (vcap4.lua presses PAGE first)
# audio A/B: swap -sound none for -wavwrite ab.wav; compare channel 1, onset-aligned
```

Soft-key port map (from `kn5000_cpanel.cpp`): `LEFT1..5` = `CPL_SEG10:0x02, CPL_SEG10:0x01,
CPL_SEG9:0x04, CPL_SEG9:0x02, CPL_SEG9:0x01`; `RIGHT1..5` = `CPL_SEG8:0x04, CPL_SEG8:0x02,
CPL_SEG8:0x01, CPL_SEG7:0x02, CPL_SEG7:0x01`; `PAGE` = `CPL_SEG2:0x80`.

Two capture traps learned this pass: a button press scheduled at the very frame the boot
settles is swallowed (the first sound of a run must be a throwaway or re-pressed), and pressing
the SOUND-GROUP button while the SOUND screen is already on page 2 leaves it on page 2, so the
PAGE press then goes back to page 1 (this silently selected the wrong variant once, caught by
the live patch-name read-back).
