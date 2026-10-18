#!/usr/bin/env bash
# run_mame.sh -- launch kn7000 (PROGRAM 941) in MAME with one runtime-lane Lua script; every
# artefact (log, snapshots, cfg, nvram, stdout) goes into OUTDIR. Nothing is written to any repo.
# Usage: [EXTRA="-flop /path.img -harddisk /path.img"] ./run_mame.sh OUTDIR SCRIPT.lua [env...]
#   ROMs:     scratch copy runtime/roms/kn7000 (sha256 of kn7000_program.rom 2879624f...e66f = baserom)
#   Emulator: /home/fsanches/compartilhado/kn7000-emulator/kn7000 (sha256 43fa8283...e278, built 2026-10-08)
#   Video:    visible window on $DISPLAY (kn7000_mame rule: never -video none); snapshots native 640x240.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:?usage: run_mame.sh OUTDIR SCRIPT.lua}"
SCRIPT="${2:?usage: run_mame.sh OUTDIR SCRIPT.lua}"
mkdir -p "$OUT/cfg" "$OUT/nvram"
OUT="$(cd "$OUT" && pwd)"
MAME=/home/fsanches/compartilhado/kn7000-emulator/kn7000
# default: empty SD slot and no floppy; EXTRA (word-split) replaces that, e.g. EXTRA="-flop x.img -harddisk sd.img"
if [ -n "${EXTRA:-}" ]; then read -r -a MEDIA <<< "$EXTRA"; else MEDIA=(-harddisk ""); fi
RT_DIR="$HERE/scripts" DG_OUT="$OUT/probe.log" DISPLAY="${DISPLAY:-:0}" \
timeout "${TMO:-1200}" "$MAME" kn7000 \
    -rompath "$HERE/roms" -skip_gameinfo -window -resolution 800x400 \
    -cfg_directory "$OUT/cfg" -nvram_directory "$OUT/nvram" \
    -snapshot_directory "$OUT" -snapview native \
    "${MEDIA[@]}" -sound none -nothrottle \
    -autoboot_script "$HERE/scripts/$SCRIPT" -autoboot_delay 0 \
    > "$OUT/mame.stdout" 2>&1
rc=$?
echo "mame exit=$rc"
