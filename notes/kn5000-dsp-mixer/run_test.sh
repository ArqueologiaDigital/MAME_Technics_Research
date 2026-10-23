#!/bin/sh
# run_test.sh PROG.txt OUTDIR [SECONDS] -- run a UPD6383_TESTPROG file on the KN5000 in the DSP1 build
# (ARCHOPTS=-DKN5000_ENABLE_DSP1=1, the tone generator mixing IC311's DO1/DO2), with DSPCFG bit 0 set by
# dspcfg.lua. OUTDIR gets out.wav (the speaker mix), run.log (the UPD6383TEST lines) and a private nvram copy.
# BIN overrides the binary (default ~/compartilhado/kn5000dsp_build/kn7000); EXTRA adds MAME options (-log
# writes error.log into ~/compartilhado/kn7000-emulator, the directory MAME runs in).
set -e
PROG=$(realpath "$1"); OUT=$2; SECS=${3:-12}
N=$(dirname "$(realpath "$0")")
BIN=${BIN:-/home/fsanches/compartilhado/kn5000dsp_build/kn7000}
mkdir -p "$OUT/nv" "$OUT/cfg"
OUT=$(realpath "$OUT")
cp -r /home/fsanches/compartilhado/kn7000-emulator/nvram/kn5000 "$OUT/nv/"
cd /home/fsanches/compartilhado/kn7000-emulator
UPD6383_PRESENT_ASIS=1 UPD6383_TESTPROG=$PROG DSPCFG_VALUE=1 DISPLAY=:0 timeout -k 5 600 "$BIN" kn5000 \
	-rompath ./roms -pluginspath ./plugins -skip_gameinfo -window -nomaximize -nothrottle \
	-seconds_to_run "$SECS" -wavwrite "$OUT/out.wav" -nvram_directory "$OUT/nv" -cfg_directory "$OUT/cfg" \
	-autoboot_script "$N/dspcfg.lua" $EXTRA > "$OUT/run.log" 2>&1 || true
grep -c "UPD6383TEST frame" "$OUT/run.log" || true
