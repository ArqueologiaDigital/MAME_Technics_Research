#!/usr/bin/env bash
# Keep the upstream-PR staging tree and the leading-edge overlay in sync.
#
# THE LAYOUT (three places, never fewer):
#
#   A  ~/compartilhado/mame           @ kn7000-base           the overlay's MAME base tree
#   B  ~/compartilhado/mame-pr        @ technics-rom-record    upstream PR staging
#   C  ~/compartilhado/kn7000_mame/src                         overlay-only files, copied
#                                                              over the build tree by build.sh
#
# A and B are git WORKTREES of one clone, so both are checked out at once and NEITHER EVER
# SWITCHES BRANCH. That is the point: switching used to silently feed PR files into an overlay
# build (the PR branch carries its own matsushita/kn7000.cpp and mame.lst entries). build.sh
# now refuses to build unless MAME_SRC is on kn7000-base.
#
# WHY THIS DOES NOT DIFF FILES BYTE-FOR-BYTE
# -----------------------------------------
# A and B sit on DIFFERENT upstream bases (kn7000-base is a long-lived fork point;
# technics-rom-record is cut from current upstream/master). Shared upstream files therefore
# differ by a hundred-odd commits of history that has nothing to do with us. Demanding
# byte-equality would report permanent drift -- a check that can never pass, which nobody runs.
#
# What must hold is that OUR OWN work is present in BOTH. So:
#   * files we PATCHED (upstream files)  -> check our marker symbol is present in both
#   * files we AUTHORED (wholly new)     -> byte-identical wherever both trees carry them
#
#   ./tools/sync-check.sh              report (default; non-zero if anything is out of sync)
#   ./tools/sync-check.sh --from-pr    copy AUTHORED files B -> A
#   ./tools/sync-check.sh --to-pr      copy AUTHORED files A -> B
#
# Copying never commits. Review with git diff, then commit in that worktree yourself.
set -uo pipefail

A="${MAME_BASE:-$HOME/compartilhado/mame}"
B="${MAME_PR:-$HOME/compartilhado/mame-pr}"
C="${OVERLAY_SRC:-$HOME/compartilhado/kn7000_mame/src}"

# Upstream files we patched:  <path>|<marker that proves our change is in>
PATCHED=(
	"src/devices/machine/intelfsh.h|FUJITSU_29LV160B"
	"src/devices/machine/intelfsh.cpp|fujitsu_29lv160b_device"
	"src/devices/machine/intelfsh.h|MACRONIX_29LV160B"
	"scripts/src/bus.lua|TECHNICS_KN6000"
)

# Files we authored outright. "optional" = the overlay does not need it yet; its ABSENCE from A
# is fine, but if both trees have it they must match.
AUTHORED_OPTIONAL=(
	src/devices/bus/technics/kn6000/hdsx3.cpp
	src/devices/bus/technics/kn6000/hdsx3.h
	src/devices/bus/technics/kn6000/kn6000_expansion.cpp
	src/devices/bus/technics/kn6000/kn6000_expansion.h
)

# Different on purpose. Listed so nobody "fixes" them.
DIVERGENT=(
	"src/mame/matsushita/kn7000.cpp   PR = ROM-record skeleton, overlay = full driver"
	"src/mame/mame.lst                PR declares five machines, overlay declares its own"
	"scripts/src/cpu.lua              overlay enables the MN10300 core; upstream has none"
)

red() { printf '\033[31m%s\033[0m\n' "$*"; }
grn() { printf '\033[32m%s\033[0m\n' "$*"; }
ylw() { printf '\033[33m%s\033[0m\n' "$*"; }

check_branches() {
	local bad=0
	for pair in "$A:kn7000-base" "$B:technics-rom-record"; do
		local dir="${pair%%:*}" want="${pair##*:}" got
		if [ ! -d "$dir" ]; then
			red "MISSING worktree: $dir"
			red "  create it:  git -C $A worktree add $dir $want"
			bad=1; continue
		fi
		got=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
		if [ "$got" != "$want" ]; then
			red "WRONG BRANCH: $dir is on '$got', expected '$want'"
			red "  These are worktrees -- one branch each. Do not 'git checkout' in them."
			bad=1
		else
			grn "ok   $dir @ $got"
		fi
	done
	return $bad
}

