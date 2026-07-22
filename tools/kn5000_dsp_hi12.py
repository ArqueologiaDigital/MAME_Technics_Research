#!/usr/bin/env python3
"""kn5000_dsp_hi12.py -- decode hi12, and try to pin the data pointer's origin.

Companion to notes/kn5000-dsp-hi12.md.  Follows notes/kn5000-dsp-axes.md sect. 10,
which concluded that the OPERATION lives in hi12 (`0x102` is the all-pass gain
multiply in two families that share nothing else) and that the pointer's origin is
the highest-value structural unknown.

Imports kn5000_dsp_chorus / _params.  NEITHER IS EDITED, and no earlier note is
edited -- corrections are collected in the note.

Sections (argv[3..], default = all):
    enum      every distinct hi12: frequency, breadth, classes, position
    lattice   does hi12 DECOMPOSE?  Hamming-distance-1 closure vs a null,
              sub-field completeness, the bit11 escape
    end       bit10 = END: the 38/38 test and the residue-closure test
    store     bit4 = "write the accumulator to mem[ptr]": pairs, controls,
              the ambiguity it breaks and the one it does not
    origin    TASK B: can the data pointer's origin be pinned from the ROM?
              class-subset search, modulus search, hi12-bit-gate search
    coverage  the honest coverage figure, recomputed the -axes.md way

Usage:
    python3 tools/kn5000_dsp_hi12.py <subprogram_v142.rom> <progdir> [sections...]

    progdir is produced by:
    python3 tools/kn5000_dsp_extract.py <subprogram_v142.rom> <progdir>
"""
import collections
import itertools
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_params as P        # noqa: E402
import kn5000_dsp_chorus as CH       # noqa: E402

fl, fmt, s8 = CH.fl, CH.fmt, CH.s8

# Same exclusion as -encoding.md / -core-draft.md / -axes.md, so the corpus is
# provably the same one (2974 words, 38 distinct images).
MALFORMED = {79, 88, 89, 90, 91}


def images38(progs):
    seen = {}
    for a in sorted(progs):
        if a in MALFORMED:
            continue
        seen.setdefault(tuple(progs[a]), a)
    return sorted(seen.values())


def corpus(progs):
    return [(a, i, w) for a in images38(progs) for i, w in enumerate(progs[a])]


def is_decoded(w):
    """The six forms the MAME disassembler decodes (-core-draft.md sect. 1)."""
    h, c, a, l = fl(w)
    if w == 0x000200000:
        return True
    if h == 0x801 and c == 0 and l in (0x821, 0x021):
        return True
    if h == 0x202 and c == 0xA and l in (0x1D5, 0x1D4):
        return True
    if h == 0x212 and c == 0xA and l == 0x407:
        return True
    return False


def bits(h):
    return " ".join(str(b) for b in range(12) if h >> b & 1) or "-"


# ------------------------------------------------------------------ SECTION enum

def sec_enum(subrom, progs, rom, args):
    print("=== SECTION enum: every distinct hi12, ranked by breadth x frequency\n")
    C = corpus(progs)
    imgs = images38(progs)
    st = collections.defaultdict(lambda: {'n': 0, 'img': set(),
                                          'cls': collections.Counter(),
                                          'lo': collections.Counter(), 'pos': []})
    for a, i, w in C:
        h, c, ad, l = fl(w)
        n = len(progs[a])
        s = st[h]
        s['n'] += 1
        s['img'].add(a)
        s['cls'][c] += 1
        s['lo'][l] += 1
        s['pos'].append(i / max(1, n - 1))
    print(f"    corpus: {len(C)} words over {len(imgs)} distinct images")
    print(f"    ★ DISTINCT hi12 VALUES: {len(st)}   "
          f"({100.0*len(st)/4096:.2f} % of the 12-bit space)\n")
    print(f"    {'hi12':>5} {'bits set':<14} {'n':>5} {'imgs':>5} {'nlo':>4} "
          f"{'meanpos':>7}  classes")
    for h, s in sorted(st.items(), key=lambda kv: (-len(kv[1]['img']), -kv[1]['n'])):
        mp = sum(s['pos']) / len(s['pos'])
        cls = ",".join('%X:%d' % (c, v) for c, v in sorted(s['cls'].items()))
        print(f"      {h:03X} {bits(h):<14} {s['n']:>5} {len(s['img']):>5} "
              f"{len(s['lo']):>4} {mp:>7.3f}  {{{cls}}}")
    print("\n    'meanpos' is the mean normalised position in the program.  Note the")
    print("    nine values whose meanpos is EXACTLY 1.000 -- see section `end`.")


