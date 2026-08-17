import sys, glob, os
BASE=0xE00000
def load(p):
    return open(p,'rb').read()
def rd(img,a,n=1):
    return img[a-BASE:a-BASE+n]
def u32(b): return int.from_bytes(b,'little')

roms=sorted(glob.glob('/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/kn5000_v*_program.rom'))
print("=== v10 spot checks ===")
v10=load('/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/kn5000_v10_program.rom')
print("xlat tbl 0xEDA03C[0x77] =", hex(rd(v10,0xEDA03C+0x77)[0]))
print("xlat row 0x70..0x7F:", rd(v10,0xEDA03C+0x70,16).hex(' '))
print("count of 0x19 in 128-byte xlat table:", rd(v10,0xEDA03C,128).count(0x19))
print("indices with 0x19:", [hex(i) for i,b in enumerate(rd(v10,0xEDA03C,128)) if b==0x19])
print("jumptbl 0xFC4965[0..7]:", [hex(u32(rd(v10,0xFC4965+4*i,4))) for i in range(8)])
print("dispatch tbl 0xEDA0BC[0x1F] =", hex(u32(rd(v10,0xEDA0BC+4*0x1F,4))))
print("bytes at 0xFC6DE9:", rd(v10,0xFC6DE9,6).hex(' '))
print("descriptor 0xED9B86:", rd(v10,0xED9B86,4).hex(' '))
print("desc ptr tbl 0xED9C1E[0x19] =", hex(u32(rd(v10,0xED9C1E+4*0x19,4))))
print("vector 0xFFFF88 (INTRX1) =", hex(u32(rd(v10,0xFFFF88,4))))
print("accel curve 0xEA98E2, 32 signed dwords:")
acc=[int.from_bytes(rd(v10,0xEA98E2+4*i,4),'little',signed=True) for i in range(32)]
print("  ", acc)

print()
print("=== index formula check: which wire bytes map to xlat index 0x77 ===")
hits=[h for h in range(256) if (((h&0xC0)>>1)|(h&0x1F))==0x77]
print("  ", [hex(h) for h in hits])

print()
print("=== cross-revision: locate the xlat table by SIGNATURE in every ROM ===")
# signature: the 16-byte row containing 0x19 at offset 0x77
sig = rd(v10,0xEDA03C+0x70,16)
print("signature row (idx 0x70..0x7F):", sig.hex(' '))
for p in roms:
    img=load(p)
    name=os.path.basename(p)
    # find full 128-byte table by searching the signature row
    occ=[m for m in range(len(img)) if img[m:m+16]==sig]
    locs=[hex(BASE+m-0x70) for m in occ]
    # also check the a9 21 descriptor
    a921=[hex(BASE+i) for i in range(len(img)-1) if img[i]==0xA9 and img[i+1]==0x21]
    print(f"{name}: xlat_table_base={locs}  'a9 21' occurrences={a921}")
