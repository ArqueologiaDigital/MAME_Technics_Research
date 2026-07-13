#!/bin/bash
# dis.sh ADDR NBYTES [tag]
# Disassemble NBYTES at firmware/library ADDR using unidasm.
IMG=/home/fsanches/compartilhado/kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin
UNIDASM=/home/fsanches/compartilhado/mame-sony-video/unidasm
ADDR=$1
N=$(( ${2:-64} ))
TAG=${3:-a}
ADDRD=$(( ADDR ))
if [ $ADDRD -ge $((0x4C000000)) ]; then
  OFF=$(( 0x3B8FD1 + (ADDRD - 0x4C000000) ))
else
  OFF=$(( ADDRD - 0x48400000 ))
fi
TMP=/tmp/dis_${TAG}.bin
dd if=$IMG of=$TMP bs=1 skip=$OFF count=$N status=none
$UNIDASM $TMP -arch mn10300 -basepc $(printf '0x%X' $ADDRD)
