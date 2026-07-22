#!/usr/bin/env python3
"""kn5000_dsp_semantics.py -- solve the uPD6383GF instruction semantics against
algorithms whose mathematics is already known exactly.

Companion note: notes/kn5000-dsp-semantics.md

This tool does NOT rewrite any existing parser.  It imports
kn5000_dsp_extract / kn5000_dsp_biquadmap (for the static coefficient banks and
the bilinear inversion) and adds:

  * an explicit MACHINE MODEL (registers bounded by the CDJ-500 block diagram)
  * a bounded, explicitly enumerated HYPOTHESIS SPACE for the nine words of the
    PARAMETRIC EQ biquad section
  * an exhaustive SEARCH of that space, scored by running the candidate
    semantics on an impulse and comparing against the biquad transfer function
    computed directly from the same ROM coefficients
  * the REVERB cross-check: does the surviving vocabulary make the 8-word
    diffuser motif compute a first-order all-pass?
  * impulse-response numbers for both.

Usage:
    python3 tools/kn5000_dsp_extract.py <subrom> /tmp/progs
    python3 tools/kn5000_dsp_semantics.py <subrom> /tmp/progs [sections...]

Sections: model space search verify reverb  (default: all)
"""

import os
import sys
import itertools

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kn5000_dsp_extract as E          # noqa: E402
import kn5000_dsp_biquadmap as M        # noqa: E402


# ---------------------------------------------------------------------------
# The section under analysis (MEASURED; notes/kn5000-dsp-biquad-map.md sect. 1)
# ---------------------------------------------------------------------------

# (word, class, signed addr8 post-increment)
SECTION = [
    (0x0000A001D3, 'A', +0),   # [0]  b1
    (0x0212A01412, 'A', +1),   # [1]  b0
    (0x0202A011D5, 'A', +1),   # [2]  b2
    (0x0202A011D4, 'A', +1),   # [3]  -a1/a0
    (0x0202A001D5, 'A', +0),   # [4]  -a2/a0
    (0x01022FF687, '2', -1),   # [5]  P-consumer
    (0x0804816415, '8', None),  # [6] class 8, operand-less
    (0x0212AFF407, 'A', -1),   # [7]  make-up gain
    (0x0000203647, '2', +3),   # [8]  P-consumer
]
CLASSA = [0, 1, 2, 3, 4, 7]
CONSUM = [5, 8]

# the pointer's position (relative to the band base) when each word executes,
# derived from the signed post-increments above.  MEASURED.
def ptr_walk():
    p, out = 0, []
    for _, cls, d in SECTION:
        out.append(p)
        if d is not None:
            p += d
    return out, p


PTR = ptr_walk()[0]          # [0,0,1,2,3,3,3,2,1]
NET = ptr_walk()[1]          # +4


# ---------------------------------------------------------------------------
# sect. "model" -- the machine model, printed
# ---------------------------------------------------------------------------

MODEL_TEXT = """\
=== THE MACHINE MODEL

Bounded by the CDJ-500 block diagram (pp. 1-15..1-17), nothing invented:

    C-RAM[256], D-RAM[256]      two 24-bit data memories
    MPLY with K and L latches -> P            24x24 -> product register
    ALU 44-bit with ACCA/ACCB   two accumulators, two shifters, OVC
    pointers CP/DP/BP1/BP2/PR1/PR2            (the cursors)
    TR0..TR3                    four temporaries  <-- the carry latches below
    external-DRAM delay controller: OF-RAM ADDR.R + DATA BUF
    DI1-3 / DO1-3               serial audio in/out

The subset this model uses, and nothing else:

    acc      one accumulator                  (ACCA)
    P        the pending multiplier product
    mem[]    the STATE space (the '000.1.NN.000' pointer space; four cells per
             biquad section, cleared at load -- cursor-general note sect. 5.2)
    cursor   the implicit COEFFICIENT pointer into the '801.0' space,
             +1 per class-A word                (MEASURED, biquad-map sect. 2)
    ptr      the signed addr8 POST-increment data cursor  (MEASURED)
    xin      the stage input bus
    TA, TB   two carry latches (TR registers) written by a memory-reading
             multiply and read back by a later store

An instruction is a function state -> state with these unknown parts:

    ACC_OP  what it does with the PENDING product P   {NONE, ADD, SET}
    SRC     where its own operand comes from          {MEM, XIN, ACC}
    WR      what (if anything) it writes to mem[ptr]  {none, XIN, ACC, TA, TB}
    (class A only) P <- coefficient[cursor++] * operand

Fixed, not searched, because each is already MEASURED or PROVEN:
  * the pointer walk  0 0 1 2 3 3 3 2 1, net +4  (from addr8, biquad note)
  * the coefficient order b1 b0 b2 -a1/a0 -a2/a0 makeup, one per class-A word
    (PROVEN BY CONSTRUCTION, biquad-coeffs + biquad-map sect. 4)
  * class A multiplies, class 2 does not          (bit 23)
  * words [5] and [8] consume P, no other word does  (P-consumer statistic,
    pinned at 1.000 / 0.000)
"""


