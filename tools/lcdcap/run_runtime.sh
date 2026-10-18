#!/usr/bin/env bash
# run_runtime.sh -- run lcdcap_runtime.lua headless in MAME kn7000 (PROGRAM 941) with a scratch ROM path.
# Question: with 0x4840000F = 0xFF in the ROM file, does the four-corner LCD chord write
# A:\LCDCAP00.BMP to the inserted floppy (or, with RT_REDIRECT_SD=1, to the SD image)?
# Usage: ./run_runtime.sh {stock|ff} OUTDIR [extra MAME args, e.g. -flop img / -harddisk img]
# Env: RT_REDIRECT_SD=1, RT_HOLD_FRAMES=N (frames to keep the four keys held; default 1800)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SET="${1:?usage: run_runtime.sh SET OUTDIR [mame args]}"
OUT="${2:?usage: run_runtime.sh SET OUTDIR [mame args]}"
shift 2
MAME=/home/fsanches/compartilhado/kn7000-emulator/kn7000
DGDIR=/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab/capture
mkdir -p "$OUT/cfg" "$OUT/nvram"
export TMPDIR=/home/fsanches/compartilhado/tmp
DG_DIR="$DGDIR" DG_OUT="$OUT/probe.log" RT_OUT="$OUT" \
timeout 1200 "$MAME" kn7000 \
    -rompath "$HERE/roms_$SET" -skip_gameinfo \
    -video none -sound none -nothrottle -seconds_to_run 600 \
    -cfg_directory "$OUT/cfg" -nvram_directory "$OUT/nvram" \
    -snapshot_directory "$OUT" -snapview native \
    "$@" \
    -autoboot_script "$HERE/lcdcap_runtime.lua" -autoboot_delay 0 \
    > "$OUT/mame.stdout" 2>&1
echo "mame exit=$?"
