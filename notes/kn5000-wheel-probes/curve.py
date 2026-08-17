import struct
ROMDIR="/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/"
BASE=0xE00000
for v,addr in [(5,0xEA97CE),(10,0xEA98E2)]:
    d=open(ROMDIR+f"kn5000_v{v}_program.rom",'rb').read()
    o=addr-BASE
    vals=[struct.unpack("<i",d[o+4*i:o+4*i+4])[0] for i in range(32)]
    print(f"v{v} curve @ {addr:06X}:")
    for i,x in enumerate(vals):
        wire = i-16  # index = sext8(wire+0x10) -> wire = i-16 for i in 0..31? careful
        print(f"   idx {i:2d} (wire {i-16:+3d}) = {x}")
