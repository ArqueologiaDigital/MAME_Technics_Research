P="/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic307"
d=open(P,"rb").read()
PAGE=0x100000
def u16(o): return d[o]|d[o+1]<<8
p=3; b=p*PAGE
n=u16(b)//4
idx=[(u16(b+4*i), u16(b+4*i+2)) for i in range(n)]
params=sorted(set(x[0] for x in idx))
waves=sorted(set(x[1] for x in idx))
for i,(pp,wo) in enumerate(idx):
    nxt=[q for q in params if q>pp]
    end=nxt[0] if nxt else (min(waves)*16)
    rec=d[b+pp:b+end]
    wnext=[w for w in waves if w>wo]
    pend=(wnext[0]*16) if wnext else PAGE
    nsamp=(pend-wo*16)//2
    pairs=" ".join(f"{rec[j]:02x}/{rec[j+1]:02x}" for j in range(2,len(rec),2))
    print(f"{i:3d} pp=0x{pp:04X} wo=0x{wo:04X} nsamp={nsamp:6d} back={u16(b+pp):04X} | {pairs}")
