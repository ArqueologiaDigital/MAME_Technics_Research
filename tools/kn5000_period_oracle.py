#!/usr/bin/env python3
"""Is detect_period() measuring the right period? Graded by the firmware's OWN zone table.

THE PROBLEM (notes/TASK-QUEUE-kn5000-sound.md, item P11): kn5000_tonegen's detect_period()
rejects a lag whose normalised autocorrelation peaks below 0.5 and then falls back to
P = N (the whole recording as one cycle), which makes update_pitch() resample by up to 44x.
b0p1c35 peaks 0.436 at lag 175 -- a real period, refused.

THE ORACLE, and why it is not circular: a multisample set assigns consecutive key zones to
consecutive sample entries of the SAME instrument. Equal temperament then fixes the ratio
between their periods regardless of how any of them was measured -- a zone centred 4
semitones higher must have a period 2^(-4/12) times as long. So we can grade a period
detector without a second detector, and without YIN. The constraint comes from the
firmware's zone table, which is data we already hold.

    log2(period) vs zone-centre key must fit a line of slope -1/12 per semitone.

STATUS 2026-08-14 — the class:entry mapping is SOLVED, but the oracle CANNOT grade P11.

  MAPPING (resolved): bank = (class >> 2) & 1, page = class & 3. Evidence: the zone table's
  per-class maximum entry is 214/177/185/436 for classes 0-3 and 198/168/151/57 for classes
  4-7, against IC307's declared page sizes 198/168/1072/57 — classes 4, 5 and 7 are EXACT
  hits on pages 0, 1, 3 and class 6 fits page 2. Classes 0-3 are the other, undumped socket.
  Parsing all four pages yields 1495 chunks, matching the driver's own 1495/1495 figure.

  ⚠ BUT THE ORACLE IS BLIND TO THE CHANGE IT WAS BUILT TO JUDGE. Measured: 94 chunks change
  period between gate 0.5 and 0.30; 321 IC307 chunks are referenced by zone sets; the
  intersection is ZERO. Both gates therefore score identically (9 of 53 sets within 25% of
  the ideal slope, median |err| 0.0641) — and that identity is NON-OBSERVATION, not
  agreement. Per the project's own rule, a criterion that cannot distinguish is not a pass.
  DO NOT cite this oracle as validating any detect_period change until it can see one.

  WHY: the fallback problem is concentrated in page 2 — 500 of its 1050 chunks (48%) fall
  back, against 11/198, 32/168 and 0/57 elsewhere — and page 2 draws only 75 of the 530
  IC307 zone references. Page 2 is very likely drums/SFX/one-shots, where "no periodicity"
  may be the CORRECT answer rather than a defect. That reframes P11: before changing the
  gate, establish whether page-2 chunks are meant to be pitched at all.

WHAT THIS TOOL DOES
  * ports detect_period() from kn5000_tonegen.cpp faithfully (same window, same DC removal,
    same normalised autocorrelation, same negative-crossing rule, same 0.92*peak search)
  * runs it over every wave in the one genuine dump, IC307
  * runs a CANDIDATE variant with the acceptance gate changed, for A/B
  * grades both against the zone-slope constraint above

    python3 tools/kn5000_period_oracle.py                 # current gate vs candidate
    python3 tools/kn5000_period_oracle.py --gate 0.30     # try another threshold

It measures and grades only. It changes nothing, and it is NOT a fitting target: never tune
a detector until this passes -- tune it until the physics holds.
"""
import argparse
import math
import os
import struct
import sys

import numpy as np

ROMS = "/home/fsanches/compartilhado/technics_roms/roms/kn5000"
IC307 = os.path.join(ROMS, "kn5000_waveform_rom.ic307")
SETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "notes", "data", "kn5000-multisample-sets.tsv")
INDEX_ENTRIES = 198
GRANULE = 16


def load_rom():
    with open(IC307, "rb") as fh:
        return fh.read()


PAGE_SIZE = 0x100000


