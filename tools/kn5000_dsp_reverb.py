#!/usr/bin/env python3
"""kn5000_dsp_reverb.py -- read the KN5000 reverb the way a reverb is built.

Companion to tools/kn5000_dsp_extract.py (ALGO_TABLE microcode) and
tools/kn5000_dsp_coeffs.py (PARAM_TABLE coefficient/parameter streams).  Neither
of those is rewritten here; both are imported.

The premise (Felipe Sanches, 2026-07-22): bit statistics cannot yield semantics,
but a *reverb has a known structure*.  If the 133-word microprogram shared by the
twelve reverb presets contains a repeating motif, that motif is very likely a
comb or all-pass stage, and whatever varies alongside it is a delay length and a
gain.  Structure -> meaning.

Findings are written up in notes/kn5000-dsp-reverb.md.  Sections:

    motif    find maximal repeating instruction motifs in a program, and count
             their occurrences across the whole 96-program corpus (the CONTROL:
             a motif that also appears in the compressor is not a comb)
    delays   the reverb presets carry no mode-0x0B delay entries.  This finds
             where their delay lengths actually live: the op-5 mode-0x0A stream
             is a sequence of (end, start) DRAM ADDRESS PAIRS that tile the
             external delay arena into contiguous segments.
    order    the falsifiable test -- ROOM < PLATE < CONCERT < WAVE by arena size
    primes   the mutual-primality / ratio tests on the recovered tap sets

Usage:
    python3 tools/kn5000_dsp_reverb.py <subprogram.rom> <progdir> [--names <mainrom>]
where <progdir> is the output of kn5000_dsp_extract.py.
"""
import collections
import glob
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_coeffs as C  # noqa: E402

FS = 48000.0                    # see notes/kn5000-dsp-coefficients.md sect. 3.1
REVERB_SLOTS = list(range(16, 28))
GATED_SLOT = 8

# ------------------------------------------------------------------ words


def load_progs(d):
    progs = {}
    for p in sorted(glob.glob(os.path.join(d, "algo*.bin"))):
        raw = open(p, "rb").read()
        n = int(os.path.basename(p)[4:6])
        progs[n] = [int.from_bytes(raw[i:i + 5], "big")
                    for i in range(0, len(raw), 5)]
    return progs


def fields(w):
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def fmt(w):
    hi, c, a, lo = fields(w)
    return f"{hi:03X}.{c:X}.{a:02X}.{lo:03X}"


def dump(words, title=""):
    print(f"--- {title} ({len(words)} words) ---")
    for i, w in enumerate(words):
        print(f"{i:>4}  {fmt(w)}")


# ------------------------------------------------------------------ motif

