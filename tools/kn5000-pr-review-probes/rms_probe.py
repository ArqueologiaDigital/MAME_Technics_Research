# Second half of the question: a PCM voice's PEAK is ~2.83x the sine's, but does it
# SOUND ~9 dB louder?  Measures each IC307 recording's RMS over the whole recording and
# over the tail (the region the sustain loop actually repeats), against the placeholder
# sine's own RMS = SINE_PEAK/sqrt(2) = 8192.
import sys, array, bisect, math
PAGE=0x100000
data=open(sys.argv[1],'rb').read()
SINE_RMS = 11585/math.sqrt(2.0)
whole=[];tail=[]
for p in range(4):
    pg=data[p*PAGE:(p+1)*PAGE]
    u16=lambda o: pg[o]|(pg[o+1]<<8)
    head=u16(0); n=head//4
    param=[u16(i*4) for i in range(n)]; wave=[u16(i*4+2) for i in range(n)]
    s=sorted(set(wave))
    for i in range(n):
        j=bisect.bisect_right(s,wave[i])
        end = PAGE if j==len(s) else s[j]*16
        off=wave[i]*16
        ns=(end-off)//2 if end>off else 0
        if ns<64: continue
        a=array.array('h'); a.frombytes(pg[off:off+ns*2])
        if sys.byteorder=='big': a.byteswap()
        acc=0
        for v in a: acc+=v*v
        whole.append(math.sqrt(acc/len(a)))
        t=a[int(len(a)*0.9):]
        acc=0
        for v in t: acc+=v*v
        tail.append(math.sqrt(acc/len(t)))
def rep(name,xs):
    xs=sorted(xs); N=len(xs)
    med=xs[N//2]
    print(f"{name}: N={N} median RMS={med:8.1f}  p10={xs[N//10]:8.1f}  p90={xs[int(N*.9)]:8.1f}"
          f"   median vs sine RMS {SINE_RMS:.0f} = {20*math.log10(med/SINE_RMS):+.1f} dB")
rep("whole recording", whole)
rep("last 10% (loop) ", tail)
