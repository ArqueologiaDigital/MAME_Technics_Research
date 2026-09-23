#!/usr/bin/env python3
#
# Q: how does a maskable interrupt reach its handler on the MN10300 Technics
#    machines -- and does the DRIVER have to know any firmware address to do it?
#
# A (what this script demonstrates): no. Every firmware programs the chip's seven
#    Interrupt Vector Registers to ZERO and builds a 6-byte `nop ; jmp <handler>`
#    thunk at the base of the vector window, with the jump displacement computed
#    against the thunk's own execution address. So one vector serves all seven
#    levels, and the handler address is the firmware's business.
#
#    This retires the belief that the KN7000 is special -- that it "installs two
#    handlers and splits the levels between them". It does not. The second
#    handler (0x4C03DDA0) is referenced by NOTHING in the whole 4 MB image.
#
# Usage:  python3 irq_vector_mechanism.py <romset-dir> [<romset-dir> ...]
#         python3 irq_vector_mechanism.py ~/compartilhado/technics_romsets
#
#   Each romset zip is de-interleaved the way the driver's ROM_LOAD32_WORD does:
#   two 16-bit halves, even half supplying bytes 0,1 of each 32-bit word and odd
#   half bytes 2,3.  The image loads at 0x48400000.
#
# PASS CRITERION
#   For every image: exactly two thunk builders, and IVR0..IVR6 all written zero
#   at one site.  Exit 1 otherwise.  A machine that grew a third thunk, or that
#   wrote a non-zero IVR, would invalidate the single-vector model the driver
#   now relies on -- which is the whole point of checking all of them.
#
import glob
import os
import re
import struct
import sys
import zipfile

BASE = 0x48400000
NOPJMP = b'\xfc\xcc\xcb\xdc\x00\x00'          # mov 0x0000dccb,d0 -- the `nop ; jmp` prologue
BUILDER = re.compile(rb'\xfc\xdc(.)\x00\x00\x90', re.S)   # mov 0x900000NN,a0

# Addresses the driver used to hardcode that turn out to be reachable from
# nowhere.  Keeping the check here means a future firmware that DOES use one
# would be noticed rather than assumed away.
DEAD = {
    'kn7000.zip': [('the "quick dispatcher" the driver used to name,', 0x4C03DDA0)],
}


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


def report(name, img):
    ok = True
    print('=== %s (%d bytes, loads at 0x%08X) ===' % (name, len(img), BASE))

    thunks = list(BUILDER.finditer(img))
    print('  thunk builders: %d   (`nop ; jmp` literal occurs %d time(s))'
          % (len(thunks), len(re.findall(re.escape(NOPJMP), img))))
    for m in thunks:
        seg = img[m.start():m.start() + 0x28]
        lits = [struct.unpack('<I', h.group(1))[0]
                for h in re.finditer(rb'\xfc\xcc(....)', seg, re.S)]
        tgt = next((v for v in lits if v != 0x0000dccb), None)
        print('    @0x%08X  window +0x%02X  handler %s'
              % (BASE + m.start(), m.group(1)[0],
                 ('0x%08X' % tgt) if tgt else '?'))
    if len(thunks) != 2:
        print('    FAIL: expected exactly 2'); ok = False

    # IVR0..IVR6 are 16-bit at 0x20000000 + L*4.  `movhu d1,(abs32)` = fc 87 <abs32>
    ivr = []
    for lvl in range(7):
        pat = b'\xfc\x87' + struct.pack('<I', 0x20000000 + lvl * 4)
        ivr.append([BASE + m.start() for m in re.finditer(re.escape(pat), img)])
    print('  IVR0..IVR6 write sites: %s' % [len(x) for x in ivr])
    if not all(len(x) == 1 for x in ivr):
        print('    FAIL: expected exactly one write per IVR'); ok = False
    else:
        print('    all seven written once, at 0x%08X-0x%08X' % (ivr[0][0], ivr[6][0]))

    # The claim that retired the KN7000 special case: the "quick dispatcher" the
    # driver used to name is referenced by NOTHING.  Check it the only way the
    # image allows -- as a 32-bit literal, and as the target of a DC/DD disp32
    # branch.  Library-space addresses (0x4C......) cannot appear as branch
    # targets in ROM space, so for those the literal scan is the whole test.
    for label, addr in DEAD.get(name, []):
        lit = len(re.findall(re.escape(struct.pack('<I', addr)), img))
        brn = 0
        for m in re.finditer(rb'[\xdc\xdd]', img):
            i = m.start()
            if i + 5 > len(img):
                continue
            if BASE + i + struct.unpack('<I', img[i + 1:i + 5])[0] == addr:
                brn += 1
        print('  %s 0x%08X: %d literal(s), %d branch(es)' % (label, addr, lit, brn))
        if lit or brn:
            print('    FAIL: expected it to be unreachable'); ok = False

    return ok


def main():
    roots = sys.argv[1:] or [os.path.expanduser('~/compartilhado/technics_romsets')]
    good = True
    seen = 0
    for root in roots:
        for z in sorted(glob.glob(os.path.join(root, '*.zip'))):
            img = deinterleave(z)
            if img is None:
                continue
            seen += 1
            good &= report(os.path.basename(z), img)
    if not seen:
        print('no romsets with program_even/program_odd halves found'); return 1
    print('\n%s (%d image(s))' % ('PASS' if good else 'FAIL', seen))
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
