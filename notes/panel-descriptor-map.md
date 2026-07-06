# Panel button map: authoritative descriptor extraction vs driver/layout

Extracted directly from the program ROM (`kn7000_program.rom`, maps at CPU
`0x48400000`) — the `PanelButtonDispatch` descriptor arrays via ptr table
`0x48614978`. Each 12-byte entry: `+0..1 event(u16 LE)`, `+4 bitmask`, `+5 bit#`,
`+6 gate`, `+7 arg`, `+8 type`. Script: scratchpad/extract_desc.py + compare.py.

## Headline numbers
- **199** descriptor button-bits across normSeg 0x00–0x23.
- Driver input ports cover SEG00–15 (**155** bits); **44 bits (SEG16–0x23) are MISSING** from the driver.
- The generated `.lay` binds only **72** buttons (`inputtag`) — the rest are decorative.

## The functional bug (why clicking buttons fails)
The layout's button→`SEG.mask` lists (`gen_lay.py` RG/SG/individual `P(...tag=,mask=)`)
were built from an OLDER/WRONG map and are inconsistent with the descriptor. Examples:
- Layout binds **"BALLAD" → SEG00 0x10**, but SEG00.b4 = event **0x2020 = START/STOP**
  (verified working a prior tick). The real BALLAD (event 0x2005) is **SEG01.b3**.
- Layout binds **"PIANO" → SEG0C 0x01**, but SEG0C.b0 = event **0x2086** (an Fn), not a
  sound category. The 0x2004/0x2010 sound-select events sit on other SEG0C–0F bits.
- Layout binds **"INTRO & ENDING" → SEG03 0x10**, but SEG03.b4 = **0x2023 = FILL IN 1**.
So a labelled button either does the wrong thing or (if bound to an unused/context bit)
appears dead. Combined with the 84 unbound (decorative) buttons and the 44 missing
SEG16–23 bits, that is the whole of "many buttons not working."

