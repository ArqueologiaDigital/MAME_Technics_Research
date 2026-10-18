#!/usr/bin/env python3
"""build_all.py -- rebuild every software-list floppy in manifest.tsv on its instrument's own disk.

Question it answers: what are the new images, zips and software-list hashes for kn5000_flop,
kn6000_flop and kn7000_flop when each entry is built by technics_floppy.py on the blank disk its
own instrument formatted (base/<model>_formatted.img.gz), labelled with the entry's name?

For each manifest row with an installer it
  1. builds OUT/roms/<list>/<entry>.img with technics_floppy.py,
  2. runs verify_floppy.py on it (static: layout, names, dates, contents; no emulator) and stops
     on the first failure,
  3. checks the payload against the image now in the software list (ROMSETS/<list>/<entry>.zip):
     same file names and bytes, in whatever layout the old image had, so only the layout changes,
  4. writes OUT/roms/<list>/<entry>.zip (the .img alone, fixed timestamp, so the zip is
     reproducible too),
and then writes OUT/hash/<list>.xml: MAME's current list (MAME/hash/<list>.xml) with only the
crc and sha1 of the rebuilt entries changed. OUT/summary.tsv lists old and new hashes per entry.
Rows without an installer (idd5000) are reported and skipped.

usage: python3 -I build_all.py OUT [--mirror DIR] [--romsets DIR] [--mame DIR]
  defaults: ~/compartilhado/ca-software-mirror/files, ~/compartilhado/technics_romsets,
            ~/compartilhado/mame
"""
import gzip
import hashlib
import os
import re
import struct
import subprocess
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
H = os.path.expanduser("~/compartilhado")


def opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


OUT = sys.argv[1]
MIRROR = opt("--mirror", f"{H}/ca-software-mirror/files")
ROMSETS = opt("--romsets", f"{H}/technics_romsets")
MAME = opt("--mame", f"{H}/mame")


def files_of(img):
    """{NAME.EXT: sha1} of the root-directory files of a FAT12 image, read through its BPB."""
    bps, spc, res, nfats, rde, _tot, _media, spf = struct.unpack_from("<HBHBHHBH", img, 11)
    fat = img[res * bps:(res + spf) * bps]
    root = (res + nfats * spf) * bps
    data = root + rde * 32
    out = {}
    for i in range(rde):
        e = img[root + 32 * i:root + 32 * i + 32]
        if e[0] == 0:
            break
        if e[0] == 0xE5 or e[11] & 0x18:
            continue
        name = e[0:8].decode("latin-1").rstrip() + "." + e[8:11].decode("latin-1").rstrip()
        cl, size = struct.unpack_from("<HI", e, 26)
        buf = bytearray()
        while 2 <= cl < 0xFF8 and len(buf) < size:
            o = data + (cl - 2) * spc * bps
            buf += img[o:o + spc * bps]
            v = struct.unpack_from("<H", fat, cl * 3 // 2)[0]
            cl = v >> 4 if cl & 1 else v & 0xFFF
        out[name.rstrip(".")] = hashlib.sha1(bytes(buf[:size])).hexdigest()
    return out


def run(*args):
    r = subprocess.run([sys.executable, "-I", *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(HERE, "manifest.tsv"))
        if l.strip() and not l.startswith("#")]
os.makedirs(f"{OUT}/base", exist_ok=True)
for base in sorted({r[3] for r in rows}):
    with gzip.open(os.path.join(HERE, "base", base + ".gz")) as src, open(f"{OUT}/base/{base}", "wb") as dst:
        dst.write(src.read())

summary = [("list", "entry", "files", "clusters", "old crc", "new crc", "new sha1", "payload")]
new_hash = {}
for lst, entry, exe, base in rows:
    if exe == "-":
        print(f"SKIP {lst} {entry}: no installer")
        summary.append((lst, entry, "-", "-", "-", "-", "-", "not rebuilt (no installer)"))
        continue
    d = f"{OUT}/roms/{lst}"
    os.makedirs(d, exist_ok=True)
    img_path, base_path, exe_path = f"{d}/{entry}.img", f"{OUT}/base/{base}", f"{MIRROR}/{exe}"
    rc, out = run(os.path.join(HERE, "technics_floppy.py"), base_path, exe_path, img_path, "--label", entry)
    if rc:
        sys.exit(f"build failed for {entry}:\n{out}")
    nfiles, used = re.search(r"(\d+) files, (\d+) of", out).groups()
    rc, out = run(os.path.join(HERE, "verify_floppy.py"), base_path, exe_path, img_path, entry)
    if rc:
        sys.exit(f"verify failed for {entry}:\n{out}")
    img = open(img_path, "rb").read()
    old_zip = f"{ROMSETS}/{lst}/{entry}.zip"
    old = zipfile.ZipFile(old_zip).read(f"{entry}.img")
    same = files_of(old) == files_of(img)
    if not same:
        sys.exit(f"payload differs from the listed image for {entry}: "
                 f"{sorted(set(files_of(old).items()) ^ set(files_of(img).items()))}")
    with zipfile.ZipFile(f"{d}/{entry}.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        info = zipfile.ZipInfo(f"{entry}.img", date_time=(2026, 10, 18, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, img)
    os.remove(img_path)
    crc = f"{zlib.crc32(img) & 0xFFFFFFFF:08x}"
    sha = hashlib.sha1(img).hexdigest()
    new_hash[(lst, entry)] = (crc, sha)
    summary.append((lst, entry, nfiles, used, f"{zlib.crc32(old) & 0xFFFFFFFF:08x}", crc, sha,
                    "same files"))
    print(f"OK   {lst} {entry}: {nfiles} files, {used} clusters, crc {crc}")

os.makedirs(f"{OUT}/hash", exist_ok=True)
for lst in sorted({r[0] for r in rows}):
    text = open(f"{MAME}/hash/{lst}.xml").read()
    cur = None
    lines = []
    for line in text.splitlines(keepends=True):
        m = re.search(r'<software name="([^"]+)"', line)
        if m:
            cur = m.group(1)
        if "<rom " in line and (lst, cur) in new_hash:
            crc, sha = new_hash[(lst, cur)]
            line = re.sub(r'crc="[0-9a-f]{8}"', f'crc="{crc}"', line)
            line = re.sub(r'sha1="[0-9a-f]{40}"', f'sha1="{sha}"', line)
        lines.append(line)
    open(f"{OUT}/hash/{lst}.xml", "w").write("".join(lines))

with open(f"{OUT}/summary.tsv", "w") as f:
    for r in summary:
        f.write("\t".join(str(c) for c in r) + "\n")
print(f"{len(new_hash)} images rebuilt; hash XMLs in {OUT}/hash; summary in {OUT}/summary.tsv")
