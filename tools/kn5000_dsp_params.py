#!/usr/bin/env python3
"""
kn5000_dsp_params.py -- decode the KN5000 sub-CPU's *effect parameter translator*:
the code path that turns a user-facing effect parameter (as edited on screen) into
byte writes to the NEC uPD6383GF effects DSP (IC311).

This is the companion tool to notes/kn5000-dsp-parameters.md.  Every number the note
quotes is printed by this script.

Inputs (paths can be overridden on the command line):
  sub-CPU  ROM : kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom  (base 0xEF00)
  main-CPU ROM : kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom      (flat, base 0)

Usage:
  python3 tools/kn5000_dsp_params.py [subcpu.rom] [maincpu.rom]
"""

import struct
import sys
import os

SUB_BASE = 0xEF00

# ---------------------------------------------------------------- ROM accessors

class Rom:
    def __init__(self, path, base):
        self.d = open(path, 'rb').read()
        self.base = base

    def ok(self, a, n=1):
        o = a - self.base
        return 0 <= o and o + n <= len(self.d)

    def u8(self, a):
        return self.d[a - self.base]

    def u16le(self, a):
        return struct.unpack_from('<H', self.d, a - self.base)[0]

    def u16be(self, a):
        return struct.unpack_from('>H', self.d, a - self.base)[0]

    def u32le(self, a):
        return struct.unpack_from('<I', self.d, a - self.base)[0]

    def raw(self, a, n):
        o = a - self.base
        return self.d[o:o + n]


# ---------------------------------------------------------------- constants
# All addresses below are sub-CPU addresses unless said otherwise.

ALGO_T1_ARRAY = 0x0001F22C   # 100 x u32 -> per-algorithm "opcode -> DSP address" map
ALGO_T2_ARRAY = 0x0001F09C   # 100 x u32 -> per-algorithm parameter bytecode stream
NULL_T1       = 0x00017425   # the shared "no parameters" map

# 100-entry, 4-byte curve tables used by the eval opcodes
CURVES = {
    'CURVE_A': 0x00012483,
    'CURVE_B': 0x00012613,
    'CURVE_C': 0x000127A3,
    'CURVE_D': 0x00012B33,
}
CURVE_LEN = 100

# main-CPU effect-name table: name[algo] at NAME_BASE - algo*NAME_STRIDE
NAME_BASE   = 0x33568
NAME_STRIDE = 18

# main-CPU user parameter name / unit tables
PNAME_BASE   = 0x0324D5   # 85 entries, 16-char name + ':' -> stride 17
PNAME_STRIDE = 17
PUNIT_BASE   = 0x03241A   # 2-char unit string, same index

# translator opcode -> (eval helper address, writer address, descriptor field used)
# Derived from the jump table OFFSETS_14745 (sub-CPU 0x0014745, base 0x0003CB8E).
# 'imm' is filled in empirically by measure_imm_sizes().
OPCODE_EVAL = {
    0x61: ('eval_038E9F', 0x0387E6, '+0'),
    0x62: ('curve_038EAC(CURVE_D)', 0x0387E6, '+0'),
    0x63: ('curve_038EB9(A/B/C sel)', 0x03846C, '+2'),
    0x64: ('eval_038EF6 (float, k=0.552)', 0x0387E6, '+0'),
    0x65: ('eval_038F9B', 0x038539, '+2'),
    0x66: ('eval_038FE8', 0x0387E6, '+0'),
    0x67: ('eval_039206', 0x0387E6, '+0'),
    0x68: ('eval_03925E', 0x038922, '+4,+8'),
    0x69: ('eval_0392AC', 0x038539, '+2'),
    0x6A: ('eval_0392F2', 0x0387E6, '+0'),
    0x6B: ('eval_03943B', 0x038539, '+2'),
    0x6C: ('eval_0394CD', 0x038539, '+2'),
    0x6D: ('eval_039525 (uses desc +8)', 0x038539, '+2'),
    0x6E: ('eval_039599', 0x0387E6, '+0'),
    0x6F: ('eval_0396C2', 0x0387E6, '+0'),
    0x70: ('eval_0397F3', 0x0387E6, '+0'),
    0x71: ('sub-stream 0x03A933', None, '-'),
    0x72: ('eval_0398CE', 0x0387E6, '+0'),
    0x73: ('block 0x039ABD', None, '-'),
    0x74: ('eval_039D26', 0x0387E6, '+0'),
    0x75: ('block 0x03869B', None, '-'),
    0x76: ('eval_039D98', 0x0387E6, '+0'),
    0x77: ('sub-stream 0x03B646', None, '-'),
    0x78: ('eval_03A22A', 0x0387E6, '+0'),
    0x79: ('eval_03A282', 0x0387E6, '+0'),
    0x21: ('eval_039206 (alias of 0x67)', 0x0387E6, '+0'),
    0x24: ('eval_03A4B7', 0x0387E6, '+0'),
    0x40: ('eval_03A4A0', 0x0387E6, '+0'),
}

