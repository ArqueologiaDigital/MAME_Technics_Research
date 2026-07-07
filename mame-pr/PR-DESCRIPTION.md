# Technics keyboards — preservation skeletons

Skeleton drivers that declare the Technics arranger keyboards and their firmware
ROMs so the images are preserved in MAME. No emulation is implemented yet
(`MACHINE_NOT_WORKING | MACHINE_NO_SOUND`); feature work will follow in later PRs.

## Files

- `src/mame/matsushita/kn7000.cpp` — new; the **Panasonic MN10300/AM33** family:
  **KN2400, KN2600, KN6000, KN6500, KN7000** (one MILK-framework source tree).
  Uses the `mn10300` CPU device as a minimal placeholder. **Depends on the separate
  MN10300 core submission.**
- `src/mame/matsushita/kn5000.cpp` — modified to add the earlier **Toshiba TLCS-900
  SX-KN1500** (`TMP95C061`, already in MAME). Its LCD panel is an SVG rendered on an
  `SCREEN_TYPE_SVG` screen. See `kn5000-additions-kn1500.cpp` for the code block.
- `kn1500_lcd.svg` — the SX-KN1500 LCD artwork, loaded as a hashed ROM asset (the
  Game & Watch / `hh_sm510` pattern). Goes in the `kn1500` romset.
- `src/mame/mame.lst` — add `kn1500` under `@source:matsushita/kn5000.cpp`, and
  `kn2400 kn2600 kn6000 kn6500 kn7000` under a new `@source:matsushita/kn7000.cpp` group.

## ROMs

The MN10300 firmware images (2,097,152 bytes each) are de-interleaved into the
physical even/odd 16-bit flash chips (`ROM_LOAD32_WORD`), reconstructed from the
checksum-verified `.SLD` firmware updates (good dumps). The KN1500 firmware is a real
mask-ROM dump but **unvalidated → BAD_DUMP** (needs a redump); its SVG LCD artwork is
a good asset. Full SHA1s: `notes/mame-pr-rom-manifest.md`.

| Driver | ROM (CRC32) |
|---|---|
| kn1500 | `…ic15` prog `0f78da9a` · `…ic15.rest` rhythm `ce60897a` (BAD_DUMP); `kn1500_lcd.svg` screen `d779a7b9` |
| kn2400 / kn2600 | program even `b94fc8a8` / odd `73781cbc` |
| kn6000 | prog even `5baeae6d` / odd `537471c0`; table even `fa5e4f93` / odd `fd8e3bcd` |
| kn6500 | prog even `d6cd26bb` / odd `1691c3d8`; table even `8c7f33a2` / odd `6953e094` |
| kn7000 | prog even `529b87ce` / odd `a36e6222`; table even `005a6db2` / odd `7e1a312e` |

## Licensing

- **Drivers: GPL2+** (matching `kn5000.cpp`) — `kn7000.cpp` and the KN1500 block.
- **CPU cores: BSD-3-Clause** — the MN10300 execution core (submitted separately), the
  `mn10300` disassembler (AJR), and `TMP95C061` (Wilbert Pol); both already upstream.
- `kn1500_lcd.svg` is original artwork by Felipe Sanches.

## Notes

- kn2600 is a clone of kn2400 (one firmware serves KN2400/KN2600/PR54 via a runtime
  model selector; a `pr54` clone can be added once its exact model name is confirmed).
- The KN1500 program ROM is BAD_DUMP (unvalidated), but the machine is included so its
  SVG LCD panel is preserved as a ROM asset. `…ic15` = program, `…ic15.rest` = rhythm.
