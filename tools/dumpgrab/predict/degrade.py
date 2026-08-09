#!/usr/bin/env python3
"""degrade.py -- composite-video-like damage models for the KN7000 debug-screen frames.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
MAME gives us pixel-exact frames. A real capture of the KN7000's rear composite output
will not be pixel-exact. Until the grabber physically arrives there is no way to measure
the real degradation, so this module *simulates* it and the sweep measures extraction
accuracy against severity.

  ==> THIS IS A SIMULATION. ITS FIDELITY TO THE ACTUAL CAPTURE CHAIN IS UNVERIFIED. <==

The parameter ranges below are chosen from what NTSC/PAL composite and cheap USB grabbers
are known to do (luma ~4.2 MHz vs chroma ~0.6 MHz, 3.58/4.43 MHz subcarrier, 8-bit ADC,
MJPEG at q~70-85, 720x480 or 720x576 sampling of a 640x240-ish source). They are NOT
measurements of Felipe's chain. When the grabber arrives, the honest move is to re-run the
sweep with the *real* frames and see where on these curves they land.

AXES (each takes sev in [0,1]; sev=0 is a no-op, and each axis documents its physical unit)

  noise_gaussian     additive white gaussian noise, sigma 0 -> 40 (8-bit levels)
  noise_saltpepper   impulse noise, 0 -> 5 % of pixels forced to 0 or 255
  chroma_bleed       chroma horizontal low-pass, 0 -> 24 px (composite chroma bandwidth)
  blur_horizontal    luma horizontal low-pass, gaussian sigma 0 -> 2.5 px (video bandwidth)
  warp_geometric     perspective + barrel, max corner displacement 0 -> 6 px
  interlace          field-based comb artifacts: even/odd line shear + one-field staleness
  jpeg_blocking      MJPEG re-encode, quality 95 -> 8
  resample           640x240 -> 720x480 -> back, i.e. a grabber that does not sample the
                     source raster 1:1 (bilinear both ways); sev scales how far off 1:1
  composite_ntsc     a real quadrature-modulated composite round trip: encode Y/I/Q onto a
                     subcarrier, then decode with a notch filter. Produces genuine dot
                     crawl and cross-colour. sev = how bad the decoder is -- but see the
                     function docstring: this axis is MEASURED to be non-monotone.

  composite_chain    the realistic PRESET: all of the above at a joint severity. This is
                     the curve to quote when someone asks "will it work on the real thing".

Dependencies: numpy + PIL only (no opencv, no scipy) -- both are already present on this
machine, which is why the harness does not need a virtualenv.
"""

import io
import math

import numpy as np
from PIL import Image

# ------------------------------------------------------------------ helpers


def _f(img):
    return np.asarray(img, dtype=np.float32)


def _clip(a):
    return np.clip(a, 0, 255)


def _gauss_kernel(sigma):
    if sigma <= 0:
        return None
    r = max(1, int(math.ceil(3 * sigma)))
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-(x ** 2) / (2 * sigma * sigma))
    return k / k.sum()


def _conv_h(a, k):
    """Horizontal convolution, edge-replicated. a is (H, W) or (H, W, C)."""
    if k is None:
        return a
    r = (len(k) - 1) // 2
    pad = [(0, 0), (r, r)] + ([(0, 0)] if a.ndim == 3 else [])
    p = np.pad(a, pad, mode="edge")
    out = np.zeros_like(a, dtype=np.float32)
    for i, w in enumerate(k):
        out += w * p[:, i:i + a.shape[1]]
    return out


def _conv_v(a, k):
    if k is None:
        return a
    r = (len(k) - 1) // 2
    pad = [(r, r), (0, 0)] + ([(0, 0)] if a.ndim == 3 else [])
    p = np.pad(a, pad, mode="edge")
    out = np.zeros_like(a, dtype=np.float32)
    for i, w in enumerate(k):
        out += w * p[i:i + a.shape[0]]
    return out


def _box_h(a, width):
    """Horizontal box filter of the given (float) width -- the crude bandwidth limiter a
    composite chroma decoder actually is."""
    if width <= 1:
        return a
    n = int(round(width))
    k = np.ones(n, dtype=np.float32) / n
    if n % 2 == 0:
        k = np.concatenate([k, [0.0]])
    return _conv_h(a, k)


# RGB <-> YIQ (NTSC). Kept explicit because the whole point of the composite model is
# that luma and chroma get different treatment.
_RGB2YIQ = np.array([[0.299, 0.587, 0.114],
                     [0.5959, -0.2746, -0.3213],
                     [0.2115, -0.5227, 0.3112]], dtype=np.float32)