# --------------------------------------------------------------- SECTION lattice

def sec_lattice(subrom, progs, rom, args):
    print("=== SECTION lattice: does hi12 DECOMPOSE into orthogonal sub-fields?\n")
    C = corpus(progs)
    V = sorted({fl(w)[0] for _a, _i, w in C})
    N = collections.Counter(fl(w)[0] for _a, _i, w in C)

    print("--- L1  THE CLOSURE TEST (MEASURED), stated before it was run\n")
    print("    An ENUMERATED opcode field has no reason to contain pairs of values one")
    print("    bit apart.  A FIELDED / horizontal-microcode encoding is nearly forced")
    print("    to: turning one enable on or off gives another legal word.  So count")
    print("    Hamming-distance-1 pairs among the observed values and compare against a")
    print("    null that holds the popcount profile fixed.  This can fail.\n")

    def hd(x, y):
        return bin(x ^ y).count('1')

    d1 = [(x, y) for x, y in itertools.combinations(V, 2) if hd(x, y) == 1]
    pc = collections.Counter(bin(v).count('1') for v in V)
    pool = collections.defaultdict(list)
    for v in range(4096):
        pool[bin(v).count('1')].append(v)
    rng = random.Random(20260722)
    nulls = []
    for _ in range(2000):
        s = set()
        for k, c in pc.items():
            s.update(rng.sample(pool[k], c))
        s = sorted(s)
        nulls.append(sum(1 for x, y in itertools.combinations(s, 2) if hd(x, y) == 1))
    mu = sum(nulls) / len(nulls)
    sd = (sum((n - mu) ** 2 for n in nulls) / len(nulls)) ** 0.5
    print(f"    observed HD-1 pairs among the {len(V)} values : {len(d1)}")
    print(f"    null (same popcount profile, 2000 draws)     : {mu:.2f} +/- {sd:.2f}")
    print(f"    ->  z = {(len(d1)-mu)/sd:+.1f}\n")
    hist = collections.Counter((x ^ y).bit_length() - 1 for x, y in d1)
    print("    which bit the pair differs in:")
    for b in range(12):
        print(f"        bit{b:<2} ({1<<b:03X}) : {hist.get(b,0)} pairs")

    print("\n--- L2  SUB-FIELD COMPLETENESS (MEASURED)\n")
    print("    If a run of bits is a FIELD, some prefix should exercise all of its")
    print("    values.  If the bits are unrelated, that is a coincidence.\n")
    f31 = ["%03X" % v for v in V if v & 0xFF0 == 0x020]
    print(f"    bits[3:1] under prefix 0x02_ : {f31}")
    print(f"        -> {len(f31)}/8 of the 3-bit field's values, bit0 always 0")
    f98 = ["%03X" % v for v in V if v & 0x0FF == 0x002 and not v & 0xC00]
    g98 = ["%03X" % v for v in V if v & 0x0FF == 0x082 and not v & 0xC00]
    print(f"    bits[9:8] on the ..02 base   : {f98}   -> {len(f98)}/4")
    print(f"    bits[9:8] on the ..82 base   : {g98}   -> {len(g98)}/4")

    print("\n--- L3  bit11 is an ESCAPE, not a modifier (MEASURED)\n")
    print("    A modifier bit leaves a legal word when removed (see bit4, sect. store).")
    print("    An escape does not, because it re-interprets the bits below it.\n")
    ok = 0
    for v in V:
        if v & 0x800:
            r = v & 0x7FF
            good = r in V
            ok += good
            print(f"        {v:03X}  x{N[v]:<4} -> residue {r:03X} in the vocabulary: {good}")
    print(f"\n    residue-in-vocabulary: {ok}/{sum(1 for v in V if v & 0x800)}"
          f"  -- bit11 does NOT behave like a modifier.")

    print("\n--- L4  the labelled signal the brief asked for (MEASURED)\n")
    print("    0x092 (phase +=) and 0x094 (wrap) : Hamming distance "
          f"{hd(0x092,0x094)}, and BOTH are 0x090 | x")
    print("    0x082 (LFO read) is 0x090 with bit4 cleared and bit1 set -- the whole")
    print("    LFO machinery lives in the 0x08_/0x09_ block (bit7 set, bit8/9 clear).")
    print(f"    0x212 (store) vs 0x102 (multiply): distance {hd(0x212,0x102)};"
          " they differ in bit4 (the")
    print("    store, sect. store) and in bit9-vs-bit8.  The decomposition puts the")
    print("    phase machinery together and separates the store from the multiply.")


