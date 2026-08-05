#!/usr/bin/env python3
"""Cache the semitone spectrogram + rise function of an emulator capture."""
import sys
import numpy as np
import audio

SR = 48000
PMIN, PMAX = 24, 108
HOP = 256
PERIODS, WMIN, WMAX = 20., 2048, 8192


def build(path, t_lo, t_hi, channel=None):
    x, sr = audio.load_wav(path, channel)
    assert sr == SR
    a, b = int(t_lo * SR), int(t_hi * SR)
    seg = x[a:b]
    clip = int((np.abs(seg) >= 0.9999).sum())
    mag, pitches, times, _ = audio.semitone_spectrogram(
        seg, pmin=PMIN, pmax=PMAX, hop=HOP, periods=PERIODS, wmin=WMIN, wmax=WMAX)
    lat = audio.band_latency(PMIN, PMAX, periods=PERIODS, wmin=WMIN, wmax=WMAX)
    return dict(mag=mag, pitches=pitches, times=times + t_lo, lat=lat,
                t_lo=t_lo, t_hi=t_hi, rms=float(np.sqrt((seg ** 2).mean())),
                clip=clip, n=len(seg))


def rise(mag, floor_db=-46.0, lag_s=0.020, hop=HOP, sr=SR):
    ref = float(mag.max())
    floor = ref * 10 ** (floor_db / 20.0)
    logm = np.log(np.maximum(mag, floor))
    lag = max(1, int(lag_s * sr / hop))
    d = np.zeros_like(logm)
    d[:, lag:] = logm[:, lag:] - logm[:, :-lag]
    return np.maximum(d, 0.0)


if __name__ == '__main__':
    path = sys.argv[1]
    lo, hi = float(sys.argv[2]), float(sys.argv[3])
    out = sys.argv[4]
    d = build(path, lo, hi)
    np.savez_compressed(out, **{k: v for k, v in d.items()
                                if isinstance(v, np.ndarray)},
                        meta=np.array([d['t_lo'], d['t_hi'], d['rms'], d['clip'], d['n']]))
    print(f"{path} [{lo},{hi}] rms={d['rms']:.4f} clipped_samples={d['clip']} "
          f"({100*d['clip']/d['n']:.3f}%) mag shape {d['mag'].shape} -> {out}")
