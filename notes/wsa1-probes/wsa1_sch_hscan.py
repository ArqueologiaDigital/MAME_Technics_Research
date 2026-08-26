import sys, numpy as np
from PIL import Image
im = Image.open(sys.argv[1]).convert('L')
A = np.array(im)
B = (A < 128)
x0,x1,y0,y1 = map(int, sys.argv[2:6])
# report, for each row y in [y0,y1), the longest run of black starting at/after x0
for y in range(y0,y1):
    row = B[y, x0:x1]
    if not row.any(): continue
    # find runs
    runs=[]
    s=None
    for i,v in enumerate(row):
        if v and s is None: s=i
        elif not v and s is not None:
            if i-s>=15: runs.append((x0+s, x0+i-1, i-s))
            s=None
    if s is not None and len(row)-s>=15: runs.append((x0+s, x1-1, len(row)-s))
    if runs:
        print(y, runs[:8])
