# Effect multi-unit routing — why only REVERB is audible (2026-07-11)

Triage of the effects-sweep "CHORUS = no audible effect" SUSPECT. **Verdict: NOT a bug — an
architectural limitation of the current single-path DSP bridge.** Documented so the fix is scoped.

## What the live taps show
With a note played (–nodrc, all unit return + input TDM slots tapped):

| unit | program | input slot | input max | return slot | return max |
|---|---|---|---|---|---|
| 0 | active global effect (reverb) | 0xC362 | **924234** | 0xC342 | **~620000** |
| 4 | rec06 | 0xC36A | 0 | 0xC34A | 0 |
| 7 | rec58 CHORUS | 0xC370 | 0 | 0xC350 | 0 |
| 8 | rec34 EQ | 0xC372 | 0 | 0xC352 | 0 |
| 9 | rec49 | 0xC376 | 0 | 0xC356 | 0 |

Only unit 0 receives signal and produces output. Toggling CHORUS ON (short-press :SEG11 0x04) and
selecting a chorus TYPE both leave unit 7's input at **0** — the chorus unit never sees audio, so it
cannot be heard. Reverb works because the panel reverb effect executes on **unit 0**, the one slot
the bridge is wired to.

## Why — the real vs modelled signal path
- REAL hardware: the tone generator holds a per-channel OUTPUT-BUS / effect-send matrix (sub-TG
  group 0x20 = latch 0x8000-0x83Fx, 64 channels × 0x10 stride; regs 0-6 = the mix/pan/route base
  `0380/0B80/0680/8CD0`, reg 8 = a per-channel send level, reg A = a wet/dry or return level). Via
  this matrix each part is sent to whichever effect unit(s) its reverb/chorus/DSP sends select, over
  the 4 SPORT pins (SDIE0-3), and the TG sums ALL the effect returns into the DAC. So reverb, chorus,
  EQ and a SOUND DSP can all be heard at once.
- OUR bridge (kn7000_dsp_bridge_device): sends the single summed TG stream to **unit 0's input**
  (0xC362/3) and reads **unit 0's return** (0xC342/3), applying just three extracted registers
  (0x803A wet/dry, 0x80B8 send, 0x8338 depth). It models ONE effect send + ONE return. The other
  units get no input and their returns are never read.

## What making chorus/EQ/DSP audible would require (scoped, deferred)
A real TG effect-mixer model:
1. Decode the group-0x20 matrix per channel: which TX pin / effect unit each part's reverb/chorus/
   DSP send routes to, and at what level (regs 8/A semantics beyond the 3 reverb ones already known —
   e.g. which reg is the chorus send vs the DSP send). Needs a capture sweep toggling each global
   effect + each part's send and diffing the matrix.
2. Bridge: feed the TG stream (scaled by each per-unit send) into MULTIPLE unit input slots
   (0xC362/0xC370/0xC372/...), and SUM the corresponding unit returns (0xC342+0xC350+0xC352+...)
   weighted by their return levels, into the DAC crossfade.
3. Verify each effect is independently audible and that reverb is unchanged.

This is a multi-day architecture change; reverb (the primary effect) is faithful today. Marking the
sweep's CHORUS/EQ/SOUND-DSP results **EXPLAINED (single-path limitation)**, not FAIL.

## Note for the sweep re-run
The MULTI/SOUND-DSP batch health tests will all read "no audible effect" for the same reason until
multi-unit routing lands — they exercise units other than 0. Their TYPE-SELECTION (loading the
program onto its unit) does work and is verified; only the audible return is missing. So the sweep's
value right now is (a) confirming type selection reprograms each unit without crashing/railing, and
(b) the recipe catalogue — not audible-effect verdicts.
