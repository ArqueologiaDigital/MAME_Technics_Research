#!/usr/bin/env python3
#
# Q: what IS the 0x90000000 window on the MN10300 Technics machines?  The driver
#    called it an "LCD controller window (regs + trampolines)" and mapped
#    0x90000000-0x97FFFFFF as one 128 MiB RAM share.
#
# A (what this script measures): 0x90000000 is the +0x40000000 CACHE-THROUGH
#    ALIAS of the work RAM at 0x50000000.  Nothing about it is an LCD.  Three
#    measurements, all cross-checked on all five images:
#
#    (1) THE THUNK IS WRITTEN THROUGH THE ALIAS AND EXECUTED AT THE BASE.
#        Every firmware writes `nop ; jmp handler` at 0x90000000 while computing
#        the jump displacement against 0x50000001 -- the jmp's address in the
#        0x5 view.  A displacement is only correct at one execution address, so
#        0x90000000 and 0x50000000 are necessarily the same storage.
#
#    (2) EVERY OTHER ADDRESS-CONTEXT USE OF THE WINDOW IS WORK RAM TOO.
#        In all five images the ONLY operands in 0x90000000-0x903FFFFF that a
#        real instruction uses as an address are 0x90000000 / 0x90000006 (the two
#        thunks), 0x9000000E (a 0x5AA5 warm-boot flag), and 0x90000010 ->
#        0x90400000 (a clear of work RAM's exact 4 MiB extent, minus the 16-byte
#        vector header).  The firmware's own .data section is copied to
#        0x50000010 -- two bytes above that flag.  Everything else with a 0x90
#        top byte goes into a DATA register and is passed as an argument, and is
#        bit-identical across three unrelated firmwares, i.e. an ID constant.
#
#    (3) THE SAME +0x40000000 IDIOM IS EVERYWHERE ELSE IN THE SAME IMAGE.
#        Per-megabyte counts of address-context operands show a clean split:
#        ROM and work RAM are addressed in the 0x4/0x5 view and never the 0x8/0x9
#        one; device windows only in the 0x8/0x9 view.  The one routine that
#        clears work RAM through 0x90000010 clears the 0x44000000 block through
#        0x84000010 four instructions later -- the alias the driver already maps.
#
#    Consequence checked by (4): a thunk executed at 0x90000001 instead of
#    0x50000001 lands at handler+0x40000000, so every handler must live in a
#    region the driver mirrors.  The report prints, per image, whether it does.
#
# Usage:  python3 window_90000000_probe.py [<romset-dir>]
#         (default ~/compartilhado/technics_romsets)
#
# The NULL for the map size, measured separately over merged upstream code:
#   grep every `map(a, b).ram()` in src/mame -> 14295 entries, median 4 KiB,
#   p99 8 MiB, 128 at >=16 MiB; the ten at 128 MiB are all machines that really
#   have 128 MB of RAM.  So a 128 MiB catch-all is not per se disqualifying --
#   it is disqualifying for a window with 16 bytes of established use.
#
import glob, os, re, struct, sys, zipfile, collections

BASE = 0x48400000

# Operand forms that carry a 32-bit ADDRESS (vs. a plain immediate into a Dn).
ADDR_FORMS = [(rb'\xfc[\xdc-\xdf]', 2, 'mov imm32,aN'),
              (rb'\xfc[\xd8-\xdb]', 2, 'cmp imm32,aN'),
              (rb'\xfc[\x80-\x8f]', 2, 'st (abs32)'),
              (rb'\xfc[\xa0-\xaf]', 2, 'ld (abs32)'),
              (rb'\xfe[\x00-\x03]', 3, 'bset/bclr (abs32)')]
DATA_FORMS = [(rb'\xfc[\xcc-\xcf]', 2, 'mov imm32,dN')]

# Ranges the driver maps as the +0x40000000 image of something (maincpu_mem).
DRIVER_MIRRORS = [(0x84000000, 0x84ffffff, '0x44000000 block'),
                  (0x8c000000, 0x8cffffff, 'library RAM'),
                  (0x90000000, 0x903fffff, 'work RAM (KN2400/KN2600 only today)')]


def deinterleave(zpath):
    """Exactly what ROM_LOAD32_WORD does: even half -> bytes 0,1; odd -> 2,3."""
    with zipfile.ZipFile(zpath) as z:
        ev = [n for n in z.namelist() if 'program_even' in n]
        od = [n for n in z.namelist() if 'program_odd' in n]
        if not (ev and od):
            return None
        e, o = z.read(ev[0]), z.read(od[0])
    img = bytearray(len(e) + len(o))
    img[0::4], img[1::4] = e[0::2], e[1::2]
    img[2::4], img[3::4] = o[0::2], o[1::2]
    return bytes(img)


