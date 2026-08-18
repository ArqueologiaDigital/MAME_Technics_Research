#!/usr/bin/env python3
"""wav_rms.py -- per-channel RMS of a WAV, whole-file and in fixed windows.

QUESTION ANSWERED: did the emulated instrument actually make sound, and did it keep
making it, or did it fall silent partway through?

    python3 tools/wav_rms.py capture.wav                # whole file, per channel
    python3 tools/wav_rms.py capture.wav --window 5     # plus per-5-second windows
    python3 tools/wav_rms.py capture.wav --window 5 --from 40 --to 120 --min-rms 200

With --min-rms it exits 1 if any window in the range is below the threshold, so it can
be used as a gate in a test script.

WHY THE WINDOWS MATTER: a whole-file RMS well above zero is satisfied by a single loud
burst followed by ninety seconds of silence. For "the demo plays", the question is
whether EVERY window has signal in it -- a gap is the failure this is looking for.

⚠ ALWAYS MEASURE A NULL FIRST. A difference from silence is not a signal: capture the
  same machine with no stimulus, and quote every later number against that baseline.
"""
import argparse, sys, wave, array, math


def rms_of(samples):
    if not samples:
        return 0.0
    return math.sqrt(sum(float(s) * float(s) for s in samples) / len(samples))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--window", type=float, default=0.0, help="window length in seconds")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--min-rms", type=float, default=None,
                    help="fail if any window in [--from,--to) is below this on BOTH channels")
    args = ap.parse_args()

    with wave.open(args.wav, "rb") as w:
        nch, width, rate, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if width != 2:
            sys.exit(f"{args.wav}: expected 16-bit samples, got {width * 8}-bit")
        raw = w.readframes(nframes)

    data = array.array("h")
    data.frombytes(raw)
    chans = [data[c::nch] for c in range(nch)]

    print(f"{args.wav}: {nch}ch {rate}Hz {nframes / rate:.1f}s")
    for c, ch in enumerate(chans):
        print(f"  channel {c}: rms {rms_of(ch):8.1f}   peak {max(max(ch), -min(ch)):6d}")

    if not args.window:
        return 0

    t1 = args.t1 if args.t1 is not None else nframes / rate
    step = int(args.window * rate)
    failures = []
    t = args.t0
    while t < t1:
        a, b = int(t * rate), min(int((t + args.window) * rate), nframes)
        if a >= nframes:
            break
        vals = [rms_of(ch[a:b]) for ch in chans]
        flag = ""
        if args.min_rms is not None and all(v < args.min_rms for v in vals):
            flag = "  <-- BELOW THRESHOLD"
            failures.append(t)
        print(f"  t={t:6.1f}s  " + "  ".join(f"ch{c} {v:8.1f}" for c, v in enumerate(vals)) + flag)
        t += args.window

    if args.min_rms is not None:
        if failures:
            print(f"FAIL: {len(failures)} window(s) below {args.min_rms}, first at t={failures[0]:.1f}s")
            return 1
        print(f"PASS: every window from {args.t0:.0f}s to {t1:.0f}s is above {args.min_rms}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
