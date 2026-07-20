# KN6000 / KN6500 control-panel matrix

How the KN6000/KN6500 panel map was derived, what it is, and what is still open.
Implementation: `src/mame/matsushita/kn6000_cpanel.cpp` (matrix + LEDs) on top of
`src/mame/matsushita/kn_cpanel.cpp` (the shared CP protocol).

## Why a new panel device at all

The KN6000/KN6500 drivers reused the KN7000 machine config wholesale, panel included.
That *worked* at the transport level -- the firmware accepted button traffic and the
TEMPO/PROGRAM wheel behaved perfectly -- because the **CP wire protocol is genuinely
shared** across the MN10300 models. What is NOT shared is the matrix contents:

> Comparing the two firmwares' button descriptors cell by cell over normSeg 0x00-0x13:
> **19 cells carry the same event, 123 carry a DIFFERENT one, 8 exist only on the KN6000
> and 9 only on the KN7000 — 88% of populated cells differ.**

So virtually every KN6000 button was doing some other button's job. That is exactly the
"presses are accepted but the mapping is all wrong" symptom.

## KN6000 vs KN6500: ONE device serves both

Their descriptor tables are **byte-identical**: 30 segments, 164 button-bits,
**zero differing entries** (same events, masks, bits, group and flag bytes; the pointer
tables differ only by base address, KN6000 `0x4C19BCAC` vs KN6500 `0x4C19BDB0`, and the
inter-array spacing matches exactly). There is therefore no reason to split them, and
`kn6000_cpanel_device` is used by both drivers.

## Source 1 — the firmware (authoritative for GEOMETRY)

`PanelButtonDispatch` descriptor arrays, reached via the pointer table above and consumed
by the dispatcher at `0x4844D376`, which indexes it directly with the segment byte
(`mov 0x4c19bcac,a1; movbu (a0),d0; asl2 d0; mov (d0,a1),a2`). 12-byte entries:

| off | field |
|---|---|
| +0 | `u16` event code |
| +2 | `u16` class (always `0x0070`) |
| +4 | `u8` bit mask |
| +5 | `u8` bit number |
| +6 | `u8` group |
| +7 | `u8` flag |
| +8 | `u32` handler pointer (library address) |

Terminated by `FFFFFFFF`. Note the KN6000 differs from the KN7000 structurally: the
KN7000 packs a per-button **arg** at +7 that identifies which member of a group was
pressed, whereas the KN6000 puts a **handler pointer** at +8 and dispatches group members
**positionally** (all 16 RHYTHM GROUP buttons share one handler and are told apart by
their seg/bit). The one exception is event `0x2040` (the menu keys), where +7 is a
distinct single bit per button.

53 distinct events, 50 of them shared with the KN7000 — which is what makes the KN7000's
event vocabulary usable as a Rosetta stone. The three KN6000-only events are `0x1012`,
`0x20AC` and `0x20AD`.

## Source 2 — the service manual (authoritative for NAMES)

SX-KN6000 service manual, pp.45-49. Two Mitsubishi **M37471M2196S** sub-CPUs scan
everything; CPC/LCDL/LCDC/LCDR/ROT have no CPU and are matrix extensions:

| sub-CPU | SEG columns | covers | normSeg |
|---|---|---|---|
| IC1 on **CPL** | SEG0..SEG9 (10) | CPL + LCDL + LCDC | 0x00-0x09 |
| IC10 on **CPR** | SEG0..SEG15 (10 wired) | CPR + CPC + LCDR + ROT | 0x0A-0x13 |

A button is (SEG column x SW0..SW7 return); an LED is (PNP anode group x SEG column).
CPR SEG8/13/14/15 are unwired — and consistently, normSeg 0x12 is CPR **SEG9**, not SEG8:
the firmware's normalized numbering skips the dead column.

## The two sources agree — which is the real result

The manual's switch inventory and the firmware's descriptor geometry were derived
completely independently, and they match cell for cell:

- 16 RHYTHM GROUP buttons in **6/6/4** columns → descriptors put exactly 6/6/4 `0x2005`
  bits at normSeg 0x00/0x01/0x02 bits 2-7, 2-7, 2-5.
- 16 SOUND GROUP buttons in **6/6/4** → exactly 6/6/4 `0x2004` bits at 0x0A/0x0B/0x0C.
- 32 MUTE UP/DOWN in four 8-tall columns, alternating UP/DOWN → four segments 0x04-0x07
  of alternating `0x2001`/`0x2000`.
- 6 PERFORMANCE PADS sharing three columns as **1/4, 2/5, 3/6** → `0x2030` at bits 0 and 1
  of 0x00/0x01/0x02. (This one corrected a wrong guess: naive positional ordering would
  have given 1/2, 3/4, 5/6.)
