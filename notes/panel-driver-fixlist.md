# KN7000 driver INPUT_PORTS fixlist

Compares the CURRENT `PORT_NAME` in `src/mame/matsushita/kn7000.cpp` `INPUT_PORTS_START(kn7000)`
(lines 922–1221, read this pass) against the authoritative `wf/panel-button-names.md`.
**Only mismatches are listed.**

`(IPT_UNUSED)` in the "current PORT_NAME" column = the bit is currently declared `IPT_UNUSED` (no
name at all). A "correct NAME" of `(firmware no-op)` / `(unused — no button)` means the bit *should*
be `IPT_UNUSED` — i.e. the driver currently gives a dead bit a bogus name.

NOTE: this supersedes the earlier `driver_fixlist.md`, which was generated against a stale
inactive-table build of the driver. The driver has since been hand-updated, so many bits are now
CORRECT and are absent here — e.g. SEG00–02 pads+genres, SEG02 0x40/0x80 (SOUND ARRANGER SET /
OFF-ON), SEG0E 0x10/0x20 (SUSTAIN / DIGITAL EFFECT), SEG08 0x08/0x10/0x20 (HELP/DISPLAY HOLD/EXIT),
SEG03 0x04 (AUTO PLAY CHORD OFF/ON), and the SEG04–07 mute matrix up through PART15-UP.

## A. Wrong name on a live button (mislabels a real, mapped function)

| SEG.bit | current PORT_NAME | correct NAME |
|---------|-------------------|--------------|
| SEG03.0x02 | APC / CHORD FINDER | APC MODE (AUTO PLAY CHORD MODE) |
| SEG03.0x08 | RIGHT1 OFF | LCD LEFT 1 (soft-key) — firmware fires RIGHT1 part-OFF |
| SEG03.0x10 | RIGHT2 OFF | LCD LEFT 2 (soft-key) — firmware fires RIGHT2 part-OFF |
| SEG03.0x20 | LEFT OFF | LCD LEFT 3 (soft-key) — firmware fires LEFT part-OFF |
| SEG03.0x40 | ACCOMP1 OFF | LCD LEFT 4 (soft-key) — firmware fires ACCOMP1 part-OFF |
| SEG03.0x80 | ACCOMP2 OFF | LCD LEFT 5 (soft-key) — firmware fires ACCOMP2 part-OFF |
| SEG08.0x01 | part18 ON | BASS — part ON (unmute) |
| SEG08.0x02 | part18 OFF | BASS — part OFF (mute) |
| SEG08.0x04 | OTHER PARTS & FR | OTHER PARTS/TR |

## B. Dead bit given a real name (should become IPT_UNUSED)

| SEG.bit | current PORT_NAME | correct NAME |
|---------|-------------------|--------------|
| SEG03.0x01 | INTRO & ENDING 1 | (unused — no button) |
| SEG09.0x80 | Part Mute Down p09 | (unused — no button) |
| SEG0A.0x01 | Part Mute Up p0A | (firmware no-op) |
| SEG0A.0x02 | Part Mute Down p0A | (firmware no-op) |
| SEG0A.0x04 | Part Mute Up p0B | (firmware no-op) |
| SEG0A.0x08 | Part Mute Down p0B | (firmware no-op) |
| SEG0A.0x10 | Part Mute Up p0C | (firmware no-op) |
| SEG0A.0x20 | Part Mute Down p0C | (firmware no-op) |
| SEG0A.0x40 | Part Mute Up p0D | (firmware no-op) |
| SEG0A.0x80 | Part Mute Down p0D | (firmware no-op) |
| SEG0B.0x01 | Part Mute Up p0E | (firmware no-op) |
| SEG0B.0x02 | Part Mute Down p0E | (firmware no-op) |
| SEG0B.0x04 | Part Mute Up p0F | (firmware no-op) |
| SEG0B.0x08 | Part Mute Down p0F | (firmware no-op) |
| SEG0B.0x10 | Part Mute Up p18 | (firmware no-op) |
| SEG0B.0x20 | Part Mute Down p18 | (firmware no-op) |
| SEG0B.0x40 | Fn Key 20A0 | (firmware no-op) |
| SEG0B.0x80 | Part Mute Up p17 | (firmware no-op) |
| SEG0C.0x40 | Fn Toggle 0B | (unused — no button) |
| SEG0D.0x40 | Fn 2016 | (unused — no button) |
| SEG0D.0x80 | Fn Toggle 0A | (unused — no button) |
| SEG0E.0x40 | Fn Key 20AE | (unused — no button) |
| SEG0F.0x80 | Fn 2012 | (unused — no button) |
| SEG14.0x04 | Sound Select 0F | (firmware no-op) |
| SEG14.0x08 | Sound Select 06 | (firmware no-op) |
| SEG15.0x08 | Sound Select 05 | (unused — no button) |
| SEG16.0x01 | Fn 1005 (DIAL?) | (unused — no button) |
| SEG17.0x01 | Fn 1004 (DATA?) | (unused — no button) |
| SEG18.0x01 | Fn 1009 | (unused — no button) |
| SEG19.0x01 | Fn 1010 | (unused — no button) |
| SEG1A.0x01 | Fn 1011 | (firmware no-op) |
| SEG20.0x01 | Fn 1020 | (unused — no button) |

