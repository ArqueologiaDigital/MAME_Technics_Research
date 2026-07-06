# KN7000 control-panel completion plan (ALL buttons + ALL LEDs)

Living checklist for the autonomous panel work. Authoritative map = the ROM-extracted
descriptor (`panel-descriptor-map.md`); scripts in scratchpad: `extract_desc.py` (descriptor),
`compare.py` (vs driver), `audit_layout.py` (vs layout). Program flash @0x48400000, table
flash @0x48000000. Regenerate layout: `python3 tools/gen_lay.py`. Always verify: valid XML,
0 duplicate inputtag/inputmask, every binding resolves to a driver PORT_BIT.

## Method
An event family with N bits whose args are 0..N-1 is an N-entry-table selector; find its
name table in the ROM (search strings in table/program flash). Single-bit events are one-off
function buttons — name from context/probe. For a physical button, bind the layout element to
the SEG.bit whose descriptor event matches its function.

## BUTTONS — event families (bind label+position ↔ descriptor bit)
- [x] 0x2005 (16) rhythm genres → RHYTHM GROUP SEG01/02 (RhythmGenreNameTable)
- [x] 0x2004 (18) sound categories → SOUND GROUP (SoundGroupNameTable @0x48131570)
- [x] 0x2000/0x2001 parts 0x10-0x14 → LCD-flanking part on/off (RIGHT1/RIGHT2/LEFT/ACCOMP1/2)
- [x] 0x2000/0x2001 parts 0x00-0x0F → MUTE grid SEG05/08-0B (verify order)
- [x] 0x2020 START/STOP, 0x2022 INTRO&ENDING (2), 0x2023 FILL IN (2), 0x2084 FADE (2)
- [~] 0x2010 (8) CONFIRMED = PART EFFECT + GLOBAL EFFECT buttons (empirical: right-panel LEDs
      cpr49/73/74/75/91/100 + effect-menu screen changes on press). arg→effect order NOT yet
      pinned (6/8 responded on home screen; a3/a4 context-dependent). To bind without mislabelling:
      read the effect-menu title (LCD) per arg, or map the effect-LED positions. Layout has the 8
      decorative buttons (PART EFFECT SUSTAIN/DIGITAL EFFECT/SOUND DSP/VARIATION; GLOBAL CHORUS/
      MULTI EFFECT/REVERB/MIC REVERB & EFFECT). 0x2010 bits a0..a7 = SEG0C.b1,SEG12.b6,SEG11.b6,
      SEG10.b6,SEG0F.b6,SEG11.b7,SEG12.b7,SEG13.b7.
- Found HELP-text function-name pool @0x48394D06 (72 names) = the full label vocabulary; event→name
  lookup is code-based (documented in panel-descriptor-map.md).

- [ ] 0x2040 (11) — "Fn Toggle" — resolve (part-effect toggles? SUSTAIN/DSP/etc.) + bind
- [ ] 0x2030 (12, args 0-5) — FILL/FADE/tempo family? resolve + bind
- [ ] 0x2008 (3), 0x2009 (3) — Balance/Ctrl — resolve + bind
- [ ] 0x2060-0x2069, 0x2081-0x2086, 0x20A0-0x20BD (single/few) — resolve one-offs + bind
      (0x2083 x2 = TRANSPOSE? 0x2085 x4, 0x2081/0x2084 x2, 0x20A1-A9 = APC/variation/etc.)
- [ ] 0x1000 (6, SEG1B), 0x1004/5/9,0x1010/11,0x1020 (SEG16-1A,20) — DIAL/DATA/special
- [ ] 0x20B5-0x20BD (SEG1D-1F, 8) — OTHER PART/HELP/CONTRAST/PAGE/DISPLAY HOLD/EXIT
- [ ] parts 0x15-0x1D (ACCOMP3-5/BASS/DRUM/CHORD) — verify mute coverage
- [ ] Add missing SEG16-0x23 input ports to the driver (44 bits) so their buttons are bindable
- [ ] Sweep gen_lay.py for remaining `tag=None` decorative buttons; bind each per descriptor

