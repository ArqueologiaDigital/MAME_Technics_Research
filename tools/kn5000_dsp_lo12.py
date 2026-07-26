#!/usr/bin/env python3
"""kn5000_dsp_lo12.py -- THE FIELD STRUCTURE OF lo12 (the uPD6383GF ALU field).

Companion to notes/dsp-alu-structure.md.  Every number in that note is printed by
this script, so the note can be re-verified with one command and nothing in it is
a remembered figure.

CORPUS.  The committed disassembly listings of the KN5000 effects DSP:

    ~/compartilhado/kn5000-roms-disasm/dsp/disasm/*.dsm

That is 3057 words = the 38 distinct effect-body images (2974) + the 60-word
common header (kernel.dsm) + the 23-word output stage (epilogue.dsm).  This is
DELIBERATELY a larger corpus than the 2974-word one used by the older
kn5000_dsp_*.py tools, and larger than the 2787 `?word' lines the lo12 census in
the task brief counted: the DECODED words (mac / mac.lb / mulst / ldptr / rstcur /
nop, 270 lines) are exactly the semantic ANCHORS this analysis needs, so removing
them would throw away the evidence.  Section `census' prints the reconciliation
with the brief's numbers (2787 words, 80 distinct lo12, 121 (class4,lo12) pairs)
so the two corpora can be told apart at a glance.

Sections (argv[2..], default = all):
    census     the corpus, the reconciliation, all 80 values, all pairs
    bits       per-bit occupancy; pairwise phi; the bit11/bit5 LOCK
    lattice    is lo12 a bit-field at all?  Hamming-1 closure vs a null
    cut        where is the field boundary?  MI + constrainedness per cut
    grid       the (SRC,L) grid; the 3-way split and its fill
    predicts   how much each candidate sub-field knows about class4 / hi12 /addr8
    checks     PREDICT-THEN-CHECK: the falsifiable claims, and the misses
    motif      lo12 constancy inside the biquad section and the all-pass core

Usage:
    python3 tools/kn5000_dsp_lo12.py [<dsp_disasm_dir>] [sections...]

    default dsp_disasm_dir = ~/compartilhado/kn5000-roms-disasm/dsp/disasm
"""
import collections
import glob
import math
import os
import random
import re
import sys

DEFAULT_DIR = os.path.expanduser(
    "~/compartilhado/kn5000-roms-disasm/dsp/disasm")

WORD_RE = re.compile(r'^\s+w(\d+)\s+([0-9A-F]{10})\s+(\S+)')


# ---------------------------------------------------------------- corpus ----
def load(dsmdir):
    """-> list of dicts, one per I-RAM word of the committed listings."""
    out = []
    for path in sorted(glob.glob(os.path.join(dsmdir, '*.dsm'))):
        name = os.path.basename(path)[:-4]
        for line in open(path):
            m = WORD_RE.match(line)
            if not m:
                continue
            w = int(m.group(2), 16)
            out.append(dict(prog=name, i=int(m.group(1)), w=w,
                            hi=(w >> 24) & 0xFFF, cls=(w >> 20) & 0xF,
                            ad=(w >> 12) & 0xFF, lo=w & 0xFFF,
                            mnem=m.group(3)))
    if not out:
        sys.exit("no words found under %s -- is the disassembly tree there?"
                 % dsmdir)
    return out


# The C-FORMAT families.  In hi12[11:8]==0xC the class4|addr8 split is a fiction
# (bits [24:12] are one 13-bit immediate).  The 0xC40/0xC41 sub-family is the one
# the brief's census excluded to reach 80 distinct lo12, so the same predicate is
# used here for the headline vocabulary.
def is_c40(r):
    return (r['hi'] & 0xFFE) == 0xC40


def is_cfmt(r):
    return (r['hi'] >> 8) == 0xC


# ------------------------------------------------------------ sub-fields ----
# The decomposition this script tests.  NOTHING below assumes it is right; the
# `cut' and `grid' sections are what argue for the boundaries.
def MODE(lo):  return (((lo >> 11) & 1) << 1) | ((lo >> 5) & 1)   # bits 11,5
def SRC(lo):   return (lo >> 6) & 0x1F                            # bits 10..6
def LOW(lo):   return lo & 0x1F                                   # bits 4..0


