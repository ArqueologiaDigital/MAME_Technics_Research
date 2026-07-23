# KN5000 effects — the COMPLETE per-effect parameter list, read live from RAM

Closes backlog item 16 of `kn5000-dsp-INDEX.md`. Companion to `kn5000-dsp-paramnames.md`
(which LOCATED the name→slot binding statically but could not extract the lists) and
`kn5000-dsp-parameters.md` (§4, the 85-name table). Everything here is **MEASURED** — read
out of live main-CPU RAM in MAME while the effect-edit page was on screen and pixel-verified
against the LCD — unless tagged otherwise.

Tools: `tools/kn5000_dsp_paramlist.py` (decodes the 85 names/units from the program ROM and
resolves a capture), `tools/kn5000_cycle.lua` (drives the panel, cycles the TYPE selector,
dumps the array), `tools/kn5000_dsp_paramlist_capture.json` (the live dump).

## 1. Mechanism — CONFIRMED LIVE

`kn5000-dsp-paramnames.md` reverse-engineered the binding statically:

```
  slot count : RAM[0x29AA]
  name index : RAM[0x29AC + slot]         (1-BASED into the 85-name table)
  name string: 0xE324D5 + 17*(index-1)    (16 chars + ':', stride 17)
  unit string: 0xE3241A +  2*(index-1)    (stride 2)
  page type  : RAM[0x8D38]
```

This is now **verified live**. On the DSP EFFECT edit page, `RAM[0x8D38]=0x0B`,
`RAM[0x29AA]=5`, `RAM[0x29AC..]=[7,8,49,1,3]`, which the table resolves to
`DEPTH / LFO SPEED / LFO WAVEFORM / VOLUME / REV SEND` — and the LCD showed exactly
`TYPE: CHORUS  DEPTH 30  LFO SPEED 0.6Hz  LFO WAVEFORM SIN  VOLUME 84  REV SEND 75`.
Every one of the 52 effect entries below was captured the same way and its parameter
*names, order and count* agree with the on-screen page. The 1-based index, the maincpu
program space, and the two live page types (0x0A reverb, 0x0B DSP effect) are all
confirmed exactly as `-paramnames.md` predicted.

### How to reach the pages (reproducible recipe)

Panel serial is driven from lua via `mach.ioport.ports[":cpanel:CPR_SEG*"]` /
`":cpanel:CPL_SEG*"` fields, `field:set_value(1/0)`. The front-panel EFFECT buttons
(`CPR_SEG3` DIGITAL EFFECT/DSP EFFECT/DIGITAL REVERB) only *toggle* the effect on the
HOME screen and do **not** open an editor — a plain OR long hold does nothing visible
(tested to 5 s). The editor pages are reached through the **SOUND menu**:

1. `MENU:SOUND` = `CPR_SEG10` mask `0x04` (short press) → SOUND MENU (page type 0x01→0x02).
2. On the SOUND MENU the LCD side soft-keys are LEFT/RIGHT 1..5:
   * **DSP EFFECT** = RIGHT-4 = `CPL_SEG7` `0x02` → editor page type **0x0B** (38 effects).
   * **REVERB** = RIGHT-2 = `CPL_SEG8` `0x02` → editor page type **0x0A** (12 reverbs + 2 delays).
   * REVERB & EQ PRESETS = RIGHT-1 `CPL_SEG8 0x04` (type 0x09, preset selector, no array).
   * EQUALIZER = RIGHT-3 `CPL_SEG8 0x01` (type 0x0C, fixed 8-slot master EQ).
   * ACOUSTIC ILLUSION = RIGHT-5 `CPL_SEG7 0x01` (type 0x0E, fixed TYPE + LEVEL).
3. On an editor page the bottom soft-keys are **TYPE / PARAMETER / VALUE**, each an
   up/down pair. **TYPE up = UP-1 = `CPL_SEG10` `0x20`**, TYPE down = DOWN-1 = `CPL_SEG10 0x10`.
   Stepping TYPE re-runs the loader (`LABEL_F457CF`) and repopulates `RAM[0x29AC]` for the
   newly-selected effect. The list does **not** wrap — it saturates at the last entry
   (Felipe confirmed ~56 further presses do nothing).

