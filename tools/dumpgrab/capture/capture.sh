#!/usr/bin/env bash
# capture.sh -- KN7000 MEMORY DUMP capture harness.
#
# Launches MAME on kn7000, drives the hidden MEMORY DUMP viewer (chord = UP+DOWN held on
# balance columns 1,4,5,8), dials a start address, sweeps N pages with the "orange button"
# (balance column 6 = +0x100 per press), and writes:
#     <out>/frames/NNNN.png   one 640x240 PNG per recorded frame (or per page)
#     <out>/movie.avi|.mng    a movie of the same window
#     <out>/manifest.csv      one row per recorded frame: relframe,absframe,seconds,addr,snap
#     <out>/manifest.json     per-page summary (first/last frame, frame count, snapshot ids)
#     <out>/capture.log       the Lua log
#
# The manifest is GROUND TRUTH produced from the firmware's own address cell, independent of
# any pixel extractor.
#
# Usage:
#   ./capture.sh --out DIR [options]
#     --out DIR          output directory                       (required)
#     --start HEX        start CPU address        (default 0x48400000, program flash base)
#     --pages N          pages to sweep                          (default 32)
#     --mode hold|tap    hold the orange button (firmware auto-repeat) or discrete taps
#                                                                (default hold)
#     --hold N           tap-mode hold, frames                   (default 8)
#     --gap N            tap-mode gap, frames                    (default 8)
#     --snap all|page|none                                       (default all)
#     --snapdelay N      frames after a page change before the first "page" snapshot (default 4)
#     --predelay N       frames of recording before the sweep starts             (default 300)
#                        Do NOT shorten this below ~240. The viewer's IDLE repaint period is
#                        ~2.95 s (measured), so right after the address is dialled the panel is
#                        still being painted and the START PAGE is never recorded settled. NOTE:
#                        lengthening it did NOT fix the start page's decode errors on the runs
#                        measured -- those turned out to be a deterministic extractor fault, not
#                        a repaint artefact. This flag buys a correctly-painted start page, not
#                        accuracy.
#     --movie avi|mng|none                                       (default avi)
#     --timeout SEC      wall-clock kill switch                  (default 900)
#     --mame DIR         emulator directory      (default /home/fsanches/compartilhado/kn7000-emulator)
#     --window|--fullscreen                                      (default --window)
#
# MAME hygiene: private -cfg_directory / -nvram_directory per run, always visible video
# (never -video none), every launch wrapped in `timeout`.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAMEDIR=/home/fsanches/compartilhado/kn7000-emulator
OUT=""; START=0x48400000; PAGES=32; MODE=hold; HOLD=8; GAP=8
SNAP=all; SNAPDELAY=4; PREDELAY=300; MOVIE=avi; TMO=900; WINFLAG=-window

while [ $# -gt 0 ]; do
  case "$1" in
    --out)        OUT="$2"; shift 2;;
    --start)      START="$2"; shift 2;;
    --pages)      PAGES="$2"; shift 2;;
    --mode)       MODE="$2"; shift 2;;
    --hold)       HOLD="$2"; shift 2;;
    --gap)        GAP="$2"; shift 2;;
    --snap)       SNAP="$2"; shift 2;;
    --snapdelay)  SNAPDELAY="$2"; shift 2;;
    --predelay)   PREDELAY="$2"; shift 2;;
    --movie)      MOVIE="$2"; shift 2;;
    --timeout)    TMO="$2"; shift 2;;
    --mame)       MAMEDIR="$2"; shift 2;;
    --window)     WINFLAG=-window; shift;;
    --fullscreen) WINFLAG=; shift;;
    -h|--help)    sed -n '2,45p' "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
[ -n "$OUT" ] || { echo "--out is required" >&2; exit 2; }

mkdir -p "$OUT/frames" "$OUT/cfg" "$OUT/nvram"
rm -f "$OUT"/frames/*.png "$OUT"/movie.avi "$OUT"/movie.mng

MOVIEPATH="$OUT/movie"

# -snapview native + -snapname frames/%i  ->  one 640x240 PNG per call at $OUT/frames/NNNN.png
# -harddisk "" keeps the SD card out of the boot path (the viewer needs nothing from it).
# -nothrottle runs as fast as the host allows; the emulated 60 Hz frame clock is unaffected,
#   so every measurement below is in EMULATED frames and is host-speed independent.
DG_DIR="$HERE" \
DG_OUT="$OUT/capture.log" \
DG_MANIFEST="$OUT/manifest.csv" \
DG_META="$OUT/manifest.json" \
DG_START="$START" DG_PAGES="$PAGES" DG_MODE="$MODE" DG_HOLD="$HOLD" DG_GAP="$GAP" \
DG_SNAP="$SNAP" DG_SNAPDELAY="$SNAPDELAY" DG_PRERUN="$PREDELAY" \
DG_MOVIE="$MOVIE" DG_MOVIEPATH="$MOVIEPATH" \
DISPLAY="${DISPLAY:-:0}" \
timeout "$TMO" "$MAMEDIR/kn7000" kn7000 \
    -rompath "$MAMEDIR/roms" -skip_gameinfo $WINFLAG -resolution 800x400 \
    -cfg_directory "$OUT/cfg" -nvram_directory "$OUT/nvram" \
    -snapshot_directory "$OUT" -snapname "frames/%i" \
    -snapview native \
    -harddisk "" -sound none -nothrottle \
    -autoboot_script "$HERE/memdump_capture.lua" -autoboot_delay 0 \
    > "$OUT/mame.stdout" 2>&1
rc=$?

echo "mame exit=$rc"
tail -n 20 "$OUT/capture.log" 2>/dev/null
echo "--- artefacts ---"
ls -l "$OUT" 2>/dev/null | grep -v '^total'
echo "frames: $(ls "$OUT/frames" 2>/dev/null | wc -l) png"
exit $rc
