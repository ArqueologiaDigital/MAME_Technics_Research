import numpy as np, glob
from PIL import Image
f = sorted(glob.glob('/tmp/dg_cap1/frames/*.png'))
a = np.array(Image.open(f[300]).convert('RGB'))
sub = a[45:215, 80:560]
# unique colours
cols, cnt = np.unique(sub.reshape(-1,3), axis=0, return_counts=True)
o = np.argsort(-cnt)
for i in o[:12]:
    print(cols[i].tolist(), cnt[i])
print('---- row 55..63, x 90..140 luma')
lum = a.mean(2)
for y in range(53, 66):
    print(y, ''.join('#' if lum[y,x]<64 else ('.' if lum[y,x]>180 else ' ') for x in range(88,150)))
