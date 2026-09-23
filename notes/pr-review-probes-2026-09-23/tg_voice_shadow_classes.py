#!/usr/bin/env python3
"""What the KN7000 tone-generator register classes 0x1000/0x1400/0x1800/0x1C00/0x2000 carry.

Question it answers: the driver reads the firmware's per-slot voice record out of guest
work RAM to get the musical pitch (KN7000_VOICE_RECORDS & friends in kn7000.cpp).  The
proposed route out is "the TG must be told which sample to play, so decode the classes the
driver discards".  This probe reads the firmware's own note-on blit and shows exactly what
those classes carry -- and that none of them carries a root pitch.

Signals read (all static, from the dumped program flash):
  * lib 0x4C037398..0x4C037691  the note-on blit: one writer call per register, each
    destination OR-ed in as a literal -> the COMPLETE shadow-offset -> register-class map.
  * ROM 0x4858766C              the 0x84-byte shadow-image template the blit ships from.
  * lib 0x4C036F9A              the write primitive: word = (slot<<20)|class<<16|data,
    so bits 19:16 of a shadow word become the register-index nibble.
  * lib 0x4C00BC83              the shadow builder (0xB4 lib voice record -> 0x84 shadow).
  * lib 0x4C02FB7E              the note-on pitch16 calculator.

Usage:
  python3 tg_voice_shadow_classes.py --romset ~/compartilhado/technics_romsets
Exit 0 = every check matched.
"""
import argparse, os, struct, sys, zipfile

LIB_BASE, LIB_FILE_OFF = 0x4C000000, 0x3B8FD1   # lib X == program file 0x3B8FD1+(X-0x4C000000)
PROG_BASE = 0x48400000

