# Did the submission change any existing SHARC machine? (2026-09-24)

Everything here was produced by the scripts one directory up. Nothing was typed by hand.

## Binaries

All built from the same worktree with the same five drivers
(`SOURCES=konami/gticlub.cpp,konami/hornet.cpp,konami/nwk-tr.cpp,konami/zr107.cpp,sega/model2.cpp`):

| binary | what it is | built by |
|---|---|---|
| base   | `upstream/master` = `ae30b778cae` | `build_pair.sh` |
| pr     | `technics-kn7000-driver-final` = `743f631e796` | `build_pair.sh` |
| seed 1 | pr, MODE1.ALUSAT **gate inverted** (fires when the bit is clear) | `build_seed1.sh` |
| seed 2 | pr, ALUSAT **clamp value** corrupted, gate untouched | `build_seed2.sh` |
| seed 3 | `Rn = Rx + Ry` **+1 in both engines** — an instrument test, not a change test | `build_seed3.sh` |

Seed 3 perturbs `compute.hxx`, which the submission does **not** touch. That is the point:
it asks whether this harness can see SHARC arithmetic on a given machine at all.

Each machine runs 4500 frames per binary; the framebuffer is dumped at frames 300, 900,
1800, 2700, 3600, 4500 (`ab_tap.lua`) and compared byte for byte (`ab_run.sh`). Identical
ROMs, identical empty cfg/nvram, identical options on both sides.

## Controls, checked before anything was believed

    determinism    gticlub twice on the base binary : MATCH (6 frames)
    discrimination gticlub vs slrasslt              : DIFFERS at all 6 marks

`ab_run.sh` stops if either fails. The discrimination control did fail once during setup —
at marks 120 and 240 both machines were still drawing the same blank screen — and the
marks were moved out until it passed.

## Result

| machine | has SHARC | base vs PR | seed 1 (ALUSAT gate) | seed 3 (fixed add) |
|---|---|---|---|---|
| `gticlub` | yes | MATCH | DIFFERS | DIFFERS |
| `slrasslt` | yes | MATCH | DIFFERS | DIFFERS |
| `gradius4` | yes | MATCH | MATCH | DIFFERS |
| `nbapbp` | yes | MATCH | MATCH | DIFFERS |
| `jetwave` | yes | MATCH | DIFFERS | DIFFERS |
| `midnrun` | yes | MATCH | DIFFERS | DIFFERS |
| `windheat` | yes | MATCH | DIFFERS | DIFFERS |
| `doa` | yes | MATCH | MATCH | DIFFERS |
| `gunblade` | yes | MATCH | MATCH | DIFFERS |
| `pltkids` | yes | MATCH | MATCH | MATCH |
| `rchase2` | yes | MATCH | MATCH | DIFFERS |
| `vstriker` | yes | MATCH | MATCH | DIFFERS |
| `zerogun` | yes | MATCH | MATCH | DIFFERS |
| `hangplt` | yes | MATCH | MATCH | DIFFERS |
| `daytona` | **no** | MATCH | MATCH | MATCH |
| `motoraid` | **no** | MATCH | MATCH | MATCH |
| `vcop` | **no** | MATCH | MATCH | MATCH |
| `vcop2` | **no** | MATCH | MATCH | MATCH |
| `vf2` | **no** | MATCH | MATCH | MATCH |

**base vs PR: all 19 identical, at every mark.**

## Five of those machines have no SHARC

`daytona`, `motoraid`, `vcop`, `vcop2` and `vf2` are Model 2O/2A/2C — Fujitsu TGP, not an
ADSP-21062 (see the correction in `../ROM-TEST-LIST.md`). Their match is not evidence
about this PR. Two independent measurements say so: `mode1-probe.txt` reports *NO DEVICE
EXPOSES MODE1* for each, and seed 3 — a deliberate defect in SHARC arithmetic — leaves all
five untouched.

So the real coverage is **14 machines**: 13 DRC plus `hangplt`, which runs two SHARCs
through the interpreter and is the only working machine that does.

## What the seeds establish

* **Seed 1** moved 5 of the 14. It lives in `sharcdrc.cpp`, so it *cannot* affect the
  interpreter, and a DRC machine that never overflows a fixed-point ALU op is unmoved too.
  On its own it would have left 9 of the 14 "MATCH" rows with no demonstrated sensitivity.
* **Seed 3** moved 13 of the 14, including `hangplt`. Those machines' framebuffers
  demonstrably respond to SHARC arithmetic, so their agreement between base and PR means
  something.
* **Still blind: `pltkids`.** Neither seed moved it, so this harness has not been shown able to
  detect a SHARC change there, and its "MATCH" should be read as "nothing observed", not as
  "nothing happened".
* **Seed 2** (six machines only, `ab-pr-vs-seed2-clamp-value-6-machines.log`) left the gate
  as the submission writes it and corrupted only the clamped value: no machine changed, so
  the gate never opens.

## Why nothing changed, measured rather than inferred

`alusat_probe.lua` samples MODE1 on every SHARC once per frame for 4500 frames
(`mode1-probe.txt`). Across all 14 SHARC machines, `ALUSAT_frames=0` — `MODE1_ALUSAT`
(0x2000, sharc.h:203) is never observed set. The OR of every value seen is printed too, so
a blind probe is distinguishable from a real zero: the Konami boards show `0x1000`,
jetwave and windheat `0x1078`, the Model 2B boards `0x18000`/`0x10000`.

The saturation tail therefore cannot fire on any of them, and the other SHARC commits
implement opcodes that previously reached `generate_unimplemented_compute`, which threw
`emu_fatalerror` — so no working machine executes those either. The match is explained,
not merely observed.

## Limits worth stating

* Sampling is once per frame: a bit set and cleared inside one frame would be missed. The
  claim is "never observed set at a frame boundary in 4500 frames".
* `pltkids` is not covered by any working sensitivity control.
* All machines stop at a POST prompt — `gticlub` on "DEVICE ERROR (STEERING WHEEL)",
  `gradius4` on "RTC CHECKSUM ERROR!" — so this measures boot and POST, not attract mode
  or gameplay. Asserting the service inputs (`AB_PRESS`) moved gradius4 into the test menu
  but did not get gticlub past its analog check.
* The 10 NOT_WORKING DRC and 5 NOT_WORKING interpreter parent sets were not run.
