#!/usr/bin/env python3
# firstnote.py WAV... -- pitch, level and noise floor of the passage's first note (A1, a held C4), in any recording.
#
# QUESTION IT ANSWERS (README.md here, "Live against computed"): is the note the listener hears the note MAME
# computed? The first note is found by level alone (the first 10 ms block above -60 dBFS after the boot's silence),
# so it works on a live capture, which starts at an unknown offset and plays stretched. Measured over 0.5-2.5 s
# after the onset (inside A1 for any stretch >= 1), left channel:
#   pitch   the strongest spectral peak above 150 Hz, Hz (a C4 is 261.6 Hz; MAME's computed C4 is 261.5)
#   floor   median spectral level in 100 Hz-10 kHz, dB under the strongest peak (between the harmonics: a clean held
#           note leaves it deep; gaps, clicks and resampling artefacts fill it)
#   rms     dBFS
# Needs numpy only.
import sys, wave
import numpy as np

print(f'{"wav":48} {"onset s":>8} {"pitch Hz":>9} {"floor dB":>9} {"rms dBFS":>9}')
for p in sys.argv[1:]:
    w = wave.open(p)
    sr, n = w.getframerate(), w.getnchannels()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, n)[:, 0].astype(np.float64) / 32768
    blk = sr // 100
    m = len(x) // blk
    e = np.sqrt((x[:m * blk] ** 2).reshape(m, blk).mean(axis=1))
    on = int(np.flatnonzero(e > 10 ** (-60 / 20))[0]) / 100
    v = x[int((on + 0.5) * sr):int((on + 2.5) * sr)]
    k = 1 << int(np.log2(len(v)))
    sp = np.abs(np.fft.rfft(v[:k] * np.hanning(k))) ** 2
    f = np.fft.rfftfreq(k, 1 / sr)
    band = sp[(f > 100) & (f < 10000)]
    pitch = f[f > 150][np.argmax(sp[f > 150])]
    print(f'{p[-48:]:48} {on:8.2f} {pitch:9.1f} {10 * np.log10(np.median(band) / band.max()):9.1f} '
          f'{10 * np.log10((v ** 2).mean()):9.1f}')
