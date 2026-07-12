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

## SEG14–0x20 decode (extends the table above)
Decoded directly from the descriptor arrays (ptr table 0x48614978, 12-byte entries):
```
SEG14  b2 0x2004/0F  b3 0x2004/06                       SOUND family (LEDgrp11.01 / 10.01)
SEG15  b2 0x2004/0E  b3 0x2004/05                       SOUND family (LEDgrp11.02 / 10.02)
SEG16  b0 maskFF 0x1005 type2   |  SEG17 b0 maskFF 0x1004 type4   (DIAL/DATA, no LED)
SEG18  b0 maskFF 0x1009 type2   |  SEG19 b0 maskFF 0x1010 type2
SEG1A  b0 maskFF 0x1011 type2   |  SEG20 b0 maskFF 0x1020 type2   (LEDgrp25.32)
SEG1B  b0..b5 0x1000/arg 05..00 type3                    6-button group (no LED)
SEG1C  (empty)
SEG1D  b0..b5 0x20B5..0x20BA  gate 0xC8..0xCD  class f7   6-button group, SPECIAL multi-LED
SEG1E  b0 0x20BB (LEDgrp00.00)  |  SEG1F b0 0x20BD (LEDgrp00.00)
```

### Interpretation
- **maskFF normSegs (SEG16/17/18/19/1A/20)** are *analog data-entry* controls
  (dispatch type 2/4 = "dial/data"), NOT push-buttons — these are the value
  dials/faders/data-encoder (TEMPO/PROGRAM, data dial, the 4 volume faders, etc.).
- **SEG14/15** are 4 more `0x2004` SOUND-family buttons.
- **SEG1D** (6 sequential `0x20B5-0x20BA`, special multi-LED, `normSeg==0x1D` is the
  one value the panel-test explicitly special-cases) structurally matches the 6-button
  **PART SELECT / CONDUCTOR** cluster in the layout — strong candidate, not yet wired.
- **SEG1B** (6× `0x1000` args 0-5) is a cursor/navigation-style group.

### Why the LCD soft-keys & CPC screen buttons aren't wired here
1. **Soft-keys are context-dependent.** LCDR1/LCDR2 fire `2001/10`,`2001/11`
   (part-select RIGHT1/RIGHT2 = SEG11.b4/b5) *on the home screen* but different
   events on other screens — there is no single static "function", and the exact
   soft-key→bit assignment mixes with part-select/transpose entries (`0x2001` is a
   multiplexed "part-control" event whose meaning depends on arg AND current mode).
2. **CPC board (OTHER PARTS/HELP/CONTRAST±/PAGE±/DISPLAY HOLD/EXIT).** Per the
   service matrix these share columns with MUTE 1-16, but the mute *events* live on
   the CPL-sourced normSegs 0x05/0x08-0x0B; the CPC's own physical→ADDR scan
   encoding is in the **undumped panel sub-CPU**, so their normSeg.bit is not
   statically provable (only the ADDR→normSeg half is).

### Conclusion / next step
Static RE has now extracted every normSeg.bit→event in the main ROM (SEG00-0x20).
The remaining unwired buttons (LCD soft-keys L/R, PART SELECT/CONDUCTOR cluster,
OTHER PARTS/HELP/CONTRAST/PAGE/DISPLAY HOLD/EXIT) can only be confidently pinned to
physical positions via the **dynamic service PANEL SW&LED test** (press each,
observe switch#/LED) — that is now the highest-value remaining task
(see service-diagnostic-mode.md for the entry hunt).

## 2026-07-12 clarification — DISK/SD MENU buttons LIVE-VERIFIED (SD works; DISK is floppy-gated)
Live probe (scratchpad/retcap/menuprobe.lua + diskclean.lua) settles the DISK/SD MENU question:
- **SD MENU = SEG0D 0x80: VERIFIED WORKING** -- pressing it from HOME opens the full SD MENU screen
  (SD TOOLS / SD PREFERENCES / FAVORITE SONGS / CUSTOM STYLE LOAD-SAVE / LOAD / SAVE / SD SONG MEDLEY /
  SD-AUDIO PLAY / SD-SOUND PLAY). The driver's SEG0D 0x80 mapping is CORRECT.
- **DISK MENU = SEG0D 0x40: does NOTHING from HOME** (screen unchanged, md5-identical). Since the
  adjacent SD MENU (SEG0D 0x80) is confirmed correct and the SD subsystem is modeled, the DISK menu is
  almost certainly FLOPPY-DEVICE-GATED -- the firmware bails with no FDC/drive modeled. It should open
  once the floppy (IC103) is modeled. No mislabel fix is warranted; the SEG0D 0x40 label is plausibly
  correct (ROM descriptor SEG0D.6 = event 0x2016).
- The "SEG12 b7 = DISK MENU" line above (from the service-manual matrix) CONFLICTS with the ROM
  descriptor (panel-descriptor-map: SEG12.7 = 0x2010 a6 = the CONTEXT-DEPENDENT Sound-Group/effect
  family) and with the live-confirmed SD MENU at SEG0D 0x80. DISREGARD it for disk-menu access; the
  confirmed path is SEG0D 0x80 (SD) / SEG0D 0x40 (DISK, floppy-gated). rule g: nothing changed.

## 2026-07-12 (2) CORRECTION — the DISK MENU opener is SEG0D 0x04 ("DISK"), NOT SEG0D 0x40
Live-verified with the floppy now modeled: **SEG0D 0x04 ("DISK") OPENS the DISK MENU** (snapshot: DISK
TOOLS/PREFERENCES/STYLE CONVERT/CUSTOM STYLE ; LOAD/SAVE/DIRECT PLAY/SONG MEDLEY). The 2026-07-12 (1)
conclusion above -- "DISK MENU = SEG0D 0x40, floppy-device-gated" -- is WRONG: that tick pressed 0x40
("DISK MENU"), which does nothing from HOME, and mis-attributed the no-op to a device gate. The menu is
NOT gated; it opens via 0x04. (SEG0D 0x40's true function is still unclear -- it may be a bank-B/context
alias; left labeled "DISK MENU" in the driver pending an empirical panel sweep. rule g: documented, not
guessed.) See floppy-fdc-investigation.md 2026-07-12 (6) for the full floppy state.
