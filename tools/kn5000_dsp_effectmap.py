#!/usr/bin/env python3
"""kn5000_dsp_effectmap.py -- a PER-EFFECT STRUCTURAL MAP of all 38 distinct
uPD6383GF microprogram images (KN5000 IC311, NEC uPD6383GF-3BA).

Companion tool to notes/kn5000-dsp-effect-map.md.  It APPLIES the model proven in
notes/kn5000-dsp-biquad-map.md and notes/kn5000-dsp-cursor-general.md --

    * an implicit COEFFICIENT CURSOR, +1 per class-A word, reset by 801.0.00.021;
    * a biquad section of 9 words consuming 6 coefficients
      (+0=b1 +1=b0 +2=b2 +3=-a1/a0 +4=-a2/a0 +5=make-up gain);
    * external-DRAM brackets 880.1.60.* / 880.1.20.*;
    * hi12=0x082 LFO read, hi12=0xC40 envelope, 104.2.00.000 all-pass marker --

to every image, and reports where it breaks.  Nothing here re-implements parsing:
it imports kn5000_dsp_extract, _class2, _biquad, _biquadmap, _params, _coeffs.
NONE of them is edited.

Sections:
    map        the deliverable: one structured entry per distinct image
    multitap   MULTI TAP DELAY -- the one claimed cursor-model failure
    deficit    the 12 images where bank != classA + 1, classified
    reverbs    the 12 reverb presets: ladders, PLATE 2 / BRIGHT 1 / BRIGHT 2
    compress   the compressor +4, narrowed
    vocab      the remaining hi12 / lo12 vocabulary, scored by co-occurrence
    triplet    the 3-word table-lookup idiom (new in this tool)

Usage:
    python3 tools/kn5000_dsp_extract.py <kn5000_subprogram_v142.rom> /tmp/progs
    python3 tools/kn5000_dsp_effectmap.py <kn5000_subprogram_v142.rom> /tmp/progs \\
            <kn5000_v10_program.rom> [section ...]

Every number printed is MEASURED.  Interpretation lives in the notes file.
"""
import collections
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_extract as E        # noqa: E402
import kn5000_dsp_class2 as K         # noqa: E402
import kn5000_dsp_biquad as B         # noqa: E402
import kn5000_dsp_biquadmap as BM     # noqa: E402
import kn5000_dsp_params as P         # noqa: E402
import kn5000_dsp_coeffs as C         # noqa: E402

PEQ = 39
REVERB_IMG = 16
REVERB_PRESETS = range(16, 28)
FS = 44100.0

# the 8-word reverb all-pass motif (reverb note sect. 1), class-A word at +5
MOTIF = [0x8801602D4, 0x104200000, 0x000200419, 0x012200680,
         0x880120655, 0x102A0064B, 0x000200000, 0x000200000]

# the three-word table-lookup idiom found by this tool (see sec_triplet)
TRIP_LAST = (0x012, 4, 0x01, 0x1CE)

COEF_OPS = {op for op, (_e, wr, _f) in P.OPCODE_EVAL.items() if wr == 0x0387E6}
COEF_OPS -= {0x74, 0x21, 0x67, 0x6A}

# families for which the earlier notes assign a meaning; used by sec_vocab to
# report only what is still UNASSIGNED.
KNOWN_HI = {0x082: 'LFO read', 0xC40: 'envelope / detector family',
            0x880: 'external-DRAM access', 0x801: 'pointer load',
            0x104: 'all-pass marker', 0x804: 'class-8 filter-output step'}
KNOWN_LO = {0x647: 'biquad store (P-consumer)', 0x687: 'biquad store (P-consumer)',
            0x821: 'pointer-load immediate', 0x021: 'pointer rewind immediate'}


# ------------------------------------------------------------------ helpers

def q(v, sh):
    return (v - (1 << 24) if v & 0x800000 else v) / float(1 << sh)


def q23(v):
    return q(v, 23)


def classa(words):
    return [i for i, w in enumerate(words) if K.fl(w)[1] == 0xA]


