#!/usr/bin/env python3
"""contexts.py -- pull the three constraint contexts verbatim from the ROM.
Scratchpad-only."""
import collections

from dspcorpus import (load, kernel_blob, distinct_images, fields, fmt,
                       KERNEL_ADDR, EPILOGUE_ADDR)

rom, names, imgs = load()
_c, _ka, KW = kernel_blob(rom, KERNEL_ADDR)
_c, _ea, EW = kernel_blob(rom, EPILOGUE_ADDR)
DIST = distinct_images(imgs)


def f31(h):
    return (h >> 1) & 7


def f98(h):
    return (h >> 8) & 3


def desc(w):
    hi, cl, ad, lo = fields(w)
    return ("%s  hi12[f98=%d f31=%d ST=%d ESC=%d EOB=%d]  lo12[u=%02X l=%02X]"
            % (fmt(w), f98(hi), f31(hi), (hi >> 4) & 1, (hi >> 11) & 1,
               1 if (hi & 0xC00) == 0x400 else 0, lo >> 5, lo & 0x1F))


print("=" * 78)
print("CONTEXT 1 -- THE ALL-PASS MOTIF  (reverb image, first core)")
print("=" * 78)
# find the reverb image (algo 16) and the gated reverb (algo 8)
rev = imgs[16]
gat = imgs[8]
CORE = [(0x880, 0x1, 0x2D4), (0x104, 0x2, 0x000), (0x000, 0x2, 0x419),
        (0x012, 0x2, 0x680), (0x880, 0x1, 0x655), (0x102, 0xA, 0x64B)]


def core_at(ws, i):
    if i + 6 > len(ws):
        return False
    for k, (hi, cl, lo) in enumerate(CORE):
        h, c, _a, l = fields(ws[i + k])
        if h != hi or c != cl or l != lo:
            return False
    return True


sites = [i for i in range(len(rev)) if core_at(rev, i)]
print("reverb image: %d words; core sites at %s" % (len(rev), sites))
i = sites[0]
for k in range(8):
    print("  slot%d w%-3d  %s" % (k, i + k, desc(rev[i + k])))

print("\nthe three ladder separators (reverb image):")
for at in (11, 59, 101):
    for k in range(5):
        print("  w%-3d  %s" % (at + k, desc(rev[at + k])))
    print()

print("=" * 78)
print("CONTEXT 2 -- THE LFO IDIOM, every occurrence in the corpus")
print("=" * 78)
LFO_W = {0x200}
hits = collections.Counter()
for ws, algos in DIST.items():
    for i, w in enumerate(ws):
        hi, cl, ad, lo = fields(w)
        if lo in LFO_W:
            hits[(hi, cl, ad, lo)] += 1
print("all words with lo12 = 0x200:")
for k, n in hits.most_common():
    hi, cl, ad, lo = k
    print("  x%-3d  %s" % (n, desc((hi << 24) | (cl << 20) | (ad << 12) | lo)))

print("\nthe LFO block in CHORUS (algo 1), words 0..12:")
for i in range(13):
    print("  w%-3d  %s" % (i, desc(imgs[1][i])))

print("\nevery image's opening LFO idiom `09x.A.dd.200`:")
for ws, algos in sorted(DIST.items(), key=lambda kv: kv[1][0]):
    idx = [i for i, w in enumerate(ws) if (w & 0xFFF) == 0x200]
    if not idx:
        continue
    nm = names.get(algos[0], "?")
    print("  algo %-3d %-24s at %s : %s"
          % (algos[0], nm[:24], idx, " ".join(fmt(ws[i]) for i in idx)))

print()
print("=" * 78)
print("CONTEXT 3 -- THE INPUT/MIX STAGE, kernel I-RAM 0..41")
print("=" * 78)
ptr = 0
for i, w in enumerate(KW[:42]):
    hi, cl, ad, lo = fields(w)
    cell = ""
    if (cl & 7) == 2:
        cell = "X%+d" % ptr
        ptr = ptr + (ad - 256 if ad > 127 else ad)
    print("  iw%-3d %s  %s" % (i, desc(w), cell))
print("  ... pointer leaves the mix block at X%+d" % ptr)

print()
print("epilogue I-RAM 60..82:")
for i, w in enumerate(EW):
    print("  w%-3d  %s" % (60 + i, desc(w)))
