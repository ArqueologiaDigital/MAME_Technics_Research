#!/usr/bin/env python3
# callxref.py TARGET_ADDR  -> scan image for MN10300 call (cd=disp16, dd=disp32) sites hitting TARGET
import struct, sys
IMG="/home/fsanches/compartilhado/kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin"
def off2addr(o):
    return (0x48400000 + o) if o < 0x3B8FD1 else (0x4C000000 + (o - 0x3B8FD1))
data=open(IMG,'rb').read()
target=int(sys.argv[1],0)
n=len(data)
hits=[]
for o in range(n-5):
    b=data[o]
    if b==0xcd:
        disp=struct.unpack('<h', data[o+1:o+3])[0]
        site=off2addr(o)
        if site+disp==target: hits.append((site,'cd16'))
    elif b==0xdd:
        disp=struct.unpack('<i', data[o+1:o+5])[0]
        site=off2addr(o)
        if site+disp==target: hits.append((site,'dd32'))
print("callers of 0x%08X: %d" % (target,len(hits)))
for s,k in hits:
    print("  0x%08X (%s)" % (s,k))