def bank_of(subrom, algo):
    out = []
    for base, ws in BM.sbank(subrom, algo):
        if base is None:
            continue
        for i, w in enumerate(ws):
            out.append((base + i, w))
    return out


def cursor_slots(words, base):
    """{program index: coefficient address} for every class-A word."""
    out, c = {}, 0
    for i, w in enumerate(words):
        if w == 0x801000021:
            c = 0
        if K.fl(w)[1] == 0xA:
            out[i] = base + c
            c += 1
    return out


def dram_words(words):
    """(opens, reads) -- 880.1.60.* writes/opens and 880.1.20.* tap reads."""
    op = [i for i, w in enumerate(words)
          if K.fl(w)[0] == 0x880 and K.fl(w)[1] == 1 and K.fl(w)[2] == 0x60]
    rd = [i for i, w in enumerate(words)
          if K.fl(w)[0] == 0x880 and K.fl(w)[1] == 1 and K.fl(w)[2] == 0x20]
    return op, rd


def triplets(words):
    """[(index, tableword)] of the 3-word table-lookup idiom."""
    out = []
    for i in range(len(words) - 2):
        if (K.fl(words[i])[3] == 0xC63 and K.fl(words[i + 1])[1] == 6
                and K.fl(words[i + 2]) == TRIP_LAST):
            out.append((i, words[i + 1]))
    return out


def motif_hits(words):
    out = []
    for i in range(len(words) - 8 + 1):
        if sum(1 for k in range(8) if words[i + k] != MOTIF[k]) <= 1:
            out.append(i)
    return out


def delays_of(subrom, algo):
    r = C.Rom(subrom)
    p = C.parse_param_stream(r, r.u32le(C.PARAM_TABLE + 4 * algo))
    return C.delays_of(p)


def host_map(rom, algo):
    t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
    out = []
    if t1p and t1p != P.NULL_T1:
        for _a, op, e in P.parse_t1(rom, t1p):
            out.append((op, e))
    return out


def image_algos(progs):
    byimg = collections.defaultdict(list)
    for a in sorted(progs):
        byimg[tuple(progs[a])].append(a)
    return byimg


def features(subrom, progs, imgs, rom):
    """Everything the map and the vocabulary scan need, per image."""
    f = {}
    r = E.Rom(subrom)
    for a in imgs:
        w = progs[a]
        bk = bank_of(subrom, a)
        base = bk[0][0] if bk else 0
        nA = classa(w)
        op, rd = dram_words(w)
        ir, _c, _o = E.parse_stream(r, r.u32le(E.ALGO_TABLE + 4 * a))
        f[a] = dict(
            words=w, bank=bk, base=base, nA=nA,
            deficit=len(bk) - len(nA) - 1,
            slots=cursor_slots(w, base),
            dram_open=op, dram_read=rd,
            allpass=[i for i, x in enumerate(w) if x == 0x104200000],
            lfo=[i for i, x in enumerate(w) if K.fl(x)[0] == 0x082],
            env=[i for i, x in enumerate(w) if K.fl(x)[0] == 0xC40],
            c8=[i for i, x in enumerate(w) if K.fl(x)[1] == 8],
            trip=triplets(w),
            motif=motif_hits(w),
            biq=B.find_sections(w, progs[PEQ][5:5 + 9], maxdiff=3),
            load=[x[0] for x in ir],
            unit=K.fl(w[-1])[2],
            host=host_map(rom, a),
            delays=delays_of(subrom, a),
            hist=collections.Counter(K.fl(x)[1] for x in w),
        )
    return f


# ----------------------------------------------------------------- map

FAMILY = {
    'reverb / ambience':   [16, 8],
    'delay':               [9, 10, 65],
    'chorus / ensemble':   [1, 2, 6, 56, 50, 64, 67],
    'flanger / phaser':    [4, 5, 66, 68],
    'EQ / filter':         [39, 3, 35, 52],
    'dynamics':            [36],
    'distortion':          [32, 33, 34],
    'rotary':              [15],
    'pan / tremolo / ring': [48, 54],
    'combinations':        [70, 71, 72, 73, 74, 75, 96, 97, 98, 99],
    'null':                [0],
}


