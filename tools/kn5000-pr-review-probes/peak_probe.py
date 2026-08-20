# Replicates kn5000_tonegen_device::parse_page_directories() for IC307 and measures
# the peak |sample| of every recording, to test whether PCM voices really can reach
# +/-32767 (i.e. 2.83x the SINE_PEAK=11585 placeholder).
import sys, struct
PAGE=0x100000
data=open(sys.argv[1],'rb').read()
allpk=[]
for p in range(4):
    pg=data[p*PAGE:(p+1)*PAGE]
    u16=lambda o: pg[o]|(pg[o+1]<<8)
    head=u16(0)
    if not head or (head&3): print(f"page {p}: no dir"); continue
    n=head//4
    if n*4 > PAGE-4: print(f"page {p}: bad"); continue
    param=[];wave=[];ok=True
    for i in range(n):
        param.append(u16(i*4)); wave.append(u16(i*4+2))
        if i and param[i]<param[i-1]: ok=False;break
        if param[i] < n*4: ok=False;break
        if wave[i]*16 >= PAGE: ok=False;break
        if u16(param[i]) != wave[i]: ok=False;break
    if not ok: print(f"page {p}: failed validation"); continue
    s=sorted(set(wave))
    import bisect
    pk=[]
    for i in range(n):
        j=bisect.bisect_right(s,wave[i])
        end = PAGE if j==len(s) else s[j]*16
        off=wave[i]*16
        ns=(end-off)//2 if end>off else 0
        if ns==0: continue
        buf=pg[off:off+ns*2]
        m=0
        for v in struct.iter_unpack('<h', buf[:len(buf)//2*2]):
            a=abs(v[0])
            if a>m: m=a
        pk.append(m)
    allpk+=pk
    pk.sort()
    print(f"page {p}: {n} recordings, {len(pk)} with PCM;  peak|s| min={pk[0]} median={pk[len(pk)//2]} p90={pk[int(len(pk)*.9)]} max={pk[-1]}")
allpk.sort()
N=len(allpk)
print(f"\nALL {N} recordings: median={allpk[N//2]}  p75={allpk[int(N*.75)]}  p90={allpk[int(N*.9)]}  max={allpk[-1]}")
for t in (11585, 16384, 23170, 30000, 32000):
    c=sum(1 for x in allpk if x>=t)
    print(f"  peak >= {t:5d} : {c:5d} / {N}  ({100.0*c/N:.1f}%)")
