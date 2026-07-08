# KN7000 panel HELP-info sweep (2026-07-08, workflow, 7 agents, 49 distinct HELP screens)

Method: boot, enter HELP (SEG08 0x08), press each SEG bit, read the "HELP : <NAME>" LCD title.
Segments SEG00-SEG20 swept (skipped part-mute banks SEG04-07 + already-done SEG12).

| SEG.bit | HELP title | already bound? |
|---------|-----------|----------------|
| SEG02 0x20 | COMPOSER MEMORY | NEW |
| SEG02 0x40 | SOUND ARRANGER SET | NEW (my unbound: SOUND ARRANGER SET) |
| SEG02 0x80 | SOUND ARRANGER OFF/ON | NEW (my unbound: SOUND ARRANGER ON/OFF) |
| SEG03 0x02 | APC/CHORD FINDER | bound (APC MODE) |
| SEG03 0x04 | AUTO PLAY CHORD OFF/ON | NEW (my unbound: APC ON/OFF) |
| SEG08 0x40 | SOUND CONTROLLER MODE | NEW |
| SEG08 0x80 | SOUND CONTROLLER RESET | NEW |
| SEG09 0x01 | PERFORMANCE PADS BANK | NEW |
| SEG09 0x02 | PERFORMANCE PADS STOP | NEW |
| SEG09 0x04 | PERFORMANCE PADS AUTO SETTING | NEW |
| SEG09 0x40 | DEMO | bound |
| SEG0D 0x04 | SOUND EXPLORER | NEW |
| SEG0D 0x08 | DIGITAL DRAWBAR | NEW |
| SEG0D 0x10 | TAB ORGAN | NEW |
| SEG0D 0x20 | SOUND GROUP | NEW |
| SEG0E 0x10 | SUSTAIN | NEW |
| SEG0E 0x20 | DIGITAL EFFECT | NEW |
| SEG10 0x40 | PART SELECT | NEW (my unbound: PART SELECT) |
| SEG10 0x80 | SOLO | bound (just did) |
| SEG11 0x40 | CONDUCTOR | NEW (my unbound: CONDUCTOR) |
| SEG13 0x20 | MULTI EFFECT | NEW |

(The rest of the 49 were already-bound buttons, confirming the map. NOT found via HELP -- no help screen,
like PAGE/CONTRAST: MUSIC STYLIST, CUSTOMIZE, FAVORITES, BANK VIEW, NEXT BANK, CUSTOM PANEL, SEQUENCER PLAY,
EASY REC, SOUND MEMORY, EXPANSION, VARIATION 2/3/4 -- these remain bit-unknown.)