## Fix direction
Regenerate the layout's button bindings FROM this map: each physical button → the
SEG.bit whose descriptor event matches its function. The DRIVER input-port labels
(below) are descriptor-derived and correct for SEG00–0F; use them as the label source.
Physical left-to-right order within a segment ≈ bit order (switch#=normSeg*8+bit), but
confirm against a panel photo before trusting positions. Also add SEG16–0x23 inputs.

## Per-SEG.bit table (descriptor event / arg  vs  current driver PORT_NAME)
```
SEG.bit  descr-event driver PORT_NAME                 match?
SEG00.0  2000/a13    LCD Left 4                       NAME?
SEG00.1  2000/a10    LCD Left 1                       NAME?
SEG00.2  2000/a14    LCD Left 5                       NAME?
SEG00.3  2000/a11    LCD Left 2                       NAME?
SEG00.4  2020/a00    START/STOP                       NAME?
SEG00.5  2000/a12    LCD Left 3                       NAME?
SEG00.6  2022/a01    INTRO & ENDING 2                 NAME?
SEG00.7  2021/a00    SYNCHRO & BREAK                  NAME?
SEG01.0  2005/a0F    MEMORY/LOAD                      NAME?
SEG01.1  2005/a07    SOUL & FUNK                      NAME?
SEG01.2  2005/a0E    CUSTOM                           NAME?
SEG01.3  2005/a06    BALLAD                           NAME?
SEG01.4  2005/a0D    JAZZ COMBO                       NAME?
SEG01.5  2005/a05    ROCK & POP                       NAME?
SEG01.6  2005/a0C    BIG BAND & SWING                 NAME?
SEG01.7  2005/a04    R & B                            NAME?
SEG02.0  2005/a0B    MOVIE SHOW                       NAME?
SEG02.1  2005/a03    MARCH                            NAME?
SEG02.2  2005/a0A    ENTERTAINER                      NAME?
SEG02.3  2005/a02    COUNTRY                          NAME?
SEG02.4  2005/a09    LATIN & WORLD                    NAME?
SEG02.5  2005/a01    GOSPEL & BLUES                   NAME?
SEG02.6  2005/a08    BALLROOM                         NAME?
SEG02.7  2005/a00    MODERN DANCE                     NAME?
SEG03.0  2022/a00    INTRO & ENDING 1                 NAME?
SEG03.1  20A1/a00    Fn Key 20A1                      ok
SEG03.2  2023/a01    FILL IN 2                        NAME?
SEG03.3  2084/a01    FADE OUT                         NAME?
SEG03.4  2023/a00    FILL IN 1                        NAME?
SEG03.5  2084/a00    FADE IN                          NAME?
SEG03.6  2085/a03    Fn 2085 a3                       ok
SEG03.7  20A6/a00    SPLIT POINT                      NAME?
SEG04.0  2085/a02    VARIATION & MSA 3                NAME?
SEG04.1  20A4/a00    TAP TEMPO                        NAME?
SEG04.2  2085/a01    VARIATION & MSA 2                NAME?
SEG04.3  20A3/a00    MUSIC STYLE ARRANGER             NAME?
SEG04.4  2085/a00    VARIATION & MSA 1                NAME?
SEG04.5  2030/a02    Tempo/Fade 0-2                   NAME?
SEG04.6  2030/a05    VARIATION & MSA 4                NAME?
SEG04.7  2030/a01    Tempo/Fade 0-1                   NAME?
SEG05.0  2000/a19    PAD 5/SOLO                       NAME?
SEG05.1  2040/a04    ONE TOUCH PLAY                   NAME?
SEG05.2  2001/a1D    PAD 4                            NAME?
SEG05.3  2000/a1D    PERFORMANCE PADS BANK            NAME?
SEG05.4  2001/a00    PAD 1                            NAME?
SEG05.5  2000/a00    PAD 3                            NAME?
SEG05.6  2001/a01    PAD 6/SOLO                       NAME?
SEG05.7  2000/a01    Part Mute Down p01               NAME?
SEG06.0  2030/a04    Tempo/Fade 0-4                   NAME?
SEG06.1  2033/a00    PERFORMANCE PADS STOP            NAME?
SEG06.2  2030/a03    SOUND SET                        NAME?
SEG06.3  2032/a00    PLAY CHORD OFF/ON                NAME?
SEG06.4  2030/a00    ARRANGER OFF/ON                  NAME?
SEG06.5  2031/a00    PERFORMANCE PADS AUTO            NAME?
SEG06.6  2040/a00    DEMO                             NAME?
SEG06.7  20B4/a00    Fn Key 20B4                      ok
SEG07.0  2040/a06    MUSIC STYLIST                    NAME?
SEG07.1  20A8/a00    AUTO MODE                        NAME?
SEG07.2  2040/a05    ONE TOUCH PLAY 2                 NAME?
SEG07.3  20A9/a00    Fn Key 20A9                      ok
SEG07.4  20A7/a00    Fn Key 20A7                      ok
SEG08.0  2001/a02    Part Mute Up p02                 NAME?
SEG08.1  2000/a02    Part Mute Down p02               NAME?
SEG08.2  2001/a03    Part Mute Up p03                 NAME?
SEG08.3  2000/a03    Part Mute Down p03               NAME?
SEG08.4  2001/a04    Part Mute Up p04                 NAME?
SEG08.5  2000/a04    Part Mute Down p04               NAME?
SEG08.6  2001/a05    Part Mute Up p05                 NAME?
SEG08.7  2000/a05    Part Mute Down p05               NAME?
SEG09.0  2001/a06    Part Mute Up p06                 NAME?
SEG09.1  2000/a06    Part Mute Down p06               NAME?
SEG09.2  2001/a07    Part Mute Up p07                 NAME?
SEG09.3  2000/a07    Part Mute Down p07               NAME?
SEG09.4  2001/a08    Part Mute Up p08                 NAME?
SEG09.5  2000/a08    Part Mute Down p08               NAME?
SEG09.6  2001/a09    Part Mute Up p09                 NAME?
SEG09.7  2000/a09    Part Mute Down p09               NAME?
SEG0A.0  2001/a0A    Part Mute Up p0A                 NAME?
SEG0A.1  2000/a0A    Part Mute Down p0A               NAME?
SEG0A.2  2001/a0B    Part Mute Up p0B                 NAME?
SEG0A.3  2000/a0B    Part Mute Down p0B               NAME?
SEG0A.4  2001/a0C    Part Mute Up p0C                 NAME?
SEG0A.5  2000/a0C    Part Mute Down p0C               NAME?
SEG0A.6  2001/a0D    Part Mute Up p0D                 NAME?
SEG0A.7  2000/a0D    Part Mute Down p0D               NAME?
SEG0B.0  2001/a0E    Part Mute Up p0E                 NAME?
SEG0B.1  2000/a0E    Part Mute Down p0E               NAME?
SEG0B.2  2001/a0F    Part Mute Up p0F                 NAME?
SEG0B.3  2000/a0F    Part Mute Down p0F               NAME?
SEG0B.4  2001/a18    Part Mute Up p18                 NAME?
SEG0B.5  2000/a18    Part Mute Down p18               NAME?
SEG0B.6  20A0/a00    Fn Key 20A0                      ok
SEG0B.7  2001/a17    Part Mute Up p17                 NAME?
SEG0C.0  2086/a00    Fn 2086 a0                       ok
SEG0C.1  2010/a00    Sound Group 0                    NAME?
SEG0C.2  2040/a01    Fn Toggle 01                     NAME?
SEG0C.3  2040/a03    Fn Toggle 03                     NAME?
SEG0C.4  2004/a04    Sound Select 04                  NAME?
SEG0C.5  2004/a0D    Sound Select 0D                  NAME?
SEG0C.6  2040/a0B    Fn Toggle 0B                     NAME?
SEG0D.0  20A2/a00    Fn Key 20A2                      ok
SEG0D.1  2009/a00    Balance/Ctrl 0 (2009)            ok
SEG0D.2  2040/a02    Fn Toggle 02                     NAME?
SEG0D.3  2040/a07    Fn Toggle 07                     NAME?
SEG0D.4  2004/a03    Sound Select 03                  NAME?
SEG0D.5  2004/a0C    Sound Select 0C                  NAME?
SEG0D.6  2016/a00    Fn 2016                          ok
SEG0D.7  2040/a0A    Fn Toggle 0A                     NAME?
SEG0E.0  2009/a02    Balance/Ctrl 2 (2009)            ok
SEG0E.1  2009/a01    Balance/Ctrl 1 (2009)            ok
SEG0E.2  2063/a00    Fn 2063                          ok
SEG0E.3  20AB/a00    Fn Key 20AB                      ok
SEG0E.4  2004/a02    Sound Select 02                  NAME?
SEG0E.5  2004/a0B    Sound Select 0B                  NAME?
SEG0E.6  20AE/a00    Fn Key 20AE                      ok
SEG0F.0  2081/a01    Fn 2081 a1                       ok
SEG0F.1  2008/a00    Balance/Ctrl 0 (2008)            ok
SEG0F.2  2060/a00    Fn 2060                          ok
SEG0F.3  20AA/a00    Fn Key 20AA                      ok
SEG0F.4  2004/a01    Sound Select 01                  NAME?
SEG0F.5  2004/a0A    Sound Select 0A                  NAME?
SEG0F.6  2010/a04    Sound Group 4                    NAME?
SEG0F.7  2012/a00    Fn 2012                          ok
SEG10.0  2081/a00    Fn 2081 a0                       ok
SEG10.1  2008/a01    Balance/Ctrl 1 (2008)            ok
SEG10.2  2061/a00    Fn 2061                          ok
SEG10.3  2069/a00    Fn 2069                          ok
SEG10.4  2004/a00    Sound Select 00                  NAME?
SEG10.5  2004/a09    Sound Select 09                  NAME?
SEG10.6  2010/a03    Sound Group 3                    NAME?
SEG10.7  2013/a00    Fn 2013                          ok
SEG11.0  2001/a14    Part Mute Up p14                 NAME?
SEG11.1  2008/a02    Balance/Ctrl 2 (2008)            ok
SEG11.2  2062/a00    Fn 2062                          ok
SEG11.3  2068/a00    Fn 2068                          ok
SEG11.4  2001/a10    Part Mute Up p10                 NAME?
SEG11.5  2001/a11    Part Mute Up p11                 NAME?
SEG11.6  2010/a02    Sound Group 2                    NAME?
SEG11.7  2010/a05    Sound Group 5                    NAME?
SEG12.0  2001/a13    Part Mute Up p13                 NAME?
SEG12.1  2083/a01    Fn 2083 a1                       ok
SEG12.2  2004/a11    Sound Select 11                  NAME?
SEG12.3  2004/a08    Sound Select 08                  NAME?
SEG12.6  2010/a01    Sound Group 1                    NAME?
SEG12.7  2010/a06    Sound Group 6                    NAME?
SEG13.0  2001/a12    Part Mute Up p12                 NAME?
SEG13.1  2083/a00    Fn 2083 a0                       ok
SEG13.2  2004/a10    Sound Select 10                  NAME?
SEG13.3  2004/a07    Sound Select 07                  NAME?
SEG13.6  2011/a00    Fn 2011                          ok
SEG13.7  2010/a07    Sound Group 7                    NAME?
SEG14.2  2004/a0F    Sound Select 0F                  NAME?
SEG14.3  2004/a06    Sound Select 06                  NAME?
SEG15.2  2004/a0E    Sound Select 0E                  NAME?
SEG15.3  2004/a05    Sound Select 05                  NAME?
SEG.bits in descriptor but MISSING from driver input ports: 44
SEG.bits in driver but NOT in descriptor (extra/phantom): 0
```

## normSegs 0x16–0x23 (MISSING from driver) — from the descriptor
0x16/0x17 DIAL/DATA (maskFF, 0x1005/0x1004), 0x18–0x1B menu/part events, 0x1D–0x1F
sound-family (0x20B5–0x20BD), 0x20 (0x1020), 0x21–0x23 duplicate rhythm/fill events
(0x2005/0x2030 — likely a second wire path or the LCD-right soft keys). Decode fully
before adding (see extract_desc.py output).

## Layout binding audit (tick 2 — after the RHYTHM GROUP fix)
Cross-checked every `gen_lay.py` binding against the descriptor event + the driver
PORT_NAME (scratchpad/audit_layout.py). Categories:

- **Confirmed CORRECT:** RHYTHM GROUP (SEG01/02, event 0x2005 genres — fixed last tick),
  START/STOP (SEG00.b4=0x2020, verified), the part-mute grid on SEG08–0B.
- **SOUND GROUP (SEG0C–0E):** the layout labels (PIANO…) mismatch the driver's *placeholder*
  names (Fn 2086 / Sound Group 0 / Sound Select 04), but the BINDINGS match the older
  probe-map and hit no *resolved* conflict, so they are probably correct — the driver names
  are just unresolved (events 0x2086/0x2010/0x2040/0x2004 not yet named).
- **Confirmed WRONG (resolved-label conflicts):**
  - INTRO & ENDING → SEG03.b4 = **FILL IN 1** (0x2023). **FIXED → SEG03.b0** (0x2022).
  - FADE IN/OUT → SEG11.b0 = **Part Mute Up p14** (0x2001). **FIXED → SEG03.b5 = FADE IN**
    (0x2084). (FADE OUT is SEG03.b3; the single pill models only the IN half — split TODO.)
  - TRANSPOSE → SEG13.b0/b1 = **Part Mute Up p12 / Fn 2083** — still WRONG; the real
    TRANSPOSE bit is unknown (no resolved descriptor label), so not fixed. Needs event RE.

### The older note `panel-button-normseg-map.md` has ERRORS — trust this descriptor
That note put genres on SEG00 (actually transport/part) and TRANSPOSE/OCTAVE on SEG13
(actually 0x2001 part-mutes / 0x2004 sound-selects). Its unprobed inferences are unreliable;
the probe-verified (`*`) entries mostly hold. **The ROM descriptor extracted here is
authoritative.**

### Blocker for the rest of the layout fix: event resolution
SEG0C–SEG13 mix many unresolved event families — 0x2004 (Sound Select, args a00–a11),
0x2010 (Sound Group, a00–a07), 0x2040 (Fn Toggle), 0x2060–69, 0x2081–86, 0x20A0–BD — while
SEG10–13 are heavily 0x2001 **part-mute-up** (parts 10–14). To bind SOUND GROUP / TRANSPOSE /
menu buttons correctly and confirm the SG probe, resolve these events to functions/names
(trace the 0x00700000|event message handlers, or find the sound-category name table). Until
then only resolved-label conflicts can be fixed safely.
