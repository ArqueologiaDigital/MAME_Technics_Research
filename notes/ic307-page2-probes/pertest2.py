import sys, collections, statistics, math
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
import kn5000_period_oracle as O
import struct
rom=O.load_rom()
dirs={p:O.page_dir(rom,p) for p in range(4)}
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
img=open(SC+'table_data.bin','rb').read()
BASE=0x050000
u8=lambda s: img[s-0x020000]
u16=lambda s: struct.unpack_from('<H',img,s-0x020000)[0]
u32=lambda s: struct.unpack_from('<I',img,s-0x020000)[0]
ref=collections.defaultdict(set)
for i in range(487):
    p=0x077914+15*i
    flags=u8(p);ptrA=u32(p+1)+BASE;ptrB=u32(p+5)+BASE;ptrC=u32(ptrA)+BASE
    st=6 if flags&0x80 else 4
    slots=[u8(ptrC+k) for k in range(128)]
    Emap=[u8(ptrA+4+s) for s in range(max(slots)+1)]
    for E in range(max(Emap)+1):
        w=u16(ptrB+st*E)
        if (w>>12)&0x4: ref[(w>>12)&3].add(w&0xFFF)
print("=== chunk length (samples) per page ===")
for p in range(4):
    L=[n for _,n in dirs[p]]
    print(f" page {p}: n={len(L):5d} median {statistics.median(L):8.0f}  mean {statistics.mean(L):9.0f}  min {min(L):6d} max {max(L):8d}  n<32: {sum(1 for x in L if x<32)}")
print()
print("=== fallback decomposition, page 2 ===")
d=dirs[2]; R=ref[2]
cats=collections.Counter()
for idx,(s,n) in enumerate(d):
    per=O.detect_period(rom,s,n)
    k='REF' if idx in R else 'UNREF'
    if n<32: cats[(k,'too-short (n<32) -> instant P=N')]+=1
    elif per==(n<<16): cats[(k,'autocorr gate rejected -> P=N')]+=1
    elif per==0: cats[(k,'P=0 (aperiodic)')]+=1
    else: cats[(k,'real period found')]+=1
for k in ('REF','UNREF'):
    tot=sum(v for (kk,_),v in cats.items() if kk==k)
    print(f"  {k} ({tot} chunks):")
    for (kk,c),v in sorted(cats.items()):
        if kk==k: print(f"      {c:36s} {v:5d}  {100.0*v/tot:5.1f}%")
# excluding n<32, to match the previously-quoted 500/1050
tot=sum(1 for s,n in d if n>=32); fb=sum(1 for s,n in d if n>=32 and O.detect_period(rom,s,n)==(n<<16))
print(f"\n  page2 excluding the {sum(1 for s,n in d if n<32)} chunks with n<32:  {fb}/{tot} fall back ({100.0*fb/tot:.1f}%)  <- reconciles the quoted '500 of 1050'")
# Fisher exact / chi2 for REF vs UNREF fallback on page 2
a=sum(1 for i,(s,n) in enumerate(d) if i in R and O.detect_period(rom,s,n)==(n<<16))
b=len(R)-a
c=sum(1 for i,(s,n) in enumerate(d) if i not in R and O.detect_period(rom,s,n)==(n<<16))
dd=(len(d)-len(R))-c
print(f"\n=== 2x2: page-2 fallback vs referenced ===\n  REF   fallback {a:4d}  ok {b:4d}\n  UNREF fallback {c:4d}  ok {dd:4d}")
n=a+b+c+dd
chi2=n*(a*dd-b*c)**2/((a+b)*(c+dd)*(a+c)*(b+dd))
print(f"  chi2 = {chi2:.2f} (1 df)  -> p = {math.erfc(math.sqrt(chi2/2)):.2e}")
print(f"  odds ratio = {(a*dd)/(b*c):.3f}  (referenced chunks are {1/((a*dd)/(b*c)):.2f}x LESS likely to fall back)")