def sec_map(subrom, progs, imgs, rom, mrom, F):
    byimg = image_algos(progs)
    placed = {a for v in FAMILY.values() for a in v}
    assert placed == set(imgs), sorted(set(imgs) ^ placed)
    for fam, members in FAMILY.items():
        print("\n" + "#" * 74)
        print(f"## FAMILY: {fam}")
        for a in members:
            d = F[a]
            w = d['words']
            nm = P.effect_name(mrom, a)
            algos = byimg[tuple(w)]
            print("\n" + "-" * 70)
            print(f"[{a}] {nm}")
            if len(algos) > 1:
                sh = [f"{x}:{P.effect_name(mrom, x)}" for x in algos]
                print(f"   shared by {len(algos)} algorithm slots: "
                      + ', '.join(sh if len(sh) <= 13 else sh[:13] + ['...']))
            print(f"   unit {0 if d['unit'] == 0x0E else 1} (terminator addr8 "
                  f"0x{d['unit']:02X}), I-RAM load {d['load']}, {len(w)} words")
            print(f"   class histogram: "
                  + ' '.join(f"{c:X}:{n}" for c, n in sorted(d['hist'].items())))
            print(f"   class-A {len(d['nA'])}, bank {len(d['bank'])} words at "
                  f"0x{d['base']:02X}, deficit {d['deficit']:+d}")
            print(f"   DRAM: {len(d['dram_open'])} writes (880.1.60) at {d['dram_open']}, "
                  f"{len(d['dram_read'])} tap reads (880.1.20) at {d['dram_read']}")
            if d['delays']:
                print("   delay lengths (mode-0x0B): "
                      + ', '.join(f"{n} ({1000.0*n/FS:.2f} ms)" for n in d['delays']))
            bits = []
            if d['biq']:
                bits.append(f"{len(d['biq'])} biquad sections at "
                            f"{[i for i, _ in d['biq']]}")
            if d['motif']:
                bits.append(f"{len(d['motif'])} reverb all-pass motifs at {d['motif']}")
            if d['allpass']:
                bits.append(f"{len(d['allpass'])} all-pass markers (104.2.00.000) "
                            f"at {d['allpass']}")
            if d['lfo']:
                bits.append(f"{len(d['lfo'])} LFO reads (082.*) at {d['lfo']}")
            if d['env']:
                bits.append(f"{len(d['env'])} C40 words at {d['env']}")
            if d['trip']:
                bits.append(f"{len(d['trip'])} table-lookup triplets at "
                            + str([(i, f"tbl 0x{K.fl(t)[2]:02X}") for i, t in d['trip']]))
            if d['c8']:
                bits.append(f"{len(d['c8'])} class-8 filter-output steps at {d['c8']}")
            for b in bits:
                print("   " + b)
            # biquad coefficient decode.  Where the host's T1 op 0x70 supplies one
            # address per section, PREFER it: it is the authority, and in the four
            # compressor images it differs from the raw cursor slot by exactly the
            # known +4 deficit (see notes sect. "the compressor +4").
            bkd = dict(d['bank'])
            op70 = [e for op, e in d['host'] if op == 0x70]
            hostslots = None
            # only when the host group is exactly one address per section (algo 39's
            # group is 10 = 5 coefficient + 5 STATE bases, so it is skipped)
            if op70 and len(op70[0]) == len(d['biq']):
                cand = op70[0]
                deltas = [cand[n] - d['slots'][i] for n, (i, _x) in enumerate(d['biq'])
                          if i in d['slots']]
                if deltas and all(0 <= x <= 8 for x in deltas):
                    hostslots = cand
            for n, (i, diff) in enumerate(d['biq']):
                slot = d['slots'].get(i)
                if hostslots is not None and slot is not None \
                        and hostslots[n] != slot:
                    print(f"   NOTE biquad @{i}: cursor says 0x{slot:02X}, host "
                          f"op 0x70 says 0x{hostslots[n]:02X} "
                          f"(delta {hostslots[n]-slot:+d}); using the host's")
                    slot = hostslots[n]
                if slot is None:
                    continue
                blk = [bkd.get(slot + k) for k in range(6)]
                if any(x is None for x in blk):
                    print(f"   biquad @{i}: coefficients 0x{slot:02X}.. "
                          f"(partly outside the loaded bank)")
                    continue
                inv = BM.invert(blk)
                print(f"   biquad @{i} reads 0x{slot:02X}..0x{slot+5:02X}: "
                      + ' '.join('%06X' % x for x in blk))
                print(f"        b=[{inv['b0']:+.6f} {inv['b1']:+.6f} {inv['b2']:+.6f}] "
                      f"a=[1 {inv['a1']:+.6f} {inv['a2']:+.6f}] "
                      f"{'STABLE' if inv['stable'] else 'UNSTABLE'}"
                      + (f"  f0={inv['f0']:.1f} Hz Q={inv['Q']:.4f}"
                         if 'f0' in inv else "")
                      + f"  DC={inv['dc']:+.4f}  make-up={q(blk[5], 22):+.4f}")
            # every class-A word with its coefficient
            print("   cursor walk (class-A word -> coefficient):")
            line = []
            for i in sorted(d['slots']):
                s = d['slots'][i]
                v = bkd.get(s)
                line.append(f"[{i}]0x{s:02X}="
                            + (f"{q23(v):+.4f}" if v is not None else "OOB"))
            for k in range(0, len(line), 6):
                print("      " + '  '.join(line[k:k + 6]))
            # host parameter map
            if d['host']:
                print("   host T1: " + '  '.join(
                    f"op{op:02X}->{[f'{v:02X}' for v in e]}" for op, e in d['host']))


