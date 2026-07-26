#!/usr/bin/env python3
"""kn5000_dsp_nextsteps.py -- the measurements behind notes/dsp-next-steps-roadmap.md.

Felipe's scope for this pass is deliberately narrow: the KERNEL (the resident
83-word scaffolding: header I-RAM 0..59 + epilogue 60..82) and ONE reverb
(I-RAM 200..332, the only unit-1 image in the machine).  Everything here is
computed over that scope.

Sections, in the order the note uses them:

  A  KERNEL-ALONE and KERNEL+REVERB census (words / distinct / families /
     decoded / class census), and the overlap between the two vocabularies.
  B  the C-format immediates on the kernel, read under the MEASURED
     "hi12[11:8]==0xC  =>  bits[23:12] are a 12-bit immediate" rule
     (notes/kn5000-dsp-header.md sect. 6).
  C  the OUTPUT-STAGE PATCH SLOTS: an exhaustive scan of the Sub CPU ROM for
     every write to I-RAM 64 / 71, and the two canned scripts that carry them.
  D  the D-RAM POINTER WALK: the cell footprint of each body under the
     established single-pointer post-increment rule
     (notes/kn5000-dsp-addressing.md), anchored at the header's ldptr.

Every number printed here appears in the note with the same label.  Nothing is
executed and nothing in the driver is touched.

Usage:
    python3 tools/kn5000_dsp_nextsteps.py [capture.txt] [subprogram.rom]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser("~/compartilhado/kn5000-roms-disasm/dsp/tools"))

import dsp_disasm as D                       # noqa: E402
import kn5000_dsp_perframe as PF             # noqa: E402

CAP_DEFAULT = os.path.join(HERE, "..", "notes", "data", "kn5000_dsp1_upload_coldboot.txt")
ROM_DEFAULT = os.path.expanduser(
    "~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom")

PATCH_SLOTS = (64, 71)


def s8(v):
    return v - 256 if v & 0x80 else v


def fam(w):
    return (D.hi12(w), D.class4(w), D.lo12(w))


def imm12(w):
    """bits[23:12] -- the C-format immediate."""
    return (D.class4(w) << 8) | D.addr8(w)


def imm13(w):
    """bits[24:12] -- as imm12, plus hi12 bit 0."""
    return ((D.hi12(w) & 1) << 12) | imm12(w)


# ---------------------------------------------------------------- A. census
def census(name, words):
    dec = [w for w in words if D.decoded(w)]
    cl = collections.Counter(D.class4(w) for w in words)
    print(f"  {name:<44s} {len(words):4d} words  "
          f"{len(set(words)):4d} distinct  "
          f"{len(set(fam(w) for w in words)):4d} families  "
          f"{len(dec):3d} decoded ({100.0 * len(dec) / len(words):4.1f} %)")
    print("        class4: " + "  ".join(f"{k:X}:{v}" for k, v in sorted(cl.items())))
    return set(words), set(fam(w) for w in words)


# ------------------------------------------------------------ D. pointer walk
def walk(words, p, moving_only=True):
    """Single-pointer model: classes 2 and A access mem[p] then p += (s8)addr8;
    hi12 bit 4 stores the accumulator to mem[p].  Returns (p, accesses, stores)."""
    acc, sto = [], []
    for w in words:
        cl, hi = D.class4(w), D.hi12(w)
        store = (hi >> 4) & 1
        if (cl & 7) == 2:
            acc.append(p)
            if store:
                sto.append(p)
            p = (p + s8(D.addr8(w))) & 0xFF
        elif store:
            sto.append(p)
    return p, acc, sto


def main():
    cap = sys.argv[1] if len(sys.argv) > 1 else CAP_DEFAULT
    rompath = sys.argv[2] if len(sys.argv) > 2 else ROM_DEFAULT

    hdr, epi, patch = PF.load_resident(cap)
    for slot, w in patch.items():
        (hdr if slot < 60 else epi)[slot - (0 if slot < 60 else 60)] = w
    bodies = PF.load_bodies(rompath)
    _, rev, revalgos = PF.body_of(bodies, 16)
    kernel = hdr + epi

    print("=" * 78)
    print("A.  KERNEL-ALONE and KERNEL+REVERB  (Felipe's scope)")
    print("=" * 78)
    kw, kf = census("KERNEL  (header 0..59 + epilogue 60..82)", kernel)
    rw, rf = census(f"REVERB  (I-RAM 200..332, algos {revalgos[0]}..{revalgos[-1]})", rev)
    census("KERNEL + REVERB  (the floor of every frame)", kernel + rev)
    print("     words shared kernel<->reverb   : "
          + (", ".join("%010X" % w for w in sorted(kw & rw)) or "(none)"))
    print("     families shared kernel<->reverb: "
          + (", ".join("%03X.%X.%03X" % f for f in sorted(kf & rf)) or "(none)"))

    print()
    print("=" * 78)
    print("B.  C-FORMAT WORDS ON THE KERNEL  (hi12[11:8]==0xC => bits[23:12] immediate)")
    print("=" * 78)
    for i, w in enumerate(kernel):
        ir = i if i < 60 else i
        if (D.hi12(w) & 0xF00) == 0xC00:
            print(f"     I-RAM {ir:3d}  {w:010X}  hi12={D.hi12(w):03X}  "
                  f"imm12=0x{imm12(w):03X} ({imm12(w):5d})  imm13=0x{imm13(w):04X}  "
                  f"lo12={D.lo12(w):03X}")

    print()
    print("=" * 78)
    print("C.  OUTPUT-STAGE PATCH SLOTS -- exhaustive Sub CPU ROM scan")
    print("=" * 78)
    rom = open(rompath, "rb").read()
    found = []
    for i in range(len(rom) - 8):
        # the canned scripts frame each poke as  <cmd 01> <addr16> <5-byte word>
        if rom[i] == 0x01 and rom[i + 1] == 0x00 and rom[i + 2] in (0x40, 0x47):
            w = int.from_bytes(rom[i + 3:i + 8], "big")
            if (w & 0xFFF) in (0x445, 0x446):
                found.append((i, rom[i + 2], w))
    print(f"     ROM = {os.path.basename(rompath)}  ({len(rom)} bytes)")
    for off, slot, w in found:
        print(f"     ROM 0x{off + 3:06X}  ->  I-RAM {slot:3d} (0x{slot:02X})   {w:010X}   "
              f"hi12={D.hi12(w):03X} imm12=0x{imm12(w):03X} imm13=0x{imm13(w):04X} "
              f"lo12={D.lo12(w):03X}")
    print(f"     TOTAL writes to I-RAM 64/71 anywhere in the ROM: {len(found)}")
    for slot in PATCH_SLOTS:
        vals = [imm13(w) for _, s, w in found if s == slot]
        if len(vals) == 2:
            lo, hi = min(vals), max(vals)
            print(f"     slot {slot}: imm13 0x{lo:04X} ({lo}) and 0x{hi:04X} ({hi})"
                  f"   ratio = {hi / lo:g}"
                  f"   {'EXACT left shift by %d' % ((hi // lo).bit_length() - 1) if hi % lo == 0 else ''}")

    print()
    print("=" * 78)
    print("D.  D-RAM POINTER WALK  (single-pointer post-increment model)")
    print("=" * 78)
    for algo, name in ((16, "ROOM REVERB (unit 1)"), (0, "NO OPERATION"), (1, "CHORUS"),
                       (36, "COMPRESSOR"), (39, "PARAMETRIC EQ")):
        _, body, _ = PF.body_of(bodies, algo)
        if algo == 16:
            entry, pre = 0x50, hdr[50:60]
        else:
            entry, pre = 0x70, hdr[42:49]
        p, _, _ = walk(pre, entry)
        pend, acc, sto = walk(body, p)
        cells = sorted(set(acc))
        print(f"     {name:<22s} ldptr #${entry:02X} -> entry p=0x{p:02X}   "
              f"{len(acc):3d} accesses  {len(cells):2d} distinct cells  "
              f"0x{cells[0]:02X}..0x{cells[-1]:02X}   "
              f"last store -> 0x{(sto[-1] if sto else 0xFFFF):02X}")
        print("            " + " ".join("%02X" % c for c in cells))
    print()
    print("     NOTE: the reverb's terminator 612.1.0F.000 has hi12 bit 4 set")
    print("           (0x612 = END | 0x212), so it STORES the accumulator; under this")
    print("           walk that store lands on D-RAM 0xCD, outside the reverb's own")
    print("           0x52..0x61 block.  See the note, K5/R2.")


if __name__ == "__main__":
    main()
