#!/usr/bin/env python3
# Generator for src/mame/layout/kn6000.lay -- the SX-KN6000 / SX-KN6500 control panel.
#
# WHY THIS EXISTS
# ---------------
# kn6000_cpanel_device carries the correct KN6000 button matrix (all 150 switch bits, cross-checked
# against the service manual), but the driver was still installing layout_kn7000 as the default
# artwork.  Every clickable element on screen therefore sat at a KN7000 position, carried a KN7000
# legend, and pointed at a KN7000 matrix cell -- so clicking "PIANO" sent the KN7000's PIANO cell,
# which is a different function on a KN6000.  The matrix was right and the artwork was wrong.
#
# WHERE THE GEOMETRY COMES FROM
# -----------------------------
# The SX-KN6000 service manual (technics_sx-kn6000-sm.pdf) reproduces the owner's-manual
# "Controls and functions" top view across pages 5 and 6 -- a two-page spread of the whole panel,
# every block outlined and every switch silkscreened.  Page 5 is the left half (RHYTHM GROUP,
# SOUND ARRANGER, AUTO PLAY CHORD, the LCDL soft keys, POWER/DEMO, SOUND CONTROLLER trackball,
# MAIN + APC/SEQUENCER VOLUME, PERFORMANCE PADS, MUSIC STYLE ARRANGER / ONE TOUCH PLAY /
# SPLIT POINT, VARIATION & MSA, FADE IN/OUT, FILL IN, INTRO & ENDING, TAP TEMPO, SYNCHRO & BREAK,
# START/STOP, PITCH BEND/MODULATION); page 6 is the right half (DISPLAY, LCDR soft keys, the 16
# MUTE rockers, PAGE/DISPLAY HOLD/EXIT, SOUND GROUP, PART EFFECT, TEMPO/PROGRAM, MUSIC STYLIST /
# FAVORITES, TRANSPOSE, R1/R2 OCTAVE, PART SELECT, CONDUCTOR, SOLO, TECHNI-CHORD, GLOBAL EFFECT +
# MIC VOLUME, PANEL MEMORY, SEQUENCER, PROGRAM MENUS, DISK).
#
# The drawing is a perspective view of a two-tier panel.  Like the KN7000 layout, this one does NOT
# reproduce the perspective: it flattens the instrument into an upper deck (screen_block: the LCD,
# its flanking soft keys and the two 4x4 category grids that sit either side of it) and a lower deck
# split into three blocks left-to-right.  Within each block the relative arrangement, grouping and
# silkscreen wording follow the manual drawing.
#
# The manual's reading order independently CONFIRMS the driver's matrix: the 16 RHYTHM GROUP buttons
# read row-major (8&16 BEAT, POP, BALLAD, ROCK'N'ROLL & BLUES / SOUL & FUNK, MODERN DANCE, U.S. TRAD,
# COUNTRY / ...) land exactly on the 6/6/4 split across CPL_SEG0/1/2 bits 2-7, and the 16 SOUND GROUP
# buttons likewise on CPR_SEG0/1/2 bits 0-5.  The six PERFORMANCE PADS are drawn 1/2/3 over 4/5/6 and
# wire as three columns of (1,4), (2,5), (3,6) -- the manual's own correction to a naive reading.
#
# INPUT TAGS
# ----------
# Every clickable element binds "cpanel:CP{L,R}_SEG{n}" + the bit mask straight out of
# kn6000_cpanel.cpp's device_input_ports().  Those port names ARE the physical scan matrix, so the
# legend a button carries here and the cell it sends are the same fact.
#
# LEDS -- DELIBERATELY UNBOUND
# ----------------------------
# The KN6000 LED coordinate map (anode row x SEG column) is traced, but how it maps onto the
# [register][bit] pair the panel device actually receives is NOT confirmed against the firmware's
# LED frame builder (see notes/kn6000-panel-matrix.md).  Indicator dots are therefore DRAWN where
# the manual shows them but carry NO output name, so they stay dark.  They are placeholders, not
# claims.  The built-in "Panel SW & LED test" (manual p.22 sec 7.5) is the ground truth to bind
# against when someone does that work.
#
# ALSO OMITTED ON PURPOSE: the PITCH BEND / MODULATION wheels and the SOUND CONTROLLER trackball
# (no emulated control behind them -- the trackball's two switches RESET/MODE are drawn and bound,
# the ball itself is decorative), the CONTRAST trimmer (an analog part, not a matrix button), the
# POWER switch (drawn decoratively), and the keyboard bed.
import io, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lay_kit import *   # palette, E/TXTS registries, elem/two/label/P/L/panel_bg, pair_h, wrap2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "src", "mame", "layout", "kn6000.lay")

W      = 2880          # canvas width (screen block, and the 3 lower blocks at 960 each)
BLK_W  = 960
BLK_H  = 503
SCR_H  = 1000

# ---------------------------------------------------------------- element library
# Same visual vocabulary as the KN7000 layout (tools/gen_lay.py); sizes re-cut for this panel.
def _pill_body(w, h, fill, fd):
    sw = 1.5; r = (h - sw) / 2.0; i = sw / 2.0
    b = lambda f: (f'<rect stroke="{STROKE}" stroke-width="{sw}" fill="{f}" x="{i:.2f}" y="{i:.2f}" '
                   f'width="{w - sw:.2f}" height="{h - sw:.2f}" rx="{r:.2f}"/>')
    return b(fill), b(fd)

