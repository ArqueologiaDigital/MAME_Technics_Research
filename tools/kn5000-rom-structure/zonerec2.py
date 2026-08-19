from collections import Counter, defaultdict
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
def s16v(v): return v-0x10000 if v>=0x8000 else v
SETB=0x077914
b2=Counter(); b2_low=Counter(); b3=Counter(); trim=Counter()
seen=set()
rows=[]
for i in range(487):
    S=SETB+15*i
    flags=u8(S); ptrA=u32(S+1)+BASE; ptrB=u32(S+5)+BASE
    st=6 if (flags&0x80) else 4
    ptrC=u32(ptrA)+BASE
    Es=set()
    for key in range(128):
        Es.add(u8(ptrA+4+u8(ptrC+key)))
    for E in sorted(Es):
        rec=ptrB+st*E
        if (rec,st) in seen: continue
        seen.add((rec,st))
        sel=u16(rec); v2=u8(rec+2); v3=u8(rec+3)
        b2[v2]+=1
        if v2&0x80: b2_low[v2&0x0F]+=1
        b3[v3]+=1
        if st==6: trim[s16v(u16(rec+4))]+=1
print("distinct zone records:", len(seen))
print("\nbyte+2 values (top 20):", b2.most_common(20))
print("\nwhen bit7 set, low nibble histogram:", dict(b2_low))
print("\nbyte+2 with bit7 set: pan field (bits6:4) histogram:",
      dict(Counter((k>>4)&7 for k,c in b2.items() if k&0x80 for _ in range(c))))
print("\nbyte+3 as signed, min/max:", min((x-256 if x>=128 else x) for x in b3), max((x-256 if x>=128 else x) for x in b3))
print("byte+3 top 15:", [(x-256 if x>=128 else x, c) for x,c in b3.most_common(15)])
print("\nstride-6 trailing word (the C term) top 15:", trim.most_common(15))
print("stride-6 trailing word range:", min(trim), max(trim), " n=", sum(trim.values()))
