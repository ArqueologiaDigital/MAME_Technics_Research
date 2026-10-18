#!/usr/bin/env python3
# Q: what BMP files exercise each branch of GetBitmapInfo 0x48421DE6 / Draw2BpFile_Impl 0x48428305?
# Writes the verifier's own test set into OUTDIR and a manifest (expected index per pixel is
# recomputed by check_dumps.py from the same pixel functions).
#   T8.BMP    8 bpp 320x240, 256-entry palette, blocks + a strip of indices 176..255
#   F4.BMP    4 bpp 640x240, 16 colours
#   TALL.BMP  8 bpp 320x300 (taller than 240): row y (top-down) has index y % 176
#   NEG.BMP   8 bpp 64x64 top-down (biHeight = -64)
#   B24.BMP   24 bpp 64x64            (must be rejected)
#   B2.BMP    2 bpp 64x64 header      (must be rejected)
#   B1.BMP    1 bpp 640x240 checkerboard
#   WIDE.BMP  8 bpp 700x10            (row longer than the 640-byte framebuffer line)
#   FULL8.BMP 8 bpp 640x240 (154,358 bytes, more than the 0x18000 read)
# usage: gen_bmp.py OUTDIR
import struct, sys, os
out = sys.argv[1]
os.makedirs(out, exist_ok=True)

def pal_colour(i):            # RGB tuple of file palette entry i
    return ((i * 37) & 0xFF, (255 - i) & 0xFF, (i * 11 + 64) & 0xFF)

def write_bmp(name, w, h, bpp, pix, ncol, topdown=False, comp=0, bisize=40):
    stride = ((w * bpp + 31) // 32) * 4
    rows = []
    order = range(h) if topdown else range(h - 1, -1, -1)   # file order
    for y in order:
        if bpp == 24:
            row = b"".join(bytes((pal_colour(pix(x, y))[2], pal_colour(pix(x, y))[1], pal_colour(pix(x, y))[0])) for x in range(w))
        else:
            vals = [pix(x, y) for x in range(w)]
            bits = 0; nb = 0; row = bytearray()
            for v in vals:
                bits = (bits << bpp) | (v & ((1 << bpp) - 1)); nb += bpp
                while nb >= 8:
                    nb -= 8; row.append((bits >> nb) & 0xFF)
            if nb:
                row.append((bits << (8 - nb)) & 0xFF)
            row = bytes(row)
        rows.append(row + b"\0" * (stride - len(row)))
    pal = b"" if bpp == 24 else b"".join(bytes((pal_colour(i)[2], pal_colour(i)[1], pal_colour(i)[0], 0)) for i in range(ncol))
    off = 14 + bisize + len(pal)
    data = b"".join(rows)
    hdr = struct.pack("<2sIHHI", b"BM", off + len(data), 0, 0, off)
    info = struct.pack("<IiiHHIIiiII", bisize, w, -h if topdown else h, 1, bpp, comp, len(data), 2835, 2835,
                       0 if bpp == 24 else ncol, 0)
    info += b"\0" * (bisize - 40)
    blob = hdr + info + pal + data
    open(os.path.join(out, name), "wb").write(blob)
    print(f"{name:10s} {w}x{h} {bpp}bpp ncol={ncol} topdown={topdown} size={len(blob)} offbits={off}")

def t8(x, y):
    if x >= 300:                      # strip of indices 176..255, 3 rows each
        return 176 + (y // 3) % 80
    return ((x // 20) + (y // 20) * 15) % 176
write_bmp("T8.BMP", 320, 240, 8, t8, 256)
write_bmp("F4.BMP", 640, 240, 4, lambda x, y: (x // 40) % 16, 16)
write_bmp("TALL.BMP", 320, 300, 8, lambda x, y: y % 176, 256)
write_bmp("NEG.BMP", 64, 64, 8, lambda x, y: 1 + (x // 8) % 8, 256, topdown=True)
write_bmp("B24.BMP", 64, 64, 24, lambda x, y: 5, 0)
write_bmp("B2.BMP", 64, 64, 2, lambda x, y: (x // 16) % 4, 4)
write_bmp("B1.BMP", 640, 240, 1, lambda x, y: ((x // 16) + (y // 16)) % 2, 2)
write_bmp("WIDE.BMP", 700, 10, 8, lambda x, y: (1 + y) if x < 640 else (100 + y), 256)
write_bmp("FULL8.BMP", 640, 240, 8, lambda x, y: 1 + (y % 175), 256)
