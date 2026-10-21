#!/bin/bash
# oracle_ab.sh EMU_DIR OUT -- the gate's KN7000 audio oracle (tools/gate.sh, "audio oracle"; recipe in tools/rigs/README.md)
# run with the binary in EMU_DIR: money.lua holds the keybed C4 from 16 to 17 s, 22 s captured. The nvram is a copy
# of the published folder's without kn7000/ic23, as the gate does; the card image is used in place. Writes OUT/o.wav
# and prints its md5 (README.md here). OUT is scratch (~/compartilhado/tmp/..., never /tmp).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RIGS="$HERE/../../tools/rigs"
EMU="$(cd "${1:?usage: oracle_ab.sh EMU_DIR OUT}" && pwd)"
O="$(mkdir -p "${2:?}" && cd "$2" && pwd)"
PUB="$HOME/compartilhado/kn7000-emulator"
rm -rf -- "${O:?}/nv" "${O:?}/cfg"; mkdir -p "$O/nv" "$O/cfg"
cp -r "$PUB/nvram/." "$O/nv/"; rm -f -- "${O:?}/nv/kn7000/ic23" "${O:?}/o.wav"
( cd "$EMU" && DISPLAY="${DISPLAY:-:0}" timeout 500 ./kn7000 kn7000 -rompath ./roms -pluginspath ./plugins -skip_gameinfo \
    -window -nothrottle -seconds_to_run 22 -autoboot_script "$RIGS/money.lua" -wavwrite "$O/o.wav" \
    -cfg_directory "$O/cfg" -nvram_directory "$O/nv" -harddisk sdcard_from_real_kn7000.img ) > "$O/run.log" 2>&1
echo "emulator md5 $(md5sum < "$EMU/kn7000" | cut -c1-32) oracle md5 $(md5sum < "$O/o.wav" | cut -c1-32)"
