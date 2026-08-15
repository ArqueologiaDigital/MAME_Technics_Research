#!/usr/bin/env bash
# test_kn5000_splash.sh -- the two-boot acceptance test for the KN5000 boot splash.
#
# WHAT QUESTION THIS ANSWERS: does a clean power-off through the modelled POWER switch leave
# state that makes the NEXT boot take the splash path? That is the acceptance criterion in
# side-quests/pending/kn5000_splash_animation.txt, and it CANNOT be tested in one run -- it
# needs two boots sharing an NVRAM directory, which is exactly what tools/rig.sh deliberately
# does not give you (it uses a throwaway directory per run, for determinism).
#
#   ./tools/tests/test_kn5000_splash.sh
#   ./tools/tests/test_kn5000_splash.sh --keep     # keep the NVRAM dir and both logs
#
# The chain under test (all of it firmware; the driver only supplies the NMI and the delay):
#   run 1: POWER pressed -> NMI -> checksums into DRAM 0xFFD4/0xFFD2
#          -> block 0xF980..0xFFEE copied to battery-backed IC21 SRAM at 0x1E8000
#          -> MAME exits and writes nvram/kn5000/nvram
#   run 2: boot -> 0x5AA5 magic at 0xFFCA absent (DRAM is volatile) -> restore from 0x1E8000
#          -> SubCPU_Payload_Verify (0xEF092B) passes -> transfer skipped -> SPLASH
set -uo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)"
EMU="${EMU_DIR:-/home/fsanches/compartilhado/kn7000-emulator}"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

NV=$(mktemp -d)
LOGD=$(mktemp -d)
cleanup() { [ "$KEEP" -eq 1 ] || rm -rf "$NV" "$LOGD"; }
trap cleanup EXIT

PASS=0; FAIL=0
ok()  { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

run() {  # run <logfile> <rig> <seconds> [extra env assignments are the caller's job]
	local log="$1" rig="$2" secs="$3"
	( cd "$EMU" && timeout $((secs * 8 + 120)) ./run.sh kn5000 \
		-window -nothrottle -seconds_to_run "$secs" \
		-autoboot_script "$REPO/tools/rigs/$rig.lua" \
		-cfg_directory "$NV" -nvram_directory "$NV" -snapshot_directory "$LOGD" \
		>"$log" 2>&1 )
}

echo "== run 1: boot, then power off through the modelled switch =="
PRESS_AT=30 run "$LOGD/run1.log" kn5000_poweroff 45
if grep -q 'power-down code RAN and reached the SRAM save' "$LOGD/run1.log"; then
	ok "firmware power-down ran ($(grep -oE 'AFTER the press: [0-9]+' "$LOGD/run1.log" | head -1))"
else
	bad "power-down did not reach the SRAM save"
	grep -E '^PO' "$LOGD/run1.log" | tail -3 | sed 's/^/        /'
fi

# The IC21 SRAM is the 128 KB file MAME writes on exit. Its CONTENT is the thing that has to
# survive, so check the saved block is not blank rather than merely that the file exists.
NVFILE="$NV/kn5000/nvram"
if [ -s "$NVFILE" ]; then
	NONZERO=$(python3 - "$NVFILE" <<-'PY'
		import sys
		d = open(sys.argv[1], "rb").read()
		# 0x1E8000 is 0x8000 into the 0x1e0000-0x1fffff SRAM window
		blk = d[0x8000:0x8000 + 0x66E]
		print(sum(1 for b in blk if b not in (0x00, 0xFF)))
	PY
	)
	if [ "${NONZERO:-0}" -gt 0 ]; then
		ok "saved SRAM holds the payload block ($NONZERO non-trivial bytes at +0x8000)"
	else
		bad "saved SRAM block at +0x8000 is blank -- nothing persisted"
	fi
else
	bad "no nvram file written at $NVFILE"
fi

echo
echo "== run 2: boot again from that NVRAM =="
run "$LOGD/run2.log" kn5000_warmboot 40
if grep -q '^WB' "$LOGD/run2.log"; then
	grep -E '^WB' "$LOGD/run2.log" | sed 's/^/  /'
	if grep -q 'WB VERDICT: warm path' "$LOGD/run2.log"; then
		ok "second boot took the warm path"
	else
		bad "second boot did not take the warm path"
	fi
else
	bad "run 2 produced no WB output"
fi

echo
echo "== $PASS passed, $FAIL failed =="
[ "$KEEP" -eq 1 ] && echo "kept: NVRAM $NV   logs+snapshots $LOGD"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
