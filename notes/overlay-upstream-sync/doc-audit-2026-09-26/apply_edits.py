#!/usr/bin/env python3
"""Apply a reviewed list of documentation edits to the overlay, safely.

QUESTION IT ANSWERS
-------------------
"Which of these proposed corrections can be applied without damaging a file, and
which must be dropped?"  It is the gate behind the counts quoted in the
2026-09-26 documentation sweep: 63 reviewed proposals in, 56 applied by this
script, 7 dropped.

WHY IT IS NOT A LOOP OF str.replace()
-------------------------------------
The first attempt was, and it corrupted the run.  Two proposals touched the same
file; applying the first made the second's anchor ambiguous, the assertion fired
half-way through, and one file had already been written.  So:

  * every anchor is located in the ORIGINAL text of its file, before anything is
    written, and must occur EXACTLY ONCE there;
  * overlapping spans are detected and the later one dropped, never applied;
  * the splices are then made from the END of the file backwards, so earlier
    offsets stay valid and no edit can move another edit's anchor.

A proposal whose anchor does not match byte-for-byte is DROPPED and reported, not
approximated.  That is the whole point: a mangled comment is worse than an
uncorrected one, and a silent partial application is worst of all.

INPUT
-----
edits.json -- a list of objects with:
    file      path relative to the overlay root
    line      the line the proposer quoted (advisory; the anchor is what matters)
    old       exact text to replace, verbatim including leading whitespace
    new       replacement text
    why       the evidence that the current text is wrong
    severity  misleads-a-reader | minor | cosmetic

RUN
---
    python3 notes/overlay-upstream-sync/doc-audit-2026-09-26/apply_edits.py \
        [edits.json] [--dry-run]

--dry-run reports what would happen and writes nothing.  Run it first.

AFTERWARDS
----------
Rebuild and check: build.sh, then grep for the strings the edits were supposed to
remove.  `grep -c 'error:'` the build log -- build.sh exits 0 even on a compile
failure.
"""
import collections, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    src = pathlib.Path(args[0]) if args else pathlib.Path(__file__).with_name("edits.json")
    edits = json.load(open(src))

    byfile = collections.defaultdict(list)
    for e in edits:
        byfile[e["file"]].append(e)

    applied, dropped = 0, []
    for f, es in byfile.items():
        p = ROOT / f
        if not p.exists():
            dropped += [(e, "file missing") for e in es]
            continue
        orig = p.read_text()

        spans = []
        for e in es:
            n = orig.count(e["old"])
            if n != 1:
                dropped.append((e, f"anchor matches {n}x in the original, need exactly 1"))
                continue
            i = orig.index(e["old"])
            spans.append((i, i + len(e["old"]), e))

        spans.sort(key=lambda s: s[0])
        keep = []
        for s in spans:
            if keep and s[0] < keep[-1][1]:
                dropped.append((s[2], f"overlaps the edit at offset {keep[-1][0]}"))
                continue
            keep.append(s)

        text = orig
        for a, b, e in reversed(keep):          # from the end, so offsets stay valid
            text = text[:a] + e["new"] + text[b:]
            applied += 1
        if not dry:
            p.write_text(text)

    print(f"{'would apply' if dry else 'applied'} {applied}   dropped {len(dropped)}")
    for e, why in dropped:
        print(f"  DROPPED {e['file']}:{e.get('line')} -- {why}")
        print(f"          proposed because: {e.get('why','')[:110]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
