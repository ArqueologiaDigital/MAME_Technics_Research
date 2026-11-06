#!/bin/sh
# run_gates.sh -- runs audio_gates.lua once on a given build, from a fresh run directory, with a
# -wavwrite capture, then measures it with gate_windows.py.
#
#   sh run_gates.sh BINARY RUNDIR [extra MAME options]
#
# RUNDIR is created (it must not exist) and gets cfg/ nvram/ snap/ diff/, a fresh copy of the real
# SD card dump, gates.txt (the probe's log), gates.wav, error.log (-log: the driver's IC311 lines)
# and windows.txt.  Put it in scratch ($TMPDIR), never /tmp.  Visible video, no sound device,
# unthrottled; about a minute of wall time.
set -eu
BIN=$1
RUN=$2
shift 2
HERE=$(cd "$(dirname "$0")" && pwd)
SD=${SD:-$HOME/compartilhado/technics_roms/media/sdcard_from_real_kn7000.img}
ROMS=${ROMS:-$HOME/compartilhado/technics_romsets}
mkdir "$RUN"
cd "$RUN"
mkdir cfg nvram snap diff
cp "$SD" sd_real.img
chmod u+w sd_real.img
OUT=gates.txt timeout -k 10 600 "$BIN" kn7000 -rompath "$ROMS" -skip_gameinfo -window -nomax \
	-sound none -nothrottle -log -cfg_directory cfg -nvram_directory nvram -snapshot_directory snap \
	-diff_directory diff -harddisk sd_real.img -wavwrite gates.wav \
	-autoboot_script "$HERE/audio_gates.lua" "$@" > mame.out 2>&1 || echo "mame exit $?"
rm -f -- sd_real.img
md5sum "$BIN" gates.wav > md5.txt
python3 -I "$HERE/gate_windows.py" gates.txt gates.wav | tee windows.txt
