#!/usr/bin/env python3
# levels.py WAV FROM TO STEP [NOTES] -- does a note stop at its note-off? (README.md here, "How the file got its order")
#
# Prints the level (dBFS RMS of channels 0 and 1, MAME's instrument outputs) of each STEP-second window from FROM to
# TO (seconds in the file; a -wavwrite file starts at emulated time 0). With NOTES (MIDI note numbers, comma
# separated, e.g. 47,57,65), also each window's spectrum peak within +-1.5% of each note's fundamental, in dB
# (relative, Hann window): a note only one voice plays that is still there long after its note-off is a hung voice.
# Examples, the takes of README.md:
#   levels.py midi-off-v1/run.wav 41 69 1                    the level never falls back after 52 s
#   levels.py midi-off-v1/run.wav 46 68 2 47,57,65           B2, A3, F4 (strings only, 46-52 s) still at 66-68 s
#   levels.py midi-off-v4/run.wav 29.5 41 0.5                organ at 30-34 s: -9 dB at its release, then held
#   levels.py midi-on/run.wav 29.75 38.5 0.25                square lead: release, then the reverb tail to silence
import sys
import wave

import numpy as np

path, t0, t1, step = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
notes = [int(n) for n in sys.argv[5].split(",")] if len(sys.argv) > 5 else []
with wave.open(path, "rb") as w:
    R, ch = w.getframerate(), w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, ch).astype(np.float64) / 32768.0
x = a[:, :2]
names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
t = t0
while t < t1 - 1e-9:
    q = x[int(t * R): int((t + step) * R)]
    lv = 10 * np.log10(max((q ** 2).mean(), 1e-24))
    line = "%7.2f-%7.2f %7.1f dBFS" % (t, t + step, lv)
    if notes:
        m = q[:, 0] + q[:, 1]
        S = np.abs(np.fft.rfft(m * np.hanning(len(m))))
        f = np.fft.rfftfreq(len(m), 1 / R)
        for n in notes:
            hz = 440 * 2 ** ((n - 69) / 12)
            sel = (f > hz * 0.985) & (f < hz * 1.015)
            line += "  %s%d %5.1f" % (names[n % 12], n // 12 - 1, 20 * np.log10(S[sel].max() + 1e-12))
    print(line)
    t += step
