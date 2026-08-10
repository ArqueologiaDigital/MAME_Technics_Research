"""End-to-end single-frame decode with self-checks.

Pipeline (each stage measured, none of it oracle-dependent):

  1. geom.fit          raster bbox + blank-column matched filter -> affine seed
  2. psf.bootstrap     Gaussian sigmas + affine, on cells 6..9 (known a priori)
  3. psf.fit_prefix    the six constant address characters, by residual
  4. psf.refine        non-parametric PSF taps on the whole address block
  5. rowdp.decode_row  joint 57-cell Viterbi per row + posteriors
  6. psf.refine again  on the DECODED page (EM M-step), then re-decode

Self-checks reported with the result, none of which need a reference:
  * the 16 row addresses must ascend by exactly 0x10
  * cells 8, 9, the 14 inter-byte gaps and the two hyphens must classify as
    space / '-' -- they are forced in the decode, so instead their residual is
    reported as a grid-sanity number
  * per-byte posterior confidence (product of the two nibble posteriors)
"""
import numpy as np

from . import geom, psf, rowdp, layout as L


def decode_frame(lum, verbose=False, em_rounds=2, noise=None, max_lag=2,
                 ncols=57, seed_geometry=None):
    g = seed_geometry
    if g is None:
        g, _ = geom.fit(lum)
        g, _ = psf.bootstrap(lum, g, verbose=verbose)
    prefix, pscores = psf.fit_prefix(lum, g, verbose=verbose)
    g, rinfo = psf.refine(lum, g, addr_prefix=prefix, iters=5, verbose=verbose)
    prefix, pscores = psf.fit_prefix(lum, g, prefix=prefix)

    rrs = [rowdp.RowRenderer(g, r, ncols=ncols) for r in range(L.NROWS)]
    # initial levels from the address block only
    seqs, posts, coefs = [], [], []
    for r in range(L.NROWS):
        rr = rrs[r]
        cand = rowdp.default_candidates(ncols)
        start = [None] * ncols
        for c, k in L.known_row_text(r, prefix).items():
            if c < ncols:
                start[c] = k
        for c in range(ncols):
            if start[c] is None:
                start[c] = 0
        coef, _ = rr.fit_levels(lum, start)
        seq, post = rowdp.decode_row(rr, lum, coef, cand, noise=noise,
                                     max_lag=max_lag)
        seqs.append(seq)
        posts.append(post)
        coefs.append(coef)

    for em in range(em_rounds):
        cells = {}
        for r in range(L.NROWS):
            for c in range(ncols):
                cells[(r, c)] = seqs[r][c]
        g, rinfo = psf.refine(lum, g, cells=cells,
                              nx=(80, L.cell_x(ncols) + L.PX),
                              ny=(L.cell_y(0) - 7, L.cell_y(L.NROWS - 1) + L.GH + 3),
                              guard=(6, 2, 6, 3), iters=3, verbose=verbose)
        rrs = [rowdp.RowRenderer(g, r, ncols=ncols) for r in range(L.NROWS)]
        newseqs, newposts, newcoefs = [], [], []
        for r in range(L.NROWS):
            rr = rrs[r]
            coef, _ = rr.fit_levels(lum, seqs[r])
            seq, post = rowdp.decode_row(rr, lum, coef,
                                         rowdp.default_candidates(ncols),
                                         noise=noise, max_lag=max_lag)
            newseqs.append(seq)
            newposts.append(post)
            newcoefs.append(coef)
        seqs, posts, coefs = newseqs, newposts, newcoefs
        if verbose:
            print("  EM round %d rms=%.3f" % (em, rinfo["rms"]))

    return _package(g, rinfo, prefix, pscores, rrs, lum, seqs, posts, coefs, ncols)


def _package(g, rinfo, prefix, pscores, rrs, lum, seqs, posts, coefs, ncols):
    addrs, addr_conf = [], []
    for r in range(L.NROWS):
        digits = "".join(L.CLASSES[k] for k in seqs[r][:8])
        addrs.append(digits)
        addr_conf.append(float(np.prod([posts[r][c][seqs[r][c]] for c in range(8)])))

    nbytes = len(L.HEX_CELLS)
    data = np.zeros((L.NROWS, nbytes), np.uint8)
    conf = np.zeros((L.NROWS, nbytes))
    nib_post = np.zeros((L.NROWS, nbytes, 2, 16))
    for r in range(L.NROWS):
        for i, hc in enumerate(L.HEX_CELLS):
            hi, lo = seqs[r][hc], seqs[r][hc + 1]
            data[r, i] = (hi << 4) | lo if hi < 16 and lo < 16 else 0
            ph, pl = posts[r][hc][:16], posts[r][hc + 1][:16]
            nib_post[r, i, 0] = ph / max(ph.sum(), 1e-12)
            nib_post[r, i, 1] = pl / max(pl.sum(), 1e-12)
            conf[r, i] = nib_post[r, i, 0].max() * nib_post[r, i, 1].max()

    # --- self-check: do the printed addresses form a +0x10 ladder? ---
    vals, ok = [], []
    for r in range(L.NROWS):
        try:
            vals.append(int(addrs[r], 16))
        except ValueError:
            vals.append(None)
    base_votes = {}
    for r, v in enumerate(vals):
        if v is not None:
            b = v - 0x10 * r
            base_votes[b] = base_votes.get(b, 0) + 1
    base = max(base_votes, key=base_votes.get) if base_votes else None
    ladder = sum(1 for r, v in enumerate(vals) if v is not None and v == base + 0x10 * r) \
        if base is not None else 0

    rms_rows = [rrs[r].fit_levels(lum, seqs[r])[1] for r in range(L.NROWS)]
    return dict(geometry=g, refine=rinfo, prefix=prefix, prefix_scores=pscores,
                addrs=addrs, addr_conf=addr_conf, base=base,
                ladder_ok=ladder, base_votes=base_votes,
                data=data, conf=conf, nib_post=nib_post, seqs=seqs,
                rms_rows=rms_rows, ncols=ncols)


def render_hex(res):
    out = []
    for r in range(L.NROWS):
        row = " ".join("%02X" % b for b in res["data"][r])
        out.append("%s  %s" % (res["addrs"][r], row))
    return "\n".join(out)
