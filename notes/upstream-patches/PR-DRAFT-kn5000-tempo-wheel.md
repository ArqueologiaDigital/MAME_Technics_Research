# PR draft — KN5000 TEMPO/PROGRAM data wheel

**Status:** READY, not yet submitted.
**Branch:** `kn5000_tempo_program_wheel` (worktree `~/compartilhado/mame-pr-ic14`), off
`upstream/master` @ `8789d0f0d48`. One commit, 3 files, +91 lines.
**Build:** `make SUBTARGET=kn5000 SOURCES=src/mame/matsushita/kn5000.cpp USE_QTDEBUG=0 -j8`
**Validated:** `./kn5000 -validate` → exit 0.
**Test:** `tools/rigs/kn5000_wheel_pr_test.lua` in the kn7000_mame repo — ten detents give ten
steps on `-bios v5`, `-bios v7` and the default v10.

---

## PR title

    kn5000: emulate the TEMPO/PROGRAM data wheel

## PR description (paste this)

The endless rotary encoder below the LCD is now an input. Turning it changes the on-screen
tempo, and whatever value the focused widget holds.

The wheel is an input of the **left** panel MCU: the service manual puts SW101 (ENCODER SWITCH,
`QSRGT002AA`) on the CPL board, wired to that MCU's ROTA/ROTB pins. It reports over the
control-panel serial link the buttons already use, as a two-byte frame — header `0xD7`, then a
signed count of detents since the last report.

`0xD7` is `0xC0 | 0x17`: bits 7:6 = 11 select the left panel, which `send_button_packet()`
already encodes, and `0x17` is the encoder's sub-address. The firmware maps a header to a record
index with `((header & 0xC0) >> 1) | (header & 0x1F)`, so `0xD7` selects record `0x19`, the data
wheel; only `0xD7` and `0xF7` reach that index and both are left-panel headers.

Three details the code depends on:

* **The second byte is a count, not a direction.** The firmware indexes an acceleration curve
  with it, so several detents inside one report period move the value further than one detent
  does — sub-linearly.
* **The count is negated.** That curve is monotonically decreasing, so a negative count raises
  the value.
* **The count must be clamped to −16..+15.** The firmware computes the curve index as
  `sext8(count + 0x10)` with no bounds check, and a larger magnitude would index off the end of
  a 32-entry table. A real panel cannot produce one, so neither may this.

The control is a wrapping positional input rather than an adjuster, since an endless encoder has
no absolute position to represent — following `src/mame/oberheim/xpander.cpp`, which has the
same kind of control on a synthesiser front panel. Detents are handed to the control-panel
device, which is what puts them on the wire.

Tested on the v5, v7 and v10 firmware revisions: ten detents give ten steps on each. Turning the
wheel faster than the panel reports moves the value less per detent, which is the acceleration
curve doing its job; the report cadence itself has not been checked against hardware.

### AI assistance

Parts of this work were done with AI assistance: **Claude Opus 5** (Anthropic), via Claude Code.
The wire encoding was derived from the firmware and cross-checked against the service manual,
and the behaviour was measured on three firmware revisions; I have reviewed and understand the
change.

---

## Why not the obvious approach

An earlier version of this wrote the firmware's own scan list in work RAM directly. It is not in
this PR, and should not be revived: that list is at `0x8E94` only on v8/v9/v10 (v7 uses
`0x8DF8`, v5/v6 use `0x8DD4` — and v5/v6 use `0x8E94` for something else, so the write corrupted
a live record); it could overwrite an entry before the main loop consumed it; and it landed
downstream of the firmware's own modal filter on record `0x19`. Going over the wire removes all
three, and the wire encoding is byte-identical across all six dumped revisions.
