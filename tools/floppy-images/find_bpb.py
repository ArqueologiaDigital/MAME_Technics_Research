#!/usr/bin/env python3
"""find_bpb.py -- where does an instrument ROM keep the boot sector its FORMAT writes?

Searches ROM images (interleaving the even/odd halves word by word when given as a pair) for a FAT12 BPB
for 1.44 MB HD (512 B/sector, 1 sector/cluster, 1 reserved, 2 FATs, 224 root entries, 2880
sectors, media F0, 9 sectors/FAT, 18 sectors/track, 2 heads) and for 720 KB DD, and prints the
bytes around each hit. The offset printed is the BPB's (byte 11 of the boot sector); the 32-byte
boot head the formatter copies starts 11 bytes earlier.
usage: find_bpb.py ROM [ROM ...]   or   find_bpb.py --pair EVEN ODD
"""
import sys

PATTERNS = {
    "1.44MB": bytes.fromhex("0002 01 0100 02 e000 400b f0 0900 1200 0200".replace(" ", "")),
    "720KB":  bytes.fromhex("0002 02 0100 02 7000 a005 f9 0300 0900 0200".replace(" ", "")),
}

def load(args):
    if args[0] == "--pair":
        ev, od = open(args[1], "rb").read(), open(args[2], "rb").read()
        out = bytearray()                      # 16-bit words, even ROM first (KN6000/KN7000)
        for i in range(0, len(ev), 2):
            out += ev[i:i + 2] + od[i:i + 2]
        return [(f"{args[1]}+{args[2]}", bytes(out))]
    return [(p, open(p, "rb").read()) for p in args]

for name, d in load(sys.argv[1:]):
    for label, pat in PATTERNS.items():
        i = d.find(pat)
        while i >= 0:
            s = max(0, i - 11)
            print(f"{name} {label} BPB at 0x{i:X}: {d[s:i + len(pat) + 26].hex(' ')}")
            print(f"    text: {d[s:i + len(pat) + 26]!r}")
            i = d.find(pat, i + 1)
