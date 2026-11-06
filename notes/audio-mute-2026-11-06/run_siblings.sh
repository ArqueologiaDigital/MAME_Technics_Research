#!/bin/sh
# run_siblings.sh -- runs sibling_boot.lua on each KN7000 sibling with two builds and compares the
# snapshot and the -wavwrite capture of each pair by md5 (identical = the change left it alone).
#
#   sh run_siblings.sh BUILD_A BUILD_B RUNDIR [machines...]     (default: kn6000 kn6500 kn2400 kn2600)
#
# RUNDIR is created (must not exist), in scratch ($TMPDIR), never /tmp.
set -eu
A=$1
B=$2
RUN=$3
shift 3
MACHINES=${*:-kn6000 kn6500 kn2400 kn2600}
HERE=$(cd "$(dirname "$0")" && pwd)
ROMS=${ROMS:-$HOME/compartilhado/technics_romsets}
mkdir "$RUN"
for m in $MACHINES; do
	for side in A B; do
		if [ "$side" = A ]; then BIN=$A; else BIN=$B; fi
		D="$RUN/$m-$side"
		mkdir -p "$D/cfg" "$D/nvram" "$D/snap" "$D/diff"
		(cd "$D" && timeout -k 10 600 "$BIN" "$m" -rompath "$ROMS" -skip_gameinfo -window -nomax -sound none \
			-nothrottle -cfg_directory cfg -nvram_directory nvram -snapshot_directory snap -diff_directory diff \
			-wavwrite out.wav -autoboot_script "$HERE/sibling_boot.lua" > mame.out 2>&1 || echo "$m $side: mame exit $?")
	done
	wa=$(md5sum < "$RUN/$m-A/out.wav" | cut -c1-32); wb=$(md5sum < "$RUN/$m-B/out.wav" | cut -c1-32)
	sa=$(cat "$RUN/$m-A"/snap/*/*.png | md5sum | cut -c1-32); sb=$(cat "$RUN/$m-B"/snap/*/*.png | md5sum | cut -c1-32)
	pk=$(python3 -I -c "import array,wave,sys;w=wave.open(sys.argv[1]);d=array.array('h',w.readframes(w.getnframes()));print(max((abs(v) for v in d),default=0))" "$RUN/$m-B/out.wav")
	echo "$m wav A $wa B $wb $([ "$wa" = "$wb" ] && echo same || echo DIFFERENT) peak(B) $pk | snapshot A $sa B $sb $([ "$sa" = "$sb" ] && echo same || echo DIFFERENT)"
done
