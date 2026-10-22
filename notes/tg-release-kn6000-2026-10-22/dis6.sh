#!/bin/bash
# dis6.sh PROG.BIN ADDR [BYTES] -- disassemble the KN6000 program image (mkprog6.py; loaded at 0x48400000) from one
# entry point, so that the variable-length MN10300 code is decoded in step from a known instruction start.
# The firmware also runs this code through its mirror at 0x4C000000 (a PC of 0x4C09468D is 0x4849468D here).
set -euo pipefail
P="${1:?prog.bin}"; A=$(( ${2:?address} )); N=$(( ${3:-0x200} ))
(( A >= 0x4C000000 )) && A=$(( A - 0x4C000000 + 0x48400000 ))
S="$(mktemp)"
dd if="$P" of="$S" bs=1 skip=$(( A - 0x48400000 )) count=$N status=none
"${UNIDASM:-$HOME/compartilhado/mame/unidasm}" "$S" -arch mn10300 -basepc "$(printf '0x%X' $A)"
rm -f -- "${S:?}"
