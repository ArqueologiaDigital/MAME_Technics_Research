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
import math
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


_NSDECL = re.compile(r'\s+xmlns(?::xlink)?="[^"]*"')


def ser(el):
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    return ET.tostring(el, encoding='unicode')


def shape_svg(art, ids, x0u, y0u, wu, hu, wpx, hpx, dark=False):
    """One control, in its OWN coordinates: bbox origin rebased to 0,0.

    kn5000.lay declares each shape once in local coordinates and places it with
    <bounds>; a shape cropped out of the artwork by an absolute viewBox cannot
    be shared, because two copies of the same key differ in every number.

    Rebasing is also strictly MORE accurate.  MAME rasterises through nanosvg in
    float32 (rendlay.cpp:2083), and the artwork's absolute coordinates run to
    ~350 user units, where a float32 ULP is already an appreciable fraction of
    the sub-pixel position the antialiaser needs.  Feeding nanosvg numbers near
    zero instead moves each edge by up to 26/255 of a level -- always towards
    the exact answer.  notes/wsa1-probes/nsvg_hash.c measures it.

    The rebase is a pure translation folded into each shape's own matrix, so it
    carries the userSpaceOnUse gradients with it: nanosvg multiplies a gradient
    by the referencing shape's transform (nanosvg.h nsvg__createGradient), the
    same rule SVG itself states."""
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
        m = (m[0], m[1], m[2], m[3], m[4] - x0u, m[5] - y0u)
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
    # ET.tostring() stamps xmlns on the root of EVERY subtree it serialises, so
    # each copied gradient and path carried its own declaration while the <svg>
    # wrapper written here carried none.  Declaring them once, on the wrapper,
    # is 3.4 KB smaller and makes each CDATA a standalone-valid SVG, which until
    # now it only was by accident.
    body = _NSDECL.sub('', ''.join(body))
    d = _NSDECL.sub('', d)
    return ('<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'width="%.3f" height="%.3f" viewBox="0 0 %.6f %.6f">'
            '<defs>%s</defs>%s</svg>'
            % (wpx, hpx, wu, hu, d, body))


def control_images(art, ids, pressable=True):
    """One control: its <image> bodies in local coordinates, its bbox, and the
    signature that says which other controls are the same key.

    The images are returned separately from the <element> wrapper because the
    wrapper is now written ONCE PER DISTINCT SHAPE, not once per control."""
    x, y, w, h = art.bbox_px(ids)
    x0u, y0u = x / geo.SCALE, y / geo.SCALE
    wu, hu = w / geo.SCALE, h / geo.SCALE
    imgs = []
    if pressable:
        # The pressed state used to be the WHOLE unpressed drawing written out a
        # second time with a 34%-black copy of the shapes laid over it -- one
        # such copy per key, and the largest duplication left in the file.  MAME
        # will draw that wash itself: a component with no <bounds> covers the
        # element (rendlay.cpp:990), and an <image> with no state= draws in
        # every state (rendlay.cpp:3141).
        #
        # That says the same thing only where the wash is UNIFORM.  A control
        # drawn from ONE shape washes evenly, and the substitution measures
        # within 1/255 (3/255 for the two round keys, whose <disk> edge
        # antialiases a little differently).  The ten LCD soft keys are drawn
        # from TWO overlapping shapes and the old code darkens each in turn, so
        # their centre lands at 1-0.66^2 = 56% and their border at 34%.  That is
        # an artefact of how the darkening was built rather than a decision, but
        # it is the artefact currently on screen, so they keep the two-image
        # form and go on looking exactly as they do now.
        base = shape_svg(art, ids, x0u, y0u, wu, hu, w, h, dark=False)
        if len(ids) == 1:
            kind = geo.shape_points(art.by_id[ids[0]])[1]
            tag = 'disk' if kind == 'ellipse' else 'rect'
            imgs.append('\t\t<image><data><![CDATA[%s]]></data></image>' % base)
            imgs.append('\t\t<%s state="1">%s</%s>' % (tag, WASH, tag))
        else:
            dk = shape_svg(art, ids, x0u, y0u, wu, hu, w, h, dark=True)
            svg = base[:-len('</svg>')] + dk[dk.index('</defs>') + len('</defs>'):]
            imgs.append('\t\t<image state="0"><data><![CDATA[%s]]></data></image>' % base)
            imgs.append('\t\t<image state="1"><data><![CDATA[%s]]></data></image>' % svg)
    else:
        imgs.append('\t\t<image><data><![CDATA[%s]]></data></image>'
                    % shape_svg(art, ids, x0u, y0u, wu, hu, w, h))
    return imgs, (x, y, w, h), shape_signature(art, ids, x0u, y0u)


