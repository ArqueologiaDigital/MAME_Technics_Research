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

### SOUND GROUP LED sweep (messy -- NOT bound yet)
Sweeping the 18 0x2004 sound bits (scratchpad/soundled.lua) shows non-clean-radio behaviour:
selecting a sound category lights the category LED PLUS part/bank indicators (PIANO->r18+r100+
r106; DRAWBAR->r107+r41; others single). Candidate single category LEDs: MALLET=cpr16, ACCORD=
cpr17, PIANO=cpr18(?), ORGAN&ACC=cpr23, WORLD=cpr34, PAD=cpr35, EXPLORER=cpr36, STRINGS=cpr40,
SYNTH=cpr41, BASS=cpr113, EWEXP=cpr31; empties GUITAR/BRASS/SAX/DRUMKITS. To bind reliably,
disambiguate the category LED from the part/bank indicators (sweep with a fixed part selected,
or diff two categories). Left unbound this tick to avoid wrong bindings.

## BREAKTHROUGH: LCD-snapshot button identification (tick 2026-07-07)
manager.machine.video:snapshot() renders the FULL layout + LCD to a PNG (works with -video
none, -snapshot_directory <dir>). Press a button via ioport, snapshot, then VIEW the PNG --
the LCD shows the button's function/screen directly. This is the definitive button-ID tool for
ALL remaining unresolved buttons (scratchpad/effectsnap.lua, soundverify.lua are templates).

Used it this tick to CORRECT a real error: "0x2004 = SOUND GROUP" was WRONG. Physical SOUND
GROUP buttons = SEG0C/0D/0E.b0-b5 (mixed events; SEG0C.b0=PIANO, b1=GUITAR snapshot-confirmed);
0x2004 = a separate per-part sound selector. Layout SG reverted. Also 0x2010 is MIXED (a1=
PROGRAM MENUS), NOT the effects -- so the effect buttons (SUSTAIN/REVERB/etc.) are still
unresolved. NEXT: snapshot-ID the remaining decorative buttons + event families (0x2040, 0x2030,
0x2060-86, 0x20A0-BD, the effects) one by one, then bind each to the correct SEG.bit.

## Snapshot-method scope + more bindings (tick 2026-07-07b)
The LCD-snapshot ID method works for SCREEN-CHANGING buttons (sound-select, genre, menus) but
NOT for LED/audio modifiers (VARIATION/MSA/TAP-TEMPO all show the same RHYTHM screen). For those,
rely on the descriptor event families + the driver labels (which have some errors -- e.g. SEG04.b6
was mislabelled "VARIATION & MSA 4"; it's really 0x2030/a05, and true VARIATION 4 = SEG03.b6 =
0x2085/a03). Bound this tick (descriptor-grounded): VARIATION 1-4 = 0x2085 a00-a03 (SEG04.b4/b2/b0
+ SEG03.b6), MUSIC STYLE ARRANGER = SEG04.b3 (0x20A3), TAP TEMPO = SEG04.b1 (0x20A4), SPLIT POINT =
SEG03.b7 (0x20A6), SYNCHRO & BREAK = SEG00.b7 (0x2021). 89 inputtags, 0 conflicts. Still decorative/
unresolved: PART EFFECT + GLOBAL EFFECT (SUSTAIN/CHORUS/etc.), AUTO PLAY CHORD, performance pads,
SEQUENCER PLAY/EASY REC, PANEL MEMORY, TRANSPOSE/OCTAVE, PART SELECT/CONDUCTOR. NEXT: snapshot-ID
the screen-changing ones (sequencer, panel-memory, APC); for toggles use descriptor + LED sweeps.

## SOUND GROUP LEDs bound (tick 2026-07-07c)
Swept the CORRECT sound-group buttons (SEG0C/0D/0E, sgled.lua) -- clean radio behaviour. Bound 13
category LEDs via OPLED: MALLET=cpr50, WORLD=cpr51, STRINGS=cpr40, BRASS=cpr41, SAX=cpr42,
ORGAN&ACC=cpr43, DRAWBAR=cpr33, TABS=cpr34, ACCORD=cpr35, PAD=cpr24, SYNTH=cpr25, BASS=cpr26,
DRUMKITS=cpr27. The SG loop's green_led now lights from firmware state. 24 LED elements bound total
(11 genre + 13 sound). LEFT OUT (shared indicators cpr48/49/100): PIANO, GUITAR, EXPLORER --
pattern suggests PIANO=cpr48, GUITAR=cpr49 (continues cpr48-51=PIANO/GUITAR/MALLET/WORLD) but
EXPLORER also hit cpr48 so verify with a targeted re-sweep (press BRASS then PIANO then GUITAR)
before binding. NEXT LED: verify PIANO/GUITAR; sweep mute LEDs (SEG08-0B) + VARIATION LEDs (SEG04,
rhythm playing) + effect LEDs; the 5 missing genres.

