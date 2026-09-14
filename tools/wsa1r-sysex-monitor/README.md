# `wsa1r-sysex-monitor` — a SysEx debug monitor for the SX-WSA1R

**Design and rationale: `notes/HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md` §A5.
Build log and current state: `notes/WSA1R-SYSEX-MONITOR-BUILD.md`.**

The goal is a bidirectional debug channel over MIDI so that µPD6383 probe microcode can be
loaded and its results read back as exact integers, instead of being inferred from audio. This
directory is the CPU-1 half: a monitor grafted into `prom_a`'s unused padding, reached by one
four-byte hook.

| file | what it is |
|---|---|
| `monitor.s` | the monitor, TLCS-900 assembly for `llvm-mc -triple=tlcs900` |
| `patch_rom.py` | grafts it into a `prom_a` image behind four refusal gates |
| `verify_in_emu.lua` | proves the patch is live *inside the running machine* |
| `build.sh` | assemble → patch → verify, one command |

## Build

```sh
./build.sh                       # writes patched_ic12.bin next to the originals it was told about
```

It assembles `monitor.s`, extracts a flat binary, and runs `patch_rom.py`, which **refuses to
write** unless all four hold: the input matches the known `prom_a` SHA1; the destination is
genuinely unused `0x0E` padding for the payload's whole length; the hook site still holds the
instruction being replaced; and the output differs from the input in *exactly* the payload plus
the four hook bytes.

## What it does today (milestone 1)

```
   in    F0 7E 7D 01 F7           -> IDENT
   out   F0 7E 7D 7F 01 00 F7
```

`0x7E` is one of the two SysEx identifiers the firmware accepts (the other is `0x50`); `0x7D` is
this monitor's marker. Once the marker is seen the monitor **claims** the message using
`(0xA9)` bit 5 — a state bit the firmware tests but never sets — and stops forwarding it to the
stock ring, so our traffic never reaches the stock parser. **Milestone 1 allocates no RAM at
all**: the reply is a ROM constant and the only state is that one borrowed bit.

## Verification, and what is still unproven

* ★ **Two independent toolchains agree.** `llvm-mc` assembles it; **MAME's own disassembler**
  (`unidasm`) reads the patched image back as exactly the intended instructions, with all four
  branch targets correct. The `call 0xf41e3c` inside it is byte-identical to the ROM's own.
* ★ **The patch is live in the running machine**, not just on disk — `verify_in_emu.lua` reads
  `0xFA586E` = `1B 46 A2 FB` (`jp 0xFBA246`), the monitor entry, and the reply table, out of
  CPU 1's own address space.
* ★ **The patched ROM boots** `wsa1r` in MAME (with the expected WRONG CHECKSUMS notice).
* ⛔ **NOT yet proven: end-to-end over MIDI.** Nothing has yet sent `F0 7E 7D 01 F7` into the
  emulated UART and seen a reply. That needs a MIDI source — see the build log.
* ⛔ **NOT yet proven: that calling the transmit primitive `0xF40ED4` from inside the MIDI
  receive interrupt is safe.** Its 47 callers look like main-loop code. If it is not re-entrant
  the reply must move to a main-loop hook.

## Restoring the instrument

The hook is four bytes. `patch_rom.py` prints the exact restore recipe every time it runs — or
simply put the original chip back in its socket, which is why sockets matter.
