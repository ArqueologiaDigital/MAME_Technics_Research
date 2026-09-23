#!/usr/bin/env python3
"""Where does a file's comment density come from -- essays, or uniform annotation?

QUESTION IT ANSWERS
    A density figure says a file is heavily commented. It does not say what to do
    about it. mn10300.h was at the 95th percentile because it carried multi-page
    peripheral documentation, so the fix was to RELOCATE those blocks beside the
    handlers they describe. Before proposing the same for another file, measure
    whether it has blocks to relocate.

    This reports the run-length distribution of comment-only lines: how many
    comment lines live in runs of 1, 2, 3 ... consecutive lines.

MEASURED 2026-09-23, src/mame/matsushita/kn7000.cpp (1953 lines):
    423 comment-only lines in 177 runs
      runs of 1-3 lines   159 runs = 326 lines = 77% of all comment lines
      runs of 4-7 lines    17 runs =  83 lines
      runs of 8+           1 run   =  14 lines
    plus 161 trailing comments on code lines.

    So there is nothing to relocate. The density is one to three lines of
    explanation next to the code they explain, throughout -- which is what
    annotating an instrument with no datasheet looks like. Moving it from the
    94th percentile to the median would mean deleting roughly 230 short
    comments, which is the blanket trim that previously removed already-merged
    upstream documentation and left 48 sentences cut off mid-clause.

USAGE
    python3 comment_run_profile.py FILE...

    Pair it with cdens.py, which gives the density, and with the null:
      git archive upstream/master src/mame | tar -x -C <scratch>
      # then cdens.py over <scratch>/src/mame/*/*.cpp of >=1000 lines
"""
import sys
from collections import Counter


def profile(path):
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    runs, cur = [], 0
    for l in lines:
        if l.strip().startswith('//'):
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    trailing = sum(1 for l in lines if '//' in l and not l.strip().startswith('//'))
    c = Counter(runs)
    total = sum(runs)
    print('%s: %d lines, %d comment-only in %d runs, %d trailing'
          % (path, len(lines), total, len(runs), trailing))
    if not total:
        return
    for k in sorted(c):
        print('   run of %2d line(s): %3d runs = %4d lines (%4.1f%%)'
              % (k, c[k], k * c[k], 100.0 * k * c[k] / total))
    short = sum(k * c[k] for k in c if k <= 3)
    print('   runs of 1-3 lines account for %.0f%% of the comment lines'
          % (100.0 * short / total))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: %s FILE...' % sys.argv[0])
    for p in sys.argv[1:]:
        profile(p)
