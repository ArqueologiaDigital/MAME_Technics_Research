#!/bin/bash
# fdc_lastbyte.sh BINARY OUTDIR SDIMG FLOPPY -- when does the firmware take a floppy sector's last byte and raise TC?
#
# Boots the kn7000 (-bios v13), opens DISK MENU > STYLE CONVERT on FLOPPY (a KN7000-formatted disk with a .CNV on it,
# as cnv_romdump's test/run_test.sh builds: build/kn7load_floppy.img) and presses OK, with fdc_lastbyte_tap.lua
# installed. Each read the DMA ends prints
#   DACKCPU <us> n=<DACK cycles so far> pc=<the ISR's DACK read> lastdma=<us of the DMA's last byte> dinsn=.. dmemq=..
# then the controller's result bytes (FDCR <us> data=..): ST0 0x04/0x00 is a normal end, 0x44 with ST1 0x80 (EN) is
# TC too late. The timing model's counters (dinsn, dmemq = quarter cycles of memory) read 0 on a binary without them.
# SDIMG is a copy of an SD card image (it is written), FLOPPY the loader floppy.
set -euo pipefail
BIN="$(readlink -f "$1")"; O="$(mkdir -p "$2" && cd "$2" && pwd)"; SD="$(readlink -f "$3")"; FL="$(readlink -f "$4")"
HERE="$(cd "$(dirname "$0")" && pwd)"
cat > "$O/cmd.txt" <<CMD
wait 30
press CPR_SEG1 04
wait 4
press CPL_SEG0 20
wait 6
lua dofile("$HERE/fdc_lastbyte_tap.lua")
press CPR_SEG6 01
wait 0.6
exit
CMD
rm -f -- "$O/cmd.txt.log"
cd "$O" && REMOTE_CMD="$O/cmd.txt" DISPLAY="${DISPLAY:-:0}" timeout 1200 "$BIN" kn7000 -bios v13 \
  -rompath "$HOME/compartilhado/kn7000-emulator/roms" -window -nothrottle -skip_gameinfo \
  -cfg_directory "$O/cfg" -nvram_directory "$O/nv" -snapshot_directory "$O/snap" \
  -autoboot_script "$HERE/../../tools/rigs/remote.lua" -flop "$FL" -harddisk "$SD" > "$O/run.log" 2>&1 || true
grep -a "DACKCPU\|FDCR" "$O/run.log"
