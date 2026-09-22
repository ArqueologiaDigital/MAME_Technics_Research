#!/usr/bin/env python3
"""Check the generated kn7000.lay's PANEL MEMORY assembly against the trace it came from,
and measure what MAME's rectangular hit test does to the eight wedge buttons.

    python3 tools/pm_lay_check.py [kn7000.lay]

Part 1 -- FIDELITY. Every pm_* placement's <bounds> and every pm_* element's path/circle must
equal tools/pm_shapes.json, and putting each path back at its bounds must land on the same
absolute Compact-view points as Felipe's trace. This closes the loop
trace SVG -> pm_shapes.json -> kn7000.lay -> absolute coordinates.

Part 2 -- HIT TEST. MAME hit-tests a view item by its <bounds> RECTANGLE, never by the
artwork's shape (src/emu/render.cpp, the m_clickable_items loop), and
layout_view::recompute() reverses m_interactive_items, so the item declared LAST is tested
FIRST and -- clickthrough being implied false by an inputtag -- claims the pointer. Eight
annular sectors have overlapping rects, so a click on one wedge can be taken by another.
This reports, per wedge, how much of its own painted area a later-declared wedge steals, and
compares the result against the round buttons this assembly replaced.
"""
import json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAY = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'src', 'mame', 'layout', 'kn7000.lay')
SHAPES = os.path.join(HERE, 'pm_shapes.json')
BLOCK = (1000.0, 997.0)
STEP = 0.25                       # sampling pitch, layout pixels
OLD_BTN_AREA = math.pi * (37.0 / 2.0) ** 2    # round_btn_silver, grown 32->37 by gen_lay.P()

sys.path.insert(0, HERE)
from svg_region_extract import path_points        # noqa: E402


def lay_items(text):
    """(group, index, ref, bounds, inputtag) for every placement, apply_nudges.py's indexing."""
    out = []
    for mg in re.finditer(r'<group name="([^"]+)">(.*?)</group>', text, re.S):
        g, body = mg.group(1), mg.group(2)
        for i, em in enumerate(re.finditer(r'<(element|screen)\b[^>]*>.*?</\1>', body, re.S)):
            t = em.group(0)
            mr = re.search(r'\bref="([^"]+)"', t)
            mb = re.search(r'<bounds\b[^>]*?x="([-\d.]+)"[^>]*?y="([-\d.]+)"'
                           r'[^>]*?width="([-\d.]+)"[^>]*?height="([-\d.]+)"', t)
            mt = re.search(r'\binputtag="([^"]+)"', t)
            out.append((g, i, mr.group(1) if mr else None,
                        tuple(float(v) for v in mb.groups()) if mb else None,
                        mt.group(1) if mt else None))
    return out


def lay_elements(text):
    """element name -> its state-0 SVG body (or the single-state body)."""
    out = {}
    for m in re.finditer(r'<element name="([^"]+)">(.*?)</element>', text, re.S):
        body = m.group(2)
        d = re.search(r'<image state="0"><data><!\[CDATA\[(.*?)\]\]></data></image>', body, re.S) \
            or re.search(r'<image><data><!\[CDATA\[(.*?)\]\]></data></image>', body, re.S)
        if d:
            out[m.group(1)] = d.group(1)
    return out


