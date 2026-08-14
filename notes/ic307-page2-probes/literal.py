"""LITERAL SEARCH the task asked for, with a POSITIVE CONTROL.
Q: does a wave-select word naming bank1/page2 (0x6xxx) live in the PROGRAM or SUB-PROGRAM ROM?
Method: search for the exact zone-record byte strings, in every ROM. A search that finds the
page-0/1/3 records but not the page-2 ones would refute 'page 2 is selected'. A search that
finds NONE of them in a given ROM proves the zone tables are not in that ROM at all."""
import struct
R='/home/fsanches/compartilhado/technics_roms/roms/kn5000/'
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
roms={
 'table_data (IC3+IC1 interleaved)': open(SC+'table_data.bin','rb').read(),
 'kn5000_v10_program.rom'          : open(R+'kn5000_v10_program.rom','rb').read(),
 'kn5000_subprogram_v142.rom'      : open(R+'kn5000_subprogram_v142.rom','rb').read(),
 'kn5000_subcpu_boot.ic30'         : open(R+'kn5000_subcpu_boot.ic30','rb').read(),
 'kn5000_rhythm_data_rom.ic14'     : open(R+'kn5000_rhythm_data_rom.ic14','rb').read(),
 'kn5000_custom_data_rom.ic19'     : open(R+'kn5000_custom_data_rom.ic19','rb').read(),
}
probes={
 'PIANO  zone rec E=0..2  (class 7 = page 3)': bytes.fromhex('007000f7cef2' '017000ee4ef9' '027000f7bdf4'),
 'SET 62 zone rec E=0..2  (class 6 = PAGE 2)': None,   # filled below
 'SET277 zone rec E=0..2  (class 6 = PAGE 2)': None,
 'SET 49 GUITAR rec E=0..3 (class 3 = bank0)': bytes.fromhex('0030d0ff' '0130a0fc' '023080fd' '033080f9'),
}
td=roms['table_data (IC3+IC1 interleaved)']
def rd(sub,n): return td[sub-0x020000:sub-0x020000+n]
probes['SET 62 zone rec E=0..2  (class 6 = PAGE 2)']=rd(0x081D22,18)
probes['SET277 zone rec E=0..2  (class 6 = PAGE 2)']=rd(0x07D690,18)
# also a class-4 (page 0) and class-5 (page 1) probe, as the positive control for pages 0 and 1
import csv
# find a stride-6 class-4 and class-5 set from the walk
for name,addr,n in (('class-4 (page 0) rec, SET 486','',0),):
    pass
for label,p in probes.items():
    print(f"\nPROBE {label}:  {p.hex()}")
    for rn,rb in roms.items():
        idx=[]; s=0
        while True:
            k=rb.find(p,s)
            if k<0: break
            idx.append(k); s=k+1
            if len(idx)>4: break
        print(f"   {rn:36s} {'HIT at '+', '.join('0x%06X'%i for i in idx) if idx else 'no hit'}")