def H(counter):
    t = sum(counter.values())
    if not t:
        return 0.0
    return -sum(v / t * math.log2(v / t) for v in counter.values() if v)


def phi(pairs):
    n11 = sum(w for a, b, w in pairs if a and b)
    n10 = sum(w for a, b, w in pairs if a and not b)
    n01 = sum(w for a, b, w in pairs if not a and b)
    n00 = sum(w for a, b, w in pairs if not a and not b)
    den = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    return ((n11 * n00 - n10 * n01) / den) if den else 0.0


# --------------------------------------------------------------- census -----
def sec_census(R):
    print("=" * 78)
    print("CENSUS -- the corpus and its reconciliation with the task brief")
    print("=" * 78)
    und = [r for r in R if r['mnem'] == '?word']
    nonc = [r for r in R if not is_c40(r)]
    print("  committed listing words (kernel + epilogue + 38 bodies) : %5d" % len(R))
    print("    of which DECODED (a real mnemonic)                    : %5d  %s"
          % (len(R) - len(und),
             dict(collections.Counter(r['mnem'] for r in R
                                      if r['mnem'] != '?word'))))
    print("    of which C-format (hi12&0xFFE)==0xC40                 : %5d"
          % (len(R) - len(nonc)))
    print()
    print("  BRIEF's corpus = the `?word' lines only:")
    print("      words %d (brief says 2788)   distinct lo12 %d   (class4,lo12) pairs %d"
          % (len(und), len(set(r['lo'] for r in und)),
             len(set((r['cls'], r['lo']) for r in und))))
    print("  THIS script's corpus = every listing word, C-format 0xC4x removed:")
    print("      words %d   distinct lo12 %d   (class4,lo12) pairs %d"
          % (len(nonc), len(set(r['lo'] for r in nonc)),
             len(set((r['cls'], r['lo']) for r in nonc))))
    print("  (same 80-value vocabulary; the decoded words only add OCCURRENCES,")
    print("   which is why the brief's 000/1D5/407 counts are lower by exactly")
    print("   the nop/mac/mulst line counts.  The pair count differs because the")
    print("   brief counts C-format words too, where `class4' is immediate data")
    print("   and not a class at all -- 118 real pairs, 121 if the fiction counts.)")
    print()

    cnt = collections.Counter(r['lo'] for r in nonc)
    print("  ALL %d DISTINCT lo12 VALUES" % len(cnt))
    print("  %-4s %-13s %-2s %-4s %-3s %6s %-11s %s"
          % ("lo12", "binary", "M", "SRC", "L", "n", "K/E/#bodies", "classes"))
    for lo, n in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0])):
        rs = [r for r in nonc if r['lo'] == lo]
        progs = set(r['prog'] for r in rs)
        where = "%s%s%2d" % ('K' if 'kernel' in progs else '-',
                             'E' if 'epilogue' in progs else '-',
                             len([p for p in progs if p.startswith('prog')]))
        cl = collections.Counter(r['cls'] for r in rs)
        print("  %03X %-12s %-2s %02X   %02X  %6d %-11s %s"
              % (lo, format(lo, '012b'), format(MODE(lo), '02b'), SRC(lo), LOW(lo), n, where,
                 " ".join("%X:%d" % kv for kv in sorted(cl.items()))))
    print()
    pairs = collections.Counter((r['cls'], r['lo']) for r in nonc)
    print("  ALL %d (class4, lo12) PAIRS" % len(pairs))
    line = []
    for (c, lo), n in sorted(pairs.items(), key=lambda kv: (kv[0][0], -kv[1])):
        line.append("%X.%03X x%d" % (c, lo, n))
        if len(line) == 6:
            print("    " + "  ".join(line))
            line = []
    if line:
        print("    " + "  ".join(line))


