#!/usr/bin/env python3
"""Generate src/mame/layout/wsa1r.lay from Felipe's SX-WSA1R artwork.

    python3 tools/gen_wsa1r_lay.py                 # write the .lay
    python3 tools/gen_wsa1r_lay.py --preview p.svg # a composed SVG for eyeballing
    python3 tools/gen_wsa1r_lay.py --check         # regenerate and diff, exit 1 if stale

WHY A GENERATOR AND NOT A HAND-WRITTEN .lay
-------------------------------------------
The artwork is Felipe's and it is faithful to the service manual's own
ARRANGEMENT OF CONTROL PANEL drawing (PDF page 5 = manual I-4).  Redrawing its
79 gradients by hand would lose it, and a raster background cannot show a
button being pressed or an LED lighting.  So this script does what kn5000.lay
does by hand: it LIFTS each interactive shape out of the drawing into a
two-state <element>, and leaves everything else in one static vector_art
element -- gradients, defs and all, exactly as drawn.

Every <bounds> value is computed by tools/wsa1_svg_geometry.py, never measured.

WHAT IS BOUND AND WHAT IS NOT is decided by the tables below and reproduced
verbatim into the .lay's header comment, so the file explains itself.
"""

import copy
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import wsa1_svg_geometry as geo          # noqa: E402

ART = geo.ART
OUT = os.path.join(ROOT, "src", "mame", "layout", "wsa1r.lay")
KN5000 = os.path.join(ROOT, "src", "mame", "layout", "kn5000.lay")

SVG = '{http://www.w3.org/2000/svg}'
XLINK = '{http://www.w3.org/1999/xlink}'
VIEW_W, VIEW_H = 1600.0, 500.0


# =======================================================================
#  THE MATRIX.  (segment, mask) -> (svg ids, legend, provenance tier)
#
#  tier "L" = the CP1/CP2 P.C. Diagram PRINTS this legend next to the switch
#             (PDF p.32 = manual II-29/30), and prom_a's own switch->LED table
#             at 0xF95088 agrees on segment, bit and population.
#  tier "B" = the switch's NET is traced, but its panel position is read off
#             the P.C. Board page (PDF p.31), whose orientation is anchored by
#             silkscreen in both axes.  The ROM's family tags corroborate the
#             GROUPING but not the individual position.
#  tier "F"  = the position is read off the P.C. Board page like tier B, but the
#             FIRMWARE then settled it, live.  Only the ten LCD soft keys are in
#             this tier; see the header comment the generator emits.
# =======================================================================

BUTTONS = [
    # SEG0 -- CP1 column 1, printed legends
    (0, 0x01, ["path244"], "PLAY MODE SOUND", "L"),
    (0, 0x02, ["path245"], "PLAY MODE COMBI", "L"),
    (0, 0x04, ["path246"], "EDIT MODE SOUND", "L"),
    (0, 0x08, ["path247"], "EDIT MODE COMBI", "L"),
    (0, 0x10, ["path240"], "BANK USER 1", "L"),
    (0, 0x20, ["path241"], "BANK USER 2", "L"),
    (0, 0x40, ["path242"], "BANK ROM/EXT", "L"),
    (0, 0x80, ["path243"], "BANK RE-MAP", "L"),

    # SEG1 -- the number pad, keys 0..7.  These four are the ones the SELF-
    # DIAGNOSTIC page (manual I-11/I-12) names by key, and they are what the
    # driver already had as its only known positions.
    (1, 0x01, ["path252"], "number 0", "L"),
    (1, 0x02, ["path255"], "number 1", "L"),
    (1, 0x04, ["path254"], "number 2", "L"),
    (1, 0x08, ["path253"], "number 3", "L"),
    (1, 0x10, ["path259"], "number 4", "L"),
    (1, 0x20, ["path258"], "number 5", "L"),
    (1, 0x40, ["path257"], "number 6", "L"),
    (1, 0x80, ["path263"], "number 7", "L"),

    # SEG2 -- printed legends; bit 7 is SW24/D24, NOT FITTED
    (2, 0x01, ["path262"], "number 8", "L"),
    (2, 0x02, ["path261"], "number 9", "L"),
    (2, 0x04, ["path251"], "+/-", "L"),
    (2, 0x08, ["path250"], "ENTER", "L"),
    (2, 0x10, ["path45"],  "PAGE down", "L"),
    (2, 0x20, ["path94"],  "PAGE up", "L"),
    (2, 0x40, ["path231"], "COMPARE", "L"),

    # SEG3 -- CP1's five-key column and the -1/+1/EXIT trio
    (3, 0x01, ["path16", "path772"], "LCD soft key, RIGHT column, 1st from top", "F"),
    (3, 0x02, ["path27", "path142"], "LCD soft key, RIGHT column, 2nd", "F"),
    (3, 0x04, ["path26", "path141"], "LCD soft key, RIGHT column, 3rd", "F"),
    (3, 0x08, ["path25", "path140"], "LCD soft key, RIGHT column, 4th", "F"),
    (3, 0x10, ["path24", "path139"], "LCD soft key, RIGHT column, 5th", "F"),
    (3, 0x20, ["path267"], "-1", "B"),
    (3, 0x40, ["path269"], "+1", "B"),
    (3, 0x80, ["path270"], "EXIT", "B"),

    # SEG4/SEG5 -- the 16 keys under the LCD, columns 1..8 left to right,
    # BOTTOM row on the even bit and TOP row on the odd bit
    (4, 0x01, ["path53"], "under-LCD key, column 1, bottom", "B"),
    (4, 0x02, ["path46"], "under-LCD key, column 1, top", "B"),
    (4, 0x04, ["path54"], "under-LCD key, column 2, bottom", "B"),
    (4, 0x08, ["path47"], "under-LCD key, column 2, top", "B"),
    (4, 0x10, ["path55"], "under-LCD key, column 3, bottom", "B"),
    (4, 0x20, ["path48"], "under-LCD key, column 3, top", "B"),
    (4, 0x40, ["path56"], "under-LCD key, column 4, bottom", "B"),
    (4, 0x80, ["path49"], "under-LCD key, column 4, top", "B"),
    (5, 0x01, ["path57"], "under-LCD key, column 5, bottom", "B"),
    (5, 0x02, ["path50"], "under-LCD key, column 5, top", "B"),
    (5, 0x04, ["path58"], "under-LCD key, column 6, bottom", "B"),
    (5, 0x08, ["path51"], "under-LCD key, column 6, top", "B"),
    (5, 0x10, ["path59"], "under-LCD key, column 7, bottom", "B"),
    (5, 0x20, ["path52"], "under-LCD key, column 7, top", "B"),
    (5, 0x40, ["path61"], "under-LCD key, column 8, bottom", "B"),
    (5, 0x80, ["path60"], "under-LCD key, column 8, top", "B"),

    # SEG7 -- CP2 column A, printed legends
    (7, 0x01, ["path80"], "MENU PART", "L"),
    (7, 0x02, ["path78"], "MENU SYSTEM", "L"),
    (7, 0x04, ["path79"], "MENU MIDI", "L"),
    (7, 0x08, ["path77"], "MENU DISK", "L"),

    # SEG8 -- CP2 column B, printed legends
    (8, 0x01, ["circle196"],  "REALTIME CREATOR 1~6", "L"),
    (8, 0x02, ["ellipse228"], "REALTIME CREATOR RESET", "L"),

    # SEG9 -- CP2's five-key column
    (9, 0x01, ["path143", "path148"], "LCD soft key, LEFT column, 1st from top", "F"),
    (9, 0x02, ["path147", "path152"], "LCD soft key, LEFT column, 2nd", "F"),
    (9, 0x04, ["path146", "path151"], "LCD soft key, LEFT column, 3rd", "F"),
    (9, 0x08, ["path145", "path150"], "LCD soft key, LEFT column, 4th", "F"),
    (9, 0x10, ["path144", "path149"], "LCD soft key, LEFT column, 5th", "F"),
]

