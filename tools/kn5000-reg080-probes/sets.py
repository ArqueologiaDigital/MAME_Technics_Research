import collections, os, math, pickle
import numpy as np
D = os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000')
ev = open(os.path.join(D,'kn5000_table_data_rom_even.ic3'),'rb').read()
od = open(os.path.join(D,'kn5000_table_data_rom_odd.ic1'),'rb').read()
img = bytearray(0x200000)
for i in range(0,len(ev),2):
    j=(i//2)*4; img[j:j+2]=ev[i:i+2]; img[j+2:j+4]=od[i:i+2]
ROOT=0x30000
u16=lambda o: img[o]|img[o+1]<<8
u32=lambda o: u16(o)|u16(o+2)<<16
s16=lambda v: v-0x10000 if v>=0x8000 else v
rel=lambda r: ROOT+r
set_base=rel(u32(ROOT+0x30)); set_stride=u16(ROOT+0xEC)
a2=[rel(u32(ROOT+o)) for o in (0x24,0x28,0x2C)]
n_sets=(min(a2)-set_base)//set_stride

S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
G=pickle.load(open(S+"G.pkl","rb"))
K=6.2
byent={(r['page'],r['ent']):r for r in G}

sets=[]
for i in range(n_sets):
    d=set_base+set_stride*i
    flags=img[d]; stride=6 if (flags&0x80) else 4
    ptrA=rel(u32(d+1)); ptrB=rel(u32(d+5)); ptrC=rel(u32(ptrA))
    root=img[d+0x0B]; base=u16(d+0x0C); pivot=(root<<8)+0x80
    zones=collections.defaultdict(list)
    for key in range(128):
        E=img[ptrA+4+img[ptrC+key]]
        rec=ptrB+stride*E
        sel=u16(rec)
        trim=s16(u16(rec+4)) if stride==6 else 0
        zones[(sel,(base-pivot)+trim)].append(key)
    sets.append((i,flags,zones))

print("n_sets",n_sets)
rows=[]
for i,flags,zones in sets:
    ic=[(sel,c,ks) for (sel,c),ks in zones.items() if 4<=(sel>>12)<=7]
    if len(ic)<3: continue
    ent=[]
    for sel,c,ks in ic:
        r=byent.get(((sel>>12)&3, sel&0xFFF))
        if r is None: continue
        ent.append((min(ks),max(ks),sel,c,r['ROOT'],r['m'],r['P']))
    if len(ent)<3: continue
    ent.sort()
    R=np.array([e[4] for e in ent])
    rows.append((i,flags,len(ent),R.max()-R.min(),ent))

rows.sort(key=lambda x:-x[2])
print("\nSETs with >=3 IC307 zones measured: %d"%len(rows))
sp=np.array([r[3] for r in rows])
print("ROOT spread within a SET (units): median %.0f  <=64 in %d/%d  <=3072 in %d/%d"
      %(np.median(sp),(sp<=64).sum(),len(sp),(sp<=3072).sum(),len(sp)))
print("  spread/3072 histogram:",sorted(collections.Counter(np.round(sp/3072).astype(int).tolist()).items()))

for i,flags,n,spread,ent in rows[:4]:
    print("\nSET %d  flags=%02X  zones=%d  ROOT spread=%.0f (%.2f octaves)"%(i,flags,n,spread,spread/3072))
    print("   %5s %5s  %6s %7s %9s %4s %9s"%("klo","khi","sel","C","ROOT","m","P"))
    for klo,khi,sel,c,rt,m,P in ent:
        print("   %5d %5d  0x%04X %7d %9.0f %4d %9.3f"%(klo,khi,sel,c,rt,m,P))
