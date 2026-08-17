#!/usr/bin/env bash
# dis_kn5000.sh 0xADDR [COUNT] [ROM]  -- disassemble TLCS-900 at hex ADDR from a KN5000 program ROM.
#
# The KN5000 counterpart to tools/dis.sh (which is MN10300, for the KN7000 family). This session
# hand-rolled `dd | unidasm -arch tlcs900` about a dozen times before admitting it was a tool.
#
#   ./tools/dis_kn5000.sh 0xEF08D4              # 96 bytes from the v10 ROM
#   ./tools/dis_kn5000.sh 0xFC5761 200
#   ./tools/dis_kn5000.sh 0x8E94 64 kn5000_v5_program.rom
#
# The main program ROM maps at 0xE00000..0xFFFFFF, so file offset = ADDR - 0xE00000.
#
# ⚠ INHERITS dis.sh's HARD-WON FIX: a per-invocation temp file, and an ARITHMETIC count. The
#   MN10300 version once used `bs="$COUNT"` into a SHARED /tmp/w.bin; a hex COUNT made `dd` fail
#   and leave the PREVIOUS call's bytes behind, so unidasm confidently disassembled stale data --
#   which is where the phantom `movhu (0x98070000)` strap-read "at every address" came from.
#   Do not reintroduce a shared scratch file here.
#
# ⚠ TLCS-900 CALLER SEARCH: routines are commonly entered by `calr` (relative), so grepping for a
#   target's absolute bytes finds nothing. Use tools/tlcs900_callers.py, which decodes both forms.
set -uo pipefail

ROMDIR="${ROMDIR:-/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000}"
UNI="${UNI:-/home/fsanches/compartilhado/mame-sony-video/unidasm}"
BASE="${BASE:-0xE00000}"

AH="${1:?usage: dis_kn5000.sh 0xADDR [COUNT] [ROMFILE]}"
COUNT=$(( ${2:-96} ))
ROM="${3:-kn5000_v10_program.rom}"

case "$ROM" in
	/*) ROMPATH="$ROM" ;;
	*)  ROMPATH="$ROMDIR/$ROM" ;;
esac
[ -f "$ROMPATH" ] || { echo "dis_kn5000: no such ROM: $ROMPATH" >&2; exit 1; }
[ -x "$UNI" ] || { echo "dis_kn5000: no unidasm at $UNI" >&2; exit 1; }

OFF=$(( AH - BASE ))
if [ "$OFF" -lt 0 ]; then
	echo "dis_kn5000: 0x$(printf %X "$AH") is below the map base $BASE" >&2
	exit 1
fi

TMP=$(mktemp /tmp/dis5k.XXXXXX) || exit 1
trap 'rm -f "$TMP"' EXIT
dd if="$ROMPATH" of="$TMP" bs=1 skip="$OFF" count="$COUNT" 2>/dev/null

GOT=$(stat -c%s "$TMP")
if [ "$GOT" -eq 0 ]; then
	echo "dis_kn5000: read 0 bytes at offset 0x$(printf %X "$OFF") -- past the end of $ROM?" >&2
	exit 1
fi
[ "$GOT" -lt "$COUNT" ] && echo "# note: only $GOT of $COUNT bytes available (end of image)"

"$UNI" "$TMP" -arch tlcs900 -basepc "$AH"
