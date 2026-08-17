import glob,os
BASE=0xE00000
roms=sorted(glob.glob('/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/kn5000_v*_program.rom'))
sig=None
tabs={}
for p in roms:
    img=open(p,'rb').read()
    n=os.path.basename(p)
    # locate xlat by the unique signature row
    S=bytes.fromhex('1f 16 17 18 1f 1f 1f 19 1f 1f 1f 1f 1f 1f 1f 1f'.replace(' ',''))
    i=img.find(S)
    tab=img[i-0x70:i-0x70+128]
    tabs[n]=tab
    # find the accel curve: 32 signed dwords 7,7,7,7,7,6...
    acc=b''.join(int(x).to_bytes(4,'little',signed=True) for x in
        [7,7,7,7,7,6,6,6,5,5,5,4,4,3,2,1,0,-1,-2,-3,-4,-4,-5,-5,-5,-6,-6,-6,-7,-7,-7,-7])
    j=img.find(acc)
    print(f"{n}: xlat@{hex(BASE+i-0x70)} accel_curve@{hex(BASE+j) if j>=0 else 'NOT FOUND'}")
ref=tabs['kn5000_v10_program.rom']
print("\n128-byte xlat table identical across all revisions:",
      all(t==ref for t in tabs.values()))
print("full v10 table:")
for r in range(8):
    print(f"  [{r*16:02x}] "+tabs['kn5000_v10_program.rom'][r*16:r*16+16].hex(' '))
