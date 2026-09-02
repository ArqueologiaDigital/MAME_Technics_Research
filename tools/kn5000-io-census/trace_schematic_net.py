#!/usr/bin/env python3
"""Follow an axis-aligned wire across a rendered Technics service-manual sheet.

Question it answers: "which CPU pin is this schematic net actually on?"  The
KN5000/WSA1 service manuals are IMAGE-ONLY PDFs, so no amount of grepping helps
and reading a 160-pin fan by eye is how pin claims get made up.  This walks the
ink instead: give it a start point on a wire and it reports every corner until
the wire ends or hits a junction.

Render the page first (poppler):

    pdftoppm -f 32 -l 32 -r 600 -png \
        ~/compartilhado/kn5000-docs/service_manual/technics_sx-kn5000.pdf p

Then, e.g. the result quoted in kn5000.cpp's Port H comment -- start on the
IC5 pin-12..17 leads at x=4145 and walk LEFT to the sheet's net labels:

    ./trace_schematic_net.py p-32.png --from 4145,2722 --dir left
    ./trace_schematic_net.py p-32.png --from 3000,2027 --dir right

    (pin 12 lead, y=2722)  -> (4033,2023) -> ... the FDCRST label row
    (FDCRST label, y=2027) -> (4036,2027) -> (4036,2727) -> pin 12

--pins finds the pin leads along one edge of a chip so you do not have to guess
the y coordinates:

    ./trace_schematic_net.py p-32.png --pins left --band 4150,4236 --range 2200,4050

--labels does the same for the sheet-connector rows on the left margin:

    ./trace_schematic_net.py p-32.png --labels --band 2900,3050 --range 1800,2600

CAVEAT, and it matters: this is a pixel walker, not a netlist extractor.  Where
two wires touch or a junction dot sits on the path it can step onto the wrong
one.  ALWAYS trace a net from BOTH ends and check the two agree, and always
check that nets whose destination you already know come out right -- that is the
control.  A single one-way trace is not evidence.
"""
import argparse
import numpy as np
from PIL import Image


def load(path, thresh=128):
    return np.array(Image.open(path).convert('L')) < thresh


def hrun(b, y, x, dx):
    H, W = b.shape
    while True:
        nx = x + dx
        if not (0 <= nx < W):
            break
        if b[max(0, y - 1):y + 2, nx].any():
            x = nx
        else:
            break
    return x


def vrun(b, y, x, dy):
    H, W = b.shape
    while True:
        ny = y + dy
        if not (0 <= ny < H):
            break
        if b[ny, max(0, x - 1):x + 2].any():
            y = ny
        else:
            break
    return y


def follow(b, y, x, mode, d, steps=30, tol=10):
    """Walk the wire.  tol is how far a perpendicular must extend before it counts
    as a turn rather than as the 3-pixel thickness of the line we are on."""
    out = [(x, y, mode, d)]
    for _ in range(steps):
        if mode == 'h':
            nx = hrun(b, y, x, d)
            if nx == x:
                break
            x = nx
            up, dn = vrun(b, y, x, -1), vrun(b, y, x, 1)
            if up < y - tol and dn <= y + tol:
                mode, d = 'v', -1
            elif dn > y + tol and up >= y - tol:
                mode, d = 'v', 1
            elif up < y - tol and dn > y + tol:
                out.append((x, y, 'JUNCTION', 0))
                break
            else:
                break
        else:
            ny = vrun(b, y, x, d)
            if ny == y:
                break
            y = ny
            lf, rt = hrun(b, y, x, -1), hrun(b, y, x, 1)
            if lf < x - tol and rt <= x + tol:
                mode, d = 'h', -1
            elif rt > x + tol and lf >= x - tol:
                mode, d = 'h', 1
            elif lf < x - tol and rt > x + tol:
                out.append((x, y, 'JUNCTION', 0))
                break
            else:
                break
        out.append((x, y, mode, d))
    return out


def groups(idx, gap=3):
    if not idx:
        return []
    g, cur = [], [idx[0]]
    for v in idx[1:]:
        if v - cur[-1] <= gap:
            cur.append(v)
        else:
            g.append(cur)
            cur = [v]
    g.append(cur)
    return [(c[0] + c[-1]) // 2 for c in g]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image')
    ap.add_argument('--from', dest='start', help='X,Y to start from')
    ap.add_argument('--dir', choices=('left', 'right', 'up', 'down'), default='left')
    ap.add_argument('--sweep', type=int, default=5,
                    help='try +/- this many rows/columns and keep the longest walk; '
                         'the printed centre of a line is rarely its exact centre')
    ap.add_argument('--tol', type=int, default=10)
    ap.add_argument('--pins', choices=('left', 'right'),
                    help='list pin-lead rows along a chip edge')
    ap.add_argument('--labels', action='store_true',
                    help='list sheet-connector wire rows')
    ap.add_argument('--band', help='LO,HI of the axis scanned for --pins/--labels')
    ap.add_argument('--range', dest='rng', help='LO,HI of rows to search')
    a = ap.parse_args()
    b = load(a.image)

    if a.pins or a.labels:
        blo, bhi = (int(v) for v in a.band.split(','))
        rlo, rhi = (int(v) for v in a.rng.split(','))
        rows = [y for y in range(rlo, rhi) if b[y, blo:bhi].mean() > 0.9]
        print(' '.join(str(v) for v in groups(rows)))
        return

    x0, y0 = (int(v) for v in a.start.split(','))
    mode, d = ('h', -1) if a.dir == 'left' else ('h', 1) if a.dir == 'right' \
        else ('v', -1) if a.dir == 'up' else ('v', 1)
    best = None
    for off in range(-a.sweep, a.sweep + 1):
        p = follow(b, y0 + off if mode == 'h' else y0,
                   x0 if mode == 'h' else x0 + off, mode, d, tol=a.tol)
        if best is None or len(p) > len(best):
            best = p
    print(' -> '.join('(%d,%d)' % (x, y) + (' %s' % m if m == 'JUNCTION' else '')
                      for x, y, m, _ in best))


if __name__ == '__main__':
    main()