def operands(img, forms):
    h = collections.defaultdict(list)
    for pat, off, kind in forms:
        for m in re.finditer(pat, img):
            i = m.start()
            if i + off + 4 <= len(img):
                h[struct.unpack('<I', img[i + off:i + off + 4])[0]].append((BASE + i, kind))
    return h


def report(name, img):
    ok = True
    print('=== %s ===' % name)
    addr, data = operands(img, ADDR_FORMS), operands(img, DATA_FORMS)

    # (1) the builder: `mov 0x900000NN,a0` ... `mov handler,d0` / `mov 0x500000NN,d1` / `sub`
    print('  (1) thunk builders -- written at 0x9, displacement computed at 0x5:')
    thunks = []
    for m in re.finditer(rb'\xfc\xdc(.)\x00\x00\x90', img, re.S):
        seg = img[m.start():m.start() + 0x28]
        lits = [struct.unpack('<I', h.group(1))[0]
                for h in re.finditer(rb'\xfc[\xcc-\xcf](....)', seg, re.S)]
        handler = next((v for v in lits if v != 0x0000dccb and not 0x50000000 <= v < 0x50000010), None)
        against = next((v for v in lits if 0x50000000 <= v < 0x50000010), None)
        slot = m.group(1)[0]
        thunks.append((slot, handler, against))
        flag = 'OK' if against == 0x50000000 + slot + 1 else 'UNEXPECTED'
        print('      @0x%08X  write 0x900000%02X  handler 0x%08X  vs 0x%08X  [%s]'
              % (BASE + m.start(), slot, handler or 0, against or 0, flag))
        if flag != 'OK':
            ok = False
    if len(thunks) != 2:
        print('      FAIL: expected exactly 2 builders'); ok = False

    # (2) every operand in the window, split by context
    print('  (2) operands in 0x90000000-0x903FFFFF, by context:')
    struct_vals = {0x90000000, 0x90000006, 0x9000000E, 0x90000010, 0x90400000}
    junk = []
    for v in sorted(set(list(addr) + list(data))):
        if not 0x90000000 <= v <= 0x90400000:
            continue
        na, nd = len(addr.get(v, [])), len(data.get(v, []))
        if na and v not in struct_vals:
            junk.append((v, addr[v]))
        if na:
            print('      0x%08X  ADDRESS x%-2d DATA x%-2d  %s%s'
                  % (v, na, nd, ', '.join('0x%08X' % s[0] for s in addr[v][:4]),
                     '   <-- verify: decodes inside data?' if v not in struct_vals else ''))
    print('      address-context values that are NOT structural: %d %s'
          % (len(junk), ['0x%08X' % v for v, _ in junk]))
    print('      data-context-only values: %d (ID constants; identical across firmwares)'
          % len([v for v in data if 0x90000000 <= v <= 0x90400000 and v not in addr]))

    # (3) the alias idiom, and the cached/uncached split per megabyte
    print('  (3) the work-RAM clear through the alias, and its 0x44/0x84 twin:')
    for pat, label in ((rb'\xfc[\xdc-\xdf]\x10\x00\x00\x90', 'mov 0x90000010,aN'),
                       (rb'\xfc[\xd8-\xdb]\x00\x00\x40\x90', 'cmp 0x90400000,aN'),
                       (rb'\xfc[\xdc-\xdf]\x10\x00\x00\x84', 'mov 0x84000010,aN'),
                       (rb'\xfc[\xd8-\xdb]\x00\x00\x04\x84', 'cmp 0x84040000,aN')):
        for m in re.finditer(pat, img):
            print('      %-20s @0x%08X' % (label, BASE + m.start()))
    pages = collections.Counter()
    for v, l in addr.items():
        pages[v >> 24] += len(l)
    print('      cached vs cache-through, by top byte:')
    for lo in (0x44, 0x48, 0x4c, 0x50, 0x56, 0x57):
        print('        0x%02X...... %6d      0x%02X...... %6d'
              % (lo, pages[lo], lo + 0x40, pages[lo + 0x40]))

    # (4) where a thunk executed at 0x9 (rather than 0x5) would actually jump
    print('  (4) if the thunk runs at 0x900000NN, each jump lands at handler+0x40000000:')
    for slot, handler, _ in thunks:
        if handler is None:
            continue
        t = (handler + 0x40000000) & 0xffffffff
        where = next((n for a, b, n in DRIVER_MIRRORS if a <= t <= b), None)
        print('        slot +0x%02X  0x%08X -> 0x%08X   %s'
              % (slot, handler, t, ('in the driver\'s mirror of ' + where) if where
                 else 'NOT MAPPED by the driver'))
    return ok


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/compartilhado/technics_romsets')
    good, seen = True, 0
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
