# Panel LED mapping — second review (clean F3+F4 LED-test sweep)

Felipe ran the **real** LED test (hold F3+F4 at boot) with `ledtest_sweep.lua`. That screen lights ONLY
the pressed button's own LED (leakage-free), so its button->LED map is authoritative for **press-lit
(switch-class) LEDs**. Raw data: `notes/ledtest-clean-sweep.log`. Normal-op observations:
`notes/led-normalop-observations.log`.

## Result of the diff vs the layout bindings
- **79 press-lit button LEDs CONFIRMED correct**, 0 single-LED mismatches. The first review's index fixes
  all hold. 1 harmless collision (cpl_led29, two ACCOMP/DRUM part-state buttons).
- The buttons that light *nothing* on a press are **mode/state LEDs** (they light when their MODE is
  active, not on a test-press) — the press-based test cannot judge them.

## Fixes applied (this pass)
- **FAVORITES (SEG0E.40) = cpr_led97** — OBSERVED live in normal op (pressing FAVORITES lit cpr_led97).
  PANEL_LED's derived cpr_led2 was dead. Bound directly in gen_lay.py.
- **CONDUCTOR — 3 LEDs = cpr_led63 / cpr_led64 / cpr_led65** (Felipe: each of the 3 buttons has its own
  LED; schematic D1107/D1114/D1120). Group SEG0F/10/11 0x02 maps contiguously (same bit, +1 per SEG col:
  SEG10.02->64, SEG11.02->65 confirmed). CONDUCTOR-1 (SEG0F.02) was dead cpr_led7 -> now **cpr_led63**
  (the free, contiguous slot; it's a mode LED so the press-test doesn't light it). `CONDUCT_LED` in gen_lay.py.

## METHOD FIX — read cpr_led/cpl_led 0-511, not 0-127
panel_led_frame index = reg*8+bit, reg 0-63 -> indices 0-511 (driver has output_finder<512>). Every earlier
sweep/observation read only 0-127. Re-observed at full 0-511 (obs511.lua): **no LED lives above 127** for
the tested buttons, so the CPR/CPL matrix uses reg 0-15 and the 0-127 reads were valid after all. FAVORITES
re-confirmed cpr_led97, DISPLAY HOLD re-confirmed cpl_led5.

## UNRESOLVED — CUSTOMIZE (SEG0C.40): emulation gap, NOT a mapping
Felipe: the CUSTOMIZE LED lights while the CUSTOMIZE MENU screen is active (off on EXIT / 2nd press).
**The button + menu WORK** — pressing SEG0C.40 opens the CUSTOMIZE MENU (screenshot `/tmp/kn_snaps` proved
it). BUT when the menu is active the emulated firmware drives **no persistent panel LED** (0-511 delta with
button released = {}). The only thing that lights is a transient **cpl_led29 WHILE THE BUTTON IS HELD** —
and cpl_led29 is shared by DRUM-1-OFF + ACCOMP-5-ON (the clean-sweep collision), so it's a press-artifact,
NOT the menu LED. => there is no LED signal to bind a layout element to; the "LED-on-while-menu-active"
firmware path isn't reached/driven in the emulator. Same class likely covers CONDUCTOR-1 (SEG0F.02 lights
nothing even at 0-511; cpr_led63 shipped as the contiguous inference below the confirmed 64/65).
NEXT (if pursued): trace the screen-manager's menu-active LED-update path in firmware to find the gate.
Asked Felipe whether to dig in or leave FAVORITES+CONDUCTOR as the deliverable.