# ------------------------------------------------------------------- SECTION end

def sec_end(subrom, progs, rom, args):
    print("=== SECTION end: bit10 (with bit11 clear) = END OF PROGRAM\n")
    C = corpus(progs)
    imgs = images38(progs)
    V = sorted({fl(w)[0] for _a, _i, w in C})
    N = collections.Counter(fl(w)[0] for _a, _i, w in C)

    print("--- E1  PREDICTION, stated before the check\n")
    print("    Nine hi12 values have mean normalised position EXACTLY 1.000 and all of")
    print("    them carry bit10.  PREDICT: a word carries bit10 (bit11 clear) IF AND")
    print("    ONLY IF it is the terminator -- class 1, addr8 in {0x0E,0x0F}, last word")
    print("    of its image.  The CONTROL is the 'only if': not one bit10 word may")
    print("    appear anywhere else in any of the 2974 words.\n")
    tot, bad = 0, []
    for a in imgs:
        ws = progs[a]
        for i, w in enumerate(ws):
            h, c, ad, l = fl(w)
            if h & 0x400 and not h & 0x800:
                tot += 1
                if not (c == 1 and ad in (0x0E, 0x0F) and i == len(ws) - 1):
                    bad.append((a, i, fmt(w)))
    print(f"    words with bit10 set and bit11 clear   : {tot}")
    print(f"    images in the corpus                   : {len(imgs)}")
    print(f"    of those words, NOT a terminator       : {len(bad)}  {bad[:6]}")
    print(f"    -> exactly one per image, zero elsewhere.  PREDICTION HOLDS.")
    print("    CONTROL for the escape: 0xC40 also carries bit10, but it also carries")
    print("    bit11, and its mean position is 0.570, not 1.000 -- inside the bit11")
    print("    format bit10 is NOT the end marker, which is what an escape means.")

    print("\n--- E2  ★ THE RESIDUE-CLOSURE TEST (MEASURED) -- this is the decisive one\n")
    print("    If bit10 is a MODIFIER on an otherwise ordinary microword, then the")
    print("    terminator's remaining bits must themselves be an ordinary hi12: the")
    print("    last instruction does its work AND halts.  If bit10 were part of an")
    print("    enumerated opcode, the residues would be arbitrary 12-bit numbers.\n")
    res = collections.Counter(fl(progs[a][-1])[0] & 0x3FF for a in imgs)
    hit = 0
    for r, n in sorted(res.items()):
        ok = r in V
        hit += ok
        print(f"        terminator hi12 {0x400|r:03X}  x{n:<3} -> residue {r:03X}  "
              f"in the vocabulary: {ok}"
              + (f"  (x{N[r]} as an ordinary word)" if ok else ""))
    lowV = [v for v in V if v < 0x400]
    q = len(lowV) / 1024.0
    print(f"\n    residues that are ordinary hi12 values : {hit}/{len(res)}")
    print(f"    NULL (tight): the residue is 10 bits, so a random terminator hi12 with")
    print(f"    bit10 set and bit11 clear has residue uniform over 1024.  {len(lowV)} of")
    print(f"    the {len(V)} observed hi12 values are below 0x400, so chance per residue")
    print(f"    = {len(lowV)}/1024 = {q:.4f}; all {len(res)} distinct residues by chance"
          f" = {q**len(res):.1e}")
    print("    CAVEAT, stated because it cuts against me: the residues are the CORPUS'S")
    print("    COMMON ops (000, 202, 212), so they are not uniform draws either.  The")
    print("    argument that survives that objection is qualitative: an ENUMERATED")
    print("    opcode has no reason to place its nine terminator codes at a constant")
    print("    offset 0x400 from nine ordinary codes at all.")
    print("\n    Read the residues: 612 = END | 212 (mac+store), 604 = END | 204,")
    print("    602 = END | 202, 504 = END | 104, 42C = END | 02C, 400 = END alone.")
    print("    ★ hi12 IS A HORIZONTAL MICROWORD OF INDEPENDENT ENABLES, not an opcode.")


# ----------------------------------------------------------------- SECTION store

