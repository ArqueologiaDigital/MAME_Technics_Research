#!/usr/bin/env python3
"""verify_floppy.py -- is IMAGE exactly "BASE plus the installer's files", and nothing else?

Question it answers: does a built software-list disk hold every member of its installer
byte-for-byte, with the name, attributes and date the extractor would give it, laid out the way
DOS writes a fresh disk, while every byte the files do not own is still the instrument's
formatted disk? Written separately from technics_floppy.py (no shared code), so a builder bug
is not repeated by its own check.

Checks, each printed PASS/FAIL:
  boot     sector 0 identical to BASE
  fats     both FAT copies identical; entries 0-1 F0 FF FF; each file's chain contiguous and
           ending in an end-of-chain mark; no allocated cluster outside the files
  label    the root's volume label is LABEL padded with '_' (or BASE's label when not given)
  files    root entries 1..n are the installer members in archive order: 8.3 name, attribute
           (archive's DOS byte & 0x27), write date/time, size, content
  rest     every other root entry 0x00; every unused data sector identical to BASE

usage: python3 -I verify_floppy.py BASE.img INSTALLER.exe IMAGE.img [LABEL]
Exit status 0 when every check passes.
"""
import struct
import sys
import zipfile

base, exe, path = sys.argv[1:4]
label = sys.argv[4] if len(sys.argv) > 4 else None
B = open(base, "rb").read()
I = open(path, "rb").read()
S = 512
ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'} {name}{': ' + detail if detail else ''}")


check("size", len(I) == len(B) == 2880 * S, f"{len(I)} bytes")
check("boot", I[:S] == B[:S])
fat1, fat2 = I[S:10 * S], I[10 * S:19 * S]
check("fats identical", fat1 == fat2)
check("fat head F0 FF FF", fat1[:3] == b"\xf0\xff\xff")


def fat(n):
    v = fat1[n * 3 // 2] | fat1[n * 3 // 2 + 1] << 8
    return v >> 4 if n & 1 else v & 0xFFF


root = I[19 * S:33 * S]
ents = [root[32 * i:32 * i + 32] for i in range(224)]
want_label = (label.upper().ljust(11, "_").encode() if label else B[19 * S:19 * S + 11])
check("label", ents[0][:11] == want_label and ents[0][11] == 0x28, repr(ents[0][:11]))
check("label entry rest", ents[0][12:] == B[19 * S + 12:19 * S + 32])

members = zipfile.ZipFile(exe).infolist()
used = set()
nxt = 2
for k, info in enumerate(members, start=1):
    e = ents[k]
    name = info.filename.upper()
    stem, _, ext = name.rpartition(".") if "." in name else (name, "", "")
    want = stem.ljust(8).encode() + ext.ljust(3).encode()
    y, mo, d, h, mi, s = info.date_time
    wt, wd = (h << 11) | (mi << 5) | (s // 2), ((y - 1980) << 9) | (mo << 5) | d
    t, dt, cl, size = struct.unpack_from("<HHHI", e, 22)
    data = zipfile.ZipFile(exe).read(info)
    chain = []
    c = cl
    while 2 <= c < 0xFF8 and len(chain) <= 2880:
        chain.append(c)
        c = fat(c)
    content = b"".join(I[(33 + c - 2) * S:(33 + c - 1) * S] for c in chain)[:size]
    good = (e[:11] == want and e[11] == info.external_attr & 0x27 and e[12:22] == bytes(10)
            and (t, dt) == (wt, wd) and size == len(data) and content == data
            and c >= 0xFF8 and chain == list(range(nxt, nxt + len(chain))))
    check(f"file {k:2d} {info.filename}", good,
          f"{len(chain)} clusters from {cl}, attr {e[11]:02X}, {size} bytes")
    nxt += len(chain)
    used.update(chain)
check("no other root entries", all(e == bytes(32) for e in ents[len(members) + 1:]))
alloc = {c for c in range(2, 2849) if fat(c)}
check("no stray clusters", alloc == used, f"{len(used)} clusters in use")
free_same = all(I[(33 + c - 2) * S:(33 + c - 1) * S] == B[(33 + c - 2) * S:(33 + c - 1) * S]
                for c in range(2, 2849) if c not in used)
check("free sectors untouched", free_same)
sys.exit(0 if ok else 1)
