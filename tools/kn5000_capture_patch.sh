#!/bin/bash
# KN5000 PER-PATCH probe: select named patches (sound group + LCD page + LCD soft key) and
# either HOLD one key or sweep chromatically. Writes a per-note-on CSV, a marks file, a WAV
# and the MAME log.
#
#   kn5000_capture_patch.sh <patchseq> <pcm|sine> <hold|sweep> <tag> [seconds]
#
# e.g.  kn5000_capture_patch.sh 'flute:L2' pcm sweep jazzflute 60
#       kn5000_capture_patch.sh 'organ:L1,organ:L3,organ+:L4' pcm hold organs 90
#
# Same private-directory discipline as kn5000_capture_hold.sh: every run gets its own
# nvram/, cfg/ and snapshot/, so parallel runs cannot contaminate each other and the driver
# never restores a previous run's work DRAM (which has caused two retractions before).
set -u
ROOT="${KN5_CAPTURE_ROOT:-/tmp/kn5000-patch}"
BUILD=/home/fsanches/compartilhado/kn7000_mame_build
SEQ="$1"; MODE="$2"; PROBE="$3"; TAG="$4"; SECS="${5:-60}"

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
export KN5_PATCHSEQ="$SEQ" KN5_PROBE="$PROBE" KN5_MARKS="$RD/marks.txt"

# KN5_MIDI=<file.mid> feeds a Standard MIDI File into midiin2, which is the "kbdmidi"
# port -- the MIDI->key-bed bridge, the SECOND MIDI_PORT the driver instantiates, and the
# one Felipe drives his controller into. This is the ONLY way to control VELOCITY: the
# key-bed ioports the lua presses go through keybed_scan(), which hard-codes
# KEYBED_VELOCITY = 100. Use KN5_PROBE=idle with it so the script selects the patch from
# the panel and then leaves the notes entirely to the file.
MIDIARG=()
[ -n "${KN5_MIDI:-}" ] && MIDIARG=(-midiin2 "$KN5_MIDI")

DISPLAY=:0 timeout $((SECS * 8 + 300)) ./kn7000 kn5000 \
    -rompath ./roms -skip_gameinfo -autoboot_delay 0 \
    "${MIDIARG[@]}" \
    -seconds_to_run "$SECS" \
    -cfg_directory "$RD/cfg" -nvram_directory "$RD/nvram" \
    -snapshot_directory "$RD/snap" \
    -autoboot_script /home/fsanches/compartilhado/kn7000_mame/tools/kn5000_patch_probe.lua \
    -wavwrite "$RD/out.wav" > "$RD/mame.log" 2>&1
echo "exit=$? tag=$TAG seq=$SEQ mode=$MODE probe=$PROBE marks=$(grep -vc '^#' "$RD/marks.txt" 2>/dev/null) rows=$(( $(wc -l < "$RD/notes.csv" 2>/dev/null || echo 1) - 1 ))"
