#!/usr/bin/env python3
"""lfo.py -- the LFO triple in every image, with the pointer walk, and prog00.
Scratchpad-only."""
import collections

from dspcorpus import (load, kernel_blob, distinct_images, fields, fmt,
                       KERNEL_ADDR, EPILOGUE_ADDR)

rom, names, imgs = load()
_c, _ka, KW = kernel_blob(rom, KERNEL_ADDR)
_c, _ea, EW = kernel_blob(rom, EPILOGUE_ADDR)
DIST = distinct_images(imgs)


def walk(ws):
    """cell touched by each word, relative to the image entry pointer."""
    ptr, out = 0, []
    for w in ws:
        hi, cl, ad, lo = fields(w)
        if (cl & 7) == 2:
            out.append(ptr)
            ptr += (ad - 256 if ad > 127 else ad)
        else:
            out.append(None)
    return out


def cur(ws):
    """C-RAM offset consumed by each class-A word."""
    out, k = {}, 0
    for i, w in enumerate(ws):
        if ((w >> 20) & 0xF) == 0xA:
            out[i] = k
            k += 1
    return out


print("=" * 78)
print("L1.  THE LFO TRIPLE -- do both 0x200 words address the SAME CELL?")
print("=" * 78)
for algo in sorted(imgs):
    ws = imgs[algo]
    idx = [i for i, w in enumerate(ws) if (w & 0xFFF) == 0x200]
    if not idx:
        continue
    cells = walk(ws)
    cc = cur(ws)
    nm = names.get(algo, "?")
    print("\n  algo %-3d %s" % (algo, nm))
    lo_ = min(idx) - 1
    hi_ = max(idx) + 2
    for i in range(max(0, lo_), min(len(ws), hi_)):
        mark = "  <<<" if (ws[i] & 0xFFF) == 0x200 else ""
        cellstr = ("cell %+4d" % cells[i]) if cells[i] is not None else "cell   --"
        curstr = ("C-RAM[+%d]" % cc[i]) if i in cc else ""
        print("     w%-3d %-14s %s %-10s%s" % (i, fmt(ws[i]), cellstr, curstr, mark))
    if len(idx) >= 2:
        a, b = idx[0], idx[1]
        print("     -> pair cells: %s vs %s  %s"
              % (cells[a], cells[b], "SAME" if cells[a] == cells[b] else "DIFFERENT"))

print()
print("=" * 78)
print("L2.  Cursor offsets of the LFO pairs (which C-RAM cells they consume)")
print("=" * 78)
for algo in (1, 2, 4, 5, 6, 48, 50, 54, 56, 36):
    if algo not in imgs:
        continue
    ws = imgs[algo]
    cc = cur(ws)
    idx = [i for i, w in enumerate(ws) if (w & 0xFFF) == 0x200]
    print("  algo %-3d %-22s : %s"
          % (algo, names.get(algo, "?")[:22],
             " ".join("w%d->C-RAM[+%d]" % (i, cc[i]) for i in idx)))

print()
print("=" * 78)
print("L3.  prog00 NO OPERATION -- the body that isolates kernel+epilogue")
print("=" * 78)
ws = imgs[0]
cells = walk(ws)
cc = cur(ws)
print("  %d words" % len(ws))
for i, w in enumerate(ws):
    cellstr = ("cell %+4d" % cells[i]) if cells[i] is not None else "cell   --"
    curstr = ("C-RAM[+%d]" % cc[i]) if i in cc else ""
    print("    w%-3d %-14s %s %s" % (i, fmt(ws[i]), cellstr, curstr))
