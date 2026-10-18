#!/usr/bin/env bash
# run_verify.sh -- run verify_probe.lua in MAME (kn7000, PROGRAM 941); every artefact goes to OUTDIR.
# usage: ./run_verify.sh OUTDIR
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:?usage: run_verify.sh OUTDIR}"
MAMEDIR=/home/fsanches/compartilhado/kn7000-emulator
DGDIR=/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab/capture
mkdir -p "$OUT/cfg" "$OUT/nvram"
DG_DIR="$DGDIR" DG_OUT="$OUT/probe.log" VP_OUT="$OUT" VP_BMPDIR="$HERE/bmps" \
DISPLAY="${DISPLAY:-:0}" \
timeout 1500 "$MAMEDIR/kn7000" kn7000 \
    -rompath "$MAMEDIR/roms" -skip_gameinfo -window -resolution 800x400 \
    -cfg_directory "$OUT/cfg" -nvram_directory "$OUT/nvram" \
    -snapshot_directory "$OUT" -snapview native \
    -harddisk "" -sound none -nothrottle \
    -autoboot_script "$HERE/verify_probe.lua" -autoboot_delay 0 \
    > "$OUT/mame.stdout" 2>&1
echo "mame exit=$?"
