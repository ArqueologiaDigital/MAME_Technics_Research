# KN5000 IC303 HLE audit — dimension: OUTPUT PATH (pan, "effect sends", mixing, globals, sample rate)

Author: autonomous audit pass, 2026-07-26. Requested by Felipe Sanches.
Scope: what leaves the chip — the group-8/9/10 level registers, the 13 global registers,
the final mix / limiter, and the sample rate. Static trace of the sub-CPU disassembly
**plus a fresh live capture of the complete register stream** (no rebuild — a Lua bus tap
on the sub-CPU at `0x100000/0x100002`, so it sees exactly what the chip sees).

Evidence labels: **MEASURED** (read from the disasm / dumped from ROM / captured live),
**INFERRED** (deduction from measured facts), **SPECULATIVE**. Every claim is cited by
asm line + ROM address, ROM byte offset, or `file:line`.

Sources
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
  (line numbers below are 1-based in that file; `LABEL_0xxxxx` **is** the ROM address).
* sub-CPU ROM `kn5000_original_roms/kn5000/kn5000_subprogram_v142.rom`
  (**file offset = address − 0xEF00**, verified against the two key-bed tables the driver
  already dumped at 0x01F43E/0x01F53E).
* HLE `kn7000_mame/src/mame/matsushita/kn5000_tonegen.{cpp,h}`, driver `kn5000.cpp`.
* Sibling audits of the same HLE from this review, in this directory:
  `kn5000-audit-voicelife.md` (voice lifecycle / allocation) and
  `kn5000-audit-pitch.md` (pitch). GAP 1 below (the missing chip-side envelope) is the
  reason a held voice never decays to silence and never self-releases, so it is the shared
  root of several lifecycle symptoms — read them together.
* **NEW live capture** (this pass): `scratchpad/outcap.lua` → `outcap.txt` (2 s hold) and
  `outcap2.lua` → `outcap2.txt` (8 s hold), default sound (PIANO), part R1, C4,
  driver key-bed velocity. Reproduce with:
  `OUTCAP_OUT=<f> OUTCAP_T0=22 ./kn7000 kn5000 -rompath roms -window -nomaximize \`
  `  -skip_gameinfo -nvram_directory <dir> -autoboot_script outcap.lua -autoboot_delay 0`
  (the earlier `scratchpad/tgcap.lua` recorded **n=0** because the tap handle was a local
  and Lua GC collected it; keeping it in a global is the whole fix.)

---

## 0. TL;DR

1. **There is no per-voice PAN in the IC303 register stream.** MEASURED, live: no register
   pair ever carries an L≠R relationship; where a pair is written by the same builder the
   two words are *bit-identical* except for a constant `0x0080` in the `+0x800` copy. The
   HLE's hard-centre pan is therefore **correct as-is** — but the reason recorded in
   `notes/kn5000-tonegen-register-semantics.md` ("pan is folded into the group8/9/10 L/R
   gains") is **FALSIFIED**.
2. **There are no per-voice EFFECT SENDS either.** `+0x8C0`, `+0x900…+0x9C0`, `+0xA00/+0xA40`
   are **envelope stages**, not sends. The brief's framing is corrected here.
3. **The real finding: `+0x800…+0xA40` is a chip-side, 3-domain, multi-stage ENVELOPE
   GENERATOR**, ten registers in one uniform format `{ target level : high byte,
   rate : low byte }`. Over an **8-second held note the sub-CPU writes NOTHING** to IC303
   (MEASURED, `outcap2.txt`) — so the entire amplitude contour is produced *inside the chip*
   from those ten words. The HLE reads one high byte and holds it constant, so **every
   KN5000 note in MAME is flat-topped: no attack, no decay, no sustain fall.** This is the
   single largest audible defect on the output path.
4. **Sample rate is wrong.** The HLE streams at 48 000 Hz (`kn5000_tonegen.cpp:76`); the
   KN5000 audio path runs at **44 100 Hz**. Pitched notes are unaffected (the pitch model is
   period-relative), but the 44 aperiodic chunks (drums/SFX) play **+146.7 cents sharp**.

---

## 1. WHAT THE FIRMWARE DOES

### 1.1 The complete register inventory (MEASURED)

Every `LD (100000h),WA` in the ROM was enumerated and its `ADD WA,<off>` recovered
(script over the whole disasm). The offsets actually used are:

| offset | group.bank | reg_idx | written at (asm line / ROM label) |
|---|---|---|---|
| +0x000 | 0.0 | 0 | gate `0x8100` / off `0x7E00` / `0xF0FF` strobe — L29754, L30210, L21F80 |
| +0x040 +0x080 +0x0C0 | 0.1-0.3 | 1-3 | wave / velocity+latch / wave-ctrl |
| +0x100 +0x140 +0x180 +0x1C0 | 1.0-1.3 | 4-7 | timbre / filter / **+0x180** / ext |
| **0x0200-0x0205** | — | GLOBAL | `ToneGen_WriteGlobalConfig` L30348-30408 |
| +0x400 +0x440 +0x480 +0x4C0 | 4.0-4.3 | 8-11 | pitch / slot counters / config |
| +0x500 +0x540 +0x580 +0x5C0 | 5.0-5.3 | 12-15 | timbre / streamed-voice ext block |
| +0x600 +0x640 | 6.0-6.1 | 16-17 | streamed-voice ext block |
| **+0x800 +0x840 +0x880 +0x8C0** | 8.0-8.3 | 20-23 | **EG domain 1** |
| **+0x900 +0x940 +0x980 +0x9C0** | 9.0-9.3 | 24-27 | **EG domain 2** |
| **+0xA00 +0xA40** | 10.0-10.1 | 28-29 | **EG domain 3** |
| **0x0C00-0x0C05, 0x0E00** | — | GLOBAL | `ToneGen_WriteGlobalConfig` L30420-30492 |

Groups 2, 12 and 14 are **never** used per-voice — only as the flat global addresses above.
(This validates the HLE's decision to intercept them wholesale; see §4.)

### 1.2 The uniform level-register format — `{ level : high byte, rate : low byte }` (MEASURED)

Every one of the ten group-8/9/10 words is assembled the same way, by six different builders:

```
LABEL_026769  L20831-20838   ; domain 1  -> 0x0451F8 / 0x0451FA
LABEL_02695A  L20951-20956   ; domain 1  (sustain-pedal variant)
LABEL_0266D8  L20714-20722   ; domain 1  (CC path)
LABEL_026975  L21071-21099   ; domain 2  -> 0x0451FC / 0x0451FE
LABEL_026AAA  L21193-21212   ; domain 3  -> 0x045200 / 0x045202
LABEL_023B21  L16123-16307   ; note-on   -> 0x0451EC/EE/F0  (+0x900/+0x940/+0x980)
LABEL_0247BF  L17455-17561   ; note-on   -> 0x0451F2/F4/F6  (+0x9C0/+0xA00/+0xA40)
LABEL_0248D5  L17566-17700   ; note-on   -> 0x0451EA        (+0x8C0)
LABEL_02576E  L19074-19085   ; note-on   -> 0x0451E4        (+0x800)
LABEL_0259C2  L19318-19348   ; note-on   -> 0x0451E6/E8     (+0x840/+0x880)
```

canonical shape (`LABEL_026A93`, asm L21080-21087):

```
    LD_H 000h            ; keep only the low byte of the rate result
    LD WA, IZ            ; IZ = the LEVEL
    SLA 8, WA            ; level << 8
    OR  WA, HL           ; | rate
    LD (0451FCh), WA
