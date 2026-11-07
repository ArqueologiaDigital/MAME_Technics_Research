#!/bin/bash
# run_peek.sh OUT [MAME] -- (ROMS: the rompath, default ~/compartilhado/kn7000-emulator/roms) boots the KN7000 on a fresh nvram and runs ic21_peek.lua (README.md here).
set -euo pipefail
OUT="$(mkdir -p "${1:?out dir}" && cd "$1" && pwd)"
MAME="${2:-$HOME/compartilhado/kn7000-emulator/kn7000}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROMS="${ROMS:-$HOME/compartilhado/kn7000-emulator/roms}"
mkdir -p "$OUT/nvram" "$OUT/cfg"
cd "$OUT"
IC21_FILE="$ROMS/kn7000/kn7000_custom_data.rom" timeout -k 5 300 "$MAME" kn7000 -rompath "$ROMS" -window -skip_gameinfo -nothrottle -nvram_directory "$OUT/nvram" \
    -cfg_directory "$OUT/cfg" -snapshot_directory "$OUT" -harddisk "" -autoboot_script "$HERE/ic21_peek.lua" \
    > "$OUT/run.log" 2>&1 || true
grep '^ic21_peek' "$OUT/run.log"
