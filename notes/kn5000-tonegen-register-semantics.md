# KN5000 tone-gen (IC303 / TC183C230002) register SEMANTICS — where the software envelope lands

Author: autonomous RE pass, 2026-07-23. Requested by Felipe Sanches.
**Analysis only** (no `src/` edits, no build). Builds on `notes/kn5000-envelope-engine.md`.

Purpose: pin down, from the SUB-CPU disassembly, EXACTLY which IC303 register(s) the
firmware's per-note software envelope writes and what each means, so the
`kn5000_tonegen` HLE render can map the ROM's envelope output into per-voice gain
without guessing.

Evidence labels: **MEASURED** (read directly from ASM), **PROVEN-BY-CONSTRUCTION**
(follows directly from a traced path), **INFERRED** (deduction), **SPECULATIVE**.

Sources (all line numbers are 1-based in these files):
* SUB-CPU disasm: `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
* HLE model: `kn7000_mame/src/mame/matsushita/kn5000_tonegen.cpp` (+ `.h`)
* Prior decode: `kn7000_mame/notes/kn5000-envelope-engine.md`

The IC303 write primitive (`ToneGen_WriteSingleReg`, asm L29919-29926):
```
ToneGen_WriteSingleReg:      ; WA = 16-bit register ADDRESS, BC = 16-bit DATA
    LD IZ, BC
    RES 7,(P6) ; LD (100000h),WA   ; address phase  (P6.7 low = CS)
    SET 7,(P6) ; LD (100002h),IZ   ; data phase
```
MEASURED. Every IC303 write in the ROM follows this address-then-data pattern.

---

## Q1 — the 16-bit register-address encoding — MEASURED, emulator is CORRECT

The address is built as `voice_number + constant_offset`, and every constant offset is
a multiple of 0x40 whose value decomposes cleanly as `group*0x100 + bank*0x40`. Proof
(each is `LD WA,<voice>; ADD WA,<offset>; LD (100000h),WA`):

| asm line | ADD offset | group | bank | meaning |
|---|---|---|---|---|
| L30173 (`02D670`) | `0180h` | 1 | 2 | expression |
| L23052 / L30098 / L30137 | `0840h` | 8 | 1 | bus-0 R gain |
| L30113 / L30152 | `0880h` | 8 | 2 | (2nd-domain level) |
| L23097 / L29988 | `0800h` | 8 | 0 | bus-0 L gain |
| L23067 / L30003 | `0900h` | 9 | 0 | bus-1 L gain |
| L23082 | `0a00h` | 10 | 0 | bus-2 gain |
| L22993 (`027F74`) | `0400h` | 4 | 0 | note/octave |
| L23012 (`027F96`) | `0080h` | 0 | 2 | velocity volume |

and the **voice number occupies the low bits** (added un-shifted), so:

```
addr = (group << 8) | (bank << 6) | channel      ; channel = voice 0..63
```

**This EXACTLY matches the HLE decode** (`kn5000_tonegen.cpp` L157-159):
`ch = addr & 0x3F` (`REG_CHANNEL_MASK`), `bank = (addr>>6)&3`
(`REG_BANK_SHIFT=6`,`REG_BANK_MASK=3`), `group = addr>>8` (`REG_GROUP_SHIFT=8`); bank
stride 0x40, group stride 0x100. **Confirmed. The emulator's address math is right.**
(PROVEN-BY-CONSTRUCTION from the ADD offsets above.) The examples in the task hold:
`reg[2]` = group0.bank2 = +0x080, `reg[20]` = group8.bank0 = +0x800.

The HLE `group_map[]` (L166) folds the 8 populated groups {0,1,4,5,6,8,9,10} into
`reg_idx = group_map[group]*4 + bank`. That folding is internally consistent with the
firmware's group usage (only those groups are ever addressed).

---

## Q2 — the amplitude-envelope write — MEASURED. It writes GROUP 0 / BANK 0 (reg_idx 0), which the render reads for GATE ONLY and whose level bits it DISCARDS

The per-tick amplitude stepper `LABEL_026E5B` (asm L21467-21491):
```
    IZ = slot[+0x2f]                 ; amp envelope counter (bit15=active)
    if bit15(IZ):
        IZ -= 0x0100                 ; advance coarse
        if (IZ & 0x7F00) == 0:       ; coarse boundary reached
            A  = slot[+0x00]         ; L21482  <-- the VOICE NUMBER (0..63)
            EXTZ WA                  ; WA = voice number = register address 0x00+voice
            BC = slot[+0x2d]         ; L21485  <-- the current LEVEL word
            CALL ToneGen_WriteSingleReg   ; L21486  => writes (group0,bank0,voice)
