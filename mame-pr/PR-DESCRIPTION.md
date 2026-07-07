# Technics keyboards — preservation skeletons

Skeleton drivers that declare the Technics arranger keyboards and their firmware
ROMs so the images are preserved in MAME. No emulation is implemented yet
(`MACHINE_NOT_WORKING | MACHINE_NO_SOUND`); feature work will follow in later PRs.

## Files

- `src/mame/matsushita/kn7000.cpp` — new; the **Panasonic MN10300/AM33** family:
  **KN2400, KN2600, KN6000, KN6500, KN7000** (one MILK-framework source tree).
  Uses the `mn10300` CPU device as a minimal placeholder. **Depends on the separate
  MN10300 core submission.**
- `src/mame/mame.lst` — add `kn2400 kn2600 kn6000 kn6500 kn7000` under a new
  `@source:matsushita/kn7000.cpp` group.

## ROMs

All 2,097,152 bytes each, de-interleaved into the physical even/odd 16-bit flash
chips (`ROM_LOAD32_WORD`), reconstructed from the checksum-verified `.SLD` firmware
updates (good dumps). Full SHA1s: see `notes/mame-pr-rom-manifest.md`.

| Driver | ROM (CRC32) |
|---|---|
| kn2400 / kn2600 | program even `b94fc8a8` / odd `73781cbc` |
| kn6000 | prog even `5baeae6d` / odd `537471c0`; table even `fa5e4f93` / odd `fd8e3bcd` |
| kn6500 | prog even `d6cd26bb` / odd `1691c3d8`; table even `8c7f33a2` / odd `6953e094` |
| kn7000 | prog even `529b87ce` / odd `a36e6222`; table even `005a6db2` / odd `7e1a312e` |

## Licensing

- **Drivers: GPL2+** (matching `kn5000.cpp`) — `kn7000.cpp`.
- **CPU cores: BSD-3-Clause**, as with the other MAME cores — the MN10300 execution
  core (submitted separately) and the `mn10300` disassembler (already upstream, AJR).

## Notes

- kn2600 is a clone of kn2400 (one firmware serves KN2400/KN2600/PR54 via a runtime
  model selector; a `pr54` clone can be added once its exact model name is confirmed).
- The earlier TLCS-900 **SX-KN1500 is deferred** from this PR: its ROM dump needs
  further investigation (a redump) before it can be included.