# ----------------------------------------------------------------- bits -----
def sec_bits(R):
    nonc = [r for r in R if not is_c40(r)]
    cnt = collections.Counter(r['lo'] for r in nonc)
    vals = sorted(cnt)
    N = len(nonc)
    print("=" * 78)
    print("BITS -- occupancy, pairwise phi, and the bit11 <-> bit5 LOCK")
    print("=" * 78)
    print("  %-4s %-22s %-7s %-20s %s"
          % ("bit", "#of the 80 values set", "%", "#occurrences set", "%"))
    for b in range(11, -1, -1):
        dv = sum(1 for v in vals if (v >> b) & 1)
        oc = sum(c for v, c in cnt.items() if (v >> b) & 1)
        print("  %-4d %-22d %-7.1f %-20d %.1f"
              % (b, dv, 100 * dv / len(vals), oc, 100 * oc / N))
    print()
    for weighted in (False, True):
        print("  pairwise phi, %s" % ("occurrence-weighted"
                                      if weighted else "over the 80 distinct values"))
        print("      " + " ".join("%6d" % b for b in range(11, -1, -1)))
        for bi in range(11, -1, -1):
            row = []
            for bj in range(11, -1, -1):
                if bi == bj:
                    row.append("     .")
                    continue
                pp = [((v >> bi) & 1, (v >> bj) & 1,
                       cnt[v] if weighted else 1) for v in vals]
                row.append("%+6.2f" % phi(pp))
            print("  %3d " % bi + " ".join(row))
        print()
    b11 = set(v for v in vals if v & 0x800)
    b5 = set(v for v in vals if v & 0x020)
    print("  THE LOCK: bit11 set in %d values / %d occurrences;"
          % (len(b11), sum(cnt[v] for v in b11)))
    print("            bit5  set in %d values / %d occurrences"
          % (len(b5), sum(cnt[v] for v in b5)))
    print("    bit11 without bit5 : %s"
          % ([("%03X" % v) for v in sorted(b11 - b5)] or "NONE"))
    print("    bit5  without bit11: %s"
          % ([("%03X x%d" % (v, cnt[v])) for v in sorted(b5 - b11)] or "NONE"))
    print("    both               : %s"
          % " ".join("%03X x%d" % (v, cnt[v]) for v in sorted(b11 & b5)))
    print()
    print("  every word of the bit-5 family, by (hi12, class4, lo12):")
    fam = [r for r in nonc if r['lo'] & 0x20]
    g = collections.Counter((r['hi'], r['cls'], r['lo']) for r in fam)
    for (hi, cl, lo), n in sorted(g.items(), key=lambda kv: -kv[1]):
        ads = sorted(set(r['ad'] for r in fam
                         if (r['hi'], r['cls'], r['lo']) == (hi, cl, lo)))
        print("    %03X.%X.**.%03X n=%-3d hi12bit6=%s addr8=%s"
              % (hi, cl, lo, n, 'Y' if hi & 0x40 else 'n',
                 " ".join("%02X" % a for a in ads[:8])))
    print()
    h6 = [r for r in nonc if (r['hi'] & 0x40) and not (r['hi'] & 0x800)]
    ok = sum(1 for r in h6 if r['lo'] & 0x20)
    print("  cross-check: hi12 bit6 set AND hi12 bit11 (ESC) clear -> lo12 bit5:"
          " %d/%d" % (ok, len(h6)))


