#!/usr/bin/env python3
"""gate_windows.py -- question: how loud is the speaker output in each window audio_gates.lua marks?

Reads an audio_gates.lua log and the -wavwrite capture of the same run (16-bit, any channel count;
channels 0 and 1 are the left and right speakers), and prints one row per window: RMS and peak of
both channels.  Besides the probe's WINDOW lines it measures "boot-pmut-low", from 0.05 s to the
first PMUT 0 -> 1 (BootPanelResetCheck), and "boot-after-pmut", the 2 s after it.

Given a second log and capture (the same probe on another build), it adds that run's RMS and the
ratio of the two in dB per window, and the largest per-sample difference over all the normal
windows (W1, W3, W5, W6-before-nmi), the two captures aligned on the key-down sample.

usage:  python3 -I gate_windows.py LOG WAV [LOG_B WAV_B]
"""
import array
import math
import sys
import wave


def windows(logpath):
    out, pmut_up = [], None
    for line in open(logpath):
        f = line.split()
        if not f:
            continue
        if f[0] == "WINDOW":
            out.append((f[1], float(f[2]), float(f[3])))
        elif f[0] == "PMUT" and f[2] == "0" and f[4] == "1" and pmut_up is None:
            pmut_up = float(f[1])
    if pmut_up is not None:
        out.insert(0, ("boot-after-pmut", pmut_up, pmut_up + 2.0))
        out.insert(0, ("boot-pmut-low", 0.05, pmut_up))
    return out


class Wav:
    def __init__(self, path):
        w = wave.open(path)
        assert w.getsampwidth() == 2, "16-bit WAV expected"
        self.ch, self.rate = w.getnchannels(), w.getframerate()
        self.data = array.array("h", w.readframes(w.getnframes()))
        self.frames = len(self.data) // self.ch

    def chan(self, c, a, b):
        i0, i1 = max(0, int(a * self.rate)), min(self.frames, int(b * self.rate))
        return self.data[i0 * self.ch + c:i1 * self.ch:self.ch]

    def stats(self, a, b):
        res = []
        for c in (0, 1):
            s = self.chan(c, a, b)
            rms = math.sqrt(sum(v * v for v in s) / len(s)) if len(s) else 0.0
            res.append((rms, max((abs(v) for v in s), default=0)))
        return res


def table(rows):
    w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    fmt = lambda r: "| " + " | ".join(c.ljust(w[i]) for i, c in enumerate(r)) + " |"
    print(fmt(rows[0]))
    print("|" + "|".join("-" * (x + 2) for x in w) + "|")
    for r in rows[1:]:
        print(fmt(r))


def main():
    wa, wina = Wav(sys.argv[2]), windows(sys.argv[1])
    two = len(sys.argv) == 5
    if two:
        wb, winb = Wav(sys.argv[4]), dict((n, (a, b)) for n, a, b in windows(sys.argv[3]))
    head = ["window", "from s", "to s", "L rms", "L peak", "R rms", "R peak"]
    if two:
        head += ["B L rms", "B R rms", "A/B dB"]
    rows = [head]
    for name, a, b in wina:
        (lr, lp), (rr, rp) = wa.stats(a, b)
        row = [name, f"{a:.3f}", f"{b:.3f}", f"{lr:.1f}", str(lp), f"{rr:.1f}", str(rp)]
        if two and name in winb:
            (blr, _), (brr, _) = wb.stats(*winb[name])
            ra, rb = math.hypot(lr, rr), math.hypot(blr, brr)
            db = "-inf" if ra == 0 and rb > 0 else ("n/a" if rb == 0 else f"{20 * math.log10(ra / rb):+.3f}")
            row += [f"{blr:.1f}", f"{brr:.1f}", db]
        rows.append(row)
    table(rows)
    if two:
        # sample-exact comparison of the normal windows, aligned on each run's own window start
        worst, n = 0, 0
        for name, a, b in wina:
            if name in ("W1-normal", "W3-normal", "W5-normal", "W6-before-nmi") and name in winb:
                ba = winb[name][0]
                for c in (0, 1):
                    sa, sb = wa.chan(c, a, b), wb.chan(c, ba, ba + (b - a))
                    m = min(len(sa), len(sb))
                    worst = max(worst, max((abs(sa[i] - sb[i]) for i in range(m)), default=0))
                    n += m
        print(f"\nnormal windows: largest per-sample difference {worst} over {n} samples")


main()
