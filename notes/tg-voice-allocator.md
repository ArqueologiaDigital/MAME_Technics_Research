# The TG voice allocator + steal engine (static RE)

Source: kn7000_disassembly commits 6fd75da/ec57390 — the library-image
functions under `TgNoteOn` that pick hardware slots, converted to real
re-assemblable MN10300 source (byte-exact). This documents the slot
choice and STEAL PRIORITY precisely; it is **static RE** (no live
verification yet). Complements tg-pitch-pipeline.md (what gets written
to a slot) — this file is about *which* slot.

## The shape of a note-on

`TgNoteOn` (0x4C036837) builds a **request record** and hands it to the
allocator chain:

```
+0x00 u16  (part<<8) | note | 0x80
+0x02 u8[4] per-element POOL byte: 0x80|pool (bit7 = element present;
            low nibble indexes the pool-descriptor table 0x485879D8)
+0x06 u8[4] per-element POLICY byte: bit3 = TG A allowed, bit4 = TG B
            allowed, bit7 = held (enrolls in the sustain mask), bit6 =
            no same-note retrigger kill
+0x0A u8[4] OUT: chosen hw slot (0..0x7F; >= 0x80 = failed)
```

* Melodic tones (class 0x00/0xC0): `TgMelodicVoiceAlloc` 0x4C034FF5 —
  up to 4 elements (tone-block halfword +4, bits 1/2/4/8). Each enabled
  element is staged into a 0xB4-byte staging record
  (0x500C9D58 + elem*0xB4) by `TgElemStageFresh` (first strike:
  velocity-zone select against the 3 zone thresholds) or
  `TgElemStageRestrike` (the part's cached previous entry from
  `TgPartElemLastGet`, byte 0x50009E48+part*8+idx*2, 0xFF = none).
  Pool bytes: ROM 0x4858710C rows [0..3] / [4..7].
* Drum kits (class 0x80): `TgDrumNoteOnStd` 0x4C03595F — up to 2
  layers, class-0x10 voices, pools ROM 0x48587114/15.
* Table-class kits (0x81..0x83): `TgDrumNoteOnTable` 0x4C035D21 —
  class-0x40 voices, pools ROM 0x48587118.
* After `TgSlotAllocate` fills +0x0A.., each staged 0xB4 record is
  copied over the LIVE lib voice record 0x500AF940 + slot*0xB4.

The TG **side** (chip) is chosen per element by `TgVoiceSideSelect`
0x4C02BED0: kit classes 1/2 force TG A (0x400), 3/4 force TG B (0x800);
melodic voices read the note's routing entry `*(rec+0x34)` (set by
`TgVoiceRoutePtrCalc` from the maincpu kit tables 0x48449DAA/0x48449DF8)
bits 10/11. `TgElemRequestFlags` folds 0x400/0x800 into policy bits
0x08/0x10.

## The voice-node layer

Every hardware slot (0..0x7F; < 0x40 = TG A, else TG B) has a 0x2C-byte
**node** at `0x500D1278 + slot*0x2C`:

```
+0x00/+0x04  class-ring links      +0x20 current list-array base
+0x08/+0x0C  order-list links      +0x24 current class
+0x10/+0x14  slot-ring links       +0x26 flags (bit0 free, bit1 fading,
+0x18/+0x1C  order base / class          bit2 sweep-release, bit7 held)
+0x28 note   +0x29 HW SLOT   +0x2A last polled level   +0x2B refade class
```

Nodes live on **class rings** inside *list arrays*
`{+0/+1 = per-side polyphony QUOTA (A/B), +2/+3 = per-side active
count, +4.. = class ring heads}`:

* per-part array: `*(0x500D0C64 + part*0x1C)` (a pointer)
* global active array: 0x500D1238 (heads 0x500D123C..)
* global free/retired array: 0x500D1258 — its class-6 head
  **0x500D1274 = the free-node first choice**

## THE steal priority

