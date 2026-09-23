#!/usr/bin/env python3
# Q: what is the NULL for a "lines of type X per file" count?
#
# Given a source root and an extension, reports the distribution so a figure
# measured on our files can be read against comparable already-merged code
# instead of against nothing.  Used for the mn10300.h comment-density argument.
import os,re,sys,statistics
root=sys.argv[1]; ext=sys.argv[2]; minl=int(sys.argv[3])
pat=re.compile(r'^[ \t]*(//|/\*|\*)')
rows=[]
for dp,dn,fn in os.walk(root):
    for f in fn:
        if not f.endswith(ext): continue
        p=os.path.join(dp,f)
        try: L=open(p,encoding='utf-8',errors='replace').read().split('\n')
        except: continue
        if L and L[-1]=='': L=L[:-1]
        if len(L)<minl: continue
        c=sum(1 for l in L if pat.match(l))
        rows.append((c/len(L)*100,p.replace(root+'/',''),c,len(L)))
rows.sort()
v=[r[0] for r in rows]
def pct(q): 
    import math
    i=(len(v)-1)*q/100.0
    lo=math.floor(i); hi=math.ceil(i)
    return v[lo] if lo==hi else v[lo]+(v[hi]-v[lo])*(i-lo)
print(f"ext={ext} n={len(rows)} median={pct(50):.1f} p75={pct(75):.1f} p90={pct(90):.1f} p95={pct(95):.1f} p99={pct(99):.1f} max={v[-1]:.1f}")
thr=float(sys.argv[4]) if len(sys.argv)>4 else None
if thr is not None:
    ge=[r for r in rows if r[0]>=thr]
    print(f"  >= {thr}: {len(ge)} files ({len(ge)/len(rows)*100:.1f}%)")
    for r in ge[-12:]: print(f"    {r[0]:5.1f}%  {r[1]}  ({r[2]}/{r[3]})")
