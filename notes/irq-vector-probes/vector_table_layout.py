#!/usr/bin/env python3
#
# Q: the MN10300 vectors a maskable interrupt of level L to <base> + IVAR[L].
#    What is <base>, what do these firmwares put in IVAR, and what sits at the
#    addresses the hardware enters?
#
# A (what this script measures, per image):
#
#   (1) THE PROGRAM ROM BEGINS WITH THE DOCUMENTED VECTOR TABLE.
#       Offset 0 is a `jmp` to the reset routine, then `nop` padding, then a
#       second `jmp` positioned so that entering at OFFSET 8 executes it. That
#       is exactly the layout the manufacturer's manual prescribes -- reset at
#       0x40000000, nonmaskable interrupts at `org 0x40000008` -- so the ROM was
#       linked for a vector base of 0x40000000 and the board decodes 0x40000000
#       to the program flash at reset.
#
#   (2) IVAR0..IVAR6 ARE WRITTEN ZERO, ONCE, AND NEVER AGAIN.
#       Seven 16-bit stores to 0x20000000 + n*4, all of a register cleared on
#       the preceding instruction. The block is never touched again through any
#       encoding: the only address inside the CPU's on-chip peripheral page
#       these images ever load into a pointer register is 0x20000070, so a
#       pointer-relative write cannot be hiding one. One vector therefore serves
#       all seven levels.
#
#   (3) THE FIRMWARE BUILDS A SECOND COPY OF THAT TABLE IN WORK RAM.
#       Two 6-byte `nop ; jmp handler` thunks at work-RAM offsets 0 and 6, each
#       displacement computed against the jmp's own execution address. The second
#       thunk's handler is the same address the ROM table's offset-8 entry jumps
#       to, i.e. it is the nonmaskable slot.
#
#       Neither thunk address is ever loaded as a call or jump target: RAM+6 is
#       loaded nowhere at all, and RAM+0 only by the routine that walks work RAM
#       with 0x5A5A5A5A / 0xA5A5 patterns, which is a memory test and not a
#       dispatch. They are entered by hardware. (The stronger form of this claim
#       -- every address-context operand in the whole window -- is measured by
#       window_90000000_probe.py, which this does not duplicate.)
#
#       The RAM copy packs its second entry at +6 where the ROM table and the
#       documented nonmaskable entry are at +8. Recorded, not explained.
#
# WHERE THE ARCHITECTURE COMES FROM (neither is this project's inference):
#   * Matsushita, "MN1030/MN103S Series Instruction Manual". Memory Layout:
#     "One assignment that is common throughout, however, is the location of the
#     reset vector. It is always at 0x40000000." Boiler Plate Code Sequences:
#     IVAR0..IVAR6 equ 0x20000000..0x20000018, each loaded with movhu and
#     commented "Set to lower 16 bits of entry point for level interrupt
#     handler"; the nonmaskable handler assembled at `org 0x40000008`. The AM32
#     memory map (p.13) puts 0x20000000-0x3FFFFFFF in the on-chip peripheral
#     region and external memory at 0x40000000-0x7FFFFFFF cachable, the same
#     memory uncachable at 0x80000000-0xBFFFFFFF -- which is the +0x40000000
#     window pairing these machines use throughout.
#   * GNU binutils/gdb, sim/mn10300/dv-mn103cpu.c: models the same block as
#     `unsigned16 interrupt_vector[7]` at offsets 0x000..0x018 of a register
#     block based at 0x20000000, and delivers a level interrupt to
#     `0x40000000 + interrupt_vector[pending_level]` (line 250), a nonmaskable
#     one to 0x40000008.
#
# WHAT THIS DOES NOT SETTLE
#   Which address the board decodes to the RAM copy at run time. (1) says the
#   flash answers 0x40000000 at reset; (3) says the RAM thunk is a hardware
#   entry point; (2) says the maskable vector is base+0 exactly. Those three can
#   only hold together if the decode of the vector base changes between reset
#   and run. The candidate mechanism is in these images and is not decoded here:
#   a 16-bit register at 0x20000070, bit-set and bit-cleared around cache-visible
#   work, has bit 7 set on the instruction immediately before IVAR0..IVAR6 are
#   cleared. Needs hardware; see HARDWARE-QUESTIONS-PENDING-FELIPE.md.
#
# USAGE
#   python3 vector_table_layout.py [<romset-dir>]      # default technics_romsets
#   python3 vector_table_layout.py --selftest          # positive control
#
# PASS CRITERION (exit 0)
#   Every image: a jmp at offset 0; a jmp reachable by entering at offset 8;
#   exactly seven IVAR stores, all of a just-cleared register; no pointer into
#   the IVAR block; exactly two RAM thunks; zero references to either thunk
#   address outside its builder.
#
# POSITIVE CONTROL
#   --selftest re-runs every check against images mutated one at a time (a
#   non-zero IVAR value, the offset-8 entry overwritten, a third thunk) and
#   requires each check to report the mutation. A check that cannot fail is not
#   a check.
#
import glob
import os
import struct
import sys
import zipfile

