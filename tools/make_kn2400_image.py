#!/usr/bin/env python3
"""Build the flat KN2400/KN2600 program image from the even/odd ROM halves.

WHY THIS IS NEEDED: the KN2400 ships as two 2 MB files loaded with ROM_LOAD32_WORD at
offsets 0 and 2 — a 16-bit-word interleave, not two contiguous halves. Disassembling either
file on its own yields plausible-looking instructions that are entirely wrong, which is the
worst kind of wrong. tools/dis.sh defaults to the KN7000 image; the KN2400/KN2600/PR54 run a
DIFFERENT firmware (one shared LKG program, no separate table flash), so it needs this.

    python3 tools/make_kn2400_image.py -o /tmp/kn2400_flat.bin
    BIN=/tmp/kn2400_flat.bin ./tools/dis.sh 0x4860C250 80

The image is 4 MB and maps at 0x48400000, so file offset = address - 0x48400000.

SANITY CHECK, printed on every run: the reset vector at 0x48400000 must disassemble as a
`jmp` into the program ROM range. Measured 2026-08-15 it is `dc df 5b 30 00` =
`jmp 0x48705bdf`. If the first byte is not 0xDC the halves are swapped or the interleave
width is wrong — stop rather than disassemble nonsense.

Used by notes/FINDINGS-kn2400-table-rom.md to disassemble the table-ROM copy loop at
0x4860C274.
"""
import argparse
import hashlib
import pathlib
import sys

DEFAULT_ROMS = pathlib.Path("/home/fsanches/compartilhado/kn7000-emulator/roms/kn2400")

# From the driver's ROM_START(kn2400).
EXPECT = {
    "kn2400_program_even.rom": "86d5d9916afdb90f82de78064b1d76fce3a21d7b",
    "kn2400_program_odd.rom": "d90a3560561efd94322dca1a6710f2d5d3837cd2",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-r", "--roms", type=pathlib.Path, default=DEFAULT_ROMS,
                    help="directory holding the two halves")
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True)
    args = ap.parse_args()

    halves = {}
    for name, sha in EXPECT.items():
        p = args.roms / name
        if not p.is_file():
            print(f"missing: {p}", file=sys.stderr)
            return 1
        data = p.read_bytes()
        got = hashlib.sha1(data).hexdigest()
        # Report rather than refuse: a re-dump is a legitimate reason for a mismatch, but it
        # must not pass silently -- every address in the findings note assumes these bytes.
        print(f"{name}: {len(data)} B sha1={got}"
              + ("" if got == sha else f"  ⚠ EXPECTED {sha}"))
        halves[name] = data

    e = halves["kn2400_program_even.rom"]
    o = halves["kn2400_program_odd.rom"]
    if len(e) != len(o):
        print(f"halves differ in size: {len(e)} vs {len(o)}", file=sys.stderr)
        return 1

    out = bytearray(len(e) * 2)
    for i in range(0, len(e), 2):
        out[i * 2:i * 2 + 2] = e[i:i + 2]
        out[i * 2 + 2:i * 2 + 4] = o[i:i + 2]

    if out[0] != 0xDC:
        print(f"⚠ reset vector starts 0x{out[0]:02X}, expected 0xDC (jmp). The interleave is "
              f"probably wrong -- do NOT disassemble this image.", file=sys.stderr)
        return 1

    # MN10300 `jmp (d32)` is PC-RELATIVE: target = PC + disp, and here PC is the map base.
    # Decoding the operand as an absolute address gives 0x00305BDF and a spurious warning --
    # a check that cries wolf is worse than no check, so this is deliberate.
    BASE = 0x48400000
    disp = int.from_bytes(out[1:5], "little")
    target = BASE + disp
    print(f"reset vector: jmp 0x{target:08X}  (disp 0x{disp:08X} from 0x{BASE:08X})"
          + ("  -- in program ROM, sane" if BASE <= target <= 0x487FFFFF
             else "  ⚠ OUTSIDE the program ROM range"))

    args.out.write_bytes(bytes(out))
    print(f"wrote {args.out}: {len(out)} B (maps at 0x48400000)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
