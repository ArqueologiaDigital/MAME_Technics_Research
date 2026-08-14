#!/usr/bin/env python3
"""Which waveform chunks that the instrument can actually PLAY get no period, and how long?

`detect_period()` returns a "P = N" fallback for 543 of IC307's 1495 chunks. Most of those
chunks are never selected, so the raw count is misleading. This tool counts only the ones the
firmware can reach, and splits them by length -- because length decides whether the fallback
is harmless or audible:

  * short chunk (<= 256 samples): the recording really IS about one cycle, and P=N is the only
    answer detect_period can give -- its own maxlag is ~N/3, so a period equal to N is
    unreachable by construction. Correct behaviour.
  * long chunk (>= 512 samples): P=N is a defect. update_pitch computes
    step = freq * N / 48000, so a 1496-sample chunk plays about 8x too fast at C4 and worse
    higher up -- the "extreme noise" kn5000_tonegen.cpp already blames on +040 = 0x505B/0x5046.

REFERENCE SET, and why it is not the TSV. This walks the 487 SET descriptors in the TABLE-DATA
ROM itself and reads the real +0x040 words, rather than the derived
notes/data/kn5000-multisample-sets.tsv zone column. The two differ: the TSV's zone column is a
narrower view, and using it made a first version of this check report ZERO referenced chunks
where the ROM walk finds 29. Always prefer the ROM.

    python3 tools/kn5000_referenced_fallbacks.py

Reference result (2026-08-14):

    page 0:  10 referenced fallbacks, 6 of them >= 512 samples (968..2016)
    page 1:  29 referenced fallbacks, 23 of them >= 512 samples (608..1816)
    page 2:  11 referenced fallbacks, 0 of them >= 512 (max 144)  <- all correctly aperiodic
    page 3:   0

So the audible target is 29 long referenced fallbacks on pages 0 and 1 -- not the 543 the raw
count suggests, and none of them on page 2. Full analysis: notes/FINDINGS-ic307-page2.md.
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_period_oracle as O  # noqa: E402

ROMS = "/home/fsanches/compartilhado/technics_roms/roms/kn5000"
EVEN = os.path.join(ROMS, "kn5000_table_data_rom_even.ic3")
ODD = os.path.join(ROMS, "kn5000_table_data_rom_odd.ic1")
BASE = 0x050000
IMG_ORIGIN = 0x020000
N_SETS = 487
SET_STRIDE = 15
SET_TABLE = 0x077914


def table_data():
    """The table-data ROM as the CPU sees it: 16-BIT WORDS interleaved, even half first.

    Byte-wise interleaving gives a different image (md5 55a92199... vs the correct
    57d838b3...) that parses into nonsense -- verified 2026-08-14.
    """
    with open(EVEN, "rb") as f:
        e = f.read()
    with open(ODD, "rb") as f:
        o = f.read()
    out = bytearray()
    for i in range(0, len(e), 2):
        out += e[i:i + 2] + o[i:i + 2]
    return bytes(out)


def referenced(img):
    """{page: {entry, ...}} for bank 1 (IC307), from the 487 SET descriptors."""
    u8 = lambda a: img[a - IMG_ORIGIN]
    u16 = lambda a: struct.unpack_from("<H", img, a - IMG_ORIGIN)[0]
    u32 = lambda a: struct.unpack_from("<I", img, a - IMG_ORIGIN)[0]
    ref = collections.defaultdict(set)
    for i in range(N_SETS):
        p = SET_TABLE + SET_STRIDE * i
        fl = u8(p)
        ptrA = u32(p + 1) + BASE
        ptrB = u32(p + 5) + BASE
        ptrC = u32(ptrA) + BASE
        stride = 6 if fl & 0x80 else 4
        slots = [u8(ptrC + k) for k in range(128)]
        emax = max(u8(ptrA + 4 + s) for s in range(max(slots) + 1))
        for E in range(emax + 1):
            w = u16(ptrB + stride * E)
            if (w >> 12) & 0x4:          # bank 1 = IC307
                ref[(w >> 12) & 3].add(w & 0xFFF)
    return ref


def main():
    rom = O.load_rom()
    pages = {p: O.page_dir(rom, p) for p in range(4)}
    ref = referenced(table_data())

    print("REFERENCED chunks with no detected period, by page")
    print("  (>=512 samples = audible defect; <=256 = correct, the chunk is one cycle)\n")
    grand_long = 0
    for p in range(4):
        d = pages[p]
        lens = [d[e][1] for e in sorted(ref.get(p, ()))
                if e < len(d) and O.detect_period(rom, *d[e]) == (d[e][1] << 16)]
        long_ = sorted(n for n in lens if n >= 512)
        grand_long += len(long_)
        span = f"{long_[0]}..{long_[-1]}" if long_ else "-"
        print(f"  page {p}: {len(lens):3d} referenced fallbacks, "
              f"{len(long_):3d} of them >= 512 samples  [{span}]")
    print(f"\n  audible target: {grand_long} long referenced fallbacks")

    # What the shipped bound change (N>256 -> return 0) actually reaches.
    flips = [(p, e, pages[p][e][1]) for p in range(4) for e in sorted(ref.get(p, ()))
             if e < len(pages[p])
             and O.detect_period(rom, *pages[p][e]) == (pages[p][e][1] << 16)
             and pages[p][e][1] > 256]
    print(f"  of which the N>256 bound converts to 'play as recorded': {len(flips)}")


if __name__ == "__main__":
    main()
