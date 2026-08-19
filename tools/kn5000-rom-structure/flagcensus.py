from collections import Counter
P="/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic307"
d=open(P,"rb").read()
PAGE=0x100000
def u16(o): return d[o]|d[o+1]<<8
allflags=Counter(); lastflags=Counter(); back=0; tot=0
per_page_last=[Counter() for _ in range(4)]
for p in range(4):
    b=p*PAGE; n=u16(b)//4
    idx=[(u16(b+4*i), u16(b+4*i+2)) for i in range(n)]
    params=sorted(set(x[0] for x in idx)); waves=sorted(set(x[1] for x in idx))
    for i,(pp,wo) in enumerate(idx):
        tot+=1
        if u16(b+pp)==wo: back+=1
        nx=[q for q in params if q>pp]; end=nx[0] if nx else min(waves)*16
        rec=d[b+pp:b+end]
        pairs=[(rec[j],rec[j+1]) for j in range(2,len(rec),2)]
        for v,f in pairs: allflags[f]+=1
        if pairs:
            lastflags[pairs[-1][1]]+=1
            per_page_last[p][pairs[-1][1]]+=1
print("back-reference OK:", back, "/", tot)
print("\nALL flag bytes, count (top 30):")
for f,c in allflags.most_common(30): print(f"  flag 0x{f:02x}: {c}")
print("\nflag bit pattern summary: bit7 set:", sum(c for f,c in allflags.items() if f&0x80),
      " bit6 set:", sum(c for f,c in allflags.items() if f&0x40),
      " neither:", sum(c for f,c in allflags.items() if not f&0xC0),
      " total:", sum(allflags.values()))
print("\nLAST-pair flag of each record:")
for f,c in lastflags.most_common(20): print(f"  0x{f:02x}: {c}")
print("\nper-page last-pair flags:")
for p in range(4):
    print(f"  page {p}: {dict(per_page_last[p].most_common(8))}")