```

**HIGH byte = LEVEL.** `IZ = TBL_0x0118FE[ clamp(patch_level + keyscale, 0, 100) ]` then
`+ velocity_term` (`LABEL_022BB8` L14463) then `clamp(0,0xFF)` (`LABEL_023328` L15237).
The table was dumped from ROM (offset 0x29FE): **101 entries, strictly decreasing,
`[0]=255 … [100]=4`**. So `0x00 = silent, 0xFF = maximum`. Three independent confirmations
that HIGHER = LOUDER:
* the mute path writes level `0x00` — `LABEL_026C43` L21250 (`LDW (0451F8h),0080h`);
* the ceiling clamp writes level `0xFF` — `LABEL_026FDD` L26FDD/asm L21617-21641
  (`LDW (100002h),0ff00h` to +0x840, `0ff80h` to +0x800);
* the velocity term is **added** to the level (`ADD IZ,HL`, L20825/L21008), and higher
  velocity is louder.
**This confirms the polarity fix of 7072b09 from the firmware side, independently of ear.**

**LOW byte = RATE.** Two tables, both dumped from ROM:
* `TBL_0x011963` (offset 0x2A63), **101 entries, `[0]=0 … [100]=127`** — a *unipolar*
  0..100 → 0..127 map. Used for `+0x800`'s rate: `LABEL_02576E` L19078-19082
  (`LD A,(XWA+028h); LDA XBC,011963h; LD A,(XBC+WA)`).
* `TBL_0x0119C8` (offset 0x2AC8), **51 entries, `[0]=0 … [50]=127`**, applied by
  `LABEL_022B68` (L14422) which clamps the input to ±50, looks up the magnitude and
  **restores the sign** → a *bipolar* int8 in [−127,+127]. Used for every other stage.
  Its inputs are a **common per-patch base plus a per-stage offset**, e.g.
  `rate(+0x9C0) = curve(clamp(TONE[+0x3d] + TONE[+0x40], −50, +50))`,
  `rate(+0xA00) = curve(clamp(TONE[+0x3d] + TONE[+0x42], …))`,
  `rate(+0xA40) = curve(clamp(TONE[+0x3d] + TONE[+0x44], …))` (asm L17463-17561).
  A shared base with per-stage deltas is envelope-shaped; three independent *sends* would
  not share a base.

**`rate = 0` means HOLD.** Proven by the unused-stage sentinel: an unprogrammed stage is
`0xAE00` = level 174, rate 0 (see the per-instrument capture in
`notes/kn5000-pipe-registers.md` §4b: STRINGS/FLUTE leave *six* stages at `0xAE00`). If
rate 0 meant "fastest" an unused stage would slam the level to 174; only "no movement"
makes the sentinel work.

### 1.3 Three EG DOMAINS (MEASURED structure, INFERRED naming)

The per-segment updater `LABEL_027FD6` (L23045) — bank-duplicated as `LABEL_02D436`
(L29936) — rewrites exactly **six** registers, in this order:

```
+0x840 <- blk[+0x2e]     +0x940 <- blk[+0x32]     +0xA00 <- blk[+0x36]
+0x800 <- blk[+0x2c]     +0x900 <- blk[+0x30]     +0x9C0 <- blk[+0x34]
```

i.e. three **pairs** `(+0x800,+0x840) (+0x900,+0x940) (+0x9C0,+0xA00)`, fed by the three
builders 026769 / 026975 / 026AAA respectively. Combined with the note-on order this gives:

| domain | registers | level source (TONE struct = slot[+0x17]) |
|---|---|---|
| **1** | +0x800, +0x840, +0x880, +0x8C0 | `TONE[+0x2d]` + channel volume `chan[+0x6c]`, floor-limited by the **sustain pedal** (`chan[+0x0a]` bit0, doc CC 0x40 offset +0x72) → **AMPLITUDE** |
| **2** | +0x900, +0x940, +0x980, (+0x9C0) | `TONE[+0x0f]/[+0x09]/[+0x0b]/[+0x0d]`, bipolar rates `TONE[+0x0a]/[+0x0c]/[+0x0e]`, whole-domain sign flip if `TONE[+0x07] < 0` |
| **3** | (+0x9C0), +0xA00, +0xA40 | `TONE[+0x45]`, rates `TONE[+0x3d] + [+0x40/+0x42/+0x44/+0x46]` |

Domain 1 is **AMPLITUDE**: MEASURED, because its level is the one the sustain pedal and the
channel volume act on. Domains 2 and 3 are **bipolar** (their rates can go negative and a
whole domain can be inverted by one sign bit) — the signature of **pitch** and **filter**
envelopes. **INFERRED**, and strongly corroborated cross-model: the KN7000's tone-gen has
exactly this shape — *three* parallel per-note EGs of three rate/level words each
(`notes/kn5000-vs-kn7000-tonegen-design.md` §2, `r0..rB` = `[rate hi | level lo]`). The
KN5000 is the same design with the two bytes **swapped** (`[level hi | rate lo]`).

### 1.4 LIVE CAPTURE — the whole note, decoded (MEASURED, this pass)

Default sound (PIANO), part R1, C4, 8-second hold. Complete stream for voice 0
(`scratchpad/outcap.txt`; voice 1 is identical modulo `+0x040 = 0x7017` and `+0x180`):

```
t=22.307361  0840 FF00 |  pre-mute (max level, rate 0)
t=22.307363  0800 FF80 |
t=22.307747  0040 7007    bank 1 (IC307) page 3 chunk 0x007   <- a real piano chunk
             0080 8E52    velocity, bit15 = load latch SET
             00C0 7400  0100 2466  0140 6FDA  0180 0000
             0400 34C1    pitch
             0440 0000  0480 0000  04C0 4400  0500 2C72
             0800 E57F  <-- EG D1 stage0
             0000 8100    KEY-ON
             0840 484C  <-- EG D1 stage1
             0880 4000  <-- EG D1 stage2
             08C0 00B0  <-- EG D1 stage3
             0900 AE00  0940 AE00  0980 AE00      <-- EG D2, all UNUSED
             09C0 FF00  0A00 40E8  0A40 30B0      <-- EG D3
             0080 0E52    bit15 CLEARED (latch release)
