"""Is 'P = N' the CORRECT answer for a page-2 chunk?

If a chunk is a SINGLE-CYCLE waveform, then P = N is right, not a defect. A single-cycle
wave must join seamlessly end-to-start, so the wrap step |x[N-1]-x[0]| should be no larger
than a typical internal step. A multi-cycle recording that merely defeated the detector has
no such constraint.

  continuity ratio  C = |x[N-1] - x[0]| / median(|x[i+1]-x[i]|)
  C ~ 1  => seamless loop, one cycle, P=N correct
  C >> 1 => a cut recording

NULL/CONTROL: page 0 and page 3 chunks (long multi-cycle recordings, medians 1920/8448
samples) must score HIGH. If they score ~1 too, the metric is measuring nothing.
"""
import sys, statistics, collections, struct
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
import kn5000_period_oracle as O
import numpy as np
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
    fl=u8(p);ptrA=u32(p+1)+BASE;ptrB=u32(p+5)+BASE;ptrC=u32(ptrA)+BASE
    st=6 if fl&0x80 else 4
    sl=[u8(ptrC+k) for k in range(128)]
    Em=[u8(ptrA+4+s) for s in range(max(sl)+1)]
    for E in range(max(Em)+1):
        w=u16(ptrB+st*E)
        if (w>>12)&0x4: ref[(w>>12)&3].add(w&0xFFF)
def C(start,n):
    x=np.frombuffer(rom,dtype='<i2',count=n,offset=start).astype(np.float64)
    if n<4: return None
    d=np.abs(np.diff(x)); m=np.median(d)
    if m<1: return None
    return abs(x[-1]-x[0])/m
groups=collections.defaultdict(list)
for p in range(4):
    for idx,(s,n) in enumerate(dirs[p]):
        per=O.detect_period(rom,s,n); fb=(per==(n<<16))
        c=C(s,n)
        if c is None: continue
        tag=f"page{p} " + ("REF " if idx in ref[p] else "UNREF ") + ("fallback" if fb else "period-found")
        groups[tag].append(c)
print(f"{'group':34s} {'n':>5} {'median C':>9} {'frac C<3':>9} {'frac C<10':>10}")
for k in sorted(groups):
    v=groups[k]
    print(f"{k:34s} {len(v):>5} {statistics.median(v):>9.2f} {sum(1 for x in v if x<3)/len(v):>9.2f} {sum(1 for x in v if x<10)/len(v):>10.2f}")
