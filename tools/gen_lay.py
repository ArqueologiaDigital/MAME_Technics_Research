#!/usr/bin/env python3
# Generator for src/mame/layout/kn7000.lay -- KN5000-style SVG-snippet layout,
# arranged to the KN7000 mockup. Three reusable blocks (groups) + two views.
# KN7000 palette: dark charcoal/graphite panel, dark buttons, white text (no
# KN5000 teal). Refined from real-unit appearance (black/graphite).
import io

# ---- palette (KN7000: darker/blacker than KN5000) -------------------------
PANEL   = "#2a2a2c"   # main control panel
PANEL2  = "#232325"   # raised/darker sub-panel
BTN     = "#232323"   # dark button face (reused from KN5000)
BTN_D   = "#1b1b1b"   # dark button pressed
LBTN    = "#3a3a3c"   # lighter button
LBTN_D  = "#2c2c2e"
STROKE  = "#000"
TXT     = '<color red="0.90" green="0.90" blue="0.90"/>'   # white-ish labels
TXTH    = '<color red="0.72" green="0.72" blue="0.74"/>'   # dimmer section headers

E = []   # element XML fragments

def elem(name, body):
    E.append(f'\t<element name="{name}">{body}</element>')

def two_state_svg(name, w, h, shape0, shape1):
    E.append(
        f'\t<element name="{name}">\n'
        f'\t\t<image state="0"><data><![CDATA[<svg width="{w}" height="{h}">{shape0}</svg>]]></data></image>\n'
        f'\t\t<image state="1"><data><![CDATA[<svg width="{w}" height="{h}">{shape1}</svg>]]></data></image>\n'
        f'\t</element>')

def txt(name, s, color=TXT):
    E.append(f'\t<element name="{name}"><text string="{s}">{color}</text></element>')

# ---- element library -------------------------------------------------------
# Panel backgrounds (one per block, plain filled rects; the block bounds set size)
def panel_bg(name, w, h, fill):
    elem(name, f'<image><data><![CDATA[<svg width="{w}" height="{h}">'
               f'<rect width="{w}" height="{h}" fill="{fill}"/></svg>]]></data></image>')

# dark round button 29x29 (reused KN5000 shape)
two_state_svg("round_btn", 29, 29,
    f'<circle stroke="{STROKE}" stroke-width="1px" fill="{BTN}" cx="14.5" cy="14.5" r="14"/>',
    f'<circle stroke="{STROKE}" stroke-width="1px" fill="{BTN_D}" cx="14.5" cy="14.5" r="14"/>')
# big round button 40x40
two_state_svg("round_btn_big", 40, 40,
    f'<circle stroke="{STROKE}" stroke-width="1px" fill="{BTN}" cx="20" cy="20" r="19.5"/>',
    f'<circle stroke="{STROKE}" stroke-width="1px" fill="{BTN_D}" cx="20" cy="20" r="19.5"/>')
# dark pill 37x21 (reused)
two_state_svg("pill_btn", 37, 21,
    f'<rect stroke="{STROKE}" stroke-width="1px" fill="{BTN}" x="0.5" y="0.5" width="36" height="20" rx="10" ry="10"/>',
    f'<rect stroke="{STROKE}" stroke-width="1px" fill="{BTN_D}" x="0.5" y="0.5" width="36" height="20" rx="10" ry="10"/>')
# wide pill 60x22 (MUSIC STYLIST, SD, TAP TEMPO ...)
two_state_svg("pill_wide", 60, 22,
    f'<rect stroke="{STROKE}" stroke-width="1px" fill="{BTN}" x="0.5" y="0.5" width="59" height="21" rx="10.5" ry="10.5"/>',
    f'<rect stroke="{STROKE}" stroke-width="1px" fill="{BTN_D}" x="0.5" y="0.5" width="59" height="21" rx="10.5" ry="10.5"/>')
# small round LEDs (reused)
two_state_svg("red_led", 8, 8,
    '<circle cx="4" cy="4" r="3.5" fill="#3a0000"/>', '<circle cx="4" cy="4" r="3.5" fill="#ff2020"/>')
two_state_svg("green_led", 8, 8,
    '<circle cx="4" cy="4" r="3.5" fill="#003a00"/>', '<circle cx="4" cy="4" r="3.5" fill="#20ff20"/>')

