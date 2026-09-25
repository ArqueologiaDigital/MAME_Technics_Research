#!/bin/bash
# Record an NGP session once, then replay it as often as needed with probes
# attached. The console needs power-on plus language and date/time before it
# boots to the splash and its tune, and that cannot be driven from Lua or
# xdotool -- MAME re-derives port values from physical input every frame -- so
# the input is captured once from a real keyboard and replayed after that.
#
#   ngp_session.sh record                  <- do the setup by hand, then Esc
#   ngp_session.sh replay [binary] [lua]   <- replay it, optionally with a probe
#
set -euo pipefail
MODE=${1:?record or replay}
WT=${WT:-$HOME/compartilhado/mame-pr-tlcs900fix}
INP=${INP:-$HOME/compartilhado/mame-roms/ngp_setup.inp}
cd "$WT"

case "$MODE" in
record)
	BIN=${2:-t9-master}
	echo "recording to $INP with $BIN"
	echo "  F1 to power on, set language and date/time, let the tune play, then Esc"
	exec ./"$BIN" ngp -rompath "$HOME/compartilhado/mame-roms" -skip_gameinfo \
		-record "$INP"
	;;
replay)
	BIN=${2:-t9-refactored}
	LUA=${3:-}
	[ -f "$INP" ] || { echo "no recording at $INP -- run: $0 record" >&2; exit 1; }
	ARGS=(-playback "$INP")
	[ -n "$LUA" ] && ARGS+=(-autoboot_script "$LUA")
	echo "replaying $INP with $BIN ${LUA:+(probe: $(basename "$LUA"))}"
	exec ./"$BIN" ngp -rompath "$HOME/compartilhado/mame-roms" -skip_gameinfo "${ARGS[@]}"
	;;
*)
	echo "usage: $0 record|replay [binary] [lua]" >&2; exit 2 ;;
esac