t=22.308297  0000 F0FF    note-on strobe (magnitude 0xFF)
     ... 8.000 SECONDS OF HELD KEY:  ***ZERO WRITES***  ...
t=30.313234  0840 8B00  0940 AE00  0A00 4FB0
             0800 8B80  0900 AE00  09C0 4FB0      <- exactly LABEL_027FD6's 6-write order
t=30.376416  00C0 0000    wave-ctrl cleared
             0000 7E00    gate off
```

Decoded under `{level, rate}`:

| reg | word | level | rate | reading |
|---|---|---|---|---|
| +0x800 | `E57F` | 229 | +127 (max) | **ATTACK** — go to 229 as fast as possible |
| +0x840 | `484C` | 72 | +76 | **DECAY** — fall to 72 |
| +0x880 | `4000` | 64 | 0 (hold) | **SUSTAIN** at 64 |
| +0x8C0 | `00B0` | 0 | −80 | **RELEASE** — fall to silence |
| +0x900/940/980 | `AE00` | 174 | 0 | domain-2 stages **unused** (sentinel) |
| +0x9C0/A00/A40 | `FF00 / 40E8 / 30B0` | 255 / 64 / 48 | 0 / −24 / −80 | domain-3 stages |

**That is a textbook ADSR for a piano**, read straight out of the register stream. It is
also the complete explanation of why the HLE's notes do not decay.

**Cross-capture corroboration of the `{level, rate}` format (independent instrument,
independent capture, independent pass).** In §4b's table the FLUTE row is the one whose
`+0x800/+0x840` are burst values rather than pre-mute writes: `+0x800 = E67F`,
`+0x840 = 5E74`, `+0x880 = 326A`. Compare my PIANO measurement: `+0x800 = E57F`,
`+0x840 = 484C`, `+0x880 = 4000`. The **stage-0 rate byte is `0x7F` in both** — the
`TBL_0x011963` maximum, i.e. "attack as fast as possible", on two unrelated instruments
captured months apart; and both stage-0 levels sit at 0xE5/0xE6. The levels then fall
monotonically stage by stage in both (229→72→64 and 230→94→50) while the rate bytes stay
in the 0x4C-0x74 band. A byte pair that were *left gain / right gain* would show no such
structure. **PREDICT-THEN-CHECK: HIT.**

Predict-then-check against `notes/kn5000-pipe-registers.md` §4b (an older per-instrument
capture): +0x8C0 `00B0` **exact**, +0x900/+0x940/+0x980 `AE00` **exact**, +0x9C0 `FF00`
**exact**; +0xA00/+0xA40 low bytes `E8`/`B0` **exact**, high bytes 0x40/0x30 vs 0x36/0x26 —
**MISS of +10/+10 level units, explained**: that capture predates the key-bed velocity fix
(7072b09), so the same key produced a different velocity, and the velocity term is *added*
to the level. Second **MISS**: §4b's `+800 FF80 / +840 FF00` are the **pre-mute** words, not
the burst values (§4b itself suspected this); the real note-on values are `E57F` / `484C`.
Both misses reported; neither changes the model.

### 1.5 The 13 GLOBAL registers (MEASURED — completely)

`ToneGen_WriteGlobalConfig` (asm L30334, internal labels `LABEL_02D7DA/02D7DE`) copies a
26-byte struct to the 13 global addresses, and is called from **exactly one place**:
`DSP_Config_Init` (asm L31095-31099) with `LDA XWA, 0F8BBh` — a RAM copy of the ROM image
(the sub-program is a downloaded payload, so it is writable). Dumped from ROM offset 0x9BB
and **confirmed byte-for-byte by the live capture**, at t = 4.065 s, written once and
never again in 33 s of running including a full note:

| global | value | source |
|---|---|---|
| 0x0200 | `0x0060` | struct[+0x00], **bit 3 patched at runtime** |
| 0x0201 | `0x0993` | struct[+0x02] |
| 0x0202 | `0x0001` | struct[+0x04] |
| 0x0203 | `0x0004` | struct[+0x06] |
| 0x0204 | `0x0004` | struct[+0x08] |
| 0x0205 | `0x000C` | struct[+0x0A] |
| 0x0C00-0x0C03 | `0x0000` | struct[+0x0C..+0x12] |
| 0x0C04 | `0x0020` | struct[+0x14] |
| 0x0C05 | `0x0001` | struct[+0x16] |
| 0x0E00 | `0x0000` | struct[+0x18] |

**The only dynamic bit in the whole global block is bit 3 of 0x0200** (asm L30338-30346:
`LD WA,(041343h); BIT 3,WA; JR Z → ORW (XIZ),0008h ; else ANDW (XIZ),0fff7h`), and RAM
`0x041343` bit 3 is itself set from a **board strap on sub-CPU port PH bit 3**
(`DSP_System_Init_Vars`, asm L38124-38130, the disasm's own comment: "Check hardware config
pin"). The driver pins it with `m_subcpu->porth_read().set_constant(0x01)`
(`kn5000.cpp:1039`), which selects the `0x0060` variant (PH.3 = 0). With PH.3 = 1 the chip
would be configured with `0x0068` instead.

**What the 13 values *mean* is NOT derivable from the firmware.** The sub-CPU treats them as
an opaque blob: one static image, one strap bit, no computation, no per-note use. Any
bit-by-bit interpretation would be invention, so none is offered here.

### 1.6 The real DAC path and the SAMPLE RATE

Board (service-manual chip list, `kn5000-docs/tone-generator.md` §"IC Inventory"):

```
IC304-307 wave ROMs -> IC303 TC183C230002 (tone gen)
                          -> IC311 DS3613GF (DSP1) + IC310 MN19413 (DSP2)   [effects]
                          -> IC313 PCM69AU  18-bit stereo DAC  (serial audio: BCK, SDOR/SDOF)
                          -> IC312 / IC314 M5218AFP op-amps -> FAJ board (mixing, LPF) -> amp
