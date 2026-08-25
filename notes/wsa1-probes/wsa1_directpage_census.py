#!/usr/bin/env python3
"""wsa1_directpage_census.py -- which WSA1 direct-page byte behaves like a MODE FLAG?

QUESTION IT ANSWERS
    "Is there a variant byte -- written once at boot, read from many places --
    that would let one firmware serve both the SX-WSA1 keyboard and the
    SX-WSA1R rack?"

    The classic shape is: RESET reads a strap, stores 0/1 into a RAM byte, and
    dozens of later sites branch on that byte.  This script measures that shape
    over the WHOLE direct page instead of asserting it for one address, so a
    candidate can be graded against its peers.

WHY THE DIRECT PAGE
    TLCS-900's 8-bit-direct form `(n)` reaches 0x000000-0x0000FF.  0x00-0x7F is
    the TMP95C061 SFR block; 0x80-0xFF is the cheapest RAM on the machine, which
    is where a compiler-less firmware puts its hottest globals.  A mode flag
    tested on many paths is exactly the thing that earns a slot there.

ENCODINGS  (all re-checked against MAME unidasm; see wsa1_port_strap_census.py)
    08 <a> <imm>   ld (a),#imm8              WRITE, immediate -- the "set once" form
    f0 <a> 40+r    ld (a),R                  WRITE
    f0 <a> b0+n    res n,(a)                 WRITE (rmw)
    f0 <a> b8+n    set n,(a)                 WRITE (rmw)
    c0 <a> 20+r    ld R8,(a)                 READ
    c0 <a> 3f imm  cp (a),#imm8              READ -- the "test it" form
    c0 <a> f0+r    cp R8,(a)                 READ
    c0 <a> c0/d0/e0 +r  and/xor/or R8,(a)    READ
    f0 <a> c8+n    bit n,(a)                 READ
    f0 <a> a0+n    stcf n,(a)                READ

SCORING
    A candidate mode flag wants: few IMMEDIATE writes (ideally 1-2, both in the
    boot path), many `cp (a),#imm` reads, and reads spread over a wide address
    range rather than clustered in one routine.  The script prints all three
    so the ranking is visible rather than asserted.

    ⚠ THE FALSE-POSITIVE RATE IS REAL.  A three-byte pattern also occurs inside
    tables and text.  --null runs the identical scan on prom_d (data only, no
    TLCS-900 code) and on byte-shuffled copies; subtract that floor before
    believing any row.  Rows near the floor mean nothing.

USAGE
    python3 wsa1_directpage_census.py                # ranked table, prom_a
    python3 wsa1_directpage_census.py --image prom_c
    python3 wsa1_directpage_census.py --addr 0xc4    # every site touching (0xC4)
    python3 wsa1_directpage_census.py --null
"""

import argparse
import os
import random
import sys

ROMS = "/home/fsanches/compartilhado/technics_roms/roms/wsa1"
IMAGES = [
    ("prom_a", "wsa1_os_v2.ic12", 0xF80000),
    ("prom_b", "wsa1_os_v2.ic13", 0xF00000),
    ("prom_c", "wsa1_os_v2.ic28", 0xF80000),
    ("prom_d", "wsa1_os_v2.ic21", 0x000000),
]
R8 = ["W", "A", "B", "C", "D", "E", "H", "L"]


def decode(buf, i):
    """(mnemonic, addr8, kind, length) or None.  kind in {'setimm','write','read','test'}."""
    b0 = buf[i]
    if b0 == 0x08:
        return ("ld (0x%02X),#0x%02X" % (buf[i + 1], buf[i + 2]), buf[i + 1], "setimm", 3)
    if b0 == 0xC0:
        a, op = buf[i + 1], buf[i + 2]
        if 0x20 <= op <= 0x27:
            return ("ld %s,(0x%02X)" % (R8[op - 0x20], a), a, "read", 3)
        if op == 0x3F:
            return ("cp (0x%02X),#0x%02X" % (a, buf[i + 3]), a, "test", 4)
        if op == 0x3C:
            return ("and (0x%02X),#0x%02X" % (a, buf[i + 3]), a, "write", 4)
        if op == 0x3E:
            return ("or (0x%02X),#0x%02X" % (a, buf[i + 3]), a, "write", 4)
        for base, mn in ((0x80, "add"), (0xC0, "and"), (0xD0, "xor"),
                         (0xE0, "or"), (0xF0, "cp")):
            if base <= op <= base + 7:
                kind = "test" if mn == "cp" else "read"
                return ("%s %s,(0x%02X)" % (mn, R8[op - base], a), a, kind, 3)
        return None
    if b0 == 0xF0:
        a, op = buf[i + 1], buf[i + 2]
        if 0x40 <= op <= 0x47:
            return ("ld (0x%02X),%s" % (a, R8[op - 0x40]), a, "write", 3)
        if 0xB0 <= op <= 0xB7:
            return ("res %d,(0x%02X)" % (op - 0xB0, a), a, "write", 3)
        if 0xB8 <= op <= 0xBF:
            return ("set %d,(0x%02X)" % (op - 0xB8, a), a, "write", 3)
        if 0xC8 <= op <= 0xCF:
            return ("bit %d,(0x%02X)" % (op - 0xC8, a), a, "test", 3)
        if 0xA0 <= op <= 0xA7:
            return ("stcf %d,(0x%02X)" % (op - 0xA0, a), a, "read", 3)
        return None
    return None


