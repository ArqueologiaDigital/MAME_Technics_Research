#!/usr/bin/env python3
"""degrade_shipped.py -- run the SHIPPED dumpgrab pipeline over simulated composite damage.

`degrade.py` models what a composite-video chain does to a frame; `sweep.py` measured those
curves with the baseline reference extractor.  This script measures the same thing for the
extractor and voter that dumpgrab actually ships, end to end, so the prediction quoted in
the README belongs to the tool the user will run.

Every condition is measured the honest way:
  * each page is degraded REPS times with an independent sub-pixel capture jitter, so the
    cross-frame vote has something to average and is not just the same frame N times;
  * the frames go through the real Pipeline (gate, tear detection, Bayesian vote,
    assembly), not a private scoring path;
  * only bytes an oracle covers are scored, and refused frames simply produce no bytes,
    which shows up as coverage rather than as accuracy.

    python3 predict/degrade_shipped.py --frames DIR_OR_GLOB --oracle ROM \
        --axis blur_horizontal --sev 0 0.1 0.2 0.3 [--pages 8] [--reps 3]

IT IS A SIMULATION.  Its fidelity to a real capture card is unverified -- see the two
documented misbehaviours in degrade.py (composite_ntsc is non-monotone; resample applies
its resampling twice).
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import degrade  # noqa: E402
from adapter import ShippedExtractor  # noqa: E402
from kn7000videograb.cli import score_against_oracle  # noqa: E402
from kn7000videograb.pipeline import Pipeline, PipelineConfig  # noqa: E402
from kn7000videograb.video_io import SourceMeta  # noqa: E402


class ArraySource:
    """Minimal FrameSource over a list of in-memory RGB frames."""

    def __init__(self, frames, name):
        self.frames = frames
        self.meta = SourceMeta("memory", name,
                               frames[0].shape[1], frames[0].shape[0], 0.0, len(frames))

    def __iter__(self):
        for i, f in enumerate(self.frames):
            yield i, f

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def close(self):
        pass


def pick_pages(paths, extractor, want):
    """One SETTLED, fully clean frame per distinct page.

    The corpus selector must be far stricter than the voter's gate: a frame caught mid
    repaint carries rows from two pages, and degrading that and then scoring it measures
    the tear, not the damage.  So the criterion here is kn7000dump's own strict flag --
    all 16 rows on the ladder AND every one of the 256 cells read with nonzero confidence.
    (Learned the hard way: with the voter's gate instead, the "sev 0" control scored 41%
    and produced more pages than were put in.)
    """
    out = {}
    for p in paths:
        rgb = np.asarray(Image.open(p).convert("RGB"), dtype=np.uint8)
        r = extractor.extract(rgb)
        res = r.get("_result")
        if not r["ok"] or res is None or not res.ok or not all(res.row_addr_ok):
            continue
        base = r["base_address"]
        if base not in out:
            out[base] = rgb
        if len(out) >= want:
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser("degrade_shipped", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", required=True, help="directory or glob of clean frames")
    ap.add_argument("--oracle", action="append", required=True,
                    help="ROM path (base inferred from the name) or BASE=PATH")
    ap.add_argument("--axis", action="append", default=None,
                    help="damage axis (repeatable); default blur_horizontal")
    ap.add_argument("--sev", type=float, nargs="+",
                    default=[0.0, 0.1, 0.2, 0.3, 0.5])
    ap.add_argument("--pages", type=int, default=8)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--jitter", type=float, default=0.5, help="capture jitter, pixels")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    import dumpgrab
    oracles = [(b, open(p, "rb").read()) for b, p in dumpgrab.oracle_specs(args.oracle)]

    paths = sorted(glob.glob(os.path.join(args.frames, "*.png"))
                   if os.path.isdir(args.frames) else glob.glob(args.frames))
    if not paths:
        raise SystemExit("no frames matched %s" % args.frames)

    ex = ShippedExtractor()
    pages = pick_pages(paths, ex, args.pages)
    print("clean pages selected: %d (%s)"
          % (len(pages), " ".join("%08X" % a for a in sorted(pages))))

    axes = args.axis or ["blur_horizontal"]
    print("\n%-18s %6s  %-26s %8s %8s %9s" %
          ("axis", "sev", "physical unit", "pages", "bytes", "accuracy"))
    for axis in axes:
        for sev in args.sev:
            rng = np.random.default_rng(args.seed)
            frames = []
            for base in sorted(pages):
                src = degrade._f(pages[base])
                for _ in range(args.reps):
                    f = degrade.capture_jitter(src, args.jitter, rng)
                    if sev > 0:
                        f = degrade.apply_axis(f, axis, sev, rng)
                    frames.append(degrade._clip(degrade._f(f)).astype(np.uint8))
            pipe = Pipeline(ex, PipelineConfig(base_continuity="off"))
            with ArraySource(frames, "%s@%.2f" % (axis, sev)) as s:
                pipe.run(s)
            sc = score_against_oracle(pipe.image, oracles)
            print("%-18s %6.2f  %-26s %8d %8d %8.4f%%"
                  % (axis, sev, degrade.UNITS[axis](sev), len(pipe.image.pages),
                     sc["scored_bytes"], 100.0 * sc["accuracy"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
