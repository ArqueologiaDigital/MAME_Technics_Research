#!/usr/bin/env python3
"""KN5000 -- is the per-selector log-pitch constant C DERIVABLE, or is it irreducible
per-recording data?  Regenerates every number quoted in the 2026-08-19 derivability probe.

Answers, in order:
  1. What C is made of            -- coarse (per-SET) vs zone_trim (per-zone); they are DISJOINT.
  2. The flags-bit1 EXTRACTION BUG -- 112 selectors carry a fabricated +49/+57/+65 semitone C.
     Ground truth: kn5000_subprogram_v142.asm:16216-16260.  When SET[+0x00] bit1 is set the
     firmware substitutes the literal 0x4280 for BOTH the root pivot AND basepitch, so the
     (basepitch - root_pivot) term is identically ZERO and neither operand is ever read.
     Falsified four ways below (raw ROM bytes, octave-fold, live capture register, exactness).
  3. Is C a function of (root, kmin, kmax, flags)?  -- NO.
  4. Is C a function of the chunk (class, entry)?   -- YES, 94.7% / 99.7%.
  5. Compact representations + the Shannon floor.

Usage:  python3 kn5000_pitch_C_derivability.py
Inputs (all committed):
    kn7000_mame/notes/data/kn5000-multisample-sets.tsv
    kn7000_mame/notes/data/kn5000-patch-partials.tsv
    kn7000_mame/tools/kn5000-rootpitch/kon.log        (5956 captured demo note-ons)
    roms/kn5000/kn5000_table_data_rom_{even.ic3,odd.ic1}
Stdlib only.  Read-only.
"""
import collections, math, os, sys
from functools import reduce
from math import gcd

