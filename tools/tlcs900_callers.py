#!/usr/bin/env python3
"""Find the real callers of a TLCS-900 routine, decoding BOTH call forms.

WHY THIS EXISTS: this project has repeatedly concluded that "static caller search does not work
in these ROMs" and fallen back to runtime stack dumps. That is half true. The KN5000's firmware
reaches most routines with the RELATIVE call `calr`, whose operand is a displacement, not an
address -- so searching for the target's absolute bytes finds nothing and the routine looks
unreachable. Searching for the *displacement* finds it immediately.

Two encodings, both decoded here (verified against unidasm on this firmware):

    1d ll mm hh        CALL  addr24      absolute, little-endian
        ef08db: 1d 9f 6a f8   call 0xf86a9f
    1e dd dd           CALR  disp16      relative to the address AFTER the 3-byte instruction
        ef0580: 1e bb 02      calr 0xef083e      (0xEF0583 + 0x02BB = 0xEF083E)

    python3 tools/tlcs900_callers.py 0xF86D86
    python3 tools/tlcs900_callers.py 0xEF083E --image /path/to/rom --base 0xE00000
    python3 tools/tlcs900_callers.py 0xEF08D4 --vectors    # also check the exception vectors

VALIDATION -- the case that motivated it. A previous session investigating why the KN5000 Feature
Presentation plays only one song traced the demo countdown timer to 0xF86D86 and recorded:

    "A static search for absolute `call 0xF86D86` (1d 86 6d f8) and for any 24-bit reference
     returned ZERO -- it is entered by calr, exactly like the stop routine."

and resorted to a runtime stack dump, which pointed at 0xF86B7C. This tool finds that caller
statically. If it ever stops doing so, something about the encoding assumptions has changed and
the tool is wrong, not the firmware.

⚠ LIMITS, so a null is not over-read:
  * It scans the byte stream linearly and cannot tell code from data -- a table can contain bytes
    that decode as a call. Treat hits as candidates and confirm with unidasm.
  * Computed/indirect calls (through a register or a jump table) are invisible to any static scan.
    "0 callers" therefore means "no DIRECT caller", never "dead".
  * Displacements are taken from the end of the instruction, which is what the disassembler agrees
    with on every case checked here.
"""
import argparse
import pathlib
import struct
import sys

DEFAULT_IMAGE = "/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/kn5000_v10_program.rom"


def scan(d, base, target):
    """Return (absolute_hits, relative_hits, stored_pointers)."""
    absolute, relative, pointers = [], [], []

    # 1d ll mm hh -- CALL addr24
    pat = bytes([0x1D, target & 0xFF, (target >> 8) & 0xFF, (target >> 16) & 0xFF])
    i = d.find(pat)
    while i >= 0:
        absolute.append(base + i)
        i = d.find(pat, i + 1)

    # 1e dd dd -- CALR disp16, relative to the address AFTER the instruction
    for i in range(len(d) - 2):
        if d[i] != 0x1E:
            continue
        disp = struct.unpack_from("<h", d, i + 1)[0]
        if base + i + 3 + disp == target:
            relative.append(base + i)

    # a bare 24-bit pointer to it (jump tables, task descriptors)
    p3 = bytes([target & 0xFF, (target >> 8) & 0xFF, (target >> 16) & 0xFF])
    i = d.find(p3)
    while i >= 0:
        # skip the ones that are the operand of the CALLs we already counted
        if (base + i - 1) not in absolute:
            pointers.append(base + i)
        i = d.find(p3, i + 1)

    return absolute, relative, pointers


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="routine address, e.g. 0xF86D86")
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--base", default="0xE00000",
                    help="CPU address the image is mapped at (KN5000 program ROM: 0xE00000)")
    ap.add_argument("--vectors", action="store_true",
                    help="also report whether the address appears in the low exception-vector area")
    args = ap.parse_args()

    target = int(args.target, 0)
    base = int(args.base, 0)
    d = pathlib.Path(args.image).read_bytes()

    print(f"image {args.image} ({len(d)} B) mapped at 0x{base:06X}")
    print(f"callers of 0x{target:06X}\n")

    absolute, relative, pointers = scan(d, base, target)

    if absolute:
        print(f"{len(absolute)} absolute CALL site(s)  [1d addr24]:")
        for a in absolute:
            print(f"   0x{a:06X}")
    else:
        print("no absolute CALL sites")

    if relative:
        print(f"\n{len(relative)} relative CALR site(s)  [1e disp16]  <-- the ones a naive search misses:")
        for a in relative:
            print(f"   0x{a:06X}   (disp {target - (a + 3):+d})")
    else:
        print("\nno relative CALR sites")

    if pointers:
        print(f"\n{len(pointers)} stored 24-bit pointer(s):")
        for a in pointers[:20]:
            print(f"   0x{a:06X}")
        if len(pointers) > 20:
            print(f"   ... and {len(pointers) - 20} more")
    else:
        print("\nno stored 24-bit pointers")

    total = len(absolute) + len(relative)
    print(f"\n{total} direct call site(s) total.")
    if total == 0:
        print("⚠ That means no DIRECT caller, NOT that the routine is dead: computed and")
        print("  table-dispatched calls are invisible to a static scan, and this firmware uses them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
