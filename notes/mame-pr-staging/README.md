# How the MAME pull-request stack is built

The KN7000 upstream submission is not a branch anyone edits by hand. It is a
**function** of three inputs — the original feature commits, a set of polish
scripts, and the canonical polished sources — replayed from scratch every time
anything changes. This directory is that machinery, kept here because the
overlay repo is the only permanent home it has; it lives and runs in a scratch
worktree (`~/compartilhado/mame-pr-kn7000drv-staging`) which is not versioned.

**Why a replay instead of editing the branch.** `kn7000.cpp` is split across five
commits. A polish pass rewrites the very lines later commits use as diff context,
so replaying the original diffs conflicts. Instead, for each commit: check out
that commit's **tree**, apply the polish deterministically, re-commit with the
original message and author. Every commit's content is a pure function of
(original tree, polish pairs), so nothing can half-apply.

## The pipeline, in order

| step | script | what it does |
|---|---|---|
| 1 | `replay_polish.py` | harvests the `(old, new)` pairs by `exec`-ing every polish script with `edit()`/`edit_all()`/`cut()` stubbed, and applies them to one `kn7000.cpp` |
| 2 | `rebuild_stack.sh` | replays the whole stack onto `upstream/master` as branch `polish-replay` |
| 3 | `split_sharc.py` | cuts the single SHARC commit into five cumulative stages against pristine upstream, so the shared-core changes are reviewable apart from the new device |
| 4 | `sweep_build.sh` | builds **every** commit, so the history is bisectable |
| 5 | `refresh_sibling_branches.sh` | re-cuts the per-feature sibling branches from the rebuilt stack |

```sh
cd ~/compartilhado/mame-pr-kn7000drv
python3 replay_polish.py --selftest <head kn7000.cpp> <polished kn7000.cpp>
bash rebuild_stack.sh
bash sweep_build.sh          # ~1-2 h; writes /tmp/sweep_out.txt
```

## The positive control, and why it is the important part

`replay_polish.py --selftest` takes `kn7000.cpp` as of the **last** commit of the
stack, applies every harvested pair, and requires the result to be
**byte-identical** to the polished working-tree file. If that fails, the harvest
is incomplete and no layer below it can be trusted. It prints how many pairs
fired, because a pair that silently matches nothing is the failure mode this
whole design exists to catch.

`rebuild_stack.sh` is checked the same way: the rebuilt tip's files must equal the
files that were actually built and run. A replay that "looks right" is not a
replay.

⚠ Two traps that cost real time here, both now encoded in the scripts:

* **`REGENIE=1` is not enough for a per-commit sweep.** The static archives must
  be deleted too. A commit that introduces a device otherwise links against a
  `liboptional.a` that make considers up to date because the device's own object
  is *older* than the archive — measured as eleven `undefined reference to
  upd765_family_device` on three consecutive commits.
* **`OWNED` must be built from the commits, not globbed off the index.** Globbing
  also catches the upstream SHARC files, which silently moves the 21065L work
  into whichever commit ran first.

## The polish scripts

Each is a small module with a docstring stating the **question it answers** and
its pass criterion, applied through `edit(path, [(old, new), ...])` so
`replay_polish.py` can harvest it. The list `replay_polish.SCRIPTS` is the
authoritative order — a script not in it does not run.

The ones carrying measurements rather than taste:

| script | the measurement behind it |
|---|---|
| `relocate_peripheral_docs.py` | comment-line density per header against upstream (`notes/pr-review-probes-2026-09-23/`) |
| `drop_dividers.py` | the null: zero section dividers in `mn10200.h`, `m6502.h`, `sh4.h`, `upd78k0.h`, `h8.h` |
| `drop_firmware_addresses.py` | five of eight hardcoded firmware addresses were replaceable (`notes/irq-vector-probes/`) |
| `mn10300_ivar.py` | IVAR0-IVAR6 are CPU registers, not board policy (`notes/irq-vector-probes/vector_table_layout.py`) |
| `tg_voice_record_comment.py` | the sample roots are in the **dumped** table ROM (`notes/tg-pitch-probes/`) |
| `dsp_clock_60mhz.py` | 60 MHz is byte-identical to 66 MHz, and a 6 MHz control proves the harness sees a too-slow clock |
| `sharc_sram_extent.py` | the data region is sized from what the effect program reaches (`0x1FFE6`), not from an assumed geometry |
| `trim_internal_map_comment.py` | archaeology belongs in the PR description, flagged on #15919 and #16204 |

## What is deliberately not here

`final2/` — the canonical polished copies of every source file, which
`rebuild_stack.sh` copies into each commit. It is ~1.3 MB of files that are
already in git, as the PR branch's own content: reconstruct it by checking out
the branch tip and copying the sources out. `final/`, `fixed/` and `layers/` are
earlier snapshots of the same, kept in the scratch worktree only.
