#!/usr/bin/env python3
"""dumpgrab -- read KN7000 ROM back out of its hidden MEMORY DUMP screen.

The KN7000's service firmware has a hex-viewer screen (the 1/4/5/8 UP+DOWN chord) that
prints 256 bytes of any CPU address as 16 rows of 16 hex bytes, each row labelled with
its own full 32-bit address, and an orange page button that steps +0x100 and auto-repeats
when held.  Point a camera or a composite-video grabber at that screen, hold the button,
and the instrument reads its own flash out loud.  This tool turns that video back into
bytes.

Four modes, one output format:

    dumpgrab.py image FRAME.png [FRAME.png ...]   one still, or a handful
    dumpgrab.py frames DIR/                       a directory of stills
    dumpgrab.py video FILE.avi | /dev/videoN      a recording, or a live grabber
    dumpgrab.py validate --dir OUT --oracle ROM   score what came out against a known ROM

Every mode writes, into --out:

    <prefix>_<START>_<LEN>.bin    the bytes, one contiguous recovered run per file
    <prefix>_<START>_<LEN>.mask   1 byte per byte: 0 = never recovered, N = N frame votes
    <prefix>_manifest.json        runs, holes, conflicts, fill byte
    <prefix>_coverage.txt         human-readable coverage + holes to re-sweep
    <prefix>_report.json          frame/tear/vote statistics (+ oracle score if given)

A hole is never quietly filled: an unrecovered byte is 0 in the mask and the fill byte in
the .bin.  A gap can be re-swept in thirty seconds; an invented byte can never be found
again.

Pieces:
    kn7000dump/       single-frame extractor: geometry fit, glyph OCR, per-byte confidence
    kn7000videograb/  frame sources, tear detection, cross-frame voting, assembly
    adapter.py        the glue between the two
    validate.py       scoring against a known ROM (byte accuracy + glyph confusion)
    capture/          the MAME harness that produced the emulator datasets
    predict/          composite-video degradation simulator (what to expect on real video)

Dependencies: python3, numpy, Pillow.  ffmpeg (the binary) for video mode only.
No OpenCV -- it is not installed on this machine and nothing here needs it.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DEFAULT_EXTRACTOR = "adapter:ShippedExtractor"
ORACLE_BASES = (("program", 0x48400000), ("table", 0x48000000))


def infer_oracle_base(path: str):
    name = os.path.basename(path).lower()
    for key, base in ORACLE_BASES:
        if key in name:
            return base
    return None


def oracle_specs(values):
    """Accept ``PATH`` (base inferred from the filename) or ``BASE=PATH``."""
    out = []
    for v in values or []:
        if "=" in v and not os.path.exists(v):
            b, path = v.split("=", 1)
            out.append((int(b, 0), path))
            continue
        base = infer_oracle_base(v)
        if base is None:
            raise SystemExit(
                "cannot infer the CPU base of oracle %r -- pass it as BASE=PATH" % v)
        out.append((base, v))
    return out


# --------------------------------------------------------------------------- #
def run_pipeline(spec, args, passthrough):
    """All three capture modes funnel through the same voter/assembler."""
    from kn7000videograb import cli as vcli

    argv = ["--input", spec, "--out", args.out, "--prefix", args.prefix,
            "--extractor", args.extractor]
    for base, path in oracle_specs(args.oracle):
        argv += ["--oracle", "0x%08X=%s" % (base, path)]
    for e in args.expect or []:
        argv += ["--expect", e]
    if args.limit:
        argv += ["--limit", str(args.limit)]
    if args.stride and args.stride != 1:
        argv += ["--stride", str(args.stride)]
    if args.dump_logs:
        argv += ["--dump-logs"]
    if args.progress_every:
        argv += ["--progress-every", str(args.progress_every)]
    argv += list(passthrough)
    return vcli.main(argv)


def cmd_image(args, passthrough):
    """Single-image mode: the full pipeline, plus a human-readable dump of each frame."""
    from adapter import ShippedExtractor

    ex = ShippedExtractor()
    for path in args.frames:
        res = ex.extract(_load(path))["_result"]
        print("== %s" % path)
        if res.base_address is None:
            print("   NOT READ: no base address (%s)" % (", ".join(res.flags) or "-"))
            continue
        n_ok = sum(res.row_addr_ok)
        print("   base 0x%08X   rows on the ladder %d/16   legend %s"
              % (res.base_address, n_ok,
                 {k: (None if v is None else "%X" % v) for k, v in res.legend.items()}))
        if n_ok < 15:
            print("   ^ SELF-CHECK FAILED -- these bytes are not trustworthy")
        for r in range(16):
            row = bytes(res.data[16 * r:16 * r + 16])
            lo = float(res.conf[r].min())
            print("   %08X  %s   min-conf %.2f"
                  % (res.base_address + 16 * r, row.hex(" "), lo))
        low = int((res.conf < 0.5).sum())
        print("   bytes below confidence 0.5: %d/256" % low)
        if res.flags:
            print("   flags: %s" % " ".join(res.flags))

    if len(args.frames) == 1:
        spec = args.frames[0]
    else:                                   # several stills: hand the voter a file list
        spec = _tmp_dir_of(args.frames, args.out)
    return run_pipeline(spec, args, passthrough)


def _load(path):
    from PIL import Image
    import numpy as np
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


def _tmp_dir_of(paths, out):
    """Symlink a list of stills into one directory so the directory source can read it."""
    d = os.path.join(out, "_frames")
    os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(d, "*")):
        os.unlink(f)
    for i, p in enumerate(paths):
        os.symlink(os.path.abspath(p), os.path.join(d, "%05d%s" % (i, os.path.splitext(p)[1])))
    return d


def cmd_frames(args, passthrough):
    return run_pipeline(args.directory, args, passthrough)


def cmd_video(args, passthrough):
    return run_pipeline(args.path, args, passthrough)


def cmd_agree(args, passthrough):
    import agree as A

    argv = ["--out", args.out, "--prefix", args.prefix,
            "--min-passes", str(args.min_passes)]
    for d in args.dir:
        argv += ["--dir", d]
    return A.main(argv + list(passthrough))


def cmd_validate(args, passthrough):
    import validate as V

    paths = [path for _, path in oracle_specs(args.oracle)]
    if not paths:
        raise SystemExit("validate needs at least one --oracle ROM")
    argv = ["--dir", args.dir, "--prefix", args.prefix]
    if args.json:
        argv += ["--json", args.json]
    if args.max_mismatch is not None:
        argv += ["--max-mismatch", str(args.max_mismatch)]
    argv += list(passthrough)
    argv += ["--oracle"] + paths          # nargs='+', so it must come last
    sys.argv = ["validate.py"] + argv
    return V.main()


# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(
        "dumpgrab", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Anything this parser does not recognise is passed straight through to "
               "the pipeline CLI (python3 -m kn7000videograb --help).")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, validate=False):
        sp.add_argument("--out", default="dumpgrab-out", help="output directory")
        sp.add_argument("--prefix", default="dump", help="output file prefix")
        sp.add_argument("--oracle", action="append", default=[],
                        help="ROM to score against: PATH (base inferred from the name) "
                             "or BASE=PATH; repeatable")
        if validate:
            return
        sp.add_argument("--extractor", default=DEFAULT_EXTRACTOR,
                        help="module:attr of the frame extractor "
                             "(default %s; 'reference' = the built-in stand-in)"
                             % DEFAULT_EXTRACTOR)
        sp.add_argument("--expect", action="append", default=[],
                        help="target range START:LENGTH for the coverage report")
        sp.add_argument("--limit", type=int, default=None, help="stop after N frames")
        sp.add_argument("--stride", type=int, default=1, help="use every Nth frame")
        sp.add_argument("--dump-logs", action="store_true",
                        help="also write per-frame and per-tear JSON logs")
        sp.add_argument("--progress-every", type=int, default=0)

    sp = sub.add_parser("image", help="one or more still frames")
    sp.add_argument("frames", nargs="+")
    common(sp)
    sp.set_defaults(func=cmd_image)

    sp = sub.add_parser("frames", help="a directory of still frames")
    sp.add_argument("directory")
    common(sp)
    sp.set_defaults(func=cmd_frames)

    sp = sub.add_parser("video", help="a video file, or a live V4L2 device")
    sp.add_argument("path")
    common(sp)
    sp.set_defaults(func=cmd_video)

    sp = sub.add_parser("agree", help="merge independent sweeps, keep only what they agree on")
    sp.add_argument("--dir", action="append", required=True,
                    help="a dumpgrab output directory; give it at least twice")
    sp.add_argument("--min-passes", type=int, default=2)
    common(sp, validate=True)
    sp.set_defaults(func=cmd_agree)

    sp = sub.add_parser("validate", help="score an extraction against a known ROM")
    sp.add_argument("--dir", required=True, help="a dumpgrab output directory")
    sp.add_argument("--json", help="write the machine-readable report here")
    sp.add_argument("--max-mismatch", type=int, default=40)
    common(sp, validate=True)
    sp.set_defaults(func=cmd_validate)
    return p


def main(argv=None):
    p = build_parser()
    args, passthrough = p.parse_known_args(argv)
    return args.func(args, passthrough)


if __name__ == "__main__":
    sys.exit(main())
