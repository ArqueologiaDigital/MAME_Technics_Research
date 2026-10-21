#!/usr/bin/env python3
# gen_listen_mid.py OUT.mid [OUT_events.txt] [--layout=N] -- the listening test's MIDI file (README.md here), our own, public domain.
#
# For MAME's -midiin1 on the kn7000: MAME starts a .mid file at emulated time 10 s (imagedev/midiin.cpp,
# m_sequence_start = max(now, 10 s)), so file time t plays at emulated time t + 10. The firmware reaches its play
# screen at about 26 s; the music starts at emulated T0 = 30 s (file time 20 s), after the parts are set up at 29 s.
# Channels 4-16 are the KN7000's receive parts PART 4-16 (owner's manual p.190; technics-anotherworld src/audio.s);
# a program change after bank select 121/0 picks a GM2 voice, channel 10 with bank 120/0 is the GM2 drum set
# (technics-anotherworld probes/cnv/awcnv_midiprog.lua showed both work on 893).
#
#   emulated s     what                                                          channel, GM program
#   30.0 - 33.0    C major chord held 3 s, then released: the release and the    8, square lead (80)
#                  reverb tail, 5 s with nothing else sounding
#   38.0 - 51.3    J. S. Bach, Prelude in C major BWV 846, bars 1-4 (q = 72)     4, piano (0)
#   52.0 - 60.0    the Prelude's four harmonies as held chords, 2 s each         5, strings (48)
#   52.0 - 60.0    a drum pattern, 4 bars at 120 bpm, a crash + kick at 60.0     10, GM2 drum set
#   61.0 - 65.0    C major chord held 4 s, then released                         7, warm pad (89)
#   68.0           end of the file
# Why this order and the square lead: in MAME (overlay 4f7b9c7, binary 7336efbe) MIDI-received notes of most voices
# do not end at their note-offs. In the first four takes of this file (README.md here) the piano held at about
# -35 dBFS after its last note, the strings and the pad rang on undiminished 10 s after theirs, a church organ (GM
# 19) fell only 9 dB and then held, and All Notes Off (CC 123) with All Sound Off (CC 120) stopped none of them.
# GM 80 falls about 40 dB within 1 s of a MIDI IN note-off (technics-anotherworld probes/cnv/README.md,
# awcnv_noteoff.lua), so the chord whose release and reverb tail are to be heard is a square-lead chord, and it is
# played first, into silence; the voices that hang come after it.
import hashlib
import struct
import sys

T0 = 30.0            # emulated time of the first note
OFFSET = 10.0        # MAME's -midiin start
TPS = 960            # ticks per second: division 480 at 500,000 us a quarter

ev = []              # (emulated time, order, bytes)


def at(t, *b):
    ev.append((t, len(ev), bytes(b)))


def note(t, ch, n, dur, vel=96):
    at(t, 0x90 | (ch - 1), n, vel)
    at(t + dur, 0x80 | (ch - 1), n, 64)


def setup(t, ch, bank, prog, vol):
    at(t, 0xB0 | (ch - 1), 0, bank)
    at(t, 0xB0 | (ch - 1), 32, 0)
    at(t, 0xC0 | (ch - 1), prog)
    at(t, 0xB0 | (ch - 1), 7, vol)


# --layout=N regenerates the file of an earlier take (README.md here, "How the file got its order"); 5, the default,
# is the file used for the listening set. Each layout's md5 is checked against the one the take recorded.
LAYOUT = 5
for a in sys.argv[1:]:
    if a.startswith("--layout="):
        LAYOUT = int(a.split("=")[1])
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
MD5 = {1: "5f76d8581cd6116bebcf174b61914ad1", 2: "a5957646496a29029a64ac12073b278d", 3: "226a9dceb31c294ce6acbcec368d9e3c",
       4: "2c24016516ee00fa8bf1acd13d48c787", 5: "8ed7203d6de097e5d457f25074f02508"}

PIANO, STRINGS, ORGAN, LEAD, PAD, DRUMS = 4, 5, 6, 8, 7, 10
setup(T0 - 1.0, PIANO, 121, 0, 110)
setup(T0 - 1.0, STRINGS, 121, 48, 100)
if LAYOUT == 5:
    setup(T0 - 1.0, LEAD, 121, 80, 80)
else:
    setup(T0 - 1.0, ORGAN, 121, 19, 90)
setup(T0 - 1.0, PAD, 121, 89, 110)
setup(T0 - 1.0, DRUMS, 120, 0, 100)


def piano(t):
    # BWV 846 bars 1-4, each half bar n1 n2 n3 n4 n5 n3 n4 n5 in sixteenths, n1 held 8, n2 held 7
    bars = [(60, 64, 67, 72, 76), (60, 62, 69, 74, 77), (59, 62, 67, 74, 77), (60, 64, 67, 72, 76)]
    s16 = 60.0 / 72 / 4
    for bar in bars:
        for _half in range(2):
            n1, n2, n3, n4, n5 = bar
            note(t, PIANO, n1, 8 * s16 * 0.98, 80)
            note(t + s16, PIANO, n2, 7 * s16 * 0.98, 76)
            for k, n in enumerate((n3, n4, n5, n3, n4, n5)):
                note(t + (2 + k) * s16, PIANO, n, s16 * 0.95, 88 if k % 3 == 0 else 80)
            t += 8 * s16


