# KN7000 physical panel switch matrix — transcribed from the service manual

Authoritative panel-button layout for the `.lay` rebuild, transcribed directly
from the SX-KN7000 service-manual schematics (the button *positions* and
*silk-screen labels*, which the KN5000-derived folklore `.lay` gets wrong). Each
board has an 8-bit scanning sub-CPU driving a SEG(column) × SW(row) switch matrix
plus a CM(row) × SEG LED matrix.

- **CPR board** — SCHEMATIC DIAGRAM-17, page 132; sub-CPU IC1001 (C2BBDB000023).
  Switch part = SW1001 + SEG·8 + SWrow (a physical part number; note the SEG8/SEG9
  columns reuse lower part numbers, so map by the SEG-column header + SW-row line,
  not by the part number).
- CPL (DIAGRAM-15, p128) and CPC (DIAGRAM-16, p130): **TODO** (same method).

## CPR switch matrix (SEG column × SW row → silk-screen label)

Verified against the 7 user press-anchors (marked ✓).

| SW row | SEG0 | SEG1 | SEG2 | SEG3 | SEG4 | SEG5 | SEG6 | SEG7 | SEG8 | SEG9 |
|--------|------|------|------|------|------|------|------|------|------|------|
| SW0 | TECHNI-CHORD | SOLO | PART SELECT LEFT | TRANSPOSE R1 (+) | TRANSPOSE R1 (-) | LCDR 5 | LCDR 4 | LCDR 3 | — | — |
| SW1 | SOUND GROUP 1 | PART SELECT RIGHT 2 | PART SELECT RIGHT 1 | CONDUCTOR RIGHT 2 | CONDUCTOR RIGHT 1 | CONDUCTOR LEFT | TRANSPOSE R2 (+) | TRANSPOSE R2 (-) | — | — |
| SW2 | PROGRAM MENUS | DISK MENU LOAD | EFFECT MIC | MULTI | REVERB | CHORUS | EN EXPANSION | MEMORY | ACCORDION REGISTER | DRUM KITS |
| SW3 | DISK EASY REC | VARIATION | (SOUND DSP?) | SOUND DSP | DIGITAL EFFECT | SUSTAIN | SOUND EXPLORER | SAX & WOODWIND | ORGAN & ACCORDION ✓ | WORLD |
| SW4 | MALLET & ORCH PERC ✓ | BRASS ✓ | STRINGS & VOCAL | GUITAR ✓ | PIANO | LCDR 1 | — | — | — | — |
| SW5 | BASS | SYNTH ✓ | PAD | TAB ORGAN | DIGITAL DRAWBAR | LCDR 2 | — | — | — | — |
| SW6 | CUSTOMIZE | CUSTOM PANEL | FAVORITES | SOUND GROUP 5 | SOUND GROUP 4 | SOUND GROUP 3 | SOUND GROUP 2 | SOUND SET | — | — |
| SW7 | SD CARD LOAD | NEXT BANK | BANK VIEW | SOUND GROUP 6 | SOUND GROUP 7 | SOUND GROUP 8 | — | — | — | — |

(LCDR 1..5 = the LCD soft-keys along the display edge. The SEG2·SW3 cell needs a
re-crop to confirm — SOUND DSP appears under SEG3·SW3; SEG2·SW3 may be blank.)

## The binding-bridge problem (why this can't just be pasted into the .lay)

The `.lay` needs each drawn button to carry (a) its physical position, (b) its
label — both now known from the matrix above — and (c) an input binding that
makes the firmware perform that button's function. (c) is the hard part:

- The driver's inputs are **normalized segments** (SEGnn = the firmware's own
  post-normalization index), because that is what the main CPU sees. The real
  panel is **physical (board, SEG, SW)**. The two are related by the panel
  **sub-CPU's scan encoding**, which lives in the sub-CPUs' own (undumped)
  firmware — so physical→normSeg cannot be derived statically.
- The 7 user anchors prove the mapping is a full scramble, not a formula:
  physical GUITAR SEG3·SW4 → normSeg 0x0C bit1; MALLET SEG0·SW4 → normSeg 0x0C
  bit2; BRASS SEG1·SW4 → normSeg 0x11 bit5. Same SW row lands on different
  normSegs/bits; the descriptor bit ≠ the SW row.

So to bind a physical button we must know which normSeg.bit triggers **its**
function. Options to obtain that mapping, in order of reliability:

