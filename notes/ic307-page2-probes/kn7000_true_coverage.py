#!/usr/bin/env python3
"""Recompute KN7000 SOURCE COVERAGE honestly, and show why tools/coverage_score.py
over-reports it by ~5x.

QUESTION ANSWERED: what share of kn7000_program.rom is emitted as real
re-assemblable MN10300 source, as opposed to `.incbin_range` passthrough?

THE BUG: coverage_score.py matches
    \\.incbin_range\\s+"([^"]+)",\\s*(0x[0-9A-Fa-f]+),\\s*(0x[0-9A-Fa-f]+)
which cannot match a directive whose START is an ARITHMETIC EXPRESSION.
src/program.s carries exactly one such directive:
    .incbin_range "baserom/kn7000_program.rom", 0x32573C + 0x800, 0x3B8000
so 598,212 raw passthrough bytes are invisible to the tool and are counted as
"real assembly source".

Reported : 18.03%  (749,584 / 4,157,185)
True     :  3.64%  (151,372 / 4,157,185)

Cross-check that settles it without reading the regex at all: src/program.s has
59,008 instruction lines. 749,584 bytes / 59,008 = 12.7 bytes per MN10300
instruction, which is impossible (max encoding is 7). 151,372 / 59,008 = 2.57,
which is right.

Run from the kn7000_disassembly checkout:  python3 kn7000_true_coverage.py
"""
import os
import re
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/home/fsanches/compartilhado/kn7000_disassembly"
prog_s = os.path.join(REPO, "src", "program.s")
table_s = os.path.join(REPO, "src", "table.s")
PROG_SIZE = 0x3F6F01   # 4,157,185
TABLE_SIZE = 0x3E94D4  # 4,101,332

LOOSE = re.compile(r'\.incbin_range\s+"([^"]+)"\s*,\s*([^\n#]+)')
STRICT = re.compile(r'\.incbin_range\s+"([^"]+)",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)')


def measure(path, total):
    src = open(path).read()
    loose = LOOSE.findall(src)
    strict = STRICT.findall(src)
    raw = 0
    missed = []
    for f, args in loose:
        a, b = [x.strip() for x in args.split(",")]
        n = eval(b) - eval(a)          # noqa: S307 - fixed local input
        raw += n
        if not (re.fullmatch(r"0x[0-9A-Fa-f]+", a) and re.fullmatch(r"0x[0-9A-Fa-f]+", b)):
            missed.append((f, a, b, n))
    return src, loose, strict, raw, missed, total


for path, total, label in ((prog_s, PROG_SIZE, "program"), (table_s, TABLE_SIZE, "table")):
    src, loose, strict, raw, missed, total = measure(path, total)
    insn = sum(1 for l in src.split("\n")
               if re.match(r"^\s+[a-z]{2,7}(\.[bwl])?\s", l) and not l.strip().startswith((".", "#")))
    print(f"== {label}.rom ==")
    print(f"   directives: {len(loose)} total, {len(strict)} visible to coverage_score.py")
    for f, a, b, n in missed:
        print(f"   MISSED by the tool's regex: {a} .. {b} = {n:,d} bytes")
    print(f"   raw passthrough : {raw:,d}")
    print(f"   REAL source     : {total - raw:,d}  = {100 * (total - raw) / total:.2f}%")
    print(f"   instruction lines {insn:,d} -> {(total - raw) / insn if insn else 0:.2f} bytes/insn"
          f"   (MN10300 encodings are 1..7 bytes; anything >7 means the number is wrong)")