# ----------------------------------------------------------------- multitap

def sec_multitap(subrom, progs, rom, mrom, F):
    a = 10
    d = F[a]
    w = d['words']
    bkd = dict(d['bank'])
    print("=== MULTI TAP DELAY (algo 10): the one claimed cursor-model failure\n")
    print(f"class-A {len(d['nA'])}, bank {len(d['bank'])}, deficit {d['deficit']:+d}")
    print("no 801.0.00.021 rewind anywhere in the body: "
          f"{0x801000021 not in w}\n")
    print("-- the bank, and its INTERNAL DUPLICATION")
    for adr, v in d['bank']:
        print(f"   0x{adr:02X} {v:06X}  {q23(v):+.6f}")
    ws = [v for _a, v in d['bank']]
    dups = [(i, j) for i in range(len(ws)) for j in range(i + 1, len(ws))
            if ws[i] == ws[j] and ws[i] not in (0, 0x200000, 0x400000)]
    print(f"   non-trivial duplicate pairs: {dups}")
    print("\n-- the cursor walk, with the class-A words")
    for i in sorted(d['slots']):
        s = d['slots'][i]
        v = bkd.get(s)
        print(f"   [{i:>3}] {K.fmt(w[i])}   0x{s:02X} = "
              + (f"{q23(v):+.6f}" if v is not None else "PAST END OF BANK"))
    print("\n-- the host's coefficient-space writes")
    for op, e in d['host']:
        if op in COEF_OPS:
            print(f"   op 0x{op:02X} -> {[f'0x{v:02X}' for v in e]}")
    print("\n-- the two candidate output groups, word for word")
    for lo, hi in ((46, 50), (52, 55)):
        print(f"   words {lo}..{hi-1}: "
              + '  '.join(K.fmt(w[i]) for i in range(lo, hi)))
    print("\n-- the words BETWEEN them (the only place a partial rewind could hide)")
    for i in range(50, 52):
        print(f"   [{i}] {K.fmt(w[i])}")
    print("\n-- control: do those words appear in ZERO-deficit images?")
    for i in (50, 51):
        owners = [b for b in F if w[i] in F[b]['words'] and F[b]['deficit'] == 0]
        print(f"   {K.fmt(w[i])}: in {len(owners)} zero-deficit images "
              f"{[P.effect_name(mrom, b) for b in owners][:6]}")