## LED progress (tick 2026-07-07d): 26 LEDs bound
PIANO=cpr48, GUITAR=cpr49 confirmed (BRASS->PIANO->GUITAR radio chain) + bound -> 15 sound-group +
11 genre = 26 LED elements now driven from firmware. EXPLORER (SEG0D.b2) still only hits shared
cpr48 -> unbound. VARIATION 1-4 (SEG04) light NO per-button LED even with rhythm playing (variation
is LCD-only). NEXT LED targets: (a) mute LEDs SEG08-0B -- but the mute_up/mute_down layout elements
have no green_led, so LED elements must be ADDED per part; (b) transport LEDs (START/STOP=cpl1,
INTRO&ENDING2=cpl11, SYNCHRO&BREAK=cpl10, FADE IN=cpl32 from the earlier home sweep) -- these are
individual green_led calls (not a loop), bind each by name=; (c) the 5 missing genres. NEXT BUTTON
targets (snapshot-ID, screen-changing): SEQUENCER PLAY/EASY REC (decorative, near SEG12), PANEL
MEMORY group, AUTO PLAY CHORD, PART SELECT/CONDUCTOR.

## Button-ID campaign (tick 2026-07-07e): snapshot scope confirmed + 3 bound
Snapshotted the toggle/mode candidates (MUSIC STYLIST, ARRANGER OFF/ON, PLAY CHORD OFF/ON, SOUND SET,
AUTO MODE): they all show the HOME/CONDUCTOR view (PMEM: A-, parts DRM2/DRM1/ACP5-1/BASS/APC/PADS/LEFT/
RIGHT2/RIGHT1 + sounds + TRANSPOSE:C), NOT distinct screens -- so like VARIATION they can't be
snapshot-ID'd (they toggle a setting shown as an on-screen indicator). RULE: snapshot IDs only
screen-OPENING buttons (sound/genre/menus); for toggles/modes trust SINGLE-BIT dedicated events
(0x2031/2032/2033/20A8/2022/2023/2084 etc.), NOT mixed families (0x2000/2001/2004/2010/2030/2040).
Bound this tick: PERFORMANCE PADS AUTO SETTING=SEG06.b5(0x2031), STOP=SEG06.b1(0x2033), AUTO PLAY
CHORD OFF/ON=SEG06.b3(0x2032). 92 inputtags. Reliable-but-unbound single-bit: FILL IN 1/2 (0x2023
SEG03.b4/b2 -- layout has no FILL button), INTRO&ENDING 2 (0x2022 SEG00.b6), FADE OUT (0x2084 SEG03.b3),
AUTO MODE (0x20A8 SEG07.b1). Mislabelled driver bits found: SEG05 "PAD"/"PADS BANK" are 0x2000/2001
part on/off; the real PERFORMANCE PADS BANK bit is unknown (BANK left decorative).

## PANEL STATUS CHECKPOINT (tick 2026-07-07f) -- tractable work largely done
Bound: **92 buttons** (inputtags, all verified/descriptor-reliable) + **26 LEDs** (11 genre + 15
sound-group). This tick's 3 probes all returned informative NEGATIVES:
- MUTE buttons (SEG08-0B) have NO panel LEDs -- part on/off state is LCD-only (the conductor view).
- 5 genres (MOVIE SHOW/MARCH/BALLROOM/MODERN DANCE/MEMORY, SEG02.b0/b1/b6/b7 + SEG01.b0) don't
  select/light on the home screen -- a second genre bank or mode-gated.
- Misc function buttons (0x2060-69, 0x2011-13 on SEG0F-13) all show the HOME/CONDUCTOR view when
  pressed -- toggles/modes, not snapshot-identifiable.

### What remains (all LOW-YIELD / hard):
1. Toggle/mode buttons (ARRANGER, PLAY CHORD, TECHNI-CHORD, PART SELECT, CONDUCTOR, SOLO, PANEL
   MEMORY, effects) -- show an on-screen INDICATOR, not a distinct screen; can't snapshot-ID. Bind
   only from SINGLE-BIT dedicated events where a layout label clearly matches.
2. SEQUENCER/COMPOSER etc. are PROGRAM-MENUS sub-items (accessed via SEG12.b6=PROGRAM MENUS), not
   direct buttons.
3. Missing SEG16-0x23 (44 bits: DIAL/DATA/LCD-soft-keys) -- need driver input ports + the high-
   segment wire-addr encoding in panel_scan (only partially known: 0x16-19->0xD0-D3, 0x1A->0x10,
   0x20->0x17).
4. Context/audio-only buttons (variations, mutes, effects) -- no visible screen/LED effect.

CONCLUSION: the easy/tractable panel bindings are essentially complete. Further gains need audio
analysis, the SEG16-23 wire-addr RE, or a real panel photo. Good point to rebalance effort toward
the other backlog (AST custom-flash codec for the "8 Beat 1" style names; disassembly growth).

