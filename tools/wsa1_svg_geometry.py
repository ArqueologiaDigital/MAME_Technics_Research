#!/usr/bin/env python3
"""Exact geometry of every shape in Felipe's SX-WSA1R control-panel artwork.

WHAT QUESTION THIS ANSWERS
--------------------------
"Where, in the 1600x500 render, is control X?"  Every <bounds> value in
src/mame/layout/wsa1r.lay came out of this script, so the layout is
re-derivable from the drawing rather than measured by eye.

    python3 tools/wsa1_svg_geometry.py                  # the whole table
    python3 tools/wsa1_svg_geometry.py path80 ellipse45 # just these ids
    python3 tools/wsa1_svg_geometry.py --selftest       # assert the landmarks

Source (Felipe's, read-only):
    ~/compartilhado/KN7000/wsa1r_artwork/wsa1r_cpanel.svg
viewBox "0 0 423.33334 132.29166", nominal width 1600 -> px = u * 3.7795274.

WHY A SCRIPT AND NOT A RULER: the drawing nests transforms (a layer
translate, then per-group matrices, and the two ball/wheel groups carry a
ROTATION).  A naive parse that ignores the rotation on an <ellipse> reports
the DATA ENTRY wheel as 64x207 instead of 153x153.  Rotated ellipse extent is
    hw = hypot(a*rx, c*ry)   hh = hypot(b*rx, d*ry)
for the matrix [a c; b d]; that identity is what this script implements and
what the --selftest checks.
"""

import math
import os
import re
import sys
import xml.etree.ElementTree as ET

SVG = '{http://www.w3.org/2000/svg}'
ART = os.path.expanduser('~/compartilhado/KN7000/wsa1r_artwork/wsa1r_cpanel.svg')
SCALE = 1600.0 / 423.33334          # user units -> render px


# ---------------------------------------------------------------- transforms

def mat_mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B,
            a * C + c * D, b * C + d * D,
            a * E + c * F + e, b * E + d * F + f)


def parse_transform(s):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    if not s:
        return m
    for name, args in re.findall(r'(\w+)\s*\(([^)]*)\)', s):
        v = [float(x) for x in re.split(r'[\s,]+', args.strip()) if x]
        if name == 'matrix':
            n = tuple(v[:6])
        elif name == 'translate':
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == 'scale':
            sx = v[0]
            sy = v[1] if len(v) > 1 else sx
            n = (sx, 0, 0, sy, 0, 0)
        elif name == 'rotate':
            a = math.radians(v[0])
            n = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                n = mat_mul(mat_mul((1, 0, 0, 1, v[1], v[2]), n),
                            (1, 0, 0, 1, -v[1], -v[2]))
        else:
            continue
        m = mat_mul(m, n)
    return m


def apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


# ---------------------------------------------------------------- path parse

TOK = re.compile(r'([MmZzLlHhVvCcSsQqTtAa])|(-?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)')


