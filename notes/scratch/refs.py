#!/usr/bin/env python3
# refs.py ADDR  -> find all little-endian 32-bit occurrences of ADDR in the image,
# printing the file offset and the mapped code address of each occurrence site.
import struct, sys
IMG="/home/fsanches/compartilhado/kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin"
def off2addr(o):
    return (0x48400000 + o) if o < 0x3B8FD1 else (0x4C000000 + (o - 0x3B8FD1))
data=open(IMG,'rb').read()
target=int(sys.argv[1],0)
needle=struct.pack('<I', target)
i=0
hits=[]
while True:
    j=data.find(needle,i)
    if j<0: break
    hits.append(j)
    i=j+1
print("target=0x%08X  %d hits" % (target,len(hits)))
for j in hits:
    print("  file_off=0x%06X  site_addr=0x%08X" % (j, off2addr(j)))
