# Does the SHARC recompiler agree with the interpreter? (KN7000 effects DSP)

**Why this exists.** Two commits of the MAME submission are titled "make the DRC
agree with the interpreter" — the fixed-point multiplier/MAC family and
`MODE1.ALUSAT`. MAME's lead maintainer is independently investigating
interpreter/recompiler divergence in the same core
([mamedev/discussions#257](https://github.com/orgs/mamedev/discussions/257),
February 2026, Racing Jam on NWK-TR), so a PR touching it should arrive with the
A/B already run rather than have a reviewer run it.

## Method

`../dsp-frame-budget/chord_harness.lua` holds a C-major chord on the key bed, so
the DSP has real signal (RULE 12), and the window before the press is the
no-stimulus null (RULE 13). The 21065L's DRC is opt-in per driver
(`m_dsp->enable_recompiler()`, kn7000.cpp) and honours MAME's `-nodrc`.

```sh
PRESS_AT=18 STOP_AT=27 ./kn kn7000 -rompath <romsets> -window -nothrottle \
    [-nodrc] -autoboot_script chord_harness.lua -str 30 -wavwrite out.wav
```

## Result, 2026-09-23

| run | wall | WAV md5 | notes-window RMS |
|---|---:|---|---:|
| DRC (as shipped) | 35.3 s | `ecde0b330edd` | 618.2 |
| DRC, every compute op forced through the interpreter | 49.7 s | `ecde0b330edd` | 618.2 |
| interpreter (`-nodrc`) | 59.9 s | `0ab367478063` | 561.3 |

Both modes are bit-deterministic — each md5 reproduced on a repeat run.

**The recompiler and the interpreter do not produce the same audio.** 854,958 of
3,888,003 samples differ (22.0%), max |delta| 10249, first difference at
t=18.066 s — 0.05 s after the chord starts. Before the press the two agree
exactly (null RMS 46.6 in both), so the divergence appears only once the DSP has
signal to process.

## Where it is NOT

**Not in the compute ops this submission adds.** The middle row is the
experiment: a diagnostic routed *every* compute op through the interpreter's own
`COMPUTE()` from inside the DRC. The audio stayed **byte-identical to native
DRC** and still differed from `-nodrc`. So the arithmetic the recompiler
generates already matches the interpreter's for every op this program executes —
including the fixed-point multiplier/MAC family and the ALUSAT clamp the two
commits add.

*Positive control for that row:* forcing the fallback cost **41% wall clock**
(35.3 s → 49.7 s), which is how we know the diagnostic actually engaged rather
than silently not firing. An unchanged md5 from a diagnostic that did nothing
would look exactly the same.

**Not in the frontend change either.** This submission replaces the loop-map's
hardcoded `l2 != 0x1` with `l2 != m_pm_page`, where
`m_pm_page = internal_ram_base() >> 17`. For the 2106x parts that is
`0x20000 >> 17 == 1` — the same literal, so every existing driver is unchanged by
construction.

## What that leaves

The difference is in how the recompiler *runs* the program — block boundaries and
the resulting interaction timing — not in its ALU. Which is where
[#257](https://github.com/orgs/mamedev/discussions/257) had already arrived from
a completely different direction:

> "All the differences seem to be in values it reads from the Voodoo... it's
> looking even more like it's something to do with how the SHARC communicates
> with the outside world, rather than a SHARC ALU emulation bug."

This is an independent reproduction of that conclusion on a second board and a
wholly different workload — an arranger keyboard's effects kernel rather than a
racing game's 3D pipeline — with the compute path excluded by construction rather
than by inspection. Offered to that discussion as data.

## Which existing machines execute the code this PR modifies

`sharc_users.py` enumerates them. The submission MODIFIES exactly one piece of
shared code -- `sharc.cpp/.h`, `sharcdrc.cpp`, `sharcfe.cpp/.h`, `sharcops.hxx`
-- so the blast radius is every machine with an ADSP2106x. Five driver files:
`konami/gticlub.cpp`, `konami/hornet.cpp`, `konami/nwk-tr.cpp`,
`konami/zr107.cpp`, `sega/model2.cpp`. **220 machines, 51 parent sets.**

```sh
python3 notes/sharc-drc-parity/sharc_users.py ~/compartilhado/mame-pr-kn7000drv upstream/master
```

The split that matters is whether the machine runs the RECOMPILER, since most of
the changes are recompiler-side. `enable_recompiler()` is opt-in per machine
config and inherited by configs that chain to one.

| | machines | parent sets | of which working |
|---|---:|---:|---:|
| DRC | 83 | 24 | **13** |
| interpreter only | 137 | 27 | 6 |

**The 13 working DRC parent sets** — the only ones where a regression would show
as changed behaviour rather than as an already-broken machine:

| driver | sets |
|---|---|
| `konami/gticlub.cpp` | `gticlub` `slrasslt` |
| `konami/hornet.cpp` | `gradius4` `nbapbp` |
| `konami/zr107.cpp` | `jetwave` `midnrun` `windheat` |
| `sega/model2.cpp` | `doa` `gunblade` `pltkids` `rchase2` `vstriker` `zerogun` |

Working interpreter-only sets, for the `sharcops.hxx` side: `hangplt`,
`daytona`, `motoraid`, `vcop`, `vcop2`, `vf2`.

`nwk-tr.cpp` calls `enable_recompiler()` **nowhere** — which is consistent with
[#257](https://github.com/orgs/mamedev/discussions/257), where the maintainer
turns it on by hand for Racing Jam to see the bug.

### Three traps the script exists to avoid

Each of these produced a wrong list before it was handled, and the wrong list
would have sent somebody hunting the wrong ROMs:

1. An in-class **declaration** `void foo(machine_config &) ATTR_COLD;` matches a
   naive "definition" regex; brace-matching from it then captures the *next*
   function's body and mis-attributes every call in it. Only `Type::name(` counts.
2. `hornet.cpp:1622` is `//m_dsp[0]->enable_recompiler();` -- **commented out**.
   Counting it moved the whole `sscope` family into the DRC column.
3. A config that calls another config inherits its recompiler setting, so the set
   must be closed transitively -- that is how `gradius4` (via `hornet_x76`) and
   nine `model2b` variants get there.

The script cross-checks itself: the number of stripped `enable_recompiler()` call
sites must equal the number of configs it found them in, per file.

## Consequence for the submission's wording

The two commits make the recompiler's **arithmetic** agree with the interpreter.
They do not make the machine's **output** agree, because something outside the
ALU diverges. The PR description says that, in those terms.

One arithmetic divergence remains and is documented at its site: Fixed-point
Dual Add/Subtract under ALUSAT OR-merges the two halves' flags before the
subtract half saturates, so its AN/AZ can read the unsaturated sign
(`Rx=0x7FFFFFFF, Ry=0xFFFFFFFF` gives AN=1 against the interpreter's 0). The forced-
fallback row shows this workload does not exercise it — otherwise that row could
not have matched native DRC to the byte.
