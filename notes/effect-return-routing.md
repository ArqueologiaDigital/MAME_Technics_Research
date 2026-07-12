# Per-effect DSP return routing — reverb-off no longer mutes the other effects

**Date:** 2026-07-12. Resolves the open faithfulness question flagged in
effect-multi-unit-routing.md (chorus/multi/sound-DSP were scaled by the reverb return `gret`, so
turning reverb off wrongly muted them).

## The question
The bridge mix scaled the chorus/sound-DSP/multi wets by `gret` = the reverb's direct/return crossfade
(sub-TG ch03 reg 0xA = 0x803A, the register the REVERB button flips). So with reverb OFF (`gret`=0),
all three other effects went silent — but the KN7000's effects are independent, so that looked wrong.
Shared master return, or per-effect returns?

## Method — live capture (scratchpad/retcap/)
Tapped the sub-TG register-indirect bus at 0x98050000. GOTCHA: the MN10300 writes the address latch as
the LOW halfword (off 0x98050000, mask 0x0000FFFF) and the data as the HIGH halfword (mask 0xFFFF0000 =
the 0x98050002 byte) — both surface at off 0x98050000, split by mask. Decode: latch=`data&0xFFFF` on the
low write; on the high write, `val=(data>>16)&0xFFFF` applied to the latched addr. group-0x20 =
`(addr & 0xFC00)==0x8000`; ch=`(addr>>4)&0x3F`, reg=`addr&0xF`. Then toggled each effect button in
isolation from a fresh boot and diffed the full group-0x20 file (cap3.lua).

## Result — each effect owns a DISTINCT return; reverb-off touches ONLY the reverb's
Per-effect toggle -> register moved (isolated, reproduced):
| Effect (button)        | SEND (reg 8)      | RETURN (reg 0xA)   | on/off values        |
|------------------------|-------------------|--------------------|----------------------|
| REVERB   (SEG0F 0x04)  | ch0B.r8 (0x80B8)  | **ch03.rA (0x803A)** | 0x007F <-> 0x7F00  |
| SOUND DSP (SEG0F 0x08) | ch09.r8 (0x8098)  | **ch09.rA (0x809A)** | 0x0000 <-> 0x007F  |
| MULTI    (SEG10 0x04)  | ch29.r8 (0x8298)  | **ch06.rA (0x806A)** | 0x0000 <-> 0x007F  |
| CHORUS   (SEG11 0x04)  | ch19.r8 (0x8198)  | *(none)*           | send 0x0B00<->0x0B3C |
| DIGITAL EFFECT (SEG10 0x08) | — | — | no group-0x20 write (separate subsystem) |

Return level = the reg-0xA LOW byte (0x7F on, 0 off), same convention as the reverb return. DECISIVE:
toggling REVERB moved ONLY ch03.rA; ch09.rA / ch06.rA and every other channel's reg-0xA stayed put. So
the returns are PER-EFFECT and independent — the reverb toggle does not gate the others. CHORUS is the
odd one: toggling it moves only its SEND (ch19.r8) — it has no separate return register, so its wet is
send-driven with a fixed makeup.

## Fix (kn7000.cpp)
- tonegen now captures ch09.rA -> `m_gain_dsp_ret`, ch06.rA -> `m_gain_multi_ret` (low byte / 127).
- bridge `set_effect_returns(dsp_ret, multi_ret)`; the mix scales SOUND DSP by `gdsp_ret` and MULTI by
  `gmul_ret` (their OWN returns) instead of `gret`; CHORUS drops the `gret` factor entirely (no return
  register, send already applied at its input, fixed makeup).
- panel_scan polls the two new returns into the bridge (250 Hz), alongside the reverb gains.

## Verification
1. **Reverb-only guard BIT-IDENTICAL** — /tmp/money.lua on the new binary md5 0787b60cc3cec696c7aa43bb471b2b1b
   == reference. When all non-reverb effects are off their paths are gated (send=0), so the reverb path
   is untouched. And when reverb is ON, gret==gdsp_ret==gmul_ret≈1.0 so the mix is unchanged too.
2. **Fix works** — reverb OFF + SOUND DSP ON + note held: the SOUND DSP output slot 0xC356 peaks at
   231293 (2.8% FS) while the reverb slot 0xC342 = 0. Before the fix that 231293 was multiplied by
   gret=0 (muted); now it reaches the DAC via ch09.rA. The two-run DAC differential also shows reverb-off
   output changes when sound-DSP toggles (peak 1907 -> 2020), which was impossible before (it would have
   been bit-identical).