# =======================================================================
#  THE LAMPS.  svg id -> (output name or None, colour, legend, why)
#
#  The output index is register*8 + bit; the register comes from the HIGH byte
#  of prom_a's variant-2 switch->LED word table at 0xF95088 and the bit from
#  its low byte, which is the LED DATA byte the panel MCU is handed
#  (Panel_SetLedRegister prom_a 0xF8C846: `ld W,(XIX+W)` maps the register to
#  the wire address, then [wire][mask] goes into the outbound queue).
#  notes/wsa1-probes/wsa1_lamp_identification.py asserts every row of this.
# =======================================================================

LAMPS = [
    ("ellipse315", "led8",  "green", "PLAY MODE SOUND (D116)",  "reg1 bit0 <- SEG0/SW0"),
    ("ellipse316", "led9",  "green", "PLAY MODE COMBI (D117)",  "reg1 bit1 <- SEG0/SW1"),
    ("ellipse317", "led10", "green", "EDIT MODE SOUND (D118)",  "reg1 bit2 <- SEG0/SW2"),
    ("ellipse314", "led11", "green", "EDIT MODE COMBI (D119)",  "reg1 bit3 <- SEG0/SW3"),
    ("ellipse307", "led0",  "red",   "BANK USER 1 (D120)",      "reg0 bit0 <- SEG0/SW4"),
    ("ellipse308", "led1",  "red",   "BANK USER 2 (D121)",      "reg0 bit1 <- SEG0/SW5"),
    ("ellipse309", "led2",  "red",   "BANK ROM/EXT (D122)",     "reg0 bit2 <- SEG0/SW6"),
    ("ellipse310", "led3",  "red",   "BANK RE-MAP (D123)",      "reg0 bit3 <- SEG0/SW7"),
    ("ellipse45",  "led32", "green", "MENU PART (D160)",        "reg4 bit0 <- SEG7/SW0"),
    ("ellipse44",  "led33", "green", "MENU SYSTEM (D161)",      "reg4 bit1 <- SEG7/SW1"),
    ("circle157",  "led40", "green", "MENU MIDI (D162)",        "reg5 bit0 <- SEG7/SW2"),
    ("ellipse43",  "led41", "green", "MENU DISK (D163)",        "reg5 bit1 <- SEG7/SW3"),
    ("ellipse231", "led50", "red",   "COMPARE (D130)",          "reg6 bit2, the LCD-key family indicator"),
    ("ellipse318", "led51", "green", "MIDI / NUMBER PAD (D131)", "reg6 bit3, the numeric family indicator"),
    # The four REALTIME CREATOR ring lamps.  The ROM says the set is
    # {reg2 bit0, reg2 bit1, reg3 bit0, reg3 bit1} = led16, led17, led24, led25
    # (RESET lights reg2 mask 0x03, "1~6" lights reg3 mask 0x03), but nothing
    # read so far says WHICH of the four is north / east / south / west.
    ("circle146-6", None, "red", "REALTIME CREATOR ring, top",    "one of led16/17/24/25 -- not decoded"),
    ("ellipse203",  None, "red", "REALTIME CREATOR ring, right",  "one of led16/17/24/25 -- not decoded"),
    ("ellipse202",  None, "red", "REALTIME CREATOR ring, bottom", "one of led16/17/24/25 -- not decoded"),
    ("ellipse204",  None, "red", "REALTIME CREATOR ring, left",   "one of led16/17/24/25 -- not decoded"),
    # Off-panel: the SERVICE CHECKING DEVICE's lamp on CN4, wsa1.cpp cpu1_p5_w().
    ("circle146-6-9", "check_led", "red", "service checking device (CN4)",
     "driver output, wsa1.cpp P5 bit 3"),
]

