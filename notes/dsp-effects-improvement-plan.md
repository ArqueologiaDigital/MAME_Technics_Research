# Plan — make the effects DSP audibly process effects (2026-07-11)

Felipe: now that the control panel works and we can enter the sound menus and change effect
parameters, we should be able to understand how effects are controlled and HEAR them change.
Right now the sound barely changes -> the DSP is not yet handling effect processing properly.

This plan supersedes the PARKED note `f3-effect-loading.md` (which stalled on the SD-menu boot
state). The blocker it hit is now gone: we reach the play screen and the effect-control buttons
are mapped in the panel.

## 0. Where we are (grounded facts)

- The ADSP-21065L (IC306) boots, runs its kernel (rec04), and TG audio flows TG -> DSP -> speaker
  (F.3 done, commit f83a6a1). With no effect loaded the DSP runs the 7-word default PASSTHROUGH at
  PM 0x8400 (dry copy) -> off==on, which is why it "barely changes".
- The firmware DOES upload effect microprograms (~84x over a boot) via the ACTIVE path
  (maincpu 0x48404EDD -> host-port HAL 0x48404E8D -> index 0x98000000 / data 0x9C000000). But the
  effect it loads for the default Concert Grand is a SUBTLE EQ/Enhancer-like record, so the mix is
  only slightly different from dry (commit a988ecf sums the two sends to make the wet audible).
- The CLEAN selection path `DspEffectSelect(unit,type)` (thunk 0x48405815 -> 0x48415793 ->
  DspEffectAssign 0x4840562C) writes `dirty=1@+6 / type@+8` into `*(0x500A01E0)+unit*0x120`. It
  NEVER ran before because `*(0x500A01E0)` stayed 0xFFFFFFFF (param block unallocated) -- the boot
  landed on the SD menu, not the play screen. **That precondition has changed** (play screen now
  reachable + effect buttons mapped), so re-test whether this path now runs.
- 80 DSP download records at 0x486BCEC4..0x486CE68D: 1 kernel (rec04), 4 SDRAM tests, 72 effect
  microprograms (rec05-76), 3 LFO data. Reverb unit9 types 0x01/0x02/0x04 -> rec06/07/09; type0 =
  rec05 = passthrough. Catalog: notes/dsp-effect-catalog.md.
- Config to reproduce sound+DSP: CONFIG bit0 "Effects DSP host stub", bit1 "TG sound" (default ON),
  bit2 "TG sound play screen (no SD menu)". Panel effect buttons (bank A, now mapped): SOUND DSP =
  SEG0F 0x08, DIGITAL EFFECT = SEG10 0x08, SOUND DSP VARIATION = SEG0E 0x08, REVERB = SEG0F 0x04,
  CHORUS = SEG11 0x04, MULTI EFFECT = SEG10 0x04, MIC REVERB & EFFECT = SEG0E 0x04.

## 1. Hypotheses for "the sound barely changes" (to disprove in order)

H1. The firmware only ever selects the subtle default effect; strong effects (reverb/chorus) are
    never selected because the selection UI/path isn't being driven (or still isn't reached).
H2. Strong effects ARE uploaded when we select them via the panel, but the DSP doesn't run them
    (upload framing wrong / released too early / wrong PM address) -> still runs the passthrough.
H3. The effect runs and produces a wet send, but the driver's dry/wet MIX is wrong (mostly dry),
    so it's inaudible. (The bridge currently SUMS dry+wet; a real effect may need a different mix,
    or writes its output elsewhere than the passthrough's TX0+0xE=0xC350.)
H4. The effect's PARAMETERS (depth/time/type from the sound menus) aren't uploaded/applied, so even
    a loaded reverb sits at a null/zero-depth setting -> inaudible.

## 2. Phased plan

### Phase A — Instrument the effect pipeline (no code change, just visibility)
Goal: see exactly what the firmware uploads to the DSP and when, driven by the panel.
1. Add temporary logging (or a Lua write-tap on 0x9C000000 index/data + the dsp_data_w commits) that
   records, per upload: target PM/DM address, block size, and -- by matching the first few words to
   the catalog -- WHICH record (rec05-76). Retain tap handles in _G (aligned 4-byte units).
2. Boot to the play screen (CONFIG bit2), then via the panel: press DIGITAL EFFECT / REVERB / SOUND
   DSP, navigate the effect screen, and CHANGE the effect type + depth. Log the resulting uploads.
