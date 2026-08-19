import collections, os, math, pickle
import numpy as np
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
G=pickle.load(open(S+"G.pkl","rb"))
K=6.2
# ---- (1) global window rule for C
best=None
for W in range(-6144,3072,8):
    ok=0
    for r in G:
        base=K+3072.0*math.log2(r['P'])          # C = base + 3072*m
        m=math.floor((W+3072-base)/3072.0)        # put C in [W, W+3072)
        if abs(base+3072*m - r['C'])<64: ok+=1
    if best is None or ok>best[1]: best=(W,ok)
W,ok=best
print("BEST GLOBAL WINDOW  C in [%d, %d):  exact-C recovery %d/%d = %.1f%%"%(W,W+3072,ok,len(G),100*ok/len(G)))
# per class
for cl in range(4,8):
    sub=[r for r in G if r['page']==cl-4]
    o=sum(1 for r in sub if abs(K+3072*math.log2(r['P'])+3072*math.floor((W+3072-(K+3072*math.log2(r['P'])))/3072.0)-r['C'])<64)
    print("   class %d: %3d/%3d = %5.1f%%"%(cl,o,len(sub),100*o/len(sub)))
# split by C==0 vs C!=0
for lab,sub in (("C==0 selectors",[r for r in G if r['C']==0]),("C!=0 selectors",[r for r in G if r['C']!=0])):
    o=sum(1 for r in sub if abs(K+3072*math.log2(r['P'])+3072*math.floor((W+3072-(K+3072*math.log2(r['P'])))/3072.0)-r['C'])<64)
    print("   %-16s %3d/%3d = %5.1f%%"%(lab,o,len(sub),100*o/len(sub)))

# ---- (2) does the measured native note land in the firmware key zone?
import re
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
a2=[rel(u32(R0+o)) for o in (0x24,0x28,0x2C)]
ns=(min(a2)-sb)//st
zone=collections.defaultdict(list)
for i in range(ns):
    d=sb+st*i; stride=6 if (img[d]&0x80) else 4
    pA=rel(u32(d+1)); pB=rel(u32(d+5)); pC=rel(u32(pA))
    per=collections.defaultdict(list)
    for key in range(128):
        E=img[pA+4+img[pC+key]]; sel=u16(pB+stride*E); per[sel].append(key)
    for sel,ks in per.items():
        if 4<=(sel>>12)<=7: zone[sel].append((min(ks),max(ks)))
byent={(r['page'],r['ent']):r for r in G}
# calibrate ONE global sample rate: nu = 12*log2(Fs/P) ; minimise |nu - zone centre|
cands=[]
for sel,zs in zone.items():
    r=byent.get(((sel>>12)&3,sel&0xFFF))
    if r is None: continue
    klo,khi=min(z[0] for z in zs),max(z[1] for z in zs)
    if khi-klo>24: continue                      # skip the catch-all end zones
    cands.append((r['P'],(klo+khi)/2.0,klo,khi))
print("\nzones usable for the octave test: %d"%len(cands))
off=np.array([c[1]+12*math.log2(c[0]) for c in cands])   # nu = -12log2 P + A  ->  A = centre + 12 log2 P
A=float(np.median(off))
Fs=440.0*2**((A-69)/12.0)
print("ONE GLOBAL SAMPLE RATE  A=%.2f  => Fs = %.0f Hz   (nu = A - 12*log2(P))"%(A,Fs))
err=np.array([ (A-12*math.log2(c[0])) - c[1] for c in cands])
print("  native-note MINUS zone centre: median %.2f st, IQR %.2f, |err|<6 st %.1f%%, |err|<12 st %.1f%%"
      %(np.median(err),np.percentile(err,75)-np.percentile(err,25),100*(abs(err)<6).mean(),100*(abs(err)<12).mean()))
inz=[1 if c[2]-3<=A-12*math.log2(c[0])<=c[3]+3 else 0 for c in cands]
print("  native note lands INSIDE its own key zone (+-3 st): %d/%d = %.1f%%"%(sum(inz),len(inz),100*np.mean(inz)))
oct_err=np.round(err/12).astype(int)
print("  octave error histogram:",sorted(collections.Counter(oct_err.tolist()).items()))

print("\n--- per-PAGE sample-rate calibration ---")
bypage=collections.defaultdict(list)
for sel,zs in zone.items():
    r=byent.get(((sel>>12)&3,sel&0xFFF))
    if r is None: continue
    klo,khi=min(z[0] for z in zs),max(z[1] for z in zs)
    if khi-klo>24: continue
    bypage[(sel>>12)&3].append((r['P'],(klo+khi)/2.0,klo,khi,sel))
for p in sorted(bypage):
    c=bypage[p]
    A=float(np.median([x[1]+12*math.log2(x[0]) for x in c]))
    Fs=440.0*2**((A-69)/12.0)
    err=np.array([(A-12*math.log2(x[0]))-x[1] for x in c])
    inz=[1 if x[2]-3<=A-12*math.log2(x[0])<=x[3]+3 else 0 for x in c]
    print("  page %d  n=%3d  A=%.2f  Fs=%6.0f Hz  |err|<3st %5.1f%%  in-zone %5.1f%%  oct-err %s"
          %(p,len(c),A,Fs,100*(abs(err)<3).mean(),100*np.mean(inz),
            sorted(collections.Counter(np.round(err/12).astype(int).tolist()).items())))
