import sys, struct
from collections import defaultdict, Counter
ROM="/home/fsanches/compartilhado/kn5000_original_roms/kn5000/"
ev=open(ROM+"kn5000_table_data_rom_even.ic3","rb").read()
od=open(ROM+"kn5000_table_data_rom_odd.ic1","rb").read()
n=len(ev)//2
region=bytearray(4*n)
for k in range(n):
    region[4*k+0]=ev[2*k]; region[4*k+1]=ev[2*k+1]
    region[4*k+2]=od[2*k]; region[4*k+3]=od[2*k+1]
region=bytes(region)
BASE=0x050000
def off(S): return S-0x020000
def u8(S): return region[off(S)]
def u16(S): return region[off(S)]|region[off(S)+1]<<8
def u32(S): return int.from_bytes(region[off(S):off(S)+4],'little')
def s16(S):
    v=u16(S); return v-0x10000 if v>=0x8000 else v
SETB=0x077914
STRIDE_OF={}  # (b7,b6,b5)->stride
def stride_for(flags):
    b5=(flags>>5)&1; b6=(flags>>6)&1; b7=(flags>>7)&1
    if b6:
        if b7: return 15 if b5 else 12
        else:  return 13 if b5 else 10
    else:
        return 6 if b7 else 4
rows=[]
clsXstride=Counter()
flagcnt=Counter()
trimvals=defaultdict(set)
byte2=Counter()
byte3=Counter()
for i in range(487):
    S=SETB+15*i
    flags=u8(S)
    ptrA=u32(S+1)+BASE
    ptrB=u32(S+5)+BASE
    kmin=u8(S+9); kmax=u8(S+10); root=u8(S+11); basep=u16(S+12); last=u8(S+14)
    st=stride_for(flags)
    flagcnt[flags]+=1
    ptrC=u32(ptrA)+BASE
    Es=set()
    for key in range(128):
        slot=u8(ptrC+key)
        E=u8(ptrA+4+slot)
        Es.add(E)
    for E in sorted(Es):
        rec=ptrB+st*E
        sel=u16(rec)
        cls=sel>>12
        clsXstride[(cls,st)]+=1
        b2=u8(rec+2); b3=u8(rec+3)
        byte2[b2&0x80]+=1
        if st>=6:
            trim=s16(rec+st-2)
        else:
            trim=None
        trimvals[cls].add(trim)
print("SET flag byte census:", dict(sorted(flagcnt.items())))
print()
print("class x zone-record-stride (count of distinct (SET,E) zone slots):")
for (cls,st),c in sorted(clsXstride.items()):
    print(f"  class {cls}  stride {st:2d}  n={c}")
print()
print("byte+2 bit7 set:", byte2)