1. **Empirical panel-test probe (recommended).** Drive each SEGnn.bit in the
   emulator and read which physical switch the firmware reports (its LED via the
   PanelSwitchClassTable 0x4860C9F4, or the on-screen panel-test identity). That
   yields SEGnn.bit → physical(SEG,SW) directly, which + this matrix = full
   labels. No guessing.
2. **More user press→screen anchors** (the method that gave the 7 above).
3. Per-button firmware RE of each descriptor event's handler (slow).

The matrix above is the authoritative half; the next tick should build the
empirical SEGnn.bit → physical bridge, after which the `.lay` can be rebuilt with
positions + labels + bindings all consistent.

## Empirical probe results — SEGnn.bit -> function (2026-07-06)

Built an efficient probe harness (tools/panel_probe.lua): boot once, save a home
savestate, then for each button *load home -> press -> snapshot*. Requires
`-skip_gameinfo` (skips the BAD_DUMP "known problems" warning). Buttons must be
pressed from a fresh home state (they are context-dependent — pressing a category
from within a sound sub-screen does NOT switch it). Snapshots montaged (LCD crop
+ label) and read. Probed all 62 CPR-region buttons (SEG0C-15).

**Sound categories (open a titled SOUND screen; matched to the CPR matrix):**

| normSeg.bit | event | function = CPR silk-screen label | CPR pos |
|---|---|---|---|
| SEG0C.b0 | 2086/00 | PIANO | SEG4.SW4 |
| SEG0C.b1 | 2010/00 | GUITAR | SEG3.SW4 |
| SEG0C.b2 | 2040/01 | MALLET & ORCH PERC | SEG0.SW4 |
| SEG0C.b3 | 2040/03 | WORLD | SEG9.SW3 |
| SEG0C.b4 | 2004/04 | STRINGS & VOCAL | SEG2.SW4 |
| SEG0C.b5 | 2004/0D | BRASS | SEG1.SW4 |
| SEG0D.b0 | 20A2/00 | SAX & WOODWIND | SEG7.SW3 |
| SEG0D.b1 | 2009/00 | ORGAN & ACCORDION | SEG8.SW3 |
| SEG0D.b2 | 2040/02 | SOUND EXPLORER | SEG6.SW3 |
| SEG0D.b3 | 2040/07 | DIGITAL DRAWBAR | SEG4.SW5 |
| SEG0D.b4 | 2004/03 | ORGAN TABS (silk "TAB ORGAN") | SEG3.SW5 |
| SEG0D.b5 | 2004/0C | ACCORDION REGISTER | SEG8.SW2 |
| SEG0E.b0 | 2009/02 | PAD | SEG2.SW5 |
| SEG0E.b1 | 2009/01 | SYNTH | SEG1.SW5 |
| SEG0E.b2 | 2063/00 | BASS | SEG0.SW5 |
| SEG0E.b3 | 20AB/00 | DRUM KITS | SEG9.SW2 |

**Other functions identified (open a titled screen or show an indicator):**

| normSeg.bit | event | function |
|---|---|---|
| SEG10.b0 | 2081/00 | ONE TOUCH PLAY |
| SEG11.b0 | 2001/14 | FADE IN |
| SEG11.b1 | 2008/02 | FADE OUT |
| SEG12.b6 | 2010/01 | PROGRAM MENUS |
| SEG12.b7 | 2010/06 | DISK MENU |
| SEG13.b0 | 2001/12 | TRANSPOSE (down) |
| SEG13.b1 | 2083/00 | TRANSPOSE (up) |
| SEG13.b2 | 2004/10 | R1/R2 OCTAVE - |
| SEG13.b3 | 2004/07 | R1/R2 OCTAVE + |

**Correction:** the earlier folklore-derived anchor "SEG11.b5 = BRASS" was WRONG
(SEG11.b5 / 2001/11 shows home — a toggle). The direct probe supersedes the
`.lay`-binding-based anchors; 5 of 6 probed anchors matched (GUITAR, MALLET,
ORGAN&ACCORDION, SYNTH, ORGAN TABS), BRASS was the mis-derived one.

**Still "home" (no titled screen from home — toggles / part on-off / SOUND GROUP
1-8 / mode buttons):** ~33 buttons across SEG0F, SEG10-15. These need matching to
the CPR matrix labels via their events or a second-context probe. Next: CPL/CPC
matrices + resolve these + rebuild the .lay.

