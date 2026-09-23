# Which existing MAME machines does the KN7000 submission put at risk?

Generated 2026-09-24 from `machines-2026-09-24.txt`; branch `technics-kn7000-driver-final`
vs `upstream/master` (`ae30b778cae`). Every table below is produced from that file, so the
counts cannot drift from its totals line.

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

## ⚠ Correction, 2026-09-24: not every machine in these files has a SHARC

An earlier revision of this file said 220 machines. That counted every machine in a FILE
that instantiates a SHARC. `src/mame/sega/model2.cpp` holds four board generations and
`ADSP21062(config, ...)` appears **once** in it (model2.cpp:2840, a `model2b_state`
config): Model 2O and 2A use a Fujitsu TGP, Model 2C a TGPx4. Only Model 2B has a SHARC.

This was caught by measurement, not by re-reading. `alusat_probe.lua` reported

    daytona  NO DEVICE EXPOSES MODE1 -- the probe saw nothing, which is not a negative result

on `daytona`, `motoraid`, `vcop`, `vcop2` and `vf2` — which is why the probe prints that
instead of nothing. `sharc_users.py` now requires the machine's own config to instantiate
an ADSP21062, closed transitively, and the seeded-defect run agrees independently: a
defect in SHARC arithmetic leaves all five of those machines untouched.

    == src/mame/konami/gticlub.cpp   11 machines   1 enable_recompiler() call site(s) in 1 config(s)
    == src/mame/konami/hornet.cpp   72 machines   3 enable_recompiler() call site(s) in 3 config(s)
    == src/mame/konami/nwk-tr.cpp   36 machines   0 enable_recompiler() call site(s) in 0 config(s)
    == src/mame/konami/zr107.cpp   11 machines   1 enable_recompiler() call site(s) in 1 config(s)
    == src/mame/sega/model2.cpp   90 machines   1 enable_recompiler() call site(s) in 1 config(s)

    TOTAL  DRC 83 machines / 24 parent sets (13 working)   INTERP 82 machines / 6 parent sets (1 working)
    55 machines in these files have NO SHARC and are excluded

## The sets worth obtaining

Only these are marked working upstream — a NOT_WORKING set cannot tell you whether a
regression is yours. `[x]` = ROMs in hand as of 2026-09-24.

### DRC — 13 parent sets (these exercise the changed code hardest)

| have ROMs | set | year | manufacturer | title | driver file |
|---|---|---|---|---|---|
| [x] | `doa` | 1996 | Tecmo | Dead or Alive (Model 2B, Revision C) | `model2.cpp` |
| [x] | `gradius4` | 1998 | Konami | Gradius IV: Fukkatsu (ver JAC) | `hornet.cpp` |
| [x] | `gticlub` | 1996 | Konami | GTI Club: Rally Cote D'Azur (ver EAA) | `gticlub.cpp` |
| [x] | `gunblade` | 1995 | Sega | Gunblade NY (Revision A) | `model2.cpp` |
| [x] | `jetwave` | 1996 | Konami | Jet Wave (EAB, Euro v1.04) | `zr107.cpp` |
| [x] | `midnrun` | 1995 | Konami | Midnight Run: Road Fighter 2 (EAA, Euro v1.11) | `zr107.cpp` |
| [x] | `nbapbp` | 1998 | Konami | NBA Play By Play (ver UAB) | `hornet.cpp` |
| [x] | `pltkids` | 1998 | Psikyo | Pilot Kids (Model 2B, Revision A) | `model2.cpp` |
| [x] | `rchase2` | 1994 | Sega | Rail Chase 2 (Revision A) | `model2.cpp` |
| [x] | `slrasslt` | 1997 | Konami | Solar Assault (ver UAA) | `gticlub.cpp` |
| [x] | `vstriker` | 1994 | Sega | Virtua Striker (Revision A) | `model2.cpp` |
| [x] | `windheat` | 1996 | Konami | Winding Heat (EAA, Euro v2.11) | `zr107.cpp` |
| [x] | `zerogun` | 1997 | Psikyo | Zero Gunner (Export, Model 2B) | `model2.cpp` |

### Interpreter — 1 parent set

| have ROMs | set | year | manufacturer | title | driver file |
|---|---|---|---|---|---|
| [x] | `hangplt` | 1997 | Konami | Hang Pilot (ver JAB) | `gticlub.cpp` |

`hangplt` is the *only* working machine that runs a SHARC through the interpreter, and it
carries two of them (`:dsp1`, `:dsp2`). It is therefore the entire interpreter data point.

Three **device** romsets are needed on top of the game sets, and none is a BIOS, which is
why none appears as a parent and why reading `GAME(...)` lines cannot find them — only
`-verifyroms` can:

| device set | needed by | file |
|---|---|---|
| `segabill`  | the six Model 2B sets | `epr-18022.ic2` |
| `model1io`  | `daytona` | `epr-14869*.25` |
| `model1io2` | `vcop` | `epr-16891.6` / `epr-18021.6` / `epr-17181.6` |

(`daytona` and `vcop` turned out to have no SHARC, so those two are not needed for this
PR after all — recorded because they were obtained for it.)

## The rest of the roster, for completeness

These are marked NOT_WORKING upstream. A machine that does not run before the change
cannot show that it still runs after it.

### DRC, NOT_WORKING — 11 sets

| have ROMs | set | year | manufacturer | title | driver file |
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

### Interpreter, NOT_WORKING — 5 sets

| have ROMs | set | year | manufacturer | title | driver file |
|---|---|---|---|---|---|
| [ ] | `racingj` | 1998 | Konami | Racing Jam (GQ676UAC) | `nwk-tr.cpp` |
| [ ] | `racingj2` | 1998 | Konami | Racing Jam: Chapter II (GQ888UAA) | `nwk-tr.cpp` |
| [ ] | `sscope` | 1999 | Konami | Silent Scope (ver UAD, Ver 1.33) | `hornet.cpp` |
| [ ] | `sscope2` | 2000 | Konami | Silent Scope 2 : Dark Silhouette (ver UAD, Ver 1.03) | `hornet.cpp` |
| [ ] | `thrilld` | 1998 | Konami | Thrill Drive (UDE) | `nwk-tr.cpp` |

## Result

See [`results-2026-09-24/README.md`](results-2026-09-24/README.md): all 19 machines run
(14 of which have a SHARC) are byte-identical between upstream and the submission, with
three seeded-defect controls and a direct MODE1 read establishing what that is worth.

## Reproducing this

    python3 sharc_users.py ~/compartilhado/mame-pr-kn7000drv upstream/master --roster

The script strips comments before searching (`//m_dsp[0]->enable_recompiler();` is
commented out at hornet.cpp:1622), counts only `Type::name(machine_config &` definitions
(an in-class declaration otherwise captures the next function's body), reads each macro to
its matching paren rather than to end of line (a wrapped `GAMEL()` would otherwise lose
its title), and closes both the recompiler set and the has-a-SHARC set transitively. The
roster's 30 parent sets must equal the 24 + 6 in the totals line.
