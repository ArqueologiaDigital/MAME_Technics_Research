#!/usr/bin/env python3
"""kn5000_dsp_blockcoeff.py -- decode the BLOCK-UPLOAD coefficient opcodes and
EXTEND the C-RAM join (tools/kn5000_dsp_namedcoeff.py) with their layouts.

NEC uPD6383GF (Technics SX-KN5000 IC311) effects DSP.  Companion to
notes/kn5000-dsp-blockcoeff.md.  Nothing in the DSP core is touched; this imports
the existing corpus + host-parameter tools and re-runs the join with the block
opcodes' C-RAM layout included.

THE BLOCK OPCODES (identified from the sub-CPU v1.42 disassembly dispatch table
OFFSETS_14745 @0x03CB8E, anchored on op0x62=038EAC / op0x63=038EB9 / op0x65=038F9B /
op0x68=03925E -- all three note-confirmed -- so the whole opcode->eval-helper->writer
chain is pinned):

  op   eval      writer sequence                 space  cells  used by
  ----------------------------------------------------------------------------
  0x70 0x0397F3  {0387E6}x3 (imm 00/10/20)        C-RAM   6     biquad designer (known)
  0x73 0x039ABD  0387E6 + 0388B3 x4               C-RAM   5     14 delay/all-pass effects
  0x71 0x03A933  0387E6 + 0388B3 x4 (per branch)  C-RAM   5     (declared by NO effect)
  0x77 0x03B646  0387E6 (1 per call)              C-RAM   1     ENSEMBLE per-voice depth
  0x76 0x039D98  0387E6 (fixed 3-word, expanded)  C-RAM   3     damping filter (known)
  0x75 0x03869B  038539 + 038606 x3, 8-9 iters    D-RAM   4/it  reverb decay/state (NOT C-RAM)
  0x24 0x03A4B7  0387E6 (1 per call, imm 19)      C-RAM   1     AUTO WAH gain curve
  0x6B 0x03943B  038539 (1 per call, imm 14)      D-RAM   1     (state, NOT C-RAM)
  0x6C 0x0394CD  038539 (1 per call, imm 14)      D-RAM   1     (state, NOT C-RAM)

  * writer 0387E6 -> `801.0.NN.821`(set ptr)+`A..26`(datum) = C-RAM coefficient space,
    continuation 0388B3 = `A..26` datum only (relies on DSP pointer auto-increment).
  * writer 038539/03846C -> `000.1.NN.000`(set ptr)+`A..15`(datum) = the OTHER (D-RAM /
    state) space, continuation 038606 = `A..15` datum only.
  The class-A coefficient CURSOR reads C-RAM (base 0x00 MEASURED), so only the 0387E6
  writers name class-A multiplies.  op0x75/0x6B/0x6C write D-RAM and cannot.

WHAT THIS ADDS TO THE JOIN (namedcoeff had op0x73/0x71/0x77 desc '-' = EXCLUDED):
  * op0x73 -> a 5-cell C-RAM block per T2-confirmed operand (base..base+4).
  * op0x77 -> a single C-RAM cell per T2-confirmed operand (the per-voice depth).
Block expansion is driven by T2-CONFIRMED operands ONLY (the T1 map over-counts, e.g.
op0x73's T1 lists base AND base+1 for each section; expanding both would falsely claim
a neighbour's cell).  This is the padding-zero hazard of namedcoeff generalised to
blocks, and it is guarded here.

Reproduce:
    python3 tools/kn5000_dsp_extract.py <subcpu.rom> /tmp/progs
    python3 tools/kn5000_dsp_blockcoeff.py <subcpu.rom> /tmp/progs <maincpu.rom>
Sections: blocks biqctl coverage delta ensemble  (default: all).
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_class2 as K          # noqa: E402
import kn5000_dsp_params as P          # noqa: E402
import kn5000_dsp_namedcoeff as N      # noqa: E402


# --------------------------------------------------------------------------
#  Block layout, decoded from the sub-CPU writers (see module docstring).
#  span = consecutive C-RAM cells written from the T1 base address.
#  Only +0 (C-RAM, writer 0387E6/0388B3) opcodes can name a class-A multiply.
# --------------------------------------------------------------------------
BLOCK_SPAN = {
    0x70: 6,   # biquad designer (b1,b0,b2,-a1,-a2,makeup)  -- already in namedcoeff
    0x76: 3,   # fixed damping/tone filter                  -- already in namedcoeff
    0x73: 5,   # computed bilinear 5-coeff section (NEW)
    0x71: 5,   # computed 5-coeff section, 3 filter types (NEW; declared by no effect)
    0x77: 1,   # per-voice depth, single computed cell (NEW)
}
# opcodes whose 0387E6 writer lands in C-RAM (name class-A multiplies)
CRAM_OPCODES = N.coeff_opcodes() | {0x73, 0x71, 0x77}

BLOCK_ROLE = {
    0x73: ("filter",  "INFERRED", "computed 5-coeff bilinear section (all-pass/comb of the delay stage)"),
    0x71: ("filter",  "INFERRED", "computed 5-coeff section, 3 filter types (unused by any effect)"),
    0x77: ("depth",   "INFERRED", "ENSEMBLE per-voice modulation depth (192.A.*.41A)"),
}


# --------------------------------------------------------------------------
#  T2-confirmed (opcode, operand) set for one algo.  A pair is confirmed if it
#  appears in EVERY surviving parse of its record (ambiguous parses intersected).
#  This is the chorus-note methodology -- the T1 map alone over-counts.
# --------------------------------------------------------------------------
def t2_confirmed(rom, algo):
    t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
    t2p = rom.u32le(P.ALGO_T2_ARRAY + 4 * algo)
    if not t2p or not t1p or t1p == P.NULL_T1:
        return set()
    addrmap = {op: ent for (_a, op, ent) in P.parse_t1(rom, t1p)}
    confirmed = set()
    for (_a, _ln, body) in P.split_records(rom, t2p):
        sols = P.decode_record(rom, body, addrmap)
        if not sols:
            continue
        # the intended decode is the parse with the MOST instructions (a record
        # is a packed list; the maximal parse consumes every instruction -- this
        # is what params.py section 3 reports and what the chorus note used to
        # find ENSEMBLE's 6 voices).  decode_record caps at 4 solutions, so a
        # blind intersection under-counts long records; the max-length parse does
        # not.  Pairs still must resolve to a real T1 operand.
        best = max(sols, key=len)
        for (op, oper, _im) in best:
            if op in addrmap and oper < len(addrmap[op]):
                confirmed.add((op, oper))
    return confirmed


# --------------------------------------------------------------------------
#  Extended C-RAM host map: namedcoeff's map (single +0 writers, biquad/damping
#  expanded) PLUS the block opcodes 0x73/0x71/0x77 expanded from T2-confirmed
#  operands.  Additive -- never overrides an existing namedcoeff cell.
# --------------------------------------------------------------------------
def host_coeff_map_ext(rom, algo):
    amap = dict(N.host_coeff_map(rom, algo))      # existing 391-name base
    t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
    if not t1p or t1p == P.NULL_T1:
        return amap, {}
    t1 = {op: ent for (_a, op, ent) in P.parse_t1(rom, t1p)}
    confirmed = t2_confirmed(rom, algo)
    added = {}
    for op in (0x73, 0x71, 0x77):
        if op not in t1:
            continue
        span = BLOCK_SPAN[op]
        for (bop, oper) in sorted(confirmed):
            if bop != op or oper >= len(t1[op]):
                continue
            base = t1[op][oper]
            if base == 0 and oper > 0:            # padding guard (never mint bogus 0x00)
                continue
            for c in range(span):
                cell = (base + c) & 0xFF
                if cell not in amap:               # never override namedcoeff
                    amap[cell] = (op, oper, c)
                    added[cell] = (op, oper, c)
    return amap, added


def role_of(op):
    if op in BLOCK_ROLE:
        return BLOCK_ROLE[op][0], BLOCK_ROLE[op][1]
    r = N.OPCODE_ROLE.get(op)
    return (r[0], r[1]) if r else ("coeff", "INFERRED")


# PROVEN LFO accumulator/wrap words (chorus.md sect. 2.2, MEASURED 29/29):
#   092.A.**.200 = phase increment (LFO rate coefficient)
#   094.A.**.200 = wrap/scale, the fixed constant 0x7FFFFF (= 1.0)
# These read BAKED-IN LFO constants, not host block coefficients.  A span-5 block
# that reaches them (e.g. PHASER's op0x73 base 0x0A extends over the LFO cells at
# 0C/0D) is OVER-REACHING; the MEASURED LFO decode wins and the block claim yields.
def _is_lfo_word(w):
    hi, cl, _a, lo = K.fl(w)
    return cl == 0xA and lo == 0x200 and hi in (0x092, 0x094)


def annotate_ext(rom, algo, words, count_revoked=None):
    """Like namedcoeff.annotate_image but with the extended block map."""
    base = N.base_of(algo)
    reverb = base == N.REVERB_BASE
    cmap, _added = host_coeff_map_ext(rom, algo)
    ca = N.cursor_addrs(words)
    ann = [None] * len(words)
    for i, w in enumerate(words):
        if ca[i] is None:
            continue
        haddr = (base + ca[i]) & 0xFF
        if reverb and haddr in N.REVERB_SLOTS:
            role, name = N.REVERB_SLOTS[haddr]
            ann[i] = (ca[i], haddr, 0x100, role, "PROVEN", name)
            continue
        hit = cmap.get(haddr)
        if hit is None:
            ann[i] = (ca[i], haddr, None, None, None, None)
            continue
        op, oi, cell = hit
        # conflict guard: a NEW block opcode must not overwrite the MEASURED LFO
        # decode.  Report as an over-reach miss, leave the word unnamed.
        if op in (0x73, 0x71, 0x77) and _is_lfo_word(w):
            if count_revoked is not None:
                count_revoked[0] += 1
            ann[i] = (ca[i], haddr, None, None, None, None)
            continue
        role, ev = role_of(op)
        if op == 0x70:
            name = "biquad " + N.BIQUAD_CELLS[cell]
        elif op == 0x73:
            name = "filter section cell %d" % cell
        elif op == 0x77:
            name = "ENSEMBLE voice depth"
        elif op == 0x76:
            name = "damping filter tap %d" % cell
        else:
            name = "op0x%02X[%d]" % (op, oi)
        ann[i] = (ca[i], haddr, op, role, ev, name)
    return ann


# ==========================================================================
def sec_blocks(progs, imgs, rom, mrom):
    print("=== BLOCK-OPCODE LAYOUT (decoded from the sub-CPU writers)\n")
    print("  op   eval     space  span  written-cells (C-RAM) per effect (T2-confirmed)\n")
    for op in (0x73, 0x77, 0x71):
        span = BLOCK_SPAN[op]
        print(f"  op0x{op:02X}  span {span}  ({BLOCK_ROLE[op][2]})")
        for a in sorted(imgs):
            t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * a)
            if not t1p or t1p == P.NULL_T1:
                continue
            t1 = {o: e for (_x, o, e) in P.parse_t1(rom, t1p)}
            if op not in t1:
                continue
            conf = sorted(oper for (bop, oper) in t2_confirmed(rom, a) if bop == op)
            cells = []
            for oper in conf:
                if oper < len(t1[op]):
                    b = t1[op][oper]
                    cells.append("0x%02X..0x%02X" % (b, (b + span - 1) & 0xFF) if span > 1 else "0x%02X" % b)
            if cells:
                print(f"     algo {a:>3} {P.effect_name(mrom, a):20} {' '.join(cells)}")
        print()


def sec_biqctl(progs, imgs, rom, mrom):
    print("=== POSITIVE CONTROL 1: biquad order still 6/6 with the block map\n")
    eq = next((a for a in imgs if mrom and P.effect_name(mrom, a) == 'PARAMETRIC EQ'), None)
    if eq is None:
        print("  EQ not found"); return
    words = progs[eq]
    ca = N.cursor_addrs(words)
    got = {}
    for i, w in enumerate(words):
        if ca[i] is not None and ca[i] < 6:
            got.setdefault(ca[i], w)
    ok = True
    for off in range(6):
        w = got.get(off)
        exp = N.BIQUAD_CLASSA_ORDER[off]
        good = (w == exp)
        ok &= good
        print(f"  C-RAM[0x0{off}] = {N.BIQUAD_CELLS[off]:>7}  {K.fmt(w) if w else '--':>14}  {'OK' if good else 'MISS'}")
    print(f"\n  biquad-order control: {'PASS' if ok else 'FAIL'}\n")
    return ok


def sec_ensemble(progs, imgs, rom, mrom):
    print("=== POSITIVE CONTROL 2: op0x77 ENSEMBLE = 3 voices x 2 channels = 6 taps\n")
    ens = next((a for a in imgs if mrom and P.effect_name(mrom, a) == 'ENSEMBLE'), None)
    if ens is None:
        print("  ENSEMBLE not found"); return
    t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * ens)
    t1 = {o: e for (_x, o, e) in P.parse_t1(rom, t1p)}
    conf = sorted(oper for (bop, oper) in t2_confirmed(rom, ens) if bop == 0x77)
    cells = [t1[0x77][o] for o in conf if o < len(t1[0x77])]
    print(f"  op0x77 T2-confirmed operands: {conf}")
    print(f"  -> C-RAM cells: {[hex(c) for c in cells]}  (predict 6: 02 04 06 | 09 0B 0D)")
    words = progs[ens]
    ann = annotate_ext(rom, ens, words)
    named = [x for x in ann if x is not None and x[2] == 0x77]
    print(f"  class-A words now named ENSEMBLE-voice-depth: {len(named)}")
    ok = (len(cells) == 6 and len(named) == 6)
    print(f"\n  ENSEMBLE voice-count control: {'PASS (6 taps)' if ok else 'CHECK'}\n")
    return ok


def sec_coverage(progs, imgs, rom, mrom):
    print("=== COVERAGE with the block map (of 822 class-A multiplies)\n")
    total = named = 0
    role_ct = collections.Counter()
    per = []
    for a in sorted(imgs):
        words = progs[a]
        ann = annotate_ext(rom, a, words)
        ch = sum(1 for x in ann if x is not None)
        nh = 0
        for x in ann:
            if x is None:
                continue
            total += 1
            if x[2] is not None:
                named += 1
                nh += 1
                role_ct[x[3]] += 1
        per.append((a, P.effect_name(mrom, a) if mrom else str(a), ch, nh))
    print(f"  class-A words in corpus : {total}")
    print(f"  NAMED                   : {named}  ({100.0*named/total:.1f} %)")
    print(f"  unnamed                 : {total-named}\n")
    print("  by ROLE:")
    for r, c in role_ct.most_common():
        print(f"    {r:14} {c}")
    print("\n  per-effect (named/class-A):")
    for a, nm, ch, nh in per:
        if ch:
            print(f"    algo {a:>3} {nm:20} {nh:>3}/{ch:<3}")
    print()
    return named, total


def sec_delta(progs, imgs, rom, mrom):
    print("=== DELTA vs namedcoeff (which multiplies the block map NEWLY names)\n")
    newly = collections.Counter()
    for a in sorted(imgs):
        words = progs[a]
        base = N.base_of(a)
        old = N.annotate_image(words, base, N.host_coeff_map(rom, a), base == N.REVERB_BASE)
        new = annotate_ext(rom, a, words)
        d = 0
        for xo, xn in zip(old, new):
            if xo is None:
                continue
            if xo[2] is None and xn[2] is not None:
                d += 1
                newly[xn[2]] += 1
        if d:
            print(f"    algo {a:>3} {P.effect_name(mrom, a):20} +{d}")
    print(f"\n  newly named by opcode: " +
          ", ".join(f"op0x{op:02X}:{c}" for op, c in newly.most_common()))
    print(f"  total newly named: {sum(newly.values())}\n")


SECTIONS = {'blocks': sec_blocks, 'biqctl': sec_biqctl, 'ensemble': sec_ensemble,
            'coverage': sec_coverage, 'delta': sec_delta}


def main(argv):
    sub = argv[1] if len(argv) > 1 else os.path.expanduser(
        '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
    pdir = argv[2] if len(argv) > 2 else '/tmp/progs'
    rest = argv[3:]
    mainrom = None
    if rest and os.path.exists(rest[0]):
        mainrom = rest[0]; rest = rest[1:]
    else:
        cand = os.path.expanduser(
            '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom')
        if os.path.exists(cand):
            mainrom = cand
    want = rest or ['blocks', 'biqctl', 'ensemble', 'coverage', 'delta']
    progs = K.load_progs(pdir)
    imgs = K.images(progs)
    rom = P.Rom(sub, P.SUB_BASE)
    mrom = P.Rom(mainrom, 0) if mainrom else None
    for s in want:
        if s in SECTIONS:
            SECTIONS[s](progs, imgs, rom, mrom)
        else:
            print('unknown section', s)


if __name__ == '__main__':
    main(sys.argv)