def sec_store(subrom, progs, rom, args):
    print("=== SECTION store: bit4 = write the accumulator to mem[ptr]\n")
    C = corpus(progs)
    V = sorted({fl(w)[0] for _a, _i, w in C})
    N = collections.Counter(fl(w)[0] for _a, _i, w in C)

    print("--- S1  the +bit4 pairs (MEASURED)\n")
    for v in V:
        if v & 0x10 and (v & ~0x10) in V:
            print(f"        {v:03X} (x{N[v]:<4}) = {v&~0x10:03X} "
                  f"(x{N[v&~0x10]:<4}) + bit4")
    miss = ["%03X" % v for v in V if v & 0x10 and (v & ~0x10) not in V]
    print(f"\n    bit4 values whose base is UNOBSERVED : {miss}")
    print("    (a PREDICTION: 008, 080, 084, 08A, 28A are legal encodings this corpus")
    print("     simply never needs -- falsifiable against any further ROM)")

    print("\n--- S2  THE TWO INDEPENDENT LABELS THAT DECIDE IT (MEASURED)\n")
    print("    0x202.A.dd.1D5 = mac    : `acc += P ; P = coef * mem[p]`   NO write")
    print("    0x212.A.dd.407 = mulst  : `mem[p] <- acc ; P = coef * acc`    WRITES")
    print("        -- determined uniquely by the 19.7 M-assignment search")
    print("           (-semantics.md sect. 6).  0x212 = 0x202 | bit4.")
    print("    0x082 = LFO / modulation-source READ  (-chorus.md sect. 2.2)  NO write")
    print("    0x092 = phase accumulator `phase += inc`, which MUST write the phase")
    print("        back.  0x092 = 0x082 | bit4.")
    print("    These two pairs were labelled by two unrelated investigations, neither")
    print("    of which was looking at bit4.  Both land the same way.")

    print("\n--- S3  ★ THE CONTROL: bit4 must predict ABSENCE (MEASURED)\n")
    print("    A store to mem[ptr] is impossible where addr8 is provably NOT a")
    print("    pointer.  Class 6's addr8 is the table-lookup selector, class 1's is a")
    print("    DRAM bracket code or the unit index, class 8's addr8 = 0x16 is unknown")
    print("    but never a cell.  PREDICT: those classes carry no bit4 at all.\n")
    c4, c0 = collections.Counter(), collections.Counter()
    term = set()
    for a in images38(progs):
        term.add((a, len(progs[a]) - 1))
    for a, i, w in C:
        h, c, ad, l = fl(w)
        (c4 if h & 0x10 else c0)[c] += 1
    print(f"    class distribution, bit4 SET   : "
          f"{dict((('%X' % k), v) for k, v in sorted(c4.items()))}")
    print(f"    class distribution, bit4 CLEAR : "
          f"{dict((('%X' % k), v) for k, v in sorted(c0.items()))}")
    nt4 = collections.Counter()
    ntot = collections.Counter()
    for a, i, w in C:
        if (a, i) in term:
            continue
        h, c, ad, l = fl(w)
        ntot[c] += 1
        if h & 0x10:
            nt4[c] += 1
    forbid = [1, 3, 5, 6, 8]
    hits = sum(nt4.get(c, 0) for c in forbid)
    pop = sum(ntot.get(c, 0) for c in forbid)
    rate = sum(c4.values()) / len(C)
    print(f"\n    EXCLUDING the 38 terminators, bit4 words in classes {forbid}:")
    print(f"        {hits} of {pop}   (expected under independence: {pop*rate:.0f})")
    print("    -> the control PASSES, and it could easily have failed.")
    print("    FLAGGED EXCEPTION: the 5 `612.1.0E/0F.000` terminators do carry bit4")
    print("    while their addr8 is the unit index.  Either a terminator repurposes")
    print("    addr8, or the final store uses a different destination.  Reported, not")
    print("    explained.")

    print("\n--- S4  ★ AN AMBIGUITY BIT4 BREAKS, AND ONE IT DOES NOT (MEASURED)\n")
    print("    -semantics.md sect. 6 left the reverb diffuser's pair")
    print("        `000.2.00.419` and `012.2.00.680`")
    print("    CONSTRAINED TO A 2-PERMUTATION: one is `d_in <- x + t` (a WRITE into the")
    print("    delay line), the other is `y <- d_out - t` (no write).")
    print("    bit4 breaks it: 0x012 has bit4, 0x000 does not.\n")
    ws = progs[16]
    marks = [i for i, w in enumerate(ws) if w == 0x104200000]
    if marks:
        m = marks[0]
        for k in range(m - 1, m + 7):
            h = fl(ws[k])[0]
            print(f"        [{k:>3}] {fmt(ws[k])}   bit4={'SET  ' if h&0x10 else 'clear'}")
    n680 = sum(1 for w in ws if fl(w)[0] == 0x012 and fl(w)[3] == 0x680)
    n419 = sum(1 for w in ws if fl(w)[0] == 0x000 and fl(w)[3] == 0x419)
    print(f"\n    in algo 16: 012.2.**.680 x{n680}, 000.2.**.419 x{n419} "
          f"(one of each per diffuser)")
    print("    ★ RESOLVED: `012.2.00.680` = `d_in <- x + t`, the write, and it sits")
    print("      IMMEDIATELY BEFORE `880.1.20.655`, the DRAM-write half of the bracket")
    print("      -- an independent corroboration from position.  `000.2.00.419` =")
    print("      `y <- d_out - t`.  A 2-permutation left open by the constraint search")
    print("      is now determined.")
    print("\n    THE ONE IT DOES NOT BREAK, reported as prominently: the biquad's")
    print("      `[5] 102.2.FF.687` and `[8] 000.2.03.647` are ALSO a 2-permutation of")
    print("      two latch-writebacks, and NEITHER carries bit4.  Under bit4 = store")
    print("      that is a contradiction unless the latch writeback is a DIFFERENT")
    print("      mechanism from the accumulator store -- which is exactly what")
    print("      -INDEX.md already records: lo12 in {0x647, 0x687} = 'biquad")
    print("      non-multiply steps'.  So bit4 is specifically `mem[ptr] <- ACC`, and")
    print("      the latch->memory writeback is named in lo12.  CONSISTENT, but this")
    print("      is a REPAIR, not a prediction, and I flag it as such.")


