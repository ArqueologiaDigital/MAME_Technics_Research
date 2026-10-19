#!/bin/bash
# thunk_check.sh BIN OUTDIR -- does each KN7000 firmware version's own interrupt thunk agree with kn7000_bios_info?
# Run on a build that boots every BIOS through the firmware-built thunk (upstream's driver: set_vector_base
# 0x50000000), e.g. the v1.3 PR build ~/compartilhado/mame-pr-kn7000-v13/kn13, with ROMPATH set to a ROM folder
# without the 4 MB IC18 and 2 MB IC19 files (that build still declares them as 8 MB NO_DUMP and stops on them).
# For each BIOS it boots 30 s and prints three PROBE lines:
#   thunk  the 16 bytes at 0x50000000: cb (nop), then dc d32 = jmp (d32, PC) from 0x50000001, so the entry the
#          firmware sends interrupts to is 0x50000001 + d32 (mod 2^32), e.g. 25de03fc -> 0x4C03DE26 on v16;
#   quick, sched  the first 16 bytes the running library holds at the table's two entry points, which must be
#          the handler prologue cff8f8fe... on every version.
set -euo pipefail
BIN="$(readlink -f "$1")"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
declare -A Q=([sp7001]=0x4C03E2C6 [v16]=0x4C03DDA0 [v15]=0x4C03DDA0 [v13]=0x4C03DD8D)
declare -A S=([sp7001]=0x4C03E34C [v16]=0x4C03DE26 [v15]=0x4C03DE26 [v13]=0x4C03DE13)
for B in sp7001 v16 v15 v13; do
  O="$OUT/$B"; mkdir -p "$O"
  cat > "$O/cmd.txt" <<CMD
wait 30
lua local sp=manager.machine.devices[":maincpu"].spaces["program"]; local h=function(a,n) local s="" for i=0,n-1 do s=s..string.format("%02x",sp:read_u8(a+i)) end return s end; emu.print_error("PROBE thunk " .. h(0x50000000,16)); emu.print_error("PROBE quick ${Q[$B]} " .. h(${Q[$B]},16)); emu.print_error("PROBE sched ${S[$B]} " .. h(${S[$B]},16))
exit
CMD
  : > "$O/cmd.txt.log"
  ( cd "$(dirname "$BIN")" && REMOTE_CMD="$O/cmd.txt" DISPLAY="${DISPLAY:-:0}" timeout 300 "$BIN" kn7000 -bios $B \
      -rompath "${ROMPATH:-$HOME/compartilhado/technics_romsets}" -window -nothrottle -skip_gameinfo \
      -cfg_directory "$O/cfg" -nvram_directory "$O/nv" -snapshot_directory "$O/snap" \
      -autoboot_script "$HOME/compartilhado/kn7000_mame/tools/rigs/remote.lua" > "$O/run.log" 2>&1 ) || true
  echo "$B: $(grep '^PROBE' "$O/run.log" | tr '\n' ' ')"
done
