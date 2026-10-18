#!/usr/bin/env python3
"""compare_disks.py -- one row per disk image: the traits that show how a floppy was made.

Question it answers: across several real disks (official images, dumps, our builds), what do the
boot sector, label, directory dates, file layout and unused space look like, side by side? Columns:
OEM name; byte 0x25 (Windows NT / Linux "volume dirty" flag); 55 AA present; label (root
volume-label entry, or '-'); files; creation and access fields (all zero, or the values seen);
files contiguous in directory order from cluster 2; slack after EOF (byte values); free-space
bytes (most common two).

usage: python3 -I compare_disks.py IMAGE.img [IMAGE.img ...]   (prints a padded Markdown table)
"""
import collections
import struct
import sys

S = 512


def fat12(fat, n):
    v = struct.unpack_from("<H", fat, n * 3 // 2)[0]
    return v >> 4 if n & 1 else v & 0xFFF


def date(d):
    return f"{1980 + (d >> 9)}-{(d >> 5) & 15:02d}-{d & 31:02d}" if d else "0"


rows = [("image", "OEM", "0x25", "55AA", "label", "files", "created", "accessed", "contiguous", "slack", "free space")]
for p in sys.argv[1:]:
    img = open(p, "rb").read()
    bps, spc, res, nf, rde, tot, med, spf = struct.unpack_from("<HBHBHHBH", img, 11)
    root, data = res + nf * spf, res + nf * spf + rde * 32 // bps
    fat = img[res * S:(res + spf) * S]
    label, files, cre, acc, slack = "-", [], set(), set(), collections.Counter()
    owned, nxt, contiguous = set(), 2, True
    for i in range(rde):
        e = img[root * S + 32 * i:root * S + 32 * i + 32]
        if e[0] == 0:
            break
        if e[0] == 0xE5 or e[11] == 0x0F:
            continue
        if e[11] & 8:
            label = e[:11].decode("latin-1")
            continue
        ct, cd, ad, cl, size = struct.unpack_from("<HHH6xHI", e, 14)
        files.append(e[:11].decode("latin-1"))
        cre.add(date(cd) + (f" {ct:04X}" if ct else ""))
        acc.add(date(ad))
        chain, c = [], cl
        while 2 <= c < 0xFF8 and len(chain) < 3000:
            chain.append(c)
            c = fat12(fat, c)
        if chain != list(range(nxt, nxt + len(chain))):
            contiguous = False
        nxt += len(chain)
        owned.update(chain)
        body = b"".join(img[(data + c - 2) * S:(data + c - 1) * S] for c in chain)
        slack.update(body[size:])
    free = collections.Counter()
    for c in range(2, tot - data + 2):
        if not fat12(fat, c):
            free.update(img[(data + c - 2) * S:(data + c - 1) * S])
    fmt = lambda cnt: " ".join(f"{b:02X}x{n}" for b, n in cnt.most_common(2)) or "-"
    rows.append((p.rsplit("/", 1)[-1], img[3:11].decode("latin-1"), f"{img[0x25]:02X}",
                 "yes" if img[510:512] == b"\x55\xaa" else "no", label, str(len(files)),
                 ",".join(sorted(cre)), ",".join(sorted(acc)), "yes" if contiguous else "NO",
                 fmt(slack), fmt(free)))
w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
for k, r in enumerate(rows):
    print("| " + " | ".join(c.ljust(w[i]) for i, c in enumerate(r)) + " |")
    if k == 0:
        print("|" + "|".join("-" * (x + 2) for x in w) + "|")
