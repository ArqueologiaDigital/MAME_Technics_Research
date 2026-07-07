# KN7000 panel LEDs — output path (preliminary)

Complements the panel *switch* mapping (notes/service-diagnostic-mode.md,
panel-matrix-service-manual.md). Needed to eventually light the `.lay` LEDs from
firmware state. Found by static RE; the final register/panel-command write still
needs one writer traced end-to-end.

## Two LED categories

**1. Button LEDs** (the small LED next to most panel buttons).
`PanelSwitchClassTable` @ 0x4860C9F4 gives, per switch#, a 2-byte record
`[LED_row_bit, LED_col_reg]` where `LED_col_reg` is one-hot (0x01/02/04/08/10/20 =
LED-matrix column) and `LED_row_bit` = 0..7. Records with high byte 0xFF are class
codes (0xF0–0xF5) for switches with **no** LED (e.g. keyboard keys). Decoded (my
independent dump, scratchpad/my_table_decode.txt): switches 6–40 and 53 carry LED
coords; e.g. sw08–15 = reg 0x02 bits 7..0, sw16–23 = reg 0x04, sw26–36 = reg 0x08,
sw35 = reg 0x10, sw40 = reg 0x20. This is what the service PANEL SW&LED test uses.

**2. Named indicator LEDs** (mode/hold/dial/other-part/…), driven by a small API:
- `SetOtherPartLed` 0x484164F4, `SetHoldLed` 0x48416512, `BlinkHoldLed` 0x48416536,
  `SetDialLed` 0x48416563, `SetModeLed` 0x48416590 (+ CheckHoldLED/CheckDialLED).
- These normalize an on/off arg then call the **LED dispatcher `0x484B1BCB`** with
  an LED index in `d0` (1..0x13 = 1..19; out-of-range → early return).
- Dispatcher: `(idx-1)*4` into **jump table `0x4861518C`** (19 u32 handlers).
- Each handler is `mov 1,d0; call 0x484B0Cxx; ret` — i.e. every one of the 19 LEDs
  has its **own dedicated set-function**:
  | idx | handler | writer |
  |-----|---------|--------|
  | 1 | 0x484B1BE7 | 0x484B0C3F |
  | 2 | 0x484B1BF1 | 0x484B0CA2 |
  | 3 | 0x484B1BFB | 0x484B1099 |
  | 4 | 0x484B1C05 | 0x484B0D05 |
  | 5 (OtherPart) | 0x484B1C0F | … |
  | …19 | 0x484B1C37/…/0x484B1C9B | … |

LED-related state RAM sits around 0x50021FD4–0x50022000 (SetModeLed reads
0x50021FD4; SetDialLed writes 0x50022000).

## TODO (for LED modeling in the driver + .lay)
1. Trace one writer (e.g. 0x484B0C3F) to the actual register or panel-serial
   command byte(s) it emits — determines whether button/indicator LEDs are a
   memory-mapped latch or a panel sub-CPU command (PanelTxKick 0x484AC523).
2. Expose those as MAME `output_finder` LEDs; bind `.lay` LED elements to them so
   they light from firmware state (the "LEDs" half of "buttons and LEDs").
3. Cross-map the 19 named-LED indices + the PanelSwitchClassTable button-LED coords
   to the physical LEDs in the layout.

## UPDATE: LED subsystem now driven (driver plumbing + derived map + first bindings)

### Driver plumbing (works)
`panel_led_frame(addr, data)` (kn7000.cpp) already receives the main CPU's LED
commands off the panel-serial TX (called at the frame decoder). Each command is a
2-byte `[addr][data]`: `addr = panel(bits7:6; 0x00=right/CPR, 0xC0/0xE0=left/CPL) |
reg(bits5:0)`, and each `data` bit is one LED of register `reg`. Fixed this tick to
route by panel into `cpr_led[reg*8+bit]` / `cpl_led[reg*8+bit]` (banks enlarged to
<512>; previously capped at 64 and mis-routed all to CPL).

### Captured boot LED frames (13, ground truth)
`addr/data`: 06/01, 0B/10, 0D/10, 0E/10, 1C/40(x2), C0/08→00, C1/50, E3/10, E6/10,
EA/00, EB/00. These are **status/mode** LEDs (rows 0x06/0B/0D/0E/1C + left-panel
rows) — NOT the sound-group button LEDs (those stay off until a sound is selected).