def fidelity(text, js):
    items = {(r, b) for g, i, r, b, t in lay_items(text) if r and r.startswith('pm_')}
    byref = {}
    for g, i, r, b, t in lay_items(text):
        if r and (r.startswith('pm_') or r == 'green_led'):
            byref.setdefault(r, []).append((b, t))
    els = lay_elements(text)
    bad, worst = [], 0.0
    for name, e in sorted(js['shapes'].items()):
        if name == 'pm_bank_led':
            want = tuple(e['bounds'])
            if not any(b == want for b, t in byref.get('green_led', [])):
                bad.append("%s: no green_led placed at %s" % (name, want))
            continue
        got = byref.get(name)
        if not got:
            bad.append("%s: not placed in the .lay" % name); continue
        if len(got) != 1:
            bad.append("%s: placed %d times" % (name, len(got))); continue
        if [round(v, 3) for v in got[0][0]] != [round(v, 3) for v in e['bounds']]:
            bad.append("%s: bounds %s != %s" % (name, got[0][0], e['bounds'])); continue
        body = els.get(name)
        if body is None:
            bad.append("%s: no element definition" % name); continue
        if e['kind'] == 'path':
            md = re.search(r'\bd="([^"]+)"', body)
            if not md or md.group(1) != e['d']:
                bad.append("%s: path data differs from pm_shapes.json" % name); continue
            bx, by = e['bounds'][0] + BLOCK[0], e['bounds'][1] + BLOCK[1]
            pts = [(x + bx, y + by) for x, y in path_points(e['d'])]
            src = [(x + bx, y + by) for x, y in path_points(md.group(1))]
            worst = max([worst] + [math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(pts, src)])
        else:
            # the CIRCLE's own r -- a bare r=" also matches the radialGradient that shades it
            mr = re.search(r'<circle\b[^>]*?\br="([\d.]+)"', body)
            if not mr or abs(float(mr.group(1)) - e['r']) > 1e-6:
                bad.append("%s: radius differs from pm_shapes.json" % name)
    labels = {}
    for g, i, r, b, t in lay_items(text):
        if b:
            labels.setdefault(tuple(round(v, 3) for v in b), []).append(r)
    for key, lb in sorted(js['labels'].items()):
        want = tuple(round(v, 3) for v in lb['bounds'])
        if want not in labels:
            bad.append("label %s (%r): nothing placed at %s" % (key, lb['text'], list(want)))
    # Felipe 2026-09-22: the SET cap and the START/STOP button are the same colour on the real
    # instrument. gen_lay.py paints both from one constant; this proves they did not drift.
    def fills(name):
        m = re.search(r'<element name="%s">(.*?)</element>' % name, text, re.S)
        return re.findall(r'fill="([^"]*)"', m.group(1)) if m else None
    if fills('pm_set') != fills('pill_greycyan'):
        bad.append("pm_set %s != pill_greycyan %s -- SET and START/STOP must match"
                   % (fills('pm_set'), fills('pill_greycyan')))
    for w in ('pm_wing_l', 'pm_wing_r'):
        if any(f.startswith('url(') for f in fills(w) or []):
            bad.append("%s is gradient-filled; Felipe asked for solid grey" % w)

    print("PART 1 -- FIDELITY")
    for msg in bad:
        print("  FAIL %s" % msg)
    if not bad:
        print("  OK: %d shapes and %d labels in the .lay match pm_shapes.json exactly"
              % (len(js['shapes']), len(js['labels'])))
        print("      SET and START/STOP share one colour (%s); both wings are solid"
              % ','.join(fills('pm_set')))
        print("      path round trip to absolute coordinates: worst deviation %.6f px" % worst)
    return not bad


def hit(text, js):
    """Sample each wedge's painted area; count what a LATER-declared wedge's rect takes."""
    order, rect = [], {}
    for g, i, r, b, t in lay_items(text):
        if r and re.fullmatch(r'pm_btn[1-8]', r):
            order.append(r); rect[r] = b
    assert len(order) == 8, "expected 8 wedge placements, found %d" % len(order)
    c = js['centre_local']; CX, CY = c[0] + BLOCK[0], c[1] + BLOCK[1]
    rr = js['radii']
    r_in, r_out = rr['btn_in'], rr['btn_out']
    mids = {int(k): v for k, v in js['wedge']['mid_angles'].items()}
    half = js['wedge']['span'] / 2.0

    print("\nPART 2 -- HIT TEST (declaration order: %s)" % " ".join(order))
    print("  wedge  own area  stolen  %stolen  aim zone   vs the 37px round button it replaced")
    tot_own = tot_stolen = 0.0
    for pos, name in enumerate(order):
        n = int(name[-1]); mid = mids[n]
        later = [rect[m] for m in order[pos + 1:]]
        own = stolen = aim = 0
        x0, y0, w, h = rect[name]
        x0 += BLOCK[0]; y0 += BLOCK[1]
        y = y0
        while y <= y0 + h:
            x = x0
            while x <= x0 + w:
                dx, dy = x - CX, y - CY
                r = math.hypot(dx, dy)
                if r_in <= r <= r_out:
                    th = math.degrees(math.atan2(dy, dx)) % 360.0
                    if abs(((th - mid + 180) % 360) - 180) <= half:
                        own += 1
                        for bx, by, bw, bh in later:
                            bx += BLOCK[0]; by += BLOCK[1]
                            if bx <= x <= bx + bw and by <= y <= by + bh:
                                stolen += 1
                                if abs(((th - mid + 180) % 360) - 180) <= 12 and \
                                        r_in + 6 <= r <= r_out - 4:
                                    aim += 1
                                break
                x += STEP
            y += STEP
        a = STEP * STEP
        tot_own += own * a; tot_stolen += stolen * a
        print("  %-7s %7.1f  %6.1f   %5.1f%%  %s  %4.2fx the old area"
              % (n, own * a, stolen * a, 100.0 * stolen / own if own else 0.0,
                 "clean    " if aim == 0 else "%5.1f px2" % (aim * a),
                 (own - stolen) * a / OLD_BTN_AREA))
    print("  TOTAL: %.0f px2 of wedge, %.0f px2 (%.1f%%) reachable only by a later sibling;"
          % (tot_own, tot_stolen, 100.0 * tot_stolen / tot_own))
    print("         unambiguous area per button %.0f px2 vs %.0f px2 for the old round buttons."
          % ((tot_own - tot_stolen) / 8.0, OLD_BTN_AREA))


def main():
    text = open(LAY).read()
    js = json.load(open(SHAPES))
    ok = fidelity(text, js)
    hit(text, js)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
