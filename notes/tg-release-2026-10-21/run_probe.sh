#!/bin/bash
# run_probe.sh EMU_DIR OUT -- one release-probe run (README.md here): probe.mid on MIDI IN 1, probe.lua's keybed note,
# the computed stream only (-nothrottle -sound none -wavwrite OUT/run.wav), -bios v13 (program 893), the real card
# image, fresh nvram/cfg. OUT is scratch (~/compartilhado/tmp/..., never /tmp). Writes OUT/{take,tgw,voices}.txt.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EMU="$(cd "${1:?usage: run_probe.sh EMU_DIR OUT}" && pwd)"
O="$(mkdir -p "${2:?}" && cd "$2" && pwd)"
rm -rf -- "${O:?}/nv" "${O:?}/cfg" "${O:?}/snap"; mkdir -p "$O/nv" "$O/cfg" "$O/snap"
rm -f -- "${O:?}/run.wav"
python3 -I "$HERE/gen_probe_mid.py" "$O/probe.mid" > "$O/versions.txt"
echo "emulator md5 $(md5sum < "$EMU/kn7000" | cut -c1-32)" >> "$O/versions.txt"
( cd "$EMU" && env TR_OUT="$O" DISPLAY="${DISPLAY:-:0}" timeout 1200 ./kn7000 kn7000 -bios v13 -rompath ./roms \
    -pluginspath ./plugins -skip_gameinfo -window -nomaximize -harddisk sdcard_from_real_kn7000.img \
    -midiin1 "$O/probe.mid" -nvram_directory "$O/nv" -cfg_directory "$O/cfg" -snapshot_directory "$O/snap" \
    -autoboot_script "$HERE/probe.lua" -nothrottle -sound none -wavwrite "$O/run.wav" ) > "$O/run.log" 2>&1
cat "$O/versions.txt" "$O/take.txt"
