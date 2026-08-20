R='/home/fsanches/compartilhado/kn5000_original_roms/kn5000/'
ev=open(R+'kn5000_table_data_rom_even.ic3','rb').read()
od=open(R+'kn5000_table_data_rom_odd.ic1','rb').read()
# ROM_LOAD32_WORD even at 0, odd at 2 -> interleave 2-byte groups
rom=bytearray(0x200000)
for i in range(0,len(ev),2):
    rom[i*2:i*2+2]=ev[i:i+2]
    rom[i*2+2:i*2+4]=od[i:i+2]
N=len(rom)
def u8(a): return rom[a]
def u16(a): return rom[a]|(rom[a+1]<<8)
def u32(a): return u16(a)|(u16(a+2)<<16)
ROOT=0x30000
rel=lambda r:(ROOT+r)&0xFFFFFFFF
set_base=rel(u32(ROOT+0x30))
stride=u16(ROOT+0xEC)
limit=min(u32(ROOT+0x24),u32(ROOT+0x28),u32(ROOT+0x2C))
print("set_base %x stride %d limit %x base_rel %x"%(set_base,stride,limit,u32(ROOT+0x30)))
n_sets=(limit-u32(ROOT+0x30))//stride
print("n_sets",n_sets)
weights={}
maxread=0
flags_hist={}
for i in range(n_sets):
    d=set_base+stride*i
    if d+0x0E>=N: print("ABORT d",i);break
    flags=u8(d); zstride=6 if (flags>>7)&1 else 4
    ptr_a=rel(u32(d+1)); ptr_b=rel(u32(d+5))
    if ptr_a+4>=N or ptr_b>=N: print("ABORT ptr",i,hex(ptr_a),hex(ptr_b));break
    ptr_c=rel(u32(ptr_a))
    if ptr_c+127>=N: print("ABORT ptrc",i);break
    coarse=0 if (flags>>1)&1 else u16(d+0x0C)-((u8(d+0x0B)<<8)+0x80)
    flags_hist[flags]=flags_hist.get(flags,0)+1
    for key in range(128):
        idx=u8(ptr_c+key)
        a=ptr_a+4+idx
        maxread=max(maxread,a)
        rec=ptr_b+zstride*u8(a)
        if rec+zstride>N: print("ABORT rec",i);break
        trim=0
        if zstride==6:
            trim=u16(rec+4)
            if trim>=0x8000: trim-=0x10000
        sel=u16(rec)
        weights.setdefault(sel,{})
        weights[sel][coarse+trim]=weights[sel].get(coarse+trim,0)+1
print("selectors",len(weights))
multi=sum(1 for s in weights if len(weights[s])>1)
print("multi-C selectors",multi)
print("max byte read at ptr_a+4+idx: 0x%x (region 0x%x)"%(maxread,N))
tab=[]
for sel in sorted(weights):
    best=max(weights[sel].items(), key=lambda kv:kv[1])
    tab.append((sel,best[0]))
print("sum", sum(c for _,c in tab))
out=[c for _,c in tab]
print("C range", min(out), max(out))
print("C outside int16:", sum(1 for c in out if c<-32768 or c>32767))
import collections
print("sample entries", tab[:8])
# how many selectors resolve into bank1(IC307)?
def dec(sel):
    cls=(sel>>12)&0xf
    return ((cls>>2)&3, cls&3, sel&0xfff)
b=collections.Counter(dec(s)[0] for s,_ in tab)
print("bank histogram", b)

import collections
cls_hist=collections.Counter((s>>12)&0xf for s,_ in tab)
print("cls histogram", dict(sorted(cls_hist.items())))
mx=collections.defaultdict(int)
for s,_ in tab: mx[(s>>12)&0xf]=max(mx[(s>>12)&0xf], s&0xfff)
print("max chunk per cls", dict(sorted(mx.items())))
