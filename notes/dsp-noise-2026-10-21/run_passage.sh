#!/bin/bash
# run_passage.sh EMU_DIR OUT MODE [mame args...] -- one session of passage.lua (README.md here).
#   MODE wav   -nothrottle -sound none -wavwrite OUT/run.wav: the computed stream, as fast as the host allows
#   MODE live  throttled, real sound output, and pw-record capturing the default sink's monitor into OUT/live.wav:
#              what a listener hears (pw-record must be available; the sink may be muted, the monitor is pre-volume)
# BYPASS=1 runs with KN7000_DSP_BYPASS_SCRATCH set (only a binary built with bypass-scratch.patch honours it: the
# SHARC stays halted after the download, IRQ0 never comes, the bridge passes the tone generator through).
# -bios v13 (program 893, the owner's), no media but the real card image, fresh nvram/cfg in OUT.
# OUT is scratch (~/compartilhado/tmp/..., never /tmp). Prints the passage log.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EMU="$(cd "${1:?usage: run_passage.sh EMU_DIR OUT wav|live [mame args]}" && pwd)"
O="$(mkdir -p "${2:?}" && cd "$2" && pwd)"
MODE="${3:?}"; shift 3
rm -rf -- "${O:?}/nv" "${O:?}/cfg"; mkdir -p "$O/nv" "$O/cfg"
rm -f -- "${O:?}/run.wav" "${O:?}/live.wav"
ENVS=(NP_OUT="$O" DISPLAY="${DISPLAY:-:0}")
[ "${BYPASS:-0}" = 1 ] && ENVS+=(KN7000_DSP_BYPASS_SCRATCH=1)
[ -n "${EXTRA:-}" ] && ENVS+=(NP_EXTRA="$(cd "$(dirname "$EXTRA")" && pwd)/$(basename "$EXTRA")")   # e.g. EXTRA=frames_tap.lua
COMMON=(kn7000 -bios v13 -rompath ./roms -pluginspath ./plugins -skip_gameinfo -window -nomaximize
        -harddisk sdcard_from_real_kn7000.img -nvram_directory "$O/nv" -cfg_directory "$O/cfg"
        -autoboot_script "$HERE/passage.lua")
echo "emulator md5 $(md5sum < "$EMU/kn7000" | cut -c1-32) mode $MODE bypass ${BYPASS:-0} args $*" > "$O/versions.txt"
case "$MODE" in
  wav)
    ( cd "$EMU" && env "${ENVS[@]}" timeout 900 ./kn7000 "${COMMON[@]}" -nothrottle -sound none \
        -wavwrite "$O/run.wav" "$@" ) > "$O/run.log" 2>&1 ;;
  live)
    pw-record -P '{ stream.capture.sink = true }' --rate 48000 --channels 2 --format s16 "$O/live.wav" &
    REC=$!
    ( cd "$EMU" && env "${ENVS[@]}" timeout 900 ./kn7000 "${COMMON[@]}" "$@" ) > "$O/run.log" 2>&1
    kill "$REC"; wait "$REC" 2>/dev/null ;;
  *) echo "MODE must be wav or live" >&2; exit 2 ;;
esac
cat "$O/passage.txt"
