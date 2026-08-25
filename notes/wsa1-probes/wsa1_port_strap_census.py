#!/usr/bin/env python3
"""wsa1_port_strap_census.py -- every TMP95C061 I/O-port access in the WSA1 v2 ROMs.

QUESTION IT ANSWERS
    "Does the WSA1 firmware read a hardware strap at boot to tell the SX-WSA1
    keyboard from the SX-WSA1R rack module?"

    A model strap has a signature: it is READ, the read FEEDS A CONDITIONAL
    BRANCH, and it is read from few sites.  This script enumerates *every* read
    of a port SFR in all four images so that the candidates can be ranked
    against the full population instead of against the handful that happen to
    be converted to assembly already (prom_a/b/c are 23% substantive, so a
    grep of the .s files would miss most of the machine).

HOW
    Byte-pattern scan of the raw images for the TLCS-900/H 8-bit-direct memory
    forms.  The encodings are not guessed; each was read off the existing
    disassembly and re-checked with MAME's unidasm:

        f0 <a> c8+n   bit n,(a)      -- prom_a 0xF8E489 = "f0 13 ca" = bit 2,(0x13)
        f0 <a> a0+n   stcf n,(a)
        f0 <a> b0+n   res n,(a)      -- prom_a 0xF8E4CD = "f0 13 b1" = res 1,(0x13)
        f0 <a> b8+n   set n,(a)      -- prom_a 0xF8E5A8 = "f0 13 b9" = set 1,(0x13)
        f0 <a> c0+n   chg n,(a)
        f0 <a> 40+r   ld (a),R       -- size taken from R
        c0 <a> 20+r   ld R8,(a)      -- prom_a 0xFE594C = "c0 1f 21" = ld A,(0x1f)
        c0 <a> 80/c0/d0/e0/f0 +r     add/and/xor/or/cp R8,(a)
        d0/e0 <a> 20+r               ld R16,(a) / ld R32,(a)
        08 <a> <imm>  ld (a),#imm8   -- prom_a 0xF8E4CA = "08 7f 0a" = ldio DMA3V,0x0a

    A hit is only reported when <a> is one of the nine port SFRs.  Because a
    three-byte pattern also occurs inside data, every READ hit is graded by
    whether a conditional branch follows within the next few bytes:

        60+cc  jr  cc,rel8    (2 bytes)   -- 0x66 = jr Z, seen at prom_a 0xF8E4A3
        70+cc  jrl cc,rel16   (3 bytes)   -- 0x7E = jrl NZ, seen at prom_a 0xF8E48C

    THE FALSE-POSITIVE RATE IS MEASURED, NOT ASSUMED: --null runs the identical
    scan over prom_d, which is data only (no TLCS-900 code), and over a
    byte-shuffled copy of each program image.  Whatever that yields is the
    noise floor these counts must beat.

USAGE
    python3 wsa1_port_strap_census.py                 # full census, all images
    python3 wsa1_port_strap_census.py --gated         # only reads feeding a branch
    python3 wsa1_port_strap_census.py --port 0x0d     # one SFR (P5)
    python3 wsa1_port_strap_census.py --null          # the noise floor
    python3 wsa1_port_strap_census.py --summary       # per-port counts only

WHAT THE NUMBERS MEAN
    "gated read" = a port read whose next instruction is a conditional branch,
    i.e. the shape a strap test has.  It is NECESSARY, not sufficient: a
    handshake line polled in a loop has exactly the same shape and this machine
    is full of them.  Read the "sites" column too -- a strap is read from ONE
    or TWO places, a handshake from dozens.
"""

import argparse
import os
import random
import sys

ROMS = "/home/fsanches/compartilhado/technics_roms/roms/wsa1"

# image -> (filename, base address, what it is)
IMAGES = [
    ("prom_a", "wsa1_os_v2.ic12", 0xF80000, "CPU 1 program, boot image"),
    ("prom_b", "wsa1_os_v2.ic13", 0xF00000, "CPU 1 program, low half"),
    ("prom_c", "wsa1_os_v2.ic28", 0xF80000, "CPU 2 program, boot image"),
    ("prom_d", "wsa1_os_v2.ic21", 0x000000, "data only -- NULL CONTROL"),
]

