import struct,re
ROMDIR="/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/"
BASE=0xE00000
# Enqueue prologue: muls WA,0x0003 ; lda XDE,imm16 ; exts XWA ; add XWA,XDE
pat = re.compile(rb'\xd8\x09\x03\x00\xf1(..)\x32\xe8\x13\xea\x80', re.S)
# also the helper "lda XHL,imm16 ; ret" preceded by nothing; find 'f1 xx yy 33 0e'
for v in [5,6,7,8,9,10]:
    d=open(ROMDIR+f"kn5000_v{v}_program.rom",'rb').read()
    out=[]
    for m in pat.finditer(d):
        addr = struct.unpack("<H", m.group(1))[0]
        out.append((BASE+m.start(), addr))
    print(f"v{v}: Enqueue sites -> {[(hex(a),hex(l)) for a,l in out]}")
    # count-var: the 'ld C,(imm16)' right before
    for m in pat.finditer(d):
        s=m.start()
        print(f"    ctx @ {BASE+s-16:06X}: {d[s-16:s+16].hex()}")
