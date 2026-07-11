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
layout draws a clickable round button per slice + its LED. **Slice order corrected per Felipe
(PM_ORDER=[2,1,8,7,6,5,4,3] round the ring -- my first angular order was scrambled).** Each PM
LED is from PANEL_LED (PM1 -> cpr_led72, verified live: recalling PM1 lights it -- which also
confirms the rows-14-19 LED formula). Verified: recalling PM1 (SEG0C 0x02) opens "PMEM A-1".

All the above are now bound in the layout (tools/gen_lay.py) + named in INPUT_PORTS.

## Felipe punch-list 2026-07-11 (progress)
DONE (commit 78b4bbd): TRANSPOSE +/- and R1/R2 OCTAVE +/- were swapped -> corrected (TRANSPOSE - =
SEG10 0x01 / + = SEG0F 0x01; OCT - = SEG13 0x02 / + = SEG12 0x02). The 6 SD CARD buttons were drawn
but unbound -> wired to the SDSW port (VOL -/+ 0x10/0x20, SKIP <</>> 0x01/0x02, STOP 0x04, PLAY/PAUSE 0x08).
RHYTHM GROUP LEDs: RE-VERIFIED all 16 genre LEDs light EXACTLY their PANEL_LED output on selection
(empirical, normal operation) and the genre button/LED order matches the mockup -- so the genres are
correct; could not reproduce a wrong genre LED. (If Felipe still sees a wrong one, need the specific label.)
STILL UNRESOLVED (investigated, NOT guessing):
- PANEL MEMORY SET: ev2011 (SEG13 0x40) DISPROVEN by a functional store test (SET+PM5 did NOT overwrite
  PM5). SET has no confirmed descriptor event -- likely a CPC-board / context action.
- CUSTOM PANEL: ev20B4 (SEG06 0x80) only sets a generic status latch 0x5006bfc8 bit0x10 (handler
  0x484B1B48) -> NOT confirmed CUSTOM PANEL. Its LED-bearing switch isn't obviously adjacent to
  CUSTOMIZE(SEG0C 0x40)/FAVORITES(SEG0E 0x40) in the LED matrix.
- PAGE UP/DOWN, CONTRAST UP/DOWN: the CPC value-encoder column (SEG16-20). Empirically SEG20 (ev1020)
  = TEMPO up (120->123); SEG16-1A showed no visible PAGE/contrast change on the tested screens. These
  are context-dependent value controls, so a fixed PAGE/CONTRAST bit isn't cleanly determinable.
All four need the CPC-board switch matrix (service manual DIAGRAM-16, not transcribed) or the sub-CPU
physical->normSeg map, OR more targeted functional RE. Left unbound rather than mis-bound.

## Still open
- CUSTOM PANEL and PANEL MEMORY SET: no distinct descriptor event found by the app/screen sweep
  (SET is likely a context action inside the PM store screen; CUSTOM PANEL bit unresolved). Left unbound.
- PAGE / CONTRAST: the CPC value-encoder column (SEG16-20, ev1004-1020) -- value controls, not LED
  buttons; a driver value-input model, not a simple bind. Left unbound.
## LED map SOLVED + APPLIED (authoritative, firmware-derived)
The (row,col)->output conversion was pinned: the LED shadow write (0x484a0b3e -> 0x484b1780 ->
0x484b170c) indexes a **row-remap table @0x48615058** whose value IS the panel_led_frame ADDR:
rows 0-7 -> 0xC0..C7 (CPL reg 0-7), rows 8-13 -> 0x00..05 (CPR reg 0-5), rows 14-19 -> 0x08..0D
(CPR reg 8-13). So:

    led index = (remap[row] & 0x3f) * 8 + col_index      (col_index = log2(col-reg one-hot))
    board     = cpl if (remap[row] & 0xc0) else cpr

VALIDATED LIVE against normal operation (not just the panel-test): genre0 (8&16 BEAT) -> cpl_led2;
selecting ROCK & POP -> cpl_led2 goes OFF, cpl_led18 comes ON (exactly as predicted); PIANO
(RIGHT1) -> cpr_led44. This DISPROVES the old panel-leds.md claim that the switch-class map "does
not match normal operation" -- that was a bank-B measurement.

