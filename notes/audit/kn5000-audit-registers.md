# KN5000 tone-gen (IC303) AUDIT — the per-voice REGISTERS

Audit dimension: *for every per-voice register the firmware writes, which routine computes it, from
what data, what it means, and whether the HLE reads it.*

Author: autonomous audit pass, 2026-07-26. Requested by Felipe Sanches.

Sources, and how to read the citations:
* **asm L<n>** = 1-based line in `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`.
* **cpp:<n>** = line in `kn7000_mame/src/mame/matsushita/kn5000_tonegen.cpp` at commit `7072b09`.
* **LIVE** = this pass's own capture of the sub-CPU bus at `0x100000` / `0x100002` (a MAME Lua
  write-tap — no emulator rebuild, so the stream is exactly what the chip is given), with the
  sub-CPU PC recorded for every write so each one is attributed to its firmware routine.
  Three captures, all reproduced in §7: **C4 note** (one manual key, 2 s hold + release, 68 writes),
  **rhythm census** (16-Beat-1 + a 3-note left chord + 3-note right chord + 3 more keys, 5734 writes
  / 215 note-ons), **rhythm timeline** (16-Beat-1 alone, 1884 writes / 70 note-ons).

Evidence labels: **MEASURED** (a ROM instruction or a live bus observation) / **INFERRED**
(deduction from measured facts) / **SPECULATIVE**. Nothing here rests on listening.

---

## 0. TL;DR

The firmware writes **28** distinct per-voice registers, not 22 — six extension registers
(`+0x1C0 +0x540 +0x580 +0x5C0 +0x600 +0x640`) were missing from every prior map. Two of the 32 the
HLE allocates (`+0x680 +0x6C0 +0xA80 +0xAC0`, reg_idx 18/19/30/31) are never written by any code
path in the ROM.

The HLE reads **3** of them by value (`regs[1]`, `regs[8]`, `regs[20]`), plus `regs[0]`'s data
transiently and two registers used only as *write events*. The other 23 are latched and dropped.

Two of the gaps are not "missing nuance", they are **structural and audible today**:

1. `+0x000`'s magnitude field is read as an amplitude, but the value `0` means *"this voice carries
   no software magnitude"*, not *"silence"*. **MEASURED: 197 of 215 note-ons carry it — the entire
   rhythm / auto-accompaniment section is muted.** Rendered rhythm-only RMS **2.6**; with the
   one-line firmware-derived fix, **28806.8** (+81 dB).
2. `+0x800/+0x840/+0x880/+0x8C0` (and the two sibling triples in groups 9 and 10) are a **four-segment
   hardware envelope generator**, `(target level << 8) | rate` per segment. The HLE runs no envelope
   at all: it reads segment 0's target as a *constant* gain. **MEASURED: for a rhythm voice the
   firmware writes nothing after the note-on burst and never keys it off — 70 note-ons, 0 key-offs,
   concurrent gated voices climb 1 → 64 and stay there.** The chip's own EG is the *only* thing that
   can end those voices, and the HLE has none.

Those two are coupled: fixing (1) alone turns the silence into a permanently saturated drone
(MEASURED — see §5 GAP 1). They must land together.

---

## 1. WHAT THE FIRMWARE DOES

### 1.1 The address encoding — confirmed

`addr = (group << 8) | (bank << 6) | voice`, voice = 0..63. Every one of the 28 offsets below is
built as `LD WA,<voice>; ADD WA,<offset>; LD (100000h),WA` with `offset` a multiple of 0x40
(`ToneGen_WriteSingleReg` asm L29919; the primitive is address-phase / data-phase around `P6.7`).
**MEASURED LIVE: 5734 writes, every one decodes; the HLE's "unknown group" path (cpp:186) is never
reached.**

### 1.2 The note-on burst — `ToneGen_WriteVoiceParams` (asm L29565)

`WA = chip voice`, `XBC = 0x0451CC` — a fixed 0x44-byte RAM staging block the 17-routine builder
chain fills first (`LABEL_02B4E3` asm L26803: `slot = 0x04308E + 0x47*n`, then 17 builders, then the
write). Because the block is at fixed addresses, `grep '(0451xxh)'` names the writer of every field.

The routine ships **23 writes in one fixed order**. PREDICT-THEN-CHECK against the LIVE C4 capture:
**23/23 in exactly this order, twice (both piano partials).**

| # | offset | block field | asm (ADD) | LIVE C4 value |
|---|---|---|---|---|
| 1 | `+0x040` | `blk+0x02` | L29573 | `7007` |
| 2 | `+0x080` | `blk+0x04` **`\| 0x8000`** (`SET 0fh` L29594) | L29588 | `8E52` |
| 3 | `+0x0C0` | `blk+0x06` | L29604 | `7400` |
| 4 | `+0x100` | `blk+0x08` | L29619 | `2466` |
| 5 | `+0x140` | `blk+0x0A` | L29634 | `6FDA` |
| 6 | `+0x180` | `blk+0x0C` | L29649 | `0000` |
| 7 | `+0x400` | `blk+0x0E` | L29664 | `34C1` |
| 8 | `+0x440` | `blk+0x10` | L29679 | `0000` |
| 9 | `+0x480` | `blk+0x12` | L29694 | `0000` |
| 10 | `+0x4C0` | `blk+0x14` | L29709 | `4400` |
| 11 | `+0x500` | `blk+0x16` | L29724 | `2C72` |
| 12 | `+0x800` | `blk+0x18` | L29739 | `E57F` |
| 13 | **`+0x000`** | literal **`0x8100`** | L29754/29757 | `8100` ← **the GATE** |
| 14 | `+0x840` | `blk+0x1A` | L29766 | `484C` |
| 15 | `+0x880` | `blk+0x1C` | L29781 | `4000` |
| 16 | `+0x8C0` | `blk+0x1E` | L29796 | `00B0` |
| 17 | `+0x900` | `blk+0x20` | L29811 | `AE00` |
| 18 | `+0x940` | `blk+0x22` | L29826 | `AE00` |
| 19 | `+0x980` | `blk+0x24` | L29841 | `AE00` |
| 20 | `+0x9C0` | `blk+0x26` | L29856 | `FF00` |
| 21 | `+0xA00` | `blk+0x28` | L29871 | `40E8` |
| 22 | `+0xA40` | `blk+0x2A` | L29886 | `30B0` |
| 23 | `+0x080` | `blk+0x04` **`& ~0x8000`** (`RES 0fh` L29907) | L29901 | `0E52` |

