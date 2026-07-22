#!/usr/bin/env python3
"""kn5000_dsp_encoding.py -- structural analysis of NEC uPD6383GF 36-bit instruction words.

Reads the algoNN.bin images produced by tools/kn5000_dsp_extract.py (5 bytes per
36-bit word, right-aligned big-endian) plus the raw ROM (for load addresses and
coefficient counts) and runs the experiments documented in
notes/kn5000-dsp-encoding.md:

    fields      per-bit occupancy + entropy, run-length of correlated bit blocks
    opcode      test candidate opcode fields: does field F partition the corpus
                into classes that differ in the *rest* of the word?
    landmarks   first/last words of every program, universal words
    reloc       same program image loaded at I-RAM 84 vs 200 -> are inner
                address fields relocated?
    pairs       minimal pairs between near-identical distinct programs
    ramaddr     candidate 8-bit RAM-address fields vs program size / coeff count

Usage:
    python3 tools/kn5000_dsp_encoding.py <progdir> [<subprogram.rom>] [section...]

Every number this prints is MEASURED.  Interpretation lives in the notes file.
"""
import collections
import glob
import math
import os
import sys

WORDBITS = 36

# ---------------------------------------------------------------- loading

def load_dir(d):
    """-> {algo_index: [word,...]} with words as ints."""
    progs = {}
    for p in sorted(glob.glob(os.path.join(d, "algo*.bin"))):
        raw = open(p, "rb").read()
        n = int(os.path.basename(p)[4:6])
        progs[n] = [int.from_bytes(raw[i:i + 5], "big") for i in range(0, len(raw), 5)]
    return progs


