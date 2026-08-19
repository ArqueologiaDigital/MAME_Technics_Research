import struct, collections
R='/home/fsanches/compartilhado/kn5000-roms-disasm/original_ROMs/'
ev=open(R+'kn5000_table_data_rom_even.ic3','rb').read()
od=open(R+'kn5000_table_data_rom_odd.ic1','rb').read()
img=bytearray(0x200000)
for i in range(0,0x100000,2):
    img[2*i]=ev[i]; img[2*i+1]=ev[i+1]
    img[2*i+2]=od[i]; img[2*i+3]=od[i+1]
u8=lambda a: img[a]
u16=lambda a: img[a]|(img[a+1]<<8)
u32=lambda a: int.from_bytes(img[a:a+4],'little')
ROOT=0x30000
rel=lambda r: ROOT+r
print('root sig u32[0]=%08x  +30=%08x +34=%08x +38=%08x +24=%08x +28=%08x +2c=%08x stride=%d'%(
    u32(ROOT),u32(ROOT+0x30),u32(ROOT+0x34),u32(ROOT+0x38),u32(ROOT+0x24),u32(ROOT+0x28),u32(ROOT+0x2c),u16(ROOT+0xec)))
setbase=rel(u32(ROOT+0x30)); stride=u16(ROOT+0xec)
end=min(rel(u32(ROOT+0x24)),rel(u32(ROOT+0x28)),rel(u32(ROOT+0x2c)))
n=(end-setbase); print('setbase=%05x n_bytes=%d n_sets=%s rem=%d'%(setbase,n,n//stride,n%stride))
n=n//stride
flags=collections.Counter(); roots=collections.Counter(); bit1=[]
for i in range(n):
    d=setbase+stride*i; f=u8(d); flags[f]+=1; roots[u8(d+0x0b)]+=1
    if f&2: bit1.append((i,u8(d+0x0b),u16(d+0x0c)))
print('flags',dict(sorted(flags.items())))
print('roots',dict(sorted(roots.items())))
print('bit1 count',len(bit1),bit1[:15])
# build C tables both ways
def build(bit1rule):
    w=collections.defaultdict(collections.Counter)
    for i in range(n):
        d=setbase+stride*i; f=u8(d); zs=6 if f&0x80 else 4
        pA=rel(u32(d+1)); pB=rel(u32(d+5)); pC=rel(u32(pA))
        piv=(u8(d+0x0b)<<8)+0x80; base=u16(d+0x0c)
        coarse=0 if (bit1rule and (f&2)) else base-piv
        for k in range(128):
            E=u8(pA+4+u8(pC+k)); rec=pB+zs*E
            sel=u16(rec); trim=struct.unpack('<h',img[rec+4:rec+6])[0] if zs==6 else 0
            w[sel][coarse+trim]+=1
    return w
old=build(False); new=build(True)
def summ(w,name):
    amb=sum(1 for s in w if len(w[s])>1)
    zero=sum(1 for s in w if w[s].most_common(1)[0][0]==0)
    print('%s: selectors=%d ambiguous=%d modal-zero=%d'%(name,len(w),amb,zero))
summ(old,'unconditional (shipped rule)'); summ(new,'bit1-aware')
diff=[s for s in old if old[s].most_common(1)[0][0]!=new[s].most_common(1)[0][0]]
print('selectors whose modal C changes:',len(diff))
print('sample',[(hex(s),old[s].most_common(1)[0][0],new[s].most_common(1)[0][0]) for s in sorted(diff)[:8]])
# compare against shipped hxx
import re
h=open('/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn5000_pitch_trim.hxx').read()
rows=re.findall(r'\{\s*0x([0-9a-fA-F]{4})\s*,\s*(-?\d+)\s*,\s*(\d)\s*\}',h)
ship={int(a,16):(int(b),int(c)) for a,b,c in rows}
print('shipped rows',len(ship))
mo=sum(1 for s in ship if s in old and old[s].most_common(1)[0][0]==ship[s][0])
mn=sum(1 for s in ship if s in new and new[s].most_common(1)[0][0]==ship[s][0])
print('shipped matches unconditional walk: %d/%d ; matches bit1-aware walk: %d/%d'%(mo,len(ship),mn,len(ship)))