# Knobs: (svg ids, item id, comment)
KNOBS = [
    (["circle276", "circle849"], "data_wheel", "DATA ENTRY DIAL body"),
    (["circle277"],              "data_wheel_finger", "DATA ENTRY DIAL finger dimple"),
    (["ellipse221", "ellipse222", "path222"], "volume_knob", "VOLUME (wire 0xD3)"),
]

# The blue rectangle Felipe drew for the LCD: the emulated screen goes here.
SCREEN_ID = "rect27"


# ----------------------------------------------------------------- helpers

def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;'))


def cmt(s):
    """Text safe inside an XML comment: '--' is illegal there, anywhere."""
    return re.sub(r'-{2,}', '-', s).rstrip('-')


def hex_to_rgb(h):
    h = h.strip().lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


class Art:
    def __init__(self, path=ART):
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()
        self.parent = {}
        self.xform = {}          # element -> accumulated PARENT transform
        self.by_id = {}
        self._index(self.root, (1, 0, 0, 1, 0, 0))
        self.defs = self.root.find(SVG + 'defs')

    def _index(self, node, m):
        for ch in node:
            self.parent[ch] = node
            self.xform[ch] = m
            i = ch.get('id')
            if i:
                self.by_id[i] = ch
            cm = geo.mat_mul(m, geo.parse_transform(ch.get('transform')))
            self._index(ch, cm)

    def bbox_px(self, ids):
        """Union bbox in render px of the named shapes."""
        x0 = y0 = 1e9
        x1 = y1 = -1e9
        for i in ids:
            el = self.by_id[i]
            m = geo.mat_mul(self.xform[el], geo.parse_transform(el.get('transform')))
            r = geo.bbox_px(el, m)
            if r is None:
                raise SystemExit("no geometry for id %s" % i)
            (x, y, w, h), _ = r
            x0, y0 = min(x0, x), min(y0, y)
            x1, y1 = max(x1, x + w), max(y1, y + h)
        return x0, y0, x1 - x0, y1 - y0

    def gradients_used(self, el):
        """ids of the gradients this element's paint references, transitively."""
        out, todo = [], []
        blob = (el.get('style') or '') + ' ' + (el.get('fill') or '') + ' ' + (el.get('stroke') or '')
        todo += re.findall(r'url\(#([^)]+)\)', blob)
        seen = set()
        while todo:
            g = todo.pop()
            if g in seen:
                continue
            seen.add(g)
            node = self.by_id.get(g)
            if node is None:
                continue
            out.append(node)
            href = node.get(XLINK + 'href') or node.get('href')
            if href and href.startswith('#'):
                todo.append(href[1:])
        return out


def strip_ns(el):
    """Drop inkscape/sodipodi cruft so the serialised art stays readable."""
    for k in list(el.attrib):
        if k.startswith('{http://www.inkscape.org') or k.startswith('{http://sodipodi'):
            del el.attrib[k]
    for ch in list(el):
        if ch.tag.startswith('{http://sodipodi') or ch.tag.startswith('{http://www.inkscape.org'):
            el.remove(ch)
        else:
            strip_ns(ch)


def ser(el):
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    return ET.tostring(el, encoding='unicode')


def shape_svg(art, ids, x0u, y0u, wu, hu, wpx, hpx, dark=False):
    """One control, cropped to its own bbox, in the ROOT user-space viewBox."""
    grads = []
    seen = set()
    body = []
    for i in ids:
        el = art.by_id[i]
        for g in art.gradients_used(el):
            if g.get('id') not in seen:
                seen.add(g.get('id'))
                gc = copy.deepcopy(g)
                strip_ns(gc)
                grads.append(gc)
        m = art.xform[el]
        cp = copy.deepcopy(el)
        strip_ns(cp)
        if dark:
            cp.set('style', 'fill:#000000;fill-opacity:0.34;stroke:none')
            for k in ('fill', 'stroke'):
                if k in cp.attrib:
                    del cp.attrib[k]
        body.append('<g transform="matrix(%s)">%s</g>'
                    % (','.join('%.9g' % v for v in m), ser(cp)))
    d = ''.join(ser(g) for g in grads)
    return ('<svg width="%.3f" height="%.3f" viewBox="%.6f %.6f %.6f %.6f">'
            '<defs>%s</defs>%s</svg>'
            % (wpx, hpx, x0u, y0u, wu, hu, d, ''.join(body)))


