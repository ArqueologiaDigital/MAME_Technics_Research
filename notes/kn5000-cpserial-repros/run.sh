#!/bin/bash
# run.sh <name> <lua> <binary> [env assignments...]
#
# Deterministic KN5000 control-panel-serial repro runner (see README.md in this directory).
# Always: EMPTY nvram dir, isolated snapshot dir, visible window on :0, timeout-wrapped.
# Never point -nvram_directory at kn7000-emulator/nvram: that is Felipe's live state, and a
# SECOND boot against any non-empty nvram dir grows a spurious "<Db>" transpose from an
# unrelated power-down-NMI defect (blog Part 72) that must not be blamed on the serial link.
set -u
OUTBASE="${OUTBASE:-/tmp/kn5000-cpserial-repros}"
NAME="$1"; shift
LUA="$(readlink -f "$1")"; shift
BIN="$(readlink -f "$1")"; shift
RUN="$OUTBASE/$NAME"
rm -rf "$RUN"; mkdir -p "$RUN/nvram" "$RUN/snap"
export DISPLAY=:0
for kv in "$@"; do export "$kv"; done
cd /home/fsanches/compartilhado/kn7000-emulator || exit 1
timeout 900 "$BIN" kn5000 -rompath ./roms -skip_gameinfo -window \
  -nvram_directory "$RUN/nvram" -snapshot_directory "$RUN/snap" \
  -autoboot_script "$LUA" -pluginspath ./plugins \
  > "$RUN/out.log" 2>&1
rc=$?
echo "EXIT=$rc $NAME bin=$BIN env=$*"
# Liveness is a PIXEL DIFF, not a counter: identical md5s across the post-press snapshots
# mean the panel is DEAD.  Read the PNGs, do not infer screen state from the log.
md5sum "$RUN"/snap/kn5000/*.png 2>/dev/null | awk '{printf "%s %s\n",substr($1,1,8),$2}'
