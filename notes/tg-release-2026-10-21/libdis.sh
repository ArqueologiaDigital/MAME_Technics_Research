#!/bin/bash
# libdis.sh LIB.BIN ADDR [BYTES] -- disassemble the dumped sound library (libdump.lua) from one entry point, so that
# the variable-length MN10300 code is decoded in step from a known instruction start (README.md here).
set -euo pipefail
LIB="${1:?lib.bin}"; A=$(( ${2:?address} )); N=$(( ${3:-0x200} ))
S="$(mktemp)"
dd if="$LIB" of="$S" bs=1 skip=$(( A - 0x4C000000 )) count=$N status=none
"${UNIDASM:-$HOME/compartilhado/mame/unidasm}" "$S" -arch mn10300 -basepc "$(printf '0x%X' $A)"
rm -f -- "${S:?}"
