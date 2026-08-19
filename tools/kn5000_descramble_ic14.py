#!/usr/bin/env python3
"""kn5000_descramble_ic14.py -- turn the transposed IC14 dump into the corrected one.

QUESTION ANSWERED: our dump of the KN5000 rhythm data ROM (IC14) has address lines A19 and
A21 transposed. Upstream MAME carries the CORRECTED dump, CRC(aa4917ce)
SHA1(fef7f1927935d8fdada2afbdbfac29aac56e1c3c), which this machine does not have a copy of.
Is the corrected dump simply this file de-scrambled? If so we can produce it locally and
verify it against the published hash, rather than needing the physical chip re-read.

    python3 tools/kn5000_descramble_ic14.py in.ic14 out.ic14

The permutation is the one the private overlay applies at load time with ROM_CONTINUE:
file block 0,1,2,3,4,5,6,7 -> 0x000000, 0x200000, 0x100000, 0x300000,
                              0x080000, 0x280000, 0x180000, 0x380000
so the output is the input's 512 KiB blocks in the order 0,4,2,6,1,5,3,7.

PASS: the output's SHA1 is fef7f1927935d8fdada2afbdbfac29aac56e1c3c. That both gives us a
usable ROM and proves the upstream record is this data, correctly ordered.
"""
import hashlib, sys

BLOCK = 0x080000
ORDER = [0, 4, 2, 6, 1, 5, 3, 7]
EXPECT = "fef7f1927935d8fdada2afbdbfac29aac56e1c3c"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    data = open(src, "rb").read()
    if len(data) != BLOCK * 8:
        sys.exit(f"{src}: expected {BLOCK * 8} bytes, got {len(data)}")

    blocks = [data[i * BLOCK:(i + 1) * BLOCK] for i in range(8)]
    out = b"".join(blocks[i] for i in ORDER)
    open(dst, "wb").write(out)

    got = hashlib.sha1(out).hexdigest()
    print(f"in  sha1 {hashlib.sha1(data).hexdigest()}")
    print(f"out sha1 {got}")
    if got == EXPECT:
        print("PASS: matches the corrected IC14 dump recorded upstream")
        return 0
    print(f"FAIL: expected {EXPECT}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
