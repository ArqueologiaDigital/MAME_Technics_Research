R='/home/fsanches/compartilhado/technics_roms/roms/kn5000/'
ev=open(R+'kn5000_table_data_rom_even.ic3','rb').read()
od=open(R+'kn5000_table_data_rom_odd.ic1','rb').read()
img=bytearray(0x200000)
for k in range(len(ev)//2):
    img[4*k+0]=ev[2*k]; img[4*k+1]=ev[2*k+1]
    img[4*k+2]=od[2*k]; img[4*k+3]=od[2*k+1]
open('/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/table_data.bin','wb').write(img)
print("built", len(img), "bytes")
