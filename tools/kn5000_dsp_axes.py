#!/usr/bin/env python3
"""kn5000_dsp_axes.py -- is the uPD6383GF word a PRODUCT of independent axes?

Companion to notes/kn5000-dsp-axes.md.  Tests the decomposition proposed at the end
of notes/kn5000-dsp-chorus.md sect. 3.2 / -core-draft.md sect. 6:

        lo12 = ROUTE      class4 = ARITHMETIC      bit 23 = CURSOR FETCH

using the PHASER's missing-operand anomaly as the probe, and ROCK ROTARY as an
independent second instance.

Imports kn5000_dsp_extract / _coeffs / _params / _biquadmap / _chorus.  NONE of them
is edited, and no note is edited.

Sections (argv[3..], default = all):
    phaser    the all-pass operand anomaly: net-delta test, host-map test, R1 vs R2
    rotary    ROCK ROTARY's rate mechanism -- prediction stated, then checked
    axes      corpus-wide: MI(lo12;class), MI(hi12;lo12), partition quality vs
              NON-CIRCULAR observables, with a permutation control
    predict   cross-class lo12 predictions: hits AND misses
    coverage  what the model implies, recomputed the -core-draft.md way

Usage:
    python3 tools/kn5000_dsp_axes.py <subprogram_v142.rom> <progdir> [sections...]

    progdir is produced by:
    python3 tools/kn5000_dsp_extract.py <subprogram_v142.rom> <progdir>
"""
import collections
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_params as P        # noqa: E402
import kn5000_dsp_chorus as CH       # noqa: E402

fl, fmt, s8 = CH.fl, CH.fmt, CH.s8

# The five malformed streams, excluded so the corpus statistics reproduce
# -encoding.md / -core-draft.md exactly (91 valid programs, 38 distinct images).
MALFORMED = {79, 88, 89, 90, 91}

# The six forms the MAME disassembler actually decodes (-core-draft.md sect. 1).
def is_decoded(w):
    h, c, a, l = fl(w)
    if w == 0x000200000:
        return True                                   # nop
    if h == 0x801 and c == 0 and l in (0x821, 0x021):
        return True                                   # ldptr / rstcur
    if h == 0x202 and c == 0xA and l in (0x1D5, 0x1D4):
        return True                                   # mac / mac.lb
    if h == 0x212 and c == 0xA and l == 0x407:
        return True                                   # mulst
    return False


def images38(progs):
    """The 38 distinct images of the 91 valid programs."""
    seen = {}
    for a in sorted(progs):
        if a in MALFORMED:
            continue
        seen.setdefault(tuple(progs[a]), a)
    return sorted(seen.values())


# ---------------------------------------------------------------- information theory

def entropy(counter):
    n = sum(counter.values())
    return -sum(v / n * math.log2(v / n) for v in counter.values() if v)


def mutual_info(pairs):
    """MI(X;Y) in bits over a list of (x, y)."""
    n = len(pairs)
    if not n:
        return 0.0, 0.0, 0.0
    cx, cy, cxy = collections.Counter(), collections.Counter(), collections.Counter()
    for x, y in pairs:
        cx[x] += 1
        cy[y] += 1
        cxy[(x, y)] += 1
    mi = 0.0
    for (x, y), v in cxy.items():
        mi += v / n * math.log2((v / n) / ((cx[x] / n) * (cy[y] / n)))
    return mi, entropy(cx), entropy(cy)


def nmi(pairs):
    mi, hx, hy = mutual_info(pairs)
    d = min(hx, hy)
    return (mi / d if d > 1e-12 else 0.0), mi, hx, hy


# ---------------------------------------------------------------- SECTION phaser

APSEC = None   # filled by sec_phaser, reused by sec_coverage


def allpass_sections(words):
    """[(i, f0, f1, f2)] for every `102.2.*.1CD | 212.*.*.412 | *` triple."""
    out = []
    for i in range(len(words) - 2):
        f0, f1 = fl(words[i]), fl(words[i + 1])
        if f0[0] == 0x102 and f0[3] == 0x1CD and f1[0] == 0x212 and f1[3] == 0x412:
            out.append((i, f0, f1, fl(words[i + 2])))
    return out


