#!/usr/bin/env python3
"""Render src/mame/layout/kn7000.lay as a single BLACK-AND-WHITE SVG.

The .lay is composed of <element> defs (SVG snippets / <text> / <rect>) placed by
<group> definitions and assembled by <view>s. This tool flattens one view (default
"Compact", which composes its groups at 1:1 scale with pure translation) into one
standalone SVG, recolouring every shape to white-fill / black-outline and every
label to black text. The result is an editable vector map of the panel: Felipe can
tweak element positions / dimensions / labels, and the diff is applied back to
tools/gen_lay.py.

    python3 tools/lay_to_svg.py [VIEW] [OUT.svg]
"""
import re, sys, os

LAY = os.path.join(os.path.dirname(__file__), "..", "src", "mame", "layout", "kn7000.lay")

def attrs(tag):
    return dict(re.findall(r'(\w[\w-]*)="([^"]*)"', tag))

def first_bounds(blob):
    """Return (x,y,w,h) of the first <bounds> (prefer state=0 for animated knobs)."""
    all_b = re.findall(r'<bounds\b([^>]*)/?>', blob)
    if not all_b:
        return None
    # prefer an explicit state="0" bounds if present (slider knob rest position)
    chosen = None
    for b in all_b:
        a = attrs("<x " + b + ">")
        if a.get("state") == "0":
            chosen = a; break
    if chosen is None:
        chosen = attrs("<x " + all_b[0] + ">")
    try:
        return (float(chosen["x"]), float(chosen["y"]),
                float(chosen["width"]), float(chosen["height"]))
    except KeyError:
        return None

def parse_elements(text):
    """name -> ('svg', content, ow, oh) | ('text', string) | ('rect',) ."""
    els = {}
    for m in re.finditer(r'<element name="([^"]+)">(.*?)</element>', text, re.S):
        name, body = m.group(1), m.group(2)
        img = re.search(r'<svg\b([^>]*)>(.*?)</svg>', body, re.S)
        if img:
            a = attrs("<svg " + img.group(1) + ">")
            ow = float(a.get("width", 100)); oh = float(a.get("height", 100))
            els[name] = ('svg', img.group(2), ow, oh)
            continue
        t = re.search(r'<text string="([^"]*)"', body)
        if t:
            els[name] = ('text', t.group(1))
            continue
        if '<rect' in body:
            els[name] = ('rect',)
    return els

def parse_groups(text):
    """name -> list of (ref, x, y, w, h, is_screen)."""
    groups = {}
    for m in re.finditer(r'<group name="([^"]+)">(.*?)</group>', text, re.S):
        name, body = m.group(1), m.group(2)
        # strip the group's own <bounds .../> (first line) so it isn't parsed as a placement
        placements = []
        for em in re.finditer(r'<(element|screen)\b([^>]*)>(.*?)</\1>', body, re.S):
            kind, hdr, inner = em.group(1), em.group(2), em.group(3)
            ha = attrs("<x " + hdr + ">")
            b = first_bounds(inner)
            if b is None:
                continue
            if kind == "screen":
                placements.append(("__screen__", *b, True))
            else:
                ref = ha.get("ref")
                if ref:
                    placements.append((ref, *b, False))
        groups[name] = placements
    return groups

def parse_view(text, view):
    """Return list of (group_ref, off_x, off_y, w, h) for the named view."""
    vm = re.search(r'<view name="%s">(.*?)</view>' % re.escape(view), text, re.S)
    if not vm:
        sys.exit("view %r not found" % view)
    out = []
    for gm in re.finditer(r'<group ref="([^"]+)">\s*<bounds\b([^>]*)/?>', gm_body := vm.group(1)):
        a = attrs("<x " + gm.group(2) + ">")
        out.append((gm.group(1), float(a["x"]), float(a["y"]),
                    float(a["width"]), float(a["height"])))
    return out

SHAPE_RE = re.compile(r'<(circle|rect|path|ellipse|line|polygon|polyline)\b([^>]*?)(/?)>')

def bw(svg_content):
    """Recolour a snippet to white-fill / black outline with a constant (non-scaling)
    1.5px stroke, so buttons stay visible at any placement scale."""
    def norm(mo):
        name, attr, close = mo.group(1), mo.group(2), mo.group(3)
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', attr))
        keep_none = a.get("fill") == "none"
        # drop styling we override; keep geometry attrs
        for k in ("fill", "stroke", "stroke-width", "vector-effect", "style"):
            a.pop(k, None)
        geom = " ".join(f'{k}="{v}"' for k, v in a.items())
        fill = "none" if keep_none else "#ffffff"
        return (f'<{name} {geom} fill="{fill}" stroke="#000000" stroke-width="2"'
                f'{("/" if close else "")}>')
    return SHAPE_RE.sub(norm, svg_content)

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def main():
    view = sys.argv[1] if len(sys.argv) > 1 else "Compact"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(__file__), "..", "..", "KN7000", "side-quests", "kn7000_layout.svg")
    text = open(LAY).read()
    els = parse_elements(text)
    groups = parse_groups(text)
    placements = parse_view(text, view)

    # canvas = union of the group offsets + sizes
    W = max(ox + w for _, ox, oy, w, h in placements)
    H = max(oy + h for _, ox, oy, w, h in placements)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="sans-serif">',
         f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>']
    for gref, ox, oy, gw, gh in placements:
        for ref, x, y, w, h, is_screen in groups.get(gref, []):
            ax, ay = ox + x, oy + y
            if is_screen:
                o.append(f'<rect x="{ax}" y="{ay}" width="{w}" height="{h}" '
                         f'fill="#ffffff" stroke="#000000" stroke-width="2"/>')
                o.append(f'<text x="{ax+w/2}" y="{ay+h/2}" text-anchor="middle" '
                         f'font-size="24" fill="#000000">LCD SCREEN</text>')
                continue
            e = els.get(ref)
            if not e:
                continue
            if e[0] == 'svg':
                _, content, ow, oh = e
                sx = w / ow if ow else 1
                sy = h / oh if oh else 1
                o.append(f'<g transform="translate({ax},{ay}) scale({sx:.4f},{sy:.4f})">'
                         f'{bw(content)}</g>')
            elif e[0] == 'text':
                fs = min(h * 0.9, 13)
                # e[1] is already XML-escaped (extracted verbatim from the .lay) -- do not re-escape
                o.append(f'<text x="{ax+w/2}" y="{ay+h*0.78}" text-anchor="middle" '
                         f'font-size="{fs:.1f}" fill="#000000">{e[1]}</text>')
            elif e[0] == 'rect':
                o.append(f'<rect x="{ax}" y="{ay}" width="{w}" height="{h}" '
                         f'fill="none" stroke="#000000" stroke-width="0.5"/>')
    o.append('</svg>')
    with open(out, "w") as f:
        f.write("\n".join(o) + "\n")
    print(f"wrote {os.path.abspath(out)}  ({W:.0f}x{H:.0f}, {len(placements)} groups, "
          f"{sum(len(groups.get(g[0],[])) for g in placements)} placements)")

if __name__ == "__main__":
    main()