def best_motif(words, minlen=3):
    """Longest instruction sequence that occurs >=2 times (non-overlapping-ish).

    Returns (motif, [start indices]).  Ties broken by occurrence count.
    """
    best = (0, 0, None)
    n = len(words)
    for ln in range(minlen, n // 2 + 1):
        seen = collections.defaultdict(list)
        for i in range(n - ln + 1):
            seen[tuple(words[i:i + ln])].append(i)
        for k, idx in seen.items():
            if len(idx) < 2:
                continue
            # keep only non-overlapping starts
            keep, last = [], -10 ** 9
            for i in idx:
                if i - last >= ln:
                    keep.append(i)
                    last = i
            if len(keep) < 2:
                continue
            score = ln * len(keep)
            if score > best[0]:
                best = (score, ln, (list(k), keep))
    return best[2]


def motif_control(progs, motif, names=None):
    """MANDATORY CONTROL: how many *other* programs contain this motif?"""
    m = list(motif)
    ln = len(m)
    hits = {}
    for n, w in sorted(progs.items()):
        c = sum(1 for i in range(len(w) - ln + 1) if w[i:i + ln] == m)
        if c:
            hits[n] = c
    return hits


# ------------------------------------------------------------------ delays

def addr_pairs(parsed):
    """The op-5 mode-0x0A payload sequence, taken pairwise.

    MEASURED shape: [(end0,start0), (end1,start1), ...].
    """
    v = [p for op, m, p, sel in parsed["entries"] if op == 5 and m == 0x0A]
    return [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]


def chains(pairs):
    """Split the pair list into maximal runs where start_k == end_{k-1}.

    A run is a set of delay buffers tiling DRAM contiguously.  Returns
    [[(start,end),...], ...] in emission order, taking every other pair
    (the stream interleaves two independent chains).
    """
    out = []
    for phase in (0, 1):
        sub = pairs[phase::2]
        cur = []
        for end, start in sub:
            if end <= start:                    # not an ascending segment
                if len(cur) >= 2:
                    out.append(cur)
                cur = []
                continue
            if cur and cur[-1][1] != start:
                if len(cur) >= 2:
                    out.append(cur)
                cur = []
            cur.append((start, end))
        if len(cur) >= 2:
            out.append(cur)
    return out


def taps(parsed):
    """-> (list of chains, each a list of segment lengths)."""
    return [[e - s for s, e in ch] for ch in chains(addr_pairs(parsed))]


# ------------------------------------------------------------------ tests

def coprime_report(vals):
    vals = [v for v in vals if v > 0]
    if len(vals) < 2:
        return "n/a"
    bad = [(a, b, math.gcd(a, b)) for i, a in enumerate(vals)
           for b in vals[i + 1:] if math.gcd(a, b) > 1]
    npairs = len(vals) * (len(vals) - 1) // 2
    g = 0
    for v in vals:
        g = math.gcd(g, v)
    return (f"{npairs - len(bad)}/{npairs} pairs coprime, overall gcd {g}, "
            f"ratio max/min {max(vals)/min(vals):.2f}")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    rompath, progdir = sys.argv[1], sys.argv[2]
    rom = C.Rom(rompath)
    A = C.load_all(rom)
    progs = load_progs(progdir)
    names = {}
    if "--names" in sys.argv:
        try:
            names = C.effect_names(sys.argv[sys.argv.index("--names") + 1])
        except Exception:
            names = {}
    nm = (lambda i: names.get(i, f"algo{i}"))

    # ---- 1. the motif -------------------------------------------------
    print("=" * 72)
    print("1. REPEATING MOTIF in the 133-word reverb program (algo 20)")
    print("=" * 72)
    w20 = progs[20]
    mot = best_motif(w20)
    m, idx = mot
    print(f"motif length {len(m)}, {len(idx)} non-overlapping occurrences "
          f"at {idx}")
    for k in m:
        print("     ", fmt(k))
    varying = "none (all occurrences byte-identical)"
    print(f"fields varying between occurrences: {varying}")

    print("\nCONTROL -- which of the 96 programs contain this exact motif?")
    hits = motif_control(progs, m)
    for n, c in sorted(hits.items()):
        print(f"   algo {n:>2} {nm(n):<18} {len(progs[n]):>4} words   x{c}")
    print(f"   -> {len(hits)} of {len(progs)} programs")

    # ---- 2. delay taps ------------------------------------------------
    print()
    print("=" * 72)
    print("2. DELAY TAPS -- op-5 mode-0x0A pairs tile the external DRAM arena")
    print("=" * 72)
    for s in REVERB_SLOTS + [GATED_SLOT]:
        ch = chains(addr_pairs(A[s]))
        print(f"\nslot {s:>2} {nm(s)}")
        for j, c in enumerate(ch):
            lens = [e - st for st, e in c]
            print(f"   chain {j}: base 0x{c[0][0]:04X}..0x{c[-1][1]:04X}  "
                  f"{len(lens)} segments")
            print(f"      lengths {lens}")
            print(f"      ms@48k  {[round(x/FS*1000,2) for x in lens]}")
            print(f"      {coprime_report(lens)}")

    # ---- 3. the size-ordering test ------------------------------------
    print()
    print("=" * 72)
    print("3. FALSIFIABLE TEST -- arena size must order ROOM < PLATE < "
          "CONCERT < WAVE")
    print("=" * 72)
    rows = []
    for s in REVERB_SLOTS:
        ch = chains(addr_pairs(A[s]))
        tot = sum(e - st for c in ch for st, e in c)
        big = max((sum(e - st for st, e in c) for c in ch), default=0)
        rows.append((tot, big, s))
    for tot, big, s in sorted(rows):
        print(f"   {nm(s):<18} total {tot:>6} words  ({tot/FS*1000:7.1f} ms)")

    # ---- 4. the alternative "one partition" reading --------------------
    print()
    print("=" * 72)
    print("4. ALTERNATIVE READING -- all boundaries merged into one partition")
    print("=" * 72)
    for s in (20, 8):
        b = sorted({x for c in chains(addr_pairs(A[s])) for p in c for x in p})
        d = [b[i + 1] - b[i] for i in range(len(b) - 1)]
        print(f"   slot {s:>2} {nm(s)}")
        print(f"      boundaries {[hex(x) for x in b]}")
        print(f"      elementary segments {d}")
        print(f"      {coprime_report(d)}")

    # ---- 5. control: does the address-chain shape occur outside reverb? -
    print()
    print("=" * 72)
    print("5. CONTROL -- contiguous (end,start) chains of >=3 segments, "
          "all 100 slots")
    print("=" * 72)
    yes, no = [], []
    for s in range(C.N_ALGOS):
        n = nm(s)
        if n.startswith("---") or n == "NO OPERATION":
            continue
        ch = [c for c in chains(addr_pairs(A[s])) if len(c) >= 3]
        (yes if ch else no).append(n)
    print(f"   DETECTED  ({len(set(yes))} distinct): {sorted(set(yes))}")
    print(f"   not found ({len(set(no))} distinct effects)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
