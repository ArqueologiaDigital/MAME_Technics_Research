#!/usr/bin/env python3
"""Anatomy of the NULL's false positives + a data-driven coincidence model for page 2."""
import struct, collections, math
PAGE=0x100000; GRAN=16
def ent(buf, base, n):
    pp=[buf[base+i*4]|(buf[base+i*4+1]<<8) for i in range(n)]
    wo=[buf[base+i*4+2]|(buf[base+i*4+3]<<8) for i in range(n)]
    return pp,wo

cases = [("ic19 @0xa67fe n=8640","/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_custom_data_rom.ic19",0xa67fe,8640),
         ("v10 @0x8d076 n=448","/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_v10_program.rom",0x8d076,448),
         ("ic307 p2 @0x200000 n=1072","/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307",0x200000,1072),
         ("ic307 p0 @0x000000 n=198","/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307",0x000000,198)]
for label,path,base,n in cases:
    buf=open(path,'rb').read(); pp,wo=ent(buf,base,n)
    gaps=[pp[i]-pp[i-1] for i in range(1,n)]
    print(f"\n{label}")
    print(f"  distinct pp {len(set(pp))}/{n}   distinct wo {len(set(wo))}/{n}   distinct pairs {len(set(zip(pp,wo)))}/{n}")
    print(f"  pp gaps: min {min(gaps)} max {max(gaps)} zero-gaps {gaps.count(0)}  "
          f"histogram {collections.Counter(gaps).most_common(6)}")
    print(f"  first 6 (pp,wo): {[(hex(a),hex(b)) for a,b in zip(pp[:6],wo[:6])]}")
    tgt = set()
    for p in set(pp): tgt.add(p); tgt.add(p+1)
    print(f"  distinct BYTES the back-reference constrains: {len(tgt)} "
          f"(={len(tgt)/2:.1f} independent u16 if disjoint)")

# ---- data-driven coincidence model for page 2 ----
rom=open("/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307",'rb').read()
base=0x200000; n=1072; pp,wo=ent(rom,base,n)
# empirical distribution of u16 values read at EVEN offsets across page 2
vals=collections.Counter(struct.unpack_from("<%dH"%(PAGE//2), rom, base))
tot=sum(vals.values())
ps=[vals.get(w,0)/tot for w in wo]
ps_floor=[max(p,1.0/tot) for p in ps]
logp=sum(math.log10(p) for p in ps_floor)
print(f"\nCOINCIDENCE MODEL (page 2, empirical u16 frequencies of the actual page):")
print(f"  per-entry P(random u16 == this wave_off): mean {sum(ps)/n:.3e}  "
      f"median {sorted(ps)[n//2]:.3e}  max {max(ps):.3e}  entries with p=0 in page: {sum(1 for p in ps if p==0)}")
print(f"  joint log10 P (independent) = {logp:.1f}   i.e. P ~ 1e{logp:.0f}")
print(f"  uniform-u16 model: log10 P = {-16*n*math.log10(2):.1f}")
print(f"  Bonferroni over every even base in a 4MB ROM (2.1e6) x every n: log10 correction ~ +7")