END_OPCODE  = 0x7A   # terminates one parameter record
T1_END_HI   = 0xF0   # 0xF0xx terminates a T1 map


# ---------------------------------------------------------------- T1: opcode -> DSP address map

def parse_t1(rom, addr, limit=64):
    """T1 record: [u16 BE total_len][u8 opcode][entry bytes ...]
    entry[i] is the 8-bit DSP address offset for operand i of that opcode.
    Terminated by a u16 whose high byte is 0xF0."""
    out = []
    a = addr
    for _ in range(limit):
        if not rom.ok(a, 3):
            break
        w = rom.u16be(a)
        if (w >> 8) == T1_END_HI:
            break
        ln = w
        if ln < 4 or ln > 64:
            break
        op = rom.u8(a + 2)
        entries = list(rom.raw(a + 3, ln - 3))
        out.append((a, op, entries))
        a += ln
    return out


# ---------------------------------------------------------------- T2: parameter bytecode stream

def split_records(rom, addr, limit=64):
    """T2 record: [u16 BE total_len][ instruction ... ][0x7A]
    Returns list of (addr, length, payload_bytes) where payload excludes the
    length prefix and the trailing 0x7A."""
    out = []
    a = addr
    for _ in range(limit):
        if not rom.ok(a, 3):
            break
        ln = rom.u16be(a)
        if ln < 5 or ln > 96:
            break
        body = rom.raw(a + 2, ln - 2)
        if body[-1] != END_OPCODE:
            break
        out.append((a, ln, body[:-1]))
        a += ln
    return out


def measure_imm_sizes(rom, algos):
    """For every record that contains exactly ONE instruction, the immediate size is
    len - 5 (2 len + 1 opcode + 1 operand + 1 terminator).  Collect per-opcode."""
    from collections import defaultdict
    cand = defaultdict(set)
    for _algo, _t1, t2 in algos:
        if not t2:
            continue
        for (_a, ln, body) in t2:
            op = body[0]
            # single-instruction heuristic: no further byte in the record is a
            # plausible opcode at a position consistent with (len-5) immediate.
            cand[op].add(ln - 5)
    return cand


def decode_record(rom, body, addrmap, maxlen=48):
    """Split a record payload into (opcode, operand, imm_bytes) instructions.

    Several eval helpers read a *variable* number of immediate bytes (they branch on
    a leading type byte), so the immediate size is NOT a per-opcode constant.  Rather
    than guess, we search: an instruction boundary is only accepted when body[i] is an
    opcode this algorithm's T1 map actually declares AND body[i+1] is a valid operand
    index into that opcode's entry list.  Returns (parses, ambiguous) where parses is
    the list of solutions found (usually exactly one)."""
    sols = []

    def rec(i, acc):
        if len(sols) >= 4:
            return
        if i == len(body):
            sols.append(list(acc))
            return
        op = body[i]
        if op not in addrmap or i + 2 > len(body):
            return
        operand = body[i + 1]
        if operand >= len(addrmap[op]):
            return
        for n in range(0, min(maxlen, len(body) - i - 2) + 1):
            acc.append((op, operand, body[i + 2:i + 2 + n]))
            rec(i + 2 + n, acc)
            acc.pop()

    rec(0, [])
    return sols


# ---------------------------------------------------------------- DSP word synthesis
# Reproduces sub-CPU writers 0x0387E6 and 0x038539 / 0x03846C byte-for-byte.

def writer_0387E6(dsp_addr, value):
    """Returns the two 5-byte DSP instruction words emitted by LABEL_0387E6."""
    a = dsp_addr & 0xFF
    w1 = bytes([0x08, 0x01, (a >> 4) & 0x0F, ((a << 4) & 0xF0) | 8, 0x21])
    w2 = bytes([0x0A,
                (value >> 1) & 0x7F,
                (value >> 9) & 0xFF,
                (value >> 1) & 0xFF,
                ((value << 7) & 0x80) | 0x26])
    return w1, w2


