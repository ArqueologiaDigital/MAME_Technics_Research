#!/usr/bin/env python3
"""KN5000 IC303 PITCH-PATH audit — regenerates every number in
notes/audit/kn5000-audit-pitch.md from the firmware tables + the IC307 dump.

Nothing here is heuristic: the per-zone constant C comes straight out of the
firmware's 487 multisample SET descriptors, and the fundamental period is the
HLE's own detect_period() re-implemented verbatim so the two agree.

    C(zone) = (SET.basepitch - ((SET.root<<8)+0x80)) + trim(zone)
    +0x400  = (key<<8) + 0x80 + C            (with no transposes)
    trim    = zone record[+0x04..05] for stride-6 SETs, 0 for stride-4  (asm L14295-14361)

Usage:  python3 tools/kn5000_pitch_audit.py [--emit-table]
        (--emit-table rewrites notes/data/kn5000-pitch-trim-table.tsv)

Stdlib only.  Run from the kn7000_mame checkout.
"""
import bisect, collections, math, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SETS = os.path.join(REPO, 'notes/data/kn5000-multisample-sets.tsv')
PARTIALS = os.path.join(REPO, 'notes/data/kn5000-patch-partials.tsv')
TABLE = os.path.join(REPO, 'notes/data/kn5000-pitch-trim-table.tsv')
ROMDIR = os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000')
IC307 = os.path.join(ROMDIR, 'kn5000_waveform_rom.ic307')
PAGE = 0x100000


# ---------------------------------------------------------------- SET descriptors
def read_sets():
    """-> list of (set_idx, stride, flags, kmin, kmax, root, basepitch, [(lo,hi,cls,entry,C)])"""
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
            if st == 6 and i in fts:            # asm LABEL_022AC5 L14341: 293Eh = rec[+0x04]
                b = bytes.fromhex(fts[i]); trim = b[2] | (b[3] << 8)
                if trim >= 0x8000: trim -= 0x10000
            zones.append((lo, hi, int(cls), int(ent, 16), (base - piv) + trim))
        out.append((r[ix['set_idx']], st, fl, int(r[ix['kmin']], 16), int(r[ix['kmax']], 16),
                    root, base, zones))
    return out


def trim_table(sets):
    """+0x040 selector -> Counter{C: key weight}."""
    W = collections.defaultdict(collections.Counter)
    for _, st, fl, kmin, kmax, root, base, zones in sets:
        for lo, hi, cls, ent, C in zones:
            W[(cls << 12) | ent][C] += (hi - lo + 1)
    return W


