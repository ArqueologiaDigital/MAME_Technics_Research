> Phase C / first-cut-audio recon (2026-07-09). Companion to sound-subsystem-plan.md.

# KN7000 Tone-Generator per-voice register semantics — synthesis-oriented map

Scope: enough of IC201/IC205's per-voice register interface to drive a minimal synth (pitch, waveform, key-on, volume) and to match a Phase-C capture. Every claim is tagged **[CONFIRMED]** (read directly from KN7000 firmware disassembly), **[KN5000]** (inferred from the documented, shared-codebase sibling), or **[UNKNOWN]**.

Disassembly method: `../mame-sony-video/unidasm build/kn7000_program.rom -arch mn10300 -basepc 0xADDR -skip (ADDR-0x48400000)`. Program ROM base = 0x48400000.

---

## 0. The single most important correction first (KN7000 address layout is NOT the KN5000 layout)

The prior note (`kn7000_mame/notes/tone-generator.md:51-67`) assumed the KN7000 reuses the KN5000 address encoding `group<<8 | bank<<6 | channel`. **The disassembly disproves this.** The KN7000 low-level write helper (0x487EFF69, the sub/main dispatcher; bodies at 0x487EFF70 sub / 0x487EFF92 main) builds the 32-bit word as:

```
word = (channel & 0x3f) << 20   |  d1(reg-class, in bits16-31)  |  data(bits0-15)
addr_port (0x98040000/0x98050000) = word >> 16
data_port (0x98040002/0x98050002) = word & 0xffff
```
(`0x487eff92: and 0x3f,d0 / asl 20,d0 / or d1 / or d2 / lsr 16→addr / and 0xffff→data`, confirmed against the live disasm.)

Because the channel field lands at **word bits 20–25 = address bits 4–9**, the KN7000 register-address bitfield is:

| addr bits | field | notes |
|---|---|---|
| **[3:0]** | register index (low nibble) | e.g. 0x2, 0x6, 0x9, 0xd |
| **[9:4]** | **channel / voice 0–63** | per-voice stride in the address space = **0x10**, not 1 |
| **[15:10]** | register group / class | e.g. 0x04→bit10, 0x20→bit13, 0x40→bit14 |
| **[15]** | doubles as a **latch strobe** | address 0x4014 vs 0xc014 = strobe pair (see §1 key-on) |

Cross-check against captured traffic: the idle "0xFC08…0xFC0B" refresh decodes to group 0x3F, index 8–0xB, channel 0 — a global/system bank, consistent with "not per-voice." The boot "groups 0x04 and 0x0C, all 64 channels" init decodes to `0x0400|(ch<<4)|idx` swept over ch=0..63.

**TG select / voice count [CONFIRMED]:** the dispatcher routes by voice id: `cmp 0x40,d0; bge main`. id 0–63 → **sub TG (0x98050000)** ch 0–63; id 64–127 → **main TG (0x98040000)** ch 0–63. So **128 voices total = 64 per TG × 2 TGs.**

> **Driver bug that blocks synthesis (actionable): `kn7000.cpp:505,509` gate capture on `m_tg_addr < 0x1000`.** Real per-voice addresses reach 0x2000/0x2400/0x3000/0x40xx/0xc0xx — i.e. **pitch, group-0x40 and the key-on strobe are all silently dropped** by the `[2][0x1000]` array. The capture array must be `[2][0x10000]` (full 16-bit address space) before any Phase-C capture or synthesis will see pitch/key-on.

---

## 1. Best-effort KN7000 per-voice register map

Register classes actually emitted by the per-voice writer (0x487EFF6B) were enumerated across the whole driver region 0x487E5000–0x487E9E00. Distinct reg-class high-halves observed: `0x0402 0x0406 0x0409 0x040d  0x2000 0x2400 0x3000  0x4014 0x4028 0x4059 0x4070 0xc014` (plus broadcast globals 0x0400/0x0c00). Address for voice N = `class | (N<<4)`.

