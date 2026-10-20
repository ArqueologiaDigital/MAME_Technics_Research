#!/usr/bin/env python3
# oracle_attack.py A.wav B.wav [FROM_S] [TO_S] [STEP_MS] -- how two oracle captures differ around the note-on.
# Per STEP_MS window (default 10 ms) from FROM_S to TO_S (default 16.08-16.40 s), channel 0: rms of A, of B, of A-B,
# and the lag (in samples, +-200) at which B best matches A in that window with its correlation. A note that is the
# same sound started a little later shows a steady lag and high correlation; a different sound shows neither.
import struct, sys, wave, math

def ch0(path):
    w = wave.open(path)
    n, c = w.getnframes(), w.getnchannels()
    s = struct.unpack('<%dh' % (n * c), w.readframes(n))
    return s[0::c], w.getframerate()

def main(a, b, t0=16.08, t1=16.40, step_ms=10.0):
    A, fs = ch0(a)
    B, _ = ch0(b)
    win = int(fs * step_ms / 1000)
    rows = [('t s', 'rms A', 'rms B', 'rms A-B', 'lag', 'corr')]
    i = int(t0 * fs)
    while i + win <= int(t1 * fs):
        x = A[i:i + win]
        rms = lambda v: math.sqrt(sum(q * q for q in v) / len(v))
        best = (-2.0, 0)
        ex = math.sqrt(sum(q * q for q in x)) or 1.0
        for lag in range(-200, 201, 2):
            y = B[i + lag:i + lag + win]
            ey = math.sqrt(sum(q * q for q in y)) or 1.0
            c = sum(p * q for p, q in zip(x, y)) / (ex * ey)
            if c > best[0]:
                best = (c, lag)
        rows.append((f'{i / fs:.3f}', f'{rms(x):.1f}', f'{rms(B[i:i + win]):.1f}',
                     f'{rms([p - q for p, q in zip(x, B[i:i + win])]):.1f}', str(best[1]), f'{best[0]:.3f}'))
        i += win
    w = [max(len(r[k]) for r in rows) for k in range(len(rows[0]))]
    for n, r in enumerate(rows):
        print('| ' + ' | '.join(r[k].ljust(w[k]) for k in range(len(r))) + ' |')
        if n == 0:
            print('|' + '|'.join('-' * (x + 2) for x in w) + '|')

if __name__ == '__main__':
    args = sys.argv[1:]
    main(args[0], args[1], *(float(x) for x in args[2:5]))
