# KN7000 front-panel button map (authoritative, from firmware data tables)

Derived by decoding the normal-mode button dispatcher's descriptor tables
directly from program ROM (data, so immune to the unidasm 0xF4 bug below).

## Structural findings (workflow-verified, commit this tick)

- The switch-CLASS table 0x4860C9F4 (and its handler 0x484A0CB5) is the
  **panel-test / service-mode** path ONLY, gated by mode flag 0x5006BFB2==1.
  It is a switch->indicator-LED map ([LED-register, value]), never touched
  in normal operation. (This is why PC-probing 0x484A0D27 saw 0 hits.)
- The **normal-mode dispatcher is 0x484ADB59**. It reads per-segment
  descriptor arrays via pointer tables 0x48614978 (bank A) / 0x486149FC
  (bank B), indexed by normalized segment (normSeg, 0x00-0x20).
- Descriptor = 12 bytes: +0 u32 eventCode (0xFFFFFFFF = array terminator),
  +4 mask (the button's bit), +5 shift, +6 gate (hi nibble = mode-var
  selector into 0x48614BC4 reading 0x5006BF9C.., lo nibble = required bit;
  checker 0x484ADCA0), +7 argHigh, +8 type (0=momentary post, 1=START/STOP-
  style w/ beep, 2/3/4 = continuous-control segs 0x16-0x20).
- Event posted = 0x10000000 + eventCode, d1 = (argHigh<<8)|bit-or-value.
- **The KN7000 uses BANK A**: seg00 bit4 = ev 0x00702020 (START/STOP,
  MAME-verified press) and seg0C bit1 = ev 0x00702010 arg0 (sound-group,
  MAME-verified GUITAR page) both match bank A, not bank B.
- Wire ADDR -> normSeg via normalization table 0x486135A0 (runtime code at
  the dispatcher; wire idx = ((ADDR&0xC0)>>1)|(ADDR&0x1F)).
- **unidasm caveat**: the MN10300 disassembler mis-decodes opcode 0xF4
  'movbu (di,am),dn' as 1 byte instead of 2, desyncing every address after
  it in a listing. Cross-check any 0x484A0Dxx-style address against the
  emulator's real execution; prefer decoding DATA tables over code.

## Event-code families (bank A, from the descriptors below)

- 0x00702005 arg 0x00-0x0F : the 16 RHYTHM-STYLE group buttons (segs 01,02)
- 0x00702000 / 0x00702001  : paired part MUTE down/up, arg = part (segs 08-0B = the 16 mixer mutes; also seg05,11-13)
- 0x00702010 arg 0x00-0x07 : the 8 SOUND-GROUP select keys (segs 0C,0F,10,11,12,13)
- 0x00702020 (type1)       : START/STOP (seg00 bit4)
- 0x00702021/22/23         : transport latches (INTRO/ENDING, SYNCHRO, FILL) (seg00 bits6/7, seg03)
- 0x00702030-33            : fade / tempo / count section (segs 04,06)
- 0x00702040               : sound/effect toggles, arg-selected (many segs)
- 0x00702060-63,68,69,81,83,84,85,86 : per-function toggles (DSP, techni-chord, etc.)
- 0x0070200x arg (segs 16-20, type 2/3/4) : continuous controls (sliders/wheels/pedals)
- 0x007020A0-BD            : one-shot function keys (menus, disk, custom, etc.)

## Bank A (KN7000 ACTIVE) — ptr table 48614978

