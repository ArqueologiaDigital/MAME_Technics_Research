# Panel button runtime test — results (correcting the "buttons complete" claim)

**The prior claim "panel buttons complete and working" was WRONG.** Only DEMO and
START/STOP had ever been spot-checked. This is a systematic runtime test of all 155
wired button fields (SEG00–SEG15), prompted by the user's correction that many buttons
do not work.

## Harness (reusable — scratchpad btest4.lua / btest5.lua)
Boot, then for each button: hold it, and observe (a) the composited screen buffer
`0x9CE00000` (hash before/after) and (b) the LED outputs (`cpl_led*`/`cpr_led*` via
`output:get_value`). Two gotchas cost most of a tick and are worth recording:

1. **`manager.machine.time.seconds` returns INTEGER seconds, not fractional.** Every
   time-based sweep window (`frac = t - k*SLOT`) is therefore ~0 → the code stays in the
   "press" branch and never logs. **Fix: drive sub-second timing from a FRAME COUNTER**
   (increment on each `register_frame_done`), not from the clock.
2. **`register_frame_done` is dense (60 Hz) only when THROTTLED** (`-video none` without
   `-nothrottle`); with `-nothrottle` it fires sparsely in emulated time and skips
   buttons. Also: the earlier "emulator hangs / ENFILE" were mostly **missing autoboot
   scripts** — heredoc (`cat >`) writes into the scratchpad don't reliably persist here;
   use the Write tool for Lua files.

## Results — from the HOME screen, ~0.28 s hold
**64 / 155 buttons produce a visible effect (screen change or LED change); 91 do not.**

| Region | works (screen/LED from home) |
|--------|------------------------------|
| SEG00–03 rhythm genre/style | **8/8, 7/8, 7/8, 6/8** — screen changes, correctly mapped |
| SEG08–09 part mutes (col 1–9) | mostly work |
| SEG0D–0E sound select | mostly work |
| SEG04 VARIATION/FILL/TAP/MSA | **0/8** from home |
| SEG05 PADS / ONE-TOUCH | **0/8** |
| SEG06 ARRANGER/PADS/DEMO/SOUND-SET | 1/8 |
| SEG07 AUTO-MODE/MUSIC-STYLIST | 0/5 |
| SEG0A–0B mutes (inactive parts) | 1/8, 0/8 |
| SEG10–15 menu/transpose/sound | partial |

## Why the 91 have no *visible* effect — three blind spots (so 64 is a LOWER BOUND)
1. **Context.** Many are auto-accompaniment controls that need the **rhythm playing**
   or a **menu open** (VARIATION/FILL/MSA, PADS, ONE-TOUCH, ARRANGER). *Confirmed:*
   SEG04 "Tempo/Fade" is dead from home but changes the screen once the rhythm is
   started.
2. **Audio-only.** VARIATION/MSA change the **audible** accompaniment pattern, not the
   screen or any LED — undetectable by a screen+LED probe. *Confirmed:* SEG04
   VARIATION 1–4 stay dead even with the rhythm playing.
3. **Short hold.** DEMO works with a ~3 s hold (verified a prior tick) but shows no
   effect under the 0.28 s sweep hold.
4. **Placeholder / uncertain mapping.** 122/156 fields still carry placeholder names
   ("Fn 2xxx", "Sound Select NN", "Sound Group N", "Balance/Ctrl NN") from incomplete
   RE. Some of these may be **genuinely mis-mapped** — this is the real concern to chase,
   distinct from the context/audio cases above.

## Honest conclusion
The **core** panel works and is correctly mapped: rhythm-genre/style select, sound
categories, and active part mutes all respond on screen. But "complete/working" was
overstated — a large fraction have no confirmed effect, the 122 placeholder-named
fields are **unverified** against the descriptor-derived map
(`panel-button-normseg-map.md`), and **SEG16–SEG20 (DIAL/DATA) are absent from the
driver entirely**.

## Next
1. Cross-check the driver's per-bit **events** against the descriptor-derived map and
   fix mismatches (static, no emulator needed for the diff).
2. Re-test the context/audio-dependent buttons **in context** (rhythm playing, menus
   open) with longer holds, to separate "broken" from "works but invisible to this probe".
3. Add the missing SEG16–SEG20 (dial/data) input ports + layout.
