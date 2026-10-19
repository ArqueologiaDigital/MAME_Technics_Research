#!/bin/bash
# checks.sh MAME_BINARY OUTDIR [ROMPATH] [CHECK...] -- does the overlay's KN7000 take what the four PRs added?
# (mamedev/mame #16517 v1.3 BIOS, #16520 wave ROMs, #16523 rhythm ROM IC18, #16524 picture ROM IC19, ported into the
# overlay's own kn7000.cpp on 2026-10-19). ROMPATH defaults to the published folder's roms/ (kn7000-emulator).
# CHECKs, all by default:
#   boot     For each BIOS v16 v15 v13 sp7001: boots kn7000 -bios <name> for 45 s with no media and prints
#              release   the program's release byte (0x4840000F: 0x13, 0x15, 0x16; sp7001 0xFF);
#              table     the table's build string (header u32 at 0x4800001C points to it: 80, 84, 83);
#              window    the rhythm resource window the firmware's probe chose, from its cache in work RAM, which
#                        moves per build (tools/kn7000_bios_addresses.py --ram 0x5000775C): 40010000 = IC18;
#              styles    the style count that window's directory declares (u24 BE at +0x18 -> block, u16 BE at +2);
#              rhythm    the digits the DEBUG TOOLS box prints as RHYTHM (window - 0x10000 + 0x3FFFEC);
#              picture   the digits it prints as PICTURE (the u32 at 0x57800000 is an offset from there);
#            and saves the screen: OUTDIR/boot/<bios>/snap/kn7000/0000.png. A BIOS whose interrupt vectors are
#            wrong does not reach the main screen.
#   wave     wave_port_check.lua: sweeps both tone generators' wave ROM test ports as the firmware's checksum core
#            does and compares the four sums with the firmware's (4 of 4 OK expected; about 6 minutes).
#   debug    -bios sp7001: rolls on the chord of part-mixer columns 1, 4, 5, 8 (opens the Panel Simulator),
#            releases, presses LCDR5 (opens DEBUG TOOLS) and saves the screen after each step; the LCD of the
#            last one goes to OUTDIR/debug/debugtools_lcd.png, whose "--- SOFTWARE VERSION ---" box should
#            read RHYTHM 33 and PICTURE 7. LCDR5 is pressed twice: on the overlay (2026-10-19) the first press
#            after the Panel Simulator opens is not taken, with 2 s or 4 s of settling and a 0.3 s or 1 s hold.
# Settings and NVRAM are thrown away (fresh per run). Uses tools/rigs/remote.lua.
set -euo pipefail
BIN="$(readlink -f "$1")"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"; HERE="$(cd "$(dirname "$0")" && pwd)"
ROMPATH="$(readlink -f "${3:-$HOME/compartilhado/kn7000-emulator/roms}")"; shift 3 2>/dev/null || shift $#
[ $# -gt 0 ] || set -- boot wave debug
RIG="$HERE/../../tools/rigs/remote.lua"

run() {   # run OUTDIR AUTOBOOT_SCRIPT [MAME ARGS...]: one MAME run, fresh settings, log in OUTDIR/run.log
  local o="$1" script="$2"; shift 2
  mkdir -p "$o"
  ( cd "$(dirname "$BIN")" && DISPLAY="${DISPLAY:-:0}" timeout 1800 "$BIN" kn7000 "$@" \
      -rompath "$ROMPATH" -window -nothrottle -skip_gameinfo \
      -cfg_directory "$o/cfg" -nvram_directory "$o/nv" -snapshot_directory "$o/snap" \
      -autoboot_script "$script" > "$o/run.log" 2>&1 ) || true
}

for CHECK in "$@"; do case "$CHECK" in
boot)
  declare -A WIN=([v16]=0x5000775c [v15]=0x5000775c [v13]=0x50007758 [sp7001]=0x5000776c)
  for B in v16 v15 v13 sp7001; do
    O="$OUT/boot/$B"; mkdir -p "$O"
    cat > "$O/cmd.txt" <<CMD
wait 45
lua local sp=manager.machine.devices[":maincpu"].spaces["program"]; local u24=function(a) return (sp:read_u8(a)<<16)|(sp:read_u8(a+1)<<8)|sp:read_u8(a+2) end; local str=function(a,lo,hi) local s="" for i=0,7 do local c=sp:read_u8(a+i); if c<lo or c>hi then break end; s=s..string.char(c) end return s end; local w=sp:read_u32(${WIN[$B]}); local blk=w+u24(w+0x18); local n=(sp:read_u8(blk+2)<<8)|sp:read_u8(blk+3); emu.print_error(string.format("PROBE release=0x%02X table=%s window=%08X styles=%d rhythm=%s picture=%s", sp:read_u8(0x4840000f), str(0x48000000+sp:read_u32(0x4800001c),0x20,0x7e), w, n, str(w-0x10000+0x3fffec,0x30,0x39), str(0x57800000+sp:read_u32(0x57800000),0x30,0x39)))
snap
exit
CMD
    : > "$O/cmd.txt.log"
    REMOTE_CMD="$O/cmd.txt" run "$O" "$RIG" -bios "$B"
    echo "boot $B: $(grep '^PROBE' "$O/run.log" || echo "no PROBE line, see $O/run.log")"
  done ;;
wave)
  O="$OUT/wave"; run "$O" "$HERE/wave_port_check.lua"
  grep '^PROBE' "$O/run.log" | sed 's/^/wave: /' || echo "wave: no PROBE lines, see $O/run.log" ;;
debug)
  O="$OUT/debug"; mkdir -p "$O"
  cat > "$O/cmd.txt" <<'CMD'
wait 45
lua _G.CH={}; _G.CAP=function(tag,mask) for _,f in pairs(manager.machine.ioport.ports[":cpanel:"..tag].fields) do if f.mask==mask then f:set_value(1); _G.CH[#_G.CH+1]=f end end end
lua _G.CAP("CPC_SEG5",0x10)
wait 0.15
lua _G.CAP("CPC_SEG5",0x20)
wait 0.15
lua _G.CAP("CPC_SEG8",0x04)
wait 0.15
lua _G.CAP("CPC_SEG8",0x08)
wait 0.15
lua _G.CAP("CPC_SEG8",0x10)
wait 0.15
lua _G.CAP("CPC_SEG8",0x20)
wait 0.15
lua _G.CAP("CPC_SEG9",0x04)
wait 0.15
lua _G.CAP("CPC_SEG9",0x08)
wait 1
lua for _,f in ipairs(_G.CH) do f:set_value(0) end; emu.print_error("PROBE chord caps rolled on and released: " .. #_G.CH)
wait 4
snap
press CPR_SEG5 01 1
wait 4
snap
press CPR_SEG5 01 1
wait 4
snap
exit
CMD
  : > "$O/cmd.txt.log"
  REMOTE_CMD="$O/cmd.txt" run "$O" "$RIG" -bios sp7001
  echo "debug: $(grep '^PROBE' "$O/run.log" || echo "no PROBE line")"
  python3 -I -c "from PIL import Image; Image.open('$O/snap/kn7000/0002.png').crop((150, 50, 850, 345)).save('$O/debugtools_lcd.png')" \
    && echo "debug: DEBUG TOOLS screen: $O/debugtools_lcd.png" ;;
*) echo "unknown check $CHECK" >&2; exit 2 ;;
esac; done
