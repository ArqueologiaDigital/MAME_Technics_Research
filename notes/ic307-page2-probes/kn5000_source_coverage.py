#!/usr/bin/env python3
"""kn5000_source_coverage.py -- the KN5000 analogue of kn7000's coverage_score.py.

QUESTION ANSWERED: for each KN5000 ROM, how many bytes enter the byte-exact build
as REAL source (assembly, typed data, or C compiled by clang -target tlcs900) and
how many are handed back verbatim through `.incbin`?

Byte-match is 100.00% on all 15 sections and always will be -- it says nothing
about understanding. This does.

Three classes of `.incbin` byte are distinguished, because they are NOT equal:

  * generated/ + a Makefile clang rule  -> HONEST (C source recompiled byte-exact)
  * generated/ written by scripts/build/extract_v7_bins.py -> ROM SLICE at build
    time. The v7 tree rebuilds byte-perfectly partly because the build copies the
    v7 ROM into its own "source". Measured separately.
  * a committed .bin with no rule       -> raw blob (documented or not)

Run from the kn5000-roms-disasm checkout:
    python3 kn5000_source_coverage.py
"""
import glob
import os
import re
import subprocess
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/home/fsanches/compartilhado/kn5000-roms-disasm"
os.chdir(REPO)

ROMS = {
    "v10/maincpu": ("maincpu v10", 2097152),
    "v9/maincpu": ("maincpu v9", 2097152),
    "v7/maincpu": ("maincpu v7", 2097152),
    "v142/subcpu": ("subcpu payload v142", 196608),
    "subcpu/boot": ("subcpu boot (IC30)", 131072),
    "table_data": ("table data", 2097152),
    "custom_data": ("custom data (IC19)", 1048576),
    "hdae5000": ("HD-AE5000", 524288),
}
INC = re.compile(r'\.incbin\s+"([^"]+)"(?:\s*,\s*([0-9a-fA-Fx]+)\s*(?:,\s*([0-9a-fA-Fx]+))?)?')

print(f"{'component':22s} {'ROM':>9s} {'incbin':>9s} {'of which C':>10s} {'source':>9s}  source%")
for root, (label, total) in ROMS.items():
    inc = gen = 0
    for f in glob.glob(root + "/**/*.s", recursive=True):
        txt = open(f, encoding="latin-1").read()
        for path, off, ln in INC.findall(txt):
            real = next((c for c in (os.path.join(os.path.dirname(f), path),
                                     os.path.join(root, path), path) if os.path.exists(c)), None)
            if not real:
                continue
            fsz = os.path.getsize(real)
            size = int(ln, 0) if ln else (fsz - int(off, 0) if off else fsz)
            inc += size
            if "generated/" in path:
                gen += size
    print(f"{label:22s} {total:9,d} {inc:9,d} {gen:10,d} {total - inc:9,d}  "
          f"{100 * (total - inc) / total:5.1f}%")

# --- the v7 circularity, measured ------------------------------------------
# extract_v7_bins.py stage 1 overwrites a C-compiled bin with a raw slice of the
# v7 ROM whenever the block at the v9 label address is >50% similar.
LLVM_NM = "/home/fsanches/compartilhado/llvm-project/build/bin/llvm-nm"
ROM_BASE = 0xE00000
try:
    v7rom = open("original_ROMs/kn5000_v7_program.rom", "rb").read()

    def syms(p):
        d = {}
        for line in subprocess.run([LLVM_NM, "--no-sort", p], capture_output=True,
                                   text=True).stdout.split("\n"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    d[parts[2]] = int(parts[0], 16)
                except ValueError:
                    pass
        return d

    v7s = syms("rebuilt_ROMs/kn5000_v7_program.llvm.elf")
    v9s = syms("rebuilt_ROMs/kn5000_v9_program.llvm.elf")
    incmap = {}
    for fp in sorted(glob.glob("v9/maincpu/**/*.s", recursive=True)):
        last = None
        for line in open(fp, "rb").readlines():
            s = line.strip()
            m = re.match(rb"^(\w+):", s)
            if m and not s.startswith(b".") and not s.startswith(b";"):
                last = m.group(1).decode("latin-1")
            if b".incbin" in s and b"generated/" in s:
                i1 = s.find(b'"') + 1
                rel = s[i1:s.find(b'"', i1)].decode("latin-1")
                a = v7s.get(last, v9s.get(last)) if last else None
                if a is not None:
                    incmap[(last, rel)] = (a, "v9/maincpu/" + rel)
    ov = ovb = keep = keepb = differ = differb = 0
    for (lab, _), (addr, v9p) in incmap.items():
        if not os.path.exists(v9p):
            continue
        n = os.path.getsize(v9p)
        d7 = v7rom[addr - ROM_BASE: addr - ROM_BASE + n]
        d9 = open(v9p, "rb").read()
        pct = sum(1 for a, b in zip(d7, d9) if a == b) / n if n else 0
        if pct > 0.5:
            ov += 1
            ovb += n
            if d7 != d9:
                differ += 1
                differb += n
        else:
            keep += 1
            keepb += n
    print(f"\nextract_v7_bins.py: overwrites {ov} C-compiled bins with raw v7 ROM slices "
          f"({ovb:,d} B); keeps C output for {keep} ({keepb:,d} B)")
    print(f"  of the overwritten, {differ} files / {differb:,d} B genuinely DIFFER from the "
          f"C output -- i.e. that many bytes of the v7 ROM are reproduced by NO source.")
except FileNotFoundError as e:
    print("\n(v7 circularity check skipped:", e, ")")