- CONDUCTOR and PART SELECT quads at CPR SEG5/SEG4 SW4-SW7 → `0x2008`/`0x2009` triples
  plus TECHNI-CHORD / SOLO at normSeg 0x0F/0x0E bits 4-7.
- LCDC's SW64..SW69 = PAGE UP, PAGE DOWN, TR, HELP, HOLD, EXIT → normSeg 0x08 bits 0-5,
  whose events (`2001`,`2000`,`2000`,`2040`,`20A0`,`2001`) match those meanings exactly.

**All 150 populated button-bits in normSeg 0x00-0x13 are named, with no leftovers on
either side.** That mutual confirmation is why this map is trusted without an exhaustive
live sweep.

## Independent wire-trace confirmation of the whole CPR half

A second, separate pass over the schematics traced the CPR sub-CPU's columns wire by wire
(switch terminal -> diode -> 68 ohm resistor -> LS07 buffer -> SEG pin) and recovered the
board's switch-numbering rule:

> Switches are numbered sequentially, grouped by column in ascending SEG order, and within
> a column in return order SW0->SW7, **skipping unfitted positions**.

Every CPR column that produces lands exactly on the normSeg this device declares:

| CPR SEG | switches | normSeg | contents |
|---|---|---|---|
| SEG0 | S201-206 | 0x0A | PIANO … WORLD (6) |
| SEG1 | S207-212 | 0x0B | ORGAN & ACCORDION … DRUM KITS (6) |
| SEG2 | S213-218 | 0x0C | DIGITAL DRAWBAR … DIGITAL EFFECT (6) |
| SEG3 | S219-225 | 0x0D | SOUND DSP, VARIATION, LCDR 1-5 (7) |
| SEG4 | S226-233 | 0x0E | ONE TOUCH PLAY … SOLO (8) |
| SEG5 | S234-241 | 0x0F | FADE IN … TECHNI-CHORD (8) |
| SEG6 | S242-249 | 0x10 | INTRO & ENDING 1 … DISK (8) |
| SEG7 | S250-257 | 0x11 | TRANSPOSE - … GLOBAL EFFECT MIC (8) |
| SEG9 | S258-264 | 0x12 | MUSIC STYLIST, FAVORITES, SYNCHRO & BREAK, **(gap)**, SET, NEXT BANK, BANK VIEW, CUSTOM PANEL |
| SEG10 | S265-272 | 0x13 | PANEL MEMORY 1-8 |

**The standout confirmation is the gap.** The trace finds exactly ONE unfitted switch
position on the whole CPR board -- column I (SEG9), return SW3 -- and the firmware's
descriptor table has exactly one hole in this range, at normSeg 0x12 bit 3. Two entirely
independent sources, a schematic trace and a ROM table, agreeing on a single missing
switch is about as strong as this kind of evidence gets. It also confirms the SEG8 skip:
SEG9 maps to normSeg 0x12, not 0x13.

## CPR LED matrix (traced, not yet bound in code)

The same pass recovered the CPR-side LED coordinates. Note the row decode: the 74LS138's
`Y0` is unconnected, so **`CM[2:0] = row + 1`** (CM=0 and CM=7 are blanking codes).

| IC11 out | driver | LED row |
|---|---|---|
| Y6 | Q20 | row 0 |
| Y5 | Q21 | row 1 |
| Y4 | Q22 | row 2 |
| Y3 | Q23 | row 3 |
| Y2 | Q24 | row 4 |
| Y1 | Q25 | row 5 |

Critically, the 12 buffered column nets carry **both** the LED cathode drive and the switch
scan -- one net, verified continuously from S272's terminal through D375's cathode to R109.
Pulling a column low simultaneously lights that column's LEDs and strobes its switches,
which is how 12 drivers serve 72 switches plus 70 LEDs.

CPR board: D351-D356 = PANEL MEMORY 1-6 on Q25 x SEG0-5; D357/D358 = PM7/PM8 on Q25 x
SEG6,7; D359 TECHNI-CHORD on Q25 x SEG9. Then rows Q20-Q25 x columns J/K/L (SEG10/12/11):

| row | J | K | L |
|---|---|---|---|
| Q20 | D360 CONDUCTOR LEFT | D362 CONDUCTOR RIGHT1 | D361 CONDUCTOR RIGHT2 |
| Q21 | D363 PART SELECT LEFT | D365 PART SELECT RIGHT1 | D364 PART SELECT RIGHT2 |
| Q22 | D366 SOLO | D368 CHORUS | D367 MULTI |
| Q23 | D369 BANK VIEW | D371 REVERB | D370 MIC |
| Q24 | D372 CUSTOM PANEL | D374 EASY REC | D373 PLAY |
| Q25 | D375 PROGRAM MENUS | D377 DISK IN USE | D376 DISK |

