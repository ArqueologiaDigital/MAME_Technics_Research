#!/usr/bin/env python3
"""List every drawable shape of an Inkscape layout SVG that falls inside a region,
with its transform flattened into absolute Compact-view coordinates.

Question it answers: "which shapes did Felipe add/change in area X, and what is their
exact geometry in the 2000x1500 coordinate space the .lay uses?"

    python3 tools/svg_region_extract.py FILE.svg X0 Y0 X1 Y1 [--diff OTHER.svg]

Bboxes for paths are computed from the path's coordinate pairs (control points included),
so a curve's bbox may be slightly larger than its true extent -- enough to LOCATE a shape,
not to measure it. Geometry is reported exactly (circle centre/radius, path d), transformed.
"""
import re, sys, math
import xml.etree.ElementTree as ET

NS = '{http://www.w3.org/2000/svg}'


def mat_mul(a, b):
    # 2x3 affine, row-major (a,b,c,d,e,f) == [[a,c,e],[b,d,f]]
    a0, a1, a2, a3, a4, a5 = a
    b0, b1, b2, b3, b4, b5 = b
    return (a0 * b0 + a2 * b1,
            a1 * b0 + a3 * b1,
            a0 * b2 + a2 * b3,
            a1 * b2 + a3 * b3,
            a0 * b4 + a2 * b5 + a4,
            a1 * b4 + a3 * b5 + a5)


def parse_transform(s):
    m = (1, 0, 0, 1, 0, 0)
    if not s:
        return m
    for name, args in re.findall(r'(\w+)\s*\(([^)]*)\)', s):
        v = [float(x) for x in re.split(r'[\s,]+', args.strip()) if x]
        if name == 'translate':
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == 'scale':
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == 'matrix':
            t = tuple(v)
        elif name == 'rotate':
            a = math.radians(v[0]); c, s_ = math.cos(a), math.sin(a)
            t = (c, s_, -s_, c, 0, 0)
            if len(v) == 3:                      # rotate about (cx,cy)
                cx, cy = v[1], v[2]
                t = mat_mul((1, 0, 0, 1, cx, cy), mat_mul(t, (1, 0, 0, 1, -cx, -cy)))
        else:
            continue
        m = mat_mul(m, t)
    return m


def apply(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def path_points(d):
    """Every coordinate pair in a path, as (x,y) in the path's own space.
    Handles absolute/relative commands and the h/v shorthands."""
    toks = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:e-?\d+)?', d)
    pts, i, cx, cy, cmd = [], 0, 0.0, 0.0, None
    start = None
    while i < len(toks):
        t = toks[i]
        if re.match(r'[A-Za-z]', t):
            cmd = t; i += 1; continue
        if cmd is None:
            i += 1; continue
        rel = cmd.islower()
        c = cmd.upper()
        n = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6, 'S': 4, 'Q': 4, 'T': 2, 'A': 7}.get(c)
        if n is None:
            i += 1; continue
        if i + n > len(toks):
            break
        v = [float(x) for x in toks[i:i + n]]
        i += n
        if c == 'H':
            cx = cx + v[0] if rel else v[0]
        elif c == 'V':
            cy = cy + v[0] if rel else v[0]
        elif c == 'A':
            cx, cy = (cx + v[5], cy + v[6]) if rel else (v[5], v[6])
        else:
            # every (x,y) pair the command carries; the LAST pair is the new current point
            for k in range(0, n, 2):
                px, py = (cx + v[k], cy + v[k + 1]) if rel else (v[k], v[k + 1])
                pts.append((px, py))
            cx, cy = pts[-1]
        if c in 'HVA':
            pts.append((cx, cy))
        if c == 'M' and start is None:
            start = (cx, cy)
        # after the first M in a polyline the command repeats as L
        if c == 'M':
            cmd = 'l' if rel else 'L'
    return pts