def control_element(art, name, ids, comment, pressable=True):
    x, y, w, h = art.bbox_px(ids)
    x0u, y0u = x / geo.SCALE, y / geo.SCALE
    wu, hu = w / geo.SCALE, h / geo.SCALE
    out = ['\t<element name="%s"><!-- %s -->' % (name, cmt(esc(comment)))]
    if pressable:
        for st, dark in ((0, False), (1, True)):
            svg = shape_svg(art, ids, x0u, y0u, wu, hu, w, h, dark=dark)
            if dark:
                # keep the unpressed art underneath the darkening overlay
                base = shape_svg(art, ids, x0u, y0u, wu, hu, w, h, dark=False)
                svg = base[:-len('</svg>')] + svg[svg.index('</defs>') + len('</defs>'):]
            out.append('\t\t<image state="%d"><data><![CDATA[%s]]></data></image>' % (st, svg))
    else:
        out.append('\t\t<image><data><![CDATA[%s]]></data></image>'
                   % shape_svg(art, ids, x0u, y0u, wu, hu, w, h))
    out.append('\t</element>')
    return '\n'.join(out), (x, y, w, h)



# MAME's draw_text() (src/emu/rendlay.cpp) renders the glyphs at bounds.HEIGHT
# and then squeezes them HORIZONTALLY by bounds.width/string_width if they do
# not fit.  That is exactly the non-uniform scale(sx, sy) Felipe's Inkscape text
# carries, so a legend reproduces at its drawn proportions if and only if the
# bounds are (true drawn advance width) x (true glyph height).  A generous box
# would let "ACOUSTIC MODELING SYNTHESIZER MODULE" render at full width and
# collide with the Technics logo.
#
# Advance widths are measured with DejaVu Sans (the artwork's family is
# 'DejaVu Math TeX Gyre', same metrics for Latin), falling back to a flat 0.62
# em ratio if PIL is not installed.
_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
_EM = 256
_font = [None, False]


def em_width(s):
    """Advance width of `s` in EM units (multiply by the font size in px)."""
    if not _font[1]:
        _font[1] = True
        try:
            from PIL import ImageFont
            for path in _FONTS:
                if os.path.exists(path):
                    _font[0] = ImageFont.truetype(path, _EM)
                    break
        except Exception:
            pass
    if _font[0] is None:
        return len(s) * 0.62
    return _font[0].getlength(s) / _EM


# ----------------------------------------------------------------- labels

def labels(art):
    """MAME <text> elements for every legend Felipe drew, with their bounds."""
    rows = []
    n = 0
    for t in art.root.iter(SVG + 'text'):
        s = ' '.join(''.join(t.itertext()).split())
        if not s:
            continue
        m = geo.mat_mul(art.xform[t], geo.parse_transform(t.get('transform')))
        x = t.get('x')
        y = t.get('y')
        ts = t.find(SVG + 'tspan')
        if x is None and ts is not None:
            x, y = ts.get('x', '0'), ts.get('y', '0')
        ax, ay = geo.apply(m, float(x.split()[0]), float(y.split()[0]))
        ax, ay = ax * geo.SCALE, ay * geo.SCALE
        st = dict(re.findall(r'([a-z-]+)\s*:\s*([^;]+)', t.get('style', '')))
        if ts is not None:                       # the tspan's style wins
            st.update(dict(re.findall(r'([a-z-]+)\s*:\s*([^;]+)', ts.get('style', ''))))
        em = float(re.sub(r'[^0-9.]', '', st.get('font-size', '2.8')))
        fs_v = em * abs(m[3]) * geo.SCALE        # glyph HEIGHT after the layer scale
        fs_h = em * abs(m[0]) * geo.SCALE        # glyph WIDTH scale, usually different
        anchor = st.get('text-anchor', 'middle').strip()
        fill = st.get('fill', '#e2e8f4').strip()
        h = fs_v * 1.164                         # em -> ascent+descent (DejaVu)
        w = max(em_width(s) * fs_h, 1.0)
        top = ay - h * 0.80                      # baseline sits ~0.8 down the box
        if anchor == 'middle':
            left, align = ax - w / 2, 0
        elif anchor == 'end':
            left, align = ax - w, 2
        else:
            left, align = ax, 1
        n += 1
        rows.append(dict(name='lbl%d' % n, text=s, x=left, y=top, w=w, h=h,
                         align=align, rgb=hex_to_rgb(fill), src=t.get('id', '')))
    return rows


# ----------------------------------------------------------------- library

def slider_library():
    """The shared widget library, taken from kn5000.lay -- the newest copy.

    ⚠ NOT from tools/slider_lib.lua: that file is STALE (it still has the
    single-port add_rotary_knob that kn7000.lay's generator calls, and
    kn7000.lay would break if it were updated in place).  kn5000.lay carries
    the two-port drag/key version this layout needs.
    """
    src = open(KN5000).read()
    a = src.index("-- Slider and knob library starts.")
    b = src.index("-- Slider and knob library ends.") + len("-- Slider and knob library ends.")
    return src[src.rindex('\n', 0, a) + 1:b]