LCDR (D301-D320): rows Q20-Q24 x SEG0-3 in reading order -- Q20 = PIANO / GUITAR /
STRINGS & VOCAL / BRASS, Q21 = MALLET / WORLD / ORGAN / SAX, Q22 = PAD / SYNTH / BASS /
DRUM KITS, Q23 = DIGITAL DRAWBAR / ACCORDION REGISTER / SOUND EXPLORER / MEMORY,
Q24 = SUSTAIN / DIGITAL EFFECT / SOUND DSP / VARIATION.

CPC (D323-D345): rows Q20-Q24 x SEG4,5,6,7,9; Q20 holds only the last three (FADE IN /
FADE OUT / SYNCHRO & BREAK). D336-D339 have diode symbols but **no printed legend** --
position suggests beat 1-4 indicators, which is inference, not documented.

**Why this is not wired up yet:** what is traced is the *hardware* coordinate
(anode row x SEG column). What `panel_led_frame()` receives is the *protocol* coordinate
(`[register][bit]`). The mapping between them is plausibly `register = row`, `bit = column`,
but that has not been confirmed against the firmware's LED frame builder, and with no
KN6000 layout to display the result there is nothing to verify it against. The decode
therefore stays generic; this table is what to bind when artwork exists, cross-checked
against the built-in "Panel SW & LED test" (service manual p.22 section 7.5).

## Segments 0x14-0x1D are not buttons

They exist in the descriptor table but carry `0x1xxx` events and reach the firmware
through the TYPE 2 latched-control path, not the switch-frame path: the four pots
(0x16-0x19), the DATA dial (0x1A) and pedal/rear switches. They are deliberately not
declared as ioports.

## Wire mapping

normSeg 0x00-0x09 → CP wire ADDR 0xC0-0xC9 (CPL sub-CPU);
normSeg 0x0A-0x13 → wire ADDR 0x00-0x09 (CPR sub-CPU).

Same two-bank allocation as the KN7000, with 10+10 columns instead of its 12+10. This is
the piece that was *inferred* rather than read out of a table (the KN6000's wire→segment
normalization is done inside its CP receive path rather than by a KN7000-style 256-byte
LUT, which was not located). It is confirmed empirically instead — see below.

## Live verification (2026-07-20)

Buttons driven via Lua on the new tags, from the booted play screen, snapshot-checked:

| model | button pressed (silk name) | result |
|---|---|---|
| KN6000 | POP (normSeg 0x00 b3) | RHYTHM screen, genre header **POP** |
| KN6000 | PIANO (normSeg 0x0A b0) | SOUND - RIGHT 1, category **PIANO**, real piano voice list |
| KN6000 | DISK (normSeg 0x10 b7) | **DISK MENU** screen |
| KN6000 | PROGRAM MENU (normSeg 0x10 b6) | **PROGRAM MENUS** screen |
| KN6000 | HELP, DEMO, START/STOP, PANEL MEMORY 2 | each changed the screen as expected |
| KN6500 | PIANO, POP | correct screens open (see limitation below) |
| KN7000 | PROGRAM MENUS, DISK MENU LOAD, PIANO | unchanged — no regression |

A button opening the screen its silkscreen names, with the right genre/category header,
is what confirms both the matrix and the wire mapping end to end.

## Open / honest limitations

- **LED register map.** The manual gives the full LED inventory by designator, colour and
  legend (CPL D125-D130, LCDL D101-D134, LCDC D106 DISPLAY HOLD, LCDR D301-D320,
  CPC D323-D345, CPR D351-D377, with `LN282RP…`=red / `LN382GP…`=green), but not the
  anode-group x SEG coordinate for most of them. `panel_led_frame()` is therefore a
  faithful *generic* decode onto `cpl_led#`/`cpr_led#`. This costs nothing today because
  **there is no KN6000 layout yet** — no LED is displayed. When one is drawn, the built-in
  **"Panel SW & LED test" (service manual p.22 §7.5)** is the ground truth to bind against,
  the same way the KN7000's F3+F4 sweep was used.
- **Within-group ordering** for the RHYTHM/SOUND group columns follows the manual's
  schematic column order, which is a good but not guaranteed proxy for physical
  left-to-right order. The POP and PIANO live checks confirm the scheme on two columns;
  the rest is consistent but not individually pixel-verified.
- **`0x20AC` / `0x20AD`** (normSeg 0x08 b7/b6) have no KN7000 counterpart. They are named
  SOUND CONTROLLER RESET / MODE from the CPL board's SW70/SW71 and the KN7000's analogous
  pair, but that is an inference, not a verified reading.