`TgSlotAllocate` 0x4C03AE07 looks up the element's pool descriptor
`0x485879D8 + pool*8 = {order-list ptr, +4 ring-entry class, +5 refade
class}` and calls `TgVoiceNodePick` 0x4C03ACC9 with the pool's ROM
**steal-order list** (0xFF-terminated; entry bit7 = search the GLOBAL
class ring, else the requesting part's own ring):

```
pool 0   -> 0x486D3844: 86 85 06 05 84 83 82 04 03 02 81 80 01 00
pool 1   -> 0x486D3853: (same minus the trailing 00)
pools 2-5, 8+ -> 0x486D3861: (minus 81 80 01 00)
pools 6,7     -> 0x486D386C: 86 85 06 05 84 83 82 04
```

So the steal order is: **retired/free (class 6) first, then releasing
voices (5..2), then held voices (1, 0) last — and at each priority the
global ring is raided before the part's own ring.** The pick itself:

* policy 0x18 (either side): the free head 0x500D1274 if non-empty,
  else the first non-empty ring in list order (no per-node predicate).
* policy 0x08 / 0x10 (must land on TG A / TG B): the same walk, but
  every candidate ring is scanned with `TgNodeScanSideA/B` so only
  nodes whose slot is on the required side qualify.
* policy 0x00: no allocation (the element fails, slot byte 0xFF).

On success the winning node is re-armed (+0x28 := note, +0x2A := 0xFF,
+0x2B := pool refade class, held flag per policy bit7, the slot's bit
set in the sustain mask 0x500D288C), moved to the part's array at the
pool's entry class, and inserted note-sorted into the order list.

**Per-part polyphony quotas:** if the chosen side's active count has
reached the array's quota (+0/+1), `TgVoiceMigrateFind` 0x4C03ADA1
walks the global rings in ROM order `0x486D383C = [06 05 02 04 03 01
00]` for a donor node on the *opposite* side and migrates it to the
global array — the mechanism that rebalances TG A/TG B load. The
displaced victim slot is notified via 0x4C00F824.

## Retire / fade (what refills the free ring)

`TgVoiceStatusSweep` 0x4C03AA86 polls the TGs 16 slots per pass
(rotating group counter 0x5000B210):

* command 0xFC08|group returns 16 "gone" bits, edged against the
  sustain mask 0x500D288C into 0x500D287C. A newly-gone, non-free node
  is retired: `TgVoiceNodeRetire` decrements the side-active count
  (never below the quota), moves the node to global-free class 6
  (head 0x500D1274) and clears it.
* surviving slots get their envelope level polled (cmd 0xFC02|slot<<4,
  `(x & 0x1FFF) >> 5`) into node+0x2A; a level < 0x80 with flag bit2
  triggers `TgVoiceNodeFadeKick` (flags |= 2, re-ring at class 6) —
  quiet releases become steal fodder early, loud ones get a grace pass
  via `TgVoiceNodeReleaseStep` (+0x2B refade class).

Key-off enters this layer through `TgVoiceNodeKeyOff` 0x4C03B0CD
(drop the held flag + sustain-mask bit, then the release step) — called
per slot by `TgPartKeyEvent` before `TgVoiceSlotService`.

## Hold/sustain + top-note behavior (the Part-52 pedal path)

`TgPartHoldQuery` 0x4C02E0F9 (d0 part, d1 note) at key-off:

* part flags bit6 clear -> returns 0xFE = "no hold, release now".
* else it scans the part's sounding voices for the HIGHEST note; if the
  released note IS the top note it promotes the next-highest (rewrites
  the remaining voices' class-0x3000 word with bit14 cleared via
  `TgVoiceRegWrite_entry`, updates the top-note byte
  0x500AD5A8+part*0x10C+0x26) and returns 0 = "hold-managed": the
  caller then only marks the key via `TgPartHoldMark` 0x4C02E2C7
  (recorded in the part's 0x500AD5A8 block; **no TG write happens at
  key-off under hold** — collection happens at pedal release).

## Pitch/level internals settled

* `TgPitchZoneFold` 0x4C02FB27: librec+0x0A := the zone pitch folded by
  +-0xC00 **octave steps** into the sample's mapped key window
  [desc+9<<8, (desc+0xA<<8)+0xFF] — the multisample octave fold.
* `TgPitchNoteResolve` 0x4C02FB7E: pitch16 = folded zone pitch +
  optional per-sample correction + part word (partrec+0x64) + master
  tune 0x500C075C + part offset resolve, clamped 0..0x7FFF.
* `TgPartPitchWordCalc` 0x4C02BF34: the part word = coarse tune<<8 +
  master 0x500C075E + (flags bit14: per-scale-degree microtuning table
  partrec+0x4A[note%12]) — **scale tuning is applied per note-on**.
* `TgLevelResolve` 0x4C02FBE3: 0..0x7F; mute/solo overrides from part
  state +0x1D, part-link borrows the linked part's level byte, else
  base level + velocity + expression.
* Drum pitch: the drum stagers call `TgPitchInitCalc_entry` with the
  kit zone's (often NULL) descriptor — the legacy 0x4280-const path of
  tg-pitch-pipeline.md enters through here, not through a special drum
  formula in the allocator.

## 2026-07-20 closure pass (static RE, all converted to source in
## kn7000_disassembly): programmers, list engine, and THE GLIDE CORRECTION

### Correction: the 0x500AD5A8 "hold mark" block is the MONO/PORTAMENTO state

The earlier reading of the +0x26.. fields as a damper-pedal mark list
(collected at pedal release) is **superseded by code**. The block
0x500AD5A8+part*0x10C carries the part's mono/portamento state:

* +0x26 current (top) note, +0x27 previous note;
* +0x28 glide tick period / +0x29 tick counter (-1 = idle);
* +0x2A step count / +0x2C step index;
* +0x30 and +0x38 SOFT-DOUBLE per-step pitch deltas;
* +0x40/+0x42 interpolated pitch offset halfwords, +0x46 curve base.

`TgPartGlidePlan` 0x4C02D79A (called under `TgPartHoldMark` when partrec
bit7 = portamento on) plans the ramp with soft-float double math
(constants 100.0/12.0/256.0/±5.0; runtime 0x4C0007E7/0x4C000856/
0x4C000879/0x4C000B1C/0x4C001629/0x4C0016AC/0x4C0019F2) against the
per-part portamento curve record 0x486D319C[partrec+6], then arms
`TgPartGlideTick` 0x4C02E5AD — the per-part periodic tick (invoked from
the part service loops at 0x4C02D2F8/0x4C02D552, gated on partrec bits
6+7). Mid-ramp the tick rewrites every part voice's class-0x2400 pitch
word (`TgPitchRuntimeCalc`) and class-0x3000 level word
(`TgVoiceLevelWordCalc` 0x4C0315D2, bit14 cleared); on the final step it
snaps the current note's (+0x26) voices and *releases the previous
note's (+0x27) voices* (`TgVoiceListReleaseByNote` + `TgVoiceNodeKeyOff`
+ `TgVoiceSlotService`). So partrec bit6 = mono/legato mode (the
top-note promotion in `TgPartHoldQuery` is mono note-priority), bit7 =
portamento. The actual damper-pedal timing story (Part 52) is a
separate mechanism — the sustain mask 0x500D288C + held-node flags —
and does NOT go through this block.

