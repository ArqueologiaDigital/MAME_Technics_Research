import collections, os, math, pickle
import numpy as np
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
G=pickle.load(open(S+"G.pkl","rb"))
byent={(r['page'],r['ent']):r for r in G}
D=os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000')
ev=open(os.path.join(D,'kn5000_table_data_rom_even.ic3'),'rb').read()
od=open(os.path.join(D,'kn5000_table_data_rom_odd.ic1'),'rb').read()
img=bytearray(0x200000)
for i in range(0,len(ev),2):
    j=(i//2)*4; img[j:j+2]=ev[i:i+2]; img[j+2:j+4]=od[i:i+2]
R0=0x30000
u16=lambda o: img[o]|img[o+1]<<8
u32=lambda o: u16(o)|u16(o+2)<<16
rel=lambda r: R0+r
sb=rel(u32(R0+0x30)); st=u16(R0+0xEC)
ns=(min(rel(u32(R0+o)) for o in (0x24,0x28,0x2C))-sb)//st
res=[]
for i in range(ns):
    d=sb+st*i; stride=6 if (img[d]&0x80) else 4
    pA=rel(u32(d+1)); pB=rel(u32(d+5)); pC=rel(u32(pA))
    per=collections.defaultdict(list)
    for key in range(128):
        E=img[pA+4+img[pC+key]]; sel=u16(pB+stride*E); per[sel].append(key)
    pts=[]
    for sel,ks in per.items():
        if not 4<=(sel>>12)<=7: continue
        r=byent.get(((sel>>12)&3,sel&0xFFF))
        if r is None: continue
        if max(ks)-min(ks)>24: continue
        pts.append(((min(ks)+max(ks))/2.0, -12*math.log2(r['P']), sel))
    if len(pts)<4: continue
    x=np.array([p[0] for p in pts]); y=np.array([p[1] for p in pts])
    sl,ic=np.polyfit(x,y,1)
    r2=1-((y-(sl*x+ic))**2).sum()/max(((y-y.mean())**2).sum(),1e-9)
    res.append((i,len(pts),sl,r2,ic))
res.sort(key=lambda t:-t[1])
sl=np.array([r[2] for r in res]); r2=np.array([r[3] for r in res]); ic=np.array([r[4] for r in res])
print("SETs with >=4 measurable narrow IC307 zones: %d"%len(res))
print("slope of (native log-pitch) vs (zone centre key):  median %.3f   IQR %.3f"%(np.median(sl),np.percentile(sl,75)-np.percentile(sl,25)))
print("  slope within 0.9..1.1 : %d/%d = %.1f%%"%(((sl>0.9)&(sl<1.1)).sum(),len(sl),100*((sl>0.9)&(sl<1.1)).mean()))
print("R^2:  median %.4f   >=0.95 in %d/%d = %.1f%%"%(np.median(r2),(r2>=0.95).sum(),len(r2),100*(r2>=0.95).mean()))
good=[r for r in res if 0.9<r[2]<1.1 and r[3]>=0.95]
print("\nSETs passing BOTH (slope~1, R^2>=0.95): %d of %d"%(len(good),len(res)))
gi=np.array([r[4] for r in good])
print("  per-SET intercept (= -12log2(Fs_effective) offset): median %.2f  spread(10-90pct) %.2f st"
      %(np.median(gi),np.percentile(gi,90)-np.percentile(gi,10)))
print("  intercept within +-1 st of the median: %d/%d = %.1f%%"%((abs(gi-np.median(gi))<1).sum(),len(gi),100*(abs(gi-np.median(gi))<1).mean()))
print("  intercept mod 12 (octave-reduced) within +-1 st of its mode: ",end="")
red=(gi-np.median(gi)+6)%12-6
print("%d/%d = %.1f%%"%((abs(red)<1).sum(),len(red),100*(abs(red)<1).mean()))
print("\n  top 12 SETs:")
for i,n,s,r,c in res[:12]:
    print("    SET %3d  zones=%2d  slope=%.3f  R2=%.4f  intercept=%.2f"%(i,n,s,r,c))
