"""Cross-check: the tonegen source (kn5000_tonegen.cpp ~L310) blames the audible 'extreme
noise' on +040 = 0x505B and 0x5046 -- class 5 = PAGE 1, ~1500-sample chunks stretched 11-19x.
If page 1 is where the LONG referenced fallbacks live, page 2 is the wrong suspect."""
import sys, struct, collections, statistics
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
import kn5000_period_oracle as O
rom=O.load_rom()
for w in (0x505B,0x5046):
    p=(w>>12)&3; e=w&0xFFF
    d=O.page_dir(rom,p); s,n=d[e]
    per=O.detect_period(rom,s,n)
    print(f"+040=0x{w:04X} -> page {p} entry 0x{e:03X}: len {n} samples, detect_period -> {'P=N' if per==(n<<16) else 'P=%.1f'%(per/65536)}")
print()
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
img=open(SC+'table_data.bin','rb').read(); BASE=0x050000
u8=lambda s: img[s-0x020000]
u16=lambda s: struct.unpack_from('<H',img,s-0x020000)[0]
u32=lambda s: struct.unpack_from('<I',img,s-0x020000)[0]
ref=collections.defaultdict(set)
for i in range(487):
    p=0x077914+15*i
    fl=u8(p);ptrA=u32(p+1)+BASE;ptrB=u32(p+5)+BASE;ptrC=u32(ptrA)+BASE
    st=6 if fl&0x80 else 4
    sl=[u8(ptrC+k) for k in range(128)]
    Em=[u8(ptrA+4+s) for s in range(max(sl)+1)]
    for E in range(max(Em)+1):
        w=u16(ptrB+st*E)
        if (w>>12)&0x4: ref[(w>>12)&3].add(w&0xFFF)
print("REFERENCED chunks that fall back, by page, with their LENGTHS")
print("(a fallback on a chunk of >=512 samples is a real defect: it gets stretched, audibly)")
for p in range(4):
    d=O.page_dir(rom,p)
    L=[d[e][1] for e in sorted(ref[p]) if O.detect_period(rom,*d[e])==(d[e][1]<<16)]
    big=[x for x in L if x>=512]
    print(f"  page {p}: {len(L):3d} referenced fallbacks, lengths median {statistics.median(L) if L else 0:.0f} max {max(L) if L else 0}"
          f"  |  of which >=512 samples: {len(big)}  {sorted(big)}")
