#!/usr/bin/env python3
"""A/B two versions of a MAME layout, placement by placement.

QUESTION IT ANSWERS
    A refactor of src/mame/layout/wsa1r.lay claims not to change what is drawn.
    This checks that claim WITHOUT building MAME: it matches the two files'
    placements by their <bounds>, renders whichever <element> each one refers to
    at exactly those bounds through MAME's own nanosvg (nsvg_hash), and reports
    where the pixels disagree and by how much.

    It is the fast gate.  It is NOT the whole story: it compares one element
    against another and is blind to COMPOSITION -- which shape ends up painted
    over which.  For that, wsa1r_panel_ab.sh renders the whole panel.

RUN
    sh notes/wsa1-probes/build_nsvg_hash.sh                  # once
    git show c51e4e8:src/mame/layout/wsa1r.lay > /tmp/before.lay
    python3 notes/wsa1-probes/wsa1r_lay_ab.py /tmp/before.lay src/mame/layout/wsa1r.lay

READING IT
    "bounds sets IDENTICAL" is the first thing to check: if a placement moved or
    vanished, nothing below it means anything.  Then every render should be
    byte-identical, and any that is not is printed with its magnitude, so a step
    that was meant to be free can be told apart from one that was not.

    Two results look alarming and are not:

    * "only in B" for a bound that did not exist before is a mark LIFTED out of
      the backdrop into its own element -- a new placement, by design.
    * a big `vector_art -> vector_art` difference is the OTHER half of the same
      change: the backdrop no longer carries the mark that was lifted, so it
      really does render differently on its own.  Only the composed panel says
      whether the two halves add back up, which is wsa1r_panel_ab.sh's job.
"""
import collections
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HASHER = os.path.join(HERE, "nsvg_hash")

ELEM = re.compile(r'<element name="([^"]+)"[^>]*>(.*?)</element>', re.S)
IMG = re.compile(r'<image(?: state="(\d+)")?><data><!\[CDATA\[(.*?)\]\]></data></image>', re.S)
PLACE = re.compile(r'<element (?:name="[^"]*" )?(?:id="[^"]*" )?ref="([^"]+)"[^>]*?>'
                   r'.*?<bounds x="([-\d.]+)" y="([-\d.]+)" '
                   r'width="([\d.]+)" height="([\d.]+)"/>', re.S)


def load(path):
    src = open(path, encoding='utf-8').read()
    elements = {}
    for m in ELEM.finditer(src):
        imgs = {}
        for im in IMG.finditer(m.group(2)):
            imgs[int(im.group(1)) if im.group(1) else 0] = im.group(2)
        if imgs:
            elements[m.group(1)] = imgs
    places = {}
    for m in PLACE.finditer(src):
        key = tuple(round(float(v), 3) for v in m.groups()[1:])
        places.setdefault(key, m.group(1))
    return elements, places


def svg_hash_cmp(a, b, w, h):
    fa = tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False)
    fa.write(a)
    fa.close()
    fb = tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False)
    fb.write(b)
    fb.close()
    try:
        r = subprocess.run([HASHER, '-cmp', fa.name, fb.name, '%.3f' % w, '%.3f' % h],
                           capture_output=True, text=True)
        m = re.search(r'ndiff=(\d+) of (\d+) maxdelta=(\d+) meandelta=([\d.]+)', r.stdout)
        if not m:
            return None, (r.stdout + r.stderr).strip()
        return (int(m.group(3)), float(m.group(4)), int(m.group(1)), int(m.group(2))), m.group(0)
    finally:
        os.unlink(fa.name)
        os.unlink(fb.name)


def main(a_path, b_path):
    if not os.path.exists(HASHER):
        sys.exit("build the oracle first:  sh %s/build_nsvg_hash.sh" % HERE)
    ea, pa = load(a_path)
    eb, pb = load(b_path)
    same_bounds = set(pa) == set(pb)
    print("A %s\nB %s" % (a_path, b_path))
    print("placements: A=%d B=%d -- bounds sets %s"
          % (len(pa), len(pb), "IDENTICAL" if same_bounds else "DIFFER"))
    for k in sorted(set(pa) ^ set(pb)):
        print("   only in %s: bounds %s" % ("A" if k in pa else "B", k))

    rows, n, exact = [], 0, 0
    for k in sorted(set(pa) & set(pb)):
        ra, rb = pa[k], pb[k]
        if ra not in ea or rb not in eb:
            continue                       # <text>/<disk>: no raster to compare
        x, y, w, h = k
        for st in sorted(set(ea[ra]) & set(eb[rb])):
            n += 1
            v, msg = svg_hash_cmp(ea[ra][st], eb[rb][st], w, h)
            if v is None:
                rows.append((1 << 30, 0.0, ra, rb, st, msg))
                continue
            if v[0] == 0:
                exact += 1
            rows.append((v[0], v[1], ra, rb, st, msg))
    rows.sort(reverse=True)
    print("\n%d renders compared, %d byte-identical" % (n, exact))
    if exact < n:
        print("the %d that differ, worst first:" % (n - exact))
        for md, mean, ra, rb, st, msg in rows[:12]:
            if md == 0:
                break
            print("   %-24s -> %-26s state%d  %s" % (ra, rb, st, msg))
    print("\nrenders whose MEAN deviation exceeds 0.5/255: %d"
          % sum(1 for r in rows if r[1] > 0.5))
    return 0 if same_bounds else 1


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
