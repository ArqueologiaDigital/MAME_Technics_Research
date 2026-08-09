"""Single-image extraction of one KN7000 MEMORY DUMP page.

    from kn7000dump import PageExtractor
    ex  = PageExtractor()                    # loads the shipped atlas
    res = ex.extract("frame.png")
    res.base_address        # 0x48400000
    res.data                # bytes, 256 of them
    res.conf                # (16,16) float, per-byte confidence in [0,1]

Redundancy used, all of it free:
  * the 16 row addresses must ascend by exactly 0x10  -> the base address is a
    vote across 16 independent reads, and a disagreeing row localises a
    geometry failure to that row;
  * the highlight colour of a cell encodes its value independently of the
    glyphs (Aqua/Yellow/Lime = the three legend bytes) -> a second opinion on
    those cells, and a check on all the others (a highlighted cell that OCRs to
    a different value is a caught error).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from . import layout as L
from .atlas import Atlas, AtlasBuilder, CLASSES
from .geometry import Grid, RowFit, fit_grid, ink_map, texture_map
from .imageutil import as_rgb, resample_patch, shear_rows

HEX = CLASSES

# Legend defaults printed by the viewer at power-up (footer
# "Aqua = F0  Yellow = F7  Lime = FF  Fuchsia = XX").  Fuchsia is disabled by
# default, hence None.  Override via PageExtractor(highlight=...) if the
# operator has stepped the highlight bytes with panel columns 10..13.
HIGHLIGHT_DEFAULT = {"aqua": 0xF0, "yellow": 0xF7, "lime": 0xFF, "fuchsia": None}
COLOR_NAMES = ["none", "aqua", "yellow", "lime", "fuchsia", "orange"]

DEFAULT_ATLAS = os.path.join(os.path.dirname(__file__), "data", "atlas_native.npz")


# --------------------------------------------------------------------------- #
@dataclass
class PageResult:
    ok: bool
    base_address: Optional[int]
    data: bytearray
    conf: np.ndarray                      # (16,16) per-byte confidence 0..1
    digit_conf: np.ndarray                # (16,32) per hex digit
    row_addresses: List[Optional[int]]    # as read, before the ascent check
    row_addr_ok: List[bool]               # row address == base + 0x10*row
    addr_conf: np.ndarray                 # (16,8) per address digit
    color_class: np.ndarray               # (16,16) index into COLOR_NAMES
    color_byte: np.ndarray                # (16,16) implied byte, -1 if none
    color_agree: np.ndarray               # (16,16) 1 agree, 0 disagree, -1 n/a
    grid: Optional[Grid]
    flags: List[str] = field(default_factory=list)
    text: List[str] = field(default_factory=list)   # the decoded hex rows
    legend: dict = field(default_factory=dict)      # highlight bytes + address, as read

    @property
    def n_low_conf(self) -> int:
        return int((self.conf < 0.5).sum())

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "base_address": (None if self.base_address is None else "%08X" % self.base_address),
            "data": bytes(self.data).hex(),
            "conf": [[round(float(v), 4) for v in row] for row in self.conf],
            "row_addresses": [None if a is None else "%08X" % a for a in self.row_addresses],
            "row_addr_ok": self.row_addr_ok,
            "color_class": [[COLOR_NAMES[int(v)] for v in row] for row in self.color_class],
            "color_agree": [[int(v) for v in row] for row in self.color_agree],
            "flags": self.flags,
            "text": self.text,
            "legend": {k: (None if v is None else "%02X" % v if k != "address" else "%08X" % v)
                       for k, v in (self.legend or {}).items()},
        }


# --------------------------------------------------------------------------- #
def _cut_patches(ink: np.ndarray, grid: Grid, cells: Sequence[Tuple[int, int]],
                 gh: int, gw: int, out_x: float = 1.15, out_y: float = 0.85,
                 recenter: bool = True, tex: Optional[np.ndarray] = None) -> np.ndarray:
    """Cut one resampled patch per character cell.

    Each patch is re-centred on its own ink before it is cut.  That matters
    more than any amount of grid polishing: a global grid fit is good to a
    few tenths of a pixel, but a character cell is only ~6 px wide on a native
    frame, so a 0.7 px residual is a tenth of a glyph -- enough to cost matches.
    Centring per cell makes the registration content-driven and therefore the
    same in the atlas and at extraction time.  The centring window is exactly
    one cell wide, which on this font contains the glyph plus its blank column
    and no part of either neighbour.
    """
    if tex is None:
        tex = texture_map(ink)
    out = np.empty((len(cells), gh, gw), dtype=np.float32)
    OS = 3                     # oversampling used for the centroid
    for i, (r, c) in enumerate(cells):
        rf = grid.rows[r]
        cx = rf.x0 + (c + 0.5) * rf.cw
        cy = rf.yc
        if recenter:
            dx, dy = _cell_offset(ink, tex, grid, r, cx, cy, OS)
            cx += dx
            cy += dy
        hy = grid.row_pitch * 0.5 * out_y
        hx = rf.cw * 0.5 * out_x
        out[i] = resample_patch(ink, cy - hy, cy + hy, cx - hx, cx + hx, gh, gw)
    return out


def _cell_offset(ink: np.ndarray, tex: np.ndarray, grid: Grid, r: int,
                 cx: float, cy: float, OS: int = 3) -> Tuple[float, float]:
    """Centroid offset of one cell's glyph, x from ink and y from texture.

    y uses the horizontal-gradient map because row 0 sits one leading below the
    panel's top border, and a solid border line drags a plain vertical centroid
    up -- measured, it broke row 0 of nearly every frame.
    """
    rf = grid.rows[r]
    wy = grid.row_pitch * 0.5
    wx = rf.cw * 0.5
    ny, nx = int(round(2 * wy * OS)), int(round(2 * wx * OS))
    if ny < 2 or nx < 2:
        return 0.0, 0.0
    pi_ = resample_patch(ink, cy - wy, cy + wy, cx - wx, cx + wx, ny, nx)
    pt_ = resample_patch(tex, cy - wy, cy + wy, cx - wx, cx + wx, ny, nx)
    yy = (np.arange(ny) + 0.5) / ny * (2 * wy) - wy
    xx = (np.arange(nx) + 0.5) / nx * (2 * wx) - wx
    ti, tt = float(pi_.sum()), float(pt_.sum())
    dx = dy = 0.0
    if ti > 0.02 * ny * nx:
        dx = float(np.clip((pi_.sum(axis=0) * xx).sum() / ti, -0.35 * rf.cw, 0.35 * rf.cw))
    if tt > 0.01 * ny * nx:
        dy = float(np.clip((pt_.sum(axis=1) * yy).sum() / tt,
                           -0.35 * grid.row_pitch, 0.35 * grid.row_pitch))
    return dx, dy


def refine_grid_by_centroids(ink: np.ndarray, grid: Grid, iters: int = 3,
                             tex: Optional[np.ndarray] = None) -> Grid:
    """Close the loop on the character pitch using the glyphs themselves.

    The column matched filter is good to a couple of hundredths of a pixel in
    pitch, which is still ~1 px of drift by the far end of a 57-character row --
    enough to shave the left stroke off the high nibble and turn '80' into '30'
    (measured).  Here the per-cell ink centroids are pooled across the 16 rows,
    fitted as a straight line in the column index, and folded back into
    (x0, pitch).  Two or three passes converge to a few hundredths of a pixel.
    """
    if tex is None:
        tex = texture_map(ink)
    lay = grid.lay
    cols = [c for c in lay.addr_idx] + [c for pair in lay.byte_idx for c in pair]
    cols.sort()
    ccol = np.array(cols, dtype=float)
    for _ in range(iters):
        dxs = np.zeros((L.NROWS, len(cols)), np.float32)
        for ri in range(L.NROWS):
            rf = grid.rows[ri]
            for j, c in enumerate(cols):
                cx = rf.x0 + (c + 0.5) * rf.cw
                dxs[ri, j] = _cell_offset(ink, tex, grid, ri, cx, rf.yc)[0]
        med = np.median(dxs, axis=0)
        # robust straight line through the per-column drift
        A = np.vstack([np.ones_like(ccol), ccol]).T
        keep = np.ones(len(ccol), bool)
        for _r in range(2):
            coef, *_ = np.linalg.lstsq(A[keep], med[keep], rcond=None)
            res = np.abs(med - A @ coef)
            nk = res <= max(0.25 * float(np.median(grid.rows[0].cw)), 3 * np.median(res) + 1e-6)
            if nk.sum() >= 6:
                keep = nk
        a, b = float(coef[0]), float(coef[1])
        for rf in grid.rows:
            rf.x0 += a - 0.5 * b
            rf.cw += b
        if abs(a) < 0.02 and abs(b) < 0.002:
            break
    return grid


def _cell_bg_rgb(rgb_sheared: np.ndarray, grid: Grid, r: int, c0: int, c1: int) -> np.ndarray:
    """Median colour of the *background* pixels of a byte cell (the brightest half)."""
    y0, y1, x0, x1 = grid.cell_box(r, c0)
    _, _, _, x1b = grid.cell_box(r, c1)
    ys = slice(max(int(round(y0)), 0), max(int(round(y1)), 1))
    xs = slice(max(int(round(x0)), 0), max(int(round(x1b)), 1))
    patch = rgb_sheared[ys, xs]
    if patch.size == 0:
        return np.array([0, 0, 0], np.float32)
    lum = patch.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    thr = np.percentile(lum, 55.0)
    sel = patch.reshape(-1, 3)[(lum >= thr).reshape(-1)]
    if sel.size == 0:
        sel = patch.reshape(-1, 3)
    return np.median(sel.astype(np.float32), axis=0)


def classify_color(rgb: np.ndarray, sat_thresh: float = 0.30) -> int:
    """Map a background colour to an index into COLOR_NAMES."""
    r, g, b = [float(v) for v in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 1e-3:
        return 0
    sat = (mx - mn) / mx
    if sat < sat_thresh:
        return 0
    hi = [v > mx * 0.55 for v in (r, g, b)]
    if hi == [False, True, True]:
        return 1   # aqua
    if hi == [True, True, False]:
        return 2   # yellow
    if hi == [False, True, False]:
        return 3   # lime
    if hi == [True, False, True]:
        return 4   # fuchsia
    if hi == [True, False, False]:
        return 5   # orange -- only the legend's own "DUMP ADRn =" block
    return 0


# --------------------------------------------------------------------------- #
def read_legend(rgb_sheared: np.ndarray, grid: Grid, atlas: Atlas,
                hex_idx: Sequence[int], ink: np.ndarray,
                tex: Optional[np.ndarray] = None) -> dict:
    """Read the colour legend line under the table.

    The viewer prints "Aqua = F0  Yellow = F7  Lime = FF  Fuchsia = XX
    DUMP ADRn = AAAAAAAA", each field on its own coloured block.  Reading it
    makes the colour cross-check SELF-CALIBRATING instead of assuming the
    power-up values -- which matters, because panel columns 10..13 step those
    four bytes and an operator (or a mis-aimed button) changes them.  The
    orange block additionally repeats the base address, an independent read of
    the single most damaging thing to get wrong.

    Returns {"aqua": int|None, ..., "address": int|None, "row_y": float}.
    """
    out = {"aqua": None, "yellow": None, "lime": None, "fuchsia": None, "address": None}
    if not grid.rows:
        return out
    rf = grid.rows[-1]
    yc = rf.yc + grid.row_pitch
    if yc + grid.row_pitch * 0.5 >= grid.height:
        return out
    lrow = RowFit(yc=yc, x0=rf.x0, cw=rf.cw, score=rf.score)
    lgrid = Grid(slope=grid.slope, row_pitch=grid.row_pitch, rows=[lrow],
                 lay=grid.lay, score=grid.score, height=grid.height, width=grid.width)

    ncols = int((grid.width - rf.x0) / rf.cw)
    ncols = max(0, min(ncols, 120))
    cls, inked = [], []
    for c in range(ncols):
        col = _cell_bg_rgb(rgb_sheared, lgrid, 0, c, c)
        cls.append(classify_color(col))
        y0, y1, x0, x1 = lgrid.cell_box(0, c)
        a, b = max(int(y0), 0), max(int(y1), 1)
        xa, xb = max(int(x0), 0), max(int(x1), 1)
        sub = ink[a:b, xa:xb]
        inked.append(float(sub.mean()) if sub.size else 0.0)

    def runs(target):
        r, start = [], None
        for c in range(ncols):
            if cls[c] == target and start is None:
                start = c
            elif cls[c] != target and start is not None:
                r.append((start, c - 1)); start = None
        if start is not None:
            r.append((start, ncols - 1))
        return [x for x in r if x[1] - x[0] >= 3]

    def read_cells(cells):
        if not cells:
            return None, 0.0
        p = _cut_patches(ink, lgrid, [(0, c) for c in cells], atlas.gh, atlas.gw, tex=tex)
        idx, ncc, mrg = atlas.classify(p, allowed=hex_idx)
        conf = _conf(ncc, mrg)
        txt = "".join(atlas.labels[i] for i in idx)
        try:
            return int(txt, 16), float(conf.min())
        except ValueError:
            return None, 0.0

    def tail_inked(a, b, n):
        """The last n ADJACENT well-inked cells of a legend block.

        "last n inked cells" is not enough: a half-pixel of grid error leaks a
        trace of ink into the trailing blank and silently shifts the field by
        one character.  Requiring the cells to be adjacent and clearly inked
        relative to the block makes the field-end unambiguous.
        """
        blk = [inked[c] for c in range(a, b + 1)]
        if not blk:
            return []
        thr = max(0.35 * max(blk), 0.03)
        cs = [c for c in range(a, b + 1) if inked[c] > thr]
        if len(cs) < n:
            return []
        end = cs[-1]
        run = [end]
        while len(run) < n:
            nxt = run[0] - 1
            if nxt < a or inked[nxt] <= thr:
                return []
            run.insert(0, nxt)
        return run

    for name, ci in (("aqua", 1), ("yellow", 2), ("lime", 3), ("fuchsia", 4)):
        rs = runs(ci)
        if not rs:
            continue
        a, b = rs[0]
        v, cf = read_cells(tail_inked(a, b, 2))
        if v is not None and cf >= 0.25:
            out[name] = v
    rs = runs(5)
    if rs:
        a, b = rs[-1]
        v, cf = read_cells(tail_inked(a, b, 8))
        if v is not None and cf >= 0.25:
            out["address"] = v
    return out


# --------------------------------------------------------------------------- #
class PageExtractor:
    def __init__(self, atlas: Optional[Atlas] = None, atlas_path: Optional[str] = None,
                 highlight: Optional[dict] = None, use_color: bool = True,
                 read_legend: bool = True):
        if atlas is None:
            p = atlas_path or DEFAULT_ATLAS
            atlas = Atlas.load(p)
        self.atlas = atlas
        self.hex_idx = [atlas.labels.index(c) for c in HEX if c in atlas.labels]
        self.highlight = dict(HIGHLIGHT_DEFAULT)
        if highlight:
            self.highlight.update(highlight)
        self.use_color = use_color
        self.read_legend = read_legend

    # -- main ---------------------------------------------------------------- #
    def extract(self, img, grid: Optional[Grid] = None, prior: Optional[Grid] = None,
                refine_pitch: bool = True, retry: bool = True) -> PageResult:
        """Decode one page.

        If the page fails its own address self-check (the 16 row addresses must
        ascend by exactly 0x10) and `retry` is set, the geometry stage is run
        again with the alternative background estimate and the better-checking
        result wins.  The self-check is content-based and independent of the
        pixels the grid was fitted on, so the retry cannot make a good frame
        worse; a frame that passes first time costs nothing extra.
        """
        rgb = as_rgb(img)
        if grid is None and retry:
            first = self.extract(rgb, prior=prior, refine_pitch=refine_pitch, retry=False)
            if sum(first.row_addr_ok) >= L.NROWS - 1:
                return first
            alt = self._extract_one(rgb, fit_grid(rgb, ink_mode="max"), refine_pitch)
            alt.flags.append("retried-with-alt-ink")
            return alt if sum(alt.row_addr_ok) > sum(first.row_addr_ok) else first
        if grid is None:
            grid = fit_grid(rgb, prior=prior)
        return self._extract_one(rgb, grid, refine_pitch)

    def _extract_one(self, rgb, grid: Grid, refine_pitch: bool = True) -> PageResult:
        ink = getattr(grid, "ink", None)
        if ink is None:
            ink = shear_rows(ink_map(rgb, ry=max(2, int(round(grid.row_pitch * 1.3))),
                                     rx=max(2, int(round(grid.row_pitch * 3.0)))), grid.slope)
        tex = texture_map(ink)
        if refine_pitch:
            grid = refine_grid_by_centroids(ink, grid, tex=tex)
        rgb_sh = np.stack([shear_rows(rgb[:, :, k].astype(np.float32), grid.slope)
                           for k in range(3)], axis=2)
        return self._decode(grid, ink, tex, rgb_sh)

    def _decode(self, grid: Grid, ink: np.ndarray, tex: np.ndarray,
                rgb_sh: Optional[np.ndarray]) -> PageResult:
        lay = grid.lay
        flags: List[str] = []

        legend = {}
        if self.read_legend and rgb_sh is not None:
            legend = read_legend(rgb_sh, grid, self.atlas, self.hex_idx, ink, tex)
        highlight = dict(self.highlight)
        for k in ("aqua", "yellow", "lime", "fuchsia"):
            if legend.get(k) is not None:
                highlight[k] = legend[k]

        # ---- address column -------------------------------------------------
        acells = [(r, c) for r in range(L.NROWS) for c in lay.addr_idx]
        ap = _cut_patches(ink, grid, acells, self.atlas.gh, self.atlas.gw, tex=tex)
        aidx, ancc, amrg = self.atlas.classify(ap, allowed=self.hex_idx)
        achars = np.array([self.atlas.labels[i] for i in aidx]).reshape(L.NROWS, 8)
        aconf = _conf(ancc, amrg).reshape(L.NROWS, 8)

        row_addr: List[Optional[int]] = []
        for r in range(L.NROWS):
            try:
                row_addr.append(int("".join(achars[r]), 16))
            except ValueError:
                row_addr.append(None)

        base, base_votes = _vote_base(row_addr)
        row_ok = [a is not None and base is not None and a == (base + 0x10 * r) & 0xFFFFFFFF
                  for r, a in enumerate(row_addr)]
        if base is None:
            flags.append("no-base-address")
        elif base_votes < L.NROWS:
            flags.append("addr-rows-disagree=%d" % (L.NROWS - base_votes))
        if base is not None and (base & 0xFF):
            flags.append("base-not-page-aligned")
        legend_addr = legend.get("address")
        if legend_addr is not None:
            if base is None:
                base = legend_addr
                flags.append("base-from-legend")
            elif legend_addr != base:
                flags.append("legend-address-differs=%08X" % legend_addr)
                if base_votes < L.NROWS // 2:
                    base = legend_addr
                    flags.append("base-taken-from-legend")

        # ---- hex digits ------------------------------------------------------
        hcells = [(r, c) for r in range(L.NROWS) for (hi, lo) in lay.byte_idx for c in (hi, lo)]
        hp = _cut_patches(ink, grid, hcells, self.atlas.gh, self.atlas.gw, tex=tex)
        hidx, hncc, hmrg = self.atlas.classify(hp, allowed=self.hex_idx)
        hchars = np.array([self.atlas.labels[i] for i in hidx]).reshape(L.NROWS, 32)
        dconf = _conf(hncc, hmrg).reshape(L.NROWS, 32)

        data = bytearray(256)
        conf = np.zeros((L.NROWS, L.NBYTES), np.float32)
        for r in range(L.NROWS):
            for k in range(L.NBYTES):
                v = int(hchars[r, 2 * k], 16) * 16 + int(hchars[r, 2 * k + 1], 16)
                data[r * 16 + k] = v
                conf[r, k] = min(dconf[r, 2 * k], dconf[r, 2 * k + 1])

        # ---- highlight colours ---------------------------------------------
        ccls = np.zeros((L.NROWS, L.NBYTES), np.int8)
        cbyte = np.full((L.NROWS, L.NBYTES), -1, np.int16)
        cagree = np.full((L.NROWS, L.NBYTES), -1, np.int8)
        if self.use_color and rgb_sh is not None:
            for r in range(L.NROWS):
                for k in range(L.NBYTES):
                    hi, lo = lay.byte_idx[k]
                    col = _cell_bg_rgb(rgb_sh, grid, r, hi, lo)
                    ci = classify_color(col)
                    ccls[r, k] = ci
                    if ci and COLOR_NAMES[ci] in highlight:
                        v = highlight[COLOR_NAMES[ci]]
                        if v is not None:
                            cbyte[r, k] = v
                            agree = int(v == data[r * 16 + k])
                            cagree[r, k] = agree
                            if agree:
                                conf[r, k] = max(conf[r, k], 0.5 * (1.0 + conf[r, k]))
                            else:
                                conf[r, k] = min(conf[r, k], 0.25)
            nbad = int((cagree == 0).sum())
            if nbad:
                flags.append("colour-mismatch=%d" % nbad)

        text = []
        for r in range(L.NROWS):
            row = "".join(achars[r]) + "  " + " ".join(
                hchars[r, 2 * k] + hchars[r, 2 * k + 1] for k in range(16))
            text.append(row)

        ok = base is not None and all(row_ok) and float(conf.min()) > 0.0
        return PageResult(ok=ok, base_address=base, data=data, conf=conf,
                          digit_conf=dconf, row_addresses=row_addr, row_addr_ok=row_ok,
                          addr_conf=aconf, color_class=ccls, color_byte=cbyte,
                          color_agree=cagree, grid=grid, flags=flags, text=text,
                          legend=legend)


    def extract_with_grid(self, grid: Grid, ink: np.ndarray, tex: np.ndarray) -> PageResult:
        """Decode from an already-fitted grid (used by the self-supervised atlas)."""
        return self._decode(grid, ink, tex, None)

    # -- atlas construction ------------------------------------------------- #
    @staticmethod
    def build_atlas_selfsupervised(images, rounds: int = 2, gh: int = None, gw: int = None,
                                   meta: Optional[dict] = None) -> Atlas:
        """Build a glyph atlas from frames whose contents are UNKNOWN.

        No oracle, no manual labelling: the screen labels itself.  Row r of a
        page shows the address base + 0x10*r, so on every page

            * the last address digit is '0' on all 16 rows, and
            * the second-to-last address digit runs 0,1,2,...,F down the rows.

        That is one labelled sample of every one of the 16 classes per frame,
        free, on any capture of any machine -- which is what makes this usable
        on Felipe's instrument, whose PROGRAM 893 flash is undumped and has no
        oracle at all.  A second round then re-labels ALL eight address digits
        of every row using the base address voted from round one, which
        multiplies the sample count and sharpens the templates.
        """
        from .atlas import GH, GW
        gh = gh or GH
        gw = gw or GW
        prepared = []
        for img in images:
            rgb = as_rgb(img)
            grid = fit_grid(rgb)
            ink = getattr(grid, "ink")
            tex = texture_map(ink)
            grid = refine_grid_by_centroids(ink, grid, tex=tex)
            prepared.append((grid, ink, tex))

        b = AtlasBuilder(gh=gh, gw=gw)
        for grid, ink, tex in prepared:
            lay = grid.lay
            cells, chars = [], []
            for r in range(L.NROWS):
                cells.append((r, lay.addr_idx[6])); chars.append("%X" % r)
                cells.append((r, lay.addr_idx[7])); chars.append("0")
            b.add_many(chars, _cut_patches(ink, grid, cells, gh, gw, tex=tex))
        atlas = b.finish(meta={"bootstrap": "address-column"})

        for _ in range(max(rounds - 1, 0)):
            ex = PageExtractor(atlas=atlas, use_color=False, read_legend=False)
            b = AtlasBuilder(gh=gh, gw=gw)
            used = 0
            for grid, ink, tex in prepared:
                res = ex.extract_with_grid(grid, ink, tex)
                if res.base_address is None or sum(res.row_addr_ok) < L.NROWS - 1:
                    continue
                used += 1
                lay = grid.lay
                cells, chars = [], []
                for r in range(L.NROWS):
                    a = (res.base_address + 0x10 * r) & 0xFFFFFFFF
                    txt = "%08X" % a
                    for j, c in enumerate(lay.addr_idx):
                        cells.append((r, c)); chars.append(txt[j])
                b.add_many(chars, _cut_patches(ink, grid, cells, gh, gw, tex=tex))
            if used:
                atlas = b.finish(meta={"bootstrap": "address-column", "self_trained_frames": used})
        m = dict(meta or {}); m.setdefault("bootstrap", "address-column")
        atlas.meta = {**(atlas.meta or {}), **m}
        return atlas


    @staticmethod
    def build_atlas(samples, gh: int = None, gw: int = None, meta: Optional[dict] = None,
                    grid_cb=None) -> Atlas:
        """samples: iterable of (image, base_address, page_bytes).

        Every character of every frame is labelled by the oracle, so an atlas
        costs nothing but the frames.
        """
        from .atlas import GH, GW
        gh = gh or GH
        gw = gw or GW
        b = AtlasBuilder(gh=gh, gw=gw)
        nframes = 0
        for img, base, page in samples:
            rgb = as_rgb(img)
            grid = fit_grid(rgb)
            if grid_cb:
                grid_cb(grid)
            ink = getattr(grid, "ink")
            tex = texture_map(ink)
            grid = refine_grid_by_centroids(ink, grid, tex=tex)
            lay = grid.lay
            cells, chars = [], []
            for r in range(L.NROWS):
                a = (base + 0x10 * r) & 0xFFFFFFFF
                s = "%08X" % a
                for j, c in enumerate(lay.addr_idx):
                    cells.append((r, c)); chars.append(s[j])
                for k, (hi, lo) in enumerate(lay.byte_idx):
                    v = page[r * 16 + k]
                    cells.append((r, hi)); chars.append("%X" % (v >> 4))
                    cells.append((r, lo)); chars.append("%X" % (v & 15))
                for j, c in enumerate(lay.sep_idx):
                    cells.append((r, c)); chars.append("-" if j == 7 else " ")
                for c in range(lay.addr_idx[-1] + 1, lay.byte_idx[0][0]):
                    cells.append((r, c)); chars.append(" ")
            patches = _cut_patches(ink, grid, cells, gh, gw, tex=tex)
            b.add_many(chars, patches)
            nframes += 1
        m = dict(meta or {}); m["frames"] = nframes
        return b.finish(meta=m)


def _conf(ncc: np.ndarray, margin: np.ndarray) -> np.ndarray:
    """Per-character confidence in [0,1] from the template-match margin.

    Calibrated by measurement on 23 native emulator frames (11,776 hex digits):
    correct digits have margin >= 0.054 at the 0.1th percentile and a median of
    0.245, while the digits that were actually wrong had margins of 0.0034 and
    0.0047.  The knee is therefore put at margin ~0.004..0.09 and ncc
    ~0.30..0.55.  The raw margin and ncc stay available to a downstream voter.
    """
    a = np.clip((margin - 0.004) / 0.09, 0.0, 1.0)
    b = np.clip((ncc - 0.30) / 0.25, 0.0, 1.0)
    return (a * b).astype(np.float32)


def _vote_base(row_addr: Sequence[Optional[int]]) -> Tuple[Optional[int], int]:
    """The base address is whatever `addr_r - 0x10*r` most rows agree on."""
    votes = {}
    for r, a in enumerate(row_addr):
        if a is None:
            continue
        b = (a - 0x10 * r) & 0xFFFFFFFF
        votes[b] = votes.get(b, 0) + 1
    if not votes:
        return None, 0
    best = max(votes.items(), key=lambda kv: kv[1])
    return best[0], best[1]