# ------------------------------------------------- one shape, many instances
#
# Felipe drew the panel by duplicating a key and dragging the copy, so the 58
# buttons are only ten DISTINCT keys.  Recognising the copies cannot be done on
# the SVG text: Inkscape gives every copy its own ids, writes the attributes in
# a different order, spells the same rectangle "v -6.61458 z" in one copy and
# "V 41.39302 Z" in the next, and leaves each copy's absolute coordinates
# cancelled by its own transform.  Two copies of one key share no numbers at
# all.
#
# So a key is fingerprinted by its GEOMETRY, after the transform is applied and
# the bbox origin is subtracted: the outline as points, the paint, and the
# gradient resolved to local endpoints and stops.  What survives is the drawing
# itself, which is the thing that has to match.
#
# The copies still disagree in the sixth decimal -- Inkscape writes a gradient
# scale as 1.1940374 here and 1.1940531 there, a stroke width as 0.264583 or
# 0.264584.  The differences that MATTER are three orders of magnitude larger:
# the two rows of under-LCD keys really do carry different gradient ramps
# (1.2046874 against 1.2364906, a 2.6% difference visible side by side).  One
# part in a thousand sits 26x above the largest rounding artefact measured and
# 26x below the smallest real difference, so nothing rides on its exact value.
# notes/wsa1-probes/wsa1r_lay_shape_classes.py re-measures both bounds.

# The ten keys.  Each is named after the artwork id of the copy the generator
# reaches first, so the name is pinned to Felipe's drawing rather than to the
# order of the BUTTONS table.  A shape that matches no entry is a HARD ERROR:
# it means the artwork changed, and a human should find out whether a key
# really grew a new look or merely drifted out of tolerance.
SHAPE_NAMES = {
    "path244": ("mode_button",
                "42x25 key: the PLAY/EDIT MODE pair, the four MENU keys, COMPARE"),
    "path240": ("bank_button",
                "the four BANK keys -- the same key as mode_button, drawn 0.9% "
                "larger in the artwork, so it is kept as its own shape rather "
                "than stretched into these bounds"),
    "path252": ("numeric_button",
                "number pad, the keys drawn at 11.1125 x 4.4979 user units"),
    "path254": ("numeric_button_large",
                "number pad, the keys drawn 0.9% larger -- the same key, second "
                "copy family in the drawing"),
    "path94":  ("under_lcd_button_top",
                "the upper row under the LCD, and PAGE up: gradient ramp 1.2047"),
    "path45":  ("under_lcd_button_bottom",
                "the lower row under the LCD, and PAGE down: a visibly different "
                "ramp, 1.2365 against the upper row's 1.2047"),
    "path16":  ("lcd_soft_key",
                "the ten LCD soft keys, five down each side of the screen"),
    "path267": ("wide_button", "-1, +1 and EXIT"),
    "circle196":  ("realtime_creator_button", "REALTIME CREATOR 1~6"),
    "ellipse228": ("realtime_creator_reset_button", "REALTIME CREATOR RESET"),
}

