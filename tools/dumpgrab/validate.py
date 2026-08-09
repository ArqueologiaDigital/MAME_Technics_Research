#!/usr/bin/env python3
"""validate.py -- score a KN7000 debug-screen ROM extraction against the real ROM.

Answers, with numbers only (nothing is asserted that is not measured):

  * how many bytes were recovered at all, and how many of those an oracle covers
  * exact byte agreement, overall and per 256-byte page
  * the address, expected value and extracted value of EVERY mismatch
  * the confusion matrix over the 16 hex glyph classes -- which digit is being read as
    which -- which is the thing that tells the extractor author what to fix
  * a per-page structural check: are the mismatches explained by a whole-page byte shift
    (a framing bug) rather than by glyph misreads?

Input: the sparse-binary + mask contract in dumpfmt.py, or --pages JSONL.
Several oracles may be given at once; each recovered byte is scored against whichever
oracle covers its CPU address. Bytes no oracle covers are counted, never scored.

Usage
  validate.py --dir /tmp/dg_out --oracle roms/kn7000/kn7000_program.rom
              (scores every <prefix>_*.bin/.mask region a dumpgrab run wrote)
  validate.py --bin dump.bin --mask dump.mask --base 0x48400000 \
              --oracle roms/kn7000/kn7000_program.rom
  validate.py --pages pages.jsonl \
              --oracle roms/kn7000/kn7000_program.rom roms/kn7000/kn7000_table.rom \
              --json report.json --max-mismatch 200

Dependencies: python3 stdlib + numpy.
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dumpfmt  # noqa: E402

HEX = "0123456789ABCDEF"


def pct(n, d):
    return 100.0 * n / d if d else float("nan")


def load_oracles(paths, explicit_base=None):
    out = []
    for p in paths:
        name = os.path.basename(p)
        if explicit_base is not None and len(paths) == 1:
            base = explicit_base
        elif "program" in name:
            base = dumpfmt.ORACLES["program"]
        elif "table" in name:
            base = dumpfmt.ORACLES["table"]
        else:
            raise SystemExit(
                "cannot infer the CPU base of oracle %s; pass --oracle-base" % name)
        out.append((base, np.frombuffer(open(p, "rb").read(), dtype=np.uint8), name))
    return out


def oracle_for(oracles, addr):
    for base, arr, name in oracles:
        if base <= addr < base + len(arr):
            return base, arr, name
    return None


def region_files(outdir, prefix="dump"):
    """A dumpgrab output directory holds one .bin/.mask pair per contiguous run, named
    <prefix>_<STARTHEX>_<LENHEX>.bin. Return [(bin_path, mask_path, base), ...]."""
    import glob as _glob
    import re as _re
    out = []
    for b in sorted(_glob.glob(os.path.join(outdir, prefix + "_*.bin"))):
        m = _re.search(r"_([0-9A-Fa-f]{8})_([0-9A-Fa-f]+)\.bin$", os.path.basename(b))
        if not m:
            continue
        msk = os.path.splitext(b)[0] + ".mask"
        out.append((b, msk if os.path.exists(msk) else None, int(m.group(1), 16)))
    if not out:
        raise SystemExit("no %s_*.bin region files in %s" % (prefix, outdir))
    return out


def collect_pages(args):
    """Return list of (page_addr, values ndarray[256] uint8, known ndarray[256] bool,
    votes ndarray[256] uint8) plus a meta dict. Everything downstream is page-oriented,
    which keeps memory flat no matter how far apart the recovered addresses are."""
    meta = {}
    pages = {}
    if getattr(args, "dir", None):
        regs = region_files(args.dir, getattr(args, "prefix", "dump"))
        meta = {"regions": len(regs), "dir": args.dir}
        for binp, mskp, base in regs:
            sub = argparse.Namespace(pages=None, bin=binp, mask=mskp, base=base, dir=None)
            for pa, (v, k, vo) in collect_pages(sub)[0].items():
                V, K, VO = pages.setdefault(
                    pa, (np.zeros(256, np.uint8), np.zeros(256, bool),
                         np.zeros(256, np.uint16)))
                V[k] = v[k]
                VO[k] += vo[k]
                K |= k
        return pages, meta
    if args.pages:
        for addr, b, known in dumpfmt.load_pages_jsonl(args.pages):
            i = 0
            while i < len(b):
                cur = addr + i
                pa = cur & ~0xFF
                off = cur & 0xFF
                take = min(256 - off, len(b) - i)
                v, k, vo = pages.setdefault(
                    pa, (np.zeros(256, np.uint8), np.zeros(256, bool),
                         np.zeros(256, np.uint16)))
                sl = slice(off, off + take)
                arr = np.frombuffer(b[i:i + take], dtype=np.uint8)
                kb = np.array(known[i:i + take], dtype=bool)
                v[sl] = np.where(kb, arr, v[sl])
                vo[sl] += kb
                k[sl] |= kb
                i += take
    else:
        data, mask, base, meta = dumpfmt.load_sparse(args.bin, args.mask, args.base)
        d = np.frombuffer(bytes(data), dtype=np.uint8)
        m = np.frombuffer(bytes(mask), dtype=np.uint8)
        nz = np.nonzero(m)[0]
        if len(nz):
            first_pg = (base + int(nz[0])) & ~0xFF
            last_pg = (base + int(nz[-1])) & ~0xFF
            for pa in range(first_pg, last_pg + 1, 256):
                lo = pa - base
                hi = lo + 256
                if hi <= 0 or lo >= len(m):
                    continue
                a = max(lo, 0)
                b_ = min(hi, len(m))
                sub = m[a:b_]
                if not sub.any():
                    continue
                v, k, vo = pages.setdefault(
                    pa, (np.zeros(256, np.uint8), np.zeros(256, bool), np.zeros(256, np.uint16)))
                sl = slice(a - lo, b_ - lo)
                v[sl] = d[a:b_]
                k[sl] = sub > 0
                vo[sl] = sub
    return pages, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin")
    ap.add_argument("--mask")
    ap.add_argument("--pages", help="pages JSONL instead of --bin/--mask")
    ap.add_argument("--dir", help="a dumpgrab output directory: score every "
                                  "<prefix>_*.bin/.mask region it contains")
    ap.add_argument("--prefix", default="dump", help="region file prefix for --dir")
    ap.add_argument("--base", type=lambda s: int(s, 0))
    ap.add_argument("--oracle", nargs="+", required=True)
    ap.add_argument("--oracle-base", type=lambda s: int(s, 0))
    ap.add_argument("--json", help="write machine-readable report here")
    ap.add_argument("--max-mismatch", type=int, default=100,
                    help="print at most N mismatch lines (0 = all)")
    ap.add_argument("--full-matrix", action="store_true")
    ap.add_argument("--per-page", action="store_true", default=True)
    ap.add_argument("--no-per-page", dest="per_page", action="store_false")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    oracles = load_oracles(args.oracle, args.oracle_base)
    pages, meta = collect_pages(args)

    n_claimed = n_scored = n_ok = n_outside = 0
    mismatches = []
    conf = np.zeros((16, 16), dtype=np.int64)
    conf_hi = np.zeros((16, 16), dtype=np.int64)
    conf_lo = np.zeros((16, 16), dtype=np.int64)
    page_rows = []

    for pa in sorted(pages):
        vals, known, votes = pages[pa]
        n_claimed += int(known.sum())
        o = oracle_for(oracles, pa)
        if o is None:
            n_outside += int(known.sum())
            page_rows.append((pa, int(known.sum()), 0, 0, "", "no oracle"))
            continue
        obase, arr, oname = o
        lo = pa - obase
        take = min(256, len(arr) - lo)
        cov = known.copy()
        cov[take:] = False
        exp = np.zeros(256, dtype=np.uint8)
        exp[:take] = arr[lo:lo + take]
        n_outside += int(known.sum()) - int(cov.sum())
        n_scored += int(cov.sum())
        eq = (vals == exp) & cov
        n_ok += int(eq.sum())

        e = exp[cov].astype(np.int64)
        g = vals[cov].astype(np.int64)
        np.add.at(conf_hi, (e >> 4, g >> 4), 1)
        np.add.at(conf_lo, (e & 15, g & 15), 1)

        bad = np.nonzero(cov & (vals != exp))[0]
        for i in bad:
            mismatches.append((pa + int(i), int(exp[i]), int(vals[i])))
        sh = ""
        if len(bad):
            sh = page_shift_diagnosis(pa, vals, cov, oracles)
        page_rows.append((pa, int(known.sum()), int(cov.sum()), int(eq.sum()), oname, sh))

    conf = conf_hi + conf_lo
    nib_total = 2 * n_scored
    nib_ok = int(np.trace(conf))

    out = []
    w = out.append
    w("=== KN7000 debug-screen extraction vs ROM oracle ===")
    for base, arr, name in oracles:
        w("oracle       : %-26s base 0x%08X  size %d (0x%X)"
          % (name, base, len(arr), len(arr)))
    if meta.get("tool"):
        w("produced by  : %s" % meta["tool"])
    w("")
    w("RECOVERY")
    w("  bytes claimed recovered : %d" % n_claimed)
    w("  ... covered by an oracle: %d" % n_scored)
    w("  ... outside every oracle: %d  (no ground truth, not scored)" % n_outside)
    w("  pages touched           : %d" % len(pages))
    fullp = sum(1 for r in page_rows if r[1] == 256)
    w("  ... fully covered (256) : %d" % fullp)
    w("  ... partial             : %d" % (len(page_rows) - fullp))
    w("")
    w("AGREEMENT")
    w("  exact byte agreement    : %d / %d = %.4f%%" % (n_ok, n_scored, pct(n_ok, n_scored)))
    w("  byte mismatches         : %d" % len(mismatches))
    w("  hex-glyph agreement     : %d / %d = %.4f%%" % (nib_ok, nib_total, pct(nib_ok, nib_total)))
    scored_pages = [r for r in page_rows if r[2]]
    perfect = sum(1 for r in scored_pages if r[2] == r[3] == 256)
    w("  perfect pages (256/256) : %d / %d = %.2f%%"
      % (perfect, len(scored_pages), pct(perfect, len(scored_pages))))
    w("")

    if args.per_page and page_rows:
        w("PER-PAGE  (claim = bytes the extractor claimed; cov = of those, bytes with truth)")
        w("  page        claim  cov   ok    %%       oracle    note")
        for pa, claim, cov_, ok, oname, sh in page_rows:
            w("  %08X    %3d   %3d   %3d   %6.2f  %-9s %s"
              % (pa, claim, cov_, ok, pct(ok, cov_), oname[:9], sh))
        w("")

    if mismatches:
        w("MISMATCHES  (cpu_addr: expected -> got   [glyph errors])")
        lim = len(mismatches) if args.max_mismatch == 0 else min(len(mismatches), args.max_mismatch)
        for cpu, exp, got in mismatches[:lim]:
            bad = []
            if exp >> 4 != got >> 4:
                bad.append("%s->%s(hi)" % (HEX[exp >> 4], HEX[got >> 4]))
            if exp & 15 != got & 15:
                bad.append("%s->%s(lo)" % (HEX[exp & 15], HEX[got & 15]))
            w("  %08X: %02X -> %02X   %s" % (cpu, exp, got, " ".join(bad)))
        if lim < len(mismatches):
            w("  ... and %d more (use --max-mismatch 0)" % (len(mismatches) - lim))
        w("")

    w(render_matrix(conf, "GLYPH CONFUSION MATRIX (both nibble positions)", args.full_matrix))
    off_diag = [(int(conf[e][g]), e, g) for e in range(16) for g in range(16)
                if e != g and conf[e][g]]
    if off_diag:
        off_diag.sort(reverse=True)
        w("")
        w("TOP CONFUSIONS  (expected -> got : count; hi/lo = which nibble position)")
        for n, e, g in off_diag[:20]:
            w("  %s -> %s : %6d   (hi %d, lo %d)"
              % (HEX[e], HEX[g], n, conf_hi[e][g], conf_lo[e][g]))
        w("")
        worst = {}
        for n, e, g in off_diag:
            worst[e] = worst.get(e, 0) + n
        w("PER-GLYPH ERROR RATE (how often each expected glyph is misread)")
        for e in sorted(worst, key=lambda k: -worst[k]):
            tot = int(conf[e].sum())
            w("  %s : %6d / %6d = %.4f%%" % (HEX[e], worst[e], tot, pct(worst[e], tot)))

    text = "\n".join(out)
    if not args.quiet:
        print(text)

    if args.json:
        rep = {
            "oracles": [{"name": n, "base": b, "size": int(len(a))} for b, a, n in oracles],
            "claimed": n_claimed,
            "scored": n_scored,
            "outside_oracle": n_outside,
            "ok": n_ok,
            "byte_accuracy": (n_ok / n_scored) if n_scored else None,
            "glyph_ok": nib_ok,
            "glyph_total": nib_total,
            "glyph_accuracy": (nib_ok / nib_total) if nib_total else None,
            "pages": [{"addr": "%08X" % pa, "claim": c, "cov": cv, "ok": ok,
                       "oracle": on, "note": sh} for pa, c, cv, ok, on, sh in page_rows],
            "perfect_pages": perfect,
            "scored_pages": len(scored_pages),
            "mismatches": [["%08X" % a, e, g] for a, e, g in mismatches],
            "confusion": conf.tolist(),
            "confusion_hi": conf_hi.tolist(),
            "confusion_lo": conf_lo.tolist(),
        }
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=1)
    return 0 if not mismatches else 1


def page_shift_diagnosis(pa, vals, cov, oracles):
    """A whole-page byte shift means the extractor mis-framed the grid (a cell or a row
    out), which is a completely different bug from a glyph misread. Detect it."""
    best = (0, -1)
    for sh in range(-32, 33):
        if sh == 0:
            continue
        o = oracle_for(oracles, pa + sh)
        if o is None:
            continue
        obase, arr, _ = o
        lo = pa + sh - obase
        if lo < 0 or lo + 256 > len(arr):
            continue
        exp = arr[lo:lo + 256]
        ok = int(((vals == exp) & cov).sum())
        if ok > best[1]:
            best = (sh, ok)
    sh, ok = best
    return "SHIFTED %+d bytes (%d/256 match there)" % (sh, ok) if ok >= 200 else ""


def render_matrix(conf, title, full):
    lines = [title, "  rows = expected glyph, cols = extracted glyph"]
    if not full:
        active = [i for i in range(16)
                  if any(conf[i][j] for j in range(16) if j != i)
                  or any(conf[j][i] for j in range(16) if j != i)]
        if not active:
            lines.append("  (clean: every glyph read correctly, %d samples)" % int(conf.sum()))
            return "\n".join(lines)
    rows = range(16) if full else active
    cols = range(16) if full else active
    lines.append("       " + " ".join("%7s" % HEX[j] for j in cols))
    for i in rows:
        cells = []
        for j in cols:
            v = int(conf[i][j])
            cells.append("%7s" % ("." if v == 0 else (("[%d]" % v) if i == j else str(v))))
        lines.append("   %s   %s" % (HEX[i], " ".join(cells)))
    lines.append("  ([n] = correct reads on the diagonal)")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
