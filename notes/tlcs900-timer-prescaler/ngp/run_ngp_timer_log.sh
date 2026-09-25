#!/bin/bash
# One command, so the tap cannot be left off by accident.
#
# Run it, then at the emulator: F1 to power on, set language and date/time, let
# it reach the splash screen and its tune, then press Esc to quit.
# The log lands in /tmp/ngp_timers.log.
set -euo pipefail
WT=${WT:-$HOME/compartilhado/mame-pr-tlcs900fix}
BIN=${1:-t9-refactored}
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WT"
rm -f /tmp/ngp_timers.log
echo "running $BIN -- power on with F1, do the setup, listen for the tune, then Esc"
./"$BIN" ngp \
	-rompath "$HOME/compartilhado/mame-roms" \
	-skip_gameinfo \
	-autoboot_script "$D/ngp_timer_log.lua"
echo
echo "=== /tmp/ngp_timers.log ==="
cat /tmp/ngp_timers.log 2>/dev/null || echo "(no log -- the script did not load)"
