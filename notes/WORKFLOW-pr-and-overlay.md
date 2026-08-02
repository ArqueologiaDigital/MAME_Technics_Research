# Workflow: upstream PR staging and leading-edge overlay, always in sync

**Felipe's rule (2026-08-02):** *"Anything we do should always immediately affect both."*
Both jobs run continuously and in parallel. Neither waits for the other.

## The layout — three places, and nothing ever switches branch

| | path | branch | what it is |
|---|---|---|---|
| **A** | `~/compartilhado/mame` | `kn7000-base` | the overlay's MAME **base tree** |
| **B** | `~/compartilhado/mame-pr` | `technics-rom-record` | upstream **PR staging** |
| **C** | `~/compartilhado/kn7000_mame/src` | (own repo) | overlay-only files, copied over the build tree |

**A and B are git worktrees of one clone.** Both are checked out simultaneously, sharing one
object store, so a commit in either is instantly visible to the other via `git`.

> ### ⛔ Never `git checkout` in A or B
> That is what the worktrees exist to prevent. `build.sh` rsyncs **A** wholesale into the build
> tree, so whatever branch A sits on *becomes the emulator*. The PR branch carries its own
> `src/mame/matsushita/kn7000.cpp` — a ROM-record skeleton with no CPU — plus its own `mame.lst`
> entries. Building from it silently produces a driver that is not this project's.
> **This happened on 2026-08-02.** `build.sh` now refuses unless A is on `kn7000-base`
> (override: `ALLOW_ANY_BASE=1`, and you should not need it).

## The one command

```sh
cd ~/compartilhado/kn7000_mame && ./tools/sync-check.sh
```

Run it **before building and before submitting**. Exit 0 means in sync.

```sh
./tools/sync-check.sh --from-pr   # copy files we authored  B -> A
./tools/sync-check.sh --to-pr     # copy files we authored  A -> B
```

Copying never commits — review with `git diff`, then commit in that worktree.

## Why it does not diff byte-for-byte

A and B sit on **different upstream bases**: `kn7000-base` is a long-lived fork point,
`technics-rom-record` is cut from current `upstream/master`. Shared upstream files therefore
differ by a hundred-odd commits of history that has nothing to do with us. Demanding
byte-equality would report permanent drift — **a check that can never pass is a check nobody
runs**, and we have been bitten by exactly that failure mode elsewhere in this project.

So the criterion is *presence of our work*, split by how the file came to be:

- **Files we patched** (upstream files — `intelfsh.*`, `bus.lua`): check that our **marker
  symbol** is present in both. Propagate these by **`git cherry-pick -x <sha>`**, not by copying,
  so the history stays honest and the shared object store makes it a one-liner.
- **Files we authored** (wholly ours — `hdsx3.*`, `kn6000_expansion.*`): must be **byte-identical**
  wherever both trees carry them. `--from-pr` / `--to-pr` handle these.
- **Divergent by design**: `matsushita/kn7000.cpp`, `mame.lst`, `cpu.lua`. **Never sync.** They are
  listed in the script so nobody "fixes" them.

## Doing a piece of work

**Work that belongs to both** (a core device, a bus device, a shared fix):

1. Do it in whichever tree you are already in.
2. Commit it there.
3. Propagate immediately — `git -C <other> cherry-pick -x <sha>` for patches, or
   `./tools/sync-check.sh --from-pr|--to-pr` for authored files.
4. `./tools/sync-check.sh` → expect `IN SYNC`.

**Work that belongs to only one side** (driver behaviour, ROM declarations): do it in that tree
and add it to `DIVERGENT` in the script if it is a new file that will now legitimately differ.

## No-data-loss properties

- Worktrees never require a checkout, so **no dirty tree is ever stashed or overwritten** to
  switch jobs. (The one time a `git stash` was used here it popped an unrelated stash from
  another branch's work — worktrees remove the reason to reach for it at all.)
- `sync-check.sh` warns when either tree has uncommitted changes before copying.
- Every propagation is a commit or a reviewable working-tree change; nothing is applied silently.
- Both branches live in one clone, so a lost directory loses no history.

## Build discipline

```sh
cd ~/compartilhado/kn7000_mame
./tools/sync-check.sh && ./build.sh && ./tools/publish-binary.sh
```

- `build.sh` returns **0 even on compile failure** — always `grep 'error:'` the log and check the
  binary is executable and >70 MB.
- The binary is written **during** the link: a size around 50 MB with no execute bit means you
  looked mid-write, not that the build shrank. Re-check before concluding anything.
- `build.sh` does **not** publish. `tools/publish-binary.sh` is a separate step, and the published
  copy was found stale on 2026-08-02 because of exactly that.
- Adding a new `#include` to a driver needs `REGENIE=1` (build.sh already passes it).
