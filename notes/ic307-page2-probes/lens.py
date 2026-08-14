import sys, collections, statistics, struct
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
import kn5000_period_oracle as O
rom=O.load_rom(); dirs={p:O.page_dir(rom,p) for p in range(4)}
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
d=dirs[2]; R=ref[2]
print("page-2 referenced entries: %d, max index 0x%03X; directory has %d entries"%(len(R),max(R),len(d)))
print("unreferenced BELOW the max referenced index (0..0x096):", sum(1 for i in range(0,max(R)+1) if i not in R))
print("unreferenced ABOVE it (0x097..0x%03X):"%(len(d)-1), sum(1 for i in range(max(R)+1,len(d)) if i not in R))
lr=[d[i][1] for i in sorted(R)]
lu=[d[i][1] for i in range(len(d)) if i not in R]
print("\nlength (samples): referenced   median %d  mean %d  min %d max %d"%(statistics.median(lr),statistics.mean(lr),min(lr),max(lr)))
print("length (samples): UNreferenced median %d  mean %d  min %d max %d"%(statistics.median(lu),statistics.mean(lu),min(lu),max(lu)))
print("\npage-2 length histogram, all 1072 chunks (top 15 values):")
h=collections.Counter(n for _,n in d)
for v,c in h.most_common(15): print(f"   {v:6d} samples  x{c:4d}   {'(power of 2)' if v and (v&(v-1))==0 else ''}")
tot=len(d); p2=sum(c for v,c in h.items() if v and (v&(v-1))==0)
print(f"   -> {p2}/{tot} = {100.0*p2/tot:.1f}% of page-2 chunks are an exact power-of-two length")
for p in (0,1,3):
    hh=collections.Counter(n for _,n in dirs[p]); t=len(dirs[p])
    pp=sum(c for v,c in hh.items() if v and (v&(v-1))==0)
    print(f"   NULL page {p}: {pp}/{t} = {100.0*pp/t:.1f}% power-of-two")
