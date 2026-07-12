#!/usr/bin/env python3
"""Apply an adjusted layout SVG (Felipe's Inkscape edit) back onto the generated kn7000.lay.

Pipeline:  gen_lay.py  ->  base kn7000.lay  ->  apply_svg.py adjusted.svg  ->  patched kn7000.lay

Both the adjusted SVG and the .lay render nearly the same panel, so each .lay placement is matched to the
NEAREST element in the SVG (labels by exact string; shapes by nearest centre within a small radius) -- for
the small cosmetic edits Felipe makes, that match is unambiguous. The placement's <bounds> is then rewritten
to the SVG element's position, keeping every binding/id/animate intact. Run with --dry to only report.

    python3 tools/apply_svg.py ../KN7000/side-quests/kn7000_layout_adjusted.svg [--dry] [--view Compact]
"""
import sys, os, re, math
sys.path.insert(0, os.path.dirname(__file__))
from lay_to_svg import parse_elements, parse_groups, parse_view, LAY
import xml.etree.ElementTree as ET
NS = '{http://www.w3.org/2000/svg}'

RADIUS = 34.0        # max centre distance (px) for a confident shape match
LABEL_RADIUS = 55.0  # max centre distance for a confident label match (filters duplicate/deleted mismatches)
SKIP_REFS = {'slider_knob'}   # animated -> its SVG position depends on the rendered state; never match by it

def _tf(el):
    t = el.get('transform', '') or ''
    dx = dy = 0.0
    m = re.search(r'translate\(\s*([-\d.]+)[ ,]+([-\d.]+)', t)
    if m: dx, dy = float(m.group(1)), float(m.group(2))
    mm = re.search(r'matrix\(([-\d.e ,]+)\)', t)
    if mm:
        p = [float(x) for x in re.split(r'[ ,]+', mm.group(1).strip()) if x]
        if len(p) == 6: dx, dy = p[4], p[5]
    return dx, dy

def parse_svg(path):
    """Return (texts, shapes): texts=[(string, cx, cy_baseline)], shapes=[(cx, cy)]."""
    root = ET.parse(path).getroot()
    texts, shapes = [], []
    for el in root.iter():
        tag = el.tag.replace(NS, '')
        dx, dy = _tf(el)
        try:
            if tag == 'text':
                s = ''.join(el.itertext()).strip()
                if s: texts.append((s, float(el.get('x', 0)) + dx, float(el.get('y', 0)) + dy))
            elif tag == 'circle':
                shapes.append((float(el.get('cx', 0)) + dx, float(el.get('cy', 0)) + dy))
            elif tag == 'rect':
                w = float(el.get('width', 0)); h = float(el.get('height', 0))
                shapes.append((float(el.get('x', 0)) + dx + w/2, float(el.get('y', 0)) + dy + h/2))
        except (TypeError, ValueError):
            continue
    return texts, shapes

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    # SAFE BY DEFAULT: only reports. Pass --apply to actually patch the .lay. The fuzzy (string/nearest)
    # matching is NOT reliable for an ID-less, editor-flattened SVG -- dense button grids risk matching a
    # neighbour, and 250+ shapes typically fail to match at all, so an --apply run on such an SVG would
    # misalign labels from their shapes. The RELIABLE path is an ID-tagged SVG (lay_to_svg stamps each
    # element with group.index.ref, which Inkscape preserves): then matches are exact. Until then, use --dry.
    dry = '--apply' not in sys.argv
    view = 'Compact'
    if '--view' in sys.argv: view = sys.argv[sys.argv.index('--view') + 1]
    if not args: sys.exit("usage: apply_svg.py adjusted.svg [--dry]")
    svg = args[0]
    text = open(LAY).read()
    els = parse_elements(text)
    groups = parse_groups(text)
    placements = parse_view(text, view)
    offset = {g: (ox, oy) for g, ox, oy, w, h in placements}
    stexts, sshapes = parse_svg(svg)

    # index SVG texts by string for exact-match lookup
    by_str = {}
    for s, x, y in stexts: by_str.setdefault(s, []).append((x, y))

    changes = {}   # (group, index) -> (new_x, new_y)  in group-local coords
    stats = {'text_moved': 0, 'text_nomatch': 0, 'shape_moved': 0, 'shape_nomatch': 0, 'unchanged': 0}
    report = []
    for gref, ox, oy, gw, gh in placements:
        for gi, (ref, x, y, w, h, is_screen) in enumerate(groups.get(gref, [])):
            if is_screen or ref in SKIP_REFS: continue
            e = els.get(ref)
            if e and e[0] == 'text':
                # base label centre in SVG coords (matches lay_to_svg: x+w/2, y+h*0.78)
                bx, by = x + ox + w/2, y + oy + h*0.78
                cand = by_str.get(e[1], [])
                if not cand: stats['text_nomatch'] += 1; continue
                fx, fy = min(cand, key=lambda p: (p[0]-bx)**2 + (p[1]-by)**2)
                if math.hypot(fx-bx, fy-by) > LABEL_RADIUS: stats['text_nomatch'] += 1; continue
                nx, ny = fx - ox - w/2, fy - oy - h*0.78
                d = math.hypot(nx - x, ny - y)
                if d > 1.5:
                    changes[(gref, gi)] = (round(nx, 1), round(ny, 1)); stats['text_moved'] += 1
                    report.append(f"  txt {e[1]!r:28.28} ({x:.0f},{y:.0f})->({nx:.0f},{ny:.0f}) d={d:.0f}")
                else: stats['unchanged'] += 1
            else:
                # shape: base centre in SVG coords, match nearest SVG shape centre
                bx, by = x + ox + w/2, y + oy + h/2
                if not sshapes: continue
                fx, fy = min(sshapes, key=lambda p: (p[0]-bx)**2 + (p[1]-by)**2)
                if math.hypot(fx-bx, fy-by) > RADIUS: stats['shape_nomatch'] += 1; continue
                nx, ny = fx - ox - w/2, fy - oy - h/2
                d = math.hypot(nx - x, ny - y)
                if d > 1.5:
                    changes[(gref, gi)] = (round(nx, 1), round(ny, 1)); stats['shape_moved'] += 1
                    report.append(f"  shp {ref:16.16} ({x:.0f},{y:.0f})->({nx:.0f},{ny:.0f}) d={d:.0f}")
                else: stats['unchanged'] += 1

    print(f"=== apply_svg {os.path.basename(svg)}: {stats} ===")
    for r in report[:200]: print(r)
    if dry:
        print(f"(dry run -- {len(changes)} placements would move)")
        return

    # patch the .lay: re-walk each group's <element|screen> matches (same order as parse_groups) and
    # rewrite the first <bounds> of changed placements.
    def patch_group(m):
        gref = m.group(1); body = m.group(2)
        idx = [-1]
        def repl(em):
            idx[0] += 1
            ch = changes.get((gref, idx[0]))
            if ch is None: return em.group(0)
            nx, ny = ch
            return re.sub(r'(<bounds\b[^>]*?\bx=")[-\d.]+("[^>]*?\by=")[-\d.]+',
                          lambda b: f'{b.group(1)}{nx}{b.group(2)}{ny}', em.group(0), count=1)
        newbody = re.sub(r'<(element|screen)\b[^>]*>.*?</\1>', repl, body, flags=re.S)
        return f'<group name="{gref}">{newbody}</group>'
    patched = re.sub(r'<group name="([^"]+)">(.*?)</group>', patch_group, text, flags=re.S)
    open(LAY, 'w').write(patched)
    print(f"patched {LAY}: {len(changes)} placements moved")

if __name__ == '__main__':
    main()