Two structural facts fall straight out and matter for the HLE:

* **`+0x080` brackets the burst** — written first with bit 15 SET and last with it CLEAR. It is a
  HOLD/COMMIT strobe, not just a parameter.
* **The gate is written in the MIDDLE (13 of 23).** `+0x840 … +0xA40` arrive *after* `0x8100`. So
  `process_key_on()` (cpp:212) runs while eight of the registers still hold the *previous* voice's
  values. Today only `regs[20]` is read there, and it is written at #12 (before the gate), so
  nothing is wrong yet — but any future read of `regs[21..29]` at key-on would read stale data.

Immediately after the burst the firmware writes the packed level/routing word to `+0x000` again
(`slot[+0x2d]`, LIVE `F0FF` at PC `02D42F` = `ToneGen_WriteSingleReg`).

### 1.3 The per-segment / release update — `LABEL_02D436` (asm L29936) and its twin `LABEL_027FD6` (L23045)

Six writes, in this order (**MEASURED LIVE at key-up, 6/6 in exactly this order**):

| offset | block field | asm | LIVE at C4 key-up |
|---|---|---|---|
| `+0x840` | `blk+0x2E` | L29943 | `8B00` |
| `+0x940` | `blk+0x32` | L29958 | `AE00` |
| `+0xA00` | `blk+0x36` | L29973 | `4FB0` |
| `+0x800` | `blk+0x2C` | L29988 | `8B80` |
| `+0x900` | `blk+0x30` | L30003 | `AE00` |
| `+0x9C0` | `blk+0x34` | L30018 | `4FB0` |

Three *pairs*, and the two members of each pair get the **identical** word. Proof for pair A
(`LABEL_026769` asm L20831-20838):

```
LABEL_02682F:
    WA = IZ ; SLA 8,WA ; SET 7,WA ; LD (0451F8h),WA   ; blk+0x2C -> +0x800 = (level<<8)|0x80
    WA = IZ ; SLA 8,WA ;           LD (0451FAh),WA   ; blk+0x2E -> +0x840 = (level<<8)
```
and identically for pair B (`LABEL_026975` asm L21083-21086, `0451FC`/`0451FE`) and pair C
(`LABEL_026AAA` asm L21211-21212, `045200`/`045202`). LIVE confirms: `8B80`/`8B00`, `AE00`/`AE00`,
`4FB0`/`4FB0`.

**This settles the pan question.** `+0x800` and `+0x840` carry the *same* number (they differ only in
bit 7 of the low byte, which `SET 7,WA` puts there). They cannot be an L/R gain pair, so the
`reg[21]`/`reg[22]`-as-pan model that `notes/kn5000-tonegen-register-semantics.md` §Q6 item 5 flagged
as unsupported is now **positively excluded**. MEASURED.

`LABEL_02CD71` (asm L29178) is what calls it. It is the general *"recompute this voice's levels"*
service, invoked for expression/volume changes as well as key release; the release is not a distinct
command on the bus. Its other branch (`slot[+0x01]` bit 8 set, asm L29197-29215) instead writes
`+0x840`/`+0x880` and then `slot[+0x2d]` to `+0x000`, and calls `LABEL_022587` (voice-free).

### 1.4 The real key-off — `LABEL_02B4A1` (asm L26770)

```
    (voice + 0x0C0) <- 0x0000        ; asm L26775-26780
    (voice + 0x000) <- 0x7E00        ; asm L26788-26793
```
The same idiom appears in the boot voice-clear loop (asm L13045-13066). It is called from exactly one
place: the voice manager `LABEL_02222A` asm L13327, i.e. **only when the chip reports the voice
SILENT**. See GAP 3 — this is why the current HLE comment at cpp:229-232 is wrong.

### 1.5 The extension writers — six registers no prior map had

`ToneGen_WriteExtParams_15` (asm L30759), `_56` (L30535), `_56b` (L30676) and their variants
`LABEL_02DA96/02DAB8/02DB16/02DCD0/02DCF2/02DD50/02DE69/02DE91/02DEB0/02DF68/02DF8B` ship a second
family of registers from block fields `blk+0x38..+0x42`, using the same
"latch with bit 15 SET → data → latch with bit 15 CLEAR" pattern as `+0x080`:

| latch | data | block fields | source (MEASURED) |
|---|---|---|---|
| `+0x540` (asm L30770/30802) | `+0x1C0` (L30787) | `blk+0x3A` / `blk+0x38` | `LABEL_024F41`, `LABEL_025229` |
| `+0x580` (L30546/30578) | `+0x600` (L30563) | `blk+0x3C` / `blk+0x40` | `part_struct[+0x5d]` asm L18100 / `part_struct[+0x5b]` asm L18097 |
| `+0x5C0` (L30687/30719) | `+0x640` (L30704) | `blk+0x3E` / `blk+0x42` | `part_struct[+0x59]` asm L18176 |

