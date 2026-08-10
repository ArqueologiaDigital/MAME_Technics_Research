import numpy as np
from PIL import Image
a = np.asarray(Image.open('/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png').convert('RGB')).astype(np.float32)
lum = a @ np.array([0.299,0.587,0.114],np.float32)
# background estimate: heavy vertical+horizontal median won't be easy; use large box blur
def boxblur(x, kx, ky):
    c = np.cumsum(np.pad(x,((ky,ky+1),(kx,kx+1)),mode='edge'),0)
    c = np.cumsum(c,1)
    # simple: use scipy-free uniform filter via cumsum
    return None
from numpy.lib.stride_tricks import sliding_window_view
sub = lum[100:480, 140:900]
# background = 90th percentile in a sliding window along x of width 41 per row
bg = np.percentile(sub, 85)
print('global bg', bg, 'min', sub.min(), 'max', sub.max())
ink = np.clip(bg-sub,0,None)
rp = ink.mean(1)
ys = np.arange(100,480)
# print compact
s=''
for i,y in enumerate(ys):
    s += '%d:%.1f ' % (y, rp[i])
print(s)
