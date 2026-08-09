#!/usr/bin/env python3
"""agree.py -- merge two or more independent sweeps, keeping only what they agree on.

This is the verification step for the case the whole exercise exists for: a ROM with NO
oracle (Felipe's PROGRAM 893).  There is no checksum anywhere in the loop -- the service
ROM test reports PASS/FAIL, not a value -- so the only available proof that a byte was
read correctly is that a second, independent pass over the same address read the same
thing.

Why this works on the failure mode that actually occurs: the errors this tool makes are
CONFIDENT, and they come from pages the sweep stepped past before the firmware had
finished repainting them.  Which pages those are depends on the phase between the panel's
auto-repeat and the repaint, and that phase differs from run to run -- measured, two
40-page sweeps of different ranges lost their settled frames on completely different
pages (the start page on one; pages 2 and 38 on the other).  So a disagreement between
passes is exactly where the doubt is.

    python3 agree.py --dir RUN1 --dir RUN2 [--dir RUN3] --out MERGED [--prefix dump]

A byte is emitted only if at least ``--min-passes`` passes know it and every pass that
knows it reports the same value.  Everything else becomes a HOLE (mask 0), listed in the
coverage report with its address so it can be re-swept.  The mask of the output counts how
many passes agreed, so ``--min-passes 2`` output can still be told apart from 3-way
agreement afterwards.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate as V  # noqa: E402


def load_run(outdir: str, prefix: str = "dump"):
    """{page_base: (values uint8[256], known bool[256])} for one dumpgrab output dir."""
    args = argparse.Namespace(dir=outdir, prefix=prefix, pages=None, bin=None,
                              mask=None, base=None)
    pages, _meta = V.collect_pages(args)
    return {pa: (v, k) for pa, (v, k, _votes) in pages.items()}


def merge(runs, min_passes: int = 2):
    """Returns (pages, stats). A byte survives only if every pass that saw it agrees."""
    all_pages = sorted({pa for r in runs for pa in r})
    out = {}
    n_agree = n_conflict = n_thin = 0
    conflicts = []
    for pa in all_pages:
        vals = np.zeros((len(runs), 256), np.uint8)
        known = np.zeros((len(runs), 256), bool)
        for i, r in enumerate(runs):
            if pa in r:
                vals[i], known[i] = r[pa]
        count = known.sum(axis=0)
        # all knowing passes must report the same value
        first = np.zeros(256, np.uint8)
        agree = np.ones(256, bool)
        seen = np.zeros(256, bool)
        for i in range(len(runs)):
            take = known[i] & ~seen
            first[take] = vals[i][take]
            seen |= known[i]
            agree &= ~known[i] | (vals[i] == first)
        ok = agree & (count >= min_passes)
        n_agree += int(ok.sum())
        bad = seen & ~agree
        n_conflict += int(bad.sum())
        n_thin += int((seen & agree & (count < min_passes)).sum())
        for i in np.nonzero(bad)[0]:
            if len(conflicts) < 200:
                conflicts.append((pa + int(i),
                                  [int(vals[j][i]) for j in range(len(runs)) if known[j][i]]))
        if ok.any():
            out[pa] = (first, ok, count)
    return out, {"agreed": n_agree, "conflicts": n_conflict,
                 "seen_by_too_few": n_thin, "conflict_list": conflicts}


def write(pages, outdir: str, prefix: str = "dump", fill: int = 0x00):
    """Same on-disk contract as the pipeline: one .bin/.mask pair per contiguous run."""
    os.makedirs(outdir, exist_ok=True)
    runs = []
    cur = None
    for pa in sorted(pages):
        vals, ok, count = pages[pa]
        for i in range(256):
            if not ok[i]:
                continue
            addr = pa + i
            if cur is not None and addr == cur[0] + len(cur[1]):
                cur[1].append(int(vals[i]))
                cur[2].append(min(int(count[i]), 255))
            else:
                if cur is not None:
                    runs.append(cur)
                cur = (addr, [int(vals[i])], [min(int(count[i]), 255)])
    if cur is not None:
        runs.append(cur)
    lines = []
    for start, data, mask in runs:
        name = "%s_%08X_%06X" % (prefix, start, len(data))
        with open(os.path.join(outdir, name + ".bin"), "wb") as fh:
            fh.write(bytes(data))
        with open(os.path.join(outdir, name + ".mask"), "wb") as fh:
            fh.write(bytes(mask))
        lines.append("  RUN  0x%08X-0x%08X  %8d bytes" % (start, start + len(data) - 1,
                                                          len(data)))
    return runs, lines


def main(argv=None):
    ap = argparse.ArgumentParser("agree", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", action="append", required=True,
                    help="a dumpgrab output directory; give it at least twice")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="dump")
    ap.add_argument("--min-passes", type=int, default=2)
    args = ap.parse_args(argv)
    if len(args.dir) < 2:
        raise SystemExit("give --dir at least twice; agreement needs two passes")

    runs = [load_run(d, args.prefix) for d in args.dir]
    for d, r in zip(args.dir, runs):
        print("%-40s %4d pages, %7d known bytes"
              % (d, len(r), sum(int(k.sum()) for _v, k in r.values())))
    pages, stats = merge(runs, args.min_passes)
    out_runs, lines = write(pages, args.out, args.prefix)

    print("\nagreed bytes        : %d" % stats["agreed"])
    print("seen by too few     : %d (known to <%d passes)"
          % (stats["seen_by_too_few"], args.min_passes))
    print("CONFLICTS (dropped) : %d" % stats["conflicts"])
    for addr, vs in stats["conflict_list"][:20]:
        print("  0x%08X: %s" % (addr, " vs ".join("0x%02X" % v for v in vs)))
    if len(stats["conflict_list"]) > 20:
        print("  ... and %d more" % (len(stats["conflict_list"]) - 20))
    print("\ncontiguous runs     : %d" % len(out_runs))
    for line in lines[:40]:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
