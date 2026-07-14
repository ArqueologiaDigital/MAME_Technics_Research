# KN7000 layout (gen_lay.py) discrepancy list

Layout input bindings in `kn7000_mame/tools/gen_lay.py` whose bound button **name or position**
disagrees with the authoritative `wf/panel-button-names.md`. Line numbers are from the current
`gen_lay.py`. Only real discrepancies are listed; the great majority of bindings (genres, mute
matrix, sound-group categories 0x00–0x0F, transport, TRANSPOSE/OCTAVE, DISK/PROGRAM MENUS, etc.)
already agree and are not repeated.

---

## 1. HIGH — SEG0E 0x10 / 0x20 are SUSTAIN / DIGITAL EFFECT, not SOUND GROUP MEMORY / EW EXPANSION

This is the single most impactful layout fix. `verify_3` proved (HELP-info) that
`SEG0E 0x10 = SUSTAIN` and `SEG0E 0x20 = DIGITAL EFFECT` (PART EFFECT cluster), NOT sound-group
buttons. gen_lay.py binds them the wrong way in **three** places:

- **`SG[]` list, L306** — `("MEMORY","SEG0E","0x10")` and `("EW EXPANSION","SEG0E","0x20")` are the
  last two SOUND GROUP entries. **Fix:** remove these two SEG0E bindings from `SG` (the real
  physical MEMORY / EW EXPANSION sound-group buttons are on other, still-unresolved bits — leave the
  two SOUND GROUP cells drawn but unbound, like other TBD buttons).
- **`PE_BITS`, L319 + PART EFFECT loop L320** — SUSTAIN and DIGITAL EFFECT are currently drawn with
  `(None,None)` (decorative). **Fix:** bind them:
  `PE_BITS = {"SUSTAIN":("SEG0E","0x10"), "DIGITAL EFFECT":("SEG0E","0x20"),
  "SOUND DSP":("SEG0F","0x01"), "VARIATION":("SEG0F","0x02")}`.
- **`OPLED`, L60–61** — `("SEG0E","0x10"):"cpr_led16"` and `("SEG0E","0x20"):"cpr_led17"` were swept
  as "MEMORY / EW EXPANSION" SOUND-GROUP category LEDs under the wrong assumption. **Fix:** re-sweep
  these two LEDs as SUSTAIN / DIGITAL EFFECT toggles (they are almost certainly not radio-category
  LEDs); move the mapping out of the SOUND GROUP LED block and re-verify the output cell.

Net effect: SEG0E 0x10/0x20 move from the SOUND GROUP block to the PART EFFECT block.

## 2. MED — SEG03 b3–b7 left soft-keys are mislabelled with keyboard-part names

`LCDPARTS`, L146–148: the left LCD soft-key column (bound to `SEG03 0x08/0x10/0x20/0x40/0x80`,
correct bits) is drawn with the visible labels `RIGHT1 / RIGHT2 / LEFT / ACCOMP1 / ACCOMP2`
(`L(nm,168,…)`, L151). These are context-dependent LCD soft-keys with NO fixed function; their
authoritative **physical** name is `LCD LEFT 1 … LCD LEFT 5` (the real unit prints no silkscreen
text beside them, and what each key does depends on the current screen). **Fix:** relabel the left
column `LCD LEFT 1…5`. The right column mirror is `SEG0F 0x04–0x40` (MED, LCD RIGHT 1…5 soft-keys,
currently unbound) — it may be bound there, but keep MED.
(part on/off reading retracted — these soft-keys are not a RIGHT1/RIGHT2/LEFT/ACCOMP part selector.)

## 3. MED — the six PERFORMANCE PADS are drawn unbound

`padspec` loop, L250–253: the 6 pad shapes get labels `1…6` (+SOLO on pads 5/6) but **no
`tag`/`mask`** — they are decorative. The pad-trigger bits are now HIGH-confidence
(`verify_0`, ev2030): **Fix:** bind pad i → its bit:
PAD1=`SEG00 0x01`, PAD2=`SEG01 0x01`, PAD3=`SEG02 0x01`, PAD4=`SEG00 0x02`,
PAD5=`SEG01 0x02` (SOLO), PAD6=`SEG02 0x02` (SOLO). The existing `str(i+1)` labels and the
`if i in (4,5): SOLO` annotation already match the authoritative pad numbering — only the binding is
missing.