# ----------------------------------------------------------------- header

def header_comment():
    lines = []
    lines.append("license:CC0-1.0")
    lines.append("")
    lines.append("Technics SX-WSA1R - ACOUSTIC MODELING SYNTHESIZER MODULE, the 2U rack.")
    lines.append("")
    lines.append("GENERATED by tools/gen_wsa1r_lay.py from Felipe's artwork")
    lines.append("~/compartilhado/KN7000/wsa1r_artwork/wsa1r_cpanel.svg, which reproduces the")
    lines.append("service manual's ARRANGEMENT OF CONTROL PANEL drawing (PDF page 5 = manual")
    lines.append("I-4/I-5).  Do not hand-edit: edit the SVG or the generator and re-run.")
    lines.append("Every <bounds> comes from tools/wsa1_svg_geometry.py, whose self-test")
    lines.append("pins nine landmarks, the LCD among them: Felipe drew it 1:1, exactly 320x240.")
    lines.append("")
    lines.append("THE SWITCH MATRIX - where the bindings come from")
    lines.append("================================================")
    lines.append("CP1/CP2 P.C. Diagram, PDF p.32 (manual II-29/30), traced by programmatic")
    lines.append("black-run extraction at 400 dpi: notes/wsa1-probes/wsa1_sch_TRACE.md and the")
    lines.append("three scan scripts beside it.  IC1 = M37471M2196S; SEG0..SEG9 are its scan")
    lines.append("columns (SEG6 pin 40 and SEG10 pin 33 are DEAD STUBS on the rack) and")
    lines.append("SW0..SW7 its return rows.")
    lines.append("")
    lines.append("Independently, prom_a's own variant-2 switch->LED table at 0xF95088 stores")
    lines.append("0x0000 for a position with no switch.  Relabel its nine rows as the nine")
    lines.append("wired segments and its zero pattern IS the schematic: 58 populated cells =")
    lines.append("47 (CP1) + 11 (CP2), the parts-list counts exactly, with the single hole at")
    lines.append("SEG2/SW7 = SW24/D24 not fitted.  15/15 checks pass in")
    lines.append("notes/wsa1-probes/wsa1_sch_vs_rom_matrix.py.  Nothing from the schematic was")
    lines.append("fed into that script, so it is a genuine second witness to segment<->column,")
    lines.append("bit<->row and population.")
    lines.append("")
    lines.append("PROVENANCE PER BUTTON.  Every one of the 58 is BOUND, and each carries its")
    lines.append("tier in its own comment:")
    lines.append("")
    n_l = sum(1 for b in BUTTONS if b[4] == 'L')
    n_b = sum(1 for b in BUTTONS if b[4] == 'B')
    n_bx = sum(1 for b in BUTTONS if b[4] == 'F')
    lines.append("  [L]  %2d buttons - the schematic PRINTS this legend next to this switch." % n_l)
    lines.append("  [B]  %2d buttons - net traced, panel position read off the P.C. BOARD page" % n_b)
    lines.append("                   (PDF p.31), whose orientation is anchored by silkscreen in")
    lines.append("                   BOTH axes (keypad reads 7,8 left-to-right and 7/4/1/0 top-")
    lines.append("                   to-bottom; PAGE is silkscreened up on SW22, down on SW21).")
    lines.append("                   The ROM's family tags corroborate the GROUPING: 0x0608 is")
    lines.append("                   exactly the numeric family (keys 0-9, +/-, ENTER and SEG3")
    lines.append("                   bits 5-7) and 0x0604 exactly the LCD-navigation family.")
    lines.append("  [F]  %2d buttons - the ten LCD soft keys.  Their NET is traced like tier B," % n_bx)
    lines.append("                   but their column was the one reading left resting on the")
    lines.append("                   board page's left-right orientation: neither five-key")
    lines.append("                   column is legended and both carry the ROM family tag")
    lines.append("                   0x0604.  ★ THE FIRMWARE SETTLED IT.  Screen 0x40, the DISK")
    lines.append("                   menu, draws FOUR entries down the left of the LCD (DISK")
    lines.append("                   LOAD / DISK SAVE / MIDI FILE DIRECT PLAY / FLOPPY DISK")
    lines.append("                   FORMAT) and TWO down the right (LOAD SINGLE SOUND / LOAD")
    lines.append("                   SINGLE COMBI.).  Pressing rows 1..5 of each column and")
    lines.append("                   reading the family-B screen the firmware moves to gives")
    lines.append("")
    lines.append("                     row   SEG9            SEG3")
    lines.append("                      1    47 DISK LOAD    54 LOAD SINGLE SOUND")
    lines.append("                      2    4C DISK SAVE    53 LOAD SINGLE COMBI.")
    lines.append("                      3    45 MIDI FILE    40 no change")
    lines.append("                      4    50 FLOPPY FMT   40 no change")
    lines.append("                      5    40 no change    40 no change")
    lines.append("")
    lines.append("                   Four live rows on SEG9, two on SEG3 - exactly as the menu")
    lines.append("                   is drawn.  SEG9 IS THE LEFT COLUMN and SEG3 the right.")
    lines.append("                   Reproduce: notes/wsa1-probes/wsa1_softkey_columns.sh")
    lines.append("")
    lines.append("NOT FITTED, so not drawn and not bound: SEG2/SW7 (SW24), SEG7/SW4..SW7,")
    lines.append("SEG8/SW2..SW7, SEG9/SW5..SW7.  SEG6 and SEG10 exist in the device's port")
    lines.append("list for the SX-WSA1 keyboard only; on this machine segment_is_wired()")
    lines.append("refuses them (wsa1_cpanel.cpp), so nothing here may bind to them.")
    lines.append("")
    lines.append("THE LAMPS")
    lines.append("=========")
    lines.append("18 lamps on the rack, and prom_a's table names 14 of them outright.  The")
    lines.append("word at 0xF95088 is (LED register << 8) | LED bit mask - confirmed from the")
    lines.append("code, not assumed: sub_F94E1C does `ld WA,(XHL)` and calls 0xF40670 -> the")
    lines.append("UNGUARDED entry of Panel_SetLedRegister (prom_a 0xF8C846), which maps W")
    lines.append("through the register->wire table and queues [wire][A].  So W (the high byte)")
    lines.append("is the register and A (the low byte) is the data.  The driver's output index")
    lines.append("is register*8 + bit, hence the led# numbers below.")
    lines.append("")
    lines.append("DRAWN BUT NOT BOUND, and why:")
    lines.append("  * the four REALTIME CREATOR ring lamps.  The ROM pins the SET to")
    lines.append("    {led16, led17, led24, led25} (RESET lights reg2 mask 0x03, \"1~6\" lights")
    lines.append("    reg3 mask 0x03) but not which of the four is north/east/south/west.")
    lines.append("  * the floppy drive's activity lamp - it belongs to the FDD, and the")
    lines.append("    driver exposes no output for it.")
    lines.append("  * CONTRAST.  VR2 on CP2 is an LCD bias pot whose wiper goes back to MAIN")
    lines.append("    as VO; it is not a panel-MCU input and there is no ioport to bind.")
    lines.append("  * POWER, PHONES, the floppy eject button - no port exists for any of them.")
    lines.append("  * REALTIME CREATOR itself is NOT a panel control: it is board MB2's")
    lines.append("    triple-gang VR2, reporting JOYX/JOYY to the MAIN TMP95C061's own A/D")
    lines.append("    (PDF p.19).  Only its four ring lamps are on CP2.  Drawn, inert.")
    lines.append("")
    lines.append("This layout is for the RACK (wsa1r) only.  The SX-WSA1 keyboard's panel is a")
    lines.append("different board with two extra scan columns and three extra pots, and NO")
    lines.append("document for it exists anywhere, so it deliberately gets no layout rather")
    lines.append("than a silently reused one.")
    return '\n'.join('\t' + ln if ln else '' for ln in lines)


