# The per-part depth bank DECODED — group-0x20 is a per-part send matrix (queue item B2, 2026-07-20)

Resolves the "depth channels 0x30-0x3B + sends 0x06/0x07 undecoded" gap from
notes/per-part-effect-model.md and the cold-toggle "on-but-silent" question from
notes/effect-return-routing.md. Method: full group-0x20 write capture across cold vs
post-refresh toggles (`kn7000-emulator/b2cap.lua`), RAM diff to locate the depth shadow
(`b2ram.lua`), watchpoints + breakpoints on the writers (`b2wp.lua`, `b2bp2.lua`,
`-debug -debugger none`), then static RE of the lib emitter/setter family.

## 1. The address decode (supersedes the flat "channel" reading)

`addr = 0x8000 | row<<8 | part<<4 | reg` — the old "channel" 0xRP is really
**row R (0..3) of mixer part P**. Verified rows:

| row | reg 8 halfword | meaning |
|---|---|---|
| 0 (0x80P8) | `0x03·L` | part P send-to-REVERB bus (hi byte 0x03 = dest part 3 = reverb return) |
| 1 (0x81P8) | `0x0B·L` | part P send-to-CHORUS bus |
| 2 (0x82P8) | `0x06·L` / `0x08·L` | part P send-to-MULTI bus; **hi byte = ON marker (0x06 = ON, 0x08 = OFF)** |
| 3 (0x83P8) | `0x85··`/`0x8C··` | part P output LEVEL/depth (the old "0x30-0x3B depth bank") — for the effect-return parts this is the effect TOTAL DEPTH (part 3 row3 = 0x8338 = the reverb TOTAL DEPTH already modeled) |
| reg 0xA | `[direct\|return]` | part P dry/insert-return crossfade (part 3 = the REVERB toggle pair; part 6 = the MULTI return enable; part 9 = the SOUND-DSP insert crossfade) |

Mixer parts = raw TG parts (7, 0xB, 0xC…) + **effect-return parts**: 3 = reverb
return, 6 = multi return, 9 = the per-part Sound-DSP INSERT return (RIGHT1).
The old note's "per-part sends ch 0x06/0x07" are simply row0 of parts 6/7 —
e.g. ch06.r8 = 0x0366 is the multi-return part's own send-to-reverb (effect
chaining), written when MULTI turns on.

## 2. The writer chain (lib, all offsets byte-verified)

- **Setter family 0x4C037D0F..0x4C037F10** — one setter per row (+ a combined
  base+level variant per row). Each merges a low-7 LEVEL argument into a
  16-bit shadow at `0x500CE2B0 + part*0x10` (+0 row0, +2 row1, +4 row2,
  +8 row3 dword) and emits the TG write through TgVoiceRegWrite_entry
  0x4C036F9A with d1 = `0x8R08<<16`. NOTE the two-entry ABI: `call` enters at
  movm+5 (e.g. chorus level setter = **0x4C037D8C**, multi combined =
  **0x4C037E3C**); the movm+add prologue is only for JSR-style entry. MDR
  holds the return address at entry (usable in debugger printf actions).
- **Row-refresh orchestrator 0x4C004E30** — refreshes one part's whole row
  block. Its gate reads the PART RECORD `0x500B5340 + idx*0x54C`:
  `+0` bit3 (**the part-insert / SOUND DSP flag**) AND `+0x62 & 0xE000` AND
  byte `+0x14` must all be nonzero, else `jmp 0x4C005083` = the **ZERO
  path** (writes level 0 to row0/1/2, row3 = 0x7F). The real path applies:
  row1 level = record byte **+0x15 (chorus depth, default 0x3C)** gated by
  `+0` bit1 (part-chorus enable); row2 level = **+0x16 (multi depth, default
  0x50)** with base nibble 6; row0 level from helper 0x4C02CA79.
- Record index for TG part 9 = **0x10** (RIGHT1). Cold boot: `+0 = 0x4907`
  (bit0/1/2 set, bit3 CLEAR); the panel SOUND DSP toggle sets bit3
  (0x490F) — the ONLY RAM byte in the whole record space that changes.

## 3. The cold-toggle mechanism (the "on-but-silent" root cause)

A cold panel CHORUS press produces EXACTLY five TG writes (part-9 row refresh:
809A=7F00, 8098=0300, 8198=**0B00**, 8298=0800, 8398=8550) and **no DSP
host-port writes** — the zero path, because RIGHT1's insert flag is off. After
a SOUND DSP toggle (bit3 set) the same press writes 8198=**0B3C**. A cold
MULTI press additionally refreshes the multi-return part 6 (806A=007F,
8068=0366, 8168=0100, 8268=0800, 8368=857F) and writes part 9 row2 =
**0x0600** (ON marker, level 0).

So with the insert off, the firmware announces the global-effect state only
via: the **CHORUS/MULTI LEDs** (always), the row2 **base nibble 6/8** (multi),
and the part-6 refresh (multi). The depth values live solely in the part
records (+0x15/+0x16), never reaching the TG.

## 4. The driver model (kn7000.cpp + kn7000_cpanel)

Single-mix approximation (no per-part TG audio), so the bridge derives one
effective send per effect:

- **MULTI**: decode row2's ON marker — `m_gain_multi = lvl ? lvl : (marker==6
  ? 0x50 : 0)`. Register-authoritative; the firmware's own written level
  always wins. (The return enable ch06.rA was already tracked and DOES move
  on a cold toggle.)
- **CHORUS**: no register carries the cold state → gate on the firmware's own
  CHORUS LED (shadowed in kn7000_cpanel_device::panel_led_frame, getter
  `chorus_led()`); default depth 0x3C when the LED is on and the written send
  is 0. A firmware-written send (insert on) always wins.
- Labeled HLE: this substitutes the *default* part-record depths; a user
  editing PART SETTING depths with the insert OFF won't be tracked (the
  firmware itself never emits them). With the insert ON everything is
  register-exact as before.

## 5. Verification

- Cold CHORUS toggle + keybed note: chorus unit (u9) fed and audible with no
  SOUND DSP interaction (was silent before). Cold MULTI toggle: u1 audible.
  A/B captures in the item-B status tick.
- Reverb oracle unchanged (effects off => both gates cold => identical path).
