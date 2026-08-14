import struct, csv, collections, sys
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
ROM='/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307'
rom=open(ROM,'rb').read()
PAGE=0x100000; G=16
def page_dir_verbose(page):
    base=page*PAGE
    u16=lambda o: struct.unpack_from('<H',rom,base+o)[0]
    head=u16(0)
    print(f"page {page}: header word = 0x{head:04X} -> n = {head//4}")
    n=head//4
    ok=True; fails=[]
    param=[];wave=[]
    for i in range(n):
        pp,wo=u16(i*4),u16(i*4+2)
        if i and pp<param[-1]: fails.append(('monotonic',i)); break
        if pp<n*4: fails.append(('overlap',i)); break
        if wo*G>=PAGE: fails.append(('inpage',i)); break
        if u16(pp)!=wo: fails.append(('backref',i,hex(pp),hex(wo),hex(u16(pp)))); break
        param.append(pp);wave.append(wo)
    print(f"   accepted {len(param)}/{n} entries; fails={fails}")
    return n,len(param),wave
tot=0
declared={}
for p in range(4):
    n,acc,wave=page_dir_verbose(p)
    declared[p]=n; tot+=n
    print(f"   distinct wave_offsets: {len(set(wave))}, min 0x{min(wave)*G:06X} max 0x{max(wave)*G:06X}")
print("total declared slots:",tot)
