#!/usr/bin/env python3
"""Semitone-resolved spectral analysis + onset/pitch extraction, numpy only.

No librosa / scipy in this environment, so everything is written from scratch.

The transform is a bank of single-frequency Hann-windowed sliding DFTs, one per
MIDI pitch -- a constant-Q analysis in all but name.  The window length for pitch
p is a fixed number of periods of p (clamped), so low notes get long windows
(frequency selectivity) and high notes short ones (time resolution).  Each band
is evaluated by FFT correlation, which is exact.
"""
import numpy as np
import wave

SR = 48000


def load_wav(path, channel=None):
    """Return (float64 samples in [-1,1], sr).  channel=None -> mean of ch1,ch2.

    The emulator's -wavwrite files are 3-channel: ch0 = flopsndout (always
    silent), ch1 = LEFT, ch2 = RIGHT.
    """
    w = wave.open(path)
    n = w.getnframes()
    nch = w.getnchannels()
    raw = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, nch).astype(np.float64)
    if channel is None:
        x = raw[:, 1:3].mean(axis=1) if nch >= 3 else raw.mean(axis=1)
    else:
        x = raw[:, channel]
    return x / 32768.0, w.getframerate()


def midi_hz(p):
    return 440.0 * 2.0 ** ((np.asarray(p, dtype=np.float64) - 69.0) / 12.0)


def _fftcorr(z, h, nfr, hop):
    """out[t*hop] = sum_k h[k] * z[t*hop + k], via FFT.  Returns nfr values."""
    w = len(h)
    n = len(z)
    N = 1 << int(np.ceil(np.log2(n + w)))
    Z = np.fft.fft(z, N)
    H = np.fft.fft(np.conj(h[::-1]).astype(np.complex128), N)   # h is real -> conj no-op
    c = np.fft.ifft(Z * H)
    # correlation at lag t sits at index t + w - 1
    idx = np.clip(np.arange(nfr) * hop + w - 1, 0, N - 1)
    return c[idx]


def semitone_spectrogram(x, sr=SR, pmin=21, pmax=110, hop=256,
                         periods=10.0, wmin=1024, wmax=12288):
    """Return (mag[P,T] float32, pitches[P], times[T] seconds).

    times[t] is the CENTRE of the analysis window for frame t.
    """
    pitches = np.arange(pmin, pmax + 1)
    nfr = (len(x) - 1) // hop + 1
    mag = np.zeros((len(pitches), nfr), dtype=np.float32)
    ctr = np.zeros((len(pitches), nfr), dtype=np.float32)
    n = np.arange(len(x), dtype=np.float64)
    for i, p in enumerate(pitches):
        f = float(midi_hz(p))
        w = int(np.clip(round(periods * sr / f), wmin, wmax))
        w = min(w, len(x))
        h = np.hanning(w + 2)[1:-1]
        h = h / h.sum()
        z = x * np.exp(-2j * np.pi * f * n / sr)
        c = _fftcorr(z, h, nfr, hop)
        mag[i] = np.abs(c).astype(np.float32)
        ctr[i] = w / 2.0
    times = (np.arange(nfr) * hop) / sr          # window START
    return mag, pitches, times, ctr


def band_latency(pmin, pmax, sr=SR, periods=10.0, wmin=1024, wmax=12288):
    """Half-window (seconds) per pitch band -- the group delay of the analysis."""
    out = []
    for p in range(pmin, pmax + 1):
        f = float(midi_hz(p))
        w = int(np.clip(round(periods * sr / f), wmin, wmax))
        out.append(w / 2.0 / sr)
    return np.array(out)


def detect_onsets(mag, pitches, times, lat, rel_thresh=0.55, floor_db=-58.0,
                  min_gap_s=0.06, sr=SR, hop=256, dominance=True):
    """Per-pitch onset detection.

    * onset function = half-wave-rectified rise of log-magnitude (a "relative
      difference" / spectral-flux detector), computed over a ~20 ms lag so a
      slow attack still registers;
    * peak-picking with a +-min_gap_s local-maximum requirement;
    * an absolute magnitude floor (floor_db, relative to the loudest bin in the
      whole analysed span) rejects leakage and noise;
    * `dominance` requires the band to be at least as loud as its +-1 semitone
      neighbours, which kills the skirt of a strong sine one semitone away.

    Onset TIMES are corrected by the band's own half-window latency, so an event
    reported at t really did start at ~t in the signal.
    Returns a list of (time_s, pitch, strength), sorted by time.
    """
    P, T = mag.shape
    ref = float(mag.max())
    floor = ref * 10 ** (floor_db / 20.0)
    logm = np.log(np.maximum(mag, floor * 1e-3))
    lag = max(1, int(0.020 * sr / hop))
    d = np.zeros_like(logm)
    d[:, lag:] = logm[:, lag:] - logm[:, :-lag]
    d = np.maximum(d, 0.0)
    gap = max(1, int(min_gap_s * sr / hop))
    out = []
    for i in range(P):
        row = d[i]
        m = mag[i]
        # candidate frames: local maxima of the rise function above threshold
        cand = np.where(row >= rel_thresh)[0]
        for t in cand:
            lo, hi = max(0, t - gap), min(T, t + gap + 1)
            if row[t] < row[lo:hi].max() - 1e-12:
                continue
            # magnitude BEFORE the rise and the local PEAK after it
            tb = max(0, t - lag)
            t2 = min(T - 1, t + lag)
            mb = m[tb]
            mp = m[t:t2 + 1].max()
            if mp < floor:
                continue
            if dominance:
                nb = []
                if i > 0:
                    nb.append(mag[i - 1, t2])
                if i < P - 1:
                    nb.append(mag[i + 1, t2])
                if nb and mp < max(nb):
                    continue
            # TIME REFINEMENT: for a Hann analysis window of length w, a step
            # onset at T0 makes the magnitude cross the half-way point exactly
            # when the window CENTRE passes T0.  Walk forward from tb to the
            # first frame at or above the half-way magnitude.
            half = 0.5 * (mb + mp)
            tc = t
            for u in range(tb, t2 + 1):
                if m[u] >= half:
                    tc = u
                    break
            tt = float(times[tc]) + float(lat[i])
            out.append((tt, int(pitches[i]), float(row[t] * mp)))
    out.sort()
    # de-duplicate: same pitch within min_gap keeps the strongest
    ded = []
    last = {}
    for tt, p, s in out:
        if p in last and tt - last[p] < min_gap_s:
            continue
        last[p] = tt
        ded.append((tt, p, s))
    return ded
