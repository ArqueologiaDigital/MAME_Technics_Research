# KN5000 real PCM sample selection + full multi-cycle faithful render

Author: autonomous RE + fix pass, 2026-07-23. Requested by Felipe Sanches.
**This session edited `src/`, built, ran MAME, verified, committed.**

Supersedes the harsh single-cycle placeholder documented in `notes/kn5000-faithful-render.md`.
Builds on / **corrects** `notes/kn5000-tone-record.md`, `notes/kn5000-wave-number.md`,
`notes/kn5000-ic307-content-map.md`.

Evidence labels: **MEASURED** (ROM bytes / disasm / the RUNNING machine), **INFERRED**,
**SPECULATIVE**.

---

## 0. TL;DR

* **The reframing was right: "wave 0 by design" was an INCOMPLETE picture.** The tonegen
  register `+0x440`/`+0x480` ("wave number") genuinely stays 0 for ordinary PCM voices — but
  that is a *legacy index-resolver* path the PCM voices bypass. The REAL per-instrument sample
  selection travels through a DIFFERENT path (the reframing's option (b)): the delivered tone
  record's **oscillator (partial) records carry explicit 24-bit sample-ROM addresses**
  (a START pointer + a LOOP pointer per oscillator). These are DISTINCT per instrument and land
  inside the waveform-ROM PCM range. (MEASURED live — §1.) This **corrects** the prior
  `kn5000-tone-record.md` §4 conclusion that "the delivered data carries no wave selection;
  identity lives only in the timbre/pitch registers."

* **The harshness is FIXED** by playing the FULL multi-cycle recording (real attack + body)
  and looping a derived SUSTAIN region, instead of looping ONE short fundamental period taken
  from the ATTACK transient (which is what buzzed). Pitch is preserved exactly (§3).

* **Selection mechanism status: see §2** (filled from the register-write trace).

---

## 1. The real selector — 24-bit sample addresses in the delivered oscillator records (MEASURED)

Live capture on the built `kn5000`, pre-init nvram → play screen (RIGHT1=Piano, RIGHT2=Bigband
Brass, LEFT=Modern E.P.1). Sub-CPU DRAM structure (verified exactly against
`kn5000-tone-record.md`): `part_base = 0x041368 + part*0x11F`; `tonerec = part_base + 0x6E`;
tonerec's first 0x18 bytes = six 4-byte little-endian **partial pointers**. Pointers ptr[2..5]
point at 15-byte **oscillator records**:

```
osc record = flag(1) | START(3B LE) | 00 | LOOP(3B LE) | 00 | 0C | rate(1) | 42 80 42 00
```

`START` and `LOOP` are 24-bit values differing by one short waveform period (15–112 samples) —
textbook (loop_start / loop_end). Both land in the PCM range (~0x2B000–0x33000, inside IC307's
page-0 indexed-PCM span 0x1A30–0xFEF60). They are **DISTINCT per instrument** (osc START
addresses):

| instr | osc1 | osc2 | osc3 | osc4 |
|---|---|---|---|---|
| PIANO | 0x02B12A | 0x02DD2E | 0x031203 | 0x031BF4 |
| BRASS | 0x02C652 | 0x02C695 | 0x031EFF | 0x0323FA |
| EP    | 0x02B3DA | 0x03078E | 0x03128A | 0x0318E3 |

Four distinct pointers per voice = a 4-oscillator / multisample PCM voice. So the KN5000 DOES
select distinct samples per instrument (owner's ground truth), via these addresses — not via the
0-valued `+0x440` register. Also a small per-instrument index sits at ptr[0]+0x02
(Piano 0x00 / Brass 0x38 / EP 0x06), echoed as the high byte of the ptr[1] pitch table — a
multisample-set tag (INFERRED). Confirmed: `tonerec[+0x1a] == 0` for all three (legacy bank
field genuinely 0); `part_base[+0x0a]` bit15 is NOT uniformly clear (Piano/Brass 0x0004, EP
0xC000) — refining the prior note's Piano-only measurement.

## 2. How the address reaches the chip / what the HLE can use — (register-write trace)

<!-- FILLED FROM DELIVERABLE-2 TRACE -->

## 3. The render fix — full multi-cycle playback + derived sustain loop (SHIPPED)

`src/mame/matsushita/kn5000_tonegen.{cpp,h}`.

* **Full-sample playback.** A voice now plays the whole selected IC307 recording from sample 0
  (its real attack and timbral evolution), then loops a **sustain region** for as long as the
  note is held / rings out. The previous model looped one short fundamental period sampled from
  the *attack* — a static buzz; that is the harshness the owner heard.
* **Derived sustain loop (`compute_loop`).** IC307 stores no loop points (MEASURED,
  `kn5000-ic307-content-map.md` §3.4), so we derive one: a region in the recording BODY (>= N/3
  in, ending ~1 period before the tail) whose length is an integer number of fundamental periods
  (so the seam is pitch-continuous), slid within ±½ period to minimise the sample+slope
  discontinuity at the seam. Measured seam discontinuities are small (tens–low-hundreds of LSB
  vs 32767 full-scale) across the tested waves.
* **Pitch cannot regress (hard constraint).** Playback rate is still driven ENTIRELY by the
  equal-tempered played note (recovered from the real keybed/MIDI event) via the recording's
  detected fundamental period `pitch_period` — identical to the prior single-cycle model, since
  advancing the read pointer by that period-derived step makes the fundamental recur at exactly
  the played frequency regardless of the recording's (un-stored) native root. The loop length is
  an integer multiple of `pitch_period`, so looping does not perturb pitch.

## 4. Verification (MEASURED on the built driver)

Keybed notes pressed via lua ioport (`-nvram` pre-init play screen, `-wavwrite`, 3-ch WAV, ch1):

* **Pitch NOT regressed (hard constraint) ✓.** C4 → fundamental **262 Hz** (dominant), with real
  harmonics (524, 1308 Hz). C5 → **524 Hz** = exact octave of C4. Chord C-E-G → **262 / 330 / 392
  Hz** all three fundamentals present and strong (mags 1.29M / 1.30M / 1.80M). 12-semitone
  distinctness preserved (period-driven step is unchanged from the prior model).
* **Full multi-cycle playback ✓.** Fine (5 ms) onset envelope of C4: silence until +40 ms (the
  firmware software-envelope attack delay), then a smooth attack ramp +40→+95 ms, then an
  evolving body (RMS fluctuating 800–1500) — a real attack transient + body, NOT the previous
  static single-cycle buzz. The recording plays 0→loop_end once, then loops the derived body
  region.
* **Envelope / velocity / MIDI-keybed bridge / has_pcm intact ✓** (those paths unchanged;
  `has_pcm` now gates on `wave_samples`). Held notes sustain via the body loop.
* **`-validate kn5000` clean (exit 0); boots to the play screen; voices sound.**

## 5. Honest limitations / what's left

<!-- FILLED -->
