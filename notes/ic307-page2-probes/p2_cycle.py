#!/usr/bin/env python3
"""CORRECTED single-cycle test (the previous |x0-x[N-1]|/median|dx| metric measured the
wrong quantity: a cycle that starts on a steep zero crossing legitimately has a large
end-to-start step). Proper signatures of a single-cycle wavetable:
   (a) starts at/near zero, (b) HALF-WAVE ANTISYMMETRY x[k+N/2] == -x[k],
   (c) the wrap step matches the local slope at the start."""
import struct, statistics, random, sys
sys.path.insert(0,"/home/fsanches/compartilhado/kn7000_mame/tools")
import kn5000_period_oracle as O
rom=O.load_rom()
def probe(st,N):
    x=struct.unpack_from("<%dh"%N,rom,st)
    h=N//2
    num=sum((x[k+h]+x[k])**2 for k in range(h)); den=sum(x[k]*x[k] for k in range(h)) or 1
    anti=num/den                      # 0.0 = perfect half-wave antisymmetry
    slope=abs(x[1]-x[0]) or 1
    return abs(x[0]), anti, abs(x[0]-x[N-1])/slope
for p,label in ((2,"page 2 chunks of 64 samples"),):
    d=O.page_dir(rom,p)
    s=[probe(st,64) for st,ns in d if ns==64]
    print(f"{label}: n={len(s)}")
    print(f"  |x[0]| : median {statistics.median(v[0] for v in s):7.0f}   ==0 exactly: "
          f"{sum(1 for v in s if v[0]==0)}   <=64: {sum(1 for v in s if v[0]<=64)}")
    a=[v[1] for v in s]
    print(f"  half-wave antisymmetry residual: median {statistics.median(a):.4f}   "
          f"<0.02: {sum(1 for v in a if v<0.02)}   <0.10: {sum(1 for v in a if v<0.10)}")
    w=[v[2] for v in s]
    print(f"  wrap step / local slope: median {statistics.median(w):.2f}  <=1.5: {sum(1 for v in w if v<=1.5)}")
rng=random.Random(3); d0=O.page_dir(rom,0); nul=[]
while len(nul)<600:
    st,ns=d0[rng.randrange(len(d0))]
    if ns<200: continue
    nul.append(probe(st+2*(rng.randrange((ns-64)//8)*8),64))
a=[v[1] for v in nul]; w=[v[2] for v in nul]
print(f"NULL (random 64-sample windows in page-0 recordings): n={len(nul)}")
print(f"  |x[0]| ==0 exactly: {sum(1 for v in nul if v[0]==0)}   <=64: {sum(1 for v in nul if v[0]<=64)}")
print(f"  half-wave antisymmetry residual: median {statistics.median(a):.4f}   "
      f"<0.02: {sum(1 for v in a if v<0.02)}   <0.10: {sum(1 for v in a if v<0.10)}")
print(f"  wrap step / local slope: median {statistics.median(w):.2f}  <=1.5: {sum(1 for v in w if v<=1.5)}")
