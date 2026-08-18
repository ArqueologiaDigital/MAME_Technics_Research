#!/usr/bin/env python3
"""Build MAME romset zips for the ROM-record PR, from our own ROM collection.

WHY THIS IS NOT A ONE-LINER: the PR declares MAME per-chip filenames
(kn7000_program_even.ic17) while our collection stores the same bytes under payload names
(kn7000_program_even.rom). So the files CANNOT be matched by name -- they are matched by
CRC32, and written into the zip under the name the driver expects.

    python3 tools/make_pr_romsets.py -o /tmp/technics-romsets.zip

Produces one outer zip containing one romset zip per machine, ready to drop into a MAME
rompath. NO_DUMP entries are skipped (they have no data by definition) and reported.

⚠ The contents are copyrighted Technics firmware. This is a local convenience for testing a
  driver against real dumps; do not publish the output.
"""
import argparse, glob, hashlib, io, os, re, sys, zipfile, zlib

DRIVER = "/home/fsanches/compartilhado/mame-pr-romrec/src/mame/matsushita/kn7000.cpp"
SEARCH = ["/home/fsanches/compartilhado/technics_roms/roms",
          "/home/fsanches/compartilhado/kn7000-emulator/roms"]


def index_by_crc(roots):
    idx = {}
    for r in roots:
        for p in glob.glob(f"{r}/**/*", recursive=True):
            if not os.path.isfile(p):
                continue
            try:
                d = open(p, "rb").read()
            except OSError:
                continue
            if d:
                idx.setdefault(f"{zlib.crc32(d) & 0xffffffff:08x}", p)
    return idx


def parse(driver):
    """-> {set_name: [(filename, crc, sha1), ...]}, plus the NO_DUMP count.

    ⚠ Macros must be expanded. kn7000.cpp defines KN2400_ROM_COMMON and both kn2400 and kn2600
    invoke it, and the macro BODY sits between kn6500's ROM_END and kn2400's ROM_START. A naive
    line scanner therefore files the shared entries under kn6500 and leaves kn2400/kn2600 empty
    -- which is exactly what the first version of this script did.
    """
    src = open(driver).read()

    # collect `#define NAME \` ... continued-line macro bodies, then drop them from the stream
    macros, lines, i = {}, src.replace("\\\n", "\x00").splitlines(), 0
    kept = []
    for line in lines:
        m = re.match(r"\s*#define\s+(\w+)\s*\x00(.*)$", line)
        if m:
            macros[m.group(1)] = m.group(2).replace("\x00", "\n")
            continue
        kept.append(line.replace("\x00", "\n"))

    def entries_of(text):
        out, nd = [], 0
        for ln in text.splitlines():
            if "NO_DUMP" in ln:
                nd += 1
                continue
            m = re.search(r'ROM[X]?_LOAD\w*\(\s*"([^"]+)"[^)]*?CRC\(([0-9a-fA-F]+)\)\s*SHA1\(([0-9a-fA-F]+)\)', ln)
            if m:
                out.append((m.group(1), m.group(2).lower(), m.group(3).lower()))
        return out, nd

    sets, cur, nodump = {}, None, 0
    for line in kept:
        m = re.search(r"ROM_START\(\s*(\w+)\s*\)", line)
        if m:
            cur = m.group(1)
            sets[cur] = []
            continue
        if re.search(r"ROM_END", line):
            cur = None
            continue
        if cur is None:
            continue
        stripped = line.strip()
        if stripped in macros:                      # a bare macro invocation
            e, nd = entries_of(macros[stripped])
            sets[cur] += e
            nodump += nd
            continue
        e, nd = entries_of(line)
        sets[cur] += e
        nodump += nd
    return sets, nodump


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--driver", default=DRIVER)
    args = ap.parse_args()

    sets, nodump = parse(args.driver)
    idx = index_by_crc(SEARCH)
    print(f"{sum(len(v) for v in sets.values())} hashed entries across {len(sets)} sets; "
          f"{nodump} NO_DUMP entries skipped")

    missing, written = [], 0
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as outer:
        for name, entries in sets.items():
            if not entries:
                continue
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as inner:
                for fn, crc, sha in entries:
                    src = idx.get(crc)
                    if not src:
                        missing.append((name, fn, crc))
                        continue
                    d = open(src, "rb").read()
                    got = hashlib.sha1(d).hexdigest()
                    if got != sha:
                        print(f"  ⚠ {name}/{fn}: CRC matched but SHA1 did NOT ({got} != {sha})")
                        missing.append((name, fn, crc))
                        continue
                    inner.writestr(fn, d)
                    written += 1
            outer.writestr(f"{name}.zip", buf.getvalue())
            print(f"  {name}.zip: {len(entries) - sum(1 for m in missing if m[0] == name)} file(s)")

    print(f"\nwrote {args.out}: {written} ROM file(s)")
    if missing:
        print("MISSING (declared but no matching content found):")
        for s, f, c in missing:
            print(f"  {s}/{f}  crc {c}")
        return 1
    print("every hashed entry resolved and SHA1-verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
