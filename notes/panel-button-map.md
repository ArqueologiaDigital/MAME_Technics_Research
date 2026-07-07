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

## MUTE matrix — SOLVED 2026-07-07 (press-count encoding method)
The 16 MUTE UP/DOWN buttons = per-part VOLUME up/down (one press = +/-1 on the PT1-16 mixer). Mapped
by ENCODING each bit's identity in the PRESS COUNT: press bit #k exactly 5k times, then one mixer
snapshot shows each affected part at a distinct level (part at 95 = the 5-press bit, 90 = 10-press,
...). Decodes a whole segment per run. Result is perfectly regular:
| seg | parts | up bits (unmute) | down bits (mute) |
|-----|-------|------------------|------------------|
| SEG04 | 1,2,3,4    | 0x01,0x04,0x10,0x40 | 0x02,0x08,0x20,0x80 |
| SEG05 | 5,6,7,8    | 0x01,0x04,0x10,0x40 | 0x02,0x08,0x20,0x80 |
| SEG06 | 9,10,11,12 | 0x01,0x04,0x10,0x40 | 0x02,0x08,0x20,0x80 |
| SEG07 | 13,14,15,16| 0x01,0x04,0x10,0x40 | 0x02,0x08,0x20,0x80 |
Within each seg: pair (0x01,0x02)=part A, (0x04,0x08)=A+1, (0x10,0x20)=A+2, (0x40,0x80)=A+3.
Parts 1-15 confirmed on the mixer; part 16 (SEG07 0x40/0x80) inferred from the exact pattern (its
mixer nudge didn't render). BUG CAUGHT: APC "OFF/ON" was guessed SEG06 0x08 from the dispatch table
(normSeg06=APC), but layout SEG06 0x08 is really PART 10 mute -> the normSeg vs layout-SEG remap is
NOT identity. Unbound APC OFF/ON. Scripts: scratchpad/mutemap.lua (edit SEQ = {seg,mask,count}).

## LCD RIGHT soft-keys — still open
LCD LEFT = SEG03 b3-b7 (user-confirmed). LCD RIGHT column bits unknown. Ruled out: SEG0A/SEG0B are
NO-OPS from home (no screen change, no mixer change, no HELP info) -- not the LCD RIGHT keys. The
LCD soft-keys are context-dependent (function changes per screen) so HELP-info + from-home probing
miss them. NEXT: characterize-sweep all unmapped segs for bits that open/navigate a screen (DEMO×2
reset between presses), or test on a screen whose right soft-keys are labelled; or ask the user.

## LCD RIGHT soft-keys — method validated, keys NOT yet reachable (2026-07-07)
User's method (great): open an instrument CATEGORY page (e.g. PIANO = SEG0C 0x01) and press an LCD
soft-key -> the corresponding instrument highlights. VALIDATED the mechanism: on the PIANO page,
SEG03 0x10 (LCD LEFT 2) highlights "Mellow Grand" (left col row 2). So the 5 LCD LEFT keys are
SEG03 b3-b7 and they work in the emulator.
BUT: swept EVERY wired ioport bit (SEG02,04-1A,20 + SEG0A/0B/03) on the PIANO page (reset highlight
to a left row via SEG03 0x08, press candidate, detect a right-column row whose box-background mean
brightness spikes) -> NO bit highlights a RIGHT-column instrument. All 8 bits/seg ARE declared
(pressable), so this isn't a probe gap. Conclusion: the 5 LCD RIGHT keys are NOT reachable through
any ADDR the driver currently emits -- consistent with the driver comment "only CPL is filled in
so far (CPC/CPR/CPSD TODO)". PanelWireNormTable has ALTERNATE ADDR sets the driver never emits
(0x80-0x8A -> nS0A-13, 0x97 -> nS1D) = the other boards. NEXT: identify the CPR board's LCD-RIGHT
wire ADDR (schematic SCHEMATIC DIAGRAM-15..18 + those alt table entries), add its ioport, re-test.
Scripts: scratchpad/pianopress.lua (open PIANO + press a bit + dump), lcdright3.lua (sweep+detect).

## NOTE: driver PORT_NAMEs are stale (nS-identity), harmless but misleading
The INPUT_PORTS PORT_NAMEs assume ioport SEGi == firmware nSi (e.g. SEG00 0x80="SYNCHRO & BREAK",
SEG03 0x10="FILL IN 1"), which the empirical map disproves (SYNCHRO=SEG15 0x04; SEG03 0x10=LCD
LEFT 2). Only labels -- the LAYOUT bindings (kn7000.lay) are the source of truth and are correct.
Cleanup TODO: regenerate PORT_NAMEs from the empirical/HELP-info map.
