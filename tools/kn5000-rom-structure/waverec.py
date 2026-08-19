import sys
from collections import Counter, defaultdict
P="/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic307"
d=open(P,"rb").read()
PAGE=0x100000
def u16(o): return d[o]|d[o+1]<<8
pages=[]
for p in range(4):
    b=p*PAGE
    n=u16(b)//4
    idx=[(u16(b+4*i), u16(b+4*i+2)) for i in range(n)]
    pages.append((b,n,idx))
    print(f"page {p} base 0x{b:06X} count {n}")
# record extents
for p in range(4):
    b,n,idx=pages[p]
    params=sorted(set(x[0] for x in idx))
    waves=sorted(set(x[1] for x in idx))
    lens=Counter()
    for i,(pp,wo) in enumerate(idx):
        nxt=[q for q in params if q>pp]
        end=nxt[0] if nxt else (min(waves)*16)
        lens[end-pp]+=1
    print(f" page {p}: record-size histogram {dict(sorted(lens.items()))}")