## C. Real button dropped as IPT_UNUSED (should be bound + named)

| SEG.bit | current PORT_NAME | correct NAME |
|---------|-------------------|--------------|
| SEG07.0x20 | (IPT_UNUSED) | PART15 MUTE DOWN (part OFF) |
| SEG07.0x40 | (IPT_UNUSED) | PART16 MUTE UP (part ON) |
| SEG07.0x80 | (IPT_UNUSED) | PART16 MUTE DOWN (part OFF) |
| SEG12.0x10 | (IPT_UNUSED) | ev2040 mode button (unresolved — name TBD; see needs_emulator.md) |
| SEG12.0x20 | (IPT_UNUSED) | ev2040 mode button (unresolved — name TBD) |
| SEG13.0x10 | (IPT_UNUSED) | GLOBAL EFFECT cluster (unresolved: CHORUS/DIGITAL EFFECT/MULTI EFFECT) |
| SEG13.0x20 | (IPT_UNUSED) | GLOBAL EFFECT cluster (unresolved) |
| SEG15.0x01 | (IPT_UNUSED) | ev2040 mode button (unresolved — name TBD) |
| SEG15.0x02 | (IPT_UNUSED) | unresolved (ev20AE/0033) |
| SEG15.0x10 | (IPT_UNUSED) | PART EFFECT cluster (unresolved: SUSTAIN/DIGITAL EFFECT/CHORUS/MULTI) |
| SEG15.0x20 | (IPT_UNUSED) | PART EFFECT cluster (unresolved) |
| SEG15.0x40 | (IPT_UNUSED) | PART EFFECT cluster (unresolved) |
| SEG15.0x80 | (IPT_UNUSED) | PART EFFECT cluster (unresolved) |

## D. Cosmetic wording (same button, tighten the label)

| SEG.bit | current PORT_NAME | correct NAME |
|---------|-------------------|--------------|
| SEG01.0x02 | PERFORMANCE PAD 5 | PERFORMANCE PADS — PAD 5 (SOLO) |
| SEG02.0x02 | PERFORMANCE PAD 6 | PERFORMANCE PADS — PAD 6 (SOLO) |
| SEG02.0x20 | RHYTHM COMPOSER MEMORY | MEMORY (rhythm genre 15) |
| SEG0D.0x04 | SOUND SOUND EXPLORER | SOUND EXPLORER (drop the doubled "SOUND") |
| SEG12.0x40 | PROGRAM MENU | PROGRAM MENUS |

## E. Confidence caveat (name OK, add soft-key note)

The driver's firmware-part name is acceptable but these bits are the ON-mirror of the SEG03
LCD-LEFT column and are actually the context-dependent LCD-RIGHT soft-keys (verify_3 downgraded
them HIGH→MED). No rename strictly required — add an "LCD RIGHT soft-key (unresolved)" comment.

| SEG.bit | current PORT_NAME | correct NAME |
|---------|-------------------|--------------|
| SEG0F.0x04 | RIGHT1 ON | RIGHT1 part-ON (physical: LCD RIGHT soft-key, unresolved) |
| SEG0F.0x08 | RIGHT2 ON | RIGHT2 part-ON (physical: LCD RIGHT soft-key, unresolved) |
| SEG0F.0x10 | LEFT ON | LEFT part-ON (physical: LCD RIGHT soft-key, unresolved) |
| SEG0F.0x20 | ACCOMP1 ON | ACCOMP1 part-ON (physical: LCD RIGHT soft-key, unresolved) |
| SEG0F.0x40 | ACCOMP2 ON | ACCOMP2 part-ON (physical: LCD RIGHT soft-key, unresolved) |

## Not applicable / verified consistent (no fix)

- SEG04–07 mute matrix: driver "MUTE PART N ON/OFF" ≡ authoritative "PARTN MUTE UP/DOWN"
  (ON = UP = unmute = ev2001; OFF = DOWN = mute = ev2000). Bit assignment verified un-swapped; only
  the three trailing PART15-DOWN / PART16 bits are missing (section C).
- SEG1B–SEG1F are outside the 224-bit decoded set (no wire path); the driver's all-`IPT_UNUSED`
  declaration for them is correct.

## Count

- Substantive fixes (A + B + C): **55** — A: 9, B: 33, C: 13
- Cosmetic (D): 5 · Caveat (E): 5
- **Total mismatches: 65 of the 162 declared/keyboard bits**
