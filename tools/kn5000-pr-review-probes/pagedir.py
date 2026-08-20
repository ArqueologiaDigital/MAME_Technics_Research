# Read-only re-implementation of kn5000_tonegen_device::parse_page_directories()
# (kn5000_tonegen.cpp:84-154 on branch kn5000_tonegen_combined) to check whether any
# recording in IC307 exceeds 65535 samples, which would overflow `samples << 16`.
import sys, struct
path = "/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307"
data = open(path,'rb').read()
PAGE = 0x100000
print("file size 0x%X" % len(data))
for p in range(4):
    base = p*PAGE
    pg = data[base:base+PAGE]
    u16 = lambda o: pg[o] | (pg[o+1]<<8)
    head = u16(0)
    if head == 0 or (head & 3):
        print("page %d: rejected (head=0x%X)" % (p, head)); continue
    n = head//4
    if n*4 > PAGE-4:
        print("page %d: rejected (n too big)" % p); continue
    param=[];wave=[];ok=True
    for i in range(n):
        param.append(u16(i*4)); wave.append(u16(i*4+2))
        if i and param[i] < param[i-1]: ok=False;break
        if param[i] < n*4: ok=False;break
        if wave[i]*16 >= PAGE: ok=False;break
        if u16(param[i]) != wave[i]: ok=False;break
    if not ok:
        print("page %d: rejected at entry %d" % (p,i)); continue
    srt = sorted(set(wave))
    import bisect
    lens=[]
    for i in range(n):
        j = bisect.bisect_right(srt, wave[i])
        end_off = PAGE if j==len(srt) else srt[j]*16
        off = wave[i]*16
        lens.append((end_off-off)//2 if end_off>off else 0)
    mx = max(lens); over = [i for i,l in enumerate(lens) if l >= 65536]
    print("page %d: %d recordings, max %d samples (0x%X), %d recordings >= 65536 samples"
          % (p, n, mx, mx, len(over)))
    if over:
        print("   e.g. entries %s ; their lengths %s" % (over[:8], [lens[i] for i in over[:8]]))
        for i in over[:8]:
            print("      entry %d: samples=%d  (samples<<16) mod 2^32 = %d" % (i, lens[i], (lens[i]<<16) & 0xffffffff))