# ----------------------------------------------------------------- deficit

def sec_deficit(subrom, progs, imgs, rom, mrom, F):
    print("=== the images where bank != classA + 1, classified\n")
    print(f"{'algo':>4} {'name':22} {'clsA':>5} {'bank':>5} {'def':>5}  "
          f"{'rewind?':>8} {'unit':>4}  class of exception")
    for a in imgs:
        d = F[a]
        if d['deficit'] == 0:
            continue
        rew = 0x801000021 in d['words']
        # does any host coefficient write land beyond the class-A reach?
        over = []
        for op, e in d['host']:
            if op in COEF_OPS:
                over += [v for v in e
                         if d['base'] + len(d['nA']) <= v < d['base'] + len(d['nA'])
                         + max(0, d['deficit'])]
        print(f"{a:>4} {P.effect_name(mrom, a):22} {len(d['nA']):>5} "
              f"{len(d['bank']):>5} {d['deficit']:>+5}  {str(rew):>8} "
              f"{0 if d['unit'] == 0x0E else 1:>4}  "
              f"host writes in the deficit window: {[f'0x{v:02X}' for v in over]}")


# ----------------------------------------------------------------- reverbs

def sec_reverbs(subrom, progs, mrom, F):
    print("=== the 12 reverb presets on the one 133-word image\n")
    w = progs[REVERB_IMG]
    hits = motif_hits(w)
    for a in REVERB_PRESETS:
        bk = dict(bank_of(subrom, a))
        if not bk:
            continue
        base = min(bk)
        slots = cursor_slots(w, base)
        g = [q23(bk[slots[i + 5]]) for i in hits if slots[i + 5] in bk]
        nm = P.effect_name(mrom, a)
        m0 = all(g[k] >= g[k + 1] for k in range(4))
        m1 = all(g[k] >= g[k + 1] for k in range(5, len(g) - 1))
        print(f"{a:>4} {nm:18} bank {len(bk):>3} @0x{base:02X}  chain0 "
              + ' '.join(f"{v:+.3f}" for v in g[:5])
              + " | chain1 " + ' '.join(f"{v:+.3f}" for v in g[5:])
              + f"  desc {m0}/{m1}")
    print("\n-- BRIGHT REVERB 2's bank against ROOM REVERB 1's, word by word")
    b16 = bank_of(subrom, 16)
    b27 = None
    for a in REVERB_PRESETS:
        if P.effect_name(mrom, a).strip().startswith('BRIGHT REVERB 2'):
            b27 = bank_of(subrom, a)
            n27 = a
    if b27:
        print(f"   ROOM REVERB 1 : {len(b16)} words at 0x{b16[0][0]:02X}")
        print(f"   BRIGHT REV. 2 : {len(b27)} words at 0x{b27[0][0]:02X}  (algo {n27})")
        for base, ws in BM.sbank(subrom, n27):
            print(f"      op-2 block at 0x{base:02X}: {len(ws)} words: "
                  + ' '.join('%06X' % x for x in ws[:8])
                  + (' ...' if len(ws) > 8 else ''))
        for base, ws in BM.sbank(subrom, 16):
            print(f"      (ROOM 1) block at 0x{base:02X}: {len(ws)} words")
    print("\n-- the gain multiset of every preset's nine stages")
    for a in REVERB_PRESETS:
        bk = dict(bank_of(subrom, a))
        base = min(bk)
        slots = cursor_slots(w, base)
        g = [q23(bk[slots[i + 5]]) for i in hits if slots[i + 5] in bk]
        print(f"   {P.effect_name(mrom, a):18} sorted {sorted(set(round(x,3) for x in g), reverse=True)}")


# ----------------------------------------------------------------- compress

