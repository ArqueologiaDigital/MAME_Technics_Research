#!/usr/bin/env python3
"""
kn5000_dsp_paramnames.py -- the name->slot binding for KN5000 effect parameters.

Companion to notes/kn5000-dsp-paramnames.md.  Two independent attacks on the one
missing link (which of the 85 parameter NAMEs belongs to which effect's slot):

  (A) ROM search on the MAIN CPU (TMP94C241F / TLCS-900) for the code that DRAWS the
      effect-edit page and indexes the name table at 0xE324D5.  RESULT: the binding is
      NOT a fixed-stride ROM table -- it is a per-effect list of name INDICES held in
      the effect-parameter UI object database, extracted to RAM 0x29AC at selection
      time.  This tool documents that path and reproduces its address arithmetic so the
      claim is checkable.  (This is why the fixed-stride scan in
      kn5000-dsp-parameters.md section 4 found nothing.)

  (B) Constraint propagation over the 85-name table using the per-algorithm DSP-target
      streams (sub-CPU) + the units/ranges filter.  This pins the defensible
      (effect,slot)->name pairs and reports what stays ambiguous.

Usage:
  python3 tools/kn5000_dsp_paramnames.py [subcpu.rom] [maincpu.rom]
"""
import os, struct, sys

SUB_BASE = 0xEF00
MAIN_ROMBASE_CPU = 0xE00000     # ROM offset X  ->  CPU address 0xE00000 + X

# ---- main-CPU tables (CPU addresses; subtract 0xE00000 for ROM file offset) ----
PNAME_BASE = 0x0324D5           # 85 names, 16 chars + ':' , stride 17     (CPU 0xE324D5)
PNAME_STRIDE = 17
PUNIT_BASE = 0x03241A           # 2-char units, same index                (CPU 0xE3241A)
NAME_BASE = 0x33568             # effect names, stride 18 DESCENDING       (CPU 0xE33568)
NAME_STRIDE = 18

# ---- sub-CPU per-algorithm pointer arrays (see kn5000_dsp_params.py) ----
ALGO_T1_ARRAY = 0x0001F22C
ALGO_T2_ARRAY = 0x0001F09C
NULL_T1 = 0x00017425
END_OPCODE = 0x7A
T1_END_HI = 0xF0


class Rom:
    def __init__(self, path, base):
        self.d = open(path, 'rb').read()
        self.base = base
    def ok(self, a, n=1):
        o = a - self.base; return 0 <= o and o + n <= len(self.d)
    def u8(self, a): return self.d[a - self.base]
    def u16be(self, a): return struct.unpack_from('>H', self.d, a - self.base)[0]
    def u32le(self, a): return struct.unpack_from('<I', self.d, a - self.base)[0]
    def raw(self, a, n): o = a - self.base; return self.d[o:o + n]


def effect_name(main, algo):
    off = NAME_BASE - algo * NAME_STRIDE
    if off < 0 or off + NAME_STRIDE > len(main.d): return '?'
    return ''.join(chr(c) for c in main.d[off:off + NAME_STRIDE] if 32 <= c < 127).strip()


def read_names(main):
    names, units = [], []
    for i in range(85):
        o = PNAME_BASE + PNAME_STRIDE * i
        names.append(main.d[o:o + 16].decode('latin1').strip())
        units.append(main.d[PUNIT_BASE + 2 * i:PUNIT_BASE + 2 * i + 2].decode('latin1').strip())
    return names, units


def parse_t1(rom, addr, limit=64):
    out, a = [], addr
    for _ in range(limit):
        if not rom.ok(a, 3): break
        w = rom.u16be(a)
        if (w >> 8) == T1_END_HI: break
        ln = w
        if ln < 4 or ln > 64: break
        out.append((a, rom.u8(a + 2), list(rom.raw(a + 3, ln - 3))))
        a += ln
    return out


def split_records(rom, addr, limit=64):
    out, a = [], addr
    for _ in range(limit):
        if not rom.ok(a, 3): break
        ln = rom.u16be(a)
        if ln < 5 or ln > 96: break
        body = rom.raw(a + 2, ln - 2)
        if body[-1] != END_OPCODE: break
        out.append((a, ln, body[:-1]))
        a += ln
    return out


# --- eval-helper -> user-facing UNIT/RANGE, the hard filter (kn5000-dsp-parameters.md s3,s6)
# Only the settled helpers carry a defensible unit.  'None' = not diagnostic.
OP_UNIT = {
    0x21: ('level', '0..0.8 lerp -> DSP 0x90 (universal wet/send level)'),
    0x62: ('dB',    'CURVE_D 1.00 dB/step volume law'),
    0x63: ('curve', 'A/B/C curve selector (mostly an internal depth/mix law, DSP 0x06)'),
    0x68: ('ms',    'ms * 44100/1000 -> DRAM word count (a delay time)'),
    0x69: ('deg',   'value/180 -> a degrees param (PHASE / PAN)'),
}

# name indices grouped by the unit string in the 0x03241A table
def names_by_unit(names, units):
    from collections import defaultdict
    g = defaultdict(list)
    for i, (n, u) in enumerate(zip(names, units)):
        g[u].append((i, n))
    return g