```
normSeg 00 -> 486136A0
    bit0 mask01: ev=00702000 arg=13 typ=0 gate=00
    bit1 mask02: ev=00702000 arg=10 typ=0 gate=00
    bit2 mask04: ev=00702000 arg=14 typ=0 gate=00
    bit3 mask08: ev=00702000 arg=11 typ=0 gate=00
    bit4 mask10: ev=00702020 arg=00 typ=1 gate=04
    bit5 mask20: ev=00702000 arg=12 typ=0 gate=00
    bit6 mask40: ev=00702022 arg=01 typ=0 gate=05
    bit7 mask80: ev=00702021 arg=00 typ=0 gate=C0
normSeg 01 -> 4861370C
    bit0 mask01: ev=00702005 arg=0F typ=0 gate=51
    bit1 mask02: ev=00702005 arg=07 typ=0 gate=5F
    bit2 mask04: ev=00702005 arg=0E typ=0 gate=50
    bit3 mask08: ev=00702005 arg=06 typ=0 gate=5F
    bit4 mask10: ev=00702005 arg=0D typ=0 gate=5F
    bit5 mask20: ev=00702005 arg=05 typ=0 gate=5F
    bit6 mask40: ev=00702005 arg=0C typ=0 gate=5F
    bit7 mask80: ev=00702005 arg=04 typ=0 gate=5F
normSeg 02 -> 48613778
    bit0 mask01: ev=00702005 arg=0B typ=0 gate=5F
    bit1 mask02: ev=00702005 arg=03 typ=0 gate=5F
    bit2 mask04: ev=00702005 arg=0A typ=0 gate=5F
    bit3 mask08: ev=00702005 arg=02 typ=0 gate=5F
    bit4 mask10: ev=00702005 arg=09 typ=0 gate=5F
    bit5 mask20: ev=00702005 arg=01 typ=0 gate=5F
    bit6 mask40: ev=00702005 arg=08 typ=0 gate=5F
    bit7 mask80: ev=00702005 arg=00 typ=0 gate=5F
normSeg 03 -> 486137E4
    bit0 mask01: ev=00702022 arg=00 typ=0 gate=05
    bit1 mask02: ev=007020A1 arg=00 typ=0 gate=20
    bit2 mask04: ev=00702023 arg=01 typ=0 gate=05
    bit3 mask08: ev=00702084 arg=01 typ=0 gate=15
    bit4 mask10: ev=00702023 arg=00 typ=0 gate=05
    bit5 mask20: ev=00702084 arg=00 typ=0 gate=15
    bit6 mask40: ev=00702085 arg=03 typ=0 gate=16
    bit7 mask80: ev=007020A6 arg=00 typ=0 gate=25
normSeg 04 -> 48613850
    bit0 mask01: ev=00702085 arg=02 typ=0 gate=16
    bit1 mask02: ev=007020A4 arg=00 typ=0 gate=23
    bit2 mask04: ev=00702085 arg=01 typ=0 gate=16
    bit3 mask08: ev=007020A3 arg=00 typ=0 gate=22
    bit4 mask10: ev=00702085 arg=00 typ=0 gate=16
    bit5 mask20: ev=00702030 arg=02 typ=0 gate=06
    bit6 mask40: ev=00702030 arg=05 typ=0 gate=06
    bit7 mask80: ev=00702030 arg=01 typ=0 gate=06
normSeg 05 -> 486138BC
    bit0 mask01: ev=00702000 arg=19 typ=0 gate=00
    bit1 mask02: ev=00702040 arg=04 typ=0 gate=64
    bit2 mask04: ev=00702001 arg=1D typ=0 gate=08
    bit3 mask08: ev=00702000 arg=1D typ=0 gate=08
    bit4 mask10: ev=00702001 arg=00 typ=0 gate=00
    bit5 mask20: ev=00702000 arg=00 typ=0 gate=00
    bit6 mask40: ev=00702001 arg=01 typ=0 gate=00
    bit7 mask80: ev=00702000 arg=01 typ=0 gate=00
normSeg 06 -> 48613928
    bit0 mask01: ev=00702030 arg=04 typ=0 gate=06
    bit1 mask02: ev=00702033 arg=00 typ=0 gate=06
    bit2 mask04: ev=00702030 arg=03 typ=0 gate=06
    bit3 mask08: ev=00702032 arg=00 typ=0 gate=06
    bit4 mask10: ev=00702030 arg=00 typ=0 gate=06
    bit5 mask20: ev=00702031 arg=00 typ=0 gate=06
    bit6 mask40: ev=00702040 arg=00 typ=0 gate=60
    bit7 mask80: ev=007020B4 arg=00 typ=0 gate=00
normSeg 07 -> 48613994
    bit0 mask01: ev=00702040 arg=06 typ=0 gate=66
    bit1 mask02: ev=007020A8 arg=00 typ=0 gate=27
    bit2 mask04: ev=00702040 arg=05 typ=0 gate=65
    bit3 mask08: ev=007020A9 arg=00 typ=0 gate=27
    bit4 mask10: ev=007020A7 arg=00 typ=0 gate=26
normSeg 08 -> 486139DC
    bit0 mask01: ev=00702001 arg=02 typ=0 gate=00
    bit1 mask02: ev=00702000 arg=02 typ=0 gate=00
    bit2 mask04: ev=00702001 arg=03 typ=0 gate=00
    bit3 mask08: ev=00702000 arg=03 typ=0 gate=00
    bit4 mask10: ev=00702001 arg=04 typ=0 gate=00
    bit5 mask20: ev=00702000 arg=04 typ=0 gate=00
    bit6 mask40: ev=00702001 arg=05 typ=0 gate=00
    bit7 mask80: ev=00702000 arg=05 typ=0 gate=00
normSeg 09 -> 48613A48
    bit0 mask01: ev=00702001 arg=06 typ=0 gate=00
    bit1 mask02: ev=00702000 arg=06 typ=0 gate=00
    bit2 mask04: ev=00702001 arg=07 typ=0 gate=00
    bit3 mask08: ev=00702000 arg=07 typ=0 gate=00
    bit4 mask10: ev=00702001 arg=08 typ=0 gate=00
    bit5 mask20: ev=00702000 arg=08 typ=0 gate=00
    bit6 mask40: ev=00702001 arg=09 typ=0 gate=00
    bit7 mask80: ev=00702000 arg=09 typ=0 gate=00
normSeg 0A -> 48613AB4
    bit0 mask01: ev=00702001 arg=0A typ=0 gate=00
    bit1 mask02: ev=00702000 arg=0A typ=0 gate=00
    bit2 mask04: ev=00702001 arg=0B typ=0 gate=00
    bit3 mask08: ev=00702000 arg=0B typ=0 gate=00
    bit4 mask10: ev=00702001 arg=0C typ=0 gate=00
    bit5 mask20: ev=00702000 arg=0C typ=0 gate=00
    bit6 mask40: ev=00702001 arg=0D typ=0 gate=00
    bit7 mask80: ev=00702000 arg=0D typ=0 gate=00
normSeg 0B -> 48613B20
    bit0 mask01: ev=00702001 arg=0E typ=0 gate=00
    bit1 mask02: ev=00702000 arg=0E typ=0 gate=00
    bit2 mask04: ev=00702001 arg=0F typ=0 gate=00
    bit3 mask08: ev=00702000 arg=0F typ=0 gate=00
    bit4 mask10: ev=00702001 arg=18 typ=0 gate=00
    bit5 mask20: ev=00702000 arg=18 typ=0 gate=00
    bit6 mask40: ev=007020A0 arg=00 typ=0 gate=17
    bit7 mask80: ev=00702001 arg=17 typ=0 gate=00
normSeg 0C -> 48613B8C
    bit0 mask01: ev=00702086 arg=00 typ=0 gate=34
    bit1 mask02: ev=00702010 arg=00 typ=0 gate=03
    bit2 mask04: ev=00702040 arg=01 typ=0 gate=61
    bit3 mask08: ev=00702040 arg=03 typ=0 gate=63
    bit4 mask10: ev=00702004 arg=04 typ=0 gate=43
    bit5 mask20: ev=00702004 arg=0D typ=0 gate=4F
    bit6 mask40: ev=00702040 arg=0B typ=0 gate=6B
normSeg 0D -> 48613BEC
    bit0 mask01: ev=007020A2 arg=00 typ=0 gate=21
    bit1 mask02: ev=00702009 arg=00 typ=0 gate=02
    bit2 mask04: ev=00702040 arg=02 typ=0 gate=62
    bit3 mask08: ev=00702040 arg=07 typ=0 gate=67
    bit4 mask10: ev=00702004 arg=03 typ=0 gate=4F
    bit5 mask20: ev=00702004 arg=0C typ=0 gate=4F
    bit6 mask40: ev=00702016 arg=00 typ=0 gate=03
    bit7 mask80: ev=00702040 arg=0A typ=0 gate=6A
normSeg 0E -> 48613C58
    bit0 mask01: ev=00702009 arg=02 typ=0 gate=02
    bit1 mask02: ev=00702009 arg=01 typ=0 gate=02
    bit2 mask04: ev=00702063 arg=00 typ=0 gate=12
    bit3 mask08: ev=007020AB arg=00 typ=0 gate=31
    bit4 mask10: ev=00702004 arg=02 typ=0 gate=4F
    bit5 mask20: ev=00702004 arg=0B typ=0 gate=4F
    bit6 mask40: ev=007020AE arg=00 typ=0 gate=33
normSeg 0F -> 48613CB8
    bit0 mask01: ev=00702081 arg=01 typ=0 gate=13
    bit1 mask02: ev=00702008 arg=00 typ=0 gate=01
    bit2 mask04: ev=00702060 arg=00 typ=0 gate=07
    bit3 mask08: ev=007020AA arg=00 typ=0 gate=31
    bit4 mask10: ev=00702004 arg=01 typ=0 gate=4F
    bit5 mask20: ev=00702004 arg=0A typ=0 gate=41
    bit6 mask40: ev=00702010 arg=04 typ=0 gate=03
    bit7 mask80: ev=00702012 arg=00 typ=0 gate=03
normSeg 10 -> 48613D24
    bit0 mask01: ev=00702081 arg=00 typ=0 gate=13
    bit1 mask02: ev=00702008 arg=01 typ=0 gate=01
    bit2 mask04: ev=00702061 arg=00 typ=0 gate=32
    bit3 mask08: ev=00702069 arg=00 typ=0 gate=30
    bit4 mask10: ev=00702004 arg=00 typ=0 gate=4F
    bit5 mask20: ev=00702004 arg=09 typ=0 gate=41
    bit6 mask40: ev=00702010 arg=03 typ=0 gate=03
    bit7 mask80: ev=00702013 arg=00 typ=0 gate=03
normSeg 11 -> 48613D90
    bit0 mask01: ev=00702001 arg=14 typ=0 gate=00
    bit1 mask02: ev=00702008 arg=02 typ=0 gate=01
    bit2 mask04: ev=00702062 arg=00 typ=0 gate=10
    bit3 mask08: ev=00702068 arg=00 typ=0 gate=11
    bit4 mask10: ev=00702001 arg=10 typ=0 gate=00
    bit5 mask20: ev=00702001 arg=11 typ=0 gate=00
    bit6 mask40: ev=00702010 arg=02 typ=0 gate=03
    bit7 mask80: ev=00702010 arg=05 typ=0 gate=03
normSeg 12 -> 48613DFC
    bit0 mask01: ev=00702001 arg=13 typ=0 gate=00
    bit1 mask02: ev=00702083 arg=01 typ=0 gate=14
    bit2 mask04: ev=00702004 arg=11 typ=0 gate=44
    bit3 mask08: ev=00702004 arg=08 typ=0 gate=43
    bit6 mask40: ev=00702010 arg=01 typ=0 gate=03
    bit7 mask80: ev=00702010 arg=06 typ=0 gate=03
normSeg 13 -> 48613E50
    bit0 mask01: ev=00702001 arg=12 typ=0 gate=00
    bit1 mask02: ev=00702083 arg=00 typ=0 gate=14
    bit2 mask04: ev=00702004 arg=10 typ=0 gate=42
    bit3 mask08: ev=00702004 arg=07 typ=0 gate=4F
    bit6 mask40: ev=00702011 arg=00 typ=0 gate=0C
    bit7 mask80: ev=00702010 arg=07 typ=0 gate=03
normSeg 14 -> 48613EA4
    bit2 mask04: ev=00702004 arg=0F typ=0 gate=40
    bit3 mask08: ev=00702004 arg=06 typ=0 gate=4F
normSeg 15 -> 48613EC8
    bit2 mask04: ev=00702004 arg=0E typ=0 gate=4F
    bit3 mask08: ev=00702004 arg=05 typ=0 gate=4F
normSeg 16 -> 48613EEC
    bit0 maskFF: ev=00701005 arg=00 typ=2 gate=92
normSeg 17 -> 48613F04
    bit0 maskFF: ev=00701004 arg=00 typ=4 gate=91
normSeg 18 -> 48613F1C
    bit0 maskFF: ev=00701009 arg=00 typ=2 gate=94
normSeg 19 -> 48613F34
    bit0 maskFF: ev=00701010 arg=00 typ=2 gate=81
normSeg 1A -> 48613F4C
    bit0 maskFF: ev=00701011 arg=00 typ=2 gate=90
normSeg 1B -> 48613F64
    bit0 mask01: ev=00701000 arg=05 typ=3 gate=80
    bit1 mask02: ev=00701000 arg=04 typ=3 gate=80
    bit2 mask04: ev=00701000 arg=03 typ=3 gate=80
    bit3 mask08: ev=00701000 arg=02 typ=3 gate=80
    bit4 mask10: ev=00701000 arg=01 typ=3 gate=80
    bit5 mask20: ev=00701000 arg=00 typ=3 gate=80
normSeg 1D -> 48613FC4
    bit0 mask01: ev=007020B5 arg=00 typ=0 gate=C8
    bit1 mask02: ev=007020B6 arg=00 typ=0 gate=C9
    bit2 mask04: ev=007020B7 arg=00 typ=0 gate=CA
    bit3 mask08: ev=007020B8 arg=00 typ=0 gate=CB
    bit4 mask10: ev=007020B9 arg=00 typ=0 gate=CC
    bit5 mask20: ev=007020BA arg=00 typ=0 gate=CD
normSeg 1E -> 48614018
    bit0 mask01: ev=007020BB arg=00 typ=0 gate=00
normSeg 1F -> 48614030
    bit0 mask01: ev=007020BD arg=00 typ=0 gate=00
normSeg 20 -> 48614048
    bit0 maskFF: ev=00701020 arg=00 typ=2 gate=96
```

