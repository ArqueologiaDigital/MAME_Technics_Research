#!/usr/bin/env python3
"""check_bmp.py -- validate an LCDCAPnn.BMP written by the KN7000 CaptureLcd (RGB path, 0x484156A0)
and compare it with a dump of the firmware's RGB565 plane 0x9CE00000 taken by lcdcap_runtime.lua.

What it checks: the BITMAPFILEHEADER / BITMAPINFOHEADER fields CaptureLcd writes
(bfSize 0x70836, bfOffBits 0x36, 640x240, 1 plane, 24 bpp, BI_RGB, biSizeImage 0x70800),
then converts to PNG, and reports which framebuffer row each BMP row equals (CaptureLcd's
loop reads row 0xF0 - y - r, i.e. rows 240..1, written bottom-up -- the row-offset question).

Usage: python3 check_bmp.py LCDCAP00.BMP OUT.png [FBDUMP.bin]
"""
import struct, sys
from PIL import Image
bmp = open(sys.argv[1], 'rb').read()
print("file size", len(bmp))
bfType, bfSize, r1, r2, bfOff = struct.unpack_from('<2sIHHI', bmp, 0)
(biSize, w, h, planes, bpp, comp, isz, xppm, yppm, clru, clri) = struct.unpack_from('<IiiHHIIiiII', bmp, 14)
print(f"bfType={bfType} bfSize=0x{bfSize:X} bfOffBits=0x{bfOff:X} biSize={biSize} {w}x{h} planes={planes} bpp={bpp} comp={comp} biSizeImage=0x{isz:X} ppm={xppm},{yppm} clrUsed={clru} clrImp={clri}")
ok = (bfType == b'BM' and bfSize == 0x70836 == len(bmp) and bfOff == 0x36 and biSize == 40 and w == 640 and h == 240
      and planes == 1 and bpp == 24 and comp == 0 and isz == 0x70800)
print("header matches CaptureLcd's constants:", ok)
px = bmp[bfOff:bfOff + 640 * 240 * 3]
img = Image.frombytes('RGB', (640, 240), px, 'raw', 'BGR', 0, -1)   # bottom-up BGR
img.save(sys.argv[2]); print("wrote", sys.argv[2])
if len(sys.argv) > 3:
    fb = open(sys.argv[3], 'rb').read()
    nrows = len(fb) // 1280
    def fbrow(r):
        out = bytearray()
        for x in range(640):
            p = fb[r * 1280 + 2 * x] | fb[r * 1280 + 2 * x + 1] << 8
            out += bytes(((p & 0xF800) >> 8, (p & 0x7E0) >> 3, (p & 0x1F) << 3))
        return bytes(out)
    fbrows = [fbrow(r) for r in range(nrows)]
    top = img.tobytes()
    match = {}
    for y in range(240):
        row = top[y * 1920:(y + 1) * 1920]
        hits = [r for r in range(nrows) if fbrows[r] == row]
        match[y] = hits
    for y in (0, 1, 2, 100, 237, 238, 239):
        print(f"  BMP display row {y:3d} == fb rows {match[y][:6]}{'...' if len(match[y]) > 6 else ''}")
    shift1 = sum(1 for y in range(240) if (y + 1) in match[y])
    shift0 = sum(1 for y in range(240) if y in match[y])
    print(f"rows equal to fb row y+1: {shift1}/240 ; equal to fb row y: {shift0}/240")
    # image of fb rows 0..239 for side-by-side
    fbimg = Image.frombytes('RGB', (640, 240), b''.join(fbrows[0:240]))
    fbimg.save(sys.argv[2].replace('.png', '_fb0-239.png'))
    print("wrote", sys.argv[2].replace('.png', '_fb0-239.png'))
