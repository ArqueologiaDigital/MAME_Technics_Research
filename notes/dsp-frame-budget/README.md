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

## Re-used 2026-09-23 to check that a round of review fixes changed no audio

After an adversarial review of the MAME PR stack, ~200 lines were changed in
response to it: the driver's five-window `io_r`/`io_w` pair was split so the
0x98000000 sound window has its own handlers, the MN10300 core's `device_reset`
gained clearing of the interrupt-delivery state, the SHARC's fixed-point dual
add/subtract gained the ALUSAT flag correction on its add half, and nine ROM
images were marked BAD_DUMP. Build, boot-screen pixel count and `-validate` all
stayed green — which is exactly the set that stayed green while the data-region
regression below was silencing the DSP.

So the same harness was re-run on the PR branch tip:

```sh
PRESS_AT=18 STOP_AT=27 ./kn kn7000 -rompath <romsets> -window -nothrottle \
    -autoboot_script chord_harness.lua -str 30 -wavwrite out.wav
```

| | value |
|---|---|
| WAV md5 | **`ecde0b33`** — identical to the 60 MHz reference above |
| notes window 18.5-27.0 s | RMS 618.2 |
| silence window 0.5-17.5 s | RMS 46.6 (the null) |

Byte-identical output is the strongest available form of "the audio path is
untouched", and the 13x RMS ratio confirms the capture is real signal rather than
a noise floor — the harness reported `3 key field(s)` and `chord down at
t=18.02`, so the stimulus demonstrably happened.

⚠ **The RMS figures are not comparable with the 305.9 / 33.3 quoted earlier on
this page.** Identical md5 means identical samples, so any difference is in how
the numbers were taken, not in the signal: different window bounds, and this pass
averaged over all channels. Use the md5 for comparison; quote RMS only with its
window.

The capture has **3 channels**, which is not a driver defect: the machine holds
two speaker devices, `:speaker` (2 inputs) and
`:fdc:0:35hd:floppysound:output` (1), and `sound_manager` sums
`dev.inputs()` across all of them (`src/emu/sound.cpp:247`). Every MAME machine
with a modelled floppy records the drive-sound channel.

## Found while doing this: two mapping defects

1. **A regression this session introduced.** Shrinking the 21065L's internal data
   region from `0x09000-0x1FFFF` to `0x09000-0x0FFFF` — on a reading of the
   part's documented internal window — unmapped memory the effect kernel uses
   heavily: **1642 distinct addresses in `0x10000-0x1FFFF`**, 886k writes in one
   run. The DSP produced no output at all. Reverted; the region is now sized from
   what the uploaded program demonstrably reaches (`0x1FFE6`), not from an
   assumed geometry. Neither the per-commit build sweep nor a boot test can catch
   this: it compiles, and the machine boots fine with dead effects.

2. **A pre-existing gap, not from this session, and it has a clean explanation.**
   The kernel hammers DM addresses below `0x08000`, which are unmapped in every
   version of this device — `0x42A9` alone took 1,566,833 accesses in the long
   run. Those are not wild pointers. **Double them and they land inside the
   mapped internal region:**

   | address | accesses | x2 | |
   |---|---:|---|---|
   | `0x042A9` | 154,534 | `0x08552` | inside the code region |
   | `0x0434B` | 3,790 | `0x08696` | inside the code region |
   | `0x00020`/`0x00024` | 102 each | — | IOP registers, `<0x100` |

   Weighted by access count over one run: **99.63% of the sub-`0x8000` traffic is
   explained by the x2 relation, 0.37% is IOP register access below `0x100`, and
   nothing is left over.** By distinct address it is 126 of 134.

   The control matters, because x2 is not a demanding test on its own: the mapped
   span `0x8000-0x1FFFF` halves to `0x4000-0x7FFF`, so an address drawn at random
   from `0..0x7FFF` would satisfy it 50% of the time. 99.63% by traffic against a
   50% baseline is a mechanism, not a coincidence.

   That points at an address VIEW the device map does not model, and MAME already
   models exactly that shape one size up: `adsp21062_device::data_2m` puts normal-word
   internal memory at `0x20000` and a SHORT-WORD view of the same storage at
   `0x40000` — twice the normal-word base — reached through `dm_short_r`/`dm_short_w`
   handlers that scale the index. The 21065L's normal-word internal memory is at
   `0x8000`, and `0x8000 / 2 = 0x4000`, which is exactly where the unexplained
   traffic sits. So the family precedent for a second, scaled view of the same
   memory is in the tree; what is NOT established is that the 21065L has a
   long-word window at that position, and nothing here names one.

   **Measured: mapping it changes nothing.** With `0x04000-0x07FFF` mapped as plain
   RAM the 1,566,833 unmapped accesses drop to **0** and the captured audio is
   byte-identical — md5 `56022f1a1978` either way, notes RMS 305.9, silence null
   33.3. So this is log noise and documentation debt, not an emulation defect, and
   whatever is written there is never read back in a way that reaches the output.

   **Left unmapped deliberately.** Adding a window to a CPU device shared by eight
   drivers, on a correlation and a family analogy rather than a datasheet, is the
   kind of speculative modelling this PR exists to avoid. The one-line change and
   the evidence for it are both recorded here, so it is cheap to do the moment the
   21065L's memory map is in hand.

   A further 122 distinct addresses land at `0x20000+`, including some at
   `0x48xxxxxx` and `0x54E0xxxx`. Those are not explained by anything here.