## 4. LOW — "OTHER PART & FR" label typo

Screen block, L156: `L("OTHER",…)` + `L("PART & FR",…)`. The ROM/HELP canonical name (descriptor
pool @0x4839504F, entry 58) is **OTHER PARTS/TR**. **Fix:** relabel `OTHER PARTS/TR` (the "FR" is a
typo for "TR"; the button IS correctly bound to `SEG08 0x04`). Same typo exists in the driver.

## 5. LOW — AUTO PLAY CHORD OFF/ON button unbound

Left block, L213: `("OFF/ON",505,54,None,None)` (top OFF/ON in the AUTO PLAY CHORD group) is
unbound. Authoritative candidate for this button is `SEG03 0x04` (AUTO PLAY CHORD OFF/ON, LOW —
static candidate pending emulator HELP confirm; see needs_emulator.md). **Fix (after confirmation):**
bind AUTO PLAY CHORD OFF/ON → `SEG03 0x04`. Note the driver already names SEG03 0x04
"AUTO PLAY CHORD OFF/ON".

## 6. LOW — VARIATION VAR2 unbound; a candidate bit exists

`VARBITS`, L267: only VAR1 = `SEG10 0x04` is bound; VAR2–4 are `(None,None)`. Authoritative VAR2
candidate is `SEG09 0x10` (MED — non-linear arg-hi inference). **Fix (optional):** bind VAR2 →
`SEG09 0x10`; leave VAR3/VAR4 unbound (no evidence).

## 7. LOW — GLOBAL EFFECT CHORUS / MULTI unbound (ambiguous bits)

`GE_BITS`, L326 binds only REVERB=`SEG13 0x40`, MIC=`SEG13 0x80` (both correct). CHORUS and MULTI
are drawn unbound. The two remaining cluster bits are `SEG13 0x10` and `SEG13 0x20` (ev2062/ev2061),
but which is CHORUS vs MULTI vs DIGITAL EFFECT is unresolved (see needs_emulator.md). Leaving them
unbound is currently correct; do NOT guess the CHORUS/MULTI ordering.

## 8. LOW (cosmetic) — ACCORDION REGISTER vs ACCORD REGISTER

`SG[]`, L305: `"ACCORDION REGISTER"` (SEG0D 0x20). ROM SoundGroupNameTable name is
`ACCORD REGISTER`; the panel silkscreen reads `ACCORDION REGISTER`. Binding + position are correct;
this is a silkscreen-vs-ROM spelling choice only — no functional fix needed.

---

## Verified consistent (spot-checked, no discrepancy)

- Genre grid `RG[]` (L223–226): SEG00/01/02 b2–b7 → genres 0–15, exact match incl. positions.
- Mute matrix `MUTES[]` (L170–173): SEG04–07 up/down pairs, including SEG07 0x40/0x80 = PART16
  (the layout is AHEAD of the driver here — it already binds these).
- `SG[]` sound categories 0x00–0x0F (all but the two SEG0E entries in fix #1), PART EFFECT SOUND
  DSP/VARIATION, SEQUENCER DISK/PROGRAM MENUS, TRANSPOSE/OCTAVE, TECHNI-CHORD/PART SELECT/CONDUCTOR
  group anchors, FADE/TAP/SYNCHRO/INTRO/START-STOP, DEMO, MUSIC STYLE ARRANGER, ONE TOUCH PLAY,
  SPLIT POINT, PADS BANK/STOP/AUTO SETTING — all agree with the authoritative map.

## Count

- Discrepancies: **8** — 1 HIGH (three-site SEG0E fix), 2 MED (soft-key labels, unbound pads),
  5 LOW (OTHER PARTS/TR typo, APC OFF/ON bind, VAR2 bind, CHORUS/MULTI, ACCORD spelling).
