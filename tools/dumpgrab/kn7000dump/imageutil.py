"""Small numpy-only image helpers (no OpenCV/scipy dependency).

Everything the extractor needs: load, grayscale, integral-image box blur,
bilinear resample, and a vertical-shear resampler used for de-rotation.
"""
from __future__ import annotations

import numpy as np

try:  # Pillow is used only for file I/O; arrays work without it.
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


def load_rgb(path) -> np.ndarray:
    """Load an image file as HxWx3 uint8 RGB."""
    if Image is None:
        raise RuntimeError("Pillow is required to load image files")
    im = Image.open(path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    return np.asarray(im, dtype=np.uint8)


def as_rgb(img) -> np.ndarray:
    """Accept a path, a PIL image or an array; return HxWx3 uint8 RGB."""
    if isinstance(img, np.ndarray):
        a = img
        if a.ndim == 2:
            a = np.repeat(a[:, :, None], 3, axis=2)
        if a.dtype != np.uint8:
            a = np.clip(a, 0, 255).astype(np.uint8)
        return a[:, :, :3]
    if Image is not None and isinstance(img, Image.Image):
        return np.asarray(img.convert("RGB"), dtype=np.uint8)
    return load_rgb(img)


def gray(rgb: np.ndarray) -> np.ndarray:
    """Luma, float32."""
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)
    return 0.299 * r + 0.587 * g + 0.114 * b


def integral(a: np.ndarray) -> np.ndarray:
    out = np.zeros((a.shape[0] + 1, a.shape[1] + 1), dtype=np.float64)
    out[1:, 1:] = a.cumsum(0).cumsum(1)
    return out


def box_mean(a: np.ndarray, ry: int, rx: int) -> np.ndarray:
    """Mean over a (2ry+1) x (2rx+1) window, edge-clamped, via integral image."""
    h, w = a.shape
    ii = integral(a.astype(np.float64))
    ys = np.arange(h)
    xs = np.arange(w)
    y0 = np.clip(ys - ry, 0, h)
    y1 = np.clip(ys + ry + 1, 0, h)
    x0 = np.clip(xs - rx, 0, w)
    x1 = np.clip(xs + rx + 1, 0, w)
    s = (ii[y1][:, x1] - ii[y0][:, x1] - ii[y1][:, x0] + ii[y0][:, x0])
    n = (y1 - y0)[:, None] * (x1 - x0)[None, :]
    return (s / np.maximum(n, 1)).astype(np.float32)


def sample_bilinear(a: np.ndarray, ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    """Bilinear sample of a 2-D array at float coordinates (broadcast together)."""
    h, w = a.shape
    ys = np.clip(ys, 0, h - 1.001)
    xs = np.clip(xs, 0, w - 1.001)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = (ys - y0).astype(np.float32)
    fx = (xs - x0).astype(np.float32)
    y1 = np.minimum(y0 + 1, h - 1)
    x1 = np.minimum(x0 + 1, w - 1)
    v = (a[y0, x0] * (1 - fy) * (1 - fx) + a[y1, x0] * fy * (1 - fx)
         + a[y0, x1] * (1 - fy) * fx + a[y1, x1] * fy * fx)
    return v


def resample_patch(a: np.ndarray, y0: float, y1: float, x0: float, x1: float,
                   oh: int, ow: int) -> np.ndarray:
    """Resample the axis-aligned box [y0,y1) x [x0,x1) into an oh x ow patch."""
    yy = y0 + (np.arange(oh, dtype=np.float32) + 0.5) * (y1 - y0) / oh
    xx = x0 + (np.arange(ow, dtype=np.float32) + 0.5) * (x1 - x0) / ow
    return sample_bilinear(a, yy[:, None], xx[None, :])


def shear_rows(a: np.ndarray, slope: float) -> np.ndarray:
    """Vertical shear: row y of the output samples y + slope*(x - w/2).

    A small rotation of the screen is, over the width of one text panel,
    indistinguishable from this shear -- and it is far cheaper to undo.
    """
    if abs(slope) < 1e-9:
        return a
    h, w = a.shape
    xs = np.arange(w, dtype=np.float32)
    ys = np.arange(h, dtype=np.float32)
    yy = ys[:, None] + slope * (xs[None, :] - w * 0.5)
    xx = np.broadcast_to(xs[None, :], (h, w))
    return sample_bilinear(a, yy, xx)


def local_max(a: np.ndarray, ry: int, rx: int) -> np.ndarray:
    """Separable maximum filter over a (2ry+1) x (2rx+1) window, edge-clamped.

    Used as the "paper" estimate for the ink map: unlike a box mean, a local
    maximum does not bleed the bright panel far out into the black area around
    it, so the surround does not turn into fake ink.
    """
    from numpy.lib.stride_tricks import sliding_window_view
    out = a
    if ry > 0:
        pad = np.pad(out, ((ry, ry), (0, 0)), mode="edge")
        out = sliding_window_view(pad, 2 * ry + 1, axis=0).max(axis=-1)
    if rx > 0:
        pad = np.pad(out, ((0, 0), (rx, rx)), mode="edge")
        out = sliding_window_view(pad, 2 * rx + 1, axis=1).max(axis=-1)
    return np.ascontiguousarray(out)
