#!/usr/bin/env python3
# make_fat12.py -- build a 1.44 MB FAT12 floppy image (raw .img) from a list of files.
# Question it serves: lets demo_feature_probe.lua insert a disk that carries a
# KN7000-format FEATURE.PRE presentation into MAME's kn7000 floppy drive.
# usage: python3 -I make_fat12.py OUT.img NAME=SRCPATH [NAME=SRCPATH ...]
#   NAME is the 8.3 name to store (upper case), SRCPATH the host file.
import struct
import sys

SECTOR = 512
TOTAL = 2880
SPC = 1            # sectors per cluster
RESERVED = 1
NFATS = 2
ROOT_ENTRIES = 224
FAT_SECTORS = 9
MEDIA = 0xF0


def boot_sector():
    b = bytearray(SECTOR)
    b[0:3] = b"\xEB\x3C\x90"
    b[3:11] = b"MSDOS5.0"
    struct.pack_into("<HBHBHHBHHHII", b, 11, SECTOR, SPC, RESERVED, NFATS, ROOT_ENTRIES,
                     TOTAL, MEDIA, FAT_SECTORS, 18, 2, 0, 0)
    b[36] = 0          # drive number
    b[38] = 0x29       # extended boot signature
    struct.pack_into("<I", b, 39, 0x12345678)
    b[43:54] = b"KN7000 TEST"
    b[54:62] = b"FAT12   "
    b[510:512] = b"\x55\xAA"
    return b


def name83(n):
    base, _, ext = n.upper().partition(".")
    assert 1 <= len(base) <= 8 and len(ext) <= 3, n
    return base.ljust(8).encode() + ext.ljust(3).encode()


def main():
    out = sys.argv[1]
    files = []
    for arg in sys.argv[2:]:
        n, _, src = arg.partition("=")
        files.append((n, open(src, "rb").read()))
    img = bytearray(TOTAL * SECTOR)
    img[0:SECTOR] = boot_sector()
    fat = [0] * 3072
    fat[0] = 0xF00 | MEDIA
    fat[1] = 0xFFF
    root_start = RESERVED + NFATS * FAT_SECTORS
    root_secs = ROOT_ENTRIES * 32 // SECTOR
    data_start = root_start + root_secs
    nclusters = TOTAL - data_start
    nxt = 2
    root = bytearray(ROOT_ENTRIES * 32)
    for i, (n, data) in enumerate(files):
        ncl = max(1, (len(data) + SECTOR - 1) // SECTOR) if data else 0
        first = nxt if ncl else 0
        assert nxt + ncl - 2 <= nclusters, "disk full"
        for k in range(ncl):
            c = nxt + k
            fat[c] = 0xFFF if k == ncl - 1 else c + 1
            off = (data_start + c - 2) * SECTOR
            chunk = data[k * SECTOR:(k + 1) * SECTOR]
            img[off:off + len(chunk)] = chunk
        nxt += ncl
        e = bytearray(32)
        e[0:11] = name83(n)
        e[11] = 0x20
        struct.pack_into("<HH", e, 22, 0, 0x2D52)   # time 00:00, date 2002-10-18
        struct.pack_into("<H", e, 26, first)
        struct.pack_into("<I", e, 28, len(data))
        root[i * 32:(i + 1) * 32] = e
    fatb = bytearray(FAT_SECTORS * SECTOR)
    for i in range(0, len(fat) - 1, 2):
        v = fat[i] | (fat[i + 1] << 12)
        j = i * 3 // 2
        if j + 3 <= len(fatb):
            fatb[j:j + 3] = v.to_bytes(3, "little")
    for f in range(NFATS):
        off = (RESERVED + f * FAT_SECTORS) * SECTOR
        img[off:off + len(fatb)] = fatb
    off = root_start * SECTOR
    img[off:off + len(root)] = root
    open(out, "wb").write(img)
    print(f"{out}: {len(files)} files, {nxt - 2} clusters used")


if __name__ == "__main__":
    main()
