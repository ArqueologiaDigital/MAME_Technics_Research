# ev2004 SOUND-CATEGORY names (arg-high -> category)

**Event 0x2004 = sound-category (SOUND GROUP) selector.**
The 16-bit event arg's **high byte is the category index**; it indexes directly into
`SoundGroupNameTable @ 0x48131570` (TABLE rom, file offset 0x131570 in
`work/kn7000_table.rom`; base 0x48000000, so 0x48131570 - 0x48000000 = 0x131570).

The table is a fixed **16-byte-wide** array of space-padded ASCII names (18 real
entries, then the same 18 repeated, then `SOUNDGROUP___036..063` placeholders).
Entry N lives at file offset 0x131570 + N*0x10. Names below are the exact ROM
spelling (trimmed of padding).

## arg-high -> category name

| arg-high | table idx | category name (ROM)  | ev2004 arg | panel button | source |
|:--------:|:---------:|----------------------|:----------:|:------------:|--------|
| 0x00 | 0  | PIANO            | 004F | SEG0C.0x01 | table@0x131570; seg_event_map |
| 0x01 | 1  | GUITAR           | 014F | SEG0C.0x02 | table@0x131580; seg_event_map |
| 0x02 | 2  | MALLET&ORCH PERC | 024F | SEG0C.0x04 | table@0x131590; seg_event_map |
| 0x03 | 3  | WORLD            | 034F | SEG0C.0x08 | table@0x1315A0; seg_event_map |
| 0x04 | 4  | STRINGS & VOCAL  | 044F | SEG0C.0x10 | table@0x1315B0; seg_event_map |
| 0x05 | 5  | BRASS            | 0543 | SEG0C.0x20 | table@0x1315C0; seg_event_map |
| 0x06 | 6  | SAX & WOODWIND   | 064F | SEG0D.0x01 | table@0x1315D0; seg_event_map |
| 0x07 | 7  | ORGAN&ACCORDION  | 074F | SEG0D.0x02 | table@0x1315E0; seg_event_map |
| 0x08 | 8  | SOUND EXPLORER   | 084F | SEG0D.0x04 | table@0x1315F0; seg_event_map |
| 0x09 | 9  | DIGITAL DRAWBAR  | 094F | SEG0D.0x08 | table@0x131600; seg_event_map |
| 0x0A | 10 | ORGAN TABS       | 0A40 | SEG0D.0x10 | table@0x131610; seg_event_map |
| 0x0B | 11 | ACCORD REGISTER  | 0B42 | SEG0D.0x20 | table@0x131620; seg_event_map |
| 0x0C | 12 | PAD              | 0C4F | SEG0E.0x01 | table@0x131630; seg_event_map |
| 0x0D | 13 | SYNTH            | 0D4F | SEG0E.0x02 | table@0x131640; seg_event_map |
| 0x0E | 14 | BASS             | 0E4F | SEG0E.0x04 | table@0x131650; seg_event_map |
| 0x0F | 15 | DRUM KITS        | 0F4F | SEG0E.0x08 | table@0x131660; seg_event_map |
| 0x10 | 16 | MEMORY           | (not via ev2004) | SEG0E.0x10 | table@0x131670 |
| 0x11 | 17 | EW EXPANSION     | (not via ev2004) | SEG0E.0x20 | table@0x131680 |

## Notes / caveats

- **Only arg-high 0x00-0x0F are emitted as ev2004** by the panel (the 16 buttons
  SEG0C.b0-b5, SEG0D.b0-b5, SEG0E.b0-b3 per seg_event_map.txt). Table indices
  **0x10 MEMORY** and **0x11 EW EXPANSION** exist in the name table and are the
  physical SEG0E.0x10 / SEG0E.0x20 buttons (per gen_lay.py SG[]), but they do NOT
  appear as ev2004 rows in seg_event_map.txt — they are dispatched by a different
  path, so their ev2004 arg (if any) is not established here.
- The **arg low byte** (0x4F for most, but 0x43 BRASS / 0x40 ORGAN TABS /
  0x42 ACCORD REGISTER) is NOT part of the category index; it is a per-category
  payload (default/last sound within the group). Category selection = high byte only.
- **Double-confirmation.** Two independent derivations agree on all 16:
  1. arg-high -> SoundGroupNameTable[arg-high]  (this dump).
  2. The layout's SOUND GROUP list in `kn7000_mame/tools/gen_lay.py` (SG[], L303-306,
     "SNAPSHOT-CONFIRMED SEG0C.b0=PIANO, b1=GUITAR"), which maps the SAME physical
     SEG bits to the SAME names in the SAME order.
  The empirical anchor from the task (SEG0C.0x01 = PIANO = arg 004F) sits at
  index 0 and matches.
- ROM spelling differs cosmetically from the silkscreen/layout labels
  (ROM "MALLET&ORCH PERC" / "ORGAN&ACCORDION" / "ACCORD REGISTER"
   vs layout "MALLET & ORCH PERC" / "ORGAN & ACCORDION" / "ACCORDION REGISTER").
  The ROM spelling above is authoritative for what the firmware displays.

## Sources
- Name table bytes: `work/kn7000_table.rom` @ file offset 0x131570 (base 0x48000000),
  16-byte stride, hexdump verified.
- ev2004 args: scratchpad `seg_event_map.txt` (grep ev2004, 16 rows).
- Physical button<->name cross-check: `kn7000_mame/tools/gen_lay.py` SG[] (L303-306);
  `kn7000_mame/notes/panel-descriptor-map.md` ("SOUND GROUP resolved (tick 3):
  event 0x2004 arg = category index ... SoundGroupNameTable @ 0x48131570, 18x16-byte").
