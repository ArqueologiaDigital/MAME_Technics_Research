# KN7000 panel button map — HELP-info sweep (2026-07-07)

Definitive layout-SEG,bit -> button, obtained by the HELP-info method (press HELP, then a button,
read the "HELP : <NAME>" title). scratchpad/helpsweep.lua sweeps a segment, deduping distinct
info screens. VALIDATED: DISK=SEG12 0x80 and PROGRAM MENUS=SEG12 0x40 were already bound and the
user confirmed they work -> the map is trustworthy.

| bit       | button              | bound? |
|-----------|---------------------|--------|
| SEG0F 0x01| SOUND DSP           | yes    |
| SEG0F 0x02| SOUND DSP VARIATION | yes (PART EFFECT "VARIATION") |
| SEG10 0x01| ONE TOUCH PLAY      | yes (was already correct) |
| SEG10 0x02| SPLIT POINT         | yes    |
| SEG10 0x04| VARIATION & MSA     | yes (VAR1) |
| SEG10 0x10| PART SELECT         | yes (1st of group) |
| SEG10 0x80| SOLO                | no drawn button |
| SEG11 0x01| FADE IN/OUT         | yes    |
| SEG11 0x04| FILL IN 1/2         | no drawn button |
| SEG11 0x10| CONDUCTOR           | yes (1st of group) |
| SEG11 0x80| TECHNI-CHORD        | yes    |
| SEG12 0x01| INTRO & ENDING 1/2  | yes    |
| SEG12 0x04| TAP TEMPO           | yes (was wrongly SEG04 0x02) |
| SEG12 0x08| START/STOP          | yes    |
| SEG12 0x40| PROGRAM MENU(S)     | yes (already correct) |
| SEG12 0x80| DISK                | yes (already correct) |
| SEG13 0x01| TRANSPOSE -/+       | yes    |
| SEG13 0x04| R1/R2 OCTAVE -/+    | yes    |
| SEG13 0x40| REVERB              | yes    |
| SEG13 0x80| MIC REVERB & EFFECT | yes (GLOBAL EFFECT "MIC") |

## Applied this pass
Bound the 10 "yes" rows; **unbound the LCDPARTS RIGHT column** (SEG11-13) which had been assumed
to be part-ON but is really FADE/CONDUCTOR/INTRO&ENDING/TRANSPOSE. (LCD LEFT = SEG03 b3-b7 left
column stays -- user-confirmed.) No double-bound bits.

## EXIT = SEG08 0x20 (FOUND 2026-07-07)
Confirmed: pressed in HELP mode it turns HELP off -> returns to the PMEM home screen. Completes
the SEG08 LCD-corner set (OTHER PARTS 0x04, HELP 0x08, DISPLAY HOLD 0x10, EXIT 0x20). Bound.

## Remaining TODO
- Bind the 7 "TODO" rows to their drawn buttons (TECHNI-CHORD, TRANSPOSE +/-, R1/R2 OCTAVE, PART
  SELECT, SOLO, FILL IN, CONDUCTOR, VARIATION & MSA).
- SUSTAIN, DIGITAL EFFECT, CHORUS, MULTI, SEQUENCER PLAY/EASY REC, SYNCHRO, SD LOAD still unfound.
