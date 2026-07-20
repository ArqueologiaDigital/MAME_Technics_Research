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
