# PR branch surgery

## `replay_tonegen_branches.py`

**Question it answers:** can the three KN5000 tone-generator PR branches be rewritten to fix a
commit-message claim and a commit-hygiene defect *without changing what was tested*?

Run on 2026-08-21 against `~/compartilhado/mame-pr-tonegen` to fix two things a reviewer would
have caught:

1. the tone-generator commit message claimed the pitch constants "follow whichever firmware
   revision is selected" -- false, `table_data` carries no `ROM_BIOS` and is one image under all
   eight options;
2. the inter-CPU latch commit added two `abort_timeslice()` calls that the very next commit
   silently removed.

The script rebuilds each branch commit by commit onto a corrected latch commit, taking each
commit's **exact original tree** (`git reset --hard <orig>` then `git reset --soft <new parent>`)
and preserving the original author name, e-mail and date. Only the two message strings change.

**THE SAFETY GATE IS THE POINT.** After rebuilding each branch it prints

    <branch>: <old tip> -> <new tip>  TREE IDENTICAL

by diffing the old tip against the new one. `TREE IDENTICAL` means the end state is byte-identical
to the tree that was actually built and measured, so no measurement has to be repeated. Anything
else prints `*** TREE DIFFERS ***` with the stat, and the result must not be used.

All three branches reported `TREE IDENTICAL`. Old tips were kept as `backup/<branch>` refs.

    python3 tools/pr-branch-surgery/replay_tonegen_branches.py

⚠ It rewrites history in that worktree and hardcodes the commit SHAs it replays, so it is a record
of one operation rather than a general tool. Re-running it after the branches have moved will not
do anything sensible. It is kept because the "TREE IDENTICAL" claim in
`notes/upstream-patches/PR-REVIEW-CONCERNS-kn5000-tonegen.md` is only checkable if the thing that
produced it is here.
