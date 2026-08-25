#!/bin/sh
# wsa1_dis.sh IMAGE ADDR [BYTES] -- disassemble a window of a WSA1 v2 ROM.
#
# QUESTION IT ANSWERS: "is the byte-pattern hit at ADDR really an instruction,
# and what branches around it?"  The census script
# (wsa1_port_strap_census.py) scans raw bytes and therefore fires inside data
# too; its own --null shows the false-positive rate is only ~3x below signal.
# Nothing from that scan may be quoted until it has been seen here, decoded
# from an earlier instruction boundary.
#
#   IMAGE  a | b | c | d
#   ADDR   CPU address (e.g. 0xF95137), or a file offset if IMAGE is d
#   BYTES  window length, default 96, starting 32 before ADDR
#
# Bases: a=0xF80000 (ic12), b=0xF00000 (ic13), c=0xF80000 (ic28), d=0 (ic21).
#
#   sh wsa1_dis.sh a 0xF95137 120
set -e
ROMS=/home/fsanches/compartilhado/technics_roms/roms/wsa1
UNIDASM=/home/fsanches/compartilhado/mame/unidasm
case "$1" in
  a) F=$ROMS/wsa1_os_v2.ic12; BASE=$((0xF80000)) ;;
  b) F=$ROMS/wsa1_os_v2.ic13; BASE=$((0xF00000)) ;;
  c) F=$ROMS/wsa1_os_v2.ic28; BASE=$((0xF80000)) ;;
  d) F=$ROMS/wsa1_os_v2.ic21; BASE=0 ;;
  *) echo "usage: $0 a|b|c|d ADDR [BYTES] [BACKUP]" >&2; exit 1 ;;
esac
ADDR=$(($2))
LEN=${3:-96}
BACK=${4:-32}
START=$((ADDR - BASE - BACK))
[ "$START" -lt 0 ] && START=0
TMP=$(mktemp /home/fsanches/compartilhado/KN7000/tmp-dir/wsa1dis.XXXXXX)
dd if="$F" bs=1 skip=$START count=$LEN of="$TMP" status=none
# ⚠ unidasm parses -basepc as HEX.  Passing shell $(( )) decimal makes every
# printed address wrong (it re-reads "16263264" as 0x16263264).  Cost an hour
# once; hence printf.
$UNIDASM "$TMP" -arch tlcs900 -basepc $(printf '%x' $((BASE + START)))
rm -f "$TMP"
