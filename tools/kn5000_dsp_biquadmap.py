#!/usr/bin/env python3
"""kn5000_dsp_biquadmap.py -- close the two gaps left by the biquad decode:

  (a) map the FIVE named coefficients (b1, b0, b2, -a1/a0, -a2/a0 -- proven by
      construction in notes/kn5000-dsp-biquad-coeffs.md) onto the SIX class-A
      multiplies of the microcode section, and
  (b) identify the sixth class-A multiply and the class-8 word.

Everything printed here is MEASURED.  Interpretation lives in
notes/kn5000-dsp-biquad-map.md.

Sections:
    section   the 9-word section, its fields, and BOTH cursor walks
    srctest   ** the falsifiable test **: does word [0]'s hi12 track the
              section's position in the band chain / the channel?
    sixth     who writes the 6th word of each algo-39 coefficient block?
              (T1 coverage of the coefficient region, algo 39 vs GEQ)
    class8    corpus survey of class 8: hi12/lo12, host images, positions,
              and the neighbourhood each one sits in
    layout    the assembled per-band memory layout

Usage:
    python3 tools/kn5000_dsp_extract.py <kn5000_subprogram_v142.rom> /tmp/progs
    python3 tools/kn5000_dsp_biquadmap.py <kn5000_subprogram_v142.rom> /tmp/progs \\
            [<kn5000_v10_program.rom>] [section ...]

Reuses tools/kn5000_dsp_biquad.py (section finder, signed addr8), which reuses
kn5000_dsp_class2.py / _coeffs.py / _params.py.  No parsing is re-implemented.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_class2 as K            # noqa: E402
import kn5000_dsp_biquad as B            # noqa: E402
import kn5000_dsp_params as P            # noqa: E402

PEQ = 39
GEQ = 79
SECTION_LEN = B.SECTION_LEN

# the five coefficients the sub-CPU emits, in emission order (biquad-coeffs note
# sect. 3/4, PROVEN BY CONSTRUCTION).  Offsets are relative to the block base NN.
COEFF_ORDER = [('b1', '2^22 Q1.22'), ('b0', '2^22 Q1.22'), ('b2', '2^22 Q1.22'),
               ('-a1/a0', '2^22 Q1.22'), ('-a2/a0', '2^23 Q0.23')]


def s8(a):
    return B.s8(a)


def load(subrom, progdir):
    progs = K.load_progs(progdir)
    imgs = B.distinct_images(progs)
    ref = progs[PEQ][5:5 + SECTION_LEN]
    return progs, imgs, ref


# --------------------------------------------------------------- section

def sec_section(progs, ref):
    print("=== the section, field by field (algo 39 words 5..13)\n")
    print(f"{'idx':>3} {'word':>10}  {'hi12':>4} {'cls':>3} {'addr8':>5} {'lo12':>4}"
          f"  {'sgn':>4}  role")
    role = {5: 'P-consumer (store)', 6: 'class 8, operand-less', 8: 'P-consumer (store)'}
    for k, w in enumerate(ref):
        h, c, a, lo = K.fl(w)
        print(f"[{k}] {w:010X}  {h:03X} {c:>3X}    {a:02X} {lo:>4X}"
              f"  {s8(a):>+4d}  {role.get(k, 'class A multiply')}")

    print("\n-- CURSOR 1: the data/state cursor, addr8 as a signed post-increment")
    print("   (class 8 excluded: its addr8 is the corpus-wide constant 0x16)")
    cur, cells = 0, []
    for k, w in enumerate(ref):
        h, c, a, lo = K.fl(w)
        if c == 8:
            print(f"   [{k}] {K.fmt(w)}   -- excluded --")
            continue
        cells.append((k, cur))
        print(f"   [{k}] {K.fmt(w)}   reads S{cur}   then cursor {cur:+d}{s8(a):+d}"
              f" -> S{cur + s8(a)}")
        cur += s8(a)
    print(f"   per-band total {cur:+d}  (cursor ends at S{cur} = next band's S0)")

    print("\n-- CURSOR 2: the coefficient cursor.  It is NOT in addr8 (see above);")
    print("   the hypothesis under test is 'one implicit +1 per class-A word'.")
    ca = 0
    for k, w in enumerate(ref):
        h, c, a, lo = K.fl(w)
        if c != 0xA:
            print(f"   [{k}] {K.fmt(w)}   class {c:X}: no coefficient fetch")
            continue
        nm = COEFF_ORDER[ca][0] if ca < len(COEFF_ORDER) else 'NN+%d (6th word)' % ca
        print(f"   [{k}] {K.fmt(w)}   coefficient cursor NN+{ca}  = {nm}")
        ca += 1
    print(f"   {ca} class-A words consumed NN+0..NN+{ca - 1}")

    print("\n-- hi12 / lo12 grouping of the six class-A words")
    g = collections.defaultdict(list)
    for k, w in enumerate(ref):
        h, c, a, lo = K.fl(w)
        if c == 0xA:
            g[h].append((k, lo))
    for h in sorted(g):
        print(f"   hi12 {h:03X}: " + "  ".join(f"[{k}] lo12={lo:03X}" for k, lo in g[h]))


# --------------------------------------------------------------- srctest

def sec_srctest(progs, imgs, ref):
    print("=== ** THE FALSIFIABLE TEST ** word [0]'s hi12 vs chain position\n")
    print("PREDICTION (pre-registered, from the brief): in a cascaded biquad chain the")
    print("only per-section difference is where x comes from -- band 1 takes the channel")
    print("input, bands 2..5 take the previous band's output.  If hi12 of word [0] is the")
    print("operand-source field, then WITHIN algorithm 39 the first section of each")
    print("channel must differ from the other four.\n")
    print(f"{'algo':>4} {'name':20} {'#':>2} {'idx':>4}  {'[0]':>13} {'[8]':>13}"
          f"  hi12[0]")
    rows = []
    for a in imgs:
        hits = B.find_sections(progs[a], ref, maxdiff=2)
        if not hits:
            continue
        nm = K.IMG_CAT.get(a, ('?',))[0]
        for n, (i, d) in enumerate(hits):
            w0, w8 = progs[a][i], progs[a][i + 8]
            rows.append((a, nm, n, i, w0, w8))
            print(f"{a:>4} {nm:20} {n:>2} {i:>4}  {K.fmt(w0):>13} {K.fmt(w8):>13}"
                  f"  {K.fl(w0)[0]:03X}")

    print("\n-- RESULT, algorithm 39 only (10 sections = 5 bands x 2 channels):")
    peq = [r for r in rows if r[0] == PEQ]
    hi = [K.fl(r[4])[0] for r in peq]
    print(f"   hi12 of word [0], in program order: {' '.join('%03X' % h for h in hi)}")
    print(f"   distinct values: {sorted(set('%03X' % h for h in hi))}")
    if len(set(hi)) == 1:
        print("   ==> the first band of a channel is NOT distinguished from the others.")
        print("   ==> PREDICTION FALSIFIED: hi12 does not encode chain position.")
    else:
        print("   ==> hi12 varies within algo 39; check whether it is bands 1 vs 2..5.")

    print("\n-- and across images (hi12 -> which images carry it):")
    per = collections.defaultdict(list)
    for a, nm, n, i, w0, w8 in rows:
        per[K.fl(w0)[0]].append(f"{a}:{nm}#{n}")
    for h in sorted(per):
        print(f"   hi12 {h:03X}  x{len(per[h]):<3} {', '.join(per[h])}")

    print("\n-- control: is hi12 of [0] constant within an image?")
    for a in sorted({r[0] for r in rows}):
        v = sorted({'%03X' % K.fl(r[4])[0] for r in rows if r[0] == a})
        print(f"   algo {a:>3} {K.IMG_CAT.get(a, ('?',))[0]:20} {v}")


# --------------------------------------------------------------- sixth

def sec_sixth(rom, mrom):
    print("=== the SIXTH word of each algo-39 coefficient block: who writes it?\n")
    print("The op-0x70 writer emits FIVE data words at NN+0..NN+4 (proven by")
    print("construction).  Algo 39's op-0x70 bases are 00 06 0C 12 18, stride 6, so")
    print("0x05/0x0B/0x11/0x17/0x1D are NOT written by op 0x70.  If the sixth class-A")
    print("multiply reads a sixth coefficient, SOME OTHER opcode in the same T1 map must")
    print("write those five addresses.  This is the test.\n")
    for algo in (PEQ, GEQ, 33, 35, 71, 72, 75, 96, 99):
        t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
        if not t1p or t1p == P.NULL_T1:
            continue
        t1 = P.parse_t1(rom, t1p)
        nm = P.effect_name(mrom, algo) if mrom else '?'
        print(f"-- algo {algo} {nm}   T1={t1p:08X}")
        cover = collections.defaultdict(list)
        for _a, op, ent in t1:
            print(f"     op {op:02X}: " + ' '.join('%02X' % e for e in ent))
            for i, e in enumerate(ent):
                cover[e].append(f"op{op:02X}[{i}]")
        if algo == PEQ:
            print("     coefficient region coverage 0x00..0x1D:")
            for addr in range(0x00, 0x1E):
                owners = cover.get(addr, [])
                inblk = (addr % 6)
                tag = ''
                if 0x70 in [int(o[2:4], 16) for o in owners] if owners else False:
                    pass
                if inblk == 5:
                    tag = '   <-- the PADDING slot'
                print(f"       0x{addr:02X} block{addr // 6} +{inblk}"
                      f"  written by: {owners if owners else 'NOBODY'}{tag}")
        print()


def sec_static(progs, rom):
    """what actually sits in the static coefficient bank of algo 39 / others."""
    print("=== static coefficient banks (op-2 blocks of the load stream)\n")
    import kn5000_dsp_extract as E
    r = E.Rom(rom)
    for algo in (PEQ, GEQ, 33, 35):
        addr = r.u32le(E.PARAM_TABLE + 4 * algo)
        iram, coeffs, ops = E.parse_stream(r, addr)
        print(f"-- algo {algo}: {len(coeffs)} static coefficient words, "
              f"{sum(1 for c in coeffs if c == 0)} of them zero")
        print("   " + ' '.join('%06X' % c for c in coeffs[:48]))
        print()


# --------------------------------------------------------------- class8

def sec_class8(progs, imgs, ref):
    print("=== corpus survey of class 8\n")
    allw = collections.Counter()
    per = collections.defaultdict(list)
    pos = collections.defaultdict(list)
    for a in imgs:
        w = progs[a]
        for i, x in enumerate(w):
            if K.fl(x)[1] == 8:
                allw[x] += 1
                per[x].append(a)
                pos[x].append((a, i))
    print(f"{'word':>13} {'n':>3}  images")
    for x, n in allw.most_common():
        nms = [f"{a}:{K.IMG_CAT.get(a, ('?',))[0]}" for a in sorted(set(per[x]))]
        print(f"{K.fmt(x):>13} {n:>3}  {', '.join(nms)}")

    print("\n-- field decomposition of the class-8 vocabulary")
    for x in sorted(allw):
        h, c, a, lo = K.fl(x)
        print(f"   {K.fmt(x)}  hi12={h:03X} (bin {h:012b})  addr8={a:02X}  lo12={lo:03X}"
              f" (bin {lo:012b})")

    print("\n-- what surrounds each class-8 word (the two words before and after)")
    for x in sorted(allw):
        print(f"   {K.fmt(x)}:")
        ctx = collections.Counter()
        for a, i in pos[x]:
            w = progs[a]
            before = tuple(K.fmt(w[j]) for j in range(max(0, i - 2), i))
            after = tuple(K.fmt(w[j]) for j in range(i + 1, min(len(w), i + 3)))
            ctx[(before, after)] += 1
        for (bef, aft), n in ctx.most_common(6):
            print(f"      x{n:<3} ... {' '.join(bef)}  [{K.fmt(x)}]  {' '.join(aft)} ...")

    print("\n-- class-8 words that are NOT inside a biquad section")
    secidx = {}
    for a in imgs:
        secidx[a] = set()
        for i, d in B.find_sections(progs[a], ref, maxdiff=2):
            secidx[a].update(range(i, i + SECTION_LEN))
    for a in imgs:
        for i, x in enumerate(progs[a]):
            if K.fl(x)[1] == 8 and i not in secidx[a]:
                w = progs[a]
                lo = max(0, i - 3)
                print(f"   algo {a:>3} {K.IMG_CAT.get(a, ('?',))[0]:18} idx {i:>3}"
                      f" {K.fmt(x)}   context: "
                      + ' '.join(('[' + K.fmt(w[j]) + ']') if j == i else K.fmt(w[j])
                                 for j in range(lo, min(len(w), i + 4))))

    print("\n-- class 0 vs class 8 (8 = 0 | multiply bit): the class-0 vocabulary")
    c0 = collections.Counter()
    for a in imgs:
        for x in progs[a]:
            if K.fl(x)[1] == 0:
                c0[x] += 1
    for x, n in c0.most_common(20):
        print(f"   {K.fmt(x)} x{n}")
    print("\n-- do any class-0 and class-8 words differ ONLY in the class nibble?")
    s0 = {x & ~(0xF << 20) for x in c0}
    s8 = {x & ~(0xF << 20) for x in allw}
    both = s0 & s8
    print(f"   {len(both)} such pairs: " +
          ', '.join(K.fmt(x | (0 << 20)) + ' <-> ' + K.fmt(x | (8 << 20)) for x in sorted(both)))

    print("\n-- lo12 of the class-8 words vs lo12 elsewhere in the corpus")
    lo8 = collections.Counter(K.fl(x)[3] for x in allw.elements())
    loall = collections.Counter()
    for a in imgs:
        for x in progs[a]:
            loall[K.fl(x)[3]] += 1
    for lo, n in lo8.most_common():
        cls = collections.Counter()
        for a in imgs:
            for x in progs[a]:
                if K.fl(x)[3] == lo:
                    cls[K.fl(x)[1]] += 1
        print(f"   lo12 {lo:03X}: {n} class-8 uses, {loall[lo]} uses overall, "
              f"classes {dict(sorted(cls.items()))}")


# --------------------------------------------------------------- align

def sec_align(progs, imgs, ref):
    """Every class-8 word, with the 9-word window ALIGNED so that the class-8
    word sits at offset 6 -- the position it occupies in the biquad section.
    This is the near-miss test the 'ROCK ROTARY has no section' anomaly needs."""
    print("=== every class-8 word, window aligned to the section (class 8 at [6])\n")
    for a in imgs:
        w = progs[a]
        for i, x in enumerate(w):
            if K.fl(x)[1] != 8:
                continue
            st = i - 6
            if st < 0 or st + SECTION_LEN > len(w):
                print(f"algo {a:>3} idx {i}: window off the ends")
                continue
            win = w[st:st + SECTION_LEN]
            d = [k for k in range(SECTION_LEN) if win[k] != ref[k]]
            print(f"algo {a:>3} {K.IMG_CAT.get(a, ('?',))[0]:20} idx {i:>3}"
                  f"  window {st:>3}..{st + 8:<3} differs in {len(d)} words {d}")
            print("      " + '  '.join(
                (('*' if k in d else ' ') + K.fmt(win[k])) for k in range(SECTION_LEN)))

    print("\n-- reference: " + '  '.join(' ' + K.fmt(x) for x in ref))

    print("\n-- tally: how well does each class-8 word's aligned window match?")
    tal = collections.defaultdict(collections.Counter)
    for a in imgs:
        w = progs[a]
        for i, x in enumerate(w):
            if K.fl(x)[1] != 8:
                continue
            st = i - 6
            if st < 0 or st + SECTION_LEN > len(w):
                tal[K.fmt(x)]['off-end'] += 1
                continue
            win = w[st:st + SECTION_LEN]
            d = sum(1 for k in range(SECTION_LEN) if win[k] != ref[k])
            tal[K.fmt(x)][d] += 1
    for wd in sorted(tal):
        print(f"   {wd}: " + '  '.join(f"d={k}: {v}" for k, v in sorted(
            tal[wd].items(), key=lambda kv: str(kv[0]))))


def sec_score(progs, imgs):
    """Does class 8 track 'has a tunable filter section' (IMG_CAT filt)?
    A general-purpose shifter should NOT."""
    print("=== class-8 presence scored against the effect-topology labels\n")
    have = {a: any(K.fl(x)[1] == 8 for x in progs[a]) for a in imgs}
    for col, name in ((4, 'filt'), (1, 'dram'), (2, 'lfo'), (3, 'env')):
        tp = fp = fn = tn = 0
        for a in imgs:
            cat = K.IMG_CAT.get(a)
            if not cat:
                continue
            lab = cat[col]
            if have[a] and lab:
                tp += 1
            elif have[a] and not lab:
                fp += 1
            elif not have[a] and lab:
                fn += 1
            else:
                tn += 1
        print(f"   class8 vs {name:5}  TP={tp:>2} FP={fp:>2} FN={fn:>2} TN={tn:>2}"
              f"  MCC={K.mcc(tp, fp, fn, tn):+.3f}")
    print("\n   images WITH a class-8 word:")
    for a in imgs:
        if have[a]:
            print(f"      {a:>3} {K.IMG_CAT.get(a, ('?',))[0]:22} filt="
                  f"{K.IMG_CAT.get(a, (0, 0, 0, 0, 0))[4]}")
    print("\n   filt-labelled images WITHOUT a class-8 word:")
    for a in imgs:
        cat = K.IMG_CAT.get(a)
        if cat and cat[4] and not have[a]:
            print(f"      {a:>3} {cat[0]}")


# --------------------------------------------------------------- layout

def sec_layout(ref):
    print("=== assembled per-band layout (see the note for the argument)\n")
    cur = 0
    print(f"{'idx':>3} {'word':>13} {'coef':>10} {'cell':>5}  reading")
    ca = 0
    for k, w in enumerate(ref):
        h, c, a, lo = K.fl(w)
        if c == 8:
            print(f"[{k}] {K.fmt(w):>13} {'--':>10} {'--':>5}  operand-less")
            continue
        cell = f"S{cur}"
        coef = '--'
        if c == 0xA:
            coef = COEFF_ORDER[ca][0] if ca < len(COEFF_ORDER) else 'NN+%d' % ca
            ca += 1
        print(f"[{k}] {K.fmt(w):>13} {coef:>10} {cell:>5}")
        cur += s8(a)


# --------------------------------------------------------------- main

def main(argv):
    sub = argv[1] if len(argv) > 1 else os.path.expanduser(
        '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
    pdir = argv[2] if len(argv) > 2 else '/tmp/progs'
    mainrom = None
    rest = argv[3:]
    if rest and os.path.exists(rest[0]):
        mainrom = rest[0]
        rest = rest[1:]
    else:
        cand = os.path.expanduser(
            '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom')
        if os.path.exists(cand):
            mainrom = cand
    want = rest or ['section', 'srctest', 'sixth', 'static', 'class8', 'align',
                    'score', 'cursormap', 'decode', 'layout']

    progs, imgs, ref = load(sub, pdir)
    rom = P.Rom(sub, P.SUB_BASE)
    mrom = P.Rom(mainrom, 0) if mainrom else None

    for s in want:
        print('=' * 78)
        if s == 'section':
            sec_section(progs, ref)
        elif s == 'srctest':
            sec_srctest(progs, imgs, ref)
        elif s == 'sixth':
            sec_sixth(rom, mrom)
        elif s == 'static':
            sec_static(progs, sub)
        elif s == 'class8':
            sec_class8(progs, imgs, ref)
        elif s == 'cursormap':
            sec_cursormap(progs, imgs, ref, rom, mrom)
        elif s == 'decode':
            sec_decode(sub, mrom, progs, imgs, ref)
        elif s == 'align':
            sec_align(progs, imgs, ref)
        elif s == 'score':
            sec_score(progs, imgs)
        elif s == 'layout':
            sec_layout(ref)
        else:
            print('unknown section', s)
        print()




# --------------------------------------------------------------- cursormap
# appended: the decisive test of the coefficient-cursor model.

def sec_cursormap(progs, imgs, ref, rom, mrom):
    """PREDICTION (stated before it was run): if the coefficient cursor advances
    by exactly one per class-A word, and is reset to 0 by the 801.0.00.021 rewind,
    then the number of class-A words preceding a biquad section IS the coefficient
    block base that the host writes for that band -- i.e. it must reproduce
    T1[op 0x70] entry by entry."""
    print("=== ** the coefficient cursor, measured against the host's T1 map **\n")
    print("count of class-A words before each biquad section (cursor reset to 0 at")
    print("any 801.0.00.021 rewind) vs the op-0x70 addresses the host writes\n")
    REWIND = 0x801000021
    ok = bad = 0
    for a in imgs:
        t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * a)
        if not t1p or t1p == P.NULL_T1:
            continue
        t1 = P.parse_t1(rom, t1p)
        bases = [e for _ad, op, ent in t1 if op == 0x70 for e in ent]
        hits = [i for i, _d in B.find_sections(progs[a], ref, maxdiff=3)]
        if not hits and not bases:
            continue
        w = progs[a]
        cnt, pred = 0, []
        for i in range(len(w)):
            if i in hits:
                pred.append(cnt)
            if w[i] == REWIND:
                cnt = 0
            if K.fl(w[i])[1] == 0xA:
                cnt += 1
        nm = P.effect_name(mrom, a) if mrom else K.IMG_CAT.get(a, ('?',))[0]
        b = bases[:len(pred)]
        match = (list(b) == pred)
        ok += match
        bad += (not match)
        print(f"algo {a:>3} {nm:20}")
        print(f"    sections at        {hits}")
        print(f"    class-A prefix     {pred}")
        print(f"    host op70 bases    {['0x%02X' % x for x in bases]}")
        print(f"    -> {'MATCH' if match else 'no match'}")
    print(f"\n   {ok} images match, {bad} do not")


# --------------------------------------------------------------- decode
# The static coefficient bank, read with the NAMED slot order.  This is the
# test that can fail: a wrong slot order gives filters that are unstable or
# whose numerators have no recognisable shape.

def sbank(rom, algo):
    """(base, [24-bit words]) of every op-2 block of an algorithm's parameter
    stream, with the base taken from the preceding op-1 pointer word
    (801.0.NN.821, the proven pointer load)."""
    import kn5000_dsp_extract as E
    r = E.Rom(rom)
    p = r.u32le(E.PARAM_TABLE + 4 * algo)
    out, base = [], None
    for _ in range(64):
        try:
            b0, b1 = r.u8(p), r.u8(p + 1)
        except IndexError:
            break
        op = b0 >> 4
        if op == 0xF:
            break
        ln = ((b0 & 0xF) << 8) | b1
        if ln < 2 or ln > 0xFFF:
            break
        body = r.slice(p + 2, ln - 2)
        if op == 1 and len(body) >= 8:
            w = int.from_bytes(body[3:8], 'big')
            h, c, a, lo = K.fl(w)
            if h == 0x801 and lo in (0x821, 0x021):
                base = a
        elif op == 2 and len(body) >= 3:
            d = body[3:]
            ws = [(d[k] << 16) | (d[k + 1] << 8) | d[k + 2]
                  for k in range(0, len(d) - 2, 3)]
            out.append((base, ws))
        p += ln
    return out


def q(v, sh):
    return (v - (1 << 24) if v & 0x800000 else v) / float(1 << sh)


def invert(block):
    """block = 6 raw words.  Slots +0..+4 = b1, b0, b2, -a1/a0, -a2/a0 with
    Q1.22 except the last (Q0.23).  Returns a dict of derived quantities."""
    b1 = q(block[0], 22)
    b0 = q(block[1], 22)
    b2 = q(block[2], 22)
    a1 = -q(block[3], 22)
    a2 = -q(block[4], 23)
    d = dict(b0=b0, b1=b1, b2=b2, a1=a1, a2=a2, sixth=block[5])
    d['stable'] = abs(a2) < 1 and abs(a1) < 1 + a2
    dcn, dcd = b0 + b1 + b2, 1 + a1 + a2
    nyn, nyd = b0 - b1 + b2, 1 - a1 + a2
    d['dc'] = dcn / dcd if dcd else float('inf')
    d['ny'] = nyn / nyd if nyd else float('inf')
    # 4/a0 = 1 - a1 + a2 ; 4K^2/a0 = 1 + a1 + a2   (bilinear-transform identity)
    import math
    if nyd > 0 and dcd / nyd > 0:
        a0 = 4.0 / nyd
        k2 = dcd * a0 / 4.0
        if k2 > 0:
            kk = math.sqrt(k2)
            d['f0'] = math.atan(kk) * 44100.0 / math.pi
            koq = a0 - 1.0 - k2
            d['Q'] = kk / koq if koq else float('inf')
            d['K'] = kk
    return d


def sec_decode(rom, mrom, progs, imgs, ref):
    print("=== the STATIC coefficient banks, inverted with the named slot order\n")
    print("slot +0 = b1, +1 = b0, +2 = b2, +3 = -a1/a0 (all Q1.22), +4 = -a2/a0 (Q0.23),")
    print("+5 = the sixth word.  f0/Q are recovered from the bilinear identities")
    print("4/a0 = 1 - a1 + a2 and 4K^2/a0 = 1 + a1 + a2, K = tan(pi f0/44100).\n")
    for algo, offs in ((PEQ, [0, 6, 12, 18, 24]), (33, [2, 11]), (35, [3, 14])):
        nm = P.effect_name(mrom, algo) if mrom else '?'
        print(f"-- algo {algo} {nm}   (biquad bases from the class-A prefix count)")
        for base, ws in sbank(rom, algo):
            if len(ws) < 6:
                print(f"   pointer 0x{base:02X}: {' '.join('%06X' % x for x in ws)}"
                      f"   (short block, not a biquad)")
                continue
            for o in offs:
                if base is None or o + 6 > len(ws) + base:
                    continue
                blk = ws[o - base:o - base + 6] if base <= o else None
                if not blk or len(blk) < 6:
                    continue
                d = invert(blk)
                print(f"   +{o:02X}: " + ' '.join('%06X' % x for x in blk))
                print(f"        b = [{d['b0']:+.6f} {d['b1']:+.6f} {d['b2']:+.6f}]"
                      f"  a = [1 {d['a1']:+.6f} {d['a2']:+.6f}]"
                      f"  {'STABLE' if d['stable'] else 'UNSTABLE'}")
                print(f"        f0 = {d.get('f0', float('nan')):9.1f} Hz   "
                      f"Q = {d.get('Q', float('nan')):8.4f}   "
                      f"DC gain = {d['dc']:+.4f}   Nyquist gain = {d['ny']:+.4f}   "
                      f"6th word = {d['sixth']:06X} "
                      f"(Q1.22 {q(d['sixth'], 22):+.4f} / Q0.23 {q(d['sixth'], 23):+.4f})")
                print(f"        numerator shape: b1/b0 = {d['b1'] / d['b0']:+.5f}   "
                      f"b2/b0 = {d['b2'] / d['b0']:+.5f}"
                      + ("   <== LOWPASS (1,2,1)" if abs(d['b1'] / d['b0'] - 2) < 2e-3
                         and abs(d['b2'] / d['b0'] - 1) < 2e-3 else "")
                      + ("   <== BANDPASS (1,0,-1)" if abs(d['b1']) < 1e-5
                         and abs(d['b2'] / d['b0'] + 1) < 2e-3 else ""))
        print()

    print("-- permutation control: how many of the 120 slot orders leave every")
    print("   one of these blocks stable, and how many reproduce a recognisable")
    print("   numerator shape?  (the falsifier for the named order)")
    import itertools
    blocks = []
    for algo, offs in ((PEQ, [0, 6, 12, 18, 24]), (33, [2, 11]), (35, [3, 14])):
        for base, ws in sbank(rom, algo):
            if len(ws) < 6 or base is None:
                continue
            for o in offs:
                b = ws[o - base:o - base + 6]
                if len(b) == 6:
                    blocks.append(b)
    import struct
    fr = open(os.path.expanduser(rom), 'rb').read()
    def f32(a):
        return struct.unpack_from('<f', fr, a - 0xEF00)[0]
    FT = [f32(0x012397 + 4 * i) for i in range(27)]
    QT = [f32(0x012403 + 4 * i) for i in range(32)]
    good, best = [], []
    for perm in itertools.permutations(range(5)):
        okall = True
        for b in blocks:
            bb = [b[perm[i]] for i in range(5)] + [b[5]]
            if not invert(bb)['stable']:
                okall = False
                break
        if okall:
            good.append(perm)
            fine = True
            for b in blocks:
                bb = [b[perm[i]] for i in range(5)] + [b[5]]
                d = invert(bb)
                f0, qq = d.get('f0'), d.get('Q')
                if f0 is None or qq is None:
                    fine = False
                    break
                if min(abs(f0 - t) / t for t in FT) > 2e-3:
                    fine = False
                if qq <= 0 or qq > 30.0:
                    fine = False
                if not fine:
                    break
            if fine:
                best.append(perm)
    print(f"   {len(blocks)} blocks; {len(good)} of 120 slot orders keep them all stable;")
    print(f"   {len(best)} of 120 ALSO put every recovered f0 on an ISO-table centre")
    print(f"   (0.2% tol) and every recovered Q inside the designer's 0.1..20 range:")
    for perm in best:
        names = ['b1', 'b0', 'b2', '-a1', '-a2']
        print("      *** slots +0..+4 = "
              + ' '.join(names[perm.index(i)] for i in range(5))
              + ("   <== the emission order" if perm == (0, 1, 2, 3, 4) else ""))
    print()
    for perm in good:
        names = ['b1', 'b0', 'b2', '-a1', '-a2']
        print("      slots +0..+4 = " + ' '.join(names[perm.index(i)] for i in range(5))
              + ("   <== the emission order" if perm == (0, 1, 2, 3, 4) else ""))


if __name__ == '__main__':
    main(sys.argv)
