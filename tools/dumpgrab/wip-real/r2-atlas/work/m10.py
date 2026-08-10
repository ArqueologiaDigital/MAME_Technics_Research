import numpy as np, glob, os
from PIL import Image
ROM='/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom'
rom=np.fromfile(ROM,dtype=np.uint8)
print('rom len', hex(len(rom)))
X0,Y0,PX,PY=90,55,6,9
HEX="0123456789ABCDEF"
def cell(ink,r,c):
    return ink[Y0+PY*r:Y0+PY*r+7, X0+PX*c:X0+PX*c+5]
files=sorted(glob.glob('/tmp/dg_cap1/frames/*.png'))
acc={}
nf=0
for fn in files[::5]:
    a=np.array(Image.open(fn).convert('RGB'))
    lum=a.mean(2)
    ink=(lum<64).astype(np.uint8)
    # read address from row0 cells 0..7 using hex font match? use known font
    F=np.load('font57.npy')  # order HEX+' -'
    labs=list(HEX)+[' ','-']
    def rd(r,c):
        p=cell(ink,r,c)
        if p.shape!=(7,5): return None
        d=[np.abs(p-F[i]).sum() for i in range(len(labs))]
        i=int(np.argmin(d))
        return labs[i] if d[i]==0 else None
    addr=''.join(rd(0,c) or '?' for c in range(8))
    if '?' in addr: continue
    base=int(addr,16)
    off=base-0x48400000
    if off<0 or off+256>len(rom): continue
    # verify hex cells match oracle
    okall=True
    for r in range(16):
        for i in range(16):
            b=rom[off+r*16+i]
            cidx=10+3*i if i<8 else 34+3*(i-8)
            h=rd(r,cidx); l=rd(r,cidx+1)
            if h is None or l is None or int(h+l,16)!=int(b):
                okall=False
    if not okall: continue
    nf+=1
    for r in range(16):
        for i in range(16):
            b=int(rom[off+r*16+i])
            ch=chr(b) if 0x20<=b<0x7f else None
            p=cell(ink,r,58+i)
            if p.shape!=(7,5): continue
            key = ch if ch is not None else ('CTRL%02X'%b)
            acc.setdefault(key,[]).append(p)
print('frames used', nf, 'distinct ascii keys', len(acc))
# check all CTRL render the same
ctrl=[k for k in acc if k.startswith('CTRL')]
allc=np.stack([p for k in ctrl for p in acc[k]]) if ctrl else None
if allc is not None:
    m=allc.mean(0); print('ctrl ambig', float(np.mean((m>0.02)&(m<0.98))), 'n',len(allc))
    print('\n'.join(''.join('#' if x>0.5 else '.' for x in row) for row in m))
out={}
for k,v in acc.items():
    v=np.stack(v).astype(np.float32); m=v.mean(0)
    amb=float(np.mean((m>0.02)&(m<0.98)))
    if amb>0: print('AMBIG', k, amb, len(v))
    out[k]=(m>0.5).astype(np.uint8)
np.savez('ascii_font.npz', keys=np.array(sorted(out)), glyphs=np.stack([out[k] for k in sorted(out)]))
print('keys:', ''.join(sorted(k for k in out if not k.startswith('CTRL'))))
