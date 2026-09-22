#!/usr/bin/env python3
"""Sample the real PANEL MEMORY colours out of a photograph of the panel.

Question it answers: "what colours should the traced PANEL MEMORY shapes be painted?"
Felipe supplied the photo (2026-09-22) and asked for the button colours to be picked from it.

    python3 tools/pm_sample_photo.py PHOTO.jpg [--centre CX CY] [--rset R]

Registration: the SET cap is the darkest compact blob in the middle of the frame, so its
centroid gives the rosette centre and its radius gives the photo's scale against
pm_shapes.json's radii (r_set = 23.7485 layout units). Every region below is then addressed in
LAYOUT units and converted, which is what makes the samples comparable to the .lay.

Angles follow the layout: SVG convention (y down, 0 deg = +x, increasing clockwise), wedge k
spanning 45k+2.72 .. 45k+42.28 degrees, so the eight grooves sit at every 45 deg.

Specular highlights are excluded by trimming the top 4% of luminance per region; the median is
the face colour and the 15th/85th percentiles drive a gradient. The photo carries its own white
balance, so these are the panel's colours AS PHOTOGRAPHED -- the point is that they are measured
from the instrument rather than guessed.
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
R_SET_LAYOUT = None          # taken from pm_shapes.json


def find_set(lum, box=(540, 420, 880, 720), pct=12):
    """Darkest compact blob in the middle: the SET cap. Returns (cx, cy, r)."""
    from collections import deque
    x0, y0, x1, y1 = box
    win = np.zeros_like(lum, bool); win[y0:y1, x0:x1] = True
    m = win & (lum < np.percentile(lum[win], pct))
    seen = np.zeros_like(m); best = (0, None)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if m[y, x] and not seen[y, x]:
                q = deque([(y, x)]); seen[y, x] = True; pts = []
                while q:
                    cy, cx = q.popleft(); pts.append((cy, cx))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if y0 <= ny < y1 and x0 <= nx < x1 and m[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True; q.append((ny, nx))
                if len(pts) > best[0]:
                    best = (len(pts), pts)
    pts = best[1]
    ys = np.array([p[0] for p in pts]); xs = np.array([p[1] for p in pts])
    w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    # NB the blob is the dark RING around the SET cap, not the cap itself -- it fills only ~13%
    # of its bbox. Its bbox is still the cap's outer edge, which is the circle pm_shapes.json
    # calls pm_set, so the scale it gives is right; the check below proves that independently.
    assert 0.85 <= w / h <= 1.18, ("the darkest blob is %dx%d, not round -- this is not the SET "
                                   "cap; pass --centre CX CY --rset R" % (w, h))
    return xs.mean(), ys.mean(), (w + h) / 4.0


def check_registration(a, cx, cy, s, rad):
    """Positive control on the centre/scale: at the derived scale the ROSETTE RIM must land on
    a dark ring -- markedly darker than the wedge faces inside it and the panel outside it. If
    the registration were wrong this would not hold, and every colour below would be sampled
    from the wrong place."""
    H, W, _ = a.shape
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot(xx - cx, yy - cy) / s
    lum = a.mean(axis=2)
    def band(r0, r1):
        sel = (r >= r0) & (r <= r1)
        return lum[sel].mean(), int(sel.sum())
    rim, nrim = band(rad['rim'] - 1.2, rad['rim'] + 1.2)
    face, nf = band(80, 90)
    panel, npn = band(rad['rim'] + 8, rad['rim'] + 16)
    print("registration control: rim r%.1f lum %.1f (n=%d) vs wedge face %.1f (n=%d) "
          "vs panel %.1f (n=%d)" % (rad['rim'], rim, nrim, face, nf, panel, npn))
    # Thresholds from the measurement: on Felipe's photo the rim is 36% darker than the faces
    # and 12% darker than the panel (which is itself dark here). A centre 150px off the mark is
    # rejected by the face test, which is the sensitive one.
    assert rim < 0.80 * face and rim < 0.95 * panel, \
        ("the rim is not a dark ring at this centre/scale (%.1f vs face %.1f, panel %.1f) -- "
         "the registration is wrong" % (rim, face, panel))
    print("  OK: the rim is %.0f%% darker than the faces and %.0f%% darker than the panel"
          % (100 * (1 - rim / face), 100 * (1 - rim / panel)))


def hexof(c):
    return '#%02x%02x%02x' % tuple(int(round(v)) for v in c)


def stats(px, name, trim=0.04):
    if len(px) < 30:
        print("  %-22s only %d px -- skipped" % (name, len(px))); return None
    lum = px.mean(axis=1)
    keep = lum <= np.percentile(lum, 100 * (1 - trim))       # drop specular highlights
    px = px[keep]; lum = lum[keep]
    o = np.argsort(lum)
    p15, p50, p85 = [px[o[int(len(o) * q)]] for q in (0.15, 0.50, 0.85)]
    med = np.median(px, axis=0)
    print("  %-22s n=%-6d median %s   dark %s  light %s"
          % (name, len(px), hexof(med), hexof(p15), hexof(p85)))
    return dict(median=hexof(med), dark=hexof(p15), light=hexof(p85))


def main():
    photo = sys.argv[1]
    js = json.load(open(os.path.join(HERE, 'pm_shapes.json')))
    rad = js['radii']; span = js['wedge']['span']
    a = np.asarray(Image.open(photo).convert('RGB')).astype(float)
    H, W, _ = a.shape
    lum = a.mean(axis=2)
    if '--centre' in sys.argv:
        i = sys.argv.index('--centre'); cx, cy = float(sys.argv[i + 1]), float(sys.argv[i + 2])
        rset = float(sys.argv[sys.argv.index('--rset') + 1])
    else:
        cx, cy, rset = find_set(lum)
    s = rset / rad['set']
    print("photo %dx%d  centre (%.1f,%.1f)  SET r=%.1f px  => %.4f px per layout unit"
          % (W, H, cx, cy, rset, s))
    print("layout radii: %s" % rad)
    check_registration(a, cx, cy, s, rad)

    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot(xx - cx, yy - cy) / s                       # in LAYOUT units
    th = (np.degrees(np.arctan2(yy - cy, xx - cx))) % 360.0
    rel = th % 45.0                                          # position within a 45 deg slot
    lo, hi = (45.0 - span) / 2.0, 45.0 - (45.0 - span) / 2.0  # 2.72 .. 42.28

    def band(r0, r1, mode='wedge', pad=3.0):
        sel = (r >= r0) & (r <= r1)
        if mode == 'wedge':
            sel &= (rel >= lo + pad) & (rel <= hi - pad)
        elif mode == 'groove':
            sel &= (rel < lo - 0.4) | (rel > hi + 0.4)
        return a[sel]

    out = {}
    print("\nWEDGE FACES (r %.1f..%.1f, radial thirds -- the face is a toroidal bevel)"
          % (rad['btn_in'], rad['btn_out']))
    w0, w1 = rad['btn_in'], rad['btn_out']
    for tag, r0, r1 in (('inner third', w0 + 2, w0 + (w1 - w0) / 3),
                        ('middle third', w0 + (w1 - w0) / 3, w0 + 2 * (w1 - w0) / 3),
                        ('outer third', w0 + 2 * (w1 - w0) / 3, w1 - 2)):
        out['wedge_' + tag.split()[0]] = stats(band(r0, r1), tag)
    out['wedge'] = stats(band(w0 + 2, w1 - 2), 'whole face')

    print("\nGROOVES between the wedges (the %.2f deg gaps)" % (45.0 - span))
    out['groove'] = stats(band(w0 + 6, w1 - 6, 'groove'), 'groove', trim=0.10)

    print("\nCENTRE")
    out['collar'] = stats(band(rad['led_in'] + 1, rad['led_out'] - 1, 'all'), 'collar r 46..55')
    out['hub'] = stats(band(rad['set'] + 3, rad['hub'] - 1, 'all'), 'hub r 27..46')
    out['set'] = stats(band(0, rad['set'] - 4, 'all'), 'SET cap')

    # The two bank wings are the same material as the wedges, so they are sampled too: a
    # rectangle inside each wing's thickest part, given in layout units relative to the centre
    # (the wings' traced paths carry arcs, which PIL cannot rasterise for a mask).
    print("\nBANK WINGS")
    wing_px = []
    dbg = np.zeros((H, W), bool)
    for tag, dx0, dx1, dy0, dy1 in (('left wing', -64, -19, -130, -110),
                                    ('right wing', 19, 64, -130, -110)):
        sel = ((xx - cx) / s >= dx0) & ((xx - cx) / s <= dx1) & \
              ((yy - cy) / s >= dy0) & ((yy - cy) / s <= dy1)
        dbg |= sel
        out[tag.replace(' ', '_')] = stats(a[sel], tag)
        wing_px.append(a[sel])
    out['wing'] = stats(np.concatenate(wing_px), 'both wings')
    if '--debug' in sys.argv:
        im = np.asarray(Image.open(photo).convert('RGB')).copy()
        im[dbg] = [255, 0, 255]
        edge = (r > rad['btn_in']) & (r < rad['btn_in'] + 0.4)
        im[edge] = [0, 255, 0]
        Image.fromarray(im).save('/tmp/pm_sample_debug.png')
        print("  (debug overlay -> /tmp/pm_sample_debug.png)")

    print("\nSURROUNDINGS")
    out['rim'] = stats(band(rad['btn_out'] + 0.5, rad['rim'] + 2, 'all'), 'rim r 96..98', trim=0.10)
    out['panel'] = stats(band(rad['rim'] + 8, rad['rim'] + 20, 'all'), 'panel just outside')

    js2 = os.path.join(HERE, 'pm_colours.json')
    with open(js2, 'w') as fh:
        json.dump(dict(source=os.path.basename(photo), centre=[cx, cy], px_per_unit=s,
                       regions={k: v for k, v in out.items() if v}), fh, indent=1, sort_keys=True)
        fh.write('\n')
    print("\nwrote %s" % js2)


if __name__ == '__main__':
    main()
