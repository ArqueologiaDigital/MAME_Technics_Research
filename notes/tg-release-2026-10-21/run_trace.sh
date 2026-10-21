#!/bin/bash
# run_trace.sh EMU_DIR OUT [BIOS] -- the release probe (probe.lua, probe.mid) under MAME's debugger with keyoff_trace.dbg
# (README.md here): the library's key-off functions are logged to OUT/error.log next to probe.lua's TG write log.
# BIOS defaults to v16, the build program.s's equates are for. -debug opens the debugger window; the script runs on.
# OUT is scratch (~/compartilhado/tmp/..., never /tmp).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EMU="$(cd "${1:?usage: run_trace.sh EMU_DIR OUT [BIOS]}" && pwd)"
O="$(mkdir -p "${2:?}" && cd "$2" && pwd)"
BIOS="${3:-v16}"
rm -rf -- "${O:?}/nv" "${O:?}/cfg"; mkdir -p "$O/nv" "$O/cfg"
rm -f -- "${O:?}/run.wav" "${O:?}/error.log"
python3 -I "$HERE/gen_probe_mid.py" "$O/probe.mid" > "$O/versions.txt"
echo "emulator md5 $(md5sum < "$EMU/kn7000" | cut -c1-32) bios $BIOS" >> "$O/versions.txt"
( cd "$O" && env TR_OUT="$O" DISPLAY="${DISPLAY:-:0}" timeout 1800 "$EMU/kn7000" kn7000 -bios "$BIOS" -rompath "$EMU/roms" \
    -pluginspath "$EMU/plugins" -skip_gameinfo -window -nomaximize -harddisk "$EMU/sdcard_from_real_kn7000.img" \
    -midiin1 "$O/probe.mid" -nvram_directory "$O/nv" -cfg_directory "$O/cfg" -snapshot_directory "$O" \
    -debug -debugscript "$HERE/keyoff_trace.dbg" -log \
    -autoboot_script "$HERE/probe.lua" -nothrottle -sound none -wavwrite "$O/run.wav" ) > "$O/run.log" 2>&1
cat "$O/versions.txt" "$O/take.txt"
