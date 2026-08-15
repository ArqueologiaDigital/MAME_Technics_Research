#!/usr/bin/env python3
"""Render a KN2400 UI source-plane dump as a PNG, so it can be looked at.

The plane is 8 bits per pixel, 320x240, row-major -- deduced from the compositor at
0x485EC9D6, which consumes 8 source bytes per group and emits 8 two-bit pixels.

    ./tools/rig.sh kn24_planedump kn2400 -s 16          # writes /tmp/kn24_plane.bin
    python3 tools/kn24_plane_to_png.py /tmp/kn24_plane.bin -o /tmp/plane.png

Writes a PNG with no external dependencies (zlib + struct only), because the point is to
look at the picture, not to install an imaging stack.

--map controls how byte values become grey:
  raw    (default) value used directly as an 8-bit grey -- shows the plane as it IS
  low2   only the low 2 bits, scaled -- shows what a 2bpp consumer would see
  eq     rank each distinct value evenly across 0..255 -- makes near-identical values
         visible when the plane uses a narrow range (e.g. 0xE0 vs 0xE1)
"""
import argparse
import struct
import sys
import zlib


def write_png(path, w, h, grey):
    raw = bytearray()
    for y in range(h):
        raw.append(0)                       # filter type 0 for each scanline
        raw += grey[y * w:(y + 1) * w]

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))   # 8-bit greyscale
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dump")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("-W", "--width", type=int, default=320)
    ap.add_argument("-H", "--height", type=int, default=240)
    ap.add_argument("--map", choices=["raw", "low2", "eq"], default="raw")
    args = ap.parse_args()

    data = open(args.dump, "rb").read()
    need = args.width * args.height
    if len(data) < need:
        print(f"dump is {len(data)} B, need {need} for {args.width}x{args.height}",
              file=sys.stderr)
        return 1
    data = data[:need]

    if args.map == "raw":
        grey = bytearray(data)
    elif args.map == "low2":
        grey = bytearray((b & 3) * 85 for b in data)
    else:
        vals = sorted(set(data))
        # Rank-equalise: a plane using only 0xE0/0xE1 is invisible in raw, obvious here.
        lut = {v: (0 if len(vals) < 2 else round(255 * i / (len(vals) - 1)))
               for i, v in enumerate(vals)}
        grey = bytearray(lut[b] for b in data)

    write_png(args.out, args.width, args.height, grey)

    hist = {}
    for b in data:
        hist[b] = hist.get(b, 0) + 1
    top = sorted(hist.items(), key=lambda kv: -kv[1])[:8]
    print(f"{args.dump}: {len(data)} B, {len(hist)} distinct values, map={args.map}")
    for v, c in top:
        print(f"  0x{v:02X}  {c:7d}  {100.0 * c / len(data):5.1f}%")
    print(f"wrote {args.out} ({args.width}x{args.height} greyscale)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