| Reg class (addr, ch=0) | width / data | source | meaning | tag |
|---|---|---|---|---|
| **0x2000** | 13-bit signed (`&0x1fff`) | pitch calc **0x487EA5A3** (reads MIDI note `(0x19,ptr)&0x7f`, adds base `(0x12,a2)`, −0x64/−0x200) | **PITCH / phase increment** (osc A) | **[CONFIRMED pitch-derived]** |
| **0x3000** | 13-bit signed (`&0x1fff`) | same calc 0x487EA5A3 | **PITCH** (osc B / coarse; dual-osc voice) | **[CONFIRMED pitch-derived]** |
| **0x2400** | 13-bit (`&0x1fff`) | 0x487EA5A3 path | pitch/level companion | inferred |
| **0x0409 / 0x0402 / 0x040d / 0x0406** | 14-bit (`&0x3fff`), top 2 bits (0xc000) preserved | voice struct offsets **+0x2c / +0x30 / +0x2e / +0x32** (writer 0x487E5FB7, case 0/1/2/3) | group-0x04 **note-key / level / envelope** params (KN5000 grp0x04 = note-key-info + level banks) | **[CONFIRMED regs], [KN5000 meaning]** |
| **0x4014 (↔ 0xc014)** | via 32-bit-data writer 0x487B97B8 / 0x487B9AED; written as a **bit15-address strobe pair** (0x4014 clear ↔ 0xc014 set, 0x487E6959 / 0x487E6999) | — | **KEY-ON / voice-control latch** (best candidate: the SET/CLEAR strobe mirrors KN5000's key-on latch) | **[CONFIRMED strobe], meaning inferred** |
| **0x4028 / 0x4059 / 0x4070** | 32-bit-data writer | — | group-0x40 level / **volume-velocity** / **pan** / effect-send | **[UNKNOWN]** (see Phase C) |
| 0x0400 / 0x0c00 (broadcast) | via 0x487EFFDB (writes BOTH TGs, field `asl 18`) | init/clear | global voice clear (grp 0x04/0x0C), all channels | [CONFIRMED] |

### The four fields a minimal synth needs
1. **Pitch (phase increment): reg class 0x2000 and 0x3000** — 13-bit signed, computed from MIDI note by 0x487EA5A3. This is the one field pinned to real semantics. **[CONFIRMED]**
2. **Key-on/off: reg class 0x4014**, driven by the address-MSB strobe pair 0x4014↔0xc014 (parallels KN5000's `+0x080` bit15 SET-then-CLEAR and `+0x000`=0x8100 key-on). **Strobe [CONFIRMED]; that 0x4014 == key-on is inferred** — Phase C must confirm the exact data value at the strobe.
3. **Volume / velocity: [UNKNOWN]** — velocity enters via the pitch/level calc (0x487EA5A3 reads note & a level base), and a group-0x40 register (0x4028/0x4059/0x4070) is the likely main-volume/velocity sink. Not resolvable statically with confidence. **[KN5000 analog: grp0x08 main-volume 0xFF80=mute.]**
4. **Waveform select / start address: [UNKNOWN which reg]** — see §3. It is an **index, not a raw address**.
5. **Pan: [UNKNOWN]** — inferred group-0x40 register pair. **[KN5000 analog: grp0x08 bank1/2, 0=silent/0x3C=center/0x78=full.]**

### Per-voice RAM working struct [CONFIRMED]
Voice parameter struct base **0x500AF940**, **stride 0xB4 (180 bytes)**, indexed `voice * 0xb4` (`0x487E6C71: mov 0xb4,d0; mulu; add 0x500af940,a0`). Field `(2,a0)` gates a `&0x7c` 4/8/0x10/0x20/0x40 state dispatch (0x487EFD1B) — the voice-control state machine (KN5000 analog: 0x7E00 idle / 0x8100 key-on). This RAM struct is the KN7000 equivalent of the KN5000 44-byte voice template; the group-0x04 register data comes straight from its +0x2c…+0x32 fields.

---

## 2. Expected register-write SEQUENCE for one note-on (to match Phase C)

The KN7000 note→voice path could **not** be fully driven statically (prior finding, `notes/tone-generator.md:136-160`: MainSoundAdd 0x4848C043 / MainSeqRun 0x484948BC never ran on blind stimulus; playback is never *triggered* in MAME, not hardware-gated). So the exact ordered emission is only partially known from the writer routines. Best static reconstruction, per voice slot, from the writer functions:

1. Group-0x04 params: writes to **0x0409, 0x0402, 0x040d, 0x0406** (+ channel<<4), data 14-bit from struct +0x2c/+0x30/+0x2e/+0x32 (0x487E5FB7).
2. **Pitch: 0x3000 and 0x2000** (+ channel<<4), 13-bit from 0x487EA5A3 (0x487E6C36, 0x487E6EAB).
3. Group-0x40 level/pan/send: **0x4028 / 0x4059 / 0x4070**.
4. **Key-on strobe on 0x4014**: write with addr bit15 SET (0xc014|ch<<4) then CLEAR (0x4014|ch<<4) — 0x487E6999 then 0x487E6959.

**The KN5000 documented order is the template to match** (`kn5000-docs/tone-generator.md:411-444`, `ToneGen_WriteVoiceParams`): pitch(+0x40) → velocity-latch SET(+0x80) → waveform(+0xC0) → note-info(+0x400) → main-volume(+0x800) → **KEY-ON(+0x000)=0x8100** → pan L/R(+0x840/+0x880) → sends → velocity-latch CLEAR(+0x80). Key point mirrored on KN7000: **volume/params are written first, key-on/strobe last.**

Phase C should log every `(TG#, addr, data)` for one note (e.g. C4=note 0x3C) and align it to this order. Expect: a burst of 0x04xx + 0x2000/0x3000 + 0x40xx writes for one channel, terminated by the 0x4014↔0xc014 strobe.

---

## 3. WAVEFORM ADDRESSING — index, not a CPU-provided start address

**Finding: the CPU never hands the TG a raw wave-ROM byte address.** No register write in the KN7000 driver carries a 24-bit ROM pointer; the pitch registers carry 13-bit values and the group-0x04 registers 14-bit values — far too small for a 16M-word (24-bit) address. This matches the documented KN5000 behavior exactly (`kn5000-docs/waveform-rom-format.md:124-155`): the SubCPU writes a compact **waveform/tone index** to a per-voice register (KN5000 `+0x0C0`, group0 bank3), and the **TG chip resolves index→ROM address internally** by reading an index/parameter table stored at the very start of the wave ROM.

KN5000 wave-ROM index format (the model to implement) [KN5000]:
- 4-byte entries `{uint16 param_ptr, uint16 wave_offset}` at ROM offset 0.
- **byte_addr = wave_offset × 16** (×8 in 16-bit words; 8-sample granularity).
- Loop/keyzone/tuning live in variable-length parameter records the chip reads itself — the CPU writes no loop registers.

Implication for the KN7000 synth's sample fetch:
- The waveform-select register on KN7000 is **[UNKNOWN which class]** — most likely one of the group-0x04 registers (0x0402/06/09/0d, sourced from the tone/patch struct) or a group-0x40 register; Phase C must identify it by varying the selected sound.
- The index→address table lives in the **undumped** wave ROMs (IC203/204/207/208). Until they are dumped, real addressing cannot be reproduced.
- The existing placeholder generator (`make_placeholder_waveroms.py`, tiled 16 MiB banks) **sidesteps this**: because every bank is tiled with a full-amplitude single-cycle waveform, any {start,loop} the TG lands on yields audible sound. So the synth can ship with: waveform-index-register → pick a placeholder bank; **pitch from 0x2000/0x3000; gate from the 0x4014 strobe**; and defer true index→addr lookup to post-dump.

---

## 4. What Phase C dynamic capture MUST extract (static gaps)

Because playback is never triggered in MAME and the note path is dormant, these must come from a live capture (via the CHORD-FINDER "ear" button or the now-working keybed FIFO at 0x98050004, `kn7000.cpp:465-476`). **First enlarge `m_tg_reg` to `[2][0x10000]` and log `(TG#, addr, data)` — the current `<0x1000` gate hides everything below.** Then capture one clean note-on/off and extract:

1. **Waveform-select register** — the one **[UNKNOWN]** field. Play the same note under two different sounds/tones; the register whose data changes with the *sound* (not the note) is the waveform index. Record index→sound mapping.
2. **Volume / velocity register** — play the same note at (if velocity-variable) two velocities, or read the main-volume register: identify which group-0x40 register (0x4028/0x4059/0x4070) tracks loudness, and its mute value (KN5000: 0xFF80).
3. **Pan register(s)** — set part pan L vs R in the UI; identify the group-0x40 register(s) that change and their center value (KN5000: 0x3C).
4. **Key-on data value & exact strobe order** — confirm 0x4014 is the trigger and capture the data written at the 0xc014→0x4014 strobe (the KN7000 analog of KN5000's 0x8100), plus the note-off value (KN5000 analog: 0x7E00 idle to `+0x000`, 0x0000 to waveform reg).
5. **Pitch reg confirmation** — capture 0x2000/0x3000 data for two known notes (e.g. C4 and C5, one octave) to verify the 13-bit value's scale (semitone/octave law) — the one thing needed to make pitch quantitatively correct rather than merely note-tracking.

With items 1, 4 and 5 the four-field minimal synth is fully specified; items 2–3 refine loudness/stereo.

---

### Key addresses (for follow-up)
- TG write dispatcher: **0x487EFF69** (sub/main by id<0x40); bodies 0x487EFF70 / 0x487EFF92; broadcast-both 0x487EFFDB.
- Per-voice writer entry: **0x487EFF6B**; group-0x04 writer **0x487E5FB7**; pitch/level writers **0x487E6C00, 0x487E6E80**; group-0x40 + key-on strobe **0x487E6959 / 0x487E6999** (via 0x487B97B8/0x487B9AED).
- Pitch computation: **0x487EA5A3** (note at struct `(0x19,ptr)&0x7f`).
- Voice RAM struct: **0x500AF940**, stride **0xB4**.
- Note-on entry points (dormant in MAME): MainSoundAdd 0x4848C043, RhyNoteOnVoice 0x4843DC7C (`note-on: vel@+2, note@+1, ch=b0&0xF, gate=b3+(b4<<7), routing@+5`), MainSeqRun 0x484948BC.
- Driver capture code + bug: `kn7000_mame/src/mame/matsushita/kn7000.cpp:503-511` (esp. the `<0x1000` gate at 505/509).