`LABEL_02DD50` (L30887) and `LABEL_02DF8B` (L31082) additionally write the literal `0x8100` to
`+0x540` / `+0x580`. All of it is gated on `desc[+0x27][+0x1a] != 0` (`LABEL_024BE3` asm L17884-17885).

*(This closes `notes/kn5000-variant-model.md` §9.3's open item — `+0x5B` does have a traced consumer;
it is `part_struct[+0x5b] → blk+0x40 → chip +0x600`.)*

**MEASURED LIVE: never written. 0 occurrences in 5734 writes across 285 note-ons** (rhythm section,
three manual parts, 12 different keys). See GAP 10.

### 1.6 The complete register table

`reg_idx = group_map[group]*4 + bank` (cpp:182). "HLE" column: **READ** = the value is consumed;
**event** = the *write* is used as a trigger but the value is not; **stored** = latched at cpp:195 and
never looked at again.

| offset | g.b | reg_idx | firmware writer(s) | computed by | meaning | HLE |
|---|---|---|---|---|---|---|
| `+0x000` | 0.0 | 0 | WVP L29757 (`8100`); `02D68F` L30257 / `02D73F` L30322 / `02CD71` L29210,29243 / `026E5B` L21486 (`slot[+0x2d]`); `02B4A1` L26793 (`7E00`); boot L13066 | `slot[+0x2d]` ← `LABEL_025589` L18856 **or** `LABEL_0255F3` L18909, then routing `LABEL_02552A` L18813 | `[15]` gate · `[14:12]`,`[11:9]` output routing · `[8]` magnitude-present · `[7:0]` linear magnitude | gate **READ**; magnitude **MISREAD** (GAP 1) |
| `+0x040` | 0.1 | 1 | WVP L29573 | `LABEL_023849` L15805 | wave select `{bank,page,chunk}` | **READ** cpp:1255, cpp:367 |
| `+0x080` | 0.2 | 2 | WVP L29588 + L29901; `LABEL_027F96` L23013; `02D68F` L30238 | `LABEL_0232C7` L15195 / `LABEL_02331C` L15230 | bit15 = HOLD/COMMIT strobe; `[11:0]` log→linear amplitude (table `0x010764`) + key-dependent nibble | **event** cpp:255; value stored |
| `+0x0C0` | 0.3 | 3 | WVP L29604; `02B4A1` L26780 (`0000`); boot L13053 | `LABEL_0253FE` L18655 | `[15:8]` per-patch level/brightness scalar; `[7:0]` `part[+0x12]` | stored (GAP 5) |
| `+0x100` | 1.0 | 4 | WVP L29619 | `LABEL_024300` L16962 → `024102`/`024444` | LFO word A | stored (GAP 7) |
| `+0x140` | 1.1 | 5 | WVP L29634 | ditto | LFO word B | stored (GAP 7) |
| `+0x180` | 1.2 | 6 | WVP L29649; `LABEL_02D670` L30174 (per-tick, from `026EC3` L21513) | `LABEL_024A49` L17698 / `LABEL_025219` L18463; low 7 bits ← `desc[+0x27][+0x24]` (L21561-21578) | 7-bit **centred** per-voice parameter, default `0x40` | stored (GAP 6) |
| `+0x1C0` | 1.3 | 7 | `ExtParams_15` L30787; `02DCD0` L30824; `02DE69` L30940 | `LABEL_024F41`/`025229`/`026D35` | extension domain 1 | stored; **never written** |
| `+0x400` | 4.0 | 8 | WVP L29664; `LABEL_027F74` L22993; `02D0BA` L29543 | `LABEL_023A05` L15996 → `023A4A` L16025 | absolute log pitch, `0x100`/semitone | **READ** cpp:576,636,672,766 |
| `+0x440` | 4.1 | 9 | WVP L29679 | `LABEL_024BE3` L17869 | — (`0x0000` in **285/285** note-ons) | stored |
| `+0x480` | 4.2 | 10 | WVP L29694 | `LABEL_024BE3` L17870 / `024E66` L18141 | — (`0x0000` in **285/285**) | stored |
| `+0x4C0` | 4.3 | 11 | WVP L29709 | `LABEL_024A49` L17701 (`0`) / `LABEL_025229` L18475 (`0x4400`) | chain-selected constant | stored |
| `+0x500` | 5.0 | 12 | WVP L29724 | `LABEL_02492D` L17645 / `0249BF` L17665 (`0`) | `2C72` mainline / `0000` rhythm | stored |
| `+0x540` | 5.1 | 13 | `ExtParams_15` L30770/30802; `02DCF2`; `02DD50` L30887 (`8100`); `02DEB0`; `02DF68` | `LABEL_024F41` | ext domain-1 latch/gate | **never written** |
| `+0x580` | 5.2 | 14 | `ExtParams_56` L30546/30578; `02DAB8`; `02DB16` L30663 (`8100`); `02DF12`; `02DF8B` | `part_struct[+0x5d]` L18100 | ext domain-2 latch/gate | **never written** |
| `+0x5C0` | 5.3 | 15 | `ExtParams_56b` L30687/30719 | `part_struct[+0x59]` L18176 | ext domain-3 latch | **never written** |
| `+0x600` | 6.0 | 16 | `ExtParams_56` L30563; `02DA96` L30600; `02DE91` L30956 | `part_struct[+0x5b]` L18097 | ext domain-2 data | **never written** |
| `+0x640` | 6.1 | 17 | `ExtParams_56b` L30704 | `LABEL_024BE3` L18158/18171 | ext domain-3 data | **never written** |
| `+0x800` | 8.0 | 20 | WVP L29739; `02D436` L29988; `02D50E` L30057; `027FD6` L23097; `02D68F` L30195; boot L13023 (`A280`), L31126 (`FF80`) | note-on: `LABEL_025636` L19085; update: `LABEL_026769` L20835 | **EG-A segment 0** = `(target<<8) \| rate`, bit7 of rate set by the software update | high byte **READ** as a *constant* gain (GAP 2, GAP 9) |
| `+0x840` | 8.1 | 21 | WVP L29766; `02D436` L29943; `02D50E` L30042; `027FD6` L23052; `02D620` L30137; `02D68F` L30222; boot L13009 (`A200`), L31113 (`FF00`) | `LABEL_02591D` L19339; update `LABEL_026769` L20838 | **EG-A segment 1** | stored (GAP 2) |
| `+0x880` | 8.2 | 22 | WVP L29781; `02D5D0` L30113; `02D620` L30152 | `LABEL_02591D` L19318 | **EG-A segment 2** | stored (GAP 2) |
| `+0x8C0` | 8.3 | 23 | WVP L29796 | `LABEL_02492D` L17657 / `0249BF` L17664 (`0`) | **EG-A segment 3** (terminal, target `0x00`) | stored (GAP 2) |
| `+0x900` | 9.0 | 24 | WVP L29811; `02D436` L30003; `027FD6` L23112 | `LABEL_023AD0` L16248; update `LABEL_026975` L21085 | **EG-B segment 0** | **event** cpp:246 (GAP 4); value stored |
| `+0x940` | 9.1 | 25 | WVP L29826; `02D436` L29958; `027FD6` L23067 | `LABEL_023AD0` L16301; update L21086 | EG-B segment 1 | stored |
| `+0x980` | 9.2 | 26 | WVP L29841 | `LABEL_023AD0` L16307 | EG-B segment 2 | stored |
| `+0x9C0` | 9.3 | 27 | WVP L29856; `02D436` L30018; `027FD6` L23127 | `LABEL_024664`/`0247BF` L17478; update `LABEL_026AAA` L21211 | **EG-C segment 0** | stored |
| `+0xA00` | 10.0 | 28 | WVP L29871; `02D436` L29973; `027FD6` L23082 | `LABEL_024868` L17556; update L21212 | EG-C segment 1 | stored |
| `+0xA40` | 10.1 | 29 | WVP L29886 | `LABEL_024868` L17561 | EG-C segment 2 | stored |
| `+0x680` `+0x6C0` `+0xA80` `+0xAC0` | 6.2/6.3/10.2/10.3 | 18,19,30,31 | **no writer anywhere in the ROM** | — | — | n/a |