- **KN6500 text rendering.** The KN6500 opens the correct screens but their text is blank.
  That is the pre-existing table-ROM data gap (these drivers currently load the KN7000
  table ROMs; the KN6500's own is undumped) — unrelated to the panel.
- The KN6000/KN6500 still have **no `.lay` artwork of their own**, so they render the
  KN7000 layout. Buttons are reachable by tag/keyboard and by the Lua path used above;
  drawing a proper KN6000 panel is future work.
## Full matrix

| normSeg | port tag | wire ADDR | SW | mask | button |
|---|---|---|---|---|---|
| 0x00 | CPL_SEG0 | 0xC0 | 0 | 0x01 | PERFORMANCE PAD 1 |
| 0x00 | CPL_SEG0 | 0xC0 | 1 | 0x02 | PERFORMANCE PAD 4 |
| 0x00 | CPL_SEG0 | 0xC0 | 2 | 0x04 | 8 & 16 BEAT |
| 0x00 | CPL_SEG0 | 0xC0 | 3 | 0x08 | POP |
| 0x00 | CPL_SEG0 | 0xC0 | 4 | 0x10 | BALLAD |
| 0x00 | CPL_SEG0 | 0xC0 | 5 | 0x20 | ROK'N'ROLL & BLUES |
| 0x00 | CPL_SEG0 | 0xC0 | 6 | 0x40 | SOUL & FUNK |
| 0x00 | CPL_SEG0 | 0xC0 | 7 | 0x80 | MODERN DANCE |
| 0x01 | CPL_SEG1 | 0xC1 | 0 | 0x01 | PERFORMANCE PAD 2 |
| 0x01 | CPL_SEG1 | 0xC1 | 1 | 0x02 | PERFORMANCE PAD 5 |
| 0x01 | CPL_SEG1 | 0xC1 | 2 | 0x04 | U.S. TRAD |
| 0x01 | CPL_SEG1 | 0xC1 | 3 | 0x08 | COUNTRY |
| 0x01 | CPL_SEG1 | 0xC1 | 4 | 0x10 | BIG BAND & SWING |
| 0x01 | CPL_SEG1 | 0xC1 | 5 | 0x20 | JAZZ COMBO |
| 0x01 | CPL_SEG1 | 0xC1 | 6 | 0x40 | MARCH & WALTZ |
| 0x01 | CPL_SEG1 | 0xC1 | 7 | 0x80 | BALLROOM & SHOW TIME |
| 0x02 | CPL_SEG2 | 0xC2 | 0 | 0x01 | PERFORMANCE PAD 3 |
| 0x02 | CPL_SEG2 | 0xC2 | 1 | 0x02 | PERFORMANCE PAD 6 |
| 0x02 | CPL_SEG2 | 0xC2 | 2 | 0x04 | LATIN |
| 0x02 | CPL_SEG2 | 0xC2 | 3 | 0x08 | WORLD |
| 0x02 | CPL_SEG2 | 0xC2 | 4 | 0x10 | CUSTOM |
| 0x02 | CPL_SEG2 | 0xC2 | 5 | 0x20 | MEMORY LOAD |
| 0x02 | CPL_SEG2 | 0xC2 | 6 | 0x40 | SOUND ARRANGER SET |
| 0x02 | CPL_SEG2 | 0xC2 | 7 | 0x80 | SOUND ARRANGER OFF/ON |
| 0x03 | CPL_SEG3 | 0xC3 | 1 | 0x02 | AUTO PLAY CHORD MODE |
| 0x03 | CPL_SEG3 | 0xC3 | 2 | 0x04 | AUTO PLAY CHORD OFF/ON |
| 0x03 | CPL_SEG3 | 0xC3 | 3 | 0x08 | LCDL 1 |
| 0x03 | CPL_SEG3 | 0xC3 | 4 | 0x10 | LCDL 2 |
| 0x03 | CPL_SEG3 | 0xC3 | 5 | 0x20 | LCDL 3 |
| 0x03 | CPL_SEG3 | 0xC3 | 6 | 0x40 | LCDL 4 |
| 0x03 | CPL_SEG3 | 0xC3 | 7 | 0x80 | LCDL 5 |
| 0x04 | CPL_SEG4 | 0xC4 | 0 | 0x01 | MUTE UP 1 (PART 1 ON) |
| 0x04 | CPL_SEG4 | 0xC4 | 1 | 0x02 | MUTE DOWN 1 (PART 1 OFF) |
| 0x04 | CPL_SEG4 | 0xC4 | 2 | 0x04 | MUTE UP 2 (PART 2 ON) |
| 0x04 | CPL_SEG4 | 0xC4 | 3 | 0x08 | MUTE DOWN 2 (PART 2 OFF) |
| 0x04 | CPL_SEG4 | 0xC4 | 4 | 0x10 | MUTE UP 3 (PART 3 ON) |
| 0x04 | CPL_SEG4 | 0xC4 | 5 | 0x20 | MUTE DOWN 3 (PART 3 OFF) |
| 0x04 | CPL_SEG4 | 0xC4 | 6 | 0x40 | MUTE UP 4 (PART 4 ON) |
| 0x04 | CPL_SEG4 | 0xC4 | 7 | 0x80 | MUTE DOWN 4 (PART 4 OFF) |
| 0x05 | CPL_SEG5 | 0xC5 | 0 | 0x01 | MUTE UP 5 (PART 5 ON) |
| 0x05 | CPL_SEG5 | 0xC5 | 1 | 0x02 | MUTE DOWN 5 (PART 5 OFF) |
| 0x05 | CPL_SEG5 | 0xC5 | 2 | 0x04 | MUTE UP 6 (PART 6 ON) |
| 0x05 | CPL_SEG5 | 0xC5 | 3 | 0x08 | MUTE DOWN 6 (PART 6 OFF) |
| 0x05 | CPL_SEG5 | 0xC5 | 4 | 0x10 | MUTE UP 7 (PART 7 ON) |
| 0x05 | CPL_SEG5 | 0xC5 | 5 | 0x20 | MUTE DOWN 7 (PART 7 OFF) |
| 0x05 | CPL_SEG5 | 0xC5 | 6 | 0x40 | MUTE UP 8 (PART 8 ON) |
| 0x05 | CPL_SEG5 | 0xC5 | 7 | 0x80 | MUTE DOWN 8 (PART 8 OFF) |
| 0x06 | CPL_SEG6 | 0xC6 | 0 | 0x01 | MUTE UP 9 (PART 9 ON) |
| 0x06 | CPL_SEG6 | 0xC6 | 1 | 0x02 | MUTE DOWN 9 (PART 9 OFF) |
| 0x06 | CPL_SEG6 | 0xC6 | 2 | 0x04 | MUTE UP 10 (PART 10 ON) |
| 0x06 | CPL_SEG6 | 0xC6 | 3 | 0x08 | MUTE DOWN 10 (PART 10 OFF) |
| 0x06 | CPL_SEG6 | 0xC6 | 4 | 0x10 | MUTE UP 11 (PART 11 ON) |
| 0x06 | CPL_SEG6 | 0xC6 | 5 | 0x20 | MUTE DOWN 11 (PART 11 OFF) |
| 0x06 | CPL_SEG6 | 0xC6 | 6 | 0x40 | MUTE UP 12 (PART 12 ON) |
| 0x06 | CPL_SEG6 | 0xC6 | 7 | 0x80 | MUTE DOWN 12 (PART 12 OFF) |
| 0x07 | CPL_SEG7 | 0xC7 | 0 | 0x01 | MUTE UP 13 (PART 13 ON) |
| 0x07 | CPL_SEG7 | 0xC7 | 1 | 0x02 | MUTE DOWN 13 (PART 13 OFF) |
| 0x07 | CPL_SEG7 | 0xC7 | 2 | 0x04 | MUTE UP 14 (PART 14 ON) |
| 0x07 | CPL_SEG7 | 0xC7 | 3 | 0x08 | MUTE DOWN 14 (PART 14 OFF) |
| 0x07 | CPL_SEG7 | 0xC7 | 4 | 0x10 | MUTE UP 15 (PART 15 ON) |
| 0x07 | CPL_SEG7 | 0xC7 | 5 | 0x20 | MUTE DOWN 15 (PART 15 OFF) |
| 0x07 | CPL_SEG7 | 0xC7 | 6 | 0x40 | MUTE UP 16 (PART 16 ON) |
| 0x07 | CPL_SEG7 | 0xC7 | 7 | 0x80 | MUTE DOWN 16 (PART 16 OFF) |
| 0x08 | CPL_SEG8 | 0xC8 | 0 | 0x01 | PAGE UP |
| 0x08 | CPL_SEG8 | 0xC8 | 1 | 0x02 | PAGE DOWN |
| 0x08 | CPL_SEG8 | 0xC8 | 2 | 0x04 | TR |
| 0x08 | CPL_SEG8 | 0xC8 | 3 | 0x08 | HELP |
| 0x08 | CPL_SEG8 | 0xC8 | 4 | 0x10 | DISPLAY HOLD |
| 0x08 | CPL_SEG8 | 0xC8 | 5 | 0x20 | EXIT |
| 0x08 | CPL_SEG8 | 0xC8 | 6 | 0x40 | SOUND CONTROLLER MODE |
| 0x08 | CPL_SEG8 | 0xC8 | 7 | 0x80 | SOUND CONTROLLER RESET |
| 0x09 | CPL_SEG9 | 0xC9 | 0 | 0x01 | PERFORMANCE PADS/BANK |
| 0x09 | CPL_SEG9 | 0xC9 | 1 | 0x02 | PERFORMANCE PADS/STOP |
| 0x09 | CPL_SEG9 | 0xC9 | 2 | 0x04 | PERFORMANCE PADS/AUTO SETTING |
| 0x09 | CPL_SEG9 | 0xC9 | 3 | 0x08 | MUSIC STYLE ARRANGER |
| 0x09 | CPL_SEG9 | 0xC9 | 4 | 0x10 | VARIATION & MSA 1 |
| 0x09 | CPL_SEG9 | 0xC9 | 5 | 0x20 | VARIATION & MSA 2 |
| 0x09 | CPL_SEG9 | 0xC9 | 6 | 0x40 | DEMO |
| 0x0A | CPR_SEG0 | 0x00 | 0 | 0x01 | PIANO |
| 0x0A | CPR_SEG0 | 0x00 | 1 | 0x02 | GUITAR |
| 0x0A | CPR_SEG0 | 0x00 | 2 | 0x04 | STRINGS & VOCAL |
| 0x0A | CPR_SEG0 | 0x00 | 3 | 0x08 | BRASS |
| 0x0A | CPR_SEG0 | 0x00 | 4 | 0x10 | MALLET & ORCH PERC |
| 0x0A | CPR_SEG0 | 0x00 | 5 | 0x20 | WORLD |
| 0x0B | CPR_SEG1 | 0x01 | 0 | 0x01 | ORGAN & ACCORDION |
| 0x0B | CPR_SEG1 | 0x01 | 1 | 0x02 | SAX & WOODWIND |
| 0x0B | CPR_SEG1 | 0x01 | 2 | 0x04 | PAD |
| 0x0B | CPR_SEG1 | 0x01 | 3 | 0x08 | SYNTH |
| 0x0B | CPR_SEG1 | 0x01 | 4 | 0x10 | BASS |
| 0x0B | CPR_SEG1 | 0x01 | 5 | 0x20 | DRUM KITS |
| 0x0C | CPR_SEG2 | 0x02 | 0 | 0x01 | DIGITAL DRAWBAR |
| 0x0C | CPR_SEG2 | 0x02 | 1 | 0x02 | ACCORDION REGISTER |
| 0x0C | CPR_SEG2 | 0x02 | 2 | 0x04 | SOUND EXPLORER |
| 0x0C | CPR_SEG2 | 0x02 | 3 | 0x08 | MEMORY |
| 0x0C | CPR_SEG2 | 0x02 | 4 | 0x10 | SUSTAIN |
| 0x0C | CPR_SEG2 | 0x02 | 5 | 0x20 | DIGITAL EFFECT |
| 0x0D | CPR_SEG3 | 0x03 | 0 | 0x01 | SOUND DSP |
| 0x0D | CPR_SEG3 | 0x03 | 1 | 0x02 | PART EFFECT VARIATION |
| 0x0D | CPR_SEG3 | 0x03 | 2 | 0x04 | LCDR 1 |
| 0x0D | CPR_SEG3 | 0x03 | 3 | 0x08 | LCDR 2 |
| 0x0D | CPR_SEG3 | 0x03 | 4 | 0x10 | LCDR 3 |
| 0x0D | CPR_SEG3 | 0x03 | 5 | 0x20 | LCDR 4 |
| 0x0D | CPR_SEG3 | 0x03 | 6 | 0x40 | LCDR 5 |
| 0x0E | CPR_SEG4 | 0x04 | 0 | 0x01 | ONE TOUCH PLAY |
| 0x0E | CPR_SEG4 | 0x04 | 1 | 0x02 | SPLIT POINT |
| 0x0E | CPR_SEG4 | 0x04 | 2 | 0x04 | VARIATION & MSA 3 |
| 0x0E | CPR_SEG4 | 0x04 | 3 | 0x08 | VARIATION & MSA 4 |
| 0x0E | CPR_SEG4 | 0x04 | 4 | 0x10 | PART SELECT LEFT |
| 0x0E | CPR_SEG4 | 0x04 | 5 | 0x20 | PART SELECT RIGHT 2 |
| 0x0E | CPR_SEG4 | 0x04 | 6 | 0x40 | PART SELECT RIGHT 1 |
| 0x0E | CPR_SEG4 | 0x04 | 7 | 0x80 | SOLO |
| 0x0F | CPR_SEG5 | 0x05 | 0 | 0x01 | FADE IN |
| 0x0F | CPR_SEG5 | 0x05 | 1 | 0x02 | FADE OUT |
| 0x0F | CPR_SEG5 | 0x05 | 2 | 0x04 | FILL IN 1 |
| 0x0F | CPR_SEG5 | 0x05 | 3 | 0x08 | FILL IN 2 |
| 0x0F | CPR_SEG5 | 0x05 | 4 | 0x10 | CONDUCTOR LEFT |
| 0x0F | CPR_SEG5 | 0x05 | 5 | 0x20 | CONDUCTOR RIGHT 2 |
| 0x0F | CPR_SEG5 | 0x05 | 6 | 0x40 | CONDUCTOR RIGHT 1 |
| 0x0F | CPR_SEG5 | 0x05 | 7 | 0x80 | TECHNI-CHORD |
| 0x10 | CPR_SEG6 | 0x06 | 0 | 0x01 | INTRO & ENDING 1 |
| 0x10 | CPR_SEG6 | 0x06 | 1 | 0x02 | INTRO & ENDING 2 |
| 0x10 | CPR_SEG6 | 0x06 | 2 | 0x04 | TAP TEMPO |
| 0x10 | CPR_SEG6 | 0x06 | 3 | 0x08 | START/STOP |
| 0x10 | CPR_SEG6 | 0x06 | 4 | 0x10 | SEQUENCER PLAY |
| 0x10 | CPR_SEG6 | 0x06 | 5 | 0x20 | SEQUENCER EASY REC |
| 0x10 | CPR_SEG6 | 0x06 | 6 | 0x40 | PROGRAM MENU |
| 0x10 | CPR_SEG6 | 0x06 | 7 | 0x80 | DISK |
| 0x11 | CPR_SEG7 | 0x07 | 0 | 0x01 | TRANSPOSE - |
| 0x11 | CPR_SEG7 | 0x07 | 1 | 0x02 | TRANSPOSE + |
| 0x11 | CPR_SEG7 | 0x07 | 2 | 0x04 | R1/R2 OCTAVE - |
| 0x11 | CPR_SEG7 | 0x07 | 3 | 0x08 | R1/R2 OCTAVE + |
| 0x11 | CPR_SEG7 | 0x07 | 4 | 0x10 | GLOBAL EFFECT CHORUS |
| 0x11 | CPR_SEG7 | 0x07 | 5 | 0x20 | GLOBAL EFFECT MULTI |
| 0x11 | CPR_SEG7 | 0x07 | 6 | 0x40 | GLOBAL EFFECT REVERB |
| 0x11 | CPR_SEG7 | 0x07 | 7 | 0x80 | GLOBAL EFFECT MIC |
| 0x12 | CPR_SEG8 | 0x08 | 0 | 0x01 | MUSIC STYLIST |
| 0x12 | CPR_SEG8 | 0x08 | 1 | 0x02 | FAVORITES |
| 0x12 | CPR_SEG8 | 0x08 | 2 | 0x04 | SYNCHRO & BREAK |
| 0x12 | CPR_SEG8 | 0x08 | 4 | 0x10 | PANEL MEMORY SET |
| 0x12 | CPR_SEG8 | 0x08 | 5 | 0x20 | NEXT BANK |
| 0x12 | CPR_SEG8 | 0x08 | 6 | 0x40 | BANK VIEW |
| 0x12 | CPR_SEG8 | 0x08 | 7 | 0x80 | CUSTOM PANEL |
| 0x13 | CPR_SEG9 | 0x09 | 0 | 0x01 | PANEL MEMORY 1 |
| 0x13 | CPR_SEG9 | 0x09 | 1 | 0x02 | PANEL MEMORY 2 |
| 0x13 | CPR_SEG9 | 0x09 | 2 | 0x04 | PANEL MEMORY 3 |
| 0x13 | CPR_SEG9 | 0x09 | 3 | 0x08 | PANEL MEMORY 4 |
| 0x13 | CPR_SEG9 | 0x09 | 4 | 0x10 | PANEL MEMORY 5 |
| 0x13 | CPR_SEG9 | 0x09 | 5 | 0x20 | PANEL MEMORY 6 |
| 0x13 | CPR_SEG9 | 0x09 | 6 | 0x40 | PANEL MEMORY 7 |
| 0x13 | CPR_SEG9 | 0x09 | 7 | 0x80 | PANEL MEMORY 8 |

## The artwork (added 2026-07-20): `src/mame/layout/kn6000.lay`

Having the right matrix was not enough. `kn6000()` still ended up with
`config.set_default_layout(layout_kn7000)` (inherited from `kn7000()`), so the KN6000 was
drawn with the **KN7000's** panel: every clickable element sat at a KN7000 position,
carried a KN7000 legend and pointed at a KN7000 matrix cell. Clicking the artwork's
"PIANO" sent the KN7000's PIANO cell — a different function here. Verification that pressed
*ports* directly bypassed the artwork entirely, which is why it passed while clicking failed.

`kn6000()` now installs `layout_kn6000`, generated by **`tools/gen_kn6000_lay.py`**.

### Geometry source

The service manual reprints the owner's-manual **"Controls and functions" top view across
pp.5-6** — a two-page spread of the whole panel with every block outlined and every switch
silkscreened. p.5 is the left half (RHYTHM GROUP, SOUND ARRANGER, AUTO PLAY CHORD, LCDL soft
keys, POWER/DEMO, SOUND CONTROLLER trackball, MAIN + APC/SEQUENCER VOLUME, PERFORMANCE PADS,
MUSIC STYLE ARRANGER / ONE TOUCH PLAY / SPLIT POINT, VARIATION & MSA, FADE, FILL IN,
INTRO & ENDING, TAP TEMPO, SYNCHRO & BREAK, START/STOP, PITCH BEND/MODULATION); p.6 is the
right half (DISPLAY, LCDR soft keys, the 16 MUTE rockers, PAGE/DISPLAY HOLD/EXIT, SOUND
GROUP, PART EFFECT, TEMPO/PROGRAM, MUSIC STYLIST/FAVORITES, TRANSPOSE, R1/R2 OCTAVE,
PART SELECT, CONDUCTOR, SOLO, TECHNI-CHORD, GLOBAL EFFECT + MIC VOLUME, PANEL MEMORY,
SEQUENCER, PROGRAM MENUS, DISK).

**The drawing independently re-confirms the matrix a third time.** Read row-major, the 16
RHYTHM GROUP legends (8&16 BEAT, POP, BALLAD, ROCK'N'ROLL & BLUES / SOUL & FUNK, MODERN
DANCE, U.S. TRAD, COUNTRY / BIG BAND & SWING, JAZZ COMBO, MARCH & WALTZ, BALLROOM & SHOW
TIME / LATIN, WORLD, CUSTOM, MEMORY LOAD) fall exactly on the 6/6/4 split over
`CPL_SEG0/1/2` bits 2-7, and the 16 SOUND GROUP legends likewise on `CPR_SEG0/1/2` bits 0-5.
The pads are drawn 1/2/3 over 4/5/6 and wire as columns (1,4), (2,5), (3,6).

### What the layout covers

Like the KN7000 layout it does NOT reproduce the two-tier perspective; it flattens the
instrument into a `screen_block` (LCD + flanking soft keys + the two 4x4 category grids that
sit either side of it + the MUTE row and PAGE/HOLD/EXIT below) and three lower-deck blocks
left to right (`left_block`, `mid_block`, `right_block`).

**All 150 named matrix cells are placed** — the generator asserts this and prints
`COVERAGE: 150/150`, listing any MISSING/EXTRA cell, so a driver change that adds or renames
a button shows up immediately. Every placement is annotated with the silk name parsed live
out of `kn6000_cpanel.cpp`'s `device_input_ports()`, so the comment cannot drift from the
binding. Draggable controls: MAIN / APC-SEQUENCER / MIC volume faders and the infinite-rotary
TEMPO/PROGRAM wheel (shared `tools/slider_lib.lua`, needs MAME's `layout` plugin).

### Deliberately omitted

- **LED bindings.** Indicator dots are drawn where the manual shows them but carry **no
  output name**, so they stay dark. The KN6000 `[register][bit]` decode is still unconfirmed
  (see the limitation above) and a guessed binding would be a false claim. The built-in
  "Panel SW & LED test" (manual p.22 §7.5) remains the ground truth to bind against.
- PITCH BEND / MODULATION wheels and the trackball ball (no emulated control behind them;
  the trackball's RESET/MODE switches *are* drawn and bound), the CONTRAST trimmer (analog,
  not a matrix button), the POWER switch (decorative), and the keyboard bed.

### Shared generator vocabulary

`tools/lay_kit.py` was extracted from `tools/gen_lay.py` so the two generators share the
palette, the element/label registries and the emitters (`elem`/`two`/`label`/`P`/`L`/
`panel_bg`/`pair_h`/`wrap2`) instead of forking. The extraction is behaviour-preserving:
regenerating `kn7000.lay` afterwards produces a **byte-identical** file.

### Live click-through evidence (2026-07-20, DISPLAY=:0, windowed, snapshot-checked)

Each press was taken from the `.lay` element carrying that silk legend (tag + mask read out
of the layout, not the driver), so it is equivalent to clicking that drawn button:

| legend clicked | screen the firmware opened |
|---|---|
| POP | RHYTHM, genre header **POP** |
| BALLROOM & SHOW TIME | RHYTHM, header **BALLROOM & SHOW** |
| MEMORY LOAD | RHYTHM, header **MEMORY** |
| PIANO | SOUND – RIGHT 1, category **PIANO**, real piano voice list |
| DRUM KITS | SOUND – RIGHT 1, category **DRUM KITS** |
| SOUND EXPLORER | **SOUND EXPLORER** browser |
| DISK | **DISK MENU** |
| PROGRAM MENU | **PROGRAM MENUS** |
| DEMO | **DEMONSTRATION** |
| SEQUENCER EASY REC | **EASY RECORD** |
| PANEL MEMORY 5 | PMEM home (a panel-memory recall — correct) |

State-toggle buttons (SPLIT POINT, TECHNI-CHORD, SOUND DSP, BANK VIEW, MUSIC STYLIST) change
no screen and so are not evidence either way; they need the LED work to verify. KN6500 loads
the same layout and its PIANO/POP open the right screens (its text still renders blank — the
pre-existing table-ROM gap). KN7000 keeps its own layout, unregressed.
