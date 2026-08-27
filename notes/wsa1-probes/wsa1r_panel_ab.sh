#!/bin/bash
# Whole-panel A/B: does the rewritten wsa1r.lay draw the same panel?
#
# QUESTION IT ANSWERS
#   nsvg_hash compares one <element> against another.  It cannot see
#   COMPOSITION -- which shape is painted over which -- and that is exactly
#   where the reuse pass went wrong once: lifting the rubber feet out of the
#   backdrop moved them from behind the panel body to in front of it, and every
#   per-element check still passed.  This renders the whole panel from a MAME
#   built at two different commits and diffs the two images.
#
# USAGE
#   # 1. capture the BEFORE, from the layout as it was
#   git show c51e4e8:src/mame/layout/wsa1r.lay > src/mame/layout/wsa1r.lay
#   ./build.sh && notes/wsa1-probes/wsa1r_panel_ab.sh capture /tmp/ab/old
#   # 2. put the current layout back and capture the AFTER
#   git checkout src/mame/layout/wsa1r.lay
#   ./build.sh && notes/wsa1-probes/wsa1r_panel_ab.sh capture /tmp/ab/new
#   # 3. compare
#   notes/wsa1-probes/wsa1r_panel_ab.sh compare /tmp/ab/old /tmp/ab/new
#
#   Add "pressed" to the capture to hold one key of every distinct shape down
#   (wsa1r_hold_one_of_each_shape.lua), which is the only way to see the
#   pressed-state artwork at all:
#       notes/wsa1-probes/wsa1r_panel_ab.sh capture /tmp/ab/press pressed
#
# WHAT THE NUMBERS MEAN
#   AE   how many of the 800000 pixels differ at all
#   PAE  the worst single channel difference, 0..1 of full scale
#   RMSE the whole-panel average
#   A reuse step that is meant to be free must come back AE=0.  The steps that
#   are not free are quoted in the commit that makes them, with these numbers.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$(dirname "$HERE")")
MAME=${MAME:-$ROOT/kn7000_mame_build/kn7000}
ROMS=${ROMS:-$ROOT/kn7000-emulator/roms}

case "$1" in
capture)
	OUT=$2; mkdir -p "$OUT"
	EXTRA=""
	[ "$3" = pressed ] && EXTRA="-autoboot_script $HERE/wsa1r_hold_one_of_each_shape.lua"
	# -str exits after N seconds and drops a snapshot; never -video none, the
	# panel has to be actually drawn.
	DISPLAY=${DISPLAY:-:0} timeout 150 "$MAME" wsa1r -rompath "$ROMS" -skip_gameinfo \
		-window -nomaximize -resolution 1600x500 \
		-snapshot_directory "$OUT" $EXTRA -str 14
	echo "captured -> $OUT/wsa1r/0000.png"
	;;
compare)
	A=$2/wsa1r/0000.png; B=$3/wsa1r/0000.png
	for m in AE PAE RMSE; do
		printf '%-5s ' "$m"
		magick compare -metric $m "$A" "$B" null: 2>&1 || true
		echo
	done
	magick "$A" "$B" -compose difference -composite -threshold 0 -format \
		'bounding box of every differing pixel: %@\n' info:
	magick "$A" "$B" -compose difference -composite -evaluate Multiply 12 \
		-colorspace Gray "$2/../diffmap.png"
	echo "difference map (x12) -> $2/../diffmap.png"
	;;
*)
	sed -n '2,40p' "$0"; exit 2 ;;
esac
