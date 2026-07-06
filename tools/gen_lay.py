#!/usr/bin/env python3
# Generator for src/mame/layout/kn7000.lay -- KN5000-style SVG-snippet layout,
# arranged pixel-perfectly to the mockup (4000x3000 = 2x the 2000x1500 layout;
# all measured coords are the mockup's /2). Three reusable blocks + two views.
import io, math

PANEL="#38383a"; PANEL2="#232325"; BTN="#54545c"; BTN_D="#262628"
LBTN="#626268"; LBTN_D="#2c2c2e"; MSP="#70747a"; MSP_D="#3c4044"; STROKE="#000"
TXT ='<color red="0.90" green="0.90" blue="0.90"/>'
TXTH='<color red="0.72" green="0.72" blue="0.74"/>'
# --- PanelSwitchClassTable-derived LED cells (PANEL-TEST map; does NOT match normal-operation
# LED behaviour -- verified wrong by probe: GUITAR press lights cpr49 not cpr72. Kept for reference
# only; NOT applied to the layout. Operation LED map must be built empirically. See notes/panel-leds.md ---
LEDMAP={
  ("SEG00","0x40"):"cpl_led8", ("SEG00","0x80"):"cpl_led16", ("SEG01","0x01"):"cpl_led57", ("SEG01","0x02"):"cpl_led49",
  ("SEG01","0x04"):"cpl_led41", ("SEG01","0x08"):"cpl_led33", ("SEG01","0x10"):"cpl_led25", ("SEG01","0x20"):"cpl_led17",
  ("SEG01","0x40"):"cpl_led9", ("SEG01","0x80"):"cpl_led1", ("SEG02","0x01"):"cpl_led58", ("SEG02","0x02"):"cpl_led50",
  ("SEG02","0x04"):"cpl_led42", ("SEG02","0x08"):"cpl_led34", ("SEG02","0x10"):"cpl_led26", ("SEG02","0x20"):"cpl_led18",
  ("SEG02","0x40"):"cpl_led10", ("SEG02","0x80"):"cpl_led2", ("SEG03","0x01"):"cpl_led0", ("SEG03","0x04"):"cpl_led59",
  ("SEG03","0x08"):"cpl_led51", ("SEG03","0x10"):"cpl_led43", ("SEG03","0x20"):"cpl_led35", ("SEG03","0x40"):"cpl_led27",
  ("SEG04","0x01"):"cpl_led19", ("SEG04","0x04"):"cpl_led11", ("SEG04","0x08"):"cpl_led4", ("SEG04","0x10"):"cpl_led3",
  ("SEG05","0x01"):"cpl_led29", ("SEG06","0x20"):"cpl_led12", ("SEG07","0x01"):"cpl_led28", ("SEG07","0x02"):"cpl_led36",
  ("SEG07","0x04"):"cpl_led44", ("SEG07","0x08"):"cpl_led52", ("SEG07","0x10"):"cpl_led60", ("SEG0B","0x40"):"cpl_led5",
  ("SEG0C","0x01"):"cpr_led32", ("SEG0C","0x02"):"cpr_led72", ("SEG0C","0x04"):"cpr_led24", ("SEG0C","0x08"):"cpr_led16",
  ("SEG0C","0x10"):"cpr_led40", ("SEG0C","0x20"):"cpr_led45", ("SEG0C","0x40"):"cpr_led0", ("SEG0D","0x01"):"cpr_led33",
  ("SEG0D","0x02"):"cpr_led34", ("SEG0D","0x04"):"cpr_led25", ("SEG0D","0x08"):"cpr_led17", ("SEG0D","0x10"):"cpr_led41",
  ("SEG0D","0x20"):"cpr_led46", ("SEG0D","0x40"):"cpr_led1", ("SEG0D","0x80"):"cpr_led9", ("SEG0E","0x01"):"cpr_led36",
  ("SEG0E","0x02"):"cpr_led35", ("SEG0E","0x04"):"cpr_led26", ("SEG0E","0x08"):"cpr_led18", ("SEG0E","0x10"):"cpr_led42",
  ("SEG0E","0x20"):"cpr_led47", ("SEG0E","0x40"):"cpr_led2", ("SEG0F","0x01"):"cpr_led39", ("SEG0F","0x02"):"cpr_led7",
  ("SEG0F","0x04"):"cpr_led27", ("SEG0F","0x08"):"cpr_led19", ("SEG0F","0x10"):"cpr_led43", ("SEG0F","0x20"):"cpr_led104",
  ("SEG0F","0x40"):"cpr_led3", ("SEG10","0x01"):"cpr_led96", ("SEG10","0x02"):"cpr_led64", ("SEG10","0x04"):"cpr_led28",
  ("SEG10","0x08"):"cpr_led20", ("SEG10","0x10"):"cpr_led44", ("SEG10","0x20"):"cpr_led105", ("SEG10","0x40"):"cpr_led4",
  ("SEG10","0x80"):"cpr_led12", ("SEG11","0x02"):"cpr_led65", ("SEG11","0x04"):"cpr_led29", ("SEG11","0x08"):"cpr_led21",
  ("SEG11","0x40"):"cpr_led5", ("SEG11","0x80"):"cpr_led13", ("SEG12","0x02"):"cpr_led37", ("SEG12","0x04"):"cpr_led30",
  ("SEG12","0x08"):"cpr_led22", ("SEG12","0x40"):"cpr_led6", ("SEG12","0x80"):"cpr_led14", ("SEG13","0x02"):"cpr_led38",
  ("SEG13","0x04"):"cpr_led31", ("SEG13","0x08"):"cpr_led23", ("SEG13","0x80"):"cpr_led15", ("SEG14","0x04"):"cpr_led88",
  ("SEG14","0x08"):"cpr_led80", ("SEG15","0x04"):"cpr_led89", ("SEG15","0x08"):"cpr_led81", ("SEG1F","0x10"):"cpl_led31",
  ("SEG1F","0x40"):"cpr_led77", ("SEG20","0x01"):"cpr_led77", ("SEG20","0x04"):"cpr_led77", ("SEG20","0x10"):"cpr_led77",
  ("SEG20","0x40"):"cpr_led77",
}
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
def P(ref,x,y,w,h,flip=False,flipy=False,tag=None,mask=None,name=None):
    fl=[]
    if flip: fl.append('flipx="yes"')
    if flipy: fl.append('flipy="yes"')
    o=f'<orientation {" ".join(fl)}/>' if fl else ''
    b=f' inputtag="{tag}" inputmask="{mask}"' if tag else ''
    nm=f' name="{name}"' if name else ''
    return f'\t\t<element ref="{ref}"{nm}{b}>{o}<bounds x="{x}" y="{y}" width="{w}" height="{h}"/></element>'