## Bank B (other layout, reference) — ptr table 486149FC

```
normSeg 00 -> 48614060
    bit0 mask01: ev=00702030 arg=00 typ=0 gate=06
    bit1 mask02: ev=00702030 arg=03 typ=0 gate=06
    bit2 mask04: ev=00702005 arg=00 typ=0 gate=5F
    bit3 mask08: ev=00702005 arg=01 typ=0 gate=5F
    bit4 mask10: ev=00702005 arg=02 typ=0 gate=5F
    bit5 mask20: ev=00702005 arg=03 typ=0 gate=5F
    bit6 mask40: ev=00702005 arg=04 typ=0 gate=5F
    bit7 mask80: ev=00702005 arg=05 typ=0 gate=5F
normSeg 01 -> 486140CC
    bit0 mask01: ev=00702030 arg=01 typ=0 gate=06
    bit1 mask02: ev=00702030 arg=04 typ=0 gate=06
    bit2 mask04: ev=00702005 arg=06 typ=0 gate=5F
    bit3 mask08: ev=00702005 arg=07 typ=0 gate=5F
    bit4 mask10: ev=00702005 arg=08 typ=0 gate=5F
    bit5 mask20: ev=00702005 arg=09 typ=0 gate=5F
    bit6 mask40: ev=00702005 arg=0A typ=0 gate=5F
    bit7 mask80: ev=00702005 arg=0B typ=0 gate=5F
normSeg 02 -> 48614138
    bit0 mask01: ev=00702030 arg=02 typ=0 gate=06
    bit1 mask02: ev=00702030 arg=05 typ=0 gate=06
    bit2 mask04: ev=00702005 arg=0C typ=0 gate=5F
    bit3 mask08: ev=00702005 arg=0D typ=0 gate=5F
    bit4 mask10: ev=00702005 arg=0E typ=0 gate=5F
    bit5 mask20: ev=00702005 arg=0F typ=0 gate=5F
    bit6 mask40: ev=00702040 arg=05 typ=0 gate=65
    bit7 mask80: ev=007020A7 arg=00 typ=0 gate=26
normSeg 03 -> 486141A4
    bit1 mask02: ev=007020A8 arg=00 typ=0 gate=27
    bit2 mask04: ev=007020A9 arg=00 typ=0 gate=27
    bit3 mask08: ev=00702000 arg=10 typ=0 gate=00
    bit4 mask10: ev=00702000 arg=11 typ=0 gate=00
    bit5 mask20: ev=00702000 arg=12 typ=0 gate=00
    bit6 mask40: ev=00702000 arg=13 typ=0 gate=00
    bit7 mask80: ev=00702000 arg=14 typ=0 gate=00
normSeg 04 -> 48614204
    bit0 mask01: ev=00702001 arg=00 typ=0 gate=00
    bit1 mask02: ev=00702000 arg=00 typ=0 gate=00
    bit2 mask04: ev=00702001 arg=01 typ=0 gate=00
    bit3 mask08: ev=00702000 arg=01 typ=0 gate=00
    bit4 mask10: ev=00702001 arg=02 typ=0 gate=00
    bit5 mask20: ev=00702000 arg=02 typ=0 gate=00
    bit6 mask40: ev=00702001 arg=03 typ=0 gate=00
    bit7 mask80: ev=00702000 arg=03 typ=0 gate=00
normSeg 05 -> 48614270
    bit0 mask01: ev=00702001 arg=04 typ=0 gate=00
    bit1 mask02: ev=00702000 arg=04 typ=0 gate=00
    bit2 mask04: ev=00702001 arg=05 typ=0 gate=00
    bit3 mask08: ev=00702000 arg=05 typ=0 gate=00
    bit4 mask10: ev=00702001 arg=06 typ=0 gate=00
    bit5 mask20: ev=00702000 arg=06 typ=0 gate=00
    bit6 mask40: ev=00702001 arg=07 typ=0 gate=00
    bit7 mask80: ev=00702000 arg=07 typ=0 gate=00
normSeg 06 -> 486142DC
    bit0 mask01: ev=00702001 arg=08 typ=0 gate=00
    bit1 mask02: ev=00702000 arg=08 typ=0 gate=00
    bit2 mask04: ev=00702001 arg=09 typ=0 gate=00
    bit3 mask08: ev=00702000 arg=09 typ=0 gate=00
    bit4 mask10: ev=00702001 arg=0A typ=0 gate=00
    bit5 mask20: ev=00702000 arg=0A typ=0 gate=00
    bit6 mask40: ev=00702001 arg=0B typ=0 gate=00
    bit7 mask80: ev=00702000 arg=0B typ=0 gate=00
normSeg 07 -> 48614348
    bit0 mask01: ev=00702001 arg=0C typ=0 gate=00
    bit1 mask02: ev=00702000 arg=0C typ=0 gate=00
    bit2 mask04: ev=00702001 arg=0D typ=0 gate=00
    bit3 mask08: ev=00702000 arg=0D typ=0 gate=00
    bit4 mask10: ev=00702001 arg=0E typ=0 gate=00
    bit5 mask20: ev=00702000 arg=0E typ=0 gate=00
    bit6 mask40: ev=00702001 arg=0F typ=0 gate=00
    bit7 mask80: ev=00702000 arg=0F typ=0 gate=00
normSeg 08 -> 486143B4
    bit0 mask01: ev=00702001 arg=18 typ=0 gate=00
    bit1 mask02: ev=00702000 arg=18 typ=0 gate=00
    bit2 mask04: ev=00702000 arg=19 typ=0 gate=00
    bit3 mask08: ev=00702040 arg=04 typ=0 gate=64
    bit4 mask10: ev=007020A0 arg=00 typ=0 gate=17
    bit5 mask20: ev=00702001 arg=17 typ=0 gate=00
    bit6 mask40: ev=007020AD arg=00 typ=0 gate=37
    bit7 mask80: ev=007020AC arg=00 typ=0 gate=37
normSeg 09 -> 48614420
    bit0 mask01: ev=00702032 arg=00 typ=0 gate=06
    bit1 mask02: ev=00702033 arg=00 typ=0 gate=06
    bit2 mask04: ev=00702031 arg=00 typ=0 gate=06
    bit3 mask08: ev=007020A3 arg=00 typ=0 gate=22
    bit4 mask10: ev=00702085 arg=00 typ=0 gate=16
    bit5 mask20: ev=00702085 arg=01 typ=0 gate=16
    bit6 mask40: ev=00702040 arg=00 typ=0 gate=60
normSeg 0A -> 48614480
    bit0 mask01: ev=00702004 arg=00 typ=0 gate=4F
    bit1 mask02: ev=00702004 arg=01 typ=0 gate=4F
    bit2 mask04: ev=00702004 arg=02 typ=0 gate=4F
    bit3 mask08: ev=00702004 arg=03 typ=0 gate=4F
    bit4 mask10: ev=00702004 arg=04 typ=0 gate=4F
    bit5 mask20: ev=00702004 arg=05 typ=0 gate=43
normSeg 0B -> 486144D4
    bit0 mask01: ev=00702004 arg=06 typ=0 gate=4F
    bit1 mask02: ev=00702004 arg=07 typ=0 gate=4F
    bit2 mask04: ev=00702004 arg=08 typ=0 gate=4F
    bit3 mask08: ev=00702004 arg=09 typ=0 gate=4F
    bit4 mask10: ev=00702004 arg=0A typ=0 gate=40
    bit5 mask20: ev=00702004 arg=0B typ=0 gate=42
normSeg 0C -> 48614528
    bit0 mask01: ev=00702004 arg=0C typ=0 gate=4F
    bit1 mask02: ev=00702004 arg=0D typ=0 gate=4F
    bit2 mask04: ev=00702004 arg=0E typ=0 gate=4F
    bit3 mask08: ev=00702004 arg=0F typ=0 gate=4F
    bit4 mask10: ev=00702068 arg=00 typ=0 gate=11
    bit5 mask20: ev=00702069 arg=00 typ=0 gate=30
normSeg 0D -> 4861457C
    bit0 mask01: ev=007020AA arg=00 typ=0 gate=31
    bit1 mask02: ev=007020AB arg=00 typ=0 gate=31
    bit2 mask04: ev=00702001 arg=10 typ=0 gate=00
    bit3 mask08: ev=00702001 arg=11 typ=0 gate=00
    bit4 mask10: ev=00702001 arg=12 typ=0 gate=00
    bit5 mask20: ev=00702001 arg=13 typ=0 gate=00
    bit6 mask40: ev=00702001 arg=14 typ=0 gate=00
normSeg 0E -> 486145DC
    bit0 mask01: ev=007020A4 arg=00 typ=0 gate=23
    bit1 mask02: ev=007020A6 arg=00 typ=0 gate=25
    bit2 mask04: ev=00702085 arg=02 typ=0 gate=16
    bit3 mask08: ev=00702085 arg=03 typ=0 gate=16
    bit4 mask10: ev=00702009 arg=02 typ=0 gate=02
    bit5 mask20: ev=00702009 arg=01 typ=0 gate=02
    bit6 mask40: ev=00702009 arg=00 typ=0 gate=02
    bit7 mask80: ev=00702086 arg=00 typ=0 gate=34
normSeg 0F -> 48614648
    bit0 mask01: ev=00702084 arg=00 typ=0 gate=15
    bit1 mask02: ev=00702084 arg=01 typ=0 gate=15
    bit2 mask04: ev=00702023 arg=00 typ=0 gate=05
    bit3 mask08: ev=00702023 arg=01 typ=0 gate=05
    bit4 mask10: ev=00702008 arg=02 typ=0 gate=01
    bit5 mask20: ev=00702008 arg=01 typ=0 gate=01
    bit6 mask40: ev=00702008 arg=00 typ=0 gate=01
    bit7 mask80: ev=007020A2 arg=00 typ=0 gate=21
normSeg 10 -> 486146B4
    bit0 mask01: ev=00702022 arg=00 typ=0 gate=05
    bit1 mask02: ev=00702022 arg=01 typ=0 gate=05
    bit2 mask04: ev=007020A1 arg=00 typ=0 gate=20
    bit3 mask08: ev=00702020 arg=00 typ=1 gate=04
    bit4 mask10: ev=00702040 arg=07 typ=0 gate=67
    bit5 mask20: ev=00702040 arg=03 typ=0 gate=63
    bit6 mask40: ev=00702040 arg=01 typ=0 gate=61
    bit7 mask80: ev=00702040 arg=02 typ=0 gate=62
normSeg 11 -> 48614720
    bit0 mask01: ev=00702081 arg=00 typ=0 gate=13
    bit1 mask02: ev=00702081 arg=01 typ=0 gate=13
    bit2 mask04: ev=00702083 arg=00 typ=0 gate=14
    bit3 mask08: ev=00702083 arg=01 typ=0 gate=14
    bit4 mask10: ev=00702062 arg=00 typ=0 gate=10
    bit5 mask20: ev=00702061 arg=00 typ=0 gate=32
    bit6 mask40: ev=00702060 arg=00 typ=0 gate=07
    bit7 mask80: ev=00702063 arg=00 typ=0 gate=12
normSeg 12 -> 4861478C
    bit0 mask01: ev=00702040 arg=06 typ=0 gate=66
    bit1 mask02: ev=007020AE arg=00 typ=0 gate=33
    bit2 mask04: ev=00702021 arg=00 typ=0 gate=C0
    bit4 mask10: ev=00702011 arg=00 typ=0 gate=0C
    bit5 mask20: ev=00702012 arg=00 typ=0 gate=03
    bit6 mask40: ev=00702013 arg=00 typ=0 gate=03
    bit7 mask80: ev=00702016 arg=00 typ=0 gate=03
normSeg 13 -> 486147EC
    bit0 mask01: ev=00702010 arg=00 typ=0 gate=03
    bit1 mask02: ev=00702010 arg=01 typ=0 gate=03
    bit2 mask04: ev=00702010 arg=02 typ=0 gate=03
    bit3 mask08: ev=00702010 arg=03 typ=0 gate=03
    bit4 mask10: ev=00702010 arg=04 typ=0 gate=03
    bit5 mask20: ev=00702010 arg=05 typ=0 gate=03
    bit6 mask40: ev=00702010 arg=06 typ=0 gate=03
    bit7 mask80: ev=00702010 arg=07 typ=0 gate=03
normSeg 14 -> 48614858
    bit0 maskFF: ev=00701011 arg=00 typ=2 gate=90
normSeg 15 -> 48614870
    bit0 maskFF: ev=00701004 arg=00 typ=4 gate=91
normSeg 16 -> 48614888
    bit0 maskFF: ev=00701010 arg=00 typ=2 gate=81
normSeg 17 -> 486148A0
    bit0 maskFF: ev=00701005 arg=00 typ=2 gate=92
normSeg 18 -> 486148B8
    bit0 maskFF: ev=00701012 arg=00 typ=2 gate=95
normSeg 19 -> 486148D0
    bit0 maskFF: ev=00701012 arg=00 typ=2 gate=95
normSeg 1A -> 486148E8
    bit0 maskFF: ev=00701009 arg=00 typ=2 gate=94
normSeg 1B -> 48614900
    bit0 mask01: ev=00701000 arg=00 typ=3 gate=80
    bit1 mask02: ev=00701000 arg=00 typ=3 gate=80
    bit2 mask04: ev=00701000 arg=00 typ=3 gate=80
    bit3 mask08: ev=00701000 arg=00 typ=3 gate=80
    bit4 mask10: ev=00701000 arg=00 typ=3 gate=80
    bit5 mask20: ev=00701000 arg=00 typ=3 gate=80
normSeg 1D -> 48614960
    bit0 maskFF: ev=00701020 arg=00 typ=2 gate=96
```


