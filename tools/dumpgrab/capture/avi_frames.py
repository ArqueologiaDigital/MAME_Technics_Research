#!/usr/bin/env python3
"""avi_frames.py -- read the AVI that MAME writes with -aviwrite / video:begin_recording().

MAME's AVI writer uses info.video_format = 0 (uncompressed 'DIB ') at 24 bpp, so every video
chunk in the movi list is a raw bottom-up BGR frame of width*height*3 bytes. No codec needed:
this parser is pure stdlib + numpy.

Deps: numpy (PIL only for --png).

    python3 avi_frames.py movie.avi --info
    python3 avi_frames.py movie.avi --png outdir/          # write frame%05d.png
    python3 avi_frames.py movie.avi --hash                 # per-frame sha1, for A/B against PNGs

As a library:
    from avi_frames import AviReader
    r = AviReader("movie.avi")
    print(r.width, r.height, r.fps, len(r))
    frame = r[0]           # numpy uint8 array (h, w, 3) in RGB order
"""
import argparse
import hashlib
import struct
import sys

import numpy as np


class AviReader:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        riff = self.f.read(12)
        if riff[0:4] != b"RIFF" or riff[8:12] != b"AVI ":
            raise ValueError(f"{path}: not a RIFF/AVI file")
        self.width = self.height = None
        self.fps = None
        self.offsets = []          # (file offset, length) of every video chunk
        self._scan(12, struct.unpack("<I", riff[4:8])[0] + 8)
        if self.width is None:
            raise ValueError(f"{path}: no avih/strf header found")

    # -- RIFF walk -------------------------------------------------------------
    def _scan(self, start, end):
        f = self.f
        pos = start
        while pos < end - 8:
            f.seek(pos)
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            ckid, cksz = hdr[0:4], struct.unpack("<I", hdr[4:8])[0]
            body = pos + 8
            if ckid in (b"LIST", b"RIFF"):
                typ = f.read(4)
                if typ == b"movi":
                    self._scan_movi(body + 4, body + cksz)
                else:
                    self._scan(body + 4, body + cksz)
            elif ckid == b"avih":
                d = f.read(cksz)
                usec_per_frame = struct.unpack("<I", d[0:4])[0]
                self.fps = 1e6 / usec_per_frame if usec_per_frame else None
            elif ckid == b"strf":
                d = f.read(cksz)
                if len(d) >= 40:
                    # BITMAPINFOHEADER: biSize, biWidth, biHeight, biPlanes, biBitCount, biCompression
                    (_size, w, h, _planes, bitcount) = struct.unpack("<Iii2H", d[0:16])
                    self.width, self.height = w, abs(h)
                    self.bitcount = bitcount
                    self.compression = d[16:20]
                    self.bottom_up = h > 0        # positive height == bottom-up DIB
            pos = body + cksz + (cksz & 1)

    def _scan_movi(self, start, end):
        f = self.f
        pos = start
        while pos < end - 8:
            f.seek(pos)
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            ckid, cksz = hdr[0:4], struct.unpack("<I", hdr[4:8])[0]
            # video chunks are "##db" (uncompressed) or "##dc" (compressed)
            if ckid[2:4] in (b"db", b"dc"):
                self.offsets.append((pos + 8, cksz))
            pos = pos + 8 + cksz + (cksz & 1)

    # -- frames ----------------------------------------------------------------
    def __len__(self):
        return len(self.offsets)

    def __getitem__(self, i):
        off, ln = self.offsets[i]
        self.f.seek(off)
        raw = self.f.read(ln)
        need = self.width * self.height * (self.bitcount // 8)
        if len(raw) < need:
            raise ValueError(f"frame {i}: short chunk {len(raw)} < {need}")
        a = np.frombuffer(raw[:need], dtype=np.uint8)
        a = a.reshape(self.height, self.width, self.bitcount // 8)
        if getattr(self, "bottom_up", True):
            a = a[::-1]
        return a[:, :, ::-1].copy() if self.bitcount == 24 else a.copy()   # BGR -> RGB


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("avi")
    ap.add_argument("--info", action="store_true")
    ap.add_argument("--png", metavar="DIR")
    ap.add_argument("--hash", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    r = AviReader(a.avi)
    if a.info or not (a.png or a.hash):
        print(f"file        : {a.avi}")
        print(f"size        : {r.width}x{r.height}  {r.bitcount} bpp  "
              f"compression={r.compression!r}  bottom_up={r.bottom_up}")
        print(f"fps         : {r.fps:.4f}" if r.fps else "fps: ?")
        print(f"frames      : {len(r)}")
        if len(r):
            import os
            print(f"bytes/frame : {r.offsets[0][1]}   file={os.path.getsize(a.avi)}")

    n = len(r) if not a.limit else min(a.limit, len(r))
    if a.png:
        from PIL import Image
        import os
        os.makedirs(a.png, exist_ok=True)
        for i in range(n):
            Image.fromarray(r[i]).save(os.path.join(a.png, f"frame{i:05d}.png"))
        print(f"wrote {n} PNGs to {a.png}")
    if a.hash:
        for i in range(n):
            print(f"{i}\t{hashlib.sha1(r[i].tobytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
