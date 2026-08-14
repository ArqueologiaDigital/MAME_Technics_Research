#!/usr/bin/env python3
"""Independent (7th, 8th) tests the six acceptance checks never look at:
   A. does the param area parse as the documented {value:8,flag:8} record grammar?
   B. are the derived chunk LENGTHS quantised (power-of-two), vs a random-offset null?"""
import struct, collections, bisect, math, random
ROM="/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307"
rom=open(ROM,'rb').read(); PAGE=0x100000; GRAN=16
def u16(o): return struct.unpack_from("<H",rom,o)[0]
def dirs(p):
    b=p*PAGE; n=u16(b)//4
    return b,n,[u16(b+i*4) for i in range(n)],[u16(b+i*4+2) for i in range(n)]

print("A. PARAM-RECORD GRAMMAR (record = wave_start u16, then {value,flag} pairs, flag 0xC0-family terminates)")
for p in range(4):
    b,n,pp,wo=dirs(p)
    bounds=sorted(set(pp))+[min(wo)*GRAN]
    lens=[]; term=0; flags=collections.Counter(); twobyte=0
    for i,ptr in enumerate(sorted(set(pp))):
        end=bounds[bisect.bisect_right(bounds,ptr)]
        L=end-ptr; lens.append(L)
        if L==2: twobyte+=1; continue
        pairs=[(rom[b+ptr+2+k*2], rom[b+ptr+3+k*2]) for k in range((L-2)//2)]
        for v,f in pairs: flags[f]+=1
        if pairs and (pairs[-1][1] & 0xC0): term+=1
    nrec=len(set(pp))
    print(f"  page {p}: {nrec} records  2-byte(bare wave_start) {twobyte}  longer {nrec-twobyte}  "
          f"ending on a 0xC0-family flag: {term}/{nrec-twobyte}")
    print(f"          flag vocabulary size {len(flags)}, top: {flags.most_common(8)}")

print("\nB. CHUNK-LENGTH QUANTISATION")
def lengths(wo):
    s=sorted(set(wo)); out=[]
    for w in wo:
        j=bisect.bisect_right(s,w); end=s[j]*GRAN if j<len(s) else PAGE
        out.append(max(0,(end-w*GRAN)//2))
    return out
pow2=lambda L: L>0 and (L & (L-1))==0
for p in range(4):
    b,n,pp,wo=dirs(p); L=lengths(wo)
    print(f"  page {p}: n={n}  power-of-two lengths {sum(1 for x in L if pow2(x))}/{n} "
          f"({100*sum(1 for x in L if pow2(x))/n:.1f}%)  "
          f"multiple-of-16-samples {sum(1 for x in L if x%16==0)}/{n}  median {sorted(L)[n//2]}")
# NULL: same count of RANDOM in-page offsets (granule-aligned), same length rule
rng=random.Random(7)
b,n,pp,wo=dirs(2)
fr=[]
for t in range(200):
    r=sorted(rng.randrange(0x26A, 0x10000) for _ in range(len(set(wo))))
    Ls=lengths(r)
    fr.append(sum(1 for x in Ls if pow2(x))/len(Ls))
print(f"  NULL (200 draws of {len(set(wo))} random granule offsets in page 2's PCM span): "
      f"power-of-two fraction mean {100*sum(fr)/len(fr):.2f}% max {100*max(fr):.2f}%")

print("\nC. ARE THE 64-SAMPLE CHUNKS SINGLE-CYCLE WAVEFORMS?")
b,n,pp,wo=dirs(2); L=lengths(wo)
sel=[i for i in range(n) if L[i]==64][:400]
zc=[];ends=[]
for i in sel:
    st=b+wo[i]*GRAN
    x=struct.unpack_from("<64h",rom,st)
    s=sum(1 for k in range(63) if (x[k]<0)!=(x[k+1]<0))
    zc.append(s); ends.append(abs(x[0])<3000 and abs(x[-1])<3000)
print(f"  {len(sel)} chunks of exactly 64 samples: sign-changes per chunk -> "
      f"{collections.Counter(zc).most_common(8)}")
print(f"  chunks whose first AND last sample are near zero (|v|<3000): {sum(ends)}/{len(sel)}")
print("  (2 sign changes over 64 samples = exactly ONE cycle in the chunk)")