def decode16(buf, i):
    """Same, for the 16-bit-direct form `(nn)` -- prefix 0xC1 (byte) / 0xF1 (sizeless).

    Verified spellings, all read off code this project has already decoded:
        c1 38 2b 21     ld A,(0x2b38)          prom_a 0xF828DF
        c1 25 27 3f 00  cp (0x2725),#0x00      prom_a 0xFF4858
        f1 05 25 41     ld (0x2505),A          prom_a 0xF898B5
        f1 40 25 00 01  ld (0x2540),#0x01      prom_a 0xF90BA5
        f1 75 20 c9     bit 1,(0x2075)         prom_a 0xF8C498
    """
    b0 = buf[i]
    if b0 not in (0xC1, 0xF1) or i + 5 >= len(buf):
        return None
    a = buf[i + 1] | (buf[i + 2] << 8)
    op = buf[i + 3]
    if b0 == 0xC1:
        if 0x20 <= op <= 0x27:
            return ("ld %s,(0x%04X)" % (R8[op - 0x20], a), a, "read", 4)
        if op == 0x3F:
            return ("cp (0x%04X),#0x%02X" % (a, buf[i + 4]), a, "test", 5)
        if op in (0x3C, 0x3E):
            return ("%s (0x%04X),#0x%02X" % ("and" if op == 0x3C else "or",
                                             a, buf[i + 4]), a, "write", 5)
        for base, mn in ((0x80, "add"), (0xC0, "and"), (0xD0, "xor"),
                         (0xE0, "or"), (0xF0, "cp")):
            if base <= op <= base + 7:
                return ("%s %s,(0x%04X)" % (mn, R8[op - base], a), a,
                        "test" if mn == "cp" else "read", 4)
        return None
    if op == 0x00:
        return ("ld (0x%04X),#0x%02X" % (a, buf[i + 4]), a, "setimm", 5)
    if 0x40 <= op <= 0x47:
        return ("ld (0x%04X),%s" % (a, R8[op - 0x40]), a, "write", 4)
    if 0xB0 <= op <= 0xBF:
        return ("%s %d,(0x%04X)" % ("res" if op < 0xB8 else "set",
                                    op & 7, a), a, "write", 4)
    if 0xC8 <= op <= 0xCF:
        return ("bit %d,(0x%04X)" % (op - 0xC8, a), a, "test", 4)
    return None


def decode24(buf, i):
    """Same again for the 24-bit-direct form -- prefix 0xC2 (byte) / 0xF2 (sizeless).

    This is the form prom_c uses for nearly all of its RAM, so leaving it out
    would make "CPU 2 has no mode flag" an artefact of the scanner instead of a
    finding.  Verified spellings from already-decoded code:
        c2 80 07 60 23        ld C,(0x600780)            prom_a 0xF8E504
        c2 d9 07 60 3f 01     cp (0x6007d9),#0x01        prom_a 0xF8E530
        f2 da 07 60 00 02     ld (0x6007da),#0x02        prom_a 0xF8E4B3
        f2 80 07 60 46        ld (0x600780),H            prom_a 0xF8E496
        f2 8a 00 00 b6        res 6,(0x00008a)           prom_a 0xF8E4F7
    """
    b0 = buf[i]
    if b0 not in (0xC2, 0xF2) or i + 6 >= len(buf):
        return None
    a = buf[i + 1] | (buf[i + 2] << 8) | (buf[i + 3] << 16)
    op = buf[i + 4]
    if b0 == 0xC2:
        if 0x20 <= op <= 0x27:
            return ("ld %s,(0x%06X)" % (R8[op - 0x20], a), a, "read", 5)
        if op == 0x3F:
            return ("cp (0x%06X),#0x%02X" % (a, buf[i + 5]), a, "test", 6)
        if op in (0x3C, 0x3E):
            return ("%s (0x%06X),#0x%02X" % ("and" if op == 0x3C else "or",
                                             a, buf[i + 5]), a, "write", 6)
        for base, mn in ((0x80, "add"), (0xC0, "and"), (0xD0, "xor"),
                         (0xE0, "or"), (0xF0, "cp")):
            if base <= op <= base + 7:
                return ("%s %s,(0x%06X)" % (mn, R8[op - base], a), a,
                        "test" if mn == "cp" else "read", 5)
        return None
    # 0xF2 is also `lda R32,(nnn)` (op 0x30+r), which is an ADDRESS-OF, not an
    # access -- excluded on purpose, it would swamp the counts.
    if op == 0x00:
        return ("ld (0x%06X),#0x%02X" % (a, buf[i + 5]), a, "setimm", 6)
    if 0x40 <= op <= 0x47:
        return ("ld (0x%06X),%s" % (a, R8[op - 0x40]), a, "write", 5)
    if 0xB0 <= op <= 0xBF:
        return ("%s %d,(0x%06X)" % ("res" if op < 0xB8 else "set",
                                    op & 7, a), a, "write", 5)
    if 0xC8 <= op <= 0xCF:
        return ("bit %d,(0x%06X)" % (op - 0xC8, a), a, "test", 5)
    return None


