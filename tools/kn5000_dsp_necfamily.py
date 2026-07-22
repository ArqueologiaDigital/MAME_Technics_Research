#!/usr/bin/env python3
"""kn5000_dsp_necfamily.py -- is the NEC uPD6383GF a descendant of the uPD7720/7725?

Tests the "NEC DSP family" hypothesis: MAME already emulates NEC's earlier
uPD7725 (src/devices/cpu/upd7725), whose 24-bit word is horizontal microcode
with an instruction TYPE at the top, an ALU op, an accumulator select, pointer
modifiers and a src/dst nibble pair at the bottom, plus a JP type carrying a
9-bit condition and an 11-bit next address.  If the 6383 is a widened
descendant, that shape should be recoverable from our 36-bit corpus.

Nothing here rewrites parsing: it imports kn5000_dsp_extract / _encoding and
reuses tools/kn5000_dsp_wordfields.py's capture parser for the header block.

Sections (pass names as argv[3..], default = all):
    layouts   candidate field layouts, scored by partition quality
    branch    ** exhaustive search for a next-address field (the big one)
    pconsume  does any field explain the measured P-consumer split?
    alu       does any window partition class 2 where earlier splits failed?
    top       do the top bits split as type+select the way the 7725's do?
    cond      small-field value clustering that could be a COND field

Usage:
    python3 tools/kn5000_dsp_extract.py <subprogram.rom> /tmp/progs
    python3 tools/kn5000_dsp_necfamily.py <subprogram.rom> /tmp/progs [sections]
"""
import collections
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_encoding as E   # noqa: E402

WORDBITS = 36
HERE = os.path.dirname(os.path.abspath(__file__))
CAPTURE = os.path.join(HERE, "..", "notes", "data",
                       "kn5000_dsp1_upload_coldboot.txt")

field = E.field
fmt36 = E.fmt36
entropy = E.entropy


def fl(w):
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def binom_p(k, n, p):
    """two-sided-ish tail probability of >=k (or <=k) successes."""
    def tail_ge(k, n, p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                   for i in range(k, n + 1))
    return tail_ge(k, n, p) if k >= n * p else 1 - tail_ge(k + 1, n, p)


# --------------------------------------------------------------- capture

def capture_blocks(path):
    """-> {iram_addr: [word ints]} for cmd-0x01 uploads whose body is 5-aligned."""
    if not os.path.exists(path):
        return {}
    lines = open(path).read().splitlines()
    out, i = {}, 0
    while i < len(lines):
        m = re.match(r"transfer\s+\d+: cmd (0x[0-9A-Fa-f]+)\s+(\d+) bytes", lines[i])
        if not m:
            i += 1
            continue
        cmd, n = int(m.group(1), 16), int(m.group(2))
        pay, j = [], i + 1
        while j < len(lines) and re.match(r"\s+[0-9A-F]{4}:", lines[j]):
            pay += [int(b, 16) for b in lines[j].split(":")[1].split()]
            j += 1
        i = j
        if cmd == 0x01 and n > 2 and (n - 2) % 5 == 0:
            addr = (pay[0] << 8) | pay[1]
            body = pay[2:]
            out[addr] = [int.from_bytes(bytes(body[k:k + 5]), "big")
                         for k in range(0, len(body), 5)]
    return out


# ------------------------------------------------------------ 1. layouts

# Candidate layouts.  Each is (name, [(fieldname, hi, lo), ...]).
# L7725x1 : the 7725 word verbatim in the low 24 bits, top 12 unexplained.
# L7725x15: every field scaled 1.5x (24->36), rounding widths up.
# LWIDE   : the 7725 shape with the ADDRESS-ish fields widened to 8 bits
#           (256-deep C-RAM/D-RAM) and src/dst kept at 4 bits.
# LOURS   : our published working map, for comparison.
LAYOUTS = {
    "L7725x1": [("type", 35, 34), ("?hi", 33, 24), ("psel", 23, 22),
                ("alu", 21, 18), ("asl", 17, 17), ("dpl", 15, 14),
                ("dphm", 13, 10), ("rp", 9, 9), ("src", 7, 4), ("dst", 3, 0)],
    "L7725x15": [("type", 35, 33), ("psel", 32, 30), ("alu", 29, 24),
                 ("asl", 23, 22), ("dpl", 21, 19), ("dphm", 18, 13),
                 ("rp", 12, 12), ("src", 11, 6), ("dst", 5, 0)],
    "LWIDE": [("type", 35, 34), ("psel", 33, 32), ("alu", 31, 28),
              ("mode", 27, 24), ("class", 23, 20), ("addr", 19, 12),
              ("ptr", 11, 8), ("src", 7, 4), ("dst", 3, 0)],
    "LOURS": [("hi12", 35, 24), ("class4", 23, 20), ("addr8", 19, 12),
              ("lo12", 11, 0)],
}


