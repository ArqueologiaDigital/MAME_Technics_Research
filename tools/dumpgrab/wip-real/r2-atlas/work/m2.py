import numpy as np
from PIL import Image
a = np.array(Image.open('/home/fsanches/compartilhado/KN7000/photos/1st-frame-grabbed.png').convert('RGB')).astype(np.float32)
print('sample colors row 300:', a[300, 150:170].astype(int).tolist())
print('panel interior 250,500:', a[250,500].astype(int))
lum = a @ np.array([0.299,0.587,0.114], np.float32)
# vertical profile of mean luma over x 200..850
prof = lum[:, 200:860].mean(1)
for y in range(100, 460):
    pass
import sys
# print rows 105..135 and 400..445
for y in list(range(105,135))+list(range(405,450)):
    print(y, round(float(prof[y]),1))