### 1.7 The three envelope generators — the central structural finding

Each of groups 8 / 9 / 10 carries a `(target level << 8) | rate` word per segment, and the software
update (§1.3) overwrites **segments 0 and 1 of each with the same value** — the classic way to force a
hardware EG to a commanded level ("ramp there and hold").

**MEASURED LIVE, note-on values:**

```
                 seg0        seg1        seg2        seg3
Piano C4  EG-A   E5 / 7F     48 / 4C     40 / 00     00 / B0     <- monotone decay to SILENCE
          EG-B   AE / 00     AE / 00     AE / 00       —
          EG-C   FF / 00     40 / E8     30 / B0       —
Drum v0   EG-A   E7 / 7F     74 / 04     74 / 00     00 / 00
Bass v1   EG-A   D5 / 7F     8A / 04     8A / 00     00 / 00
```

Three independent confirmations that these really are `(level, rate)` segment descriptors:

1. **`seg1.level == seg2.level` in 197 / 197 rhythm note-ons** (census: `+0x840` top values
   `8A04:103 7404:56 6404:38`, `+0x880` top values `8A00:103 7400:56 6400:38` — identical high bytes,
   identical counts), with rate `0x04` then `0x00`. That is "decay to X, then hold" — an ADS.
2. **The terminal segment's target is `0x00` for every voice observed** (`+0x8C0` = `00B0` piano,
   `0000` rhythm). Nothing else in the register stream can end a voice.
3. **The targets are monotone non-increasing under the *current* `higher = louder` polarity**
   (`E5 → 48 → 40 → 00`; `E7 → 74 → 74 → 00`) and monotone *in­creasing* under the opposite one.
   This is an **independent cross-check that the polarity fix of `7072b09` is correct**, derived from
   a register family nobody had looked at when that fix was made.

INFERRED (cannot be settled from the firmware): the exact rate→time law, and whether rate `0x00`
means "hold" or "terminate". The rate byte comes from table `0x011963` at note-on
(`LABEL_025636` asm L19078) and `0x0119C8` in the EG builders; the tables are in the code ROM and the
chip that consumes them is undumped.

What EG-B and EG-C physically drive (filter, pitch, a second amplitude domain, effect sends) is
**not decidable from the firmware** — their builders (`LABEL_023AD0`, `LABEL_024664`) compute
structurally similar level+velocity accumulators. Do not guess. What *is* decidable: EG-A is the
amplitude EG (the HLE already gets audible velocity response from its segment 0).

---

## 2. WHAT THE HLE DOES

| what | where |
|---|---|
| latches all 32 registers | cpp:195 |
| `+0x000`: `0x7E00` → key off · `0x81xx` → key on · else bit15 → `env_level = min(data & 0x1FF, 0xFF)` | cpp:205-226 |
| `+0x900` write >1 ms after the gate while keyed on → `process_key_off` | cpp:246-251 |
| `+0x080` with bit15 set → `resolve_waveform` | cpp:255-256 |
| `+0x040` or `+0x400` → `update_pitch` | cpp:261-262 |
| `+0x080` or any group-8 → `update_voice_params` | cpp:266-267 |
| `update_voice_params` = `gain = 2^((regs[20]>>8 − 231)/10)`, **pan forced centre** | cpp:462-521 (regs[20] at :495, pan at :515-520) |
| `env_level` applied | cpp:1520 |
| 50 ms linear release fade + deactivation | cpp:1369, cpp:1524-1543 |
| `status_r` = the key-on bitmap | cpp:290-316 |

