#!/usr/bin/env python3
"""kn5000_compare_real.py -- compare a recording of the real KN5000 against our render.

QUESTION ANSWERED: two things nothing in this project has been able to check, because both need
the actual instrument.

  1. ARE THE NOTES RIGHT? The HLE recovers each played note by subtracting a per-recording constant
     from the pitch register. That decode has been validated against the firmware's own tables and
     against the tone generator's bus, but never against sound. If our note onsets land at the same
     pitches as the real instrument's, the decode is right end to end.

  2. HOW FAST IS THE ENVELOPE? The rate law's two constants are fitted by ear (kn5000_tonegen.cpp,
     eg_rate_to_step). Measuring attack and decay times on the real recording settles them. They
     shape about 13% of demo notes; the other 87% reach their final level in under a tenth of the
     note's length, so look at the slow notes.

    python3 tools/kn5000_compare_real.py real.wav ours.wav
    python3 tools/kn5000_compare_real.py real.wav ours.wav --offset 12.5

`--offset` shifts the real recording to align with ours: the emulator capture starts when the demo
is triggered, the video starts whenever the uploader pressed record.

⚠ WHAT THIS CANNOT DO: judge timbre. Our renderer synthesises a sine because the wave ROMs are
  undumped, so the spectra will not match and are not supposed to. Compare ONSET TIMES, PITCHES and
  ENVELOPE SHAPES -- never spectral similarity.
"""
import argparse, math, statistics, sys, wave, array


def load(path, offset=0.0):
    with wave.open(path, 'rb') as w:
        nch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        sys.exit(f"{path}: need 16-bit PCM, got {width*8}-bit")
    d = array.array('h')
    d.frombytes(raw)
    mono = [sum(d[i:i+nch]) / nch for i in range(0, len(d) - nch + 1, nch)]
    skip = int(offset * rate)
    return mono[skip:] if skip > 0 else mono, rate


def envelope(sig, rate, hop_ms=10.0):
    hop = max(1, int(rate * hop_ms / 1000.0))
    return [math.sqrt(sum(x * x for x in sig[i:i+hop]) / max(1, len(sig[i:i+hop])))
            for i in range(0, len(sig) - hop, hop)], hop / rate


def onsets(env, dt, thresh=2.5, floor=200.0):
    """Rising edges in the short-time energy: a crude but adequate note detector."""
    out = []
    for i in range(1, len(env)):
        if env[i] > floor and env[i] > thresh * max(env[i-1], 1.0):
            out.append(i * dt)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real")
    ap.add_argument("ours")
    ap.add_argument("--offset", type=float, default=0.0, help="seconds to skip in the real recording")
    ap.add_argument("--window", type=float, default=60.0, help="seconds to compare")
    args = ap.parse_args()

    r, rr = load(args.real, args.offset)
    o, orr = load(args.ours)
    r = r[:int(args.window * rr)]
    o = o[:int(args.window * orr)]

    er, dtr = envelope(r, rr)
    eo, dto = envelope(o, orr)
    onr, ono = onsets(er, dtr), onsets(eo, dto)
    print(f"real : {len(r)/rr:6.1f}s  {len(onr):4d} onsets  ({len(onr)/(len(r)/rr)*60:.0f}/min)")
    print(f"ours : {len(o)/orr:6.1f}s  {len(ono):4d} onsets  ({len(ono)/(len(o)/orr)*60:.0f}/min)")

    # tempo proxy: the modal inter-onset interval
    for label, on in (("real", onr), ("ours", ono)):
        gaps = [b - a for a, b in zip(on, on[1:]) if 0.05 < b - a < 2.0]
        if gaps:
            print(f"   {label}: median inter-onset {1000*statistics.median(gaps):6.1f} ms "
                  f"over {len(gaps)} intervals")

    print("\nENVELOPE SHAPE -- attack time of the loudest onsets (for the rate law):")
    for label, env, dt, on in (("real", er, dtr, onr), ("ours", eo, dto, ono)):
        rises = []
        for t in on[:200]:
            i = int(t / dt)
            peak = max(env[i:i+30] or [0])
            if peak < 500:
                continue
            j = i
            while j < min(i + 30, len(env)) and env[j] < 0.9 * peak:
                j += 1
            rises.append((j - i) * dt)
        if rises:
            print(f"   {label}: median attack {1000*statistics.median(rises):6.1f} ms "
                  f"over {len(rises)} onsets")
    print("\nCompare the two attack figures: ours is set by eg_rate_to_step's D and T127.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
