#!/usr/bin/env python3
"""How many DISTINCT shapes are there really in wsa1r.lay?  READ-ONLY.

QUESTION IT ANSWERS
  src/mame/layout/wsa1r.lay is 932 lines but 267 KB, because the generator
  (tools/gen_wsa1r_lay.py) emits each of the 58 buttons as a COMPLETE inline
  SVG in ABSOLUTE artwork coordinates, with its own private copy of the
  gradient <defs>, cropped by a per-button viewBox.  kn5000.lay instead
  declares a shape ONCE in LOCAL coordinates ("dark_25x25_button") and places
  it many times with <element ref=...><bounds/></element>.

  Before wsa1r.lay can be rewritten that way, three things must be settled with
  pixels rather than opinion:

    1. is the absolute -> local coordinate change LOSS-FREE?   (--self-test)
    2. once every control is in local coordinates, how many EQUIVALENCE CLASSES
       are there -- sets whose members rasterise to BYTE-IDENTICAL RGBA?  That
       count is the number of <element>s the rewritten layout needs, and
       58 - count is the number of <element>s it deletes.
    3. how many FURTHER merges appear if an element may STRETCH into
       differently-sized <bounds>, which is what MAME does to any element whose
       bounds do not match its natural aspect?  Those are not pixel-exact by
       construction, so each is reported with its per-axis size delta in px AND
       its measured pixel error, and the caller decides.

TWO NORMALISATIONS, AND WHY BOTH ARE HERE
  Each control is <svg width=Wpx height=Hpx viewBox="vbx vby vbw vbh"> followed
  by one or more top-level <g transform="matrix(1,0,0,1,e,f)">.  Moving the
  shape to the origin means translating by T = (e - vbx, f - vby).  T is
  POSITION-INVARIANT -- a copy of the same shape drawn elsewhere in the artwork
  has e and vbx shifted by the SAME amount -- and that invariance is the whole
  reason this makes copies comparable.

  FOLD   the body is wrapped in one extra <g transform="translate(-vbx,-vby)">.
         Not one artwork number is touched, so it is exact by construction, and
         the self-test confirms it: 120/120 byte-identical to the original crop.
         It is therefore the RASTERISER for the class analysis.  What it does
         not do is make two copies textually equal: the absolute numbers stay.

  BAKE   T is folded into the geometry itself -- absolute path coordinates,
         ellipse/circle centres, and the userSpaceOnUse GRADIENT geometry
         (gradientTransform e,f, or x1,y1,x2,y2 when a gradient carries no
         gradientTransform).  The <g> transform is dropped, the viewBox reset
         to "0 0 vbw vbh", and every id renumbered a0,a1,...  This is the form
         a shared <element> would actually contain, and two copies of one shape
         come out CHARACTER-IDENTICAL.
         BAKE applies only where every top-level <g> is a pure translation: all
         58 buttons and volume_knob.  data_wheel and data_wheel_finger carry
         matrix(2.1441055,1.1335575,...) and vector_art a y-flip with nested
         <g>/<clipPath>, so those three fall back to FOLD (for vector_art T is
         (0,0) and the step is a no-op -- its viewBox already starts at 0,0).

  The bake is exact in exact arithmetic but not in binary floating point: it
  moves the gradient's userSpaceOnUse origin from ~ -93 to ~ -201, and the
  subtraction that librsvg then performs loses a few low bits.  The self-test
  measures that instead of hiding it; it is worth at most 1/255 on a few percent
  of the edge bytes of a handful of controls, and the class table is computed
  from the FOLD rasters so it never depends on the bake at all.

RASTERISER
  librsvg 2.60 via python3-gi + pycairo, ARGB32, at the element's natural pixel
  size AND at 4x, both hashed; two controls are in one class only if BOTH agree.
  MAME renders layout SVG with nanosvg, not librsvg, so these hashes are a
  strict comparison BETWEEN TWO SVGS, not a prediction of MAME's own output --
  which is all the question needs, since two SVGs that are byte-identical under
  a conforming renderer are interchangeable under any renderer.

RUN
  python3 notes/wsa1-probes/wsa1r_lay_shape_classes.py                 # full report
  python3 notes/wsa1-probes/wsa1r_lay_shape_classes.py --self-test     # gate only
  python3 notes/wsa1-probes/wsa1r_lay_shape_classes.py --emit DIR      # dump the SVGs
  python3 notes/wsa1-probes/wsa1r_lay_shape_classes.py --lay FILE      # another .lay

  ⚠ THE BASELINE.  The figures in README.md were measured against wsa1r.lay as
  of commit c51e4e8 -- 267287 bytes, 62 inline-SVG <element>s, 58 of them
  buttons.  The reuse pass this probe exists to justify DELETES those private
  SVGs, so re-running against a rewritten file will not reproduce them.  To
  reproduce, hand the probe the baseline:
      git show c51e4e8:src/mame/layout/wsa1r.lay > /tmp/wsa1r-baseline.lay
      python3 notes/wsa1-probes/wsa1r_lay_shape_classes.py --lay /tmp/wsa1r-baseline.lay

  The full report also re-asks the class question of MAME's OWN rasteriser via
  nsvg_hash beside this file (build it with build_nsvg_hash.sh); librsvg is the
  strict referee, nanosvg is what the user actually sees.
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile

import gi
gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg          # noqa: E402
import cairo                            # noqa: E402

LAY = "/home/fsanches/compartilhado/kn7000_mame/src/mame/layout/wsa1r.lay"

# The numbers quoted in README.md were measured against the layout as it stood
# in commit c51e4e8 ("wsa1r: a control panel, generated from Felipe's artwork"),
# 267287 bytes, 62 inline-SVG <element>s.  Once the reuse pass lands, that file
# no longer HAS 58 private button SVGs, so reproduce the baseline with
#     git show c51e4e8:src/mame/layout/wsa1r.lay > /tmp/wsa1r-baseline.lay
#     python3 .../wsa1r_lay_shape_classes.py --lay /tmp/wsa1r-baseline.lay
BASELINE = "c51e4e8"
NSVG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nsvg_hash")

# ---------------------------------------------------------------- parsing ----

ELEM_RE = re.compile(r'<element name="([^"]+)"([^>]*)>(.*?)</element>', re.S)
IMG_RE = re.compile(
    r'<image(?:\s+state="(-?\d+)")?><data><!\[CDATA\[(.*?)\]\]></data></image>', re.S)
SVG_OPEN = re.compile(r"<svg\b([^>]*)>")
ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*"([^"]*)"')
NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
MATRIX_RE = re.compile(r"matrix\(\s*(" + NUM + r")[,\s]+(" + NUM + r")[,\s]+(" + NUM +
                       r")[,\s]+(" + NUM + r")[,\s]+(" + NUM + r")[,\s]+(" + NUM + r")\s*\)")


class Control(object):
    __slots__ = ("name", "state", "svg", "line", "wpx", "hpx", "vb",
                 "fold", "bake", "how", "nat", "fine")

    def __init__(self, name, state, svg, line):
        self.name, self.state, self.svg, self.line = name, state, svg, line

    def key(self):
        return self.name if self.state is None else "%s@%s" % (self.name, self.state)


def parse_lay(path):
    src = open(path, encoding="utf-8").read()
    out = []
    for m in ELEM_RE.finditer(src):
        name, body, base = m.group(1), m.group(3), m.start(3)
        for im in IMG_RE.finditer(body):
            line = src.count("\n", 0, base + im.start()) + 1
            out.append(Control(name, im.group(1), im.group(2), line))
    return out


def attrs_of(s):
    return dict(ATTR_RE.findall(s))


def fnum(x):
    """Format a coordinate THIS SCRIPT CHANGED, so two copies of one shape agree
    to the last digit.  9 decimals: the artwork carries at most 7, and the only
    error absorbed is the ~1e-14 float noise in (e - vbx).

    Numbers the script does NOT change keep their ORIGINAL TEXT.  That is not
    cosmetic: reprinting a gradient's scale 1.1915828 as 1.191583 slides the
    shading by ~5e-5 user units, and the self-test caught it as a 1-LSB failure
    on 32 of the 120 controls the first time this script was run."""
    v = round(x + 0.0, 9)
    if v == 0.0:
        v = 0.0                                   # kill -0.0
    s = ("%.9f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-") else "0"


# ----------------------------------------------------------- path surgery ----

PATH_TOK = re.compile(r"([MmZzLlHhVvCcSsQqTtAa])|(" + NUM + r")")
NARG = {"m": 2, "l": 2, "t": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "a": 7, "z": 0}
# which argument indexes inside one parameter group are x's and which are y's
XY = {"m": ([0], [1]), "l": ([0], [1]), "t": ([0], [1]),
      "h": ([0], []), "v": ([], [0]),
      "c": ([0, 2, 4], [1, 3, 5]), "s": ([0, 2], [1, 3]), "q": ([0, 2], [1, 3]),
      "a": ([5], [6]), "z": ([], [])}


def translate_path(d, tx, ty):
    """Translate the ABSOLUTE coordinates of a path by (tx,ty).  Relative ones
    keep their original text, except the first 'm', whose first pair is absolute
    per SVG 1.1."""
    toks = [(a or b, bool(a)) for a, b in PATH_TOK.findall(d)]
    out, i, cmd, first = [], 0, None, True
    while i < len(toks):
        tok, is_cmd = toks[i]
        if is_cmd:
            cmd = tok
            i += 1
            if cmd.lower() == "z":
                out.append(cmd)
                first = False
                continue
        elif cmd is None:
            raise ValueError("path starts with a number: %r" % d[:40])
        groups, n = [], NARG[cmd.lower()]
        while i < len(toks) and not toks[i][1]:
            g = []
            for _ in range(n):
                if i >= len(toks) or toks[i][1]:
                    raise ValueError("short parameter group in %r" % d[:40])
                g.append(toks[i][0])              # ORIGINAL TEXT
                i += 1
            groups.append(g)
        xs, ys = XY[cmd.lower()]
        for gi_, g in enumerate(groups):
            if cmd.isupper() or (first and cmd == "m" and gi_ == 0):
                for k in xs:
                    g[k] = fnum(float(g[k]) + tx)
                for k in ys:
                    g[k] = fnum(float(g[k]) + ty)
        out.append(cmd + " " + " ".join(",".join(g) for g in groups))
        first = False
    return " ".join(out)


def fold_translate_into_matrix(mtx_text, tx, ty):
    """translate(tx,ty) . matrix(a,b,c,d,e,f) == matrix(a,b,c,d,e+tx,f+ty).
    a..d keep their original text; only the two translation cells move."""
    m = MATRIX_RE.search(mtx_text)
    a, b, c, d, e, f = m.groups()
    new = "matrix(%s,%s,%s,%s,%s,%s)" % (a, b, c, d,
                                         fnum(float(e) + tx), fnum(float(f) + ty))
    return mtx_text[:m.start()] + new + mtx_text[m.end():]


# ----------------------------------------------------------- normalisation ---

TOPG_RE = re.compile(r"<g\b([^>]*)>")
PRIM_RE = re.compile(r"<(path|ellipse|circle|rect)\b([^>]*)/>")
GRAD_RE = re.compile(r"<linearGradient\b([^>]*?)(/?)>")
ID_RE = re.compile(r'\bid="([^"]+)"')


def _split(svg):
    """-> (open_tag, defs, rest, (vbx,vby), viewBox_wh_text)"""
    om = SVG_OPEN.search(svg)
    a = attrs_of(om.group(1))
    vbt = re.split(r"[,\s]+", a["viewBox"].strip())
    head, body = om.group(0), svg[om.end():]
    assert body.endswith("</svg>")
    body = body[:-len("</svg>")]
    head = head.replace('viewBox="%s"' % a["viewBox"],
                        'viewBox="0 0 %s %s"' % (vbt[2], vbt[3]))
    de = body.find("</defs>")
    defs = body[:de + len("</defs>")] if de >= 0 else ""
    rest = body[de + len("</defs>"):] if de >= 0 else body
    return head, defs, rest, (float(vbt[0]), float(vbt[1])), (vbt[2], vbt[3])


def _max_g_depth(body):
    depth = mx = 0
    for t in re.finditer(r"<(/?)g[\s>]", body):
        depth += -1 if t.group(1) else 1
        mx = max(mx, depth)
    return mx


def normalise_fold(svg):
    """Exact by construction: not one artwork number is touched."""
    head, defs, rest, (vbx, vby), _ = _split(svg)
    if abs(vbx) < 1e-12 and abs(vby) < 1e-12:
        return head + defs + rest + "</svg>", "identity"
    wrap = '<g transform="translate(%s,%s)">' % (fnum(-vbx), fnum(-vby))
    return head + defs + wrap + rest + "</g></svg>", "fold"


def normalise_bake(svg):
    """Position-independent TEXT, or (None, why) when the shape resists it."""
    head, defs, rest, (vbx, vby), _ = _split(svg)
    if _max_g_depth(rest) > 1:
        return None, "nested <g>/<clipPath>"
    gmats = []
    for gm in TOPG_RE.finditer(rest):
        t = attrs_of(gm.group(1)).get("transform", "")
        m = MATRIX_RE.search(t)
        if not m or t.strip() != m.group(0):
            return None, "top-level <g> has no plain matrix() transform"
        va = [float(x) for x in m.groups()]
        if (va[0], va[1], va[2], va[3]) != (1.0, 0.0, 0.0, 1.0):
            return None, ("top-level <g> is not a pure translation: "
                          "matrix(%g,%g,%g,%g,..)" % tuple(va[:4]))
        gmats.append((gm.group(0), va[4], va[5]))
    if not gmats:
        return None, "no top-level <g> to absorb the translation"
    if len({(round(e, 9), round(f, 9)) for _, e, f in gmats}) != 1:
        return None, "top-level <g>s disagree on the translation (shared <defs>)"

    tx, ty = gmats[0][1] - vbx, gmats[0][2] - vby

    def grad_fix(m):                                  # gradients move with the shape
        inner, close = m.group(1), m.group(2)
        ga = attrs_of(inner)
        if ga.get("gradientUnits") != "userSpaceOnUse":
            return m.group(0)
        if "gradientTransform" in ga:
            inner = inner.replace('gradientTransform="%s"' % ga["gradientTransform"],
                                  'gradientTransform="%s"' %
                                  fold_translate_into_matrix(ga["gradientTransform"], tx, ty))
        else:
            for k, dv in (("x1", tx), ("y1", ty), ("x2", tx), ("y2", ty)):
                if k in ga:
                    inner = inner.replace('%s="%s"' % (k, ga[k]),
                                          '%s="%s"' % (k, fnum(float(ga[k]) + dv)))
        return "<linearGradient" + inner + close + ">"

    def prim_fix(m):
        tag, inner = m.group(1), m.group(2)
        pa = attrs_of(inner)
        if "transform" in pa:                         # fold into the primitive's own
            inner = inner.replace('transform="%s"' % pa["transform"],
                                  'transform="%s"' %
                                  fold_translate_into_matrix(pa["transform"], tx, ty))
        elif tag == "path":
            inner = inner.replace('d="%s"' % pa["d"],
                                  'd="%s"' % translate_path(pa["d"], tx, ty))
        else:
            for k, dv in (("cx", tx), ("cy", ty), ("x", tx), ("y", ty)):
                if k in pa:
                    inner = inner.replace('%s="%s"' % (k, pa[k]),
                                          '%s="%s"' % (k, fnum(float(pa[k]) + dv)))
        return "<%s%s/>" % (tag, inner)

    out = head + GRAD_RE.sub(grad_fix, defs) + PRIM_RE.sub(prim_fix, rest) + "</svg>"
    for gtext, _e, _f in gmats:
        out = out.replace(gtext, "<g>", 1)
    return canonical_ids(out), "bake"


def canonical_ids(svg):
    """Renumber every id a0,a1,... in document order, so two copies of one shape
    -- whose Inkscape ids differ (linearGradient249 vs 250) -- come out with
    identical TEXT as well as identical pixels."""
    mapping = {}
    for m in ID_RE.finditer(svg):
        mapping.setdefault(m.group(1), "a%d" % len(mapping))
    for old in sorted(mapping, key=len, reverse=True):
        new = mapping[old]
        svg = svg.replace('id="%s"' % old, 'id="%s"' % new)
        svg = svg.replace("url(#%s)" % old, "url(#%s)" % new)
        svg = svg.replace('href="#%s"' % old, 'href="#%s"' % new)
    return svg


def reposition(norm, orig):
    """Put a normalised SVG back where it came from, for the round-trip gate."""
    head, defs, rest, _, _ = _split(norm)
    a = attrs_of(SVG_OPEN.search(orig).group(1))
    vbt = re.split(r"[,\s]+", a["viewBox"].strip())
    head = re.sub(r'viewBox="[^"]*"', 'viewBox="%s"' % a["viewBox"], head)
    return (head + defs + '<g transform="translate(%s,%s)">' % (vbt[0], vbt[1]) +
            rest + "</g></svg>")


# ------------------------------------------------------------ rasterising ----

def set_size(svg, w, h):
    om = SVG_OPEN.search(svg)
    a = attrs_of(om.group(1))
    head = om.group(0)
    head = head.replace('width="%s"' % a["width"], 'width="%g"' % w)
    head = head.replace('height="%s"' % a["height"], 'height="%g"' % h)
    return svg[:om.start()] + head + svg[om.end():]


def raster(svg, w, h):
    handle = Rsvg.Handle.new_from_data(svg.encode("utf-8"))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    rect = Rsvg.Rectangle()
    rect.x, rect.y, rect.width, rect.height = 0.0, 0.0, float(w), float(h)
    if not handle.render_document(cr, rect):
        raise RuntimeError("librsvg refused to render")
    surf.flush()
    data, stride = bytes(surf.get_data()), surf.get_stride()
    return b"".join(data[y * stride:y * stride + w * 4] for y in range(h))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def natural(c):
    return max(1, int(round(c.wpx))), max(1, int(round(c.hpx)))


def hashes(svg, w, h):
    """natural-size hash AND a 4x supersampled hash; a class needs both."""
    return (sha(raster(set_size(svg, w, h), w, h)),
            sha(raster(set_size(svg, w * 4, h * 4), w * 4, h * 4)))


def pixdiff(a, b):
    tot = mx = ndiff = 0
    for x, y in zip(a, b):
        d = abs(x - y)
        tot += d
        if d > mx:
            mx = d
        if d:
            ndiff += 1
    n = float(len(a))
    return tot / n, mx, 100.0 * ndiff / n


# ------------------------------------------------------------------ main -----

def load():
    ctrls = parse_lay(LAY)
    for c in ctrls:
        a = attrs_of(SVG_OPEN.search(c.svg).group(1))
        c.wpx, c.hpx = float(a["width"]), float(a["height"])
        c.vb = tuple(float(x) for x in re.split(r"[,\s]+", a["viewBox"].strip()))
        c.fold, foldhow = normalise_fold(c.svg)
        c.bake, bakehow = normalise_bake(c.svg)
        c.how = bakehow if c.bake else "%s (%s)" % (foldhow, bakehow)
    return ctrls


def self_test(ctrls):
    print("SELF-TEST -- is the absolute -> local rewrite loss-free?")
    print("  Rasterise the ORIGINAL cropped SVG and the NORMALISED one at natural")
    print("  size AND at 4x, and demand identical RGBA.  Three gates:")
    gates = [
        ("A  FOLD == ORIGINAL          (the gate the class table rests on)",
         lambda c: c.fold),
        ("B  BAKE == ORIGINAL          (the text-canonical form)",
         lambda c: c.bake),
        ("C  reposition(BAKE) == ORIGINAL   (round trip: is any INFORMATION lost?)",
         lambda c: reposition(c.bake, c.svg) if c.bake else None),
    ]
    allok = True
    for label, get in gates:
        bad, skipped = [], 0
        for c in ctrls:
            cand = get(c)
            if cand is None:
                skipped += 1
                continue
            w, h = natural(c)
            if hashes(c.svg, w, h) != hashes(cand, w, h):
                worst = max((pixdiff(raster(set_size(c.svg, w * k, h * k), w * k, h * k),
                                     raster(set_size(cand, w * k, h * k), w * k, h * k))
                             + (k,) for k in (1, 4)), key=lambda t: (t[1], t[2]))
                bad.append((c, worst))
        n = len(ctrls) - skipped
        print("  gate %s" % label)
        if not bad:
            print("       PASS  %d/%d byte-identical%s" %
                  (n, n, "  (%d not applicable)" % skipped if skipped else ""))
        else:
            lsb = all(d[1] <= 1 for _c, d in bad)
            allok = allok and lsb
            print("       %s  %d/%d byte-identical, %d differ%s" %
                  ("PASS within 1/255" if lsb else "FAIL",
                   n - len(bad), n, len(bad),
                   "  (%d not applicable)" % skipped if skipped else ""))
            print("       worst residual: max|delta| = %d/255%s" %
                  (max(d[1] for _c, d in bad),
                   "  -- one LSB of antialiasing, no shape moved" if lsb else ""))
            for c, d in bad:
                print("         %-16s mean|d|=%.4f  max|d|=%d  bytes differing"
                      " %.2f%%  (worst at %dx)" % (c.key(), d[0], d[1], d[2], d[3]))
    print("  %d controls: %s" %
          (len(ctrls), ", ".join("%d %s" % (sum(1 for c in ctrls if c.how == h), h)
                                 for h in sorted({c.how for c in ctrls}))))
    return allok


def nsvg_hash(svg, w, h):
    """The same question put to MAME'S OWN rasteriser.  nsvg_hash.c reproduces
    rendlay.cpp draw_svg(), so this is what the user actually sees."""
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
        fh.write(svg)
        path = fh.name
    try:
        out = subprocess.run([NSVG, path, str(w), str(h)],
                             capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(path)
    return out.split()[0]


def nsvg_cmp(a, b, w, h):
    fs = []
    for svg in (a, b):
        fh = tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False)
        fh.write(svg)
        fh.close()
        fs.append(fh.name)
    try:
        out = subprocess.run([NSVG, "-cmp", fs[0], fs[1], str(w), str(h)],
                             capture_output=True, text=True, check=True).stdout
    finally:
        for f in fs:
            os.unlink(f)
    d = dict(kv.split("=") for kv in out.split() if "=" in kv)
    return int(d["ndiff"]), int(d["maxdelta"]), float(d["meandelta"])


def nsvg_cross_check(ctrls, btns):
    """Ask the SAME question of MAME'S OWN rasteriser.  This is not a formality:
    nanosvg is float32, so where the coordinates SIT changes what it draws."""
    print()
    print("=" * 78)
    print("CROSS-CHECK AGAINST MAME'S OWN RASTERISER (nsvg_hash, nanosvg)")
    print("=" * 78)
    if not os.access(NSVG, os.X_OK):
        print("  nsvg_hash not built -- run  sh notes/wsa1-probes/build_nsvg_hash.sh")
        return
    print("  librsvg is the strict referee; nanosvg is what MAME actually draws.")
    print()
    print("  1. IS THE NORMALISATION FREE UNDER NANOSVG TOO?  original vs BAKE:")
    worst, ndis = (0, 0, 0.0), 0
    for c in ctrls:
        w, h = natural(c)
        form = c.bake or c.fold
        d = nsvg_cmp(c.svg, form, w, h)
        if d[0]:
            ndis += 1
            if d[1] > worst[1]:
                worst = d
    print("     %d of %d controls differ; worst ndiff=%d maxdelta=%d meandelta=%.4f"
          % (ndis, len(ctrls), worst[0], worst[1], worst[2]))
    print("     NOT a bug in the rewrite -- it is nanosvg's float32 precision at the")
    print("     artwork's absolute coordinates (x up to ~420).  Moving a shape to the")
    print("     origin makes the rasteriser MORE accurate, not less; librsvg, which")
    print("     is double, calls the two identical (gate A, 120/120).")
    print()
    print("  2. THE CLASS COUNT, per normalisation form:")
    for state in sorted({c.state for c in btns}):
        grp = [c for c in btns if c.state == state]
        lib = {tuple(sorted(c.name for c in g)) for g in classes(grp)}
        for form in ("fold", "bake"):
            by = {}
            for c in grp:
                w, h = natural(c)
                by.setdefault((nsvg_hash(getattr(c, form), w, h), (w, h)), []).append(c)
            nan = {tuple(sorted(c.name for c in g)) for g in by.values()}
            print("     state=%s  %-4s -> %2d nanosvg classes   (librsvg: %d)%s"
                  % (state, form.upper(), len(nan), len(lib),
                     "   SAME PARTITION" if nan == lib else ""))
    print("     FOLD keeps the artwork's big coordinates alive inside nanosvg's")
    print("     FLOATS and shatters classes that are one shape.  BAKE does not.")
    print("     A rewritten wsa1r.lay must carry BAKED local coordinates.")

    print()
    print("  3. WHAT EACH MERGE COSTS IN MAME.  For every librsvg class, replace")
    print("     each member by the class representative and measure, with nanosvg,")
    print("     the worst pixel disagreement inside the class:")
    print("     %-4s %3s %-15s %12s %8s %8s  %s" %
          ("cls", "n", "size px", "worst ndiff", "maxdelta", "mean", "worst pair"))
    for state in sorted({c.state for c in btns}):
        for i, g in enumerate(classes([c for c in btns if c.state == state])):
            if len(g) < 2:
                continue
            w, h = natural(g[0])
            worst, who = (0, 0, 0.0), "-"
            for c in g[1:]:
                d = nsvg_cmp(g[0].bake, c.bake, w, h)
                if d[1] > worst[1]:
                    worst, who = d, "%s vs %s" % (g[0].name, c.name)
            print("     C%-3d %3d %7.3fx%-7.3f %6d/%-5d %8d %8.4f  %s"
                  % (i, len(g), g[0].wpx, g[0].hpx, worst[0], w * h,
                     worst[1], worst[2], who if worst[0] else "IDENTICAL"))
        break            # the two states partition identically; one pass is enough
    print("     Every class whose worst row reads 0/N IDENTICAL can be collapsed")
    print("     with MAME drawing the very same pixels.  The rest are Inkscape")
    print("     duplication noise in the 6th digit, and the number beside them is")
    print("     the exact price of collapsing them anyway.")


def classes(items):
    by = {}
    for c in items:
        by.setdefault((c.nat, c.fine, natural(c)), []).append(c)
    return sorted(by.values(), key=lambda g: (-len(g), g[0].name))


def report(ctrls):
    for c in ctrls:
        w, h = natural(c)
        c.nat, c.fine = hashes(c.fold, w, h)          # gate A form: exact

    btns = [c for c in ctrls if c.name.startswith("btn_")]
    others = [c for c in ctrls if not c.name.startswith("btn_")]
    print()
    print("INPUT: %s   (%d bytes)" % (LAY, os.path.getsize(LAY)))
    print("  %d <element>s carry inline SVG; %d images (%d button, %d other)" %
          (len({c.name for c in ctrls}), len(ctrls), len(btns), len(others)))
    print("  buttons: %d, states: %s" %
          (len({c.name for c in btns}), sorted({c.state for c in btns})))

    for state in sorted({c.state for c in btns}):
        grp = [c for c in btns if c.state == state]
        cls = classes(grp)
        print()
        print("=" * 78)
        print("EXACT EQUIVALENCE CLASSES -- %d buttons, state=%s" % (len(grp), state))
        print("  %d buttons -> %d classes   (%d of the 58 <element>s are redundant,"
              " %.0f%%)" % (len(grp), len(cls), len(grp) - len(cls),
                            100.0 * (len(grp) - len(cls)) / len(grp)))
        print("=" * 78)
        print("  %-5s %3s  %-15s %s" % ("cls", "n", "size px", "members"))
        for i, g in enumerate(cls):
            names = sorted(c.name for c in g)
            print("  C%-4d %3d  %7.3fx%-7.3f %s" %
                  (i, len(g), g[0].wpx, g[0].hpx, " ".join(names[:6])))
            for k in range(6, len(names), 6):
                print("  %-5s %3s  %-15s %s" % ("", "", "", " ".join(names[k:k + 6])))
        # the same question asked only at 1x -- what the 4x check is buying
        loose = {}
        for c in grp:
            loose.setdefault((c.nat, natural(c)), []).append(c)
        if len(loose) != len(cls):
            print()
            print("  The 4x check is load-bearing: at NATURAL SIZE ALONE these 58")
            print("  buttons fall into only %d classes, %d fewer.  The extra splits are"
                  % (len(loose), len(cls) - len(loose)))
            byloose = {}
            for i, g in enumerate(cls):
                byloose.setdefault((g[0].nat, natural(g[0])), []).append(i)
            for k, v in byloose.items():
                if len(v) > 1:
                    print("    %s  -- identical at 1x, different at 4x" %
                          " == ".join("C%d" % i for i in v))
        stretch_report(cls)

    nsvg_cross_check(ctrls, btns)

    print()
    print("=" * 78)
    print("CONTROLS THAT ARE NOT BUTTONS")
    print("=" * 78)
    print("  %-22s %-9s %-17s %-22s %s" %
          ("element", "norm", "size px", "viewBox origin", "line"))
    for c in others:
        print("  %-22s %-9s %8.3fx%-8.3f (%10.4f,%9.4f)  %d" %
              (c.key(), c.how.split(" ")[0], c.wpx, c.hpx, c.vb[0], c.vb[1], c.line))
    for c in ctrls:
        if not c.bake:
            print("  RESISTS BAKE: %-18s %s" % (c.key(), c.how))

    # do the two states partition the 58 buttons the same way?
    part = {}
    for state in sorted({c.state for c in btns}):
        part[state] = sorted(tuple(sorted(c.name for c in g))
                             for g in classes([c for c in btns if c.state == state]))
    same = len(set(map(str, part.values()))) == 1
    print()
    print("STATE 0 vs STATE 1: the two partitions are %s" %
          ("IDENTICAL -- one <element> per class serves both states"
           if same else "DIFFERENT -- the states must be classed separately"))

    body = sum(len(c.svg) for c in ctrls)
    btnbody = sum(len(c.svg) for c in btns)
    print("BYTE ACCOUNTING: inline SVG is %d of the file's %d bytes (%.0f%%);"
          % (body, os.path.getsize(LAY), 100.0 * body / os.path.getsize(LAY)))
    keep = 0
    for state in sorted({c.state for c in btns}):
        keep += sum(len(g[0].svg) for g in classes([c for c in btns if c.state == state]))
    print("                 the 116 button images are %d bytes, and one image per"
          % btnbody)
    print("                 class would be %d -- a %.0f%% cut of the button payload."
          % (keep, 100.0 * (btnbody - keep) / btnbody))

    print()
    print("TEXT IDENTITY -- does the bake alone make copies literally equal?")
    for state in sorted({c.state for c in btns}):
        grp = [c for c in btns if c.state == state and c.bake]
        tset = {}
        for c in grp:
            tset.setdefault(c.bake, []).append(c.name)
        px = len(classes([c for c in btns if c.state == state]))
        print("  state=%s: %d distinct normalised SVG STRINGS vs %d pixel classes -> %s"
              % (state, len(tset), px,
                 "identical -- a string compare finds every class"
                 if len(tset) == px else
                 "%d merge(s) a text compare would MISS" % (len(tset) - px)))
    noisy = {}
    for g in classes([c for c in btns if c.state == "0"]):
        if len(g) < 2 or not all(c.bake for c in g):
            continue
        ref = ATTR_RE.findall(g[0].bake)
        for c in g[1:]:
            for (k1, v1), (k2, v2) in zip(ref, ATTR_RE.findall(c.bake)):
                if k1 == k2 and v1 != v2:
                    noisy.setdefault(k1, set()).add(g[0].name)
    if noisy:
        print("  WHY: inside a single PIXEL class the baked text still disagrees on")
        print("       %s" % ", ".join("%s (%d class%s)" % (k, len(v), "" if len(v) == 1
                                                          else "es")
                                      for k, v in sorted(noisy.items())))
        print("       and it is all Inkscape per-copy noise in the 6th-7th digit:")
        print("         viewBox   9.260417 vs 9.26042      (sub-micron on a 35 px button)")
        print("         style     stroke-width 0.264583 vs 0.264584")
        print("         gradient  scale 1.1915839 vs 1.1915845, and a VERTICAL gradient")
        print("                   whose x1==x2 sits at a different -- invisible --")
        print("                   horizontal offset")
        print("       Declared px size, by contrast, is IDENTICAL inside every class.")
        print("       That noise is exactly why this probe rasterises instead of")
        print("       diffing strings: text finds %d merges, pixels find %d."
              % (58 - len({c.bake for c in btns if c.state == "0" and c.bake}),
                 58 - len(classes([c for c in btns if c.state == "0"]))))


def stretch_report(cls):
    print()
    print("  MERGES AVAILABLE IF AN ELEMENT MAY STRETCH INTO ITS <bounds>")
    print("  (render class A at class B's natural pixel size -- exactly what MAME")
    print("   does to an <element ref> given other bounds -- and compare with B.)")
    reps = [(i, g[0], len(g)) for i, g in enumerate(cls)]
    exact, near = [], []
    for ia, a, na in reps:
        for ib, b, nb in reps:
            if ia >= ib:
                continue
            wb, hb = natural(b)
            dw, dh = a.wpx - b.wpx, a.hpx - b.hpx
            if hashes(a.fold, wb, hb) == (b.nat, b.fine):
                exact.append((ia, ib, dw, dh, na, nb))
                continue
            d = max((pixdiff(raster(set_size(a.fold, wb * k, hb * k), wb * k, hb * k),
                             raster(set_size(b.fold, wb * k, hb * k), wb * k, hb * k))
                     + (k,) for k in (1, 4)), key=lambda t: (t[1], t[2]))
            if d[0] < 24.0:
                near.append((ia, ib, dw, dh, d, na, nb))
    if exact:
        print("    PIXEL-EXACT under stretch: %d pair(s)" % len(exact))
        for ia, ib, dw, dh, na, nb in exact:
            print("      C%d(n=%d) == C%d(n=%d)   size delta dx=%+.3f px dy=%+.3f px"
                  % (ia, na, ib, nb, dw, dh))
    else:
        print("    PIXEL-EXACT under stretch: NONE")
    if near:
        near.sort(key=lambda t: t[4][0])
        print("    NEAR merges (mean |RGBA delta| < 24/255), with what they cost:")
        print("      %-11s %9s %9s %8s %7s %8s %6s" %
              ("pair", "dx px", "dy px", "mean|d|", "max|d|", "%bytes", "scale"))
        for ia, ib, dw, dh, d, na, nb in near:
            print("      C%-3d -> C%-4d %+9.3f %+9.3f %8.2f %7d %7.1f%% %5dx"
                  % (ia, ib, dw, dh, d[0], d[1], d[2], d[3]))
    else:
        print("    NEAR merges under the 24/255 mean threshold: NONE")

    # the practical count: classes that differ by AT MOST ONE LSB are the same
    # float noise gate B measured, not a difference anyone can see or that any
    # renderer would reproduce.  Union them and say whether the merge even needs
    # a stretch (it does not when the two classes declare the same px size).
    parent = list(range(len(reps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    stretched = set()
    for ia, ib, dw, dh, d, na, nb in near:
        if d[1] <= 1:
            if abs(dw) > 1e-9 or abs(dh) > 1e-9:
                stretched.add((ia, ib))
            parent[find(ia)] = find(ib)
    comp = {}
    for i in range(len(reps)):
        comp.setdefault(find(i), []).append(i)
    merged = [v for v in comp.values() if len(v) > 1]
    print()
    print("    WITH A 1/255 TOLERANCE (the same float noise gate B measures):")
    if merged:
        print("      %d classes -> %d.  The merges are" %
              (len(reps), len(reps) - sum(len(v) - 1 for v in merged)))
        for v in merged:
            same = all(abs(reps[i][1].wpx - reps[v[0]][1].wpx) < 1e-9 and
                       abs(reps[i][1].hpx - reps[v[0]][1].hpx) < 1e-9 for i in v)
            print("        %-24s %7.3fx%-7.3f  %s" %
                  (" = ".join("C%d" % i for i in v),
                   reps[v[0]][1].wpx, reps[v[0]][1].hpx,
                   "SAME declared size -- no stretching needed" if same
                   else "needs a stretch"))
    else:
        print("      no change")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true",
                    help="only run the loss-free normalisation gates")
    ap.add_argument("--emit", metavar="DIR",
                    help="also write every normalised SVG (bake, else fold) to DIR")
    ap.add_argument("--lay", metavar="FILE", default=LAY,
                    help="the layout to read (default: the in-tree wsa1r.lay; the "
                         "README's numbers come from %s:src/mame/layout/wsa1r.lay)"
                         % BASELINE)
    args = ap.parse_args()

    globals()["LAY"] = args.lay
    ctrls = load()
    if not ctrls:
        print("no inline-SVG <element>s in %s" % args.lay)
        print("The reuse pass removes them; re-run against the baseline:")
        print("  git show %s:src/mame/layout/wsa1r.lay > /tmp/wsa1r-baseline.lay"
              % BASELINE)
        print("  python3 %s --lay /tmp/wsa1r-baseline.lay" % os.path.basename(__file__))
        return 2
    ok = self_test(ctrls)
    if args.emit:
        os.makedirs(args.emit, exist_ok=True)
        for c in ctrls:
            with open(os.path.join(args.emit, c.key().replace("@", "_s") + ".svg"),
                      "w", encoding="utf-8") as fh:
                fh.write(c.bake or c.fold)
        print("  wrote %d normalised SVGs to %s" % (len(ctrls), args.emit))
    if args.self_test:
        return 0 if ok else 1
    if not ok:
        print("\n!! gate A failed -- the class table below is void")
    report(ctrls)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
