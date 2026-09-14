#!/usr/bin/env bash
# build.sh -- assemble the monitor and graft it into a prom_a image.
#
#   ./build.sh [ORIGINAL.ic12] [OUT.bin]
#
# Defaults to the project's own prom_a dump and writes ./patched_ic12.bin.
# See README.md; the design is notes/HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md sect. A5.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LLVM="${LLVM:-$HOME/compartilhado/llvm-project/build/bin}"
SRC="${1:-$HOME/compartilhado/kn5000-roms-disasm/wsa1/original_ROMs/wsa1_prom_a.ic12}"
OUT="${2:-$HERE/patched_ic12.bin}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "=== assemble (llvm-mc -triple=tlcs900, the project's own backend)"
"$LLVM/llvm-mc" -triple=tlcs900 -filetype=obj -o "$TMP/monitor.o" "$HERE/monitor.s"
"$LLVM/llvm-objcopy" -O binary --only-section=.text "$TMP/monitor.o" "$TMP/monitor.bin"
echo "    $(stat -c%s "$TMP/monitor.bin") bytes"

echo "=== patch"
python3 "$HERE/patch_rom.py" "$SRC" "$TMP/monitor.bin" "$OUT"

echo
echo "=== cross-check with MAME's OWN disassembler (a second, independent toolchain)"
UNIDASM="${UNIDASM:-$HOME/compartilhado/kn7000_mame_build/unidasm}"
if [ -x "$UNIDASM" ]; then
  dd if="$OUT" of="$TMP/hook.bin" bs=1 skip=$((0x2586E)) count=4 status=none
  "$UNIDASM" "$TMP/hook.bin" -arch tlcs900 -basepc 0xFA586E | head -1
  dd if="$OUT" of="$TMP/mon.bin" bs=1 skip=$((0x3A246)) count=67 status=none
  "$UNIDASM" "$TMP/mon.bin" -arch tlcs900 -basepc 0xFBA246
else
  echo "    (unidasm not found at $UNIDASM -- skipped)"
fi