def main(argv):
    sub = argv[1] if len(argv) > 1 else \
        os.path.expanduser('~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
    mn = argv[2] if len(argv) > 2 else \
        os.path.expanduser('~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom')
    rom, mrom = Rom(sub, SUB_BASE), Rom(mn, 0)
    names, units = read_names(mrom)

    print('=' * 78)
    print('A. THE NAME->SLOT BINDING, LOCATED ON THE MAIN CPU (TLCS-900)')
    print('=' * 78)
    print("""
The parameter-edit page is drawn by DspItem0CngFunc (asm 0xF355xx).  The name-drawing
loop (LABEL_F3561F, asm ~204102) is:

    PUSHW  0011h                 ; stride = 17 (the PNAME table stride)
    LD A,(021098h)               ; page/window base index for this screen
    ADD WA,(XSP+014h)            ; + row offset
    LDA XBC,29ACh ; ADD ; LD A,(XWA)   ; A = RAM[0x29AC + idx]  <- the NAME INDEX (1-based)
    MULS_WA 0011h                ; * 17
    LDA XBC,0E324C4h ; ADD       ; ptr = 0xE324C4 + 17*storedidx
    CALL draw_string(ptr, ...)   ;   0xE324C4 = 0xE324D5 - 17  => name entry (storedidx-1)

The very next loop (LABEL_F3566C) draws the UNIT with base 0xE32418 (= 0xE3241A - 2)
and stride 2 -- SAME stored index.  So:

  *  name[slot] = string at 0xE324D5 + 17*(RAM[0x29AC+slot] - 1)
  *  unit[slot] = string at 0xE3241A +  2*(RAM[0x29AC+slot] - 1)
  *  value[slot]= word   at RAM[0x2978 + 2*slot]

RAM[0x29AC..] is a flat array of (name_index+1) bytes, length RAM[0x29AA], filled per
effect by LABEL_F457CF (asm ~230296).  That loader dispatches on the effect TYPE byte
RAM[0x8D38] (0x0a/0x0b/0x0c/0x0e/0xd6 = five parameter layouts) and, per slot QIZH,
reads:

    value      = LABEL_FDC7F9(objid)      -> RAM[0x2978 + 2*QIZH]
    name index = LABEL_FDC6E7(objid)      -> RAM[0x29AC + QIZH]      (byte, 1-based)

where objid = 0x4900 / 0x4B10 / 0x4C10 / 0x4D10 / 0x4E10 + QIZH.  FDC6E7 / FDC7F9 are a
GENERIC UI object-property database (resolver LABEL_FDC5AB / FDC504 / FDC41D, pointer
tables at 0xEE6044 / 0xEE61D4 / 0xEE637A).  The per-effect list of name indices is a
PROPERTY of the effect's parameter objects in that database -- not a flat table.

==> This is why the fixed-stride scan in kn5000-dsp-parameters.md section 4 found
    nothing: there is no fixed-stride name-index table.  The binding is variable-length
    and object-indirected -- exactly the shape a stride scan is blind to.  Statically
    dumping all 59 lists requires decoding the UI object DB (FDC5AB + the 0xEE60xx
    tables); that is the recommended follow-up.
""")

    print('=' * 78)
    print('B. CONSTRAINT PROPAGATION  (per-algorithm DSP streams x units/ranges filter)')
    print('=' * 78)
    g = names_by_unit(names, units)
    print('\nname pool by UNIT (the hard filter, table 0x03241A):')
    for u in sorted(g, key=lambda x: (x != '', x)):
        tag = repr(u) if u else "'' (dimensionless)"
        print('  unit %-4s : %s' % (tag, ', '.join('%d=%s' % (i, n) for i, n in g[u])))

    print('\nPER-ALGORITHM STREAM with unit-forced pins (only settled helpers labelled):')
    for algo in range(100):
        t1p = rom.u32le(ALGO_T1_ARRAY + 4 * algo)
        t2p = rom.u32le(ALGO_T2_ARRAY + 4 * algo)
        t2 = split_records(rom, t2p) if t2p else []
        if not t2:
            continue
        # collect distinct (op) present
        ops = []
        for (_a, _ln, body) in t2:
            op = body[0]
            if op not in ops:
                ops.append(op)
        print('\n-- algo %2d  %-18s  records=%d' % (algo, effect_name(mrom, algo), len(t2)))
        for op in ops:
            if op in OP_UNIT:
                u, desc = OP_UNIT[op]
                print('     op %02X  UNIT=%-5s  %s' % (op, u, desc))
        # universal level pin
        if 0x21 in ops:
            print('     PIN: DSP 0x90 (op21) = the universal 0..0.8 level  [name UNDECIDED:'
                  ' DEPTH(6) or the effect DRY/WET, see s5]')

    print("""
PROPAGATION VERDICT (honest):
  * The one PIN that is unit-forced AND universal is op21 -> DSP 0x90, the 0..0.8 level.
    Its NAME is still undecided (DEPTH vs a per-block DRY/WET) -- so it forces a SLOT,
    not a name.
  * ms-helper (op68) and deg-helper (op69) narrow a slot to {ms names} / {PHASE,PAN},
    but several effects have >1 ms name, so they do not force a single name alone.
  * The COUNT cross-check the brief asks for CANNOT be closed statically: the displayed
    count is RAM[0x29AA], itself a value in the object DB, and the T2 record count is
    NOT the UI param count (some records are internal constants -- reverb op75/op67/op76
    are fixed coefficients with no on-screen name).  So propagation is under-constrained
    until the object DB (attack A's follow-up) yields the real per-effect slot count.
  * No CONTRADICTION was produced -- but that is because too few names could be forced,
    not because everything agreed.  Reported as a miss, per the rules of evidence.
""")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
