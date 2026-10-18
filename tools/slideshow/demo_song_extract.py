#!/usr/bin/env python3
"""demo_song_extract.py -- question it answers: what are the record (0x8E0) and the song
pages of the KN7000's built-in demo song N, as func_48457355 inflates them from the program
ROM, and which picture events (status 0x8A, 3 bytes) do the pages hold?

func_48457355 (song 1..12): record <- inflate(u32[0x50000C20 + 4*(N-1)]) into Rec8E0TablePtr(0)
(max 0x8E0), pages <- inflate(u32[0x50000C50 + 4*(N-1)]) into 0x5003D36C (max 0x9800),
sounds <- inflate(u32[0x50000C80 + 4*(N-1)]).  The .data image of 0x50000010.. lives at
program ROM 0x487B0B78 (notes/work-ram-map.md), so word W of .data is at ROM
0x487B0B78 + (W - 0x50000010).

usage: python3 -I demo_song_extract.py ROM N OUTDIR    (ROM = baserom/kn7000_program.rom)
writes OUTDIR/demoN_record.bin, OUTDIR/demoN_pages.bin and prints the 0x8A candidates.
"""
import sys, zlib, struct, os
BASE = 0x48400000
def main():
    rom = open(sys.argv[1], "rb").read()
    n = int(sys.argv[2], 0)
    out = sys.argv[3]
    def word(cpu): return struct.unpack_from("<I", rom, cpu - BASE)[0]
    def data_word(addr): return word(0x487B0B78 + (addr - 0x50000010))
    res = {}
    for name, tab in (("record", 0x50000C20), ("pages", 0x50000C50), ("sounds", 0x50000C80)):
        p = data_word(tab + 4 * (n - 1))
        blob = rom[p - BASE: p - BASE + 0x20000]
        for wb in (15, -15):
            try:
                d = zlib.decompressobj(wb)
                raw = d.decompress(blob)
                print(f"{name}: src 0x{p:08X} wbits {wb} -> 0x{len(raw):X} bytes (consumed 0x{len(blob)-len(d.unused_data):X})")
                res[name] = raw
                break
            except zlib.error as e:
                continue
        else:
            print(f"{name}: src 0x{p:08X} not zlib/deflate")
    os.makedirs(out, exist_ok=True)
    for k, v in res.items():
        open(os.path.join(out, f"demo{n}_{k}.bin"), "wb").write(v)
    pg = res.get("pages", b"")
    hits = [i for i in range(len(pg) - 2) if pg[i] == 0x8A]
    print(f"0x8A bytes in pages: {len(hits)}")
    for i in hits[:80]:
        b1, b2 = pg[i + 1], pg[i + 2]
        num = b1 | ((b2 & 0x3F) << 7)
        print(f"  page 0x{i//256:X} off 0x{i%256:02X}: 8A {b1:02X} {b2:02X} -> n={num & 0x1FFF} {'USER' if b2 & 0x40 else 'PRESET'}   ctx {pg[max(0,i-4):i+6].hex(' ')}")
main()