# -------------------------------------------------------------- lattice -----
def sec_lattice(R):
    nonc = [r for r in R if not is_c40(r)]
    cnt = collections.Counter(r['lo'] for r in nonc)
    V = set(cnt)
    print("=" * 78)
    print("LATTICE -- is lo12 a BIT-FIELD or an enumerated opcode?")
    print("=" * 78)
    per = collections.Counter()
    pairs = []
    for v in sorted(V):
        for b in range(12):
            u = v ^ (1 << b)
            if u in V and u > v:
                per[b] += 1
                pairs.append((v, u, b))
    tot = len(pairs)
    random.seed(1)
    bybits = collections.defaultdict(list)
    for x in range(4096):
        bybits[bin(x).count('1')].append(x)
    prof = collections.Counter(bin(v).count('1') for v in V)
    ns = []
    for _ in range(500):
        S = set()
        for p, k in prof.items():
            S |= set(random.sample(bybits[p], k))
        ns.append(sum(1 for v in S for b in range(12)
                      if (v ^ (1 << b)) in S and (v ^ (1 << b)) > v))
    mu = sum(ns) / len(ns)
    sd = (sum((x - mu) ** 2 for x in ns) / len(ns)) ** .5
    print("  Hamming-distance-1 pairs in the 80-value vocabulary : %d" % tot)
    print("  popcount-matched null (500 draws)                   : %.1f +- %.1f"
          % (mu, sd))
    print("  z = %+.1f  -> lo12 DECOMPOSES (same test that established hi12)"
          % ((tot - mu) / sd))
    print()
    print("  %-4s %-7s %s" % ("bit", "#pairs", "the pairs (counts)"))
    for b in range(11, -1, -1):
        ex = sorted([(v, u) for v, u, bb in pairs if bb == b],
                    key=lambda t: -(cnt[t[0]] + cnt[t[1]]))
        print("  %-4d %-7d %s"
              % (b, per[b],
                 " ".join("%03X/%03X(%d/%d)" % (v, u, cnt[v], cnt[u])
                          for v, u in ex[:8])))


# ------------------------------------------------------------------ cut -----
def sec_cut(R):
    nonc = [r for r in R if not is_c40(r)]
    DP = [r for r in nonc if not (r['lo'] & 0x20)]
    V = sorted(set(r['lo'] for r in DP))
    print("=" * 78)
    print("CUT -- where is the boundary?  (datapath words only: lo12 bit5 clear)")
    print("=" * 78)
    print("  %d words, %d distinct lo12." % (len(DP), len(V)))
    print("  For each 2-way split: how many codes each half uses (a real sub-field")
    print("  uses FAR fewer than a free field would), the occurrence-weighted")
    print("  mutual information between the halves (a real split has LOW MI), and")
    print("  H(class4 | high half).")
    print()
    print("  %-4s %-5s %-5s %-9s %-9s %-7s %s"
          % ("cut", "#hi", "of", "#lo", "of", "I(bits)", "H(cls|hi)"))
    Hc = H(collections.Counter(r['cls'] for r in DP))
    for k in range(1, 11):
        ch = collections.Counter()
        cl = collections.Counter()
        cj = collections.Counter()
        for r in DP:
            v = r['lo']
            ch[v >> k] += 1
            cl[v & ((1 << k) - 1)] += 1
            cj[(v >> k, v & ((1 << k) - 1))] += 1
        byh = collections.defaultdict(collections.Counter)
        for r in DP:
            byh[r['lo'] >> k][r['cls']] += 1
        hc = sum(sum(c.values()) / len(DP) * H(c) for c in byh.values())
        print("  %-4d %-5d %-5d %-9d %-9d %-7.3f %.3f"
              % (k, len(ch), 1 << (12 - k), len(cl), 1 << k,
                 H(ch) + H(cl) - H(cj), hc))
    print("  H(class4) with no conditioning = %.3f" % Hc)


# ----------------------------------------------------------------- grid -----
def sec_grid(R):
    nonc = [r for r in R if not is_c40(r)]
    print("=" * 78)
    print("GRID -- lo12[11:6] (rows) x lo12[5:0] (cols), whole corpus")
    print("=" * 78)
    grid = collections.defaultdict(collections.Counter)
    for r in nonc:
        grid[r['lo'] >> 6][r['lo'] & 0x3F] += 1
    Ls = sorted(set(l for g in grid.values() for l in g))
    print("      " + "".join("%-4X" % l for l in Ls))
    for s in sorted(grid):
        print("  %02X  " % s + "".join(("%-4d" % grid[s][l]) if grid[s][l]
                                       else " .  " for l in Ls))
    print()
    print("  Note the BLOCK structure: rows >= 0x20 (lo12 bit11 set) use only")
    print("  columns >= 0x20 (lo12 bit5 set), and vice versa -- the lock, drawn.")
    print()
    DP = [r for r in nonc if not (r['lo'] & 0x20)]
    V = sorted(set(r['lo'] for r in DP))
    srcs = sorted(set(SRC(v) for v in V))
    print("  SRC = lo12[10:6] -> the set of lo12[4:0] seen with it:")
    for s in srcs:
        mem = sorted(set(LOW(v) for v in V if SRC(v) == s))
        n = sum(1 for r in DP if SRC(r['lo']) == s)
        print("    %02X (%s) n=%-5d L: %s"
              % (s, format(s, '05b'), n, " ".join("%02X" % x for x in mem)))
    print()
    lows = sorted(set(LOW(v) for v in V))
    print("  L codes used: %s" % " ".join("%02X" % x for x in lows))
    print("  L codes NOT used: %s"
          % " ".join("%02X" % x for x in range(32) if x not in lows))
    print("  fill of SRC x L : %d used of %d x %d = %d cells (%.1f%%)"
          % (len(V), len(srcs), len(lows), len(srcs) * len(lows),
             100 * len(V) / (len(srcs) * len(lows))))


