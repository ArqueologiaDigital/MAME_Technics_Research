"""Command line front end.

    python -m kn7000videograb --input SPEC --out DIR [options]

SPEC is a directory of frames, a single image, a video file, or /dev/videoN.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from typing import Callable, List, Optional, Tuple

import numpy as np

from .assembly import coverage_report
from .pipeline import Pipeline, PipelineConfig
from .video_io import open_source


def load_extractor(spec: str) -> Callable:
    """``reference`` for the built-in stand-in, or ``module:attr`` for package c2's."""
    if spec in ("reference", "ref", ""):
        from .reference_extractor import ReferenceExtractor
        return ReferenceExtractor()
    if ":" in spec:
        mod, attr = spec.split(":", 1)
    else:
        mod, attr = spec, "extract"
    m = importlib.import_module(mod)
    obj = getattr(m, attr)
    return obj() if isinstance(obj, type) else obj


def parse_range(s: str) -> Tuple[int, int]:
    """``0x48400000:0x400000`` -> (start, length)."""
    a, b = s.split(":")
    return int(a, 0), int(b, 0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("kn7000videograb", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True,
                   help="directory of frames, image, video file, or /dev/videoN")
    p.add_argument("--out", default="out", help="output directory")
    p.add_argument("--prefix", default="dump")
    p.add_argument("--extractor", default="reference",
                   help="'reference' (built in) or module:attr for package c2")
    p.add_argument("--limit", type=int, default=None, help="stop after N frames")
    p.add_argument("--stride", type=int, default=1, help="use every Nth frame")
    p.add_argument("--size", default=None, help="WxH, needed only for raw sources")

    g = p.add_argument_group("voting")
    g.add_argument("--vote-mode", choices=("bayes", "weighted"), default="bayes")
    g.add_argument("--max-votes-per-page", type=int, default=0,
                   help="cap frames folded into one page (0 = unlimited)")
    g.add_argument("--early-stop-margin", type=float, default=0.0,
                   help=">0 stops voting on a page once every cell is decided by this "
                        "log-likelihood margin")

    g = p.add_argument_group("dedup")
    g.add_argument("--dedup", choices=("identical", "similar", "off"), default="off",
                   help="reuse the cached extraction for bit-identical frames. "
                        "Default off: analog capture never produces identical "
                        "frames, and it measured more accurate")
    g.add_argument("--similar-threshold", type=float, default=6.0)

    g = p.add_argument_group("tearing")
    g.add_argument("--tear-policy", choices=("split", "discard", "discount", "off"),
                   default="split")
    g.add_argument("--no-ladder", action="store_true")
    g.add_argument("--no-confidence-tear", action="store_true")
    g.add_argument("--no-temporal-tear", action="store_true")
    g.add_argument("--loose-adjacent", action="store_true",
                   help="accept a ladder split without requiring adjacent page bases")
    g.add_argument("--cell-threshold", type=float, default=0.35)
    g.add_argument("--max-bad-cells", type=int, default=6)

    g = p.add_argument_group("assembly")
    g.add_argument("--fill", default="0x00", help="byte written where nothing is known")
    g.add_argument("--min-posterior", type=float, default=0.0,
                   help="cells whose voted posterior is below this are reported "
                        "UNKNOWN rather than guessed")
    g.add_argument("--base-continuity", choices=("off", "reject", "repair"),
                   default="reject",
                   help="what to do with a page address the sweep cannot be at: drop the "
                        "frame (default), rebuild its high half from context, or trust it")
    g.add_argument("--continuity-window", default="0x8000",
                   help="how far either side of the sweep's current position a page "
                        "address may be")
    g.add_argument("--max-gap", type=int, default=0,
                   help="bridge holes up to N bytes inside one output file "
                        "(bridged bytes stay 0 in the mask)")
    g.add_argument("--expect", action="append", default=[],
                   help="target range START:LENGTH for the coverage report; repeatable")

    g = p.add_argument_group("diagnostics")
    g.add_argument("--oracle", action="append", default=[],
                   help="BASE=PATH ROM file to score against; repeatable")
    g.add_argument("--progress-every", type=int, default=0)
    g.add_argument("--dump-logs", action="store_true",
                   help="write per-frame and tear logs as JSON")
    return p


def score_against_oracle(image, oracles: List[Tuple[int, bytes]]) -> dict:
    """Byte-for-byte comparison of everything we claim to know."""
    total = correct = 0
    unscored = 0
    wrong_examples = []
    for base, (data, known, post) in image.pages.items():
        for i in range(len(data)):
            if not known[i]:
                continue
            addr = base + i
            truth = None
            for obase, blob in oracles:
                if obase <= addr < obase + len(blob):
                    truth = blob[addr - obase]
                    break
            if truth is None:
                unscored += 1
                continue
            total += 1
            if int(data[i]) == truth:
                correct += 1
            elif len(wrong_examples) < 40:
                wrong_examples.append({
                    "address": f"0x{addr:08X}",
                    "got": f"0x{int(data[i]):02X}",
                    "truth": f"0x{truth:02X}",
                    "posterior": round(float(post[i]), 4),
                })
    return {
        "scored_bytes": total,
        "correct": correct,
        "wrong": total - correct,
        "accuracy": (correct / total) if total else 0.0,
        "unscored_bytes_outside_oracle": unscored,
        "wrong_examples": wrong_examples,
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = PipelineConfig(
        vote_mode=args.vote_mode,
        dedup=args.dedup,
        similar_threshold=args.similar_threshold,
        tear_policy=args.tear_policy,
        use_ladder=not args.no_ladder,
        use_confidence_tear=not args.no_confidence_tear,
        use_temporal_tear=not args.no_temporal_tear,
        strict_adjacent=not args.loose_adjacent,
        cell_threshold=args.cell_threshold,
        max_bad_cells=args.max_bad_cells,
        max_votes_per_page=args.max_votes_per_page,
        early_stop_margin=args.early_stop_margin,
        fill=int(args.fill, 0),
        min_posterior=args.min_posterior,
        base_continuity=args.base_continuity,
        continuity_window=int(args.continuity_window, 0),
        progress_every=args.progress_every,
    )
    size = None
    if args.size:
        w, h = args.size.lower().split("x")
        size = (int(w), int(h))

    extractor = load_extractor(args.extractor)
    pipe = Pipeline(extractor, cfg)
    with open_source(args.input, limit=args.limit, stride=args.stride, size=size) as src:
        print(f"source: {src.meta}", flush=True)
        pipe.run(src)

    os.makedirs(args.out, exist_ok=True)
    manifest = pipe.image.write(args.out, prefix=args.prefix, max_gap=args.max_gap)
    expected = [parse_range(e) for e in args.expect]
    report = pipe.report(expected)
    print(report)

    result = {"stats": pipe.stats.as_dict(), "manifest": manifest}

    if args.oracle:
        oracles = []
        for spec in args.oracle:
            b, path = spec.split("=", 1)
            with open(path, "rb") as fh:
                oracles.append((int(b, 0), fh.read()))
        sc = score_against_oracle(pipe.image, oracles)
        result["oracle"] = sc
        print("\n== oracle ==")
        print(f"scored bytes : {sc['scored_bytes']}")
        print(f"correct      : {sc['correct']}")
        print(f"wrong        : {sc['wrong']}")
        print(f"ACCURACY     : {100.0 * sc['accuracy']:.6f}%")
        if sc["wrong_examples"]:
            print("first wrong bytes:")
            for w in sc["wrong_examples"][:10]:
                print(f"  {w['address']} got {w['got']} truth {w['truth']}"
                      f" posterior {w['posterior']}")

    with open(os.path.join(args.out, args.prefix + "_report.json"), "w") as fh:
        json.dump(result, fh, indent=2)
    with open(os.path.join(args.out, args.prefix + "_coverage.txt"), "w") as fh:
        fh.write(report + "\n")
    if args.dump_logs:
        with open(os.path.join(args.out, args.prefix + "_frames.json"), "w") as fh:
            json.dump(pipe.frame_log, fh, indent=1)
        with open(os.path.join(args.out, args.prefix + "_tears.json"), "w") as fh:
            json.dump(pipe.tear_log, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
