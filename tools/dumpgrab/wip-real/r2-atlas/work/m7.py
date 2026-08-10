import numpy as np, glob
from PIL import Image
a = np.array(Image.open('/tmp/dg_cap1/frames/0300.png').convert('RGB'))
row = a[100]
xs=[x for x in range(80,560) if tuple(row[x])==(200,200,200)]
print('native 200 cols at y=100:', xs[:5], xs[-5:])
r2 = a[49]  # top of panel
print('native y=49 x range grey:', [x for x in range(80,560) if tuple(r2[x])!=(0,0,0)][:3])
m=np.all(a==128,axis=2)
sub=m[49:210, :]
cols=np.nonzero(sub.any(0))[0]
print('grey128 cols in panel band', cols.min(), cols.max())