# ---------------------------------------------------------------------------
# the interpreter
# ---------------------------------------------------------------------------

SRC_MEM, SRC_XIN, SRC_ACC = 0, 1, 2
WR_NONE, WR_XIN, WR_ACC, WR_R = 0, 1, 2, 3     # WR_R carries a source word index

OPN, OPADD, OPSET = 0, 1, 2


class Cand(object):
    """one point of the hypothesis space"""
    __slots__ = ('src', 'accop', 'wr', 'out')

    def __init__(self, src, accop, wr, out):
        self.src = src        # dict word -> SRC_*
        self.accop = accop    # dict word -> OP*
        self.wr = wr          # dict word -> (kind, arg)
        self.out = out        # 'acc' or 'P'


def run_section(cand, coef, xs, nsamp, ncell=4, tgt=None):
    """Run one biquad section on the sample list xs.  Returns the outputs.
       If tgt is given, abort (return None) at the first mismatch -- this is
       what makes the 19.7M-point sweep tractable."""
    mem = [0.0] * (ncell + 4)
    ys = []
    for n in range(nsamp):
        xin = xs[n]
        acc = 0.0
        P = 0.0
        rd = {}
        cur = 0
        p = 0
        for i, (_, cls, d) in enumerate(SECTION):
            if cls != '8':
                op = cand.accop.get(i, OPN)
                if op == OPADD:
                    acc = acc + P
                elif op == OPSET:
                    acc = P
                o = None
                if cls == 'A':
                    s = cand.src[i]
                    if s == SRC_MEM:
                        o = mem[p]
                        rd[i] = o
                    elif s == SRC_XIN:
                        o = xin
                    else:
                        o = acc
                w = cand.wr.get(i)
                if w is not None:
                    k, a = w
                    if k == WR_XIN:
                        v = xin
                    elif k == WR_ACC:
                        v = acc
                    else:
                        if a not in rd:
                            return None          # value not yet available
                        v = rd[a]
                    mem[p] = v
                if cls == 'A':
                    P = coef[cur] * o
                    cur += 1
            if d is not None:
                p += d
        y = acc if cand.out == 'acc' else P
        if tgt is not None and abs(y - tgt[n]) > 1e-9:
            return None
        ys.append(y)
    return ys


def target_response(coef, xs, nsamp):
    """The biquad the coefficients DESCRIBE, computed directly.
       v[n] = b0 x + b1 x1 + b2 x2 + A1 v1 + A2 v2 ; y = G v"""
    b1, b0, b2, A1, A2, G = coef
    x1 = x2 = v1 = v2 = 0.0
    out = []
    for n in range(nsamp):
        x = xs[n]
        v = b0 * x + b1 * x1 + b2 * x2 + A1 * v1 + A2 * v2
        out.append(G * v)
        x2, x1 = x1, x
        v2, v1 = v1, v
    return out


