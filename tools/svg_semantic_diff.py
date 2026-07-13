#!/usr/bin/env python3
"""Semantic diff of two KN7000 layout SVGs -> per-stable-ID deltas (Felipe's nudges).
Resolves the full transform chain to each leaf; matches unique-signature leaves 1:1 and duplicate-signature
leaves by MUTUAL-nearest (safe: never mis-moves); aggregates per stable-ID element. Writes /tmp/layout_nudges.json."""
import re, math, json
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
NS='{http://www.w3.org/2000/svg}'

def mat_mul(A,B):
    a,b,c,d,e,f=A; g,h,i,j,k,l=B
    return (a*g+c*h,b*g+d*h,a*i+c*j,b*i+d*j,a*k+c*l+e,b*k+d*l+f)
def apply_mat(M,x,y):
    a,b,c,d,e,f=M; return (a*x+c*y+e,b*x+d*y+f)
def parse_tf(s):
    M=(1,0,0,1,0,0)
    for name,args in re.findall(r'(translate|scale|matrix)\s*\(([^)]*)\)',s or ''):
        n=[float(v) for v in re.split(r'[ ,]+',args.strip()) if v]
        if name=='translate': t=(1,0,0,1,n[0],n[1] if len(n)>1 else 0)
        elif name=='scale': t=(n[0],0,0,n[1] if len(n)>1 else n[0],0,0)
        else: t=tuple(n[:6])
        M=mat_mul(M,t)
    return M
def nfill(el):
    st=el.get('style','') or ''; m=re.search(r'fill:\s*([^;]+)',st)
    return (m.group(1).strip() if m else (el.get('fill','') or '')).lower()
def nstroke(el):
    st=el.get('style','') or ''; m=re.search(r'stroke:\s*([^;]+)',st)
    return (m.group(1).strip() if m else (el.get('stroke','') or '')).lower()
def leaf(el):
    t=el.tag.replace(NS,'')
    if t=='circle': return (float(el.get('cx',0)),float(el.get('cy',0))),f"circ:r{round(float(el.get('r',0)))}:{nfill(el)}:{nstroke(el)}"
    if t=='rect':
        w=float(el.get('width',0)); h=float(el.get('height',0))
        return (float(el.get('x',0))+w/2,float(el.get('y',0))+h/2),f"rect:{round(w)}x{round(h)}:{nfill(el)}"
    if t=='text': return (float(el.get('x',0)),float(el.get('y',0))),"text:"+''.join(el.itertext()).strip()
    if t=='line': return (float(el.get('x1',0)),float(el.get('y1',0))),f"line:{round(float(el.get('x2',0))-float(el.get('x1',0)))}x{round(float(el.get('y2',0))-float(el.get('y1',0)))}"
    if t=='path':
        m=re.search(r'[Mm]\s*([-\d.eE]+)[ ,]+([-\d.eE]+)',el.get('d','') or '')
        return ((float(m.group(1)),float(m.group(2))) if m else (0,0)),"path:"+(el.get('d','') or '')[:24]
    return None,None
def sid(el,par):
    c=el
    while c is not None:
        i=c.get('id','') or ''
        if re.match(r'^[A-Za-z_]+\.\d+\.',i): return i
        c=par.get(c)
    return None
def collect(path):
    root=ET.parse(path).getroot(); par={c:p for p in root.iter() for c in p}
    out=[]
    for el in root.iter():
        t=el.tag.replace(NS,'')
        if t not in ('circle','rect','text','line','path'): continue
        if t=='rect' and (float(el.get('width',0))>=1990 or float(el.get('height',0))>=990): continue
        anc=el; bad=False
        while anc is not None:
            if anc.tag.replace(NS,'') in ('defs','clipPath'): bad=True; break
            anc=par.get(anc)
        if bad: continue
        lp,s=leaf(el)
        if lp is None: continue
        chain=[]; c=el
        while c is not None: chain.append(parse_tf(c.get('transform',''))); c=par.get(c)
        M=(1,0,0,1,0,0)
        for tr in reversed(chain): M=mat_mul(M,tr)
        ax,ay=apply_mat(M,lp[0],lp[1])
        out.append((s,(round(ax,2),round(ay,2)),sid(el,par)))
    return out

O=collect('kn7000_layout_original.svg'); A=collect('kn7000_layout_adjusted.svg')
ob=defaultdict(list); ab=defaultdict(list)
for s,p,i in O: ob[s].append((p,i))
for s,p,i in A: ab[s].append((p,i))
per_id=defaultdict(list); skipped=0
for sig in set(ob)|set(ab):
    os_=ob.get(sig,[]); as_=ab.get(sig,[])
    if len(os_)==1 and len(as_)==1:              # unique -> forced 1:1
        op,oid=os_[0]; ap=as_[0][0]
        if oid: per_id[oid].append((round(ap[0]-op[0],1),round(ap[1]-op[1],1)))
        continue
    # multi -> mutual nearest
    if not as_ or not os_:
        continue
    an=[min(range(len(os_)),key=lambda k:math.hypot(as_[j][0][0]-os_[k][0][0],as_[j][0][1]-os_[k][0][1])) for j in range(len(as_))]
    for oi,(op,oid) in enumerate(os_):
        aj=min(range(len(as_)),key=lambda k:math.hypot(op[0]-as_[k][0][0],op[1]-as_[k][0][1]))
        if an[aj]==oi:                            # mutual nearest
            ap=as_[aj][0]
            if oid: per_id[oid].append((round(ap[0]-op[0],1),round(ap[1]-op[1],1)))
        else:
            skipped+=1
# aggregate per element (mode delta), keep nonzero
nudges={}; ambiguous=[]
for eid,ds in per_id.items():
    dxy,cnt=Counter(ds).most_common(1)[0]
    if abs(dxy[0])>0.5 or abs(dxy[1])>0.5:
        agree=cnt/len(ds)
        if agree>0.6: nudges[eid]=[dxy[0],dxy[1]]
        else: ambiguous.append((eid,ds))
json.dump(nudges,open('/tmp/layout_nudges.json','w'),indent=1)
print(f"leaves O={len(O)} A={len(A)}; mutual-nearest skipped {skipped} leaf pairs")
print(f"NUDGED ELEMENTS: {len(nudges)}  (ambiguous/skipped elements: {len(ambiguous)})")
for eid,d in sorted(nudges.items(),key=lambda x:-abs(x[1][0])-abs(x[1][1])):
    print(f"  {eid:34} delta=({d[0]:+.1f},{d[1]:+.1f})")
if ambiguous:
    print("--- ambiguous (leaves disagree, NOT applied) ---")
    for eid,ds in ambiguous[:20]: print(f"  {eid}: {Counter(ds).most_common(3)}")