def partition_score(words, hi, lo):
    """How much more constant do the OTHER bits become, given this field?
    Sum over the other bits of (corpus entropy - conditional entropy)."""
    n = len(words)
    f = [field(w, hi, lo) for w in words]
    groups = collections.defaultdict(list)
    for a, w in zip(f, words):
        groups[a].append(w)
    tot = 0.0
    for b in range(WORDBITS):
        if lo <= b <= hi:
            continue
        col = [(w >> b) & 1 for w in words]
        H = entropy(col)
        Hc = sum(len(g) / n * entropy([(w >> b) & 1 for w in g])
                 for g in groups.values())
        tot += H - Hc
    return tot


def sec_layouts(progs, words):
    print("=" * 74)
    print("1. CANDIDATE FIELD LAYOUTS -- borrowed shapes, scored")
    print("=" * 74)
    print("partition score = sum over the OTHER 36-w bits of (H(bit) - H(bit|field)).")
    print("A real field explains its neighbours; a phantom one does not.\n")
    for name, flds in LAYOUTS.items():
        print(f"  {name}")
        for fn, hi, lo in flds:
            vals = [field(w, hi, lo) for w in words]
            nv = len(set(vals))
            sc = partition_score(words, hi, lo)
            space = 1 << (hi - lo + 1)
            print(f"    {fn:>6} [{hi:2d}:{lo:2d}] {nv:4d}/{space:<5d} vals "
                  f"({nv/space:5.1%})  H={entropy(vals):5.2f}  score={sc:6.3f}")
        print()
    print("  REFERENCE: exhaustive best-scoring windows of each width\n")
    for w_ in (2, 3, 4, 5, 6, 8):
        rows = sorted(((partition_score(words, lo + w_ - 1, lo), lo)
                       for lo in range(WORDBITS - w_ + 1)), reverse=True)[:3]
        s = "  ".join(f"[{lo+w_-1}:{lo}] {sc:.3f}" for sc, lo in rows)
        print(f"    width {w_}: {s}")


# ------------------------------------------------------------- 2. branch

