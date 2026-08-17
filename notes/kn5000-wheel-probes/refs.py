ROMDIR="/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/"
BASE=0xE00000
# TLCS-900 16-bit direct operand encodings: prefix C1/D1/E1/F1 (byte/word/long/imm) + lo hi
import sys
target=bytes([0x94,0x8e])
for v in [5,6,7,8,9,10]:
    d=open(ROMDIR+f"kn5000_v{v}_program.rom",'rb').read()
    hits=[]
    for i in range(len(d)-3):
        if d[i] in (0xC1,0xD1,0xE1,0xF1) and d[i+1:i+3]==target:
            hits.append(BASE+i)
    print(f"v{v}: operand '(0x8E94)' candidate sites: {len(hits)} -> {[hex(x) for x in hits[:12]]}")