# The marks the DRAWING repeats, as opposed to the keys.  Same naming rule as
# SHAPE_NAMES: the artwork id of the first instance, so that renaming a shape
# in Inkscape cannot silently rename a layout element, and an unrecognised
# repeat stops the generator instead of appearing as "shape7".
#
# The third field says whether the mark is actually LIFTED, and that is a
# measured decision, not a taste.  A mark drawn inside the backdrop is
# rasterised as part of one 1600x500 image and lands at whatever sub-pixel
# phase it has; lifted, it is rasterised into its own integer-pixel box and
# that phase is quantised away.  How much this costs does not follow the mark's
# size -- it follows how much hard-edged contrast the mark carries.  Measured
# against the panel MAME draws from the original file:
#
#     lcd_soft_key_marker_left    maxdelta  25/255   mean 1.5    LIFT
#     lcd_soft_key_marker_right   maxdelta  26/255   mean 2.0    LIFT
#     menu_rule                   maxdelta   5/255   mean 0.0    LIFT
#     rack_ear_slot_right         maxdelta  64/255   mean 4.7    keep
#     rack_ear_slot_left          maxdelta  65/255   mean 5.2    keep
#     volume_scale_dot            maxdelta 102/255   mean 12.9   keep
#
# The first three sit inside the envelope the keys already spend (26/255 on one
# antialiased border row).  A 3x3 dot moving 40% of full scale does not, and no
# amount of tidiness is worth repainting Felipe's drawing, so the ear slots and
# the volume scale stay in the backdrop where they render exactly as before.
DECOR_NAMES = {
    "path99":     ("lcd_soft_key_marker_left",
                   "the arrow beside an LCD soft key, left column", True),
    "path114":    ("lcd_soft_key_marker_right",
                   "the arrow beside an LCD soft key, right column", True),
    "path1":      ("menu_rule",
                   "one of the two rules flanking the MENU legend", True),
    "ellipse209": ("volume_scale_dot",
                   "one of the eleven dots ringing the VOLUME knob", False),
    "path40":     ("rack_ear_slot_left", "a mounting slot in the left rack ear", False),
    "path41":     ("rack_ear_slot_right", "a mounting slot in the right rack ear", False),
    "path291":    ("mode_rule", "the rule drawn over PLAY MODE and over EDIT MODE", False),
    "ellipse193": ("rubber_foot", "one of the two feet showing below the panel", False),
}
# mode_rule and rubber_foot would be refused by the z-order guard anyway; they
# are marked False as well so the reason reads the same for every entry.

WASH = '<color red="0.0" green="0.0" blue="0.0" alpha="0.34"/>'

SHAPE_TOL = 1e-3

_PAINT = ('fill', 'stroke', 'stroke-width', 'fill-opacity', 'stroke-opacity',
          'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray')


def _style_of(el):
    st = dict(re.findall(r'([a-z-]+)\s*:\s*([^;]+)', el.get('style', '')))
    for k in _PAINT:                      # presentation attributes lose to style
        if el.get(k) is not None:
            st.setdefault(k, el.get(k))
    return {k: v.strip() for k, v in st.items()}


def _stops(art, node):
    """The stop list, following xlink:href the way SVG inherits it."""
    seen = set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        stops = node.findall(SVG + 'stop')
        if stops:
            out = []
            for st in stops:
                sty = dict(re.findall(r'([a-z-]+)\s*:\s*([^;]+)', st.get('style', '')))
                out.append((float(st.get('offset', 0)),
                            sty.get('stop-color', st.get('stop-color', '#000')).strip(),
                            float(sty.get('stop-opacity', st.get('stop-opacity', 1)))))
            return out
        href = node.get(XLINK + 'href') or node.get('href') or ''
        node = art.by_id.get(href[1:]) if href.startswith('#') else None
    return []


