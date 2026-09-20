# WSA1R: why the upstream extraction paints late and short

**The headline, and it corrects two of my own conclusions.**

The extraction is **not stalled**. It paints the UI, ~28x later than the overlay and 492 bytes
short, permanently. Two independent causes, both measured here:

1. **The timebase runs 16x slow.** `ticktap.lua`: the overlay's INTT1 handler bumps RAM 0x0080
   **4879** times in 10 emulated seconds, the extraction **305**. Ratio **15.997**. That is
   upstream's 8-bit timer prescaler shifting by 7/9/11 (fc/128, fc/512, fc/2048) where the
   databook gives fc/8, fc/32, fc/128.

2. **CPU 1 never drains the link latch.** `linkread.lua`: the overlay reads 0x7C0000 16 times by
   tick 878 and 908 times by tick 1305 (the micro-DMA burst), settling at 948 with one timeout.
   The extraction: **ZERO reads through tick 2163**, flag 0x8A oscillating 0x80/0x00, timeout
   counter climbing 1 -> 2 -> 3.

⚠ **Both of these invalidate earlier conclusions of mine, and the reason is the same mistake.**
I ran every comparison for 20 emulated seconds. The overlay paints at t=3-6 s; the extraction needs
t=85-135 s. So:

  * "the screen is blank" was **wrong** -- it was blank *at 20 s*;
  * "the CPU core is exonerated, because swapping the overlay's entire tlcs900 in still stalls" was
    **wrong for the same reason** -- that test also ran 20 s, far too short to show a 16x
    difference. The prescaler is back in scope, with `ticktap.lua` as its measurement;
  * and the timer prescaler, which I reverted as "disproven", is a real defect after all.

A measurement window shorter than the effect you are looking for reports absence. Index by the
machine's own tick, not by wall-clock seconds -- which is what `linkread.lua` does, deliberately,
so the 16x timebase difference cannot confound the link result.


Suggested permanent home: `kn7000_mame/notes/wsa1-probes/`.
Two binaries are compared throughout:

  WORKING   ~/compartilhado/kn7000_mame_build/kn7000   (overlay driver + overlay tlcs900 core)
  STALLING  /tmp/claude-1000/wsa1drv/wsa1              (upstream-extraction branch technics-wsa1-driver)

A symlink rompath under the extraction's ROM_LOAD names (no ROM copied) lives in
`../exroms/wsa1r/`.

## ticktap.lua -- how fast is the firmware's timebase?
Question: how many times per emulated second does CPU 1's INTT1 handler bump the
tick word at RAM 0x0080, and from which PC?  Pass = ~4879 writes in 10 emulated
seconds, all from PC 0xF82D14 (488.28 Hz = 28 MHz / 2048 / 28).

    kn7000 wsa1r -rompath <roms> -window -skip_gameinfo -str 10 \
      -autoboot_script ticktap.lua -autoboot_delay 0
    wsa1   wsa1r -rompath ../exroms -window -str 10 \
      -autoboot_script ticktap.lua -autoboot_delay 0

Measured 2026-09-20: overlay 4879, extraction 305. Ratio 15.997.

## vramfill.lua / vram2.lua -- does the UI ever get painted?
Question: how many of the SED1330's 32 KiB of display RAM are non-zero?
vramfill.lua samples every emulated second, vram2.lua every 5 s and keeps a max
(for the long extraction runs).  Pass = the overlay's two milestones, 452 then
5562.

    kn7000 ... -str 20  -autoboot_script vramfill.lua   -> 452 @ t=3 s, 5562 @ t=6 s, flat to 22 s
    wsa1   ... -str 260 -autoboot_script vram2.lua      -> 452 @ t=85 s, 5070 @ t=135 s, flat to 295 s

The extraction is NOT stalled; it paints late and 492 bytes short, permanently.

## linkread.lua / linkread_fine.lua -- is the inter-processor link being drained?
Question: does CPU 1 ever consume bytes from the link latch at 0x7C0000, or does
it only ever time out?  Reads are counted with a read tap (micro-DMA reads count
too, and show up attributed to whatever PC the CPU is sitting at, i.e. the wait
loop at 0xF8E671-0xF8E681).  Also samples RAM 0x8A bit 7 ("transfer in
progress", polled at prom_a 0xF8E671), RAM 0x6007E1 (the byte the timeout path
at 0xF8E694 increments) and RAM 0x0080, so results can be indexed by TICK rather
than by second and the 16x timebase difference does not confound them.
linkread_fine.lua is the same probe printing every second instead of every ten.

    kn7000 ... -str 20  -autoboot_script linkread_fine.lua
    wsa1   ... -str 290 -autoboot_script linkread.lua

