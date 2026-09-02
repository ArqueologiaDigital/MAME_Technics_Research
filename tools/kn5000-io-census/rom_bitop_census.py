#!/usr/bin/env python3
"""Count TLCS-900 bit operations on an 8-bit-direct SFR, in the RAW ROM bytes.

Question it answers: "is the source census COMPLETE, or did the disassembler
frame some of this port's traffic as data and hide it from me?"

The source trees are excellent but they are a FRAMING, and a port claim that
rests on a framing inherits its mistakes -- data misframed as code invents
accesses, and code misframed as data hides them.  This scans the ROM image
itself for the three-byte encodings

    F0 <addr> C8+b   BIT b,(nn)
    F0 <addr> B8+b   SET b,(nn)
    F0 <addr> B0+b   RES b,(nn)

which need no framing at all.  Run it beside sfr_census.py: agreement means the
source census is complete for that bit; a surplus here means the tree has that
site framed as data; a surplus there means the tree invented it.

The F0 prefix (8-bit direct memory operand) was confirmed against the project's
own unidasm listing, e.g.

    ef05a6: f0 38 c8    bit 0,(0x38)      <- Boot_FlashAndExtensions, PE.0

⚠ A byte match is NOT proof of an instruction: the same three bytes occur inside
data.  This instrument answers "how many candidates exist", and it is only
decisive when it AGREES with the source census.  Where the counts differ, go and
look at the address it prints.

Usage:
    ./rom_bitop_census.py PD.6 PH.0 PG PE.5 -- <rom> [<rom> ...]
    ./rom_bitop_census.py --all-bits PD -- ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v*_program.rom

Port names and their SFR addresses come from the disassembly's own header,
kn5000-roms-disasm/v10/maincpu/shared/sfr_tmp94c241.s.  PG is 0x40 and PZ is
0x68 -- if a claim names a port and a register number that disagree, one of them
is invented.
"""
import argparse
import re
import sys

PORTS = {'P0': 0x00, 'P1': 0x04, 'P2': 0x08, 'P3': 0x0C, 'P4': 0x10, 'P5': 0x14,
         'P6': 0x18, 'P7': 0x1C, 'P8': 0x20, 'PA': 0x28, 'PB': 0x2C, 'PC': 0x30,
         'PD': 0x34, 'PE': 0x38, 'PF': 0x3C, 'PG': 0x40, 'PH': 0x44, 'PZ': 0x68,
         'T8RUN': 0x80, 'T16RUN': 0x9E, 'INTES1': 0xEB, 'INTCLR': 0xF8}
OPS = (('BIT', 0xC8), ('SET', 0xB8), ('RES', 0xB0))


def scan(data, addr, bit):
    out = {}
    for name, base in OPS:
        pat = bytes((0xF0, addr, base + bit))
        out[name] = [m.start() for m in re.finditer(re.escape(pat), data)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('targets', nargs='+',
                    help='PORT.BIT (e.g. PD.6), or PORT with --all-bits')
    ap.add_argument('--all-bits', action='store_true')
    ap.add_argument('--base', type=lambda v: int(v, 0), default=0,
                    help='ROM load address, added to the printed offsets '
                         '(the KN5000 main program image maps at 0xE00000)')
    ap.add_argument('--roms', nargs='+', required=True)
    a = ap.parse_args()

    for rom in a.roms:
        data = open(rom, 'rb').read()
        print('== %s (%d bytes)' % (rom, len(data)))
        for t in a.targets:
            if a.all_bits:
                port, bits = t.upper(), range(8)
            else:
                port, _, b = t.upper().partition('.')
                bits = [int(b)]
            if port not in PORTS:
                sys.exit('unknown port %r' % port)
            for bit in bits:
                r = scan(data, PORTS[port], bit)
                tot = sum(len(v) for v in r.values())
                if a.all_bits and tot == 0:
                    continue
                print('  %s.%d (0x%02X)  %s' % (
                    port, bit, PORTS[port],
                    '  '.join('%s x%d%s' % (
                        n, len(v),
                        ' @' + ','.join('%06X' % (a.base + o) for o in v[:6]) if v else '')
                        for n, v in r.items())))


if __name__ == '__main__':
    main()
