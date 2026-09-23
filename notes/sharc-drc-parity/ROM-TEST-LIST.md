# Which existing MAME machines does the KN7000 submission put at risk?

Generated: 2026-09-23, branch `technics-kn7000-driver-final` vs `upstream/master` (ae30b778cae).

## The blast radius is exactly two things

Of the 24 files the branch touches, 18 are **new** and nothing outside the submission
references them. Two pieces are shared:

1. **`src/devices/cpu/sharc/`** — `sharc.cpp`, `sharc.h`, `sharcdrc.cpp`, `sharcfe.cpp`,
   `sharcfe.h`, `sharcops.hxx`. Every machine with an ADSP-2106x runs this code.
2. **`scripts/src/cpu.lua`** — one string. `DRC_CPUS` listed `"ADSP21062"`, which is not
   a CPUS token anywhere in the tree (the real token is `ADSP2106X`, cpu.lua:252). The
   entry was therefore dead, and a `SOURCES=` build whose only DRC CPU is the SHARC got
   `CPU_INCLUDE_DRC = false` and failed to link. Full builds were never affected —
   MIPS3/POWERPC/SH pull the DRC in regardless. No machine's behaviour changes.

So: **the machines to test are every machine with a SHARC.** 220 of them, in five
driver files.

    src/mame/konami/gticlub.cpp    11 machines
    src/mame/konami/hornet.cpp     72
    src/mame/konami/nwk-tr.cpp     36   (enables the recompiler nowhere)
    src/mame/konami/zr107.cpp      11
    src/mame/sega/model2.cpp       90

Most of the change is recompiler-side, so the split that matters is DRC vs interpreter:
**83 machines run the DRC, 137 the interpreter.** A `machine_config` that calls another
inherits its `enable_recompiler()`, so that set is closed transitively.

## The sets actually worth obtaining

Only these are marked working upstream — a NOT_WORKING set cannot tell you whether a
regression is yours. Tick the box when you have the ROMs.

### DRC — 13 parent sets (these exercise the changed code hardest)

| | set | year | manufacturer | title | driver file |
|---|---|---|---|---|---|
| [ ] | `doa` | 1996 | Tecmo | Dead or Alive (Model 2B, Revision C) | `model2.cpp` |
| [ ] | `gradius4` | 1998 | Konami | Gradius IV: Fukkatsu (ver JAC) | `hornet.cpp` |
| [ ] | `gticlub` | 1996 | Konami | GTI Club: Rally Cote D'Azur (ver EAA) | `gticlub.cpp` |
| [ ] | `gunblade` | 1995 | Sega | Gunblade NY (Revision A) | `model2.cpp` |
| [ ] | `jetwave` | 1996 | Konami | Jet Wave (EAB, Euro v1.04) | `zr107.cpp` |
| [ ] | `midnrun` | 1995 | Konami | Midnight Run: Road Fighter 2 (EAA, Euro v1.11) | `zr107.cpp` |
| [ ] | `nbapbp` | 1998 | Konami | NBA Play By Play (ver UAB) | `hornet.cpp` |
| [ ] | `pltkids` | 1998 | Psikyo | Pilot Kids (Model 2B, Revision A) | `model2.cpp` |
| [ ] | `rchase2` | 1994 | Sega | Rail Chase 2 (Revision A) | `model2.cpp` |
| [ ] | `slrasslt` | 1997 | Konami | Solar Assault (ver UAA) | `gticlub.cpp` |
| [ ] | `vstriker` | 1994 | Sega | Virtua Striker (Revision A) | `model2.cpp` |
| [ ] | `windheat` | 1996 | Konami | Winding Heat (EAA, Euro v2.11) | `zr107.cpp` |
| [ ] | `zerogun` | 1997 | Psikyo | Zero Gunner (Export, Model 2B) | `model2.cpp` |

### Interpreter — 6 parent sets (cover the non-DRC half of `sharcops.hxx`)

| | set | year | manufacturer | title | driver file |
|---|---|---|---|---|---|
| [ ] | `daytona` | 1994 | Sega | Daytona USA (Revision A) | `model2.cpp` |
| [ ] | `hangplt` | 1997 | Konami | Hang Pilot (ver JAB) | `gticlub.cpp` |
| [ ] | `motoraid` | 1997 | Sega | Motor Raid - Twin | `model2.cpp` |
| [ ] | `vcop` | 1994 | Sega | Virtua Cop (Revision B) | `model2.cpp` |
| [ ] | `vcop2` | 1995 | Sega | Virtua Cop 2 | `model2.cpp` |
| [ ] | `vf2` | 1994 | Sega | Virtua Fighter 2 (Version 2.1) | `model2.cpp` |

Several of these need a BIOS set as well: the Model 2A/B boards expect `model2` /
`model2b`, and the Konami boards want their own.

## The rest of the roster, for completeness

These are the SHARC parent sets MAME already marks NOT_WORKING. They are listed so the
roster is complete, not because they are useful evidence — a machine that does not run
before the change cannot show that it still runs after it.

### DRC, NOT_WORKING — 11 sets