**Registers read by value: `regs[1]`, `regs[8]`, `regs[20]` — three of 28.** `regs[2]` and `regs[24]`
are used only as write *events*. `m_global_regs` (cpp:166) is stored and never read.

*(Stale comment: cpp:1341 says the wave number is in "regs[9]/regs[10]". Those are `+0x440`/`+0x480`,
MEASURED `0x0000` in 285/285 note-ons; the wave number is `regs[1]`.)*

---

## 3. THINGS AUDITED AND FOUND **CORRECT** — do not change them

1. **The address decode** (`ch = addr & 0x3F`, `bank = (addr>>6)&3`, `group = addr>>8`, cpp:173-175)
   and the `group_map` fold (cpp:182). MEASURED over 5734 live writes: every offset the firmware
   emits decodes, none is dropped, the "unknown group" branch is unreachable. The 32-entry file is
   large enough for the 28 registers that exist.
2. **The key-on discriminator `(data & 0xFF00) == 0x8100`** (cpp:212) is exactly the firmware's gate
   (asm L29757, L30213, L30294). MEASURED 285/285 note-ons.
3. **The key-off decode `data == 0x7E00`** (cpp:207) matches `LABEL_02B4A1` asm L26793 and the boot
   clear asm L13066. MEASURED.
4. **Not re-triggering on the `0xF0xx` rewrites** (the `else if` ordering at cpp:218) is right — the
   firmware writes `slot[+0x2d]` to the same register microseconds after the gate (LIVE, PC `02D42F`).
5. **`+0x040` is the sole wave selector.** No other register carries wave identity; `+0x440`/`+0x480`
   are `0x0000` in 285/285 note-ons, so they cannot be "rotating DMA slot counters" carrying anything.
6. **`regs[20]`'s high byte is a LEVEL, higher = louder** — independently re-derived here from the
   four-segment structure (§1.7 point 3). The `7072b09` polarity fix is confirmed, not just plausible.
7. **The global-register decode** (cpp:154-169) matches the live stream (`0x0200`-`0x0205` and
   `0x0C00`-`0x0C03` observed at boot: `0060 0993 0001 0004 0004 000C` / `0000 ×4`).

---

## 4. PREDICT-THEN-CHECK, misses included

| prediction (made from the disassembly, before the capture) | result |
|---|---|
| `ToneGen_WriteVoiceParams` emits 23 writes in the tabled order, gate 13th | **HIT 23/23**, twice |
| `+0x080` first write has bit 15 set, last has it clear | **HIT** (`8E52` → `0E52`) |
| `LABEL_02D436` emits 6 writes in the order `840,940,A00,800,900,9C0` | **HIT 6/6** |
| the update writes the *same* word to `+0x800` and `+0x840`, differing by bit 7 | **HIT** (`8B80`/`8B00`) |
| the six extension registers are conditional (`desc[+0x27][+0x1a]`) | **HIT** — 0 of 5734 writes |
| the `+0x900` release heuristic would misfire on every EG segment tick | **MISS** — for the piano the firmware emits **no** per-segment updates at all during a 2 s hold, so it does not misfire here. Reported as a latent hazard (GAP 4), not an observed defect |
| the firmware would issue its own `0x7E00` at key-up regardless of the HLE | **MISS, and the falsification is decisive** — with the heuristic disabled (one-line experiment build) the firmware writes the release EG burst and then **nothing at all** for the remaining 2 s. The `0x7E00` seen in the baseline run at `t=22.312042` is a *consequence* of our heuristic having already flipped `status_r` |

---

## 5. THE DELTA — numbered gaps, ranked by audible impact

### GAP 1 — `+0x000` magnitude `0` is read as silence; **the whole rhythm section is muted**. MEASURED.

*What is wrong.* cpp:224 does `env_level = min(data & 0x1FF, 0xFF)` and cpp:1520 multiplies by it.
The firmware has **two** builders for that word:

* `LABEL_025589` (asm L18856-18898): `BC = 0x00FF − 4*(pb[0] & 0x3F)` → **`0x03..0xFF`, never 0**,
  plus bit 8 iff `pb[0] != 0` (asm L18867-18869 — the arithmetic cannot carry into bit 8, so bit 8 is
  a flag, not part of the number).
* `LABEL_0255F3` (asm L18909-18942): writes a **bare `0xF000` / `0xFE00`** — no magnitude field at all.

So low-9-bits `== 0` means *"this voice carries no software magnitude"* (its contour is the chip's
EG), never *"amplitude zero"*. `LABEL_0255F3` is the one used by the `LABEL_02C0B6` builder chain
(asm L27949) — the rhythm / auto-accompaniment / GM path.

*Audible consequence.* MEASURED, rhythm census: **197 of 215 note-ons carry `+0x000 = 0xF000`**
(the 18 that do not are exactly my 9 manual key presses × 2 piano partials). Rendered audio,
16-Beat-1 running with no keys held:

```
                        rhythm only (19-25 s)      rhythm + manual piano (26.5-29.5 s)
current build           rms    2.6  peak    434    rms  5294.7  peak 16506
one-line fix applied    rms 28806.8 peak  32768    rms 29304.1  peak 32768
```

**+81 dB.** The drums, bass and accompaniment of a KN5000 — the instrument's headline feature — are
silent today.

A second, smaller error rides along: `min(mag, 0xFF)` collapses the whole `0x103..0x1FB` range
(bit 8 set) to `0xFF`, so the magnitude never varies even when present. The magnitude is the **low
byte**; bit 8 is a flag.