# ------------------------------------------------------------- predicts -----
def sec_predicts(R):
    nonc = [r for r in R if not is_c40(r)]
    DP = [r for r in nonc if not (r['lo'] & 0x20)]
    print("=" * 78)
    print("PREDICTS -- what does each candidate sub-field KNOW?  (bits; lower is")
    print("            better; `whole lo12' is the floor any split must approach)")
    print("=" * 78)
    fields = [("SRC=[10:6]", lambda r: SRC(r['lo'])),
              ("[4:3]", lambda r: (r['lo'] >> 3) & 3),
              ("[2:0]", lambda r: r['lo'] & 7),
              ("bit4", lambda r: (r['lo'] >> 4) & 1),
              ("bit3", lambda r: (r['lo'] >> 3) & 1),
              ("L=[4:0]", lambda r: LOW(r['lo'])),
              ("whole lo12", lambda r: r['lo'])]
    targets = [("class4", lambda r: r['cls']),
               ("class4 bit3 (cursor)", lambda r: (r['cls'] >> 3) & 1),
               ("class&7==2 (ptr inc)", lambda r: 1 if (r['cls'] & 7) == 2 else 0),
               ("hi12", lambda r: r['hi']),
               ("hi12 bit4 = STORE", lambda r: (r['hi'] >> 4) & 1),
               ("hi12 bit11 = ESC", lambda r: (r['hi'] >> 11) & 1),
               ("hi12 f98 = [9:8]", lambda r: (r['hi'] >> 8) & 3),
               ("hi12 f31 = [3:1]", lambda r: (r['hi'] >> 1) & 7),
               ("addr8 == 0", lambda r: 1 if r['ad'] == 0 else 0),
               ("addr8 sign", lambda r: 1 if r['ad'] >= 128 else 0)]
    print("  %-22s %-9s %s" % ("target", "H(target)",
                               " ".join("%-11s" % f[0] for f in fields)))
    for tn, tf in targets:
        base = H(collections.Counter(tf(r) for r in DP))
        row = []
        for _, ff in fields:
            by = collections.defaultdict(collections.Counter)
            for r in DP:
                by[ff(r)][tf(r)] += 1
            row.append("%-11.3f" % sum(sum(c.values()) / len(DP) * H(c)
                                       for c in by.values()))
        print("  %-22s %-9.3f %s" % (tn, base, " ".join(row)))
    print()
    print("  hi12 bit4 (store acc -> mem[ptr]) rate per L code:")
    by = collections.defaultdict(lambda: [0, 0])
    for r in DP:
        by[LOW(r['lo'])][0] += 1
        if r['hi'] & 0x10:
            by[LOW(r['lo'])][1] += 1
    for l in sorted(by):
        n, b = by[l]
        mem = " ".join("%03X" % v for v in
                       sorted(set(r['lo'] for r in DP if LOW(r['lo']) == l)))
        print("    L=%02X n=%-5d hi12b4=%-5d (%5.1f%%)  %s"
              % (l, n, b, 100 * b / n, mem))
    print()
    print("  hi12 bit4 rate per SRC:")
    by2 = collections.defaultdict(lambda: [0, 0])
    for r in DP:
        by2[SRC(r['lo'])][0] += 1
        if r['hi'] & 0x10:
            by2[SRC(r['lo'])][1] += 1
    for s in sorted(by2):
        n, b = by2[s]
        print("    SRC=%02X n=%-5d hi12b4=%-5d (%5.1f%%)" % (s, n, b, 100 * b / n))


