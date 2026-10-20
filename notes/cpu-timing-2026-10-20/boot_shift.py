#!/usr/bin/env python3
# boot_shift.py DIR_A DIR_B [STEP] -- when does binary B reach each screen binary A shows during the boot?
#
# DIR_A and DIR_B hold the snapshots prof.lua (PROF_SNAP=1) saved every STEP seconds (default 1) of emulated time:
# NNNN.png = (NNNN + 1) * STEP s. A "screen" is a snapshot of A that differs from A's previous one (mean absolute
# difference of the LCD area, downscaled, above NEW); for each, the table gives the first time A shows it and the first
# time B shows the same screen (difference below SAME), and the shift. The LCD area is the overlay layout's
# (x 148-852, y 52-316 in a 1000x750 snapshot).
import sys, os
from PIL import Image

NEW, SAME = 3.0, 3.0

def load(d):
    fs = sorted(f for f in os.listdir(d) if f.endswith('.png'))
    return [Image.open(os.path.join(d, f)).convert('L').crop((148, 52, 852, 316)).resize((176, 66)).tobytes() for f in fs]

def mad(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

def main(a, b, step=1.0):
    A, B = load(a), load(b)
    rows = [('screen', 'A first at s', 'B first at s', 'shift s')]
    prev = None
    n = 0
    for i, ia in enumerate(A):
        if prev is not None and mad(ia, prev) <= NEW:
            continue
        prev = ia
        n += 1
        j = next((j for j, ib in enumerate(B) if mad(ia, ib) <= SAME), None)
        rows.append((str(n), f'{(i + 1) * step:.0f}', '-' if j is None else f'{(j + 1) * step:.0f}',
                     '-' if j is None else f'{(j - i) * step:+.0f}'))
    w = [max(len(r[k]) for r in rows) for k in range(4)]
    for m, r in enumerate(rows):
        print('| ' + ' | '.join(r[k].ljust(w[k]) for k in range(4)) + ' |')
        if m == 0:
            print('|' + '|'.join('-' * (x + 2) for x in w) + '|')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 1.0)
