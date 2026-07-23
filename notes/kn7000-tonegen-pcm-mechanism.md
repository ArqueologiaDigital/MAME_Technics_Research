# KN7000/KN6000/KN6500 tone generator: every voice now plays PCM (no sine oscillator)

Felipe Sanches' faithful-mechanism principle: *the emulation should be as accurate
as possible, even when temporarily faking something — fake it with the CORRECT
MECHANISM real hardware would use.* The Technics MN10300-family tone generators
(KN7000 IC201/IC205, KN6000/KN6500 IC213) are **wavetable/PCM** engines: every
voice reads sample data from a wave ROM. There is **no sine oscillator anywhere on
the chip.**

The four KN7000 wave ROMs are **undumped**, so the shared tone-generator base
(`src/mame/matsushita/kn_tonegen.cpp`) used to have two amplitude/timbre paths in
its render loop:

* a **synthetic wave-pack PCM path** — voices whose runtime sample-select maps to a
  donor zone in `kn7000_waves_synthetic.rom` ("KN7WVSY2", built by
  `tools/make_wave_pack.py` from genuine KN5000 IC307 donor PCM) play real PCM with
  start/len/loop + linear interpolation. **This is the correct mechanism.**
* a **`sin()` fallback** — voices with no pack entry (`m_wsel[v] == -1`) were
  synthesized with a computed sine oscillator. **This is the placeholder that has
  now been removed**, because real hardware has no such oscillator.

## What changed

1. **A fabricated sine is now a real PCM sample.** `tools/make_wave_pack.py` emits a
   single-cycle, whole-loop sine as **entry 0** of the pack, on the reserved
   **wildcard bank `0xFF`** (which never zone-matches a real voice). It is
   441 samples long → root pitch `44100/441 = 100.000 Hz` exactly, full-scale
   (±32767). The driver adopts this entry as the **default** that any otherwise-
   unmapped voice maps to.

2. **`m_wsel` is never `-1` for a keyed voice.** Both derived decoders
   (`kn7000_tonegen.cpp`, `kn6000_tonegen.cpp`) now initialise the per-voice
   wave-select to `m_wdefault` (the sine entry) and only override it when a donor
   zone matches. So every keyed voice flows through the **single PCM-playback
   datapath** (start/len/loop/interp).

3. **The `sin()` branch is deleted** from `kn_tonegen_base_device::sound_stream_update`.
   One codepath, matching hardware.

4. **Robustness when the optional pack ROM is absent.** The pack ROM is
   `ROM_LOAD_OPTIONAL`. If it is missing (or supplies no bank-`0xFF` entry),
   `device_start` **synthesizes the identical 441-sample / 100 Hz sine into an owned
   `m_sine_pcm` buffer** and registers it as `m_wdefault`. So the render path stays
   pure PCM regardless of whether the fabricated ROM is present — never a `sin()`
   oscillator, never silence for a keyed voice.

This also shrinks the artificial gap between the KN5000 (real PCM) and the
MN10300-family tone generators: all now go through sample playback.

### KN6000 livelock caught + fixed (a required consequence of routing every voice through PCM)

Routing every voice through the PCM datapath surfaced a latent hazard on the
**KN6000/KN6500**, whose note->pitch resolve is *not yet reversed* (see the
`kn_tonegen.h` header). During boot the KN6000 hands the render a **huge (finite),
non-finite, or negative `m_freq`**. The old `sin()` fallback shrugged this off (one
phase add). The PCM path must not: an unbounded `while (pos >= end) pos -= llen`
wrap would iterate billions of times on a huge finite step and **livelock the
single-threaded emulator** (MEASURED: pure HEAD boots KN6000 to its play screen in
seconds; HEAD+this-change stalled at ~0.84 emulated s, still spinning at 60 wall s).

The render is therefore hardened (this is correct for a wave engine regardless of
the placeholder situation — it must never livelock or read out of bounds on a bad
pitch):

* **read position** sanitised (`isfinite`, `0 <= pos < len`) before `uint32_t(pos)`
  indexes the PCM — no OOB read;
