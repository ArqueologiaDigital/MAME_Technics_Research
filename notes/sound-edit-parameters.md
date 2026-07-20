# SOUND-screen edit parameters, as the firmware actually stores them

> Static RE, 2026-07-20, from the library window (0x4C......) of the
> KN7000 program flash. Every function named here is converted to real
> MN10300 assembly in the sibling `kn7000_disassembly` repo and the whole
> image still rebuilds byte-identically, so the offsets below are read off
> code that is proven to be the shipped code.
>
> Companion documents: `notes/sound-gui-inventory.md` (what the screens
> look like, from the user's manual) and `notes/tg-envelope-sweep-results.md`
> (the envelope parameters we decoded live against the tone generator).

The goal of this note is the join between the two: **which on-screen row
corresponds to which byte in RAM, and through which API.**

---

## 1. DIGITAL DRAWBAR (manual p36) — COMPLETE

Path: PART SELECT + the DIGITAL DRAWBAR sound-group button. The screen
draws nine drawbars (16', 5 1/3', 8', 4', 2 2/3', 2', 1 3/5', 1 1/3', 1'),
a `<Jazz Drawbars>`/`<Rock Drawbars>` type button, two PERCUSSIVE TONE
buttons (2 2/3' and 4') and four value rows: DRAWBAR ATTACK TIME,
RELEASE TIME, PERCUSSIVE TONE DECAY, LEVEL.

### The record

Per part, 0x1C bytes at **`0x500082C8 + part*0x1C`**:

| offset | contents |
|---|---|
| +0x00, +0x02, +0x04 | three **12-bit registration words**; each packs three 4-bit drawbar levels |
| +0x06 | **PERCUSSIVE TONE**, 2 bits (the 2 2/3' and 4' buttons) |
| +0x08 | **DRAWBAR ATTACK TIME** (signed offset) |
| +0x09 | **RELEASE TIME** (signed offset) |
| +0x0A | **PERCUSSIVE TONE DECAY** (signed offset) |
| +0x0B | **PERCUSSIVE TONE LEVEL** (signed offset) |
| +0x0C, +0x0E, +0x10 | level words derived from the registration |
| +0x19 | drawbar **TYPE** flag (Jazz / Rock), 0 or 1 |

Nine levels x 4 bits = 36 bits = three 12-bit words. They are not stored
in display order; the ROM scatter table **0x486D10A0** (3 x 3 bytes)
supplies the mapping:

```
word0 nibbles (bits 0-3, 4-7, 8-11) -> display slots 0, 1, 6
word1                               -> display slots 3, 5, 8
word2                               -> display slots 2, 4, 7
```

### The APIs

| function (lib) | what it does |
|---|---|
| `TgPartDrawbarPairSet1` 0x4C00A5C7 | drawbars 1+2 (16', 5 1/3') |
| `TgPartDrawbarPairSet2` 0x4C00A5FB | drawbars 3+4 (8', 4') |
| `TgPartDrawbarPairSet3` 0x4C00A653 | drawbars 5+6 (2 2/3', 2') |
| `TgPartDrawbarPairSet4` 0x4C00A6AB | drawbars 7+8 (1 3/5', 1 1/3') |
| `TgPartDrawbarPairSet5` 0x4C00A702 | drawbar 9 (1') **+ PERCUSSIVE TONE** |
| `TgPartDrawbarAtkRlsSet` 0x4C00A74D | ATTACK TIME / RELEASE TIME |
| `TgPartDrawbarPercSet` 0x4C00A786 | PERCUSSIVE TONE DECAY / LEVEL |
| `TgPartDrawbarTypeSet/Clear/Get` 0x4C00A2F1 / 0x4C00A307 / 0x4C00A31C | the Jazz/Rock type flag |
| `TgPartDrawbarOffsetsReset` 0x4C00A594 | zero the four offset bytes |
| `TgPartDrawbarCapture` 0x4C00A253 | load the registration **out of** the currently selected sound |
| `TgPartDrawbarRegExport` 0x4C00A330 | pack the record back out as 8 display bytes |
| `TgPartDrawbarOffsetApply` 0x4C00A7E5 | push everything onto the synthesis engine |

Every setter takes `(d0 = part, d1 = a packed pair of 4-bit values)` and
ends by calling `TgPartDrawbarUnitEnable_entry` + `TgPartDrawbarLevelsDerive_entry`,
so the screen never has to ask for a refresh.

The four ATTACK/RELEASE/DECAY/LEVEL rows are *indices*, not values: the
setters look the nibble up in the signed ladder at **0x48586E84**
(`0,1,2,...,7,-8,-7,...,-1` as s16) and scale it (<<2, *2, <<2, <<3).

### How it reaches the tone generator

`TgPartDrawbarOffsetApply` (0x4C00A7E5) writes the four registration
words straight into aux mod-unit fields +0x04/+0x05 of the part's SOUND
EDIT shadow (see `notes/`-adjacent RE in kn7000_disassembly's
`kn7000_manual.sym`), and then **adds** the four parameter bytes to
whatever the sound already had:

| unit | field | offset byte | clamp |
|---|---|---|---|
| 0..2 (sustained footages) | aux +0x28 | +0x0A perc decay | 0..100 |
| 0..2 | aux +0x2E | +0x0B perc level | 0..100 |
| 3 (percussion tap) | aux +0x19 | +0x08 attack | 0..0x7F |
| 3 | aux +0x2A, +0x2C | +0x09 release | 0..100 |

The clamp is `TgEditOffsetAddClamp` (0x4C00A7BC / entry 0x4C00A7BE),
`clamp((u8)current + (s8)delta, min, max)` — the shared applier behind
every offset-style edit parameter in the firmware, which is where the
manual's recurring "±100" ranges come from (max = 0x64).

**The consequence worth remembering:** the four drawbar value rows are a
*differential* layer. They do not describe the sound; they lean on it.
The same +12 on ATTACK TIME does something different depending on which
organ patch is loaded.

---

## 2. LFO EDIT (manual p174) — STRUCTURE MAPPED, ROW NAMES OPEN

The manual says LFO EDIT offers **12 LFO groups** and four destination
pages (PITCH MODULATION = vibrato, AMP = tremolo, FILTER = wah-wah,
PAN = auto pan). The firmware matches that exactly.

- ROM table **0x486D2ED5**, stride **0x27**, twelve records.
- Each record carries four `(speed, depth, ...)` triples at +0x00,
  +0x03, +0x06, +0x09 — one per destination page. Most groups only use
  one or two of them (group 4 uses the first two, group 6 only the
  third, group 9 only the fourth, group 8 only the +0x18 tail block).
- The group for a part is the **low nibble of byte +0x44 of the part's
  tone descriptor** (`0x500CE404 + part*0x130` -> pointer -> +0x44).
- `TgPartEditLfoGroupLoad` (0x4C00CF8B) validates 0..0x0B and jumps
  through the table **0x48586F28** to one of **eight** unpackers
  (`TgPartEditLfoLoadA`..`H`), because the groups do not share a layout.
- Each unpacker writes an **8-byte parameter block at +0x45** of the
  per-part SOUND EDIT record **`0x500C0784 + (part-0x10)*0x2C8`**.
- `TgPartEditLfoFlagSet` (0x4C00D047) toggles **bit7 of +0x44** of that
  same record. The LFO EDIT page has two on/off toggles (KEYSYNC and
  CONNECTION) and we have not settled which one this is.

**Not settled:** which of the eight block bytes is SPEED / PHASE / WAVE /
DELAY / DEPTH / TOUCH. Sample values (group 0) are `0x0F, 0x19, 0x0A,
0x00, 0x64, -, 0x00, 0x00`; the 0x64 looks like a full-scale DEPTH and
the 0x0A like a DELAY, but that is a guess until a live session drives
the screen and watches the block.

---

## 3. The SOUND EDIT record itself

`0x500C0784 + (part-0x10)*0x2C8`, 712 bytes, allocated for parts
**0x10, 0x11, 0x12 only** — the three editable parts, matching the guard
in `TgPartLocalEditActivate` (0x4C00CB3F). Known so far:

| offset | contents |
|---|---|
| +0x44 | LFO block header; bit7 = an on/off toggle (`TgPartEditLfoFlagSet`) |
| +0x45..+0x4C | the 8-byte LFO parameter block |
| +0x4D, +0x4E, +0x4F, +0x51 | flag bytes: bit7 mirrors a single bit of the part-setting record, bits0-6 mirror a whole byte of it (table below) |
| +0x52, +0x53 | whole bytes copied straight from the part-setting record |

### The flag refreshers — CONVERTED, 2026-07-20

The family at **0x4C00EDE4..0x4C00F12A** turns out to be **NINE**
functions, not twelve (the earlier count was a guess from a call-target
scan; rescanning the prologues gives nine). All nine are converted and
byte-verified in `kn7000_disassembly`. They share one shape:

```c
void refresh(u8 part) {
    if (part < 0x10 || part > 0x12) return;          /* editable parts only */
    if (!TgPartLocalEditActive(part)) return;        /* 0x4C00C6BF */
    u8  *dst = SOUND_EDIT(part) + FIELD;             /* 0x500C0784+(part-0x10)*0x2C8 */
    u8  *src = (u8 *)(0x500B5340 + part*0x54C);      /* part-setting record */
    ...one bit, or one byte, copied...
}
```

| function (lib CPU) | SOUND EDIT field | source in `0x500B5340 + part*0x54C` |
|---|---|---|
| `TgSoundEditFlag4DBit7Refresh` 0x4C00EDE4 | +0x4D bit7 | halfword +0x00, bit7 |
| `TgSoundEditFlag4DLowRefresh`  0x4C00EE41 | +0x4D bits0-6 | byte +0x06 |
| `TgSoundEditFlag4EBit7Refresh` 0x4C00EE9A | +0x4E bit7 | halfword +0x00, bit1 |
| `TgSoundEditFlag4ELowRefresh`  0x4C00EEF7 | +0x4E bits0-6 | byte +0x15 |
| `TgSoundEditFlag4FBit7Refresh` 0x4C00EF4B | +0x4F bit7 | halfword +0x00, bit6 |
| `TgSoundEditFlag51Bit7Refresh` 0x4C00EFA8 | +0x51 bit7 | **composite** (below) |
| `TgSoundEditFlag51LowRefresh`  0x4C00F04E | +0x51 bits0-6 | byte +0x0E |
| `TgSoundEditByte52Refresh`     0x4C00F0A2 | +0x52 (whole byte) | byte +0x0F |
| `TgSoundEditByte53Refresh`     0x4C00F0E6 | +0x53 (whole byte) | byte +0x14 |

Eight of the nine are a straight mirror. The odd one out,
`TgSoundEditFlag51Bit7Refresh`, computes its bit from three places in
the part-setting record: a 2-bit mode field (halfword +0x62, bits11-12),
bit3 of halfword +0x00, the group bits14-15 of halfword +0x62, and byte
+0x14 — set when the mode is 0 or 3 and byte +0x14 is non-zero, or when
the mode is 1/2 and the +0x62 group bits are set. That is the shape of a
"this part actually has an effect send / is actually audible" derivation
rather than a plain copy, so its user-facing name is left open until a
live session can watch it change.

What the four flag bytes *mean* on the screen is still open — the six
low-bit sources (+0x06, +0x15, +0x0E, +0x0F, +0x14) are single-byte
part-setting fields, so a live session that moves one SOUND EDIT row at
a time and diffs `0x500B5340 + part*0x54C` will name them in one pass.

---

## 4. What a live session could do with this

Everything above is a plain RAM write plus one API call, so a future
live session can drive SOUND EDIT programmatically instead of clicking:

- read `0x500082C8 + part*0x1C` before and after a drawbar move to
  confirm the nibble mapping on real screen input;
- set a drawbar registration directly and check the LCD redraws;
- watch `0x500C0784 + (part-0x10)*0x2C8 + 0x45` while stepping the LFO
  EDIT rows — that is the cheapest way to finish section 2.
