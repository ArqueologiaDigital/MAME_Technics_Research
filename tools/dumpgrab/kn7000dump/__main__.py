"""Command line for the single-image MEMORY DUMP extractor.

    python3 -m kn7000dump extract FRAME.png [FRAME2.png ...]
        [--atlas A.npz] [--json OUT.json] [--bin OUT.bin] [--text] [--quiet]

    python3 -m kn7000dump atlas --out A.npz --frame FRAME.png --address 48400000
        [--frame ... --address ...] [--rom-dir DIR]
        (labels every glyph from the ROM oracle -- no manual labelling at all)

    python3 -m kn7000dump grid FRAME.png [--out overlay.png]
        (writes a debug overlay of the fitted character grid)

Exit status is 0 if every frame produced a page whose 16 row addresses agree.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from .atlas import Atlas
from .extract import DEFAULT_ATLAS, PageExtractor
from .geometry import fit_grid
from .imageutil import as_rgb, load_rgb


def _fmt_page(res) -> str:
    lines = []
    base = res.base_address
    for r in range(16):
        addr = None if base is None else base + 0x10 * r
        hexs = " ".join("%02X" % res.data[r * 16 + k] for k in range(16))
        hexs = hexs[:23] + "-" + hexs[24:]
        low = "".join("*" if res.conf[r, k] < 0.5 else " " for k in range(16))
        lines.append("%s  %s   %s" % ("%08X" % addr if addr is not None else "????????",
                                      hexs, low.rstrip() and ("low:" + low) or ""))
    return "\n".join(lines)


def cmd_extract(args) -> int:
    ex = PageExtractor(atlas_path=args.atlas)
    out = []
    bad = 0
    for path in args.frames:
        res = ex.extract(load_rgb(path))
        ok = res.base_address is not None and all(res.row_addr_ok)
        bad += 0 if ok else 1
        if not args.quiet:
            print("%s: base=%s  low-confidence cells=%d  flags=%s"
                  % (os.path.basename(path),
                     "%08X" % res.base_address if res.base_address is not None else "None",
                     res.n_low_conf, ",".join(res.flags) or "-"))
            if args.text:
                print(_fmt_page(res))
        d = res.to_dict()
        d["frame"] = path
        out.append(d)
        if args.bin and res.base_address is not None:
            with open(args.bin, "ab") as fh:
                fh.write(bytes(res.data))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=1)
    return 1 if bad else 0


def cmd_atlas(args) -> int:
    from .oracle import Oracle
    if len(args.frame) != len(args.address):
        print("need one --address per --frame", file=sys.stderr)
        return 2
    orc = Oracle(args.rom_dir) if args.rom_dir else Oracle()
    samples = []
    for f, a in zip(args.frame, args.address):
        addr = int(a, 16)
        page = orc.page(addr)
        if page is None:
            print("address %08X is outside the known ROM windows" % addr, file=sys.stderr)
            return 2
        samples.append((load_rgb(f), addr, page))
    at = PageExtractor.build_atlas(samples, meta={"frames": [os.path.basename(f) for f in args.frame]})
    at.save(args.out)
    print("wrote %s: %d classes, %d samples"
          % (args.out, len(at.labels), int(at.counts.sum())))
    return 0


def cmd_grid(args) -> int:
    from PIL import Image, ImageDraw
    rgb = as_rgb(load_rgb(args.frame))
    g = fit_grid(rgb)
    im = Image.fromarray(rgb).convert("RGB")
    dr = ImageDraw.Draw(im)
    for r in range(16):
        for c in range(g.lay.hex_end):
            y0, y1, x0, x1 = g.cell_box(r, c)
            y0 += g.slope * (x0 - rgb.shape[1] * 0.5) * -1
            y1 += g.slope * (x0 - rgb.shape[1] * 0.5) * -1
            dr.rectangle([x0, y0, x1, y1], outline=(255, 0, 0))
    out = args.out or (os.path.splitext(args.frame)[0] + "_grid.png")
    im.save(out)
    print("slope=%.5f row_pitch=%.4f x0=%.3f cw=%.4f -> %s"
          % (g.slope, g.row_pitch, g.rows[0].x0, g.rows[0].cw, out))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kn7000dump", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract")
    e.add_argument("frames", nargs="+")
    e.add_argument("--atlas", default=DEFAULT_ATLAS)
    e.add_argument("--json")
    e.add_argument("--bin")
    e.add_argument("--text", action="store_true")
    e.add_argument("--quiet", action="store_true")
    e.set_defaults(func=cmd_extract)

    a = sub.add_parser("atlas")
    a.add_argument("--out", required=True)
    a.add_argument("--frame", action="append", required=True)
    a.add_argument("--address", action="append", required=True)
    a.add_argument("--rom-dir")
    a.set_defaults(func=cmd_atlas)

    g = sub.add_parser("grid")
    g.add_argument("frame")
    g.add_argument("--out")
    g.set_defaults(func=cmd_grid)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