_YIQ2RGB = np.linalg.inv(_RGB2YIQ).astype(np.float32)


def rgb2yiq(a):
    return a.reshape(-1, 3).dot(_RGB2YIQ.T).reshape(a.shape)


def yiq2rgb(a):
    return a.reshape(-1, 3).dot(_YIQ2RGB.T).reshape(a.shape)


# ------------------------------------------------------------------ axes

def noise_gaussian(img, sev, rng):
    """sigma 0 -> 40 8-bit levels."""
    sigma = 40.0 * sev
    if sigma <= 0:
        return img
    return _clip(_f(img) + rng.normal(0, sigma, _f(img).shape).astype(np.float32))


def noise_saltpepper(img, sev, rng):
    """0 -> 5 % of pixels forced to black or white (dropout / sparkle)."""
    p = 0.05 * sev
    if p <= 0:
        return img
    a = _f(img).copy()
    m = rng.random(a.shape[:2])
    a[m < p / 2] = 0.0
    a[(m >= p / 2) & (m < p)] = 255.0
    return a


def chroma_bleed(img, sev, rng=None):
    """Composite chroma bandwidth: horizontal low-pass of I and Q only, 0 -> 24 px."""
    width = 24.0 * sev
    if width < 1.0:
        return img
    y = rgb2yiq(_f(img))
    y[..., 1] = _box_h(y[..., 1], width)
    y[..., 2] = _box_h(y[..., 2], width)
    return _clip(yiq2rgb(y))


def blur_horizontal(img, sev, rng=None):
    """Luma bandwidth limit: horizontal gaussian, sigma 0 -> 2.5 px."""
    k = _gauss_kernel(2.5 * sev)
    return _clip(_conv_h(_f(img), k)) if k is not None else img


def warp_geometric(img, sev, rng=None, seed=0):
    """Perspective + barrel, MAX corner displacement 0 -> 6 px (uniform, so the stated
    number really is the worst case). Deterministic per seed, because a real chain's
    geometry is stable frame to frame -- only the noise is not.

    Caveat worth stating plainly: a composite capture does NOT warp much. Vertical
    position is locked to sync and horizontal to the line clock. This axis is the right
    model for a PHOTOGRAPH of the screen (the 60 phone photos in KN7000/photos/) and for a
    grabber with a sloppy timebase; it is the least applicable axis to a clean capture."""
    amp = 6.0 * sev
    if amp <= 0.05:
        return img
    a = _f(img)
    h, w = a.shape[:2]
    r = np.random.default_rng(1234 + seed)
    # small random projective jitter of the 4 corners + barrel term
    kx = r.uniform(-1, 1, 4) * amp / max(w, 1)
    ky = r.uniform(-1, 1, 4) * amp / max(h, 1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = xx / (w - 1.0)
    v = yy / (h - 1.0)
    # bilinear corner displacement field == keystone/trapezoid to first order
    dx = ((1 - u) * (1 - v) * kx[0] + u * (1 - v) * kx[1]
          + (1 - u) * v * kx[2] + u * v * kx[3]) * w
    dy = ((1 - u) * (1 - v) * ky[0] + u * (1 - v) * ky[1]
          + (1 - u) * v * ky[2] + u * v * ky[3]) * h
    # barrel/pincushion about the centre
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    nx = (xx - cx) / cx
    ny = (yy - cy) / cy
    rr = nx * nx + ny * ny
    kbar = (amp / max(w, h)) * 0.8 * (1 if (seed % 2 == 0) else -1)
    dx += kbar * nx * rr * cx
    dy += kbar * ny * rr * cy
    return _clip(_sample(a, xx + dx, yy + dy))


def _sample(a, X, Y):
    h, w = a.shape[:2]
    X = np.clip(X, 0, w - 1.001)
    Y = np.clip(Y, 0, h - 1.001)
    x0 = np.floor(X).astype(np.int32)
    y0 = np.floor(Y).astype(np.int32)
    fx = (X - x0)[..., None] if a.ndim == 3 else (X - x0)
    fy = (Y - y0)[..., None] if a.ndim == 3 else (Y - y0)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy)
            + a[y1, x0] * (1 - fx) * fy + a[y1, x1] * fx * fy)


