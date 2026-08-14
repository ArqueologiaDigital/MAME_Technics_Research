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

⚠⚠ STATUS 2026-08-14: THE GRADING HALF IS BLOCKED. The zone table addresses samples as
`class:entry` -- an 8-way class field plus an entry index reaching 0x1B2 (429 distinct
values). The global IC307 index has only 198 entries, max 0x0C5, so `entry` is NOT a global
wave index and the two cannot be joined yet. Until `class:entry` is decoded to (chip, wave)
this tool must not emit a detector verdict; a first version of it did, and its "0 of 28 sets
within 25% of ideal slope" was measuring a bad join, not a bad detector.
   Note the likely consequence: if `class` selects the waveform chip, most zones resolve to
IC304/305/306, which are NOT dumped -- so this oracle will only ever grade the IC307 subset,
which the roadmap already declares the KN5000 test corpus.

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


def wave_table(rom):
    """(start_byte, n_samples) per index entry.

    The index is 198 entries of TWO u16 -- (param_ptr, wave_offset) -- exactly as
    tools/extract_kn5000_waves.py parses it. Reading it as one u32 gives nonsense, which
    is how the first version of this tool found periods for 1 wave in 12.
    """
    entries = [struct.unpack_from("<HH", rom, i * 4) for i in range(INDEX_ENTRIES)]
    if entries[0][0] != INDEX_ENTRIES * 4:
        sys.exit("entry0 param_ptr 0x%04x != 0x%04x -- not a KN5000 waveform ROM"
                 % (entries[0][0], INDEX_ENTRIES * 4))
    starts = sorted({w * GRANULE for _, w in entries})
    out = []
    for _pp, w in entries:
        s0 = w * GRANULE
        nxt = min((t for t in starts if t > s0), default=len(rom))
        out.append((s0, max(0, (nxt - s0) // 2)))
    return out


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
                    rng, _cls, ent = z.split(":")
                    lo, hi = (int(v) for v in rng.split("-"))
                    zones.append(((lo + hi) / 2.0, int(ent, 16)))
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
        for key, ent in zones:
            p = periods.get(ent)
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
    table = wave_table(rom)
    if args.limit:
        table = table[:args.limit]

    cur, cand = {}, {}
    nfall_cur = nfall_cand = 0
    for i, (start, ns) in enumerate(table):
        if ns < 32 or start + 2 * ns > len(rom):
            continue
        pc = detect_period(rom, start, ns, gate=0.5)
        pk = detect_period(rom, start, ns, gate=args.gate)
        pc = pc[0] if isinstance(pc, tuple) else pc
        pk = pk[0] if isinstance(pk, tuple) else pk
        if pc:
            cur[i] = pc
            if pc == (ns << 16):
                nfall_cur += 1
        if pk:
            cand[i] = pk
            if pk == (ns << 16):
                nfall_cand += 1

    print(f"waves analysed: {len(table)}   (IC307, the one genuine dump)")
    print(f"  shipped gate 0.5   : {len(cur):3d} periods, {nfall_cur:3d} are the P=N fallback")
    print(f"  candidate gate {args.gate:<4}: {len(cand):3d} periods, {nfall_cand:3d} are the P=N fallback")
    sets = zone_sets(SETS)
    ents = [e for _i, z in sets for _k, e in z]
    print(f"\nzone table: {len(sets)} sets, {len(ents)} zone refs, "
          f"entry range 0x{min(ents):03X}..0x{max(ents):03X}, {len(set(ents))} distinct")
    print(f"global IC307 wave index: {INDEX_ENTRIES} entries (max 0x{INDEX_ENTRIES - 1:03X})")
    if max(ents) >= INDEX_ENTRIES:
        print("\n⚠ GRADING SKIPPED -- zone 'entry' exceeds the global wave index, so "
              "class:entry is not a\n  global index and any join would be meaningless. "
              "Decode class:entry -> (chip, wave) first.")
        print("  Until then this tool reports only the DETECTOR's own behaviour above.")
        return
    grade(cur, sets, "shipped gate 0.5")
    grade(cand, sets, f"candidate gate {args.gate}")


if __name__ == "__main__":
    main()