def flatten_path(d, steps=16):
    """Return the path's points in USER space (beziers sampled, arcs by their
    endpoints and control box -- no arc in this drawing carries a bbox the
    endpoints miss by more than a pixel, and --selftest pins the ones that
    matter)."""
    toks = [(c or n) for c, n in TOK.findall(d)]
    pts, i, cmd = [], 0, None
    cx = cy = sx = sy = 0.0
    px = py = None      # last control point, for S/T

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    def bez(x0, y0, x1, y1, x2, y2, x3, y3):
        for k in range(1, steps + 1):
            t = k / steps
            u = 1 - t
            pts.append((u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3,
                        u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3))

    while i < len(toks):
        if toks[i] and toks[i][0].isalpha():
            cmd = toks[i]
            i += 1
            if cmd in 'Zz':
                cx, cy = sx, sy
                continue
        if i >= len(toks):
            break
        rel = cmd.islower()
        C = cmd.upper()
        if C == 'M':
            x, y = num(), num()
            if rel:
                x, y = cx + x, cy + y
            cx, cy = sx, sy = x, y
            pts.append((cx, cy))
            cmd = 'l' if rel else 'L'
        elif C == 'L':
            x, y = num(), num()
            if rel:
                x, y = cx + x, cy + y
            cx, cy = x, y
            pts.append((cx, cy))
        elif C == 'H':
            x = num()
            cx = cx + x if rel else x
            pts.append((cx, cy))
        elif C == 'V':
            y = num()
            cy = cy + y if rel else y
            pts.append((cx, cy))
        elif C == 'C':
            x1, y1, x2, y2, x, y = (num() for _ in range(6))
            if rel:
                x1, y1, x2, y2, x, y = cx + x1, cy + y1, cx + x2, cy + y2, cx + x, cy + y
            bez(cx, cy, x1, y1, x2, y2, x, y)
            px, py = x2, y2
            cx, cy = x, y
        elif C == 'S':
            x2, y2, x, y = (num() for _ in range(4))
            if rel:
                x2, y2, x, y = cx + x2, cy + y2, cx + x, cy + y
            x1, y1 = (2 * cx - px, 2 * cy - py) if px is not None else (cx, cy)
            bez(cx, cy, x1, y1, x2, y2, x, y)
            px, py = x2, y2
            cx, cy = x, y
        elif C == 'Q':
            x1, y1, x, y = (num() for _ in range(4))
            if rel:
                x1, y1, x, y = cx + x1, cy + y1, cx + x, cy + y
            bez(cx, cy, cx + 2.0 / 3 * (x1 - cx), cy + 2.0 / 3 * (y1 - cy),
                x + 2.0 / 3 * (x1 - x), y + 2.0 / 3 * (y1 - y), x, y)
            px, py = x1, y1
            cx, cy = x, y
        elif C == 'T':
            x, y = num(), num()
            if rel:
                x, y = cx + x, cy + y
            x1, y1 = (2 * cx - px, 2 * cy - py) if px is not None else (cx, cy)
            bez(cx, cy, x1, y1, x1, y1, x, y)
            px, py = x1, y1
            cx, cy = x, y
        elif C == 'A':
            rx, ry, rot, laf, sf, x, y = (num() for _ in range(7))
            if rel:
                x, y = cx + x, cy + y
            # endpoints plus the ellipse's own extent about the chord midpoint
            pts.append((cx, cy))
            pts.append((x, y))
            mx, my = (cx + x) / 2, (cy + y) / 2
            pts.append((mx - rx, my - ry))
            pts.append((mx + rx, my + ry))
            cx, cy = x, y
        else:
            i += 1
    return pts


# ---------------------------------------------------------------- shape bbox

def shape_points(el):
    """Points in the element's OWN user space, or None if it has no geometry."""
    tag = el.tag.replace(SVG, '')
    g = lambda k, dflt=0.0: float(el.get(k, dflt))
    if tag == 'rect':
        x, y, w, h = g('x'), g('y'), g('width'), g('height')
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], 'rect'
    if tag == 'circle':
        cx, cy, r = g('cx'), g('cy'), g('r')
        return [(cx, cy, r, r)], 'ellipse'
    if tag == 'ellipse':
        cx, cy = g('cx'), g('cy')
        rx = float(el.get('rx', el.get('r', 0)))
        ry = float(el.get('ry', el.get('r', 0)))
        return [(cx, cy, rx, ry)], 'ellipse'
    if tag == 'path':
        d = el.get('d')
        return (flatten_path(d), 'path') if d else (None, None)
    if tag == 'text':
        x = el.get('x')
        y = el.get('y')
        if x is None:
            ts = el.find(SVG + 'tspan')
            if ts is None:
                return None, None
            x, y = ts.get('x', '0'), ts.get('y', '0')
        return [(float(x.split()[0]), float(y.split()[0]))], 'text'
    return None, None


