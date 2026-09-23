# Does the effects kernel meet its frame budget at the part's rated 60 MHz?

IC306 is marked S21065LKS240 — a 60 MHz part. The driver had been running it at
66 MHz, set in an overlay commit whose stated result was that the effects kernel
started completing 44,100 frames per second. That is a frame-budget threshold,
not a hardware rating, so moving to 60 MHz needed a measurement rather than a
hope.

**Answer: 60 MHz is safe.** The output is byte-identical to 66 MHz.

## Method

`chord_harness.lua` holds a C-major chord on the key bed, because a DSP test with
no notes playing is not a test — a DSP fed silence outputs silence, and the first
run of this measurement returned "100% stale, 0% non-zero" purely because nothing
was playing. The window before `PRESS_AT` is the deliberate no-stimulus null, so
every run carries its own control.

```sh
PRESS_AT=18 STOP_AT=27 ./kn kn7000 -rompath <romsets> -window -nothrottle \
    -autoboot_script chord_harness.lua -str 30 -log -wavwrite out.wav
```

The driver is temporarily instrumented in `dsp_audio_tick` to count, per IRQ0
tick, whether the kernel's output buffer at DM `0xC342` changed since the last
tick. A tick where it did not is a frame the kernel failed to finish in time.

## Result, measured 2026-09-23

| DSP clock | ticks | stale | non-zero | WAV md5 |
|---|---:|---:|---:|---|
| 66 MHz (old) | 1,146,600 | 752,581 (65.64%) | 394,018 | `ecde0b33…` |
| **60 MHz (rated)** | 1,146,600 | 752,581 (65.64%) | 394,018 | `ecde0b33…` |
| 6 MHz (control) | 1,146,600 | 1,090,727 (**95.13%**) | 391,102 | — |

60 and 66 MHz are identical to the byte. The 6 MHz control is what makes that
meaningful: a clock too slow to meet the budget drives stale from 66% to 95%, so
the measurement demonstrably *can* see a clock that does not keep up. Without
that row, "no difference" would be indistinguishable from "the clock is not
wired to anything".

Audio sanity, same runs: in the notes window the capture is RMS 305.9 against a
silence-window null of 33.3, so the harness is producing real audio and not
measuring its own noise floor. At 6 MHz the same window reads 561.1 — audibly
different, consistent with the kernel failing to process and the dry path passing
through.

(The 65% steady-state stale figure is not a defect: the chord decays, and a
decayed-to-zero output is identical frame to frame by definition.)

## Found while doing this: two mapping defects

1. **A regression this session introduced.** Shrinking the 21065L's internal data
   region from `0x09000-0x1FFFF` to `0x09000-0x0FFFF` — on a reading of the
   part's documented internal window — unmapped memory the effect kernel uses
   heavily: **1642 distinct addresses in `0x10000-0x1FFFF`**, 886k writes in one
   run. The DSP produced no output at all. Reverted; the region is now sized from
   what the uploaded program demonstrably reaches (`0x1FFE6`), not from an
   assumed geometry. Neither the per-commit build sweep nor a boot test can catch
   this: it compiles, and the machine boots fine with dead effects.

2. **A pre-existing gap, not from this session.** The kernel makes **1,566,833**
   accesses to DM `0x42A9` and 19,619 to `0x434B`, both below `0x08000` and
   unmapped in every version of this device. A further 122 distinct addresses
   land at `0x20000+`, including some at `0x48xxxxxx` and `0x54E0xxxx` that look
   like wild pointers. Recorded, not diagnosed — the SHARC's short-word and
   long-word address views are the obvious suspects and nothing here establishes
   which.
