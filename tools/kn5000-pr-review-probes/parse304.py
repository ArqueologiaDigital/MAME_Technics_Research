import struct, sys
PAGE=0x100000
data=open('/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic304','rb').read()
def u16(b,o): return b[o]|(b[o+1]<<8)
for p in range(4):
    pg=data[p*PAGE:(p+1)*PAGE]
    head=u16(pg,0)
    if not head or (head&3): print("page",p,"reject head",hex(head)); continue
    n=head//4
    if n*4 > PAGE-4: print("page",p,"reject n"); continue
    param=[];wave=[];ok=True
    for i in range(n):
        pa=u16(pg,i*4); wa=u16(pg,i*4+2)
        param.append(pa); wave.append(wa)
        if i and pa<param[i-1]: ok=False;break
        if pa < n*4: ok=False;break
        if wa*16>=PAGE: ok=False;break
        if u16(pg,pa)!=wa: ok=False;break
    if not ok: print("page",p,"reject at",i); continue
    srt=sorted(set(wave))
    import bisect
    samples=[]
    for i in range(n):
        j=bisect.bisect_right(srt,wave[i])
        end = PAGE if j==len(srt) else srt[j]*16
        off=wave[i]*16
        samples.append((end-off)//2 if end>off else 0)
    big=[ (i,s) for i,s in enumerate(samples) if s>=65536 ]
    print("page",p,"n=",n,"max samples",max(samples),"count>=65536:",len(big), "count==0:",sum(1 for s in samples if s==0))
    if big[:5]: print("   examples:",big[:5])
