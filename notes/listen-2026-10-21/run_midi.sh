#!/bin/bash
# run_midi.sh EMU_DIR OUT on|off -- one take of listen.mid on MIDI IN 1 (README.md here), the computed stream only:
# -nothrottle -sound none -wavwrite OUT/run.wav, -bios v13 (program 893), the real card image, fresh nvram/cfg.
# BYPASS=1 sets KN7000_DSP_BYPASS_SCRATCH (only a binary built with ../dsp-noise-2026-10-21/bypass-scratch.patch
# honours it: the SHARC stays halted and the bridge passes the tone generator through).
# OUT is scratch (~/compartilhado/tmp/..., never /tmp). Prints midi_take.lua's log.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EMU="$(cd "${1:?usage: run_midi.sh EMU_DIR OUT on|off}" && pwd)"
O="$(mkdir -p "${2:?}" && cd "$2" && pwd)"
REV="${3:?on or off}"
rm -rf -- "${O:?}/nv" "${O:?}/cfg" "${O:?}/snap"; mkdir -p "$O/nv" "$O/cfg" "$O/snap"
rm -f -- "${O:?}/run.wav"
ENVS=(LT_OUT="$O" LT_REVERB="$REV" DISPLAY="${DISPLAY:-:0}")
[ "${BYPASS:-0}" = 1 ] && ENVS+=(KN7000_DSP_BYPASS_SCRATCH=1)
echo "emulator md5 $(md5sum < "$EMU/kn7000" | cut -c1-32) reverb $REV bypass ${BYPASS:-0} listen.mid md5 $(md5sum < "$HERE/listen.mid" | cut -c1-32)" > "$O/versions.txt"
( cd "$EMU" && env "${ENVS[@]}" timeout 900 ./kn7000 kn7000 -bios v13 -rompath ./roms -pluginspath ./plugins \
    -skip_gameinfo -window -nomaximize -harddisk sdcard_from_real_kn7000.img -midiin1 "$HERE/listen.mid" \
    -nvram_directory "$O/nv" -cfg_directory "$O/cfg" -snapshot_directory "$O/snap" \
    -autoboot_script "$HERE/midi_take.lua" -nothrottle -sound none -wavwrite "$O/run.wav" ) > "$O/run.log" 2>&1
cat "$O/take.txt"
