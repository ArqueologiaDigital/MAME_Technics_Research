#!/bin/bash
# check_ic23.sh MAME_BINARY OUTDIR [BIOS] -- does the KN7000's IC23 keep the panel memories across runs, and what does
# the firmware do when they are damaged? Each run boots kn7000 -bios BIOS (default v16) for 40 s with no media and
# the same -nvram_directory OUTDIR/nv, under ic23_probe.lua (which prints the firmware's verdict on IC23 and then
# presses POWER OFF, or quits plainly), and the saved file is read with ic23_file.py:
#   1 blank          no ic23 file: IC23 starts all zero, as the RAM placeholder did; POWER OFF
#   2 again          boots from what run 1 saved: the firmware should find its checksum valid; POWER OFF
#   3 header-hit     byte 0x100 flipped first: inside the 0x7A0-byte header (the live panel settings), which the
#                    checksum covers; the Another World builds' game image at 0x44000000 lands here
#   4 after-header   did the firmware throw the damaged header away (factory settings) and stamp again?
#   5 store-hit      byte 0x30000 flipped: inside the PANEL MEMORY store (104 records, 0x824-0x30173), which the
#                    checksum does NOT cover; the Another World VM state lands here through the 256 KB repeat
#   6 after-store    does the flipped byte survive a boot unnoticed?
#   7 change-plain   press BRASS at 30 s (changes the live settings in the header), then quit MAME directly
#                    instead of POWER OFF, as closing the window does
#   8 after-plain    what the next boot makes of that: the header no longer matches the last stamp
#   9 change-power   press BRASS at 30 s, then POWER OFF
#  10 after-power    the change is kept and the stamp is valid
# The validity byte is read only where its address is known (v16, v15: 0x5006CC80).
set -euo pipefail
# MAME keeps a non-default BIOS's NVRAM in its own folder (-bios sp7001 -> nvram/kn7000_0/, v13 -> kn7000_4/)
ic23() { ls "$1"/nv/kn7000*/ic23 2>/dev/null | head -1; }
BIN="$(readlink -f "$1")"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"; BIOS="${3:-v16}"
HERE="$(cd "$(dirname "$0")" && pwd)"; EMU="${EMU_DIR:-$HOME/compartilhado/kn7000-emulator}"
VALID=""; case "$BIOS" in v16|v15) VALID=0x5006CC80 ;; esac
rm -rf -- "${OUT:?}/nv"; mkdir -p "$OUT/nv"
run() {   # run NAME POWER(0/1) [PANEL_PRESS]
  local P=""; [ "$2" = 1 ] && P=1
  ( cd "$OUT" && IC23_AT=40 IC23_VALID="$VALID" IC23_POWER="$P" IC23_PRESS="${3:-}" DISPLAY="${DISPLAY:-:0}" timeout 600 "$BIN" kn7000 \
      -bios "$BIOS" -rompath "$EMU/roms" -pluginspath "$EMU/plugins" -skip_gameinfo -window -nothrottle \
      -cfg_directory "$OUT/cfg-$1" -nvram_directory "$OUT/nv" -harddisk "" \
      -autoboot_script "$HERE/ic23_probe.lua" > "$OUT/run-$1.log" 2>&1 ) || true
  echo "$1: $(grep -m1 '^PROBE t=' "$OUT/run-$1.log" || echo 'no PROBE line') $(grep -c 'pressed POWER' "$OUT/run-$1.log" | sed 's/^1$/[POWER OFF]/;s/^0$/[plain exit]/')"
  grep '^PROBE power latch' "$OUT/run-$1.log" | sed 's/^/   /' || true
  echo "   saved file: $(python3 -I "$HERE/ic23_file.py" "$(ic23 "$OUT")")"
  cp "$(ic23 "$OUT")" "$OUT/ic23-after-$1.bin"
}
bytes() { echo "byte 0x100 = $(xxd -s 0x100 -l 1 -p "$1"), byte 0x30000 = $(xxd -s 0x30000 -l 1 -p "$1")"; }
run 1-blank 1
run 2-again 1
echo "   before run 3: $(python3 -I "$HERE/ic23_file.py" "$(ic23 "$OUT")" --corrupt 100 | head -1)"
run 3-header-hit 1
run 4-after-header 1
echo "   before run 5: $(python3 -I "$HERE/ic23_file.py" "$(ic23 "$OUT")" --corrupt 30000 | head -1)"
run 5-store-hit 1
run 6-after-store 1
run 7-change-plain 0 "CPR_SEG9 08"
run 8-after-plain 1
run 9-change-power 1 "CPR_SEG9 08"
run 10-after-power 1
for f in 2-again 4-after-header 6-after-store 8-after-plain 10-after-power; do echo "   after $f: $(bytes "$OUT/ic23-after-$f.bin")"; done
echo "   header bytes that differ, run 8's saved file vs run 10's: $(cmp -l "$OUT/ic23-after-8-after-plain.bin" "$OUT/ic23-after-10-after-power.bin" | awk '$1 <= 1956 {n++} END {print n+0}')"
