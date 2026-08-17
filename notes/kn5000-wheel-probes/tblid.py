import struct,hashlib
ROMDIR="/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/"
BASE=0xE00000
SIG=bytes.fromhex("c98bcbcc1fc9ccc0c9ef01cbe1d812f2")
for v in [5,6,7,8,9,10]:
    d=open(ROMDIR+f"kn5000_v{v}_program.rom",'rb').read()
    h=d.find(SIG)
    tbl=struct.unpack("<I",d[h+16:h+20])[0]&0xFFFFFF
    t=d[tbl-BASE:tbl-BASE+0x80]
    print(f"v{v}: table 0x{tbl:06X} sha1={hashlib.sha1(t).hexdigest()}")