⚠ **Screen lags RAM.** Near a TYPE change the loader updates `RAM[0x29AC]` a few frames
before the LCD finishes redrawing, so a snapshot taken immediately can show the *previous*
effect's title over the *new* array. The capture below therefore waits ~1.0 s after each
press before reading **both** RAM and the screenshot, so title and array are consistent.
(This was caught live: at the tail, RAM had already advanced to the last effect while the
LCD still showed the previous name.)

## 2. Coverage

| page | type | mechanism | entries |
|---|---|---|---|
| DSP EFFECT | 0x0B | name-index array (0x29AC) | **38** effects |
| DIGITAL REVERB | 0x0A | name-index array (0x29AC) | 12 reverbs (one shared list) + SINGLE DELAY + MULTI TAP DELAY |
| EQUALIZER | 0x0C | **fixed** 8-slot (loader `0x4C10`) | master 4-band EQ: LOW/MID-LOW/MID-HIGH/HIGH × (FREQ Hz, GAIN dB) |
| ACOUSTIC ILLUSION | 0x0E | **fixed** 4-slot (loader `0x4E10`) | TYPE (STANDARD/PERCUSSIVE/SYMPHONIC/DEEP SPACE) + ILLUSION LEVEL |
| REVERB & EQ PRESETS | 0x09 | preset selector, no per-param array | — |

So **50 distinct effect algorithms now have a fully-named, ordered parameter list**
(38 DSP + 12 reverbs; SINGLE DELAY and MULTI TAP DELAY additionally appear on the reverb
page with a REV-SEND-less variant). The EQUALIZER and ACOUSTIC ILLUSION pages use fixed
hard-coded layouts (the `0x8D38` = 0x0C / 0x0E loader branches from `-paramnames.md` §B),
**not** the 85-name array, so they are documented above but are outside the array mechanism.

## 3. THE DELIVERABLE — DSP EFFECT page (type 0x0B), in TYPE-selector order

Regenerate with:
`python3 tools/kn5000_dsp_paramlist.py <program.rom> --resolve tools/kn5000_dsp_paramlist_capture.json`