# TMP95C061 port SFRs.  Names from include/tmp95c061_sfr.inc, which takes them
# from MAME's tmp95c061_syms[] and nothing else.
PORTS = {
    0x01: "P1", 0x06: "P2", 0x0D: "P5", 0x12: "P6", 0x13: "P7",
    0x18: "P8", 0x19: "P9", 0x1E: "PA", 0x1F: "PB",
}
# Control registers, tracked separately: writing one is configuration, not a read.
PORTCR = {
    0x04: "P1CR", 0x09: "P2FC", 0x10: "P5CR", 0x11: "P5FC", 0x15: "P6FC",
    0x16: "P7CR", 0x17: "P7FC", 0x1A: "P8CR", 0x1B: "P8FC",
    0x2C: "PACR", 0x2D: "PAFC", 0x2E: "PBCR", 0x2F: "PBFC",
}

R8 = ["W", "A", "B", "C", "D", "E", "H", "L"]
CC = ["F", "LT", "LE", "ULE", "OV", "MI", "Z", "C",
      "T", "GE", "GT", "UGT", "NOV", "PL", "NZ", "NC"]


def decode(buf, i):
    """Return (mnemonic, sfr_addr, is_read, length) for a port access at i, else None."""
    b0 = buf[i]
    if b0 == 0x08 and i + 2 < len(buf):                       # ld (n),#imm8
        return ("ld (%s),#0x%02X" % ("{P}", buf[i + 2]), buf[i + 1], False, 3)
    if b0 in (0xC0, 0xD0, 0xE0, 0xF0) and i + 2 < len(buf):
        a, op = buf[i + 1], buf[i + 2]
        sz = {0xC0: "", 0xD0: "w", 0xE0: "l", 0xF0: ""}[b0]
        if b0 == 0xF0:
            if 0xC8 <= op <= 0xCF:
                return ("bit %d,(%s)" % (op - 0xC8, "{P}"), a, True, 3)
            if 0xA0 <= op <= 0xA7:
                return ("stcf %d,(%s)" % (op - 0xA0, "{P}"), a, True, 3)
            if 0xB0 <= op <= 0xB7:
                return ("res %d,(%s)" % (op - 0xB0, "{P}"), a, False, 3)
            if 0xB8 <= op <= 0xBF:
                return ("set %d,(%s)" % (op - 0xB8, "{P}"), a, False, 3)
            if 0xC0 <= op <= 0xC7:
                return ("chg %d,(%s)" % (op - 0xC0, "{P}"), a, False, 3)
            if 0x40 <= op <= 0x47:
                return ("ld (%s),%s" % ("{P}", R8[op - 0x40]), a, False, 3)
            return None
        if 0x20 <= op <= 0x27:
            return ("ld%s %s,(%s)" % (sz, R8[op - 0x20], "{P}"), a, True, 3)
        if b0 != 0xC0:
            return None
        for base, mn in ((0x80, "add"), (0xC0, "and"), (0xD0, "xor"),
                         (0xE0, "or"), (0xF0, "cp")):
            if base <= op <= base + 7:
                return ("%s %s,(%s)" % (mn, R8[op - base], "{P}"), a, True, 3)
        if op == 0x3F and i + 3 < len(buf):                   # cp (n),#imm8
            return ("cp (%s),#0x%02X" % ("{P}", buf[i + 3]), a, True, 4)
        if op == 0x3C and i + 3 < len(buf):                   # and (n),#imm8
            return ("and (%s),#0x%02X" % ("{P}", buf[i + 3]), a, False, 4)
        if op == 0x3E and i + 3 < len(buf):                   # or (n),#imm8
            return ("or (%s),#0x%02X" % ("{P}", buf[i + 3]), a, False, 4)
        return None
    return None


