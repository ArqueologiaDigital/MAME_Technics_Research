#!/usr/bin/env python3
# Generator for src/mame/layout/kn7000.lay -- KN5000-style SVG-snippet layout,
# arranged pixel-perfectly to the mockup (4000x3000 = 2x the 2000x1500 layout;
# all measured coords are the mockup's /2). Three reusable blocks + two views.
import io, math, os, re

PANEL="#38383a"; PANEL2="#232325"; BTN="#54545c"; BTN_D="#262628"
LBTN="#626268"; LBTN_D="#2c2c2e"; MSP="#70747a"; MSP_D="#3c4044"; STROKE="#000"
TXT ='<color red="0.90" green="0.90" blue="0.90"/>'
TXTH='<color red="0.72" green="0.72" blue="0.74"/>'
# PANEL_LED: authoritative button -> indicator-LED map, computed from the firmware's own
# PanelSwitchClassTable (0x4860C9F4; switch#=normSeg*8+bit -> [LED row, col reg]) + the LED
# row-remap table (0x48615058 -> panel_led_frame addr) => led = (remap[row]&0x3f)*8 + col_index,
# board = cpl if remap[row]&0xc0 else cpr. VALIDATED live: genre0->cpl_led2, ROCK&POP->cpl_led18,
# PIANO->cpr_led44 (all exact). rows 14-19 (SEG12-15 upper bits) are derived, spot-check pending.
PANEL_LED={
  ("SEG00","0x40"):"cpl_led8", ("SEG00","0x80"):"cpl_led16", ("SEG01","0x01"):"cpl_led57",
  ("SEG01","0x02"):"cpl_led49", ("SEG01","0x04"):"cpl_led41", ("SEG01","0x08"):"cpl_led33",
  ("SEG01","0x10"):"cpl_led25", ("SEG01","0x20"):"cpl_led17", ("SEG01","0x40"):"cpl_led9",
  ("SEG01","0x80"):"cpl_led1", ("SEG02","0x01"):"cpl_led58", ("SEG02","0x02"):"cpl_led50",
  ("SEG02","0x04"):"cpl_led42", ("SEG02","0x08"):"cpl_led34", ("SEG02","0x10"):"cpl_led26",
  ("SEG02","0x20"):"cpl_led18", ("SEG02","0x40"):"cpl_led10", ("SEG02","0x80"):"cpl_led2",
  ("SEG03","0x01"):"cpl_led0", ("SEG03","0x04"):"cpl_led59", ("SEG03","0x08"):"cpl_led51",
  ("SEG03","0x10"):"cpl_led43", ("SEG03","0x20"):"cpl_led35", ("SEG03","0x40"):"cpl_led27",
  ("SEG04","0x01"):"cpl_led19", ("SEG04","0x04"):"cpl_led11", ("SEG04","0x08"):"cpl_led4",
  ("SEG04","0x10"):"cpl_led3", ("SEG05","0x01"):"cpl_led29", ("SEG06","0x20"):"cpl_led12",
  ("SEG07","0x01"):"cpl_led28", ("SEG07","0x02"):"cpl_led36", ("SEG07","0x04"):"cpl_led44",
  ("SEG07","0x08"):"cpl_led52", ("SEG07","0x10"):"cpl_led60", ("SEG0B","0x40"):"cpl_led5",
  ("SEG0C","0x01"):"cpr_led32", ("SEG0C","0x02"):"cpr_led72", ("SEG0C","0x04"):"cpr_led24",
  ("SEG0C","0x08"):"cpr_led16", ("SEG0C","0x10"):"cpr_led40", ("SEG0C","0x20"):"cpr_led45",
  ("SEG0C","0x40"):"cpr_led0", ("SEG0D","0x01"):"cpr_led33", ("SEG0D","0x02"):"cpr_led34",
  ("SEG0D","0x04"):"cpr_led25", ("SEG0D","0x08"):"cpr_led17", ("SEG0D","0x10"):"cpr_led41",
  ("SEG0D","0x20"):"cpr_led46", ("SEG0D","0x40"):"cpr_led1", ("SEG0D","0x80"):"cpr_led9",
  ("SEG0E","0x01"):"cpr_led36", ("SEG0E","0x02"):"cpr_led35", ("SEG0E","0x04"):"cpr_led26",
  ("SEG0E","0x08"):"cpr_led18", ("SEG0E","0x10"):"cpr_led42", ("SEG0E","0x20"):"cpr_led47",
  ("SEG0E","0x40"):"cpr_led2", ("SEG0F","0x01"):"cpr_led39", ("SEG0F","0x02"):"cpr_led7",
  ("SEG0F","0x04"):"cpr_led27", ("SEG0F","0x08"):"cpr_led19", ("SEG0F","0x10"):"cpr_led43",
  ("SEG0F","0x20"):"cpr_led104", ("SEG0F","0x40"):"cpr_led3", ("SEG10","0x01"):"cpr_led96",
  ("SEG10","0x02"):"cpr_led64", ("SEG10","0x04"):"cpr_led28", ("SEG10","0x08"):"cpr_led20",
  ("SEG10","0x10"):"cpr_led44", ("SEG10","0x20"):"cpr_led105", ("SEG10","0x40"):"cpr_led4",
  ("SEG10","0x80"):"cpr_led12", ("SEG11","0x02"):"cpr_led65", ("SEG11","0x04"):"cpr_led29",
  ("SEG11","0x08"):"cpr_led21", ("SEG11","0x40"):"cpr_led5", ("SEG11","0x80"):"cpr_led13",
  ("SEG12","0x02"):"cpr_led37", ("SEG12","0x04"):"cpr_led30", ("SEG12","0x08"):"cpr_led22",
  ("SEG12","0x40"):"cpr_led6", ("SEG12","0x80"):"cpr_led14", ("SEG13","0x02"):"cpr_led38",
  ("SEG13","0x04"):"cpr_led31", ("SEG13","0x08"):"cpr_led23", ("SEG13","0x80"):"cpr_led15",
  ("SEG14","0x04"):"cpr_led88", ("SEG14","0x08"):"cpr_led80", ("SEG15","0x04"):"cpr_led89",
  ("SEG15","0x08"):"cpr_led81",
}
# The genre / sound-group / effect / sequencer loops below look up their indicator LED from
# this same authoritative map (aliased), replacing the old empirical/bank-B guesses.
GENRE_LED = PANEL_LED
OPLED = PANEL_LED

# --- LED purpose comments (KN5000 style), GENERATED so they can never drift from the binding -------
# Each panel LED indicates one button/function. Rather than hand-writing <!-- comments --> in the .lay
# (which would rot the moment a binding changes), we derive the purpose of every LED from the SINGLE
# source of truth -- the driver's INPUT_PORTS (which (normSeg,bit) is which button) -- composed with
# the very same PANEL_LED[(normSeg,mask)] -> led-name map that forms the layout binding. The comment
# is looked up by the LED's OUTPUT NAME (the thing MAME actually drives), so comment and binding are
# emitted from one key. Regenerating the layout re-derives all comments; a button rename or LED remap
# updates the comment automatically. See the annotate pass at the tail of this file.
def _load_btn_names():
    # Parse the driver INPUT_PORTS for every panel button's silk name, keyed BOTH ways:
    #   BTN_CP  = {(CP-port tag, "0xNN"): name}    -- matches the layout's final inputtag/inputmask
    #   BTN_SEG = {("SEGxx" normSeg, "0xNN"): name} -- matches the PANEL_LED (SEGxx,mask) LED keys
    kncpp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "mame", "matsushita", "kn7000.cpp")
    cp2ns = {"CPL_SEG0":0x00,"CPL_SEG1":0x01,"CPL_SEG2":0x02,"CPL_SEG3":0x03,"CPL_SEG4":0x04,
             "CPL_SEG6":0x06,"CPL_SEG7":0x07,"CPC_SEG5":0x05,"CPC_SEG8":0x08,"CPC_SEG9":0x09,
             "CPC_SEG10":0x0a,"CPC_SEG11":0x0b,"CPR_SEG0":0x0c,"CPR_SEG1":0x0d,"CPR_SEG2":0x0e,
             "CPR_SEG3":0x0f,"CPR_SEG4":0x10,"CPR_SEG5":0x11,"CPR_SEG6":0x12,"CPR_SEG7":0x13,
             "CPR_SEG8":0x14,"CPR_SEG9":0x15}
    by_cp = {}; by_seg = {}; cp = None
    for ln in open(kncpp).read().splitlines():
        m = re.search(r'PORT_START\("(CP[LCR]_SEG\d+)"\)', ln)
        if m: cp = m.group(1); continue
        if "PORT_START" in ln: cp = None; continue           # left the CP scan-matrix ports
        if cp is None: continue
        mb = re.search(r'PORT_BIT\(\s*(0x[0-9a-fA-F]+).*?PORT_NAME\("([^"]*)"\)', ln)
        if mb:
            mask = "0x%02x" % int(mb.group(1), 16)
            nm = re.sub(r'\s*\(SW\d+\)\s*$', '', mb.group(2)).strip()
            by_cp[(cp, mask)] = nm
            by_seg[("SEG%02X" % cp2ns[cp], mask)] = nm
    return by_cp, by_seg
BTN_CP, BTN_NAME = _load_btn_names()
LED_PURPOSE = {}
for _k, _led in PANEL_LED.items():                            # the 91 LEDs bound via PANEL_LED
    if BTN_NAME.get(_k): LED_PURPOSE[_led] = BTN_NAME[_k]
# LEDs whose placement binds a LITERAL name (empirically corrected or state/beat indicators, i.e. not
# reachable through PANEL_LED). Where the LED indicates a real button, derive from BTN_NAME so it still
# tracks a rename; otherwise use a static description.
LED_PURPOSE.setdefault("cpr_led97", BTN_NAME.get(("SEG0E", "0x40"), "FAVORITES"))   # real FAVORITES LED (PANEL_LED's cpr_led2 is dead)
LED_PURPOSE.setdefault("cpr_led63", BTN_NAME.get(("SEG0F", "0x02"), "CONDUCTOR"))   # CONDUCTOR (SEG0F.02); cpr_led64/65 come via PANEL_LED
LED_PURPOSE.update({
    "cpl_led20": "APC/SEQ VOLUME (state LED, no button)",
    "cpl_led24": "BEAT 1", "cpl_led32": "BEAT 2", "cpl_led40": "BEAT 3", "cpl_led48": "BEAT 4",
})
def _mk_comment(text):
    # XML comments may not contain "--" nor end with "-".
    return "<!-- %s -->" % text.replace("--", "-").rstrip("-").strip()