## Scope / remaining
- CHORUS wet uses a fixed makeup (no hardware return register found for it); DIGITAL EFFECT is a
  separate subsystem (no TG-bus write) — both left as-is, documented.
- The *_WET=0.60 makeup constants are still uncalibrated (need Felipe's ear); this fix is about the
  reverb-independence (correctness), not the absolute wet level.

## 2026-07-12: stress validation of the fix + a panel-toggle observation
STRESS TEST (scratchpad/retcap/excite*.lua): each effect isolated (reverb off for the non-reverb ones),
slammed with an 8-key cluster (C4..G4 held) = the loudest realistic input, watching each effect's own
DSP output slot for rails + the DAC for clips.
- SOUND DSP isolated (reverb OFF) + 8-key cluster: own slot 0xC356 peak 488644 (5.8% FS), 0 railed
  frames -> the per-effect-return fix is AUDIBLE IN ISOLATION and STABLE under heavy drive (reproduces
  last tick's 231293 single-note result, now under an 8-note cluster). Before the fix this was muted
  (xgret=0 with reverb off).
- REVERB + 8-key cluster: own slot 0xC342 peak 1338464 (16.0% FS), 0 rails -> stable; even the loudest
  path stays >5x below the 94% rail line.
- DAC across the whole 8-key-cluster stress run: peak 10591, ZERO clipped samples.
=> The excitation-dependent caveat from the divergence sweep is substantially CLOSED: the loudest
   realistic input drives the effects to at most ~16% FS, nowhere near the rail, and the divergence
   sweep already covered every effect TYPE for self-excitation.

PANEL OBSERVATION (not a fix issue, flagged for the panel work): the CHORUS (SEG11 0x04) and MULTI
(SEG10 0x04) on/off toggles did NOT engage their SEND (ch19.r8 / ch29.r8 stayed 0) when pressed via a
scripted short press from the home screen -- yet the isolated per-effect-toggle capture (cap3) DID see
ch19.r8 change on a chorus press. So these two effect-toggle bits appear CONTEXT-DEPENDENT (consistent
with panel-completion-plan.md's note that some 0x2010 effect-button args are context-dependent). SOUND
DSP (SEG0F 0x08) and REVERB (SEG0F 0x04) engage reliably. Chorus/multi AUDIO output itself is already
validated via the divergence sweep's screen-navigation (R1B chorus 8 types, M1-M5 multi). This is a
panel-mapping loose end (relates to priority 2), NOT a return-routing bug -- the send=0 is upstream of
the mix fix.

## 2026-07-12 (later): the chorus/multi "toggle" finding CHARACTERIZED — context-dependent, likely faithful
Followed up last note's "chorus/multi toggles don't engage" flag with a proper characterization
(scratchpad/retcap/chartog*.lua, flagcheck.lua). Reading the SEND LOW BYTE (the actual level; high byte
is a separate field I initially misread):
- Fresh home screen: pressing CHORUS (SEG11 0x04) x3 -> send stays 0x0B00 (low 0 = off). No engage.
- After a SOUND DSP (SEG0F 0x08) toggle: CHORUS press -> 0x0B00->0x0B3C (low 0x3C = ON), press again ->
  off; MULTI press -> 0x0800->0x0650 (low 0x50 = ON). BOTH engage.
- After a REVERB toggle (only): CHORUS still does NOT engage; MULTI's high byte moves but low byte stays
  0 (still off). PART SELECT alone also does not enable CHORUS.
So chorus/multi on/off are REPRODUCIBLY CONTEXT-DEPENDENT: they engage in certain panel contexts
(observed: after a SOUND DSP interaction) but not from a cold home screen. REVERB and SOUND DSP toggles
engage standalone.
INTERPRETATION: the driver runs the REAL firmware, so the button->event->send chain is all firmware
logic -- this context-dependence is almost certainly FAITHFUL behavior (CHORUS/MULTI are GLOBAL-effect
buttons whose on/off the firmware gates on a per-part / effect-edit context; see panel-completion-plan's
note that the 0x2010 effect-button family is context-dependent), NOT an emulation bug. CORRECTION to the
prior note: it is wrong to call this a "panel loose end that doesn't engage" -- chorus/multi DO engage
and toggle correctly in the right context; the earlier test simply pressed them from a cold home screen.
Whether the panel HLE delivers the event in EVERY context is unverified (would need firmware event/LED
tracing), but there is no evidence of a delivery bug -- REVERB/SOUND DSP prove the HLE path works, and
the gating is on the firmware side. NOT changing anything (rule g: nothing is clearly broken). Deeper
resolution (the exact firmware gating condition) belongs to the per-part effect model, which is future
work and not required for the effects to be controllable.
