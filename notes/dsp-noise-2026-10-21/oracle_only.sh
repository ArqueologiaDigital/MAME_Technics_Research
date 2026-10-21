#!/bin/bash
# oracle_only.sh EMU_DIR OUT -- the gate's KN7000 audio oracle alone (tools/gate.sh, "audio oracle"), without the rest
# of the gate: the same throwaway nvram (EMU_DIR/nvram minus kn7000/ic23), the kn7000 liveness run that precedes it in
# the gate (it writes nvram the oracle then reads), IC23 cleared again, then the 22 s money.lua run with -wavwrite.
# Prints the WAV's md5, to compare with gate.sh's ORACLE_MD5. OUT is scratch (~/compartilhado/tmp/..., never /tmp).
set -uo pipefail
RIGS="$(cd "$(dirname "$0")/../../tools/rigs" && pwd)"
EMU_DIR="$(cd "${1:?usage: oracle_only.sh EMU_DIR OUT}" && pwd)"
O="$(mkdir -p "${2:?usage: oracle_only.sh EMU_DIR OUT}" && cd "$2" && pwd)"
rm -rf -- "${O:?}/nv" "${O:?}/cfg"; mkdir -p "$O/nv" "$O/cfg"
cp -r "$EMU_DIR/nvram/." "$O/nv/" 2>/dev/null
rm -f -- "${O:?}/nv/kn7000/ic23"
cd "$EMU_DIR" || exit 1
LIVENESS_AT=25 LIVENESS_MIN=11 DISPLAY="${DISPLAY:-:0}" timeout 260 ./run.sh kn7000 -window -nothrottle \
  -seconds_to_run 27 -nvram_directory "$O/nv" -autoboot_script "$RIGS/liveness.lua" 2>&1 | grep -m1 '^LIVENESS'
rm -f -- "${O:?}/nv/kn7000/ic23" "${O:?}/o.wav"
DISPLAY="${DISPLAY:-:0}" timeout 500 ./run.sh kn7000 -window -nothrottle -seconds_to_run 22 \
  -autoboot_script "$RIGS/money.lua" -wavwrite "$O/o.wav" -cfg_directory "$O/cfg" -nvram_directory "$O/nv" \
  -harddisk sdcard_from_real_kn7000.img > "$O/oracle.log" 2>&1
echo "emulator md5 $(md5sum < "$EMU_DIR/kn7000" | cut -c1-32)"
echo "oracle md5 $(md5sum < "$O/o.wav" | cut -c1-32)  ($(grep -m1 'Average speed' "$O/oracle.log"))"
