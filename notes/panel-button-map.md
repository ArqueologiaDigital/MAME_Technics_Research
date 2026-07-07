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
| SEG10 0x04| VARIATION & MSA     | TODO (VARBITS group) |
| SEG10 0x10| PART SELECT         | TODO   |
| SEG10 0x80| SOLO                | TODO   |
| SEG11 0x01| FADE IN/OUT         | yes    |
| SEG11 0x04| FILL IN 1/2         | TODO   |
| SEG11 0x10| CONDUCTOR           | TODO   |
| SEG11 0x80| TECHNI-CHORD        | TODO   |
| SEG12 0x01| INTRO & ENDING 1/2  | yes    |
| SEG12 0x04| TAP TEMPO           | yes (was wrongly SEG04 0x02) |
| SEG12 0x08| START/STOP          | yes    |
| SEG12 0x40| PROGRAM MENU(S)     | yes (already correct) |
| SEG12 0x80| DISK                | yes (already correct) |
| SEG13 0x01| TRANSPOSE -/+       | TODO   |
| SEG13 0x04| R1/R2 OCTAVE -/+    | TODO   |
| SEG13 0x40| REVERB              | yes    |
| SEG13 0x80| MIC REVERB & EFFECT | yes (GLOBAL EFFECT "MIC") |

## Applied this pass
Bound the 10 "yes" rows; **unbound the LCDPARTS RIGHT column** (SEG11-13) which had been assumed
to be part-ON but is really FADE/CONDUCTOR/INTRO&ENDING/TRANSPOSE. (LCD LEFT = SEG03 b3-b7 left
column stays -- user-confirmed.) No double-bound bits.

## TODO (next tick)
- Bind the 7 "TODO" rows to their drawn buttons (TECHNI-CHORD, TRANSPOSE +/-, R1/R2 OCTAVE, PART
  SELECT, SOLO, FILL IN, CONDUCTOR, VARIATION & MSA).
- EXIT still unknown -- HELP-info sweep the remaining segs (SEG03/04/06/07/08/09/14-1F/20); EXIT is
  the bit that turns HELP OFF (returns to home) rather than showing an info screen.
- SUSTAIN, DIGITAL EFFECT, CHORUS, MULTI, SEQUENCER PLAY/EASY REC, SYNCHRO, SD LOAD still unfound.