APPLIED: tools/gen_lay.py now computes `PANEL_LED[(SEG,mask)]` for all 91 button LEDs from this
formula (replacing the old bank-B `LEDMAP`, the re-keyed `OPLED`/`GENRE_LED`, and the hardcoded
state-identity names). Every bound button's green_led lights from the correct firmware output.
(Special-class buttons F0-F7 -- part on/off, START/STOP, SD switches -- have no standard indicator
LED, so they stay dark, which is correct.) Rows 0-13 are live-validated; rows 14-19 (SEG12-15
upper bits) are derived from the same clean remap but not yet individually spot-checked.

Full empirical confirmation via the real Panel SW & LED test still wants the boot-combo entry
(C#3+D#3+C#4) -- being cracked -- but the formula is already firmware-authoritative + validated.

## USING the self-test mode (2026-07-10) -- flag 0x5006BFB2, + validation via it
Felipe: "use the LED & Button self-test mode." The service Panel SW & LED test (manual 8.5) is
gated by RAM flag 0x5006BFB2 -- when the panel dispatcher (0x484ADB59 @0x484ADB72) reads it as 1,
a button press routes to the InOut test handler 0x484A0CB0, which lights that switch's LED from
PanelSwitchClassTable. Behaviour (observed): the LED lights ~1 s after the press and ACCUMULATES
(matches the manual's "press all buttons -> ALL DEVICE OK"). Enabler: tools/panel_selftest.lua
(holds the flag = 1 every frame).

RAN IT and it CONFIRMED the PANEL_LED map: pressing each button lights exactly its formula LED.
- delta sweep (13 buttons across all row ranges): 10/13 lit exactly the formula LED; the 3 "misses"
  were LEDs already lit (home state / prior accumulation), not errors.
- membership sweep (27 buttons): 24/27 have their formula LED lit after pressing (incl. rows 14-19:
  BRASS cpr81, SAX cpr80, PM1 cpr72, PM8 cpr15 -- the rows I was unsure of, now confirmed). The 3
  misses were leakage on that long automated run.

WHY THE HYBRID/LEAKAGE (confirmed by disassembly, not just inferred): PanelButtonDispatch 0x484ADB59
reads the flag at 0x484ADB72; if ==1 it calls the InOut test handler 0x484A11E1 (which lights the
switch's LED) at 0x484ADB7C -- then UNCONDITIONALLY falls through to 0x484ADB85 and runs the normal
dispatch (0x484ABAFD -> post the button event). So with the flag forced ON, a press does BOTH the
LED test AND its normal function; the event is still posted and consumed by whatever screen is
focused. In the real test APP the focused test window treats the event as a no-op (clean isolation);
on the HOME screen the home window runs the real function (the "leakage"). This is INHERENT -- it
cannot be cleaned by forcing the flag harder (the firmware also clears the flag block via the panel
init routine 0x484ADB14, but that's a boot/reset block-clear, not a per-press race). The only clean
path is being IN the test screen. The LED validation is unaffected: 0x484A11E1 lights the correct
switch-class LED regardless (that is what the sweep measured).

LIMITATION (honest): we cannot enter the test SCREEN (no "ALL DEVICE OK" text, no clean isolation).
The boot key-combo is read by the panel/key SUB-CPU, which the emulator does not model at power-on
(subagent-verified: injecting the keys into the note FIFO does nothing). And forcing the flag on the
HOME screen is a HYBRID -- the test handler lights the LED but the home screen ALSO processes the
button (e.g. a genre press changes the displayed rhythm), so LEDs leak/drift over long sweeps. This
does NOT weaken the LED validation: the switch-class (test) LED EQUALS the normal-operation LED
(separately proven: genre0->cpl2, ROCK&POP->cpl18 in normal mode), so the map is right either way.
tools/panel_selftest.lua works best one-button-at-a-time (a quick "does button X light LED Y?" check).
To get the full interactive test screen would need modeling the sub-CPU power-on key report OR forcing
the MILK test-window object create (StestWindowProc 0x484A4A2B / 0x50009) -- both larger efforts.
