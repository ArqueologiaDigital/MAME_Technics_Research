#!/usr/bin/env python3
"""KN5000 chromatic-sweep pitch audit -- does each note render at the pitch it was asked for?

Reads a run directory produced by tools/kn5000_capture_patch.sh in `sweep` mode
(out.wav + marks.txt + notes.csv) and answers ONE question per note:

    does this note render AT the pitch asked for, an OCTAVE ABOVE, or an octave below?

METHOD, and why it is allowed to fail. For each note we cut the SUSTAIN portion of the WAV
(past the attack), take its magnitude spectrum, and find the LOWEST partial that reaches a
fixed fraction of the peak. The verdict is the raw ratio f_low / f_expected, with
f_expected = 440 * 2**((midi-69)/12); it is only NAMED an octave when it lands within a
quarter tone of one, and otherwise prints as the number of semitones it actually is.

The obvious alternative -- scoring the harmonic sum at f/2, f and 2f and taking the winner
-- was tried first and DOES NOT WORK here, which is worth recording because it looks more
principled: these recordings routinely put more energy in the second harmonic than in the
fundamental (typ. 1.00 vs 0.93), so the score at f and at 2f agrees to within 4% and the
test cannot call the octave at all. The lowest partial can, because an octave error MOVES
the whole series up and leaves nothing below it.

A free autocorrelation f0 estimator was rejected for a different reason: it carries its own
octave errors, which is precisely the defect under investigation, so it could not be told
apart from what it is measuring.

`--free` also prints the raw f_low in Hz.

The per-note-on CSV is joined in, so each row also carries the WAVE CHUNK the note
selected and the period detect_period() measured for it -- which is what turns "note 61
is an octave high" into "chunk N's measured period is wrong".

usage: kn5000_sweep_pitch.py <rundir> [--csv] [--free]
"""
import csv
import math
import os
import sys
import wave

import numpy as np

NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def note_name(m):
    return "%s%d" % (NAMES[m % 12], m // 12 - 1)


def read_wav_mono(path):
    with wave.open(path, "rb") as w:
        nch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit("expected 16-bit WAV, got %d bytes/sample" % sw)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if nch > 1:
        x = x.reshape(-1, nch)
        # The KN5000 renders THREE channels and the first is silent in these captures
        # (see notes/kn5000-do3-is-hdae5000.md -- DO3 is not in the main mix). Averaging a
        # silent channel in does not change the spectrum, but averaging two channels that
        # carry a detuned unison pair DOES: their difference frequency shows up as a
        # spurious partial BELOW the fundamental, which is exactly what this tool must not
        # mistake for an octave. So analyse the single loudest channel.
        energy = (x ** 2).sum(axis=0)
        x = x[:, int(np.argmax(energy))]
    return x, sr


def spectrum(seg, sr, pad=4):
    """Hann-windowed magnitude spectrum, zero-padded for finer frequency probing."""
    seg = seg - seg.mean()
    n = len(seg)
    seg = seg * np.hanning(n)
    nfft = 1 << int(math.ceil(math.log2(n * pad)))
    X = np.abs(np.fft.rfft(seg, nfft))
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
    return freqs, X


def hscore(freqs, X, f0, nharm=8, tol=0.03):
    """Sum of harmonic peak magnitudes, each maximised over a +-tol band."""
    tot = 0.0
    nyq = freqs[-1]
    for k in range(1, nharm + 1):
        f = f0 * k
        if f > nyq * 0.9:
            break
        lo, hi = np.searchsorted(freqs, f * (1 - tol)), np.searchsorted(freqs, f * (1 + tol))
        if hi > lo:
            tot += X[lo:hi].max()
    return tot


def lowest_partial(freqs, X, thresh=0.20, fmin=50.0):
    """Frequency of the LOWEST spectral peak reaching `thresh` of the maximum.

    This -- not the harmonic sum -- is the measurement that decides the octave here, and
    the reason is MEASURED rather than stylistic: on these flute recordings the SECOND
    harmonic is consistently stronger than the fundamental (typ. 1.00 vs 0.93), so a
    harmonic-sum score at f and at 2f comes out within 4% of each other and cannot call
    the octave at all. The lowest partial can: if a note were rendered an octave high its
    lowest partial would MOVE UP by a factor of two, with nothing left below it.

    It can still fail, and says so: `f_low/f_expected` is reported as a raw ratio, so a
    non-octave error appears as a non-octave number instead of being rounded to one.

    `thresh` is 0.20 of the maximum and that is MEASURED, not taste: these patches render a
    detuned unison pair, so every partial arrives as a cluster of sidebands ~10 Hz apart,
    and a 0.05 threshold picks up the bottom sideband of the cluster instead of the partial
    itself -- which reported a real one-octave error as +10.6 semitones. At 0.20 the same
    notes read +11.8 to +12.0, agreeing with the period ratio measured straight off the ROM.
    """
    lo = int(np.searchsorted(freqs, fmin))
    if lo >= len(X) - 1:
        return 0.0
    cut = thresh * X[lo:].max()
    for i in range(lo + 1, len(X) - 1):
        if X[i] >= cut and X[i] > X[i - 1] and X[i] >= X[i + 1]:
            # parabolic refinement on the log magnitude
            y0, y1, y2 = X[i - 1], X[i], X[i + 1]
            den = y0 - 2 * y1 + y2
            d = 0.5 * (y0 - y2) / den if den != 0 else 0.0
            d = max(-0.5, min(0.5, d))
            return float(freqs[i] + d * (freqs[1] - freqs[0]))
    return 0.0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_csv = "--csv" in sys.argv
    want_free = "--free" in sys.argv
    rundir = args[0]

    data, sr = read_wav_mono(os.path.join(rundir, "out.wav"))

    rows = []
    npath = os.path.join(rundir, "notes.csv")
    if os.path.exists(npath):
        with open(npath) as f:
            for r in csv.DictReader(f):
                try:
                    r["t_on"] = float(r["t_on"])
                except (KeyError, TypeError, ValueError):
                    continue
                rows.append(r)

    hdr = ["patch", "midi", "note", "sel040", "bank", "pg", "chunk", "real",
           "samples", "period", "step", "OCT", "ratio", "peak"]
    if want_free:
        hdr += ["f_low"]
    print("# %s   sr=%d  %.2f s" % (rundir, sr, len(data) / sr))
    if as_csv:
        print(",".join(hdr))
    else:
        print(("%-11s %4s %-5s %6s %4s %3s %5s %4s %8s %7s %8s %5s %7s %7s"
               + (" %8s" if want_free else "%.0s")) % tuple(hdr + ([""] if not want_free else [])))

    with open(os.path.join(rundir, "marks.txt")) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            patch, midi_s, t_on_s, t_off_s = line.split()
            midi, t_on, t_off = int(midi_s), float(t_on_s), float(t_off_s)
            if midi < 0:
                continue

            dur = t_off - t_on
            a = int((t_on + 0.35 * dur) * sr)
            b = min(int((t_on + 0.95 * dur) * sr), len(data))
            seg = data[a:b]
            free_st = ""
            if len(seg) < 1024:
                verdict, margin, peak = "SHORT", 0.0, 0
            else:
                peak = int(np.abs(seg).max())
                if peak < 40:
                    verdict, margin = "SIL", 0.0
                else:
                    freqs, X = spectrum(seg, sr)
                    fx = 440.0 * 2.0 ** ((midi - 69) / 12.0)
                    flow = lowest_partial(freqs, X)
                    if flow <= 0:
                        verdict, margin = "?", 0.0
                    else:
                        margin = flow / fx
                        st = 12.0 * math.log2(margin)
                        # name it an octave only if it really is one, within a quarter tone
                        if abs(st) <= 0.5:
                            verdict = "ok"
                        elif abs(st - 12.0) <= 0.5:
                            verdict = "+12"
                        elif abs(st + 12.0) <= 0.5:
                            verdict = "-12"
                        else:
                            verdict = "%+.1f" % st
                    if want_free:
                        free_st = "%.1f" % flow

            cand = sorted((r for r in rows if abs(r["t_on"] - t_on) < 0.05),
                          key=lambda r: abs(r["t_on"] - t_on))
            r = cand[0] if cand else {}
            vals = [patch, midi, note_name(midi), r.get("sel040", "-"), r.get("bank", "-"),
                    r.get("page", "-"), r.get("chunk", "-"), r.get("wave_real", "-"),
                    r.get("wave_samples", "-"), r.get("period", "-"),
                    r.get("pitch_step", "-"), verdict, "%.2f" % margin, peak]
            if want_free:
                vals.append(free_st)
            if as_csv:
                print(",".join(str(v) for v in vals))
            else:
                fmt = "%-11s %4d %-5s %6s %4s %3s %5s %4s %8s %7s %8s %5s %7s %7d"
                if want_free:
                    fmt += " %8s"
                print(fmt % tuple(vals))


if __name__ == "__main__":
    main()