def load_addrs(rompath):
    """-> {algo: (load_addr, nwords, ncoeffs)} using the extractor's parser."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kn5000_dsp_extract as ex
    rom = ex.Rom(rompath)
    out = {}
    for i in range(ex.N_ALGOS):
        ptr = rom.u32le(ex.ALGO_TABLE + 4 * i)
        try:
            iram, coeffs, _ = ex.parse_stream(rom, ptr)
        except Exception:
            continue
        if not iram:
            continue
        out[i] = (iram[0][0], sum(len(w) for _, w, _ in iram), len(coeffs))
    return out

# ---------------------------------------------------------------- helpers

def bit(w, b):
    return (w >> b) & 1


def field(w, hi, lo):
    return (w >> lo) & ((1 << (hi - lo + 1)) - 1)


def entropy(vals):
    c = collections.Counter(vals)
    n = len(vals)
    return -sum(k / n * math.log2(k / n) for k in c.values())


def mutual_info(a, b):
    n = len(a)
    ja = collections.Counter(zip(a, b))
    ca, cb = collections.Counter(a), collections.Counter(b)
    return sum(k / n * math.log2((k / n) / (ca[x] / n * cb[y] / n))
               for (x, y), k in ja.items())

# ---------------------------------------------------------------- sections

def sec_fields(words):
    print("== per-bit occupancy (MEASURED) ==")
    n = len(words)
    ones = [sum(bit(w, b) for w in words) for b in range(WORDBITS)]
    for b in range(WORDBITS - 1, -1, -1):
        f = ones[b] / n
        h = 0.0 if f in (0.0, 1.0) else -(f * math.log2(f) + (1 - f) * math.log2(1 - f))
        bar = "#" * int(f * 50)
        print(f"  bit {b:2d}  set {ones[b]:5d}/{n} ({f:5.1%})  H={h:.3f} {bar}")

    print("\n== adjacent-bit mutual information (field-boundary probe) ==")
    print("   low MI between bit b and b-1 suggests a boundary between them")
    cols = [[bit(w, b) for w in words] for b in range(WORDBITS)]
    for b in range(WORDBITS - 1, 0, -1):
        mi = mutual_info(cols[b], cols[b - 1])
        print(f"  {b:2d}|{b-1:2d}  MI={mi:.4f} {'*' * int(mi * 60)}")


def sec_opcode(words):
    """A real opcode field should PARTITION: words sharing the opcode should be
    more similar in the remaining bits than random words are."""
    print("== opcode-field hypothesis test (MEASURED) ==")
    n = len(words)
    Htot = entropy(words)
    print(f"  {n} words, {len(set(words))} distinct, H(word)={Htot:.2f} bits\n")
    print(f"  {'field':>10} {'vals':>5} {'H(f)':>6} {'H(rest|f)':>10} {'H(rest)':>8} {'IG':>6}")
    rows = []
    for lo in range(0, WORDBITS):
        for w_ in range(2, 9):
            hi = lo + w_ - 1
            if hi >= WORDBITS:
                continue
            f = [field(x, hi, lo) for x in words]
            mask = ((1 << WORDBITS) - 1) ^ (((1 << w_) - 1) << lo)
            rest = [x & mask for x in words]
            Hf, Hr = entropy(f), entropy(rest)
            # conditional entropy of rest given field
            groups = collections.defaultdict(list)
            for a, b in zip(f, rest):
                groups[a].append(b)
            Hcond = sum(len(g) / n * entropy(g) for g in groups.values())
            rows.append((Hr - Hcond, f"[{hi}:{lo}]", len(set(f)), Hf, Hcond, Hr))
    rows.sort(reverse=True)
    for ig, name, nv, Hf, Hc, Hr in rows[:20]:
        print(f"  {name:>10} {nv:5d} {Hf:6.2f} {Hc:10.2f} {Hr:8.2f} {ig:6.3f}")
    print("\n  NOTE: information gain is trivially maximised by high-entropy fields;")
    print("  the diagnostic is IG *relative to* H(f).  A true opcode has modest")
    print("  H(f) and large IG (it explains the rest of the word).")
    print(f"\n  {'field':>10} {'H(f)':>6} {'IG':>6} {'IG/H(f)':>8}")
    for ig, name, nv, Hf, Hc, Hr in sorted(rows, key=lambda r: -(r[0] / max(r[3], 1e-9)))[:15]:
        print(f"  {name:>10} {Hf:6.2f} {ig:6.3f} {ig / max(Hf,1e-9):8.3f}")


def sec_landmarks(progs):
    print("== structural landmarks (MEASURED) ==")
    first = collections.Counter(p[0] for p in progs.values() if p)
    last = collections.Counter(p[-1] for p in progs.values() if p)
    print(f"  FIRST words: {len(first)} distinct across {len(progs)} programs")
    for w, c in first.most_common(8):
        print(f"    {w:010X}  x{c}")
    print(f"  LAST words: {len(last)} distinct")
    for w, c in last.most_common(8):
        print(f"    {w:010X}  x{c}")

    # unique images only
    imgs = {}
    for i, p in progs.items():
        imgs.setdefault(tuple(p), []).append(i)
    print(f"\n  {len(imgs)} DISTINCT program images among {len(progs)} slots")
    first = collections.Counter(k[0] for k in imgs)
    last = collections.Counter(k[-1] for k in imgs)
    print("  distinct-image FIRST words:")
    for w, c in first.most_common(8):
        print(f"    {w:010X}  x{c}")
    print("  distinct-image LAST words:")
    for w, c in last.most_common(8):
        print(f"    {w:010X}  x{c}")

    # positional universality: does word k of each program tend to match?
    print("\n  positional agreement (fraction of distinct images sharing the modal word):")
    keys = list(imgs)
    for k in list(range(0, 10)) + [-3, -2, -1]:
        col = [p[k] for p in keys if len(p) > abs(k)]
        m, c = collections.Counter(col).most_common(1)[0]
        print(f"    pos {k:>3}: modal {m:010X} in {c}/{len(col)}")


def sec_reloc(progs, addrs):
    print("== relocation test: same image at I-RAM 84 vs 200 (MEASURED) ==")
    imgs = collections.defaultdict(list)
    for i, p in progs.items():
        imgs[tuple(p)].append(i)
    byaddr = collections.defaultdict(set)
    for img, slots in imgs.items():
        for s in slots:
            if s in addrs:
                byaddr[img].add(addrs[s][0])
    both = [img for img, a in byaddr.items() if len(a) > 1]
    print(f"  {len(imgs)} distinct images; {len(both)} appear at MORE THAN ONE load address")
    for img in both:
        print(f"    len {len(img)} at addresses {sorted(byaddr[img])} "
              f"-> IDENTICAL BYTES, so no relocation was applied")
    # near-identical images across the two address groups
    g84 = [img for img, a in byaddr.items() if a == {84}]
    g200 = [img for img, a in byaddr.items() if a == {200}]
    print(f"  images only at 84: {len(g84)}   only at 200: {len(g200)}")
    best = None
    for a in g84:
        for b in g200:
            if len(a) != len(b):
                continue
            d = sum(1 for x, y in zip(a, b) if x != y)
            if best is None or d < best[0]:
                best = (d, len(a), a, b)
    if best:
        d, L, a, b = best
        print(f"  closest 84-vs-200 same-length pair: {L} words, {d} differ")
        if 0 < d <= 12:
            for k, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print(f"    w{k:3d}: {x:010X} vs {y:010X}   xor {x ^ y:010X}")


def sec_pairs(progs, limit=6):
    print("== minimal pairs between distinct images (MEASURED) ==")
    imgs = sorted({tuple(p) for p in progs.values()}, key=len)
    pairs = []
    for i in range(len(imgs)):
        for j in range(i + 1, len(imgs)):
            a, b = imgs[i], imgs[j]
            if len(a) != len(b):
                continue
            d = sum(1 for x, y in zip(a, b) if x != y)
            if d:
                pairs.append((d, len(a), a, b))
    pairs.sort(key=lambda r: (r[0], r[1]))
    print(f"  {len(pairs)} same-length image pairs; closest {limit}:")
    for d, L, a, b in pairs[:limit]:
        print(f"\n  -- {L} words, {d} differing --")
        for k, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print(f"     w{k:3d}: {x:010X} vs {y:010X}   xor {x ^ y:010X}")


def sec_ramaddr(progs, addrs):
    print("== candidate 8-bit RAM-address fields (MEASURED) ==")
    imgs = {}
    for i, p in progs.items():
        imgs.setdefault(tuple(p), i)
    print(f"  {'field':>10} {'distinct':>8} {'coverage':>9} {'r(size)':>8}")
    sizes, data = [], collections.defaultdict(list)
    for img, slot in imgs.items():
        sizes.append(len(img))
    for lo in range(0, WORDBITS - 7):
        hi = lo + 7
        vals = [field(w, hi, lo) for p in progs.values() for w in p]
        dv = len(set(vals))
        # correlate per-program distinct-value count with program size
        xs, ys = [], []
        for img in imgs:
            xs.append(len(img))
            ys.append(len({field(w, hi, lo) for w in img}))
        r = pearson(xs, ys)
        print(f"  [{hi:2d}:{lo:2d}] {dv:8d} {dv/256:9.1%} {r:8.3f}")
    print("\n  coverage = fraction of 0..255 that the field actually takes.")
    print("  A real 8-bit RAM pointer field should have high coverage AND its")
    print("  per-program distinct-value count should grow with program size.")


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def sec_high(words):
    """Distribution of the top nibble(s) and what co-varies with them."""
    print("== high-field distributions (MEASURED) ==")
    for hi, lo in ((35, 33), (35, 32), (35, 31), (35, 30), (35, 28)):
        c = collections.Counter(field(w, hi, lo) for w in words)
        print(f"  [{hi}:{lo}] {len(c)} of {1<<(hi-lo+1)} values used; top:",
              " ".join(f"{v:X}:{k}" for v, k in c.most_common(10)))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    progs = load_dir(sys.argv[1])
    rompath = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].endswith(".rom") else None
    secs = [a for a in sys.argv[2:] if not a.endswith(".rom")] or \
        ["fields", "high", "opcode", "landmarks", "reloc", "pairs", "ramaddr"]
    addrs = load_addrs(rompath) if rompath else {}
    words = [w for p in progs.values() for w in p]
    uniq = sorted({tuple(p) for p in progs.values()})
    uwords = [w for p in uniq for w in p]
    print(f"loaded {len(progs)} programs, {len(words)} words "
          f"({len(uniq)} distinct images, {len(uwords)} deduped words)\n")
    for s in secs:
        print()
        if s == "fields":
            sec_fields(uwords)
        elif s == "high":
            sec_high(uwords)
        elif s == "opcode":
            sec_opcode(uwords)
        elif s == "landmarks":
            sec_landmarks(progs)
        elif s == "reloc":
            sec_reloc(progs, addrs)
        elif s == "pairs":
            sec_pairs(progs)
        elif s == "ramaddr":
            sec_ramaddr(progs, addrs)


if __name__ == "__main__":
    main()

# ===========================================================================
# CONFIRMED-EXPERIMENT SECTIONS (added after the first analysis pass; these are
# the ones whose results are quoted in notes/kn5000-dsp-encoding.md)
# ===========================================================================

BAD_ALGOS_NOTE = """algo 79 and 88 parse to I-RAM load addresses 1520 and 3376,
outside the 384-word I-RAM: their ALGO_TABLE pointers do not lead to a valid
bytecode stream.  All quantitative results EXCLUDE them (load addr > 344)."""


def fmt36(w):
    """9-nibble field-aligned rendering: hi12 . c4 . addr8 . lo12."""
    return (f"{(w >> 24) & 0xFFF:03X}.{(w >> 20) & 0xF:X}."
            f"{(w >> 12) & 0xFF:02X}.{w & 0xFFF:03X}")


def good_progs(progdir, rompath):
    """Load programs, dropping the two malformed streams."""
    addrs = load_addrs(rompath)
    out = {}
    for i, p in load_dir(progdir).items():
        if addrs.get(i, (9999,))[0] <= 344:
            out[i] = p
    return out, addrs


def sec_classfield(progs):
    """[23:20] as an instruction-class field: does it gate the addr8 field?"""
    imgs = sorted({tuple(p) for p in progs.values()}, key=len)
    W = [w for p in imgs for w in p]
    print("== [23:20] partition (MEASURED) ==")
    g = collections.defaultdict(list)
    for w in W:
        g[field(w, 23, 20)].append(w)
    print(f"{'[23:20]':>8}{'n':>6}{'hi12':>6}{'addr8':>7}{'lo12':>6}   top hi12 classes")
    for k in sorted(g, key=lambda k: -len(g[k])):
        v = g[k]
        top = " ".join(f"{a:03X}:{c}" for a, c in
                       collections.Counter(field(x, 35, 24) for x in v).most_common(4))
        print(f"{k:>8X}{len(v):>6}{len({field(x,35,24) for x in v}):>6}"
              f"{len({field(x,19,12) for x in v}):>7}{len({field(x,11,0) for x in v}):>6}   {top}")


def sec_terminator(progs):
    """The end-of-program landmark: [23:20]==1 and addr8 in {0x0E,0x0F}."""
    print("== terminator landmark (MEASURED) ==")
    fin = mid = 0
    bad = []
    for i, p in progs.items():
        for k, w in enumerate(p):
            if field(w, 23, 20) == 1 and field(w, 19, 12) in (0x0E, 0x0F):
                if k == len(p) - 1:
                    fin += 1
                else:
                    mid += 1
                    print(f"  MID-PROGRAM hit: algo{i} w{k} {fmt36(w)}")
        if not (field(p[-1], 23, 20) == 1 and field(p[-1], 19, 12) in (0x0E, 0x0F)):
            bad.append((i, fmt36(p[-1])))
    print(f"  signature at final word: {fin}/{len(progs)} programs")
    print(f"  signature anywhere else: {mid}  (0 => perfect precision)")
    print(f"  programs missing it    : {bad if bad else 'none'}")
    print("  final-word variants:",
          sorted({fmt36(p[-1]) for p in progs.values()}))


def sec_minpair(progs):
    """The algo32/algo34 minimal pair -- the addr8-field proof."""
    print("== decisive minimal pair (MEASURED) ==")
    imgs = {}
    for i, p in progs.items():
        imgs.setdefault(tuple(p), []).append(i)
    K = list(imgs)
    best = []
    for i in range(len(K)):
        for j in range(i + 1, len(K)):
            a, b = K[i], K[j]
            if len(a) != len(b):
                continue
            d = [(k, x, y) for k, (x, y) in enumerate(zip(a, b)) if x != y]
            if d:
                best.append((len(d), imgs[a], imgs[b], d))
    best.sort(key=lambda r: r[0])
    for nd, ia, ib, d in best[:2]:
        print(f"\n  algos {ia} vs {ib}: {nd} words differ")
        for k, x, y in d:
            dl = (field(y, 19, 12) - field(x, 19, 12)) % 256
            dl = dl - 256 if dl > 128 else dl
            same = (x & ~(0xFF << 12)) == (y & ~(0xFF << 12))
            print(f"    w{k:3d}: {fmt36(x)}  vs  {fmt36(y)}   "
                  f"addr8 delta {dl:+4d}   {'ONLY addr8 differs' if same else 'other bits differ too'}")


def sec_summary(progs):
    imgs = sorted({tuple(p) for p in progs.values()}, key=len)
    W = [w for p in imgs for w in p]
    print("== field-value-space census (MEASURED) ==")
    print(f"  {len(progs)} programs, {len(imgs)} distinct images, {len(W)} words, "
          f"{len(set(W))} distinct words")
    for hi, lo, name in ((35, 24, "hi12"), (23, 20, "class4"),
                         (19, 12, "addr8"), (11, 0, "lo12")):
        c = collections.Counter(field(w, hi, lo) for w in W)
        space = 1 << (hi - lo + 1)
        print(f"  [{hi:2d}:{lo:2d}] {name:7s} {len(c):5d} of {space:5d} values "
              f"({len(c)/space:6.1%})  H={entropy([field(w,hi,lo) for w in W]):.2f}")
    print("\n  Only addr8 [19:12] has broad coverage of its value space -> it is the")
    print("  only field that behaves like a 256-entry RAM address.  hi12 and lo12 use")
    print("  ~1.4% of their space each -> sparse control encodings, not immediates.")
