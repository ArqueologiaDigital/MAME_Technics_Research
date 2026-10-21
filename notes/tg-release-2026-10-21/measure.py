#!/usr/bin/env python3
# measure.py OUT -- does each note of the release probe end? (README.md here)
#
# Reads OUT/run.wav (MAME -wavwrite: emulated time 0 = sample 0; channels 0 and 1 are the instrument's outputs) and
# OUT/voices.txt (probe.lua's log of the tone generator's own voice state). For each section of gen_probe_mid.py it
# follows the note's fundamental (a Hann-windowed spectrum of 0.1 s windows, the peak within +-1.5% of the note's
# frequency, as notes/listen-2026-10-21/levels.py does): the held level (mean of the dB values from 0.5 s after the
# note-on to 0.1 s before the end), then the first time after the end at which the fundamental is 40 dB below that,
# and where it stands 1 s and 3 s after the end (the next section starts 3.5 s after it). "End" is the note-off, or the CC 123 / CC 120 for the last two.
# Prints an aligned Markdown table, then the last voices.txt sample that has a voice above zero (the probe logs
# every 0.05 s up to 79 s; a voice still there at 78.95 s never ended).
import sys
import wave

import numpy as np

OUT = sys.argv[1]
SECTIONS = [  # name, note-on (emulated s), end, MIDI note
    ("keybed C4 (panel sound)", 32.0, 33.5, 60),
    ("MIDI ch 1 D4 (panel sound)", 37.0, 38.5, 62),
    ("ch 4 GM 0 piano E4", 42.0, 43.5, 64),
    ("ch 5 GM 48 strings F4", 47.0, 48.5, 65),
    ("ch 6 GM 89 pad G4", 52.0, 53.5, 67),
    ("ch 7 GM 19 organ A4", 57.0, 58.5, 69),
    ("ch 8 GM 80 square lead B4", 62.0, 63.5, 71),
    ("ch 5 strings C5, CC 123", 67.0, 68.5, 72),
    ("ch 6 pad D5, CC 120", 72.0, 73.5, 74),
]
W = 0.1
with wave.open(OUT + "/run.wav", "rb") as w:
    R, ch = w.getframerate(), w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, ch).astype(np.float64) / 32768.0
m = a[:, 0] + a[:, 1]
hann = np.hanning(int(W * R))
f = np.fft.rfftfreq(len(hann), 1 / R)


def level(t, n):
    q = m[int(t * R): int(t * R) + len(hann)]
    if len(q) < len(hann):
        return -240.0
    S = np.abs(np.fft.rfft(q * hann))
    hz = 440 * 2 ** ((n - 69) / 12)
    sel = (f > hz * 0.985) & (f < hz * 1.015)
    return 20 * np.log10(S[sel].max() + 1e-12)


rows = [("section", "held (dB)", "-40 dB after end", "end +1 s", "end +3 s")]
for name, on, end, n in SECTIONS:
    held = np.mean([level(t, n) for t in np.arange(on + 0.5, end - 0.1, W)])
    t40 = None
    for t in np.arange(end, end + 4.5, 0.01):
        if level(t, n) < held - 40:
            t40 = t - end
            break
    r1, r3 = level(end + 1.0, n) - held, level(end + 3.0, n) - held
    rows.append((name, "%.1f" % held, "never (4.5 s)" if t40 is None else "%.2f s" % t40, "%+.1f dB" % r1, "%+.1f dB" % r3))
wid = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
for k, r in enumerate(rows):
    print("| " + " | ".join(c.ljust(wid[i]) for i, c in enumerate(r)) + " |")
    if k == 0:
        print("|" + "|".join("-" * (x + 2) for x in wid) + "|")

last = {}
for line in open(OUT + "/voices.txt"):
    t, v, g, s, md, e = line.split()
    last.setdefault(t, []).append((int(v), float(e)))
if last:
    t = max(last, key=float)
    print("\nlast voices.txt sample with a voice above zero, t=%s: %s" % (t, ", ".join("v%d %.3f" % ve for ve in last[t])))
else:
    print("\nno voice above zero in voices.txt")
