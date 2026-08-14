#!/usr/bin/env python3
"""Are page-2's 64-sample chunks WRAP-CONTINUOUS (designed to loop as one cycle)?
   Null = random 64-sample windows cut from real PCM at the same granule alignment."""
import struct, statistics, bisect, random, sys
sys.path.insert(0,"/home/fsanches/compartilhado/kn7000_mame/tools")
import kn5000_period_oracle as O
rom=O.load_rom(); PAGE=0x100000; GRAN=16
d2=O.page_dir(rom,2)
def wrapratio(st,N):
    x=struct.unpack_from("<%dh"%N,rom,st)
    steps=[abs(x[k+1]-x[k]) for k in range(N-1)]
    m=statistics.median(steps) or 1
    return abs(x[0]-x[N-1])/m
r=[wrapratio(st,ns) for st,ns in d2 if ns==64]
print(f"page 2, {len(r)} chunks of 64 samples:")
print(f"  |x[0]-x[63]| / median|dx| : median {statistics.median(r):.2f}  "
      f"frac <= 1.0 : {100*sum(1 for v in r if v<=1)/len(r):.1f}%  frac <= 2.0 : {100*sum(1 for v in r if v<=2)/len(r):.1f}%")
rng=random.Random(11); base=2*PAGE
nul=[]
d0=O.page_dir(rom,0)
for _ in range(len(r)):
    st,ns=d0[rng.randrange(len(d0))]
    if ns<200: continue
    o=st+2*(rng.randrange((ns-64)//8)*8)
    nul.append(wrapratio(o,64))
print(f"NULL, {len(nul)} random 64-sample windows inside page-0 recordings:")
print(f"  |x[0]-x[63]| / median|dx| : median {statistics.median(nul):.2f}  "
      f"frac <= 1.0 : {100*sum(1 for v in nul if v<=1)/len(nul):.1f}%  frac <= 2.0 : {100*sum(1 for v in nul if v<=2)/len(nul):.1f}%")
