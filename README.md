# MAME_Technics_Research

This repo hosts the raw work-in-progress of MAME-related investigations of the Technics musical keyboards.

It is laid out as an *overlay* on the MAME source tree: every file under `src/`
sits at the path it would occupy inside MAME, so integrating it is a matter of
copying the files in and registering them in the build (see
[`INTEGRATION.md`](INTEGRATION.md)).

## What lives where

- `src/mame/matsushita/` — machine drivers and devices for the Technics
  keyboards: KN5000, KN6000/KN6500, KN7000, KN1500 and KN2400/KN2600, plus the
  SX-WSA1/WSA1R synthesizer, and the shared control-panel (`kn_cpanel`) and
  tone-generator (`kn_tonegen`) device bases they build on.
- `src/devices/cpu/mn10300/` — a Panasonic MN10300/AM33 execution core
  (upstream MAME ships only the disassembler). Overlay work also touches
  `tlcs900/` (the shared core, TMP94C241, TMP95C061 and TMP95C063), `sharc/`
  and a `upd6383/` DSP core.
- `src/devices/machine/`, `src/devices/video/`, `src/devices/bus/technics/` —
  overlaid copies of `spi_sdcard` (the KN7000's SD card), `sed1330` (the WSA1's
  all-graphics panel) and the KN5000's `hdae5000` expansion board.
- `src/mame/layout/` — internal layouts for kn5000/kn6000/kn7000 and wsa1r.
- `notes/` — investigation write-ups and findings; the bulk of the research
  record. Start here for the current state of any given topic.
- `tools/` — capture rigs, Lua probes, oracles and disassembly helpers.
- `tests/` — MN10300 instruction-length validation against MAME's unidasm.
- `mame-pr/` — material staged for upstream MAME pull requests.

## Building

`./build.sh` assembles a disposable build tree from a full MAME checkout
(default `../mame`, which has to be on the `kn7000-base` branch), symlinks this
overlay's files into it and compiles a focused MAME binary with the Qt debugger
included. Overridable environment variables: `MAME_SRC`, `BUILD_TREE`, `ROM_SRC`,
`JOBS`, `QT_HOME`. The manual steps it automates are documented in
[`INTEGRATION.md`](INTEGRATION.md).

## Status and caveats

This is raw work-in-progress, not a finished emulator: every machine is marked
`MACHINE_NOT_WORKING`, and several ROM images the drivers reference are not
honest dumps of the real chips — they are marked `BAD_DUMP` in the driver
source and must not be mistaken for verified preservation.

## License

Follows Felipe's preferred licensing for MAME contributions: BSD-3-Clause for
core modules, GPL2+ for the machine drivers. (c) 2026 Felipe Correa da Silva Sanches.