def deinterleave(zf, even, odd):
    e, o = zf.read(even), zf.read(odd)
    b = bytearray(len(e) + len(o))
    for i in range(len(e) // 2):
        b[i*4:i*4+2] = e[i*2:i*2+2]
        b[i*4+2:i*4+4] = o[i*2:i*2+2]
    return bytes(b)

def off(addr):
    return LIB_FILE_OFF + addr - LIB_BASE if addr >= LIB_BASE else addr - PROG_BASE

def u32(d, a): return struct.unpack_from('<I', d, off(a))[0]
def count(d, v):
    b, n, i = struct.pack('<I', v), 0, 0
    while True:
        i = d.find(b, i)
        if i < 0: return n
        n += 1; i += 1

fails = []
def check(label, got, want):
    ok = got == want
    print(('  ok   ' if ok else '  FAIL ') + '%-58s %s' % (label, got if ok else '%s != %s' % (got, want)))
    if not ok: fails.append(label)

def scan_blit(d):
    """Walk 0x4C037398..0x4C037691 recovering (shadow offset, width, register class)."""
    a, end, out = 0x4C0373BC, 0x4C037691, []
    while a < end:
        o = off(a)
        if d[o] == 0xF8 and d[o+1] in (0x02, 0x62):        # mov/movhu (d8,a2),d0
            shoff, width, a2 = d[o+2], 32 if d[o+1] == 0x02 else 16, a + 3
        elif d[o] == 0xFA and d[o+1] == 0x02:              # mov (d16,a2),d0
            shoff, width, a2 = struct.unpack_from('<H', d, o+2)[0], 32, a + 4
        elif d[o] == 0xF0 and d[o+1] == 0x62:              # movhu (a2),d0
            shoff, width, a2 = 0, 16, a + 2
        else:
            a += 1; continue
        cls, b = None, off(a2)
        for _ in range(8):                                  # find the class literal for d1
            if d[b] == 0xFC and d[b+1] == 0xCD:
                cls = struct.unpack_from('<I', d, b+2)[0] >> 16; b += 6; break
            if d[b] == 0x04:                                # clr d1 -> class 0x0000
                cls = 0; b += 1; break
            b += 1
        if cls is not None:
            out.append((shoff, width, cls))
        a = a2
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--romset', default=os.path.expanduser('~/compartilhado/technics_romsets'))
    args = ap.parse_args()
    imgs = {}
    for s, e, o in (('kn7000', 'kn7000_program_even.ic17', 'kn7000_program_odd.ic16'),
                    ('kn6000', 'kn6000_program_even.ic12', 'kn6000_program_odd.ic11'),
                    ('kn6500', 'kn6500_program_even.ic12', 'kn6500_program_odd.ic11')):
        with zipfile.ZipFile(os.path.join(args.romset, s + '.zip')) as z:
            imgs[s] = deinterleave(z, e, o)
    d = imgs['kn7000']

    print('1. the note-on blit enumerates the whole map (lib 0x4C037398)')
    m = dict((o, (w, c)) for o, w, c in scan_blit(d))
    for shoff, cls in ((0x34, 0x1000), (0x38, 0x1400), (0x3C, 0x1800),
                       (0x40, 0x1C00), (0x44, 0x2000), (0x48, 0x2400)):
        check('shadow +0x%02X -> class 0x%04X, 32-bit' % (shoff, cls), m.get(shoff), (32, cls))

    print('2. the 0x84-byte ROM template the blit ships (0x4858766C)')
    for shoff, val in ((0x34, 0x00000000), (0x38, 0x00000000), (0x3C, 0x00000200),
                       (0x40, 0x00000002), (0x44, 0x00095FFF)):
        check('template +0x%02X' % shoff, '0x%08X' % u32(d, 0x4858766C + shoff), '0x%08X' % val)

    print('3. the write primitive puts shadow bits 19:16 in the register-index nibble')
    check('0x4C036FA4 asl 20,d0 (slot)', d[off(0x4C036FA4):off(0x4C036FA4)+3].hex(), 'f8c014')
    check('0x4C036FAC lsr 16,d1 -> addr latch', d[off(0x4C036FAC):off(0x4C036FAC)+3].hex(), 'f8c510')

    print('4. the shadow builder writes the wave index into +0x40 (class 0x1C00)')
    # 4c00bcd2 add 0x40,a2 ; 4c00bce0 and 0x0fff,d1 ; 4c00bcec mov d1,(a2)
    check('0x4C00BCD2 add 0x40,a2', d[off(0x4C00BCD2):off(0x4C00BCD2)+2].hex(), '2240')
    check('0x4C00BCE0 and 0x0fff,d1', d[off(0x4C00BCE0):off(0x4C00BCE0)+4].hex(), 'fae1ff0f')
    check('0x4C037C81 asl 12,d1 (bank code -> bits 19:12)',
          d[off(0x4C037C81):off(0x4C037C81)+3].hex(), 'f8c10c')
    check('0x4C037C84 and 0xfff00fff,d3', d[off(0x4C037C84):off(0x4C037C84)+6].hex(), 'fce3ff0ff0ff')

    print('5. pitch18 is built from pitch16, and pitch16 absorbs RAM-resident terms')
    # 4c00bd46 add 0x1800,d1 ; 4c00bd4a asl2 ; 4c00bd4b and 0x0003ffff
    check('0x4C00BD46 add 0x1800,d1', d[off(0x4C00BD46):off(0x4C00BD46)+4].hex(), 'fac10018')
    check('0x4C00BD4B and 0x0003ffff,d1', d[off(0x4C00BD4B):off(0x4C00BD4B)+6].hex(), 'fce1ffff0300')
    check('0x4C02FBAD movhu (0x500C075C),d0  [master tune, RAM]',
          d[off(0x4C02FBAD):off(0x4C02FBAD)+6].hex(), 'fcac5c070c50')
    check('0x4C02FBA4 add 0x500B5340,a0  [per-part pitch offset, RAM]',
          d[off(0x4C02FBA4):off(0x4C02FBA4)+6].hex(), 'fcd040530b50')

    print('6. class 0x2009 is the note-tracking companion, not a level')
    # 4c02e08c or 0x4000,d1 ; 4c02e099 and 0x1fff,d0 ; 4c02e0a4 mov 0x20000000,d1
    check('0x4C02E08C or 0x4000,d1', d[off(0x4C02E08C):off(0x4C02E08C)+4].hex(), 'fae50040')
    check('0x4C02E099 and 0x1fff,d0', d[off(0x4C02E099):off(0x4C02E099)+4].hex(), 'fae0ff1f')
    check('0x4C02E0A4 mov 0x20000000,d1', d[off(0x4C02E0A4):off(0x4C02E0A4)+6].hex(), 'fccd00000020')

    print('7. the three record bases are distinct link-time constants, not indirections')
    for img, base, want in (('kn7000', 0x500AF940, 76), ('kn6000', 0x5027AF28, 58),
                            ('kn6500', 0x5027AF1C, 58)):
        check('%s: 0x%08X occurrences' % (img, base), count(imgs[img], base), want)
    for img, base in (('kn6000', 0x500AF940), ('kn7000', 0x5027AF28), ('kn6500', 0x5027AF28)):
        check('%s: 0x%08X occurrences (cross)' % (img, base), count(imgs[img], base), 0)

    print('\n%s' % ('FAILED: ' + ', '.join(fails) if fails else 'PASS -- every check matched'))
    return 1 if fails else 0

sys.exit(main())
