#!/usr/bin/env python3
"""sqt_jkd.py -- question it answers: can we read and write KN7000 'J KD' sequencer files
(.SQT) exactly as the firmware's decoder func_48533F61 reads them?

Header (0x18 bytes, func_4852BB88 / func_4852F487): +0 'J KD', +4 00 01 00, +7 format byte
(0xF0 = whole sequencer, part 1 = 10 song records = 0x58C0; 0x0F = one song, part 1 = 0x8E0),
+8 part-1 decoded size, +0xC part-2 decoded size (song pages), +0x10 part-1 coded size,
+0x14 part-2 coded size, +0x18 coded part 1, then coded part 2.
Coding (func_48533F61, read 2026-10-18): LZSS, 0x2000-byte ring zero-filled, r starts at
0x1FF6; one flag byte per 8 items, LSB first, bit 1 = literal byte, bit 0 = 2-byte match
pos = b1 | (b2 & 0xF8) << 5, length = (b2 & 7) + 3.

usage:
  python3 -I sqt_jkd.py info FILE.SQT [OUTPREFIX]      decode, check sizes, dump parts
  python3 -I sqt_jkd.py build OUT.SQT RECORD.bin PAGES.bin [TEMPLATE_PART1.bin]
        format 0xF0 file: part 1 = RECORD as song 1, songs 2..10 zero-filled or, with
        TEMPLATE_PART1 (a decoded part 1 of a real KN7000 save), copied from it; part 2 =
        PAGES; literal-only LZSS (flag 0xFF + 8 bytes), then re-decoded and compared.
"""
import sys, struct

def lzss_decode(src, maxout):
    ring = bytearray(0x2000); r = 0x1FF6; out = bytearray(); i = 0; flags = 0
    def getc():
        nonlocal i
        if i >= len(src): return -1
        c = src[i]; i += 1; return c
    while True:
        flags >>= 1
        if not (flags & 0x100):
            c = getc()
            if c < 0: break
            flags = c | 0xFF00
        if flags & 1:
            c = getc()
            if c < 0 or len(out) >= maxout: break
            out.append(c); ring[r] = c; r = (r + 1) & 0x1FFF
        else:
            a = getc(); b = getc()
            if a < 0 or b < 0: break
            pos = a | ((b & 0xF8) << 5); n = (b & 7) + 3
            for k in range(n):
                c = ring[(pos + k) & 0x1FFF]
                if len(out) >= maxout: break
                out.append(c); ring[r] = c; r = (r + 1) & 0x1FFF
    return bytes(out)

def lzss_encode_literal(data):
    out = bytearray()
    for k in range(0, len(data), 8):
        out.append(0xFF); out += data[k:k + 8]
    return bytes(out)

def info(path, prefix=None):
    d = open(path, "rb").read()
    magic, fmt = d[0:4], d[7]
    s1, s2, c1, c2 = struct.unpack_from("<IIII", d, 8)
    print(f"{path}: magic {magic!r} bytes4..7 {d[4:8].hex(' ')} part1 0x{s1:X}/coded 0x{c1:X} part2 0x{s2:X}/coded 0x{c2:X} file 0x{len(d):X} (0x18+c1+c2 = 0x{0x18+c1+c2:X})")
    p1 = lzss_decode(d[0x18:0x18 + c1], s1)
    p2 = lzss_decode(d[0x18 + c1:0x18 + c1 + c2], s2)
    print(f"  decoded part1 0x{len(p1):X} part2 0x{len(p2):X}")
    hits = [k for k in range(len(p2) - 2) if p2[k] == 0x8A and p2[k + 2] in (0x40, 0x00)]
    print(f"  0x8A,n,0x40/0x00 triples in part 2: {len(hits)}")
    if prefix:
        open(prefix + "_part1.bin", "wb").write(p1); open(prefix + "_part2.bin", "wb").write(p2)
    return p1, p2

def build(out, recf, pagesf, templf=None):
    rec = open(recf, "rb").read(); pages = open(pagesf, "rb").read()
    assert len(rec) == 0x8E0, hex(len(rec))
    if templf:
        t = open(templf, "rb").read(); assert len(t) == 0x58C0
        p1 = rec + t[0x8E0:]
    else:
        p1 = rec + bytes(0x58C0 - len(rec))
    e1 = lzss_encode_literal(p1); e2 = lzss_encode_literal(pages)
    hdr = b"J KD" + bytes([0, 1, 0, 0xF0]) + struct.pack("<IIII", len(p1), len(pages), len(e1), len(e2))
    open(out, "wb").write(hdr + e1 + e2)
    q1, q2 = info(out)
    assert q1 == p1 and q2 == pages, "round trip failed"
    print("  round trip OK")

if __name__ == "__main__":
    if sys.argv[1] == "info": info(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif sys.argv[1] == "build": build(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None)
