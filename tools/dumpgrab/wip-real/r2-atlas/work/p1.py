import numpy as np
from PIL import Image
im = Image.open('/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png').convert('RGB')
a = np.asarray(im).astype(np.float32)
H,W,_=a.shape
lum = a @ np.array([0.299,0.587,0.114],np.float32)
# vertical profile of the text region: use horizontal gradient energy
g = np.abs(np.diff(lum,axis=1)).mean(1)
for y in range(105,135): print('y',y, round(float(g[y]),2), round(float(lum[y,300:800].mean()),1))
print('...')
for y in range(410,440): print('y',y, round(float(g[y]),2), round(float(lum[y,300:800].mean()),1))
