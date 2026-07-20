# The global effect ENABLE bits (0x500C0758 / 0x500C075A) and the command
# dispatcher that writes them

**Date:** 2026-07-20. Static, from the conversion of the TG global-parameter
module `0x4C008CBB..0x4C009837` (kn7000_disassembly commit 887169f, 44
functions, byte-match held). Cross-referenced against the LIVE captures in
`effect-return-routing.md` (per-effect sub-TG send/return registers),
`dsp-unit-roles-live-capture.md` (the fixed-function DSP unit map) and
`reverb-toggle-findings.md` (the panel REVERB button trace).

This closes the question left open by the previous tick: *which of the
0x500C0758 bits other than bit9 belong to which GUI effect.* It is answered
for **two** of them and honestly left open for four.

## 1. The dispatcher

`TgGlobalParamCommand` = **0x4C0092B3** (post-prologue entry 0x4C0092B9),
signature `(d0 = command id, d1 = value)`.

```
if (id < 9 || id > 0x50) return;
k    = id - 8;
slot = k & 0x3F;
e    = (struct { u32 key; void (*fn)(); } *) 0x48586C60 + slot;
if (e->key != k) return;      /* unassigned -> the no-op tail 0x4C009562 */
goto *e->fn;                  /* ~30 INLINE handler blocks, all returning
                                 through this frame: ret [d2,d3,a2],0xa4 */
```

It is **one function**, not thirty-one: every handler block is inline and
shares the dispatcher's stack frame. Its **only** caller in the image is the
sound-command byte-stream interpreter at **0x4C003ED3**, which pulls two bytes
off the stream (`0x4C003A17`) and calls the entry — so every global TG
parameter on the instrument is set by a two-byte message, not by a direct
call from the UI.

The 64-entry table at **0x48586C60** (program ROM, file offset 0x186C60) is
the authoritative id → handler map. 24 of the 64 slots are live.

## 2. The bit map

`0x500C0758` is a halfword of global enables; `0x500C075A` a halfword of
global gates.

| bit | mask | setter | dispatcher id | channel refresh triggered | identification |
|---|---|---|---|---|---|
| 1,2,3 | 0x000E | `TgEffectRouteSelect` 0x4C008FA1 | 0x29 | — | **3-value ROUTE field** (value 1/2/3 → bit1/2/3, 0 = none). Not a bitmask: the setter clears 0x000E first. Consumers are in the element layer (0x4C0350E4/517E/527F/531E/5555/578C read bit2; 0x4C03545D/5502/5693/5739 read bit1). |
| 4 | 0x0010 | `TgEffectEnableBit4` 0x4C0090EC | 0x42 | none | **not named** — read once, at 0x4C036EC3 in the low-level TG layer |
| 9 | 0x0200 | `TgEffectEnableReverb` 0x4C00908F | 0x40 | chan **3** + chan **0x0B** | ★ **REVERB** |
| 10 | 0x0400 | `TgEffectEnableBit10` 0x4C0090C0 | 0x41 | none | **not named** |
| 11 | 0x0800 | set/cleared at 0x4C00840E / 0x4C008420 (a *different* module) | — | chan **7** | **not named**; the most-read bit of the lot (the per-part apply layer 0x4C0046E6/4796/48AB/49B4/4A4D/4BAD/4C8B/4F41 and 0x4C02CDA3 all gate on it) |
| 12 | 0x1000 | `TgEffectEnableMulti` 0x4C00916B | 0x45 | chan **0x0C** + chan **6** | ★ **MULTI** |
| 13 | 0x2000 | `TgEffectEnableBit13` 0x4C009197 | 0x46 | chan **1** | **not named** |
| 14 | 0x4000 | `TgEffectEnableBit14` 0x4C0091C3 | 0x47 | chan **5** | **not named** |

`0x500C075A`:

| bit | setter | id | meaning |
|---|---|---|---|
| 0,1,2 | `TgGlobalFlag{0,1,2}{Get,Set,Clear}` 0x4C00921A..0x4C0092B3 | 0x4A writes all three as a 3-bit field | a 3-bit mode field, individually accessible |
| 3 | `TgGroupGainClass23Enable` 0x4C009115 | 0x43 | gate for the class-2/3 group master gain `0x500C0760` — **inverted** (non-zero argument *clears* the bit) |
| 4 | `TgGroupGainParts13To1AEnable` 0x4C009140 | 0x44 | gate for the parts-0x13..0x1A group gain `0x500C0762`, also inverted |
| 5 | `TgMasterVolumeSubEnable` 0x4C0091EF | 0x48 | include the SUB master-volume term `0x500082B6` in the `0x500C0780` bus |

Bits 3 and 4 are exactly the gates `TgLevelTermFinalize` (0x4C02BF86) was
already documented to apply to those two group gains — the two halves now
meet.

## 3. How bit9 and bit12 got named (and why the others did not)

