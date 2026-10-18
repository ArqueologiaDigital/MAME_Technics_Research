#!/usr/bin/env python3
"""fat12_relayout.py -- copy the files of a FAT12 floppy image onto a standard-layout 1.44 MB image.

Question it serves: does a KN6000/KN7000 accept a software-list disk once its files sit on a
floppy laid out the way DOS/Windows formats one? The floppy software lists' images were built
with pyfatfs: their FAT starts F0 0F FF and each FAT has 12 sectors. The KN6000/KN7000 media
probes (0x4853312E / 0x48470CE3) accept only F0 FF FF / F9 FF FF, and the KN6000 file system
expects 9-sector FATs (root directory at sector 19). See notes/kn6000-feature-presentation.md.

Reads the source image's BPB, follows each root-directory file's FAT12 chain (root directory
only, no subdirectories, which the presentation disks do not use), and writes the files in
directory order with make_fat12.py, next to this script.

usage: python3 -I fat12_relayout.py SRC.img OUT.img
       python3 -I fat12_relayout.py --fatid-only SRC.img OUT.img
--fatid-only copies SRC unchanged except bytes 1-2 of each FAT, set to FF FF (the variant that
passes the media probe but keeps the 12-sector FATs; runs B6, B10, D1).
"""
import os
import struct
import subprocess
import sys
import tempfile


def files_of(img):
    bps, spc, res, nfats, rde, _tot, _media, spf = struct.unpack_from("<HBHBHHBH", img, 11)
    fat = img[res * bps:(res + spf) * bps]
    root = (res + nfats * spf) * bps
    data = root + rde * 32

    def next_cluster(c):
        v = struct.unpack_from("<H", fat, c * 3 // 2)[0]
        return v >> 4 if c & 1 else v & 0xfff

    out = []
    for i in range(rde):
        e = img[root + 32 * i:root + 32 * i + 32]
        if e[0] == 0:
            break
        if e[0] == 0xe5 or e[11] & 0x18:          # deleted, volume label or directory
            continue
        name = e[0:8].decode("latin-1").rstrip()
        ext = e[8:11].decode("latin-1").rstrip()
        cl, size = struct.unpack_from("<HI", e, 26)
        buf = bytearray()
        while 2 <= cl < 0xff8 and len(buf) < size:
            o = data + (cl - 2) * spc * bps
            buf += img[o:o + spc * bps]
            cl = next_cluster(cl)
        out.append((name + ("." + ext if ext else ""), bytes(buf[:size])))
    return out


def fatid_only(src, dst):
    img = bytearray(open(src, "rb").read())
    bps, _spc, res, nfats, _rde, _tot, _media, spf = struct.unpack_from("<HBHBHHBH", img, 11)
    for i in range(nfats):
        o = (res + i * spf) * bps
        img[o + 1:o + 3] = b"\xff\xff"
    open(dst, "wb").write(img)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--fatid-only":
        return fatid_only(sys.argv[2], sys.argv[3])
    if len(sys.argv) != 3:
        sys.exit("usage: fat12_relayout.py [--fatid-only] SRC.img OUT.img")
    src, dst = sys.argv[1], sys.argv[2]
    files = files_of(open(src, "rb").read())
    maker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_fat12.py")
    with tempfile.TemporaryDirectory() as tmp:          # honours TMPDIR
        args = []
        for name, body in files:
            p = os.path.join(tmp, name)
            open(p, "wb").write(body)
            args.append("%s=%s" % (name, p))
        subprocess.run([sys.executable, "-I", maker, dst] + args, check=True)


if __name__ == "__main__":
    main()