REPO = os.environ.get('KN7000_MAME', os.path.expanduser('~/compartilhado/kn7000_mame'))
ROMS = os.environ.get('KN5000_ROMS', os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000'))
SETS = os.path.join(REPO, 'notes/data/kn5000-multisample-sets.tsv')
KON  = os.path.join(REPO, 'tools/kn5000-rootpitch/kon.log')


def read_sets():
    """SET descriptors.  Returns dicts with the zone list carrying BOTH C variants:
         C_shipped = (basepitch - ((root<<8)+0x80)) + trim      (what the .hxx ships)
         C_fixed   = 0 + trim  when SET[+0].bit1, else C_shipped (what the firmware does)"""
    rows = [l.rstrip('\n').split('\t') for l in open(SETS)]
    hdr, rows = rows[0], rows[1:]
    ix = {k: i for i, k in enumerate(hdr)}
    out = []
    for r in rows:
        st = int(r[ix['stride']]); fl = int(r[ix['flags']], 16)
        root = int(r[ix['root']], 16); base = int(r[ix['basepitch']], 16)
        piv = (root << 8) + 0x80
        zs = r[ix['zones(lo-hi:class:entry)']]; ft = r[ix['finetune(E:hex)']]
        if not zs:
            continue
        fts = {}
        if ft:
            for f in ft.split(';'):
                k, v = f.split(':'); fts[int(k)] = v
        zones = []
        for i, z in enumerate(zs.split(';')):
            rng, cls, ent = z.split(':'); lo, hi = [int(x) for x in rng.split('-')]
            trim = 0
            if st == 6 and i in fts:                 # zone rec[+0x04..05], asm 16261-16266
                b = bytes.fromhex(fts[i]); trim = b[2] | (b[3] << 8)
                if trim >= 0x8000: trim -= 0x10000
            coarse = base - piv
            zones.append(dict(lo=lo, hi=hi, cls=int(cls), ent=int(ent, 16), trim=trim,
                              coarse=coarse,
                              C_shipped=coarse + trim,
                              C_fixed=(0 + trim) if (fl & 2) else (coarse + trim)))
        out.append(dict(sid=r[ix['set_idx']], stride=st, flags=fl, root=root, base=base, piv=piv,
                        kmin=int(r[ix['kmin']], 16), kmax=int(r[ix['kmax']], 16), zones=zones))
    return out


def per_selector(sets, key):
    """+0x040 selector -> Counter{C: key-span weight}."""
    W = collections.defaultdict(collections.Counter)
    for x in sets:
        for z in x['zones']:
            W[(z['cls'] << 12) | z['ent']][z[key]] += z['hi'] - z['lo'] + 1
    return W


def fold(v, kmin, kmax):
    """Pitch_Fold_Octaves_Into_Range, asm:14585 -- +-0x0C00 until inside [kmin,kmax] pitch."""
    lo = (kmin << 8) + 0x80; hi = (kmax << 8) + 0x80; n = 0
    while v > hi and n < 64: v -= 0x0C00; n += 1
    while v < lo and n < 64: v += 0x0C00; n += 1
    return n


def main():
    s = read_sets()
    nz = sum(len(x['zones']) for x in s)
    print("== 0. corpus ==")
    print("   %d SETs, %d zones, %d distinct +0x040 selectors"
          % (len(s), nz, len(per_selector(s, 'C_fixed'))))
    print("   stride: %s   flags: %s"
          % (dict(collections.Counter(x['stride'] for x in s)),
             dict(collections.Counter('%02X' % x['flags'] for x in s))))

    print("\n== 1. C = (basepitch - ((root<<8)+0x80)) + zone_trim: the two terms are DISJOINT ==")
    nc = sum(1 for x in s for z in x['zones'] if z['coarse'])
    nt = sum(1 for x in s for z in x['zones'] if z['trim'])
    nb = sum(1 for x in s for z in x['zones'] if z['coarse'] and z['trim'])
    print("   coarse != 0 : %4d zones (%.1f%%), %d distinct values" %
          (nc, 100 * nc / nz, len({z['coarse'] for x in s for z in x['zones']})))
    print("   trim   != 0 : %4d zones (%.1f%%), %d distinct values" %
          (nt, 100 * nt / nz, len({z['trim'] for x in s for z in x['zones']})))
    print("   BOTH   != 0 : %4d zones   <-- disjoint populations" % nb)
    roots = collections.Counter('%02X' % x['root'] for x in s if not (x['flags'] & 2))
    print("   root over the %d SETs whose root the firmware actually READS: %s"
          % (sum(roots.values()), dict(roots)))
    print("   -> root has ZERO variance; C is literally  basepitch - 0x4280 + zone_trim")

    print("\n== 2. THE flags-bit1 EXTRACTION BUG (asm 16216-16260) ==")
    b1 = [x for x in s if x['flags'] & 2]
    print("   %d SETs have SET[+0x00] bit1 set: sids %s"
          % (len(b1), ','.join(x['sid'] for x in b1)))
    print("   all have basepitch=0x%04X, root in %s -> fabricated C in %s"
          % (b1[0]['base'], sorted({'%02X' % x['root'] for x in b1}),
             sorted({x['base'] - x['piv'] for x in b1})))
    print("   2a. RAW ROM: descriptor byte 0")
    try:
        ev = open(os.path.join(ROMS, 'kn5000_table_data_rom_even.ic3'), 'rb').read()
        od = open(os.path.join(ROMS, 'kn5000_table_data_rom_odd.ic1'), 'rb').read()
        img = bytearray(0x200000)
        for i in range(0, len(ev), 2):
            j = (i // 2) * 4
            img[j:j + 2] = ev[i:i + 2]; img[j + 2:j + 4] = od[i:i + 2]
        for sid in (0, 49, 66):
            o = 0x57914 + 15 * sid
            print("       sid %3d @ %06X : %s" % (sid, o, ' '.join('%02x' % b for b in img[o:o + 15])))
    except OSError as e:
        img = None
        print("       (table-data ROM unavailable: %s)" % e)
    print("   2b. OCTAVE-FOLD: under the shipped C the firmware would have to fold; under the fix it never does")
    for tag, key in (('shipped', 'coarse'), ('fixed  ', None)):
        tf = tt = 0
        for x in b1:
            for k in range(x['kmin'], x['kmax'] + 1):
                c = (x['base'] - x['piv']) if key else 0
                tt += 1; tf += fold(256 * k + 0x80 + c, x['kmin'], x['kmax']) > 0
        print("       %s C : %4d of %4d in-range keys need an octave fold (%.1f%%)"
              % (tag, tf, tt, 100 * tf / tt))
    tf = tt = 0
    for x in s:
        if x['flags'] & 2: continue
        for z in x['zones']:
            for k in range(max(z['lo'], x['kmin']), min(z['hi'], x['kmax']) + 1):
                tt += 1; tf += fold(256 * k + 0x80 + z['coarse'], x['kmin'], x['kmax']) > 0
    print("       control (non-bit1 SETs)     : %d of %d (%.1f%%)" % (tf, tt, 100 * tf / tt))

    Wo = per_selector(s, 'C_shipped'); Wf = per_selector(s, 'C_fixed')
    old = {k: v.most_common(1)[0][0] for k, v in Wo.items()}
    new = {k: v.most_common(1)[0][0] for k, v in Wf.items()}
    diff = {k for k in old if old[k] != new[k]}
    print("   2c/2d. LIVE CAPTURE (%s)" % os.path.basename(KON))
    try:
        R = []
        n = 0
        for l in open(KON):
            p = l.split()
            if p[0] != 'KON' or len(p) < 5: continue
            n += 1
            sel = int(p[3], 16); pit = int(p[4], 16)
            if pit and sel in diff:
                R.append(((pit - 0x80 - old[sel]) / 256.0, (pit - 0x80 - new[sel]) / 256.0))
        print("       %d note-ons; %d (%.2f%%) hit a selector the fix changes" % (n, len(R), 100 * len(R) / n))
        print("       decoded register : shipped MIDI %.0f..%.0f   fixed MIDI %.0f..%.0f"
              % (min(a for a, _ in R), max(a for a, _ in R),
                 min(b for _, b in R), max(b for _, b in R)))
        for tol, lbl in ((0.5 / 256, 'EXACT (<0.4 cent)'), (0.02, '+-5 cents')):
            a = sum(1 for x, _ in R if abs(x - round(x)) <= tol)
            b = sum(1 for _, y in R if abs(y - round(y)) <= tol)
            print("       integer-MIDI, %-18s: shipped %3d/%d   fixed %3d/%d" % (lbl, a, len(R), b, len(R)))
        print("       (the shipped values are all X*256-1, so a +-5-cent metric is BLIND to a")
        print("        49-65 semitone error -- only the EXACT gate can see it)")
    except OSError as e:
        print("       (capture unavailable: %s)" % e)

    print("\n== 3. is C a function of (root, kmin, kmax, flags)?  NO ==")
    bys = collections.defaultdict(set)
    for x in s:
        for z in x['zones']: bys[x['sid']].add(z['C_fixed'])
    multi = sum(1 for v in bys.values() if len(v) > 1)
    print("   %d of %d SETs carry MORE THAN ONE C internally (max %d) while root/kmin/kmax/flags"
          % (multi, len(bys), max(len(v) for v in bys.values())))
    print("   are constant within a SET -> C cannot be a function of them.")
    byc = collections.defaultdict(collections.Counter)
    for k, v in new.items(): byc[k >> 12][v] += 1
    hit = sum(c.most_common(1)[0][1] for c in byc.values())
    print("   class alone 'predicts' %d/%d = %.1f%% -- but only by always answering 0,"
          % (hit, len(new), 100 * hit / len(new)))
    print("   which is exactly the C==0 base rate: zero information beyond the prior.")

    print("\n== 4. is C a function of the CHUNK (class,entry)?  YES ==")
    byc2 = collections.defaultdict(set)
    for x in s:
        for z in x['zones']: byc2[(z['cls'], z['ent'])].add(z['C_fixed'])
    one = sum(1 for v in byc2.values() if len(v) == 1)
    print("   %d of %d chunks single-valued (%.1f%%)" % (one, len(byc2), 100 * one / len(byc2)))
    b6 = collections.defaultdict(set)
    for x in s:
        if x['stride'] != 6: continue
        for z in x['zones']: b6[(z['cls'], z['ent'])].add(z['trim'])
    o6 = sum(1 for v in b6.values() if len(v) == 1)
    print("   restricted to stride-6 (where the data actually varies per zone):"
          " %d of %d (%.1f%%)" % (o6, len(b6), 100 * o6 / len(b6)))
    c7 = {z['ent']: z['trim'] for x in s if x['stride'] == 6 for z in x['zones'] if z['cls'] == 7}
    dup = sum(1 for e in range(0x10) if c7.get(e) == c7.get(e + 0x10) and e in c7)
    print("   class 7: trim(e) == trim(e+0x10) for %d/16 entries -- a velocity-layer DUPLICATE"
          % dup)
    print("   of the same recordings carrying the same constants.")

    print("\n== 5. the values are MEASURED, not designed ==")
    vals = sorted({v for v in new.values() if v})
    gaps = [b - a for a, b in zip(vals, vals[1:])]
    print("   %d distinct nonzero C, range %d..%d, gcd %d"
          % (len(vals), vals[0], vals[-1], reduce(gcd, [abs(v) for v in vals])))
    print("   nearest-neighbour gap: min %d unit(s) (%.2f cent), median %d, %d of %d gaps <= 5 units"
          % (min(gaps), min(gaps) * 100 / 256.0, sorted(gaps)[len(gaps) // 2],
             sum(1 for g in gaps if g <= 5), len(gaps)))
    print("   whole semitones (mult of 256): %d of %d distinct values (%.1f%%)"
          % (sum(1 for v in vals if v % 256 == 0), len(vals),
             100 * sum(1 for v in vals if v % 256 == 0) / len(vals)))

    print("\n== 6. compact representations ==")
    nzsel = {k: v for k, v in new.items() if v}
    tot = sum(sum(v.values()) for v in Wf.values())
    z = sum(sum(Wf[k].values()) for k in new if not new[k])
    print("   after the bit1 fix: %d of %d selectors have C == 0 (%.1f%%), key weight %.1f%%"
          % (len(new) - len(nzsel), len(new), 100 * (len(new) - len(nzsel)) / len(new), 100 * z / tot))
    runs = []
    for cl in range(16):
        ks = sorted(e for c, e in ((k >> 12, k & 0xFFF) for k in nzsel) if c == cl)
        i = 0
        while i < len(ks):
            j = i
            while j + 1 < len(ks) and ks[j + 1] == ks[j] + 1 and \
                  nzsel[(cl << 12) | ks[j + 1]] == nzsel[(cl << 12) | ks[i]]: j += 1
            runs.append((cl, ks[i], ks[j])); i = j + 1
    cnt = collections.Counter(nzsel.values()); n = len(nzsel)
    H = -sum(c / n * math.log2(c / n) for c in cnt.values())
    print("   A. shipped   : 1444 x {u16,i16,u8} padded 6 B = %d B" % (1444 * 6))
    print("   B. exceptions: %d x {u16 sel, i16 c}          = %d B   <-- recommended" % (n, 4 * n))
    print("   C. run-length: %d runs x {u16,u8,i16}         = %d B" % (len(runs), 5 * len(runs)))
    print("   D. pool+index: %d distinct x2 + %d x{u16,u8}  = %d B" % (len(vals), n, 2 * len(vals) + 3 * n))
    print("   Shannon floor of the value stream: %.2f bit/entry x %d = %.0f B" % (H, n, H * n / 8))

    print("\n== 7. intrinsic accuracy floor of ANY selector-keyed C ==")
    wrong = sum(sum(w for C, w in v.items() if C != v.most_common(1)[0][0]) for v in Wf.values())
    big = sum(w for v in Wf.values() for C, w in v.items()
              if C != v.most_common(1)[0][0] and abs(C - v.most_common(1)[0][0]) >= 256)
    print("   modal C is WRONG for %d of %d key slots = %.2f%% (%.2f%% by >= 1 semitone)."
          % (wrong, tot, 100 * wrong / tot, 100 * big / tot))
    print("   That is a property of the firmware data, not of the representation:")
    print("   a table, a runtime walk and a hypothetical formula all inherit it.")


if __name__ == '__main__':
    main()