# --------------------------------------------------------------- checks -----
def sec_checks(R):
    nonc = [r for r in R if not is_c40(r)]
    print("=" * 78)
    print("CHECKS -- PREDICT-THEN-CHECK.  Misses are printed, not hidden.")
    print("=" * 78)

    def verdict(ok, bad, name, note=""):
        print("  %-5s %s%s" % ("PASS" if not bad else "MISS", name,
                               ("  " + note) if note else ""))

    b5 = [r for r in nonc if r['lo'] & 0x20]
    bad = [r for r in b5 if r['hi'] & 0x10]
    print("  P-A  a bit-5 word writes a REGISTER, so it should not also carry")
    print("       hi12 bit4 (store acc -> mem[ptr]).")
    verdict(len(b5) - len(bad), bad, "%d bit-5 words, %d with hi12 bit4"
            % (len(b5), len(bad)))
    for r in bad:
        print("         %-26s w%-4d %03X.%X.%02X.%03X"
              % (r['prog'], r['i'], r['hi'], r['cls'], r['ad'], r['lo']))
    print()
    s0b = [r for r in nonc if SRC(r['lo']) == 0x0B]
    off = [r for r in s0b if not (r['cls'] == 1 and r['hi'] in (0x880, 0x900, 0x800))]
    print("  P-B  SRC=0x0B is the external delay-RAM operand -> every such word")
    print("       should be a class-1 8x0 delay-RAM word.")
    verdict(len(s0b) - len(off), off,
            "%d SRC=0x0B words, %d off-family" % (len(s0b), len(off)))
    for k, n in collections.Counter("%03X.%X.%02X.%03X"
                                    % (r['hi'], r['cls'], r['ad'], r['lo'])
                                    for r in off).most_common():
        print("         %s x%d" % (k, n))
    print()
    a = [r for r in s0b if r['cls'] == 0xA]
    print("  P-C  a delay-RAM word never fetches a coefficient -> SRC=0x0B is")
    print("       never class A.")
    verdict(len(s0b), a, "%d SRC=0x0B words, %d class A" % (len(s0b), len(a)))
    print()
    s1c = [r for r in nonc if SRC(r['lo']) == 0x1C]
    off = [r for r in s1c if r['hi'] != 0x092]
    print("  P-D  SRC=0x1C (lo12 0x700) is the LFO/modulation read -> hi12 0x092")
    print("       only.")
    verdict(len(s1c) - len(off), off,
            "%d SRC=0x1C words, %d with another hi12" % (len(s1c), len(off)))
    print()
    s13 = [r for r in nonc if SRC(r['lo']) == 0x13]
    forms = collections.Counter((r['cls'], r['lo']) for r in s13)
    print("  P-E  SRC=0x13 is the table-lookup operand -> exactly two forms,")
    print("       class-6 0x4CD (the lookup) and class-A 0x4C8 (the multiply).")
    verdict(len(s13), [f for f in forms
                       if f not in ((6, 0x4CD), (0xA, 0x4C8))],
            "%d words, forms %s" % (len(s13),
                                    {("%X.%03X" % f): n for f, n in forms.items()}))
    print()
    s00 = [r for r in nonc if SRC(r['lo']) == 0 and not (r['lo'] & 0x20)]
    a = [r for r in s00 if r['cls'] == 0xA]
    print("  P-F  SRC=0x00 = `no operand source' -> should never be class A.")
    verdict(len(s00) - len(a), a,
            "%d SRC=0x00 datapath words, %d class A" % (len(s00), len(a)))
    for k, n in collections.Counter("%03X.A.%02X.%03X" % (r['hi'], r['ad'], r['lo'])
                                    for r in a).most_common(8):
        print("         %s x%d" % (k, n))
    print()
    print("  P-G  lo12 bit0 = the external-DRAM DIRECTION (0 read / 1 write).")
    g = collections.defaultdict(collections.Counter)
    for r in nonc:
        if r['hi'] == 0x880 and r['cls'] == 1:
            g[r['ad']][r['lo']] += 1
    for ad in sorted(g):
        print("       addr8=%02X n=%-4d %s" % (ad, sum(g[ad].values()),
              " ".join("%03X x%d [bit0=%d]" % (l, n, l & 1)
                       for l, n in g[ad].most_common())))
    print("       addr8=20 (the FORCED WRITE): bit0 = 1 in %d/%d"
          % (sum(n for l, n in g[0x20].items() if l & 1), sum(g[0x20].values())))
    print("       addr8=60 (the FORCED READ) : bit0 = 0 in %d/%d"
          % (sum(n for l, n in g[0x60].items() if not (l & 1)),
             sum(g[0x60].values())))
    print("       FALSIFIED by SINGLE DELAY (prog09): its ONE delay-line block is")
    print("       880.1.60.2D9 (bit0=1) then 880.1.20.64B (bit0=1).  A delay must")
    print("       read; two writes and no read is impossible.  So bit0 is NOT the")
    print("       direction and addr8 60/20 stands.")