## Driver-wiring audit vs the authoritative map (2026-07-05)

Cross-checking the current kn7000.cpp panel_scan wiring against bank A:

- **CPL_SEG0-7 -> normSeg 0x00-0x07: CORRECT.** START/STOP (00.b4), the 16
  rhythm-style groups (0x702005 args 0-F across segs 01/02), variation/arranger
  (03/04), pads (05), fade/tempo (06), and the seg-07 function keys all land on
  their real events. Keep as-is.

- **CPC_SEG0-4 -> normSeg 0x0C-0x10: MIS-ASSIGNED.** These normSegs are the
  SOUND-GROUP / right-panel function events (0x702010 sound groups, 0x702004,
  0x702081, 0x702008...). The driver labels them OTHER PARTS/TG, HELP, CONTRAST,
  MUTE UP/DOWN -- wrong. (Empirically, pressing "HELP" = CPC_SEG0.b1 opened the
  GUITAR sound page = 0x702010 arg0, confirming the mismatch.)

- **CPR_SEG5-8 -> normSeg 0x08-0x0B: MIS-ASSIGNED.** These are the 16 mixer
  MUTES: paired events 0x702001 (up) / 0x702000 (down), arg = part 0x02-0x18,
  8 buttons/seg x 4 segs = 32 = MUTE UP/DOWN 1-16. The driver labels them LCD
  Right / TRANSPOSE / CHORUS -- wrong. CPR_SEG9 (bank11 sub0xC) normalizes to
  0xFF (invalid) and should not exist.

