import sys,re
R='/home/fsanches/compartilhado/technics_roms/roms/kn2400/'
e=open(R+'kn2400_program_even.rom','rb').read()
o=open(R+'kn2400_program_odd.rom','rb').read()
out=bytearray()
for i in range(0,len(e),2):
    out+=e[i:i+2]+o[i:i+2]
open('kn2400_interleaved.bin','wb').write(out)
d=bytes(out)
for pat in (b'KN2600',b'KN-2600',b'KN2400',b'KN-2400',b'kn2600',b'2600',b'PR54',b'PR-54'):
    idx=[m.start() for m in re.finditer(re.escape(pat), d)]
    print(pat.decode(), len(idx), idx[:8])