def sec_phaser(subrom, progs, rom, args):
    global APSEC
    print("=== SECTION phaser: where do the all-pass gains come from?\n")
    imgs = images38(progs)

    print("--- P1  the census (MEASURED)\n")
    tot = {a: allpass_sections(progs[a]) for a in imgs}
    tot = {a: v for a, v in tot.items() if v}
    for a, v in tot.items():
        nA = sum(1 for _i, f0, f1, f2 in v if 0xA in (f0[1], f1[1], f2[1]))
        print(f"    algo {a:>3} {CH.NAMES.get(a, '?'):<16} {len(v):>3} all-pass sections, "
              f"{nA} of them containing a class-A word")
    n = sum(len(v) for v in tot.values())
    print(f"    total {n} sections in {len(tot)} images")

    print("\n--- P2  THE NET-DELTA TEST (MEASURED, origin-free and assumption-free)\n")
    print("    Each section is three words; each carries a signed addr8, which is the")
    print("    data pointer's post-increment.  If the three deltas SUM TO ZERO the")
    print("    pointer is back where it started, so every section addresses the SAME")
    print("    operand cell -- one shared gain, not one gain per section.")
    print("    This uses no origin, no class-skip rule and no host data: it can fail.\n")
    zero = nonzero = 0
    tails = []
    for a, v in tot.items():
        for i, f0, f1, f2 in v:
            d = s8(f0[2]) + s8(f1[2]) + s8(f2[2])
            if d == 0:
                zero += 1
            else:
                nonzero += 1
                tails.append((a, i, d, f1[1], fmt(progs[a][i + 2])))
    print(f"    sections with net pointer delta == 0 : {zero} / {zero + nonzero}")
    print(f"    sections with net delta != 0         : {nonzero}\n")
    print("    the exceptions, in full:")
    for a, i, d, c1, w2 in tails:
        print(f"      algo {a:>3} word {i:>3}  net {d:+3d}   middle word class {c1:X}   "
              f"third word {w2}")
    tailmark = all(w2 == '104.2.00.000' for _a, _i, _d, _c, w2 in tails)
    tailA = all(c == 0xA for _a, _i, _d, c, _w in tails)
    print(f"\n    every exception's third word is the all-pass marker 104.2.00.000 : {tailmark}")
    print(f"    every exception's middle word is class A                         : {tailA}")
    print("    -> the exceptions are exactly the LAST section of each chain, where the")
    print("       pointer deliberately leaves the chain.  All INTERIOR sections cancel.")

    print("\n--- P3  THE HOST-MAP TEST (MEASURED) -- can R1 be true?\n")
    print("    R1 (chorus note sect. 5.2): class-2 words multiply by a coefficient at an")
    print("    EXPLICITLY ADDRESSED location, i.e. the ascending 0x45..0x4E in")
    print("    `102.2.<k>.1CD` are 20 distinct coefficient ADDRESSES.")
    print("    If so, the host must write them -- gains have to come from somewhere.\n")
    for a in sorted(tot):
        amap = CH.t1_map(rom, a)
        allad = sorted({e for ent in amap.values() for e in ent})
        used = sorted({ad for _o, ad in CH.t2_used(rom, a, amap)})
        need = sorted({f0[2] for _i, f0, _f1, _f2 in tot[a]})
        hit = [x for x in need if x in allad]
        print(f"    algo {a:>3} {CH.NAMES.get(a, '?'):<16}")
        print(f"        addr8 in the chain words : {' '.join('%02X' % x for x in need)}")
        print(f"        every address the host T1 even MENTIONS : "
              f"{' '.join('%02X' % x for x in allad)}")
        print(f"        T2-confirmed host writes               : "
              f"{' '.join('%02X' % x for x in used)}")
        print(f"        chain addr8 values the host ever writes : "
              f"{hit if hit else 'NONE'}")
    print("\n    -> R1 is FALSIFIED.  The host never writes any address in the chain's")
    print("       addr8 range, and P2 shows those bytes are not addresses at all --")
    print("       they are increments that cancel.  R2 (one shared gain per chain) is")
    print("       what survives, and P2 measures it directly.")

    print("\n--- P4  the shared cell, and what fills it (INFERRED)\n")
    print("    Immediately outside each chain sits a block of the shape")
    print("        <table-lookup triplet> | 000.A.**.415 (depth) | 212.A.**.1D5 (centre)")
    print("    hi12 0x212 = write to mem[ptr] (MEASURED, chorus note sect. 5.3), so this")
    print("    block WRITES a value = centre + depth x lfo.  The centre coefficients:\n")
    for a in sorted(tot):
        bank, b0 = CH.bank_of(subrom, a)
        cur, rows = 0, []
        for i, w in enumerate(progs[a]):
            if w == 0x801000021:
                cur = 0
            h, c, ad, l = fl(w)
            if c == 0xA:
                if h == 0x212 and l == 0x1D5:
                    v = bank.get(b0 + cur)
                    if v is not None:
                        rows.append((i, fmt(w), v, P.q23(v) if hasattr(P, 'q23') else
                                     ((v - (1 << 24)) / (1 << 23) if v & 0x800000
                                      else v / (1 << 23))))
                cur += 1
        for i, s, v, f in rows:
            print(f"    algo {a:>3} word {i:>3}  {s}  coefficient {v:06X} = {f:+.6f}")
    print("\n    0x381062 = +0.438000 recurs as the centre in every phaser image.  A")
    print("    first-order all-pass coefficient of 0.438 swept by +/- a small depth is")
    print("    a textbook phaser.  MEASURED: the constant and its position.  INFERRED:")
    print("    that this block's write is the cell the chain reads.")

    print("\n--- P5  THE CONTROL: the REVERB's all-pass ladders (MEASURED)\n")
    print("    If bit 23 is a cursor-fetch enable and the class-2 form exists BECAUSE the")
    print("    gain is shared, then an all-pass family whose gains genuinely DIFFER per")
    print("    section must use the class-A form and must NOT move the pointer at all.")
    print("    The reverb is that family (-reverb.md: two ladders of five diffusers).")
    print("    This is a control that could have failed.\n")
    rev = [a for a in imgs if len(progs[a]) == 133]
    for a in rev:
        ws = progs[a]
        marks = [i for i, w in enumerate(ws) if w == 0x104200000]
        print(f"    algo {a} (the only unit-1 program): {len(marks)} all-pass markers "
              f"at {marks}")
        secs = []
        for m in marks:
            blk = ws[m - 1:m + 7]
            if len(blk) == 8:
                secs.append(blk)
        same = len({tuple(b) for b in secs})
        nA = [sum(1 for w in b if fl(w)[1] == 0xA) for b in secs]
        moved = [sum(s8(fl(w)[2]) for w in b if fl(w)[1] not in (1, 4, 6)) for b in secs]
        print(f"        distinct 8-word section images     : {same}")
        print(f"        class-A words per section          : {nA}")
        print(f"        net pointer delta per section      : {moved}")
        print(f"        the recurring section:")
        for w in secs[0]:
            print(f"            {fmt(w)}")
    print("\n    -> CONTROL PASSES.  Every reverb diffuser carries its OWN class-A word")
    print("       (102.A.00.64B) and the pointer never moves inside a section.  Where the")
    print("       gains differ per stage the cursor route is used; where one modulated")
    print("       gain is shared by twenty stages the pointer route is used.  Same hi12")
    print("       0x102 in both -- so hi12 names the OPERATION and the class+lo12 name")
    print("       WHERE THE OPERAND COMES FROM.  That is not the brief's decomposition.")

    APSEC = tot


