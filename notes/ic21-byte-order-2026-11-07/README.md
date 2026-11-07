# IC21's CUSTOM bank reached the CPU halfword-swapped (fixed 2026-11-07)

**Question:** does the CPU read the CUSTOM bank of `kn7000_custom_data.rom` (IC21 chip offset 0x20000 = CPU 0x96820000)
in the file's byte order? The file starts `49 4B 01 01 08 02 16 02` ("IK").

Reported by the technics-roms-disasm session (its `kn7000/notes/kn7000-ic21/README.md` section 1): the bank read
`"KI"`, and the firmware wrote an empty directory over it. Until this fix, the file was a plain `ROM_LOAD_OPTIONAL`;
the other three Initial Data files already had `ROM_GROUPWORD | ROM_REVERSE`.

| build                                        | CPU reads at frame 1      | at frame 2400 (40 s)                                      | bank = the file's at 40 s        |
|----------------------------------------------|---------------------------|-----------------------------------------------------------|----------------------------------|
| published `kn7000-emulator/kn7000` (b0fd265) | `4B 49 01 01 02 08 02 16` | `49 4B 00 00 00 00 00 00`: the firmware's empty directory | 1,246,477 of 1,966,080 (63.40%)  |
| with the word swap (this commit)             | `49 4B 01 01 08 02 16 02` | `49 4B 01 01 08 02 16 02`                                 | 1,966,080 of 1,966,080 (100.00%) |

c9862c2 (2026-08-02) quoted "100.00% match, 63.40% if byte-swapped" for this region. Its comparison had the
orientations the wrong way round: 63.40% is what the plain load gives.

- `ic21_peek.lua`: the probe. It reads bytes (`read_u8`), so no byte order of ours enters the reading. It peeks the
  first 8 bytes at frame 2 and at `IC21_LATE`, and with `IC21_FILE` compares the whole bank with the file.
- `run_peek.sh OUT [MAME]`: boots a fresh `-nvram_directory` (IC21 is an nvram device and loads the ROM only when it
  has no saved image) and prints the probe's lines.
  - `notes/ic21-byte-order-2026-11-07/run_peek.sh ~/compartilhado/tmp/ic21/before`
  - `notes/ic21-byte-order-2026-11-07/run_peek.sh ~/compartilhado/tmp/ic21/after ~/compartilhado/kn7000_mame_build/kn7000`

An nvram image saved by an older build keeps its swapped or emptied bank. Delete `nvram/kn7000/customflash` to have
the bank loaded from the ROM again (this loses saved custom data).
