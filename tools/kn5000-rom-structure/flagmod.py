from collections import Counter
P="/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic307"
d=open(P,"rb").read()
PAGE=0x100000
def u16(o): return d[o]|d[o+1]<<8
recs=[]
for p in range(4):
    b=p*PAGE; n=u16(b)//4
    idx=[(u16(b+4*i), u16(b+4*i+2)) for i in range(n)]
    params=sorted(set(x[0] for x in idx)); waves=sorted(set(x[1] for x in idx))
    for i,(pp,wo) in enumerate(idx):
        nx=[q for q in params if q>pp]; end=nx[0] if nx else min(waves)*16
        rec=d[b+pp:b+end]
        recs.append((p,i,[(rec[j],rec[j+1]) for j in range(2,len(rec),2)]))
mod=Counter(); allf=[]
for p,i,pairs in recs:
    for v,f in pairs:
        allf.append(f); mod[f%9]+=1
print("flag %% 9 histogram:", dict(sorted(mod.items())))
print("total pairs:", len(allf))
# how many distinct flags, and are they all of form 9k+r with r in {0,1,2,7,8}?
dis=sorted(set(allf))
good=[f for f in dis if f%9 in (0,1,2,7,8)]
print("distinct flags:", len(dis), " of which %9 in {0,1,2,7,8}:", len(good))
print("distinct flags list:", " ".join("%02x"%f for f in dis))
print()
# sample medium records
shown=0
for p,i,pairs in recs:
    if 6 <= len(pairs) <= 14 and p in (0,1):
        print(f"page {p} chunk {i:4d}: " + " ".join("%02x/%02x"%(v,f) for v,f in pairs))
        shown+=1
        if shown>=12: break