BASE = 0x48400000
IVAR_ADDRS = [0x20000000 + n * 4 for n in range(7)]
LIBRARY_DELTA = 0x4C000000 - 0x48400000   # the self-loaded library copy of the flash


def deinterleave(zpath):
    """Two 16-bit halves, the way the driver's ROM_LOAD32_WORD reads them."""
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


def jmp_at(img, off):
    """Decode a jmp at img[off], returning (target, length) or None.

    Only the two forms the vector tables use: DC disp32 and CC disp16. The
    MN10300 computes a branch target from the address of the OPCODE."""
    if off + 1 > len(img):
        return None
    if img[off] == 0xDC and off + 5 <= len(img):
        d = struct.unpack_from('<i', img, off + 1)[0]
        return (BASE + off + d) & 0xFFFFFFFF, 5
    if img[off] == 0xCC and off + 3 <= len(img):
        d = struct.unpack_from('<h', img, off + 1)[0]
        return (BASE + off + d) & 0xFFFFFFFF, 3
    return None


def entry_from(img, off):
    """Follow `nop` padding from off and return the jmp target reached, or None."""
    for _ in range(16):
        j = jmp_at(img, off)
        if j:
            return j[0]
        if img[off] != 0xCB:            # nop
            return None
        off += 1
    return None


def rom_table(img):
    """(1) reset entry and the entry reached at offset 8."""
    return entry_from(img, 0), entry_from(img, 8)


def ivar_writes(img):
    """(2) every 16-bit store to an IVAR, as (address_of_insn, ivar_index,
    preceded_by_clear). `FC 87 <abs32>` is movhu d1,(abs32); `04` is clr d1."""
    out = []
    for off in range(1, len(img) - 6):
        if img[off] == 0xFC and img[off + 1] == 0x87:
            v = struct.unpack_from('<I', img, off + 2)[0]
            if v in IVAR_ADDRS:
                # the clear precedes the FIRST store of the run
                prev_is_run = img[off - 6:off - 4] == b'\xfc\x87'
                out.append((BASE + off, IVAR_ADDRS.index(v),
                            prev_is_run or img[off - 1] == 0x04))
    return out


def ivar_pointers(img):
    """(2) any `mov imm32,aN` whose immediate lands in the IVAR block."""
    out = []
    for off in range(len(img) - 6):
        if img[off] == 0xFC and 0xDC <= img[off + 1] <= 0xDF:
            v = struct.unpack_from('<I', img, off + 2)[0]
            if 0x20000000 <= v <= 0x2000001B:
                out.append((BASE + off, v))
    return out


def ram_thunks(img):
    """(3) `mov 0x900000NN,a0` builders, and the handler each thunk jumps to.

    The builder loads the write address in the uncachable view and, four
    instructions later, the jmp's own execution address in the cachable one;
    the handler is the immediate in between."""
    out = []
    for off in range(len(img) - 0x20):
        if img[off] == 0xFC and img[off + 1] == 0xDC:
            w = struct.unpack_from('<I', img, off + 2)[0]
            if not (0x90000000 <= w <= 0x9000001F):
                continue
            hnd = exe = None
            for k in range(6, 0x20):
                if img[off + k] == 0xFC and img[off + k + 1] == 0xCC:
                    hnd = struct.unpack_from('<I', img, off + k + 2)[0]
                if img[off + k] == 0xFC and img[off + k + 1] == 0xCD:
                    exe = struct.unpack_from('<I', img, off + k + 2)[0]
            if hnd is not None and exe is not None:
                out.append((BASE + off, w & 0xFF, hnd, exe))
    return out


def addr_loads(img, addr, ignore):
    """(3) every `mov imm32,aN` that loads addr -- the only way this ISA builds
    an indirect jump or call target. Byte-coincident literals are NOT counted:
    a bare scan for the 32-bit value matches thousands of unaligned positions,
    which is what makes an untyped search useless here."""
    out = []
    for off in range(len(img) - 6):
        if img[off] == 0xFC and 0xDC <= img[off + 1] <= 0xDF:
            if struct.unpack_from('<I', img, off + 2)[0] == addr:
                a = BASE + off
                if not any(b <= a <= b + 0x20 for b in ignore):
                    out.append((a, img[off + 1] - 0xDC))
    return out