def _grad_key(art, gid, m):
    """A gradient as LOCAL geometry plus stops -- id and spelling discarded."""
    node = art.by_id.get(gid)
    if node is None:
        return ['grad?'], []
    tag = node.tag.replace(SVG, '')
    units = node.get('gradientUnits', 'objectBoundingBox')
    full = geo.mat_mul(m, geo.parse_transform(node.get('gradientTransform')))
    skel, nums = [tag, units], []
    num = lambda k, d='0': float(re.sub('[^0-9.eE+-]', '', node.get(k, d)) or d)
    if tag == 'linearGradient':
        pts = [(num('x1'), num('y1')), (num('x2'), num('y2'))]
        if units == 'userSpaceOnUse':
            pts = [geo.apply(full, x, y) for x, y in pts]
        # What a linear gradient DOES is t(p) = (p-P1).d / |d|^2, so two of them
        # paint identically when d matches and P1.d matches.  Sliding the axis
        # sideways -- which Inkscape does to every copy, the ramp being vertical
        # and its x therefore arbitrary -- must not read as a different key.
        (x1, y1), (x2, y2) = pts
        dx, dy = x2 - x1, y2 - y1
        q = dx * dx + dy * dy
        nums += [dx, dy, (x1 * dx + y1 * dy) / q if q else 0.0]
    else:
        pts = [(num('cx', '0.5'), num('cy', '0.5')), (num('fx', node.get('cx', '0.5')),
                                                      num('fy', node.get('cy', '0.5')))]
        nums.append(num('r', '0.5'))
        for x, y in pts:
            if units == 'userSpaceOnUse':
                x, y = geo.apply(full, x, y)
            nums += [x, y]
    for off, col, op in _stops(art, node):
        skel.append(col)
        nums += [off, op]
    return skel, nums


def shape_signature(art, ids, x0u, y0u):
    """What this control IS: outline, paint and gradients, in local units."""
    skel, nums = [], []
    for i in ids:
        el = art.by_id[i]
        m = art.xform[el]
        m = (m[0], m[1], m[2], m[3], m[4] - x0u, m[5] - y0u)
        pts, kind = geo.shape_points(el)
        skel.append(kind or '?')
        if kind == 'ellipse':
            cx, cy, rx, ry = pts[0]
            ox, oy = geo.apply(m, cx, cy)
            nums += [ox, oy, math.hypot(m[0] * rx, m[2] * ry),
                     math.hypot(m[1] * rx, m[3] * ry)]
        elif pts:
            for p in pts:
                ox, oy = geo.apply(m, p[0], p[1])
                nums += [ox, oy]
        st = _style_of(el)
        for k in _PAINT:
            v = st.get(k)
            if v is None:
                continue
            g = re.match(r'url\(#([^)]+)\)', v)
            if g:
                gs, gn = _grad_key(art, g.group(1), m)
                skel.append(k + '=' + '/'.join(gs))
                nums += gn
                continue
            try:
                nums.append(float(v))
                skel.append(k + '=#')
            except ValueError:
                skel.append('%s=%s' % (k, v))
    return ('|'.join(skel), tuple(nums))


def same_shape(a, b):
    """Same drawing, and every number within SHAPE_TOL relative."""
    if a[0] != b[0] or len(a[1]) != len(b[1]):
        return False
    for u, v in zip(a[1], b[1]):
        if abs(u - v) > SHAPE_TOL * max(1.0, abs(u), abs(v)):
            return False
    return True


_DRAWABLE = {'path', 'rect', 'circle', 'ellipse'}


def root_drawables(art):
    """Every drawable in the artwork, in document = paint order."""
    out = []

    def walk(node):
        for ch in node:
            t = ch.tag.replace(SVG, '')
            if t in ('defs', 'metadata', 'namedview', 'clipPath'):
                continue
            if t in _DRAWABLE:
                out.append(ch)
            else:
                walk(ch)

    walk(art.root)
    return out


