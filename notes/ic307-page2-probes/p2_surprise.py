#!/usr/bin/env python3
"""How surprising is check 6 passing 1072x? Honest model: the param block must REPRODUCE
the wave column. Measure the information content of what has to coincide, and check the
degenerate escape route (constant data) that produced the null's own false positives."""
import struct, collections, math, bisect
ROM="/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307"
rom=open(ROM,'rb').read(); PAGE=0x100000; GRAN=16
def dirs(p):
    b=p*PAGE; n=struct.unpack_from("<H",rom,b)[0]//4
    return b,n,[struct.unpack_from("<H",rom,b+i*4)[0] for i in range(n)],\
             [struct.unpack_from("<H",rom,b+i*4+2)[0] for i in range(n)]
b,n,pp,wo=dirs(2)
print("Is the param block a literal duplicate of the wave column?")
run=0
for i in range(n):
    if pp[i]==0x10C0+2*i: run+=1
    else: break
print(f"  entries whose param_ptr == 0x10C0 + 2*i (pure duplicate prefix): {run}")
print(f"  2-byte records overall: {sum(1 for i in range(1,n) if pp[i]-pp[i-1]==2)} of {n-1} gaps")
gaps=[wo[i]-wo[i-1] for i in range(1,n)]
cnt=collections.Counter(gaps); tot=len(gaps)
H=-sum(c/tot*math.log2(c/tot) for c in cnt.values())
print(f"\nINFORMATION IN WHAT MUST COINCIDE:")
print(f"  wave_off gap alphabet: {len(cnt)} distinct values, empirical entropy {H:.2f} bits/step")
print(f"  -> the duplicated column carries >= {H*tot:.0f} bits that the param block reproduces exactly")
print(f"  gap histogram top: {cnt.most_common(8)}")
print(f"  the null's false positives (ic19 n=8640, v10 n=448) had 1 distinct wave value:")
print(f"     entropy 0.00 bits/step -> ONE coincidence repeated, not {tot} of them")
print(f"  uniform-u16 model for 1072 disjoint back-references: log10 P = {-16*n*math.log10(2):.0f}")

print("\nORGAN CLICK cross-check (name table says class 6 entries 0x028,0x030,...,0x068):")
srt=sorted(set(wo))
def L(i):
    j=bisect.bisect_right(srt,wo[i]); end=srt[j]*GRAN if j<len(srt) else PAGE
    return max(0,(end-wo[i]*GRAN)//2)
for e in (0x028,0x030,0x038,0x040,0x048,0x050,0x058,0x060,0x068):
    print(f"   entry 0x{e:03X} -> wave_off 0x{wo[e]:04X} @0x{b+wo[e]*GRAN:06X}  {L(e):5d} samples "
          f"({1000*L(e)/32000:.1f} ms at 32 kHz)")
lens=[L(i) for i in range(n)]
print(f"   page-2 median chunk {sorted(lens)[n//2]} samples; these 9 are all "
      f"{'<=' if max(L(e) for e in (0x28,0x30,0x38,0x40,0x48,0x50,0x58,0x60,0x68))<=256 else '>'} 256")
