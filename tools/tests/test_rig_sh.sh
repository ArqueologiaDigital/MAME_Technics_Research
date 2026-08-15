#!/usr/bin/env bash
# test_rig_sh.sh -- the fault injection behind rig.sh's "it tells you when a rig did not load".
#
# WHAT QUESTION THIS ANSWERS: commit e72a11d claims rig.sh was "verified by fault injection: a
# broken rig exits 1 with a named diagnosis". This is that injection, made repeatable. Without
# it the claim rests on a one-line file that lived in session scratch and is now gone.
#
#   ./tools/tests/test_rig_sh.sh            # fast checks only (no emulator, ~1 s)
#   ./tools/tests/test_rig_sh.sh --full     # also the broken-rig injection (boots MAME, ~2 min)
#
# Exit 0 only if every check passed.
#
# The broken rig is GENERATED here rather than committed as a file, so there is no
# permanently-broken .lua sitting in tools/rigs/ for the index to list and for someone to
# "fix" a year from now.
set -uo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)"
RIG="$REPO/tools/rig.sh"
FULL=0
[ "${1:-}" = "--full" ] && FULL=1

PASS=0; FAIL=0
ok()  { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

echo "== argument handling (no emulator) =="

# -h must print usage, not be swallowed as a rig name. It was, in the first version.
out=$("$RIG" -h 2>&1); rc=$?
if [ $rc -eq 0 ] && echo "$out" | grep -q '^usage: rig.sh'; then
	ok "-h prints usage"
else
	bad "-h  (rc=$rc, first line: $(echo "$out" | head -1))"
fi

# A rig that does not exist must fail BEFORE launching anything.
out=$("$RIG" no_such_rig_xyz 2>&1); rc=$?
if [ $rc -ne 0 ] && echo "$out" | grep -q 'no such rig'; then
	ok "missing rig rejected without launching"
else
	bad "missing rig  (rc=$rc)"
fi

# The machine must be inferable and reported. rig.sh prints its header before launching, so a
# short timeout is enough to read it -- this check deliberately does not wait for the run.
out=$(timeout 5 "$RIG" kn5000_p9_stall -s 1 2>&1 | head -6)
if echo "$out" | grep -q 'machine: kn5000'; then
	ok "machine inferred from the rig-machine: header"
else
	bad "machine inference  ($(echo "$out" | grep -m1 machine))"
fi

if [ "$FULL" -eq 0 ]; then
	echo
	echo "== $PASS passed, $FAIL failed (fast subset -- pass --full for the injection) =="
	[ "$FAIL" -eq 0 ] || exit 1
	exit 0
fi

echo
echo "== fault injection: a rig that does not load =="
# THE POINT: MAME exits rc=3 with a fatal error here -- it does NOT run on without the rig
# (measured 2026-08-15; the first draft of rig.sh's header guessed otherwise and was wrong).
# rig.sh must turn that into a one-line diagnosis rather than a fatal buried in a log.
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
printf 'this is not valid lua (((\n' > "$TMP/broken_rig.lua"

out=$("$RIG" "$TMP/broken_rig.lua" kn5000 -s 5 -l "$TMP/broken.log" 2>&1); rc=$?
if [ $rc -ne 0 ] && echo "$out" | grep -q 'THE RIG DID NOT LOAD'; then
	ok "broken rig -> rc=$rc and a named diagnosis"
else
	bad "broken rig  (rc=$rc; expected non-zero + 'THE RIG DID NOT LOAD')"
	echo "$out" | tail -5 | sed 's/^/        /'
fi

echo
echo "== $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ] || exit 1
exit 0