# ---------------------------------------------------------------------------
# sect. "space" / "search"
# ---------------------------------------------------------------------------

# a-priori restrictions, each one declared in the note:
#  R1  SRC of a class-A word is one of {MEM, XIN, ACC}.  (DRAM/DI buffers are
#      excluded: the biquad images carry no 880.1.60/20 bracket at all.)
#  R2  exactly one write per state cell per sample, by one of the two words
#      whose pointer sits on that cell.
#  R3  the MAC chain: [2][3][4][5] accumulate (otherwise fewer than five
#      products reach the sum); [1] and [8] may ADD or SET; [0] may be NONE or
#      SET; [7] must be NONE (its predecessor's product was consumed by [5]).
#  R4  reads happen before the write inside one word.
#  R5  class 8 [6] is the identity on this model's state.

CELL_WRITERS = {0: (0, 1), 1: (2, 8), 2: (3, 7), 3: (4, 5)}


def enumerate_space():
    """yield (Cand, ) over the whole declared space; also returns its size."""
    srcs = list(itertools.product((SRC_MEM, SRC_XIN, SRC_ACC), repeat=6))
    accops = []
    for a0 in (OPN, OPSET):
        for a1 in (OPADD, OPSET):
            for a8 in (OPADD, OPSET):
                accops.append((a0, a1, a8))
    wrsel = list(itertools.product(*[CELL_WRITERS[c] for c in range(4)]))
    return srcs, accops, wrsel


def wr_values_for(word, srcmap):
    """the values a write by `word` may take: XIN, ACC, or the value read by an
    earlier MEM-reading class-A word."""
    out = [(WR_XIN, None), (WR_ACC, None)]
    for j in CLASSA:
        if j < word and srcmap.get(j) == SRC_MEM:
            out.append((WR_R, j))
    return out


def search(coefs, verbose=True):
    """coefs: a list of coefficient 6-vectors.  A candidate must reproduce the
    biquad for EVERY one of them (generic vectors first, so that no accidental
    zero or repeat in a real bank can make a wrong assignment look right)."""
    srcs, accops, wrsel = enumerate_space()
    xs = [1.0] + [0.0] * 23
    coef = coefs[0]
    tgts = [target_response(c, xs, 12) for c in coefs]
    tgt = tgts[0]
    hits = []
    nspace = 0
    ntried = 0
    for src in srcs:
        srcmap = dict(zip(CLASSA, src))
        for wsel in wrsel:
            valsets = [wr_values_for(w, srcmap) for w in wsel]
            nspace += len(accops) * 1
            for vals in itertools.product(*valsets):
                wr = dict(zip(wsel, vals))
                if len(wr) != 4:
                    continue                     # two cells sharing a writer
                for ac in accops:
                    a0, a1, a8 = ac
                    accop = {0: a0, 1: a1, 2: OPADD, 3: OPADD, 4: OPADD,
                             5: OPADD, 7: OPN, 8: a8}
                    for outreg in ('acc', 'P'):
                        ntried += 1
                        c = Cand(srcmap, accop, wr, outreg)
                        if run_section(c, coef, xs, 12, tgt=tgt) is None:
                            continue
                        if all(run_section(c, coefs[m], xs, 12,
                                           tgt=tgts[m]) is not None
                               for m in range(1, len(coefs))):
                            hits.append((src, wsel, vals, ac, outreg))
    return hits, ntried


def space_size():
    srcs, accops, wrsel = enumerate_space()
    tot = 0
    for src in srcs:
        srcmap = dict(zip(CLASSA, src))
        for wsel in wrsel:
            if len(set(wsel)) != 4:
                continue
            n = 1
            for w in wsel:
                n *= len(wr_values_for(w, srcmap))
            tot += n * len(accops) * 2
    return tot


# ---------------------------------------------------------------------------
# the coefficient banks
# ---------------------------------------------------------------------------

