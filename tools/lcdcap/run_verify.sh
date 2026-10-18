#!/usr/bin/env bash
# run_verify.sh -- run verify_chord.lua in MAME (kn7000, PROGRAM 941) and keep the log.
# Question: see the header of verify_chord.lua (orders, extra-pair release, re-fire, pad trigger).
# Usage: ./run_verify.sh OUTDIR
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:?usage: run_verify.sh OUTDIR}"
MAMEDIR=/home/fsanches/compartilhado/kn7000-emulator
DGDIR=/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab/capture
mkdir -p "$OUT/cfg" "$OUT/nvram"
sha256sum "$MAMEDIR/kn7000" > "$OUT/emulator.sha256"
DG_DIR="$DGDIR" DG_OUT="$OUT/verify.log" DISPLAY="${DISPLAY:-:0}" \
timeout 900 "$MAMEDIR/kn7000" kn7000 \
    -rompath "$MAMEDIR/roms" -skip_gameinfo -window -resolution 800x400 \
    -cfg_directory "$OUT/cfg" -nvram_directory "$OUT/nvram" \
    -snapshot_directory "$OUT" -snapview native \
    -harddisk "" -sound none -nothrottle \
    -autoboot_script "$HERE/verify_chord.lua" -autoboot_delay 0 \
    > "$OUT/mame.stdout" 2>&1
echo "mame exit=$?"