# --- KN7000-unique shapes ---
# LCD soft-key: rectangle with a vertical divider line near the inner edge
two_state_svg("lcd_soft_key", 120, 46,
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="118" height="44" rx="4"/>'
    f'<line x1="30" y1="1" x2="30" y2="45" stroke="{STROKE}" stroke-width="1.5"/>',
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="118" height="44" rx="4"/>'
    f'<line x1="30" y1="1" x2="30" y2="45" stroke="{STROKE}" stroke-width="1.5"/>')
# mute half-buttons: top (UP) and bottom (DOWN) of a tall split rectangle 44x62 each
two_state_svg("mute_up", 44, 62,
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="42" height="60" rx="4"/>',
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="42" height="60" rx="4"/>')
two_state_svg("mute_down", 44, 62,
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="42" height="60" rx="4"/>',
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="42" height="60" rx="4"/>')
# tall CONTRAST pill (capsule) with a knob line
two_state_svg("contrast_pill", 40, 150,
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{PANEL2}" x="1" y="1" width="38" height="148" rx="19"/>'
    f'<rect fill="{BTN}" x="10" y="60" width="20" height="30" rx="4" stroke="{STROKE}"/>',
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{PANEL2}" x="1" y="1" width="38" height="148" rx="19"/>'
    f'<rect fill="{BTN_D}" x="10" y="66" width="20" height="30" rx="4" stroke="{STROKE}"/>')
# tall PAGE pill (up/down capsule)
two_state_svg("page_pill", 40, 150,
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="38" height="148" rx="19"/>',
    f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="38" height="148" rx="19"/>')
# vertical fader (volume slider): track + cap
two_state_svg("fader", 34, 150,
    f'<rect fill="{PANEL2}" stroke="{STROKE}" x="14" y="4" width="6" height="142"/>'
    f'<rect fill="{LBTN}" stroke="{STROKE}" stroke-width="1.5" x="4" y="40" width="26" height="20" rx="3"/>'
    f'<line x1="8" y1="50" x2="26" y2="50" stroke="{STROKE}"/>',
    f'<rect fill="{PANEL2}" stroke="{STROKE}" x="14" y="4" width="6" height="142"/>'
    f'<rect fill="{LBTN_D}" stroke="{STROKE}" stroke-width="1.5" x="4" y="46" width="26" height="20" rx="3"/>'
    f'<line x1="8" y1="56" x2="26" y2="56" stroke="{STROKE}"/>')
# TEMPO/PROGRAM encoder (big knurled knob)
two_state_svg("tempo_knob", 110, 110,
    f'<circle cx="55" cy="55" r="52" fill="{BTN}" stroke="{STROKE}" stroke-width="2"/>'
    f'<circle cx="55" cy="55" r="40" fill="{PANEL2}" stroke="{STROKE}"/>'
    f'<circle cx="55" cy="30" r="6" fill="{LBTN}" stroke="{STROKE}"/>',
    f'<circle cx="55" cy="55" r="52" fill="{BTN_D}" stroke="{STROKE}" stroke-width="2"/>'
    f'<circle cx="55" cy="55" r="40" fill="{PANEL2}" stroke="{STROKE}"/>'
    f'<circle cx="55" cy="30" r="6" fill="{LBTN}" stroke="{STROKE}"/>')
# PANEL MEMORY big segmented dial (bold ring, radial spokes, center SET)
spokes = "".join(
    f'<line x1="90" y1="90" x2="{90+80*__import__("math").cos(a)}" y2="{90+80*__import__("math").sin(a)}" stroke="{STROKE}" stroke-width="1.5"/>'
    for a in [i*3.14159/4 for i in range(8)])
two_state_svg("panel_memory_dial", 180, 180,
    f'<circle cx="90" cy="90" r="86" fill="{PANEL2}" stroke="{STROKE}" stroke-width="2"/>'
    f'{spokes}'
    f'<circle cx="90" cy="90" r="82" fill="none" stroke="{STROKE}" stroke-width="7"/>'
    f'<circle cx="90" cy="90" r="34" fill="{BTN}" stroke="{STROKE}" stroke-width="2"/>',
    f'<circle cx="90" cy="90" r="86" fill="{PANEL2}" stroke="{STROKE}" stroke-width="2"/>'
    f'{spokes}'
    f'<circle cx="90" cy="90" r="82" fill="none" stroke="{STROKE}" stroke-width="7"/>'
    f'<circle cx="90" cy="90" r="34" fill="{BTN_D}" stroke="{STROKE}" stroke-width="2"/>')
# performance pad (angled trapezoid pad)
two_state_svg("perf_pad", 78, 52,
    f'<path fill="{BTN}" stroke="{STROKE}" stroke-width="1.5" d="M4,6 L74,2 L74,50 L4,50 Z"/>',
    f'<path fill="{BTN_D}" stroke="{STROKE}" stroke-width="1.5" d="M4,6 L74,2 L74,50 L4,50 Z"/>')
# music note (DEMO)
elem("music_note", '<image><data><![CDATA[<svg width="20" height="24">'
     f'<circle cx="6" cy="19" r="5" fill="{TXT[19:26] if False else "#e0e0e0"}"/>'
     '<rect x="10" y="2" width="2.5" height="17" fill="#e0e0e0"/>'
     '<path d="M10,2 q8,2 8,8 q-3,-5 -8,-4 Z" fill="#e0e0e0"/></svg>]]></data></image>')
# screen border (frame around the LCD)
elem("screen_border", '<image><data><![CDATA[<svg width="1320" height="520">'
     f'<rect x="1" y="1" width="1318" height="518" fill="#050505" stroke="{STROKE}" stroke-width="2"/>'
     '</svg>]]></data></image>')

print(f"# {len(E)} elements defined; generator OK")
open("/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/74c7edc4-f16b-4349-97a0-39242e320cdb/scratchpad/lay_elements.xml","w").write("\n".join(E))

# ============================ block / view builders =========================
import math
TXTS = {}   # label text -> element name (dedup)
def xesc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def label(s, color=TXT):
    key=(s,color)
    if key not in TXTS:
        n=f"t{len(TXTS)}"; TXTS[key]=n
        E.append(f'\t<element name="{n}"><text string="{xesc(s)}">{color}</text></element>')
    return TXTS[key]

def P(ref,x,y,w,h,flip=False):
    o='<orientation flipx="yes"/>' if flip else ''
    return f'\t\t<element ref="{ref}">{o}<bounds x="{x}" y="{y}" width="{w}" height="{h}"/></element>'
def L(s,x,y,w,h,color=TXT):
    return f'\t\t<element ref="{label(s,color)}"><bounds x="{x}" y="{y}" width="{w}" height="{h}"/></element>'

# round button with a label above and a small LED (returns fragment list)
def keybtn(x,y,name,led="green_led",r=29):
    f=[P(name if name in ("round_btn","round_btn_big") else "round_btn",x,y,r,r)]
    return f

# ------------------------------- SCREEN BLOCK -------------------------------
S=[]
S.append('\t<group name="screen_block">')
S.append('\t\t<bounds x="0" y="0" width="2000" height="800"/>')
S.append(P("bg_screen",0,0,2000,800))
S.append(P("screen_border",340,100,1320,520))
S.append('\t\t<screen index="0"><bounds x="360" y="120" width="1280" height="480"/></screen>')
# LCD soft keys L/R (5 each)
ys=[200,285,370,455,540]
for i,yy in enumerate(ys):
    S.append(P("lcd_soft_key",140,yy,120,46))
    S.append(P("lcd_soft_key",1740,yy,120,46,flip=True))
# OTHER PART&FR + HELP
S.append(L("OTHER",118,612,84,16)); S.append(L("PART & FR",108,628,104,16))
S.append(P("round_btn_big",150,648,40,40)); S.append(P("red_led",196,652,8,8))
S.append(L("HELP",150,772,60,16)); S.append(P("round_btn_big",150,708,40,40))
# CONTRAST pill
S.append(L("CONTRAST",258,612,110,16)); S.append(P("contrast_pill",286,634,40,150))
S.append(L("MUTE",336,700,50,14,TXTH))
# MUTE 1..16 (decorative in v1; bindings are a separate pass)
for i in range(16):
    x=396+i*76
    S.append(P("mute_up",x,634,44,62)); S.append(P("mute_down",x,700,44,62))
# PAGE / DISPLAY HOLD / EXIT
S.append(L("PAGE",1636,612,60,16)); S.append(P("page_pill",1640,634,40,150))
S.append(L("DISPLAY",1726,606,84,15)); S.append(L("HOLD",1740,622,60,15))
S.append(P("round_btn_big",1748,648,40,40)); S.append(P("red_led",1794,652,8,8))
S.append(L("EXIT",1750,772,60,16)); S.append(P("round_btn_big",1748,708,40,40))
S.append('\t</group>')

# ------------------------- helper: labelled round grid ----------------------
def round_grid(out, x0, y0, cols, dx, dy, entries, header=None, big=False):
    # entries: list of (row, col, label_lines)  ; label above button, led below-left
    if header: out.append(L(header, x0, y0-22, dx*cols, 16, TXTH))
    r = 40 if big else 29
    for (row,col,lines) in entries:
        x=x0+col*dx; y=y0+row*dy
        for k,ln in enumerate(lines):
            out.append(L(ln, x-6, y-14-(len(lines)-1-k)*13, dx-4, 12))
        out.append(P("round_btn_big" if big else "round_btn", x, y, r, r))
        out.append(P("green_led", x-10, y+r-8, 8, 8))

# ------------------------------- LEFT BLOCK ---------------------------------
LB=[]
LB.append('\t<group name="left_block">')
LB.append('\t\t<bounds x="0" y="0" width="1000" height="700"/>')
LB.append(P("bg_left",0,0,1000,700))
# faders
for i,(nm) in enumerate(["MAIN","APC/SEQ","MIC","LINE IN"]):
    x=30+i*54
    LB.append(L(nm,x-14,14,60,12,TXTH)); LB.append(P("fader",x,36,34,150))
# AUTO PLAY CHORD
LB.append(L("AUTO PLAY CHORD",250,14,150,12,TXTH))
for i,(nm) in enumerate(["MODE","OFF/ON"]):
    LB.append(L(nm,250+i*70,34,60,12)); LB.append(P("round_btn",258+i*70,50,29,29))
for i,(nm) in enumerate(["SET","OFF/ON"]):
    LB.append(L(nm,250+i*70,96,60,12)); LB.append(P("round_btn",258+i*70,112,29,29))
# RHYTHM GROUP grid (2 x 8)
RG=["8 & 16 BEAT","ROCK & POP","BALLAD","JAZZ & SWING","BALLROOM","MOVIE & SHOW","ENTERTAINER","ORGANIST",
    "60s & 70s","MODERN DANCE","SOUL & R&B","COUNTRY & WESTERN","MARCH & WALTZ","LATIN & WORLD","CUSTOM","MEMORY"]
ent=[]
for i,nm in enumerate(RG):
    ent.append((i//8, i%8, [nm]))
round_grid(LB, 430, 60, 8, 66, 66, ent, header="RHYTHM GROUP")
# MUSIC STYLIST
LB.append(L("MUSIC STYLIST",250,196,120,12)); LB.append(P("pill_wide",250,212,60,22))
# DEMO + performance pad triggers
LB.append(P("music_note",30,250,20,24)); LB.append(L("DEMO",26,278,50,12))
for i,(nm) in enumerate(["AUTO SETTING","BANK","STOP"]):
    LB.append(L(nm,90+i*70,250,66,12)); LB.append(P("round_btn",100+i*70,266,29,29))
LB.append(L("PERFORMANCE PADS",100,236,180,12,TXTH))
# performance pads 1-6 (2x3)
for i in range(6):
    x=30+(i%3)*82; y=330+(i//3)*56
    LB.append(P("perf_pad",x,y,78,52)); LB.append(L(str(i+1),x+6,y+34,20,14))
# arranger pills row
arr=["MUSIC STYLE ARRANGER","ONE TOUCH PLAY","SPLIT POINT"]
for i,nm in enumerate(arr):
    x=290+i*100; LB.append(L(nm,x,330,96,12)); LB.append(P("pill_wide",x,346,60,22))
for i,nm in enumerate(["VARIATION 1","2","3","4"]):
    x=290+i*70; LB.append(P("round_btn",x,400,29,29)); LB.append(L(nm,x-4,388,50,11))
for i,nm in enumerate(["FADE IN/OUT","TAP TEMPO","SYNCHRO & BREAK","INTRO & ENDING","START/STOP"]):
    x=580+i*80; LB.append(L(nm,x,330,76,12)); LB.append(P("pill_wide",x,346,60,22))
LB.append('\t</group>')

# ------------------------------- RIGHT BLOCK --------------------------------
RB=[]
RB.append('\t<group name="right_block">')
RB.append('\t\t<bounds x="0" y="0" width="1000" height="700"/>')
RB.append(P("bg_right",0,0,1000,700))
# SOUND GROUP grid (2 x 9)
SG=["PIANO","GUITAR","MALLET & ORCH PERC","WORLD","STRINGS & VOCAL","BRASS","SAX & WOODWIND","ORGAN & ACCORDION","SOUND EXPLORER",
    "DIGITAL DRAWBAR","ORGAN TABS","ACCORDION REGISTER","PAD","SYNTH","BASS","DRUM KITS","MEMORY","EW EXPANSION"]
ent=[]
for i,nm in enumerate(SG):
    ent.append((i//9, i%9, [nm]))
round_grid(RB, 40, 60, 9, 66, 66, ent, header="SOUND GROUP")
# PART EFFECT
for i,nm in enumerate(["SUSTAIN","DIGITAL EFFECT","SOUND DSP","VARIATION"]):
    x=650+i*70; RB.append(L(nm,x-4,196,60,12)); RB.append(P("round_btn",x,212,29,29))
RB.append(L("PART EFFECT",650,180,150,12,TXTH))
# GLOBAL EFFECT
for i,nm in enumerate(["CHORUS","MULTI","REVERB","MIC"]):
    x=650+i*70; RB.append(L(nm,x-4,256,60,12)); RB.append(P("round_btn",x,272,29,29))
RB.append(L("GLOBAL EFFECT",650,244,150,12,TXTH))
# SEQUENCER
RB.append(L("SEQUENCER",900,180,90,12,TXTH))
for i,nm in enumerate(["PLAY","EASY REC","DISK","PROGRAM MENUS"]):
    RB.append(L(nm,900,200+i*30,90,12)); RB.append(P("round_btn",960,196+i*30,29,29))
# TEMPO/PROGRAM
RB.append(L("TEMPO/PROGRAM",40,300,140,12,TXTH)); RB.append(P("tempo_knob",50,320,110,110))
# TRANSPOSE
RB.append(L("TRANSPOSE",210,300,100,12,TXTH))
RB.append(P("pill_wide",210,320,60,22)); RB.append(P("pill_wide",210,350,60,22))
# TECHNI-CHORD / PART SELECT / CONDUCTOR
for i,nm in enumerate(["TECHNI-CHORD","PART SELECT","CONDUCTOR"]):
    x=320+i*90; RB.append(L(nm,x,300,86,12,TXTH)); RB.append(P("round_btn",x+20,320,29,29))
# PANEL MEMORY dial
RB.append(L("PANEL MEMORY",620,300,180,12,TXTH)); RB.append(P("panel_memory_dial",640,320,180,180))
RB.append(L("SET",705,405,50,14))
RB.append(L("BANK VIEW",620,300,90,12)); RB.append(L("NEXT BANK",740,300,90,12))
# SD + CUSTOM PANEL / FAVORITES / CUSTOMIZE
RB.append(L("SD",900,320,40,12,TXTH)); RB.append(P("pill_wide",900,336,60,22))
for i,nm in enumerate(["CUSTOM PANEL","FAVORITES","CUSTOMIZE"]):
    x=850+i*50; RB.append(L(nm,x,520,60,11)); RB.append(P("round_btn",x+10,536,29,29))
RB.append('\t</group>')

# ------------------------- panel backgrounds + views ------------------------
panel_bg("bg_screen",2000,800,PANEL)
panel_bg("bg_left",1000,700,PANEL)
panel_bg("bg_right",1000,700,PANEL)

VIEWS='''
	<view name="Compact">
		<bounds x="0" y="0" width="2000" height="1500"/>
		<group ref="screen_block"><bounds x="0" y="0" width="2000" height="800"/></group>
		<group ref="left_block"><bounds x="0" y="800" width="1000" height="700"/></group>
		<group ref="right_block"><bounds x="1000" y="800" width="1000" height="700"/></group>
	</view>

	<view name="Full Unit">
		<bounds x="0" y="0" width="4000" height="800"/>
		<group ref="left_block"><bounds x="0" y="50" width="1000" height="700"/></group>
		<group ref="screen_block"><bounds x="1000" y="0" width="2000" height="800"/></group>
		<group ref="right_block"><bounds x="3000" y="50" width="1000" height="700"/></group>
	</view>
'''

# ------------------------------- assemble -----------------------------------
out=io.StringIO()
out.write('<?xml version="1.0"?>\n')
out.write('<!-- KN7000 control-panel layout. SVG-snippet style (after kn5000.lay);\n')
out.write('     three reusable blocks (screen_block, left_block, right_block) +\n')
out.write('     Compact and Full Unit views. Generated by tools/gen_lay.py. -->\n')
out.write('<mamelayout version="2">\n\n')
out.write("\n".join(E)); out.write("\n\n")
out.write("\n".join(S)); out.write("\n\n")
out.write("\n".join(LB)); out.write("\n\n")
out.write("\n".join(RB)); out.write("\n")
out.write(VIEWS)
out.write('</mamelayout>\n')
open("/home/fsanches/compartilhado/kn7000_mame/src/mame/layout/kn7000.lay","w").write(out.getvalue())
print(f"WROTE kn7000.lay: {len(E)} elements, {len(TXTS)} labels")
