#!/usr/bin/env python3
"""Find the real callers of an MN10300 routine, by decoding call instructions.

WHY THIS EXISTS — an off-by-two that makes "dead code" verdicts unreliable:

    4849fd9e: cf c0   movm [d2,d3], (sp)   <- the function ENTRY
    4849fda0: 0c      clr  d3
    ...
    4849fe30: cd 70 ff c0 08   call 0x4849fda0, [d2,d3], 8    <- the caller enters at +2

MN10300's `call target, [regs], size` saves the listed registers *as part of the call*, so the
compiler emits callers that jump PAST the callee's own `movm` prologue. Searching for the entry
address therefore finds nothing, and a routine with real callers looks unreachable.

That already produced a wrong conclusion in this project: `0x4849FD9E` was recorded as having
"0 callers and 0 stored pointers — unreachable", when `MainRomTestFunc` calls it at `+2`.

    python3 tools/mn10300_callers.py 0x4849FD9E
    python3 tools/mn10300_callers.py 0x484A4FBA --image /path/to/other.bin --base 0x48400000
    python3 tools/mn10300_callers.py 0x4849FD9E --skew 0,2,4   # entry, +2, +4

It decodes every `call` in the image and reports those whose target lands on the address or any
requested skew, plus any stored 32-bit pointer to it (jump tables, task descriptors).

Encodings decoded (MN10300 / AM33):
    0xCD imm16 regs u8 size u8   -- call (d16,PC)
    0xDD imm32 regs u8 size u8   -- call (d32,PC)
    0xF0 0xF4 / 0xF0 0xF5        -- calls (An)  : indirect, reported as a COUNT only, since the
                                                  target is a register and cannot be resolved here

⚠ LIMITS, so a null from this is not over-read: displacements are PC-relative from the opcode
byte, which is what the disassembler agrees with on the cases checked, but this decodes the
stream linearly and does not know code from data — a byte sequence inside a table can look like
a call. Treat hits as candidates and confirm with tools/dis.sh. And an indirect `calls (An)`
target is invisible to any static scan, so "0 direct callers" still never proves dead.
"""
import argparse
import pathlib
import struct
import sys

DEFAULT_IMAGE = "/home/fsanches/compartilhado/kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin"


def decode_calls(d, base):
    """Yield (site, target) for every direct call in the image."""
    for i in range(len(d) - 6):
        op = d[i]
        if op == 0xCD:
            disp = struct.unpack_from("<h", d, i + 1)[0]
        elif op == 0xDD:
            disp = struct.unpack_from("<i", d, i + 1)[0]
        else:
            continue
        yield base + i, base + i + disp


def do_range(image, base, lo, hi):
    d = pathlib.Path(image).read_bytes()
    calls = {}
    for site, tgt in decode_calls(d, base):
        if lo <= tgt <= hi:
            calls.setdefault(tgt, []).append(site)
    if not calls:
        print(f"no direct calls land in 0x{lo:08X}..0x{hi:08X}")
        return 0
    print(f"{len(calls)} distinct call target(s) in 0x{lo:08X}..0x{hi:08X}:\n")
    for tgt in sorted(calls):
        sites = calls[tgt]
        inside = sum(1 for s in sites if lo <= s <= hi)
        note = f"   ({inside} of them from inside the window)" if inside else ""
        print(f"  0x{tgt:08X}  <- {len(sites)} call site(s){note}")
        for s in sorted(sites)[:6]:
            print(f"        from 0x{s:08X}")
        if len(sites) > 6:
            print(f"        ... and {len(sites) - 6} more")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", nargs="?", help="routine address, e.g. 0x4849FD9E")
    ap.add_argument("--range", dest="rng",
                    help="LO,HI instead of a single target: report every call target landing in "
                         "that window, grouped by callee. Maps a family of routines and their "
                         "callers in one pass -- useful when the entry addresses are unknown.")
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--base", default="0x48400000")
    ap.add_argument("--skew", default="0,2",
                    help="comma-separated entry offsets to accept (default 0,2 -- MN10300 callers "
                         "commonly enter at +2, past the movm prologue)")
    args = ap.parse_args()

    base = int(args.base, 0)
    if args.rng:
        lo, hi = [int(x, 0) for x in args.rng.split(",")]
        return do_range(args.image, base, lo, hi)
    if not args.target:
        print("give a target address or --range LO,HI", file=sys.stderr)
        return 2
    target = int(args.target, 0)
    skews = [int(x, 0) for x in args.skew.split(",")]
    wanted = {target + s: s for s in skews}

    d = pathlib.Path(args.image).read_bytes()
    print(f"image {args.image} ({len(d)} B) mapped at 0x{base:08X}")
    print(f"looking for calls to 0x{target:08X} at skew(s) {', '.join(f'+{s}' for s in skews)}\n")

    hits, indirect = [], 0
    for i in range(len(d) - 6):
        op = d[i]
        if op == 0xCD:
            disp = struct.unpack_from("<h", d, i + 1)[0]
            tgt = base + i + disp
        elif op == 0xDD:
            disp = struct.unpack_from("<i", d, i + 1)[0]
            tgt = base + i + disp
        elif op == 0xF0 and d[i + 1] in (0xF4, 0xF5):
            indirect += 1
            continue
        else:
            continue
        if tgt in wanted:
            hits.append((base + i, tgt, wanted[tgt]))

    ptrs = []
    for s in skews:
        pat = struct.pack("<I", target + s)
        off = d.find(pat)
        while off >= 0:
            ptrs.append((base + off, target + s))
            off = d.find(pat, off + 1)

    if hits:
        print(f"{len(hits)} direct call site(s):")
        for site, tgt, skew in hits:
            print(f"   0x{site:08X}  ->  0x{tgt:08X}   (entry+{skew})")
    else:
        print("no direct call sites found")
    if ptrs:
        print(f"\n{len(ptrs)} stored pointer(s):")
        for site, tgt in ptrs:
            print(f"   0x{site:08X}  holds 0x{tgt:08X}")
    else:
        print("\nno stored pointers")

    print(f"\n(image contains {indirect} indirect `calls (An)` sites; their targets are registers "
          f"and cannot be resolved statically, so absence of direct callers is never proof of "
          f"dead code)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
