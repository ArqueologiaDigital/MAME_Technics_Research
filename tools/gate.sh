#!/usr/bin/env bash
# gate.sh -- the one check that has to stay green.
#
# WHY THIS EXISTS: over one week in August 2026, six separately-published claims turned
# out to be false the moment anything was re-run -- a source-coverage figure inflated 5x,
# two audio-oracle baselines that no longer reproduced (and disagreed with each other),
# "zero .byte code", "all LABEL_* replaced", three synthetic files shipping as chip dumps,
# and a DSP evidence script that had rotted. None were found by looking; they surfaced on
# first re-run. This script is the standing re-run.
#
#   ./tools/gate.sh              # everything
#   ./tools/gate.sh --static     # no emulator: validate + verifyroms only (seconds)
#   ./tools/gate.sh --model kn7000
#
# Exit 0 only if every check passed. Any failure exits 1 with a summary.
#
# ⚠ Deliberately uses -window, not -video none: the project rule is that a human can
#   always see what a rig is doing. It does mean this needs a display.
set -uo pipefail

EMU_DIR="${EMU_DIR:-/home/fsanches/compartilhado/kn7000-emulator}"
RIGS="$(cd "$(dirname "$0")" && pwd)/rigs"
ONLY=""
STATIC=0
while [ $# -gt 0 ]; do
	case "$1" in
		--static) STATIC=1 ;;
		--model) ONLY="$2"; shift ;;
		*) echo "usage: $0 [--static] [--model NAME]"; exit 2 ;;
	esac
	shift
done

cd "$EMU_DIR" || { echo "gate: no emulator at $EMU_DIR"; exit 1; }
[ -x ./kn7000 ] || { echo "gate: no binary at $EMU_DIR/kn7000"; exit 1; }

# Per-model expectations, measured 2026-08-14 on binary 74035784 B.
#   model:min_distinct
# min_distinct is a FLOOR just under the observed value, so a real regression trips it
# while ordinary UI variation does not. Observed: kn7000 12, kn5000 20, kn6000 9,
# kn6500 8, kn2400 4, kn2600 4.
#   ⚠ kn2400/kn2600 sit at 4 because they render almost nothing -- a known defect, not a
#   healthy baseline. Raise their floor when the text path is fixed.
#   kn1500 has no screen device (SVG/HD44780) so the probe reports SKIP.
MODELS="kn7000:11 kn5000:18 kn6000:8 kn6500:7 kn2400:4 kn2600:4 kn1500:0"

ORACLE_MD5="780de131e33a4a0c99d092b57a074247"

PASS=0; FAIL=0; SKIP=0
FAILED=""
ok()   { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL  $1"; FAIL=$((FAIL+1)); FAILED="$FAILED
    $1"; }
skip() { echo "  SKIP  $1"; SKIP=$((SKIP+1)); }

echo "== static =="
if timeout 120 ./kn7000 -validate >/dev/null 2>&1; then ok "-validate"; else bad "-validate"; fi
if timeout 180 ./kn7000 -listxml >/dev/null 2>&1; then ok "-listxml"; else bad "-listxml"; fi

for entry in $MODELS; do
	m="${entry%%:*}"
	[ -n "$ONLY" ] && [ "$m" != "$ONLY" ] && continue
	# "best available" is a pass: BAD_DUMP entries are declared, not accidents.
	out=$(timeout 200 ./kn7000 "$m" -rompath ./roms -verifyroms 2>&1)
	if echo "$out" | grep -qE 'romset .* is (good|best available)'; then
		ok "verifyroms $m"
	else
		bad "verifyroms $m -- $(echo "$out" | tail -1)"
	fi
done

[ "$STATIC" -eq 1 ] && { echo; echo "static only: $PASS passed, $FAIL failed"; [ "$FAIL" -eq 0 ] || exit 1; exit 0; }

echo
echo "== liveness (does it boot and draw?) =="
for entry in $MODELS; do
	m="${entry%%:*}"; min="${entry##*:}"
	[ -n "$ONLY" ] && [ "$m" != "$ONLY" ] && continue
	line=$(LIVENESS_AT=25 LIVENESS_MIN="$min" timeout 260 ./run.sh "$m" \
		-window -nothrottle -seconds_to_run 27 \
		-autoboot_script "$RIGS/liveness.lua" 2>&1 | grep -m1 '^LIVENESS')
	case "$line" in
		*PASS*) ok "liveness $m  (${line#LIVENESS $m })" ;;
		*SKIP*) skip "liveness $m  -- no screen device" ;;
		"")     bad "liveness $m -- no LIVENESS line (crash, or never reached t=25)" ;;
		*)      bad "liveness $m  (${line#LIVENESS $m })" ;;
	esac
done

echo
echo "== audio oracle (kn7000 keybed + reverb) =="
if [ -n "$ONLY" ] && [ "$ONLY" != kn7000 ]; then
	skip "oracle -- --model $ONLY"
else
	# The recipe is pinned in rigs/README.md. Uses the SD image in place (read-only):
	# copying it costs 121 MB per run and has filled the scratch filesystem before.
	W=$(mktemp -d)/o.wav
	C=$(mktemp -d)
	timeout 500 ./run.sh kn7000 -window -nothrottle -seconds_to_run 22 \
		-autoboot_script "$RIGS/money.lua" -wavwrite "$W" \
		-cfg_directory "$C" -harddisk sdcard_from_real_kn7000.img >/dev/null 2>&1
	if [ ! -s "$W" ]; then
		bad "oracle -- no wav produced"
	else
		got=$(md5sum "$W" | cut -d' ' -f1)
		if [ "$got" = "$ORACLE_MD5" ]; then
			ok "oracle md5 $got"
		else
			bad "oracle md5 $got != $ORACLE_MD5 (audio path changed -- re-baseline deliberately, in its own commit)"
		fi
	fi
	rm -rf "$(dirname "$W")" "$C"
fi

echo
echo "== $PASS passed, $FAIL failed, $SKIP skipped =="
if [ "$FAIL" -gt 0 ]; then
	echo "failures:$FAILED"
	exit 1
fi
exit 0
