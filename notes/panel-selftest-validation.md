# Panel button/LED self-test: validation + mapping the decorative buttons (2026-07-10)

Task: use the firmware's Panel SW & LED self-test to validate every button + LED and map the
still-decorative buttons (Panel Memory etc.).

## Button-set VALIDATION (static, authoritative)
The service Panel SW & LED test uses `PanelSwitchClassTable @ 0x4860C9F4`. The panel-test handler
(0x484A0CB0) computes **switch# = normSeg*8 + bit#**, then reads the 2-byte record
`PanelSwitchClassTable[switch#] = [LED row / class, LED col reg]`:
- `----` (0xFFFF) = no button at that normSeg.bit.
- class 0xF0..0xF7 = special switch (part on/off, SD switches, sensors -- no normal indicator LED).
- otherwise = a normal button whose indicator LED is at (row, col-reg one-hot).

Cross-checked against the driver's bank-A INPUT_PORTS: **the real-button set matches** --
SEG16-1B/20 are all `----` (correct: they're the CPC value-encoder column, no LED), SEG1D b0-b5 =
class F7 (the SD front switches), and every UNUSED bit in the ports lines up with a `----` entry.
Only anomaly: SEG14 b7 = class F3 (a special switch with no descriptor event -- a sensor/reserved,
left unbound). So the button map is validated as complete + phantom-free.

## Decorative buttons MAPPED (empirical app/screen sweep)
Driving each candidate normSeg.bit in the emulator and reading the screen it opens resolved the
buttons that were merely decorative in the layout. Confirmed:

| Button                | normSeg.bit | event / how confirmed                          |
|-----------------------|-------------|------------------------------------------------|
| MUSIC STYLIST         | SEG07 0x01  | ev2040 app-open -> MUSIC STYLIST screen        |
| SEQUENCER EASY RECORD | SEG0C 0x08  | ev2040 -> EASY RECORD screen                   |
| CUSTOMIZE             | SEG0C 0x40  | ev2040 -> CUSTOMIZE MENU                        |
| SEQUENCER PLAY        | SEG0D 0x08  | ev2040 -> SEQUENCER PLAY                        |
| SD MENU (LOAD pill)   | SEG0D 0x80  | ev2040 -> SD MENU                              |
| PANEL MEMORY 1..8     | see below   | ev2010 arg-mid 0..7 -> "PMEM x-N" recall       |
| PANEL MEMORY BANK SEL / BANK VIEW | SEG10 0x80 | ev2013 -> PANEL MEMORY BANK SELECT screen |
| NEXT BANK             | SEG0F 0x80  | ev2012 -> advances to the next PM bank         |
| FAVORITES             | SEG0E 0x40  | ev20AE -> FAVORITES screen                     |

PANEL MEMORY 1..8 (ev2010, arg-mid = PM# - 1; cross-checked vs the descriptor dump):
PM1 SEG0C 0x02, PM2 SEG12 0x40, PM3 SEG11 0x40, PM4 SEG10 0x40, PM5 SEG0F 0x40, PM6 SEG11 0x80,
PM7 SEG12 0x80, PM8 SEG13 0x80. The physical dial is an 8-way pie-slice ring + central SET; the
layout now draws a clickable round button per slice (verified: clicking PM1 recalls "PMEM A-1").

All the above are now bound in the layout (tools/gen_lay.py) + named in INPUT_PORTS.

## Still open
- CUSTOM PANEL and PANEL MEMORY SET: no distinct descriptor event found by the app/screen sweep
  (SET is likely a context action inside the PM store screen; CUSTOM PANEL bit unresolved). Left unbound.
- PAGE / CONTRAST: the CPC value-encoder column (SEG16-20, ev1004-1020) -- value controls, not LED
  buttons; a driver value-input model, not a simple bind. Left unbound.
- LED bindings: PanelSwitchClassTable gives every button's LED (row, col); the driver's
  panel_led_frame maps a serial LED write (addr,data) -> cpl/cpr_led[reg*8+bit]. The exact
  (row,col)->(addr,data) firmware conversion (0x484a0b3e -> 0x484b1780 -> serial) still needs
  pinning, OR an empirical panel-test sweep (boot combo C#3+D#3+C#4 entry being cracked). Until
  then the layout keeps the state-identity genre/sound-group LEDs + dark elsewhere (honest).
