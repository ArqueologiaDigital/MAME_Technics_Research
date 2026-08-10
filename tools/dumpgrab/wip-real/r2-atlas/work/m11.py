import numpy as np, glob
from PIL import Image
rom=np.fromfile('/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom',dtype=np.uint8)
F=np.load('font57.npy'); labs=list("0123456789ABCDEF")+[' ','-']
X0,Y0,PX,PY=90,55,6,9
def cell(ink,r,c): return ink[Y0+PY*r:Y0+PY*r+7, X0+PX*c:X0+PX*c+5]
def rd(ink,r,c):
    p=cell(ink,r,c)
    d=[int(np.abs(p-F[i]).sum()) for i in range(18)]
    i=int(np.argmin(d)); return labs[i] if d[i]==0 else '?'
CM_CELL=[59+i for i in range(8)]+[68+j for j in range(8)]
acc={}; nf=0
for fn in sorted(glob.glob('/tmp/dg_cap1/frames/*.png'))[::3]:
    ink=(np.array(Image.open(fn).convert('RGB')).mean(2)<64).astype(np.uint8)
    addr=''.join(rd(ink,0,c) for c in range(8))
    if '?' in addr: continue
    off=int(addr,16)-0x48400000
    if off<0 or off+256>len(rom): continue
    ok=True
    for r in range(16):
        for i in range(16):
            ci=10+3*i if i<8 else 34+3*(i-8)
            h=rd(ink,r,ci); l=rd(ink,r,ci+1)
            if h=='?' or l=='?' or int(h+l,16)!=int(rom[off+r*16+i]): ok=False; break
        if not ok: break
    if not ok: continue
    if rd(ink,0,67)!='-' or rd(ink,0,57)!=' ' or rd(ink,0,58)!=' ': continue
    nf+=1
    for r in range(16):
        for i in range(16):
            b=int(rom[off+r*16+i]); acc.setdefault(b,[]).append(cell(ink,r,CM_CELL[i]))
print('frames', nf, 'distinct bytes', len(acc))
amb=0; G=np.zeros((256,7,5),np.uint8); have=np.zeros(256,bool)
for b,v in acc.items():
    m=np.stack(v).astype(np.float32).mean(0)
    a=float(np.mean((m>0.02)&(m<0.98)))
    if a>0: amb+=1; print('AMBIG byte %02X'%b, a, len(v))
    G[b]=(m>0.5).astype(np.uint8); have[b]=True
print('ambiguous byte classes:', amb, ' missing:', 256-int(have.sum()))
np.savez('charmap256.npz', glyphs=G, have=have)
# collisions
sig={}
for b in range(256):
    if have[b]: sig.setdefault(G[b].tobytes(),[]).append(b)
coll=[v for v in sig.values() if len(v)>1]
print('distinct glyphs among present:', len(sig), 'collision groups:', len(coll))
for v in coll[:12]: print('  ', ' '.join('%02X'%x for x in v))