def page_dir(rom, page):
    """Parse one 1 MB page's self-delimiting directory -> [(start_byte, n_samples)].

    Port of kn5000_tonegen_device::parse_page_directories, including all six acceptance
    checks, so a non-directory page is rejected instead of yielding garbage.

    ⚠ Each chip holds FOUR such pages, each with its OWN directory -- IC307 declares
    198 / 168 / 1072 / 57 slots. An earlier version of this tool parsed only the first
    198-entry table and therefore analysed page 0 alone, about 13% of the chip.
    """
    base = page * PAGE_SIZE
    if base + PAGE_SIZE > len(rom):
        return []
    u16 = lambda o: struct.unpack_from("<H", rom, base + o)[0]
    head = u16(0)                                                   # 1
    if head == 0 or head % 4:
        return []
    n = head // 4
    if n * 4 > PAGE_SIZE - 4:                                       # 2
        return []
    param, wave = [], []
    for i in range(n):
        pp, wo = u16(i * 4), u16(i * 4 + 2)
        if i and pp < param[-1]:                                    # 3 monotonic
            return []
        if pp < n * 4:                                              # 4 no overlap
            return []
        if wo * GRANULE >= PAGE_SIZE:                               # 5 in-page
            return []
        if u16(pp) != wo:                                           # 6 back-reference
            return []
        param.append(pp); wave.append(wo)
    starts = sorted({w * GRANULE for w in wave})
    out = []
    for w in wave:
        s0 = w * GRANULE
        nxt = min((t for t in starts if t > s0), default=PAGE_SIZE)
        out.append((base + s0, max(0, (nxt - s0) // 2)))
    return out


def class_to_page(cls):
    """Zone-table class -> (bank, page). bank 1 = IC307, the one genuine dump.

    MEASURED (2026-08-14): the zone table's per-class maximum entry index is
    214/177/185/436 for classes 0-3 and 198/168/151/57 for classes 4-7, against IC307's
    declared page sizes 198/168/1072/57. Classes 4, 5 and 7 are EXACT hits on pages
    0, 1 and 3; class 6 (needs 151) fits page 2's 1072. Classes 0-3 exceed every page
    except one, so they cannot all live on this chip -- they are the other, undumped
    socket. Hence bank = (class >> 2) & 1, page = class & 3.
    """
    return (cls >> 2) & 1, cls & 3


def detect_period(rom, start, samples, gate=0.5):
    """Port of kn5000_tonegen_device::detect_period. Returns period in Q16, or 0.

    Kept structurally identical to the C++ so an A/B here means the same thing there.
    """
    if samples < 32:
        return samples << 16
    off = samples // 3
    W = min(samples - off, 4096)
    if W < 64:
        off, W = 0, min(samples, 4096)
    minlag, maxlag = 4, min(W // 2, 2048)
    if maxlag <= minlag:
        return samples << 16

    x = []
    for i in range(W):
        bp = start + (off + i) * 2
        if bp + 1 >= len(rom):
            break
        x.append(float(struct.unpack_from("<h", rom, bp)[0]))
    n = len(x)
    if n <= minlag * 2 + 4:
        return samples << 16

    mean = sum(x) / n
    x = [v - mean for v in x]
    if sum(v * v for v in x) < 1.0:
        return samples << 16

    hi = min(maxlag, n - 1)
    # Same quantity as the C++ inner loop -- correlation over the overlap, normalised by
    # sqrt(energy of each side of the overlap) -- computed with prefix sums so the whole
    # lag sweep is O(n log n) instead of O(n * maxlag). Verified against the literal
    # transcription by --selftest.
    xa = np.asarray(x, dtype=np.float64)
    sq = np.concatenate(([0.0], np.cumsum(xa * xa)))
    r = [-2.0] * (hi + 1)
    for lag in range(minlag, hi + 1):
        m = n - lag
        c = float(np.dot(xa[:m], xa[lag:lag + m]))
        e0 = float(sq[m] - sq[0])
        e1 = float(sq[lag + m] - sq[lag])
        den = math.sqrt(e0 * e1)
        r[lag] = (c / den) if den > 1.0 else -2.0

    cross = 0
    for lag in range(minlag, hi + 1):
        if r[lag] < 0.0:
            cross = lag
            break
    if cross == 0:
        return (samples << 16) if samples <= 2048 else 0

    peak = max(r[cross:hi + 1])

    def refine(lag):
        frac = 0.0
        if lag > minlag and lag + 1 <= hi:
            y0, y1, y2 = r[lag - 1], r[lag], r[lag + 1]
            den = y0 - 2.0 * y1 + y2
            if abs(den) > 1e-12:
                frac = 0.5 * (y0 - y2) / den
            frac = max(-0.5, min(0.5, frac))
        return int(max(1.0, lag + frac) * 65536.0 + 0.5)

    if peak >= gate:
        for lag in range(cross + 1, hi):
            if r[lag] >= 0.92 * peak and r[lag] >= r[lag - 1] and r[lag] >= r[lag + 1]:
                return refine(lag)
        for lag in range(cross, hi + 1):
            if r[lag] >= 0.92 * peak:
                return refine(lag)
    return (samples << 16) if samples <= 2048 else 0


def zone_sets(path):
    """Parse the multisample sets: [(set_idx, [(zone_centre_key, entry_index), ...])]."""
    out = []
    with open(path) as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        zi = hdr.index("zones(lo-hi:class:entry)")
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) <= zi:
                continue
            zones = []
            for z in f[zi].split(";"):
                try:
                    rng, cls, ent = z.split(":")
                    lo, hi = (int(v) for v in rng.split("-"))
                    zones.append(((lo + hi) / 2.0, int(cls), int(ent, 16)))
                except ValueError:
                    continue
            if len(zones) >= 4:
                out.append((int(f[0]), zones))
    return out


def slope_fit(pts):
    """Least-squares slope of log2(period) vs key. Ideal = -1/12."""
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    return (num / den) if den else 0.0


def grade(periods, sets, label):
    IDEAL = -1.0 / 12.0
    good = bad = skipped = 0
    errs = []
    for _idx, zones in sets:
        pts = []
        for key, cls, ent in zones:
            bank, page = class_to_page(cls)
            if bank != 1:
                continue          # the other socket is undumped -- cannot grade it
            p = periods.get((page, ent))
            if p:
                pts.append((key, math.log2(p / 65536.0)))
        if len(pts) < 4:
            skipped += 1
            continue
        s = slope_fit(pts)
        errs.append(abs(s - IDEAL))
        if abs(s - IDEAL) <= 0.25 * abs(IDEAL):
            good += 1
        else:
            bad += 1
    med = sorted(errs)[len(errs) // 2] if errs else float("nan")
    print(f"  {label:22s} sets graded {good + bad:4d}  within 25% of ideal slope: "
          f"{good:4d}  off: {bad:4d}  median |slope err| {med:.4f}")
    return good, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gate", type=float, default=0.30,
                    help="candidate acceptance threshold to A/B against the shipped 0.5")
    ap.add_argument("--limit", type=int, default=0, help="only the first N waves (quick run)")
    args = ap.parse_args()

    if not os.path.exists(IC307):
        sys.exit(f"missing {IC307}")
    rom = load_rom()
    pages = {p: page_dir(rom, p) for p in range(4)}
    print("IC307 page directories: " +
          ", ".join(f"p{p}={len(v)}" for p, v in pages.items()))
    table = [(p, i, st, ns) for p, v in pages.items() for i, (st, ns) in enumerate(v)]
    if args.limit:
        table = table[:args.limit]

    cur, cand = {}, {}
    nfall_cur = nfall_cand = 0
    for (pg, i, start, ns) in table:
        if ns < 32 or start + 2 * ns > len(rom):
            continue
        pc = detect_period(rom, start, ns, gate=0.5)
        pk = detect_period(rom, start, ns, gate=args.gate)
        if pc:
            cur[(pg, i)] = pc
            if pc == (ns << 16):
                nfall_cur += 1
        if pk:
            cand[(pg, i)] = pk
            if pk == (ns << 16):
                nfall_cand += 1

    print(f"waves analysed: {len(table)}   (IC307, the one genuine dump)")
    print(f"  shipped gate 0.5   : {len(cur):3d} periods, {nfall_cur:3d} are the P=N fallback")
    print(f"  candidate gate {args.gate:<4}: {len(cand):3d} periods, {nfall_cand:3d} are the P=N fallback")
    sets = zone_sets(SETS)
    refs = [(c, e) for _i, z in sets for _k, c, e in z]
    on307 = sum(1 for c, _e in refs if class_to_page(c)[0] == 1)
    print(f"\nzone table: {len(sets)} sets, {len(refs)} zone refs; "
          f"{on307} ({100.0 * on307 / len(refs):.0f}%) resolve to IC307, "
          f"the rest to the undumped socket")
    print(f"grading only IC307 zones, ideal slope -1/12 = {-1/12:.4f} per semitone:")
    grade(cur, sets, "shipped gate 0.5")
    grade(cand, sets, f"candidate gate {args.gate}")


if __name__ == "__main__":
    main()
