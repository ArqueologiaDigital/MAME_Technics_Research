#!/usr/bin/env python3
# Q: do the MAME dumps written by verify_probe.lua match what the disassembly predicts for
# Draw2BpFile_Impl 0x48428305 (index + 0x20 into the 8-bpp plane 0x500D4080, palette slots
# 0x20..0xCF from file colours 0..0xAF as 0x00BBGGRR, RGB565 at 77/100 for slots 0x20..0xDF)?
# usage: check_dumps.py RUNDIR BMPDIR
import struct, sys, os
run, bmpdir = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def pal_colour(i):            # identical to gen_bmp.py
    return ((i * 37) & 0xFF, (255 - i) & 0xFF, (i * 11 + 64) & 0xFF)
def rgb565_77(r, g, b):
    r, g, b = r * 77 // 100, g * 77 // 100, b * 77 // 100
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | ((b & 0xF8) >> 3)
def load(tag):
    fb = open(f"{run}/{tag}_fb.bin", "rb").read()
    lcd = open(f"{run}/{tag}_lcd.bin", "rb").read()
    raw = struct.unpack("<256I", open(f"{run}/{tag}_palraw.bin", "rb").read())
    p565 = struct.unpack("<256H", open(f"{run}/{tag}_pal565.bin", "rb").read())
    return fb, lcd, raw, p565
def fbpx(fb, x, y): return fb[y * 640 + x]
def lcdpx(lcd, x, y): return struct.unpack_from("<H", lcd, (y * 640 + x) * 2)[0]

def region_check(tag, w, h, expect, x0=0, y0=0, label_box=(156, 216, 315, 235)):
    fb, lcd, raw, p565 = load(tag)
    bad = tot = 0; first = None
    for y in range(h):
        for x in range(w):
            if label_box and label_box[0] <= x <= label_box[2] and label_box[1] <= y <= label_box[3]:
                continue                          # the NN:NAME label is printed over the image
            tot += 1
            e = expect(x, y)
            if fbpx(fb, x0 + x, y0 + y) != e:
                bad += 1
                if first is None: first = (x, y, fbpx(fb, x0 + x, y0 + y), e)
    print(f"{tag}: framebuffer {tot - bad}/{tot} pixels as predicted; first mismatch {first}")
    return fb, lcd, raw, p565

def pal_check(tag, raw, p565, ncol):
    ok = sum(1 for i in range(min(ncol, 176)) if raw[0x20 + i] == (pal_colour(i)[2] << 16 | pal_colour(i)[1] << 8 | pal_colour(i)[0]))
    ok565 = sum(1 for i in range(min(ncol, 176)) if p565[0x20 + i] == rgb565_77(*pal_colour(i)))
    print(f"{tag}: raw palette 0x20..: {ok}/{min(ncol,176)} = file colour as 0x00BBGGRR; RGB565 77/100: {ok565}/{min(ncol,176)}")

# T8: 8 bpp 320x240 -- index + 0x20 (wrapping for 224..255)
def t8(x, y):
    i = 176 + (y // 3) % 80 if x >= 300 else ((x // 20) + (y // 20) * 15) % 176
    return (i + 0x20) & 0xFF
fb, lcd, raw, p565 = region_check("T8", 320, 240, t8)
pal_check("T8", raw, p565, 256)
print("T8: slots 0xD0..0xDF raw (untouched by the file):", " ".join(f"{raw[i]:06X}" for i in range(0xD0, 0xD4)), "...")
# LCD colour of an in-range pixel and of a wrapped one
for (x, y) in [(25, 45), (310, 0), (310, 150), (310, 239)]:
    i = fbpx(fb, x, y)
    print(f"T8: pixel ({x},{y}) fb {i:02X} lcd {lcdpx(lcd, x, y):04X} pal565[{i:02X}]={p565[i]:04X}")

# F4: 4 bpp 640x240, 16 colours
fb, lcd, raw, p565 = region_check("F4", 640, 240, lambda x, y: ((x // 40) % 16) + 0x20)
pal_check("F4", raw, p565, 16)
t8raw = load("T8")[2]
same = sum(1 for i in range(0x30, 0xD0) if raw[i] == t8raw[i])
print(f"F4: slots 0x30..0xCF: {same}/160 still equal to the T8 values; sample", " ".join(f"{raw[i]:08X}" for i in (0x30, 0x31, 0x60, 0xCF)))

# TALL: 8 bpp 320x300, row y (top-down) index y % 176 -> top 240 rows expected
fb, lcd, raw, p565 = region_check("TALL", 320, 240, lambda x, y: (y % 176) + 0x20)
alt = sum(1 for y in range(240) if fbpx(fb, 10, y) == ((y + 60) % 176) + 0x20)
print(f"TALL: rows matching the BOTTOM-240 hypothesis at x=10: {alt}/240")

# NEG: top-down 64x64 -> no pixels, palette loaded
fb, lcd, raw, p565 = load("NEG")
print("NEG: fb (0..7,0..3):", fb[0:8].hex(), "| raw[0x21]", f"{raw[0x21]:08X}", "expected",
      f"{pal_colour(1)[2] << 16 | pal_colour(1)[1] << 8 | pal_colour(1)[0]:08X}")
pal_check("NEG", raw, p565, 256)

for tag in ("B24", "B2"):
    fb, lcd, raw, p565 = load(tag)
    print(f"{tag}: raw[0x20]={raw[0x20]:08X} (sentinel 00123456) pal565[0x20]={p565[0x20]:04X} (sentinel 1234); fb row0[0:8]={fb[0:8].hex()}")

fb, lcd, raw, p565 = region_check("B1", 640, 240, lambda x, y: (((x // 16) + (y // 16)) % 2) + 0x20)
print(f"B1: raw[0x20]={raw[0x20]:08X} raw[0x21]={raw[0x21]:08X}")

# WIDE: 700x10 8 bpp; rows drawn bottom row first, each copy 700 bytes from the row start
fb, lcd, raw, p565 = load("WIDE")
print("WIDE: row 0 x0..3", fb[0:4].hex(), "x 636..643", fb[636:644].hex())
print("WIDE: row 1 x0..3", fb[640:644].hex(), "(prediction: tail of row 0 = index 100+0+0x20 = 0x84 for x<60)")
print("WIDE: row 10 x0..3 (below the image)", fb[6400:6404].hex(), "(prediction: tail of row 9 = 100+9+0x20 = 0x8D)")
print("WIDE: row 1 x 60..63", fb[700:704].hex(), "(prediction: own row 1 = 1+1+0x20 = 0x22)")

# FULL8 cut at 98,304 bytes
fb, lcd, raw, p565 = load("FULL8")
after = open(f"{run}/FULL8_after_502D0000.bin", "rb").read()
good = [y for y in range(240) if all(fbpx(fb, x, y) == 1 + (y % 175) + 0x20 for x in range(0, 640, 7))]
print(f"FULL8 (truncated): rows drawn from the file: {len(good)} (y {min(good) if good else '-'}..{max(good) if good else '-'});"
      f" row 0 x0..7 {fb[0:8].hex()}; RAM after 0x502D0000 first bytes {after[:8].hex()}")
