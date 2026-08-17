import hashlib
R='/home/fsanches/compartilhado/technics_roms/roms/kn7000/'
names=['01ctmini.ic21','01custm1.ic21','02custm2.ic21','03custm3.ic21','04custm4.ic21',
       '01custm5.ic21','02custm6.ic21','03custm7.ic21','04custm8.ic21']
data=[open(R+n,'rb').read() for n in names]
assert all(len(d)==0x1e0000 for d in data)
same=[]
for s in range(30):
    blk=[d[s*0x10000:(s+1)*0x10000] for d in data]
    ident = all(b==blk[0] for b in blk)
    if ident: same.append(s)
print('identical 64K sectors (index within loaded data, 0 == flash offset 0x20000):', same)
print('count', len(same), 'of 30')
# also index counting from flash sector 0 of the 64K array (flash 0x10000 == sector 0)
print('same, expressed as 64K-sector index from flash 0x10000:', [s+1 for s in same])