def L(s,x,y,w,h,color=TXT): return f'\t\t<element ref="{label(s,color)}"><bounds x="{x}" y="{y}" width="{w}" height="{h}"/></element>'
def panel_bg(n,w,h,fill): elem(n,f'<image><data><![CDATA[<svg width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="{fill}"/></svg>]]></data></image>')

# ---- element library (reused kn5000 shapes + kn7000-unique) ----
two("round_btn",29,29,f'<circle stroke="{STROKE}" fill="{BTN}" cx="14.5" cy="14.5" r="14"/>',f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="14.5" cy="14.5" r="14"/>')
two("round_btn_big",42,42,f'<circle stroke="{STROKE}" fill="{BTN}" cx="21" cy="21" r="20.5"/>',f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="21" cy="21" r="20.5"/>')
two("pill_btn",37,21,f'<rect stroke="{STROKE}" fill="{BTN}" x="0.5" y="0.5" width="36" height="20" rx="10"/>',f'<rect stroke="{STROKE}" fill="{BTN_D}" x="0.5" y="0.5" width="36" height="20" rx="10"/>')
two("pill_wide",60,22,f'<rect stroke="{STROKE}" fill="{BTN}" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>',f'<rect stroke="{STROKE}" fill="{BTN_D}" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>')
two("pill_orange",60,22,f'<rect stroke="{STROKE}" fill="#c8641e" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>',f'<rect stroke="{STROKE}" fill="#8a4310" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>')
two("pill_greycyan",60,22,f'<rect stroke="{STROKE}" fill="#4a5c5e" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>',f'<rect stroke="{STROKE}" fill="#33454a" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>')
two("round_red",29,29,f'<circle stroke="{STROKE}" fill="#b02020" cx="14.5" cy="14.5" r="14"/>',f'<circle stroke="{STROKE}" fill="#7c1414" cx="14.5" cy="14.5" r="14"/>')
two("red_led",8,8,'<circle cx="4" cy="4" r="3.5" fill="#3a0000"/>','<circle cx="4" cy="4" r="3.5" fill="#ff2020"/>')
two("green_led",8,8,'<circle cx="4" cy="4" r="3.5" fill="#003a00"/>','<circle cx="4" cy="4" r="3.5" fill="#20ff20"/>')
# page up/down = two halves of a tall pill (rounded outer end, flat inner end)
two("page_up",50,78,f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" d="M 2,77 V 26 A 24 24 0 0 1 26 2 A 24 24 0 0 1 48 26 V 77 Z"/>',f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" d="M 2,77 V 26 A 24 24 0 0 1 26 2 A 24 24 0 0 1 48 26 V 77 Z"/>')
two("page_dn",50,78,f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" d="M 2,1 V 52 A 24 24 0 0 0 26 76 A 24 24 0 0 0 48 52 V 1 Z"/>',f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" d="M 2,1 V 52 A 24 24 0 0 0 26 76 A 24 24 0 0 0 48 52 V 1 Z"/>')
# thin filled line (scaled to bounds) for bookends/brackets
elem("hline",f'<image><data><![CDATA[<svg width="100" height="3"><rect y="1" width="100" height="1.4" fill="#9a9a9c"/></svg>]]></data></image>')
elem("vline",f'<image><data><![CDATA[<svg width="3" height="100"><rect x="1" width="1.4" height="100" fill="#9a9a9c"/></svg>]]></data></image>')
# pill-shaped highlight ring (no fill) to envelop DRAWBAR/ORGAN TABS round buttons
two("pill_ring",70,40,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="none" x="2" y="2" width="66" height="36" rx="18"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="none" x="2" y="2" width="66" height="36" rx="18"/>')
two("bank_wing",90,26,f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" d="M 3,20 C 25,7 65,7 87,20 L 87,24 C 65,11 25,11 3,24 Z"/>',f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" d="M 3,20 C 25,7 65,7 87,20 L 87,24 C 65,11 25,11 3,24 Z"/>')
elem("big_ring",f'<image><data><![CDATA[<svg width="200" height="200"><circle cx="100" cy="100" r="97" fill="none" stroke="{STROKE}" stroke-width="1.5"/></svg>]]></data></image>')
two("demo_btn",42,42,f'<circle stroke="{STROKE}" fill="{BTN}" cx="21" cy="21" r="20.5"/><circle stroke="{STROKE}" fill="none" cx="21" cy="21" r="15.5"/>',f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="21" cy="21" r="20.5"/><circle stroke="{STROKE}" fill="none" cx="21" cy="21" r="15.5"/>')
# LCD soft key: rect + inner vertical divider
two("lcd_soft_key",123,34,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="121" height="32" rx="3"/><line x1="28" y1="1" x2="28" y2="33" stroke="{STROKE}" stroke-width="1.5"/>',
                          f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="121" height="32" rx="3"/><line x1="28" y1="1" x2="28" y2="33" stroke="{STROKE}" stroke-width="1.5"/>')
two("mute_up",55,77,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="53" height="75" rx="3"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="53" height="75" rx="3"/>')
two("mute_down",55,78,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="53" height="76" rx="3"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="53" height="76" rx="3"/>')
two("tall_pill",50,155,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="2" y="2" width="46" height="151" rx="23"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="2" y="2" width="46" height="151" rx="23"/>')
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
    S.append(P("lcd_soft_key",138,yy,123,34,flip=True))
    S.append(P("lcd_soft_key",1740,yy,123,34))
# OTHER PART & FR / HELP
S += [L("OTHER",145,704,52,13), L("PART & FR",131,717,80,13), P("round_btn_big",150,748,42,42), P("red_led",196,752,8,8),
      P("round_btn_big",150,852,42,42), L("HELP",149,838,44,13)]
# CONTRAST tall pill (x282-332)
S += [L("CONTRAST",247,717,120,13), P("tall_pill",282,756,50,155), L("MUTE",342,825,42,13,TXTH),
      P("hline",344,818,32,3), P("vline",344,806,3,14), P("hline",344,843,32,3), P("vline",344,843,3,14)]
# MUTE 1..16 -> PART1..16 on/off pairs (workflow static-RE: 0x2001=on,0x2000=off; normSeg.bit=on/off pair)
# up=part ON (unmute), down=part OFF (mute).  (seg, on_mask, off_mask)
MUTES=[("SEG05",0x10,0x20),("SEG05",0x40,0x80),
       ("SEG08",0x01,0x02),("SEG08",0x04,0x08),("SEG08",0x10,0x20),("SEG08",0x40,0x80),
       ("SEG09",0x01,0x02),("SEG09",0x04,0x08),("SEG09",0x10,0x20),("SEG09",0x40,0x80),
       ("SEG0A",0x01,0x02),("SEG0A",0x04,0x08),("SEG0A",0x10,0x20),("SEG0A",0x40,0x80),
       ("SEG0B",0x01,0x02),("SEG0B",0x04,0x08)]
for i in range(16):
    x=round(378+i*80.4); seg,onm,offm=MUTES[i]
    S.append(P("mute_up",x,756,55,77,tag=seg,mask=f"0x{onm:02x}"))
    S.append(P("mute_down",x,833,55,78,tag=seg,mask=f"0x{offm:02x}"))
# PAGE / DISPLAY HOLD / EXIT
S += [L("PAGE",1679,717,52,13), P("page_up",1680,756,50,78), P("page_dn",1680,834,50,77),
      L("DISPLAY",1789,704,64,13), L("HOLD",1789,717,64,13), P("round_btn_big",1790,748,42,42), P("red_led",1836,752,8,8),
      P("round_btn_big",1790,852,42,42), L("EXIT",1789,838,44,13)]
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
    LB.append(L(nm,cx-16,y-13,42,9)); LB.append(P("round_btn",cx-14,y,32,32)); LB.append(P("green_led",cx+18,y+2,8,8))
RGcols=[581,636,691,746,802,857,912,967]
RG=[("8 & 16 BEAT","SEG00","0x04"),("ROCK & POP","SEG00","0x08"),("BALLAD","SEG00","0x10"),("JAZZ & SWING","SEG00","0x20"),
    ("BALLROOM","SEG00","0x40"),("MOVIE & SHOW","SEG00","0x80"),("ENTERTAINER","SEG01","0x04"),("ORGANIST","SEG01","0x08"),
    ("60s & 70s","SEG01","0x10"),("MODERN DANCE","SEG01","0x20"),("SOUL & R&B","SEG01","0x40"),("COUNTRY & WESTERN","SEG01","0x80"),
    ("MARCH & WALTZ","SEG02","0x04"),("LATIN & WORLD","SEG02","0x08"),("CUSTOM","SEG02","0x10"),("MEMORY","SEG02","0x20")]
LB.append(L("RHYTHM GROUP",700,32,180,11,TXTH))
for i,(nm,tag,mask) in enumerate(RG):
    cx=RGcols[i%8]; cy=90 if i<8 else 162; ls=wrap2(nm)
    for k,ln in enumerate(ls): LB.append(L(ln,cx-28,cy-22-(len(ls)-1-k)*9,56,8))
    LB.append(P("round_btn",cx-16,cy,32,32,tag=tag,mask=mask)); LB.append(P("green_led",cx-4,cy-13,8,8))
LB.append(L("MUSIC STYLIST",418,214,120,10)); LB.append(P("green_led",470,216,8,8)); LB.append(P("pill_orange",441,228,65,22))
LB += [L("DEMO",18,258,44,10), P("music_note",56,252,16,20), P("demo_btn",26,274,42,42),
       L("PERFORMANCE PADS",98,250,172,9,TXTH), P("hline",95,254,26,3), P("hline",247,254,26,3)]
for nm,cx in [("AUTO SETTING",155),("BANK",230),("STOP",305)]:
    LB.append(L(nm,cx-30,262,64,9)); LB.append(P("round_btn",cx-14,274,32,32))
LB.append(P("green_led",151,270,8,8))   # AUTO SETTING LED
padspec=[("msp_corner",0,0),("msp_middle",0,0),("msp_corner",1,0),("msp_corner",0,1),("msp_middle",0,1),("msp_corner",1,1)]
padcol=[(35,94),(129,100),(229,94)]; padrow=[(368,41),(409,42)]   # measured, abutting (no gaps)
for i,(shp,fx,fy) in enumerate(padspec):
    (x,w)=padcol[i%3]; (y,h)=padrow[i//3]
    LB.append(P(shp,x,y,w,h,flip=bool(fx),flipy=bool(fy))); LB.append(L(str(i+1),x+w//2-10,y+h//2-8,20,12))
    if i in (4,5): LB.append(L("SOLO",x+w//2-14,y+h//2+4,28,7,TXTH))
for nm,cx,cy,tg,mk in [("MUSIC STYLE ARRANGER",375,360,None,None),("ONE TOUCH PLAY",490,350,"SEG10","0x01"),("SPLIT POINT",555,350,None,None)]:
    ls=wrap2(nm)
    for k,ln in enumerate(ls): LB.append(L(ln,cx-42,cy-26+k*9,84,8))
    LB.append(P("round_btn",cx-16,cy,32,32,tag=tg,mask=mk))
LB.append(P("green_led",371,350,8,8))   # MUSIC STYLE ARRANGER LED
# L-bracket linking MUSIC STYLE ARRANGER down to VARIATION 1
LB += [P("vline",348,356,3,58), P("hline",348,412,20,3)]
LB.append(L("VARIATION",430,378,90,8,TXTH))
for i,cx in enumerate([366,426,486,546]):
    LB.append(P("round_btn",cx,399,32,32)); LB.append(P("green_led",cx-2,388,8,8)); LB.append(L(str(i+1),cx+8,388,10,8))
for nm,x,w,h,tg,mk in [("FADE IN/OUT",625,105,28,"SEG11","0x01"),("TAP TEMPO",740,105,28,None,None),("SYNCHRO & BREAK",856,105,28,None,None)]:
    LB.append(L(nm,x,340,w,9)); LB.append(P("pill_wide",x,355,w,h,tag=tg,mask=mk))
# FADE in/out LEDs (two, one per half) + SYNCHRO LED
LB += [P("green_led",x+20,364,8,8) for x in [625]] + [P("green_led",625+72,364,8,8)]
LB.append(P("green_led",856+48,364,8,8))   # SYNCHRO & BREAK LED
for nm,x,w,h,shp,tg,mk in [("INTRO & ENDING",740,105,50,"pill_wide","SEG03","0x10"),("START/STOP",856,105,50,"pill_greycyan","SEG00","0x10")]:
    LB.append(L(nm,x,394,w,9)); LB.append(P(shp,x,408,w,h,tag=tg,mask=mk))
# INTRO&ENDING 1/2 LEDs + SEQ RESET/COUNT INTRO labels ; START/STOP 1-4 LEDs
LB += [P("green_led",763,414,8,8), P("green_led",800,414,8,8)]
LB += [L("SEQUENCER",748,452,44,7), L("RESET",752,459,36,7), L("COUNT INTRO",802,452,52,7)]
LB += [P("green_led",867+i*9,414,8,8) for i in range(4)] + [L("BEAT",905,452,28,7)]
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
    cx=SGcols[i%9]; cy=90 if i<9 else 162; ls=wrap2(nm)
    for k,ln in enumerate(ls): RB.append(L(ln,cx-28,cy-22-(len(ls)-1-k)*9,56,8))
    RB.append(P("round_btn",cx-16,cy,32,32,tag=tag,mask=mask)); RB.append(P("green_led",cx-4,cy-13,8,8))
    if i in (9,10): RB.append(P("pill_ring",cx-34,cy-4,68,40))
RB.append(L("PART EFFECT",560,32,150,10,TXTH)); RB += [P("hline",560,37,26,3), P("hline",684,37,26,3)]
for nm,cx in [("SUSTAIN",565),("DIGITAL EFFECT",620),("SOUND DSP",675),("VARIATION",730)]:
    ls=wrap2(nm)
    for k,ln in enumerate(ls): RB.append(L(ln,cx-26,58-(len(ls)-1-k)*9,52,8))
    RB.append(P("round_btn",cx-14,71,32,32)); RB.append(P("green_led",cx-2,60,8,8))
RB.append(L("GLOBAL EFFECT",560,128,150,10,TXTH)); RB += [P("hline",558,133,24,3), P("hline",688,133,24,3)]
for nm,cx in [("CHORUS",565),("MULTI",620),("REVERB",675),("MIC",730)]:
    RB.append(L(nm,cx-26,152,52,8)); RB.append(P("round_btn",cx-14,163,32,32)); RB.append(P("green_led",cx-2,152,8,8))
RB.append(L("SEQUENCER",850,32,90,10,TXTH))
for nm,cx,cy,shp,tg,mk in [("PLAY",845,71,"round_btn",None,None),("EASY REC",915,71,"round_red",None,None),("DISK",845,149,"round_btn","SEG12","0x80"),("PROGRAM MENUS",915,149,"round_btn","SEG12","0x40")]:
    ls=wrap2(nm)
    for k,ln in enumerate(ls): RB.append(L(ln,cx-26,cy-13-(len(ls)-1-k)*9,52,8))
    RB.append(P(shp,cx-16,cy,32,32,tag=tg,mask=mk)); RB.append(P("green_led",cx-4,cy-13,8,8))
# DISK / IN USE indicator + line to DISK button
RB += [L("DISK",798,138,32,8,TXTH), L("IN USE",796,147,36,8,TXTH), P("green_led",812,158,8,8), P("hline",822,162,20,3), L("LOAD",832,183,32,8)]
RB.append(L("SD",882,214,40,10,TXTH)); RB.append(P("pill_orange",860,228,60,22)); RB.append(P("green_led",886,216,8,8)); RB.append(L("LOAD",874,252,32,8))
RB.append(L("TEMPO/PROGRAM",38,300,140,10,TXTH)); RB.append(P("tempo_knob",50,318,110,110)); RB.append(P("green_led",164,336,8,8))
RB.append(L("TRANSPOSE",213,320,100,10,TXTH))
RB += [P("green_led",230,328,8,8), P("green_led",262,328,8,8), P("pill_wide",213,335,75,24,tag="SEG13",mask="0x02")]
RB += [P("green_led",230,398,8,8), P("green_led",262,398,8,8), L("-",232,388,8,8), L("+",264,388,8,8), P("pill_wide",213,405,75,24,tag="SEG13",mask="0x01")]
RB.append(L("TECHNI-CHORD",403,258,92,9,TXTH)); RB += [P("green_led",428,274,8,8), P("round_btn",416,285,32,32), P("green_led",488,274,8,8), P("round_btn",476,285,32,32)]
RB.append(L("PART SELECT",348,322,92,9,TXTH)); RB += [P("hline",348,327,22,3), P("hline",470,327,22,3)]
for cx in [360,425,485]: RB += [P("green_led",cx+12,334,8,8), P("round_btn",cx,345,32,32)]
for cx in [360,425,485]: RB += [P("green_led",cx+12,399,8,8), P("round_btn",cx,410,32,32)]
RB.append(L("CONDUCTOR",393,454,92,9,TXTH)); RB += [P("hline",360,458,26,3), P("hline",470,458,26,3)]
RB += [L("BANK VIEW",583,220,72,8), P("green_led",585,230,8,8), P("bank_wing",580,238,90,26),
       L("NEXT BANK",690,220,72,8), P("bank_wing",685,238,90,26), L("PANEL MEMORY",608,255,172,10,TXTH),
       P("panel_memory_dial",565,268,190,190), L("SET",638,354,44,12)]
# PANEL MEMORY numbers 1-8 around the dial (center 660,363; r~95)
import math as _m
for _i,_lab in enumerate(["1","2","3","4","5","6","7","8"]):
    _a=_m.radians(-90+ (_i)*45 +200)
    _x=660+int(88*_m.cos(_a)); _y=363+int(88*_m.sin(_a))
    RB.append(L(_lab,_x-4,_y-4,8,8,TXTH))
RB.append(P("big_ring",800,318,148,148))
RB += [L("CUSTOM",804,318,52,8), L("PANEL",806,327,48,8), P("green_led",800,336,8,8), P("round_btn_big",812,344,42,42)]
RB += [L("CUSTOMIZE",895,330,60,8), P("green_led",946,340,8,8), P("round_btn_big",900,348,42,42)]
RB += [L("FAVORITES",840,436,72,8), P("green_led",912,438,8,8), P("round_btn_big",858,398,42,42)]
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

	<!-- Zoomed single-block views (each fills the window) for detailed layout review -->
	<view name="Screen Block">
		<bounds x="0" y="0" width="2000" height="997"/>
		<group ref="screen_block"><bounds x="0" y="0" width="2000" height="997"/></group>
	</view>

	<view name="Left Block">
		<bounds x="0" y="0" width="1000" height="503"/>
		<group ref="left_block"><bounds x="0" y="0" width="1000" height="503"/></group>
	</view>

	<view name="Right Block">
		<bounds x="0" y="0" width="1000" height="503"/>
		<group ref="right_block"><bounds x="0" y="0" width="1000" height="503"/></group>
	</view>
'''
o=io.StringIO()
o.write('<?xml version="1.0"?>\n<!-- KN7000 control-panel layout, kn5000 SVG-snippet style, pixel-mapped to the\n')
o.write('     mockup (4000x3000 = 2x). 3 reusable blocks + Compact & Full Unit views.\n     Generated by tools/gen_lay.py. -->\n<mamelayout version="2">\n\n')
o.write("\n".join(E)+"\n\n"+"\n".join(S)+"\n\n"+"\n".join(LB)+"\n\n"+"\n".join(RB)+"\n"+VIEWS+'</mamelayout>\n')
open("/home/fsanches/compartilhado/kn7000_mame/src/mame/layout/kn7000.lay","w").write(o.getvalue())
print(f"WROTE kn7000.lay: {len(E)} elements, {len(TXTS)} labels")