*Firmware-derived fix* (cpp:224):
```cpp
const int mag = data & 0x1FF;                 // bit8 = "magnitude present" flag
m_voice[ch].env_level = mag ? (mag & 0xFF) : 0xFF;
```
*Confidence:* MEASURED (the two builders, the 197/215 census, the ±81 dB A/B). The `mag & 0xFF`
refinement is INFERRED (no live sample with bit 8 set was observed — `pb[0]` was 0 in every voice
captured, so only `0x0FF` and `0x000` appear).

> **This must NOT be shipped alone.** MEASURED: with only this change the rhythm renders at a
> permanently saturated level (RMS 28807 of 32768, flat for the whole run — see the time series in
> §7.3) because nothing ever decays or ends the voices. It is the *first half* of GAP 2 + GAP 3.

### GAP 2 — the group-8/9/10 registers are four-segment ENVELOPE GENERATORS; the HLE runs none. MEASURED.

*What is wrong.* `update_voice_params` (cpp:462-521) reads `regs[20] >> 8` as a **constant** gain and
ignores `regs[21..29]` and every rate byte. There is no segment stepping anywhere in the device.

*Audible consequence.* MEASURED, rhythm timeline capture: for a rhythm voice the firmware writes the
note-on burst and **nothing else, ever** — 70 note-ons, **0** key-offs, **0** per-segment updates,
concurrent gated voices climbing 1 → 64 and stuck at 64 for the rest of the run. The entire amplitude
contour of a drum hit or a bass note is delegated to the chip EG. With no EG:
* rhythm and accompaniment voices never decay and never end (masked today by GAP 1's mute);
* a held piano note has no decay — it holds at its *attack peak* forever (see GAP 9);
* the release is a single instantaneous jump to the release target (`0xE5 → 0x8B` = −58 dB in one
  sample) followed by a synthetic 50 ms linear fade (cpp:1369, cpp:1526), instead of a ramp at the
  programmed rate through the remaining segments to `0x00`;
* Bright Piano and Mellow Piano — which differ **only** in `+0x080 +0x0C0 +0x100 +0x140 +0x8C0
  +0xA00 +0xA40` — render bit-identically. `+0x8C0` alone is `00B0` for Piano and `0000` for both
  others: a different terminal decay rate that is simply thrown away.

*Firmware-derived fix.* Give `voice_t` a 4-entry segment array and a current gain. On a write to
`+0x800/+0x840/+0x880/+0x8C0` store `{target = data>>8, rate = data & 0x7F}` into segment
`bank`; on the gate, start at segment 0; per output sample move the gain toward the current
segment's target at its rate and advance when reached; a segment with rate 0 holds. When the gain
reaches the floor, deactivate — which makes `status_r` report the voice silent, which is exactly what
lets the firmware reclaim it (GAP 3). Segments 0/1 being rewritten mid-note is the firmware's
"ramp to this level" command and needs no special case.

*Confidence:* MEASURED for the register layout, the write order, the "same word to seg0 and seg1"
rule, the `seg1.level == seg2.level` 197/197 census, the terminal `0x00` target, and the absence of
any other contour source. INFERRED for the rate→time law and for the rate-0 semantics.

### GAP 3 — `status_r` reports every gated voice active forever, so the firmware can never reclaim one. MEASURED.

*What is wrong.* cpp:290-316 returns the `key_on` bitmap. The firmware's voice manager
(`LABEL_02219F`/`LABEL_02222A` asm L13273-13330) computes *"voices I commanded on that the chip says
are silent"* and frees each via `LABEL_02B4A1` (asm L26770) — the real
`+0x0C0 ← 0x0000; +0x000 ← 0x7E00` sequence. Our answer never says "silent", so that never fires.

*Evidence.* MEASURED: 70 note-ons, **0** key-offs; 64 voices permanently gated. And the decisive
experiment (§4, last row): **with the `+0x900` heuristic disabled the firmware emits the release EG
burst and then nothing at all** — no `0x7E00` in the following 2 s. So the `0x7E00` observed in the
baseline C4 run 4.75 ms after the burst was *caused* by our own heuristic.

*Consequence.* The comment at cpp:229-232 ("The sub-CPU never writes a `0x7E00` key-off when a held
key is released") is **false as an account of the hardware** — the firmware writes it whenever the
chip reports silence. It is only true *because* the HLE prevents the chip from ever reporting silence.

*Fix.* Report a voice as active only while its EG gain is above the silence floor (GAP 2). The
firmware's own voice manager then does the reclaiming exactly as on hardware, and both the
`hold_counter` bookkeeping (cpp:1375) and the heuristic of GAP 4 can be deleted.

*Confidence:* MEASURED.

### GAP 4 — the release heuristic keys on a general "levels changed" update, not on note-off. MEASURED mechanism, latent defect.

*What is wrong.* cpp:246-251 releases the voice on any `+0x900` write more than 1 ms after the gate.
That write comes from `LABEL_02D436`, which `LABEL_02CD71` (asm L29217-29227) calls for **every**
level recomputation — expression pedal, part-volume change, key release alike.

*Status.* PREDICTED to misfire; **MEASURED not to, in this capture** — the piano emits no
per-segment update at all during a 2 s hold, so the only `+0x900` write after the gate really is the
release. Reported as a **miss on my prediction** and a latent hazard: any patch whose second-domain
envelope actually steps, or any live volume change under a held note, would cut the note off.
(`+0x080` *is* rewritten alone under a held note — MEASURED at `t=34.165752`, PC `027FB4` =
`LABEL_027F96` — so the "level changed while held" path is live in normal play.)

*Fix.* With GAP 2 + GAP 3 in place the heuristic is unnecessary: honour the release EG burst as a new
segment target and let the firmware's real `0x7E00` (which will then arrive) end the voice.

### GAP 5 — `+0x0C0`, the per-patch level scalar, is ignored. MEASURED value, INFERRED role.

*Firmware.* `LABEL_0253FE` asm L18655-18733:
`DE = part[+0x0f]; if DE: DE += patch[+0x5C] − 0x40; DE += sext(part[+0x66]); clamp 0..0x7F; DE <<= 8;
DE |= part[+0x12]`. MEASURED live: `7400` (Piano) vs `5A00` (Bright, Mellow) — 26 units apart;
`5A00` for 159 of 215 note-ons, `6200` for 38.

*Why it is a LEVEL, not a filter cutoff.* It is zeroed as the **first** step of the standard
"silence this voice" sequence — `LABEL_02B4A1` writes `+0x0C0 ← 0x0000` immediately before the
`0x7E00` key-off (asm L26775-26793), and the boot voice-clear does the same (asm L13045-13066).
Zeroing a filter cutoff before a key-off would be pointless; zeroing a gain to de-click is exactly
what you would do. INFERRED, but well supported.

*Audible consequence.* Piano sits 26 units above Bright/Mellow in a per-voice gain nobody applies.
Today the only rendered Piano↔Bright difference is the `+0x800` delta (+5.38 dB, prior measurement).

*Fix.* Fold `regs[3] >> 8` into the voice gain on the same log scale as `regs[20]`'s level. Note the
scale constant is not derivable (the chip is undumped) — see GAP 9.

### GAP 6 — `+0x180` is a 7-bit **centred** per-voice parameter (pan is the leading reading) and the HLE hard-centres pan. MEASURED field, INFERRED meaning.

*Firmware.* Default `0x0040` (`LABEL_0272A3` asm L21912 `LDW (0451D8h),0040h`). The low 7 bits are
explicitly *replaced* from a per-partial byte at run time (`LABEL_026F4A` asm L21571-21578:
`DE = slot[+0x2b] & 0xFF80; DE |= desc[+0x27][+0x24]`), and forced to `0x7F` when the part's routing
byte `0x04138E + 0x11F*part == 2` (asm L17690, L18449). It is re-written per tick by the
second-domain stepper `LABEL_026EC3` → `LABEL_02D670` (asm L30169).

*MEASURED live values across 285 note-ons:* `0x0000`, `0x0028`, `0x0040`, `0x007F` — nothing else,
never above `0x7F`. `0x0040` on 94 of 215; **the two Piano partials take `0x0000` and `0x007F`, the
two extremes.**

*Why pan.* A 7-bit field whose *default is the exact centre of its range* is a bipolar control; a
level would default to `0x7F`. `0x40` = centre is MIDI CC10's convention, and a dual-layer acoustic
piano hard-panned L/R is standard practice. INFERRED — not proven; "bipolar modulation depth" is not
excluded.

*Audible consequence.* cpp:515-520 sets `volume_l == volume_r` unconditionally. The entire stereo
image is lost: the piano's two layers collapse to mono-centre, and every part's pan setting is
discarded.

*Fix.* `p = regs[6] & 0x7F` (0 = left, 0x40 = centre, 0x7F = right) driving `volume_l/volume_r`.
Gate it behind an A/B check — this is the one gap in the list whose *meaning* is inferred rather
than measured, and Felipe's ear on the real instrument is the arbiter.

### GAP 7 — `+0x100 / +0x140`, the LFO, ignored. MEASURED variation, INFERRED role.

`LABEL_024300` (asm L16962) dispatches on `pb[+0x0F] & 7` through a 6-entry table at `0x0000F6B3`;
mode 0 writes the "no LFO" constants `0x017F`/`0x7F7F` (`LABEL_0272A3` asm L21903-21904).
MEASURED live: 15 distinct `+0x100` values over 215 note-ons; Piano / Bright / Mellow are
`244E / 2461 / 2445` and Piano's `+0x140` differs from the other two. No vibrato, tremolo or rotary
modulation exists anywhere in the emulation, so every modulated variant is indistinguishable from its
static twin. Fix: decode the two words' packing (the five active branches `LABEL_02413E / 0241A0 /
024205 / 024250 / 0242A1` are named but their bit layout is not decoded — an open RE item) and
modulate pitch/amplitude.

### GAP 8 — `+0x080`'s payload ignored, and the waveform is resolved on the wrong edge. MEASURED.

The register is a HOLD/COMMIT strobe *plus* a 12-bit log→linear amplitude (`LABEL_0232C7` asm L15195,
table `0x010764`). MEASURED live: `8E52 → 0E52` (piano), `ACDC → 2CDC` (drum) — 64 distinct values
over 215 note-ons, and it is re-written **alone** under a held note when a part volume changes
(`LABEL_027F96` asm L23008, observed at `t=34.165752`). The HLE reads none of it, so live volume
changes under a held note are inaudible.

Separately: cpp:255-256 resolves the waveform on the bit15-SET strobe, which MEASURED arrives
*before* `+0x0C0 … +0xA40` and before the gate. `process_key_on` re-resolves anyway (cpp:1344), so the
early call is redundant; it is also the only place that could latch a half-programmed voice.
Recommend dropping it and keeping the key-on resolve.

### GAP 9 — the `+0x800` gain model reads the attack peak, with hand-calibrated constants. MEASURED.

`regs[20] >> 8` is **EG-A segment 0's target** — the peak the attack reaches, not the level the note
sits at. For the piano the steady level is segment 2's `0x40`, which is `0xA5` units *below* segment
0's `0xE5`; at the device's `K = 10` that is a 16-fold error on every held note. The rate byte is
discarded entirely. `K = 10` / `REF = 231` (cpp:490-493) are calibration constants, honestly labelled
as such in the source — they stay unavoidable while IC303 is undumped, but they should be applied to
the *EG output*, not to segment 0's target.

### GAP 10 — six extension registers are decoded but dead. MEASURED absent — no action needed.

`+0x1C0 +0x540 +0x580 +0x5C0 +0x600 +0x640` (reg_idx 7, 13, 14, 15, 16, 17): full writer set in §1.5,
gated on `desc[+0x27][+0x1a] != 0` (asm L17884). **0 writes in 5734, across 285 note-ons covering the
rhythm section, three manual parts and 12 keys.** They are already stored correctly by the existing
`group_map`, so nothing is lost. Recorded so the next pass does not re-discover them, and so that if
a future patch/part configuration *does* trigger them the register file is ready.
Registers 18/19/30/31 (`+0x680 +0x6C0 +0xA80 +0xAC0`) have no writer anywhere in the ROM.

---

## 6. Recommended order of work

1. **GAP 2 + GAP 1 + GAP 3 together** — the EG, the magnitude fix and the honest `status_r` are one
   change. Landing any of them alone regresses the sound (MEASURED for GAP 1).
2. **GAP 4** — delete the heuristic once 2+3 are in.
3. **GAP 5** (`+0x0C0` into the gain) and **GAP 6** (`+0x180` as pan) — both small, both need an
   A/B against Felipe's ear because their *scale* / *meaning* is inferred.
4. **GAP 7** (LFO) — needs the bit packing of `LABEL_024300`'s five branches decoded first.
5. **GAP 8** — cheap cleanup.

---

## 7. Reproduction

### 7.1 The capture harness (no rebuild needed)

`scratchpad/tgcap.lua` — a MAME Lua write-tap on the sub-CPU program space, `0x100000` = address
latch, `0x100002` = data, recording `t, addr, data, sub-CPU PC`:

```lua
local sp = manager.machine.devices[":subcpu"].spaces["program"]
_G.TAPKEEP = sp:install_write_tap(0x100000, 0x100003, "tgcap", function(off, data, mask) ... end)
```

**Trap that cost an hour: the tap object must be kept alive.** `sp:install_write_tap(...)` returns a
sol userdata; if its value is discarded the tap is garbage-collected and *silently stops firing* — the
first three attempts here reported "0 tone-generator writes in 60 s" on a fully booted machine.
Assign it to a global.

```bash
cd ~/compartilhado/kn7000-emulator
TGCAP_OUT=$S/tgcap_c4.txt TGCAP_T0=20 timeout 500 ./kn7000 kn5000 -rompath roms \
  -window -nomaximize -skip_gameinfo -nvram_directory $S/nvcap \
  -autoboot_script $S/tgcap.lua -autoboot_delay 0 -video opengl -sound none
```

### 7.2 The C4 note (68 writes) — the whole of it

```
# KEYDOWN 20.300814
20.302474 0840 FF00 02C9A1     <- pre-clear (level 0xFF, rate 0)
20.302477 0800 FF80 02C9C2
20.302869 0040 7007 02D128     <- ToneGen_WriteVoiceParams begins
   ... 23 writes, gate 0x8100 -> +0x000 at 20.302905 (13th) ...
20.302936 0080 0E52 02D412     <- commit (bit15 cleared)
20.303412 0000 F0FF 02D42F     <- slot[+0x2d]
   (voice 1 identically: +0x040 = 7017, +0x180 = 007F, +0x000 = F0FF)
   *** 2.0 s of hold: ZERO further writes ***
# KEYUP 22.305986
22.307280 0840 8B00 02D45B     <- LABEL_02D436, 6 writes, both voices
22.307283 0940 AE00 02D47D
22.307286 0A00 4FB0 02D49F
22.307289 0800 8B80 02D4C1
22.307292 0900 AE00 02D4E3     <- the write the HLE's heuristic triggers on
22.307296 09C0 4FB0 02D505
22.312042 00C0 0000 02B4BF     <- LABEL_02B4A1 -- and ONLY because the heuristic
22.312045 0000 7E00 02B4DB        already flipped status_r 4.75 ms earlier
```

### 7.3 The A/B that measures GAP 1

One-line change at cpp:224 (`mag ? min(mag,0xFF) : 0xFF`), `./build.sh`, then the same script with
`-wavwrite`. The wav is 3-channel; audio is on ch1/ch2 (ch0 is silent).

```
                        rhythm only            rhythm + manual piano
current build           rms     2.6            rms  5294.7
with the fix            rms 28806.8            rms 29304.1
```

Time series of the fixed run, 0.25 s windows: `135` before START, then `15214 20160 25692 …` and a
flat `28000-30500` for the rest — i.e. permanently saturated, which is what makes GAP 2/GAP 3
prerequisites rather than follow-ups.

The diagnostic edit was **reverted** and the build tree rebuilt clean
(`src/mame/matsushita/kn5000_tonegen.cpp` untouched at the end of this pass; the published binary in
`kn7000-emulator/` was never overwritten — every run above used
`../kn7000_mame_build/kn7000` directly).

### 7.4 The experiment that measures GAP 3

Wrap cpp:246's condition in `if (false && …)`, rebuild, re-run the C4 script: the release EG burst
still arrives at `22.3073`, and **nothing** follows it for the remaining 2 s (`n = 64` writes vs 68
in the baseline, the four missing ones being exactly the two `+0x0C0 ← 0x0000` / `+0x000 ← 0x7E00`
pairs). Also reverted.

### 7.5 Static tooling

```bash
# every IC303 register address the firmware writes, with the value's source
#   scan.py  : "LD (100000h),WA" preceded by "ADD WA,<off>", data traced forward
# every writer of the 0x0451CC staging block, attributed to its builder routine
#   attr2.py : writes to 0x0451CC..0x04520F, owner = nearest preceding chain member
```
(both in the session scratchpad; each is ~30 lines of stdlib Python over the .asm)