### Derived button→LED map (from PanelSwitchClassTable, authoritative)
For a bound button: `switch# = normSeg*8+bit` → `PanelSwitchClassTable[switch#] =
(byte0,byte1)`; `HWrow = 0x48615058[byte0]`, `colbit = log2(byte1)`. Right-panel
rows (<0x40) → `cpr_led[HWrow*8+colbit]`; rows ≥0xC0 → `cpl_led[(HWrow&0x3f)*8+colbit]`.
SOUND group (all right/cpr), now BOUND in the layout:
```
PIANO=cpr_led32  GUITAR=cpr_led72  MALLET&ORCH PERC=cpr_led24  WORLD=cpr_led16
STRINGS&VOCAL=cpr_led40  BRASS=cpr_led45  SAX&WOODWIND=cpr_led33  ORGAN&ACCORDION=cpr_led34
SOUND EXPLORER=cpr_led25  DIGITAL DRAWBAR=cpr_led17  ORGAN TABS=cpr_led41
ACCORDION REGISTER=cpr_led46  PAD=cpr_led36  SYNTH=cpr_led35  BASS=cpr_led26  DRUM KITS=cpr_led18
```
Also derivable (not yet bound): ONE TOUCH PLAY=cpr_led96, PROGRAM MENUS=cpr_led6,
DISK MENU=cpr_led14, FADE OUT=cpr_led65, TRANSPOSE+=cpr_led38, OCTAVE±=cpr_led23/31.

### Status / next
- The SOUND LEDs are bound but not yet visually confirmed lit — they only light
  when a sound is selected, and sound-menu navigation is currently blocked by a
  separate emulation issue (rhythm/sound menus). The bindings are derived from the
  firmware's own table so they are correct; visual confirmation awaits the menu fix.
- TODO: derive+bind the CPL (left-panel) LEDs (rhythm genres, arranger) and the
  status LEDs (boot-frame rows), and reconcile the boot-frame rows (0x06/0B/0D/0E/1C)
  to physical indicators.

## VERIFICATION (this tick) + a caveat on the derivation
Ran the driver + read outputs via Lua at idle: the **driver->output pipeline is
confirmed working** — `cpr_led48=1`, `cpl_led3/12/14=1`, `cpr_led92/108/116=1`
(exactly the boot frames), and the bound SOUND LEDs read 0 (correctly off, no sound
active). Pressing a button changes the lit set, so LED state tracks firmware output.

**Caveat on PanelSwitchClassTable-derived cells:** that table is the *panel-test*
switch->LED map. Two findings:
1. Buttons with class byte0>=0xF0 (e.g. BALLAD=SEG00.b4, class 0xF0) are **special
   multi-LED** handlers — my derivation correctly SKIPS them (name=None/decorative).
   Empirically BALLAD's active-genre LED is `cpl3` (a special-handler cell), not a
   simple [row][bit].
2. A single genre probe (press ENTERTAINER=SEG01.b2, derived `cpl_led41`) lit
   `cpl_led9` instead — but that is confounded by the known rhythm-menu emulation
   bug (genre selection is currently unreliable), so it is NOT conclusive evidence
   the derivation is wrong.

**Status:** the ~26 bound direct-LED cells (SOUND cats + genres, byte0<0xF0) are
derived from the firmware's own table and are the best available; they are NOT yet
independently confirmed in normal operation (blocked by the sound/rhythm menu
emulation bugs). The driver plumbing is solid. Next: (a) fix/º understand the menu
emulation bug, then re-probe each LED for clean confirmation; (b) map the special
class-code (0xF0-0xF7) multi-LED handlers for BALLAD-type indicators + status LEDs.

## CORRECTION (this tick): the PanelSwitchClassTable derivation is WRONG for operation LEDs
Probed empirically (single-button, file-redirect capture): pressing **GUITAR**
(SEG0C.b1) moves the sound-group indicator **cpr48 -> cpr49** (baseline cpr48 =
current piano sound), NOT the derived `cpr_led72`. So `PanelSwitchClassTable` is the
**panel-test** switch->LED map and does **not** match the normal-operation LED
behaviour. The 26 derived `.lay` LED bindings from last tick were therefore WRONG
and have been **reverted** (green LEDs are decorative again; the driver plumbing —
which IS verified correct — is unchanged).

### What is actually true (empirical)
- Driver->output pipeline works (verified: outputs match the boot frames).
- The **sound-group indicator is a single moving LED in reg 0x06** (cpr48..cpr55);
  baseline (piano) = cpr48, GUITAR = cpr49. Hypothesis (needs confirming): the 16
  SOUND buttons map consecutively cpr48..cpr63 (reg6 then reg7), but only 1 data
  point is confirmed. A GUITAR press also toggled cpr100 (reg0x0C) + cpl4 — so
  there are secondary indicators too; the delta is not a clean single bit.

### To build the correct map (next focused effort)
Empirical probe = the only reliable source. Probe method that WORKS: **one button
per run**, press at t~17.3, read outputs at t~18.3, `m:exit()`, capture with
`> file 2>&1` (NOT a pipe — pipes lose buffered output on SIGKILL), timeout >=140s
(boot to t=18 takes ~90s real at -nothrottle). io.open is sandboxed; multi-button
savestate flows stalled. Run one per sound-cat / genre / transport button, record
the lit-set delta, then bind those exact outputs. (Blocked-ish: rhythm/sound menu
emulation bug makes some selections unreliable, but SOUND-group selection worked.)

