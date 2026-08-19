# PR draft: KN5000 tone generator (partial), and the two fixes it needs

Branch: `kn5000_minimal_tonegen` in `~/compartilhado/mame-pr-tonegen` (worktree off upstream/master).
Three commits, in this order:

1. `tlcs900/tmp94c241: one /INT0 request per assertion of the pin`
2. `kn5000: raise one /INT0 per inter-CPU latch write, and release it on read`
3. `kn5000: add a partial tone generator (IC303)`

---

## Suggested PR description

### Summary

Adds a partial tone generator for the Technics SX-KN5000, plus the two interrupt fixes it needs
before the instrument can play a note. The machine goes from `MACHINE_NO_SOUND` to
`MACHINE_IMPERFECT_SOUND`, and its built-in demo now plays.

### The tone generator is deliberately partial

IC303 is a 64-voice chip that plays PCM multisamples out of four mask ROMs. Three of those --
IC304, IC305 and IC306 -- are undumped and stay `NO_DUMP` here. **This device reads no waveform
data at all and synthesises a sine per voice instead.** The notes come out at the right pitch and
the right time; the tone colour is a placeholder and is not what the instrument sounds like. That
is stated in the header comment as plainly as I can put it.

What is modelled from the firmware's behaviour: the register protocol, eight of the thirty-two
per-voice registers (gate, recording selector, output level, pan, absolute pitch, three envelope
segments), the three-segment amplitude envelope, and the voice lifecycle the sub-CPU's allocator
reads back through the status port. Absolute pitch is decoded through a per-selector constant
table generated from the dumped sub-CPU program ROM -- no waveform ROM is consulted for it.

### The two fixes

They are a matched pair and neither works alone.

**`tmp94c241`.** On taking INT0 the core restored the interrupt flag if the pin still read as
asserted. That cannot be right: MAME defers an external de-assert through `set_input_line()` ->
`synchronize()`, so a device releasing /INT0 inside its own read handler leaves the level stale for
the rest of the timeslice, and the flag is raised again for a request that has already been served.
On this machine it dispatched a non-reentrant receive ISR twice; the inner call consumed the packet
header, the outer one then read a payload byte and parsed it as a header, and the inter-CPU link
never recovered. `clear_int0_level()` is added so a driver can retire the level at the moment its
read handler releases the pin.

**`kn5000`.** The two CPUs talk through a pair of 8-bit latches. `generic_latch` invokes its
pending callback only when the flag CHANGES, so a byte written while the previous one is unread
raises no interrupt at all -- and silently replaces the unread byte. The driver now clears the flag
before each write, so every write interrupts, and calls `clear_int0_level()` from each read handler.

This second one is general: any driver pairing `generic_latch` with a level-triggered interrupt
line has the same hole.

### Verification

Stimulus: the machine's own Feature Presentation demo, started from the panel (DEMO, then the
FEATURE PRESENTATION soft key, then "Start the internal DEMO"), captured for 140 s.

| | before | after |
|---|---|---|
| note-on gates reaching IC303 | 65 (boot sweep only) | 4141 |
| register writes | 2343 | 137154 |
| audio RMS, L/R | 0.0 / 0.0 | 1361 / 1243 |

- Null control, no stimulus, 30 s: RMS 0.0 on both channels. Every figure above is quoted against
  that, not against silence-in-principle.
- Audibility gate: every 5 s window from t=55 s to t=135 s has RMS above 200 -- no silent gaps.
- The same demo on our private research tree produces 4141 gates and RMS 1386 / 1253, so the note
  events reaching the chip are identical and the level agrees within 2%.
- `-validate` exits clean; the waveform ROM region is untouched.

### AI disclosure

This work was produced with AI assistance: Claude Opus 5 (1M context), via Claude Code, under my
direction and review. The reverse engineering, the measurements quoted above and the code were
produced in that collaboration; I have reviewed and tested the result.

---

## Notes for the submitter (not part of the description)

- The pitch table is generated, ~1500 lines, and derived from firmware. It is the most likely thing
  for a reviewer to object to. Without it every voice falls back to one constant and plays with a
  median error of about ten semitones, so it is load-bearing rather than decorative.
- Roughly 42% of the demo's note-ons arrive as "hand-off" commands whose low bits are undecoded;
  they are rendered silent, and that is where the drum part goes. Documented in the source.
- The envelope rate constants and the soft-clip knee are calibrated by ear, not decoded, and are
  labelled as such.
- Reproduce with `tools/rigs/kn5000_tg_writes.lua` (gates) and `tools/wav_rms.py` (audio) from the
  KN7000 preservation repository.
