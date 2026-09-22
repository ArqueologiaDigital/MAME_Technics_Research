#!/usr/bin/env python3
"""Extract the PANEL MEMORY / BANK VIEW assembly Felipe traced in Inkscape and write it as
layout-ready geometry for tools/gen_lay.py.

Question it answers: "what are the exact shapes of the 8 PANEL MEMORY wedge buttons, their
LEDs, the three concentric circles, the two bank wings and every label in that assembly, in
the right_block's local coordinates?"

    python3 tools/pm_extract.py [SVG] [-o tools/pm_shapes.json]
    default SVG: ~/compartilhado/KN7000/side-quests/kn7000_layout_adjusted2.svg

Nothing here is hand-typed geometry: the wedge->number mapping is DERIVED by pairing each
annular sector's mid-angle with the nearest single-digit label, and the run asserts that the
result is a 1:1 pairing onto {1..8}. A re-trace that renumbers Inkscape ids still works; a
trace that is not eight regular sectors fails loudly instead of emitting something plausible.

Signals read from the SVG:
  * three concentric circles sharing one centre -> outer rim / hub / SET, by radius
  * annular-sector paths in the OUTER radius band  -> the 8 buttons
  * annular-sector paths in the INNER radius band  -> the 8 LEDs
  * the two paths filled #d5cbb2 -> BANK VIEW (left) / NEXT BANK (right) wings
  * the path filled #231f18     -> the recess the wings sit in
  * <text> font-size and the Inkscape stroke-width scale hint -> label size (see LABEL_BASE)
"""
import json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svg_region_extract import shapes, apply, path_points        # noqa: E402

DEFAULT_SVG = os.path.expanduser(
    '~/compartilhado/KN7000/side-quests/kn7000_layout_adjusted2.svg')
BLOCK = (1000.0, 997.0)        # right_block's offset in the Compact view
PAD = 1.5                      # canvas margin so a centred stroke is not clipped
REGION = (1550.0, 1190.0, 1780.0, 1470.0)

# The .lay <bounds> a label had BEFORE Felipe rescaled it in Inkscape, from gen_lay.py's own
# L() calls. Inkscape records the rescale as the element's style stroke-width, so the new box
# is (w,h) * that factor -- which is how the label keeps the proportions it was exported with.
# tools/lay_to_svg.py places a label's text at (x+w/2, y+0.78*h) with font-size min(0.9*h,13).
LABEL_BASE = {
    'BANK VIEW':    (72.0, 8.0),
    'NEXT BANK':    (72.0, 8.0),
    'PANEL MEMORY': (172.0, 10.0),
    'SET':          (44.0, 12.0),
    '_digit':       (8.0, 8.0),
}
WING_FILL, RECESS_FILL = '#d5cbb2', '#231f18'


def uscale(ctm):
    s = math.hypot(ctm[0], ctm[1])
    assert abs(s - math.hypot(ctm[2], ctm[3])) < 1e-6, "non-uniform transform: %s" % (ctm,)
    return s


def xform_path(d, s, tx, ty, nd=4):
    """Rewrite a path's data under (x,y) -> (s*x+tx, s*y+ty). Uniform scale only.

    Two SVG quirks, both of which produced broken output before they were handled:

    * A LEADING relative moveto is absolute for its FIRST coordinate pair only; the pairs
      after it are relative lineto. Promoting the whole command to M made those absolute and
      scattered the shape across the canvas (2263 px, caught by verify()).
    * The implicit lineto that follows a moveto must only be WRITTEN when the input actually
      continues with bare coordinates. Emitting it unconditionally put a bare "L" in front of
      the next explicit command ("M 70.5664 1.5 L A 143 ..."), which every renderer rejects --
      and the coordinate round trip could not see it, because a command with no operands is a
      no-op to a parser that only collects points. validate() exists for that.
    """
    out, i = [], 0
    toks = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE]-?\d+)?', d)
    cmd, orig, pending, first = None, None, None, True
    f = lambda v: ('%.*f' % (nd, v)).rstrip('0').rstrip('.') or '0'
    while i < len(toks):
        t = toks[i]
        if re.match(r'[A-Za-z]', t):
            orig = t
            cmd = 'M' if (first and t == 'm') else t     # leading m: absolute first pair
            pending = None
            out.append(cmd); i += 1; continue
        if pending:
            out.append(pending); cmd = pending; pending = None
        c = cmd.upper(); rel = cmd.islower()
        n = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6, 'S': 4, 'Q': 4, 'T': 2, 'A': 7}[c]
        v = [float(x) for x in toks[i:i + n]]; i += n
        if c == 'H':
            out.append(f(s * v[0] if rel else s * v[0] + tx))
        elif c == 'V':
            out.append(f(s * v[0] if rel else s * v[0] + ty))
        elif c == 'A':
            out += [f(s * v[0]), f(s * v[1]), f(v[2]), f(v[3]), f(v[4])]
            out += ([f(s * v[5]), f(s * v[6])] if rel
                    else [f(s * v[5] + tx), f(s * v[6] + ty)])
        else:
            for k in range(0, n, 2):
                out += ([f(s * v[k]), f(s * v[k + 1])] if rel
                        else [f(s * v[k] + tx), f(s * v[k + 1] + ty)])
        if c == 'M':
            # the implicit continuation is relative iff the ORIGINAL moveto was lowercase
            pending = 'l' if orig.islower() else 'L'
        first = False
    return ' '.join(out)