def sec_compress(progs, mrom, F):
    print("=== the compressor's +4, narrowed\n")
    COMP = [36, 75, 96, 97]
    zero = [a for a in F if F[a]['deficit'] == 0]
    # families in EVERY compressor image and in NO zero-deficit image
    cnt = collections.Counter()
    for a in COMP:
        for f in {(K.fl(x)[0], K.fl(x)[1], K.fl(x)[3]) for x in F[a]['words']
                  if K.fl(x)[1] != 0xA}:
            cnt[f] += 1
    cand = [f for f, n in cnt.items() if n == 4
            and not any(f in {(K.fl(x)[0], K.fl(x)[1], K.fl(x)[3])
                              for x in F[b]['words']} for b in zero)]
    print(f"11-family baseline (cursor-general sect. 4): {len(cand)} candidates")
    for f in sorted(cand):
        print(f"   {f[0]:03X}.{f[1]:X}.{f[2]:03X}")
    print("\n-- NEW CONTROL: the same families against the OTHER positive-deficit")
    print("   images (GATED REVERB +4, ROCK ROTARY +4, ROOM REVERB +3, AUTO WAH +1).")
    print("   A word that consumes a coefficient without being class A should")
    print("   also appear where OTHER unexplained deficits are; a word that")
    print("   appears in NO other deficit image is compressor-private plumbing.")
    others = [a for a in F if F[a]['deficit'] > 0 and a not in COMP]
    for f in sorted(cand):
        own = [P.effect_name(mrom, b) for b in others
               if f in {(K.fl(x)[0], K.fl(x)[1], K.fl(x)[3]) for x in F[b]['words']}]
        print(f"   {f[0]:03X}.{f[1]:X}.{f[2]:03X}  also in: {own if own else '-- none --'}")
    print("\n-- per-image counts of each candidate, against the deficit")
    print(f"   {'family':14} " + ' '.join(f"{P.effect_name(mrom,a)[:9]:>9}" for a in COMP))
    for f in sorted(cand):
        row = []
        for a in COMP:
            row.append(sum(1 for x in F[a]['words']
                           if (K.fl(x)[0], K.fl(x)[1], K.fl(x)[3]) == f))
        print(f"   {f[0]:03X}.{f[1]:X}.{f[2]:03X}      "
              + ' '.join(f"{n:>9}" for n in row)
              + ("   <== constant 2/image = 4 fetches iff 2 each" if set(row) == {2} else "")
              + ("   <== constant 4/image = 4 fetches iff 1 each" if set(row) == {4} else ""))


# ----------------------------------------------------------------- op76

def sec_op76(imgs, mrom, F):
    print("=== op 0x76: how WIDE is the block it writes?\n")
    print("PREDICTION (stated before running): cursor-general sect. 6 measured the")
    print("reverb's two op-0x76 entries as the heads of two 3-word DAMPING TRIPLES,")
    print("but called the width 'not fixed' because the entry SPACINGS are 3, 4 and 7.")
    print("If the width really is 3, then in every image each op-0x76 address must be")
    print("the cursor slot of a class-A word, and the three consecutive coefficients")
    print("from that address must repeat verbatim at the OTHER op-0x76 addresses of")
    print("the same image (one tone filter per channel / per tap).\n")
    for a in imgs:
        d = F[a]
        e = [x for op, x in d['host'] if op == 0x76]
        if not e:
            continue
        bkd = dict(d['bank'])
        used = set(d['slots'].values())
        blocks = []
        for adr in e[0]:
            blk = [bkd.get(adr + k) for k in range(3)]
            blocks.append((adr, blk, adr in used))
        print(f"{a:>4} {P.effect_name(mrom, a):20} entries "
              f"{[f'0x{x:02X}' for x in e[0]]}  spacings "
              f"{[e[0][k+1]-e[0][k] for k in range(len(e[0])-1)]}")
        for adr, blk, hit in blocks:
            print(f"      0x{adr:02X} {'(class-A slot)' if hit else '(NOT a slot)':16}"
                  + ' '.join(f"{q23(v):+.6f}" if v is not None else "  --  "
                             for v in blk))
        ident = len({tuple(b) for _a, b, _h in blocks}) == 1
        print(f"      all blocks identical: {ident}   "
              f"all addresses are class-A slots: {all(h for _a, _b, h in blocks)}")


