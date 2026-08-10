import numpy as np
from PIL import Image
a = np.array(Image.open('/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png').convert('RGB')).astype(np.float32)
H,W,_ = a.shape
print('shape', a.shape)
# grey-ish: r~g~b and mid level
r,g,b = a[:,:,0],a[:,:,1],a[:,:,2]
mx = a.max(2); mn = a.min(2)
sat = mx-mn
grey = (sat < 40) & (mx > 60) & (mx < 220)
ys,xs = np.nonzero(grey)
print('grey bbox x', xs.min(), xs.max(), 'y', ys.min(), ys.max(), 'count', len(xs))
# column/row profiles of greyness
colp = grey.sum(0); rowp = grey.sum(1)
import sys
np.set_printoptions(linewidth=250, threshold=10000)
# find contiguous run where colp large
th = grey.sum()/ max(1,(ys.max()-ys.min()+1)) * 0.3
print('rows with grey>50:', np.nonzero(rowp>50)[0].min(), np.nonzero(rowp>50)[0].max())
print('cols with grey>50:', np.nonzero(colp>50)[0].min(), np.nonzero(colp>50)[0].max())
