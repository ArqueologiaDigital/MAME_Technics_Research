import numpy as np, glob
from PIL import Image
f = sorted(glob.glob('/tmp/dg_cap1/frames/*.png'))
X0,Y0,PX,PY = 90,55,6,9
HEX="0123456789ABCDEF"
acc = {c: [] for c in HEX+" -"}
def cell(a, r, c):
    y=Y0+PY*r; x=X0+PX*c
    return a[y:y+7, x:x+5]
for fn in f[::37]:
    a = np.array(Image.open(fn).convert('RGB')).mean(2)
    ink = (a < 64).astype(np.uint8)
    # sanity: cell 7 must be a '0' shape and cell6 = r
    for r in range(16):
        acc[HEX[r]].append(cell(ink,r,6))
        acc['0'].append(cell(ink,r,7))
        acc[' '].append(cell(ink,r,8)); acc[' '].append(cell(ink,r,9))
        acc['-'].append(cell(ink,r,33))
res={}
for c,v in acc.items():
    v=np.stack(v).astype(np.float32)
    m=v.mean(0)
    disagree = np.mean((m>0.02)&(m<0.98))
    res[c]=(m>0.5).astype(np.uint8)
    print(repr(c), 'n=',len(v), 'ambig frac %.4f'%disagree)
np.save('font57.npy', np.stack([res[c] for c in HEX+" -"]))
for c in HEX+" -":
    print(repr(c))
    for row in res[c]:
        print('  '+''.join('#' if x else '.' for x in row))
