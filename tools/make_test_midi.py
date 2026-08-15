#!/usr/bin/env python3
"""Write a minimal MIDI file that holds one note, for pitch-accuracy measurement.

Feeds the KN5000's `kbdmidi` port, which plays the machine's OWN keybed (MIDI 36..96 =
C2..C7, see kn5000.cpp "A host MIDI controller wired to the kbdmidi port"). That gives an
exact, known input pitch — which is what task-queue item P10 needs: the emulator's onset
centroid measures ~13 semitones above a reference render, and nobody has yet played a known
note and measured what actually comes out.

    python3 tools/make_test_midi.py --note 60 --seconds 4 -o c4.mid
    ./run.sh kn5000 ... -kbdmidi midiin -min2 c4.mid -wavwrite out.wav

Defaults to MIDI 60 (C4, 261.626 Hz). Channel 1, velocity 100, one note on, one note off.
No tempo map beyond the default 120 bpm / 480 ticks per beat.
"""
import argparse
import struct


def vlq(n):
    """MIDI variable-length quantity."""
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, 0x80 | (n & 0x7F))
        n >>= 7
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--note", type=int, default=60, help="MIDI note number (60 = C4)")
    ap.add_argument("--velocity", type=int, default=100)
    ap.add_argument("--seconds", type=float, default=4.0, help="how long to hold it")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="silence before the note. MAME's midiin streams the file from machine "
                         "start, so a note at t=0 lands during boot and is lost -- give it "
                         "enough delay to clear the boot (the KN5000 settles around t=25 s).")
    ap.add_argument("--channel", type=int, default=0)
    ap.add_argument("-o", "--out", default="test_note.mid")
    args = ap.parse_args()

    TPQ = 480                      # ticks per quarter note
    us_per_beat = 500000           # 120 bpm
    ticks = int(args.seconds * TPQ * 1000000.0 / us_per_beat)

    ev = bytearray()
    # tempo meta, so the file is self-describing rather than relying on a player default
    ev += vlq(0) + b"\xFF\x51\x03" + struct.pack(">I", us_per_beat)[1:]
    pre = int(args.delay * TPQ * 1000000.0 / us_per_beat)
    ev += vlq(pre) + bytes([0x90 | (args.channel & 0x0F), args.note & 0x7F, args.velocity & 0x7F])
    ev += vlq(ticks) + bytes([0x80 | (args.channel & 0x0F), args.note & 0x7F, 0x40])
    ev += vlq(0) + b"\xFF\x2F\x00"          # end of track

    trk = b"MTrk" + struct.pack(">I", len(ev)) + bytes(ev)
    hdr = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TPQ)
    with open(args.out, "wb") as f:
        f.write(hdr + trk)

    freq = 440.0 * (2.0 ** ((args.note - 69) / 12.0))
    print(f"wrote {args.out}: note {args.note} = {freq:.3f} Hz at t={args.delay}s, "
          f"held {args.seconds}s, vel {args.velocity}, ch {args.channel + 1}")
    print(f"  one octave high would read {freq * 2:.3f} Hz; one octave low {freq / 2:.3f} Hz")


if __name__ == "__main__":
    main()