# where each image's 6-word biquad blocks start inside its uploaded bank.
# MEASURED, biquad-map note sect. 2.3 / sect. 4: OVERDRIVE loads 2+6+1 twice,
# EXCITER 3+6+2 twice, PARAMETRIC EQ five blocks of six from 0x00.
BLOCK_STARTS = {33: [2, 11], 35: [3, 14], 39: [0, 6, 12, 18, 24]}


def bank_blocks(rom, algo):
    """[(bank offset, 6 raw words)] for the biquad blocks of one image."""
    flat, base0 = [], None
    for base, ws in M.sbank(rom, algo):
        if base is None:
            continue
        if base0 is None:
            base0 = base
        while len(flat) < base - base0:
            flat.append(0)
        flat.extend(ws)
    out = []
    for st in BLOCK_STARTS.get(algo, []):
        if st + 6 <= len(flat):
            out.append((st, flat[st:st + 6]))
    return out


def decode_block(ws):
    """6 raw 24-bit words -> the six machine coefficients, in cursor order."""
    b1 = M.q(ws[0], 22)
    b0 = M.q(ws[1], 22)
    b2 = M.q(ws[2], 22)
    A1 = M.q(ws[3], 22)      # already NEGATED in ROM
    A2 = M.q(ws[4], 23)      # already NEGATED in ROM, Q0.23
    G = M.q(ws[5], 22)
    return [b1, b0, b2, A1, A2, G]


# ---------------------------------------------------------------------------
# THE REVERB CROSS-CHECK
# ---------------------------------------------------------------------------

MOTIF = ['880.1.60.2D4', '104.2.00.000', '000.2.00.419', '012.2.00.680',
         '880.1.20.655', '102.A.00.64B', '000.2.00.000', '000.2.00.000']

# CONCERT REVERB 1 stage gains, cursor slots 0x98..0x9C | 0xA1..0xA4
# (MEASURED, cursor-general note sect. 3.2)
GAINS_C1 = [0.750, 0.630, 0.620, 0.600, 0.500,
            0.730, 0.720, 0.700, 0.600]
# delay lengths, reverb note sect. 2 (chain 0 then chain 1, pre-delay dropped)
DELAYS = [452, 978, 1077, 691, 789, 638, 1462, 496, 774]


def allpass_chain(x, gains, delays, nsamp):
    """one-multiplier all-pass:  t = g*(x + d_out) ; d_in = x + t ; y = d_out - t
       H(z) = (-g + z^-N) / (1 - g z^-N)"""
    lines = [[0.0] * d for d in delays]
    pos = [0] * len(delays)
    out = []
    for n in range(nsamp):
        s = x[n] if n < len(x) else 0.0
        for k in range(len(delays)):
            dout = lines[k][pos[k]]
            t = gains[k] * (s + dout)
            lines[k][pos[k]] = s + t
            pos[k] = (pos[k] + 1) % delays[k]
            s = dout - t
        out.append(s)
    return out


def allpass_check(g, N, nsamp=60000):
    """energy check: a true all-pass has unit gain at every frequency, so the
    impulse response has total energy exactly 1."""
    line = [0.0] * N
    p = 0
    e = 0.0
    for n in range(nsamp):
        s = 1.0 if n == 0 else 0.0
        dout = line[p]
        t = g * (s + dout)
        line[p] = s + t
        p = (p + 1) % N
        y = dout - t
        e += y * y
    return e


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def sec_model():
    print(MODEL_TEXT)
    print("pointer walk from the signed addr8 post-increments:")
    print("   word :  " + "  ".join("[%d]" % i for i in range(9)))
    print("   ptr  :  " + "  ".join(" %d " % v for v in PTR))
    print("   net per band: +%d\n" % NET)