* **step** clamped finite / non-negative;
* **loop wrap** done with an **O(1) `fmod`**, not a subtract-loop — bounded for any
  finite step.

Verified after the fix: KN6000 and KN6500 both boot to their PMEM play screen with
full-length audio, identical to the pre-change (pure-HEAD) behaviour; the KN7000 A/B
is unchanged (below). The proper cure is to reverse the KN6000 note->pitch routine
so `m_freq` is always a sane musical frequency; until then the guards keep the shared
render robust.

**Honest label (in-source and in the pack provenance):** *fabricated sine PCM
placeholder for the undumped wave ROMs; the datapath is faithful, the data is not.*
Richer timbres are deliberately NOT invented here — that is for when the real ROMs
are dumped.

## Files touched

* `src/mame/matsushita/kn_tonegen.h` — `m_wdefault`, `m_sine_pcm`; `m_wsel` comment.
* `src/mame/matsushita/kn_tonegen.cpp` — recognise bank `0xFF` default in the pack
  parse; synthesize the fallback sine if absent; **delete the `sin()` render branch**
  (single PCM datapath); drop the now-unused `FS`/`TWO_PI` render constants.
* `src/mame/matsushita/kn7000_tonegen.cpp` — unmapped voice → `m_wdefault` (was `-1`).
* `src/mame/matsushita/kn6000_tonegen.cpp` — unmapped voice → `m_wdefault` (was `-1`).
* `tools/make_wave_pack.py` — `build_sine_entry()` emits the default sine (entry 0,
  bank `0xFF`); provenance updated.
* `kn7000_waves_synthetic.rom` regenerated deterministically:
  * old: 14 entries, CRC `fcaf76ad`, SHA1 `c4268b2b385dd1a6fe80bd7eeb662aea55da7caf`
  * new: 15 entries (14 donors + default sine), CRC `bc94e4ba`,
    SHA1 `66543485ac7ba53126a765168555b525b38d87b2`
  * driver `ROM_LOAD_OPTIONAL` hash in `kn7000.cpp` updated to match.

## Behaviour proof (MEASURED — A/B FFT)

The mechanism swap must not change the audible tone (same clean sine, same pitch,
same level). To isolate the fallback specifically, the A/B was captured with the
**wave pack ROM absent**, so BEFORE every voice used `sin()` and AFTER every voice
used the C++ fallback PCM sine. Note held = C4 (MIDI 60) on the KN7000 home screen;
steady window [23–26 s]; Goertzel fundamental estimate.

| capture            | binary            | source           | fundamental      | RMS    | peak   | THD (h2–h8) |
|--------------------|-------------------|------------------|------------------|--------|--------|-------------|
| `before_sine.wav`  | old (pre-change)  | computed `sin()` | **261.630 Hz**   | 0.0238 | 0.0639 | ~0.07 %     |
| `after_sine.wav`   | new (this change) | fabricated PCM   | **261.630 Hz**   | 0.0238 | 0.0639 | ~0.07 %     |

* Fundamental **MIDI 60.000** in both (< 0.001 semitone difference — well within the
  < 0.01-semitone gate). Level and decay envelope identical to integer-peak
  resolution; THD ~0.07 % confirms a clean sine.
* The two WAVs are **not** bit-identical (16 918 bytes differ) — exactly the expected
  "PCM-sampled sine vs computed sine" result — yet spectrally indistinguishable.
* **Pitch tracking of the fabricated sample verified** at a second note: C5 (MIDI 72)
  on the new binary reads **523.25 Hz = MIDI 72.000** exactly. The 100 Hz-root sine
  steps correctly across the range.

Normal path (pack present, 15 zones): KN7000 boots to the PMEM play screen; the
default Concert Grand plays through the donor path unchanged. KN6000/KN6500 (which
have no wave-pack region) now play the C++ fallback PCM sine instead of `sin()`;
both boot to their play screen. `-validate` clean on all seven drivers (kn5000,
kn6000, kn6500, kn7000, kn2400, kn2600, kn1500).