Each enable handler re-runs the **global effect-channel refreshers** converted
in the previous tick, and each refresher gates its own programming on the same
bit. The channel numbers are the `d0` argument to the sub-TG register writers
`0x4C037F10` / `0x4C037EB7` / `0x4C037D14` / `0x4C037E08`, so they can be read
straight off the code. `effect-return-routing.md` captured the panel toggles
live against the same channels:

| live-captured (effect-return-routing.md) | static (this note) |
|---|---|
| REVERB button → send **ch0B**.r8, return **ch03**.rA | bit9 handler refreshes chan **3** + chan **0x0B** |
| MULTI button → return **ch06**.rA | bit12 handler refreshes chan **6** + chan 0x0C |

Two independent methods, same channels — that is what pins **bit9 = REVERB**
(already known, now confirmed structurally) and **bit12 = MULTI** (new).

The remaining candidates cannot be closed the same way:

* **CHORUS** toggles only `ch19`.r8 and **SOUND DSP** only `ch09` — per-part
  *matrix rows*, not the global channels 1/3/5/6/7/0x0B/0x0C this module owns.
  So the chorus and sound-DSP enables are **not** in this halfword, or at
  least not observable through it. Bits 10 and 4 (which refresh no channel at
  all) are the natural suspects but nothing in the code says so, and it is not
  claimed here.
* **bit13 → chan 1** and **bit14 → chan 5**: the channels are certain, the GUI
  label is not. Chan 1 writes reg 0 and reg 5; chan 5 writes reg 0 and reg
  0x0C — neither uses the reg-8/reg-0xA send/return convention the four
  captured effects use, so they are probably not effect sends at all.
* **bit11** has no setter in this module; it is set/cleared at 0x4C00840E /
  0x4C008420, and is by far the most widely *read* bit. Whatever it is, it is
  a more fundamental gate than the panel effects. Its channel is 7.

## 4. Two side facts worth keeping

