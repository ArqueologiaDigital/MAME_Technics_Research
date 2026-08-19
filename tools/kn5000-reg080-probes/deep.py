import numpy as np, re, math
from collections import Counter, defaultdict
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
ROM="/home/fsanches/compartilhado/kn5000_original_roms/kn5000/kn5000_waveform_rom.ic307"
rom=open(ROM,'rb').read()
PAGE=0x100000
def u16(b,o): return b[o]|(b[o+1]<<8)
def scan(page):
    base=page*PAGE; pg=rom[base:base+PAGE]; n=u16(pg,0)//4
    param=[u16(pg,i*4) for i in range(n)]; wave=[u16(pg,i*4+2) for i in range(n)]
    srt=sorted(set(wave)); sp=sorted(set(param))
    out=[]
    for i in range(n):
        j=np.searchsorted(srt,wave[i],side='right'); end=PAGE if j>=len(srt) else srt[j]*16
        off=wave[i]*16
        k=np.searchsorted(sp,param[i],side='right'); rend=sp[k] if k<len(sp) else None
        out.append(dict(start=base+off,ns=(end-off)//2 if end>off else 0,
                        pp=param[i],rlen=(rend-param[i]) if rend else 0,
                        rec=pg[param[i]:rend] if rend else b''))
    return out
D={p:scan(p) for p in range(4)}
a=np.load(S+"per.npy"); per={(int(r[0]),int(r[1])):(r[2],r[3]) for r in a}
HXX="/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn5000_pitch_trim.hxx"
rows=re.findall(r'\{\s*0x([0-9A-Fa-f]{4}),\s*(-?\d+),\s*(\d)\s*\}',open(HXX).read())
C={int(x,16):(int(y),int(z)) for x,y,z in rows}

rec=[]
for sel,(c,amb) in sorted(C.items()):
    cls=sel>>12
    if not 4<=cls<=7: continue
    page=cls&3; ent=sel&0xFFF
    P,q=per.get((page,ent),(0,9))
    if P<=0: continue
    d=D[page][ent]
    rec.append(dict(sel=sel,page=page,ent=ent,C=c,amb=amb,P=P,q=q,
                    NAT=-3072*math.log2(P),ROOT=-3072*math.log2(P)+c,
                    ns=d['ns'],rlen=d['rlen'],recb=d['rec']))

def report(rs,label):
    R=np.array([r['ROOT'] for r in rs])
    if len(R)<5: print(label,"n<5"); return None
    ang=np.mod(R,3072.)/3072*2*np.pi
    K=(math.atan2(np.sin(ang).mean(),np.cos(ang).mean())/(2*np.pi))*3072%3072
    dev=(R-K+1536)%3072-1536
    print("%-38s n=%4d  K=%7.1f  |dev|med=%5.1f u (%4.1f ct)  <=25ct %5.1f%%  <=50ct %5.1f%%"
          %(label,len(R),K,np.median(abs(dev)),np.median(abs(dev))/2.56,
            100*(abs(dev)<64).mean(),100*(abs(dev)<128).mean()))
    return K

report(rec,"ALL IC307 selectors")
report([r for r in rec if r['amb']==0],"single-valued C")
report([r for r in rec if r['amb']==0 and r['q']<0.3],"single-C + YIN d'<0.30")
report([r for r in rec if r['amb']==0 and r['q']<0.15],"single-C + YIN d'<0.15")
for p in range(4):
    report([r for r in rec if r['page']==p and r['amb']==0 and r['q']<0.3],"  page %d single-C d'<0.30"%p)
# dedupe to distinct chunks
seen={}
for r in rec:
    if r['amb']==0 and r['q']<0.3: seen.setdefault((r['page'],r['ent']),r)
K=report(list(seen.values()),"DISTINCT CHUNKS single-C d'<0.30")
np.save(S+"K.npy",np.array([K]))
import pickle; pickle.dump(rec,open(S+"rec.pkl","wb"))
