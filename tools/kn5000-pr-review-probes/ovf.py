import numpy as np, bisect
PAGE=0x100000
data=np.fromfile('/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic307',dtype=np.uint8)
def u16(b,o): return int(b[o])|(int(b[o+1])<<8)
tot=0; ovf=0; worst=0; nrec=0
for p in range(4):
    pg=data[p*PAGE:(p+1)*PAGE]
    head=u16(pg,0); n=head//4
    wave=[u16(pg,i*4+2) for i in range(n)]
    srt=sorted(set(wave))
    for i in range(n):
        j=bisect.bisect_right(srt,wave[i]); end=PAGE if j==len(srt) else srt[j]*16
        off=wave[i]*16; ns=(end-off)//2
        if ns<2: continue
        nrec+=1
        s=pg[off:off+ns*2].view(np.int16).astype(np.int32)
        d=np.abs(np.diff(s))
        tot+=len(d); ovf+=int((d>32768).sum()); worst=max(worst,int(d.max()))
print("recordings",nrec,"adjacent pairs",tot,"pairs with |b-a|>32768:",ovf, "(%.4f%%)"%(100.0*ovf/tot), "max |b-a|",worst)
# for pairs that overflow, minimum frac needed
