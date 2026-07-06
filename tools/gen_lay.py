#!/usr/bin/env python3
# Generator for src/mame/layout/kn7000.lay -- KN5000-style SVG-snippet layout,
# arranged pixel-perfectly to the mockup (4000x3000 = 2x the 2000x1500 layout;
# all measured coords are the mockup's /2). Three reusable blocks + two views.
import io, math

PANEL="#2a2a2c"; PANEL2="#232325"; BTN="#232323"; BTN_D="#1b1b1b"
LBTN="#3a3a3c"; LBTN_D="#2c2c2e"; MSP="#5f6367"; MSP_D="#505860"; STROKE="#000"
TXT ='<color red="0.90" green="0.90" blue="0.90"/>'
TXTH='<color red="0.72" green="0.72" blue="0.74"/>'
E=[]; TXTS={}
def elem(n,b): E.append(f'\t<element name="{n}">{b}</element>')
def two(n,w,h,s0,s1):
    E.append(f'\t<element name="{n}">\n\t\t<image state="0"><data><![CDATA[<svg width="{w}" height="{h}">{s0}</svg>]]></data></image>\n'
             f'\t\t<image state="1"><data><![CDATA[<svg width="{w}" height="{h}">{s1}</svg>]]></data></image>\n\t</element>')
def xesc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def label(s,color=TXT):
    k=(s,color)
    if k not in TXTS:
        n=f"t{len(TXTS)}"; TXTS[k]=n
        E.append(f'\t<element name="{n}"><text string="{xesc(s)}">{color}</text></element>')
    return TXTS[k]
def P(ref,x,y,w,h,flip=False,tag=None,mask=None):
    o='<orientation flipx="yes"/>' if flip else ''
    b=f' inputtag="{tag}" inputmask="{mask}"' if tag else ''
    return f'\t\t<element ref="{ref}"{b}>{o}<bounds x="{x}" y="{y}" width="{w}" height="{h}"/></element>'
def L(s,x,y,w,h,color=TXT): return f'\t\t<element ref="{label(s,color)}"><bounds x="{x}" y="{y}" width="{w}" height="{h}"/></element>'
def panel_bg(n,w,h,fill): elem(n,f'<image><data><![CDATA[<svg width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="{fill}"/></svg>]]></data></image>')

