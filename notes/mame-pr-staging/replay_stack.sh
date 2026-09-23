#!/bin/bash
# Fold this session's polish and review fixes into the commits that own each file.
#
# QUESTION IT ANSWERS
#   "The work is one flat set of worktree edits; the PR is an 11-commit stack.
#    How does each edit reach the commit that introduced the code it touches?"
#
#   Files owned by exactly one commit are replaced wholesale from final2/.
#   kn7000.cpp spans five commits, so each of its five versions is rebuilt by
#   replaying the harvested (old, new) pairs -- see replay_polish.py, whose
#   --selftest is the positive control that the replay is complete.
#
# PASS  every commit still builds (swept afterwards) and the tip's tree is
#       identical to the pre-replay worktree.
set -euo pipefail
S=~/compartilhado/mame-pr-kn7000drv-staging/final2
R=~/compartilhado/mame-pr-kn7000drv-staging/replay_polish.py
cd ~/compartilhado/mame-pr-kn7000drv

declare -A OWN=(
  [94aaed10c1b]="src/devices/cpu/mn10300/mn10300.cpp src/devices/cpu/mn10300/mn10300.h"
  [62e66b54b83]="src/devices/cpu/sharc/sharc.cpp src/devices/cpu/sharc/sharc.h src/devices/cpu/sharc/sharcdrc.cpp"
  [b1e19b95e01]="src/mame/matsushita/kn6000_cpanel.cpp src/mame/matsushita/kn6000_cpanel.h src/mame/matsushita/kn7000_cpanel.cpp src/mame/matsushita/kn7000_cpanel.h src/mame/matsushita/kn_cpanel.cpp src/mame/matsushita/kn_cpanel.h"
  [efcbb3c0ccf]="src/mame/matsushita/kn6000_tonegen.cpp src/mame/matsushita/kn6000_tonegen.h src/mame/matsushita/kn7000_tonegen.cpp src/mame/matsushita/kn7000_tonegen.h src/mame/matsushita/kn_tonegen.cpp src/mame/matsushita/kn_tonegen.h"
  [50e43616968]="src/mame/layout/kn7000.lay"
)
KN=(d9b4ba6c117 9f2f72ba9a8 bcf33138beb 24d6ccb1459 9582437bf1e)

echo "== stashing the worktree =="
git stash push -u -m replay-stack >/dev/null

export GIT_SEQUENCE_EDITOR="sed -i 's/^pick/edit/'"
git rebase -i upstream/master >/dev/null 2>&1 || true

while true; do
	sha=$(git log -1 --format=%h)
	subj=$(git log -1 --format=%s)
	orig=$(git log -1 --format=%h "$(git rev-parse HEAD)")
	# match by subject, since rewriting changes the sha as we go
	for k in "${!OWN[@]}"; do
		if [ "$(git log -1 --format=%s "$k")" = "$subj" ]; then
			for f in ${OWN[$k]}; do cp "$S/$(basename "$f")" "$f"; done
			echo "  $subj <- $(echo "${OWN[$k]}" | wc -w) file(s)"
		fi
	done
	for k in "${KN[@]}"; do
		if [ "$(git log -1 --format=%s "$k")" = "$subj" ]; then
			python3 "$R" src/mame/matsushita/kn7000.cpp | sed 's/^/  /'
		fi
	done
	git add -A
	git commit --amend --no-edit --quiet
	git rebase --continue >/dev/null 2>&1 || break
	if ! git rebase --show-current-patch >/dev/null 2>&1; then break; fi
done

echo "== restoring the worktree stash =="
git stash pop >/dev/null 2>&1 || echo "  (nothing to pop -- the stash was consumed)"
git log --oneline upstream/master..HEAD | cat
