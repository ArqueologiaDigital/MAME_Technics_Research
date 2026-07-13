#!/usr/bin/env python3
"""Apply per-element layout nudges (deltas) to kn7000.lay, keyed by the stable id "group.index.ref".

The nudges come from a semantic diff of Felipe's Inkscape-adjusted layout SVG vs the clean export
(tools/svg_semantic_diff -> layout_nudges.json). Each nudge shifts an element's first <bounds> x/y by
(dx,dy) in Compact-view/layout pixels (the SVG export is 1:1 with the layout). The (group,index) indexing
matches tools/lay_to_svg.py exactly (nth <element>/<screen> per <group>), and every nudge is REF-VERIFIED
against the .lay element at that index before it is applied -- a mismatch is reported and skipped, never
mis-applied. Run AFTER gen_lay.py (which regenerates the base .lay), so the nudges survive regeneration.

Usage: apply_nudges.py [nudges.json] [lay_path]   (defaults: tools/layout_nudges.json, the repo .lay)
"""
import re, json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LAY = os.path.join(HERE, '..', 'src', 'mame', 'layout', 'kn7000.lay')
DEFAULT_NUDGES = os.path.join(HERE, 'layout_nudges.json')

def load_nudges(path):
    raw = json.load(open(path))
    by_gi = {}
    for k, (dx, dy) in raw.items():
        m = re.match(r'^([A-Za-z_]+)\.(\d+)\.(.+)$', k)
        if m:
            by_gi[(m.group(1), int(m.group(2)))] = (m.group(3), float(dx), float(dy))
    return by_gi

def patch(text, by_gi):
    stats = {'applied': 0, 'refmismatch': 0, 'nobounds': 0}
    mism = []
    def patch_group(mg):
        gref = mg.group(1); body = mg.group(2)
        idx = [-1]
        def repl(em):
            idx[0] += 1
            key = (gref, idx[0])
            if key not in by_gi:
                return em.group(0)
            ref_exp, dx, dy = by_gi[key]
            mref = re.search(r'\bref="([^"]+)"', em.group(0))
            actual = mref.group(1) if mref else (re.search(r'\bid="([^"]+)"', em.group(0)) or [None, '?'])[1]
            if actual != ref_exp:
                stats['refmismatch'] += 1; mism.append((gref, idx[0], ref_exp, actual)); return em.group(0)
            def badd(b):
                nx = round(float(b.group(2)) + dx, 1); ny = round(float(b.group(4)) + dy, 1)
                return f'{b.group(1)}{nx}{b.group(3)}{ny}'
            new, n = re.subn(r'(<bounds\b[^>]*?\bx=")([-\d.]+)("[^>]*?\by=")([-\d.]+)', badd, em.group(0), count=1)
            if n == 0:
                stats['nobounds'] += 1; return em.group(0)
            stats['applied'] += 1; return new
        newbody = re.sub(r'<(element|screen)\b[^>]*>.*?</\1>', repl, body, flags=re.S)
        return f'<group name="{gref}">{newbody}</group>'
    patched = re.sub(r'<group name="([^"]+)">(.*?)</group>', patch_group, text, flags=re.S)
    return patched, stats, mism

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    nudges_path = args[0] if len(args) > 0 else DEFAULT_NUDGES
    lay_path = args[1] if len(args) > 1 else DEFAULT_LAY
    write = '--apply' in sys.argv
    by_gi = load_nudges(nudges_path)
    text = open(lay_path).read()
    patched, stats, mism = patch(text, by_gi)
    print(f"nudges: {len(by_gi)} | applied {stats['applied']}, ref-mismatch {stats['refmismatch']}, no-bounds {stats['nobounds']}")
    for g, i, exp, act in mism[:30]:
        print(f"  REF MISMATCH {g}.{i}: expected ref '{exp}' but .lay has '{act}'  (SKIPPED)")
    if write and stats['refmismatch'] == 0:
        open(lay_path, 'w').write(patched)
        print(f"WROTE nudged {lay_path}")
    elif write:
        print("NOT written: ref mismatches present (index misalignment) -- fix before applying")
    else:
        print("(dry run; pass --apply to write)")

if __name__ == '__main__':
    main()
