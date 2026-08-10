"""A synthetic instrument, so the decoder can be measured instead of admired.

The viewer's font was recovered from the emulator as 5x7 pixel bitmaps, and the
screen is 640x240 displayed at 4:3 -- so its pixels are twice as tall as they
are wide, which is why a character cell measures about 6 x 11 on a captured
frame.  That is the whole geometry, and it is little enough to re-create.

This module renders a page of the MEMORY DUMP screen from known bytes, warps it
through a homography into a camera-sized frame, and adds the things a handheld
camera actually adds: blur, sensor noise, a brightness gradient, and a
frame-to-frame wobble.  The decoder then has to recover bytes we already know.

That makes three questions answerable with numbers rather than opinion:

    * does the whole loop work -- track, read, vote, lock -- end to end?
    * how much resolution does the operator actually need?  (`sweep`)
    * does hand shake break the tracker, and at what amplitude?

The renderer deliberately shares no code with the decoder's geometry: it lays
characters out from the font metrics, and the decoder has to find them.  A test
that used the decoder's own grid to draw the image would prove nothing.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import geom as G

FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "wip-real", "r1-psf", "font_native.json")

CHAR_W, CHAR_H = 5, 7           # the glyph bitmap, in native screen pixels
PITCH_X, PITCH_Y = 6, 8         # cell pitch on the screen, in native pixels
ORIGIN_X, ORIGIN_Y = 8, 16
SCREEN_W, SCREEN_H = 640, 240

# How tall a character cell looks relative to its width once the screen has
# been displayed and photographed.  This is MEASURED off a real capture
# (row pitch 11.39 px against a character pitch of 5.83), not derived from any
# claim about the panel's pixel aspect -- the two are easy to confuse and only
# the measured one matters for generating a realistic test image.
CELL_ASPECT = 1.95


def load_font(path: str = FONT_PATH) -> Dict[str, np.ndarray]:
    with open(path) as fh:
        raw = json.load(fh)
    return {k: np.array([[1.0 if ch == "#" else 0.0 for ch in row] for row in rows],
                        np.float32) for k, rows in raw.items()}


# The viewer's highlight colours, printed in its own footer legend:
#   "Aqua = F0   Yellow = F7   Lime = FF   Fuchsia = XX"
# Bytes equal to one of those values are drawn on a coloured background, which
# is a second, independent statement of their value -- see recog.colour_veto.
HIGHLIGHT = {0xF0: (0.55, 0.95, 0.95), 0xF7: (0.95, 0.95, 0.45), 0xFF: (0.55, 0.95, 0.45)}


def render_screen(base: int, data: bytes, font: Optional[Dict[str, np.ndarray]] = None,
                  ink: float = 0.10, paper: float = 0.92,
                  highlight: bool = True) -> np.ndarray:
    """One page as the 640x240 screen would show it: dark text on light.

    Returns HxWx3 when `highlight` is on, so the colour channel is available.
    """
    font = font or load_font()
    img = np.full((SCREEN_H, SCREEN_W), paper, np.float32)
    for r in range(16):
        addr = (base + 0x10 * r) & 0xFFFFFFFF
        row = data[r * 16:(r + 1) * 16]
        txt = "%08X  " % addr
        txt += " ".join("%02X" % b for b in row[:8])
        txt += "-"
        txt += " ".join("%02X" % b for b in row[8:])
        txt += "  " + "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in row)
        y = ORIGIN_Y + r * PITCH_Y
        for c, ch in enumerate(txt):
            g = font.get(ch.upper())
            if g is None:
                g = font.get(".", None)
                if g is None:
                    continue
            x = ORIGIN_X + c * PITCH_X
            if x + CHAR_W > SCREEN_W or y + CHAR_H > SCREEN_H:
                break
            sub = img[y:y + CHAR_H, x:x + CHAR_W]
            img[y:y + CHAR_H, x:x + CHAR_W] = np.where(g > 0, ink, sub)
    if not highlight:
        return img
    rgb = np.repeat(img[:, :, None], 3, axis=2)
    for r in range(16):
        for k in range(16):
            col = HIGHLIGHT.get(data[r * 16 + k])
            if col is None:
                continue
            # Byte k's high nibble is at character 10+3k for every k: the '-'
            # after byte 7 occupies the separator slot, it does not add one.
            x0 = ORIGIN_X + G.BYTE_COLS[k][0] * PITCH_X
            y0 = ORIGIN_Y + r * PITCH_Y
            blk = rgb[y0:y0 + CHAR_H, x0:x0 + 2 * PITCH_X]
            paperish = blk.mean(axis=2) > (ink + paper) * 0.5
            for c in range(3):
                blk[:, :, c] = np.where(paperish, col[c], blk[:, :, c])
    return rgb


def text_quad_on_screen() -> np.ndarray:
    """Where the 16 x 57 character block sits on the 640x240 screen.

    Returned in screen pixels; the simulator warps it along with the picture so
    the test knows the true answer the decoder is supposed to converge on.
    """
    x0 = ORIGIN_X
    x1 = ORIGIN_X + G.NCOL_HEX * PITCH_X
    y0 = ORIGIN_Y
    y1 = ORIGIN_Y + G.NROW * PITCH_Y
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)


# --------------------------------------------------------------------------- #
def gauss_blur(a: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0.01:
        return a
    rad = max(1, int(math.ceil(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-rad, rad + 1) / sigma) ** 2)
    k /= k.sum()
    out = np.zeros_like(a)
    pad = np.pad(a, ((0, 0), (rad, rad)), mode="edge")
    for i, w in enumerate(k):
        out += w * pad[:, i:i + a.shape[1]]
    a2 = out
    out = np.zeros_like(a2)
    pad = np.pad(a2, ((rad, rad), (0, 0)), mode="edge")
    for i, w in enumerate(k):
        out += w * pad[i:i + a.shape[0], :]
    return out


def warp(screen: np.ndarray, H: np.ndarray, out_w: int, out_h: int,
         bg: float = 0.05) -> np.ndarray:
    """Inverse-map the screen into a camera-sized frame through H (screen -> frame)."""
    Hi = np.linalg.inv(H)
    yy, xx = np.mgrid[0:out_h, 0:out_w].astype(np.float64)
    den = Hi[2, 0] * xx + Hi[2, 1] * yy + Hi[2, 2]
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    sx = (Hi[0, 0] * xx + Hi[0, 1] * yy + Hi[0, 2]) / den
    sy = (Hi[1, 0] * xx + Hi[1, 1] * yy + Hi[1, 2]) / den
    inside = (sx >= 0) & (sx <= screen.shape[1] - 1.01) & (sy >= 0) & (sy <= screen.shape[0] - 1.01)
    v = G.sample_bilinear(screen.astype(np.float32), np.clip(sy, 0, screen.shape[0] - 1.01),
                          np.clip(sx, 0, screen.shape[1] - 1.01))
    return np.where(inside, v, bg).astype(np.float32)


def quad_homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    A = np.zeros((8, 8)); b = np.zeros(8)
    for i in range(4):
        x, y = src[i]; X, Y = dst[i]
        A[2 * i] = [x, y, 1, 0, 0, 0, -x * X, -y * X]; b[2 * i] = X
        A[2 * i + 1] = [0, 0, 0, x, y, 1, -x * Y, -y * Y]; b[2 * i + 1] = Y
    h = np.linalg.solve(A, b)
    return np.array([[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]])


class SimSource:
    """A frame source that behaves like a handheld camera on a real screen."""

    name = "simulated"

    def __init__(self, base: int, data: bytes, width: int = 1280, height: int = 720,
                 px_per_char: float = 12.0, blur: float = 1.1, noise: float = 3.0,
                 shake: float = 1.5, tilt: float = 0.0, seed: int = 12345,
                 pages: Optional[List[Tuple[int, bytes]]] = None,
                 page_every: int = 0):
        self.size = (width, height)
        self.rng = np.random.default_rng(seed)
        self.font = load_font()
        self.pages = pages or [(base, data)]
        self.page_every = page_every
        self.pi = 0
        self.px_per_char = px_per_char
        self.blur = blur
        self.noise = noise
        self.shake = shake
        self.tilt = tilt
        self.n = 0
        self._screens = {b: render_screen(b, d, self.font) for b, d in self.pages}
        self.true_quad: Optional[np.ndarray] = None

    def _dst_quad(self) -> np.ndarray:
        w, h = self.size
        block_w = G.NCOL_HEX * self.px_per_char
        block_h = G.NROW * self.px_per_char * CELL_ASPECT
        cx, cy = w * 0.5, h * 0.5
        q = np.array([[-block_w / 2, -block_h / 2], [block_w / 2, -block_h / 2],
                      [block_w / 2, block_h / 2], [-block_w / 2, block_h / 2]], float)

        # Hand motion, not white noise.  A hand drifts: position, distance and
        # angle wander smoothly and are strongly correlated from one frame to
        # the next, with only a small uncorrelated tremor on top.  Perturbing
        # the four corners independently every frame -- which is what an
        # obvious implementation does -- is a far harsher and quite unphysical
        # adversary: it deforms the panel into a different quadrilateral thirty
        # times a second, which no tracker should be expected to follow and no
        # real camera produces.
        s = self.shake
        if s:
            a = 0.90                                  # drift persistence
            self._drift = getattr(self, "_drift", np.zeros(5))
            self._drift = a * self._drift + np.sqrt(1 - a * a) * self.rng.normal(
                0, [1.5 * s, 1.5 * s, 0.004 * s, 0.004 * s, 0.004 * s])
            dx, dy, ds, kx, ky = self._drift
            q = q * (1.0 + ds)
            for i, sgn in ((0, +1), (1, +1), (2, -1), (3, -1)):
                q[i, 0] *= (1.0 + sgn * kx)
            for i, sgn in ((0, -1), (1, +1), (2, +1), (3, -1)):
                q[i, 1] *= (1.0 + sgn * ky)
            q = q + np.array([dx, dy]) + self.rng.normal(0, 0.15 * s, size=(4, 2))
        if self.tilt:
            t = self.tilt
            q[0, 0] *= (1 - t); q[3, 0] *= (1 - t)
            q[0, 1] *= (1 - t * 0.3); q[3, 1] *= (1 - t * 0.3)
        return q + np.array([cx, cy])

    def read(self) -> np.ndarray:
        if self.page_every and self.n and self.n % self.page_every == 0:
            self.pi = (self.pi + 1) % len(self.pages)
        base, _ = self.pages[self.pi]
        screen = self._screens[base]
        dst = self._dst_quad()
        src = text_quad_on_screen()
        H = quad_homography(src, dst)
        self.true_quad = dst.copy()
        w, h = self.size
        if screen.ndim == 3:
            img = np.stack([warp(screen[:, :, c], H, w, h) for c in range(3)], axis=2)
            if self.blur:
                img = np.stack([gauss_blur(img[:, :, c], self.blur) for c in range(3)], axis=2)
        else:
            img = warp(screen, H, w, h)
            if self.blur:
                img = gauss_blur(img, self.blur)
        # a brightness gradient, as any real photograph of a lit screen has
        yy, xx = np.mgrid[0:h, 0:w]
        shade = (0.85 + 0.3 * (xx / max(w - 1, 1)) * (1 - 0.4 * yy / max(h - 1, 1)))
        if img.ndim == 3:
            img = img * shade[:, :, None]
        else:
            img = np.repeat((img * shade)[:, :, None], 3, axis=2)
        img = np.clip(img * 255.0 + self.rng.normal(0, self.noise, img.shape), 0, 255)
        self.n += 1
        return img.astype(np.uint8)

    @property
    def alive(self) -> bool:
        return True

    @property
    def error(self) -> str:
        return ""

    @property
    def dropped(self) -> int:
        return 0

    def close(self) -> None:
        pass


def parse_sim_spec(spec: str, oracle_dir: Optional[str] = None,
                   width: int = 1280, height: int = 720) -> SimSource:
    """`sim:48019000,px=12,blur=1.1,shake=1.5,tilt=0.15,pages=2`"""
    body = spec.split(":", 1)[1] if ":" in spec else spec
    parts = body.split(",")
    base = int(parts[0], 16) if parts and parts[0] else 0x48019000
    kw = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            kw[k.strip()] = float(v)
    npages = int(kw.pop("pages", 1))
    page_every = int(kw.pop("page_every", 120))

    data_for = {}
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from kn7000dump.oracle import Oracle
        orc = Oracle(oracle_dir) if oracle_dir else Oracle()
        for i in range(npages):
            d = orc.page(base + 0x100 * i)
            if d is None:
                raise ValueError
            data_for[base + 0x100 * i] = d
    except Exception:
        rng = np.random.default_rng(7)
        for i in range(npages):
            data_for[base + 0x100 * i] = bytes(rng.integers(0, 256, 256, dtype=np.uint8))

    pages = [(a, data_for[a]) for a in sorted(data_for)]
    return SimSource(pages[0][0], pages[0][1], width, height,
                     px_per_char=kw.get("px", 12.0), blur=kw.get("blur", 1.1),
                     noise=kw.get("noise", 3.0), shake=kw.get("shake", 1.5),
                     tilt=kw.get("tilt", 0.0), seed=int(kw.get("seed", 12345)),
                     pages=pages, page_every=page_every if npages > 1 else 0)
