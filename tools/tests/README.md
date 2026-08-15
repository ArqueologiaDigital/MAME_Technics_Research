# Tests for the tooling itself

Small self-checks for the scripts in `tools/`. These test the *instruments*, not the emulation
— when a rig reports a number, these are what say the rig was actually attached.

| script | question it answers | how to run |
|---|---|---|
| `test_rig_sh.sh` | Does `tools/rig.sh` refuse a missing rig, infer the machine, and **say so when a rig fails to load** instead of leaving a fatal buried in a log? | `./tools/tests/test_rig_sh.sh` (fast, ~1 s) · `--full` also boots MAME for the injection (~2 min) |

## Why `test_rig_sh.sh` exists

Commit `e72a11d` claims `rig.sh` was *"verified by fault injection: a broken rig exits 1 with a
named diagnosis"*. That injection was a one-line invalid-Lua file in session scratch, which is
not storage — the claim would have outlived its evidence within the day. This is the same
injection, repeatable, and it generates the broken rig itself rather than parking a
permanently-broken `.lua` in `tools/rigs/` for the index to list.

Measured 2026-08-15, and the reason the check is worth having: MAME does **not** quietly run on
without its autoboot script. It exits `rc=3` with
`Fatal error: Error loading autoboot script …`. `rig.sh`'s job is to surface that as one line
rather than something you have to go read a log to discover.

Last run: **4 passed, 0 failed** (`--full`).
