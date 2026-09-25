#!/usr/bin/env python3
"""Write a small SMF used as the stimulus for the noise A/B.

What question does it answer? "Is the noise the effects DSP, the tone generator,
or something else?" -- which needs notes actually sounding, because a sound test
with nothing playing is not a test.

The key bed cannot serve: the firmware never polls the key FIFO, so driving the
KEYS ports produces nothing (measured: main speaker pair bit-identical with and
without a 61-key stimulus). MIDI in on the keybed bridge does reach the tone
generator.

Usage: make_test_midi.py out.mid
"""
import struct
import sys


def vlq(n):
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def main(path):
    TPQ = 480
    ev = bytearray()

    def add(delta, data):
        ev.extend(vlq(delta))
        ev.extend(data)

    add(0, b"\xB0\x07\x7F")                 # channel volume full
    # a held triad, four beats
    for n in (60, 64, 67):
        add(0, bytes([0x90, n, 100]))
    add(TPQ * 4, bytes([0x80, 60, 0]))
    for n in (64, 67):
        add(0, bytes([0x80, n, 0]))
    # then a scale, one note per beat
    for n in (60, 62, 64, 65, 67, 69, 71, 72):
        add(TPQ // 2, bytes([0x90, n, 100]))
        add(TPQ, bytes([0x80, n, 0]))
    add(TPQ * 2, b"\xFF\x2F\x00")           # end of track

    trk = b"MTrk" + struct.pack(">I", len(ev)) + bytes(ev)
    hdr = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TPQ)
    open(path, "wb").write(hdr + trk)
    print("wrote %s (%d bytes)" % (path, len(hdr) + len(trk)))


if __name__ == "__main__":
    main(sys.argv[1])