report() {
	local bad=0
	echo
	echo "OUR PATCHES TO UPSTREAM FILES (marker must be present in both):"
	for e in "${PATCHED[@]}"; do
		local f="${e%%|*}" m="${e##*|}" ina=0 inb=0
		grep -q -- "$m" "$A/$f" 2>/dev/null && ina=1
		grep -q -- "$m" "$B/$f" 2>/dev/null && inb=1
		if   [ $ina -eq 1 ] && [ $inb -eq 1 ]; then grn "  both  $m   ($f)"
		elif [ $ina -eq 1 ]; then red  "  PR MISSING  $m   ($f)  -- promote with --to-pr or cherry-pick"; bad=1
		elif [ $inb -eq 1 ]; then red  "  OVERLAY MISSING  $m   ($f)  -- adopt with --from-pr or cherry-pick"; bad=1
		else                     red  "  ABSENT FROM BOTH  $m   ($f)"; bad=1
		fi
	done

	echo
	echo "FILES WE AUTHORED (identical wherever both carry them; optional in the overlay):"
	for f in "${AUTHORED_OPTIONAL[@]}"; do
		if   [ -f "$A/$f" ] && [ -f "$B/$f" ]; then
			cmp -s "$A/$f" "$B/$f" && grn "  ==  $f" || { red "  !=  $f   DRIFT"; bad=1; }
		elif [ -f "$B/$f" ]; then ylw "  pr-only  $f   (overlay does not use it yet -- fine)"
		elif [ -f "$A/$f" ]; then red "  overlay-only  $f   -- PR is missing it"; bad=1
		else                      ylw "  absent from both  $f"
		fi
	done

	echo
	echo "DIVERGENT BY DESIGN (never sync):"
	for d in "${DIVERGENT[@]}"; do echo "  xx  $d"; done

	echo
	echo "OVERLAY DELTA (informational -- files C replaces in the build tree):"
	local n=0
	while IFS= read -r f; do
		[ -f "$A/src/$f" ] && ! cmp -s "$C/$f" "$A/src/$f" && n=$((n+1))
	done < <(cd "$C" && find . -type f \( -name '*.cpp' -o -name '*.h' \) | sed 's|^\./||')
	echo "  $n overlay file(s) differ from the base tree -- that IS the overlay, not drift."
	return $bad
}

copy() {
	local from to
	if [ "$1" = "from-pr" ]; then from="$B"; to="$A"; else from="$A"; to="$B"; fi
	for dir in "$A" "$B"; do
		local n; n=$(git -C "$dir" status --porcelain 2>/dev/null | wc -l)
		[ "$n" -gt 0 ] && ylw "note: $dir has $n uncommitted change(s)"
	done
	echo "copying AUTHORED files: $from -> $to"
	local n=0
	for f in "${AUTHORED_OPTIONAL[@]}"; do
		[ -f "$from/$f" ] || continue
		cmp -s "$from/$f" "$to/$f" && continue
		mkdir -p "$(dirname "$to/$f")"
		cp -f "$from/$f" "$to/$f" && { echo "  updated $f"; n=$((n+1)); }
	done
	[ $n -eq 0 ] && echo "  (nothing to copy)"
	echo
	ylw "Patched-file changes are NOT copied -- cherry-pick those so history stays honest:"
	ylw "  git -C $to cherry-pick -x <sha>"
	ylw "Nothing committed. Review with:  git -C $to diff"
}

echo "=== sync-check: upstream PR staging <-> overlay ==="
check_branches || { red "Fix the worktrees first."; exit 2; }

case "${1:-}" in
	--from-pr) copy from-pr ;;
	--to-pr)   copy to-pr ;;
	""|--check)
		report; rc=$?
		echo
		[ $rc -eq 0 ] && grn "IN SYNC." || red "OUT OF SYNC -- resolve before building or submitting."
		exit $rc ;;
	*) echo "usage: $0 [--check|--from-pr|--to-pr]"; exit 1 ;;
esac
