#!/usr/bin/env bash
# midi_roundtrip.sh -- the MIDI-ONLY end-to-end test of the SysEx debug monitor.
#
#   ./midi_roundtrip.sh [OUTDIR]
#
# QUESTION IT ANSWERS
#   Can an EXTERNAL program drive the monitor and read its answers back with NOTHING but MIDI?
#   No Lua, no memory taps, no debugger -- the same instrument that will be available when the
#   EPROM is in the real machine, which is the whole point (Felipe, 2026-09-14: "the real device
#   does not let us inspect its internals as easily as we do with lua scripting").
#
# HOW
#   in   a Standard MIDI File on `-midiin'   (deterministic; replays identically every run)
#   out  ALSA's "Midi Through Port-0" on `-midiout', captured by `aseqdump', a program that knows
#        nothing about MAME or about this project
#
# WHAT EACH CASE PROVES, and what PASS looks like
#
#   IDENT   send  F0 7E 7D 01 F7
#           want  F0 7E 7D 7F 01 00 F7
#           The reply is a ROM constant, so this tests the TRANSPORT only: hook reached, message
#           claimed, block queued, transmitter woken, bytes shifted out at 31250 baud.
#
#   PEEK    send  F0 7E 7D 02 0F 0B 0A 02 03 06 F7        (address 0x00FBA236, 6 nibbles MSB first)
#           want  F0 7E 7D 7E 0F 00 07 0E 07 0D 07 0F 00 01 00 00 0F 07 00 00 F7
#           SELF-VERIFYING: 0xFBA236 is the monitor's OWN reply table, so the right answer is
#           known before the machine runs.  Nibble-decoded the payload is
#               F0 7E 7D 7F 01 00 F7 00
#           which is that table plus its first pad byte.  This tests the DATA PATH: CPU-1 memory
#           read at an address that arrived over MIDI, returned over MIDI.
#
# ⚠ THE TEN-SECOND FLOOR IS NOT OPTIONAL, AND IT IS AN OFFSET, NOT A DEADLINE.
#   `midiin_device' sets m_sequence_start = std::max(machine().time(), attotime(10,0)) -- "to
#   allow the keyboards to initialize" -- and then plays the file FROM THERE.  So a file timestamp
#   of T seconds reaches the machine at 10 + T.  Both mistakes are easy and both look identical
#   (an empty capture): too SHORT a run plays nothing, and too LATE a timestamp plays nothing.
#   Here the SysEx sits at T = 1 s, so it arrives at ~11 s of a 16 s run.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$(mktemp -d)}"
MAME="${MAME:-$HOME/compartilhado/kn7000_mame_build/kn7000}"
STOCK="${STOCK:-$HOME/compartilhado/kn7000_mame_build/roms/wsa1r}"
PORT="${PORT:-Midi Through Port-0}"
DUMPPORT="${DUMPPORT:-14:0}"
mkdir -p "$OUT"

echo "=== 1. build the patched prom_a"
"$HERE/build.sh" "${SRC:-$HOME/compartilhado/kn5000-roms-disasm/wsa1/original_ROMs/wsa1_prom_a.ic12}" \
    "$OUT/patched_ic12.bin" >"$OUT/build.log" 2>&1 || { cat "$OUT/build.log"; exit 1; }
grep -E "gate [0-9] (PASSED|FAILED)" "$OUT/build.log"

echo "=== 2. assemble a rompath: the patched prom_a, everything else the stock dump"
mkdir -p "$OUT/roms/wsa1r"
cp "$OUT/patched_ic12.bin" "$OUT/roms/wsa1r/qsigcwsa1ax.ic12"
for f in qsigcwsa1bx.ic13 qsigcwsa1cx.ic28 qsigcwsa1dx.ic21; do
    ln -sf "$STOCK/$f" "$OUT/roms/wsa1r/$f"
done

run_case() {                       # run_case NAME ROMPATH "hex,bytes,in" "EXPECTED REPLY"|NONE
    local name="$1" roms="$2" send="$3" want="$4"
    python3 "$HERE/make_sysex_mid.py" "$OUT/$name.mid" --at-seconds 1.0 --bytes "$send" >/dev/null
    timeout 45 aseqdump -p "$DUMPPORT" >"$OUT/$name.cap" 2>&1 &
    local cap=$!
    sleep 1
    #  Run from $OUT so MAME's cfg/, nvram/ and snap/ land in the scratch directory instead of
    #  the source tree -- and so each invocation starts from the same (absent) saved state, which
    #  is what makes the capture comparable run to run.  ⚠ This is NOT the private-cfg habit that
    #  once hid a real user bug: nothing here is a user-facing setting, and the machine under test
    #  is a patched ROM that no user has.
    ( cd "$OUT" && timeout 40 "$MAME" wsa1r -rompath "$roms" \
        -midiin "$OUT/$name.mid" -midiout "$PORT" \
        -skip_gameinfo -window -seconds_to_run 16 >"$OUT/$name.log" 2>&1 ) || true
    wait $cap 2>/dev/null || true
    local got
    got="$(sed -n 's/.*System exclusive *//p' "$OUT/$name.cap" | head -1 | tr -s ' ' | sed 's/ *$//')"
    #  ⚠ A CAPTURE THAT SAW NOTHING AT ALL IS NOT A RESULT, it is a broken instrument.  Every run
    #  of this machine emits Active Sensing continuously, so an empty capture means aseqdump never
    #  connected or MAME never opened the port -- which would make the NONE case pass for the
    #  wrong reason.  Demand the background traffic before reading anything into the SysEx line.
    if ! grep -q "Active Sensing" "$OUT/$name.cap"; then
        echo "  ❌ $name -- NO MIDI AT ALL on $DUMPPORT (not even Active Sensing); the capture is"
        echo "       not an instrument this run.  Check the port name and that aseqdump started."
        FAIL=1
        return
    fi
    if [ "$want" = "NONE" ]; then
        if [ -z "$got" ]; then
            echo "  ✅ $name  (control: no SysEx, as required)"
        else
            echo "  ❌ $name  (control: expected NO SysEx, got $got)"
            FAIL=1
        fi
    elif [ "$got" = "$want" ]; then
        echo "  ✅ $name  $got"
    else
        echo "  ❌ $name"
        echo "       want: $want"
        echo "       got : ${got:-<nothing captured>}"
        FAIL=1
    fi
}

echo "=== 3. drive it over MIDI and read the answers back over MIDI"
FAIL=0
run_case ident "$OUT/roms" "F0,7E,7D,01,F7" \
    "F0 7E 7D 7F 01 00 F7"
run_case peek  "$OUT/roms" "F0,7E,7D,02,0F,0B,0A,02,03,06,F7" \
    "F0 7E 7D 7E 0F 00 07 0E 07 0D 07 0F 00 01 00 00 0F 07 00 00 F7"

#  ★ THE NEGATIVE CONTROL, and it is the reason the two ✅s above mean anything.  The identical
#  stimulus against the UNPATCHED ROM must produce NO SysEx.  Without it "a reply appeared" is
#  compatible with the firmware answering by itself -- and 0x7E IS an identifier the stock parser
#  accepts, so that is not a far-fetched alternative.
echo "=== 4. negative control: the same stimulus against the STOCK prom_a"
run_case stock "$(dirname "$STOCK")" "F0,7E,7D,01,F7" NONE

echo "=== artefacts in $OUT"
exit $FAIL