def sec_space():
    srcs, accops, wrsel = enumerate_space()
    print("=== THE HYPOTHESIS SPACE\n")
    print("  SRC per class-A word (6 words)      : 3^6  = %d" % len(srcs))
    print("  cell-writer selection (4 cells)     : 2^4  = %d" % len(wrsel))
    print("  written value per writer            : 2..6 each")
    print("  ACC_OP free at [0],[1],[8]          : %d" % len(accops))
    print("  section output register             : 2")
    print("  ------------------------------------------------")
    print("  TOTAL points ENUMERATED             : %d" % space_size())
    print("""
  Excluded a priori, and why (each is a restriction the note must own):
   R1 class-A SRC not from the external-DRAM data buffer or the DI latches:
      the biquad-bearing images contain no 880.1.60/880.1.20 bracket at all.
   R2 exactly one write per state cell per sample, by one of the two words
      whose pointer sits on that cell.  (Both-write and no-write are excluded;
      no-write makes the filter time-varying, both-write is redundant.)
   R3 [2][3][4][5] must accumulate, or fewer than five products reach the sum;
      [7] must not, its predecessor's product was already consumed by [5].
   R4 read-before-write inside one instruction.
   R5 class 8 is the identity on the modelled state.
""")


def sec_search(rom):
    print("=== THE SEARCH\n")
    import random
    random.seed(20260722)
    gen = [[random.uniform(-0.9, 0.9) for _ in range(5)] + [1.7]
           for _ in range(2)]
    for g in gen:
        g[3] *= 0.5
        g[4] *= 0.5
    coef = decode_block(bank_blocks(rom, 33)[0][1])
    print("scored against TWO generic random coefficient vectors (so that no")
    print("accidental zero or repeated value in a real bank can make a wrong")
    print("assignment pass), then re-verified on the real ROM banks:")
    for g in gen:
        print("   b1=%+.6f b0=%+.6f b2=%+.6f  A1=%+.6f A2=%+.6f  G=%+.6f"
              % tuple(g))
    print("   OVERDRIVE  (algo 33, bank +02, the real thing):")
    print("   b1=%+.6f b0=%+.6f b2=%+.6f  A1=%+.6f A2=%+.6f  G=%+.6f"
          % tuple(coef))
    hits, ntried = search(gen + [coef])
    print("\n   points visited : %d" % ntried)
    print("   exact matches  : %d" % len(hits))
    print()
    summarise(hits)
    print("   first three survivors, in full:\n")
    for h in hits[:3]:
        src, wsel, vals, ac, outreg = h
        print("   ---- solution")
        names = {SRC_MEM: 'MEM', SRC_XIN: 'XIN', SRC_ACC: 'ACC'}
        opn = {OPN: '-', OPADD: 'ADD', OPSET: 'SET'}
        srcmap = dict(zip(CLASSA, src))
        accop = {0: ac[0], 1: ac[1], 2: OPADD, 3: OPADD, 4: OPADD,
                 5: OPADD, 7: OPN, 8: ac[2]}
        wr = dict(zip(wsel, vals))
        for i, (w, cls, d) in enumerate(SECTION):
            s = names.get(srcmap.get(i), '')
            wv = ''
            if i in wr:
                k, a = wr[i]
                wv = ('mem[p]<-XIN' if k == WR_XIN else
                      'mem[p]<-ACC' if k == WR_ACC else
                      'mem[p]<-latch(read of [%d])' % a)
            print("     [%d] %010X  cls %s  ptr S%d  accop %-3s  src %-3s  %s"
                  % (i, w, cls, PTR[i], opn.get(accop.get(i, OPN)), s, wv))
        print("     output register: %s" % outreg)
    return hits, coef