| # | EFFECT | slots | ordered parameters (unit) |
|---|---|---|---|
| 0 | CHORUS | 5 | DEPTH, LFO SPEED(Hz), LFO WAVEFORM, VOLUME, REV SEND |
| 1 | MODULATED CHORUS | 7 | DEPTH, SLOW LFO SPEED(Hz), FAST LFO SPEED(Hz), FAST LFO BALANCE, LFO WAVEFORM, VOLUME, REV SEND |
| 2 | ENHANCER | 7 | MANUAL, LOW MIX, HIGH MIX, DELAY L(ms), DELAY R(ms), VOLUME, REV SEND |
| 3 | FLANGER | 8 | DEPTH, LFO SPEED(Hz), RESONANCE, MANUAL, PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 4 | PHASER | 8 | DEPTH, LFO SPEED(Hz), RESONANCE, MANUAL, PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 5 | ENSEMBLE | 5 | DEPTH, LFO SPEED(Hz), LFO WAVEFORM, VOLUME, REV SEND |
| 6 | GATED REVERB | 6 | GATE TIME(ms), HIGH DAMP GAIN, THRESHOLD, MASK TIME(ms), VOLUME, REV SEND |
| 7 | SINGLE DELAY | 7 | DELAY L(ms), DELAY R(ms), FEEDBACK L, FEEDBACK R, HIGH DAMP GAIN, VOLUME, REV SEND |
| 8 | MULTI TAP DELAY | 12 | DELAY 1-4(ms), PAN 1-4, FEEDBACK, HIGH DAMP GAIN, VOLUME, REV SEND |
| 9 | DISTORTION | 4 | DRIVE, ADJUST, VOLUME, REV SEND |
| 10 | OVERDRIVE | 4 | DRIVE, ADJUST, VOLUME, REV SEND |
| 11 | FUZZ | 4 | DRIVE, ADJUST, VOLUME, REV SEND |
| 12 | EXCITER | 6 | DRIVE, ADJUST, HIGH EMPHASIS FC(Hz), EMPHASIS GAIN, VOLUME, REV SEND |
| 13 | COMPRESSOR | 6 | THRESHOLD, RATIO, ATTACK SENS.(s), RELEASE SENS.(s), VOLUME, REV SEND |
| 14 | SLOW ATTACKER | 5 | THRESHOLD, ATTACK RATE(s), RELEASE RATE(s), VOLUME, REV SEND |
| 15 | PARAMETRIC EQ | 17 | (BAND EMPHASIS FC/Q/G) × 5 bands, VOLUME, REV SEND |
| 16 | AUTO PAN | 6 | DEPTH, LFO SPEED(Hz), PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 17 | VIBRATO | 6 | DEPTH, LFO SPEED(Hz), PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 18 | AUTO WAH | 5 | RESONANCE, MANUAL, SWEEP RANGE, VOLUME, REV SEND |
| 19 | ROTARY SPEAKER | 15 | DRIVE, VOLUME ADJUST, TREBLE DEPTH, TREBLE FAST(Hz), SLOW(Hz), WIND UP(s), WIND DOWN(s), BASS DEPTH, BASS FAST(Hz), BASS SLOW(Hz), WIND UP(s), WIND DOWN(s), VOLUME, SLOW/FAST, REV SEND |
| 20 | ROCK ROTARY | 15 | (identical to ROTARY SPEAKER) |
| 21 | RING MODULATOR | 5 | OSC SPEED(Hz), PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 22 | MIX UP | 8 | DEPTH, SLOW LFO SPEED(Hz), FAST LFO SPEED L(Hz), FAST LFO SPEED R(Hz), PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 23 | S. DELAY+CHORUS | 11 | DELAY DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, CHORUS DRY/WET, DEPTH, LFO SPEED(Hz), LFO WAVEFORM, VOLUME, REV SEND |
| 24 | S. DELAY+S. DELAY | 12 | DELAY1 DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, DELAY2 DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, VOLUME, REV SEND |
| 25 | S. DELAY+FLANGER | 14 | DELAY DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, FLANGER DRY/WET, DEPTH, LFO SPEED, RESONANCE, MANUAL, PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 26 | S. DELAY+VIBRATO | 11 | DELAY DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, DEPTH, LFO SPEED, PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 27 | S. DELAY+PHASER | 14 | DELAY DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, PHASER DRY/WET, DEPTH, LFO SPEED, RESONANCE, MANUAL, PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 28 | AUTO WAH+S. DELAY | 10 | RESONANCE, MANUAL, SWEEP RANGE, DELAY DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, VOLUME, REV SEND |
| 29 | PEQ+CHORUS | 9 | BAND EMPHASIS FC/Q/G, CHORUS DRY/WET, DEPTH, LFO SPEED, LFO WAVEFORM, VOLUME, REV SEND |
| 30 | PEQ+S. DELAY | 10 | BAND EMPHASIS FC/Q/G, DELAY DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, VOLUME, REV SEND |
| 31 | PEQ+FLANGER | 12 | BAND EMPHASIS FC/Q/G, FLANGER DRY/WET, DEPTH, LFO SPEED, RESONANCE, MANUAL, PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 32 | PEQ+VIBRATO | 9 | BAND EMPHASIS FC/Q/G, DEPTH, LFO SPEED, PHASE, LFO WAVEFORM, VOLUME, REV SEND |
| 33 | PEQ+COMPRESSOR | 9 | BAND EMPHASIS FC/Q/G, THRESHOLD, RATIO, ATTACK SENS.(s), RELEASE SENS.(s), VOLUME, REV SEND |
| 34 | PEQ+COMPR+DIST | 11 | BAND EMPHASIS FC/Q/G, THRESHOLD, RATIO, ATTACK SENS., RELEASE SENS., DRIVE, ADJUST, VOLUME, REV SEND |
| 35 | PEQ+COMPR+OVERDR | 11 | (identical to PEQ+COMPR+DIST) |
| 36 | PEQ+DIST+DELAY | 12 | BAND EMPHASIS FC/Q/G, DRIVE, ADJUST, DELAY DRY/WET, DELAY L, DELAY R, FEEDBACK L, FEEDBACK R, VOLUME, REV SEND |
| 37 | PEQ+OVERDR+DELAY | 12 | (identical to PEQ+DIST+DELAY) — last entry, selector saturates here |

Notes: `S. DELAY` = SINGLE DELAY, `PEQ` = PARAMETRIC EQ. The BAND EMPHASIS FC/Q/G triple
is index 51/52/53; "DELAY L/R, FEEDBACK L/R" is 22/23/24/25 wherever a single-delay block
appears. Effects sharing an identical name-index list (e.g. FLANGER≡PHASER, DIST≡OVERDRIVE≡FUZZ,
ROTARY≡ROCK ROTARY) differ only in DSP coefficients, not in the UI parameter set.

## 4. THE DELIVERABLE — DIGITAL REVERB page (type 0x0A)

