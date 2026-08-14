"""NULL/CONTROL for 'no zone table addresses page-2 entry > 0x096'.
Claim every byte of the zone-table region that the 487 SET descriptors reach
(ptrA slot table, ptrB record array, ptrC 128-byte key table), then look at what
is LEFT OVER. If a leftover run decodes as a stride-4/6 wave-select array whose
class-6 entries exceed 0x096, the claim is REFUTED."""
import struct, collections
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
img=open(SC+'table_data.bin','rb').read()
BASE=0x050000
def off(s): return s-0x020000
def u8(s): return img[off(s)]
def u16(s): return struct.unpack_from('<H',img,off(s))[0]
def u32(s): return struct.unpack_from('<I',img,off(s))[0]
LO,HI=0x07AD9D,0x084E6F           # the zone/key/partial-record region (note table, root+0x24..+0x78)
claimed=bytearray(HI-LO)
def mark(a,n):
    for x in range(a,a+n):
        if LO<=x<HI: claimed[x-LO]=1
SETBASE=0x077914;N=487;ST=15
for i in range(N):
    p=SETBASE+ST*i
    flags=u8(p);ptrA=u32(p+1)+BASE;ptrB=u32(p+5)+BASE;ptrC=u32(ptrA)+BASE
    stride=6 if flags&0x80 else 4
    slots=[u8(ptrC+k) for k in range(128)]
    ms=max(slots)
    Emap=[u8(ptrA+4+s) for s in range(ms+1)]
    mark(ptrA,4+ms+1); mark(ptrC,128); mark(ptrB,stride*(max(Emap)+1))
n_cl=sum(claimed); tot=HI-LO
print(f"zone-table region {LO:06X}..{HI:06X} = {tot} bytes; claimed by the 487 SETs = {n_cl} ({100.0*n_cl/tot:.1f}%)")
# leftover runs
runs=[];i=0
while i<tot:
    if claimed[i]: i+=1; continue
    j=i
    while j<tot and not claimed[j]: j+=1
    runs.append((LO+i,j-i)); i=j
runs.sort(key=lambda r:-r[1])
print(f"leftover runs: {len(runs)}, total {sum(r[1] for r in runs)} bytes; 10 largest:")
for a,n in runs[:10]: print(f"   {a:06X} +{n}")
# decode every leftover run as both strides, count class-6 entries > 0x096
hits=[]
c6=collections.Counter(); c6big=collections.Counter()
for a,n in runs:
    for stride in (4,6):
        for k in range(n//stride):
            w=u16(a+stride*k)
            if (w>>12)&0xF==6:
                e=w&0xFFF
                c6[e]+=1
                if e>0x096: c6big[e]+=1; hits.append((a+stride*k,stride,w))
print()
print(f"class-6 words found in LEFTOVER bytes (both strides, so double-counted): {sum(c6.values())}")
print(f"  of which entry > 0x096: {sum(c6big.values())}  distinct {len(c6big)}")
if c6big:
    print("  sample:", hits[:12])
    print("  distinct entries >0x096:", ' '.join('%03X'%e for e in sorted(c6big))[:400])
