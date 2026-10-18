#!/usr/bin/env python3
"""dissect_disk.py -- everything a real FAT12 floppy image records about how it was written.

Question it answers: what does a disk somebody actually made look like, beyond its files? For a
raw 1.44 MB image it prints the boot sector bytes that differ from zero after the 32-byte head,
every root-directory slot (live, deleted, long-name, volume label) with all its date fields
decoded, each live file's cluster chain as runs (fragmentation shows as several runs), the
clusters marked used in the FAT that no file owns, and the fill of the free clusters. With
--zip INSTALLER it also compares each file's content with the archive member of the same name.

usage: python3 -I dissect_disk.py IMAGE.img [--zip INSTALLER.exe]
"""
import collections
import struct
import sys
import zipfile

img = open(sys.argv[1], "rb").read()
zf = zipfile.ZipFile(sys.argv[sys.argv.index("--zip") + 1]) if "--zip" in sys.argv else None
S = 512
bps, spc, res, nf, rde, tot, med, spf = struct.unpack_from("<HBHBHHBH", img, 11)
root, data = res + nf * spf, res + nf * spf + rde * 32 // bps
fat = img[res * S:(res + spf) * S]


def fat12(n):
    v = struct.unpack_from("<H", fat, n * 3 // 2)[0]
    return v >> 4 if n & 1 else v & 0xFFF


def dt(t, d):
    if not d:
        return "0"
    return (f"{1980 + (d >> 9):04d}-{(d >> 5) & 15:02d}-{d & 31:02d} "
            f"{t >> 11:02d}:{(t >> 5) & 63:02d}:{(t & 31) * 2:02d}")


print(f"boot head: {img[:32].hex(' ')}")
extra = [(i, img[i]) for i in range(32, 512) if img[i]]
print(f"boot bytes after the head that are not 0: {[(hex(i), hex(v)) for i, v in extra]}")
print(f"FAT copies identical: {img[res * S:(res + spf) * S] == img[(res + spf) * S:root * S]}")
owned = set()
for i in range(rde):
    e = img[root * S + 32 * i:root * S + 32 * i + 32]
    if e[0] == 0:
        print(f"slot {i}: end of directory")
        break
    attr = e[11]
    kind = "LFN" if attr == 0x0F else "deleted" if e[0] == 0xE5 else "label" if attr & 8 else "file"
    ct, cd, ad, wt, wd, cl, size = struct.unpack_from("<HHHxxHHHI", e, 14)
    print(f"slot {i}: {kind:7s} {e[:11]!r} attr {attr:02X} ntres {e[12]:02X} "
          f"created {dt(ct, cd)} (+{e[13]}/100 s) accessed {dt(0, ad)} written {dt(wt, wd)} "
          f"cluster {cl} size {size}")
    if kind != "file":
        continue
    chain, c = [], cl
    while 2 <= c < 0xFF8 and len(chain) < 3000:
        chain.append(c)
        c = fat12(c)
    owned.update(chain)
    runs, start = [], chain[0] if chain else None
    for a, b in zip(chain, chain[1:] + [None]):
        if b != a + 1:
            runs.append(f"{start}-{a}" if a != start else f"{a}")
            start = b
    body = b"".join(img[(data + c - 2) * S:(data + c - 1) * S] for c in chain)
    note = ""
    if zf:
        name = e[:8].decode().rstrip() + ("." + e[8:11].decode().rstrip() if e[8:11].strip() else "")
        try:
            note = "content == archive" if body[:size] == zf.read(name) else "content DIFFERS from archive"
        except KeyError:
            note = "not in archive"
        tail = body[size:]
        note += f"; slack after EOF: {dict(collections.Counter(tail).most_common(3))}"
    print(f"         chain {len(chain)} clusters in runs {runs}; end mark {c:03X}; {note}")
used = {c for c in range(2, tot - data + 2) if fat12(c)}
print(f"clusters used in the FAT but owned by no file: {sorted(used - owned)[:40]}"
      f"{' ...' if len(used - owned) > 40 else ''} ({len(used - owned)})")
free = [c for c in range(2, tot - data + 2) if c not in used]
fill = collections.Counter(b for c in free for b in img[(data + c - 2) * S:(data + c - 1) * S])
print(f"free clusters: {len(free)}, their bytes: {dict(fill.most_common(4))}")