| | set | year | manufacturer | title | driver file |
|---|---|---|---|---|---|
| [ ] | `dynabb` | 1996 | Sega | Dynamite Baseball | `model2.cpp` |
| [ ] | `dynabb97` | 1997 | Sega | Dynamite Baseball 97 (Revision A) | `model2.cpp` |
| [ ] | `fvipers` | 1995 | Sega | Fighting Vipers (Revision D) | `model2.cpp` |
| [ ] | `indy500` | 1995 | Sega | INDY 500 Twin (Revision A, Newer) | `model2.cpp` |
| [ ] | `lastbrnx` | 1996 | Sega | Last Bronx (Export, Revision A) | `model2.cpp` |
| [ ] | `powsled` | 1996 | Sega | Power Sled (Slave, Revision A) | `model2.cpp` |
| [ ] | `schamp` | 1996 | Sega | Sonic Championship (USA) | `model2.cpp` |
| [ ] | `sgt24h` | 1996 | Jaleco | Super GT 24h | `model2.cpp` |
| [ ] | `terabrst` | 1998 | Konami | Teraburst (1998/07/17 ver UEL) | `hornet.cpp` |
| [ ] | `thunderh` | 1997 | Konami | Operation Thunder Hurricane (ver EAA) | `gticlub.cpp` |
| [ ] | `von` | 1995 | Sega | Cyber Troopers Virtual-On - Twin (Export) | `model2.cpp` |

### Interpreter, NOT_WORKING — 21 sets

| | set | year | manufacturer | title | driver file |
|---|---|---|---|---|---|
| [ ] | `airwlkrs` | 1997 | Data East Corporation | Air Walkers | `model2.cpp` |
| [ ] | `bel` | 1997 | Sega / EPL Productions | Behind Enemy Lines | `model2.cpp` |
| [ ] | `desert` | 1994 | Sega / Martin Marietta | Desert Tank | `model2.cpp` |
| [ ] | `dynamcop` | 1998 | Sega | Dynamite Cop (Export, Model 2A) | `model2.cpp` |
| [ ] | `hotd` | 1997 | Sega | The House of the Dead (Revision A) | `model2.cpp` |
| [ ] | `hpyagu98` | 1998 | Deniam | Hanguk Pro Yagu 98 | `model2.cpp` |
| [ ] | `manxtt` | 1995 | Sega | Manx TT Superbike - DX/Twin (Revision D) | `model2.cpp` |
| [ ] | `overrev` | 1997 | Jaleco | Over Rev (Model 2C, Revision A) | `model2.cpp` |
| [ ] | `racingj` | 1998 | Konami | Racing Jam (GQ676UAC) | `nwk-tr.cpp` |
| [ ] | `racingj2` | 1998 | Konami | Racing Jam: Chapter II (GQ888UAA) | `nwk-tr.cpp` |
| [ ] | `rascot2` | 1997 | Sega | Royal Ascot II | `model2.cpp` |
| [ ] | `segawski` | 1997 | Sega | Sega Water Ski (Japan, Revision A) | `model2.cpp` |
| [ ] | `skisuprg` | 1996 | Sega | Sega Ski Super G | `model2.cpp` |
| [ ] | `skytargt` | 1995 | Sega | Sky Target | `model2.cpp` |
| [ ] | `srallyc` | 1995 | Sega | Sega Rally Championship - Twin/DX (Revision C) | `model2.cpp` |
| [ ] | `sscope` | 1999 | Konami | Silent Scope (ver UAD, Ver 1.33) | `hornet.cpp` |
| [ ] | `sscope2` | 2000 | Konami | Silent Scope 2 : Dark Silhouette (ver UAD, Ver 1.03) | `hornet.cpp` |
| [ ] | `stcc` | 1996 | Sega | Sega Touring Car Championship (newer) | `model2.cpp` |
| [ ] | `thrilld` | 1998 | Konami | Thrill Drive (UDE) | `nwk-tr.cpp` |
| [ ] | `topskatr` | 1997 | Sega | Top Skater (Export, Revision A) | `model2.cpp` |
| [ ] | `waverunr` | 1996 | Sega | Wave Runner (Japan, Revision A) | `model2.cpp` |

## Reproducing this table

    python3 sharc_users.py ~/compartilhado/mame-pr-kn7000drv upstream/master --roster

Raw output kept beside it as `machines-2026-09-23.txt`; every table above is generated
from that file, so the counts cannot drift from the totals line:

    TOTAL  DRC 83 machines / 24 parent sets (13 working)   INTERP 137 machines / 27 parent sets (6 working)

The script strips comments before searching (`//m_dsp[0]->enable_recompiler();` is
commented out at hornet.cpp:1622), counts only `Type::name(machine_config &`
definitions (an in-class declaration otherwise captures the next function's body and
mis-attributes everything after it), reads each macro to its matching paren rather than
to end of line (a wrapped `GAMEL()` would otherwise lose its title), and closes the
recompiler config set transitively. It prints totals so a miscount is visible: the
roster's 51 parent sets must equal the 24 + 27 in the totals line.
