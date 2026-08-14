#!/usr/bin/env python3
"""P11 consequence analysis: what changes audibly if detect_period's gate goes 0.5 -> 0.30.

Reuses the faithful port in kn7000_mame/tools/kn5000_period_oracle.py (page_dir, detect_period,
class_to_page) but instruments detect_period to report WHICH branch produced the fallback.
Read-only; writes nothing into the project.
"""
import math, os, struct, sys, json
import numpy as np

TOOLS = "/home/fsanches/compartilhado/kn7000_mame/tools"
DATA = "/home/fsanches/compartilhado/kn7000_mame/notes/data"
sys.path.insert(0, TOOLS)
from kn5000_period_oracle import load_rom, page_dir, class_to_page, zone_sets, GRANULE

ROM = load_rom()


def detect_period_x(rom, start, samples, gate=0.5):
    """Same arithmetic as the C++ / the oracle, plus a branch label and diagnostics.

    returns dict(period_q16, branch, peak, cross, best_lag)
    branch in {short, maxlag, tooshort, silent, nocross, gate_reject, accept}
    """
    R = lambda p, br, peak=None, cross=None, lag=None: dict(
        period_q16=p, branch=br, peak=peak, cross=cross, lag=lag)
    if samples < 32:
        return R(samples << 16, "short")
    off = samples // 3
    W = min(samples - off, 4096)
    if W < 64:
        off, W = 0, min(samples, 4096)
    minlag, maxlag = 4, min(W // 2, 2048)
    if maxlag <= minlag:
        return R(samples << 16, "maxlag")
    n0 = min(W, max(0, (len(rom) - start) // 2 - off))
    x = np.frombuffer(rom, dtype="<i2", count=n0, offset=start + off * 2).astype(np.float64)
    n = len(x)
    if n <= minlag * 2 + 4:
        return R(samples << 16, "tooshort")
    x = x - x.mean()
    if float(np.dot(x, x)) < 1.0:
        return R(samples << 16, "silent")
    hi = min(maxlag, n - 1)
    sq = np.concatenate(([0.0], np.cumsum(x * x)))
    r = np.full(hi + 1, -2.0)
    for lag in range(minlag, hi + 1):
        m = n - lag
        c = float(np.dot(x[:m], x[lag:lag + m]))
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
        return R((samples << 16) if samples <= 2048 else 0, "nocross")
    peak = float(r[cross:hi + 1].max())

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
                return R(refine(lag), "accept", peak, cross, lag)
        for lag in range(cross, hi + 1):
            if r[lag] >= 0.92 * peak:
                return R(refine(lag), "accept", peak, cross, lag)
    return R((samples << 16) if samples <= 2048 else 0, "gate_reject", peak, cross, None)


def main():
    pages = {p: page_dir(ROM, p) for p in range(4)}
    rows = []
    for pg, v in pages.items():
        for i, (start, ns) in enumerate(v):
            if ns < 32 or start + 2 * ns > len(ROM):
                rows.append(dict(page=pg, chunk=i, n=ns, skipped=True))
                continue
            a = detect_period_x(ROM, start, ns, 0.5)
            b = detect_period_x(ROM, start, ns, 0.30)
            rows.append(dict(page=pg, chunk=i, n=ns, start=start, skipped=False,
                             p5=a["period_q16"], b5=a["branch"], peak=a["peak"],
                             cross=a["cross"], lag5=a["lag"],
                             p3=b["period_q16"], b3=b["branch"], lag3=b["lag"]))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "periods.json")
    with open(out, "w") as fh:
        json.dump(rows, fh)
    print("wrote", out, len(rows), "rows")


if __name__ == "__main__":
    main()