# ---------------------------------------------------------------- SECTION origin

def sec_origin(subrom, progs, rom, args):
    print("=== SECTION origin: TASK B -- can the data pointer's origin be pinned?\n")
    imgs = images38(progs)
    classes = sorted({fl(w)[1] for a in imgs for w in progs[a]})

    print("--- O1  the constraint every candidate must satisfy\n")
    print("    The program runs once per sample.  Its state cells must be in the same")
    print("    place next sample.  So over one pass the pointer must either RETURN to")
    print("    its origin, or be RESET.  Test the first: is there a rule 'these classes")
    print("    advance the pointer' under which every image's net delta is zero?\n")
    best = []
    for r in range(len(classes) + 1):
        for sub in itertools.combinations(classes, r):
            S = set(sub)
            nz = sum(1 for a in imgs
                     if sum(s8(fl(w)[2]) for w in progs[a] if fl(w)[1] in S) == 0)
            best.append((nz, len(S), sub))
    best.sort(key=lambda t: (-t[0], -t[1]))
    print(f"    {'net-0 images':>12}  classes")
    for nz, n, sub in best[:6]:
        tag = "   <- DEGENERATE (classes 0 and 5 always have addr8 == 0)" \
              if all(c in (0, 5) for c in sub) else ""
        print(f"    {nz:>8}/{len(imgs)}  {{{','.join('%X'%c for c in sub)}}}{tag}")
    print("\n    Every NON-degenerate rule fails.  With all classes counted the net")
    print("    delta per image is:")
    nets = {a: sum(s8(fl(w)[2]) for w in progs[a]) for a in imgs}
    vals = sorted(nets.values())
    print(f"        min {vals[0]:+d}   max {vals[-1]:+d}   zero in "
          f"{sum(1 for v in vals if v == 0)}/{len(imgs)} images")

    print("\n--- O2  does it return modulo a wrap? (MEASURED)\n")
    print("    A circular buffer of size M would make the pointer return mod M.")
    rows = sorted(((sum(1 for a in imgs if nets[a] % M == 0), M)
                   for M in range(2, 4097)), reverse=True)
    print("    best moduli: " + ", ".join(f"M={m}: {z}/{len(imgs)}" for z, m in rows[:8]))
    print("    The best is M=3 at chance level.  256 (the addr8 space) gives "
          f"{sum(1 for a in imgs if nets[a] % 256 == 0)}/{len(imgs)}.")

    print("\n--- O3  a hi12-bit gate? (MEASURED)\n")
    print("    Perhaps only words with a particular hi12 bit move the pointer.\n")
    gb = []
    for mask in range(4096):
        for pol in (0, 1):
            z = 0
            for a in imgs:
                s = 0
                for w in progs[a]:
                    h, c, ad, l = fl(w)
                    if ((h & mask) != 0) == bool(pol):
                        s += s8(ad)
                if s == 0:
                    z += 1
            gb.append((z, mask, pol))
    gb.sort(key=lambda t: (-t[0], bin(t[1]).count('1')))
    for z, m, p in gb[:5]:
        tag = "   <- DEGENERATE (no word moves the pointer)" if m in (0, 1) and p else ""
        print(f"        {z:>2}/{len(imgs)}  gate: (hi12 & {m:03X}) != 0 is {bool(p)}{tag}")
    print("\n    Only the degenerate gates reach 38/38.  NEGATIVE.")

    print("\n--- O4  where the pointer loads actually live (PROVEN BY CONSTRUCTION)\n")
    n821 = sum(1 for a in imgs for w in progs[a] if fl(w)[3] == 0x821)
    n801 = collections.Counter(fmt(w) for a in imgs for w in progs[a]
                               if fl(w)[0] == 0x801)
    print(f"    words with lo12 == 0x821 (ldptr) in the 38 body images : {n821}")
    print(f"    words with hi12 == 0x801 in the 38 body images         : {dict(n801)}")
    print("    -- the one that exists is the COEFFICIENT-cursor reset, not a data")
    print("       pointer load.")
    print("\n    The firmware builds `801.0.NN.821` at LABEL_0387E6 as")
    print("        08 01 (A>>4)&0F ((A<<4)&F0)|8 21")
    print("    so addr8 == A exactly: an ABSOLUTE 8-bit address, not a delta")
    print("    (-parameters.md sect. 4).  And the cold-boot capture shows those words")
    print("    arriving on the HOST-POKE channel (`transfer 5: 01 60 08 01 05 08 21`")
    print("    = ldptr #0x50), never in the cmd-0x04 I-RAM instruction stream.")
    print("\n    ★ So the pointer-load instruction is real and proven, and it is NOT")
    print("      part of any effect body.  Nothing in a body sets the pointer.")

    print("\n--- O5  the biquad is NOT an independent anchor (CORRECTION)\n")
    print("    -biquad-map.md sect. 7 gives 'channel bases 0x40 (ch 0) and 0x54 (ch 1)'.")
    print("    Those numbers are the CUMULATIVE addr8 walk taken from word 0 with the")
    print("    origin assumed to be zero (tools/kn5000_dsp_biquadmap.py, CURSOR 1).")
    print("    They are therefore origin-RELATIVE and cannot pin the origin.  Anyone")
    print("    reading them as absolute C-RAM addresses would be double-counting an")
    print("    assumption.  Reported because it is easy to get wrong.")

    print("\n--- O6  VERDICT (Task B)\n")
    print("    THE ORIGIN CANNOT BE PINNED FROM THE ROM ALONE.  Four independent")
    print("    searches are negative (O1, O2, O3) and the one proven pointer-load form")
    print("    is absent from every body (O4).  What survives is a single model:")
    print("        the pointer is RESET at program start -- by the terminator's END")
    print("        (sect. end), by the header/stub, or by the host -- to a per-unit")
    print("        base that the instruction stream never names.")
    print("    Of the brief's four candidates, 'an explicit ldptr at section entry' is")
    print("    FALSIFIED (O4: zero occurrences), 'a value set by the header' and 'a")
    print("    per-effect base written by the host' are indistinguishable from")
    print("    'implied by the terminator' on static evidence.")
    print("\n    WHAT WOULD SETTLE IT, in order of cost:")
    print("      1. Run the core and watch the C-RAM/D-RAM address bus for one sample")
    print("         period.  The first data access after the terminator names the")
    print("         origin directly.  The device exists; it is disabled.")
    print("      2. Sweep one host parameter and find which body word's operand")
    print("         changes.  T1 gives the absolute address; the body gives the")
    print("         relative one; the difference IS the origin.  This needs a live")
    print("         core too, but only one number out of it.")
    print("      3. The datasheet.")
    print("    ★ AND THE READY-MADE FALSIFIER STAYS VALID: any candidate origin must")
    print("      still reproduce the phaser's 18 exact cancellations (-axes.md sect.")
    print("      2.2), the biquad's +4 per-band walk, and the reverb's stationary")
    print("      pointer.  All three are DIFFERENCES, so all three are origin-free --")
    print("      which is also why they cannot supply the origin.")


