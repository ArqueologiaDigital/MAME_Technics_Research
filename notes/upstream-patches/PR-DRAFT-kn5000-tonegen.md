# PR draft: KN5000 tone generator (partial), and the two interrupt fixes it needs

Branch: `kn5000_minimal_tonegen` in `~/compartilhado/mame-pr-tonegen` (worktree off upstream/master).
Three commits:

1. `tlcs900/tmp94c241: one /INT0 request per assertion of the pin`
2. `kn5000: raise one /INT0 per inter-CPU latch write, and release it on read`
3. `kn5000: add a partial tone generator (IC303)`

887 insertions. Full incremental history preserved at tag `detailed-history-2026-08-20`; the state
before the pitch table became a ROM walk is at `pre-romwalk-2026-08-19`.

---

## Suggested PR description

### Summary

Adds a partial tone generator for the Technics SX-KN5000, plus the two interrupt fixes without
which the machine cannot play a note. It goes from `MACHINE_NO_SOUND` to
`MACHINE_IMPERFECT_SOUND`, and its built-in demo plays.

### The tone generator is deliberately partial

IC303 is a 64-voice chip that plays PCM multisamples from four mask ROMs. Three of them --
IC304/305/306 -- are undumped and stay `NO_DUMP`. **This device reads no waveform data at all and
synthesises a sine per voice instead.** The notes come out at the right pitch and the right time;
the tone colour is a placeholder and is not what the instrument sounds like. That is stated in the
device header as plainly as I can put it, and it is the part of this PR I would most like an
opinion on: the alternative is for the machine to stay silent until the ROMs are dumped.

What is modelled, all decoded from the firmware's behaviour rather than guessed:

* the register protocol, and the per-voice registers carrying gate, recording selector, output
  level, pan, absolute pitch and a **four-segment** amplitude envelope;
* the hand-off command's low byte as a per-voice output level (F0FF full, F1D7, F187, F000 silent);
* the voice lifecycle the sub-CPU's allocator reads back through the status port.

**Nothing firmware-derived is checked in.** The per-recording pitch constants the HLE needs are
built at `machine_start` by walking the firmware's own multisample descriptors in the `table_data`
mask ROM -- a ROM the driver already loads -- so they also follow whichever firmware revision is
selected. 1444 constants from 487 descriptors.

### The two interrupt fixes

They are a matched pair; neither works alone.

**`tmp94c241`.** On taking INT0 the core restored the interrupt flag if the pin still read as
asserted. That cannot be right: MAME defers an external de-assert through `set_input_line()` ->
`synchronize()`, so a device that releases /INT0 inside its own read handler leaves the level stale
for the rest of the timeslice and the flag is raised again for a request already served. On this
machine it dispatched a non-reentrant receive ISR twice; the inner call consumed a packet header,
the outer one then read a payload byte and parsed it as a header, and the inter-CPU link never
recovered. `clear_int0_level()` is added so a driver can retire the level when its read handler
releases the pin.

**`kn5000`.** `generic_latch` invokes its pending callback only when the flag CHANGES, so a byte
written while the previous one is unread raises no interrupt at all -- and replaces the unread byte.
The driver now clears the flag before each write and calls `clear_int0_level()` from each read
handler. This hole is general: any driver pairing `generic_latch` with a level-triggered interrupt
has it.

### Verification

Stimulus is the machine's own Feature Presentation demo, started from the panel (DEMO, then the
FEATURE PRESENTATION soft key, then "Start the internal DEMO"), captured for 140 s.

| | before | after |
|---|---|---|
| note-on gates reaching IC303 | 65 (the boot sweep only) | ~4100 |
| register writes | 2343 | ~137000 |
| audio rms, L/R | 0.0 / 0.0 | 936 / 805 |

* Null control, no stimulus, 30 s: **rms 0.0**. Every figure above is quoted against that.
* Audibility: every 5 s window from t=55 s to t=135 s is above rms 200 -- no silent gaps.
* `-validate` clean; the waveform ROM region is untouched.
* Cost of the device: 1.65 percentage points of emulation speed (82.34% with sound, 83.99% with
  `-sound none`, same run).

⚠ **The gate count is a signal, not an invariant.** The demo's completion is timing-fragile:
4141, 4363 (with `-sound none`) and 2796 (with one internal constant rounded by 1.7%) have all been
measured. The failure criterion that matters is a STALL -- a gate count that freezes and never
advances -- not any particular total.

### Known inaccuracies, stated rather than discovered

* The timbre is a placeholder; see above.
* Percussion is rendered as a tone held for the note's length, where the real chip decays it inside
  its own PCM, so the balance between drums and pitched parts is wrong.
* The envelope rate law's two constants are fitted by ear. Measured over 1279 demo notes, 87% reach
  their final envelope level in under a tenth of the note's own length, so the fit shapes the
  remaining ~13%.
* `SILENT_HOLDOFF` is load-bearing at its exact value: rounding it to 100 ms stalls the demo,
  because when a voice is reported free shifts firmware timing enough to trip the link race above.
* 68 of the 1444 pitch constants are ambiguous -- reachable from more than one descriptor with
  different values -- and are resolved by weight with a deterministic tie-break.

### AI disclosure

This work was produced with AI assistance: Claude Opus 5 (1M context), via Claude Code, under my
direction and review. The reverse engineering, the measurements quoted above and the code were
produced in that collaboration; I have reviewed and tested the result.

---

## Notes for the submitter (not part of the description)

* Consider asking upstream about the placeholder oscillator BEFORE submitting -- it is the one
  design decision a reviewer may reject outright, and the answer changes the shape of the PR.
* Decide whether to split commit 1 (the CPU core fix) into its own PR; it stands on its own merits
  and has a different reviewer audience.
* Reproduce with `tools/rigs/kn5000_tg_writes.lua` (gates) and `tools/wav_rms.py` (audio) from the
  KN7000 preservation repository.
* NOT yet verified against real hardware. A recording of the instrument playing the same demo would
  check the note decode end to end and measure the envelope rate law; `tools/kn5000_compare_real.py`
  is written and waiting for the audio.
