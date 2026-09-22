#!/usr/bin/env python3
"""Re-key layout_nudges.json after a structural edit to a layout group.

gen_lay.py applies Felipe's nudges ALL-OR-NOTHING: apply_nudges.py ref-verifies every
"group.index.ref" key against the element at that index, and one mismatch drops all of them.
Adding or removing placements shifts those indices, so every edit to a group has to be
followed by a re-key or the whole panel silently loses its finetuning.

    GEN_LAY_NO_NUDGE=1 python3 tools/gen_lay.py   # before the edit -> copy the .lay aside
    ...make the edit...
    GEN_LAY_NO_NUDGE=1 python3 tools/gen_lay.py   # after  the edit -> copy the .lay aside
    python3 tools/migrate_nudges.py OLD.lay NEW.lay [--write]

A placement is matched across the two files by (group, ref, bounds) -- its pre-nudge bounds,
which is what the un-nudged base gives. Duplicates match in order of appearance. A nudge whose
placement no longer exists is REPORTED AND DROPPED: that is the correct outcome when the
shape it adjusted was replaced, and it is printed so it is never a silent loss.
"""
import json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
NUDGES = os.path.join(HERE, 'layout_nudges.json')


def placements(lay):
    """group -> [(index, ref, bounds-key)] using apply_nudges.py's OWN indexing.

    That indexing is the nth <element>|<screen> per <group>, and the "ref" it verifies is the
    element's ref= or, failing that, its id=. Reimplementing it by eye is how this tool first
    reported 145 bogus drops: a regex that expected ref= immediately after <element misses
    `<element name="cpl_led20" ref="green_led">` and every index after it slides.
    """
    out = {}
    for mg in re.finditer(r'<group name="([^"]+)">(.*?)</group>', lay, re.S):
        g, body = mg.group(1), mg.group(2)
        rows = []
        for i, em in enumerate(re.finditer(r'<(element|screen)\b[^>]*>.*?</\1>', body, re.S)):
            tagtext = em.group(0)
            mref = re.search(r'\bref="([^"]+)"', tagtext)
            if mref:
                ref = mref.group(1)
            else:
                mid = re.search(r'\bid="([^"]+)"', tagtext)
                ref = mid.group(1) if mid else '?'
            b = re.search(r'<bounds\b[^>]*?x="([-\d.]+)"[^>]*?y="([-\d.]+)"'
                          r'[^>]*?width="([-\d.]+)"[^>]*?height="([-\d.]+)"', tagtext)
            rows.append((i, ref, b.groups() if b else None))
        out[g] = rows
    return out


def main():
    old, new = sys.argv[1], sys.argv[2]
    write = '--write' in sys.argv
    O, N = placements(open(old).read()), placements(open(new).read())
    nud = json.load(open(NUDGES))

    # (group, ref, bounds) -> queue of new indices
    pool = defaultdict(list)
    for g, rows in N.items():
        for i, ref, b in rows:
            pool[(g, ref, b)].append(i)

    out, dropped, moved, kept = {}, [], 0, 0
    for key, delta in nud.items():
        g, idx, ref = key.split('.', 2)
        idx = int(idx)
        row = next((r for r in O.get(g, []) if r[0] == idx), None)
        if row is None or row[1] != ref:
            dropped.append((key, 'not in %s' % os.path.basename(old)))
            continue
        cand = pool.get((g, row[1], row[2]))
        if not cand:
            dropped.append((key, 'placement gone'))
            continue
        ni = cand.pop(0)
        out['%s.%d.%s' % (g, ni, ref)] = delta
        kept += 1
        moved += (ni != idx)

    print("%s -> %s" % (os.path.basename(old), os.path.basename(new)))
    for g in sorted(set(O) | set(N)):
        print("  %-14s %3d -> %3d placements" % (g, len(O.get(g, [])), len(N.get(g, []))))
    print("  nudges: %d in, %d kept (%d re-indexed), %d dropped" % (len(nud), kept, moved, len(dropped)))
    for k, why in sorted(dropped):
        print("    DROP %-42s %s" % (k, why))
    if write:
        with open(NUDGES, 'w') as fh:
            json.dump(out, fh, indent=1)
            fh.write('\n')
        print("  wrote %s" % NUDGES)
    else:
        print("  (dry run -- pass --write to update layout_nudges.json)")


if __name__ == '__main__':
    main()
