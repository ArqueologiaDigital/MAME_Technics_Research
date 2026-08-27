#!/usr/bin/env python3
"""Recompose a dumped SX-WSA1R display RAM under each SED1330 MX mode.

QUESTION IT ANSWERS: the emulated wsa1r shows highlighted GUI elements as solid
white blocks.  Which composition rule turns the SAME display RAM into the screen
the real unit shows (photos/wsa1r_screen_sample.jpg -- dark glyphs on a light
field inside every highlight)?

INPUT: the 32768-byte display-RAM image written by
notes/wsa1-probes/wsa1_ovlay_and_highlight_layers.lua with DUMPBIN set.

The geometry is the firmware's own, not a guess: LCD_Init_SED1330 (prom_a
0xF8E819) sends SYSTEM SET `30 07 00 27 35 EF 28 00` -> 8 pixels per byte, 40
bytes per line, 240 lines, and SCROLL `00 00 F0 00 26 F0 00 4C` -> SAD1 = 0x0000,
SAD2 = 0x2600, SAD3 = 0x4C00.  MSB is the leftmost pixel (the plotter's mask
table at 0xF8EDAC is 80 40 20 10 08 04 02 01).

  python3 wsa1_compose_layers.py wsa1_vram.bin --out-prefix comp

writes comp_or.png / comp_xor.png / comp_and.png and prints, for every byte
where layers 0 and 1 overlap, the hand-checkable arithmetic.

MEASURED 2026-08-27: with the boot SOUND MODE screen in display RAM, OR
reproduces the emulator's solid white block exactly, and XOR reproduces the
photograph -- "Sound Name *****" in dark glyphs on a light field, and the part
number "1" punched dark out of its highlighted box.  Layers 0 and 1 overlap in
2780 pixels; layers 1 and 2 overlap in none, so this screen says nothing about
how the THIRD layer joins in.
"""
import argparse

AP, W, H = 40, 320, 240
BASE = (0x0000, 0x2600, 0x4C00)


def unpack(data, base):
    return [[(data[base + y * AP + x // 8] >> (7 - (x % 8))) & 1
             for x in range(W)] for y in range(H)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--out-prefix", default="comp")
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()

    data = open(args.dump, "rb").read()
    if len(data) < 0x4C00 + H * AP:
        raise SystemExit("dump too short: %d bytes" % len(data))
    L = [unpack(data, b) for b in BASE]

    for name, fn in (("or", lambda a, b, c: a | b | c),
                     ("xor", lambda a, b, c: (a ^ b) | c),
                     ("and", lambda a, b, c: (a & b) | c)):
        try:
            from PIL import Image
        except ImportError:
            print("PIL missing; skipping %s.png" % name)
            break
        im = Image.new("RGB", (W, H))
        px = im.load()
        for y in range(H):
            for x in range(W):
                v = fn(L[0][y][x], L[1][y][x], L[2][y][x])
                px[x, y] = (200, 225, 255) if v else (10, 40, 160)
        im.resize((W * args.scale, H * args.scale), Image.NEAREST).save(
            "%s_%s.png" % (args.out_prefix, name))
        print("wrote %s_%s.png" % (args.out_prefix, name))

    for i, b in enumerate(BASE):
        n = sum(1 for y in range(H) for x in range(W) if L[i][y][x])
        print("layer%d SAD=0x%04X : %d set pixels" % (i, b, n))
    ov = [(0, 1), (0, 2), (1, 2)]
    for a, b in ov:
        n = sum(1 for y in range(H) for x in range(W) if L[a][y][x] and L[b][y][x])
        print("overlap layer%d & layer%d : %d pixels" % (a, b, n))

    print("\nbytes where layer0 and layer1 both have set bits:")
    shown = 0
    for y in range(H):
        for bx in range(AP):
            b0 = data[BASE[0] + y * AP + bx]
            b1 = data[BASE[1] + y * AP + bx]
            if b0 & b1 and shown < 12:
                print("  y=%3d x=%3d..%3d  L0 @0x%04X=%02X  L1 @0x%04X=%02X"
                      "  ->  OR=%02X  XOR=%02X  AND=%02X"
                      % (y, bx * 8, bx * 8 + 7,
                         BASE[0] + y * AP + bx, b0, BASE[1] + y * AP + bx, b1,
                         b0 | b1, b0 ^ b1, b0 & b1))
                shown += 1


if __name__ == "__main__":
    main()
