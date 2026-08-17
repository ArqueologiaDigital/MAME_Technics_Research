import zlib, hashlib
R='/home/fsanches/compartilhado/technics_roms/roms/kn7000/'
for name, ev, od in (('program','kn7000_program_even.rom','kn7000_program_odd.rom'),
                     ('table','kn7000_table_even.rom','kn7000_table_odd.rom')):
    payload = open(R+f'kn7000_{name}.rom','rb').read()
    print(f'{name}: payload {len(payload)} bytes')
    for pad in (b'\xff', b'\x00'):
        d = payload + pad*(0x400000-len(payload))
        e = bytes(b for i in range(0,len(d),4) for b in d[i:i+2])
        o = bytes(b for i in range(0,len(d),4) for b in d[i+2:i+4])
        for lbl, got, fn in (('even',e,ev),('odd',o,od)):
            want = open(R+fn,'rb').read()
            print(f'  pad={pad.hex()} {lbl}: match={got==want} crc={zlib.crc32(got)&0xffffffff:08x}')