def strings_drums(b0):
    # the Prelude's harmonies as held chords on strings, with 4 bars of drums at 120 bpm
    chords = [(48, 55, 60, 64), (48, 57, 62, 65), (47, 55, 62, 65), (48, 55, 60, 64)]
    for i, ch in enumerate(chords):
        for n in ch:
            note(b0 + 2.0 * i, STRINGS, n, 1.9, 90)
        for j in range(8):
            note(b0 + 2.0 * i + 0.25 * j, DRUMS, 42, 0.1, 80)        # closed hi-hat, eighths
        note(b0 + 2.0 * i, DRUMS, 36, 0.1, 112)                      # kick on 1 and 3
        note(b0 + 2.0 * i + 1.0, DRUMS, 36, 0.1, 112)
        note(b0 + 2.0 * i + 0.5, DRUMS, 38, 0.1, 104)                # snare on 2 and 4
        note(b0 + 2.0 * i + 1.5, DRUMS, 38, 0.1, 104)
    note(b0 + 8.0, DRUMS, 49, 0.1, 110)                              # crash
    note(b0 + 8.0, DRUMS, 36, 0.1, 112)


def chord(t, ch, notes, dur, vel=100):
    for n in notes:
        note(t, ch, n, dur, vel)


def cleanup(t, ch):                                                  # All Notes Off, All Sound Off
    at(t, 0xB0 | (ch - 1), 123, 0)
    at(t, 0xB0 | (ch - 1), 120, 0)


CMAJ5, CMAJ_PAD = (48, 55, 60, 64, 67), (48, 55, 64, 67, 72)
if LAYOUT == 5:      # the listening set: square-lead chord, piano, strings + drums, pad
    piano(T0 + 8.0)
    chord(T0, LEAD, CMAJ5, 3.0)
    strings_drums(T0 + 22.0)
    chord(T0 + 31.0, PAD, CMAJ_PAD, 4.0)
    END = T0 + 38.0
elif LAYOUT == 1:    # piano, strings + drums, organ, pad
    piano(T0)
    strings_drums(T0 + 14.0)
    chord(T0 + 23.0, ORGAN, (48, 60, 64, 67), 3.0, 96)
    chord(T0 + 28.0, PAD, CMAJ_PAD, 4.0)
    END = T0 + 38.0
elif LAYOUT == 2:    # piano, strings + drums, pad, organ, with All Notes / Sound Off after piano, strings, pad
    piano(T0)
    strings_drums(T0 + 14.0)
    chord(T0 + 23.0, PAD, CMAJ_PAD, 3.0)
    chord(T0 + 28.0, ORGAN, CMAJ5, 4.0)
    END = T0 + 38.0
    cleanup(T0 + 20.0, PIANO)
    cleanup(T0 + 22.6, STRINGS)
    cleanup(T0 + 27.5, PAD)
elif LAYOUT in (3, 4):   # 3: piano, organ, strings + drums, pad; 4: organ first, then the same
    piano(T0 if LAYOUT == 3 else T0 + 10.0)
    chord(T0 + 14.5 if LAYOUT == 3 else T0, ORGAN, CMAJ5, 4.0)
    strings_drums(T0 + 24.0)
    chord(T0 + 33.0, PAD, CMAJ_PAD, 4.0)
    END = T0 + 40.0

ev.sort(key=lambda e: (e[0], e[1]))
trk = bytearray(b"\x00\xFF\x51\x03" + struct.pack(">I", 500000)[1:])
trk += b"\x00\xFF\x03" + bytes([len(b"KN7000 listening test")]) + b"KN7000 listening test"


def vlq(n):
    b = [n & 0x7F]
    n >>= 7
    while n:
        b.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(b))


last = 0
for tm, _o, b in ev:
    tk = round((tm - OFFSET) * TPS)
    trk += vlq(tk - last) + b
    last = tk
trk += vlq(round((END - OFFSET) * TPS) - last) + b"\xFF\x2F\x00"
smf = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)
open(ARGS[0], "wb").write(smf)
if len(ARGS) > 1:
    with open(ARGS[1], "w") as f:
        for tm, _o, b in ev:
            f.write("%.3f %s\n" % (tm, b.hex(" ")))
md5 = hashlib.md5(smf).hexdigest()
print("layout %d: %d events, first note at emulated %.1f s, end at %.1f s, md5 %s (%s)" % (
    LAYOUT, len(ev), T0, END, md5, "as recorded" if md5 == MD5[LAYOUT] else "DIFFERS from the take's " + MD5[LAYOUT]))
