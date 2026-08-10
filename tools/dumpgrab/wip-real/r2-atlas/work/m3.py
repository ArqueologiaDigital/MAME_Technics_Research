import numpy as np, glob
from PIL import Image
f = sorted(glob.glob('/tmp/dg_cap1/frames/*.png'))
print(len(f), f[:2])
a = np.array(Image.open(f[300]).convert('RGB'))
print(a.shape)
# find rows where color==(200,200,200)
m = np.all(a==200, axis=2)
ys,xs=np.nonzero(m)
print('border200 rows', sorted(set(ys.tolist()))[:10], sorted(set(ys.tolist()))[-10:])
print('border200 cols', sorted(set(xs.tolist()))[:6], sorted(set(xs.tolist()))[-6:])
m128 = np.all(a==128, axis=2)
ys,xs=np.nonzero(m128)
print('grey128 y', ys.min(), ys.max(), 'x', xs.min(), xs.max())
