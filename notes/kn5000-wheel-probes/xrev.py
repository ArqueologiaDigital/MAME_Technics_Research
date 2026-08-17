import sys, glob, struct
ROMDIR="/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/"
BASE=0xE00000
SIG_HDR2REC = bytes.fromhex("c98bcbcc1fc9ccc0c9ef01cbe1d812f2")   # header->record translator prologue
SIG_VALXLAT = bytes.fromhex("d812cb8dcdcc07cbccc0cbef03cde3d912d9ec02f2")  # value xlat dispatch
SIG_CLASS   = bytes.fromhex("cfcc38cfef01ced6eb12ebc8")           # parser class dispatch
SIG_DESC    = bytes.fromhex("a92100ff")                            # wheel descriptor
SIG_ACCEL   = bytes.fromhex("c9c810d813d8ec02f2")                  # add A,0x10; exts WA; sla 2; lda XBC,imm
for v in [5,6,7,8,9,10]:
    fn = ROMDIR+f"kn5000_v{v}_program.rom"
    d = open(fn,'rb').read()
    print(f"===== v{v} =====")
    # header->record
    hits=[i for i in range(len(d)) if d.startswith(SIG_HDR2REC,i)]
    for h in hits:
        tbl = struct.unpack("<I", d[h+16:h+20])[0] & 0xFFFFFF
        toff = tbl - BASE
        rec77 = d[toff+0x77]
        cnt19 = d[toff:toff+0x80].count(0x19)
        print(f"  hdr2rec @ {BASE+h:06X}  table=0x{tbl:06X}  table[0x77]=0x{rec77:02X}  count(0x19)in128={cnt19}")
    if not hits: print("  hdr2rec: NOT FOUND")
    # value xlat
    hits=[i for i in range(len(d)) if d.startswith(SIG_VALXLAT,i)]
    for h in hits:
        tbl = struct.unpack("<I", d[h+21:h+25])[0] & 0xFFFFFF
        toff = tbl - BASE
        p1f = struct.unpack("<I", d[toff+0x1F*4:toff+0x1F*4+4])[0] & 0xFFFFFF
        print(f"  valxlat @ {BASE+h:06X}  table=0x{tbl:06X}  [0x1F]=0x{p1f:06X}  code={d[p1f-BASE:p1f-BASE+5].hex()}")
    if not hits: print("  valxlat: NOT FOUND")
    # class dispatch
    hits=[i for i in range(len(d)) if d.startswith(SIG_CLASS,i)]
    for h in hits:
        tbl = struct.unpack("<I", d[h+12:h+16])[0] & 0xFFFFFF
        toff = tbl-BASE
        ents=[struct.unpack("<I", d[toff+4*k:toff+4*k+4])[0]&0xFFFFFF for k in range(8)]
        print(f"  classdisp @ {BASE+h:06X} table=0x{tbl:06X} class2=0x{ents[2]:06X} class6=0x{ents[6]:06X}")
    if not hits: print("  classdisp: NOT FOUND")
    # descriptor
    hits=[i for i in range(len(d)) if d.startswith(SIG_DESC,i)]
    print(f"  desc a92100ff hits: {[hex(BASE+h) for h in hits]}")
    for h in hits:
        print(f"     handler=0x{struct.unpack('<I',d[h+4:h+8])[0]&0xFFFFFF:06X}")
    # count of byte pair a9 21
    n=sum(1 for i in range(len(d)-1) if d[i]==0xa9 and d[i+1]==0x21)
    print(f"  'a9 21' pair count in image: {n}")
    # accel
    hits=[i for i in range(len(d)) if d.startswith(SIG_ACCEL,i)]
    for h in hits:
        tbl = struct.unpack("<I", d[h+9:h+13])[0] & 0xFFFFFF
        print(f"  accel-index @ {BASE+h:06X} curve=0x{tbl:06X}")