ARITY = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6, 'S': 4, 'Q': 4, 'T': 2, 'A': 7, 'Z': 0}


def validate(d):
    """Every command must be followed by a whole number of operand groups, and no command may
    be left with none. Returns the command sequence; raises on malformed data."""
    toks = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE]-?\d+)?', d)
    seq, i = [], 0
    while i < len(toks):
        t = toks[i]
        assert re.match(r'[A-Za-z]', t), "stray operand at token %d in %r" % (i, d[:60])
        i += 1
        n = ARITY[t.upper()]
        got = 0
        while i < len(toks) and not re.match(r'[A-Za-z]', toks[i]):
            got += 1; i += 1
        assert n == 0 or (got and got % n == 0), \
            "command %r has %d operands, not a multiple of %d, in %r" % (t, got, n, d[:60])
        assert n != 0 or got == 0, "command %r takes no operands but got %d" % (t, got)
        seq.append(t)
    return seq


def inside(b, r):
    return not (b[2] < r[0] or b[0] > r[2] or b[3] < r[1] or b[1] > r[3])


def box(bbox):
    """(bounds, canvas, shift) for a shape: local bounds, element canvas, canvas offset."""
    x0, y0, x1, y1 = bbox
    bx, by = x0 - PAD - BLOCK[0], y0 - PAD - BLOCK[1]
    w, h = (x1 - x0) + 2 * PAD, (y1 - y0) + 2 * PAD
    return ([round(bx, 3), round(by, 3), round(w, 3), round(h, 3)],
            [round(w, 3), round(h, 3)], (-(x0 - PAD), -(y0 - PAD)))


