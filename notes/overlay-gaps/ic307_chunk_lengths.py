# Question: does any IC307 recording exceed 65535 samples (the overlay's 16.16
# uint32 wave_offset limit) or land on a multiple of 65536 (the branch's 110de5031e7 case)?
# Usage: python3 -I ic307_chunk_lengths.py <kn5000_waveform_rom.ic307>
import sys
rom = open(sys.argv[1], 'rb').read()
PAGE = 0x100000
mx = 0; over = 0; mult = 0; total = 0
for p in range(4):
    pg = rom[p*PAGE:(p+1)*PAGE]
    u16 = lambda o: pg[o] | (pg[o+1] << 8)
    head = u16(0)
    if not head or head & 3:
        print('page', p, 'no dir'); continue
    n = head // 4
    wave = [u16(i*4+2) for i in range(n)]
    s = sorted(set(wave))
    import bisect
    for w in wave:
        i = bisect.bisect_right(s, w)
        end = PAGE if i == len(s) else s[i]*16
        smp = (end - w*16)//2
        total += 1; mx = max(mx, smp)
        if smp > 65535: over += 1
        if smp and smp % 65536 == 0: mult += 1
    print('page', p, 'n', n)
print('chunks', total, 'max samples', mx, '>65535:', over, 'multiple of 65536:', mult)
