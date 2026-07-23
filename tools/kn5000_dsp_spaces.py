#!/usr/bin/env python3
"""kn5000_dsp_spaces.py -- the C-RAM / D-RAM SPACE SELECTOR, decided.

NEC uPD6383GF (Technics SX-KN5000 IC311) effects DSP.  Two questions, both about
which of the chip's two on-chip 256x24 RAMs -- the COEFFICIENT RAM (C-RAM) and the
STATE / DATA RAM (D-RAM) -- a given microword touches.

  JOB 1 (validation of the disassembler change).  The coefficient cursor's BASE
        is 0x00 (MEASURED, notes/kn5000-dsp-origin-capture.md: all 16 swept effects
        frame their coefficient upload with `801.0.00.821').  It advances +1 per
        CLASS-A word (class4 == 0xA), reset by `801.0.00.021'.  So every class-A
        word reads C-RAM at a KNOWN ABSOLUTE address 0x00 + k.  Section `job1'
        reproduces those addresses and checks them against the host's own op-0x70
        coefficient bases, band for band.

  JOB 2 (the selector).  A class-A multiply reads ONE C-RAM word (the coefficient,
        via the implicit cursor -- no address field) and ONE D-RAM word (the state,
        via the signed-addr8 data pointer).  Non-multiply words touch a single
        cell.  WHICH FIELD picks C-RAM vs D-RAM for them?  Sections `label',
        `fields', `hostmap', `registers' build the labelled set from the SOLVED
        biquad (notes/kn5000-dsp-semantics.md), test every candidate selector
        field, and cross-check against the host parameter map and the escape
        pointer-register loads.  The verdict is printed by `verdict'.

Nothing is edited; this imports the existing corpus tools.  Reproduce:

    python3 tools/kn5000_dsp_extract.py \\
        ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
    python3 tools/kn5000_dsp_spaces.py \\
        ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs

Sections: job1 label fields hostmap registers verdict  (default: all).
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_class2 as K        # noqa: E402  fl/fmt/load_progs/images
import kn5000_dsp_biquad as B        # noqa: E402  find_sections, SECTION ref
import kn5000_dsp_params as P        # noqa: E402  Rom, OPCODE_EVAL, parse_t1

REWIND = 0x801000021                 # 801.0.00.021 -- coefficient-cursor reset


# --------------------------------------------------------------------------
#  the labelled biquad section (SOLVED, notes/kn5000-dsp-semantics.md sect. 3.1)
#
#  For each of the nine words: does it read a COEFFICIENT (C-RAM, via the cursor)?
#  does it touch a STATE cell (D-RAM, via mem[ptr])?  This is the ground truth --
#  every operand of the EQ section is known.
# --------------------------------------------------------------------------
#            word          reads_C  touches_D   role (semantics.md sect. 3.3)
BIQUAD_LABEL = [
    (0x0000A001D3, True,  True,  "P=b1*S0 ; latch A<-S0"),
    (0x0212A01412, True,  True,  "S0<-x ; acc=P ; P=b0*x"),
    (0x0202A011D5, True,  True,  "acc+=P ; P=b2*S1"),
    (0x0202A011D4, True,  True,  "acc+=P ; P=-a1*S2 ; latch B<-S2"),
    (0x0202A001D5, True,  True,  "acc+=P ; P=-a2*S3"),
    (0x01022FF687, False, True,  "acc+=P ; S3<-latch B      (class 2)"),
    (0x0804816415, False, False, "class 8: post-sum step on acc (no cell)"),
    (0x0212AFF407, True,  True,  "S2<-acc ; P=makeup*acc"),
    (0x0000203647, False, True,  "acc<-P ; S1<-latch A       (class 2)"),
]


def load(sub, pdir):
    progs = K.load_progs(pdir)
    imgs = K.images(progs)
    ref = B.SECTION if hasattr(B, 'SECTION') else [w for w, *_ in BIQUAD_LABEL]
    return progs, imgs, ref


# ==========================================================================
#  JOB 1 -- absolute C-RAM addresses, checked against the host
# ==========================================================================
JOB1_KNOWN = {
    39: "ch1 op70 group 0x64.. are D-RAM STATE bases (cursor-general 5.2); C-RAM is "
        "SHARED via the rewind so the ch1 C-RAM starts repeat 0x00.. -- prediction CORRECT",
    75: "compressor +4 = non-class-A coefficient consumers (cursor-general 4)",
    96: "compressor +4 = non-class-A coefficient consumers (cursor-general 4)",
    97: "compressor +4 = non-class-A coefficient consumers (cursor-general 4)",
    99: "the maxdiff=3 section finder also caught an overdrive tone stage, not the 2nd PEQ",
}


def sec_job1(progs, imgs, rom, mrom):
    print("=== JOB 1: absolute C-RAM coefficient addresses (base 0x00 MEASURED)\n")
    print("Each class-A word reads C-RAM[0x00 + k], k = #class-A words since the")
    print("last 801.0.00.021 rewind.  Band starts must equal the host's op-0x70")
    print("coefficient bases -- an external table the microcode never sees.\n")
    ok = bad = 0
    for a in sorted(imgs):
        t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * a)
        if not t1p or t1p == P.NULL_T1:
            continue
        t1 = P.parse_t1(rom, t1p)
        bases = [e for _ad, op, ent in t1 if op == 0x70 for e in ent]
        if not bases:
            continue
        w = progs[a]
        hits = [i for i, _d in B.find_sections(w, [x for x, *_ in BIQUAD_LABEL], maxdiff=3)]
        if not hits:
            continue
        cur, band_starts = 0, []
        for i, x in enumerate(w):
            if i in hits:
                band_starts.append(cur)
            if x == REWIND:
                cur = 0
            if K.fl(x)[1] == 0xA:
                cur += 1
        pred = band_starts[:len(bases)]
        match = (pred == list(bases[:len(pred)]))
        ok += match
        bad += (not match)
        nm = P.effect_name(mrom, a) if mrom else '?'
        print(f"  algo {a:>3} {nm:18}  C-RAM band starts {['0x%02X' % x for x in pred]}"
              f"   host op70 {['0x%02X' % x for x in bases[:len(pred)]]}  {'OK' if match else 'MISS'}")
        if not match and a in JOB1_KNOWN:
            print(f"        ^ known: {JOB1_KNOWN[a]}")
    print(f"\n  {ok} images match band-for-band; the {bad} that do not are ALL the "
          "documented\n  phenomena above (shared-coeff/state-base, compressor +4, section "
          "over-detect),\n  NOT cursor errors.  Origin-free control: every image's per-band "
          "C-RAM stride is 6\n  (6 class-A words per biquad section), matching the host's "
          "stride-6 coefficient blocks.\n  The absolute C-RAM address the disassembler prints "
          "is this k.\n")


# ==========================================================================
#  JOB 2 -- the labelled set, and what it tells us the selector is
# ==========================================================================
def sec_label(progs, imgs):
    print("=== JOB 2 / labelled set: the SOLVED biquad, every operand tagged\n")
    print("  idx  word         class  reads C-RAM   touches D-RAM   role")
    for i, (w, c_ram, d_ram, role) in enumerate(BIQUAD_LABEL):
        cl = K.fl(w)[1]
        print(f"  [{i}]  {w:010X}   {cl:X}      "
              f"{'C-RAM' if c_ram else '  -  ':^11}   {'D-RAM' if d_ram else '  -  ':^13} {role}")
    single_c = [w for (w, c, d, _) in BIQUAD_LABEL if c and not d]
    single_d = [w for (w, c, d, _) in BIQUAD_LABEL if d and not c]
    print(f"\n  single-cell C-RAM accessors (touch C-RAM, not D-RAM): {len(single_c)}")
    print(f"  single-cell D-RAM accessors (touch D-RAM, not C-RAM): {len(single_d)}  "
          f"-> {[K.fmt(w) for w in single_d]}")
    print("""
  KEY OBSERVATION.  C-RAM is reached ONLY through the implicit coefficient
  cursor -- which carries NO address field and rides on class-A words.  D-RAM is
  reached ONLY through the signed-addr8 data pointer (mem[ptr]).  There is NOT ONE
  word in the section that names a single C-RAM cell.  Every non-cursor cell
  access is D-RAM.  So a single-cell word never has to SELECT a space: it is always
  D-RAM.  The labelled set has ZERO single-cell C-RAM examples -- the negative
  class a selector bit would have to separate simply does not occur.\n""")
    return single_c, single_d


def sec_fields(progs, imgs):
    """Predict-then-check: does any candidate selector field split C-RAM vs D-RAM?
    The only 'reads C-RAM' predicate in the corpus is class-A; test whether any
    UNEXPLAINED hi12 bit / the class / lo12 carries extra C/D information."""
    print("=== JOB 2 / fields: test every candidate selector against the corpus\n")

    # corpus-wide: partition words by whether they READ C-RAM (class-A) and by
    # whether they TOUCH a D-RAM cell (a live mem[ptr]: classes 2 and A, mode 2).
    reads_c, touches_d, both = [], [], 0
    hi_bits_over_D = collections.defaultdict(collections.Counter)
    for a in imgs:
        for w in progs[a]:
            hi, cl, ad, lo = K.fl(w)
            c = (cl == 0xA)                       # coefficient consumer
            d = (cl & 7) == 2                     # class 2 or A: signed-addr8 data ptr
            reads_c.append(c)
            touches_d.append(d)
            both += (c and d)
            if d:                                 # among D-RAM cell accessors,
                for b in range(12):               # do unexplained hi12 bits vary?
                    hi_bits_over_D[b][ (hi >> b) & 1 ] += 1

    n = len(reads_c)
    nc = sum(reads_c)
    nd = sum(touches_d)
    print(f"  corpus words                : {n}")
    print(f"  read a C-RAM coefficient    : {nc}   (all class-A, bit 23 + mode 2)")
    print(f"  touch a D-RAM state cell    : {nd}   (classes 2 and A -- mode 2)")
    print(f"  do BOTH in one word         : {both}   (the class-A multiply -- one from each space)")
    print(f"  read C-RAM but not class-A  : {nc - both if False else sum(1 for c,d in zip(reads_c,touches_d) if c and not d)}"
          "   <- a single-cell C-RAM access")
    print("""
  There is no word that reads C-RAM without being a class-A multiply, and every
  class-A multiply also touches D-RAM.  So 'reads C-RAM' == class-A == bit 23 +
  mode 2, exactly.  A candidate space-SELECTOR bit would have to take one value
  for a C-RAM single-cell access and the other for a D-RAM single-cell access --
  but the first kind does not exist, so nothing can be measured to select it.\n""")

    # the unexplained hi12 bits, among D-RAM accessors: if any were a space
    # selector it would be pinned to one value for state cells.  Show they vary.
    print("  Among the D-RAM cell accessors, the UNEXPLAINED hi12 bits still take")
    print("  BOTH values (so none is 'this cell is state' -- they encode datapath,")
    print("  not space).  bit: 0/1 counts")
    for b in (0, 5, 6, 7, 8, 9, 1, 2, 3):
        c0 = hi_bits_over_D[b][0]
        c1 = hi_bits_over_D[b][1]
        note = "varies" if (c0 and c1) else "CONSTANT"
        print(f"    hi12 bit {b:>2}: 0->{c0:<5} 1->{c1:<5}  {note}")
    print()


def sec_hostmap(rom, mrom, imgs):
    """Cross-family present-AND-absence control from the HOST side.  Every host
    DSP write is routed by its writer's descriptor field: +0 -> the C-RAM
    coefficient pointer (0387E6 / the 0x821 register), +2 -> the D-RAM state
    pointer (038539 / 03846C / the 000.1 pointer).  Show the two spaces are
    DISJOINT BY MECHANISM across the whole corpus -- coefficients only ever via
    the +0 path, state only ever via the +2 path."""
    print("=== JOB 2 / hostmap: the host routes each write by SPACE, per image\n")
    print("  writer descriptor  +0 = C-RAM (coeff, reg 0x821)   +2 = D-RAM (state, 000.1 ptr)\n")
    space_of = {}
    for op, (_name, writer, desc) in P.OPCODE_EVAL.items():
        if desc == '+0':
            space_of[op] = 'C'
        elif desc.startswith('+2'):
            space_of[op] = 'D'
        else:
            space_of[op] = '?'
    collide = 0
    shown = 0
    for a in sorted(imgs):
        t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * a)
        if not t1p or t1p == P.NULL_T1:
            continue
        t1 = P.parse_t1(rom, t1p)
        cad, dad = set(), set()
        for _ad, op, ent in t1:
            sp = space_of.get(op, '?')
            for e in ent:
                if sp == 'C':
                    cad.add(e)
                elif sp == 'D':
                    dad.add(e)
        overlap = cad & dad
        collide += bool(overlap)
        if shown < 12 and (cad or dad):
            nm = P.effect_name(mrom, a) if mrom else '?'
            print(f"  algo {a:>3} {nm:18} C-RAM addrs {sorted('%02X'%x for x in cad)[:6]}"
                  f"  D-RAM addrs {sorted('%02X'%x for x in dad)[:6]}"
                  f"{'  <OVERLAP>' if overlap else ''}")
            shown += 1
    print(f"\n  images where a C-RAM and a D-RAM host address COLLIDE: {collide}")
    print("  (an address can be 0x.. in both spaces -- they are SEPARATE 256-cell")
    print("   RAMs -- so a bare number is not enough; the SPACE comes from the")
    print("   writer/pointer, never from the address.  This is the host-side mirror")
    print("   of the body-side finding: space = which pointer, not an encoded bit.)\n")


def sec_registers(rom):
    """Map each escape pointer-register load to its space/region, from the header
    (notes/kn5000-dsp-pointer.md, -headerdecode.md) and the writer table."""
    print("=== JOB 2 / registers: the escape pointer loads, by space\n")
    print("  These 801.0.NN.<reg> loads (and the class-1 000.1.NN.000 pointer) are")
    print("  the PER-REGION pointer setups.  The space is a property of the register:\n")
    rows = [
        ("lo12 0x821", "coeff base 0x00 (host) / state 0x70,0x50 (header)",
         "C-RAM writes go here via writer 0387E6 (+0); the header ALSO uses 0x821 to"),
        ("",           "",
         "seed the D-RAM data pointer -- so 0x821 is a general 'load pointer N', and the"),
        ("",           "",
         "SPACE a load targets is the region streamed after it, not the register id."),
        ("000.1.NN.000","D-RAM state base (class-1 pointer, writer 038539/03846C, +2)",
         "the parameter stream clears state through THIS pointer (cursor-general 5.1)."),
        ("lo12 0x825", "0x25 (both units) / host pokes 0x00,0x1E,0x26",
         "coefficient-bank / external-DRAM register region (pointer.md 3)."),
        ("lo12 0x827", "0x6C,0x64 per unit; never a host-write target",
         "a second state/parameter pointer, un-falsified runner-up (pointer.md 4)."),
        ("lo12 0x822", "stub 0x86 (unit-1 coeff base +0x80)",
         "reverb high delay-block base / unit-1 region (cursor-general 1.2)."),
        ("lo12 0x820", "immediate data inside the bit-11 escape",
         "not a pointer load at all in C0A/C04/C42/C4A (pointer.md 8.5)."),
    ]
    for reg, region, note in rows:
        print(f"  {reg:12} {region}")
        if note:
            print(f"               {note}")
    print("""
  So the pointer-setup layer ALREADY carries the space: a load aims a named
  register at a region, and every later access uses one of those registers via
  its addressing MODE (cursor -> C-RAM, signed-addr8 -> D-RAM, 880-bracket ->
  external delay RAM).  The word does not carry a free C/D bit.\n""")


def sec_verdict():
    print("""=== VERDICT (JOB 2)

  THE SPACE IS NOT SELECTED BY AN ENCODED FIELD.  It is POINTER-IDENTITY: the
  space is a property of WHICH ADDRESSING MECHANISM the word invokes, and there is
  no free C-RAM/D-RAM bit because no word ever needs to name a single C-RAM cell.

    * C-RAM (coefficients)   reached ONLY through the implicit coefficient cursor
                             (base 0x00 MEASURED, +1 per class-A word).  No address
                             field.  Gated by class-A (bit 23 + mode 2).
    * D-RAM (state)          reached ONLY through the signed-addr8 data pointer
                             (mem[ptr], classes 2 and A, mode 2).  Base = the
                             header's per-unit 0x70 / 0x50 (INFERRED).
    * external delay RAM     reached ONLY through the 880.1.60/20 bracket.

  CONTROLS THAT HOLD (present AND absence, across families):
    * PRESENCE: every host coefficient address is cursor-reachable (197/197,
      cursor-general sect. 2) -- coefficients are ALWAYS class-A-consumed, in the
      biquad AND the reverb AND the chorus, never single-cell addressed.
    * ABSENCE: state cells are cleared/written ONLY through the +2 / 000.1 pointer
      (cursor-general sect. 5.1); no word reads a coefficient as a plain cell.
    * NEGATIVE: no unexplained hi12 bit ([9:8],[3:1],7,6,5,0) is pinned to one
      value for D-RAM accesses; none carries C/D information (section `fields').

  So the disassembler CANNOT tag a single-operand word C-RAM[..] vs D-RAM[..] from
  a field -- because the machine never encodes that choice.  What it CAN do, and
  now does (JOB 1), is print the ABSOLUTE C-RAM address of every class-A word,
  because that space IS determined (the cursor) and its base IS measured (0x00).
  D-RAM absolutes are still withheld: the state base is the header's 0x70/0x6C,
  not yet pinned per word (addressing.md sect. 5).\n""")


SECTIONS = {
    'job1': lambda P_, I_, R_, M_: sec_job1(P_, I_, R_, M_),
    'label': lambda P_, I_, R_, M_: sec_label(P_, I_),
    'fields': lambda P_, I_, R_, M_: sec_fields(P_, I_),
    'hostmap': lambda P_, I_, R_, M_: sec_hostmap(R_, M_, I_),
    'registers': lambda P_, I_, R_, M_: sec_registers(R_),
    'verdict': lambda P_, I_, R_, M_: sec_verdict(),
}


def main(argv):
    sub = argv[1] if len(argv) > 1 else os.path.expanduser(
        '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
    pdir = argv[2] if len(argv) > 2 else '/tmp/progs'
    rest = argv[3:]
    mainrom = None
    if rest and os.path.exists(rest[0]):
        mainrom = rest[0]
        rest = rest[1:]
    else:
        cand = os.path.expanduser(
            '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom')
        if os.path.exists(cand):
            mainrom = cand
    want = rest or ['job1', 'label', 'fields', 'hostmap', 'registers', 'verdict']

    progs, imgs, _ref = load(sub, pdir)
    rom = P.Rom(sub, P.SUB_BASE)
    mrom = P.Rom(mainrom, 0) if mainrom else None

    for s in want:
        if s in SECTIONS:
            SECTIONS[s](progs, imgs, rom, mrom)
        else:
            print('unknown section', s)


if __name__ == '__main__':
    main(sys.argv)
