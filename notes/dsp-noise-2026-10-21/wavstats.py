#!/usr/bin/env python3
# wavstats.py WAV [PASSAGE_TXT] [--offset S] -- per-part statistics of a passage.lua recording (README.md here).
#
# QUESTION IT ANSWERS: does the recorded stream itself carry noise, and where? For each part of the passage (the
# boot's silence, A1/A2 with REVERB as at boot, B1/B2 with it toggled, the tails) it prints, for the instrument's
# two channels (a -wavwrite file has a third, the floppy drive, which is left out):
#   rms      level, dBFS
#   peak     dBFS, and how many samples sit at full scale (clipped)
#   hf5/hf10 the share of energy above 5 kHz / 10 kHz, dB relative to the total (a held C4 piano-like note has
#            little there; broadband noise or clicks raise it)
#   floor    the median spectral level between the harmonics of the held note, dB below the strongest peak (a
#            clean note gives a deep floor; hiss or crackle fills it)
#   clicks   samples whose second difference exceeds 8x the part's RMS second difference (discontinuities)
#   flat     the longest run of identical samples, and how many runs of >= 4 identical samples there are (a
#            DSP output held on underflow shows as flat runs)
#   L-R      RMS of L-R relative to L+R, dB (mono gives -inf)
# The part boundaries come from PASSAGE_TXT's EV lines (default: next to the WAV); --offset shifts them (a live
# capture starts later than the emulation). Needs numpy only.
import sys, wave, re, os
import numpy as np

args = [a for a in sys.argv[1:]]
off = 0.0
if '--offset' in args:
    i = args.index('--offset'); off = float(args[i + 1]); del args[i:i + 2]
wavp = args[0]
evp = args[1] if len(args) > 1 else os.path.join(os.path.dirname(wavp), 'passage.txt')
w = wave.open(wavp)
sr, nch = w.getframerate(), w.getnchannels()
x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, nch)[:, :2].astype(np.float64)
ev = {}
for line in open(evp):
    m = re.match(r'EV t=([\d.]+) (.*?) reverb_led', line)
    if m:
        k = m.group(2).split(' (')[0]
        ev[k + ' 2' if k in ev else k] = float(m.group(1)) + off
T0 = ev['A1 on']
parts = [
    ('silence (boot, before A1)', T0 - 6, T0 - 1),
    ('A1 C4, REVERB boot state', ev['A1 on'] + 0.5, ev['A1 off']),
    ('A2 chord, REVERB boot state', ev['A2 on'] + 0.5, ev['A2 off']),
    ('A tail', ev['A2 off'] + 0.2, ev['REVERB press'] - 0.2),
    ('B1 C4, REVERB toggled', ev['B1 on'] + 0.5, ev['B1 off']),
    ('B2 chord, REVERB toggled', ev['B2 on'] + 0.5, ev['B2 off']),
    ('B tail', ev['B2 off'] + 0.2, ev['REVERB press 2'] - 0.2),
]
def db(v): return 10 * np.log10(max(v, 1e-30))
print(f'{os.path.basename(wavp)}: {sr} Hz, {nch} ch, {len(x) / sr:.2f} s; parts from {os.path.basename(evp)} (offset {off:+.3f} s)')
print(f'{"part":30} {"ch":2} {"rms":>7} {"peak":>7} {"clip":>5} {"hf5":>6} {"hf10":>6} {"floor":>6} {"clicks":>6} {"flatmax":>7} {"flat4":>6} {"L-R":>6}')
for name, a, b in parts:
    s = x[int(a * sr):int(b * sr)] / 32768.0
    if len(s) < sr // 4: continue
    side = db(((s[:, 0] - s[:, 1]) ** 2).mean()) - db(((s[:, 0] + s[:, 1]) ** 2).mean() + 1e-30)
    for c in range(2):
        v = s[:, c]
        ms = (v ** 2).mean()
        n = 1 << int(np.log2(len(v)))
        spec = np.abs(np.fft.rfft(v[:n] * np.hanning(n))) ** 2
        f = np.fft.rfftfreq(n, 1 / sr)
        tot = spec.sum() + 1e-30
        hf5, hf10 = db(spec[f > 5000].sum() / tot), db(spec[f > 10000].sum() / tot)
        # floor between harmonics: median of the spectrum in 100 Hz-10 kHz, relative to its maximum
        band = spec[(f > 100) & (f < 10000)]
        floor = db(np.median(band) / (band.max() + 1e-30)) if band.size else 0
        d2 = np.diff(v, 2)
        thr = 8 * np.sqrt((d2 ** 2).mean()) if ms > 0 else np.inf
        clicks = int((np.abs(d2) > thr).sum()) if ms > 0 else 0
        same = np.concatenate(([False], v[1:] == v[:-1], [False]))
        edges = np.flatnonzero(np.diff(same.astype(int)))
        runs = (edges[1::2] - edges[0::2] + 1) if edges.size else np.array([0])
        clip = int((np.abs(v) >= 32767 / 32768).sum())
        print(f'{name[:30]:30} {"LR"[c]:2} {db(ms):7.1f} {db(np.abs(v).max() ** 2 + 1e-30):7.1f} {clip:5d} '
              f'{hf5:6.1f} {hf10:6.1f} {floor:6.1f} {clicks:6d} {int(runs.max()):7d} {int((runs >= 4).sum()):6d} '
              f'{side:6.1f}')
