# KN7000 panel button → normSeg.bit → function → LED map

Derived by static RE of the program ROM (workflow kn7000-panel-map: switch-class,
wire-norm, panel-test, descriptor agents, cross-checked against the empirical
probe bindings in panel-matrix-service-manual.md). This is the map used to bind
control-panel buttons in the MAME layout. `*` = also probe-verified on-screen.

## The three key relations (all statically proven)

1. **Switch/LED index:** `switch# = normSeg*8 + bit` (normSeg = switch#>>3,
   bit = switch#&7). Verified at the panel-test indexer 0x484A0CB0/0D07.
2. **`PanelSwitchClassTable` @0x4860C9F4**: 2-byte record per switch# at
   `0x4860C9F4 + 2*(normSeg*8+bit)` = `{byte0 = LED group, byte1 = LED column bit}`.
   `byte0` ≥ 0xF0 → special multi-LED / no-LED (keyboard keys). `byte0` indexes LED
   register-map `0x48615058[] = c0 c1 c2 c3 c4 c5 c6 c7 00 01 02 03 04 05 08 09 0a
   0b 0c 0d ff` to pick the hardware CM-row LED register; `byte1` = column bit.
3. **`PanelWireNormTable` @0x486135A0** (bank A = KN7000, flag @0x5006BE94 = 0):
   `wireIndex = ((ADDR&0xC0)>>1)|(ADDR&0x1F)`, `normSeg = table[wireIndex]`. ADDR is
   the panel-serial frame's first byte. grp0 ADDR 0x00-0x09→normSeg 0x0C-0x15,
   0x10→0x1A, 0x17→0x20; grp3 ADDR 0xC0-0xCB→normSeg 0x00-0x0B, 0xD0-0xD3→0x16-0x19.
   (The board/SEG/SW → ADDR half lives in the undumped panel sub-CPU; known
   empirically from press anchors.)

## Descriptor format (`PanelButtonDispatch` 0x484ADB59)
Per-normSeg array of 12-byte entries (FFFFFFFF-terminated), ptr table A @0x48614978:
`+0..1 event(u16 LE)`, `+4 bitmask`, `+5 bit#`, `+6 gate(hi=predicate class, lo=param)`,
`+7 arg`, `+8 dispatch type 0..4`. Posted msg = `0x00700000|event`, with type prefixes.
Mute/part family: `0x2001`=part ON, `0x2000`=part OFF, arg = part index into
PartNameTable 0x485FDE70: `00-0F`=PART1-16, `10`=RIGHT1, `11`=RIGHT2, `12`=LEFT,
`13-17`=ACCOMP1-5, `18`=BASS, `19`=DRUM1, `1A`=DRUM2, `1B`=CHORD.
`0x2005`=RHYTHM genre (name via RhythmGenreNameTable, genre=(arg+7)%16).
`0x2004`/`0x2040`/`0x2009`/`0x2010`=SOUND-category / screen / menu families.

## normSeg.bit → function  (WIRED in kn7000.lay unless noted)
```
SEG00  b4 BALLAD  b6 8&16BEAT/BALLROOM  b7 MOVIE&SHOW      (0x2000/2020-22 genre, mode-gated)
SEG01  b2 ENTERTAINER b3 ORGANIST b4 60s&70s b5 MODERN DANCE b6 SOUL&R&B b7 COUNTRY&WESTERN
SEG02  b1 LATIN&WORLD b2 MARCH&WALTZ b4 CUSTOM b5 MEMORY  b6 SOUND ARRANGER*  (0x2005 genre)
SEG03  b1 APC SELECT*  b2/b4 INTRO&ENDING  b3/b5/b6 VARIATION/MSA  b7 start/synchro grp
SEG04  b0/b2/b4 VARIATION/MSA   b1/b3 (20A3/20A4 ?)   b5/b6/b7 FILL/FADE
SEG05  b1 (2040/04 sound cat)  b4/b5 PART1 on/off  b6/b7 PART2 on/off  [MUTE col1-2] WIRED
SEG06  b0/b2/b4 FILL/FADE  b1/b3/b5 arranger  b6 sound cat  b7 (20B4 ?)
SEG07  b0/b2 sound cat  b1/b3/b4 (20A7-A9 ?)                 (only 5 entries)
SEG08  PART3-6 on/off pairs (b0..b7)                          [MUTE col3-6] WIRED
SEG09  PART7-10 on/off pairs                                  [MUTE col7-10] WIRED
SEG0A  PART11-14 on/off pairs                                 [MUTE col11-14] WIRED
SEG0B  b0/b1 PART15  b2/b3 PART16  b4/b5 BASS on/off  b7 ACCOMP5   [MUTE col15-16] WIRED
SEG0C  b0 PIANO* b1 GUITAR* b2 MALLET&ORCH PERC* b3 WORLD* b4 STRINGS&VOCAL* b5 BRASS*   WIRED
SEG0D  b0 SAX&WOODWIND* b1 ORGAN&ACCORDION* b2 SOUND EXPLORER* b3 DIGITAL DRAWBAR*
       b4 ORGAN TABS* b5 ACCORDION REGISTER*                                            WIRED
SEG0E  b0 PAD* b1 SYNTH* b2 BASS* b3 DRUM KITS*                                          WIRED
SEG0F  b0 ONE TOUCH PLAY(alt)  b1 FADE  b6/b7 MENU/screen        (b2/b3 20AA/2060 ?)
SEG10  b0 ONE TOUCH PLAY*  b1 FADE  b6 MENU  b7 screen           WIRED(b0)
SEG11  b0 FADE IN*  b1 FADE OUT*  b4 PART-SELECT RIGHT1  b5 PART-SELECT RIGHT2  b6/b7 MENU
SEG12  b0 ACCOMP1/part-select  b1 TRANSPOSE  b6 PROGRAM MENUS*  b7 DISK MENU*   WIRED(b6,b7)
SEG13  b0 TRANSPOSE down*  b1 TRANSPOSE up*  b2 OCTAVE-*  b3 OCTAVE+*  b6/b7 screen  WIRED(b0,b1)
```

## Still unresolved / next
- LCD soft-keys (5 L + 5 R), OTHER PART&FR, HELP, CONTRAST±, PAGE±, DISPLAY HOLD,
  EXIT: not clearly in SEG00-13; likely normSeg 0x14-0x20 (grp3 ADDR 0xD0-0xD7) — the
  descriptor agent stopped at SEG13. Decode SEG14-20 next.
- Several `0x20Ax`/`0x2060-69` events (transport/pad/synchro groups) are unlabeled (no
  probe screen) — resolvable via the service PANEL SW&LED test (dynamic track) or by
  matching gate/predicate classes.
- The boot service-mode key-combo entry (to run the panel test live) is still open —
  the check does NOT read the voice FIFO (that feeds only the TG); see
  service-diagnostic-mode.md.
- LED modeling: byte0/byte1 give the matrix cell per button; drive .lay LEDs from
  firmware LED state once a writer is traced (panel-leds.md).
