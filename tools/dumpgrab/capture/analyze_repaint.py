#!/usr/bin/env python3
"""analyze_repaint.py -- FIRMWARE-REPAINT ATOMICITY measurement for the KN7000 MEMORY DUMP sweep.

THIS IS NOT AN ANALOG-TEARING TEST. MAME emits pixel-exact framebuffers, so capture-chain
tearing does not exist in this environment. What is measured here is a property of the
FIRMWARE: when the page address changes, does the viewer repaint all 16 rows within a single
emulated 60 Hz frame, or do intermediate frames escape showing rows from two different pages?

Method (geometry-free, no font/OCR needed):
  1. A SLOW capture supplies one settled "golden" PNG per page address.
  2. In a FAST capture, every emitted frame is compared against the goldens SCANLINE BY
     SCANLINE, by exact pixel equality (MAME is deterministic, so equality is the right test).
  3. Scanlines that are identical across all goldens (title bar, colour legend, rocker row)
     carry no page information and are excluded.  Every remaining "informative" scanline is
     labelled with the page whose golden it matches, or UNKNOWN if it matches none (a line
     caught mid-write).
  4. A frame is MIXED if its informative scanlines carry more than one page label.

Deps: numpy, pillow.

    python3 analyze_repaint.py --slow SLOWDIR --fast FASTDIR [--json out.json]
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image


def load_manifest(d):
    rows = []
    with open(os.path.join(d, "manifest.csv")) as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "relframe": int(r["relframe"]),
                "absframe": int(r["absframe"]),
                "seconds": float(r["seconds"]),
                "addr": int(r["addr"], 16),
                "snap": int(r["snap"]),
            })
    return rows


def row_of(y, informative):
    """Map a scanline to one of the viewer's 16 hex rows (the informative band is exactly them)."""
    y0, y1 = int(informative.min()), int(informative.max())
    return min(15, max(0, int((y - y0) * 16 // (y1 - y0 + 1))))


def png(d, idx):
    p = os.path.join(d, "frames", f"{idx:04d}.png")
    if not os.path.exists(p):                       # MAME widens the index past 9999
        p = os.path.join(d, "frames", f"{idx}.png")
    return np.asarray(Image.open(p).convert("RGB"))


def build_goldens(slowdir):
    """Settled images per address from the slow run.

    Returns (goldens, unstable_lines):
      goldens[addr]  = the LAST snapshot taken while that address was displayed, i.e. the most
                       fully settled repaint available.
      unstable_lines = scanlines that differ between snapshots of the SAME address. Those carry
                       animation (blinking cursor, tempo/clock widgets), not page identity, and
                       must not be used to label a frame.
    """
    rows = load_manifest(slowdir)
    per_addr = {}
    for r in rows:
        if r["snap"] >= 0:
            per_addr.setdefault(r["addr"], []).append(r["snap"])
    goldens, unstable = {}, None
    for addr, snaps in sorted(per_addr.items()):
        imgs = [png(slowdir, s) for s in snaps]
        goldens[addr] = imgs[-1]
        # The FIRST snapshot of a page can still be mid-repaint, so it is excluded from the
        # stability test -- otherwise every text row would look "animated". Instability is
        # judged only across snapshots taken well after the page change.
        tail = imgs[1:] if len(imgs) > 2 else imgs
        if len(tail) > 1:
            st = np.stack(tail)
            diff = ~np.all(st == st[0][None], axis=(0, 2, 3))     # (H,) True where it wobbles
            unstable = diff if unstable is None else (unstable | diff)
    if unstable is None:
        unstable = np.zeros(next(iter(goldens.values())).shape[0], dtype=bool)
    return goldens, unstable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slow", required=True, help="capture dir of the SLOW run (goldens)")
    ap.add_argument("--fast", required=True, help="capture dir of the FAST run (per-frame PNGs)")
    ap.add_argument("--json", help="write the full result here")
    a = ap.parse_args()

    goldens, unstable = build_goldens(a.slow)
    if len(goldens) < 2:
        print("need at least 2 golden pages", file=sys.stderr)
        return 2
    addrs = sorted(goldens)
    H, W, _ = goldens[addrs[0]].shape
    G = np.stack([goldens[x] for x in addrs])                      # (P, H, W, 3)

    # informative scanlines = differ between pages AND are stable within a page
    same_everywhere = np.all(G == G[0][None], axis=(0, 2, 3))      # (H,)
    informative = np.where((~same_everywhere) & (~unstable))[0]
    print(f"goldens          : {len(addrs)} pages "
          f"0x{addrs[0]:08X}..0x{addrs[-1]:08X}, image {W}x{H}")
    print(f"informative rows : {len(informative)} of {H} "
          f"(y {informative.min()}..{informative.max()});  "
          f"{int(unstable.sum())} rows dropped as animated, "
          f"{int(same_everywhere.sum())} as page-invariant")

    fast = load_manifest(a.fast)
    frames = [r for r in fast if r["snap"] >= 0]
    if not frames:
        print("fast capture has no per-frame snapshots (run it with --snap all)", file=sys.stderr)
        return 2

    # Exact-match lookup: scanline content -> the SET of golden pages that contain it.
    # A set, not a single page: one pixel row through a text line is often identical on several
    # pages (rows of 0xFF, coincidental glyph rows). Collapsing that to one page would invent
    # "mixing" where there is only ambiguity -- this was a real false positive during development.
    lut = {}
    for pi, x in enumerate(addrs):
        for y in informative:
            lut.setdefault(y, {}).setdefault(G[pi, y].tobytes(), set()).add(x)

    per_frame = []
    mixed = 0
    unknown_lines_total = 0
    mixed_examples = []
    for r in frames:
        img = png(a.fast, r["snap"])
        sets, unknown = [], 0
        for y in informative:
            s = lut[y].get(img[y].tobytes())
            if s is None:
                unknown += 1
            sets.append(s)
        known = [s for s in sets if s]
        # A frame is single-page-consistent iff SOME page explains every known scanline.
        consistent = set(addrs)
        for s in known:
            consistent &= s
        unknown_lines_total += unknown
        is_mixed = (len(known) > 0) and (len(consistent) == 0)
        # For a mixed frame: how much of the screen is the odd one out, and which text rows?
        stale_lines, stale_rows = [], []
        if is_mixed:
            votes = Counter()
            for s in known:
                votes.update(s)
            modal = votes.most_common(1)[0][0]
            stale_lines = [int(y) for y, s in zip(informative, sets) if s and modal not in s]
            stale_rows = sorted({row_of(y, informative) for y in stale_lines})
        rec = {
            "relframe": r["relframe"],
            "manifest_addr": r["addr"],
            "mixed": bool(is_mixed),
            "consistent_pages": [f"0x{x:08X}" for x in sorted(consistent)],
            "unknown_lines": unknown,
            "informative_lines": int(len(informative)),
            "stale_lines": len(stale_lines),
            "stale_rows": stale_rows,
        }
        per_frame.append(rec)
        if is_mixed:
            mixed += 1
            if len(mixed_examples) < 12:
                # where does the split sit? label each line by the smallest candidate page
                seq = [(int(y), (f"0x{min(s):08X}" if s else None))
                       for y, s in zip(informative, sets)]
                mixed_examples.append({"relframe": r["relframe"], "lines": seq})

    n = len(per_frame)
    clean = [f for f in per_frame if not f["mixed"] and f["unknown_lines"] == 0]
    partial = [f for f in per_frame if not f["mixed"] and f["unknown_lines"] > 0]
    print()
    print(f"frames analysed  : {n}")
    print(f"MIXED frames     : {mixed}  ({100.0 * mixed / n:.2f} %)   "
          f"<- provably rows from >1 page in one emitted frame")
    print(f"clean frames     : {len(clean)}  ({100.0 * len(clean) / n:.2f} %)   "
          f"<- every informative line matches one page, none half-written")
    print(f"partial frames   : {len(partial)}  ({100.0 * len(partial) / n:.2f} %)  "
          f"<- consistent with one page but some lines caught mid-write")
    print(f"unknown lines    : {unknown_lines_total} of {n * len(informative)} "
          f"({100.0 * unknown_lines_total / (n * len(informative)):.3f} %)")
    if mixed:
        sl = sorted(f["stale_lines"] for f in per_frame if f["mixed"])
        rowhist = Counter()
        for f in per_frame:
            if f["mixed"]:
                rowhist.update(f["stale_rows"])
        print(f"  in a mixed frame, scanlines belonging to the OTHER page: "
              f"min={sl[0]} median={sl[len(sl)//2]} max={sl[-1]} of {len(informative)}")
        print(f"  hex rows (0=top,15=bottom) ever caught stale: "
              f"{sorted(rowhist)}  counts={[rowhist[k] for k in sorted(rowhist)]}")

    # how long does the screen actually SHOW each page (as opposed to the address cell holding it)?
    shown = []
    cur, run = None, 0
    for f in per_frame:
        p = (f["consistent_pages"][0]
             if (not f["mixed"] and f["unknown_lines"] == 0 and len(f["consistent_pages"]) == 1)
             else None)
        if p == cur:
            run += 1
        else:
            if cur is not None:
                shown.append((cur, run))
            cur, run = p, 1
    if cur is not None:
        shown.append((cur, run))
    pure = [r for p, r in shown if p is not None]
    if pure:
        pure_sorted = sorted(pure)
        print(f"clean frames per displayed page: min={pure_sorted[0]} "
              f"median={pure_sorted[len(pure_sorted)//2]} max={pure_sorted[-1]} "
              f"(n={len(pure)} runs)")

    # latency between the address cell changing and the screen showing that page
    by_addr_first_shown = {}
    for f in per_frame:
        if not f["mixed"] and f["unknown_lines"] == 0 and len(f["consistent_pages"]) == 1:
            p = int(f["consistent_pages"][0], 16)
            by_addr_first_shown.setdefault(p, f["relframe"])
    first_in_manifest = {}
    for r in fast:
        first_in_manifest.setdefault(r["addr"], r["relframe"])
    lat = [by_addr_first_shown[x] - first_in_manifest[x]
           for x in by_addr_first_shown if x in first_in_manifest]
    if lat:
        lat.sort()
        print(f"repaint latency  : address-cell change -> first clean frame of that page: "
              f"min={lat[0]} median={lat[len(lat)//2]} max={lat[-1]} frames (n={len(lat)})")

    # PAGE COVERAGE -- the question that decides whether a sweep can dump a ROM at all:
    # does every page the address cell visited get at least one clean, complete frame?
    visited = []
    for r in fast:
        if not visited or visited[-1] != r["addr"]:
            visited.append(r["addr"])
    visited_set = sorted(set(visited))
    clean_count = Counter()
    for f in per_frame:
        if not f["mixed"] and f["unknown_lines"] == 0 and len(f["consistent_pages"]) == 1:
            clean_count[int(f["consistent_pages"][0], 16)] += 1
    missing = [x for x in visited_set if clean_count[x] == 0]
    cc = sorted(clean_count[x] for x in visited_set)
    print(f"page coverage    : {len(visited_set) - len(missing)}/{len(visited_set)} pages got a "
          f"clean frame; clean frames per page min={cc[0]} median={cc[len(cc)//2]} max={cc[-1]}")
    if missing:
        print(f"                   MISSED: {[f'0x{x:08X}' for x in missing]}")

    # DISPLAY LAG -- during a fast sweep the address cell runs ahead of the painted screen, so
    # manifest.addr is NOT the page on the frame recorded at the same instant.
    lag = []
    addr_by_rel = {r["relframe"]: r["addr"] for r in fast}
    for f in per_frame:
        if not f["mixed"] and f["unknown_lines"] == 0 and len(f["consistent_pages"]) == 1:
            shown_addr = int(f["consistent_pages"][0], 16)
            lag.append((addr_by_rel[f["relframe"]] - shown_addr) // 0x100)
    if lag:
        lh = Counter(lag)
        print(f"display lag      : manifest addr minus page actually on screen, in PAGES: "
              f"{dict(sorted(lh.items()))}")

    out = {
        "slow_dir": a.slow, "fast_dir": a.fast,
        "image": [int(W), int(H)],
        "golden_pages": [f"0x{x:08X}" for x in addrs],
        "informative_lines": [int(y) for y in informative],
        "frames_analysed": n,
        "mixed_frames": mixed,
        "mixed_fraction": mixed / n,
        "clean_frames": len(clean),
        "partial_frames": len(partial),
        "unknown_line_fraction": unknown_lines_total / (n * len(informative)),
        "clean_frames_per_displayed_page": pure,
        "repaint_latency_frames": lat,
        "mixed_examples": mixed_examples,
        "per_frame": per_frame,
    }
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
