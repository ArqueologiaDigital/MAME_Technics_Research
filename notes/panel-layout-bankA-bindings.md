# STAGE 2: layout artwork (tools/gen_lay.py) rebound to bank A (the KN7000)

Each physical silk-screen button keeps its position + label; only its `tag`/`mask`
(and the state-driven LED `name=`) change from the old bank-B guesses to the
bank-A descriptor bits (source: /tmp/bankA_dump.txt + the STAGE-1 INPUT_PORTS).

## Click bindings (physical function -> bank-A SEG.bit)

### LCD-flanking part on/off soft-keys (5 rows, left=OFF / right=ON)
| part    | OFF (left)   | ON (right)   |
|---------|--------------|--------------|
| RIGHT1  | SEG00 0x02   | SEG11 0x10   |
| RIGHT2  | SEG00 0x08   | SEG11 0x20   |
| LEFT    | SEG00 0x20   | SEG13 0x01   |
| ACCOMP1 | SEG00 0x01   | SEG12 0x01   |
| ACCOMP2 | SEG00 0x04   | SEG11 0x01   |

### LCD-corner control buttons (HELP-info verified, panel_family_2.txt)
- OTHER PART & FR = SEG05 0x01, HELP = SEG05 0x02 (HELP cross-confirmed by STAGE-1)
- DISPLAY HOLD = SEG0B 0x40 (cross-confirmed by STAGE-1), EXIT = SEG0B 0x80
- PAGE up/down + CONTRAST +/-: bank-A bits unverified (CPC control column, context-routed) -> LEFT UNBOUND

### 16-part mixer MUTE row (up=part ON, down=part OFF; ev2001/ev2000)
part1 SEG05 0x10/0x20, part2 SEG05 0x40/0x80, part3 SEG08 0x01/0x02, part4 SEG08 0x04/0x08,
part5 SEG08 0x10/0x20, part6 SEG08 0x40/0x80, part7 SEG09 0x01/0x02, part8 SEG09 0x04/0x08,
part9 SEG09 0x10/0x20, part10 SEG09 0x40/0x80, part11 SEG0A 0x01/0x02, part12 SEG0A 0x04/0x08,
part13 SEG0A 0x10/0x20, part14 SEG0A 0x40/0x80, part15 SEG0B 0x01/0x02, part16 SEG0B 0x04/0x08

### RHYTHM GROUP (16 genres, position i = genre i; ev2005 arg-mid = genre index)
g0 8&16 BEAT SEG02 0x80, g1 ROCK&POP SEG02 0x20, g2 BALLAD SEG02 0x08, g3 JAZZ&SWING SEG02 0x02,
g4 BALLROOM SEG01 0x80, g5 MOVIE&SHOW SEG01 0x20, g6 ENTERTAINER SEG01 0x08, g7 ORGANIST SEG01 0x02,
g8 60s&70s SEG02 0x40, g9 MODERN DANCE SEG02 0x10, g10 SOUL&R&B SEG02 0x04, g11 COUNTRY&WESTERN SEG02 0x01,
g12 MARCH&WALTZ SEG01 0x40, g13 LATIN&WORLD SEG01 0x10, g14 CUSTOM SEG01 0x04, g15 MEMORY SEG01 0x01

### SOUND GROUP (18 categories, position i = category i; ev2004 arg-hi = category index)
PIANO SEG10 0x10, GUITAR SEG0F 0x10, MALLET&ORCH PERC SEG0E 0x10, WORLD SEG0D 0x10,
STRINGS&VOCAL SEG0C 0x10, BRASS SEG15 0x08, SAX&WOODWIND SEG14 0x08, ORGAN&ACCORDION SEG13 0x08,
SOUND EXPLORER SEG12 0x08, DIGITAL DRAWBAR SEG10 0x20, ORGAN TABS SEG0F 0x20, ACCORD REGISTER SEG0E 0x20,
PAD SEG0D 0x20, SYNTH SEG0C 0x20, BASS SEG15 0x04, DRUM KITS SEG14 0x04, MEMORY SEG13 0x04, EW EXPANSION SEG12 0x04
(MEMORY + EW EXPANSION are now BOUND in bank A -- were decorative in bank B.)

### PART EFFECT / GLOBAL EFFECT (SEG0E-11 bits 0x04/0x08)
SUSTAIN SEG11 0x08, DIGITAL EFFECT SEG10 0x08, SOUND DSP SEG0F 0x08, SOUND DSP VARIATION SEG0E 0x08
CHORUS SEG11 0x04, MULTI SEG10 0x04, REVERB SEG0F 0x04, MIC REVERB&EFFECT SEG0E 0x04

### Transport / rhythm control
START/STOP SEG00 0x10, SYNCHRO&BREAK SEG00 0x80, TAP TEMPO SEG03 0x02,
INTRO&ENDING 1 SEG03 0x01 / 2 SEG00 0x40, FILL IN 1 SEG03 0x10 / 2 SEG03 0x04,
FADE IN SEG03 0x20 / OUT SEG03 0x08 (ev2084 arg-mid 0=IN,1=OUT),
VAR&MSA 1 SEG04 0x10 / 2 SEG04 0x04 / 3 SEG04 0x01 / 4 SEG03 0x40,
MUSIC STYLE ARRANGER SEG04 0x08, ONE TOUCH PLAY SEG04 0x02, SPLIT POINT SEG03 0x80,
DEMO SEG06 0x40, PADS: AUTO SETTING SEG06 0x20 / BANK SEG06 0x08 / STOP SEG06 0x02,
PERFORMANCE PADS 1-6 = SEG06 0x10, SEG04 0x80, SEG04 0x20, SEG06 0x04, SEG06 0x01, SEG04 0x40

### APC / SOUND ARRANGER
APC MODE SEG07 0x02, APC OFF/ON SEG07 0x08, SOUND ARRANGER SET SEG07 0x04, SA OFF/ON SEG07 0x10

### SEQUENCER
DISK SEG0D 0x04, PROGRAM MENUS SEG0C 0x04 (PLAY / EASY REC: no static bank-A candidate -> UNBOUND)

### TRANSPOSE / R1-R2 OCTAVE / TECHNI-CHORD / SOLO / PART SELECT / CONDUCTOR
TRANSPOSE - SEG0F 0x01 / + SEG10 0x01 (arg-mid 1=-,0=+ inferred)
R1/R2 OCTAVE - SEG12 0x02 / + SEG13 0x02
TECHNI-CHORD SEG0D 0x01, SOLO SEG0C 0x01
PART SELECT (3) SEG0D 0x02, SEG0E 0x02, SEG0E 0x01 (ev2009 mid 0/1/2 -- all 3 now known)
CONDUCTOR (3) SEG0F 0x02, SEG10 0x02, SEG11 0x02 (ev2008 mid 0/1/2 -- all 3 now known)

## LED name= (state-driven; bank-independent -> re-keyed by state identity)
- GENRE_LED + SOUND GROUP OPLED: re-keyed to bank-A button bits by genre/category identity.
- Individual verified LEDs kept by state identity: SYNCHRO&BREAK cpr_led113, START/STOP cpr_led36,
  MUSIC STYLE ARRANGER cpl_led13, SPLIT POINT cpr_led30, TECHNI-CHORD cpr_led73, DISPLAY HOLD cpl_led5.
- PART/GLOBAL EFFECT + others: bank-A bits not in the swept OPLED -> dark until an empirical bank-A
  LED re-sweep (documented follow-up). A dark LED is honest; a wrong-lit one is not.