two("round_btn", 29, 29, f'<circle stroke="{STROKE}" fill="{BTN}" cx="14.5" cy="14.5" r="14"/>',
                         f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="14.5" cy="14.5" r="14"/>')
two("round_btn_big", 42, 42, f'<circle stroke="{STROKE}" fill="{BTN}" cx="21" cy="21" r="20.5"/>',
                             f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="21" cy="21" r="20.5"/>')
two("round_btn_silver", 42, 42, f'<circle stroke="{STROKE}" fill="{SILVER}" cx="21" cy="21" r="20.5"/>',
                                f'<circle stroke="{STROKE}" fill="{SILVER_D}" cx="21" cy="21" r="20.5"/>')
# square-ish buttons: the RHYTHM/SOUND GROUP keys and PART SELECT/CONDUCTOR are rounded rectangles
two("sq_btn", 44, 30, f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="42" height="28" rx="7"/>',
                      f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="42" height="28" rx="7"/>')
two("sq_btn_big", 52, 44, f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="50" height="42" rx="9"/>',
                          f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="50" height="42" rx="9"/>')
two("demo_btn", 42, 42,
    f'<circle stroke="{STROKE}" fill="#2c2c32" cx="21" cy="21" r="20.5"/><circle stroke="#4a4a50" stroke-width="0.5" fill="{BTN}" cx="21" cy="21" r="16"/>',
    f'<circle stroke="{STROKE}" fill="#1e1e23" cx="21" cy="21" r="20.5"/><circle stroke="#34343a" stroke-width="0.5" fill="{BTN_D}" cx="21" cy="21" r="16"/>')
two("red_led", 8, 8, '<circle cx="4" cy="4" r="3.5" fill="#3a0000"/>', '<circle cx="4" cy="4" r="3.5" fill="#ff2020"/>')
two("green_led", 8, 8, '<circle cx="4" cy="4" r="3.5" fill="#003a00"/>', '<circle cx="4" cy="4" r="3.5" fill="#20ff20"/>')
two("pill_md", 150, 44, *_pill_body(150, 44, SILVER, SILVER_D))
two("pill_start", 180, 60, *_pill_body(180, 60, "#4a5c5e", "#33454a"))
two("lcd_soft_key", 123, 34,
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{SILVER}" x="1" y="1" width="121" height="32" rx="3"/><line x1="28" y1="1" x2="28" y2="33" stroke="{STROKE}" stroke-width="1.5"/>',
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{SILVER_D}" x="1" y="1" width="121" height="32" rx="3"/><line x1="28" y1="1" x2="28" y2="33" stroke="{STROKE}" stroke-width="1.5"/>')
two("mute_up", 55, 77, f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{SILVER}" x="1" y="1" width="53" height="75" rx="3"/>',
                       f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{SILVER_D}" x="1" y="1" width="53" height="75" rx="3"/>')
two("mute_down", 55, 78, f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{SILVER}" x="1" y="1" width="53" height="76" rx="3"/>',
                         f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{SILVER_D}" x="1" y="1" width="53" height="76" rx="3"/>')
two("page_up", 50, 78, f'<path stroke="{STROKE}" stroke-width="1.5" fill="{SILVER}" d="M 2,77 V 26 A 24 24 0 0 1 26 2 A 24 24 0 0 1 48 26 V 77 Z"/>',
                       f'<path stroke="{STROKE}" stroke-width="1.5" fill="{SILVER_D}" d="M 2,77 V 26 A 24 24 0 0 1 26 2 A 24 24 0 0 1 48 26 V 77 Z"/>')
two("page_dn", 50, 78, f'<path stroke="{STROKE}" stroke-width="1.5" fill="{SILVER}" d="M 2,1 V 52 A 24 24 0 0 0 26 76 A 24 24 0 0 0 48 52 V 1 Z"/>',
                       f'<path stroke="{STROKE}" stroke-width="1.5" fill="{SILVER_D}" d="M 2,1 V 52 A 24 24 0 0 0 26 76 A 24 24 0 0 0 48 52 V 1 Z"/>')
# MUSIC STYLIST / FAVORITES: one disc split into an upper and a lower half (manual p.6)
two("disc_top", 96, 52, f'<path stroke="{STROKE}" stroke-width="1.5" fill="{SILVER}" d="M 2,50 A 46 46 0 0 1 94 50 Z"/>',
                        f'<path stroke="{STROKE}" stroke-width="1.5" fill="{SILVER_D}" d="M 2,50 A 46 46 0 0 1 94 50 Z"/>')
two("disc_bot", 96, 52, f'<path stroke="{STROKE}" stroke-width="1.5" fill="{SILVER}" d="M 2,2 A 46 46 0 0 0 94 2 Z"/>',
                        f'<path stroke="{STROKE}" stroke-width="1.5" fill="{SILVER_D}" d="M 2,2 A 46 46 0 0 0 94 2 Z"/>')
# PERFORMANCE PADS (KN5000/KN7000 shape, shared silhouette on this panel too)
two("msp_corner", 63, 39, f'<path stroke="{STROKE}" fill="{MSP}" d="M 62.5,0.5 C 40,2 18.8,5.2 0.5,9.7 V 38.5 H 62.5 Z"/>',
                          f'<path stroke="{STROKE}" fill="{MSP_D}" d="M 62.5,0.5 C 40,2 18.8,5.2 0.5,9.7 V 38.5 H 62.5 Z"/>')
two("msp_corner_r", 63, 39, f'<path transform="translate(63,0) scale(-1,1)" stroke="{STROKE}" fill="{MSP}" d="M 62.5,0.5 C 40,2 18.8,5.2 0.5,9.7 V 38.5 H 62.5 Z"/>',
                            f'<path transform="translate(63,0) scale(-1,1)" stroke="{STROKE}" fill="{MSP_D}" d="M 62.5,0.5 C 40,2 18.8,5.2 0.5,9.7 V 38.5 H 62.5 Z"/>')
two("msp_middle", 61, 40, f'<path stroke="{STROKE}" fill="{MSP}" d="M 30.1,0.5 C 20.1,0.5 10.2,0.9 0.5,1.5 V 39.5 H 60.5 V 1.6 C 50.5,0.9 40.3,0.5 30.1,0.5 Z"/>',
                          f'<path stroke="{STROKE}" fill="{MSP_D}" d="M 30.1,0.5 C 20.1,0.5 10.2,0.9 0.5,1.5 V 39.5 H 60.5 V 1.6 C 50.5,0.9 40.3,0.5 30.1,0.5 Z"/>')
two("tempo_knob", 100, 100,
    f'<circle cx="50" cy="50" r="48" fill="{SILVER}" stroke="{STROKE}" stroke-width="2"/><circle cx="50" cy="50" r="37" fill="{SILVER_D}" stroke="#828289"/>',
    f'<circle cx="50" cy="50" r="48" fill="{SILVER_D}" stroke="{STROKE}" stroke-width="2"/><circle cx="50" cy="50" r="37" fill="{SILVER_D}" stroke="#828289"/>')
elem("tempo_finger", f'<image><data><![CDATA[<svg width="16" height="16"><circle cx="8" cy="8" r="7" fill="#6e6e76" stroke="{STROKE}" stroke-width="1"/></svg>]]></data></image>')
elem("trackball", f'<image><data><![CDATA[<svg width="120" height="120"><circle cx="60" cy="60" r="58" fill="{PANEL2}" stroke="{STROKE}" stroke-width="2"/><circle cx="60" cy="60" r="44" fill="#3e3e46" stroke="#54545c" stroke-width="1.5"/><circle cx="60" cy="60" r="12" fill="{PANEL2}" stroke="#54545c"/></svg>]]></data></image>')
elem("power_sw", f'<image><data><![CDATA[<svg width="60" height="40"><rect x="1" y="1" width="58" height="38" rx="7" fill="{SILVER}" stroke="{STROKE}" stroke-width="1.5"/></svg>]]></data></image>')
elem("inv_rect", '<rect><color red="0" green="0" blue="0" alpha="0"/></rect>')
elem("fader_rail", '<rect><color red="0.13" green="0.13" blue="0.14"/></rect>')
elem("slider_knob", '<rect><bounds x="0" y="0" width="30" height="18"/><color red="0.34" green="0.34" blue="0.37"/></rect>'
                    '<rect><bounds x="2" y="8" width="26" height="2.5"/><color red="0.9" green="0.9" blue="0.92"/></rect>')
elem("hline", '<image><data><![CDATA[<svg width="100" height="3"><rect y="1" width="100" height="1.4" fill="#9a9a9c"/></svg>]]></data></image>')
elem("vline", '<image><data><![CDATA[<svg width="3" height="100"><rect x="1" width="1.4" height="100" fill="#9a9a9c"/></svg>]]></data></image>')
elem("screen_frame", f'<image><data><![CDATA[<svg width="1418" height="595"><rect x="3.5" y="3.5" width="1411" height="588" fill="none" stroke="{SILVER}" stroke-width="5"/><rect x="8" y="8" width="1402" height="579" fill="#050505" stroke="{STROKE}" stroke-width="2"/></svg>]]></data></image>')
panel_bg("bg_top", W, SCR_H, PANEL)
panel_bg("bg_blk", BLK_W, BLK_H, PANEL)

# ---------------------------------------------------------------- placement helpers
def hdr(out, text, x, y, w):
    """Group caption with the manual's flanking rule lines (e.g. --- SOUND ARRANGER ---)."""
    out.append(L(text, x, y, w, 13, TXTH))

def cell(out, x, y, name, tag, mask, dx=120, ref="round_btn", size=32, led=True, gap=13):
    """One labelled, bound button: legend line(s) above, indicator dot left of the legend."""
    lines = wrap2(name)
    lx = x - (dx - size) // 2 - 4
    for k, ln in enumerate(lines):
        out.append(L(ln, lx, y - gap - (len(lines) - 1 - k) * 10, dx - 2, 9))
    if led:
        out.append(P("red_led", lx + 2, y - gap - (len(lines) - 1) * 10 - 1, 8, 8))
    out.append(P(ref, x, y, size, size, tag=tag, mask=mask))

def fader(out, cx, y, h, port, l1, l2="VOLUME", lw=64):
    sid = port.lower(); x = cx - 15; kh = 18
    out.append(L(l1, cx - lw // 2, y - 24, lw, 9, TXTH))
    if l2: out.append(L(l2, cx - 24, y - 15, 48, 9, TXTH))
    out.append(P("fader_rail", cx - 3, y + kh // 2, 6, h - kh))
    out.append(f'\t\t<element id="{sid}_click" ref="inv_rect"><bounds x="{x}" y="{y}" width="30" height="{h}"/></element>')
    out.append(f'\t\t<element id="{sid}_knob" ref="slider_knob"><animate inputtag="{port}" inputmask="0xffff"/>'
               f'<bounds state="100" x="{x}" y="{y}" width="30" height="{kh}"/>'
               f'<bounds state="0" x="{x}" y="{y + h - kh}" width="30" height="{kh}"/></element>')

# ================================================================= SCREEN BLOCK (upper deck)
S = ['\t<group name="screen_block">', f'\t\t<bounds x="0" y="0" width="{W}" height="{SCR_H}"/>',
     P("bg_top", 0, 0, W, SCR_H), P("screen_frame", 690, 97, 1418, 595),
     '\t\t<screen index="0"><bounds x="759" y="154" width="1280" height="480"/></screen>']

# ---- RHYTHM GROUP: 4x4, manual reading order == the driver's 6/6/4 split over CPL_SEG0/1/2 b2..b7
RG = [("8 & 16 BEAT", "CPL_SEG0", "0x04"), ("POP", "CPL_SEG0", "0x08"),
      ("BALLAD", "CPL_SEG0", "0x10"), ("ROCK'N'ROLL & BLUES", "CPL_SEG0", "0x20"),
      ("SOUL & FUNK", "CPL_SEG0", "0x40"), ("MODERN DANCE", "CPL_SEG0", "0x80"),
      ("U.S. TRAD", "CPL_SEG1", "0x04"), ("COUNTRY", "CPL_SEG1", "0x08"),
      ("BIG BAND & SWING", "CPL_SEG1", "0x10"), ("JAZZ COMBO", "CPL_SEG1", "0x20"),
      ("MARCH & WALTZ", "CPL_SEG1", "0x40"), ("BALLROOM & SHOW TIME", "CPL_SEG1", "0x80"),
      ("LATIN", "CPL_SEG2", "0x04"), ("WORLD", "CPL_SEG2", "0x08"),
      ("CUSTOM", "CPL_SEG2", "0x10"), ("MEMORY LOAD", "CPL_SEG2", "0x20")]
hdr(S, "RHYTHM GROUP", 60, 42, 480)
S += [P("hline", 60, 56, 480, 3)]
for i, (nm, tg, mk) in enumerate(RG):
    cell(S, 80 + (i % 4) * 120, 110 + (i // 4) * 100, nm, tg, mk, dx=120, ref="sq_btn", size=44, gap=24)

# ---- SOUND ARRANGER / AUTO PLAY CHORD (drawn directly under the RHYTHM GROUP box, manual p.5)
hdr(S, "SOUND ARRANGER", 62, 546, 220); S += [P("hline", 62, 560, 220, 3)]
cell(S, 84, 596, "SET", "CPL_SEG2", "0x40", dx=100)
cell(S, 204, 596, "OFF/ON", "CPL_SEG2", "0x80", dx=100)
hdr(S, "AUTO PLAY CHORD", 302, 546, 220); S += [P("hline", 302, 560, 220, 3)]
cell(S, 324, 596, "MODE", "CPL_SEG3", "0x02", dx=100)
cell(S, 444, 596, "OFF/ON", "CPL_SEG3", "0x04", dx=100)

# ---- LCD soft keys: 5 down each side of the display.  Context-dependent, no silkscreen legend on
#      the real panel (the current screen labels them), so they are drawn blank here too.
for yy, lm, rm in zip([205, 294, 383, 472, 561],
                      ["0x08", "0x10", "0x20", "0x40", "0x80"],    # CPL_SEG3 -> LCDL 1..5
                      ["0x04", "0x08", "0x10", "0x20", "0x40"]):   # CPR_SEG3 -> LCDR 1..5
    S.append(P("lcd_soft_key", 520, yy, 123, 34, flip=True, tag="CPL_SEG3", mask=lm))
    S.append(P("lcd_soft_key", 2125, yy, 123, 34, tag="CPR_SEG3", mask=rm))

# ---- left of / below the display: OTHER PARTS/TR, HELP, CONTRAST (decorative), MUTE 1-16
S += [L("OTHER", 528, 717, 60, 13), L("PARTS / TR", 520, 730, 76, 13),
      P("round_btn_big", 537, 748, 42, 42, tag="CPL_SEG8", mask="0x04"), P("red_led", 583, 752, 8, 8),
      P("round_btn_big", 537, 852, 42, 42, tag="CPL_SEG8", mask="0x08"), L("HELP", 536, 838, 44, 13)]
# CONTRAST is an analog trimmer at the lower-left of the display (manual p.5) -- shown, not clickable.
S += [L("CONTRAST", 610, 730, 100, 13), P("fader_rail", 655, 762, 6, 140),
      P("hline", 636, 756, 44, 3), P("hline", 636, 900, 44, 3)]
# MUTE: 16 part on/off rockers.  CPL_SEG4/5/6/7 = parts 1-4/5-8/9-12/13-16; within a segment the four
# pairs are (0x01,0x02),(0x04,0x08),(0x10,0x20),(0x40,0x80) = up(part ON)/down(part OFF).
MUTE_SEGS = ["CPL_SEG4", "CPL_SEG5", "CPL_SEG6", "CPL_SEG7"]
MUTE_PAIRS = [("0x01", "0x02"), ("0x04", "0x08"), ("0x10", "0x20"), ("0x40", "0x80")]
S += [L("MUTE", 700, 825, 46, 13, TXTH), P("hline", 702, 818, 32, 3), P("vline", 702, 806, 3, 14),
      P("hline", 702, 843, 32, 3), P("vline", 702, 843, 3, 14)]
for i in range(16):
    x = 770 + i * 83
    seg = MUTE_SEGS[i // 4]; on, off = MUTE_PAIRS[i % 4]
    S.append(L(str(i + 1), x + 10, 742, 26, 11, TXTH))
    S.append(P("mute_up", x, 756, 46, 77, tag=seg, mask=on))
    S.append(P("mute_down", x, 833, 46, 78, tag=seg, mask=off))
# ---- right of the display: PAGE, DISPLAY HOLD, EXIT
S += [L("PAGE", 2124, 730, 52, 13),
      P("page_up", 2125, 756, 50, 78, tag="CPL_SEG8", mask="0x01"),
      P("page_dn", 2125, 834, 50, 77, tag="CPL_SEG8", mask="0x02"),
      L("DISPLAY", 2222, 717, 64, 13), L("HOLD", 2222, 730, 64, 13),
      P("round_btn_big", 2235, 748, 42, 42, tag="CPL_SEG8", mask="0x10"), P("red_led", 2281, 752, 8, 8),
      P("round_btn_big", 2235, 852, 42, 42, tag="CPL_SEG8", mask="0x20"), L("EXIT", 2234, 838, 44, 13)]

# ---- SOUND GROUP: 4x4, manual reading order == CPR_SEG0/1/2 b0..b5 (6/6/4)
SG = [("PIANO", "CPR_SEG0", "0x01"), ("GUITAR", "CPR_SEG0", "0x02"),
      ("STRINGS & VOCAL", "CPR_SEG0", "0x04"), ("BRASS", "CPR_SEG0", "0x08"),
      ("MALLET & ORCH PERC", "CPR_SEG0", "0x10"), ("WORLD", "CPR_SEG0", "0x20"),
      ("ORGAN & ACCORDION", "CPR_SEG1", "0x01"), ("SAX & WOODWIND", "CPR_SEG1", "0x02"),
      ("PAD", "CPR_SEG1", "0x04"), ("SYNTH", "CPR_SEG1", "0x08"),
      ("BASS", "CPR_SEG1", "0x10"), ("DRUM KITS", "CPR_SEG1", "0x20"),
      ("DIGITAL DRAWBAR", "CPR_SEG2", "0x01"), ("ACCORDION REGISTER", "CPR_SEG2", "0x02"),
      ("SOUND EXPLORER", "CPR_SEG2", "0x04"), ("MEMORY", "CPR_SEG2", "0x08")]
hdr(S, "SOUND GROUP", 2300, 42, 480); S += [P("hline", 2300, 56, 480, 3)]
for i, (nm, tg, mk) in enumerate(SG):
    cell(S, 2320 + (i % 4) * 120, 110 + (i // 4) * 100, nm, tg, mk, dx=120, ref="sq_btn", size=44, gap=24)
# ---- PART EFFECT row, directly under SOUND GROUP (manual p.6)
hdr(S, "PART EFFECT", 2300, 546, 480); S += [P("hline", 2300, 560, 480, 3)]
for i, (nm, tg, mk) in enumerate([("SUSTAIN", "CPR_SEG2", "0x10"), ("DIGITAL EFFECT", "CPR_SEG2", "0x20"),
                                  ("SOUND DSP", "CPR_SEG3", "0x01"), ("VARIATION", "CPR_SEG3", "0x02")]):
    cell(S, 2324 + i * 120, 596, nm, tg, mk, dx=112)
S.append('\t</group>')

# ================================================================= LEFT BLOCK (lower deck, left)
LB = ['\t<group name="left_block">', f'\t\t<bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/>',
      P("bg_blk", 0, 0, BLK_W, BLK_H)]
LB += [L("POWER", 42, 28, 70, 13, TXTH), P("power_sw", 45, 46, 60, 40),
       L("OFF", 40, 90, 30, 10, TXTH), L("ON", 82, 90, 30, 10, TXTH)]
LB += [L("DEMO", 152, 28, 60, 13), P("demo_btn", 160, 46, 42, 42, tag="CPL_SEG9", mask="0x40"),
       P("red_led", 206, 50, 8, 8)]
hdr(LB, "SOUND CONTROLLER", 40, 140, 220); LB += [P("hline", 40, 154, 220, 3)]
cell(LB, 62, 190, "RESET", "CPL_SEG8", "0x80", dx=90, led=False)
cell(LB, 202, 190, "MODE", "CPL_SEG8", "0x40", dx=90, led=False)
LB += [P("trackball", 90, 250, 120, 120), P("red_led", 146, 234, 8, 8)]
fader(LB, 330, 200, 190, "VOL_MAIN", "MAIN")
fader(LB, 415, 200, 190, "VOL_APCSEQ", "APC/SEQUENCER", lw=110)
LB.append(P("green_led", 437, 202, 8, 8))
# ---- PERFORMANCE PADS
hdr(LB, "PERFORMANCE PADS", 520, 28, 400); LB += [P("hline", 520, 42, 400, 3)]
cell(LB, 545, 90, "AUTO SETTING", "CPL_SEG9", "0x04", dx=110)
cell(LB, 790, 90, "BANK", "CPL_SEG9", "0x01", dx=80, led=False)
cell(LB, 880, 90, "STOP", "CPL_SEG9", "0x02", dx=80, led=False)
PADS = [("1", "CPL_SEG0", "0x01"), ("2", "CPL_SEG1", "0x01"), ("3", "CPL_SEG2", "0x01"),
        ("4", "CPL_SEG0", "0x02"), ("5", "CPL_SEG1", "0x02"), ("6", "CPL_SEG2", "0x02")]
for i, (nm, tg, mk) in enumerate(PADS):
    ref = ["msp_corner", "msp_middle", "msp_corner_r"][i % 3]
    x = 525 + (i % 3) * 130; y = 180 + (i // 3) * 62
    LB.append(P(ref if i < 3 else "msp_middle", x, y, 130, 58, tag=tg, mask=mk))
    LB.append(L(nm, x + 58, y + 22, 20, 12, TXTD))
LB += [L("SOLO", 700, 302, 40, 9, TXTD), L("SOLO", 830, 302, 40, 9, TXTD)]
LB.append('\t</group>')

# ================================================================= MID BLOCK (lower deck, centre)
MB = ['\t<group name="mid_block">', f'\t\t<bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/>',
      P("bg_blk", 0, 0, BLK_W, BLK_H)]
cell(MB, 60, 90, "MUSIC STYLE ARRANGER", "CPL_SEG9", "0x08", dx=110)
cell(MB, 190, 90, "ONE TOUCH PLAY", "CPR_SEG4", "0x01", dx=110)
cell(MB, 320, 90, "SPLIT POINT", "CPR_SEG4", "0x02", dx=110)
hdr(MB, "VARIATION & MSA", 40, 190, 400); MB += [P("hline", 40, 204, 400, 3)]
for i, (tg, mk) in enumerate([("CPL_SEG9", "0x10"), ("CPL_SEG9", "0x20"), ("CPR_SEG4", "0x04"), ("CPR_SEG4", "0x08")]):
    cell(MB, 55 + i * 100, 250, str(i + 1), tg, mk, dx=90, ref="round_btn_big", size=42)
# ---- rhythm transport (manual p.5, right of VARIATION & MSA)
hdr(MB, "FADE", 500, 34, 150)
MB += [L("IN", 512, 48, 40, 10), L("OUT", 592, 48, 40, 10), P("red_led", 522, 60, 8, 8), P("red_led", 602, 60, 8, 8)]
MB += pair_h("CPR_SEG5", "0x01", "0x02", 500, 72, 150, 44)
hdr(MB, "TAP TEMPO", 690, 34, 150)
MB += [P("pill_md", 690, 72, 150, 44, tag="CPR_SEG6", mask="0x04")]
hdr(MB, "FILL IN", 500, 160, 150)
MB += [L("1", 522, 174, 20, 10), L("2", 606, 174, 20, 10)]
MB += pair_h("CPR_SEG5", "0x04", "0x08", 500, 188, 150, 46)
MB += [L("SEQUENCER RESET", 486, 238, 90, 9, TXTH), L("COUNT INTRO", 588, 238, 80, 9, TXTH)]
hdr(MB, "INTRO & ENDING", 690, 160, 160)
MB += [L("1", 712, 174, 20, 10), L("2", 796, 174, 20, 10)]
MB += pair_h("CPR_SEG6", "0x01", "0x02", 690, 188, 150, 46)
hdr(MB, "SYNCHRO & BREAK", 500, 300, 170)
MB += [P("pill_md", 500, 322, 150, 44, tag="CPR_SEG8", mask="0x04"), P("red_led", 566, 312, 8, 8)]
hdr(MB, "START / STOP", 700, 300, 160)
MB += [P("pill_start", 690, 320, 180, 60, tag="CPR_SEG6", mask="0x08")]
for i in range(4):   # 1 2 3 4 BEAT indicators (unbound: KN6000 LED decode unconfirmed)
    MB.append(P("red_led", 700 + i * 40, 392, 8, 8)); MB.append(L(str(i + 1), 712 + i * 40, 391, 18, 10, TXTH))
MB.append(L("BEAT", 866, 391, 44, 10, TXTH))
MB.append('\t</group>')

# ================================================================= RIGHT BLOCK (lower deck, right)
RB = ['\t<group name="right_block">', f'\t\t<bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/>',
      P("bg_blk", 0, 0, BLK_W, BLK_H)]
RB += [L("TEMPO / PROGRAM", 18, 26, 128, 13, TXTH),
       '\t\t<element id="tempo_knob" ref="tempo_knob"><bounds x="30" y="46" width="110" height="110"/></element>',
       '\t\t<element id="tempo_click" ref="inv_rect"><bounds x="30" y="46" width="110" height="110"/></element>',
       '\t\t<element id="tempo_finger" ref="tempo_finger"><bounds x="69" y="85" width="32" height="32"/></element>',
       P("red_led", 146, 30, 8, 8)]
RB += [L("MUSIC STYLIST", 170, 26, 110, 11), P("red_led", 220, 40, 8, 8),
       P("disc_top", 175, 52, 96, 52, tag="CPR_SEG8", mask="0x01"),
       P("disc_bot", 175, 106, 96, 52, tag="CPR_SEG8", mask="0x02"),
       P("red_led", 220, 160, 8, 8), L("FAVORITES", 178, 172, 90, 11), L("CUSTOMIZE", 178, 183, 90, 9, TXTH)]
hdr(RB, "TRANSPOSE", 300, 22, 130)
RB += [P("red_led", 316, 38, 8, 8), L("-", 328, 37, 16, 10), P("red_led", 394, 38, 8, 8), L("+", 406, 37, 16, 10)]
RB += pair_h("CPR_SEG7", "0x01", "0x02", 300, 56, 130, 40)
hdr(RB, "R1/R2 OCTAVE", 300, 108, 140)
RB += [P("red_led", 316, 124, 8, 8), L("-", 328, 123, 16, 10), P("red_led", 394, 124, 8, 8), L("+", 406, 123, 16, 10)]
RB += pair_h("CPR_SEG7", "0x04", "0x08", 300, 140, 130, 40)
hdr(RB, "PART SELECT", 460, 22, 230); RB += [P("hline", 460, 36, 230, 3)]
for i, (nm, mk) in enumerate([("LEFT", "0x10"), ("RIGHT 2", "0x20"), ("RIGHT 1", "0x40")]):
    RB.append(P("red_led", 478 + i * 76, 44, 8, 8))
    RB.append(P("sq_btn", 470 + i * 76, 56, 44, 30, tag="CPR_SEG4", mask=mk))
for i, (nm, mk) in enumerate([("LEFT", "0x10"), ("RIGHT 2", "0x20"), ("RIGHT 1", "0x40")]):
    RB.append(L(nm, 458 + i * 76, 100, 68, 10))
    RB.append(P("red_led", 478 + i * 76, 112, 8, 8))
    RB.append(P("sq_btn_big", 466 + i * 76, 124, 52, 44, tag="CPR_SEG5", mask=mk))
hdr(RB, "CONDUCTOR", 460, 174, 230); RB += [P("hline", 460, 188, 230, 3)]
cell(RB, 716, 56, "SOLO", "CPR_SEG4", "0x80", dx=80)
cell(RB, 710, 128, "TECHNI-CHORD", "CPR_SEG5", "0x80", dx=100, ref="round_btn_big", size=42)
hdr(RB, "GLOBAL EFFECT", 460, 206, 300); RB += [P("hline", 460, 220, 300, 3)]
for i, (nm, mk) in enumerate([("CHORUS", "0x10"), ("MULTI", "0x20"), ("REVERB", "0x40"), ("MIC", "0x80")]):
    cell(RB, 468 + i * 78, 254, nm, "CPR_SEG7", mk, dx=78)
fader(RB, 878, 236, 116, "VOL_MIC", "MIC", lw=64)
# ---- PANEL MEMORY
hdr(RB, "PANEL MEMORY", 30, 296, 420); RB += [P("hline", 30, 310, 420, 3)]
for nm, x, mk in [("SET", 40, "0x10"), ("NEXT BANK", 140, "0x20"), ("BANK VIEW", 250, "0x40"), ("CUSTOM PANEL", 360, "0x80")]:
    cell(RB, x, 346, nm, "CPR_SEG8", mk, dx=100)
for i in range(8):
    cell(RB, 40 + i * 62, 420, str(i + 1), "CPR_SEG9", "0x%02x" % (1 << i), dx=58, ref="round_btn_silver", size=42)
hdr(RB, "SEQUENCER", 600, 296, 190); RB += [P("hline", 600, 310, 190, 3)]
cell(RB, 620, 346, "PLAY", "CPR_SEG6", "0x10", dx=90)
cell(RB, 730, 346, "EASY REC", "CPR_SEG6", "0x20", dx=90)
cell(RB, 620, 430, "PROGRAM MENUS", "CPR_SEG6", "0x40", dx=100)
cell(RB, 740, 430, "DISK", "CPR_SEG6", "0x80", dx=80)
RB += [L("LOAD", 726, 472, 60, 10, TXTH), L("DISK IN USE", 806, 418, 86, 9, TXTH), P("red_led", 844, 430, 8, 8)]
RB.append('\t</group>')

# ================================================================= views + script
VIEWS = f'''
	<view name="Compact">
		<bounds x="0" y="0" width="{W}" height="{SCR_H + BLK_H}"/>
		<group ref="screen_block"><bounds x="0" y="0" width="{W}" height="{SCR_H}"/></group>
		<group ref="left_block"><bounds x="0" y="{SCR_H}" width="{BLK_W}" height="{BLK_H}"/></group>
		<group ref="mid_block"><bounds x="{BLK_W}" y="{SCR_H}" width="{BLK_W}" height="{BLK_H}"/></group>
		<group ref="right_block"><bounds x="{2 * BLK_W}" y="{SCR_H}" width="{BLK_W}" height="{BLK_H}"/></group>
	</view>

	<view name="Screen Block">
		<bounds x="0" y="0" width="{W}" height="{SCR_H}"/>
		<group ref="screen_block"><bounds x="0" y="0" width="{W}" height="{SCR_H}"/></group>
	</view>

	<view name="Left Block">
		<bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/>
		<group ref="left_block"><bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/></group>
	</view>

	<view name="Mid Block">
		<bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/>
		<group ref="mid_block"><bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/></group>
	</view>

	<view name="Right Block">
		<bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/>
		<group ref="right_block"><bounds x="0" y="0" width="{BLK_W}" height="{BLK_H}"/></group>
	</view>
'''

_lib = open(os.path.join(HERE, "slider_lib.lua")).read()
SCRIPT = ('\t<script><![CDATA[\n' + _lib + '\n'
          '\t\t-- Draggable controls: MAIN / APC-SEQUENCER volume (left_block), MIC volume\n'
          '\t\t-- (right_block) and the infinite-rotary TEMPO/PROGRAM wheel (right_block).\n'
          '\t\tfile:set_resolve_tags_callback(function()\n'
          '\t\t\tfor vname, view in pairs(file.views) do\n'
          '\t\t\t\tlocal any = false\n'
          '\t\t\t\tif view.items["vol_main_click"] ~= nil then\n'
          '\t\t\t\t\tadd_vertical_slider(view, "vol_main_click", "vol_main_knob", "VOL_MAIN")\n'
          '\t\t\t\t\tadd_vertical_slider(view, "vol_apcseq_click", "vol_apcseq_knob", "VOL_APCSEQ")\n'
          '\t\t\t\t\tany = true\n'
          '\t\t\t\tend\n'
          '\t\t\t\tif view.items["vol_mic_click"] ~= nil then\n'
          '\t\t\t\t\tadd_vertical_slider(view, "vol_mic_click", "vol_mic_knob", "VOL_MIC")\n'
          '\t\t\t\t\tany = true\n'
          '\t\t\t\tend\n'
          '\t\t\t\tif view.items["tempo_click"] ~= nil and view.items["tempo_finger"] ~= nil then\n'
          '\t\t\t\t\tadd_rotary_knob(view, "tempo_click", "tempo_finger", "TEMPO_KNOB")\n'
          '\t\t\t\t\tany = true\n'
          '\t\t\t\tend\n'
          '\t\t\t\tif any then install_slider_callbacks(view) end\n'
          '\t\t\tend\n'
          '\t\tend)\n'
          '\t\treturn { frame = poll_rotary_wheels }\n'
          '\t]]></script>\n')

o = io.StringIO()
o.write('<?xml version="1.0"?>\n'
        '<!-- Technics SX-KN6000 / SX-KN6500 control-panel layout.\n'
        '     Geometry and silkscreen wording from the SX-KN6000 service manual pp.5-6 (the owner\'s\n'
        '     manual "Controls and functions" two-page panel drawing); every button binds its own\n'
        '     kn6000_cpanel_device scan-matrix cell.  Indicator LEDs are drawn but intentionally\n'
        '     UNBOUND: the KN6000 LED register/bit decode is not yet confirmed.\n'
        '     Generated by tools/gen_kn6000_lay.py; do not edit by hand. -->\n'
        '<mamelayout version="2">\n\n')
o.write("\n".join(E) + "\n\n" + "\n".join(S) + "\n\n" + "\n".join(LB) + "\n\n" + "\n".join(MB) + "\n\n"
        + "\n".join(RB) + "\n" + VIEWS + SCRIPT + '</mamelayout>\n')
lay = o.getvalue()

# --- Annotate every bound button with its silk name, read from the DEVICE's INPUT_PORTS, so the
#     comment in the .lay can never drift from what the driver says the cell is.
_src = os.path.join(HERE, "..", "src", "mame", "matsushita", "kn6000_cpanel.cpp")
BTN = {}; _cp = None
for ln in open(_src).read().splitlines():
    m = re.search(r'PORT_START\("(CP[LR]_SEG\d+)"\)', ln)
    if m: _cp = m.group(1); continue
    if "PORT_START" in ln: _cp = None; continue
    if _cp is None: continue
    mb = re.search(r'PORT_BIT\(\s*(0x[0-9a-fA-F]+).*?PORT_NAME\("([^"]*)"\)', ln)
    if mb:
        BTN[(_cp, "0x%02x" % int(mb.group(1), 16))] = re.sub(r'\s*\(SW\d+\)\s*$', '', mb.group(2)).strip()
_n = [0, 0]
def _ann(m):
    nm = BTN.get((m.group(2), m.group(3)))
    if not nm:
        _n[1] += 1; return m.group(0)
    _n[0] += 1
    return f'<element {m.group(1)}><!-- {nm.replace("--", "-")} -->'
lay = re.sub(r'<element ([^>]*\binputtag="(CP[LR]_SEG\d+)" inputmask="(0x[0-9a-fA-F]+)"[^>]*)>', _ann, lay)

# --- The scan-matrix ports live in the control-panel DEVICE, so qualify every inputtag with its path.
lay, _q = re.subn(r'inputtag="(CP[LR]_SEG\d+)"', r'inputtag="cpanel:\1"', lay)

open(OUT, "w").write(lay)
print(f"WROTE kn6000.lay: {len(E)} elements, {len(TXTS)} labels")
print(f"ANNOTATED {_n[0]} buttons from kn6000_cpanel.cpp INPUT_PORTS ({_n[1]} unknown)")
print(f"QUALIFIED {_q} button inputtags with the cpanel: device path")
_bound = set(re.findall(r'inputtag="cpanel:(CP[LR]_SEG\d+)" inputmask="(0x[0-9a-fA-F]+)"', lay))
_named = set(BTN)
print(f"COVERAGE: {len(_bound)}/{len(_named)} named matrix cells placed")
for k in sorted(_named - _bound):
    print(f"  MISSING {k[0]} {k[1]} = {BTN[k]}")
for k in sorted(_bound - _named):
    print(f"  EXTRA   {k[0]} {k[1]} (no such named cell in the driver)")