def bbox_px(el, m):
    pts, kind = shape_points(el)
    if not pts:
        return None
    if kind == 'ellipse':
        cx, cy, rx, ry = pts[0]
        a, b, c, d, e, f = m
        ox, oy = apply(m, cx, cy)
        hw = math.hypot(a * rx, c * ry)
        hh = math.hypot(b * rx, d * ry)
        x0, y0, x1, y1 = ox - hw, oy - hh, ox + hw, oy + hh
    else:
        xs, ys = [], []
        for p in pts:
            X, Y = apply(m, p[0], p[1])
            xs.append(X)
            ys.append(Y)
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    return (x0 * SCALE, y0 * SCALE, (x1 - x0) * SCALE, (y1 - y0) * SCALE), kind


def collect(path=ART):
    """id -> (x, y, w, h, kind) in render px, in document order."""
    root = ET.parse(path).getroot()
    out = []

    def rec(node, m):
        for ch in node:
            tag = ch.tag.replace(SVG, '')
            if tag in ('defs', 'metadata', 'namedview', 'clipPath'):
                continue
            cm = mat_mul(m, parse_transform(ch.get('transform')))
            if tag == 'g':
                rec(ch, cm)
                continue
            r = bbox_px(ch, cm)
            if r is None:
                continue
            (x, y, w, h), kind = r
            txt = ''
            if kind == 'text':
                txt = "".join(ch.itertext()).strip()
            out.append((ch.get('id', ''), x, y, w, h, kind, txt))
    rec(root, (1, 0, 0, 1, 0, 0))
    return out


# ---------------------------------------------------------------- self-test

LANDMARKS = {
    # id            x        y       w       h      tol
    'rect27':     (632.836, 84.961, 320.000, 240.000, 0.05),   # the LCD, drawn 1:1
    'rect28':     (600.5,   74.5,   383.0,  264.0,   0.6),     # inner bezel
    'rect135':    (548.0,   44.0,   488.0,  313.0,   0.6),     # outer bezel
    'circle276':  (1110.5,  164.5,  153.0,  153.0,   0.6),     # DATA ENTRY wheel
    'circle225':  (244.5,   164.5,  153.0,  153.0,   0.6),     # REALTIME CREATOR ball
    'path80':     (244.5,   101.5,   42.0,   25.0,   0.6),     # MENU PART button
    'path46':     (617.5,   375.5,   34.0,   24.0,   0.6),     # under-LCD key col1 top
    'path231':    (527.5,   392.5,   42.0,   25.0,   0.6),     # COMPARE
    'ellipse45':  (263.3,    77.3,    6.4,    6.4,   0.2),     # MENU PART LED
}


def selftest():
    tbl = {i: (x, y, w, h) for i, x, y, w, h, k, t in collect()}
    bad = 0
    for i, (X, Y, W, H, tol) in LANDMARKS.items():
        if i not in tbl:
            print('MISSING %s' % i)
            bad += 1
            continue
        x, y, w, h = tbl[i]
        for got, want, nm in ((x, X, 'x'), (y, Y, 'y'), (w, W, 'w'), (h, H, 'h')):
            if abs(got - want) > tol:
                print('FAIL %-12s %s: got %.3f want %.3f' % (i, nm, got, want))
                bad += 1
    # the rotation trap: parsed WITHOUT the group matrix the wheel is not square
    print('%d landmarks, %d failures' % (len(LANDMARKS), bad))
    return bad


if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == '--selftest':
        sys.exit(1 if selftest() else 0)
    rows = collect()
    want = set(args)
    print('%-14s %9s %9s %9s %9s  %-8s %s' % ('id', 'x', 'y', 'w', 'h', 'kind', 'text'))
    for i, x, y, w, h, k, t in rows:
        if want and i not in want:
            continue
        print('%-14s %9.3f %9.3f %9.3f %9.3f  %-8s %s' % (i, x, y, w, h, k, t))