## FIRMWARE DIG (Felipe: yes) — empirical + architecture
ARCHITECTURE (notes/panel-leds.md): TWO LED categories. (1) Button LEDs via PanelSwitchClassTable @0x4860C9F4
(press-lit; the LED-test/sweep category). (2) NAMED indicator LEDs (mode/hold/dial) via API SetOtherPartLed
0x484164F4 / SetHoldLed 0x48416512 / SetDialLed 0x48416563 / SetModeLed 0x48416590 -> dispatcher 0x484B1BCB
(idx 1..19 in d0) -> jump table 0x4861518C -> per-LED writers 0x484B0Cxx -> panel frame. The CUSTOMIZE LED
is category 2 (that's why press-based tests never lit it; DISPLAY HOLD = cpl_led5 is also cat-2 and DID light).

EMPIRICAL (clean, press+RELEASE, display free): over the WHOLE CUSTOMIZE menu open->close cycle the firmware
sends only TWO panel frames: open -> **C3=00** (clears cpl reg3 = cpl_led24-31 OFF), close -> **C3=20** (cpl
reg3 bit5 = cpl_led29 ON). So cpl_led29 is a HOME-screen indicator that gets cleared when the menu takes the
display and restored on return — NOT a CUSTOMIZE LED. **Opening the menu drives NO lighting frame.** => the
firmware never issues a "light CUSTOMIZE LED" command in the emulator. Root cause is a gate / uncalled path;
workflow customize-led-trace (wf_0901118c-f2e) is decoding the 19 named-LED writers + the menu LED-call + the gate.
GOTCHA that cost hours: a STALE 9-hour-old emulator (pid, prev session) held the display -> every new run died
on "display conflict / exit 1". Always `ps -eo pid,etimes | grep kn7000` and kill old ones before launching.

## RESOLVED (2026-07-13) — CUSTOMIZE LED = cpr_led0; the bug was DRIVER-side, not firmware
Workflow customize-led-trace (5 agents, adversarially verified) + fixed disassembler proved:
- The firmware DOES drive the CUSTOMIZE LED, UNGATED. CUSTOMIZE screen 0x000E000D -> MainTitleControl
  0x4842B670 -> live call 0x4842B6F5 = SetModeLed(0x0B) [alt entry 0x48416595]. modeLEDtable 0x4859E364[0x0B]
  =0x13 (named-LED idx19) -> jumptbl 0x4861518C[18]=0x484b1c94 -> writer 0x484b111e sets bit0 of LED-shadow
  reg8 (0x50150A44) -> frame builder TXs **[addr=0x00][data]**. SetModeLed auto-clears the previous mode LED
  (state 0x50021FD4), which is why the LED goes off on EXIT / when another mode screen opens.
- **ROOT CAUSE = a DRIVER bug**: kn7000.cpp sio_tx_byte() had `case 0x00: break;` treating addr byte 0x00 as
  idle/padding and DROPPING it before panel_led_frame. But addr 0x00 = CPR reg0 ([0x00][bits]) = the mode
  indicator LEDs cpr_led0 (CUSTOMIZE, idx19), cpr_led1 (idx13), cpr_led2 (idx11). FIX = delete that case ->
  falls through to panel_led_frame. VERIFIED live: cpr_led0 = 0 (home) -> 1 (menu open) -> 0 (menu closed).
- The layout ALREADY binds CUSTOMIZE green_led to cpr_led0 (PANEL_LED[SEG0C 0x40]) -- my ORIGINAL binding
  was right all along; only the driver drop hid it. No layout change needed.
- DECODED 19 named LEDs (idx->led): 1 cpl_led5(HOLD,calib), 2 cpl_led28, 3 cpl_led44, 4 cpr_led97(DIAL),
  5 cpl_led29(OTHERPART), 6 cpr_led25, 7 cpr_led24, 8 cpr_led16, 9 cpl_led36, 10 cpr_led17, 11 cpr_led2,
  12 cpr_led12, 13 cpr_led1, 14 cpr_led9, 15/16/17/18 none, 19 cpr_led0(CUSTOMIZE). (ADDR_TABLE_A@0x48615058,
  Bank A when tg_sound_enabled.) These are candidates for future mode-LED bindings.

## TOOLING BUG FIXED — tools/dis.sh was giving STALE disassembly
dis.sh used `dd bs="$COUNT"` into a SHARED /tmp/w.bin: a hex COUNT made dd fail (stale file) AND concurrent
callers raced -> every address could render the SAME template (this is the origin of the phantom
`movhu (0x98070000)` strap-read that polluted earlier RE). FIXED: arithmetic COUNT + per-invocation mktemp +
bs=1. Re-verify any earlier dis.sh-derived claim that shows a 0x98070000/0x8006 strap read.