# ----------------------------------------------------------------- generate

def build():
    art = Art()
    out = []
    out.append('<?xml version="1.0"?>')
    out.append('<!--\n%s\n-->' % cmt(header_comment()))
    out.append('<mamelayout version="2">')

    extracted = set()

    # ---- controls ------------------------------------------------------
    elems, places = [], []

    for seg, mask, ids, legend, tier in BUTTONS:
        name = 'btn_s%d_b%d' % (seg, mask.bit_length() - 1)
        e, (x, y, w, h) = control_element(art, name, ids, '%s  [%s]' % (legend, tier))
        elems.append(e)
        places.append('\t\t<element ref="%s" inputtag="cpanel:CP_SEG%d" inputmask="0x%02x">'
                      '<!-- SEG%d/SW%d  %s  [%s] -->'
                      '<bounds x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></element>'
                      % (name, seg, mask, seg, mask.bit_length() - 1, cmt(esc(legend)), tier,
                         x, y, w, h))
        extracted.update(ids)

    # knobs (no press state)
    knob_bounds = {}
    for ids, iid, comment in KNOBS:
        e, (x, y, w, h) = control_element(art, iid, ids, comment, pressable=False)
        elems.append(e)
        knob_bounds[iid] = (x, y, w, h)
        places.append('\t\t<element id="%s" ref="%s"><!-- %s -->'
                      '<bounds x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></element>'
                      % (iid, iid, cmt(esc(comment)), x, y, w, h))
        extracted.update(ids)

    # ---- lamps ---------------------------------------------------------
    lamp_places = []
    for sid, outname, colour, legend, why in LAMPS:
        x, y, w, h = art.bbox_px([sid])
        ref = 'wsa1_led_%s' % colour
        if outname:
            lamp_places.append('\t\t<element name="%s" ref="%s"><!-- %s ; %s -->'
                               '<bounds x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></element>'
                               % (outname, ref, cmt(esc(legend)), cmt(esc(why)), x, y, w, h))
        else:
            lamp_places.append('\t\t<element ref="%s"><!-- UNBOUND: %s ; %s -->'
                               '<bounds x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></element>'
                               % (ref, cmt(esc(legend)), cmt(esc(why)), x, y, w, h))
        extracted.add(sid)

    # ---- labels --------------------------------------------------------
    # ⚠ BEFORE the static-art prune below, which deletes every <text> node from
    # the tree.  Computing them afterwards silently yields an empty list and a
    # panel with no legends at all.
    lbl = labels(art)

    # ---- static art ----------------------------------------------------
    extracted.add(SCREEN_ID)
    root = art.root
    for parent in list(root.iter()):
        for ch in list(parent):
            i = ch.get('id')
            if (i in extracted) or ch.tag == SVG + 'text' \
                    or ch.tag.startswith('{http://sodipodi'):
                parent.remove(ch)
    strip_ns(root)
    for k in ('width', 'height'):
        root.set(k, '1600' if k == 'width' else '500')
    art_svg = ser(root)

    out.append('\t<!-- Felipe\'s drawing, minus every shape lifted out below.  The')
    out.append('\t     gradients, the shaded floppy bezel and the bevelled wheels are his,')
    out.append('\t     transplanted whole rather than redrawn. -->')
    out.append('\t<element name="vector_art">')
    out.append('\t\t<image><data><![CDATA[%s]]></data></image>' % art_svg)
    out.append('\t</element>')
    out.append('')
    out.append('\t<!-- LN382G / LN282R, unlit fills taken from the artwork (#003000 / #440000). -->')
    out.append('\t<element name="wsa1_led_green" defstate="0">')
    out.append('\t\t<disk state="0"><color red="0.00" green="0.19" blue="0.00"/></disk>')
    out.append('\t\t<disk state="1"><color red="0.15" green="1.00" blue="0.15"/></disk>')
    out.append('\t</element>')
    out.append('\t<element name="wsa1_led_red" defstate="0">')
    out.append('\t\t<disk state="0"><color red="0.27" green="0.00" blue="0.00"/></disk>')
    out.append('\t\t<disk state="1"><color red="1.00" green="0.13" blue="0.13"/></disk>')
    out.append('\t</element>')
    out.append('')
    out.extend(elems)
    out.append('')

    # ---- label elements ------------------------------------------------
    for r in lbl:
        out.append('\t<element name="%s"><text string="%s" align="%d">'
                   '<color red="%.2f" green="%.2f" blue="%.2f"/></text></element>'
                   % (r['name'], esc(r['text']), r['align'], *r['rgb']))
    out.append('')

    # ---- group ---------------------------------------------------------
    sx, sy, sw, sh = art.bbox_px([SCREEN_ID])
    out.append('\t<group name="panel">')
    out.append('\t\t<bounds left="0" right="%d" top="0" bottom="%d"/>' % (VIEW_W, VIEW_H))
    out.append('\t\t<element ref="vector_art"><bounds x="0" y="0" width="%d" height="%d"/></element>'
               % (VIEW_W, VIEW_H))
    out.append('')
    out.append('\t\t<!-- The SED1330 panel, 320x240 (wsa1.cpp screen.set_size).  Felipe drew')
    out.append('\t\t     the LCD 1:1, so this lands inside his bezel with no scaling. -->')
    out.append('\t\t<screen index="0"><bounds x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></screen>'
               % (sx, sy, sw, sh))
    out.append('')
    out.extend(places)
    out.append('')
    out.extend(lamp_places)
    out.append('')
    for r in lbl:
        out.append('\t\t<element ref="%s"><!-- %s -->'
                   '<bounds x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></element>'
                   % (r['name'], cmt(esc(r['text'])), r['x'], r['y'], r['w'], r['h']))
    out.append('\t</group>')
    out.append('')
    out.append('\t<view name="Control Panel">')
    out.append('\t\t<bounds x="0" y="0" width="%d" height="%d"/>' % (VIEW_W, VIEW_H))
    out.append('\t\t<group ref="panel"><bounds x="0" y="0" width="%d" height="%d"/></group>'
               % (VIEW_W, VIEW_H))
    out.append('\t</view>')
    out.append('')
    out.append('\t<view name="Screen close-up">')
    out.append('\t\t<bounds x="548" y="44" width="488" height="313"/>')
    out.append('\t\t<group ref="panel"><bounds x="0" y="0" width="%d" height="%d"/></group>'
               % (VIEW_W, VIEW_H))
    out.append('\t</view>')
    out.append('')
    out.append('\t<script><![CDATA[')
    out.append(slider_library())
    out.append('''
		-- SX-WSA1R DATA ENTRY DIAL (ESW1 QSRGT002AA on CP1, wire 0xD7) and VOLUME
		-- (VR1 5k B on CP2 -> CP1 R36 -> IC1 AD3, wire 0xD3).
		--
		-- The dial is an INFINITE relative encoder: only its CHANGES reach the
		-- firmware, so the wheel is dragged in a circle and the DRAG ADJUSTER is
		-- nudged notch by notch.  It cannot be the same field as CP_DIAL: an analog
		-- field's only Lua write path, set_value(), latches m_use_adjoverride and
		-- detaches the field from the input system for good.  wsa1_cpanel.cpp sums
		-- the wrap-aware delta of both.
		--
		-- VOLUME is a plain absolute pot, so a vertical drag over the knob is enough.
		-- ⚠ Felipe's drawn pointer does NOT turn with it: a MAME layout item can be
		-- moved by a Lua bounds callback but not rotated, and inventing a second
		-- orbiting marker would contradict the drawing.  The value is visible in the
		-- machine's own display, and in MAME's slider menu.
		file:set_resolve_tags_callback(function()
			for vname, view in pairs(file.views) do
				if view.items["data_wheel"] ~= nil and view.items["data_wheel_finger"] ~= nil then
					add_rotary_knob(view, "data_wheel", "data_wheel_finger",
										"cpanel:CP_DIAL_DRAG", "cpanel:CP_DIAL")
				end
				if view.items["volume_knob"] ~= nil then
					add_simplecounter_knob(view, "volume_knob", "cpanel:CP_VOLUME", 1.0)
				end
				install_slider_callbacks(view)
			end
		end)
		return { frame = function() poll_rotary_wheels(); follow_rotary_values() end }''')
    out.append('\t]]></script>')
    out.append('</mamelayout>')
    return '\n'.join(out) + '\n'


