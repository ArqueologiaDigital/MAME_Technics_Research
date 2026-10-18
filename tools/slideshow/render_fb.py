#!/usr/bin/env python3
"""render_fb.py -- question it answers: what picture does the KN7000 work RAM hold for the
LCD, independent of MAME's own LCD rendering?  Re-implements LcdOut (0x48414D71..0x48414DC9,
read 2026-10-18): for each of the 640 x 240 bytes p of the frame buffer 0x500D4080,
  (p & 0xF0) == 0xD0 -> direct colour: R4 = p & 0xF, G4 = q >> 4, B4 = q & 0xF where q is the
                        byte at the same offset of PICTURE_PLANE2 0x500F9880
                        (RGB565 word = R4<<12 | G4<<7 | B4<<1)
  otherwise          -> RGB565 palette 0x50122AAC[p] (256 x u16)
usage: python3 -I render_fb.py FB.bin PLANE2.bin PAL565.bin OUT.png
(The 0x50031490 CLUT is NOT what LcdOut reads; an earlier version of this script used it.)
"""
import sys, struct
from PIL import Image
fb = open(sys.argv[1], "rb").read(); p2 = open(sys.argv[2], "rb").read(); pal = open(sys.argv[3], "rb").read()
assert len(fb) == len(p2) == 640 * 240 and len(pal) == 0x200
def c565(w): return ((w >> 11 & 31) * 255 // 31, (w >> 5 & 63) * 255 // 63, (w & 31) * 255 // 31)
lut = [c565(struct.unpack_from("<H", pal, 2 * i)[0]) for i in range(256)]
out = bytearray()
ndirect = 0
for i, p in enumerate(fb):
    if p & 0xF0 == 0xD0:
        q = p2[i]; out += bytes(c565((p & 0xF) << 12 | (q >> 4) << 7 | (q & 0xF) << 1)); ndirect += 1
    else:
        out += bytes(lut[p])
Image.frombytes("RGB", (640, 240), bytes(out)).save(sys.argv[4])
print(sys.argv[4], f"direct-colour pixels {ndirect} of {len(fb)}")
