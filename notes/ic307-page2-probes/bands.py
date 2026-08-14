import sys, collections, statistics, struct
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
import kn5000_period_oracle as O
rom=O.load_rom(); d=O.page_dir(rom,2)
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
img=open(SC+'table_data.bin','rb').read(); BASE=0x050000
u8=lambda s: img[s-0x020000]
u16=lambda s: struct.unpack_from('<H',img,s-0x020000)[0]
u32=lambda s: struct.unpack_from('<I',img,s-0x020000)[0]
R=set()
for i in range(487):
    p=0x077914+15*i
    fl=u8(p);ptrA=u32(p+1)+BASE;ptrB=u32(p+5)+BASE;ptrC=u32(ptrA)+BASE
    st=6 if fl&0x80 else 4
    sl=[u8(ptrC+k) for k in range(128)]
    Em=[u8(ptrA+4+s) for s in range(max(sl)+1)]
    for E in range(max(Em)+1):
        w=u16(ptrB+st*E)
        if ((w>>12)&0xF)==6: R.add(w&0xFFF)
print(f"{'entry band':>14} {'n':>5} {'median len':>11} {'%pow2':>7} {'%referenced':>12}")
for lo in range(0,1072,64):
    hi=min(lo+64,1072)
    L=[d[i][1] for i in range(lo,hi)]
    p2=sum(1 for x in L if x and (x&(x-1))==0)
    rf=sum(1 for i in range(lo,hi) if i in R)
    print(f"  0x{lo:03X}-0x{hi-1:03X} {hi-lo:>5} {statistics.median(L):>11.0f} {100.0*p2/len(L):>6.1f}% {100.0*rf/(hi-lo):>11.1f}%")
print()
print("first 24 directory entries of page 2 (idx: start_off len ref?):")
for i in range(24):
    print(f"   {i:3d} 0x{d[i][0]-0x200000:06X} {d[i][1]:6d} {'REF' if i in R else ''}")
print("...")
for i in range(148,160):
    print(f"   {i:3d} 0x{d[i][0]-0x200000:06X} {d[i][1]:6d} {'REF' if i in R else ''}")