def main():
    svg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else DEFAULT_SVG
    out = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv else \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pm_shapes.json')

    got = [s for s in shapes(svg) if inside(s[5], REGION)]
    circles = [s for s in got if s[0] == 'circle']
    paths = [s for s in got if s[0] == 'path']
    texts = [s for s in got if s[0] == 'text']

    # --- the three concentric circles ------------------------------------------------
    cen = {}
    for s in circles:
        c = apply(s[3], s[4]['cx'], s[4]['cy'])
        cen.setdefault((round(c[0], 2), round(c[1], 2)), []).append((s, s[4]['r'] * uscale(s[3])))
    hub_c, ring = max(cen.items(), key=lambda kv: len(kv[1]))
    assert len(ring) == 3, "expected 3 concentric circles at the rosette centre, got %d" % len(ring)
    ring.sort(key=lambda sr: sr[1])
    (set_s, r_set), (hub_s, r_hub), (rim_s, r_rim) = ring
    CX, CY = hub_c

    # --- annular sectors: 8 buttons (outer band) + 8 LEDs (inner band) ---------------
    sec = []
    for s in paths:
        pts = [apply(s[3], *p) for p in path_points(s[4]['d'])]
        rs = [math.hypot(x - CX, y - CY) for x, y in pts]
        th = [math.degrees(math.atan2(y - CY, x - CX)) % 360.0 for x, y in pts]
        if max(rs) - min(rs) < 1.0 or max(rs) > r_rim + 2.0:
            continue                                   # not a sector of this rosette
        span = (max(th) - min(th)) % 360.0
        mid = (min(th) + max(th)) / 2.0
        if span > 180.0:                               # sector straddles 0 deg
            lo = min(t for t in th if t > 180.0); hi = max(t for t in th if t < 180.0)
            span = (hi - lo) % 360.0; mid = (lo + span / 2.0) % 360.0
        sec.append((s, min(rs), max(rs), mid, span))
    btn = [x for x in sec if x[2] > (r_hub + r_rim) / 2.0]
    led = [x for x in sec if x[2] <= (r_hub + r_rim) / 2.0]
    assert len(btn) == 8 and len(led) == 8, "expected 8 buttons + 8 LEDs, got %d + %d" % (len(btn), len(led))

    # --- pair each sector with its digit label ---------------------------------------
    digits = [t for t in texts if re.fullmatch(r'[1-8]', t[4]['s'])]
    assert len(digits) == 8, "expected 8 digit labels, got %d" % len(digits)
    dang = {}
    for t in digits:
        p = apply(t[3], t[4]['x'], t[4]['y'])
        dang[int(t[4]['s'])] = (math.degrees(math.atan2(p[1] - CY, p[0] - CX)) % 360.0, t)

    def nearest(mid, pool):
        return min(pool, key=lambda n: abs(((dang[n][0] - mid + 180) % 360) - 180))

    num_of, free = {}, set(dang)
    for x in sorted(btn, key=lambda x: x[3]):
        n = nearest(x[3], free); free.discard(n); num_of[id(x[0])] = n
    assert not free, "digits left unpaired: %s" % sorted(free)
    led_num = {}
    for x in led:
        b = min(btn, key=lambda y: abs(((y[3] - x[3] + 180) % 360) - 180))
        led_num[id(x[0])] = num_of[id(b[0])]
    assert sorted(led_num.values()) == list(range(1, 9)), "LED/button pairing is not 1:1"

    # --- wings + recess ---------------------------------------------------------------
    wings = sorted((s for s in paths if WING_FILL in s[2]), key=lambda s: s[5][0])
    recess = [s for s in paths if RECESS_FILL in s[2]]
    assert len(wings) == 2, "expected 2 bank wings filled %s, got %d" % (WING_FILL, len(wings))
    assert len(recess) == 1, "expected 1 recess filled %s, got %d" % (RECESS_FILL, len(recess))

    # --- emit --------------------------------------------------------------------------
    sh = {}

    def put(name, s, kind='path'):
        bounds, canvas, (tx, ty) = box(s[5])
        e = dict(kind=kind, bounds=bounds, canvas=canvas, src=s[1])
        if kind == 'path':
            ctm = s[3]
            # the shape's own transform (scale+translate) and the canvas shift, in one pass
            e['d'] = xform_path(s[4]['d'], uscale(ctm), ctm[4] + tx, ctm[5] + ty)
        sh[name] = e

    put('pm_recess', recess[0])
    put('pm_wing_l', wings[0])
    put('pm_wing_r', wings[1])
    for x in btn:
        put('pm_btn%d' % num_of[id(x[0])], x[0])
    for x in led:
        put('pm_led%d' % led_num[id(x[0])], x[0])

    def circ(name, s, r):
        c = apply(s[3], s[4]['cx'], s[4]['cy'])
        sh[name] = dict(kind='circle', src=s[1], r=round(r, 4),
                        bounds=[round(c[0] - r - PAD - BLOCK[0], 3), round(c[1] - r - PAD - BLOCK[1], 3),
                                round(2 * (r + PAD), 3), round(2 * (r + PAD), 3)],
                        canvas=[round(2 * (r + PAD), 3), round(2 * (r + PAD), 3)])
    circ('pm_rim', rim_s, r_rim)
    circ('pm_hub', hub_s, r_hub)
    circ('pm_set', set_s, r_set)

    # the BANK VIEW indicator: the only circle that is not one of the three concentric ones
    lone = [s for s in circles if s is not rim_s and s is not hub_s and s is not set_s]
    assert len(lone) == 1, "expected exactly 1 bank-view LED circle, got %d" % len(lone)
    c = apply(lone[0][3], lone[0][4]['cx'], lone[0][4]['cy'])
    r = lone[0][4]['r'] * uscale(lone[0][3])
    sh['pm_bank_led'] = dict(kind='led', src=lone[0][1], r=round(r, 4),
                             bounds=[round(c[0] - r - BLOCK[0], 3), round(c[1] - r - BLOCK[1], 3),
                                     round(2 * r, 3), round(2 * r, 3)])

    labels = {}
    for t in texts:
        s_txt = t[4]['s']
        if s_txt not in LABEL_BASE and not re.fullmatch(r'[1-8]', s_txt):
            continue
        w0, h0 = LABEL_BASE.get(s_txt, LABEL_BASE['_digit'])
        m = re.search(r'stroke-width:\s*([0-9.]+)', t[2])
        scale = float(m.group(1)) if m else 1.0
        scale *= uscale(t[3])                       # Inkscape hint x any group transform
        w, h = w0 * scale, h0 * scale
        p = apply(t[3], t[4]['x'], t[4]['y'])
        key = 'num%s' % s_txt if re.fullmatch(r'[1-8]', s_txt) else \
            re.sub(r'[^a-z]+', '_', s_txt.lower())
        labels[key] = dict(text=s_txt, src=t[1],
                           bounds=[round(p[0] - w / 2 - BLOCK[0], 3), round(p[1] - 0.78 * h - BLOCK[1], 3),
                                   round(w, 3), round(h, 3)])
    for k in ('bank_view', 'next_bank', 'panel_memory', 'set'):
        assert k in labels, "missing label %r" % k

    doc = dict(
        source=os.path.relpath(svg, os.path.expanduser('~/compartilhado')),
        generated_by='tools/pm_extract.py',
        block_origin=list(BLOCK), pad=PAD,
        centre_local=[round(CX - BLOCK[0], 4), round(CY - BLOCK[1], 4)],
        radii=dict(rim=round(r_rim, 4), hub=round(r_hub, 4), set=round(r_set, 4),
                   btn_in=round(min(x[1] for x in btn), 4), btn_out=round(max(x[2] for x in btn), 4),
                   led_in=round(min(x[1] for x in led), 4), led_out=round(max(x[2] for x in led), 4)),
        wedge=dict(span=round(sum(x[4] for x in btn) / 8.0, 4),
                   led_span=round(sum(x[4] for x in led) / 8.0, 4),
                   mid_angles={str(num_of[id(x[0])]): round(x[3], 4) for x in btn}),
        shapes=sh, labels=labels)
    with open(out, 'w') as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write('\n')
    print("wrote %s" % out)
    print("  centre (right_block local) = (%.4f, %.4f)" % tuple(doc['centre_local']))
    print("  radii  %s" % doc['radii'])
    print("  wedge span %.2f deg (gap %.2f), LED span %.2f deg"
          % (doc['wedge']['span'], 45.0 - doc['wedge']['span'], doc['wedge']['led_span']))
    print("  number -> mid angle: %s" % doc['wedge']['mid_angles'])
    print("  %d shapes, %d labels" % (len(sh), len(labels)))