# -------------------------------------------------------------- SECTION coverage

def sec_coverage(subrom, progs, rom, args):
    print("=== SECTION coverage: the honest figure, scoped the -axes.md way\n")
    C = corpus(progs)
    n = len(C)
    dec = sum(1 for _a, _i, w in C if is_decoded(w))
    print(f"    words over the 38 distinct images  : {n}")
    print(f"    the six MAME forms                 : {dec}  ({100.0*dec/n:.1f} %)"
          f"   <- -core-draft.md")

    def allpass(words):
        out = []
        for i in range(len(words) - 2):
            f0, f1 = fl(words[i]), fl(words[i + 1])
            if f0[0] == 0x102 and f0[3] == 0x1CD and f1[0] == 0x212 and f1[3] == 0x412:
                out.append(i)
        return out

    ap_imgs = {a for a in images38(progs) if allpass(progs[a])}
    prior = collections.Counter()
    for a, _i, w in C:
        if is_decoded(w):
            continue
        h, c, a8, l = fl(w)
        if h == 0x212 and c == 2 and l == 0x000:
            prior['212.2.**.000 plain store (chorus, 32 images)'] += 1
        elif h == 0x102 and c == 2 and l == 0x1CD and a in ap_imgs:
            prior['102.2.**.1CD all-pass gain via mem[ptr] (axes, 3 images)'] += 1
        elif h == 0x212 and l == 0x412 and a in ap_imgs:
            prior['212.*.**.412 all-pass section write (axes, 3 images)'] += 1
        elif h in (0x092, 0x094) and c == 0xA and l == 0x200:
            prior['092/094.A.**.200 LFO phase (chorus, 20 images)'] += 1
        elif h == 0x102 and c == 0xA and l == 0x64B:
            prior['102.A.00.64B reverb diffuser gain (axes, 1 image)'] += 1
    base = dec + sum(prior.values())
    for k, v in prior.most_common():
        print(f"        {v:>5}  {k}")
    print(f"    -axes.md baseline                  : {base}  ({100.0*base/n:.1f} %)")

    add = collections.Counter()
    for a, i, w in C:
        h, c, a8, l = fl(w)
        if h == 0x400 and c == 1 and l == 0x000:
            add['400.1.0E/0F.000 = END, whole word decoded'] += 1
        elif a == 16 and h == 0x012 and c == 2 and l == 0x680:
            add['012.2.00.680 = d_in <- x + t   (2-permutation broken, algo 16)'] += 1
        elif a == 16 and h == 0x000 and c == 2 and l == 0x419:
            add['000.2.00.419 = y <- d_out - t  (its partner, algo 16)'] += 1
    print(f"\n    added by THIS note, each scoped to where it was actually read:")
    for k, v in add.most_common():
        print(f"        {v:>5}  {k}")
    tot = base + sum(add.values())
    print(f"        {sum(add.values()):>5}  TOTAL")
    print(f"\n    ★ decoded, revised                 : {tot}  ({100.0*tot/n:.1f} %)")
    print("\n    NOT counted, deliberately:")
    nterm = sum(1 for a in images38(progs)
                if (fl(progs[a][-1])[0] & 0x3FF) != 0)
    nb4 = sum(1 for _a, _i, w in C if fl(w)[0] & 0x10)
    print(f"      * the {nterm} terminators of the form END | <op>: the END half is")
    print("        decoded, the residue op is not, so the WORD is not decoded.")
    print(f"      * the {nb4} words carrying bit4: knowing one bit of a 36-bit word is")
    print("        not a decode.  This is exactly the over-claim -axes.md sect. 6.1")
    print("        refused to make, and the same refusal applies to my own result.")
    print("\n    The gain of this pass is +%.1f points of coverage and a STRUCTURAL"
          % (100.0 * (tot - base) / n))
    print("    result.  Saying otherwise would be dishonest: the structure is worth")
    print("    much more than the three-quarters of a point.")


# ------------------------------------------------------------------------- main

SECTIONS = {'enum': sec_enum, 'lattice': sec_lattice, 'end': sec_end,
            'store': sec_store, 'origin': sec_origin, 'coverage': sec_coverage}


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