def sec_branch(progs, addrs, cap):
    print()
    print("=" * 74)
    print("2. ** BRANCH HUNT -- a field carrying an address INSIDE the program")
    print("=" * 74)
    print("PREDICTION (stated before measuring): if the 6383 has a 7725-style JP,")
    print("some contiguous field (possibly shifted left, as the 7725's NA sits at")
    print("[12:2]) carries, in a MINORITY of words, a value inside that program's")
    print("own I-RAM extent [load, load+len).  Fall-through words carry junk there,")
    print("so the discriminator is: does ANY field position produce in-range values")
    print("that are (a) rare, (b) present in most programs, (c) NOT explainable as")
    print("the operand address we already know about?\n")

    imgs = {}
    for a, p in progs.items():
        imgs.setdefault(tuple(p), []).append(a)
    print(f"  {len(imgs)} distinct images, "
          f"{sum(len(p) for p in imgs)} words scanned per field position\n")

    # For each (hi,lo,shift), count words whose value lands in the program extent.
    results = []
    for w_ in range(7, 13):
        for lo in range(WORDBITS - w_ + 1):
            hi = lo + w_ - 1
            for shift in (0, 1, 2):
                inr = tot = 0
                progs_hit = 0
                perprog = []
                for img, alist in imgs.items():
                    base, n = addrs[alist[0]][0], len(img)
                    lo_a, hi_a = base, base + n
                    c = 0
                    for wd in img:
                        v = field(wd, hi, lo) << shift
                        tot += 1
                        if lo_a <= v < hi_a:
                            c += 1
                    inr += c
                    perprog.append(c)
                    if c:
                        progs_hit += 1
                results.append((inr / tot, inr, tot, progs_hit, hi, lo, shift,
                                perprog))

    # chance expectation: a uniform field of width w hits an n-word window with
    # probability n / 2^(w-shift-ish); report ratio to that.
    print("  field       shift  in-range   rate   chance   ratio  progs-with-hits")
    rows = []
    for rate, inr, tot, ph, hi, lo, shift, pp in results:
        w_ = hi - lo + 1
        span = (1 << w_) << shift
        # mean program length over images
        meanlen = sum(len(i) for i in imgs) / len(imgs)
        chance = min(1.0, meanlen / span)
        rows.append((rate / chance if chance else 0, rate, inr, tot, ph, hi, lo,
                     shift, chance))
    rows.sort(reverse=True)
    for ratio, rate, inr, tot, ph, hi, lo, shift, ch in rows[:14]:
        print(f"  [{hi:2d}:{lo:2d}]<<{shift}  {inr:6d}/{tot} {rate:6.3f} "
              f"{ch:8.3f} {ratio:7.2f}  {ph}/{len(imgs)}")

    print("\n  -- RARITY FILTER: a branch is rare.  Restrict to fields whose")
    print("  in-range rate is between 0.5% and 12% AND which hit >=50% of images:")
    cands = [r for r in rows if 0.005 <= r[1] <= 0.12 and r[4] >= len(imgs) // 2]
    if not cands:
        print("    NONE.  Every field position is either almost never in range")
        print("    or in range so often that it is the operand address, not a target.")
    for ratio, rate, inr, tot, ph, hi, lo, shift, ch in cands[:10]:
        print(f"    [{hi:2d}:{lo:2d}]<<{shift}  rate {rate:.3f} ratio {ratio:.2f} "
              f"images {ph}/{len(imgs)}")

    # The unit-1 discriminator: one image loads at 200..332, all others at 84..
    print("\n  -- THE RELOCATION DISCRIMINATOR (the strongest available test).")
    print("  One image loads at I-RAM 200 (len 133), the rest at 84.  A genuine")
    print("  absolute next-address field must carry values >=200 in THAT image and")
    print("  <200 in the others.  Scan every field for that signature:\n")
    u1 = [(img, alist) for img, alist in imgs.items() if addrs[alist[0]][0] == 200]
    u0 = [(img, alist) for img, alist in imgs.items() if addrs[alist[0]][0] == 84]
    print(f"    unit-1 images: {len(u1)}   unit-0 images: {len(u0)}")
    best = []
    for w_ in range(8, 13):
        for lo in range(WORDBITS - w_ + 1):
            hi = lo + w_ - 1
            for shift in (0, 1, 2):
                a = [field(x, hi, lo) << shift for img, _ in u1 for x in img]
                b = [field(x, hi, lo) << shift for img, _ in u0 for x in img]
                ha = sum(1 for v in a if 200 <= v < 333) / max(len(a), 1)
                hb = sum(1 for v in b if 84 <= v < 217) / max(len(b), 1)
                xa = sum(1 for v in a if 84 <= v < 217) / max(len(a), 1)
                best.append((ha - xa, ha, xa, hb, hi, lo, shift))
    best.sort(reverse=True)
    print("    field      P(in own extent|unit1)  P(in unit0 extent|unit1)  delta"
          "   P(own|unit0)")
    for d, ha, xa, hb, hi, lo, shift in best[:8]:
        print(f"    [{hi:2d}:{lo:2d}]<<{shift}   {ha:18.3f}  {xa:22.3f} "
              f"{d:+7.3f}  {hb:10.3f}")

    # -- unrolling: the decisive NEGATIVE control for loops in effect bodies
    print("\n  -- UNROLLING CONTROL (the decisive negative evidence).")
    print("  A machine with loops would emit ONE all-pass section and loop it.")
    print("  Count structurally identical repeated blocks whose ONLY difference is")
    print("  the addr8 operand -- those are hand-unrolled iterations:\n")
    for img, alist in sorted(imgs.items(), key=lambda kv: -len(kv[0]))[:6]:
        p = list(img)
        # mask out addr8 and look for the longest repeated masked run
        m = [w & ~(0xFF << 12) for w in p]
        best = (0, 0)
        for period in range(2, 12):
            run = 0
            for i in range(len(m) - period):
                if m[i] == m[i + period]:
                    run += 1
                else:
                    if run > best[0]:
                        best = (run, period)
                    run = 0
            if run > best[0]:
                best = (run, period)
        print(f"    algo{alist[0]:02d} len {len(p):3d}: longest addr8-only-varying "
              f"repeat = {best[0]} words at period {best[1]}")
    print("\n  If those runs are long, the bodies are UNROLLED and contain no")
    print("  backward branch at all -- which is what a branch search must explain.")

    # header / stub, where the control flow is expected to live
    if cap:
        print("\n  -- THE HEADER AND STUB (capture): 60 words @0, 23 words @60.")
        print("  These are the scaffolding; if any code branches, it is here.")
        for base in sorted(cap):
            blk = cap[base]
            if base > 84:
                continue
            print(f"\n    block @{base}, {len(blk)} words")
            hits = collections.Counter()
            for w_ in range(7, 13):
                for lo in range(WORDBITS - w_ + 1):
                    hi = lo + w_ - 1
                    for shift in (0, 1, 2):
                        c = sum(1 for x in blk
                                if base <= (field(x, hi, lo) << shift)
                                < base + len(blk))
                        if 0 < c <= max(3, len(blk) // 6):
                            hits[(hi, lo, shift)] = c
            if not hits:
                print("      no field yields a rare in-extent value")
            for (hi, lo, sh), c in hits.most_common(6):
                vals = sorted({(field(x, hi, lo) << sh) for x in blk
                               if base <= (field(x, hi, lo) << sh) < base + len(blk)})
                print(f"      [{hi:2d}:{lo:2d}]<<{sh}  {c} word(s), values {vals}")


# ----------------------------------------------------------- 3. pconsume

def sec_pconsume(progs):
    print()
    print("=" * 74)
    print("3. THE P-CONSUMER SPLIT -- can any field explain it?")
    print("=" * 74)
    print("FIXED POINT: for class-2 words, P(previous word is class A) is bimodal,")
    print("pinned at 1.000 and 0.000 for many lo12/hi12 values.  If the 7725's")
    print("layout carries over, the SOURCE field (src=`m`/`n`, or the P-select")
    print("field) must be what separates them.  PREDICTION: some field of <=6 bits")
    print("partitions the class-2 words into consumers and non-consumers with")
    print("higher purity than the arbitrary windows tried in round one.\n")

    imgs = sorted({tuple(p) for p in progs.values()}, key=len)
    lab = []   # (word, is_p_consumer)
    for p in imgs:
        for i in range(1, len(p)):
            if ((p[i] >> 20) & 0xF) == 2:
                lab.append((p[i], ((p[i - 1] >> 20) & 0xF) == 0xA))
    base = sum(1 for _, y in lab if y) / len(lab)
    print(f"  {len(lab)} class-2 words with a predecessor; baseline P = {base:.3f}\n")

    rows = []
    for w_ in range(1, 7):
        for lo in range(WORDBITS - w_ + 1):
            hi = lo + w_ - 1
            g = collections.defaultdict(lambda: [0, 0])
            for wd, y in lab:
                v = field(wd, hi, lo)
                g[v][0] += 1
                g[v][1] += y
            # weighted purity: how far from the baseline each group is
            pur = sum(n * max(k / n, 1 - k / n) for n, k in g.values()) / len(lab)
            # count of DECISIVE groups (>=8 words, pinned at 0 or 1)
            dec = sum(n for n, k in g.values()
                      if n >= 8 and (k == 0 or k == n))
            rows.append((pur, dec / len(lab), hi, lo, len(g)))
    rows.sort(reverse=True)
    print("  field      vals   purity   frac of words in DECISIVE groups")
    for pur, dfr, hi, lo, nv in rows[:14]:
        print(f"  [{hi:2d}:{lo:2d}] {nv:6d}  {pur:7.3f}   {dfr:6.3f}")
    print("\n  (purity 1.000 = the field perfectly predicts P-consumption;")
    print(f"   the trivial floor is max(base,1-base) = {max(base,1-base):.3f})")

    # explicit 7725-shaped candidates
    print("\n  Named candidates, 7725 analogues:")
    for name, hi, lo in (("src[7:4]", 7, 4), ("dst[3:0]", 3, 0),
                         ("psel[23:22]", 23, 22), ("psel[33:32]", 33, 32),
                         ("alu[21:18]", 21, 18), ("lo12 lo byte", 7, 0),
                         ("lo12 hi nib", 11, 8)):
        g = collections.defaultdict(lambda: [0, 0])
        for wd, y in lab:
            v = field(wd, hi, lo)
            g[v][0] += 1
            g[v][1] += y
        pur = sum(n * max(k / n, 1 - k / n) for n, k in g.values()) / len(lab)
        print(f"    {name:14s} vals {len(g):3d}  purity {pur:.3f}")

    # is lo12's high nibble a function of its low byte? (published observation)
    print("\n  CONTROL: is lo12[11:8] a function of lo12[7:0]?  (if the low byte")
    print("  were src|dst and the high nibble an independent field, it would not be)")
    m = collections.defaultdict(set)
    for p in imgs:
        for wd in p:
            m[wd & 0xFF].add((wd >> 8) & 0xF)
    multi = {k: v for k, v in m.items() if len(v) > 1}
    print(f"    {len(m)} distinct lo bytes; {len(multi)} map to >1 high nibble")
    for k, v in sorted(multi.items())[:10]:
        print(f"      lo byte {k:02X} -> high nibbles {sorted(v)}")


# ---------------------------------------------------------------- 4. alu

def sec_alu(progs):
    print()
    print("=" * 74)
    print("4. AN ALU-OP FIELD?  Partition quality inside class 2")
    print("=" * 74)
    print("Round one measured that class 2 'does not decompose' at the boundaries")
    print("tried.  PREDICTION: if a 3-5 bit ALU-op field exists, the window that")
    print("holds it scores markedly above its neighbours -- a LOCAL PEAK, not just")
    print("a high number (wide/high-entropy windows always score high).\n")
    imgs = sorted({tuple(p) for p in progs.values()}, key=len)
    c2 = [w for p in imgs for w in p if ((w >> 20) & 0xF) == 2]
    print(f"  {len(c2)} class-2 words, {len(set(c2))} distinct\n")
    for w_ in (3, 4, 5):
        print(f"  width {w_}:")
        sc = [(partition_score(c2, lo + w_ - 1, lo), lo)
              for lo in range(WORDBITS - w_ + 1)]
        for s, lo in sc:
            nv = len(set(field(x, lo + w_ - 1, lo) for x in c2))
            peak = ""
            l_ = [x for x in sc if x[1] == lo - 1]
            r_ = [x for x in sc if x[1] == lo + 1]
            if (not l_ or s > l_[0][0]) and (not r_ or s > r_[0][0]) and s > 0.3:
                peak = "  <-- LOCAL PEAK"
            print(f"    [{lo+w_-1:2d}:{lo:2d}] vals {nv:3d}  score {s:6.3f}{peak}")
        print()


# ---------------------------------------------------------------- 5. top

def sec_top(progs, words):
    print()
    print("=" * 74)
    print("5. TOP BITS AS type + select (the 7725 shape)")
    print("=" * 74)
    print("The 7725 puts a 2-bit TYPE at the very top and P-select below it, and")
    print("the meaning of every lower field depends on TYPE.  PREDICTION: if our")
    print("class4[23:20] is really a TYPE, the distribution of the OTHER fields")
    print("must change qualitatively with it -- not merely shift.\n")
    g = collections.defaultdict(list)
    for w in words:
        g[(w >> 20) & 0xF].append(w)
    print("  class  n     H(hi12)  H(addr8)  H(lo12)  distinct-hi12 shared with class 2")
    c2set = set((x >> 24) & 0xFFF for x in g.get(2, []))
    for c in sorted(g, key=lambda k: -len(g[k])):
        ws = g[c]
        hs = set((x >> 24) & 0xFFF for x in ws)
        print(f"   {c:X}  {len(ws):5d}  {entropy([(x>>24)&0xFFF for x in ws]):7.2f}"
              f"  {entropy([(x>>12)&0xFF for x in ws]):8.2f}"
              f"  {entropy([x&0xFFF for x in ws]):7.2f}"
              f"   {len(hs & c2set):3d}/{len(hs)}")
    print("\n  TYPE-then-SELECT test: split class4 into [23:22] and [21:20] and ask")
    print("  whether the upper pair behaves like a type (gating what the lower means).")
    for hi, lo, nm in ((23, 22, "class4[23:22]"), (21, 20, "class4[21:20]")):
        vals = collections.Counter(field(w, hi, lo) for w in words)
        sc = partition_score(words, hi, lo)
        print(f"    {nm}: {dict(sorted(vals.items()))}  score {sc:.3f}")
    print("\n  Also: the top TWO bits, 7725-style.")
    for hi, lo in ((35, 34), (35, 33), (35, 32)):
        vals = collections.Counter(field(w, hi, lo) for w in words)
        print(f"    [{hi}:{lo}] {dict(sorted(vals.items()))}  "
              f"score {partition_score(words, hi, lo):.3f}")


# --------------------------------------------------------------- 6. cond

def sec_cond(progs, cap):
    print()
    print("=" * 74)
    print("6. A COND FIELD?  small-field value clustering")
    print("=" * 74)
    print("The pin table proves a COND field exists and tests RQ1-RQ3.  If it is a")
    print("small field that is USUALLY the 'always' code, its distribution should be")
    print("heavily dominated by one value with a short tail of others -- and the")
    print("tail should be rarer in straight-line effect bodies than in the header.\n")
    imgs = sorted({tuple(p) for p in progs.values()}, key=len)
    body = [w for p in imgs for w in p]
    hdr = [w for base in cap if base <= 84 for w in cap[base]] if cap else []
    print(f"  bodies {len(body)} words, header+stub {len(hdr)} words\n")
    if not hdr:
        print("  (no capture available; header test skipped)")
    print("  field      body: top val share | header: top val share | ratio of")
    print("                                                          tail rates")
    rows = []
    for w_ in (2, 3, 4):
        for lo in range(WORDBITS - w_ + 1):
            hi = lo + w_ - 1
            cb = collections.Counter(field(w, hi, lo) for w in body)
            sb = cb.most_common(1)[0][1] / len(body)
            if sb < 0.80:
                continue
            if hdr:
                ch = collections.Counter(field(w, hi, lo) for w in hdr)
                sh = ch.most_common(1)[0][1] / len(hdr)
                tail = (1 - sh) / max(1 - sb, 1e-9)
            else:
                sh, tail = float("nan"), float("nan")
            rows.append((tail, hi, lo, sb, sh))
    rows.sort(reverse=True)
    for tail, hi, lo, sb, sh in rows[:12]:
        print(f"  [{hi:2d}:{lo:2d}]  {sb:20.3f} | {sh:19.3f} | {tail:8.2f}")
    if not rows:
        print("  no field is >=80% dominated by a single value")


# --------------------------------------------------------------- driver

def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    rompath, progdir = argv[1], argv[2]
    want = argv[3:] or ["layouts", "branch", "pconsume", "alu", "top", "cond"]
    progs, addrs = E.good_progs(progdir, rompath)
    imgs = sorted({tuple(p) for p in progs.values()}, key=len)
    words = [w for p in imgs for w in p]
    cap = capture_blocks(CAPTURE)
    print(f"corpus: {len(progs)} programs, {len(imgs)} distinct images, "
          f"{len(words)} words, {len(set(words))} distinct")
    print(f"capture blocks: {sorted(cap)}\n")
    if "layouts" in want:
        sec_layouts(progs, words)
    if "branch" in want:
        sec_branch(progs, addrs, cap)
    if "pconsume" in want:
        sec_pconsume(progs)
    if "alu" in want:
        sec_alu(progs)
    if "top" in want:
        sec_top(progs, words)
    if "cond" in want:
        sec_cond(progs, cap)


if __name__ == "__main__":
    main(sys.argv)
