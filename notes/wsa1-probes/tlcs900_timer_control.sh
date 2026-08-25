#!/bin/bash
# THE NULL BUILD for the TMP95C061 timer fixes.
#
# QUESTION IT ANSWERS: "how much of what you measured was the fix, and how much
# was the machine?"  It puts the overlay's tmp95c061.cpp back to UPSTREAM timer
# behaviour -- the 16x-slow prescaler taps (>>7 >>9 >>11 >>15) and no 16-bit
# timer counting at all -- so the same probe can be run against the same binary
# lineage with only the timer model changed.  Nothing else moves: the P6 fix,
# the serial-channel-1 additions, INT6/INT7 and control register 0x3C all stay.
#
# USAGE
#     notes/wsa1-probes/tlcs900_timer_control.sh null      # revert the timers
#     ./build.sh                                           # ~1 file + link
#     ...run the probe, record the numbers...
#     notes/wsa1-probes/tlcs900_timer_control.sh fixed     # put them back
#     ./build.sh
#     notes/wsa1-probes/tlcs900_timer_control.sh check     # which state am I in?
#
# ⚠ It edits the overlay source in place.  Always finish with `fixed`, and
# `git diff --stat src/devices/cpu/tlcs900/tmp95c061.cpp` should come back empty.
#
# WHAT THE PROBES SHOWED (wsa1r, 45 s, 2026-08-25 -- see the tables in
# notes/WSA1-EMULATION-DISASM-GAPS.md for the full run):
#     RAM 0x0080 tick counter (INTT1)   null 30.4 Hz   fixed 488.0 Hz
#     INTTR4 dispatches (vector 0x50)   null   none    fixed 192.0 Hz steady

set -euo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
F="$HERE/src/devices/cpu/tlcs900/tmp95c061.cpp"

# The four tap constants, and the two run guards for the 16-bit units.
FIXED_TAPS='static constexpr int PRESCALE_T1   = 3;    // fc\/8
static constexpr int PRESCALE_T4   = 5;    // fc\/32
static constexpr int PRESCALE_T16  = 7;    // fc\/128
static constexpr int PRESCALE_T256 = 11;   // fc\/2048'

case "${1:-check}" in
null)
	sed -i \
		-e 's|^static constexpr int PRESCALE_T1   = 3;.*$|static constexpr int PRESCALE_T1   = 7;    // NULL BUILD (upstream)|' \
		-e 's|^static constexpr int PRESCALE_T4   = 5;.*$|static constexpr int PRESCALE_T4   = 9;    // NULL BUILD (upstream)|' \
		-e 's|^static constexpr int PRESCALE_T16  = 7;.*$|static constexpr int PRESCALE_T16  = 11;   // NULL BUILD (upstream)|' \
		-e 's|^static constexpr int PRESCALE_T256 = 11;.*$|static constexpr int PRESCALE_T256 = 15;   // NULL BUILD (upstream)|' \
		-e 's|^		if ( m_trun \& 0x10 )$|		if ( false \&\& ( m_trun \& 0x10 ) )   // NULL BUILD (upstream: never counted)|' \
		-e 's|^		if ( m_trun \& 0x20 )$|		if ( false \&\& ( m_trun \& 0x20 ) )   // NULL BUILD (upstream: never counted)|' \
		"$F"
	echo "NULL build armed.  Now run ./build.sh"
	;;
fixed)
	sed -i \
		-e 's|^static constexpr int PRESCALE_T1   = 7;.*$|static constexpr int PRESCALE_T1   = 3;    // fc/8|' \
		-e 's|^static constexpr int PRESCALE_T4   = 9;.*$|static constexpr int PRESCALE_T4   = 5;    // fc/32|' \
		-e 's|^static constexpr int PRESCALE_T16  = 11;.*$|static constexpr int PRESCALE_T16  = 7;    // fc/128|' \
		-e 's|^static constexpr int PRESCALE_T256 = 15;.*$|static constexpr int PRESCALE_T256 = 11;   // fc/2048|' \
		-e 's|^		if ( false \&\& ( m_trun \& 0x10 ) ).*$|		if ( m_trun \& 0x10 )|' \
		-e 's|^		if ( false \&\& ( m_trun \& 0x20 ) ).*$|		if ( m_trun \& 0x20 )|' \
		"$F"
	echo "FIXED build restored.  Now run ./build.sh"
	;;
check)
	grep -n 'NULL BUILD' "$F" && echo "=> currently the NULL build" \
		|| echo "=> currently the FIXED build"
	;;
*)
	echo "usage: $0 {null|fixed|check}" >&2; exit 2 ;;
esac