CONCLUSION: the physical-board->wireADDR guess is right for CPL but wrong for
CPC/CPR. Because the firmware only cares about normSeg, the robust fix is to
STOP guessing physical boards and instead define the input ports BY normSeg
(0x00-0x15 momentary + 0x16-0x20 continuous), naming each bit from its event
code here, and have panel_scan emit the reverse-normalized wireADDR for each
normSeg (bank11 subs 0-0xB -> segs 00-0B; bank00 subs 0-9 -> segs 0C-15). The
artwork can group the named fields by real board cosmetically. This makes every
button functionally correct by construction. (Next tick: the mechanical rewrite,
verified by re-pressing START/STOP + a mute + a sound group.)

### Reverse normalization (normSeg -> wire ADDR to emit)
normSeg 0x00-0x0B: bank11 (ADDR = 0xC0 | (seg<=7? seg : 0x08|(seg-8... )));
  precisely: sub = seg for seg 0-0xB; ADDR = 0xC0 | (sub&7) | (sub&8?0x08:0).
normSeg 0x0C-0x15: bank00, sub = seg-0x0C; ADDR = (sub&7) | (sub&8?0x08:0).
(type-1 encoding bit3 auto-applies for sub>=8, matching the wire rule.)

## Reorganization DONE (2026-07-05, commit 57d2193)

