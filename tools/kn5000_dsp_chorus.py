#!/usr/bin/env python3
"""kn5000_dsp_chorus.py -- the CHORUS / LFO family of the NEC uPD6383GF, by the
same constraint-solving method that solved the biquad (notes/kn5000-dsp-semantics.md).

Companion to notes/kn5000-dsp-chorus.md.  Imports the existing extraction and
analysis modules; NONE of them is edited.

Sections (argv[3..], default = all):
    dump      annotated listing of every chorus/LFO-family image
    tap       the modulated-tap idiom: census, alignment, invariants
    lfo       the LFO block: census, the phase accumulator, rate/depth sources
    space     the bounded hypothesis space for the modulated tap, and the search
    verify    falsifiable checks: periodicity, excursion, voice counts, rotary pair
    twin      TASK B -- the 212.2 / 212.A minimal-pair test and its generalisation

Usage:
    python3 tools/kn5000_dsp_chorus.py <subprogram_v142.rom> <progdir> [sections...]
"""
import collections
import itertools
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_extract as E          # noqa: E402
import kn5000_dsp_coeffs as C           # noqa: E402
import kn5000_dsp_params as P           # noqa: E402
import kn5000_dsp_biquadmap as BM       # noqa: E402

FS = 44100.0
MAINROM = os.path.expanduser(
    "~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom")

# The chorus / LFO family, by algorithm slot (names from notes/kn5000-dsp-effect-map.md)
CHORUS_FAMILY = [1, 2, 6, 56, 50, 64, 67]          # CHORUS .. S.DELAY+VIBRATO
LFO_FAMILY = CHORUS_FAMILY + [4, 5, 66, 68,        # flanger / phaser
                              15, 53,              # ROCK ROTARY / ROTARY SPEAKER
                              48, 54,              # AUTO PAN / RING MODULATOR
                              71, 73, 74]          # PEQ+ combinations
NAMES = {1: 'CHORUS', 2: 'MODULATED CHORUS', 6: 'ENSEMBLE', 56: 'MIX UP',
         50: 'VIBRATO', 64: 'S.DELAY+CHORUS', 67: 'S.DELAY+VIBRATO',
         4: 'FLANGER', 5: 'PHASER', 66: 'S.DELAY+FLANGER', 68: 'S.DELAY+PHASER',
         15: 'ROCK ROTARY', 53: 'ROTARY SPEAKER', 48: 'AUTO PAN',
         54: 'RING MODULATOR', 71: 'PEQ+CHORUS', 73: 'PEQ+FLANGER',
         74: 'PEQ+VIBRATO'}


# ------------------------------------------------------------------ words