3. Deliverable: a timeline "panel action -> DSP record(s) uploaded to PM 0x8400 (+ DM params)".
   This immediately tells us H1 (are strong records ever selected?) and grounds everything else.
   Tools: kn7000_disassembly/dsp/ record fingerprints; interleave_evenodd.py + unidasm (offset =
   addr-0x48400000, dd first -- unidasm doesn't seek).

### Phase B — Is the clean DspEffectSelect path now reachable?
Goal: verify the precondition change.
1. Tap `*(0x500A01E0)` over a play-screen boot + an effect-screen visit. Does it get ALLOCATED
   (!= 0xFFFFFFFF) now? If yes, DspBootDefaultEffects (0x4840537D) / DspEffectSelect run -> the clean
   path is live and selecting a reverb writes unit9 type -> rec06/07/09 uploaded. If still -1, find
   what allocates it (DspAllocParamBlock 0x484057A9 caller) and what gates that.
2. If reachable: navigate to REVERB via the panel, pick a reverb type, and confirm (Phase A logging)
   that rec06/07/09 uploads to PM 0x8400. This likely resolves H1.

### Phase C — Verify the DSP RUNS the selected effect (H2)
Goal: confirm execution, not just upload.
1. With a reverb selected, tap the SHARC PC: is it executing the effect code at PM 0x8400+ (not just
   the 7-word passthrough)? Confirm the per-frame IRQ0 loop reaches the effect's compute.
2. Confirm the effect writes its output: the passthrough writes 2 words (dry) at TX0+0xE=0xC350; an
   effect writes 4 (dry + wet sends at 0xC350/1 + 0xC352/3). Re-derive the output offset per effect
   by tapping the TX0-region write address (a reverb may target a different slot).
3. If it doesn't run/produce wet: check the F.2 upload framing (block-open 0xA1/0x41, release on the
   final bare 0xA0), the PM address, and the SPORT/DMA buffer bases (TX0=0xC342/RX0=0xC362 derived).

### Phase D — Verify + fix the MIX and audio routing (H3)
Goal: the wet send must reach the DAC at an audible level.
1. In kn7000_dsp_bridge_device + dsp_audio_tick: confirm the driver reads BOTH sends (0xC350/1 dry,
   0xC352/3 wet) and mixes them. Check the mix law -- is the wet at full level or scaled down?
2. A/B capture (spectral, Goertzel + a decaying-tail test): press a note, RELEASE it, and look for a
   reverb TAIL after note-off. A sustained note only shows coloration; the tail is the proof. Compare
   effect-off (CONFIG bit1) vs on (bit0+bit1). Fix the mix/offset until the tail is clearly audible.

### Phase E — Effect PARAMETERS from the sound menus (H4)
Goal: changing reverb depth/type in the menu audibly changes the sound.
1. From Phase A, identify the parameter uploads (DM 0x9800/0xC000 param commits) that accompany a
   menu parameter change. Confirm the driver forwards them to the DSP (dsp_data_w handles DM commits).
2. Sweep a parameter (e.g., reverb depth min->max) via the panel and confirm the wet level/character
   changes in the captured audio. This closes the loop Felipe wants: "change a parameter -> hear it".

### Phase F — Consolidate + document
1. If the clean path (Phase B) works, prefer it (faithful). Do NOT hack-upload records from the
   driver as anything but a labeled last-resort demo.
2. Update: notes/f3-effect-loading.md (unpark), dsp-effect-catalog.md (per-record audible identity),
   the website sound page, and the blog. Commit + publish + re-verify.

## 3. First concrete step (next session)
Phase A + B together in one instrumented run: boot to the play screen with sound+DSP on, tap
0x9C000000 + `*(0x500A01E0)`, then drive the panel (SOUND DSP -> DIGITAL EFFECT -> pick REVERB, change
depth) and produce the "panel action -> DSP upload + param-block state" timeline. That single run
disproves or confirms H1/H2 and tells us whether the fix is selection (B), execution (C), mix (D),
or parameters (E). Everything downstream branches on it.

## 4. Guard-rails
- Faithful first: drive the firmware to select effects via the modeled panel; treat direct record
  uploads as demo-only and label them.
- Don't regress the clean dry passthrough (spectrally off==on within 1% today).
- Retain every Lua tap/notifier handle in _G; taps cover aligned 4-byte units.
- Never -video none; commit + publish after driver rebuilds.