### The per-class note-on/key-off programmers (dispatch layer now closed)

Note-on (under `TgNoteOn`, dispatch on staged librec+2):

* bit2 (fresh, class 0x104/0x004) -> `TgElemNoteOnFresh` 0x4C033CB3:
  builds the COMPLETE shadow register image (pitch chain, level word,
  all four pitch/filter EG segments + amp EG, raw EG writes to both the
  even and odd companion register blocks) before gate-on. Every first
  strike lands here; `TgElemNoteOnStd` programs the bit1 RESTRIKES.
* else (drum 0x10 / table 0x40) -> `TgKitElemNoteOn` 0x4C013547, a
  near-twin that fetches tone params through the kit/table fetchers.
* kit classes 0x81..0x83 also fire a PCM one-shot layer:
  `TgNoteOnKitLayer` 0x4C03678F (stage 0x4C036602 + allocate
  0x4C0366D7, pool byte 0x83, then gate-on + immediate gate-off).

Key-off (under `TgVoiceSlotService`, class&0x7C):

* 0x10 drum -> `TgDrumKeyOffProgram` 0x4C00C0B1 (amp release from
  `TgDrumAmpReleaseCalc` 0x4C00AD48, curve ROM 0x486D2649 + key
  scaling), 0x40 table -> `TgTableKeyOffProgram` 0x4C0115AA
  (TgKeyOffAmpRelease(0)), else/restrike -> `TgElemKeyOffRelease`
  0x4C013F0F (key-off offset from the note's routing entry). All three
  end in the same `TgVoiceEgBurstWrite` 6-write release burst; the
  melodic fresh class (bit2) is only FLAG-marked here and released
  later via the dirty-release flush.

### The voice-list collect/release engine

`TgVoiceListBuild` 0x4C03B3B5 + 8 tiny wrappers (0x4C010047..0x4C010127)
are how every subsystem enumerates sounding voices: request = {flags,
match part<<8|note, mask} -> slot bytes 0xFF/0x80-terminated. flags
0x80 = collect-AND-release (`TgNodeRingReleaseWalk`: moves each match
to the releasing ring, marks pending bit11, follows the slot ring so
same-note stacked voices go together), 0x40 = skip-pending collect,
else plain collect; all-parts mode sweeps the 128-node pool
0x500D1278. Part order-ring heads live at 0x500D0C64+part*0x1C +4
(sounding) / +8 (releasing); +0xC is a 16-byte slot bitmask
(`TgPartSlotMaskBuild`/`TgNodePendingMark`/`TgPartPendingFlush`).
