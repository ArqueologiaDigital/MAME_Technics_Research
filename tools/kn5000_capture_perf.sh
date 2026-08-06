#!/bin/bash
# One KN5000 performance capture: nav to DEMO->PERFORMANCES->SOUND->{piano|organ},
# render in {pcm|sine}, write a per-note-on CSV and a WAV.
#
#   kn5000_capture_perf.sh <piano|organ> <pcm|sine> <tag> <seconds_to_run> [nolog]
#
# Every run gets its OWN nvram/, cfg/ and snapshot/ directory so parallel runs cannot
# contaminate each other, and so the driver never restores a previous run's work DRAM
# (kn5000 persists 1 MB of work RAM as "nvram1").
#
# `nolog` leaves KN5000_NOTELOG unset, which is how the "instrumentation does not
# perturb the audio" A/B is taken with ONE binary instead of two.
set -u
ROOT="${KN5_CAPTURE_ROOT:-/tmp/kn5000-capture}"
BUILD=/home/fsanches/compartilhado/kn7000_mame_build
WHAT="$1"; MODE="$2"; TAG="$3"; SECS="$4"; NOLOG="${5:-}"

RD="$ROOT/run/$TAG"
rm -rf "$RD"; mkdir -p "$RD/nvram" "$RD/snap" "$RD/cfg"

# The render mode is carried by the PRIVATE cfg, never by ioport_field:set_value()
# (which TOGGLES a PORT_CONFNAME field, and MAME then persists the toggle). The nav
# script only READS :TGMODE back, once a second, into the run's log.
#
# :AREA is pinned too, and it is NOT cosmetic: the standing kn5000.cfg in the build tree
# carries AREA=2 and the whole capture set was taken with it. Leaving it at its default
# (6, "Other") produced a DIFFERENT audio md5 on an otherwise identical 45 s piano run
# (3ee6be6b... vs 5c84723d...), so a cfg that omits it is a different experiment.
TGVAL=0; [ "$MODE" = "sine" ] && TGVAL=1
printf '%s\n' '<?xml version="1.0"?>' '<mameconfig version="10">' \
  '    <system name="kn5000">' '        <input>' \
  '            <port tag=":AREA" type="DIPSWITCH" mask="6" defvalue="6" value="2" />' \
  "            <port tag=\":TGMODE\" type=\"CONFIG\" mask=\"1\" defvalue=\"0\" value=\"$TGVAL\" />" \
  '        </input>' '    </system>' '</mameconfig>' > "$RD/cfg/kn5000.cfg"

cd "$BUILD" || exit 1
if [ "$NOLOG" = "nolog" ]; then unset KN5000_NOTELOG; else export KN5000_NOTELOG="$RD/notes.csv"; fi
export KN5_TARGET="$WHAT" KN5_T0=12.0 KN5_GAP=2.0 KN5_SNAPS="${KN5_SNAPS:-26,32,40}"

DISPLAY=:0 timeout $((SECS * 8 + 240)) ./kn7000 kn5000 \
    -rompath ./roms -skip_gameinfo -autoboot_delay 0 \
    -seconds_to_run "$SECS" \
    -cfg_directory "$RD/cfg" -nvram_directory "$RD/nvram" \
    -snapshot_directory "$RD/snap" \
    -autoboot_script /home/fsanches/compartilhado/kn7000_mame/tools/kn5000_perf_nav.lua \
    -wavwrite "$RD/out.wav" > "$RD/mame.log" 2>&1
echo "exit=$? tag=$TAG wav=$(md5sum "$RD/out.wav" 2>/dev/null | cut -d' ' -f1) rows=$(wc -l < "$RD/notes.csv" 2>/dev/null)"