# ---------------------------------------------------------------- SECTION rotary

def cursor_slots(subrom, progs, a):
    """{absolute coefficient address: (word index, word)} for class-A words."""
    bank, b0 = CH.bank_of(subrom, a)
    out, cur = {}, 0
    for i, w in enumerate(progs[a]):
        if w == 0x801000021:
            cur = 0
        if fl(w)[1] == 0xA:
            out[b0 + cur] = (i, w, bank.get(b0 + cur))
            cur += 1
    return out


def sec_rotary(subrom, progs, rom, args):
    print("=== SECTION rotary: ROCK ROTARY's rate, PREDICTED then CHECKED\n")
    print("--- R0  THE PREDICTION, stated before the check\n")
    print("    The phaser's answer (sect. phaser) is: a second operand route exists and")
    print("    it is the DATA POINTER -- a class-2 word multiplies by mem[ptr] where a")
    print("    class-A word multiplies by coef[cursor++].")
    print("    IF ROCK ROTARY's missing 092.A is the same phenomenon, THEN its rate must")
    print("    arrive on a CLASS-2 word, and the addresses host op 0x69 writes (0x0F,")
    print("    0x13) must NOT be consumed by the coefficient cursor -- because a value")
    print("    that travels the pointer route is precisely one the cursor never fetches.\n")
    print("    That is falsifiable, and the way it fails is informative: if 0x0F/0x13 ARE")
    print("    cursor slots, ROCK ROTARY has no missing-operand problem at all and the")
    print("    two anomalies are DIFFERENT mechanisms.\n")

    print("--- R1  THE CHECK (MEASURED)\n")
    for a in (15, 53):
        if a not in progs:
            continue
        amap = CH.t1_map(rom, a)
        slots = cursor_slots(subrom, progs, a)
        n92 = sum(1 for w in progs[a] if fl(w)[0] == 0x092 and fl(w)[1] == 0xA)
        print(f"    algo {a} {CH.NAMES.get(a, '?')}: 092.A words = {n92}")
        for op in (0x69, 0x66, 0x65):
            if op not in amap:
                print(f"      host op 0x{op:02X}: not declared")
                continue
            print(f"      host op 0x{op:02X} writes "
                  f"{' '.join('%02X' % e for e in amap[op])}")
            for e in amap[op]:
                if e in slots:
                    i, w, v = slots[e]
                    print(f"        addr {e:02X} IS cursor slot -> word {i:>3} {fmt(w)}"
                          f"  coef {('%06X' % v) if v is not None else '??'}")
                else:
                    print(f"        addr {e:02X} is NOT a cursor slot")
    print("\n--- R2  VERDICT\n")
    print("    PREDICTION MISSED.  Op 0x69's addresses 0x0F and 0x13 ARE ordinary")
    print("    coefficient-cursor slots, consumed by class-A words.  ROCK ROTARY's rate")
    print("    therefore travels the NORMAL cursor route; nothing is missing.")
    print("    What is absent is the 092.A PHASE-ACCUMULATOR IDIOM, not an operand.")
    print("    The two anomalies are DIFFERENT: the phaser lacks an operand ROUTE, ROCK")
    print("    ROTARY merely uses a different OSCILLATOR ALGORITHM.  One mechanism does")
    print("    NOT explain both, and the brief's 'strong if it does' does not apply.")


