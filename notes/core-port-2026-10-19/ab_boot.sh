#!/bin/bash
# ab_boot.sh BIN_A BIN_B OUTDIR [ROMPATH] -- do two overlay binaries boot every MN10300 model to the same screens?
# Written for the CPU-core port of 2026-10-19 (README.md here): BIN_A is the binary before it, BIN_B after.
# For each case below, each binary boots with no media, fresh settings and NVRAM, -log on, and saves snapshots at
# the emulated times in TIMES (snaps.lua). The KN7000's boot splash is a JPEG the firmware decodes in software,
# with bsch in its Huffman decoder, so the early frames check that instruction. Prints one line per case:
#   case  = (identical) or X (different) per snapshot  unimplemented/illegal-opcode and divide-by-zero log lines,
#         A's and B's; those lines are kept in OUTDIR/<case>/{A,B}/opcodes.log (the rest of error.log is deleted).
# The old core logged each divide by zero; the new one sets V and logs nothing, so those lines are expected only in A.
# Snapshots land in OUTDIR/<case>/{A,B}/snap/<driver>/NNNN.png. ROMPATH defaults to the published folder's roms/.
set -euo pipefail
A="$(readlink -f "$1")"; B="$(readlink -f "$2")"; OUT="$(mkdir -p "$3" && cd "$3" && pwd)"
ROMPATH="$(readlink -f "${4:-$HOME/compartilhado/kn7000-emulator/roms}")"
HERE="$(cd "$(dirname "$0")" && pwd)"
TIMES="${TIMES:-2 3 4 5 6 8 12 20 45}"
CASES="${CASES:-kn7000:v16 kn7000:v15 kn7000:v13 kn7000:sp7001 kn6000: kn6500: kn2400: kn2600:}"
for C in $CASES; do
  M="${C%%:*}"; BIOS="${C#*:}"; NAME="$M${BIOS:+-$BIOS}"
  for S in A B; do
    BIN="$A"; [ "$S" = B ] && BIN="$B"
    O="$OUT/$NAME/$S"; mkdir -p "$O"
    ( cd "$O" && SNAP_TIMES="$TIMES" DISPLAY="${DISPLAY:-:0}" timeout 900 "$BIN" "$M" ${BIOS:+-bios "$BIOS"} \
        -rompath "$ROMPATH" -hashpath "$HOME/compartilhado/kn7000-emulator/hash" -window -nothrottle -skip_gameinfo \
        -log -cfg_directory cfg -nvram_directory nv -snapshot_directory snap \
        -autoboot_script "$HERE/snaps.lua" > run.log 2>&1 ) || true
    # error.log runs to ~200 MB (mostly DSP and I/O traces): keep only the opcode lines
    grep -E "unimplemented|illegal|by zero" "$O/error.log" > "$O/opcodes.log" || true
    rm -f -- "${O:?}/error.log"
  done
  res=""
  for P in "$OUT/$NAME/A/snap/$M"/*.png; do
    [ -e "$P" ] || { res="no snapshots"; break; }
    Q="$OUT/$NAME/B/snap/$M/$(basename "$P")"
    if [ -e "$Q" ] && cmp -s "$P" "$Q"; then res="$res ="; else res="$res X"; fi
  done
  ua=$(wc -l < "$OUT/$NAME/A/opcodes.log"); ub=$(wc -l < "$OUT/$NAME/B/opcodes.log")
  echo "$NAME  snapshots(${TIMES// /,}):$res  unimplemented/illegal/divide-by-zero log lines A=$ua B=$ub"
done