def preview(path):
    """Compose the artwork with the label boxes drawn on top, for eyeballing."""
    art = Art()
    lbl = labels(art)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="500" '
             'viewBox="0 0 1600 500">',
             '<g transform="scale(%.9f)">' % geo.SCALE]
    root = ET.parse(ART).getroot()
    for parent in list(root.iter()):
        for ch in list(parent):
            if ch.tag == SVG + 'text':
                parent.remove(ch)
    strip_ns(root)
    inner = ser(root)
    inner = inner[inner.index('>') + 1:inner.rindex('</')]
    parts.append(inner)
    parts.append('</g>')
    for r in lbl:
        parts.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="none" '
                     'stroke="#ff00ff" stroke-width="0.4"/>' % (r['x'], r['y'], r['w'], r['h']))
        anchor = {0: 'middle', 1: 'start', 2: 'end'}[r['align']]
        cx = {0: r['x'] + r['w'] / 2, 1: r['x'], 2: r['x'] + r['w']}[r['align']]
        # mimic MAME: glyph height = bounds height, squeezed horizontally to fit
        parts.append('<text x="%.2f" y="%.2f" font-size="%.2f" text-anchor="%s" '
                     'textLength="%.2f" lengthAdjust="spacingAndGlyphs" '
                     'font-family="DejaVu Sans" fill="#%02x%02x%02x">%s</text>'
                     % (cx, r['y'] + r['h'] * 0.80, r['h'] * 0.86, anchor, r['w'],
                        int(r['rgb'][0] * 255), int(r['rgb'][1] * 255), int(r['rgb'][2] * 255),
                        esc(r['text'])))
    parts.append('</svg>')
    open(path, 'w').write('\n'.join(parts))
    print('preview -> %s' % path)


