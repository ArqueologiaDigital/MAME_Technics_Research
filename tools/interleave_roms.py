#!/usr/bin/env python3
"""Rebuild a flat program image from the even/odd ROM halves MAME loads.

QUESTION IT ANSWERS
  "What bytes does the CPU actually see?"

  The MN10300 machines put their program across a PAIR of 16-bit flash devices
  on alternating halfwords, so a romset holds ..._even.icNN and ..._odd.icNN
  and neither one disassembles on its own.  Anything that reads the firmware
  linearly -- unidasm, a byte search for a literal, comparing one model's
  routine against another's -- needs the two woven back together first.

  ROM_LOAD32_WORD in the driver does this inside MAME.  This does the same
  thing outside it, so a search can be run without the emulator.

WHAT IT PRODUCES
  interleave(even, odd) -> out, with even supplying byte 0, 2, 4 ... and odd
  supplying 1, 3, 5 ...  That is the byte order ROM_LOAD32_WORD(even, 0x000000)
  + ROM_LOAD32_WORD(odd, 0x000002) produces, which is why the reset vector at
  file offset 0 reads back as `jmp 0x48407EFF`.

  The output is a raw image whose offset 0 is CPU address 0x48400000 for a
  program ROM, so a CPU address maps to a file offset as addr - 0x48400000.

RUN
  python3 tools/interleave_roms.py EVEN ODD OUT
  python3 tools/interleave_roms.py --set kn7000 -C <romdir>   # the usual pairs

  Then, e.g.:
  unidasm kn7000_prog.bin -arch mn10300 -basepc 0x48400000 | less

PASS CRITERION
  The two halves must be the same size, and the result twice that size.  Both
  are asserted: a mismatched pair is a wrong romset, not something to weave
  anyway.  --set additionally checks the KN7000 program image begins with the
  reset jump, which is a positive control that the halves are the right way
  round -- swapping them produces a plausible-looking file that disassembles
  to nonsense, and nothing else in the output announces the mistake.
"""
import argparse
import os
import sys

# (label, even, odd) per romset, as the driver's ROM_LOAD32_WORD pairs them.
# Upstream names each half after its chip; this overlay's older romsets use a
# plain .rom suffix. Either is accepted, upstream's tried first.
SETS = {
    'kn7000': [('prog',  ['kn7000_program_even.ic17', 'kn7000_program_even.rom'],
                         ['kn7000_program_odd.ic16',  'kn7000_program_odd.rom']),
               ('table', ['kn7000_table_even.ic17',   'kn7000_table_even.rom'],
                         ['kn7000_table_odd.ic16',    'kn7000_table_odd.rom'])],
    'kn6000': [('prog',  ['kn6000_program_even.ic12', 'kn6000_program_even.rom'],
                         ['kn6000_program_odd.ic11',  'kn6000_program_odd.rom'])],
    'kn6500': [('prog',  ['kn6500_program_even.ic12', 'kn6500_program_even.rom'],
                         ['kn6500_program_odd.ic11',  'kn6500_program_odd.rom'])],
    'kn2400': [('prog',  ['kn2400_program_even.ic13', 'kn2400_program_even.rom'],
                         ['kn2400_program_odd.ic12',  'kn2400_program_odd.rom'])],
}


def first_existing(d, names):
    for n in names:
        p = os.path.join(d, n)
        if os.path.exists(p):
            return p
    return None

# `dc ff 7e 00 00` = jmp with a 32-bit little-endian PC-relative displacement
# (mn103dasm.cpp case 0xdc: pc + r32(pc+1)), so 0x48400000 + 0x7eff.
RESET_JUMP = bytes((0xdc, 0xff, 0x7e, 0x00, 0x00))   # jmp 0x48407EFF at offset 0


def interleave(even_path, odd_path, out_path):
    e = open(even_path, 'rb').read()
    o = open(odd_path, 'rb').read()
    if len(e) != len(o):
        sys.exit('halves differ in size (%d vs %d) -- wrong romset?' % (len(e), len(o)))
    b = bytearray(len(e) + len(o))
    b[0::2] = e
    b[1::2] = o
    assert len(b) == 2 * len(e)
    open(out_path, 'wb').write(bytes(b))
    return bytes(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('even', nargs='?')
    ap.add_argument('odd', nargs='?')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--set', choices=sorted(SETS), help='weave a known romset')
    ap.add_argument('-C', default='.', help='directory holding the romset (default: .)')
    a = ap.parse_args()

    if a.set:
        for label, evs, ods in SETS[a.set]:
            ep, op = first_existing(a.C, evs), first_existing(a.C, ods)
            if not (ep and op):
                print('  skip %-6s (%s missing)' % (label, evs[0]))
                continue
            out = '%s_%s.bin' % (a.set, label)
            img = interleave(ep, op, out)
            note = ''
            if a.set == 'kn7000' and label == 'prog':
                ok = img[:5] == RESET_JUMP
                note = '  reset jump: %s' % ('OK' if ok else 'NOT FOUND -- halves swapped?')
                if not ok:
                    print('  wrote %-22s %8d bytes%s' % (out, len(img), note))
                    sys.exit('the KN7000 program image does not start with its reset jump')
            print('  wrote %-22s %8d bytes%s' % (out, len(img), note))
        return 0

    if not (a.even and a.odd and a.out):
        ap.error('give EVEN ODD OUT, or --set')
    img = interleave(a.even, a.odd, a.out)
    print('wrote %s (%d bytes)' % (a.out, len(img)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
