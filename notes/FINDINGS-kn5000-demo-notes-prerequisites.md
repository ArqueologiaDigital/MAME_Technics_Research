# What the KN5000 demo needs before it can play a single note

Date: 2026-08-19. Written while preparing an upstream PR for a minimal tone generator.

## The question

The built-in Feature Presentation demo plays music on our private overlay. On a tree based on
upstream master it does not, even with a working tone generator attached. What is missing?

## The measurements

Identical stimulus in both trees (`tools/rigs/kn5000_tg_writes.lua`, which presses DEMO, LEFT 4,
LEFT 2 and taps sub-CPU writes to the tone generator at 0x100000/0x100002):

| tree | note-on gates | data writes | audio RMS |
|---|---|---|---|
| private overlay | 4141 | 137211 | 1386 / 1253 |
| upstream + minimal tone generator | 65 | 2343 | 0.0 / 0.0 |
| upstream + all three fixes below | **4141** | 137154 | **1361 / 1243** |

The 65 gates are the sub-CPU's boot-time sweep across its 64 voices; they happen before any
payload transfer, which is why they appear even when the link is dead. Null control (no stimulus,
30 s): RMS 0.0. Windowed gate over t=55..135 s: every 5 s window above 200 in the fixed tree.

## The cause: two lost edges, one on each side

**1. A latch write on an unread byte raises no interrupt, and destroys the byte.**
`generic_latch_base_device::set_latch_written()` invokes the pending callback only when the flag
CHANGES (`src/devices/machine/gen_latch.cpp`), while `sync_callback()` overwrites the stored value
unconditionally. So the second of two writes to an unread latch is silent in both senses: no
/INT0, and the first byte is gone.

**2. Releasing /INT0 from inside a read handler does not take effect until the timeslice ends.**
`generic_latch_8_device::read()` calls `set_input_line(..., CLEAR_LINE)`, which is deferred through
`synchronize()`. The level stays asserted for the rest of the slice.

Upstream's cover for (2) was a level-detect re-assertion in `tmp94c241`'s interrupt acceptance: if
the pin still reads asserted, put the flag back. That re-raises a request that has already been
served, and on this machine it dispatched a non-reentrant receive ISR twice -- the inner call ate
the header, the suspended outer call then read a PAYLOAD byte and parsed it as a header, arming
micro-DMA for a count that could never complete.

## The fix is a matched pair

- CPU core: delete the re-assertion, and expose `clear_int0_level()`.
- Driver: clear the latch's pending flag before each write, and call `clear_int0_level()` from each
  read handler. Hold the two CPUs in step around a transfer so the writer cannot outrun the reader.

**They only work together.** Removing the re-assertion ALONE was measured and changed nothing --
65 gates, silence -- because it removes the old recovery without supplying the edges that replace
it. That null result was briefly misread here as "the CPU fix is not a prerequisite"; it is one
half of a prerequisite.

## What was excluded, and how

- **The IC14 rhythm ROM record.** Upstream already carries the corrected dump (commit 8789d0f0d48).
  Our local ROM set was the stale transposed file. `tools/kn5000_descramble_ic14.py` reorders our
  dump's eight 512 KiB blocks and produces SHA1 `fef7f1927935d8fdada2afbdbfac29aac56e1c3c`, exactly
  the upstream record -- so the corrected dump IS this data, reordered. Re-running the test with a
  byte-correct IC14 still gave 65 gates: necessary for correct data, not the blocker.
- **The sub-CPU boot ROM (IC30).** Both trees load the same file, and the overlay plays the demo
  with it. Excluded by construction; Felipe confirmed independently.

## The process lesson, which cost more than the bug

Three wrong causes were proposed here (IC14, IC30, the CPU fix alone), each from reading code and
reasoning about it. The two things that actually moved the investigation were a SCREENSHOT and a
SWEEP:

- The demo start needs THREE presses (DEMO -> LEFT 4 -> LEFT 2). The rig pressed one and asserted
  in its own header that this started the demo. Every capture made with it was silent for a reason
  that had nothing to do with the code under test. Nine scripted presses and two hypotheses were
  spent before anyone looked at the display, which showed a menu.
- Which soft key starts it was then GUESSED from where the arrows sat on screen, twice, wrongly.
  Pressing all five and counting note-ons answered it in one run.

If a scripted stimulus produces no effect, photograph the machine before theorising about the
code. `tools/rigs/kn5000_screenshots.lua` and `tools/rigs/kn5000_softkey_sweep.lua` exist for this.
