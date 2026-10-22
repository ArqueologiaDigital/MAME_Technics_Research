#!/bin/bash
# run_probe6.sh EMU_DIR OUT -- one KN6000 (or MODEL=kn6500) release-probe run (README.md here): ../tg-release-2026-10-21's probe.mid on
# MIDI IN 1, probe6.lua's logs, the computed stream only (-nothrottle -sound none -wavwrite OUT/run.wav), fresh
# nvram/cfg. OUT is scratch (~/compartilhado/tmp/..., never /tmp). Writes OUT/{take,tgw,tgr,voices}.txt.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EMU="$(cd "${1:?usage: run_probe6.sh EMU_DIR OUT}" && pwd)"
O="$(mkdir -p "${2:?}" && cd "$2" && pwd)"
rm -rf -- "${O:?}/nv" "${O:?}/cfg" "${O:?}/snap"; mkdir -p "$O/nv" "$O/cfg" "$O/snap"
rm -f -- "${O:?}/run.wav"
python3 -I "$HERE/../tg-release-2026-10-21/gen_probe_mid.py" "$O/probe.mid" > "$O/versions.txt"
echo "emulator md5 $(md5sum < "$EMU/kn7000" | cut -c1-32)" >> "$O/versions.txt"
( cd "$EMU" && env TR_OUT="$O" DISPLAY="${DISPLAY:-:0}" timeout -k 10 1200 ./kn7000 "${MODEL:-kn6000}" -rompath ./roms \
    -pluginspath ./plugins -skip_gameinfo -window -nomaximize \
    -midiin1 "$O/probe.mid" -nvram_directory "$O/nv" -cfg_directory "$O/cfg" -snapshot_directory "$O/snap" \
    -autoboot_script "$HERE/probe6.lua" -nothrottle -sound none -wavwrite "$O/run.wav" ) > "$O/run.log" 2>&1
cat "$O/versions.txt" "$O/take.txt"