Pass = the overlay's shape: tick 878 -> 16 reads, tick 1305 -> 908 reads (the
micro-DMA burst), settling at 948 with flag8A=00 and ONE timeout.
Measured on the extraction: ZERO reads through tick 2163, flag8A oscillating
0x80/0x00 and the timeout counter climbing 1 -> 2 -> 3.

## pcprobe.lua, linkstate.lua, unmapval.lua, rows.py (../)
Earlier pass: per-frame PC histogram for both CPUs; tick/flag/timeout sampler;
return-value probe for every window that is noprw() in one build and unmapped in
the other (all 00 in both); mechanical address-map row extractor for the two
drivers.

---

## The rest of the probes in this directory

Collected from the six-axis comparison run of 2026-09-20. The ones named in the sections above are
the ones whose numbers are quoted; the remainder are the supporting instruments from the same pass,
kept because a measurement whose scaffolding is gone cannot be repeated.

Broadly:

* `ticktap.lua`, `linkread*.lua`, `linkstate.lua`, `vram*.lua` -- the four quoted measurements.
* `pcprobe.lua`, `pcsample.lua`, `pcs*.lua` -- per-frame PC histograms for both processors, used to
  establish that neither CPU is wedged in a single loop.
* `unmapval.lua` -- what every window that is `noprw()` in one build and unmapped in the other
  actually returns. All `00` in both, which is what rules the open-bus theory out.
* `hstap.lua`, `hs2.lua`, `hs3.lua`, `kern.lua`, `after.lua` -- handshake and kernel-entry taps.
* `rows.py` -- mechanical address-map row extractor, so the two drivers' maps compare as ranges
  rather than as text.
* `cmp_strip.py`, `cmp_fnsplit.py` -- comment-stripping and per-function splitting, so "is this
  file the same apart from comments" is answered by a diff rather than by eye.
* `rt_dispon.lua` -- which code issues the final `DISP ON` and with what parameter byte, logging
  the CPU 1 PC for every DISP ON/OFF. The parameter is what turns the three layer attributes on,
  so this names the routine that makes the panel show anything.
* `rt_who54.lua` -- who calls the DISP-attribute routine at prom_a 0xF8F7B8 with all three layers
  on (parameter 0x54), by dumping the stack above SP when the parameter byte goes out.
* `sfr.lua`, `tap.lua`, `linktap.lua`, `long*.lua`, `rt_probe.lua`, `waitjob.sh` -- earlier or
  narrower variants kept for provenance.

⚠ Run them with `-window` and a `-seconds_to_run` that is LONG ENOUGH. That is the whole lesson of
this directory: the extraction's milestones land at t=85-135 s, and every conclusion drawn from a
20-second window in this session was wrong.


## ⚠ Late addition: the extraction's renderer never draws a pixel

Instrumenting `draw_graphics_scanline()` at frame 8000 (t ~ 133 s, just after the UI lands):

    UG#8000  vram_nonzero=5070  bytes_in_layers=5070     <- the content IS where the code reads
    UG#8000  px_seen=0  px_set=0  mx=1                   <- and the drawing loop never runs

So the extraction's `update_graphics()` is entered with all three pages enabled, correct geometry
(`fp=15 lf=240 sl1=241 ap=40 ov=1 dm=3 d=1 sad1=0000 sad2=2600 sad3=4C00 cr=40 fx=8`), and every
one of the 5070 non-zero display-RAM bytes inside the windows it reads -- and examines no pixels.

★ `mx=1` is `MX_XOR`, **not** the `MX_OR` the device's own command log reports and not the `MX=0`
that `wsa1r_lcd_command_census.py` reads out of all three of the firmware's immediate OVLAY writes.
So `m_mx` is being set from a path not accounted for. That is the next thread to pull, and it is a
defect in the upstream-candidate `sed1330` change, not in the machine.
