"""Is 'P = N' the CORRECT answer on page 2's power-of-two chunks?
Test: a true single-cycle wave has NO sub-period. Compare energy at lag N/2 and N/4
(normalised autocorrelation) -- a single cycle scores LOW at both; a 2-cycle or 4-cycle
chunk scores HIGH at N/2 or N/4. NULL/CONTROL: the 256-sample page-0 entry 0 is the
documented single sine cycle (kn5000-ic307-content-map.md 2.1) -> must score LOW."""
import sys, numpy as np, collections, statistics, struct
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
import kn5000_period_oracle as O
rom=O.load_rom(); d2=O.page_dir(rom,2); d0=O.page_dir(rom,0)
def ac(start,n,lag):
    x=np.frombuffer(rom,dtype='<i2',count=n,offset=start).astype(np.float64); x-=x.mean()
    a=x[:n-lag]; b=x[lag:]
    den=np.sqrt((a*a).sum()*(b*b).sum())
    return float((a*b).sum()/den) if den>0 else 0.0
def score(start,n): return max(ac(start,n,n//2), ac(start,n,n//4))
print("CONTROL: page-0 entry 0 = the documented single 256-sample sine cycle")
s,n=d0[0]; print(f"   len {n}  r(N/2)={ac(s,n,n//2):+.3f}  r(N/4)={ac(s,n,n//4):+.3f}  -> score {score(s,n):+.3f}")
print("CONTROL: page-0 long recordings (median 1920 samples, known multi-cycle) -- must score HIGH")
sc=[score(s,n) for s,n in d0[1:60]]
print(f"   n=59 median score {statistics.median(sc):+.3f}   frac>0.5 {sum(1 for x in sc if x>0.5)/len(sc):.2f}")
print()
groups=collections.defaultdict(list)
for i,(s,n) in enumerate(d2):
    if n<16: continue
    p2 = n and (n&(n-1))==0
    groups['page2 power-of-two (n=%d)'%0 if False else ('page2 POW2' if p2 else 'page2 non-pow2')].append(score(s,n))
for k,v in groups.items():
    print(f"{k:22s} n={len(v):5d} median {statistics.median(v):+.3f}  frac>0.5 {sum(1 for x in v if x>0.5)/len(v):.2f}")
print()
print("the two organ waves the firmware actually selects:")
for name,e in (("DIGITAL DRAWBAR / Accomp Drawbars +040=0x6096",0x096),("Organ Bass / Soul Organ +040=0x6070",0x070),
               ("Organ Click +040=0x6028",0x028),("Organ Click +040=0x6068",0x068)):
    s,n=d2[e]
    per=O.detect_period(rom,s,n)
    print(f"   {name:46s} entry 0x{e:03X} off 0x{s-0x200000:06X} len {n:5d}  detect_period -> {'P=N (whole chunk = one cycle)' if per==(n<<16) else 'P=%.1f'%(per/65536)}  score {score(s,n):+.3f}")
