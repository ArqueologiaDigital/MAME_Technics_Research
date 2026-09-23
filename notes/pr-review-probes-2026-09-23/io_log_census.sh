#!/bin/bash
# Q: which undecoded I/O addresses does the KN7000 driver actually log, and how
#    often? A driver that logs a quarter of a million lines in twenty seconds
#    will be noticed by whoever runs it with -log.
#
# A (measured 2026-09-23, 20 s of emulated time from cold boot, 85 MB error.log):
#
#      166,421   io_w  +060000     <- the hottest by far
#       91,891   io_w  +000026
#          496   io_w  +000024
#          244   io_w  +001010
#          209   io_w  +000064
#
#    The logged number is `offset << 1` -- a BYTE offset within whichever map
#    entry fired, not an address. Only the 0x98000000 sound window is large
#    enough (0x80000 bytes) to produce +060000, so that one is 0x98060000. The
#    others are ambiguous between the four windows that share the plain logger,
#    which is what io_log_absolute.py exists to fix.
#
#    Neither hot address appears as a 32-bit literal anywhere in the 4 MB
#    program image, so both are reached through a pointer register -- consistent
#    with a streaming loop, and why a static scan for the constant finds nothing.
#
# ⚠ Deriving the address from this log cost two wrong guesses before the
#   ambiguity was the obvious explanation. Read the format string first:
#   `logerror("%s: io_w  +%06X = ...", ..., offset << 1, ...)`.
#
# RUN
#   ./io_log_census.sh <path-to-kn-binary> <rompath>
set -euo pipefail
KN=${1:?usage: io_log_census.sh <kn binary> <rompath>}
ROMS=${2:?usage: io_log_census.sh <kn binary> <rompath>}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$(dirname "$KN")"
rm -f error.log
DISPLAY=${DISPLAY:-:0} timeout -k 5 300 "./$(basename "$KN")" kn7000 \
	-rompath "$ROMS" -str 20 -nothrottle -log -window -resolution 800x400 \
	>/dev/null 2>&1 || true
[ -s error.log ] || { echo "no error.log produced -- did -log take?"; exit 1; }
echo "error.log size: $(stat -c%s error.log) bytes"
echo "top undecoded write targets (offset within the firing map entry):"
grep -o "io_w  +[0-9A-F]*" error.log | sort | uniq -c | sort -rn | head -10
echo "top undecoded read targets:"
grep -o "io_r  +[0-9A-F]*" error.log | sort | uniq -c | sort -rn | head -10