def branch_after(buf, i, length):
    """If a conditional branch starts at i+length, name it.  '' otherwise.

    Also looks one instruction further, to catch `ld C,(P9) / and C,#8 / jr`,
    which is the other way a strap test is written.
    """
    j = i + length
    if j < len(buf):
        b = buf[j]
        if 0x60 <= b <= 0x6F and b not in (0x60, 0x68):       # jr cc (F/T are not tests
            return "jr %s" % CC[b - 0x60]
        if 0x70 <= b <= 0x7F and b not in (0x70, 0x78):       # jrl cc
            return "jrl %s" % CC[b - 0x70]
    # allow one intervening 2-4 byte ALU op on the loaded register
    for skip in (2, 3, 4):
        k = i + length + skip
        if k < len(buf):
            b = buf[k]
            if 0x60 <= b <= 0x6F and b not in (0x60, 0x68):
                return "jr %s (+%d)" % (CC[b - 0x60], skip)
            if 0x70 <= b <= 0x7F and b not in (0x70, 0x78):
                return "jrl %s (+%d)" % (CC[b - 0x70], skip)
    return ""


def scan(buf, base):
    out = []
    for i in range(len(buf) - 4):
        d = decode(buf, i)
        if d is None:
            continue
        mn, a, is_read, ln = d
        if a not in PORTS and a not in PORTCR:
            continue
        name = PORTS.get(a) or PORTCR[a]
        out.append({
            "addr": base + i, "off": i, "mn": mn.replace("{P}", name),
            "sfr": a, "port": name, "read": is_read,
            "gate": branch_after(buf, i, ln) if is_read else "",
        })
    return out


def load(fn):
    with open(os.path.join(ROMS, fn), "rb") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gated", action="store_true", help="only reads that feed a branch")
    ap.add_argument("--port", type=lambda s: int(s, 0), help="restrict to one SFR address")
    ap.add_argument("--image", help="restrict to one image (prom_a/b/c/d)")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--null", action="store_true", help="run the noise-floor controls")
    args = ap.parse_args()

    if args.null:
        print("NOISE FLOOR -- the same scan where no port access can be real\n")
        print("%-28s %8s %8s %8s" % ("control", "reads", "gated", "writes"))
        for tag, fn, base, _ in IMAGES:
            buf = load(fn)
            if tag == "prom_d":
                h = scan(buf, base)
                print("%-28s %8d %8d %8d" % (
                    "prom_d (data only)", sum(1 for x in h if x["read"]),
                    sum(1 for x in h if x["gate"]), sum(1 for x in h if not x["read"])))
            rnd = random.Random(20260825)
            sh = bytearray(buf)
            rnd.shuffle(sh)
            h = scan(bytes(sh), base)
            print("%-28s %8d %8d %8d" % (
                tag + " byte-shuffled", sum(1 for x in h if x["read"]),
                sum(1 for x in h if x["gate"]), sum(1 for x in h if not x["read"])))
        return

    grand = {}
    for tag, fn, base, what in IMAGES:
        if args.image and args.image != tag:
            continue
        hits = scan(load(fn), base)
        if args.port is not None:
            hits = [h for h in hits if h["sfr"] == args.port]
        if args.gated:
            hits = [h for h in hits if h["gate"]]
        print("=" * 78)
        print("%s  (%s, base 0x%06X) -- %s" % (tag, fn, base, what))
        print("=" * 78)
        per = {}
        for h in hits:
            k = h["port"]
            per.setdefault(k, [0, 0, 0])
            per[k][0 if h["read"] else 2] += 1
            if h["gate"]:
                per[k][1] += 1
        print("  %-6s %6s %6s %6s" % ("port", "reads", "gated", "writes"))
        for k in sorted(per, key=lambda x: -per[x][1]):
            print("  %-6s %6d %6d %6d" % (k, per[k][0], per[k][1], per[k][2]))
        grand[tag] = per
        if not args.summary:
            print()
            for h in hits:
                print("  %06X  %-22s %-14s %s" % (
                    h["addr"], h["mn"], h["gate"], "READ" if h["read"] else "write"))
        print()


if __name__ == "__main__":
    sys.exit(main())
