#!/usr/bin/env python3
"""The two thresholds gen_wsa1r_lay.py is built on, measured rather than argued.

QUESTION 1 -- why may SHAPE_TOL be 1e-3?
    The generator decides two of the 58 buttons are the same key when their
    geometric signatures agree to one part in a thousand.  That number is only
    defensible if the drawing's own rounding noise sits well below it and the
    real differences sit well above it.  This measures both, over every pair,
    and prints the gap.

QUESTION 2 -- why may the pressed state be a MAME component?
    control_images() used to emit the whole unpressed drawing a second time with
    a 34%-black copy of the shapes over it.  It now emits the base once and lets
    MAME wash it with <rect state="1"> (or <disk> for a round key).  That is only
    legitimate where the old wash was UNIFORM.  This rebuilds the old two-image
    form, composites the new one the way MAME will, and reports the difference
    per shape -- including the ten LCD soft keys, which are two overlapping
    shapes, wash to 1-0.66^2 = 56% in their middle, and are therefore left alone.

RUN
    sh notes/wsa1-probes/build_nsvg_hash.sh          # once, for question 2
    python3 notes/wsa1-probes/wsa1r_shape_tolerance.py
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import gen_wsa1r_lay as G                                        # noqa: E402

HASHER = os.path.join(HERE, "nsvg_hash")


def rel(u, v):
    return abs(u - v) / max(1.0, abs(u), abs(v))


def signatures(art):
    out = []
    for seg, mask, ids, legend, tier in G.BUTTONS:
        x, y, w, h = art.bbox_px(ids)
        sig = G.shape_signature(art, ids, x / G.geo.SCALE, y / G.geo.SCALE)
        out.append((legend, ids, sig))
    return out


def question1(art):
    sigs = signatures(art)
    # the classes the generator actually forms
    classes = []
    for legend, ids, sig in sigs:
        for c in classes:
            if G.same_shape(c[0], sig):
                c[1].append(legend)
                break
        else:
            classes.append((sig, [legend]))
    cls_of = {}
    for n, (sig, members) in enumerate(classes):
        for m in members:
            cls_of[m] = n

    merged, apart = [], []
    for i, (la, ida, sa) in enumerate(sigs):
        for lb, idb, sb in sigs[i + 1:]:
            if sa[0] != sb[0] or len(sa[1]) != len(sb[1]):
                continue                      # different drawing entirely
            d = max((rel(u, v) for u, v in zip(sa[1], sb[1])), default=0.0)
            (merged if cls_of[la] == cls_of[lb] else apart).append((d, la, lb))
    merged.sort()
    apart.sort()

    print("QUESTION 1 -- the merge tolerance, SHAPE_TOL = %g\n" % G.SHAPE_TOL)
    print("  %d buttons form %d shapes." % (len(sigs), len(classes)))
    print("  Pairs compared (same drawing, so comparable at all): %d merged, "
          "%d kept apart.\n" % (len(merged), len(apart)))
    if merged:
        print("  worst disagreement among pairs the generator MERGES:")
        for d, a, b in merged[-3:][::-1]:
            print("     %.3e   %s / %s" % (d, a, b))
    if apart:
        print("  smallest disagreement among pairs it keeps APART:")
        for d, a, b in apart[:3]:
            print("     %.3e   %s / %s" % (d, a, b))
    if merged and apart:
        noise, real = merged[-1][0], apart[0][0]
        print("\n  noise ceiling  %.3e  = SHAPE_TOL / %.0f" % (noise, G.SHAPE_TOL / noise))
        print("  real floor     %.3e  = SHAPE_TOL x %.0f" % (real, real / G.SHAPE_TOL))
        print("  the two are %.0fx apart, and SHAPE_TOL sits between them." % (real / noise))
        return noise, real
    return None, None


def _wash(pix, n, kind, w, h):
    """Composite MAME's 34%-black <rect>/<disk> over an RGBA buffer."""
    out = bytearray(pix)
    cx, cy, rx, ry = w / 2.0, h / 2.0, w / 2.0, h / 2.0
    for i in range(n):
        if kind == 'disk':
            px, py = i % w + 0.5, i // w + 0.5
            if ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 > 1.0:
                continue
        for c in range(3):
            out[i * 4 + c] = int(round(out[i * 4 + c] * 0.66))
        out[i * 4 + 3] = int(round(out[i * 4 + 3] * 0.66 + 255 * 0.34))
    return out


def question2(art):
    if not os.path.exists(HASHER):
        sys.exit("build the oracle first:  sh %s/build_nsvg_hash.sh" % HERE)

    def dump(svg, w, h, out):
        f = tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False)
        f.write(svg)
        f.close()
        subprocess.run([HASHER, f.name, '%.3f' % w, '%.3f' % h, '-dump', out],
                       capture_output=True)
        os.unlink(f.name)

    print("\n\nQUESTION 2 -- may MAME draw the pressed wash itself?\n")
    print("  %-32s %-6s %s" % ("shape", "wash", "old two-image form vs base+wash"))
    seen = set()
    for seg, mask, ids, legend, tier in G.BUTTONS:
        key = tuple(ids)
        name = G.SHAPE_NAMES.get(ids[0], (None,))[0]
        if name is None or name in seen:
            continue
        seen.add(name)
        x, y, w, h = art.bbox_px(ids)
        x0u, y0u = x / G.geo.SCALE, y / G.geo.SCALE
        wu, hu = w / G.geo.SCALE, h / G.geo.SCALE
        base = G.shape_svg(art, ids, x0u, y0u, wu, hu, w, h, dark=False)
        dk = G.shape_svg(art, ids, x0u, y0u, wu, hu, w, h, dark=True)
        old = base[:-len('</svg>')] + dk[dk.index('</defs>') + len('</defs>'):]
        dump(base, w, h, '/tmp/_b.raw')
        dump(old, w, h, '/tmp/_o.raw')
        B = open('/tmp/_b.raw', 'rb').read()
        O = open('/tmp/_o.raw', 'rb').read()
        n = len(B) // 4
        rw = int(w) if int(w) else 1
        rh = n // rw
        kind = 'disk' if (len(ids) == 1 and
                          G.geo.shape_points(art.by_id[ids[0]])[1] == 'ellipse') else 'rect'
        N = _wash(B, n, kind, rw, rh)
        mx = nd = 0
        for i in range(n * 4):
            d = abs(N[i] - O[i])
            if d:
                nd += 1
                mx = max(mx, d)
        verdict = "SUBSTITUTED" if len(ids) == 1 else "kept as two images"
        print("  %-32s %-6s maxdelta=%3d  ndiff=%5d/%-6d  %s"
              % (name, kind, mx, nd, n * 4, verdict))
    os.unlink('/tmp/_b.raw')
    os.unlink('/tmp/_o.raw')


if __name__ == '__main__':
    art = G.Art()
    question1(art)
    question2(art)
