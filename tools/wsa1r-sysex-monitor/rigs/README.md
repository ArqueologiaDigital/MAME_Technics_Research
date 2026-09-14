# `rigs/` — the Lua rigs that produced the numbers in this directory's notes

Each answers one question, non-invasively, inside a running MAME. Run them with
`-autoboot_script`, e.g.

```sh
cd ~/compartilhado/kn7000_mame_build
./kn7000 wsa1r -rompath <patched-roms> -skip_gameinfo -window \
    -autoboot_script ~/compartilhado/kn7000_mame/tools/wsa1r-sysex-monitor/rigs/<rig>.lua
```

| rig | question it answers | what it produced |
|---|---|---|
| `ramscan.lua` | **Which RAM windows does the firmware never write?** Write taps over candidate windows across a full boot. | The monitor's state address. Over 12 s: `0x007F00` **227** writes, `0x640000` **6**, `0x660000` **6**, `0x67F000` **0**, `0x67FF00` **0** — so the state block sits at `0x67FF00`. ⚠ Twelve seconds of *boot* is not the machine's whole life; re-run under more activity before trusting it on hardware. |
| `peek_verify.lua` | **Does PEEK actually work?** Asks the monitor to read its own reply table at `0xFBA236`, so the right answer is known in advance. | `MST_ADDR = 36 A2 FB 00` and a 21-byte reply matching the expectation byte for byte. Self-verifying by construction. |
| `midi_rxdiag.lua` | **Is MIDI reaching the CPU, and is it real data or framing noise?** Counts entries to `MIDI_RX_Byte` and reads the firmware's own error counter. | Settled that 102 entries occurred **with no input mounted** (framing errors **0**), i.e. they were spurious and our bytes were absent — which pointed the investigation upstream instead of at the monitor. |
| `images.lua` | **Did the MIDI image actually mount?** Lists `machine.images` with filenames. | `:mdin:midiin:midiinimg exists=true` — proving the file *was* loaded, which is what ruled out a mount failure and left MAME's deliberate 10-second playback delay as the only explanation. |
| `tap_probe.lua` | **What does MAME's Lua tap API accept?** Installs one tap under `pcall` and prints the error. | *"start address has low bits set, did you mean fba258?"* — the lesson that **taps must be bus-width aligned**. |
| `../midi_e2e.lua` | **End-to-end**: does a SysEx over MIDI reach the monitor? Execution taps on five addresses, with an upstream control. | The `✅ END-TO-END PASS` in `notes/WSA1R-SYSEX-MONITOR-BUILD.md`. |
| `../verify_in_emu.lua` | **Is the patch live in the running machine**, not just on disk? | Reads the hook, the entry and the reply table out of CPU 1's address space. |

## Two rig lessons worth keeping

* **MAME Lua address-space taps must be bus-width aligned.** CPU 1's program space is 16 bits, so
  an odd start address is rejected outright. Align down and cover the word — and remember the tap
  then fires on a fetch of *either* byte.
* **TLCS-900 registers are exposed bank-qualified** — `XWA0`…`XWA3`, `XDE0`…`XDE3`. There is no
  plain `DE`, and asking for one is a nil index. Which bank is live depends on RFP, so a rig that
  wants to set a register should set all four.

⚠ Every rig here is READ-ONLY on the machine except `peek_verify.lua`, which only reads too. None
of them writes guest memory; they observe.
