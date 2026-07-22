#!/usr/bin/env python3
"""kn5000_dsp_header.py -- the uPD6383GF COMMON HEADER and ALGORITHM-CHANGE STUB.

The ROM ALGO_TABLE corpus (see tools/kn5000_dsp_extract.py and
notes/kn5000-dsp-encoding.md) contains only per-sample EFFECT BODIES: straight-line
code.  The control machinery -- loop counters LC1-LC3, the COND field, GF flag
manipulation, DRAM-delay setup, audio I/O framing -- must live in the scaffolding
that every effect shares, and that scaffolding is two blocks the effect corpus does
not contain:

    I-RAM  0..59   60-word common header       (Sub CPU EFF_WriteHeader, ROM 0x01E496)
    I-RAM 60..82   23-word algorithm-change stub (DSP_AlgorithmChange, ROM 0x01E63C)

Both are in a cold-boot capture from the kn5000_dsp1 device.  This tool
characterises those 83 words and runs the falsification tests reported in
notes/kn5000-dsp-header.md.  It DECODES NOTHING it cannot defend; every printed
section is labelled with the strength of the evidence it supports.

Usage:
    python3 tools/kn5000_dsp_header.py <kn5000_dsp1_upload.txt> [<subprogram.rom>]
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kn5000_dsp_wordfields import parse, as_int          # noqa: E402

IRAM_WORDS = 384
HDR_ADDR, HDR_LEN = 0, 60
STUB_ADDR, STUB_LEN = 60, 23
BODY_SLOTS = (84, 200)          # effect unit 0 / unit 1 load addresses
POKE_BASE = 352                 # host scratch region seen in the capture


def fields(v):
    """The field map established in notes/kn5000-dsp-encoding.md (INFERRED)."""
    return (v >> 24) & 0xFFF, (v >> 20) & 0xF, (v >> 12) & 0xFF, v & 0xFFF


def fmt(v):
    hi, c, a, lo = fields(v)
    return f"{hi:03X}.{c:X}.{a:02X}.{lo:03X}"


def is_terminator(v):
    _, c, a, _ = fields(v)
    return c == 1 and a in (0x0E, 0x0F)


# --------------------------------------------------------------------------- #
# corpus
# --------------------------------------------------------------------------- #
def load_capture(path):
    blocks = parse(path)
    hdrs = [ws for _, a, ws in blocks if a == HDR_ADDR and len(ws) == HDR_LEN]
    stubs = [ws for _, a, ws in blocks if a == STUB_ADDR and len(ws) == STUB_LEN]
    if not hdrs or not stubs:
        sys.exit(f"{path}: no 60-word block at 0 / 23-word block at 60")
    ident_h = all(b == hdrs[0] for b in hdrs)
    ident_s = all(b == stubs[0] for b in stubs)
    hdr = [as_int(w) for w in hdrs[0]]
    stub = [as_int(w) for w in stubs[0]]
    return blocks, hdr, stub, (len(hdrs), ident_h), (len(stubs), ident_s)


def load_bodies(progdir):
    """The 96 extracted effect-body images, as the control vocabulary."""
    words = []
    if not progdir or not os.path.isdir(progdir):
        return words
    for fn in sorted(os.listdir(progdir)):
        if not fn.endswith(".bin"):
            continue
        d = open(os.path.join(progdir, fn), "rb").read()
        words += [int.from_bytes(d[i:i + 5], "big") for i in range(0, len(d) - 4, 5)]
    return words


# --------------------------------------------------------------------------- #
# reports
# --------------------------------------------------------------------------- #
def dump(hdr, stub):
    print("=" * 78)
    print("1. THE 83 WORDS, field-decomposed  [MEASURED: the bytes; INFERRED: the map]")
    print("=" * 78)
    print("  iram  hi12.c.addr.lo12   addr8  note")
    for base, blk, name in ((HDR_ADDR, hdr, "header"), (STUB_ADDR, stub, "stub")):
        print(f"  --- {name} @{base} ---")
        for i, v in enumerate(blk):
            note = "<<< TERMINATOR" if is_terminator(v) else ""
            print(f"  {base + i:4d}  {fmt(v)}   {(v >> 12) & 0xFF:3d}   {note}")


def vocabulary(hdr, stub, bodies):
    print()
    print("=" * 78)
    print("2. VOCABULARY: header/stub vs the effect bodies  [MEASURED]")
    print("=" * 78)
    bset = set(bodies)
    for blk, name in ((hdr, "header @0..59"), (stub, "stub @60..82")):
        d = set(blk)
        uniq = d - bset
        print(f"  {name:16s} {len(blk):3d} words, {len(d):3d} distinct, "
              f"{len(uniq):3d} ({100 * len(uniq) / max(1, len(d)):.0f}%) never seen "
              f"in {len(bodies)} body words")
    print()
    print("  class4 histogram")
    for blk, name in ((hdr, "header"), (stub, "stub"), (bodies, "bodies")):
        h = collections.Counter(fields(v)[1] for v in blk)
        print(f"    {name:8s} " + " ".join(f"{k:X}:{h[k]}" for k in sorted(h)))
    print()
    print("  classes that occur in header/stub but NOT in any effect body:")
    hb = set(fields(v)[1] for v in hdr + stub)
    bb = set(fields(v)[1] for v in bodies)
    print(f"    {sorted(hb - bb)}   (bodies-only: {sorted(bb - hb)})")


def structure(hdr, stub):
    print()
    print("=" * 78)
    print("3. STRUCTURE  [MEASURED positions, INFERRED reading]")
    print("=" * 78)
    t = [i for i, v in enumerate(hdr) if is_terminator(v)]
    print(f"  terminators inside the header at I-RAM {t}"
          f"  -> {[fmt(hdr[i]) for i in t]}")
    t2 = [i for i, v in enumerate(stub) if is_terminator(v)]
    print(f"  terminators inside the stub      : {t2}  <-- the stub has NONE")
    print()
    print("  the two header segments, side by side (segment A = 40..49, B = 50..59):")
    for k in range(10):
        a, b = hdr[40 + k], hdr[50 + k]
        same = "==" if a == b else ("~" if fields(a)[3] == fields(b)[3] else "  ")
        print(f"    {40+k:3d} {fmt(a)}  {same}  {50+k:3d} {fmt(b)}")
    print()
    print("  lo12 families (a lo12 value shared by >=2 of the 83 words):")
    fam = collections.defaultdict(list)
    for base, blk in ((HDR_ADDR, hdr), (STUB_ADDR, stub)):
        for i, v in enumerate(blk):
            fam[fields(v)[3]].append((base + i, v))
    for lo, items in sorted(fam.items(), key=lambda kv: -len(kv[1])):
        if len(items) < 2:
            continue
        print(f"    lo12={lo:03X}  x{len(items)}: " +
              " ".join(f"{i}:{fmt(v)}" for i, v in items))


def handoff_hunt(hdr, stub):
    print()
    print("=" * 78)
    print("4. HAND-OFF HUNT: is a branch to I-RAM 84 / 200 encoded anywhere?")
    print("=" * 78)
    W = hdr + stub
    idx = list(range(HDR_ADDR, HDR_ADDR + len(hdr))) + \
        list(range(STUB_ADDR, STUB_ADDR + len(stub)))
    hits = collections.defaultdict(list)
    for lo in range(36):
        for w in range(1, 17):
            if lo + w > 36:
                continue
            m = (1 << w) - 1
            for j, v in enumerate(W):
                x = (v >> lo) & m
                if x in BODY_SLOTS:
                    hits[(lo, w)].append((idx[j], x))
    both = {k: v for k, v in hits.items()
            if {x for _, x in v} == set(BODY_SLOTS)}
    print(f"  exhaustive scan of every contiguous bitfield (bit {0}..35, width 1..16)")
    print(f"  fields yielding BOTH 84 and 200 : {both if both else 'NONE'}")
    print(f"  fields yielding either value    : {len(hits)}")
    for k in sorted(hits):
        vals = hits[k]
        print(f"    bits[{k[0]+k[1]-1}:{k[0]}]  " +
              " ".join(f"@{i}={x}" for i, x in vals[:6]) +
              ("" if len(vals) <= 6 else f" (+{len(vals)-6})"))
    print()
    print("  CONTROL: how often does a random 36-bit word contain 84 or 200 in some")
    print("  contiguous field?  Nearly always -- these hits are not evidence unless")
    print("  the SAME field position gives 84 in one word and 200 in another.")


def poke_region(blocks):
    print()
    print("=" * 78)
    print("5. RUNTIME I-RAM WRITES: the patch slots and the poke region  [MEASURED]")
    print("=" * 78)
    for k, (cmd, addr, ws) in enumerate(blocks):
        if addr in (HDR_ADDR, STUB_ADDR) and len(ws) in (HDR_LEN, STUB_LEN):
            print(f"  #{k:3d} @{addr:<4d} {len(ws):3d} words   (block upload)")
        elif addr in BODY_SLOTS:
            print(f"  #{k:3d} @{addr:<4d} {len(ws):3d} words   <-- EFFECT BODY")
        elif addr < POKE_BASE and len(ws) == 1:
            print(f"  #{k:3d} @{addr:<4d} PATCH  {fmt(as_int(ws[0]))}")
        elif addr >= POKE_BASE:
            s = " ".join(fmt(as_int(w)) for w in ws[:4])
            print(f"  #{k:3d} @{addr:<4d} {len(ws):3d} words  poke: {s}"
                  f"{' ...' if len(ws) > 4 else ''}")
    print()
    print("  patch-slot summary (slot identified by its INVARIANT lo12):")
    slots = collections.defaultdict(list)
    for _, addr, ws in blocks:
        if len(ws) == 1 and addr < POKE_BASE:
            slots[addr].append(as_int(ws[0]))
    for a, vs in sorted(slots.items()):
        los = {fields(v)[3] for v in vs}
        print(f"    I-RAM {a}: lo12 {'CONSTANT ' + f'{los.pop():03X}' if len(los) == 1 else los}"
              f"   values " + " ".join(sorted({fmt(v) for v in vs})))


def rom_crosscheck(rompath, hdr, stub):
    if not rompath or not os.path.exists(rompath):
        return
    print()
    print("=" * 78)
    print("6. ROM CROSS-CHECK  [MEASURED]")
    print("=" * 78)
    d = open(rompath, "rb").read()
    base = 0xEF00

    def sl(a, n):
        return d[a - base:a - base + n]

    for a, blk, name in ((0x01E496, hdr, "header"), (0x01E63C, stub, "stub")):
        rec = sl(a, 5)
        op, ln = rec[0] >> 4, ((rec[0] & 0xF) << 8) | rec[1]
        iaddr = (rec[3] << 8) | rec[4]
        body = sl(a + 5, len(blk) * 5)
        words = [int.from_bytes(body[i:i + 5], "big") for i in range(0, len(body), 5)]
        print(f"  {name}: ROM 0x{a:06X} op={op} len={ln} cmd=0x{rec[2]:02X} "
              f"I-RAM addr={iaddr}  bytes match capture: {words == blk}")

    # the per-effect patch table that immediately follows the header stream
    tail = sl(0x01E5C7, 0x80)
    print("\n  patch table immediately after the header stream (ROM 0x01E5C7):")
    i = 0
    while i < len(tail) - 1:
        op, ln = tail[i] >> 4, ((tail[i] & 0xF) << 8) | tail[i + 1]
        if op == 0xF:
            print("    F0 terminator")
            i += 1
            continue
        if ln < 2 or i + ln > len(tail):
            break
        rec = tail[i:i + ln]
        if op == 0xE and ln == 10:
            iaddr = (rec[3] << 8) | rec[4]
            w = int.from_bytes(rec[5:10], "big")
            print(f"    op E -> I-RAM {iaddr:3d} := {fmt(w)}")
        else:
            print(f"    op {op:X} len {ln}: {rec.hex()}")
        i += ln


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cap = sys.argv[1]
    rom = sys.argv[2] if len(sys.argv) > 2 else None
    # the extracted effect-body images (kn5000_dsp_extract.py output) are the
    # control vocabulary; look for them beside the capture or one level up
    progdir = None
    d = os.path.dirname(os.path.abspath(cap))
    for _ in range(3):
        if os.path.isdir(os.path.join(d, "progs")):
            progdir = os.path.join(d, "progs")
            break
        d = os.path.dirname(d)
    blocks, hdr, stub, (nh, ih), (ns, isd) = load_capture(cap)
    bodies = load_bodies(progdir)
    print(f"capture {cap}")
    print(f"  header uploaded {nh}x, byte-identical: {ih}")
    print(f"  stub   uploaded {ns}x, byte-identical: {isd}")
    print(f"  body vocabulary: {len(bodies)} words from {progdir}")
    dump(hdr, stub)
    if bodies:
        vocabulary(hdr, stub, bodies)
    structure(hdr, stub)
    handoff_hunt(hdr, stub)
    poke_region(blocks)
    rom_crosscheck(rom, hdr, stub)


if __name__ == "__main__":
    main()
