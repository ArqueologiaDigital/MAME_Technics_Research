#!/usr/bin/env python3
"""fat16_ls.py -- list the root directory of a FAT16 SD image (MBR or superfloppy) and optionally
extract one root file. Read-only. Used to look for LCDCAPnn.BMP after a MAME run.

Usage: python3 -I fat16_ls.py IMAGE [NAME.EXT OUTFILE]
"""
import struct, sys
img = sys.argv[1]
f = open(img, 'rb')
d0 = f.read(512)
base = 0
if d0[0x1FE:0x200] == b"\x55\xaa" and struct.unpack_from("<H", d0, 11)[0] == 0:
    base = struct.unpack_from("<I", d0, 0x1BE + 8)[0] * 512
f.seek(base); bs = f.read(512)
bps, spc, rsv, nfat, nroot = struct.unpack_from("<HBHBH", bs, 11)
tot16, _m, spf = struct.unpack_from("<HBH", bs, 19)
fat0 = base + rsv * bps
root = base + (rsv + nfat * spf) * bps
data0 = root + ((nroot * 32 + bps - 1) // bps) * bps
f.seek(fat0); fat = f.read(spf * bps)
f.seek(root); rd = f.read(nroot * 32)
ents = []
for i in range(nroot):
    e = rd[i * 32:(i + 1) * 32]
    if e[0] == 0: break
    if e[0] == 0xE5 or e[11] == 0x0F: continue
    name = e[0:8].decode('latin1').rstrip() + ('.' + e[8:11].decode('latin1').rstrip() if e[8:11].strip() else '')
    attr = e[11]; clus = struct.unpack_from('<H', e, 26)[0]; size = struct.unpack_from('<I', e, 28)[0]
    t, dt = struct.unpack_from('<HH', e, 22)
    ents.append((name, attr, clus, size, dt, t))
    print(f"{name:14s} attr={attr:02X} clus={clus:5d} size={size:9d} date={((dt>>9)+1980):04d}-{(dt>>5)&15:02d}-{dt&31:02d} {t>>11:02d}:{(t>>5)&63:02d}:{(t&31)*2:02d}")
if len(sys.argv) > 3:
    want = sys.argv[2].upper()
    for name, attr, clus, size, dt, t in ents:
        if name == want:
            out = bytearray(); c = clus
            while 2 <= c < 0xFFF8 and len(out) < size:
                f.seek(data0 + (c - 2) * spc * bps); out += f.read(spc * bps)
                c = struct.unpack_from('<H', fat, c * 2)[0]
            open(sys.argv[3], 'wb').write(out[:size])
            print("extracted", want, "->", sys.argv[3], len(out[:size]), "bytes (chain", "complete" if len(out) >= size else "SHORT", ")")
            break
    else:
        sys.exit("not found: " + want)