* **REVERB OFF is conditional.** `TgEffectEnableReverb(0)` first tests
  `0x500C0758` bit3 — the top value of the ROUTE field — and if it is set,
  takes the *enable* path anyway. With route == 3 the reverb cannot be turned
  off through this setter. (Not yet observed live; a candidate explanation if
  a future capture shows a reverb-off press that doesn't stick.)
* The dispatcher also owns the **master volume chain**:
  `0x500082B4` (main, id 0x14) + `0x500082B6` (sub, id 0x20) + `0x500082B8`
  (aux, id 0x21), each biased −0x7F, summed, clamped to [−0x7F, 0] and
  published as `0x500C077E` (all three) and `0x500C0780` (sub only if
  0x500C075A bit5), scaled ×0xC992/0x7F and written to hw via `0x4C038028` /
  `0x4C038046`; plus the master **fine tune** `0x500C075C` = v×2 (id 0x19) and
  master **transpose** `0x500C075E` = (v−0x40)<<8 (id 0x1A) — the two terms
  `tg-pitch-pipeline.md` already had on the read side.

## 5. Not claimed

Nothing here is a behavioural result: no MAME run was made for this note. The
GUI names for bits 4, 10, 13 and 14 remain open, and the CHORUS and SOUND DSP
global enables have not been located at all. The next place to look is the
**producer** of the command ids — the maincpu code that builds the two-byte
sound-command messages — since that is where a panel button and a command id
are in the same basic block.

---

## 6. Addendum 2026-07-20: the PRODUCER side

Section 5 said the next place to look was the *producer* of the command
ids. It has now been traced (kn7000_disassembly commit 348551b, 35 more
functions converted, byte-match held).

### 6.1 The "sound-command byte stream" is an internal MIDI stream

The interpreter is **0x4C003B31** (prologue 0x4C003B2C). It pulls a status
byte with `SndCmdStreamGetByte` 0x4C003A17 and dispatches on `status & 0xF0`:

| status | data bytes | meaning |
|---|---|---|
| 0x9x | 3 | note-on family -> 0x4C036EA4, or 0x48483873 when the first data byte >= 0xF0 |
| 0xAx | 2 | -> 0x4C003C6B |
| 0xBx | 3 | control change -> 0x4C003CC6 |
| 0xCx | 2 | program change -> 0x4C003D4A |
| 0xDx | 2 | -> 0x4C003DD4 |
| 0xEx | 3 | -> `0x4C008C74` (the TG global module's *other* entry) |
| **0xFx** | **2** | **`TgGlobalParamCommand(id = data1, value = data2)`** at 0x4C003ED3 |

Region-1 code produces messages by building a **length-prefixed byte
buffer** (`{ len, status, data... }`) and calling the stream writer
**`SndCmdStreamWrite` 0x4C003A65** (32 call sites image-wide).

### 6.2 Who emits which global-parameter id

A full scan of the image for 0xFx message construction (both the code
pattern and a data-region scan for the byte template `03 F0 <id> <val>`)
finds **exactly three** producers:

| producer | id emitted | value |
|---|---|---|
| `SndCmdEmitUnitCc` **0x48410FB0** | **0x35** | the unit value, when the resolved unit is 0xFF |
| `SndCmdEmitGlobalDepth` **0x48411101** | **0x33** (sel 1) / **0x34** (sel 5) / **0x32** (sel 9) | `d1 * 0x7F / 0x63` — a 0..99 **percent** control |
| `SndCmdSendReverbPartsApply` **0x4844B334** | **0x2B** | the canned ROM message 0x485B85EC, value 0x7F |

Both of the first two live in the **sound-unit setting module**
0x484104C7..0x4841202C, which is driven by five parameter-database groups
`0xB010 / 0xB020 / 0xB030 / 0xB040 / 0xB050` (sub-key `+0x04` = the target
part, which must be in 0x13..0x1A).

### 6.3 What this does and does not settle

* It **confirms** the id → channel chain from the other end: id 0x32 sets
  0x500082BE and refreshes chan **0x0B** — the live-captured REVERB SEND —
  and its producer is a **percent-valued** control (0..99 → 0..127). That is
  the shape of a front-panel *depth* control, and it is the first time a
  region-1 control and the reverb send channel have been seen in the same
  basic block.
* It **does not** name bits 4/10/13/14. The enable ids 0x40..0x47 have **no
  region-1 producer at all** — nothing in the maincpu image builds a 0xFx
  message with those ids. They are driven from the **library** side: the id
  list at **0x485870F0** (`01 02 .. 0b 10 11 20 40 41 42 43 44 45 46 47 48
  49 4a 4b ff`) is referenced only from library code around 0x4C00FB94.
  So the next place to look is that library consumer, not the maincpu.
* No behavioural result: no MAME run was made for this addendum.

---

## 7. Addendum 2026-07-20 (second): the 0x485870F0 lead is DEAD — RETRACTED

Section 6.3 named the library consumer of the byte list **0x485870F0** as
"the next place to look" and the *only* remaining route to naming enable
bits 4/10/13/14. That consumer has now been read
(kn7000_disassembly, `tools/dis_view.py`; the three references are at
0x4C00FB92, 0x4C00FC0C and 0x4C00FC81, inside three sibling collectors
0x4C00FB3C / 0x4C00FBC5 / 0x4C00FC3C).

**It is not the same id space.** 0x485870F0 is the per-part **class-register
TAG table** of the sub-TG register cache — the very table the already-named
`TgPartClassRegCollect` (0x4C00FBC5, entry 0x4C00FBCA) walks in parallel with
`0x500C59E4 + part*0x36`, one halfword slot per tag. Its 27 entries
(`00..0B 10 11 20 40..4B`, terminator `FF`) index that cache; a companion
table 0x48587030 maps `tag & 0x3F` to a dense 0..0x0E slot and 0x485870B0 to
0x0F..0x1A.

Two independent reasons the numeric overlap with the dispatcher ids
0x40..0x47 is a **coincidence**:

1. `TgGlobalParamCommand` only accepts ids **9..0x50** (`k = id - 8` keyed
   into 0x48586C60). Twelve of the 27 tags are `0x00..0x0B` — below 9, so
   they cannot be dispatcher ids at all.
2. None of the dispatcher ids this note actually traced (0x14, 0x19, 0x1A,
   0x20, 0x21, 0x29, 0x2B, 0x32, 0x33, 0x34, 0x35, 0x48..0x4B) appear in the
   tag list, and none of the tag values 0x00..0x0B appear in the dispatcher
   table. The two sets meet only on 0x40..0x4B, which is what made the lead
   look plausible.

So the plan of section 6.3 is **retracted**, as the "go to the maincpu
producer" plan of section 5 was retracted before it. Bits 4, 10, 13 and 14
still have **no** GUI name, and both static routes are now exhausted:

* no region-1 code builds a 0xFx message with ids 0x40..0x47 (section 6.3);
* no library code reaches those ids through 0x485870F0 either (this section).

Whatever writes them either constructs the command bytes somewhere a byte
template scan cannot see (computed id), or the enables are simply never
driven at all in this firmware.

### What would settle it — a QUEUED LIVE TASK

Static analysis has nothing left to offer here. The remaining method is
behavioural, and it is cheap:

> **Live enable-path tap.** Break/watch on `TgGlobalParamCommand`
> (0x4C0092B3) — or simply watch the halfword `0x500C0758` — and press each
> panel effect control in turn: REVERB, CHORUS, SOUND DSP, MULTI, DIGITAL
> EFFECT, and the per-part effect on/off keys. Record `(button, id, value,
> 0x500C0758 before/after)`. Any button that moves bit 4, 10, 13 or 14 names
> it outright; a full sweep that moves none of them is itself a result — it
> would mean those four enables are dead in this firmware, which is a
> publishable finding in its own right.
>
> Prerequisite: the play screen with sound (CONFIG bit2), since the effect
> layer is idle on the SD menu.

Until that session runs, bits 4/10/13/14 stay **deliberately unnamed**.
