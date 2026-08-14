import sys, lzss, io
p=sys.argv[1]
d=open(p,'rb').read()
magic=d[:8]; size=int.from_bytes(d[8:11],'big')
out=lzss.decompress(d[11:])
print(p, magic, hex(size), "got", hex(len(out)))
open(sys.argv[2],'wb').write(out[:size])