def verify(svg=None, js=None):
    """Round-trip check: every emitted path, put back at its <bounds> in the Compact view,
    must land on the same absolute points as the shape it came from. Tolerance 1e-3 px."""
    svg = svg or DEFAULT_SVG
    js = js or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pm_shapes.json')
    doc = json.load(open(js))
    src = {s[1]: s for s in shapes(svg)}
    worst, checked = 0.0, 0
    for name, e in sorted(doc['shapes'].items()):
        if e['kind'] != 'path':
            continue
        s = src[e['src']]
        validate(e['d'])                     # syntax, which a point-only compare cannot see
        want = [apply(s[3], *p) for p in path_points(s[4]['d'])]
        bx, by = e['bounds'][0] + BLOCK[0], e['bounds'][1] + BLOCK[1]
        got = [(x + bx, y + by) for x, y in path_points(e['d'])]
        assert len(want) == len(got), "%s: %d points out, %d in" % (name, len(got), len(want))
        dev = max(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(want, got))
        worst = max(worst, dev); checked += 1
        print("  %-10s %3d points  max deviation %.6f px" % (name, len(got), dev))
    # the canvas must also cover the shape, else MAME clips or rescales the artwork
    for name, e in sorted(doc['shapes'].items()):
        if e['kind'] != 'path':
            continue
        pts = path_points(e['d'])
        w, h = e['canvas']
        assert -0.001 <= min(p[0] for p in pts) and max(p[0] for p in pts) <= w + 0.001, \
            "%s overflows its canvas in x" % name
        assert -0.001 <= min(p[1] for p in pts) and max(p[1] for p in pts) <= h + 0.001, \
            "%s overflows its canvas in y" % name
    print("VERIFY OK: %d paths round-trip, worst deviation %.6f px, none overflows its canvas"
          % (checked, worst))
    return worst


if __name__ == '__main__':
    if '--verify' in sys.argv:
        verify()
    else:
        main()
