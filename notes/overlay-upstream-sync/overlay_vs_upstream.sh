#!/usr/bin/env bash
# Question answered: which files does this overlay carry that upstream MAME has
# CHANGED since our base branch forked -- i.e. which upstream fixes does an
# overlay build silently revert?
#
# The overlay symlinks its own copy of a file over MAME's (build.sh), so a file
# that upstream fixed after our fork point comes back pre-fix in every overlay
# build, and rebasing the base branch does NOT fix it.
#
#   ./overlay_vs_upstream.sh
#
# Reports, per file: whether upstream has it at all, how many upstream commits
# touched it since the base branch, and the diff size. A file with a non-zero
# commit count is the finding; everything else is noise.
#
# The glob MUST cover .hxx. An earlier pass globbed only *.cpp/*.h/*.lay and
# missed sharcops.hxx, which is where half of #16016 lives.
set -uo pipefail

OVERLAY="${OVERLAY:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
MAME="${MAME:-$HOME/compartilhado/mame}"
BASE="${BASE:-kn7000-base}"
REF="${REF:-upstream/master}"

echo "overlay: $OVERLAY"
echo "base:    $BASE   = $(git -C "$MAME" rev-parse --short=11 "$BASE")"
echo "ref:     $REF    = $(git -C "$MAME" rev-parse --short=11 "$REF")"
echo "fork:    $(git -C "$MAME" log --oneline -1 "$(git -C "$MAME" merge-base "$BASE" "$REF")")"
echo "behind:  $(git -C "$MAME" rev-list --count "$BASE".."$REF")   ahead: $(git -C "$MAME" rev-list --count "$REF".."$BASE")"
echo

printf "%-52s %-9s %-7s %s\n" FILE UPSTREAM DIFF "COMMITS-SINCE-BASE (the finding)"
cd "$OVERLAY"
# every tracked source extension, .hxx included
find src -type f | sort | while read -r f; do
	if ! git -C "$MAME" cat-file -e "$REF:$f" 2>/dev/null; then
		printf "%-52s %-9s\n" "$f" "absent"
		continue
	fi
	d=$(git -C "$MAME" show "$REF:$f" | diff -u - "$f" | grep -c '^[+-]')
	n=$(git -C "$MAME" log --oneline "$BASE..$REF" -- "$f" | wc -l)
	mark=""
	[ "$n" -gt 0 ] && mark="  <== REVERTS: $(git -C "$MAME" log --oneline -1 "$BASE..$REF" -- "$f")"
	printf "%-52s %-9s %-7s %s%s\n" "$f" "present" "$d" "$n" "$mark"
done