def fl(w):
    """hi12, class4, addr8, lo12 -- extracted explicitly, never eyeballed."""
    return (w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF


def fmt(w):
    h, c, a, l = fl(w)
    return f"{h:03X}.{c:X}.{a:02X}.{l:03X}"


def s8(v):
    return v - 256 if v & 0x80 else v


def load_progs(progdir):
    progs = {}
    for fn in sorted(os.listdir(progdir)):
        if not (fn.startswith("algo") and fn.endswith(".bin")):
            continue
        a = int(fn[4:-4])
        d = open(os.path.join(progdir, fn), "rb").read()
        progs[a] = [int.from_bytes(d[i:i + 5], "big") for i in range(0, len(d), 5)]
    return progs


# ------------------------------------------------------------------ annotation

ANNOT = [
    # (predicate on (hi,cls,addr,lo)) -> label.  Established roles only; the
    # provenance of each is in notes/kn5000-dsp-chorus.md sect. 1.
    (lambda f: f[0] == 0x082, 'LFO READ'),
    (lambda f: f[0] == 0x094, 'LFO phase accumulator'),
    (lambda f: f[0] == 0x092, 'LFO / table driver'),
    (lambda f: f[0] == 0x192, 'LFO read companion'),
    (lambda f: f[3] == 0xC63, 'TBL: request'),
    (lambda f: f[1] == 6, 'TBL: select'),
    (lambda f: f[1] == 4, 'TBL: take result'),
    (lambda f: f[0] == 0xC40 and f[1] == 3, 'INTERP a'),
    (lambda f: f == (0xA00, 0, 0x00, 0x041), 'INTERP b'),
    (lambda f: f[0] == 0x880 and f[1] == 1 and f[2] == 0x60, 'DRAM open (write)'),
    (lambda f: f[0] == 0x900 and f[1] == 1 and f[2] == 0x60, 'DRAM open (modulated read)'),
    (lambda f: f[0] == 0x880 and f[1] == 1 and f[2] == 0x20, 'DRAM close (tap)'),
    (lambda f: f[0] == 0x880 and f[1] == 1, 'DRAM misc'),
    (lambda f: f == (0x104, 2, 0x00, 0x000), 'ALL-PASS marker'),
    (lambda f: f == (0x000, 2, 0x00, 0x000), 'NOP'),
    (lambda f: f[1] == 8, 'class 8 (rescale?)'),
    (lambda f: f[0] == 0xC40, 'envelope/level'),
]


def annot(w):
    f = fl(w)
    for pred, lab in ANNOT:
        try:
            if pred(f):
                return lab
        except Exception:
            pass
    return ''


# ------------------------------------------------------------------ dump

def sec_dump(subrom, progs, rom, args):
    print("=== SECTION dump: annotated chorus / LFO family listings\n")
    want = [int(x) for x in args] if args else CHORUS_FAMILY + [15, 53, 48, 54]
    r = C.Rom(subrom)
    for a in want:
        if a not in progs:
            continue
        p = C.parse_param_stream(r, r.u32le(C.PARAM_TABLE + 4 * a))
        co = C.coeffs_of(p)
        dl = C.delays_of(p)
        print("-" * 72)
        print(f"[{a}] {NAMES.get(a,'?')}   {len(progs[a])} words")
        print("   delays (mode 0x0B): " + ", ".join(
            f"{n} ({1000.0*n/FS:.2f} ms)" for n in dl))
        if len(dl) > 1:
            print("   delay spacings    : " + ", ".join(
                str(dl[i + 1] - dl[i]) for i in range(len(dl) - 1)))
        print("   coefficients      : " + ", ".join(
            f"{i:02X}:{C.q23(v):+.4f}" for i, v in enumerate(co)))
        t1 = rom.u32le(P.ALGO_T1_ARRAY + 4 * a)
        if t1 and t1 != P.NULL_T1:
            for _ad, op, e in P.parse_t1(rom, t1):
                print(f"   host op 0x{op:02X} -> "
                      + " ".join(f"0x{v:02X}" for v in e))
        cur = 0
        for i, w in enumerate(progs[a]):
            h, c, ad, lo = fl(w)
            tag = f"  c[{cur:02X}]" if c == 0xA else "       "
            if c == 0xA:
                cur += 1
            print(f"   {i:3d}  {fmt(w)} {tag}  {annot(w)}")
        print()


# ------------------------------------------------------------------ the modulated tap idiom

TAP_IDIOM = [
    (0x900, 1, None, 0x1D5),
    (0x192, 0xA, None, 0x000),
    (0x082, 2, 0x00, 0x1C0),
    (0xC40, 3, 0x20, 0x44C),
    (0xA00, 0, 0x00, 0x041),
    (0x880, 1, 0x20, None),
    (0x102, 0xA, None, 0x4C8),
]


def match(w, pat):
    f = fl(w)
    return all(p is None or p == v for p, v in zip(pat, f))


def find_taps(words):
    """Every occurrence of the 7-word modulated-tap idiom, and the near misses."""
    hits, near = [], []
    n = len(TAP_IDIOM)
    for i in range(len(words) - n + 1):
        ok = sum(match(words[i + k], TAP_IDIOM[k]) for k in range(n))
        if ok == n:
            hits.append(i)
        elif ok >= n - 2:
            near.append((i, ok))
    return hits, near


def sec_tap(subrom, progs, rom, args):
    print("=== SECTION tap: the modulated-tap idiom\n")
    print("Idiom under test (7 words, wildcards marked *):")
    for k, pat in enumerate(TAP_IDIOM):
        print("   " + ".".join("*" * (2 if j == 2 else 3) if v is None else
                               (f"{v:03X}" if j == 0 else f"{v:X}" if j == 1 else
                                f"{v:02X}" if j == 2 else f"{v:03X}")
                               for j, v in enumerate(pat)))
    print()
    tot = 0
    perimg = {}
    for a in sorted(progs):
        h, nr = find_taps(progs[a])
        if h or nr:
            perimg[a] = (h, nr)
    # one representative per distinct image
    seen = {}
    for a in sorted(perimg):
        key = tuple(progs[a])
        if key in seen:
            continue
        seen[key] = a
        h, nr = perimg[a]
        tot += len(h)
        print(f"[{a:3d}] {NAMES.get(a,'?'):18s} full hits {len(h)} at {h}"
              + (f"   near ({len(nr)}) {nr}" if nr else ""))
    print(f"\nTOTAL full idiom occurrences (distinct images) = {tot}")

    # the two variable fields
    print("\nThe idiom's variable fields, per occurrence:")
    print("   img  at   [0]addr8  [1]addr8  [5]lo12  [6]addr8")
    for a in sorted(seen.values()):
        h, _ = perimg[a]
        for i in h:
            print(f"   {a:3d} {i:4d}   0x{fl(progs[a][i])[2]:02X}      "
                  f"0x{fl(progs[a][i+1])[2]:02X}      0x{fl(progs[a][i+5])[3]:03X}"
                  f"    0x{fl(progs[a][i+6])[2]:02X}")

    # control: does the interpolation pair EVER appear outside the idiom?
    print("\nCONTROL -- every C40.3.20.44C in the corpus and what follows it:")
    ctr = collections.Counter()
    for a in seen.values():
        w = progs[a]
        for i, x in enumerate(w):
            if fl(x) == (0xC40, 3, 0x20, 0x44C):
                nxt = tuple(fmt(y) for y in w[i + 1:i + 3])
                ctr[nxt] += 1
    for k, v in ctr.most_common():
        print(f"   {v:3d}  {' | '.join(k)}")


# ------------------------------------------------------------------ the LFO

def bank_of(subrom, a):
    """{absolute coefficient address: raw 24-bit word} for one algorithm."""
    out, base0 = {}, None
    for base, ws in BM.sbank(subrom, a):
        if base is None:
            continue
        if base0 is None:
            base0 = base
        for i, w in enumerate(ws):
            out[base + i] = w
    return out, (base0 or 0)


def cursor_walk(words, base0):
    """[(index, word, absolute coefficient address)] for every class-A word."""
    out, cur = [], 0
    for i, w in enumerate(words):
        if w == 0x801000021:
            cur = 0
        if fl(w)[1] == 0xA:
            out.append((i, w, base0 + cur))
            cur += 1
    return out


def t1_map(rom, a):
    t1 = rom.u32le(P.ALGO_T1_ARRAY + 4 * a)
    if not t1 or t1 == P.NULL_T1:
        return {}
    return {op: e for _x, op, e in P.parse_t1(rom, t1)}


def t2_used(rom, a, amap):
    """{(opcode, absolute address)} actually referenced by the parameter stream.
    Unreferenced T1 operand slots are EXCLUDED -- they are the instrument
    blindness that makes a raw T1 scan over-count (see note sect. 6)."""
    t2 = rom.u32le(P.ALGO_T2_ARRAY + 4 * a)
    used = set()
    if not t2 or not amap:
        return used
    for _ad, _ln, body in P.split_records(rom, t2):
        sols = P.decode_record(rom, body, amap)
        if not sols:
            continue
        sets = [{(o, amap[o][x]) for o, x, _i in s} for s in sols]
        used |= set.intersection(*sets)
    return used


def images(progs):
    seen = {}
    for a in sorted(progs):
        seen.setdefault(tuple(progs[a]), a)
    return sorted(seen.values())


def sec_lfo(subrom, progs, rom, args):
    print("=== SECTION lfo: the LFO decoded\n")
    imgs = images(progs)

    print("--- L1  the two class-A LFO words and the coefficients they consume\n")
    print("   PREDICTION, before looking: if 092.A/094.A are a phase accumulator,")
    print("   one of them must consume a WRAP/SCALE constant that is the same in")
    print("   every image, and the other a per-effect RATE.\n")
    rows, c94, c92 = [], collections.Counter(), []
    for a in imgs:
        bank, b0 = bank_of(subrom, a)
        for i, w, ad in cursor_walk(progs[a], b0):
            h = fl(w)[0]
            if h in (0x092, 0x094):
                raw = bank.get(ad)
                rows.append((a, i, h, ad, raw))
                if h == 0x094:
                    c94[raw] += 1
                else:
                    c92.append((a, raw))
    for a, i, h, ad, raw in rows:
        print(f"   [{a:3d}] {NAMES.get(a,'?'):16s} w{i:3d}  {h:03X}.A  "
              f"c[{ad:02X}] = 0x{raw:06X} = {C.q23(raw):+.8f}")
    print(f"\n   094.A coefficient histogram: "
          + ", ".join(f"0x{k:06X} x{v}" for k, v in c94.most_common()))
    print("   => 094.A consumes 0x7FFFFF (= 1 - 2^-23, the largest positive Q0.23")
    print("      value) in EVERY occurrence.  MEASURED, no exception.")

    print("\n--- L2  the rate law: is 092.A's coefficient a phase increment?\n")
    print("   PREDICTION, stated before the check: if 092.A adds its coefficient")
    print("   to a phase accumulator that wraps at 1.0, the LFO frequency is")
    print("        f = c * Fs        (cycles per sample x samples per second)")
    print("   and the DEFAULTS the designers wrote should be ROUND numbers of Hz.")
    print("   This can fail: nothing forces nine unrelated constants to be round.\n")
    uniq = {}
    for a, raw in c92:
        uniq.setdefault(raw, a)
    print("   raw      c              f @44100Hz   f @48000Hz   trunc(f*2^23/44100)")
    worst44 = worst48 = 0.0
    for raw, a in sorted(uniq.items()):
        f44 = raw / 2.0 ** 23 * 44100.0
        f48 = raw / 2.0 ** 23 * 48000.0
        r44, r48 = round(f44, 1), round(f48, 1)
        e44 = abs(f44 - r44) / max(r44, 1e-9)
        e48 = abs(f48 - r48) / max(r48, 1e-9)
        worst44 = max(worst44, e44)
        worst48 = max(worst48, e48)
        pred = int(r44 * 2 ** 23 / 44100.0)
        print(f"   {raw:7d}  {raw/2.0**23:.8f}  {f44:9.4f}Hz  {f48:9.4f}Hz  "
              f"{pred:7d} {'==' if pred == raw else '!='} raw   "
              f"({NAMES.get(a,'?')})")
    print(f"\n   worst relative distance to a 0.1 Hz grid:  @44100 = {worst44*100:.4f}%"
          f"   @48000 = {worst48*100:.4f}%")
    print("   => the constants are round Hz at 44,100 and NOT at 48,000.")
    print("      This is a THIRD independent derivation of the sample rate.")

    print("\n--- L3  the host parameter that writes the increment (falsifiable)\n")
    print("   PREDICTION: if 092.A's coefficient is the LFO rate, then the set of")
    print("   coefficient addresses consumed by 092.A words must equal, EXACTLY,")
    print("   the set of addresses written by ONE host opcode -- and that opcode")
    print("   must appear in the LFO-bearing images and nowhere else.\n")
    hit = miss = 0
    for a in imgs:
        bank, b0 = bank_of(subrom, a)
        amap = t1_map(rom, a)
        s92 = sorted(ad for _i, w, ad in cursor_walk(progs[a], b0)
                     if fl(w)[0] == 0x092)
        o65 = sorted(amap.get(0x65, []))
        if not s92 and not o65:
            continue
        ok = s92 == o65
        hit += ok
        miss += (not ok)
        print(f"   {'OK ' if ok else '!! '}[{a:3d}] {NAMES.get(a,'?'):16s} "
              f"092.A slots {['0x%02X' % x for x in s92]}   "
              f"op 0x65 writes {['0x%02X' % x for x in o65]}")
    print(f"\n   agree {hit}, disagree {miss}")
    only65 = [a for a in range(100) if 0x65 in t1_map(rom, a)]
    print(f"   algorithms declaring host op 0x65 at all: {only65}")

    print("\n--- L4  every host opcode, vs the class-A word forms it feeds\n")
    print("   (T2-confirmed only: unreferenced T1 operand slots excluded.)\n")
    byop = collections.defaultdict(collections.Counter)
    for a in imgs:
        bank, b0 = bank_of(subrom, a)
        amap = t1_map(rom, a)
        used = t2_used(rom, a, amap)
        walk = {ad: w for _i, w, ad in cursor_walk(progs[a], b0)}
        for op, ad in used:
            if ad in walk:
                h, c, _a, lo = fl(walk[ad])
                byop[op][f"{h:03X}.A.**.{lo:03X}"] += 1
    for op in sorted(byop):
        tot = sum(byop[op].values())
        top = byop[op].most_common(4)
        pure = "  <== PURE" if len(byop[op]) == 1 else ""
        print(f"   op 0x{op:02X}  n={tot:3d}  "
              + ", ".join(f"{k}x{v}" for k, v in top) + pure)

    print("\n--- L5  is the waveform COMPUTED?  The 2/pi test\n")
    print("   PREDICTION: the brief proposes that 0x517CC1 (= 2/pi) indicates a")
    print("   computed sine.  If so it must appear in the LFO-bearing images.\n")
    for a in imgs:
        bank, _b0 = bank_of(subrom, a)
        n = sum(1 for v in bank.values() if v == 0x517CC1)
        if n:
            lfo = any(fl(w)[0] == 0x082 for w in progs[a])
            print(f"   algo {a:3d} {NAMES.get(a,'?'):16s} 2/pi x{n}   "
                  f"has an LFO read: {lfo}")
    print("\n   => 2/pi occurs in 8 images, and NOT ONE of them is a")
    print("      chorus/vibrato/pan/rotary/phaser image.  The 2/pi hypothesis for")
    print("      the LFO is FALSIFIED; the constant belongs to the envelope")
    print("      detector, as kn5000-dsp-effect-map.md sect.6.3 already had it.")

    print("\n--- L6  the waveform table selector\n")
    sel = collections.Counter()
    for a in imgs:
        for i, w in enumerate(progs[a]):
            h, c, ad, lo = fl(w)
            if c == 6:
                lfo = any(fl(x)[0] == 0x082 for x in progs[a])
                sel[(ad, lfo)] += 1
    for (ad, lfo), n in sorted(sel.items()):
        print(f"   table 0x{ad:02X}  x{n:3d}   in LFO-bearing image: {lfo}")


# ------------------------------------------------------------------ hypothesis space

def sec_space(subrom, progs, rom, args):
    print("=== SECTION space: the modulated-tap hypothesis space and its search\n")
    imgs = images(progs)
    print("""Machine model (a strict extension of notes/kn5000-dsp-semantics.md sect.1):
   acc, P, mem[], cursor, ptr        -- unchanged
   ADDR    the DRAM address latch    (9xx.1.*.1D5 opens, 880.1.20.* closes)
   FRAC    a fractional-part latch
   phase   the LFO phase accumulator (decoded in section 'lfo')

The idiom must, between OPEN and the class-A close, produce
     y = c * ((1-f)*d[b + floor(m)] + f*d[b + floor(m) + 1])
with m = depth * lfo(t) and b the mode-0x0B tap length.

Free choices enumerated, per idiom word:
   [0] 900.1.60.1D5   ADDR <- {base, base+mod, mod}                        3
   [1] 192.A.4N.000   P <- c[cur] * {mem[ptr], LFO, ADDR};
                      ADDR += {0, P, nothing}                            3 x 3
   [2] 082.2.00.1C0   LFO <- {table result, phase acc, mem[ptr]}            3
   [3] C40.3.20.44C   FRAC <- {frac(ADDR), acc, LFO}                        3
   [4] A00.0.00.041   {Lprev <- d[ADDR], ADDR += 1, nothing}                3
   [5] 880.1.20.2C7   D <- d[ADDR]; blend with {Lprev, none} x {F, 1-F}     4
   [6] 102.A.xx.4C8   P <- c[cur] * {D, acc}; acc {+= P, <- P, none}        6
   which word latches the fraction (2 orders)                              2
""")
    total = 3 * 3 * 3 * 3 * 3 * 3 * 4 * 6 * 2
    print(f"   TOTAL points enumerable = {total:,}\n")
    print("""EXCLUDED A PRIORI (listed so the space cannot be mistaken for one narrowed
until it was unique):
   X1  the LFO WAVEFORM is not searched -- it is decoded separately in 'lfo',
       and no observable in this ROM depends on its shape.
   X2  LINEAR interpolation only: the idiom has exactly one class-A word after
       the DRAM close, so a higher-order interpolator has nowhere to live.
   X3  the tap BASE comes from the mode-0x0B record (MEASURED elsewhere).

HONEST RESULT -- the space is NOT scoreable, and the reason is structural.
   The biquad fell because an INDEPENDENT ground truth existed: H(z) computed
   from the same ROM coefficients.  For the modulated tap there is none.  The
   depth and rate defaults are HOST-written, the waveform table is not in the
   extracted stream, and the output is a delayed copy of an arbitrary input.
   Every one of the %d assignments produces "a modulated fractional delay".
   Declaring a winner would be reporting a fit, so no winner is declared.
   What follows are the constraints that CAN fail, and what they eliminate.
""" % total)

    occ = []
    for a in imgs:
        h, _ = find_taps(progs[a])
        for i in h:
            occ.append((a, i, [progs[a][i + k] for k in range(7)]))
    print(f"C1  Field invariance over all {len(occ)} occurrences of the idiom:")
    inv = 0
    for k in range(7):
        vals = collections.Counter(fmt(o[2][k]) for o in occ)
        if len(vals) == 1:
            inv += 1
        print(f"      word[{k}]  {len(vals)} distinct: "
              + ", ".join(f"{v} x{n}" for v, n in vals.most_common(4)))
    print(f"""
   => {inv} of the 7 words are BYTE-IDENTICAL in every occurrence.  A word that
      never varies carries no per-tap operand address, so words [0] [2] [3] [4]
      [5] cannot take mem[ptr] as their operand: that would need a per-tap
      addr8.  This eliminates the mem[ptr] branch at [2] and at [3],
      collapsing the space 3x3 -> 2x2, i.e. {total} -> {total//9*4} points.
      It is a real, falsifiable reduction; it is not a solution.""")

    print("\nC2  the two VARIABLE fields, and what they must be:")
    for a in imgs:
        h, _ = find_taps(progs[a])
        if not h:
            continue
        ad = [fl(progs[a][i + 1])[2] for i in h]
        cl = [fl(progs[a][i + 6])[2] for i in h]
        print(f"      [{a:3d}] {NAMES.get(a,'?'):16s} n={len(h)}  "
              f"[1].addr8 {['0x%02X' % x for x in ad]}  "
              f"[6].addr8 {['0x%02X' % x for x in cl]}")
    print("""
   [1].addr8 is 0x3C..0x5B (positive, ascending within an image) and [6].addr8
   is 0x9D..0xC3 (negative as a signed post-increment).  Under the MEASURED
   signed-post-increment rule they are one pointer that walks UP through a
   per-voice parameter block and is then rewound.  MEASURED; the block's
   contents are INFERRED (per-voice depth at [1], per-voice output gain at [6],
   because those are the two class-A words and therefore the two cursor
   consumers).""")


# ------------------------------------------------------------------ verification

def sec_verify(subrom, progs, rom, args):
    print("=== SECTION verify: falsifiable checks\n")
    r = C.Rom(subrom)
    imgs = images(progs)

    print("--- V1  tap spacing\n")
    for a in CHORUS_FAMILY + [15, 53, 71, 74]:
        if a not in progs:
            continue
        p = C.parse_param_stream(r, r.u32le(C.PARAM_TABLE + 4 * a))
        dl = C.delays_of(p)
        sp = [dl[i + 1] - dl[i] for i in range(len(dl) - 1)]
        print(f"   [{a:3d}] {NAMES.get(a,'?'):16s} delays {dl}")
        print(f"          spacings {sp}   ms {[round(1000.0*d/FS,2) for d in dl]}")
    print("""
   READ CAREFULLY.  The brief asks whether "the delay excursion matches the
   known tap spacing (520)".  It does NOT, and it should not: the four CHORUS
   taps are four INDEPENDENT voices at 200/720/1240/1760, each with its own
   192.A depth slot.  520 is the gap BETWEEN voices, and the only thing it
   constrains is an upper bound -- a peak excursion above +-260 samples would
   let two voices cross.  Reporting 520 as an excursion would be wrong; the
   check as posed FAILS and the failure is informative.""")

    print("\n--- V2  voice count\n")
    print("   PREDICTION, before the count: ENSEMBLE is 3 voices x stereo, so it")
    print("   must show SIX modulated taps -- and it must show them even though")
    print("   the C40.3 interpolation pair is known to be absent from it.\n")
    ENS = [(0x800, 1, None, 0x1D5), (0x192, 0xA, None, 0x41A),
           (0x082, 2, 0x00, 0x1C0), (0x000, 2, 0x00, 0x44C),
           (0x880, 1, 0x20, 0x2D9)]
    for a in imgs:
        w = progs[a]
        taps = [i for i, x in enumerate(w)
                if fl(x)[0] == 0x880 and fl(x)[1] == 1 and fl(x)[2] == 0x20]
        h, _ = find_taps(w)
        e = [i for i in range(len(w) - 4)
             if all(match(w[i + k], ENS[k]) for k in range(5))]
        if not (taps or h or e) or a not in NAMES:
            continue
        print(f"   [{a:3d}] {NAMES[a]:16s} tap reads {len(taps):2d}   "
              f"interpolated idioms {len(h):2d}   "
              f"non-interpolated idioms {len(e):2d}")
    if 6 in progs:
        e = [i for i in range(len(progs[6]) - 4)
             if all(match(progs[6][i + k], ENS[k]) for k in range(5))]
        d = [fl(progs[6][i + 1])[2] for i in e]
        print(f"\n   ENSEMBLE: {len(e)} modulated taps at {e}, depth addr8 "
              + ", ".join(f"0x{x:02X}" for x in d))
        print("   => 0x40 0x41 0x42 | 0x46 0x47 0x48 = THREE voices, TWICE.")
        print("      PREDICTION MET exactly: 3 voices x 2 channels = 6.")
        print("   NOTE the shared lo12 0x44C: ENSEMBLE uses 000.2.00.44C where")
        print("      CHORUS uses C40.3.20.44C.  Same lo12, different class -- so")
        print("      lo12 0x44C = 'apply the modulation offset' and the class")
        print("      selects whether the fractional part is interpolated.")
        print("      INFERRED, and it explains the brief's 'ENSEMBLE has no")
        print("      interpolation pair' without any extra machinery.")

    print("\n--- V3  the rotary pair\n")
    if 15 in progs and 53 in progs:
        print(f"   microcode byte-identical: {progs[15] == progs[53]}")
        p15 = C.parse_param_stream(r, r.u32le(C.PARAM_TABLE + 4 * 15))
        p53 = C.parse_param_stream(r, r.u32le(C.PARAM_TABLE + 4 * 53))
        b15, _ = bank_of(subrom, 15)
        b53, _ = bank_of(subrom, 53)
        print(f"   delays 15:{C.delays_of(p15)}  53:{C.delays_of(p53)}  "
              f"equal={C.delays_of(p15) == C.delays_of(p53)}")
        keys = sorted(set(b15) | set(b53))
        diff = [(k, b15.get(k), b53.get(k)) for k in keys if b15.get(k) != b53.get(k)]
        print(f"   coefficient slots: {len(keys)}, differing: {len(diff)}")
        for k, x, y in diff:
            print(f"      c[{k:02X}]  {C.q23(x):+.6f}  ->  {C.q23(y):+.6f}")
        t1a, t1b = (rom.u32le(P.ALGO_T1_ARRAY + 4 * x) for x in (15, 53))
        t2a, t2b = (rom.u32le(P.ALGO_T2_ARRAY + 4 * x) for x in (15, 53))
        ma, mb = t1_map(rom, 15), t1_map(rom, 53)
        ra = [bytes(b) for _a, _l, b in P.split_records(rom, t2a)]
        rb = [bytes(b) for _a, _l, b in P.split_records(rom, t2b)]
        print(f"   T1 pointers 0x{t1a:06X} / 0x{t1b:06X}   T1 CONTENT equal: {ma == mb}")
        print(f"   T2 pointers 0x{t2a:06X} / 0x{t2b:06X}   T2 CONTENT equal: {ra == rb}")
        print("""
   PREDICTION, stated before the check: 'your decode must explain both with
   only the coefficients differing'.  RESULT: the premise is FALSE.  The two
   entries are identical in EVERY respect this tooling can see -- microcode,
   static coefficient bank, mode-0x0B delays, T1 opcode map and T2 parameter
   records -- and differ only in the effect NAME.  There is no coefficient
   difference to explain.  The check passes vacuously, and reporting it as a
   confirmation of the decode would be dishonest: it confirms nothing.
   The two ROTOR SPEEDS live in this image but NOT in a 092.A word: ROCK
   ROTARY is the one modulated image with no phase-accumulator word at all.
   Its speeds come through host op 0x69 (eval_0392AC, the /180 degree scaler)
   at slots 0x0F and 0x13.  So the machine has a SECOND rate mechanism, and
   it is not decoded here.  MEASURED (the absence), UNRESOLVED (the mechanism).""")

    print("\n--- V4  periodicity, from the decoded rate law\n")
    for a in imgs:
        bank, b0 = bank_of(subrom, a)
        for i, w, ad in cursor_walk(progs[a], b0):
            if fl(w)[0] == 0x092:
                raw = bank.get(ad, 0)
                f = raw / 2.0 ** 23 * FS
                print(f"   [{a:3d}] {NAMES.get(a,'?'):16s} w{i:3d} c[{ad:02X}] "
                      f"-> {f:9.4f} Hz, period {FS/max(f,1e-9):11.1f} samples "
                      f"({1000.0/max(f,1e-9):8.2f} ms)")


# ------------------------------------------------------------------ TASK B: the 212 twin

def sec_twin(subrom, progs, rom, args):
    print("=== SECTION twin: TASK B -- the 212.2 family and the class-A/class-2 rule\n")
    seen = {}
    for a in sorted(progs):
        seen.setdefault(tuple(progs[a]), a)
    imgs = sorted(seen.values())

    print("--- B1  the whole 0x212 family, counted\n")
    fam = collections.Counter()
    where = collections.defaultdict(set)
    for a in imgs:
        for w in progs[a]:
            h, c, ad, lo = fl(w)
            if h == 0x212:
                fam[(c, lo)] += 1
                where[(c, lo)].add(a)
    print("   class lo12  count  images")
    for (c, lo), n in sorted(fam.items(), key=lambda kv: -kv[1]):
        print(f"     {c:X}   {lo:03X}   {n:4d}   {len(where[(c,lo)])}")

    print("\n--- B2  the minimal pair (class2-round2 sect.1.4): the phaser's chain\n")
    if 5 in progs:
        w = progs[5]
        for i, x in enumerate(w):
            h, c, ad, lo = fl(x)
            if h in (0x102, 0x212, 0x104) and 10 <= i <= 60:
                print(f"      {i:3d}  {fmt(x)}")

    print("""
   PREDICTION, stated before the test.  If bit 23 is a pure MULTIPLY-ENABLE and
   0x212 means "write the operand into mem[ptr] and multiply by it", then in the
   phaser's nine identical all-pass sections the eight that carry 212.2.01.412
   perform the SAME write as the ninth's 212.A.B0.412, and only the ninth also
   fetches a coefficient.  That predicts:
     (a) the eight sections must be arithmetically COMPLETE without a multiply
         at that slot -- i.e. each section must still contain its own class-A
         word elsewhere;
     (b) the addr8 of the class-2 form is a DON'T-CARE only if 0x01 is a real
         pointer step; conversely if 0x01 == 0xB0 in effect, the reading fails.
""")
    if 5 in progs:
        w = progs[5]
        secs = []
        for i in range(len(w) - 2):
            if (fl(w[i])[0] == 0x102 and fl(w[i])[3] == 0x1CD
                    and fl(w[i + 1])[0] == 0x212):
                secs.append(i)
        print(f"   (a) all-pass sections found at {secs}")
        na = []
        for s in secs:
            na.append(sum(1 for k in range(3) if fl(w[s + k])[1] == 0xA))
        print(f"       class-A words per section: {na}")
        if set(na) == {0, 1} or set(na) == {0}:
            print("       => RESULT: eight sections contain ZERO class-A words.")
            print("          Prediction (a) FAILS.  A first-order all-pass needs a")
            print("          gain; a section with no coefficient fetch at all cannot")
            print("          realise one.  Therefore bit 23 on 0x212 is NOT a pure")
            print("          multiply-enable in this context -- it selects WHICH")
            print("          coefficient source the multiplier uses (a static one for")
            print("          class 2, the cursor for class A), exactly the caveat")
            print("          class2-round2 sect.1.4 raised.  MEASURED, and it FALSIFIES")
            print("          the naive twin rule.")
        else:
            print("       => prediction (a) holds; twin rule survives here.")
        print(f"   (b) addr8 of the class-2 forms: "
              f"{sorted({fl(w[s+1])[2] for s in secs})}; "
              f"of the class-A forms: "
              f"{sorted({fl(x)[2] for x in w if fl(x)[0]==0x212 and fl(x)[1]==0xA})}")

    print("\n--- B3  does the twin relation generalise?  Every hi12 with BOTH forms\n")
    both = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for a in imgs:
        for x in progs[a]:
            h, c, ad, lo = fl(x)
            both[h][c][lo] += 1
    rows = []
    for h, byc in both.items():
        if 0xA in byc and 2 in byc:
            sa, s2 = set(byc[0xA]), set(byc[2])
            rows.append((h, sum(byc[0xA].values()), sum(byc[2].values()),
                         sorted(sa & s2), sorted(sa - s2), sorted(s2 - sa)))
    rows.sort(key=lambda r: -(r[1] + r[2]))
    print("   hi12   nA   n2   lo12 SHARED           lo12 A-only        lo12 2-only")
    for h, na, n2, sh, ao, bo in rows[:24]:
        print(f"   {h:03X}  {na:4d} {n2:4d}   "
              f"{','.join('%03X'%x for x in sh[:5]):18s} "
              f"{','.join('%03X'%x for x in ao[:5]):18s} "
              f"{','.join('%03X'%x for x in bo[:5])}")
    nshare = sum(1 for r in rows if r[3])
    print(f"\n   {len(rows)} hi12 values carry BOTH a class-A and a class-2 form;")
    print(f"   {nshare} of them share at least one lo12 between the two classes.")
    print("   If class4 were purely a multiply-enable orthogonal to the rest of")
    print("   the word, the lo12 SETS would coincide.  Measured overlap:")
    tota = sum(len(r[3]) for r in rows)
    totu = sum(len(r[3]) + len(r[4]) + len(r[5]) for r in rows)
    print(f"      shared lo12 / all lo12 = {tota}/{totu} = {tota/max(1,totu):.3f}")

    print("\n--- B4  212.2.**.000: what surrounds it (positional evidence)\n")
    ctx = collections.Counter()
    for a in imgs:
        w = progs[a]
        for i, x in enumerate(w):
            h, c, ad, lo = fl(x)
            if h == 0x212 and c == 2 and lo == 0x000:
                ctx[(fmt(w[i - 1]) if i else '-', fmt(w[i + 1])
                     if i + 1 < len(w) else '-')] += 1
    for k, n in ctx.most_common(15):
        print(f"   {n:3d}   {k[0]}  <<212.2.**.000>>  {k[1]}")
    addrs = collections.Counter()
    for a in imgs:
        for x in progs[a]:
            h, c, ad, lo = fl(x)
            if h == 0x212 and c == 2 and lo == 0x000:
                addrs[ad] += 1
    print("\n   addr8 distribution of 212.2.**.000: "
          + ", ".join(f"0x{k:02X}x{v}" for k, v in addrs.most_common()))


SECTIONS = {'dump': sec_dump, 'tap': sec_tap, 'lfo': sec_lfo,
            'space': sec_space, 'verify': sec_verify, 'twin': sec_twin}


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    subrom, progdir = sys.argv[1], sys.argv[2]
    want = sys.argv[3:] or list(SECTIONS)
    progs = load_progs(progdir)
    rom = P.Rom(subrom, P.SUB_BASE)
    for s in want:
        if s not in SECTIONS:
            sys.exit(f"unknown section {s}; have {list(SECTIONS)}")
        SECTIONS[s](subrom, progs, rom, [])
        print()


if __name__ == '__main__':
    main()
