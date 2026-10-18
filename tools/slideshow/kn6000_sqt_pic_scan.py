#!/usr/bin/env python3
"""kn6000_sqt_pic_scan.py -- question it answers: do the KN6000 'I KD' presentation songs
(CA-6FP01..04 .SQT) carry the same 3-byte picture events as KN7000 songs (status 0x8A, n & 0x7F,
(n >> 7) & 0x3F | 0x40 for USER -- encoder func_4846BE8B), and which picture numbers do they use?
Layout as measured here (2026-10-18): 'I KD' header with +8 part-1 size, +0xC part-2 size;
part 1 is raw deflate from +0x18 followed by a 4-byte (Adler-32-like) trailer, then part 2 is raw
deflate followed by 4 bytes (handy.sqt: part 2 at 0x476 = 0x18 + 0x45A + 4).
Prints every 0x8A,n,b2 triple with b2 in {0x00, 0x40} in part 2 (pages); a heuristic scan, the
running-status event stream is not parsed, so a hit can be a coincidence.
usage: python3 -I kn6000_sqt_pic_scan.py FILE.SQT [...]
"""
import sys, struct, zlib
for p in sys.argv[1:]:
    d = open(p, "rb").read()
    s1, s2, c1, c2 = struct.unpack_from("<IIII", d, 8)
    o = zlib.decompressobj(-15); p1 = o.decompress(d[0x18:]); off = len(d) - len(o.unused_data) + 4
    p2 = zlib.decompressobj(-15).decompress(d[off:])
    hits = [(i, p2[i + 1], p2[i + 2]) for i in range(len(p2) - 2) if p2[i] == 0x8A and p2[i + 2] in (0, 0x40)]
    print(f"{p}: magic {d[:4]!r} part 2 at +0x{off:X}, part1 0x{len(p1):X}/0x{s1:X} part2 0x{len(p2):X}/0x{s2:X}; 0x8A triples {len(hits)}")
    print("   n:", " ".join(f"{b1 | ((b2 & 0x3F) << 7)}{'U' if b2 & 0x40 else 'P'}@{i // 256:X}" for i, b1, b2 in hits))