All twelve standalone reverbs share ONE parameter list (each captured live: CONCERT/DARK/
BRIGHT/WAVE ×2 by stepping TYPE up, ROOM/PLATE ×2 by stepping down):

| EFFECT(s) | slots | parameters |
|---|---|---|
| ROOM 1/2, PLATE 1/2, CONCERT 1/2, DARK 1/2, BRIGHT 1/2, WAVE 1/2 | 5 | REVERB TIME(s), PRE DELAY(ms), HIGH DAMP GAIN, ER.LEVEL, VOLUME |
| SINGLE DELAY (reverb page) | 6 | DELAY L(ms), DELAY R(ms), FEEDBACK L, FEEDBACK R, HIGH DAMP GAIN, VOLUME |
| MULTI TAP DELAY (reverb page) | 11 | DELAY 1-4(ms), PAN 1-4, FEEDBACK, HIGH DAMP GAIN, VOLUME |

The reverb-page delays are the same effects as on the DSP page but drop the trailing
REV SEND slot (a reverb IS the reverb bus, so there is nothing to send).

## 5. Validation — predict-then-check, all PASS

* **Count match.** `RAM[0x29AA]` equals the number of parameters shown on the LCD (verified
  by screenshot on CHORUS=5, and by the tail saturating at the correct last effect).
* **Family sanity.** Every listing is coherent for its effect family — no reverb shows
  THRESHOLD/RATIO, no compressor shows REVERB TIME. Reverbs → REVERB TIME/PRE DELAY/HIGH
  DAMP GAIN/ER.LEVEL; compressor → THRESHOLD/RATIO/ATTACK/RELEASE; gated reverb → GATE TIME/
  MASK TIME/THRESHOLD; rotary → TREBLE/BASS horn depths + WIND UP/DOWN + SLOW/FAST; ring
  modulator → OSC SPEED.
* **DSP-target PINS proven end-to-end** (main-CPU name ↔ DSP write from `-parameters.md`/
  `-paramnames.md`):
  * `HIGH DAMP GAIN`(idx 36) is a **reverb** slot — the exact §5 prediction (DARK>BRIGHT
    damping ordering). Confirmed: it is present on every reverb, gated reverb and delay.
  * `THRESHOLD`/`RATIO`(40/41) are the **compressor**'s — §D prediction confirmed.
  * `BAND EMPHASIS FC/Q/G`(51/52/53) appear as **exactly 5 bands** on PARAMETRIC EQ —
    §D's "PEQ = 5×`op0x70`" is confirmed from the UI side (17 = 5×3 + VOLUME + REV SEND).
  * `LFO SPEED`(8)/`LFO WAVEFORM`(49) appear on **precisely** the effects with an LFO
    (chorus/flanger/phaser/pan/vibrato/ensemble/mixup) — the `hi12=0x082` LFO-read /
    `092.A` phase cell. Effects without an LFO never list them.
  * ms-helper (op 0x68) → GATE TIME/MASK TIME on GATED REVERB, DELAY L/R everywhere a
    delay block appears; deg-helper (op 0x69) → PHASE and PAN 1..4 on MULTI TAP DELAY.
* **The §5 "0x90 universal level" ambiguity is resolved.** The universal trailing controls
  are `VOLUME`(1/2) and `REV SEND`(3), NOT `DEPTH`(6). DEPTH is specifically a modulation
  depth and appears only on LFO effects.
* **No contradiction** was produced by Felipe's propagation cross-check: every name is
  consumed with a unit/range consistent with its effect, and the leftover names
  (e.g. INTENSITY 83, EXCITE 84, blank 85) correspond to slots not exposed on these two
  pages (85 is the null/blank name that appears past the count as trailing array garbage).

## 6. What remains / not covered

* EQUALIZER (0x0C) and ACOUSTIC ILLUSION (0x0E) pages use fixed hard-coded slot lists, not
  the 85-name array; their names were read from the LCD (§2) but not through this mechanism.
* A handful of the 85 names are never referenced by any effect reachable through these two
  pages: `INTENSITY`(83), `EXCITE`(84) — likely belonging to a fixed-layout page (possibly
  ACOUSTIC ILLUSION's internals or an unreached preset). Low value to chase.
* The effect-name RAM display buffer is at DRAM `0x30AE5` but is written progressively during
  redraw, so it is unreliable for scripted reads — the screenshot is authoritative for names.
