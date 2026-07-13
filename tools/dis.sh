#!/bin/bash
# dis.sh 0xADDR [COUNT]  -- disassemble MN10300 at hex ADDR from the decompressed program image.
# Pass -basepc as the HEX string (unidasm mislabels a decimal basepc).
#
# FIX 2026-07-13: the old version used `dd ... bs="$COUNT" ... count=1` into a SHARED /tmp/w.bin.
# Two bugs: (1) a hex COUNT (e.g. 0x200) made `bs=0x200` invalid so dd failed and left a STALE
# /tmp/w.bin -> unidasm disassembled whatever the previous call wrote (this is what produced the
# phantom `movhu (0x98070000)` strap-read template at every address); (2) concurrent callers raced
# on /tmp/w.bin. Now: arithmetic COUNT (handles hex+decimal), a per-invocation temp file, bs=1.
BIN=/home/fsanches/compartilhado/kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin
UNI=/home/fsanches/compartilhado/mame-sony-video/unidasm
AH="$1"; COUNT=$(( ${2:-96} ))
OFF=$(( AH - 0x48400000 ))
TMP=$(mktemp /tmp/dis.XXXXXX) || exit 1
trap 'rm -f "$TMP"' EXIT
dd if="$BIN" of="$TMP" bs=1 skip="$OFF" count="$COUNT" 2>/dev/null
"$UNI" "$TMP" -arch mn10300 -basepc "$AH" 2>/dev/null
