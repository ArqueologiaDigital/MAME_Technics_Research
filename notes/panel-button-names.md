# KN7000 panel button NAMES — authoritative map (2026-07-07)

Every ioport SEG.bit -> firmware event (pinned board-decode: `panel-board-decode.md` + `panel-dispatch-active.txt`) -> human NAME.
Sources: HELP-info (keyboard names itself, top confidence), ROM tables (genres GenreStyleTable@0x48735EE4, sounds SoundGroupNameTable@0x48131570), part ids, and the empirical event->name legend. `legend` = named via another bit that fires the same event; `legend(event)` = same event family, likely the paired +/- or ON/OFF half.

| SEG.bit | normSeg | event | NAME | source |
|---|---|---|---|---|
| SEG00.0x01 | nS00 | ev2030 arg0006 | PERFORMANCE PAD 1 | HELP-info |
| SEG00.0x02 | nS00 | ev2030 arg0306 | PERFORMANCE PAD 4 | HELP-info |
| SEG00.0x04 | nS00 | ev2005 arg005F | RHYTHM GROUP: 8&16 BEAT | genre-tbl |
| SEG00.0x08 | nS00 | ev2005 arg015F | RHYTHM GROUP: ROCK & POP | genre-tbl |
| SEG00.0x10 | nS00 | ev2005 arg025F | RHYTHM GROUP: BALLAD | genre-tbl |
| SEG00.0x20 | nS00 | ev2005 arg035F | RHYTHM GROUP: JAZZ & SWING | genre-tbl |
| SEG00.0x40 | nS00 | ev2005 arg045F | RHYTHM GROUP: BALLROOM | genre-tbl |
| SEG00.0x80 | nS00 | ev2005 arg055F | RHYTHM GROUP: MOVIE & SHOW | genre-tbl |
| SEG01.0x01 | nS01 | ev2030 arg0106 | PERFORMANCE PAD 2 | HELP-info |
| SEG01.0x02 | nS01 | ev2030 arg0406 | PERFORMANCE PAD 5 | HELP-info |
| SEG01.0x04 | nS01 | ev2005 arg065F | RHYTHM GROUP: ENTERTAINER | genre-tbl |
| SEG01.0x08 | nS01 | ev2005 arg075F | RHYTHM GROUP: ORGANIST | genre-tbl |
| SEG01.0x10 | nS01 | ev2005 arg085F | RHYTHM GROUP: 60s & 70s | genre-tbl |
| SEG01.0x20 | nS01 | ev2005 arg095F | RHYTHM GROUP: MODERN DANCE | genre-tbl |
| SEG01.0x40 | nS01 | ev2005 arg0A5F | RHYTHM GROUP: SOUL & R&B | genre-tbl |
| SEG01.0x80 | nS01 | ev2005 arg0B5F | RHYTHM GROUP: COUNTRY & WESTERN | genre-tbl |
| SEG02.0x01 | nS02 | ev2030 arg0206 | PERFORMANCE PAD 3 | HELP-info |
| SEG02.0x02 | nS02 | ev2030 arg0506 | PERFORMANCE PAD 6 | HELP-info |
| SEG02.0x04 | nS02 | ev2005 arg0C5F | RHYTHM GROUP: MARCH & WALTZ | genre-tbl |
| SEG02.0x08 | nS02 | ev2005 arg0D5F | RHYTHM GROUP: LATIN & WORLD | genre-tbl |
| SEG02.0x10 | nS02 | ev2005 arg0E5F | RHYTHM GROUP: CUSTOM | genre-tbl |
| SEG02.0x20 | nS02 | ev2005 arg0F5F | RHYTHM GROUP: COMPOSER MEMORY | genre-tbl |
| SEG02.0x40 | nS02 | ev2040 arg0565 | SOUND ARRANGER SET | HELP-info |
| SEG02.0x80 | nS02 | ev20A7 arg0026 | SOUND ARRANGER OFF/ON | HELP-info |
| SEG03.0x01 | nS03 |  | (no panel event) | unused |
| SEG03.0x02 | nS03 | ev20A8 arg0027 | APC / CHORD FINDER | HELP-info |
| SEG03.0x04 | nS03 | ev20A9 arg0027 | AUTO PLAY CHORD OFF/ON | HELP-info |
| SEG03.0x08 | nS03 | ev2000 arg1000 | RIGHT1 OFF | part |
| SEG03.0x10 | nS03 | ev2000 arg1100 | RIGHT2 OFF | part |
| SEG03.0x20 | nS03 | ev2000 arg1200 | LEFT OFF | part |
| SEG03.0x40 | nS03 | ev2000 arg1300 | ACCOMP1 OFF | part |
| SEG03.0x80 | nS03 | ev2000 arg1400 | ACCOMP2 OFF | part |
| SEG04.0x01 | nS04 | ev2001 arg0000 | MUTE PART 1 ON | part |
| SEG04.0x02 | nS04 | ev2000 arg0000 | MUTE PART 1 OFF | part |
| SEG04.0x04 | nS04 | ev2001 arg0100 | MUTE PART 2 ON | part |
| SEG04.0x08 | nS04 | ev2000 arg0100 | MUTE PART 2 OFF | part |
| SEG04.0x10 | nS04 | ev2001 arg0200 | MUTE PART 3 ON | part |
| SEG04.0x20 | nS04 | ev2000 arg0200 | MUTE PART 3 OFF | part |
| SEG04.0x40 | nS04 | ev2001 arg0300 | MUTE PART 4 ON | part |
| SEG04.0x80 | nS04 | ev2000 arg0300 | MUTE PART 4 OFF | part |
| SEG05.0x01 | nS05 | ev2001 arg0400 | MUTE PART 5 ON | part |
| SEG05.0x02 | nS05 | ev2000 arg0400 | MUTE PART 5 OFF | part |
| SEG05.0x04 | nS05 | ev2001 arg0500 | MUTE PART 6 ON | part |
| SEG05.0x08 | nS05 | ev2000 arg0500 | MUTE PART 6 OFF | part |
| SEG05.0x10 | nS05 | ev2001 arg0600 | MUTE PART 7 ON | part |
| SEG05.0x20 | nS05 | ev2000 arg0600 | MUTE PART 7 OFF | part |
| SEG05.0x40 | nS05 | ev2001 arg0700 | MUTE PART 8 ON | part |
| SEG05.0x80 | nS05 | ev2000 arg0700 | MUTE PART 8 OFF | part |
| SEG06.0x01 | nS06 | ev2001 arg0800 | MUTE PART 9 ON | part |
| SEG06.0x02 | nS06 | ev2000 arg0800 | MUTE PART 9 OFF | part |
| SEG06.0x04 | nS06 | ev2001 arg0900 | MUTE PART 10 ON | part |
| SEG06.0x08 | nS06 | ev2000 arg0900 | MUTE PART 10 OFF | part |
| SEG06.0x10 | nS06 | ev2001 arg0A00 | MUTE PART 11 ON | part |
| SEG06.0x20 | nS06 | ev2000 arg0A00 | MUTE PART 11 OFF | part |
| SEG06.0x40 | nS06 | ev2001 arg0B00 | MUTE PART 12 ON | part |
| SEG06.0x80 | nS06 | ev2000 arg0B00 | MUTE PART 12 OFF | part |
| SEG07.0x01 | nS07 | ev2001 arg0C00 | MUTE PART 13 ON | part |
| SEG07.0x02 | nS07 | ev2000 arg0C00 | MUTE PART 13 OFF | part |
| SEG07.0x04 | nS07 | ev2001 arg0D00 | MUTE PART 14 ON | part |
| SEG07.0x08 | nS07 | ev2000 arg0D00 | MUTE PART 14 OFF | part |
| SEG07.0x10 | nS07 | ev2001 arg0E00 | MUTE PART 15 ON | part |
| SEG07.0x20 | nS07 | ev2000 arg0E00 | MUTE PART 15 OFF | part |
| SEG07.0x40 | nS07 | ev2001 arg0F00 | MUTE PART 16 ON | part |
| SEG07.0x80 | nS07 | ev2000 arg0F00 | MUTE PART 16 OFF | part |
| SEG08.0x01 | nS08 | ev2001 arg1800 | part18 ON | part |
| SEG08.0x02 | nS08 | ev2000 arg1800 | part18 OFF | part |
| SEG08.0x04 | nS08 | ev2000 arg1900 | OTHER PARTS & FR | HELP-info |
| SEG08.0x08 | nS08 | ev2040 arg0464 | HELP | HELP-info |
| SEG08.0x10 | nS08 | ev20A0 arg0017 | DISPLAY HOLD | HELP-info |
| SEG08.0x20 | nS08 | ev2001 arg1700 | EXIT | HELP-info |
| SEG08.0x40 | nS08 | ev20AD arg0037 | SOUND CONTROLLER MODE | HELP-info |
| SEG08.0x80 | nS08 | ev20AC arg0037 | SOUND CONTROLLER RESET | HELP-info |
| SEG09.0x01 | nS09 | ev2032 arg0006 | PERFORMANCE PADS BANK | HELP-info |
| SEG09.0x02 | nS09 | ev2033 arg0006 | PERFORMANCE PADS STOP | HELP-info |
| SEG09.0x04 | nS09 | ev2031 arg0006 | PERFORMANCE PADS AUTO SETTING | HELP-info |
| SEG09.0x08 | nS09 | ev20A3 arg0022 | MUSIC STYLE ARRANGER | HELP-info |
| SEG09.0x10 | nS09 | ev2085 arg0016 | VARIATION & MSA | HELP-info |
| SEG09.0x20 | nS09 | ev2085 arg0116 | VARIATION & MSA | legend(event) |
| SEG09.0x40 | nS09 | ev2040 arg0060 | DEMO | HELP-info |
| SEG09.0x80 | nS09 |  | (no panel event) | unused |
| SEG0A.0x01 | INVALID |  | (firmware no-op) | no-op |
| SEG0A.0x02 | INVALID |  | (firmware no-op) | no-op |
| SEG0A.0x04 | INVALID |  | (firmware no-op) | no-op |
| SEG0A.0x08 | INVALID |  | (firmware no-op) | no-op |
| SEG0A.0x10 | INVALID |  | (firmware no-op) | no-op |
| SEG0A.0x20 | INVALID |  | (firmware no-op) | no-op |
| SEG0A.0x40 | INVALID |  | (firmware no-op) | no-op |
| SEG0A.0x80 | INVALID |  | (firmware no-op) | no-op |
| SEG0B.0x01 | INVALID |  | (firmware no-op) | no-op |
| SEG0B.0x02 | INVALID |  | (firmware no-op) | no-op |
| SEG0B.0x04 | INVALID |  | (firmware no-op) | no-op |
| SEG0B.0x08 | INVALID |  | (firmware no-op) | no-op |
| SEG0B.0x10 | INVALID |  | (firmware no-op) | no-op |
| SEG0B.0x20 | INVALID |  | (firmware no-op) | no-op |
| SEG0B.0x40 | INVALID |  | (firmware no-op) | no-op |
| SEG0B.0x80 | INVALID |  | (firmware no-op) | no-op |
| SEG0C.0x01 | nS0A | ev2004 arg004F | SOUND GROUP: PIANO | sound-tbl |
| SEG0C.0x02 | nS0A | ev2004 arg014F | SOUND GROUP: GUITAR | sound-tbl |
| SEG0C.0x04 | nS0A | ev2004 arg024F | SOUND GROUP: MALLET&ORCH PERC | sound-tbl |
| SEG0C.0x08 | nS0A | ev2004 arg034F | SOUND GROUP: WORLD | sound-tbl |
| SEG0C.0x10 | nS0A | ev2004 arg044F | SOUND GROUP: STRINGS & VOCAL | sound-tbl |
| SEG0C.0x20 | nS0A | ev2004 arg0543 | SOUND GROUP: BRASS | sound-tbl |
| SEG0C.0x40 | nS0A |  | (no panel event) | unused |
| SEG0C.0x80 | nS0A |  | (no panel event) | unused |
| SEG0D.0x01 | nS0B | ev2004 arg064F | SOUND GROUP: SAX & WOODWIND | sound-tbl |
| SEG0D.0x02 | nS0B | ev2004 arg074F | SOUND GROUP: ORGAN&ACCORDION | sound-tbl |
| SEG0D.0x04 | nS0B | ev2004 arg084F | SOUND GROUP: SOUND EXPLORER | sound-tbl |
| SEG0D.0x08 | nS0B | ev2004 arg094F | SOUND GROUP: DIGITAL DRAWBAR | sound-tbl |
| SEG0D.0x10 | nS0B | ev2004 arg0A40 | SOUND GROUP: ORGAN TABS | sound-tbl |
| SEG0D.0x20 | nS0B | ev2004 arg0B42 | SOUND GROUP: ACCORD REGISTER | sound-tbl |
| SEG0D.0x40 | nS0B |  | (no panel event) | unused |
| SEG0D.0x80 | nS0B |  | (no panel event) | unused |
| SEG0E.0x01 | nS0C | ev2004 arg0C4F | SOUND GROUP: PAD | sound-tbl |
| SEG0E.0x02 | nS0C | ev2004 arg0D4F | SOUND GROUP: SYNTH | sound-tbl |
| SEG0E.0x04 | nS0C | ev2004 arg0E4F | SOUND GROUP: BASS | sound-tbl |
| SEG0E.0x08 | nS0C | ev2004 arg0F4F | SOUND GROUP: DRUM KITS | sound-tbl |
| SEG0E.0x10 | nS0C | ev2068 arg0011 | SUSTAIN | HELP-info |
| SEG0E.0x20 | nS0C | ev2069 arg0030 | DIGITAL EFFECT | HELP-info |
| SEG0E.0x40 | nS0C |  | (no panel event) | unused |
| SEG0E.0x80 | nS0C |  | (no panel event) | unused |
| SEG0F.0x01 | nS0D | ev20AA arg0031 | SOUND DSP | HELP-info |
| SEG0F.0x02 | nS0D | ev20AB arg0031 | SOUND DSP VARIATION | HELP-info |
| SEG0F.0x04 | nS0D | ev2001 arg1000 | RIGHT1 ON | part |
| SEG0F.0x08 | nS0D | ev2001 arg1100 | RIGHT2 ON | part |
| SEG0F.0x10 | nS0D | ev2001 arg1200 | LEFT ON | part |
| SEG0F.0x20 | nS0D | ev2001 arg1300 | ACCOMP1 ON | part |
| SEG0F.0x40 | nS0D | ev2001 arg1400 | ACCOMP2 ON | part |
| SEG0F.0x80 | nS0D |  | (no panel event) | unused |
| SEG10.0x01 | nS0E | ev20A4 arg0023 | ONE TOUCH PLAY | HELP-info |
| SEG10.0x02 | nS0E | ev20A6 arg0025 | SPLIT POINT | HELP-info |
| SEG10.0x04 | nS0E | ev2085 arg0216 | VARIATION & MSA | HELP-info |
| SEG10.0x08 | nS0E | ev2085 arg0316 | VARIATION & MSA | legend(event) |
| SEG10.0x10 | nS0E | ev2009 arg0202 | PART SELECT | HELP-info |
| SEG10.0x20 | nS0E | ev2009 arg0102 | PART SELECT | legend(event) |
| SEG10.0x40 | nS0E | ev2009 arg0002 | PART SELECT | legend(event) |
| SEG10.0x80 | nS0E | ev2086 arg0034 | SOLO | HELP-info |
| SEG11.0x01 | nS0F | ev2084 arg0015 | FADE IN/OUT | HELP-info |
| SEG11.0x02 | nS0F | ev2084 arg0115 | FADE IN/OUT | legend(event) |
| SEG11.0x04 | nS0F | ev2023 arg0005 | FILL IN 1/2 | HELP-info |
| SEG11.0x08 | nS0F | ev2023 arg0105 | FILL IN 1/2 | legend(event) |
| SEG11.0x10 | nS0F | ev2008 arg0201 | CONDUCTOR | HELP-info |
| SEG11.0x20 | nS0F | ev2008 arg0101 | CONDUCTOR | legend(event) |
| SEG11.0x40 | nS0F | ev2008 arg0001 | CONDUCTOR | legend(event) |
| SEG11.0x80 | nS0F | ev20A2 arg0021 | TECHNI-CHORD | HELP-info |
| SEG12.0x01 | nS10 | ev2022 arg0005 | INTRO & ENDING | HELP-info |
| SEG12.0x02 | nS10 | ev2022 arg0105 | INTRO & ENDING | legend(event) |
| SEG12.0x04 | nS10 | ev20A1 arg0020 | TAP TEMPO | HELP-info |
| SEG12.0x08 | nS10 | ev2020 arg0004 | START/STOP | HELP-info |
| SEG12.0x10 | nS10 | ev2040 arg0767 | SOUND ARRANGER SET | legend(event) |
| SEG12.0x20 | nS10 | ev2040 arg0363 | SOUND ARRANGER SET | legend(event) |
| SEG12.0x40 | nS10 | ev2040 arg0161 | PROGRAM MENU | HELP-info |
| SEG12.0x80 | nS10 | ev2040 arg0262 | DISK | HELP-info |
| SEG13.0x01 | nS11 | ev2081 arg0013 | TRANSPOSE -/+ | HELP-info |
| SEG13.0x02 | nS11 | ev2081 arg0113 | TRANSPOSE -/+ | legend(event) |
| SEG13.0x04 | nS11 | ev2083 arg0014 | R1/R2 OCTAVE -/+ | HELP-info |
| SEG13.0x08 | nS11 | ev2083 arg0114 | R1/R2 OCTAVE -/+ | legend(event) |
| SEG13.0x10 | nS11 | ev2062 arg0010 | CHORUS | HELP-info |
| SEG13.0x20 | nS11 | ev2061 arg0032 | MULTI EFFECT | HELP-info |
| SEG13.0x40 | nS11 | ev2060 arg0007 | REVERB | HELP-info |
| SEG13.0x80 | nS11 | ev2063 arg0012 | MIC REVERB & EFFECT | HELP-info |
| SEG14.0x01 | INVALID |  | (firmware no-op) | no-op |
| SEG14.0x02 | INVALID |  | (firmware no-op) | no-op |
| SEG14.0x04 | INVALID |  | (firmware no-op) | no-op |
| SEG14.0x08 | INVALID |  | (firmware no-op) | no-op |
| SEG14.0x10 | INVALID |  | (firmware no-op) | no-op |
| SEG14.0x20 | INVALID |  | (firmware no-op) | no-op |
| SEG14.0x40 | INVALID |  | (firmware no-op) | no-op |
| SEG14.0x80 | INVALID |  | (firmware no-op) | no-op |
| SEG15.0x01 | nS12 | ev2040 arg0666 | SOUND ARRANGER SET | legend(event) |
| SEG15.0x02 | nS12 | ev20AE arg0033 | (unnamed) ev20AE arg0033 | UNNAMED |
| SEG15.0x04 | nS12 | ev2021 arg00C0 | SYNCHRO & BREAK | HELP-info |
| SEG15.0x08 | nS12 |  | (no panel event) | unused |
| SEG15.0x10 | nS12 | ev2011 arg000C | (unnamed) ev2011 arg000C | UNNAMED |
| SEG15.0x20 | nS12 | ev2012 arg0003 | (unnamed) ev2012 arg0003 | UNNAMED |
| SEG15.0x40 | nS12 | ev2013 arg0003 | (unnamed) ev2013 arg0003 | UNNAMED |
| SEG15.0x80 | nS12 | ev2016 arg0003 | (unnamed) ev2016 arg0003 | UNNAMED |
| SEG16.0x01 | nS14 |  | (no panel event) | unused |
| SEG16.0x02 | nS14 |  | (no panel event) | unused |
| SEG16.0x04 | nS14 |  | (no panel event) | unused |
| SEG16.0x08 | nS14 |  | (no panel event) | unused |
| SEG16.0x10 | nS14 |  | (no panel event) | unused |
| SEG16.0x20 | nS14 |  | (no panel event) | unused |
| SEG16.0x40 | nS14 |  | (no panel event) | unused |
| SEG16.0x80 | nS14 |  | (no panel event) | unused |
| SEG17.0x01 | nS15 |  | (no panel event) | unused |
| SEG17.0x02 | nS15 |  | (no panel event) | unused |
| SEG17.0x04 | nS15 |  | (no panel event) | unused |
| SEG17.0x08 | nS15 |  | (no panel event) | unused |
| SEG17.0x10 | nS15 |  | (no panel event) | unused |
| SEG17.0x20 | nS15 |  | (no panel event) | unused |
| SEG17.0x40 | nS15 |  | (no panel event) | unused |
| SEG17.0x80 | nS15 |  | (no panel event) | unused |
| SEG18.0x01 | nS16 |  | (no panel event) | unused |
| SEG18.0x02 | nS16 |  | (no panel event) | unused |
| SEG18.0x04 | nS16 |  | (no panel event) | unused |
| SEG18.0x08 | nS16 |  | (no panel event) | unused |
| SEG18.0x10 | nS16 |  | (no panel event) | unused |
| SEG18.0x20 | nS16 |  | (no panel event) | unused |
| SEG18.0x40 | nS16 |  | (no panel event) | unused |
| SEG18.0x80 | nS16 |  | (no panel event) | unused |
| SEG19.0x01 | nS17 |  | (no panel event) | unused |
| SEG19.0x02 | nS17 |  | (no panel event) | unused |
| SEG19.0x04 | nS17 |  | (no panel event) | unused |
| SEG19.0x08 | nS17 |  | (no panel event) | unused |
| SEG19.0x10 | nS17 |  | (no panel event) | unused |
| SEG19.0x20 | nS17 |  | (no panel event) | unused |
| SEG19.0x40 | nS17 |  | (no panel event) | unused |
| SEG19.0x80 | nS17 |  | (no panel event) | unused |
| SEG1A.0x01 | INVALID |  | (firmware no-op) | no-op |
| SEG1A.0x02 | INVALID |  | (firmware no-op) | no-op |
| SEG1A.0x04 | INVALID |  | (firmware no-op) | no-op |
| SEG1A.0x08 | INVALID |  | (firmware no-op) | no-op |
| SEG1A.0x10 | INVALID |  | (firmware no-op) | no-op |
| SEG1A.0x20 | INVALID |  | (firmware no-op) | no-op |
| SEG1A.0x40 | INVALID |  | (firmware no-op) | no-op |
| SEG1A.0x80 | INVALID |  | (firmware no-op) | no-op |
| SEG20.0x01 | nS1D |  | (no panel event) | unused |
| SEG20.0x02 | nS1D |  | (no panel event) | unused |
| SEG20.0x04 | nS1D |  | (no panel event) | unused |
| SEG20.0x08 | nS1D |  | (no panel event) | unused |
| SEG20.0x10 | nS1D |  | (no panel event) | unused |
| SEG20.0x20 | nS1D |  | (no panel event) | unused |
| SEG20.0x40 | nS1D |  | (no panel event) | unused |
| SEG20.0x80 | nS1D |  | (no panel event) | unused |
