#!/usr/bin/env python3
"""Does the page-2 P=N fallback indicate a fake directory, or a searchable-lag ceiling?
   Reuses the committed port tools/kn5000_period_oracle.py verbatim."""
import sys, bisect, struct, collections
sys.path.insert(0,"/home/fsanches/compartilhado/kn7000_mame/tools")
import kn5000_period_oracle as O
rom=O.load_rom()
for p in range(4):
    d=O.page_dir(rom,p)
    fall=tot=0; byl=collections.Counter(); fbyl=collections.Counter()
    for (st,ns) in d:
        if ns<32 or st+2*ns>len(rom): continue
        tot+=1
        pc=O.detect_period(rom,st,ns,gate=0.5)
        bucket = ns if ns<=256 else ">256"
        byl[bucket]+=1
        if pc==(ns<<16): fall+=1; fbyl[bucket]+=1
    print(f"page {p}: {fall}/{tot} chunks return the P=N fallback")
    if p==2:
        print("   by chunk length:  "+"  ".join(f"{k}:{fbyl[k]}/{byl[k]}" for k in sorted(byl,key=str)))
print("\nMECHANISM (code, kn5000_tonegen.cpp detect_period / the port):")
for N in (64,128,256,512):
    off=N//3; W=min(N-off,4096)
    if W<64: off,W=0,min(N,4096)
    print(f"   N={N:4d} -> window W={W:4d}, maxlag=min(W/2,2048)={min(W//2,2048):4d}"
          f"   a single cycle of length {N} is {'UNREACHABLE' if N>min(W//2,2048) else 'reachable'}")
