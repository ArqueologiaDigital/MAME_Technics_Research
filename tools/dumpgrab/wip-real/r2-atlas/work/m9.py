import numpy as np
from PIL import Image
a = np.array(Image.open('/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png').convert('RGB')).astype(np.float32)
lum = a @ np.array([0.299,0.587,0.114], np.float32)
# text band: address column x 155..250 (8 chars) - ink profile
band = lum[100:450, 160:880]
bg = np.median(band)
ink = np.clip(bg - band, 0, None)
rp = ink.mean(1)
for i,y in enumerate(range(100,450)):
    print(y, round(float(rp[i]),2))
