"""The 11 REFERENCED page-2 chunks that fall back: are any of them LONG recordings
(where P=N would be a real defect), or are they all short single-cycle waves
(where P=N is arithmetically the only answer detect_period can give)?
maxlag = min(W//2,2048) with W ~= 2/3*N  =>  maxlag ~= N/3 < N, so a chunk that IS one
cycle has its true period OUTSIDE the search range by construction."""
import sys, struct, collections
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
import kn5000_period_oracle as O
rom=O.load_rom(); d=O.page_dir(rom,2)
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
img=open(SC+'table_data.bin','rb').read(); BASE=0x050000
u8=lambda s: img[s-0x020000]
u16=lambda s: struct.unpack_from('<H',img,s-0x020000)[0]
u32=lambda s: struct.unpack_from('<I',img,s-0x020000)[0]
# entry -> which SETs use it
use=collections.defaultdict(set)
for i in range(487):
    p=0x077914+15*i
    fl=u8(p);ptrA=u32(p+1)+BASE;ptrB=u32(p+5)+BASE;ptrC=u32(ptrA)+BASE
    st=6 if fl&0x80 else 4
    sl=[u8(ptrC+k) for k in range(128)]
    Em=[u8(ptrA+4+s) for s in range(max(sl)+1)]
    for E in range(max(Em)+1):
        w=u16(ptrB+st*E)
        if ((w>>12)&0xF)==6: use[w&0xFFF].add(i)
def maxlag(n):
    off=n//3; W=min(n-off,4096)
    if W<64: off,W=0,min(n,4096)
    return min(W//2,2048)
print(f"{'entry':>6} {'len':>7} {'maxlag':>7} {'P':>10}  used by SETs")
tot=0
for e in sorted(use):
    s,n=d[e]; per=O.detect_period(rom,s,n)
    fb=(per==(n<<16))
    if not fb: continue
    tot+=1
    print(f" 0x{e:03X} {n:>7} {maxlag(n):>7} {'P=N':>10}  {sorted(use[e])}")
print(f"\n{tot} referenced page-2 chunks fall back; ALL have len <= {max(d[e][1] for e in use if O.detect_period(rom,*d[e])==(d[e][1]<<16))} samples")
print("longest REFERENCED page-2 chunk that does NOT fall back:",
      max((d[e][1] for e in use if O.detect_period(rom,*d[e])!=(d[e][1]<<16)), default=0))
