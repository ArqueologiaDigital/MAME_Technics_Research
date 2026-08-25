#!/usr/bin/env python3
"""The SX-KN1500's IC15 program image is HALF BLANK in four of its eight blocks,
and this script measures exactly how.

WHY IT IS HERE: this came out of the TMP95C061 timer regression pass.  The
KN1500 never boots -- it spends its whole run inside the crt0 RAM test at
0xFA047F-0xFA04A3 -- and the standing gate SKIPS it ("no screen device"), so
nothing was watching.  A live probe
(notes/wsa1-probes/tlcs900_16bit_unmodelled_use.lua) showed that RAM test
writing 0xA5/0x5A over the CPU's OWN internal I/O registers at 0x34-0x47, which
is not something a sane memory test does.  Following that back gives the cause,
and it is in the ROM image, not in the emulation.

THE ROUTINE.  0xFA0460 loads a region descriptor and tests it:

    fa046c  lda XBC,0xf38b24     ; table of 10-byte region descriptors
    fa0471  exts XWA             ; index = E * 10
    fa0473  add XWA,XBC
    fa0475  ld XIX,(XWA)         ; +0 = start address
    fa0477  ld XBC,(XWA+0x04)    ; +4 = length
    fa047a  srl 0x01,XBC
    fa047f  ld D,(XIX) / ld (XIX),0x5a / cp (XIX),0x5a / ...   ; the A5/5A test

Descriptor 0 reads start = 0xFFDEFFF2, length = 0xFFF2FF00.  Those are not
addresses; they are 0xFF filler interleaved with real bytes.  With a
16-million-entry length the pointer walks the entire 24-bit space, which is how
it reaches the internal I/O block.

THE DEFECT, and it is perfectly regular.  Split the 2 MiB image into eight
256 KiB blocks.  Four of them (0, 1, 4, 5 -- i.e. 0xE00000, 0xE40000, 0xF00000,
0xF40000) have 0xFF in EVERY odd-offset byte.  The other four are normal.  And
for each damaged block, its even-offset byte stream is EXACTLY the odd-offset
byte stream of the block 512 KiB above it -- 131072 of 131072 bytes, all four
pairs, no exceptions.

So the odd bytes are not lost, they are misplaced: the image looks like a dump
where A0 was mis-driven for half the passes.

WHAT THIS DOES *NOT* ESTABLISH.  The obvious repair -- treat blocks 2, 3, 6, 7
as the real 1 MiB ROM -- does NOT work.  Under it, 0xF38B24 lands in a table of
instrument-name ASCII ("...ynthgoA...", "ourinAcc"), not in a region
descriptor.  The reset vector at 0xFFFF00 is unchanged either way (block 7 is
undamaged), which is why the machine gets as far as it does.  The right
reassembly is not known and this script deliberately does not guess one:
the honest conclusion is that IC15 needs a RE-DUMP, and the driver's ROM entry
should say so.

RUN:
    python3 notes/wsa1-probes/kn1500_ic15_dump_defect.py [path/to/ic15]
"""

import os
import sys

DEFAULT = ("/home/fsanches/compartilhado/technics_roms/roms/kn1500/"
           "technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15")
BLOCK = 0x40000
BASE = 0xE00000


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.exists(path):
        print("not found: %s" % path)
        return 2
    d = open(path, "rb").read()
    print("image  : %s" % path)
    print("size   : %d bytes (%d blocks of %d)" % (len(d), len(d) // BLOCK, BLOCK))
    print()
    blk = [d[i * BLOCK:(i + 1) * BLOCK] for i in range(len(d) // BLOCK)]

    print("block    even-offset 0xFF   odd-offset 0xFF   verdict")
    damaged = []
    for i, b in enumerate(blk):
        e = sum(1 for j in range(0, len(b), 2) if b[j] == 0xFF)
        o = sum(1 for j in range(1, len(b), 2) if b[j] == 0xFF)
        half = len(b) // 2
        bad = (o == half)
        if bad:
            damaged.append(i)
        print("%06X   %6.1f%%            %6.1f%%           %s"
              % (BASE + i * BLOCK, 100.0 * e / half, 100.0 * o / half,
                 "ODD BYTES ALL BLANK" if bad else "ok"))
    print()

    ok = fail = 0
    for i in damaged:
        j = i + 2   # the block 512 KiB (two blocks) higher
        if j >= len(blk):
            print("[FAIL] block %06X has no +512K partner" % (BASE + i * BLOCK))
            fail += 1
            continue
        even_i = blk[i][0::2]
        odd_j = blk[j][1::2]
        same = sum(1 for a, b in zip(even_i, odd_j) if a == b)
        good = (same == len(even_i))
        print("[%s] block %06X even stream vs block %06X odd stream: %d/%d identical"
              % ("PASS" if good else "FAIL", BASE + i * BLOCK, BASE + j * BLOCK,
                 same, len(even_i)))
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)

    print()
    print("the descriptor the RAM test reads, as the driver maps the image today:")
    import struct
    off = 0xF38B24 - BASE
    for k in range(3):
        e = d[off + k * 10: off + (k + 1) * 10]
        s = struct.unpack("<I", e[0:4])[0]
        n = struct.unpack("<I", e[4:8])[0]
        print("  entry %d  start=%08X  length=%08X   <- 0xFF interleaved, not an address"
              % (k, s, n))

    print()
    print("%d PASS, %d FAIL" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
