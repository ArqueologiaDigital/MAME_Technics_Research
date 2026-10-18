#!/usr/bin/env python3
"""mkfat12.py -- write a blank, freshly formatted 1.44 MB FAT12 floppy image (raw .img),
the layout an MS-DOS FORMAT A: /F:1440 produces: 512 B/sector, 1 sector/cluster, 1 reserved,
2 FATs x 9 sectors, 224 root entries, 2880 sectors, media F0, 18 sectors/track, 2 heads.
mtools is not installed on this machine, hence this script.

Usage: python3 mkfat12.py OUT.img [LABEL]
"""
import struct, sys
out = sys.argv[1]
label = (sys.argv[2] if len(sys.argv) > 2 else "LCDCAP").upper()[:11].ljust(11).encode()
img = bytearray(1474560)
bs = bytearray(512)
bs[0:3] = b"\xEB\x3C\x90"
bs[3:11] = b"MSDOS5.0"
struct.pack_into("<HBHBHHBHHHII", bs, 11, 512, 1, 1, 2, 224, 2880, 0xF0, 9, 18, 2, 0, 0)
struct.pack_into("<BBBI", bs, 36, 0x00, 0, 0x29, 0x1234ABCD)
bs[43:54] = label
bs[54:62] = b"FAT12   "
bs[510:512] = b"\x55\xAA"
img[0:512] = bs
for n in range(2):                       # FAT copies at sectors 1 and 10
    o = (1 + 9 * n) * 512
    img[o:o + 3] = b"\xF0\xFF\xFF"
root = (1 + 18) * 512                    # sector 19
img[root:root + 11] = label              # volume-label entry
img[root + 11] = 0x08
open(out, "wb").write(img)
print("wrote", out, len(img), "bytes, label", label.decode().strip())