def interlace(img, sev, rng=None, prev=None):
    """Field artifacts. Two mechanisms, both real:
      (a) horizontal shear between even and odd fields (line-time jitter), 0 -> 3 px
      (b) one field carries the PREVIOUS frame's content (tearing during a page flip),
          which is exactly the risk Felipe named for the held-orange-button sweep.
    `prev` supplies the stale field when given."""
    if sev <= 0:
        return img
    a = _f(img).copy()
    shear = 3.0 * sev
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = np.where((yy.astype(int) % 2) == 1, shear, -shear)
    a = _sample(a, xx + dx, yy)
    if prev is not None:
        p = _f(prev)
        if p.shape == a.shape:
            odd = (np.arange(h) % 2) == 1
            a[odd] = p[odd]
    return _clip(a)


def jpeg_blocking(img, sev, rng=None):
    """MJPEG re-encode; quality 95 -> 8."""
    q = int(round(95 - 87 * sev))
    if q >= 95:
        return img
    im = Image.fromarray(_clip(_f(img)).astype(np.uint8))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=max(1, q), subsampling=2)
    buf.seek(0)
    return _f(Image.open(buf).convert("RGB"))


def resample(img, sev, rng=None):
    """The grabber does not sample the source raster 1:1: the KN7000 emits a 640x240-ish
    active raster and a capture stick samples it on its own clock into 720x480.

    sev interpolates the intermediate raster from 640x240 (1:1) to 720x480 and back.

    NOTE this applies the resampling TWICE, which is harsher than reality -- a real chain
    resamples once and hands the extractor the 720x480 frame. The extractor here is
    scale-invariant (it resamples each cell back to a canonical 7x5 patch from whatever
    grid it registers), so feeding it the intermediate frame directly would be the
    faithful test; the round trip is used so that every axis returns a frame of the same
    size and the axes stay comparable. Read this axis as a PESSIMISTIC bound.
    """
    if sev <= 0:
        return img
    h, w = _f(img).shape[:2]
    tw = int(round(w + sev * (720 - w)))
    th = int(round(h + sev * (480 - h)))
    im = Image.fromarray(_clip(_f(img)).astype(np.uint8))
    mid = im.resize((tw, th), Image.BILINEAR)
    return _f(mid.resize((w, h), Image.BILINEAR))


def composite_ntsc(img, sev, rng=None):
    """A genuine composite round trip.

    Encode  C(x) = I(x)*sin(2*pi*fsc*x + p) + Q(x)*cos(...),  signal = Y + C, with the
    subcarrier phase inverted line to line as NTSC does.

    Decode  luma  = signal through a NOTCH at fsc, then a luma bandwidth limit
            chroma = synchronous demodulation of the signal, then a chroma low-pass

    sev is DECODER BADNESS, and it moves two physical knobs together:
      * notch depth   1 -> 0   (a shallow notch leaves the subcarrier in the luma:
                                that is dot crawl, and it lands right on top of 1-px
                                font strokes)
      * luma bandwidth 4.9 -> 1.9 MHz equivalent (gaussian sigma 0.30 -> 1.10 px at the
                                ~12.3 MHz pixel clock a 640-px active line implies)
    sev = 0 is a near-perfect separator and is close to the identity.

    ==> MEASURED CAVEAT: this axis is NOT monotone in damage. <==
    At sev 0.05 the reference extractor scores 59.1 % and at sev 0.20-0.30 it scores
    97-98 %. The reason is physical, not a coding bug: a DEEP notch at 3.58 MHz combined
    with a still-wide luma passband rings hard on the 1-px strokes of a 5x7 font, while a
    shallower notch with a narrower passband smooths the ringing away. Read the endpoints,
    not the ordering: a deep subcarrier notch is actively bad for this content.

    Note the KN7000 dump screen is mostly NEUTRAL grey, so I and Q are zero over most of
    the text; the coloured highlight cells (Aqua/Yellow/Lime/Fuchsia) are where a
    composite decoder actually has something to get wrong, and they are exactly the cells
    whose value the legend already tells us.
    """
    if sev <= 0:
        return img
    a = _f(img)
    h, w = a.shape[:2]
    yiq = rgb2yiq(a)
    Y, I, Q = yiq[..., 0], yiq[..., 1], yiq[..., 2]
    fsc = 3.579545 / 12.2727           # cycles per pixel
    x = np.arange(w, dtype=np.float32)
    ph = 2 * math.pi * fsc * x[None, :] + (np.arange(h, dtype=np.float32)[:, None] * math.pi)
    s, c = np.sin(ph), np.cos(ph)
    comp = Y + 0.5 * (I * s + Q * c)   # 0.5 = the usual chroma-to-luma amplitude ratio

    # --- band-pass at fsc, used both to notch the luma and to recover the chroma
    r = 8
    n = np.arange(-r, r + 1, dtype=np.float32)
    env = np.exp(-(n ** 2) / (2 * 2.0 ** 2))
    env /= env.sum()
    bp = 2.0 * np.cos(2 * math.pi * fsc * n) * env      # band-pass kernel centred on fsc
    depth = 1.0 - sev                                   # notch depth
    notch = -depth * bp
    notch[r] += 1.0                                     # delta - depth * bandpass
    Yr = _conv_h(comp, notch)
    Yr = _conv_h(Yr, _gauss_kernel(0.30 + 0.80 * sev))  # luma bandwidth limit

    # --- chroma: synchronous demodulation + low-pass (width grows with decoder badness)
    li = _box_h(comp * s * 4.0, 4 + 16 * sev)
    lq = _box_h(comp * c * 4.0, 4 + 16 * sev)
    return _clip(yiq2rgb(np.stack([Yr, li, lq], -1)))


