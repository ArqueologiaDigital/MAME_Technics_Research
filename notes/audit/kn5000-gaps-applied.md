# KN5000 IC303 — APPLYING THE CALIBRATED GAPS (CAL-1 / LIFE-1 / LIFE-2 / OUT-1 / OUT-2 / headroom)

What was actually implemented in `src/mame/matsushita/kn5000_tonegen.{cpp,h}` from the three design
notes of this pass — `kn5000-eg-calibration.md` (48e304c), `kn5000-lifecycle-design.md` (75f6e1e) and
`kn5000-output-design.md` (7197732) — what was deliberately **not**, and the full measurement table.

Every law below is either **DERIVED** (traceable to a ROM table or an instruction sequence, cited by
asm line + label + ROM offset) or explicitly flagged **CALIBRATED**. There are exactly **three**
calibrated numbers in the whole envelope/output path and each one is named in the source with the
experiment that would replace it.

---

## 0. SUMMARY

| gap | status | one line |
|---|---|---|
| **CAL-1 (a)** level → gain | **SHIPPED, DERIVED** | `gain = 2^((L−255)/16)`, from sub-ROM table `0x010764`. Replaces the fitted `2^((L−231)/10)`. |
| **CAL-1 (b)** rate → time | **SHIPPED**, structure derived, 2 constants CALIBRATED | rate 0 = HOLD and 0x7F = fastest are DERIVED; the seconds are not in the ROM. |
| **CAL-1** run the EG | **SHIPPED** | three segments from `+0x800/+0x840/+0x880`, per output sample. A held piano now decays like a piano. |
| **LIFE-1** honest `status_r` | **SHIPPED** | 152 gates / **64** frees → 154 gates / **154** frees. Stuck voices 64 → **0**. |
| **LIFE-2** deterministic note-off | **NOT SHIPPED — there is none** | disproved four ways; the timing heuristic is KEPT because deleting it would leave released notes ringing. |
| **OUT-1** stereo pan | **SHIPPED** | `+0x180` bits[6:0], balance law. L and R now genuinely differ. |
| **OUT-2** effect sends | **CORRECTLY A NO-OP** | they are EG stage words; effects are on the DSP bus at `0x130000`. Nothing written. |
| **headroom** | **SHIPPED** | unconditional ×0.70 trim removed, knee raised to 0.85. Battery peak 32746 → 23324. |
| R5 (`0x7E00` = hard stop) | **NOT SHIPPED** | would *add* a click while the release heuristic still exists. Reason measured, see §4. |
| R7/R8 (delete heuristic + counters) | **NOT SHIPPED** | see LIFE-2. |
| hand-off word `0xF0xx` mute | **KEPT** | still the wrong reading; removing it still regresses. Now *unblocked* — see §6. |

**No-regression battery: 7/7 before, 7/7 after.** `-validate kn5000` clean. Boots to the PMEM play
screen (`RIGHT1 = Piano`).

---

## 1. CAL-1 (a) — LEVEL byte → LINEAR GAIN. **DERIVED.**

```c
gain(L) = 2 ^ ((L - 255) / 16)          // 0.376287 dB per level unit
```

Tabulated at 1/16-count resolution in `device_start()` (4096 entries) because it is evaluated once
per voice per output sample; `eg_level_to_gain()` indexes it.

**Where it comes from.** `LABEL_0232C7` (v142 asm L15195-15214) builds chip register `+0x080` through
sub-ROM table `0x010764` (file offset `0x1864`), and that table is bit-exactly
`T[i] = round(128·log2(2^(i>>4)·(1+(i&15)/16)))` for **256 of 256** entries — a 4-bit-exponent /
4-bit-mantissa float. So an 8-bit level code is a log amplitude at exactly **16 counts per octave**.
Corroborated three ways: the 9-position cap table `0x011ADF` steps exactly 3.010 dB; the 8-bit target
(16/oct), the 12-bit `+0x080` (256/oct) and the 13-bit level readback (512/oct, `AND 3FFFh; SRL 5`
asm L13341-13342) span the same 96 dB; the voice manager's `0x80` threshold is exactly 8 octaves.

**What it replaced, and why that mattered.** The shipped fit `2^((L−231)/10)` was wrong in *both*
constants: K = 10 is 1.6× too steep (153.5 dB implied across a 96 dB register) and REF = 231
saturated the top 25 codes, so 26 of the 127 velocities rendered identically. The consequence that
blocked this whole workflow: the Piano's own DECAY2 target `0x40` read **−100.5 dB** under the fit
and reads **−71.9 dB** under the derived law. "Running the EG kills held notes" was a property of the
constants, not of the EG.

