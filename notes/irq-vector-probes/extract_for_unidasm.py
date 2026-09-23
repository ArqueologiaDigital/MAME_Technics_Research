#!/usr/bin/env python3
#
# Q: how do I disassemble an address range of a Technics MN10300 romset?
#
# A: unidasm does NOT seek -- it disassembles a file from its first byte -- and
#    the romsets are stored as two interleaved 16-bit halves, so neither half is
#    disassemblable on its own. This de-interleaves the way the driver's
#    ROM_LOAD32_WORD does (even half supplies bytes 0,1 of each 32-bit word, odd
#    half bytes 2,3; the image loads at 0x48400000) and writes the requested
#    window to a file for unidasm to read.
#
# Every disassembly quoted in this directory's README and in
# HARDWARE-QUESTIONS-PENDING-FELIPE.md was produced with this:
#
#   python3 extract_for_unidasm.py ~/compartilhado/technics_romsets/kn7000.zip \
#           0x48410040 0xC0 /tmp/w.bin
#   ~/compartilhado/mame/unidasm /tmp/w.bin -arch mn10300 -basepc 0x48410040
#
# which prints, among others, the seven IVAR stores and the `clr d1` that feeds
# them:
#
#   484100a3: 04                    clr     d1
#   484100a4: fc 87 00 00 00 20     movhu   d1, (0x20000000)
#   ...
#   484100c8: fc 87 18 00 00 20     movhu   d1, (0x20000018)
#
# and, at 0x48400000 with length 0x40, the ROM vector table.
#
import sys
import zipfile

BASE = 0x48400000


def deinterleave(zpath):
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        ev = [n for n in names if 'program_even' in n]
        od = [n for n in names if 'program_odd' in n]
        if not (ev and od):
            raise SystemExit('%s has no program_even/program_odd' % zpath)
        e, o = z.read(ev[0]), z.read(od[0])
    img = bytearray(len(e) + len(o))
    img[0::4], img[1::4] = e[0::2], e[1::2]
    img[2::4], img[3::4] = o[0::2], o[1::2]
    return bytes(img)


def main():
    if len(sys.argv) != 5:
        raise SystemExit('usage: %s <romset.zip> <start-addr> <length> <out.bin>'
                         % sys.argv[0])
    zpath, start, length, out = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0), sys.argv[4]
    img = deinterleave(zpath)
    off = start - BASE
    if not (0 <= off < len(img)):
        raise SystemExit('%#x is outside the %d KiB image at %#x'
                         % (start, len(img) // 1024, BASE))
    open(out, 'wb').write(img[off:off + length])
    print('wrote %#x bytes of %s from %#x to %s' % (length, zpath, start, out))
    print('  unidasm %s -arch mn10300 -basepc %#x' % (out, start))


if __name__ == '__main__':
    main()