## CPC switch matrix (SCHEMATIC DIAGRAM-16, page 130) — the mixer board

Columns are scan lines SEG5, SEG8, SEG9, SEG10, SEG11 (from CN1108); rows SW0-7.
The CPC board has no own microcomputer (switch/LED matrix wired to the main
scanner via CN1107/CN1108). Switch part = SW1155 + col*8 + SWrow.

| SW row | SEG5 | SEG8 | SEG9 | SEG10 | SEG11 |
|--------|------|------|------|-------|-------|
| SW0 | OTHER PARTS/TG | MUTE UP 3 | MUTE UP 7 | MUTE UP 11 | MUTE UP 15 |
| SW1 | HELP | MUTE DOWN 3 | MUTE DOWN 7 | MUTE DOWN 11 | MUTE DOWN 15 |
| SW2 | CONTRAST UP | MUTE UP 4 | MUTE UP 8 | MUTE UP 12 | MUTE UP 16 |
| SW3 | CONTRAST DOWN | MUTE DOWN 4 | MUTE DOWN 8 | MUTE DOWN 12 | MUTE DOWN 16 |
| SW4 | MUTE UP 1 | MUTE UP 5 | MUTE UP 9 | MUTE UP 13 | PAGE UP |
| SW5 | MUTE DOWN 1 | MUTE DOWN 5 | MUTE DOWN 9 | MUTE DOWN 13 | PAGE DOWN |
| SW6 | MUTE UP 2 | MUTE UP 6 | MUTE UP 10 | MUTE UP 14 | DISPLAY HOLD |
| SW7 | MUTE DOWN 2 | MUTE DOWN 6 | MUTE DOWN 10 | MUTE DOWN 14 | EXIT |

So the CPC labels (HELP, CONTRAST UP/DOWN, MUTE UP/DOWN 1-16, PAGE UP/DOWN,
DISPLAY HOLD, EXIT, OTHER PARTS/TG) actually MATCH the KN5000-folklore labels the
current .lay uses -- for this board the labels/positions were roughly right; only
the input BINDINGS were wrong (which is why pressing "HELP" navigated to GUITAR).
The 16 MUTE UP/DOWN pairs are the part mixer (map to the 0x2001/0x2000 mute
events; part index via the part-name table 0x485FDE70). LED matrix (CM rows):
OTHER PARTS/TR, SPRIT 2, SPRIT 3, DISPLAY HOLD.

## CPL switch matrix (SCHEMATIC DIAGRAM-15, page 128) — rhythm / arranger / pads

Own sub-CPU IC1101 (C2BBDB000023); columns SEG0,1,2,3,4,6,7 (SEG5 belongs to
CPC); rows SW0-7. Switch part = SW1102 + col-index*8 + SWrow. Some right-column
cells (SEG4 SW4-7, SEG7 SW5-7) need a re-crop to confirm (marked ?).

| SW row | SEG0 | SEG1 | SEG2 | SEG3 | SEG4 | SEG6 | SEG7 |
|--------|------|------|------|------|------|------|------|
| SW0 | LCDL 4 | MEMORY/LOAD | MOVIE SHOW | INTRO & ENDING 1 | VARIATION & MSA 3 | PAD 5/SOLO | MUSIC STYLIST |
| SW1 | LCDL 1 | SOUL & FUNK | MARCH | TAP TEMPO | VARIATION & MSA 2 | PERFORMANCE PADS/STOP | AUTO MODE |
| SW2 | LCDL 5 | CUSTOM | ENTERTAINER | FILL IN 2 | MUSIC STYLE ARRANGER | PAD 4 | SOUND SET |
| SW3 | LCDL 2 | BALLAD | COUNTRY | FADE OUT | VARIATION & MSA 1 | PERFORMANCE PADS/BANK | PLAY CHORD OFF/ON |
| SW4 | START/STOP | JAZZ COMBO | LATIN & WORLD | FILL IN 1 | ? | PAD 1 | ARRANGER OFF/ON |
| SW5 | LCDL 3 | ROCK & POP | GOSPEL & BLUES | FADE IN | ? | PERFORMANCE PADS/AUTO | ? |
| SW6 | INTRO & ENDING 2 | BIG BAND & SWING | BALLROOM | VARIATION & MSA 4 | ? | DEMO | ? |
| SW7 | SYNCHRO & BREAK | R & B | MODERN DANCE | SPLIT POINT | PAD 6/SOLO ? | PAD 2 | ? |