The driver inputs are now one ioport per normalized segment (SEG00..SEG15);
panel_scan emits the reverse-normalized wire address per segment, so every
button reaches its intended firmware event by construction. Verified by scripted
presses: SEG00.b4 = START/STOP -> rhythm; SEG0C.b1 = sound-group -> GUITAR page;
SEG08.b0 = mixer -> scrolled the sound list. The .lay was remapped
behavior-preservingly (old board button -> SEG port with the same normSeg).

REMAINING (layout polish, not wiring): the artwork's on-screen LABELS + button
POSITIONS still reflect the old physical-board transcription (e.g. the CPC cells
say "MUTE UP 1" but now click a sound-select function, because that physical
position's true normSeg carries a sound event). To finish: relabel/reposition
the CPC/CPR artwork from the event map, and decode the arg->genre (0x702005) and
arg->sound-group (0x702010) / arg->part (0x702000/01) sub-tables to give the
rhythm/sound/mute buttons their exact product names.

## Rhythm-genre (0x702005) arg decode — table found, wiring deferred (2026-07-05)

Located the rhythm-GROUP name table in program ROM at **0x48735EE4** (16 records,
stride 0x18, each a 2-byte "[H" LCD-home prefix + centred name):
  idx 0 8&16 BEAT     1 ROCK & POP    2 BALLAD        3 JAZZ & SWING
  idx 4 BALLROOM      5 MOVIE & SHOW  6 ENTERTAINER   7 ORGANIST
  idx 8 60s & 70s     9 MODERN DANCE  A SOUL & R&B    B COUNTRY&WESTERN
  idx C MARCH & WALTZ D LATIN & WORLD E CUSTOM        F MEMORY

The 0x702005 event's `arg` is NOT a direct index. A rotation table
**[7,8,9,A,B,C,D,E,F,0,1,2,3,4,5,6]** appears 3x in ROM (e.g. 0x485B920F);
i.e. **genre_index = (arg + 7) mod 16**. CONFIRMED for arg 0x04 -> idx 0x0B =
COUNTRY&WESTERN by two independent clean single-press-from-home tests (SEG01
bit7 opens the RHYTHM / COUNTRY&WESTERN select screen).

NOT yet wired into PORT_NAMEs because a batch sweep of all 16 buttons was
UNRELIABLE: the descriptor "gate" field mode-gates these keys -- from the home
screen some presses act as PERFORMANCE PADS (e.g. arg0F -> "Church Bells", arg07
-> "Cosmic Maj") instead of opening the genre list, and rapid sequential presses
accumulate sub-mode state so later presses don't refresh the displayed genre.
Only isolated single-press-from-a-clean-home-state reliably shows a genre.

NEXT TICK METHOD (clean): for each of the 16 (seg,bit), do a SEPARATE run (or a
long delay + return-to-home between presses) pressing ONE genre button from the
home screen, snapshot the RHYTHM title, and record arg->genre. Confirm the
(arg+7) rule across ≥3 distinct genres, then apply names to SEG01/SEG02 (ports +
.lay text). The arg per (seg,bit): SEG01 b0..b7 = 0F 07 0E 06 0D 05 0C 04;
SEG02 b0..b7 = 0B 03 0A 02 09 01 08 00.

## User-verified button->function calibration (2026-07-06)

The user pressed buttons in the running emulator (which show the OLD folklore
.lay labels) and reported the actual on-screen function. Correlating each press's
SEG.bit to its firmware descriptor event gives GROUND-TRUTH event->function
anchors -- the first real calibration of the CPC/CPR (sound-group) area:

| folklore label | SEG.bit | descriptor event/arg | ACTUAL function |
|---|---|---|---|
| CONTRAST UP   | SEG0C.2 | 0x702040 arg01 | MALLET & ORCH PERC |
| HELP          | SEG0C.1 | 0x702010 arg00 | GUITAR |
| MUTE DOWN 3   | SEG0D.1 | 0x702009 arg00 | ORGAN & ACCORDION |
| MUTE DOWN 7   | SEG0E.1 | 0x702009 arg01 | SYNTH |
| MUTE UP 5     | SEG0D.4 | 0x702004 arg03 | ORGAN TABS |
| BASS          | SEG11.5 | 0x702001 arg11 | BRASS |
| SOUND GROUP 2 | SEG09.6 | 0x702001 arg09 | DEMONSTRATION |

Key lesson: the sound-group / function names are NOT one flat event family --
they are spread across SEVERAL event codes (0x702001, 0x702004, 0x702009,
0x702010, 0x702040), each arg-indexed to a specific target. This matches the
gui-toolkit-event-system.md finding that button function identity is a
widget-level detail, not a single lookup table. So full auto-generalization from
the descriptors alone is not possible; each event family needs its own arg->name
table (in its handler) reversed, OR more user press->screen observations to
anchor them empirically.

These 7 are now correctly labelled in both the driver PORT_NAMEs and the .lay
artwork (commit below). To iteratively unlock more: press a mislabelled button,
note the screen, and add the (SEG.bit -> function) row here; the descriptor event
is then known and its whole arg family can often be inferred.

### Correction: the by-function relabel was reverted (introduced noise)

Relabelling those 7 buttons *by the function they trigger* (commit f75bf78) was
wrong for the LAYOUT: it created duplicate labels (GUITAR/BRASS/SYNTH/MALLET &
ORCH PERC/ORGAN & ACCORDION each appeared twice) and drew sound-group names in
the CPC-board region where they don't physically sit. Reverted (commit a1b5331);
the run-copy no longer has the duplicates.

Two distinct coordinate systems must be kept straight:

1. **Functional input mapping** (which SEG.bit triggers which firmware event).
   This is FIRMWARE-CORRECT in the driver: panel_scan emits each SEGnn's
   reverse-normalized wire address, the firmware normalizes it, and the
   descriptor gives the event. Verified by the buttons working AND by the user's
   7 press->screen observations (the table above). This layer is sound.

2. **Physical panel matrix / .lay artwork** (which button, with which
   silk-screen label, sits at which board + physical SEG column + SW row, and
   where it is drawn). The current .lay is KN5000-derived FOLKLORE -- wrong
   labels and positions throughout the CPC/CPR area -- with bindings
   behaviour-preservingly remapped onto the SEGnn ports. It does NOT match the
   SX-KN7000 service manual and must be REBUILT from it, not patched by function.

The authoritative source for (2) is the service-manual panel schematics
(SCHEMATIC DIAGRAM-15..18: CPL p128, CPC p130, CPR p132/133): each board's switch
matrix (SEG0..9 columns x SW rows, e.g. CPR SW1001,1009,... step 8) with the
silk-screen labels drawn beside the switches in the schematic image. A correct
.lay rebuild needs: physical (board, SEG, SW, label) from those pages, mapped
through physical->wire->normSeg to the SEGnn ports, so drawn position + label +
binding are all consistent. The user's press anchors are ground truth for the
functional side and will validate the rebuild. This is a careful, separate task.