# ---------------------------------------------------------------- IC307 geometry
def parse_page(d, base):
    """Same six acceptance checks as kn5000_tonegen.cpp::parse_page_directories()."""
    u16 = lambda o: d[base + o] | (d[base + o + 1] << 8)
    head = u16(0)
    if head == 0 or head & 3 or head // 4 * 4 > PAGE - 4:
        return None
    n = head // 4
    param, wave = [], []
    for i in range(n):
        p, w = u16(i * 4), u16(i * 4 + 2)
        if (i and p < param[-1]) or p < n * 4 or w * 16 >= PAGE or u16(p) != w:
            return None
        param.append(p); wave.append(w)
    srt = sorted(set(wave))
    start, samples = [], []
    for i in range(n):
        j = bisect.bisect_right(srt, wave[i])
        end = PAGE if j >= len(srt) else srt[j] * 16
        off = wave[i] * 16
        start.append(base + off)
        samples.append((end - off) // 2 if end > off else 0)
    return dict(count=n, start=start, samples=samples)


def detect_period(d, start, samples):
    """Verbatim port of kn5000_tonegen_device::detect_period(), in float samples (0 = aperiodic)."""
    if samples < 32:
        return float(samples)
    off = samples // 3; W = min(samples - off, 4096)
    if W < 64:
        off = 0; W = min(samples, 4096)
    minlag = 4; maxlag = min(W // 2, 2048)
    if maxlag <= minlag:
        return float(samples)
    x = []
    for i in range(W):
        bp = start + (off + i) * 2
        if bp + 1 >= len(d): break
        v = d[bp] | (d[bp + 1] << 8)
        x.append(float(v - 65536 if v >= 32768 else v))
    n = len(x)
    if n <= minlag * 2 + 4:
        return float(samples)
    m = sum(x) / n
    x = [v - m for v in x]
    if sum(v * v for v in x) < 1.0:
        return float(samples)
    hi = min(maxlag, n - 1)
    ps = [0.0] * (n + 1)
    for i, v in enumerate(x):
        ps[i + 1] = ps[i] + v * v
    r = [-2.0] * (hi + 1)
    for lag in range(minlag, hi + 1):
        c = 0.0; L = n - lag
        for i in range(L):
            c += x[i] * x[i + lag]
        den = math.sqrt(ps[L] * (ps[n] - ps[lag]))
        r[lag] = c / den if den > 1.0 else -2.0
    cross = 0
    for lag in range(minlag, hi + 1):
        if r[lag] < 0.0:
            cross = lag; break
    if cross == 0:
        return float(samples) if samples <= 2048 else 0.0
    peak = max(r[cross:hi + 1])

    def refine(lag):
        frac = 0.0
        if lag > minlag and lag + 1 <= hi:
            y0, y1, y2 = r[lag - 1], r[lag], r[lag + 1]
            den = y0 - 2 * y1 + y2
            if abs(den) > 1e-12:
                frac = max(-0.5, min(0.5, 0.5 * (y0 - y2) / den))
        return max(1.0, lag + frac)

    if peak >= 0.5:
        for lag in range(cross + 1, hi):
            if r[lag] >= 0.92 * peak and r[lag] >= r[lag - 1] and r[lag] >= r[lag + 1]:
                return refine(lag)
        for lag in range(cross, hi + 1):
            if r[lag] >= 0.92 * peak:
                return refine(lag)
    return float(samples) if samples <= 2048 else 0.0


# ---------------------------------------------------------------- the audit checks
def main():
    sets = read_sets()
    W = trim_table(sets)
    tot = sum(sum(c.values()) for c in W.values())
    amb = [s for s, c in W.items() if len(c) > 1]
    ambmass = sum(sum(W[s].values()) for s in amb)
    modal_wrong = sum(sum(w for C, w in W[s].items() if C != W[s].most_common(1)[0][0]) for s in amb)
    print("== 1. per-selector constant C ==")
    print("   %d SETs, %d zones, %d distinct +0x040 selectors" % (len(sets), sum(len(z[7]) for z in sets), len(W)))
    print("   single-valued: %d (%.1f%%)   ambiguous: %d (key mass %.1f%%, modal still wrong %.2f%%)"
          % (len(W) - len(amb), 100 * (len(W) - len(amb)) / len(W), len(amb),
             100 * ambmass / tot, 100 * modal_wrong / tot))

    print("\n== 2. HLE uncorrelated-voice fallback (kn5000_tonegen.cpp:772, anchor 0x3524) ==")
    errs = sorted((60 + (C - 13476) / 256.0, w) for c in W.values() for C, w in c.items())
    acc = 0; pct = {}
    for e, w in errs:
        acc += w
        for p in (1, 5, 25, 50, 75, 95, 99):
            if p not in pct and acc >= tot * p / 100:
                pct[p] = e
    print("   rendered-minus-true, semitones:", {p: "%+.2f" % v for p, v in sorted(pct.items())})
    print("   min %+.2f  max %+.2f   within +-0.5 semitone: %.1f%% of key slots"
          % (errs[0][0], errs[-1][0], 100 * sum(w for e, w in errs if abs(e) <= 0.5) / tot))

    print("\n== 3. voice_pitch_index() monotonicity (kn5000_tonegen.cpp:365-368) ==")
    bad = 0; ex = []
    for sid, st, fl, kmin, kmax, root, base, zones in sets:
        km = {}
        for lo, hi, cls, ent, C in zones:
            for k in range(lo, min(hi, 127) + 1):
                km[k] = (ent, C)
        prev = pk = None; broke = False
        for k in range(128):
            if k not in km: continue
            ent, C = km[k]
            V = max(0, min(0x7FFF, 256 * k + 0x80 + C))
            idx = (ent & 0x0F) * 0x100000 + V
            if prev is not None and idx < prev and not broke:
                ex.append((sid, pk, k, prev, idx)); broke = True
            prev, pk = idx, k
        bad += broke
    print("   NON-monotonic in %d of %d SETs (%.0f%%)" % (bad, len(sets), 100 * bad / len(sets)))
    for e in ex[:5]:
        print("     SET %s key %d->%d : 0x%08X -> 0x%08X" % e)

    print("\n== 4. partial-block census (key follow / coarse / fine) ==")
    try:
        ev = open(os.path.join(ROMDIR, 'kn5000_table_data_rom_even.ic3'), 'rb').read()
        od = open(os.path.join(ROMDIR, 'kn5000_table_data_rom_odd.ic1'), 'rb').read()
        img = bytearray(0x200000)
        for i in range(0, len(ev), 2):                     # ROM_LOAD32_WORD, kn5000.cpp:1166-1167
            j = (i // 2) * 4
            img[j:j + 2] = ev[i:i + 2]; img[j + 2:j + 4] = od[i:i + 2]
        rows = [l.rstrip('\n').split('\t') for l in open(PARTIALS)]
        ix = {k: i for i, k in enumerate(rows[0])}
        kf = collections.Counter(); nc = nf = n = 0
        for r in rows[1:]:
            o = int(r[ix['region_off']], 16)
            if o + 8 >= len(img): continue
            kf[img[o + 6] & 7] += 1
            nc += (img[o + 4] != 0); nf += (img[o + 5] != 0); n += 1
        print("   blk[+0x06]&7 (key follow):", dict(sorted(kf.items())))
        print("   NOT full key-follow: %d of %d (%.1f%%)   FIXED pitch (==7): %d"
              % (n - kf[0], n, 100 * (n - kf[0]) / n, kf.get(7, 0)))
        print("   coarse blk[+0x04] nonzero: %d   fine blk[+0x05] nonzero: %d" % (nc, nf))
    except OSError as e:
        print("   (table-data ROM unavailable: %s)" % e)

    print("\n== 5. IC307 page law  K = C + 0x80 - 3072*log2(period) ==")
    try:
        d = open(IC307, 'rb').read()
    except OSError as e:
        print("   (IC307 unavailable: %s)" % e); return
    pages = {p: parse_page(d, p * PAGE) for p in range(4)}
    per = {}

    def P(cls, e):
        pg = pages[cls & 3]
        if not pg or e >= pg['count']: return None
        k = (cls & 3, e)
        if k not in per:
            per[k] = detect_period(d, pg['start'][e], pg['samples'][e])
        return per[k] or None

    for cls in (4, 5, 6, 7):
        ks = [((list(c)[0] + 128 - 3072 * math.log2(P(cls, s & 0xFFF))) % 3072)
              for s, c in W.items() if s >> 12 == cls and len(c) == 1 and P(cls, s & 0xFFF)]
        if not ks: continue
        Kp = min(ks, key=lambda a: sum(min(abs(x - a), 3072 - abs(x - a)) for x in ks))
        dev = []
        for x in ks:
            e = (x - Kp) % 3072
            dev.append(e - 3072 if e > 1536 else e)
        n = len(dev); a = sorted(abs(v) for v in dev)
        print("   class %d: n=%3d  K_page=%6.1f  within +-64 units: %3d (%3.0f%%)  med|dev| %5.1f  max %6.1f"
              % (cls, n, Kp, sum(1 for v in a if v <= 64), 100 * sum(1 for v in a if v <= 64) / n,
                 a[n // 2], a[-1]))

    print("\n== 6. zone-boundary steps the HLE renders as 0.0 (default piano SET #1) ==")
    for sid, st, fl, kmin, kmax, root, base, zones in sets:
        if sid != '1': continue
        Ks = []
        for lo, hi, cls, ent, C in zones:
            p = P(cls, ent)
            Ks.append((lo, hi, C + 128 - 3072 * math.log2(p) if p else None))
        med = statistics.median(k % 3072 for _, _, k in Ks if k is not None)
        devs = []
        for lo, hi, k in Ks:
            if k is None: devs.append(None); continue
            e = (k % 3072) - med
            devs.append(e - 3072 if e > 1536 else (e + 3072 if e < -1536 else e))
        steps = [(devs[i] - devs[i - 1]) * 100 / 256 for i in range(1, len(devs))
                 if devs[i] is not None and devs[i - 1] is not None]
        print("   per-zone dev (cents): %s" % ["%+.1f" % (v * 100 / 256) for v in devs if v is not None])
        print("   boundary steps      : %s" % ["%+.1f" % s for s in steps])
        print("   worst %.1f cents   RMS %.1f cents" % (max(abs(s) for s in steps),
                                                        math.sqrt(sum(s * s for s in steps) / len(steps))))

    if '--emit-table' in sys.argv:
        with open(TABLE, 'w') as f:
            f.write("sel\tclass\tentry\tC_modal\tn_distinct\tkey_weight\tall_C\n")
            for sel in sorted(W):
                c = W[sel]
                f.write("%04X\t%d\t%03X\t%d\t%d\t%d\t%s\n"
                        % (sel, sel >> 12, sel & 0xFFF, c.most_common(1)[0][0], len(c),
                           sum(c.values()), ";".join("%d:%d" % kv for kv in sorted(c.items()))))
        print("\nwrote", TABLE)


if __name__ == '__main__':
    main()