E=[]; TXTS={}; _TXT_NAMES=set()
def elem(n,b): E.append(f'\t<element name="{n}">{b}</element>')
def two(n,w,h,s0,s1):
    E.append(f'\t<element name="{n}">\n\t\t<image state="0"><data><![CDATA[<svg width="{w}" height="{h}">{s0}</svg>]]></data></image>\n'
             f'\t\t<image state="1"><data><![CDATA[<svg width="{w}" height="{h}">{s1}</svg>]]></data></image>\n\t</element>')
def xesc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def _txt_slug(s):
    # Semantic element name derived from the label text, e.g. "FILL IN" -> "fill_in_text",
    # "PART & FR" -> "part_and_fr_text", "+" -> "plus_text".
    t=s.strip()
    if   t=="+": t="plus"
    elif t=="-": t="minus"
    else:        t=t.replace("&"," and ")
    t=re.sub(r'[^0-9a-z]+','_',t.lower()).strip('_')
    return (t or "sym")+"_text"
def label(s,color=TXT):
    k=(s,color)
    if k not in TXTS:
        base=_txt_slug(s); n=base; i=2
        while n in _TXT_NAMES:                 # disambiguate same-slug labels (e.g. differing color)
            n=f"{base[:-5]}_{i}_text"; i+=1
        _TXT_NAMES.add(n); TXTS[k]=n
        E.append(f'\t<element name="{n}"><text string="{xesc(s)}">{color}</text></element>')
    return TXTS[k]