# ----------------------------------------------------------------- vocab

def mcc(pred, truth, imgs):
    tp = sum(1 for a in imgs if pred[a] and truth[a])
    fp = sum(1 for a in imgs if pred[a] and not truth[a])
    fn = sum(1 for a in imgs if not pred[a] and truth[a])
    tn = len(imgs) - tp - fp - fn
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return ((tp * tn - fp * fn) / den if den else 0.0), tp, fp, fn, tn


def predicates(imgs, mrom, F):
    nm = {a: P.effect_name(mrom, a) for a in imgs}

    def has(a, *s):
        return any(x in nm[a] for x in s)
    return {
        'lfo(name)':  lambda a: has(a, 'CHORUS', 'FLANGER', 'PHASER', 'ENSEMBLE',
                                    'VIBRATO', 'PAN', 'RING', 'MIX UP', 'ROTARY'),
        'dist(name)': lambda a: has(a, 'DISTORTION', 'OVERDR', 'FUZZ', 'EXCITER', 'DIST'),
        'reverb':     lambda a: has(a, 'REVERB'),
        'delay':      lambda a: has(a, 'DELAY'),
        'moddelay':   lambda a: has(a, 'CHORUS', 'FLANGER', 'VIBRATO', 'ENSEMBLE', 'ROTARY'),
        'peq':        lambda a: has(a, 'PARAMETRIC', 'PEQ'),
        'compr':      lambda a: has(a, 'COMPR'),
        'wah':        lambda a: has(a, 'WAH'),
        'dram(mc)':   lambda a: bool(F[a]['dram_open'] or F[a]['dram_read']),
        'biquad(mc)': lambda a: bool(F[a]['biq']),
        'triplet(mc)': lambda a: bool(F[a]['trip']),
        'lforead(mc)': lambda a: bool(F[a]['lfo']),
        'deficit>0':  lambda a: F[a]['deficit'] > 0,
    }


def sec_vocab(progs, imgs, mrom, F, thresh=0.80):
    print("=== the remaining vocabulary, by co-occurrence\n")
    PRED = predicates(imgs, mrom, F)
    truth = {n: {a: bool(f(a)) for a in imgs} for n, f in PRED.items()}
    hi = collections.defaultdict(set)
    lo = collections.defaultdict(set)
    for a in imgs:
        for x in progs[a]:
            h, c, ad, l = K.fl(x)
            hi[h].add(a)
            lo[l].add(a)
    print(f"{len(hi)} distinct hi12 values, {len(lo)} distinct lo12 values "
          f"over the 38 images.")
    print(f"already assigned: hi12 {len(KNOWN_HI)}, lo12 {len(KNOWN_LO)}\n")
    for label, table, known in (('hi12', hi, KNOWN_HI), ('lo12', lo, KNOWN_LO)):
        print(f"-- UNASSIGNED {label} values, best predicate (|MCC| >= {thresh}"
              " and present in >= 2 images)")
        for v in sorted(table):
            if v in known:
                continue
            s = table[v]
            if len(s) < 2:
                continue
            pred = {a: (a in s) for a in imgs}
            best = max(((mcc(pred, truth[n], imgs), n) for n in truth),
                       key=lambda t: abs(t[0][0]))
            (m, tp, fp, fn, tn), n = best
            if abs(m) >= thresh:
                print(f"   {label} 0x{v:03X}  n={len(s):>2}  {n:12} "
                      f"MCC {m:+.3f}  TP{tp} FP{fp} FN{fn} TN{tn}")
        print(f"\n   -- UNASSIGNED {label} with NO predicate above {thresh}:")
        rest = []
        for v in sorted(table):
            if v in known:
                continue
            s = table[v]
            if len(s) < 2:
                rest.append((v, len(s), 'singleton' if len(s) == 1 else ''))
                continue
            pred = {a: (a in s) for a in imgs}
            m = max(abs(mcc(pred, truth[n], imgs)[0]) for n in truth)
            if m < thresh:
                rest.append((v, len(s), f"best |MCC| {m:.2f}"))
        print("      " + ', '.join(f"0x{v:03X}(n={n})" for v, n, _ in rest))
        print()


