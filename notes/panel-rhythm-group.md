# KN7000 panel — RHYTHM GROUP genre map + real-machine feedback (2026-07-07)

Source: user real-machine testing of the published binary (commit 34cc23b) +
snapshot-probe verification in the emulator. This is GROUND TRUTH for the panel wiring.

## RHYTHM GROUP — genre → input-bit map (VERIFIED, FIXED)
The 16 genre-select buttons are wired to **SEG00 / SEG01 / SEG02, bit b2..b7** → genres
0..15 in order (SEG02 stops at b5). Physical layout position i = genre i (2 rows × 8).
Verified by snapshot (pressing the bit opens that genre's RHYTHM screen):

| genre | name              | bit        | how verified |
|-------|-------------------|------------|--------------|
| 0     | 8&16 BEAT         | SEG00 0x04 | snapshot     |
| 1     | ROCK & POP        | SEG00 0x08 | snapshot     |
| 2     | BALLAD            | SEG00 0x10 | user (START/STOP=SEG00 0x10 → BALLAD) |
| 3     | JAZZ & SWING      | SEG00 0x20 | snapshot     |
| 4     | BALLROOM          | SEG00 0x40 | snapshot     |
| 5     | MOVIE & SHOW      | SEG00 0x80 | user (SYNCHRO=SEG00 0x80 → MOVIE&SHOW) |
| 6     | ENTERTAINER       | SEG01 0x04 | snapshot + user |
| 7     | ORGANIST          | SEG01 0x08 | user |
| 8     | 60s & 70s         | SEG01 0x10 | user |
| 9     | MODERN DANCE      | SEG01 0x20 | user |
| 10    | SOUL & R&B        | SEG01 0x40 | user |
| 11    | COUNTRY & WESTERN | SEG01 0x80 | user |
| 12    | MARCH & WALTZ     | SEG02 0x04 | user |
| 13    | LATIN & WORLD     | SEG02 0x08 | user |
| 14    | CUSTOM            | SEG02 0x10 | user |
| 15    | MEMORY            | SEG02 0x20 | user |

Genre order = GenreStyleTable @0x48735EE4. b0/b1 of each SEG are NOT genres
(the old layout's MEMORY/LOAD, SOUL & FUNK on SEG01 b0/b1 lit nothing — consistent).

**FIXED**: RG list rebuilt to this map (gen_lay.py). The old binding was SEG01/SEG02
b0-b7 (off-by-bits) and collided with START/STOP (SEG00 0x10) etc.

## Collision cleanup (FIXED this pass)
Because SEG00 b2..b7 are the genre bits, buttons the layout wrongly put on those bits were
spuriously opening genres. Unbound (made decorative) until their real bits are found:
- **START/STOP** (was SEG00 0x10 = BALLAD) → unbound
- **SYNCHRO & BREAK** (was SEG00 0x80 = MOVIE & SHOW) → unbound
- **LCD-LEFT soft-keys** (LCDPARTS OFF column, was SEG00 0x04/0x08/0x20 = genres 0/1/3, plus
  0x01/0x02) → unbound

## Confirmed WORKING (do NOT change — user)
- DISK, PROGRAM MENUS (buttons).
- Whole SOUND GROUP button+LED: PIANO, GUITAR, MALLET & ORCH PERC, WORLD, STRINGS & VOCAL,
  BRASS, SAX & WOODWIND, ORGAN & ACCORDION, DIGITAL DRAWBAR, ORGAN TABS, ACCORDION REGISTER,
  PAD, SYNTH, BASS, DRUM KITS.

## REMAINING mis-bindings / TODO (from user feedback — follow-up ticks)
`current_button (layout bit) => what it really triggers` — so the real bit for the *target*
function is the one currently on `current_button`:
- **RESOLVED (2026-07-07)** — the 5 LCD-LEFT soft-keys are wired to **SEG03 b3..b7**
  (top->bottom = LCD LEFT 1..5): 0x08, 0x10, 0x20, 0x40, 0x80. Direct user evidence:
  FADE(SEG03 0x20)=>LCD LEFT 3, VAR4(SEG03 0x40)=>LCD LEFT 4, SPLIT(SEG03 0x80)=>LCD LEFT 5;
  LCD LEFT 1-2 (0x08/0x10) extrapolate the run. Bound the left soft-key column to these bits;
  freed FADE IN/OUT (SEG03 0x20), VARIATION 4 (SEG03 0x40), SPLIT POINT (SEG03 0x80) — those
  buttons' real bits are now TBD. NOTE: these are context-sensitive soft-keys (inactive on the
  home screen), so they can't be snapshot-verified from home — user re-test to confirm.
- **RESOLVED (2026-07-07)** — the MUTE-mislabel clues gave real bits for 5 functions,
  all snapshot-verified from a clean boot, now bound to their real buttons:
  | function            | real bit    | verified by            | layout change |
  |---------------------|-------------|------------------------|---------------|
  | DEMO                | SEG09 0x40  | snapshot: DEMONSTRATION | DEMO btn was SEG06 0x40 (no-op) → SEG09 0x40 |
  | PADS BANK SELECT    | SEG09 0x01  | snapshot: PADS BANK SELECT | PADS "BANK" btn was decorative → SEG09 0x01 |
  | OTHER PARTS & FR    | SEG08 0x04  | snapshot: PT1-16 mixer | was decorative → SEG08 0x04 |
  | HELP                | SEG08 0x08  | snapshot: HELP FUNCTION | was decorative → SEG08 0x08 |
  | MUSIC STYLE ARRANGER| SEG09 0x08  | user (mode toggle; MSA btn was SEG04 0x08 = fader) | → SEG09 0x08 |
  **Finding**: SEG08 and SEG09 are DEDICATED-FUNCTION segments, NOT the part-mute matrix.
  The MUTES[] table put "part mute up/down" on SEG08/SEG09 (MUTE 3-10) — all wrong. Those
  8 mute buttons are now unbound (decorative). The REAL part-mute matrix is unknown (TBD);
  MUTE 1-2 (SEG05) and 11-16 (SEG0A/0B) are left bound but unverified (likely also wrong).
- LCD LEFT 2 => ROCK & POP, LCD LEFT 3 => JAZZ & SWING, LCD LEFT 5 => 8&16 BEAT
  (already resolved by the genre map + unbinding the left column).

## Other observations (TODO)
- **SOUND EXPLORER (RESOLVED 2026-07-07)**: NOT a layout bug. LED sweep (soundsweep.lua) shows the
  firmware itself lights cpr48 (PIANO) + cpr26 (BASS) when SEG0D 0x04 is pressed — SOUND EXPLORER is
  a browser mode with no own category LED, so the emulator is faithful and the user's "lights
  PIANO+BASS" is the real behaviour. Nothing to change (EXPLORER green_led stays dark). The 15 real
  category LEDs all match OPLED (confirms "works perfectly").
- **MEMORY / EW EXPANSION (RESOLVED 2026-07-07)**: were unbound. LED sweep (extsweep.lua):
  **MEMORY = SEG0E 0x10 (cpr16), EW EXPANSION = SEG0E 0x20 (cpr17)** — SOUND GROUP b4/b5, category
  (radio) behaviour continuing PAD/SYNTH/BASS/DRUM KITS. Now bound.
- **No visual feedback** (button not associated with any input, or no LED):
  all PART EFFECT + GLOBAL EFFECT; all BANK VIEW / NEXT BANK / PANEL
  MEMORY; all CUSTOM PANEL / CUSTOMIZE / FAVORITES; SEQUENCER PLAY & EASY REC; SD LOAD
  (orange); APC SET/OFF-ON (lower) [MODE = SEG03 0x02, found]; DISPLAY HOLD; EXIT; PAGE UP/DOWN.
  → these need their input bits found (many may be dedicated events, not in the scanned segs).

## Genre LEDs (RESOLVED 2026-07-07)
Re-swept the genre-select LEDs on the corrected bits (scratchpad/genreled2.lua: press each
genre bit, diff which `cpl_led` turns on — radio behaviour). Result: **genre G → cpl_led[3 +
8*(G//4) - (G%4)]**:
| genre | cpl | genre | cpl | genre | cpl | genre | cpl |
|-------|-----|-------|-----|-------|-----|-------|-----|
| 0 | 3  | 4 | 11 | 8  | 19 | 12 | 27 |
| 1 | 2  | 5 | 10 | 9  | 18 | 13 | 26 |
| 2 | 1  | 6 | 9  | 10 | 17 | 14 | 25 |
| 3 | 0  | 7 | 8  | 11 | 16 | 15 | 24 |
Bound via the `GENRE_LED` dict in gen_lay.py (the RHYTHM GROUP green_leds now use it, not OPLED).
The SEG01/SEG02 values matched the old OPLED (already correct); the 4 SEG00 genres (0,1,3,4 =
cpl3/2/0/11) were the ones previously dark. NB the sweep also shows cpl_led1/cpl_led10 (which the
old OPLED labelled "START/STOP"/"SYNCHRO" transport LEDs) are really the genre-2 / genre-5 LEDs.
