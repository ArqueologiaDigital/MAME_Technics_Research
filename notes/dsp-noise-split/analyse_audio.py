#!/usr/bin/env python3
"""Characterise a KN7000 capture: is the output noisy, and where does it come from?

The captures have THREE channels, not two: the driver instantiates :speaker (2ch,
the instrument) and the floppy connector's .enable_sound(true) adds
:fdc:0:35hd:floppysound:output (1ch). They appear in creation order, so ch0/ch1 are
the instrument and ch2 is the drive motor. Reporting a "noise level" off the mixed
file without splitting them attributes the motor hum to the tone generator.

Prints per-channel level, the quietest one-second window (the noise floor, which is
what "noisy" usually means), and the high-frequency fraction of the instrument pair
via a zero-crossing proxy -- broadband hash raises it, musical content does not.

Usage: analyse_audio.py a.wav [b.wav ...]
"""
import math
import struct
import sys
import wave


def load(path):
    w = wave.open(path)
    n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
    s = struct.unpack("<%dh" % (n * ch), w.readframes(n))
    return [list(s[c::ch]) for c in range(ch)], sr


def rms(xs):
    return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else 0.0


def dbfs(v):
    return -99.0 if v <= 0 else 20 * math.log10(v / 32768.0)


def zcr(xs):
    return sum(1 for i in range(1, len(xs)) if (xs[i - 1] < 0) != (xs[i] < 0)) / max(1, len(xs) - 1)


def main(paths):
    for p in paths:
        chans, sr = load(p)
        print("== %s  (%d ch, %d Hz, %.1f s)" % (p.split("/")[-1], len(chans), sr, len(chans[0]) / sr))
        names = {0: "instrument L", 1: "instrument R", 2: "floppy motor"}
        for i, c in enumerate(chans):
            print("   ch%d %-13s peak %6d (%6.1f dBFS)   rms %8.2f (%6.1f dBFS)"
                  % (i, names.get(i, "?"), max(abs(x) for x in c), dbfs(max(abs(x) for x in c)),
                     rms(c), dbfs(rms(c))))
        inst = [max(abs(chans[0][i]), abs(chans[1][i])) for i in range(len(chans[0]))]
        secs = [rms(inst[s * sr:(s + 1) * sr]) for s in range(len(inst) // sr)]
        floor = min(secs) if secs else 0
        print("   instrument pair: quietest second rms %.2f (%.1f dBFS), loudest %.2f (%.1f dBFS)"
              % (floor, dbfs(floor), max(secs), dbfs(max(secs))))
        print("   instrument zero-crossing rate %.4f  (broadband hash pushes this up)"
              % zcr(chans[0]))


if __name__ == "__main__":
    main(sys.argv[1:])
