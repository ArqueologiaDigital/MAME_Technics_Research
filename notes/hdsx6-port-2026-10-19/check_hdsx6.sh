#!/bin/bash
# check_hdsx6.sh MAME_BINARY OUTDIR [ROMPATH] -- does the overlay's KN6000/KN6500 run the HD-SX6 (PR #16220 v5)?
# For each of kn6000 and kn6500: boots with -exp hdsx6 and a blank hard disk for 30 s of emulated time, with the PR's
# own probe (KN7000/tools/mame-pr-planning/kn6000-expansion-pr/probes/hdsx3_tap.lua: it logs every access to the
# card's I/O window and every ATA command), and snapshots at 6.0 s and 29 s. Pass, as for the PR (its README):
#   "ATA CMD ec"              the firmware sent IDENTIFY DEVICE (needs atahle's SET FEATURES 0x55 fix first)
#   "ATA data-port reads 512" it read the IDENTIFY block
#   snapshot 1 (6.0 s)        the board's own "HD-SX6 First edition / Start-up ... please wait!" screen
#   snapshot 2 (29 s)         the KN6000's play screen
# The overlay's KN6000 reaches the card about 2.6 s later than upstream's: board code first runs at 5.68 s (3.12 s
# in the PR's runs) and the splash shows from 5.85 s to 6.35 s (3.15-3.30 s there), so the PR's 3.2 s snapshot is
# still black here.
# The blank disk is 1422/16/63 (700 MiB; the firmware wants at least about 641 MiB), made once with chdman as an
# uncompressed CHD in OUTDIR, and each run writes to its own copy. ROMPATH defaults to the published folder's roms/
# (which holds hdsx6/ once tools/publish-binary.sh has run). Prints one summary line per model.
# The disk goes in -harddisk2: the overlay's KN6000 machines inherit the KN7000's SD card slot, which takes
# -harddisk1 (upstream's KN6000 has no SD slot, so there it is plain -harddisk).
set -euo pipefail
BIN="$(readlink -f "$1")"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
ROMPATH="${3:-$HOME/compartilhado/kn7000-emulator/roms}"
TAP="$HOME/compartilhado/KN7000/tools/mame-pr-planning/kn6000-expansion-pr/probes/hdsx3_tap.lua"
CHDMAN="${CHDMAN:-$(dirname "$BIN")/chdman}"
[ -f "$OUT/blank.chd" ] || "$CHDMAN" createhd -o "$OUT/blank.chd" -chs 1422,16,63 -ss 512 -c none > "$OUT/chdman.log" 2>&1
for M in kn6000 kn6500; do
  O="$OUT/$M"; mkdir -p "$O"; cp "$OUT/blank.chd" "$O/disk.chd"
  ( cd "$O" && HDSX3_SNAP_AT="6.0,29" DISPLAY="${DISPLAY:-:0}" timeout 900 "$BIN" "$M" -exp hdsx6 -harddisk2 "$O/disk.chd" \
      -rompath "$ROMPATH" -hashpath "$HOME/compartilhado/kn7000-emulator/hash" -window -nothrottle -skip_gameinfo \
      -cfg_directory cfg -nvram_directory nv -snapshot_directory snap -seconds_to_run 30 \
      -autoboot_script "$TAP" > stdout.txt 2> stderr.txt ) || true
  rm -f -- "${O:?}/disk.chd"
  ident=$(grep -c "ATA CMD ec" "$O/stdout.txt" || true)
  reads=$(grep -o "ATA data-port reads [0-9]*" "$O/stdout.txt" || echo "no data-port line")
  cmds=$(grep -o "ATA CMD [0-9a-f]*" "$O/stdout.txt" | awk '{print $3}' | tr '\n' ' ' || true)
  echo "$M: IDENTIFY sent $ident time(s); $reads; ATA commands: ${cmds:-none}; snapshots: $(ls "$O/snap/$M" 2>/dev/null | tr '\n' ' ')"
done