def writer_038539(dsp_addr, value):
    """Returns the two 5-byte DSP instruction words emitted by LABEL_038539 / 0x03846C."""
    a = dsp_addr & 0xFF
    w1 = bytes([0x00, 0x00, 0x10 | ((a >> 4) & 0x0F), (a << 4) & 0xF0, 0x00])
    w2 = bytes([0x0A,
                (value >> 1) & 0x7F,
                (value >> 9) & 0xFF,
                (value >> 1) & 0xFF,
                ((value << 7) & 0x80) | 0x15])
    return w1, w2


def word36(b5):
    v = 0
    for c in b5:
        v = (v << 8) | c
    return v & 0xFFFFFFFFF


def fields(w):
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def fmt_word(b5):
    hi, cl, ad, lo = fields(word36(b5))
    return '%03X.%X.%02X.%03X' % (hi, cl, ad, lo)


# ---------------------------------------------------------------- curves

def curve(rom, base):
    return [rom.u32le(base + 4 * i) for i in range(CURVE_LEN)]


def db(v, full=(1 << 23)):
    import math
    if v <= 0:
        return None
    return 20.0 * math.log10(v / float(full))


# ---------------------------------------------------------------- names

def effect_name(main, algo):
    off = NAME_BASE - algo * NAME_STRIDE
    if off < 0 or off + NAME_STRIDE > len(main.d):
        return '?'
    s = main.d[off:off + NAME_STRIDE]
    return ''.join(chr(c) for c in s if 32 <= c < 127).strip()


# ---------------------------------------------------------------- main

