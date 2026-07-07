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

## Additional HELP-info sweep (SEG08/09/15) — 2026-07-07
Clean sweep (body-brightness help-off detection, excluding HELP/EXIT) VERIFIED SEG09 (my earlier
"contaminated" reading was a misread of a blended image):
| bit | button | bound? |
|-----|--------|--------|
| SEG08 0x40| SOUND CONTROLLER MODE  | (no drawn button) |
| SEG08 0x80| SOUND CONTROLLER RESET | (no drawn button) |
| SEG09 0x01| PERFORMANCE PADS BANK  | yes |
| SEG09 0x02| PERFORMANCE PADS STOP  | yes (was wrongly SEG06 0x02) |
| SEG09 0x04| PERFORMANCE PADS AUTO SETTING | yes (was wrongly SEG06 0x20) |
| SEG09 0x08| MUSIC STYLE ARRANGER   | yes |
| SEG09 0x10| VARIATION & MSA (2nd)  | (VAR2; not distinctly bound) |
| SEG09 0x40| DEMO                   | yes |
| SEG15 0x04| SYNCHRO & BREAK        | yes |
SEG04/06/07/14/16-1F produced NO HELP info (no buttons there, or non-informative).

## MUTE UP/DOWN buttons — STILL OPEN (user-flagged 2026-07-07)
The 16 MUTE UP/DOWN buttons do NOT show HELP info (swept SEG05/0A/0B in HELP mode -> 0 captures),
so the HELP-name oracle can't map them. They are per-part VOLUME nudges: pressing the confirmed
SEG05 0x20 (= MUTE DOWN 7) drops PART 7's mixer level 100->99 (a full press ramps to silence).
Known: SEG05 = parts 7,8 (user). The part-level RAM byte was NOT found in 0x50030000-0x50048000
(not a simple 0-100 byte / not a toggle). NEXT approach: open the OTHER PARTS (PT1-16) mixer via
SEG08 0x04, press each candidate mute-down bit, snapshot, read which PT's level dropped -> map bit
-> part. Candidate segs: SEG05 (parts 7,8 + maybe 5,6 on b0-b3), SEG0A, SEG0B, and others TBD.