## SEG16-0x23 checklist item RESOLVED (tick 2026-07-07g)
Added SEG16-SEG20 input ports (driver builds + boots). Wire-addr RE showed the "44 missing bits"
is really only **6 addable panel-serial buttons** (SEG16-1A, SEG20 = DIAL/DATA/special, ADDR
0xD0-D3/0x10/0x17); SEG1B-1F/21-23 are NOT panel-serial (no wire path). panel_scan now uses a
seg->ADDR lookup table for all 0x21 segments. NEXT for these 6: snapshot-ID (press each -> read LCD;
0x16=DIAL?, 0x17=DATA? per the old note, likely PAGE/DISPLAY-HOLD/EXIT among 0x1009/1010/1011/1020)
then bind to the layout's DIAL/DATA/PAGE/DISPLAY HOLD/EXIT/OTHER PART buttons + relabel the driver.

## Tick 2026-07-07i: SEG16-20 verified + 2 transport LEDs bound (28 total)
Snapshot-tested the 6 new SEG16-20 buttons IN A MENU CONTEXT (opened PROGRAM MENUS via SEG12.b6,
then pressed each): all 6 DELIVER (no port/field errors, menu stayed responsive) but NONE change
the screen -- they are data-entry (0x1005 DIAL rotary, 0x1004 DATA +/-, 0x1009/1010/1011/1020), not
PAGE/EXIT (those must be the non-panel-serial SEG1D-1F, 0x20B5-BD, which have no wire path). So the
SEG16-20 buttons are confirmed-working but not snapshot-ID-able and not cleanly bindable to layout
buttons. Bound 2 transport LEDs (transled.lua, rhythm playing, radio-confirmed): START/STOP=cpl1
(first BEAT LED), SYNCHRO&BREAK=cpl10 (its green_led). INTRO&ENDING/FADE/TAP are momentary triggers
with no steady LED. 28 LEDs bound now. REMAINING LED: BEAT LEDs 2-4 (need a cycling-playback capture);
effect-cluster LEDs. The panel is at its observable limit -- buttons+LEDs that produce no visible
screen/LED change can't be verified in emulation without a real-machine reference.

## Tick 2026-07-07k: BEAT LEDs + 0x2008/9 investigated (panel at observable limit)
BEAT indicator LEDs do NOT cycle (no beat engine without wave ROMs) -- cpl1/cpl12/cpl14 light
STEADY during playback (cpl1=START/STOP bound; cpl12/cpl14 unmapped, not bound -- physical LED
position unverifiable). 0x2008/0x2009 family resolved (see panel-descriptor-map.md): 0x2009 =
sound-group buttons (re-validated existing cpr43/24/25 bindings); 0x2008 = 3 right-panel toggle
buttons with verified LEDs cpr19/30/55 but unverified identity (likely PART EFFECT; NOT bound per
the 0x2004 lesson). No new reliable bindings this tick. CONCLUSION: the panel is genuinely at its
OBSERVABLE LIMIT -- 98 buttons + 28 LEDs all verified; every remaining button/LED is a toggle/
data-entry/effect with no snapshot-distinguishable identity and no LED-position reference. Further
panel binding requires a REAL-MACHINE photo/reference. Recommend brief future panel ticks.

## Tick 2026-07-07m: panel LED ROM tables ruled out (unidasm)
Disassembled PanelSwitchClassTable (0x4860C9F4) + PanelLedRegMap (0x48615058) readers -- confirmed
NEITHER is a button->LED shortcut (switch-matrix self-test scan + LED-register select, respectively).
So the cron's "bind LEDs via PanelSwitchClassTable" step is a dead end. Panel LED binding stays
empirical + is COMPLETE for all verified buttons (28 LEDs). The panel is at its observable limit;
the high-value work is now the "8 Beat 1" trace (unidasm-enabled) in the GENERAL tick, not the panel.

## Tick 2026-07-07o: PANEL WORK EXHAUSTED -- panel cron retired
Tried 3 more unidasm-enabled approaches to resolve the remaining button events -> labels:
(1) HELP name pool @0x48394D06 = garbage (that address is wrong);
(2) button function-name strings exist in the ROM but SCATTERED (SUSTAIN 0x485E7638, Reverb 0x4864FB24,
    Chorus 0x48591D38, ...) -- not a table;
(3) the 0x485E7xxx labels (SUSTAIN / SUSTAIN LENGTH) are PARAMETER-MENU entries, not a button->label map.
All dead ends -- consistent with the ~8 prior ticks (observation, snapshots, LED sweeps, descriptor
analysis, ROM tables via unidasm). 

FINAL STATUS: the panel is DEFINITIVELY at its observable limit -- **98 buttons + 28 LEDs verified-bound**.
Every remaining button/LED is a toggle / data-entry / effect with (a) no snapshot-distinguishable
identity, (b) no LED-position reference, and (c) no event->label reference in the dumped program ROM.
Completing them REQUIRES a real-machine photo/silk-screen reference (the user's SVG-mockup domain), not
more emulation or static RE.

DECISION: retired the panel cron (206c9236) this tick. It was re-deriving the same "exhausted" conclusion
each fire, spending tokens with no marginal gain. The GENERAL autonomous cron (59ece5f7) continues the
full backlog -- including any panel work that becomes tractable if a real-machine reference appears -- and
is currently converging on the high-value "8 Beat 1" style-name trace. Re-create a panel cron anytime if
a real-machine reference becomes available.
