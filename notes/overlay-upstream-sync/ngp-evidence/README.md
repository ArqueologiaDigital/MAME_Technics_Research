# NGP prescaler evidence: NESdev thread 18579

Saved 2026-09-26 because a comment in this tree cited it as "SNK's own NGP developer manual"
and drew the opposite conclusion from what it actually says. Keeping the source means the next
reader can check rather than inherit.

`t18579.txt` / `t18579.xhtml` — https://forums.nesdev.org/viewtopic.php?t=18579 (2019).

## What it actually contains

- **byuu**: *"if we go off of the dev manual, T16 is 128/fc. 6144000/128 = 48000hz"*, and
  *"if I don't use the dev manual values for T1 (8/fc), T4 (32/fc), T16 (128/fc), T256
  (2048/fc), then the audio in every [game] runs twice as slow"*. Those four ratios are
  verbatim Toshiba Table 3.8 (1), so this is the databook restated, not a second source.
- **mic_, on real hardware**: timer 0, mode bits `%10` (= phiT4), TREG0 = 0x32, interrupt every
  ~12800 states at 3,072,000 states/s ⇒ the tap runs at **12 kHz**. Databook phiT4 = fc/32 =
  192 kHz; 12 kHz is fc/512, upstream's value.
- **mic_ also states the state definition** this project derived independently: *"the TLCS-900/H
  being clocked at 6,144,000 Hz and each state being two clock cycles, you've got 3,072,000
  states/second"* — i.e. 1 state = fc/2, which is what the parked `tlcs900-real-timings` branch
  implements.
- **The clock gear**: byuu gives the prescaler input as `6144000/(4,8,16,32,64)` by gear
  setting, and says SysPro claims it is "always 384KHz". 6.144 MHz : 384 kHz = exactly 16:1,
  the disputed factor.
- byuu's own timings miss hardware (he gets 0xFE where mic_ measures 0xEA) and he concludes
  *"the cycle timings mic_ lists are not accurate"*. **The two authorities disagree.**

## What it does NOT contain

A measurement of a prescaler tap in isolation, and any statement from SNK about tap ratios.