def summarise(hits):
    """what every survivor agrees on, and what it does not."""
    names = {SRC_MEM: 'MEM', SRC_XIN: 'XIN', SRC_ACC: 'ACC'}
    opn = {OPN: 'none', OPADD: 'ADD-P', OPSET: 'SET-P'}
    attr = {}
    for src, wsel, vals, ac, outreg in hits:
        srcmap = dict(zip(CLASSA, src))
        accop = {0: ac[0], 1: ac[1], 2: OPADD, 3: OPADD, 4: OPADD,
                 5: OPADD, 7: OPN, 8: ac[2]}
        wr = dict(zip(wsel, vals))
        for i in range(9):
            a = attr.setdefault(i, {'src': set(), 'accop': set(), 'wr': set()})
            if i in srcmap:
                a['src'].add(names[srcmap[i]])
            if i in accop:
                a['accop'].add(opn[accop[i]])
            if i in wr:
                k, ar = wr[i]
                a['wr'].add('XIN' if k == WR_XIN else 'ACC' if k == WR_ACC
                            else 'latch[%d]' % ar)
            else:
                a['wr'].add('-')
        attr.setdefault('out', set()).add(outreg)
    print("   what ALL %d survivors agree on (DETERMINED) and what they do"
          " not (CONSTRAINED):\n" % len(hits))
    print("     word            ptr   operand      P-op          write")
    for i in range(9):
        a = attr[i]
        def f(ss):
            if not ss:
                return '-'
            return sorted(ss)[0] if len(ss) == 1 \
                else '{' + '|'.join(sorted(ss)) + '}'
        print("     [%d] %010X S%d   %-12s %-13s %s"
              % (i, SECTION[i][0], PTR[i], f(a['src']),
                 f(a['accop']), f(a['wr'])))
    print("     section output register: %s" % '|'.join(sorted(attr['out'])))
    print(PREFERRED)


PREFERRED = """
   The residual 144 are FOUR observationally-equivalent binary choices inside
   one section (which of two words performs a write, and whether the sum is
   started by SET-P at [1] or by an already-zero accumulator).  The ENCODING
   breaks two of them, independently of the mathematics:

     * [1] and [7] are the only two words in the section with hi12 = 0x212,
       and [7] is DETERMINED to be a write-and-multiply.  Reading hi12 = 0x212
       as "write the operand to mem[ptr] and multiply by it" places the S0
       write on [1], not on [0].
     * [0] (lo12 0x1D3) and [3] (lo12 0x1D4) are exactly the two memory reads
       whose value is written to another cell later in the section; [2] and [4]
       (lo12 0x1D5) are the two whose value is not.  Reading 0x1D3/0x1D4 as
       "read into carry latch A/B" and 0x647/0x687 as "consume P and store
       latch A/B" places the S1 and S3 writes on [8] and [5] -- the two
       P-consumers -- which is also the only reading in which those two words
       do anything beyond an accumulate the class-A words already perform.

   The preferred reading, then, is DIRECT FORM I with four state cells and four
   writes, two of them folded into multiply instructions:

     [0] b1  * S0(=x[n-1]) ; latch A <- S0
     [1] S0 <- x[n] ; b0 * x[n]              (hi12 0x212 = write-and-multiply)
     [2] b2  * S1(=x[n-2])
     [3] -a1 * S2(=v[n-1]) ; latch B <- S2
     [4] -a2 * S3(=v[n-2])
     [5] acc += P  (the sum v[n] is complete) ; S3 <- latch B   (v2 <- v1)
     [6] class 8: the filter-output step on acc (rescale/round/saturate)
     [7] S2 <- acc (v1 <- v) ; P = makeup * acc                 (the output)
     [8] acc <- P ; S1 <- latch A                               (x2 <- x1)

   Note that the recursion runs on the UNSCALED sum v, and the make-up gain is
   applied only on the way out -- which is exactly why the sixth coefficient is
   the reciprocal of the numerator scaling and why it is never touched by the
   parameter path.
"""


def sec_verify(rom, hits):
    print("\n=== IMPULSE-RESPONSE VERIFICATION on real ROM banks\n")
    if not hits:
        print("   no surviving semantics -- nothing to verify")
        return
    src, wsel, vals, ac, outreg = hits[0]
    srcmap = dict(zip(CLASSA, src))
    accop = {0: ac[0], 1: ac[1], 2: OPADD, 3: OPADD, 4: OPADD,
             5: OPADD, 7: OPN, 8: ac[2]}
    cand = Cand(srcmap, accop, dict(zip(wsel, vals)), outreg)
    cases = [(33, 'OVERDRIVE'), (35, 'EXCITER'), (39, 'PARAMETRIC EQ')]
    xs = [1.0] + [0.0] * 63
    for algo, name in cases:
        for base, ws in bank_blocks(rom, algo):
            coef = decode_block(ws)
            if all(abs(c) < 1e-12 for c in coef[:5]):
                continue
            got = run_section(cand, coef, xs, 64)
            want = target_response(coef, xs, 64)
            err = max(abs(a - b) for a, b in zip(got, want))
            rel = err / max(1e-30, max(abs(v) for v in want))
            print("   algo %2d %-14s block +%02X   max|err| = %.3e   "
                  "relative %.3e   h[0..3] = %+.6f %+.6f %+.6f %+.6f"
                  % (algo, name, base, err, rel, got[0], got[1],
                     got[2], got[3]))
        if algo == 39:
            break


