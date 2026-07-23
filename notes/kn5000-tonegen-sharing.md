# KN5000 tone-generator vs kn_tonegen_base — can the synthesis core be shared?

Author: autonomous RE pass, 2026-07-23. Question posed by Felipe: the KN5000
tone-generator (`kn5000_tonegen_device`, standalone, ~603 lines) is almost
certainly a PCM-wavetable variant of the same lineage as the shared
`kn_tonegen_base_device` (KN6000/KN6500/KN7000). So is the *synthesis* core
(EG, pitch, sample playback, pan, render loop) shareable, leaving only the
register front end per-model?

**VERDICT: (c) NO — no clean, behavior-preserving overlap to extract.** They
are variants of one PCM-wavetable *family*, but the two MAME devices model
synthesis at fundamentally different levels, with different pitch
representations, different (essentially absent vs full) envelope laws,
different sample sources, different sample rates, and different stereo models.
Every candidate "shared" piece would be a force-fit — precisely the failure
mode that cost this project a week on the KN7000 (plausible-but-wrong audio).
**No refactor performed.**

---

## 1. Chip facts (confirmed from code + comments)

| | KN5000 | KN6000/KN6500 | KN7000 |
|---|---|---|---|
| TG part | Toshiba **TC183C230002** (IC303) | NEC **D82398GD001** (IC213) | **2× D82398GD001** (IC201/205) |
| Voices | 64 | 64 | 128 (two chips) |
| Host interface | **register-indirect**: SubCPU latches a 16-bit reg *address* @0x100000, then data @0x100002 (P6.7 = CS strobe) | **plane-based** write primitive | same plane-based primitive |
| Firmware write primitive | (its own, register-indirect) | 0x4849465B | 0x4C036F7C — **byte-identical to KN6000** |

PROVEN (static RE, recorded in `kn_tonegen.h`): the KN6000 and KN7000 write
primitives are byte-identical, which is *why* those two share a base. That
evidence organizes `kn_tonegen_base` around the plane-based write primitive.

MEASURED (from `kn5000_tonegen.{cpp,h}`): the KN5000 uses a different part
number **and** a different host interface (register-indirect: group/bank/
channel address decode, 32 regs/voice as 8 groups × 4 banks). There is **no
firmware-write-primitive evidence** linking it to the plane-based base — the
one thing that justified the KN6000/KN7000 share does not exist here.

---

## 2. Structural diff of the synthesis core

The base's `sound_stream_update` + `eg_tau` + the caller-resolved pitch is one
synthesis philosophy; the KN5000's is a different one. Item by item:

| Aspect | kn_tonegen_base (KN6000/7000) | kn5000_tonegen | Same? |
|---|---|---|---|
| **Sample source** | **Sine oscillator** (`sin(m_phase)`), or *optional* synthetic donor wave pack (`m_wentries`, "KN7WVSY2"). Does **not** read the real wave ROMs. | **Real PCM wavetable** stepped through the actual waveform ROM (`m_waveform_data`, IC304-307), 16.16 fixed-point, linear interp. | **NO** |
| **Pitch representation** | `m_freq[v]` in **Hz (double)**, computed by the **caller** from `note_x256` (musical 1/256-semitone) resolved from the firmware library voice record. | `pitch_step` **integer 16.16**, derived *inside* the device from a hardware **semitone-ratio register** (0x8000=1.0×) + an **octave register** (`reg[8]`, note<<8). Caller supplies nothing. | **NO** |
| **Envelope** | Full **4-stage rate\|level EG** (ATTACK→DCY1→DCY2→RELEASE), exponential coefficients via `eg_tau(rate)=13·2^(−rate/20)`, resolved from firmware r0/r1/r2 pairs; float `m_env`. | **No EG.** Only a linear `release_counter` (2400 smp ≈ 50 ms fade) + a `hold_counter` timer for status read-back. Attack/decay/sustain do not exist. | **NO** |
| **Sample rate** | 44100 | 48000 | NO |
| **Stereo / pan** | **None** — single mono `acc`, duplicated to L and R. | **Real stereo** `volume_l`/`volume_r` from group-8 pan registers (0x3C center). | **NO** |
| **Voice lifecycle** | gate + stage machine; gate-follow key coupling (`key_break`), managed key-up burst, steal-mute. | `active`/`key_on` + hold/release counters; loop-while-held; deactivate on wave end. | **NO** |
| **Per-voice state** | phase, freq(Hz), env, 4-stage EG coeffs, aux/mode, bus-send register file, wave-pack sel | regs[32], wave_offset/start/length(16.16), pitch_step, vol L/R, release/hold counters | **NO** (disjoint) |
| **Render loop / accumulate / clamp** | per-voice loop, accumulate, clamp | per-voice loop, accumulate, clamp | Generic only |

The only overlap is the last row — "loop over voices, accumulate, clamp,
write stream" — which is generic to *any* PCM mixer and is not a shared
*algorithm*. Everything with actual DSP semantics diverges.

