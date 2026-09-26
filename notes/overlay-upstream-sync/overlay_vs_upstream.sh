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
REF="${REF:-upstream/master}"
# The range must start at the point up to which overlay-shared files have been RECONCILED,
# not at the base branch. Rebasing the base empties `kn7000-base..upstream/master` and the
# sweep then reports nothing at all -- a clean bill of health it has not earned, and a gate
# that cannot fail is not a gate. SYNCED-AT is that point, advanced by hand only when every
# file this sweep flags has been dealt with.
BASE="${BASE:-$(cat "$(dirname "${BASH_SOURCE[0]}")/SYNCED-AT")}"

echo "overlay: $OVERLAY"
echo "synced:  $BASE  = $(git -C "$MAME" log --oneline -1 "$BASE")"
echo "ref:     $REF    = $(git -C "$MAME" rev-parse --short=11 "$REF")"
echo "unreconciled upstream commits: $(git -C "$MAME" rev-list --count "$BASE".."$REF")"
echo

printf "%-52s %-9s %-7s %s\n" FILE UPSTREAM DIFF "UNRECONCILED (the finding)"
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
	if [ "$n" -gt 0 ]; then
		# Upstream touched this file after our fork, so the overlay's copy MIGHT revert
		# the change. Decide which by testing whether the commit's own added lines are
		# present in the overlay -- "upstream touched it" is the smoke, this is the fire.
		c=$(git -C "$MAME" log --format=%h -1 "$BASE..$REF" -- "$f")
		missing=0; total=0
		while IFS= read -r l; do
			l=${l#+}
			[ -z "${l// }" ] && continue
			total=$((total+1))
			grep -qF -- "$l" "$f" || missing=$((missing+1))
		done < <(git -C "$MAME" show "$c" -- "$f" | grep '^+' | grep -v '^++')
		if [ "$missing" -gt 0 ]; then
			mark="  <== REVERTS $missing/$total lines of: $(git -C "$MAME" log --oneline -1 "$c")"
		else
			mark="  (ported: all $total lines of $c present)"
		fi
	fi
	printf "%-52s %-9s %-7s %s%s\n" "$f" "present" "$d" "$n" "$mark"
done
