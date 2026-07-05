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