```
`WA = slot[+0]` is the bare voice number, used unmodified as the register address, so
the target is **group 0, bank 0 (offset +0x000) = the voice-control register =
`reg_idx 0`**. MEASURED / PROVEN-BY-CONSTRUCTION.

The value `slot[+0x2d]` is the packed level word. Its high bits are a gate/routing
command, its low bits are the amplitude magnitude:
* built at L18884-18898 (`025589`/`0255F3`): `OR 0fe00h` (release modes 5/6/0) or
  `OR 0f000h` (normal) over a magnitude `BC`.
* magnitude seed `BC = 0x00FF - 4*(x & 0x3F)` (L18862-18865): larger index → smaller
  value → a **linear 0..0xFF gain in the low byte** (0xFF = loud).
* `02552A` (L18826, L18845) then ORs routing bits (`bit9`, `bits12-14`) chosen from a
  per-voice routing table 0x04138D. So the word is:
  `[15]=active gate | [14:12],[9]=routing/command | [8:0]=amplitude magnitude`.

So `reg_idx 0` is a **combined gate + envelope-magnitude + routing** register. Typical
values: `0x8100`=key-on trigger, `0x7E00`=idle/off, `0xF000|mag`=active-normal,
`0xFE00|mag`=active-release.

**What the HLE render does with reg_idx 0 (`kn5000_tonegen.cpp` L183-195):**
```
if (group == 0 && bank == 0) {
    if (data == 0x7E00) process_key_off(ch);
    else if (data & 0x8000) process_key_on(ch);   // <-- fires on EVERY 0xF000|mag write
}
```
It uses the word for the on/off GATE only. The magnitude bits `[8:0]` are **never read
into amplitude** — the per-tick software envelope is invisible to the render. This is
the register the task suspected: a THIRD register the render ignores (distinct from
reg[2]/reg[20]).

**Worse than ignored — actively harmful (MEASURED bug):** `0xF000|mag` and
`0xFE00|mag` both have bit15 set, so the `else if (data & 0x8000)` branch calls
`process_key_on(ch)` on *every coarse envelope tick*, and `process_key_on` resets
`v.wave_offset = 0` (L423). The envelope re-writes therefore keep restarting the
waveform. The render should key-on only on the genuine trigger (`data == 0x8100`, or a
rising edge from idle), not on every active-level rewrite.

---

## Q3 — the expression write — MEASURED. GROUP 1 / BANK 2 (+0x180) = reg_idx 6

Second-domain stepper `LABEL_026EC3` (asm L21513-21587) calls `LABEL_02D670`:
```
LABEL_02D670 (asm L30169-30177):
    LD IZ, BC                ; data
    ADD WA, 0180h            ; WA = voice + 0x180  = group1.bank2
    LD (100000h), WA ; LD (100002h), IZ
