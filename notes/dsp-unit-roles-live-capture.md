# DSP unit roles — LIVE DspEffectSelect + upload capture (2026-07-20)

Queue item A3 (+A2). One instrumented session (`kn7000-emulator/a3.lua`, log
`a3_run.log`) with (1) a write tap on the DspEffectSelect param block
(`*(0x500A01E0)`, allocated at boot on the play-screen path — value here
0x5009EB58) logging every `{unit, type}` write at struct offset +8, and (2) an
index/data-port tap (0x98000000/0x9C000000) logging every PM/DM download
target, while driving the four effect GUIs from the panel. Screens
pixel-verified per snapshot. Follow-up session `a3b.lua` (log `a3b_run.log`)
drove the EQUALIZER screen and dumped unit-8's live DM bank per preset.

## ★ HEADLINE: the fixed-function unit map (LIVE FACT now, three labels flip)

| unit | PM slot | live-captured role | evidence |
|---|---|---|---|
| u0 | 0x8400 | **REVERB** (the hold-REVERB screen) | every reverb preset select → param-block type write {unit=0, 0x10/0x12/0x14/0x16} + full record upload to PM 0x8400 (+ scrub[u0], CALL-slot 0x8080 repatch) |
| u1 | 0x8500 | **MULTI** (captured state) | Multi "Cross Delay/Shallow" select → {unit=1, type=0x0C=rec15} + u1 slab writes + PM 0x850C/0x8529 patches (the delay-length immediates) |
| u2..u6 | 0x8600..0x8A00 | **per-part Sound-DSP / Digital-Effect insert pool** | SOUND DSP screen (part RIGHT1) → {unit=2, 0x03=rec08 Enhancer}; boot defaults u2=0x03 u3=0x06 u4=0x01 u5=0x29 u6=0x05; PANEL MEMORY recalls resync all of u2..u6 with per-part types (0x05/0x06/0x23/0x29/0x01/0x03…) |
| u7 | 0x8B00 | **MIC REVERB** | type 0x58 (rec58) written on the PMEM-recall resyncs; PM 0x8B1D/22/28/4B/51/56 word patches (rec58's per-preset immediates) |
| u8 | 0x8C00 | **EQUALIZER** (known) | boot init {unit=8, 0x4F}; live PM 0x8C00 read = rec34 wrapper (`CALL 0x831B`) |
| u9 | 0x8D00 | **CHORUS** (the hold-CHORUS screen) | Chorus1–4 → {unit=9, 0x52=rec49}; GM Chorus1–4 → {unit=9, 0x02=rec07}; uploads land at PM 0x8D00 / params 0xC2B5+ |

This corrects the whitelist role labels in `dsp-effect-catalog.md` §3, which
had unit0="Enhancer group", unit7="Chorus", unit9="Reverb" (inferences from
GUI-group guessing). The whitelist CONTENTS were always consistent with the
new labels: unit0 accepts 0x10–0x1F = the six comb+allpass reverb records
rec51–56; unit9 accepts 0x01/0x02/0x04/0x40/0x52 = rec06/07/09/70/49, all
modulated-delay choruses (`reverb-algorithm.md` §6 proved they can't be
reverbs); unit7 accepts 0x58–0x5B = rec58–61, the mic reverbs
(`final-batch-algorithms.md` already called them "unit 7").

Corollary for `kernel-architecture.md` §8: the "MULTI = u6" verdict is
**REFUTED**, and with it the bank↔serial-line 1:1 hypothesis. The three TG
send buses map to specific TDM **pairs**, not lines:

| TG send bus | unit | input pair | serial line |
|---|---|---|---|
| REVERB 0x80xx | u0 | 0xC362/3 | SPORT0-A pair 0 |
| CHORUS 0x81xx | u9 | 0xC376/7 | SPORT1-A pair 2 |
| MULTI 0x82xx | u1 | 0xC364/5 | SPORT0-A pair 1 |

u7's input pair 0xC370/1 (SPORT0-B) is therefore the MIC feed from the TG,
and u8's 0xC372/3 (SPORT1-A pair 0) the master-mix insert feed — consistent
with `dynamics-eq-exciter.md` §5.4's TG-closes-the-loop model. (Caveat: "u1 =
MULTI" is the captured machine state — boot default + PMEM A-2/A-5; if the
ALLOCATION screen or other registrations can move the multi to another insert
slot, that is not excluded. The u2 Sound-DSP capture is likewise per-part:
RIGHT1.)

