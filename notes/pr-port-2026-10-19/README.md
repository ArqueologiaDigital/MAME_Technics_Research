# Five unmerged PRs carried in the overlay (2026-10-19)

Felipe asked for everything in flight upstream to run in the overlay build before it merges:

| PR     | what                                                                   | how it reached the overlay                                                                  |
|--------|------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| #16517 | KN7000 firmware v1.3 (program 893 / table 80) BIOS                     | ported by hand into the overlay's `kn7000.cpp` (with upstream's whole BIOS set)             |
| #16520 | the four wave ROMs; the main TG is at 0x98050000                       | ported by hand: ROM records, the wave ROM test port, the main/sub labels                    |
| #16523 | the rhythm ROM IC18 at 0x40000000                                      | ported by hand: ROM record, installed in `machine_start()`                                  |
| #16524 | the picture ROM IC19 at 0x57800000                                     | ported by hand: ROM record, installed in `machine_start()`                                  |
| (none) | floppy software lists rebuilt (`technics-kn-flop-rebuild`, not opened) | hash commit cherry-picked onto `kn7000-base` (`59af79aca1f`); its driver fixes started here |

The overlay's `kn7000.cpp` is not upstream's file (one `kn7000_state`, the voice engine, the DSP), so the
four driver PRs could not be applied as patches.

## What changed

- **ROM records.** The `kn7000` set takes upstream's records and file names: `-bios sp7001`, `v16`
  (default), `v15`, `v14`, `v13`; the wave ROMs `c3cbqd00000[1-4]`, `c3cbnd000046.ic18`,
  `c3cbmd000098.ic19`. Region tags stay the overlay's (`maincpu`, `table`). This was inventory item B.6
  in `../overlay-upstream-sync/UNSUBMITTED-2026-10-18.md`.
- **Per-BIOS firmware addresses.** The driver was written against v16, and five addresses it uses
  move between builds. Without the interrupt entry points the firmware does not take interrupts at
  all. `kn7000_bios_info` in `kn7000.cpp` holds them; `tools/kn7000_bios_addresses.py` produces
  the table:

  | bios   | build | quick dispatcher | scheduler entry | voice records | SD audio state | SD sound state |
  |--------|-------|------------------|-----------------|---------------|----------------|----------------|
  | sp7001 | 942   | `0x4C03E2C6`     | `0x4C03E34C`    | `0x500AF950`  | `0x500063EE`   | `0x500063E1`   |
  | v16    | 941   | `0x4C03DDA0`     | `0x4C03DE26`    | `0x500AF940`  | `0x500063E6`   | `0x500063D9`   |
  | v15    | 935   | `0x4C03DDA0`     | `0x4C03DE26`    | `0x500A1104`  | `0x500063E6`   | `0x500063D9`   |
  | v14    | 929   | `0x4C03DD8B`     | `0x4C03DE11`    | `0x500A1104`  | unknown        | unknown        |
  | v13    | 893   | `0x4C03DD8D`     | `0x4C03DE13`    | `0x500A10E0`  | `0x500063DE`   | `0x500063D1`   |

  The handlers are found by v16's bytes (64 at the library start, 0x86 at the quick dispatcher, 64 at
  the scheduler entry), each exactly once per image. The work-RAM addresses are found by the 12 bytes
  before and 8 after each place v16's code names them; every matched site agrees (between 2 and 55
  sites per address). v14 survives only from its upper half, so it cannot boot and its SD code is
  missing.

  `thunk_check.sh` confirms the scheduler entries on the running firmware. In upstream's driver the
  CPU enters interrupts through a thunk the firmware builds at 0x50000000, `nop ; jmp (d32,PC)`.
  On the v1.3 PR build, each version's thunk jumps to the table's scheduler entry, and both table
  entries hold the handler prologue `cff8f8fe...` in library RAM (`thunk_check-2026-10-19.txt`):

  | bios   | thunk `jmp` displacement | target       |
  |--------|--------------------------|--------------|
  | sp7001 | `0xFC03E34B`             | `0x4C03E34C` |
  | v16    | `0xFC03DE25`             | `0x4C03DE26` |
  | v15    | `0xFC03DE25`             | `0x4C03DE26` |
  | v13    | `0xFC03DE12`             | `0x4C03DE13` |

- **Wave ROMs.** Served through the tone generators' wave ROM test port (`tg_wave_read`), the way the
  ROM dumper read them: main TG 0x98050000 select 0/1 = IC203/IC204, sub TG 0x98040000 = IC207/IC208.
  The driver had the two tone generators' names the other way round; the comments are corrected,
  and the indices (0 = 0x98040000) are unchanged. **The voices still play the synthetic wave pack:**
  only the test port reads the real ROMs.
- **IC18** is installed at 0x40000000 (mirror 0x40400000) and **IC19** at 0x57800000 (mirrored to
  0x57FFFFFF). The synthetic "Technics Rhythms" resource at 0x54E00000 is retired.
- **Softlists.** `kn7000-base` carries the rebuilt `hash/kn{5,6,7}000_flop.xml`, and
  `tools/publish-binary.sh` ships the matching zips from
  `~/compartilhado/technics_romsets/floppy-rebuild-2026-10-18/roms/`. Zips are compared by content,
  not mtime, so a rebuilt image replaces the old one.