# ----------------------------------------------------------------- triplet

def sec_triplet(progs, imgs, mrom, F):
    print("=== the 3-word TABLE-LOOKUP idiom (new)\n")
    print("Idiom:  xxx.0.00.C63   000.6.AA.4CD/407   012.4.01.1CE   -- always")
    print("consecutive, never otherwise.  It is the ONLY use of class 4 and class 6")
    print("in the whole corpus, which is why their per-image counts are equal.\n")
    tot = sum(len(F[a]['trip']) for a in imgs)
    c4 = sum(F[a]['hist'].get(4, 0) for a in imgs)
    c6 = sum(F[a]['hist'].get(6, 0) for a in imgs)
    print(f"   triplets {tot}   class-4 words {c4}   class-6 words {c6}   "
          f"{'ALL ACCOUNTED FOR' if tot == c4 == c6 else 'MISMATCH'}\n")
    PRED = predicates(imgs, mrom, F)
    pred = {a: bool(F[a]['trip']) for a in imgs}
    for n in ('lfo(name)', 'dist(name)'):
        t = {a: bool(PRED[n](a)) for a in imgs}
        print(f"   triplet vs {n:12}: MCC {mcc(pred, t, imgs)[0]:+.3f}")
    t = {a: bool(PRED['lfo(name)'](a) or PRED['dist(name)'](a)) for a in imgs}
    m, tp, fp, fn, tn = mcc(pred, t, imgs)
    print(f"   triplet vs (lfo OR dist)  : MCC {m:+.3f}  TP{tp} FP{fp} FN{fn} TN{tn}")
    print("\n-- the class-6 word's addr8 (the table selector) vs the effect kind")
    tab = collections.defaultdict(collections.Counter)
    for a in imgs:
        for _i, t6 in F[a]['trip']:
            kind = 'dist' if PRED['dist(name)'](a) else 'lfo'
            tab[K.fl(t6)[2]][kind] += 1
    for ad in sorted(tab):
        print(f"   table 0x{ad:02X}: {dict(tab[ad])}")
    print("\n-- the leading word's variants")
    v = collections.Counter()
    for a in imgs:
        for i, _t in F[a]['trip']:
            v[K.fmt(F[a]['words'][i])] += 1
    for k, n in v.most_common():
        print(f"   {k}  x{n}")


# ----------------------------------------------------------------- main

SECTIONS = ['map', 'multitap', 'deficit', 'reverbs', 'compress', 'op76',
            'vocab', 'triplet']


def main(argv):
    if len(argv) < 4:
        sys.exit(__doc__)
    subrom, progdir, mainrom = argv[1], argv[2], argv[3]
    want = [s for s in argv[4:] if s in SECTIONS] or SECTIONS
    progs = K.load_progs(progdir)
    imgs = B.distinct_images(progs)
    rom = P.Rom(subrom, P.SUB_BASE)
    mrom = P.Rom(mainrom, 0)
    F = features(subrom, progs, imgs, rom)
    for s in want:
        print('\n' + '=' * 78)
        if s == 'map':
            sec_map(subrom, progs, imgs, rom, mrom, F)
        elif s == 'multitap':
            sec_multitap(subrom, progs, rom, mrom, F)
        elif s == 'deficit':
            sec_deficit(subrom, progs, imgs, rom, mrom, F)
        elif s == 'reverbs':
            sec_reverbs(subrom, progs, mrom, F)
        elif s == 'compress':
            sec_compress(progs, mrom, F)
        elif s == 'op76':
            sec_op76(imgs, mrom, F)
        elif s == 'vocab':
            sec_vocab(progs, imgs, mrom, F)
        elif s == 'triplet':
            sec_triplet(progs, imgs, mrom, F)


if __name__ == '__main__':
    main(sys.argv)
