# Did the submission change any existing SHARC machine? (2026-09-23)

Everything here was produced by the scripts one directory up. Nothing was typed by hand.

## What was compared

Three binaries, all built from the same worktree with the same five SHARC drivers
(`SOURCES=konami/gticlub.cpp,konami/hornet.cpp,konami/nwk-tr.cpp,konami/zr107.cpp,sega/model2.cpp`):

| binary | from | built by |
|---|---|---|
| `mame-sharc-base`   | `upstream/master` = `ae30b778cae`      | `build_pair.sh` |
| `mame-sharc-pr`     | `technics-kn7000-driver-final` = `743f631e796` | `build_pair.sh` |
| `mame-sharc-seeded` | the PR tip with the ALUSAT **gate inverted** | `build_seed1.sh` |
| `mame-sharc-seed2`  | the PR tip with the ALUSAT **clamp value corrupted** | `build_seed2.sh` |

Each machine is run for 4500 frames on each binary and its framebuffer is dumped at
frames 300, 900, 1800, 2700, 3600 and 4500 (`ab_tap.lua`), then compared byte for byte
(`ab_run.sh`). Both binaries get the same ROMs, the same empty cfg/nvram and the same
options.

## The instrument was checked before it was believed

    determinism    gticlub twice on the base binary : MATCH (6 frames)
    discrimination gticlub vs slrasslt              : DIFFERS at all 6 marks

The first says MAME is run-to-run deterministic here; without it every MATCH below
would be noise. The second says the comparison can tell two machines apart; without it
a MATCH would be vacuous. `ab_run.sh` stops if either fails, and both did fail once
during setup: at marks 120 and 240 gticlub and slrasslt are still drawing the same
blank screen, and the discrimination control caught it. The marks were moved out.

## Result

    base vs PR      6 of 6 machines MATCH at all 6 marks
    base vs seed1   gticlub  DIFFERS at 5 of 6 marks
                    slrasslt DIFFERS at 5 of 6 marks
                    jetwave  DIFFERS, then stops producing frames entirely
                    midnrun  DIFFERS, then stops producing frames entirely
                    gradius4 MATCH
                    nbapbp   MATCH

    PR vs seed2     6 of 6 machines MATCH at all 6 marks

So a defect seeded into the very code the submission adds changes what four of the six
machines draw — two of them into a hang. The submission's own version changes nothing.

The two seeds say different things, which is why there are two. **Seed 1** inverts the
gate, so it saturates whenever the mode bit is CLEAR: it differs, which proves these
machines really do execute overflowing fixed-point ALU ops and that the A/B can see
into that code. **Seed 2** leaves the gate exactly as the submission writes it and
corrupts only the value it clamps to: it matches, which says the gate itself never
opens. Seed 1 alone would not have distinguished "the tail is correct" from "the tail
never runs".

⚠ `ab-pr-vs-seed2.log` was written before `ab_run.sh` took `AB_LABEL_A`/`AB_LABEL_B`,
so its columns read `base_exit` / `pr_exit`; they are the PR binary and seed 2.

## Why nothing changed, measured rather than inferred

`alusat_probe.lua` reads MODE1 off every SHARC once per frame for 4500 frames:

    gticlub   :dsp1  MODE1_or=00001000  ALUSAT_frames=0
    slrasslt  :dsp1  MODE1_or=00001000  ALUSAT_frames=0
    gradius4  :dsp1  MODE1_or=00001000  ALUSAT_frames=0
    nbapbp    :dsp1  MODE1_or=00001000  ALUSAT_frames=0
    jetwave   :dsp   MODE1_or=00001078  ALUSAT_frames=0
    midnrun   :dsp   MODE1_or=00001000  ALUSAT_frames=0

`MODE1_or` is the OR of every value seen, so a probe that saw no traffic at all would
be distinguishable from one that saw traffic without the bit — jetwave exercises four
mode bits, and still never `MODE1_ALUSAT` (0x2000, sharc.h:203).

**MODE1.ALUSAT is never set on any of these machines**, so the saturation tail the
submission adds cannot fire, and the four other SHARC commits implement opcodes that
upstream reaches only through `generate_unimplemented_compute` — which threw
`emu_fatalerror` before, so no working machine executes them either. The match is
explained, not merely observed.

Sampling is once per frame, so a bit set and cleared inside a single frame would be
missed. That is a real limit of this probe: the claim is "never observed set at a frame
boundary in 4500 frames", not "provably never set".

## What this does NOT cover

* The six Model 2 sets (`doa gunblade pltkids rchase2 vstriker zerogun`) need the
  `segabill` device romset — one 64 KiB file, `epr-18022.ic2` — which is not in hand.
* None of the six working INTERPRETER sets (`hangplt daytona motoraid vcop vcop2 vf2`)
  are in hand, so the interpreter half of `sharcops.hxx` has not been run on a real
  machine.
* `windheat`, the thirteenth DRC set, is not in hand.
* All six machines stop at a POST prompt — gticlub on "DEVICE ERROR (STEERING WHEEL)",
  gradius4 on "RTC CHECKSUM ERROR!" — so this measures boot and POST, not attract mode
  or gameplay. Asserting the service inputs (`AB_PRESS`) moved gradius4 into the test
  menu but did not get gticlub past its analog-input check.