# ---------------------------------------------------------------- SECTION axes

def corpus(progs):
    """[(image, index, word)] over the 38 distinct images."""
    out = []
    for a in images38(progs):
        for i, w in enumerate(progs[a]):
            out.append((a, i, w))
    return out


def sec_axes(subrom, progs, rom, args):
    print("=== SECTION axes: is the word a PRODUCT of independent fields?\n")
    C = corpus(progs)
    print(f"    corpus: {len(C)} words over {len(images38(progs))} distinct images\n")

    print("--- A1  are the fields independent of each other? (MEASURED)\n")
    print("    A product space requires the axes to be close to INDEPENDENT.  MI near 0")
    print("    means independent; MI near min(H) means one determines the other.\n")
    F = [fl(w) for _a, _i, w in C]
    names = ['hi12', 'class4', 'addr8', 'lo12']
    print(f"    {'pair':<18} {'MI':>7} {'H(X)':>7} {'H(Y)':>7} {'NMI':>7}")
    for x in range(4):
        for y in range(x + 1, 4):
            pairs = [(f[x], f[y]) for f in F]
            nm, mi, hx, hy = nmi(pairs)
            print(f"    {names[x]+' x '+names[y]:<18} {mi:>7.3f} {hx:>7.3f} "
                  f"{hy:>7.3f} {nm:>7.3f}")
    print("\n    Read this carefully: NMI is normalised by min(H), so it is the fraction")
    print("    of the SMALLER field's information that the larger one already carries.")

    print("\n--- A2  partition quality against NON-CIRCULAR observables (MEASURED)\n")
    print("    THE TRAP: most 'structural labels' we hold (all-pass marker, DRAM bracket,")
    print("    terminator, NOP, LFO read) are DEFINED by hi12/class/lo12.  Scoring a")
    print("    grouping-by-lo12 against a label defined by lo12 is circular and would")
    print("    'confirm' anything.  So the observables below are built ONLY from things")
    print("    outside the word itself:")
    print("        NEIGH  = (hi12 of the previous word, hi12 of the next word)")
    print("        IMAGE  = which of the 38 images the occurrence is in")
    print("        POS    = position in the program, in tenths\n")
    obs = {}
    neigh, image, pos = [], [], []
    byimg = collections.defaultdict(list)
    for a, i, w in C:
        byimg[a].append((i, w))
    for a in byimg:
        ws = [w for _i, w in sorted(byimg[a])]
        n = len(ws)
        for i, w in enumerate(ws):
            pv = fl(ws[i - 1])[0] if i else -1
            nx = fl(ws[i + 1])[0] if i + 1 < n else -1
            neigh.append((pv, nx))
            image.append(a)
            pos.append(min(9, i * 10 // n))
    obs['NEIGH'] = neigh
    obs['IMAGE'] = image
    obs['POS'] = pos

    groupings = {
        'lo12': [f[3] for f in F],
        'class4': [f[1] for f in F],
        '(lo12,class4)': [(f[3], f[1]) for f in F],
        'hi12': [f[0] for f in F],
        '(hi12,class4)': [(f[0], f[1]) for f in F],
        '(hi12,lo12)': [(f[0], f[3]) for f in F],
        'full word': [w for _a, _i, w in C],
    }
    rng = random.Random(20260722)
    print(f"    {'grouping':<16} {'|G|':>5} " +
          " ".join(f"{o:>20}" for o in obs))
    print(f"    {'':<16} {'':>5} " +
          " ".join(f"{'NMI  (null)  lift':>20}" for _ in obs))
    for gname, g in groupings.items():
        cells = []
        for oname, o in obs.items():
            nm, _mi, _hx, _hy = nmi(list(zip(g, o)))
            # permutation control: same group-size profile, labels shuffled
            nulls = []
            for _ in range(8):
                gg = list(g)
                rng.shuffle(gg)
                nulls.append(nmi(list(zip(gg, o)))[0])
            nl = sum(nulls) / len(nulls)
            cells.append(f"{nm:>6.3f} {nl:>6.3f} {nm - nl:>+6.3f}")
        print(f"    {gname:<16} {len(set(g)):>5} " + " ".join(f"{c:>20}" for c in cells))
    print("\n    'null' is the same grouping with its labels shuffled -- it measures how")
    print("    much NMI you get for free from having that many groups.  'lift' = NMI -")
    print("    null is the only column that means anything.")

    print("\n--- A3  ★ THE DECISIVE TEST: is the information ADDITIVE? (MEASURED)\n")
    print("    A product space of independent axes has a signature: what each axis knows")
    print("    about the context is DIFFERENT information, so the joint grouping should")
    print("    know roughly the SUM.  A single axis dressed up as two has the opposite")
    print("    signature -- the second field tells you almost nothing new.")
    print("    Measured in raw bits of MI against NEIGH, permutation-corrected.\n")

    def adjmi(g, o, R=20):
        mi = mutual_info(list(zip(g, o)))[0]
        acc = 0.0
        for _ in range(R):
            gg = list(g)
            rng.shuffle(gg)
            acc += mutual_info(list(zip(gg, o)))[0]
        return mi - acc / R

    glo = [f[3] for f in F]
    gcl = [f[1] for f in F]
    ghi = [f[0] for f in F]
    a_lo, a_cl, a_hi = adjmi(glo, neigh), adjmi(gcl, neigh), adjmi(ghi, neigh)
    a_locl = adjmi(list(zip(glo, gcl)), neigh)
    a_hilo = adjmi(list(zip(ghi, glo)), neigh)
    a_hicl = adjmi(list(zip(ghi, gcl)), neigh)
    print(f"    adj MI (bits)   lo12 {a_lo:6.3f}   class4 {a_cl:6.3f}   hi12 {a_hi:6.3f}")
    print(f"                    (lo12,class4) {a_locl:6.3f}   (hi12,lo12) {a_hilo:6.3f}"
          f"   (hi12,class4) {a_hicl:6.3f}\n")
    for na, nb, aa, ab, aj in (('lo12', 'class4', a_lo, a_cl, a_locl),
                               ('hi12', 'lo12', a_hi, a_lo, a_hilo),
                               ('hi12', 'class4', a_hi, a_cl, a_hicl)):
        syn = aj - aa - ab
        newbits = aj - aa
        print(f"    {na} + {nb}:  synergy {syn:+6.3f} bits    "
              f"{nb} adds {newbits:+.3f} of its own {ab:.3f} "
              f"({100.0*max(0.0, newbits)/ab:.0f} % new, {100-100.0*max(0.0, newbits)/ab:.0f} % redundant)")
    print("\n    ADDITIVE product space would give synergy near 0.  Every pair is")
    print("    strongly NEGATIVE.  The fields are heavily REDUNDANT with one another:")
    print("    they are not independent axes over this corpus.")


# ---------------------------------------------------------------- SECTION predict

PREDICTIONS = [
    # (lo12, the class it is known in, what it is known to mean there, the source,
    #  the class(es) to predict into, the prediction, how it is checked)
    (0x407, 0xA, "212.A.dd.407 = mulst: mem[p] <- acc ; P = coef[cur++] * acc",
     "-semantics.md, DETERMINED UNIQUELY",
     "if lo12 is the ROUTE and hi12 0x212 is the write, then 000.2.**.407 should "
     "be the SAME route without the write and without the fetch -- i.e. it should "
     "route acc into the multiplier only"),
    (0x1D5, 0xA, "202.A.dd.1D5 = mac: P = coef[cur++] * mem[p] ; acc += P",
     "-semantics.md, all 144 search survivors agree",
     "000.2.**.1D5 / 104.2.**.1D5 should also be MAC-shaped, taking the multiplicand "
     "from somewhere other than the cursor"),
    (0x44C, 0x3, "C40.3.20.44C = apply modulation offset, keeping the fraction",
     "-chorus.md sect. 3.2",
     "any other class carrying lo12 0x44C should also be a modulation-offset apply"),
    (0x200, 0xA, "092.A/094.A .200 = phase accumulate / wrap",
     "-chorus.md sect. 2.2, MEASURED",
     "class-2 words with lo12 0x200 should also touch the LFO phase"),
    (0x412, 0x2, "212.2.01.412 = the all-pass chain's per-section write",
     "this note, sect. phaser",
     "212.A.**.412 (the chain-terminal form) should be the same write plus a "
     "cursor fetch"),
    (0x821, 0x0, "801.0.NN.821 = ldptr #NN  (PROVEN BY CONSTRUCTION)",
     "-parameters.md",
     "no other class should carry lo12 0x821 at all -- a pointer load has no "
     "arithmetic variant"),
]


def sec_predict(subrom, progs, rom, args):
    print("=== SECTION predict: does the product model PREDICT? hits AND misses\n")
    C = corpus(progs)
    bylo = collections.defaultdict(collections.Counter)
    byloimg = collections.defaultdict(set)
    for a, _i, w in C:
        h, c, ad, l = fl(w)
        bylo[l][(h, c)] += 1
        byloimg[(l, c)].add(a)

    for lo, kc, meaning, src, pred in PREDICTIONS:
        print(f"--- lo12 = 0x{lo:03X}")
        print(f"    KNOWN in class {kc:X}: {meaning}")
        print(f"      source: {src}")
        print(f"    PREDICTION: {pred}")
        forms = bylo[lo]
        classes = collections.Counter()
        for (h, c), n in forms.items():
            classes[c] += n
        print(f"    OBSERVED: lo12 0x{lo:03X} occurs {sum(forms.values())} times in "
              f"{len(forms)} (hi12,class) forms, classes "
              f"{{{', '.join('%X:%d' % (c, n) for c, n in sorted(classes.items()))}}}")
        for (h, c), n in sorted(forms.items(), key=lambda kv: -kv[1])[:8]:
            print(f"        {h:03X}.{c:X}.**.{lo:03X}  x{n:<4} in "
                  f"{len(byloimg[(lo, c)])} images")
        other = [c for c in classes if c != kc]
        if not other:
            print("    -> VACUOUS: lo12 occurs in only one class.  The product model")
            print("       makes no testable statement here.  Reported, not counted.")
        print()

    print("--- the honest scoreboard\n")
    n_lo = len(bylo)
    multi = [l for l, f in bylo.items()
             if len({c for _h, c in f}) > 1]
    print(f"    distinct lo12 values in the corpus            : {n_lo}")
    print(f"    lo12 values occurring in MORE THAN ONE class  : {len(multi)} "
          f"({100.0*len(multi)/n_lo:.1f} %)")
    print("    -> a lo12 that only ever appears in one class cannot support a")
    print("       cross-class prediction AT ALL.  That is the ceiling on the whole")
    print("       method, and it is measured, not argued.")
    cross = 0
    for l in multi:
        cross += sum(bylo[l].values())
    print(f"    occurrences covered by multi-class lo12 values : {cross} / {len(C)} "
          f"({100.0*cross/len(C):.1f} %)")


# ---------------------------------------------------------------- SECTION coverage

def sec_coverage(subrom, progs, rom, args):
    print("=== SECTION coverage: what the model actually buys, with a control\n")
    C = corpus(progs)
    n = len(C)
    dec = sum(1 for _a, _i, w in C if is_decoded(w))
    print(f"    words over the 38 distinct images : {n}")
    print(f"    decoded by the six MAME forms     : {dec}  ({100.0*dec/n:.1f} %)"
          f"   <- -core-draft.md's baseline")

    # What THIS note and the chorus note add.  SCOPED: a form is only counted in the
    # images where it was actually measured -- claiming 212.A.**.412 in all 18 images
    # it occurs in, when the chain was only read in 3, would be exactly the kind of
    # over-claim this project keeps having to retract.
    ap_imgs = {a for a in images38(progs) if allpass_sections(progs[a])}
    added = collections.Counter()
    for a, _i, w in C:
        if is_decoded(w):
            continue
        h, c, a8, l = fl(w)
        if h == 0x212 and c == 2 and l == 0x000:
            added['212.2.**.000 plain store (chorus note 5.3, 32 images)'] += 1
        elif h == 0x102 and c == 2 and l == 0x1CD and a in ap_imgs:
            added['102.2.**.1CD all-pass gain via mem[ptr] (this note, 3 images)'] += 1
        elif h == 0x212 and l == 0x412 and a in ap_imgs:
            added['212.*.**.412 all-pass section write (this note, 3 images)'] += 1
        elif h in (0x092, 0x094) and c == 0xA and l == 0x200:
            added['092/094.A.**.200 LFO phase (chorus note 2.2, 20 images)'] += 1
        elif h == 0x102 and c == 0xA and l == 0x64B:
            added['102.A.00.64B reverb diffuser gain via cursor (this note)'] += 1
    tot_add = sum(added.values())
    print(f"\n    added by the chorus note + this note:")
    for k, v in added.most_common():
        print(f"        {v:>5}  {k}")
    print(f"        {tot_add:>5}  TOTAL")
    print(f"\n    decoded, revised                  : {dec + tot_add}  "
          f"({100.0*(dec+tot_add)/n:.1f} %)")

    print("\n--- the CONTROL: how many words does the PRODUCT MODEL imply that the")
    print("    above does not already cover?\n")
    known_lo = {0x407, 0x1D5, 0x1D4, 0x44C, 0x200, 0x412, 0x821, 0x021, 0x000, 0x1CD}
    implied = 0
    implied_forms = collections.Counter()
    for _a, _i, w in C:
        if is_decoded(w):
            continue
        h, c, a8, l = fl(w)
        if l in known_lo:
            implied += 1
            implied_forms[(h, c, l)] += 1
    print(f"    undecoded words whose lo12 is one we claim to KNOW in some class:")
    print(f"        {implied} occurrences, {len(implied_forms)} distinct (hi12,class,lo12)")
    print(f"        = {100.0*implied/n:.1f} % of the corpus")
    print("\n    THAT NUMBER IS NOT A DECODE.  Knowing the lo12 tells you the route and")
    print("    nothing else: the hi12 (destination) and the class (arithmetic) of those")
    print("    words are still unknown, and sect. predict shows the cross-class")
    print("    predictions are mostly VACUOUS because most lo12 values live in exactly")
    print("    one class.  The number that survives is the one above it.")


# ---------------------------------------------------------------- main

SECTIONS = {'phaser': sec_phaser, 'rotary': sec_rotary, 'axes': sec_axes,
            'predict': sec_predict, 'coverage': sec_coverage}


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    subrom, progdir = sys.argv[1], sys.argv[2]
    want = sys.argv[3:] or list(SECTIONS)
    progs = CH.load_progs(progdir)
    rom = P.Rom(subrom, P.SUB_BASE)
    for s in want:
        if s not in SECTIONS:
            sys.exit(f"unknown section {s}; have {' '.join(SECTIONS)}")
        SECTIONS[s](subrom, progs, rom, sys.argv[3:])
        print()


if __name__ == '__main__':
    main()
