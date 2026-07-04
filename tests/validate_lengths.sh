#!/bin/bash
# Validate the MN10300 instruction-length decoder against MAME unidasm over the
# real KN7000 program ROM. Requires: g++, a unidasm built with the mn10300 arch,
# and the extracted kn7000_program.rom.
#
# Usage:
#   ROM=/path/kn7000_program.rom UNIDASM=/path/unidasm ./validate_lengths.sh
#
# Defaults assume the sibling repos / staged copies used during development.
set -euo pipefail
cd "$(dirname "$0")"

ROM="${ROM:-../../kn7000_extraction/output/kn7000_program.rom}"
UNIDASM="${UNIDASM:-../../mame-sony-video/unidasm}"
BASE=0x48400000
START=0x80
END=0x186000   # end of program code region 1

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "==> disassembling code region with unidasm"
# NOTE: unidasm mis-parses a decimal -basepc; it MUST be a 0x-prefixed hex string.
BASEPC="$(printf '0x%x' $((BASE + START)))"
"$UNIDASM" "$ROM" -arch mn10300 -basepc "$BASEPC" -skip $START \
    -count $((END - START)) > "$tmp/ud.txt"

echo "==> building ground truth (offset length illegal)"
python3 - "$tmp/ud.txt" $BASE > "$tmp/gt.txt" <<'PY'
import re, sys
base = int(sys.argv[2], 16)
for line in open(sys.argv[1]):
    m = re.match(r"([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2} )+?)\s{2,}(\S+)", line)
    if not m:
        continue
    off = int(m.group(1), 16) - base
    nbytes = len(m.group(2).split())
    illegal = 1 if m.group(3).strip() == "?" else 0
    print(f"{off:x} {nbytes} {illegal}")
PY

echo "==> compiling validator"
g++ -O2 -std=c++17 -o "$tmp/mn10300_length" mn10300_length.cpp

echo "==> running"
"$tmp/mn10300_length" "$ROM" "$tmp/gt.txt"