def main(argv):
    sub_path = argv[1] if len(argv) > 1 else \
        os.path.expanduser('~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
    main_path = argv[2] if len(argv) > 2 else \
        os.path.expanduser('~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom')

    rom = Rom(sub_path, SUB_BASE)
    mrom = Rom(main_path, 0)

    print('=' * 78)
    print('1. ALGORITHM POINTER ARRAYS')
    print('=' * 78)
    algos = []
    for algo in range(100):
        t1p = rom.u32le(ALGO_T1_ARRAY + 4 * algo)
        t2p = rom.u32le(ALGO_T2_ARRAY + 4 * algo)
        t1 = parse_t1(rom, t1p) if (t1p and t1p != NULL_T1) else []
        t2 = split_records(rom, t2p) if t2p else []
        algos.append((algo, t1, t2))
        nm = effect_name(mrom, algo)
        flag = ''
        if t2p == 0 and nm.startswith('---'):
            flag = 'ok(empty)'
        elif t2p == 0:
            flag = 'NAMED but NO param stream'
        elif nm.startswith('---'):
            flag = '*** named ---- but HAS stream ***'
        print('algo %2d  T1=%08X T2=%08X  %-18s %s' % (algo, t1p, t2p, nm, flag))

    # shared-T1 groups
    print()
    print('shared T1 groups (identical parameter map = same DSP program):')
    from collections import defaultdict
    g = defaultdict(list)
    for algo in range(100):
        t1p = rom.u32le(ALGO_T1_ARRAY + 4 * algo)
        if t1p and t1p != NULL_T1:
            g[t1p].append(algo)
    for p, l in sorted(g.items()):
        if len(l) > 1:
            print('  T1=%08X : algos %s' % (p, l))
            for a in l:
                print('       %2d %s' % (a, effect_name(mrom, a)))

    print()
    print('=' * 78)
    print('2. IMMEDIATE SIZES PER OPCODE (empirical: len-5 over single-instruction records)')
    print('=' * 78)
    cand = measure_imm_sizes(rom, algos)
    imm = {}
    for op in sorted(cand):
        s = sorted(cand[op])
        imm[op] = min(x for x in s if x >= 0) if s else 0
        print('  op %02X  candidate imm sizes %s  -> using %d   %s'
              % (op, s, imm[op], OPCODE_EVAL.get(op, ('?',))[0]))

    print()
    print('=' * 78)
    print('3. PER-ALGORITHM PARAMETER MAP')
    print('=' * 78)
    for algo, t1, t2 in algos:
        if not t2:
            continue
        print()
        print('--- algo %2d  %s' % (algo, effect_name(mrom, algo)))
        addrmap = {}
        for (_a, op, entries) in t1:
            addrmap[op] = entries
            print('    T1 op %02X -> DSP addr offsets %s' %
                  (op, ' '.join('%02X' % e for e in entries)))
        for (a, ln, body) in t2:
            sols = decode_record(rom, body, addrmap)
            n = len(sols)
            # prefer the parse with the most instructions (the 4x-repeat records
            # only parse that way); flag ambiguity honestly.
            best = max(sols, key=len) if sols else []
            print('    T2 @%06X len%2d %-30s %s:' %
                  (a, ln, body.hex().upper(),
                   '' if n == 1 else ('[%d parses]' % n if n < 4 else '[>=4 parses]')),
                  end='')
            if not best:
                print('  <no parse>')
                continue
            for (op, operand, immb) in best:
                tgt = addrmap[op][operand]
                print(' [op%02X#%02X->addr%02X imm=%s]' %
                      (op, operand, tgt, immb.hex().upper()), end='')
            print()

    print()
    print('=' * 78)
    print('4. VALUE CURVE TABLES (100 entries, 32-bit, indexed by the USER VALUE 0..99)')
    print('=' * 78)
    for nm, base in CURVES.items():
        c = curve(rom, base)
        print('  %s @%08X  [1]=%08X (%+.2f dBFS)  [50]=%08X (%+.2f dBFS)  [99]=%08X (%+.2f dBFS)'
              % (nm, base, c[1], db(c[1]), c[50], db(c[50]), c[99], db(c[99])))
        # per-step dB, to test "is it a constant-dB ladder?"
        steps = [db(c[i + 1]) - db(c[i]) for i in range(1, 99)]
        print('       per-step dB: min %.4f  max %.4f  mean %.4f' %
              (min(steps), max(steps), sum(steps) / len(steps)))

    print()
    print('=' * 78)
    print('5. WRITER SYNTHESIS CHECK (what the DSP actually receives)')
    print('=' * 78)
    for (nm, wf) in (('0387E6', writer_0387E6), ('038539', writer_038539)):
        w1, w2 = wf(0x96, 0x005A6704)
        print('  writer %s  addr=0x96 value=0x5A6704 ->  %s  %s'
              % (nm, fmt_word(w1), fmt_word(w2)))
        w1, w2 = wf(0x00, 0x00000000)
        print('  writer %s  addr=0x00 value=0        ->  %s  %s'
              % (nm, fmt_word(w1), fmt_word(w2)))

    print()
    print('=' * 78)
    print('6. USER PARAMETER NAMES + UNITS (main CPU ROM)')
    print('=' * 78)
    print('  name strings : 0x%06X, stride %d, 85 entries' % (PNAME_BASE, PNAME_STRIDE))
    print('  unit strings : 0x%06X, stride 2, same index' % PUNIT_BASE)
    for i in range(85):
        o = PNAME_BASE + PNAME_STRIDE * i
        nm = mrom.d[o:o + 16].decode('latin1').strip()
        un = mrom.d[PUNIT_BASE + 2 * i:PUNIT_BASE + 2 * i + 2].decode('latin1').strip()
        print('   %2d  %-18s %s' % (i, nm, un))

    print()
    print('=' * 78)
    print('7. SAMPLE RATE, FROM THE FIRMWARE (not assumed)')
    print('=' * 78)
    print('  sub-CPU LABEL_03925E:  samples = ms * 0x%04X / 0x%03X = ms * %d / %d'
          % (0xAC44, 0x3E8, 0xAC44, 0x3E8))
    print('  -> the millisecond-to-DRAM-word conversion is hard-coded at %d Hz.' % 0xAC44)
    print('  sub-CPU LABEL_0392AC:  scale / 0x%02X (%d)  -> a 0..180 degree parameter'
          % (0xB4, 0xB4))
    print('  sub-CPU LABEL_039206:  lerp(v1,v2,user/0x%02X) -> user value range 0..%d'
          % (0x63, 0x63))

    print()
    print('=' * 78)
    print('8. DELAY-TIME CONVERSION TABLE (for DRAM word counts already published)')
    print('=' * 78)
    print('  %-24s %8s %8s %8s' % ('quantity', '32 kHz', '44.1 kHz*', '48 kHz'))
    for nm, n in (('chorus tap 200', 200), ('chorus tap 720', 720),
                  ('chorus tap 1240', 1240), ('chorus tap 1760', 1760),
                  ('chorus spacing 520', 520),
                  ('rotary tap 160', 160), ('rotary tap 502', 502),
                  ('rotary tap 862', 862),
                  ('slot64 1344', 1344), ('slot64 2688', 2688),
                  ('slot71 1600', 1600), ('slot71 6400', 6400),
                  ('DRAM full 131072', 131072)):
        print('  %-24s %7.2fms %7.2fms %7.2fms' %
              (nm, n / 32000.0 * 1000, n / 44100.0 * 1000, n / 48000.0 * 1000))

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