# ------------------------------------------------------------------ preset chain
CHAIN_ORDER = [
    ("warp_geometric", 1.0),
    ("blur_horizontal", 1.0),
    ("composite_ntsc", 1.0),
    ("chroma_bleed", 0.6),
    ("interlace", 0.6),
    ("noise_gaussian", 0.7),
    ("noise_saltpepper", 0.3),
    ("resample", 1.0),
    ("jpeg_blocking", 0.8),
]


def composite_chain(img, sev, rng=None, **kw):
    """The realistic preset: every axis at a fraction of the joint severity, applied in
    physical order (optics/geometry -> analogue bandwidth -> modulation -> noise ->
    sampling -> compression)."""
    a = img
    for name, wgt in CHAIN_ORDER:
        a = AXES[name](a, sev * wgt, rng)
    return a


def capture_jitter(img, px, rng):
    """Sub-pixel sampling-phase jitter between successive frames of the SAME static page.

    Without this every repeated "capture" of a page is bit-identical for the deterministic
    axes (blur, warp, resample, jpeg, composite), and cross-frame voting would be measured
    against a straw man -- it can only ever help where frames differ. A real grabber's ADC
    phase and the source's line timing do drift, so successive frames of a motionless
    screen are NOT identical. Default 0.5 px, applied per repetition, on every axis.
    """
    if px <= 0:
        return img
    a = _f(img)
    h, w = a.shape[:2]
    dx = float(rng.uniform(-px, px))
    dy = float(rng.uniform(-px, px))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return _clip(_sample(a, xx + dx, yy + dy))


AXES = {
    "noise_gaussian": noise_gaussian,
    "noise_saltpepper": noise_saltpepper,
    "chroma_bleed": chroma_bleed,
    "blur_horizontal": blur_horizontal,
    "warp_geometric": warp_geometric,
    "interlace": interlace,
    "jpeg_blocking": jpeg_blocking,
    "resample": resample,
    "composite_ntsc": composite_ntsc,
    "composite_chain": composite_chain,
}

UNITS = {
    "noise_gaussian": lambda s: "sigma=%.1f levels" % (40 * s),
    "noise_saltpepper": lambda s: "%.2f%% pixels" % (100 * 0.05 * s),
    "chroma_bleed": lambda s: "chroma LPF %.1f px" % (24 * s),
    "blur_horizontal": lambda s: "luma sigma %.2f px" % (2.5 * s),
    "warp_geometric": lambda s: "max corner %.1f px" % (6 * s),
    "interlace": lambda s: "field shear %.2f px" % (3 * s),
    "jpeg_blocking": lambda s: "JPEG q=%d" % max(1, int(round(95 - 87 * s))),
    "resample": lambda s: "via %dx%d" % (round(640 + s * 80), round(240 + s * 240)),
    "composite_ntsc": lambda s: "decoder badness %.2f" % s,
    "composite_chain": lambda s: "joint severity %.2f" % s,
}


def apply_axis(img, axis, sev, rng):
    return AXES[axis](img, sev, rng)


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser(description="render damaged copies of a frame")
    ap.add_argument("frame")
    ap.add_argument("--axis", default="composite_chain", choices=sorted(AXES))
    ap.add_argument("--sev", type=float, nargs="+", default=[0.2, 0.4, 0.6, 0.8, 1.0])
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    src = _f(Image.open(a.frame).convert("RGB"))
    os.makedirs(a.outdir, exist_ok=True)
    for s in a.sev:
        rng = np.random.default_rng(a.seed)
        d = apply_axis(src, a.axis, s, rng)
        p = os.path.join(a.outdir, "%s_%03d.png" % (a.axis, int(round(s * 100))))
        Image.fromarray(_clip(_f(d)).astype(np.uint8)).save(p)
        print("%-18s sev %.2f  (%s)  -> %s" % (a.axis, s, UNITS[a.axis](s), p))