## GUI name → type map (reverb page 1 pinned)

| GUI select | param-block write | record |
|---|---|---|
| Reverb Room1 | u0 type **0x10** | rec53 (small room) |
| Reverb Plate1 | u0 type **0x12** | rec54 (bright) |
| Reverb Concert1 | u0 type **0x14** | rec51 (reference) |
| Reverb Dark1 | u0 type **0x16** | rec55 (dark output) |
| Reverb Room2/Plate2/Concert2/Dark2 | *no type write* | same records — DM-bank-only variant (see below) |
| Chorus Chorus1–4 | u9 type **0x52** | rec49 |
| Chorus GM Chorus1–4 | u9 type **0x02** | rec07 |
| Multi Cross Delay Shallow* | u1 type **0x0C** | rec15 |
| Sound DSP Enhancer1–6 (RIGHT1) | u2 type **0x03** | rec08 |

The "…2" reverb variants and the numbered presets within a chorus/multi/DSP
family select the **same type**: their select bursts skip the PM record
upload and rewrite only the DM coefficient bank (plus a handful of state
words — u0state+0x02/+0x06/+0x0C for the reverb variants instead of the
+0x00 reset a record swap does). Every reverb preset writes the same
coefficient cells c011–c01e, c026, c028 + the single PM word 0x8463; the
per-preset early-tap immediates (0x8406/0x8410/0x841A/0x841D) only change on
a record swap. So "Room1 vs Room2" is a **pure DM voicing pair** on rec53 —
matching the PM-family structure the static diff predicted. (Reverb page 2 —
Stadium etc. — not driven this session; by the whitelist those must sit on
the remaining pairs 0x18/0x19 = rec56 and 0x1E/0x1F = rec52 plus the odd
aliases.)

## The select-burst anatomy (what one GUI preset press does)