```
The value is `slot[+0x2b]` (L21541 `LD BC,(XBC+02bh)`), a second envelope level derived
in parallel (its own counter `slot[+0x31]/[+0x35]`, L21518/21523). `+0x180 = group1,
bank2`; in the HLE `group_map[1]=1`, so it lands in **`reg_idx 6`** — the model STORES
it (L179) but nothing reads it. MEASURED.

Combination math: this is a SEPARATE per-voice level register, not an add/multiply the
CPU folds into reg_idx 0. The firmware writes two independent envelope levels to two
independent chip registers (reg_idx 0 and reg_idx 6); how the chip combines them is
internal to IC303 (black box). INFERRED: +0x180 is a per-voice level/VCA in a second
domain (the note-on cluster below shows the L/R bus GAINS are the group8/9/10
registers, so +0x180 is more plausibly a secondary amp/expression scalar than pan).

---

## Q4 — level scale / format — MEASURED (structure) + INFERRED (curve)

Two distinct numeric encodings carry the envelope, one per register family:

1. **reg_idx 0 (group0.bank0) magnitude** — `[8:0]` linear, `0x00..0xFF`, `0xFF`=loud
   (`0xFF - 4*index`, L18865). Gate/routing in the high bits. MEASURED.
2. **group8/9/10 L/R bus gains** — the LEVEL is `loglevel << 8`, i.e. the byte sits in
   the HIGH byte. Built in `LABEL_026769` (asm L20831-20838):
   ```
       WA = IZ ; SLA 8,WA ; SET 7,WA ; LD (0451F8h),WA   ; = (loglevel<<8) | 0x0080
       WA = IZ ; SLA 8,WA ;           LD (0451FAh),WA     ; = (loglevel<<8)
   ```
   where `loglevel` is a byte fetched from table **0x0118FE** (L20776,
   `LD A,(0118FE + index)`) indexed by `(patch_level + keyscale)`; then velocity-scaled
   (`022BB8`, L20825) and clamped. The 0x0118FE lookup makes the contour **logarithmic
   / quasi-exponential in perceived loudness** while the reg_idx-0 counter ramps
   linearly. MEASURED that it is a table lookup; INFERRED that 0x0118FE is a
   log/attenuation curve (table body lies below this disasm's range at 0x0118FE and was
   not dumped here — **direction (loud=high vs loud=low) is UNVERIFIED**, flag for the
   live check).

Format summary: reg_idx 0 carries the **fast per-tick linear magnitude** (low byte);
group8/9/10 carry the **per-segment log-scaled, pan-split L/R bus gains** (high byte).
Both are GAINS the chip multiplies the PCM by (INFERRED — IC303 internal), not raw
sample data.

---

## Q5 — note-on seed vs per-tick update — MEASURED. SAME register at both

* Note-on programs reg_idx 0 with `0x8100` (key-on trigger) inside the note-on cluster
  `LABEL_02D68F` (asm L30209-30213: `LD WA,IZ ; LD (100000h),WA ; LDW (100002h),8100h`,
  IZ = voice number → group0.bank0).
* Per-tick, the SAME register (group0.bank0) is rewritten by `026E5B` (L21486) with the
  time-varying `slot[+0x2d]` (`0xF000|mag` / `0xFE00|mag`), and again per-segment by
  `LABEL_02CD71` (asm L29209-29210: `LD BC,(XIZ+02dh); CALL ToneGen_WriteSingleReg`).
* The L/R bus gains (group8/9/10) are ALSO written at both note-on (`027FD6`,
  L23045-23134) and per-segment (`02D436`, L29936-30033) from the same block fields
  (+0x2c/+0x2e/+0x30/+0x32/+0x34/+0x36).

So it is ONE continuously-updated level register per family — group0.bank0 for the
combined gate+magnitude, group8.bank0/bank1 (+siblings) for the bus gains — written at
note-on and rewritten as the envelope walks. There is no "note-on writes reg A, tick
writes reg B" split. **Consequence for the HLE:** the render can simply READ the level
the ROM already deposits in these registers; it does NOT need `update_voice_params` to
fire on a *new* group/bank — group0.bank0 already passes through `data_w`, and group8
already triggers `update_voice_params` (L208). MEASURED.

---

## Q6 — the complete per-voice amplitude chain (firmware truth)

Ordered by how the ROM builds and deposits it:

1. **Velocity (static per note)** — group0.bank2 (+0x080) = `reg_idx 2`. Written once at
   note-on by `LABEL_027F96` (asm L23012-23018: `ADD WA,0080h`; data = block+4 with
   bit15 cleared). HLE reads `reg[2] & 0x0FFF` (L270). USED, correct.
2. **Envelope magnitude (per tick, fast, linear)** — group0.bank0 (+0x000) =
   `reg_idx 0`, low 9 bits of `slot[+0x2d]`. Written per coarse tick by `026E5B`
   (L21486) and per segment by `02CD71` (L29210). HLE: **ignored** (gate only).
3. **Envelope bus gains (per segment, log, pan-split L/R)** — group8.bank0 (+0x800,
   `reg_idx 20`) and group8.bank1 (+0x840, `reg_idx 21`) = the bus-0 L/R gain PAIR, both
   `loglevel<<8` (pan applied by scaling loglevel differently per side in `026975`/
   `026AAA` before the write); plus bus-1 (group9, reg_idx 24/25) and bus-2 (group10/
   group9.bank3, reg_idx 28/27) for the effect sends. Written at note-on (`027FD6`) and
   per segment (`02D436`). HLE: reads `reg[20]` as "main volume" (per-segment trigger DOES
   fire), but MISINTERPRETS it — see below — and reads `reg[21]/reg[22]` low bytes as
   *pan*, which are ~0 here (the level is in the high byte), so pan defaults to center.
4. **Expression (per tick, 2nd domain)** — group1.bank2 (+0x180) = `reg_idx 6`, value
   `slot[+0x2b]`. Written by `026EC3`→`02D670`. HLE: stored, ignored.
5. **Pan** — NOT a separate register. It is folded into the group8/9/10 L/R gains
   (item 3). The HLE's `reg[21]/reg[22]`-as-pan model does not correspond to a firmware
   pan register.

### The register-by-register semantic map

| addr (+off) | group.bank | reg_idx | firmware role | value format | when written | HLE render uses it? |
|---|---|---|---|---|---|---|
| +0x000 | 0.0 | 0 | voice control = **gate + amp-envelope magnitude + routing** | `[15]gate,[14:12]/[9]route,[8:0]lin mag`; 0x8100/0x7E00/0xF000\|m/0xFE00\|m | note-on + **per tick** (026E5B) + per seg | **gate only; magnitude DROPPED** |
| +0x040 | 0.1 | 1 | pitch (semitone ratio) | 16-bit pitch-table word | note-on / pitch change | yes (`update_pitch`) |
| +0x080 | 0.2 | 2 | velocity volume (static) | `[11:0]` lin, bit15=latch | note-on (027F96) | yes (`reg[2]&0xFFF`) |
| +0x0C0 | 0.3 | 3 | waveform control | index-ish | note-on / cleared on off | approx (`resolve_waveform`) |
| +0x180 | 1.2 | 6 | expression (2nd-domain envelope level) | level word (slot+0x2b) | note-on + **per tick** (026EC3) | stored, **ignored** |
| +0x400 | 4.0 | 8 | note / octave key info | `(note<<8)` | note-on (027F74) | yes (octave in `update_pitch`) |
| +0x800 | 8.0 | 20 | **bus-0 L gain (envelope×pan)** | `(loglevel<<8)\|0x80` | note-on + **per seg** (02D436) | partial+**wrong**: read as "main vol", inverted |
| +0x840 | 8.1 | 21 | **bus-0 R gain (envelope×pan)** | `loglevel<<8` | note-on + per seg | **wrong**: read as pan-L (low byte ≈ 0) |
| +0x880 | 8.2 | 22 | 2nd-domain bus level | `level<<8` (02D620/02D5D0) | per seg | **wrong**: read as pan-R |
| +0x900 | 9.0 | 24 | bus-1 L gain (effect send) | `loglevel<<8` form | note-on + per seg | stored, ignored |
| +0x940 | 9.1 | 25 | bus-1 R gain | " | note-on + per seg | stored, ignored |
| +0x9C0 | 9.3 | 27 | bus-2 gain | " | note-on + per seg | stored, ignored |
| +0xA00 | 10.0 | 28 | bus-2 gain | " | note-on + per seg | stored, ignored |

MEASURED except the internal chip combine (INFERRED). PREDICT-THEN-CHECK: predicted the
envelope would land in a register the render ignores — **hit** (reg_idx 0 magnitude +
reg_idx 6). One miss vs the task's framing: the render is NOT wholly blind to the
envelope — it already re-runs `update_voice_params` when the per-segment loglevel hits
group8.bank0 (`reg_idx 20`); it just interprets that register backwards and misses the
smooth per-tick layer and the L/R-gain-pair structure.

---

## What the `kn5000_tonegen` render must change (precise, minimal)

The envelope runs in ROM; do **not** re-implement it. The chip model's only job is to
READ the level the ROM writes. Minimal, ordered by impact:

1. **Stop re-triggering key-on on envelope writes (correctness prerequisite).**
   In `data_w` group0/bank0 (L183-195), gate on/off should key ON only for the genuine
   trigger — `data == 0x8100` (or a rising edge out of the idle/off state) — NOT for
   every `data & 0x8000`. As written, each `0xF000|mag`/`0xFE00|mag` rewrite calls
   `process_key_on` and resets `wave_offset = 0`, corrupting playback.

2. **Read the per-tick amplitude envelope from reg_idx 0.**
   When group0/bank0 is written with bit15 set and `data != 0x7E00`, extract the
   magnitude `data & 0x01FF` (linear, 0x1FF≈full; low byte dominates) into a new
   per-voice `env_level`, and multiply it into `volume_l/volume_r` in
   `sound_stream_update` alongside the existing velocity term. This is the register the
   dedicated per-tick amplitude stepper (`026E5B`) targets, so honoring it makes the
   ROM's attack/decay/sustain/release audible. Treat `0xFE00|mag` the same as
   `0xF000|mag` for level (the 0xFE00 vs 0xF000 difference is release-mode/routing, not
   a different scale).

3. **Fix the group8 interpretation (`update_voice_params`, L263-303).**
   `reg[20]` (+0x800) and `reg[21]` (+0x840) are the bus-0 **L and R gains**, each
   `loglevel<<8` (level in the HIGH byte, louder = higher IF 0x0118FE is a straight
   level table — verify direction live). They are NOT "main volume + pan". Replace the
   `main_vol = 0xFF00 - (reg20 & 0xFF00)` inversion and the `reg[21]/reg[22] low-byte
   pan` reads with: `gain_L = reg[20] >> 8`, `gain_R = reg[21] >> 8` (pan already baked
   in). `reg[22]`/group9/group10 are the effect-send buses — ignore for dry output.

4. **Expression (reg_idx 6, +0x180) — optional second pass.** A second per-tick level;
   fold in as an extra multiplier once item 2 is validated. Lower priority.

`update_voice_params` does **not** need to trigger on a *new* group/bank: group0.bank0
already flows through `data_w`, and group8 already triggers the recompute. The fix is
about READING bits already arriving, not routing new addresses.

**Is it "already audible"? No.** The coarse per-segment contour is *partially* present
via `reg[20]`, but (a) it is interpreted inverted, (b) the smooth per-tick ramp
(reg_idx 0 magnitude) is dropped entirely, and (c) the spurious key-on re-trigger
resets the waveform on every envelope tick. Items 1-3 above are the minimal set to make
the ROM's software envelope faithfully audible.

### Live-check gate (before committing numbers)
The one UNVERIFIED numeric is the direction of table 0x0118FE (loud=high vs loud=low)
and the exact magnitude bit-width in reg_idx 0. Confirm on the running KN5000 build by
watching group0.bank0 (`0x100000/0x100002`) writes over a held note for a slow-attack
vs fast-decay sound — expect the low byte of the `0xF000|mag` writes to rise then fall.
Everything else here is MEASURED from the disassembly.
