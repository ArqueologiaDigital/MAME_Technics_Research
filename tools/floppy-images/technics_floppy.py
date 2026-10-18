#!/usr/bin/env python3
"""technics_floppy.py -- the floppy a Technics data-disk installer writes, as a raw 1.44 MB image.

Question it answers: "what disk does a user end up with after running installer X onto a floppy
that instrument Y formatted?" The installers (ca6fp01.exe, idd7000.exe, ...) are ZIP archives
behind a self-extractor stub (WinZip Self-Extractor 16-bit, or Mijenix ZipMagic 32-bit). Run on a
PC they copy their members onto an already formatted disk; they never write a boot sector or a
FAT layout of their own. So the image is two independent parts:

1. BASE: a blank disk formatted by the instrument itself (DISK > DISK TOOLS > FORMAT, run in
   MAME and saved as .img). It supplies the boot sector, the empty FATs, the volume label the
   instrument wrote and the instrument's fill byte in every unused sector.
2. The files, written the way an extractor writes them through DOS/Windows: in archive (central
   directory) order, each in contiguous clusters from the first free one, into the first free
   root-directory entries; 8.3 name upper-cased, the DOS attribute byte stored in the archive,
   the archive's DOS write date/time, creation/access fields 0 (DOS / Windows 3.1 behaviour, no
   long-file-name entries); bytes after end of file in the last sector are 0.

--label replaces the volume label the base disk carries (entry 0 of the root directory, which
the instruments write as eleven '_' when no name is typed), padded with '_' to 11 characters.

usage: python3 -I technics_floppy.py BASE.img INSTALLER.exe OUT.img [--label NAME]
"""
import struct
import sys
import zipfile

SECTOR = 512


def geometry(img):
    bps, spc, res, nfats, rde, tot, media, spf = struct.unpack_from("<HBHBHHBH", img, 11)
    assert (bps, spc, res, nfats, rde, tot, media, spf) == (512, 1, 1, 2, 224, 2880, 0xF0, 9), \
        "base is not a 1.44 MB FAT12 disk"
    root = res + nfats * spf
    return res, nfats, spf, root, root + rde * 32 // bps, rde, tot


def name83(n):
    base, ext = (n.upper().rsplit(".", 1) + [""])[:2] if "." in n else (n.upper(), "")
    assert 1 <= len(base) <= 8 and len(ext) <= 3 and "/" not in n, f"not an 8.3 name: {n!r}"
    return base.ljust(8).encode("ascii") + ext.ljust(3).encode("ascii")


def dos_datetime(dt):
    y, mo, d, h, mi, s = dt
    return (h << 11) | (mi << 5) | (s // 2), ((y - 1980) << 9) | (mo << 5) | d


def get_fat12(fatb, n):
    w = struct.unpack_from("<H", fatb, n * 3 // 2)[0]
    return w >> 4 if n & 1 else w & 0xFFF


def put_fat12(fatb, n, v):
    o = n * 3 // 2
    w = struct.unpack_from("<H", fatb, o)[0]
    w = (w & 0x000F) | (v << 4) if n & 1 else (w & 0xF000) | v
    struct.pack_into("<H", fatb, o, w)


def build(base, exe, label=None):
    img = bytearray(base)
    res, nfats, spf, root, data, rde, tot = geometry(img)
    fats = [img[(res + f * spf) * SECTOR:(res + (f + 1) * spf) * SECTOR] for f in range(nfats)]
    assert all(f == fats[0] for f in fats), "base FAT copies differ"
    fatb = bytearray(fats[0])
    nclusters = tot - data
    assert all(get_fat12(fatb, c) == 0 for c in range(2, nclusters + 2)), "base disk is not empty"
    entries = [root * SECTOR + 32 * i for i in range(rde)]
    if label is not None:
        lab = [o for o in entries if img[o + 11] & 0x08 and img[o] not in (0, 0xE5)]
        assert lab, "base disk has no volume label entry"
        assert len(label) <= 11
        img[lab[0]:lab[0] + 11] = label.upper().ljust(11, "_").encode("ascii")
    free = iter(o for o in entries if img[o] in (0, 0xE5))
    z = zipfile.ZipFile(exe)
    nxt = 2
    names = set()
    for info in z.infolist():
        payload = z.read(info)                 # zipfile checks each member's CRC-32
        ncl = (len(payload) + SECTOR - 1) // SECTOR
        assert nxt - 2 + ncl <= nclusters, "disk full"
        first = nxt if ncl else 0
        for k in range(ncl):
            c = nxt + k
            put_fat12(fatb, c, 0xFFF if k == ncl - 1 else c + 1)
            o = (data + c - 2) * SECTOR
            img[o:o + SECTOR] = payload[k * SECTOR:(k + 1) * SECTOR].ljust(SECTOR, b"\0")
        nxt += ncl
        n = name83(info.filename)
        assert n not in names, f"duplicate 8.3 name {info.filename}"
        names.add(n)
        e = bytearray(32)
        e[0:11] = n
        e[11] = info.external_attr & 0x27      # read-only, hidden, system, archive
        t, d = dos_datetime(info.date_time)
        struct.pack_into("<HHHI", e, 22, t, d, first, len(payload))
        o = next(free)
        img[o:o + 32] = e
    for f in range(nfats):
        o = (res + f * spf) * SECTOR
        img[o:o + len(fatb)] = fatb
    return img, len(names), nxt - 2, nclusters


def main():
    args = sys.argv[1:]
    label = None
    if "--label" in args:
        i = args.index("--label")
        label = args[i + 1]
        del args[i:i + 2]
    base, exe, out = args
    img, nfiles, used, total = build(open(base, "rb").read(), exe, label)
    open(out, "wb").write(img)
    print(f"{out}: {nfiles} files, {used} of {total} clusters")


if __name__ == "__main__":
    main()