```

**The audio frame rate is 44 100 Hz — MEASURED, twice, independently:**
* the sub-CPU converts effect delay-times with `ms × 0xAC44 / 0x3E8` = `ms × 44100 / 1000`
  (asm L46298, L46312, … 17 sites) — `notes/kn5000-dsp-parameters.md` §3;
* the double constant `π/44100 = 7.1237928650000007e-05` at ROM `0x012F57` (and `0x012FBF`,
  `0x012FEB`) drives the biquad coefficient math — `notes/kn5000-dsp-biquad-coeffs.md`.

Those measure the **DSP**. IC303 feeds the DSPs, which feed one PCM69AU on one serial audio
bus with one LRCK — there is no sample-rate converter anywhere on the path. So **IC303's
output frame rate is 44 100 Hz: INFERRED (strong)**. The `48 kHz` in
`kn5000-docs/audio-subsystem.md` L1959 and `tone-generator.md` L365/L371 is a description of
the *HLE*, not a hardware measurement — it is circular and should be corrected.

---

## 2. WHAT THE HLE DOES

| item | code | behaviour |
|---|---|---|
| stream | `kn5000_tonegen.cpp:76` | `stream_alloc(0, 2, 48000)` — 48 kHz literal |
| device clock | `kn5000.cpp:1117` | `KN5000_TONEGEN(config, m_tonegen, 0)` — **no clock at all** |
| globals | `kn5000_tonegen.cpp:154-170` | decoded and stored in `m_global_regs[13]`, logged, **never read** |
| level | `kn5000_tonegen.cpp:495` | `loglevel = (v.regs[20] >> 8) & 0xFF` — high byte of `+0x800` only |
| gain law | `kn5000_tonegen.cpp:490-513` | `gain = 2^((loglevel − 231)/10)`, clamped to 1.0. K and REF are **CALIBRATED**, not derived |
| pan | `kn5000_tonegen.cpp:515-520` | `volume_l = volume_r = amp` — hard centre |
| envelope | `kn5000_tonegen.cpp:224, 1520` | `env_level = min(data & 0x1FF, 0xFF)` from group0/bank0; `sample = sample * env_level / 0xFF` |
| release | `kn5000_tonegen.cpp:1369, 1375, 1526` | fixed 2400-sample (50 ms @48 k) linear fade + 4800-sample hold |
| mix | `kn5000_tonegen.cpp:1555-1556` | `mix += (sample * volume) >> 15` |
| limiter | `kn5000_tonegen.cpp:1569-1579` | `x = 0.70 * acc/32768`; pass-through below 0.75; `tanh` above |
| aperiodic pitch | `kn5000_tonegen.cpp:743-747` | `pitch_step = 0x10000` = one recording sample per **48 kHz** output sample |
| periodic pitch | `kn5000_tonegen.cpp:785` | `step = freq * period_q16 / 48000.0` |

Registers **stored and never read** on the output path: `regs[6]` (+0x180), `regs[21]`
(+0x840), `regs[22]` (+0x880), `regs[23]` (+0x8C0), `regs[24..27]` (+0x900…+0x9C0),
`regs[28..29]` (+0xA00/+0xA40), and all 13 globals — **10 per-voice output registers + 13
globals ignored, 1 half-register (the high byte of +0x800) used.**

---

## 3. THE DELTA — numbered gaps

### GAP 1 — The chip-side multi-stage ENVELOPE is not modelled at all. Every note is flat. **[MEASURED]**
* **Wrong:** the HLE takes the *note-on* value of `+0x800`'s high byte as a static gain
  (`kn5000_tonegen.cpp:495, 511, 519`) and never looks at the other nine stage registers.
  The sub-CPU's `env_level` path (`:224, :1520`) cannot compensate: over an **8-second held
  note the firmware writes `0x0000 ← 0xF0FF` exactly once**, so `env_level` is a constant
  0xFF (MEASURED, `outcap2.txt`, 0 writes between note-on and key-up).
* **Audible consequence:** the *whole* amplitude shape is missing. The captured PIANO
  programs A=229 → D=72 → S=64 → R=0; the HLE renders a constant 229 forever. A piano that
  never decays, an organ and a piano with identical contours, brass that never swells,
  strings that never fade in. It also makes every held note sustain indefinitely instead of
  decaying to silence and self-releasing (on hardware the chip drops a finished voice from
  the active-voice bitmap and the firmware then gates it off).
* **Firmware-derived fix:** decode the ten words as `{target level = w>>8, rate = w&0xFF}`
  and run a per-voice level walker inside the device: start at the domain-1 stage-0 target,
  advance toward each successive stage's target at that stage's rate, `rate == 0` = hold
  (proven by the `0xAE00` sentinel), jump to the release stage on key-off. Domain 1
  (+0x800/+0x840/+0x880/+0x8C0) is AMPLITUDE (MEASURED — the sustain pedal and channel
  volume act on its level). **Honest limit: the rate→time conversion and the exact stage
  sequencing are IC303 internals and are NOT derivable from the firmware.** They must be
  calibrated once (and labelled CALIBRATED), exactly like K/REF already are. Everything
  else — which registers, which byte, that 0 = hold, that domain 1 is amplitude — is
  measured.
* **Confidence: MEASURED** (the gap and the format); **INFERRED** (domain 2/3 = pitch/filter).

### GAP 2 — The RATE byte is discarded, so every level change is an instantaneous step. **[MEASURED]**
* **Wrong:** `kn5000_tonegen.cpp:495` keeps only `regs[20] >> 8`. The low byte — the rate —
  is thrown away everywhere.
* **Audible consequence:** the key-up burst writes `+0x800 ← 0x8B80` = "go to level 139 at
  rate 0x80". The HLE jumps the gain from 0.871 to 0.0017 **in one sample** (a −55 dB step),
  then applies its own unrelated 50 ms linear fade. That is a click plus a fade, where the
  hardware has one smooth ramp. Same for every note-on: the attack is instantaneous.
* **Firmware-derived fix:** treat the low byte as the rate for the ramp to the new target
  (see GAP 1). Note the encoding is self-consistent: the CPU-driven segment writes use rate
  `0x80` = **128**, one above `TBL_0x011963`'s maximum of 127 — i.e. "immediate", which is
  exactly right for a level the CPU has already interpolated.
* **Confidence: MEASURED.**

### GAP 3 — Sample rate: the HLE runs 8.84 % fast. **[MEASURED / INFERRED]**
* **Wrong:** `kn5000_tonegen.cpp:76` `stream_alloc(0,2,48000)`, `:785` `/48000.0`,
  `:1369/:1375` `2400`/`4800`. The hardware path is **44 100 Hz** (§1.6).
* **Audible consequence:**
  * **Aperiodic chunks** (`:743-747`, `pitch_step = 0x10000` = "the recording's own rate")
    play at 48 kHz instead of 44.1 kHz — **+146.7 cents sharp and 8.8 % shorter**. That is
    every drum, hi-hat, applause and telephone sample: **16/198 of page 0 and 28/168 of
    page 1** by the code's own count. A whole drum kit a semitone-and-a-half sharp.
  * The release/hold constants are 8.8 % short (50 ms → 45.9 ms, 100 ms → 91.9 ms).
  * Pitched notes are **unaffected** (see §4) — the pitch model is period-relative.
* **Firmware-derived fix:** `stream_alloc(0, 2, 44100)`, `/44100.0`, `2205`/`4410`; and give
  the device a real clock instead of `0` (`kn5000.cpp:1117`) so the rate is derivable rather
  than a literal.
* **Confidence: MEASURED** that the DSP/delay path is 44 100 Hz and that the HLE is 48 000;
  **INFERRED (strong)** that IC303 shares that frame rate (one serial audio bus, one DAC, no
  SRC on the board).

### GAP 4 — `REF = 231` clips the top 10 % of the level scale. **[MEASURED]**
* **Wrong:** `kn5000_tonegen.cpp:493` `REF = 231.0` with `gain` clamped to 1.0 at `:512`.
  REF was taken from one observed note-on level. But the firmware's **own** ceiling is
  `0xFF = 255` — `LABEL_026FDD` (asm L21617-21641) explicitly clamps to `0xFF80`/`0xFF00`,
  and `LABEL_023328` (L15237) clamps every level to `[0, 0xFF]`.
* **Audible consequence:** every level from 231 to 255 renders identically at full scale —
  ~14 dB of the top of the range is flattened. It bites immediately: the captured note-on
  level is **229**, one unit under the clip edge, and `+0x9C0` is `0xFF00` = 255.
* **Firmware-derived fix:** `REF = 255.0` (the firmware's declared maximum), which uses the
  whole range and never clips. **Must be re-calibrated together with GAP 1**, not before —
  see GAP 5.
* **Confidence: MEASURED.**

### GAP 5 — The gain slope `K = 10` is demonstrably too steep once the stages are decoded. **[MEASURED consequence, slope itself NOT derivable]**
* **Wrong:** `kn5000_tonegen.cpp:490` `K = 10.0` (10 level units per amplitude halving =
  0.602 dB/unit, so the 0..255 range spans **153 dB**).
* **Audible consequence:** under that slope the firmware's own PIANO stages land at
  attack −1.2 dB, **decay −95.7 dB, sustain −100.5 dB**. The moment GAP 1 is implemented the
  entire envelope below level ~200 becomes inaudible and the note becomes a click. A
  plausible chip scale (0.25 dB/unit ⇒ 64 dB full range) puts the same stages at
  −6.5 / −45.8 / −47.8 dB — musical.
* **Firmware-derived fix:** none. **SAY SO EXPLICITLY: the dB-per-level-unit of IC303 is a
  chip internal and cannot be derived from the sub-CPU firmware.** What *is* derivable is
  the constraint set: level 0 = silence, level 255 = the firmware's maximum, and the stage
  levels above. K must be re-fitted against those constraints together with GAP 1/GAP 4 and
  labelled CALIBRATED.
* **Confidence: MEASURED** (that K=10 collapses the decoded stages); **not derivable** (the
  correct value).

### GAP 6 — 10 per-voice output registers stored and never read. **[MEASURED]**
`regs[21] (+0x840)`, `regs[22] (+0x880)`, `regs[23] (+0x8C0)`, `regs[24..27] (+0x900…+0x9C0)`,
`regs[28..29] (+0xA00/+0xA40)` — subsumed by GAP 1 — **plus `regs[6]` (+0x180)**, which the
capture shows **differs between the two oscillators of the same note**: voice 0 gets
`0x0000`, voice 1 gets `0x007F`. Whatever it is, it is a *per-oscillator* differentiator the
render is blind to, and it is one of the registers "Bright Piano" and "Mellow Piano" can
differ in. Its meaning is **not decoded** — the two candidate build paths are
`LABEL_0249BF` (asm L17662-17701, `+0x2b` = 0 / 0x7F / `TONE[0]` selected by
`chan[+0x26]`) and the second-domain stepper `LABEL_026EC3 → LABEL_02D670` (asm L30169).
**No claim is made that it is pan.**
* **Confidence: MEASURED** (that it differs per oscillator and is ignored); meaning **OPEN**.

### GAP 7 — The unconditional `HEADROOM` contradicts its own comment and costs 3.1 dB. **[MEASURED]**
* **Wrong:** `kn5000_tonegen.cpp:1571-1573`. The comment says "the mix passes through
  UNCHANGED below a knee K (so single notes and small chords keep full amplitude)", but
  `x = HEADROOM * acc / 32768` with `HEADROOM = 0.70` is applied to **every** sample before
  the knee test. Nothing ever passes through unchanged; a single full-scale voice peaks at
  0.61, i.e. **−4.3 dB**.
* **Audible consequence:** the whole instrument is quieter than it should be, and the
  documented behaviour is not the implemented behaviour.
* **Fix:** either drop `HEADROOM` and lower the knee, or fix the comment. Not
  firmware-derivable (IC303's internal headroom/limiting is undumped) — but the code/comment
  mismatch is objective.
* **Confidence: MEASURED.**

### GAP 8 — The 13 globals are stored and never read; one of them is board-strap dependent. **[MEASURED]**
* **Wrong:** `kn5000_tonegen.cpp:154-170` stores them; nothing consumes them.
* **Audible consequence:** **probably none today**, and this is an honest "cannot say more":
  the values are a single static image written once at boot (§1.5, confirmed live), so
  ignoring them cannot make the *dynamics* wrong. What they configure (voice count?
  interpolation? output routing? master level?) is not derivable — the firmware never
  computes with them.
* **Actionable sub-item:** global `0x0200` bit 3 mirrors sub-CPU **port PH bit 3**, a board
  strap, currently pinned by `kn5000.cpp:1039` `porth_read().set_constant(0x01)` — an
  **unverified driver constant** that silently selects `0x0200 = 0x0060` over `0x0068`. Worth
  a line in the driver comment (and a question for Felipe: what is PH.3 wired to?).
* **Confidence: MEASURED.**

### GAP 9 — Release/hold are hardcoded and not firmware-derived. **[MEASURED]**
`release_counter = 2400` / `hold_counter = 4800` (`:1369`, `:1375`) are 50 ms / 100 ms at
48 kHz with a **linear** fade (`:1526`). Once GAP 1/GAP 2 land, the release ramp comes from
`+0x8C0` = `{level 0, rate}` and this hand-rolled fade should go away entirely (the
`hold_counter` bookkeeping lifetime for the firmware's status poll must stay).

### GAP 10 — The release *detector* is still a heuristic, but the capture shows why it works. **[MEASURED]**
`kn5000_tonegen.cpp:246-251` triggers key-off on a group-9/bank-0 write more than 1 ms after
the gate. In the capture, `0900` appears **twice**: at note-on **12 µs** after the gate
(`t=22.307783` gate → `t=22.307795`), and in the key-up burst 8 s later. So the 1 ms
threshold separates them by three orders of magnitude — the heuristic is safe *for this
path*. It remains a heuristic: any future firmware path that rewrites `+0x900` mid-note
would false-trigger a release. The real decode is the six-register `LABEL_027FD6` burst
signature (`+0x840, +0x940, +0xA00, +0x800, +0x900, +0x9C0` in that exact order, MEASURED
live), which is a far stronger match than "a write to one register".

### GAP 11 — Two doc pages assert a 48 kHz hardware sample rate that is really the HLE's. **[MEASURED]**
`kn5000-docs/audio-subsystem.md:1959` and `tone-generator.md:365/371` state "48 kHz" as a
hardware property. It is circular (it describes `kn5000_tonegen.cpp:76`) and contradicts the
driver's own comment at `kn5000.cpp:1094-1097` ("the sample rate is 44,100 Hz"). Fix the
docs with GAP 3.

---

## 4. AUDITED AND FOUND CORRECT

These were checked against the firmware and are **right as they stand** — with, in two
cases, a *wrong recorded reason* that this note corrects.

1. **Hard-centre pan is CORRECT.** **MEASURED**: there is no per-voice pan anywhere in the
   IC303 register stream. Where the firmware writes a "pair", the two words are identical
   except for a constant `0x0080` in the `+0x800` copy — `LABEL_026769` L20831-20838,
   `LABEL_0266D8` L20714-20722, `LABEL_02685B` L20866-20872, `LABEL_026BDC` L21221-21228,
   `LABEL_026C16` L21243-21247, `LABEL_026C43` L21250-21251 (**6/6 sites, no exception**),
   and confirmed live in the key-up burst (`+0x800 = 8B80`, `+0x840 = 8B00`;
   `+0x900 = +0x940 = AE00`; `+0x9C0 = +0xA00 = 4FB0`). `LABEL_02D620` (asm L30130-30147)
   even writes the *same* word to `+0x840` **and** `+0x880`.
   **Correction:** `notes/kn5000-tonegen-register-semantics.md` §Q6 item 5 ("Pan … is folded
   into the group8/9/10 L/R gains") and §"What must change" item 3 (`gain_L = reg[20]>>8`,
   `gain_R = reg[21]>>8`) are **FALSIFIED** — `reg[20]` and `reg[21]` are *envelope stage 0
   and stage 1*, not left and right. Implementing that recommendation would have made the
   attack level the left channel and the decay level the right channel. **Do not do it.**
   If the KN5000 pans parts at all (the UI/CC 0x0A path exists — `sound-parameter-protocol.md`
   L140), it does **not** reach IC303 through the per-voice registers; it must be downstream
   (DSP/mixer) or in a path not yet traced. **Cannot be derived from what was audited —
   saying so rather than inventing a mapping.**
2. **Ignoring "effect sends" is CORRECT, because there are none.** `+0x8C0`, `+0x900…+0x9C0`,
   `+0xA00/+0xA40` are envelope stages (§1.2-§1.4). The per-voice register stream contains
   **no wet/dry send**. (This corrects the audit brief's own premise.)
3. **The level POLARITY (higher = louder) is CORRECT** — the 2026-07-26 fix in 7072b09 is
   confirmed from the firmware, three independent ways (§1.2), so it no longer rests on ear
   alone.
4. **Taking only the HIGH byte of `+0x800` as the level is CORRECT** — the low byte is a
   separate field (the rate), so `regs[20] >> 8` is the right extraction. (What is wrong is
   *discarding* the low byte, GAP 2, not including it.)
5. **The global-address decode is CORRECT.** `kn5000_tonegen.cpp:154-170` intercepts
   `0x02xx`, `0x0Cxx`, `0x0E00` before the per-voice decode. MEASURED by exhaustive
   enumeration of every `LD (100000h)` in the ROM: groups 2, 12 and 14 are **never** used as
   per-voice addresses, so nothing is stolen from the voice path. The 13 captured global
   writes land on indices 0-12 with no aliasing.
6. **Pitch of PERIODIC recordings is INDEPENDENT of the stream rate** — `:785` computes the
   step from an absolute target frequency, so the fundamental lands on `freq` Hz whatever the
   stream rate is. GAP 3 therefore does **not** detune pitched notes; only the aperiodic
   `pitch_step = 0x10000` path is affected. (Checked explicitly so GAP 3 is not overstated.)
7. **The mix accumulator cannot overflow.** `sample` ≤ 32767 after interpolation and the
   `env_level` scale; `(sample * volume) >> 15` ≤ 32767 per voice; 64 voices ≤ 2.1 M, far
   inside int32. `:1555-1556` is safe.
8. **The `0x0080` bit in `+0x800` is correctly not treated as level** — it is a rate value
   (128 = "immediate"), and `regs[20] >> 8` already drops it.

---

## 5. Reproducing the measurements

```
# register-stream capture (no rebuild needed)
cd /home/fsanches/compartilhado/kn7000-emulator
OUTCAP_OUT=/tmp/outcap.txt OUTCAP_T0=22 timeout 420 ./kn7000 kn5000 -rompath roms \
  -window -nomaximize -skip_gameinfo -nvram_directory <isolated-nvram-dir> \
  -autoboot_script <scratchpad>/outcap.lua -autoboot_delay 0 -video opengl -sound none
```
Script: `scratchpad/outcap.lua` (2 s hold) / `outcap2.lua` (8 s hold). **The tap handle must
be stored in a Lua global** or GC silently disables it (that is the `n=0` failure mode of the
older `tgcap.lua`).

ROM table dumps (`file offset = address − 0xEF00`, file
`kn5000_original_roms/kn5000/kn5000_subprogram_v142.rom`):
`0x0118FE` level (101 entries, 255→4), `0x011963` unipolar rate (101, 0→127),
`0x0119C8` bipolar rate magnitude (51, 0→127), `0x00F8BB` the 13-word global-config image,
`0x00F8D5` the 34-word voice template.