SEG1+SEG2 hold 16 rhythm-genre buttons (MEMORY/LOAD, SOUL&FUNK, CUSTOM, BALLAD,
JAZZ COMBO, ROCK&POP, BIG BAND&SWING, R&B, MOVIE SHOW, MARCH, ENTERTAINER,
COUNTRY, LATIN&WORLD, GOSPEL&BLUES, BALLROOM, MODERN DANCE) -> the 0x2005/arg
rhythm-group events, named via RhythmGenreNameTable 0x48735EE4 (genre=(arg+7)%16).

## Big picture: all 3 boards' labels match the folklore .lay; only BINDINGS are wrong

The KN5000-derived folklore labels/positions the current .lay uses are (roughly)
correct for all three boards -- the SX-KN7000 shares the KN5000 panel layout. What
is wrong is the input BINDING of each drawn button (which is why clicking "HELP"
navigated to GUITAR). So the .lay rebuild reduces mainly to re-binding each button
to the normSeg.bit whose function matches its label -- not redrawing everything.
The binding for each is obtained from the empirical probe (normSeg.bit -> function)
matched to these matrix labels.

## Probe results SEG00-0B (rhythm / transport / mutes) — 2026-07-06

Probed all 93 SEG00-0B buttons the same way. Two caveats surfaced:
- **Mode-gating**: from the home screen, several buttons act as PERFORMANCE PADS
  (play a phrase: Voice Welcome, Waves, Church Bells, Cosmic Maj/Min, Birdsong)
  rather than their labelled function -- so the probe is ambiguous for those bits.
- **No-screen buttons**: part mutes and arranger toggles (FILL/FADE/VARIATION/
  INTRO-ENDING) change state without opening a titled screen -> show home. These
  must be matched structurally (event family + physical label), not by screen.

**Rhythm genres cleanly identified (RHYTHM screen title = RhythmGenreNameTable name):**

| normSeg.bit | event | genre |
|---|---|---|
| SEG00.b2 | 2000/14 | 8&16 BEAT |
| SEG00.b3 | 2000/11 | ROCK & POP |
| SEG00.b4 | 2020/00 | BALLAD |
| SEG00.b5 | 2000/12 | JAZZ & SWING |
| SEG00.b6 | 2022/01 | BALLROOM |
| SEG00.b7 | 2021/00 | MOVIE & SHOW |
| SEG01.b2 | 2005/0E | ENTERTAINER |
| SEG01.b3 | 2005/06 | ORGANIST |
| SEG01.b4 | 2005/0D | 60s & 70s |
| SEG01.b5 | 2005/05 | MODERN DANCE |
| SEG01.b6 | 2005/0C | SOUL & R&B |
| SEG01.b7 | 2005/04 | COUNTRY&WESTERN |
| SEG02.b2 | 2005/0A | MARCH & WALTZ |
| SEG02.b3 | 2005/02 | LATIN & WORLD |
| SEG02.b4 | 2005/09 | CUSTOM |
| SEG02.b5 | 2005/01 | MEMORY |

(These internal names differ slightly from the CPL silk-screen wording, e.g.
"MARCH & WALTZ"=silk "MARCH", "COUNTRY&WESTERN"=silk "COUNTRY", "JAZZ & SWING"=silk
"JAZZ COMBO" -- match by nearest genre.)

**Menu / function screens identified:**

| normSeg.bit | event | function |
|---|---|---|
| SEG02.b6 | 2005/08 | SOUND ARRANGER |
| SEG03.b1 | 20A1/00 | APC SELECT (Auto Play Chord) |

**Not screen-identifiable (match structurally next):** part mutes SEG08-0B +
SEG05 (0x2000/0x2001 arg = part; -> CPC MUTE UP/DOWN 1-16 via part-name table);
arranger toggles SEG04/06 (0x2030 = FILL/FADE, 0x2084/0x2085 = VARIATION, 0x2023 =
INTRO/ENDING); pad buttons (mode-gated).

## Rebuild plan (next)

The .lay rebuild is now data-gathering-complete for the screen buttons. Remaining
before generation: (1) structurally match the no-screen buttons (mutes via
part-name table + CPC MUTE positions; arranger toggles via event family + CPL
labels); (2) generate the .lay -- keep the folklore geometry/labels (they match)
and REWRITE each button's inputtag/inputmask to the correct normSeg.bit. Verify a
sample of re-bound buttons with the probe before committing.