def scan16(buf, base, dec=None):
    dec = dec or decode16
    hits = []
    for i in range(len(buf) - 7):
        d = dec(buf, i)
        if d is None:
            continue
        mn, a, kind, ln = d
        hits.append({"addr": base + i, "mn": mn, "a": a, "kind": kind})
    return hits


def scan(buf, base, lo=0x80, hi=0xFF):
    hits = []
    for i in range(len(buf) - 4):
        d = decode(buf, i)
        if d is None:
            continue
        mn, a, kind, ln = d
        if not (lo <= a <= hi):
            continue
        hits.append({"addr": base + i, "mn": mn, "a": a, "kind": kind})
    return hits


def load(fn):
    with open(os.path.join(ROMS, fn), "rb") as f:
        return f.read()


def table(hits, title):
    per = {}
    for h in hits:
        p = per.setdefault(h["a"], {"setimm": 0, "write": 0, "read": 0,
                                    "test": 0, "sites": []})
        p[h["kind"]] += 1
        p["sites"].append(h["addr"])
    print("=" * 78)
    print(title)
    print("=" * 78)
    print("  %-6s %7s %6s %6s %6s %6s  %s" %
          ("addr", "setimm", "write", "read", "test", "spread", "first..last site"))
    rows = []
    for a, p in per.items():
        spread = max(p["sites"]) - min(p["sites"]) if len(p["sites"]) > 1 else 0
        rows.append((a, p, spread))
    # a mode flag: few immediate writes, many tests, wide spread
    rows.sort(key=lambda r: (-r[1]["test"], -r[2]))
    for a, p, spread in rows[:30]:
        print("  0x%04X %7d %6d %6d %6d %6d  %06X..%06X" %
              (a, p["setimm"], p["write"], p["read"], p["test"], spread,
               min(p["sites"]), max(p["sites"])))
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="prom_a")
    ap.add_argument("--addr", type=lambda s: int(s, 0))
    ap.add_argument("--null", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--wide", action="store_true",
                    help="scan 16-bit-direct RAM (0x0000-0xFFFF) instead of the direct page")
    ap.add_argument("--wide24", action="store_true",
                    help="scan 24-bit-direct RAM -- the form prom_c uses for most variables")
    args = ap.parse_args()

    if args.wide or args.wide24:
        dec = decode24 if args.wide24 else decode16
        for tag, fn, base in (IMAGES if args.all else
                              [x for x in IMAGES if x[0] == args.image]):
            hits = scan16(load(fn), base, dec)
            if args.addr is not None:
                for h in [x for x in hits if x["a"] == args.addr]:
                    print("  %06X  %-8s %s" % (h["addr"], h["kind"], h["mn"]))
                continue
            table(hits, "%s (%s) -- 16-bit-direct RAM, ranked by test count" % (tag, fn))
        return

    if args.null:
        print("NOISE FLOOR for the direct-page scan\n")
        print("%-26s %8s %8s %8s" % ("control", "setimm", "read", "test"))
        for tag, fn, base in IMAGES:
            buf = load(fn)
            if tag == "prom_d":
                h = scan(buf, base)
                print("%-26s %8d %8d %8d" % ("prom_d (data only)",
                      sum(1 for x in h if x["kind"] == "setimm"),
                      sum(1 for x in h if x["kind"] == "read"),
                      sum(1 for x in h if x["kind"] == "test")))
            rnd = random.Random(20260825)
            sh = bytearray(buf)
            rnd.shuffle(sh)
            h = scan(bytes(sh), base)
            print("%-26s %8d %8d %8d" % (tag + " shuffled",
                  sum(1 for x in h if x["kind"] == "setimm"),
                  sum(1 for x in h if x["kind"] == "read"),
                  sum(1 for x in h if x["kind"] == "test")))
        return

    todo = IMAGES if args.all else [x for x in IMAGES if x[0] == args.image]
    for tag, fn, base in todo:
        hits = scan(load(fn), base)
        if args.addr is not None:
            hits = [h for h in hits if h["a"] == args.addr]
            print("=" * 78)
            print("%s -- every site touching (0x%02X)" % (tag, args.addr))
            print("=" * 78)
            for h in hits:
                print("  %06X  %-8s %s" % (h["addr"], h["kind"], h["mn"]))
            print("  (%d sites)\n" % len(hits))
        else:
            table(hits, "%s (%s) -- direct page 0x80-0xFF, ranked by test count" % (tag, fn))


if __name__ == "__main__":
    sys.exit(main())
