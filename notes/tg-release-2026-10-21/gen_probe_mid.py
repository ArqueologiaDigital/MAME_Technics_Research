#!/usr/bin/env python3
# gen_probe_mid.py OUT.mid -- the release probe's MIDI file (README.md here). Ours, public domain.
#
# QUESTION IT SERVES: does each voice family end at its note-off, over MIDI on channel 1 (a panel part) and on
# channels 4-16 (the GM receive parts), and do All Notes Off (CC 123) and All Sound Off (CC 120) end a held note?
# One note per section, each on its own pitch, so that levels.py can follow each note's fundamental on its own.
# MAME starts a .mid at emulated 10 s (file time t plays at emulated t + 10). probe.lua presses the keybed note
# (C4, key index 0x18) itself at 32.0-33.5 s; this file has nothing there.
#
#   emulated s    what                                         channel, GM program        note
#   32.0 - 33.5   keybed C4 (probe.lua)                        panel RIGHT 1 sound        C4 60
#   37.0 - 38.5   MIDI, a panel part                           1 (panel sound)            D4 62
#   42.0 - 43.5   piano                                        4, GM 0                    E4 64
#   47.0 - 48.5   strings                                      5, GM 48                   F4 65
#   52.0 - 53.5   warm pad                                     6, GM 89                   G4 67
#   57.0 - 58.5   church organ                                 7, GM 19                   A4 69
#   62.0 - 63.5   square lead                                  8, GM 80                   B4 71
#   67.0 -        strings, no note-off; CC 123 at 68.5         5, GM 48                   C5 72
#   72.0 -        warm pad, no note-off; CC 120 at 73.5        6, GM 89                   D5 74
#   78.0          end of the file
import hashlib
import struct
import sys

OFFSET = 10.0
TPS = 960
ev = []


def at(t, *b):
    ev.append((t, len(ev), bytes(b)))


def note(t, ch, n, dur, vel=100):
    at(t, 0x90 | (ch - 1), n, vel)
    if dur is not None:
        at(t + dur, 0x80 | (ch - 1), n, 64)


def setup(t, ch, bank, prog, vol):
    at(t, 0xB0 | (ch - 1), 0, bank)
    at(t, 0xB0 | (ch - 1), 32, 0)
    at(t, 0xC0 | (ch - 1), prog)
    at(t, 0xB0 | (ch - 1), 7, vol)


setup(29.0, 4, 121, 0, 110)
setup(29.0, 5, 121, 48, 100)
setup(29.0, 6, 121, 89, 110)
setup(29.0, 7, 121, 19, 90)
setup(29.0, 8, 121, 80, 80)
note(37.0, 1, 62, 1.5)
note(42.0, 4, 64, 1.5)
note(47.0, 5, 65, 1.5)
note(52.0, 6, 67, 1.5)
note(57.0, 7, 69, 1.5)
note(62.0, 8, 71, 1.5)
note(67.0, 5, 72, None)
at(68.5, 0xB4, 123, 0)
note(72.0, 6, 74, None)
at(73.5, 0xB5, 120, 0)
END = 78.0

ev.sort(key=lambda e: (e[0], e[1]))
trk = bytearray(b"\x00\xFF\x51\x03" + struct.pack(">I", 500000)[1:])


def vlq(n):
    b = [n & 0x7F]
    n >>= 7
    while n:
        b.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(b))


last = 0
for t, _o, b in ev:
    tick = round((t - OFFSET) * TPS)
    trk += vlq(tick - last) + b
    last = tick
trk += vlq(round((END - OFFSET) * TPS) - last) + b"\xFF\x2F\x00"
data = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)
with open(sys.argv[1], "wb") as f:
    f.write(data)
print("%s md5 %s, %d events" % (sys.argv[1], hashlib.md5(data).hexdigest(), len(ev)))
