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
OVERLAY=$(dirname "$(dirname "$HERE")")          # .../kn7000_mame
SIBLINGS=$(dirname "$OVERLAY")                   # .../compartilhado
MAME=${MAME:-$SIBLINGS/kn7000_mame_build/kn7000}
ROMS=${ROMS:-$SIBLINGS/kn7000-emulator/roms}

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
per-element)
	# Break the whole-panel difference down by each placement's <bounds>, which
	# is how the lift/keep figures in the generator's DECOR_NAMES were measured:
	# a mark lifted out of the backdrop is re-rasterised into its own
	# integer-pixel box and loses the sub-pixel phase it had inside the one big
	# backdrop raster, and this says what that costs, mark by mark.
	#   wsa1r_panel_ab.sh per-element /tmp/ab/old /tmp/ab/new [layout.lay]
	A=$2/wsa1r/0000.png B=$3/wsa1r/0000.png LAY=${4:-$OVERLAY/src/mame/layout/wsa1r.lay} \
	python3 - <<'PY'
import os, re, subprocess, collections
A, B, LAY = os.environ['A'], os.environ['B'], os.environ['LAY']
lay = open(LAY, encoding='utf-8').read()
place = collections.defaultdict(list)
for m in re.finditer(r'<element (?:name="[^"]*" )?(?:id="[^"]*" )?ref="([^"]+)"[^>]*?>'
                     r'.*?<bounds x="([-\d.]+)" y="([-\d.]+)" '
                     r'width="([\d.]+)" height="([\d.]+)"/>', lay, re.S):
    place[m.group(1)].append(tuple(float(v) for v in m.groups()[1:]))
d = subprocess.run(['magick', A, B, '-compose', 'difference', '-composite',
                    '-colorspace', 'Gray', '-depth', '8', 'gray:-'],
                   capture_output=True).stdout
W = H = None
ident = subprocess.run(['magick', 'identify', '-format', '%w %h', A],
                       capture_output=True, text=True).stdout.split()
W, H = int(ident[0]), int(ident[1])
print('%-30s %-5s %s' % ('element', 'xN', 'worst placement'))
for name, places in sorted(place.items()):
    worst = None
    for (x, y, w, h) in places:
        x0, y0 = max(0, int(x) - 2), max(0, int(y) - 2)
        x1, y1 = min(W, int(x + w) + 2), min(H, int(y + h) + 2)
        vals = [d[yy * W + xx] for yy in range(y0, y1) for xx in range(x0, x1)]
        if not vals:
            continue
        s = (max(vals), sum(1 for v in vals if v), len(vals),
             sum(vals) / float(len(vals)))
        if worst is None or s > worst:
            worst = s
    if worst:
        print('  %-30s x%-4d maxdelta=%3d  ndiff=%4d/%-6d mean=%.2f'
              % (name, len(places), worst[0], worst[1], worst[2], worst[3]))
PY
	;;
*)
	sed -n '2,40p' "$0"; exit 2 ;;
esac