### Fraction breakdown of `kn5000_tonegen.cpp` (~603 lines)

- **(a) chip-specific front end** (register-indirect decode, group_map,
  global-reg decode, key on/off dispatch, keybed FIFO, wave-ROM index/
  addressing): ≈ 55% (addr/data_w/r 125-229, resolve_waveform 348-412,
  keybed 236-256).
- **(b) synthesis that *duplicates* the base:** ≈ **0%.** None of the base's
  EG law, note_x256→Hz pitch, sine/donor playback, or gate machine is
  duplicated — the KN5000 does none of those things.
- **(c) genuinely KN5000-unique synthesis** (integer pitch_step from the
  hardware semitone table + octave reg, real-PCM 16.16 wavetable playback
  with interp/loop, hold+linear-release timers, stereo pan): ≈ 45%.

PREDICT-THEN-CHECK: the task hypothesized 603 vs 190 lines implies the KN5000
"duplicates synthesis the base already has." **Prediction missed.** The extra
lines are *not* duplicated synthesis — they are (i) a heavier register-indirect
front end than the plane decode, and (ii) a *real* sample-playback engine that
the base simply does not contain. The base is *smaller* because it is a
sine/donor **approximation**; the KN5000 is larger because it actually plays
the ROM PCM.

---

## 3. Why sharing would be a force-fit (not a clean extraction)

1. **Opposite fidelity levels.** To "share" a render core you must pick one
   sample source. The base plays sine/donor PCM; the KN5000 plays real ROM
   PCM. Neither can adopt the other without either regressing the KN5000 to
   sine (losing real audio) or rewriting the base to read wave ROMs it has no
   addressing for. That is a rewrite, not a share.

2. **Incompatible pitch models.** The base's pitch is Hz resolved by the
   *caller* from a firmware library record; the KN5000's pitch is an integer
   16.16 step the device derives itself from a hardware semitone-ratio
   register + octave register. The KN5000 "sings in tune" *because* of that
   self-contained integer derivation. Routing it through the base's
   `note_x256`→Hz path would change the numbers that currently produce
   verified-correct pitch — the exact plausible-but-wrong-audio risk.

3. **Envelope mismatch.** The base's 4-stage exponential EG has no counterpart
   in the KN5000 (which has only a linear release + hold timer). Imposing the
   base EG on the KN5000 would audibly change every note's amplitude contour.

4. **No firmware evidence to anchor a KN5000 share.** The KN6000/KN7000 share
   is justified by a *byte-identical write primitive*. No such match exists for
   the KN5000 (different part, different register-indirect primitive). Sharing
   here would be justified by aesthetics ("both are PCM wavetables"), not by
   the evidence standard this base was built to.

---

## 4. What (if anything) *could* be shared later — and why not now

The only honest future candidate is a **generic linear-interpolation PCM
voice-playback helper** (16.16 stepping + tail loop + interp), which both the
KN5000 render loop and the base's *donor-wave-pack* branch resemble in spirit.
But:
- they use different position types (base: `double m_wpos`; KN5000: `uint32_t`
  16.16),
- different loop metadata (base: build-time `lstart/llen` from the pack;
  KN5000: ROM index-table lengths),
- different rate inputs (Hz/root vs 16.16 step).

Extracting that would share ~15-20 mechanical lines while adding an adapter on
each side to convert types — a net negative in clarity, and it touches the
KN5000's verified-in-tune playback for no behavioral gain. Not worth it. If
the base is ever upgraded from sine-HLE to real wave-ROM playback (a much
larger project), revisit then; at that point a shared PCM engine *would* have
real evidence and real payoff.

---

## 5. Deliverable summary

- **Chip comparison:** different parts (TC183C230002 vs D82398GD001),
  different host interfaces (register-indirect vs plane-based), no shared write
  primitive.
- **Synthesis shared vs divergent:** ~0% genuinely shared *algorithms*; the
  render/accumulate/clamp skeleton is generic-only. Pitch, envelope, sample
  source, sample rate, and stereo model all diverge.
- **Verdict:** **(c) NO clean shared core.** Variants of one PCM-wavetable
  lineage, but the two MAME devices model synthesis so differently (real-ROM
  sample playback + integer HW pitch + no EG, vs sine/donor HLE + Hz pitch +
  full firmware EG) that any share is a force-fit.
- **Refactored?** **No.** Per the task's own guardrail, a well-evidenced NO is
  a valid deliverable, and force-fitting risks regressing the KN5000's
  verified-in-tune audio. No src/ changed → no build/-validate/audio-A/B
  needed (the A/B gate exists only to protect a refactor; there is none).

Labels: chip/interface facts = MEASURED (from source) / PROVEN-BY-RE (KN6000
primitive match, per kn_tonegen.h). Synthesis divergence = MEASURED (direct
source comparison). "Same lineage" = SPECULATIVE (plausible from PCM-wavetable
family, unproven for the KN5000 part).