def P(ref,x,y,w,h,flip=False,flipy=False,tag=None,mask=None,name=None):
    # Match the mockup's round-button size: the mockup draws them ~37px dia vs the layout's 32px
    # (measured over the RHYTHM GROUP, centres already aligned). Grow round_btn 32->37, centre kept.
    if ref=="round_btn" and w==32 and h==32:
        x-=2; y-=2; w=37; h=37
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
two("round_btn",29,29,f'<circle stroke="{STROKE}" fill="{BTN}" cx="14.5" cy="14.5" r="14"/><circle stroke="{STROKE}" fill="none" cx="14.5" cy="14.5" r="9.5"/>',f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="14.5" cy="14.5" r="14"/><circle stroke="{STROKE}" fill="none" cx="14.5" cy="14.5" r="9.5"/>')
two("round_btn_big",42,42,f'<circle stroke="{STROKE}" fill="{BTN}" cx="21" cy="21" r="20.5"/>',f'<circle stroke="{STROKE}" fill="{BTN_D}" cx="21" cy="21" r="20.5"/>')
two("pill_btn",37,21,f'<rect stroke="{STROKE}" fill="{BTN}" x="0.5" y="0.5" width="36" height="20" rx="10"/>',f'<rect stroke="{STROKE}" fill="{BTN_D}" x="0.5" y="0.5" width="36" height="20" rx="10"/>')
two("pill_wide",60,22,f'<rect stroke="{STROKE}" fill="{BTN}" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>',f'<rect stroke="{STROKE}" fill="{BTN_D}" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>')
two("pill_orange",60,22,f'<rect stroke="{STROKE}" fill="#c8641e" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>',f'<rect stroke="{STROKE}" fill="#8a4310" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>')
two("pill_greycyan",60,22,f'<rect stroke="{STROKE}" fill="#4a5c5e" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>',f'<rect stroke="{STROKE}" fill="#33454a" x="1.5" y="1.5" width="57" height="19" rx="9.5"/>')
two("round_red",29,29,f'<circle stroke="{STROKE}" fill="#b02020" cx="14.5" cy="14.5" r="14"/><circle stroke="{STROKE}" fill="none" cx="14.5" cy="14.5" r="9.5"/>',f'<circle stroke="{STROKE}" fill="#7c1414" cx="14.5" cy="14.5" r="14"/><circle stroke="{STROKE}" fill="none" cx="14.5" cy="14.5" r="9.5"/>')
two("red_led",8,8,'<circle cx="4" cy="4" r="3.5" fill="#3a0000"/>','<circle cx="4" cy="4" r="3.5" fill="#ff2020"/>')
two("green_led",8,8,'<circle cx="4" cy="4" r="3.5" fill="#003a00"/>','<circle cx="4" cy="4" r="3.5" fill="#20ff20"/>')
# tiny down-pointing triangle for the 3 keyboard split-point indicators (Felipe)
elem("split_arrow",'<image><data><![CDATA[<svg width="12" height="10"><path d="M 1,1 L 11,1 L 6,9 Z" fill="#54545c" stroke="#000"/></svg>]]></data></image>')
# ---- split-pill halves: two clickable halves form one divided pill (KN5000 pattern). Scale to bounds. ----
# horizontal (-/+ , in/out, 1/2): left half rounded-left + flat-right, right half mirrored.
two("half_l",40,22,f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" d="M 40,1 L 11,1 A 10 10 0 0 0 11,21 L 40,21 Z"/>',f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" d="M 40,1 L 11,1 A 10 10 0 0 0 11,21 L 40,21 Z"/>')
two("half_r",40,22,f'<path transform="translate(40,0) scale(-1,1)" stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" d="M 40,1 L 11,1 A 10 10 0 0 0 11,21 L 40,21 Z"/>',f'<path transform="translate(40,0) scale(-1,1)" stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" d="M 40,1 L 11,1 A 10 10 0 0 0 11,21 L 40,21 Z"/>')
# vertical (CONTRAST up/down): top half rounded-top + flat-bottom, bottom half mirrored.
two("half_t",22,40,f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" d="M 1,40 L 1,11 A 10 10 0 0 1 21,11 L 21,40 Z"/>',f'<path stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" d="M 1,40 L 1,11 A 10 10 0 0 1 21,11 L 21,40 Z"/>')
two("half_b",22,40,f'<path transform="translate(0,40) scale(1,-1)" stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" d="M 1,40 L 1,11 A 10 10 0 0 1 21,11 L 21,40 Z"/>',f'<path transform="translate(0,40) scale(1,-1)" stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" d="M 1,40 L 1,11 A 10 10 0 0 1 21,11 L 21,40 Z"/>')
# ---- SD-card transport buttons (48x30, icon baked in) ----
two("sd_stop",48,30,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="46" height="28" rx="4"/><rect x="19" y="10" width="10" height="10" fill="#d8d8d8"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="46" height="28" rx="4"/><rect x="19" y="10" width="10" height="10" fill="#d8d8d8"/>')
two("sd_play",48,30,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="46" height="28" rx="4"/><path d="M 15,9 L 15,21 L 24,15 Z" fill="#d8d8d8"/><rect x="28" y="9" width="3" height="12" fill="#d8d8d8"/><rect x="33" y="9" width="3" height="12" fill="#d8d8d8"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="46" height="28" rx="4"/><path d="M 15,9 L 15,21 L 24,15 Z" fill="#d8d8d8"/><rect x="28" y="9" width="3" height="12" fill="#d8d8d8"/><rect x="33" y="9" width="3" height="12" fill="#d8d8d8"/>')
two("sd_skipb",48,30,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="46" height="28" rx="4"/><path d="M 22,9 L 22,21 L 14,15 Z M 32,9 L 32,21 L 24,15 Z" fill="#d8d8d8"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="46" height="28" rx="4"/><path d="M 22,9 L 22,21 L 14,15 Z M 32,9 L 32,21 L 24,15 Z" fill="#d8d8d8"/>')
two("sd_skipf",48,30,f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN}" x="1" y="1" width="46" height="28" rx="4"/><path d="M 16,9 L 16,21 L 24,15 Z M 26,9 L 26,21 L 34,15 Z" fill="#d8d8d8"/>',f'<rect stroke="{STROKE}" stroke-width="1.5" fill="{BTN_D}" x="1" y="1" width="46" height="28" rx="4"/><path d="M 16,9 L 16,21 L 24,15 Z M 26,9 L 26,21 L 34,15 Z" fill="#d8d8d8"/>')
# pair helpers: emit two bound half-buttons (one split pill) + optional per-half labels
def pair_h(seg,ma,mb,x,y,w,h,la="",lb="",seg2=None):
    sb=seg2 or seg   # bank A: some split pairs (INTRO&ENDING, TRANSPOSE, R1/R2 OCT) straddle two SEGs
    r=[P("half_l",x,y,w//2,h,tag=seg,mask=ma),P("half_r",x+w-w//2,y,w//2,h,tag=sb,mask=mb)]
    if la: r.append(L(la,x+w//4-14,y+h//2-6,28,12))
    if lb: r.append(L(lb,x+3*w//4-14,y+h//2-6,28,12))
    return r
def pair_v(seg,ma,mb,x,y,w,h,la="",lb="",seg2=None):
    sb=seg2 or seg   # top/bottom halves may straddle two SEGs (e.g. CONTRAST +/-)
    if seg: r=[P("half_t",x,y,w,h//2,tag=seg,mask=ma),P("half_b",x,y+h-h//2,w,h//2,tag=sb,mask=mb)]
    else:   r=[P("half_t",x,y,w,h//2),P("half_b",x,y+h-h//2,w,h//2)]   # seg=None -> unbound (bits unknown)
    if la: r.append(L(la,x+w//2-14,y+h//4-6,28,12))
    if lb: r.append(L(lb,x+w//2-14,y+3*h//4-6,28,12))
    return r
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
# ESQ1-style draggable slider parts: transparent click-area, rail track, and the moving knob.
elem("inv_rect",'<rect><color red="0" green="0" blue="0" alpha="0"/></rect>')
elem("fader_rail",'<rect><color red="0.13" green="0.13" blue="0.14"/></rect>')
elem("slider_knob",f'<rect><bounds x="0" y="0" width="30" height="18"/><color red="0.34" green="0.34" blue="0.37"/></rect><rect><bounds x="2" y="8" width="26" height="2.5"/><color red="0.9" green="0.9" blue="0.92"/></rect>')
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
# LCD-flanking soft-keys: 5 rows down each side of the display, listed top->bottom as
# (left-SEG, left-mask, right-SEG, right-mask). These are CONTEXT-DEPENDENT keys -- the real unit
# prints NO silkscreen text beside them (their function is whatever the current screen shows), so the
# panel is blank there. Left column wires to SEG00 (-> the driver's LCDL 1-5); right column to
# SEG11-13. Both columns are bound and clickable and work in the driver. These are the physical
# "LCD LEFT/RIGHT 1-5" soft-keys -- context-dependent, NOT any fixed-function / keyboard-part button.
LCD_SOFTKEYS=[("SEG00","0x02","SEG11","0x10"),("SEG00","0x08","SEG11","0x20"),
              ("SEG00","0x20","SEG13","0x01"),("SEG00","0x01","SEG12","0x01"),
              ("SEG00","0x04","SEG11","0x01")]
for yy,(ls,lm,rs,rm) in zip([205,294,383,472,561], LCD_SOFTKEYS):
    S.append(P("lcd_soft_key",138,yy,123,34,flip=True,tag=ls,mask=lm))
    S.append(P("lcd_soft_key",1740,yy,123,34,tag=rs,mask=rm))
# OTHER PART & FR / HELP
# bank A (HELP-info verified, panel_family_2.txt): OTHER PART & FR = SEG05 0x01, HELP = SEG05 0x02
# (HELP cross-confirmed by the STAGE-1 INPUT_PORTS auto-namer).
S += [L("OTHER",145,717,52,13), L("PART & FR",131,730,80,13), P("round_btn_big",150,748,42,42,tag="SEG05",mask="0x01"), P("red_led",196,752,8,8),
      P("round_btn_big",150,852,42,42,tag="SEG05",mask="0x02"), L("HELP",149,838,44,13)]
# CONTRAST tall pill (x282-332)
# CONTRAST up/down: bits UNKNOWN, left UNBOUND. (The earlier SEG08 0x40/0x80 guess was proven WRONG by the
# 2026-07-08 HELP-info sweep -- those are SOUND CONTROLLER MODE/RESET. CONTRAST has no HELP screen, so its
# real bits are still unidentified.)
# CONTRAST +/- : GUESS #2 (Felipe: guess #1 SEG16/17 was wrong). Use the OTHER complete remap pair
# (ev1010,ev1011): + = SEG19 0x01 (ev1010), - = SEG1A 0x01 (ev1011). remap table 0x48589150.
S += [L("CONTRAST",247,730,120,13)] + pair_v("SEG19","0x01","0x01",282,756,50,155,"+","-",seg2="SEG1A") + [L("MUTE",342,825,42,13,TXTH),
      P("hline",344,818,32,3), P("vline",344,806,3,14), P("hline",344,843,32,3), P("vline",344,843,3,14)]
# MUTE 1..16 -> PART 1..16 on/off pairs. up=part ON (unmute)=on_mask, down=part OFF (mute)=off_mask.
# SOLVED 2026-07-07 by the emulator "press-count encoding" method (press bit N times -> its part's
# PT1-16 mixer level drops by N; one snapshot decodes the whole map). The matrix is perfectly regular:
# SEG04=parts 1-4, SEG05=parts 5-8, SEG06=parts 9-12, SEG07=parts 13-16; within each seg the four
# up/down pairs are (0x01,0x02),(0x04,0x08),(0x10,0x20),(0x40,0x80) for the four consecutive parts.
# (Parts 1-15 confirmed on the mixer; part 16 = SEG07 0x40/0x80 inferred from the exact pattern.)
# The old SEG08/09/0A/0B guesses were all wrong -- SEG08/09 are function keys, SEG0A/0B move nothing.
# NB: this is the layout-SEG vs firmware-normSeg remap in action -- normSeg06 is "APC/rhythm" in the
# dispatch table, but layout SEG04-07 physically wire to the part-mute matrix.
# bank A: 16 parts, up=part ON (ev2001) / down=part OFF (ev2000). Parts 1-2=SEG05 hi nibble,
# 3-6=SEG08, 7-10=SEG09, 11-14=SEG0A, 15-16=SEG0B. (seg, on_mask, off_mask) per part.
MUTES=[("SEG05",0x10,0x20),("SEG05",0x40,0x80),("SEG08",0x01,0x02),("SEG08",0x04,0x08),
       ("SEG08",0x10,0x20),("SEG08",0x40,0x80),("SEG09",0x01,0x02),("SEG09",0x04,0x08),
       ("SEG09",0x10,0x20),("SEG09",0x40,0x80),("SEG0A",0x01,0x02),("SEG0A",0x04,0x08),
       ("SEG0A",0x10,0x20),("SEG0A",0x40,0x80),("SEG0B",0x01,0x02),("SEG0B",0x04,0x08)]
FN_SEGS=set()   # (all 16 mute cells are real now; no function-seg overlaps left to unbind)
for i in range(16):
    x=round(378+i*80.4); seg,onm,offm=MUTES[i]
    ut,um=(None,None) if seg in FN_SEGS else (seg,f"0x{onm:02x}")
    dt,dm=(None,None) if seg in FN_SEGS else (seg,f"0x{offm:02x}")
    S.append(P("mute_up",x,756,55,77,tag=ut,mask=um))
    S.append(P("mute_down",x,833,55,78,tag=dt,mask=dm))
# PAGE / DISPLAY HOLD / EXIT
# PAGE up/down (CPC-board pair). BITS UNVERIFIED -- best-guess SEG08 0x01 (up) / 0x02 (down); no HELP
# screen for PAGE. *** FLAG FOR REVIEW ***
# PAGE up/down : GUESS #2 (Felipe: guess #1 SEG18/19 was wrong). Use the complete remap pair
# (ev1004,ev1005): up = SEG16 0x01 (ev1005), down = SEG17 0x01 (ev1004). remap table 0x48589150.
S += [L("PAGE",1679,730,52,13), P("page_up",1680,756,50,78,tag="SEG16",mask="0x01"), P("page_dn",1680,834,50,77,tag="SEG17",mask="0x01"),
      # bank A: DISPLAY HOLD = SEG0B 0x40 (HELP-info + STAGE-1 cross-confirmed). LED cpl_led5 (state identity).
      L("DISPLAY",1777,717,64,13), L("HOLD",1777,730,64,13), P("round_btn_big",1790,748,42,42,tag="SEG0B",mask="0x40"), P("red_led",1836,752,8,8,name=PANEL_LED.get(("SEG0B","0x40"))),
      # bank A: EXIT = SEG0B 0x80 (HELP-info verified, panel_family_2.txt).
      P("round_btn_big",1790,852,42,42,tag="SEG0B",mask="0x80"), L("EXIT",1789,838,44,13)]
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
# 4 volume sliders -- ESQ1-style DRAGGABLE placeholders (control targets TBD, per user). Each = rail
# + transparent click-area (id, the drag region) + animated knob (id, <animate> maps the PORT_ADJUSTER
# value to the knob's Y position). The <script> at the bottom wires the drag via the ESQ1 slider library.
SLPORT={"MAIN":"VOL_MAIN","APC/SEQ":"VOL_APCSEQ","MIC":"VOL_MIC","LINE IN":"VOL_LINEIN"}
SLDISP={"APC/SEQ":"APC/SEQUENCER"}   # display name (Felipe: real panel spells it out); key stays "APC/SEQ"
for nm,cx,y,h in [("MAIN",100,51,130),("APC/SEQ",166,51,130),("MIC",261,68,108),("LINE IN",304,68,108)]:
    disp=SLDISP.get(nm,nm); lw=76 if len(disp)>8 else 48
    LB.append(L(disp,cx-lw//2,y-14,lw,9,TXTH)); LB.append(L("VOLUME",cx-24,y-5,48,9,TXTH))
    port=SLPORT[nm]; sid=port.lower(); x=cx-15; w=30; kh=18
    LB.append(P("fader_rail",cx-3,y+kh//2,6,h-kh))
    # APC/SEQUENCER VOLUME indicator LED (GREEN) = the firmware's own matrix LED cpl_led20 (CPL reg2, SEG4
    # column = bit4), driven the normal way via panel_led_frame -- NOT a driver-side RAM hack. Identified
    # from the service-manual CPL schematic (DIAGRAM-15 p128): LED D1179 "APC/SEQENCER", green (LNJ382GKGX02),
    # in the reg2 row (anchored by SYNCHRO & BREAK = D1115 = cpl_led16, firmware-validated) at SEG4 -> reg2*8+4
    # = cpl_led20. It is one of the two CPL LEDs with no associated button (the other is a split-point LED);
    # in the Panel SW&LED self-test only DEMO lights it. Placed by the slider label.
    if nm=="APC/SEQ": LB.append('\t\t<element name="cpl_led20" ref="green_led"><bounds x="%d" y="%d" width="8" height="8"/></element>' % (cx+18, y+2))
    LB.append(f'\t\t<element id="{sid}_click" ref="inv_rect"><bounds x="{x}" y="{y}" width="{w}" height="{h}"/></element>')
    LB.append(f'\t\t<element id="{sid}_knob" ref="slider_knob"><animate inputtag="{port}" inputmask="0xffff"/><bounds state="100" x="{x}" y="{y}" width="{w}" height="{kh}"/><bounds state="0" x="{x}" y="{y+h-kh}" width="{w}" height="{kh}"/></element>')
LB.append(L("AUTO PLAY CHORD",418,36,150,10,TXTH))
# AUTO PLAY CHORD: MODE = SEG03 0x02 (fresh-boot scr:pixel dump 2026-07-07: opens the "APC SELECT"
# screen BASIC/FINGERED/PIANIST; was decorative). The top OFF/ON had been guessed SEG06 0x08 from the
# dispatch table's normSeg06=APC, but SEG06 0x08 is empirically PART 10 mute-down (now in MUTES), so
# OFF/ON is unbound again (its real bit is TBD; the normSeg->layout-SEG remap is not identity here).
# AUTO PLAY CHORD (MODE/OFF-ON) + SOUND ARRANGER (SET/OFF-ON) -- bank A (from /tmp/bankA_dump.txt SEG07):
# APC MODE=SEG07 0x02 (APC/CHORD FINDER), APC OFF/ON=SEG07 0x08, SOUND ARRANGER SET=SEG07 0x04 (app-open),
# SOUND ARRANGER OFF/ON=SEG07 0x10.
for nm,cx,y,tg,mk in [("MODE",447,54,"SEG07","0x02"),("OFF/ON",505,54,"SEG07","0x08"),("SET",447,139,"SEG07","0x04"),("OFF/ON",505,139,"SEG07","0x10")]:
    LB.append(L(nm,cx-16,y-13,42,9)); LB.append(P("round_btn",cx-14,y,32,32,tag=tg,mask=mk))
    # LED colours (Felipe): GREEN = APC MODE(0x02), Sound Arranger SET(0x04)+OFF/ON(0x10); RED = APC OFF/ON(0x08)
    LB.append(P("green_led" if mk in ("0x02","0x04","0x10") else "red_led",cx+18,y+2,8,8,name=OPLED.get((tg,mk))))
RGcols=[581,636,691,746,802,857,912,967]
# RHYTHM GROUP = the 16 genres. EMPIRICALLY VERIFIED (2026-07-07, snapshot probe +
# user real-machine testing): the genre-select bits are SEG00/SEG01/SEG02 bit b2..b7
# -> genres 0..15 in order (SEG02 stops at b5). Snapshots confirm SEG00 0x04=8&16 BEAT,
# 0x08=ROCK&POP, 0x10=BALLAD, 0x20=JAZZ&SWING, 0x40=BALLROOM, 0x80=MOVIE&SHOW; SEG01
# 0x04..0x80=ENTERTAINER..COUNTRY&WESTERN; SEG02 0x04..0x20=MARCH&WALTZ..MEMORY. The old
# binding (SEG01/SEG02 b0-b7) was off and collided with START/STOP (SEG00 0x10) etc.
# Physical position i = genre i (2 rows x 8). See notes/panel-rhythm-group.md.
# bank A (ev2005, position i = genre i; arg-mid = genre index -> re-derived bits). See notes/panel-layout-bankA-bindings.md.
RG=[("8&16 BEAT","SEG02","0x80"),("ROCK & POP","SEG02","0x20"),("BALLAD","SEG02","0x08"),("JAZZ & SWING","SEG02","0x02"),
    ("BALLROOM","SEG01","0x80"),("MOVIE & SHOW","SEG01","0x20"),("ENTERTAINER","SEG01","0x08"),("ORGANIST","SEG01","0x02"),
    ("60s & 70s","SEG02","0x40"),("MODERN DANCE","SEG02","0x10"),("SOUL & R&B","SEG02","0x04"),("COUNTRY & WESTERN","SEG02","0x01"),
    ("MARCH & WALTZ","SEG01","0x40"),("LATIN & WORLD","SEG01","0x10"),("CUSTOM","SEG01","0x04"),("MEMORY","SEG01","0x01")]
# LED-purpose fallback for genre cells with no bound driver button (orphan genres ORGANIST / 60s&70s):
# take the name from the RG list. setdefault keeps BTN_NAME (the driver) as authority where a button exists.
for _gnm,_gsg,_gmk in RG:
    _gled = GENRE_LED.get((_gsg, _gmk))
    if _gled: LED_PURPOSE.setdefault(_gled, _gnm)
# Genre-select LEDs: driven by the firmware-authoritative PANEL_LED map (GENRE_LED = PANEL_LED, above).
# The old local GENRE_LED dict here (genreled2.lua, 2026-07-07) was WRONG for ALL 16 genres. The live
# Panel SW&LED self-test sweep (2026-07-13) lights EXACTLY PANEL_LED[(SEG,mask)] on each genre press --
# e.g. 8&16 BEAT->cpl_led2, ROCK&POP->cpl_led18, BALLAD->cpl_led34, JAZZ&SWING->cpl_led50, MEMORY->cpl_led57
# -- not the old cpl_led0-3/8-11/16-19/25-27 values. Removed; the loop below now reads PANEL_LED. (MEMORY's
# real LED cpl_led57 does NOT collide with BEAT-1's cpl_led24, so the earlier "leave MEMORY dark" note is
# retracted.) Colours unchanged (RED except CUSTOM/MEMORY green).
LB.append(L("RHYTHM GROUP",700,42,180,11,TXTH))
for i,(nm,tag,mask) in enumerate(RG):
    cx=RGcols[i%8]; cy=90 if i<8 else 162; ls=wrap2(nm)
    for k,ln in enumerate(ls): LB.append(L(ln,cx-28,cy-22-(len(ls)-1-k)*9,56,8))
    LB.append(P("round_btn",cx-16,cy,32,32,tag=tag,mask=mask))
    # LED colour (Felipe): RHYTHM GROUP genres are RED except CUSTOM & MEMORY (GREEN)
    LB.append(P("green_led" if nm in ("CUSTOM","MEMORY") else "red_led",cx-4,cy-13,8,8,name=GENRE_LED.get((tag,mask))))
# MUSIC STYLIST = SEG07 0x01 (ev2040 app-open MUSIC STYLIST, empirically confirmed).
LB.append(L("MUSIC STYLIST",418,214,120,10)); LB.append(P("green_led",470,216,8,8,name=PANEL_LED.get(("SEG07","0x01")))); LB.append(P("pill_orange",441,228,65,22,tag="SEG07",mask="0x01"))
LB += [L("DEMO",18,258,44,10), P("music_note",56,252,16,20), P("demo_btn",26,274,42,42,tag="SEG06",mask="0x40"),   # bank A: DEMO = SEG06 0x40 (ev2040 app-open DEMO)
       L("PERFORMANCE PADS",98,250,172,9,TXTH), P("hline",95,254,26,3), P("hline",247,254,26,3)]
# PERFORMANCE PADS: AUTO SETTING=0x2031, STOP=0x2033 (single-bit dedicated events, pool-matched);
# BANK left decorative (its "PADS BANK" driver label is on a 0x2000 part-off bit = mislabel).
# PERFORMANCE PADS (HELP-info 2026-07-07): AUTO SETTING=SEG09 0x04, BANK=SEG09 0x01, STOP=SEG09 0x02.
# (AUTO SETTING/STOP were wrongly on SEG06; the whole PADS row is SEG09 0x01/0x02/0x04.)
for nm,cx,tg,mk in [("AUTO SETTING",155,"SEG06","0x20"),("BANK",230,"SEG06","0x08"),("STOP",305,"SEG06","0x02")]:  # bank A pad-control row (ev2031/2032/2033)
    LB.append(L(nm,cx-30,262,64,9)); LB.append(P("round_btn",cx-14,274,32,32,tag=tg,mask=mk))
LB.append(P("green_led",151,270,8,8,name=PANEL_LED.get(("SEG06","0x20"))))   # AUTO SETTING LED (cpl_led12)
padspec=[("msp_corner",0,0),("msp_middle",0,0),("msp_corner",1,0),("msp_corner",0,1),("msp_middle",0,1),("msp_corner",1,1)]
padcol=[(35,94),(129,100),(229,94)]; padrow=[(368,41),(409,51)]   # measured vs mockup: bottom row reaches y~1457
# PERFORMANCE PADS 1-6 = ev2030 (HELP-info 2026-07-07). pad index i (label i+1) -> its SEG.bit:
# bank A (ev2030, arg-mid = pad index 0..5): pads 1-6.
PAD_BITS=[("SEG06","0x10"),("SEG04","0x80"),("SEG04","0x20"),("SEG06","0x04"),("SEG06","0x01"),("SEG04","0x40")]
for i,(shp,fx,fy) in enumerate(padspec):
    (x,w)=padcol[i%3]; (y,h)=padrow[i//3]; ptg,pmk=PAD_BITS[i]
    LB.append(P(shp,x,y,w,h,flip=bool(fx),flipy=bool(fy),tag=ptg,mask=pmk)); LB.append(L(str(i+1),x+w//2-10,y+h//2-8,20,12))
    if i in (4,5): LB.append(L("SOLO",x+w//2-14,y+h//2+4,28,7,TXTH))
# MUSIC STYLE ARRANGER = SEG09 0x08 (user: MUTE DOWN 8 => MSA; old SEG04 0x08 only moved a fader).
# SPLIT POINT was SEG03 0x80 = LCD LEFT 5 (now bound to the left soft-key); unbound until its real bit is found.
for nm,cx,cy,tg,mk in [("MUSIC STYLE ARRANGER",375,360,"SEG04","0x08"),("ONE TOUCH PLAY",490,350,"SEG04","0x02"),("SPLIT POINT",555,350,"SEG03","0x80")]:  # bank A
    ls=wrap2(nm)
    for k,ln in enumerate(ls): LB.append(L(ln,cx-42,cy-26+k*9,84,8))
    LB.append(P("round_btn",cx-16,cy,32,32,tag=tg,mask=mk))
LB.append(P("red_led",371,350,8,8,name=PANEL_LED.get(("SEG04","0x08"))))   # MUSIC STYLE ARRANGER LED RED (Felipe)
# SPLIT POINT button has NO indicator LED (Felipe: removed)
# L-bracket linking MUSIC STYLE ARRANGER down to VARIATION 1
LB += [P("vline",348,356,3,58), P("hline",348,412,20,3)]
LB.append(L("VARIATION",430,378,90,8,TXTH))
# VARIATION 1-3 = SEG04 b4/b2/b0; VARIATION 4 was SEG03 0x40 but the user shows that bit is
# LCD LEFT 4 (now bound to the left soft-key), so VAR4 is freed (decorative; real bit TBD).
# These are rhythm modifiers with no distinct LCD, so snapshot can't verify them.
VARBITS=[("SEG04","0x10"),("SEG04","0x04"),("SEG04","0x01"),("SEG03","0x40")]  # bank A VAR&MSA 1-4 (ev2085 arg-mid 0..3) -- all four now bound
for i,cx in enumerate([366,426,486,546]):
    LB.append(P("round_btn",cx,399,32,32,tag=VARBITS[i][0],mask=VARBITS[i][1])); LB.append(P("red_led",cx-2,388,8,8,name=PANEL_LED.get((VARBITS[i][0],VARBITS[i][1])))); LB.append(L(str(i+1),cx+8,388,10,8))   # VARIATION LEDs RED (Felipe); cpl_led3/11/19/27
# bank A (ev2084, arg-mid 0=IN,1=OUT): FADE IN = SEG03 0x20 / OUT = SEG03 0x08.
# TAP TEMPO = SEG03 0x02 (ev20A1). SYNCHRO & BREAK = SEG00 0x80 (ev2021).
LB.append(L("FADE",625,340,105,9)); LB += pair_h("SEG03","0x20","0x08",625,355,105,28,"IN","OUT")
for nm,x,w,h,tg,mk in [("TAP TEMPO",740,105,28,"SEG03","0x02"),("SYNCHRO & BREAK",856,105,28,"SEG00","0x80")]:
    LB.append(L(nm,x,340,w,9)); LB.append(P("pill_wide",x,355,w,h,tag=tg,mask=mk))
# FADE in/out LEDs (two, one per half) + SYNCHRO LED -- all RED (Felipe)
LB += [P("red_led",645,364,8,8,name=PANEL_LED.get(("SEG03","0x20")))] + [P("red_led",697,364,8,8,name=PANEL_LED.get(("SEG03","0x08")))]   # FADE IN=cpl_led35 / OUT=cpl_led51
LB.append(P("red_led",856+48,364,8,8,name=PANEL_LED.get(("SEG00","0x80"))))   # SYNCHRO & BREAK LED RED (Felipe)
# bank A (ev2022, arg-mid 0/1): INTRO & ENDING 1 = SEG03 0x01 / 2 = SEG00 0x40 (straddles two SEGs).
# ev2023 (arg-mid 0/1): FILL IN 1 = SEG03 0x10 / 2 = SEG03 0x04. START/STOP = SEG00 0x10 (ev2020).
LB.append(L("INTRO & ENDING",740,394,105,9)); LB += pair_h("SEG03","0x01","0x40",740,408,105,50,"1","2",seg2="SEG00")
LB.append(L("FILL IN",625,394,105,9)); LB += pair_h("SEG03","0x10","0x04",625,408,105,50,"1","2")
# START/STOP stays a single greycyan pill.
LB.append(L("START/STOP",856,394,105,9)); LB.append(P("pill_greycyan",856,408,105,50,tag="SEG00",mask="0x10"))
# INTRO&ENDING 1/2 LEDs + SEQ RESET/COUNT INTRO labels ; START/STOP 1-4 LEDs
LB += [P("red_led",763,414,8,8,name=PANEL_LED.get(("SEG03","0x01"))), P("red_led",800,414,8,8,name=PANEL_LED.get(("SEG00","0x40")))]   # INTRO & ENDING 1/2 LEDs RED (Felipe); cpl_led0/8
# FILL IN 1/2 LEDs -- were MISSING; added over the FILL IN pill halves (x=625,w=105). RED (Felipe).
LB += [P("red_led",648,414,8,8,name=PANEL_LED.get(("SEG03","0x10"))), P("red_led",685,414,8,8,name=PANEL_LED.get(("SEG03","0x04")))]   # FILL IN 1/2; cpl_led43/59
LB += [L("SEQUENCER",748,452,44,7), L("RESET",752,459,36,7), L("COUNT INTRO",802,452,52,7)]
# first BEAT LED = START/STOP indicator (cpl1, lit on rhythm start); beats 2-4 not yet swept
# BEAT 1-4 indicators: light in sequence per beat. Order corrected per Felipe (my first sweep
# started mid-measure): beat1=cpl24, beat2=cpl32, beat3=cpl40, beat4=cpl48 (left-to-right = 1-2-3-4).
_beatled=["cpl_led24","cpl_led32","cpl_led40","cpl_led48"]
# BEAT 1-4: a uniform horizontal row at y=395, 25.5px apart (Felipe: beats 1-2 were correctly placed at
# the left; 3-4 realigned to the SAME y and EVEN spacing so all four form one row). Emitted in signal
# order so the beat sweep runs strictly left-to-right = 1-2-3-4. beat 1 RED, beats 2-4 GREEN (Felipe).
_beatx=[866.5,892,917.5,943]
LB += [P("green_led" if i>0 else "red_led",_beatx[i],395,8,8, name=_beatled[i]) for i in range(4)] + [L("BEAT",905,452,28,7)]
# 3 SPLIT-POINT indicators at the very bottom of the layout (Felipe): a tiny down-arrow + RED LED per
# keyboard split point. Exact key positions are TBD -- placeholders spread along the bottom edge;
# Felipe will reposition them to the real split keys via the SVG-editing loop.
for _sx in (200,500,800):
    LB.append(P("red_led",_sx+2,478,8,8)); LB.append(P("split_arrow",_sx,489,12,10))
LB.append('\t</group>')

# =================== RIGHT BLOCK (bottom-right; coords = abs - (1000,997)) ===
RB=['\t<group name="right_block">','\t\t<bounds x="0" y="0" width="1000" height="503"/>',P("bg_right",0,0,1000,503)]
SGcols=[51,107,162,217,272,327,383,438,493]
# SOUND GROUP = the 18 physical category buttons (bank A, event 0x2004; arg-hi = category index into
# SoundGroupNameTable @0x48131570). Position i = category i (verified: SEG10.b4->PIANO, SEG14.b3->SAX
# screenshot-confirmed). The bits span SEG0C-15 -- see notes/panel-layout-bankA-bindings.md.
SG=[("PIANO","SEG10","0x10"),("GUITAR","SEG0F","0x10"),("MALLET & ORCH PERC","SEG0E","0x10"),("WORLD","SEG0D","0x10"),
    ("STRINGS & VOCAL","SEG0C","0x10"),("BRASS","SEG15","0x08"),("SAX & WOODWIND","SEG14","0x08"),("ORGAN & ACCORDION","SEG13","0x08"),("SOUND EXPLORER","SEG12","0x08"),
    ("DIGITAL DRAWBAR","SEG10","0x20"),("ORGAN TABS","SEG0F","0x20"),("ACCORDION REGISTER","SEG0E","0x20"),("PAD","SEG0D","0x20"),
    ("SYNTH","SEG0C","0x20"),("BASS","SEG15","0x04"),("DRUM KITS","SEG14","0x04"),("MEMORY","SEG13","0x04"),("EW EXPANSION","SEG12","0x04")]
# MEMORY (SEG13 0x04) / EW EXPANSION (SEG12 0x04) ARE bound in bank A (were decorative-only in bank B).
RB.append(L("SOUND GROUP",240,42,180,11,TXTH))
for i,(nm,tag,mask) in enumerate(SG):
    cx=SGcols[i%9]; cy=90 if i<9 else 162; ls=wrap2(nm)
    for k,ln in enumerate(ls): RB.append(L(ln,cx-28,cy-22-(len(ls)-1-k)*9,56,8))
    RB.append(P("round_btn",cx-16,cy,32,32,tag=tag,mask=mask))
    # LED colour (Felipe): SOUND GROUP buttons are RED except MEMORY (GREEN)
    RB.append(P("green_led" if nm=="MEMORY" else "red_led",cx-4,cy-13,8,8,name=OPLED.get((tag,mask))))
    if i in (9,10): RB.append(P("pill_ring",cx-34,cy-4,68,40))
RB.append(L("PART EFFECT",560,42,150,10,TXTH)); RB += [P("hline",560,47,26,3), P("hline",684,47,26,3)]
# PART EFFECT (HELP-info 2026-07-07): SOUND DSP=SEG0F 0x01, VARIATION(=SOUND DSP VARIATION)=SEG0F 0x02,
# SUSTAIN=SEG0E 0x10, DIGITAL EFFECT=SEG0E 0x20. (SUSTAIN/DIGITAL EFFECT were mis-labelled MEMORY/EW
# EXPANSION in the SOUND GROUP list above; corrected here.)
# bank A: PART EFFECT row = SEG0E-11 bit 0x08 (SOUND DSP VARIATION..SUSTAIN). See notes/panel-layout-bankA-bindings.md.
PE_BITS={"SOUND DSP":("SEG0F","0x08"),"VARIATION":("SEG0E","0x08"),"SUSTAIN":("SEG11","0x08"),"DIGITAL EFFECT":("SEG10","0x08")}
for nm,cx in [("SUSTAIN",565),("DIGITAL EFFECT",620),("SOUND DSP",675),("VARIATION",730)]:
    ls=wrap2(nm); tg,mk=PE_BITS.get(nm,(None,None))
    for k,ln in enumerate(ls): RB.append(L(ln,cx-26,58-(len(ls)-1-k)*9,52,8))
    RB.append(P("round_btn",cx-14,71,32,32,tag=tg,mask=mk)); RB.append(P("red_led",cx-2,60,8,8,name=OPLED.get((tg,mk))))   # PART EFFECT LEDs RED (Felipe)
RB.append(L("GLOBAL EFFECT",560,128,150,10,TXTH)); RB += [P("hline",558,133,24,3), P("hline",688,133,24,3)]
# GLOBAL EFFECT (SEG13): REVERB=0x40, MIC(=MIC REVERB & EFFECT)=0x80 (HELP-info). CHORUS=0x10,
# MULTI=0x20 -- event-inferred: they fire ev2062/ev2061 in this group but have no HELP page (verified
# no-op in HELP mode); the 4 bits 0x10/0x20/0x40/0x80 map L->R to the 4 buttons. notes/panel-button-names.md
# bank A: GLOBAL EFFECT row = SEG0E-11 bit 0x04 (MIC REVERB&EFFECT..CHORUS).
GE_BITS={"CHORUS":("SEG11","0x04"),"MULTI":("SEG10","0x04"),"REVERB":("SEG0F","0x04"),"MIC":("SEG0E","0x04")}
for nm,cx in [("CHORUS",565),("MULTI",620),("REVERB",675),("MIC",730)]:
    tg,mk=GE_BITS.get(nm,(None,None))
    RB.append(L(nm,cx-26,152,52,8)); RB.append(P("round_btn",cx-14,163,32,32,tag=tg,mask=mk)); RB.append(P("red_led",cx-2,152,8,8,name=OPLED.get((tg,mk))))   # GLOBAL EFFECT LEDs RED (Felipe)
RB.append(L("SEQUENCER",850,42,90,10,TXTH))
# bank A (empirical app-open screen sweep 2026-07-10): DISK = SEG0D 0x04, PROGRAM MENUS = SEG0C 0x04,
# PLAY = SEG0D 0x08 (opens SEQUENCER PLAY), EASY REC = SEG0C 0x08 (opens EASY RECORD).
for nm,cx,cy,shp,tg,mk in [("PLAY",845,71,"round_btn","SEG0D","0x08"),("EASY REC",915,71,"round_red","SEG0C","0x08"),("DISK",845,149,"round_btn","SEG0D","0x04"),("PROGRAM MENUS",915,149,"round_btn","SEG0C","0x04")]:
    ls=wrap2(nm)
    for k,ln in enumerate(ls): RB.append(L(ln,cx-26,cy-13-(len(ls)-1-k)*9,52,8))
    RB.append(P(shp,cx-16,cy,32,32,tag=tg,mask=mk)); RB.append(P("green_led",cx-4,cy-13,8,8,name=OPLED.get((tg,mk))))  # DISK=cpr_led75, PROGRAM MENUS=cpr_led74
# DISK / IN USE indicator + line to DISK button
RB += [L("DISK",798,138,32,8,TXTH), L("IN USE",796,147,36,8,TXTH), P("red_led",812,158,8,8), P("hline",822,162,20,3), L("LOAD",832,183,32,8)]   # DISK IN USE LED RED (Felipe)
# SD (LOAD) pill = SEG0D 0x80 (ev2040 app-open SD MENU, empirically confirmed).
RB.append(L("SD",882,214,40,10,TXTH)); RB.append(P("pill_orange",860,228,60,22,tag="SEG0D",mask="0x80")); RB.append(P("green_led",886,216,8,8,name=PANEL_LED.get(("SEG0D","0x80")))); RB.append(L("LOAD",874,252,32,8))
RB.append(L("TEMPO/PROGRAM",38,300,140,10,TXTH)); RB.append(P("tempo_knob",50,318,110,110)); RB.append(P("green_led",164,336,8,8))
# TEMPO/PROGRAM knob is DRAGGABLE (relative encoder): a transparent click-area over the knob, wired in the
# <script> below via add_simplecounter_knob -> PORT_ADJUSTER "TEMPO_KNOB". Vertical drag = tempo up/down.
# The click-area element itself is APPENDED AT THE END of right_block (see below) so it does not shift the
# element indices that layout_nudges.json keys on. (The green_led at 164,336 is the knob's indicator LED --
# left UNBOUND: RE found no firmware signal that drives it, so binding it would be a guess; see notes.)
RB.append(L("TRANSPOSE",213,320,100,10,TXTH))
# SPLIT PAIRS (bank A -- each half on a different SEG; arg-mid 1=-,0=+ inferred):
#   TRANSPOSE  - = SEG10 0x01 / + = SEG0F 0x01 (ev2081; +/- corrected per Felipe 2026-07-11)
#   R1/R2 OCT  - = SEG13 0x02 / + = SEG12 0x02 (ev2083; +/- corrected per Felipe)
RB += [P("red_led",230,328,8,8,name=PANEL_LED.get(("SEG10","0x01"))), P("red_led",262,328,8,8,name=PANEL_LED.get(("SEG0F","0x01")))] + pair_h("SEG10","0x01","0x01",213,335,75,24,"-","+",seg2="SEG0F")   # TRANSPOSE LEDs RED (Felipe); -=cpr_led96/+=cpr_led39
RB.append(L("R1/R2 OCTAVE",210,378,96,8,TXTH))
RB += [P("red_led",230,398,8,8,name=PANEL_LED.get(("SEG13","0x02"))), P("red_led",262,398,8,8,name=PANEL_LED.get(("SEG12","0x02")))] + pair_h("SEG13","0x02","0x02",213,405,75,24,"-","+",seg2="SEG12")   # R1/R2 OCTAVE LEDs RED (Felipe); -=cpr_led38/+=cpr_led37
# HELP-info (2026-07-07): TECHNI-CHORD=SEG11 0x80, PART SELECT=SEG10 0x10, CONDUCTOR=SEG11 0x10.
# These are button GROUPS (all members share the same HELP name); the found bit is bound to the
# FIRST member of each group -- exact per-position bits within a group aren't distinguishable by HELP.
RB.append(L("TECHNI-CHORD",403,258,68,9,TXTH)); RB.append(L("SOLO",474,258,40,9,TXTH))
# bank A: TECHNI-CHORD = SEG0D 0x01 (ev20A2), SOLO = SEG0C 0x01 (ev2086). TECHNI-CHORD LED cpr_led73 (state identity).
# TECHNI-CHORD & SOLO LEDs RED (Felipe)
RB += [P("red_led",428,274,8,8,name=PANEL_LED.get(("SEG0D","0x01"))), P("round_btn",416,285,32,32,tag="SEG0D",mask="0x01"), P("red_led",488,274,8,8,name=PANEL_LED.get(("SEG0C","0x01"))), P("round_btn",476,285,32,32,tag="SEG0C",mask="0x01")]
RB.append(L("PART SELECT",348,322,92,9,TXTH)); RB += [P("hline",348,327,22,3), P("hline",470,327,22,3)]
# bank A PART SELECT group (ev2009, arg-mid 0/1/2) -- all three members now known.
# Panel silk order left->right = LEFT, RIGHT 2 (centre), RIGHT 1 (Felipe 2026-07-14): the layout had the
# outer pair horizontally mirrored, so LEFT/RIGHT 1 (SEG0E.01=cpr_led36 / SEG0D.02=cpr_led34) are swapped;
# centre RIGHT 2 kept. (The service-manual schematic mislabels these -- its D1069/D1055 LEFT/RIGHT 1 are the
# reverse of the panel silk; driver PORT_NAMEs corrected to match the silk.)
PARTSEL=[("SEG0E","0x01"),("SEG0E","0x02"),("SEG0D","0x02")]
for j,cx in enumerate([360,425,485]): tg,mk=PARTSEL[j]; RB += [P("red_led",cx+12,334,8,8,name=PANEL_LED.get((tg,mk))), P("round_btn",cx,345,32,32,tag=tg,mask=mk)]   # PART SELECT LEDs RED (Felipe); cpr_led34/35/36
# bank A CONDUCTOR group (ev2008, arg-mid 0/1/2) -- all three members now known.
# Panel silk order left->right = LEFT, RIGHT 2 (centre), RIGHT 1 (Felipe 2026-07-14): same horizontal-mirror
# fix as PART SELECT -- the outer pair (SEG11.02=cpr_led65 LEFT / SEG0F.02=cpr_led63 RIGHT 1) is swapped;
# centre SEG10.02=cpr_led64 (RIGHT 2) kept. Each button has its own LED; the group SEG0F/10/11 0x02 maps
# contiguously to cpr_led63/64/65 (schematic D1107/D1114/D1120, but its RIGHT 1/RIGHT 2 labels are the
# reverse of the panel silk -- driver PORT_NAMEs corrected to match).
CONDUCT=[("SEG11","0x02"),("SEG10","0x02"),("SEG0F","0x02")]
CONDUCT_LED=[PANEL_LED.get(("SEG11","0x02")), PANEL_LED.get(("SEG10","0x02")), "cpr_led63"]
for j,cx in enumerate([360,425,485]): tg,mk=CONDUCT[j]; RB += [P("red_led",cx+12,399,8,8,name=CONDUCT_LED[j]), P("round_btn",cx,410,32,32,tag=tg,mask=mk)]   # CONDUCTOR LEDs RED (Felipe)
RB.append(L("CONDUCTOR",393,454,92,9,TXTH)); RB += [P("hline",360,458,26,3), P("hline",470,458,26,3)]
# bank A (empirical screen sweep 2026-07-10): BANK VIEW = SEG10 0x80 (ev2013, PANEL MEMORY BANK
# SELECT screen); NEXT BANK = SEG0F 0x80 (ev2012, advances the bank).
RB += [L("BANK VIEW",583,220,72,8), P("green_led",585,230,8,8,name=PANEL_LED.get(("SEG10","0x80"))), P("bank_wing",580,238,90,26,tag="SEG10",mask="0x80"),
       L("NEXT BANK",690,220,72,8), P("bank_wing",685,238,90,26,tag="SEG0F",mask="0x80"), L("PANEL MEMORY",608,255,172,10,TXTH),
       P("panel_memory_dial",565,268,190,190),
       # PANEL MEMORY SET : EDUCATED GUESS (Felipe 2026-07-11, will test+refine). SEG13 0x40 (ev2011 --
       # fits the ev2010 recall / ev2011 SET / ev2012 NEXT BANK / ev2013 BANK VIEW pattern; a store test
       # was inconclusive, maybe blocked by DATA PROTECTION). Transparent clickable over the dial centre.
       P("inv_rect",639,342,42,42,tag="SEG13",mask="0x40"), L("SET",638,354,44,12)]
# PANEL MEMORY = an 8-way pie-slice dial (center 660,363) with a central SET. Each numbered slice
# recalls a registration -- bank A ev2010 arg-mid = PM number - 1 (empirically confirmed: pressing
# each opens "PMEM x-N"). Draw the number labels (r=88) + a clickable round button per slice (r=62).
import math as _m
# PM number -> its ev2010 recall bit (arg-mid = PM# - 1; verified: SEG0C 0x02 recalls PMEM A-1).
PM_BY_NUM={1:("SEG0C","0x02"),2:("SEG12","0x40"),3:("SEG11","0x40"),4:("SEG10","0x40"),
           5:("SEG0F","0x40"),6:("SEG11","0x80"),7:("SEG12","0x80"),8:("SEG13","0x80")}
# Physical slice order corrected per Felipe (2026-07-10; my earlier angular order was scrambled):
# angular slot i shows PM_ORDER[i], recalls that registration, and lights its own LED.
PM_ORDER=[2,1,8,7,6,5,4,3]
for _i,_num in enumerate(PM_ORDER):
    _a=_m.radians(-90+ (_i)*45 +200)
    _lx=660+int(88*_m.cos(_a)); _ly=363+int(88*_m.sin(_a))
    RB.append(L(str(_num),_lx-4,_ly-4,8,8,TXTH))
    _bx=660+int(58*_m.cos(_a)); _by=363+int(58*_m.sin(_a))
    _tg,_mk=PM_BY_NUM[_num]
    RB.append(P("round_btn",_bx-16,_by-16,32,32,tag=_tg,mask=_mk))
    _ex=660+int(80*_m.cos(_a)); _ey=363+int(80*_m.sin(_a))
    RB.append(P("green_led",_ex-4,_ey-4,8,8,name=PANEL_LED.get((_tg,_mk))))
RB.append(P("big_ring",809,327,130,130))
# CUSTOM PANEL = SEG0D 0x40 (CPR_SEG1 SW6, ev2016) -- physical position confirmed by Felipe 2026-07-14
# (the driver bit that panel-driver-fixlist.md had flagged "Fn 2016 unused"). LED = cpr_led1.
RB += [L("CUSTOM",804,318,52,8), L("PANEL",806,327,48,8), P("green_led",800,336,8,8,name=PANEL_LED.get(("SEG0D","0x40"))), P("round_btn_big",819,353,42,42,tag="SEG0D",mask="0x40")]
# CUSTOMIZE = SEG0C 0x40 (ev2040 app-open CUSTOMIZE MENU); FAVORITES = SEG0E 0x40 (ev20AE, FAVORITES
# screen) -- both empirically confirmed.
RB += [L("CUSTOMIZE",895,330,60,8), P("green_led",946,340,8,8,name=PANEL_LED.get(("SEG0C","0x40"))), P("round_btn_big",884,350,42,42,tag="SEG0C",mask="0x40")]
RB += [L("FAVORITES",840,436,72,8), P("green_led",912,438,8,8,name="cpr_led97"), P("round_btn_big",852,407,42,42,tag="SEG0E",mask="0x40")]   # FAVORITES LED = cpr_led97 (observed live in normal op; PANEL_LED's cpr_led2 was wrong/dead)
# Draggable TEMPO/PROGRAM knob click-area -- appended LAST in right_block so it never shifts the indices
# that layout_nudges.json references (a mid-group insert would invalidate every later nudge's ref-check).
RB.append('\t\t<element id="tempo_click" ref="inv_rect"><bounds x="50" y="318" width="110" height="110"/></element>')
RB.append('\t</group>')

# ---- SD-card transport block (its own group, referenced by the views) ----
# Order per the two photos: SD VOLUME -/+ , SKIP/SEARCH <<//>> , STOP , PLAY/PAUSE , SD IN USE LED.
# Bound to the SDSW input port (the 6 SD front-panel switches, byte 0x9CC00008 active-low ->
# descriptor SEG1D events 0x20B5..BA): VOL- 0x10, VOL+ 0x20, SKIP<< 0x01, SKIP>> 0x02, STOP 0x04,
# PLAY/PAUSE 0x08. (Silk order per Felipe: these are the "6 SD CARD buttons".)
SDB=['\t<group name="sd_block">','\t\t<bounds x="0" y="0" width="500" height="70"/>',
     L("SD VOLUME",8,52,96,10,TXTH), P("half_l",12,18,42,30,tag="SDSW",mask="0x10"), P("half_r",54,18,42,30,tag="SDSW",mask="0x20"), L("-",28,28,12,12), L("+",70,28,12,12),
     L("SKIP / SEARCH",116,52,104,10,TXTH), P("sd_skipb",120,18,48,30,tag="SDSW",mask="0x01"), P("sd_skipf",172,18,48,30,tag="SDSW",mask="0x02"),
     L("STOP",243,52,52,10,TXTH), P("sd_stop",245,18,48,30,tag="SDSW",mask="0x04"),
     L("PLAY / PAUSE",306,52,76,10,TXTH), P("sd_play",320,18,48,30,tag="SDSW",mask="0x08"), P("green_led",376,30,8,8),   # SD CARD PLAY/PAUSE LED (Felipe: green)
     L("SD IN USE",406,42,72,10,TXTH), P("red_led",438,28,8,8)]
SDB.append('\t</group>')

VIEWS='''
	<view name="Compact">
		<bounds x="0" y="0" width="2000" height="1500"/>
		<group ref="screen_block"><bounds x="0" y="0" width="2000" height="997"/></group>
		<group ref="left_block"><bounds x="0" y="997" width="1000" height="503"/></group>
		<group ref="right_block"><bounds x="1000" y="997" width="1000" height="503"/></group>
		<!-- SD-card transport: centered below the MUTE row (compact view); overall dims unchanged -->
		<group ref="sd_block"><bounds x="750" y="915" width="500" height="70"/></group>
	</view>

	<view name="Full Unit">
		<bounds x="0" y="0" width="4000" height="997"/>
		<group ref="left_block"><bounds x="0" y="247" width="1000" height="503"/></group>
		<group ref="screen_block"><bounds x="1000" y="0" width="2000" height="997"/></group>
		<group ref="right_block"><bounds x="3000" y="247" width="1000" height="503"/></group>
		<group ref="sd_block"><bounds x="1750" y="915" width="500" height="70"/></group>
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

	<view name="SD Block">
		<bounds x="0" y="0" width="500" height="70"/>
		<group ref="sd_block"><bounds x="0" y="0" width="500" height="70"/></group>
	</view>
'''
o=io.StringIO()
o.write('<?xml version="1.0"?>\n<!-- KN7000 control-panel layout, kn5000 SVG-snippet style, pixel-mapped to the\n')
o.write('     mockup (4000x3000 = 2x). 3 reusable blocks + Compact & Full Unit views.\n     Generated by tools/gen_lay.py. -->\n<mamelayout version="2">\n\n')
# Slider drag support (same mechanism as MAME's esq1/linndrum/mpc60 layouts): the shared slider library
# (tools/slider_lib.lua) + registration of the 4 volume faders. The faders live in the left_block group,
# so they appear in EVERY view that references it (Compact, Full Unit, Left Block) -- wire ALL of them
# (MAME remembers the selected view in cfg, so wiring only one left the others un-draggable).
_lib=open("/home/fsanches/compartilhado/kn7000_mame/tools/slider_lib.lua").read()
SCRIPT=('\t<script><![CDATA[\n'+_lib+'\n'
        '\t\t-- KN7000 draggable controls: the 4 volume faders (left_block) + the TEMPO/PROGRAM knob\n'
        '\t\t-- (right_block). Registered per view that contains each, callbacks installed once per view.\n'
        '\t\tfile:set_resolve_tags_callback(function()\n'
        '\t\t\tfor vname, view in pairs(file.views) do\n'
        '\t\t\t\tlocal any = false\n'
        '\t\t\t\tif view.items["vol_main_click"] ~= nil then\n'
        '\t\t\t\t\tadd_vertical_slider(view, "vol_main_click", "vol_main_knob", "VOL_MAIN")\n'
        '\t\t\t\t\tadd_vertical_slider(view, "vol_apcseq_click", "vol_apcseq_knob", "VOL_APCSEQ")\n'
        '\t\t\t\t\tadd_vertical_slider(view, "vol_mic_click", "vol_mic_knob", "VOL_MIC")\n'
        '\t\t\t\t\tadd_vertical_slider(view, "vol_linein_click", "vol_linein_knob", "VOL_LINEIN")\n'
        '\t\t\t\t\tany = true\n'
        '\t\t\t\tend\n'
        '\t\t\t\tif view.items["tempo_click"] ~= nil then\n'
        '\t\t\t\t\t-- relative encoder: a vertical drag over the knob accumulates into the TEMPO_KNOB\n'
        '\t\t\t\t\t-- adjuster; the driver diffs it into [0x17, pos] steps. scale 1.5 = ~1.5*height per sweep.\n'
        '\t\t\t\t\tadd_simplecounter_knob(view, "tempo_click", "TEMPO_KNOB", 1.5)\n'
        '\t\t\t\t\tany = true\n'
        '\t\t\t\tend\n'
        '\t\t\t\tif any then install_slider_callbacks(view) end\n'
        '\t\t\tend\n'
        '\t\tend)\n'
        '\t]]></script>\n')
# ---- READABILITY: cluster each group's placements into correlated on-screen controls, blank-line
#      separated, so related declarations (a button + its label(s) + its LED(s)) sit together.
#      Button-anchored: interactive elements are the anchors (touching pairs like a split pill merge),
#      each label/LED attaches to its nearest anchor; backgrounds pin to the front. WITHIN a cluster the
#      ORIGINAL relative order is preserved, so draw order (z-order) is unchanged and the render is
#      pixel-identical. Runs before the nudge pass so the nudge (group,index) keys stay consistent.
#      The reorder is DETERMINISTIC, so the order is stable across regenerations. The placement
#      permutation is written to /tmp/reorder_perms.json {group:{old_idx:new_idx}} -- it was used once
#      to migrate layout_nudges.json's keys when this pass was introduced, and would be reused to
#      re-migrate if the clustering ever changes (map old key group.i.ref -> group.perm[i].ref).
def _reorder_group(lines, GW, GH, MERGE=6, ORPHAN=30):
    from collections import defaultdict
    header, footer = lines[0], lines[-1]
    mid = lines[1:-1]
    struct = [l for l in mid if l.strip() and '<element' not in l and '<screen' not in l]
    plac   = [l for l in mid if ('<element' in l) or ('<screen' in l)]
    def pbox(l):
        mb=re.search(r'<bounds\b[^>]*?x="([-\d.]+)"[^>]*?y="([-\d.]+)"[^>]*?width="([-\d.]+)"[^>]*?height="([-\d.]+)"', l)
        return tuple(map(float,mb.groups())) if mb else None
    info=[]
    for oi,l in enumerate(plac):
        b=pbox(l)
        anchor=('inputtag=' in l) or bool(re.search(r'id="\w+_(?:click|knob)"',l)) or ('<screen' in l)
        isbg=(b is None) or ('bg_' in l) or (b is not None and b[2]*b[3]>0.25*GW*GH and not anchor)
        info.append({'oi':oi,'l':l,'b':b,'anchor':anchor,'bg':isbg})
    bgs=[e for e in info if e['bg']]
    anchors=[e for e in info if (not e['bg']) and e['anchor']]
    nons=[e for e in info if (not e['bg']) and (not e['anchor'])]
    def gap(b1,b2):
        x1,y1,w1,h1=b1;x2,y2,w2,h2=b2
        dx=max(0.0,max(x1,x2)-min(x1+w1,x2+w2));dy=max(0.0,max(y1,y2)-min(y1+h1,y2+h2));return (dx*dx+dy*dy)**0.5
    n=len(anchors);par=list(range(n))
    def find(a):
        while par[a]!=a: par[a]=par[par[a]];a=par[a]
        return a
    for i in range(n):
        for j in range(i+1,n):
            if anchors[i]['b'] and anchors[j]['b'] and gap(anchors[i]['b'],anchors[j]['b'])<=MERGE: par[find(i)]=find(j)
    ac=defaultdict(list)
    for k in range(n): ac[find(k)].append(anchors[k])
    clusters=list(ac.values())
    def cbox(es):
        bs=[e['b'] for e in es if e['b']]
        xs=[b[0] for b in bs];ys=[b[1] for b in bs];xe=[b[0]+b[2] for b in bs];ye=[b[1]+b[3] for b in bs]
        return (min(xs),min(ys),max(xe)-min(xs),max(ye)-min(ys))
    boxes=[cbox(cl) for cl in clusters]
    def adist(b,box):
        x,y,w,h=b;bx,by,bw,bh=box;xc=x+w/2.0
        dy=max(0.0,max(y,by)-min(y+h,by+bh));dx=max(0.0,max(x,bx)-min(x+w,bx+bw))
        hmis=0.0 if bx<=xc<=bx+bw else min(abs(xc-bx),abs(xc-(bx+bw)))
        return dy+2.5*dx+0.3*hmis
    for e in nons:
        if e['b'] is None or not clusters:
            clusters.append([e]); boxes.append(e['b'] or (0,0,0,0)); continue
        d,i=min((adist(e['b'],boxes[k]),k) for k in range(len(clusters)))
        if d<=ORPHAN: clusters[i].append(e)
        else: clusters.append([e]); boxes.append(e['b'])
    def ckey(cl):
        ys=[e['b'][1] for e in cl if e['b']];xs=[e['b'][0] for e in cl if e['b']]
        return (round(min(ys)/8.0) if ys else 0.0, min(xs) if xs else 0.0)
    clusters.sort(key=ckey)
    order=[]; out=[header]+struct
    for e in sorted(bgs,key=lambda e:e['oi']):
        out.append(e['l']); order.append(e)
    for cl in clusters:
        out.append('')
        for e in sorted(cl,key=lambda e:e['oi']):
            out.append(e['l']); order.append(e)
    out.append(footer)
    return out, {e['oi']:ni for ni,e in enumerate(order)}
_GDIM={'screen_block':(2000,997),'left_block':(1000,503),'right_block':(1000,503),'sd_block':(500,70)}
_perms={}
S,   _perms['screen_block'] = _reorder_group(S,   *_GDIM['screen_block'])
LB,  _perms['left_block']   = _reorder_group(LB,  *_GDIM['left_block'])
RB,  _perms['right_block']  = _reorder_group(RB,  *_GDIM['right_block'])
SDB, _perms['sd_block']     = _reorder_group(SDB, *_GDIM['sd_block'])
import json as _json_perm
open('/tmp/reorder_perms.json','w').write(_json_perm.dumps(_perms))

o.write("\n".join(E)+"\n\n"+"\n".join(S)+"\n\n"+"\n".join(LB)+"\n\n"+"\n".join(RB)+"\n\n"+"\n".join(SDB)+"\n"+VIEWS+SCRIPT+'</mamelayout>\n')
_LAY_PATH="/home/fsanches/compartilhado/kn7000_mame/src/mame/layout/kn7000.lay"
open(_LAY_PATH,"w").write(o.getvalue())
print(f"WROTE kn7000.lay: {len(E)} elements, {len(TXTS)} labels")

# Apply Felipe's finetuning nudges: per-element bounds deltas from a semantic diff of his
# Inkscape-adjusted layout SVG (tools/svg_semantic_diff.py -> layout_nudges.json). Applied to the
# freshly-written base .lay so the adjustments survive every regeneration. Each nudge is keyed by the
# stable id "group.index.ref" and REF-VERIFIED against the .lay element at that index before it is
# shifted, so a structural change to the layout that moves indices around fails loudly instead of
# silently mis-moving. To refresh: re-export the SVG, re-run svg_semantic_diff, regenerate.
import os as _os
_nud=_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"layout_nudges.json")
if _os.path.exists(_nud):
    import apply_nudges
    _by=apply_nudges.load_nudges(_nud)
    _patched,_st,_mism=apply_nudges.patch(open(_LAY_PATH).read(),_by)
    if _st['refmismatch']==0:
        open(_LAY_PATH,"w").write(_patched)
        print(f"APPLIED {_st['applied']} layout nudges (layout_nudges.json)")
    else:
        print(f"WARNING: {_st['refmismatch']} nudge ref-mismatches -- NOT applied (indexing drifted):")
        for _g,_i,_e,_a in _mism[:10]: print(f"  {_g}.{_i}: expected '{_e}' got '{_a}'")

# --- Adopt CP{board}_SEG{col} scan-matrix port names (KN5000 style). The layout binds each button
#     to its firmware normalized segment (SEGxx); rename that 1:1 to the sub-CPU scan column
#     CP{board}_SEG{col} at the SAME bit (= same SW sense line). normSeg IS the scan address (one
#     wire ADDR per column, no per-bit repacking), so this is a pure relabel -- no permutation, no
#     translation table. Segments outside 0x00-0x15 (valuators / SD GPIO / undecoded) carry no
#     button binding and are left decorative.
import re as _re
_NS2CP={0x00:"CPL_SEG0",0x01:"CPL_SEG1",0x02:"CPL_SEG2",0x03:"CPL_SEG3",0x04:"CPL_SEG4",
        0x05:"CPC_SEG5",0x06:"CPL_SEG6",0x07:"CPL_SEG7",0x08:"CPC_SEG8",0x09:"CPC_SEG9",
        0x0a:"CPC_SEG10",0x0b:"CPC_SEG11",0x0c:"CPR_SEG0",0x0d:"CPR_SEG1",0x0e:"CPR_SEG2",
        0x0f:"CPR_SEG3",0x10:"CPR_SEG4",0x11:"CPR_SEG5",0x12:"CPR_SEG6",0x13:"CPR_SEG7",
        0x14:"CPR_SEG8",0x15:"CPR_SEG9"}
_lay=open(_LAY_PATH).read(); _cnt=[0,0]
def _sub(m):
    _seg=int(m.group(1),16); _mask=m.group(2)
    if _seg in _NS2CP:
        _cnt[0]+=1
        return f'inputtag="{_NS2CP[_seg]}" inputmask="{_mask}"'
    _cnt[1]+=1
    return ""  # non-button segment (valuator / SD / undecoded) -> decorative
_lay=_re.sub(r'inputtag="SEG([0-9A-Fa-f]{2})" inputmask="(0x[0-9a-fA-F]+)"',_sub,_lay)
_lay=_re.sub(r' ?inputtag="\{port_name\}"( inputmask="[^"]*")?',"",_lay)  # strip unfilled template artifact
open(_LAY_PATH,"w").write(_lay)
print(f"RELABELED {_cnt[0]} layout buttons SEGxx->CP{{board}}_SEG{{col}} (scan-matrix identity; {_cnt[1]} non-button left decorative)")

# --- Annotate every panel LED placement with its purpose (KN5000 style: <!-- FUNCTION --> right after
#     the opening <element> tag). Generated from LED_PURPOSE (built at the top from the driver bindings),
#     so the comment can never drift. Runs LAST so it cannot disturb the nudge/relabel passes above.
_lay = open(_LAY_PATH).read()
_ann = [0, 0]
def _annotate_led(_m):
    _attrs, _name = _m.group(1), _m.group(2)
    if "<!--" in _m.group(0):            # already annotated (defensive; regen writes fresh anyway)
        return _m.group(0)
    _p = LED_PURPOSE.get(_name)
    if not _p:
        _ann[1] += 1
        return _m.group(0)               # no known purpose -> leave uncommented
    _ann[0] += 1
    return f'<element {_attrs}>{_mk_comment(_p)}'
_lay = re.sub(r'<element ([^>]*\bname="(cp[lcr]_led\d+)"[^>]*)>', _annotate_led, _lay)

# --- Annotate every panel BUTTON placement with its silk name (KN5000 style: <!-- name --> right after
#     the opening <element> tag). Keyed by the button's ACTUAL binding (inputtag=CP{board}_SEG{col},
#     inputmask), looked up in BTN_CP (parsed from the driver INPUT_PORTS), so the comment cannot drift.
#     Runs after the relabel pass, so inputtag is already the final CP scan-column port.
# A few placements bind cells the driver leaves IPT_UNUSED (the LCDR soft-keys, the orphan genres
# ORGANIST/60s&70s, and the speculative CUSTOM PANEL). Their identity comes from the LAYOUT's own
# placement data (RG genre list / LCD_SOFTKEYS row order / the CUSTOM label) via BTN_FALLBACK. If the
# driver later names such a cell, BTN_CP wins automatically (checked first).
_ns2cp = {0x00:"CPL_SEG0",0x01:"CPL_SEG1",0x02:"CPL_SEG2",0x03:"CPL_SEG3",0x04:"CPL_SEG4",0x05:"CPC_SEG5",
          0x06:"CPL_SEG6",0x07:"CPL_SEG7",0x08:"CPC_SEG8",0x09:"CPC_SEG9",0x0a:"CPC_SEG10",0x0b:"CPC_SEG11",
          0x0c:"CPR_SEG0",0x0d:"CPR_SEG1",0x0e:"CPR_SEG2",0x0f:"CPR_SEG3",0x10:"CPR_SEG4",0x11:"CPR_SEG5",
          0x12:"CPR_SEG6",0x13:"CPR_SEG7",0x14:"CPR_SEG8",0x15:"CPR_SEG9"}
def _cpkey(_seg, _mask): return (_ns2cp[int(_seg[3:], 16)], "0x%02x" % int(_mask, 16))
BTN_FALLBACK = {}
for _gnm, _gsg, _gmk in RG:                                   # orphan genres (bound ones resolve via BTN_CP)
    BTN_FALLBACK.setdefault(_cpkey(_gsg, _gmk), _gnm)
# (LCDR 1-5 and CUSTOM PANEL are now real driver-bound buttons -- per Felipe's SW map, LCDR are at
# CPR_SEG5 SW0/SW4/SW5 = 5/1/2, CPR_SEG6 SW0 = 4, CPR_SEG7 SW0 = 3 -- so they resolve via BTN_CP, no
# fallback needed. Only the two orphan RHYTHM genres (ORGANIST, 60s & 70s) remain layout-sourced.)
_btn = [0, 0, 0]
def _annotate_btn(_m):
    if "<!--" in _m.group(0):                # already carries a comment -> leave it
        return _m.group(0)
    _key = (_m.group(2), _m.group(3))
    _nm = BTN_CP.get(_key)
    if _nm:
        _btn[0] += 1
        return f'<element {_m.group(1)}>{_mk_comment(_nm)}'
    _fb = BTN_FALLBACK.get(_key)
    if _fb:
        _btn[1] += 1
        return f'<element {_m.group(1)}>{_mk_comment(_fb)}'   # layout-sourced label (driver cell unnamed)
    _btn[2] += 1
    return _m.group(0)                       # genuinely unknown -> uncommented
_lay = re.sub(r'<element ([^>]*\binputtag="(CP[LCR]_SEG\d+)" inputmask="(0x[0-9a-fA-F]+)"[^>]*)>', _annotate_btn, _lay)

open(_LAY_PATH, "w").write(_lay)
print(f"ANNOTATED {_ann[0]} LED elements with purpose comments ({_ann[1]} placed LEDs had no known purpose)")
print(f"ANNOTATED {_btn[0]} BUTTON elements from the driver + {_btn[1]} from layout data (driver cell unnamed); {_btn[2]} unknown")