`gain(0)` is forced to exactly 0. That is the **CAL-1 contract** the lifecycle design states: the
firmware frees a channel only when the chip reports silence, so a gain law that never reaches zero
would deadlock a 64-voice instrument. (−95.95 dB vs −∞ is inaudible either way.)

### The `+0x800` bit-7 contradiction — how it is handled, and what is still open

The lifecycle note flagged a contradiction it deliberately did not resolve: the three *silencing*
contexts (`0xFF80` pre-reuse, `0xA280` panic, `0x8B80` release) carry **three different levels**, and
under "higher = louder" the pre-reuse `0xFF` is the *loudest* value in the register.

The resolution adopted here is **not** a re-decode of the level byte — it is the low byte, and it is
DERIVED. All three of those words carry rate `0`/bit 7, and **rate 0 = HOLD**, so *none of them moves
the envelope at all*:

* `+0x840 = 0xFF00` → target 255, rate 0 → the EG does not move. No blip.
* `+0x800 = 0xFF80` / `0xA280` / `0x8B80` → bit 7 set. Bit 7's meaning is **NOT decoded**; it cleanly
  separates "note-on programmed the EG" (every rate-table value is ≤ 127, and the attack literal is
  `OR BC,007fh` asm L19399) from "software is commanding a level" (`LABEL_026769` → `LABEL_02682F`,
  asm L20831-20838, `SLA 8,WA; SET 7,WA`). A bit-7 word is therefore **ignored as a segment program**.

That conservative treatment is load-bearing, not timid: at key-up the firmware ships `0x8B80` =
level 139 = **−43.65 dB**, which is *louder* than the piano's own sustain level `0x48` = −68.86 dB.
Honouring it as a segment target would make a released note get **louder** — precisely the defect
reported from real-hardware comparison on 2026-07-25. The same rule disposes of audit GAP 7 (the
full-scale blip 386 µs before every re-gate) with no special case at all.

Also verified while tracing this: `LABEL_02682F` stages to `0x0451F8`/`0x0451FA` = staging `[+0x2c]`
/`[+0x2e]`, and `LABEL_02D620` (asm L30130) ships `[+0x2e]` to **`+0x840` *and* `+0x880`** — it does
not touch `+0x800` at all. `LABEL_02D436` (asm L29936) ships `[+0x2c]→+0x800`, `[+0x2e]→+0x840`,
`[+0x30]→+0x900`, `[+0x32]→+0x940`, `[+0x34]→+0x9C0`, `[+0x36]→+0xA00`: three `(seg0,seg1)` pairs for
three EGs, confirming the output note's §2 grouping argument from the writer side.

---

## 2. CAL-1 (b) — RATE byte → SEGMENT SPEED. Structure DERIVED, 2 constants CALIBRATED.

```c
rate == 0 -> HOLD                                             [DERIVED]
speed(rate) = 255 / (T127 · 2^((127-rate)/D))  level units/s  [FORM: INFERRED]
    D    = 4.0      CALIBRATED (DERIVED bound: 3.8 .. 7.7 counts per doubling)
    T127 = 3.4 ms   CALIBRATED
```

