import numpy as np, glob
from PIL import Image
f = sorted(glob.glob('/tmp/dg_cap1/frames/*.png'))
a = np.array(Image.open(f[300]).convert('RGB'))
col = a[:, 300]
for y in range(44, 216):
    print(y, col[y].tolist())
