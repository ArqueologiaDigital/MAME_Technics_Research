#!/usr/bin/env python3
"""Generate a single-note MIDI file for observing WSA1R note-off behaviour.

QUESTION THIS ANSWERS: on a real note-on then note-off fed to MIDI IN, what
exact tone-generator register writes does the firmware issue -- specifically,
what RATE byte does note-ON write to block 0x0800 (attack ramp vs the 0xFF80
"hold" marker), and what does the note-OFF tail (MidiNote_OffTail, prom_c
0xFB374A) write?  The answer decides whether an autonomous busy-bit countdown
keyed on the 0x0800 low byte would misfire during a held note.

Run against the LOG_TG build (VERBOSE |= LOG_TG in wsa1.cpp) and grep the log
for `tg: ch`.  One note: on at t=25 s (after boot), off at t=28 s, end t=31 s.

    python3 tools/rigs/wsa1_one_note.py            # writes one_note.mid here
    ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \\
        -midiin one_note.mid -seconds_to_run 31 -log
    grep '^tg: ch' error.log        # decoded per-write trace
"""
import struct, sys


def vlq(n):
    out = bytearray([n & 0x7f]); n >>= 7
    while n:
        out.insert(0, 0x80 | (n & 0x7f)); n >>= 7
    return bytes(out)


def main():
    ev = bytearray()
    ev += vlq(0) + bytes([0xff, 0x51, 0x03]) + struct.pack(">I", 500000)[1:]  # 120 bpm
    # 480 tpqn @ 120 bpm -> 480 ticks = 0.5 s.  Rest to 25 s, hold 3 s, release.
    ev += vlq(50 * 480) + bytes([0x90, 69, 110])   # note-on  A4 vel 110 @ t=25 s
    ev += vlq(6 * 480) + bytes([0x80, 69, 0])       # note-off A4       @ t=28 s
    ev += vlq(6 * 480) + bytes([0xff, 0x2f, 0x00])  # end               @ t=31 s
    trk = b"MTrk" + struct.pack(">I", len(ev)) + bytes(ev)
    hdr = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480)
    with open("one_note.mid", "wb") as f:
        f.write(hdr + trk)
    print("wrote one_note.mid (A4 on t=25 s, off t=28 s, end t=31 s)")


if __name__ == "__main__":
    sys.exit(main())
