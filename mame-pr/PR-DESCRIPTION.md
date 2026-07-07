# Technics keyboards — preservation skeletons

Skeleton drivers that declare the Technics arranger keyboards and their firmware
ROMs so the images are preserved in MAME. No emulation is implemented yet
(`MACHINE_NOT_WORKING | MACHINE_NO_SOUND`); feature work will follow in later PRs.

## Files

- `src/mame/matsushita/technics_kn.cpp` — the **Panasonic MN10300/AM33** family:
  **KN2400, KN2600, KN6000, KN6500, KN7000** (one MILK-framework source tree).
  Uses the `mn10300` CPU device as a minimal placeholder. **Depends on the separate
  MN10300 core submission.**
- `src/mame/matsushita/kn1500.cpp` — the earlier **Toshiba TLCS-900** SX-KN1500
  (`TMP95C061`, already in MAME). Same lineage as the SX-KN5000.
- `src/mame/mame.lst` — add: `kn1500 kn2400 kn2600 kn6000 kn6500 kn7000`.

## ROMs

All 2,097,152 bytes each. The MN10300 images are de-interleaved into the physical
even/odd 16-bit flash chips (`ROM_LOAD32_WORD`), reconstructed from the
checksum-verified `.SLD` firmware updates (good dumps). The KN1500 pair is a real
mask-ROM dump but **unvalidated → BAD_DUMP** (needs a redump). Full SHA1s: see
`notes/mame-pr-rom-manifest.md`.

| Driver | ROM (CRC32) |
|---|---|
| kn1500 | `...ic15` prog `0f78da9a` · `...ic15.rest` rhythm `ce60897a` (BAD_DUMP) |
| kn2400 / kn2600 | program even `b94fc8a8` / odd `73781cbc` |
| kn6000 | prog even `5baeae6d` / odd `537471c0`; table even `fa5e4f93` / odd `fd8e3bcd` |
| kn6500 | prog even `d6cd26bb` / odd `1691c3d8`; table even `8c7f33a2` / odd `6953e094` |
| kn7000 | prog even `529b87ce` / odd `a36e6222`; table even `005a6db2` / odd `7e1a312e` |

## Notes

- kn2600 is a clone of kn2400 (one firmware serves KN2400/KN2600/PR54 via a runtime
  model selector; a `pr54` clone can be added once its exact model name is confirmed).
- KN1500 `.ic15` (program) and `.ic15.rest` (rhythm) come from one mask ROM (IC15);
  the dump does not currently decode as coherent TLCS-900, hence BAD_DUMP.
