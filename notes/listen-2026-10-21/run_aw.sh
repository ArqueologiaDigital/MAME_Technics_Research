#!/bin/bash
# run_aw.sh OUT dsp|tg wav|live -- Another World's intro through the program menu card (README.md here), one session.
#   dsp|tg  the game's sound mode for the intro (aw_intro.lua AWI_MODE)
#   wav     -nothrottle -sound none -wavwrite OUT/run.wav: the computed stream only
#   live    throttled at normal speed, real sound output, -wavwrite OUT/run.wav as well, and pw-record capturing the
#           default sink's monitor into OUT/live.wav: what the host actually played. OUT/intro_wall.txt gets the
#           seconds from the start of the capture to the intro's start (to within the 0.05 s poll), for the trim.
# EMU (default ~/compartilhado/kn7000-emulator, the published binary), -bios v13 (program 893), CARD (default
# technics-roms-disasm kn7000/tools/kn7menu/build/card: the menu, AW\ with KN7APP.BIN 94910f68...) put into a copy
# of the real card image with kn7menu/fatimg.py, the owner's loader floppy as released, fresh nvram/cfg in OUT.
# AWI_LEN: emulated seconds of intro (default 64). AWI_SCRIPT: another autoboot script in place of aw_intro.lua (one
# that runs it, as ../tg-release-2026-10-21/aw_voices.lua does). OUT is scratch (~/compartilhado/tmp/..., never /tmp); the card
# and floppy copies are deleted afterwards. The recordings are Another World's audio: never commit them.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EMU="${EMU:-$HOME/compartilhado/kn7000-emulator}"
DISASM="${DISASM:-$HOME/compartilhado/technics-roms-disasm/kn7000}"
CARD="${CARD:-$DISASM/tools/kn7menu/build/card}"
FLOPPY="$DISASM/tools/cnv_romdump/releases/2026-10-19/floppy/kn7load_floppy.img"
O="$(mkdir -p "${1:?usage: run_aw.sh OUT dsp|tg wav|live}" && cd "$1" && pwd)"
MODE="${2:?dsp or tg}"; CAP="${3:?wav or live}"
rm -rf -- "${O:?}/nv" "${O:?}/cfg"; mkdir -p "$O/nv" "$O/cfg"
rm -f -- "${O:?}/run.wav" "${O:?}/live.wav" "${O:?}/intro_mark" "${O:?}/intro_wall.txt"
cp "$EMU/sdcard_from_real_kn7000.img" "$O/sd.img"; chmod u+w "$O/sd.img"
python3 -I "$DISASM/tools/kn7menu/fatimg.py" "$O/sd.img" put "$CARD" > "$O/fatimg.txt"
cp "$FLOPPY" "$O/floppy.img"; chmod u+w "$O/floppy.img"
{
  echo "emulator md5 $(md5sum < "$EMU/kn7000" | cut -c1-32), bios v13, mode $MODE, capture $CAP"
  echo "card menu KN7APP.BIN sha1 $(sha1sum < "$CARD/KN7APP.BIN" | cut -c1-40), AW KN7APP.BIN sha1 $(sha1sum < "$CARD/AW/KN7APP.BIN" | cut -c1-40)"
  echo "floppy sha1 $(sha1sum < "$FLOPPY" | cut -c1-40), card image sha1 $(sha1sum < "$EMU/sdcard_from_real_kn7000.img" | cut -c1-40)"
} > "$O/versions.txt"
ARGS=(kn7000 -bios v13 -rompath ./roms -pluginspath ./plugins -skip_gameinfo -window -nomaximize
      -harddisk "$O/sd.img" -flop "$O/floppy.img" -wavwrite "$O/run.wav"
      -nvram_directory "$O/nv" -cfg_directory "$O/cfg" -autoboot_script "${AWI_SCRIPT:-$HERE/aw_intro.lua}")
ENVS=(AWI_OUT="$O" AWI_MODE="$MODE" AWI_LEN="${AWI_LEN:-64}" DISPLAY="${DISPLAY:-:0}")
case "$CAP" in
  wav)
    ( cd "$EMU" && env "${ENVS[@]}" timeout 1800 ./kn7000 "${ARGS[@]}" -nothrottle -sound none ) > "$O/run.log" 2>&1 ;;
  live)
    T0=$(date +%s.%N)
    pw-record -P '{ stream.capture.sink = true }' --rate 48000 --channels 2 --format s16 "$O/live.wav" &
    REC=$!
    ( cd "$EMU" && env "${ENVS[@]}" timeout 1800 ./kn7000 "${ARGS[@]}" ) > "$O/run.log" 2>&1 &
    MP=$!
    while kill -0 "$MP" 2>/dev/null; do
      if [ ! -f "$O/intro_wall.txt" ] && [ -f "$O/intro_mark" ]; then
        echo "$(date +%s.%N) $T0" | awk '{ printf "%.3f\n", $1 - $2 }' > "$O/intro_wall.txt"
      fi
      sleep 0.05
    done
    wait "$MP"
    kill "$REC"; wait "$REC" 2>/dev/null ;;
  *) echo "capture must be wav or live" >&2; exit 2 ;;
esac
rm -f -- "${O:?}/sd.img" "${O:?}/floppy.img"
cat "$O/events.txt"