## LEDs
- [ ] Extract PanelSwitchClassTable @0x4860C9F4 (2 bytes/switch#=normSeg*8+bit) + LED reg-map
      0x48615058 → per-button cpl_led/cpr_led index. Verify format vs known (SOUL&FUNK=SEG01.b1
      lit cpl9 in an earlier probe).
- [ ] Add a LEDMAP (SEG.bit → cpl_led/cpr_led index) to gen_lay.py; emit an LED element bound to
      that output next to each button (name="cpl_ledN").
- [ ] Named indicator LEDs (SetModeLed/SetHoldLed/SetDialLed dispatcher 0x484B1BCB) — bind.
- [ ] Empirically confirm with the button-test harness (press → mapped LED lights).

## VERIFY (per tick + at milestones)
- Layout: valid XML, 0 conflicts, all bindings resolve.
- Runtime (throttled -video none, frame-counter timing, Write-tool scripts): pressed buttons
  produce screen/LED effects; mapped LEDs light.

## STATUS LOG (newest first)
- soft-keys: LCD-flanking part on/off bound (10); driver SEG00 relabelled; TRANSPOSE unbound.
- SOUND GROUP resolved (0x2004) + rebound. RHYTHM GROUP resolved (0x2005) + rebound.
- INTRO&ENDING/FADE fixes. 83 inputtags bound.


## LED work: operation map is EMPIRICAL (PanelSwitchClassTable is panel-TEST only)
Verified with the reliable frame-counter harness: pressing SEG01 genre buttons lights
cpl8/16/17/18/19/9 — which do NOT match the PanelSwitchClassTable @0x4860C9F4 decode
(cpl1/9/17/25/33/41/49/57). So that table is the panel-self-test map; the OPERATION LED
map (what the .lay must bind) has to be swept empirically.

Full-panel sweep (scratchpad/fullled.lua, throttled -video none, frame-counter, get_value
per button) → only ~16 buttons light a clean single LED from the HOME screen; the rest are
context-dependent (need a part active / a menu open) or have no LED, plus one shared/blinking
indicator cpl5. So the LED map must be built with per-CONTEXT sweeps (rhythm playing, sound
menu open, etc.), same as the button-effect limitation.

### Clean operation LED map so far (SEG.bit → cpl/cpr LED index), home screen:
| SEG | button | LED |
|-----|--------|-----|
| SEG00 | LCD Left 3 | cpl0 |
| SEG00 | INTRO & ENDING 2 | cpl11 |
| SEG00 | SYNCHRO & BREAK | cpl10 |
| SEG00 | LCD Left 5 | cpl3 |
| SEG00 | START/STOP | cpl1 |
| SEG00 | LCD Left 2 | cpl2 |
| SEG01 | BIG BAND & SWING | cpl17 |
| SEG01 | JAZZ COMBO | cpl19 |
| SEG01 | CUSTOM | cpl9 |
| SEG01 | ROCK & POP | cpl18 |
| SEG01 | BALLAD | cpl8 |
| SEG01 | R & B | cpl16 |
| SEG02 | MODERN DANCE | cpl34 |
| SEG02 | GOSPEL & BLUES | cpr31 |
| SEG03 | Fn Key 20A1 | cpl33 |
| SEG03 | FADE IN | cpl32 |

### To finish LEDs (cron ticks):
1. Re-run fullled.lua in more contexts (start rhythm; open sound menu) to capture the
   context-only LEDs; merge into the map.
2. Add a `name="cpl_ledN"/"cpr_ledN"` to each button's LED element in gen_lay.py so MAME
   drives it from the output (the green_led elements are currently decorative).
3. Bind the named indicator LEDs via the dispatcher 0x484B1BCB.

## LED binding — infrastructure live (extend OPLED)
gen_lay.py now has an `OPLED` dict (SEG,mask)->cpl/cpr output name; the green_led elements bind
to it via `name=OPLED.get((tag,mask))` so MAME lights them from firmware state. DONE: 11
rhythm-group genre LEDs (SEG01 SOUL&FUNK=cpl3/CUSTOM=cpl9/BALLAD=cpl8/JAZZ=cpl19/ROCK=cpl18/
BIGBAND=cpl17/R&B=cpl16; SEG02 ENTERTAINER=cpl27/COUNTRY=cpl26/LATIN=cpl25/GOSPEL=cpl24).
TODO genres (empty in the home sweep -- need re-sweep with a primed radio state): SEG01 MEMORY/
LOAD & SEG02 MOVIE SHOW/MARCH/BALLROOM/MODERN DANCE. NEXT LED work: (a) sweep SOUND GROUP LEDs
(0x2004 bits) + add to OPLED + wire the SG loop's green_led like the RG loop; (b) sweep the
effect/mute/transport LEDs in context; (c) apply OPLED to the SG/mute/individual green_leds.
Sweep tool: scratchpad/genreled.lua (frame-counter, captures LED ON+OFF for radio inference).
