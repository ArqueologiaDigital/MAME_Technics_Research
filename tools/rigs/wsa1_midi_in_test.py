#!/usr/bin/env python3
"""Generate a MIDI file for the WSA1R MIDI-IN end-to-end test.

QUESTION THIS ANSWERS: does an external MIDI note, fed to the wired MIDI IN,
travel CPU 1 SC0 -> the inter-processor link -> CPU 2's note engine -> the tone
generator and become an audible (placeholder-sine) voice?

MAME's `midiin` is a MIDI-IN IMAGE device: it plays a .mid FILE by emulated
time, so no host MIDI port is needed (this environment has no rawmidi input for
PortMidi anyway).  The file below holds note-on/off pairs spanning the boot
window, so the capture shows exactly WHEN the path comes alive.

RUN, from the build tree (unthrottled; visible video per house rule):
    python3 tools/rigs/wsa1_midi_in_test.py           # writes note_long.mid
    ./kn7000 wsa1r -rompath <roms> -window -skip_gameinfo -nomax \\
        -midiin note_long.mid -wavwrite out.wav -seconds_to_run 65

MEASURED 2026-09-06 (48 kHz capture, 1 s RMS windows, left channel):
    0..24 s  RMS 0            (boot; placeholder correctly silent)
    25 s     RMS ~2600, then rising to ~21000 by ~55 s
The rise is real and is a KNOWN limitation, not a bug in the path: note-off does
not release a voice yet (the tone generator's busy bit never falls, so the
firmware never retires the record), so voices accumulate.  What it proves is the
whole chain: MIDI IN -> SC0 -> link -> CPU 2 -> tone generator -> sine.
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
    # 480 tpqn, 120 bpm -> 480 ticks = 0.5 s.  Rest to t = 15 s, then a note every 1 s.
    ev += vlq(30 * 480) + bytes([0x90, 69, 110])
    ev += vlq(480) + bytes([0x80, 69, 0])
    notes = [72, 60, 64, 67, 71, 69] * 8
    for nn in notes:
        ev += vlq(480) + bytes([0x90, nn, 110])
        ev += vlq(480) + bytes([0x80, nn, 0])
    ev += vlq(0) + bytes([0xff, 0x2f, 0x00])
    trk = b"MTrk" + struct.pack(">I", len(ev)) + bytes(ev)
    hdr = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480)
    with open("note_long.mid", "wb") as f:
        f.write(hdr + trk)
    print("wrote note_long.mid (first note t=15 s, then one per second)")


if __name__ == "__main__":
    sys.exit(main())