def repeated_decor(art, extracted):
    """Marks the drawing itself repeats, clustered the same way the keys are.

    The static art is not only a backdrop: it carries the arrow beside each of
    the ten LCD soft keys, the eleven dots ringing the VOLUME knob, the rack-ear
    slots and the feet, each drawn out once per instance.  Anything that appears
    more than once is lifted into a single <element> and placed, exactly as a
    key is; anything unique is left in the backdrop where it was.

    A candidate is either a <g> holding nothing but drawables -- the arrows are
    three paths apiece -- or a lone drawable.  Returns
    [(name, what, [(ids, bounds), ...]), ...] in document order."""
    cands = []

    def walk(node):
        kids = [c for c in node if c.tag.replace(SVG, '')
                not in ('defs', 'metadata', 'namedview')]
        draw = [c for c in kids if c.tag.replace(SVG, '') in _DRAWABLE]
        groups = [c for c in kids if c.tag == SVG + 'g']
        if node.tag == SVG + 'g' and draw and not groups:
            ids = [c.get('id') for c in draw if c.get('id')]
            if ids and not (set(ids) & extracted):
                cands.append(ids)
                return
        for c in draw:
            i = c.get('id')
            if i and i not in extracted:
                cands.append([i])
        for g in groups:
            walk(g)

    walk(art.root)

    clusters = []
    for ids in cands:
        try:
            x, y, w, h = art.bbox_px(ids)
        except SystemExit:
            continue                       # no geometry: leave it in the art
        sig = shape_signature(art, ids, x / geo.SCALE, y / geo.SCALE)
        for cl in clusters:
            if same_shape(cl[0], sig):
                cl[1].append((ids, (x, y, w, h)))
                break
        else:
            clusters.append((sig, [(ids, (x, y, w, h))]))

    # A mark may only be lifted if nothing DRAWN LATER covers it.  Lifting moves
    # a shape from wherever it sat in the drawing to on top of the whole
    # backdrop, and the two feet are drawn early and then half hidden by the
    # panel body: lifted, they climb out from behind it and sit proud of the
    # front panel.  Document order is the z order, so anything later whose bbox
    # touches the candidate disqualifies the whole cluster.
    order, boxes = {}, {}
    for n, el in enumerate(root_drawables(art)):
        i = el.get('id')
        if not i:
            continue
        order[i] = n
        try:
            boxes[i] = art.bbox_px([i])
        except SystemExit:
            pass

    def overdrawn(ids, box):
        """Would lifting these shapes change what is painted over what?

        The rewritten panel paints backdrop, then the lifted marks, then the
        screen, the keys, the lamps and the legends.  So a mark changes places
        with two kinds of neighbour: a BACKDROP shape that used to come after it
        (which would now end up underneath), and a KEY or lamp that used to come
        before it (which would now end up on top).  Either way the drawing
        changes, and the mark stays where it is."""
        first = min((order.get(i, 1 << 30) for i in ids), default=0)
        last = max((order.get(i, -1) for i in ids), default=-1)
        x, y, w, h = box
        for i, n in order.items():
            if i in ids or i not in boxes:
                continue
            later_backdrop = n > last and i not in extracted
            earlier_control = n < first and i in extracted
            if not (later_backdrop or earlier_control):
                continue
            bx, by, bw, bh = boxes[i]
            if bx < x + w and x < bx + bw and by < y + h and y < by + bh:
                return i
        return None

    out = []
    for sig, members in clusters:
        if len(members) < 2:
            continue
        blocked = [(ids, overdrawn(ids, box)) for ids, box in members]
        blocked = [(ids, o) for ids, o in blocked if o]
        if blocked:
            continue                   # left in the backdrop, where its z is
        first = members[0][0][0]
        if first not in DECOR_NAMES:
            sys.exit('the artwork repeats a mark this generator cannot name: %s '
                     '(x%d, first at %.0f,%.0f).  Add it to DECOR_NAMES.'
                     % (first, len(members), members[0][1][0], members[0][1][1]))
        name, what, lift = DECOR_NAMES[first]
        if lift:
            out.append((name, what, members))
    return out


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
        rows.append(dict(name=None, text=s, x=left, y=top, w=w, h=h,
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
    #
    # PASS 1: lift every button out of the drawing, in local coordinates.
    # PASS 2: group the ones that are the same key.
    # PASS 3: write each key ONCE, then place it wherever the panel has one.
    elems, places = [], []

    lifted = []
    for seg, mask, ids, legend, tier in BUTTONS:
        imgs, box, sig = control_images(art, ids)
        lifted.append(dict(ids=ids, imgs=imgs, box=box, sig=sig,
                           seg=seg, mask=mask, legend=legend, tier=tier))
        extracted.update(ids)

    shapes = []                      # [{sig, name, members:[lifted...]}]
    for c in lifted:
        for sh in shapes:
            if same_shape(sh['sig'], c['sig']):
                sh['members'].append(c)
                break
        else:
            shapes.append(dict(sig=c['sig'], members=[c], first=c))

    unnamed = [sh['first']['ids'][0] for sh in shapes
               if sh['first']['ids'][0] not in SHAPE_NAMES]
    if unnamed:
        sys.exit('the artwork now has button shapes this generator cannot name: %s\n'
                 'add them to SHAPE_NAMES, or find out why a key stopped matching '
                 'its family (notes/wsa1-probes/wsa1r_lay_shape_classes.py says which)'
                 % ', '.join(unnamed))

    for sh in shapes:
        name, what = SHAPE_NAMES[sh['first']['ids'][0]]
        sh['name'] = name
        legends = '; '.join(m['legend'] for m in sh['members'])
        elems.append('\t<element name="%s"><!-- %s\n\t     x%d: %s -->\n%s\n\t</element>'
                     % (name, cmt(esc(what)), len(sh['members']), cmt(esc(legends)),
                        '\n'.join(sh['first']['imgs'])))
        for m in sh['members']:
            x, y, w, h = m['box']
            places.append('\t\t<element ref="%s" inputtag="cpanel:CP_SEG%d" inputmask="0x%02x">'
                          '<!-- SEG%d/SW%d  %s  [%s] -->'
                          '<bounds x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></element>'
                          % (name, m['seg'], m['mask'], m['seg'], m['mask'].bit_length() - 1,
                             cmt(esc(m['legend'])), m['tier'], x, y, w, h))
    places.sort(key=lambda p: (int(re.search(r'SEG(\d+)/SW', p).group(1)),
                               int(re.search(r'/SW(\d+)', p).group(1))))

    # knobs (no press state).  Each is unique, so each is its own element; they
    # go through control_images for the local-coordinate rebase all the same.
    for ids, iid, comment in KNOBS:
        imgs, (x, y, w, h), _ = control_images(art, ids, pressable=False)
        elems.append('\t<element name="%s"><!-- %s -->\n%s\n\t</element>'
                     % (iid, cmt(esc(comment)), '\n'.join(imgs)))
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

    # ---- repeated decoration -------------------------------------------
    # The backdrop repeats marks too, and they are shared on the same terms as
    # the keys: one element, N placements.  Anything unique stays in the art.
    decor_elems, decor_places = [], []
    for name, what, members in repeated_decor(art, extracted):
        ids0 = members[0][0]
        imgs, _, _ = control_images(art, ids0, pressable=False)
        decor_elems.append('\t<element name="%s"><!-- %s ; drawn %d times -->\n%s\n\t</element>'
                           % (name, cmt(esc(what)), len(members), '\n'.join(imgs)))
        for ids, (x, y, w, h) in members:
            decor_places.append('\t\t<element ref="%s">'
                                '<bounds x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></element>'
                                % (name, x, y, w, h))
            extracted.update(ids)

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
            # <clipPath> goes too.  nanosvg -- the ONLY rasteriser the layout
            # engine has (rendlay.cpp:2083) -- does not implement clipping at
            # all, so the drawing MAME shows is already the unclipped one and
            # these 19 blocks are 3.8 KB that nothing ever reads.  Twelve of
            # them are the same A4 page rectangle, written out twelve times.
            if (i in extracted) or ch.tag == SVG + 'text' \
                    or ch.tag == SVG + 'clipPath' \
                    or ch.tag.startswith('{http://sodipodi'):
                parent.remove(ch)
    for el in root.iter():
        el.attrib.pop('clip-path', None)

    # Now sweep <defs>.  Every control lifted out above took a COPY of its
    # gradients with it (shape_svg emits them inline), but the originals stayed
    # behind with nothing left to paint.  Walk url(#..) and xlink:href from what
    # actually survives, close the set, and drop the rest.
    defs_nodes = [d for d in root.iter() if d.tag == SVG + 'defs']
    defined = {}
    for d in defs_nodes:
        for ch in d:
            if ch.get('id'):
                defined[ch.get('id')] = (d, ch)

    def refs_of(el):
        blob = ' '.join(v for v in el.attrib.values())
        out = set(re.findall(r'url\(#([^)]+)\)', blob))
        for k in ('{http://www.w3.org/1999/xlink}href', 'href'):
            v = el.get(k)
            if v and v.startswith('#'):
                out.add(v[1:])
        return out

    frontier = set()
    for el in root.iter():
        if any(el is c for _, c in defined.values()) or el.tag == SVG + 'defs':
            continue
        if any(el in list(d.iter()) for d in defs_nodes):
            continue
        frontier |= refs_of(el)
    alive = set()
    while frontier:
        i = frontier.pop()
        if i in alive or i not in defined:
            continue
        alive.add(i)
        node = defined[i][1]
        for sub in node.iter():
            frontier |= refs_of(sub)
    for i, (d, ch) in defined.items():
        if i not in alive:
            d.remove(ch)

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
    out.extend(decor_elems)
    out.append('')

    # ---- label elements ------------------------------------------------
    # A legend is the same element wherever it is drawn: five of Felipe's 56
    # are repeats (SOUND, COMBI and MODE each appear under both PLAY and EDIT,
    # 1 and 2 under both USER banks).  Naming them after their own text also
    # says rather more at the point of use than lbl1..lbl56 did.
    seen_lbl, used = {}, {}
    for r in lbl:
        key = (r['text'], r['align'], r['rgb'])
        if key not in seen_lbl:
            # Spell the signs out.  Squeezing them away turns "+1" and "-1"
            # into "1", which then collides with the real "1" legend and comes
            # back as lbl_1_2 and lbl_1_3 -- names that read as variants of the
            # wrong key.  A hyphen BETWEEN alphanumerics is a range, not a
            # minus ("1-6"), so it stays a separator.
            t = r['text'].replace('+', '_PLUS_')
            t = re.sub(r'(?<![A-Za-z0-9])-|-(?![A-Za-z0-9])', '_MINUS_', t)
            base = 'lbl_' + (re.sub(r'[^A-Za-z0-9]+', '_', t).strip('_').upper()
                             or 'TEXT')
            if base in used:
                sys.exit('two different legends both want the element name %s '
                         '(%r and %r) -- give one of them a distinct name'
                         % (base, used[base], r['text']))
            used[base] = r['text']
            seen_lbl[key] = base
            out.append('\t<element name="%s"><text string="%s" align="%d">'
                       '<color red="%.2f" green="%.2f" blue="%.2f"/></text></element>'
                       % (seen_lbl[key], esc(r['text']), r['align'], *r['rgb']))
        r['name'] = seen_lbl[key]
    out.append('')

    # ---- group ---------------------------------------------------------
    sx, sy, sw, sh = art.bbox_px([SCREEN_ID])
    out.append('\t<group name="panel">')
    out.append('\t\t<bounds left="0" right="%d" top="0" bottom="%d"/>' % (VIEW_W, VIEW_H))
    out.append('\t\t<element ref="vector_art"><bounds x="0" y="0" width="%d" height="%d"/></element>'
               % (VIEW_W, VIEW_H))
    out.append('')
    out.append('\t\t<!-- the marks the drawing repeats, on top of the backdrop they')
    out.append('\t\t     were lifted out of and under everything else -->')
    out.extend(decor_places)
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
    cx, cy, cw, ch = art.bbox_px(['rect135'])
    out.append('\t\t<bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f"/>'
               % (cx, cy, cw, ch))
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
