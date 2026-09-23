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
regression is yours.

### DRC — 13 parent sets (these exercise the changed code hardest)

| set | year | manufacturer | title |
|---|---|---|---|
| `gticlub`  | 1996 | Konami | GTI Club: Rally Cote D'Azur (ver EAA) |
| `slrasslt` | 1997 | Konami | Solar Assault (ver UAA) |
| `gradius4` | 1998 | Konami | Gradius IV: Fukkatsu (ver JAC) |
| `nbapbp`   | 1998 | Konami | NBA Play By Play (ver UAB) |
| `jetwave`  | 1996 | Konami | Jet Wave (EAB, Euro v1.04) |
| `midnrun`  | 1995 | Konami | Midnight Run: Road Fighter 2 (EAA, Euro v1.11) |
| `windheat` | 1996 | Konami | Winding Heat (EAA, Euro v2.11) |
| `doa`      | 1996 | Tecmo  | Dead or Alive (Model 2B, Revision C) |
| `gunblade` | 1995 | Sega   | Gunblade NY (Revision A) |
| `pltkids`  | 1998 | Psikyo | Pilot Kids (Model 2B, Revision A) |
| `rchase2`  | 1994 | Sega   | Rail Chase 2 (Revision A) |
| `vstriker` | 1994 | Sega   | Virtua Striker (Revision A) |
| `zerogun`  | 1997 | Psikyo | Zero Gunner (Export, Model 2B) |

### Interpreter — 6 parent sets (cover the non-DRC half of `sharcops.hxx`)

| set | year | manufacturer | title |
|---|---|---|---|
| `hangplt`  | 1997 | Konami | Hang Pilot (ver JAB) |
| `daytona`  | 1994 | Sega   | Daytona USA (Revision A) |
| `motoraid` | 1997 | Sega   | Motor Raid - Twin |
| `vcop`     | 1994 | Sega   | Virtua Cop (Revision B) |
| `vcop2`    | 1995 | Sega   | Virtua Cop 2 |
| `vf2`      | 1994 | Sega   | Virtua Fighter 2 (Version 2.1) |

Several of these need a BIOS set as well (`vf2` and the other Model 2A/B boards expect
`model2` / `model2b`; the Konami boards want their own).

## Reproducing this table

    python3 sharc_users.py ~/compartilhado/mame-pr-kn7000drv upstream/master

Raw output kept beside it as `machines-2026-09-23.txt`. The script strips comments before
searching (`//m_dsp[0]->enable_recompiler();` is commented out at hornet.cpp:1622), counts
only `Type::name(machine_config &` definitions (an in-class declaration otherwise captures
the next function's body), and closes the config set transitively. It prints totals so a
miscount is visible.