# ---- element library (reused kn5000 shapes + kn7000-unique) ----
two("round_btn",29,29,f'<circle stroke="{STROKE}" fill="{BTN}" cx="14.5" cy="14.5" r="14"/>',f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="14.5" cy="14.5" r="14"/>')
two("round_btn_big",42,42,f'<circle stroke="{STROKE}" fill="{BTN}" cx="21" cy="21" r="20.5"/>',f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="21" cy="21" r="20.5"/>')
two("pill_btn",37,21,f'<rect stroke="{STROKE}" fill="{BTN}" x="0.5" y="0.5" width="36" height="20" rx="10"/>',f'<rect stroke="{STROKE}" fill="{BTN_D}" x="0.5" y="0.5" width="36" height="20" rx="10"/>')
two("pill_wide",60,22,f'<rect stroke="{STROKE}" fill="{BTN}" x="0.5" y="0.5" width="59" height="21" rx="10.5"/>',f'<rect stroke="{STROKE}" fill="{BTN_D}" x="0.5" y="0.5" width="59" height="21" rx="10.5"/>')
two("red_led",8,8,'<circle cx="4" cy="4" r="3.5" fill="#3a0000"/>','<circle cx="4" cy="4" r="3.5" fill="#ff2020"/>')
two("green_led",8,8,'<circle cx="4" cy="4" r="3.5" fill="#003a00"/>','<circle cx="4" cy="4" r="3.5" fill="#20ff20"/>')
# LCD soft key: rect + inner vertical divider
two("lcd_soft_key",123,34,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="121" height="32" rx="3"/><line x1="28" y1="1" x2="28" y2="33" stroke="{STROKE}" stroke-width="1.5"/>',
                          f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="121" height="32" rx="3"/><line x1="28" y1="1" x2="28" y2="33" stroke="{STROKE}" stroke-width="1.5"/>')
two("mute_up",55,77,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="53" height="75" rx="3"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="53" height="75" rx="3"/>')
two("mute_down",55,78,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="53" height="76" rx="3"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="53" height="76" rx="3"/>')
two("tall_pill",50,155,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="48" height="153" rx="24"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="48" height="153" rx="24"/>')
two("fader",30,150,f'<rect fill="{PANEL2}" stroke="{STROKE}" x="12" y="4" width="6" height="142"/><rect fill="{LBTN}" stroke="{STROKE}" stroke-width="1.5" x="2" y="40" width="26" height="18" rx="3"/>',
                    f'<rect fill="{PANEL2}" stroke="{STROKE}" x="12" y="4" width="6" height="142"/><rect fill="{LBTN_D}" stroke="{STROKE}" stroke-width="1.5" x="2" y="48" width="26" height="18" rx="3"/>')
two("tempo_knob",100,100,f'<circle cx="50" cy="50" r="48" fill="{BTN}" stroke="{STROKE}" stroke-width="2"/><circle cx="50" cy="50" r="36" fill="{PANEL2}" stroke="{STROKE}"/><circle cx="50" cy="26" r="6" fill="{LBTN}" stroke="{STROKE}"/>',
                         f'<circle cx="50" cy="50" r="48" fill="{BTN_D}" stroke="{STROKE}" stroke-width="2"/><circle cx="50" cy="50" r="36" fill="{PANEL2}" stroke="{STROKE}"/><circle cx="50" cy="26" r="6" fill="{LBTN}" stroke="{STROKE}"/>')
sp="".join(f'<line x1="80" y1="80" x2="{80+72*math.cos(a)}" y2="{80+72*math.sin(a)}" stroke="{STROKE}" stroke-width="1.5"/>' for a in [i*math.pi/4 for i in range(8)])
two("panel_memory_dial",160,160,f'<circle cx="80" cy="80" r="77" fill="{PANEL2}" stroke="{STROKE}" stroke-width="2"/>{sp}<circle cx="80" cy="80" r="73" fill="none" stroke="{STROKE}" stroke-width="7"/><circle cx="80" cy="80" r="30" fill="{BTN}" stroke="{STROKE}" stroke-width="2"/>',
                                f'<circle cx="80" cy="80" r="77" fill="{PANEL2}" stroke="{STROKE}" stroke-width="2"/>{sp}<circle cx="80" cy="80" r="73" fill="none" stroke="{STROKE}" stroke-width="7"/><circle cx="80" cy="80" r="30" fill="{BTN_D}" stroke="{STROKE}" stroke-width="2"/>')
# reused KN5000 MSP performance-pad buttons (same shape on KN7000)
two("msp_corner",63,39,f'<path stroke="{STROKE}" fill="{MSP}" d="M 62.5,0.5 C 40,2 18.8,5.2 0.5,9.7 V 38.5 H 62.5 Z"/>',f'<path stroke="{STROKE}" fill="{MSP_D}" d="M 62.5,0.5 C 40,2 18.8,5.2 0.5,9.7 V 38.5 H 62.5 Z"/>')
two("msp_corner_r",63,39,f'<path transform="translate(63,0) scale(-1,1)" stroke="{STROKE}" fill="{MSP}" d="M 62.5,0.5 C 40,2 18.8,5.2 0.5,9.7 V 38.5 H 62.5 Z"/>',f'<path transform="translate(63,0) scale(-1,1)" stroke="{STROKE}" fill="{MSP_D}" d="M 62.5,0.5 C 40,2 18.8,5.2 0.5,9.7 V 38.5 H 62.5 Z"/>')
two("msp_middle",61,40,f'<path stroke="{STROKE}" fill="{MSP}" d="M 30.1,0.5 C 20.1,0.5 10.2,0.9 0.5,1.5 V 39.5 H 60.5 V 1.6 C 50.5,0.9 40.3,0.5 30.1,0.5 Z"/>',f'<path stroke="{STROKE}" fill="{MSP_D}" d="M 30.1,0.5 C 20.1,0.5 10.2,0.9 0.5,1.5 V 39.5 H 60.5 V 1.6 C 50.5,0.9 40.3,0.5 30.1,0.5 Z"/>')
elem("music_note",'<image><data><![CDATA[<svg width="20" height="24"><circle cx="6" cy="19" r="5" fill="#e0e0e0"/><rect x="10" y="2" width="2.5" height="17" fill="#e0e0e0"/><path d="M10,2 q8,2 8,8 q-3,-5 -8,-4 Z" fill="#e0e0e0"/></svg>]]></data></image>')
elem("screen_frame",f'<image><data><![CDATA[<svg width="1404" height="581"><rect x="1" y="1" width="1402" height="579" fill="#050505" stroke="{STROKE}" stroke-width="2"/></svg>]]></data></image>')
panel_bg("bg_top",2000,997,PANEL); panel_bg("bg_left",1000,503,PANEL); panel_bg("bg_right",1000,503,PANEL)

# =================== SCREEN BLOCK (top region, pixel-perfect) ===============
# Measured (lay coords): LCD frame x298-1702,y104-685; divider y997.
S=['\t<group name="screen_block">','\t\t<bounds x="0" y="0" width="2000" height="997"/>',
   P("bg_top",0,0,2000,997), P("screen_frame",298,104,1404,581),
   '\t\t<screen index="0"><bounds x="360" y="154" width="1280" height="480"/></screen>']
for yy in [205,294,383,472,561]:
    S.append(P("lcd_soft_key",138,yy,123,34))
    S.append(P("lcd_soft_key",1740,yy,123,34,flip=True))
# OTHER PART & FR / HELP
S += [L("OTHER PART & FR",90,712,150,15), P("round_btn_big",150,748,42,42), P("red_led",196,752,8,8),
      P("round_btn_big",150,852,42,42), L("HELP",150,900,80,15)]
# CONTRAST tall pill (x282-332)
S += [L("CONTRAST",250,712,120,15), P("tall_pill",282,756,50,155), L("MUTE",340,825,42,13,TXTH)]
# MUTE 1..16  (x=378+i*80.4, w55; up y756 h77, down y833 h78) -- decorative for now
for i in range(16):
    x=round(378+i*80.4)
    S.append(P("mute_up",x,756,55,77)); S.append(P("mute_down",x,833,55,78))
# PAGE / DISPLAY HOLD / EXIT
S += [L("PAGE",1636,712,60,15), P("tall_pill",1680,756,50,155),
      L("DISPLAY HOLD",1745,706,110,15), P("round_btn_big",1790,748,42,42), P("red_led",1836,752,8,8),
      P("round_btn_big",1790,852,42,42), L("EXIT",1790,900,60,15)]
S.append('\t</group>')

# =================== helper: labelled round grid (with bindings) ============
def wrap2(s):
    w=s.split(' ')
    if len(s)<=10 or len(w)==1: return [s]
    h=(len(w)+1)//2; return [' '.join(w[:h]),' '.join(w[h:])]
def grid(out,x0,y0,cols,dx,dy,entries,header=None):
    if header: out.append(L(header,x0-8,y0-26,dx*cols,14,TXTH))
    for i,(nm,tag,mask) in enumerate(entries):
        row,col=i//cols,i%cols; x=x0+col*dx; y=y0+row*dy
        for k,ln in enumerate(wrap2(nm)):
            out.append(L(ln,x-(dx-29)//2-4,y-13-(len(wrap2(nm))-1-k)*10,dx-2,9))
        out.append(P("round_btn",x,y,32,32,tag=tag,mask=mask)); out.append(P("green_led",x-9,y+22,8,8))

# =================== LEFT BLOCK (bottom-left; coords = mockup abs - (0,997)) =
LB=['\t<group name="left_block">','\t\t<bounds x="0" y="0" width="1000" height="503"/>',P("bg_left",0,0,1000,503)]
for nm,cx,y,h in [("MAIN",100,51,130),("APC/SEQ",166,51,130),("MIC",261,68,108),("LINE IN",304,68,108)]:
    LB.append(L(nm,cx-24,y-24,48,9,TXTH)); LB.append(L("VOLUME",cx-24,y-15,48,9,TXTH)); LB.append(P("fader",cx-15,y,30,h))
LB.append(L("AUTO PLAY CHORD",418,26,150,10,TXTH))
for nm,cx,y in [("MODE",447,54),("OFF/ON",505,54),("SET",447,139),("OFF/ON",505,139)]:
    LB.append(L(nm,cx-16,y-13,42,9)); LB.append(P("round_btn",cx-14,y,32,32))
RGcols=[580,635,690,746,801,856,911,967]
RG=[("8 & 16 BEAT","SEG00","0x04"),("ROCK & POP","SEG00","0x08"),("BALLAD","SEG00","0x10"),("JAZZ & SWING","SEG00","0x20"),
    ("BALLROOM","SEG00","0x40"),("MOVIE & SHOW","SEG00","0x80"),("ENTERTAINER","SEG01","0x04"),("ORGANIST","SEG01","0x08"),
    ("60s & 70s","SEG01","0x10"),("MODERN DANCE","SEG01","0x20"),("SOUL & R&B","SEG01","0x40"),("COUNTRY & WESTERN","SEG01","0x80"),
    ("MARCH & WALTZ","SEG02","0x04"),("LATIN & WORLD","SEG02","0x08"),("CUSTOM","SEG02","0x10"),("MEMORY","SEG02","0x20")]
LB.append(L("RHYTHM GROUP",700,32,180,11,TXTH))
for i,(nm,tag,mask) in enumerate(RG):
    cx=RGcols[i%8]; cy=71 if i<8 else 149; ls=wrap2(nm)
    for k,ln in enumerate(ls): LB.append(L(ln,cx-27,cy-13-(len(ls)-1-k)*9,54,8))
    LB.append(P("round_btn",cx-14,cy,32,32,tag=tag,mask=mask)); LB.append(P("green_led",cx-22,cy+22,8,8))
LB.append(L("MUSIC STYLIST",418,214,120,10)); LB.append(P("pill_wide",441,228,65,22))
LB += [P("music_note",30,268,20,24), L("DEMO",20,300,52,10), L("PERFORMANCE PADS",98,250,172,9,TXTH)]
for nm,cx in [("AUTO SETTING",155),("BANK",230),("STOP",305)]:
    LB.append(L(nm,cx-30,262,64,9)); LB.append(P("round_btn",cx-14,274,32,32))
pad=["msp_corner","msp_middle","msp_corner_r"]
for i in range(6):
    x=10+(i%3)*108; y=369 if i<3 else 421; LB.append(P(pad[i%3],x,y,105,48)); LB.append(L(str(i+1),x+8,y+22,20,12))
for nm,cx,cy in [("MUSIC STYLE ARRANGER",375,360),("ONE TOUCH PLAY",490,350),("SPLIT POINT",555,350)]:
    ls=wrap2(nm)
    for k,ln in enumerate(ls): LB.append(L(ln,cx-42,cy-26+k*9,84,8))
    LB.append(P("round_btn",cx-14,cy,32,32))
for i,cx in enumerate([366,426,486,546]):
    LB.append(P("round_btn",cx,399,32,32)); LB.append(L(("VARIATION " if i==0 else "")+str(i+1),cx-12,388,54,8))
for nm,x,w in [("FADE IN/OUT",630,88),("TAP TEMPO",755,80),("SYNCHRO & BREAK",855,80)]:
    LB.append(L(nm,x,335,w+12,9)); LB.append(P("pill_wide",x,352,w,24))
for nm,x,w in [("INTRO & ENDING",720,88),("START/STOP",855,80)]:
    LB.append(L(nm,x,412,w+12,9)); LB.append(P("pill_wide",x,427,w,24))
LB.append('\t</group>')

# =================== RIGHT BLOCK (bottom-right; coords = abs - (1000,997)) ===
RB=['\t<group name="right_block">','\t\t<bounds x="0" y="0" width="1000" height="503"/>',P("bg_right",0,0,1000,503)]
SGcols=[51,107,162,217,272,327,383,438,493]
SG=[("PIANO","SEG0C","0x01"),("GUITAR","SEG0C","0x02"),("MALLET & ORCH PERC","SEG0C","0x04"),("WORLD","SEG0C","0x08"),
    ("STRINGS & VOCAL","SEG0C","0x10"),("BRASS","SEG0C","0x20"),("SAX & WOODWIND","SEG0D","0x01"),("ORGAN & ACCORDION","SEG0D","0x02"),("SOUND EXPLORER","SEG0D","0x04"),
    ("DIGITAL DRAWBAR","SEG0D","0x08"),("ORGAN TABS","SEG0D","0x10"),("ACCORDION REGISTER","SEG0D","0x20"),("PAD","SEG0E","0x01"),
    ("SYNTH","SEG0E","0x02"),("BASS","SEG0E","0x04"),("DRUM KITS","SEG0E","0x08"),("MEMORY",None,None),("EW EXPANSION",None,None)]
RB.append(L("SOUND GROUP",240,32,180,11,TXTH))
for i,(nm,tag,mask) in enumerate(SG):
    cx=SGcols[i%9]; cy=71 if i<9 else 149; ls=wrap2(nm)
    for k,ln in enumerate(ls): RB.append(L(ln,cx-27,cy-13-(len(ls)-1-k)*9,54,8))
    if i in (9,10): RB.append(P("pill_wide",cx-24,cy+2,48,22,tag=tag,mask=mask))
    else: RB.append(P("round_btn",cx-14,cy,32,32,tag=tag,mask=mask)); RB.append(P("green_led",cx-22,cy+22,8,8))
RB.append(L("PART EFFECT",560,32,150,10,TXTH))
for nm,cx in [("SUSTAIN",565),("DIGITAL EFFECT",620),("SOUND DSP",675),("VARIATION",730)]:
    ls=wrap2(nm)
    for k,ln in enumerate(ls): RB.append(L(ln,cx-26,58-(len(ls)-1-k)*9,52,8))
    RB.append(P("round_btn",cx-14,71,32,32))
RB.append(L("GLOBAL EFFECT",560,128,150,10,TXTH))
for nm,cx in [("CHORUS",565),("MULTI",620),("REVERB",675),("MIC",730)]:
    RB.append(L(nm,cx-26,150,52,8)); RB.append(P("round_btn",cx-14,163,32,32))
RB.append(L("SEQUENCER",850,32,90,10,TXTH))
for nm,cx,cy in [("PLAY",845,71),("EASY REC",915,71),("DISK",845,149),("PROGRAM MENUS",915,149)]:
    ls=wrap2(nm)
    for k,ln in enumerate(ls): RB.append(L(ln,cx-26,cy-13-(len(ls)-1-k)*9,52,8))
    RB.append(P("round_btn",cx-14,cy,32,32))
RB.append(L("SD",882,214,40,10,TXTH)); RB.append(P("pill_wide",860,228,60,22))
RB.append(L("TEMPO/PROGRAM",38,300,140,10,TXTH)); RB.append(P("tempo_knob",50,318,110,110))
RB.append(L("TRANSPOSE",213,320,100,10,TXTH)); RB.append(P("pill_wide",213,335,75,24)); RB.append(P("pill_wide",213,405,75,24))
RB.append(L("TECHNI-CHORD",403,258,92,9,TXTH)); RB.append(P("round_btn",416,285,32,32)); RB.append(P("round_btn",476,285,32,32))
RB.append(L("PART SELECT",348,322,92,9,TXTH))
for cx in [360,425,485]: RB.append(P("round_btn",cx,345,32,32))
for cx in [360,425,485]: RB.append(P("round_btn",cx,410,32,32))
RB.append(L("CONDUCTOR",393,454,92,9,TXTH))
RB += [L("BANK VIEW",593,232,82,9), L("NEXT BANK",700,232,82,9), L("PANEL MEMORY",608,255,172,10,TXTH),
       P("panel_memory_dial",565,268,190,190), L("SET",638,354,44,12)]
RB.append(L("CUSTOM PANEL",798,320,72,9)); RB.append(P("round_btn",816,335,32,32))
RB.append(L("CUSTOMIZE",898,320,72,9)); RB.append(P("round_btn",906,335,32,32))
RB.append(L("FAVORITES",843,454,72,9)); RB.append(P("round_btn",860,415,32,32))
RB.append('\t</group>')

VIEWS='''
	<view name="Compact">
		<bounds x="0" y="0" width="2000" height="1500"/>
		<group ref="screen_block"><bounds x="0" y="0" width="2000" height="997"/></group>
		<group ref="left_block"><bounds x="0" y="997" width="1000" height="503"/></group>
		<group ref="right_block"><bounds x="1000" y="997" width="1000" height="503"/></group>
	</view>

	<view name="Full Unit">
		<bounds x="0" y="0" width="4000" height="997"/>
		<group ref="left_block"><bounds x="0" y="247" width="1000" height="503"/></group>
		<group ref="screen_block"><bounds x="1000" y="0" width="2000" height="997"/></group>
		<group ref="right_block"><bounds x="3000" y="247" width="1000" height="503"/></group>
	</view>
'''
o=io.StringIO()
o.write('<?xml version="1.0"?>\n<!-- KN7000 control-panel layout, kn5000 SVG-snippet style, pixel-mapped to the\n')
o.write('     mockup (4000x3000 = 2x). 3 reusable blocks + Compact & Full Unit views.\n     Generated by tools/gen_lay.py. -->\n<mamelayout version="2">\n\n')
o.write("\n".join(E)+"\n\n"+"\n".join(S)+"\n\n"+"\n".join(LB)+"\n\n"+"\n".join(RB)+"\n"+VIEWS+'</mamelayout>\n')
open("/home/fsanches/compartilhado/kn7000_mame/src/mame/layout/kn7000.lay","w").write(o.getvalue())
print(f"WROTE kn7000.lay: {len(E)} elements, {len(TXTS)} labels")