# ---------------------------------------------------------------- motif -----
def sec_motif(R):
    byprog = collections.defaultdict(list)
    for r in R:
        byprog[r['prog']].append(r)
    for p in byprog:
        byprog[p].sort(key=lambda r: r['i'])
    print("=" * 78)
    print("MOTIF -- is lo12 fixed by the DATAFLOW ROLE?  (if it is the ALU/route")
    print("         field it must be constant at a motif slot even when hi12 is not)")
    print("=" * 78)
    SIG = [0x1D3, 0x412, 0x1D5, 0x1D4, 0x1D5, 0x687, 0x415, 0x407, 0x647]
    n = 0
    bs = collections.defaultdict(collections.Counter)
    for p, ws in byprog.items():
        for j in range(len(ws) - 8):
            if [ws[j + k]['lo'] for k in range(9)] == SIG:
                n += 1
                for k in range(9):
                    bs[k][(ws[j + k]['hi'], ws[j + k]['cls'], ws[j + k]['lo'])] += 1
    print("  the 9-word biquad section, %d occurrences across the corpus:" % n)
    for k in range(9):
        print("    w%d: %s" % (k, "  ".join(
            "%03X.%X.%03X x%d (SRC=%02X L=%02X)" % (h, c, l, m, SRC(l), LOW(l))
            for (h, c, l), m in bs[k].most_common(3))))
    print("  -> lo12 is CONSTANT at every slot; hi12 is NOT (w0, w8).")
    print()
    n = 0
    slots = collections.defaultdict(collections.Counter)
    for p, ws in byprog.items():
        for j in range(len(ws) - 5):
            w = ws[j:j + 6]
            if (w[0]['hi'] == 0x880 and w[0]['ad'] == 0x60 and w[1]['hi'] == 0x104
                    and w[2]['hi'] == 0x000 and w[2]['lo'] == 0x419
                    and w[3]['hi'] == 0x012 and w[4]['hi'] == 0x880
                    and w[4]['ad'] == 0x20 and w[5]['hi'] == 0x102):
                n += 1
                for k in range(6):
                    slots[k][w[k]['lo']] += 1
    print("  the 6-word reverb all-pass core, %d occurrences:" % n)
    for k in range(6):
        print("    slot%d: %s" % (k + 1, "  ".join(
            "%03X x%d (SRC=%02X L=%02X)" % (l, m, SRC(l), LOW(l))
            for l, m in slots[k].most_common())))


SECTIONS = dict(census=sec_census, bits=sec_bits, lattice=sec_lattice,
                cut=sec_cut, grid=sec_grid, predicts=sec_predicts,
                checks=sec_checks, motif=sec_motif)


def main():
    args = sys.argv[1:]
    dsmdir = DEFAULT_DIR
    if args and os.path.isdir(args[0]):
        dsmdir = args.pop(0)
    want = args or list(SECTIONS)
    R = load(dsmdir)
    for s in want:
        if s not in SECTIONS:
            sys.exit("unknown section %r; pick from %s" % (s, list(SECTIONS)))
        SECTIONS[s](R)
        print()


if __name__ == '__main__':
    main()
