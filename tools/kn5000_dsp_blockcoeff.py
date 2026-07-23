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
#  Block layout + join were FOLDED INTO kn5000_dsp_namedcoeff.py (2026-07-23):
#  a single call to N.host_coeff_map / N.annotate_image now returns the full
#  391 individual + 109 block = 500 union.  This module keeps its REPORT sections
#  (blocks / biqctl / ensemble / coverage / delta) and simply REUSES the unified
#  definitions so there is one source of truth.
# --------------------------------------------------------------------------
BLOCK_SPAN = N.BLOCK_SPAN            # {0x73:5, 0x71:5, 0x77:1}
BLOCK_ROLE = N.BLOCK_ROLE
# opcodes whose 0387E6 writer lands in C-RAM (name class-A multiplies)
CRAM_OPCODES = N.coeff_opcodes() | set(N.BLOCK_OPCODES)

t2_confirmed = N.t2_confirmed        # T2-confirmed (opcode, operand) set per algo
_is_lfo_word = N._is_lfo_word        # the LFO over-reach revocation predicate
role_of = N._role_lookup             # (role, evidence) for an opcode


def host_coeff_map_ext(rom, algo):
    """Compat shim: the unified N.host_coeff_map already includes the block cells.
    Returns (full_map, block_added) where block_added is the +109 delta over the
    individual-only names, for callers that still want the split."""
    full = N.host_coeff_map(rom, algo)
    added = {cell: v for cell, v in full.items() if v[0] in N.BLOCK_OPCODES}
    return full, added


def annotate_ext(rom, algo, words):
    """The unified annotation (individual + block, LFO over-reach revoked)."""
    base = N.base_of(algo)
    return N.annotate_image(words, base, N.host_coeff_map(rom, algo),
                            base == N.REVERB_BASE)


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
        # the individual-only baseline = the unified map with the block cells removed
        full = N.host_coeff_map(rom, a)
        indiv = {c: v for c, v in full.items() if v[0] not in N.BLOCK_OPCODES}
        old = N.annotate_image(words, base, indiv, base == N.REVERB_BASE)
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