def shapes(path):
    """Yield (tag, id, style, ctm, geometry-dict, bbox) for every drawable."""
    root = ET.parse(path).getroot()

    def walk(e, ctm):
        ctm = mat_mul(ctm, parse_transform(e.get('transform')))
        tag = e.tag.replace(NS, '')
        if tag == 'g' or tag == 'svg':
            for k in e:
                if k.tag.startswith(NS):
                    yield from walk(k, ctm)
            return
        g, pts = {}, []
        if tag == 'circle':
            cx, cy, r = float(e.get('cx', 0)), float(e.get('cy', 0)), float(e.get('r', 0))
            g = dict(cx=cx, cy=cy, r=r)
            pts = [(cx - r, cy - r), (cx + r, cy + r)]
        elif tag == 'rect':
            x, y = float(e.get('x', 0)), float(e.get('y', 0))
            w, h = float(e.get('width', 0)), float(e.get('height', 0))
            g = dict(x=x, y=y, w=w, h=h)
            pts = [(x, y), (x + w, y + h)]
        elif tag == 'path':
            g = dict(d=e.get('d', ''))
            pts = path_points(g['d'])
        elif tag == 'text':
            x, y = float(e.get('x', 0)), float(e.get('y', 0))
            g = dict(x=x, y=y, s=''.join(e.itertext()).strip())
            pts = [(x, y)]
        else:
            return
        if not pts:
            return
        tp = [apply(ctm, *p) for p in pts]
        bbox = (min(p[0] for p in tp), min(p[1] for p in tp),
                max(p[0] for p in tp), max(p[1] for p in tp))
        yield (tag, e.get('id'), e.get('style') or '', ctm, g, bbox)

    yield from walk(root, (1, 0, 0, 1, 0, 0))


def inside(bbox, r):
    return not (bbox[2] < r[0] or bbox[0] > r[2] or bbox[3] < r[1] or bbox[1] > r[3])


def key(s):
    tag, _id, style, ctm, g, bbox = s
    txt = g.get('s', '')
    return (tag, txt, tuple(round(v, 1) for v in bbox))


def fmt(s):
    tag, _id, style, ctm, g, bbox = s
    b = "[%7.2f %7.2f %7.2f %7.2f]" % bbox
    extra = ''
    if tag == 'circle':
        c = apply(ctm, g['cx'], g['cy'])
        extra = "  centre=(%.3f,%.3f) r=%.4f" % (c[0], c[1], g['r'] * math.hypot(ctm[0], ctm[1]))
    elif tag == 'text':
        p = apply(ctm, g['x'], g['y'])
        extra = "  at=(%.2f,%.2f) %r" % (p[0], p[1], g['s'])
    elif tag == 'rect':
        p = apply(ctm, g['x'], g['y'])
        extra = "  xy=(%.2f,%.2f) wh=(%.2f,%.2f)" % (p[0], p[1], g['w'] * ctm[0], g['h'] * ctm[3])
    return "%-6s %-14s %s%s\n        style=%s" % (tag, _id, b, extra, style[:110])


def main():
    f = sys.argv[1]
    reg = tuple(float(x) for x in sys.argv[2:6])
    other = sys.argv[sys.argv.index('--diff') + 1] if '--diff' in sys.argv else None
    A = [s for s in shapes(f) if inside(s[5], reg)]
    if other is None:
        print("# %s  region=%s  %d shapes" % (f, reg, len(A)))
        for s in sorted(A, key=lambda s: (s[5][1], s[5][0])):
            print(fmt(s))
        return
    B = [s for s in shapes(other) if inside(s[5], reg)]
    ka, kb = {key(s): s for s in A}, {key(s): s for s in B}
    print("# region=%s   %s: %d shapes   %s: %d shapes" % (reg, f, len(A), other, len(B)))
    print("\n## only in %s (%d)" % (f, len(set(ka) - set(kb))))
    for k in sorted(set(ka) - set(kb), key=lambda k: (k[2][1], k[2][0])):
        print(fmt(ka[k]))
    print("\n## only in %s (%d)" % (other, len(set(kb) - set(ka))))
    for k in sorted(set(kb) - set(ka), key=lambda k: (k[2][1], k[2][0])):
        print(fmt(kb[k]))
    print("\n## in both (%d)" % len(set(ka) & set(kb)))
    for k in sorted(set(ka) & set(kb), key=lambda k: (k[2][1], k[2][0])):
        print(fmt(ka[k]))


if __name__ == '__main__':
    main()