## Empirical operation-LED survey (2026-07-07): method, obstacle, and a corrected assumption
Now that panel buttons deliver to the firmware (held input; see notes + kn7000.cpp panel_scan),
the operation LED map can be probed: press a button and read which `cpl_led`/`cpr_led` output
turns on (Lua `manager.machine.output:get_value("cpr_led23")`, or a change-log `fprintf` in
panel_led_frame). Findings:

- **Single-button probe WORKS reliably.** E.g. pressing a SEG0D sound button changed cpr LEDs;
  the LED outputs (output_finder<512> m_cpl_leds/m_cpr_leds) read fine from Lua. LED indices
  span **0..511** (reg*8+bit), not just 0..150 -- scan the full range.
- **Batch sweep is unreliable (timing obstacle).** `emu.register_frame_done` fires only ~every
  3-4 EMULATED seconds here (regardless of -nothrottle/-window/throttle), so a fast per-button
  sweep (0.6-0.7 s slots) samples the scan window for only ~15-20% of buttons; the rest are
  skipped. A reliable batch would need slots >~4 s (very slow) or a different timing hook; the
  practical route is **one press per short run** (the single-button probe) or the debugger.
- **Operation LED behaviour is messy.** A get_value "currently-on" scan catches BLINKING/shared
  indicators as noise -- `cpr36` recurred for 7 unrelated buttons (a blink/cursor, not a
  per-button LED). Sound buttons behave as radio (previous LED off, new on).
- **CORRECTED ASSUMPTION:** the confirmed clean mappings -- SEG00 INTRO&ENDING2->cpl2,
  SEG01 SOUL&FUNK->cpl9, SEG01 JAZZ COMBO->cpl17, SEG02 ENTERTAINER->cpl26 -- have LED indices
  that MATCH the PanelSwitchClassTable `LEDMAP` (gen_lay.py) for those segments. So that map is
  likely **correct for the CPL (left = rhythm/style/transport) buttons**; the earlier "verified
  wrong" case (GUITAR->cpr49 not cpr72) is on the **CPR (right = sound)** side. The panel-test
  map is PARTIALLY right, not wholesale wrong.

**Recommended path (next):** verify the `LEDMAP` per-button with single-button probes (one press
per short run, read the LED delta over the full 0..511 range), APPLY the confirmed CPL portion to
the layout, and re-derive only the CPR entries. The panel BUTTONS are complete + working
(156 wired, delivery verified); the LED visual binding is this remaining refinement.

## Function-button LED map — empirical sweep (2026-07-07)
scratchpad/ledsweep.lua: for each of the 108 bound buttons, EXIT->home, read the cpl/cpr LED
outputs (via `manager.machine.output:get_value`), press the button, read again, record the
newly-lit output. cpl_led4 = a home/EXIT indicator that any button re-lights -> filtered as noise.
All 16 GENRE LEDs matched the existing GENRE_LED map (method validated). NEW function-button LEDs
(now added to OPLED + wired to their green/red_led in gen_lay.py):
| button | SEG.bit | LED |
|--------|---------|-----|
| APC / CHORD FINDER   | SEG03 0x02 | cpl_led33 |
| DISPLAY HOLD         | SEG08 0x10 | cpl_led5  |
| MUSIC STYLE ARRANGER | SEG09 0x08 | cpl_led13 |
| SOUND DSP            | SEG0F 0x01 | cpr_led18 |
| SOUND DSP VARIATION  | SEG0F 0x02 | cpr_led19 |
| SPLIT POINT          | SEG10 0x02 | cpr_led30 |
| TECHNI-CHORD         | SEG11 0x80 | cpr_led73 |
| START/STOP           | SEG12 0x08 | cpr_led36 (rhythm-running; also lit by DEMO) |
| PROGRAM MENU         | SEG12 0x40 | cpr_led74 |
| DISK                 | SEG12 0x80 | cpr_led75 |
| CHORUS               | SEG13 0x10 | cpr_led100 |
| MULTI EFFECT         | SEG13 0x20 | cpr_led99 |
| MIC REVERB & EFFECT  | SEG13 0x80 | cpr_led91 |
| SYNCHRO & BREAK      | SEG15 0x04 | cpr_led113 |
CORRECTED two mis-wired LEDs: SYNCHRO was cpl10 -> cpr_led113; START/STOP was cpl1 -> cpr_led36.
TODO: REVERB (SEG13 0x40) LED is on-by-default (cpr_led92 at home?) so the press-sweep didn't catch
it -- verify by toggling. ONE TOUCH PLAY (SEG10 0x01 -> cpl_led5?) shares with DISPLAY HOLD -- uncertain.
