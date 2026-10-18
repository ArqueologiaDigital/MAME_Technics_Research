#!/usr/bin/env bash
# run_menu_shots.sh MACHINE ROMPATH OUTDIR -- boot MACHINE (kn6000|kn6500) with ROMPATH and
# snapshot the play screen plus six first-level menus (menu_shots.lua). Used to check that
# the generated table/font placeholder (tools/kn6xxx_font_placeholder.py) makes the menu
# text render. Visible window (the project rule: never -video none).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
M="${1:?machine}"; ROMS="${2:?rompath}"; OUT="${3:?outdir}"
BIN="${BIN:-$HERE/../../../kn7000_mame_build/kn7000}"
mkdir -p "$OUT/cfg" "$OUT/nvram" "$OUT/snap" "$OUT/sta"
export DISPLAY="${DISPLAY:-:0}"
timeout 900 "$BIN" "$M" -rompath "$ROMS" -skip_gameinfo -window -nothrottle -sound none \
  -seconds_to_run 400 -cfg_directory "$OUT/cfg" -nvram_directory "$OUT/nvram" \
  -snapshot_directory "$OUT/snap" -state_directory "$OUT/sta" -snapview native \
  -autoboot_script "$HERE/menu_shots.lua" -autoboot_delay 0 > "$OUT/mame.log" 2>&1
echo "exit=$? shots: $(grep -c '^SHOT' "$OUT/mame.log")"
