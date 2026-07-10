# The KN7000's real panel is bank A (0x48614978), not bank B — the whole map was wrong

## The discovery (2026-07-10)

The firmware has TWO panel button-descriptor tables (button -> event maps), selected by
a flag: dispatch 0x484ADB59 -> selector 0x484ABAFD returns *(0x5006BE94); **==0 uses
bank A 0x48614978, !=0 uses bank B 0x486149FC** (disassembled). The flag is set by
0x484ABB06 from the TG-present strap probe 0x484D7713: **TG present -> flag 0 -> bank A;
TG absent -> flag 1 -> bank B.**

The KN5000/KN6000/KN7000 share this codebase; the two banks are two models' panels.
**Bank A IS the KN7000, bank B is a sibling without SD:**
- Bank A SEG1D = the six SD front-panel switches (events 0x20B5..0x20BA), SEG1E/1F valid.
- Bank B has ZERO SD-switch events; its SEG1E/1F pointers are garbage (0x00702068 / 0x11).
- The SD card is a KN7000-only feature -> bank A = KN7000.

The real KN7000 has tone generators -> TG present -> bank A. So bank A is correct.

## Why the driver's panel was wrong

For a long time the driver FALSELY reported TG absent (sound was opt-in), so the
emulation ran bank B. The panel map (button PORT_NAMEs, the layout bindings, the SOUND
GROUP list, the DISK/SD navigation) was all built + "confirmed" against bank B -- a
DIFFERENT model. It was internally self-consistent, so buttons "worked" in emulation,
but it modeled the wrong sibling. When sound was made default-on (report TG present =
correct), the firmware switched to bank A (the real KN7000) and the mismatch surfaced:
the SOUND buttons misbehave, DISK moved, and placeholder names ("Fn 2016") are exposed.

## Confirmed bank-A positions (runtime-verified)

- SEG14.b3 -> event 0x2004 arg 0x064F = opens **"SOUND - RIGHT 1: SAX & WOODWIND"**
  (Sop Sax Soloist / Alto Sax / Flute...). SCREENSHOT-CONFIRMED. (The driver had SAX
  mislabelled at SEG0D.b0.)
- DISK MENU = SEG0D.b6 (event 0x2016), not SEG12.b7 (which is 0x2010/603 in bank A).

## SOUND GROUP under bank A (event 0x2004; arg-high -> SoundGroupNameTable @0x48131570)

| SEG.bit | arg  | category            |
|---------|------|---------------------|
| SEG10.b4| 004F | PIANO               |
| SEG0F.b4| 014F | GUITAR              |
| SEG0E.b4| 024F | MALLET&ORCH PERC    |
| SEG0D.b4| 034F | WORLD               |
| SEG0C.b4| 044F | STRINGS & VOCAL     |
| SEG15.b3| 0543 | BRASS               |
| SEG14.b3| 064F | SAX & WOODWIND      |
| SEG13.b3| 074F | ORGAN&ACCORDION     |
| SEG12.b3| 0843 | SOUND EXPLORER      |
| SEG10.b5| 0941 | DIGITAL DRAWBAR     |
| SEG0F.b5| 0A41 | ORGAN TABS          |
| SEG0E.b5| 0B4F | ACCORD REGISTER     |
| SEG0D.b5| 0C4F | PAD                 |
| SEG0C.b5| 0D4F | SYNTH               |
| SEG15.b2| 0E4F | BASS                |
| SEG14.b2| 0F40 | DRUM KITS           |
| SEG13.b2| 1042 | MEMORY              |
| SEG12.b2| 1144 | EW EXPANSION        |

## Plan: rebuild the driver panel for bank A

Rewrite every SEG port PORT_NAME + the layout inputtag/inputmask bindings to bank A's
functions. Event families (all from the bank-A dump 0x48614978):
- 0x2004 SOUND GROUP (table above), 0x2005 RHYTHM GROUP (SEG01-02), 0x2000/0x2001 sound
  registration + PMEM select (SEG00, SEG05, SEG08-0B), 0x2020-0x2033 transport/fill/
  intro, 0x2010-0x2016/0x2040 menus (DISK 0x2016), 0x2060-0x2069/0x2008/0x2009 part &
  balance, 0x2080-0x20BE effects/mutes/chord, 0x1000-0x1020 (SEG16-20) OTHER PART/HELP/
  CONTRAST/PAGE/DISPLAY HOLD/EXIT/MUTE/SD.
Workflow wf (decode each event->function name) feeds the rewrite; anchors above are
runtime-verified.

## Which model is bank B? (2026-07-10)

The bank is chosen by the model/TG strap 0x98070000 via probe 0x484D7713: it returns 3
when bit1 is CLEAR, 2 when bit1 set/bit2 clear, 1 when both set; the bank selector treats
"==3" as bank B, "1 or 2" as bank A. So on real KN7000 hardware (TG present, bit1 set) the
panel is ALWAYS bank A; bank B is the strap's "no-TG / other-variant" state and is never
selected on a real KN7000.

Checked Felipe's guess (KN6000/KN6500): interleaved the KN6000 program ROM and searched
for bank B's exact SEG0C descriptor (ev2004/arg0C4F, bytes 0420 70 00 01 4f 0c) -> **0
matches**, so bank B is NOT the KN6000's panel. (Note: the KN6000 firmware DOES contain
0x20B5-family bytes, so the KN6000/6500 likely have their own card slot -- SD isn't
KN7000-exclusive after all; bank A = KN7000 still stands, anchored by the TG-present strap
+ the screenshot-confirmed SAX@SEG14.b3.) Conclusion: bank B is a no-TG service/variant
panel baked into the shared codebase, not a specific sibling we can name from the KN7000
firmware alone.