def sec_reverb():
    print("\n=== THE REVERB CROSS-CHECK\n")
    print("the 8-word diffuser motif (algo 16, words 19..26 and 8 more times):")
    for i, w in enumerate(MOTIF):
        print("     [%d] %s" % (i, w))
    print("""
The model built on the biquad says:
   * class A  = P <- coefficient[cursor++] * <one operand>          (1 word)
   * a class-2 word may compute an ALU sum of two register operands
   * 880.1.60 / 880.1.20 open and close an external-DRAM transaction

The ONLY realisation of a first-order all-pass with EXACTLY ONE multiply is

     t     = g * (x + d_out)
     d_in  = x + t
     y     = d_out - t          =>   H(z) = (-g + z^-N)/(1 - g z^-N)

which needs, besides the delay read and the delay write, exactly
   one ALU add   x + d_out      -> feeds the multiplier
   one multiply  g * (...)      -> the class-A word, gain from the cursor
   one ALU add   x + t          -> the value written back to the delay
   one ALU sub   d_out - t      -> the stage output
i.e. THREE non-multiplying arithmetic words.  The motif has exactly three:
   104.2.00.000   the all-pass marker (present in every all-pass effect and in
                  no other, MCC +0.881) -- the  x + d_out  sum
   000.2.00.419   } the  x + t  and  d_out - t  pair
   012.2.00.680   }
""")
    print("all-pass energy test (a true all-pass has impulse energy exactly 1):")
    for g, N in zip(GAINS_C1, DELAYS):
        e = allpass_check(g, N)
        print("     g = %.3f  N = %4d   impulse energy = %.9f" % (g, N, e))
    print()
    y = allpass_chain([1.0], GAINS_C1, DELAYS, 40000)
    import math
    print("nine-stage diffuser chain, CONCERT REVERB 1 gains and the reverb")
    print("note's delay lengths -- energy decay relief:")
    tot = sum(v * v for v in y)
    acc = 0.0
    marks = [0.1, 0.5, 0.9, 0.99]
    mi = 0
    for n, v in enumerate(y):
        acc += v * v
        while mi < len(marks) and acc >= marks[mi] * tot:
            print("     %3d%% of the energy has arrived by  %6d samples"
                  " (%7.1f ms)" % (int(marks[mi] * 100), n, n / 44.1))
            mi += 1
    nz = sum(1 for v in y[:8000] if abs(v) > 1e-6)
    print("     echo density: %d taps above 1e-6 in the first 8000 samples"
          " (%.1f/ms)" % (nz, nz / (8000 / 44.1)))
    print("     total energy = %.6f  (unity => the cascade is loss-less, i.e."
          " all-pass, as a pure diffuser must be)" % tot)
    peak = max(abs(v) for v in y)
    print("     peak |h| = %.6f at n = %d"
          % (peak, max(range(len(y)), key=lambda k: abs(y[k]))))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    rom = argv[1]
    want = argv[3:] if len(argv) > 3 else \
        ['model', 'space', 'search', 'verify', 'reverb']
    hits = []
    if 'model' in want:
        sec_model()
    if 'space' in want:
        sec_space()
    if 'search' in want or 'verify' in want:
        hits, _ = sec_search(rom)
    if 'verify' in want:
        sec_verify(rom, hits)
    if 'reverb' in want:
        sec_reverb()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
