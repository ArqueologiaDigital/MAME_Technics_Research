#!/usr/bin/env python3
# lay_kit.py -- the SHARED layout vocabulary used by the Technics panel-layout generators
# (tools/gen_lay.py -> kn7000.lay, tools/gen_kn6000_lay.py -> kn6000.lay).
#
# What lives here is the *mechanism*, not the artwork: the panel colour palette, the element/label
# registries, and the emitters that turn a shape + a bounds rectangle into a MAME <element>/<view>
# line. Model-specific SHAPES (button sizes, the LCD bezel, the wheel...) stay in each generator,
# because they are geometry and the two instruments genuinely differ there.
#
# Extracted verbatim from gen_lay.py so a second model can be drawn without forking that file; the
# KN7000 layout is byte-identical before and after the extraction (verified by regenerating it).
import math, os, re



PANEL="#38383a"; PANEL2="#232325"; BTN="#54545c"; BTN_D="#262628"
LBTN="#626268"; LBTN_D="#2c2c2e"; STROKE="#000"
# Unified "silver" (Felipe): the shared metallic-grey used by the TEMPO/PROGRAM wheel body, MSP pads, the
# pill-shaped buttons (not the orange/START-STOP ones), the PANEL MEMORY buttons + the encircled buttons.
# Made a bit darker than the old wheel body #a3a3a9, still lighter than the grey buttons BTN #54545c.
SILVER="#909097"; SILVER_D="#7a7a82"   # normal / pressed(+bevel)
MSP=SILVER; MSP_D=SILVER_D             # MSP performance pads share the silver
TXT ='<color red="0.90" green="0.90" blue="0.90"/>'
TXTH='<color red="0.72" green="0.72" blue="0.74"/>'
TXTD='<color red="0.13" green="0.13" blue="0.15"/>'   # dark legend colour (for the metallic SD plate)
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
    if ref in ("round_btn","round_btn2","metal_btn","round_btn_silver") and w==32 and h==32:
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
_PILLN=[0]
def _hhalf(w,h,side,fill,fd):   # one horizontal split-pill half: rounded outer end (r=h/2), flat inner edge.
    _PILLN[0]+=1; nm=f"hh{_PILLN[0]}"; sw=1.5; r=h/2.0; ra=(h-sw)/2.0; i=sw/2.0
    d=f'M {w-i:.2f},{i:.2f} L {r:.2f},{i:.2f} A {ra:.2f} {ra:.2f} 0 0 0 {r:.2f},{h-i:.2f} L {w-i:.2f},{h-i:.2f} Z'
    tf='' if side=='l' else f'transform="translate({w},0) scale(-1,1)" '
    b=lambda f:f'<path {tf}stroke="{STROKE}" stroke-width="{sw}" fill="{f}" d="{d}"/>'
    two(nm,w,h,b(fill),b(fd)); return nm
_SEAMN=[0]
def _gapseam(w,h,fill):   # the split-pill centre divider: a NON-clickable rect (no inputtag) with a BLACK
    _SEAMN[0]+=1; nm=f"seam{_SEAMN[0]}"; sw=1.0; i=sw/2.0   # outline + silver fill (Felipe).
    b=f'<rect stroke="{STROKE}" stroke-width="{sw}" fill="{fill}" x="{i:.2f}" y="{i:.2f}" width="{w-sw:.2f}" height="{h-sw:.2f}"/>'
    two(nm,w,h,b,b); return nm
def pair_h(seg,ma,mb,x,y,w,h,la="",lb="",seg2=None,fill=None,fd=None):
    sb=seg2 or seg; fill=fill or SILVER; fd=fd or SILVER_D   # split pills are SILVER (Felipe)
    GAP=4; hw=(w-GAP)//2; gw=w-2*hw      # gw = centre divider width (the two halves each stay hw wide)
    nl=_hhalf(hw,h,'l',fill,fd); nr=_hhalf(hw,h,'r',fill,fd)
    r=[P(nl,x,y,hw,h,tag=seg,mask=ma),P(nr,x+w-hw,y,hw,h,tag=sb,mask=mb),
       P(_gapseam(gw,h,fill),x+hw,y,gw,h)]   # NON-clickable divider (no tag) w/ black outline, fills the gap
    if la: r.append(L(la,x+hw//2-14,y+h//2-6,28,12))
    if lb: r.append(L(lb,x+w-hw//2-14,y+h//2-6,28,12))
    return r
def wrap2(s):
    w=s.split(' ')
    if len(s)<=10 or len(w)==1: return [s]
    h=(len(w)+1)//2; return [' '.join(w[:h]),' '.join(w[h:])]