DERIVED parts, all in `eg_rate_to_step()`'s comment with citations: `0x7F` is hard-coded as the
attack (asm L19399) and is the neutral default `0xFF7F` (asm L21915); `0` is *forbidden* where the
envelope must move (DECAY1 is `clamp(·,4,127)`, asm L19424-19427 and L19304-19307) and *is the
default* where it must not (DECAY2 is `clamp(·,0,127)`, asm L19309-19312, and is omitted entirely
when the descriptor's has-DECAY2 bit is clear, asm L19463-19467); a **linear** rate→speed law is
FALSIFIED by the Piano/Drum register pair (it would make the piano's whole decay 13.7× shorter than
the drum's).

NOT derivable, with a positive argument: the firmware never computes an envelope time — it polls the
chip (`LABEL_02219F` asm L13334-13348) — and an exhaustive scan of every near-geometric u16 run in
the sub ROM found 11 exponential tables, all LFO/pitch, none rate-indexed. IC303 is undumped.

**The experiment that replaces both** (~20 min on the real KN5000, written into the source comment):
time a held PIANO note's attack peak → −40 dB; repeat on a patch with a strongly different DECAY1
rate (STRINGS / ORGAN), reading the rate back from `+0x840`'s low byte; then
`D = (r2−r1)/log2(t1·ΔL2/(t2·ΔL1))`, and `T127` from either point. A third rate over-determines it
and validates the exponential *form* itself.

### Live confirmation of the law as implemented

With `D = 4`, the Piano's DECAY1 (rate `0x4C` = 76) predicts **11.01 level units/s = 4.14 dB/s**.
MEASURED on a 12 s held C4, in the window where the sample's own contribution is flat (t = 22 → 30 s):
predicted **33.1 dB**, measured **33.8 dB**. **PREDICT-THEN-CHECK: HIT.**

---

## 3. LIFE-1 — the honest `status_r`. **SHIPPED, and it is the headline result.**

`status_r()` now implements **R0** (decode the latch instead of masking it to 2 bits: `0x0000..0x0003`
= bank bitmap, `0x0180+ch` = that voice's envelope level `<<5`, anything else = 0), **R1** (the bit is
the `eg_running` LATCH — set only by `0x81xx`, cleared only by `0x7E00` or by genuine silence) and
**R2s** (a voice reports silent only after its own rendered contribution has stayed below **0.5 LSB**
of the 16-bit output continuously for one full bank-poll period, **98.33 ms** = 4720 samples).

**A/B, same rhythm, same 20 s, same nvram — `notes/audit/data-gaps/life.lua`:**

| | before | after |
|---|---|---|
| gates (`0x81xx`) | 152 | 154 |
| frees (`0x7E00`) | **64** | **154** |
| voices simultaneously gated-and-never-freed, peak | **64 (pinned)** | **3** |
| still live after STOP | **64** | **0** |
| live samples over time | 13 → 23 → 27 → 37 → 45 → 54 → **64 → 64 → 64** | 0 → 0 → 0 → 1 → 0 → 1 → 1 → 0 → 1 |

The lifecycle note's MEASURED never-freed case is fixed too: `ch00` gated at 5.859349 was previously
never freed and re-gated at 12.006012 for a different note; it is now freed at 6.030509.

### The safety invariant, measured directly

A 12.0-second held C4 (`hold12.lua`), logging every `+0x000` gate/free:

```
PRESS 20.003    20.005831 ch00 8100    20.006313 ch01 8100
        ... 12.0 s, ZERO 0x7E00 for either channel ...
RELEASE 32.014  32.142419 ch00 7E00    32.142481 ch01 7E00      (128 ms after key-up)
```

**A held key is structurally unreclaimable**, exactly as the design's Corollary A predicted: while the
key is down the EG sits above the floor, the contribution never falls below 0.5 LSB, the interlock
never arms, the bit never drops. Its audio contour over those 12 s:

```
 t=+0.1 s  −20.9 dBFS   t=+2 s  −37.0    t=+6 s  −53.4    t=+10 s  −70.8
 t=+0.5 s  −27.0        t=+4 s  −45.1    t=+8 s  −62.0    t=+11.9 s −81.9
```

---

## 4. What was NOT shipped, and why

**LIFE-2 — the deterministic note-off. THERE IS NONE.** The timing heuristic (a group9/bank0 write
> 1 ms after the gate) is **kept**, and the source now carries the disproof of every candidate
replacement: `LABEL_02CD71` (asm L29178) is a general "levels changed" service with ten call sites,
and `Voice_CC_Portamento` (L25150) → `LABEL_02CCD3` (L29116) → `Voice_ParamInit` (L29344) →
`LABEL_02CD71` → `LABEL_02D436` re-emits the whole six-write "release" burst on every sounding
channel of a part **with the keys still down**; `Voice_ParamInit` is simultaneously the note-off
service (asm L29469); a note-off may produce **no bus write at all** for up to ~3.1 s (asm
L29372-L29386); and a note-off may arrive as a hard mute `0xFF00/0xFF80` byte-identical to the
note-**on** pre-mute (L28663/L28677 vs L28560/L28578).

The design would have deleted the heuristic on the argument that the chip's own release ramp ends the
note. **That ramp is exactly what is not decoded**: the release word's low byte is `0x80`, i.e. rate
0 = HOLD, so an EG driven straight from the register stream freezes a released note at its sustain
level and never ends it. Deleting the heuristic would therefore be a regression, not a fix.

**R5 (`0x7E00` as a hard stop).** Not adopted, for a measured reason rather than caution: with the
heuristic still present the `0x7E00` for a key-bed voice arrives ~41 ms after the fade has already
started, when the voice is at ~18 % amplitude — a hard stop there would **add** a click the current
guarded path does not have. What `0x7E00` *does* now do is drop the `eg_running` latch immediately,
which is what the firmware needs in order to re-gate the channel.

**R7/R8 (delete `process_key_off`, `hold_counter`, `release_counter`).** Subsumed by the above.

**OUT-2 (effect sends).** Correctly a no-op, re-verified from the writer side (§1). Nothing written.
The `+0x8C0`/`+0x900..+0x9C0`/`+0xA00`/`+0xA40` words *are* two further envelope generators, and
those are still unmodelled — that is a real remaining gap, but it is an EG gap, not a send gap.

---

## 5. OUT-1 (pan) and headroom

`update_voice_params()` no longer computes loudness at all — `volume_l`/`volume_r` are now **pure pan
gains** and the EG supplies amplitude. Pan = `regs[6] & 0x7F` (`+0x180`), balance law with
`gL(0x40) = gR(0x40) = 1.0` and `max(g) = 1.0`. `voice_t::reset()` seeds `regs[6] = 0x0040`, the
firmware's own default (asm L21912) — without it an unwritten voice would render hard left.

LIVE confirmation, default Piano C4, all three piano variants: `+0x180 = 0x0000` on oscillator 0 and
`0x007F` on oscillator 1 — the two layers are hard-panned to opposite extremes, and the render now
shows it (chord section, ch1 vs ch2 rms: **7392 / 7392 before → 2332 / 1403 after**).

Headroom: the unconditional `×0.70` trim is gone (the sum now passes through **exactly unchanged**
below the knee, which it never did before) and the knee is raised to `K = 0.85` + tanh. The knee is
CALIBRATED and bounded by the data. No voice-count normalisation, no auto-gain — there is no hardware
mechanism for either.

**The one remaining free parameter, deliberately left at unity.** The chain from level code to DAC
also passes through `+0x080` and `+0x0C0`, neither of which the HLE applies, so a single global
make-up scalar is undetermined. It is **not invented here.** Consequence, stated plainly: the
instrument is **≈ 11 dB quieter** than the previous build — **−8.58 dB** from correcting the level
law, **−6 dB** from honestly hard-panning the piano's two layers into separate channels, **+3.1 dB**
from removing the trim. That is the right direction for the WATCH item (the previous build peaked at
**32746/32767 = 99.9 % FS** on this very battery; it now peaks at **23324 = 71 %**, and the limiter
is never engaged), and it is recoverable in one line by whoever calibrates the scalar against real
hardware.

---

## 6. Still wrong, and now UNBLOCKED

The hand-off word `0xF0xx`/`0xFExx` is still read as a linear amplitude (`data & 0x1FF`), which mutes
every rhythm/accompaniment voice (bare `0xF000` → 0). It is **kept**, and the reason it was kept has
now *changed*: the old justification ("a handed-off voice has no remaining path to end") is
**falsified** — §3 shows the firmware frees them. The reason it is still kept is narrower and
measured: with the EG running, a rhythm patch programs `SUST1 == SUST2` with DECAY1 at the clamp
floor 4 (197/197 note-ons), i.e. a **flat gate that never falls**, and the HLE loops the sample while
the voice is gated — so un-muting alone restores the saturated drone. Closing it needs two more
pieces: the decode of the `0xF0xx` low bits (audit GAP 8 — the current mask is one bit too wide), and
a rule for when a non-looping one-shot has *ended*. Both are out of scope for this pass and neither
is guessed at here. Accompaniment rms 7.50 → 0.77 across the change (inaudible before and after).

---

## 7. FULL NO-REGRESSION TABLE

Same MIDI battery (`reg.mid`, `-midiin2`, internal key bed), same isolated nvram, pre-change binary
vs final binary.

| MUST-NOT-REGRESS check | before | after | verdict |
|---|---|---|---|
| sample selection: `+0x040` per oscillator, 3 piano variants | `7007` / `7017` | **identical** | PASS (code path untouched) |
| chromatic C4..B4 distinct + monotonic | 12/12, worst 11.2 ¢ | 12/12, worst 13.7 ¢ | PASS (see note below) |
| exact octave C4 → C5 | 2.0000 (+0.0 ¢) | **2.0000 (+0.0 ¢)** | PASS |
| chord C-E-G, all three fundamentals | 260.7 / 328.1 / 389.7 Hz | **260.7 / 328.1 / 389.7 Hz** | PASS |
| chord not clipped | 32075 (97.9 % FS) | **15050 (45.9 % FS)** | PASS, improved |
| velocity DIRECTION (soft 30 vs hard 120) | 7.53× (+17.5 dB) | **7.45× (+17.4 dB)** | PASS |
| release decays monotonically, no rise | pass | **pass** | PASS |
| release smoothness (max \|Δsample\| at key-up) | 2023 | **97** | improved 26 dB |
| held note still sounding after 2.5 s | rms 2988 | rms 275 | PASS (and now *decays*, §2) |
| held note not reclaimed — 12 s hold | n/a | **0 frees in 12.0 s** | PASS |
| TVF: Piano / Bright / Mellow differ | `2466`/`2470`/`2450` | **identical registers** | PASS |
| TVF: rendered spectral centroid | — | 1650 / 1722 / 1457 Hz | PASS (Mellow < Piano < Bright) |
| stereo: L vs R differ | identical | **2332 / 1403 rms** | new |
| whole-battery peak | 32746 / 32767 | **23324 / 32767** | improved |
| `-validate kn5000` | clean | **clean** | PASS |
| boots to the PMEM play screen | yes | **yes** (`RIGHT1 = Piano`) | PASS |
| **battery score** | **7/7** | **7/7** | |

*Chromatic note (not a pitch regression):* `reg.py`'s `lines()` returns raw FFT bin centres with no
parabolic refinement, and at N = 16384 / 48 kHz one bin is 2.93 Hz = **11.6 cents at A4**. The two
readings that moved (A4 439.45 → 436.52, A#4 465.82 → 462.89) are **adjacent bins** — 150·df → 149·df
and 159·df → 158·df — i.e. the same partial picked one bin lower because the EG changed the spectral
balance inside the analysis window. The octave ratio, measured on the same tool, is unchanged at
exactly 2.0000.

---

## 8. PREDICT-THEN-CHECK LOG (misses included)

| # | prediction | outcome |
|---|---|---|
| 1 | held-piano decay of 33.1 dB over t = 22→30 s under `D = 4` | **HIT** — measured 33.8 dB |
| 2 | net level change ≈ −11.5 dB (−8.58 law, −6 pan, +3.1 trim) | **HIT** — measured −11.0 dB (rms 6227 → 1750) |
| 3 | a held key can never be reclaimed (design Corollary A) | **HIT** — 0 frees in a 12.0 s hold |
| 4 | honest silence reporting refills the free list | **HIT** — 64/152 → 154/154 frees, stuck voices 64 → 0 |
| 5 | pan makes L and R differ | **HIT** — 7392/7392 → 2332/1403 |
| 6 | removing the `0xFF80` pre-mute blip is audible in the A/B | **MISS (not reproduced).** The 0.4 ms pre-gate window measures peak **0 in both builds** — in this capture the channel was idle before the gate, so there was nothing for the blip to amplify. The *mechanism* is removed by construction (rate 0 = HOLD, bit 7 ignored), but its removal is **not** measured. Reported rather than claimed. |
| 7 | the release would be smoother | **HIT, larger than expected** — max \|Δ\| 2023 → 97 (−26 dB, of which only −11 dB is the level change) |
| 8 | with LIFE-1 fixed, the hand-off mute could be removed | **MISS** — §6: rhythm patches program a flat gate that never falls, so un-muting still drones. Kept. |

---

## 9. REPRODUCTION

```bash
S=<scratchpad>/gaps
# no-regression battery (needs tvf/reg.mid + the pre-init nvram copy)
$S/battery.sh v1 && python3 tvf/reg.py $S/v1/reg.wav
# LIFE-1 A/B
$S/runlua.sh        life_v1     $S/life.lua   44
$S/runlua_before.sh life_before $S/life.lua   44
# held-note safety
$S/runlua.sh hold_v1 $S/hold12.lua 35
# TVF / pan / wave-select register capture
ABKEYS="L1,L2,L1p2" ABNOTES="C4:KEY2:1" T_BASE=22 SLOT=10 HOLD=1.6  $S/ab.sh tvf_v1 ./kn7000
```

Probe scripts are archived in `notes/audit/data-gaps/`.