Record swap (e.g. Room1 when rec5x wasn't loaded, GM Chorus1 after rec49):
```
DM 0x9C40+unit  (scrub countdown arm)
PM 0x8080+slotword (CALL target -> scrub stub, then back to 0x8400+unit*0x100)
DM 0x9800+unit*0x50 (state reset at +0)
DM 0xC000+unit*0x4D (params from +0)
PM 0x8400+unit*0x100 (the full record)
DM param singles (preset bank) + PM single-word patches (per-preset immediates)
PM 0x8080+slotword (re-patch)
```
Same-record preset: only the scrub arm + CALL flip + DM singles + the
per-preset PM words. This is the live confirmation of the kernel doc's §6
scrub-stub usage hypothesis (host parks the CALL on a scrub stub during
swaps): the CALL-slot word is written twice around every burst.

The param-block side: type lands at struct +8 (16-bit; +4 = a 16-bit flag
written 1 first, +0xA = 1) — the doc's "+6 dirty" is really +4, with +0xA a
second flag. Writes repeat once per affected part-row for the per-part
effects (unit9 chorus ×6, unit1 multi ×7, unit2 sound-dsp ×7) and once for
the global reverb. Struct +0 holds a pointer that flips between 0x5009EB58
and 0x5009F69C (= base+0xB44) on every select — a double-buffered
desired-state table pair.

Bonus capture: pressing a PANEL MEMORY (SOUND GROUP 2/5 = CPR_SEG6 0x40 /
CPR_SEG3 0x40 — hit accidentally while hunting PROGRAM MENUS) triggers a
**full effect re-sync**: every unit's scrub armed, CALL slots flipped, u0
reverb + u1 multi + u2..u6 inserts + u7 mic reverb + u9 chorus all
re-uploaded. A registration recall rebuilds the whole DSP state.

## A2 — the u8 EQ coefficient bank (flat vs presets): SETTLED

Live DM dumps of u8's c004..c019 (`a3b_run.log`, addresses 0xC26C..0xC281):

- **At flat (boot AND on the EQUALIZER screen), the host bank is an EXACT
  mirror bank**: every section's numerator = bit-exact sign-flipped
  denominator, all g = 1.0 → H(z) ≡ 1. The old "~15%-of-peak per-sample
  difference at flat" (effect-multi-unit-routing.md 2026-07-12) is therefore
  **not a coefficient effect** — that measurement artifact (frame
  misalignment in the feed test) should not be cited against a conditional
  u8 insert. `dynamics-eq-exciter.md` §5.4's PROVISIONAL is resolved the
  other way: GUI-flat IS 0 dB internally and IS transparent.
- The flat pole placement matches the GUI FC row **125/500/1k/2k/8k**
  (pixel-verified) = a1 1.97734/−0.982362, 1.945209/−0.965120,
  1.854196/−0.932108, S1 p 0.982347, S5 p 0.218894 — i.e. **rec23's template
  pole values, not rec34's ROM template** (484/969/1940): the host computes
  the bank from the on-screen FC/Q/GAIN and never uses rec34's DM template.
- Preset semantics (each preset rewrites FC+GAIN, i.e. poles AND zeros):
  - **Treble Boost**: S5 → p=0.0338, z=−0.8153, g=1.7815 → unity DC,
    ×2.51 (+8.0 dB) at Nyquist; S4 pole moved (FC edit), still mirror; S1
    slightly non-mirror.
  - **Make Up**: all five sections non-mirror (broad multi-band shaping,
    section gains ≈0.99–1.0).
  - **Radio**: S2/S3 g>1 (1.020/1.046 mid boost), S5 g=0.390 (−8 dB
    treble cut), S1 non-mirror.
  - **No Hi Hat**: only S4 rewritten: a1=1.35876, a2=−0.61382→(0xBF1D22F3
    =−0.61381), g=0.8613, non-mirror numerator → a mid-high notch.
  - **Flat (preset)**: a different exact-mirror bank (its own stored FCs) —
    identity again.
- The right-column soft key R1 acts as **ORIGINAL** (restores the pre-preset
  bank — dumps returned bit-identical to the boot bank); R2 = no bank
  change. Uploads land as per-word DM blocks at 0xC26C..0xC281 + scrub[u8]
  arm + CALL-slot 0x809D flips; **no DspEffectSelect type write** (type
  stays 0x4F; preset changes are DM-only refreshes).
- The bank updates even with `EQ : OFF` on screen — the on/off gate is not
  in the DSP coefficients (TG-side routing or a host flag elsewhere).

## Method gotchas (for reuse)

- The DspEffectSelect param block IS allocated on the play-screen boot path
  (old "stays -1" observations were the SD-menu-era state). Poll
  0x500A01E0 and tap `[base, base+0xB40)`.
- Host download order is: IIEP0 (idx 0x40, 2 halves) → … → DMAC0 commit
  (idx 0x1C = 0xA1 PM / 0x41 DM) → **payload after the commit** (park
  follows); a capture that opens the block at the commit and clears pending
  data at the park sees empty payloads — attach data seen after the commit
  to the just-opened block.
- CEP0 (idx 0x42) is written as two halves — high half 0 last; latch the low
  half only.
- Soft keys, authoritative (driver cpanel PORT_NAMEs): LCDL1..5 = CPL_SEG0
  0x02/0x08/0x20/0x01/0x04; LCDR1..5 = CPR_SEG5 0x10 / CPR_SEG5 0x20 /
  CPR_SEG7 0x01 / CPR_SEG6 0x01 / CPR_SEG5 0x01. PROGRAM MENUS = CPR_SEG0
  0x04. **CPR_SEG6 0x40 and CPR_SEG3 0x40 are PANEL MEMORY 2/5** — pressing
  them mid-navigation recalls a registration (and resyncs every DSP unit).
- EQUALIZER screen: PROGRAM MENUS → REVERB & EFFECT (LCDL2) → EQUALIZER
  (LCDR5).