def check(name, img, quiet=False):
    """Run every check; return a list of failure strings."""
    bad = []
    p = (lambda *a: None) if quiet else print

    reset, nmi = rom_table(img)
    p('  ROM vector table @ %08X: reset -> %s, offset+8 -> %s'
      % (BASE, '%08X' % reset if reset else 'NONE',
         '%08X' % nmi if nmi else 'NONE'))
    if reset is None:
        bad.append('no jmp at ROM offset 0')
    if nmi is None:
        bad.append('ROM offset 8 does not reach a jmp')

    w = ivar_writes(img)
    idx = sorted(i for _, i, _ in w)
    p('  IVAR stores: %d (levels %s), all from a cleared register: %s'
      % (len(w), ','.join(str(i) for i in idx), all(c for _, _, c in w)))
    if len(w) != 7 or idx != list(range(7)):
        bad.append('expected one store to each of IVAR0..IVAR6, got %d (%s)'
                   % (len(w), idx))
    if not all(c for _, _, c in w):
        bad.append('an IVAR store does not write a just-cleared register')

    ptr = ivar_pointers(img)
    p('  pointers into the IVAR block: %d' % len(ptr))
    if ptr:
        bad.append('IVAR reachable through a pointer: %s'
                   % ', '.join('%08X' % a for a, _ in ptr))

    th = ram_thunks(img)
    p('  work-RAM thunks: %d' % len(th))
    for b, o, h, e in th:
        p('     builder %08X -> RAM+%X  jmp %08X  (jmp executes at %08X)'
          % (b, o, h, e))
    if len(th) != 2:
        bad.append('expected 2 work-RAM thunks, got %d' % len(th))
    builders = [b for b, _, _, _ in th]
    for b, o, h, e in th:
        loads = addr_loads(img, (e & ~0xFF) | o, builders)
        p('     RAM+%X loaded into an address register at: %s'
          % (o, ', '.join('%08X(a%d)' % t for t in loads) if loads else 'nowhere'))
    if len(th) == 2 and nmi is not None:
        # The library ROM at 0x4C000000 is the firmware's own copy of the flash
        # from 0x48400000, so the same routine has two addresses 0x03C00000
        # apart; kn6000/kn6500 vector the RAM copy at the library one.
        if th[1][2] == nmi:
            how = 'yes'
        elif th[1][2] == nmi + LIBRARY_DELTA:
            how = 'yes, via the library copy at +%06X' % LIBRARY_DELTA
        else:
            how = 'NO'
            bad.append('second thunk (%08X) is not the ROM offset-8 handler (%08X)'
                       % (th[1][2], nmi))
        p('  second thunk is the ROM offset-8 handler: %s' % how)
    return bad


def mutate_ivar(img):
    """Break check (2): make the store follow something other than `clr d1`."""
    m = bytearray(img)
    for off in range(1, len(m) - 6):
        if m[off] == 0xFC and m[off + 1] == 0x87 and \
           struct.unpack_from('<I', m, off + 2)[0] == IVAR_ADDRS[0]:
            m[off - 1] = 0xCB                     # nop instead of clr d1
            break
    return bytes(m)


def mutate_nmi(img):
    """Break check (1): overwrite the offset-8 entry."""
    m = bytearray(img)
    m[5:16] = b'\xff' * 11
    return bytes(m)


def mutate_thunk(img):
    """Break check (3): plant a third builder."""
    m = bytearray(img)
    for off in range(len(m) - 0x20):
        if m[off] == 0xFC and m[off + 1] == 0xDC and \
           0x90000000 <= struct.unpack_from('<I', m, off + 2)[0] <= 0x9000001F:
            src = bytes(m[off:off + 0x20])
            m[0x1000:0x1000 + 0x20] = src         # a copy somewhere harmless
            break
    return bytes(m)


def selftest(img):
    print('POSITIVE CONTROL -- each mutation must be reported')
    ok = True
    for label, fn, want in (
            ('IVAR store no longer preceded by a clear', mutate_ivar, 'cleared register'),
            ('ROM offset-8 entry destroyed', mutate_nmi, 'offset 8'),
            ('a third work-RAM thunk planted', mutate_thunk, 'thunks, got 3')):
        bad = check('mutant', fn(img), quiet=True)
        hit = any(want in b for b in bad)
        print('  %-44s reported: %s' % (label, hit))
        if not hit:
            print('     (failures seen: %s)' % bad)
        ok = ok and hit
    return ok


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
        print('== %s (%d KiB)' % (name, len(img) // 1024))
        bad = check(name, img)
        for b in bad:
            print('  FAIL: %s' % b)
        failures += len(bad)
    print('\n%s' % ('PASS' if not failures else 'FAIL: %d problem(s)' % failures))
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
