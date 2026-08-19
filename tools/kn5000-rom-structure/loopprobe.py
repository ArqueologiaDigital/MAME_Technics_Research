import struct, math
P="/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic307"
d=open(P,"rb").read()
PAGE=0x100000
def u16(o): return d[o]|d[o+1]<<8
def chunks(p):
    b=p*PAGE; n=u16(b)//4
    idx=[(u16(b+4*i), u16(b+4*i+2)) for i in range(n)]
    params=sorted(set(x[0] for x in idx)); waves=sorted(set(x[1] for x in idx))
    out=[]
    for i,(pp,wo) in enumerate(idx):
        nx=[q for q in params if q>pp]; end=nx[0] if nx else min(waves)*16
        rec=d[b+pp:b+end]
        wn=[w for w in waves if w>wo]; pend=(wn[0]*16) if wn else PAGE
        out.append(dict(i=i,pp=pp,wo=wo,rec=rec,start=b+wo*16,nsamp=(pend-wo*16)//2))
    return out

def samples(c, off, cnt):
    a=c['start']+2*off
    return list(struct.unpack_from("<%dh"%cnt, d, a))

def period(c):
    n=c['nsamp']
    if n<2048: return 0.0
    # window in the body
    w0=int(n*0.55); L=min(4096, n-w0-1)
    x=samples(c,w0,L)
    best=(0,-2)
    seen_neg=False
    for lag in range(2, L//2):
        num=0.0; e1=0.0; e2=0.0
        for i in range(0, L-lag, 4):
            a=x[i]; b=x[i+lag]
            num+=a*b; e1+=a*a; e2+=b*b
        r=num/math.sqrt(e1*e2+1e-9)
        if r<0: seen_neg=True
        if seen_neg and r>best[1]: best=(lag,r)
    return best[0]

for p in [3]:
    cs=chunks(p)
    print("chunk  nsamp   rec              V   P   nsamp/P   V*8/P  V*16/P  V*32/P")
    for c in cs[:16]:
        rec=c['rec']
        pairs=[(rec[j],rec[j+1]) for j in range(2,len(rec),2)]
        if len(pairs)!=1: 
            v,f=pairs[0]
        else:
            v,f=pairs[0]
        V=((f>>6)&3)*256+v
        Pp=period(c)
        if Pp:
            print(f"{c['i']:3d} {c['nsamp']:7d}  {' '.join('%02x/%02x'%q for q in pairs):18s} V={V:4d} P={Pp:4d} n/P={c['nsamp']/Pp:8.2f} {V*8/Pp:7.2f} {V*16/Pp:7.2f} {V*32/Pp:7.2f}")
