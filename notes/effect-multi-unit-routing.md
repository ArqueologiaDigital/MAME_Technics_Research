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

## 2026-07-11: effect-send matrix DECODED + kernel-routing blocker found (workflow wf_ff73662f-062)

### The effect-send register map (group-0x20, sub-TG @0x98050000) — CONFIRMED live
Emitter lib 0x4C036FBA/0x4C036F9A: latch = plane<<8 | channel<<4 | reg; reg 8 = SEND, reg A =
WET/DRY, plane 0x83 = DEPTH. Each effect = a fixed bus CHANNEL (distinguished by channel number):
| Effect | SEND reg | WET/DRY | DEPTH | default OFF | live-verified |
|---|---|---|---|---|---|
| REVERB | 0x80B8 (ch0B) | 0x803A (ch03) | 0x8338 | send 0x0366 ON | ✓ (audible on unit 0) |
| CHORUS | **0x8198 (ch19, BANK1)** | 0x809A? | 0x8378 | 0x0B00 (send 0) | ✓ low byte == per-part CHORUS DEPTH (60->63 tracked 0x3C->0x3F) |
| SOUND DSP | 0x8098 (ch09) / 0x80C8 (chC) | — | — | | |
| MULTI | 0x8298 (ch29, bank2) | | | | |
The 4 banks (0x80/81/82/83xx) plausibly map to the 4 SPORT returns / unit groups.

### Enable recipe (per-part chorus, RIGHT1) -- LIVE-VERIFIED
PROGRAM MENUS (SEG0C 0x04) -> SOUND (SEG00 0x02) -> PART SETTING (SEG00 0x02) -> PAGE UP (SEG0B 0x10)
to page 2/5. Column p2: SOUND DSP ON=SEG08 0x40, SOUND DSP DEPTH=SEG09 0x01, CHORUS ON=SEG09 0x04,
CHORUS DEPTH=SEG09 0x10. ★ FIRMWARE QUIRK: 0x8198 is only (re)written when the effect-bus block is
"active" -- CHORUS ON + depth alone leaves 0x8198=0x0B00; enabling SOUND DSP (or its depth) forces
the block refresh, then 0x8198 = 0x0B00|depth appears. (Verified: with SOUND DSP on + chorus depth
63, 0x8198 = 0x0B3F.)

### ★ THE BLOCKER (why chorus is still silent, even with a driver feed)
Implemented a SAFE multi-unit feed (reverted, commit not kept): tonegen captures 0x8198 -> chorus
send gain; the tick feeds unit-7 input (0xC370 = raw TG x chorus_send) and sums unit-7 return
(0xC350); gated on send>0 so REVERB stays BIT-IDENTICAL when chorus off (A/B verified 0/2.11M diff).
RESULT: with chorus enabled, unit-7 INPUT went nonzero (306484, my feed works) BUT unit-7 RETURN
(0xC350) stayed 0 -- and a scan of ALL return slots 0xC342-0xC359 showed ONLY unit 0 (reverb, C342/3)
produces output; every other unit outputs 0. So **feeding a unit's input slot does NOT make it run**:
the kernel's per-frame routing (which unit reads/writes which slot) is configured internally by the
firmware's effect setup, NOT a fixed slot map. The 10-unit CALL chain executes, but only unit 0 is
wired into the live audio path; the others are dormant regardless of their input slot contents.
NEXT (supervised / deeper RE): decode the kernel's per-frame routing setup -- how the firmware
configures which SPORT/slot each unit reads+writes when an effect is enabled (the I4-cursor walk +
the per-unit input/output pointer programming), and what makes unit 7 join the active chain. Only
then can the driver route audio to it. The send-matrix half is DONE (above); the kernel-routing half
is the remaining gate. Reverb (unit 0) remains complete and untouched.

## 2026-07-11 ★★ ROOT CAUSE of ALL silent effects: the unmodeled DSP FLAG3 input pin
Continuing the kernel-routing decode (static, from the dsp listings). The real gate is NOT the send
matrix and NOT the input slot -- it is a **SHARC FLAG3 hardware input pin**.

### Evidence
- Kernel (rec04): all 10 unit CALL slots are patched to real programs at boot (0x8400..0x8D00) and
  RUN every frame -- confirmed live (PM 0x8080-0x80A0 read: unit0=0x8400 ... unit7=0x8B00 chorus ...
  unit9=0x8D00; identical with chorus off/on). So every unit executes; dormancy is INSIDE the unit.
- Chorus program rec58 (relocated to 0x8B00), FIRST instruction:
    8400: IF NOT FLAG3_IN, JUMP 0x8432    <- skips the read/process/write when FLAG3 is LOW
    8401: R0 = DM(0x20, I4)               <- input = DM(I4+0x20); 8410/8419: DM(I4,M2)=R0 output
  FIVE effect programs gate on FLAG3_IN; the audible ones (rec49 reverb, rec56 enhancer) do NOT --
  they always run. That is exactly why reverb is audible and chorus/multi/etc. are silent.
- Kernel reset: `8071: BIT SET MODE2 0x18011` = FLAG0/FLAG1 as OUTPUTS; **FLAG3 stays an INPUT**
  (MODE2_FLG3O 0x40000 not set). Mainloop `8098: IF FLAG3_IN, MODIFY(I3,M3)` reads the pin.
- MAME models it: m_core->flag[3] (sharcops.hxx:1374/1390 FLAG3 / NOT FLAG3), set_flag_input(n,state)
  (sharc.cpp:1204). **But the KN7000 driver NEVER calls set_flag_input for the DSP** -> flag[3] stays
  0 forever -> every FLAG3-gated effect permanently takes the skip branch.

### So there are TWO gates for a non-reverb effect to be audible (both currently unmodelled):
1. **FLAG3 input pin must be driven high** when a FLAG3-gated effect is active. On the real board this
   DSP pin is driven by the CPU/control logic; the driver must model it (set_flag_input(3, ...)).
   Currently never set -> the units skip regardless of anything else. THE PRIMARY GATE.
2. The unit's SPORT input slot must be fed (the send-matrix half, decoded above: chorus send 0x8198
   -> unit-7 input). Only meaningful once FLAG3 lets the unit run.

### Concrete next steps (supervised / next tick)
a. Find what drives the DSP FLAG3 pin: RE the firmware for the CPU write (GPIO / control register bit)
   that goes high when chorus/multi/DSP effects are enabled -- likely near the effect-enable/apply
   code (0x4C0092B3 dispatcher, or a GPIO around 0x9807xxxx / 0x36008xxx). Wire it in the driver via
   m_dsp->set_flag_input(3, state).
b. THEN combine with the send feed (revert-kept design: feed unit-7 input 0xC370 = raw TG x chorus
   send, sum unit-7 return). Verify each FLAG3-gated effect runs cleanly (no rail) and reverb stays
   bit-identical (reverb doesn't gate on FLAG3, so driving FLAG3 must NOT change it -- easy A/B).
c. Note: FLAG3 gates 5 effects together (not per-unit), so it is a global "FLAG3-effects active"
   enable; per-unit activity is then the send levels + the unit's own params.
This is the missing keystone: the effects aren't mis-routed, they are HELD DISABLED at the DSP flag.
