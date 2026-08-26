import sys, numpy as np
from PIL import Image
im = Image.open(sys.argv[1]).convert('L')
B = (np.array(im) < 128)
x0,x1,y0,y1 = map(int, sys.argv[2:6])
minlen = int(sys.argv[6]) if len(sys.argv)>6 else 200
for x in range(x0,x1):
    col = B[y0:y1, x]
    if not col.any(): continue
    runs=[]; s=None
    for i,v in enumerate(col):
        if v and s is None: s=i
        elif not v and s is not None:
            if i-s>=minlen: runs.append((y0+s, y0+i-1, i-s))
            s=None
    if s is not None and len(col)-s>=minlen: runs.append((y0+s, y1-1, len(col)-s))
    if runs: print(x, runs)
