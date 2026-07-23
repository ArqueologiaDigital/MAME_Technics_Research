#!/usr/bin/env python3
"""kn5000_dsp_namedcoeff.py -- NAME every class-A multiply's coefficient.

NEC uPD6383GF (Technics SX-KN5000 IC311) effects DSP.

THE JOIN (only possible since the disassembler emits ABSOLUTE C-RAM addresses):

  Every class-A word (class4 == 0xA) reads ONE coefficient from C-RAM through the
  implicit cursor.  Its absolute C-RAM address is KNOWN: base + k, where k = number
  of class-A words since the last `801.0.00.021' rewind (base 0x00 unit-0 MEASURED;
  base 0x90 for the unit-1 reverb).  The HOST parameter translator (T1 map,
  notes/kn5000-dsp-parameters.md) writes each effect's coefficients to specific
  C-RAM offsets through a per-opcode eval helper whose ROLE is known (biquad =
  op0x70, damping = op0x76, reverb decay = op0x75, VOLUME = op0x21->0x90, ...).

      class-A multiply  ->  C-RAM[base + k]  ->  host T1: which OPCODE wrote it
                        ->  the opcode's ROLE / the effect's NAMED parameter.

  This names the operand of the ~822 class-A multiplies, and lets non-multiply
  neighbours inherit meaning by the role of the product they consume.

Nothing is edited here; this imports the existing corpus tools.  Reproduce:

    python3 tools/kn5000_dsp_extract.py \\
        ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
    python3 tools/kn5000_dsp_namedcoeff.py \\
        ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs \\
        ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom

Sections: biqctl table coverage neighbours unknowns  (default: all).
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_class2 as K        # noqa: E402  fl/fmt/load_progs/images
import kn5000_dsp_params as P        # noqa: E402  Rom, OPCODE_EVAL, parse_t1

RSTCUR = 0x801000021                 # 801.0.00.021 -- coefficient-cursor reset
REVERB_ALGOS = set(range(16, 28))    # the 12 reverbs = the ONLY unit-1 image (INDEX)
REVERB_BASE = 0x90                   # unit-1 coeff bank base (cursor-general 1.2 / 3.2)


# --------------------------------------------------------------------------
#  the disassembler's coefficient-consumer predicate and cursor, replicated
#  EXACTLY (src/devices/cpu/upd6383/upd6383d.cpp coeff_consumer / disassemble).
# --------------------------------------------------------------------------
def is_classA(w):
    return K.fl(w)[1] == 0xA


def cursor_addrs(words):
    """For each word index, the absolute cursor k (relative, base 0) if it is a
    class-A word, else None.  Reset by RSTCUR, +1 per class-A -- the disassembler's
    algorithm (count class-A since last rstcur / buffer start)."""
    out = [None] * len(words)
    k = 0
    for i, w in enumerate(words):
        if w == RSTCUR:
            k = 0
        if is_classA(w):
            out[i] = k
            k += 1
    return out


# --------------------------------------------------------------------------
#  opcode -> ROLE.  Established from the DECODED effects, tagged by evidence:
#   PROVEN  = pinned by the solved biquad / reverb / host-write control
#   INFERRED= role follows from the opcode's eval helper + paramlist family
# --------------------------------------------------------------------------
#            role,        evidence,   note
OPCODE_ROLE = {
    0x70: ("EQ",            "PROVEN",  "biquad coefficient (semantics.md; 6/band)"),
    0x76: ("damping",      "PROVEN",  "HIGH DAMP GAIN 3-word filter (cursor-general 6)"),
    0x75: ("decay",       "PROVEN",  "reverb decay coeff -> 0x97 (parameters.md 5)"),
    0x66: ("mix/tap",      "INFERRED","output-tail / diffuser gains in reverb (cursor-general 3.3)"),
    0x21: ("output-level", "PROVEN",  "VOLUME, 0x90, 0..0.8 dB law (parameters.md 5)"),
    0x74: ("input/tone",   "INFERRED","fixed 0x1D tone constant (26/38 images)"),
    0x72: ("gain-computer","PROVEN",  "compressor THRESHOLD/RATIO (paramsemantics 3)"),
    0x6E: ("coeff",        "INFERRED","+0 writer (eval_039599)"),
    0x6F: ("coeff",        "INFERRED","+0 writer (eval_0396C2)"),
    0x64: ("coeff",        "INFERRED","+0 writer (float k=0.552)"),
    0x61: ("coeff",        "INFERRED","+0 writer (eval_038E9F)"),
    0x6A: ("coeff",        "INFERRED","+0 writer (eval_0392F2)"),
    0x67: ("delay/tap",    "INFERRED","+0 writer (eval_039206; often ext-DRAM regs)"),
    0x78: ("coeff",        "INFERRED","+0 writer (eval_03A22A)"),
    0x79: ("coeff",        "INFERRED","+0 writer (eval_03A282)"),
    0x24: ("coeff",        "INFERRED","+0 writer (eval_03A4B7)"),
    0x40: ("coeff",        "INFERRED","+0 writer (eval_03A4A0)"),
    0x62: ("output-level", "INFERRED","CURVE_D dB volume law (parameters.md 5)"),
}

# biquad Direct-Form-I coefficient names, C-RAM offset 0..5 within a band
# (semantics.md sect. 3.1; the POSITIVE CONTROL for the whole join).
BIQUAD_CELLS = ["b1", "b0", "b2", "-a1", "-a2", "makeup"]
# the labelled class-A words of the solved EQ section, IN band order 0..5
# (the class-8 post-sum step 804.8.16.415 is NOT class-A, skipped by the cursor).
BIQUAD_CLASSA_ORDER = [0x0000A001D3, 0x0212A01412, 0x0202A011D5,
                       0x0202A011D4, 0x0202A001D5, 0x0212AFF407]


def coeff_opcodes():
    """opcodes whose writer descriptor is +0 -> the C-RAM coefficient pointer."""
    return {op for op, (_n, _w, desc) in P.OPCODE_EVAL.items() if desc == '+0'}


# PROVEN reverb bank slot -> (role, name) overlay, straight from the fully-decoded
# reverb (cursor-general.md sect. 3.2 / 3.3).  base 0x90.  Every class-A word of the
# 133-word reverb image lands on one of these, so the reverb is named 33/33.
REVERB_SLOTS = {
    0x90: ("input-gain", "input scaling"), 0x91: ("input-gain", "input scaling"),
    0x92: ("input-gain", "input scaling"),
    0x93: ("damping", "damping filter #1 (HIGH DAMP GAIN)"),
    0x94: ("damping", "damping filter #1"), 0x95: ("damping", "damping filter #1"),
    0x96: ("decay", "DRAM tap gain (0.500)"),
    0x97: ("decay", "op0x75 reverb decay coeff"),
    0x98: ("decay", "diffuser ladder-0 (REVERB TIME)"),
    0x99: ("decay", "diffuser ladder-0"), 0x9A: ("decay", "diffuser ladder-0"),
    0x9B: ("decay", "diffuser ladder-0"), 0x9C: ("decay", "diffuser ladder-0"),
    0x9D: ("decay", "DRAM tap gain (0.500)"),
    0x9E: ("damping", "op0x76 damping triple #2 (HIGH DAMP GAIN)"),
    0x9F: ("damping", "damping triple #2"), 0xA0: ("damping", "damping triple #2"),
    0xA1: ("decay", "diffuser ladder-1 (REVERB TIME)"),
    0xA2: ("decay", "diffuser ladder-1"), 0xA3: ("decay", "diffuser ladder-1"),
    0xA4: ("decay", "diffuser ladder-1"),
    0xA5: ("decay", "DRAM tap gain (0.500)"),
    0xA6: ("damping", "op0x76 damping triple #3 (HIGH DAMP GAIN)"),
    0xA7: ("damping", "damping triple #3"), 0xA8: ("damping", "damping triple #3"),
    0xA9: ("mix", "LEFT output tail (op0x66 / ER.LEVEL)"),
    0xAA: ("mix", "LEFT output tail"), 0xAB: ("mix", "LEFT output tail"),
    0xAC: ("mix", "LEFT output tail"),
    0xAD: ("mix", "RIGHT output tail"), 0xAE: ("mix", "RIGHT output tail"),
    0xAF: ("mix", "RIGHT output tail (op0x66)"),
    0xB0: ("mix", "RIGHT output tail"),
}


def host_coeff_map(rom, algo):
    """Build {C-RAM address -> (opcode, operand_index)} for one algo, restricted
    to +0 (C-RAM coefficient) writers.  MULTI-CELL coefficients are EXPANDED:
    op0x70 (biquad) writes 6 consecutive cells per band (b1,b0,b2,-a1,-a2,makeup);
    op0x76 (damping) writes 3 consecutive cells per entry (cursor-general 6).
    Returns {} if no stream."""
    t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
    if not t1p or t1p == P.NULL_T1:
        return {}
    cops = coeff_opcodes()
    amap = {}
    for _ad, op, ent in P.parse_t1(rom, t1p):
        if op not in cops:
            continue
        span = 6 if op == 0x70 else (3 if op == 0x76 else 1)
        for oi, e in enumerate(ent):
            # T1 entries are 0x00-PADDED to a fixed record width (e.g. op0x74 =
            # "1D 00 00 00"); a 0x00 at operand index > 0 is padding, not a real
            # coefficient address -- dropping it removes false C-RAM[0x00] hits.
            if e == 0 and oi > 0:
                continue
            for c in range(span):
                amap.setdefault((e + c) & 0xFF, (op, oi, c))  # first writer wins
    return amap


def base_of(algo):
    # images() collapses the 12 byte-identical reverbs to representative algo 16,
    # which is in REVERB_ALGOS -- the only unit-1 image (INDEX).  base 0x90.
    return REVERB_BASE if algo in REVERB_ALGOS else 0x00


# ==========================================================================
#  POSITIVE CONTROL -- the biquad coefficient ORDER
# ==========================================================================
def sec_biqctl(progs, imgs, rom, mrom):
    print("=== POSITIVE CONTROL: biquad coefficient order b1,b0,b2,-a1,-a2,makeup\n")
    print("  If the C-RAM join mis-orders these six cells (00..05) the whole join")
    print("  is wrong.  Check algo 39 (PARAMETRIC EQ): the class-A words at band")
    print("  offsets 0..5 must be the SOLVED biquad section words, in order.\n")
    # find the EQ image
    eq = None
    for a in imgs:
        if mrom and P.effect_name(mrom, a) == 'PARAMETRIC EQ':
            eq = a
            break
    if eq is None:
        print("  PARAMETRIC EQ image not found"); return
    words = progs[eq]
    ca = cursor_addrs(words)
    # collect the class-A words at each cursor cell 0..5 of the FIRST band
    got = {}
    for i, w in enumerate(words):
        if ca[i] is not None and ca[i] < 6:
            got.setdefault(ca[i], w)
    allok = True
    for off in range(6):
        w = got.get(off)
        exp = BIQUAD_CLASSA_ORDER[off]
        ok = (w == exp)
        allok &= ok
        print(f"  C-RAM[0x0{off}] = {BIQUAD_CELLS[off]:>7}  word {K.fmt(w) if w else '   --    '}"
              f"   expect {K.fmt(exp)}   {'OK' if ok else 'MISS'}")
    print(f"\n  biquad-order control: {'PASS' if allok else 'FAIL -- JOIN IS WRONG, STOP'}\n")
    return allok


# ==========================================================================
#  THE NAMED-COEFFICIENT TABLE + per-multiply annotation
# ==========================================================================
def annotate_image(words, base, cmap, reverb=False):
    """-> list over word indices of (k, host_addr, opcode, role, ev, name) or None.
    opcode is None when the cell carries no host coefficient (unnamed)."""
    ca = cursor_addrs(words)
    ann = [None] * len(words)
    for i, w in enumerate(words):
        if ca[i] is None:
            continue
        haddr = (base + ca[i]) & 0xFF
        if reverb and haddr in REVERB_SLOTS:
            role, name = REVERB_SLOTS[haddr]
            ann[i] = (ca[i], haddr, 0x100, role, "PROVEN", name)   # 0x100 = reverb overlay
            continue
        hit = cmap.get(haddr)
        if hit is None:
            ann[i] = (ca[i], haddr, None, None, None, None)
            continue
        op, oi, cell = hit
        role, ev, _note = OPCODE_ROLE.get(op, ("coeff", "INFERRED", ""))
        if op == 0x70:
            name = "biquad " + BIQUAD_CELLS[cell]
        elif op == 0x76:
            name = "damping filter tap %d" % cell
        else:
            name = "op0x%02X[%d]" % (op, oi)
        ann[i] = (ca[i], haddr, op, role, ev, name)
    return ann


def sec_table(progs, imgs, rom, mrom):
    print("=== NAMED-COEFFICIENT TABLE -- a sample per family\n")
    picks = ['PARAMETRIC EQ', 'CHORUS', 'COMPRESSOR', 'SINGLE DELAY', 'AUTO WAH']
    byname = {}
    for a in imgs:
        nm = P.effect_name(mrom, a) if mrom else str(a)
        byname.setdefault(nm, a)
    # reverb representative
    rev = next((a for a in imgs if any(x in REVERB_ALGOS for x in imgs[a])), None)
    for nm in picks + (['(reverb)'] if rev is not None else []):
        a = rev if nm == '(reverb)' else byname.get(nm)
        if a is None:
            continue
        words = progs[a]
        base = base_of(a)
        rev = base == REVERB_BASE
        cmap = host_coeff_map(rom, a)
        ann = annotate_image(words, base, cmap, rev)
        realname = P.effect_name(mrom, a) if mrom else str(a)
        print(f"  --- algo {a} {realname} (base 0x{base:02X}) ---")
        shown = 0
        for i, x in enumerate(ann):
            if x is None:
                continue
            k, ha, op, role, ev, name = x
            if op is None:
                tag = "(no host coeff -- unnamed)"
            else:
                tag = f"role={role:12} {ev:8} {name}"
            print(f"    w{i:<3} {K.fmt(words[i])}  C-RAM[0x{ha:02X}]  {tag}")
            shown += 1
            if shown >= 16:
                print("    ...")
                break
        print()


def sec_coverage(progs, imgs, rom, mrom):
    print("=== COVERAGE: of the 822 class-A multiplies, how many are NAMED\n")
    total_ca = named = unnamed = 0
    role_ct = collections.Counter()
    ev_ct = collections.Counter()
    per_effect = []
    for a in sorted(imgs):
        words = progs[a]
        base = base_of(a)
        cmap = host_coeff_map(rom, a)
        ann = annotate_image(words, base, cmap, base == REVERB_BASE)
        ca_here = sum(1 for x in ann if x is not None)
        nm_here = 0
        for x in ann:
            if x is None:
                continue
            total_ca += 1
            if x[2] is None:
                unnamed += 1
            else:
                named += 1
                nm_here += 1
                role_ct[x[3]] += 1
                ev_ct[x[4]] += 1
        per_effect.append((a, P.effect_name(mrom, a) if mrom else str(a),
                           ca_here, nm_here))
    print(f"  class-A words in corpus (38 images) : {total_ca}")
    print(f"  NAMED (land on a host +0 coeff addr) : {named}   "
          f"({100.0*named/total_ca:.1f} %)")
    print(f"  unnamed (no host coeff at that cell) : {unnamed}\n")
    print("  named multiplies by ROLE:")
    for r, c in role_ct.most_common():
        print(f"    {r:14} {c}")
    print("\n  by evidence: " + ", ".join(f"{e} {c}" for e, c in ev_ct.most_common()))
    print("\n  per-effect (class-A / named):")
    for a, nm, ch, nh in per_effect:
        if ch:
            print(f"    algo {a:>3} {nm:20} {nh:>3}/{ch:<3}")
    print()
    return named, unnamed, total_ca


# ==========================================================================
#  NEIGHBOUR PROPAGATION -- the P-consumer that follows a role-X multiply
# ==========================================================================
def sec_neighbours(progs, imgs, rom, mrom):
    print("=== NEIGHBOUR PROPAGATION: the word AFTER a named multiply, by role\n")
    print("  A class-2 P-consumer that follows a role-X multiply accumulates/stores")
    print("  role-X's product.  Tally (following-word family) x (predecessor role)")
    print("  across ALL effects: a family that consistently follows ONE role is")
    print("  pinned to that role (present-AND-absence).\n")
    # (hi12,class,lo12) of the following word  ->  Counter(role)
    follow = collections.defaultdict(collections.Counter)
    for a in sorted(imgs):
        words = progs[a]
        base = base_of(a)
        cmap = host_coeff_map(rom, a)
        ann = annotate_image(words, base, cmap, base == REVERB_BASE)
        for i in range(len(words) - 1):
            x = ann[i]
            if x is None or x[3] is None:
                continue
            role = x[3]
            nh, nc, na, nl = K.fl(words[i + 1])
            key = (nh, nc, nl)
            follow[key][role] += 1
    # report families whose successor-role is dominated by one role
    print("  following word (hi12.cl.lo12)  n   dominant role (share)   also")
    rows = []
    for key, ctr in follow.items():
        tot = sum(ctr.values())
        if tot < 8:
            continue
        role, c = ctr.most_common(1)[0]
        rows.append((tot, key, role, c, ctr))
    rows.sort(reverse=True)
    for tot, (nh, nc, nl), role, c, ctr in rows[:22]:
        share = 100.0 * c / tot
        others = ",".join(f"{r}:{n}" for r, n in ctr.most_common()[1:3])
        star = " <== PINNED" if share >= 85 else ""
        print(f"  {nh:03X}.{nc:X}.{nl:03X}  {tot:>3}   {role:14} {share:4.0f}%   {others}{star}")
    print()


# ==========================================================================
#  FREQUENT UNKNOWN WORDS -- what operand ROLE do they carry?
# ==========================================================================
def sec_unknowns(progs, imgs, rom, mrom):
    print("=== FREQUENT UNKNOWN WORDS: operand ROLE of their coefficient\n")
    print("  For each frequent class-A family (hi12.cl.lo12), what ROLE does its")
    print("  named coefficient carry, across effects?  A family whose coefficient")
    print("  is ALWAYS one role gains that operand role (present-AND-absence).\n")
    fam = collections.defaultdict(collections.Counter)   # class-A families
    famtot = collections.Counter()
    for a in sorted(imgs):
        words = progs[a]
        base = base_of(a)
        cmap = host_coeff_map(rom, a)
        ann = annotate_image(words, base, cmap, base == REVERB_BASE)
        for i, x in enumerate(ann):
            if x is None:
                continue
            nh, nc, na, nl = K.fl(words[i])
            key = (nh, nc, nl)
            famtot[key] += 1
            if x[3] is not None:
                fam[key][x[3]] += 1
    print("  class-A family        occ  named  dominant coeff-role (share)")
    rows = sorted(famtot.items(), key=lambda kv: -kv[1])
    for (nh, nc, nl), tot in rows[:24]:
        ctr = fam[(nh, nc, nl)]
        nn = sum(ctr.values())
        if nn == 0:
            print(f"  {nh:03X}.{nc:X}.{nl:03X}   {tot:>3}   {nn:>3}    (never named)")
            continue
        role, c = ctr.most_common(1)[0]
        share = 100.0 * c / nn
        star = " <== ROLE" if share >= 85 and nn >= 6 else ""
        print(f"  {nh:03X}.{nc:X}.{nl:03X}   {tot:>3}   {nn:>3}    {role:14} {share:4.0f}%{star}")
    print()


SECTIONS = {
    'biqctl': sec_biqctl,
    'table': sec_table,
    'coverage': sec_coverage,
    'neighbours': sec_neighbours,
    'unknowns': sec_unknowns,
}


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
    want = rest or ['biqctl', 'table', 'coverage', 'neighbours', 'unknowns']

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
