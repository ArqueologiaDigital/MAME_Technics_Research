#!/bin/bash
# KN5000 HELD-NOTE sweep: for each SOUND GROUP in a list, hold one key for several
# seconds. Writes a per-note-on CSV, a raw tone-generator bus trace, a marks file
# (exact emulated t_on/t_off of every hold) and a WAV.
#
#   kn5000_capture_hold.sh <soundgroup[,soundgroup...]> <pcm|sine> <tag> [seconds]
#
# With ONE key held and nothing else sounding, the rendered WAV IS the per-voice
# amplitude envelope -- which is the measurement this defect needs. A level metric
# (rms/peak/clipping over a whole run) CANNOT see "it decayed while the key was down";
# only the envelope over the hold can, and tools/kn5000_hold_analyze.py reads it.
#
# Same private-directory discipline as kn5000_capture_perf.sh: every run gets its own
# nvram/, cfg/ and snapshot/ so parallel runs cannot contaminate each other and the
# driver never restores a previous run's work DRAM.
set -u
ROOT="${KN5_CAPTURE_ROOT:-/tmp/kn5000-hold}"
BUILD=/home/fsanches/compartilhado/kn7000_mame_build
SOUNDS="$1"; MODE="$2"; TAG="$3"; SECS="${4:-40}"

RD="$ROOT/run/$TAG"
rm -rf "$RD"; mkdir -p "$RD/nvram" "$RD/snap" "$RD/cfg"

TGVAL=0; [ "$MODE" = "sine" ] && TGVAL=1
printf '%s\n' '<?xml version="1.0"?>' '<mameconfig version="10">' \
  '    <system name="kn5000">' '        <input>' \
  '            <port tag=":AREA" type="DIPSWITCH" mask="6" defvalue="6" value="2" />' \
  "            <port tag=\":TGMODE\" type=\"CONFIG\" mask=\"1\" defvalue=\"0\" value=\"$TGVAL\" />" \
  '        </input>' '    </system>' '</mameconfig>' > "$RD/cfg/kn5000.cfg"

cd "$BUILD" || exit 1
export KN5000_NOTELOG="$RD/notes.csv"
export KN5_SOUNDSEQ="$SOUNDS"
export KN5_T0="${KN5_T0:-14.0}" KN5_HOLD="${KN5_HOLD:-8.0}" KN5_SETTLE="${KN5_SETTLE:-3.0}" KN5_GAP="${KN5_GAP:-2.0}"
export KN5_KEYPORT="${KN5_KEYPORT:-KEY2}" KN5_KEYMASK="${KN5_KEYMASK:-1}"
export KN5_BUSLOG="$RD/bus.txt" KN5_MARKS="$RD/marks.txt"

DISPLAY=:0 timeout $((SECS * 8 + 240)) ./kn7000 kn5000 \
    -rompath ./roms -skip_gameinfo -autoboot_delay 0 \
    -seconds_to_run "$SECS" \
    -cfg_directory "$RD/cfg" -nvram_directory "$RD/nvram" \
    -snapshot_directory "$RD/snap" \
    -autoboot_script /home/fsanches/compartilhado/kn7000_mame/tools/kn5000_hold_note.lua \
    -wavwrite "$RD/out.wav" > "$RD/mame.log" 2>&1
echo "exit=$? tag=$TAG sounds=$SOUNDS mode=$MODE holds=$(grep -vc '^#' "$RD/marks.txt" 2>/dev/null) rows=$(wc -l < "$RD/notes.csv" 2>/dev/null)"