CPANEL = os.path.join(ROOT, "src", "mame", "matsushita", "wsa1_cpanel.cpp")

# Rack positions on a WIRED segment that carry no switch: prom_a 0xF95088 stores
# 0x0000 there, and the parts list has no S-number for them.
NOT_FITTED = ({(2, 7)} | {(7, b) for b in range(4, 8)}
              | {(8, b) for b in range(2, 8)} | {(9, b) for b in range(5, 8)})


def check_ports():
    """The legends live in BUTTONS above and are copied into wsa1_cpanel.cpp's
    PORT_NAMEs.  This is the guard against the two drifting apart."""
    want = {(seg, mask.bit_length() - 1): lg for seg, mask, ids, lg, tier in BUTTONS}
    src = open(CPANEL).read()
    bad = 0
    seen = set()
    for m in re.finditer(r'PORT_NAME\("Panel SEG(\d+) SW(\d+)([^"]*)"\)', src):
        seg, bit, tail = int(m.group(1)), int(m.group(2)), m.group(3)
        seen.add((seg, bit))
        if (seg, bit) in want:
            if not tail.startswith(' (rack: %s' % want[(seg, bit)]):
                print('MISMATCH SEG%d/SW%d: cpp has "%s", table says "%s"'
                      % (seg, bit, tail.strip(), want[(seg, bit)]))
                bad += 1
        elif (seg, bit) in NOT_FITTED:
            if 'not fitted' not in tail:
                print('SEG%d/SW%d should be marked "not fitted" on the rack' % (seg, bit))
                bad += 1
        elif seg in (6, 10):
            pass                      # SX-WSA1 keyboard only; no rack legend exists
        else:
            print('SEG%d/SW%d is neither in the table nor marked not fitted' % (seg, bit))
            bad += 1
    missing = set(want) - seen
    if missing:
        print('no PORT_NAME for %s' % sorted(missing))
        bad += len(missing)
    print('%d PORT_NAMEs checked against %d table rows, %d problems'
          % (len(seen), len(want), bad))
    return bad


if __name__ == '__main__':
    if '--check-ports' in sys.argv:
        raise SystemExit(1 if check_ports() else 0)
    if '--preview' in sys.argv:
        preview(sys.argv[sys.argv.index('--preview') + 1])
        raise SystemExit(0)
    text = build()
    if '--check' in sys.argv:
        cur = open(OUT).read() if os.path.exists(OUT) else ''
        if cur != text:
            sys.exit('%s is STALE -- re-run tools/gen_wsa1r_lay.py' % OUT)
        if check_ports():
            sys.exit('wsa1_cpanel.cpp PORT_NAMEs disagree with the table')
        print('%s is up to date (%d bytes)' % (OUT, len(text)))
        raise SystemExit(0)
    open(OUT, 'w').write(text)
    print('wrote %s (%d bytes, %d buttons, %d lamps, %d labels)'
          % (OUT, len(text), len(BUTTONS), len(LAMPS), len(labels(Art()))))
