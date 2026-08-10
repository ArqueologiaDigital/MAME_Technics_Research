import numpy as np
from PIL import Image
a = np.array(Image.open('/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png').convert('RGB')).astype(np.float32)
lum = a @ np.array([0.299,0.587,0.114], np.float32)
# horizontal profile over text band y 130..420
prof = lum[130:420].mean(0)
print('--- x 135..175')
for x in range(135,180): print(x, round(float(prof[x]),1))
print('--- x 875..915')
for x in range(875,915): print(x, round(float(prof[x]),1))
