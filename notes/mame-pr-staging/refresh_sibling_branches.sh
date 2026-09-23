#!/bin/bash
# Re-cut the two standalone CPU-core branches from the rebuilt stack.
#
# QUESTION IT ANSWERS
#   "The four branches of this submission are supposed to be the same work seen
#    separately. After the stack was rebuilt, are they?"
#
#   technics-mn10300-core and technics-sharc-21065l were each one commit taken
#   from the old stack. The stack has since been cleaned up and the SHARC work
#   split into five, so both are stale -- and they are the branches a CORE
#   maintainer reads, so a stale one is worse than none.
#
#   They are re-cut by cherry-picking the corresponding commits out of the
#   rebuilt stack, which keeps them identical to what the driver branch carries.
#
# PASS  each branch's files are byte-identical to the stack's, per branch.
set -euo pipefail
cd ~/compartilhado/mame-pr-kn7000drv
STACK=technics-kn7000-driver-final

pick () {   # $1 = branch, $2... = commit subjects, in order
	local br="$1"; shift
	git checkout -q -B "$br" upstream/master
	for subj in "$@"; do
		local c
		# `&& echo` is false on the last commit, which under `set -e -o pipefail`
		# would abort the script rather than leave $c empty; the trailing `|| true`
		# keeps the emptiness check below as the thing that decides.
		c=$(git rev-list --reverse "upstream/master..$STACK" | while read -r r; do
			[ "$(git log -1 --format=%s "$r")" = "$subj" ] && echo "$r" || true; done | head -1)
		[ -n "$c" ] || { echo "NO SUCH COMMIT: $subj" >&2; exit 1; }
		git cherry-pick -x "$c" >/dev/null || { echo "PICK FAILED: $subj" >&2; exit 1; }
	done
	printf '%-30s %2d commits  %s\n' "$br" "$(git rev-list --count upstream/master..HEAD)" "$(git rev-parse --short HEAD)"
}

pick technics-mn10300-core "cpu/mn10300: add an execution core"
pick technics-sharc-21065l \
	"cpu/sharc: let a variant place its internal memory elsewhere" \
	"cpu/sharc: run an unimplemented compute op through the interpreter" \
	"cpu/sharc: implement the fixed-point multiplier, signed average and TOGGLE ASTAT" \
	"cpu/sharc: apply MODE1.ALUSAT in the DRC's fixed-point ALU" \
	"cpu/sharc: add the ADSP-21065L"

# Acceptance: compare each branch's commits to the stack's OWN CHANGES, not to the
# stack's tree. The stack's tree at a given commit also carries every earlier
# commit's edits -- scripts/src/cpu.lua is touched by both the MN10300 commit and
# the DRC_CPUS one -- so a tree comparison reports a difference that is not one.
echo "== acceptance: each branch's commits must make the stack's changes =="
fail=0
check () {
	local br="$1"; shift
	local i=0
	for subj in "$@"; do
		i=$((i+1))
		local sc bc
		sc=$(git rev-list --reverse "upstream/master..$STACK" | while read -r r; do
			[ "$(git log -1 --format=%s "$r")" = "$subj" ] && echo "$r" || true; done | head -1)
		bc=$(git rev-list --reverse "upstream/master..$br" | while read -r r; do
			[ "$(git log -1 --format=%s "$r")" = "$subj" ] && echo "$r" || true; done | head -1)
		if [ -z "$bc" ]; then echo "  $br: MISSING $subj"; fail=1; continue; fi
		if diff -q <(git show --format= "$sc") <(git show --format= "$bc") >/dev/null; then
			printf '  %-24s %2d. identical patch  %s\n' "$br" "$i" "$subj"
		else
			printf '  %-24s %2d. PATCH DIFFERS    %s\n' "$br" "$i" "$subj"; fail=1
		fi
	done
}
check technics-mn10300-core "cpu/mn10300: add an execution core"
check technics-sharc-21065l \
	"cpu/sharc: let a variant place its internal memory elsewhere" \
	"cpu/sharc: run an unimplemented compute op through the interpreter" \
	"cpu/sharc: implement the fixed-point multiplier, signed average and TOGGLE ASTAT" \
	"cpu/sharc: apply MODE1.ALUSAT in the DRC's fixed-point ALU" \
	"cpu/sharc: add the ADSP-21065L"

git checkout -q "$STACK"
exit $fail
