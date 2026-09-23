#!/usr/bin/env python3
#
# Q: two claims in this directory's README and in
#    HARDWARE-QUESTIONS-PENDING-FELIPE.md rest on a search whose boundary they
#    state. This is that search.
#
#    (a) "The only address in the CPU's on-chip peripheral page that any of these
#         images loads into a pointer register is 0x20000070" -- which is what
#         rules out a pointer-relative write to IVAR hiding from the abs32 scan
#         in vector_table_layout.py, and so what makes 'IVAR is written zero once
#         and never again' a measurement rather than an assumption.
#
#    (b) "A 16-bit register at 0x20000070 is written 0x30 then 0x03 early in
#         reset, has bit 7 set on the instruction immediately before IVAR0..IVAR6
#         are cleared, and has bits 0 and 1 cleared later, each inside a short
#         setlb delay loop" -- the candidate mechanism for the board's vector
#         base re-decode, parked for hardware.
#
# A (measured, all five images): (a) holds -- 0x20000070 is the only one. (b) is
#    reported site by site below; read the printed immediates, not a summary.
#
#    The peripheral page is 0x20000000-0x3FFFFFFF (Matsushita MN1030/MN103S
#    instruction manual, AM32 memory map, p.13). This scans the low 256 bytes of
#    it, which is where the CPU's own register block lives: IVAR0-IVAR6 at
#    +0x00..+0x18, and per GNU's dv-mn103cpu.c an IMCR at +0x20 and a CPUM at
#    +0x40. 0x20000070 is past everything that model covers, so it belongs to
#    the MN103002A's own complement, for which no manual is in hand.
#
# USAGE
#   python3 peripheral_page_probe.py [<romset-dir>]
#
# PASS CRITERION (exit 0)
#   Every image: 0x20000070 is the ONLY pointer base in 0x20000000-0x200000FF.
#   Any other would mean the IVAR block could be written through a pointer, and
#   the single-vector model would have to be re-derived.
#
# POSITIVE CONTROL
#   --selftest plants a `mov 0x20000004,a0` in a copy and requires the check to
#   report it.
#
import glob
import os
import struct
import sys
import zipfile

BASE = 0x48400000
PAGE_LO, PAGE_HI = 0x20000000, 0x200000FF
IVAR_ADDRS = [0x20000000 + n * 4 for n in range(7)]


def deinterleave(zpath):
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        ev = [n for n in names if 'program_even' in n]
        od = [n for n in names if 'program_odd' in n]
        if not (ev and od):
            return None
        e, o = z.read(ev[0]), z.read(od[0])
    img = bytearray(len(e) + len(o))
    img[0::4], img[1::4] = e[0::2], e[1::2]
    img[2::4], img[3::4] = o[0::2], o[1::2]
    return bytes(img)


def pointer_loads(img):
    """(a) every `mov imm32,aN` whose immediate lands in the low peripheral page."""
    out = []
    for off in range(len(img) - 6):
        if img[off] == 0xFC and 0xDC <= img[off + 1] <= 0xDF:
            v = struct.unpack_from('<I', img, off + 2)[0]
            if PAGE_LO <= v <= PAGE_HI:
                out.append((BASE + off, v, img[off + 1] - 0xDC))
    return out


def describe(img, off, window=0x18):
    """(b) what the instructions after a pointer load do to the register.

    Only the four idioms these images use, named rather than fully decoded:
      FC CC <imm32>  mov imm32,d0      -- a whole value written
      F8 E4 <imm8>   or  imm8,d0       -- bits SET
      FA E0 <imm16>  and imm16,d0      -- bits CLEARED (report the complement)
      DB             setlb             -- the delay loop
    """
    acts = []
    i = off + 6
    end = min(len(img) - 4, off + 6 + window)
    while i < end:
        if img[i] == 0xFC and img[i + 1] == 0xCC:
            acts.append('write %#x' % struct.unpack_from('<I', img, i + 2)[0]); i += 6; continue
        if img[i] == 0xF8 and img[i + 1] == 0xE4:
            acts.append('SET bits %#04x' % img[i + 2]); i += 3; continue
        if img[i] == 0xFA and img[i + 1] == 0xE0:
            m = struct.unpack_from('<H', img, i + 2)[0]
            acts.append('CLEAR bits %#06x' % ((~m) & 0xFFFF)); i += 4; continue
        if img[i] == 0xDB:
            acts.append('setlb loop'); i += 1; continue
        i += 1
    # does a run of IVAR stores begin within 16 bytes after this site?
    ivar_next = any(img[j] == 0xFC and img[j + 1] == 0x87
                    and struct.unpack_from('<I', img, j + 2)[0] in IVAR_ADDRS
                    for j in range(off + 6, min(len(img) - 6, off + 6 + 0x18)))
    if ivar_next:
        acts.append('** the IVAR0..IVAR6 run starts here **')
    return acts


def check(img, quiet=False):
    p = (lambda *a: None) if quiet else print
    bad = []
    loads = pointer_loads(img)
    bases = sorted({v for _, v, _ in loads})
    p('  pointer bases in %08X-%08X: %s'
      % (PAGE_LO, PAGE_HI, ', '.join('%08X' % b for b in bases) or 'none'))
    if [b for b in bases if b != 0x20000070]:
        bad.append('a pointer base other than 0x20000070: %s'
                   % ', '.join('%08X' % b for b in bases if b != 0x20000070))
    for a, v, r in loads:
        if v != 0x20000070:
            continue
        acts = describe(img, a - BASE)
        if acts:
            p('     %08X  mov %#010x,a%d  ->  %s' % (a, v, r, '; '.join(acts)))
    return bad


def selftest(img):
    m = bytearray(img)
    for off in range(len(m) - 6):                   # overwrite a real site's base
        if m[off] == 0xFC and m[off + 1] == 0xDC and \
           struct.unpack_from('<I', m, off + 2)[0] == 0x20000070:
            struct.pack_into('<I', m, off + 2, 0x20000004)
            break
    bad = check(bytes(m), quiet=True)
    hit = any('other than 0x20000070' in b for b in bad)
    print('POSITIVE CONTROL -- a planted pointer to IVAR1 reported: %s' % hit)
    return hit


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root = args[0] if args else os.path.expanduser('~/compartilhado/technics_romsets')
    images = []
    for zp in sorted(glob.glob(os.path.join(root, '*.zip'))):
        img = deinterleave(zp)
        if img:
            images.append((os.path.basename(zp), img))
    if not images:
        print('no romsets with program_even/program_odd under %s' % root)
        return 2
    if '--selftest' in sys.argv:
        return 0 if selftest(images[0][1]) else 1
    failures = 0
    for name, img in images:
        print('== %s' % name)
        bad = check(img)
        for b in bad:
            print('  FAIL: %s' % b)
        failures += len(bad)
    print('\n%s' % ('PASS' if not failures else 'FAIL: %d problem(s)' % failures))
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
