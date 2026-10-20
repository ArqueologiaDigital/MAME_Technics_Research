#!/usr/bin/env python3
# compare_dspmem.py CHIP_DIR MAME_DIR -- does the emulator leave the effects DSP's memory as the real chip has it?
#
# Both directories hold the DSP probe's phase-2 files (technics-roms-disasm kn7000/tools/cnv_romdump, pass 7):
# DSPPM.BIN (PM 0x8000-0x8DFF, 48-bit words, three 16-bit halves LSW first, after a 0x80-byte header) and DSPDM.BIN
# (DM 0x9800-0x9FFF at 0x80 and DM 0xC000-0xC4FF at 0x2080, 32-bit words). CHIP_DIR comes from the instrument, MAME_DIR
# from the same probe in MAME (run_test.sh --dspmem, ideally with the instrument's IC23 as NVRAM so the same effects
# load). Prints, per region of the kernel's map (notes/dsp-effect-catalog.md), how many words are equal and the
# differing addresses as ranges, and how many of those MAME holds as 0: memory nothing wrote in the emulator, which on
# the chip keeps whatever the SRAM powered up with. Equal code means the emulator downloaded what the firmware
# downloads on the chip; DM state, delay lines and I/O rings move while the DSP runs and are expected to differ.
import struct
import sys

PM_REGIONS = [(0x8000, 0x8078, 'interrupt vectors, reset handler'),
              (0x8078, 0x80A6, 'main loop and the host-patched unit CALL slots'),
              (0x80A6, 0x8300, 'kernel: dispatch, scrub stubs, the rest'),
              (0x8300, 0x8400, 'shared filter helpers'),
              (0x8400, 0x8D00, 'effect programs (downloaded per unit)'),
              (0x8D00, 0x8E00, 'boot-init, recycled by slot 9')]
DM_REGIONS = [(0x9800, 0x9C40, 'per-unit state (0x50 words each)'),
              (0x9C40, 0xA000, 'scrub countdown table and the rest'),
              (0xC000, 0xC302, 'per-unit parameters (0x4D words each)'),
              (0xC302, 0xC342, 'slot I/O descriptors, SPORT TCBs'),
              (0xC342, 0xC382, 'SPORT DMA rings (8 x 8 words, live audio)'),
              (0xC382, 0xC500, 'the rest')]


def pm_words(b):
    return {0x8000 + i: struct.unpack_from('<HHH', b, 0x80 + 6 * i) for i in range(0xE00)}


def dm_words(b):
    w = {0x9800 + i: struct.unpack_from('<I', b, 0x80 + 4 * i)[0] for i in range(0x800)}
    w.update({0xC000 + i: struct.unpack_from('<I', b, 0x2080 + 4 * i)[0] for i in range(0x500)})
    return w


def ranges(addrs):
    out, start, prev = [], None, None
    for a in addrs:
        if start is None:
            start = prev = a
        elif a == prev + 1:
            prev = a
        else:
            out.append((start, prev)); start = prev = a
    if start is not None:
        out.append((start, prev))
    return ', '.join(f'{s:#06x}' if s == e else f'{s:#06x}-{e:#06x}' for s, e in out) or '-'


def table(head, rows):
    w = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    print('| ' + ' | '.join(str(c).ljust(w[i]) for i, c in enumerate(head)) + ' |')
    print('|' + '|'.join('-' * (x + 2) for x in w) + '|')
    for r in rows:
        print('| ' + ' | '.join(str(c).ljust(w[i]) for i, c in enumerate(r)) + ' |')


def main():
    chip, mame = sys.argv[1], sys.argv[2]
    for name, words, regions, kind in (('DSPPM.BIN', pm_words, PM_REGIONS, 'PM'), ('DSPDM.BIN', dm_words, DM_REGIONS, 'DM')):
        a = words(open(f'{chip}/{name}', 'rb').read())
        b = words(open(f'{mame}/{name}', 'rb').read())
        rows = []
        for lo, hi, what in regions:
            addrs = [x for x in range(lo, hi) if x in a]
            diff = [x for x in addrs if a[x] != b[x]]
            zero = sum(1 for x in diff if not any(b[x]) if isinstance(b[x], tuple)) if kind == 'PM' else \
                sum(1 for x in diff if b[x] == 0)
            rows.append((f'{kind} {lo:#06x}-{hi - 1:#06x}', what, len(addrs), len(addrs) - len(diff), zero,
                         ranges(diff)))
        table(('range', 'what', 'words', 'equal', 'differ, MAME 0', 'differ'), rows)
        print()


if __name__ == '__main__':
    main()