- **Publishing.** `tools/publish-binary.sh` copies the BIOS files and dumped chips from
  `~/compartilhado/technics_romsets/kn7000/` (they are not in `technics_roms/roms/kn7000`).

## Checks

`checks.sh MAME_BINARY OUTDIR [ROMPATH] [boot|wave|debug]`: the question each answers and the signal it
reads are in its header. `wave_port_check.lua` is a copy of KN7000
`tools/mame-pr-planning/kn7000-waverom-pr/wave_port_check.lua`.

Results on 2026-10-19, overlay binary built from this commit's source, ROM path = the published
folder's `roms/kn7000` plus `~/compartilhado/technics_romsets/kn7000`:

| check                               | result                                                                                                                                               |
|-------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| `build.sh`                          | 0 errors; `kn7000 -validate` and `-validate` (all systems) exit 0                                                                                    |
| `-verifyroms kn7000`                | best available: only v14's undumped lower half and the synthetic wave pack are flagged                                                               |
| boot v16                            | `release=0x16 table=84 window=40010000 styles=220 rhythm=33 picture=7`, main screen                                                                  |
| boot v15                            | `release=0x15 table=84 window=40010000 styles=220 rhythm=33 picture=7`, main screen                                                                  |
| boot v13                            | `release=0x13 table=80 window=40010000 styles=220 rhythm=33 picture=7`, main screen (`boot-v13.png`)                                                 |
| boot sp7001                         | `release=0xFF table=83 window=40010000 styles=220 rhythm=33 picture=7`, main screen                                                                  |
| wave                                | 4 of 4 OK: IC203 `8164C77C`, IC204 `815CFC83`, IC207 `8331EF0B`, IC208 `83254F9D`, the firmware's own sums                                           |
| debug (sp7001)                      | DEBUG TOOLS: PROGRAM 942, TABLE 83, RHYTHM 33, PICTURE 7 (`debugtools-sp7001.png`)                                                                   |
| ablation: v13 with v16's vectors    | black screen at 45 s, `window=00000000 styles=0`: the rhythm probe never ran (`ablation-v13-with-v16-vectors.png`)                                   |
| `-verifysoftlist`, published folder | kn5000_flop 14/14, kn6000_flop 21/21, kn7000_flop 6/6, wsa1_flop 9/9; the three rebuilt lists' hash files and all 40 zips equal the rebuild folder's |

**The gate** (`tools/gate.sh` on the published folder): 16 passed, 1 failed, 1 skipped. Static checks,
`verifyroms` for every model and liveness for every model pass, and so does the KN5000 demo oracle
(`8bbe54f7…`). The KN7000 audio oracle (`tools/rigs/money.lua`) moved from `4c3a522a…` to `bd02a9c1…`.
`oracle_attribution.sh` runs the gate's recipe three ways, each with its own copy of `nvram/kn7000`:

| run                                                                           | md5                                | rms  |
|-------------------------------------------------------------------------------|------------------------------------|------|
| old binary (published 2026-10-18, md5 `0f9dbc85…`)                            | `4c3a522a63f4e86fe9f7d7c8d94f5dbe` | 48.2 |
| new binary                                                                    | `bd02a9c15b580d6b4b4c0a42f78a1fcb` | 48.2 |
| new binary, IC18/IC19 windows read 0 and the synthetic resource at 0x54E00000 | `4c3a522a63f4e86fe9f7d7c8d94f5dbe` | 48.2 |

The firmware seeing the real rhythm and picture ROMs accounts for the whole change; the BIOS table,
the wave port and the relabelling move nothing on this path. The oracle is re-baselined to
`bd02a9c1…` in its own commit.

Every boot shows "8Bt Standard" in the RHYTHM field; until now the overlay showed the synthetic
resource's "8&16BT 01 ?". The large "KN7000" drawn green behind the main screen is not new (it is in
`../kn7000-ui-plane-2026-08-15.png`).

The ablation is the reason for the table: with v16's interrupt entry points, v13 takes no interrupt
and never reaches its first screen. It was built by changing only the v13 row to v16's two
vectors, and the source was restored afterwards.

## Not done

- **The voices do not play the real wave ROMs.** The voice engine still reads the synthetic pack;
  only the WAVE ROM test port reads the dumps. Playing them is the tone generator work (board #3, A2).
- **v14** cannot boot: its lower half was never dumped.
- **The SP7001 plug-in** (Another World) has not been tried on the overlay; it was developed on
  `~/compartilhado/mame-pr/kn7000`.
- **LCDR5 on the Panel Simulator** has to be pressed twice on the overlay (`checks.sh` header); on
  upstream's driver once is enough. Not investigated.
- The custom-flash records keep the overlay's names and region tag (`customflash`, the four Initial
  Data files); upstream has only `01ctmini.ic21` in `custom_data`.
- The published folder still holds the v16 set under its old names and `kn7000_rhythms_synthetic.rom`;
  nothing loads them, and `publish-binary.sh` never deletes.

## At the next resync

When these PRs merge, upstream's `kn7000.cpp` gains the same ROM records; the overlay's copy replaces
it as before, so nothing changes here. Rebasing `kn7000-base` onto an upstream that has the floppy
rebuild drops the cherry-pick `59af79aca1f` as already applied.
