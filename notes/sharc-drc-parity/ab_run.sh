#!/bin/bash
# Run every available SHARC machine on the upstream binary and on the submission's
# binary, and compare the framebuffer at fixed frames.
#
# QUESTION IT ANSWERS
#   "The submission changes src/devices/cpu/sharc, which 220 existing machines
#    execute. Do any of them behave differently?"
#
# BOTH BINARIES GET IDENTICAL TREATMENT: same ROMs, same empty cfg/nvram, same
# frame marks, same options. The nvram directory is private and starts empty, so
# both take the same first-boot path -- an inherited nvram would let one binary
# start from a state the other never saw.
#
# -str IS NOT OPTIONAL, and it is not there to bound the run.
#   Every one of these machines carries a red/yellow warning screen (gticlub is
#   MACHINE_IMPERFECT_GRAPHICS | MACHINE_NODEVICE_LAN), and -skip_gameinfo does not
#   dismiss it. Emulation does not start until it is, so the autoboot timer -- armed
#   for autoboot_delay EMULATED seconds -- never expires and the tap never loads.
#   Measured: without -str the chunk did not even reach its first line after 60 s of
#   wall clock; with -str 10 it loaded, installed, fired and exited at frame 60.
#   Passing a script that does not exist is how to tell the two apart: MAME reports
#   "Error loading autoboot script" at startup either way, so a silent run means the
#   script loaded and is simply never being invoked.
#
# TWO CONTROLS RUN FIRST, and the script stops if either fails:
#   determinism   the same binary twice on the same set must produce IDENTICAL
#                 dumps. If MAME is not run-to-run deterministic here, every
#                 "MATCH" below is meaningless.
#   discrimination  two DIFFERENT sets must produce DIFFERENT dumps. If the
#                 comparison cannot tell those apart it cannot tell anything apart.
#
# USAGE  ab_run.sh <base-binary> <pr-binary> <rompath> <outdir> [set ...]
set -uo pipefail

BASE=${1:?base binary}; PR=${2:?pr binary}; ROMS=${3:?rompath}; OUT=${4:?outdir}; shift 4
SETS=("$@")
MARKS=${AB_MARKS:-600,1200,1800,2400,3000}
# The two binaries are not always upstream-vs-submission: the seeded controls compare
# the submission against a deliberately broken build. Labelling the columns keeps a
# saved log from claiming it measured something it did not.
LA=${AB_LABEL_A:-base}; LB=${AB_LABEL_B:-pr}
LAST=${MARKS##*,}
mkdir -p "$OUT"
TAP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ab_tap.lua"

run () {   # $1 = binary, $2 = set, $3 = tag
	local d="$OUT/$2.$3"
	rm -rf "$d"; mkdir -p "$d/cfg" "$d/nvram"
	AB_OUT="$d" AB_MARKS="$MARKS" timeout -k 10 1200 "$1" "$2" \
		-rompath "$ROMS" -skip_gameinfo -nothrottle -sound none \
		-autoboot_script "$TAP" -str "${AB_STR:-120}" \
		-cfg_directory "$d/cfg" -nvram_directory "$d/nvram" \
		-snapshot_directory "$d" -window -nomaximize -resolution 640x480 \
		> "$d/mame.log" 2>&1
	echo $? > "$d/exit"
}

cmp_dirs () {   # $1 $2 -> prints MATCH / DIFFERS <frame> / NODATA
	local a="$1" b="$2" n=0 bad=""
	for f in "$a"/f*.raw; do
		[ -e "$f" ] || continue
		n=$((n+1))
		local g="$b/$(basename "$f")"
		if [ ! -e "$g" ]; then bad="$bad missing:$(basename "$f" .raw)"; continue; fi
		cmp -s "$f" "$g" || bad="$bad $(basename "$f" .raw)"
	done
	if [ "$n" = 0 ]; then echo "NODATA"; elif [ -z "$bad" ]; then echo "MATCH ($n frames)"; else echo "DIFFERS at$bad"; fi
}

echo "== controls =="
CTL=${SETS[0]}
run "$BASE" "$CTL" ctlA
run "$BASE" "$CTL" ctlB
det=$(cmp_dirs "$OUT/$CTL.ctlA" "$OUT/$CTL.ctlB")
echo "  determinism   $CTL twice on the base binary: $det"
case "$det" in MATCH*) ;; *) echo "  CONTROL FAILED -- the A/B cannot mean anything. Stopping." >&2; exit 1;; esac

if [ ${#SETS[@]} -gt 1 ]; then
	OTHER=${SETS[1]}
	run "$BASE" "$OTHER" ctlC
	dis=$(cmp_dirs "$OUT/$CTL.ctlA" "$OUT/$OTHER.ctlC")
	echo "  discrimination $CTL vs $OTHER: $dis"
	case "$dis" in DIFFERS*) ;; *) echo "  CONTROL FAILED -- the comparison cannot tell two machines apart. Stopping." >&2; exit 1;; esac
fi

echo
echo "== $LA vs $LB, $LAST frames each, marks $MARKS =="
fail=0
for s in "${SETS[@]}"; do
	run "$BASE" "$s" "$LA" &
	p1=$!
	run "$PR" "$s" "$LB" &
	p2=$!
	wait $p1 $p2
	eb=$(cat "$OUT/$s.$LA/exit" 2>/dev/null); ep=$(cat "$OUT/$s.$LB/exit" 2>/dev/null)
	r=$(cmp_dirs "$OUT/$s.$LA" "$OUT/$s.$LB")
	printf '  %-10s %s_exit=%-3s %s_exit=%-3s  %s\n' "$s" "$LA" "${eb:-?}" "$LB" "${ep:-?}" "$r"
	case "$r" in MATCH*) ;; *) fail=1;; esac
done
echo
[ $fail = 0 ] && echo "ALL MATCH" || echo "SOME DIFFER -- see above"
exit $fail
